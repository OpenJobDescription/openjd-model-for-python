// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use openjd_expr::path_mapping::PathFormat;
use pyo3::prelude::*;
use pyo3::types::PyType;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyclass_enum(module = "openjd._openjd_rs")
)]
#[pyclass(
    module = "openjd.expr",
    name = "PathFormat",
    eq,
    eq_int,
    hash,
    frozen,
    from_py_object
)]
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
// Variant names follow Python's UPPER_CASE enum convention.
#[allow(clippy::upper_case_acronyms)]
pub(crate) enum PyPathFormat {
    POSIX = 0,
    WINDOWS = 1,
    URI = 2,
}

impl PyPathFormat {
    /// Variant name as a static `&str` (`"POSIX"`, `"WINDOWS"`,
    /// `"URI"`). Available outside `#[pymethods]` so other modules
    /// (e.g. `path_mapping::__repr__`) can use it for diagnostic
    /// rendering.
    pub(crate) fn variant_name(&self) -> &'static str {
        match self {
            PyPathFormat::POSIX => "POSIX",
            PyPathFormat::WINDOWS => "WINDOWS",
            PyPathFormat::URI => "URI",
        }
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyPathFormat {
    #[getter]
    fn name(&self) -> &'static str {
        self.variant_name()
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
        let cls = py.get_type::<Self>();
        Ok((helper, (cls, self.name())))
    }
}

impl From<PyPathFormat> for PathFormat {
    fn from(pf: PyPathFormat) -> Self {
        match pf {
            PyPathFormat::POSIX => PathFormat::Posix,
            PyPathFormat::WINDOWS => PathFormat::Windows,
            PyPathFormat::URI => PathFormat::Uri,
        }
    }
}

impl From<PathFormat> for PyPathFormat {
    fn from(pf: PathFormat) -> Self {
        match pf {
            PathFormat::Posix => PyPathFormat::POSIX,
            PathFormat::Windows => PyPathFormat::WINDOWS,
            PathFormat::Uri => PyPathFormat::URI,
        }
    }
}
