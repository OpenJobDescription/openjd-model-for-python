// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

//! Python bindings for `openjd_model`'s profile types:
//! `SpecificationRevision`, `ModelExtension`, `ModelProfile`,
//! `CallerLimits`, and `ValidationContext`.
//!
//! These mirror the Rust crate API one-to-one. They replace the
//! earlier ad-hoc `supported_extensions: list[str]` kwarg on
//! `decode_*_template` and `create_job` — callers now build a
//! `ModelProfile` and pass it through.

use std::collections::HashSet;

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyType};
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_model::types::{
    CallerLimits, Extensions, ModelExtension, ModelProfile, SpecificationRevision,
    ValidationContext,
};

use crate::expr::profile::{PyExprProfile, PyHostContext};

// ── SpecificationRevision ─────────────────────────────────────────

/// Revision of the OpenJD specification.
///
/// Mirrors `openjd_model::types::SpecificationRevision`. Marked
/// `#[non_exhaustive]` in Rust so future revisions can be added
/// without a SemVer break; the Python enum has the same growth path.
///
/// On the Python side, the variant is exposed as
/// `SpecificationRevision.v2023_09` (matching the v0 Pydantic
/// model's lowercase-`v` `str`-Enum naming) and compares equal to
/// the spec-form string `"2023-09"`. ``rev.value`` returns the
/// spec-form string. The class is *not* a `str` subclass, so
/// `isinstance(rev, str)` returns `False` — for code that needs a
/// string, call `str(rev)` or `rev.value`.
#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyclass_enum(module = "openjd._openjd_rs")
)]
#[pyclass(
    module = "openjd._openjd_rs",
    name = "SpecificationRevision",
    frozen,
    from_py_object
)]
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
pub(crate) enum PySpecificationRevision {
    #[pyo3(name = "v2023_09")]
    V2023_09 = 0,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PySpecificationRevision {
    fn __repr__(&self) -> &'static str {
        match self {
            PySpecificationRevision::V2023_09 => "SpecificationRevision.v2023_09",
        }
    }

    /// Spec-form revision string, e.g. `"2023-09"`.
    fn __str__(&self) -> &'static str {
        self.value()
    }

    /// Spec-form revision string. Mirrors the `.value` attribute of
    /// a Python `str`-`Enum` (e.g. ``rev.value == "2023-09"``).
    #[getter]
    fn value(&self) -> &'static str {
        match self {
            PySpecificationRevision::V2023_09 => "2023-09",
        }
    }

    /// Variant name as a string (e.g. `"v2023_09"`). Matches the
    /// Python-side variant name and the v0 `str`-Enum's `.name`.
    #[getter]
    fn name(&self) -> &'static str {
        match self {
            PySpecificationRevision::V2023_09 => "v2023_09",
        }
    }

    /// Equal to another ``SpecificationRevision`` of the same
    /// variant, or to the spec-form string (e.g. ``"2023-09"``).
    /// Returns ``NotImplemented`` for unrelated types so Python
    /// falls back to the right-hand operand's ``__eq__``.
    fn __eq__(&self, other: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
        use pyo3::IntoPyObjectExt;
        let py = other.py();
        if let Ok(o) = other.extract::<PySpecificationRevision>() {
            return (self == &o).into_py_any(py);
        }
        if let Ok(s) = other.extract::<String>() {
            return (self.value() == s).into_py_any(py);
        }
        Ok(py.NotImplemented())
    }

    fn __ne__(&self, other: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
        use pyo3::IntoPyObjectExt;
        let py = other.py();
        if let Ok(o) = other.extract::<PySpecificationRevision>() {
            return (self != &o).into_py_any(py);
        }
        if let Ok(s) = other.extract::<String>() {
            return (self.value() != s).into_py_any(py);
        }
        Ok(py.NotImplemented())
    }

    /// Hash by spec-form string so ``rev == "2023-09"`` and
    /// ``hash(rev) == hash("2023-09")`` agree (required for set /
    /// dict membership across the two types).
    fn __hash__(&self, py: Python<'_>) -> PyResult<isize> {
        self.value().into_pyobject(py)?.hash()
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

impl From<PySpecificationRevision> for SpecificationRevision {
    fn from(r: PySpecificationRevision) -> Self {
        match r {
            PySpecificationRevision::V2023_09 => SpecificationRevision::V2023_09,
        }
    }
}

impl From<SpecificationRevision> for PySpecificationRevision {
    fn from(r: SpecificationRevision) -> Self {
        match r {
            SpecificationRevision::V2023_09 => PySpecificationRevision::V2023_09,
            #[allow(unreachable_patterns)]
            _ => PySpecificationRevision::V2023_09,
        }
    }
}

// ── ModelExtension ─────────────────────────────────────────────────

/// Model-side extension recognized by the `2023_09` specification
/// revision.
///
/// Names match `openjd_model::types::ModelExtension` (which in turn
/// matches the canonical UPPER_SNAKE_CASE strings as they appear in
/// template YAML/JSON). The Python enum is `eq, eq_int` so that
/// `ModelExtension.EXPR == ModelExtension.EXPR` works in sets.
#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyclass_enum(module = "openjd._openjd_rs")
)]
#[pyclass(
    module = "openjd.model._v1.types",
    name = "ModelExtension",
    eq,
    eq_int,
    hash,
    frozen,
    from_py_object
)]
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
// Python-side UPPER_SNAKE_CASE naming convention; ``EXPR`` is a
// 4-letter acronym.
#[allow(non_camel_case_types, clippy::upper_case_acronyms)]
pub(crate) enum PyModelExtension {
    TASK_CHUNKING = 0,
    REDACTED_ENV_VARS = 1,
    FEATURE_BUNDLE_1 = 2,
    EXPR = 3,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyModelExtension {
    /// Spec-form extension name, e.g. `"EXPR"`.
    fn as_str(&self) -> &'static str {
        let r: ModelExtension = (*self).into();
        r.as_str()
    }

    fn __repr__(&self) -> String {
        format!("ModelExtension.{}", self.as_str())
    }

    fn __str__(&self) -> &'static str {
        self.as_str()
    }

    /// Parse an UPPER_SNAKE_CASE extension name into a
    /// `ModelExtension`. Returns `None` for unrecognized names.
    #[staticmethod]
    fn from_str(s: &str) -> Option<PyModelExtension> {
        use std::str::FromStr;
        ModelExtension::from_str(s).ok().map(Into::into)
    }

    /// Variant name as a string (e.g. `"EXPR"`). Equivalent to
    /// [`as_str()`](Self::as_str).
    #[getter]
    fn name(&self) -> &'static str {
        self.as_str()
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

impl From<PyModelExtension> for ModelExtension {
    fn from(e: PyModelExtension) -> Self {
        match e {
            PyModelExtension::TASK_CHUNKING => ModelExtension::TaskChunking,
            PyModelExtension::REDACTED_ENV_VARS => ModelExtension::RedactedEnvVars,
            PyModelExtension::FEATURE_BUNDLE_1 => ModelExtension::FeatureBundle1,
            PyModelExtension::EXPR => ModelExtension::Expr,
        }
    }
}

impl From<ModelExtension> for PyModelExtension {
    fn from(e: ModelExtension) -> Self {
        match e {
            ModelExtension::TaskChunking => PyModelExtension::TASK_CHUNKING,
            ModelExtension::RedactedEnvVars => PyModelExtension::REDACTED_ENV_VARS,
            ModelExtension::FeatureBundle1 => PyModelExtension::FEATURE_BUNDLE_1,
            ModelExtension::Expr => PyModelExtension::EXPR,
            #[allow(unreachable_patterns)]
            _ => PyModelExtension::EXPR,
        }
    }
}

// ── ModelProfile ───────────────────────────────────────────────────

/// Model-side profile: spec revision plus enabled extensions.
///
/// Mirrors `openjd_model::ModelProfile`. Pass to
/// [`decode_job_template(profile=...)`](crate::model::decode_job_template_str),
/// `decode_environment_template(profile=...)`, and
/// `create_job(profile=...)`.
///
/// Use [`to_expr_profile(host_context)`](Self::to_expr_profile) to
/// derive a matching `ExprProfile` for the expression engine.
#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.types",
    name = "ModelProfile",
    frozen,
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyModelProfile {
    pub(crate) inner: ModelProfile,
}

impl Default for PyModelProfile {
    /// Same default as the Python-callable ``ModelProfile()``
    /// constructor — the v2023_09 revision with no extensions.
    /// Rust callers in the bindings should use this rather than
    /// hardcoding the revision literal.
    fn default() -> Self {
        Self {
            inner: ModelProfile::new(SpecificationRevision::V2023_09),
        }
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyModelProfile {
    /// Build a profile for the given revision with the given extension set.
    ///
    /// `extensions` accepts `ModelExtension` values directly. To pass
    /// extension *strings* (e.g. `["EXPR", "TASK_CHUNKING"]`) use
    /// [`from_strings`](Self::from_strings).
    #[new]
    #[pyo3(signature = (revision=PySpecificationRevision::V2023_09, *, extensions=None))]
    fn new(revision: PySpecificationRevision, extensions: Option<Vec<PyModelExtension>>) -> Self {
        let mut profile = ModelProfile::new(revision.into());
        if let Some(exts) = extensions {
            let set: Extensions = exts.into_iter().map(Into::into).collect();
            profile = profile.with_extensions(set);
        }
        Self { inner: profile }
    }

    /// Build a profile from a list of extension *strings* (e.g. the
    /// strings that appear in a template's `extensions:` field).
    /// Unknown names are an error.
    #[classmethod]
    fn from_strings(
        _cls: &Bound<'_, PyType>,
        revision: PySpecificationRevision,
        extensions: Vec<String>,
    ) -> PyResult<Self> {
        use std::str::FromStr;
        let mut set: Extensions = HashSet::new();
        for s in extensions {
            let ext =
                ModelExtension::from_str(&s).map_err(pyo3::exceptions::PyValueError::new_err)?;
            set.insert(ext);
        }
        Ok(Self {
            inner: ModelProfile::new(revision.into()).with_extensions(set),
        })
    }

    /// Builder: return a new profile with the given extensions
    /// (replaces any existing set). Does not mutate `self`.
    fn with_extensions(&self, extensions: Vec<PyModelExtension>) -> Self {
        let set: Extensions = extensions.into_iter().map(Into::into).collect();
        Self {
            inner: self.inner.clone().with_extensions(set),
        }
    }

    /// The specification revision this profile targets.
    #[getter]
    fn revision(&self) -> PySpecificationRevision {
        self.inner.revision().into()
    }

    /// The set of enabled extensions, as a list.
    #[getter]
    fn extensions(&self) -> Vec<PyModelExtension> {
        self.inner
            .extensions()
            .iter()
            .copied()
            .map(Into::into)
            .collect()
    }

    /// Whether the given extension is enabled in this profile.
    fn has_extension(&self, ext: PyModelExtension) -> bool {
        self.inner.has_extension(ext.into())
    }

    /// Derive an [`ExprProfile`](crate::expr::PyExprProfile) matching this
    /// profile's revision and extensions, with the caller-specified
    /// [`HostContext`](crate::expr::PyHostContext).
    ///
    /// This is the bridge from the model layer to the expression engine:
    /// pass the result to `FunctionLibrary.for_profile(...)`.
    fn to_expr_profile(&self, host_context: &PyHostContext) -> PyExprProfile {
        let p = self.inner.to_expr_profile(host_context.inner.clone());
        PyExprProfile { inner: p }
    }

    fn __repr__(&self) -> String {
        let mut exts: Vec<&str> = self.inner.extensions().iter().map(|e| e.as_str()).collect();
        exts.sort_unstable();
        format!(
            "ModelProfile(revision={}, extensions=[{}])",
            match self.inner.revision() {
                SpecificationRevision::V2023_09 => "V2023_09",
                #[allow(unreachable_patterns)]
                _ => "<unknown>",
            },
            exts.join(", "),
        )
    }

    /// Pickle support — round-trips through `__init__(revision,
    /// extensions=...)`.
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
        kwargs.set_item(
            "revision",
            PySpecificationRevision::from(self.inner.revision()),
        )?;
        let exts: Vec<PyModelExtension> = self
            .inner
            .extensions()
            .iter()
            .copied()
            .map(Into::into)
            .collect();
        kwargs.set_item("extensions", exts)?;
        let args = PyTuple::new(py, [cls.into_any(), kwargs.into_any()])?;
        Ok((helper, args.into()))
    }

    /// Structural equality. Two profiles are equal iff they share the
    /// same revision and the same set of extensions. Required by the
    /// pickle round-trip contract documented in
    /// `specs/python-model-interface.md` ("Pickle Support") — a
    /// loaded profile must compare equal to the original. The
    /// underlying `ModelProfile` upstream doesn't derive
    /// `PartialEq` (its `extensions` field is a `HashSet`), so we
    /// implement equality field-by-field at the binding boundary.
    fn __eq__(&self, other: &Self) -> bool {
        self.inner.revision() == other.inner.revision()
            && self.inner.extensions() == other.inner.extensions()
    }
}

// ── CallerLimits ───────────────────────────────────────────────────

/// Caller-supplied limits beyond what the OpenJD spec defines.
///
/// All fields are optional; `None` means "no additional restriction
/// beyond the spec-defined limit." Caller limits can only tighten
/// spec-defined limits, never relax them.
///
/// Mirrors `openjd_model::CallerLimits`.
#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.types",
    name = "CallerLimits",
    frozen,
    from_py_object
)]
#[derive(Clone, Default)]
pub(crate) struct PyCallerLimits {
    pub(crate) inner: CallerLimits,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyCallerLimits {
    #[new]
    #[pyo3(signature = (
        *,
        max_step_count=None,
        max_env_count=None,
        max_task_count=None,
        max_step_script_size=None,
        max_environment_size=None,
        max_template_size=None,
    ))]
    fn new(
        max_step_count: Option<usize>,
        max_env_count: Option<usize>,
        max_task_count: Option<u64>,
        max_step_script_size: Option<usize>,
        max_environment_size: Option<usize>,
        max_template_size: Option<usize>,
    ) -> Self {
        Self {
            inner: CallerLimits {
                max_step_count,
                max_env_count,
                max_task_count,
                max_step_script_size,
                max_environment_size,
                max_template_size,
            },
        }
    }

    #[getter]
    fn max_step_count(&self) -> Option<usize> {
        self.inner.max_step_count
    }
    #[getter]
    fn max_env_count(&self) -> Option<usize> {
        self.inner.max_env_count
    }
    #[getter]
    fn max_task_count(&self) -> Option<u64> {
        self.inner.max_task_count
    }
    #[getter]
    fn max_step_script_size(&self) -> Option<usize> {
        self.inner.max_step_script_size
    }
    #[getter]
    fn max_environment_size(&self) -> Option<usize> {
        self.inner.max_environment_size
    }
    #[getter]
    fn max_template_size(&self) -> Option<usize> {
        self.inner.max_template_size
    }

    fn __repr__(&self) -> String {
        format!(
            "CallerLimits(max_step_count={:?}, max_env_count={:?}, max_task_count={:?}, \
             max_step_script_size={:?}, max_environment_size={:?}, max_template_size={:?})",
            self.inner.max_step_count,
            self.inner.max_env_count,
            self.inner.max_task_count,
            self.inner.max_step_script_size,
            self.inner.max_environment_size,
            self.inner.max_template_size,
        )
    }

    /// Pickle support — round-trips through `__init__` with all six
    /// optional fields as keyword arguments.
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
        kwargs.set_item("max_step_count", self.inner.max_step_count)?;
        kwargs.set_item("max_env_count", self.inner.max_env_count)?;
        kwargs.set_item("max_task_count", self.inner.max_task_count)?;
        kwargs.set_item("max_step_script_size", self.inner.max_step_script_size)?;
        kwargs.set_item("max_environment_size", self.inner.max_environment_size)?;
        kwargs.set_item("max_template_size", self.inner.max_template_size)?;
        let args = PyTuple::new(py, [cls.into_any(), kwargs.into_any()])?;
        Ok((helper, args.into()))
    }

    /// Structural equality — required by the pickle round-trip
    /// contract. Compares all six fields; the underlying
    /// `CallerLimits` upstream doesn't derive `PartialEq`, so we
    /// implement equality field-by-field at the binding boundary.
    fn __eq__(&self, other: &Self) -> bool {
        self.inner.max_step_count == other.inner.max_step_count
            && self.inner.max_env_count == other.inner.max_env_count
            && self.inner.max_task_count == other.inner.max_task_count
            && self.inner.max_step_script_size == other.inner.max_step_script_size
            && self.inner.max_environment_size == other.inner.max_environment_size
            && self.inner.max_template_size == other.inner.max_template_size
    }
}

// ── ValidationContext ──────────────────────────────────────────────

/// A `ModelProfile` plus `CallerLimits`, bundled together.
///
/// Most callers can construct one directly from a `ModelProfile`, or
/// derive one from a parsed template via `JobTemplate.profile`.
///
/// Mirrors `openjd_model::types::ValidationContext`.
#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.types",
    name = "ValidationContext",
    frozen,
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyValidationContext {
    pub(crate) inner: ValidationContext,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyValidationContext {
    /// Build a context from a profile, with optional caller limits.
    #[new]
    #[pyo3(signature = (profile, *, caller_limits=None))]
    fn new(profile: &PyModelProfile, caller_limits: Option<&PyCallerLimits>) -> Self {
        let limits = caller_limits.map(|c| c.inner.clone()).unwrap_or_default();
        Self {
            inner: ValidationContext::from_profile(profile.inner.clone())
                .with_caller_limits(limits),
        }
    }

    #[getter]
    fn profile(&self) -> PyModelProfile {
        PyModelProfile {
            inner: self.inner.profile.clone(),
        }
    }

    #[getter]
    fn caller_limits(&self) -> PyCallerLimits {
        PyCallerLimits {
            inner: self.inner.caller_limits.clone(),
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "ValidationContext(profile={}, caller_limits={})",
            PyModelProfile {
                inner: self.inner.profile.clone()
            }
            .__repr__(),
            PyCallerLimits {
                inner: self.inner.caller_limits.clone()
            }
            .__repr__(),
        )
    }

    /// Pickle support — round-trips through `__init__(profile,
    /// caller_limits=...)`.
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
        kwargs.set_item(
            "profile",
            PyModelProfile {
                inner: self.inner.profile.clone(),
            },
        )?;
        kwargs.set_item(
            "caller_limits",
            PyCallerLimits {
                inner: self.inner.caller_limits.clone(),
            },
        )?;
        let args = PyTuple::new(py, [cls.into_any(), kwargs.into_any()])?;
        Ok((helper, args.into()))
    }

    /// Structural equality — required by the pickle round-trip
    /// contract. A context is equal to another iff both its
    /// `profile` and its `caller_limits` are equal. Composes the
    /// per-component `__eq__` we just added on `PyModelProfile` and
    /// `PyCallerLimits`.
    fn __eq__(&self, other: &Self) -> bool {
        let p_self = PyModelProfile {
            inner: self.inner.profile.clone(),
        };
        let p_other = PyModelProfile {
            inner: other.inner.profile.clone(),
        };
        let cl_self = PyCallerLimits {
            inner: self.inner.caller_limits.clone(),
        };
        let cl_other = PyCallerLimits {
            inner: other.inner.caller_limits.clone(),
        };
        p_self.__eq__(&p_other) && cl_self.__eq__(&cl_other)
    }
}
