// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

//! Template-time `userInterface` pyclasses.
//!
//! Mirror the 11 `*UserInterface` Rust struct types in
//! `openjd_model::template`, plus `FileFilter`. Returned by the
//! `user_interface` getter on each `Job*ParameterDefinition` pyclass.
//!
//! All UI types share three common fields (`control`, `label`,
//! `group_label`) plus type-specific extras:
//!
//! * `IntUserInterface` / `ListIntUserInterface` —
//!   `single_step_delta: Optional[int]`
//! * `FloatUserInterface` / `ListFloatUserInterface` —
//!   `decimals: Optional[int]`,
//!   `single_step_delta: Optional[float]`
//! * `PathUserInterface` / `ListPathUserInterface` —
//!   `file_filters: Optional[list[FileFilter]]`,
//!   `file_filter_default: Optional[FileFilter]`
//! * `StringUserInterface`, `BoolUserInterface`,
//!   `RangeExprUserInterface`, `ListSimpleUserInterface`,
//!   `HiddenOnlyUserInterface` — common only

use pyo3::prelude::*;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_model::template::{
    BoolUserInterface, FileFilter, FloatUserInterface, HiddenOnlyUserInterface, IntUserInterface,
    ListFloatUserInterface, ListIntUserInterface, ListPathUserInterface, ListSimpleUserInterface,
    PathUserInterface, RangeExprUserInterface, StringUserInterface,
};

// ── FileFilter ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "FileFilter",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyFileFilter {
    pub(crate) inner: FileFilter,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyFileFilter {
    #[getter]
    fn label(&self) -> &str {
        &self.inner.label
    }

    #[getter]
    fn patterns(&self) -> Vec<String> {
        self.inner.patterns.clone()
    }

    fn __repr__(&self) -> String {
        format!(
            "FileFilter(label={:?}, patterns={:?})",
            self.inner.label, self.inner.patterns
        )
    }
}

// ── StringUserInterface (common-only) ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "StringUserInterface",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyStringUserInterface {
    pub(crate) inner: StringUserInterface,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyStringUserInterface {
    #[getter]
    fn control(&self) -> Option<&str> {
        self.inner.control.as_deref()
    }

    #[getter]
    fn label(&self) -> Option<&str> {
        self.inner.label.as_deref()
    }

    #[getter]
    fn group_label(&self) -> Option<&str> {
        self.inner.group_label.as_deref()
    }

    #[getter]
    #[pyo3(name = "groupLabel")]
    fn group_label_camel(&self) -> Option<&str> {
        self.group_label()
    }

    fn __repr__(&self) -> String {
        "StringUserInterface(...)".to_string()
    }
}

// ── BoolUserInterface (common-only) ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "BoolUserInterface",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyBoolUserInterface {
    pub(crate) inner: BoolUserInterface,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyBoolUserInterface {
    #[getter]
    fn control(&self) -> Option<&str> {
        self.inner.control.as_deref()
    }

    #[getter]
    fn label(&self) -> Option<&str> {
        self.inner.label.as_deref()
    }

    #[getter]
    fn group_label(&self) -> Option<&str> {
        self.inner.group_label.as_deref()
    }

    #[getter]
    #[pyo3(name = "groupLabel")]
    fn group_label_camel(&self) -> Option<&str> {
        self.group_label()
    }

    fn __repr__(&self) -> String {
        "BoolUserInterface(...)".to_string()
    }
}

// ── RangeExprUserInterface (common-only) ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "RangeExprUserInterface",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyRangeExprUserInterface {
    pub(crate) inner: RangeExprUserInterface,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyRangeExprUserInterface {
    #[getter]
    fn control(&self) -> Option<&str> {
        self.inner.control.as_deref()
    }

    #[getter]
    fn label(&self) -> Option<&str> {
        self.inner.label.as_deref()
    }

    #[getter]
    fn group_label(&self) -> Option<&str> {
        self.inner.group_label.as_deref()
    }

    #[getter]
    #[pyo3(name = "groupLabel")]
    fn group_label_camel(&self) -> Option<&str> {
        self.group_label()
    }

    fn __repr__(&self) -> String {
        "RangeExprUserInterface(...)".to_string()
    }
}

// ── ListSimpleUserInterface (common-only — used by LIST[STRING], LIST[BOOL]) ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "ListSimpleUserInterface",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyListSimpleUserInterface {
    pub(crate) inner: ListSimpleUserInterface,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyListSimpleUserInterface {
    #[getter]
    fn control(&self) -> Option<&str> {
        self.inner.control.as_deref()
    }

    #[getter]
    fn label(&self) -> Option<&str> {
        self.inner.label.as_deref()
    }

    #[getter]
    fn group_label(&self) -> Option<&str> {
        self.inner.group_label.as_deref()
    }

    #[getter]
    #[pyo3(name = "groupLabel")]
    fn group_label_camel(&self) -> Option<&str> {
        self.group_label()
    }

    fn __repr__(&self) -> String {
        "ListSimpleUserInterface(...)".to_string()
    }
}

// ── HiddenOnlyUserInterface (common-only — used by LIST[LIST[INT]]) ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "HiddenOnlyUserInterface",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyHiddenOnlyUserInterface {
    pub(crate) inner: HiddenOnlyUserInterface,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyHiddenOnlyUserInterface {
    #[getter]
    fn control(&self) -> Option<&str> {
        self.inner.control.as_deref()
    }

    #[getter]
    fn label(&self) -> Option<&str> {
        self.inner.label.as_deref()
    }

    #[getter]
    fn group_label(&self) -> Option<&str> {
        self.inner.group_label.as_deref()
    }

    #[getter]
    #[pyo3(name = "groupLabel")]
    fn group_label_camel(&self) -> Option<&str> {
        self.group_label()
    }

    fn __repr__(&self) -> String {
        "HiddenOnlyUserInterface(...)".to_string()
    }
}

// ── IntUserInterface (single_step_delta) ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "IntUserInterface",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyIntUserInterface {
    pub(crate) inner: IntUserInterface,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyIntUserInterface {
    #[getter]
    fn control(&self) -> Option<&str> {
        self.inner.control.as_deref()
    }

    #[getter]
    fn label(&self) -> Option<&str> {
        self.inner.label.as_deref()
    }

    #[getter]
    fn group_label(&self) -> Option<&str> {
        self.inner.group_label.as_deref()
    }

    #[getter]
    #[pyo3(name = "groupLabel")]
    fn group_label_camel(&self) -> Option<&str> {
        self.group_label()
    }

    #[getter]
    fn single_step_delta(&self) -> Option<i64> {
        self.inner.single_step_delta.as_ref().map(|f| f.0)
    }

    #[getter]
    #[pyo3(name = "singleStepDelta")]
    fn single_step_delta_camel(&self) -> Option<i64> {
        self.single_step_delta()
    }

    fn __repr__(&self) -> String {
        "IntUserInterface(...)".to_string()
    }
}

// ── ListIntUserInterface (single_step_delta) ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "ListIntUserInterface",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyListIntUserInterface {
    pub(crate) inner: ListIntUserInterface,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyListIntUserInterface {
    #[getter]
    fn control(&self) -> Option<&str> {
        self.inner.control.as_deref()
    }

    #[getter]
    fn label(&self) -> Option<&str> {
        self.inner.label.as_deref()
    }

    #[getter]
    fn group_label(&self) -> Option<&str> {
        self.inner.group_label.as_deref()
    }

    #[getter]
    #[pyo3(name = "groupLabel")]
    fn group_label_camel(&self) -> Option<&str> {
        self.group_label()
    }

    #[getter]
    fn single_step_delta(&self) -> Option<i64> {
        self.inner.single_step_delta.as_ref().map(|f| f.0)
    }

    #[getter]
    #[pyo3(name = "singleStepDelta")]
    fn single_step_delta_camel(&self) -> Option<i64> {
        self.single_step_delta()
    }

    fn __repr__(&self) -> String {
        "ListIntUserInterface(...)".to_string()
    }
}

// ── FloatUserInterface (decimals + single_step_delta) ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "FloatUserInterface",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyFloatUserInterface {
    pub(crate) inner: FloatUserInterface,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyFloatUserInterface {
    #[getter]
    fn control(&self) -> Option<&str> {
        self.inner.control.as_deref()
    }

    #[getter]
    fn label(&self) -> Option<&str> {
        self.inner.label.as_deref()
    }

    #[getter]
    fn group_label(&self) -> Option<&str> {
        self.inner.group_label.as_deref()
    }

    #[getter]
    #[pyo3(name = "groupLabel")]
    fn group_label_camel(&self) -> Option<&str> {
        self.group_label()
    }

    #[getter]
    fn decimals(&self) -> Option<i64> {
        self.inner.decimals.as_ref().map(|f| f.0)
    }

    #[getter]
    fn single_step_delta(&self) -> Option<f64> {
        self.inner.single_step_delta.as_ref().map(|f| f.0)
    }

    #[getter]
    #[pyo3(name = "singleStepDelta")]
    fn single_step_delta_camel(&self) -> Option<f64> {
        self.single_step_delta()
    }

    fn __repr__(&self) -> String {
        "FloatUserInterface(...)".to_string()
    }
}

// ── ListFloatUserInterface (decimals + single_step_delta) ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "ListFloatUserInterface",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyListFloatUserInterface {
    pub(crate) inner: ListFloatUserInterface,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyListFloatUserInterface {
    #[getter]
    fn control(&self) -> Option<&str> {
        self.inner.control.as_deref()
    }

    #[getter]
    fn label(&self) -> Option<&str> {
        self.inner.label.as_deref()
    }

    #[getter]
    fn group_label(&self) -> Option<&str> {
        self.inner.group_label.as_deref()
    }

    #[getter]
    #[pyo3(name = "groupLabel")]
    fn group_label_camel(&self) -> Option<&str> {
        self.group_label()
    }

    #[getter]
    fn decimals(&self) -> Option<i64> {
        self.inner.decimals.as_ref().map(|f| f.0)
    }

    #[getter]
    fn single_step_delta(&self) -> Option<f64> {
        self.inner.single_step_delta.as_ref().map(|f| f.0)
    }

    #[getter]
    #[pyo3(name = "singleStepDelta")]
    fn single_step_delta_camel(&self) -> Option<f64> {
        self.single_step_delta()
    }

    fn __repr__(&self) -> String {
        "ListFloatUserInterface(...)".to_string()
    }
}

// ── PathUserInterface (file_filters + file_filter_default) ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "PathUserInterface",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyPathUserInterface {
    pub(crate) inner: PathUserInterface,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyPathUserInterface {
    #[getter]
    fn control(&self) -> Option<&str> {
        self.inner.control.as_deref()
    }

    #[getter]
    fn label(&self) -> Option<&str> {
        self.inner.label.as_deref()
    }

    #[getter]
    fn group_label(&self) -> Option<&str> {
        self.inner.group_label.as_deref()
    }

    #[getter]
    #[pyo3(name = "groupLabel")]
    fn group_label_camel(&self) -> Option<&str> {
        self.group_label()
    }

    #[getter]
    fn file_filters(&self) -> Option<Vec<PyFileFilter>> {
        self.inner.file_filters.as_ref().map(|v| {
            v.iter()
                .map(|ff| PyFileFilter { inner: ff.clone() })
                .collect()
        })
    }

    #[getter]
    #[pyo3(name = "fileFilters")]
    fn file_filters_camel(&self) -> Option<Vec<PyFileFilter>> {
        self.file_filters()
    }

    #[getter]
    fn file_filter_default(&self) -> Option<PyFileFilter> {
        self.inner
            .file_filter_default
            .as_ref()
            .map(|ff| PyFileFilter { inner: ff.clone() })
    }

    #[getter]
    #[pyo3(name = "fileFilterDefault")]
    fn file_filter_default_camel(&self) -> Option<PyFileFilter> {
        self.file_filter_default()
    }

    fn __repr__(&self) -> String {
        "PathUserInterface(...)".to_string()
    }
}

// ── ListPathUserInterface (file_filters + file_filter_default) ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "ListPathUserInterface",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyListPathUserInterface {
    pub(crate) inner: ListPathUserInterface,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyListPathUserInterface {
    #[getter]
    fn control(&self) -> Option<&str> {
        self.inner.control.as_deref()
    }

    #[getter]
    fn label(&self) -> Option<&str> {
        self.inner.label.as_deref()
    }

    #[getter]
    fn group_label(&self) -> Option<&str> {
        self.inner.group_label.as_deref()
    }

    #[getter]
    #[pyo3(name = "groupLabel")]
    fn group_label_camel(&self) -> Option<&str> {
        self.group_label()
    }

    #[getter]
    fn file_filters(&self) -> Option<Vec<PyFileFilter>> {
        self.inner.file_filters.as_ref().map(|v| {
            v.iter()
                .map(|ff| PyFileFilter { inner: ff.clone() })
                .collect()
        })
    }

    #[getter]
    #[pyo3(name = "fileFilters")]
    fn file_filters_camel(&self) -> Option<Vec<PyFileFilter>> {
        self.file_filters()
    }

    #[getter]
    fn file_filter_default(&self) -> Option<PyFileFilter> {
        self.inner
            .file_filter_default
            .as_ref()
            .map(|ff| PyFileFilter { inner: ff.clone() })
    }

    #[getter]
    #[pyo3(name = "fileFilterDefault")]
    fn file_filter_default_camel(&self) -> Option<PyFileFilter> {
        self.file_filter_default()
    }

    fn __repr__(&self) -> String {
        "ListPathUserInterface(...)".to_string()
    }
}
