# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from collections import defaultdict
import typing
from typing import cast, Any, Optional, Type, Literal, Union
from inspect import isclass

from pydantic import Discriminator
from pydantic_core import InitErrorDetails
from pydantic.fields import FieldInfo, ModelPrivateAttr

# Workaround for Python 3.9 where issubclass raises an error "TypeError: issubclass() arg 1 must be a class"
from pydantic.v1.utils import lenient_issubclass

from .._types import OpenJDModel, ResolutionScope
from .._format_strings import FormatString, FormatStringError

__all__ = ["prevalidate_model_template_variable_references"]

# *******************
# READ THIS if you want to understand what's going on in this file.
# *******************
#
# What are we doing here?
# ------
# The function 'prevalidate_model_template_variable_references()' exported from this
# module is used internally to this package/library to check/validate that template
# variable references within a template (Job or Environment) are to variables that
# have been defined within the template, and that they exist at the scope of the reference.
# Variable references to variables that don't exist in the scope are flagged as validation
# errors and returned by the function.
#
# For example,
# {
#   "specificationVersion": "jobtemplate-2023-09",
#   "name": " {{ Param.JobName }}",
#   "parameterDefinitions": [
#      { "name": "Name", "type": "STRING "}
#   ],
#   ... and so on
# }
# would have an error at the _root_.name field because the template variable "Param.JobName" does
# not exist (the declared parameter is called "Param.Name" or "RawParam.Name").
#
# The current OpenJD models make use of a limited number of field types, and so this implementation
# only caters to those fields that we use. Specifically, we currently have fields that are the following
# shapes:
# class FieldTypesUsed(OpenJDModel):
#    # Singleton field types
#    # -----
#    literal: Literal[EnumClass.member]
#    scalar: int, str, FormatString, Decimal, etc.
#    discriminated_union: Annotated[Union[OpenJDModel, OpenJDModel, ...], Field(..., discriminator=<fieldname>)
#    union: Union[<list-of-scalars>, <scalar>] or Union[<scalar-type>, <scalar-type>, ...]
#    # -----
#    # List field types:
#    # -----
#    list_field: list[<singleton>]
#    # -----
#    # Dictionary field types:
#    # -----
#    dict_field: dict[str, <singleton>]
#
# This is a piece of a larger suite of validators that are run on the given input, and need only
# be narrowly concerned with validating that references to variables are correct. Other errors, such
# as parsing or model-mismatch errors are detected by other validators in the suite.
#
# How are we doing it?
# ----
# We're given both:
#  1) The root class of the template model (e.g. JobTemplate or EnvironmentTemplate); and
#  2) *Prevalidation* candidate data for that model as a dict[str, Any].
#
# Only field values of a type derived from OpenJDModel can *define* a template variable, and only
# field values that are of type FormatString can *reference* a template variable.
# So, we do a depth-first preorder traversal of the template model in sync with the given value dictionary. Each
# node of this traversal is of a model type derived from OpenJDModel.
#
# At each node of the traversal we:
#  1) Recursively collect the set of template variable names that are available to the current node:
#      - The node's parent may have template variable definitions that are made available to this node.
#      - Child nodes of this one may export their template variable definitions to this node.
#      - The node itself my define template variables for reference within it and its children.
#  2) Then inspect each field of the model:
#      a) FormatStrings to ensure that they only reference defined variables; and
#      b) Recursively traverse into members that are of type derived from OpenJDModel; these are the members
#         that may contain template variable references within their members.
#
# It is possible for a given template to contain multiple variable reference errors, and we want to report *all* of them
# so that users do not have to play find-the-error whack-a-mole (validate, fix the one error, re-validate, fix the new error, repeat...).
#
# Through all of this we keep in mind that our input *data* may not match our model at all (e.g. we're expecting an OpenJDModel for
# a field but are given a value that's a string, int, or other non-dict type).
#
# What else do I need to know?
# ---
# 1. Every template variable is defined at one of three scopes. That scope defines where that variable is available for reference.
#    See the docstring for the ResolutionScope class for information on these scopes.
#     - If the OpenJDModel._template_variable_scope member has a value, then it indicates a change of scope in the traversal; the node
#       and all children (until another scope change) resolve variable references using this given scope.
# 2. An OpenJDModel can define template variables.
#    - Information on which variables a model defines, if any, are encoded in that model's `_template_variable_definitions` field.
#      See the docstring of the DefinesTemplateVariables class for information on how variables are defined.
# 3. An OpenJDModel can export template variable definitions to their parent in the template model, and have to declare which, if any,
#    of their fields variable definitions are passed in to.
#    - Information on this is encoded in the model's `_template_variable_sources` field. See the comment for this field in the
#      OpenJDModel base class for information on this property
# 4. Since this validation is a pre-validator, we basically have to re-implement a fragment of Pydantic's model parser for this
#    depth first traversal. Thus, you'll need to know the following about Pydantic v2's data model and parser to understand this
#    implementation:
#    a) All models are derived from pydantic.BaseModel
#    b) pydantic.BaseModel.model_fields: dict[str, FieldInfo] is injected into all BaseModels by pydantic's BaseModel metaclass.
#       This member is what gives pydantic information about each of the fields defined in the model class. The key of the dict is the
#       name of the field in the model.
#    c) pydantic.FieldInfo describes the type information about a model's field:
#       i) pydantic.FieldInfo.annotation gives you the type of the field; The structure of the field is contained
#          in this type, including typing.Annotated values for discriminated unions. Both the definition collection and
#          validation recursively unwraps these types along with the values. The pydantic.FieldInfo also includes a discriminator
#          value, so the code handles both cases.


class ScopedSymtabs(defaultdict):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(set, **kwargs)

    def update_self(self, other: "ScopedSymtabs") -> "ScopedSymtabs":
        """Union the other's contents into self."""
        for k, v in other.items():
            self[k] |= v
        return self


def prevalidate_model_template_variable_references(cls: Type[OpenJDModel], values: dict[str, Any]):
    """Validates the template variable references in a given model.

    Notes:
    1. This is designed for use as a pre-validator. As such, the given
       'values' have *NOT* been parsed and converted in to model class instances. Instead,
       'values' is raw unvalidated input from the user; it may be completely wrong!
    2. The validation is based on the model metadata that is stored in the
       model class hierarchy:
       _template_variable_scope
       _tempalte_variable_definitions and
       _template_variable_sources
    """

    return _validate_model_template_variable_references(
        cls,
        _internal_deepcopy(values),
        ResolutionScope.TEMPLATE,
        symbols=ScopedSymtabs(),
        loc=(),
        symbol_prefix="",
    )


def _internal_deepcopy(value: Any) -> Any:
    # We might be given input that actually contains models. If so, then we convert those
    # back to dictionaries to simplify the logic in this file.
    # e.g. if someone is using a model's constructor directly as in:
    # JobTemplate(
    #    specificationVersion="jobtemplate-2023-09",
    #    name="Foo",
    #    steps=[
    #       StepTemplate( ... ),
    #       StepTemplate( ... )
    #    ]
    # )
    # In this case our input will have instances of StepTemplate within it that we need
    # to convert to dicts.
    if isinstance(value, dict):
        return {k: _internal_deepcopy(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_internal_deepcopy(v) for v in value]
    elif isinstance(value, OpenJDModel):
        return value.dict()
    return value


def _validate_model_template_variable_references(
    model: Type,
    value: Any,
    current_scope: ResolutionScope,
    symbol_prefix: str,
    symbols: ScopedSymtabs,
    loc: tuple,
    discriminator: Union[str, Discriminator, None] = None,
) -> list[InitErrorDetails]:
    """Inner implementation of prevalidate_model_template_variable_references().

    Arguments:
      cls - The model class for the Open Job Description model that we're validating the references against.
      values - The values used to construct the model of type cls.
      current_scope - The variable reference scope at this level of the recursion.
      symbol_prefix - The variable symbol prefix (e.g. "Task.") for symbols defined at this level of recursion.
      symbols - The variable symbols that have been defined in each reference scope.
      loc - The path of fields taken from the root of the model to the current recursive level
    """

    # The errors that we're collecting for this node in the traversal, and will return from the function call.
    errors: list[InitErrorDetails] = []

    model_origin = typing.get_origin(model)

    # Unwrap the Optional types
    if model_origin is typing.Optional:
        return _validate_model_template_variable_references(
            typing.get_args(model)[0],
            value,
            current_scope,
            symbol_prefix,
            symbols,
            loc,
            discriminator=discriminator,
        )

    # Unwrap the Annotated type, and get the discriminator while doing so
    if model_origin is typing.Annotated:
        model_args = typing.get_args(model)
        for annotation in model_args[1:]:
            if isinstance(annotation, FieldInfo):
                discriminator = annotation.discriminator
        return _validate_model_template_variable_references(
            model_args[0],
            value,
            current_scope,
            symbol_prefix,
            symbols,
            loc,
            discriminator=discriminator,
        )

    # Validate all the items of a list
    if model_origin is list:
        # If the shape expects a list, but the value isn't one then we have a validation error.
        # The error will get flagged by subsequent passes of the model validation.
        if isinstance(value, list):
            item_model = typing.get_args(model)[0]
            for i, item in enumerate(value):
                errors.extend(
                    _validate_model_template_variable_references(
                        item_model, item, current_scope, symbol_prefix, symbols, (*loc, i)
                    )
                )
        return errors

    if model_origin is dict:
        # If the shape expects a dict, but the value isn't one then we have a validation error.
        # The error will get flagged by subsequent passes of the model validation.
        if isinstance(value, dict):
            item_model = typing.get_args(model)[1]
            for key, item in value.items():
                if not isinstance(key, str):
                    continue
                errors.extend(
                    _validate_model_template_variable_references(
                        item_model,
                        item,
                        current_scope,
                        symbol_prefix,
                        symbols,
                        (*loc, key),
                    )
                )
        return errors

    # Validate all the variables from a non-discriminated union
    if model_origin is Union and discriminator is None:
        for sub_type in typing.get_args(model):
            errors.extend(
                _validate_model_template_variable_references(
                    sub_type, value, current_scope, symbol_prefix, symbols, loc
                )
            )
        return errors

    # Unwrap a discriminated union to the selected type
    if model_origin is Union and discriminator is not None:
        unioned_model = _get_model_for_singleton_value(model, value, discriminator)
        if unioned_model is not None:
            return _validate_model_template_variable_references(
                unioned_model,
                value,
                current_scope,
                symbol_prefix,
                symbols,
                loc,
            )
        else:
            return []

    if isclass(model) and lenient_issubclass(model, FormatString):
        if isinstance(value, str):
            return _check_format_string(value, current_scope, symbols, loc)
        return []

    # Return an empty error list if it's not an OpenJDModel, or if it's not a dict
    if not (isclass(model) and lenient_issubclass(model, OpenJDModel) and isinstance(value, dict)):
        return []

    # Does this cls change the variable reference scope for itself and its children? If so, then update
    # our scope.
    model_override_scope = cast(ModelPrivateAttr, model._template_variable_scope).get_default()
    if model_override_scope is not None:
        current_scope = model_override_scope

    # Apply any changes that this node makes to the template variable prefix.
    #  e.g. It may change "Env." to "Env.File."
    variable_defs = model._template_variable_definitions
    if variable_defs.symbol_prefix.startswith("|"):
        # The "|" character resets the nesting.
        symbol_prefix = variable_defs.symbol_prefix[1:]
    else:
        # If the node doesn't modify the variable prefix, then symbol_prefix will be the empty string
        symbol_prefix += variable_defs.symbol_prefix

    # Recursively collect all of the variable definitions at this node and its child nodes.
    value_symbols = _collect_variable_definitions(
        model, value, current_scope, symbol_prefix, recursive_pruning=False
    )

    # Recursively validate the contents of FormatStrings within the model.
    for field_name, field_info in model.model_fields.items():
        field_value = value.get(field_name)
        field_model = field_info.annotation
        if field_value is None or field_model is None:
            continue
        if typing.get_origin(field_model) is Literal:
            # Literals aren't format strings and cannot be recursed in to; skip them.
            continue

        validation_symbols = ScopedSymtabs()

        # If field_name is in _template_variable_sources, then the value tells us which
        # source fields from the current model/cls we need to propagate down into the
        # recursion for validating field_name
        for source in model._template_variable_sources.get(field_name, set()):
            validation_symbols.update_self(value_symbols.get(source, ScopedSymtabs()))

        # Add in all of the symbols passed down from the parent.
        validation_symbols.update_self(symbols)

        errors.extend(
            _validate_model_template_variable_references(
                field_model,
                field_value,
                current_scope,
                symbol_prefix,
                validation_symbols,
                (*loc, field_name),
                field_info.discriminator,
            )
        )

    return errors


def _check_format_string(
    value: str, current_scope: ResolutionScope, symbols: ScopedSymtabs, loc: tuple
) -> list[InitErrorDetails]:
    # Collect the variable reference errors, if any, from the given FormatString value.

    errors = list[InitErrorDetails]()
    scoped_symbols = symbols[current_scope]
    try:
        f_value = FormatString(value)
    except FormatStringError:
        # Improperly formed string. Later validation passes will catch and flag this.
        return errors

    for expr in f_value.expressions:
        if expr.expression:
            try:
                expr.expression.validate_symbol_refs(symbols=scoped_symbols)
            except ValueError as exc:
                errors.append(
                    InitErrorDetails(type="value_error", loc=loc, ctx={"error": exc}, input=value)
                )
    return errors


def _get_model_for_singleton_value(
    model: Any, value: Any, discriminator: Union[str, Discriminator, None] = None
) -> Optional[Type]:
    """Given a FieldInfo and the value that we're given for that field, determine
    the actual Model for the value in the event that the FieldInfo may be for
    a discriminated union."""

    # Unpack the annotated type, extracting the discriminator if provided
    if typing.get_origin(model) is typing.Annotated:
        for annotation in typing.get_args(model)[1:]:
            if isinstance(annotation, FieldInfo):
                discriminator = annotation.discriminator
        model = typing.get_args(model)[0]

    if discriminator is None or typing.get_origin(model) is not typing.Union:
        # If it's not a discriminated union, then pass through the type
        return model
    elif not isinstance(discriminator, str):
        # This code only supports a field name discriminator, not a callable
        raise NotImplementedError(
            "You have hit an unimplemented code path. Please report this as a bug."
        )
    elif not isinstance(value, dict):
        # Validation error - will be flagged by a subsequent validation stage.
        return None

    # The field is a discriminated union. Use the discriminator key to figure out which model
    # this specific value is.
    discr_value = value.get(discriminator)
    if not discr_value:
        # key didn't have a value. This is a validation error that a later phase of validation
        # will flag.
        return None
    if not isinstance(discr_value, str):
        # Keys must be strings.
        return None

    # Find the correct model for the discriminator value by unwrapping the Union and then the discriminator Literals
    assert typing.get_origin(model) is typing.Union  # For the type checker
    for sub_model in typing.get_args(model):
        sub_model_discr_value = sub_model.model_fields[discriminator].annotation
        if typing.get_origin(sub_model_discr_value) is not typing.Literal:
            raise NotImplementedError(
                "You have hit an unimplemented code path. Please report this as a bug."
            )
        if typing.get_args(sub_model_discr_value)[0] == discr_value:
            return sub_model

    return None


## =============================================
## =============================================
## =============================================
## =============================================
#    Functions for collecting variable definitions
## =============================================
## =============================================
## =============================================
## =============================================


def _collect_variable_definitions(  # noqa: C901  (suppress: too complex)
    model: Type,
    value: Any,
    current_scope: ResolutionScope,
    symbol_prefix: str,
    recursive_pruning: bool = True,
    discriminator: Union[str, Discriminator, None] = None,
) -> dict[str, ScopedSymtabs]:
    """Collects the names of variables that each field of this model object provides.

    The return value is a dictionary with a set of symbols for each field,
    "__self__" for the model itself, and "__export__" for the symbols that it
    exports to its parent in the data model.

    When the model is not an OpenJDModel, it only populates the "__export__".
    """

    # NOTE: This is not written to be super generic and handle all possible OpenJD models going
    #  forward forever. It handles the subset of the general Pydantic data model that OpenJD is
    #  currently using, and will be extended as we use additional features of Pydantic's data model.

    model_origin = typing.get_origin(model)

    # Unwrap the Optional types
    if model_origin is typing.Optional:
        return _collect_variable_definitions(
            typing.get_args(model)[0],
            value,
            current_scope,
            symbol_prefix,
            discriminator=discriminator,
        )

    # Unwrap the Annotated type, and get the discriminator while doing so
    if model_origin is typing.Annotated:
        model_args = typing.get_args(model)
        for annotation in model_args[1:]:
            if isinstance(annotation, FieldInfo):
                discriminator = annotation.discriminator
        return _collect_variable_definitions(
            model_args[0], value, current_scope, symbol_prefix, discriminator=discriminator
        )

    # Aggregate all the collected variable definitions from a list
    if model_origin is list:
        # If the shape expects a list, but the value isn't one then we have a validation error.
        # The error will get flagged by subsequent passes of the model validation.
        symtab = ScopedSymtabs()
        if isinstance(value, list):
            item_model = typing.get_args(model)[0]
            for item in value:
                symtab.update_self(
                    _collect_variable_definitions(item_model, item, current_scope, symbol_prefix)[
                        "__export__"
                    ]
                )
        return {"__export__": symtab}

    # Aggregate all the matching variables from a non-discriminated union
    if model_origin is Union and discriminator is None:
        symtab = ScopedSymtabs()
        for sub_type in typing.get_args(model):
            symtab.update_self(
                _collect_variable_definitions(sub_type, value, current_scope, symbol_prefix)[
                    "__export__"
                ]
            )
        return {"__export__": symtab}

    # Unwrap a discriminated union to the selected type
    if model_origin is Union and discriminator is not None:
        unioned_model = _get_model_for_singleton_value(model, value, discriminator)
        if unioned_model is not None:
            return _collect_variable_definitions(
                unioned_model,
                value,
                current_scope,
                symbol_prefix,
            )
        else:
            return {"__export__": ScopedSymtabs()}

    # Anything except for an OpenJDModel returns an empty result
    if not isclass(model) or not lenient_issubclass(model, OpenJDModel):
        return {"__export__": ScopedSymtabs()}

    # If the model has no exported variable definitions, prune it
    if recursive_pruning and "__export__" not in model._template_variable_sources:
        return {"__export__": ScopedSymtabs()}

    # If the value is not a dict, then it's a validation error. We'll flag that error later.
    if not isinstance(value, dict):
        return {"__export__": ScopedSymtabs()}

    symbols: dict[str, ScopedSymtabs] = {"__self__": ScopedSymtabs(), "__export__": ScopedSymtabs()}

    # Process the variable definitions defined by this model
    defs = getattr(model, "_template_variable_definitions", None)

    if defs:
        if defs.field:
            # defs.field being defined means that the cls defines a template variable.

            # Figure out the name of the variable.
            name: str = ""
            if (def_field_value := value.get(defs.field)) is not None:
                # The name of the variable is in a field and the field has a value
                # in the given data.
                if isinstance(def_field_value, str):
                    # The field can only be a name if its value is a string; otherwise,
                    # this will get flagged as a validation error later.
                    name = def_field_value

            # Define the symbols that are defined in the appropriate scopes if we have the name.
            if name:
                for vardef in defs.defines:
                    if vardef.prefix.startswith("|"):
                        symbol_name = f"{vardef.prefix[1:]}{name}"
                    else:
                        symbol_name = f"{symbol_prefix}{vardef.prefix}{name}"
                    _add_symbol(symbols["__self__"], vardef.resolves, symbol_name)

        # If this object injects any template variables then those are injected at the
        # current model's scope.
        for symbol in defs.inject:
            if symbol.startswith("|"):
                symbol_name = symbol[1:]
            else:
                symbol_name = f"{symbol_prefix}{symbol}"
            _add_symbol(symbols["__self__"], current_scope, symbol_name)

    # Collect the variable definitions exported by the fields of the model
    for field_name, field_info in model.model_fields.items():
        field_value = value.get(field_name)
        field_model = field_info.annotation
        if field_value is None or field_model is None:
            continue

        discriminator = field_info.discriminator

        symbols[field_name] = _collect_variable_definitions(
            field_model, field_value, current_scope, symbol_prefix, discriminator=discriminator
        )["__export__"]

    # Collect the exported symbols as specified by the metadata
    for source in model._template_variable_sources.get("__export__", set()):
        symbols["__export__"].update_self(symbols.get(source, ScopedSymtabs()))

    return symbols


def _add_symbol(into: ScopedSymtabs, scope: ResolutionScope, symbol_name: str) -> None:
    """A helper function for adding a symbol into the correct ScopedSymtabs based on the scope of
    the symbol definition"""
    if scope == ResolutionScope.TEMPLATE:
        into[ResolutionScope.TEMPLATE].add(symbol_name)
        into[ResolutionScope.SESSION].add(symbol_name)
        into[ResolutionScope.TASK].add(symbol_name)
    elif scope == ResolutionScope.SESSION:
        into[ResolutionScope.SESSION].add(symbol_name)
        into[ResolutionScope.TASK].add(symbol_name)
    else:
        into[ResolutionScope.TASK].add(symbol_name)
