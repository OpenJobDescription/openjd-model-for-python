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
decode/create functions, ``SpecificationRevision`` and
``TemplateSpecificationVersion`` (Rust pyclasses re-exported from
``openjd._openjd_rs``), and the ``RevisionExtensions`` legacy compat
wrapper — but does *not* re-export the structural pyclasses. Those
live in their respective submodules. Update imports at call sites,
e.g.::

    # Before
    from openjd.model._v1 import Job, Step, JobTemplate, JobParameterType

    # After
    from openjd.model._v1.template import JobTemplate
    from openjd.model._v1.job import Job, Step
    from openjd.model._v1.types import JobParameterType

Note: the v0 names ``ParameterValue`` and ``ParameterValueType`` are
*not* part of the v1 surface. Use ``JobParameterValue`` /
``JobParameterType`` (or ``TaskParameterValue`` / ``TaskParameterType``)
from ``openjd.model._v1.types`` instead. The previously-Python
``SpecificationRevision`` and ``TemplateSpecificationVersion`` classes
are now Rust pyclasses; their Python-side surface is unchanged
(lowercase variant names, ``.value``, equality with the spec-form
string), but ``isinstance(rev, str)`` returns ``False``.
"""

import re
from typing import Any, Optional, Sequence, Union


# ── Entry-point functions and a few cross-cutting types ──
#
# Top-level convenience: decode/create functions live here (they're not
# template-or-job-specific). ``CallerLimits`` is convenient at top-level
# because it's an argument to ``decode_job_template``. ``DocumentType``
# is referenced by ``document_string_to_object`` below.

from openjd._openjd_rs import (
    # Decode functions (raw)
    decode_job_template_dict,
    decode_environment_template_dict,
    decode_job_template_str as _rs_decode_job_template_str,
    decode_environment_template_str as _rs_decode_environment_template_str,
    # Job creation
    create_job,
    preprocess_job_parameters,
    merge_job_parameter_definitions,
    evaluate_let_bindings,
    # Used by document_string_to_object below
    DocumentType,
    # Used by decode_job_template signature
    CallerLimits,
    # Cross-cutting types — re-exported here for legacy callers
    # that still do ``from openjd.model._v1 import …``. The
    # canonical location is ``openjd.model._v1.types``. The Rust
    # pyclasses behave like ``str``-Enums (lowercase variant names,
    # ``.value`` returns the spec form, equality with str works).
    ModelProfile,
    SpecificationRevision,
    TemplateSpecificationVersion,
    # Used by capability validation (FormatString is also accessible
    # via ``openjd.expr``; pulled in early for use in
    # ``validate_*_capability_name``).
    FormatString,
)

# DecodeValidationError is needed internally by ``document_string_to_object``
# below (it converts YAML/JSON parse errors into ``DecodeValidationError``).
# Other error classes live in ``openjd.model._v1.errors`` and are not
# re-exported at the top level — import from ``.errors`` directly.
from openjd._openjd_rs import DecodeValidationError

# Types/template/job submodules — re-export so users can do:
#   from openjd.model._v1 import template, job, types, errors
from . import errors, job, template, types  # noqa: F401


# ── SpecificationRevision and TemplateSpecificationVersion ──
#
# These were Python ``str``-Enums in the v0 reference. The Rust
# pyclasses (imported above from ``openjd._openjd_rs``) now carry
# the same surface: lowercase variant names matching the v0
# convention (``SpecificationRevision.v2023_09``,
# ``TemplateSpecificationVersion.JOBTEMPLATE_v2023_09``), a
# ``.value`` getter that returns the spec form, equality with the
# spec-form string (``rev == "2023-09"`` is ``True``), a hash that
# matches the spec-form string's hash (so set / dict membership
# across the two types works), and ``TemplateSpecificationVersion``
# additionally accepts the spec form or the variant name in its
# constructor (``TemplateSpecificationVersion("jobtemplate-2023-09")``).
# The classes are *not* ``str`` subclasses; for code that needs a
# string, call ``str(rev)`` or ``rev.value``.


# ── Python-only types ──


class RevisionExtensions:
    """Tracks which extensions are active for a specification revision.

    Thin compat wrapper around ``ModelProfile`` for callers that still pass
    ``RevisionExtensions(spec_rev=..., supported_extensions=[...])``. New
    code should construct a ``ModelProfile`` directly.
    """

    def __init__(
        self,
        spec_rev: "SpecificationRevision | None" = None,
        revision: "SpecificationRevision | None" = None,
        supported_extensions: Optional[list] = None,
        extensions: Optional[set] = None,
    ):
        self.revision = spec_rev or revision or SpecificationRevision.v2023_09
        if supported_extensions is not None:
            self.extensions = set(supported_extensions)
        else:
            self.extensions = extensions or set()

    def to_profile(self) -> "ModelProfile":
        """Build the matching ``ModelProfile``."""
        return ModelProfile.from_strings(
            self.revision,
            sorted(str(e) for e in self.extensions),
        )


# Type aliases (Python-only, opaque dict shapes used by openjd-sessions)
JobParameterValues = dict  # dict[str, JobParameterValue] or dict[str, dict]
JobParameterInputValues = dict  # dict[str, str]
TaskParameterSet = dict  # dict[str, Any]
JobParameterDefinition = Any  # opaque from Rust (JobTemplate.parameter_definitions)
OpenJDModel = Any  # base class no longer needed


# ── Capability validation (Python side) ──
#
# Strict kw-only signatures matching the v0 reference's
# ``openjd.model._capabilities.validate_*_capability_name``. Returns
# ``None`` on success and raises ``ValueError`` on a malformed name.
# ``standard_capabilities`` is required (not optional) because the
# vendor-prefix check needs to know which names are "well-known"
# enough to bypass the prefix requirement.
#
# Behaviour notes (matching v0):
#
# * ``capability_name`` accepts either ``str`` or ``FormatString``.
#   A ``FormatString`` that contains expressions (``{{...}}``)
#   short-circuits — the substituted value is validated at
#   resolution time instead. A literal ``FormatString`` falls
#   through to the same regex / scope checks as a plain string.
# * Names are lower-cased before regex matching. The matching
#   regex is identical to v0:
#       ^(?:[a-z_][a-z0-9_]+:)?(?:amount|attr)(?:\.[a-z_][a-z0-9_]*)+$
# * Names without a vendor prefix that match a name in
#   ``standard_capabilities`` are accepted unconditionally.
# * Names without a vendor prefix that use a reserved scope
#   (``worker``, ``job``, ``step``, ``task``) and that are NOT in
#   ``standard_capabilities`` are rejected — those scopes are
#   reserved for OpenJD-defined capabilities.

_CAPABILITY_NAME_REGEX = re.compile(
    r"^(?:[a-z_][a-z0-9_]+:)?(?:amount|attr)(?:\.[a-z_][a-z0-9_]*)+$"
)
_RESERVED_SCOPES = ("worker", "job", "step", "task")


def _split_vendor(capability_name: str) -> tuple[str, str]:
    """Split ``vendor:name`` → ``(vendor, name)``. Returns
    ``("", capability_name)`` if there's no colon."""
    if ":" in capability_name:
        head, tail = capability_name.split(":", 1)
        return (head, tail)
    return ("", capability_name)


def _validate_capability_name(
    capability_name: "Union[str, FormatString]",
    standard_capabilities: Sequence[str],
    required_name_prefix: str,
) -> None:
    # Skip validation when the format string carries an unresolved
    # expression — the substituted value is validated at resolution
    # time instead.
    if isinstance(capability_name, FormatString):
        if not capability_name.is_literal():
            return
        capability_name = capability_name.raw()
    capability_name = capability_name.lower()
    if _CAPABILITY_NAME_REGEX.fullmatch(capability_name) is None:
        raise ValueError(f"Value is not a valid Capability name: {capability_name}")

    vendor, capability = _split_vendor(capability_name)
    if not vendor and capability in standard_capabilities:
        return

    if not capability.startswith(required_name_prefix):
        raise ValueError(
            f"Capability name after the vendor prefix must start with "
            f"'{required_name_prefix}': {capability_name}"
        )

    # Reserved scope check (worker / job / step / task) — only a
    # listed standard capability may use one of these scopes.
    scope = capability_name.split(".")[1]
    if scope in _RESERVED_SCOPES:
        raise ValueError(
            f"Only Open Job Description defined capabilities may start with "
            f"'{required_name_prefix}{scope}': {capability_name}"
        )


def validate_amount_capability_name(
    *,
    capability_name: "Union[str, FormatString]",
    standard_capabilities: Sequence[str],
) -> None:
    """Validate an ``amount.*`` capability name.

    Args:
        capability_name: A ``str`` or ``FormatString``. A
            ``FormatString`` containing unresolved expressions is
            accepted as-is (validation happens at resolution time).
        standard_capabilities: The set of OpenJD-defined amount
            capability names. Names without a vendor prefix are
            accepted unconditionally if they appear in this set;
            otherwise the reserved-scope check applies.

    Raises:
        ValueError: if ``capability_name`` is malformed, is missing
            the required ``amount.`` prefix, or uses a reserved
            scope without being a standard capability.
    """
    _validate_capability_name(capability_name, standard_capabilities, "amount.")


def validate_attribute_capability_name(
    *,
    capability_name: "Union[str, FormatString]",
    standard_capabilities: Sequence[str],
) -> None:
    """Validate an ``attr.*`` capability name. See
    :func:`validate_amount_capability_name` for full semantics."""
    _validate_capability_name(capability_name, standard_capabilities, "attr.")


# ── Standard capabilities ──

STANDARD_AMOUNT_CAPABILITIES: dict[str, dict] = {
    "amount.worker.vcpu": {},
    "amount.worker.memory": {},
    "amount.worker.gpu": {},
    "amount.worker.gpu.memory": {},
    "amount.worker.disk.scratch": {},
}

STANDARD_ATTRIBUTE_CAPABILITIES: dict[str, dict] = {
    "attr.worker.os.family": {"values": {"linux", "windows", "macos"}, "multivalued": False},
    "attr.worker.cpu.arch": {"values": {"x86_64", "arm64"}, "multivalued": False},
}


# ── Functions ──

try:
    from yaml import CSafeLoader as _YamlLoader
except ImportError:
    from yaml import SafeLoader as _YamlLoader  # type: ignore[assignment]


def document_string_to_object(
    *, document: str, document_type: "DocumentType | None" = None
) -> dict[str, Any]:
    """Parse a YAML or JSON document string into a Python dict."""
    import json as _json

    import yaml as _yaml

    try:
        if document_type == DocumentType.JSON:
            result = _json.loads(document)
        else:
            result = _yaml.load(document, Loader=_YamlLoader)
    except Exception as e:
        raise DecodeValidationError(str(e)) from e
    if not isinstance(result, dict):
        raise DecodeValidationError(
            f"Template must be a mapping/object, got {type(result).__name__}"
        )
    return result


def decode_job_template(
    *,
    template: dict[str, Any],
    supported_extensions: Optional[list[str]] = None,
    caller_limits: "Optional[CallerLimits]" = None,
) -> "template.JobTemplate":
    """Decode and validate a job template from a Python dict.

    Args:
        template: The decoded template mapping.
        supported_extensions: The caller's allowlist of OpenJD extension
            names. The template's ``extensions:`` field is validated
            against this list — any name in the template that is not
            both a recognized ``ModelExtension`` AND in this list is
            rejected with ``Unsupported extension names: ...``. Pass
            ``None`` (the default) for an empty allowlist (i.e., reject
            every extension the template requests).
        caller_limits: Optional ``CallerLimits`` to tighten spec-defined
            limits.

    Returns:
        The parsed ``openjd.model._v1.template.JobTemplate``. Use
        ``template.profile`` to access the ``ModelProfile`` describing
        the template's declared revision and extensions (a subset of
        ``supported_extensions``).
    """
    return decode_job_template_dict(
        template,
        supported_extensions=(
            list(supported_extensions) if supported_extensions is not None else None
        ),
        caller_limits=caller_limits,
    )


def decode_template(
    *,
    template: dict[str, Any],
    supported_extensions: Optional[list[str]] = None,
    caller_limits: "Optional[CallerLimits]" = None,
) -> "template.JobTemplate":
    """Deprecated alias for :func:`decode_job_template`.

    Mirrors the v0 / pure-Python reference's ``decode_template``,
    which is itself documented as deprecated. New code should call
    ``decode_job_template`` directly. Will be removed in a future
    release.
    """
    return decode_job_template(
        template=template,
        supported_extensions=supported_extensions,
        caller_limits=caller_limits,
    )


def decode_environment_template(
    *,
    template: dict[str, Any],
    supported_extensions: Optional[list[str]] = None,
) -> "template.EnvironmentTemplate":
    """Decode and validate an environment template from a Python dict.

    See ``decode_job_template`` for ``supported_extensions`` semantics.
    Environment templates do not accept caller limits.
    """
    return decode_environment_template_dict(
        template,
        supported_extensions=(
            list(supported_extensions) if supported_extensions is not None else None
        ),
    )


def decode_job_template_str(
    document: str,
    format: DocumentType = DocumentType.YAML,
    *,
    supported_extensions: Optional[list[str]] = None,
    caller_limits: "Optional[CallerLimits]" = None,
) -> "template.JobTemplate":
    """Decode and validate a job template from a YAML or JSON string.

    Parses ``document`` as a YAML (default) or JSON document, then
    validates it the same way :func:`decode_job_template` does. This is
    a convenience wrapper around the dict-shaped entry point — pass
    ``DocumentType.JSON`` to force JSON parsing instead of the
    YAML-superset default.

    Args:
        document: The template source as a YAML or JSON string.
        format: Document type. Defaults to ``DocumentType.YAML``
            (which is also a superset of JSON).
        supported_extensions: The caller's allowlist of OpenJD
            extension names; see :func:`decode_job_template`.
        caller_limits: Optional :class:`CallerLimits` to tighten
            spec-defined limits.

    Returns:
        The parsed :class:`openjd.model._v1.template.JobTemplate`.
    """
    return _rs_decode_job_template_str(
        document,
        format,
        supported_extensions=(
            list(supported_extensions) if supported_extensions is not None else None
        ),
        caller_limits=caller_limits,
    )


def decode_environment_template_str(
    document: str,
    format: DocumentType = DocumentType.YAML,
    *,
    supported_extensions: Optional[list[str]] = None,
) -> "template.EnvironmentTemplate":
    """Decode and validate an environment template from a YAML or JSON string.

    Parses ``document`` as a YAML (default) or JSON document, then
    validates it the same way :func:`decode_environment_template` does.

    Args:
        document: The template source as a YAML or JSON string.
        format: Document type. Defaults to ``DocumentType.YAML``
            (which is also a superset of JSON).
        supported_extensions: The caller's allowlist of OpenJD
            extension names; see :func:`decode_job_template`.

    Returns:
        The parsed :class:`openjd.model._v1.template.EnvironmentTemplate`.
        Environment templates do not accept caller limits.
    """
    return _rs_decode_environment_template_str(
        document,
        format,
        supported_extensions=(
            list(supported_extensions) if supported_extensions is not None else None
        ),
    )


# All v0 compatibility shims have been removed. v0 callers should
# stay on ``openjd.model``; v1 callers should import structural types
# from their canonical submodules:
#
#   * ``openjd.model._v1.template``  (template-time pyclasses)
#   * ``openjd.model._v1.job``       (job-time pyclasses, EmbeddedFile,
#                                     StepDependencyEdge, etc.)
#   * ``openjd.model._v1.types``     (cross-cutting types)
#   * ``openjd.model._v1.errors``    (exception classes)
#   * ``openjd.expr``                (FormatString, SymbolTable,
#                                     RangeExpr, ExpressionError)


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
    "decode_template",
    "document_string_to_object",
    "evaluate_let_bindings",
    "merge_job_parameter_definitions",
    "preprocess_job_parameters",
    # Capability validation (Python-only)
    "validate_amount_capability_name",
    "validate_attribute_capability_name",
    "STANDARD_AMOUNT_CAPABILITIES",
    "STANDARD_ATTRIBUTE_CAPABILITIES",
    # Spec-revision pyclass enums (re-exported from openjd._openjd_rs)
    "SpecificationRevision",
    "TemplateSpecificationVersion",
    # Python-only compat classes
    "RevisionExtensions",
    # Opaque type aliases
    "JobParameterDefinition",
    "JobParameterInputValues",
    "JobParameterValues",
    "OpenJDModel",
    "TaskParameterSet",
    # Used by decode_job_template signature (re-exported from .types)
    "CallerLimits",
    "DocumentType",
    "ModelProfile",
    # Version
    "version",
)
