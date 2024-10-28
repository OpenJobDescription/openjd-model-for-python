# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any, Union

from pydantic.v1 import ValidationError
from pydantic.v1.error_wrappers import ErrorWrapper

from .._symbol_table import SymbolTable
from .._format_strings import FormatString, FormatStringError
from .._types import OpenJDModel

__all__ = ("instantiate_model",)


def instantiate_model(  # noqa: C901
    model: OpenJDModel,
    symtab: SymbolTable,
    loc: tuple[Union[str, int], ...] = tuple[str](),
    within_field: str = "",
) -> OpenJDModel:
    """This function is for instantiating a Template model into a Job model.

    It does a depth-first traversal through the model, mutating each stage according
    to the instructions given in the model's create-job metadata.

    Args:
        model (OpenJDModel): The model instance to transform.
        symtab (SymbolTable): The symbol table containing fully qualified Job parameter values
            used during the instantiation.
        loc (tuple[Union[str,int], ...], optional): Path to the model. Used for generating contextual errors.
        within_field (str): The name of the field where this model was found during traversal. "" if this
            is the top-level/root model

    Raises:
        ValidationError - If there are any validation errors from the target models.

    Returns:
        OpenJDModel: The transformed model.
    """

    errors = list[ErrorWrapper]()
    instantiated_fields = dict[str, Any]()

    for field_name in model.__fields__.keys():
        target_field_name = field_name
        if field_name in model._job_creation_metadata.rename_fields:
            target_field_name = model._job_creation_metadata.rename_fields[field_name]
        if field_name in model._job_creation_metadata.exclude_fields:
            # The field is marked for being excluded
            continue
        if not hasattr(model, field_name):
            # Field has no value. Set to None and move on.
            instantiated_fields[target_field_name] = None
            continue

        field = getattr(model, field_name)
        instantiated: Any
        # TODO - try/except. Collect errors
        try:
            if isinstance(field, list):
                # Raises: ValidationError
                instantiated = _instantiate_list_field(model, field_name, field, symtab, loc)
            elif isinstance(field, dict):
                # Raises: ValidationError
                instantiated = _instantiate_dict_field(model, field_name, field, symtab, loc)
            else:
                # Raises: ValidationError, FormatStringError
                instantiated = _instantiate_noncollection_value(
                    model, field_name, field, symtab, loc + (field_name,)
                )
            instantiated_fields[target_field_name] = instantiated
        except (ValidationError, FormatStringError) as exc:
            errors.append(ErrorWrapper(exc, loc))

    if errors:
        raise ValidationError(errors, model.__class__)

    if model._job_creation_metadata.adds_fields is not None:
        new_fields = model._job_creation_metadata.adds_fields(within_field, model, symtab)
        instantiated_fields.update(**new_fields)

    try:
        if model._job_creation_metadata.create_as is not None:
            create_as_metadata = model._job_creation_metadata.create_as
            if create_as_metadata.model is not None:
                return create_as_metadata.model(**instantiated_fields)
            elif create_as_metadata.callable is not None:
                create_as_class = create_as_metadata.callable(model)
                return create_as_class(**instantiated_fields)
        return model.__class__(**instantiated_fields)
    except ValidationError as exc:
        raise ValidationError([ErrorWrapper(exc, loc)], model.__class__)


def _instantiate_noncollection_value(
    within_model: OpenJDModel,
    field_name: str,
    value: Any,
    symtab: SymbolTable,
    loc: tuple[Union[str, int], ...],
) -> Any:
    """Instantiate a single value that must not be a collection type (list, dict, etc).

    Arguments:
        within_model (OpenJDModel): The model within which the value is located.
        field_name (str): The name of the field within that model that contains the value.
        value (Any): Value to process.
        symtab (SymbolTable): Symbol table for format string value lookups.
        loc (tuple[Union[str,int], ...]): Path to this value.
    """

    # Note: Let the exceptions fall through to the calling context to handle.
    # If we wrap them into ValidationErrors here, then the locations of errors will
    # be incorrect.

    if isinstance(value, OpenJDModel):
        # Raises: ValidationError
        return instantiate_model(value, symtab, loc, field_name)
    elif (
        isinstance(value, FormatString)
        and field_name in within_model._job_creation_metadata.resolve_fields
    ):
        # Raises: FormatStringError
        return value.resolve(symtab=symtab)

    return value


def _instantiate_list_field(  # noqa: C901
    within_model: OpenJDModel,
    field_name: str,
    value: list[Any],
    symtab: SymbolTable,
    loc: tuple[Union[str, int], ...],
) -> Union[list[Any], dict[str, Any]]:
    """As _instantiate_noncollection_value, but where the value is a list.

    Arguments:
        within_model (OpenJDModel): The model within which the value is located.
        field_name (str): The name of the field within that model that contains the value.
        value (Any): Value to process.
        symtab (SymbolTable): Symbol table for format string value lookups.
        loc (tuple[Union[str,int], ...]): Path to this value.
    """
    errors = list[ErrorWrapper]()
    result: Union[list[Any], dict[str, Any]]
    if field_name in within_model._job_creation_metadata.reshape_field_to_dict:
        key_field = within_model._job_creation_metadata.reshape_field_to_dict[field_name]
        result = dict[str, Any]()
        for idx, item in enumerate(value):
            key = getattr(item, key_field)
            try:
                # Raises: ValidationError, FormatStringError
                result[key] = _instantiate_noncollection_value(
                    within_model,
                    field_name,
                    item,
                    symtab,
                    loc
                    + (
                        field_name,
                        idx,
                    ),
                )
            except (ValidationError, FormatStringError) as exc:
                errors.append(ErrorWrapper(exc, loc))
    else:
        result = list[Any]()
        for idx, item in enumerate(value):
            try:
                # Raises: ValidationError, FormatStringError
                result.append(
                    _instantiate_noncollection_value(
                        within_model,
                        field_name,
                        item,
                        symtab,
                        loc
                        + (
                            field_name,
                            idx,
                        ),
                    )
                )
            except (ValidationError, FormatStringError) as exc:
                errors.append(ErrorWrapper(exc, loc))

    if errors:
        raise ValidationError(errors, within_model.__class__)

    return result


def _instantiate_dict_field(
    within_model: OpenJDModel,
    field_name: str,
    value: dict[str, Any],
    symtab: SymbolTable,
    loc: tuple[Union[str, int], ...],
) -> dict[str, Any]:
    """As _instantiate_noncollection_value, but where the value is a dict.

    Arguments:
        within_model (OpenJDModel): The model within which the value is located.
        field_name (str): The name of the field within that model that contains the value.
        value (Any): Value to process.
        symtab (SymbolTable): Symbol table for format string value lookups.
        loc (tuple[Union[str,int], ...]): Path to this value.
    """
    errors = list[ErrorWrapper]()
    result = dict[str, Any]()
    for key, item in value.items():
        try:
            # Raises: ValidationError, FormatStringError
            result[key] = _instantiate_noncollection_value(
                within_model,
                key,  # We call the dictionary key the field name for adds_fields arguments to be correct
                item,
                symtab,
                loc
                + (
                    field_name,
                    key,
                ),
            )
        except (ValidationError, FormatStringError) as exc:
            errors.append(ErrorWrapper(exc, loc))

    if errors:
        raise ValidationError(errors, within_model.__class__)

    return result
