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

    @abstractmethod
    def evaluate(self, *, symtab: SymbolTable) -> Any:  # pragma: no cover
        """Evaluate the expression rooted at this node given definitions
        of symbols in a symbol table.

        Raises:
            ValueError: If the expression is not valid. The given error contains
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

    def evaluate(self, *, symtab: SymbolTable) -> Any:
        if self.name not in symtab:
            raise ValueError(f"{self.name} has no value")
        return symtab[self.name]

    def __repr__(self):
        return f"FullName({self.name})"
