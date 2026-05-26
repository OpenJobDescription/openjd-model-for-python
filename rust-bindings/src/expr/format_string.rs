// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use pyo3::prelude::*;
use pyo3::types::PyType;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_expr::format_string::{FormatString, FormatStringOptions};

use crate::expr::errors::{expr_err_to_py, format_string_validation_err_to_py};
use crate::expr::evaluate::profile_for_call;
use crate::expr::expr_value::PyExprValue;
use crate::expr::profile::PyExprProfile;
use crate::expr::symbol_table::extract_symtab;

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.expr", name = "FormatString", from_py_object)]
#[derive(Clone)]
pub(crate) struct PyFormatString {
    pub(crate) inner: FormatString,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyFormatString {
    #[new]
    fn new(input: &str) -> PyResult<Self> {
        FormatString::new(input)
            .map(|inner| PyFormatString { inner })
            .map_err(expr_err_to_py)
    }

    #[pyo3(signature = (symtab, *, profile=None))]
    fn resolve_string(
        &self,
        symtab: &Bound<'_, pyo3::PyAny>,
        profile: Option<&PyExprProfile>,
    ) -> PyResult<String> {
        let st = extract_symtab(symtab)?;
        let lib = profile_for_call(profile);
        let opts = FormatStringOptions::new().with_library(&lib);
        self.inner
            .resolve_string_with(&st, &opts)
            .map_err(expr_err_to_py)
    }

    #[pyo3(signature = (symtab, *, profile=None))]
    fn resolve(
        &self,
        symtab: &Bound<'_, pyo3::PyAny>,
        profile: Option<&PyExprProfile>,
    ) -> PyResult<PyExprValue> {
        let st = extract_symtab(symtab)?;
        let lib = profile_for_call(profile);
        let opts = FormatStringOptions::new().with_library(&lib);
        self.inner
            .resolve_with(&st, &opts)
            .map(|inner| PyExprValue { inner })
            .map_err(expr_err_to_py)
    }

    fn raw(&self) -> &str {
        self.inner.raw()
    }

    fn has_complex_expressions(&self) -> bool {
        self.inner.has_complex_expressions()
    }

    fn expression_names(&self) -> Vec<String> {
        self.inner
            .expression_names()
            .into_iter()
            .map(|s| s.to_string())
            .collect()
    }

    fn is_literal(&self) -> bool {
        self.inner.is_literal()
    }

    /// Copy symbol table entries referenced by this format string's expressions
    /// from `source` into `dest`. Only copies the actual values referenced,
    /// stopping at property/method access (e.g. for `Param.Name.upper()`,
    /// copies `Param.Name` but not `Param.Name.upper`).
    fn copy_used_symtab_values(
        &self,
        source: &crate::expr::PySymbolTable,
        dest: &Bound<'_, pyo3::PyAny>,
    ) -> PyResult<()> {
        let cell: &Bound<'_, crate::expr::PySymbolTable> = dest.cast()?;
        let mut guard = cell.borrow_mut();
        self.inner
            .copy_used_symtab_values(&source.inner, &mut guard.inner);
        Ok(())
    }

    /// Validate every ``{{...}}`` interpolation against ``symtab``,
    /// raising `FormatStringValidationError` on the first failure.
    ///
    /// Per the spec, callers populate the symbol table with
    /// `ExprValue.unresolved(T)` placeholders for symbols whose
    /// concrete values aren't known at validation time — the
    /// evaluator's unresolved-propagation rules then drive type
    /// checking through the expression tree.
    ///
    /// Mirrors the Rust crate's
    /// `FormatString::validate_expressions(symtab, lib)`. Returns
    /// `None` on success.
    #[pyo3(signature = (symtab, *, profile=None))]
    fn validate_expressions(
        &self,
        symtab: &Bound<'_, pyo3::PyAny>,
        profile: Option<&PyExprProfile>,
    ) -> PyResult<()> {
        let st = extract_symtab(symtab)?;
        let lib = profile_for_call(profile);
        self.inner
            .validate_expressions(&st, &lib)
            .map_err(format_string_validation_err_to_py)
    }

    fn __str__(&self) -> &str {
        self.inner.raw()
    }

    fn __repr__(&self) -> String {
        format!("FormatString(\"{}\")", self.inner.raw())
    }

    /// Two `FormatString`s compare equal when their raw source
    /// strings are equal. Lexically distinct inputs that would
    /// resolve to the same value (e.g. `"{{ Param.X }}"` vs
    /// `"{{Param.X}}"`) compare unequal — this preserves source
    /// identity rather than canonicalising whitespace.
    fn __eq__(&self, other: &Bound<'_, pyo3::PyAny>) -> PyResult<bool> {
        let Ok(rhs) = other.extract::<PyRef<'_, PyFormatString>>() else {
            return Ok(false);
        };
        Ok(self.inner.raw() == rhs.inner.raw())
    }

    /// Hash on the raw source string — same contract as `__eq__`.
    fn __hash__(&self) -> u64 {
        use std::hash::{DefaultHasher, Hash, Hasher};
        let mut h = DefaultHasher::new();
        self.inner.raw().hash(&mut h);
        h.finish()
    }

    /// Pickle support — round-trips through the raw input string.
    fn __reduce__<'py>(&self, py: Python<'py>) -> PyResult<(Bound<'py, PyType>, (String,))> {
        Ok((py.get_type::<Self>(), (self.inner.raw().to_string(),)))
    }
}

#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyfunction(module = "openjd._openjd_rs")
)]
#[pyfunction]
pub(crate) fn escape_format_string(value: &str) -> String {
    openjd_expr::format_string::escape_format_string(value)
}
