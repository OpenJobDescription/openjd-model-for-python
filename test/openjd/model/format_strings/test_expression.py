# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from unittest.mock import patch

import pytest

from openjd.model import ExpressionError, SymbolTable, TokenError, ValidationError
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

    def test_validate_success(self):
        # GIVEN
        symtab = SymbolTable()
        symtab["Test.Name"] = "value"

        # WHEN
        expr = InterpolationExpression("Test.Name")

        # THEN
        try:
            expr.validate(symtab=symtab)
        except ValidationError:
            pytest.fail("Incorrectly identified expression as nonvalid.")

    def test_validate_fails(self):
        # GIVEN
        symtab = SymbolTable()
        symtab["Test.Name"] = "value"

        # WHEN
        expr = InterpolationExpression("Test.Fail")

        # THEN
        with pytest.raises(ValidationError) as exc:
            expr.validate(symtab=symtab)

        assert "Test.Fail" in str(exc), "Name should be in validation error"

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
