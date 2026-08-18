// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyString};
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_expr::path_mapping::PathFormat;
use openjd_expr::symbol_table::SymbolTable;
use openjd_expr::types::ExprType;
use openjd_expr::value::ExprValue;

use crate::expr::expr_value::{py_to_expr_value, PyExprValue};
use crate::expr::path_format::PyPathFormat;

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.expr", name = "SymbolTable", from_py_object)]
#[derive(Clone)]
pub(crate) struct PySymbolTable {
    pub(crate) inner: SymbolTable,
}

pub(crate) fn dict_to_symtab(dict: &Bound<'_, PyDict>) -> PyResult<SymbolTable> {
    let mut st = SymbolTable::new();
    for (key, value) in dict.iter() {
        let k: String = key.extract()?;
        if let Ok(sub_dict) = value.cast::<PyDict>() {
            let sub = dict_to_symtab(sub_dict)?;
            st.set_table(&k, sub);
        } else if let Ok(sub_st) = value.extract::<PySymbolTable>() {
            st.set_table(&k, sub_st.inner);
        } else {
            let v = py_to_expr_value(&value)?;
            st.set(&k, v)
                .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        }
    }
    Ok(st)
}

pub(crate) fn extract_symtab(obj: &Bound<'_, pyo3::PyAny>) -> PyResult<SymbolTable> {
    if let Ok(pst) = obj.extract::<PySymbolTable>() {
        return Ok(pst.inner);
    }
    if let Ok(dict) = obj.cast::<PyDict>() {
        return dict_to_symtab(dict);
    }
    Err(pyo3::exceptions::PyTypeError::new_err(
        "Expected SymbolTable or dict",
    ))
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PySymbolTable {
    #[new]
    #[pyo3(signature = (init=None, *, source=None))]
    fn new(
        init: Option<&Bound<'_, pyo3::PyAny>>,
        source: Option<&Bound<'_, pyo3::PyAny>>,
    ) -> PyResult<Self> {
        let arg = source.or(init);
        match arg {
            None => Ok(PySymbolTable {
                inner: SymbolTable::new(),
            }),
            Some(obj) => extract_symtab(obj).map(|inner| PySymbolTable { inner }),
        }
    }

    fn __contains__(&self, key: &str) -> bool {
        self.inner.contains(key)
    }

    fn __getitem__(&self, py: Python<'_>, key: &str) -> PyResult<Py<pyo3::PyAny>> {
        use pyo3::IntoPyObjectExt;
        match self.inner.get(key) {
            Some(openjd_expr::symbol_table::SymbolTableEntry::Value(v)) => {
                PyExprValue { inner: v.clone() }.into_py_any(py)
            }
            Some(openjd_expr::symbol_table::SymbolTableEntry::Table(t)) => {
                PySymbolTable { inner: t.clone() }.into_py_any(py)
            }
            None => Err(pyo3::exceptions::PyKeyError::new_err(key.to_string())),
        }
    }

    fn get(&self, py: Python<'_>, name: &str) -> PyResult<Option<Py<pyo3::PyAny>>> {
        use pyo3::IntoPyObjectExt;
        match self.inner.get(name) {
            Some(openjd_expr::symbol_table::SymbolTableEntry::Value(v)) => {
                Ok(Some(PyExprValue { inner: v.clone() }.into_py_any(py)?))
            }
            Some(openjd_expr::symbol_table::SymbolTableEntry::Table(t)) => {
                Ok(Some(PySymbolTable { inner: t.clone() }.into_py_any(py)?))
            }
            None => Ok(None),
        }
    }

    fn __setitem__(&mut self, key: &str, value: &Bound<'_, pyo3::PyAny>) -> PyResult<()> {
        let v = if let Ok(ev) = value.extract::<PyExprValue>() {
            ev.inner
        } else {
            py_to_expr_value(value)?
        };
        self.inner
            .set(key, v)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }

    #[getter]
    fn keys(&self) -> std::collections::HashSet<String> {
        self.inner.keys().map(|s| s.to_string()).collect()
    }

    #[getter]
    fn symbols(&self) -> std::collections::HashSet<String> {
        self.inner.all_paths("").into_iter().collect()
    }

    #[pyo3(signature = (*others))]
    fn union(&self, others: &Bound<'_, pyo3::types::PyTuple>) -> PyResult<Self> {
        let mut result = self.inner.clone();
        for item in others.iter() {
            let other = if let Ok(st) = item.extract::<PySymbolTable>() {
                st.inner
            } else if let Ok(dict) = item.cast::<PyDict>() {
                dict_to_symtab(dict)?
            } else {
                return Err(pyo3::exceptions::PyTypeError::new_err(
                    "union() arguments must be SymbolTable or dict",
                ));
            };
            result.merge_from(&other);
        }
        Ok(PySymbolTable { inner: result })
    }

    /// Pickle support — round-trips through a flat
    /// `dict[str, ExprValue]` of all dotted leaf paths.
    fn __reduce__<'py>(
        &self,
        py: Python<'py>,
    ) -> PyResult<(Bound<'py, pyo3::types::PyType>, (Bound<'py, PyDict>,))> {
        use pyo3::IntoPyObjectExt;
        let dict = PyDict::new(py);
        for path in self.inner.all_paths("") {
            if let Some(openjd_expr::symbol_table::SymbolTableEntry::Value(v)) =
                self.inner.get(&path)
            {
                dict.set_item(path, PyExprValue { inner: v.clone() }.into_py_any(py)?)?;
            }
        }
        Ok((py.get_type::<Self>(), (dict,)))
    }

    /// Mirror the pure-Python reference's ``SymbolTable({...})`` repr.
    /// The dict shows each top-level key mapped to either an
    /// ``ExprValue`` (leaf) or a nested ``SymbolTable`` (subtable),
    /// recursing through nested subtables for free via Python's repr.
    fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        use pyo3::IntoPyObjectExt;
        let dict = PyDict::new(py);
        // Walk top-level keys in sorted order so the repr is
        // deterministic (`HashMap` iteration order is otherwise random).
        let mut keys: Vec<&str> = self.inner.keys().collect();
        keys.sort_unstable();
        for key in keys {
            match self.inner.get(key) {
                Some(openjd_expr::symbol_table::SymbolTableEntry::Value(v)) => {
                    dict.set_item(key, PyExprValue { inner: v.clone() }.into_py_any(py)?)?;
                }
                Some(openjd_expr::symbol_table::SymbolTableEntry::Table(t)) => {
                    dict.set_item(key, PySymbolTable { inner: t.clone() }.into_py_any(py)?)?;
                }
                None => {}
            }
        }
        Ok(format!("SymbolTable({})", dict.repr()?))
    }

    /// Two `SymbolTable`s compare equal when they contain the
    /// same set of dotted-path → value mappings. Insertion order
    /// in the underlying `HashMap` does not affect equality, and
    /// equality is recursive through nested subtables. Returns
    /// `False` for non-`SymbolTable` arguments — `dict` is **not**
    /// auto-coerced (use the `SymbolTable(dict)` constructor for
    /// that, then compare).
    ///
    /// `SymbolTable` is intentionally **not** hashable
    /// (`__setitem__` is supported, so the contents can change
    /// after construction — Python's hash/eq contract requires
    /// hashable types to be effectively immutable).
    fn __eq__(&self, other: &Bound<'_, pyo3::PyAny>) -> PyResult<bool> {
        let Ok(rhs) = other.extract::<PyRef<'_, PySymbolTable>>() else {
            return Ok(false);
        };
        Ok(symbol_table_eq(&self.inner, &rhs.inner))
    }
}

/// Recursive value-equality on `openjd_expr::SymbolTable`. Two
/// tables are equal iff they have the same keys at every level
/// and equal leaf `ExprValue`s. The underlying crate does not
/// derive `PartialEq` on `SymbolTable`, so we walk the tree.
fn symbol_table_eq(a: &SymbolTable, b: &SymbolTable) -> bool {
    use openjd_expr::symbol_table::SymbolTableEntry;
    let a_keys: std::collections::HashSet<&str> = a.keys().collect();
    let b_keys: std::collections::HashSet<&str> = b.keys().collect();
    if a_keys != b_keys {
        return false;
    }
    for key in a_keys {
        match (a.get(key), b.get(key)) {
            (Some(SymbolTableEntry::Value(va)), Some(SymbolTableEntry::Value(vb))) => {
                if va != vb {
                    return false;
                }
            }
            (Some(SymbolTableEntry::Table(ta)), Some(SymbolTableEntry::Table(tb))) => {
                if !symbol_table_eq(ta, tb) {
                    return false;
                }
            }
            // Type mismatch (Value vs Table) at the same key.
            _ => return false,
        }
    }
    true
}

// ── SerializedSymbolTable ──────────────────────────────────────────
//
// Opaque box around the Rust-side serialized form. The intended
// transport path is ``Step.resolved_symtab → Session.run_task``,
// which never inspects the contents — keeping the value serialized
// avoids two unnecessary conversions (``to_symtab`` on the getter,
// ``from_symtab`` on the setter). Callers that *do* want to peek at
// or modify the symbol table go through ``.to_symtab()`` / a fresh
// ``SerializedSymbolTable.from_symtab(...)``.

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.expr",
    name = "SerializedSymbolTable",
    frozen,
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PySerializedSymbolTable {
    pub(crate) inner: openjd_expr::SerializedSymbolTable,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PySerializedSymbolTable {
    /// Build a ``SerializedSymbolTable`` from an in-memory
    /// ``SymbolTable``. The serialized form is the canonical
    /// transport between ``create_job`` (which produces it as
    /// ``Step.resolved_symtab``) and ``Session.run_task`` (which
    /// consumes it). Callers that build their own symbol tables can
    /// use this classmethod to convert.
    #[classmethod]
    fn from_symtab(_cls: &Bound<'_, pyo3::types::PyType>, symtab: &PySymbolTable) -> Self {
        Self {
            inner: openjd_expr::SerializedSymbolTable::from_symtab(&symtab.inner),
        }
    }

    /// Build a ``SerializedSymbolTable`` from its JSON transport
    /// text, as produced by ``to_json_str``.
    ///
    /// This is the inverse of ``to_json_str`` and exists for callers
    /// that carry the transport form across a process or service
    /// boundary — a scheduler persisting the table produced by
    /// ``create_job`` and later handing it to a worker, for instance.
    /// Prefer ``from_symtab`` when the source is an in-memory
    /// ``SymbolTable``.
    ///
    /// Raises ``ValueError`` if the text is not valid JSON. Note that
    /// the *contents* are validated lazily: a well-formed JSON
    /// document whose entries are not valid symbol table entries is
    /// accepted here and rejected by ``to_symtab``.
    #[classmethod]
    fn from_json_str(_cls: &Bound<'_, pyo3::types::PyType>, json: &str) -> PyResult<Self> {
        let inner = openjd_expr::SerializedSymbolTable::from_json_str(json).map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!(
                "Failed to parse SerializedSymbolTable JSON: {e}"
            ))
        })?;
        Ok(Self { inner })
    }

    /// Serialize to the JSON transport text: an array of
    /// ``{"name", "type", "value"}`` objects in canonical
    /// (lexicographic) path order.
    ///
    /// Use this to move a table across a process or service boundary;
    /// pair it with ``from_json_str`` to reconstruct. The result is
    /// stable for a given table, so it is safe to store or compare.
    fn to_json_str(&self) -> PyResult<String> {
        serde_json::to_string(&self.inner).map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!(
                "Failed to serialize SerializedSymbolTable: {e}"
            ))
        })
    }

    /// Deserialize this serialized symbol table into a full
    /// ``SymbolTable`` suitable for inspection or modification.
    /// ``path_format`` controls how PATH-typed values are
    /// reconstructed: ``PathFormat.POSIX`` (the default) uses
    /// forward slashes, ``PathFormat.WINDOWS`` uses backslashes.
    /// Most callers should pass the ``PathFormat`` matching the
    /// session's host OS.
    #[pyo3(signature = (*, path_format=None))]
    fn to_symtab(
        &self,
        path_format: Option<crate::expr::path_format::PyPathFormat>,
    ) -> PyResult<PySymbolTable> {
        let pf = path_format
            .map(Into::into)
            .unwrap_or_else(openjd_expr::path_mapping::PathFormat::host);
        let inner = self.inner.to_symtab(pf).map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!(
                "Failed to deserialize SerializedSymbolTable: {e}"
            ))
        })?;
        Ok(PySymbolTable { inner })
    }

    fn __repr__(&self) -> String {
        // Don't try to render the contents — the value is opaque
        // transport. Emit just the type name.
        "SerializedSymbolTable(...)".to_string()
    }

    /// Pickle support — round-trips through the JSON string form.
    #[allow(clippy::type_complexity)] // pickle reducer tuple shape is by design
    fn __reduce__<'py>(&self, py: Python<'py>) -> PyResult<(Bound<'py, pyo3::PyAny>, (String,))> {
        let helper = py
            .import("openjd._openjd_rs")?
            .getattr("_reconstruct_serialized_symtab")?;
        let json = serde_json::to_string(&self.inner).map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!(
                "Failed to pickle SerializedSymbolTable: {e}"
            ))
        })?;
        Ok((helper, (json,)))
    }
}

/// Pickle helper — module-level free function so pickled bytes
/// can be reconstructed across interpreter sessions.
#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyfunction(module = "openjd._openjd_rs")
)]
#[pyfunction]
pub(crate) fn _reconstruct_serialized_symtab(json: &str) -> PyResult<PySerializedSymbolTable> {
    let inner = openjd_expr::SerializedSymbolTable::from_json_str(json).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!(
            "Failed to unpickle SerializedSymbolTable: {e}"
        ))
    })?;
    Ok(PySerializedSymbolTable { inner })
}

// ── Typed symbol-table builder ─────────────────────────────────────
//
// Bridges the pure-Python (v0) model's flat dotted-key symbol table into
// a typed `SymbolTable` the engine can evaluate against. This replaces the
// former Python `symtab_to_expr_values`/`_to_expr_value` coercion so the
// string→typed-value coercion lives next to the engine (PR #285 review,
// C3/C5). The OpenJD-type → EXPR-type-spec mapping stays in Python; this
// function takes the resolved EXPR type spec strings (e.g. "int",
// "list[int]", "path") so the engine owns only the coercion + nesting.

/// Coerce a single Python value to an `ExprValue`, optionally toward a known
/// target `ExprType`. String values are coerced via `from_str_coerce` (so a
/// stored ``"10"`` of type INT becomes a real integer); other native values
/// are built then coerced. With no target the value's native type is
/// inferred. Mirrors the former Python ``_expr_support._to_expr_value``.
fn coerce_symbol_value(
    value: &Bound<'_, pyo3::PyAny>,
    target: Option<&ExprType>,
    pf: PathFormat,
) -> PyResult<ExprValue> {
    let Some(target) = target else {
        // No confident type — let the engine infer from the native value.
        return py_to_expr_value(value);
    };
    if let Ok(s) = value.cast::<PyString>() {
        return ExprValue::from_str_coerce(&s.to_cow()?, target, pf)
            .map_err(pyo3::exceptions::PyValueError::new_err);
    }
    py_to_expr_value(value)?
        .coerce(target, pf)
        .map_err(pyo3::exceptions::PyValueError::new_err)
}

/// Build a typed :class:`SymbolTable` from a flat dotted-key value map and an
/// optional per-key EXPR type-spec map, coercing string values to their
/// declared type and nesting dotted keys (``"Param.Frame"``) into subtables.
///
/// ``values`` maps dotted symbol names to their (typically string) values, as
/// the v0 model stores them. ``types`` maps the same dotted names to EXPR
/// type spec strings (``"int"``, ``"list[int]"``, ``"path"``, …); names absent
/// from ``types`` are inferred from the value. ``path_format`` controls how
/// PATH-typed values are interpreted (defaults to the host OS).
#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyfunction(module = "openjd._openjd_rs")
)]
#[pyfunction]
#[pyo3(signature = (values, types=None, *, path_format=None))]
pub(crate) fn build_symbol_table(
    values: &Bound<'_, PyDict>,
    types: Option<&Bound<'_, PyDict>>,
    path_format: Option<PyPathFormat>,
) -> PyResult<PySymbolTable> {
    let pf = path_format
        .map(PathFormat::from)
        .unwrap_or_else(PathFormat::host);
    let mut st = SymbolTable::new();
    for (key, value) in values.iter() {
        let dotted: String = key.extract()?;
        let target: Option<ExprType> = match types {
            Some(t) => match t.get_item(dotted.as_str())? {
                Some(spec_obj) => {
                    let spec: String = spec_obj.extract()?;
                    Some(ExprType::parse(&spec).map_err(pyo3::exceptions::PyValueError::new_err)?)
                }
                None => None,
            },
            None => None,
        };
        let ev = coerce_symbol_value(&value, target.as_ref(), pf)?;
        st.set(&dotted, ev)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    }
    Ok(PySymbolTable { inner: st })
}
