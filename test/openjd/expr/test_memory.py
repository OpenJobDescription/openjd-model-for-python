# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for memory-bounded evaluation."""

import pytest
from openjd.expr import (
    ExprType,
    ExprValue,
    ExpressionError,
    PathFormat,
    SymbolTable,
    TypeCode,
    evaluate_expression,
    parse_expression,
)


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


def _flag_symtab() -> SymbolTable:
    return SymbolTable(
        {
            "Session.Flag": ExprValue.unresolved(ExprType("bool")),
        }
    )


def _big_path_symtab() -> SymbolTable:
    """``Big`` is a POSIX path of 1,000,001 characters: tracking it exceeds any limit
    below 1 MB."""
    return SymbolTable(
        {
            "Session.Flag": ExprValue.unresolved(ExprType("bool")),
            "Big": ExprValue("/" + "a" * 1_000_000, type="path", path_format=PathFormat.POSIX),
        }
    )


def _memory_error(used: int, limit: int, expr: str, caret: str) -> str:
    return f"Expression memory usage ({used} bytes) exceeded limit ({limit} bytes)\n  {expr}\n  {caret}"


class TestMemoryAccountingInOpenjdExpr0_10_1:  # noqa: N801
    """openjd-expr 0.10.1 (openjd-rs#410, #417, #418) charges each live value once and
    releases it once. Expectations are copied from upstream
    ``tests/integration/test_memory.rs``. Every case except the named controls differs on
    0.10.0; ids and docstrings give the 0.10.0 result measured through this binding.
    """

    @pytest.mark.parametrize(
        "expr,limit,used,caret",
        [
            pytest.param(
                "[1, 2, 3] * 10000000",
                10000,
                1920000384,
                "~~~~~~~~~~^~~~~~~~~~",
                id="list literal charged once (0.10.0: 1920000576)",
            ),
            pytest.param(
                "range_expr('1-2000000')[::-1]",
                10000,
                128000288,
                "~~~~~~~~~~~~~~~~~~~~~~~^~~~~~",
                id="omitted slice bounds are tracked (0.10.0: 128000160)",
            ),
            pytest.param(
                "['A' * 600000 for x in [1, 2, 3]]",
                1500000,
                1800576,
                "^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
                id="comprehension iterable charged once (0.10.0: 1800768)",
            ),
            pytest.param(
                "['C' * 600000] + ['B' * 600000]",
                1000000,
                1200224,
                "                  ~~~~^~~~~~~~",
                id="exceeded while producing the second element (0.10.0: caret on the first list)",
            ),
            pytest.param(
                "['A' * 1000000, string('C' * 200000 == 'D' * 200000), 'B' * 700000]",
                1500000,
                1700272,
                "                                                      ~~~~^~~~~~~~",
                id="comparison releases operands once (0.10.0: 3000272)",
            ),
            pytest.param(
                "('A' * 1000000)[:]",
                1500000,
                2000256,
                "~~~~~~~~~~~~~~^~~~",
                id="string slice budgeted before allocating (0.10.0: fit, peak 1048640)",
            ),
        ],
    )
    def test_reported_usage(self, expr: str, limit: int, used: int, caret: str) -> None:
        with pytest.raises(ExpressionError) as excinfo:
            parse_expression(expr).evaluate(memory_limit=limit)
        assert str(excinfo.value) == _memory_error(used, limit, expr, caret)

    def test_coercion_to_the_target_type_is_charged_at_the_coerced_size(self) -> None:
        """A ``range_expr`` coerced to ``list[int]`` is 100,000 ints. 0.10.0 charged only
        the ``range_expr`` and returned the list."""
        expr = "range_expr('1-100000')"
        with pytest.raises(ExpressionError) as excinfo:
            parse_expression(expr).evaluate(memory_limit=100000, target_type=ExprType("list[int]"))
        assert str(excinfo.value) == _memory_error(800064, 100000, expr, "^~~~~~~~~~~~~~~~~~~~~~")

    def test_a_budget_error_in_the_if_branch_propagates_before_the_else_branch_runs(self) -> None:
        """0.10.0 evaluated both branches and reported ``Both branches fail in the
        if/else``, including the else-branch's ``Cannot convert 'nope' to int``."""
        expr = "Session.Flag or ('A' * 10000000 if Session.Flag else int('nope')) == 'x'"
        with pytest.raises(ExpressionError) as excinfo:
            parse_expression(expr).evaluate(values=_flag_symtab(), memory_limit=1048576)
        assert str(excinfo.value) == _memory_error(
            10000136, 1048576, expr, "                 ~~~~^~~~~~~~~~"
        )

    def test_a_compound_value_error_is_still_absorbed(self) -> None:
        """Control for the test above: with no budget error inside, ``or`` still
        absorbs the both-branches-fail error."""
        result = parse_expression(
            "Session.Flag or (int('a') if Session.Flag else int('b')) == 7"
        ).evaluate(values=_flag_symtab(), memory_limit=1048576)
        assert result.type == ExprType("unresolved[bool]")

    def test_an_absorbed_comprehension_failure_still_counts_toward_peak_memory(self) -> None:
        """0.10.0 dropped the failed iteration's spend and reported a peak of 512."""
        result = parse_expression(
            "[int('A' * 1000000) for x in [1]] if Session.Flag else []"
        ).evaluate_with_metrics(values=_flag_symtab())
        assert result.value.type.type_code == TypeCode.UNRESOLVED
        assert result.peak_memory >= 1_000_000

    @pytest.mark.parametrize(
        "expr,limit",
        [
            pytest.param(
                "len(['A' * 1000000 - 1 for x in [1]] if Session.Flag else []) + len('B' * 600000)",
                1500000,
                id="absorbed comprehension failure leaves no footprint",
            ),
            pytest.param(
                "len(int('x') if Session.Flag else 'A' * 1000000) + len('B' * 600000)",
                1500000,
                id="absorbing conditional releases the other branch (0.10.0: 1600264 bytes)",
            ),
            pytest.param(
                "len(['C' * 600000]) + len('B' * 300000)",
                1000000,
                id="list literal elements charged once (0.10.0: 1200128 bytes)",
            ),
            pytest.param(
                "['A' * 100000 for x in range(5)]", 560000, id="pushed element charged once"
            ),
            pytest.param("['A' * 600000 for x in [1, 2]]", 1500000, id="two large elements fit"),
        ],
    )
    def test_fits_under_the_limit(self, expr: str, limit: int) -> None:
        """The middle two cases fail on 0.10.0. The other three also fit on 0.10.0;
        upstream added them against over-charges introduced and fixed within #410 and
        #417, so here they are controls that the new accounting does not over-charge."""
        result = parse_expression(expr).evaluate_with_metrics(
            values=_flag_symtab(), memory_limit=limit
        )
        assert result.peak_memory <= limit

    def test_an_attribute_base_lookup_reports_the_memory_error(self) -> None:
        """0.10.0 rewrote the budget error as ``Undefined variable: 'Big.name'.``"""
        with pytest.raises(ExpressionError) as excinfo:
            parse_expression("Big.name").evaluate(
                values=_big_path_symtab(), memory_limit=500000, path_format=PathFormat.POSIX
            )
        assert str(excinfo.value) == _memory_error(1000065, 500000, "Big.name", "^~~")

    def test_an_attribute_memory_error_is_not_absorbed(self) -> None:
        expr = "Session.Flag or Big.name == 'x'"
        with pytest.raises(ExpressionError) as excinfo:
            parse_expression(expr).evaluate(
                values=_big_path_symtab(), memory_limit=500000, path_format=PathFormat.POSIX
            )
        assert str(excinfo.value) == _memory_error(1000065, 500000, expr, "                ^~~")

    def test_an_attribute_value_error_is_still_rewritten(self) -> None:
        """Control: a real property error keeps the friendlier message."""
        with pytest.raises(ExpressionError) as excinfo:
            parse_expression("'abc'.name").evaluate(memory_limit=1000000)
        assert str(excinfo.value) == (
            "'name' property is not available for string. Available for: path\n  'abc'.name\n  ~~~~~~^~~~"
        )
