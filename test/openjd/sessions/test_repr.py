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

import os

import pytest

from openjd._openjd_rs import (
    ActionResult,
    ActionState,
    ActionStatus,
    PathFormat,
    PathMappingRule,
    PosixSessionUser,
    Session,
    SessionState,
)

# The characters Rust's Debug renders in its brace form, which Python
# cannot parse. Debug special-cases only the quote, the backslash, and
# NUL/tab/CR/LF; every OTHER control falls through, so ESC is included
# deliberately -- ANSI colour sequences in captured stdout are the most
# likely trigger of this bug in the field, far more so than any exotic
# codepoint. Then the escapes Debug does get right, kept as controls
# against a hand-rolled replacement breaking them, and printable
# non-ASCII that must survive verbatim.
HOSTILE_STRINGS = [
    "esc\x1b[0m",
    "a\x01b",
    "a\x1fb",
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
    """No string field, but the same ``Option`` and enum defects.

    This repr is deliberately lossy: it shows ``state`` and ``exit_code``,
    not the other five fields ``__eq__`` compares. So it is *evaluable*
    but does not round-trip, and it cannot be made to -- ``started_at``
    and ``ended_at`` are not constructor arguments. Do not read the
    Python-literal spelling as a round-trip guarantee; the lossiness is
    pinned below so a later change to the field list is a deliberate one.
    """

    @pytest.mark.parametrize("exit_code", [0, 1, -9, None])
    def test_repr_is_evaluable(self, exit_code: int | None) -> None:
        status = ActionStatus(state=ActionState.SUCCESS, exit_code=exit_code)
        assert_parses(repr(status))
        # The defect this pins: `Some(0)` and a bare `SUCCESS` both raised
        # NameError. Evaluability only -- see the class docstring.
        eval(repr(status), dict(EVAL_NS))

    def test_repr_omits_fields_that_eq_compares(self) -> None:
        # Guards the class docstring's claim rather than asserting a
        # round-trip that cannot hold.
        status = ActionStatus(
            state=ActionState.SUCCESS, exit_code=0, progress=50.0, status_message="halfway"
        )
        assert repr(status) == "ActionStatus(state=ActionState.SUCCESS, exit_code=0)"
        rebuilt = eval(repr(status), dict(EVAL_NS))
        assert rebuilt != status
        assert rebuilt.progress is None and status.progress == 50.0

    def test_repr_renders_none_exit_code(self) -> None:
        assert repr(ActionStatus(state=ActionState.FAILED, exit_code=None)) == (
            "ActionStatus(state=ActionState.FAILED, exit_code=None)"
        )


@pytest.mark.skipif(os.name != "posix", reason="PosixSessionUser is constructible only on posix")
class TestPosixSessionUserRepr:
    """``user`` and ``group`` arrive from outside.

    The binding gates construction on ``#[cfg(unix)]`` and raises
    ``RuntimeError: Only available on posix systems.`` elsewhere, so these
    mirror that with ``os.name``. ``WindowsSessionUser`` has no counterpart
    here: off the process user it demands a password or a logon token, so
    it cannot be built with an arbitrary name just to read its repr.
    """

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


class TestSessionRepr:
    """``session_id`` is supplied by the caller, so it needs escaping too.

    A real ``Session`` creates a working directory, so each case calls
    ``cleanup()``. The keyword must match the constructor: the repr used to
    say ``id=``, which parsed but raised ``TypeError`` on eval.
    """

    @staticmethod
    def _session(session_id: str) -> Session:
        return Session(session_id=session_id, job_parameter_values={})

    # `session_id` becomes a path component of the working directory, so NUL
    # is refused by the filesystem before any repr is taken ("file name
    # contained an unexpected NUL byte"). That is a constructor constraint,
    # not a repr gap -- ActionResult covers NUL through the same helper.
    SESSION_ID_CASES = [s for s in HOSTILE_STRINGS if "\x00" not in s]

    @pytest.mark.parametrize("session_id", SESSION_ID_CASES)
    def test_repr_matches_cpython_for_session_id(self, session_id: str) -> None:
        session = self._session(session_id)
        try:
            assert repr(session) == (
                f"Session(session_id={session_id!r}, state=SessionState.READY)"
            )
            assert_parses(repr(session))
        finally:
            session.cleanup()

    def test_repr_uses_the_constructor_keyword(self) -> None:
        # `id=` parsed but was not a real argument, so eval raised TypeError.
        session = self._session("s1")
        try:
            r = repr(session)
            assert "session_id=" in r and "(id=" not in r
            # `job_parameter_values` is required and absent from the repr, so
            # a full round-trip is not available; this pins the keyword only.
            with pytest.raises(TypeError):
                eval(r, {"Session": Session, "SessionState": SessionState})
        finally:
            session.cleanup()


class TestPathMappingRuleRepr:
    """Hand-rolled ``'{}'`` quoting corrupted Windows paths silently.

    ``C:\\temp`` rendered as ``'C:\\temp'``, which Python reads as ``C:`` +
    TAB + ``emp`` -- it parses, and yields the wrong string. An apostrophe
    in a path closed the literal early instead.
    """

    @pytest.mark.parametrize("path", HOSTILE_STRINGS + ["C:\\temp", "C:\\x", "/home/o'brien"])
    def test_repr_matches_cpython_for_both_paths(self, path: str) -> None:
        rule = PathMappingRule(
            source_path_format=PathFormat.POSIX, source_path=path, destination_path=path
        )
        assert repr(rule) == (
            "PathMappingRule(source_path_format=PathFormat.POSIX, "
            f"source_path={path!r}, destination_path={path!r})"
        )

    @pytest.mark.parametrize("path", ["C:\\temp", "C:\\users", "/home/o'brien/scenes"])
    def test_repr_round_trips_a_windows_path(self, path: str) -> None:
        # The silent-corruption case: this used to parse and give back a
        # different string.
        rule = PathMappingRule(
            source_path_format=PathFormat.WINDOWS, source_path="/mnt/s", destination_path=path
        )
        rebuilt = eval(repr(rule), {"PathMappingRule": PathMappingRule, "PathFormat": PathFormat})
        assert rebuilt.destination_path == path
        assert rebuilt == rule


class TestReprNegativeControls:

    def test_plain_action_result(self) -> None:
        assert repr(ActionResult(state=ActionState.SUCCESS, exit_code=0, stdout="ok")) == (
            "ActionResult(state=ActionState.SUCCESS, exit_code=0, stdout='ok')"
        )

    @pytest.mark.skipif(
        os.name != "posix", reason="PosixSessionUser is constructible only on posix"
    )
    def test_plain_posix_session_user(self) -> None:
        assert repr(PosixSessionUser(user="alice", group="staff")) == (
            "PosixSessionUser(user='alice', group='staff')"
        )

    def test_state_enum_repr_unchanged(self) -> None:
        # The spelling the reprs above embed.
        assert repr(ActionState.SUCCESS) == "ActionState.SUCCESS"
