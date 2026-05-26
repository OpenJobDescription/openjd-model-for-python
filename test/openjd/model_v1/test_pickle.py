# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Pickle round-trip tests for the ``openjd.model._v1`` value types.

The Group A enums (``DocumentType``, ``JobParameterType``, ``TaskParameterType``,
``ModelExtension``, ``SpecificationRevision``, ``TemplateSpecificationVersion``)
and Group B value types (``ModelProfile``, ``CallerLimits``, ``ValidationContext``,
``JobParameterValue``, ``TaskParameterValue``) all support pickle.

The decoded model containers (``JobTemplate``, ``Job``, ``Step``, etc.) do
not yet — see ``reports/model-bindings-quality-evaluation-report.md``
recommendation #8 for the planned approach.

Note: ``SpecificationRevision`` and ``TemplateSpecificationVersion`` are
shadowed by Python ``Enum`` shims in ``openjd.model._v1`` for backward
compatibility. The Rust pyclasses report ``__module__ ==
"openjd._openjd_rs"`` so pickle resolves them via the extension module
rather than through the wrapper. Users accessing the wrapper Enum
(``openjd.model._v1.SpecificationRevision.v2023_09``) get the Python
``str``-Enum, which has always been pickleable.
"""

import pickle

import pytest


# ── Group A: enums ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "value",
    [
        "openjd._openjd_rs.DocumentType.YAML",
        "openjd._openjd_rs.DocumentType.JSON",
        "openjd._openjd_rs.JobParameterType.STRING",
        "openjd._openjd_rs.JobParameterType.INT",
        "openjd._openjd_rs.JobParameterType.FLOAT",
        "openjd._openjd_rs.JobParameterType.PATH",
        "openjd._openjd_rs.JobParameterType.BOOL",
        "openjd._openjd_rs.JobParameterType.RANGE_EXPR",
        "openjd._openjd_rs.JobParameterType.LIST_STRING",
        "openjd._openjd_rs.JobParameterType.LIST_INT",
        "openjd._openjd_rs.JobParameterType.LIST_LIST_INT",
        "openjd._openjd_rs.TaskParameterType.INT",
        "openjd._openjd_rs.TaskParameterType.FLOAT",
        "openjd._openjd_rs.TaskParameterType.STRING",
        "openjd._openjd_rs.TaskParameterType.PATH",
        "openjd._openjd_rs.TaskParameterType.CHUNK_INT",
        "openjd._openjd_rs.SpecificationRevision.v2023_09",
        "openjd._openjd_rs.ModelExtension.TASK_CHUNKING",
        "openjd._openjd_rs.ModelExtension.REDACTED_ENV_VARS",
        "openjd._openjd_rs.ModelExtension.FEATURE_BUNDLE_1",
        "openjd._openjd_rs.ModelExtension.EXPR",
        "openjd._openjd_rs.TemplateSpecificationVersion.JOBTEMPLATE_v2023_09",
        "openjd._openjd_rs.TemplateSpecificationVersion.ENVIRONMENT_v2023_09",
    ],
)
def test_enum_round_trip(value):
    """Each enum value round-trips back to itself.

    The parametrize ``id`` strings tell pytest what the test name is and
    also document which symbol is under test in the failure summary.
    """
    module_path, attr = value.rsplit(".", 1)
    cls_path, cls = module_path.rsplit(".", 1)
    import importlib

    module = importlib.import_module(cls_path)
    enum_cls = getattr(module, cls)
    v = getattr(enum_cls, attr)
    loaded = pickle.loads(pickle.dumps(v))
    assert loaded == v
    # Most are enum singletons — check identity too.
    assert loaded is v


def test_task_parameter_type_hashable_for_dict_keys():
    """``TaskParameterType`` is now hashable; can be used as a dict key
    and round-trips through pickle."""
    from openjd._openjd_rs import TaskParameterType

    d = {
        TaskParameterType.INT: 1,
        TaskParameterType.STRING: "two",
        TaskParameterType.CHUNK_INT: [3, 4],
    }
    loaded = pickle.loads(pickle.dumps(d))
    assert loaded == d


def test_job_parameter_type_in_set():
    """``JobParameterType`` was already hashable; verify pickle round-trips
    through a set."""
    from openjd._openjd_rs import JobParameterType

    s = {JobParameterType.STRING, JobParameterType.INT, JobParameterType.LIST_PATH}
    loaded = pickle.loads(pickle.dumps(s))
    assert loaded == s


# ── Group B: value types ─────────────────────────────────────────


def test_model_profile_round_trip_default():
    from openjd._openjd_rs import ModelProfile, SpecificationRevision

    p = ModelProfile(SpecificationRevision.v2023_09)
    loaded = pickle.loads(pickle.dumps(p))
    assert loaded.revision == p.revision
    assert loaded.extensions == p.extensions


def test_model_profile_round_trip_with_extensions():
    from openjd._openjd_rs import ModelExtension, ModelProfile, SpecificationRevision

    p = ModelProfile(
        SpecificationRevision.v2023_09,
        extensions=[ModelExtension.EXPR, ModelExtension.TASK_CHUNKING],
    )
    loaded = pickle.loads(pickle.dumps(p))
    assert loaded.revision == p.revision
    assert sorted(e.name for e in loaded.extensions) == sorted(e.name for e in p.extensions)


def test_caller_limits_round_trip_default():
    from openjd._openjd_rs import CallerLimits

    limits = CallerLimits()
    loaded = pickle.loads(pickle.dumps(limits))
    assert loaded.max_step_count is None
    assert loaded.max_template_size is None


def test_caller_limits_round_trip_populated():
    from openjd._openjd_rs import CallerLimits

    limits = CallerLimits(
        max_step_count=10,
        max_env_count=5,
        max_task_count=1_000_000,
        max_step_script_size=2048,
        max_environment_size=1024,
        max_template_size=4096,
    )
    loaded = pickle.loads(pickle.dumps(limits))
    assert loaded.max_step_count == 10
    assert loaded.max_env_count == 5
    assert loaded.max_task_count == 1_000_000
    assert loaded.max_step_script_size == 2048
    assert loaded.max_environment_size == 1024
    assert loaded.max_template_size == 4096


def test_validation_context_round_trip():
    from openjd._openjd_rs import (
        CallerLimits,
        ModelExtension,
        ModelProfile,
        SpecificationRevision,
        ValidationContext,
    )

    profile = ModelProfile(SpecificationRevision.v2023_09, extensions=[ModelExtension.EXPR])
    limits = CallerLimits(max_step_count=10)
    ctx = ValidationContext(profile, caller_limits=limits)
    loaded = pickle.loads(pickle.dumps(ctx))
    assert loaded.profile.revision == profile.revision
    assert loaded.caller_limits.max_step_count == 10


def test_job_parameter_value_round_trip():
    from openjd._openjd_rs import JobParameterType, JobParameterValue

    v = JobParameterValue(type=JobParameterType.INT, value="42")
    loaded = pickle.loads(pickle.dumps(v))
    assert loaded == v
    assert loaded.value == "42"


def test_task_parameter_value_round_trip():
    from openjd._openjd_rs import TaskParameterType, TaskParameterValue

    v = TaskParameterValue(type=TaskParameterType.STRING, value="hello")
    loaded = pickle.loads(pickle.dumps(v))
    assert loaded == v
    assert loaded.value == "hello"


# ── Equality + hashability invariants ──────────────────────────


def test_document_type_hashable():
    """``DocumentType`` is hashable so it can be used as a dict key
    or set member alongside the other enum-shaped pyclasses
    (``JobParameterType``, ``TaskParameterType``,
    ``SpecificationRevision``)."""
    from openjd.model._v1.types import DocumentType

    # Self-consistent: same variant hashes to the same value.
    assert hash(DocumentType.YAML) == hash(DocumentType.YAML)
    assert hash(DocumentType.JSON) == hash(DocumentType.JSON)

    # Distinct variants hash distinctly.
    assert hash(DocumentType.YAML) != hash(DocumentType.JSON)

    # Usable as a set member and dict key.
    s = {DocumentType.YAML, DocumentType.JSON}
    assert len(s) == 2
    d = {DocumentType.YAML: "y", DocumentType.JSON: "j"}
    assert d[DocumentType.YAML] == "y"


def test_model_profile_equality_after_pickle():
    """``ModelProfile`` round-trips through pickle and the loaded
    instance compares equal to the original via ``__eq__``. Pinned
    for parity with the spec's "Pickle Support" claim that pickled
    state ``compares equal to the original``."""
    from openjd._openjd_rs import ModelExtension, ModelProfile, SpecificationRevision

    p = ModelProfile(
        SpecificationRevision.v2023_09,
        extensions=[ModelExtension.EXPR, ModelExtension.TASK_CHUNKING],
    )
    loaded = pickle.loads(pickle.dumps(p))
    assert loaded == p


def test_model_profile_equality_negative():
    """Different profiles compare unequal — confirms ``__eq__``
    isn't accidentally trivial."""
    from openjd._openjd_rs import ModelExtension, ModelProfile, SpecificationRevision

    p_a = ModelProfile(SpecificationRevision.v2023_09, extensions=[ModelExtension.EXPR])
    p_b = ModelProfile(SpecificationRevision.v2023_09, extensions=[ModelExtension.TASK_CHUNKING])
    p_c = ModelProfile(SpecificationRevision.v2023_09)
    assert p_a != p_b
    assert p_a != p_c


def test_caller_limits_equality_after_pickle():
    from openjd._openjd_rs import CallerLimits

    limits = CallerLimits(
        max_step_count=10,
        max_env_count=5,
        max_task_count=1_000_000,
        max_step_script_size=2048,
        max_environment_size=1024,
        max_template_size=4096,
    )
    loaded = pickle.loads(pickle.dumps(limits))
    assert loaded == limits


def test_caller_limits_equality_negative():
    """Different caller-limits configurations compare unequal."""
    from openjd._openjd_rs import CallerLimits

    a = CallerLimits(max_step_count=10)
    b = CallerLimits(max_step_count=20)
    c = CallerLimits()
    assert a != b
    assert a != c


def test_validation_context_equality_after_pickle():
    from openjd._openjd_rs import (
        CallerLimits,
        ModelExtension,
        ModelProfile,
        SpecificationRevision,
        ValidationContext,
    )

    ctx = ValidationContext(
        ModelProfile(SpecificationRevision.v2023_09, extensions=[ModelExtension.EXPR]),
        caller_limits=CallerLimits(max_step_count=10),
    )
    loaded = pickle.loads(pickle.dumps(ctx))
    assert loaded == ctx


def test_validation_context_equality_negative():
    """Two contexts with different profiles or different caller
    limits compare unequal."""
    from openjd._openjd_rs import (
        CallerLimits,
        ModelExtension,
        ModelProfile,
        SpecificationRevision,
        ValidationContext,
    )

    profile_a = ModelProfile(SpecificationRevision.v2023_09, extensions=[ModelExtension.EXPR])
    profile_b = ModelProfile(SpecificationRevision.v2023_09)
    ctx_a = ValidationContext(profile_a, caller_limits=CallerLimits(max_step_count=10))
    ctx_b = ValidationContext(profile_b, caller_limits=CallerLimits(max_step_count=10))
    ctx_c = ValidationContext(profile_a, caller_limits=CallerLimits(max_step_count=99))
    assert ctx_a != ctx_b  # different profile
    assert ctx_a != ctx_c  # different caller limits
