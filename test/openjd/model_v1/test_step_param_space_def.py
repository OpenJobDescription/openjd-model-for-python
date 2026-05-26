# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the typed ``StepParameterSpaceDefinition`` pyclasses
returned by ``StepTemplate.parameter_space``.

Mirror the runtime ``openjd_model::template::TaskParameterDefinition``
enum 1:1:

* ``IntTaskParameterDefinition`` — ``range: list[int] | FormatString``
* ``FloatTaskParameterDefinition`` — ``range: list[float | FormatString] | FormatString``
* ``StringTaskParameterDefinition`` — ``range: list[FormatString] | FormatString``
* ``PathTaskParameterDefinition`` — ``range: list[FormatString] | FormatString``
* ``ChunkIntTaskParameterDefinition`` — ``range``, plus
  ``chunks: ChunksDefinition``

Plus ``ChunksDefinition`` for the chunks payload (mirrors
``openjd_model::template::ChunksDefinition``):

* ``default_task_count: int | FormatString``
* ``target_runtime_seconds: Optional[int | FormatString]``
* ``range_constraint: 'CONTIGUOUS' | 'NONCONTIGUOUS'``

See report finding #11 (`StepTemplate.parameter_space` exposure).
"""

from openjd.expr import FormatString
from openjd.model._v1 import decode_job_template
from openjd.model._v1.template import (
    ChunkIntTaskParameterDefinition,
    ChunksDefinition,
    FloatTaskParameterDefinition,
    IntTaskParameterDefinition,
    PathTaskParameterDefinition,
    StepParameterSpaceDefinition,
    StringTaskParameterDefinition,
)


def _decode_step(parameter_space=None, *, extensions=None):
    """Build a one-step template with the supplied ``parameterSpace``
    block and run it through ``decode_job_template``.

    Returns the parsed ``StepTemplate``.
    """
    template = {
        "specificationVersion": "jobtemplate-2023-09",
        "name": "T",
        "steps": [
            {
                "name": "S",
                "script": {"actions": {"onRun": {"command": "echo"}}},
            }
        ],
    }
    if parameter_space is not None:
        template["steps"][0]["parameterSpace"] = parameter_space
    if extensions:
        template["extensions"] = list(extensions)
    t = decode_job_template(
        template=template,
        supported_extensions=list(extensions) if extensions else None,
    )
    return t.steps[0]


# ── Empty / missing parameter_space ──


class TestParameterSpaceAccessor:
    def test_no_parameter_space(self) -> None:
        """A step without a ``parameterSpace`` field has
        ``step.parameter_space is None`` (and the camelCase alias)."""
        step = _decode_step()
        assert step.parameter_space is None
        assert step.parameterSpace is None

    def test_minimal_parameter_space(self) -> None:
        """A minimal parameterSpace returns a typed
        ``StepParameterSpaceDefinition`` with one definition and no
        explicit combination."""
        step = _decode_step(
            {
                "taskParameterDefinitions": [
                    {"name": "F", "type": "INT", "range": [1, 2, 3]},
                ]
            }
        )
        ps = step.parameter_space
        assert isinstance(ps, StepParameterSpaceDefinition)
        assert ps.combination is None
        defs = ps.task_parameter_definitions
        assert len(defs) == 1
        assert isinstance(defs[0], IntTaskParameterDefinition)

    def test_combination_string(self) -> None:
        """The ``combination`` getter returns the raw string
        unchanged."""
        step = _decode_step(
            {
                "taskParameterDefinitions": [
                    {"name": "A", "type": "INT", "range": [1, 2]},
                    {"name": "B", "type": "STRING", "range": ["x", "y"]},
                ],
                "combination": "A * B",
            }
        )
        assert step.parameter_space.combination == "A * B"

    def test_camelcase_alias(self) -> None:
        """``taskParameterDefinitions`` is a camelCase alias for
        ``task_parameter_definitions``."""
        step = _decode_step(
            {
                "taskParameterDefinitions": [
                    {"name": "F", "type": "INT", "range": [1, 2, 3]},
                ]
            }
        )
        ps = step.parameter_space
        assert len(ps.taskParameterDefinitions) == len(ps.task_parameter_definitions)


# ── Per-variant tests ──


class TestIntTaskParameterDefinition:
    def test_list_range(self) -> None:
        """Integer literal list is exposed as a Python ``list[int]``."""
        step = _decode_step(
            {
                "taskParameterDefinitions": [
                    {"name": "F", "type": "INT", "range": [1, 2, 3]},
                ]
            }
        )
        d = step.parameter_space.task_parameter_definitions[0]
        assert isinstance(d, IntTaskParameterDefinition)
        assert d.name == "F"
        assert d.type == "INT"
        assert d.range == [1, 2, 3]

    def test_range_expression_string(self) -> None:
        """``range: "1-10:2"`` (range-expression-string syntax) is
        exposed as a ``FormatString``. Under the EXPR extension, it
        could carry a ``{{Param.X}}`` interpolation; here it's a
        literal range expression, but the carrier type is the same."""
        step = _decode_step(
            {
                "taskParameterDefinitions": [
                    {"name": "F", "type": "INT", "range": "1-10:2"},
                ]
            }
        )
        d = step.parameter_space.task_parameter_definitions[0]
        assert isinstance(d, IntTaskParameterDefinition)
        assert isinstance(d.range, FormatString)
        assert d.range.raw() == "1-10:2"


class TestFloatTaskParameterDefinition:
    def test_list_of_literals(self) -> None:
        step = _decode_step(
            {
                "taskParameterDefinitions": [
                    {"name": "F", "type": "FLOAT", "range": [1.5, 2.5, 3.5]},
                ]
            }
        )
        d = step.parameter_space.task_parameter_definitions[0]
        assert isinstance(d, FloatTaskParameterDefinition)
        assert d.type == "FLOAT"
        assert d.range == [1.5, 2.5, 3.5]

    def test_list_with_format_string(self) -> None:
        """``FloatRangeItem`` is a union — list elements can be
        either literals (Python ``float``) or ``FormatString``s."""
        step = _decode_step(
            extensions=["EXPR"],
            parameter_space={
                "taskParameterDefinitions": [
                    {
                        "name": "F",
                        "type": "FLOAT",
                        "range": [1.5, "{{Param.X}}", 3.5],
                    },
                ],
            },
        )
        d = step.parameter_space.task_parameter_definitions[0]
        items = d.range
        assert items[0] == 1.5
        assert isinstance(items[1], FormatString)
        assert items[1].raw() == "{{Param.X}}"
        assert items[2] == 3.5


class TestStringTaskParameterDefinition:
    def test_list_of_format_strings(self) -> None:
        """STRING list elements are always ``FormatString`` (they may
        carry interpolation expressions)."""
        step = _decode_step(
            {
                "taskParameterDefinitions": [
                    {"name": "F", "type": "STRING", "range": ["a", "b", "c"]},
                ]
            }
        )
        d = step.parameter_space.task_parameter_definitions[0]
        assert isinstance(d, StringTaskParameterDefinition)
        assert d.type == "STRING"
        assert all(isinstance(v, FormatString) for v in d.range)
        assert [v.raw() for v in d.range] == ["a", "b", "c"]


class TestPathTaskParameterDefinition:
    def test_list_of_format_strings(self) -> None:
        """PATH list elements are ``FormatString`` (same shape as
        STRING but the parameter type tag differs)."""
        step = _decode_step(
            {
                "taskParameterDefinitions": [
                    {"name": "F", "type": "PATH", "range": ["/a", "/b"]},
                ]
            }
        )
        d = step.parameter_space.task_parameter_definitions[0]
        assert isinstance(d, PathTaskParameterDefinition)
        assert d.type == "PATH"
        assert [v.raw() for v in d.range] == ["/a", "/b"]


class TestChunkIntTaskParameterDefinition:
    def test_minimal_chunks(self) -> None:
        """A ``CHUNK[INT]`` parameter exposes both ``range`` and a
        typed ``ChunksDefinition`` for the chunks payload."""
        step = _decode_step(
            extensions=["TASK_CHUNKING"],
            parameter_space={
                "taskParameterDefinitions": [
                    {
                        "name": "F",
                        "type": "CHUNK[INT]",
                        "range": "1-100",
                        "chunks": {
                            "defaultTaskCount": 4,
                            "rangeConstraint": "CONTIGUOUS",
                        },
                    }
                ]
            },
        )
        d = step.parameter_space.task_parameter_definitions[0]
        assert isinstance(d, ChunkIntTaskParameterDefinition)
        assert d.type == "CHUNK[INT]"
        assert d.name == "F"
        assert isinstance(d.range, FormatString)
        chunks = d.chunks
        assert isinstance(chunks, ChunksDefinition)
        assert chunks.default_task_count == 4
        assert chunks.target_runtime_seconds is None
        assert chunks.range_constraint == "CONTIGUOUS"

    def test_chunks_with_target_runtime(self) -> None:
        """``targetRuntimeSeconds`` and a ``NONCONTIGUOUS`` constraint
        round-trip through the typed pyclass surface."""
        step = _decode_step(
            extensions=["TASK_CHUNKING"],
            parameter_space={
                "taskParameterDefinitions": [
                    {
                        "name": "F",
                        "type": "CHUNK[INT]",
                        "range": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                        "chunks": {
                            "defaultTaskCount": 4,
                            "targetRuntimeSeconds": 60,
                            "rangeConstraint": "NONCONTIGUOUS",
                        },
                    }
                ]
            },
        )
        d = step.parameter_space.task_parameter_definitions[0]
        chunks = d.chunks
        assert chunks.default_task_count == 4
        assert chunks.target_runtime_seconds == 60
        assert chunks.range_constraint == "NONCONTIGUOUS"
        # camelCase aliases
        assert chunks.defaultTaskCount == 4
        assert chunks.targetRuntimeSeconds == 60
        assert chunks.rangeConstraint == "NONCONTIGUOUS"

    def test_chunks_with_format_string_default_task_count(self) -> None:
        """``defaultTaskCount`` accepts a format string under the
        EXPR extension; it's exposed as ``FormatString`` rather than
        an ``int``."""
        step = _decode_step(
            extensions=["TASK_CHUNKING", "EXPR"],
            parameter_space={
                "taskParameterDefinitions": [
                    {
                        "name": "F",
                        "type": "CHUNK[INT]",
                        "range": "1-100",
                        "chunks": {
                            "defaultTaskCount": "{{Param.ChunkSize}}",
                            "rangeConstraint": "CONTIGUOUS",
                        },
                    }
                ]
            },
        )
        d = step.parameter_space.task_parameter_definitions[0]
        chunks = d.chunks
        assert isinstance(chunks.default_task_count, FormatString)
        assert chunks.default_task_count.raw() == "{{Param.ChunkSize}}"


# ── Mixed dispatch ──


class TestMultipleVariants:
    def test_dispatch_correctly(self) -> None:
        """A parameterSpace with all 5 variants in one definition
        list dispatches each element to the correct typed pyclass."""
        step = _decode_step(
            extensions=["TASK_CHUNKING"],
            parameter_space={
                "taskParameterDefinitions": [
                    {"name": "I", "type": "INT", "range": [1, 2]},
                    {"name": "F", "type": "FLOAT", "range": [1.5]},
                    {"name": "S", "type": "STRING", "range": ["x"]},
                    {"name": "P", "type": "PATH", "range": ["/a"]},
                    {
                        "name": "C",
                        "type": "CHUNK[INT]",
                        "range": "1-10",
                        "chunks": {
                            "defaultTaskCount": 2,
                            "rangeConstraint": "CONTIGUOUS",
                        },
                    },
                ]
            },
        )
        defs = step.parameter_space.task_parameter_definitions
        assert isinstance(defs[0], IntTaskParameterDefinition)
        assert isinstance(defs[1], FloatTaskParameterDefinition)
        assert isinstance(defs[2], StringTaskParameterDefinition)
        assert isinstance(defs[3], PathTaskParameterDefinition)
        assert isinstance(defs[4], ChunkIntTaskParameterDefinition)
