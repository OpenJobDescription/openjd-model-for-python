# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for list operations including concatenation and comprehensions."""

from __future__ import annotations

import pytest
from openjd.expr import evaluate_expression, SymbolTable, ExpressionError, ExprValue
from openjd.expr import ExprType
from openjd.expr import PathFormat

INT = ExprType("int")
FLOAT = ExprType("float")
STRING = ExprType("string")
PATH = ExprType("path")


def _eval_with_target(expr: str, target_type: ExprType | None, path_format=None):
    """Evaluate expression with a specific target type."""
    return evaluate_expression(expr, target_type=target_type, path_format=path_format)


class TestListLiteralTypeInference:
    """Tests for natural type inference of list literals without target type (RFC 0005)."""

    # Homogeneous lists
    def test_all_int(self) -> None:
        assert str(evaluate_expression("[1, 2, 3]").type) == "list[int]"

    def test_all_float(self) -> None:
        assert str(evaluate_expression("[1.0, 2.0]").type) == "list[float]"

    def test_all_string(self) -> None:
        assert str(evaluate_expression('["a", "b"]').type) == "list[string]"

    def test_all_bool(self) -> None:
        assert str(evaluate_expression("[True, False]").type) == "list[bool]"

    # int/float promotion
    def test_int_float_promotes_to_float(self) -> None:
        result = evaluate_expression("[1, 2.0]")
        assert str(result.type) == "list[float]"
        assert result.item() == [1.0, 2.0]

    def test_float_int_promotes_to_float(self) -> None:
        result = evaluate_expression("[1.0, 2]")
        assert str(result.type) == "list[float]"

    # Nested lists
    def test_nested_same_type(self) -> None:
        assert str(evaluate_expression("[[1], [2, 3]]").type) == "list[list[int]]"

    def test_nested_int_float_promotes(self) -> None:
        assert str(evaluate_expression("[[1], [2.0]]").type) == "list[list[float]]"

    def test_nested_int_float_coerces_values(self) -> None:
        """Inner list[int] elements must be coerced to list[float] (evaluator path)."""
        result = evaluate_expression("[[1], [2.0]]")
        inner = result.item()
        assert isinstance(inner[0][0], float)
        assert inner[0] == [1.0]
        assert inner[1] == [2.0]

    # path/string promotion
    def test_path_string_promotes_to_string(self) -> None:
        result = evaluate_expression('[path("/a"), "b"]', path_format=PathFormat.POSIX)
        assert str(result.type) == "list[string]"
        assert result.item() == ["/a", "b"]

    def test_nested_path_string_promotes(self) -> None:
        result = evaluate_expression('[[path("/a")], ["b"]]')
        assert str(result.type) == "list[list[string]]"

    def test_nested_path_string_coerces_values(self) -> None:
        """Inner list[path] elements must be coerced to list[string] (evaluator path)."""
        import sys

        result = evaluate_expression('[[path("/a")], ["b"]]')
        inner = result.item()
        assert isinstance(inner[0][0], str)
        expected_path = "\\a" if sys.platform == "win32" else "/a"
        assert inner[0] == [expected_path]
        assert inner[1] == ["b"]

    # Error cases - null in list
    def test_null_in_list_fails(self) -> None:
        with pytest.raises(ExpressionError, match="null is not allowed"):
            evaluate_expression("[1, null]")

    def test_none_in_list_fails(self) -> None:
        with pytest.raises(ExpressionError, match="null is not allowed"):
            evaluate_expression("[None, 'a']")

    # Error cases - incompatible types
    def test_int_string_fails(self) -> None:
        with pytest.raises(ExpressionError, match="incompatible types.*int.*string"):
            evaluate_expression("[1, 'a']")

    def test_int_bool_fails(self) -> None:
        with pytest.raises(ExpressionError, match="incompatible types.*int.*bool"):
            evaluate_expression("[1, True]")

    def test_string_bool_fails(self) -> None:
        with pytest.raises(ExpressionError, match="incompatible types.*string.*bool"):
            evaluate_expression('["a", True]')

    def test_scalar_list_fails(self) -> None:
        with pytest.raises(ExpressionError, match="incompatible types.*int.*list"):
            evaluate_expression("[1, [2]]")

    def test_three_incompatible_types_fails(self) -> None:
        with pytest.raises(ExpressionError, match="incompatible types.*int.*float.*string"):
            evaluate_expression('[1, 2.0, "a"]')

    def test_path_int_fails(self) -> None:
        with pytest.raises(ExpressionError, match="incompatible types.*path.*int"):
            evaluate_expression('[path("/a"), 1]')

    def test_three_level_nesting_fails(self) -> None:
        with pytest.raises(ExpressionError, match="nested at most 2 levels"):
            evaluate_expression("[[[1, 2]]]")

    def test_three_level_nesting_in_comprehension_fails(self) -> None:
        with pytest.raises(ExpressionError, match="nested at most 2 levels"):
            evaluate_expression("[[[x]] for x in [1, 2]]")


class TestListElementCoercion:
    """Tests for list element coercion when target type has single list type (RFC 0005)."""

    # -> list[string]
    def test_int_to_string(self) -> None:
        result = _eval_with_target("[1, 2, 3]", ExprType("list[string]"))
        assert str(result.type) == "list[string]"
        assert result.item() == ["1", "2", "3"]

    def test_float_to_string(self) -> None:
        result = _eval_with_target("[1.5, 2.0]", ExprType("list[string]"))
        assert str(result.type) == "list[string]"
        assert result.item() == ["1.5", "2.0"]

    def test_bool_to_string(self) -> None:
        result = _eval_with_target("[True, False]", ExprType("list[string]"))
        assert str(result.type) == "list[string]"
        assert result.item() == ["true", "false"]

    def test_path_to_string(self) -> None:
        result = _eval_with_target(
            '[path("/a"), path("/b")]',
            ExprType("list[string]"),
            path_format=PathFormat.POSIX,
        )
        assert str(result.type) == "list[string]"
        assert [str(p) for p in result.item()] == ["/a", "/b"]

    # -> list[path]
    def test_string_to_path(self) -> None:
        result = _eval_with_target(
            '["/a", "/b"]',
            ExprType("list[path]"),
            path_format=PathFormat.POSIX,
        )
        assert str(result.type) == "list[path]"
        assert [str(p) for p in result.item()] == ["/a", "/b"]

    # -> list[int]
    def test_float_to_int_exact(self) -> None:
        result = _eval_with_target("[1.0, 2.0, 3.0]", ExprType("list[int]"))
        assert str(result.type) == "list[int]"
        assert result.item() == [1, 2, 3]

    def test_float_to_int_not_exact(self) -> None:
        with pytest.raises(ExpressionError, match="not a whole number"):
            _eval_with_target("[1.5]", ExprType("list[int]"))

    def test_string_to_int_valid(self) -> None:
        result = _eval_with_target('["1", "2", "3"]', ExprType("list[int]"))
        assert str(result.type) == "list[int]"
        assert result.item() == [1, 2, 3]

    def test_string_to_int_invalid(self) -> None:
        with pytest.raises(ExpressionError, match="Cannot co"):
            _eval_with_target('["abc"]', ExprType("list[int]"))

    def test_string_to_int_float_string(self) -> None:
        with pytest.raises(ExpressionError, match="Cannot co"):
            _eval_with_target('["3.1"]', ExprType("list[int]"))

    # -> list[float]
    def test_int_to_float(self) -> None:
        result = _eval_with_target("[1, 2, 3]", ExprType("list[float]"))
        assert str(result.type) == "list[float]"
        assert result.item() == [1.0, 2.0, 3.0]

    def test_string_to_float_valid(self) -> None:
        result = _eval_with_target('["1.5", "2.0"]', ExprType("list[float]"))
        assert str(result.type) == "list[float]"
        assert result.item() == [1.5, 2.0]

    def test_string_to_float_invalid(self) -> None:
        with pytest.raises(ExpressionError, match="Cannot co"):
            _eval_with_target('["abc"]', ExprType("list[float]"))

    # bool cannot coerce to int/float/path
    def test_bool_to_int_fails(self) -> None:
        with pytest.raises(ExpressionError, match="Cannot co"):
            _eval_with_target("[True]", ExprType("list[int]"))

    def test_bool_to_float_fails(self) -> None:
        with pytest.raises(ExpressionError, match="Cannot co"):
            _eval_with_target("[False]", ExprType("list[float]"))

    def test_bool_to_path_fails(self) -> None:
        with pytest.raises(ExpressionError, match="Cannot co"):
            _eval_with_target("[True]", ExprType("list[path]"))

    # Mixed types in list with coercion
    def test_mixed_int_string_to_string(self) -> None:
        result = _eval_with_target('["--quality", 5]', ExprType("list[string]"))
        assert str(result.type) == "list[string]"
        assert result.item() == ["--quality", "5"]

    # No coercion when no target or multiple list types
    def test_no_target_keeps_original_type(self) -> None:
        result = _eval_with_target("[1, 2, 3]", None)
        assert str(result.type) == "list[int]"


class TestNestedListElementCoercion:
    """Tests for recursive list element coercion with list[list[T]] (RFC 0005)."""

    # -> list[list[string]] with mixed input types
    def test_nested_mixed_to_string(self) -> None:
        list_list_string = ExprType("list[list[string]]")
        result = _eval_with_target(
            '[[1, 2.5, True, path("/a")], ["already"]]',
            list_list_string,
            path_format=PathFormat.POSIX,
        )
        assert str(result.type) == "list[list[string]]"
        assert result.item() == [
            ["1", "2.5", "true", "/a"],
            ["already"],
        ]

    # -> list[list[path]] from strings
    def test_nested_string_to_path(self) -> None:
        list_list_path = ExprType("list[list[path]]")
        result = _eval_with_target('[["/a", "/b"], ["/c"]]', list_list_path)
        assert str(result.type) == "list[list[path]]"

    # -> list[list[int]] with mixed int-convertible types
    def test_nested_mixed_to_int(self) -> None:
        list_list_int = ExprType("list[list[int]]")
        result = _eval_with_target('[["1", 2.0, 3], ["4"]]', list_list_int)
        assert str(result.type) == "list[list[int]]"
        assert result.item() == [
            [1, 2, 3],
            [4],
        ]

    # -> list[list[float]] with mixed float-convertible types
    def test_nested_mixed_to_float(self) -> None:
        list_list_float = ExprType("list[list[float]]")
        result = _eval_with_target('[[1, "2.5", 3.0], ["4"]]', list_list_float)
        assert str(result.type) == "list[list[float]]"
        assert result.item() == [
            [1.0, 2.5, 3.0],
            [4.0],
        ]

    # Error cases
    def test_nested_float_to_int_not_exact(self) -> None:
        list_list_int = ExprType("list[list[int]]")
        with pytest.raises(ExpressionError, match="not a whole number"):
            _eval_with_target("[[1.5]]", list_list_int)

    def test_nested_string_to_int_invalid(self) -> None:
        list_list_int = ExprType("list[list[int]]")
        with pytest.raises(ExpressionError, match="Cannot co"):
            _eval_with_target('[["abc"]]', list_list_int)

    def test_nested_string_to_int_float_string(self) -> None:
        list_list_int = ExprType("list[list[int]]")
        with pytest.raises(ExpressionError, match="Cannot co"):
            _eval_with_target('[["3.1"]]', list_list_int)

    def test_nested_string_to_float_invalid(self) -> None:
        list_list_float = ExprType("list[list[float]]")
        with pytest.raises(ExpressionError, match="Cannot co"):
            _eval_with_target('[["not a number"]]', list_list_float)

    def test_nested_bool_to_int_fails(self) -> None:
        list_list_int = ExprType("list[list[int]]")
        with pytest.raises(ExpressionError, match="Cannot co"):
            _eval_with_target("[[True]]", list_list_int)

    def test_nested_bool_to_float_fails(self) -> None:
        list_list_float = ExprType("list[list[float]]")
        with pytest.raises(ExpressionError, match="Cannot co"):
            _eval_with_target("[[False]]", list_list_float)

    def test_nested_bool_to_path_fails(self) -> None:
        list_list_path = ExprType("list[list[path]]")
        with pytest.raises(ExpressionError, match="Cannot co"):
            _eval_with_target("[[True]]", list_list_path)


class TestLists:
    def test_list_literal(self) -> None:
        result = evaluate_expression("[1, 2, 3]")
        assert result.item() == [1, 2, 3]

    def test_list_trailing_comma(self) -> None:
        """Trailing comma in list literal is allowed."""
        result = evaluate_expression("[1, 2, 3,]")
        assert result.item() == [1, 2, 3]

    def test_list_single_element_trailing_comma(self) -> None:
        """Single element with trailing comma."""
        result = evaluate_expression("[42,]")
        assert result.item() == [42]

    def test_subscript_positive(self) -> None:
        assert evaluate_expression("[10, 20, 30][1]").item() == 20

    def test_subscript_negative(self) -> None:
        assert evaluate_expression("[10, 20, 30][-1]").item() == 30

    def test_subscript_out_of_bounds(self) -> None:
        with pytest.raises(ExpressionError, match="out of bounds"):
            evaluate_expression("[1, 2, 3][10]")


class TestListComprehension:
    def test_simple_comprehension(self) -> None:
        result = evaluate_expression("[x * 2 for x in [1, 2, 3]]")
        assert result.item() == [2, 4, 6]

    def test_comprehension_with_filter(self) -> None:
        result = evaluate_expression("[x for x in [1, 2, 3, 4, 5] if x > 2]")
        assert result.item() == [3, 4, 5]

    def test_comprehension_with_outer_variable(self) -> None:
        symtab = SymbolTable({"Param.Base": 100})
        result = evaluate_expression("[Param.Base + i for i in [1, 2, 3]]", values=symtab)
        assert result.item() == [101, 102, 103]

    def test_string_comprehension(self) -> None:
        result = evaluate_expression("[s.upper() for s in ['a', 'b', 'c']]")
        assert result.item() == ["A", "B", "C"]


class TestListConcatenation:
    """Tests for list concatenation with type coercion (RFC 0006)."""

    def test_list_concat_int(self) -> None:
        result = evaluate_expression("[1, 2] + [3, 4]")
        assert result.item() == [1, 2, 3, 4]
        assert str(result.type) == "list[int]"

    def test_list_concat_int_float(self) -> None:
        result = evaluate_expression("[1, 2] + [3.0, 4.0]")
        assert result.item() == [1.0, 2.0, 3.0, 4.0]
        assert str(result.type) == "list[float]"

    def test_list_concat_float_int(self) -> None:
        result = evaluate_expression("[1.0, 2.0] + [3, 4]")
        assert result.item() == [1.0, 2.0, 3.0, 4.0]
        assert str(result.type) == "list[float]"

    def test_list_concat_empty_left(self) -> None:
        result = evaluate_expression("[] + [1, 2, 3]")
        assert result.item() == [1, 2, 3]

    def test_list_concat_empty_right(self) -> None:
        result = evaluate_expression("[1, 2, 3] + []")
        assert result.item() == [1, 2, 3]

    def test_list_concat_both_empty(self) -> None:
        result = evaluate_expression("[] + []")
        assert result.item() == []
        assert str(result.type) == "list[nulltype]"

    def test_range_expr_concat_list(self) -> None:
        result = evaluate_expression("range_expr('1-3') + [10, 11]")
        assert result.item() == [1, 2, 3, 10, 11]

    def test_list_concat_range_expr(self) -> None:
        result = evaluate_expression("[10, 11] + range_expr('1-3')")
        assert result.item() == [10, 11, 1, 2, 3]

    def test_list_float_concat_range_expr(self) -> None:
        result = evaluate_expression("[10.5, 11.5] + range_expr('1-3')")
        assert result.item() == [10.5, 11.5, 1.0, 2.0, 3.0]
        assert str(result.type) == "list[float]"

    def test_range_expr_concat_range_expr(self) -> None:
        result = evaluate_expression("range_expr('1-3') + range_expr('10-12')")
        assert result.item() == [1, 2, 3, 10, 11, 12]

    def test_range_expr_concat_list_float(self) -> None:
        result = evaluate_expression("range_expr('1-3') + [10.5, 11.5]")
        assert result.item() == [1.0, 2.0, 3.0, 10.5, 11.5]
        assert str(result.type) == "list[float]"

    def test_comprehension_concat_list(self) -> None:
        result = evaluate_expression("[x * 2 for x in [1, 2, 3]] + [100]")
        assert result.item() == [2, 4, 6, 100]

    def test_chained_concat(self) -> None:
        result = evaluate_expression("[1] + [2] + [3]")
        assert result.item() == [1, 2, 3]

    def test_incompatible_types_string_int(self) -> None:
        with pytest.raises(ExpressionError, match="Cannot concatenate"):
            evaluate_expression("['a', 'b'] + [1, 2]")

    def test_concat_with_symtab(self) -> None:
        symtab = SymbolTable({"a": [1, 2], "b": [3, 4]})
        result = evaluate_expression("a + b", values=symtab)
        assert result.item() == [1, 2, 3, 4]

    def test_concat_symtab_range_expr(self) -> None:
        from openjd.expr import RangeExpr

        symtab = SymbolTable({"frames": RangeExpr("1-5"), "extra": [100, 200]})
        result = evaluate_expression("frames + extra", values=symtab)
        assert result.item() == [1, 2, 3, 4, 5, 100, 200]

    def test_list_concat_path_string(self) -> None:
        """list[path] + list[string] -> list[string] (path coerced to string)."""
        result = evaluate_expression(
            '[path("/foo"), path("/bar")] + ["baz", "qux"]',
            path_format=PathFormat.POSIX,
        )
        assert result.item() == ["/foo", "/bar", "baz", "qux"]
        assert str(result.type) == "list[string]"

    def test_list_concat_string_path(self) -> None:
        """list[string] + list[path] -> list[string] (path coerced to string)."""
        result = evaluate_expression(
            '["foo", "bar"] + [path("/baz"), path("/qux")]',
            path_format=PathFormat.POSIX,
        )
        assert result.item() == ["foo", "bar", "/baz", "/qux"]
        assert str(result.type) == "list[string]"


class TestListMembership:
    """Tests for the in/not in operators."""

    def test_int_in_list(self) -> None:
        assert evaluate_expression("3 in [1, 2, 3, 4, 5]").item() is True

    def test_int_not_in_list(self) -> None:
        assert evaluate_expression("6 in [1, 2, 3, 4, 5]").item() is False

    def test_string_in_list(self) -> None:
        assert evaluate_expression('"b" in ["a", "b", "c"]').item() is True

    def test_string_not_in_list(self) -> None:
        assert evaluate_expression('"z" in ["a", "b", "c"]').item() is False

    def test_not_in_operator_true(self) -> None:
        assert evaluate_expression("6 not in [1, 2, 3]").item() is True

    def test_not_in_operator_false(self) -> None:
        assert evaluate_expression("2 not in [1, 2, 3]").item() is False

    def test_float_in_list(self) -> None:
        assert evaluate_expression("2.5 in [1.0, 2.5, 3.0]").item() is True

    def test_bool_in_list(self) -> None:
        assert evaluate_expression("True in [False, True]").item() is True
        assert evaluate_expression("False in [True, True]").item() is False

    def test_path_in_list(self) -> None:
        symtab = SymbolTable(
            {
                "paths": ExprValue(
                    [
                        ExprValue("/a", type="path", path_format=PathFormat.POSIX),
                        ExprValue("/b", type="path", path_format=PathFormat.POSIX),
                    ]
                ),
                "p": ExprValue("/b", type="path", path_format=PathFormat.POSIX),
            }
        )
        assert (
            evaluate_expression("p in paths", values=symtab, path_format=PathFormat.POSIX).item()
            is True
        )

    def test_path_not_in_list(self) -> None:
        symtab = SymbolTable(
            {
                "paths": ExprValue(
                    [
                        ExprValue("/a", type="path", path_format=PathFormat.POSIX),
                        ExprValue("/b", type="path", path_format=PathFormat.POSIX),
                    ]
                ),
                "p": ExprValue("/c", type="path", path_format=PathFormat.POSIX),
            }
        )
        assert (
            evaluate_expression("p in paths", values=symtab, path_format=PathFormat.POSIX).item()
            is False
        )


class TestSortedReversed:
    """Tests for sorted() and reversed() functions."""

    # sorted() tests
    def test_sorted_int_list(self) -> None:
        result = evaluate_expression("sorted([3, 1, 4, 1, 5, 9, 2, 6])")
        assert result.item() == [1, 1, 2, 3, 4, 5, 6, 9]
        assert str(result.type) == "list[int]"

    def test_sorted_float_list(self) -> None:
        result = evaluate_expression("sorted([3.5, 1.2, 2.8])")
        assert result.item() == [1.2, 2.8, 3.5]
        assert str(result.type) == "list[float]"

    def test_sorted_string_list(self) -> None:
        result = evaluate_expression('sorted(["banana", "apple", "cherry"])')
        assert result.item() == ["apple", "banana", "cherry"]
        assert str(result.type) == "list[string]"

    def test_sorted_empty_list(self) -> None:
        result = evaluate_expression("sorted([])")
        assert result.item() == []

    def test_sorted_single_element(self) -> None:
        result = evaluate_expression("sorted([42])")
        assert result.item() == [42]

    def test_sorted_already_sorted(self) -> None:
        result = evaluate_expression("sorted([1, 2, 3])")
        assert result.item() == [1, 2, 3]

    def test_sorted_reverse_order(self) -> None:
        result = evaluate_expression("sorted([5, 4, 3, 2, 1])")
        assert result.item() == [1, 2, 3, 4, 5]

    def test_sorted_with_duplicates(self) -> None:
        result = evaluate_expression("sorted([3, 1, 2, 1, 3])")
        assert result.item() == [1, 1, 2, 3, 3]

    def test_sorted_method_syntax(self) -> None:
        result = evaluate_expression("[3, 1, 2].sorted()")
        assert result.item() == [1, 2, 3]

    # reversed() tests
    def test_reversed_int_list(self) -> None:
        result = evaluate_expression("reversed([1, 2, 3, 4, 5])")
        assert result.item() == [5, 4, 3, 2, 1]
        assert str(result.type) == "list[int]"

    def test_reversed_float_list(self) -> None:
        result = evaluate_expression("reversed([1.1, 2.2, 3.3])")
        assert result.item() == [3.3, 2.2, 1.1]
        assert str(result.type) == "list[float]"

    def test_reversed_string_list(self) -> None:
        result = evaluate_expression('reversed(["a", "b", "c"])')
        assert result.item() == ["c", "b", "a"]
        assert str(result.type) == "list[string]"

    def test_reversed_empty_list(self) -> None:
        result = evaluate_expression("reversed([])")
        assert result.item() == []

    def test_reversed_single_element(self) -> None:
        result = evaluate_expression("reversed([42])")
        assert result.item() == [42]

    def test_reversed_method_syntax(self) -> None:
        result = evaluate_expression("[1, 2, 3].reversed()")
        assert result.item() == [3, 2, 1]

    # Combined tests
    def test_sorted_then_reversed(self) -> None:
        result = evaluate_expression("reversed(sorted([3, 1, 2]))")
        assert result.item() == [3, 2, 1]

    def test_reversed_then_sorted(self) -> None:
        result = evaluate_expression("sorted(reversed([3, 1, 2]))")
        assert result.item() == [1, 2, 3]

    def test_sorted_chained_method(self) -> None:
        result = evaluate_expression("[3, 1, 2].sorted().reversed()")
        assert result.item() == [3, 2, 1]


class TestUnique:
    """Tests for unique() function — deduplication preserving first occurrence order."""

    def test_unique_int(self) -> None:
        result = evaluate_expression("unique([3, 1, 2, 1, 3, 2])")
        assert result.item() == [3, 1, 2]
        assert result.type == ExprType("list[int]")

    def test_unique_string(self) -> None:
        result = evaluate_expression('unique(["a", "b", "a", "c", "b"])')
        assert result.item() == ["a", "b", "c"]
        assert result.type == ExprType("list[string]")

    def test_unique_float(self) -> None:
        result = evaluate_expression("unique([1.5, 2.5, 1.5, 3.5])")
        assert result.item() == [1.5, 2.5, 3.5]
        assert result.type == ExprType("list[float]")

    def test_unique_bool(self) -> None:
        result = evaluate_expression("unique([True, False, True, False])")
        assert result.item() == [True, False]
        assert result.type == ExprType("list[bool]")

    def test_unique_path(self) -> None:
        result = evaluate_expression(
            'unique([path("/a/b"), path("/c/d"), path("/a/b")])', path_format=PathFormat.POSIX
        )
        assert result.item() == ["/a/b", "/c/d"]
        assert result.type == ExprType("list[path]")

    def test_unique_range_expr(self) -> None:
        result = evaluate_expression(
            'unique([range_expr("1-3"), range_expr("4-6"), range_expr("1-3")])'
        )
        assert len(result.item()) == 2
        assert result.type == ExprType("list[range_expr]")

    def test_unique_list_int(self) -> None:
        result = evaluate_expression("unique([[1, 2], [3, 4], [1, 2], [5, 6]])")
        assert result.item() == [[1, 2], [3, 4], [5, 6]]
        assert result.type == ExprType("list[list[int]]")

    def test_unique_list_string(self) -> None:
        result = evaluate_expression('unique([["a", "b"], ["c", "d"], ["a", "b"]])')
        assert result.item() == [["a", "b"], ["c", "d"]]
        assert result.type == ExprType("list[list[string]]")

    def test_unique_list_float(self) -> None:
        result = evaluate_expression("unique([[1.0, 2.0], [3.0], [1.0, 2.0]])")
        assert result.item() == [[1.0, 2.0], [3.0]]
        assert result.type == ExprType("list[list[float]]")

    def test_unique_list_bool(self) -> None:
        result = evaluate_expression("unique([[True], [False], [True]])")
        assert result.item() == [[True], [False]]
        assert result.type == ExprType("list[list[bool]]")

    def test_unique_list_path(self) -> None:
        result = evaluate_expression(
            'unique([[path("/a")], [path("/b")], [path("/a")]])', path_format=PathFormat.POSIX
        )
        assert result.item() == [["/a"], ["/b"]]
        assert result.type == ExprType("list[list[path]]")

    def test_unique_no_duplicates(self) -> None:
        result = evaluate_expression("unique([1, 2, 3])")
        assert result.item() == [1, 2, 3]
        assert result.type == ExprType("list[int]")

    def test_unique_all_same(self) -> None:
        result = evaluate_expression("unique([7, 7, 7, 7])")
        assert result.item() == [7]
        assert result.type == ExprType("list[int]")

    def test_unique_empty(self) -> None:
        result = evaluate_expression("unique([])")
        assert result.item() == []

    def test_unique_method_syntax(self) -> None:
        result = evaluate_expression("[1, 2, 1, 3, 2].unique()")
        assert result.item() == [1, 2, 3]
        assert result.type == ExprType("list[int]")

    def test_unique_chained_with_sorted(self) -> None:
        result = evaluate_expression("[3, 1, 2, 1, 3].unique().sorted()")
        assert result.item() == [1, 2, 3]
        assert result.type == ExprType("list[int]")

    def test_unique_preserves_first_occurrence(self) -> None:
        result = evaluate_expression('unique(["banana", "apple", "banana", "cherry", "apple"])')
        assert result.item() == ["banana", "apple", "cherry"]
        assert result.type == ExprType("list[string]")


class TestAnyAll:
    """Tests for any() and all() functions."""

    def test_any_true(self) -> None:
        assert evaluate_expression("any([True, False])").item() is True

    def test_any_false(self) -> None:
        assert evaluate_expression("any([False, False])").item() is False

    def test_any_empty_list(self) -> None:
        assert evaluate_expression("any([])").item() is False

    def test_all_true(self) -> None:
        assert evaluate_expression("all([True, True])").item() is True

    def test_all_false(self) -> None:
        assert evaluate_expression("all([True, False])").item() is False

    def test_all_empty_list(self) -> None:
        assert evaluate_expression("all([])").item() is True


class TestJoin:
    """Tests for join() function."""

    def test_join_strings(self) -> None:
        assert evaluate_expression('join(["a", "b", "c"], ",")').item() == "a,b,c"

    def test_join_paths(self) -> None:
        assert (
            evaluate_expression(
                'join([path("/a"), path("/b")], ":")',
                path_format=PathFormat.POSIX,
            ).item()
            == "/a:/b"
        )

    def test_join_empty_list(self) -> None:
        assert evaluate_expression('join([], ",")').item() == ""


class TestRange:
    """Tests for range() function."""

    def test_range_stop(self) -> None:
        result = evaluate_expression("range(5)")
        assert result.item() == [0, 1, 2, 3, 4]
        assert str(result.type) == "list[int]"

    def test_range_stop_zero(self) -> None:
        result = evaluate_expression("range(0)")
        assert result.item() == []

    def test_range_start_stop(self) -> None:
        result = evaluate_expression("range(1, 5)")
        assert result.item() == [1, 2, 3, 4]

    def test_range_start_stop_same(self) -> None:
        result = evaluate_expression("range(5, 5)")
        assert result.item() == []

    def test_range_start_stop_step(self) -> None:
        result = evaluate_expression("range(0, 10, 2)")
        assert result.item() == [0, 2, 4, 6, 8]

    def test_range_negative_step(self) -> None:
        result = evaluate_expression("range(5, 0, -1)")
        assert result.item() == [5, 4, 3, 2, 1]

    def test_range_negative_start_stop(self) -> None:
        result = evaluate_expression("range(-5, 0)")
        assert result.item() == [-5, -4, -3, -2, -1]

    def test_range_step_zero_error(self) -> None:
        with pytest.raises(ExpressionError, match="step cannot be zero"):
            evaluate_expression("range(0, 10, 0)")


class TestListMultiplication:
    """Tests for list * int repetition operator."""

    def test_multiply_int_list(self) -> None:
        result = evaluate_expression("[1, 2, 3] * 3")
        assert result.item() == [1, 2, 3, 1, 2, 3, 1, 2, 3]

    def test_multiply_string_list(self) -> None:
        result = evaluate_expression('["a", "b"] * 2')
        assert result.item() == ["a", "b", "a", "b"]

    def test_multiply_by_zero(self) -> None:
        result = evaluate_expression("[1, 2, 3] * 0")
        assert result.item() == []

    def test_multiply_by_one(self) -> None:
        result = evaluate_expression("[1, 2] * 1")
        assert result.item() == [1, 2]

    def test_multiply_empty_list(self) -> None:
        result = evaluate_expression("[] * 5")
        assert result.item() == []

    def test_multiply_preserves_type(self) -> None:
        result = evaluate_expression("[1.5, 2.5] * 2")
        assert str(result.type) == "list[float]"
        assert result.item() == [1.5, 2.5, 1.5, 2.5]

    def test_multiply_nested_list(self) -> None:
        result = evaluate_expression("[[1, 2], [3]] * 2")
        assert str(result.type) == "list[list[int]]"
        assert len(result.item()) == 4


class TestFlatten:
    def test_nested(self) -> None:
        result = evaluate_expression("flatten([[1, 2], [3]])")
        assert result.item() == [1, 2, 3]

    def test_identity_int(self) -> None:
        result = evaluate_expression("flatten([1, 2, 3])")
        assert result.item() == [1, 2, 3]

    def test_identity_string(self) -> None:
        result = evaluate_expression("flatten(['a', 'b'])")
        assert result.item() == ["a", "b"]

    def test_empty(self) -> None:
        result = evaluate_expression("flatten([])")
        assert result.item() == []


class TestExprValueListConstructionErrors:
    """``ExprValue([...])`` rejects element-type mismatches with
    ``TypeError`` (not ``ValueError``) — type-class mismatch is the
    semantic category, and ``TypeError`` is the Python convention for
    that. Pinned for parity with the pure-Python reference's
    ``TypeError("List contains incompatible types: ...")`` /
    ``TypeError("Cannot construct a list containing unresolved values
    ...")``.

    Note: ``[1, 'a']`` *as an expression* (`evaluate_expression(
    "[1, 'a']")`) is rejected at evaluation time with
    ``ExpressionError`` per RFC 0005's "list literal contains
    incompatible types" diagnostic. That's a separate path from
    direct ``ExprValue([1, 'a'])`` construction from Python."""

    def test_mixed_int_string_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="incompatible types"):
            ExprValue([1, "hello"])

    def test_list_with_unresolved_first_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="unresolved"):
            ExprValue([ExprValue.unresolved(ExprType("int")), 42])

    def test_list_with_unresolved_later_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="unresolved"):
            ExprValue([42, ExprValue.unresolved(ExprType("int"))])
