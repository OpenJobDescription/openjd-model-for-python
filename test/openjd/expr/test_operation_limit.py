# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for operation-bounded evaluation."""

from __future__ import annotations

import pytest
from openjd.expr import (
    evaluate_expression,
    parse_expression,
    ExpressionError,
    DEFAULT_OPERATION_LIMIT,
)


def op_limit_msg(limit: int, count: int | None = None) -> str:
    """Expected first line of an operation-limit-exceeded error."""
    if count is None:
        count = limit + 1
    return f"Expression operation count ({count}) exceeded limit ({limit})\n"


class TestDefaultOperationLimit:
    """Tests for the default operation limit constant."""

    def test_default_is_10_million(self) -> None:
        assert DEFAULT_OPERATION_LIMIT == 10_000_000


class TestOperationLimitExceeded:
    """Tests that operation limit is enforced with correct error messages."""

    def test_function_calls_count(self) -> None:
        """Each function call counts as 1 operation."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("1 + 1", operation_limit=0)
        assert str(exc_info.value) == "".join(
            [
                "Expression operation count (1) exceeded limit (0)\n",
                "  1 + 1\n",
                "  ~~^~~",
            ]
        )

    def test_range_iterations_count(self) -> None:
        """range(N) counts N iterations plus the function call."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("range(100)", operation_limit=50)
        assert str(exc_info.value) == "".join(
            [
                op_limit_msg(50),
                "  range(100)\n",
                "  ^~~~~~~~~~",
            ]
        )

    def test_list_comprehension_iterations_count(self) -> None:
        """List comprehension iterations are counted."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("[x for x in range(1000)]", operation_limit=50)
        assert str(exc_info.value) == "".join(
            [
                op_limit_msg(50),
                "  [x for x in range(1000)]\n",
                "              ^~~~~~~~~~~",
            ]
        )

    def test_sum_iterations_count(self) -> None:
        """sum() iterating a list counts the elements."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("sum(range(1000))", operation_limit=100)
        assert str(exc_info.value) == "".join(
            [
                op_limit_msg(100),
                "  sum(range(1000))\n",
                "      ^~~~~~~~~~~",
            ]
        )

    def test_min_iterations_count(self) -> None:
        """min() iterating a list counts the elements."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("min(range(1000))", operation_limit=100)
        assert str(exc_info.value) == "".join(
            [
                op_limit_msg(100),
                "  min(range(1000))\n",
                "      ^~~~~~~~~~~",
            ]
        )

    def test_max_iterations_count(self) -> None:
        """max() iterating a list counts the elements."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("max(range(1000))", operation_limit=100)
        assert str(exc_info.value) == "".join(
            [
                op_limit_msg(100),
                "  max(range(1000))\n",
                "      ^~~~~~~~~~~",
            ]
        )

    def test_sorted_iterations_count(self) -> None:
        """sorted() iterating a list counts the elements."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("sorted(range(1000))", operation_limit=100)
        assert str(exc_info.value) == "".join(
            [
                op_limit_msg(100),
                "  sorted(range(1000))\n",
                "         ^~~~~~~~~~~",
            ]
        )

    def test_reversed_iterations_count(self) -> None:
        """reversed() iterating a list counts the elements."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("reversed(range(1000))", operation_limit=100)
        assert str(exc_info.value) == "".join(
            [
                op_limit_msg(100),
                "  reversed(range(1000))\n",
                "           ^~~~~~~~~~~",
            ]
        )

    def test_join_iterations_count(self) -> None:
        """join() iterating a list counts the elements."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("['a','b','c','d','e'].join(',')", operation_limit=2)
        assert str(exc_info.value) == "".join(
            [
                op_limit_msg(2),
                "  ['a','b','c','d','e'].join(',')\n",
                "  ~~~~~~~~~~~~~~~~~~~~~~^~~~~~~~~",
            ]
        )

    def test_contains_iterations_count(self) -> None:
        """'in' operator on a list counts the elements."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("99 in range(1000)", operation_limit=100)
        assert str(exc_info.value) == "".join(
            [
                op_limit_msg(100),
                "  99 in range(1000)\n",
                "        ^~~~~~~~~~~",
            ]
        )

    def test_list_concat_iterations_count(self) -> None:
        """List concatenation counts elements of both lists."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("range(500) + range(500)", operation_limit=100)
        assert str(exc_info.value) == "".join(
            [
                op_limit_msg(100),
                "  range(500) + range(500)\n",
                "  ^~~~~~~~~~",
            ]
        )

    def test_list_multiply_iterations_count(self) -> None:
        """List repetition counts the result elements."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("[1, 2, 3] * 1000", operation_limit=100)
        assert str(exc_info.value) == "".join(
            [
                op_limit_msg(100),
                "  [1, 2, 3] * 1000\n",
                "  ~~~~~~~~~~^~~~~~",
            ]
        )

    def test_flatten_iterations_count(self) -> None:
        """flatten() counts outer and inner list elements."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("flatten([[1,2],[3,4]] * 500)", operation_limit=100)
        assert str(exc_info.value) == "".join(
            [
                op_limit_msg(100),
                "  flatten([[1,2],[3,4]] * 500)\n",
                "          ~~~~~~~~~~~~~~^~~~~",
            ]
        )

    def test_repr_sh_list_iterations_count(self) -> None:
        """repr_sh() on a list counts the elements."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("repr_sh(range(1000))", operation_limit=100)
        assert str(exc_info.value) == "".join(
            [
                op_limit_msg(100),
                "  repr_sh(range(1000))\n",
                "          ^~~~~~~~~~~",
            ]
        )

    def test_any_iterations_count(self) -> None:
        """any() iterating a list counts the elements."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("any([False] * 1000)", operation_limit=100)
        assert str(exc_info.value) == "".join(
            [
                op_limit_msg(100),
                "  any([False] * 1000)\n",
                "      ~~~~~~~~^~~~~~",
            ]
        )

    def test_all_iterations_count(self) -> None:
        """all() iterating a list counts the elements."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("all([True] * 1000)", operation_limit=100)
        assert str(exc_info.value) == "".join(
            [
                op_limit_msg(100),
                "  all([True] * 1000)\n",
                "      ~~~~~~~^~~~~~",
            ]
        )

    def test_list_equality_iterations_count(self) -> None:
        """List equality comparison counts the elements."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("range(1000) == range(1000)", operation_limit=100)
        assert str(exc_info.value) == "".join(
            [
                op_limit_msg(100),
                "  range(1000) == range(1000)\n",
                "  ^~~~~~~~~~~",
            ]
        )


class TestOperationLimitWithinBounds:
    """Tests that normal expressions work within the operation limit."""

    def test_simple_arithmetic(self) -> None:
        """Simple arithmetic works within a small limit."""
        result = evaluate_expression("1 + 2", operation_limit=10)
        assert result.item() == 3

    def test_small_range(self) -> None:
        """Small range works within a reasonable limit."""
        result = evaluate_expression("range(5)", operation_limit=1000)
        assert result.item() == [0, 1, 2, 3, 4]

    def test_small_list_comprehension(self) -> None:
        """Small list comprehension works within a reasonable limit."""
        result = evaluate_expression("[x * 2 for x in range(5)]", operation_limit=1000)
        assert result.item() == [0, 2, 4, 6, 8]

    def test_default_limit_handles_normal_expressions(self) -> None:
        """Normal expressions work with the default limit."""
        result = evaluate_expression("sum(range(100))")
        assert result.item() == 4950

    def test_string_operations_within_limit(self) -> None:
        """String operations work within limit."""
        result = evaluate_expression("'hello'.upper()", operation_limit=100)
        assert result.item() == "HELLO"

    def test_chained_operations_within_limit(self) -> None:
        """Chained operations work within limit."""
        result = evaluate_expression("'a,b,c'.split(',').join(';')", operation_limit=100)
        assert result.item() == "a;b;c"


class TestOperationCount:
    """Tests for operation_count tracking via ParsedExpression.evaluate_with_metrics."""

    def test_operation_count_returned(self) -> None:
        """evaluate_with_metrics() reports operation count > 0."""
        result = parse_expression("1 + 2").evaluate_with_metrics()
        assert result.operation_count > 0

    def test_constant_has_zero_operations(self) -> None:
        """A bare constant requires no operations."""
        result = parse_expression("42").evaluate_with_metrics()
        assert result.operation_count == 0

    def test_single_function_call_is_one_operation(self) -> None:
        """A single operator is 1 operation."""
        result = parse_expression("1 + 2").evaluate_with_metrics()
        assert result.operation_count == 1

    def test_range_counts_call_plus_iterations(self) -> None:
        """range(N) counts 1 call + N iterations."""
        result = parse_expression("range(10)").evaluate_with_metrics()
        # 1 call + 10 iterations = 11
        assert result.operation_count == 11

    def test_sum_range_counts_both(self) -> None:
        """sum(range(N)) counts operations for both range and sum."""
        result = parse_expression("sum(range(10))").evaluate_with_metrics()
        # range: 1 call + 10 iterations = 11
        # sum: 1 call + 10 iterations = 11
        # total = 22
        assert result.operation_count == 22

    def test_list_comprehension_counts_iterations(self) -> None:
        """List comprehension counts iterations and per-element operations."""
        result = parse_expression("[x * 2 for x in [1, 2, 3]]").evaluate_with_metrics()
        # 3 iterations from comprehension + 3 __mul__ calls = 6
        assert result.operation_count == 6

    def test_operation_count_increases_with_list_size(self) -> None:
        """Larger lists produce higher operation counts."""
        small = parse_expression("sum(range(10))").evaluate_with_metrics()
        large = parse_expression("sum(range(100))").evaluate_with_metrics()
        assert large.operation_count > small.operation_count

    def test_operation_count_reflects_each_call(self) -> None:
        """Each evaluate_with_metrics() call reports only that call's operation count."""
        parsed = parse_expression("sum(range(Param.N))")
        large = parsed.evaluate_with_metrics(values={"Param.N": 100})
        small = parsed.evaluate_with_metrics(values={"Param.N": 5})
        assert small.operation_count < large.operation_count

    def test_nested_comprehension_accumulates(self) -> None:
        """Nested operations accumulate operation counts."""
        result = parse_expression("[x + 1 for x in range(10)]").evaluate_with_metrics()
        # range: 1 call + 10 iterations = 11
        # comprehension: 10 iterations
        # 10 __add__ calls
        # total = 31
        assert result.operation_count == 31
