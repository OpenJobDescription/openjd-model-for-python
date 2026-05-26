# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest
import re

from openjd.model._internal import validate_step_parameter_space_dimensions
from openjd.model import ExpressionError


@pytest.mark.parametrize(
    "param_ranges, combination",
    [
        pytest.param({"A": 5}, "A", id="Identifier"),
        pytest.param({"A": 5, "B": 10}, "A * B", id="Product"),
        pytest.param({"A": 5, "B": 5}, "(A,B)", id="Association"),
        pytest.param({"A": 5, "B": 5, "C": 10}, "(A,B)*C", id="Association-Product"),
        pytest.param({"A": 5, "B": 5, "C": 10}, "C*(A,B)", id="Product-Association"),
        pytest.param({"A": 5, "B": 5, "C": 1}, "(A*C,B)", id="Nested product 2"),
        pytest.param({"A": 5, "B": 5, "C": 1}, "(A,B*C)", id="Nested product 2"),
        pytest.param({"A": 5, "B": 5, "C": 5}, "((A,C),B)", id="Nested association 1"),
        pytest.param({"A": 5, "B": 5, "C": 5}, "(A,(B,C))", id="Nested association 2"),
    ],
)
def test_allowable(param_ranges: dict[str, int], combination: str) -> None:
    # Test that perfectly valid parameter spaces do not raise exceptions

    # THEN
    validate_step_parameter_space_dimensions(param_ranges, combination)


@pytest.mark.parametrize(
    "param_ranges, combination, expected_exception",
    [
        pytest.param(
            {"A": 5, "B": 10},
            "(A,B)",
            "Associative expressions must have arguments with identical ranges. Expression (A, B) has argument lengths (5, 10).",
            id="2-arg",
        ),
        pytest.param(
            {"A": 5, "B": 10, "C": 10},
            "(A,B,C)",
            "Associative expressions must have arguments with identical ranges. Expression (A, B, C) has argument lengths (5, 10, 10).",
            id="3-arg; A",
        ),
        pytest.param(
            {"A": 10, "B": 5, "C": 10},
            "(A,B,C)",
            "Associative expressions must have arguments with identical ranges. Expression (A, B, C) has argument lengths (10, 5, 10).",
            id="3-arg; B",
        ),
        pytest.param(
            {"A": 10, "B": 10, "C": 5},
            "(A,B,C)",
            "Associative expressions must have arguments with identical ranges. Expression (A, B, C) has argument lengths (10, 10, 5).",
            id="3-arg; C",
        ),
        pytest.param(
            {"A": 5, "B": 5, "C": 5},
            "(A,B*C)",
            "Associative expressions must have arguments with identical ranges. Expression (A, B * C) has argument lengths (5, 25).",
            id="Nested product",
        ),
        pytest.param(
            {"A": 5, "B": 10, "C": 10},
            "(A,(B,C))",
            "Associative expressions must have arguments with identical ranges. Expression (A, (B, C)) has argument lengths (5, 10).",
            id="Nested Association",
        ),
        pytest.param(
            {"A": 5, "B": 10, "C": 10},
            "C * (A,B)",
            "Associative expressions must have arguments with identical ranges. Expression (A, B) has argument lengths (5, 10).",
            id="Recurse to association 1",
        ),
        pytest.param(
            {"A": 5, "B": 10, "C": 10},
            "(A,B) * C",
            "Associative expressions must have arguments with identical ranges. Expression (A, B) has argument lengths (5, 10).",
            id="Recurse to association 2",
        ),
    ],
)
def test_mismatched_association(
    param_ranges: dict[str, int], combination: str, expected_exception: str
) -> None:
    # Test that expressions that contain associations with mismatched argument lengths
    # all raise the expected exception.

    # THEN
    with pytest.raises(ExpressionError, match=re.escape(expected_exception)):
        validate_step_parameter_space_dimensions(param_ranges, combination)
