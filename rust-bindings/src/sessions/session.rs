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
use openjd_sessions::action_status::ActionStatus;
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

/// Body of a spawned action thread.
///
/// Builds a lightweight current-thread Tokio runtime, runs the action
/// closure to completion while catching panics, then **always** returns
/// the `Session` to the shared slot and refreshes the snapshot — even if
/// the runtime failed to build or the future panicked. This guarantees:
///
/// * the session is never left permanently "taken" (which would wedge
///   every later call into `"An action is already running"`), and
/// * a panic in async session code can't escape the detached thread to
///   poison shared state silently and tear down the interpreter's view
///   of the session.
///
/// A runtime-build failure is surfaced as a terminal FAILED
/// `ActionStatus` so the Python-side poller terminates cleanly. A panic
/// inside the action is likewise converted into a terminal FAILED
/// `ActionStatus` (rather than copying the possibly-still-Running real
/// session state), so the poller never hangs on a panicked action.
fn run_action<F>(
    mut session: Session,
    session_arc: Arc<Mutex<Option<Session>>>,
    snapshot: Arc<Mutex<StateSnapshot>>,
    action: F,
) where
    F: FnOnce(&tokio::runtime::Runtime, &mut Session),
{
    let rt = match tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
    {
        Ok(rt) => rt,
        Err(e) => {
            // Couldn't build a runtime (e.g. fd/thread exhaustion). Mark
            // the action FAILED and drop out of RUNNING so the poller
            // delivers a terminal callback instead of hanging.
            {
                let mut snap = lock_recover(&snapshot);
                snap.state = SessionState::Ready;
                snap.action_status = Some(failed_action_status(&format!(
                    "failed to start action runtime: {e}"
                )));
            }
            *lock_recover(&session_arc) = Some(session);
            return;
        }
    };

    // Catch panics so a panic inside async session code still restores
    // the session below rather than leaking out of this detached thread.
    let action_result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        action(&rt, &mut session);
    }));

    // Restore the session BEFORE refreshing the snapshot, holding the guard
    // across both so there's no window where a caller finds the slot empty.
    // Python callers watch `state` via the snapshot and dispatch the next
    // action the moment it transitions out of Running; if the snapshot
    // updated first they could find the mutex still empty ("An action is
    // already running").
    let guard = {
        let mut slot = lock_recover(&session_arc);
        *slot = Some(session);
        slot
    };

    match action_result {
        Ok(()) => {
            if let Some(s) = guard.as_ref() {
                PySession::update_snapshot(s, &snapshot);
            }
        }
        Err(payload) => {
            // The action panicked mid-run. `catch_unwind` kept the session
            // usable for future calls, but the real `session.state()` may
            // still read Running with no terminal `ActionStatus` — which
            // would leave the Python poller waiting forever. Force a
            // terminal FAILED status and drop out of RUNNING, mirroring the
            // runtime-build-failure branch above.
            let mut snap = lock_recover(&snapshot);
            snap.state = SessionState::Ready;
            snap.action_status = Some(failed_action_status(&format!(
                "action panicked during execution: {}",
                panic_detail(payload.as_ref())
            )));
        }
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
    session: Arc<Mutex<Option<Session>>>,
    /// Snapshot updated after each state change, readable without blocking on the session.
    snapshot: Arc<Mutex<StateSnapshot>>,
    /// Thread-safe cancel handle, obtained at construction. Delivers a cancel
    /// to whichever action is running even while the `Session` value is owned
    /// by a background action thread — the case where `Session::cancel_action`
    /// is unreachable (it needs `&mut Session`).
    cancel_handle: openjd_sessions::session::SessionCancelHandle,
}

impl PySession {
    fn update_snapshot(session: &Session, snapshot: &Arc<Mutex<StateSnapshot>>) {
        let mut snap = lock_recover(snapshot);
        snap.state = session.state();
        snap.action_status = session.action_status();
        snap.environments_entered = session.environments_entered().to_vec();
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PySession {
    #[new]
    #[pyo3(signature = (*, session_id, job_parameter_values, path_mapping_rules=None, retain_working_dir=false, os_env_vars=None, session_root_directory=None, user=None, profile=None))]
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
        let callback = Box::new(move |_session_id: &str, status: &ActionStatus| {
            if let Ok(mut snap) = snapshot_for_cb.lock() {
                snap.action_status = Some(status.clone());
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
        };
        let session = Session::with_config(config).map_err(session_err_to_py)?;
        {
            let mut snap = lock_recover(&snapshot);
            snap.state = session.state();
            snap.working_directory = session.working_directory().to_string_lossy().to_string();
            snap.files_directory = session.files_directory().to_string_lossy().to_string();
            snap.action_status = session.action_status();
        }
        let cancel_handle = session.cancel_handle();
        Ok(PySession {
            session: Arc::new(Mutex::new(Some(session))),
            snapshot,
            cancel_handle,
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
    /// Rules are stored sorted by source-path length (longest first) so that
    /// the most specific rule matches first during FormatString resolution.
    ///
    /// Consumers (notably the Deadline Cloud worker agent's Job Attachments
    /// download action) call this after an action assigns additional path
    /// mappings — e.g. per-storage-profile mappings derived at task-sync time.
    ///
    /// Returns an error if an action is currently in-flight (the underlying
    /// Session has been taken by a background thread). Call this between
    /// actions.
    fn extend_path_mapping_rules(
        &self,
        additional: Vec<crate::expr::PyPathMappingRule>,
    ) -> PyResult<()> {
        let mut guard = lock_recover(&self.session);
        let session = guard.as_mut().ok_or_else(|| {
            pyo3::exceptions::PyRuntimeError::new_err(
                "cannot extend path mapping rules while an action is running",
            )
        })?;
        let rules: Vec<openjd_expr::path_mapping::PathMappingRule> =
            additional.into_iter().map(|p| p.inner).collect();
        session.extend_path_mapping_rules(rules);
        Ok(())
    }

    // ── Non-blocking action methods ──

    /// Enter an environment. Non-blocking — spawns the onEnter action on a
    /// background thread and returns the environment identifier immediately.
    #[pyo3(signature = (*, environment, identifier=None, resolved_symtab=None, os_env_vars=None))]
    fn enter_environment(
        &self,
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

        // Take the session out of the mutex so the background thread owns it
        let mut guard = lock_recover(&self.session);
        let session = guard.take().ok_or_else(|| {
            pyo3::exceptions::PyRuntimeError::new_err("An action is already running")
        })?;
        drop(guard);

        // Update snapshot to RUNNING and CLEAR action_status.
        // The worker's poll loop treats a non-None action_status as "the current
        // action has reported state". If we leave the previous action's status
        // here, the poll loop will immediately fire a stale terminal callback
        // for the new action — causing the worker to think envEnter / run_task
        // finished in ~1ms with the previous action's SUCCEEDED result.
        {
            let mut snap = lock_recover(&self.snapshot);
            snap.state = SessionState::Running;
            snap.action_status = None;
        }

        let session_arc = self.session.clone();
        let snapshot = self.snapshot.clone();

        std::thread::spawn(move || {
            run_action(session, session_arc, snapshot, move |rt, session| {
                let env_ref = os_env_vars.as_ref();
                let _ = rt.block_on(session.enter_environment(
                    &env,
                    resolved.as_ref(),
                    Some(&env_id),
                    env_ref,
                ));
            });
        });

        Ok(return_id)
    }

    /// Exit an environment. Non-blocking — spawns the onExit action on a
    /// background thread.
    #[pyo3(signature = (*, identifier, resolved_symtab=None, keep_session_running=true, os_env_vars=None))]
    fn exit_environment(
        &self,
        identifier: String,
        resolved_symtab: Option<&crate::expr::PySerializedSymbolTable>,
        keep_session_running: bool,
        os_env_vars: Option<HashMap<String, String>>,
    ) -> PyResult<()> {
        let resolved = resolved_symtab.map(|st| st.inner.clone());

        let mut guard = lock_recover(&self.session);
        let session = guard.take().ok_or_else(|| {
            pyo3::exceptions::PyRuntimeError::new_err("An action is already running")
        })?;
        drop(guard);

        {
            let mut snap = lock_recover(&self.snapshot);
            snap.state = SessionState::Running;
            snap.action_status = None;
        }

        let session_arc = self.session.clone();
        let snapshot = self.snapshot.clone();

        std::thread::spawn(move || {
            run_action(session, session_arc, snapshot, move |rt, session| {
                let env_ref = os_env_vars.as_ref();
                let _ = rt.block_on(session.exit_environment(
                    &identifier,
                    resolved.as_ref(),
                    keep_session_running,
                    env_ref,
                ));
            });
        });

        Ok(())
    }

    /// Run a task. Non-blocking — spawns the onRun action on a background thread.
    ///
    /// `step_name` is surfaced as `WrappedStep.Name` to a wrapping
    /// environment's `onWrapTaskRun` hook (RFC 0008). It defaults to an empty
    /// string when the caller does not supply one.
    #[pyo3(signature = (*, step_script, step_name=None, task_parameter_values=None, resolved_symtab=None, os_env_vars=None))]
    fn run_task(
        &self,
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

        let mut guard = lock_recover(&self.session);
        let session = guard.take().ok_or_else(|| {
            pyo3::exceptions::PyRuntimeError::new_err("An action is already running")
        })?;
        drop(guard);

        {
            let mut snap = lock_recover(&self.snapshot);
            snap.state = SessionState::Running;
            snap.action_status = None;
        }

        let session_arc = self.session.clone();
        let snapshot = self.snapshot.clone();

        std::thread::spawn(move || {
            run_action(session, session_arc, snapshot, move |rt, session| {
                let env_ref = os_env_vars.as_ref();
                let task_ref = task_params.as_ref();
                let _ = rt.block_on(session.run_task(
                    &step_name,
                    &script,
                    task_ref,
                    resolved.as_ref(),
                    env_ref,
                ));
            });
        });

        Ok(())
    }

    /// Run a subprocess. Non-blocking — spawns on a background thread.
    #[pyo3(signature = (*, command, args=None, timeout=None, os_env_vars=None, use_session_env_vars=true, log_banner_message=None))]
    fn run_subprocess(
        &self,
        command: String,
        args: Option<Vec<String>>,
        timeout: Option<f64>,
        os_env_vars: Option<HashMap<String, String>>,
        use_session_env_vars: bool,
        log_banner_message: Option<String>,
    ) -> PyResult<()> {
        let mut guard = lock_recover(&self.session);
        let session = guard.take().ok_or_else(|| {
            pyo3::exceptions::PyRuntimeError::new_err("An action is already running")
        })?;
        drop(guard);

        {
            let mut snap = lock_recover(&self.snapshot);
            snap.state = SessionState::Running;
            snap.action_status = None;
        }

        let session_arc = self.session.clone();
        let snapshot = self.snapshot.clone();

        std::thread::spawn(move || {
            run_action(session, session_arc, snapshot, move |rt, session| {
                let duration = timeout.map(std::time::Duration::from_secs_f64);
                let env_ref = os_env_vars.as_ref();
                let args_ref = args.as_deref();
                let banner_ref = log_banner_message.as_deref();
                let _ = rt.block_on(session.run_subprocess(
                    &command,
                    args_ref,
                    duration,
                    env_ref,
                    use_session_env_vars,
                    banner_ref,
                ));
            });
        });

        Ok(())
    }

    fn cancel_action(
        &self,
        time_limit: Option<f64>,
        mark_action_failed: Option<bool>,
    ) -> PyResult<()> {
        let duration = time_limit.map(std::time::Duration::from_secs_f64);
        let mark_failed = mark_action_failed.unwrap_or(false);
        // Direct path when the session is not taken (e.g. between actions):
        // Session::cancel_action also performs the Running -> Canceling state
        // transition, which the handle cannot (it doesn't own the Session).
        let mut guard = lock_recover(&self.session);
        if let Some(session) = guard.as_mut() {
            let result = session
                .cancel_action(duration, mark_failed)
                .map_err(session_err_to_py);
            Self::update_snapshot(session, &self.snapshot);
            return result;
        }
        drop(guard);

        // Session is owned by a background action thread: deliver through the
        // thread-safe cancel handle. Cancellation follows the action's own
        // cancelation method (including cross-user helper delivery), exactly
        // like Session::cancel_action.
        if self.cancel_handle.cancel(duration, mark_failed) {
            // The handle cannot set the session's transient Canceling state;
            // reflect it in the snapshot so Python-side pollers observe the
            // cancel-in-progress phase until the terminal state lands.
            let mut snap = lock_recover(&self.snapshot);
            snap.state = SessionState::Canceling;
            Ok(())
        } else {
            Err(pyo3::exceptions::PyRuntimeError::new_err(
                "Cannot cancel: no action is running",
            ))
        }
    }

    fn cleanup(&self) {
        let mut guard = lock_recover(&self.session);
        if let Some(session) = guard.as_mut() {
            session.cleanup();
            Self::update_snapshot(session, &self.snapshot);
        }
    }

    fn __repr__(&self) -> String {
        let snap = lock_recover(&self.snapshot);
        format!("Session(id={:?}, state={:?})", snap.session_id, snap.state)
    }
}
