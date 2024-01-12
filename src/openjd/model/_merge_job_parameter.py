# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from decimal import Decimal
from typing import Any, NamedTuple, Optional, Union, cast

from ._errors import CompatibilityError
from ._parse import parse_model
from ._types import JobParameterDefinition
from .v2023_09 import (
    JobParameterType,
    JobPathParameterDefinition,
    JobStringParameterDefinition,
    JobFloatParameterDefinition,
    JobIntParameterDefinition,
)


class SourcedParamDefinition(NamedTuple):
    source: str
    definition: JobParameterDefinition


class SourcedStringParameterDefinition(NamedTuple):
    source: str
    definition: JobStringParameterDefinition


class SourcedPathParameterDefinition(NamedTuple):
    source: str
    definition: JobPathParameterDefinition


class SourcedIntParameterDefinition(NamedTuple):
    source: str
    definition: JobIntParameterDefinition


class SourcedFloatParameterDefinition(NamedTuple):
    source: str
    definition: JobFloatParameterDefinition


def merge_job_parameter_definitions_for_one(
    params: list[SourcedParamDefinition],
) -> JobParameterDefinition:
    """Given an ordered list of job parameter definitions of the *same* job parameter, this merges the definitions into a single
    job parameter definition. In the act of doing the merger, this performs checks to ensure that the job parameter definitions are
    compatible with one another.

    Returns (JobParameterDefinition):
        The result of merging all of the given definitions in to a single definition.

    Raises:
        CompatibilityError -- if the given definitions are not compatible in some way. The error's message is a newline-separated
           string containing the compatibility errors that were discovered.
    """

    merged_properties = dict[str, Any]()

    # Protect from programmer error; all parameters need to have the same name.
    name = params[-1].definition.name
    if any(param.definition.name != name for param in params):
        raise CompatibilityError("Parameter names differ. Please report this as a bug.")
    merged_properties["name"] = name

    # The two parameters must be from compatible SchemaVersions
    # This is the same schema version right now, but may be relaxed as new versions are added.
    schema_version = params[-1].definition.version
    if any(param.definition.version != schema_version for param in params):
        raise CompatibilityError("Parameter model versions differ.")

    # All parameters must be the same parameter type.
    param_type = params[-1].definition.type
    for param in params:
        if param.definition.type != param_type:
            raise CompatibilityError(
                f"Parameter type in '{param.source}' differs from expected type '{str(param_type.value)}'"
            )
    merged_properties["type"] = param_type

    # Default value is the last defined one in the list.
    default_values = [
        param.definition.default for param in params if param.definition.default is not None
    ]
    if default_values:
        merged_properties["default"] = default_values[-1]

    errors = list[str]()

    # The set of allowedValues for a parameter definition must be a subset as we proceed down the list.
    av_ret, err = _merge_allowed_values(params)
    if av_ret is not None:
        merged_properties["allowedValues"] = av_ret
    if err:
        errors.extend(err)

    if param_type == JobParameterType.PATH:
        ret, err = _merge_path_param_types(params)
        if ret:
            merged_properties.update(**ret)
        if err:
            errors.extend(err)

    if param_type in (JobParameterType.STRING, JobParameterType.PATH):
        ret, err = _merge_string_kind_param_constraints(params)
        if ret:
            merged_properties.update(**ret)
        if err:
            errors.extend(err)
    else:
        ret, err = _merge_number_kind_param_constraints(params)
        if ret:
            merged_properties.update(**ret)
        if err:
            errors.extend(err)

    if errors:
        raise CompatibilityError("\n".join(errors))

    return cast(
        JobParameterDefinition,
        parse_model(model=params[0].definition.__class__, obj=merged_properties),
    )


def _merge_allowed_values(
    params: list[SourcedParamDefinition],
) -> tuple[Optional[Union[list[str], list[int], list[Decimal]]], list[str]]:
    errors = list[str]()
    return_value: Optional[Union[set[str], set[int], set[Decimal]]] = None

    for param in params:
        definition = param.definition
        if not definition.allowedValues:
            # If this definition doesn't have a set of allowedValues, then it's unconstrained.
            # Thus, it's happy with any values and we can move on to the next one.
            continue
        if not return_value:
            return_value = cast(
                Union[set[str], set[int], set[Decimal]], set(definition.allowedValues)
            )
        else:
            param_as_set = cast(
                Union[set[str], set[int], set[Decimal]], set(definition.allowedValues)
            )
            return_value.intersection_update(param_as_set)

    if return_value is not None and not return_value:
        errors.append(
            "The intersection of all allowedValues is empty. There are no values that can satisfy all constraints."
        )

    return (
        cast(Union[list[str], list[int], list[Decimal]], sorted(return_value))
        if return_value
        else None,
        errors,
    )


def _merge_path_param_types(
    params: list[SourcedParamDefinition],
) -> tuple[dict[str, Any], list[str]]:
    errors = list[str]()
    return_value = dict[str, Any]()

    casted_params = cast(list[SourcedPathParameterDefinition], params)
    # objectType & dataFlow must be identical in all templates, if provided.
    object_types = set(
        [
            # objectType's default value is DIRECTORY if it's not provided.
            param.definition.objectType if param.definition.objectType is not None else "DIRECTORY"
            for param in casted_params
        ]
    )
    data_flows = set(
        [
            param.definition.dataFlow
            for param in casted_params
            if param.definition.dataFlow is not None
        ]
    )
    if len(object_types) > 1:
        errors.append("Parameter objectTypes differ.")
    if len(data_flows) > 1:
        errors.append("Parameter dataFlows differ.")
    try:
        defined_object_type = next(
            iter(
                param.definition.objectType
                for param in casted_params
                if param.definition.objectType is not None
            )
        )
        return_value["objectType"] = defined_object_type
    except StopIteration:
        # There were no objectTypes defined.
        pass
    if data_flows:
        return_value["dataFlow"] = list(data_flows)[0]

    return return_value, errors


def _merge_string_kind_param_constraints(
    params: list[SourcedParamDefinition],
) -> tuple[dict[str, Any], list[str]]:
    errors = list[str]()
    return_value = dict[str, Any]()

    casted_params = cast(
        Union[list[SourcedStringParameterDefinition], list[SourcedPathParameterDefinition]], params
    )
    # Check common constraints for string-valued parameteter types.
    #  minLength -- cannot get smaller as we iterate through the list
    #  maxLength -- cannot get bigger as we iterate through the list
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    for param in casted_params:
        definition = param.definition
        if definition.minLength is not None:
            if min_length is None:
                min_length = definition.minLength
            else:
                min_length = max(min_length, definition.minLength)
        if definition.maxLength is not None:
            if max_length is None:
                max_length = definition.maxLength
            else:
                max_length = min(max_length, definition.maxLength)

    if min_length is not None:
        return_value["minLength"] = min_length
    if max_length is not None:
        return_value["maxLength"] = max_length

    if min_length is not None and max_length is not None and min_length > max_length:
        errors.append(
            f"Merged constraint minLength ({min_length}) <= maxLength ({max_length}) is not satisfyable."
        )

    return return_value, errors


def _merge_number_kind_param_constraints(
    params: list[SourcedParamDefinition],
) -> tuple[dict[str, Any], list[str]]:
    errors = list[str]()
    return_value = dict[str, Any]()

    casted_params = cast(
        Union[list[SourcedIntParameterDefinition], list[SourcedFloatParameterDefinition]], params
    )
    # Check common constraints for number-valued parameteter types.
    #  minValue -- cannot get smaller as we iterate through the list
    #  maxValue -- cannot get bigger as we iterate through the list
    min_value: Optional[Union[int, Decimal]] = None
    max_value: Optional[Union[int, Decimal]] = None
    for param in casted_params:
        definition = param.definition
        if definition.minValue is not None:
            if min_value is None:
                min_value = definition.minValue
            else:
                min_value = max(min_value, definition.minValue)
        if definition.maxValue is not None:
            if max_value is None:
                max_value = definition.maxValue
            else:
                max_value = min(max_value, definition.maxValue)

    if min_value is not None:
        return_value["minValue"] = min_value
    if max_value is not None:
        return_value["maxValue"] = max_value

    if min_value is not None and max_value is not None and min_value > max_value:
        errors.append(
            f"Merged constraint minValue ({min_value}) <= maxValue ({max_value}) is not satisfyable."
        )

    return return_value, errors
