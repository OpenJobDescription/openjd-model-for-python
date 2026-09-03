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

from typing import Any, Callable, Optional

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


class TestFloatRangeSpellingIsPreserved:
    """A FLOAT range element given as a ``str`` keeps the decimal places it was
    written with, so the value reaching a command line is the one the caller asked
    for (Template Schemas §7.5, openjd-rs#354).

    ``StepParameterSpace`` builds the *resolved* space directly, without the
    ``decode_job_template`` + ``create_job`` path, so it is its own route to a
    ``Float64`` and has to make the same choice: the template's range element is a
    ``<float> | <floatstring>`` union, and only the string member carries a
    spelling. Before openjd-model 0.6.0 there was no spelling to carry -- the
    resolved range was ``Vec<f64>`` -- so this could not be observed.
    """

    @staticmethod
    def _rendered(elements: list[Any]) -> list[str]:
        space = StepParameterSpace(
            taskParameterDefinitions={"F": {"type": "FLOAT", "range": elements}}
        )
        return [params["F"].value for params in StepParameterSpaceIterator(space=space)]

    @pytest.mark.parametrize(
        "element,expected",
        [
            ("1.50", "1.50"),  # the trailing zero is the requested scale
            ("3.500", "3.500"),
            ("1e3", "1e3"),  # exponent notation is not expanded
            ("1E+2", "1E+2"),
            ("5.", "5."),  # no digit is invented after the point
            (".5", ".5"),  # nor before it
            ("0.50", "0.50"),
            ("-0.00", "0.00"),  # zero has no sign, but keeps its places
            # The last two do not pin the fix -- both render the same without it, and
            # both survive the mutant that reverts it. Kept as controls: canonical text
            # must not change, and padded text must still be trimmed (it took the
            # string path already, because Rust's `f64` parse rejects the spaces).
            ("2.5", "2.5"),
            ("  2.50  ", "2.50"),
        ],
    )
    def test_a_string_element_keeps_its_spelling(self, element: str, expected: str) -> None:
        assert self._rendered([element]) == [expected]

    @pytest.mark.parametrize("element,expected", [(1.5, "1.5"), (1000.0, "1000.0"), (0.5, "0.5")])
    def test_a_float_element_renders_as_the_number(self, element: float, expected: str) -> None:
        """The negative control. A Python ``float`` is the union's ``<float>`` member and
        has no spelling to keep, so it must not acquire one from ``str()`` -- these are
        the values where preserving the text would have been indistinguishable from
        rendering the number, and they must stay that way."""
        assert self._rendered([element]) == [expected]

    def test_it_matches_what_the_template_path_renders(self) -> None:
        """The two routes to a resolved space agree, which is the point of the fix:
        before it, this space rendered ``1.5`` where the template rendered ``1.50``."""
        elements = ["1.50", "1e3", "5.", ".5", "2.5"]
        template = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "T",
            "steps": [
                {
                    "name": "S",
                    "parameterSpace": {
                        "taskParameterDefinitions": [
                            {"name": "F", "type": "FLOAT", "range": elements}
                        ]
                    },
                    "script": {
                        "actions": {"onRun": {"command": "echo", "args": ["{{Task.Param.F}}"]}}
                    },
                }
            ],
        }
        step = create_job(
            job_template=decode_job_template(template=template), job_parameter_values={}
        ).steps[0]
        from_template = [params["F"].value for params in StepParameterSpaceIterator(step=step)]
        assert self._rendered(elements) == from_template == elements

    def test_a_redundant_leading_zero_is_not_stripped_here(self) -> None:
        """The one place the two routes still differ, and deliberately. Stripping a
        redundant leading zero is a ``create_job`` normalization (openjd-model
        ``create_job/ranges.rs``), not part of reading a resolved value, so the
        template path renders ``2.50`` while a value handed straight to the resolved
        type keeps the ``0``. Constructing the Rust ``TaskParameter`` directly behaves
        the same way, because ``Float64``'s deserializer trims whitespace and unsigns
        zero but does not strip.
        """
        assert self._rendered(["02.50"]) == ["02.50"]

    def test_an_unparseable_element_is_still_rejected(self) -> None:
        """Forwarding the text rather than a number must not turn a bad element into an
        accepted one; it fails in ``Float64``'s deserializer instead of here."""
        with pytest.raises(ValueError, match="not-a-float"):
            self._rendered(["not-a-float"])


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


class TestChunksTaskCountOverride:
    """``chunks_task_count_override`` re-chunks a space at the caller's granularity.

    Before this existed, a *statically* chunked space could only be walked at the
    template's own ``defaultTaskCount``: the ``chunks_default_task_count`` setter
    accepts adaptive spaces only. Consumers that store one task per chunk value —
    the reason the pure-Python reference has this argument — had no way to expand a
    static space through the binding.
    """

    @staticmethod
    def _step(chunks: dict[str, Any], *, range: str = "1-10") -> Any:
        """A single CHUNK[INT] step, built through decode + create_job so the test
        exercises the same path a consumer hits at runtime."""
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
                                    "range": range,
                                    "chunks": chunks,
                                }
                            ]
                        },
                        "script": {
                            "actions": {
                                "onRun": {"command": "echo", "args": ["{{Task.Param.Frame}}"]}
                            }
                        },
                    }
                ],
            },
            supported_extensions=["TASK_CHUNKING"],
        )
        return create_job(job_template=t, job_parameter_values={}).steps[0]

    _STATIC = {"defaultTaskCount": 5, "rangeConstraint": "CONTIGUOUS"}
    _ADAPTIVE = {"defaultTaskCount": 5, "targetRuntimeSeconds": 60, "rangeConstraint": "CONTIGUOUS"}

    @staticmethod
    def _frames(it: Any) -> list:
        return [params["Frame"].value for params in it]

    def test_static_space_without_override_yields_template_chunks(self) -> None:
        """The baseline the override changes: 1-10 at 5 per chunk is two chunks."""
        it = StepParameterSpaceIterator(step=self._step(self._STATIC))
        assert self._frames(it) == ["1-5", "6-10"]

    def test_static_space_with_override_1_yields_individual_tasks(self) -> None:
        """The case the argument exists for, and the one that was unreachable."""
        it = StepParameterSpaceIterator(step=self._step(self._STATIC), chunks_task_count_override=1)
        assert self._frames(it) == [f"{n}-{n}" for n in range(1, 11)]

    def test_len_counts_the_overridden_granularity(self) -> None:
        """``len()`` is the observable proof the override reached the space: the same
        template counts 2 without it and 10 with it."""
        step = self._step(self._STATIC)
        assert len(StepParameterSpaceIterator(step=step)) == 2
        assert len(StepParameterSpaceIterator(step=step, chunks_task_count_override=1)) == 10

    def test_indexing_observes_the_override(self) -> None:
        """``__getitem__`` builds a fresh iterator, so it has to carry the override too,
        or indexing reports chunks iteration never yields.

        Uses NONCONTIGUOUS because random access needs a non-sequential space, and a
        CONTIGUOUS chunked space is always sequential (see the test below).
        """
        it = StepParameterSpaceIterator(
            step=self._step({"defaultTaskCount": 5, "rangeConstraint": "NONCONTIGUOUS"}),
            chunks_task_count_override=1,
        )
        yielded = self._frames(it)
        assert yielded == [str(n) for n in range(1, 11)]
        # Without the override carried through, index 0 would be the template's first
        # chunk, "1-5", and disagree with what iteration produced.
        fresh = StepParameterSpaceIterator(
            step=self._step({"defaultTaskCount": 5, "rangeConstraint": "NONCONTIGUOUS"}),
            chunks_task_count_override=1,
        )
        assert fresh[0]["Frame"].value == yielded[0]
        assert fresh[9]["Frame"].value == yielded[-1]
        assert fresh[-1]["Frame"].value == yielded[-1]

    def test_a_contiguous_space_supports_indexing_with_or_without_the_override(self) -> None:
        """openjd-model 0.6.0 (openjd-rs#355) gave a contiguous chunked space random
        access, so ``get`` now answers where it used to decline. Promoted from
        ``test_known_gaps.py::test_a_contiguous_chunked_space_supports_indexing``,
        which pinned the v0 reading as a strict xfail.

        Indexing observes the override, same as the NONCONTIGUOUS case above, and the
        end of the space is still an ``IndexError``.
        """
        it = StepParameterSpaceIterator(step=self._step(self._STATIC))
        assert [it[0]["Frame"].value, it[1]["Frame"].value, it[-1]["Frame"].value] == [
            "1-5",
            "6-10",
            "6-10",
        ]
        with pytest.raises(IndexError) as excinfo:
            _ = it[2]
        assert str(excinfo.value) == "index out of range"

        overridden = StepParameterSpaceIterator(
            step=self._step(self._STATIC), chunks_task_count_override=1
        )
        assert [overridden[0]["Frame"].value, overridden[-1]["Frame"].value] == ["1-1", "10-10"]

    def test_an_adaptive_space_still_refuses_indexing(self) -> None:
        """The negative control for the test above, and the remaining limitation
        recorded in ``specs/python-model-interface.md``: an adaptive space has no
        knowable count, so ``len()`` raises and every index is out of range. Iteration
        still yields, which is what distinguishes "unknown count" from "empty"."""
        it = StepParameterSpaceIterator(step=self._step(self._ADAPTIVE))
        assert it.chunks_adaptive is True
        for index in (0, -1):
            with pytest.raises(IndexError) as excinfo:
                _ = it[index]
            assert str(excinfo.value) == "index out of range"
        assert self._frames(StepParameterSpaceIterator(step=self._step(self._ADAPTIVE))) == [
            "1-5",
            "6-10",
        ]

    @pytest.mark.parametrize(
        "chunks,override,expected_count",
        [
            # Statically chunked: no override involved, the template's own size.
            ({"defaultTaskCount": 5, "rangeConstraint": "CONTIGUOUS"}, None, 5),
            # Statically chunked, re-chunked by the override.
            ({"defaultTaskCount": 5, "rangeConstraint": "CONTIGUOUS"}, 1, 1),
            # Adaptive, turned static by the override, which becomes the size.
            (
                {
                    "defaultTaskCount": 5,
                    "targetRuntimeSeconds": 60,
                    "rangeConstraint": "CONTIGUOUS",
                },
                1,
                1,
            ),
        ],
        ids=["static", "static-overridden", "adaptive-overridden"],
    )
    def test_chunk_metadata_is_reported_for_a_non_adaptive_space(
        self, chunks: dict[str, Any], override: Optional[int], expected_count: int
    ) -> None:
        """openjd-model 0.6.0 (openjd-rs#355) reports ``chunks_parameter_name`` and
        ``chunks_default_task_count`` for any chunked space, not only an adaptive one,
        which is what the v0 reference has always done. Promoted from
        ``test_known_gaps.py``, where it was a strict xfail."""
        it = StepParameterSpaceIterator(
            step=self._step(chunks), chunks_task_count_override=override
        )
        assert it.chunks_adaptive is False
        assert it.chunks_parameter_name == "Frame"
        assert it.chunks_default_task_count == expected_count

    def test_an_intermediate_override_regroups_the_chunks(self) -> None:
        """Not just 1: any positive size regroups the space."""
        it = StepParameterSpaceIterator(step=self._step(self._STATIC), chunks_task_count_override=2)
        assert self._frames(it) == ["1-2", "3-4", "5-6", "7-8", "9-10"]

    def test_override_turns_adaptive_chunking_off(self) -> None:
        """Matches the pure-Python reference: supplying the override makes the
        parameter static, which is also what makes ``len()`` answerable — an
        adaptive space raises on ``len()`` because the count is not yet knowable."""
        adaptive = StepParameterSpaceIterator(step=self._step(self._ADAPTIVE))
        assert adaptive.chunks_adaptive is True
        with pytest.raises(ValueError) as excinfo:
            len(adaptive)
        assert (
            str(excinfo.value)
            == "Length is not available because the parameter space uses adaptive chunking."
        )

        overridden = StepParameterSpaceIterator(
            step=self._step(self._ADAPTIVE), chunks_task_count_override=1
        )
        assert overridden.chunks_adaptive is False
        assert len(overridden) == 10
        assert self._frames(overridden) == [f"{n}-{n}" for n in range(1, 11)]

    def test_a_non_positive_override_is_rejected_even_when_it_would_be_ignored(self) -> None:
        """The validation runs before the space is inspected, so an unchunked space still
        rejects 0 rather than silently discarding it. The reference does not validate at
        all; this is the documented divergence, pinned so it stays deliberate."""
        space = StepParameterSpace(
            taskParameterDefinitions={"Frame": {"type": "INT", "range": [1, 2, 3]}}
        )
        with pytest.raises(ValueError) as excinfo:
            StepParameterSpaceIterator(space=space, chunks_task_count_override=0)
        assert str(excinfo.value) == "chunks_task_count_override must be a positive integer."

    def test_override_is_ignored_when_the_space_has_no_chunked_parameter(self) -> None:
        """Reference behaviour: the override only applies to a space that chunks."""
        space = StepParameterSpace(
            taskParameterDefinitions={"Frame": {"type": "INT", "range": [1, 2, 3]}}
        )
        it = StepParameterSpaceIterator(space=space, chunks_task_count_override=1)
        assert [params["Frame"].value for params in it] == ["1", "2", "3"]
        assert it.chunks_default_task_count is None
        assert it.chunks_parameter_name is None

    @pytest.mark.parametrize("override", [0, -1, -5])
    def test_a_non_positive_override_is_rejected_as_a_value_error(self, override: int) -> None:
        """openjd-model clamps the override to at least 1, so 0 would silently mean 1, and
        the ``chunks_default_task_count`` setter already refuses 0.

        Negatives report the same ``ValueError`` rather than the ``OverflowError`` an
        unsigned extraction would raise, so one ``except ValueError`` covers every
        non-positive input.
        """
        with pytest.raises(ValueError) as excinfo:
            StepParameterSpaceIterator(
                step=self._step(self._STATIC), chunks_task_count_override=override
            )
        assert str(excinfo.value) == "chunks_task_count_override must be a positive integer."

    def test_the_setter_still_refuses_a_static_space(self) -> None:
        """The override does not replace the setter, and must not loosen it: the
        setter mutates a live adaptive iterator, which a static space cannot do."""
        it = StepParameterSpaceIterator(step=self._step(self._STATIC))
        with pytest.raises(ValueError) as excinfo:
            it.chunks_default_task_count = 1
        assert str(excinfo.value) == (
            "The parameter space does not use adaptive chunking, "
            "so cannot modify chunks_default_task_count."
        )

    def test_yielded_values_round_trip_through_contains(self) -> None:
        """An overridden chunk must still satisfy containment, so a consumer can
        validate a task it was handed."""
        step = self._step(self._STATIC)
        it = StepParameterSpaceIterator(step=step, chunks_task_count_override=1)
        fresh = StepParameterSpaceIterator(step=step, chunks_task_count_override=1)
        for params in list(it):
            assert params in fresh
