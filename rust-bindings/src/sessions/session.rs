// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};

use pyo3::prelude::*;
use pyo3::types::PyDict;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_model::types::{JobParameterType, JobParameterValue, JobParameterValues};
use openjd_model::types::{TaskParameterSet, TaskParameterType, TaskParameterValue};
use openjd_sessions::action::ActionState;
use openjd_sessions::action_status::ActionStatus;
use openjd_sessions::error::SessionError;
use openjd_sessions::limits::SessionLimits;
use openjd_sessions::session::{Session, SessionConfig, SessionState};

use super::errors::session_err_to_py;
use super::types::{PyActionStatus, PySessionState};
use crate::expr::expr_value::py_to_expr_value;
use crate::model::job::PyEnvironment;
use crate::model::job::PyStepScript;

use super::session_user::{PyPosixSessionUser, PyWindowsSessionUser};

fn extract_job_parameter_values(py_dict: &Bound<'_, PyDict>) -> PyResult<JobParameterValues> {
    let mut result = JobParameterValues::new();
    for (key, val) in py_dict.iter() {
        let name: String = key.extract()?;
        // Direct passthrough when the Python caller already has a
        // typed ``JobParameterValue`` pyclass — unwrap to the
        // underlying Rust struct, no dict round-trip required.
        if let Ok(jpv) = val.extract::<crate::model::types::PyJobParameterValue>() {
            result.insert(name, jpv.inner);
            continue;
        }
        if let Ok(inner_dict) = val.cast::<PyDict>() {
            let type_str: String = inner_dict
                .get_item("type")?
                .ok_or_else(|| pyo3::exceptions::PyKeyError::new_err("Missing 'type' key"))?
                .extract()?;
            let param_type = JobParameterType::from_spec_str(&type_str).ok_or_else(|| {
                pyo3::exceptions::PyValueError::new_err(format!(
                    "Unknown parameter type: {type_str}"
                ))
            })?;
            let value_obj = inner_dict
                .get_item("value")?
                .ok_or_else(|| pyo3::exceptions::PyKeyError::new_err("Missing 'value' key"))?;
            let value = py_to_expr_value(&value_obj)?;
            result.insert(name, JobParameterValue { param_type, value });
        } else {
            return Err(pyo3::exceptions::PyTypeError::new_err(
                "Each parameter value must be a JobParameterValue or \
                 a dict with 'type' and 'value' keys",
            ));
        }
    }
    Ok(result)
}

fn extract_path_mapping_rules(
    rules: Option<Vec<crate::expr::PyPathMappingRule>>,
) -> Option<Vec<openjd_expr::path_mapping::PathMappingRule>> {
    rules.map(|r| r.into_iter().map(|p| p.inner).collect())
}

fn extract_task_parameter_values(py_dict: &Bound<'_, PyDict>) -> PyResult<TaskParameterSet> {
    let mut result = TaskParameterSet::new();
    for (key, val) in py_dict.iter() {
        let name: String = key.extract()?;
        // Direct passthrough when the Python caller already has a
        // typed ``TaskParameterValue`` pyclass — unwrap to the
        // underlying Rust struct, no dict round-trip required.
        if let Ok(tpv) = val.extract::<crate::model::types::PyTaskParameterValue>() {
            result.insert(name, tpv.inner);
            continue;
        }
        if let Ok(inner_dict) = val.cast::<PyDict>() {
            let type_str: String = inner_dict
                .get_item("type")?
                .ok_or_else(|| pyo3::exceptions::PyKeyError::new_err("Missing 'type' key"))?
                .extract()?;
            let param_type = TaskParameterType::from_spec_str(&type_str).ok_or_else(|| {
                pyo3::exceptions::PyValueError::new_err(format!(
                    "Unknown task parameter type: {type_str}"
                ))
            })?;
            let value_obj = inner_dict
                .get_item("value")?
                .ok_or_else(|| pyo3::exceptions::PyKeyError::new_err("Missing 'value' key"))?;
            let value = py_to_expr_value(&value_obj)?;
            result.insert(name, TaskParameterValue { param_type, value });
        } else {
            // Accept raw values as STRING type
            let value = py_to_expr_value(&val)?;
            result.insert(
                name,
                TaskParameterValue {
                    param_type: TaskParameterType::String,
                    value,
                },
            );
        }
    }
    Ok(result)
}

/// Snapshot of session state that Python can read without holding the session lock.
#[derive(Clone)]
struct StateSnapshot {
    session_id: String,
    state: SessionState,
    working_directory: String,
    files_directory: String,
    action_status: Option<ActionStatus>,
    environments_entered: Vec<String>,
}

/// Lock a mutex, recovering the guard even if a previous holder panicked.
///
/// Action work runs on detached `std::thread::spawn` threads. A panic on
/// one of those threads (e.g. inside async session code) would poison
/// `session` / `snapshot`, after which every later `.lock().unwrap()` —
/// including the read-only property getters invoked from the Python
/// thread — would itself panic and surface as an uncatchable
/// `PanicException`, permanently wedging the session object. Recovering
/// the poisoned guard keeps the session readable so the failure can be
/// reported through the normal `ActionStatus` channel instead of
/// cascading.
///
/// Caveat: `into_inner()` recovers the lock but not the invariants — a
/// thread that panicked mid-mutation may have left the data readable but
/// not necessarily consistent. For the read-only snapshot getters that's
/// harmless (worst case: stale fields). For the `session` slot, the
/// panic-handling path in `run_action` forces a terminal FAILED
/// `ActionStatus`, which closes the practical risk of re-dispatching an
/// action onto a half-mutated session.
fn lock_recover<T>(m: &Mutex<T>) -> std::sync::MutexGuard<'_, T> {
    m.lock().unwrap_or_else(|poisoned| poisoned.into_inner())
}

/// Build a terminal FAILED `ActionStatus` carrying `message`.
///
/// Used when an action thread can't even start (e.g. the Tokio runtime
/// fails to build) so the Python poller observes a terminal state and
/// stops waiting on RUNNING rather than spinning forever.
fn failed_action_status(message: &str) -> ActionStatus {
    ActionStatus {
        state: openjd_sessions::action::ActionState::Failed,
        progress: None,
        status_message: None,
        fail_message: Some(message.to_string()),
        exit_code: None,
        started_at: None,
        ended_at: None,
    }
}

/// Convert a timeout or time limit given in seconds. Zero passes through to
/// the crate, which refuses a zero `run_subprocess` timeout and reads a zero
/// cancel time limit as "terminate now". A negative, NaN or infinite value
/// has no `Duration`, so it raises `ValueError` here rather than panicking.
fn seconds_to_duration(name: &str, seconds: f64) -> PyResult<std::time::Duration> {
    std::time::Duration::try_from_secs_f64(seconds).map_err(|_| {
        pyo3::exceptions::PyValueError::new_err(format!(
            "{name} must be a finite, non-negative number of seconds, got {seconds}"
        ))
    })
}

/// What an action thread tells the Python thread that handed it a call.
///
/// A non-blocking method must not return until it knows whether the crate
/// accepted the call. The crate refuses a call (wrong state, unknown or
/// duplicate environment, out-of-order exit, bad `run_subprocess`
/// arguments) before it touches the session, and such a refusal has to
/// raise. It accepts a call by reporting the call's action through the
/// session callback, before its first `.await`; from then on every outcome,
/// errors included, is recorded on the action status.
enum CallOutcome {
    /// The crate accepted the call and its action is `Running`.
    Started,
    /// The crate returned before the action reported `Running`.
    /// `accepted == false` means it refused the call and changed nothing, so
    /// `error` is the refusal. Otherwise the action ended without running a
    /// subprocess (an environment with no script, or a failure before the
    /// action started), and its status says how.
    Returned {
        accepted: bool,
        error: Option<SessionError>,
    },
}

/// The call an action thread is running, until the Python thread that made
/// it has been told the outcome.
struct PendingCall {
    tx: std::sync::mpsc::SyncSender<CallOutcome>,
    /// Set by the session callback: the crate reported an action for this
    /// call, so it accepted it.
    accepted: bool,
}

type PendingSlot = Arc<Mutex<Option<PendingCall>>>;

/// Body of a spawned action thread.
///
/// Builds a lightweight current-thread Tokio runtime, runs the action
/// closure to completion while catching panics, then **always** returns
/// the `Session` to the shared slot and refreshes the snapshot — even if
/// the runtime failed to build or the future panicked. This guarantees:
///
/// * the session is never left permanently "taken" (which would wedge
///   every later call), and
/// * a panic in async session code can't escape the detached thread to
///   poison shared state silently and tear down the interpreter's view
///   of the session.
///
/// A runtime-build failure is surfaced as a terminal FAILED
/// `ActionStatus` so the Python-side poller terminates cleanly. A panic
/// inside the action is likewise converted into a terminal FAILED
/// `ActionStatus` (rather than copying the possibly-still-Running real
/// session state), so the poller never hangs on a panicked action.
///
/// If the calling Python thread is still waiting (the action never
/// reported `Running`), it is told the outcome after the session is back in
/// its slot, so it can make its next call straight away.
fn run_action<F>(
    mut session: Session,
    session_arc: Arc<Mutex<Option<Session>>>,
    snapshot: Arc<Mutex<StateSnapshot>>,
    pending: PendingSlot,
    action: F,
) where
    F: FnOnce(&tokio::runtime::Runtime, &mut Session) -> Result<(), SessionError>,
{
    let rt = match tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
    {
        Ok(rt) => rt,
        Err(e) => {
            // Couldn't build a runtime (e.g. fd/thread exhaustion). The
            // crate never saw the call, so treat it as refused: put the
            // session back unchanged and raise in the caller.
            let call = lock_recover(&pending).take();
            *lock_recover(&session_arc) = Some(session);
            tell(
                call,
                false,
                Some(SessionError::Runtime(format!(
                    "failed to start action runtime: {e}"
                ))),
            );
            return;
        }
    };

    // Catch panics so a panic inside async session code still restores
    // the session below rather than leaking out of this detached thread.
    let action_result =
        std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| action(&rt, &mut session)));

    // Take the waiting call, if any, before the session goes back: once it
    // is back another thread can start a call and install its own.
    let call = lock_recover(&pending).take();
    let accepted = call.as_ref().is_none_or(|c| c.accepted);

    // Restore the session BEFORE refreshing the snapshot, holding the guard
    // across both so there's no window where a caller finds the slot empty.
    // Python callers watch `state` via the snapshot and dispatch the next
    // action the moment it transitions out of Running; if the snapshot
    // updated first they could find the mutex still empty.
    let guard = {
        let mut slot = lock_recover(&session_arc);
        *slot = Some(session);
        slot
    };

    match action_result {
        Ok(result) => {
            if let Some(s) = guard.as_ref() {
                PySession::update_snapshot(s, &snapshot);
            }
            // Still under the session guard, so no next action can have
            // started and been overwritten.
            if accepted {
                if let Err(e) = &result {
                    record_unreported_failure(&snapshot, e);
                }
            }
            drop(guard);
            tell(call, accepted, result.err());
        }
        Err(payload) => {
            // The action panicked mid-run. `catch_unwind` kept the session
            // usable for future calls, but the real `session.state()` may
            // still read Running with no terminal `ActionStatus` — which
            // would leave the Python poller waiting forever. Force a
            // terminal FAILED status and drop out of RUNNING, mirroring the
            // runtime-build-failure branch above.
            {
                let mut snap = lock_recover(&snapshot);
                snap.state = SessionState::Ready;
                snap.action_status = Some(failed_action_status(&format!(
                    "action panicked during execution: {}",
                    panic_detail(payload.as_ref())
                )));
            }
            drop(guard);
            tell(call, true, None);
        }
    }
}

/// Tell a waiting Python thread how its call came out. Nothing to do when
/// it was already told the action started.
fn tell(call: Option<PendingCall>, accepted: bool, error: Option<SessionError>) {
    if let Some(call) = call {
        // `send` fails only when the receiver is gone, and the caller drops
        // it only after receiving: there is nobody left to tell.
        let _ = call.tx.send(CallOutcome::Returned { accepted, error });
    }
}

/// An accepted call returned an error. The crate records every such error
/// on the action status (`fail_action_setup`, `drive_action`, or a failed
/// script's own status), so this normally changes nothing. If the status
/// doesn't show a failure, record the error there rather than lose it.
fn record_unreported_failure(snapshot: &Arc<Mutex<StateSnapshot>>, e: &SessionError) {
    let mut snap = lock_recover(snapshot);
    let reported = snap.action_status.as_ref().is_some_and(|st| {
        matches!(
            st.state,
            ActionState::Failed | ActionState::Canceled | ActionState::Timeout
        )
    });
    if !reported {
        snap.action_status = Some(failed_action_status(&e.to_string()));
    }
}

/// Best-effort extraction of a human-readable message from a caught panic
/// payload (`std::panic::catch_unwind`'s `Err` value), which is usually the
/// `&str` or `String` passed to `panic!`.
fn panic_detail(payload: &(dyn std::any::Any + Send)) -> String {
    if let Some(s) = payload.downcast_ref::<&'static str>() {
        (*s).to_string()
    } else if let Some(s) = payload.downcast_ref::<String>() {
        s.clone()
    } else {
        "unknown panic".to_string()
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.sessions._v1", name = "Session")]
pub(crate) struct PySession {
    /// The Rust session. None while a background thread has taken ownership.
    ///
    /// Lock it only with the GIL released (`Python::detach`). `cleanup` and
    /// `cancel_action` call into the crate while holding it, the crate logs,
    /// and `pyo3_log` takes the GIL for each record, so a thread that held
    /// the GIL while waiting for this lock would deadlock with them.
    session: Arc<Mutex<Option<Session>>>,
    /// Snapshot updated after each state change, readable without blocking on the session.
    snapshot: Arc<Mutex<StateSnapshot>>,
    /// Thread-safe cancel handle, obtained at construction. Delivers a cancel
    /// to whichever action is running even while the `Session` value is owned
    /// by a background action thread — the case where `Session::cancel_action`
    /// is unreachable (it needs `&mut Session`).
    cancel_handle: Arc<openjd_sessions::session::SessionCancelHandle>,
    /// The call whose caller is waiting to learn whether the crate accepted
    /// it. Shared with the session callback, which marks it accepted.
    pending: PendingSlot,
}

impl PySession {
    fn update_snapshot(session: &Session, snapshot: &Arc<Mutex<StateSnapshot>>) {
        let mut snap = lock_recover(snapshot);
        snap.state = session.state();
        snap.action_status = session.action_status();
        snap.environments_entered = session.environments_entered().to_vec();
    }

    /// The error for a call made while an action thread owns the session.
    /// The crate itself would refuse it with `InvalidState`, because the
    /// session is `Running` or `Canceling`; give the same message. Until the
    /// action reports `Running` the snapshot may still show the state
    /// before it, so anything else reads as `Running`.
    fn busy_error(&self, expected: &[SessionState]) -> PyErr {
        let current = match lock_recover(&self.snapshot).state {
            s @ (SessionState::Running | SessionState::Canceling) => s,
            _ => SessionState::Running,
        };
        session_err_to_py(SessionError::InvalidState {
            expected: expected.to_vec(),
            current,
        })
    }

    /// Run `action` on a background thread and return once the crate has
    /// accepted it and its action is `Running`, or once it has returned.
    /// A call the crate refuses raises `SessionError` with the crate's
    /// message and leaves the session, its state and its action status as
    /// they were. Every later outcome of an accepted call is reported on the
    /// action status. The GIL is released while waiting, because the action
    /// thread needs it to log.
    fn dispatch<F>(&self, py: Python<'_>, expected: &[SessionState], action: F) -> PyResult<()>
    where
        F: FnOnce(&tokio::runtime::Runtime, &mut Session) -> Result<(), SessionError>
            + Send
            + 'static,
    {
        // The session mutex is only ever locked with the GIL released; see
        // `PySession::session`.
        let session_arc = self.session.clone();
        let Some(session) = py.detach(move || lock_recover(&session_arc).take()) else {
            return Err(self.busy_error(expected));
        };
        let (tx, rx) = std::sync::mpsc::sync_channel(1);
        *lock_recover(&self.pending) = Some(PendingCall {
            tx,
            accepted: false,
        });

        // `run_action` owns the session from here. If the thread can't be
        // spawned, the closure is dropped unrun, so keep the session where
        // it can be recovered, put it back, and raise, as for a refusal.
        let session_slot = Arc::new(Mutex::new(Some(session)));
        let for_thread = session_slot.clone();
        let session_arc = self.session.clone();
        let snapshot = self.snapshot.clone();
        let pending = self.pending.clone();
        let spawned = std::thread::Builder::new()
            .name("openjd-session-action".into())
            .spawn(move || {
                let Some(session) = lock_recover(&for_thread).take() else {
                    return;
                };
                run_action(session, session_arc, snapshot, pending, action)
            });
        if let Err(e) = spawned {
            *lock_recover(&self.pending) = None;
            if let Some(session) = lock_recover(&session_slot).take() {
                let session_arc = self.session.clone();
                py.detach(move || *lock_recover(&session_arc) = Some(session));
            }
            return Err(session_err_to_py(SessionError::Runtime(format!(
                "failed to start the action thread: {e}"
            ))));
        }

        match py.detach(move || rx.recv()) {
            Ok(CallOutcome::Returned {
                accepted: false,
                error: Some(e),
            }) => Err(session_err_to_py(e)),
            // Started, an accepted call that returned (its status says how),
            // or an action thread that ended without saying (it panicked
            // outside `catch_unwind`; the snapshot reports the failure).
            _ => Ok(()),
        }
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PySession {
    /// ``caller_limits`` carries the run-time half of a submitting
    /// service's policy: the resolved-value caps and evaluation
    /// budgets. A session is the enforcement boundary for them — a
    /// worker can run a job that never passed through this process's
    /// template validation or job creation — so pass the same
    /// ``CallerLimits`` value used there. Fields with no run-time
    /// meaning (document sizes, step and task counts) are ignored.
    #[new]
    #[pyo3(signature = (*, session_id, job_parameter_values, path_mapping_rules=None, retain_working_dir=false, os_env_vars=None, session_root_directory=None, user=None, profile=None, caller_limits=None))]
    #[allow(clippy::too_many_arguments)] // PyO3 #[new] mirrors a kwarg-rich public constructor
    fn new(
        session_id: String,
        job_parameter_values: &Bound<'_, PyDict>,
        path_mapping_rules: Option<Vec<crate::expr::PyPathMappingRule>>,
        retain_working_dir: bool,
        os_env_vars: Option<HashMap<String, String>>,
        session_root_directory: Option<PathBuf>,
        user: Option<&Bound<'_, PyAny>>,
        profile: Option<crate::model::profile::PyModelProfile>,
        caller_limits: Option<&crate::model::profile::PyCallerLimits>,
    ) -> PyResult<Self> {
        let params = extract_job_parameter_values(job_parameter_values)?;

        // Accept either `PosixSessionUser` or `WindowsSessionUser`. Both
        // PyO3 wrappers carry an `Arc<dyn SessionUser>` we can pull through
        // unchanged into the session config.
        let user_inner: Option<Arc<dyn openjd_sessions::session_user::SessionUser>> = match user {
            None => None,
            Some(obj) => {
                if let Ok(posix) = obj.extract::<PyPosixSessionUser>() {
                    Some(posix.inner)
                } else if let Ok(win) = obj.extract::<PyRef<PyWindowsSessionUser>>() {
                    Some(win.inner.clone())
                } else {
                    return Err(pyo3::exceptions::PyTypeError::new_err(
                        "user must be a PosixSessionUser or WindowsSessionUser",
                    ));
                }
            }
        };

        // Build the snapshot Arc up front so the callback closure can refresh
        // action_status in real time as the underlying session reports openjd_*
        // directives. Without this, snap.action_status only updates after the
        // run_*/enter_*/exit_* future completes and Python pollers see no
        // mid-action progress.
        //
        // Note: we deliberately mutate only `action_status` here, not `state`.
        // `state` transitions are driven by the Python-visible run_* methods
        // (which set Running, then update_snapshot at the end). Touching state
        // from the callback would race with those.
        let snapshot = Arc::new(Mutex::new(StateSnapshot {
            session_id: session_id.clone(),
            state: SessionState::Ready,
            working_directory: String::new(),
            files_directory: String::new(),
            action_status: None,
            environments_entered: vec![],
        }));
        let snapshot_for_cb = snapshot.clone();
        let pending: PendingSlot = Arc::new(Mutex::new(None));
        let pending_for_cb = pending.clone();
        // The crate calls this for every action it accepts before the
        // action's first `.await`, so the first call for a pending call is
        // its acceptance. On `Running`, the caller is told the action
        // started; `state` is set here, under the snapshot lock and before
        // the action thread's final `update_snapshot`, so it can't
        // overwrite a later state. Lock order: snapshot, then pending.
        let callback = Box::new(move |_session_id: &str, status: &ActionStatus| {
            let mut snap = lock_recover(&snapshot_for_cb);
            snap.action_status = Some(status.clone());
            let mut slot = lock_recover(&pending_for_cb);
            if let Some(call) = slot.as_mut() {
                call.accepted = true;
                if status.state == ActionState::Running {
                    snap.state = SessionState::Running;
                    if let Some(call) = slot.take() {
                        // Fails only if the caller is gone; see `tell`.
                        let _ = call.tx.send(CallOutcome::Started);
                    }
                }
            }
        });

        let config = SessionConfig {
            session_id: session_id.clone(),
            job_parameter_values: params,
            path_mapping_rules: extract_path_mapping_rules(path_mapping_rules),
            retain_working_dir,
            callback: Some(callback),
            os_env_vars,
            session_root_directory,
            user: user_inner,
            profile: profile.map(|p| p.inner),
            cancel_token: None,
            sticky_bit_policy: Default::default(),
            debug_collect_stdout: false,
            echo_openjd_directives: true,
            limits: caller_limits
                .map(|c| SessionLimits::from(&c.inner))
                .unwrap_or_default(),
        };
        let session = Session::with_config(config).map_err(session_err_to_py)?;
        {
            let mut snap = lock_recover(&snapshot);
            snap.state = session.state();
            snap.working_directory = session.working_directory().to_string_lossy().to_string();
            snap.files_directory = session.files_directory().to_string_lossy().to_string();
            snap.action_status = session.action_status();
        }
        let cancel_handle = Arc::new(session.cancel_handle());
        Ok(PySession {
            session: Arc::new(Mutex::new(Some(session))),
            snapshot,
            cancel_handle,
            pending,
        })
    }

    // ── Properties (read from snapshot, never block on running action) ──

    #[getter]
    fn session_id(&self) -> String {
        lock_recover(&self.snapshot).session_id.clone()
    }

    #[getter]
    fn state(&self) -> PySessionState {
        lock_recover(&self.snapshot).state.into()
    }

    #[getter]
    fn working_directory(&self) -> String {
        lock_recover(&self.snapshot).working_directory.clone()
    }

    #[getter]
    fn files_directory(&self) -> String {
        lock_recover(&self.snapshot).files_directory.clone()
    }

    #[getter]
    fn action_status(&self) -> Option<PyActionStatus> {
        lock_recover(&self.snapshot)
            .action_status
            .clone()
            .map(PyActionStatus::from)
    }

    #[getter]
    fn environments_entered(&self) -> Vec<String> {
        lock_recover(&self.snapshot).environments_entered.clone()
    }

    /// Extend the session's path mapping rules with additional rules.
    ///
    /// When several rules match a path, the one whose source path has the
    /// most names wins, and between rules for the same location the
    /// one given last wins, wherever it sits in the list.
    ///
    /// Consumers (notably the Deadline Cloud worker agent's Job Attachments
    /// download action) call this after an action assigns additional path
    /// mappings — e.g. per-storage-profile mappings derived at task-sync time.
    ///
    /// Returns an error if an action is currently in-flight (the underlying
    /// Session has been taken by a background thread). Call this between
    /// actions. Raises `SessionError`, leaving the rules unchanged, when an
    /// added rule is invalid, for example a POSIX or WINDOWS `source_path`
    /// that is not absolute.
    fn extend_path_mapping_rules(
        &self,
        py: Python<'_>,
        additional: Vec<crate::expr::PyPathMappingRule>,
    ) -> PyResult<()> {
        let rules: Vec<openjd_expr::path_mapping::PathMappingRule> =
            additional.into_iter().map(|p| p.inner).collect();
        let session_arc = self.session.clone();
        let result = py.detach(move || {
            lock_recover(&session_arc)
                .as_mut()
                .map(|session| session.extend_path_mapping_rules(rules))
        });
        match result {
            Some(r) => r.map_err(session_err_to_py),
            None => Err(pyo3::exceptions::PyRuntimeError::new_err(
                "cannot extend path mapping rules while an action is running",
            )),
        }
    }

    // ── Non-blocking action methods ──
    //
    // Each returns once its action is `Running` (or, for an action that
    // runs no subprocess, once it has ended) and leaves the rest to a
    // background thread. A call the crate refuses raises `SessionError`
    // with the crate's message, as the Rust method returns `Err`, and
    // changes nothing; that includes a call while another action is
    // running or the session is ending-only. Once the crate has accepted a
    // call, its outcome, including an error before the action's subprocess
    // starts, is on `action_status`.

    /// Enter an environment. Non-blocking: returns the environment
    /// identifier once the onEnter action is running.
    ///
    /// Raises `SessionError` if the session isn't `READY`, if
    /// `identifier` is already entered, or if a second environment with a
    /// wrap hook is entered. A failure after that, such as an environment
    /// variable that doesn't resolve, fails the action; the environment
    /// still counts as entered and must be exited.
    #[pyo3(signature = (*, environment, identifier=None, resolved_symtab=None, os_env_vars=None))]
    fn enter_environment(
        &self,
        py: Python<'_>,
        environment: &PyEnvironment,
        identifier: Option<String>,
        resolved_symtab: Option<&crate::expr::PySerializedSymbolTable>,
        os_env_vars: Option<HashMap<String, String>>,
    ) -> PyResult<String> {
        let env = environment.inner.clone();
        let env_id = match &identifier {
            Some(id) => id.clone(),
            None => {
                let snap = lock_recover(&self.snapshot);
                format!("{}:{}", snap.session_id, uuid::Uuid::new_v4().simple())
            }
        };
        let return_id = env_id.clone();

        // Clone the inner ``SerializedSymbolTable`` (a thin
        // ``serde_json::Value`` wrapper) so the background thread
        // owns it. ``None`` means the runner sees an empty step-scope
        // symtab — ``Param.*``, ``RawParam.*``, and step-level let
        // bindings won't be visible during script-level let-binding
        // evaluation or expression interpolation.
        let resolved = resolved_symtab.map(|st| st.inner.clone());

        self.dispatch(py, &[SessionState::Ready], move |rt, session| {
            rt.block_on(session.enter_environment(
                &env,
                resolved.as_ref(),
                Some(&env_id),
                os_env_vars.as_ref(),
            ))
            .map(|_| ())
        })?;
        Ok(return_id)
    }

    /// Exit an environment. Non-blocking: returns once the onExit action is
    /// running.
    ///
    /// Raises `SessionError` if the session isn't `READY` or
    /// `READY_ENDING`, if `identifier` isn't entered, or if it isn't the
    /// most recently entered environment. A failure after that fails the
    /// action, and the environment still counts as exited.
    #[pyo3(signature = (*, identifier, resolved_symtab=None, keep_session_running=true, os_env_vars=None))]
    fn exit_environment(
        &self,
        py: Python<'_>,
        identifier: String,
        resolved_symtab: Option<&crate::expr::PySerializedSymbolTable>,
        keep_session_running: bool,
        os_env_vars: Option<HashMap<String, String>>,
    ) -> PyResult<()> {
        let resolved = resolved_symtab.map(|st| st.inner.clone());
        self.dispatch(
            py,
            &[SessionState::Ready, SessionState::ReadyEnding],
            move |rt, session| {
                rt.block_on(session.exit_environment(
                    &identifier,
                    resolved.as_ref(),
                    keep_session_running,
                    os_env_vars.as_ref(),
                ))
                .map(|_| ())
            },
        )
    }

    /// Run a task. Non-blocking: returns once the onRun action is running.
    ///
    /// Raises `SessionError` if the session isn't `READY`, for example
    /// because an earlier action failed and the session is ending-only. A
    /// failure after that, such as a task parameter value that can't be
    /// coerced, fails the action.
    ///
    /// `step_name` is surfaced as `WrappedStep.Name` to a wrapping
    /// environment's `onWrapTaskRun` hook (RFC 0008). It defaults to an empty
    /// string when the caller does not supply one.
    #[pyo3(signature = (*, step_script, step_name=None, task_parameter_values=None, resolved_symtab=None, os_env_vars=None))]
    fn run_task(
        &self,
        py: Python<'_>,
        step_script: &PyStepScript,
        step_name: Option<String>,
        task_parameter_values: Option<&Bound<'_, PyDict>>,
        resolved_symtab: Option<&crate::expr::PySerializedSymbolTable>,
        os_env_vars: Option<HashMap<String, String>>,
    ) -> PyResult<()> {
        let script = step_script.inner.clone();
        let step_name = step_name.unwrap_or_default();
        let task_params = match task_parameter_values {
            Some(d) => Some(extract_task_parameter_values(d)?),
            None => None,
        };
        let resolved = resolved_symtab.map(|st| st.inner.clone());

        self.dispatch(py, &[SessionState::Ready], move |rt, session| {
            rt.block_on(session.run_task(
                &step_name,
                &script,
                task_params.as_ref(),
                resolved.as_ref(),
                os_env_vars.as_ref(),
            ))
            .map(|_| ())
        })
    }

    /// Run a subprocess. Non-blocking: returns once it is running.
    ///
    /// Raises `SessionError` if the session isn't `READY`, if `command` is
    /// empty or blank, or if `timeout` is zero, and `ValueError` if
    /// `timeout` is negative, NaN or infinite.
    #[pyo3(signature = (*, command, args=None, timeout=None, os_env_vars=None, use_session_env_vars=true, log_banner_message=None))]
    #[allow(clippy::too_many_arguments)] // PyO3 method mirrors a kwarg-rich public signature
    fn run_subprocess(
        &self,
        py: Python<'_>,
        command: String,
        args: Option<Vec<String>>,
        timeout: Option<f64>,
        os_env_vars: Option<HashMap<String, String>>,
        use_session_env_vars: bool,
        log_banner_message: Option<String>,
    ) -> PyResult<()> {
        let duration = timeout
            .map(|t| seconds_to_duration("timeout", t))
            .transpose()?;
        self.dispatch(py, &[SessionState::Ready], move |rt, session| {
            rt.block_on(session.run_subprocess(
                &command,
                args.as_deref(),
                duration,
                os_env_vars.as_ref(),
                use_session_env_vars,
                log_banner_message.as_deref(),
            ))
            .map(|_| ())
        })
    }

    /// Take an ending-only session (`READY_ENDING`) back to `READY`, so it
    /// accepts `run_task`, `enter_environment` and `run_subprocess` again.
    /// The environments entered, the last action's status and the
    /// environment variables stay as they were.
    ///
    /// Raises `SessionError` if the session isn't `READY_ENDING`. The
    /// crate also refuses after its session-wide cancel token is canceled;
    /// this binding doesn't expose one, so that can't happen here.
    fn clear_ending_only(&self, py: Python<'_>) -> PyResult<()> {
        let session_arc = self.session.clone();
        let snapshot = self.snapshot.clone();
        let result = py.detach(move || {
            let mut guard = lock_recover(&session_arc);
            let session = guard.as_mut()?;
            let r = session.clear_ending_only();
            Self::update_snapshot(session, &snapshot);
            Some(r)
        });
        match result {
            Some(r) => r.map_err(session_err_to_py),
            None => Err(self.busy_error(&[SessionState::ReadyEnding])),
        }
    }

    /// Cancel the running action.
    ///
    /// Raises `SessionError` with the crate's message if no action is
    /// running, and `ValueError` if `time_limit` is negative, NaN or
    /// infinite.
    #[pyo3(signature = (time_limit=None, mark_action_failed=None))]
    fn cancel_action(
        &self,
        py: Python<'_>,
        time_limit: Option<f64>,
        mark_action_failed: Option<bool>,
    ) -> PyResult<()> {
        let duration = time_limit
            .map(|t| seconds_to_duration("time_limit", t))
            .transpose()?;
        let mark_failed = mark_action_failed.unwrap_or(false);
        let session_arc = self.session.clone();
        let snapshot = self.snapshot.clone();
        let handle = self.cancel_handle.clone();
        // The crate reports an action `Running` just before it installs the
        // action's cancel token, so a cancel straight after the call that
        // started it can find no token yet. Keep trying until the token is
        // there or the action thread has given the session back; the gap is
        // well under a millisecond. Give up after `CANCEL_WAIT`, which is
        // only reached when the action thread itself is waiting on this
        // call (a logging handler that cancels, for example). The GIL is
        // released meanwhile.
        const CANCEL_WAIT: std::time::Duration = std::time::Duration::from_secs(2);
        let deadline = std::time::Instant::now() + CANCEL_WAIT;
        py.detach(move || loop {
            {
                let mut guard = lock_recover(&session_arc);
                if let Some(session) = guard.as_mut() {
                    // Between actions, or the action has ended: the crate
                    // decides, and refuses with `InvalidState` unless the
                    // session is `Running` (which it isn't here).
                    let result = session
                        .cancel_action(duration, mark_failed)
                        .map_err(session_err_to_py);
                    Self::update_snapshot(session, &snapshot);
                    return result;
                }
                // Session is owned by a background action thread: deliver
                // through the thread-safe cancel handle, which follows the
                // action's own cancelation method (including cross-user
                // helper delivery), exactly like Session::cancel_action.
                // Holding the session lock means the action thread can't
                // write its final snapshot before the `Canceling` below, so
                // the snapshot can't be left reading `Canceling` after the
                // action has ended.
                if handle.cancel(duration, mark_failed) {
                    lock_recover(&snapshot).state = SessionState::Canceling;
                    return Ok(());
                }
            }
            if std::time::Instant::now() >= deadline {
                return Err(session_err_to_py(SessionError::Runtime(
                    "Cannot cancel: the action has not started yet".into(),
                )));
            }
            std::thread::sleep(std::time::Duration::from_micros(100));
        })
    }

    /// Clean up the session, deleting its working directory unless it is
    /// retained. Does nothing while an action is running. The GIL is
    /// released meanwhile: on Windows the crate retries a removal that
    /// fails for up to about 31 s.
    fn cleanup(&self, py: Python<'_>) {
        let session_arc = self.session.clone();
        let snapshot = self.snapshot.clone();
        py.detach(move || {
            let mut guard = lock_recover(&session_arc);
            if let Some(session) = guard.as_mut() {
                session.cleanup();
                Self::update_snapshot(session, &snapshot);
            }
        });
    }

    fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        // Read out from under the guard and drop it before calling into
        // CPython: `py_str` allocates, an allocation can trigger a GC pass,
        // and a finalizer run by that pass may re-enter this Session and
        // re-lock `snapshot`, which is not reentrant.
        let (session_id, state) = {
            let snap = lock_recover(&self.snapshot);
            (snap.session_id.clone(), snap.state)
        };
        Ok(format!(
            "Session(session_id={}, state=SessionState.{})",
            crate::py_repr::py_str(py, &session_id)?,
            crate::sessions::types::PySessionState::from(state).name()
        ))
    }
}
