# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

from typing import AbstractSet as _AbstractSet
from typing import Any, Optional, Union

__all__ = ["SymbolTable"]


class SymbolTable:
    """
    Class used to represent the available symbols that can be used for interpolation in the current context.
    """

    _table: dict[str, Any]

    def __init__(self, *, source: Optional[Union[SymbolTable, dict[str, Any]]] = None):
        """Initialize the SymbolTable

        Args:
            source (Optional[Union[SymbolTable, dict[str, Any]]], optional): If provided then this
                gets initialized with the contents of the given source. Defaults to None.
        """
        self._table = dict()
        if source is not None:
            if isinstance(source, SymbolTable):
                self._table.update(source._table)
            elif isinstance(source, dict):
                self._table.update(source)
            else:
                raise TypeError(f"Cannot initialize with type {type(source)}")

    def __contains__(self, symbol: str) -> bool:
        return symbol in self._table

    def __getitem__(self, symbol: str) -> Any:
        return self._table[symbol]

    def __setitem__(self, symbol: str, value: Any) -> None:
        if not isinstance(symbol, str):
            raise TypeError("Symbol must be a string")
        self._table[symbol] = value

    @property
    def symbols(self) -> _AbstractSet[str]:
        """
        Returns:
            Set[str]: The set of symbols defined in this symbol table
        """
        return self._table.keys()

    def union(self, *symtabs: Union[SymbolTable, dict[str, Any]]) -> SymbolTable:
        """Create a new SymbolTable that is the union of this SymbolTable with
        the given ones.

        If a specific symbol is defined in more than one SymbolTable then the
        last defined value takes precidence.

        Returns:
            SymbolTable: A new SymbolTable.
        """
        retval = SymbolTable()
        retval._table.update(self._table)
        for symtab in symtabs:
            if isinstance(symtab, SymbolTable):
                retval._table.update(symtab._table)
            elif isinstance(symtab, dict):
                retval._table.update(symtab)
            else:
                raise TypeError(f"Cannot union with type {type(symtab)}")
        return retval
