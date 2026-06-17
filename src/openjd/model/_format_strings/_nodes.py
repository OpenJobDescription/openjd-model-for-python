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
    def validate_symbol_refs(self, *, symbols: set[str]) -> None:  # pragma: no cover
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

    @abstractmethod
    def __repr__(self) -> str:  # pragma: no cover
        """String representation of the node for printing."""
        pass


# A heuristic. Any closest match with an edit distance greater than this will
# not be returned as a closest match for error reporting purposes.
MAX_MATCH_DISTANCE_THRESHOLD = 5


@dataclass
class FullNameNode(Node):
    """Expression tree node representing a fully qualified identifier name.
    e.g. Foo.Bar.Baz or Foo
    """

    name: str

    def validate_symbol_refs(self, *, symbols: set[str]) -> None:
        if self.name not in symbols:
            msg = f"Variable {self.name} does not exist at this location."
            distance, closest_matches = closest(symbols, self.name)
            if distance < MAX_MATCH_DISTANCE_THRESHOLD:
                if len(closest_matches) == 1:
                    msg += f" Did you mean: {''.join(closest_matches)}"
                elif len(closest_matches) > 1:
                    msg += f" Did you mean one of: {', '.join(sorted(closest_matches))}"
            raise ValueError(msg)

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

    def validate_symbol_refs(self, *, symbols: set[str]) -> None:
        # accessed_symbols are the free variable references in full dotted
        # spelling (e.g. "Param.X"); local let-bound names are excluded by the
        # engine. Compare against the set of symbols visible at this location.
        missing = set(self._parsed.accessed_symbols) - symbols
        if missing:
            from ._edit_distance import closest

            name = sorted(missing)[0]
            msg = f"Variable {name} does not exist at this location."
            distance, closest_matches = closest(symbols, name)
            if distance < MAX_MATCH_DISTANCE_THRESHOLD:
                if len(closest_matches) == 1:
                    msg += f" Did you mean: {''.join(closest_matches)}"
                elif len(closest_matches) > 1:
                    msg += f" Did you mean one of: {', '.join(sorted(closest_matches))}"
            raise ValueError(msg)

    def evaluate(self, *, symtab: SymbolTable, path_format: Any = None) -> Any:
        from ._expr_support import (
            ExprProfile,
            map_eval_error,
            symtab_to_expr_values,
        )

        values = symtab_to_expr_values(
            symtab, types=getattr(symtab, "expr_types", None), path_format=path_format
        )
        try:
            result = self._parsed.evaluate(
                values=values, profile=ExprProfile.current(), path_format=path_format
            )
        except Exception as exc:  # noqa: BLE001 - boundary; re-raise as model error
            raise map_eval_error(exc)
        return result.item()

    def __repr__(self):
        return f"Expr({self.expr})"
