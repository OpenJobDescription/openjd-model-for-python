# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for method call implicit type coercion behavior.

RFC 0005 specifies that when using UFCS (Uniform Function Call Syntax),
implicit type coercion should NOT apply to the first parameter (the receiver)
when calling a function as a method.

For example:
- `startswith('/foo/bar', '/foo')` - function call, coercion applies to both args
- `'/foo/bar'.startswith('/foo')` - method call, no coercion on receiver

This ensures that method calls are type-safe on the receiver.
"""

import pytest
from openjd.expr import evaluate_expression, ExpressionError
from openjd.expr import PathFormat


class TestMethodCallNoReceiverCoercion:
    """Tests that method calls do NOT coerce the receiver (first argument)."""

    def test_path_startswith_as_method_fails(self) -> None:
        """path.startswith() should fail - no path->string coercion on receiver."""
        # startswith(string, string) exists, but path.startswith() should NOT
        # coerce path to string for the receiver
        with pytest.raises(ExpressionError, match="startswith\\(\\) is not available for path"):
            evaluate_expression("path('/foo/bar').startswith('/foo')")

    def test_path_startswith_as_function_succeeds(self) -> None:
        """startswith(path, string) should succeed with coercion."""
        # When called as a function, coercion applies to all arguments
        result = evaluate_expression(
            "startswith(path('/foo/bar'), '/foo')",
            path_format=PathFormat.POSIX,
        )
        assert result.item() is True

    def test_path_endswith_as_method_fails(self) -> None:
        """path.endswith() should fail - no path->string coercion on receiver."""
        with pytest.raises(ExpressionError, match="endswith\\(\\) is not available for path"):
            evaluate_expression("path('/foo/bar').endswith('bar')")

    def test_path_endswith_as_function_succeeds(self) -> None:
        """endswith(path, string) should succeed with coercion."""
        result = evaluate_expression("endswith(path('/foo/bar'), 'bar')")
        assert result.item() is True

    def test_path_split_as_method_fails(self) -> None:
        """path.split() should fail - no path->string coercion on receiver."""
        with pytest.raises(ExpressionError, match="split\\(\\) is not available for path"):
            evaluate_expression("path('/foo/bar').split('/')")

    def test_path_split_as_function_succeeds(self) -> None:
        """split(path, string) should succeed with coercion."""
        result = evaluate_expression(
            "split(path('/foo/bar'), '/')",
            path_format=PathFormat.POSIX,
        )
        assert result.item() == ["", "foo", "bar"]

    def test_string_method_on_string_works(self) -> None:
        """String methods on string receivers should work normally."""
        assert evaluate_expression("'hello'.upper()").item() == "HELLO"
        assert evaluate_expression("'hello'.startswith('hel')").item() is True

    def test_int_method_coercion_blocked(self) -> None:
        """int.method() should not coerce int to float for receiver."""
        # If there's a function that takes (float) but not (int), calling it
        # as a method on int should fail
        # Note: Most math functions have both int and float signatures,
        # so we need to find one that only has float
        pass  # Skip for now - need to find a suitable function

    def test_function_call_coerces_all_args(self) -> None:
        """Function calls should coerce all arguments including first."""
        # min(float, float) should work with int args via coercion
        result = evaluate_expression("min(1, 2.5)")
        assert result.item() == 1.0

    def test_method_call_coerces_non_receiver_args(self) -> None:
        """Method calls should still coerce non-receiver arguments."""
        # For a method like replace(string, string, string), the 2nd and 3rd
        # args can still be coerced if needed
        # Currently all string functions take string args, so this is a no-op test
        result = evaluate_expression("'hello'.replace('l', 'L')")
        assert result.item() == "heLLo"
