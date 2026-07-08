# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Open Job Description Model — backed by Rust bindings.

This package mirrors the structure of the underlying ``openjd_model`` Rust
crate:

* ``openjd.model._v1.template`` — template-time types (``JobTemplate``,
  ``EnvironmentTemplate``, etc.). Returned by ``decode_*_template``.
* ``openjd.model._v1.job`` — job-time types (``Job``, ``Step``, ``Action``,
  ``Environment``, ``StepParameterSpace``, the typed task-parameter
  pyclasses, etc.). Returned by ``create_job``.
* ``openjd.model._v1.types`` — cross-cutting types (``JobParameterType``,
  ``TaskParameterType``, ``ModelProfile``, ``CallerLimits``,
  ``ValidationContext``, ``DocumentType``, etc.).
* ``openjd.model._v1.errors`` — exception classes raised by
  ``decode_*`` and ``create_job``.

This top-level module re-exports the package's *entry points* — the
decode/create functions and the cross-cutting types
``SpecificationRevision``, ``TemplateSpecificationVersion``,
``ModelProfile``, ``CallerLimits``, and ``DocumentType`` — but does
*not* re-export the structural pyclasses. Those live in their
respective submodules.
"""

# ── Entry-point functions and a few cross-cutting types ──
#
# Top-level convenience: decode/create functions live here (they're not
# template-or-job-specific). ``CallerLimits`` is convenient at top-level
# because it's an argument to ``decode_job_template``. ``DocumentType``
# is an argument to ``decode_job_template_str`` and
# ``decode_environment_template_str``.

from openjd._openjd_rs import (
    # Decode entry points (the `_str` variants take a YAML/JSON
    # string, the un-suffixed forms take a Python dict; doc strings
    # propagate from the Rust source via PyO3 `///` comments).
    decode_job_template,
    decode_job_template_str,
    decode_environment_template,
    decode_environment_template_str,
    # Job creation
    create_job,
    preprocess_job_parameters,
    merge_job_parameter_definitions,
    evaluate_let_bindings,
    # Used by decode_*_template_str signatures
    DocumentType,
    # Used by decode_job_template signature
    CallerLimits,
    # Cross-cutting types — first-class entry points exposed at
    # the top level so callers can write
    # ``from openjd.model._v1 import SpecificationRevision`` etc.
    # without descending into ``.types``. ``SpecificationRevision``
    # and ``TemplateSpecificationVersion`` are Rust pyclass enums
    # that behave like ``str``-Enums (lowercase variant names,
    # ``.value`` returns the spec form, equality with str works).
    ModelProfile,
    SpecificationRevision,
    TemplateSpecificationVersion,
)

# Types/template/job submodules — re-export so users can do:
#   from openjd.model._v1 import template, job, types, errors
from . import errors, job, template, types  # noqa: F401

# ── Python-only types ──


# ── Capability validation ──
#
# All five capability functions are direct re-exports of the Rust
# pyfunctions in ``openjd._openjd_rs`` — no Python wrapper. The
# validators do the full check (length, regex, reserved-scope,
# standard-name short-circuit). They take a plain ``str`` as the
# capability name; callers with an unresolved-expression
# ``FormatString`` should defer the call themselves (template-time
# capability-name validation is done inside the Rust template
# validator already).

from openjd._openjd_rs import (
    standard_amount_capability_names,
    standard_attribute_capabilities,
    standard_attribute_capability_names,
    validate_amount_capability_name,
    validate_attribute_capability_name,
)


from .._version import version  # noqa: E402

__all__ = (
    # Submodules
    "errors",
    "job",
    "template",
    "types",
    # Decode + create entry points
    "create_job",
    "decode_environment_template",
    "decode_environment_template_str",
    "decode_job_template",
    "decode_job_template_str",
    "evaluate_let_bindings",
    "merge_job_parameter_definitions",
    "preprocess_job_parameters",
    # Capability validation
    "validate_amount_capability_name",
    "validate_attribute_capability_name",
    # Standard-capability lookups
    "standard_amount_capability_names",
    "standard_attribute_capability_names",
    "standard_attribute_capabilities",
    # Spec-revision pyclass enums (re-exported from openjd._openjd_rs)
    "SpecificationRevision",
    "TemplateSpecificationVersion",
    # Used by decode_job_template signature (re-exported from .types)
    "CallerLimits",
    "DocumentType",
    "ModelProfile",
    # Version
    "version",
)
