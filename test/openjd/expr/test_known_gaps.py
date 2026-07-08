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

import pytest

from openjd.expr import (
    ExpressionError,
    SymbolTable,
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
