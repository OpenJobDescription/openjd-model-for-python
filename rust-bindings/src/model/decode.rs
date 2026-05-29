// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use pyo3::prelude::*;
use pyo3::types::PyDict;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_model::template::parse::DocumentType;
use openjd_model::CallerLimits;

use super::errors::model_err_to_py;
use super::profile::PyCallerLimits;
use super::template::{PyEnvironmentTemplate, PyJobTemplate};
use super::types::PyDocumentType;

/// Parse a raw string into serde_json::Value based on document type.
fn parse_string(document: &str, format: PyDocumentType) -> PyResult<serde_json::Value> {
    let doc_type: DocumentType = format.into();
    openjd_model::template::parse::document_string_to_object(
        document,
        doc_type,
        &CallerLimits::default(),
    )
    .map_err(model_err_to_py)
}

/// Convert a Python dict to serde_json::Value via JSON round-trip.
fn dict_to_json_value(template: &Bound<'_, PyDict>) -> PyResult<serde_json::Value> {
    let json_str: String = {
        let json_mod = template.py().import("json")?;
        json_mod.call_method1("dumps", (template,))?.extract()?
    };
    serde_json::from_str(&json_str)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

/// Borrow the Python `Vec<String>` allowlist as the `&[&str]` form
/// the Rust crate's `decode_*_template` expects.
fn as_str_slice(v: &Option<Vec<String>>) -> Option<Vec<&str>> {
    v.as_ref()
        .map(|exts| exts.iter().map(String::as_str).collect())
}

fn limits_or_default(c: Option<&PyCallerLimits>) -> CallerLimits {
    c.map(|c| c.inner.clone()).unwrap_or_default()
}

/// Decode and validate a job template from a YAML or JSON string.
///
/// Parses ``document`` (YAML by default; pass ``DocumentType.JSON``
/// to force JSON parsing instead of the YAML-superset default), then
/// validates the result against the OpenJD schema.
///
/// Args:
///     document: The template source as a YAML or JSON string.
///     format: Document type. Defaults to ``DocumentType.YAML``
///         (which is also a superset of JSON).
///     supported_extensions: The caller's allowlist of OpenJD
///         extension names. The template's ``extensions:`` field
///         is validated against this list — any name in the
///         template that is not both a recognized
///         ``ModelExtension`` AND in this list is rejected with
///         ``Unsupported extension names: ...``. Pass ``None``
///         (the default) for an empty allowlist (i.e., reject
///         every extension the template requests).
///     caller_limits: Optional ``CallerLimits`` to tighten
///         spec-defined limits (e.g. maximum step count).
///
/// Returns:
///     The parsed ``openjd.model._v1.template.JobTemplate``. Use
///     ``template.profile`` to access the ``ModelProfile``
///     describing the template's declared revision and extensions
///     (a subset of ``supported_extensions``).
#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyfunction(module = "openjd._openjd_rs")
)]
#[pyfunction]
#[pyo3(signature = (document, format=PyDocumentType::YAML, *, supported_extensions=None, caller_limits=None))]
pub(crate) fn decode_job_template_str(
    document: &str,
    format: PyDocumentType,
    supported_extensions: Option<Vec<String>>,
    caller_limits: Option<&PyCallerLimits>,
) -> PyResult<PyJobTemplate> {
    let value = parse_string(document, format)?;
    let exts = as_str_slice(&supported_extensions);
    let limits = limits_or_default(caller_limits);
    let jt = openjd_model::decode_job_template(value, exts.as_deref(), &limits)
        .map_err(model_err_to_py)?;
    Ok(PyJobTemplate { inner: jt })
}

/// Decode and validate a job template from a Python dict.
///
/// Validates ``template`` against the OpenJD schema. Use this
/// entry point when the document has already been parsed (e.g.
/// from PyYAML or ``json.loads``); for parsing directly from a
/// string, use ``decode_job_template_str``.
///
/// Args:
///     template: The decoded template mapping.
///     supported_extensions: The caller's allowlist of OpenJD
///         extension names. The template's ``extensions:`` field
///         is validated against this list — any name in the
///         template that is not both a recognized
///         ``ModelExtension`` AND in this list is rejected with
///         ``Unsupported extension names: ...``. Pass ``None``
///         (the default) for an empty allowlist (i.e., reject
///         every extension the template requests).
///     caller_limits: Optional ``CallerLimits`` to tighten
///         spec-defined limits (e.g. maximum step count).
///
/// Returns:
///     The parsed ``openjd.model._v1.template.JobTemplate``. Use
///     ``template.profile`` to access the ``ModelProfile``
///     describing the template's declared revision and extensions
///     (a subset of ``supported_extensions``).
#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyfunction(module = "openjd._openjd_rs")
)]
#[pyfunction]
#[pyo3(signature = (template, *, supported_extensions=None, caller_limits=None))]
pub(crate) fn decode_job_template(
    template: &Bound<'_, PyDict>,
    supported_extensions: Option<Vec<String>>,
    caller_limits: Option<&PyCallerLimits>,
) -> PyResult<PyJobTemplate> {
    let value = dict_to_json_value(template)?;
    let exts = as_str_slice(&supported_extensions);
    let limits = limits_or_default(caller_limits);
    let jt = openjd_model::decode_job_template(value, exts.as_deref(), &limits)
        .map_err(model_err_to_py)?;
    Ok(PyJobTemplate { inner: jt })
}

/// Decode and validate an environment template from a YAML or JSON string.
///
/// Parses ``document`` (YAML by default; pass ``DocumentType.JSON``
/// to force JSON parsing instead of the YAML-superset default), then
/// validates the result against the OpenJD environment-template
/// schema.
///
/// Args:
///     document: The template source as a YAML or JSON string.
///     format: Document type. Defaults to ``DocumentType.YAML``
///         (which is also a superset of JSON).
///     supported_extensions: The caller's allowlist of OpenJD
///         extension names. The template's ``extensions:`` field
///         is validated against this list — any name in the
///         template that is not both a recognized
///         ``ModelExtension`` AND in this list is rejected with
///         ``Unsupported extension names: ...``. Pass ``None``
///         (the default) for an empty allowlist (i.e., reject
///         every extension the template requests).
///
/// Returns:
///     The parsed ``openjd.model._v1.template.EnvironmentTemplate``.
///     Environment templates do not accept ``caller_limits``.
#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyfunction(module = "openjd._openjd_rs")
)]
#[pyfunction]
#[pyo3(signature = (document, format=PyDocumentType::YAML, *, supported_extensions=None))]
pub(crate) fn decode_environment_template_str(
    document: &str,
    format: PyDocumentType,
    supported_extensions: Option<Vec<String>>,
) -> PyResult<PyEnvironmentTemplate> {
    let value = parse_string(document, format)?;
    let exts = as_str_slice(&supported_extensions);
    let et = openjd_model::decode_environment_template(value, exts.as_deref())
        .map_err(model_err_to_py)?;
    Ok(PyEnvironmentTemplate { inner: et })
}

/// Decode and validate an environment template from a Python dict.
///
/// Validates ``template`` against the OpenJD environment-template
/// schema. Use this entry point when the document has already been
/// parsed (e.g. from PyYAML or ``json.loads``); for parsing
/// directly from a string, use ``decode_environment_template_str``.
///
/// Args:
///     template: The decoded template mapping.
///     supported_extensions: The caller's allowlist of OpenJD
///         extension names. The template's ``extensions:`` field
///         is validated against this list — any name in the
///         template that is not both a recognized
///         ``ModelExtension`` AND in this list is rejected with
///         ``Unsupported extension names: ...``. Pass ``None``
///         (the default) for an empty allowlist (i.e., reject
///         every extension the template requests).
///
/// Returns:
///     The parsed ``openjd.model._v1.template.EnvironmentTemplate``.
///     Environment templates do not accept ``caller_limits``.
#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyfunction(module = "openjd._openjd_rs")
)]
#[pyfunction]
#[pyo3(signature = (template, *, supported_extensions=None))]
pub(crate) fn decode_environment_template(
    template: &Bound<'_, PyDict>,
    supported_extensions: Option<Vec<String>>,
) -> PyResult<PyEnvironmentTemplate> {
    let value = dict_to_json_value(template)?;
    let exts = as_str_slice(&supported_extensions);
    let et = openjd_model::decode_environment_template(value, exts.as_deref())
        .map_err(model_err_to_py)?;
    Ok(PyEnvironmentTemplate { inner: et })
}
