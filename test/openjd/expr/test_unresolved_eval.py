# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for evaluating expressions with unresolved values (type checking via evaluation)."""

import pytest

from openjd.expr import ExprValue, ExprType, TypeCode, evaluate_expression
from openjd.expr import ExpressionError
from openjd.expr import SymbolTable


class TestUnknownPassThrough:
    """Test that unresolved values pass through symbol lookup unchanged."""

    def test_simple_name(self) -> None:
        values = SymbolTable({"X": ExprValue.unresolved(ExprType("int"))})
        result = evaluate_expression("X", values=values)
        assert result.type.type_code == TypeCode.UNRESOLVED
        assert result.type == ExprType("unresolved[int]")

    def test_dotted_name(self) -> None:
        values = SymbolTable({"Param.Count": ExprValue.unresolved(ExprType("int"))})
        result = evaluate_expression("Param.Count", values=values)
        assert result.type.type_code == TypeCode.UNRESOLVED
        assert result.type == ExprType("unresolved[int]")

    def test_different_types(self) -> None:
        for type_str in ["int", "float", "string", "path", "bool", "list[int]", "list[string]"]:
            values = SymbolTable({"X": ExprValue.unresolved(type_str)})
            result = evaluate_expression("X", values=values)
            assert result.type.type_code == TypeCode.UNRESOLVED
            assert result.type == ExprType(f"unresolved[{type_str}]")

    def test_unconstrained_unknown(self) -> None:
        values = SymbolTable({"X": ExprValue.unresolved(ExprType("any"))})
        result = evaluate_expression("X", values=values)
        assert result.type.type_code == TypeCode.UNRESOLVED
        assert result.type == ExprType("unresolved")


class TestUnknownFunctionCalls:
    """Test that function calls with unresolved args return unresolved[return_type]."""

    def test_len_of_unknown_list(self) -> None:
        values = SymbolTable({"X": ExprValue.unresolved("list[int]")})
        result = evaluate_expression("len(X)", values=values)
        assert result.type.type_code == TypeCode.UNRESOLVED
        assert result.type == ExprType("unresolved[int]")


class TestUnknownTypeErrors:
    """Test that type errors with unresolved args show unwrapped type names."""

    def test_operator_incompatible_unknown_types(self) -> None:
        values = SymbolTable(
            {
                "X": ExprValue.unresolved("string"),
                "Y": ExprValue.unresolved("int"),
            }
        )
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("X + Y", values=values)
        expected = [
            "Cannot use '+' operator with string and int\n",
            "  X + Y\n",
            "  ~~^~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_operator_unknown_and_concrete(self) -> None:
        values = SymbolTable({"X": ExprValue.unresolved("string")})
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("X - 1", values=values)
        expected = [
            "Cannot use '-' operator with string and int\n",
            "  X - 1\n",
            "  ~~^~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_function_unknown_wrong_type(self) -> None:
        values = SymbolTable({"X": ExprValue.unresolved("int")})
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("len(X)", values=values)
        expected = [
            "No matching signature for len(int)\n",
            "  len(X)\n",
            "  ^~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_method_wrong_receiver_type(self) -> None:
        values = SymbolTable({"X": ExprValue.unresolved("int")})
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("X.upper()", values=values)
        expected = [
            "upper() is not available for int. Available for: string\n",
            "  X.upper()\n",
            "  ~~^~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_property_wrong_receiver_type(self) -> None:
        values = SymbolTable({"X": ExprValue.unresolved("int")})
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("X.stem", values=values)
        expected = [
            "'stem' property is not available for int. Available for: path\n",
            "  X.stem\n",
            "  ~~^~~~",
        ]
        assert str(exc_info.value) == "".join(expected)


class TestUnknownIfElse:
    """Test if/else behavior with unresolved conditions and branches."""

    def test_unknown_condition_both_branches_succeed(self) -> None:
        """Both branches succeed -> unresolved[T | S]."""
        values = SymbolTable(
            {
                "cond": ExprValue.unresolved("bool"),
                "X": ExprValue.unresolved("int"),
                "Y": ExprValue.unresolved("string"),
            }
        )
        result = evaluate_expression("X if cond else Y", values=values)
        assert result.type == ExprType("unresolved[int | string]")

    def test_unknown_condition_same_branch_types(self) -> None:
        """Both branches return same type -> unresolved[T]."""
        values = SymbolTable(
            {
                "cond": ExprValue.unresolved("bool"),
                "X": ExprValue.unresolved("int"),
                "Y": ExprValue.unresolved("int"),
            }
        )
        result = evaluate_expression("X if cond else Y", values=values)
        assert result.type == ExprType("unresolved[int]")

    def test_unknown_condition_concrete_branches(self) -> None:
        """Concrete branch values with unresolved condition -> unresolved[T | S]."""
        values = SymbolTable({"cond": ExprValue.unresolved("bool")})
        result = evaluate_expression("1 if cond else 'hello'", values=values)
        assert result.type == ExprType("unresolved[int | string]")

    def test_unknown_condition_one_branch_fails(self) -> None:
        """One branch fails -> result is the succeeding branch type."""
        values = SymbolTable(
            {
                "cond": ExprValue.unresolved("bool"),
                "X": ExprValue.unresolved("int"),
            }
        )
        # body succeeds (X is int), orelse fails (X + "bad" is type error)
        result = evaluate_expression("X if cond else X + 'bad'", values=values)
        assert result.type == ExprType("unresolved[int]")

    def test_unknown_condition_one_branch_fails_different_types(self) -> None:
        """Failing branch ignored, succeeding branch type preserved."""
        values = SymbolTable(
            {
                "cond": ExprValue.unresolved("bool"),
                "X": ExprValue.unresolved("string"),
                "Y": ExprValue.unresolved("int"),
            }
        )
        # body succeeds (X is string), orelse fails (Y.upper() — int has no upper).
        # Result is unresolved[string], not unresolved[int | string], because the
        # failing branch can never return a value.
        result = evaluate_expression("X if cond else Y.upper()", values=values)
        assert result.type == ExprType("unresolved[string]")

    def test_unknown_condition_other_branch_fails(self) -> None:
        """The other branch fails -> result is the succeeding branch type."""
        values = SymbolTable(
            {
                "cond": ExprValue.unresolved("bool"),
                "X": ExprValue.unresolved("int"),
            }
        )
        result = evaluate_expression("X + 'bad' if cond else X", values=values)
        assert result.type == ExprType("unresolved[int]")

    def test_unknown_condition_other_branch_fails_different_types(self) -> None:
        """Failing branch ignored, succeeding branch type preserved."""
        values = SymbolTable(
            {
                "cond": ExprValue.unresolved("bool"),
                "X": ExprValue.unresolved("int"),
                "Y": ExprValue.unresolved("string"),
            }
        )
        # body fails (X.upper() — int has no upper), orelse succeeds (Y is string)
        result = evaluate_expression("X.upper() if cond else Y", values=values)
        assert result.type == ExprType("unresolved[string]")

    def test_unknown_condition_both_branches_fail(self) -> None:
        """Both branches fail -> error mentioning both failures."""
        values = SymbolTable(
            {
                "cond": ExprValue.unresolved("bool"),
                "X": ExprValue.unresolved("int"),
                "Y": ExprValue.unresolved("path"),
            }
        )
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("X + 'a' if cond else Y * 'b'", values=values)
        expected = [
            "Both branches fail in the if/else:\n",
            "  if-branch: Cannot use '+' operator with int and string\n",
            "  X + 'a' if cond else Y * 'b'\n",
            "  ~~^~~~~\n",
            "  else-branch: Cannot use '*' operator with path and string\n",
            "  X + 'a' if cond else Y * 'b'\n",
            "                       ~~^~~~~\n",
            "  X + 'a' if cond else Y * 'b'\n",
            "  ^~~~~~~~~~~~~~~~~~~~~~~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_known_condition_unknown_branch_values(self) -> None:
        """Known condition picks the right branch, returns its unresolved value."""
        values = SymbolTable(
            {
                "X": ExprValue.unresolved("int"),
                "Y": ExprValue.unresolved("string"),
            }
        )
        result = evaluate_expression("X if True else Y", values=values)
        assert result.type == ExprType("unresolved[int]")

        result = evaluate_expression("X if False else Y", values=values)
        assert result.type == ExprType("unresolved[string]")

    def test_unknown_condition_wrong_constraint_type(self) -> None:
        """unresolved[string] as condition is a type error."""
        values = SymbolTable({"cond": ExprValue.unresolved("string")})
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("1 if cond else 2", values=values)
        expected = [
            "Condition must be a boolean, got string\n",
            "  1 if cond else 2\n",
            "       ^~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_unknown_bool_condition_accepted(self) -> None:
        """unresolved[bool] is a valid condition."""
        values = SymbolTable({"cond": ExprValue.unresolved("bool")})
        result = evaluate_expression("1 if cond else 2", values=values)
        assert result.type.type_code == TypeCode.UNRESOLVED

    def test_unknown_bool_union_condition_accepted(self) -> None:
        """unresolved[bool | int] is a valid condition (constraint includes bool)."""
        values = SymbolTable({"cond": ExprValue.unresolved("bool | int")})
        result = evaluate_expression("1 if cond else 2", values=values)
        assert result.type.type_code == TypeCode.UNRESOLVED

    def test_unconstrained_unknown_condition_accepted(self) -> None:
        """unknown (i.e. unresolved[any]) is a valid condition."""
        values = SymbolTable({"cond": ExprValue.unresolved("any")})
        result = evaluate_expression("1 if cond else 2", values=values)
        assert result.type.type_code == TypeCode.UNRESOLVED


class TestUnknownListLiterals:
    """Test list literal type inference with unresolved elements."""

    def test_all_concrete_same_type(self) -> None:
        """[1, 2, 3] -> list[int] (no unknowns, no change)."""
        result = evaluate_expression("[1, 2, 3]", values=SymbolTable())
        assert result.type == ExprType("list[int]")

    def test_all_unknown_same_constraint(self) -> None:
        """[unresolved[int], unresolved[int]] -> unresolved[list[int]]."""
        values = SymbolTable({"X": ExprValue.unresolved("int"), "Y": ExprValue.unresolved("int")})
        result = evaluate_expression("[X, Y]", values=values)
        assert result.type == ExprType("unresolved[list[int]]")

    def test_mix_concrete_and_unknown_same_type(self) -> None:
        """[1, unresolved[int], 3] -> unresolved[list[int]]."""
        values = SymbolTable({"X": ExprValue.unresolved("int")})
        result = evaluate_expression("[1, X, 3]", values=values)
        assert result.type == ExprType("unresolved[list[int]]")

    def test_all_unknown_int_float_coercion(self) -> None:
        """[unresolved[int], unresolved[float]] -> unresolved[list[float]]."""
        values = SymbolTable(
            {
                "X": ExprValue.unresolved("int"),
                "Y": ExprValue.unresolved("float"),
            }
        )
        result = evaluate_expression("[X, Y]", values=values)
        assert result.type == ExprType("unresolved[list[float]]")

    def test_mix_concrete_and_unknown_coercion(self) -> None:
        """[1, unresolved[float]] -> unresolved[list[float]]."""
        values = SymbolTable({"X": ExprValue.unresolved("float")})
        result = evaluate_expression("[1, X]", values=values)
        assert result.type == ExprType("unresolved[list[float]]")

    def test_mix_unknown_int_and_concrete_float(self) -> None:
        """[unresolved[int], 1.0] -> unresolved[list[float]] (int coerces to float)."""
        values = SymbolTable({"X": ExprValue.unresolved("int")})
        result = evaluate_expression("[X, 1.0]", values=values)
        assert result.type == ExprType("unresolved[list[float]]")

    def test_all_unknown_path_string_coercion(self) -> None:
        """[unresolved[path], unresolved[string]] -> unresolved[list[string]]."""
        values = SymbolTable(
            {
                "X": ExprValue.unresolved("path"),
                "Y": ExprValue.unresolved("string"),
            }
        )
        result = evaluate_expression("[X, Y]", values=values)
        assert result.type == ExprType("unresolved[list[string]]")

    def test_mix_concrete_string_and_unknown_path(self) -> None:
        """['hello', unresolved[path]] -> unresolved[list[string]]."""
        values = SymbolTable({"X": ExprValue.unresolved("path")})
        result = evaluate_expression("['hello', X]", values=values)
        assert result.type == ExprType("unresolved[list[string]]")

    def test_mix_unknown_path_and_concrete_string(self) -> None:
        """[unresolved[path], 'hello'] -> unresolved[list[string]] (path coerces to string)."""
        values = SymbolTable({"X": ExprValue.unresolved("path")})
        result = evaluate_expression("[X, 'hello']", values=values)
        assert result.type == ExprType("unresolved[list[string]]")

    def test_mix_unknown_string_and_concrete_path(self) -> None:
        """[unresolved[string], path('/a')] -> unresolved[list[string]] (path coerces to string)."""
        values = SymbolTable({"X": ExprValue.unresolved("string")})
        result = evaluate_expression("[X, path('/a')]", values=values)
        assert result.type == ExprType("unresolved[list[string]]")

    def test_incompatible_types_error(self) -> None:
        """[unresolved[int], unresolved[string]] -> error."""
        values = SymbolTable(
            {
                "X": ExprValue.unresolved("int"),
                "Y": ExprValue.unresolved("string"),
            }
        )
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("[X, Y]", values=values)
        expected = [
            "List literal contains incompatible types: int, string\n",
            "  [X, Y]\n",
            "  ^~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_empty_list_unchanged(self) -> None:
        """[] -> list[nulltype] (no unknowns)."""
        result = evaluate_expression("[]", values=SymbolTable())
        assert result.type == ExprType("list[nulltype]")


class TestUnknownListComprehensions:
    """Test list comprehension with unresolved iterables."""

    def test_unknown_list_iterable(self) -> None:
        """[x for x in unresolved[list[int]]] -> unresolved[list[int]]."""
        values = SymbolTable({"X": ExprValue.unresolved("list[int]")})
        result = evaluate_expression("[x for x in X]", values=values)
        assert result.type == ExprType("unresolved[list[int]]")

    def test_unknown_list_with_body_expr(self) -> None:
        """[x + 1 for x in unresolved[list[int]]] -> unresolved[list[int]]."""
        values = SymbolTable({"X": ExprValue.unresolved("list[int]")})
        result = evaluate_expression("[x + 1 for x in X]", values=values)
        assert result.type == ExprType("unresolved[list[int]]")

    def test_unknown_range_iterable(self) -> None:
        """[x for x in unresolved[range_expr]] -> unresolved[list[int]]."""
        values = SymbolTable({"X": ExprValue.unresolved("range_expr")})
        result = evaluate_expression("[x for x in X]", values=values)
        assert result.type == ExprType("unresolved[list[int]]")

    def test_unknown_iterable_with_transform(self) -> None:
        """[string(x) for x in unresolved[list[int]]] -> unresolved[list[string]]."""
        values = SymbolTable({"X": ExprValue.unresolved("list[int]")})
        result = evaluate_expression("[string(x) for x in X]", values=values)
        assert result.type == ExprType("unresolved[list[string]]")


class TestUnknownCoercion:
    """Test that unresolved values coerce correctly in function/operator contexts."""

    def test_unknown_int_plus_float(self) -> None:
        """unresolved[int] + 1.0 -> unresolved[float] (int coerces to float)."""
        values = SymbolTable({"X": ExprValue.unresolved("int")})
        result = evaluate_expression("X + 1.0", values=values)
        assert result.type == ExprType("unresolved[float]")

    def test_unknown_int_times_float(self) -> None:
        """unresolved[int] * 2.0 -> unresolved[float]."""
        values = SymbolTable({"X": ExprValue.unresolved("int")})
        result = evaluate_expression("X * 2.0", values=values)
        assert result.type == ExprType("unresolved[float]")

    def test_unknown_path_in_string_context(self) -> None:
        """unresolved[path] coerces to unresolved[string] when string is expected."""
        values = SymbolTable({"X": ExprValue.unresolved("path")})
        result = evaluate_expression("upper(X)", values=values)
        assert result.type == ExprType("unresolved[string]")


class TestUnknownComparisons:
    """Test comparison operators with unresolved values."""

    def test_unknown_less_than(self) -> None:
        values = SymbolTable({"X": ExprValue.unresolved("int")})
        result = evaluate_expression("X < 5", values=values)
        assert result.type == ExprType("unresolved[bool]")

    def test_chained_comparison(self) -> None:
        values = SymbolTable({"X": ExprValue.unresolved("int")})
        result = evaluate_expression("1 < X < 10", values=values)
        assert result.type == ExprType("unresolved[bool]")

    def test_equality_with_unknown(self) -> None:
        values = SymbolTable({"X": ExprValue.unresolved("string")})
        result = evaluate_expression("X == 'hello'", values=values)
        assert result.type == ExprType("unresolved[bool]")

    def test_in_operator_with_unknown_list(self) -> None:
        values = SymbolTable({"X": ExprValue.unresolved("list[int]")})
        result = evaluate_expression("3 in X", values=values)
        assert result.type == ExprType("unresolved[bool]")

    def test_chained_concrete_then_unknown(self) -> None:
        """1 < 2 < X — first comparison is concrete true, second is unresolved."""
        values = SymbolTable({"X": ExprValue.unresolved("int")})
        result = evaluate_expression("1 < 2 < X", values=values)
        assert result.type == ExprType("unresolved[bool]")

    def test_cross_type_comparison_with_unknowns(self) -> None:
        """unresolved[string] < unresolved[list[int]] -> unresolved[bool].

        Comparison operators accept any types at the signature level (T1, T2) -> bool.
        Cross-type ordering errors are caught at runtime, not during type checking.
        """
        values = SymbolTable(
            {
                "X": ExprValue.unresolved("string"),
                "Y": ExprValue.unresolved("list[int]"),
            }
        )
        result = evaluate_expression("X < Y", values=values)
        assert result.type == ExprType("unresolved[bool]")


class TestUnknownBoolOps:
    """Test and/or with unresolved boolean values."""

    def test_unknown_and_true(self) -> None:
        values = SymbolTable({"X": ExprValue.unresolved("bool")})
        result = evaluate_expression("X and True", values=values)
        assert result.type == ExprType("unresolved[bool]")

    def test_false_and_unknown(self) -> None:
        """False and X -> False (short-circuit, X never matters)."""
        values = SymbolTable({"X": ExprValue.unresolved("bool")})
        result = evaluate_expression("False and X", values=values)
        assert result == ExprValue(False)

    def test_unknown_or_false(self) -> None:
        values = SymbolTable({"X": ExprValue.unresolved("bool")})
        result = evaluate_expression("X or False", values=values)
        assert result.type == ExprType("unresolved[bool]")

    def test_true_or_unknown(self) -> None:
        """True or X -> True (short-circuit, X never matters)."""
        values = SymbolTable({"X": ExprValue.unresolved("bool")})
        result = evaluate_expression("True or X", values=values)
        assert result == ExprValue(True)

    def test_multiple_unknowns_and(self) -> None:
        """X and Y and True -> unresolved[bool] when both X and Y are unresolved."""
        values = SymbolTable(
            {
                "X": ExprValue.unresolved("bool"),
                "Y": ExprValue.unresolved("bool"),
            }
        )
        result = evaluate_expression("X and Y and True", values=values)
        assert result.type == ExprType("unresolved[bool]")

    def test_unknown_or_true_is_true(self) -> None:
        """X or True -> True (X is a value, can't fail, result always True)."""
        values = SymbolTable({"X": ExprValue.unresolved("bool")})
        result = evaluate_expression("X or True", values=values)
        assert result == ExprValue(True)

    def test_unknown_and_false_is_false(self) -> None:
        """X and False -> False (X is a value, can't fail, result always False)."""
        values = SymbolTable({"X": ExprValue.unresolved("bool")})
        result = evaluate_expression("X and False", values=values)
        assert result == ExprValue(False)

    def test_type_error_in_boolop_not_suppressed(self) -> None:
        """X.upper() or True -> error. Type errors are caught even when result is determined.

        Unlike if/else branches, boolop operands are always type-checked because
        a type error indicates a bug regardless of the runtime value.
        """
        values = SymbolTable({"X": ExprValue.unresolved("int")})
        with pytest.raises(ExpressionError, match="upper.*not available for int"):
            evaluate_expression("X.upper() or True", values=values)


class TestUnknownSubscript:
    """Test subscript/slice with unresolved values."""

    def test_unknown_list_index(self) -> None:
        values = SymbolTable({"X": ExprValue.unresolved("list[int]")})
        result = evaluate_expression("X[0]", values=values)
        assert result.type == ExprType("unresolved[int]")

    def test_concrete_list_unknown_index(self) -> None:
        values = SymbolTable({"I": ExprValue.unresolved("int")})
        result = evaluate_expression("[1, 2, 3][I]", values=values)
        assert result.type == ExprType("unresolved[int]")

    def test_unknown_list_unknown_index(self) -> None:
        values = SymbolTable(
            {
                "X": ExprValue.unresolved("list[string]"),
                "I": ExprValue.unresolved("int"),
            }
        )
        result = evaluate_expression("X[I]", values=values)
        assert result.type == ExprType("unresolved[string]")

    def test_unknown_list_slice(self) -> None:
        values = SymbolTable({"X": ExprValue.unresolved("list[int]")})
        result = evaluate_expression("X[1:3]", values=values)
        assert result.type == ExprType("unresolved[list[int]]")

    def test_unknown_string_index_error(self) -> None:
        """unresolved[string] as index is a type error."""
        values = SymbolTable({"I": ExprValue.unresolved("string")})
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("[1, 2][I]", values=values)
        expected = [
            "Index must be an integer\n",
            "  [1, 2][I]\n",
            "  ~~~~~~^~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_unknown_slice_bounds(self) -> None:
        """[1,2,3][X:] where X is unresolved[int] -> unresolved[list[int]]."""
        values = SymbolTable({"X": ExprValue.unresolved("int")})
        result = evaluate_expression("[1, 2, 3][X:]", values=values)
        assert result.type == ExprType("unresolved[list[int]]")


class TestUnknownFail:
    """Test fail() behavior with unresolved values."""

    def test_fail_with_unknown_message(self) -> None:
        """fail(unresolved[string]) -> unresolved[noreturn] (doesn't actually raise)."""
        values = SymbolTable({"msg": ExprValue.unresolved("string")})
        result = evaluate_expression("fail(msg)", values=values)
        assert result.type == ExprType("unresolved[noreturn]")

    def test_if_else_with_unknown_fail(self) -> None:
        """X if cond else fail(msg) -> unresolved[int] (noreturn collapses in union)."""
        values = SymbolTable(
            {
                "cond": ExprValue.unresolved("bool"),
                "X": ExprValue.unresolved("int"),
                "msg": ExprValue.unresolved("string"),
            }
        )
        result = evaluate_expression("X if cond else fail(msg)", values=values)
        assert result.type == ExprType("unresolved[int]")

    def test_if_else_with_concrete_fail(self) -> None:
        """X if cond else fail('bad') -> unresolved[int].

        fail() with concrete args raises, but the if/else treats it as a
        failing branch and returns the other branch's type.
        """
        values = SymbolTable(
            {
                "cond": ExprValue.unresolved("bool"),
                "X": ExprValue.unresolved("int"),
            }
        )
        result = evaluate_expression("X if cond else fail('bad')", values=values)
        assert result.type == ExprType("unresolved[int]")

    def test_fail_in_boolop_not_caught_during_type_check(self) -> None:
        """(fail('bad') if cond else False) or True -> True during type checking.

        This is an edge case: the if/else suppresses the fail() branch (it might
        not execute), producing unresolved[bool]. Then `unresolved[bool] or True` is True.
        At runtime with cond=True, fail() would raise before reaching `or True`.
        This will only be caught later when evaluated with cond as a known value.
        """
        values = SymbolTable({"cond": ExprValue.unresolved("bool")})
        result = evaluate_expression("(fail('bad') if cond else False) or True", values=values)
        assert result == ExprValue(True)


class TestSymbolTableWithTypes:
    """Test that SymbolTable auto-wraps ExprType values as unknown."""

    def test_simple_types(self) -> None:
        st = SymbolTable({"X": ExprType("int"), "Y": ExprType("string")})
        assert st["X"] == ExprValue.unresolved(ExprType("int"))
        assert st["Y"] == ExprValue.unresolved(ExprType("string"))

    def test_dotted_paths(self) -> None:
        st = SymbolTable({"Param.Frame": ExprType("int"), "Param.Name": ExprType("string")})
        param = st["Param"]
        assert isinstance(param, SymbolTable)
        assert param["Frame"] == ExprValue.unresolved(ExprType("int"))
        assert param["Name"] == ExprValue.unresolved(ExprType("string"))

    def test_evaluation_with_types(self) -> None:
        """SymbolTable built from ExprType values works with evaluate_expression."""
        st = SymbolTable({"X": ExprType("int")})
        result = evaluate_expression("X + 1", values=st)
        assert result.type == ExprType("unresolved[int]")

    def test_mixed_concrete_and_types(self) -> None:
        """SymbolTable can mix concrete values and ExprType unknowns."""
        st = SymbolTable({"X": 42, "Y": ExprType("string")})
        assert st["X"] == ExprValue(42)
        assert st["Y"] == ExprValue.unresolved(ExprType("string"))
        # Concrete X evaluates fully, unknown Y propagates
        result = evaluate_expression("X + 1", values=st)
        assert result == ExprValue(43)
        result = evaluate_expression("Y + '!'", values=st)
        assert result.type == ExprType("unresolved[string]")


class TestUnknownGenericBindingConflict:
    """Test that unresolved[T] and T are compatible in generic type variable bindings."""

    def test_in_operator_unknown_item_concrete_list(self) -> None:
        """X in [1, 3, 5] where X is unresolved[int] — T binds to int from list and unresolved[int] from X."""
        values = SymbolTable({"X": ExprValue.unresolved("int")})
        result = evaluate_expression("X in [1, 3, 5]", values=values)
        assert result.type == ExprType("unresolved[bool]")

    def test_not_in_operator_unknown_item(self) -> None:
        values = SymbolTable({"X": ExprValue.unresolved("int")})
        result = evaluate_expression("X not in [2, 4, 6]", values=values)
        assert result.type == ExprType("unresolved[bool]")

    def test_in_operator_concrete_item_unknown_list(self) -> None:
        values = SymbolTable({"L": ExprValue.unresolved("list[int]")})
        result = evaluate_expression("3 in L", values=values)
        assert result.type == ExprType("unresolved[bool]")


class TestUnknownBoolOpErrorSuppression:
    """Test that errors after unresolved operands in and/or are suppressed."""

    def test_unknown_or_fail_suppressed(self) -> None:
        """Param.Flag or fail('msg') — fail() suppressed because Flag might short-circuit."""
        values = SymbolTable({"Flag": ExprValue.unresolved("bool")})
        result = evaluate_expression("Flag or fail('required')", values=values)
        assert result.type == ExprType("unresolved[bool]")

    def test_unknown_and_fail_suppressed(self) -> None:
        """Param.Flag and fail('msg') — fail() suppressed because Flag might short-circuit."""
        values = SymbolTable({"Flag": ExprValue.unresolved("bool")})
        result = evaluate_expression("Flag and fail('required')", values=values)
        assert result.type == ExprType("unresolved[bool]")

    def test_concrete_false_or_fail_not_suppressed(self) -> None:
        """false or fail('msg') — no unknown before fail, so it raises."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("false or fail('required')")
        expected = "".join(
            [
                "required\n",
                "  false or fail('required')\n",
                "           ^~~~~~~~~~~~~~~~",
            ]
        )
        assert str(exc_info.value) == expected

    def test_concrete_true_and_fail_not_suppressed(self) -> None:
        """true and fail('msg') — no unknown before fail, so it raises."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("true and fail('required')")
        expected = "".join(
            [
                "required\n",
                "  true and fail('required')\n",
                "           ^~~~~~~~~~~~~~~~",
            ]
        )
        assert str(exc_info.value) == expected

    def test_type_error_after_unknown_suppressed(self) -> None:
        """X or (1 + 'bad') — type error suppressed after unknown."""
        values = SymbolTable({"X": ExprValue.unresolved("bool")})
        result = evaluate_expression("X or (1 + 'bad')", values=values)
        assert result.type == ExprType("unresolved[bool]")

    def test_type_error_before_unknown_not_suppressed(self) -> None:
        """(1 + 'bad') or X — type error before unknown, not suppressed."""
        values = SymbolTable({"X": ExprValue.unresolved("bool")})
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("(1 + 'bad') or X", values=values)
        expected = "".join(
            [
                "Cannot use '+' operator with int and string\n",
                "  (1 + 'bad') or X\n",
                "   ~~^~~~~~~",
            ]
        )
        assert str(exc_info.value) == expected
