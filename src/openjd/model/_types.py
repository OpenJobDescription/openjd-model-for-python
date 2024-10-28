# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Optional, Type, Union

from pydantic.v1 import BaseModel, Extra

from ._symbol_table import SymbolTable

if TYPE_CHECKING:
    # Avoiding a circular import
    from .v2023_09 import EnvironmentTemplate as EnvironmentTemplate_2023_09
    from .v2023_09 import Job as Job_2023_09
    from .v2023_09 import JobTemplate as JobTemplate_2023_09
    from .v2023_09 import Step as Step_2023_09
    from .v2023_09 import StepParameterSpace as StepParameterSpace_2023_09
    from .v2023_09 import (
        JobIntParameterDefinition,
        JobFloatParameterDefinition,
        JobStringParameterDefinition,
        JobPathParameterDefinition,
    )

    EnvironmentTemplate = EnvironmentTemplate_2023_09
    JobTemplate = JobTemplate_2023_09
    Job = Job_2023_09
    JobParameterDefinition = Union[
        JobIntParameterDefinition,
        JobFloatParameterDefinition,
        JobStringParameterDefinition,
        JobPathParameterDefinition,
    ]
    StepParameterSpace = StepParameterSpace_2023_09
    Step = Step_2023_09
else:
    EnvironmentTemplate = Any
    JobTemplate = Any
    Job = Any
    JobParameterDefinition = Any
    StepParameterSpace = Any
    Step = Any

__all__ = (
    "DefinesTemplateVariables",
    "EnvironmentTemplate",
    "Job",
    "JobParameterDefinition",
    "JobParameterInterface",
    "JobParameterValues",
    "JobTemplate",
    "OpenJDModel",
    "ParameterValue",
    "ParameterValueType",
    "SpecificationRevision",
    "Step",
    "StepParameterSpace",
    "TaskParameterSet",
    "TemplateSpecificationVersion",
)


if sys.version_info >= (3, 10):
    dataclass_kwargs = {"slots": True, "kw_only": True}
else:
    dataclass_kwargs = dict[str, Any]()


class ParameterValueType(str, Enum):
    STRING = "STRING"
    INT = "INT"
    FLOAT = "FLOAT"
    PATH = "PATH"


@dataclass(frozen=True, **dataclass_kwargs)
class ParameterValue:
    type: ParameterValueType
    # All values are strings regardless of types.
    # We typecast as needed during processing based on the type
    # of the parameter value.
    value: str


TaskParameterSet = dict[str, ParameterValue]
JobParameterInputValues = dict[str, str]
JobParameterValues = dict[str, ParameterValue]


class TemplateSpecificationVersion(str, Enum):
    """Enumerant of all Open Job Description Specification version strings for
    templates. This is generally the value of a template's 'specificationVersion'
    field.

    Special values:
      UNDEFINED -- Purely for internal testing.

    Versions:
      v2023_09 -- Job Template for spec version 2023-09.
      ENVIRONMENT_v2023_09 -- Environment Template for spec version 2023-09.
    """

    UNDEFINED = "UNDEFINED"
    JOBTEMPLATE_v2023_09 = "jobtemplate-2023-09"
    ENVIRONMENT_v2023_09 = "environment-2023-09"
    # Future:
    # JOBTEMPLATE_EXPERIMENTAL = "jobtemplate-experimental"
    # ENVIRONMENT_EXPERIMENTAL = "environment-experimental"

    @staticmethod
    def job_template_versions() -> tuple[TemplateSpecificationVersion, ...]:
        return (TemplateSpecificationVersion.JOBTEMPLATE_v2023_09,)

    @staticmethod
    def is_job_template(version: TemplateSpecificationVersion) -> bool:
        return version in TemplateSpecificationVersion.job_template_versions()

    @staticmethod
    def environment_template_versions() -> tuple[TemplateSpecificationVersion, ...]:
        return (TemplateSpecificationVersion.ENVIRONMENT_v2023_09,)

    @staticmethod
    def is_environment_template(version: TemplateSpecificationVersion) -> bool:
        return version in TemplateSpecificationVersion.environment_template_versions()


class SpecificationRevision(str, Enum):
    """Enumerant of all published Open Job Description revisions. This appears as the value
    of the 'revision' property in all model instances.

    Special values:
      UNDEFINED -- Purely for internal testing.
    """

    UNDEFINED = "UNDEFINED"
    v2023_09 = "2023-09"
    # Future:
    #  EXPERIMENTAL = "experimental"


class ResolutionScope(str, Enum):
    """Template variable definition and usage scopes:
    TEMPLATE - The Job Template scope.
               Variables defined in this scope are available in the TEMPLATE, SESSION, and TASK scopes.
    SESSION - The Session scope.
             Variables defined in this scope are available in the WORKER, and TASK scopes.
    TASK - The Task scope.
           Variables defined in this scope are only available in the TASK scope.
    """

    TEMPLATE = "TEMPLATE"
    SESSION = "SESSION"
    TASK = "TASK"


@dataclass(frozen=True, eq=False, **dataclass_kwargs)
class TemplateVariableDef:
    """The prefix and scope for a variable definition."""

    prefix: str
    resolves: ResolutionScope


class DefinesTemplateVariables:
    """Metadata for the template variables that an Open Job Description model defines.

    Attributes:
        symbol_prefix (str): This controls the prefix of newly defined template variables,
            like "Task.Param.". By default these concatenate to match how models are nested.
            A "|" prefix discards the parent scope prefix.
        defines -- A set of variable prefixes to define the variable using, and the scopes into
            which those variables are defined.
        field (str): If provided, adds a template variable based on a field in the model. E.g. for a
            job parameter, the scope prefix is "Param." and the field is "name", so if the model has
            "MyParameter" for its name, it produces the variable "Param.MyParameter". A special
            value "__key__", not currently used by any model, indicates the name should come
            from the dictionary key above the model object.
        inject (set[str]): This adds specific names not generated from model fields, like the
            "Session.WorkingDirectory" name, into the scope of the model.
            A "|" prefix discards the parent scope prefix.
            The given symbols are always injected into the current variable scope.
    """

    def __init__(
        self,
        *,
        symbol_prefix: str = "",
        defines: set[TemplateVariableDef] = set(),
        field: str = "",
        inject: set[str] = set(),
    ):
        self.symbol_prefix = symbol_prefix
        self.defines = defines
        self.field = field
        self.inject = inject

    def __repr__(self) -> str:
        return f"DefinesTemplateVariables(symbol_prefix={self.symbol_prefix!r}, defines={self.defines!r}, field={self.field!r}, inject={self.inject!r})"


@dataclass(frozen=True, eq=False, **dataclass_kwargs)
class JobCreateAsMetadata:
    # Only one of the following may be non-None
    # model: Union[Type["OpenJDModel"], Callable[["OpenJDModel"], Type["OpenJDModel"]]]
    model: Optional[Type["OpenJDModel"]] = field(default=None)
    callable: Optional[Callable[["OpenJDModel"], Type["OpenJDModel"]]] = field(default=None)


@dataclass(frozen=True, eq=False, **dataclass_kwargs)
class JobCreationMetadata:
    """Metadata for creating a job out of a job template.
    This metadata instructs the recursive algorithm as to what special
    treatment the model needs during translation from Template to Job.
    """

    resolve_fields: set[str] = field(default_factory=set)
    """The names of fields in the model that may contain FormatStrings, and
    if it does then those FormatStrings must be resolved into strings when
    creating a job.
    We support resolving fields that are:
     1. FormatStrings
     2. lists of FormatStrings
     3. lists of a mix of FormatStrings and non-FormatStrings (e.g. ints,floats,regular-strings,etc)
    """

    create_as: Optional[JobCreateAsMetadata] = field(default=None)
    """The class to create the model as during instantiation. Options:
    1. None -- create as the model class itself.
    2. create_as.model is not None -- create as the given model class.
        Use-cases: JobTemplate creates as a Job, which has a different definition for Job Parameters
            and has fewer fields.
    3. create_as.callable is not None -- invoke the function and create as the class returned.
        arg0 = The instance that is being instantiated
        arg1 = The symbol table for the instantiation.
        Use-case: Conditionally selecting a TaskParameter model class based on how the range
            of the Task parameter is defined (list or expression)
    """

    exclude_fields: set[str] = field(default_factory=set)
    """A set of fields that are ignored when processing the model. The model that is created will
    not be provided values, or kwargs even, for these fields.
    """

    adds_fields: Optional[Callable[[str, "OpenJDModel", SymbolTable], dict[str, Any]]] = field(
        default=None
    )
    """This property defines a callable that uses the instantiation context (i.e. SymbolTable) and
    can materialize new fields that are not already present in the model.
        arg0 - The model key where this model was found.
        arg1 - The model that is adding a value.
        arg2 - The symbol table used in the instantiation.
        Use-case: Transforming Job Parameters from their Template form to Job form; we inject the
            value of the parameter from the SymbolTable into the Job.
    """

    reshape_field_to_dict: dict[str, str] = field(default_factory=dict)
    """This instructs the instantation code to reshape the given list fields into dict fields.
        key: name of the field to reshape.
        value: field name within the list item to use as the dictionary key.
    """

    rename_fields: dict[str, str] = field(default_factory=dict)
    """This instructs the instantiation code to rename the given fields.
    """


class OpenJDModel(BaseModel):
    # See: https://docs.pydantic.dev/usage/model_config/
    class Config:
        # Forbid extra fields in the input
        extra = Extra.forbid

        # Make the model instances immutable
        frozen = True

    # The specific schema revision that the model implements.
    revision: ClassVar[SpecificationRevision]

    # ----
    # Metadata used for defining template variables for use in FormatStrings

    # The variable scope of this model and all submodels, recursively, that don't redefine their own scope.
    _template_variable_scope: Optional[ResolutionScope] = None

    # This specifies how the model generates template variables, see details in the
    # docstring for DefinesTemplateVariables.
    _template_variable_definitions: ClassVar[DefinesTemplateVariables] = DefinesTemplateVariables()

    # This specifies, for each field that substitutes template variables, which other fields
    # they come from. {"<destination-field>": {"<source-field>", ...}, ...}
    #   Template variable destination fields:
    #       "<fieldname>" means the field gets variables from the provided list of source fields.
    #       "__export__" means that the parent scope gets variables from the provided list of source fields.
    #   Template variable source fields:
    #       "<fieldname>" provides the field's exported variables.
    #       "__self__" provides the variables exported by this model via `__template_variable_definitions`.
    _template_variable_sources: ClassVar[dict[str, set[str]]] = {}

    # ----
    # Metadata used in the creation of a Job from a Job Template

    # Metadata for creating a job out of a job template.
    # This metadata instructs the recursive algorithm as to what special
    # treatment the model needs during translation from Template to Job.
    _job_creation_metadata: ClassVar[JobCreationMetadata] = JobCreationMetadata()


class JobParameterInterface(ABC):
    @abstractmethod
    def _check_constraints(self, value: Any) -> None:
        """Given a value, check that the value meets the constraints of the
        Job Parameter's definition.

        Returns:
            True - If the value meets all constraints.

        Raises:
            ValueError if the value does not meet at least one constraint
        """
        pass
