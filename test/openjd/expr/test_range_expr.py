# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for range expressions."""

import pytest
from openjd.expr import evaluate_expression, SymbolTable, ExpressionError, TypeCode
from openjd.expr import RangeExpr, IntRange


class TestRangeExpr:
    def test_range_expr_from_string(self) -> None:
        result = evaluate_expression("range_expr('1-10')")
        assert result.type.type_code == TypeCode.RANGE_EXPR
        assert len(result.item()) == 10

    def test_range_expr_len(self) -> None:
        assert evaluate_expression("len(range_expr('1-10'))").item() == 10

    def test_range_expr_subscript_positive(self) -> None:
        assert evaluate_expression("range_expr('1-10')[0]").item() == 1
        assert evaluate_expression("range_expr('1-10')[9]").item() == 10

    def test_range_expr_subscript_negative(self) -> None:
        assert evaluate_expression("range_expr('1-10')[-1]").item() == 10
        assert evaluate_expression("range_expr('1-10')[-2]").item() == 9

    def test_range_expr_subscript_out_of_bounds(self) -> None:
        with pytest.raises(ExpressionError, match="out of bounds"):
            evaluate_expression("range_expr('1-10')[100]")

    def test_range_expr_to_list(self) -> None:
        result = evaluate_expression("list(range_expr('1-5'))")
        assert result.item() == [1, 2, 3, 4, 5]

    def test_range_expr_to_string(self) -> None:
        assert evaluate_expression("string(range_expr('1-5,10-15'))").item() == "1-5,10-15"

    def test_range_expr_with_step(self) -> None:
        result = evaluate_expression("list(range_expr('1-10:2'))")
        assert result.item() == [1, 3, 5, 7, 9]

    def test_range_expr_from_symtab(self) -> None:
        from openjd.expr import RangeExpr

        symtab = SymbolTable({"Param.Frames": RangeExpr("1-100:10")})
        assert evaluate_expression("Param.Frames[0]", values=symtab).item() == 1
        assert evaluate_expression("len(Param.Frames)", values=symtab).item() == 10

    def test_range_expr_invalid_string(self) -> None:
        with pytest.raises(ExpressionError, match="Expected integer"):
            evaluate_expression("range_expr('not-a-range')")

    def test_range_expr_empty_string(self) -> None:
        with pytest.raises(ExpressionError, match="Empty expression"):
            evaluate_expression("range_expr('')")

    def test_range_expr_from_list(self) -> None:
        result = evaluate_expression("range_expr([1, 2, 3])")
        assert result.item() == RangeExpr("1-3")

    def test_range_expr_from_list_non_contiguous(self) -> None:
        result = evaluate_expression("range_expr([1, 3, 5, 10])")
        assert list(result.item()) == [1, 3, 5, 10]

    def test_range_expr_from_list_duplicates(self) -> None:
        result = evaluate_expression("string(range_expr([1, 1, 1]))")
        assert result.item() == "1"

    def test_range_expr_from_list_reverse(self) -> None:
        result = evaluate_expression("string(range_expr([9, 8, 7, 6]))")
        assert result.item() == "6-9"

    def test_range_expr_empty_list(self) -> None:
        with pytest.raises(ExpressionError, match="requires at least one value"):
            evaluate_expression("range_expr([])")

    def test_range_expr_in_comprehension(self) -> None:
        result = evaluate_expression("[x * 2 for x in range_expr('1-5')]")
        assert result.item() == [2, 4, 6, 8, 10]

    def test_range_expr_in_comprehension_with_filter(self) -> None:
        result = evaluate_expression("[x for x in range_expr('1-10') if x > 5]")
        assert result.item() == [6, 7, 8, 9, 10]

    def test_range_expr_in_comprehension_from_symtab(self) -> None:
        from openjd.expr import RangeExpr

        symtab = SymbolTable({"Frames": RangeExpr("1-100:10")})
        result = evaluate_expression("[f + 1000 for f in Frames]", values=symtab)
        assert result.item() == list(range(1001, 1100, 10))

    def test_range_expr_min(self) -> None:
        assert evaluate_expression("min(range_expr('5-10'))").item() == 5
        assert evaluate_expression("min(range_expr('10-5:-1'))").item() == 5
        assert evaluate_expression("min(range_expr('1,5,10,3'))").item() == 1

    def test_range_expr_max(self) -> None:
        assert evaluate_expression("max(range_expr('5-10'))").item() == 10
        assert evaluate_expression("max(range_expr('10-5:-1'))").item() == 10
        assert evaluate_expression("max(range_expr('1,5,10,3'))").item() == 10

    def test_range_expr_sum(self) -> None:
        assert evaluate_expression("sum(range_expr('1-5'))").item() == 15
        assert evaluate_expression("sum(range_expr('1-10:2'))").item() == 25  # 1+3+5+7+9

    def test_range_expr_min_max_from_symtab(self) -> None:
        from openjd.expr import RangeExpr

        symtab = SymbolTable({"Frames": RangeExpr("10-50:5")})
        assert evaluate_expression("min(Frames)", values=symtab).item() == 10
        assert evaluate_expression("max(Frames)", values=symtab).item() == 50

    def test_range_expr_is_hashable(self) -> None:
        """``RangeExpr`` is hashable. The hash defers to the Rust crate's
        manual ``Hash`` impl on ``RangeExpr`` (which hashes the
        underlying ranges), so two values that compare equal also hash
        equal."""
        a = RangeExpr("1-10")
        b = RangeExpr("1-10")
        c = RangeExpr("1-10:2")

        # Usable as a set element.
        assert len({a, b, c}) == 2
        # Equal values produce equal hashes.
        assert hash(a) == hash(b)
        # Distinct shapes produce distinct hashes (overwhelmingly likely
        # for the default hasher; the contract is only that equal values
        # hash equal, but a collision here would still indicate something
        # surprising).
        assert hash(a) != hash(c)

    def test_start(self) -> None:
        assert RangeExpr("1-10").start == 1
        assert RangeExpr("1,5,10-20").start == 1
        # Multiple ranges are sorted ascending by the parser, so start is
        # always the smallest value.
        assert RangeExpr("10-20,1-5").start == 1

    def test_end(self) -> None:
        assert RangeExpr("1-10").end == 10
        assert RangeExpr("1,5,10-20").end == 20

    def test_start_end_single_value(self) -> None:
        r = RangeExpr("42")
        assert r.start == 42
        assert r.end == 42

    def test_from_list_contiguous(self) -> None:
        assert str(RangeExpr.from_list([1, 2, 3])) == "1-3"

    def test_from_list_non_contiguous(self) -> None:
        # Rust's RangeExpr::from_values packs an arithmetic-progression
        # subsequence into a single stride range when possible; [1,3,5]
        # therefore renders as "1-5:2", not three separate values.
        assert str(RangeExpr.from_list([1, 3, 5])) == "1-5:2"
        assert list(RangeExpr.from_list([1, 3, 5, 10])) == [1, 3, 5, 10]

    def test_from_list_duplicates(self) -> None:
        assert str(RangeExpr.from_list([1, 1, 1])) == "1"

    def test_from_list_reverse(self) -> None:
        """Values are sorted ascending before packing, so a descending
        input still produces an ascending range."""
        assert str(RangeExpr.from_list([9, 8, 7, 6])) == "6-9"

    def test_from_list_strings(self) -> None:
        """Numeric strings are accepted and parsed as ints."""
        assert str(RangeExpr.from_list(["1", "2", "3"])) == "1-3"

    def test_from_list_mixed(self) -> None:
        """Ints and strings can be mixed in a single call."""
        assert str(RangeExpr.from_list([1, "2", 3])) == "1-3"

    def test_from_list_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            RangeExpr.from_list([])

    def test_from_list_invalid_string_raises(self) -> None:
        with pytest.raises(ValueError, match="not a valid integer"):
            RangeExpr.from_list(["abc"])

    def test_from_list_invalid_type_raises(self) -> None:
        with pytest.raises(TypeError, match="must be int or str"):
            RangeExpr.from_list([1.5])


class TestExprValueRangeExprProtocols:
    """Test len, indexing, and iteration on ExprValue with range_expr type."""

    def test_len(self) -> None:
        result = evaluate_expression('range_expr("1-10")')
        assert len(result) == 10

    def test_index_first(self) -> None:
        result = evaluate_expression('range_expr("1-10")')
        assert result[0].item() == 1

    def test_index_last(self) -> None:
        result = evaluate_expression('range_expr("1-10")')
        assert result[9].item() == 10

    def test_negative_index(self) -> None:
        result = evaluate_expression('range_expr("1-10")')
        assert result[-1].item() == 10
        assert result[-10].item() == 1

    def test_index_out_of_bounds(self) -> None:
        result = evaluate_expression('range_expr("1-10")')
        with pytest.raises(IndexError):
            result[10]

    def test_negative_index_out_of_bounds(self) -> None:
        result = evaluate_expression('range_expr("1-10")')
        with pytest.raises(IndexError):
            result[-11]

    def test_iteration(self) -> None:
        result = evaluate_expression('range_expr("1-5")')
        assert [e.item() for e in result] == [1, 2, 3, 4, 5]

    def test_step(self) -> None:
        result = evaluate_expression('range_expr("1-10:3")')
        assert len(result) == 4
        assert [e.item() for e in result] == [1, 4, 7, 10]

    def test_non_contiguous(self) -> None:
        result = evaluate_expression('range_expr("1-3,10-12")')
        assert len(result) == 6
        assert [e.item() for e in result] == [1, 2, 3, 10, 11, 12]

    def test_len_on_non_sequence_raises(self) -> None:
        result = evaluate_expression("42")
        with pytest.raises(TypeError):
            len(result)

    def test_index_on_non_sequence_raises(self) -> None:
        result = evaluate_expression("42")
        with pytest.raises(TypeError):
            result[0]

    def test_iter_on_non_sequence_raises(self) -> None:
        result = evaluate_expression("42")
        with pytest.raises(TypeError):
            list(result)


class TestIntRange:
    """``IntRange`` is the element type returned by
    ``RangeExpr.ranges()``. It exposes ``start``/``end``/``step``
    getters, supports iteration / containment / hashing / equality /
    pickle, and matches the v0 reference's ``IntRange`` shape."""

    def test_constructor_ascending(self) -> None:
        ir = IntRange(1, 10, 1)
        assert ir.start == 1
        assert ir.end == 10
        assert ir.step == 1

    def test_constructor_with_step(self) -> None:
        # Last value reached by stepping (not the parameter end).
        ir = IntRange(1, 10, 2)
        assert ir.start == 1
        assert ir.end == 9
        assert ir.step == 2
        assert list(ir) == [1, 3, 5, 7, 9]

    def test_constructor_normalises_descending(self) -> None:
        # IntRange(10, 1, -1) is normalised to ascending form, matching
        # the upstream ``IntRange::new`` and the v0 reference's
        # constructor behaviour.
        ir = IntRange(10, 1, -1)
        assert ir.start == 1
        assert ir.end == 10
        assert ir.step == 1

    def test_constructor_zero_step_raises(self) -> None:
        with pytest.raises(Exception, match="step must not be zero"):
            IntRange(1, 10, 0)

    def test_constructor_ascending_with_negative_step_raises(self) -> None:
        with pytest.raises(Exception, match="ascending range"):
            IntRange(1, 10, -1)

    def test_len_step_1(self) -> None:
        assert len(IntRange(1, 10, 1)) == 10

    def test_len_with_step(self) -> None:
        assert len(IntRange(1, 9, 2)) == 5  # [1, 3, 5, 7, 9]

    def test_iter(self) -> None:
        assert list(IntRange(1, 5, 1)) == [1, 2, 3, 4, 5]

    def test_contains(self) -> None:
        ir = IntRange(1, 9, 2)
        assert 1 in ir
        assert 3 in ir
        assert 9 in ir
        assert 2 not in ir
        assert 10 not in ir

    def test_repr(self) -> None:
        assert repr(IntRange(1, 10, 1)) == "IntRange(start=1, end=10, step=1)"
        assert repr(IntRange(5, 15, 2)) == "IntRange(start=5, end=15, step=2)"

    def test_eq(self) -> None:
        assert IntRange(1, 10, 1) == IntRange(1, 10, 1)
        assert IntRange(1, 10, 1) != IntRange(1, 10, 2)
        assert IntRange(1, 10, 1) != IntRange(2, 10, 1)
        assert IntRange(1, 10, 1) != IntRange(1, 11, 1)

    def test_hashable(self) -> None:
        # Same values hash to the same value.
        assert hash(IntRange(1, 10, 1)) == hash(IntRange(1, 10, 1))
        # Usable as set / dict key.
        s = {IntRange(1, 10, 1), IntRange(1, 10, 2), IntRange(1, 10, 1)}
        assert len(s) == 2  # the duplicate is collapsed

    def test_pickle_round_trip(self) -> None:
        import pickle

        original = IntRange(1, 10, 2)
        loaded = pickle.loads(pickle.dumps(original))
        assert loaded == original
        assert (loaded.start, loaded.end, loaded.step) == (1, 9, 2)


class TestRangeExprRangesReturnsIntRange:
    """``RangeExpr.ranges()`` returns a list of ``IntRange``
    instances (not bare ``(start, end, step)`` tuples). This matches
    the v0 reference's shape and lets callers attribute-access the
    components (``.start`` / ``.end`` / ``.step``) without
    positional-tuple bookkeeping."""

    def test_single_range_returns_intrange(self) -> None:
        r = RangeExpr("1-10")
        ranges = r.ranges()
        assert len(ranges) == 1
        assert isinstance(ranges[0], IntRange)
        assert ranges[0] == IntRange(1, 10, 1)

    def test_multi_range_returns_intrange_list(self) -> None:
        r = RangeExpr("1-3,10-12")
        ranges = r.ranges()
        assert len(ranges) == 2
        assert all(isinstance(ir, IntRange) for ir in ranges)
        assert ranges[0] == IntRange(1, 3, 1)
        assert ranges[1] == IntRange(10, 12, 1)

    def test_stepped_range(self) -> None:
        r = RangeExpr("1-10:3")
        ranges = r.ranges()
        assert len(ranges) == 1
        # Upstream normalises: the last value reachable by stepping is 10.
        assert ranges[0] == IntRange(1, 10, 3)
        # Confirm the iteration shape matches RangeExpr's iteration.
        assert list(ranges[0]) == list(r)
