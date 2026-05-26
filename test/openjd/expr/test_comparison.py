# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for comparison and logical operations."""

import sys
import pytest
from openjd.expr import evaluate_expression, ExprValue, SymbolTable
from openjd.expr import PathFormat

HOST_PATH_FORMAT = PathFormat.WINDOWS if sys.platform == "win32" else PathFormat.POSIX


class TestComparison:
    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("5 > 3", True),
            ("3 > 5", False),
            ("5 < 3", False),
            ("3 < 5", True),
            ("5 >= 5", True),
            ("5 <= 5", True),
            ("5 == 5", True),
            ("5 == 6", False),
            ("5 != 6", True),
            ("5 != 5", False),
        ],
    )
    def test_int_comparison(self, expr: str, expected: bool) -> None:
        assert evaluate_expression(expr).item() == expected

    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("'abc' < 'abd'", True),
            ("'abc' == 'abc'", True),
            ("'abc' != 'xyz'", True),
        ],
    )
    def test_string_comparison(self, expr: str, expected: bool) -> None:
        assert evaluate_expression(expr).item() == expected


class TestLogical:
    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("True and True", True),
            ("True and False", False),
            ("False and True", False),
            ("False and False", False),
            ("True or False", True),
            ("False or True", True),
            ("False or False", False),
            ("not True", False),
            ("not False", True),
        ],
    )
    def test_logical_operators(self, expr: str, expected: bool) -> None:
        assert evaluate_expression(expr).item() == expected

    def test_short_circuit_and(self) -> None:
        symtab = SymbolTable({"X": 0})
        assert evaluate_expression("False and (1 / X > 0)", values=symtab).item() is False

    def test_short_circuit_or(self) -> None:
        symtab = SymbolTable({"X": 0})
        assert evaluate_expression("True or (1 / X > 0)", values=symtab).item() is True

    # Value-returning and/or with null-coalescing semantics

    def test_or_null_returns_right(self) -> None:
        assert evaluate_expression('null or "fallback"').item() == "fallback"

    def test_or_false_returns_right(self) -> None:
        assert evaluate_expression('false or "fallback"').item() == "fallback"

    def test_or_truthy_returns_left(self) -> None:
        assert evaluate_expression('"hello" or "fallback"').item() == "hello"

    def test_or_zero_is_truthy(self) -> None:
        assert evaluate_expression("0 or 5").item() == 0

    def test_or_empty_string_is_truthy(self) -> None:
        assert evaluate_expression('"" or "fallback"').item() == ""

    def test_or_empty_list_is_truthy(self) -> None:
        assert str(evaluate_expression("[] or [1]")) == "[]"

    def test_and_null_returns_null(self) -> None:
        r = evaluate_expression('null and "hello"')
        assert r.is_null

    def test_and_false_returns_false(self) -> None:
        assert evaluate_expression('false and "hello"').item() is False

    def test_and_truthy_returns_right(self) -> None:
        assert evaluate_expression('"hello" and "world"').item() == "world"

    def test_and_true_returns_right(self) -> None:
        assert evaluate_expression('true and "hello"').item() == "hello"

    def test_or_short_circuits_fail(self) -> None:
        assert evaluate_expression('true or fail("should not reach")').item() is True

    def test_and_short_circuits_fail(self) -> None:
        assert evaluate_expression('null and fail("should not reach")').is_null


class TestConditional:
    def test_if_true(self) -> None:
        assert evaluate_expression("10 if True else 20").item() == 10

    def test_if_false(self) -> None:
        assert evaluate_expression("10 if False else 20").item() == 20

    def test_nested_conditional(self) -> None:
        assert evaluate_expression("1 if False else 2 if False else 3").item() == 3

    def test_conditional_with_expression(self) -> None:
        symtab = SymbolTable({"Param.Quality": "final"})
        assert (
            evaluate_expression("16 if Param.Quality == 'final' else 4", values=symtab).item() == 16
        )


class TestCrossTypeEquality:
    """Tests for cross-type equality comparison."""

    def test_string_eq_path(self, tmp_path) -> None:
        p = tmp_path / "home" / "user"
        symbols = SymbolTable(
            {"s": str(p), "p": ExprValue(str(p), type="path", path_format=HOST_PATH_FORMAT)}
        )
        assert evaluate_expression("s == p", values=symbols).item() is True

    def test_string_eq_int(self) -> None:
        assert evaluate_expression("'5' == 5").item() is False

    def test_bool_eq_int(self) -> None:
        assert evaluate_expression("True == 1").item() is False

    def test_int_eq_list(self) -> None:
        assert evaluate_expression("1 == [1]").item() is False

    def test_int_eq_float(self) -> None:
        assert evaluate_expression("5 == 5.0").item() is True

    def test_list_eq_same(self) -> None:
        assert evaluate_expression("[1, 2] == [1, 2]").item() is True

    def test_nested_list_eq(self) -> None:
        assert evaluate_expression("[[1]] == [[1]]").item() is True

    def test_list_eq_range_expr(self) -> None:
        assert evaluate_expression('[1, 2, 3] == range_expr("1-3")').item() is True

    def test_list_lt(self) -> None:
        assert evaluate_expression("[1, 2] < [1, 3]").item() is True

    def test_list_le_equal(self) -> None:
        assert evaluate_expression("[1, 2] <= [1, 2]").item() is True


class TestCrossTypeInequality:
    """Tests for cross-type inequality comparison."""

    def test_int_lt_float(self) -> None:
        assert evaluate_expression("5 < 5.5").item() is True

    def test_int_le_float_equal(self) -> None:
        assert evaluate_expression("5 <= 5.0").item() is True

    def test_string_lt_path(self, tmp_path) -> None:
        a = tmp_path / "aaa"
        b = tmp_path / "bbb"
        symbols = SymbolTable(
            {"s": str(a), "p": ExprValue(str(b), type="path", path_format=HOST_PATH_FORMAT)}
        )
        assert evaluate_expression("s < p", values=symbols).item() is True


class TestCrossTypeOrderingErrors:
    """Tests that invalid cross-type ordering comparisons raise errors."""

    def test_string_lt_int_errors(self) -> None:
        from openjd.expr import ExpressionError

        with pytest.raises(ExpressionError, match="Cannot use"):
            evaluate_expression('"5" < 5')

    def test_string_gt_int_errors(self) -> None:
        from openjd.expr import ExpressionError

        with pytest.raises(ExpressionError, match="Cannot use"):
            evaluate_expression('"abc" > 123')

    def test_bool_lt_int_errors(self) -> None:
        from openjd.expr import ExpressionError

        with pytest.raises(ExpressionError, match="Cannot use"):
            evaluate_expression("True < 0")

    def test_bool_ordering(self) -> None:
        # False < True (False=0, True=1)
        assert evaluate_expression("False < True").item() is True
        assert evaluate_expression("True > False").item() is True
        assert evaluate_expression("False <= False").item() is True
        assert evaluate_expression("True >= True").item() is True

    def test_int_lt_string_errors(self) -> None:
        from openjd.expr import ExpressionError

        with pytest.raises(ExpressionError, match="Cannot use"):
            evaluate_expression('5 < "5"')

    def test_float_gt_string_errors(self) -> None:
        from openjd.expr import ExpressionError

        with pytest.raises(ExpressionError, match="Cannot use"):
            evaluate_expression('3.14 > "pi"')
