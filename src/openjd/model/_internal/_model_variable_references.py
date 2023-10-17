# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

__all__ = ["validate_model_template_variable_references"]

from collections import defaultdict
from typing import Any, cast, Dict, List

from pydantic.error_wrappers import ErrorWrapper

from .._format_strings import FormatString
from .._types import OpenJDModel, ResolutionScope


class ScopedSymtabs(defaultdict):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(set, **kwargs)

    def union(self, other: "ScopedSymtabs") -> "ScopedSymtabs":
        """Union the other's contents into self."""
        for k, v in other.items():
            self[k] |= v
        return self


def validate_model_template_variable_references(
    cls: OpenJDModel, values: Dict[str, Any]
) -> List[ErrorWrapper]:
    """Validates the template variable references in a model object, based on the model metadata:
    _template_variable_scope
    _template_variable_definitions and
    _template_variable_sources
    """
    return _validate_model_template_variable_references(
        cls,
        values,
        ResolutionScope.TEMPLATE,  # root is template scope
        symbols=ScopedSymtabs(),
        loc=(),
        symbol_prefix="",
    )


def _validate_model_template_variable_references(
    cls: OpenJDModel,
    values: Dict[str, Any],
    current_scope: ResolutionScope,
    symbol_prefix: str,
    symbols: ScopedSymtabs,
    loc: tuple,
) -> List[ErrorWrapper]:
    """Inner implementation of validate_model_template_variable_references().

    Arguments:
      cls - The model class for the Open Job Description model that we're validating the references against.
      values - The values used to construct the model of type cls.
      current_scope - The variable reference scope at this level of the recursion.
      symbol_prefix - The variable symbol prefix (e.g. "Task.") for symbols defined at this level of recursion.
      symbols - The variable symbols that have been defined in each reference scope.
      loc - The path of fields taken from the root of the model to the current recursive level
    """
    errors: List[ErrorWrapper] = []

    # Update scope if the model defines a scope for itself and all children
    if cls._template_variable_scope is not None:
        current_scope = cls._template_variable_scope

    value_defs = cls._template_variable_definitions
    if value_defs.symbol_prefix.startswith("|"):
        # The "|" character resets the nesting.
        symbol_prefix = value_defs.symbol_prefix[1:]
    else:
        symbol_prefix += value_defs.symbol_prefix

    # Collect all the symbols for this value, from itself or exported by its fields
    dict_key = ""  # Pass in the dict key if there is one
    if loc and isinstance(loc[-1], str):
        dict_key = loc[-1]
    value_symbols = _collect_model_template_variables(
        cls, values, current_scope, symbol_prefix, dict_key=dict_key
    )

    # Validate the fields
    for field_name, field_value in values.items():
        if field_value and field_name:
            validation_symbols = ScopedSymtabs()

            # If field_name is in _template_variable_sources, then the value tells us which
            # source fields from the current model/cls we need to propagate down into the
            # recursion for validating field_name
            for source in cls._template_variable_sources.get(field_name, set()):
                validation_symbols.union(value_symbols.get(source, ScopedSymtabs()))

            # Add in all of the symbols passed down from the parent.
            validation_symbols.union(symbols)

            errors.extend(
                _validate_field_template_variable_references(
                    field_value,
                    current_scope,
                    symbol_prefix,
                    validation_symbols,
                    (*loc, field_name),
                )
            )

    return errors


def _collect_model_template_variables(  # noqa: C901  (suppress: too complex)
    cls: OpenJDModel,
    values: Dict[str, Any],
    current_scope: ResolutionScope,
    symbol_prefix: str,
    dict_key: str = "",
) -> Dict[str, ScopedSymtabs]:
    """Collects the names of variables that each field of this model object provides.

    The return value is a dictionary with a set of symbols for each field,
    and "__self__" for the model itself.
    """

    defs = cls._template_variable_definitions

    symbols: Dict[str, ScopedSymtabs] = {"__self__": ScopedSymtabs()}

    def add_symbol(into: ScopedSymtabs, scope: ResolutionScope, symbol_name: str) -> None:
        if scope == ResolutionScope.TEMPLATE:
            into[ResolutionScope.TEMPLATE].add(symbol_name)
            into[ResolutionScope.SESSION].add(symbol_name)
            into[ResolutionScope.TASK].add(symbol_name)
        elif scope == ResolutionScope.SESSION:
            into[ResolutionScope.SESSION].add(symbol_name)
            into[ResolutionScope.TASK].add(symbol_name)
        else:
            into[ResolutionScope.TASK].add(symbol_name)

    if defs.field:
        # The cls defines template variables.

        # Figure out the name of the variable.
        name: str
        if defs.field == "__key__":
            # The name comes from the dict key instead of a model field.
            name = dict_key
        else:
            name = values[defs.field]

        # Define the symbols that are defined in the appropriate scopes.
        for vardef in defs.defines:
            if vardef.prefix.startswith("|"):
                symbol_name = f"{vardef.prefix[1:]}{name}"
            else:
                symbol_name = f"{symbol_prefix}{vardef.prefix}{name}"
            add_symbol(symbols["__self__"], vardef.resolves, symbol_name)

    # If this object injects any template variables then those are injected at the
    # current model's scope.
    for symbol in defs.inject:
        if symbol.startswith("|"):
            symbol_name = symbol[1:]
        else:
            symbol_name = f"{symbol_prefix}{symbol}"
        add_symbol(symbols["__self__"], current_scope, symbol_name)

    for field_name, field_value in values.items():
        if isinstance(field_value, OpenJDModel):
            # Collect all the exported variables
            symbols[field_name] = _collect_model_template_variables(
                cast(OpenJDModel, type(field_value)),
                dict(field_value._iter()),
                current_scope,
                f"{symbol_prefix}",
            )["__export__"]
        elif isinstance(field_value, list):
            symbols[field_name] = ScopedSymtabs()
            for item in field_value:
                # Collect all the exported variables
                if isinstance(item, OpenJDModel):
                    exports = _collect_model_template_variables(
                        cast(OpenJDModel, type(item)),
                        dict(item._iter()),
                        current_scope,
                        f"{symbol_prefix}",
                    )["__export__"]
                    symbols[field_name].union(exports)
        elif isinstance(field_value, dict):
            # This is for when the name comes from the dict key instead of a model field.
            symbols[field_name] = ScopedSymtabs()
            for item_name, item in field_value.items():
                # Collect all the exported variables
                if isinstance(item, OpenJDModel):
                    exports = _collect_model_template_variables(
                        cast(OpenJDModel, type(item)),
                        dict(item._iter()),
                        current_scope,
                        f"{symbol_prefix}",
                        dict_key=item_name,
                    )["__export__"]
                    symbols[field_name].union(exports)

    # Collect the exported symbols as specified by the metadata
    symbols["__export__"] = ScopedSymtabs()
    for source in cls._template_variable_sources.get("__export__", set()):
        symbols["__export__"].union(symbols.get(source, ScopedSymtabs()))

    return symbols


def _validate_field_template_variable_references(  # noqa: C901  (suppress: too complex)
    value: Any, current_scope: ResolutionScope, symbol_prefix: str, symbols: ScopedSymtabs, loc: Any
) -> List[ErrorWrapper]:
    """Recursively validates all the template variable references of a model, based on its
    type annotation metadata. Returns the set of symbols exported by the object
    """

    errors: List[ErrorWrapper] = []
    if isinstance(value, list):
        for i, item in enumerate(value):
            errors.extend(
                _validate_field_template_variable_references(
                    item, current_scope, symbol_prefix, symbols, (*loc, i)
                )
            )
    elif isinstance(value, dict):
        # This is for the v2022_05_01 job parameters, where the name comes
        # from the dict key instead of a model field.
        for item_name, item in value.items():
            # Collect all the exported variables
            errors.extend(
                _validate_field_template_variable_references(
                    item, current_scope, symbol_prefix, symbols, (*loc, item_name)
                )
            )
    elif isinstance(value, FormatString):
        scoped_symbols = symbols[current_scope]
        for expr in value.expressions:
            if expr.expression:
                try:
                    expr.expression.validate_symbol_refs(symbols=scoped_symbols)
                except ValueError as exc:
                    errors.append(ErrorWrapper(exc, loc))
    elif isinstance(value, OpenJDModel):
        errors.extend(
            _validate_model_template_variable_references(
                cast(OpenJDModel, type(value)),
                dict(value._iter()),
                current_scope,
                symbol_prefix,
                symbols,
                loc,
            )
        )

    return errors
