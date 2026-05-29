// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyType};
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_sessions::action::ActionState;
use openjd_sessions::action_status::ActionStatus;
use openjd_sessions::runner::ScriptRunnerState;
use openjd_sessions::session::SessionState;

// ── SessionState ──

#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyclass_enum(module = "openjd._openjd_rs")
)]
#[pyclass(
    module = "openjd.sessions._v1",
    name = "SessionState",
    eq,
    eq_int,
    frozen,
    hash,
    from_py_object
)]
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
#[allow(non_camel_case_types, clippy::upper_case_acronyms)]
pub(crate) enum PySessionState {
    READY,
    RUNNING,
    CANCELING,
    READY_ENDING,
    ENDED,
}

impl From<SessionState> for PySessionState {
    fn from(s: SessionState) -> Self {
        match s {
            SessionState::Ready => Self::READY,
            SessionState::Running => Self::RUNNING,
            SessionState::Canceling => Self::CANCELING,
            SessionState::ReadyEnding => Self::READY_ENDING,
            SessionState::Ended => Self::ENDED,
        }
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PySessionState {
    /// Variant name as a string (e.g. `"READY"`).
    #[getter]
    fn name(&self) -> &'static str {
        match self {
            Self::READY => "READY",
            Self::RUNNING => "RUNNING",
            Self::CANCELING => "CANCELING",
            Self::READY_ENDING => "READY_ENDING",
            Self::ENDED => "ENDED",
        }
    }

    fn __repr__(&self) -> String {
        format!("SessionState.{}", self.name())
    }

    /// Pickle support — round-trips through the variant name.
    #[allow(clippy::type_complexity)] // pickle reducer tuple shape is by design
    fn __reduce__<'py>(
        &self,
        py: Python<'py>,
    ) -> PyResult<(Bound<'py, PyAny>, (Bound<'py, PyType>, &'static str))> {
        let helper = py
            .import("openjd._openjd_rs")?
            .getattr("_reconstruct_enum")?;
        Ok((helper, (py.get_type::<Self>(), self.name())))
    }
}

// ── ActionState ──

#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyclass_enum(module = "openjd._openjd_rs")
)]
#[pyclass(
    module = "openjd.sessions._v1",
    name = "ActionState",
    eq,
    eq_int,
    frozen,
    hash,
    from_py_object
)]
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
#[allow(non_camel_case_types, clippy::upper_case_acronyms)]
pub(crate) enum PyActionState {
    RUNNING,
    SUCCESS,
    FAILED,
    CANCELED,
    TIMEOUT,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyActionState {
    fn __str__(&self) -> &'static str {
        match self {
            Self::RUNNING => "running",
            Self::SUCCESS => "success",
            Self::FAILED => "failed",
            Self::CANCELED => "canceled",
            Self::TIMEOUT => "timeout",
        }
    }

    /// Match Python's Enum.name surface so callers using `state.name`
    /// (e.g. f"...as {state.name}") work without changes.
    #[getter]
    fn name(&self) -> &'static str {
        match self {
            Self::RUNNING => "RUNNING",
            Self::SUCCESS => "SUCCESS",
            Self::FAILED => "FAILED",
            Self::CANCELED => "CANCELED",
            Self::TIMEOUT => "TIMEOUT",
        }
    }

    /// Pickle support — round-trips through the variant name.
    #[allow(clippy::type_complexity)] // pickle reducer tuple shape is by design
    fn __reduce__<'py>(
        &self,
        py: Python<'py>,
    ) -> PyResult<(Bound<'py, PyAny>, (Bound<'py, PyType>, &'static str))> {
        let helper = py
            .import("openjd._openjd_rs")?
            .getattr("_reconstruct_enum")?;
        Ok((helper, (py.get_type::<Self>(), self.name())))
    }
}

impl From<ActionState> for PyActionState {
    fn from(s: ActionState) -> Self {
        match s {
            ActionState::Running => Self::RUNNING,
            ActionState::Success => Self::SUCCESS,
            ActionState::Failed => Self::FAILED,
            ActionState::Canceled => Self::CANCELED,
            ActionState::Timeout => Self::TIMEOUT,
        }
    }
}

impl From<PyActionState> for ActionState {
    fn from(s: PyActionState) -> Self {
        match s {
            PyActionState::RUNNING => Self::Running,
            PyActionState::SUCCESS => Self::Success,
            PyActionState::FAILED => Self::Failed,
            PyActionState::CANCELED => Self::Canceled,
            PyActionState::TIMEOUT => Self::Timeout,
        }
    }
}

// ── ScriptRunnerState ──

#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyclass_enum(module = "openjd._openjd_rs")
)]
#[pyclass(
    module = "openjd.sessions._v1",
    name = "ScriptRunnerState",
    eq,
    eq_int,
    frozen,
    hash,
    from_py_object
)]
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
#[allow(non_camel_case_types, clippy::upper_case_acronyms)]
pub(crate) enum PyScriptRunnerState {
    READY,
    RUNNING,
    CANCELING,
    CANCELED,
    TIMEOUT,
    FAILED,
    SUCCESS,
}

impl From<ScriptRunnerState> for PyScriptRunnerState {
    fn from(s: ScriptRunnerState) -> Self {
        match s {
            ScriptRunnerState::Ready => Self::READY,
            ScriptRunnerState::Running => Self::RUNNING,
            ScriptRunnerState::Canceling => Self::CANCELING,
            ScriptRunnerState::Canceled => Self::CANCELED,
            ScriptRunnerState::Timeout => Self::TIMEOUT,
            ScriptRunnerState::Failed => Self::FAILED,
            ScriptRunnerState::Success => Self::SUCCESS,
        }
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyScriptRunnerState {
    /// Variant name as a string (e.g. `"READY"`).
    #[getter]
    fn name(&self) -> &'static str {
        match self {
            Self::READY => "READY",
            Self::RUNNING => "RUNNING",
            Self::CANCELING => "CANCELING",
            Self::CANCELED => "CANCELED",
            Self::TIMEOUT => "TIMEOUT",
            Self::FAILED => "FAILED",
            Self::SUCCESS => "SUCCESS",
        }
    }

    fn __repr__(&self) -> String {
        format!("ScriptRunnerState.{}", self.name())
    }

    /// Pickle support — round-trips through the variant name.
    #[allow(clippy::type_complexity)] // pickle reducer tuple shape is by design
    fn __reduce__<'py>(
        &self,
        py: Python<'py>,
    ) -> PyResult<(Bound<'py, PyAny>, (Bound<'py, PyType>, &'static str))> {
        let helper = py
            .import("openjd._openjd_rs")?
            .getattr("_reconstruct_enum")?;
        Ok((helper, (py.get_type::<Self>(), self.name())))
    }
}

// ── ActionStatus ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.sessions._v1",
    name = "ActionStatus",
    frozen,
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyActionStatus {
    inner: ActionStatus,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyActionStatus {
    #[new]
    #[pyo3(signature = (*, state, progress=None, status_message=None, fail_message=None, exit_code=None))]
    fn new(
        state: PyActionState,
        progress: Option<f64>,
        status_message: Option<String>,
        fail_message: Option<String>,
        exit_code: Option<i32>,
    ) -> Self {
        Self {
            inner: ActionStatus {
                state: state.into(),
                progress,
                status_message,
                fail_message,
                exit_code,
                started_at: None,
                ended_at: None,
            },
        }
    }

    #[getter]
    fn state(&self) -> PyActionState {
        self.inner.state.into()
    }

    #[getter]
    fn progress(&self) -> Option<f64> {
        self.inner.progress
    }

    #[getter]
    fn status_message(&self) -> Option<&str> {
        self.inner.status_message.as_deref()
    }

    #[getter]
    fn fail_message(&self) -> Option<&str> {
        self.inner.fail_message.as_deref()
    }

    #[getter]
    fn exit_code(&self) -> Option<i32> {
        self.inner.exit_code
    }

    /// When the action started, as a tz-aware UTC `datetime`, or `None`
    /// if the action has not started yet.
    #[getter]
    fn started_at<'py>(&self, py: Python<'py>) -> PyResult<Option<Bound<'py, PyAny>>> {
        system_time_to_py_datetime(py, self.inner.started_at)
    }

    /// When the action ended, as a tz-aware UTC `datetime`, or `None`
    /// if the action has not ended yet.
    #[getter]
    fn ended_at<'py>(&self, py: Python<'py>) -> PyResult<Option<Bound<'py, PyAny>>> {
        system_time_to_py_datetime(py, self.inner.ended_at)
    }

    fn __repr__(&self) -> String {
        format!(
            "ActionStatus(state={:?}, exit_code={:?})",
            self.inner.state, self.inner.exit_code
        )
    }

    /// Field-wise structural equality. Two ``ActionStatus`` instances
    /// compare equal when every field matches. Without this, the
    /// pyclass falls back to identity comparison, which breaks
    /// ``mock.assert_called_with`` and dataclass ``__eq__`` for
    /// dataclasses that hold an ``ActionStatus``.
    fn __eq__(&self, other: &Self) -> bool {
        let a = &self.inner;
        let b = &other.inner;
        a.state == b.state
            && a.progress == b.progress
            && a.status_message == b.status_message
            && a.fail_message == b.fail_message
            && a.exit_code == b.exit_code
            && a.started_at == b.started_at
            && a.ended_at == b.ended_at
    }

    fn __ne__(&self, other: &Self) -> bool {
        !self.__eq__(other)
    }

    /// Internal classmethod used by pickle to reconstruct an
    /// `ActionStatus` with its full state including `started_at` and
    /// `ended_at`. Not intended for normal user code; use
    /// `ActionStatus(*, state, ...)` for ordinary construction.
    #[classmethod]
    #[pyo3(signature = (
        *,
        state,
        progress=None,
        status_message=None,
        fail_message=None,
        exit_code=None,
        started_at=None,
        ended_at=None,
    ))]
    // Mirrors the Python kw-only signature; one parameter per
    // ActionStatus field plus the implicit `_cls` and `py` PyO3
    // arguments. Splitting into a builder would obscure the 1:1
    // shape with the Python surface.
    #[allow(clippy::too_many_arguments)]
    fn _from_state<'py>(
        _cls: &Bound<'py, PyType>,
        py: Python<'py>,
        state: PyActionState,
        progress: Option<f64>,
        status_message: Option<String>,
        fail_message: Option<String>,
        exit_code: Option<i32>,
        started_at: Option<Bound<'py, PyAny>>,
        ended_at: Option<Bound<'py, PyAny>>,
    ) -> PyResult<Self> {
        Ok(Self {
            inner: ActionStatus {
                state: state.into(),
                progress,
                status_message,
                fail_message,
                exit_code,
                started_at: py_datetime_to_system_time(py, started_at)?,
                ended_at: py_datetime_to_system_time(py, ended_at)?,
            },
        })
    }

    /// Pickle support — round-trips through `_from_state` which can
    /// carry the otherwise-internal `started_at` and `ended_at`
    /// timestamps.
    fn __reduce__<'py>(
        &self,
        py: Python<'py>,
    ) -> PyResult<(Bound<'py, PyAny>, Py<pyo3::types::PyTuple>)> {
        use pyo3::types::PyTuple;
        let helper = py
            .import("openjd._openjd_rs")?
            .getattr("_reconstruct_kwargs")?;
        let cls = py.get_type::<Self>();
        let from_state = cls.getattr("_from_state")?;
        let kwargs = PyDict::new(py);
        kwargs.set_item("state", PyActionState::from(self.inner.state))?;
        kwargs.set_item("progress", self.inner.progress)?;
        kwargs.set_item("status_message", self.inner.status_message.clone())?;
        kwargs.set_item("fail_message", self.inner.fail_message.clone())?;
        kwargs.set_item("exit_code", self.inner.exit_code)?;
        kwargs.set_item(
            "started_at",
            system_time_to_py_datetime(py, self.inner.started_at)?,
        )?;
        kwargs.set_item(
            "ended_at",
            system_time_to_py_datetime(py, self.inner.ended_at)?,
        )?;
        let args = PyTuple::new(py, [from_state.into_any(), kwargs.into_any()])?;
        Ok((helper, args.into()))
    }
}

/// Convert a Rust `Option<SystemTime>` to a Python tz-aware UTC datetime.
///
/// Uses the Python `datetime` module (rather than pyo3_chrono/PyDateTime)
/// to avoid adding a dependency. The value is a `datetime.datetime` with
/// `tzinfo=datetime.timezone.utc`.
fn system_time_to_py_datetime<'py>(
    py: Python<'py>,
    t: Option<std::time::SystemTime>,
) -> PyResult<Option<Bound<'py, PyAny>>> {
    let Some(t) = t else {
        return Ok(None);
    };
    let secs = t
        .duration_since(std::time::UNIX_EPOCH)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("pre-epoch time: {e}")))?
        .as_secs_f64();
    let datetime_mod = py.import("datetime")?;
    let timezone = datetime_mod.getattr("timezone")?;
    let utc = timezone.getattr("utc")?;
    let dt_cls = datetime_mod.getattr("datetime")?;
    let dt = dt_cls.call_method1("fromtimestamp", (secs, utc))?;
    Ok(Some(dt))
}

/// Convert a Python tz-aware datetime to a Rust `SystemTime`.
///
/// Inverse of [`system_time_to_py_datetime`]. Used by
/// `PyActionStatus._from_state` (the pickle reconstructor) to round-trip
/// the otherwise-internal `started_at` and `ended_at` timestamps.
fn py_datetime_to_system_time<'py>(
    _py: Python<'py>,
    dt: Option<Bound<'py, PyAny>>,
) -> PyResult<Option<std::time::SystemTime>> {
    let Some(dt) = dt else {
        return Ok(None);
    };
    if dt.is_none() {
        return Ok(None);
    }
    let secs: f64 = dt.call_method0("timestamp")?.extract()?;
    if secs.is_nan() || !secs.is_finite() {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "datetime.timestamp() must produce a finite value",
        ));
    }
    if secs >= 0.0 {
        Ok(Some(
            std::time::UNIX_EPOCH + std::time::Duration::from_secs_f64(secs),
        ))
    } else {
        Ok(Some(
            std::time::UNIX_EPOCH - std::time::Duration::from_secs_f64(-secs),
        ))
    }
}

impl From<ActionStatus> for PyActionStatus {
    fn from(s: ActionStatus) -> Self {
        Self { inner: s }
    }
}

// ── ActionResult ──

/// The result of running an action: terminal state, exit code, and a
/// captured snippet of stdout (if any).
///
/// `ActionResult` is normally produced by the binding when an action
/// completes; user code can also construct one directly, e.g. for
/// tests. All three fields are exposed as read-only attributes.
#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.sessions._v1",
    name = "ActionResult",
    frozen,
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyActionResult {
    #[pyo3(get)]
    state: PyActionState,
    #[pyo3(get)]
    exit_code: Option<i32>,
    #[pyo3(get)]
    stdout: String,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyActionResult {
    #[new]
    #[pyo3(signature = (*, state, exit_code=None, stdout=String::new()))]
    fn new(state: PyActionState, exit_code: Option<i32>, stdout: String) -> Self {
        Self {
            state,
            exit_code,
            stdout,
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "ActionResult(state={}, exit_code={:?}, stdout={:?})",
            self.state.name(),
            self.exit_code,
            self.stdout,
        )
    }

    fn __eq__(&self, other: &Self) -> bool {
        self.state == other.state
            && self.exit_code == other.exit_code
            && self.stdout == other.stdout
    }

    /// Pickle support — round-trips through `__init__(*, state,
    /// exit_code=..., stdout=...)`.
    fn __reduce__<'py>(
        &self,
        py: Python<'py>,
    ) -> PyResult<(Bound<'py, PyAny>, Py<pyo3::types::PyTuple>)> {
        use pyo3::types::PyTuple;
        let helper = py
            .import("openjd._openjd_rs")?
            .getattr("_reconstruct_kwargs")?;
        let cls = py.get_type::<Self>();
        let kwargs = PyDict::new(py);
        kwargs.set_item("state", self.state)?;
        kwargs.set_item("exit_code", self.exit_code)?;
        kwargs.set_item("stdout", &self.stdout)?;
        let args = PyTuple::new(py, [cls.into_any(), kwargs.into_any()])?;
        Ok((helper, args.into()))
    }
}
