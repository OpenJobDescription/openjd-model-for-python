// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

mod expr;
mod model;
mod pickle_helpers;
mod sessions;

use pyo3::prelude::*;
use pyo3::types::PyType;

use openjd_expr::eval::{DEFAULT_MEMORY_LIMIT, DEFAULT_OPERATION_LIMIT};

#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::define_stub_info_gatherer;

use expr::*;
use model::*;
use sessions::*;

#[cfg(feature = "stub-gen")]
define_stub_info_gatherer!(stub_info);

/// Register a PyO3 `create_exception!`-built exception under its canonical
/// public name, and patch the type's `__name__`, `__qualname__`, and
/// `__module__` attributes so that `repr`, `pickle`, and tracebacks all
/// report the user-facing name (e.g. `openjd.sessions._v1.SessionError`)
/// rather than the binding-internal `_openjd_rs.PySessionError`.
///
/// PyO3's `create_exception!` macro stringifies its identifier argument and
/// uses that as the type name, and accepts only a bare module identifier (no
/// dots) for the module string. Without this fix-up, Python sees these
/// exceptions under their internal `Py`-prefixed names — which surface in
/// tracebacks, pickle, IDE tooltips, and Sphinx output. Fixing it up here in
/// the binding (rather than in each consuming Python package's `__init__.py`)
/// guarantees the canonical names are visible regardless of import order.
fn register_renamed_exception(
    m: &Bound<'_, PyModule>,
    py_type: Bound<'_, PyType>,
    public_name: &str,
    public_module: &str,
) -> PyResult<()> {
    py_type.setattr("__module__", public_module)?;
    py_type.setattr("__name__", public_name)?;
    py_type.setattr("__qualname__", public_name)?;
    m.add(public_name, py_type)?;
    Ok(())
}

// ── Module ──

#[pymodule]
#[pyo3(name = "_openjd_rs")]
fn openjd_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Install Rust→Python logging bridge. Remap Rust crate targets
    // (openjd_sessions, openjd_model, openjd_expr) to Python logger
    // hierarchy (openjd.sessions, openjd.model, openjd.expr).
    pyo3_log::Logger::default()
        .filter(log::LevelFilter::Info)
        .install()
        .ok();

    // ── Expr types ──
    m.add_class::<PyPathFormat>()?;
    m.add_class::<PyExprType>()?;
    m.add_class::<PyTypeCode>()?;
    m.add_class::<PyExprValue>()?;
    m.add_class::<PySymbolTable>()?;
    m.add_class::<PySerializedSymbolTable>()?;
    m.add_class::<PyExprRevision>()?;
    m.add_class::<PyExprExtension>()?;
    m.add_class::<PyHostContext>()?;
    m.add_class::<PyExprProfile>()?;
    m.add_class::<PyParsedExpression>()?;
    m.add_class::<PyEvalResult>()?;
    m.add_class::<PyPathMappingRule>()?;
    m.add_class::<PyRangeExpr>()?;
    m.add_class::<PyIntRange>()?;
    m.add_class::<PyFormatString>()?;

    m.add_function(wrap_pyfunction!(evaluate_expression, m)?)?;
    m.add_function(wrap_pyfunction!(parse_expression, m)?)?;
    m.add_function(wrap_pyfunction!(escape_format_string, m)?)?;
    m.add_function(wrap_pyfunction!(build_symbol_table, m)?)?;
    m.add_function(wrap_pyfunction!(_reconstruct_expr_value, m)?)?;
    m.add_function(wrap_pyfunction!(_reconstruct_serialized_symtab, m)?)?;

    m.add("DEFAULT_MEMORY_LIMIT", DEFAULT_MEMORY_LIMIT)?;
    m.add("DEFAULT_OPERATION_LIMIT", DEFAULT_OPERATION_LIMIT)?;

    register_renamed_exception(
        m,
        m.py().get_type::<PyRangeExprError>(),
        "RangeExprError",
        "openjd.expr",
    )?;
    register_renamed_exception(
        m,
        m.py().get_type::<PyFormatStringValidationError>(),
        "FormatStringValidationError",
        "openjd.expr",
    )?;
    register_renamed_exception(
        m,
        m.py().get_type::<PyExpressionError>(),
        "ExpressionError",
        "openjd.expr",
    )?;
    register_renamed_exception(
        m,
        m.py().get_type::<PyExpressionTypeError>(),
        "ExpressionTypeError",
        "openjd.expr",
    )?;
    // Attach the reference's keyword constructor and decoration
    // methods (`with_context`, `message_with_expr_prefix`) to
    // `ExpressionError`. The methods are real `#[pyfunction]`s
    // installed onto the type via `setattr`; Python's descriptor
    // protocol exposes them as bound instance methods.
    // `ExpressionTypeError` inherits them through normal class
    // inheritance.
    expr::errors::attach_expression_error_methods(m)?;

    // ── Model types ──
    m.add_class::<PyDocumentType>()?;
    m.add_class::<PyTemplateSpecificationVersion>()?;
    m.add_class::<PySpecificationRevision>()?;
    m.add_class::<PyModelExtension>()?;
    m.add_class::<PyModelProfile>()?;
    m.add_class::<PyCallerLimits>()?;
    m.add_class::<PyValidationContext>()?;
    m.add_class::<PyJobParameterType>()?;
    m.add_class::<PyTaskParameterType>()?;
    m.add_class::<PyTaskParameterValue>()?;
    m.add_class::<PyJobParameterValue>()?;
    m.add_class::<PyJobTemplate>()?;
    m.add_class::<PyEnvironmentTemplate>()?;
    m.add_class::<PyJob>()?;
    m.add_class::<PyStep>()?;
    m.add_class::<PyStepScript>()?;
    m.add_class::<PyStepActions>()?;
    m.add_class::<PyAction>()?;
    m.add_class::<PyEnvironment>()?;
    m.add_class::<PyEnvironmentScript>()?;
    m.add_class::<PyEnvironmentActions>()?;
    m.add_class::<PyEmbeddedFile>()?;
    m.add_class::<PyJobParameter>()?;
    m.add_class::<PyHostRequirements>()?;
    m.add_class::<PyAmountRequirement>()?;
    m.add_class::<PyAttributeRequirement>()?;
    m.add_class::<PyStepParameterSpace>()?;
    m.add_class::<PyStepDependency>()?;
    m.add_class::<PyCancelationMode>()?;
    m.add_class::<PyStepParameterSpaceIterator>()?;
    m.add_class::<PyStepDependencyGraph>()?;
    m.add_class::<PyStepDependencyNode>()?;
    m.add_class::<PyStepDependencyEdge>()?;
    m.add_class::<PyTaskChunksDefinition>()?;
    m.add_class::<PyIntTaskParameter>()?;
    m.add_class::<PyFloatTaskParameter>()?;
    m.add_class::<PyStringTaskParameter>()?;
    m.add_class::<PyPathTaskParameter>()?;
    m.add_class::<PyChunkIntTaskParameter>()?;
    // Template-time structural pyclasses (mirror openjd_model::template::*)
    m.add_class::<PyTemplateAction>()?;
    m.add_class::<PyTemplateAmountRequirement>()?;
    m.add_class::<PyTemplateAttributeRequirement>()?;
    m.add_class::<PyTemplateCancelationMode>()?;
    m.add_class::<PyTemplateEmbeddedFile>()?;
    m.add_class::<PyTemplateEnvironment>()?;
    m.add_class::<PyTemplateEnvironmentActions>()?;
    m.add_class::<PyTemplateEnvironmentScript>()?;
    m.add_class::<PyTemplateHostRequirements>()?;
    m.add_class::<PySimpleAction>()?;
    m.add_class::<PyTemplateStepActions>()?;
    m.add_class::<PyTemplateStepDependency>()?;
    m.add_class::<PyTemplateStepScript>()?;
    m.add_class::<PyStepTemplate>()?;
    // JobParameterDefinition variants (template-time)
    m.add_class::<PyJobStringParameterDefinition>()?;
    m.add_class::<PyJobIntParameterDefinition>()?;
    m.add_class::<PyJobFloatParameterDefinition>()?;
    m.add_class::<PyJobPathParameterDefinition>()?;
    m.add_class::<PyJobBoolParameterDefinition>()?;
    m.add_class::<PyJobRangeExprParameterDefinition>()?;
    m.add_class::<PyJobListStringParameterDefinition>()?;
    m.add_class::<PyJobListPathParameterDefinition>()?;
    m.add_class::<PyJobListIntParameterDefinition>()?;
    m.add_class::<PyJobListFloatParameterDefinition>()?;
    m.add_class::<PyJobListBoolParameterDefinition>()?;
    m.add_class::<PyJobListListIntParameterDefinition>()?;

    // StepParameterSpaceDefinition + 5 typed task-parameter
    // definitions (template-time, mirror the
    // `template::TaskParameterDefinition` enum).
    m.add_class::<PyStepParameterSpaceDefinition>()?;
    m.add_class::<PyChunksDefinition>()?;
    m.add_class::<PyIntTaskParameterDefinition>()?;
    m.add_class::<PyFloatTaskParameterDefinition>()?;
    m.add_class::<PyStringTaskParameterDefinition>()?;
    m.add_class::<PyPathTaskParameterDefinition>()?;
    m.add_class::<PyChunkIntTaskParameterDefinition>()?;

    // userInterface pyclasses (template-time, mirror the
    // `template::*UserInterface` Rust struct types) plus FileFilter.
    m.add_class::<PyFileFilter>()?;
    m.add_class::<PyStringUserInterface>()?;
    m.add_class::<PyIntUserInterface>()?;
    m.add_class::<PyFloatUserInterface>()?;
    m.add_class::<PyPathUserInterface>()?;
    m.add_class::<PyBoolUserInterface>()?;
    m.add_class::<PyRangeExprUserInterface>()?;
    m.add_class::<PyListSimpleUserInterface>()?;
    m.add_class::<PyListPathUserInterface>()?;
    m.add_class::<PyListIntUserInterface>()?;
    m.add_class::<PyListFloatUserInterface>()?;
    m.add_class::<PyHiddenOnlyUserInterface>()?;

    m.add_function(wrap_pyfunction!(decode_job_template_str, m)?)?;
    m.add_function(wrap_pyfunction!(decode_job_template, m)?)?;
    m.add_function(wrap_pyfunction!(decode_environment_template_str, m)?)?;
    m.add_function(wrap_pyfunction!(decode_environment_template, m)?)?;
    m.add_function(wrap_pyfunction!(py_create_job, m)?)?;
    m.add_function(wrap_pyfunction!(py_create_environment, m)?)?;
    m.add_function(wrap_pyfunction!(py_deserialize_step, m)?)?;
    m.add_function(wrap_pyfunction!(py_preprocess_job_parameters, m)?)?;
    m.add_function(wrap_pyfunction!(py_merge_job_parameter_definitions, m)?)?;
    m.add_function(wrap_pyfunction!(py_evaluate_let_bindings, m)?)?;

    // Capability validation and standard-capability lookup
    m.add_function(wrap_pyfunction!(validate_amount_capability_name, m)?)?;
    m.add_function(wrap_pyfunction!(validate_attribute_capability_name, m)?)?;
    m.add_function(wrap_pyfunction!(standard_amount_capability_names, m)?)?;
    m.add_function(wrap_pyfunction!(standard_attribute_capability_names, m)?)?;
    m.add_function(wrap_pyfunction!(job_parameter_type_expr_spec, m)?)?;
    m.add_function(wrap_pyfunction!(standard_attribute_capabilities, m)?)?;

    register_renamed_exception(
        m,
        m.py().get_type::<PyDecodeValidationError>(),
        "DecodeValidationError",
        "openjd.model._v1.errors",
    )?;
    register_renamed_exception(
        m,
        m.py().get_type::<PyModelValidationError>(),
        "ModelValidationError",
        "openjd.model._v1.errors",
    )?;
    register_renamed_exception(
        m,
        m.py().get_type::<PyUnsupportedSchema>(),
        "UnsupportedSchema",
        "openjd.model._v1.errors",
    )?;

    // ── Sessions types ──
    m.add_class::<PySessionState>()?;
    m.add_class::<PyActionState>()?;
    m.add_class::<PyScriptRunnerState>()?;
    m.add_class::<PyActionStatus>()?;
    m.add_class::<PyActionResult>()?;
    m.add_class::<PySession>()?;
    m.add_class::<PyPosixSessionUser>()?;
    m.add_class::<PyWindowsSessionUser>()?;
    register_renamed_exception(
        m,
        m.py().get_type::<PySessionError>(),
        "SessionError",
        "openjd.sessions._v1",
    )?;
    register_renamed_exception(
        m,
        m.py().get_type::<PyBadCredentialsException>(),
        "BadCredentialsException",
        "openjd.sessions._v1",
    )?;

    // ── Pickle reconstruction helpers ──
    //
    // Module-level functions referenced by the `__reduce__` methods on
    // pyclasses across all three components. Names are part of the
    // pickle wire format (older pickled bytes may reference them) — do
    // not rename without a deprecation cycle.
    m.add_function(wrap_pyfunction!(pickle_helpers::_reconstruct_enum, m)?)?;
    m.add_function(wrap_pyfunction!(pickle_helpers::_reconstruct_kwargs, m)?)?;

    Ok(())
}
