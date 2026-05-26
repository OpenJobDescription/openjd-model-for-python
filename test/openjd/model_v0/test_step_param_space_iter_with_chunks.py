# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest
from typing import Any

from openjd.model import (
    ParameterValue,
    ParameterValueType,
    StepParameterSpaceIterator,
)

from openjd.model.v2023_09 import (
    RangeExpressionTaskParameterDefinition as RangeExpressionTaskParameterDefinition_2023_09,
    RangeListTaskParameterDefinition as RangeListTaskParameterDefinition_2023_09,
    StepParameterSpace as StepParameterSpace_2023_09,
    TaskChunksDefinition as TaskChunksDefinition_2023_09,
    TaskChunksRangeConstraint as TaskChunksRangeConstraint_2023_09,
)

from openjd.model._step_param_space_iter import (
    divide_chunk_sizes,
    divide_int_interval_into_chunks,
    divide_int_list_into_contiguous_chunks,
    divide_int_list_into_noncontiguous_chunks,
)


PARAMETRIZE_CASES: tuple = (
    pytest.param(
        RangeListTaskParameterDefinition_2023_09(
            type=ParameterValueType.CHUNK_INT,
            range=["1", "2"],
            chunks=TaskChunksDefinition_2023_09(
                defaultTaskCount=1, rangeConstraint=TaskChunksRangeConstraint_2023_09.CONTIGUOUS
            ),
        ),
        ["1-1", "2-2"],  # [v for v in it]
        False,
        ["1-2"],  # "v in it" returns True
        ["1", "2", "0-1"],  # "v in it" returns False
        id="contig chunks, chunksize 1, range is short list",
    ),
    pytest.param(
        RangeListTaskParameterDefinition_2023_09(
            type=ParameterValueType.CHUNK_INT,
            range=["1", "2"],
            chunks=TaskChunksDefinition_2023_09(
                defaultTaskCount=2, rangeConstraint=TaskChunksRangeConstraint_2023_09.CONTIGUOUS
            ),
        ),
        ["1-2"],  # [v for v in it]
        False,
        ["1-1", "2-2"],  # "v in it" returns True
        ["1", "2", "0-1"],  # "v in it" returns False
        id="contig chunks, chunksize 2, range is short list",
    ),
    pytest.param(
        RangeExpressionTaskParameterDefinition_2023_09(
            type=ParameterValueType.CHUNK_INT,
            range="1-2",
            chunks=TaskChunksDefinition_2023_09(
                defaultTaskCount=1, rangeConstraint=TaskChunksRangeConstraint_2023_09.CONTIGUOUS
            ),
        ),
        ["1-1", "2-2"],  # [v for v in it]
        False,
        ["1-2"],  # "v in it" returns True
        ["1", "2", "0-1", "3-"],  # "v in it" returns False
        id="contig chunks, chunksize 1, range is short range expr",
    ),
    pytest.param(
        RangeExpressionTaskParameterDefinition_2023_09(
            type=ParameterValueType.CHUNK_INT,
            range="1-2",
            chunks=TaskChunksDefinition_2023_09(
                defaultTaskCount=2, rangeConstraint=TaskChunksRangeConstraint_2023_09.CONTIGUOUS
            ),
        ),
        ["1-2"],  # [v for v in it]
        False,
        ["1-1", "2-2"],  # "v in it" returns True
        ["1", "2", "0-1"],  # "v in it" returns False
        id="contig chunks, chunksize 2, range is short range expr",
    ),
    pytest.param(
        RangeListTaskParameterDefinition_2023_09(
            type=ParameterValueType.CHUNK_INT,
            range=["1", "2"],
            chunks=TaskChunksDefinition_2023_09(
                defaultTaskCount=1, rangeConstraint=TaskChunksRangeConstraint_2023_09.NONCONTIGUOUS
            ),
        ),
        ["1", "2"],  # [v for v in it]
        False,
        ["1-1", "2-2", "1-2", "1-2:1"],  # "v in it" returns True
        ["0", "0-1"],  # "v in it" returns False
        id="noncontig chunks, chunksize 1, range is short list",
    ),
    pytest.param(
        RangeListTaskParameterDefinition_2023_09(
            type=ParameterValueType.CHUNK_INT,
            range=["1", "2"],
            chunks=TaskChunksDefinition_2023_09(
                defaultTaskCount=2, rangeConstraint=TaskChunksRangeConstraint_2023_09.NONCONTIGUOUS
            ),
        ),
        ["1,2"],  # [v for v in it]
        False,
        ["1-1", "2-2", "1-2", "1-2:1"],  # "v in it" returns True
        ["0", "0-1"],  # "v in it" returns False
        id="noncontig chunks, chunksize 2, range is short list",
    ),
    pytest.param(
        RangeExpressionTaskParameterDefinition_2023_09(
            type=ParameterValueType.CHUNK_INT,
            range="1-2",
            chunks=TaskChunksDefinition_2023_09(
                defaultTaskCount=1, rangeConstraint=TaskChunksRangeConstraint_2023_09.NONCONTIGUOUS
            ),
        ),
        ["1", "2"],  # [v for v in it]
        False,
        ["1-1", "2-2", "1-2", "1-2:1"],  # "v in it" returns True
        ["0", "0-1"],  # "v in it" returns False
        id="noncontig chunks, chunksize 1, range is short range expr",
    ),
    pytest.param(
        RangeExpressionTaskParameterDefinition_2023_09(
            type=ParameterValueType.CHUNK_INT,
            range="1-2",
            chunks=TaskChunksDefinition_2023_09(
                defaultTaskCount=2, rangeConstraint=TaskChunksRangeConstraint_2023_09.NONCONTIGUOUS
            ),
        ),
        ["1,2"],  # [v for v in it]
        False,
        ["1-1", "2-2", "1-2", "1-2:1"],  # "v in it" returns True
        ["0", "0-1"],  # "v in it" returns False
        id="noncontig chunks, chunksize 2, range is short range expr",
    ),
    pytest.param(
        RangeExpressionTaskParameterDefinition_2023_09(
            type=ParameterValueType.CHUNK_INT,
            range="1,3,5",
            chunks=TaskChunksDefinition_2023_09(
                defaultTaskCount=100, rangeConstraint=TaskChunksRangeConstraint_2023_09.CONTIGUOUS
            ),
        ),
        ["1-1", "3-3", "5-5"],  # [v for v in it]
        False,
        [],  # "v in it" returns True
        ["0", "0-1", "2-2", "1-2", "1-2:1"],  # "v in it" returns False
        id="contig chunks, chunksize 100, range is noncontig",
    ),
    pytest.param(
        RangeExpressionTaskParameterDefinition_2023_09(
            type=ParameterValueType.CHUNK_INT,
            range="1,3,5",
            chunks=TaskChunksDefinition_2023_09(
                defaultTaskCount=100,
                rangeConstraint=TaskChunksRangeConstraint_2023_09.NONCONTIGUOUS,
            ),
        ),
        ["1-5:2"],  # [v for v in it]
        False,
        ["1", "3", "5", "1-1", "3-3", "5-5", "1,3", "1-3:2", "1,3,5"],  # "v in it" returns True
        ["1-3", "1-5", "0", "2", "4", "6", "X", "--3"],  # "v in it" returns False
        id="noncontig chunks, chunksize 100, range is noncontig",
    ),
    pytest.param(
        RangeExpressionTaskParameterDefinition_2023_09(
            type=ParameterValueType.CHUNK_INT,
            range="1-35",
            chunks=TaskChunksDefinition_2023_09(
                defaultTaskCount=10, rangeConstraint=TaskChunksRangeConstraint_2023_09.CONTIGUOUS
            ),
        ),
        # Non-adaptive spreads out the chunks evenly
        ["1-9", "10-18", "19-27", "28-35"],  # [v for v in it]
        False,
        ["1-35", "1-1", "35-35"],  # "v in it" returns True
        ["0-0", "1", "35", "36-36", "0-35", "1-36"],  # "v in it" returns False
        id="contig chunks, chunksize 10, range 1-35, non-adaptive",
    ),
    pytest.param(
        RangeExpressionTaskParameterDefinition_2023_09(
            type=ParameterValueType.CHUNK_INT,
            range="1-35",
            chunks=TaskChunksDefinition_2023_09(
                defaultTaskCount=10,
                targetRuntimeSeconds=20,
                rangeConstraint=TaskChunksRangeConstraint_2023_09.NONCONTIGUOUS,
            ),
        ),
        # Adaptive makes chunks as big as possible, so the last chunk ends up smaller
        ["1-10", "11-20", "21-30", "31-35"],  # [v for v in it]
        True,
        ["1-35", "1", "1-1", "35", "35-35"],  # "v in it" returns True
        ["0", "0-0", "36", "36-36", "0-35", "1-36", "12-"],  # "v in it" returns False
        id="noncontig chunks, chunksize 10, range 1-35, adaptive",
    ),
    pytest.param(
        RangeExpressionTaskParameterDefinition_2023_09(
            type=ParameterValueType.CHUNK_INT,
            range="-20--5",
            chunks=TaskChunksDefinition_2023_09(
                defaultTaskCount=5, rangeConstraint=TaskChunksRangeConstraint_2023_09.CONTIGUOUS
            ),
        ),
        # Non-adaptive spreads out the chunks evenly
        ["-20--17", "-16--13", "-12--9", "-8--5"],  # [v for v in it]
        False,
        ["-20--5", "-20--10"],  # "v in it" returns True
        [
            "-21",
            "-20--4",
            "-",
            "",
            "-19",
            "-5",
            "-20,-19,-18,-15",
            "-20--25:-3",
        ],  # "v in it" returns False
        id="contig chunks, chunksize 5, negative frames, non-adaptive",
    ),
    pytest.param(
        RangeExpressionTaskParameterDefinition_2023_09(
            type=ParameterValueType.CHUNK_INT,
            range="-20--5",
            chunks=TaskChunksDefinition_2023_09(
                defaultTaskCount=5,
                targetRuntimeSeconds=20,
                rangeConstraint=TaskChunksRangeConstraint_2023_09.CONTIGUOUS,
            ),
        ),
        # Adaptive makes chunks as big as possible, so the last chunk ends up smaller
        ["-20--16", "-15--11", "-10--6", "-5--5"],  # [v for v in it]
        True,
        ["-20--5", "-20--10"],  # "v in it" returns True
        [
            "-21",
            "-20--4",
            "-",
            "",
            "-19",
            "-5",
            "-20,-19,-18,-15",
            "-20--25:-3",
            "--13",
        ],  # "v in it" returns False
        id="contig chunks, chunksize 5, negative frames, adaptive",
    ),
    pytest.param(
        RangeExpressionTaskParameterDefinition_2023_09(
            type=ParameterValueType.CHUNK_INT,
            range="-20--5",
            chunks=TaskChunksDefinition_2023_09(
                defaultTaskCount=5,
                targetRuntimeSeconds=20,
                rangeConstraint=TaskChunksRangeConstraint_2023_09.NONCONTIGUOUS,
            ),
        ),
        # Adaptive makes chunks as big as possible, so the last chunk ends up smaller
        ["-20--16", "-15--11", "-10--6", "-5"],  # [v for v in it]
        True,
        ["-20--5", "-20", "-19", "-5", "-20,-19,-18,-15", "-6--18:-3"],  # "v in it" returns True
        ["-21", "-20--4", "-", "", "-20--25:-3"],  # "v in it" returns False
        id="noncontig chunks, chunksize 5, negative frames, adaptive",
    ),
)


@pytest.mark.parametrize(
    "range_int_param,expected,chunks_adaptive,expected_contains,expected_not_contains",
    PARAMETRIZE_CASES,
)
def test_single_param_chunked_iteration(
    range_int_param, expected, chunks_adaptive, expected_contains, expected_not_contains
):
    # GIVEN
    space = StepParameterSpace_2023_09(
        taskParameterDefinitions={
            "Param1": range_int_param,
        }
    )

    # WHEN
    it = StepParameterSpaceIterator(space=space)

    # THEN
    assert it.chunks_adaptive == chunks_adaptive
    assert it.chunks_default_task_count == range_int_param.chunks.defaultTaskCount
    # Check that full iteration over the range gives the expected result
    assert [v for v in it] == [
        {"Param1": ParameterValue(type=ParameterValueType.CHUNK_INT, value=v)} for v in expected
    ]
    # Check that resetting the iterator and re-iterating produces the same again
    it.reset_iter()
    assert [v for v in it] == [
        {"Param1": ParameterValue(type=ParameterValueType.CHUNK_INT, value=v)} for v in expected
    ]
    # Check that __contains__ is True/False for all provided cases
    for v in expected:
        assert {"Param1": ParameterValue(type=ParameterValueType.CHUNK_INT, value=v)} in it
    for v in expected_contains:
        assert {"Param1": ParameterValue(type=ParameterValueType.CHUNK_INT, value=v)} in it
    for v in expected_not_contains:
        assert {"Param1": ParameterValue(type=ParameterValueType.CHUNK_INT, value=v)} not in it
    # Check that the length and indexing work as expected
    it.reset_iter()
    if chunks_adaptive:
        # With adaptive chunking, it can't retrieve the length or use the indexing operator
        with pytest.raises(ValueError):
            len(it)
        with pytest.raises(LookupError):
            it[0]
    else:
        assert len(it) == len(expected)
        for i, v in enumerate(expected):
            assert it[i] == {"Param1": ParameterValue(type=ParameterValueType.CHUNK_INT, value=v)}
            assert it[i - len(expected)] == {
                "Param1": ParameterValue(type=ParameterValueType.CHUNK_INT, value=v)
            }
        # Without adaptive chunking, the chunk size is fixed
        with pytest.raises(ValueError):
            it.chunks_default_task_count = 1

    assert it.chunks_parameter_name == "Param1"


PARAMETRIZE_CASES = (
    pytest.param(
        {
            "Param1": RangeListTaskParameterDefinition_2023_09(
                type=ParameterValueType.CHUNK_INT,
                range=["1", "2"],
                chunks=TaskChunksDefinition_2023_09(
                    defaultTaskCount=1, rangeConstraint=TaskChunksRangeConstraint_2023_09.CONTIGUOUS
                ),
            ),
            "Param2": RangeListTaskParameterDefinition_2023_09(
                type=ParameterValueType.STRING,
                range=["A", "B"],
            ),
        },
        [("1-1", "A"), ("1-1", "B"), ("2-2", "A"), ("2-2", "B")],  # [v for v in it]
        False,  # chunks_adaptive
        None,  # override_chunk_size
        [("1-2", "A"), ("1-2", "B")],  # "v in it" returns True
        [("1", "A"), ("2", "A"), ("1", "B"), ("2", "B"), ("1-1", "C")],  # "v in it" returns False
        id="2 dim, chunked outer, chunksize 1, non-adaptive",
    ),
    pytest.param(
        {
            "Param1": RangeListTaskParameterDefinition_2023_09(
                type=ParameterValueType.CHUNK_INT,
                range=["1", "2"],
                chunks=TaskChunksDefinition_2023_09(
                    defaultTaskCount=1, rangeConstraint=TaskChunksRangeConstraint_2023_09.CONTIGUOUS
                ),
            ),
            "Param2": RangeListTaskParameterDefinition_2023_09(
                type=ParameterValueType.STRING,
                range=["A", "B"],
            ),
        },
        [("1-2", "A"), ("1-2", "B")],  # [v for v in it]
        False,  # chunks_adaptive
        5,  # override_chunk_size
        [("1-1", "A"), ("2-2", "A"), ("1-1", "B"), ("2-2", "B")],  # "v in it" returns True
        [("1", "A"), ("2", "A"), ("1", "B"), ("2", "B"), ("1-1", "AB")],  # "v in it" returns False
        id="2 dim, chunked outer, chunksize 1, non-adaptive, override chunksize 5",
    ),
    pytest.param(
        {
            "Param1": RangeListTaskParameterDefinition_2023_09(
                type=ParameterValueType.CHUNK_INT,
                range=["1", "2"],
                chunks=TaskChunksDefinition_2023_09(
                    defaultTaskCount=2, rangeConstraint=TaskChunksRangeConstraint_2023_09.CONTIGUOUS
                ),
            ),
            "Param2": RangeListTaskParameterDefinition_2023_09(
                type=ParameterValueType.STRING,
                range=["A", "B"],
            ),
        },
        [("1-2", "A"), ("1-2", "B")],  # [v for v in it]
        False,  # chunks_adaptive
        None,  # override_chunk_size
        [("1-1", "A"), ("2-2", "A"), ("1-1", "B"), ("2-2", "B")],  # "v in it" returns True
        [("1", "A"), ("2", "A"), ("1", "B"), ("2", "B"), ("1-1", "AB")],  # "v in it" returns False
        id="2 dim, chunked outer, chunksize 2, non-adaptive",
    ),
    pytest.param(
        {
            "Param1": RangeListTaskParameterDefinition_2023_09(
                type=ParameterValueType.CHUNK_INT,
                range=["1", "2"],
                chunks=TaskChunksDefinition_2023_09(
                    defaultTaskCount=2, rangeConstraint=TaskChunksRangeConstraint_2023_09.CONTIGUOUS
                ),
            ),
            "Param2": RangeListTaskParameterDefinition_2023_09(
                type=ParameterValueType.STRING,
                range=["A", "B"],
            ),
        },
        [("1-1", "A"), ("1-1", "B"), ("2-2", "A"), ("2-2", "B")],  # [v for v in it]
        False,  # chunks_adaptive
        1,  # override_chunk_size
        [("1-2", "A"), ("1-2", "B")],  # "v in it" returns True
        [("1", "A"), ("2", "A"), ("1", "B"), ("2", "B"), ("1-1", "C")],  # "v in it" returns False
        id="2 dim, chunked outer, chunksize 2, non-adaptive, override chunksize 1",
    ),
    pytest.param(
        {
            "Param1": RangeListTaskParameterDefinition_2023_09(
                type=ParameterValueType.CHUNK_INT,
                range=["1", "2"],
                chunks=TaskChunksDefinition_2023_09(
                    defaultTaskCount=1,
                    targetRuntimeSeconds=20,
                    rangeConstraint=TaskChunksRangeConstraint_2023_09.CONTIGUOUS,
                ),
            ),
            "Param2": RangeListTaskParameterDefinition_2023_09(
                type=ParameterValueType.STRING,
                range=["A", "B"],
            ),
        },
        # The order is different from the equivalent non-adaptive, because the chunked dimension
        # is moved to the inside
        [("1-1", "A"), ("2-2", "A"), ("1-1", "B"), ("2-2", "B")],  # [v for v in it]
        True,  # chunks_adaptive
        None,  # override_chunk_size
        [("1-2", "A"), ("1-2", "B")],  # "v in it" returns True
        [("1", "A"), ("2", "A"), ("1", "B"), ("2", "B"), ("0-0", "A")],  # "v in it" returns False
        id="2 dim, chunked outer, chunksize 1, adaptive",
    ),
    pytest.param(
        {
            "Param1": RangeListTaskParameterDefinition_2023_09(
                type=ParameterValueType.CHUNK_INT,
                range=["1", "2"],
                chunks=TaskChunksDefinition_2023_09(
                    defaultTaskCount=2,
                    targetRuntimeSeconds=20,
                    rangeConstraint=TaskChunksRangeConstraint_2023_09.CONTIGUOUS,
                ),
            ),
            "Param2": RangeListTaskParameterDefinition_2023_09(
                type=ParameterValueType.STRING,
                range=["A", "B"],
            ),
        },
        [("1-2", "A"), ("1-2", "B")],  # [v for v in it]
        True,  # chunks_adaptive
        None,  # override_chunk_size
        [("1-1", "A"), ("2-2", "A"), ("1-1", "B"), ("2-2", "B")],  # "v in it" returns True
        [("1", "A"), ("2", "A"), ("1", "B"), ("2", "B"), ("3-3", "B")],  # "v in it" returns False
        id="2 dim, chunked outer, chunksize 2, adaptive",
    ),
    pytest.param(
        {
            "Param1": RangeListTaskParameterDefinition_2023_09(
                type=ParameterValueType.CHUNK_INT,
                range=["1", "2"],
                chunks=TaskChunksDefinition_2023_09(
                    defaultTaskCount=2,
                    targetRuntimeSeconds=20,
                    rangeConstraint=TaskChunksRangeConstraint_2023_09.NONCONTIGUOUS,
                ),
            ),
            "Param2": RangeListTaskParameterDefinition_2023_09(
                type=ParameterValueType.STRING,
                range=["A", "B"],
            ),
        },
        [("1", "A"), ("1", "B"), ("2", "A"), ("2", "B")],  # [v for v in it]
        False,  # chunks_adaptive
        1,  # override_chunk_size
        [("1-1", "A"), ("2-2", "A"), ("1-1", "B"), ("2-2", "B")],  # "v in it" returns True
        [("1", "C"), ("3-3", "B")],  # "v in it" returns False
        id="2 dim, chunked outer, chunksize 2, adaptive, noncontig, override chunksize 1 (turns off adaptive)",
    ),
)


@pytest.mark.parametrize(
    "param_defs,expected,chunks_adaptive,override_chunk_size,expected_contains,expected_not_contains",
    PARAMETRIZE_CASES,
)
def test_multi_param_chunked_iteration(
    param_defs: dict[str, Any],
    expected,
    chunks_adaptive,
    override_chunk_size,
    expected_contains,
    expected_not_contains,
):
    # GIVEN
    space = StepParameterSpace_2023_09(taskParameterDefinitions=param_defs)

    # WHEN
    it = StepParameterSpaceIterator(space=space, chunks_task_count_override=override_chunk_size)

    # THEN
    def element(tup):
        return {
            n: ParameterValue(type=ParameterValueType(param.type), value=v)
            for (n, param), v in zip(param_defs.items(), tup)
        }

    expected_values = [element(tup) for tup in expected]
    assert it.chunks_adaptive == chunks_adaptive
    # Check that full iteration over the range gives the expected result
    assert [v for v in it] == expected_values
    # Check that resetting the iterator and re-iterating produces the same again
    it.reset_iter()
    assert [v for v in it] == expected_values
    # Check that __contains__ is True/False for all provided cases
    for value in expected_values:
        assert value in it
    for tup in expected_contains:
        assert element(tup) in it
    for tup in expected_not_contains:
        assert element(tup) not in it
    assert it.chunks_parameter_name == "Param1"


def test_adaptive_contiguous_chunked_iteration():
    # GIVEN
    param_defs = {
        "P1": RangeExpressionTaskParameterDefinition_2023_09(
            type=ParameterValueType.CHUNK_INT,
            range="1-20",
            chunks=TaskChunksDefinition_2023_09(
                defaultTaskCount=2,
                targetRuntimeSeconds=20,
                rangeConstraint=TaskChunksRangeConstraint_2023_09.CONTIGUOUS,
            ),
        ),
        "P2": RangeListTaskParameterDefinition_2023_09(
            type=ParameterValueType.STRING,
            range=["A", "B"],
        ),
    }
    space = StepParameterSpace_2023_09(taskParameterDefinitions=param_defs)

    # WHEN
    it = StepParameterSpaceIterator(space=space)

    def make_item(v0, v1):
        return {
            "P1": ParameterValue(type=ParameterValueType.CHUNK_INT, value=v0),
            "P2": ParameterValue(type=ParameterValueType.STRING, value=v1),
        }

    # THEN
    # Starting with chunk size 2, then change the chunk size periodically
    assert next(it) == make_item("1-2", "A")
    assert next(it) == make_item("3-4", "A")
    it.chunks_default_task_count = 10
    assert next(it) == make_item("5-14", "A")
    assert next(it) == make_item("15-20", "A")
    assert next(it) == make_item("1-10", "B")
    it.chunks_default_task_count = 4
    assert next(it) == make_item("11-14", "B")
    assert next(it) == make_item("15-18", "B")
    it.chunks_default_task_count = 1
    assert next(it) == make_item("19-19", "B")
    assert next(it) == make_item("20-20", "B")

    with pytest.raises(StopIteration):
        next(it)

    assert it.chunks_parameter_name == "P1"


def test_adaptive_noncontiguous_chunked_iteration():
    # GIVEN
    param_defs = {
        "P1": RangeExpressionTaskParameterDefinition_2023_09(
            type=ParameterValueType.CHUNK_INT,
            range="1-10,12,15,18,20-23,1000",
            chunks=TaskChunksDefinition_2023_09(
                defaultTaskCount=2,
                targetRuntimeSeconds=20,
                rangeConstraint=TaskChunksRangeConstraint_2023_09.NONCONTIGUOUS,
            ),
        ),
        "P2": RangeListTaskParameterDefinition_2023_09(
            type=ParameterValueType.STRING,
            range=["A", "B"],
        ),
    }
    space = StepParameterSpace_2023_09(taskParameterDefinitions=param_defs)

    # WHEN
    it = StepParameterSpaceIterator(space=space)

    def make_item(v0, v1):
        return {
            "P1": ParameterValue(type=ParameterValueType.CHUNK_INT, value=v0),
            "P2": ParameterValue(type=ParameterValueType.STRING, value=v1),
        }

    # THEN
    # Starting with chunk size 2, then change the chunk size periodically
    assert next(it) == make_item("1,2", "A")
    assert next(it) == make_item("3,4", "A")
    it.chunks_default_task_count = 10
    assert next(it) == make_item("5-10,12-18:3,20", "A")
    assert next(it) == make_item("21-23,1000", "A")
    assert next(it) == make_item("1-10", "B")
    it.chunks_default_task_count = 4
    assert next(it) == make_item("12-18:3,20", "B")
    assert next(it) == make_item("21-23,1000", "B")

    with pytest.raises(StopIteration):
        next(it)

    assert it.chunks_parameter_name == "P1"


def test_divide_chunk_sizes():
    # Some edge cases
    assert divide_chunk_sizes(1, 0) == []
    assert divide_chunk_sizes(1, 1) == [1]
    assert divide_chunk_sizes(10000, 10000) == [10000]
    assert divide_chunk_sizes(1, 100) == [1] * 100
    # Splitting in two
    assert divide_chunk_sizes(25, 49) == [25, 24]
    assert divide_chunk_sizes(25, 50) == [25, 25]
    assert divide_chunk_sizes(26, 51) == [26, 25]
    # Check that chunks are evenly divided across a variety of chunk counts for a prime task count
    assert divide_chunk_sizes(37, 37) == [37]
    assert divide_chunk_sizes(36, 37) == [19, 18]
    assert divide_chunk_sizes(17, 37) == [13, 12, 12]
    assert divide_chunk_sizes(9, 37) == [8, 7, 8, 7, 7]
    assert divide_chunk_sizes(4, 37) == [4, 4, 4, 3, 4, 4, 3, 4, 4, 3]
    assert divide_chunk_sizes(3, 37) == [3, 3, 3, 3, 3, 3, 2, 3, 3, 3, 3, 3, 2]
    assert divide_chunk_sizes(2, 37) == [2] * 18 + [1]
    assert divide_chunk_sizes(1, 37) == [1] * 37


def test_divide_interval_into_chunks():
    # Some edge cases
    assert divide_int_interval_into_chunks(1, 0, 0) == ["0-0"]
    assert divide_int_interval_into_chunks(10, -10, -1) == ["-10--1"]
    assert divide_int_interval_into_chunks(5, -10, -1) == ["-10--6", "-5--1"]
    assert divide_int_interval_into_chunks(100000, 0, 10000) == ["0-10000"]
    assert divide_int_interval_into_chunks(10000, 0, 10000) == ["0-5000", "5001-10000"]
    assert divide_int_interval_into_chunks(1, 1, 100) == [f"{i}-{i}" for i in range(1, 101)]
    # Where the boundaries of splitting in 1, 2, or 3 live
    assert divide_int_interval_into_chunks(24, 1, 50) == ["1-17", "18-34", "35-50"]
    assert divide_int_interval_into_chunks(25, 1, 50) == ["1-25", "26-50"]
    assert divide_int_interval_into_chunks(49, 1, 50) == ["1-25", "26-50"]
    assert divide_int_interval_into_chunks(50, 1, 50) == ["1-50"]
    # Check that chunks are evenly divided across a variety of chunk counts for a prime task count
    assert divide_int_interval_into_chunks(1, 22, 40) == [f"{i}-{i}" for i in range(22, 41)]
    assert divide_int_interval_into_chunks(2, 22, 40) == [
        f"{i}-{min(i + 1, 40)}" for i in range(22, 41, 2)
    ]
    assert divide_int_interval_into_chunks(3, 22, 40) == [
        "22-24",
        "25-27",
        "28-30",
        "31-32",
        "33-35",
        "36-38",
        "39-40",
    ]
    assert divide_int_interval_into_chunks(5, 22, 40) == ["22-26", "27-31", "32-36", "37-40"]
    assert divide_int_interval_into_chunks(15, 22, 40) == ["22-31", "32-40"]
    assert divide_int_interval_into_chunks(37, 22, 40) == ["22-40"]


def test_divide_int_list_into_contiguous_chunks():
    # Cases of dividing an integer list into contiguous chunks
    assert divide_int_list_into_contiguous_chunks(1, []) == []
    assert divide_int_list_into_contiguous_chunks(1, [1, 2, 3, 5, 7]) == [
        "1-1",
        "2-2",
        "3-3",
        "5-5",
        "7-7",
    ]
    assert divide_int_list_into_contiguous_chunks(100, [1, 2, 3, 5, 7]) == ["1-3", "5-5", "7-7"]
    assert divide_int_list_into_contiguous_chunks(100, [1, 2, 3, 7, 4, 5]) == ["1-3", "7-7", "4-5"]
    assert divide_int_list_into_contiguous_chunks(2, [1, 2, 3, 7, 4, 5]) == [
        "1-2",
        "3-3",
        "7-7",
        "4-5",
    ]


def test_divide_int_list_into_noncontiguous_chunks():
    # Cases of dividing an integer list into noncontiguous chunks
    assert divide_int_list_into_noncontiguous_chunks(1, []) == []
    assert divide_int_list_into_noncontiguous_chunks(1, [1, 2, 3, 5, 7]) == [
        "1",
        "2",
        "3",
        "5",
        "7",
    ]
    assert divide_int_list_into_noncontiguous_chunks(100, [1, 2, 3, 5, 7]) == ["1-3,5,7"]
    assert divide_int_list_into_noncontiguous_chunks(100, [1, 2, 3, 7, 4, 5]) == ["1-5,7"]
    assert divide_int_list_into_noncontiguous_chunks(2, [1, 2, 3, 7, 4, 5]) == ["1,2", "3,7", "4,5"]
    assert divide_int_list_into_noncontiguous_chunks(3, [1, 2, 3, 7, 4, 5]) == ["1-3", "4,5,7"]
