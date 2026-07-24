# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from .._symbol_table import SymbolTable
from ._edit_distance import closest


class Node(ABC):
    """
    Base expression tree node class.
    """

    @abstractmethod
    def validate_symbol_refs(
        self, *, symbols: set[str], symbol_types: Any = None
    ) -> None:  # pragma: no cover
        """Verifies that the expression rooted at this node is valid
        given the definitions of symbols in a symbol table.

        For example, an expression is not valid if it references
        a symbol that does not exist in the symbol table.

        Raises:
            ValueError: If the expression is not valid. The given error contains
               context and information on the specifics of the error.

        Args:
            symbols (set[str]): The names of symbols visible to this expression.
        """
        pass

    # Whether evaluate() may return a non-scalar (list/bool/path) value.
    # The legacy FullNameNode only ever yields str/Real; EXPR can yield more.
    allows_nonscalar: bool = False

    @abstractmethod
    def evaluate(self, *, symtab: SymbolTable, path_format: Any = None) -> Any:  # pragma: no cover
        """Evaluate the expression rooted at this node given definitions
        of symbols in a symbol table.

        Raises:
            ValueError: If the expression is not valid. The given error contains
               context and information on the specifics of the error.

        Args:
            symtab (SymbolTable): Symbol definitions.
            path_format (Any): Optional EXPR PathFormat used for PATH-typed
                values; ignored by nodes that do not evaluate expressions.

        Returns:
            Any: Value of the expression.
        """
        pass

    def evaluate_to_str(self, *, symtab: SymbolTable, path_format: Any = None) -> str:
        """Evaluate the expression and coerce the result to its format-string
        string form (the value substituted into the surrounding string).

        The default implementation applies Python ``str()`` to the evaluated
        value, which is correct for the legacy scalar (``str``/``Real``) nodes.
        EXPR-backed nodes override this to use the engine's own spec-defined
        coercion (RFC 0005), so e.g. ``true``/``false``/``null`` and lists
        render per the specification rather than as Python reprs.

        A ``None`` value interpolates as the empty string, matching the EXPR
        engine's null rendering (RFC 0005) — relevant for nullable injected
        symbols such as ``WrappedAction.Cancelation.NotifyPeriodInSeconds``
        (RFC 0008 follow-up), which is ``None`` when no notify period
        applies.
        """
        value = self.evaluate(symtab=symtab, path_format=path_format)
        if value is None:
            return ""
        return str(value)

    @abstractmethod
    def __repr__(self) -> str:  # pragma: no cover
        """String representation of the node for printing."""
        pass


# A heuristic. Any closest match with an edit distance greater than this will
# not be returned as a closest match for error reporting purposes.
MAX_MATCH_DISTANCE_THRESHOLD = 5


def _missing_symbol_error(name: str, symbols: set[str]) -> ValueError:
    """Build the "Variable ... does not exist" error for an unresolved symbol,
    appending an edit-distance "Did you mean ...?" hint when a close match
    exists. Shared by the legacy and EXPR symbol-reference checks so the
    diagnostic stays identical across both."""
    msg = f"Variable {name} does not exist at this location."
    distance, closest_matches = closest(symbols, name)
    if distance < MAX_MATCH_DISTANCE_THRESHOLD:
        if len(closest_matches) == 1:
            msg += f" Did you mean: {''.join(closest_matches)}"
        elif len(closest_matches) > 1:
            msg += f" Did you mean one of: {', '.join(sorted(closest_matches))}"
    return ValueError(msg)


@dataclass
class FullNameNode(Node):
    """Expression tree node representing a fully qualified identifier name.
    e.g. Foo.Bar.Baz or Foo
    """

    name: str

    def validate_symbol_refs(self, *, symbols: set[str], symbol_types: Any = None) -> None:
        if self.name not in symbols:
            raise _missing_symbol_error(self.name, symbols)

    def evaluate(self, *, symtab: SymbolTable, path_format: Any = None) -> Any:
        if self.name not in symtab:
            raise ValueError(f"{self.name} has no value")
        return symtab[self.name]

    def __repr__(self):
        return f"FullName({self.name})"


class ExprNode(Node):
    """Expression tree node backed by the Rust ``openjd-expr`` engine.

    Used in place of :class:`FullNameNode` when a template declares the
    ``EXPR`` extension. Wraps a Rust ``ParsedExpression`` and satisfies the
    same ``Node`` interface so the rest of the model is unaware of which
    backend answered.
    """

    allows_nonscalar = True

    def __init__(self, expr: str) -> None:
        # Import here to keep the Rust expr surface off the non-EXPR path.
        from ._expr_support import parse_expr_or_raise, static_validate_symbol_free

        self.expr = expr
        # Raises: model ExpressionError on parse failure.
        self._parsed = parse_expr_or_raise(expr)
        # Statically validate expressions with no free symbol references so
        # that literal/semantic errors (overflow, division by zero, unknown
        # function, type mismatch, ...) are caught at `check` time rather than
        # only at evaluation. Symbol-referencing expressions are validated once
        # their types are known (RFC 0007 parameter types).
        if not self._parsed.accessed_symbols:
            static_validate_symbol_free(expr)

    @property
    def called_functions(self) -> set:
        """Names of functions invoked by this expression."""
        return set(self._parsed.called_functions)

    @property
    def accessed_symbols(self) -> set:
        """Free symbol references in this expression, in full dotted spelling
        (e.g. ``"Param.X"``). Local ``let``/comprehension-bound names are
        excluded by the engine."""
        return set(self._parsed.accessed_symbols)

    def validate_symbol_refs(self, *, symbols: set[str], symbol_types: Any = None) -> None:
        accessed = set(self._parsed.accessed_symbols)

        # Typed validation: if every accessed symbol resolves to a defined
        # symbol prefix whose EXPR type is known (e.g. job parameters), validate
        # the whole expression against those types. This catches type mismatches
        # and resolves method/property access (e.g. Param.File.name on a PATH).
        # Only attempted when ALL accessed prefixes are typed-known, so an
        # unknown-typed symbol (e.g. a `let` name) safely falls back to the
        # name-only check below rather than risking a wrong-type rejection.
        if symbol_types and accessed:
            from ._expr_support import (
                longest_defined_prefix,
                validate_typed_expression,
            )

            prefix_types: dict = {}
            fully_typed = True
            for name in accessed:
                prefix = longest_defined_prefix(name, symbols)
                if prefix is None or prefix not in symbol_types:
                    fully_typed = False
                    break
                prefix_types[prefix] = symbol_types[prefix]
            if fully_typed:
                # Raises model ExpressionError on a type/method error.
                validate_typed_expression(self._parsed, typed_symbols=prefix_types)
                self._check_comprehension_shadowing(symbols)
                return

        # accessed_symbols are the free variable references in full dotted
        # spelling (e.g. "Param.X"); local let-bound names are excluded by the
        # engine. Compare against the set of symbols visible at this location.
        # A reference is defined when any dotted prefix of it is a defined
        # symbol: the remaining segments are property/method access on that
        # symbol's value (e.g. `work_dir.name` on a `let`-bound path), whose
        # type-correctness is checked by the typed validation above when the
        # types are known, and at evaluation time otherwise — mirroring the
        # Rust engine's treatment of unknown-typed symbols.
        from ._expr_support import longest_defined_prefix

        missing = {name for name in accessed if longest_defined_prefix(name, symbols) is None}
        if missing:
            raise _missing_symbol_error(sorted(missing)[0], symbols)
        self._check_comprehension_shadowing(symbols)

    def _check_comprehension_shadowing(self, symbols: set) -> None:
        # Comprehension/local-binding variables may not shadow a variable that
        # is in scope (RFC 0007 §3.6). `local_bindings` are the names bound by
        # comprehensions/let-expressions inside this expression.
        shadowed = set(self._parsed.local_bindings) & symbols
        if shadowed:
            raise ValueError(
                f"Variable {sorted(shadowed)[0]!r} bound by a comprehension shadows "
                "a variable that already exists at this location."
            )

    def _evaluate_raw(self, *, symtab: SymbolTable, path_format: Any = None) -> Any:
        """Evaluate the expression and return the engine's ``ExprValue``.

        Shared by :meth:`evaluate` (which unwraps to the native Python value)
        and :meth:`evaluate_to_str` (which uses the engine's spec-defined string
        coercion). Re-raises engine errors as the model's ``ExpressionError``.
        """
        from ._expr_support import (
            map_eval_error,
            profile_for_symtab,
            symtab_to_expr_values,
        )

        # Both the engine symbol table and the evaluation profile (which
        # carries the session's host-context path mapping rules, if any) are
        # cached on the symbol table per mutation version — see
        # _expr_support for why (per-expression Rust-boundary rebuilds).
        values = symtab_to_expr_values(
            symtab, types=symtab.expr_types or None, path_format=path_format
        )
        profile = profile_for_symtab(symtab)
        try:
            return self._parsed.evaluate(values=values, profile=profile, path_format=path_format)
        except Exception as exc:  # noqa: BLE001 - boundary; re-raise as model error
            raise map_eval_error(exc)

    def evaluate(self, *, symtab: SymbolTable, path_format: Any = None) -> Any:
        return self._evaluate_raw(symtab=symtab, path_format=path_format).item()

    def evaluate_value(self, *, symtab: SymbolTable, path_format: Any = None) -> Any:
        """Evaluate and return the engine's ``ExprValue`` (not unwrapped to a
        native Python value).

        Callers that re-seed the result into a symbol table (e.g. the session
        runtime's ``let`` bindings, RFC 0007) should use this form: the typed
        symbol-table builder passes an ``ExprValue`` through unchanged, so the
        bound value keeps its EXPR type (a path stays a path for property
        access) and its rendering fidelity (a float's declared trailing zeros
        are preserved), matching the Rust runtime's natively typed symbol
        table.
        """
        return self._evaluate_raw(symtab=symtab, path_format=path_format)

    def evaluate_to_str(self, *, symtab: SymbolTable, path_format: Any = None) -> str:
        # ``str(ExprValue)`` applies the engine's RFC 0005 format-string
        # coercion (e.g. ``true``/``false``, double-quoted list items, preserved
        # Decimal trailing zeros) rather than Python's ``str()`` of the native
        # value, which would emit Python reprs (``True``/``None``/``['a', 'b']``).
        # A null result interpolates as the empty string, matching the Rust
        # engine's FormatString resolution (RFC 0005).
        value = self._evaluate_raw(symtab=symtab, path_format=path_format)
        if getattr(value, "is_null", False):
            return ""
        return str(value)

    def __repr__(self):
        return f"Expr({self.expr})"
