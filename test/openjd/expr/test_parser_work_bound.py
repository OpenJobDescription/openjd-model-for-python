# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Parsing an invalid expression takes bounded time (openjd-rs#489).

openjd-expr 0.11.0 to 0.14.0 parsed with RustPython's fork of Ruff's parser
(openjd-rs#429), whose CPython-style syntax-error hints parse ahead and rewind.
Hints nest inside brackets, so parse time doubled per unclosed bracket level.
Through these bindings, ``decode_job_template`` took 2.6 s in a release build
(39 s in a debug build) on the 101-byte ``"[i f(" * 20 + "x"``, and 5.0 s on
the 363-byte fuzz reproducer below. Any template field that takes an
expression could stall template decoding. openjd-expr 0.15.0 (openjd-rs#531)
parses with Astral's ``ruff_python_parser``, which has no such hints; each
input here now fails in a few milliseconds.

Each case runs through the expression API and through both template decoders,
since the pure-Python ``openjd.model`` evaluates EXPR expressions with the same
Rust parser. The 1 s bound is generous so the tests don't flake on a slow CI
runner; one decode runs first so that one-time setup isn't timed.
"""

from __future__ import annotations

import time
from typing import Any, Callable

import pytest

from openjd.expr import ExpressionError, FormatString, parse_expression
from openjd.model import DecodeValidationError as V0DecodeValidationError
from openjd.model import decode_job_template as v0_decode_job_template
from openjd.model._v1 import decode_job_template as v1_decode_job_template
from openjd.model._v1.errors import DecodeValidationError as V1DecodeValidationError

_TIME_BOUND_SECONDS = 1.0

# The fuzz harness's reproducer for openjd-rs#489, 363 bytes.
_SLOW_DOTS = (
    "ginaen([manifestVersion.......................(............(......................"
    "........join.................(.....................n.................(..........."
    "................destination_55555path.(..............data......................"
    "......@....so, 1],.so[vted().d(......destination_55555path.(..............data.."
    "..............................so, dx in e"
)

_CASES = [
    pytest.param("[i f(" * 20 + "x", "Expected `,`, found identifier", id="unclosed [i f( x20"),
    pytest.param("f(a " * 20 + "x", "Expected `,`, found identifier", id="unclosed f(a x20"),
    pytest.param(_SLOW_DOTS, "Expected `,`, found `...`", id="fuzz slow-dots"),
]


def _template(expr: str) -> dict[str, Any]:
    return {
        "specificationVersion": "jobtemplate-2023-09",
        "extensions": ["EXPR"],
        "name": "T",
        "steps": [
            {
                "name": "S",
                "script": {
                    "actions": {"onRun": {"command": "echo", "args": ["{{ " + expr + " }}"]}}
                },
            }
        ],
    }


def _timed(f: Callable[[], object], exc_type: type[Exception]) -> tuple[float, str]:
    start = time.perf_counter()
    with pytest.raises(exc_type) as exc_info:
        f()
    return time.perf_counter() - start, str(exc_info.value)


@pytest.fixture(scope="module", autouse=True)
def _warm_up() -> None:
    v0_decode_job_template(template=_template("1"), supported_extensions=["EXPR"])
    v1_decode_job_template(template=_template("1"), supported_extensions=["EXPR"])


def test_the_101_byte_reproducer_is_101_bytes() -> None:
    """The input size the module docstring quotes."""
    assert len("[i f(" * 20 + "x") == 101
    assert len(_SLOW_DOTS) == 363


@pytest.mark.parametrize("expr, headline", _CASES)
def test_parse_expression(expr: str, headline: str) -> None:
    elapsed, message = _timed(lambda: parse_expression(expr), ExpressionError)
    assert message.startswith(f"Syntax error: {headline}\n  {expr}\n")
    assert elapsed < _TIME_BOUND_SECONDS


@pytest.mark.parametrize("expr, headline", _CASES)
def test_format_string(expr: str, headline: str) -> None:
    elapsed, message = _timed(lambda: FormatString("{{ " + expr + " }}"), ExpressionError)
    assert f"Syntax error: {headline}\n" in message
    assert elapsed < _TIME_BOUND_SECONDS


@pytest.mark.parametrize("expr, headline", _CASES)
def test_v0_decode_job_template(expr: str, headline: str) -> None:
    """The pure-Python model, which the Python CLI uses."""
    elapsed, message = _timed(
        lambda: v0_decode_job_template(template=_template(expr), supported_extensions=["EXPR"]),
        V0DecodeValidationError,
    )
    assert message.startswith(
        "1 validation errors for JobTemplate\n"
        "steps[0] -> script -> actions -> onRun -> args[0]:\n"
        f"\tFailed to parse interpolation expression at [0, {len(expr) + 6}]. "
        f"Reason: Syntax error: {headline}\n"
    )
    assert elapsed < _TIME_BOUND_SECONDS


@pytest.mark.parametrize("expr, headline", _CASES)
def test_v1_decode_job_template(expr: str, headline: str) -> None:
    elapsed, message = _timed(
        lambda: v1_decode_job_template(template=_template(expr), supported_extensions=["EXPR"]),
        V1DecodeValidationError,
    )
    assert message.startswith(
        "'jobtemplate-2023-09' failed checks: "
        f"Failed to parse interpolation expression at [0, {len(expr) + 6}]. "
        f"Reason: Syntax error: {headline}\n"
    )
    assert elapsed < _TIME_BOUND_SECONDS
