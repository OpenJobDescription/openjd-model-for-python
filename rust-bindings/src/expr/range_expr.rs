// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use pyo3::prelude::*;
use pyo3::types::PyType;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_expr::range_expr::{IntRange, RangeExpr};

use crate::expr::errors::PyRangeExprError;

/// A single contiguous integer range: ``[start, end]`` inclusive
/// with a positive ``step``. Both ``start`` and ``end`` are always
/// included in the iteration set, and ``step`` is always positive
/// (descending input ranges are normalised to ascending form
/// upstream).
///
/// Returned by ``RangeExpr.ranges()``. Pinned for parity with the
/// v0 reference's ``IntRange`` shape.
#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.expr", name = "IntRange", frozen, from_py_object)]
#[derive(Clone)]
pub(crate) struct PyIntRange {
    pub(crate) inner: IntRange,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyIntRange {
    #[new]
    #[pyo3(signature = (start, end, step=1))]
    fn new(start: i64, end: i64, step: i64) -> PyResult<Self> {
        IntRange::new(start, end, step)
            .map(|inner| PyIntRange { inner })
            .map_err(|e| PyRangeExprError::new_err(e.to_string()))
    }

    /// Smallest value in the range (always <= ``end``).
    #[getter]
    fn start(&self) -> i64 {
        self.inner.start()
    }

    /// Largest value in the range (always >= ``start``).
    #[getter]
    fn end(&self) -> i64 {
        self.inner.end()
    }

    /// Step between successive values (always > 0).
    #[getter]
    fn step(&self) -> i64 {
        self.inner.step()
    }

    fn __len__(&self) -> usize {
        self.inner.len()
    }

    fn __contains__(&self, value: i64) -> bool {
        self.inner.contains(value)
    }

    fn __iter__(&self) -> PyIntRangeIter {
        PyIntRangeIter {
            values: self.inner.iter().collect(),
            pos: 0,
        }
    }

    fn __eq__(&self, other: &PyIntRange) -> bool {
        self.inner == other.inner
    }

    fn __hash__(&self) -> u64 {
        use std::hash::{Hash, Hasher};
        let mut h = std::collections::hash_map::DefaultHasher::new();
        self.inner.hash(&mut h);
        h.finish()
    }

    fn __repr__(&self) -> String {
        format!(
            "IntRange(start={}, end={}, step={})",
            self.inner.start(),
            self.inner.end(),
            self.inner.step()
        )
    }

    /// Pickle support — round-trips through the constructor.
    fn __reduce__<'py>(&self, py: Python<'py>) -> PyResult<(Bound<'py, PyType>, (i64, i64, i64))> {
        Ok((
            py.get_type::<Self>(),
            (self.inner.start(), self.inner.end(), self.inner.step()),
        ))
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.expr")]
pub(crate) struct PyIntRangeIter {
    values: Vec<i64>,
    pos: usize,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyIntRangeIter {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(&mut self) -> Option<i64> {
        if self.pos < self.values.len() {
            let v = self.values[self.pos];
            self.pos += 1;
            Some(v)
        } else {
            None
        }
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.expr", name = "RangeExpr", from_py_object)]
#[derive(Clone)]
pub(crate) struct PyRangeExpr {
    pub(crate) inner: RangeExpr,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyRangeExpr {
    #[new]
    fn new(expr: &str) -> PyResult<Self> {
        expr.parse::<RangeExpr>()
            .map(|inner| PyRangeExpr { inner })
            .map_err(|e| PyRangeExprError::new_err(e.to_string()))
    }

    #[staticmethod]
    fn from_str(expr: &str) -> PyResult<Self> {
        expr.parse::<RangeExpr>()
            .map(|inner| PyRangeExpr { inner })
            .map_err(|e| PyRangeExprError::new_err(e.to_string()))
    }

    /// Build a `RangeExpr` from a list of values. Values may be ints,
    /// strs (parsed as ints), or a mix. Duplicates are removed and the
    /// final range is sorted ascending.
    ///
    /// Raises ``ValueError`` if the list is empty (matching the
    /// pure-Python reference).
    #[staticmethod]
    fn from_list(values: &Bound<'_, pyo3::PyAny>) -> PyResult<Self> {
        let mut ints: Vec<i64> = Vec::new();
        for item in values.try_iter()? {
            let item = item?;
            if let Ok(i) = item.extract::<i64>() {
                ints.push(i);
            } else if let Ok(s) = item.extract::<String>() {
                let parsed: i64 = s.trim().parse().map_err(|_| {
                    pyo3::exceptions::PyValueError::new_err(format!(
                        "Range value {s:?} is not a valid integer"
                    ))
                })?;
                ints.push(parsed);
            } else {
                return Err(pyo3::exceptions::PyTypeError::new_err(format!(
                    "Range value must be int or str, got {}",
                    item.get_type().name()?
                )));
            }
        }
        if ints.is_empty() {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "Range expression cannot be empty",
            ));
        }
        Ok(PyRangeExpr {
            inner: RangeExpr::from_values(ints)
                .map_err(|e| PyRangeExprError::new_err(e.to_string()))?,
        })
    }

    /// Smallest value in the range expression.
    #[getter]
    fn start(&self) -> PyResult<i64> {
        self.inner
            .ranges()
            .first()
            .map(|r| r.start())
            .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("Range expression is empty"))
    }

    /// Largest value in the range expression.
    #[getter]
    fn end(&self) -> PyResult<i64> {
        self.inner
            .ranges()
            .last()
            .map(|r| r.end())
            .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("Range expression is empty"))
    }

    fn __len__(&self) -> usize {
        self.inner.len()
    }

    fn __eq__(&self, other: &PyRangeExpr) -> bool {
        self.inner == other.inner
    }

    fn __contains__(&self, value: i64) -> bool {
        self.inner.contains(value)
    }

    fn __getitem__(&self, index: isize) -> PyResult<i64> {
        let len = self.inner.len();
        let idx = if index < 0 {
            len as isize + index
        } else {
            index
        };
        if idx < 0 || idx as usize >= len {
            return Err(pyo3::exceptions::PyIndexError::new_err(
                "index out of range",
            ));
        }
        self.inner
            .get(idx as i64)
            .ok_or_else(|| pyo3::exceptions::PyIndexError::new_err("index out of range"))
    }

    fn __iter__(&self) -> PyRangeExprIter {
        PyRangeExprIter {
            values: self.inner.to_vec(),
            pos: 0,
        }
    }

    fn __str__(&self) -> String {
        self.inner.to_string()
    }

    fn __repr__(&self) -> String {
        format!("RangeExpr(\"{}\")", self.inner)
    }

    fn ranges(&self) -> Vec<PyIntRange> {
        self.inner
            .ranges()
            .iter()
            .map(|r| PyIntRange { inner: r.clone() })
            .collect()
    }

    /// Hash defers to the Rust `RangeExpr` impl (which hashes the
    /// underlying `Vec<IntRange>`), so two `RangeExpr` instances
    /// that compare equal hash equal. Like all PyO3-derived hashes,
    /// the value is interpreter-session-local and not stable across
    /// processes.
    fn __hash__(&self) -> u64 {
        use std::hash::{Hash, Hasher};
        let mut h = std::collections::hash_map::DefaultHasher::new();
        self.inner.hash(&mut h);
        h.finish()
    }

    /// Pickle support — round-trips through the canonical string
    /// representation (e.g. `"1-10"`, `"1-10:2,20-30"`).
    fn __reduce__<'py>(&self, py: Python<'py>) -> PyResult<(Bound<'py, PyType>, (String,))> {
        Ok((py.get_type::<Self>(), (self.inner.to_string(),)))
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.expr")]
pub(crate) struct PyRangeExprIter {
    values: Vec<i64>,
    pos: usize,
}

#[pymethods]
impl PyRangeExprIter {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(&mut self) -> Option<i64> {
        if self.pos < self.values.len() {
            let v = self.values[self.pos];
            self.pos += 1;
            Some(v)
        } else {
            None
        }
    }
}
