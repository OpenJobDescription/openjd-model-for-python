// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

//! Template-time `StepParameterSpaceDefinition` pyclasses.
//!
//! Mirror the Rust `openjd_model::template::StepParameterSpaceDefinition`
//! and `TaskParameterDefinition` enum 1:1 — the raw, pre-`create_job`
//! form of a step's parameter-space declaration. Returned by
//! `StepTemplate.parameter_space`.
//!
//! Five typed pyclasses mirror the `TaskParameterDefinition` variants:
//!
//! * `IntTaskParameterDefinition` — `range: list[int] | FormatString`
//! * `FloatTaskParameterDefinition` — `range: list[float | FormatString] | FormatString`
//! * `StringTaskParameterDefinition` — `range: list[FormatString] | FormatString`
//! * `PathTaskParameterDefinition` — `range: list[FormatString] | FormatString`
//! * `ChunkIntTaskParameterDefinition` — `range`, plus `chunks: ChunksDefinition`
//!
//! Plus `ChunksDefinition` for the chunks payload (mirrors
//! `template::ChunksDefinition`).
//!
//! All `range` values are exposed as Python unions: a list of values
//! (mirroring the YAML/JSON `[…]` form) OR a `FormatString` (mirroring
//! the `"1-10"` range-expression-string form, which under the EXPR
//! extension may also reference a `RangeExpr` parameter via a
//! `{{Param.X}}` interpolation). Numeric integer fields with possibly
//! parametric values (e.g. `chunks.defaultTaskCount`) are exposed as
//! `int | FormatString`.
//!
//! Pickle round-trip is **not** yet supported on these pyclasses —
//! they're exposed as read-only views of decoded templates. To
//! round-trip a template, re-decode from the source document.

use pyo3::prelude::*;
use pyo3::types::PyList;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_model::template::{
    ChunkIntTaskParameterDefinition, ChunksDefinition, FloatRange, FloatRangeItem,
    FloatTaskParameterDefinition, IntOrFormatString, IntRange, IntTaskParameterDefinition,
    PathTaskParameterDefinition, RangeConstraint, StepParameterSpaceDefinition, StringRange,
    StringTaskParameterDefinition, TaskParameterDefinition,
};

use crate::expr::PyFormatString;

// ── Helpers ──

fn range_constraint_str(rc: &RangeConstraint) -> &'static str {
    match rc {
        RangeConstraint::Contiguous => "CONTIGUOUS",
        RangeConstraint::Noncontiguous => "NONCONTIGUOUS",
    }
}

/// Convert an `IntOrFormatString` to a Python value (`int` or
/// `FormatString`).
fn int_or_fs_to_py<'py>(py: Python<'py>, v: &IntOrFormatString) -> PyResult<Bound<'py, PyAny>> {
    match v {
        IntOrFormatString::Int(n) => Ok(n.into_pyobject(py)?.into_any()),
        IntOrFormatString::FormatString(fs) => Ok(PyFormatString { inner: fs.clone() }
            .into_pyobject(py)?
            .into_any()),
    }
}

/// Convert a `FloatRangeItem` to a Python value (`float` or
/// `FormatString`).
fn float_range_item_to_py<'py>(py: Python<'py>, v: &FloatRangeItem) -> PyResult<Bound<'py, PyAny>> {
    match v {
        FloatRangeItem::Float(f) => Ok(f.into_pyobject(py)?.into_any()),
        FloatRangeItem::FormatString(fs) => Ok(PyFormatString { inner: fs.clone() }
            .into_pyobject(py)?
            .into_any()),
    }
}

/// Convert an `IntRange` to a Python value (`list[int]` or
/// `FormatString`).
fn int_range_to_py<'py>(py: Python<'py>, r: &IntRange) -> PyResult<Bound<'py, PyAny>> {
    match r {
        IntRange::List(items) => {
            let py_list = PyList::empty(py);
            for item in items {
                py_list.append(item.0)?;
            }
            Ok(py_list.into_any())
        }
        IntRange::Expression(fs) => Ok(PyFormatString { inner: fs.clone() }
            .into_pyobject(py)?
            .into_any()),
    }
}

/// Convert a `StringRange` to a Python value
/// (`list[FormatString]` or `FormatString`).
fn string_range_to_py<'py>(py: Python<'py>, r: &StringRange) -> PyResult<Bound<'py, PyAny>> {
    match r {
        StringRange::List(items) => {
            let py_list = PyList::empty(py);
            for fs in items {
                py_list.append(PyFormatString { inner: fs.clone() })?;
            }
            Ok(py_list.into_any())
        }
        StringRange::Expression(fs) => Ok(PyFormatString { inner: fs.clone() }
            .into_pyobject(py)?
            .into_any()),
    }
}

/// Convert a `FloatRange` to a Python value
/// (`list[float | FormatString]` or `FormatString`).
fn float_range_to_py<'py>(py: Python<'py>, r: &FloatRange) -> PyResult<Bound<'py, PyAny>> {
    match r {
        FloatRange::List(items) => {
            let py_list = PyList::empty(py);
            for item in items {
                py_list.append(float_range_item_to_py(py, item)?)?;
            }
            Ok(py_list.into_any())
        }
        FloatRange::Expression(fs) => Ok(PyFormatString { inner: fs.clone() }
            .into_pyobject(py)?
            .into_any()),
    }
}

// ── ChunksDefinition ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "ChunksDefinition",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyChunksDefinition {
    pub(crate) inner: ChunksDefinition,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyChunksDefinition {
    #[getter]
    fn default_task_count<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        int_or_fs_to_py(py, &self.inner.default_task_count)
    }

    #[getter]
    #[pyo3(name = "defaultTaskCount")]
    fn default_task_count_camel<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        self.default_task_count(py)
    }

    #[getter]
    fn target_runtime_seconds<'py>(&self, py: Python<'py>) -> PyResult<Option<Bound<'py, PyAny>>> {
        match &self.inner.target_runtime_seconds {
            None => Ok(None),
            Some(v) => Ok(Some(int_or_fs_to_py(py, v)?)),
        }
    }

    #[getter]
    #[pyo3(name = "targetRuntimeSeconds")]
    fn target_runtime_seconds_camel<'py>(
        &self,
        py: Python<'py>,
    ) -> PyResult<Option<Bound<'py, PyAny>>> {
        self.target_runtime_seconds(py)
    }

    #[getter]
    fn range_constraint(&self) -> &'static str {
        range_constraint_str(&self.inner.range_constraint)
    }

    #[getter]
    #[pyo3(name = "rangeConstraint")]
    fn range_constraint_camel(&self) -> &'static str {
        self.range_constraint()
    }

    fn __repr__(&self) -> String {
        "ChunksDefinition(...)".to_string()
    }
}

// ── IntTaskParameterDefinition ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "IntTaskParameterDefinition",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyIntTaskParameterDefinition {
    pub(crate) inner: IntTaskParameterDefinition,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyIntTaskParameterDefinition {
    #[getter]
    fn r#type(&self) -> &'static str {
        "INT"
    }

    #[getter]
    fn name(&self) -> &str {
        self.inner.name.as_str()
    }

    #[getter]
    fn range<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        int_range_to_py(py, &self.inner.range)
    }

    fn __repr__(&self) -> String {
        format!(
            "IntTaskParameterDefinition(name={:?})",
            self.inner.name.as_str()
        )
    }
}

// ── FloatTaskParameterDefinition ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "FloatTaskParameterDefinition",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyFloatTaskParameterDefinition {
    pub(crate) inner: FloatTaskParameterDefinition,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyFloatTaskParameterDefinition {
    #[getter]
    fn r#type(&self) -> &'static str {
        "FLOAT"
    }

    #[getter]
    fn name(&self) -> &str {
        self.inner.name.as_str()
    }

    #[getter]
    fn range<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        float_range_to_py(py, &self.inner.range)
    }

    fn __repr__(&self) -> String {
        format!(
            "FloatTaskParameterDefinition(name={:?})",
            self.inner.name.as_str()
        )
    }
}

// ── StringTaskParameterDefinition ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "StringTaskParameterDefinition",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyStringTaskParameterDefinition {
    pub(crate) inner: StringTaskParameterDefinition,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyStringTaskParameterDefinition {
    #[getter]
    fn r#type(&self) -> &'static str {
        "STRING"
    }

    #[getter]
    fn name(&self) -> &str {
        self.inner.name.as_str()
    }

    #[getter]
    fn range<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        string_range_to_py(py, &self.inner.range)
    }

    fn __repr__(&self) -> String {
        format!(
            "StringTaskParameterDefinition(name={:?})",
            self.inner.name.as_str()
        )
    }
}

// ── PathTaskParameterDefinition ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "PathTaskParameterDefinition",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyPathTaskParameterDefinition {
    pub(crate) inner: PathTaskParameterDefinition,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyPathTaskParameterDefinition {
    #[getter]
    fn r#type(&self) -> &'static str {
        "PATH"
    }

    #[getter]
    fn name(&self) -> &str {
        self.inner.name.as_str()
    }

    #[getter]
    fn range<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        string_range_to_py(py, &self.inner.range)
    }

    fn __repr__(&self) -> String {
        format!(
            "PathTaskParameterDefinition(name={:?})",
            self.inner.name.as_str()
        )
    }
}

// ── ChunkIntTaskParameterDefinition ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "ChunkIntTaskParameterDefinition",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyChunkIntTaskParameterDefinition {
    pub(crate) inner: ChunkIntTaskParameterDefinition,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyChunkIntTaskParameterDefinition {
    #[getter]
    fn r#type(&self) -> &'static str {
        "CHUNK[INT]"
    }

    #[getter]
    fn name(&self) -> &str {
        self.inner.name.as_str()
    }

    #[getter]
    fn range<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        int_range_to_py(py, &self.inner.range)
    }

    #[getter]
    fn chunks(&self) -> PyChunksDefinition {
        PyChunksDefinition {
            inner: self.inner.chunks.clone(),
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "ChunkIntTaskParameterDefinition(name={:?})",
            self.inner.name.as_str()
        )
    }
}

// ── Dispatch ──

/// Convert a `TaskParameterDefinition` enum value into the appropriate
/// pyclass instance.
fn task_param_def_to_py<'py>(
    py: Python<'py>,
    def: &TaskParameterDefinition,
) -> PyResult<Bound<'py, PyAny>> {
    match def {
        TaskParameterDefinition::INT(p) => {
            Bound::new(py, PyIntTaskParameterDefinition { inner: p.clone() }).map(|b| b.into_any())
        }
        TaskParameterDefinition::FLOAT(p) => {
            Bound::new(py, PyFloatTaskParameterDefinition { inner: p.clone() })
                .map(|b| b.into_any())
        }
        TaskParameterDefinition::STRING(p) => {
            Bound::new(py, PyStringTaskParameterDefinition { inner: p.clone() })
                .map(|b| b.into_any())
        }
        TaskParameterDefinition::PATH(p) => {
            Bound::new(py, PyPathTaskParameterDefinition { inner: p.clone() }).map(|b| b.into_any())
        }
        TaskParameterDefinition::CHUNK_INT(p) => {
            Bound::new(py, PyChunkIntTaskParameterDefinition { inner: p.clone() })
                .map(|b| b.into_any())
        }
    }
}

// ── StepParameterSpaceDefinition ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "StepParameterSpaceDefinition",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyStepParameterSpaceDefinition {
    pub(crate) inner: StepParameterSpaceDefinition,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyStepParameterSpaceDefinition {
    /// The list of typed task-parameter definitions. Each element is
    /// one of `IntTaskParameterDefinition`,
    /// `FloatTaskParameterDefinition`,
    /// `StringTaskParameterDefinition`,
    /// `PathTaskParameterDefinition`, or
    /// `ChunkIntTaskParameterDefinition`.
    #[getter]
    fn task_parameter_definitions<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        let py_list = PyList::empty(py);
        for def in &self.inner.task_parameter_definitions {
            py_list.append(task_param_def_to_py(py, def)?)?;
        }
        Ok(py_list)
    }

    #[getter]
    #[pyo3(name = "taskParameterDefinitions")]
    fn task_parameter_definitions_camel<'py>(
        &self,
        py: Python<'py>,
    ) -> PyResult<Bound<'py, PyList>> {
        self.task_parameter_definitions(py)
    }

    /// The combination expression, or ``None`` if the default
    /// (left-to-right product) applies.
    #[getter]
    fn combination(&self) -> Option<&str> {
        self.inner.combination.as_deref()
    }

    fn __repr__(&self) -> String {
        format!(
            "StepParameterSpaceDefinition(task_parameter_definitions={} items, combination={:?})",
            self.inner.task_parameter_definitions.len(),
            self.inner.combination,
        )
    }
}
