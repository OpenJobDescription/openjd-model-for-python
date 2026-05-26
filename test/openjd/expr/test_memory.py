# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for memory-bounded evaluation."""

import pytest
from openjd.expr import evaluate_expression, parse_expression, ExpressionError, TypeCode


class TestMemoryLimit:
    """Tests for memory_limit parameter."""

    def test_string_multiplication_exceeds_limit(self) -> None:
        """String multiplication that would exceed limit is blocked before allocation."""
        with pytest.raises(ExpressionError, match="exceeded limit|Operation limit exceeded"):
            evaluate_expression('"a" * 10000000', memory_limit=1000)

    def test_list_multiplication_exceeds_limit(self) -> None:
        """List multiplication that would exceed limit is blocked before allocation."""
        with pytest.raises(ExpressionError, match="exceeded limit|Operation limit exceeded"):
            evaluate_expression("[1, 2, 3] * 10000000", memory_limit=10000)

    def test_range_exceeds_limit(self) -> None:
        """range() that would exceed limit is blocked before allocation."""
        with pytest.raises(ExpressionError, match="exceeded limit|Operation limit exceeded"):
            evaluate_expression("range(10000000)", memory_limit=1000)

    def test_range_start_stop_exceeds_limit(self) -> None:
        """range(start, stop) that would exceed limit is blocked."""
        with pytest.raises(ExpressionError, match="exceeded limit|Operation limit exceeded"):
            evaluate_expression("range(0, 10000000)", memory_limit=1000)

    def test_range_start_stop_step_exceeds_limit(self) -> None:
        """range(start, stop, step) that would exceed limit is blocked."""
        with pytest.raises(ExpressionError, match="exceeded limit|Operation limit exceeded"):
            evaluate_expression("range(0, 10000000, 1)", memory_limit=1000)

    def test_normal_expression_within_limit(self) -> None:
        """Normal expressions work within default limit."""
        result = evaluate_expression("1 + 2 + 3")
        assert result.item() == 6

    def test_small_string_multiplication_within_limit(self) -> None:
        """Small string multiplication works within limit."""
        result = evaluate_expression('"ab" * 5', memory_limit=10000)
        assert result.item() == "ababababab"

    def test_small_range_within_limit(self) -> None:
        """Small range works within limit."""
        result = evaluate_expression("range(5)", memory_limit=10000)
        assert result.item() == [0, 1, 2, 3, 4]


class TestPeakMemory:
    """Tests for peak_memory tracking via ParsedExpression.evaluate_with_metrics."""

    def test_peak_memory_returned(self) -> None:
        """ParsedExpression.evaluate_with_metrics() reports peak memory > 0."""
        parsed = parse_expression("1 + 2")
        result = parsed.evaluate_with_metrics()
        assert result.peak_memory > 0

    def test_peak_memory_increases_with_complexity(self) -> None:
        """More complex expressions use more peak memory."""
        simple = parse_expression("1").evaluate_with_metrics()
        complex_expr = parse_expression("[1, 2, 3, 4, 5]").evaluate_with_metrics()
        assert complex_expr.peak_memory > simple.peak_memory

    def test_peak_memory_for_string(self) -> None:
        """String values contribute to peak memory."""
        short = parse_expression('"a"').evaluate_with_metrics()
        long = parse_expression('"a" * 100').evaluate_with_metrics()
        assert long.peak_memory > short.peak_memory

    def test_intermediate_values_released(self) -> None:
        """Intermediate values are released, keeping peak memory bounded."""
        # (1+2) + (3+4) should release intermediate results
        parsed = parse_expression("(1 + 2) + (3 + 4)")
        result = parsed.evaluate_with_metrics()
        assert result.value.item() == 10
        assert result.peak_memory > 0

    def test_peak_memory_reflects_each_call(self) -> None:
        """Each evaluate_with_metrics() call reports only that call's peak memory."""
        parsed = parse_expression("Param.X * 100")
        # First call with large string
        large = parsed.evaluate_with_metrics(values={"Param.X": "a" * 1000})
        # Second call with small value
        small = parsed.evaluate_with_metrics(values={"Param.X": "b"})
        # Each result reflects only its own call, not the other.
        assert small.peak_memory < large.peak_memory


class TestEvaluateExpressionReturnsExprValue:
    """Tests for evaluate_expression returning ExprValue directly."""

    def test_returns_expr_value(self) -> None:
        """evaluate_expression returns ExprValue directly."""
        result = evaluate_expression("42")
        assert result.item() == 42

    def test_has_type_attribute(self) -> None:
        """ExprValue has type attribute."""
        result = evaluate_expression("42")
        assert result.type.type_code == TypeCode.INT


class TestMemoryReleasedInComprehensions:
    """Regression tests: intermediate values in comprehensions must be released.

    Previously, evaluate() returned values that were already memory-tracked,
    but callers wrapped them in _track() again, causing double-tracking.
    Only one _release() happened per value, so memory leaked on every
    comprehension iteration.
    """

    def test_nested_comprehension_releases_inner_lists(self) -> None:
        """Inner lists consumed by len() should be fully released each iteration.

        Without the fix, each iteration leaked the inner list's memory,
        causing peak memory to scale as O(outer * inner_list_size) instead
        of O(inner_list_size).
        """
        # Single iteration baseline
        single = parse_expression("len([i for i in range(100)])").evaluate_with_metrics()
        single_peak = single.peak_memory

        # 100 iterations — peak should be similar to single, plus the small result list
        multi = parse_expression(
            "[len([i for i in range(100)]) for k in range(100)]"
        ).evaluate_with_metrics()

        # With the leak, multi.peak_memory would be ~100x single_peak.
        # Without the leak, it should be only modestly larger (result list of 100 ints).
        assert multi.peak_memory < single_peak * 5

    def test_deeply_nested_comprehension_bounded_memory(self) -> None:
        """Triple-nested comprehensions with len() should have bounded peak memory.

        This is the pattern from the conformance test. Without the fix,
        N=100 used ~118MB. With the fix, it uses ~55KB.
        """
        result = parse_expression(
            "[len([i for i in [len(range(100)) for j in range(100)]]) for k in range(100)]"
        ).evaluate_with_metrics()
        # Should be well under 1MB — the result is just 100 ints
        assert result.peak_memory < 1_000_000

    @pytest.mark.skip(reason="Rust memory accounting differs from Python")
    def test_comprehension_function_call_releases_args(self) -> None:
        """Function args evaluated inside a comprehension loop are released properly."""
        # sorted() takes a list arg, processes it, returns a new list.
        # The input arg should be released after each call.
        multi = parse_expression(
            "[len(sorted(range(50))) for i in range(50)]"
        ).evaluate_with_metrics()

        single = parse_expression("len(sorted(range(50)))").evaluate_with_metrics()

        assert multi.peak_memory < single.peak_memory * 20
