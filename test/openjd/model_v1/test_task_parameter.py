# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the typed task-parameter pyclasses returned by
``StepParameterSpace.taskParameterDefinitions``.

The five classes mirror the ``openjd_model::job::TaskParameter``
runtime enum 1:1:

* ``IntTaskParameter`` — ``range: list[int] | RangeExpr``
* ``FloatTaskParameter`` — ``range: list[float]``
* ``StringTaskParameter`` — ``range: list[str]``
* ``PathTaskParameter`` — ``range: list[str]``
* ``ChunkIntTaskParameter`` — ``range: list[int] | RangeExpr``,
  ``chunks: TaskChunksDefinition``

``IntTaskParameter`` deliberately does NOT carry a ``chunks`` field
even though the underlying Rust struct has
``chunks: Option<ResolvedChunks>`` — no resolver path ever produces
``Some(_)`` on the ``Int`` variant; chunks are exclusively a
``ChunkInt`` concern.

See ``reports/model-bindings-quality-evaluation-report.md`` Rec #6.
"""

import pickle

import pytest

from openjd.expr import RangeExpr
from openjd.model._v1 import (
    create_job,
    decode_job_template,
)
from openjd.model._v1.job import (
    ChunkIntTaskParameter,
    FloatTaskParameter,
    IntTaskParameter,
    PathTaskParameter,
    StringTaskParameter,
    TaskChunksDefinition,
)
from openjd.model._v1.types import (
    TaskParameterType,
)


def _decode_with_param(param_dict: dict):
    """Build a one-step template with the supplied
    ``taskParameterDefinitions`` entry and run it through
    ``decode_job_template`` + ``create_job``."""
    template = {
        "specificationVersion": "jobtemplate-2023-09",
        "name": "T",
        "steps": [
            {
                "name": "S",
                "parameterSpace": {"taskParameterDefinitions": [param_dict]},
                "script": {"actions": {"onRun": {"command": "echo"}}},
            }
        ],
    }
    t = decode_job_template(template=template)
    return create_job(job_template=t, job_parameter_values={})


def _decode_with_chunks(param_dict: dict, *, extensions=None):
    """Same as :func:`_decode_with_param` but for templates that need
    the TASK_CHUNKING extension."""
    template = {
        "specificationVersion": "jobtemplate-2023-09",
        "name": "T",
        "extensions": extensions or ["TASK_CHUNKING"],
        "steps": [
            {
                "name": "S",
                "parameterSpace": {"taskParameterDefinitions": [param_dict]},
                "script": {"actions": {"onRun": {"command": "echo"}}},
            }
        ],
    }
    t = decode_job_template(template=template, supported_extensions=extensions or ["TASK_CHUNKING"])
    return create_job(job_template=t, job_parameter_values={})


class TestIntTaskParameter:
    def test_decode_int_range_string(self) -> None:
        """``range: \"1-3\"`` (range-string syntax) becomes a ``RangeExpr``."""
        j = _decode_with_param({"name": "F", "type": "INT", "range": "1-3"})
        F = j.steps[0].parameterSpace.taskParameterDefinitions["F"]

        assert isinstance(F, IntTaskParameter)
        assert F.type == TaskParameterType.INT
        assert isinstance(F.range, RangeExpr)
        assert list(F.range) == [1, 2, 3]

    def test_decode_int_range_list(self) -> None:
        """``range: [1, 5, 10]`` becomes a Python ``list[int]``."""
        j = _decode_with_param({"name": "F", "type": "INT", "range": [1, 5, 10]})
        F = j.steps[0].parameterSpace.taskParameterDefinitions["F"]

        assert isinstance(F, IntTaskParameter)
        assert F.type == TaskParameterType.INT
        assert F.range == [1, 5, 10]

    def test_construct_from_python(self) -> None:
        """``IntTaskParameter`` can be constructed directly with
        either a list of ints or a ``RangeExpr``."""
        a = IntTaskParameter(range=[1, 2, 3])
        assert a.range == [1, 2, 3]
        assert a.type == TaskParameterType.INT

        b = IntTaskParameter(range=RangeExpr("1-10"))
        assert isinstance(b.range, RangeExpr)
        assert str(b.range) == "1-10"

    def test_no_chunks_attribute(self) -> None:
        """``IntTaskParameter`` deliberately omits the ``chunks``
        attribute — the Rust enum field always carries
        ``Option::None`` for this variant."""
        a = IntTaskParameter(range=[1])
        assert not hasattr(a, "chunks")

    def test_pickle_round_trip_list(self) -> None:
        a = IntTaskParameter(range=[1, 2, 3])
        loaded = pickle.loads(pickle.dumps(a))
        assert loaded == a

    def test_pickle_round_trip_range_expr(self) -> None:
        a = IntTaskParameter(range=RangeExpr("1-10:2"))
        loaded = pickle.loads(pickle.dumps(a))
        assert loaded == a

    def test_eq_distinguishes_list_and_range_expr(self) -> None:
        """Two parameters with the same numeric values but different
        carrier types (list vs RangeExpr) compare unequal — we treat
        the variant as part of the identity."""
        a = IntTaskParameter(range=[1, 2, 3])
        b = IntTaskParameter(range=RangeExpr("1-3"))
        assert a != b


class TestFloatTaskParameter:
    def test_decode_float_range(self) -> None:
        j = _decode_with_param({"name": "F", "type": "FLOAT", "range": ["1.5", "2.5", "3.5"]})
        F = j.steps[0].parameterSpace.taskParameterDefinitions["F"]

        assert isinstance(F, FloatTaskParameter)
        assert F.type == TaskParameterType.FLOAT
        assert F.range == [1.5, 2.5, 3.5]

    def test_construct_and_pickle(self) -> None:
        a = FloatTaskParameter(range=[1.0, 2.5, 3.14])
        assert a.type == TaskParameterType.FLOAT
        loaded = pickle.loads(pickle.dumps(a))
        assert loaded == a


class TestStringTaskParameter:
    def test_decode_string_range(self) -> None:
        j = _decode_with_param({"name": "F", "type": "STRING", "range": ["a", "b", "c"]})
        F = j.steps[0].parameterSpace.taskParameterDefinitions["F"]

        assert isinstance(F, StringTaskParameter)
        assert F.type == TaskParameterType.STRING
        assert F.range == ["a", "b", "c"]

    def test_construct_and_pickle(self) -> None:
        a = StringTaskParameter(range=["x", "y"])
        assert a.type == TaskParameterType.STRING
        loaded = pickle.loads(pickle.dumps(a))
        assert loaded == a


class TestPathTaskParameter:
    def test_decode_path_range(self) -> None:
        j = _decode_with_param({"name": "F", "type": "PATH", "range": ["/a/b", "/c/d"]})
        F = j.steps[0].parameterSpace.taskParameterDefinitions["F"]

        assert isinstance(F, PathTaskParameter)
        assert F.type == TaskParameterType.PATH
        assert F.range == ["/a/b", "/c/d"]

    def test_construct_and_pickle(self) -> None:
        a = PathTaskParameter(range=["/tmp/x"])
        assert a.type == TaskParameterType.PATH
        loaded = pickle.loads(pickle.dumps(a))
        assert loaded == a


class TestChunkIntTaskParameter:
    def test_decode_chunk_int(self) -> None:
        j = _decode_with_chunks(
            {
                "name": "F",
                "type": "CHUNK[INT]",
                "range": "1-10",
                "chunks": {
                    "defaultTaskCount": 2,
                    "rangeConstraint": "CONTIGUOUS",
                },
            }
        )
        F = j.steps[0].parameterSpace.taskParameterDefinitions["F"]

        assert isinstance(F, ChunkIntTaskParameter)
        assert F.type == TaskParameterType.CHUNK_INT
        assert isinstance(F.range, RangeExpr)
        assert isinstance(F.chunks, TaskChunksDefinition)
        assert F.chunks.default_task_count == 2
        assert F.chunks.target_runtime_seconds is None
        assert F.chunks.range_constraint == "CONTIGUOUS"

    def test_decode_chunk_int_with_target_runtime(self) -> None:
        j = _decode_with_chunks(
            {
                "name": "F",
                "type": "CHUNK[INT]",
                "range": "1-100",
                "chunks": {
                    "defaultTaskCount": 4,
                    "targetRuntimeSeconds": 60,
                    "rangeConstraint": "NONCONTIGUOUS",
                },
            }
        )
        F = j.steps[0].parameterSpace.taskParameterDefinitions["F"]
        assert F.chunks.target_runtime_seconds == 60
        assert F.chunks.range_constraint == "NONCONTIGUOUS"

    def test_construct_and_pickle(self) -> None:
        chunks = TaskChunksDefinition(default_task_count=4, range_constraint="CONTIGUOUS")
        a = ChunkIntTaskParameter(range=[1, 2, 3], chunks=chunks)
        assert a.type == TaskParameterType.CHUNK_INT
        assert a.chunks.default_task_count == 4

        loaded = pickle.loads(pickle.dumps(a))
        assert loaded == a


class TestTaskChunksDefinition:
    def test_construct_minimum(self) -> None:
        d = TaskChunksDefinition(default_task_count=1, range_constraint="CONTIGUOUS")
        assert d.default_task_count == 1
        assert d.target_runtime_seconds is None
        assert d.range_constraint == "CONTIGUOUS"

    def test_construct_full(self) -> None:
        d = TaskChunksDefinition(
            default_task_count=10,
            target_runtime_seconds=300,
            range_constraint="NONCONTIGUOUS",
        )
        assert d.default_task_count == 10
        assert d.target_runtime_seconds == 300
        assert d.range_constraint == "NONCONTIGUOUS"

    def test_invalid_range_constraint_raises(self) -> None:
        with pytest.raises(ValueError, match="range_constraint"):
            TaskChunksDefinition(default_task_count=1, range_constraint="bogus")

    def test_pickle_round_trip(self) -> None:
        d = TaskChunksDefinition(
            default_task_count=4,
            target_runtime_seconds=60,
            range_constraint="NONCONTIGUOUS",
        )
        loaded = pickle.loads(pickle.dumps(d))
        assert loaded == d

    def test_eq(self) -> None:
        a = TaskChunksDefinition(default_task_count=4, range_constraint="CONTIGUOUS")
        b = TaskChunksDefinition(default_task_count=4, range_constraint="CONTIGUOUS")
        c = TaskChunksDefinition(default_task_count=5, range_constraint="CONTIGUOUS")
        assert a == b
        assert a != c


class TestStepParameterSpaceTypedDict:
    """Regression of model report Rec #6: ``taskParameterDefinitions``
    returns typed pyclasses, not the previous serde-tagged dict shape."""

    def test_dict_value_is_typed_pyclass_not_dict(self) -> None:
        """The value at each name in
        ``StepParameterSpace.taskParameterDefinitions`` is a typed
        pyclass instance (one of the five ``*TaskParameter`` classes),
        not a serde-internal dict like
        ``{'int': {'range': {'rangeExpr': {...}}, 'chunks': None}}``.
        """
        j = _decode_with_param({"name": "F", "type": "INT", "range": "1-3"})
        F = j.steps[0].parameterSpace.taskParameterDefinitions["F"]

        assert not isinstance(F, dict)
        assert hasattr(F, "type")
        assert hasattr(F, "range")
        assert F.type == TaskParameterType.INT

    def test_multiple_definitions_dispatch_correctly(self) -> None:
        template = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "T",
            "steps": [
                {
                    "name": "S",
                    "parameterSpace": {
                        "taskParameterDefinitions": [
                            {"name": "I", "type": "INT", "range": "1-3"},
                            {"name": "F", "type": "FLOAT", "range": ["1.0", "2.0"]},
                            {"name": "S", "type": "STRING", "range": ["a", "b"]},
                            {"name": "P", "type": "PATH", "range": ["/a"]},
                        ]
                    },
                    "script": {"actions": {"onRun": {"command": "echo"}}},
                }
            ],
        }
        t = decode_job_template(template=template)
        j = create_job(job_template=t, job_parameter_values={})
        ps = j.steps[0].parameterSpace
        assert ps is not None
        defs = ps.taskParameterDefinitions

        assert isinstance(defs["I"], IntTaskParameter)
        assert isinstance(defs["F"], FloatTaskParameter)
        assert isinstance(defs["S"], StringTaskParameter)
        assert isinstance(defs["P"], PathTaskParameter)
