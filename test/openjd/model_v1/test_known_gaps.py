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


import pytest


@pytest.mark.parametrize("name", ["Any", "Optional", "Sequence", "Union", "re", "Enum"])
def test_no_internal_imports_leak_at_top_level(name: str) -> None:
    import openjd.model._v1 as v1

    assert not hasattr(v1, name), f"{name} leaks as a public attribute on openjd.model._v1"
