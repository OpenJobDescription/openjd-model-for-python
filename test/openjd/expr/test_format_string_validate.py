# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for ``FormatString.validate_expressions``.

This is the spec's static-type-check path for format strings: the
caller populates the symbol table with ``ExprValue.unresolved(T)``
placeholders for symbols whose concrete values are not yet known,
then calls ``validate_expressions`` to drive evaluation through
the unresolved-propagation rules. Failures raise
``FormatStringValidationError`` (a ``ValueError`` subclass) with
a caret-style diagnostic message anchored at the failing
``{{...}}`` interpolation.

Resolves the P2 housekeeping recommendation in
``reports/expr-bindings-quality-evaluation-report.md`` to expose
this method on the binding (it was previously only reachable via
the underlying Rust crate, leaving ``FormatStringValidationError``
registered but unraisable from Python).
"""

from __future__ import annotations

import pytest

from openjd.expr import (
    ExprExtension,
    ExprProfile,
    ExprRevision,
    ExprType,
    ExprValue,
    FormatString,
    FormatStringValidationError,
    SymbolTable,
)


class TestValidateExpressionsSuccess:
    """Cases that validate cleanly and return ``None``."""

    def test_pure_literal(self) -> None:
        # No interpolations ⇒ trivially valid.
        FormatString("just text").validate_expressions(SymbolTable())

    def test_resolved_symbol(self) -> None:
        fs = FormatString("hello {{Param.Name}}")
        fs.validate_expressions(SymbolTable({"Param.Name": "world"}))

    def test_unresolved_placeholder(self) -> None:
        # The intended use: validate against placeholder values
        # whose types are known but values aren't.
        fs = FormatString("hello {{Param.Name}}")
        fs.validate_expressions(
            SymbolTable({"Param.Name": ExprValue.unresolved(ExprType("string"))})
        )

    def test_multiple_segments_all_valid(self) -> None:
        fs = FormatString("{{Param.A}} and {{Param.B}}")
        fs.validate_expressions(
            SymbolTable(
                {
                    "Param.A": ExprValue.unresolved(ExprType("int")),
                    "Param.B": ExprValue.unresolved(ExprType("string")),
                }
            )
        )

    def test_returns_none(self) -> None:
        # Spec contract: returns None on success (i.e. it's a
        # validator, not a value-producing call). Mypy already
        # knows the return type is None, so any positive
        # assertion that compares to None is flagged as a no-op
        # (`func-returns-value`). Just exercise the call and let
        # the absence of an exception serve as the assertion.
        FormatString("hello").validate_expressions(SymbolTable())

    def test_complex_expression_with_expr_extension(self) -> None:
        # An EXPR-extension expression resolves cleanly when the
        # right profile is supplied and operand types match.
        prof = ExprProfile(ExprRevision.CURRENT, extensions=ExprExtension.ALL)
        fs = FormatString("{{Param.X + 1}}")
        fs.validate_expressions(
            SymbolTable({"Param.X": ExprValue.unresolved(ExprType("int"))}),
            profile=prof,
        )


class TestValidateExpressionsFailure:
    """Cases that raise ``FormatStringValidationError``."""

    def test_undefined_symbol(self) -> None:
        fs = FormatString("hello {{Param.Missing}}")
        with pytest.raises(FormatStringValidationError) as exc_info:
            fs.validate_expressions(SymbolTable())
        # The error wraps the underlying ExpressionError message
        # plus a caret-style diagnostic anchored at the failing
        # {{...}} segment.
        msg = str(exc_info.value)
        assert "Failed to parse interpolation expression" in msg
        assert "Undefined variable" in msg
        assert "Param.Missing" in msg

    def test_undefined_symbol_carries_segment_offsets(self) -> None:
        # The diagnostic includes byte offsets of the failing
        # {{...}} pair so callers can highlight precisely.
        fs = FormatString("prefix {{Param.X}} suffix")
        with pytest.raises(FormatStringValidationError) as exc_info:
            fs.validate_expressions(SymbolTable())
        msg = str(exc_info.value)
        # `{{Param.X}}` runs from offset 7 to 18 (exclusive of `}}`
        # itself: `[7, 18]`).
        assert "[7, 18]" in msg

    def test_type_mismatch_with_expr_extension(self) -> None:
        # Validation runs the expression as if for evaluation, so
        # type errors during evaluation surface as
        # FormatStringValidationError.
        prof = ExprProfile(ExprRevision.CURRENT, extensions=ExprExtension.ALL)
        fs = FormatString("{{Param.X + 1}}")
        with pytest.raises(FormatStringValidationError) as exc_info:
            fs.validate_expressions(
                SymbolTable({"Param.X": "not a number"}),
                profile=prof,
            )
        msg = str(exc_info.value)
        assert "Cannot use '+' operator" in msg

    def test_first_failure_short_circuits(self) -> None:
        # The Rust contract is to return on the first error, not
        # accumulate. Mixing a known-bad segment with a known-good
        # one yields exactly one error pointing at the bad one.
        fs = FormatString("{{Param.Bad}} {{Param.Good}}")
        with pytest.raises(FormatStringValidationError) as exc_info:
            fs.validate_expressions(
                SymbolTable(
                    {
                        # Param.Good is defined, Param.Bad is not.
                        "Param.Good": ExprValue.unresolved(ExprType("string")),
                    }
                )
            )
        msg = str(exc_info.value)
        # The diagnostic offsets `[0, 13]` point at the FIRST
        # segment (the bad one), not the second — short-circuit
        # behaviour. (`Param.Good` may still appear in the message
        # as a "Did you mean: Param.Good" suggestion attached to
        # the underlying ExpressionError, so we don't assert on
        # its absence.)
        assert "Param.Bad" in msg
        assert "[0, 13]" in msg

    def test_inherits_from_value_error(self) -> None:
        # ``FormatStringValidationError`` is registered as a
        # ``ValueError`` subclass so callers that catch the broad
        # exception still see these.
        fs = FormatString("{{Param.X}}")
        with pytest.raises(ValueError):
            fs.validate_expressions(SymbolTable())


class TestValidateExpressionsArgumentForms:
    """Argument-shape tests: positional symtab, keyword
    library/profile, dict-as-symtab acceptance."""

    def test_dict_accepted_as_symtab(self) -> None:
        # Like ``resolve_string`` / ``resolve``, ``validate_expressions``
        # accepts a plain ``dict`` and coerces it to a SymbolTable
        # internally.
        fs = FormatString("{{Param.Name}}")
        fs.validate_expressions({"Param.Name": "x"})

    def test_symtab_is_positional_only_required(self) -> None:
        # Calling with no arguments should fail at the Python level.
        fs = FormatString("hello")
        with pytest.raises(TypeError):
            fs.validate_expressions()  # type: ignore[call-arg]

    def test_library_and_profile_are_keyword_only(self) -> None:
        # Mirrors ``resolve_string`` / ``resolve`` — only ``symtab``
        # is positional. ``profile`` (the lone keyword arg, after
        # the removal of ``library``) cannot be passed positionally.
        fs = FormatString("hello")
        with pytest.raises(TypeError):
            fs.validate_expressions(SymbolTable(), None)  # type: ignore[misc]
