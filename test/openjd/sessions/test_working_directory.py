# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""How ``Session`` names its working directory."""

from __future__ import annotations

import os
import re

from openjd._openjd_rs import Session


def test_the_working_directory_is_named_with_8_random_characters() -> None:
    """Since openjd-sessions 0.8.2 (openjd-rs#444) the session working directory
    is named with exactly 8 characters from ``[a-z0-9_]`` and no part of the
    session ID, as the pure-Python reference's ``mkdtemp(prefix="")`` names it.
    Before, the name was the session ID followed by 32 hex digits."""
    session = Session(session_id="my-session-id", job_parameter_values={})
    try:
        name = os.path.basename(session.working_directory)
        assert re.fullmatch(r"[a-z0-9_]{8}", name), name
    finally:
        session.cleanup()
