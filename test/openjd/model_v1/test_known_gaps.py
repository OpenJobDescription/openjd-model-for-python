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

import pytest

from openjd.model._v1 import (
    TemplateSpecificationVersion,
    decode_job_template,
    merge_job_parameter_definitions,
)


# ── JobTemplate.specification_version is comparable to TemplateSpecificationVersion ──
#
# Resolved: ``rust-bindings/src/model/types.rs`` (PyTemplateSpecificationVersion)
# was reshaped so the Rust pyclass exposes the v0 ``str``-Enum surface
# directly: lowercase variant names (``JOBTEMPLATE_v2023_09`` /
# ``ENVIRONMENT_v2023_09``), a ``.value`` getter, equality with the
# spec-form string, and a constructor that accepts the spec form or the
# variant name. There is now exactly one
# ``TemplateSpecificationVersion`` class — the one in ``openjd._openjd_rs``
# is also re-exported at ``openjd.model._v1`` and ``openjd.model._v1.types``
# (identity-preserving). ``JobTemplate.specification_version`` returns
# instances of the same class.


def test_template_specification_version_comparable_to_python_str_enum() -> None:
    t = decode_job_template(
        template={
            "specificationVersion": "jobtemplate-2023-09",
            "name": "T",
            "steps": [{"name": "S", "script": {"actions": {"onRun": {"command": "echo"}}}}],
        }
    )
    assert t.specification_version == TemplateSpecificationVersion.JOBTEMPLATE_v2023_09


# ── merge_job_parameter_definitions: default is always a string ──
#
# The spec for ``merge_job_parameter_definitions`` ("Return shape —
# list[dict], not typed pyclasses") says:
#
#     ``default`` (present only if the source template provided a
#     default) — the default value, in its native Python type
#     (``int`` / ``float`` / ``str`` / ``list`` / …) per the
#     parameter's type.
#
# In practice the binding emits the default as a ``str`` for every
# variant — including ``INT`` (where v0 carried the int) and ``FLOAT``
# (where v0 carried the float). The to-display-string coercion lives
# in ``rust-bindings/src/model/create_job_fns.rs::py_merge_job_parameter_definitions``
# (the ``default`` extraction routes through ``param_value.to_display_string()``).
#
# Fix path: at the v1 binding boundary, convert the default to its
# native Python type for ``INT`` (``int``), ``FLOAT`` (``float``),
# ``BOOL`` (``bool``), and the ``LIST[*]`` variants (``list[T]``).
# Strings stay as ``str``; ``PATH`` stays as ``str`` (matching the
# spec's "STRING / PATH" handling elsewhere). The Rust crate's
# ``MergedParameterDefinition::default`` already carries the typed
# value — the binding just needs to dispatch on ``param_type`` when
# inserting into the dict.
#
# Cross-reference: report Recommendation #3.


@pytest.mark.xfail(
    strict=True, reason="v1 emits default as str for every type; spec promises native Python type"
)
def test_merge_default_int_returned_as_int() -> None:
    t = decode_job_template(
        template={
            "specificationVersion": "jobtemplate-2023-09",
            "name": "T",
            "parameterDefinitions": [
                {"name": "Count", "type": "INT", "default": 5},
            ],
            "steps": [{"name": "S", "script": {"actions": {"onRun": {"command": "echo"}}}}],
        }
    )
    merged = merge_job_parameter_definitions(job_template=t)
    [count_def] = merged
    assert count_def["default"] == 5
    assert isinstance(count_def["default"], int)
    assert not isinstance(count_def["default"], str)


@pytest.mark.xfail(
    strict=True, reason="v1 emits default as str for every type; spec promises native Python type"
)
def test_merge_default_float_returned_as_float() -> None:
    t = decode_job_template(
        template={
            "specificationVersion": "jobtemplate-2023-09",
            "name": "T",
            "parameterDefinitions": [
                {"name": "Pi", "type": "FLOAT", "default": 3.14},
            ],
            "steps": [{"name": "S", "script": {"actions": {"onRun": {"command": "echo"}}}}],
        }
    )
    merged = merge_job_parameter_definitions(job_template=t)
    [pi_def] = merged
    assert pi_def["default"] == 3.14
    assert isinstance(pi_def["default"], float)


# ── merge_job_parameter_definitions drops the description field ──
#
# v0's ``merge_job_parameter_definitions`` returned a list of typed
# ``Job*ParameterDefinition`` pyclasses; each carried the per-template
# ``description: Optional[str]`` field copied straight from the
# template. The v1 binding flattens every variant to a dict, but the
# spec-listed keys (``name``, ``type``, ``source``, ``default``,
# ``objectType``, ``dataFlow``) **do not include** ``description`` —
# and the binding does not emit one. Downstream tooling that builds
# UI prompts ("show the user every parameter and ask for values")
# loses access to the per-parameter human-readable description.
#
# The underlying Rust crate's
# ``openjd_model::merge_job_parameter_definitions`` does not surface
# a description on the merged struct (only on the original
# ``JobParameterDefinition``). The v1 binding could either:
#  (a) add ``description`` to the merged dict by reading it back off
#      the originating template's ``parameter_definitions`` list, or
#  (b) document the omission in the spec and steer callers to read
#      the description off ``JobTemplate.parameter_definitions``.
#
# Cross-reference: report Recommendation #4.


@pytest.mark.xfail(strict=True, reason="v1 drops description; spec lists no description key")
def test_merge_includes_description() -> None:
    t = decode_job_template(
        template={
            "specificationVersion": "jobtemplate-2023-09",
            "name": "T",
            "parameterDefinitions": [
                {"name": "Count", "type": "INT", "default": 5, "description": "Number of frames"},
            ],
            "steps": [{"name": "S", "script": {"actions": {"onRun": {"command": "echo"}}}}],
        }
    )
    merged = merge_job_parameter_definitions(job_template=t)
    [count_def] = merged
    assert count_def.get("description") == "Number of frames"


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


@pytest.mark.parametrize("name", ["Any", "Optional", "Sequence", "Union", "re", "Enum"])
def test_no_internal_imports_leak_at_top_level(name: str) -> None:
    import openjd.model._v1 as v1

    assert not hasattr(v1, name), f"{name} leaks as a public attribute on openjd.model._v1"
