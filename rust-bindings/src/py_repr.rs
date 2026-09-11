// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

//! Rendering values into `__repr__` output that Python can parse.
//!
//! `format!("{:?}", s)` is not a Python literal writer. Rust's `Debug` for
//! `str` special-cases only the quote, the backslash, and NUL, tab, CR and
//! LF; every other control character and every non-printable falls through
//! to Rust's brace form, `\u{1b}` or `\u{a0}`. Python wants exactly four
//! hex digits after `\u`, so those do not parse. ESC is the one to keep in
//! mind: ANSI colour sequences in captured process output hit this far more
//! often than any exotic codepoint does.
//!
//! Delegating to CPython's own `repr()` removes the guesswork rather than
//! reimplementing its escaping table: the output is by construction
//! whatever the running interpreter produces, including its per-string
//! choice of quote character.
//!
//! Scope: the `sessions` reprs route through here. Reprs under `model/`
//! and the rest of `expr/` still use `{:?}` or hand-rolled quoting and
//! carry the same defect — see the tracking note in the pull request that
//! introduced this module. A new repr should use these helpers.
//!
//! Callers must not hold a lock across `py_str`: it re-enters the
//! interpreter, which can run arbitrary Python (allocation may trigger a
//! GC pass and with it `__del__` and weakref callbacks). Read what you
//! need out from under the guard, drop it, then format.

use pyo3::prelude::*;
use pyo3::types::{PyString, PyStringMethods};

/// CPython's `repr()` of `value`, ready to embed in a `__repr__`.
pub(crate) fn py_str(py: Python<'_>, value: &str) -> PyResult<String> {
    // `to_cow` reads the UTF-8 directly and propagates failure. Going via
    // `to_string()` would resolve to PyO3's `Display`, which calls `str()`
    // on the object -- a second interpreter round-trip whose error has
    // nowhere to go but a panic out of `__repr__`.
    Ok(PyString::new(py, value).repr()?.to_cow()?.into_owned())
}

/// An optional `int` as Python spells it. `Debug` would emit `Some(0)`,
/// which evaluates to a `NameError`.
pub(crate) fn py_opt_int(value: Option<i32>) -> String {
    match value {
        Some(v) => v.to_string(),
        None => "None".to_string(),
    }
}
