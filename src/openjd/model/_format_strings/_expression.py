# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import numbers
from typing import Any, Optional, Union

from .._errors import ExpressionError
from .._symbol_table import SymbolTable
from ._nodes import Node
from ._parser import parse_format_string_expr
from .._types import ModelParsingContextInterface


class InterpolationExpression:
    expr: str
    _expression_tree: Node

    def __init__(self, expr: str, *, context: ModelParsingContextInterface) -> None:
        """Constructor.

        Raises:
            ExpressionError: The provided expression cannot be parsed.
            TokenError: The provided expression contains nonvalid or unexpected tokens.

        Args:
            expr (str): The expression
        """
        self.expr = expr

        # Raises: ExpressionError, TokenError
        self._expresion_tree = parse_format_string_expr(expr, context=context)

    def validate_symbol_refs(self, *, symbols: set[str], symbol_types: Any = None) -> None:
        """Check whether this expression can be evaluated correctly given a set of symbol names.

        Args:
            symbols (set[str]): The names of symbols visible to this expression.
            symbol_types: Optional mapping of symbol name -> EXPR type string,
                enabling type-aware validation when available.

        Raises:
            ValueError: If the expression cannot be evaluated with the given symbol names
        """
        self._expresion_tree.validate_symbol_refs(symbols=symbols, symbol_types=symbol_types)

    @property
    def called_functions(self) -> set:
        """Names of functions invoked by this expression (empty for the legacy
        name-only parser)."""
        return getattr(self._expresion_tree, "called_functions", set())

    @property
    def accessed_symbols(self) -> set:
        """Free symbol references in this expression in full dotted spelling
        (empty for the legacy name-only parser, which exposes no such set)."""
        return getattr(self._expresion_tree, "accessed_symbols", set())

    def evaluate(
        self, *, symtab: SymbolTable, path_format: Optional[Any] = None
    ) -> Union[numbers.Real, str, Any]:
        """Evaluate the expression given a SymbolTable.

        Args:
            symtab (SymbolTable): A symbol table containing values to use in the evaluation.
            path_format (Any): Optional EXPR PathFormat for PATH-typed values.

        Raises:
            ExpressionError: If the expression could not be evaluated.

        Returns:
            The resulting value. For legacy (non-EXPR) expressions this is a
            ``numbers.Real`` or ``str``; EXPR expressions may also yield
            ``bool``, ``list``, or ``None``.
        """
        try:
            result = self._expresion_tree.evaluate(symtab=symtab, path_format=path_format)
        except ValueError as exc:
            raise ExpressionError(f"Expression failed validation: {str(exc)}")

        # EXPR-backed nodes may legitimately return non-scalar values; the
        # legacy name path is still restricted to Real/str to preserve its
        # exact behavior.
        if getattr(self._expresion_tree, "allows_nonscalar", False):
            return result
        if isinstance(result, (numbers.Real, str)):
            return result

        raise ExpressionError(f"Nonvalid result type: {result} of type {type(result)}")

    def evaluate_value(self, *, symtab: SymbolTable, path_format: Optional[Any] = None) -> Any:
        """Evaluate the expression, preferring the engine's typed value form.

        For EXPR-backed expressions this returns the engine ``ExprValue``,
        which keeps the result's EXPR type (path/int/float/list/...) and its
        string-rendering fidelity when re-seeded into a symbol table — the
        session runtime's ``let`` bindings (RFC 0007) rely on this. Legacy
        (non-EXPR) expressions return their native value, identical to
        :meth:`evaluate`.

        Raises:
            ExpressionError: If the expression could not be evaluated.
        """
        evaluate_value = getattr(self._expresion_tree, "evaluate_value", None)
        if evaluate_value is None:
            return self.evaluate(symtab=symtab, path_format=path_format)
        try:
            return evaluate_value(symtab=symtab, path_format=path_format)
        except ValueError as exc:
            raise ExpressionError(f"Expression failed validation: {str(exc)}")

    def evaluate_to_str(self, *, symtab: SymbolTable, path_format: Optional[Any] = None) -> str:
        """Evaluate the expression and coerce the result to the string form that
        is substituted into the surrounding format string.

        For EXPR expressions this uses the engine's spec-defined string coercion
        (RFC 0005) rather than Python's ``str()``, so booleans, null, and lists
        render per the specification rather than as Python reprs.

        Args:
            symtab (SymbolTable): A symbol table containing values to use in the evaluation.
            path_format (Any): Optional EXPR PathFormat for PATH-typed values.

        Raises:
            ExpressionError: If the expression could not be evaluated.
        """
        try:
            return self._expresion_tree.evaluate_to_str(symtab=symtab, path_format=path_format)
        except ValueError as exc:
            raise ExpressionError(f"Expression failed validation: {str(exc)}")
