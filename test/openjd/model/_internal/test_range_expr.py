# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from itertools import zip_longest
from typing import Union

import pytest

from openjd.model import ExpressionError, TokenError
from openjd.model import IntRangeExpr
from openjd.model._range_expr import IntRange, Parser as RangeExpressionParser


class TestRangeExpressionParser:
    def test_propagates_error(self) -> None:
        # GIVEN
        parser = RangeExpressionParser()

        # THEN
        with pytest.raises(TokenError):
            parser.parse("!")

    def test_fails_empty(self) -> None:
        # GIVEN
        parser = RangeExpressionParser()

        # THEN
        with pytest.raises(ExpressionError):
            parser.parse("")

    @pytest.mark.parametrize(
        "range_expr",
        [
            pytest.param("1-a", id="non-valid character at end"),
            pytest.param("b-1", id="non-valid character at start"),
            pytest.param("--12", id="missing start"),
            pytest.param("1-", id="missing end"),
            pytest.param("1-,3-4", id="missing end in first range"),
            pytest.param("1-10,11-", id="misisng end in second range"),
            pytest.param("--1-10", id="extra hyphen in front of start"),
            pytest.param("1---10", id="extra hyphen in front of end"),
            pytest.param("1--10:--5", id="extra hyphen in front of step"),
            pytest.param("1-2,,3-4", id="extra comma between ranges"),
            pytest.param("1-:2,", id="trailing comma"),
            pytest.param("1-2:", id="missing step"),
            pytest.param("2:", id="trailing colon"),
            pytest.param(":2", id="leading colon"),
            pytest.param(":", id="just a colon"),
            pytest.param("1-2 4-5", id="missing comma between ranges"),
            pytest.param("1-24-5", id="extra number at the end"),
            pytest.param("1-2:1 -5", id="missing comma before second range"),
            pytest.param("1-2:0", id="step cannot be 0"),
            pytest.param("1-0:1", id="the inclusive offset does not make this range valid"),
            pytest.param("0-1:-1", id="total length 0 for pos range and neg step"),
            pytest.param("2-0:1", id="total length 0 for neg range and post step"),
            pytest.param("0-1, 1-2:-1", id="has length, but incorrect negative step"),
            pytest.param("2-1:-1, 2-0:1", id="has length, but incorrect positive step"),
        ],
    )
    def test_not_valid_expression(self, range_expr: str) -> None:
        # GIVEN
        parser = RangeExpressionParser()

        # THEN
        with pytest.raises(ExpressionError):
            parser.parse(range_expr)

    @pytest.mark.parametrize(
        "range_expr",
        [
            pytest.param("-9999999"),
            pytest.param("-100"),
            pytest.param("-1"),
            pytest.param("0"),
            pytest.param("1"),
            pytest.param("100"),
            pytest.param("9999999"),
        ],
    )
    def test_only_start(self, range_expr: str) -> None:
        # GIVEN
        parser = RangeExpressionParser()

        # WHEN
        full_range = parser.parse(range_expr)

        # THEN
        assert len(full_range) == 1
        assert str(full_range) == range_expr
        for i in full_range:
            assert i == int(range_expr) == full_range.start == full_range.end

    @pytest.mark.parametrize(
        "range_expr, expected_range_expr",
        [
            pytest.param("\t0 - 1 :\t1, 2 -\t100 : 1", "0-1:1,2-100:1"),
        ],
    )
    def test_ignore_whitespace(self, range_expr: str, expected_range_expr: str) -> None:
        # GIVEN
        parser = RangeExpressionParser()

        # WHEN
        with_whitespace = parser.parse(range_expr)
        without_whitepsace = parser.parse(expected_range_expr)

        # THEN
        assert with_whitespace == without_whitepsace

    @pytest.mark.parametrize(
        "range_expr,start,end,length",
        [pytest.param("1-100", 1, 100, 100)],
    )
    def test_parse_one_positive_range_no_step(
        self, range_expr: str, start: int, end: int, length: int
    ) -> None:
        # GIVEN
        parser = RangeExpressionParser()

        # WHEN
        full_range = parser.parse(range_expr)

        # THEN
        assert len(full_range) == length
        assert full_range.start == min(start, end)
        assert full_range.end == max(start, end)

    @pytest.mark.parametrize(
        "range_expr,start,end,total_range,range_str",
        [
            pytest.param("1-100,101-200", 1, 200, 200, "1-200"),
            pytest.param("0-1,3-4,7-9,10", 0, 10, 8, "0-1,3-4,7-10"),
            pytest.param("20-29,0-9,10-19", 0, 29, 30, "0-29"),
        ],
    )
    def test_parse_multiple_positive_non_overlapping_ranges(
        self, range_expr: str, start: int, end: int, total_range: int, range_str: str
    ) -> None:
        # GIVEN
        parser = RangeExpressionParser()

        # WHEN
        full_range = parser.parse(range_expr)

        # THEN
        assert full_range.start == start
        assert full_range.end == end
        assert len(full_range) == total_range
        assert str(full_range) == range_str

    @pytest.mark.parametrize(
        "range_expr",
        [
            pytest.param("1-10,1-10", id="complete overlap"),
            pytest.param("10-1:-1,10-1:-1", id="descending complete overlap"),
            pytest.param("-10--1,-10--1", id="negative complete overlap"),
            pytest.param("-1--10:-1,-1--10:-1", id="negative descending complete overlap"),
            pytest.param("1-10,2-9", id="complete overlap, subset"),
            pytest.param("1-10,9-19", id="partial overlap"),
            pytest.param("9-19,1-10", id="partial overlap, reverse order"),
            pytest.param("1-10:1,10-1:-1", id="ascending and descending overlap"),
            pytest.param("-1--10:-1,-10--19:-1", id="negative partial overlap"),
        ],
    )
    def test_parse_overlapping_ranges(self, range_expr: str) -> None:
        # GIVEN
        parser = RangeExpressionParser()

        # WHEN / THEN
        with pytest.raises(ExpressionError):
            parser.parse(range_expr)


class TestIntRangeExpr:
    def test_range_sorting_and_merging(self):
        # GIVEN
        first = IntRange(start=-9, end=0)
        second = IntRange(start=1, end=10)
        third = IntRange(start=11, end=20)

        sorted_merged_ranges = [IntRange(start=-9, end=20)]
        range_str = "-9-20"

        # WHEN
        full_range = IntRangeExpr([third, second, first])

        # THEN
        assert full_range.ranges == sorted_merged_ranges
        assert str(full_range) == range_str

    @pytest.mark.parametrize(
        "range_input_str,range_str",
        [
            pytest.param("  5 ", "5", id="one int"),
            pytest.param("9,0,3,2,8,10,1,4,7,6,5", "0-10", id="values 0-10 out of order"),
            pytest.param("3-5,0-2,8-12:2", "0-5,8-12:2", id="ranges out of order with steps"),
        ],
    )
    def test_range_expr_from_str(self, range_input_str: str, range_str: str):
        # GIVEN

        # WHEN
        full_range = IntRangeExpr.from_str(range_input_str)

        # THEN
        assert str(full_range) == range_str

    @pytest.mark.parametrize(
        "range_list,range_str",
        [
            pytest.param([5], "5", id="one int"),
            pytest.param(["7"], "7", id="one int as a str"),
            pytest.param([9, 0, 3, 2, 8, 10, 1, 4, 7, 6, 5], "0-10", id="values 0-10 out of order"),
            pytest.param(
                [1, 3, 5, 6, 7, 8, 10, 13, 16],
                "1-5:2,6-8,10-16:3",
                id="runs with different step size",
            ),
        ],
    )
    def test_range_expr_from_list(self, range_list: list[Union[int, str]], range_str: str):
        # GIVEN

        # WHEN
        full_range = IntRangeExpr.from_list(range_list)

        # THEN
        assert str(full_range) == range_str

    def test_sorting_with_descending_ranges(self):
        # GIVEN
        first = IntRange(start=-10, end=-19, step=-1)
        second = IntRange(start=-1, end=-9, step=-1)
        third = IntRange(start=10, end=0, step=-1)

        sorted_ranges = [first, second, third]

        # WHEN
        full_range = IntRangeExpr([second, third, first])

        # THEN
        for actual, expected in zip_longest(full_range.ranges, sorted_ranges):
            assert actual == expected

    def test_sorting_mixed_ascending_and_descending_ranges(self):
        # GIVEN
        first = IntRange(start=-9, end=-7, step=1)
        second = IntRange(start=1, end=-6, step=-1)
        third = IntRange(start=2, end=9, step=1)

        sorted_ranges = [first, second, third]

        # WHEN
        full_range = IntRangeExpr([second, first, third])

        # THEN
        for actual, expected in zip_longest(full_range.ranges, sorted_ranges):
            assert actual == expected

    @pytest.mark.parametrize(
        "index",
        [
            pytest.param(20, id="longer than length"),
            pytest.param(-21, id="negative index - longer than length"),
            pytest.param(100, id="much longer"),
            pytest.param(-101, id="negative - much longer"),
        ],
    )
    def test_range_expression_getitem_out_of_bounds(self, index):
        # GIVEN
        first = IntRange(start=-5, end=0, step=1)
        second = IntRange(start=5, end=10, step=1)
        third = IntRange(start=13, end=20, step=1)

        range_expression = IntRangeExpr([third, second, first])

        # WHEN / THEN
        with pytest.raises(IndexError):
            range_expression[index]

    @pytest.mark.parametrize(
        "index, expected_item",
        [
            pytest.param(0, -5, id="first range - first item"),
            pytest.param(2, -3, id="first range"),
            pytest.param(5, 0, id="second range"),
            pytest.param(15, 16, id="third range"),
            pytest.param(19, 20, id="third range - last item"),
            pytest.param(-1, 20, id="negative index - first item"),
            pytest.param(-20, -5, id="negative index - last item"),
        ],
    )
    def test_range_expression_getitem(self, index, expected_item):
        # GIVEN
        first = IntRange(start=-5, end=0, step=1)
        second = IntRange(start=5, end=10, step=1)
        third = IntRange(start=13, end=20, step=1)

        range_expression = IntRangeExpr([third, second, first])

        # WHEN
        actual = range_expression[index]

        for i, r in enumerate(range_expression):
            print(i, r)

        # THEN
        assert actual == expected_item

    @pytest.mark.parametrize(
        "range_expr",
        [
            pytest.param("1-10,11-20"),
        ],
    )
    def test_iterable(self, range_expr: str) -> None:
        # GIVEN / WHEN
        parser: RangeExpressionParser = RangeExpressionParser()
        full_range: IntRangeExpr = parser.parse(range_expr)
        expected_range: range = range(full_range.start, full_range.end + 1, 1)

        # THEN
        for actual, expected in zip_longest(full_range, expected_range):
            assert actual == expected

    def test_read_only_properties(self) -> None:
        # GIVEN
        full_range: IntRangeExpr = IntRangeExpr([IntRange(start=0, end=10, step=1)])
        original_ranges_contents: list[IntRange] = full_range.ranges

        # WHEN
        full_range.ranges.append(IntRange(start=1, end=2, step=1))

        # THEN
        assert original_ranges_contents == full_range.ranges == [IntRange(start=0, end=10, step=1)]

        # WHEN
        full_range.ranges[0] = IntRange(start=1, end=2, step=1)

        # THEN
        assert original_ranges_contents == full_range.ranges == [IntRange(start=0, end=10, step=1)]

        # WHEN / THEN
        with pytest.raises(AttributeError):
            full_range.start = 1  # type: ignore

        with pytest.raises(AttributeError):
            full_range.end = 1  # type: ignore

        with pytest.raises(AttributeError):
            full_range.ranges = []  # type: ignore


class TestIntRange:
    def test_comparisons(self):
        # GIVEN / WHEN / THEN
        # start, end, and step are the same, therefore equal and not less/greater than
        assert IntRange(start=0, end=0, step=1) == IntRange(start=0, end=0)
        assert not IntRange(start=0, end=0) < IntRange(start=0, end=0)
        assert not IntRange(start=0, end=0) > IntRange(start=0, end=0)

        # start is different
        assert IntRange(start=0, end=1) < IntRange(start=1, end=1)

        # start is the same, other end is bigger
        assert IntRange(start=0, end=0) < IntRange(start=0, end=1)

        # start and end are same, other step is bigger
        assert IntRange(start=0, end=0, step=1) < IntRange(start=0, end=0, step=2)

    def test_length(self):
        # GIVEN / WHEN / THEN
        # positive ascending
        assert len(IntRange(start=0, end=0, step=1)) == 1
        assert len(IntRange(start=0, end=10, step=1)) == 11
        assert len(IntRange(start=0, end=10, step=2)) == 6

        # negative ascending
        assert len(IntRange(start=-3, end=-1, step=1)) == 3
        assert len(IntRange(start=-3, end=1, step=1)) == 5
        assert len(IntRange(start=-3, end=1, step=2)) == 3

        # positive descending
        assert len(IntRange(start=0, end=0, step=-1)) == 1
        assert len(IntRange(start=10, end=-5, step=-1)) == 16
        assert len(IntRange(start=10, end=-5, step=-2)) == 8

        # negative descending
        assert len(IntRange(start=-3, end=-7, step=-1)) == 5
        assert len(IntRange(start=-3, end=-7, step=-2)) == 3

    def test_read_only_properties(self) -> None:
        # GIVEN
        range: IntRange = IntRange(start=0, end=10, step=1)

        # WHEN / THEN
        with pytest.raises(AttributeError):
            range.start = 1  # type: ignore

        with pytest.raises(AttributeError):
            range.end = 1  # type: ignore

        with pytest.raises(AttributeError):
            range.step = 1  # type: ignore
