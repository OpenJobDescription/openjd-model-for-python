// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyType};
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_model::template::parse::DocumentType;
use openjd_model::types::TaskParameterType;
use openjd_model::JobParameterType;
use openjd_model::TemplateSpecificationVersion;
use openjd_model::{JobParameterValue, TaskParameterValue};

use crate::expr::expr_value::{expr_value_to_py, py_to_expr_value};

#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyclass_enum(module = "openjd._openjd_rs")
)]
#[pyclass(
    module = "openjd.model._v1.types",
    name = "DocumentType",
    eq,
    eq_int,
    frozen,
    hash,
    from_py_object
)]
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
#[allow(non_camel_case_types, clippy::upper_case_acronyms)]
pub(crate) enum PyDocumentType {
    YAML = 0,
    JSON = 1,
}

impl From<PyDocumentType> for DocumentType {
    fn from(v: PyDocumentType) -> Self {
        match v {
            PyDocumentType::YAML => DocumentType::Yaml,
            PyDocumentType::JSON => DocumentType::Json,
        }
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyDocumentType {
    /// Variant name as a string (e.g. `"YAML"`).
    #[getter]
    fn name(&self) -> &'static str {
        match self {
            Self::YAML => "YAML",
            Self::JSON => "JSON",
        }
    }

    fn __repr__(&self) -> String {
        format!("DocumentType.{}", self.name())
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

/// Template specification version (job-template or
/// environment-template, with the spec revision encoded in the
/// variant name).
///
/// On the Python side the variants are exposed as
/// ``TemplateSpecificationVersion.JOBTEMPLATE_v2023_09`` and
/// ``TemplateSpecificationVersion.ENVIRONMENT_v2023_09`` (matching
/// the v0 Pydantic model's `str`-Enum naming). Instances compare
/// equal to the spec-form string (e.g. ``"jobtemplate-2023-09"``)
/// and ``rev.value`` returns the spec-form string. The constructor
/// accepts either the spec-form string or the variant name (e.g.
/// ``TemplateSpecificationVersion("jobtemplate-2023-09")``).
/// The class is *not* a `str` subclass.
#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyclass_enum(module = "openjd._openjd_rs")
)]
#[pyclass(
    module = "openjd._openjd_rs",
    name = "TemplateSpecificationVersion",
    frozen,
    from_py_object
)]
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
#[allow(non_camel_case_types)]
pub(crate) enum PyTemplateSpecificationVersion {
    #[pyo3(name = "JOBTEMPLATE_v2023_09")]
    JOBTEMPLATE_2023_09 = 0,
    #[pyo3(name = "ENVIRONMENT_v2023_09")]
    ENVIRONMENT_2023_09 = 1,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyTemplateSpecificationVersion {
    /// Construct from a spec-form string (e.g.
    /// ``"jobtemplate-2023-09"``) or a variant name (e.g.
    /// ``"JOBTEMPLATE_v2023_09"``). Mirrors the constructor
    /// behaviour of a Python ``str``-``Enum``.
    #[new]
    fn new(value: &str) -> PyResult<Self> {
        match value {
            "jobtemplate-2023-09" | "JOBTEMPLATE_v2023_09" => Ok(Self::JOBTEMPLATE_2023_09),
            "environment-2023-09" | "ENVIRONMENT_v2023_09" => Ok(Self::ENVIRONMENT_2023_09),
            _ => Err(pyo3::exceptions::PyValueError::new_err(format!(
                "{:?} is not a valid TemplateSpecificationVersion",
                value
            ))),
        }
    }

    fn as_str(&self) -> &'static str {
        match self {
            Self::JOBTEMPLATE_2023_09 => "jobtemplate-2023-09",
            Self::ENVIRONMENT_2023_09 => "environment-2023-09",
        }
    }

    fn is_job_template(&self) -> bool {
        matches!(self, Self::JOBTEMPLATE_2023_09)
    }

    fn is_environment_template(&self) -> bool {
        matches!(self, Self::ENVIRONMENT_2023_09)
    }

    fn __str__(&self) -> &'static str {
        self.as_str()
    }

    fn __repr__(&self) -> String {
        format!("TemplateSpecificationVersion.{}", self.name())
    }

    /// Variant name as a string (e.g. ``"JOBTEMPLATE_v2023_09"``).
    /// Matches the Python-side variant name.
    #[getter]
    fn name(&self) -> &'static str {
        match self {
            Self::JOBTEMPLATE_2023_09 => "JOBTEMPLATE_v2023_09",
            Self::ENVIRONMENT_2023_09 => "ENVIRONMENT_v2023_09",
        }
    }

    /// Spec-form string. Mirrors the `.value` attribute of a
    /// Python ``str``-``Enum`` (e.g.
    /// ``ver.value == "jobtemplate-2023-09"``).
    #[getter]
    fn value(&self) -> &'static str {
        self.as_str()
    }

    /// Equal to another ``TemplateSpecificationVersion`` of the
    /// same variant, or to the spec-form string. Returns
    /// ``NotImplemented`` for unrelated types so Python falls back
    /// to the right-hand operand's ``__eq__``.
    fn __eq__(&self, other: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
        use pyo3::IntoPyObjectExt;
        let py = other.py();
        if let Ok(o) = other.extract::<PyTemplateSpecificationVersion>() {
            return (self == &o).into_py_any(py);
        }
        if let Ok(s) = other.extract::<String>() {
            return (self.as_str() == s).into_py_any(py);
        }
        Ok(py.NotImplemented())
    }

    fn __ne__(&self, other: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
        use pyo3::IntoPyObjectExt;
        let py = other.py();
        if let Ok(o) = other.extract::<PyTemplateSpecificationVersion>() {
            return (self != &o).into_py_any(py);
        }
        if let Ok(s) = other.extract::<String>() {
            return (self.as_str() != s).into_py_any(py);
        }
        Ok(py.NotImplemented())
    }

    /// Hash by spec-form string so ``ver == "jobtemplate-2023-09"``
    /// and ``hash(ver) == hash("jobtemplate-2023-09")`` agree
    /// (required for set / dict membership across the two types).
    fn __hash__(&self, py: Python<'_>) -> PyResult<isize> {
        self.as_str().into_pyobject(py)?.hash()
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

impl From<TemplateSpecificationVersion> for PyTemplateSpecificationVersion {
    fn from(v: TemplateSpecificationVersion) -> Self {
        match v {
            TemplateSpecificationVersion::JobTemplate2023_09 => Self::JOBTEMPLATE_2023_09,
            TemplateSpecificationVersion::Environment2023_09 => Self::ENVIRONMENT_2023_09,
            _ => Self::JOBTEMPLATE_2023_09, // future variants
        }
    }
}

#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyclass_enum(module = "openjd._openjd_rs")
)]
#[pyclass(
    module = "openjd.model._v1.types",
    name = "JobParameterType",
    eq,
    eq_int,
    frozen,
    hash,
    from_py_object
)]
#[derive(Clone, Copy, PartialEq)]
#[allow(non_camel_case_types, clippy::upper_case_acronyms)]
pub(crate) enum PyJobParameterType {
    STRING = 0,
    INT = 1,
    FLOAT = 2,
    PATH = 3,
    BOOL = 4,
    RANGE_EXPR = 5,
    LIST_STRING = 6,
    LIST_INT = 7,
    LIST_FLOAT = 8,
    LIST_PATH = 9,
    LIST_BOOL = 10,
    LIST_LIST_INT = 11,
}

impl std::hash::Hash for PyJobParameterType {
    fn hash<H: std::hash::Hasher>(&self, state: &mut H) {
        std::mem::discriminant(self).hash(state);
    }
}
#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyJobParameterType {
    fn as_str(&self) -> &'static str {
        JobParameterType::from(*self).as_spec_str()
    }

    fn __str__(&self) -> &'static str {
        self.as_str()
    }

    fn __repr__(&self) -> String {
        format!("JobParameterType.{}", self.as_str())
    }

    /// Variant name as a string (e.g. `"INT"`, `"LIST_STRING"`).
    #[getter]
    fn name(&self) -> &'static str {
        match self {
            Self::STRING => "STRING",
            Self::INT => "INT",
            Self::FLOAT => "FLOAT",
            Self::PATH => "PATH",
            Self::BOOL => "BOOL",
            Self::RANGE_EXPR => "RANGE_EXPR",
            Self::LIST_STRING => "LIST_STRING",
            Self::LIST_INT => "LIST_INT",
            Self::LIST_FLOAT => "LIST_FLOAT",
            Self::LIST_PATH => "LIST_PATH",
            Self::LIST_BOOL => "LIST_BOOL",
            Self::LIST_LIST_INT => "LIST_LIST_INT",
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

/// Map an OpenJD job-parameter type spec name (e.g. ``"INT"``, ``"LIST[INT]"``,
/// ``"RANGE_EXPR"``; case-insensitive) to its EXPR type spec string
/// (``"int"``, ``"list[int]"``, ``"range_expr"``), or ``None`` when the name is
/// not a recognized job-parameter type. Single-sources both the
/// (case-insensitive) type-name parsing and the OpenJD-type -> EXPR-type
/// mapping in the Rust ``openjd-model`` crate so the Python model does not
/// hand-maintain a parallel table.
#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyfunction(module = "openjd._openjd_rs")
)]
#[pyfunction]
pub(crate) fn job_parameter_type_expr_spec(type_name: &str) -> Option<String> {
    JobParameterType::from_spec_str(type_name.trim()).map(|t| t.expr_type().to_string())
}

impl From<PyJobParameterType> for JobParameterType {
    fn from(v: PyJobParameterType) -> Self {
        match v {
            PyJobParameterType::STRING => JobParameterType::String,
            PyJobParameterType::INT => JobParameterType::Int,
            PyJobParameterType::FLOAT => JobParameterType::Float,
            PyJobParameterType::PATH => JobParameterType::Path,
            PyJobParameterType::BOOL => JobParameterType::Bool,
            PyJobParameterType::RANGE_EXPR => JobParameterType::RangeExpr,
            PyJobParameterType::LIST_STRING => JobParameterType::ListString,
            PyJobParameterType::LIST_INT => JobParameterType::ListInt,
            PyJobParameterType::LIST_FLOAT => JobParameterType::ListFloat,
            PyJobParameterType::LIST_PATH => JobParameterType::ListPath,
            PyJobParameterType::LIST_BOOL => JobParameterType::ListBool,
            PyJobParameterType::LIST_LIST_INT => JobParameterType::ListListInt,
        }
    }
}

impl From<JobParameterType> for PyJobParameterType {
    fn from(v: JobParameterType) -> Self {
        match v {
            JobParameterType::String => PyJobParameterType::STRING,
            JobParameterType::Int => PyJobParameterType::INT,
            JobParameterType::Float => PyJobParameterType::FLOAT,
            JobParameterType::Path => PyJobParameterType::PATH,
            JobParameterType::Bool => PyJobParameterType::BOOL,
            JobParameterType::RangeExpr => PyJobParameterType::RANGE_EXPR,
            JobParameterType::ListString => PyJobParameterType::LIST_STRING,
            JobParameterType::ListInt => PyJobParameterType::LIST_INT,
            JobParameterType::ListFloat => PyJobParameterType::LIST_FLOAT,
            JobParameterType::ListPath => PyJobParameterType::LIST_PATH,
            JobParameterType::ListBool => PyJobParameterType::LIST_BOOL,
            JobParameterType::ListListInt => PyJobParameterType::LIST_LIST_INT,
            _ => PyJobParameterType::STRING, // future variants
        }
    }
}

// ── TaskParameterType ──

#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyclass_enum(module = "openjd._openjd_rs")
)]
#[pyclass(
    module = "openjd.model._v1.types",
    name = "TaskParameterType",
    eq,
    eq_int,
    frozen,
    hash,
    from_py_object
)]
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
#[allow(non_camel_case_types, clippy::upper_case_acronyms)]
pub(crate) enum PyTaskParameterType {
    INT,
    FLOAT,
    STRING,
    PATH,
    CHUNK_INT,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyTaskParameterType {
    fn as_str(&self) -> &'static str {
        match self {
            Self::INT => "INT",
            Self::FLOAT => "FLOAT",
            Self::STRING => "STRING",
            Self::PATH => "PATH",
            Self::CHUNK_INT => "CHUNK[INT]",
        }
    }
    fn __repr__(&self) -> String {
        format!("TaskParameterType.{}", self.name())
    }

    /// Variant name as a string (e.g. `"INT"`, `"CHUNK_INT"`).
    ///
    /// Distinct from `as_str()` for the `CHUNK_INT` variant, whose
    /// spec form is `"CHUNK[INT]"`.
    #[getter]
    fn name(&self) -> &'static str {
        match self {
            Self::INT => "INT",
            Self::FLOAT => "FLOAT",
            Self::STRING => "STRING",
            Self::PATH => "PATH",
            Self::CHUNK_INT => "CHUNK_INT",
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

impl From<PyTaskParameterType> for TaskParameterType {
    fn from(v: PyTaskParameterType) -> Self {
        match v {
            PyTaskParameterType::INT => TaskParameterType::Int,
            PyTaskParameterType::FLOAT => TaskParameterType::Float,
            PyTaskParameterType::STRING => TaskParameterType::String,
            PyTaskParameterType::PATH => TaskParameterType::Path,
            PyTaskParameterType::CHUNK_INT => TaskParameterType::ChunkInt,
        }
    }
}

impl From<TaskParameterType> for PyTaskParameterType {
    fn from(v: TaskParameterType) -> Self {
        // ``TaskParameterType`` is ``#[non_exhaustive]`` so the
        // wildcard arm covers any future variant. Today the enum
        // has exactly five variants, all listed explicitly below.
        match v {
            TaskParameterType::Int => PyTaskParameterType::INT,
            TaskParameterType::Float => PyTaskParameterType::FLOAT,
            TaskParameterType::String => PyTaskParameterType::STRING,
            TaskParameterType::Path => PyTaskParameterType::PATH,
            TaskParameterType::ChunkInt => PyTaskParameterType::CHUNK_INT,
            _ => unreachable!("Unknown TaskParameterType variant — bindings need updating"),
        }
    }
}

// ── TaskParameterValue ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.types",
    name = "TaskParameterValue",
    frozen,
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyTaskParameterValue {
    pub(crate) inner: TaskParameterValue,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyTaskParameterValue {
    /// Construct a ``TaskParameterValue``.
    ///
    /// ``value`` accepts any Python type that ``ExprValue`` accepts:
    /// ``str``, ``int``, ``float``, ``bool``, ``Decimal``, ``list``,
    /// ``ExprValue``, ``RangeExpr``. The ``param_type`` is recorded
    /// as-is — coercion to the target type happens later when the
    /// value flows into ``Session`` / ``create_job``. To match the
    /// pre-binding behaviour, no validation against ``param_type``
    /// is done here.
    #[new]
    #[pyo3(signature = (*, r#type, value))]
    fn new(r#type: PyTaskParameterType, value: &Bound<'_, PyAny>) -> PyResult<Self> {
        let expr_value = py_to_expr_value(value)?;
        Ok(Self {
            inner: TaskParameterValue {
                param_type: r#type.into(),
                value: expr_value,
            },
        })
    }

    #[getter(r#type)]
    fn get_type(&self) -> PyTaskParameterType {
        self.inner.param_type.into()
    }

    /// Canonical string form of the value. Matches the v0 reference's
    /// dataclass-of-strings shape (``"42"``, ``"true"``, ``"[1, 2, 3]"``)
    /// and pre-reshape binding behaviour. For the native Python value,
    /// use ``item()``.
    #[getter]
    fn value(&self) -> String {
        self.inner.value.to_display_string()
    }

    /// Native Python value backing this ``TaskParameterValue``.
    /// Mirrors ``ExprValue.item()`` — returns ``int`` for INT,
    /// ``list`` for LIST_*, etc.
    fn item(&self, py: Python<'_>) -> PyResult<Py<pyo3::PyAny>> {
        expr_value_to_py(py, &self.inner.value)
    }

    fn as_str(&self) -> &'static str {
        let pt: PyTaskParameterType = self.inner.param_type.into();
        pt.as_str()
    }

    fn __eq__(&self, other: &Bound<'_, pyo3::PyAny>) -> PyResult<bool> {
        let other_type = other.getattr("type")?;
        let other_type_str: String = other_type.call_method0("as_str")?.extract()?;
        let other_value: String = other.getattr("value")?.extract()?;
        let self_type: PyTaskParameterType = self.inner.param_type.into();
        Ok(self_type.as_str() == other_type_str
            && self.inner.value.to_display_string() == other_value)
    }

    fn __repr__(&self) -> String {
        let pt: PyTaskParameterType = self.inner.param_type.into();
        format!(
            "TaskParameterValue(type={}, value={:?})",
            pt.as_str(),
            self.inner.value.to_display_string()
        )
    }

    fn __hash__(&self) -> u64 {
        use std::hash::{Hash, Hasher};
        let mut h = std::collections::hash_map::DefaultHasher::new();
        let pt: PyTaskParameterType = self.inner.param_type.into();
        pt.as_str().hash(&mut h);
        self.inner.value.to_display_string().hash(&mut h);
        h.finish()
    }

    /// Pickle support — round-trips through ``__init__(*, type, value)``
    /// using the native Python value (``item()``) so the inner
    /// ``ExprValue`` type is preserved across pickle.
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
        let pt: PyTaskParameterType = self.inner.param_type.into();
        kwargs.set_item("type", pt)?;
        kwargs.set_item("value", expr_value_to_py(py, &self.inner.value)?)?;
        let args = PyTuple::new(py, [cls.into_any(), kwargs.into_any()])?;
        Ok((helper, args.into()))
    }
}

// ── JobParameterValue ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.types",
    name = "JobParameterValue",
    frozen,
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyJobParameterValue {
    pub(crate) inner: JobParameterValue,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyJobParameterValue {
    /// Construct a ``JobParameterValue``.
    ///
    /// ``value`` accepts any Python type that ``ExprValue`` accepts:
    /// ``str``, ``int``, ``float``, ``bool``, ``Decimal``, ``list``,
    /// ``ExprValue``, ``RangeExpr``. The ``param_type`` is recorded
    /// as-is — coercion to the target type happens later when the
    /// value flows into ``Session`` / ``create_job``. To match the
    /// pre-binding behaviour, no validation against ``param_type``
    /// is done here.
    #[new]
    #[pyo3(signature = (*, r#type, value))]
    fn new(r#type: PyJobParameterType, value: &Bound<'_, PyAny>) -> PyResult<Self> {
        let expr_value = py_to_expr_value(value)?;
        Ok(Self {
            inner: JobParameterValue {
                param_type: r#type.into(),
                value: expr_value,
            },
        })
    }

    #[getter(r#type)]
    fn get_type(&self) -> PyJobParameterType {
        self.inner.param_type.into()
    }

    /// Canonical string form of the value. Matches the v0 reference's
    /// dataclass-of-strings shape (``"42"``, ``"true"``, ``"[1, 2, 3]"``)
    /// and pre-reshape binding behaviour. For the native Python value,
    /// use ``item()``.
    #[getter]
    fn value(&self) -> String {
        self.inner.value.to_display_string()
    }

    /// Native Python value backing this ``JobParameterValue``.
    /// Mirrors ``ExprValue.item()`` — returns ``int`` for INT,
    /// ``list`` for LIST_*, etc.
    fn item(&self, py: Python<'_>) -> PyResult<Py<pyo3::PyAny>> {
        expr_value_to_py(py, &self.inner.value)
    }

    fn as_str(&self) -> &'static str {
        let pt: PyJobParameterType = self.inner.param_type.into();
        pt.as_str()
    }

    fn __eq__(&self, other: &Bound<'_, pyo3::PyAny>) -> PyResult<bool> {
        let other_type = other.getattr("type")?;
        let other_type_str: String = other_type.call_method0("as_str")?.extract()?;
        let other_value: String = other.getattr("value")?.extract()?;
        let self_type: PyJobParameterType = self.inner.param_type.into();
        Ok(self_type.as_str() == other_type_str
            && self.inner.value.to_display_string() == other_value)
    }

    fn __repr__(&self) -> String {
        let pt: PyJobParameterType = self.inner.param_type.into();
        format!(
            "JobParameterValue(type={}, value={:?})",
            pt.as_str(),
            self.inner.value.to_display_string()
        )
    }

    fn __hash__(&self) -> u64 {
        use std::hash::{Hash, Hasher};
        let mut h = std::collections::hash_map::DefaultHasher::new();
        let pt: PyJobParameterType = self.inner.param_type.into();
        pt.as_str().hash(&mut h);
        self.inner.value.to_display_string().hash(&mut h);
        h.finish()
    }

    /// Pickle support — round-trips through ``__init__(*, type, value)``
    /// using the native Python value (``item()``) so the inner
    /// ``ExprValue`` type is preserved across pickle.
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
        let pt: PyJobParameterType = self.inner.param_type.into();
        kwargs.set_item("type", pt)?;
        kwargs.set_item("value", expr_value_to_py(py, &self.inner.value)?)?;
        let args = PyTuple::new(py, [cls.into_any(), kwargs.into_any()])?;
        Ok((helper, args.into()))
    }
}
