# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Fuzz tests for openjd.expr using Hypothesis.

These tests use random input generation to find crashes and edge cases.
Run with: hatch run fuzz:expr
"""

from __future__ import annotations

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from openjd.expr import parse_expression, ExpressionError

pytestmark = pytest.mark.fuzz


class TestParserFuzz:
    """Fuzz the expression parser with arbitrary strings."""

    @given(expr=st.text(max_size=200))
    @settings(suppress_health_check=[HealthCheck.too_slow])
    def test_parser_no_crash(self, expr: str) -> None:
        """Parser should never crash - only raise ExpressionError for invalid input."""
        try:
            parse_expression(expr)
        except ExpressionError:
            pass  # Expected for invalid input

    @given(data=st.binary(max_size=200))
    @settings(suppress_health_check=[HealthCheck.too_slow])
    def test_parser_binary_no_crash(self, data: bytes) -> None:
        """Parser handles arbitrary bytes decoded as UTF-8."""
        try:
            expr = data.decode("utf-8", errors="replace")
            parse_expression(expr)
        except ExpressionError:
            pass
