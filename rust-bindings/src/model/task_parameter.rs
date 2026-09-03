// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

//! Typed task-parameter pyclasses exposed by
//! `StepParameterSpace.taskParameterDefinitions`.
//!
//! The Rust crate's runtime `TaskParameter` enum has five variants
//! — `Int`, `Float`, `String`, `Path`, `ChunkInt` — and the binding
//! mirrors that 1:1: each variant gets its own pyclass so users can
//! discriminate with `isinstance()` and pattern-match on `.type`,
//! and so the Python type stub captures each variant's exact
//! `range` shape without an awkward union.
//!
//! Naming follows the Rust runtime variants. The v0 pure-Python
//! reference uses different names (`RangeListTaskParameterDefinition`
//! and `RangeExpressionTaskParameterDefinition`) for the post-
//! `create_job` shape; v1 deliberately diverges to mirror the
//! underlying Rust enum exactly. See
//! `reports/model-bindings-quality-evaluation-report.md` Rec #6 for
//! the rationale.
//!
//! ## Field shapes
//!
//! | pyclass | range | chunks |
//! |---|---|---|
//! | `IntTaskParameter` | `list[int] \| RangeExpr` | (absent) |
//! | `FloatTaskParameter` | `list[float]` | (absent) |
//! | `StringTaskParameter` | `list[str]` | (absent) |
//! | `PathTaskParameter` | `list[str]` | (absent) |
//! | `ChunkIntTaskParameter` | `list[int] \| RangeExpr` | `TaskChunksDefinition` |
//!
//! `IntTaskParameter` does *not* carry `chunks` even though the
//! underlying Rust struct has `chunks: Option<ResolvedChunks>`,
//! because no resolver path ever produces `Some(_)` on the `Int`
//! variant — chunks are exclusively a `ChunkInt` concern. Mirroring
//! the runtime *behaviour* is more useful than mirroring the
//! struct field declaration.

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_model::job::{ResolvedChunks, TaskParamRange, TaskParameter};
use openjd_model::template::RangeConstraint;

use crate::expr::range_expr::PyRangeExpr;
use crate::model::types::PyTaskParameterType;

// ── TaskChunksDefinition ─────────────────────────────────────────

/// Resolved chunks payload attached to a `ChunkIntTaskParameter`.
///
/// Mirrors `openjd_model::job::ResolvedChunks` — the post-
/// format-string-resolution form. `target_runtime_seconds` is
/// optional; `range_constraint` is one of the strings
/// `"CONTIGUOUS"` or `"NONCONTIGUOUS"`.
#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.job",
    name = "TaskChunksDefinition",
    frozen,
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyTaskChunksDefinition {
    pub(crate) inner: ResolvedChunks,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyTaskChunksDefinition {
    #[new]
    #[pyo3(signature = (*, default_task_count, target_runtime_seconds=None, range_constraint))]
    fn new(
        default_task_count: usize,
        target_runtime_seconds: Option<usize>,
        range_constraint: &str,
    ) -> PyResult<Self> {
        let constraint = match range_constraint {
            "CONTIGUOUS" => RangeConstraint::Contiguous,
            "NONCONTIGUOUS" => RangeConstraint::Noncontiguous,
            other => {
                return Err(pyo3::exceptions::PyValueError::new_err(format!(
                    "Unknown range_constraint {other:?}; expected 'CONTIGUOUS' or 'NONCONTIGUOUS'"
                )))
            }
        };
        Ok(Self {
            inner: ResolvedChunks {
                default_task_count,
                target_runtime_seconds,
                range_constraint: constraint,
            },
        })
    }

    #[getter]
    fn default_task_count(&self) -> usize {
        self.inner.default_task_count
    }

    #[getter]
    fn target_runtime_seconds(&self) -> Option<usize> {
        self.inner.target_runtime_seconds
    }

    /// Either ``"CONTIGUOUS"`` or ``"NONCONTIGUOUS"``.
    #[getter]
    fn range_constraint(&self) -> &'static str {
        match self.inner.range_constraint {
            RangeConstraint::Contiguous => "CONTIGUOUS",
            RangeConstraint::Noncontiguous => "NONCONTIGUOUS",
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "TaskChunksDefinition(default_task_count={}, target_runtime_seconds={:?}, range_constraint={:?})",
            self.inner.default_task_count,
            self.inner.target_runtime_seconds,
            self.range_constraint(),
        )
    }

    fn __eq__(&self, other: &Self) -> bool {
        self.inner.default_task_count == other.inner.default_task_count
            && self.inner.target_runtime_seconds == other.inner.target_runtime_seconds
            && self.inner.range_constraint == other.inner.range_constraint
    }

    /// Pickle support — round-trips through ``__init__``.
    #[allow(clippy::type_complexity)] // pickle reducer tuple shape is by design
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
        kwargs.set_item("default_task_count", self.inner.default_task_count)?;
        kwargs.set_item("target_runtime_seconds", self.inner.target_runtime_seconds)?;
        kwargs.set_item("range_constraint", self.range_constraint())?;
        let args = PyTuple::new(py, [cls.into_any(), kwargs.into_any()])?;
        Ok((helper, args.into()))
    }
}

// ── Helpers ──────────────────────────────────────────────────────

/// Convert a `TaskParamRange<i64>` into either a Python `list[int]`
/// or a `PyRangeExpr`, depending on the variant.
fn int_range_to_py<'py>(
    py: Python<'py>,
    range: &TaskParamRange<i64>,
) -> PyResult<Bound<'py, PyAny>> {
    match range {
        TaskParamRange::List(items) => {
            let list = PyList::new(py, items)?;
            Ok(list.into_any())
        }
        TaskParamRange::RangeExpr(expr) => {
            use pyo3::IntoPyObjectExt;
            let py_expr = PyRangeExpr {
                inner: expr.clone(),
            };
            py_expr.into_bound_py_any(py)
        }
    }
}

/// Coerce a Python value (either `list[int]` or a `PyRangeExpr`)
/// into a Rust `TaskParamRange<i64>`. Used by the constructors.
fn int_range_from_py(value: &Bound<'_, PyAny>) -> PyResult<TaskParamRange<i64>> {
    if let Ok(re) = value.extract::<PyRangeExpr>() {
        return Ok(TaskParamRange::RangeExpr(re.inner));
    }
    if let Ok(list) = value.cast::<PyList>() {
        let mut out = Vec::with_capacity(list.len());
        for item in list.iter() {
            out.push(item.extract::<i64>()?);
        }
        return Ok(TaskParamRange::List(out));
    }
    Err(pyo3::exceptions::PyTypeError::new_err(
        "range must be a list[int] or a RangeExpr",
    ))
}

// ── IntTaskParameter ─────────────────────────────────────────────

/// Resolved INT task parameter: a `range` (list of ints OR a
/// `RangeExpr`) and no chunks.
#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.job",
    name = "IntTaskParameter",
    frozen,
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyIntTaskParameter {
    pub(crate) range: TaskParamRange<i64>,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyIntTaskParameter {
    #[new]
    #[pyo3(signature = (*, range))]
    fn new(range: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self {
            range: int_range_from_py(range)?,
        })
    }

    /// Always ``TaskParameterType.INT``.
    #[getter]
    fn r#type(&self) -> PyTaskParameterType {
        PyTaskParameterType::INT
    }

    /// Either a ``list[int]`` or a :class:`openjd.expr.RangeExpr`.
    #[getter]
    fn range<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        int_range_to_py(py, &self.range)
    }

    fn __repr__<'py>(&self, py: Python<'py>) -> PyResult<String> {
        Ok(format!(
            "IntTaskParameter(range={})",
            self.range(py)?.repr()?,
        ))
    }

    fn __eq__(&self, other: &Self) -> bool {
        int_ranges_equal(&self.range, &other.range)
    }

    /// Pickle support — round-trips through ``__init__(*, range=...)``.
    #[allow(clippy::type_complexity)] // pickle reducer tuple shape is by design
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
        kwargs.set_item("range", int_range_to_py(py, &self.range)?)?;
        let args = PyTuple::new(py, [cls.into_any(), kwargs.into_any()])?;
        Ok((helper, args.into()))
    }
}

// ── FloatTaskParameter ───────────────────────────────────────────

/// Resolved FLOAT task parameter: a list of floats.
#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.job",
    name = "FloatTaskParameter",
    frozen,
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyFloatTaskParameter {
    pub(crate) range: Vec<f64>,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyFloatTaskParameter {
    #[new]
    #[pyo3(signature = (*, range))]
    fn new(range: Vec<f64>) -> Self {
        Self { range }
    }

    /// Always ``TaskParameterType.FLOAT``.
    #[getter]
    fn r#type(&self) -> PyTaskParameterType {
        PyTaskParameterType::FLOAT
    }

    #[getter]
    fn range(&self) -> Vec<f64> {
        self.range.clone()
    }

    fn __repr__(&self) -> String {
        format!("FloatTaskParameter(range={:?})", self.range)
    }

    fn __eq__(&self, other: &Self) -> bool {
        self.range == other.range
    }

    /// Pickle support — round-trips through ``__init__(*, range=...)``.
    #[allow(clippy::type_complexity)] // pickle reducer tuple shape is by design
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
        kwargs.set_item("range", self.range.clone())?;
        let args = PyTuple::new(py, [cls.into_any(), kwargs.into_any()])?;
        Ok((helper, args.into()))
    }
}

// ── StringTaskParameter ──────────────────────────────────────────

/// Resolved STRING task parameter: a list of strings.
#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.job",
    name = "StringTaskParameter",
    frozen,
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyStringTaskParameter {
    pub(crate) range: Vec<String>,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyStringTaskParameter {
    #[new]
    #[pyo3(signature = (*, range))]
    fn new(range: Vec<String>) -> Self {
        Self { range }
    }

    /// Always ``TaskParameterType.STRING``.
    #[getter]
    fn r#type(&self) -> PyTaskParameterType {
        PyTaskParameterType::STRING
    }

    #[getter]
    fn range(&self) -> Vec<String> {
        self.range.clone()
    }

    fn __repr__(&self) -> String {
        format!("StringTaskParameter(range={:?})", self.range)
    }

    fn __eq__(&self, other: &Self) -> bool {
        self.range == other.range
    }

    /// Pickle support — round-trips through ``__init__(*, range=...)``.
    #[allow(clippy::type_complexity)] // pickle reducer tuple shape is by design
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
        kwargs.set_item("range", self.range.clone())?;
        let args = PyTuple::new(py, [cls.into_any(), kwargs.into_any()])?;
        Ok((helper, args.into()))
    }
}

// ── PathTaskParameter ────────────────────────────────────────────

/// Resolved PATH task parameter: a list of path strings.
#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.job",
    name = "PathTaskParameter",
    frozen,
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyPathTaskParameter {
    pub(crate) range: Vec<String>,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyPathTaskParameter {
    #[new]
    #[pyo3(signature = (*, range))]
    fn new(range: Vec<String>) -> Self {
        Self { range }
    }

    /// Always ``TaskParameterType.PATH``.
    #[getter]
    fn r#type(&self) -> PyTaskParameterType {
        PyTaskParameterType::PATH
    }

    #[getter]
    fn range(&self) -> Vec<String> {
        self.range.clone()
    }

    fn __repr__(&self) -> String {
        format!("PathTaskParameter(range={:?})", self.range)
    }

    fn __eq__(&self, other: &Self) -> bool {
        self.range == other.range
    }

    /// Pickle support — round-trips through ``__init__(*, range=...)``.
    #[allow(clippy::type_complexity)] // pickle reducer tuple shape is by design
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
        kwargs.set_item("range", self.range.clone())?;
        let args = PyTuple::new(py, [cls.into_any(), kwargs.into_any()])?;
        Ok((helper, args.into()))
    }
}

// ── ChunkIntTaskParameter ────────────────────────────────────────

/// Resolved CHUNK[INT] task parameter: a `range` (list of ints OR
/// a `RangeExpr`) plus a required :class:`TaskChunksDefinition`.
/// Available only when the ``TASK_CHUNKING`` extension is enabled.
#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.job",
    name = "ChunkIntTaskParameter",
    frozen,
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyChunkIntTaskParameter {
    pub(crate) range: TaskParamRange<i64>,
    pub(crate) chunks: ResolvedChunks,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyChunkIntTaskParameter {
    #[new]
    #[pyo3(signature = (*, range, chunks))]
    fn new(range: &Bound<'_, PyAny>, chunks: PyTaskChunksDefinition) -> PyResult<Self> {
        Ok(Self {
            range: int_range_from_py(range)?,
            chunks: chunks.inner,
        })
    }

    /// Always ``TaskParameterType.CHUNK_INT``.
    #[getter]
    fn r#type(&self) -> PyTaskParameterType {
        PyTaskParameterType::CHUNK_INT
    }

    /// Either a ``list[int]`` or a :class:`openjd.expr.RangeExpr`.
    #[getter]
    fn range<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        int_range_to_py(py, &self.range)
    }

    /// The chunks definition. Always set on this variant.
    #[getter]
    fn chunks(&self) -> PyTaskChunksDefinition {
        PyTaskChunksDefinition {
            inner: self.chunks.clone(),
        }
    }

    fn __repr__<'py>(&self, py: Python<'py>) -> PyResult<String> {
        Ok(format!(
            "ChunkIntTaskParameter(range={}, chunks={})",
            self.range(py)?.repr()?,
            self.chunks().__repr__(),
        ))
    }

    fn __eq__(&self, other: &Self) -> bool {
        int_ranges_equal(&self.range, &other.range)
            && self.chunks.default_task_count == other.chunks.default_task_count
            && self.chunks.target_runtime_seconds == other.chunks.target_runtime_seconds
            && self.chunks.range_constraint == other.chunks.range_constraint
    }

    /// Pickle support — round-trips through ``__init__(*, range=, chunks=)``.
    #[allow(clippy::type_complexity)] // pickle reducer tuple shape is by design
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
        kwargs.set_item("range", int_range_to_py(py, &self.range)?)?;
        kwargs.set_item("chunks", self.chunks())?;
        let args = PyTuple::new(py, [cls.into_any(), kwargs.into_any()])?;
        Ok((helper, args.into()))
    }
}

// ── Conversion ───────────────────────────────────────────────────

/// Wrap a Rust `TaskParameter` as the appropriate Python pyclass
/// variant.
pub(crate) fn task_parameter_to_py<'py>(
    py: Python<'py>,
    tp: &TaskParameter,
) -> PyResult<Bound<'py, PyAny>> {
    use pyo3::IntoPyObjectExt;
    match tp {
        TaskParameter::Int { range, chunks: _ } => {
            // The runtime crate carries `Option<ResolvedChunks>` on
            // the `Int` variant, but no resolver path ever populates
            // it (only `ChunkInt` does). The Python binding mirrors
            // the runtime *behaviour*: `IntTaskParameter` has no
            // chunks field at all. If a future code path produces
            // `Some(_)` here it should construct `ChunkInt` instead;
            // until then the field is silently ignored.
            PyIntTaskParameter {
                range: range.clone(),
            }
            .into_bound_py_any(py)
        }
        // `Float64` carries the spelling a `<floatstring>` range element was
        // written with (§7.5). It reaches a command line through
        // `TaskParameterValue`, which renders it verbatim; this getter is the
        // numeric introspection view, so take the value and drop the spelling.
        TaskParameter::Float { range } => PyFloatTaskParameter {
            range: range.iter().map(|f| f.value()).collect(),
        }
        .into_bound_py_any(py),
        TaskParameter::String { range } => PyStringTaskParameter {
            range: range.clone(),
        }
        .into_bound_py_any(py),
        TaskParameter::Path { range } => PyPathTaskParameter {
            range: range.clone(),
        }
        .into_bound_py_any(py),
        TaskParameter::ChunkInt { range, chunks } => PyChunkIntTaskParameter {
            range: range.clone(),
            chunks: chunks.clone(),
        }
        .into_bound_py_any(py),
    }
}

// ── Internal helpers ─────────────────────────────────────────────

fn int_ranges_equal(a: &TaskParamRange<i64>, b: &TaskParamRange<i64>) -> bool {
    match (a, b) {
        (TaskParamRange::List(va), TaskParamRange::List(vb)) => va == vb,
        (TaskParamRange::RangeExpr(ea), TaskParamRange::RangeExpr(eb)) => ea == eb,
        _ => false,
    }
}

// Suppress unused-import warning when stub-gen is disabled.
// (PyType import removed in Rec #12 cleanup; the cfg-gated suppression
// is no longer needed.)
