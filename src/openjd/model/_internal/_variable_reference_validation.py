# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from collections import defaultdict
from typing import Any, Optional, Type
from inspect import isclass

from pydantic.v1.error_wrappers import ErrorWrapper
import pydantic.v1.fields
from pydantic.v1.typing import is_literal_type

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
#    depth first traversal. Thus, you'll need to know the following about Pydantic v1.x's data model and parser to understand this
#    implementation:
#    a) All models are derived from pydantic.v1.BaseModel
#    b) pydantic.BaseModel.__fields__: dict[str, pydantic.ModelField] is injected into all BaseModels by pydantic's BaseModel metaclass.
#       This member is what gives pydantic information about each of the fields defined in the model class. The key of the dict is the
#       name of the field in the model.
#    c) pydantic.ModelField describes the type information about a model's field:
#        i) pydantic.ModelField.shape is an integer that defines the shape of the field
#                SHAPE_SINGLETON means that it's a singleton type.
#                SHAPE_LIST means that it's a list type.
#                SHAPE_DICT means that it's a dict type.
#                etc.
#       ii) pydantic.ModelField.type_ gives you the type of the field; this is only useful for scalar singleton fields.
#       iii) pydantic.ModelField.sub_fields: Optional[list[pydantic.ModelField]] exists for list, dictionary, and union-typed singleton
#            fields:
#            1. For SHAPE_LIST: sub_fields has length 1, and its element is the ModelField for the elements of the list.
#            2. For SHAPE_DICT: sub_fields has length 1, and its element is the ModelField for the value-type of the dict.
#            3. For SHAPE_SINGLETON:
#                 a) For scalar-typed fields: sub_fields is None
#                 b) For union-typed fields: sub_fields is a list of all of the types in the union
#       iv) For discriminated unions:
#            1. pydantic.ModelField.discriminator_key: Optional[str] exists and it gives the name of the submodel field used to
#               determine which type of the union a given data value is.
#            2. pydantic.sub_fields_mapping: Optional[dict[str,pydantic.ModelField]] exists and can be used to find the unioned type
#               for a given discriminator value.
#


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
    cls: Type[OpenJDModel],
    values: dict[str, Any],
    current_scope: ResolutionScope,
    symbol_prefix: str,
    symbols: ScopedSymtabs,
    loc: tuple,
) -> list[ErrorWrapper]:
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
    errors: list[ErrorWrapper] = []

    # Does this cls change the variable reference scope for itself and its children? If so, then update
    # our scope.
    if cls._template_variable_scope is not None:
        current_scope = cls._template_variable_scope

    # Apply any changes that this node makes to the template variable prefix.
    #  e.g. It may change "Env." to "Env.File."
    variable_defs = cls._template_variable_definitions
    if variable_defs.symbol_prefix.startswith("|"):
        # The "|" character resets the nesting.
        symbol_prefix = variable_defs.symbol_prefix[1:]
    else:
        # If the node doesn't modify the variable prefix, then symbol_prefix will be the empty string
        symbol_prefix += variable_defs.symbol_prefix

    # Recursively collect all of the variable definitions at this node and its child nodes.
    value_symbols = _collect_variable_definitions(cls, values, current_scope, symbol_prefix)

    # Recursively validate the contents of FormatStrings within the model.
    # Note: cls.__fields__: dict[str, pydantic.v1.fields.ModelField]
    for field_name, field_model in cls.__fields__.items():
        field_value = values.get(field_name, None)
        if field_value is None:
            continue
        if is_literal_type(field_model.type_):
            # Literals aren't format strings and cannot be recursed in to; skip them.
            continue

        validation_symbols = ScopedSymtabs()

        # If field_name is in _template_variable_sources, then the value tells us which
        # source fields from the current model/cls we need to propagate down into the
        # recursion for validating field_name
        for source in cls._template_variable_sources.get(field_name, set()):
            validation_symbols.update_self(value_symbols.get(source, ScopedSymtabs()))

        # Add in all of the symbols passed down from the parent.
        validation_symbols.update_self(symbols)

        if field_model.shape == pydantic.v1.fields.SHAPE_SINGLETON:
            _validate_singleton(
                errors,
                field_model,
                field_value,
                current_scope,
                symbol_prefix,
                validation_symbols,
                (*loc, field_name),
            )
        elif field_model.shape == pydantic.v1.fields.SHAPE_LIST:
            if not isinstance(field_value, list):
                continue
            assert field_model.sub_fields is not None  # For the type checker
            item_model = field_model.sub_fields[0]
            for i, item in enumerate(field_value):
                _validate_singleton(
                    errors,
                    item_model,
                    item,
                    current_scope,
                    symbol_prefix,
                    validation_symbols,
                    (*loc, field_name, i),
                )
        elif field_model.shape == pydantic.v1.fields.SHAPE_DICT:
            if not isinstance(field_value, dict):
                continue
            assert field_model.sub_fields is not None  # For the type checker
            item_model = field_model.sub_fields[0]
            for key, item in field_value.items():
                if not isinstance(key, str):
                    continue
                _validate_singleton(
                    errors,
                    item_model,
                    item,
                    current_scope,
                    symbol_prefix,
                    validation_symbols,
                    (*loc, field_name, key),
                )
        else:
            raise NotImplementedError(
                "You have hit an unimplemented code path. Please report this as a bug."
            )

    return errors


def _validate_singleton(
    errors: list[ErrorWrapper],
    field_model: pydantic.v1.fields.ModelField,
    field_value: Any,
    current_scope: ResolutionScope,
    symbol_prefix: str,
    symbols: ScopedSymtabs,
    loc: tuple,
) -> None:
    # Note: ModelField.sub_fields is populated if (otherwise it's None):
    #   a) field is a list type => sub_fields has 1 element, and its type is the element type of the list
    #       - this is handled *before* calling this function.
    #   b) field is a union => sub_fields' elements are the model types in the union
    #   c) field is a discriminated union => sub_fields has 1 element, and it is a ModelField with info about the union.

    if (
        field_model.discriminator_key is None
        and field_model.sub_fields
        and len(field_model.sub_fields) > 1
    ):
        # The field is a union without a discriminator.
        #  e.g. Union[ list[Union[int,FormatString]], FormatString ]
        _validate_general_union(
            errors, field_model, field_value, current_scope, symbol_prefix, symbols, loc
        )
        return

    if field_model.discriminator_key:
        #  Discriminated union case - figure out what the actual model type is.
        if not isinstance(field_value, dict):
            # Validation error -- discriminated unions are always discriminating models, and so
            # must by a dict.
            return
        model = _get_model_for_singleton_value(field_model, field_value)
        if model is None:
            # Validation error - will be flagged by a subsequent validation stage.
            return
        field_model = model

    if isclass(field_model.type_) and issubclass(field_model.type_, FormatString):
        if isinstance(field_value, str):
            errors.extend(_check_format_string(field_value, current_scope, symbols, loc))
    elif isclass(field_model.type_) and issubclass(field_model.type_, OpenJDModel):
        if isinstance(field_value, dict):
            errors.extend(
                _validate_model_template_variable_references(
                    field_model.type_,
                    field_value,
                    current_scope,
                    symbol_prefix,
                    symbols,
                    loc,
                )
            )


def _validate_general_union(
    errors: list[ErrorWrapper],
    field_model: pydantic.v1.fields.ModelField,
    field_value: Any,
    current_scope: ResolutionScope,
    symbol_prefix: str,
    symbols: ScopedSymtabs,
    loc: tuple,
) -> None:
    # Notes:
    # - We narrowly only handle the kinds of unions that are present in the current model.
    #   - We rely on additions to the model being well tested w.r.t. evaluation of format strings, and
    #     such new tests being added signaling that this code needs to be enhanced.
    # - Unions of model types are not currently present in the model so we do not handle/test that case.
    # - The only union type that we have looks like: Union[ list[Union[int,FormatString]], FormatString ]
    #    - It's in the range field of task parameter definitions

    # We have to consider that the value may be any one of the types in the union, so we have to look at each possible type
    # and attempt to process the value as that type.
    assert field_model.sub_fields is not None  # For the type checker
    for sub_field in field_model.sub_fields:
        if sub_field.shape == pydantic.v1.fields.SHAPE_SINGLETON:
            _validate_singleton(
                errors, sub_field, field_value, current_scope, symbol_prefix, symbols, loc
            )
        elif sub_field.shape == pydantic.v1.fields.SHAPE_LIST:
            if not isinstance(field_value, list):
                # The given value must be a list in this case.
                continue
            assert sub_field.sub_fields is not None
            item_model = sub_field.sub_fields[0]  # For the type checker
            for item in field_value:
                _validate_singleton(
                    errors, item_model, item, current_scope, symbol_prefix, symbols, loc
                )


def _check_format_string(
    value: str, current_scope: ResolutionScope, symbols: ScopedSymtabs, loc: tuple
) -> list[ErrorWrapper]:
    # Collect the variable reference errors, if any, from the given FormatString value.

    errors = list[ErrorWrapper]()
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
                errors.append(ErrorWrapper(exc, loc))
    return errors


def _get_model_for_singleton_value(
    field_model: pydantic.v1.fields.ModelField, value: Any
) -> Optional[pydantic.v1.fields.ModelField]:
    """Given a ModelField and the value that we're given for that field, determine
    the actual ModelField for the value in the event that the ModelField may be for
    a discriminated union."""

    # Precondition: value is a dict
    assert isinstance(value, dict)

    if field_model.discriminator_key is None:
        # If it's not a discriminated union, then the type_ of the field is the expected type of the value.
        return field_model

    # The field is a discriminated union. Use the discriminator key to figure out which model
    # this specific value is.
    key_value = value.get(field_model.discriminator_key, None)
    if not key_value:
        # key didn't have a value. This is a validation error that a later phase of validation
        # will flag.
        return None
    if not isinstance(key_value, str):
        # Keys must be strings.
        return None

    assert field_model.sub_fields_mapping is not None  # For the type checker
    sub_model = field_model.sub_fields_mapping.get(key_value)
    if not sub_model:
        # The key value that we were given is not valid.
        return None
    return sub_model


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
    cls: Type[OpenJDModel],
    values: dict[str, Any],
    current_scope: ResolutionScope,
    symbol_prefix: str,
) -> dict[str, ScopedSymtabs]:
    """Collects the names of variables that each field of this model object provides.

    The return value is a dictionary with a set of symbols for each field,
    "__self__" for the model itself, and "__exports__" for the symbols that it
    exports to its parent in the data model.
    """

    # NOTE: This is not written to be super generic and handle all possible OpenJD models going
    #  forward forever. It handles the subset of the general Pydantic data model that OpenJD is
    #  currently using, and will be extended as we use additional features of Pydantic's data model.

    symbols: dict[str, ScopedSymtabs] = {"__self__": ScopedSymtabs()}

    defs = cls._template_variable_definitions

    if defs.field:
        # defs.field being defined means that the cls defines a template variable.

        # Figure out the name of the variable.
        name: str = ""
        if (def_field_value := values.get(defs.field, None)) is not None:
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

    # Note: cls.__fields__: dict[str, pydantic.v1.fields.ModelField]
    for field_name, field_model in cls.__fields__.items():
        field_value = values.get(field_name, None)
        if field_value is None:
            continue

        if is_literal_type(field_model.type_):
            # Literals cannot define variables, so skip this field.
            continue

        if field_model.shape == pydantic.v1.fields.SHAPE_SINGLETON:
            result = _collect_singleton(field_model, field_value, current_scope, symbol_prefix)
            if result:
                symbols[field_name] = result
        elif field_model.shape == pydantic.v1.fields.SHAPE_LIST:
            # If the shape expects a list, but the value isn't one then we have a validation error.
            # The error will get flagged by subsequent passes of the model validation.
            if not isinstance(field_value, list):
                continue
            assert field_model.sub_fields is not None
            item_model = field_model.sub_fields[0]
            symbols[field_name] = ScopedSymtabs()
            for item in field_value:
                result = _collect_singleton(item_model, item, current_scope, symbol_prefix)
                if result:
                    symbols[field_name].update_self(result)
        elif field_model.shape == pydantic.v1.fields.SHAPE_DICT:
            # dict[] fields can't define symbols.
            continue
        else:
            raise NotImplementedError(
                "You have hit an unimplemented code path. Please report this as a bug."
            )

    # Collect the exported symbols as specified by the metadata
    symbols["__export__"] = ScopedSymtabs()
    for source in cls._template_variable_sources.get("__export__", set()):
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


def _collect_singleton(
    model: pydantic.v1.fields.ModelField,
    value: Any,
    current_scope: ResolutionScope,
    symbol_prefix: str,
) -> Optional[ScopedSymtabs]:
    # Singletons that we recurse in to must all be OpenJDModels, so that means that
    # the value must be a dictionary. hen the provided field value must be a dictionary
    # to have a chance of being valid. If it's not valid, then we just skip it and
    # let subsequent validation passes in the model itself flag those.

    # Note: ModelField.sub_fields is populated if (otherwise it's None):
    #   a) field is a list type => sub_fields has 1 element, and its type is the element type of the list
    #   b) field is a union => sub_fields' elements are the model types in the union
    #   c) field is a discriminated union => sub_fields has 1 element, and it is a ModelField with info about the union.
    if not isinstance(value, dict):
        return None

    if (
        model.discriminator_key is None
        and model.sub_fields is not None
        and len(model.sub_fields) > 1
    ):
        # The only cases like this in our *current* model are the range field of IntTaskParameterDefinitions; they
        # are non-discriminated unions of types that do not contain variable definitions, so we skip them.
        return None

    if isclass(model.type_) and not issubclass(model.type_, OpenJDModel):
        # The field is something like str, int, etc. These can't define variables, so skip it.
        return None

    value_model = _get_model_for_singleton_value(model, value)
    if value_model is None:
        return None
    if not isclass(value_model.type_) or (
        isclass(value_model.type_) and not issubclass(value_model.type_, OpenJDModel)
    ):
        # We only recursively collect from OpenJDModel typed values.
        return None
    if "__export__" not in value_model.type_._template_variable_sources:
        # If the model doesn't export symbols, then there's no point to recursing in to this value.
        return None
    return _collect_variable_definitions(
        value_model.type_,
        value,
        current_scope,
        symbol_prefix,
    )["__export__"]
