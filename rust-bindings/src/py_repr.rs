// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

//! Rendering values into `__repr__` output that Python can parse.
//!
//! `format!("{:?}", s)` is not a Python literal writer. Rust's `Debug` for
//! `str` happens to agree with Python on the quote, the backslash and the
//! C0 controls, but it renders anything else non-printable as `\u{a0}`,
//! and CPython wants exactly four hex digits after `\u`. A repr carrying
//! such a character does not parse at all, so a value that arrives from
//! outside -- captured process output, a template-supplied name -- can
//! corrupt the repr of the object holding it.
//!
//! Delegating to CPython's own `repr()` retires the bug class instead of
//! reimplementing its escaping table: the output is by construction
//! whatever the running interpreter produces, including its per-string
//! choice of quote character.

use pyo3::prelude::*;
use pyo3::types::PyString;

/// CPython's `repr()` of `value`, ready to embed in a `__repr__`.
pub(crate) fn py_str(py: Python<'_>, value: &str) -> PyResult<String> {
    Ok(PyString::new(py, value).repr()?.to_string())
}

/// An optional `int` as Python spells it. `Debug` would emit `Some(0)`,
/// which evaluates to a `NameError`.
pub(crate) fn py_opt_int(value: Option<i32>) -> String {
    match value {
        Some(v) => v.to_string(),
        None => "None".to_string(),
    }
}
