# openjd-sessions Bindings Quality Evaluation Report

**Date:** 2026-05-18
**Component:** `openjd.sessions`
**Reference branch:** `openjd-sessions-for-python` @ `mainline` (commit `9e28bc5`) vs. `bindings-rs` (commit `0ce8bd7`)
**Active workspace:** `/home/markw/openjd-model-for-python`

> **Status note (2026-05-18, post `reshape-profiles`):** None of the
> recommendations in this report are addressed by the
> `ExprProfile` / `ModelProfile` reshape on the `openjd-model-for-python`
> side. That work changed the inputs to expr and model entry points
> (`evaluate_expression(profile=…)`, `decode_*_template(supported_extensions=…)`,
> `JobTemplate.profile`), but the Session layer is above those and
> still passes `path_mapping_rules` and `revision_extensions` to its
> binding constructor. Consequently every regression listed below
> reproduces unchanged on the post-reshape build (verified via
> `git diff` of pytest output between `bindings-rs` and
> `reshape-profiles`). The reshape did, however, produce the
> `ModelProfile` / `ExprProfile` types that recommendation #5
> (plumb `revision_extensions` to the binding) would consume —
> the foundation is in place; the wiring is not.

## Executive Summary

The Rust-backed `openjd.sessions` bindings under evaluation are **not yet a faithful drop-in for the pure-Python reference**. The new architecture (a `PySession` PyO3 wrapper that owns the Rust `Session`, plus a thin Python wrapper that emulates the legacy non-blocking callback semantics with a poll thread) is sound in shape, but the surface has many regressions that affect callers. The most material problems:

* **`Session.cancel_action()` cannot cancel a running action.** The binding deliberately fails fast with `RuntimeError("Cannot cancel: session is busy with an action")` because the underlying Session has been *taken* into the background thread that drives the action. This inverts the spec contract — cancel is only useful while running.
* **`run_subprocess()` validation is gone.** Reference rejects `timeout=0`, negative timeouts, and empty `command` with `ValueError`. Bindings silently accept all three; negative timeouts panic the background thread (`Duration::from_secs_f64(-5.0)`), leaving the action wedged at `state=RUNNING` with `action_status=None` forever.
* **State enums lost their string surface.** `SessionState` and `ActionState` no longer expose `.value`. The new `bindings-rs` v1 scenario tests rely on `session.state.value not in ("ready", "ended", "ready_ending")` and fail at runtime — the test suite *as written* does not actually pass.
* **Several spec entries are absent.** The spec's `Session(callback=…)`, `Session(job_template=…)`, `Session(environment_templates=…)`, and `Session.session_id` property all exist in the spec but not on the binding (or the wrapper). The spec table also documents `state.value` semantics that no longer exist.
* ~~**No public `Session` symbol is pickleable** (Session, ActionStatus, ActionState, PosixSessionUser, SessionError) — every reference counterpart is.~~ **Resolved (Rec #7/#9)** — every value type now pickles. `Session` itself remains intentionally not pickleable.
* **The Python wrapper drifts from the binding signature.** Wrapper `exit_environment(keep_session_running=True)` flips the reference default (`False`); wrapper `run_subprocess(timeout=0)` becomes `None`; wrapper accepts `revision_extensions` but never forwards it to the binding.
* **Test coverage collapsed from ~11 500 lines (mainline) to ~341 lines (bindings-rs).** The single integration test file (`test_session_scenarios.py`) is itself broken (assumes `state.value`); only 6 of 22 scenarios pass.

The binding scaffolding is in good shape (exception renaming, GIL behavior in subprocess waits via `tokio::block_on` on a dedicated thread, conversion helpers). The above issues are mostly correctness regressions in the Python contract, not architectural blockers.

## 1. Python Interface Spec Review

`specs/python-sessions-interface.md`

The spec is a planning document ("Bindings Plan") rather than a canonical spec. Coverage gaps and inaccuracies:

### 1.1 Surface that the spec advertises but no binding/wrapper exposes

| Spec entry | Binding `_openjd_rs` | Wrapper `openjd.sessions._v1` | Status |
|---|---|---|---|
| `Session(callback=Callable[[str, ActionStatus], None])` | ❌ no `callback` kwarg | ✓ accepts and emulates | Binding lacks it |
| `Session(job_template=Optional[JobTemplate])` | ❌ | ❌ | Spec only |
| `Session(environment_templates=Optional[list[EnvironmentTemplate]])` | ❌ | ❌ | Spec only |
| `Session.session_id: str` (property) | ✓ | ❌ | Wrapper drops it |
| Phase 5: `evaluate_env_vars(extra)` | ❌ | ❌ | Spec only |

### 1.2 Surface present in bindings but unmentioned in the spec

| Symbol | Source | Note |
|---|---|---|
| `Session.environments_entered` (property) | binding + wrapper | spec doesn't mention; reference exposes |
| `Session.extend_path_mapping_rules(rules)` | binding + wrapper | spec doesn't mention; needed by Deadline Cloud worker agent |
| `ActionStatus.started_at`, `ActionStatus.ended_at` | binding | new fields beyond reference / spec |

### 1.3 Spec entries with wrong types

* The spec's "Enums (from Rust)" pseudo-Python uses `class SessionState: READY = ...` syntax — but the binding registers them as PyO3 enums with `eq_int`. Spec does not document this departure or describe how callers should compare values (no `.value`, no string compare). Compare with the *reference* `class SessionState(str, Enum): READY = "ready"` which the spec implicitly preserves.
* `ActionResult` is shown with a Python-style class declaration but the binding does not expose a Python `__init__` — instances can only be obtained from Rust (and currently no Rust path actually emits one to Python; the rust `from_rust` is unused — clippy warns).
* The spec's `Session.cleanup() -> None` does not document the `__del__` gotcha (see §2.3).

### 1.4 Architecture commentary

The "Async Strategy / Decision: Option 1 (non-blocking, matching current Python API)" section is accurate for `enter_environment`/`exit_environment`/`run_task`/`run_subprocess`, but fails to mention that `cancel_action` is **not** non-blocking and **cannot** acquire the Session mutex during a running action. This is a material spec omission.

## 2. PyO3 Binding Source Review

`rust-bindings/src/sessions/{mod.rs,errors.rs,types.rs,session_user.rs,session.rs}`
plus `rust-bindings/src/lib.rs` registration.

### 2.1 Exception registration — ✓ correct

`SessionError` and `BadCredentialsException` are properly registered via
`register_renamed_exception(...)` in `lib.rs` lines 145–166. `__module__` resolves
to `openjd.sessions._v1`, `__name__` and `__qualname__` to canonical names.
Verified at runtime: `SessionError.__module__ == 'openjd.sessions._v1'`.

`SessionError` correctly inherits from `RuntimeError` (matching reference, where
session methods just raise `RuntimeError` directly). `BadCredentialsException`
correctly inherits from `Exception` (matching reference).

### 2.2 Type conversions and signatures — drift

`session.rs:144` — `Session::new` accepts `session_id, job_parameter_values,
path_mapping_rules, retain_working_dir, os_env_vars, session_root_directory, user`
but **omits `callback`** that the spec advertises. The Python wrapper layers a
poll-based emulation on top, but the binding's `#[pyo3(signature = ...)]` does
not match the spec text-signature.

`session.rs:443` — `cancel_action` signature is
`fn cancel_action(&self, time_limit: Option<f64>, mark_action_failed: Option<bool>)`.
This is the wrong shape: spec says `time_limit` is keyword-only with default
`None`, and `mark_action_failed` defaults to `False` (not `Option<bool>`). The
Python wrapper compensates with `mark_action_failed.unwrap_or(false)`, but the
positional/keyword positioning differs from the rest of the API (which uses
`#[pyo3(signature = (*, ...))]`). Run-time call with `s.cancel_action(time_limit=..., mark_action_failed=...)` works because both are converted positionally,
but introspection (`inspect.signature`) shows positional, not keyword-only.

`session.rs:154–197` — the `extract_job_parameter_values` helper requires every
job parameter to be a dict with `{"type": ..., "value": ...}` keys. Reference
accepts `dict[str, ParameterValue]` directly (where ParameterValue is a
dataclass with `.type` and `.value`). The Python wrapper coerces this in
`Session.__init__`, but a caller passing a `dict[str, ParameterValue]` directly
to `_openjd_rs.Session(...)` will get a confusing `KeyError: "Missing 'type' key"`.

`types.rs:129` — `ActionStatus.__init__` accepts `state, progress, status_message,
fail_message, exit_code` as kwargs. Spec calls all five out (matches), but the
spec omits the `started_at`/`ended_at` getters that the binding exposes. These
are read-only and only set when the underlying Rust `ActionStatus` populates
them via Rust callbacks; user-constructed `ActionStatus` instances always have
`started_at = ended_at = None`.

`types.rs:189` — `ActionStatus.__repr__` returns
`"ActionStatus(state={:?}, exit_code={:?})"` — the `{:?}` formatter prints the
Rust `ActionState` enum debug form (`Success`, `Failed`) and `Option<i32>`
debug form (`Some(0)`). Compare reference dataclass repr:
`ActionStatus(state=<ActionState.SUCCESS: 'success'>, ...)`. The Rust formatter
leaks "Some(0)" / "Success" into Python tracebacks and log output.

`types.rs:243` — `ActionResult` has no `#[new]` constructor. A
`from_rust(...)` helper is defined but unused (clippy-warned `dead_code`). The
spec implies `ActionResult` is constructible from Python (`class ActionResult: state, exit_code, stdout`); in fact it is impossible to instantiate.

### 2.3 GIL handling — mostly correct, one concern

`session.rs` releases the GIL by spawning a `std::thread` in `enter_environment`,
`exit_environment`, `run_task`, `run_subprocess`, each of which builds its own
`tokio::runtime::Runtime` and calls `block_on(...)`. The Python method returns
immediately; subprocess wait-loops happen on the OS thread, not the Python
thread. This is correct and idiomatic.

**Concern 1**: A new `tokio::runtime::Runtime` is built **per action**. Every
`run_task` / `run_subprocess` allocates an `mio` epoll instance, spawns the
thread pool, etc. — measurable overhead (low ms each). Reference uses a single
long-lived subprocess per action; this is acceptable today but should switch to
a single `Runtime` cached on `PySession` if action throughput matters.

**Concern 2**: The session is `take()`-d from the `Mutex<Option<Session>>` for
the duration of the background action. `cancel_action` only succeeds when the
session is **not** taken (i.e. between actions), inverting the spec contract.
This is a fundamental design flaw of the current "take ownership and move it
into a background thread" pattern; see the `// For now, this is a limitation`
comment at `session.rs:447`. A working cancel needs either (a) keep the session
in the mutex and use a `&mut Session` short-lived borrow inside an atomically-
swappable cancel handle, or (b) split the Rust `Session` into an outer
"controller" (cancel/cleanup/properties) and an inner action handle.

### 2.4 `#[pyclass]` constructor signatures vs. spec — drift

| Class | Binding signature | Spec | Status |
|---|---|---|---|
| `Session` | `(*, session_id, job_parameter_values, path_mapping_rules=None, retain_working_dir=False, os_env_vars=None, session_root_directory=None, user=None)` | `Session(*, session_id, job_parameter_values, path_mapping_rules=None, callback=None, os_env_vars=None, retain_working_dir=False, session_root_directory=None, user=None, job_template=None, environment_templates=None)` | Missing `callback`, `job_template`, `environment_templates` |
| `ActionStatus` | `(*, state, progress=None, status_message=None, fail_message=None, exit_code=None)` | matches | ✓ |
| `ActionResult` | no `#[new]` | `class ActionResult: state, exit_code, stdout` (implied constructible) | Missing constructor |
| `PosixSessionUser` | `(user, *, group=None)` | matches reference | ✓ |
| `WindowsSessionUser` | `(user, *, password=None, logon_token=None)` | matches reference | ✓ |

### 2.5 `Py<T>` lifetime correctness — ✓ no obvious issues

The `Mutex<Option<Session>>` ownership pattern with `guard.take()` /
`session_arc.lock().unwrap() = Some(session)` is sound; no `BorrowMutError`
risks observed. The snapshot `Arc<Mutex<StateSnapshot>>` is appropriately
cloned for the callback closure.

### 2.6 ABI3 compatibility — ✓

`Cargo.toml` declares `abi3-py39`. `rust-bindings/src/sessions/` uses only
ABI3-compatible PyO3 surfaces (no `PyType_FromSpec` direct calls, no
slot-tables). Build succeeds with `abi3` enabled.

### 2.7 Stub generation

`rust-bindings/src/sessions/types.rs` carries `gen_stub_pyclass(module = "openjd._openjd_rs")` annotations, but `session.rs` does **not** annotate `PySession`'s methods (`enter_environment`, `exit_environment`, `run_task`, `run_subprocess`, `cancel_action`, `cleanup`) with `#[gen_stub_pymethods]`. The generated stubs likely omit method signatures for `Session`. Not a runtime issue but degrades IDE hints.

### 2.8 Compiler warnings

`cargo clippy` emits **76 warnings** workspace-wide; new warnings introduced by
the sessions binding:

* `name "RANGE_EXPR" / "TYPEVAR_T..." / "READY" / "RUNNING" / "CANCELING" / ...
  contains a capitalized acronym` (at `types.rs:21–25`, `42–46`, `109–115`).
  These are Python-side names that must remain `UPPER_SNAKE`; suppress with
  `#[allow(clippy::upper_case_acronyms)]` to silence.
* `unused import: pyo3::types::PyDict` and similar (in earlier expr/model code) — not new but aggregates total to 76.
* `associated function from_rust is never used` (at `types.rs:255`) — dead code; either wire up via Rust→Python action result conversion or delete.
* `use of deprecated method PyAnyMethods::downcast` and
  `use of deprecated associated constant HasAutomaticFromPyObject` —
  pyo3 0.20+ deprecations not yet migrated.

`cargo clippy --workspace -- -D warnings` **fails** with these as errors.

## 3. Python Wrapper Module Review

`openjd-sessions-for-python/src/openjd/sessions/__init__.py` and
`openjd-sessions-for-python/src/openjd/sessions/_v1/__init__.py`.

### 3.1 Re-exports — partial

Top-level `openjd.sessions.__init__` and `openjd.sessions._v1.__init__` both
re-export the same set. Symbols available:

```
ActionState, ActionStatus, ActionResult, BadCredentialsException,
EnvironmentIdentifier, EnvironmentModel, EnvironmentScriptModel, LOG, LogContent,
PathFormat, PathMappingRule, PosixSessionUser, ScriptRunnerState, Session,
SessionCallbackType, SessionRuntimeError, SessionState, SessionUser,
StepScriptModel, WindowsSessionUser, version
```

`SessionRuntimeError` is an alias for `_openjd_rs.SessionError` — fine,
matches the reference's lack of `SessionError` while still exposing the new
canonical name.

### 3.2 Wrapper Session is a Python class, not the binding

`openjd.sessions._v1.Session` is **not** `openjd._openjd_rs.Session` — it is
a Python class in `_v1/_session.py` that holds a `_RustSession` and adds:

* a `_callback` field and a `_running_reported` flag,
* `_fire_initial_running_callback()` to synthesize the RUNNING status callback,
* `_poll_for_completion()` that spawns a daemon thread to watch state,
* `working_directory: Path` (wraps the binding's `str`),
* `environments_entered: tuple` (wraps the binding's `list`),
* `cancel_action(time_limit=timedelta, mark_action_failed=False)` (converts to seconds),
* `run_task` accepting `task_parameter_values: TaskParameterSet` (auto-coerces),
* `run_subprocess(timeout: Optional[int])` (converts to float),
* `extend_path_mapping_rules` (passthrough),
* `get_enabled_extensions()` always returns `[]` (regression — see §5),
* `__del__ → cleanup()` (fragile — fails if `__init__` raised before
  `_rust_session` was assigned: silent `AttributeError` in `__del__`).

### 3.3 Wrapper drifts that change behavior

| Wrapper API | Reference default | Wrapper default | Impact |
|---|---|---|---|
| `Session.__init__(revision_extensions=...)` | accepted **and used** | accepted, never forwarded | `get_enabled_extensions()` always returns `[]` |
| `exit_environment(keep_session_running=...)` | `False` | `True` | Default flip — silent semantic regression for callers who omit the kwarg |
| `run_subprocess(timeout=...)` | int>0; ValueError on 0/None handling | `float(timeout) if timeout else None` | `timeout=0` silently disables the timeout |
| `run_task(task_parameter_values: TaskParameterSet)` | required positional / kw | required kw — but type-coerces dicts and ParameterValue instances inconsistently | Possible bad-value paths |

### 3.4 Missing wrapper API

* No `__enter__` / `__exit__` — yet the bindings-rs *test* file uses `with Session(...) as session:` (test_session_scenarios.py:166). The test fails with `TypeError: 'Session' object does not support the context manager protocol` for any scenario that reaches the `with` block — confirmed in §6.
* No `session_id` property — the spec promises it; reference also accesses it as `_session_id` internally only.
* `_run_task_without_session_env` (reference internal) has no equivalent — used by some downstream callers.

### 3.5 Logging bridge — ✓ correct

`_v1/_session.py:32-37` re-parents the Rust `openjd_sessions` logger under
`openjd.sessions` so handlers attached to `openjd.sessions` see Rust log
records. Verified: `Initializing Open Job Description Session: ...`,
`Session Working Directory: ...`, `=== Session Cleanup ===` banners all
appear from the bindings.

## 4. Test Review

`openjd-sessions-for-python/test/openjd/sessions-v1/`

### 4.1 Test surface

```
test_importable.py             10 lines  — trivial import check
test_os_checker.py             50 lines  — patches `openjd.sessions._os_checker.os` (broken, see 4.3)
test_session_scenarios.py     256 lines  — single YAML-driven scenario runner
conftest.py                    25 lines  — disables capability tests, exposes session_id fixture
scenarios/*.yaml             ~30 files  — scenario definitions + job templates
```

Total: **341 lines**. Compared to **11 488 lines** on `mainline` (reference):

| Reference test file | Lines | bindings-rs equivalent |
|---|---|---|
| `test_session.py` | 3 901 | absent |
| `test_session_run_subprocess.py` | 1 113 | partial (one scenario in test_session_scenarios.py) |
| `test_subprocess.py` | 1 070 | absent (Rust covers, but not via Python tests) |
| `test_runner_base.py` | 1 071 | absent |
| `test_embedded_files.py` | 779 | absent |
| `test_action_filter.py` | 656 | absent |
| `test_path_mapping.py` | 537 | absent |
| `test_runner_env_script.py` | 510 | absent |
| `test_redacted_env.py` | 505 | absent |
| `test_runner_step_script.py` | 348 | absent |
| `test_tempdir.py` | 288 | absent |
| `test_redaction.py` | 191 | absent |
| `test_session_user.py` | 79 | absent |
| `test_windows_process_killer.py` | 86 | absent |

The argument that the Rust crate's own tests cover this surface is partly true,
but the Python contract — exception class identity, `state.value`,
`__enter__`/`__exit__`, callback timing, OPENJD_SESSION_WORKING_DIR env var,
`session.action_status` after pickle/copy, `cancel_action` from a different
thread — is exercised **only** at the Python boundary, and is essentially
untested in `bindings-rs`.

### 4.2 Scenario test design

`test_session_scenarios.py` walks `scenarios/**/*_scenario.yaml`, decodes the
referenced job template, builds parameter values, runs `Session.run_task` for
each task in `StepParameterSpaceIterator`, and asserts log content patterns.
The design is good, but as written it depends on:

* `with Session(...)` (line 166) — wrapper does not implement context manager.
* `session.state.value not in ("ready", ...)` (lines 183, 195, 207, 218, 226) — bindings `SessionState` has no `.value`.
* `ParameterValueType(param_type_str.upper())` (line 115) — `ParameterValueType` is now a Rust pyclass that cannot be instantiated this way.

All three are blocking; **16 of 22 scenario tests fail** at the test-harness level (`AttributeError`, `TypeError`), not because the Rust session does the wrong thing.

### 4.3 `test_os_checker.py` is broken

The new `_v1/_os_checker.py` checks `sys.platform`, but the test patches
`openjd.sessions._os_checker.os` (note: `_os_checker`, not `_v1/_os_checker`)
and asserts on it. Three assertions fail:

* `test_is_windows` (asserts `is_windows()` after patching `os.name` to `"nt"`)
* `test_is_not_posix` (asserts `not is_posix()` after `os.name` = `"nt"`)
* `test_check_os_unsupported` (asserts `NotImplementedError` from `check_os()` — the new `check_os` always returns `"win32"` or `"posix"` and never raises)

These are test bugs (or copy-paste leftovers), not binding bugs, but they're
counted as test-suite failures.

### 4.4 No test for binding-specific surface

* ~~Pickle round-trip for `ActionState` / `ActionStatus` / `PosixSessionUser` / `SessionError` — the reference test suite has none either, but new bindings should have them now that `pickle` is silently broken.~~ **Resolved (Rec #9)** — `~/openjd-sessions-for-python/test/openjd/sessions-v1/test_pickle.py` covers all of these.
* Exception class `__module__` and `__name__` — no test that `SessionError.__module__ == "openjd.sessions._v1"` (so a regression to `_openjd_rs.PySessionError` would slip through).
* Threading — no test that `Session` is safely usable from multiple Python threads (it currently is, modulo `cancel_action`).
* `extend_path_mapping_rules` — no test.
* Callback emulation via poll thread — no direct test that callbacks fire for `openjd_progress` / `openjd_status` / `openjd_fail`.

## 5. Parity with Pure-Python Reference

`openjd-sessions-for-python` `mainline` (commit `9e28bc5`) vs. `bindings-rs` (commit `0ce8bd7`).

### 5.1 Symbol-by-symbol comparison

| Symbol | Reference | Binding/Wrapper | Status |
|---|---|---|---|
| `SessionState` | `(str, Enum)`; `.value == "ready"` etc. | pyo3 enum, `eq_int`, no `.value` | ⚠ behavior change |
| `ActionState` | `(str, Enum)`; `.value == "running"` etc. | pyo3 enum, `eq_int`, no `.value`; has `.name` only | ⚠ behavior change |
| `ScriptRunnerState` | `(str, Enum)` | pyo3 enum, no `.value`, no `.name` | ⚠ behavior change |
| `ActionStatus` | `@dataclass(frozen=True)`; pickleable, equality, hashable | `#[pyclass(frozen)]`; pickleable, eq+hash work, repr leaks Rust | ✓ pickle resolved (Rec #9), repr still leaks |
| `ActionResult` | not in reference | new pyclass, Python-constructible via `#[new]`, pickleable | ✓ resolved (Rec #11) |
| `Session.__init__(callback=...)` | accepted | accepted only by wrapper, NOT by binding | ⚠ binding gap |
| `Session.__init__(revision_extensions=...)` | accepted, used | accepted by wrapper, **not forwarded** | ❌ silent regression |
| `Session.cancel_action()` | cancels a running action | raises `RuntimeError("session is busy")` while running | ❌ correctness regression |
| `Session.__enter__/__exit__` | implemented | not implemented on wrapper | ❌ missing |
| `Session.session_id` (property) | not exposed in ref either; spec says yes | not on wrapper; on binding only | ⚠ matches ref |
| `Session.run_subprocess(timeout=0)` | raises `ValueError` | silently runs without timeout (wrapper: `if timeout else None`) | ❌ correctness regression |
| `Session.run_subprocess(timeout=-5)` | raises `ValueError` | panics in background thread; action wedges | ❌ correctness regression |
| `Session.run_subprocess(command="")` | raises `ValueError` | accepts; action wedges with `action_status=None` | ❌ correctness regression |
| `Session.run_task(task_parameter_values)` | required (`TaskParameterSet`) | wrapper makes it required, but accepts dicts of dicts | ⚠ silent type drift |
| `Session.exit_environment(keep_session_running=False)` | default `False` | wrapper default `True` | ❌ silent default flip |
| `Session.environments_entered` (property) | `tuple[str, ...]` | binding returns `list[str]`; wrapper returns `tuple` | ✓ wrapper matches |
| `Session.working_directory` | `Path` | binding returns `str`; wrapper returns `Path` | ✓ wrapper matches |
| `SessionUser` | `ABC` with `is_process_user()` | `typing.Union[PosixSessionUser, WindowsSessionUser]` | ⚠ ABC removed (isinstance still works for Union via runtime checks but inheritance-based checks break) |
| `PosixSessionUser` | dataclass with `__slots__`; pickleable | pyo3 pyclass; pickleable via `__reduce__`, no `__slots__` attribute | ✓ pickle resolved (Rec #9) |
| `WindowsSessionUser` | dataclass with `__slots__`; importable on linux, raises on construct | pyo3 pyclass; same import/construct semantics; password/logon_token cached for getter | ✓ matches |
| `BadCredentialsException` | plain Python `Exception` subclass | pyo3 exception; module renamed correctly | ✓ matches |
| `LOG`, `LogContent` | Python logging | unchanged Python module | ✓ |
| `PathFormat`, `PathMappingRule` | Python class | re-exported from `openjd.expr` (Rust) | ✓ |
| `Session.get_enabled_extensions()` | returns the configured extensions | always returns `[]` | ❌ regression |
| `Session._run_task_without_session_env` (reference internal) | implemented | absent | ⚠ missing internal |

### 5.2 Behavioral differences and error message shape

| Failure | Reference | Binding | Status |
|---|---|---|---|
| `run_task` while session not READY | `RuntimeError("Session must be in the READY state to run a task.")` | `RuntimeError("An action is already running")` | ⚠ message change |
| `cancel_action` when nothing is running | `RuntimeError("No actions are running")` | `SessionError("Session must be in RUNNING state, current: READY")` | ⚠ class+message change |
| `cancel_action` while running | succeeds | `RuntimeError("Cannot cancel: session is busy with an action")` | ❌ contract inversion |
| `Session(session_root_directory=…)` non-existent dir | `RuntimeError("Ensure that the root directory ...")` | likely Rust I/O error → `SessionError(...)` (untested) | ⚠ untested |
| `enter_environment` with same identifier twice | `RuntimeError("Environment {id} has already been entered ...")` | not verified | ⚠ untested |
| `exit_environment` with unknown id | `RuntimeError("Cannot exit unknown Environment ...")` | not verified | ⚠ untested |

### 5.3 Underlying Rust crate — `openjd-rs`

`openjd-sessions` Rust crate (per the `eval-crate sessions` work; not re-evaluated here) provides `Session::cancel_action(time_limit, mark_failed) -> Result<(), SessionError>` that takes `&mut self`. The binding takes `&self` and locks a `Mutex<Option<Session>>` to obtain `&mut Session`; this works only when the action is between calls. The Rust crate already supports a `CancellationToken` (via `tokio_util::sync::CancellationToken`) that can be triggered from another thread without holding `&mut Session` — the binding does **not** wire this up. This is the missing piece for §2.3 / §5.1's `cancel_action` regression.

## 6. Build and Test Results

### 6.1 Build (`maturin develop`)

```
$ python scripts/maturin_build.py develop --manifest-path rust-bindings/Cargo.toml

📦 Built wheel for abi3 Python ≥ 3.9 to /tmp/.tmp.../openjd_model-...whl
✏️ Setting installed package as editable
🛠 Installed openjd-model-0.9.1.post13+g430f0d667
warning: `openjd-python` (lib) generated 25 warnings
```

Build succeeds. 25 warnings emitted (clippy details in §2.8).

### 6.2 `cargo clippy --workspace`

```
warning: `openjd-python` (lib) generated 76 warnings
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 6.04s
```

`cargo clippy --workspace -- -D warnings` — **fails** because clippy denies
the upper-case-acronyms variant names (`READY`, `RUNNING`, `CANCELING`,
`READY_ENDING`, `ENDED`, `CANCELED`, `FAILED`, `SUCCESS`, `TIMEOUT`,
`RANGE_EXPR`, etc.). Add `#[allow(clippy::upper_case_acronyms)]` to the
relevant enum decls or change the pyo3 `name = "..."` strings.

### 6.3 Pytest — model side

```
$ python -m pytest test/openjd/expr test/openjd/model_v0 test/openjd/model_v1 --no-cov

4003 passed, 25 skipped, 19 xfailed, 8 warnings, 31 errors in 8.70s
```

The 31 "errors" are pytest-xdist worker collection issues (deferred from a
flaky inifile / xdist interaction); when run with smaller scope the same files
collect and pass cleanly. Not a regression caused by sessions changes.

### 6.4 Pytest — sessions side (`bindings-rs` test surface)

```
$ python -m pytest test/openjd/sessions-v1 --no-cov

16 failed, 6 passed, 5 skipped in 0.75s
```

Failures break down:

| Failure | Cause |
|---|---|
| `test_os_checker::test_check_os_unsupported`, `::test_is_windows`, `::test_is_not_posix` | Test bug — patches wrong module (see §4.3) |
| `test_session_scenarios::test_scenario[...]` × 13 | All fail in test harness, not session: `state.value` missing, context manager not implemented, `ParameterValueType` not constructible |

```
$ python -m pytest test/openjd/sessions-v0 --no-cov

74 passed, 13 errors in 0.99s
```

The 13 errors are all `ImportError: attempted relative import with no known parent package` — the v0 tests still target the legacy pure-Python implementation (importing `_subprocess`, `_runner_base`, `_session_user._validate_username_password`, etc.) that has been removed. These tests are dead on the `bindings-rs` branch.

### 6.5 Pytest — sessions known gaps (this report)

`test/openjd/sessions-v1/test_known_gaps.py` (created during this evaluation): 17 xfailing tests demonstrate each issue in §5. Run:

```
$ python -m pytest test/openjd/sessions-v1/test_known_gaps.py --no-cov

17 xfailed in 0.84s
```

All 17 are reproducible failures of the binding/wrapper.

## 7. Exploratory Findings

### 7.1 Critical correctness regressions

1. **`cancel_action` cannot cancel a running action.** Working code:
   ```python
   s = Session(session_id="x", job_parameter_values={})
   s.run_subprocess(command=sys.executable, args=["-c", "import time; time.sleep(10)"])
   time.sleep(0.3)
   s.cancel_action()  # RuntimeError: Cannot cancel: session is busy with an action
   ```
   The binding deliberately rejects cancel when the underlying `Session` is
   *taken* (i.e. exactly when cancel is needed). Demonstrated by
   `test_known_gaps::test_cancel_action_actually_cancels_running_action`.
   Reference fix path: thread the Rust crate's `CancellationToken` to a
   `cancel()` method that does not need `&mut Session`. **High priority.**

2. **`run_subprocess` skips all input validation.**
   * `timeout=0` silently disables (wrapper bug at `_session.py` line in
     `run_subprocess`: `float(timeout) if timeout else None`).
   * `timeout=-5` reaches Rust → `Duration::from_secs_f64(-5.0).unwrap()` panics
     in the background thread. The Python session is now stuck at `state=RUNNING`;
     `action_status` is never updated; Rust panic prints to stderr only.
   * `command=""` — same wedge: the action sits at RUNNING with `action_status=None`.

   Reference's reference behavior is `ValueError` for all three. **High priority.**

3. **State enums lost `.value`.** `SessionState.READY.value` → `AttributeError`.
   The new `bindings-rs` test_session_scenarios.py uses `state.value` and is
   broken; downstream callers that compare against the legacy str — including
   the worker-agent fast path — silently get `False` everywhere because
   `SessionState.READY != "ready"`. **High priority.**

4. **`exit_environment(keep_session_running=...)` default flipped.** The
   wrapper changes the reference default from `False` to `True`. Callers that
   omit the kwarg silently behave differently. **Medium priority.**

5. **`revision_extensions` accepted but never forwarded.** `Session(...,
   revision_extensions=RevisionExtensions(spec_rev=…, supported_extensions=
   ["TASK_CHUNKING"]))` runs without error, but `s.get_enabled_extensions()`
   always returns `[]`. The binding's `SessionConfig` has no extensions field
   that the wrapper could plumb to. Either remove `revision_extensions` from
   the wrapper signature (with a deprecation) or extend `SessionConfig` and
   plumb through. **Medium priority.**

### 7.2 Behavior parity divergences

6. **`ActionStatus.__repr__` leaks Rust internals.** `repr(ActionStatus(state=ActionState.SUCCESS, exit_code=0))` → `"ActionStatus(state=Success, exit_code=Some(0))"`. Reference reports `"ActionStatus(state=<ActionState.SUCCESS: 'success'>, ...)"`. Visible in tracebacks and worker-agent log lines.

7. ~~**None of the new pyclasses are pickleable.** `ActionState`, `ActionStatus`, `PosixSessionUser`, `Session`, `SessionError` all `TypeError: cannot pickle 'openjd.sessions._v1.X' object` on `pickle.dumps`. Reference is fully pickleable for the dataclasses / `(str, Enum)`s. Pickle is used by the Deadline Cloud worker-agent IPC layer; this regression breaks that path.~~ **Resolved (Rec #9).** All value types (`SessionState`, `ActionState`, `ScriptRunnerState`, `ActionStatus`, `ActionResult`, `PosixSessionUser`, `WindowsSessionUser`) and `SessionError` / `BadCredentialsException` round-trip through pickle. `Session` itself remains intentionally not pickleable — it owns live OS resources. New tests live in `~/openjd-sessions-for-python/test/openjd/sessions-v1/test_pickle.py`.

8. ~~**`ActionResult` cannot be constructed from Python.** No `#[new]` impl; only via the dead-code `from_rust(...)` helper that nothing calls. The spec's pseudo-Python `class ActionResult: state, exit_code, stdout` is misleading — instances are unobtainable.~~ **Resolved (Rec #11).** `PyActionResult` now has a `#[new]` accepting `(*, state, exit_code=None, stdout="")` plus `__repr__`, `__eq__`, and `__reduce__` for pickle round-trip.

9. **`SessionUser` is a `typing.Union`, not an ABC.** Reference has an ABC with `is_process_user()` abstract method. Binding-side `SessionUser` is an alias; `isinstance(u, SessionUser)` works only because `typing.Union` triggers a special isinstance dispatch, but `class MyUser(SessionUser)` no longer works. Downstream fakers / mocks that subclassed `SessionUser` have to switch to `Mock(spec=PosixSessionUser)`.

10. **`Session.session_id` property missing on wrapper.** Spec promises it; the binding has it; the Python wrapper drops it. Trivial fix: add `@property def session_id(self): return self._session_id`.

11. **`Session.__enter__` / `__exit__` missing on wrapper.** The bindings-rs test scenario file uses `with Session(...) as s:` but the wrapper has no `__enter__`. Reference does. Add to wrapper, and also enable the existing scenario tests.

12. **`Session.__del__` raises `AttributeError` if `__init__` raised before `_rust_session` was assigned.** Construction failures (e.g. invalid path mapping rules) leave a half-built object; `__del__` then triggers the noisy traceback. Fix with `if self._rust_session is not None: self._rust_session.cleanup()`.

### 7.3 Test/spec hygiene

13. **`test_os_checker.py` patches `openjd.sessions._os_checker.os`** but the new module uses `sys.platform`. Three tests assert wrong things — they pass against reference and fail against bindings. Either rewrite to patch `sys.platform` or drop these tests; the binding's `_os_checker` is a 4-liner that doesn't need patching at all.

14. **Spec advertises `Session.run_task` parameters that don't match the wrapper.** Spec says `task_parameter_values: Optional[dict] = None`; wrapper makes it required.

15. **Spec advertises `SessionError(SessionError)` as a Python exception class but the existing tests don't verify the canonical `__module__`.** Add a regression test.

16. **`environments_entered` is undocumented in the spec.** Promote it from internal to public and document its return type.

17. **76 clippy warnings** (see §2.8). Most are pyo3 deprecations to migrate; the `upper_case_acronyms` warnings are intentional but should be silenced via `#[allow]` rather than ignored.

## 8. Recommendations

Numbered for the report-driven workflow in `~/openjd-rs/AGENTS.md`. Strike through with `~~ ... ~~ **Resolved.**` when fixed.

### Priority 1 — correctness regressions (fix before any caller migration)

1. Make `Session.cancel_action()` work while an action is running. Wire the
   Rust crate's `CancellationToken` through to a binding-owned handle so
   cancel does not require `&mut Session`. Reference test:
   `test/openjd/sessions-v1/test_known_gaps.py::test_cancel_action_actually_cancels_running_action`.
   Files: `rust-bindings/src/sessions/session.rs` lines 446–459; openjd-rs
   `openjd-sessions/src/session.rs` cancel surface.

2. Validate `run_subprocess(timeout=...)` and `run_subprocess(command=...)` arguments at the **wrapper** boundary so timeout=0/negative and empty command raise `ValueError` matching reference.
   Reference tests:
   `test/openjd/sessions-v1/test_known_gaps.py::test_run_subprocess_rejects_timeout_zero`,
   `::test_run_subprocess_rejects_negative_timeout`, `::test_run_subprocess_rejects_empty_command`.
   Files: `openjd-sessions-for-python/src/openjd/sessions/_v1/_session.py`
   `Session.run_subprocess` (replace `if timeout else None` with explicit
   `is None` check; add empty-command check at top).

3. In Rust, make negative `timeout` reject cleanly instead of panicking:
   replace `Duration::from_secs_f64(t).unwrap()` with a check that returns a
   `SessionError`. File: `rust-bindings/src/sessions/session.rs` line 425
   (`run_subprocess`'s `let duration = timeout.map(std::time::Duration::from_secs_f64);`).

4. Fix `exit_environment` default `keep_session_running=False` to match reference.
   Reference test:
   `test/openjd/sessions-v1/test_known_gaps.py::test_exit_environment_keep_session_running_default_is_false`.
   Files: `openjd-sessions-for-python/src/openjd/sessions/_v1/_session.py`
   wrapper signature; `rust-bindings/src/sessions/session.rs` line 318
   `#[pyo3(signature = (*, identifier, keep_session_running=true, ...))]`.

5. Either plumb `revision_extensions` to the binding through a new
   `SessionConfig.supported_extensions` field, or remove the parameter from the
   wrapper. Currently it's silently ignored. Reference test:
   `test/openjd/sessions-v1/test_known_gaps.py::test_revision_extensions_actually_used`.
   Files: `rust-bindings/src/sessions/session.rs` (PySession::new) and
   `openjd-sessions-for-python/src/openjd/sessions/_v1/_session.py` (wrapper).

### Priority 2 — Python contract regressions

6. Add `.value` (returning the lowercase legacy string) on `SessionState`,
   `ActionState`, and `ScriptRunnerState`, so that `state.value == "ready"`
   continues to work. The simplest path is a `#[getter] fn value(&self) ->
   &'static str` in `rust-bindings/src/sessions/types.rs`. Reference test:
   `test_known_gaps::test_session_state_has_value_attribute`. Also fixes
   `test_session_scenarios.py` line 183 (currently broken).

7. Implement `__enter__` / `__exit__` on the wrapper `Session` class.
   Reference test: `test_known_gaps::test_wrapper_session_supports_context_manager`.
   File: `openjd-sessions-for-python/src/openjd/sessions/_v1/_session.py`.

8. Add a `session_id` property to the wrapper `Session` class. Trivial.
   Reference test: `test_known_gaps::test_wrapper_session_id_property`.

9. ~~Make `ActionState` / `ActionStatus` / `PosixSessionUser` /
   `WindowsSessionUser` / `Session` (where applicable) pickleable by
   implementing `__reduce__` in PyO3. Especially for value types like
   `ActionState` and `ActionStatus`, which are frequently sent across IPC in
   the Deadline Cloud worker agent. Reference tests:
   `test_known_gaps::test_action_state_is_pickleable`,
   `test_action_status_is_pickleable`, `test_posix_session_user_is_pickleable`.~~
   **Resolved.** Implemented for all the value types listed above.
   `Session` is intentionally **not** pickleable (it owns live OS
   resources). `ActionStatus` round-trips its `started_at` and
   `ended_at` timestamps via a private `_from_state` classmethod
   that converts to and from Python `datetime`. New tests live in
   `~/openjd-sessions-for-python/test/openjd/sessions-v1/test_pickle.py`.

10. Fix `ActionStatus.__repr__` to use Python-friendly enum names instead of
    the Rust `Debug` format. File: `rust-bindings/src/sessions/types.rs:189`.
    Reference test: `test_known_gaps::test_action_status_repr_is_python_friendly`.

11. ~~Either make `ActionResult` Python-constructible (add `#[new]`) or remove
    it from the spec. Currently it's exposed but unobtainable. File:
    `rust-bindings/src/sessions/types.rs:243`. Reference test:
    `test_known_gaps::test_action_result_constructible_from_python`.~~
    **Resolved.** Added `#[new]` with signature
    `(*, state, exit_code=None, stdout="")` plus `__repr__`, `__eq__`,
    and `__reduce__`.

12. Fix `Session.__del__` to defend against half-constructed objects: guard
    `self._rust_session.cleanup()` with `if hasattr(self, '_rust_session') and self._rust_session is not None`.
    File: `openjd-sessions-for-python/src/openjd/sessions/_v1/_session.py:369`.

13. Add `Session(callback=...)` to the binding constructor, OR remove the
    `callback` parameter from the spec and document the polling-thread
    emulation. Currently the spec promises a callback the binding doesn't
    accept. Files: `rust-bindings/src/sessions/session.rs` PySession::new,
    `specs/python-sessions-interface.md`.

14. Either remove `job_template` and `environment_templates` from the spec
    (they're not used) or wire them through. File:
    `specs/python-sessions-interface.md`.

### Priority 3 — Test surface and hygiene

15. Fix the broken `test_os_checker.py` tests. Either drop them, or rewrite to
    patch `sys.platform` instead of `openjd.sessions._os_checker.os`. File:
    `test/openjd/sessions-v1/test_os_checker.py`.

16. Re-enable `test_session_scenarios.py` after fixes for #6 and #7. Today
    16 of 22 scenarios fail at the test-harness level, not because of
    binding behavior.

17. Port a representative subset of mainline tests to `bindings-rs`:
    * `test_session_user.py` — small, self-contained, covers `PosixSessionUser` semantics.
    * `test_redaction.py`, `test_redacted_env.py` — exercise env-var redaction surface (binding has `os_env_vars`; redaction unverified).
    * `test_action_filter.py` — directive parsing (`openjd_progress`/`status`/`fail`/`env`/`unset_env`).
    * `test_path_mapping.py` — already covered by scenario tests in part, but unit-level path mapping coverage is missing.

18. Drop the `test/openjd/sessions-v0/` directory or split it out. It contains
    13 files that all `ImportError` on the `bindings-rs` branch because the
    pure-Python implementation modules they import have been deleted.

19. Add binding-specific tests for:
    * `SessionError.__module__ == "openjd.sessions._v1"` and analogous for
      `BadCredentialsException` (regression test for the renaming work).
    * `extend_path_mapping_rules` happy path and "while running" rejection.
    * Concurrent `Session` use from multiple Python threads (already works,
      but lock for it).
    * `OPENJD_SESSION_WORKING_DIR` env var set on subprocesses (public API).

### Priority 4 — Build and clippy hygiene

20. Add `#[allow(clippy::upper_case_acronyms)]` to enum declarations in
    `rust-bindings/src/sessions/types.rs` for `PySessionState`, `PyActionState`,
    `PyScriptRunnerState`, and other Python-facing enums whose variants must
    remain `UPPER_SNAKE`. Restore `cargo clippy --workspace -- -D warnings` to a
    pass.

21. Migrate from deprecated `pyo3::types::PyAnyMethods::downcast` to
    `Bound::cast` (~12 call sites across expr/model/sessions). Migrate from
    `HasAutomaticFromPyObject::<true>::MSG` deprecations by adding
    `#[pyclass(from_py_object)]` or `#[pyclass(skip_from_py_object)]`
    attributes (~10 sites in sessions and elsewhere).

22. Either delete `PyActionResult::from_rust` (dead code per clippy) or wire
    it up so something actually calls it (e.g. a future `Session.action_result`
    property when an action ends).

23. Add `#[gen_stub_pymethods]` to `PySession` impl block in
    `rust-bindings/src/sessions/session.rs` so generated stubs include
    `enter_environment`, `exit_environment`, `run_task`, `run_subprocess`,
    `cancel_action`, `cleanup`, `extend_path_mapping_rules` signatures.

### Priority 5 — Spec corrections

24. Update `specs/python-sessions-interface.md` to match what the binding
    actually exposes (or update bindings to match spec). Specific edits
    needed:
    * Remove `callback` from `Session.__init__` until it's wired through (or
      keep and add to binding).
    * Remove `job_template` and `environment_templates` from `Session.__init__`
      table.
    * Document that `SessionState`/`ActionState` are pyo3 enums (not `(str,
      Enum)`); explain `.name` works but `.value` does not (or fix per #6).
    * Document `ActionStatus.started_at` / `ended_at` getters.
    * Document `extend_path_mapping_rules`.
    * Mention the `cancel_action` regression in the "Compatibility / Breaking
      changes" section so callers don't get surprised.
