# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for ``StepParameterSpaceIterator`` over a directly-constructed
``StepParameterSpace``.

These tests build the parameter space pyclass without going through
``decode_job_template`` + ``create_job`` so they can exercise specific
combinations of typed task-parameter pyclasses
(``IntTaskParameter``, ``StringTaskParameter``, etc.) and combination
expressions in isolation.

The ``StepParameterSpace`` constructor accepts each task-parameter
definition as a dict literal of the form
``{type, range, [chunks]}`` matching the YAML/JSON template syntax.
"""

from typing import Any, Callable

import pytest

from openjd.expr import RangeExpr
from openjd.model._v1 import (
    create_job,
    decode_job_template,
)
from openjd.model._v1.job import (
    StepParameterSpace,
    StepParameterSpaceIterator,
)
from openjd.model._v1.types import (
    TaskParameterType,
    TaskParameterValue,
)


# Convenience constructor for a TaskParameterValue from a short type
# tag and a string value. The iterator yields TaskParameterValue
# instances so the expected-value table reads cleanly.
def _v(type: TaskParameterType, value: str) -> TaskParameterValue:
    return TaskParameterValue(type=type, value=value)


_INT = TaskParameterType.INT
_STRING = TaskParameterType.STRING
_FLOAT = TaskParameterType.FLOAT


# Helper builders for the dict-shaped task-parameter definitions that
# ``StepParameterSpace.__init__`` accepts. These mirror the YAML/JSON
# template syntax: ``{type: ..., range: ...}``.
def _int_list(values: list[int]) -> dict[str, Any]:
    return {"type": "INT", "range": [str(v) for v in values]}


def _int_range(expr: str) -> dict[str, Any]:
    return {"type": "INT", "range": RangeExpr(expr)}


def _string_list(values: list[str]) -> dict[str, Any]:
    return {"type": "STRING", "range": values}


def _chunk_int_adaptive(
    expr: str, default_task_count: int, target_runtime_seconds: int
) -> dict[str, Any]:
    return {
        "type": "CHUNK[INT]",
        "range": RangeExpr(expr),
        "chunks": {
            "defaultTaskCount": default_task_count,
            "targetRuntimeSeconds": target_runtime_seconds,
            "rangeConstraint": "CONTIGUOUS",
        },
    }


class TestStepParameterSpaceIterator:
    @pytest.mark.parametrize(
        "range_int_param",
        [
            pytest.param(_int_list([1, 2]), id="list"),
            pytest.param(_int_range("1-2"), id="range-expr"),
        ],
    )
    def test_names(self, range_int_param: dict[str, Any]) -> None:
        # GIVEN
        space = StepParameterSpace(
            taskParameterDefinitions={
                "Param1": range_int_param,
                "Param2": _string_list(["a", "b", "c"]),
            }
        )

        # WHEN
        it = StepParameterSpaceIterator(space=space)

        # THEN
        assert it.names == set(("Param1", "Param2"))

    def test_no_param_iteration(self) -> None:
        # GIVEN
        expected: list[dict[str, TaskParameterValue]] = [{}]
        # parameterSpace is None for steps with no task parameters
        template_data = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Job",
            "steps": [{"name": "step", "script": {"actions": {"onRun": {"command": "do thing"}}}}],
        }
        job_template = decode_job_template(template=template_data)
        job = create_job(job_template=job_template, job_parameter_values=dict())

        space = job.steps[0].parameterSpace

        # WHEN
        it = StepParameterSpaceIterator(space=space)

        # THEN
        assert list(it) == expected
        it.reset_iter()
        assert list(it) == expected

    def test_no_param_getelem(self) -> None:
        # GIVEN
        template_data = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Job",
            "steps": [{"name": "step", "script": {"actions": {"onRun": {"command": "do thing"}}}}],
        }
        job_template = decode_job_template(template=template_data)
        job = create_job(job_template=job_template, job_parameter_values=dict())

        space = job.steps[0].parameterSpace

        # WHEN
        it = StepParameterSpaceIterator(space=space)

        # THEN
        with pytest.raises(IndexError):
            it[1]
        with pytest.raises(IndexError):
            it[-2]
        empty: dict[str, TaskParameterValue] = {}
        assert it[0] == empty
        assert it[-1] == empty

        assert empty in it
        assert {"Param": _v(_INT, "3")} not in it
        assert {"Param": _v(_FLOAT, "3")} not in it

    @pytest.mark.parametrize(
        "range_int_param",
        [
            pytest.param(_int_list([1, 2]), id="list"),
            pytest.param(_int_range("1-2"), id="range-expr"),
        ],
    )
    def test_single_param_iteration(self, range_int_param: dict[str, Any]) -> None:
        # GIVEN
        expected = [1, 2]
        space = StepParameterSpace(
            taskParameterDefinitions={
                "Param1": range_int_param,
            }
        )

        # WHEN
        it = StepParameterSpaceIterator(space=space)

        # THEN
        for i in range(len(expected)):
            assert {"Param1": _v(_INT, str(expected[i]))} == next(it), f"i = {i}"
        with pytest.raises(StopIteration):
            next(it)
        # The chunks parameter is only relevant when the parameter space is
        # chunked.
        with pytest.raises(ValueError):
            it.chunks_default_task_count = 1

        assert {"Param1": _v(_INT, "1")} in it
        assert {"Param1": _v(_INT, "2")} in it
        assert {"Param1": _v(_INT, "x")} not in it

    @pytest.mark.parametrize(
        "param_range",
        [
            pytest.param([10], id="single"),
            pytest.param([10, 11, 12, 13, 14, 15], id="six"),
        ],
    )
    def test_single_param_getelem(self, param_range: list[int]) -> None:
        # GIVEN
        space = StepParameterSpace(
            taskParameterDefinitions={
                "Param1": _int_list(param_range),
            }
        )

        # WHEN
        it = StepParameterSpaceIterator(space=space)

        # THEN
        with pytest.raises(IndexError):
            it[len(param_range)]
        with pytest.raises(IndexError):
            it[-len(param_range) - 1]
        expected = [{"Param1": _v(_INT, str(v))} for v in param_range]
        assert [it[i] for i in range(0, len(param_range))] == expected
        expected_reversed = list(reversed(expected))
        assert [it[-i - 1] for i in range(0, len(param_range))] == expected_reversed

        for i in range(len(param_range)):
            assert expected[i] in it
        assert {"Param1": _v(_INT, "9")} not in it
        assert {"Param2": _v(_INT, "10")} not in it
        assert {
            "Param1": _v(_INT, "10"),
            "Param2": _v(_INT, "10"),
        } not in it
        assert {} not in it
        assert it.chunks_parameter_name is None

    @pytest.mark.parametrize(
        "range_param, expected_len",
        [
            pytest.param(_int_list([1, 2, 3]), 3, id="list-3"),
            pytest.param(_int_range("1-5"), 5, id="range-expr-5"),
            pytest.param(_int_list([0, 10, 20, 40]), 4, id="list-4"),
        ],
    )
    def test_single_param_len(self, range_param: dict[str, Any], expected_len: int) -> None:
        # GIVEN
        space = StepParameterSpace(
            taskParameterDefinitions={
                "Param1": range_param,
            }
        )

        # WHEN
        result = StepParameterSpaceIterator(space=space)

        # THEN
        assert len(result) == expected_len
        # Test twice. We do some caching of lengths. Test the caching flows.
        assert len(result) == expected_len

    @pytest.mark.parametrize(
        "range_int_param",
        [
            pytest.param(_int_list([1, 2]), id="list"),
            pytest.param(_int_range("1-2"), id="range-expr"),
        ],
    )
    def test_defaults_product(self, range_int_param: dict[str, Any]) -> None:
        # GIVEN
        space = StepParameterSpace(
            taskParameterDefinitions={
                "Param1": range_int_param,
                "Param2": _string_list(["a", "b"]),
            }
        )

        # WHEN
        it = StepParameterSpaceIterator(space=space)

        # THEN
        # The combination_expr should default to "Param1 * Param2"
        assert len(it) == 2 * 2
        element: Callable[[int, str], dict[str, TaskParameterValue]] = lambda p1, p2: {
            "Param1": _v(_INT, str(p1)),
            "Param2": _v(_STRING, str(p2)),
        }
        expected_values = (
            element(1, "a"),
            element(1, "b"),
            element(2, "a"),
            element(2, "b"),
        )
        assert expected_values == tuple(v for v in it)

        for value in expected_values:
            assert value in it
        assert element(1, "A") not in it
        assert element(1, "c") not in it
        assert element(0, "a") not in it
        assert element(3, "a") not in it
        assert {} not in it
        assert {
            "Param1": _v(_FLOAT, "1"),
            "Param2": _v(_STRING, "a"),
        } not in it

    def test_product_len(self) -> None:
        # GIVEN
        space = StepParameterSpace(
            taskParameterDefinitions={
                "Param1": _int_range("1-2:1"),
                "Param2": _string_list(["a", "b", "c"]),
                "Param3": _int_list([-1, -2]),
            },
            combination="Param1 * Param2 * Param3",
        )

        # WHEN
        result = StepParameterSpaceIterator(space=space)

        # THEN
        assert len(result) == 2 * 3 * 2
        # Test twice. We do some caching of lengths. Test the caching flows.
        assert len(result) == 2 * 3 * 2

    def test_associate_iteration(self) -> None:
        # GIVEN
        space = StepParameterSpace(
            taskParameterDefinitions={
                "Param1": _int_range("1-4"),
                "Param2": _string_list(["a", "b", "c", "d"]),
                "Param3": _int_list([-1, -2, -3, -4]),
            },
            combination="(Param1, Param2, Param3)",
        )

        # WHEN
        result = StepParameterSpaceIterator(space=space)

        # THEN
        element: Callable[[int, str, int], dict[str, TaskParameterValue]] = lambda p1, p2, p3: {
            "Param1": _v(_INT, str(p1)),
            "Param2": _v(_STRING, str(p2)),
            "Param3": _v(_INT, str(p3)),
        }
        expected_values = [
            element(1, "a", -1),
            element(2, "b", -2),
            element(3, "c", -3),
            element(4, "d", -4),
        ]
        assert expected_values == [v for v in result]

    def test_associate_len(self) -> None:
        # GIVEN
        space = StepParameterSpace(
            taskParameterDefinitions={
                "Param1": _int_list([1, 2, 3, 4]),
                "Param2": _string_list(["a", "b", "c", "d"]),
                "Param3": _int_range("-1--4:-1"),
            },
            combination="(Param1, Param2, Param3)",
        )

        # WHEN
        result = StepParameterSpaceIterator(space=space)

        # THEN
        assert len(result) == 4
        # Test twice. We do some caching of lengths. Test the caching flows.
        assert len(result) == 4

    def test_associate_getitem(self) -> None:
        # GIVEN
        space = StepParameterSpace(
            taskParameterDefinitions={
                "Param1": _int_range("1-4"),
                "Param2": _string_list(["a", "b", "c", "d"]),
                "Param3": _int_list([-1, -2, -3, -4]),
            },
            combination="(Param1, Param2, Param3)",
        )

        # WHEN
        it = StepParameterSpaceIterator(space=space)

        # THEN
        element: Callable[[int, str, int], dict[str, TaskParameterValue]] = lambda p1, p2, p3: {
            "Param1": _v(_INT, str(p1)),
            "Param2": _v(_STRING, str(p2)),
            "Param3": _v(_INT, str(p3)),
        }
        expected_values = [
            element(1, "a", -1),
            element(2, "b", -2),
            element(3, "c", -3),
            element(4, "d", -4),
        ]
        with pytest.raises(IndexError):
            it[len(expected_values)]
        with pytest.raises(IndexError):
            it[-len(expected_values) - 1]
        assert expected_values == [it[i] for i in range(0, len(expected_values))]
        expected_reversed = list(reversed(expected_values))
        assert expected_reversed == [it[-i - 1] for i in range(0, len(expected_values))]

        # Validate that __contains__ returns True for all values yielded.
        for v in it:
            assert v in it
        # Validate that __contains__ returns False for some values outside.
        assert element(5, "a", -1) not in it
        assert element(4, "d", -3) not in it
        assert element(2, "c", -2) not in it
        assert {} not in it
        assert {
            "Param1": _v(_INT, "4"),
            "Param2": _v(_STRING, "d"),
            "Param3": _v(_FLOAT, "-2"),
        } not in it

    def test_nested_expr_iteration(self) -> None:
        """A more deeply nested test to hit all of the recursive edge
        cases — namely, ensure that we hit the iterator resets in the
        implementation."""

        # GIVEN
        space = StepParameterSpace(
            taskParameterDefinitions={
                "Param1": _int_list([1, 2]),
                "Param2": _string_list(["a", "b", "c", "d"]),
                "Param3": _int_range("10-11"),
                "Param4": _int_list([20, 21]),
            },
            combination="Param1 * ( Param2, Param3 * Param4 )",
        )

        # WHEN
        it = StepParameterSpaceIterator(space=space)

        # THEN
        element: Callable[[int, str, int, int], dict[str, TaskParameterValue]] = (
            lambda p1, p2, p3, p4: {
                "Param1": _v(_INT, str(p1)),
                "Param2": _v(_STRING, str(p2)),
                "Param3": _v(_INT, str(p3)),
                "Param4": _v(_INT, str(p4)),
            }
        )
        expected_values = [
            element(1, "a", 10, 20),
            element(1, "b", 10, 21),
            element(1, "c", 11, 20),
            element(1, "d", 11, 21),
            element(2, "a", 10, 20),
            element(2, "b", 10, 21),
            element(2, "c", 11, 20),
            element(2, "d", 11, 21),
        ]
        assert expected_values == [v for v in it]

    def test_nested_expr_contains(self) -> None:
        """``__contains__`` recognises values yielded by an iterator
        over a nested combination expression. Regression test for
        report finding #2 (recursive
        ``AssociationNode::validate_containment`` projection)."""

        # GIVEN
        space = StepParameterSpace(
            taskParameterDefinitions={
                "Param1": _int_list([1, 2]),
                "Param2": _string_list(["a", "b", "c", "d"]),
                "Param3": _int_range("10-11"),
                "Param4": _int_list([20, 21]),
            },
            combination="Param1 * ( Param2, Param3 * Param4 )",
        )

        # WHEN
        it = StepParameterSpaceIterator(space=space)

        # THEN
        element: Callable[[int, str, int, int], dict[str, TaskParameterValue]] = (
            lambda p1, p2, p3, p4: {
                "Param1": _v(_INT, str(p1)),
                "Param2": _v(_STRING, str(p2)),
                "Param3": _v(_INT, str(p3)),
                "Param4": _v(_INT, str(p4)),
            }
        )
        for value in [
            element(1, "a", 10, 20),
            element(1, "b", 10, 21),
            element(1, "c", 11, 20),
            element(1, "d", 11, 21),
            element(2, "a", 10, 20),
            element(2, "b", 10, 21),
            element(2, "c", 11, 20),
            element(2, "d", 11, 21),
        ]:
            assert value in it
        assert element(1, "a", 10, 19) not in it
        assert element(1, "a", 10, 22) not in it
        assert element(0, "a", 10, 20) not in it
        assert {} not in it
        assert {
            "Param1": _v(_INT, "1"),
            "Param2": _v(_STRING, "c"),
            "Param3": _v(_STRING, "11"),  # wrong type for Param3
            "Param4": _v(_INT, "20"),
        } not in it

    def test_contains_self_yielded_values(self) -> None:
        """``__contains__`` must recognise the dict values the iterator
        just yielded — a frequently-used test idiom is
        ``for v in expected_values: assert v in it``."""

        # GIVEN
        space = StepParameterSpace(
            taskParameterDefinitions={
                "Frame": _int_range("1-3"),
            }
        )

        # WHEN
        it = StepParameterSpaceIterator(space=space)
        yielded = list(iter(it))

        # THEN
        assert len(yielded) == 3
        it.reset_iter()
        for v in yielded:
            assert v in it

    def test_chunks_default_task_count_setter_mutates_iterator(self) -> None:
        """The setter must actually mutate iterator state — adaptive
        chunking callers (e.g. the worker agent) need to be able to
        reduce or grow the chunk size at runtime."""

        # GIVEN: a CHUNK[INT] parameter with adaptive chunking
        # (defaultTaskCount + targetRuntimeSeconds).
        space = StepParameterSpace(
            taskParameterDefinitions={
                "F": _chunk_int_adaptive(
                    "1-100", default_task_count=10, target_runtime_seconds=120
                ),
            }
        )

        # WHEN
        it = StepParameterSpaceIterator(space=space)

        # THEN
        assert it.chunks_adaptive is True
        assert it.chunks_default_task_count == 10
        it.chunks_default_task_count = 5
        assert it.chunks_default_task_count == 5

    def test_len_raises_on_adaptive_chunking(self) -> None:
        """``__len__`` must raise ``ValueError`` on adaptive-chunked
        spaces — silently returning 0 would let callers mistake an
        adaptive space for an empty one."""

        # GIVEN
        space = StepParameterSpace(
            taskParameterDefinitions={
                "F": _chunk_int_adaptive(
                    "1-100", default_task_count=10, target_runtime_seconds=120
                ),
            }
        )

        # WHEN
        it = StepParameterSpaceIterator(space=space)

        # THEN
        assert it.chunks_adaptive is True
        with pytest.raises(ValueError, match="adaptive chunking"):
            len(it)


class TestChunkIntContains:
    """``__contains__`` must round-trip values yielded by a chunked
    iterator. The iterator yields ``TaskParameterValue`` instances
    whose ``value`` is a chunk-range string (e.g. ``"1-5"``) under
    ``TaskParameterType.CHUNK_INT``. When the value is fed back into
    a fresh iterator's ``__contains__`` check, the binding must
    parse the string as a ``RangeExpr`` (matching what the upstream
    ``validate_containment`` expects structurally) — a plain INT
    coercion produces an ``ExprValue::String`` that doesn't match
    and silently returns ``False``."""

    @staticmethod
    def _chunked_step() -> Any:
        # Build via decode + create so we exercise the full path
        # the worker agent / sessions hit at runtime.
        t = decode_job_template(
            template={
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
                                    "chunks": {
                                        "defaultTaskCount": 5,
                                        "rangeConstraint": "CONTIGUOUS",
                                    },
                                }
                            ]
                        },
                        "script": {
                            "actions": {
                                "onRun": {
                                    "command": "echo",
                                    "args": ["{{Task.Param.Frame}}"],
                                }
                            }
                        },
                    }
                ],
            },
            supported_extensions=["TASK_CHUNKING"],
        )
        j = create_job(job_template=t, job_parameter_values={})
        return j.steps[0]

    def test_yielded_chunks_round_trip(self) -> None:
        """Every value yielded by an iterator over a CHUNK[INT]
        space must report ``in fresh_iter`` as ``True``."""
        step = self._chunked_step()
        it = StepParameterSpaceIterator(step=step)
        fresh = StepParameterSpaceIterator(step=step)
        yielded = list(it)
        assert len(yielded) == 2  # 1-10 / 5-task default → 2 chunks
        for params in yielded:
            assert params in fresh, f"{params} should round-trip through __contains__ but didn't"

    def test_nonexistent_chunk_not_in_iter(self) -> None:
        """A chunk-range value that doesn't appear in the space
        must report ``in iter`` as ``False`` — confirms the fix
        doesn't accidentally return ``True`` for everything that
        parses as a ``RangeExpr``."""
        step = self._chunked_step()
        it = StepParameterSpaceIterator(step=step)
        # The space yields {1-5, 6-10}; 3-7 is a valid range but not
        # one of the canonical chunks.
        non_existing = {"Frame": TaskParameterValue(type=TaskParameterType.CHUNK_INT, value="3-7")}
        assert non_existing not in it

    def test_explicit_chunk_value_round_trip(self) -> None:
        """A user-constructed ``TaskParameterValue`` with a chunk
        string that *does* match a yielded chunk reports ``in iter``
        as ``True`` even when not obtained via iteration."""
        step = self._chunked_step()
        it = StepParameterSpaceIterator(step=step)
        # Construct fresh — this is the consumer use-case where a
        # caller wants to check whether a known chunk is in the space.
        existing = {"Frame": TaskParameterValue(type=TaskParameterType.CHUNK_INT, value="1-5")}
        assert existing in it
