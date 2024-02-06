# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from unittest.mock import patch

import pytest

from openjd.model import ExpressionError, SymbolTable, TokenError
from openjd.model._format_strings._expression import InterpolationExpression
from openjd.model._format_strings._parser import Parser


class TestInterpolationExpression:
    def test_init_builds_expr_tree(self):
        with patch.object(Parser, "parse") as mock:
            # WHEN
            InterpolationExpression("Foo.Bar")

            # THEN
            mock.assert_called_once_with("Foo.Bar")

    def test_init_reraises_parse_error(self):
        # GIVEN
        expr = ".."

        # THEN
        with pytest.raises(TokenError):
            InterpolationExpression(expr)

    def test_init_reraises_tokenizer_error(self):
        # GIVEN
        expr = "!!"

        # THEN
        with pytest.raises(TokenError):
            InterpolationExpression(expr)

    def test_validate_success(self) -> None:
        # GIVEN
        symbols = set(("Test.Name",))
        expr = InterpolationExpression("Test.Name")

        # THEN
        expr.validate_symbol_refs(symbols=symbols)  # Does not raise

    @pytest.mark.parametrize(
        "symbols, expr, error_matches",
        [
            pytest.param(
                set(),
                "Test.Foo",
                "Variable Test.Foo does not exist at this location.",
                id="empty set",
            ),
            pytest.param(
                set(("Test.Foo", "Test.Boo", "Test.Another")),
                "Tst.Foo",
                "Variable Tst.Foo does not exist at this location. Did you mean: Test.Foo",
                id="one candidate",
            ),
            pytest.param(
                set(("Test.Foo", "Test.Boo", "Test.Another")),
                "Test.Zoo",
                "Variable Test.Zoo does not exist at this location. Did you mean one of: Test.Boo, Test.Foo",
                id="two candidates",
            ),
        ],
    )
    def test_validate_error(self, symbols: set[str], expr: str, error_matches: str) -> None:
        # GIVEN
        test = InterpolationExpression(expr)

        # THEN
        with pytest.raises(ValueError, match=error_matches):
            test.validate_symbol_refs(symbols=symbols)

    def test_evaluate_success(self):
        # GIVEN
        symtab = SymbolTable()
        symtab["Test.Name"] = "value"
        expr = InterpolationExpression("Test.Name")

        # WHEN
        result = expr.evaluate(symtab=symtab)

        # THEN
        assert result == "value"

    def test_evaluate_fails(self):
        # GIVEN
        symtab = SymbolTable()
        symtab["Test.Name"] = "value"

        # WHEN
        expr = InterpolationExpression("Test.Fail")

        # THEN
        with pytest.raises(ExpressionError) as exc:
            expr.evaluate(symtab=symtab)

        assert "Test.Fail" in str(exc), "Name should be in validation error"

    def test_evaluate_badtype(self):
        # GIVEN
        symtab = SymbolTable()
        symtab["Test.Name"] = {"foo": "bar"}
        expr = InterpolationExpression("Test.Name")

        # THEN
        with pytest.raises(ExpressionError):
            expr.evaluate(symtab=symtab)
