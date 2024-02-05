# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Callable, Union

import pytest

from openjd.model import (
    ParameterValue,
    ParameterValueType,
    StepParameterSpaceIterator,
    create_job,
    parse_model,
)

from openjd.model.v2023_09 import JobTemplate as JobTemplate_2023_09
from openjd.model.v2023_09 import (
    RangeExpressionTaskParameterDefinition as RangeExpressionTaskParameterDefinition_2023_09,
)
from openjd.model.v2023_09 import (
    RangeListTaskParameterDefinition as RangeListTaskParameterDefinition_2023_09,
)
from openjd.model.v2023_09 import (
    StepParameterSpace as StepParameterSpace_2023_09,
)

RangeTaskParameter = Union[
    RangeListTaskParameterDefinition_2023_09, RangeExpressionTaskParameterDefinition_2023_09
]


class TestStepParameterSpaceIterator_2023_09:  # noqa: N801
    @pytest.mark.parametrize(
        "range_int_param",
        [
            RangeListTaskParameterDefinition_2023_09(type=ParameterValueType.INT, range=[1, 2]),
            RangeExpressionTaskParameterDefinition_2023_09(
                type=ParameterValueType.INT, range="1-2"
            ),
        ],
    )
    def test_names(self, range_int_param):
        # GIVEN
        space = StepParameterSpace_2023_09(
            taskParameterDefinitions={
                "Param1": range_int_param,
                "Param2": RangeListTaskParameterDefinition_2023_09(
                    type=ParameterValueType.STRING, range=["a", "b", "c"]
                ),
            }
        )

        # WHEN
        result = StepParameterSpaceIterator(space=space)

        # THEN
        assert result.names == set(("Param1", "Param2"))

    def test_no_param_iteration(self):
        # GIVEN
        expected = [{}]
        # The parameter space is None in the mdoel when there are no parameters
        template_data = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Job",
            "steps": [{"name": "step", "script": {"actions": {"onRun": {"command": "do thing"}}}}],
        }
        job_template = parse_model(model=JobTemplate_2023_09, obj=template_data)
        job = create_job(job_template=job_template, job_parameter_values=dict())

        space = job.steps[0].parameterSpace
        iterator = StepParameterSpaceIterator(space=space)

        # WHEN
        result = list(iterator)

        # THEN
        assert result == expected

    def test_no_param_getelem(self):
        # GIVEN
        # The parameter space in a job with no task parameters
        template_data = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Job",
            "steps": [{"name": "step", "script": {"actions": {"onRun": {"command": "do thing"}}}}],
        }
        job_template = parse_model(model=JobTemplate_2023_09, obj=template_data)
        job = create_job(job_template=job_template, job_parameter_values=dict())

        space = job.steps[0].parameterSpace

        # WHEN
        result = StepParameterSpaceIterator(space=space)

        # THEN
        with pytest.raises(IndexError):
            result[1]
        with pytest.raises(IndexError):
            result[-2]
        expected = {}
        assert result[0] == expected
        assert result[-1] == expected

    @pytest.mark.parametrize(
        "range_int_param",
        [
            RangeListTaskParameterDefinition_2023_09(type=ParameterValueType.INT, range=[1, 2]),
            RangeExpressionTaskParameterDefinition_2023_09(
                type=ParameterValueType.INT, range="1-2"
            ),
        ],
    )
    def test_single_param_iteration(self, range_int_param):
        # GIVEN
        expected = [1, 2]
        space = StepParameterSpace_2023_09(
            taskParameterDefinitions={
                "Param1": range_int_param,
            }
        )
        iterator = StepParameterSpaceIterator(space=space)

        # WHEN
        it = iter(iterator)

        # THEN
        for i in range(len(expected)):
            assert {
                "Param1": ParameterValue(type=ParameterValueType.INT, value=str(expected[i]))
            } == next(it), f"i = {i}"
        with pytest.raises(StopIteration):
            next(it)

    @pytest.mark.parametrize("param_range", [[10], [10, 11, 12, 13, 14, 15]])
    def test_single_param_getelem(self, param_range):
        # GIVEN
        space = StepParameterSpace_2023_09(
            taskParameterDefinitions={
                "Param1": RangeListTaskParameterDefinition_2023_09(
                    type=ParameterValueType.INT, range=param_range
                ),
            }
        )

        # WHEN
        result = StepParameterSpaceIterator(space=space)

        # THEN
        with pytest.raises(IndexError):
            result[len(param_range)]
        with pytest.raises(IndexError):
            result[-len(param_range) - 1]
        expected = [
            {"Param1": ParameterValue(type=ParameterValueType.INT, value=str(v))}
            for v in param_range
        ]
        assert [result[i] for i in range(0, len(param_range))] == expected
        range_reversed = param_range.copy()
        range_reversed.reverse()
        expected.reverse()
        assert [result[-i - 1] for i in range(0, len(param_range))] == expected

    @pytest.mark.parametrize(
        "given, expected",
        [
            ([1, 2, 3], 3),
            ("1-5", 5),
            (["a", "b", "c", "d"], 4),
        ],
    )
    def test_single_param_len(self, given, expected) -> None:
        # GIVEN
        range_int_param: RangeTaskParameter
        if isinstance(given, list):
            range_int_param = RangeListTaskParameterDefinition_2023_09(
                type=ParameterValueType.INT, range=given
            )
        elif isinstance(given, str):
            range_int_param = RangeExpressionTaskParameterDefinition_2023_09(
                type=ParameterValueType.INT, range=given
            )

        space = StepParameterSpace_2023_09(
            taskParameterDefinitions={
                "Param1": range_int_param,
            }
        )

        # WHEN
        result = StepParameterSpaceIterator(space=space)

        # THEN
        assert len(result) == expected
        # Test twice. We do some caching of lengths. Test the caching flows.
        assert len(result) == expected

    @pytest.mark.parametrize(
        "range_int_param",
        [
            RangeListTaskParameterDefinition_2023_09(type=ParameterValueType.INT, range=[1, 2]),
            RangeExpressionTaskParameterDefinition_2023_09(
                type=ParameterValueType.INT, range="1-2"
            ),
        ],
    )
    def test_defaults_product(
        self, range_int_param: RangeListTaskParameterDefinition_2023_09
    ) -> None:
        # GIVEN
        space = StepParameterSpace_2023_09(
            taskParameterDefinitions={
                "Param1": range_int_param,
                "Param2": RangeListTaskParameterDefinition_2023_09(
                    type=ParameterValueType.STRING, range=["a", "b"]
                ),
            }
        )

        # WHEN
        result = StepParameterSpaceIterator(space=space)

        # THEN
        # The combination_expr should default to "Param1 * Param2"
        assert len(result) == 2 * 2
        element: Callable[[int, str], dict[str, ParameterValue]] = lambda p1, p2: {
            "Param1": ParameterValue(type=ParameterValueType.INT, value=str(p1)),
            "Param2": ParameterValue(type=ParameterValueType.STRING, value=str(p2)),
        }
        expected_values = (
            element(1, "a"),
            element(1, "b"),
            element(2, "a"),
            element(2, "b"),
        )
        assert expected_values == tuple(v for v in result)

    def test_product_iteration(self) -> None:
        # GIVEN
        space = StepParameterSpace_2023_09(
            taskParameterDefinitions={
                "Param1": RangeListTaskParameterDefinition_2023_09(
                    type=ParameterValueType.INT, range=[1, 2]
                ),
                "Param2": RangeListTaskParameterDefinition_2023_09(
                    type=ParameterValueType.STRING, range=["a", "b", "c"]
                ),
                "Param3": RangeExpressionTaskParameterDefinition_2023_09(
                    type=ParameterValueType.INT, range="-1 - -2 : -1"
                ),
            },
            combination="Param1 * Param2 * Param3",
        )

        # WHEN
        result = StepParameterSpaceIterator(space=space)

        # THEN
        element: Callable[[int, str, int], dict[str, ParameterValue]] = lambda p1, p2, p3: {
            "Param1": ParameterValue(type=ParameterValueType.INT, value=str(p1)),
            "Param2": ParameterValue(type=ParameterValueType.STRING, value=str(p2)),
            "Param3": ParameterValue(type=ParameterValueType.INT, value=str(p3)),
        }
        expected_values = [
            element(1, "a", -1),
            element(1, "a", -2),
            element(1, "b", -1),
            element(1, "b", -2),
            element(1, "c", -1),
            element(1, "c", -2),
            element(2, "a", -1),
            element(2, "a", -2),
            element(2, "b", -1),
            element(2, "b", -2),
            element(2, "c", -1),
            element(2, "c", -2),
        ]
        assert expected_values == [v for v in result]

    def test_product_len(self):
        # GIVEN
        space = StepParameterSpace_2023_09(
            taskParameterDefinitions={
                "Param1": RangeExpressionTaskParameterDefinition_2023_09(
                    type=ParameterValueType.INT, range="1-2:1"
                ),
                "Param2": RangeListTaskParameterDefinition_2023_09(
                    type=ParameterValueType.STRING, range=["a", "b", "c"]
                ),
                "Param3": RangeListTaskParameterDefinition_2023_09(
                    type=ParameterValueType.INT, range=[-1, -2]
                ),
            },
            combination="Param1 * Param2 * Param3",
        )

        # WHEN
        result = StepParameterSpaceIterator(space=space)

        # THEN
        assert len(result) == 2 * 3 * 2
        # Test twice. We do some caching of lengths. Test the caching flows.
        assert len(result) == 2 * 3 * 2

    def test_product_getitem(self) -> None:
        # GIVEN
        space = StepParameterSpace_2023_09(
            taskParameterDefinitions={
                "Param1": RangeListTaskParameterDefinition_2023_09(
                    type=ParameterValueType.INT, range=[1, 2]
                ),
                "Param2": RangeListTaskParameterDefinition_2023_09(
                    type=ParameterValueType.STRING, range=["a", "b", "c"]
                ),
                "Param3": RangeExpressionTaskParameterDefinition_2023_09(
                    type=ParameterValueType.INT, range="-1--2:-1"
                ),
            },
            combination="Param1 * Param2 * Param3",
        )

        # WHEN
        result = StepParameterSpaceIterator(space=space)

        # THEN
        element: Callable[[int, str, int], dict[str, ParameterValue]] = lambda p1, p2, p3: {
            "Param1": ParameterValue(type=ParameterValueType.INT, value=str(p1)),
            "Param2": ParameterValue(type=ParameterValueType.STRING, value=str(p2)),
            "Param3": ParameterValue(type=ParameterValueType.INT, value=str(p3)),
        }
        expected_values = [
            element(1, "a", -1),
            element(1, "a", -2),
            element(1, "b", -1),
            element(1, "b", -2),
            element(1, "c", -1),
            element(1, "c", -2),
            element(2, "a", -1),
            element(2, "a", -2),
            element(2, "b", -1),
            element(2, "b", -2),
            element(2, "c", -1),
            element(2, "c", -2),
        ]
        with pytest.raises(IndexError):
            result[len(expected_values)]
        with pytest.raises(IndexError):
            result[-len(expected_values) - 1]
        assert expected_values == [result[i] for i in range(0, len(expected_values))]
        expected_reversed = expected_values.copy()
        expected_reversed.reverse()
        assert expected_reversed == [result[-i - 1] for i in range(0, len(expected_values))]

    def test_associate_iteration(self) -> None:
        # GIVEN
        space = StepParameterSpace_2023_09(
            taskParameterDefinitions={
                "Param1": RangeExpressionTaskParameterDefinition_2023_09(
                    type=ParameterValueType.INT, range="1-4"
                ),
                "Param2": RangeListTaskParameterDefinition_2023_09(
                    type=ParameterValueType.STRING, range=["a", "b", "c", "d"]
                ),
                "Param3": RangeListTaskParameterDefinition_2023_09(
                    type=ParameterValueType.INT, range=[-1, -2, -3, -4]
                ),
            },
            combination="(Param1, Param2, Param3)",
        )

        # WHEN
        result = StepParameterSpaceIterator(space=space)

        # THEN
        element: Callable[[int, str, int], dict[str, ParameterValue]] = lambda p1, p2, p3: {
            "Param1": ParameterValue(type=ParameterValueType.INT, value=str(p1)),
            "Param2": ParameterValue(type=ParameterValueType.STRING, value=str(p2)),
            "Param3": ParameterValue(type=ParameterValueType.INT, value=str(p3)),
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
        space = StepParameterSpace_2023_09(
            taskParameterDefinitions={
                "Param1": RangeListTaskParameterDefinition_2023_09(
                    type=ParameterValueType.INT, range=[1, 2, 3, 4]
                ),
                "Param2": RangeListTaskParameterDefinition_2023_09(
                    type=ParameterValueType.STRING, range=["a", "b", "c", "d"]
                ),
                "Param3": RangeExpressionTaskParameterDefinition_2023_09(
                    type=ParameterValueType.INT, range="-1--4:-1"
                ),
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
        space = StepParameterSpace_2023_09(
            taskParameterDefinitions={
                "Param1": RangeExpressionTaskParameterDefinition_2023_09(
                    type=ParameterValueType.INT, range="1-4"
                ),
                "Param2": RangeListTaskParameterDefinition_2023_09(
                    type=ParameterValueType.STRING, range=["a", "b", "c", "d"]
                ),
                "Param3": RangeListTaskParameterDefinition_2023_09(
                    type=ParameterValueType.INT, range=[-1, -2, -3, -4]
                ),
            },
            combination="(Param1, Param2, Param3)",
        )

        # WHEN
        result = StepParameterSpaceIterator(space=space)

        # THEN
        element: Callable[[int, str, int], dict[str, ParameterValue]] = lambda p1, p2, p3: {
            "Param1": ParameterValue(type=ParameterValueType.INT, value=str(p1)),
            "Param2": ParameterValue(type=ParameterValueType.STRING, value=str(p2)),
            "Param3": ParameterValue(type=ParameterValueType.INT, value=str(p3)),
        }
        expected_values = [
            element(1, "a", -1),
            element(2, "b", -2),
            element(3, "c", -3),
            element(4, "d", -4),
        ]
        with pytest.raises(IndexError):
            result[len(expected_values)]
        with pytest.raises(IndexError):
            result[-len(expected_values) - 1]
        assert expected_values == [result[i] for i in range(0, len(expected_values))]
        expected_reversed = expected_values.copy()
        expected_reversed.reverse()
        assert expected_reversed == [result[-i - 1] for i in range(0, len(expected_values))]

    def test_nested_expr_iteration(self) -> None:
        # A more deeply nested test to hit all of the recursive edge cases.
        # Namely ensure that we hit the iterator resets in the implementation.

        # GIVEN
        space = StepParameterSpace_2023_09(
            taskParameterDefinitions={
                "Param1": RangeListTaskParameterDefinition_2023_09(
                    type=ParameterValueType.INT, range=[1, 2]
                ),
                "Param2": RangeListTaskParameterDefinition_2023_09(
                    type=ParameterValueType.STRING, range=["a", "b", "c", "d"]
                ),
                "Param3": RangeExpressionTaskParameterDefinition_2023_09(
                    type=ParameterValueType.INT, range="10-11"
                ),
                "Param4": RangeListTaskParameterDefinition_2023_09(
                    type=ParameterValueType.INT, range=[20, 21]
                ),
            },
            combination="Param1 * ( Param2, Param3 * Param4 )",
        )

        # WHEN
        result = StepParameterSpaceIterator(space=space)

        # THEN
        element: Callable[[int, str, int, int], dict[str, ParameterValue]] = (
            lambda p1, p2, p3, p4: {
                "Param1": ParameterValue(type=ParameterValueType.INT, value=str(p1)),
                "Param2": ParameterValue(type=ParameterValueType.STRING, value=str(p2)),
                "Param3": ParameterValue(type=ParameterValueType.INT, value=str(p3)),
                "Param4": ParameterValue(type=ParameterValueType.INT, value=str(p4)),
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
        assert expected_values == [v for v in result]
