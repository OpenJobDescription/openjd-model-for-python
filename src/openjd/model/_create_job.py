# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from pydantic import ValidationError

from ._errors import DecodeValidationError
from ._symbol_table import SymbolTable
from ._internal import instantiate_model
from ._types import (
    Job,
    JobParameterInputValues,
    JobParameterValues,
    JobTemplate,
    ParameterValue,
    ParameterValueType,
    SchemaVersion,
)
from ._convert_pydantic_error import pydantic_validationerrors_to_str, ErrorDict

if TYPE_CHECKING:
    # Avoiding a circular import that occurs when trying to import FormatString
    from .v2023_09 import JobTemplate as JobTemplate_2023_09


__all__ = ("preprocess_job_parameters",)


# =======================================================================
# ================ Preprocessing Job Parameters =========================
# =======================================================================


def _collect_available_parameter_names(job_template: JobTemplate) -> set[str]:
    # job_template.parameterDefinitions is a list[JobParameterDefinitionList]
    return (
        set(param.name for param in job_template.parameterDefinitions)
        if job_template.parameterDefinitions
        else set()
    )


def _collect_extra_job_parameter_names(
    job_template: JobTemplate, job_parameter_values: JobParameterInputValues
) -> set[str]:
    # Verify that job parameters are provided if the template requires them
    available_parameters: set[str] = _collect_available_parameter_names(job_template)
    return set(job_parameter_values).difference(available_parameters)


def _collect_missing_job_parameter_names(
    job_template: JobTemplate, job_parameter_values: JobParameterValues
) -> set[str]:
    available_parameters: set[str] = _collect_available_parameter_names(job_template)
    return available_parameters.difference(set(job_parameter_values.keys()))


def _collect_defaults_2023_09(
    job_template: "JobTemplate_2023_09", job_parameter_values: JobParameterInputValues
) -> JobParameterValues:
    # For the type checker
    assert job_template.parameterDefinitions is not None

    return_value: JobParameterValues = dict()
    # Collect defaults
    for param in job_template.parameterDefinitions:
        if param.name not in job_parameter_values:
            if param.default is not None:
                return_value[param.name] = ParameterValue(
                    type=ParameterValueType(param.type), value=str(param.default)
                )
        else:
            # Check the parameter against the constraints
            value = job_parameter_values[param.name]
            return_value[param.name] = ParameterValue(
                type=ParameterValueType(param.type), value=str(value)
            )

    return return_value


def _check_2023_09(
    job_template: "JobTemplate_2023_09", job_parameter_values: JobParameterValues
) -> None:
    # For the type checker
    assert job_template.parameterDefinitions is not None

    errors: list[str] = []
    # Check values
    for param in job_template.parameterDefinitions:
        if param.name in job_parameter_values:
            param_value = job_parameter_values[param.name]
            try:
                param._check_constraints(param_value.value)
            except ValueError as err:
                errors.append(str(err))

    if errors:
        raise ValueError(", ".join(errors))


def preprocess_job_parameters(
    *, job_template: JobTemplate, job_parameter_values: JobParameterInputValues
) -> JobParameterValues:
    """Preprocess a collection of job parameter values. Must be used prior to
    instantiating a Job Template into a Job.
    This:
    1. Errors if job parameter values are defined that are not defined in the template.
    2. Errors if there are job parameters defined in the job template that do not have default
        values, and do not have defined job parameter values.
    3. Adds values to the job parameter values for any missing job parameters for which
        the job template defines default values.
    4. Errors if any of the provided job parameter values do not meet the constraints
        for the parameter defined in the job template.

    Arguments:
        job_template (JobTemplate) -- A Job Template to check the job parameter values against.
        job_parameter_values (JobParameterValues) -- Mapping of Job Parameter names to values.
            e.g. { "Foo": 12 } if you have a Job Parameter named "Foo"

    Returns:
        A copy of job_parameter_values, but with added values for any missing job parameters
        that have default values defined in the Job Template.

    Raises:
        ValueError - If any errors are detected with the given job parameter values.
    """
    if job_template.version not in (SchemaVersion.v2023_09,):
        raise NotImplementedError(f"Not implemented for schema version {job_template.version}")

    return_value: JobParameterValues = dict()
    errors: list[str] = []

    extra_defined_parameters = _collect_extra_job_parameter_names(
        job_template, job_parameter_values
    )
    if extra_defined_parameters:
        extra_list = ", ".join(extra_defined_parameters)
        errors.append(
            f"Job parameter values provided for parameters that are not defined in the template: {extra_list}"
        )
    if job_template.parameterDefinitions:
        # Set of all required, but undefined, job parameter values
        try:
            if job_template.version == SchemaVersion.v2023_09:
                return_value = _collect_defaults_2023_09(job_template, job_parameter_values)
                _check_2023_09(job_template, return_value)
            else:
                raise NotImplementedError(
                    f"Not implemented for schema version {job_template.version}"
                )
        except ValueError as err:
            errors.append(str(err))
        missing = _collect_missing_job_parameter_names(job_template, return_value)

        if missing:
            missing_list = ", ".join(missing)
            errors.append(f"Values missing for required job parameters: {missing_list}")

    if errors:
        raise ValueError("\n".join(errors))

    return return_value


# =======================================================================
# ================ Creating a Job from a Job Template ===================
# =======================================================================


def create_job(*, job_template: JobTemplate, job_parameter_values: JobParameterValues) -> Job:
    """This function will create a job from a given Job Template and set of values for
    Job Parameters. Minimally, values must be provided for Job Parameters that do not have
    default values defined in the template.

    This will run a check of all given job parameters via preprocess_job_parameters() before
    creating the job from the template.

    Arguments:
        job_template (JobTemplate) -- A Job Template to check the job parameter values against.
        job_parameter_values (JobParameterValues) -- Mapping of Job Parameter names to values.

    Raises:
        DecodeValidationError

    Returns:
        Job: The job generated.
    """

    # Raises: ValueError
    try:
        # Raises: ValueError
        all_job_parameter_values = preprocess_job_parameters(
            job_template=job_template,
            job_parameter_values={
                name: param.value for name, param in job_parameter_values.items()
            },
        )
    except ValueError as exc:
        raise DecodeValidationError(str(exc))

    # Build out the symbol table for instantiating the Job.
    # We just prefix all job parameter names with the appropriate prefix.
    symtab = SymbolTable()
    if job_template.specificationVersion == SchemaVersion.v2023_09:
        from .v2023_09 import ValueReferenceConstants as ValueReferenceConstants_2023_09

        for name, param in all_job_parameter_values.items():
            if param.type != "PATH":
                symtab[
                    f"{ValueReferenceConstants_2023_09.JOB_PARAMETER_PREFIX.value}.{name}"
                ] = all_job_parameter_values[name].value
            symtab[
                f"{ValueReferenceConstants_2023_09.JOB_PARAMETER_RAWPREFIX.value}.{name}"
            ] = all_job_parameter_values[name].value
    else:
        raise NotImplementedError(
            f"Spec version {job_template.specificationVersion} not implemented."
        )

    # Create the job
    try:
        job = instantiate_model(job_template, symtab)
    except ValidationError as exc:
        raise DecodeValidationError(
            pydantic_validationerrors_to_str(
                job_template.__class__, cast(list[ErrorDict], exc.errors())
            )
        )

    return cast(Job, job)
