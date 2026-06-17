// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

//! `openjd.expr` exception classes.
//!
//! `ExpressionError` and `ExpressionTypeError` are
//! `pyo3::create_exception!`-built `ValueError` subclasses, with
//! the reference's keyword constructor and decoration methods
//! (`with_context`, `message_with_expr_prefix`) attached to the
//! type at extension-module init time.
//!
//! ## Why `create_exception!` plus attached methods?
//!
//! The cleanest model would be `#[pyclass(extends = PyValueError)]`
//! with `#[pymethods]` declaring everything natively. PyO3 only
//! supports subclassing built-in exceptions on Python 3.12+ when
//! the `abi3` feature is enabled (per PyO3's exception guide), and
//! this crate targets `abi3-py39` to support every interpreter
//! from 3.9 forward. So `#[pyclass(extends = PyValueError)]` is off
//! the table for these classes.
//!
//! The next-cleanest model — and the one used here — is to keep
//! the `create_exception!` declarations but attach the custom
//! `__init__` and decoration methods at module init via the
//! standard Python `exec` mechanism. The method bodies live as
//! `&'static str` constants in this file (single source of truth),
//! get compiled into real Python `function` objects so the
//! descriptor protocol binds them correctly to instances, and are
//! installed onto the type via `setattr`. `ExpressionTypeError`
//! inherits the methods through normal class inheritance — no
//! separate attachment needed.
//!
//! `RangeExprError` and `FormatStringValidationError` carry no
//! extra state and use plain `create_exception!` with no
//! attachments.

use pyo3::prelude::*;
use pyo3::types::PyDict;

// ── Exception classes ───────────────────────────────────────────

pyo3::create_exception!(
    _openjd_rs,
    PyExpressionError,
    pyo3::exceptions::PyValueError
);
pyo3::create_exception!(_openjd_rs, PyExpressionTypeError, PyExpressionError);
pyo3::create_exception!(_openjd_rs, PyRangeExprError, pyo3::exceptions::PyValueError);
pyo3::create_exception!(
    _openjd_rs,
    PyFormatStringValidationError,
    pyo3::exceptions::PyValueError
);

// ── Method bodies (executed at module init) ─────────────────────
//
// The reference `ExpressionError` from the pure-Python branch
// exposes:
//
//   * `__init__(message, *, expr=None, node=None, lineno=None,
//      col_offset=None)` — store structured location info as
//      instance attributes alongside the standard
//      `BaseException.args` payload.
//   * `with_context(expr, node=None)` — return a new exception
//      decorated with the supplied expression source. Innermost
//      context wins: if `self` already has `expr` set, the call
//      is a no-op.
//   * `message_with_expr_prefix(prefix)` — render the error with
//      a custom prefix on the expression source line and the
//      caret column shifted accordingly. Falls back to
//      `str(self)` for context-free or multi-line errors.
//
// Rendering shape of `message_with_expr_prefix` (the "printing"
// path). When `expr` is attached and single-line, it produces a
// three-line, caret-annotated message:
//
//     <base message>
//       <prefix><expr>
//               ^
//
//   * line 1 is `self._base_message` (the original message text);
//   * line 2 is the expression source, two-space-indented, with
//     the caller-supplied `prefix` prepended
//     (`"  " + prefix + expr`);
//   * line 3 is emitted only when `col_offset is not None`: a
//     caret under the offending column. The caret is shifted right
//     by `len(prefix)` (`" " * (col_offset + len(prefix))`) so it
//     stays aligned with the source character after the prefix
//     pushes the expression text rightward.
//
// If `expr is None` or the expression is multi-line (`"\n" in
// expr`), it returns plain `str(self)` with no caret annotation.
//
// Implementing these as `#[pyfunction]`s installed via `setattr`
// would *almost* work, except that PyO3's `#[pyfunction]` builds
// a `PyCFunction` (builtin function) which is not bound to its
// instance via the standard descriptor protocol. Compiling these
// as plain Python `def`s — once, at module init — produces real
// `function` objects that bind correctly when looked up through
// an instance (`err.with_context(...)` resolves to a bound method
// just like a `def` declared in a class body).
const ATTACHED_METHODS_SOURCE: &str = r#"
def __init__(self, *args, expr=None, node=None, lineno=None, col_offset=None):
    super(ExpressionError, self).__init__(*args)
    self.expr = expr
    self.node = node
    self.lineno = lineno
    self.col_offset = col_offset
    self._base_message = args[0] if args else ""


def with_context(self, expr, node=None):
    """Return a new ExpressionError carrying ``expr`` (and
    optionally ``node``) as decoration. If ``self`` already has
    expression context attached, returns ``self`` unchanged."""
    if self.expr is not None:
        return self
    cls = type(self)
    new = cls(
        self._base_message,
        expr=expr,
        node=node if node is not None else self.node,
        lineno=self.lineno,
        col_offset=self.col_offset,
    )
    return new


def message_with_expr_prefix(self, prefix):
    """Render the error with ``prefix`` inserted before the
    expression source line and the caret indicator shifted
    accordingly. Falls back to ``str(self)`` for errors without
    ``expr`` attached or for multi-line expressions."""
    expr = self.expr
    if expr is None or "\n" in expr:
        return str(self)
    base = self._base_message
    lines = [base, "  " + prefix + expr]
    if self.col_offset is not None:
        lines.append("  " + " " * (self.col_offset + len(prefix)) + "^")
    return "\n".join(lines)
"#;

/// Compile and install the keyword-constructor and decoration
/// methods on `ExpressionError`. Called from the extension module
/// init in `lib.rs` after `register_renamed_exception` has set
/// the canonical `__module__` / `__name__` / `__qualname__`.
///
/// `ExpressionTypeError` inherits the methods through normal
/// Python class inheritance — no separate attachment is needed.
pub(crate) fn attach_expression_error_methods(m: &Bound<'_, PyModule>) -> PyResult<()> {
    let py = m.py();
    let cls = py.get_type::<PyExpressionError>();
    let globals = PyDict::new(py);
    // The `super(ExpressionError, self)` lookup inside `__init__`
    // needs the class to be reachable in the namespace where the
    // function is compiled.
    globals.set_item("ExpressionError", cls.clone())?;
    py.run(
        &std::ffi::CString::new(ATTACHED_METHODS_SOURCE).unwrap(),
        Some(&globals),
        None,
    )?;
    for name in ["__init__", "with_context", "message_with_expr_prefix"] {
        let func = globals.get_item(name)?.ok_or_else(|| {
            pyo3::exceptions::PyRuntimeError::new_err(format!(
                "internal error: ExpressionError method {name} was not compiled"
            ))
        })?;
        cls.setattr(name, func)?;
    }
    Ok(())
}

// ── Conversion helpers ───────────────────────────────────────────

/// Map a Rust-side `ExpressionError` to a Python-side
/// `PyExpressionError` instance.
pub(crate) fn expr_err_to_py(e: openjd_expr::error::ExpressionError) -> PyErr {
    PyExpressionError::new_err(e.to_string())
}

/// Map a Rust-side `FormatStringValidationError` to a Python-side
/// `PyFormatStringValidationError` instance. The Rust struct
/// implements `Display` as
/// `"Failed to parse interpolation expression at [start, end]. message"`,
/// which we forward verbatim. Structured fields (`input`, `start`,
/// `end`, `expression_error`) are not currently exposed to Python —
/// callers who need them should match on the message string or
/// catch `ExpressionError` directly via `evaluate_*`. If a real
/// structured access need surfaces, the helper can grow into
/// `new_err((message, input, start, end))` populating instance
/// attributes.
pub(crate) fn format_string_validation_err_to_py(
    e: openjd_expr::format_string::FormatStringValidationError,
) -> PyErr {
    PyFormatStringValidationError::new_err(e.to_string())
}
