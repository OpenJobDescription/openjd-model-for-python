# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""How ``Session`` handles a failed action, through openjd-sessions 0.10.0.

- openjd-rs#532: when ``run_task``, ``enter_environment`` or
  ``exit_environment`` fails before its subprocess starts, for example because a parameter value can't be coerced,
  the action fails with the error's message and the session becomes
  ending-only, as the pure-Python ``openjd.sessions`` does. Before, the binding
  saw an error it discards, so ``action_status`` stayed ``None`` and the
  session went back to ``READY``.
- openjd-rs#524: an action that fails leaves the session ending-only, even
  after ``exit_environment(keep_session_running=True)`` succeeds. Before, that
  exit returned the session to ``READY``.
- openjd-rs#536: when ``exit_environment`` can't build its symbol table from
  the ``resolved_symtab`` it is given, it runs ``onExit`` with the table the
  environment was entered with. Before, ``onExit`` didn't run.
- openjd-rs#530: white space around a number in an INT or FLOAT parameter
  value is ignored. Before, such a value failed before the action started,
  which the binding didn't report, so the task silently didn't run.

What a session does with a call it then refuses is in ``test_known_gaps.py``.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

from openjd._openjd_rs import (
    ActionState,
    Session,
    SessionState,
    _reconstruct_serialized_symtab,
    create_environment,
    decode_environment_template,
    deserialize_step,
)


def _python(code: str) -> dict[str, Any]:
    return {"command": sys.executable, "args": ["-c", code]}


def _step_script(action: dict[str, Any]) -> Any:
    return deserialize_step({"name": "S", "script": {"actions": {"onRun": action}}}).script


def _environment(**actions: dict[str, Any]) -> Any:
    return create_environment(
        decode_environment_template(
            template={
                "specificationVersion": "environment-2023-09",
                "environment": {"name": "E", "script": {"actions": actions}},
            }
        )
    )


def _settle(session: Session) -> None:
    deadline = time.monotonic() + 30
    while session.state == SessionState.RUNNING and time.monotonic() < deadline:
        time.sleep(0.05)
    assert session.state != SessionState.RUNNING, "action did not finish within 30s"


def _session(tmp_path: Path, **kwargs: Any) -> Session:
    return Session(
        session_id="s", job_parameter_values={}, session_root_directory=str(tmp_path), **kwargs
    )


def test_a_task_that_fails_before_it_starts_fails_the_action(tmp_path: Path) -> None:
    session = _session(tmp_path)
    try:
        session.run_task(
            step_script=_step_script({"command": "echo", "args": ["{{Task.Param.F}}"]}),
            task_parameter_values={"F": {"type": "INT", "value": "abc"}},
        )
        _settle(session)
        status = session.action_status
        assert status is not None
        assert status.state == ActionState.FAILED
        assert status.fail_message == (
            "Failed to coerce parameter 'Task.RawParam.F': "
            "Cannot convert 'abc' to int: invalid digit found in string"
        )
        assert session.state == SessionState.READY_ENDING
    finally:
        session.cleanup()


def test_an_environment_that_fails_before_it_starts_fails_the_action(tmp_path: Path) -> None:
    """The environment still counts as entered, so it can be exited, and its
    exit fails before ``onExit`` starts the same way and counts as exited."""
    session = Session(
        session_id="s",
        job_parameter_values={"P": {"type": "PATH", "value": "/a/" + "x" * 32_800}},
        session_root_directory=str(tmp_path),
    )
    try:
        identifier = session.enter_environment(
            environment=_environment(onEnter=_python(""), onExit=_python(""))
        )
        _settle(session)
        status = session.action_status
        assert status is not None
        assert status.state == ActionState.FAILED
        assert status.fail_message == (
            "Failed to apply path mapping to Param.P: "
            "the path is 32803 bytes long, more than the limit of 32768 bytes"
        )
        assert session.state == SessionState.READY_ENDING
        assert session.environments_entered == [identifier]
        session.exit_environment(identifier=identifier)
        _settle(session)
        status = session.action_status
        assert status is not None
        assert status.state == ActionState.FAILED
        assert session.environments_entered == []
    finally:
        session.cleanup()


def test_a_failed_task_keeps_the_session_ending_only(tmp_path: Path) -> None:
    session = _session(tmp_path)
    try:
        identifier = session.enter_environment(environment=_environment(onEnter=_python("")))
        _settle(session)
        session.run_task(step_script=_step_script(_python("raise SystemExit(1)")))
        _settle(session)
        assert session.state == SessionState.READY_ENDING
        session.exit_environment(identifier=identifier, keep_session_running=True)
        _settle(session)
        status = session.action_status
        assert status is not None
        assert status.state == ActionState.SUCCESS
        assert session.state == SessionState.READY_ENDING
    finally:
        session.cleanup()


def test_on_exit_runs_with_the_enter_time_table(tmp_path: Path) -> None:
    marker = tmp_path / "on-exit-ran"
    session = _session(tmp_path)
    try:
        identifier = session.enter_environment(
            environment=_environment(
                onEnter=_python(""),
                onExit=_python(f"open({str(marker)!r}, 'w').close()"),
            )
        )
        _settle(session)
        not_a_table = _reconstruct_serialized_symtab("{}")
        session.exit_environment(identifier=identifier, resolved_symtab=not_a_table)
        _settle(session)
        status = session.action_status
        assert status is not None
        assert status.state == ActionState.SUCCESS
        assert marker.exists()
        assert session.state == SessionState.READY
    finally:
        session.cleanup()


def test_white_space_around_a_numeric_parameter_value_is_ignored(tmp_path: Path) -> None:
    out = tmp_path / "out.txt"
    session = Session(
        session_id="s",
        job_parameter_values={"I": {"type": "INT", "value": " 7 "}},
        session_root_directory=str(tmp_path),
    )
    try:
        session.run_task(
            step_script=_step_script(
                {
                    "command": sys.executable,
                    "args": [
                        "-c",
                        "import sys; open(sys.argv[1], 'w').write(sys.argv[2] + '|' + sys.argv[3])",
                        str(out),
                        "{{Param.I}}",
                        "{{Task.Param.F}}",
                    ],
                }
            ),
            task_parameter_values={"F": {"type": "FLOAT", "value": " 1.50 "}},
        )
        _settle(session)
        status = session.action_status
        assert status is not None
        assert status.state == ActionState.SUCCESS
        assert out.read_text() == "7|1.50"
    finally:
        session.cleanup()
