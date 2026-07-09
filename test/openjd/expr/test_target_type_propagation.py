# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for target-type propagation rules.

Mirrors ``crates/openjd-expr/tests/integration/test_target_type_propagation.rs``
in the ``openjd-rs`` workspace and the reference Python tests in the
``fork/expr`` branch's ``test/openjd/expr/test_target_type_propagation.py``.

Two rules are covered:

1. **Union member match.** When ``target_type`` is a union and the
   evaluated value already matches one of the members, the value is
   returned unchanged with that member's type.
2. **Operand-unconstrained arithmetic.** When ``target_type`` is set,
   operators evaluate their operands without that constraint applied,
   then coerce the result. RFC 0005 § "Operators evaluate operands
   unconstrained" is the canonical statement.

Both behaviours were tracked as gaps in
``reports/expr-bindings-quality-evaluation-report.md`` and resolved
crate-side in ``openjd-rs`` (see report Recommendations #1 and #2).

The reference test suite uses private internal helpers
(``openjd.expr._eval.Evaluator``, ``ast_parse_keyword_context``); the
binding only exposes the public ``evaluate_expression`` entry point, so
the tests here use that — same coverage, same parametrized cases.
"""

from openjd.expr import ExprType, SymbolTable, TypeCode, evaluate_expression

STRING = ExprType("string")
LIST_INT = ExprType("list[int]")
INT_OR_STRING = ExprType("int | string")
RANGE_TARGET = ExprType(TypeCode.UNION, [STRING, LIST_INT])


def _eval(expr: str, symtab=None, target_type=None):
    """Public-API wrapper: invoke ``evaluate_expression`` with the
    binding's user-facing ``values=`` / ``target_type=`` keyword args.
    """
    return evaluate_expression(
        expr,
        values=symtab if symtab is not None else SymbolTable(),
        target_type=target_type,
    )


class TestTargetTypeUnionMembership:
    """A value already in a union member type is returned unchanged."""

    def test_string_in_int_or_string(self) -> None:
        v = _eval("'42'", target_type=INT_OR_STRING)
        assert v.type == STRING
        assert v.item() == "42"


class TestArithmeticInStringContext:
    """Arithmetic works when the target type is STRING.

    RFC 0005 says operators evaluate their operands without the
    target-type constraint, then coerce the result.
    """

    def test_subtraction_with_string_target(self) -> None:
        result = _eval(
            "Param.Count - 1",
            symtab=SymbolTable({"Param.Count": 100}),
            target_type=STRING,
        )
        assert result.item() == "99"

    def test_addition_with_string_target(self) -> None:
        result = _eval(
            "Param.A + Param.B",
            symtab=SymbolTable({"Param.A": 10, "Param.B": 20}),
            target_type=STRING,
        )
        assert result.item() == "30"

    def test_multiplication_with_string_target(self) -> None:
        result = _eval(
            "Param.X * 6",
            symtab=SymbolTable({"Param.X": 7}),
            target_type=STRING,
        )
        assert result.item() == "42"

    def test_division_with_string_target(self) -> None:
        result = _eval(
            "Param.N / 4",
            symtab=SymbolTable({"Param.N": 10}),
            target_type=STRING,
        )
        assert result.item() == "2.5"

    def test_floor_division_with_string_target(self) -> None:
        result = _eval(
            "Param.N // 3",
            symtab=SymbolTable({"Param.N": 10}),
            target_type=STRING,
        )
        assert result.item() == "3"

    def test_modulo_with_string_target(self) -> None:
        result = _eval(
            "Param.N % 3",
            symtab=SymbolTable({"Param.N": 10}),
            target_type=STRING,
        )
        assert result.item() == "1"

    def test_complex_expression_with_string_target(self) -> None:
        """Complex arithmetic like range expressions use."""
        result = _eval(
            "(Param.ImageCount - 1) // Param.ChunkSize",
            symtab=SymbolTable({"Param.ImageCount": 100, "Param.ChunkSize": 10}),
            target_type=STRING,
        )
        assert result.item() == "9"

    def test_nested_arithmetic_with_string_target(self) -> None:
        result = _eval(
            "(Param.End - Param.Start) // Param.Step",
            symtab=SymbolTable({"Param.Start": 0, "Param.End": 100, "Param.Step": 10}),
            target_type=STRING,
        )
        assert result.item() == "10"


class TestArithmeticInRangeContext:
    """Arithmetic in range-expression context (``STRING | LIST_INT``)."""

    def test_subtraction_in_range_context(self) -> None:
        result = _eval(
            "Param.End - 1",
            symtab=SymbolTable({"Param.End": 100}),
            target_type=RANGE_TARGET,
        )
        assert result.item() == "99"

    def test_floor_division_in_range_context(self) -> None:
        result = _eval(
            "(Param.Total - 1) // Param.Chunk",
            symtab=SymbolTable({"Param.Total": 100, "Param.Chunk": 10}),
            target_type=RANGE_TARGET,
        )
        assert result.item() == "9"


class TestComparisonInStringContext:
    """Comparisons work when the target type is STRING."""

    def test_less_than_with_string_target(self) -> None:
        result = _eval(
            "Param.A < Param.B",
            symtab=SymbolTable({"Param.A": 5, "Param.B": 10}),
            target_type=STRING,
        )
        assert result.item() == "true"

    def test_equality_with_string_target(self) -> None:
        result = _eval(
            "Param.X == 42",
            symtab=SymbolTable({"Param.X": 42}),
            target_type=STRING,
        )
        assert result.item() == "true"


class TestUnaryOpInStringContext:
    """Unary operators work when the target type is STRING."""

    def test_negation_with_string_target(self) -> None:
        result = _eval(
            "-Param.N",
            symtab=SymbolTable({"Param.N": 42}),
            target_type=STRING,
        )
        assert result.item() == "-42"

    def test_not_with_string_target(self) -> None:
        result = _eval(
            "not Param.Flag",
            symtab=SymbolTable({"Param.Flag": True}),
            target_type=STRING,
        )
        assert result.item() == "false"


class TestConditionalInStringContext:
    """Conditional expressions propagate target types correctly."""

    def test_conditional_with_string_target(self) -> None:
        result = _eval(
            "100 if Param.Quality == 'high' else 50",
            symtab=SymbolTable({"Param.Quality": "high"}),
            target_type=STRING,
        )
        assert result.item() == "100"

    def test_conditional_arithmetic_with_string_target(self) -> None:
        result = _eval(
            "Param.N * 2 if Param.Flag else Param.N",
            symtab=SymbolTable({"Param.N": 10, "Param.Flag": True}),
            target_type=STRING,
        )
        assert result.item() == "20"
