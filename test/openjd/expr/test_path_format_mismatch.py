# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for path_format mismatch detection between ExprValues and the Evaluator."""

import sys

import pytest
from openjd.expr import evaluate_expression, ExprValue, SymbolTable
from openjd.expr import ExpressionError
from openjd.expr import PathFormat


class TestPathFormatMismatch:
    """Evaluator should raise when a symbol table PATH value has a different path_format."""

    def test_posix_value_in_windows_evaluator(self) -> None:
        val = ExprValue("/tmp/render.exr", type="path", path_format=PathFormat.POSIX)
        symtab = SymbolTable({"P": val})
        with pytest.raises(ExpressionError, match="Path format mismatch"):
            evaluate_expression("P", values=symtab, path_format=PathFormat.WINDOWS)

    def test_windows_value_in_posix_evaluator(self) -> None:
        val = ExprValue(r"C:\renders\shot01", type="path", path_format=PathFormat.WINDOWS)
        symtab = SymbolTable({"P": val})
        with pytest.raises(ExpressionError, match="Path format mismatch"):
            evaluate_expression("P", values=symtab, path_format=PathFormat.POSIX)

    def test_matching_format_no_error(self) -> None:
        val = ExprValue("/tmp/render.exr", type="path", path_format=PathFormat.POSIX)
        symtab = SymbolTable({"P": val})
        result = evaluate_expression("P", values=symtab, path_format=PathFormat.POSIX)
        assert str(result) == "/tmp/render.exr"

    def test_create_path_defaults_to_host_format(self) -> None:
        """Creating a path without explicit path_format defaults to host native."""
        val = ExprValue("/tmp/test", type="path")
        expected = "\\tmp\\test" if sys.platform == "win32" else "/tmp/test"
        assert str(val) == expected

    def test_evaluator_defaults_to_host_format(self) -> None:
        """When evaluator has path_format=None, it defaults to host native format."""
        host_format = PathFormat.WINDOWS if sys.platform == "win32" else PathFormat.POSIX
        val = ExprValue("/tmp/render.exr", type="path", path_format=host_format)
        symtab = SymbolTable({"P": val})
        result = evaluate_expression("P", values=symtab, path_format=None)
        assert str(result) == str(val)

    def test_list_path_mismatch(self) -> None:
        val = ExprValue(["/a", "/b"], type="list[path]", path_format=PathFormat.POSIX)
        symtab = SymbolTable({"Paths": val})
        with pytest.raises(ExpressionError, match="Path format mismatch"):
            evaluate_expression("Paths", values=symtab, path_format=PathFormat.WINDOWS)

    def test_list_path_matching_no_error(self) -> None:
        val = ExprValue(["/a", "/b"], type="list[path]", path_format=PathFormat.POSIX)
        symtab = SymbolTable({"Paths": val})
        result = evaluate_expression("Paths", values=symtab, path_format=PathFormat.POSIX)
        assert result.item() == ["/a", "/b"]

    def test_mismatch_error_message_includes_variable_name(self) -> None:
        val = ExprValue("/tmp/test", type="path", path_format=PathFormat.WINDOWS)
        symtab = SymbolTable({"Param": {"InputFile": val}})
        with pytest.raises(ExpressionError, match="Param.InputFile"):
            evaluate_expression("Param.InputFile", values=symtab, path_format=PathFormat.POSIX)

    def test_non_path_types_no_check(self) -> None:
        """INT, STRING, etc. should never trigger the check."""
        symtab = SymbolTable(
            {
                "x": ExprValue(42),
                "s": ExprValue("hello"),
                "b": ExprValue(True),
            }
        )
        assert evaluate_expression("x", values=symtab, path_format=PathFormat.POSIX).item() == 42
        assert (
            evaluate_expression("s", values=symtab, path_format=PathFormat.POSIX).item() == "hello"
        )
        assert evaluate_expression("b", values=symtab, path_format=PathFormat.POSIX).item() is True
