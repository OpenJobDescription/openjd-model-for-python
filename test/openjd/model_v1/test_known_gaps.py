# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Failing tests demonstrating behavioural gaps between the Rust-backed
``openjd.model._v1`` bindings and the v0 (pure-Python, pydantic-based)
reference implementation that ships in the same repo as
``openjd.model`` / ``openjd.model.v0``.

Every test here is expected to *fail* against the current bindings and
is marked ``xfail``. As gaps are resolved the corresponding tests are
moved to the appropriate home in this directory (e.g. error-class
tests to ``test_errors.py``, parameter tests to
``test_job_param_defs.py``); this file is being driven to zero. An
xpass is a signal that something is mis-categorised — promote it.

Cross-reference:
    reports/model-bindings-quality-evaluation-report.md
"""

from __future__ import annotations

from typing import Any

# ── Top-level package no longer leaks typing imports ──
#
# An earlier draft of ``openjd.model._v1`` imported ``Any``,
# ``Optional``, ``Sequence``, ``Union`` from ``typing`` (and ``re``
# from stdlib) without underscore-prefixing or listing them in
# ``__all__``. They were leaking as plain attribute access
# (``openjd.model._v1.Optional``), which tooling that walks the
# public attribute set of the module treated as part of the public
# surface. The v1 module no longer needs any of those imports — the
# capability validators moved entirely to Rust and the document
# parsing helper was removed — so this regression test verifies
# none of them have been re-introduced.


import pytest


@pytest.mark.parametrize("name", ["Any", "Optional", "Sequence", "Union", "re", "Enum"])
def test_no_internal_imports_leak_at_top_level(name: str) -> None:
    import openjd.model._v1 as v1

    assert not hasattr(v1, name), f"{name} leaks as a public attribute on openjd.model._v1"


# ── Chunked parameter spaces: two divergences from the v0 reference ──
#
# Found while adding `chunks_task_count_override` to
# `StepParameterSpaceIterator`. Neither is caused by that argument — both
# reproduce without it — so they are recorded here rather than fixed in
# passing.


def _chunked_step(constraint: str) -> Any:
    from openjd.model._v1 import create_job, decode_job_template

    template = {
        "specificationVersion": "jobtemplate-2023-09",
        "name": "T",
        "extensions": ["TASK_CHUNKING"],
        "steps": [
            {
                "name": "S",
                "parameterSpace": {
                    "taskParameterDefinitions": [
                        {
                            "name": "Frame",
                            "type": "CHUNK[INT]",
                            "range": "1-10",
                            "chunks": {"defaultTaskCount": 5, "rangeConstraint": constraint},
                        }
                    ]
                },
                "script": {
                    "actions": {"onRun": {"command": "echo", "args": ["{{Task.Param.Frame}}"]}}
                },
            }
        ],
    }
    job_template = decode_job_template(template=template, supported_extensions=["TASK_CHUNKING"])
    return create_job(job_template=job_template, job_parameter_values={}).steps[0]


@pytest.mark.xfail(
    reason="v1 derives chunks_parameter_name and chunks_default_task_count from adaptive "
    "detection, so both are None for a statically chunked space. v0 reports them for any "
    "chunked space. See openjd-model step_param_space.rs: chunks_param_name and "
    "adaptive_chunk_size are both built from adaptive_info.",
    strict=True,
)
def test_chunk_metadata_is_reported_for_a_static_space() -> None:
    """v0 returns ``"Frame"`` and ``5`` for this space. v1 returns ``None`` for both.

    Neither value is unknowable — both are in the template — so a consumer inspecting a
    static chunked space through v1 cannot learn which parameter chunks, or at what size.
    """
    from openjd.model._v1.job import StepParameterSpaceIterator

    it = StepParameterSpaceIterator(step=_chunked_step("CONTIGUOUS"))
    assert it.chunks_adaptive is False
    assert it.chunks_parameter_name == "Frame"
    assert it.chunks_default_task_count == 5


@pytest.mark.xfail(
    reason="v1 refuses random access whenever the space needs sequential iteration, and "
    "contiguous chunking always does. v0 supports indexing the same space.",
    strict=True,
)
def test_a_contiguous_chunked_space_supports_indexing() -> None:
    """v0 answers ``it[0]`` with ``1-5``. v1 raises ``IndexError``.

    ``len()`` works on this space, so the count is known; only ``get`` declines.
    """
    from openjd.model._v1.job import StepParameterSpaceIterator

    it = StepParameterSpaceIterator(step=_chunked_step("CONTIGUOUS"))
    assert len(it) == 2
    assert it[0]["Frame"].value == "1-5"
