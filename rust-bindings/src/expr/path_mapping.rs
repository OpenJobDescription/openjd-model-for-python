// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use pyo3::prelude::*;
use pyo3::types::PyDict;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_expr::path_mapping::{PathFormat, PathMappingRule};

use crate::expr::path_format::PyPathFormat;

/// Extract a path argument, accepting str or the appropriate pathlib type for the format.
fn extract_path_arg(
    obj: &Bound<'_, pyo3::PyAny>,
    fmt: PyPathFormat,
    name: &str,
) -> PyResult<String> {
    if let Ok(s) = obj.extract::<String>() {
        return Ok(s);
    }
    let type_name = obj.get_type().name()?.to_string();
    match fmt {
        PyPathFormat::POSIX => {
            if type_name == "PurePosixPath" || type_name == "PosixPath" {
                return Ok(obj.str()?.to_string());
            }
            // The pure-Python reference (`PathMappingRule.__init__`)
            // raises `ValueError` with the exact phrase
            // `"source_path_format does not match source_path type"`.
            // We keep that phrase verbatim so callers porting from v0
            // continue to match it, then append the actionable detail
            // (which format was expected, what type was supplied) so
            // the message tells the user how to fix their call.
            Err(pyo3::exceptions::PyValueError::new_err(format!(
                "Path mapping rule source_path_format does not match source_path type: \
                 {name} must be str or PurePosixPath for POSIX format, got {type_name}"
            )))
        }
        PyPathFormat::WINDOWS => {
            if type_name == "PureWindowsPath" || type_name == "WindowsPath" {
                return Ok(obj.str()?.to_string());
            }
            Err(pyo3::exceptions::PyValueError::new_err(format!(
                "Path mapping rule source_path_format does not match source_path type: \
                 {name} must be str or PureWindowsPath for WINDOWS format, got {type_name}"
            )))
        }
        PyPathFormat::URI => Err(pyo3::exceptions::PyValueError::new_err(format!(
            "Path mapping rule source_path_format does not match source_path type: \
             {name} must be str for URI format, got {type_name}"
        ))),
    }
}

/// Extract a destination path, accepting str or any pathlib Path type.
fn extract_path_str(obj: &Bound<'_, pyo3::PyAny>, name: &str) -> PyResult<String> {
    if let Ok(s) = obj.extract::<String>() {
        return Ok(s);
    }
    let type_name = obj.get_type().name()?.to_string();
    if type_name.contains("Path") {
        return Ok(obj.str()?.to_string());
    }
    Err(pyo3::exceptions::PyTypeError::new_err(format!(
        "{name} must be str or Path, got {type_name}"
    )))
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.expr", name = "PathMappingRule", from_py_object)]
#[derive(Clone)]
pub(crate) struct PyPathMappingRule {
    pub(crate) inner: PathMappingRule,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyPathMappingRule {
    #[new]
    #[pyo3(signature = (*, source_path_format, source_path, destination_path))]
    fn new(
        source_path_format: PyPathFormat,
        source_path: &Bound<'_, pyo3::PyAny>,
        destination_path: &Bound<'_, pyo3::PyAny>,
    ) -> PyResult<Self> {
        let src = extract_path_arg(source_path, source_path_format, "source_path")?;
        let dst = extract_path_str(destination_path, "destination_path")?;
        // For URI source format, validate the URI form up-front —
        // matches the v0 reference's ``__init__`` check, which
        // raises ``ValueError`` if ``source_path`` doesn't parse
        // as a URI (i.e., doesn't start with ``scheme://``).
        // Without this validation the binding silently accepts
        // any string and the misuse only surfaces later, when
        // path-mapping is applied at session-time.
        if source_path_format == PyPathFormat::URI && !openjd_expr::path_mapping::is_uri(&src) {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "Path mapping rule with URI source_path_format requires a URI string source_path",
            ));
        }
        Ok(PyPathMappingRule {
            inner: PathMappingRule {
                source_path_format: source_path_format.into(),
                source_path: src,
                destination_path: dst,
            },
        })
    }

    #[getter]
    fn source_path_format(&self) -> PyPathFormat {
        self.inner.source_path_format.into()
    }

    #[getter]
    fn source_path(&self) -> &str {
        &self.inner.source_path
    }

    #[getter]
    fn destination_path(&self) -> &str {
        &self.inner.destination_path
    }

    fn __repr__(&self) -> String {
        // Render `source_path_format` using its Python name
        // (`PathFormat.POSIX`) rather than the underlying Rust
        // enum's `Debug` name (`Posix`). Matches the Python
        // convention for enum repr.
        let fmt: PyPathFormat = self.inner.source_path_format.into();
        format!(
            "PathMappingRule(source_path_format=PathFormat.{}, source_path='{}', destination_path='{}')",
            fmt.variant_name(), self.inner.source_path, self.inner.destination_path
        )
    }

    /// Two `PathMappingRule`s compare equal when they have the
    /// same `source_path_format`, `source_path`, and
    /// `destination_path`. Returns `False` for non-rule
    /// arguments.
    fn __eq__(&self, other: &Bound<'_, pyo3::PyAny>) -> PyResult<bool> {
        let Ok(rhs) = other.extract::<PyRef<'_, PyPathMappingRule>>() else {
            return Ok(false);
        };
        Ok(
            self.inner.source_path_format == rhs.inner.source_path_format
                && self.inner.source_path == rhs.inner.source_path
                && self.inner.destination_path == rhs.inner.destination_path,
        )
    }

    /// Hash on the same three fields used by `__eq__`. Equal
    /// rules hash equal — required by Python's hash/eq contract.
    fn __hash__(&self) -> u64 {
        use std::hash::{DefaultHasher, Hash, Hasher};
        let mut h = DefaultHasher::new();
        // PathFormat is repr-stable; hash by Debug repr.
        format!("{:?}", self.inner.source_path_format).hash(&mut h);
        self.inner.source_path.hash(&mut h);
        self.inner.destination_path.hash(&mut h);
        h.finish()
    }

    #[pyo3(signature = (*, path, output_format=None))]
    fn apply(&self, path: &str, output_format: Option<PyPathFormat>) -> (bool, String) {
        let result = match output_format {
            Some(fmt) => self.inner.apply_with_format(path, fmt.into()),
            None => self.inner.apply(path),
        };
        match result {
            Some(mapped) => (true, mapped),
            None => (false, path.to_string()),
        }
    }

    fn to_dict(&self) -> std::collections::HashMap<String, String> {
        let mut d = std::collections::HashMap::new();
        d.insert(
            "source_path_format".into(),
            match self.inner.source_path_format {
                PathFormat::Posix => "POSIX",
                PathFormat::Windows => "WINDOWS",
                PathFormat::Uri => "URI",
            }
            .into(),
        );
        d.insert("source_path".into(), self.inner.source_path.clone());
        d.insert(
            "destination_path".into(),
            self.inner.destination_path.clone(),
        );
        d
    }

    #[staticmethod]
    fn from_dict(d: &Bound<'_, PyDict>) -> PyResult<Self> {
        // The supported field set, in the canonical order. Used both
        // for the "requires the following fields" diagnostic (Python
        // list repr with single-quoted names) and for the
        // unsupported-keys check below. Matches the v0 reference's
        // ``[field.name for field in fields(PathMappingRule)]``.
        const SUPPORTED: [&str; 3] = ["source_path_format", "source_path", "destination_path"];
        // Format the field-names list the same way Python's ``repr``
        // does for a ``list[str]``: ``['a', 'b', 'c']``. The v0
        // reference relies on f-string interpolation
        // (``f"...{field_names}"``) to produce that form, and tests
        // pin the exact substring; matching it verbatim is required
        // for parity.
        let field_names_repr = format!(
            "[{}]",
            SUPPORTED
                .iter()
                .map(|s| format!("'{s}'"))
                .collect::<Vec<_>>()
                .join(", "),
        );
        let get = |key: &str| -> PyResult<String> {
            d.get_item(key)?
                .ok_or_else(|| {
                    pyo3::exceptions::PyValueError::new_err(format!(
                        "Path mapping rule requires the following fields: {field_names_repr}"
                    ))
                })?
                .extract::<String>()
        };
        if d.is_empty() {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "Empty path mapping rule",
            ));
        }
        // Reject keys outside the supported set up-front, matching the
        // pure-Python reference. Build a sorted set so the error
        // message is deterministic across Python's dict ordering.
        let mut unsupported: Vec<String> = Vec::new();
        for key in d.keys() {
            let key_str: String = key.extract()?;
            if !SUPPORTED.contains(&key_str.as_str()) {
                unsupported.push(key_str);
            }
        }
        if !unsupported.is_empty() {
            unsupported.sort();
            // Mirror Python's `set` repr:
            // `{'extra1', 'extra2'}`.
            let formatted = format!(
                "{{{}}}",
                unsupported
                    .iter()
                    .map(|s| format!("'{s}'"))
                    .collect::<Vec<_>>()
                    .join(", "),
            );
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "Unsupported fields for constructing path mapping rule: {formatted}"
            )));
        }
        let fmt_str = get("source_path_format")?;
        let fmt = match fmt_str.to_uppercase().as_str() {
            "POSIX" => PyPathFormat::POSIX,
            "WINDOWS" => PyPathFormat::WINDOWS,
            "URI" => PyPathFormat::URI,
            other => {
                return Err(pyo3::exceptions::PyValueError::new_err(format!(
                    "Unknown path format: {other}"
                )))
            }
        };
        let source_path = get("source_path")?;
        // Apply the same URI validation the constructor enforces.
        // Without this, ``from_dict`` could accept a non-URI
        // ``source_path`` for a URI-format rule and silently
        // construct a rule that never matches anything at session
        // time. Pinned for parity with the v0 reference's
        // ``__init__`` check (which the v0 ``from_dict`` also
        // routes through).
        if fmt == PyPathFormat::URI && !openjd_expr::path_mapping::is_uri(&source_path) {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "Path mapping rule with URI source_path_format requires a URI string source_path",
            ));
        }
        Ok(PyPathMappingRule {
            inner: PathMappingRule {
                source_path_format: fmt.into(),
                source_path,
                destination_path: get("destination_path")?,
            },
        })
    }

    /// Pickle support — round-trips through `to_dict` / `from_dict`.
    #[allow(clippy::type_complexity)] // pickle reducer tuple shape is by design
    fn __reduce__<'py>(
        &self,
        py: Python<'py>,
    ) -> PyResult<(
        Bound<'py, PyAny>,
        (std::collections::HashMap<String, String>,),
    )> {
        let cls = py.get_type::<Self>();
        let from_dict = cls.getattr("from_dict")?;
        Ok((from_dict, (self.to_dict(),)))
    }
}
