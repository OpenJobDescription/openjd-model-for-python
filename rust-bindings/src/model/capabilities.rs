// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

//! Capability name validation and standard-capability lookup.
//!
//! Wraps the Rust crate's `capabilities::*` API with PyO3 entry
//! points and adds the rich semantics (length cap + reserved-scope
//! check + standard-name whitelist short-circuit) that the
//! template-time validator in `openjd_model::template::validate_v2023_09`
//! enforces internally. The crate's public `validate_*_capability_name`
//! functions today do regex-only checks; the rest of the validation
//! lives behind `pub(crate)` helpers that this module reimplements
//! to avoid changing the crate's public surface.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_model::capabilities::{
    standard_amount_capability_names as rs_amount_names,
    standard_attribute_capabilities as rs_attribute_caps,
    standard_attribute_capability_names as rs_attribute_names,
    validate_amount_capability_name as rs_validate_amount_regex,
    validate_attribute_capability_name as rs_validate_attribute_regex,
};
use openjd_model::ModelProfile;

use super::profile::PyModelProfile;

const MAX_CAPABILITY_NAME_LEN: usize = 100;
const RESERVED_SCOPES: &[&str] = &["worker", "job", "step", "task"];

/// Resolve an optional ``ModelProfile`` to an owned profile. Returns
/// the binding's default profile (matching the Python-callable
/// ``ModelProfile()`` constructor) when ``profile`` is ``None``.
fn resolve_profile(profile: Option<&PyModelProfile>) -> ModelProfile {
    profile
        .map(|p| p.inner.clone())
        .unwrap_or_else(|| PyModelProfile::default().inner)
}

/// Strip the optional ``vendor:`` prefix from a capability name,
/// returning the un-prefixed portion. ``"foo:amount.bar"`` → ``"amount.bar"``.
/// If there's no colon, returns the input unchanged.
fn strip_vendor(name: &str) -> &str {
    name.split_once(':').map(|(_, rest)| rest).unwrap_or(name)
}

/// Check the reserved-scope rule on a capability name. Mirrors
/// `openjd_model::template::validate_v2023_09::helpers::check_capability_reserved_scope`,
/// which is `pub(crate)` in the crate so we can't call it directly.
///
/// Standard-name short-circuit: a name without a vendor prefix that
/// matches one of ``standard`` is accepted (those ARE the spec-defined
/// reserved-scope capabilities). Otherwise, names whose second
/// dot-segment is in `RESERVED_SCOPES` are rejected.
fn check_reserved_scope(name_lower: &str, standard: &[&str]) -> Result<(), String> {
    let capability = strip_vendor(name_lower);
    if standard.contains(&capability) {
        return Ok(());
    }
    let parts: Vec<&str> = capability.split('.').collect();
    if parts.len() >= 2 {
        let scope = parts[1];
        if RESERVED_SCOPES.contains(&scope) {
            return Err(format!(
                "capability '{name_lower}' uses reserved scope '{scope}'. \
                 Only spec-defined capabilities may use this scope."
            ));
        }
    }
    Ok(())
}

/// Run the shared length + regex checks. The regex check is
/// delegated to the crate's regex-only `validate_*_capability_name`
/// (which uses the same `AMOUNT_CAP_RE` / `ATTR_CAP_RE` the
/// template-time validator uses).
fn check_length_and_regex(
    name: &str,
    regex_check: fn(&str) -> Result<(), String>,
) -> Result<(), String> {
    if name.len() > MAX_CAPABILITY_NAME_LEN {
        return Err(format!(
            "capability name '{name}' exceeds {MAX_CAPABILITY_NAME_LEN} characters."
        ));
    }
    regex_check(name)
}

// ── Validators ─────────────────────────────────────────────────────

/// Validate that ``name`` is a well-formed amount-capability name.
///
/// Checks (in order):
///
/// 1. Length must be at most 100 characters.
/// 2. Must match the amount-capability regex
///    ``^([A-Za-z_][A-Za-z0-9_]*:)?amount\.[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$``.
/// 3. Names without a vendor prefix that match a spec-defined
///    standard capability (e.g. ``amount.worker.vcpu``) are accepted.
/// 4. Names whose second dot-segment is one of the reserved scopes
///    (``worker``, ``job``, ``step``, ``task``) are rejected unless
///    they appear in (3) — those scopes are reserved for OpenJD-defined
///    capabilities.
///
/// Args:
///     name: The capability name to validate.
///     profile: The model profile whose ``(revision, extensions)``
///         determine the standard-capability set used for the
///         reserved-scope short-circuit. Defaults to a profile equivalent to
///         ``ModelProfile()``.
///
/// Raises:
///     ValueError: if any of the checks above fail.
#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyfunction(module = "openjd._openjd_rs")
)]
#[pyfunction]
#[pyo3(signature = (name, *, profile=None))]
pub(crate) fn validate_amount_capability_name(
    name: &str,
    profile: Option<&PyModelProfile>,
) -> PyResult<()> {
    let profile = resolve_profile(profile);
    let revision = profile.revision();
    let extensions = profile.extensions();
    let standard =
        rs_amount_names(revision, extensions).map_err(|e| PyValueError::new_err(e.to_string()))?;

    check_length_and_regex(name, rs_validate_amount_regex).map_err(PyValueError::new_err)?;
    let lower = name.to_lowercase();
    check_reserved_scope(&lower, standard).map_err(PyValueError::new_err)?;
    Ok(())
}

/// Validate that ``name`` is a well-formed attribute-capability name.
///
/// Checks (in order):
///
/// 1. Length must be at most 100 characters.
/// 2. Must match the attribute-capability regex
///    ``^([A-Za-z_][A-Za-z0-9_]*:)?attr\.[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$``.
/// 3. Names without a vendor prefix that match a spec-defined
///    standard capability (e.g. ``attr.worker.os.family``) are accepted.
/// 4. Names whose second dot-segment is one of the reserved scopes
///    (``worker``, ``job``, ``step``, ``task``) are rejected unless
///    they appear in (3) — those scopes are reserved for OpenJD-defined
///    capabilities.
///
/// Args:
///     name: The capability name to validate.
///     profile: The model profile whose ``(revision, extensions)``
///         determine the standard-capability set used for the
///         reserved-scope short-circuit. Defaults to a profile equivalent to
///         ``ModelProfile()``.
///
/// Raises:
///     ValueError: if any of the checks above fail.
#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyfunction(module = "openjd._openjd_rs")
)]
#[pyfunction]
#[pyo3(signature = (name, *, profile=None))]
pub(crate) fn validate_attribute_capability_name(
    name: &str,
    profile: Option<&PyModelProfile>,
) -> PyResult<()> {
    let profile = resolve_profile(profile);
    let revision = profile.revision();
    let extensions = profile.extensions();
    let standard = rs_attribute_names(revision, extensions)
        .map_err(|e| PyValueError::new_err(e.to_string()))?;
    let standard_slice: Vec<&str> = standard.to_vec();

    check_length_and_regex(name, rs_validate_attribute_regex).map_err(PyValueError::new_err)?;
    let lower = name.to_lowercase();
    check_reserved_scope(&lower, &standard_slice).map_err(PyValueError::new_err)?;
    Ok(())
}

// ── Standard-capability lookups ────────────────────────────────────

/// Return the names of the spec-defined amount capabilities for the
/// given profile.
///
/// Args:
///     profile: The model profile whose ``(revision, extensions)``
///         determine the standard-capability set. Defaults to a
///         profile equivalent to ``ModelProfile()``.
///
/// Returns:
///     A list of capability names like ``["amount.worker.vcpu", ...]``.
#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyfunction(module = "openjd._openjd_rs")
)]
#[pyfunction]
#[pyo3(signature = (*, profile=None))]
pub(crate) fn standard_amount_capability_names(
    profile: Option<&PyModelProfile>,
) -> PyResult<Vec<String>> {
    let profile = resolve_profile(profile);
    let revision = profile.revision();
    let extensions = profile.extensions();
    let names =
        rs_amount_names(revision, extensions).map_err(|e| PyValueError::new_err(e.to_string()))?;
    Ok(names.iter().map(|s| s.to_string()).collect())
}

/// Return the names of the spec-defined attribute capabilities for
/// the given profile.
///
/// Args:
///     profile: The model profile whose ``(revision, extensions)``
///         determine the standard-capability set. Defaults to a
///         profile equivalent to ``ModelProfile()``.
///
/// Returns:
///     A list of capability names like ``["attr.worker.os.family", ...]``.
#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyfunction(module = "openjd._openjd_rs")
)]
#[pyfunction]
#[pyo3(signature = (*, profile=None))]
pub(crate) fn standard_attribute_capability_names(
    profile: Option<&PyModelProfile>,
) -> PyResult<Vec<String>> {
    let profile = resolve_profile(profile);
    let revision = profile.revision();
    let extensions = profile.extensions();
    let names = rs_attribute_names(revision, extensions)
        .map_err(|e| PyValueError::new_err(e.to_string()))?;
    Ok(names.iter().map(|s| s.to_string()).collect())
}

/// Return the spec-defined attribute capabilities for the given
/// profile, including each capability's allowed values.
///
/// Args:
///     profile: The model profile whose ``(revision, extensions)``
///         determine the standard-capability set. Defaults to a
///         profile equivalent to ``ModelProfile()``.
///
/// Returns:
///     A list of ``(name, [allowed values])`` pairs. For example:
///     ``[("attr.worker.os.family", ["linux", "windows", "macos"]),
///        ("attr.worker.cpu.arch", ["x86_64", "arm64"])]``.
#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyfunction(module = "openjd._openjd_rs")
)]
#[pyfunction]
#[pyo3(signature = (*, profile=None))]
pub(crate) fn standard_attribute_capabilities(
    profile: Option<&PyModelProfile>,
) -> PyResult<Vec<(String, Vec<String>)>> {
    let profile = resolve_profile(profile);
    let revision = profile.revision();
    let extensions = profile.extensions();
    let caps = rs_attribute_caps(revision, extensions)
        .map_err(|e| PyValueError::new_err(e.to_string()))?;
    Ok(caps
        .iter()
        .map(|(name, values)| {
            (
                name.to_string(),
                values.iter().map(|v| v.to_string()).collect(),
            )
        })
        .collect())
}
