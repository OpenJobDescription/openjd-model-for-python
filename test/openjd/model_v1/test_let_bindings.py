# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for ``openjd.model._v1.evaluate_let_bindings``.

``evaluate_let_bindings`` is the entry point sessions use to resolve
step-level ``let:`` bindings at runtime against a symbol table. The
function is implemented in the ``openjd-model`` Rust crate (it produces
``ModelError`` and is consumed by the model crate's
``create_job/instantiate.rs`` runtime machinery), so the Python surface
lives under ``openjd.model._v1`` alongside ``create_job`` and
``preprocess_job_parameters`` rather than under ``openjd.expr``.

Coverage anchored to the report's recommendation #6:
* Single binding (the spec example).
* Chained bindings where a later binding references an earlier one.
* ``ExpressionError`` on syntax error inside a binding.
* ``ExpressionError`` on the missing-``=`` form.
* The result ``SymbolTable`` containing both the original input
  symbols and the bound names.
"""

import pytest

from openjd.expr import ExpressionError, ExprProfile, SymbolTable
from openjd.model._v1 import CallerLimits, evaluate_let_bindings


class TestEvaluateLetBindings:
    """Resolve let bindings against a symbol table.

    Returned ``SymbolTable`` carries both the input symbols and the
    bound names. ``ExpressionError`` is raised on any per-binding
    evaluation or parse failure with a message that names the
    offending binding text.
    """

    def test_single_binding_spec_example(self) -> None:
        """The exact example from
        ``specs/python-model-interface.md::evaluate_let_bindings``."""
        st = SymbolTable({"Param.Start": 1, "Param.Count": 10})
        result = evaluate_let_bindings(["end = Param.Start + Param.Count - 1"], st)
        assert result["end"].item() == 10

    def test_chained_bindings_reference_earlier_names(self) -> None:
        """Each binding sees the names introduced by earlier bindings
        in the same call. Order is left-to-right; the result is the
        combined symbol table."""
        st = SymbolTable({"Param.X": 10})
        result = evaluate_let_bindings(
            [
                "a = Param.X + 1",
                "b = a * 2",
                "c = a + b",
            ],
            st,
        )
        assert result["a"].item() == 11
        assert result["b"].item() == 22
        assert result["c"].item() == 33

    def test_input_symbols_preserved_in_result(self) -> None:
        """The result ``SymbolTable`` contains both the original input
        symbols and the new bound names. Callers walk the result
        without needing to merge the input table back in."""
        st = SymbolTable({"Param.Frame": 42, "Param.Name": "render"})
        result = evaluate_let_bindings(["doubled = Param.Frame * 2"], st)
        assert result["Param.Frame"].item() == 42
        assert result["Param.Name"].item() == "render"
        assert result["doubled"].item() == 84

    def test_empty_bindings_list_returns_input_symbols(self) -> None:
        """An empty bindings list is a no-op — the result mirrors the
        input symbol table."""
        st = SymbolTable({"Param.X": 10, "Param.Y": "hello"})
        result = evaluate_let_bindings([], st)
        assert result["Param.X"].item() == 10
        assert result["Param.Y"].item() == "hello"

    def test_missing_equals_raises_expression_error(self) -> None:
        """Per AGENTS.md "Test Quality Standard": assert exception
        class **and** the full message body. The diagnostic names
        the offending binding text verbatim."""
        st = SymbolTable({"Param.X": 10})
        with pytest.raises(ExpressionError) as excinfo:
            evaluate_let_bindings(["bad"], st)
        assert str(excinfo.value) == "Missing '=' in let binding: bad"

    def test_missing_equals_blank_string_raises_expression_error(self) -> None:
        """A blank-string binding still surfaces the canonical
        missing-``=`` error rather than failing silently."""
        st = SymbolTable({})
        with pytest.raises(ExpressionError) as excinfo:
            evaluate_let_bindings([""], st)
        assert str(excinfo.value) == "Missing '=' in let binding: "

    def test_syntax_error_in_rhs_raises_expression_error(self) -> None:
        """A truncated / invalid expression on the right-hand side
        surfaces an ``ExpressionError`` whose message names the
        whole binding (the parser's caret-and-source rendering is
        appended after the binding text)."""
        st = SymbolTable({"Param.X": 10})
        with pytest.raises(ExpressionError) as excinfo:
            evaluate_let_bindings(["bad = 1 +"], st)
        # The message has the binding text in the prefix and the
        # parser's source-with-caret rendering below; pin the
        # critical substrings rather than the multi-line whole, but
        # use ``in`` checks rather than ``match=`` regex (cleaner
        # against multi-line content with caret characters).
        msg = str(excinfo.value)
        assert msg.startswith("Error evaluating let binding 'bad': Syntax error")
        assert "bad = 1 +" in msg  # the source line is echoed

    def test_undefined_symbol_in_binding_raises(self) -> None:
        """Referencing a symbol that doesn't exist in the input table
        raises ``ExpressionError`` with the offending binding name."""
        st = SymbolTable({"Param.X": 10})
        with pytest.raises(ExpressionError) as excinfo:
            evaluate_let_bindings(["a = NotDefined.Y + 1"], st)
        msg = str(excinfo.value)
        assert msg.startswith("Error evaluating let binding 'a':")
        assert "Undefined variable: 'NotDefined.Y'" in msg

    def test_chained_undefined_in_later_binding_raises(self) -> None:
        """A later binding referencing an undefined name (when the
        earlier one didn't introduce it) raises with that binding's
        name, not the earlier one's."""
        st = SymbolTable({"Param.X": 10})
        with pytest.raises(ExpressionError) as excinfo:
            evaluate_let_bindings(
                [
                    "a = Param.X + 1",
                    "b = NotDefined.Y * 2",
                ],
                st,
            )
        # Diagnostic identifies the *failing* binding ('b'), not 'a'.
        msg = str(excinfo.value)
        assert msg.startswith("Error evaluating let binding 'b':")
        assert "Undefined variable: 'NotDefined.Y'" in msg

    def test_with_explicit_profile(self) -> None:
        """``profile=`` is the optional third axis. Passing
        ``ExprProfile.current()`` is equivalent to omitting it; pin
        the contract so callers porting from sessions runtime code
        (which always passes a profile) see the same shape."""
        st = SymbolTable({"Param.X": 10})
        result = evaluate_let_bindings(["y = Param.X + 5"], st, profile=ExprProfile.current())
        assert result["y"].item() == 15


class TestEvaluateLetBindingsCallerLimits:
    """``caller_limits`` is the fourth axis, added with openjd-model 0.9.0
    (openjd-rs#399); 0.8.0's ``evaluate_let_bindings`` took no budgets at all.

    A binding evaluates a parsed expression directly rather than resolving a format
    string, so without this argument a caller that lowered
    ``max_eval_memory_bytes`` / ``max_eval_operations`` for template validation and
    job creation would leave let bindings evaluating on the spec-recommended
    defaults. The remaining ``CallerLimits`` fields have no meaning here.
    """

    def test_operation_budget_is_applied(self) -> None:
        st = SymbolTable({"Param.X": 10})
        with pytest.raises(ExpressionError) as excinfo:
            evaluate_let_bindings(
                ["a = Param.X + 1"], st, caller_limits=CallerLimits(max_eval_operations=1)
            )
        message = str(excinfo.value)
        assert message.startswith("Error evaluating let binding 'a':")
        assert "operation count (2) exceeded limit (1)" in message

    def test_memory_budget_is_applied(self) -> None:
        st = SymbolTable({"Param.X": 10})
        with pytest.raises(ExpressionError) as excinfo:
            evaluate_let_bindings(
                ["a = 'z' * 10000"], st, caller_limits=CallerLimits(max_eval_memory_bytes=16)
            )
        assert "memory usage (72 bytes) exceeded limit (16 bytes)" in str(excinfo.value)

    def test_unrelated_limits_do_not_restrict_a_binding(self) -> None:
        """Negative control: a ``CallerLimits`` carrying only document-shape caps
        leaves the binding on the spec-recommended defaults, and a binding that
        exceeds neither default is evaluated."""
        st = SymbolTable({"Param.X": 10})
        result = evaluate_let_bindings(
            ["a = 'z' * 10000"],
            st,
            caller_limits=CallerLimits(max_step_count=1, max_template_size=1),
        )
        assert len(result["a"].item()) == 10000

    def test_omitting_the_argument_uses_the_defaults(self) -> None:
        """Negative control for the same expression with no limits at all — the only
        behaviour available before the bump."""
        result = evaluate_let_bindings(["a = 'z' * 10000"], SymbolTable({}))
        assert len(result["a"].item()) == 10000
