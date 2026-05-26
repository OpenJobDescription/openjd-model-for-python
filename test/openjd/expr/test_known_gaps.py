# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Failing tests demonstrating behavioural gaps between the Rust-backed
``openjd.expr`` bindings and the pure-Python reference implementation.

Every test here is expected to *fail* against the current bindings and is
marked ``xfail``. As gaps are resolved the corresponding tests are moved
to the appropriate home in this directory (e.g. pickle tests to
``test_pickle.py``, path-mapping tests to ``test_path_mapping.py``);
this file is being driven to zero.

Cross-reference:
    reports/expr-bindings-quality-evaluation-report.md
"""

from __future__ import annotations

from pathlib import PureWindowsPath

import pytest

from openjd.expr import (
    ExprValue,
    ExpressionError,
    PathFormat,
    PathMappingRule,
    SymbolTable,
)


# ── ExprValue NaN / Inf raise plain ValueError, not ExpressionError ──
#
# The pure-Python reference (`openjd.expr._value._create`) raises
# ``ExpressionError`` for NaN and infinity inputs:
#
#     if isnan(float_value):
#         raise ExpressionError("Float operation produced NaN")
#     if isinf(float_value):
#         raise ExpressionError("Float operation produced infinity")
#
# The Rust-backed binding raises a plain ``ValueError`` (carrying the
# message from the underlying ``Float64::new`` validator). Catching
# ``ExpressionError`` no longer covers these paths, so callers porting
# from v0 will see different exception class identity in
# ``except ExpressionError`` blocks. Fix path: have
# ``rust-bindings/src/expr/expr_value.rs::py_to_expr_value`` and
# ``from_float`` map ``Float64::new`` errors through
# ``PyExpressionError::new_err`` instead of ``PyValueError::new_err``,
# matching ``make_list_err_to_py``'s pattern of remapping
# upstream errors to the reference's exception class.
#
# Cross-reference: report Recommendation #1.


class TestExprValueNaNInfErrorClass:
    def test_nan_raises_expression_error(self) -> None:
        with pytest.raises(ExpressionError, match="NaN"):
            ExprValue(float("nan"))

    def test_inf_raises_expression_error(self) -> None:
        with pytest.raises(ExpressionError, match="infinity"):
            ExprValue(float("inf"))

    def test_neg_inf_raises_expression_error(self) -> None:
        with pytest.raises(ExpressionError, match="infinity"):
            ExprValue(float("-inf"))


# Mark every test in the class above as xfail; the ``except`` clause
# matches ``ValueError`` (the binding's current behaviour) but NOT
# ``ExpressionError``, so each assertion above raises a non-matching
# exception today. Pytest collects the four tests into the class so
# we put the marker on the class declaration above.
pytest.mark.xfail(
    reason="Reference raises ExpressionError for NaN/Inf; binding raises plain ValueError",
    raises=ValueError,
    strict=True,
)(TestExprValueNaNInfErrorClass)


# ── ExprValue(int outside i64) leaks the inner OverflowError text ──
#
# The reference raises:
#
#     ExpressionError("Integer overflow: result is outside the 64-bit signed range")
#
# The binding currently produces a longer message that leaks the inner
# PyO3 OverflowError into the user-visible string:
#
#     "Integer overflow: value does not fit in i64
#      (OverflowError: Python int too large to convert to C long)"
#
# This drifts the message away from the reference and surfaces an
# implementation detail of the binding. Fix path:
# ``rust-bindings/src/expr/expr_value.rs::py_to_expr_value`` should
# raise ``PyExpressionError::new_err("Integer overflow: result is
# outside the 64-bit signed range")`` for the ``i64`` extract failure,
# matching the reference message verbatim.
#
# Cross-reference: report Recommendation #2.


@pytest.mark.xfail(
    reason="Binding leaks underlying OverflowError text; reference uses canonical phrasing",
    strict=True,
)
def test_expr_value_int_overflow_message_matches_reference() -> None:
    with pytest.raises(ExpressionError) as excinfo:
        ExprValue(2**63)  # one past i64::MAX
    # Reference's exact message — no "value does not fit in i64",
    # no "(OverflowError: ...)" suffix.
    assert str(excinfo.value) == "Integer overflow: result is outside the 64-bit signed range"


# ── PathMappingRule constructor raises TypeError, not ValueError ──
#
# Reference:
#
#     elif source_path_format == PathFormat.POSIX:
#         if not isinstance(source_path, PurePosixPath):
#             raise ValueError(
#                 "Path mapping rule source_path_format does not match source_path type"
#             )
#
# The binding raises ``TypeError`` with a different message:
#
#     "source_path must be str or PurePosixPath for POSIX format,
#      got PureWindowsPath"
#
# The exception class identity matters because callers porting from v0
# write ``except ValueError`` blocks. Fix path:
# ``rust-bindings/src/expr/path_mapping.rs::extract_path_arg`` should
# raise ``PyValueError::new_err`` with the reference's exact message
# when the supplied pathlib type doesn't match the format.
#
# Cross-reference: report Recommendation #3.


@pytest.mark.xfail(
    reason="Binding raises TypeError; reference raises ValueError on path format mismatch",
    raises=TypeError,
    strict=True,
)
def test_path_mapping_rule_format_mismatch_raises_value_error() -> None:
    with pytest.raises(ValueError, match="source_path_format does not match source_path type"):
        PathMappingRule(
            source_path_format=PathFormat.POSIX,
            source_path=PureWindowsPath("C:\\foo"),
            destination_path="/dst",
        )


# ── SymbolTable['Key'] = value when Key is already a subtable ──
#
# Reference (``_set_path`` with a single-component key):
#
#     if len(parts) == 1:
#         self._table[key] = self._convert_value(value)
#
# Unconditionally overwrites, so ``st['Param'] = 99`` is allowed even
# when ``Param`` previously held a subtable.
#
# The binding's underlying Rust ``SymbolTable::set`` rejects this:
#
#     "Cannot set 'Param': 'Param' is not a table"
#
# This is consequential for callers that rebuild a symbol table by
# overwriting top-level namespaces. Fix path: relax the
# ``set_value`` guard in the underlying crate (or shadow the
# behaviour in ``rust-bindings/src/expr/symbol_table.rs::__setitem__``
# by deleting any pre-existing subtable entry before calling
# ``set``) so a single-component key always overwrites.
#
# Cross-reference: report Recommendation #4.


@pytest.mark.xfail(
    reason="Binding rejects overwriting a subtable with a value via single-component __setitem__",
    raises=ValueError,
    strict=True,
)
def test_symbol_table_setitem_overwrites_subtable() -> None:
    st = SymbolTable({"Param.Frame": 42})
    # Reference: this just replaces the 'Param' subtable with the int.
    st["Param"] = 99
    # After the overwrite, 'Param' is a leaf int value.
    assert st["Param"].item() == 99
    # And the previously-nested 'Param.Frame' is no longer reachable.
    assert "Param.Frame" not in st


# ── Integer overflow message leaks the inner OverflowError text ──
#
# (See test_expr_value_int_overflow_message_matches_reference above for
# the i64::MAX side; the same drift applies symmetrically below
# i64::MIN.) The reference's ``ExprValue._create`` raises
# ``ExpressionError("Integer overflow: result is outside the 64-bit
# signed range")`` for *any* integer outside the i64 window. The
# binding's ``py_to_expr_value`` produces the same drifted phrasing
# regardless of sign, so a separate strict xfail pins the negative
# side explicitly — without it, a partial fix that only addresses
# i64::MAX would silently start xpassing the existing positive-side
# test and miss the negative-side regression.
#
# Cross-reference: report Recommendation #2.


@pytest.mark.xfail(
    reason="Negative i64 overflow shares the same message-leak drift as i64::MAX",
    strict=True,
)
def test_expr_value_negative_int_overflow_message_matches_reference() -> None:
    with pytest.raises(ExpressionError) as excinfo:
        ExprValue(-(2**63) - 1)  # one below i64::MIN
    assert str(excinfo.value) == "Integer overflow: result is outside the 64-bit signed range"


# ── ExpressionError raised from Rust does not populate `expr` /
#    `col_offset` instance fields ──
#
# When ``evaluate_expression`` raises an error from Rust, the message
# string already contains the source line and caret indicator (the
# Rust crate does the formatting). The binding wraps that string
# verbatim into a Python ``ExpressionError`` via
# ``PyExpressionError::new_err(e.to_string())``. The Python-side
# ``__init__`` therefore stores the multi-line string in
# ``_base_message`` and leaves ``self.expr`` / ``self.col_offset`` /
# ``self.lineno`` set to ``None``.
#
# Reference behavior is the opposite: ``Evaluator`` always raises
# ``ExpressionError(message, expr=..., node=..., lineno=..., col_offset=...)``
# with structured location info, and ``_format_message`` produces
# the multi-line render lazily from those fields. Callers that
# inspect ``e.expr``, ``e.col_offset``, or ``e.lineno`` after
# catching an error from ``evaluate_expression`` get ``None`` on
# the binding — so structured-diagnostic consumers regress silently.
#
# Fix path: ``rust-bindings/src/expr/errors.rs::expr_err_to_py``
# should construct ``PyExpressionError`` via the keyword
# constructor (``PyExpressionError::new_err((message, kwargs))`` or
# similar) populating the source string, line, and column from the
# ``openjd_expr::error::ExpressionError`` struct, instead of
# stuffing the formatted display string into a positional argument.
#
# Cross-reference: report Recommendation #5.


@pytest.mark.xfail(
    reason=(
        "Rust-originated ExpressionError loses structured location info — "
        "self.expr/lineno/col_offset stay None after evaluate_expression failure"
    ),
    strict=True,
)
def test_expression_error_carries_structured_location() -> None:
    from openjd.expr import evaluate_expression

    with pytest.raises(ExpressionError) as excinfo:
        evaluate_expression("Param.X")
    err = excinfo.value
    # Reference: the evaluator raised
    #   ExpressionError("Undefined variable: 'Param.X'.",
    #                   expr="Param.X", lineno=1, col_offset=0)
    # so all three fields are populated and the *_base_message* is the
    # single-line headline (no source/caret embedded yet).
    assert err.expr == "Param.X"
    assert err.col_offset == 0


# ── ExpressionError._base_message includes the formatted source/caret
#    block for Rust-originated errors, breaking
#    `message_with_expr_prefix` ──
#
# ``message_with_expr_prefix(prefix)`` is documented to produce a
# rendering with the prefix inserted before the expression source
# line and the caret column shifted accordingly. It works against
# Python-constructed ``ExpressionError`` instances because
# ``_base_message`` is the headline ("bad value") and the source
# line is reconstructed from ``self.expr`` + ``self.col_offset``.
#
# When the error comes from Rust, ``_base_message`` already contains
# the formatted "headline\n  source\n  ~~~~^" block — and ``expr`` /
# ``col_offset`` are ``None`` (see previous test). So
# ``message_with_expr_prefix`` falls back to ``str(self)`` (because
# ``expr is None``), which still includes the *original* caret line
# but no prefixed line. After ``with_context(...)`` attaches an
# expression string, the rendering concatenates the embedded
# source-and-caret block with a *prefixed* line that has no caret of
# its own:
#
#     "Undefined variable: 'Param.X'."
#     "  Param.X"
#     "  ~~~~~~^"
#     "  x = outer expression source"   ← prefixed line, no caret
#
# That's broken: the caret is anchored at the unprefixed source, the
# prefixed line is bare, and the headline is followed by *two*
# expression renderings.
#
# Fix path: same as Recommendation #5 — populate ``expr``,
# ``lineno``, ``col_offset`` from the Rust-side error so
# ``_base_message`` is the headline only and
# ``message_with_expr_prefix`` can re-render cleanly.
#
# Cross-reference: report Recommendation #5.


@pytest.mark.xfail(
    reason=(
        "Rust-originated ExpressionError._base_message embeds source/caret, "
        "so message_with_expr_prefix double-renders or omits the caret"
    ),
    strict=True,
)
def test_message_with_expr_prefix_renders_cleanly_for_rust_error() -> None:
    from openjd.expr import evaluate_expression

    try:
        evaluate_expression("Param.X")
    except ExpressionError as e:
        rendered = e.with_context("Param.X").message_with_expr_prefix("x = ")
    # Reference shape: headline + "  x = Param.X" + "  " + " " * 6 + "^".
    expected = "Undefined variable: 'Param.X'.\n  x = Param.X\n        ^"
    assert rendered == expected
