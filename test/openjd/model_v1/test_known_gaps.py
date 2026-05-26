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
from openjd.model._v1.errors import DecodeValidationError


# ── Empty-steps validation raises ModelValidationError, not DecodeValidationError ──
#
# v0 raises ``DecodeValidationError`` for templates whose ``steps:`` list
# is empty. v1 raises ``ModelValidationError``. The two classes are
# siblings under ``ValueError`` (not parent-child), so callers that did
#
#     except DecodeValidationError:
#         ...handle malformed template...
#
# in their v0 code stop catching this case under v1. ``except
# ValueError`` covers both, but the spec promises both classes are
# decode/validation paths and v0 / v1 should agree on which one fires
# for a structurally invalid template.
#
# Fix path: ``rust-bindings/src/model/errors.rs::model_err_to_py``
# already has both arms — ``ModelError::ModelValidation`` →
# ``PyModelValidationError`` and ``ModelError::DecodeValidation`` →
# ``PyDecodeValidationError``. The upstream Rust validator
# (`openjd_model::template::validation::validate_job_template`) is
# producing ``ModelError::ModelValidation`` for a structural-decode
# failure that the v0 reference treated as a decode error. Either
# remap the empty-steps case to ``DecodeValidation`` upstream, or
# document the class change in
# ``specs/python-model-interface.md``.
#
# Cross-reference: report Recommendation #1.


@pytest.mark.xfail(
    strict=True, reason="v1 raises ModelValidationError; v0 raised DecodeValidationError"
)
def test_empty_steps_raises_decode_validation_error_like_v0() -> None:
    template = {
        "specificationVersion": "jobtemplate-2023-09",
        "name": "T",
        "steps": [],
    }
    with pytest.raises(DecodeValidationError):
        decode_job_template(template=template)


# ── JobTemplate.specification_version is incomparable to TemplateSpecificationVersion ──
#
# Spec ("Output Types (from Rust, opaque)") and the
# ``TemplateSpecificationVersion`` enum block both promise:
#
#     template.specification_version    # TemplateSpecificationVersion enum
#     ...
#     TSV.JOBTEMPLATE_v2023_09          # "jobtemplate-2023-09"
#
# i.e. the value off the template should be comparable to the public
# str-Enum. In practice ``JobTemplate.specification_version`` is the
# Rust pyclass enum (``openjd._openjd_rs.TemplateSpecificationVersion``,
# variant ``JOBTEMPLATE_2023_09`` — note: no leading ``v``), while
# ``v1.TemplateSpecificationVersion`` is the Python str-Enum shim
# (variant ``JOBTEMPLATE_v2023_09``). The two are different classes
# with different variant identities, so equality is always ``False``.
#
# v0 returned the Python str-Enum directly off the template, so
# ``t.specificationVersion == TemplateSpecificationVersion.JOBTEMPLATE_v2023_09``
# was True. v1 silently breaks this idiom.
#
# Fix path: have ``rust-bindings/src/model/template.rs::specification_version``
# convert the underlying ``TemplateSpecificationVersion`` to the Python
# str-Enum value using the shim (or expose a ``.matches()`` helper on
# the Rust enum). Alternatively, drop the Python str-Enum shim entirely
# and have ``v1.TemplateSpecificationVersion`` re-export the Rust class
# (with renamed variants for parity), so there is only one
# ``TemplateSpecificationVersion`` class.
#
# Cross-reference: report Recommendation #2.


@pytest.mark.xfail(
    strict=True,
    reason="v1 returns Rust enum, not the Python str-Enum that v1.TemplateSpecificationVersion exposes",
)
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


# ── Top-level package leaks typing imports ──
#
# ``openjd.model._v1.__init__.py`` imports ``Any``, ``Optional``,
# ``Sequence``, ``Union`` from ``typing``, ``Enum`` from ``enum``, and
# ``re`` for the capability-name regex. None of these are prefixed
# with ``_`` and none are listed in ``__all__``, but plain attribute
# access (``openjd.model._v1.Optional``) still resolves them. That's
# a leak: tooling that walks the public attribute set of the module
# (``inspect.getmembers``, ``hasattr``-based discovery, IDE
# completion) treats them as part of the public surface.
#
# v0 had the same issue at one point and resolved it by aliasing
# imports with ``_`` prefixes (``import re as _re``, ``from typing
# import Any as _Any``, …). The v1 binding should follow the same
# convention.
#
# Cross-reference: report Recommendation #5.


@pytest.mark.parametrize("name", ["Any", "Optional", "Sequence", "Union", "Enum", "re"])
@pytest.mark.xfail(strict=True, reason="internal typing imports leak as public attributes")
def test_no_internal_imports_leak_at_top_level(name: str) -> None:
    import openjd.model._v1 as v1

    assert not hasattr(v1, name), f"{name} leaks as a public attribute on openjd.model._v1"


# ── StepDependencyGraph.topo_sorted() spec example mismatches reality ──
#
# Spec ("Iteration Types (from Rust)" → "StepDependencyGraph") shows:
#
#     graph.topo_sorted()         # ["Render", "Composite"] — dependency order
#     graph.step_names()          # ["Render", "Composite"]
#
# implying both return strings. In reality ``topo_sorted()`` returns
# a list of ``Step`` objects (matching the underlying Rust crate's
# ``StepDependencyGraph::topo_sorted`` semantics), and only
# ``step_names()`` returns strings.
#
# This is a spec-vs-binding mismatch in the spec, not a binding bug
# — but it is the same kind of drift the eval-bindings skill is
# designed to catch. Either the spec example needs to read
# ``[Step(name="Render"), Step(name="Composite")]`` (or call
# ``step_names()`` instead), or the binding needs to change to
# return strings (which would be a regression vs the underlying Rust
# semantics).
#
# Recommended resolution: update the spec, since downstream consumers
# (worker agent, openjd-cli) need the ``Step`` objects to drive task
# scheduling.
#
# Cross-reference: report Recommendation #7.


@pytest.mark.xfail(
    strict=True, reason="spec example shows strings but binding returns Step objects (spec doc bug)"
)
def test_topo_sorted_returns_strings_per_spec_example() -> None:
    """The spec example for ``StepDependencyGraph.topo_sorted()``
    suggests strings (``["Render", "Composite"]``). The actual
    binding returns ``Step`` objects. Pin the spec's literal claim
    so when this xfail flips to xpass the spec — or this assertion
    — gets updated.
    """
    from openjd.model._v1 import create_job
    from openjd.model._v1.job import StepDependencyGraph

    t = decode_job_template(
        template={
            "specificationVersion": "jobtemplate-2023-09",
            "name": "T",
            "steps": [
                {"name": "A", "script": {"actions": {"onRun": {"command": "echo"}}}},
                {
                    "name": "B",
                    "script": {"actions": {"onRun": {"command": "ls"}}},
                    "dependencies": [{"dependsOn": "A"}],
                },
            ],
        }
    )
    job = create_job(job_template=t, job_parameter_values={})
    graph = StepDependencyGraph(job=job)
    result = graph.topo_sorted()
    # Spec example claims a list of strings.
    assert all(
        isinstance(x, str) for x in result
    ), f"spec promises strings; got {[type(x).__name__ for x in result]}"
