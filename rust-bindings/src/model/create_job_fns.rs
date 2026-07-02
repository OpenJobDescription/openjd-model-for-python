// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use pyo3::prelude::*;
use pyo3::types::PyDict;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_model::template::EnvironmentTemplate;
use openjd_model::types::JobParameterInputValues;
use openjd_model::JobParameterType;
use openjd_model::PathParameterOptions;

use crate::expr::expr_value::py_to_expr_value;

use super::errors::model_err_to_py;
use super::job::{PyEnvironment, PyJob, PyStep};
use super::template::{PyEnvironmentTemplate, PyJobTemplate};

fn extract_input_values(py_dict: &Bound<'_, PyDict>) -> PyResult<JobParameterInputValues> {
    let mut result = JobParameterInputValues::new();
    for (key, val) in py_dict.iter() {
        let name: String = key.extract()?;
        if let Ok(inner_dict) = val.cast::<PyDict>() {
            // {"type": ..., "value": ...} — take the value field.
            if let Some(v) = inner_dict.get_item("value")? {
                result.insert(name, py_to_expr_value(&v)?);
            }
        } else if let Ok(jpv) = val.extract::<crate::model::types::PyJobParameterValue>() {
            // ``JobParameterValue``-shaped pyclass: use its inner
            // ExprValue directly. ``preprocess_job_parameters`` will
            // infer the target type from the parameter definition
            // and coerce. Going through ``inner.value`` (an
            // ``ExprValue``) preserves type fidelity — going through
            // ``.value`` (a string) would lose typing for list types
            // whose elements need re-parsing.
            result.insert(name, jpv.inner.value);
        } else if let (Ok(_), Ok(value_attr)) = (val.getattr("type"), val.getattr("value")) {
            // Other ``ParameterValue``-shaped object with ``.type`` /
            // ``.value`` attributes (e.g. mock objects in tests).
            // Drop the type — preprocess will infer + coerce.
            result.insert(name, py_to_expr_value(&value_attr)?);
        } else {
            // Bare scalar (e.g. ``{"Frame": 5}``). Pass straight through.
            result.insert(name, py_to_expr_value(&val)?);
        }
    }
    Ok(result)
}

fn extract_env_templates(
    env_templates: Option<Vec<PyEnvironmentTemplate>>,
) -> Vec<EnvironmentTemplate> {
    env_templates
        .map(|v| v.into_iter().map(|e| e.inner).collect())
        .unwrap_or_default()
}

#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyfunction(module = "openjd._openjd_rs")
)]
#[pyfunction(name = "create_job")]
#[pyo3(signature = (*, job_template, job_parameter_values, environment_templates=None, validation_context=None))]
pub(crate) fn py_create_job(
    job_template: &PyJobTemplate,
    job_parameter_values: &Bound<'_, PyDict>,
    environment_templates: Option<Vec<PyEnvironmentTemplate>>,
    validation_context: Option<&super::profile::PyValidationContext>,
) -> PyResult<PyJob> {
    let env_templates = extract_env_templates(environment_templates);

    // Match the v0 (pure-Python) reference's behaviour: route the
    // caller-supplied parameter values through ``preprocess_job_parameters``
    // before constructing the job. This:
    //   * fills in defaults from the parameter definitions for any
    //     names the caller didn't supply explicitly, so
    //     ``Job.parameters`` ends up with every defined parameter
    //     (matching the v0 contract that downstream consumers —
    //     sessions, the worker agent, deadline-cli — rely on);
    //   * runs every per-parameter constraint check before
    //     instantiation (no need for the caller to also call
    //     ``preprocess_job_parameters`` first);
    //   * coerces input values from their raw Python form
    //     (string, int, etc.) to the typed ``ExprValue`` shape that
    //     ``create_job`` expects.
    //
    // Path-resolution-related options use sentinel "skip" values
    // (empty paths + ``allow_template_dir_walk_up=true``) because at
    // ``create_job`` time we don't know the on-disk template
    // directory or the caller's CWD; the v0 reference does the same.
    // Callers that need PATH-default resolution against a real
    // template-dir / CWD should call ``preprocess_job_parameters``
    // explicitly first and then pass the result to ``create_job``.
    let input_values = extract_input_values(job_parameter_values)?;
    let path_opts = PathParameterOptions {
        job_template_dir: "",
        current_working_dir: "",
        path_format: openjd_expr::path_mapping::PathFormat::host(),
        allow_template_dir_walk_up: true,
        allow_uri_path_values: false,
    };
    let params = openjd_model::preprocess_job_parameters(
        &job_template.inner,
        &input_values,
        &env_templates,
        &path_opts,
    )
    .map_err(model_err_to_py)?;

    // Use the caller-supplied validation_context if given; otherwise
    // derive the default one from the template's declared profile.
    let ctx = match validation_context {
        Some(vc) => vc.inner.clone(),
        None => job_template.inner.default_validation_context(),
    };
    let job =
        openjd_model::create_job(&job_template.inner, &params, &ctx).map_err(model_err_to_py)?;
    Ok(PyJob { inner: job })
}

#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyfunction(module = "openjd._openjd_rs")
)]
#[pyfunction(name = "preprocess_job_parameters")]
#[pyo3(signature = (*, job_template, job_parameter_values, environment_templates=None, job_template_dir, current_working_dir, allow_job_template_dir_walk_up=false))]
pub(crate) fn py_preprocess_job_parameters(
    py: Python<'_>,
    job_template: &PyJobTemplate,
    job_parameter_values: &Bound<'_, PyDict>,
    environment_templates: Option<Vec<PyEnvironmentTemplate>>,
    job_template_dir: std::path::PathBuf,
    current_working_dir: std::path::PathBuf,
    allow_job_template_dir_walk_up: bool,
) -> PyResult<Py<PyDict>> {
    let input_values = extract_input_values(job_parameter_values)?;
    let env_templates = extract_env_templates(environment_templates);
    // Pass ``job_template_dir`` through verbatim so the upstream
    // diagnostic ("The value supplied for the job template dir, X,
    // is not an absolute path.") names the path the caller actually
    // supplied — earlier versions rewrote `"."` to `""` here, which
    // leaked into the diagnostic as an empty placeholder.
    let tdir = job_template_dir.to_str().unwrap_or("");
    // ``current_working_dir`` keeps the `"."` → `""` rewrite. The
    // CWD never appears in any error message, and upstream's
    // PATH-value handling treats an empty CWD as "skip the join"
    // (see ``preprocess_job_parameters`` in the upstream crate);
    // a literal `"."` would prepend `./` to relative path values,
    // diverging from the v0 reference's behaviour.
    let cwd_str = current_working_dir.to_str().unwrap_or("");
    let cwd = if cwd_str == "." { "" } else { cwd_str };
    let path_opts = PathParameterOptions {
        job_template_dir: tdir,
        current_working_dir: cwd,
        path_format: openjd_expr::path_mapping::PathFormat::host(),
        allow_template_dir_walk_up: allow_job_template_dir_walk_up,
        allow_uri_path_values: false,
    };
    let result = openjd_model::preprocess_job_parameters(
        &job_template.inner,
        &input_values,
        &env_templates,
        &path_opts,
    )
    .map_err(model_err_to_py)?;

    use pyo3::IntoPyObjectExt;
    let out = PyDict::new(py);
    for (name, jpv) in &result {
        let pv = super::types::PyJobParameterValue { inner: jpv.clone() };
        out.set_item(name, pv.into_py_any(py)?)?;
    }
    Ok(out.unbind())
}

#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyfunction(module = "openjd._openjd_rs")
)]
#[pyfunction(name = "merge_job_parameter_definitions")]
#[pyo3(signature = (*, job_template, environment_templates=None))]
pub(crate) fn py_merge_job_parameter_definitions(
    py: Python<'_>,
    job_template: &PyJobTemplate,
    environment_templates: Option<Vec<PyEnvironmentTemplate>>,
) -> PyResult<Vec<Py<PyDict>>> {
    let env_templates = extract_env_templates(environment_templates);
    let merged = openjd_model::merge_job_parameter_definitions(&job_template.inner, &env_templates)
        .map_err(model_err_to_py)?;

    // Collect descriptions by parameter name. The upstream
    // `MergedParameterDefinition` struct does not carry a description
    // field (only `name`, `param_type`, `default`, `object_type`,
    // `data_flow`, `source`, and the merged constraint fields), so we
    // recover it here by walking the same template sources the merge
    // walked. To match how `default` is tracked (later template wins),
    // we walk environment templates first (in order) then the job
    // template last, overwriting on each set description we encounter.
    let mut descriptions: std::collections::HashMap<&str, &str> = std::collections::HashMap::new();
    for et in &env_templates {
        if let Some(params) = &et.parameter_definitions {
            for p in params {
                if let Some(desc) = p.description() {
                    descriptions.insert(p.name(), desc);
                }
            }
        }
    }
    for p in job_template.inner.parameter_definitions_list() {
        if let Some(desc) = p.description() {
            descriptions.insert(p.name(), desc);
        }
    }

    let mut out = Vec::new();
    for m in &merged {
        let d = PyDict::new(py);
        d.set_item("name", &m.name)?;
        d.set_item("type", m.param_type.as_spec_str())?;
        if let Some(ref default) = m.default {
            let py_default = default_to_native(py, m.param_type, default)?;
            d.set_item("default", py_default)?;
        }
        if let Some(desc) = descriptions.get(m.name.as_str()) {
            d.set_item("description", *desc)?;
        }
        if let Some(ref ot) = m.object_type {
            d.set_item("objectType", ot.to_string())?;
        }
        if let Some(ref df) = m.data_flow {
            d.set_item("dataFlow", df.to_string())?;
        }
        d.set_item("source", &m.source)?;
        out.push(d.unbind());
    }
    Ok(out)
}

/// Convert a stringified default value back into the native Python
/// type for its parameter type.
///
/// The upstream Rust crate's `MergedParameterDefinition::default` is
/// `Option<String>` — every variant is stringified through
/// `JobParameterDefinition::default_value()` regardless of the
/// underlying typed payload. The binding contract (per
/// `specs/python-model-interface.md`) is that callers receive the
/// default in its native Python type (`int` for `INT`, `float` for
/// `FLOAT`, `list[T]` for `LIST[T]`, etc.). This helper parses the
/// stringified form back into the right Python type.
///
/// `STRING` / `PATH` / `RANGE_EXPR` defaults pass through unchanged
/// (they are already strings). `LIST[*]` defaults are JSON-serialised
/// by the upstream `default_value()` implementation, so they round-trip
/// through `serde_json`.
///
/// If parsing fails for any reason (defensive fallback against future
/// upstream serialization changes), the original string is returned
/// so the caller never sees a `None` where v0 would have produced a
/// default.
fn default_to_native(
    py: Python<'_>,
    param_type: JobParameterType,
    raw: &str,
) -> PyResult<Py<pyo3::PyAny>> {
    use pyo3::IntoPyObjectExt;
    match param_type {
        JobParameterType::String | JobParameterType::Path | JobParameterType::RangeExpr => {
            raw.into_py_any(py)
        }
        JobParameterType::Int => raw
            .parse::<i64>()
            .ok()
            .map(|v| v.into_py_any(py))
            .unwrap_or_else(|| raw.into_py_any(py)),
        JobParameterType::Float => raw
            .parse::<f64>()
            .ok()
            .map(|v| v.into_py_any(py))
            .unwrap_or_else(|| raw.into_py_any(py)),
        JobParameterType::Bool => match raw {
            "true" => true.into_py_any(py),
            "false" => false.into_py_any(py),
            _ => raw.into_py_any(py),
        },
        JobParameterType::ListString | JobParameterType::ListPath => {
            serde_json::from_str::<Vec<String>>(raw)
                .ok()
                .map(|v| v.into_py_any(py))
                .unwrap_or_else(|| raw.into_py_any(py))
        }
        JobParameterType::ListInt => serde_json::from_str::<Vec<i64>>(raw)
            .ok()
            .map(|v| v.into_py_any(py))
            .unwrap_or_else(|| raw.into_py_any(py)),
        JobParameterType::ListFloat => serde_json::from_str::<Vec<f64>>(raw)
            .ok()
            .map(|v| v.into_py_any(py))
            .unwrap_or_else(|| raw.into_py_any(py)),
        JobParameterType::ListBool => serde_json::from_str::<Vec<bool>>(raw)
            .ok()
            .map(|v| v.into_py_any(py))
            .unwrap_or_else(|| raw.into_py_any(py)),
        JobParameterType::ListListInt => serde_json::from_str::<Vec<Vec<i64>>>(raw)
            .ok()
            .map(|v| v.into_py_any(py))
            .unwrap_or_else(|| raw.into_py_any(py)),
        // ``JobParameterType`` is ``#[non_exhaustive]`` — any future
        // variant we don't know about falls back to the raw string so
        // callers see *some* value rather than nothing.
        _ => raw.into_py_any(py),
    }
}

#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyfunction(module = "openjd._openjd_rs")
)]
#[pyfunction]
#[pyo3(name = "evaluate_let_bindings")]
#[pyo3(signature = (bindings, symtab, *, profile=None))]
pub(crate) fn py_evaluate_let_bindings(
    bindings: Vec<String>,
    symtab: &crate::expr::PySymbolTable,
    profile: Option<&crate::expr::profile::PyExprProfile>,
) -> PyResult<crate::expr::PySymbolTable> {
    let lib = crate::expr::evaluate::profile_for_call(profile);
    let result = openjd_model::evaluate_let_bindings(
        &bindings,
        &symtab.inner,
        Some(&lib),
        openjd_expr::path_mapping::PathFormat::host(),
    )
    .map_err(super::errors::model_err_to_py)?;
    Ok(crate::expr::PySymbolTable { inner: result })
}

/// Deserialize a job-side `Step` from a Python dict. This matches the
/// payload shape that the Deadline Cloud service's `GetStepDetails` /
/// `BatchGetJobEntity` API returns in the `template` field: it is a
/// serialized `openjd_model::job::Step`, not a template-side StepTemplate.
///
/// Consumers like the Deadline Cloud worker agent use this to reconstruct
/// a `Step` object from the wire payload so they can pass its
/// parameter_space to the step-parameter-space iterator and its script
/// to `Session.run_task`.
#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyfunction(module = "openjd._openjd_rs")
)]
#[pyfunction(name = "deserialize_step")]
pub(crate) fn py_deserialize_step(step_dict: &Bound<'_, PyDict>) -> PyResult<PyStep> {
    use openjd_model::job;
    let json_str: String = {
        let json_mod = step_dict.py().import("json")?;
        json_mod.call_method1("dumps", (step_dict,))?.extract()?
    };
    let step: job::Step = serde_json::from_str(&json_str).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("failed to deserialize Step: {e}"))
    })?;
    Ok(PyStep { inner: step })
}

/// Convert a template `EnvironmentTemplate` into a job-side `Environment` with
/// the same contents. Analogous to how `create_job` instantiates a `JobTemplate`
/// into a `Job`, but for a standalone environment (no job parameters involved
/// in environment-only templates).
///
/// Consumers like the Deadline Cloud worker agent need this to turn the
/// `EnvironmentDetails` boto payload into an `Environment` they can pass to
/// `Session.enter_environment`.
#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyfunction(module = "openjd._openjd_rs")
)]
#[pyfunction(name = "create_environment")]
pub(crate) fn py_create_environment(env_template: &PyEnvironmentTemplate) -> PyEnvironment {
    let env = openjd_model::convert_environment(&env_template.inner.environment);
    PyEnvironment { inner: env }
}
