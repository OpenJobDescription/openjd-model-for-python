# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Optional, Iterable, Type, Union

from pydantic import ConfigDict, BaseModel

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
        JobBoolParameterDefinition,
        JobListStringParameterDefinition,
        JobListPathParameterDefinition,
        JobListIntParameterDefinition,
        JobListFloatParameterDefinition,
        JobListBoolParameterDefinition,
        JobListListIntParameterDefinition,
        JobRangeExprParameterDefinition,
    )

    EnvironmentTemplate = EnvironmentTemplate_2023_09
    JobTemplate = JobTemplate_2023_09
    Job = Job_2023_09
    JobParameterDefinition = Union[
        JobIntParameterDefinition,
        JobFloatParameterDefinition,
        JobStringParameterDefinition,
        JobPathParameterDefinition,
        JobBoolParameterDefinition,
        JobListStringParameterDefinition,
        JobListPathParameterDefinition,
        JobListIntParameterDefinition,
        JobListFloatParameterDefinition,
        JobListBoolParameterDefinition,
        JobListListIntParameterDefinition,
        JobRangeExprParameterDefinition,
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
    # This type is only used for task parameters, not job parameters
    CHUNK_INT = "CHUNK[INT]"
    # EXPR extension (RFC 0007) job-parameter value types. These tag a job
    # parameter value through preprocessing/create_job; the underlying value is
    # carried natively (lists/bools) for these types so the typed EXPR
    # SymbolTable builder can coerce them, rather than the stringified form used
    # by the original scalar types.
    BOOL = "BOOL"
    RANGE_EXPR = "RANGE_EXPR"
    LIST_STRING = "LIST[STRING]"
    LIST_PATH = "LIST[PATH]"
    LIST_INT = "LIST[INT]"
    LIST_FLOAT = "LIST[FLOAT]"
    LIST_BOOL = "LIST[BOOL]"
    LIST_LIST_INT = "LIST[LIST[INT]]"


@dataclass(frozen=True, **dataclass_kwargs)
class ParameterValue:
    type: ParameterValueType
    # For the original scalar types (STRING/INT/FLOAT/PATH) the value is a
    # string, typecast as needed during processing. For the EXPR-extension
    # types (RFC 0007: BOOL and the LIST[*] variants) the value is carried as
    # its native Python type (bool / list) so the typed EXPR SymbolTable
    # builder can coerce it — a stringified list cannot be re-parsed back to a
    # typed list.
    value: Any


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
    # Whether the variable holds the raw, unprocessed template value
    # (RawParam.* / Task.RawParam.*). Raw path-typed values are plain strings
    # (RFC 0005): type-aware validation maps a raw PATH to "string" and a raw
    # LIST[PATH] to "list[string]", matching openjd-rs's build_param_symtab.
    raw: bool = False


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
        expr_inject: set[str] = set(),
    ):
        self.symbol_prefix = symbol_prefix
        self.defines = defines
        self.field = field
        self.inject = inject
        # Symbols injected only when the EXPR extension is enabled. Applied by
        # the variable-reference prevalidator (which has the parsing context);
        # the static `inject` set above cannot be made conditional.
        self.expr_inject = expr_inject

    def __repr__(self) -> str:
        return f"DefinesTemplateVariables(symbol_prefix={self.symbol_prefix!r}, defines={self.defines!r}, field={self.field!r}, inject={self.inject!r}, expr_inject={self.expr_inject!r})"


@dataclass(frozen=True, eq=False, **dataclass_kwargs)
class JobCreateAsMetadata:
    # Only one of the following may be non-None.
    model: Optional[Type["OpenJDModel"]] = field(default=None)
    # The callable receives the model and the mapping of typed whole-field
    # resolutions (field name -> native value) that instantiate_model computed
    # for the model's typed_resolve_fields — the same values the field
    # instantiation uses — so target-model selection can depend on a typed
    # resolution without re-evaluating the expression.
    callable: Optional[Callable[["OpenJDModel", dict], Type["OpenJDModel"]]] = field(default=None)


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

    typed_resolve_fields: set[str] = field(default_factory=set)
    """The names of fields (a subset of ``resolve_fields``) that first attempt
    RFC 0006 typed whole-field resolution: a field whose value is a single
    whole-field ``{{ ... }}`` expression evaluating to a list keeps the native
    list instead of a stringified rendering. Used by task-parameter ``range``
    fields so ``range: "{{Param.Values}}"`` with a ``LIST[*]`` job parameter
    instantiates to the literal value list, matching openjd-rs. Fields whose
    typed resolution does not apply (multi-segment format strings, non-list
    results, or evaluation errors) fall back to normal string resolution.

    ``instantiate_model`` evaluates each such field at most once; the result
    is shared with the ``create_as`` callable (see JobCreateAsMetadata).
    """

    typed_resolve_coerce: Optional[Callable[["OpenJDModel", str, Any], Any]] = field(default=None)
    """Optional element-coercion hook for typed whole-field resolutions
    (RFC 0006). When set, ``instantiate_model`` calls it for each field whose
    typed resolution succeeded — arguments are the model, the field name, and
    the raw resolution result (the engine's list ``ExprValue`` with element
    type variants preserved, or a native Python list on the non-engine
    fallback path) — and uses its return value as the instantiated field
    value. The hook may raise ``ValueError`` to reject an element (e.g. a
    bool in an INT task-parameter range); the error is aggregated into the
    model's validation errors. When unset, the raw result is unwrapped to a
    native Python list unchanged.
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

    adds_fields: Optional[Callable[["OpenJDModel", SymbolTable], dict[str, Any]]] = field(
        default=None
    )
    """This property defines a callable that uses the instantiation context (i.e. SymbolTable) and
    can materialize new fields that are not already present in the model.
        arg0 - The model that is adding a value.
        arg1 - The symbol table used in the instantiation.
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

    transform: Optional[Callable[["OpenJDModel"], "OpenJDModel"]] = field(default=None)
    """A callable that transforms the source model before field processing.
        arg0 - The model to transform.
        returns - The transformed model (can be the same instance or a new one).
        Use-case: Resolving syntax sugar on StepTemplate before creating Step.
    """

    extends_symtab: Optional[Callable[["OpenJDModel", SymbolTable], SymbolTable]] = field(
        default=None
    )
    """A callable that returns the symbol table to use when instantiating this
    model and its subtree, given the enclosing symbol table. The returned table
    is used for all of the model's fields; the enclosing table is unaffected.
        arg0 - The model being instantiated.
        arg1 - The enclosing symbol table.
        Use-case: A StepTemplate seeds Step.Name and evaluates its step-level
            EXPR `let` bindings (RFC 0007 §3.6) so the step's parameter space,
            host requirements, and script instantiate against them — mirroring
            openjd-rs's per-step symbol table in instantiate_step.
    """


class OpenJDModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    # The specific schema revision that the model implements.
    revision: ClassVar[SpecificationRevision]

    # The model parsing context required by this model. Each revision of
    # the specification defines this, and it must be default-constructible.
    model_parsing_context_type: ClassVar[Type]

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

    # Per-field variable-scope overrides: fields listed here (and their
    # submodels) validate their format-string references at the given scope
    # instead of the model's ambient scope. Used for fields that VALIDATE at
    # template scope (no Session.*, no Env.File.*/Task.File.*, no host
    # functions) while their siblings validate at the ambient session/task
    # scope — e.g. an Action's `timeout` and `cancelation`, which are carried
    # through job creation unresolved and resolve at run time, but may only
    # reference template-scope symbols (plus per-field injections below).
    _template_field_scopes: ClassVar[dict[str, ResolutionScope]] = {}

    # Per-field extra symbol injection: symbols listed here are visible in
    # every scope, but only within the named field's subtree. Names use the
    # DefinesTemplateVariables.inject spelling (a "|" prefix discards the
    # parent scope prefix). Used for the RFC 0008 wrap hooks' WrappedAction.*
    # variables, which exist only within their hook's action but must be
    # visible even to the hook's template-scoped fields (timeout/cancelation)
    # for round-trip forwarding.
    _template_field_inject: ClassVar[dict[str, set[str]]] = {}

    # As _template_field_inject, but the symbols are injected at SESSION
    # scope: visible to the field subtree's session/task-scoped fields
    # (e.g. a wrap hook's command/args) but NOT to its template-scoped
    # fields (timeout/cancelation). Used for the RFC 0008 WrappedEnv.Name /
    # WrappedStep.Name variables, which openjd-rs excludes from hook
    # timeout/cancelation validation.
    _template_field_inject_session: ClassVar[dict[str, set[str]]] = {}

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


class RevisionExtensions:
    """
    Data class for representing a specific OpenJD Specification Revision and set of extensions
    in order to evaluate supported capabilities.

    This class encapsulates both the specification revision and the set of extensions that are
    supported or requested by a template.

    Attributes:
        spec_rev: The revision of the Open Job Description specification being used.
        extensions: The set of extension names that are supported or requested.
    """

    spec_rev: SpecificationRevision
    """This contains the revision of the Open Job Description being parsed (e.g. "2023-09").
    By providing it in the context, shared code like the FormatString class can do
    version-specific processing.
    """

    extensions: set[str]
    """When parsing a top-level model instance, this is the set of supported extension names.
    The 'extensions' field is second in the list of model properties for both the job template
    and environment template, and when that field is processed it becomes the set of extensions
    that the template requested.
    """

    def __init__(
        self, *, spec_rev: SpecificationRevision, supported_extensions: Optional[Iterable[str]]
    ) -> None:
        """
        Initialize a RevisionExtensions instance.

        Args:
            spec_rev: The specification revision to use.
            supported_extensions: An optional iterable of extension names that are supported.
                                 If None, an empty set will be used.
        """
        self.spec_rev = spec_rev
        self.extensions = set(supported_extensions or [])


class ModelParsingContextInterface(ABC):
    """Context required while parsing an OpenJDModel. A subclass
    must be provided when calling model_validate.

        OpenJDModelSubclass.model_validate(data, context=ModelParsingContext())

    Individual validators receive this value as ValidationInfo.context.

    This interface defines the contract for model parsing contexts across different
    specification revisions. It provides access to the specification revision and
    extensions that are supported or requested by a template, which allows validators
    to adjust their behavior based on the specification version and enabled extensions.
    """

    revision_extensions: RevisionExtensions
    """Contains information about the specification revision and supported extensions.
    This allows shared code like the FormatString class to perform version-specific
    processing and extension-dependent validation.

    When fields of a model that depend on an extension are processed, its validators should
    check whether the needed extension is included in the context and adjust its parsing
    as written in the specification.
    """

    @property
    def spec_rev(self) -> SpecificationRevision:
        """
        Get the specification revision being used.

        Returns:
            The specification revision from the revision_extensions.
        """
        return self.revision_extensions.spec_rev

    @property
    def extensions(self) -> set[str]:
        """
        Get the set of supported extensions.

        Returns:
            The set of extension names from the revision_extensions.
        """
        return self.revision_extensions.extensions

    @extensions.setter
    def extensions(self, extension_set: set[str]):
        """
        Set the supported extensions.

        Args:
            extension_set: The new set of extension names to use.
        """
        self.revision_extensions.extensions = extension_set

    def __init__(
        self, *, spec_rev: SpecificationRevision, supported_extensions: Optional[Iterable[str]]
    ) -> None:
        """
        Initialize a ModelParsingContextInterface instance.

        Args:
            spec_rev: The specification revision to use.
            supported_extensions: An optional iterable of extension names that are supported.
                                 If None, an empty set will be used.
        """
        self.revision_extensions = RevisionExtensions(
            spec_rev=spec_rev, supported_extensions=supported_extensions
        )
