// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use std::sync::Arc;

use pyo3::prelude::*;
use pyo3::types::PyDict;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_sessions::session_user::SessionUser;

// ─────────────────────────────────────────────────────────────────
// PosixSessionUser
// ─────────────────────────────────────────────────────────────────

/// A PyO3 wrapper that holds an Arc<dyn SessionUser> for passing to Session.
#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.sessions._v1",
    name = "PosixSessionUser",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyPosixSessionUser {
    pub(crate) inner: Arc<dyn SessionUser>,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyPosixSessionUser {
    #[new]
    #[pyo3(signature = (user, *, group=None))]
    fn new(user: String, group: Option<String>) -> PyResult<Self> {
        #[cfg(unix)]
        {
            let ru = openjd_sessions::session_user::PosixSessionUser::new(&user, group.as_deref());
            Ok(Self {
                inner: Arc::new(ru),
            })
        }
        #[cfg(not(unix))]
        {
            // Suppress unused-variable warnings on non-unix targets.
            let _ = (user, group);
            Err(pyo3::exceptions::PyRuntimeError::new_err(
                "Only available on posix systems.",
            ))
        }
    }

    #[getter]
    fn user(&self) -> &str {
        self.inner.user()
    }

    #[getter]
    fn group(&self) -> &str {
        self.inner.group()
    }

    fn is_process_user(&self) -> bool {
        self.inner.is_process_user()
    }

    fn __repr__(&self) -> String {
        format!(
            "PosixSessionUser(user={:?}, group={:?})",
            self.inner.user(),
            self.inner.group()
        )
    }

    /// Pickle support — round-trips through `__init__(user, *, group=...)`.
    ///
    /// Note that on non-POSIX hosts the resulting object cannot be
    /// loaded (the constructor raises `RuntimeError`). This matches
    /// the reference Python class, which is also platform-restricted
    /// at construction time.
    fn __reduce__<'py>(
        &self,
        py: Python<'py>,
    ) -> PyResult<(Bound<'py, PyAny>, Py<pyo3::types::PyTuple>)> {
        use pyo3::types::PyTuple;
        let helper = py
            .import("openjd._openjd_rs")?
            .getattr("_reconstruct_kwargs")?;
        let cls = py.get_type::<Self>();
        let kwargs = PyDict::new(py);
        kwargs.set_item("user", self.inner.user())?;
        kwargs.set_item("group", self.inner.group())?;
        let args = PyTuple::new(py, [cls.into_any(), kwargs.into_any()])?;
        Ok((helper, args.into()))
    }
}

// ─────────────────────────────────────────────────────────────────
// WindowsSessionUser
// ─────────────────────────────────────────────────────────────────

// Exception raised for incorrect username or password.
//
// Mirrors the legacy Python `openjd.sessions.BadCredentialsException`. Lives
// in the `_openjd_rs` extension module; the v1 sessions package re-exports
// it under its canonical home.
pyo3::create_exception!(
    _openjd_rs,
    PyBadCredentialsException,
    pyo3::exceptions::PyException
);

/// PyO3 binding for `openjd_sessions::WindowsSessionUser`.
///
/// Mirrors the legacy Python `WindowsSessionUser` API: construct with
/// `WindowsSessionUser(user, *, password=..., logon_token=...)`. Exposes
/// `.user`, `.password`, `.logon_token`, and `is_process_user()`.
///
/// Validation of the username/password is performed unconditionally by the
/// underlying Rust `WindowsSessionUser::with_password` (which calls
/// `LogonUserW`). There is no Python-level override hook — callers that need
/// to bypass real Windows logon for testing must mock at a different layer
/// (e.g. patching the binding constructor itself).
///
/// The class is importable on all platforms so that consumers can reference
/// it in type annotations and `isinstance` checks, but actual instantiation
/// fails on non-Windows hosts with a `RuntimeError`, matching the legacy
/// Python class.
#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.sessions._v1", name = "WindowsSessionUser")]
pub(crate) struct PyWindowsSessionUser {
    pub(crate) inner: Arc<dyn SessionUser>,
    /// Cached password (if construction supplied one). Stored in the
    /// binding so the `.password` getter can return it; the underlying
    /// Rust `SessionUser` trait does not expose passwords.
    password: Option<String>,
    /// Cached logon token handle (Windows only). Stored as a raw
    /// `isize` so the type is platform-independent on the binding side.
    /// The actual handle lifetime is owned by the underlying Rust
    /// `WindowsSessionUser`.
    logon_token: Option<isize>,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyWindowsSessionUser {
    /// Create a `WindowsSessionUser`.
    ///
    /// Arguments mirror the legacy Python class. Exactly one of `password`
    /// or `logon_token` must be provided when the user is not the process
    /// owner. When the user is the process owner, both must be `None`.
    ///
    /// On Windows, supplying `password` triggers immediate credential
    /// validation via `LogonUserW`; a logon failure raises
    /// `BadCredentialsException`. On non-Windows hosts the constructor
    /// raises `RuntimeError` (matching the legacy Python class), but the
    /// type itself is importable.
    ///
    /// `logon_token` accepts either a Python `int` or any object with an
    /// `__int__` method (e.g. `ctypes.wintypes.HANDLE` from a pywin32
    /// `LogonUser` call). This matches the legacy Python class which used
    /// `ctypes.wintypes.HANDLE` directly.
    #[new]
    #[pyo3(signature = (user, *, password=None, logon_token=None))]
    fn new(
        user: String,
        password: Option<String>,
        logon_token: Option<Bound<'_, PyAny>>,
    ) -> PyResult<Self> {
        // Coerce logon_token (which may be a Python int OR a ctypes
        // HANDLE / c_void_p subclass) to a plain isize.
        //
        // ctypes objects expose `.value` for the integer payload; we
        // try that before falling back to extract::<isize> (which
        // works for plain int and anything implementing __index__).
        // Don't use `int(obj)` here -- on c_void_p subclasses
        // `int()` can return the raw bytes of the address, not an
        // integer (Python 3.11 PyO3 surface).
        let logon_token: Option<isize> = match logon_token {
            None => None,
            Some(obj) if obj.is_none() => None,
            Some(obj) => {
                if let Ok(value_attr) = obj.getattr("value") {
                    if let Ok(v) = value_attr.extract::<isize>() {
                        Some(v)
                    } else {
                        Some(obj.extract::<isize>()?)
                    }
                } else {
                    Some(obj.extract::<isize>()?)
                }
            }
        };
        #[cfg(windows)]
        {
            use openjd_sessions::session_user::{BadCredentialsError, WindowsSessionUser};

            if password.is_some() && logon_token.is_some() {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "The \"password\" and \"logon_token\" arguments are mutually exclusive",
                ));
            }

            // Determine whether `user` matches the process user.
            let is_process_user = openjd_sessions::win32::get_process_user()
                .map(|proc_user| user.eq_ignore_ascii_case(&proc_user))
                .unwrap_or(false);

            if is_process_user {
                if password.is_some() {
                    return Err(pyo3::exceptions::PyRuntimeError::new_err(
                        "User is the process owner. Do not provide a password.",
                    ));
                }
                if logon_token.is_some() {
                    return Err(pyo3::exceptions::PyRuntimeError::new_err(
                        "User is the process owner. Do not provide a logon token.",
                    ));
                }

                let ru = WindowsSessionUser::for_process_user()
                    .map_err(pyo3::exceptions::PyRuntimeError::new_err)?;
                return Ok(Self {
                    inner: Arc::new(ru),
                    password: None,
                    logon_token: None,
                });
            }

            // Cross-user path: must supply credentials.
            if password.is_none() && logon_token.is_none() {
                return Err(pyo3::exceptions::PyRuntimeError::new_err(
                    "Must supply a password or logon token. User is not the process owner.",
                ));
            }

            if let Some(pw) = password {
                if openjd_sessions::win32::is_session_zero() {
                    return Err(pyo3::exceptions::PyRuntimeError::new_err(
                        "Must supply a logon_token rather than a password. \
                         Passwords are not supported when running in Windows Session 0.",
                    ));
                }

                let ru = match WindowsSessionUser::with_password(&user, &pw) {
                    Ok(u) => u,
                    Err(BadCredentialsError::LogonFailure) => {
                        return Err(PyBadCredentialsException::new_err(
                            "The username or password is incorrect.",
                        ));
                    }
                    Err(BadCredentialsError::Other(msg)) => {
                        return Err(pyo3::exceptions::PyRuntimeError::new_err(msg));
                    }
                };
                Ok(Self {
                    inner: Arc::new(ru),
                    password: Some(pw),
                    logon_token: None,
                })
            } else {
                // logon_token path
                let token_isize = logon_token.unwrap();
                let handle =
                    windows::Win32::Foundation::HANDLE(token_isize as *mut core::ffi::c_void);
                let ru = WindowsSessionUser::with_logon_token(&user, handle)
                    .map_err(pyo3::exceptions::PyRuntimeError::new_err)?;
                Ok(Self {
                    inner: Arc::new(ru),
                    password: None,
                    logon_token: Some(token_isize),
                })
            }
        }

        #[cfg(not(windows))]
        {
            // Match the legacy Python class: instantiation is an error
            // on non-Windows, but the class itself is importable.
            let _ = (user, password, logon_token);
            Err(pyo3::exceptions::PyRuntimeError::new_err(
                "Only available on Windows systems.",
            ))
        }
    }

    #[getter]
    fn user(&self) -> &str {
        self.inner.user()
    }

    /// The password supplied at construction time, or `None` if construction
    /// used a logon token or no credentials.
    #[getter]
    fn password(&self) -> Option<&str> {
        self.password.as_deref()
    }

    /// The logon token supplied at construction time, or `None` if
    /// construction used a password or no credentials. Returned as an
    /// `int` mirroring `ctypes.wintypes.HANDLE` semantics.
    #[getter]
    fn logon_token(&self) -> Option<isize> {
        self.logon_token
    }

    fn is_process_user(&self) -> bool {
        self.inner.is_process_user()
    }

    fn __repr__(&self) -> String {
        format!("WindowsSessionUser(user={:?})", self.inner.user())
    }

    /// Pickle support — round-trips through `__init__(user, *,
    /// password=..., logon_token=...)`.
    ///
    /// **Caveats:**
    ///
    /// 1. Pickling a Windows password is sensitive — it is stored
    ///    plaintext in the pickle output. Avoid pickling
    ///    `WindowsSessionUser` to disk or over an untrusted channel.
    ///    This matches the reference Python `dataclass` which also
    ///    stored `password` as a plain field.
    /// 2. `logon_token` is a process-local Win32 HANDLE. The integer
    ///    value pickles correctly but does not refer to a valid handle
    ///    in another process; unpickling on a different process will
    ///    fail at `LogonUser` validation.
    /// 3. Unpickling on a non-Windows host raises `RuntimeError`,
    ///    matching the reference class.
    fn __reduce__<'py>(
        &self,
        py: Python<'py>,
    ) -> PyResult<(Bound<'py, PyAny>, Py<pyo3::types::PyTuple>)> {
        use pyo3::types::PyTuple;
        let helper = py
            .import("openjd._openjd_rs")?
            .getattr("_reconstruct_kwargs")?;
        let cls = py.get_type::<Self>();
        let kwargs = PyDict::new(py);
        kwargs.set_item("user", self.inner.user())?;
        if let Some(pw) = &self.password {
            kwargs.set_item("password", pw)?;
        }
        if let Some(tok) = self.logon_token {
            kwargs.set_item("logon_token", tok)?;
        }
        let args = PyTuple::new(py, [cls.into_any(), kwargs.into_any()])?;
        Ok((helper, args.into()))
    }
}
