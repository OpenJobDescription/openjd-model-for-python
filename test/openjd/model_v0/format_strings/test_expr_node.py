# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for the EXPR-extension format-string seam (Rust-backed ExprNode).

These cover the v0 model delegating {{ }} expression parsing/evaluation to the
Rust openjd-expr engine when the EXPR extension is declared, and preserving the
legacy Name.Dot.Name behaviour when it is not.
"""

import pytest

from openjd.model import ExpressionError
from openjd.model._format_strings._nodes import ExprNode, FullNameNode
from openjd.model._format_strings._parser import parse_format_string_expr
from openjd.model._symbol_table import SymbolTable
from openjd.model.v2023_09 import ModelParsingContext as ModelParsingContext_v2023_09


def _ctx(extensions):
    """A parsing context whose *declared* extension set is `extensions`.

    Mirrors the post-`extensions`-field state where context.extensions holds
    the template's declared extensions.
    """
    ctx = ModelParsingContext_v2023_09(supported_extensions=extensions)
    ctx.extensions = set(extensions)
    return ctx


class TestExprGating:
    def test_expr_declared_yields_expr_node(self):
        node = parse_format_string_expr("Param.X + 3", context=_ctx(["EXPR"]))
        assert isinstance(node, ExprNode)

    def test_expr_not_declared_yields_fullname_node(self):
        node = parse_format_string_expr("Param.X", context=_ctx([]))
        assert isinstance(node, FullNameNode)

    def test_expr_grammar_rejected_without_extension(self):
        # '+' is not part of the legacy Name.Dot.Name grammar.
        with pytest.raises(ExpressionError):
            parse_format_string_expr("Param.X + 3", context=_ctx([]))

    def test_plain_name_still_parses_with_expr(self):
        node = parse_format_string_expr("Param.X", context=_ctx(["EXPR"]))
        assert isinstance(node, ExprNode)


class TestExprEvaluate:
    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("Param.X + 3", 13),
            ("Param.X - 3", 7),
            ("Param.X * 2", 20),
            ("Param.X // 3", 3),
            ("2 ** 3", 8),
            ("-Param.X", -10),
            ("(Param.X + 1) * 2", 22),
        ],
    )
    def test_arithmetic(self, expr, expected):
        node = parse_format_string_expr(expr, context=_ctx(["EXPR"]))
        st = SymbolTable()
        st["Param.X"] = 10
        assert node.evaluate(symtab=st) == expected

    def test_function_library_available(self):
        # repr_sh is part of the standard EXPR function library and must be
        # reachable through the default profile.
        node = parse_format_string_expr("repr_sh('a b')", context=_ctx(["EXPR"]))
        assert node.evaluate(symtab=SymbolTable()) == "'a b'"

    def test_list_result_allowed(self):
        node = parse_format_string_expr("[1, 2, 3]", context=_ctx(["EXPR"]))
        assert node.evaluate(symtab=SymbolTable()) == [1, 2, 3]

    def test_typed_string_symbol_coerced_via_types(self):
        # When a types map is supplied, a string-valued symbol is coerced to
        # the declared EXPR type (INT) so arithmetic works.
        node = parse_format_string_expr("Param.X + 1", context=_ctx(["EXPR"]))
        st = SymbolTable()
        st["Param.X"] = "10"  # stringly-typed, as create_job stores it
        st.expr_types = {"Param.X": "INT"}  # type: ignore[attr-defined]
        assert node.evaluate(symtab=st) == 11


class TestExprSymbolRefValidation:
    def test_missing_symbol_raises(self):
        node = parse_format_string_expr("Param.X + 1", context=_ctx(["EXPR"]))
        with pytest.raises(ValueError):
            node.validate_symbol_refs(symbols={"Param.Y"})

    def test_present_symbol_ok(self):
        node = parse_format_string_expr("Param.X + 1", context=_ctx(["EXPR"]))
        node.validate_symbol_refs(symbols={"Param.X"})

    def test_let_local_not_treated_as_free_symbol(self):
        # Comprehension-local names must not be reported as missing free
        # symbols; only the free reference (Param.Items) is validated.
        node = parse_format_string_expr("[x * 2 for x in Param.Items]", context=_ctx(["EXPR"]))
        node.validate_symbol_refs(symbols={"Param.Items"})


class TestExprErrors:
    def test_parse_error_is_model_expression_error(self):
        with pytest.raises(ExpressionError):
            parse_format_string_expr("Param.X +", context=_ctx(["EXPR"]))
