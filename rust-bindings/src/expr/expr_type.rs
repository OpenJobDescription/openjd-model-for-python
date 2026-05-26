// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use pyo3::prelude::*;
use pyo3::types::PyType;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;
use std::collections::HashMap;

use openjd_expr::types::{ExprType, TypeCode};

// ── PyTypeCode enum ──

#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyclass_enum(module = "openjd._openjd_rs")
)]
#[pyclass(
    module = "openjd.expr",
    name = "TypeCode",
    eq,
    eq_int,
    frozen,
    hash,
    from_py_object
)]
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
// Variant names are the user-facing Python enum identifiers and follow
// Python's UPPER_SNAKE_CASE convention rather than Rust's UpperCamelCase.
#[allow(non_camel_case_types, clippy::upper_case_acronyms)]
pub(crate) enum PyTypeCode {
    NULLTYPE,
    BOOL,
    INT,
    FLOAT,
    STRING,
    PATH,
    LIST,
    RANGE_EXPR,
    ANY,
    UNION,
    NORETURN,
    UNRESOLVED,
    TYPEVAR_T,
    TYPEVAR_T1,
    TYPEVAR_T2,
    TYPEVAR_T3,
}

impl From<TypeCode> for PyTypeCode {
    fn from(tc: TypeCode) -> Self {
        match tc {
            TypeCode::NullType => PyTypeCode::NULLTYPE,
            TypeCode::Bool => PyTypeCode::BOOL,
            TypeCode::Int => PyTypeCode::INT,
            TypeCode::Float => PyTypeCode::FLOAT,
            TypeCode::String => PyTypeCode::STRING,
            TypeCode::Path => PyTypeCode::PATH,
            TypeCode::List => PyTypeCode::LIST,
            TypeCode::RangeExpr => PyTypeCode::RANGE_EXPR,
            TypeCode::Any => PyTypeCode::ANY,
            TypeCode::Union => PyTypeCode::UNION,
            TypeCode::NoReturn => PyTypeCode::NORETURN,
            TypeCode::Unresolved => PyTypeCode::UNRESOLVED,
            TypeCode::TypeVarT => PyTypeCode::TYPEVAR_T,
            TypeCode::TypeVarT1 => PyTypeCode::TYPEVAR_T1,
            TypeCode::TypeVarT2 => PyTypeCode::TYPEVAR_T2,
            TypeCode::TypeVarT3 => PyTypeCode::TYPEVAR_T3,
            TypeCode::Signature => PyTypeCode::NORETURN, // no Python equivalent
            // `TypeCode` is `#[non_exhaustive]`; if a new variant is
            // added crate-side it MUST be mirrored here. Surfacing a
            // panic at the binding boundary is preferable to silently
            // collapsing future variants into `ANY` (the previous
            // fallback), which would corrupt round-trips and mask the
            // missing handler.
            tc => unreachable!(
                "openjd-expr added a new TypeCode variant ({tc:?}) but the Python binding has no mapping; \
                 add a match arm in `rust-bindings/src/expr/expr_type.rs` and a corresponding `PyTypeCode` variant"
            ),
        }
    }
}

impl From<PyTypeCode> for TypeCode {
    fn from(tc: PyTypeCode) -> Self {
        match tc {
            PyTypeCode::NULLTYPE => TypeCode::NullType,
            PyTypeCode::BOOL => TypeCode::Bool,
            PyTypeCode::INT => TypeCode::Int,
            PyTypeCode::FLOAT => TypeCode::Float,
            PyTypeCode::STRING => TypeCode::String,
            PyTypeCode::PATH => TypeCode::Path,
            PyTypeCode::LIST => TypeCode::List,
            PyTypeCode::RANGE_EXPR => TypeCode::RangeExpr,
            PyTypeCode::ANY => TypeCode::Any,
            PyTypeCode::UNION => TypeCode::Union,
            PyTypeCode::NORETURN => TypeCode::NoReturn,
            PyTypeCode::UNRESOLVED => TypeCode::Unresolved,
            PyTypeCode::TYPEVAR_T => TypeCode::TypeVarT,
            PyTypeCode::TYPEVAR_T1 => TypeCode::TypeVarT1,
            PyTypeCode::TYPEVAR_T2 => TypeCode::TypeVarT2,
            PyTypeCode::TYPEVAR_T3 => TypeCode::TypeVarT3,
        }
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyTypeCode {
    /// Variant name as a string (e.g. `"INT"`).
    #[getter]
    fn name(&self) -> &'static str {
        match self {
            PyTypeCode::NULLTYPE => "NULLTYPE",
            PyTypeCode::BOOL => "BOOL",
            PyTypeCode::INT => "INT",
            PyTypeCode::FLOAT => "FLOAT",
            PyTypeCode::STRING => "STRING",
            PyTypeCode::PATH => "PATH",
            PyTypeCode::LIST => "LIST",
            PyTypeCode::RANGE_EXPR => "RANGE_EXPR",
            PyTypeCode::ANY => "ANY",
            PyTypeCode::UNION => "UNION",
            PyTypeCode::NORETURN => "NORETURN",
            PyTypeCode::UNRESOLVED => "UNRESOLVED",
            PyTypeCode::TYPEVAR_T => "TYPEVAR_T",
            PyTypeCode::TYPEVAR_T1 => "TYPEVAR_T1",
            PyTypeCode::TYPEVAR_T2 => "TYPEVAR_T2",
            PyTypeCode::TYPEVAR_T3 => "TYPEVAR_T3",
        }
    }

    /// Pickle support — round-trips through the variant name.
    #[allow(clippy::type_complexity)] // pickle reducer tuple shape is by design
    fn __reduce__<'py>(
        &self,
        py: Python<'py>,
    ) -> PyResult<(Bound<'py, PyAny>, (Bound<'py, PyType>, &'static str))> {
        let helper = py
            .import("openjd._openjd_rs")?
            .getattr("_reconstruct_enum")?;
        Ok((helper, (py.get_type::<Self>(), self.name())))
    }
}

pub(crate) fn str_to_typecode(v: &str) -> PyResult<TypeCode> {
    match v {
        "nulltype" => Ok(TypeCode::NullType),
        "bool" => Ok(TypeCode::Bool),
        "int" => Ok(TypeCode::Int),
        "float" => Ok(TypeCode::Float),
        "string" => Ok(TypeCode::String),
        "path" => Ok(TypeCode::Path),
        "list" => Ok(TypeCode::List),
        "range_expr" => Ok(TypeCode::RangeExpr),
        "any" => Ok(TypeCode::Any),
        "union" => Ok(TypeCode::Union),
        "noreturn" => Ok(TypeCode::NoReturn),
        "unresolved" => Ok(TypeCode::Unresolved),
        "T" => Ok(TypeCode::TypeVarT),
        "T1" => Ok(TypeCode::TypeVarT1),
        "T2" => Ok(TypeCode::TypeVarT2),
        "T3" => Ok(TypeCode::TypeVarT3),
        "signature" => Ok(TypeCode::Signature),
        _ => Err(pyo3::exceptions::PyValueError::new_err(format!(
            "Unknown TypeCode value: {v}"
        ))),
    }
}

/// Validate that the parameter count for a `TypeCode` matches the
/// canonical arity for that variant, raising `ValueError` on mismatch.
/// The reference enforces these constraints; the upstream Rust
/// `ExprType::new` is permissive and produces non-canonical shapes
/// (e.g. `unresolved` with zero or two type params, `list` with
/// zero or many element types) that don't appear anywhere in
/// well-formed evaluation. Validating here keeps the Python surface
/// honest without requiring upstream changes.
///
/// Note: `Union` is intentionally NOT validated here — the upstream
/// `normalize_union` accepts any number of params and unwraps /
/// flattens / hoists `noreturn` and `unresolved` in well-defined
/// ways. Single-element unions unwrap to the element, zero-element
/// unions become `noreturn`. Existing tests rely on this; preserving
/// it.
fn validate_typecode_arity(code: TypeCode, params: &[ExprType]) -> PyResult<()> {
    let n = params.len();
    let err = |msg: &str| Err(pyo3::exceptions::PyValueError::new_err(msg.to_string()));
    match code {
        // Exactly one type parameter.
        TypeCode::List | TypeCode::Unresolved => {
            if n != 1 {
                return err(&format!(
                    "{:?} requires exactly one type parameter, got {}",
                    code, n
                ));
            }
        }
        // Zero parameters expected. Includes the simple primitives
        // (NullType, Bool, Int, Float, String, Path, RangeExpr) and
        // the special markers (Any, NoReturn, TypeVarT*, Signature).
        // Union is exempt from validation — see doc comment above.
        TypeCode::Union => {}
        _ => {
            if n != 0 {
                return err(&format!(
                    "{:?} does not accept type parameters, got {}",
                    code, n
                ));
            }
        }
    }
    Ok(())
}

pub(crate) fn extract_expr_type(obj: &Bound<'_, pyo3::PyAny>) -> PyResult<ExprType> {
    if let Ok(t) = obj.extract::<PyExprType>() {
        return Ok(t.inner);
    }
    if let Ok(s) = obj.extract::<String>() {
        return ExprType::parse(&s).map_err(pyo3::exceptions::PyValueError::new_err);
    }
    Err(pyo3::exceptions::PyTypeError::new_err(
        "type must be a string or ExprType",
    ))
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.expr", name = "ExprType", from_py_object)]
#[derive(Clone)]
pub(crate) struct PyExprType {
    pub(crate) inner: ExprType,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyExprType {
    #[new]
    #[pyo3(signature = (arg, params=None))]
    fn new(arg: &Bound<'_, pyo3::PyAny>, params: Option<Vec<PyExprType>>) -> PyResult<Self> {
        // Try TypeCode first (works for both single-arg and two-arg forms)
        if let Ok(tc) = arg.extract::<PyTypeCode>() {
            let code: TypeCode = tc.into();
            let rust_params: Vec<ExprType> = params
                .unwrap_or_default()
                .into_iter()
                .map(|p| p.inner)
                .collect();
            validate_typecode_arity(code, &rust_params)?;
            return Ok(PyExprType {
                inner: ExprType::new(code, rust_params),
            });
        }
        // String form
        if let Ok(s) = arg.extract::<String>() {
            if let Some(p) = &params {
                // Two-arg string form: ExprType("list", [ExprType("int")])
                let code = str_to_typecode(&s)?;
                let rust_params: Vec<ExprType> = p.iter().map(|p| p.inner.clone()).collect();
                validate_typecode_arity(code, &rust_params)?;
                return Ok(PyExprType {
                    inner: ExprType::new(code, rust_params),
                });
            }
            // Single-arg string form: ExprType("list[int]")
            return ExprType::parse(&s)
                .map(|t| PyExprType { inner: t })
                .map_err(pyo3::exceptions::PyValueError::new_err);
        }
        Err(pyo3::exceptions::PyTypeError::new_err(
            "ExprType() requires a string or TypeCode",
        ))
    }

    #[staticmethod]
    fn list(elem: &PyExprType) -> Self {
        PyExprType {
            inner: ExprType::list(elem.inner.clone()),
        }
    }

    #[staticmethod]
    fn union(types: Vec<PyExprType>) -> Self {
        PyExprType {
            inner: ExprType::union(types.into_iter().map(|t| t.inner).collect()),
        }
    }

    fn nullable(&self) -> Self {
        PyExprType {
            inner: ExprType::union(vec![self.inner.clone(), ExprType::NULLTYPE]),
        }
    }

    fn is_nullable(&self) -> bool {
        self.inner.code() == TypeCode::Union
            && self
                .inner
                .params()
                .iter()
                .any(|p| p.code() == TypeCode::NullType)
    }

    #[getter]
    fn type_code(&self) -> PyTypeCode {
        PyTypeCode::from(self.inner.code())
    }

    #[getter]
    fn type_params(&self) -> Vec<PyExprType> {
        self.inner
            .params()
            .iter()
            .map(|p| PyExprType { inner: p.clone() })
            .collect()
    }

    fn is_concrete(&self) -> bool {
        self.inner.is_concrete()
    }

    fn is_symbolic(&self) -> bool {
        self.inner.is_symbolic()
    }

    fn match_type(
        &self,
        py: Python<'_>,
        other: &PyExprType,
    ) -> PyResult<Option<Py<pyo3::types::PyDict>>> {
        use pyo3::IntoPyObjectExt;
        match self.inner.match_type(&other.inner) {
            None => Ok(None),
            Some(bindings) => {
                let dict = pyo3::types::PyDict::new(py);
                for (k, v) in bindings {
                    let py_key = PyTypeCode::from(k);
                    let py_val = PyExprType { inner: v };
                    dict.set_item(py_key.into_py_any(py)?, py_val.into_py_any(py)?)?;
                }
                Ok(Some(dict.into()))
            }
        }
    }

    fn substitute(&self, bindings: &Bound<'_, pyo3::types::PyDict>) -> PyResult<PyExprType> {
        let mut rust_bindings: HashMap<TypeCode, ExprType> = HashMap::new();
        for (k, v) in bindings.iter() {
            let tc: PyTypeCode = k.extract()?;
            let et: PyExprType = v.extract()?;
            rust_bindings.insert(tc.into(), et.inner);
        }
        Ok(PyExprType {
            inner: self.inner.substitute(&rust_bindings),
        })
    }

    fn __str__(&self) -> String {
        self.inner.to_string()
    }

    fn __repr__(&self) -> String {
        format!("ExprType(\"{}\")", self.inner)
    }

    fn __eq__(&self, other: &PyExprType) -> bool {
        self.inner == other.inner
    }

    fn __hash__(&self) -> u64 {
        use std::hash::{Hash, Hasher};
        let mut h = std::collections::hash_map::DefaultHasher::new();
        self.inner.hash(&mut h);
        h.finish()
    }

    /// Pickle support — round-trips through the spec-form string
    /// representation (e.g. `"int"`, `"list[int]"`).
    fn __reduce__<'py>(&self, py: Python<'py>) -> PyResult<(Bound<'py, PyType>, (String,))> {
        Ok((py.get_type::<Self>(), (self.inner.to_string(),)))
    }
}
