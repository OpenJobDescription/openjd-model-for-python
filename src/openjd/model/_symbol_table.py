# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

from typing import AbstractSet as _AbstractSet
from typing import Any, Optional, Union

__all__ = ["SymbolTable"]


class _VersionedDict(dict):
    """A ``dict`` that bumps its owning :class:`SymbolTable`'s version on
    every mutation.

    The symbol table caches the EXPR engine's typed symbol table (an
    expensive Rust-boundary construction) keyed on its version; ``expr_types``
    is mutated directly by callers (``symtab.expr_types[k] = v`` /
    ``.update(...)``), so those mutations must be observable for the cache to
    be sound.

    Mutations bump the version *after* the change lands: a concurrent reader
    that snapshots mid-mutation then caches under the pre-bump version, and
    the bump immediately supersedes that entry (self-healing), rather than
    poisoning the cache under the post-bump version.
    """

    def __init__(self, owner: "SymbolTable", *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Backref to the owning SymbolTable; internal to this module.
        self._owner = owner

    def __eq__(self, other: object) -> bool:
        # The owner backref is bookkeeping, not value state: equality is
        # plain dict equality (two tables' expr_types with the same contents
        # compare equal regardless of which SymbolTable owns them).
        return super().__eq__(other)

    # dict subclasses are unhashable; keep that explicit alongside __eq__.
    __hash__ = None  # type: ignore[assignment]

    def __setitem__(self, key: Any, value: Any) -> None:
        super().__setitem__(key, value)
        self._owner._bump_version()

    def __delitem__(self, key: Any) -> None:
        super().__delitem__(key)
        self._owner._bump_version()

    def __ior__(self, other: Any) -> "_VersionedDict":  # type: ignore[misc,override]
        # mypy flags the __ior__/__or__ signature asymmetry inherent to
        # augmenting only the in-place operator; `|` (non-mutating) needs no
        # version bump and keeps dict's signature.
        result = super().__ior__(other)
        self._owner._bump_version()
        return result

    def update(self, *args: Any, **kwargs: Any) -> None:
        super().update(*args, **kwargs)
        self._owner._bump_version()

    def setdefault(self, key: Any, default: Any = None) -> Any:
        result = super().setdefault(key, default)
        self._owner._bump_version()
        return result

    def pop(self, *args: Any) -> Any:
        result = super().pop(*args)
        self._owner._bump_version()
        return result

    def popitem(self) -> Any:
        result = super().popitem()
        self._owner._bump_version()
        return result

    def clear(self) -> None:
        super().clear()
        self._owner._bump_version()


def _rebuild_symbol_table(
    table: dict, expr_types: dict, expr_host_rules: Optional[list]
) -> "SymbolTable":
    """Pickle reconstructor for :class:`SymbolTable` (see ``__reduce__``)."""
    symtab = SymbolTable()
    symtab._table.update(table)
    symtab.expr_types.update(expr_types)
    symtab._expr_host_rules = expr_host_rules
    return symtab


class SymbolTable:
    """
    Class used to represent the available symbols that can be used for interpolation in the current context.
    """

    _table: dict[str, Any]
    # Optional host-context path mapping rules (``openjd.expr.PathMappingRule``
    # values). When set (even to an empty list), EXPR expressions evaluated
    # against this symbol table run with a host context: host-context
    # functions such as ``apply_path_mapping`` are available and apply these
    # rules — the v0 equivalent of openjd-rs's session-scope
    # ``HostContext::WithRules``. ``None`` means no host context (template
    # scope).
    _expr_host_rules: Optional[list[Any]]
    # Monotonic mutation counter. Bumped by every mutation of ``_table``,
    # ``expr_types``, or ``expr_host_rules`` so that the EXPR evaluation layer
    # can cache the (expensive, Rust-boundary) typed engine symbol table and
    # host-context profile per symbol-table state. See
    # ``_format_strings._expr_support.symtab_to_expr_values``.
    _version: int
    # Opaque cache slot owned by the EXPR evaluation layer: maps cache keys
    # to (version, value) pairs. Never copied to derived tables.
    _expr_eval_cache: Optional[dict]

    def __init__(self, *, source: Optional[Union[SymbolTable, dict[str, Any]]] = None):
        """Initialize the SymbolTable

        Args:
            source (Optional[Union[SymbolTable, dict[str, Any]]], optional): If provided then this
                gets initialized with the contents of the given source. Defaults to None.
        """
        self._table = dict()
        self._expr_types: dict[str, str] = _VersionedDict(self)
        self._expr_host_rules = None
        self._version = 0
        self._expr_eval_cache = None
        if source is not None:
            if isinstance(source, SymbolTable):
                self._table.update(source._table)
                self._expr_types.update(source._expr_types)
                if source._expr_host_rules is not None:
                    self._expr_host_rules = list(source._expr_host_rules)
            elif isinstance(source, dict):
                self._table.update(source)
            else:
                raise TypeError(f"Cannot initialize with type {type(source)}")

    def _bump_version(self) -> None:
        self._version += 1

    @property
    def expr_types(self) -> dict[str, str]:
        """Optional mapping of symbol name -> OpenJD type name (e.g. "INT",
        "LIST[INT]") for EXPR-typed symbols. Used by the EXPR expression
        engine to coerce stored values to their declared type. Preserved
        across copies and unions; empty for non-EXPR symbol tables.

        Mutations (including item assignment and ``update``) are tracked for
        the EXPR evaluation cache; assigning a whole new mapping is also
        supported.
        """
        return self._expr_types

    @expr_types.setter
    def expr_types(self, value: dict[str, str]) -> None:
        # Rewrap into a versioned dict so subsequent in-place mutations keep
        # invalidating the cache, and bump for the reassignment itself.
        self._expr_types = _VersionedDict(self, value)
        self._bump_version()

    @property
    def expr_host_rules(self) -> Optional[list[Any]]:
        return self._expr_host_rules

    @expr_host_rules.setter
    def expr_host_rules(self, rules: Optional[list[Any]]) -> None:
        self._expr_host_rules = rules
        self._bump_version()

    def __reduce__(self) -> tuple:
        # The versioned dict's owner backref cannot survive plain dict-subclass
        # pickling (items are restored through __setitem__ before the instance
        # state exists), so serialize plain data and rebuild.
        return (
            _rebuild_symbol_table,
            (
                dict(self._table),
                dict(self._expr_types),
                None if self._expr_host_rules is None else list(self._expr_host_rules),
            ),
        )

    def __repr__(self) -> str:
        return f"SymbolTable({self._table})"

    def __contains__(self, symbol: str) -> bool:
        return symbol in self._table

    def __getitem__(self, symbol: str) -> Any:
        return self._table[symbol]

    def __setitem__(self, symbol: str, value: Any) -> None:
        if not isinstance(symbol, str):
            raise TypeError("Symbol must be a string")
        self._table[symbol] = value
        self._bump_version()

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
        retval.expr_types.update(self._expr_types)
        if self._expr_host_rules is not None:
            retval._expr_host_rules = list(self._expr_host_rules)
        for symtab in symtabs:
            if isinstance(symtab, SymbolTable):
                retval._table.update(symtab._table)
                retval.expr_types.update(symtab._expr_types)
                if symtab._expr_host_rules is not None:
                    retval._expr_host_rules = list(symtab._expr_host_rules)
            elif isinstance(symtab, dict):
                retval._table.update(symtab)
            else:
                raise TypeError(f"Cannot union with type {type(symtab)}")
        return retval
