// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use pyo3::prelude::*;
use pyo3::types::PyType;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_expr::symbol_table::SymbolTable;

use crate::expr::errors::expr_err_to_py;
use crate::expr::evaluate::profile_for_call;
use crate::expr::expr_type::PyExprType;
use crate::expr::expr_value::PyExprValue;
use crate::expr::path_format::PyPathFormat;
use crate::expr::profile::PyExprProfile;
use crate::expr::symbol_table::extract_symtab;

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.expr", name = "ParsedExpression")]
pub(crate) struct PyParsedExpression {
    inner: openjd_expr::eval::ParsedExpression,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyParsedExpression {
    fn __repr__(&self) -> String {
        format!("ParsedExpression(\"{}\")", self.inner.expression())
    }

    #[getter]
    fn accessed_symbols(&self) -> std::collections::HashSet<String> {
        self.inner.accessed_symbols().clone()
    }

    #[getter]
    fn called_functions(&self) -> std::collections::HashSet<String> {
        self.inner.called_functions().clone()
    }

    #[getter]
    fn local_bindings(&self) -> std::collections::HashSet<String> {
        self.inner.local_bindings().clone()
    }

    #[getter]
    fn expr(&self) -> &str {
        self.inner.expression()
    }

    /// Evaluate the expression and return the resulting :class:`ExprValue`.
    ///
    /// Use :meth:`evaluate_with_metrics` instead when you also need the
    /// resource-usage counters (peak memory, operation count).
    #[pyo3(signature = (*, values=None, profile=None, target_type=None, path_format=None, memory_limit=None, operation_limit=None))]
    #[allow(clippy::too_many_arguments)] // signature mirrors the documented evaluate() Python API
    fn evaluate(
        &self,
        values: Option<&Bound<'_, pyo3::PyAny>>,
        profile: Option<&PyExprProfile>,
        target_type: Option<&PyExprType>,
        path_format: Option<PyPathFormat>,
        memory_limit: Option<usize>,
        operation_limit: Option<usize>,
    ) -> PyResult<PyExprValue> {
        let symtab;
        let symtab_refs: Vec<&SymbolTable> = if let Some(v) = values {
            symtab = extract_symtab(v)?;
            vec![&symtab]
        } else {
            vec![]
        };

        let lib = profile_for_call(profile);
        let mut builder = self.inner.with_library(&lib);

        if let Some(ml) = memory_limit {
            builder = builder.with_memory_limit(ml);
        }
        if let Some(ol) = operation_limit {
            builder = builder.with_operation_limit(ol);
        }
        if let Some(pf) = path_format {
            builder = builder.with_path_format(pf.into());
        }
        if let Some(tt) = target_type {
            builder = builder.with_target_type(&tt.inner);
        }

        let value = builder.evaluate(&symtab_refs).map_err(expr_err_to_py)?;
        Ok(PyExprValue { inner: value })
    }

    /// Type-check the expression against a symbol table of (typically
    /// unresolved) typed placeholders, without extracting a concrete value.
    ///
    /// Succeeds when the expression is well-typed for the given symbol types —
    /// including when the result is an unresolved value that merely depends on
    /// a runtime symbol — and raises only on a genuine type/evaluation error.
    /// Unlike :meth:`evaluate`, it discards the result, so it never raises the
    /// "cannot extract value from unresolved" boundary error; callers no longer
    /// need to sniff the error message to tell a real type error from a
    /// runtime-dependent one.
    #[pyo3(signature = (*, values=None, profile=None))]
    fn typecheck(
        &self,
        values: Option<&Bound<'_, pyo3::PyAny>>,
        profile: Option<&PyExprProfile>,
    ) -> PyResult<()> {
        let symtab;
        let symtab_refs: Vec<&SymbolTable> = if let Some(v) = values {
            symtab = extract_symtab(v)?;
            vec![&symtab]
        } else {
            vec![]
        };
        let lib = profile_for_call(profile);
        self.inner
            .with_library(&lib)
            .evaluate(&symtab_refs)
            .map_err(expr_err_to_py)?;
        Ok(())
    }

    /// Evaluate the expression and return an :class:`EvalResult` with the
    /// resulting value alongside the per-call resource-usage metrics
    /// (``peak_memory`` in bytes, ``operation_count``).
    ///
    /// This mirrors ``ParsedExpression::evaluate_with_metrics`` on the
    /// underlying ``openjd_expr`` Rust crate. Use :meth:`evaluate` when
    /// you don't need the metrics — it skips the metric-tracking overhead.
    #[pyo3(signature = (*, values=None, profile=None, target_type=None, path_format=None, memory_limit=None, operation_limit=None))]
    #[allow(clippy::too_many_arguments)] // signature mirrors evaluate()
    fn evaluate_with_metrics(
        &self,
        values: Option<&Bound<'_, pyo3::PyAny>>,
        profile: Option<&PyExprProfile>,
        target_type: Option<&PyExprType>,
        path_format: Option<PyPathFormat>,
        memory_limit: Option<usize>,
        operation_limit: Option<usize>,
    ) -> PyResult<PyEvalResult> {
        let symtab;
        let symtab_refs: Vec<&SymbolTable> = if let Some(v) = values {
            symtab = extract_symtab(v)?;
            vec![&symtab]
        } else {
            vec![]
        };

        let lib = profile_for_call(profile);
        let mut builder = self.inner.with_library(&lib);

        if let Some(ml) = memory_limit {
            builder = builder.with_memory_limit(ml);
        }
        if let Some(ol) = operation_limit {
            builder = builder.with_operation_limit(ol);
        }
        if let Some(pf) = path_format {
            builder = builder.with_path_format(pf.into());
        }
        if let Some(tt) = target_type {
            builder = builder.with_target_type(&tt.inner);
        }

        let result = builder
            .evaluate_with_metrics(&symtab_refs)
            .map_err(expr_err_to_py)?;
        Ok(PyEvalResult {
            value: PyExprValue {
                inner: result.value,
            },
            peak_memory: result.peak_memory,
            operation_count: result.operation_count,
        })
    }
}

/// Result of :meth:`ParsedExpression.evaluate_with_metrics`.
///
/// Bundles the evaluated :class:`ExprValue` together with the
/// per-call resource counters tracked by the evaluator. Mirrors
/// the ``EvalResult`` struct in the underlying ``openjd_expr`` Rust
/// crate (``value``, ``peak_memory``, ``operation_count``).
///
/// All three fields are populated atomically by a single call —
/// unlike the previous racy ``ParsedExpression.peak_memory_usage``
/// / ``operation_count`` attributes, an ``EvalResult`` is local to
/// its caller and safe to share or compare across threads.
#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.expr", name = "EvalResult", frozen, from_py_object)]
#[derive(Clone)]
pub(crate) struct PyEvalResult {
    value: PyExprValue,
    peak_memory: usize,
    operation_count: usize,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyEvalResult {
    #[new]
    #[pyo3(signature = (value, peak_memory, operation_count))]
    fn new(value: PyExprValue, peak_memory: usize, operation_count: usize) -> Self {
        PyEvalResult {
            value,
            peak_memory,
            operation_count,
        }
    }

    /// The evaluated value.
    #[getter]
    fn value(&self) -> PyExprValue {
        self.value.clone()
    }

    /// Peak memory consumed during evaluation, in bytes.
    #[getter]
    fn peak_memory(&self) -> usize {
        self.peak_memory
    }

    /// Number of evaluator operations performed.
    #[getter]
    fn operation_count(&self) -> usize {
        self.operation_count
    }

    fn __repr__(&self) -> String {
        format!(
            "EvalResult(value={}, peak_memory={}, operation_count={})",
            self.value.inner.repr_python(),
            self.peak_memory,
            self.operation_count,
        )
    }

    fn __eq__(&self, other: &PyEvalResult) -> bool {
        self.value.inner.equals(&other.value.inner)
            && self.peak_memory == other.peak_memory
            && self.operation_count == other.operation_count
    }

    /// Pickle support — round-trips through the constructor.
    fn __reduce__<'py>(
        &self,
        py: Python<'py>,
    ) -> PyResult<(Bound<'py, PyType>, (PyExprValue, usize, usize))> {
        Ok((
            py.get_type::<Self>(),
            (self.value.clone(), self.peak_memory, self.operation_count),
        ))
    }
}

#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyfunction(module = "openjd._openjd_rs")
)]
#[pyfunction]
pub(crate) fn parse_expression(expr: &str) -> PyResult<PyParsedExpression> {
    openjd_expr::eval::ParsedExpression::new(expr)
        .map(|inner| PyParsedExpression { inner })
        .map_err(expr_err_to_py)
}
