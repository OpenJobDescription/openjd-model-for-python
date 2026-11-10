# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""``Session`` rejects an invalid path mapping rule.

Since openjd-sessions 0.9.0 (openjd-rs#472) a session keeps its rules in a
``PathMapper``, which requires each POSIX or WINDOWS ``source_path`` to be
absolute (How Jobs Are Run, "Path Mapping"). Before, a relative rule was
accepted and matched relative paths. The rules are checked when the session is
constructed and when ``extend_path_mapping_rules`` adds to them.
"""

from __future__ import annotations

import os
import time

import pytest

from openjd import _openjd_rs
from openjd._openjd_rs import Session
from openjd.expr import PathFormat, PathMappingRule

# Registered at runtime by `register_renamed_exception`; the type stub doesn't
# declare the exception classes.
SessionError: type[Exception] = getattr(_openjd_rs, "SessionError")

_GOOD = PathMappingRule(
    source_path_format=PathFormat.POSIX, source_path="/a", destination_path="/b"
)
_RELATIVE = PathMappingRule(
    source_path_format=PathFormat.POSIX, source_path="rel", destination_path="/b"
)
_MESSAGE = (
    "Invalid path mapping rules: path mapping rule 1: source_path 'rel' must be an "
    "absolute POSIX path, starting with '/'"
)


def test_construction_rejects_a_relative_source_path() -> None:
    with pytest.raises(SessionError) as exc_info:
        Session(
            session_id=f"path-mapping-{time.time_ns()}",
            job_parameter_values={},
            path_mapping_rules=[_GOOD, _RELATIVE],
        )
    assert str(exc_info.value) == _MESSAGE


def test_extend_rejects_a_relative_source_path() -> None:
    """The index counts from the first existing rule, so the one added rule
    after one existing rule is rule 1."""
    session = Session(
        session_id=f"path-mapping-{time.time_ns()}",
        job_parameter_values={},
        path_mapping_rules=[_GOOD],
    )
    try:
        with pytest.raises(SessionError) as exc_info:
            session.extend_path_mapping_rules([_RELATIVE])
        assert str(exc_info.value) == _MESSAGE
    finally:
        session.cleanup()


def test_the_working_directory_is_named_with_8_random_characters() -> None:
    """Since openjd-sessions 0.9.0 (openjd-rs#444) the session working directory
    is named with exactly 8 characters from ``[a-z0-9_]`` and no part of the
    session ID, as the pure-Python reference's ``mkdtemp(prefix="")`` names it.
    Before, the name was the session ID followed by 32 hex digits."""
    import re

    session = Session(session_id="my-session-id", job_parameter_values={})
    try:
        name = os.path.basename(session.working_directory)
        assert re.fullmatch(r"[a-z0-9_]{8}", name), name
    finally:
        session.cleanup()
