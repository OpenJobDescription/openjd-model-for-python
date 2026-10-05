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


import sys

import pytest


@pytest.mark.parametrize("name", ["Any", "Optional", "Sequence", "Union", "re", "Enum"])
def test_no_internal_imports_leak_at_top_level(name: str) -> None:
    import openjd.model._v1 as v1

    assert not hasattr(v1, name), f"{name} leaks as a public attribute on openjd.model._v1"


# ── v0 PATH preprocessing lags the spec (openjd-specifications#191) ──
#
# These run v0, not the binding: openjd-model 0.11.0 (openjd-rs#421) made v1 join
# LIST[PATH] defaults and normalize relative submitted PATH values, which Template
# Schemas §2.2 and §2.12 now require. ``TestListPathDefaultRules`` and
# ``TestSubmittedPathNormalization`` in ``test_create_job.py`` pin the v1 side.

_V0_PATH_GAP = "v0 preprocess_job_parameters does not apply openjd-specifications#191 (§2.2, §2.12)"


def _v0_preprocess(definition: dict, values: dict) -> dict:
    from pathlib import Path

    import openjd.model as v0

    template = v0.decode_job_template(
        template={
            "specificationVersion": "jobtemplate-2023-09",
            "extensions": ["EXPR"],
            "name": "T",
            "parameterDefinitions": [definition],
            "steps": [{"name": "S", "script": {"actions": {"onRun": {"command": "echo"}}}}],
        },
        supported_extensions=["EXPR"],
    )
    out = v0.preprocess_job_parameters(
        job_template=template,
        job_parameter_values=values,
        job_template_dir=Path("/a/job1"),
        current_working_dir=Path("/tmp/cwd"),
    )
    return {name: value.value for name, value in out.items()}


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX fixture paths")
@pytest.mark.xfail(strict=True, reason=_V0_PATH_GAP)
def test_v0_joins_list_path_defaults_to_the_template_directory() -> None:
    out = _v0_preprocess(
        {"name": "Paths", "type": "LIST[PATH]", "default": ["./output", "sub/../other"]}, {}
    )
    assert out["Paths"] == ["/a/job1/output", "/a/job1/other"]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX fixture paths")
@pytest.mark.xfail(strict=True, reason=_V0_PATH_GAP)
def test_v0_normalizes_a_relative_submitted_path() -> None:
    out = _v0_preprocess({"name": "P", "type": "PATH"}, {"P": "sub/../other"})
    assert out["P"] == "/tmp/cwd/other"
