# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for type system: literals, conversions, and JSON compatibility."""

import pytest
from openjd.expr import evaluate_expression, SymbolTable, ExpressionError


class TestLiteralTypes:
    """Tests confirming types of literal expressions."""

    def test_empty_list_type(self) -> None:
        assert str(evaluate_expression("[]").type) == "list[nulltype]"

    def test_int_list_type(self) -> None:
        assert str(evaluate_expression("[1, 2, 3]").type) == "list[int]"

    def test_float_list_type(self) -> None:
        assert str(evaluate_expression("[1.0, 2.0]").type) == "list[float]"

    def test_string_list_type(self) -> None:
        assert str(evaluate_expression("['a', 'b']").type) == "list[string]"

    def test_bool_list_type(self) -> None:
        assert str(evaluate_expression("[True, False]").type) == "list[bool]"

    def test_nested_list_type(self) -> None:
        symtab = SymbolTable({"nested": [[1, 2], [3, 4]]})
        assert str(evaluate_expression("nested", values=symtab).type) == "list[list[int]]"

    def test_int_type(self) -> None:
        assert str(evaluate_expression("42").type) == "int"

    def test_float_type(self) -> None:
        assert str(evaluate_expression("3.14").type) == "float"

    def test_string_type(self) -> None:
        assert str(evaluate_expression("'hello'").type) == "string"

    def test_bool_type(self) -> None:
        assert str(evaluate_expression("True").type) == "bool"

    def test_null_type(self) -> None:
        assert str(evaluate_expression("null").type) == "nulltype"

    def test_none_type(self) -> None:
        assert str(evaluate_expression("None").type) == "nulltype"


class TestJsonLiterals:
    def test_null(self) -> None:
        assert evaluate_expression("null").is_null is True

    def test_true(self) -> None:
        assert evaluate_expression("true").item() is True

    def test_false(self) -> None:
        assert evaluate_expression("false").item() is False

    def test_mixed_with_python_style(self) -> None:
        assert evaluate_expression("true if True else false").item() is True


class TestTypeConversion:
    """Tests for type conversion functions."""

    def test_string_from_string(self) -> None:
        assert evaluate_expression('string("abc")').item() == "abc"

    def test_int_from_int(self) -> None:
        assert evaluate_expression("int(42)").item() == 42

    def test_float_from_float(self) -> None:
        assert evaluate_expression("float(3.14)").item() == 3.14

    def test_bool_from_bool(self) -> None:
        assert evaluate_expression("bool(True)").item() is True
        assert evaluate_expression("bool(False)").item() is False
        assert evaluate_expression("bool(true)").item() is True
        assert evaluate_expression("bool(false)").item() is False

    def test_bool_from_null(self) -> None:
        assert evaluate_expression("bool(null)").item() is False
        assert evaluate_expression("bool(None)").item() is False

    def test_bool_from_int(self) -> None:
        assert evaluate_expression("bool(0)").item() is False
        assert evaluate_expression("bool(1)").item() is True
        assert evaluate_expression("bool(-1)").item() is True

    def test_bool_from_float(self) -> None:
        assert evaluate_expression("bool(0.0)").item() is False
        assert evaluate_expression("bool(1.0)").item() is True

    def test_bool_from_string_true(self) -> None:
        for s in ["1", "true", "TRUE", "on", "yes"]:
            assert evaluate_expression(f'bool("{s}")').item() is True

    def test_bool_from_string_false(self) -> None:
        for s in ["0", "false", "FALSE", "off", "no"]:
            assert evaluate_expression(f'bool("{s}")').item() is False

    def test_bool_from_string_invalid(self) -> None:
        with pytest.raises(ExpressionError, match="Cannot convert"):
            evaluate_expression('bool("invalid")')

    def test_bool_from_path_rejected(self) -> None:
        with pytest.raises(ExpressionError, match="Cannot convert path"):
            evaluate_expression('bool(path("/tmp"))')

    def test_bool_from_list_rejected(self) -> None:
        with pytest.raises(ExpressionError, match="Cannot convert list"):
            evaluate_expression("bool([1, 2, 3])")

    def test_string_from_int(self) -> None:
        assert evaluate_expression("string(42)").item() == "42"

    def test_string_from_bool(self) -> None:
        assert evaluate_expression("string(True)").item() == "true"

    def test_string_from_null(self) -> None:
        assert evaluate_expression("string(null)").item() == "null"
        assert evaluate_expression("string(None)").item() == "null"

    def test_string_from_list_int(self) -> None:
        assert evaluate_expression("string([1, 2, 3])").item() == "[1, 2, 3]"

    def test_string_from_list_string(self) -> None:
        assert evaluate_expression("string(['a', 'b', 'c'])").item() == '["a", "b", "c"]'

    def test_string_from_list_float(self) -> None:
        assert evaluate_expression("string([1.5, 2.5])").item() == "[1.5, 2.5]"

    def test_string_from_list_bool(self) -> None:
        assert evaluate_expression("string([true, false])").item() == "[true, false]"

    def test_string_from_list_nested(self) -> None:
        assert evaluate_expression("string([[1, 2], [3, 4]])").item() == "[[1, 2], [3, 4]]"

    def test_string_from_list_empty(self) -> None:
        assert evaluate_expression("string([])").item() == "[]"

    def test_int_from_string(self) -> None:
        assert evaluate_expression("int('42')").item() == 42

    def test_int_from_string_invalid(self) -> None:
        with pytest.raises(ExpressionError, match="Cannot convert"):
            evaluate_expression("int('abc')")

    def test_float_from_int(self) -> None:
        assert evaluate_expression("float(42)").item() == 42.0
