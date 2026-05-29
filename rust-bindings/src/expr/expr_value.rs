// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use pyo3::prelude::*;
use pyo3::types::{PyBool, PyFloat, PyInt, PyList, PyString};
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_expr::path_mapping::PathFormat;
use openjd_expr::types::ExprType;
use openjd_expr::value::ExprValue;

use crate::expr::errors::{PyExpressionError, PyExpressionTypeError};
use crate::expr::expr_type::{extract_expr_type, PyExprType};
use crate::expr::path_format::PyPathFormat;
use crate::expr::range_expr::PyRangeExpr;

/// Return the path format associated with a `Path` or `ListPath` value,
/// or `None` for any other variant. Mirrors the upstream `find_path_format`.
fn find_path_format(v: &ExprValue) -> Option<PathFormat> {
    match v {
        ExprValue::Path { format, .. } => Some(*format),
        v if v.is_list() => v
            .list_elements()
            .and_then(|elems| elems.iter().find_map(find_path_format)),
        _ => None,
    }
}

/// Wrap an `ExprValue::make_list` error in a `TypeError`, rewriting
/// the upstream "make_list expected X element, got Y" message into
/// the reference's "List contains incompatible types: X, Y" form.
/// Errors mentioning unresolved elements rewrite to the reference's
/// "Cannot construct a list containing unresolved values" message.
fn make_list_err_to_py(e: openjd_expr::error::ExpressionError) -> PyErr {
    let msg = e.to_string();
    // Strip the caret/source-line decoration upstream may attach;
    // we only care about the headline.
    let headline = msg.split('\n').next().unwrap_or(&msg);
    let rewritten = if let Some(rest) = headline.strip_prefix("make_list expected ") {
        // "X element, got Y" — extract X and Y.
        if let Some((expected, got_part)) = rest.split_once(" element, got ") {
            if got_part == "unresolved" {
                "Cannot construct a list containing unresolved values. \
                Use ExprValue.unresolved() to create unresolved list types \
                for type checking."
                    .to_string()
            } else {
                format!(
                    "List contains incompatible types: {}, {}",
                    expected, got_part
                )
            }
        } else {
            headline.to_string()
        }
    } else {
        headline.to_string()
    };
    pyo3::exceptions::PyTypeError::new_err(rewritten)
}

pub(crate) fn py_to_expr_value(obj: &Bound<'_, pyo3::PyAny>) -> PyResult<ExprValue> {
    if obj.is_none() {
        return Ok(ExprValue::Null);
    }
    if let Ok(b) = obj.cast::<PyBool>() {
        return Ok(ExprValue::Bool(b.is_true()));
    }
    if let Ok(i) = obj.cast::<PyInt>() {
        // Map PyO3's `OverflowError` for out-of-range integers to
        // `ExpressionError` so error class identity matches the
        // pure-Python reference (which raises `ExpressionError` for
        // integers outside the i64 range). Use the reference's
        // canonical message verbatim — the underlying PyO3
        // `OverflowError` text leaks an implementation detail
        // ("Python int too large to convert to C long") that's not
        // useful to callers.
        return i.extract::<i64>().map(ExprValue::Int).map_err(|err| {
            let py = i.py();
            if err.is_instance_of::<pyo3::exceptions::PyOverflowError>(py) {
                PyExpressionError::new_err(
                    "Integer overflow: result is outside the 64-bit signed range",
                )
            } else {
                err
            }
        });
    }
    if let Ok(f) = obj.cast::<PyFloat>() {
        // `Float64::new` already produces canonical "Float operation
        // produced NaN" / "Float operation produced infinity"
        // messages — surface them through `ExpressionError` so the
        // exception class matches the pure-Python reference's
        // `ExprValue._create`.
        let float = openjd_expr::value::Float64::new(f.extract::<f64>()?)
            .map_err(|e| PyExpressionError::new_err(e.to_string()))?;
        return Ok(ExprValue::Float(float));
    }
    if let Ok(s) = obj.cast::<PyString>() {
        return Ok(ExprValue::String(s.to_cow()?.to_string()));
    }
    // Handle `decimal.Decimal` via a real `isinstance` check so that
    // user-defined `Decimal` subclasses are accepted and unrelated
    // classes that happen to be named `"Decimal"` are not.
    let py = obj.py();
    let decimal_cls = py.import("decimal")?.getattr("Decimal")?;
    if obj.is_instance(&decimal_cls)? {
        let f: f64 = obj.call_method0("__float__")?.extract()?;
        let s: String = obj.call_method0("__str__")?.extract()?;
        // Same treatment as the `PyFloat` arm above: NaN / infinity
        // on a `Decimal` should surface as `ExpressionError` to
        // match the pure-Python reference.
        let float = openjd_expr::value::Float64::with_str(f, s)
            .map_err(|e| PyExpressionError::new_err(e.to_string()))?;
        return Ok(ExprValue::Float(float));
    }
    if let Ok(ev) = obj.extract::<PyExprValue>() {
        return Ok(ev.inner);
    }
    if let Ok(r) = obj.extract::<PyRangeExpr>() {
        return Ok(ExprValue::RangeExpr(r.inner));
    }
    if let Ok(t) = obj.extract::<PyExprType>() {
        return Ok(ExprValue::Unresolved(t.inner));
    }
    if let Ok(list) = obj.cast::<PyList>() {
        let elements: PyResult<Vec<ExprValue>> =
            list.iter().map(|item| py_to_expr_value(&item)).collect();
        let elements = elements?;
        let hint = elements
            .first()
            .map(|e| e.expr_type())
            .unwrap_or(ExprType::NULLTYPE);
        // `make_list` rejects element-type mismatches and unresolved
        // elements; both are type errors per the reference contract,
        // so map to `TypeError` (not `ValueError`).
        return ExprValue::make_list(elements, hint).map_err(make_list_err_to_py);
    }
    Err(pyo3::exceptions::PyTypeError::new_err(format!(
        "Cannot convert {} to ExprValue",
        obj.get_type().name()?
    )))
}

/// Convert an `ExprValue` to a native Python object. Raises
/// `ExpressionTypeError` if the value is unresolved — there is no
/// meaningful Python value to extract from a placeholder. Recursive
/// list construction propagates the same contract; an unresolved
/// element inside a list also raises (in practice, list-construction
/// already rejects unresolved elements upstream).
pub(crate) fn expr_value_to_py(py: Python<'_>, val: &ExprValue) -> PyResult<Py<pyo3::PyAny>> {
    use pyo3::IntoPyObjectExt;
    match val {
        ExprValue::Null => Ok(py.None()),
        ExprValue::Bool(b) => Ok(b.into_py_any(py)?),
        ExprValue::Int(i) => Ok(i.into_py_any(py)?),
        ExprValue::Float(f) => Ok(f.value().into_py_any(py)?),
        ExprValue::String(s) => Ok(s.into_py_any(py)?),
        ExprValue::Path { value, .. } => Ok(value.into_py_any(py)?),
        ExprValue::RangeExpr(r) => Ok(PyRangeExpr { inner: r.clone() }.into_py_any(py)?),
        ExprValue::Unresolved(t) => Err(PyExpressionTypeError::new_err(format!(
            "Cannot extract value from unresolved[{}]: value is not known",
            t
        ))),
        val if val.is_list() => {
            let elements = val.list_elements().unwrap_or_default();
            let items: Vec<Py<pyo3::PyAny>> = elements
                .iter()
                .map(|e| expr_value_to_py(py, e))
                .collect::<PyResult<_>>()?;
            Ok(PyList::new(py, items)?.into_any().unbind())
        }
        // `ExprValue` is `#[non_exhaustive]`; if a new variant is added
        // crate-side it MUST be mirrored above. Surfacing a panic at
        // the binding boundary is preferable to silently converting
        // future variants to Python `None` (the previous fallback),
        // which would corrupt round-trips and mask the missing handler.
        v => unreachable!(
            "openjd-expr added a new ExprValue variant ({v:?}) but the Python binding has no mapping; \
             add a match arm in `rust-bindings/src/expr/expr_value.rs::expr_value_to_py`"
        ),
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.expr", name = "ExprValue", from_py_object)]
#[derive(Clone)]
pub(crate) struct PyExprValue {
    pub(crate) inner: ExprValue,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyExprValue {
    #[new]
    #[pyo3(signature = (value, r#type=None, path_format=None))]
    fn new(
        value: &Bound<'_, pyo3::PyAny>,
        r#type: Option<&Bound<'_, pyo3::PyAny>>,
        path_format: Option<PyPathFormat>,
    ) -> PyResult<Self> {
        let target = match r#type {
            Some(type_obj) => Some(extract_expr_type(type_obj)?),
            None => None,
        };
        let pf = path_format
            .map(PathFormat::from)
            .unwrap_or_else(PathFormat::host);

        // Build the inner value, using target type as hint for list construction
        let inner = if let Ok(list) = value.cast::<PyList>() {
            let elements: PyResult<Vec<ExprValue>> =
                list.iter().map(|item| py_to_expr_value(&item)).collect();
            let elements = elements?;
            let hint = if let Some(ref t) = target {
                t.params().first().cloned().unwrap_or(ExprType::STRING)
            } else {
                elements
                    .first()
                    .map(|e| e.expr_type())
                    .unwrap_or(ExprType::NULLTYPE)
            };
            ExprValue::make_list(elements, hint).map_err(make_list_err_to_py)?
        } else {
            py_to_expr_value(value)?
        };

        match target {
            None => Ok(PyExprValue { inner }),
            Some(target) => {
                let coerced = match &inner {
                    ExprValue::String(s) => ExprValue::from_str_coerce(s, &target, pf),
                    _ => inner.coerce(&target, pf),
                };
                coerced
                    .map(|v| PyExprValue { inner: v })
                    .map_err(pyo3::exceptions::PyValueError::new_err)
            }
        }
    }

    #[staticmethod]
    fn unresolved(ty: &Bound<'_, pyo3::PyAny>) -> PyResult<Self> {
        let expr_type = extract_expr_type(ty)?;
        Ok(PyExprValue {
            inner: ExprValue::Unresolved(expr_type),
        })
    }

    /// Construct a Float-typed ``ExprValue`` from a numeric value.
    ///
    /// ``value`` accepts ``int``, ``float``, or ``decimal.Decimal``.
    /// When the input is a ``Decimal`` and ``original_str`` is not
    /// supplied, the ``Decimal``'s string form is captured
    /// automatically — so ``ExprValue.from_float(Decimal("1.00"))``
    /// preserves the trailing zeros in ``str()`` just like the
    /// equivalent ``ExprValue(Decimal("1.00"))`` call does. This
    /// keeps the two constructor entry points consistent.
    ///
    /// The optional ``original_str`` argument carries the
    /// user-supplied source string for diagnostics — when present,
    /// it's surfaced verbatim in error messages and ``__str__``,
    /// preserving information that would otherwise be lost in the
    /// f64 round-trip (e.g. trailing zeros: ``"3.140"`` vs
    /// ``3.14``). When omitted (or ``None``) for a non-``Decimal``
    /// input, the canonical Rust ``f64`` ``Display`` form is used.
    ///
    /// Mirrors the pure-Python reference:
    /// ``ExprValue.from_float(value, original_str=None)``.
    #[staticmethod]
    #[pyo3(signature = (value, original_str=None))]
    fn from_float(value: &Bound<'_, pyo3::PyAny>, original_str: Option<String>) -> PyResult<Self> {
        // If the caller passed a ``Decimal`` and didn't override
        // ``original_str``, capture the Decimal's lexical form
        // automatically. This mirrors the main ``ExprValue(...)``
        // constructor's Decimal handling so that the two
        // constructor surfaces produce the same ``str()`` form for
        // a given Decimal input.
        let py = value.py();
        let resolved_original_str: Option<String> = match original_str {
            Some(s) => Some(s),
            None => {
                let decimal_cls = py.import("decimal")?.getattr("Decimal")?;
                if value.is_instance(&decimal_cls)? {
                    Some(value.call_method0("__str__")?.extract()?)
                } else {
                    None
                }
            }
        };
        // Coerce to ``f64`` via the standard PyO3 path. This works
        // for ``int``, ``float``, and ``Decimal`` (the latter via
        // ``Decimal.__float__()``).
        let f: f64 = value.extract()?;
        let float = match resolved_original_str {
            Some(s) => openjd_expr::value::Float64::with_str(f, s),
            None => openjd_expr::value::Float64::new(f),
        }
        .map_err(|e| PyExpressionError::new_err(e.to_string()))?;
        Ok(PyExprValue {
            inner: ExprValue::Float(float),
        })
    }

    #[getter]
    fn r#type(&self) -> PyExprType {
        PyExprType {
            inner: self.inner.expr_type(),
        }
    }

    #[getter]
    fn is_null(&self) -> bool {
        matches!(self.inner, ExprValue::Null)
    }

    /// Memory footprint of this value in bytes, including the inline
    /// struct and heap-allocated payload. Mirrors
    /// ``ExprValue::memory_size`` in the underlying Rust crate; values
    /// are sized in Rust terms, not Python ones, and are intended for
    /// memory-limit-aware code (the same accounting that
    /// ``DEFAULT_MEMORY_LIMIT`` enforces during evaluation).
    fn memory_size(&self) -> usize {
        self.inner.memory_size()
    }

    fn item(&self, py: Python<'_>) -> PyResult<Py<pyo3::PyAny>> {
        expr_value_to_py(py, &self.inner)
    }

    fn __len__(&self) -> PyResult<usize> {
        match &self.inner {
            ExprValue::RangeExpr(r) => Ok(r.len()),
            _ => self.inner.list_len().ok_or_else(|| {
                pyo3::exceptions::PyTypeError::new_err("ExprValue is not a list or range_expr")
            }),
        }
    }

    fn __getitem__(&self, index: isize) -> PyResult<PyExprValue> {
        let len = self.__len__()?;
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
        match &self.inner {
            ExprValue::RangeExpr(r) => r
                .get(idx as i64)
                .map(|i| PyExprValue {
                    inner: ExprValue::Int(i),
                })
                .ok_or_else(|| pyo3::exceptions::PyIndexError::new_err("index out of range")),
            _ => self
                .inner
                .list_elements()
                .and_then(|v| v.into_iter().nth(idx as usize))
                .map(|e| PyExprValue { inner: e })
                .ok_or_else(|| pyo3::exceptions::PyIndexError::new_err("index out of range")),
        }
    }

    fn __iter__(slf: Py<Self>, py: Python<'_>) -> PyResult<Py<PyExprValueIter>> {
        let inner = &slf.borrow(py).inner;
        let elements: Vec<PyExprValue> = match inner {
            ExprValue::RangeExpr(r) => r
                .iter()
                .map(|i| PyExprValue {
                    inner: ExprValue::Int(i),
                })
                .collect(),
            _ => inner
                .list_elements()
                .ok_or_else(|| {
                    pyo3::exceptions::PyTypeError::new_err("ExprValue is not a list or range_expr")
                })?
                .into_iter()
                .map(|e| PyExprValue { inner: e })
                .collect(),
        };
        Py::new(py, PyExprValueIter { elements, pos: 0 })
    }

    fn __str__(&self) -> PyResult<String> {
        if let ExprValue::Unresolved(t) = &self.inner {
            return Err(PyExpressionTypeError::new_err(format!(
                "Cannot convert unresolved[{}] to string: value is not known",
                t
            )));
        }
        Ok(self.inner.to_display_string())
    }

    fn __repr__(&self) -> String {
        self.inner.repr_python()
    }

    fn __bool__(&self) -> bool {
        match &self.inner {
            ExprValue::Null => false,
            ExprValue::Bool(b) => *b,
            ExprValue::Int(i) => *i != 0,
            ExprValue::Float(f) => f.value() != 0.0,
            ExprValue::String(s) => !s.is_empty(),
            ExprValue::Path { value, .. } => !value.is_empty(),
            ExprValue::RangeExpr(r) => !r.is_empty(),
            _ if self.inner.is_list() => self.inner.list_len().unwrap_or(0) > 0,
            _ => false,
        }
    }

    fn __eq__(&self, other: &PyExprValue) -> bool {
        self.inner.equals(&other.inner)
    }

    /// Pickle support — round-trips through `__init__` (or
    /// `unresolved` for `Unresolved` values).
    ///
    /// The reducer encodes:
    /// - the native Python value (`item()`)
    /// - the type name (e.g. `"int"`, `"list[path]"`)
    /// - for path / list-of-path values, the path format
    ///
    /// For `Unresolved(t)` values we use `ExprValue.unresolved(t)` instead.
    fn __reduce__<'py>(
        &self,
        py: Python<'py>,
    ) -> PyResult<(Bound<'py, PyAny>, Py<pyo3::types::PyTuple>)> {
        use pyo3::types::{PyTuple, PyType};
        use pyo3::IntoPyObjectExt;
        let cls: Bound<'py, PyType> = py.get_type::<Self>();
        // Unresolved values have no payload — only a type. Reconstruct
        // via `ExprValue.unresolved(type_str)`.
        if let ExprValue::Unresolved(t) = &self.inner {
            let unresolved = cls.getattr("unresolved")?;
            let args = PyTuple::new(py, [t.to_string().into_py_any(py)?])?;
            return Ok((unresolved, args.into()));
        }
        // Use a private module-level helper so older pickles can still load.
        let helper = py
            .import("openjd._openjd_rs")?
            .getattr("_reconstruct_expr_value")?;
        let item = expr_value_to_py(py, &self.inner)?;
        let type_str = self.inner.expr_type().to_string();
        let path_format: Option<&str> = find_path_format(&self.inner).map(|f| match f {
            PathFormat::Posix => "POSIX",
            PathFormat::Windows => "WINDOWS",
            PathFormat::Uri => "URI",
        });
        let args = PyTuple::new(
            py,
            [
                item,
                type_str.into_py_any(py)?,
                match path_format {
                    Some(s) => s.into_py_any(py)?,
                    None => py.None(),
                },
            ],
        )?;
        Ok((helper, args.into()))
    }
}

/// Pickle helper: reconstruct an `ExprValue` from `(item, type_str,
/// path_format_name)`. Module-level so it has a stable import path
/// for pickled bytes from older interpreter sessions.
#[pyfunction]
pub(crate) fn _reconstruct_expr_value<'py>(
    py: Python<'py>,
    item: &Bound<'py, PyAny>,
    type_str: Option<&str>,
    path_format: Option<&str>,
) -> PyResult<PyExprValue> {
    use pyo3::types::{PyDict, PyTuple};
    let cls = py.get_type::<PyExprValue>();
    let kwargs = PyDict::new(py);
    if let Some(t) = type_str {
        kwargs.set_item("type", t)?;
    }
    if let Some(pf) = path_format {
        let pf_enum = py
            .import("openjd.expr")?
            .getattr("PathFormat")?
            .getattr(pf)?;
        kwargs.set_item("path_format", pf_enum)?;
    }
    let args = PyTuple::new(py, [item.clone()])?;
    let result = cls.call(args, Some(&kwargs))?;
    let value = result.extract::<PyExprValue>()?;
    Ok(value)
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.expr")]
struct PyExprValueIter {
    elements: Vec<PyExprValue>,
    pos: usize,
}

#[pymethods]
impl PyExprValueIter {
    fn __iter__(slf: Py<Self>) -> Py<Self> {
        slf
    }

    fn __next__(&mut self) -> Option<PyExprValue> {
        if self.pos < self.elements.len() {
            let val = self.elements[self.pos].clone();
            self.pos += 1;
            Some(val)
        } else {
            None
        }
    }
}
