# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""A call the openjd-sessions crate refuses raises, as the Rust method returns ``Err``.

The crate refuses a call before it changes anything: the session state, the
last action's status and the environments entered stay as they were. Each test
drives a sequence through the binding and checks the crate's documented result:
the exception class, its message (the crate's ``SessionError`` text), the state,
and that ``action_status`` still describes the previous action.

Before, the binding handed every call to a background thread and discarded the
crate's ``Result``, so a refused call returned as if an action had started, ran
nothing, and left the previous action's status showing. openjd-sessions 0.10.0
(openjd-rs#524) made that common: a failed action keeps the session ending-only
even after a successful ``exit_environment(keep_session_running=True)``.

``clear_ending_only`` is the crate's way out of ending-only (openjd-rs#524).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Callable, Optional

import pytest

from openjd import _openjd_rs
from openjd._openjd_rs import (
    ActionState,
    ActionStatus,
    Session,
    SessionState,
    create_environment,
    decode_environment_template,
    deserialize_step,
)

# Registered at runtime by `register_renamed_exception`; the type stub doesn't
# declare the exception classes.
SessionError: type[Exception] = getattr(_openjd_rs, "SessionError")


def _python(code: str) -> dict[str, Any]:
    return {"command": sys.executable, "args": ["-c", code]}


def _step_script(code: str) -> Any:
    return deserialize_step({"name": "S", "script": {"actions": {"onRun": _python(code)}}}).script


def _environment(name: str = "E", *, extensions: Optional[list[str]] = None, **actions: Any) -> Any:
    template: dict[str, Any] = {
        "specificationVersion": "environment-2023-09",
        "environment": {"name": name, "script": {"actions": actions}},
    }
    if extensions:
        template["extensions"] = extensions
    return create_environment(
        decode_environment_template(template=template, supported_extensions=extensions)
    )


def _settle(session: Session) -> None:
    deadline = time.monotonic() + 10
    busy = (SessionState.RUNNING, SessionState.CANCELING)
    while session.state in busy and time.monotonic() < deadline:
        time.sleep(0.02)
    assert session.state not in busy, "action did not finish within 10s"


def _status(session: Session) -> Optional[tuple]:
    status: Optional[ActionStatus] = session.action_status
    if status is None:
        return None
    return (status.state, status.exit_code, status.fail_message, status.status_message)


@pytest.fixture
def session(tmp_path: Path):
    s = Session(session_id="s", job_parameter_values={}, session_root_directory=str(tmp_path))
    try:
        yield s
    finally:
        s.cleanup()


def _assert_refused(
    session: Session,
    call: Callable[[], object],
    message: str,
    error: type[Exception] = SessionError,
) -> None:
    """``call`` raises ``error(message)`` and changes nothing."""
    state = session.state
    status = _status(session)
    entered = session.environments_entered
    with pytest.raises(error) as exc_info:
        call()
    assert str(exc_info.value) == message
    assert session.state == state
    assert _status(session) == status
    assert session.environments_entered == entered


def _make_ending_only(session: Session) -> str:
    """Enter an environment, fail a task in it, and exit it with
    ``keep_session_running=True``. Returns the identifier of a second, outer
    environment that is still entered."""
    outer = session.enter_environment(environment=_environment("Outer", onEnter=_python("")))
    _settle(session)
    inner = session.enter_environment(environment=_environment("Inner", onEnter=_python("")))
    _settle(session)
    session.run_task(step_script=_step_script("raise SystemExit(1)"))
    _settle(session)
    session.exit_environment(identifier=inner, keep_session_running=True)
    _settle(session)
    status = session.action_status
    assert status is not None and status.state == ActionState.SUCCESS
    assert session.state == SessionState.READY_ENDING
    return outer


class TestOnAnEndingOnlySession:
    """openjd-rs#524: an ending-only session accepts only ``exit_environment``
    and ``cleanup``. The others raise ``InvalidState``."""

    _MESSAGE = "Session must be in READY state, current: READY_ENDING"

    def test_run_task(self, session: Session, tmp_path: Path) -> None:
        marker = tmp_path / "ran"
        _make_ending_only(session)
        _assert_refused(
            session,
            lambda: session.run_task(
                step_script=_step_script(f"open({str(marker)!r}, 'w').close()")
            ),
            self._MESSAGE,
        )
        time.sleep(0.2)
        assert not marker.exists()

    def test_enter_environment(self, session: Session) -> None:
        _make_ending_only(session)
        _assert_refused(
            session,
            lambda: session.enter_environment(environment=_environment(onEnter=_python(""))),
            self._MESSAGE,
        )

    def test_run_subprocess(self, session: Session) -> None:
        _make_ending_only(session)
        _assert_refused(
            session,
            lambda: session.run_subprocess(command=sys.executable, args=["-c", ""]),
            self._MESSAGE,
        )

    def test_exit_environment_is_still_accepted(self, session: Session) -> None:
        outer = _make_ending_only(session)
        session.exit_environment(identifier=outer)
        _settle(session)
        status = session.action_status
        assert status is not None and status.state == ActionState.SUCCESS
        assert session.environments_entered == []
        assert session.state == SessionState.READY_ENDING


class TestClearEndingOnly:
    def test_returns_the_session_to_ready(self, session: Session) -> None:
        """The last action's status and the environments entered stay as
        they were, and the session accepts new actions again."""
        outer = _make_ending_only(session)
        status = _status(session)
        session.clear_ending_only()
        assert session.state == SessionState.READY
        assert _status(session) == status
        assert session.environments_entered == [outer]
        session.run_task(step_script=_step_script(""))
        _settle(session)
        new_status = session.action_status
        assert new_status is not None and new_status.state == ActionState.SUCCESS
        assert session.state == SessionState.READY

    def test_a_failed_action_makes_it_ending_only_again(self, session: Session) -> None:
        _make_ending_only(session)
        session.clear_ending_only()
        session.run_task(step_script=_step_script("raise SystemExit(1)"))
        _settle(session)
        assert session.state == SessionState.READY_ENDING

    def test_refused_when_the_session_is_ready(self, session: Session) -> None:
        _assert_refused(
            session,
            session.clear_ending_only,
            "Session must be in READY_ENDING state, current: READY",
        )

    def test_refused_while_an_action_runs(self, session: Session) -> None:
        session.run_task(step_script=_step_script("import time; time.sleep(30)"))
        try:
            assert session.state == SessionState.RUNNING
            _assert_refused(
                session,
                session.clear_ending_only,
                "Session must be in READY_ENDING state, current: RUNNING",
            )
        finally:
            session.cancel_action()
            _settle(session)


class TestWhileAnActionRuns:
    """The crate refuses every action while one is running. Before, the
    binding raised ``RuntimeError("An action is already running")``; it now
    gives the crate's ``InvalidState`` message. ``SessionError`` is a
    ``RuntimeError``, so a caller catching ``RuntimeError`` still does."""

    @pytest.mark.parametrize(
        "call, message",
        [
            pytest.param(
                lambda s: s.run_task(step_script=_step_script("")),
                "Session must be in READY state, current: RUNNING",
                id="run_task",
            ),
            pytest.param(
                lambda s: s.enter_environment(environment=_environment(onEnter=_python(""))),
                "Session must be in READY state, current: RUNNING",
                id="enter_environment",
            ),
            pytest.param(
                lambda s: s.exit_environment(identifier="E"),
                "Session must be in READY or READY_ENDING state, current: RUNNING",
                id="exit_environment",
            ),
            pytest.param(
                lambda s: s.run_subprocess(command=sys.executable, args=["-c", ""]),
                "Session must be in READY state, current: RUNNING",
                id="run_subprocess",
            ),
        ],
    )
    def test_a_second_action(
        self, session: Session, call: Callable[[Session], object], message: str
    ) -> None:
        session.run_task(step_script=_step_script("import time; time.sleep(30)"))
        try:
            assert session.state == SessionState.RUNNING
            assert issubclass(SessionError, RuntimeError)
            _assert_refused(session, lambda: call(session), message)
        finally:
            session.cancel_action()
            _settle(session)


class TestOtherRefusals:
    def test_exit_an_unknown_environment(self, session: Session) -> None:
        _assert_refused(
            session,
            lambda: session.exit_environment(identifier="nope"),
            "Unknown environment identifier: nope",
        )

    def test_exit_out_of_order(self, session: Session) -> None:
        first = session.enter_environment(environment=_environment("A", onEnter=_python("")))
        _settle(session)
        second = session.enter_environment(environment=_environment("B", onEnter=_python("")))
        _settle(session)
        _assert_refused(
            session,
            lambda: session.exit_environment(identifier=first),
            f"Must exit the most recently entered environment first. Expected {second}, got {first}",
        )

    def test_enter_a_duplicate_identifier(self, session: Session) -> None:
        session.enter_environment(environment=_environment(onEnter=_python("")), identifier="A")
        _settle(session)
        _assert_refused(
            session,
            lambda: session.enter_environment(
                environment=_environment(onEnter=_python("")), identifier="A"
            ),
            "Environment A has already been entered in this Session.",
        )

    def test_enter_a_second_wrap_environment(self, session: Session) -> None:
        def wrap_environment(name: str) -> Any:
            hooks = ("onWrapEnvEnter", "onWrapTaskRun", "onWrapEnvExit")
            return _environment(
                name, extensions=["EXPR", "WRAP_ACTIONS"], **{h: _python("") for h in hooks}
            )

        session.enter_environment(environment=wrap_environment("W1"))
        _settle(session)
        _assert_refused(
            session,
            lambda: session.enter_environment(environment=wrap_environment("W2")),
            "RFC 0008: a session may have at most one Environment defining wrap hooks "
            "(onWrapEnvEnter / onWrapTaskRun / onWrapEnvExit). Environment 'W1' already "
            "defines wrap hooks; cannot also enter 'W2'.",
        )

    @pytest.mark.parametrize(
        "kwargs, message",
        [
            pytest.param({"command": "  "}, "command must be a non-empty string", id="blank"),
            pytest.param(
                {"command": sys.executable, "timeout": 0.0},
                "timeout must be positive",
                id="zero timeout",
            ),
        ],
    )
    def test_run_subprocess_arguments(
        self, session: Session, kwargs: dict[str, Any], message: str
    ) -> None:
        _assert_refused(session, lambda: session.run_subprocess(**kwargs), message)

    @pytest.mark.parametrize(
        "timeout, shown", [(-1.0, "-1"), (float("nan"), "NaN"), (float("inf"), "inf")]
    )
    def test_run_subprocess_timeout_with_no_duration(
        self, session: Session, timeout: float, shown: str
    ) -> None:
        """A timeout with no ``Duration`` raises ``ValueError`` before the
        crate sees it. Before, the binding's conversion panicked
        (``PanicException``, which ``except Exception`` doesn't catch)."""
        _assert_refused(
            session,
            lambda: session.run_subprocess(command=sys.executable, timeout=timeout),
            f"timeout must be a finite, non-negative number of seconds, got {shown}",
            ValueError,
        )


_SLEEP = "import time; time.sleep(30)"


class TestCancelAction:
    def test_with_no_action_running(self, session: Session) -> None:
        """The crate's ``InvalidState``, whether or not an action has run."""
        message = "Session must be in RUNNING state, current: READY"
        _assert_refused(session, session.cancel_action, message)
        session.run_task(step_script=_step_script(""))
        _settle(session)
        _assert_refused(session, session.cancel_action, message)

    def test_a_second_cancel_while_canceling(self, session: Session, tmp_path: Path) -> None:
        """The crate refuses a cancel while one is in progress. Before, the
        binding delivered it through the cancel handle and returned, ignoring
        its time limit."""
        marker = tmp_path / "started"
        ignore_notify = (
            "import signal, time\n"
            "for name in ('SIGTERM', 'SIGBREAK'):\n"
            "    if hasattr(signal, name):\n"
            "        signal.signal(getattr(signal, name), signal.SIG_IGN)\n"
            f"open({str(marker)!r}, 'w').close()\n"
            "time.sleep(30)"
        )
        script = deserialize_step(
            {
                "name": "S",
                "script": {
                    "actions": {
                        "onRun": {
                            **_python(ignore_notify),
                            "cancelation": {
                                "mode": "NOTIFY_THEN_TERMINATE",
                                "notifyPeriodInSeconds": 3,
                            },
                        }
                    }
                },
            }
        ).script
        session.run_task(step_script=script)
        deadline = time.monotonic() + 10
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert marker.exists()
        session.cancel_action()
        assert session.state == SessionState.CANCELING
        _assert_refused(
            session,
            lambda: session.cancel_action(time_limit=0.0),
            "Session must be in RUNNING state, current: CANCELING",
        )
        _settle(session)
        status = session.action_status
        assert status is not None and status.state == ActionState.CANCELED

    def test_a_time_limit_with_no_duration(self, session: Session) -> None:
        _assert_refused(
            session,
            lambda: session.cancel_action(time_limit=-1.0),
            "time_limit must be a finite, non-negative number of seconds, got -1",
            ValueError,
        )

    @pytest.mark.parametrize(
        "start",
        [
            pytest.param(lambda s: s.run_task(step_script=_step_script(_SLEEP)), id="run_task"),
            pytest.param(
                lambda s: s.run_subprocess(command=sys.executable, args=["-c", _SLEEP]),
                id="run_subprocess",
            ),
            pytest.param(
                lambda s: s.enter_environment(environment=_environment(onEnter=_python(_SLEEP))),
                id="enter_environment",
            ),
        ],
    )
    def test_straight_after_the_call_that_started_the_action(
        self, session: Session, start: Callable[[Session], object]
    ) -> None:
        """The crate reports an action ``Running`` just before it installs
        its cancel token. A cancel made as soon as the call returns still
        reaches the action; before, it nearly always raised "Cannot cancel:
        no action is running" and the action ran to the end."""
        for _ in range(5):
            start(session)
            began = time.monotonic()
            session.cancel_action()
            _settle(session)
            assert time.monotonic() - began < 4
            status = session.action_status
            assert status is not None and status.state == ActionState.CANCELED
            assert session.state == SessionState.READY_ENDING
            session.clear_ending_only()


class TestAcceptedCalls:
    """An accepted call returns once its action is running, with
    ``action_status`` describing the new action, not the previous one."""

    def test_run_task_reports_the_new_action(self, session: Session) -> None:
        session.run_task(step_script=_step_script("raise SystemExit(1)"))
        _settle(session)
        session.clear_ending_only()
        session.run_task(step_script=_step_script("import time; time.sleep(0.5)"))
        status = session.action_status
        assert status is not None
        assert status.state == ActionState.RUNNING
        assert session.state == SessionState.RUNNING
        _settle(session)
        status = session.action_status
        assert status is not None and status.state == ActionState.SUCCESS

    def test_an_environment_with_no_script_has_ended_on_return(self, session: Session) -> None:
        """Nothing runs, so the action has ended by the time the call
        returns, and the session is back in its slot for the next call."""
        environment = create_environment(
            decode_environment_template(
                template={
                    "specificationVersion": "environment-2023-09",
                    "environment": {"name": "E", "variables": {"X": "1"}},
                }
            )
        )
        identifier = session.enter_environment(environment=environment)
        status = session.action_status
        assert status is not None and status.state == ActionState.SUCCESS
        assert session.state == SessionState.READY
        session.exit_environment(identifier=identifier)
        assert session.environments_entered == []


_CONCURRENT_CLEANUP = r"""
import logging, os, sys, threading
logging.basicConfig(level=logging.INFO, stream=open(os.devnull, "w"))
from openjd import _openjd_rs
from openjd._openjd_rs import Session
SessionError = getattr(_openjd_rs, "SessionError")
for i in range(50):
    s = Session(session_id=f"s{i}", job_parameter_values={}, session_root_directory=sys.argv[1])
    stop = threading.Event()
    def hammer():
        while not stop.is_set():
            try:
                s.clear_ending_only()
            except SessionError:
                pass
    t = threading.Thread(target=hammer, daemon=True)
    t.start()
    s.cleanup()
    stop.set()
    t.join()
print("done")
"""


def test_cleanup_with_a_concurrent_call_and_logging_on(tmp_path: Path) -> None:
    """``cleanup`` holds the session lock while the crate logs, and each log
    record needs the GIL. A concurrent call that waited for the lock while
    holding the GIL deadlocked. Every lock of the session is now taken with
    the GIL released. This runs in a fresh interpreter so the INFO level is
    in force when the binding's logger first looks it up."""
    import subprocess

    result = subprocess.run(
        [sys.executable, "-c", _CONCURRENT_CLEANUP, str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=25,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "done"


_CANCEL_ON_BANNER = r"""
import logging, sys, time
from openjd import _openjd_rs
from openjd._openjd_rs import Session, SessionState, deserialize_step
SessionError = getattr(_openjd_rs, "SessionError")
results = []
class CancelOnBanner(logging.Handler):
    def emit(self, record):
        if "Running Task" in record.getMessage() and not results:
            try:
                session.cancel_action()
                results.append("canceled")
            except SessionError as e:
                results.append(str(e))
logging.getLogger().addHandler(CancelOnBanner())
logging.getLogger().setLevel(logging.INFO)
session = Session(session_id="s", job_parameter_values={}, session_root_directory=sys.argv[1])
script = deserialize_step(
    {"name": "S", "script": {"actions": {"onRun": {"command": sys.executable, "args": ["-c", ""]}}}}
).script
session.run_task(step_script=script)
while session.state == SessionState.RUNNING:
    time.sleep(0.02)
session.cleanup()
print(results)
"""


def test_cancel_from_the_action_thread_before_it_starts(tmp_path: Path) -> None:
    """The crate logs the "Running Task" banner on the action thread between
    reporting the action ``Running`` and installing its cancel token. A
    logging handler that cancels there can't wait for the token, which can't
    appear while it runs, so it raises at once instead of hanging. Runs in a
    fresh interpreter, as above."""
    import subprocess

    result = subprocess.run(
        [sys.executable, "-c", _CANCEL_ON_BANNER, str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=25,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "['Cannot cancel: the action has not started yet']"


_CANCEL_WHILE_THE_ACTION_THREAD_WAITS = r"""
import logging, sys, time
from openjd._openjd_rs import ActionState, Session, SessionState, deserialize_step
class SlowOnBanner(logging.Handler):
    def emit(self, record):
        if "Running Task" in record.getMessage():
            time.sleep(2.5)
logging.getLogger().addHandler(SlowOnBanner())
logging.getLogger().setLevel(logging.INFO)
session = Session(session_id="s", job_parameter_values={}, session_root_directory=sys.argv[1])
script = deserialize_step(
    {"name": "S", "script": {"actions": {"onRun": {
        "command": sys.executable, "args": ["-c", "import time; time.sleep(30)"]}}}}
).script
session.run_task(step_script=script)
session.cancel_action()
while session.state in (SessionState.RUNNING, SessionState.CANCELING):
    time.sleep(0.02)
print(session.action_status.state.name)
session.cleanup()
"""


def test_cancel_while_the_action_thread_is_slow_to_start(tmp_path: Path) -> None:
    """The gap between the crate reporting ``Running`` and installing the
    cancel token includes logging the action's banner, which needs the GIL
    and runs every Python logging handler. Here a handler takes 2.5 s. A
    cancel from another thread waits the gap out rather than giving up; with
    a 2 s limit it used to raise "Cannot cancel: the action has not started
    yet", and the task ran to the end."""
    import subprocess

    result = subprocess.run(
        [sys.executable, "-c", _CANCEL_WHILE_THE_ACTION_THREAD_WAITS, str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=25,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "CANCELED"
