# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for arithmetic and math operations."""

import pytest
from openjd.expr import evaluate_expression, ExpressionError, TypeCode


class TestArithmetic:
    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("1 + 2", 3),
            ("10 - 3", 7),
            ("4 * 5", 20),
            ("10 // 3", 3),
            ("10 % 3", 1),
            ("-5", -5),
            ("+5", 5),
            ("1 + 2 * 3", 7),
            ("(1 + 2) * 3", 9),
        ],
    )
    def test_int_arithmetic(self, expr: str, expected: int) -> None:
        assert evaluate_expression(expr).item() == expected

    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("1.5 + 2.5", 4.0),
            ("5.0 - 1.5", 3.5),
            ("2.0 * 3.0", 6.0),
            ("7.0 / 2.0", 3.5),
        ],
    )
    def test_float_arithmetic(self, expr: str, expected: float) -> None:
        assert evaluate_expression(expr).item() == expected

    def test_float_precision_display(self) -> None:
        # Float display should use round-trip representation like Python
        result = evaluate_expression("0.1 + 0.2")
        assert str(result) == "0.30000000000000004"

    def test_float_passthrough_preserves_original(self) -> None:
        """Float values should preserve original string when only copied (RFC 0005)."""
        from openjd.expr import SymbolTable, ExprValue

        # Create a float with explicit original string representation
        symtab = SymbolTable({"Param": SymbolTable({"V": ExprValue.from_float(3.5, "3.500")})})

        # Just referencing the value should preserve original representation
        result = evaluate_expression("Param.V", values=symtab)
        assert str(result) == "3.500"

    def test_float_passthrough_loses_original_after_operation(self) -> None:
        """Float values should use shortest repr after any operation (RFC 0005)."""
        from openjd.expr import SymbolTable, ExprValue

        symtab = SymbolTable({"Param": SymbolTable({"V": ExprValue.from_float(3.5, "3.500")})})

        # Operation should produce shortest representation
        result = evaluate_expression("Param.V + 0", values=symtab)
        assert str(result) == "3.5"

    def test_int_division_returns_float(self) -> None:
        assert evaluate_expression("10 / 4").item() == 2.5

    def test_division_by_zero(self) -> None:
        with pytest.raises(ExpressionError, match="Division by zero"):
            evaluate_expression("1 / 0")

    def test_modulo_by_zero(self) -> None:
        with pytest.raises(ExpressionError, match="Modulo by zero"):
            evaluate_expression("1 % 0")


class TestFloorDivision:
    """Tests for floor division operator (//)."""

    def test_int_floordiv_returns_int(self) -> None:
        result = evaluate_expression("10 // 3")
        assert result.item() == 3
        assert result.type.type_code == TypeCode.INT

    def test_float_floordiv_returns_int(self) -> None:
        result = evaluate_expression("10.0 // 3.0")
        assert result.item() == 3
        assert result.type.type_code == TypeCode.INT

    def test_float_floordiv_truncates(self) -> None:
        assert evaluate_expression("7.5 // 2.0").item() == 3
        assert evaluate_expression("-7.5 // 2.0").item() == -4

    def test_floordiv_by_zero_int(self) -> None:
        with pytest.raises(ExpressionError, match="Division by zero"):
            evaluate_expression("10 // 0")

    def test_floordiv_by_zero_float(self) -> None:
        with pytest.raises(ExpressionError, match="Division by zero"):
            evaluate_expression("10.0 // 0.0")


class TestPowerOperator:
    """Tests for the ** power operator."""

    def test_int_power_positive_exponent(self) -> None:
        result = evaluate_expression("2 ** 3")
        assert result.item() == 8
        assert result.type.type_code == TypeCode.INT

    def test_int_power_negative_exponent(self) -> None:
        result = evaluate_expression("2 ** (-3)")
        assert result.item() == 0.125
        assert result.type.type_code == TypeCode.FLOAT

    def test_int_power_zero_exponent(self) -> None:
        result = evaluate_expression("5 ** 0")
        assert result.item() == 1

    def test_float_power(self) -> None:
        result = evaluate_expression("2.0 ** 3.0")
        assert result.item() == 8.0
        assert result.type.type_code == TypeCode.FLOAT

    def test_float_power_fractional(self) -> None:
        result = evaluate_expression("4.0 ** 0.5")
        assert result.item() == 2.0

    def test_int_zero_to_negative_power_error(self) -> None:
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("0 ** (-1)")
        expected = [
            "Cannot raise zero to a negative power\n",
            "  0 ** (-1)\n",
            "  ~~^~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_int_zero_to_negative_power_error_large(self) -> None:
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("0 ** (-5)")
        expected = [
            "Cannot raise zero to a negative power\n",
            "  0 ** (-5)\n",
            "  ~~^~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_float_negative_base_fractional_exponent_error(self) -> None:
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("(-2.0) ** 0.5")
        expected = [
            "Cannot compute -2 ** 0.5 (would produce complex number)\n",
            "  (-2.0) ** 0.5\n",
            "  ~~~~~~~^~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_float_negative_one_sqrt_error(self) -> None:
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("(-1.0) ** 0.5")
        expected = [
            "Cannot compute -1 ** 0.5 (would produce complex number)\n",
            "  (-1.0) ** 0.5\n",
            "  ~~~~~~~^~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_float_overflow_error(self) -> None:
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("2.0 ** 1024.0")
        expected = [
            "Overflow computing 2 ** 1024 (result too large for float)\n",
            "  2.0 ** 1024.0\n",
            "  ~~~~^~~~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_float_zero_to_negative_power_error(self) -> None:
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("0.0 ** (-1.0)")
        expected = [
            "Cannot raise zero to a negative power\n",
            "  0.0 ** (-1.0)\n",
            "  ~~~~^~~~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)


class TestMathFunctions:
    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("abs(-5)", 5),
            ("abs(5)", 5),
            ("min(3, 7)", 3),
            ("max(3, 7)", 7),
            ("floor(3.7)", 3),
            ("ceil(3.2)", 4),
            ("round(3.5)", 4),
        ],
    )
    def test_math_functions(self, expr: str, expected: int) -> None:
        assert evaluate_expression(expr).item() == expected


class TestRoundToEven:
    """Tests for round() banker's rounding (round half to even) behavior."""

    @pytest.mark.parametrize(
        "expr,expected",
        [
            # round(x) - single argument
            ("round(0.5)", 0),  # 0.5 rounds to even (0)
            ("round(1.5)", 2),  # 1.5 rounds to even (2)
            ("round(2.5)", 2),  # 2.5 rounds to even (2)
            ("round(3.5)", 4),  # 3.5 rounds to even (4)
            ("round(4.5)", 4),  # 4.5 rounds to even (4)
            ("round(-0.5)", 0),  # -0.5 rounds to even (0)
            ("round(-1.5)", -2),  # -1.5 rounds to even (-2)
            ("round(-2.5)", -2),  # -2.5 rounds to even (-2)
        ],
    )
    def test_round_half_to_even(self, expr: str, expected: int) -> None:
        result = evaluate_expression(expr)
        assert result.item() == expected
        assert result.type.type_code == TypeCode.INT

    @pytest.mark.parametrize(
        "expr,expected",
        [
            # round(x, ndigits) - two arguments
            # Note: Some .5 values can't be exactly represented in binary float,
            # so we test with values that round predictably
            ("round(0.125, 2)", 0.12),  # 0.125 is exact, rounds to even (0.12)
            ("round(0.375, 2)", 0.38),  # 0.375 is exact, rounds to even (0.38)
            ("round(0.625, 2)", 0.62),  # 0.625 is exact, rounds to even (0.62)
            ("round(0.875, 2)", 0.88),  # 0.875 is exact, rounds to even (0.88)
            ("round(0.25, 1)", 0.2),  # 0.25 is exact, rounds to even (0.2)
            ("round(0.75, 1)", 0.8),  # 0.75 is exact, rounds to even (0.8)
            ("round(2.5, 0)", 2.0),  # 2.5 is exact, rounds to even (2.0)
            ("round(3.5, 0)", 4.0),  # 3.5 is exact, rounds to even (4.0)
            # Negative values
            ("round(-0.125, 2)", -0.12),  # -0.125 rounds to even (-0.12)
            ("round(-0.375, 2)", -0.38),  # -0.375 rounds to even (-0.38)
            ("round(-0.25, 1)", -0.2),  # -0.25 rounds to even (-0.2)
            ("round(-0.75, 1)", -0.8),  # -0.75 rounds to even (-0.8)
            ("round(-2.5, 0)", -2.0),  # -2.5 rounds to even (-2.0)
            ("round(-3.5, 0)", -4.0),  # -3.5 rounds to even (-4.0)
        ],
    )
    def test_round_ndigits_half_to_even(self, expr: str, expected: float) -> None:
        result = evaluate_expression(expr)
        assert result.item() == pytest.approx(expected)

    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("round(42, 0)", 42),
            ("round(42, 2)", 42),
            ("round(-7, 1)", -7),
            ("round(11, -1)", 10),
            ("round(155, -1)", 160),
            ("round(155, -2)", 200),
            ("round(150, -2)", 200),  # rounds to even
            ("round(250, -2)", 200),  # rounds to even
        ],
    )
    def test_round_int_ndigits_returns_int(self, expr: str, expected: int) -> None:
        """round(int, ndigits) returns int with rounding applied (RFC 0006)."""
        result = evaluate_expression(expr)
        assert result.item() == expected
        assert result.type.type_code == TypeCode.INT


class TestFloorCeilReturnType:
    """Tests that floor and ceil always return int."""

    def test_floor_float_returns_int(self) -> None:
        result = evaluate_expression("floor(3.7)")
        assert result.item() == 3
        assert result.type.type_code == TypeCode.INT

    def test_floor_int_returns_int(self) -> None:
        result = evaluate_expression("floor(3)")
        assert result.item() == 3
        assert result.type.type_code == TypeCode.INT

    def test_ceil_float_returns_int(self) -> None:
        result = evaluate_expression("ceil(3.2)")
        assert result.item() == 4
        assert result.type.type_code == TypeCode.INT

    def test_ceil_int_returns_int(self) -> None:
        result = evaluate_expression("ceil(3)")
        assert result.item() == 3
        assert result.type.type_code == TypeCode.INT


class TestSum:
    """Tests for sum() function."""

    def test_sum_int_list(self) -> None:
        assert evaluate_expression("sum([1, 2, 3])").item() == 6

    def test_sum_float_list(self) -> None:
        assert evaluate_expression("sum([1.5, 2.5])").item() == 4.0

    def test_sum_empty_list(self) -> None:
        result = evaluate_expression("sum([])")
        assert result.item() == 0
        assert result.type.type_code == TypeCode.INT


class TestFailFunction:
    """Tests for fail() validation function - runtime behavior."""

    def test_fail_raises_error(self) -> None:
        """fail() raises ExpressionError with the message."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression('fail("custom error message")')
        expected = "".join(
            [
                "custom error message\n",
                '  fail("custom error message")\n',
                "  ^~~~~~~~~~~~~~~~~~~~~~~~~~~~",
            ]
        )
        assert str(exc_info.value) == expected

    def test_fail_short_circuit_or_true(self) -> None:
        """true or fail() does not call fail()."""
        assert evaluate_expression('true or fail("should not see")').item() is True

    def test_fail_short_circuit_or_false(self) -> None:
        """false or fail() calls fail()."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression('false or fail("validation failed")')
        expected = "".join(
            [
                "validation failed\n",
                '  false or fail("validation failed")\n',
                "           ^~~~~~~~~~~~~~~~~~~~~~~~~",
            ]
        )
        assert str(exc_info.value) == expected

    def test_fail_short_circuit_and_false(self) -> None:
        """false and fail() does not call fail()."""
        assert evaluate_expression('false and fail("should not see")').item() is False

    def test_fail_short_circuit_and_true(self) -> None:
        """true and fail() calls fail()."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression('true and fail("validation failed")')
        expected = "".join(
            [
                "validation failed\n",
                '  true and fail("validation failed")\n',
                "           ^~~~~~~~~~~~~~~~~~~~~~~~~",
            ]
        )
        assert str(exc_info.value) == expected

    def test_fail_if_else_true_condition(self) -> None:
        """x if true else fail() returns x."""
        assert evaluate_expression('1.5 if true else fail("should not see")').item() == 1.5

    def test_fail_if_else_false_condition(self) -> None:
        """x if false else fail() calls fail()."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression('1 if false else fail("condition was false")')
        expected = "".join(
            [
                "condition was false\n",
                '  1 if false else fail("condition was false")\n',
                "                  ^~~~~~~~~~~~~~~~~~~~~~~~~~~",
            ]
        )
        assert str(exc_info.value) == expected

    def test_fail_in_then_true_condition(self) -> None:
        """fail() if true else x calls fail()."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression('fail("condition was true") if true else 1')
        expected = "".join(
            [
                "condition was true\n",
                '  fail("condition was true") if true else 1\n',
                "  ^~~~~~~~~~~~~~~~~~~~~~~~~~",
            ]
        )
        assert str(exc_info.value) == expected

    def test_fail_in_then_false_condition(self) -> None:
        """fail() if false else x returns x."""
        assert evaluate_expression('fail("should not see") if false else 2.5').item() == 2.5

    def test_fail_validation_pattern(self) -> None:
        """Common validation pattern: condition or fail()."""
        assert evaluate_expression('5 > 0 or fail("must be positive")').item() is True
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression('-1 > 0 or fail("must be positive")')
        expected = "".join(
            [
                "must be positive\n",
                '  -1 > 0 or fail("must be positive")\n',
                "            ^~~~~~~~~~~~~~~~~~~~~~~~",
            ]
        )
        assert str(exc_info.value) == expected

    def test_fail_if_else_various_types(self) -> None:
        """fail() in else branch preserves exact type for int, string."""
        assert evaluate_expression('42 if true else fail("error")').item() == 42
        assert evaluate_expression('"hello" if true else fail("error")').item() == "hello"

    def test_fail_both_branches(self) -> None:
        """fail() if cond else fail() raises."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression('fail("then") if true else fail("else")')
        expected = "".join(
            [
                "then\n",
                '  fail("then") if true else fail("else")\n',
                "  ^~~~~~~~~~~~",
            ]
        )
        assert str(exc_info.value) == expected


class TestFloatSanitization:
    """Tests that nan, inf, and -0.0 are handled per spec."""

    def test_overflow_to_infinity(self) -> None:
        with pytest.raises(ExpressionError, match="infinity"):
            evaluate_expression("1e300 * 1e300")

    def test_literal_infinity(self) -> None:
        with pytest.raises(ExpressionError, match="infinity"):
            evaluate_expression("1e3000")

    def test_float_from_inf_string(self) -> None:
        with pytest.raises(ExpressionError, match="Cannot convert"):
            evaluate_expression("float('inf')")

    def test_float_from_nan_string(self) -> None:
        with pytest.raises(ExpressionError, match="Cannot convert"):
            evaluate_expression("float('nan')")

    def test_negative_zero_normalized(self) -> None:
        assert str(evaluate_expression("-0.0")) == "0.0"

    def test_negative_zero_from_arithmetic(self) -> None:
        assert str(evaluate_expression("-1.0 * 0.0")) == "0.0"

    def test_abs_negative_zero(self) -> None:
        assert str(evaluate_expression("abs(-0.0)")) == "0.0"

    def test_negative_zero_equals_zero(self) -> None:
        assert evaluate_expression("-0.0 == 0.0").item() is True
