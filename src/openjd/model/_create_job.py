# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import json
from os.path import normpath
from pathlib import Path
from typing import Any, Optional, cast

from pydantic import ValidationError

from ._errors import CompatibilityError, DecodeValidationError
from ._format_strings import FormatStringError
from ._symbol_table import SymbolTable
from ._internal import instantiate_model
from ._merge_job_parameter import merge_job_parameter_definitions
from ._types import (
    EnvironmentTemplate,
    Job,
    JobParameterDefinition,
    JobParameterInputValues,
    JobParameterValues,
    JobTemplate,
    ParameterValue,
    ParameterValueType,
    SpecificationRevision,
    TemplateSpecificationVersion,
)
from ._convert_pydantic_error import pydantic_validationerrors_to_str

__all__ = ("preprocess_job_parameters",)

# The original scalar job-parameter type names whose values are carried as
# strings through preprocessing. EXPR-extension types (BOOL, RANGE_EXPR, and
# the LIST[*] variants) are carried natively instead so the typed EXPR symbol
# table can coerce them.
_LEGACY_SCALAR_TYPE_NAMES = frozenset({"STRING", "INT", "FLOAT", "PATH"})


def _coerce_expr_param_value(param_type_name: str, value: Any) -> Any:
    """Coerce a SUBMITTED string value for an EXPR-typed job parameter to its
    native form, mirroring openjd-rs's ``coerce_from_str``
    (job/create_job/parameters.rs): BOOL accepts the spec's boolean strings,
    and LIST[*] values may be supplied as JSON — the public input type is
    ``dict[str, str]``, so string forms must be accepted. Native values
    (bool, list) pass through unchanged.

    Raises:
        ValueError: If a string value cannot be coerced (message shapes match
            the Rust implementation).
    """
    if param_type_name == "BOOL" and isinstance(value, str):
        lowered = value.lower()
        if lowered in ("true", "yes", "on", "1"):
            return True
        if lowered in ("false", "no", "off", "0"):
            return False
        raise ValueError(
            f"Value '{value}' is not a valid boolean. Accepted: true/false, 1/0, yes/no, on/off."
        )
    if param_type_name.startswith("LIST") and isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            raise ValueError(f"Value '{value}' is not valid JSON for a list parameter.")
        if not isinstance(parsed, list):
            raise ValueError(f"Value '{value}' is not valid JSON for a list parameter.")
        return parsed
    return value


def _is_uri(value: str) -> bool:
    """Whether ``value`` is a URI (``scheme://...`` with an RFC 3986 scheme).
    Mirrors openjd-rs's ``uri_path::is_uri``: the scheme must start with an
    ASCII letter and contain only ASCII alphanumerics, ``+``, ``.``, or ``-``.
    """
    scheme_end = value.find("://")
    if scheme_end <= 0:
        return False
    scheme = value[:scheme_end]
    if not scheme[0].isascii() or not scheme[0].isalpha():
        return False
    return all(c.isascii() and (c.isalnum() or c in "+.-") for c in scheme)


# =======================================================================
# ================ Preprocessing Job Parameters =========================
# =======================================================================


def _collect_available_parameter_names(
    job_parameter_definitions: list[JobParameterDefinition],
) -> set[str]:
    return set(param.name for param in job_parameter_definitions)


def _collect_extra_job_parameter_names(
    job_parameter_definitions: list[JobParameterDefinition],
    job_parameter_values: JobParameterInputValues,
) -> set[str]:
    # Verify that job parameters are provided if the template requires them
    available_parameters: set[str] = _collect_available_parameter_names(job_parameter_definitions)
    return set(job_parameter_values).difference(available_parameters)


def _collect_missing_job_parameter_names(
    job_parameter_definitions: list[JobParameterDefinition],
    job_parameter_values: JobParameterValues,
) -> set[str]:
    available_parameters: set[str] = _collect_available_parameter_names(job_parameter_definitions)
    return available_parameters.difference(set(job_parameter_values.keys()))


def _resolve_path_default_2023_09(
    param_name: str,
    default: str,
    *,
    job_template_dir: Path,
    allow_job_template_dir_walk_up: bool,
    allow_uri_path_values: bool,
) -> str:
    """Resolve a PATH parameter's default value string.

    - RFC 0006 (EXPR): URI-form defaults ("s3://...") are preserved verbatim —
      they are not filesystem paths, so the template-dir join and walk-up
      enforcement do not apply. Mirrors openjd-rs's preprocess_job_parameters
      URI handling.
    - Otherwise the default is made relative to ``job_template_dir``, with the
      ``allow_job_template_dir_walk_up`` request enforced.

    Raises:
        ValueError: If the default violates the walk-up restrictions.
    """
    if default == "":
        return default
    if allow_uri_path_values and _is_uri(default):
        return default
    default_path = Path(default)
    if default_path.is_absolute():
        # While we could permit absolute paths within the job template dir,
        # we choose not to do so. A job template using absolute paths as path defaults
        # within the template's directory isn't portable and it's easier to make
        # them relative early in the creating a job.
        if not allow_job_template_dir_walk_up:
            raise ValueError(
                f"The default value of PATH parameter {param_name} is an absolute path. Default paths must be relative, and are joined to the job template's directory."
            )
    elif job_template_dir.is_absolute():
        # Note: Using os.path.normpath instead of Path.resolve, since
        #       Path.resolve makes changes to the path unexpected by users,
        #       like switching Windows drive letters to UNC paths.
        default_path = Path(normpath(job_template_dir / default_path))
        if not allow_job_template_dir_walk_up and not default_path.is_relative_to(job_template_dir):
            raise ValueError(
                f"The default value of PATH parameter {param_name} references a path outside of the template directory. Walking up from the template directory is not permitted."
            )
        default = str(default_path)
    return default


def _collect_defaults_2023_09(
    job_parameter_definitions: list[JobParameterDefinition],
    job_parameter_values: JobParameterInputValues,
    job_template_dir: Path,
    current_working_dir: Path,
    allow_job_template_dir_walk_up: bool,
    allow_uri_path_values: bool = False,
) -> JobParameterValues:
    if not allow_job_template_dir_walk_up and not job_template_dir.is_absolute():
        raise ValueError(
            f"The value supplied for the job template dir, {job_template_dir}, is not an absolute path. It must be absolute to enforce that PATH parameter defaults are always inside the job template dir."
        )

    return_value: JobParameterValues = dict[str, ParameterValue]()
    # Collect defaults
    for param in job_parameter_definitions:
        is_legacy_scalar = param.type.name in _LEGACY_SCALAR_TYPE_NAMES
        if param.name not in job_parameter_values:
            if param.default is not None:
                if not is_legacy_scalar:
                    # EXPR types (BOOL / RANGE_EXPR / LIST[*]): carry the native
                    # default through so the typed symbol-table builder can
                    # coerce it. The PATH-relative-default handling below only
                    # applies to the scalar PATH type.
                    return_value[param.name] = ParameterValue(
                        type=ParameterValueType(param.type), value=param.default
                    )
                    continue
                default = str(param.default)
                if param.type.name == "PATH":
                    default = _resolve_path_default_2023_09(
                        param.name,
                        default,
                        job_template_dir=job_template_dir,
                        allow_job_template_dir_walk_up=allow_job_template_dir_walk_up,
                        allow_uri_path_values=allow_uri_path_values,
                    )
                return_value[param.name] = ParameterValue(
                    type=ParameterValueType(param.type), value=default
                )
        else:
            # Check the parameter against the constraints
            value = job_parameter_values[param.name]
            if not is_legacy_scalar:
                # EXPR types: coerce submitted string forms (BOOL strings,
                # JSON lists — the public input type is dict[str, str]) to
                # their native values, then carry through; mirrors
                # openjd-rs's coerce_from_str.
                # Raises ValueError (collected by the caller) on bad input.
                value = _coerce_expr_param_value(param.type.name, value)
                return_value[param.name] = ParameterValue(
                    type=ParameterValueType(param.type), value=value
                )
                continue
            # Join any provided relative PATH parameter value with the current_working_directory
            # (except the empty value "" and, under EXPR, URI values which are preserved verbatim)
            if (
                param.type.name == "PATH"
                and value != ""
                and not (allow_uri_path_values and _is_uri(str(value)))
                and not Path(value).is_absolute()
            ):
                value = str(current_working_dir / value)
            return_value[param.name] = ParameterValue(
                type=ParameterValueType(param.type), value=str(value)
            )

    return return_value


def _check_2023_09(
    job_parameter_definitions: list[JobParameterDefinition],
    job_parameter_values: JobParameterValues,
) -> None:
    errors = list[str]()
    # Check values
    for param in job_parameter_definitions:
        if param.name in job_parameter_values:
            param_value = job_parameter_values[param.name]
            # The EXPR-extension LIST[*]/RANGE_EXPR definitions don't implement
            # _check_constraints (BOOL and the original scalars do). Their
            # template defaults are validated at decode time, and their values
            # are type-checked when coerced into the typed EXPR symbol table, so
            # skip the create-time constraint check when it isn't available.
            check_constraints = getattr(param, "_check_constraints", None)
            if check_constraints is None:
                continue
            try:
                check_constraints(param_value.value)
            except ValueError as err:
                errors.append(str(err))

    if errors:
        raise ValueError("\n".join(errors))


def preprocess_job_parameters(
    *,
    job_template: JobTemplate,
    job_parameter_values: JobParameterInputValues,
    job_template_dir: Path,
    current_working_dir: Path,
    allow_job_template_dir_walk_up: bool = False,
    environment_templates: Optional[list[EnvironmentTemplate]] = None,
) -> JobParameterValues:
    """Preprocess a collection of job parameter values. Must be used prior to
    instantiating a Job Template into a Job.

    By default, this function performs client-side validation of PATH parameters to
    ensure that path references in the job template, either relative or absolute, cannot
    escape the directory the template is in. While doing so, it transforms relative paths
    into absolute paths. This is the right default for use in a client job submission context,
    for example with access to the workstation's file system.

    In a server context that no longer can access the workstation's file system, you
    can pass Path() as the job template and current working directories and True
    as allow_job_template_dir_walk_up. With these options, the PATH parameter values will
    remain untouched, and no validation of paths escaping the job template directory will
    be performed.

    This function does the following:
    1. Errors if job parameter values are defined that are not defined in the template.
    2. Errors if there are job parameters defined in the job template that do not have default
        values, and do not have defined job parameter values.
    3. Adds values to the job parameter values for any missing job parameters for which
        the job template defines default values.
    4. Errors if any of the provided job parameter values do not meet the constraints
        for the parameter defined in the job template.
    5. For any PATH parameter from the job template with a default value that is relative,
        makes it absolute by joining with `job_template_dir`.
    6. Errors if `allow_job_template_dir_walk_up` is False, and any PATH parameter default
        is an absolute path or resolves to a path outside of `job_template_dir`.
    7. For any PATH parameter from the `job_parameter_values` with a value that is relative,
        makes it absolute by joining with `current_working_dir`.

    Arguments:
        job_template (JobTemplate) -- A Job Template to check the job parameter values against.
        job_parameter_values (JobParameterValues) -- Mapping of Job Parameter names to values.
            e.g. { "Foo": 12 } if you have a Job Parameter named "Foo"
        job_template_dir (Path) -- The path, on the local file system, where the job template
            lives. Any PATH parameter's default with a relative path value
            is joined to this path.
        current_working_dir (Path) -- The current working directory to use. Any input
            PATH job parameter with a relative path value is joined to this path. These are input
            from the user submitting the job, and any absolute or relative paths are permitted.
        allow_job_template_dir_walk_up (bool) -- Affects the validation of PATH parameter defaults.
            If True, allows absolute paths and relative paths with ".." that walk up outside
            the job template dir. If False, disallows these cases.
        environment_templates (Optional[list[EnvironmentTemplate]]) -- An ordered list of the
            externally defined Environment Templates that are applied to the Job.

    Returns:
        A copy of job_parameter_values, but with added values for any missing job parameters
        that have default values defined in the Job Template.

    Raises:
        ValueError - If any errors are detected with the given job parameter values.
    """
    if job_template.revision not in (SpecificationRevision.v2023_09,):
        raise NotImplementedError(
            f"Not implemented for Open Job Description Job Templates from revision {str(job_template.revision.value)}"
        )
    if environment_templates and any(
        env.revision not in (SpecificationRevision.v2023_09,) for env in environment_templates
    ):
        raise NotImplementedError(
            f"Not implemented for Open Job Description Environment Templates from revisions other than {str(SpecificationRevision.v2023_09.value)}"
        )

    return_value: JobParameterValues = dict[str, ParameterValue]()
    errors = list[str]()

    parameterDefinitions: Optional[list[JobParameterDefinition]] = None
    try:
        parameterDefinitions = merge_job_parameter_definitions(
            job_template=job_template, environment_templates=environment_templates
        )
    except CompatibilityError as e:
        # There's no point in continuing if the job parameter definitions are not compatible.
        raise ValueError(str(e))

    extra_defined_parameters = _collect_extra_job_parameter_names(
        parameterDefinitions, job_parameter_values
    )
    if extra_defined_parameters:
        extra_list = ", ".join(sorted(extra_defined_parameters))
        errors.append(
            f"Job parameter values provided for parameters that are not defined in the template: {extra_list}"
        )
    if parameterDefinitions:
        # Set of all required, but undefined, job parameter values
        try:
            if job_template.revision == SpecificationRevision.v2023_09:
                return_value = _collect_defaults_2023_09(
                    parameterDefinitions,
                    job_parameter_values,
                    job_template_dir,
                    current_working_dir,
                    allow_job_template_dir_walk_up,
                    # RFC 0006: URI-form PATH values are only meaningful with
                    # the EXPR extension (path ops and mapping understand
                    # URIs). Matches the openjd-rs CLI, which enables URI
                    # path values for EXPR templates.
                    allow_uri_path_values="EXPR"
                    in (getattr(job_template, "extensions", None) or []),
                )
                _check_2023_09(parameterDefinitions, return_value)
            else:
                raise NotImplementedError(
                    f"Not implemented for schema version {str(job_template.revision.value)}"
                )
        except ValueError as err:
            errors.append(str(err))
        missing = _collect_missing_job_parameter_names(parameterDefinitions, return_value)

        if missing:
            missing_list = ", ".join(sorted(missing))
            errors.append(f"Values missing for required job parameters: {missing_list}")

    if errors:
        raise ValueError("\n".join(errors))

    return return_value


# =======================================================================
# ================ Creating a Job from a Job Template ===================
# =======================================================================


def create_job(
    *,
    job_template: JobTemplate,
    job_parameter_values: JobParameterValues,
    environment_templates: Optional[list[EnvironmentTemplate]] = None,
) -> Job:
    """This function will create a job from a given Job Template and set of values for
    Job Parameters. Minimally, values must be provided for Job Parameters that do not have
    default values defined in the template.

    This will run a check of all given job parameters via preprocess_job_parameters() before
    creating the job from the template.

    Arguments:
        job_template (JobTemplate) -- A Job Template to check the job parameter values against.
        job_parameter_values (JobParameterValues) -- Mapping of Job Parameter names to values.
        environment_templates (Optional[list[EnvironmentTemplate]]) -- An ordered list of the
            externally defined Environment Templates that are applied to the Job.

    Raises:
        DecodeValidationError

    Returns:
        Job: The job generated.
    """

    # Raises: ValueError
    try:
        # Raises: ValueError

        # Because this is validating the parameter values without the original job template
        # dir and current working dir, this call passes Path() for job_template_dir
        # and current_working_dir, and True for allow_job_template_dir_walkup.
        all_job_parameter_values = preprocess_job_parameters(
            job_template=job_template,
            job_parameter_values={
                name: param.value for name, param in job_parameter_values.items()
            },
            job_template_dir=Path(),
            current_working_dir=Path(),
            allow_job_template_dir_walk_up=True,
            environment_templates=environment_templates,
        )
    except ValueError as exc:
        raise DecodeValidationError(str(exc))

    # Build out the symbol table for instantiating the Job.
    # We just prefix all job parameter names with the appropriate prefix.
    symtab = SymbolTable()
    if job_template.specificationVersion == TemplateSpecificationVersion.JOBTEMPLATE_v2023_09:
        from .v2023_09 import ValueReferenceConstants as ValueReferenceConstants_2023_09

        # Record each parameter's OpenJD type so the typed symbol-table
        # builder coerces its (stringly carried) value to the right ExprType
        # during EXPR expression evaluation — matching openjd-rs, whose
        # create_job symbol table carries typed ExprValues for every
        # parameter (an INT param is an int, so `{{ Param.X + 3 }}` works).
        # STRING needs no coercion. Path-typed parameters (PATH and
        # LIST[PATH]) have no template-scope Param.* symbol at all: the
        # processed value (with path mapping) only exists at host/session
        # scope, so openjd-rs excludes Param.* for both here and seeds only
        # RawParam.* — as a plain string for PATH and a list[string] for
        # LIST[PATH] (RFC 0005 "Job Parameter Types"; parameters.rs
        # build_symbol_table).
        # The typing only affects the EXPR evaluation path; non-EXPR
        # templates keep their existing string-based interpolation.
        expr_types: dict[str, str] = {}
        for name, param in all_job_parameter_values.items():
            prefix = ValueReferenceConstants_2023_09.JOB_PARAMETER_PREFIX.value
            raw_prefix = ValueReferenceConstants_2023_09.JOB_PARAMETER_RAWPREFIX.value
            if param.type.name not in ("PATH", "LIST_PATH"):
                symtab[f"{prefix}.{name}"] = all_job_parameter_values[name].value
                if param.type.name != "STRING":
                    expr_types[f"{prefix}.{name}"] = param.type.value
            symtab[f"{raw_prefix}.{name}"] = all_job_parameter_values[name].value
            if param.type.name == "LIST_PATH":
                expr_types[f"{raw_prefix}.{name}"] = ParameterValueType.LIST_STRING.value
            elif param.type.name not in ("STRING", "PATH"):
                expr_types[f"{raw_prefix}.{name}"] = param.type.value
        symtab.expr_types.update(expr_types)
        # RFC 0007 §7.3.1 (EXPR): Job.Name is the job's resolved name,
        # available to the job's steps and environments. Seeded before
        # instantiation so step fields (including step-level `let` bindings)
        # can reference it — mirroring openjd-rs's instantiate_job, which
        # resolves the name first and seeds it into the symbol table.
        if "EXPR" in (getattr(job_template, "extensions", None) or []):
            try:
                symtab["Job.Name"] = job_template.name.resolve(symtab=symtab)
            except FormatStringError as exc:
                raise DecodeValidationError(f"Failed to resolve the job's name: {exc}")
    else:
        raise NotImplementedError(
            f"Spec version {job_template.specificationVersion} not implemented."
        )

    # Create the job
    try:
        job = instantiate_model(job_template, symtab)
    except ValidationError as exc:
        raise DecodeValidationError(
            pydantic_validationerrors_to_str(job_template.__class__, exc.errors())
        )

    return cast(Job, job)
