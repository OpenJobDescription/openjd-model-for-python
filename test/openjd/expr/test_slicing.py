# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for slicing operations (RFC 0005/0006)."""

import pytest

from openjd.expr import evaluate_expression
from openjd.expr import ExpressionError


class TestListSlicing:
    """Tests for list slicing."""

    def test_basic_slice(self):
        result = evaluate_expression("[1, 2, 3, 4, 5][1:4]")
        assert str(result) == "[2, 3, 4]"

    def test_slice_from_start(self):
        result = evaluate_expression("[1, 2, 3, 4, 5][:3]")
        assert str(result) == "[1, 2, 3]"

    def test_slice_to_end(self):
        result = evaluate_expression("[1, 2, 3, 4, 5][2:]")
        assert str(result) == "[3, 4, 5]"

    def test_slice_with_step(self):
        result = evaluate_expression("[1, 2, 3, 4, 5][::2]")
        assert str(result) == "[1, 3, 5]"

    def test_slice_reverse(self):
        result = evaluate_expression("[1, 2, 3, 4, 5][::-1]")
        assert str(result) == "[5, 4, 3, 2, 1]"

    def test_slice_negative_start(self):
        result = evaluate_expression("[1, 2, 3, 4, 5][-3:]")
        assert str(result) == "[3, 4, 5]"

    def test_slice_negative_stop(self):
        result = evaluate_expression("[1, 2, 3, 4, 5][1:-1]")
        assert str(result) == "[2, 3, 4]"

    def test_slice_empty_result(self):
        result = evaluate_expression("[1, 2, 3][5:10]")
        assert str(result) == "[]"

    def test_slice_step_zero_error(self):
        with pytest.raises(ExpressionError, match="step cannot be zero"):
            evaluate_expression("[1, 2, 3][::0]")


class TestStringSlicing:
    """Tests for string slicing."""

    def test_basic_slice(self):
        result = evaluate_expression('"hello"[1:4]')
        assert str(result) == "ell"

    def test_slice_from_start(self):
        result = evaluate_expression('"hello"[:3]')
        assert str(result) == "hel"

    def test_slice_to_end(self):
        result = evaluate_expression('"hello"[2:]')
        assert str(result) == "llo"

    def test_slice_reverse(self):
        result = evaluate_expression('"hello"[::-1]')
        assert str(result) == "olleh"

    def test_slice_with_step(self):
        result = evaluate_expression('"abcdefg"[::2]')
        assert str(result) == "aceg"

    def test_single_index(self):
        result = evaluate_expression('"hello"[0]')
        assert str(result) == "h"

    def test_negative_index(self):
        result = evaluate_expression('"hello"[-1]')
        assert str(result) == "o"

    def test_index_out_of_bounds(self):
        with pytest.raises(ExpressionError, match="out of bounds"):
            evaluate_expression('"hello"[10]')


class TestRangeExprSlicing:
    """Tests for range_expr slicing."""

    def test_basic_slice(self):
        result = evaluate_expression('range_expr("1-10")[2:5]')
        assert str(result) == "3-5"

    def test_slice_with_step(self):
        result = evaluate_expression('range_expr("1-10")[::2]')
        assert str(result) == "1-9:2"

    def test_slice_reverse(self):
        result = evaluate_expression('range_expr("1-5")[::-1]')
        assert str(result) == "[5, 4, 3, 2, 1]"

    def test_slice_negative_indices(self):
        result = evaluate_expression('range_expr("1-10")[-3:]')
        assert str(result) == "8-10"


class TestPathSlicing:
    """Tests confirming path is NOT subscriptable (matching Python pathlib behavior)."""

    def test_path_index_not_supported(self):
        with pytest.raises(ExpressionError, match="Cannot subscript type path"):
            evaluate_expression('path("/a/b/c")[0]')

    def test_path_slice_not_supported(self):
        with pytest.raises(ExpressionError, match="Cannot subscript type path"):
            evaluate_expression('path("/a/b/c")[1:3]')


class TestSlicingWithExpressions:
    """Tests for slicing with expression bounds."""

    def test_slice_with_variable_bounds(self):
        from openjd.expr import SymbolTable

        symtab = SymbolTable({"start": 1, "end": 4})
        result = evaluate_expression("[1, 2, 3, 4, 5][start:end]", values=symtab)
        assert str(result) == "[2, 3, 4]"

    def test_chained_slice(self):
        result = evaluate_expression("[1, 2, 3, 4, 5][1:4][::2]")
        assert str(result) == "[2, 4]"

    def test_slice_on_split_result(self):
        result = evaluate_expression('"a;b;c;d;e".split(";")[:3]')
        assert str(result) == '["a", "b", "c"]'
