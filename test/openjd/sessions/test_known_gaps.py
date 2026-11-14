# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Known gaps between the sessions binding and the pure-Python reference.

Each test is a strict xfail. When a gap is fixed, move its test next to the
surface it covers rather than leaving it here.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from openjd._openjd_rs import Session, SessionState, deserialize_step

# ── A call the session refuses returns as if it had started an action ──
#
# The non-blocking actions in ``rust-bindings/src/sessions/session.rs``
# (``run_task``, ``enter_environment``, ``exit_environment``,
# ``run_subprocess``) hand the call to a background thread and discard the
# crate's ``Result``. A call the crate refuses up front, such as ``run_task``
# on an ending-only session, therefore returns ``None``, runs nothing, and
# leaves ``action_status`` showing the previous action. The pure-Python
# ``openjd.sessions.Session`` raises for a session that isn't ``READY``.
#
# openjd-sessions 0.10.0 (openjd-rs#524) made this reachable in normal use: a
# failed action keeps the session ending-only even after
# ``exit_environment(keep_session_running=True)``, so the next ``run_task``
# is refused, and the caller sees the exit's ``SUCCESS``. With openjd-sessions
# 0.9.0 that ``run_task`` ran.


@pytest.mark.xfail(
    reason="A run_task the crate refuses returns None and leaves the previous action_status",
    strict=True,
)
def test_run_task_on_an_ending_only_session_raises(tmp_path: Path) -> None:
    def script(code: str):
        return deserialize_step(
            {
                "name": "S",
                "script": {"actions": {"onRun": {"command": sys.executable, "args": ["-c", code]}}},
            }
        ).script

    session = Session(session_id="s", job_parameter_values={}, session_root_directory=str(tmp_path))
    try:
        session.run_task(step_script=script("raise SystemExit(1)"))
        deadline = time.monotonic() + 30
        while session.state == SessionState.RUNNING and time.monotonic() < deadline:
            time.sleep(0.05)
        assert session.state == SessionState.READY_ENDING
        with pytest.raises(Exception):
            session.run_task(step_script=script(""))
    finally:
        session.cleanup()
