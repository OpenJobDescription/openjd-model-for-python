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
                "Each parameter value must be a dict with 'type' and 'value' keys",
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

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.sessions._v1", name = "Session")]
pub(crate) struct PySession {
    /// The Rust session. None while a background thread has taken ownership.
    session: Arc<Mutex<Option<Session>>>,
    /// Snapshot updated after each state change, readable without blocking on the session.
    snapshot: Arc<Mutex<StateSnapshot>>,
}

impl PySession {
    fn update_snapshot(session: &Session, snapshot: &Arc<Mutex<StateSnapshot>>) {
        let mut snap = snapshot.lock().unwrap();
        snap.state = session.state();
        snap.action_status = session.action_status();
        snap.environments_entered = session.environments_entered().to_vec();
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PySession {
    #[new]
    #[pyo3(signature = (*, session_id, job_parameter_values, path_mapping_rules=None, retain_working_dir=false, os_env_vars=None, session_root_directory=None, user=None))]
    fn new(
        session_id: String,
        job_parameter_values: &Bound<'_, PyDict>,
        path_mapping_rules: Option<Vec<crate::expr::PyPathMappingRule>>,
        retain_working_dir: bool,
        os_env_vars: Option<HashMap<String, String>>,
        session_root_directory: Option<PathBuf>,
        user: Option<&Bound<'_, PyAny>>,
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
            profile: None,
            cancel_token: None,
            sticky_bit_policy: Default::default(),
            debug_collect_stdout: false,
            echo_openjd_directives: true,
        };
        let session = Session::with_config(config).map_err(session_err_to_py)?;
        {
            let mut snap = snapshot.lock().unwrap();
            snap.state = session.state();
            snap.working_directory = session.working_directory().to_string_lossy().to_string();
            snap.files_directory = session.files_directory().to_string_lossy().to_string();
            snap.action_status = session.action_status();
        }
        Ok(PySession {
            session: Arc::new(Mutex::new(Some(session))),
            snapshot,
        })
    }

    // ── Properties (read from snapshot, never block on running action) ──

    #[getter]
    fn session_id(&self) -> String {
        self.snapshot.lock().unwrap().session_id.clone()
    }

    #[getter]
    fn state(&self) -> PySessionState {
        self.snapshot.lock().unwrap().state.into()
    }

    #[getter]
    fn working_directory(&self) -> String {
        self.snapshot.lock().unwrap().working_directory.clone()
    }

    #[getter]
    fn files_directory(&self) -> String {
        self.snapshot.lock().unwrap().files_directory.clone()
    }

    #[getter]
    fn action_status(&self) -> Option<PyActionStatus> {
        self.snapshot
            .lock()
            .unwrap()
            .action_status
            .clone()
            .map(PyActionStatus::from)
    }

    #[getter]
    fn environments_entered(&self) -> Vec<String> {
        self.snapshot.lock().unwrap().environments_entered.clone()
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
        let mut guard = self.session.lock().unwrap();
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
    #[pyo3(signature = (*, environment, identifier=None, os_env_vars=None))]
    fn enter_environment(
        &self,
        environment: &PyEnvironment,
        identifier: Option<String>,
        os_env_vars: Option<HashMap<String, String>>,
    ) -> PyResult<String> {
        let env = environment.inner.clone();
        let env_id = match &identifier {
            Some(id) => id.clone(),
            None => {
                let snap = self.snapshot.lock().unwrap();
                format!("{}:{}", snap.session_id, uuid::Uuid::new_v4().simple())
            }
        };
        let return_id = env_id.clone();

        // Take the session out of the mutex so the background thread owns it
        let mut guard = self.session.lock().unwrap();
        let mut session = guard.take().ok_or_else(|| {
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
            let mut snap = self.snapshot.lock().unwrap();
            snap.state = SessionState::Running;
            snap.action_status = None;
        }

        let session_arc = self.session.clone();
        let snapshot = self.snapshot.clone();

        std::thread::spawn(move || {
            let rt = tokio::runtime::Runtime::new().unwrap();
            let env_ref = os_env_vars.as_ref();
            let _ = rt.block_on(session.enter_environment(&env, None, Some(&env_id), env_ref));
            // Put session back BEFORE updating the snapshot. Python callers
            // watch `state` via the snapshot and dispatch the next action the
            // moment it transitions out of Running. If we updated the snapshot
            // first, a Python caller could call run_task / enter_environment
            // and find the mutex still empty — "An action is already running".
            *session_arc.lock().unwrap() = Some(session);
            let guard = session_arc.lock().unwrap();
            if let Some(s) = guard.as_ref() {
                Self::update_snapshot(s, &snapshot);
            }
        });

        Ok(return_id)
    }

    /// Exit an environment. Non-blocking — spawns the onExit action on a
    /// background thread.
    #[pyo3(signature = (*, identifier, keep_session_running=true, os_env_vars=None))]
    fn exit_environment(
        &self,
        identifier: String,
        keep_session_running: bool,
        os_env_vars: Option<HashMap<String, String>>,
    ) -> PyResult<()> {
        let mut guard = self.session.lock().unwrap();
        let mut session = guard.take().ok_or_else(|| {
            pyo3::exceptions::PyRuntimeError::new_err("An action is already running")
        })?;
        drop(guard);

        {
            let mut snap = self.snapshot.lock().unwrap();
            snap.state = SessionState::Running;
            snap.action_status = None;
        }

        let session_arc = self.session.clone();
        let snapshot = self.snapshot.clone();

        std::thread::spawn(move || {
            let rt = tokio::runtime::Runtime::new().unwrap();
            let env_ref = os_env_vars.as_ref();
            let _ = rt.block_on(session.exit_environment(
                &identifier,
                None,
                keep_session_running,
                env_ref,
            ));
            *session_arc.lock().unwrap() = Some(session);
            let guard = session_arc.lock().unwrap();
            if let Some(s) = guard.as_ref() {
                Self::update_snapshot(s, &snapshot);
            }
        });

        Ok(())
    }

    /// Run a task. Non-blocking — spawns the onRun action on a background thread.
    #[pyo3(signature = (*, step_script, task_parameter_values=None, os_env_vars=None))]
    fn run_task(
        &self,
        step_script: &PyStepScript,
        task_parameter_values: Option<&Bound<'_, PyDict>>,
        os_env_vars: Option<HashMap<String, String>>,
    ) -> PyResult<()> {
        let script = step_script.inner.clone();
        let task_params = match task_parameter_values {
            Some(d) => Some(extract_task_parameter_values(d)?),
            None => None,
        };

        let mut guard = self.session.lock().unwrap();
        let mut session = guard.take().ok_or_else(|| {
            pyo3::exceptions::PyRuntimeError::new_err("An action is already running")
        })?;
        drop(guard);

        {
            let mut snap = self.snapshot.lock().unwrap();
            snap.state = SessionState::Running;
            snap.action_status = None;
        }

        let session_arc = self.session.clone();
        let snapshot = self.snapshot.clone();

        std::thread::spawn(move || {
            let rt = tokio::runtime::Runtime::new().unwrap();
            let env_ref = os_env_vars.as_ref();
            let task_ref = task_params.as_ref();
            let _ = rt.block_on(session.run_task(&script, task_ref, None, env_ref));
            *session_arc.lock().unwrap() = Some(session);
            let guard = session_arc.lock().unwrap();
            if let Some(s) = guard.as_ref() {
                Self::update_snapshot(s, &snapshot);
            }
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
        let mut guard = self.session.lock().unwrap();
        let mut session = guard.take().ok_or_else(|| {
            pyo3::exceptions::PyRuntimeError::new_err("An action is already running")
        })?;
        drop(guard);

        {
            let mut snap = self.snapshot.lock().unwrap();
            snap.state = SessionState::Running;
            snap.action_status = None;
        }

        let session_arc = self.session.clone();
        let snapshot = self.snapshot.clone();

        std::thread::spawn(move || {
            let rt = tokio::runtime::Runtime::new().unwrap();
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
            *session_arc.lock().unwrap() = Some(session);
            let guard = session_arc.lock().unwrap();
            if let Some(s) = guard.as_ref() {
                Self::update_snapshot(s, &snapshot);
            }
        });

        Ok(())
    }

    fn cancel_action(
        &self,
        time_limit: Option<f64>,
        mark_action_failed: Option<bool>,
    ) -> PyResult<()> {
        // cancel_action can be called while an action is running (session is taken).
        // The Rust Session supports this via CancellationToken which is checked by the
        // subprocess runner. But we don't have access to &mut Session here.
        // For now, this is a limitation — cancel requires the session to not be taken.
        let duration = time_limit.map(std::time::Duration::from_secs_f64);
        let mut guard = self.session.lock().unwrap();
        match guard.as_mut() {
            Some(session) => session
                .cancel_action(duration, mark_action_failed.unwrap_or(false))
                .map_err(session_err_to_py),
            None => Err(pyo3::exceptions::PyRuntimeError::new_err(
                "Cannot cancel: session is busy with an action",
            )),
        }
    }

    fn cleanup(&self) {
        let mut guard = self.session.lock().unwrap();
        if let Some(session) = guard.as_mut() {
            session.cleanup();
            Self::update_snapshot(session, &self.snapshot);
        }
    }

    fn __repr__(&self) -> String {
        let snap = self.snapshot.lock().unwrap();
        format!("Session(id={:?}, state={:?})", snap.session_id, snap.state)
    }
}
