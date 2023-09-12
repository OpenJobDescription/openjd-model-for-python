# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import numbers
from typing import Union

from .._errors import ExpressionError
from .._symbol_table import SymbolTable
from ._nodes import Node
from ._parser import Parser


class InterpolationExpression:
    expr: str
    _expression_tree: Node

    def __init__(self, expr: str) -> None:
        """Constructor.

        Raises:
            ExpressionError: The provided expression cannot be parsed.
            TokenError: The provided expression contains nonvalid or unexpected tokens.

        Args:
            expr (str): The expression
        """
        self.expr = expr
        parser = Parser()

        # Raises: ExpressionError, TokenError
        self._expresion_tree = parser.parse(expr)

    def validate_symbol_refs(self, *, symbols: set[str]) -> None:
        """Check whether this expression can be evaluated correctly given a set of symbol names.

        Args:
            symbols (set[str]): The names of symbols visible to this expression.

        Raises:
            ValueError: If the expression cannot be evaluated with the given symbol names
        """
        self._expresion_tree.validate_symbol_refs(symbols=symbols)

    def evaluate(self, *, symtab: SymbolTable) -> Union[numbers.Real, str]:
        """Evaluate the expression given a SymbolTable.

        Args:
            symtab (SymbolTable): A symbol table containing values to use in the evaluation.

        Raises:
            ExpressionError: If the expression could not be evaluated.

        Returns:
            Union[numbers.Real, str]: Resulting value.
        """
        try:
            result = self._expresion_tree.evaluate(symtab=symtab)
        except ValueError as exc:
            raise ExpressionError(f"Expression failed validation: {str(exc)}")

        if isinstance(result, (numbers.Real, str)):
            return result

        raise ExpressionError(f"Nonvalid result type: {result} of type {type(result)}")
