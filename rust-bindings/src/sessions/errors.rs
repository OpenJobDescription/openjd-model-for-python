// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use openjd_sessions::error::SessionError;
use pyo3::prelude::*;

pyo3::create_exception!(_openjd_rs, PySessionError, pyo3::exceptions::PyRuntimeError);

pub(crate) fn session_err_to_py(e: SessionError) -> PyErr {
    PySessionError::new_err(e.to_string())
}
