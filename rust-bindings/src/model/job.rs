// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;

use pyo3::prelude::*;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_model::job;

use crate::expr::expr_value::PyExprValue;
use crate::expr::range_expr::PyRangeExpr;
use crate::model::types::PyJobParameterType;

// ── PyJob ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.model._v1.job", name = "Job", from_py_object)]
#[derive(Clone)]
pub(crate) struct PyJob {
    pub(crate) inner: job::Job,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyJob {
    #[getter]
    fn name(&self) -> &str {
        &self.inner.name
    }

    #[getter]
    fn description(&self) -> Option<&str> {
        self.inner.description.as_deref()
    }

    #[getter]
    fn revision(&self) -> &'static str {
        "2023-09"
    }

    #[getter]
    fn extensions(&self) -> Option<Vec<String>> {
        self.inner
            .extensions
            .as_ref()
            .map(|exts| exts.iter().map(|e| e.as_str().to_string()).collect())
    }

    #[getter]
    fn steps(&self) -> Vec<PyStep> {
        self.inner
            .steps
            .iter()
            .map(|s| PyStep { inner: s.clone() })
            .collect()
    }

    #[getter]
    fn parameters(&self) -> HashMap<String, PyJobParameter> {
        self.inner
            .parameters
            .iter()
            .map(|(k, v)| (k.clone(), PyJobParameter { inner: v.clone() }))
            .collect()
    }

    #[getter]
    fn job_environments(&self) -> Option<Vec<PyEnvironment>> {
        self.inner.job_environments.as_ref().map(|envs| {
            envs.iter()
                .map(|e| PyEnvironment { inner: e.clone() })
                .collect()
        })
    }

    #[getter]
    #[pyo3(name = "jobEnvironments")]
    fn job_environments_camel(&self) -> Option<Vec<PyEnvironment>> {
        self.job_environments()
    }

    fn __repr__(&self) -> String {
        format!("Job(name={:?})", self.inner.name)
    }
}

// ── PyStep ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.model._v1.job", name = "Step", from_py_object)]
#[derive(Clone)]
pub(crate) struct PyStep {
    pub(crate) inner: job::Step,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyStep {
    #[getter]
    fn name(&self) -> &str {
        &self.inner.name
    }

    #[getter]
    fn description(&self) -> Option<&str> {
        self.inner.description.as_deref()
    }

    #[getter]
    fn script(&self) -> PyStepScript {
        PyStepScript {
            inner: self.inner.script.clone(),
        }
    }

    #[getter]
    fn step_environments(&self) -> Option<Vec<PyEnvironment>> {
        self.inner.step_environments.as_ref().map(|envs| {
            envs.iter()
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
    fn parameter_space(&self) -> Option<PyStepParameterSpace> {
        self.inner
            .parameter_space
            .as_ref()
            .map(|ps| PyStepParameterSpace { inner: ps.clone() })
    }

    #[getter]
    #[pyo3(name = "resolvedBindings")]
    fn resolved_bindings(&self) -> Option<Vec<String>> {
        self.inner.script.let_bindings.clone()
    }

    #[getter]
    fn resolved_symtab(&self) -> Option<crate::expr::PySerializedSymbolTable> {
        self.inner
            .resolved_symtab
            .as_ref()
            .map(|st| crate::expr::PySerializedSymbolTable { inner: st.clone() })
    }

    #[getter]
    #[pyo3(name = "parameterSpace")]
    fn parameter_space_camel(&self) -> Option<PyStepParameterSpace> {
        self.parameter_space()
    }

    #[getter]
    fn dependencies(&self) -> Option<Vec<PyStepDependency>> {
        self.inner.dependencies.as_ref().map(|deps| {
            deps.iter()
                .map(|d| PyStepDependency { inner: d.clone() })
                .collect()
        })
    }

    /// Job-time host requirements for this step. ``None`` if the
    /// template did not declare any. Returns the resolved
    /// :class:`HostRequirements` from
    /// :mod:`openjd.model._v1.job` (distinct from the
    /// template-time :class:`TemplateHostRequirements`).
    #[getter]
    fn host_requirements(&self) -> Option<PyHostRequirements> {
        self.inner
            .host_requirements
            .as_ref()
            .map(|hr| PyHostRequirements { inner: hr.clone() })
    }

    /// camelCase alias for ``host_requirements``.
    #[getter]
    #[pyo3(name = "hostRequirements")]
    fn host_requirements_camel(&self) -> Option<PyHostRequirements> {
        self.host_requirements()
    }

    fn __repr__(&self) -> String {
        format!("Step(name={:?})", self.inner.name)
    }

    fn __eq__(&self, other: &PyStep) -> bool {
        self.inner.name == other.inner.name
    }

    fn __hash__(&self) -> u64 {
        use std::hash::{Hash, Hasher};
        let mut h = std::collections::hash_map::DefaultHasher::new();
        self.inner.name.hash(&mut h);
        h.finish()
    }
}

// ── PyStepScript ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.model._v1.job", name = "StepScript", from_py_object)]
#[derive(Clone)]
pub(crate) struct PyStepScript {
    pub(crate) inner: job::StepScript,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyStepScript {
    /// Construct a ``StepScript``. ``embedded_files`` may be passed
    /// as either snake-case or the camelCase alias ``embeddedFiles``;
    /// if both are given the snake-case form wins. The let-bindings
    /// list may be passed as ``let_bindings`` or its alias ``let``.
    #[new]
    #[pyo3(signature = (*, actions, embedded_files=None, embeddedFiles=None, let_bindings=None, r#let=None))]
    fn new(
        actions: PyStepActions,
        embedded_files: Option<Vec<PyEmbeddedFile>>,
        #[allow(non_snake_case)] embeddedFiles: Option<Vec<PyEmbeddedFile>>,
        let_bindings: Option<Vec<String>>,
        r#let: Option<Vec<String>>,
    ) -> Self {
        let embedded_files = embedded_files.or(embeddedFiles);
        let let_bindings = let_bindings.or(r#let);
        PyStepScript {
            inner: job::StepScript {
                let_bindings,
                actions: actions.inner,
                embedded_files: embedded_files.map(|v| v.into_iter().map(|e| e.inner).collect()),
            },
        }
    }

    #[getter]
    fn revision(&self) -> &'static str {
        "2023-09"
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

    /// camelCase alias for ``let_bindings``. Mirrors the JSON
    /// template schema's ``let`` keyword.
    #[getter]
    #[pyo3(name = "let")]
    fn let_alias(&self) -> Option<Vec<String>> {
        self.let_bindings()
    }

    #[getter]
    fn embedded_files(&self) -> Option<Vec<PyEmbeddedFile>> {
        self.inner.embedded_files.as_ref().map(|files| {
            files
                .iter()
                .map(|f| PyEmbeddedFile { inner: f.clone() })
                .collect()
        })
    }

    #[getter]
    #[pyo3(name = "embeddedFiles")]
    fn embedded_files_camel(&self) -> Option<Vec<PyEmbeddedFile>> {
        self.embedded_files()
    }
}

// ── PyStepActions ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.model._v1.job", name = "StepActions", from_py_object)]
#[derive(Clone)]
pub(crate) struct PyStepActions {
    inner: job::StepActions,
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
            inner: job::StepActions {
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
}

// ── PyAction ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.model._v1.job", name = "Action", from_py_object)]
#[derive(Clone)]
pub(crate) struct PyAction {
    inner: job::Action,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyAction {
    #[new]
    #[pyo3(signature = (*, command, args=None, timeout=None, cancelation=None))]
    fn new(
        command: crate::expr::PyFormatString,
        args: Option<Vec<crate::expr::PyFormatString>>,
        timeout: Option<crate::expr::PyFormatString>,
        cancelation: Option<PyCancelationMode>,
    ) -> Self {
        PyAction {
            inner: job::Action {
                command: command.inner,
                args: args.map(|a| a.into_iter().map(|fs| fs.inner).collect()),
                timeout: timeout.map(|t| t.inner),
                cancelation: cancelation.map(|c| c.inner),
            },
        }
    }

    #[getter]
    fn command(&self) -> crate::expr::PyFormatString {
        crate::expr::PyFormatString {
            inner: self.inner.command.clone(),
        }
    }

    #[getter]
    fn args(&self) -> Option<Vec<crate::expr::PyFormatString>> {
        self.inner.args.as_ref().map(|a| {
            a.iter()
                .map(|fs| crate::expr::PyFormatString { inner: fs.clone() })
                .collect()
        })
    }

    #[getter]
    fn timeout(&self) -> Option<crate::expr::PyFormatString> {
        self.inner
            .timeout
            .as_ref()
            .map(|t| crate::expr::PyFormatString { inner: t.clone() })
    }

    #[getter]
    fn cancelation(&self) -> Option<PyCancelationMode> {
        self.inner
            .cancelation
            .as_ref()
            .map(|c| PyCancelationMode { inner: c.clone() })
    }
}

// ── PyEnvironment ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.model._v1.job", name = "Environment", from_py_object)]
#[derive(Clone)]
pub(crate) struct PyEnvironment {
    pub(crate) inner: job::Environment,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyEnvironment {
    #[getter]
    fn name(&self) -> &str {
        &self.inner.name
    }

    #[getter]
    fn description(&self) -> Option<&str> {
        self.inner.description.as_deref()
    }

    #[getter]
    fn script(&self) -> Option<PyEnvironmentScript> {
        self.inner
            .script
            .as_ref()
            .map(|s| PyEnvironmentScript { inner: s.clone() })
    }

    #[getter]
    fn variables(&self) -> Option<HashMap<String, String>> {
        self.inner.variables.as_ref().map(|vars| {
            vars.iter()
                .map(|(k, v)| (k.clone(), v.raw().to_string()))
                .collect()
        })
    }

    fn __repr__(&self) -> String {
        format!("Environment(name={:?})", self.inner.name)
    }
}

// ── PyEnvironmentScript ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.job",
    name = "EnvironmentScript",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyEnvironmentScript {
    inner: job::EnvironmentScript,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyEnvironmentScript {
    #[getter]
    fn actions(&self) -> PyEnvironmentActions {
        PyEnvironmentActions {
            inner: self.inner.actions.clone(),
        }
    }

    #[getter]
    fn embedded_files(&self) -> Option<Vec<PyEmbeddedFile>> {
        self.inner.embedded_files.as_ref().map(|files| {
            files
                .iter()
                .map(|f| PyEmbeddedFile { inner: f.clone() })
                .collect()
        })
    }

    #[getter]
    #[pyo3(name = "embeddedFiles")]
    fn embedded_files_camel(&self) -> Option<Vec<PyEmbeddedFile>> {
        self.embedded_files()
    }
}

// ── PyEnvironmentActions ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.job",
    name = "EnvironmentActions",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyEnvironmentActions {
    inner: job::EnvironmentActions,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyEnvironmentActions {
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
}

// ── PyEmbeddedFile ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.model._v1.job", name = "EmbeddedFile", from_py_object)]
#[derive(Clone)]
pub(crate) struct PyEmbeddedFile {
    inner: job::EmbeddedFile,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyEmbeddedFile {
    /// Build an EmbeddedFile in the v2023_09 schema.
    ///
    /// Accepts keyword arguments matching the legacy Pydantic EmbeddedFileText
    /// shape used by the Deadline Cloud worker agent and other consumers:
    ///
    /// ```text
    /// EmbeddedFile(name="x", type="TEXT", data=FormatString("..."))
    /// ```
    ///
    /// Also accepts snake-case (`end_of_line`) and camelCase (`endOfLine`).
    #[new]
    #[pyo3(signature = (
        *,
        name,
        r#type,
        filename=None,
        data=None,
        runnable=None,
        endOfLine=None,
        end_of_line=None,
    ))]
    fn new(
        name: String,
        r#type: String,
        filename: Option<String>,
        data: Option<crate::expr::PyFormatString>,
        runnable: Option<bool>,
        #[allow(non_snake_case)] endOfLine: Option<String>,
        end_of_line: Option<String>,
    ) -> PyResult<Self> {
        let file_type = match r#type.as_str() {
            "TEXT" => openjd_model::types::FileType::Text,
            other => {
                return Err(pyo3::exceptions::PyValueError::new_err(format!(
                    "EmbeddedFile.type must be 'TEXT', got {other:?}"
                )));
            }
        };
        let eol_str = end_of_line.or(endOfLine);
        let end_of_line = match eol_str.as_deref() {
            None => None,
            Some("LF") => Some(openjd_model::types::EndOfLine::Lf),
            Some("CRLF") => Some(openjd_model::types::EndOfLine::Crlf),
            Some(other) => {
                return Err(pyo3::exceptions::PyValueError::new_err(format!(
                    "EmbeddedFile.endOfLine must be 'LF' or 'CRLF', got {other:?}"
                )));
            }
        };
        Ok(PyEmbeddedFile {
            inner: job::EmbeddedFile {
                name,
                file_type,
                // Plain string per the 2023-09 schema: the field is not
                // @fmtstring, so "{{ }}" sequences are literal text.
                filename,
                data: data.map(|d| d.inner),
                runnable,
                end_of_line,
            },
        })
    }

    #[getter]
    fn name(&self) -> &str {
        &self.inner.name
    }

    #[getter]
    #[pyo3(name = "type")]
    fn type_(&self) -> String {
        self.inner.file_type.to_string()
    }

    #[getter]
    fn filename(&self) -> Option<String> {
        self.inner.filename.clone()
    }

    #[getter]
    fn data(&self) -> Option<String> {
        self.inner.data.as_ref().map(|d| d.raw().to_string())
    }

    /// Whether this embedded file should be marked executable when
    /// the session materialises it on disk. ``None`` means the
    /// template did not set the field. Mirrors v0's
    /// ``EmbeddedFile.runnable``.
    #[getter]
    fn runnable(&self) -> Option<bool> {
        self.inner.runnable
    }

    /// End-of-line policy for this embedded file: ``"LF"``,
    /// ``"CRLF"``, ``"AUTO"``, or ``None`` if the template did not
    /// set the field. Mirrors v0's ``EmbeddedFile.endOfLine``.
    #[getter]
    fn end_of_line(&self) -> Option<&'static str> {
        self.inner.end_of_line.map(|e| match e {
            openjd_model::types::EndOfLine::Lf => "LF",
            openjd_model::types::EndOfLine::Crlf => "CRLF",
            openjd_model::types::EndOfLine::Auto => "AUTO",
        })
    }

    /// camelCase alias for ``end_of_line``.
    #[getter]
    #[pyo3(name = "endOfLine")]
    fn end_of_line_camel(&self) -> Option<&'static str> {
        self.end_of_line()
    }
}

// ── PyJobParameter ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.model._v1.job", name = "JobParameter", from_py_object)]
#[derive(Clone)]
pub(crate) struct PyJobParameter {
    inner: job::JobParameter,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyJobParameter {
    #[getter]
    fn name(&self) -> &str {
        &self.inner.name
    }

    /// The parameter's type as a :class:`JobParameterType` enum.
    /// Mirrors the v0 reference's ``JobParameter.type`` field type
    /// and the underlying Rust ``job::JobParameter.param_type``
    /// field.
    ///
    /// Note: ``JobParameterType`` is a pyo3 enum without a
    /// ``str`` mixin, so equality against a string literal returns
    /// ``False`` — ``param.type == "INT"`` is **not** the same as
    /// ``param.type == JobParameterType.INT``. Compare against
    /// the enum, use ``param.type is JobParameterType.INT``, or
    /// call ``str(param.type)`` to get the spec-form string.
    #[getter]
    #[pyo3(name = "type")]
    fn type_(&self) -> PyJobParameterType {
        self.inner.param_type.into()
    }

    #[getter]
    fn value(&self) -> PyExprValue {
        PyExprValue {
            inner: self.inner.value.clone(),
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "JobParameter(name={:?}, type={:?})",
            self.inner.name,
            self.inner.param_type.as_spec_str()
        )
    }
}

// ── PyHostRequirements / PyAmountRequirement / PyAttributeRequirement ──
//
// Job-time host requirements. Distinct from the template-time
// `Template{HostRequirements,AmountRequirement,AttributeRequirement}`
// pyclasses in `template_types.rs`: there, `min`/`max` and
// `any_of`/`all_of` are `FormatString` (raw template syntax). Here,
// after `create_job` has resolved the template, the format strings
// have been evaluated to concrete `f64` (for amounts) and `String`
// (for attributes).

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.job",
    name = "AmountRequirement",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyAmountRequirement {
    inner: job::AmountRequirement,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyAmountRequirement {
    #[getter]
    fn name(&self) -> &str {
        &self.inner.name
    }

    #[getter]
    fn min(&self) -> Option<f64> {
        self.inner.min
    }

    #[getter]
    fn max(&self) -> Option<f64> {
        self.inner.max
    }

    fn __repr__(&self) -> String {
        format!("AmountRequirement(name={:?})", self.inner.name)
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.job",
    name = "AttributeRequirement",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyAttributeRequirement {
    inner: job::AttributeRequirement,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyAttributeRequirement {
    #[getter]
    fn name(&self) -> &str {
        &self.inner.name
    }

    #[getter]
    fn any_of(&self) -> Option<Vec<String>> {
        self.inner.any_of.clone()
    }

    #[getter]
    #[pyo3(name = "anyOf")]
    fn any_of_camel(&self) -> Option<Vec<String>> {
        self.any_of()
    }

    #[getter]
    fn all_of(&self) -> Option<Vec<String>> {
        self.inner.all_of.clone()
    }

    #[getter]
    #[pyo3(name = "allOf")]
    fn all_of_camel(&self) -> Option<Vec<String>> {
        self.all_of()
    }

    fn __repr__(&self) -> String {
        format!("AttributeRequirement(name={:?})", self.inner.name)
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.job",
    name = "HostRequirements",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyHostRequirements {
    inner: job::HostRequirements,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyHostRequirements {
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
}

// ── PyStepParameterSpace ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.job",
    name = "StepParameterSpace",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyStepParameterSpace {
    pub(crate) inner: job::StepParameterSpace,
}

/// Build a `TaskParameter` JSON value (in the externally-tagged form
/// expected by serde) from the test-friendly `{type, range, [chunks]}`
/// dict shape.
///
/// Accepts:
/// - `type` as an `openjd._openjd_rs.TaskParameterType` / `JobParameterType`
///   enum (which has `as_str()`), or a plain string like `"INT"`.
/// - `range` as a Python list of strings (or values coerced to strings),
///   or a `RangeExpr` (which has `__str__` returning the canonical form).
fn task_param_def_from_dict(
    py: Python<'_>,
    item: &Bound<'_, pyo3::PyAny>,
) -> PyResult<serde_json::Value> {
    use pyo3::types::{PyDict, PyList};

    let dict: &Bound<'_, PyDict> = item.cast::<PyDict>().map_err(|_| {
        pyo3::exceptions::PyTypeError::new_err(
            "Each task parameter definition must be a dict with 'type' and 'range' keys",
        )
    })?;

    // Resolve the type key into the canonical "INT" / "FLOAT" / ... string.
    let type_obj = dict
        .get_item("type")?
        .ok_or_else(|| pyo3::exceptions::PyKeyError::new_err("Missing 'type' key"))?;
    let type_str: String = if let Ok(s) = type_obj.extract::<String>() {
        s
    } else {
        // Enum values (PyTaskParameterType / PyJobParameterType) expose as_str().
        type_obj.call_method0("as_str")?.extract()?
    };
    let type_upper = type_str.to_ascii_uppercase();

    // The Rust `TaskParameter` variant tag is `int` / `float` / `string` /
    // `path` / `chunkInt` (camelCase via serde rename_all). Map "CHUNK[INT]"
    // → "chunkInt" and the rest to lowercase.
    let variant = match type_upper.as_str() {
        "INT" => "int",
        "FLOAT" => "float",
        "STRING" => "string",
        "PATH" => "path",
        "CHUNK[INT]" | "CHUNK_INT" => "chunkInt",
        other => {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "Unsupported task parameter type: {other}"
            )))
        }
    };

    // Resolve the range key. Either a Python list or a RangeExpr-like.
    //
    // Note on shape: `TaskParameter::{Int, ChunkInt}` use the externally-
    // tagged enum `TaskParamRange<i64>` ({"list": [...]} or {"rangeExpr": "..."}),
    // while Float/String/Path carry a plain `Vec<...>` — flat JSON list, no
    // wrapper.
    let range_obj = dict
        .get_item("range")?
        .ok_or_else(|| pyo3::exceptions::PyKeyError::new_err("Missing 'range' key"))?;
    let is_int_variant = matches!(variant, "int" | "chunkInt");
    let range_value: serde_json::Value = if let Ok(list) = range_obj.cast::<PyList>() {
        // List of values — coerce each to the variant's element type.
        let mut items: Vec<serde_json::Value> = Vec::with_capacity(list.len());
        for v in list.iter() {
            let s: String = match v.extract::<String>() {
                Ok(s) => s,
                Err(_) => v.str()?.extract()?,
            };
            items.push(match variant {
                "int" | "chunkInt" => match s.parse::<i64>() {
                    Ok(n) => serde_json::Value::Number(n.into()),
                    Err(_) => serde_json::Value::String(s),
                },
                "float" => match s.parse::<f64>() {
                    Ok(n) => serde_json::Number::from_f64(n)
                        .map(serde_json::Value::Number)
                        .unwrap_or(serde_json::Value::String(s)),
                    Err(_) => serde_json::Value::String(s),
                },
                _ => serde_json::Value::String(s),
            });
        }
        if is_int_variant {
            serde_json::json!({ "list": items })
        } else {
            serde_json::Value::Array(items)
        }
    } else if let Ok(re) = range_obj.extract::<PyRangeExpr>() {
        // A RangeExpr — only valid for Int/ChunkInt variants. Serialize
        // its native shape (`{ranges: [...]}`) and wrap it in the
        // `TaskParamRange::RangeExpr` variant tag.
        if !is_int_variant {
            return Err(pyo3::exceptions::PyTypeError::new_err(format!(
                "RangeExpr is only valid for INT or CHUNK[INT] task parameters, got {}",
                type_upper
            )));
        }
        let inner_json = serde_json::to_value(&re.inner)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        serde_json::json!({ "rangeExpr": inner_json })
    } else {
        return Err(pyo3::exceptions::PyTypeError::new_err(
            "Task parameter 'range' must be a list or a RangeExpr",
        ));
    };

    // Some variants require additional fields:
    //   - `int`: { range, chunks: Option<ResolvedChunks> }
    //   - `chunkInt`: { range, chunks: ResolvedChunks }
    //   - `float`/`string`/`path`: { range }
    let mut variant_obj = serde_json::Map::new();
    variant_obj.insert("range".to_string(), range_value);
    if matches!(variant, "int" | "chunkInt") {
        // Pull `chunks` if the user supplied one; otherwise default to null
        // for `int` (which is `Option<ResolvedChunks>`).
        let chunks_obj = dict.get_item("chunks")?;
        let chunks_value = match chunks_obj {
            Some(c) if !c.is_none() => {
                // Round-trip through json.dumps for whatever shape the user
                // provided. The Rust `ResolvedChunks` struct is camelCase.
                let json_mod = py.import("json")?;
                let s: String = json_mod.call_method1("dumps", (c,))?.extract()?;
                serde_json::from_str(&s).map_err(|e| {
                    pyo3::exceptions::PyValueError::new_err(format!("Invalid 'chunks' value: {e}"))
                })?
            }
            _ => serde_json::Value::Null,
        };
        if variant == "chunkInt" && chunks_value.is_null() {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "CHUNK[INT] task parameter requires a 'chunks' field",
            ));
        }
        variant_obj.insert("chunks".to_string(), chunks_value);
    }

    let mut outer = serde_json::Map::new();
    outer.insert(variant.to_string(), serde_json::Value::Object(variant_obj));
    Ok(serde_json::Value::Object(outer))
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyStepParameterSpace {
    /// Build a parameter space from a Python dict of definitions.
    ///
    /// Each value in `taskParameterDefinitions` may be either:
    /// - A dict with `type` (string or enum) and `range` (list of strings
    ///   or a RangeExpr). For CHUNK[INT] params, `chunks` is required.
    /// - Anything else accepted by the existing JSON shape used by the
    ///   `task_parameter_definitions` getter.
    #[new]
    #[pyo3(signature = (*, taskParameterDefinitions=None, combination=None))]
    #[allow(non_snake_case)]
    fn new(
        py: Python<'_>,
        taskParameterDefinitions: Option<&Bound<'_, pyo3::types::PyDict>>,
        combination: Option<String>,
    ) -> PyResult<Self> {
        let mut defs = serde_json::Map::new();
        if let Some(dict) = taskParameterDefinitions {
            for (key, val) in dict.iter() {
                let name: String = key.extract()?;
                let value = task_param_def_from_dict(py, &val)?;
                defs.insert(name, value);
            }
        }
        let space_json = serde_json::json!({
            "taskParameterDefinitions": serde_json::Value::Object(defs),
            "combination": combination,
        });
        let inner: job::StepParameterSpace = serde_json::from_value(space_json)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        Ok(PyStepParameterSpace { inner })
    }

    #[getter]
    fn task_parameter_definitions(&self, py: Python<'_>) -> PyResult<Py<pyo3::PyAny>> {
        use pyo3::IntoPyObjectExt;
        let dict = pyo3::types::PyDict::new(py);
        for (name, tp) in &self.inner.task_parameter_definitions {
            let value = crate::model::task_parameter::task_parameter_to_py(py, tp)?;
            dict.set_item(name, value)?;
        }
        dict.into_py_any(py)
    }

    #[getter]
    #[pyo3(name = "taskParameterDefinitions")]
    fn task_parameter_definitions_camel(&self, py: Python<'_>) -> PyResult<Py<pyo3::PyAny>> {
        self.task_parameter_definitions(py)
    }

    #[getter]
    fn combination(&self) -> Option<&str> {
        self.inner.combination.as_deref()
    }
}

// ── PyStepDependency ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.job",
    name = "StepDependency",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyStepDependency {
    inner: job::StepDependency,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyStepDependency {
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
}

// ── PyCancelationMode ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.job",
    name = "CancelationMode",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyCancelationMode {
    inner: job::CancelationMode,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyCancelationMode {
    #[getter]
    fn mode(&self) -> &str {
        match &self.inner {
            job::CancelationMode::Terminate => "TERMINATE",
            job::CancelationMode::NotifyThenTerminate { .. } => "NOTIFY_THEN_TERMINATE",
            // The raw format string; the mode decision is deferred to run
            // time. Matches the openjd-rs serialization of DeferredMode.
            job::CancelationMode::DeferredMode { mode, .. } => mode.raw(),
        }
    }

    #[getter]
    fn notify_period_in_seconds(&self) -> Option<String> {
        match &self.inner {
            job::CancelationMode::NotifyThenTerminate {
                notify_period_in_seconds,
            }
            | job::CancelationMode::DeferredMode {
                notify_period_in_seconds,
                ..
            } => notify_period_in_seconds
                .as_ref()
                .map(|t| t.raw().to_string()),
            _ => None,
        }
    }
}
