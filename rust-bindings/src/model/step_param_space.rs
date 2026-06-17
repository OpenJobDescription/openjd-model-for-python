// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use std::collections::HashSet;
use std::sync::Mutex;

use pyo3::prelude::*;
use pyo3::types::PyDict;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_model::job::StepParameterSpace;
use openjd_model::types::{TaskParameterSet, TaskParameterType, TaskParameterValue};
use openjd_model::StepParameterSpaceIterator;

use super::job::{PyStep, PyStepParameterSpace};
use super::types::PyTaskParameterValue;
use crate::expr::expr_value::py_to_expr_value;
use crate::model::errors::model_err_to_py;

fn task_param_set_to_py(py: Python<'_>, params: &TaskParameterSet) -> PyResult<Py<PyDict>> {
    use pyo3::IntoPyObjectExt;
    let dict = PyDict::new(py);
    for (name, tpv) in params {
        let pv = PyTaskParameterValue { inner: tpv.clone() };
        dict.set_item(name, pv.into_py_any(py)?)?;
    }
    Ok(dict.unbind())
}

fn extract_task_parameter_set(dict: &Bound<'_, PyDict>) -> PyResult<TaskParameterSet> {
    let mut result = TaskParameterSet::new();
    for (key, val) in dict.iter() {
        let name: String = key.extract()?;
        if let Ok(type_attr) = val.getattr("type") {
            // Resolve the parameter type's spec string. Try `as_str()` first
            // (the convention used by the Rust-backed `PyTaskParameterType`
            // and `PyJobParameterType` pyclass enums, plus the Python-side
            // `ParameterValue` shim), then `.value` (stdlib `enum.Enum`
            // members from the pure-Python reference), then `__str__`.
            let type_str: String = type_attr
                .call_method0("as_str")
                .or_else(|_| type_attr.getattr("value"))
                .or_else(|_| type_attr.call_method0("__str__"))
                .and_then(|v| v.extract())?;
            let param_type =
                TaskParameterType::from_spec_str(&type_str).unwrap_or(TaskParameterType::String);
            let value_str: String = val.getattr("value")?.extract()?;
            let value = if param_type == TaskParameterType::ChunkInt {
                // CHUNK[INT] values are range expression strings like
                // `"1-5"` (produced by the iterator's `to_display_string`).
                // Parse to ExprValue::RangeExpr so that the iterator's
                // `validate_containment` — which matches structurally
                // against ExprValue::RangeExpr — can compare yielded
                // chunks. A plain INT coercion produces an
                // ExprValue::String that doesn't match.
                value_str
                    .parse::<openjd_expr::range_expr::RangeExpr>()
                    .map(openjd_expr::ExprValue::RangeExpr)
                    .unwrap_or(openjd_expr::ExprValue::String(value_str))
            } else {
                openjd_expr::ExprValue::from_str_coerce(
                    &value_str,
                    &param_type_to_expr_type(param_type),
                    openjd_expr::path_mapping::PathFormat::host(),
                )
                .unwrap_or(openjd_expr::ExprValue::String(value_str))
            };
            result.insert(name, TaskParameterValue { param_type, value });
        } else {
            let value = py_to_expr_value(&val)?;
            result.insert(
                name,
                TaskParameterValue {
                    param_type: TaskParameterType::String,
                    value,
                },
            );
        }
    }
    Ok(result)
}

fn param_type_to_expr_type(pt: TaskParameterType) -> openjd_expr::ExprType {
    match pt {
        TaskParameterType::Int | TaskParameterType::ChunkInt => openjd_expr::ExprType::INT,
        TaskParameterType::Float => openjd_expr::ExprType::FLOAT,
        TaskParameterType::String => openjd_expr::ExprType::STRING,
        TaskParameterType::Path => openjd_expr::ExprType::PATH,
        _ => openjd_expr::ExprType::STRING, // future variants
    }
}

/// Lock the iterator mutex, recovering the guard if a previous holder
/// panicked. A panic inside `next()` / `contains()` / `validate_containment()`
/// would otherwise poison the mutex, and every subsequent `.lock().unwrap()`
/// would raise an uncatchable `PanicException` on the Python side — wedging
/// the iterator object permanently. Recovering keeps it usable.
fn lock_recover<T>(m: &Mutex<T>) -> std::sync::MutexGuard<'_, T> {
    m.lock().unwrap_or_else(|poisoned| poisoned.into_inner())
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.model._v1.job", name = "StepParameterSpaceIterator")]
pub(crate) struct PyStepParameterSpaceIterator {
    /// Resolved parameter space — kept so `__getitem__` can build a
    /// fresh non-mutating iterator without having to walk back through
    /// `iter`'s internal cursor.
    space: StepParameterSpace,
    /// Cached length captured at construction time. Used by `__len__`
    /// for non-adaptive spaces (adaptive spaces raise instead).
    len: usize,
    /// Cached parameter names captured at construction time.
    names: HashSet<String>,
    /// The persistent iterator that backs `__next__`, `reset_iter`,
    /// `__contains__`, and `chunks_default_task_count` (getter and
    /// setter). Holding it across calls is what lets the setter
    /// actually mutate state — the underlying `Arc<AtomicUsize>` for
    /// adaptive chunking lives inside this iterator.
    ///
    /// `Mutex` is required because pyclass types must be `Sync`. The
    /// inner `StepParameterSpaceIterator` is `Send + Sync` because
    /// every `NodeIterator` impl is `Send + Sync` (enforced at the
    /// trait bound in `openjd-model`).
    iter: Mutex<StepParameterSpaceIterator>,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyStepParameterSpaceIterator {
    #[new]
    #[pyo3(signature = (*, step=None, space=None))]
    fn new(step: Option<&PyStep>, space: Option<&PyStepParameterSpace>) -> PyResult<Self> {
        let ps = if let Some(s) = space {
            s.inner.clone()
        } else if let Some(st) = step {
            st.inner
                .parameter_space
                .clone()
                .unwrap_or_else(|| StepParameterSpace {
                    task_parameter_definitions: Default::default(),
                    combination: None,
                })
        } else {
            // No space and no step — empty parameter space (1 task, no params)
            StepParameterSpace {
                task_parameter_definitions: Default::default(),
                combination: None,
            }
        };
        let iter = StepParameterSpaceIterator::new(&ps).map_err(model_err_to_py)?;
        let len = iter.len();
        let names = iter.names().clone();
        Ok(Self {
            space: ps,
            len,
            names,
            iter: Mutex::new(iter),
        })
    }

    fn __len__(&self) -> PyResult<usize> {
        // Match the pure-Python reference: adaptive-chunked spaces
        // cannot answer `len()` because the count depends on the
        // dynamic chunk size that may change during execution.
        let iter = lock_recover(&self.iter);
        if iter.chunks_adaptive() {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "Length is not available because the parameter space uses adaptive chunking.",
            ));
        }
        Ok(self.len)
    }

    fn __getitem__(&self, py: Python<'_>, index: isize) -> PyResult<Py<PyDict>> {
        let idx = if index < 0 {
            let adjusted = self.len as isize + index;
            if adjusted < 0 {
                return Err(pyo3::exceptions::PyIndexError::new_err(
                    "index out of range",
                ));
            }
            adjusted as usize
        } else {
            index as usize
        };
        // Random access uses a fresh iterator — don't disturb the
        // persistent iter's cursor or its adaptive Arc.
        let iter = StepParameterSpaceIterator::new(&self.space).map_err(model_err_to_py)?;
        match iter.get(idx) {
            Some(params) => task_param_set_to_py(py, &params),
            None => Err(pyo3::exceptions::PyIndexError::new_err(
                "index out of range",
            )),
        }
    }

    /// Iterator protocol — return self so `next(it)` and `for x in it`
    /// both advance the same shared cursor inside the persistent
    /// `StepParameterSpaceIterator`. Mirrors the Python reference,
    /// which also exposes `__iter__`/`__next__` directly.
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(&self, py: Python<'_>) -> PyResult<Option<Py<PyDict>>> {
        let mut iter = lock_recover(&self.iter);
        match iter.next() {
            Some(params) => Ok(Some(task_param_set_to_py(py, &params)?)),
            None => Ok(None),
        }
    }

    fn __contains__(&self, item: &Bound<'_, PyDict>) -> PyResult<bool> {
        let params = extract_task_parameter_set(item)?;
        let iter = lock_recover(&self.iter);
        Ok(iter.contains(&params))
    }

    /// Validate that ``params`` is contained in this iterator's
    /// parameter space. Returns ``None`` on success (matching the
    /// v0 reference's implicit-``None`` return). Raises
    /// :class:`ValueError` with a detailed diagnostic message on
    /// failure — naming the offending parameter or the mismatching
    /// name set as appropriate. Mirrors the underlying Rust
    /// crate's ``StepParameterSpaceIterator::validate_containment``.
    fn validate_containment(&self, params: &Bound<'_, PyDict>) -> PyResult<()> {
        let params = extract_task_parameter_set(params)?;
        let iter = lock_recover(&self.iter);
        iter.validate_containment(&params)
            .map_err(pyo3::exceptions::PyValueError::new_err)
    }

    fn reset_iter(&self) {
        let mut iter = lock_recover(&self.iter);
        iter.reset();
    }

    #[getter]
    fn names(&self) -> HashSet<String> {
        self.names.clone()
    }

    #[getter]
    fn chunks_adaptive(&self) -> bool {
        let iter = lock_recover(&self.iter);
        iter.chunks_adaptive()
    }

    #[getter]
    fn chunks_parameter_name(&self) -> Option<String> {
        let iter = lock_recover(&self.iter);
        iter.chunks_parameter_name().map(|s| s.to_string())
    }

    #[getter]
    fn chunks_default_task_count(&self) -> Option<usize> {
        let iter = lock_recover(&self.iter);
        iter.chunks_default_task_count()
    }

    #[setter]
    fn set_chunks_default_task_count(&self, value: usize) -> PyResult<()> {
        if value == 0 {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "chunks_default_task_count must be a positive integer.",
            ));
        }
        let mut iter = lock_recover(&self.iter);
        if !iter.chunks_adaptive() {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "The parameter space does not use adaptive chunking, so cannot modify chunks_default_task_count.",
            ));
        }
        iter.set_chunks_default_task_count(value);
        Ok(())
    }
}
