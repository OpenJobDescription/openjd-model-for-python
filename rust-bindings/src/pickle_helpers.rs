// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

//! Pickle reconstruction helpers shared across the binding.
//!
//! Most pyclasses in this crate implement `__reduce__` by returning a
//! 2-tuple `(callable, args)` where `callable` is one of the helpers
//! below or a method on the type itself. Centralising these helpers
//! here keeps every type's `__reduce__` to a single line.
//!
//! Three patterns are supported:
//!
//! 1. **Enum-by-name** (`_reconstruct_enum`): for `#[pyclass]` enums
//!    whose variants are reachable as class attributes (e.g.
//!    `PathFormat.POSIX`). The variant name and qualified class name
//!    fully describe the value.
//! 2. **Constructor-with-kwargs** (`_reconstruct_kwargs`): for
//!    `#[pyclass]` value types whose `#[new]` accepts a keyword set
//!    that round-trips with all of the type's getters.
//! 3. **Constructor-from-string** (the type's own `__init__(str)`):
//!    for `ExprType`, `RangeExpr`, `FormatString` etc. whose string
//!    form is canonical. These reduce to `(cls, (str(self),))`
//!    directly without needing a helper.
//!
//! The helpers are exposed as Python-level `_openjd_rs._reconstruct_*`
//! functions so that pickled bytes serialised by older interpreter
//! sessions can still be loaded (as long as the helper names remain
//! stable).

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyType};
/// Reconstruct an enum-class instance by attribute lookup.
///
/// Equivalent to ``getattr(cls, name)`` — used by `__reduce__` on
/// `#[pyclass]` enums (`PathFormat`, `ActionState`, etc.) so that
/// ``pickle.loads(pickle.dumps(PathFormat.POSIX))`` round-trips back
/// to the same singleton enum value.
#[pyfunction]
pub(crate) fn _reconstruct_enum<'py>(
    cls: &Bound<'py, PyType>,
    name: &str,
) -> PyResult<Bound<'py, PyAny>> {
    cls.getattr(name)
}

/// Reconstruct a value-typed `#[pyclass]` instance by calling its
/// `__init__` (or any other callable) with the supplied keyword
/// arguments.
///
/// Used by `__reduce__` on flat value types whose `#[new]` accepts
/// every getter as a keyword argument (e.g. `CallerLimits`,
/// `PosixSessionUser`). Also accepts classmethod accessors —
/// `ActionStatus._from_state` for instance — for types where the
/// public `#[new]` doesn't expose every internal field.
#[pyfunction]
pub(crate) fn _reconstruct_kwargs<'py>(
    callable: &Bound<'py, PyAny>,
    kwargs: &Bound<'py, PyDict>,
) -> PyResult<Bound<'py, PyAny>> {
    callable.call((), Some(kwargs))
}
