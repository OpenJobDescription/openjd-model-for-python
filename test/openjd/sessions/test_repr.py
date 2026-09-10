# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""``__repr__`` output for the sessions bindings must be parseable Python.

These reprs were built with ``format!("{:?}")``, which is not a Python
literal writer. Rust's ``Debug`` for ``str`` agrees with Python on the
quote, the backslash and the C0 controls, but renders anything else
non-printable as ``\\u{a0}`` -- and CPython wants exactly four hex digits
after ``\\u``, so the literal does not parse. ``Debug`` for ``Option``
likewise emits ``Some(0)``, which is a ``NameError``.

That made a repr corruptible by its own data. ``ActionResult.stdout`` is
captured process output, so a non-ASCII byte in a job's stdout is ordinary
rather than adversarial, and ``PosixSessionUser`` carries a user name that
arrives from outside. Both land in log lines and exception messages.

Every string field now goes through CPython's own ``repr()``, so the
escaping is by construction whatever the running interpreter produces.
"""

from __future__ import annotations

import pytest

from openjd._openjd_rs import (
    ActionResult,
    ActionState,
    ActionStatus,
    PosixSessionUser,
)

# The characters Rust's Debug renders as \u{...}: non-printable outside
# ASCII (U+00A0, U+3000, U+0085) plus non-printable ASCII (U+007F). Then
# the ones Debug does escape correctly, kept as controls against a
# hand-rolled replacement getting them wrong, and printable non-ASCII
# that must survive verbatim.
HOSTILE_STRINGS = [
    "a\xa0b",
    "a\u3000b",
    "a\x85b",
    "a\x7fb",
    "a\u200bb",
    "a\U00100000b",
    'a"b',
    "it's",
    "a\\b",
    "a\nb",
    "a\r\nb",
    "a\tb",
    "a\x00b",
    "café",
    "a\U0001f600b",
    "",
]

ALL_ACTION_STATES = [
    ActionState.RUNNING,
    ActionState.SUCCESS,
    ActionState.FAILED,
    ActionState.CANCELED,
    ActionState.TIMEOUT,
]

EVAL_NS = {
    "ActionResult": ActionResult,
    "ActionState": ActionState,
    "ActionStatus": ActionStatus,
    "PosixSessionUser": PosixSessionUser,
}


def assert_parses(text: str) -> None:
    """The repr must at least be syntactically valid Python."""
    compile(text, "<repr>", "eval")


class TestActionResultRepr:
    """``ActionResult.stdout`` is captured process output."""

    @pytest.mark.parametrize("stdout", HOSTILE_STRINGS)
    def test_repr_parses(self, stdout: str) -> None:
        assert_parses(repr(ActionResult(state=ActionState.SUCCESS, exit_code=0, stdout=stdout)))

    @pytest.mark.parametrize("stdout", HOSTILE_STRINGS)
    def test_repr_embeds_cpython_repr_of_stdout(self, stdout: str) -> None:
        result = ActionResult(state=ActionState.SUCCESS, exit_code=0, stdout=stdout)
        assert repr(result) == (
            f"ActionResult(state=ActionState.SUCCESS, exit_code=0, stdout={stdout!r})"
        )

    @pytest.mark.parametrize("stdout", HOSTILE_STRINGS)
    def test_repr_round_trips(self, stdout: str) -> None:
        result = ActionResult(state=ActionState.SUCCESS, exit_code=0, stdout=stdout)
        assert eval(repr(result), dict(EVAL_NS)) == result

    @pytest.mark.parametrize(
        "exit_code,expected",
        [(0, "exit_code=0"), (1, "exit_code=1"), (-9, "exit_code=-9"), (None, "exit_code=None")],
    )
    def test_repr_renders_exit_code_as_python(self, exit_code: int | None, expected: str) -> None:
        # Debug would emit `Some(0)`, which is a NameError.
        assert expected in repr(
            ActionResult(state=ActionState.SUCCESS, exit_code=exit_code, stdout="")
        )

    @pytest.mark.parametrize("state", ALL_ACTION_STATES)
    def test_repr_names_the_state_as_python(self, state: ActionState) -> None:
        result = ActionResult(state=state, exit_code=0, stdout="")
        assert f"state={state!r}" in repr(result)
        assert eval(repr(result), dict(EVAL_NS)) == result


class TestActionStatusRepr:
    """No string field, but the same ``Option`` and enum defects."""

    @pytest.mark.parametrize("exit_code", [0, 1, -9, None])
    def test_repr_is_evaluable(self, exit_code: int | None) -> None:
        status = ActionStatus(state=ActionState.SUCCESS, exit_code=exit_code)
        assert_parses(repr(status))
        # Evaluates without NameError; ActionStatus has no __eq__ against a
        # rebuilt instance's other fields, so this asserts evaluability only.
        eval(repr(status), dict(EVAL_NS))

    def test_repr_renders_none_exit_code(self) -> None:
        assert repr(ActionStatus(state=ActionState.FAILED, exit_code=None)) == (
            "ActionStatus(state=ActionState.FAILED, exit_code=None)"
        )


class TestPosixSessionUserRepr:
    """``user`` and ``group`` arrive from outside."""

    @pytest.mark.parametrize("value", HOSTILE_STRINGS)
    def test_repr_parses_for_user(self, value: str) -> None:
        assert_parses(repr(PosixSessionUser(user=value, group="g")))

    @pytest.mark.parametrize("value", HOSTILE_STRINGS)
    def test_repr_matches_cpython_for_user(self, value: str) -> None:
        assert repr(PosixSessionUser(user=value, group="g")) == (
            f"PosixSessionUser(user={value!r}, group={'g'!r})"
        )

    @pytest.mark.parametrize("value", HOSTILE_STRINGS)
    def test_repr_matches_cpython_for_group(self, value: str) -> None:
        # `group` is a separate argument to the same writer; a fix applied
        # to only the first would pass every `user` case above.
        assert repr(PosixSessionUser(user="u", group=value)) == (
            f"PosixSessionUser(user={'u'!r}, group={value!r})"
        )


class TestReprNegativeControls:
    """Text needing no escaping must pass through unaltered."""

    def test_plain_action_result(self) -> None:
        assert repr(ActionResult(state=ActionState.SUCCESS, exit_code=0, stdout="ok")) == (
            "ActionResult(state=ActionState.SUCCESS, exit_code=0, stdout='ok')"
        )

    def test_plain_posix_session_user(self) -> None:
        assert repr(PosixSessionUser(user="alice", group="staff")) == (
            "PosixSessionUser(user='alice', group='staff')"
        )

    def test_state_enum_repr_unchanged(self) -> None:
        # The spelling the reprs above embed.
        assert repr(ActionState.SUCCESS) == "ActionState.SUCCESS"
