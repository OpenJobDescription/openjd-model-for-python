# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Shared evaluation of EXPR ``let`` bindings (RFC 0007 §3.6).

One implementation of the "parse ``name = expression``, skip malformed,
evaluate, seed the symbol table" loop, used by:

- the model's job instantiation (a StepTemplate's step-level bindings,
  evaluated at create time so the step's parameter space and host
  requirements resolve against them), and
- the ``openjd-sessions`` runtime (script-level bindings evaluated by the
  runners, and step-level bindings re-applied when entering a step's
  environments).

Keeping it here single-sources the "malformed bindings are rejected by the
``let`` field validator at decode time; skip defensively at evaluation time"
policy, and the RHS parse memoization.
"""

from functools import lru_cache
from typing import Any, Iterable

from ._symbol_table import SymbolTable

__all__ = ["evaluate_let_bindings"]


@lru_cache(maxsize=1024)
def _parse_rhs(rhs: str) -> Any:
    """Parse a binding's RHS as a standalone EXPR expression.

    Memoized: a template's binding strings are invariant, but bindings are
    re-applied on every environment enter/exit and every task run, so caching
    the parse avoids re-parsing the same expression through the engine per
    application. The returned node holds no symbol-table state —
    ``evaluate_value`` takes the symbol table per call — so it is safe to
    share across evaluations. Parse errors propagate and are not cached.
    """
    # Deferred import to keep the Rust expr surface off the non-EXPR path;
    # `let` fields only exist when the EXPR extension is declared.
    from ._format_strings._nodes import ExprNode

    return ExprNode(rhs)


def evaluate_let_bindings(*, symtab: SymbolTable, let_bindings: Iterable[str]) -> None:
    """Evaluate EXPR ``let`` bindings in order, seeding each into ``symtab``.

    ``let_bindings`` is an ordered list of ``"name = expression"`` strings.
    Each RHS is evaluated against the symbol table built so far (so later
    bindings can reference earlier ones), and the engine's typed result is
    stored under the bound name — a let-bound path stays a path for property
    access, and float rendering fidelity is preserved — matching the Rust
    runtime's natively typed symbol table.

    Malformed bindings (missing ``=``, empty name or expression) are skipped:
    the ``let`` field validator rejects them at decode time, so evaluation is
    defensive here.

    Not to be confused with ``openjd.model._v1.evaluate_let_bindings`` (the
    Rust-backed v1 surface), which has a different signature and returns a
    new symbol table; this v0 helper mutates ``symtab`` in place.

    Raises:
        ValueError: if a binding's expression fails to parse or evaluate;
            the message names the binding.
    """
    for binding in let_bindings:
        name, sep, rhs = binding.partition("=")
        name = name.strip()
        rhs = rhs.strip()
        if not sep or not name or not rhs:
            # Malformed bindings are rejected by the `let` validator.
            continue
        try:
            # evaluate_value keeps the engine's typed value (paths stay
            # paths, float rendering fidelity is preserved) when the binding
            # is later referenced.
            symtab[name] = _parse_rhs(rhs).evaluate_value(symtab=symtab)
        except ValueError as exc:
            raise ValueError(f"let binding {name!r}: {exc}")
