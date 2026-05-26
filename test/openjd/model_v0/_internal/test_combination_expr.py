# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest

from openjd.model import ExpressionError, TokenError
from openjd.model._internal import CombinationExpressionParser


class TestTaskParameterSpaceParser:
    @pytest.mark.parametrize(
        "given,expected",
        [
            # (given, expected)
            ("A", "A"),
            # Product
            ("A * B", "Product(A, B)"),
            ("A * B * C * D * E", "Product(A, B, C, D, E)"),
            # Association
            ("(A, B)", "Assoc(A, B)"),
            ("(A, B, C, D, E)", "Assoc(A, B, C, D, E)"),
            # Combinations
            ("A * (B, C)", "Product(A, Assoc(B, C))"),
            ("(B, C) * A", "Product(Assoc(B, C), A)"),
            ("(A * B, C * D)", "Assoc(Product(A, B), Product(C, D))"),
            ("((A, B), (C, D))", "Assoc(Assoc(A, B), Assoc(C, D))"),
        ],
    )
    def test_successful_parses(self, given, expected):
        # GIVEN
        parser = CombinationExpressionParser()

        # WHEN
        result = parser.parse(given)

        # THEN
        assert repr(result) == expected, given
        assert str(result) == given

    @pytest.mark.parametrize("given", ["A A", "* A", "A * *", "(A, B C)"])
    def test_raises_tokenerror(self, given):
        # GIVEN
        parser = CombinationExpressionParser()

        # THEN
        with pytest.raises(TokenError):
            parser.parse(given)

    @pytest.mark.parametrize(
        "given",
        [
            "",
            "(A, B",
            "A * ,",
            "(A)",
            "(A",
            "A *",
        ],
    )
    def test_raises_expressionerror(self, given):
        # GIVEN
        parser = CombinationExpressionParser()

        # THEN
        with pytest.raises(ExpressionError):
            parser.parse(given)
