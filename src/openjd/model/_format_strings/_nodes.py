# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from .._symbol_table import SymbolTable
from .._errors import ValidationError


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

    @abstractmethod
    def validate(self, *, symtab: SymbolTable) -> None:  # pragma: no cover
        """Verifies that the expression rooted at this node is valid
        given the definitions of symbols in a symbol table.

        For example, an expression is not valid if it references
        a symbol that does not exist in the symbol table.

        Raises:
            ValidationError: If the expression is not valid. The given error contains
               context and information on the specifics of the error.

        Args:
            symtab (SymbolTable): Symbol definitions to validate against.

        Note: The symtab does need to have placeholder values for each symbol
        that are of the appropriate type. For example, a placeholder for a
        number-type symbol might be the integer value 0.
        """
        pass

    @abstractmethod
    def evaluate(self, *, symtab: SymbolTable) -> Any:  # pragma: no cover
        """Evaluate the expression rooted at this node given definitions
        of symbols in a symbol table.

        Raises:
            ValidationError: If the expression is not valid. The given error contains
               context and information on the specifics of the error.

        Args:
            symtab (SymbolTable): Symbol definitions.

        Returns:
            Any: Value of the expression.
        """
        pass

    @abstractmethod
    def __repr__(self) -> str:  # pragma: no cover
        """String representation of the node for printing."""
        pass


@dataclass
class FullNameNode(Node):
    """Expression tree node representing a fully qualified identifier name.
    e.g. Foo.Bar.Baz or Foo
    """

    name: str

    def validate_symbol_refs(self, *, symbols: set[str]) -> None:
        if self.name not in symbols:
            raise ValueError(
                f"{self.name} is referenced by an expression, but is out of scope or has no value"
            )

    def validate(self, *, symtab: SymbolTable) -> None:
        if self.name not in symtab:
            raise ValidationError(f"{self.name} has no value")

    def evaluate(self, *, symtab: SymbolTable) -> Any:
        self.validate(symtab=symtab)
        return symtab[self.name]

    def __repr__(self):
        return f"FullName({self.name})"
