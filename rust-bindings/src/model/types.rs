// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyType};
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_model::template::parse::DocumentType;
use openjd_model::JobParameterType;
use openjd_model::TemplateSpecificationVersion;

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
    #[pyo3(get)]
    pub(crate) param_type: PyTaskParameterType,
    #[pyo3(get)]
    pub(crate) value: String,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyTaskParameterValue {
    #[new]
    #[pyo3(signature = (*, r#type, value))]
    fn new(r#type: PyTaskParameterType, value: String) -> Self {
        Self {
            param_type: r#type,
            value,
        }
    }

    #[getter(r#type)]
    fn get_type(&self) -> PyTaskParameterType {
        self.param_type
    }

    fn as_str(&self) -> &str {
        self.param_type.as_str()
    }

    fn __eq__(&self, other: &Bound<'_, pyo3::PyAny>) -> PyResult<bool> {
        let other_type = other.getattr("type")?;
        let other_type_str: String = other_type.call_method0("as_str")?.extract()?;
        let other_value: String = other.getattr("value")?.extract()?;
        Ok(self.param_type.as_str() == other_type_str && self.value == other_value)
    }

    fn __repr__(&self) -> String {
        format!(
            "TaskParameterValue(type={}, value={:?})",
            self.param_type.as_str(),
            self.value
        )
    }

    fn __hash__(&self) -> u64 {
        use std::hash::{Hash, Hasher};
        let mut h = std::collections::hash_map::DefaultHasher::new();
        self.param_type.as_str().hash(&mut h);
        self.value.hash(&mut h);
        h.finish()
    }

    /// Pickle support — round-trips through `__init__(*, type, value)`.
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
        kwargs.set_item("type", self.param_type)?;
        kwargs.set_item("value", &self.value)?;
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
    #[pyo3(get)]
    pub(crate) param_type: PyJobParameterType,
    #[pyo3(get)]
    pub(crate) value: String,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyJobParameterValue {
    #[new]
    #[pyo3(signature = (*, r#type, value))]
    fn new(r#type: PyJobParameterType, value: String) -> Self {
        Self {
            param_type: r#type,
            value,
        }
    }

    #[getter(r#type)]
    fn get_type(&self) -> PyJobParameterType {
        self.param_type
    }

    fn as_str(&self) -> &str {
        self.param_type.as_str()
    }

    fn __eq__(&self, other: &Bound<'_, pyo3::PyAny>) -> PyResult<bool> {
        let other_type = other.getattr("type")?;
        let other_type_str: String = other_type.call_method0("as_str")?.extract()?;
        let other_value: String = other.getattr("value")?.extract()?;
        Ok(self.param_type.as_str() == other_type_str && self.value == other_value)
    }

    fn __repr__(&self) -> String {
        format!(
            "JobParameterValue(type={}, value={:?})",
            self.param_type.as_str(),
            self.value
        )
    }

    fn __hash__(&self) -> u64 {
        use std::hash::{Hash, Hasher};
        let mut h = std::collections::hash_map::DefaultHasher::new();
        self.param_type.as_str().hash(&mut h);
        self.value.hash(&mut h);
        h.finish()
    }

    /// Pickle support — round-trips through `__init__(*, type, value)`.
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
        kwargs.set_item("type", self.param_type)?;
        kwargs.set_item("value", &self.value)?;
        let args = PyTuple::new(py, [cls.into_any(), kwargs.into_any()])?;
        Ok((helper, args.into()))
    }
}
