// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

//! Template-time job-parameter pyclasses.
//!
//! Mirror the 12 variants of the
//! `openjd_model::template::JobParameterDefinition` enum 1:1:
//!
//! Base 4 (always available):
//! * `JobStringParameterDefinition`
//! * `JobIntParameterDefinition`
//! * `JobFloatParameterDefinition`
//! * `JobPathParameterDefinition`
//!
//! EXPR-extension 8 (require the `EXPR` extension to be enabled in
//! the template's `extensions:` list):
//! * `JobBoolParameterDefinition`
//! * `JobRangeExprParameterDefinition`
//! * `JobListStringParameterDefinition`
//! * `JobListPathParameterDefinition`
//! * `JobListIntParameterDefinition`
//! * `JobListFloatParameterDefinition`
//! * `JobListBoolParameterDefinition`
//! * `JobListListIntParameterDefinition`
//!
//! Each pyclass exposes the core surface — `name`, `description`,
//! `default`, plus type-specific constraints (`allowed_values`,
//! `min_length`/`max_length`, `min_value`/`max_value`, `object_type`,
//! `data_flow`, `item` constraints). The `user_interface` field is
//! not yet exposed (the `*UserInterface` Rust types are large and
//! warrant a follow-up commit); calling `.user_interface` returns
//! ``None`` for now.
//!
//! Pickle is supported via `_reconstruct_kwargs`. The dispatch
//! helper at the bottom of this file produces the right pyclass
//! variant from a `JobParameterDefinition` enum.

use pyo3::prelude::*;
use pyo3::types::PyList;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_model::template::{
    JobBoolParameterDefinition, JobFloatParameterDefinition, JobIntParameterDefinition,
    JobListBoolParameterDefinition, JobListFloatParameterDefinition, JobListIntParameterDefinition,
    JobListListIntParameterDefinition, JobListPathParameterDefinition,
    JobListStringParameterDefinition, JobParameterDefinition, JobPathParameterDefinition,
    JobRangeExprParameterDefinition, JobStringParameterDefinition,
};
use openjd_model::types::{DataFlow, JobParameterType, ObjectType};

use super::types::PyJobParameterType;
use super::user_interfaces::{
    PyBoolUserInterface, PyFloatUserInterface, PyHiddenOnlyUserInterface, PyIntUserInterface,
    PyListFloatUserInterface, PyListIntUserInterface, PyListPathUserInterface,
    PyListSimpleUserInterface, PyPathUserInterface, PyRangeExprUserInterface,
    PyStringUserInterface,
};

// ── Helpers ──

fn object_type_str(t: ObjectType) -> &'static str {
    match t {
        ObjectType::File => "FILE",
        ObjectType::Directory => "DIRECTORY",
    }
}

fn data_flow_str(d: DataFlow) -> &'static str {
    match d {
        DataFlow::None => "NONE",
        DataFlow::In => "IN",
        DataFlow::Out => "OUT",
        DataFlow::Inout => "INOUT",
    }
}

// ── JobStringParameterDefinition ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "JobStringParameterDefinition",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyJobStringParameterDefinition {
    pub(crate) inner: JobStringParameterDefinition,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyJobStringParameterDefinition {
    #[getter]
    fn r#type(&self) -> PyJobParameterType {
        PyJobParameterType::from(JobParameterType::String)
    }

    #[getter]
    fn name(&self) -> &str {
        self.inner.name.as_str()
    }

    #[getter]
    fn description(&self) -> Option<&str> {
        self.inner.description.as_ref().map(|d| d.0.as_str())
    }

    #[getter]
    fn default(&self) -> Option<&str> {
        self.inner.default.as_deref()
    }

    #[getter]
    fn allowed_values(&self) -> Option<Vec<String>> {
        self.inner.allowed_values.clone()
    }

    #[getter]
    #[pyo3(name = "allowedValues")]
    fn allowed_values_camel(&self) -> Option<Vec<String>> {
        self.allowed_values()
    }

    #[getter]
    fn min_length(&self) -> Option<usize> {
        self.inner.min_length
    }

    #[getter]
    #[pyo3(name = "minLength")]
    fn min_length_camel(&self) -> Option<usize> {
        self.min_length()
    }

    #[getter]
    fn max_length(&self) -> Option<usize> {
        self.inner.max_length
    }

    #[getter]
    #[pyo3(name = "maxLength")]
    fn max_length_camel(&self) -> Option<usize> {
        self.max_length()
    }

    fn __repr__(&self) -> String {
        format!(
            "JobStringParameterDefinition(name={:?})",
            self.inner.name.as_str()
        )
    }

    /// The optional `userInterface` block. Returns
    /// `Optional[StringUserInterface]` — see the type's spec for fields.
    #[getter]
    fn user_interface(&self) -> Option<PyStringUserInterface> {
        self.inner
            .user_interface
            .as_ref()
            .map(|ui| PyStringUserInterface { inner: ui.clone() })
    }

    #[getter]
    #[pyo3(name = "userInterface")]
    fn user_interface_camel(&self) -> Option<PyStringUserInterface> {
        self.user_interface()
    }
}

// ── JobIntParameterDefinition ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "JobIntParameterDefinition",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyJobIntParameterDefinition {
    pub(crate) inner: JobIntParameterDefinition,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyJobIntParameterDefinition {
    #[getter]
    fn r#type(&self) -> PyJobParameterType {
        PyJobParameterType::from(JobParameterType::Int)
    }

    #[getter]
    fn name(&self) -> &str {
        self.inner.name.as_str()
    }

    #[getter]
    fn description(&self) -> Option<&str> {
        self.inner.description.as_ref().map(|d| d.0.as_str())
    }

    #[getter]
    fn default(&self) -> Option<i64> {
        self.inner.default.as_ref().map(|f| f.0)
    }

    #[getter]
    fn allowed_values(&self) -> Option<Vec<i64>> {
        self.inner
            .allowed_values
            .as_ref()
            .map(|v| v.iter().map(|f| f.0).collect())
    }

    #[getter]
    #[pyo3(name = "allowedValues")]
    fn allowed_values_camel(&self) -> Option<Vec<i64>> {
        self.allowed_values()
    }

    #[getter]
    fn min_value(&self) -> Option<i64> {
        self.inner.min_value.as_ref().map(|f| f.0)
    }

    #[getter]
    #[pyo3(name = "minValue")]
    fn min_value_camel(&self) -> Option<i64> {
        self.min_value()
    }

    #[getter]
    fn max_value(&self) -> Option<i64> {
        self.inner.max_value.as_ref().map(|f| f.0)
    }

    #[getter]
    #[pyo3(name = "maxValue")]
    fn max_value_camel(&self) -> Option<i64> {
        self.max_value()
    }

    fn __repr__(&self) -> String {
        format!(
            "JobIntParameterDefinition(name={:?})",
            self.inner.name.as_str()
        )
    }

    #[getter]
    fn user_interface(&self) -> Option<PyIntUserInterface> {
        self.inner
            .user_interface
            .as_ref()
            .map(|ui| PyIntUserInterface { inner: ui.clone() })
    }

    #[getter]
    #[pyo3(name = "userInterface")]
    fn user_interface_camel(&self) -> Option<PyIntUserInterface> {
        self.user_interface()
    }
}

// ── JobFloatParameterDefinition ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "JobFloatParameterDefinition",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyJobFloatParameterDefinition {
    pub(crate) inner: JobFloatParameterDefinition,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyJobFloatParameterDefinition {
    #[getter]
    fn r#type(&self) -> PyJobParameterType {
        PyJobParameterType::from(JobParameterType::Float)
    }

    #[getter]
    fn name(&self) -> &str {
        self.inner.name.as_str()
    }

    #[getter]
    fn description(&self) -> Option<&str> {
        self.inner.description.as_ref().map(|d| d.0.as_str())
    }

    #[getter]
    fn default(&self) -> Option<f64> {
        self.inner.default.as_ref().map(|f| f.0)
    }

    #[getter]
    fn allowed_values(&self) -> Option<Vec<f64>> {
        self.inner
            .allowed_values
            .as_ref()
            .map(|v| v.iter().map(|f| f.0).collect())
    }

    #[getter]
    #[pyo3(name = "allowedValues")]
    fn allowed_values_camel(&self) -> Option<Vec<f64>> {
        self.allowed_values()
    }

    #[getter]
    fn min_value(&self) -> Option<f64> {
        self.inner.min_value.as_ref().map(|f| f.0)
    }

    #[getter]
    #[pyo3(name = "minValue")]
    fn min_value_camel(&self) -> Option<f64> {
        self.min_value()
    }

    #[getter]
    fn max_value(&self) -> Option<f64> {
        self.inner.max_value.as_ref().map(|f| f.0)
    }

    #[getter]
    #[pyo3(name = "maxValue")]
    fn max_value_camel(&self) -> Option<f64> {
        self.max_value()
    }

    fn __repr__(&self) -> String {
        format!(
            "JobFloatParameterDefinition(name={:?})",
            self.inner.name.as_str()
        )
    }

    #[getter]
    fn user_interface(&self) -> Option<PyFloatUserInterface> {
        self.inner
            .user_interface
            .as_ref()
            .map(|ui| PyFloatUserInterface { inner: ui.clone() })
    }

    #[getter]
    #[pyo3(name = "userInterface")]
    fn user_interface_camel(&self) -> Option<PyFloatUserInterface> {
        self.user_interface()
    }
}

// ── JobPathParameterDefinition ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "JobPathParameterDefinition",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyJobPathParameterDefinition {
    pub(crate) inner: JobPathParameterDefinition,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyJobPathParameterDefinition {
    #[getter]
    fn r#type(&self) -> PyJobParameterType {
        PyJobParameterType::from(JobParameterType::Path)
    }

    #[getter]
    fn name(&self) -> &str {
        self.inner.name.as_str()
    }

    #[getter]
    fn description(&self) -> Option<&str> {
        self.inner.description.as_ref().map(|d| d.0.as_str())
    }

    #[getter]
    fn default(&self) -> Option<&str> {
        self.inner.default.as_deref()
    }

    #[getter]
    fn allowed_values(&self) -> Option<Vec<String>> {
        self.inner.allowed_values.clone()
    }

    #[getter]
    #[pyo3(name = "allowedValues")]
    fn allowed_values_camel(&self) -> Option<Vec<String>> {
        self.allowed_values()
    }

    #[getter]
    fn min_length(&self) -> Option<usize> {
        self.inner.min_length
    }

    #[getter]
    #[pyo3(name = "minLength")]
    fn min_length_camel(&self) -> Option<usize> {
        self.min_length()
    }

    #[getter]
    fn max_length(&self) -> Option<usize> {
        self.inner.max_length
    }

    #[getter]
    #[pyo3(name = "maxLength")]
    fn max_length_camel(&self) -> Option<usize> {
        self.max_length()
    }

    #[getter]
    fn object_type(&self) -> Option<&'static str> {
        self.inner.object_type.map(object_type_str)
    }

    #[getter]
    #[pyo3(name = "objectType")]
    fn object_type_camel(&self) -> Option<&'static str> {
        self.object_type()
    }

    #[getter]
    fn data_flow(&self) -> Option<&'static str> {
        self.inner.data_flow.map(data_flow_str)
    }

    #[getter]
    #[pyo3(name = "dataFlow")]
    fn data_flow_camel(&self) -> Option<&'static str> {
        self.data_flow()
    }

    fn __repr__(&self) -> String {
        format!(
            "JobPathParameterDefinition(name={:?})",
            self.inner.name.as_str()
        )
    }

    #[getter]
    fn user_interface(&self) -> Option<PyPathUserInterface> {
        self.inner
            .user_interface
            .as_ref()
            .map(|ui| PyPathUserInterface { inner: ui.clone() })
    }

    #[getter]
    #[pyo3(name = "userInterface")]
    fn user_interface_camel(&self) -> Option<PyPathUserInterface> {
        self.user_interface()
    }
}

// ── JobBoolParameterDefinition (EXPR) ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "JobBoolParameterDefinition",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyJobBoolParameterDefinition {
    pub(crate) inner: JobBoolParameterDefinition,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyJobBoolParameterDefinition {
    #[getter]
    fn r#type(&self) -> PyJobParameterType {
        PyJobParameterType::from(JobParameterType::Bool)
    }

    #[getter]
    fn name(&self) -> &str {
        self.inner.name.as_str()
    }

    #[getter]
    fn description(&self) -> Option<&str> {
        self.inner.description.as_ref().map(|d| d.0.as_str())
    }

    #[getter]
    fn default(&self) -> Option<bool> {
        self.inner.default.as_ref().map(|b| b.0)
    }

    fn __repr__(&self) -> String {
        format!(
            "JobBoolParameterDefinition(name={:?})",
            self.inner.name.as_str()
        )
    }

    #[getter]
    fn user_interface(&self) -> Option<PyBoolUserInterface> {
        self.inner
            .user_interface
            .as_ref()
            .map(|ui| PyBoolUserInterface { inner: ui.clone() })
    }

    #[getter]
    #[pyo3(name = "userInterface")]
    fn user_interface_camel(&self) -> Option<PyBoolUserInterface> {
        self.user_interface()
    }
}

// ── JobRangeExprParameterDefinition (EXPR) ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "JobRangeExprParameterDefinition",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyJobRangeExprParameterDefinition {
    pub(crate) inner: JobRangeExprParameterDefinition,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyJobRangeExprParameterDefinition {
    #[getter]
    fn r#type(&self) -> PyJobParameterType {
        PyJobParameterType::from(JobParameterType::RangeExpr)
    }

    #[getter]
    fn name(&self) -> &str {
        self.inner.name.as_str()
    }

    #[getter]
    fn description(&self) -> Option<&str> {
        self.inner.description.as_ref().map(|d| d.0.as_str())
    }

    #[getter]
    fn default(&self) -> Option<&str> {
        self.inner.default.as_deref()
    }

    #[getter]
    fn min_length(&self) -> Option<usize> {
        self.inner.min_length
    }

    #[getter]
    #[pyo3(name = "minLength")]
    fn min_length_camel(&self) -> Option<usize> {
        self.min_length()
    }

    #[getter]
    fn max_length(&self) -> Option<usize> {
        self.inner.max_length
    }

    #[getter]
    #[pyo3(name = "maxLength")]
    fn max_length_camel(&self) -> Option<usize> {
        self.max_length()
    }

    fn __repr__(&self) -> String {
        format!(
            "JobRangeExprParameterDefinition(name={:?})",
            self.inner.name.as_str()
        )
    }

    #[getter]
    fn user_interface(&self) -> Option<PyRangeExprUserInterface> {
        self.inner
            .user_interface
            .as_ref()
            .map(|ui| PyRangeExprUserInterface { inner: ui.clone() })
    }

    #[getter]
    #[pyo3(name = "userInterface")]
    fn user_interface_camel(&self) -> Option<PyRangeExprUserInterface> {
        self.user_interface()
    }
}

// ── JobListStringParameterDefinition (EXPR) ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "JobListStringParameterDefinition",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyJobListStringParameterDefinition {
    pub(crate) inner: JobListStringParameterDefinition,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyJobListStringParameterDefinition {
    #[getter]
    fn r#type(&self) -> PyJobParameterType {
        PyJobParameterType::from(JobParameterType::ListString)
    }

    #[getter]
    fn name(&self) -> &str {
        self.inner.name.as_str()
    }

    #[getter]
    fn description(&self) -> Option<&str> {
        self.inner.description.as_ref().map(|d| d.0.as_str())
    }

    #[getter]
    fn default(&self) -> Option<Vec<String>> {
        self.inner.default.clone()
    }

    #[getter]
    fn min_length(&self) -> Option<usize> {
        self.inner.min_length
    }

    #[getter]
    #[pyo3(name = "minLength")]
    fn min_length_camel(&self) -> Option<usize> {
        self.min_length()
    }

    #[getter]
    fn max_length(&self) -> Option<usize> {
        self.inner.max_length
    }

    #[getter]
    #[pyo3(name = "maxLength")]
    fn max_length_camel(&self) -> Option<usize> {
        self.max_length()
    }

    fn __repr__(&self) -> String {
        format!(
            "JobListStringParameterDefinition(name={:?})",
            self.inner.name.as_str()
        )
    }

    #[getter]
    fn user_interface(&self) -> Option<PyListSimpleUserInterface> {
        self.inner
            .user_interface
            .as_ref()
            .map(|ui| PyListSimpleUserInterface { inner: ui.clone() })
    }

    #[getter]
    #[pyo3(name = "userInterface")]
    fn user_interface_camel(&self) -> Option<PyListSimpleUserInterface> {
        self.user_interface()
    }
}

// ── JobListPathParameterDefinition (EXPR) ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "JobListPathParameterDefinition",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyJobListPathParameterDefinition {
    pub(crate) inner: JobListPathParameterDefinition,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyJobListPathParameterDefinition {
    #[getter]
    fn r#type(&self) -> PyJobParameterType {
        PyJobParameterType::from(JobParameterType::ListPath)
    }

    #[getter]
    fn name(&self) -> &str {
        self.inner.name.as_str()
    }

    #[getter]
    fn description(&self) -> Option<&str> {
        self.inner.description.as_ref().map(|d| d.0.as_str())
    }

    #[getter]
    fn default(&self) -> Option<Vec<String>> {
        self.inner.default.clone()
    }

    #[getter]
    fn min_length(&self) -> Option<usize> {
        self.inner.min_length
    }

    #[getter]
    #[pyo3(name = "minLength")]
    fn min_length_camel(&self) -> Option<usize> {
        self.min_length()
    }

    #[getter]
    fn max_length(&self) -> Option<usize> {
        self.inner.max_length
    }

    #[getter]
    #[pyo3(name = "maxLength")]
    fn max_length_camel(&self) -> Option<usize> {
        self.max_length()
    }

    #[getter]
    fn object_type(&self) -> Option<&'static str> {
        self.inner.object_type.map(object_type_str)
    }

    #[getter]
    #[pyo3(name = "objectType")]
    fn object_type_camel(&self) -> Option<&'static str> {
        self.object_type()
    }

    #[getter]
    fn data_flow(&self) -> Option<&'static str> {
        self.inner.data_flow.map(data_flow_str)
    }

    #[getter]
    #[pyo3(name = "dataFlow")]
    fn data_flow_camel(&self) -> Option<&'static str> {
        self.data_flow()
    }

    fn __repr__(&self) -> String {
        format!(
            "JobListPathParameterDefinition(name={:?})",
            self.inner.name.as_str()
        )
    }

    #[getter]
    fn user_interface(&self) -> Option<PyListPathUserInterface> {
        self.inner
            .user_interface
            .as_ref()
            .map(|ui| PyListPathUserInterface { inner: ui.clone() })
    }

    #[getter]
    #[pyo3(name = "userInterface")]
    fn user_interface_camel(&self) -> Option<PyListPathUserInterface> {
        self.user_interface()
    }
}

// ── JobListIntParameterDefinition (EXPR) ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "JobListIntParameterDefinition",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyJobListIntParameterDefinition {
    pub(crate) inner: JobListIntParameterDefinition,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyJobListIntParameterDefinition {
    #[getter]
    fn r#type(&self) -> PyJobParameterType {
        PyJobParameterType::from(JobParameterType::ListInt)
    }

    #[getter]
    fn name(&self) -> &str {
        self.inner.name.as_str()
    }

    #[getter]
    fn description(&self) -> Option<&str> {
        self.inner.description.as_ref().map(|d| d.0.as_str())
    }

    #[getter]
    fn default(&self) -> Option<Vec<i64>> {
        self.inner
            .default
            .as_ref()
            .map(|v| v.iter().map(|f| f.0).collect())
    }

    #[getter]
    fn min_length(&self) -> Option<usize> {
        self.inner.min_length
    }

    #[getter]
    #[pyo3(name = "minLength")]
    fn min_length_camel(&self) -> Option<usize> {
        self.min_length()
    }

    #[getter]
    fn max_length(&self) -> Option<usize> {
        self.inner.max_length
    }

    #[getter]
    #[pyo3(name = "maxLength")]
    fn max_length_camel(&self) -> Option<usize> {
        self.max_length()
    }

    fn __repr__(&self) -> String {
        format!(
            "JobListIntParameterDefinition(name={:?})",
            self.inner.name.as_str()
        )
    }

    #[getter]
    fn user_interface(&self) -> Option<PyListIntUserInterface> {
        self.inner
            .user_interface
            .as_ref()
            .map(|ui| PyListIntUserInterface { inner: ui.clone() })
    }

    #[getter]
    #[pyo3(name = "userInterface")]
    fn user_interface_camel(&self) -> Option<PyListIntUserInterface> {
        self.user_interface()
    }
}

// ── JobListFloatParameterDefinition (EXPR) ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "JobListFloatParameterDefinition",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyJobListFloatParameterDefinition {
    pub(crate) inner: JobListFloatParameterDefinition,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyJobListFloatParameterDefinition {
    #[getter]
    fn r#type(&self) -> PyJobParameterType {
        PyJobParameterType::from(JobParameterType::ListFloat)
    }

    #[getter]
    fn name(&self) -> &str {
        self.inner.name.as_str()
    }

    #[getter]
    fn description(&self) -> Option<&str> {
        self.inner.description.as_ref().map(|d| d.0.as_str())
    }

    #[getter]
    fn default(&self) -> Option<Vec<f64>> {
        self.inner
            .default
            .as_ref()
            .map(|v| v.iter().map(|f| f.0).collect())
    }

    #[getter]
    fn min_length(&self) -> Option<usize> {
        self.inner.min_length
    }

    #[getter]
    #[pyo3(name = "minLength")]
    fn min_length_camel(&self) -> Option<usize> {
        self.min_length()
    }

    #[getter]
    fn max_length(&self) -> Option<usize> {
        self.inner.max_length
    }

    #[getter]
    #[pyo3(name = "maxLength")]
    fn max_length_camel(&self) -> Option<usize> {
        self.max_length()
    }

    fn __repr__(&self) -> String {
        format!(
            "JobListFloatParameterDefinition(name={:?})",
            self.inner.name.as_str()
        )
    }

    #[getter]
    fn user_interface(&self) -> Option<PyListFloatUserInterface> {
        self.inner
            .user_interface
            .as_ref()
            .map(|ui| PyListFloatUserInterface { inner: ui.clone() })
    }

    #[getter]
    #[pyo3(name = "userInterface")]
    fn user_interface_camel(&self) -> Option<PyListFloatUserInterface> {
        self.user_interface()
    }
}

// ── JobListBoolParameterDefinition (EXPR) ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "JobListBoolParameterDefinition",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyJobListBoolParameterDefinition {
    pub(crate) inner: JobListBoolParameterDefinition,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyJobListBoolParameterDefinition {
    #[getter]
    fn r#type(&self) -> PyJobParameterType {
        PyJobParameterType::from(JobParameterType::ListBool)
    }

    #[getter]
    fn name(&self) -> &str {
        self.inner.name.as_str()
    }

    #[getter]
    fn description(&self) -> Option<&str> {
        self.inner.description.as_ref().map(|d| d.0.as_str())
    }

    #[getter]
    fn default(&self) -> Option<Vec<bool>> {
        self.inner
            .default
            .as_ref()
            .map(|v| v.iter().map(|b| b.0).collect())
    }

    #[getter]
    fn min_length(&self) -> Option<usize> {
        self.inner.min_length
    }

    #[getter]
    #[pyo3(name = "minLength")]
    fn min_length_camel(&self) -> Option<usize> {
        self.min_length()
    }

    #[getter]
    fn max_length(&self) -> Option<usize> {
        self.inner.max_length
    }

    #[getter]
    #[pyo3(name = "maxLength")]
    fn max_length_camel(&self) -> Option<usize> {
        self.max_length()
    }

    fn __repr__(&self) -> String {
        format!(
            "JobListBoolParameterDefinition(name={:?})",
            self.inner.name.as_str()
        )
    }

    #[getter]
    fn user_interface(&self) -> Option<PyListSimpleUserInterface> {
        self.inner
            .user_interface
            .as_ref()
            .map(|ui| PyListSimpleUserInterface { inner: ui.clone() })
    }

    #[getter]
    #[pyo3(name = "userInterface")]
    fn user_interface_camel(&self) -> Option<PyListSimpleUserInterface> {
        self.user_interface()
    }
}

// ── JobListListIntParameterDefinition (EXPR) ──

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.template",
    name = "JobListListIntParameterDefinition",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyJobListListIntParameterDefinition {
    pub(crate) inner: JobListListIntParameterDefinition,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyJobListListIntParameterDefinition {
    #[getter]
    fn r#type(&self) -> PyJobParameterType {
        PyJobParameterType::from(JobParameterType::ListListInt)
    }

    #[getter]
    fn name(&self) -> &str {
        self.inner.name.as_str()
    }

    #[getter]
    fn description(&self) -> Option<&str> {
        self.inner.description.as_ref().map(|d| d.0.as_str())
    }

    #[getter]
    fn default(&self) -> Option<Vec<Vec<i64>>> {
        self.inner.default.as_ref().map(|v| {
            v.iter()
                .map(|inner| inner.iter().map(|f| f.0).collect())
                .collect()
        })
    }

    #[getter]
    fn min_length(&self) -> Option<usize> {
        self.inner.min_length
    }

    #[getter]
    #[pyo3(name = "minLength")]
    fn min_length_camel(&self) -> Option<usize> {
        self.min_length()
    }

    #[getter]
    fn max_length(&self) -> Option<usize> {
        self.inner.max_length
    }

    #[getter]
    #[pyo3(name = "maxLength")]
    fn max_length_camel(&self) -> Option<usize> {
        self.max_length()
    }

    fn __repr__(&self) -> String {
        format!(
            "JobListListIntParameterDefinition(name={:?})",
            self.inner.name.as_str()
        )
    }

    #[getter]
    fn user_interface(&self) -> Option<PyHiddenOnlyUserInterface> {
        self.inner
            .user_interface
            .as_ref()
            .map(|ui| PyHiddenOnlyUserInterface { inner: ui.clone() })
    }

    #[getter]
    #[pyo3(name = "userInterface")]
    fn user_interface_camel(&self) -> Option<PyHiddenOnlyUserInterface> {
        self.user_interface()
    }
}

// ── Dispatch ──

/// Convert a `JobParameterDefinition` enum value into the appropriate
/// pyclass instance, returning a Python object.
pub(crate) fn job_param_def_to_py<'py>(
    py: Python<'py>,
    def: &JobParameterDefinition,
) -> PyResult<Bound<'py, PyAny>> {
    match def {
        JobParameterDefinition::STRING(p) => {
            Bound::new(py, PyJobStringParameterDefinition { inner: p.clone() })
                .map(|b| b.into_any())
        }
        JobParameterDefinition::INT(p) => {
            Bound::new(py, PyJobIntParameterDefinition { inner: p.clone() }).map(|b| b.into_any())
        }
        JobParameterDefinition::FLOAT(p) => {
            Bound::new(py, PyJobFloatParameterDefinition { inner: p.clone() }).map(|b| b.into_any())
        }
        JobParameterDefinition::PATH(p) => {
            Bound::new(py, PyJobPathParameterDefinition { inner: p.clone() }).map(|b| b.into_any())
        }
        JobParameterDefinition::BOOL(p) => {
            Bound::new(py, PyJobBoolParameterDefinition { inner: p.clone() }).map(|b| b.into_any())
        }
        JobParameterDefinition::RANGE_EXPR(p) => {
            Bound::new(py, PyJobRangeExprParameterDefinition { inner: p.clone() })
                .map(|b| b.into_any())
        }
        JobParameterDefinition::LIST_STRING(p) => {
            Bound::new(py, PyJobListStringParameterDefinition { inner: p.clone() })
                .map(|b| b.into_any())
        }
        JobParameterDefinition::LIST_PATH(p) => {
            Bound::new(py, PyJobListPathParameterDefinition { inner: p.clone() })
                .map(|b| b.into_any())
        }
        JobParameterDefinition::LIST_INT(p) => {
            Bound::new(py, PyJobListIntParameterDefinition { inner: p.clone() })
                .map(|b| b.into_any())
        }
        JobParameterDefinition::LIST_FLOAT(p) => {
            Bound::new(py, PyJobListFloatParameterDefinition { inner: p.clone() })
                .map(|b| b.into_any())
        }
        JobParameterDefinition::LIST_BOOL(p) => {
            Bound::new(py, PyJobListBoolParameterDefinition { inner: p.clone() })
                .map(|b| b.into_any())
        }
        JobParameterDefinition::LIST_LIST_INT(p) => {
            Bound::new(py, PyJobListListIntParameterDefinition { inner: p.clone() })
                .map(|b| b.into_any())
        }
    }
}

/// Convert an `Option<Vec<JobParameterDefinition>>` from the Rust
/// model into ``Optional[list[JobParameterDefinition pyclass]]``,
/// returning ``None`` if the field is absent OR empty.
pub(crate) fn job_param_defs_to_py<'py>(
    py: Python<'py>,
    defs: Option<&Vec<JobParameterDefinition>>,
) -> PyResult<Option<Bound<'py, PyList>>> {
    match defs {
        None => Ok(None),
        Some(v) if v.is_empty() => Ok(None),
        Some(v) => {
            let py_list = PyList::empty(py);
            for d in v {
                py_list.append(job_param_def_to_py(py, d)?)?;
            }
            Ok(Some(py_list))
        }
    }
}
