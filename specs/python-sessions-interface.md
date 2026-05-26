# Python Sessions Interface — Rust Bindings Plan

Replace the Python `openjd-sessions-for-python` implementation with bindings
to the Rust `openjd-sessions` crate, exposed through the existing
`openjd._openjd_rs` native extension in `openjd-model-for-python`.

## Architecture

```
openjd-model-for-python (Rust extension)
  └── openjd._openjd_rs          ← single .so, already ships expr + model
        ├── expr bindings         ← done
        ├── model bindings        ← done
        └── sessions bindings     ← new: wraps openjd-sessions crate

openjd-sessions-for-python (Python)
  └── openjd.sessions
        └── imports from openjd._openjd_rs (via openjd.model / openjd.expr)
```

Sessions is a dependency of model, so it can import from `openjd._openjd_rs`.
The Rust sessions crate depends on `openjd-expr` and `openjd-model`, which
are already linked into the extension.

## Rust Sessions Crate API

The `openjd-sessions` crate provides:

| Rust type | Description |
|---|---|
| `Session` | Core state machine: enter/exit environments, run tasks, cancel, cleanup |
| `SessionConfig` | Configuration for creating a session |
| `SessionState` | Enum: Ready, Running, Canceling, ReadyEnding, Ended |
| `ActionState` | Enum: Running, Success, Failed, Canceled, Timeout |
| `ActionStatus` | Progress/status/fail message/exit code for current action |
| `ActionResult` | Final result of an action (state, exit code, stdout, stderr) |
| `ActionMessage` | Parsed openjd stdout messages (progress, env, status, fail) |
| `SessionError` | Error enum for all session operations |
| `ScriptRunnerState` | Enum: Ready, Running, Canceling, Canceled, Timeout, Failed, Success |
| `CancelMethod` | Enum: Terminate, NotifyThenTerminate |
| `EmbeddedFiles` | File materialization with scope (Step/Env) |
| `SessionUser` trait | Cross-user execution (PosixSessionUser, WindowsSessionUser) |
| `SubprocessResult` | Exit state + code + stdout from a subprocess |

Key methods on `Session`:
- `with_config(SessionConfig)` — constructor
- `enter_environment(env, resolved_symtab, identifier, os_env_vars)` — async
- `exit_environment(identifier, resolved_symtab, keep_running, os_env_vars)` — async
- `run_task(script, task_params, resolved_symtab, os_env_vars)` — async
- `run_subprocess(command, args, timeout, os_env_vars, ...)` — async
- `cancel_action(time_limit, mark_failed)`
- `cleanup()`
- `build_symbol_table(task_params, base)` — symbol table construction
- `evaluate_env_vars(extra)` — cumulative env var evaluation
- Properties: `session_id`, `state`, `working_directory`, `files_directory`, `action_status`

## Python Interface

### Enums (from Rust)

```python
class SessionState:
    READY = ...
    RUNNING = ...
    CANCELING = ...
    READY_ENDING = ...
    ENDED = ...

class ActionState:
    RUNNING = ...
    SUCCESS = ...
    FAILED = ...
    CANCELED = ...
    TIMEOUT = ...
```

### Types (from Rust)

```python
class ActionStatus:
    state: ActionState
    progress: Optional[float]
    status_message: Optional[str]
    fail_message: Optional[str]
    exit_code: Optional[int]

class ActionResult:
    state: ActionState
    exit_code: Optional[int]
    stdout: str
```

### Session class (wraps Rust Session)

```python
class Session:
    def __init__(
        self,
        *,
        session_id: str,
        job_parameter_values: dict[str, ParameterValue],
        path_mapping_rules: Optional[list[PathMappingRule]] = None,
        callback: Optional[Callable] = None,
        os_env_vars: Optional[dict[str, str]] = None,
        retain_working_dir: bool = False,
        session_root_directory: Optional[Path] = None,
        user: Optional[SessionUser] = None,
        job_template: Optional[JobTemplate] = None,
        environment_templates: Optional[list[EnvironmentTemplate]] = None,
    ): ...

    # Properties
    session_id: str
    state: SessionState
    working_directory: Path
    files_directory: Path
    action_status: Optional[ActionStatus]

    # Environment lifecycle (non-blocking — starts action, returns immediately)
    def enter_environment(
        self,
        *,
        environment: Environment,
        identifier: Optional[str] = None,
        os_env_vars: Optional[dict[str, str]] = None,
    ) -> str: ...

    def exit_environment(
        self,
        *,
        identifier: str,
        os_env_vars: Optional[dict[str, str]] = None,
    ) -> None: ...

    # Task execution (non-blocking — starts action, returns immediately)
    def run_task(
        self,
        *,
        step_script: StepScript,
        task_parameter_values: Optional[dict] = None,
        os_env_vars: Optional[dict[str, str]] = None,
    ) -> None: ...

    # Subprocess execution (non-blocking)
    def run_subprocess(
        self,
        *,
        command: str,
        args: Optional[list[str]] = None,
        timeout: Optional[float] = None,
        os_env_vars: Optional[dict[str, str]] = None,
        use_session_env_vars: bool = True,
        log_banner_message: Optional[str] = None,
    ) -> None: ...

    # Control
    def cancel_action(
        self,
        *,
        time_limit: Optional[float] = None,
        mark_action_failed: bool = False,
    ) -> None: ...

    def cleanup(self) -> None: ...
```

### SessionUser (stays in Python, passed to Rust)

The `SessionUser` types involve OS-specific credential validation (sudo
checks, Windows logon tokens) that are better kept in Python for now.
The Rust `SessionUser` trait accepts user/group strings — the Python side
validates credentials and passes the identity through.

```python
class PosixSessionUser:
    user: str
    group: str

class WindowsSessionUser:
    user: str
    password: Optional[str]
```

### Callback interface

The Python callback `Callable[[str, ActionStatus], None]` is invoked from
Rust via PyO3 when action status changes. The Rust `drive_action` loop
sends `ActionMessage` values through a channel; the binding converts them
to `ActionStatus` and calls the Python callback on the main thread.

## Async Strategy

The Rust sessions crate uses `tokio` async for subprocess I/O. The Python
sessions API is **non-blocking**: `run_task()`, `enter_environment()`, and
`exit_environment()` start a subprocess in a background thread and return
immediately. The caller polls `session.action_status` or receives a callback
when the action completes.

Options:

1. **Spawn tokio task, return immediately** — Match the Python API. Each
   `run_task`/`enter_environment` call spawns a tokio task on a background
   runtime. The Python method returns immediately. The callback fires from
   the tokio runtime when the action completes. The caller polls
   `action_status` or waits for the callback.

2. **Block until complete** — Change the Python API to block. Would break
   existing callers (worker agent, CLI) that rely on non-blocking behavior.

**Decision: Option 1 (non-blocking, matching current Python API).** We
maintain a single `tokio::Runtime` on the `PySession` object. Each action
method spawns a task on that runtime and returns immediately. The runtime
thread drives subprocess I/O and calls the Python callback (acquiring the
GIL) when the action finishes or status changes.

```rust
#[pymethods]
impl PySession {
    fn run_task(&mut self, ...) -> PyResult<()> {
        // Spawn on the session's tokio runtime — returns immediately
        let handle = self.runtime.spawn(async move {
            session.run_task(script, task_params, ...).await
        });
        self.action_handle = Some(handle);
        Ok(())
    }

    #[getter]
    fn action_status(&self) -> Option<PyActionStatus> {
        // Read current status from shared state
    }
}
```

The GIL is released during subprocess execution since the tokio runtime
runs on its own thread.

## Incremental Build Plan

### Phase 1: Enums, errors, and simple types

Add to `rust-bindings/src/sessions/` in the model-for-python extension:

- `SessionState` enum
- `ActionState` enum (replaces Python `ActionState(str, Enum)`)
- `ActionStatus` class
- `ActionResult` class
- `SessionError` → Python exception
- `ScriptRunnerState` enum

Wire into `lib.rs` module registration. Update `openjd.sessions._types`
to import from `openjd._openjd_rs` instead of defining locally.

**Test:** Import enums, check values match Python originals.

### Phase 2: Session construction and properties

- `Session.__init__` wrapping `Session::with_config`
- Properties: `session_id`, `state`, `working_directory`, `files_directory`
- `cleanup()` method
- `action_status` property
- `cancel_action()` method

**Test:** Create session, check properties, cleanup.

### Phase 3: Environment lifecycle

- `enter_environment()` — wraps async `Session::enter_environment`
- `exit_environment()` — wraps async `Session::exit_environment`
- Callback plumbing (ActionMessage → ActionStatus → Python callback)
- Env var tracking (openjd_env, openjd_unset_env)

**Test:** Enter/exit environment with onEnter/onExit scripts, verify
env vars are set/unset, callback fires.

### Phase 4: Task execution

- `run_task()` — wraps async `Session::run_task`
- Symbol table construction with path mapping
- Embedded file materialization
- Let binding evaluation
- Action filter (openjd_progress, openjd_status, openjd_fail)

**Test:** Run tasks with parameters, embedded files, let bindings.
Verify action status, progress, stdout capture.

### Phase 5: Subprocess and advanced features

- `run_subprocess()` — for worker agent install/sync operations
- Cancelation with time limits
- Cross-user execution (PosixSessionUser passthrough)
- Redacted environment variables
- `evaluate_env_vars()` for external consumers

**Test:** Run subprocess, cancel mid-execution, cross-user scenarios.

### Phase 6: Python sessions cleanup

- Remove Python runner classes (`_runner_base.py`, `_runner_step_script.py`,
  `_runner_env_script.py`)
- Remove Python embedded files (`_embedded_files.py`)
- Remove Python action filter (`_action_filter.py`)
- Simplify `_session.py` to thin wrapper over Rust `Session`
- Remove subprocess management (`_subprocess.py`)
- Keep `_session_user.py` (credential validation stays in Python)
- Keep `_logging.py` (Python logging integration)

## Dependencies

```toml
# rust-bindings/Cargo.toml additions
openjd-sessions = { git = "...", branch = "prototype" }
tokio = { version = "1", features = ["rt", "process", "io-util", "sync", "time"] }
uuid = { version = "1", features = ["v4"] }
```

## Logging

The Rust sessions crate uses the `log` crate. We bridge to Python logging:

- Set up a `log` → Python `logging` bridge in the PyO3 module init
- The Rust `session_log!` macro tags messages with session_id and LogContent
- The Python side receives structured log records matching the current format

This preserves the existing log output that the worker agent and CLI parse.

## Compatibility

The Python `Session` class signature stays the same. Callers (worker agent,
CLI `openjd run`) don't need changes. Internal implementation moves from
Python subprocess management to Rust async subprocess management.

Breaking changes:
- `ActionState` becomes a Rust enum (not `str, Enum`) — string comparison
  like `state == "running"` breaks, must use `state == ActionState.RUNNING`
- Internal types (`ScriptRunnerState`, `ActionMonitoringFilter`) are no
  longer importable from sessions submodules

## Pickle Support

Pickle is used by the Deadline Cloud worker-agent IPC layer, so all
value types that flow across that boundary are pickleable. The
``Session`` class itself is not — it owns live OS resources (subprocess,
working directory, file handles) that are not meaningful to serialize.

| Type | Reduces through |
|---|---|
| ``SessionState`` | variant name (``READY``, ``RUNNING``, ``ENDED``, …) |
| ``ActionState`` | variant name (``RUNNING``, ``SUCCESS``, ``FAILED``, …) |
| ``ScriptRunnerState`` | variant name |
| ``ActionStatus`` | private ``_from_state`` classmethod that round-trips ``state``, ``progress``, ``status_message``, ``fail_message``, ``exit_code``, ``started_at``, ``ended_at`` |
| ``ActionResult`` | constructor arguments (``state``, ``exit_code``, ``stdout``) |
| ``PosixSessionUser`` | constructor arguments (``user``, ``group``) |
| ``WindowsSessionUser`` | constructor arguments (``user``, ``password``, ``logon_token``) — see caveats below |
| ``SessionError``, ``BadCredentialsException`` | standard exception pickle, under their canonical ``openjd.sessions._v1`` module path |

``WindowsSessionUser`` pickle caveats:

1. The password is stored plaintext in the pickle output. Avoid pickling
   ``WindowsSessionUser`` to disk or over an untrusted channel. This
   matches the legacy Python ``dataclass`` which also stored ``password``
   as a plain field.
2. ``logon_token`` is a process-local Win32 ``HANDLE``. The integer
   value pickles correctly but does not refer to a valid handle in
   another process; unpickling on a different process will fail at
   ``LogonUser`` validation.
3. Unpickling on a non-Windows host raises ``RuntimeError``, matching
   the construction-time behavior.

``Session`` is intentionally not pickleable — pickling a live session
object would silently produce a stub that cannot run anything. Take a
checkpoint of the inputs (``Session.__init__`` arguments and current
``ActionStatus``) instead.
