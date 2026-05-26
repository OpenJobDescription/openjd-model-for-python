// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use openjd_model::ModelError;
use pyo3::prelude::*;

use crate::expr::errors::{PyExpressionError, PyFormatStringValidationError};

pyo3::create_exception!(
    _openjd_rs,
    PyDecodeValidationError,
    pyo3::exceptions::PyValueError
);
pyo3::create_exception!(
    _openjd_rs,
    PyModelValidationError,
    pyo3::exceptions::PyValueError
);
pyo3::create_exception!(
    _openjd_rs,
    PyUnsupportedSchema,
    pyo3::exceptions::PyValueError
);

/// Resolve the Python-only ``CompatibilityError`` class from the
/// ``openjd.model._v1`` module and instantiate it with ``msg``.
///
/// ``CompatibilityError`` is a Python-side class (a thin
/// ``ValueError`` subclass) declared in
/// ``src/openjd/model/_v1/__init__.py``. It can't be created with
/// ``pyo3::create_exception!`` because it has to live in the Python
/// module surface for legacy compatibility (callers do
/// ``from openjd.model._v1 import CompatibilityError``). Importing
/// from Rust at error-mapping time is cheap (the GIL is already
/// held in every call site that invokes ``model_err_to_py`` — they
/// all run inside a ``#[pyfunction]`` or ``#[pymethods]`` body —
/// and ``CompatibilityError`` errors are rare in practice).
fn compatibility_err(msg: String) -> PyErr {
    Python::attach(|py| {
        match py
            .import("openjd.model._v1")
            .and_then(|m| m.getattr("CompatibilityError"))
            .and_then(|cls| cls.call1((msg.clone(),)))
        {
            Ok(instance) => PyErr::from_value(instance),
            // Either ``openjd.model._v1`` isn't loaded yet (shouldn't
            // happen — the Python wrapper module is imported before
            // any binding call is reachable) or
            // ``CompatibilityError(msg)`` failed to construct. Fall
            // back to the generic class so the failure surfaces as
            // *some* error rather than a panic.
            Err(_) => PyModelValidationError::new_err(msg),
        }
    })
}

pub(crate) fn model_err_to_py(e: ModelError) -> PyErr {
    match e {
        ModelError::DecodeValidation(msg) => PyDecodeValidationError::new_err(msg),
        ModelError::ModelValidation(errors) => PyModelValidationError::new_err(errors.to_string()),
        ModelError::UnsupportedSchema(msg) => PyUnsupportedSchema::new_err(msg),
        // Surface format-string failures via the dedicated
        // FormatStringValidationError class — matches the v0
        // reference's exception class hierarchy. The wrapper
        // re-exports this as ``FormatStringError`` for legacy
        // callers.
        ModelError::FormatStringError { message, .. } => {
            PyFormatStringValidationError::new_err(message)
        }
        // Expression-evaluation errors thrown by
        // ``openjd_expr`` during template/job processing surface
        // as ``ExpressionError`` (the same class
        // ``openjd.expr.evaluate_expression`` raises).
        ModelError::Expression(expr_err) => PyExpressionError::new_err(expr_err.to_string()),
        // Compatibility errors are the Python-side
        // ``CompatibilityError`` (a ``ValueError`` subclass).
        ModelError::Compatibility(msg) => compatibility_err(msg),
        _ => PyModelValidationError::new_err(e.to_string()),
    }
}
