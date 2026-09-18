# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""``Session(caller_limits=...)`` applies the run-time half of a caller's policy.

openjd-sessions 0.7.0 (openjd-rs#399) added ``SessionConfig.limits``, and this
binding fills it from a ``CallerLimits`` — the same value a submitting service
passes to ``decode_job_template`` and ``create_job``. A session is the
enforcement boundary for the resolved-value caps: a worker can run a job that
never passed through the validating process, and only the session sees the final
resolved value. 0.6.0 had no such field, so a session enforced nothing beyond
the spec.

These tests run a real subprocess, which is why they live here rather than
alongside the model-layer cap tests in ``test/openjd/model_v1``.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from openjd._openjd_rs import ActionState, CallerLimits, Session, deserialize_step


def _step(arg: str) -> Any:
    """A job-side ``Step`` whose ``onRun`` passes ``arg`` to ``echo``."""
    return deserialize_step(
        {
            "name": "S",
            "script": {"actions": {"onRun": {"command": "echo", "args": [arg]}}},
        }
    )


def _run_task(arg: str, caller_limits: Optional[CallerLimits]) -> tuple[ActionState, str]:
    """Run one task to completion; return its final state and message."""
    session = Session(
        session_id=f"caller-limits-{time.time_ns()}",
        job_parameter_values={},
        caller_limits=caller_limits,
    )
    try:
        session.run_task(step_script=_step(arg).script)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            status = session.action_status
            if status is not None and status.state != ActionState.RUNNING:
                break
            time.sleep(0.05)
        status = session.action_status
        assert status is not None, "action never reported a status"
        assert status.state != ActionState.RUNNING, "action did not finish within 30s"
        return status.state, status.fail_message or status.status_message or ""
    finally:
        session.cleanup()


class TestSessionResolvedArgLengthCap:
    def test_an_argument_over_the_cap_fails_the_action(self) -> None:
        state, message = _run_task("a" * 40, CallerLimits(max_resolved_arg_len=5))
        assert state == ActionState.FAILED
        assert "resolved value is 40 characters, exceeding the maximum of 5" in message

    def test_an_argument_under_the_cap_runs(self) -> None:
        """Negative control: the same argument under a cap it fits."""
        state, _ = _run_task("a" * 40, CallerLimits(max_resolved_arg_len=99))
        assert state == ActionState.SUCCESS

    def test_omitting_caller_limits_enforces_nothing(self) -> None:
        """Negative control, and the only behaviour openjd-sessions 0.6.0 had."""
        state, _ = _run_task("a" * 40, None)
        assert state == ActionState.SUCCESS

    def test_an_unrelated_limit_does_not_affect_the_action(self) -> None:
        """A ``CallerLimits`` carrying only document-shape caps has no run-time
        counterpart, so the session ignores it rather than rejecting the value."""
        state, _ = _run_task("a" * 40, CallerLimits(max_step_count=1, max_template_size=1))
        assert state == ActionState.SUCCESS
