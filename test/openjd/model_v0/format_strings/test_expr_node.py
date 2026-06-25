# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for the EXPR-extension format-string seam (Rust-backed ExprNode).

These cover the v0 model delegating {{ }} expression parsing/evaluation to the
Rust openjd-expr engine when the EXPR extension is declared, and preserving the
legacy Name.Dot.Name behaviour when it is not.
"""

import pytest

from openjd.expr import PathFormat
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

    def test_native_list_symbol_inferred(self):
        # A native list value is inferred as a typed list by the Rust
        # build_symbol_table bridge, so aggregate functions work without an
        # explicit type entry.
        node = parse_format_string_expr("sum(Param.Items)", context=_ctx(["EXPR"]))
        st = SymbolTable()
        st["Param.Items"] = [1, 2, 3]
        assert node.evaluate(symtab=st) == 6


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


class TestExprRangeExprTypedValidation:
    """RANGE_EXPR job-parameter symbols now type-check (the OpenJD-type → EXPR
    mapping resolves RANGE_EXPR to the engine's ``range_expr`` type instead of
    the former ``None`` that fell back to name-only validation). Mirrors the
    openjd-rs range_expr behaviour.
    """

    def _validate(self, expr):
        node = parse_format_string_expr(expr, context=_ctx(["EXPR"]))
        node.validate_symbol_refs(
            symbols={"Param.Frames"}, symbol_types={"Param.Frames": "range_expr"}
        )

    @pytest.mark.parametrize(
        "expr",
        [
            "Param.Frames[0]",  # subscript -> int
            "len(Param.Frames)",  # length of the range
            "list(Param.Frames)",  # convert to list[int]
        ],
    )
    def test_valid_range_expr_ops_typecheck(self, expr):
        self._validate(expr)  # does not raise

    def test_type_mismatch_rejected(self):
        # Arithmetic with a range_expr is a genuine type error, now caught at
        # validation time rather than slipping through name-only validation.
        with pytest.raises(ExpressionError, match=r"range_expr"):
            self._validate("Param.Frames + 1")

    def test_invalid_method_rejected(self):
        with pytest.raises(ExpressionError, match=r"not available for range_expr"):
            self._validate("Param.Frames.upper()")


class TestExprErrors:
    def test_parse_error_is_model_expression_error(self):
        with pytest.raises(ExpressionError):
            parse_format_string_expr("Param.X +", context=_ctx(["EXPR"]))


class TestExprPaths:
    """PATH-typed expression coverage mirroring the openjd-rs path tests
    (``crates/openjd-expr/tests/integration/test_paths.rs`` and
    ``test_rfc_examples.rs``): path construction, the path properties/methods
    (``.name``/``.stem``/``.suffix``/``.parent``/``.with_suffix``), POSIX vs
    Windows ``path_format`` behavior, and PATH-typed symbol coercion. PR #285
    review C4.
    """

    def _eval(self, expr, *, path_format=PathFormat.POSIX, symtab=None):
        node = parse_format_string_expr(expr, context=_ctx(["EXPR"]))
        return node.evaluate(symtab=symtab or SymbolTable(), path_format=path_format)

    def test_path_constructor(self):
        assert self._eval("path('/tmp/file.txt')") == "/tmp/file.txt"

    def test_path_from_parts_list(self):
        # path(list[string]) reconstructs a path from its parts.
        assert self._eval("path(['/', 'a', 'b', 'c'])") == "/a/b/c"

    def test_name(self):
        assert self._eval("path('/a/b/render.exr').name") == "render.exr"

    def test_stem(self):
        assert self._eval("path('/a/b/render.exr').stem") == "render"

    def test_suffix(self):
        assert self._eval("path('/a/b/render.exr').suffix") == ".exr"

    def test_parent(self):
        assert self._eval("path('/a/b/c').parent") == "/a/b"

    @pytest.mark.parametrize(
        "expr,expected",
        [
            (
                "path('/projects/shot01/render.exr').with_suffix('.png')",
                "/projects/shot01/render.png",
            ),
            ("path('/projects/shot01/render.exr').with_suffix('')", "/projects/shot01/render"),
            (
                "path('/projects/shot01/render.exr').with_name('output.png')",
                "/projects/shot01/output.png",
            ),
            (
                "path('/projects/shot01/render.exr').with_stem('final')",
                "/projects/shot01/final.exr",
            ),
        ],
    )
    def test_with_suffix_name_stem(self, expr, expected):
        assert self._eval(expr) == expected

    def test_windows_as_posix(self):
        # Convert a Windows path to POSIX separators for shell scripts.
        assert (
            self._eval(r"path('C:\\renders\\project').as_posix()", path_format=PathFormat.WINDOWS)
            == "C:/renders/project"
        )

    def test_join_operator_and_suffix(self):
        # RFC example: (OutputDir / InputFile.name).with_suffix('.png')
        assert (
            self._eval(
                "(path('/output') / path('/in/scene.exr').name).with_suffix('.png')",
            )
            == "/output/scene.png"
        )

    def test_path_typed_symbol_method_access(self):
        # A PATH-typed job-parameter symbol (stored as a string by create_job)
        # is coerced to a path via the types map, so method/property access
        # works just like the Rust engine.
        st = SymbolTable()
        st["Param.File"] = "/a/b/render.exr"
        st.expr_types = {"Param.File": "PATH"}  # type: ignore[attr-defined]
        node = parse_format_string_expr("Param.File.name", context=_ctx(["EXPR"]))
        assert node.evaluate(symtab=st, path_format=PathFormat.POSIX) == "render.exr"
