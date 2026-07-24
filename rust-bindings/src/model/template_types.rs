// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

//! Template-time model pyclasses.
//!
//! Mirror the `openjd_model::template` Rust types 1:1 — the raw,
//! pre-`create_job` form of every model element. These are returned
//! by `JobTemplate.steps`, `JobTemplate.job_environments`,
//! `EnvironmentTemplate.environment`, and similar accessors.
//!
//! Each pyclass exposes the fields of its underlying Rust type as
//! getters; FormatString-typed fields are preserved as
//! `openjd.expr.FormatString` (raw, pre-resolution). Action sugar
//! variants on `StepTemplate` (`bash`/`python`/etc.) are exposed as
//! `Optional[SimpleAction]`.
//!
//! Pickle is supported via the project's `_reconstruct_kwargs`
//! helper, matching the convention used by other PyO3-backed types
//! in the bindings.

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_model::template::{
    Action, AmountRequirement, AttributeRequirement, CancelationMode, EmbeddedFile, Environment,
    EnvironmentActions, EnvironmentScript, HostRequirements, SimpleAction, StepActions,
    StepDependency, StepScript, StepTemplate,
};
use openjd_model::types::{EndOfLine, FileType};

use crate::expr::PyFormatString;

// ── Action ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "TemplateAction",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyAction {
    pub(crate) inner: Action,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyAction {
    #[new]
    #[pyo3(signature = (*, command, args=None, timeout=None, cancelation=None))]
    fn new(
        command: PyFormatString,
        args: Option<Vec<PyFormatString>>,
        timeout: Option<PyFormatString>,
        cancelation: Option<PyCancelationMode>,
    ) -> Self {
        PyAction {
            inner: Action {
                command: command.inner,
                args: args.map(|a| a.into_iter().map(|fs| fs.inner).collect()),
                timeout: timeout.map(|t| t.inner),
                cancelation: cancelation.map(|c| c.inner),
            },
        }
    }

    #[getter]
    fn command(&self) -> PyFormatString {
        PyFormatString {
            inner: self.inner.command.clone(),
        }
    }

    #[getter]
    fn args(&self) -> Option<Vec<PyFormatString>> {
        self.inner.args.as_ref().map(|a| {
            a.iter()
                .map(|fs| PyFormatString { inner: fs.clone() })
                .collect()
        })
    }

    #[getter]
    fn timeout(&self) -> Option<PyFormatString> {
        self.inner
            .timeout
            .as_ref()
            .map(|t| PyFormatString { inner: t.clone() })
    }

    #[getter]
    fn cancelation(&self) -> Option<PyCancelationMode> {
        self.inner
            .cancelation
            .as_ref()
            .map(|c| PyCancelationMode { inner: c.clone() })
    }

    fn __repr__(&self) -> String {
        format!("Action(command={:?})", self.inner.command.raw())
    }

    #[allow(clippy::type_complexity)]
    fn __reduce__<'py>(
        slf: PyRef<'py, Self>,
        py: Python<'py>,
    ) -> PyResult<(Bound<'py, PyAny>, Py<pyo3::types::PyTuple>)> {
        use pyo3::types::PyTuple;
        let helper = py
            .import("openjd._openjd_rs")?
            .getattr("_reconstruct_kwargs")?;
        let kwargs = PyDict::new(py);
        kwargs.set_item("command", slf.command().into_pyobject(py)?)?;
        if let Some(a) = slf.args() {
            kwargs.set_item("args", a)?;
        }
        if let Some(t) = slf.timeout() {
            kwargs.set_item("timeout", t)?;
        }
        if let Some(c) = slf.cancelation() {
            kwargs.set_item("cancelation", c)?;
        }
        let cls = py.get_type::<PyAction>();
        let args = PyTuple::new(py, [cls.into_any(), kwargs.into_any()])?;
        Ok((helper, args.into()))
    }
}

// ── CancelationMode ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "TemplateCancelationMode",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyCancelationMode {
    pub(crate) inner: CancelationMode,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyCancelationMode {
    #[new]
    #[pyo3(signature = (*, mode, notify_period_in_seconds=None))]
    fn new(mode: &str, notify_period_in_seconds: Option<PyFormatString>) -> PyResult<Self> {
        let inner = match mode {
            "TERMINATE" => {
                if notify_period_in_seconds.is_some() {
                    return Err(pyo3::exceptions::PyValueError::new_err(
                        "TERMINATE accepts no notify_period_in_seconds",
                    ));
                }
                CancelationMode::Terminate
            }
            "NOTIFY_THEN_TERMINATE" => CancelationMode::NotifyThenTerminate {
                notify_period_in_seconds: notify_period_in_seconds.map(|fs| fs.inner),
            },
            // A format-string mode (FEATURE_BUNDLE_1) defers the
            // TERMINATE-vs-NOTIFY_THEN_TERMINATE decision to run time.
            // Mirrors the openjd-rs serde impl, which routes any mode
            // containing "{{" to CancelationMode::DeferredMode.
            other if other.contains("{{") => CancelationMode::DeferredMode {
                mode: openjd_expr::FormatString::new(other).map_err(|e| {
                    pyo3::exceptions::PyValueError::new_err(format!(
                        "invalid cancelation mode format string: {e}"
                    ))
                })?,
                notify_period_in_seconds: notify_period_in_seconds.map(|fs| fs.inner),
            },
            other => {
                return Err(pyo3::exceptions::PyValueError::new_err(format!(
                    "unknown cancelation mode: {other}"
                )))
            }
        };
        Ok(PyCancelationMode { inner })
    }

    #[getter]
    fn mode(&self) -> &str {
        match &self.inner {
            CancelationMode::Terminate => "TERMINATE",
            CancelationMode::NotifyThenTerminate { .. } => "NOTIFY_THEN_TERMINATE",
            // The raw format string; the mode decision is deferred to run
            // time. Matches the openjd-rs serialization of DeferredMode.
            CancelationMode::DeferredMode { mode, .. } => mode.raw(),
        }
    }

    #[getter]
    fn notify_period_in_seconds(&self) -> Option<PyFormatString> {
        match &self.inner {
            CancelationMode::Terminate => None,
            CancelationMode::NotifyThenTerminate {
                notify_period_in_seconds,
            }
            | CancelationMode::DeferredMode {
                notify_period_in_seconds,
                ..
            } => notify_period_in_seconds
                .as_ref()
                .map(|fs| PyFormatString { inner: fs.clone() }),
        }
    }

    #[getter]
    #[pyo3(name = "notifyPeriodInSeconds")]
    fn notify_period_in_seconds_camel(&self) -> Option<PyFormatString> {
        self.notify_period_in_seconds()
    }

    fn __repr__(&self) -> String {
        match &self.inner {
            CancelationMode::Terminate => "CancelationMode(mode='TERMINATE')".to_string(),
            CancelationMode::NotifyThenTerminate {
                notify_period_in_seconds,
            } => {
                let raw = notify_period_in_seconds
                    .as_ref()
                    .map(|fs| format!("{:?}", fs.raw()))
                    .unwrap_or_else(|| "None".to_string());
                format!(
                    "CancelationMode(mode='NOTIFY_THEN_TERMINATE', notify_period_in_seconds={raw})"
                )
            }
            CancelationMode::DeferredMode {
                mode,
                notify_period_in_seconds,
            } => {
                let raw = notify_period_in_seconds
                    .as_ref()
                    .map(|fs| format!("{:?}", fs.raw()))
                    .unwrap_or_else(|| "None".to_string());
                format!(
                    "CancelationMode(mode={:?}, notify_period_in_seconds={raw})",
                    mode.raw()
                )
            }
        }
    }

    #[allow(clippy::type_complexity)]
    fn __reduce__<'py>(
        slf: PyRef<'py, Self>,
        py: Python<'py>,
    ) -> PyResult<(Bound<'py, PyAny>, Py<pyo3::types::PyTuple>)> {
        use pyo3::types::PyTuple;
        let helper = py
            .import("openjd._openjd_rs")?
            .getattr("_reconstruct_kwargs")?;
        let kwargs = PyDict::new(py);
        kwargs.set_item("mode", slf.mode())?;
        if let Some(p) = slf.notify_period_in_seconds() {
            kwargs.set_item("notify_period_in_seconds", p)?;
        }
        let cls = py.get_type::<PyCancelationMode>();
        let args = PyTuple::new(py, [cls.into_any(), kwargs.into_any()])?;
        Ok((helper, args.into()))
    }
}

// ── StepActions ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "TemplateStepActions",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyStepActions {
    pub(crate) inner: StepActions,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyStepActions {
    /// Construct a ``StepActions``. Accepts either the snake-case
    /// ``on_run`` kwarg or the camelCase ``onRun`` alias used by v0
    /// (Pydantic) and the JSON template schema. If both are passed,
    /// the snake-case form wins.
    #[new]
    #[pyo3(signature = (*, on_run=None, onRun=None))]
    fn new(
        on_run: Option<PyAction>,
        #[allow(non_snake_case)] onRun: Option<PyAction>,
    ) -> PyResult<Self> {
        let on_run = on_run.or(onRun).ok_or_else(|| {
            pyo3::exceptions::PyTypeError::new_err(
                "StepActions() missing required keyword argument: 'on_run' (or 'onRun')",
            )
        })?;
        Ok(PyStepActions {
            inner: StepActions {
                on_run: on_run.inner,
            },
        })
    }

    #[getter]
    fn on_run(&self) -> PyAction {
        PyAction {
            inner: self.inner.on_run.clone(),
        }
    }

    #[getter]
    #[pyo3(name = "onRun")]
    fn on_run_camel(&self) -> PyAction {
        self.on_run()
    }

    fn __repr__(&self) -> String {
        format!("StepActions(on_run={})", self.on_run().__repr__())
    }

    #[allow(clippy::type_complexity)]
    fn __reduce__<'py>(
        slf: PyRef<'py, Self>,
        py: Python<'py>,
    ) -> PyResult<(Bound<'py, PyAny>, Py<pyo3::types::PyTuple>)> {
        use pyo3::types::PyTuple;
        let helper = py
            .import("openjd._openjd_rs")?
            .getattr("_reconstruct_kwargs")?;
        let kwargs = PyDict::new(py);
        kwargs.set_item("on_run", slf.on_run())?;
        let cls = py.get_type::<PyStepActions>();
        let args = PyTuple::new(py, [cls.into_any(), kwargs.into_any()])?;
        Ok((helper, args.into()))
    }
}

// ── EnvironmentActions ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "TemplateEnvironmentActions",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyEnvironmentActions {
    pub(crate) inner: EnvironmentActions,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyEnvironmentActions {
    /// Construct an ``EnvironmentActions``. Accepts either snake-case
    /// (``on_enter`` / ``on_exit``) or the camelCase aliases
    /// (``onEnter`` / ``onExit``) used by v0 and the JSON template
    /// schema. If both flavours of the same field are passed, the
    /// snake-case form wins.
    #[new]
    #[allow(clippy::too_many_arguments)]
    #[pyo3(signature = (*, on_enter=None, on_exit=None, on_wrap_env_enter=None, on_wrap_task_run=None, on_wrap_env_exit=None, onEnter=None, onExit=None, onWrapEnvEnter=None, onWrapTaskRun=None, onWrapEnvExit=None))]
    fn new(
        on_enter: Option<PyAction>,
        on_exit: Option<PyAction>,
        on_wrap_env_enter: Option<PyAction>,
        on_wrap_task_run: Option<PyAction>,
        on_wrap_env_exit: Option<PyAction>,
        #[allow(non_snake_case)] onEnter: Option<PyAction>,
        #[allow(non_snake_case)] onExit: Option<PyAction>,
        #[allow(non_snake_case)] onWrapEnvEnter: Option<PyAction>,
        #[allow(non_snake_case)] onWrapTaskRun: Option<PyAction>,
        #[allow(non_snake_case)] onWrapEnvExit: Option<PyAction>,
    ) -> Self {
        let on_enter = on_enter.or(onEnter);
        let on_exit = on_exit.or(onExit);
        let on_wrap_env_enter = on_wrap_env_enter.or(onWrapEnvEnter);
        let on_wrap_task_run = on_wrap_task_run.or(onWrapTaskRun);
        let on_wrap_env_exit = on_wrap_env_exit.or(onWrapEnvExit);
        PyEnvironmentActions {
            inner: EnvironmentActions {
                on_wrap_env_enter: on_wrap_env_enter.map(|a| a.inner),
                on_wrap_task_run: on_wrap_task_run.map(|a| a.inner),
                on_wrap_env_exit: on_wrap_env_exit.map(|a| a.inner),
                on_enter: on_enter.map(|a| a.inner),
                on_exit: on_exit.map(|a| a.inner),
            },
        }
    }

    #[getter]
    fn on_enter(&self) -> Option<PyAction> {
        self.inner
            .on_enter
            .as_ref()
            .map(|a| PyAction { inner: a.clone() })
    }

    #[getter]
    #[pyo3(name = "onEnter")]
    fn on_enter_camel(&self) -> Option<PyAction> {
        self.on_enter()
    }

    #[getter]
    fn on_exit(&self) -> Option<PyAction> {
        self.inner
            .on_exit
            .as_ref()
            .map(|a| PyAction { inner: a.clone() })
    }

    #[getter]
    #[pyo3(name = "onExit")]
    fn on_exit_camel(&self) -> Option<PyAction> {
        self.on_exit()
    }

    #[getter]
    fn on_wrap_env_enter(&self) -> Option<PyAction> {
        self.inner
            .on_wrap_env_enter
            .as_ref()
            .map(|a| PyAction { inner: a.clone() })
    }

    #[getter]
    #[pyo3(name = "onWrapEnvEnter")]
    fn on_wrap_env_enter_camel(&self) -> Option<PyAction> {
        self.on_wrap_env_enter()
    }

    #[getter]
    fn on_wrap_task_run(&self) -> Option<PyAction> {
        self.inner
            .on_wrap_task_run
            .as_ref()
            .map(|a| PyAction { inner: a.clone() })
    }

    #[getter]
    #[pyo3(name = "onWrapTaskRun")]
    fn on_wrap_task_run_camel(&self) -> Option<PyAction> {
        self.on_wrap_task_run()
    }

    #[getter]
    fn on_wrap_env_exit(&self) -> Option<PyAction> {
        self.inner
            .on_wrap_env_exit
            .as_ref()
            .map(|a| PyAction { inner: a.clone() })
    }

    #[getter]
    #[pyo3(name = "onWrapEnvExit")]
    fn on_wrap_env_exit_camel(&self) -> Option<PyAction> {
        self.on_wrap_env_exit()
    }

    fn __repr__(&self) -> String {
        format!(
            "EnvironmentActions(on_enter={}, on_exit={})",
            self.on_enter()
                .map(|a| a.__repr__())
                .unwrap_or_else(|| "None".to_string()),
            self.on_exit()
                .map(|a| a.__repr__())
                .unwrap_or_else(|| "None".to_string()),
        )
    }

    #[allow(clippy::type_complexity)]
    fn __reduce__<'py>(
        slf: PyRef<'py, Self>,
        py: Python<'py>,
    ) -> PyResult<(Bound<'py, PyAny>, Py<pyo3::types::PyTuple>)> {
        use pyo3::types::PyTuple;
        let helper = py
            .import("openjd._openjd_rs")?
            .getattr("_reconstruct_kwargs")?;
        let kwargs = PyDict::new(py);
        if let Some(a) = slf.on_enter() {
            kwargs.set_item("on_enter", a)?;
        }
        if let Some(a) = slf.on_exit() {
            kwargs.set_item("on_exit", a)?;
        }
        if let Some(a) = slf.on_wrap_env_enter() {
            kwargs.set_item("on_wrap_env_enter", a)?;
        }
        if let Some(a) = slf.on_wrap_task_run() {
            kwargs.set_item("on_wrap_task_run", a)?;
        }
        if let Some(a) = slf.on_wrap_env_exit() {
            kwargs.set_item("on_wrap_env_exit", a)?;
        }
        let cls = py.get_type::<PyEnvironmentActions>();
        let args = PyTuple::new(py, [cls.into_any(), kwargs.into_any()])?;
        Ok((helper, args.into()))
    }
}

// ── EmbeddedFile ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "TemplateEmbeddedFile",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyEmbeddedFile {
    pub(crate) inner: EmbeddedFile,
}

fn parse_file_type(s: &str) -> PyResult<FileType> {
    match s {
        "TEXT" => Ok(FileType::Text),
        other => Err(pyo3::exceptions::PyValueError::new_err(format!(
            "unknown file type: {other}"
        ))),
    }
}

fn file_type_str(t: FileType) -> &'static str {
    match t {
        FileType::Text => "TEXT",
        _ => "UNKNOWN",
    }
}

fn parse_eol(s: &str) -> PyResult<EndOfLine> {
    match s {
        "LF" => Ok(EndOfLine::Lf),
        "CRLF" => Ok(EndOfLine::Crlf),
        "AUTO" => Ok(EndOfLine::Auto),
        other => Err(pyo3::exceptions::PyValueError::new_err(format!(
            "unknown end-of-line: {other}"
        ))),
    }
}

fn eol_str(e: EndOfLine) -> &'static str {
    match e {
        EndOfLine::Lf => "LF",
        EndOfLine::Crlf => "CRLF",
        EndOfLine::Auto => "AUTO",
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyEmbeddedFile {
    #[new]
    #[pyo3(signature = (*, name, r#type, filename=None, data=None, runnable=None, end_of_line=None))]
    fn new(
        name: String,
        r#type: &str,
        filename: Option<String>,
        data: Option<PyFormatString>,
        runnable: Option<bool>,
        end_of_line: Option<&str>,
    ) -> PyResult<Self> {
        Ok(PyEmbeddedFile {
            inner: EmbeddedFile {
                name,
                file_type: parse_file_type(r#type)?,
                // Plain string per the 2023-09 schema: the field is not
                // @fmtstring, so "{{ }}" sequences are literal text.
                filename,
                data: data.map(|fs| fs.inner),
                runnable,
                end_of_line: end_of_line.map(parse_eol).transpose()?,
            },
        })
    }

    #[getter]
    fn name(&self) -> &str {
        &self.inner.name
    }

    #[getter]
    #[pyo3(name = "type")]
    fn type_(&self) -> &'static str {
        file_type_str(self.inner.file_type)
    }

    #[getter]
    fn filename(&self) -> Option<String> {
        self.inner.filename.clone()
    }

    #[getter]
    fn data(&self) -> Option<PyFormatString> {
        self.inner
            .data
            .as_ref()
            .map(|fs| PyFormatString { inner: fs.clone() })
    }

    #[getter]
    fn runnable(&self) -> Option<bool> {
        self.inner.runnable
    }

    #[getter]
    fn end_of_line(&self) -> Option<&'static str> {
        self.inner.end_of_line.map(eol_str)
    }

    #[getter]
    #[pyo3(name = "endOfLine")]
    fn end_of_line_camel(&self) -> Option<&'static str> {
        self.end_of_line()
    }

    fn __repr__(&self) -> String {
        format!(
            "EmbeddedFile(name={:?}, type={:?})",
            self.inner.name,
            file_type_str(self.inner.file_type)
        )
    }

    #[allow(clippy::type_complexity)]
    fn __reduce__<'py>(
        slf: PyRef<'py, Self>,
        py: Python<'py>,
    ) -> PyResult<(Bound<'py, PyAny>, Py<pyo3::types::PyTuple>)> {
        use pyo3::types::PyTuple;
        let helper = py
            .import("openjd._openjd_rs")?
            .getattr("_reconstruct_kwargs")?;
        let kwargs = PyDict::new(py);
        kwargs.set_item("name", slf.name())?;
        kwargs.set_item("type", slf.type_())?;
        if let Some(fs) = slf.filename() {
            kwargs.set_item("filename", fs)?;
        }
        if let Some(fs) = slf.data() {
            kwargs.set_item("data", fs)?;
        }
        if let Some(r) = slf.runnable() {
            kwargs.set_item("runnable", r)?;
        }
        if let Some(e) = slf.end_of_line() {
            kwargs.set_item("end_of_line", e)?;
        }
        let cls = py.get_type::<PyEmbeddedFile>();
        let args = PyTuple::new(py, [cls.into_any(), kwargs.into_any()])?;
        Ok((helper, args.into()))
    }
}

// ── StepScript ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "TemplateStepScript",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyStepScript {
    pub(crate) inner: StepScript,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyStepScript {
    /// Construct a ``StepScript``. ``embedded_files`` may be passed
    /// as either snake-case or its camelCase alias ``embeddedFiles``;
    /// if both are given the snake-case form wins. A ``let`` alias
    /// is also accepted for ``let_bindings``.
    #[new]
    #[pyo3(signature = (*, actions, let_bindings=None, embedded_files=None, embeddedFiles=None, r#let=None))]
    fn new(
        actions: PyStepActions,
        let_bindings: Option<Vec<String>>,
        embedded_files: Option<Vec<PyEmbeddedFile>>,
        #[allow(non_snake_case)] embeddedFiles: Option<Vec<PyEmbeddedFile>>,
        r#let: Option<Vec<String>>,
    ) -> Self {
        let embedded_files = embedded_files.or(embeddedFiles);
        let let_bindings = let_bindings.or(r#let);
        PyStepScript {
            inner: StepScript {
                let_bindings,
                actions: actions.inner,
                embedded_files: embedded_files.map(|v| v.into_iter().map(|f| f.inner).collect()),
            },
        }
    }

    #[getter]
    fn actions(&self) -> PyStepActions {
        PyStepActions {
            inner: self.inner.actions.clone(),
        }
    }

    #[getter]
    fn let_bindings(&self) -> Option<Vec<String>> {
        self.inner.let_bindings.clone()
    }

    #[getter]
    #[pyo3(name = "let")]
    fn let_alias(&self) -> Option<Vec<String>> {
        self.let_bindings()
    }

    #[getter]
    fn embedded_files(&self) -> Option<Vec<PyEmbeddedFile>> {
        self.inner.embedded_files.as_ref().map(|v| {
            v.iter()
                .map(|f| PyEmbeddedFile { inner: f.clone() })
                .collect()
        })
    }

    #[getter]
    #[pyo3(name = "embeddedFiles")]
    fn embedded_files_camel(&self) -> Option<Vec<PyEmbeddedFile>> {
        self.embedded_files()
    }

    fn __repr__(&self) -> String {
        "StepScript(...)".to_string()
    }

    #[allow(clippy::type_complexity)]
    fn __reduce__<'py>(
        slf: PyRef<'py, Self>,
        py: Python<'py>,
    ) -> PyResult<(Bound<'py, PyAny>, Py<pyo3::types::PyTuple>)> {
        use pyo3::types::PyTuple;
        let helper = py
            .import("openjd._openjd_rs")?
            .getattr("_reconstruct_kwargs")?;
        let kwargs = PyDict::new(py);
        kwargs.set_item("actions", slf.actions())?;
        if let Some(b) = slf.let_bindings() {
            kwargs.set_item("let_bindings", b)?;
        }
        if let Some(f) = slf.embedded_files() {
            kwargs.set_item("embedded_files", f)?;
        }
        let cls = py.get_type::<PyStepScript>();
        let args = PyTuple::new(py, [cls.into_any(), kwargs.into_any()])?;
        Ok((helper, args.into()))
    }
}

// ── EnvironmentScript ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "TemplateEnvironmentScript",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyEnvironmentScript {
    pub(crate) inner: EnvironmentScript,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyEnvironmentScript {
    /// Construct an ``EnvironmentScript``. ``embedded_files`` may be
    /// passed as either snake-case or its camelCase alias
    /// ``embeddedFiles``; if both are given the snake-case form
    /// wins. A ``let`` alias is also accepted for ``let_bindings``.
    #[new]
    #[pyo3(signature = (*, actions, let_bindings=None, embedded_files=None, embeddedFiles=None, r#let=None))]
    fn new(
        actions: PyEnvironmentActions,
        let_bindings: Option<Vec<String>>,
        embedded_files: Option<Vec<PyEmbeddedFile>>,
        #[allow(non_snake_case)] embeddedFiles: Option<Vec<PyEmbeddedFile>>,
        r#let: Option<Vec<String>>,
    ) -> Self {
        let embedded_files = embedded_files.or(embeddedFiles);
        let let_bindings = let_bindings.or(r#let);
        PyEnvironmentScript {
            inner: EnvironmentScript {
                let_bindings,
                actions: actions.inner,
                embedded_files: embedded_files.map(|v| v.into_iter().map(|f| f.inner).collect()),
            },
        }
    }

    #[getter]
    fn actions(&self) -> PyEnvironmentActions {
        PyEnvironmentActions {
            inner: self.inner.actions.clone(),
        }
    }

    #[getter]
    fn let_bindings(&self) -> Option<Vec<String>> {
        self.inner.let_bindings.clone()
    }

    #[getter]
    #[pyo3(name = "let")]
    fn let_alias(&self) -> Option<Vec<String>> {
        self.let_bindings()
    }

    #[getter]
    fn embedded_files(&self) -> Option<Vec<PyEmbeddedFile>> {
        self.inner.embedded_files.as_ref().map(|v| {
            v.iter()
                .map(|f| PyEmbeddedFile { inner: f.clone() })
                .collect()
        })
    }

    #[getter]
    #[pyo3(name = "embeddedFiles")]
    fn embedded_files_camel(&self) -> Option<Vec<PyEmbeddedFile>> {
        self.embedded_files()
    }

    fn __repr__(&self) -> String {
        "EnvironmentScript(...)".to_string()
    }

    #[allow(clippy::type_complexity)]
    fn __reduce__<'py>(
        slf: PyRef<'py, Self>,
        py: Python<'py>,
    ) -> PyResult<(Bound<'py, PyAny>, Py<pyo3::types::PyTuple>)> {
        use pyo3::types::PyTuple;
        let helper = py
            .import("openjd._openjd_rs")?
            .getattr("_reconstruct_kwargs")?;
        let kwargs = PyDict::new(py);
        kwargs.set_item("actions", slf.actions())?;
        if let Some(b) = slf.let_bindings() {
            kwargs.set_item("let_bindings", b)?;
        }
        if let Some(f) = slf.embedded_files() {
            kwargs.set_item("embedded_files", f)?;
        }
        let cls = py.get_type::<PyEnvironmentScript>();
        let args = PyTuple::new(py, [cls.into_any(), kwargs.into_any()])?;
        Ok((helper, args.into()))
    }
}

// ── Environment ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "TemplateEnvironment",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyEnvironment {
    pub(crate) inner: Environment,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyEnvironment {
    #[new]
    #[pyo3(signature = (*, name, description=None, script=None, variables=None))]
    fn new(
        py: Python<'_>,
        name: String,
        description: Option<String>,
        script: Option<PyEnvironmentScript>,
        variables: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Self> {
        let _ = py;
        let mut vars: Option<std::collections::HashMap<String, openjd_expr::FormatString>> = None;
        if let Some(d) = variables {
            let mut map = std::collections::HashMap::new();
            for (k, v) in d.iter() {
                let key: String = k.extract()?;
                let val: PyFormatString = v.extract()?;
                map.insert(key, val.inner);
            }
            vars = Some(map);
        }
        Ok(PyEnvironment {
            inner: Environment {
                name,
                description: description.map(openjd_model::template::Description),
                script: script.map(|s| s.inner),
                variables: vars,
            },
        })
    }

    #[getter]
    fn name(&self) -> &str {
        &self.inner.name
    }

    #[getter]
    fn description(&self) -> Option<&str> {
        self.inner.description.as_ref().map(|d| d.0.as_str())
    }

    #[getter]
    fn script(&self) -> Option<PyEnvironmentScript> {
        self.inner
            .script
            .as_ref()
            .map(|s| PyEnvironmentScript { inner: s.clone() })
    }

    #[getter]
    fn variables<'py>(&self, py: Python<'py>) -> PyResult<Option<Bound<'py, PyDict>>> {
        match &self.inner.variables {
            None => Ok(None),
            Some(map) => {
                let d = PyDict::new(py);
                for (k, v) in map {
                    d.set_item(k, PyFormatString { inner: v.clone() })?;
                }
                Ok(Some(d))
            }
        }
    }

    fn __repr__(&self) -> String {
        format!("Environment(name={:?})", self.inner.name)
    }

    #[allow(clippy::type_complexity)]
    fn __reduce__<'py>(
        slf: PyRef<'py, Self>,
        py: Python<'py>,
    ) -> PyResult<(Bound<'py, PyAny>, Py<pyo3::types::PyTuple>)> {
        use pyo3::types::PyTuple;
        let helper = py
            .import("openjd._openjd_rs")?
            .getattr("_reconstruct_kwargs")?;
        let kwargs = PyDict::new(py);
        kwargs.set_item("name", slf.name())?;
        if let Some(d) = slf.description() {
            kwargs.set_item("description", d)?;
        }
        if let Some(s) = slf.script() {
            kwargs.set_item("script", s)?;
        }
        if let Some(v) = slf.variables(py)? {
            kwargs.set_item("variables", v)?;
        }
        let cls = py.get_type::<PyEnvironment>();
        let args = PyTuple::new(py, [cls.into_any(), kwargs.into_any()])?;
        Ok((helper, args.into()))
    }
}

// ── HostRequirements / AmountRequirement / AttributeRequirement ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "TemplateAmountRequirement",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyAmountRequirement {
    pub(crate) inner: AmountRequirement,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyAmountRequirement {
    #[new]
    #[pyo3(signature = (*, name, min=None, max=None))]
    fn new(name: String, min: Option<PyFormatString>, max: Option<PyFormatString>) -> Self {
        PyAmountRequirement {
            inner: AmountRequirement {
                name,
                min: min.map(|fs| fs.inner),
                max: max.map(|fs| fs.inner),
            },
        }
    }

    #[getter]
    fn name(&self) -> &str {
        &self.inner.name
    }

    #[getter]
    fn min(&self) -> Option<PyFormatString> {
        self.inner
            .min
            .as_ref()
            .map(|fs| PyFormatString { inner: fs.clone() })
    }

    #[getter]
    fn max(&self) -> Option<PyFormatString> {
        self.inner
            .max
            .as_ref()
            .map(|fs| PyFormatString { inner: fs.clone() })
    }

    fn __repr__(&self) -> String {
        format!("AmountRequirement(name={:?})", self.inner.name)
    }

    #[allow(clippy::type_complexity)]
    fn __reduce__<'py>(
        slf: PyRef<'py, Self>,
        py: Python<'py>,
    ) -> PyResult<(Bound<'py, PyAny>, Py<pyo3::types::PyTuple>)> {
        use pyo3::types::PyTuple;
        let helper = py
            .import("openjd._openjd_rs")?
            .getattr("_reconstruct_kwargs")?;
        let kwargs = PyDict::new(py);
        kwargs.set_item("name", slf.name())?;
        if let Some(fs) = slf.min() {
            kwargs.set_item("min", fs)?;
        }
        if let Some(fs) = slf.max() {
            kwargs.set_item("max", fs)?;
        }
        let cls = py.get_type::<PyAmountRequirement>();
        let args = PyTuple::new(py, [cls.into_any(), kwargs.into_any()])?;
        Ok((helper, args.into()))
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "TemplateAttributeRequirement",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyAttributeRequirement {
    pub(crate) inner: AttributeRequirement,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyAttributeRequirement {
    #[new]
    #[pyo3(signature = (*, name, any_of=None, all_of=None))]
    fn new(
        name: String,
        any_of: Option<Vec<PyFormatString>>,
        all_of: Option<Vec<PyFormatString>>,
    ) -> Self {
        PyAttributeRequirement {
            inner: AttributeRequirement {
                name,
                any_of: any_of.map(|v| v.into_iter().map(|fs| fs.inner).collect()),
                all_of: all_of.map(|v| v.into_iter().map(|fs| fs.inner).collect()),
            },
        }
    }

    #[getter]
    fn name(&self) -> &str {
        &self.inner.name
    }

    #[getter]
    fn any_of(&self) -> Option<Vec<PyFormatString>> {
        self.inner.any_of.as_ref().map(|v| {
            v.iter()
                .map(|fs| PyFormatString { inner: fs.clone() })
                .collect()
        })
    }

    #[getter]
    #[pyo3(name = "anyOf")]
    fn any_of_camel(&self) -> Option<Vec<PyFormatString>> {
        self.any_of()
    }

    #[getter]
    fn all_of(&self) -> Option<Vec<PyFormatString>> {
        self.inner.all_of.as_ref().map(|v| {
            v.iter()
                .map(|fs| PyFormatString { inner: fs.clone() })
                .collect()
        })
    }

    #[getter]
    #[pyo3(name = "allOf")]
    fn all_of_camel(&self) -> Option<Vec<PyFormatString>> {
        self.all_of()
    }

    fn __repr__(&self) -> String {
        format!("AttributeRequirement(name={:?})", self.inner.name)
    }

    #[allow(clippy::type_complexity)]
    fn __reduce__<'py>(
        slf: PyRef<'py, Self>,
        py: Python<'py>,
    ) -> PyResult<(Bound<'py, PyAny>, Py<pyo3::types::PyTuple>)> {
        use pyo3::types::PyTuple;
        let helper = py
            .import("openjd._openjd_rs")?
            .getattr("_reconstruct_kwargs")?;
        let kwargs = PyDict::new(py);
        kwargs.set_item("name", slf.name())?;
        if let Some(v) = slf.any_of() {
            kwargs.set_item("any_of", v)?;
        }
        if let Some(v) = slf.all_of() {
            kwargs.set_item("all_of", v)?;
        }
        let cls = py.get_type::<PyAttributeRequirement>();
        let args = PyTuple::new(py, [cls.into_any(), kwargs.into_any()])?;
        Ok((helper, args.into()))
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "TemplateHostRequirements",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyHostRequirements {
    pub(crate) inner: HostRequirements,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyHostRequirements {
    #[new]
    #[pyo3(signature = (*, amounts=None, attributes=None))]
    fn new(
        amounts: Option<Vec<PyAmountRequirement>>,
        attributes: Option<Vec<PyAttributeRequirement>>,
    ) -> Self {
        PyHostRequirements {
            inner: HostRequirements {
                amounts: amounts.map(|v| v.into_iter().map(|a| a.inner).collect()),
                attributes: attributes.map(|v| v.into_iter().map(|a| a.inner).collect()),
            },
        }
    }

    #[getter]
    fn amounts(&self) -> Option<Vec<PyAmountRequirement>> {
        self.inner.amounts.as_ref().map(|v| {
            v.iter()
                .map(|a| PyAmountRequirement { inner: a.clone() })
                .collect()
        })
    }

    #[getter]
    fn attributes(&self) -> Option<Vec<PyAttributeRequirement>> {
        self.inner.attributes.as_ref().map(|v| {
            v.iter()
                .map(|a| PyAttributeRequirement { inner: a.clone() })
                .collect()
        })
    }

    fn __repr__(&self) -> String {
        "HostRequirements(...)".to_string()
    }

    #[allow(clippy::type_complexity)]
    fn __reduce__<'py>(
        slf: PyRef<'py, Self>,
        py: Python<'py>,
    ) -> PyResult<(Bound<'py, PyAny>, Py<pyo3::types::PyTuple>)> {
        use pyo3::types::PyTuple;
        let helper = py
            .import("openjd._openjd_rs")?
            .getattr("_reconstruct_kwargs")?;
        let kwargs = PyDict::new(py);
        if let Some(v) = slf.amounts() {
            kwargs.set_item("amounts", v)?;
        }
        if let Some(v) = slf.attributes() {
            kwargs.set_item("attributes", v)?;
        }
        let cls = py.get_type::<PyHostRequirements>();
        let args = PyTuple::new(py, [cls.into_any(), kwargs.into_any()])?;
        Ok((helper, args.into()))
    }
}

// ── StepDependency ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "TemplateStepDependency",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyStepDependency {
    pub(crate) inner: StepDependency,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyStepDependency {
    #[new]
    #[pyo3(signature = (*, depends_on))]
    fn new(depends_on: String) -> Self {
        PyStepDependency {
            inner: StepDependency { depends_on },
        }
    }

    #[getter]
    fn depends_on(&self) -> &str {
        &self.inner.depends_on
    }

    #[getter]
    #[pyo3(name = "dependsOn")]
    fn depends_on_camel(&self) -> &str {
        self.depends_on()
    }

    fn __repr__(&self) -> String {
        format!("StepDependency(dependsOn={:?})", self.inner.depends_on)
    }

    #[allow(clippy::type_complexity)]
    fn __reduce__<'py>(
        slf: PyRef<'py, Self>,
        py: Python<'py>,
    ) -> PyResult<(Bound<'py, PyAny>, Py<pyo3::types::PyTuple>)> {
        use pyo3::types::PyTuple;
        let helper = py
            .import("openjd._openjd_rs")?
            .getattr("_reconstruct_kwargs")?;
        let kwargs = PyDict::new(py);
        kwargs.set_item("depends_on", slf.depends_on())?;
        let cls = py.get_type::<PyStepDependency>();
        let args = PyTuple::new(py, [cls.into_any(), kwargs.into_any()])?;
        Ok((helper, args.into()))
    }
}

// ── SimpleAction ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "SimpleAction",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PySimpleAction {
    pub(crate) inner: SimpleAction,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PySimpleAction {
    #[new]
    #[pyo3(signature = (*, script, let_bindings=None, args=None, timeout=None, cancelation=None))]
    fn new(
        script: String,
        let_bindings: Option<Vec<String>>,
        args: Option<Vec<PyFormatString>>,
        timeout: Option<PyFormatString>,
        cancelation: Option<PyCancelationMode>,
    ) -> Self {
        PySimpleAction {
            inner: SimpleAction {
                let_bindings,
                script,
                args: args.map(|a| a.into_iter().map(|fs| fs.inner).collect()),
                timeout: timeout.map(|t| t.inner),
                cancelation: cancelation.map(|c| c.inner),
            },
        }
    }

    #[getter]
    fn script(&self) -> &str {
        &self.inner.script
    }

    #[getter]
    fn let_bindings(&self) -> Option<Vec<String>> {
        self.inner.let_bindings.clone()
    }

    #[getter]
    #[pyo3(name = "let")]
    fn let_alias(&self) -> Option<Vec<String>> {
        self.let_bindings()
    }

    #[getter]
    fn args(&self) -> Option<Vec<PyFormatString>> {
        self.inner.args.as_ref().map(|a| {
            a.iter()
                .map(|fs| PyFormatString { inner: fs.clone() })
                .collect()
        })
    }

    #[getter]
    fn timeout(&self) -> Option<PyFormatString> {
        self.inner
            .timeout
            .as_ref()
            .map(|fs| PyFormatString { inner: fs.clone() })
    }

    #[getter]
    fn cancelation(&self) -> Option<PyCancelationMode> {
        self.inner
            .cancelation
            .as_ref()
            .map(|c| PyCancelationMode { inner: c.clone() })
    }

    fn __repr__(&self) -> String {
        "SimpleAction(...)".to_string()
    }

    #[allow(clippy::type_complexity)]
    fn __reduce__<'py>(
        slf: PyRef<'py, Self>,
        py: Python<'py>,
    ) -> PyResult<(Bound<'py, PyAny>, Py<pyo3::types::PyTuple>)> {
        use pyo3::types::PyTuple;
        let helper = py
            .import("openjd._openjd_rs")?
            .getattr("_reconstruct_kwargs")?;
        let kwargs = PyDict::new(py);
        kwargs.set_item("script", slf.script())?;
        if let Some(b) = slf.let_bindings() {
            kwargs.set_item("let_bindings", b)?;
        }
        if let Some(a) = slf.args() {
            kwargs.set_item("args", a)?;
        }
        if let Some(t) = slf.timeout() {
            kwargs.set_item("timeout", t)?;
        }
        if let Some(c) = slf.cancelation() {
            kwargs.set_item("cancelation", c)?;
        }
        let cls = py.get_type::<PySimpleAction>();
        let args = PyTuple::new(py, [cls.into_any(), kwargs.into_any()])?;
        Ok((helper, args.into()))
    }
}

// ── StepTemplate ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "StepTemplate",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyStepTemplate {
    pub(crate) inner: StepTemplate,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyStepTemplate {
    #[getter]
    fn name(&self) -> &str {
        &self.inner.name
    }

    #[getter]
    fn description(&self) -> Option<&str> {
        self.inner.description.as_ref().map(|d| d.0.as_str())
    }

    #[getter]
    fn let_bindings(&self) -> Option<Vec<String>> {
        self.inner.let_bindings.clone()
    }

    #[getter]
    #[pyo3(name = "let")]
    fn let_alias(&self) -> Option<Vec<String>> {
        self.let_bindings()
    }

    #[getter]
    fn dependencies(&self) -> Option<Vec<PyStepDependency>> {
        self.inner.dependencies.as_ref().map(|v| {
            v.iter()
                .map(|d| PyStepDependency { inner: d.clone() })
                .collect()
        })
    }

    #[getter]
    fn step_environments(&self) -> Option<Vec<PyEnvironment>> {
        self.inner.step_environments.as_ref().map(|v| {
            v.iter()
                .map(|e| PyEnvironment { inner: e.clone() })
                .collect()
        })
    }

    #[getter]
    #[pyo3(name = "stepEnvironments")]
    fn step_environments_camel(&self) -> Option<Vec<PyEnvironment>> {
        self.step_environments()
    }

    #[getter]
    fn host_requirements(&self) -> Option<PyHostRequirements> {
        self.inner
            .host_requirements
            .as_ref()
            .map(|h| PyHostRequirements { inner: h.clone() })
    }

    #[getter]
    #[pyo3(name = "hostRequirements")]
    fn host_requirements_camel(&self) -> Option<PyHostRequirements> {
        self.host_requirements()
    }

    /// The step's parameter-space definition, or ``None`` if the
    /// step has no `parameterSpace:` field.
    ///
    /// Returns a typed `StepParameterSpaceDefinition` whose
    /// `task_parameter_definitions` is a list of typed pyclasses
    /// dispatching on the `TaskParameterDefinition` enum
    /// (`IntTaskParameterDefinition`, `FloatTaskParameterDefinition`,
    /// `StringTaskParameterDefinition`,
    /// `PathTaskParameterDefinition`,
    /// `ChunkIntTaskParameterDefinition`).
    ///
    /// For the resolved (post-`create_job`) form with format strings
    /// evaluated, see `Step.parameterSpace` on the job-time `Step`.
    #[getter]
    fn parameter_space(
        &self,
    ) -> Option<super::step_param_space_def::PyStepParameterSpaceDefinition> {
        self.inner.parameter_space.as_ref().map(|ps| {
            super::step_param_space_def::PyStepParameterSpaceDefinition { inner: ps.clone() }
        })
    }

    #[getter]
    #[pyo3(name = "parameterSpace")]
    fn parameter_space_camel(
        &self,
    ) -> Option<super::step_param_space_def::PyStepParameterSpaceDefinition> {
        self.parameter_space()
    }

    #[getter]
    fn script(&self) -> Option<PyStepScript> {
        self.inner
            .script
            .as_ref()
            .map(|s| PyStepScript { inner: s.clone() })
    }

    #[getter]
    fn bash(&self) -> Option<PySimpleAction> {
        self.inner
            .bash
            .as_ref()
            .map(|s| PySimpleAction { inner: s.clone() })
    }

    #[getter]
    fn python(&self) -> Option<PySimpleAction> {
        self.inner
            .python
            .as_ref()
            .map(|s| PySimpleAction { inner: s.clone() })
    }

    #[getter]
    fn cmd(&self) -> Option<PySimpleAction> {
        self.inner
            .cmd
            .as_ref()
            .map(|s| PySimpleAction { inner: s.clone() })
    }

    #[getter]
    fn powershell(&self) -> Option<PySimpleAction> {
        self.inner
            .powershell
            .as_ref()
            .map(|s| PySimpleAction { inner: s.clone() })
    }

    #[getter]
    fn node(&self) -> Option<PySimpleAction> {
        self.inner
            .node
            .as_ref()
            .map(|s| PySimpleAction { inner: s.clone() })
    }

    fn __repr__(&self) -> String {
        format!("StepTemplate(name={:?})", self.inner.name)
    }
}

/// Convert a `serde_json::Value` to a Python object. (Reserved for
/// future use when a typed `StepParameterSpaceDefinition` pyclass is
/// added; currently unused.)
#[allow(dead_code)]
fn json_to_py<'py>(py: Python<'py>, value: &serde_json::Value) -> PyResult<Bound<'py, PyAny>> {
    use pyo3::IntoPyObject;
    use serde_json::Value;
    Ok(match value {
        Value::Null => py.None().bind(py).clone(),
        Value::Bool(b) => b.into_pyobject(py)?.to_owned().into_any(),
        Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                i.into_pyobject(py)?.into_any()
            } else if let Some(u) = n.as_u64() {
                u.into_pyobject(py)?.into_any()
            } else if let Some(f) = n.as_f64() {
                f.into_pyobject(py)?.into_any()
            } else {
                py.None().bind(py).clone()
            }
        }
        Value::String(s) => s.into_pyobject(py)?.into_any(),
        Value::Array(arr) => {
            let py_list = PyList::empty(py);
            for v in arr {
                py_list.append(json_to_py(py, v)?)?;
            }
            py_list.into_any()
        }
        Value::Object(obj) => {
            let d = PyDict::new(py);
            for (k, v) in obj {
                d.set_item(k, json_to_py(py, v)?)?;
            }
            d.into_any()
        }
    })
}
