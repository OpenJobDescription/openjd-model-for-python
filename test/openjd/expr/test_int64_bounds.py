# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for 64-bit signed integer bounds enforcement."""

import pytest
from openjd.expr import evaluate_expression, ExpressionError


class TestInt64ValidBounds:
    """INT64_MIN and INT64_MAX are valid values."""

    def test_int64_max_literal(self) -> None:
        result = evaluate_expression("9223372036854775807")
        assert result.item() == 9223372036854775807

    def test_int64_min_literal(self) -> None:
        result = evaluate_expression("-9223372036854775808")
        assert result.item() == -9223372036854775808

    def test_int64_min_plus_max_is_negative_one(self) -> None:
        result = evaluate_expression("-9223372036854775808 + 9223372036854775807")
        assert result.item() == -1


class TestInt64OverflowLiterals:
    """Integer literals outside 64-bit range are errors."""

    def test_positive_literal_overflow(self) -> None:
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("9223372036854775808")
        expected = "".join(
            [
                "Integer overflow: result is outside the 64-bit signed range\n",
                "  9223372036854775808\n",
                "  ^~~~~~~~~~~~~~~~~~~",
            ]
        )
        assert str(exc_info.value) == expected

    def test_negative_literal_overflow(self) -> None:
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("-9223372036854775809")
        expected = "".join(
            [
                "Integer overflow: result is outside the 64-bit signed range\n",
                "  -9223372036854775809\n",
                "  ^~~~~~~~~~~~~~~~~~~~",
            ]
        )
        assert str(exc_info.value) == expected


class TestInt64OverflowArithmetic:
    """Arithmetic that exceeds 64-bit range is an error."""

    def test_addition_overflow(self) -> None:
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("9223372036854775807 + 1")
        expected = "".join(
            [
                "Integer overflow: result is outside the 64-bit signed range\n",
                "  9223372036854775807 + 1\n",
                "  ~~~~~~~~~~~~~~~~~~~~^~~",
            ]
        )
        assert str(exc_info.value) == expected

    def test_subtraction_overflow(self) -> None:
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("-9223372036854775808 - 1")
        expected = "".join(
            [
                "Integer overflow: result is outside the 64-bit signed range\n",
                "  -9223372036854775808 - 1\n",
                "  ~~~~~~~~~~~~~~~~~~~~~^~~",
            ]
        )
        assert str(exc_info.value) == expected

    def test_multiplication_overflow_positive(self) -> None:
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("4611686018427387905 * 2")
        expected = "".join(
            [
                "Integer overflow: result is outside the 64-bit signed range\n",
                "  4611686018427387905 * 2\n",
                "  ~~~~~~~~~~~~~~~~~~~~^~~",
            ]
        )
        assert str(exc_info.value) == expected

    def test_multiplication_overflow_negative(self) -> None:
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("-4611686018427387905 * 2")
        expected = "".join(
            [
                "Integer overflow: result is outside the 64-bit signed range\n",
                "  -4611686018427387905 * 2\n",
                "  ~~~~~~~~~~~~~~~~~~~~~^~~",
            ]
        )
        assert str(exc_info.value) == expected


class TestInt64OverflowPow:
    """Power operations that exceed 64-bit range are errors."""

    def test_pow_overflow(self) -> None:
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("2 ** 64")
        expected = "".join(
            [
                "Integer overflow: result is outside the 64-bit signed range\n",
                "  2 ** 64\n",
                "  ~~^~~~~",
            ]
        )
        assert str(exc_info.value) == expected

    def test_pow_overflow_large_exponent(self) -> None:
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("2 ** 1000000")
        expected = "".join(
            [
                "Integer overflow: result is outside the 64-bit signed range\n",
                "  2 ** 1000000\n",
                "  ~~^~~~~~~~~~",
            ]
        )
        assert str(exc_info.value) == expected


class TestInt64OverflowConversion:
    """Type conversions that exceed 64-bit range are errors."""

    def test_float_to_int_overflow(self) -> None:
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("int(9.3e18)")
        expected = "".join(
            [
                "Integer overflow: result is outside the 64-bit signed range\n",
                "  int(9.3e18)\n",
                "  ^~~~~~~~~~~",
            ]
        )
        assert str(exc_info.value) == expected


class TestInt64FloatUnaffected:
    """Float values outside int64 range are valid."""

    def test_large_positive_float(self) -> None:
        result = evaluate_expression("9223372036854775808.0")
        assert str(result) == "9223372036854775808.0"

    def test_large_negative_float(self) -> None:
        # Unary negation removes pass-through, so shortest repr
        result = evaluate_expression("-9223372036854775809.0")
        assert str(result) == "-9.223372036854776e+18"
