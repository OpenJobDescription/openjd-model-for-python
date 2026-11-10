# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""The Rust session runtime's structured log fields reach Python ``LogRecord`` objects.

The runtime's ``session_log!`` macro attaches ``session_id``, ``openjd_log_content``
and ``openjd_timestamp_usec`` to every record it emits, and the PyO3 logging bridge
forwards them as ``LogRecord`` attributes. This test runs one real session, at INFO as
well as at ERROR, and checks that every record carrying ``openjd_log_content`` carries
all three fields with the documented types and values, that every record carrying
``session_id`` names this session, and that no record carries a partial set of the
three. The runtime also logs a few records through plain ``log::`` calls rather than
``session_log!``; those carry only ``session_id`` (the session initialization record)
or no fields at all (conditional warnings), so the test does not require the three
fields on every record it collects.

The session runs in a child interpreter rather than in this process. The bridge caches
each Python logger's effective level the first time a record passes through it, so the
level the ``openjd.sessions`` logger has at that first record decides, for the rest of
the process, whether INFO records cross the boundary at all. The child sets the level
before the extension is imported, which makes the INFO-level records deterministic no
matter what else ran earlier in this test worker.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from typing import Any

_TAGS = ("session_id", "openjd_log_content", "openjd_timestamp_usec")

# ``LogContent`` bit values documented in specs/python-sessions-interface.md:
# BANNER=1, FILE_PATH=2, FILE_CONTENTS=4, COMMAND_OUTPUT=8, EXCEPTION_INFO=16,
# PROCESS_CONTROL=32, PARAMETER_INFO=64, HOST_INFO=128.
_DOCUMENTED_BITS = 0xFF
_EXCEPTION_INFO = 16

# Runs in a child interpreter. Argument 1 is the session id. It runs one task whose
# third argument exceeds the caller's resolved-argument cap, so the action fails
# deterministically before any process is launched, then prints every record the
# ``openjd.sessions`` logger received as one JSON line.
_PROBE = r"""
import json
import logging
import sys
import time

LOGGER = logging.getLogger("openjd.sessions")
LOGGER.setLevel(logging.INFO)
RECORDS = []


class Collector(logging.Handler):
    def emit(self, record):
        RECORDS.append(record)


LOGGER.addHandler(Collector())

from openjd._openjd_rs import ActionState, CallerLimits, Session, deserialize_step

session_id = sys.argv[1]
argument_limit = len(sys.executable) + 1
step = deserialize_step(
    {
        "name": "S",
        "script": {
            "actions": {
                "onRun": {
                    "command": sys.executable,
                    "args": ["-c", "pass", "a" * (argument_limit + 1)],
                }
            }
        },
    }
)
session = Session(
    session_id=session_id,
    job_parameter_values={},
    caller_limits=CallerLimits(max_resolved_arg_len=argument_limit),
)
try:
    session.run_task(step_script=step.script)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        status = session.action_status
        if status is not None and status.state != ActionState.RUNNING:
            break
        time.sleep(0.05)
    status = session.action_status
    state = None if status is None else status.state.name
finally:
    session.cleanup()


def describe(record):
    tags = {}
    for name in ("session_id", "openjd_log_content", "openjd_timestamp_usec"):
        if hasattr(record, name):
            value = getattr(record, name)
            tags[name] = {
                "type": type(value).__name__,
                "value": value if isinstance(value, str) else repr(value),
            }
    return {
        "logger": record.name,
        "level": record.levelname,
        "message": record.getMessage(),
        "tags": tags,
    }


print(json.dumps({"state": state, "records": [describe(record) for record in RECORDS]}))
"""


def _run_probe(session_id: str) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "-c", _PROBE, session_id],
        capture_output=True,
        text=True,
        timeout=25,
        check=False,
    )
    assert (
        completed.returncode == 0
    ), f"the probe interpreter exited with {completed.returncode}:\n{completed.stderr}"
    result: dict[str, Any] = json.loads(completed.stdout.strip().splitlines()[-1])
    return result


def test_every_rust_session_record_includes_structured_tags() -> None:
    session_id = f"logging-{time.time_ns()}"
    probe = _run_probe(session_id)

    assert (
        probe["state"] == "FAILED"
    ), f"the deliberate setup failure did not fail the action: {probe}"
    records = [record for record in probe["records"] if record["logger"] == "openjd.sessions"]
    assert records, "the Rust session emitted no records"

    # ``session_id`` is the one field the runtime also puts on its raw records, so
    # every record that carries it must name this session, as a ``str``.
    tagged = [record for record in records if "session_id" in record["tags"]]
    assert tagged, "no record carried session_id"
    for record in tagged:
        tag = record["tags"]["session_id"]
        assert tag["type"] == "str", record
        assert tag["value"] == session_id, record

    # A record either comes from ``session_log!`` and carries all three fields, or is a
    # raw ``log::`` record carrying only ``session_id`` or nothing. Any other subset
    # means a field was lost on the way across the bridge.
    for record in records:
        assert set(record["tags"]) in (set(_TAGS), {"session_id"}, set()), record

    # A record that carries the content category comes from ``session_log!``, which
    # always emits all three fields together.
    for record in records:
        tags = record["tags"]
        if "openjd_log_content" not in tags:
            continue
        assert set(tags) == set(_TAGS), record

        content = tags["openjd_log_content"]
        assert content["type"] == "str", record
        assert content["value"].isdigit(), record
        bits = int(content["value"])
        assert bits != 0, record
        assert bits & ~_DOCUMENTED_BITS == 0, record  # one of, or a combination of, the bits

        timestamp = tags["openjd_timestamp_usec"]
        assert timestamp["type"] == "str", record
        assert timestamp["value"].isdigit(), record
        assert int(timestamp["value"]) > 0, record

    fully_tagged = [record for record in records if set(record["tags"]) == set(_TAGS)]
    assert any(
        record["level"] == "INFO" for record in fully_tagged
    ), "no INFO record carried all three fields"
    failures = [record for record in fully_tagged if record["level"] == "ERROR"]
    assert failures, "the action failure record did not carry all three fields"
    assert any(
        int(record["tags"]["openjd_log_content"]["value"]) & _EXCEPTION_INFO for record in failures
    ), "the action failure record was not tagged EXCEPTION_INFO"
