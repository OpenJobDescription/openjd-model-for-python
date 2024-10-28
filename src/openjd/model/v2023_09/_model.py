# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from enum import Enum
from graphlib import CycleError, TopologicalSorter
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Optional, Type, Union, cast
from typing_extensions import Annotated

from pydantic.v1 import (
    Field,
    PositiveInt,
    PositiveFloat,
    StrictBool,
    StrictInt,
    ValidationError,
    conint,
    conlist,
    constr,
    root_validator,
    validator,
)
from pydantic.v1.error_wrappers import ErrorWrapper

from .._format_strings import FormatString
from .._errors import ExpressionError, TokenError
from .._capabilities import (
    validate_amount_capability_name,
    validate_attribute_capability_name,
)
from .._internal import (
    CombinationExpressionParser,
    validate_step_parameter_space_dimensions,
    validate_unique_elements,
)
from .._internal._variable_reference_validation import (
    prevalidate_model_template_variable_references,
)
from .._range_expr import IntRangeExpr
from .._types import (
    DefinesTemplateVariables,
    JobCreateAsMetadata,
    JobCreationMetadata,
    JobParameterInterface,
    OpenJDModel,
    ResolutionScope,
    SpecificationRevision,
    TemplateSpecificationVersion,
    TemplateVariableDef,
)


class OpenJDModel_v2023_09(OpenJDModel):  # noqa: N801
    revision = SpecificationRevision.v2023_09


class ValueReferenceConstants(Enum):
    """Prefixes used when referencing values in format strings."""

    JOB_PARAMETER_PREFIX = "Param"
    """Prefix for referencing processed Job Parameters.
    """

    JOB_PARAMETER_RAWPREFIX = "RawParam"
    """Prefix for referencing Job Parameters' input value.
    """

    ENV_FILE_PREFIX = "Env.File"
    """Prefix for referencing an Environment's embedded files.
    """

    TASK_FILE_PREFIX = "Task.File"
    """Prefix for referencing an embedded file that is defined within
    a Step Script.
    """

    TASK_PARAMETER_PREFIX = "Task.Param"
    """Prefix for referencing a processed Task Parameter's value.
    """

    TASK_PARAMETER_RAWPREFIX = "Task.RawParam"
    """Prefix for referencing Task Parameter's input value.
    """

    WORKING_DIRECTORY = "Session.WorkingDirectory"
    """The reference to the Session Working Directory.
    This will resolve to the fully qualified temporary directory on disk
    that is being used as the working directory for the Session.
    """

    HAS_PATH_MAPPING_RULES = "Session.HasPathMappingRules"
    """The reference to whether or not a Task/Environment run
    has path mapping rules available.
    Value of this value will be either: "true" or "false"
    ( case sensitive )
    """

    PATH_MAPPING_RULES_FILE = "Session.PathMappingRulesFile"
    """A value that resolves to the fully qualified file location
    of a JSON file that contains the path mapping rules. This file will
    be in the Session's Working Directory.
    If there are no path mapping rules, then this file will contain
    only: {}
    """


# ==================================================================
# ============================= String types =======================
# ==================================================================

# All unicode characters except for those in the Cc unicode character
# category.
#  Cc category =
#    C0 = 0x00-0x1F
#         https://www.unicode.org/charts/PDF/U0000.pdf
#    DEL character (0x7F)
#    C1 = 0x80-0x9F
#         https://www.unicode.org/charts/PDF/U0080.pdf
_Cc_characters = r"\u0000-\u001F\u007F-\u009F"
_standard_string_regex = rf"(?-m:^[^{_Cc_characters}]+\Z)"

# Latin alphanumeric, starting with a letter
_identifier_regex = r"(?-m:^[A-Za-z_][A-Za-z0-9_]*\Z)"

# Regex for defining file filter patterns allowed for use in file dialogs.
# 1. Allowable values: "*", "*.*", and "*.[:file-extension-chars:]+".
#    The characters that :file-extension-chars: can take on are any unicode character except:
#    a. The Cc unicode character category.
#    b. Path separators "\" and "/".
#    c. Wildcard characters "*", "?", "[", "]".
#    d. Characters commonly disallowed in paths "#", "%", "&", "{", "}", "<", ">",
#       "$", "!", "'", "\"", ":", "@", "`", "|", "=".
_file_dialog_filter_pattern_regex = (
    rf"(?-m:^(?:\*|\*\.\*|\*\."
    rf"[^{_Cc_characters}\\/\*"
    rf"\?\[\]#%&\{{\}}<>\$\!'"
    rf"\\\":@`|=]+)\Z)"
)


class JobTemplateName(FormatString):
    _min_length = 1


if TYPE_CHECKING:
    JobName = str
    Identifier = str
    Description = str
    EnvironmentName = str
    StepName = str
    ParameterStringValue = str
else:
    JobName = constr(min_length=1, max_length=128, strict=True, regex=_standard_string_regex)
    Identifier = constr(min_length=1, max_length=64, strict=True, regex=_identifier_regex)
    Description = constr(
        min_length=1,
        max_length=2048,
        strict=True,
        # All unicode except the [Cc] (control characters) category
        # Allow CR, LF, and TAB.
        regex=f"(?-m:^(?:[^{_Cc_characters}]|[\r\n\t])+\Z)",
    )
    EnvironmentName = constr(min_length=1, max_length=64, strict=True, regex=_standard_string_regex)
    StepName = constr(min_length=1, max_length=64, strict=True, regex=_standard_string_regex)
    ParameterStringValue = constr(min_length=0, max_length=1024, strict=True)

# ==================================================================
# ============================= Script types =======================
# ==================================================================


# ---------------------------- Action type -------------------------


class CommandString(FormatString):
    _min_length = 1
    # All unicode except the [Cc] (control characters) category
    _regex = f"(?-m:^[^{_Cc_characters}]+\Z)"


class ArgString(FormatString):
    # All unicode except the [Cc] (control characters) category
    # Allow CR, LF, and TAB.
    _regex = f"(?-m:^[^{_Cc_characters}]*\Z)"


class CancelationMode(str, Enum):
    NOTIFY_THEN_TERMINATE = "NOTIFY_THEN_TERMINATE"
    TERMINATE = "TERMINATE"


if TYPE_CHECKING:
    NotifyPeriodType = int
else:
    NotifyPeriodType = conint(ge=1, le=600)


class CancelationMethodNotifyThenTerminate(OpenJDModel_v2023_09):
    """Notify-then-terminate cancelation mode for an Action.

    On Posix systems — Send a SIGTERM, followed by waiting for the notify period in
    seconds, and then sending SIGKILL to the entire process tree if the command is
    still running.

    On Windows systems — Send a CTRL_C, followed by waiting for the notify period in
    seconds, and then Terminating the entire process tree if the command is still running.

    Prior to sending the first signal, a file called cancel.info is written to the session
    working directory. The contents of this file provide an ISO 8601 time in UTC, in the form
    <year>-<month>-<day>T<hour>:<minute>:<second>Z,
    at which the notify period will end. The format of this file is:

    ```
    NotifyEnd = <yyyy>-<mm>-<dd>T<hh>:<mm>:<ss>Z
    ```

    Attributes:
        mode ("NOTIFY_THEN_TERMINATE"): The mode of the cancelation to use.
        notifyPeriodInSeconds (Optional[int]): Defines the maximum number of seconds between
            the two signals. It is possible that the actual duration allowed in a particular
            cancel event will be less than this amount if circumstances warrant.
            Maximum value: 600
            Defaults:
                120 for onRun StepScript Action
                30 for all other Actions
    """

    mode: Literal[CancelationMode.NOTIFY_THEN_TERMINATE]
    notifyPeriodInSeconds: Optional[NotifyPeriodType] = None  # noqa: N815


class CancelationMethodTerminate(OpenJDModel_v2023_09):
    """Terminate cancelation mode for an Action.

    On Posix systems — Send SIGKILL to the entire process tree when a cancel is requested.

    On Windows systems - Terminate the entire process tree when a cancel is requested.

    Attributes:
        mode ("TERMINATE"): The mode of the cancelation to use.
    """

    mode: Literal[CancelationMode.TERMINATE]


if TYPE_CHECKING:
    ArgListType = list[ArgString]
else:
    ArgListType = conlist(ArgString, min_items=1)


class Action(OpenJDModel_v2023_09):
    """An Action to run.

    Attributes:
        command (FormatString): The command/executable that will be run.
        args (Optional[list[FormatString]]): The arguments that are provided to the command
            when it is run.
        timeout (Optional[int]): Maximum allowed runtime of the Action in seconds.
            Default: No timeout
        cancelation (Optional[Union[CancelationMethodNotifyThenTerminate, CancelationMethodTerminate]]):
            If defined, provides details regarding how this action should be canceled.
            Default: CancelationMethodTerminate
    """

    command: CommandString
    args: Optional[ArgListType] = None
    timeout: Optional[PositiveInt] = None
    cancelation: Optional[
        Union[CancelationMethodNotifyThenTerminate, CancelationMethodTerminate]
    ] = Field(None, discriminator="mode")


class StepActions(OpenJDModel_v2023_09):
    """The Actions for Tasks of a Step.

    Attributes:
        onRun (Action): Action to run when running a single Task.
    """

    onRun: Action  # noqa: N815


class EnvironmentActions(OpenJDModel_v2023_09):
    """The Actions to run at various stages of running an Environment.

    Attributes:
        onEnter (Optional[Action]): Action to run when entering the environment
            as part of a Session.
        onExit (Optional[Action]): Action to run when exiting the environment
            in a Session.

    Note: Must define at least one of onEnter or onExit
    """

    onEnter: Optional[Action] = Field(None)  # noqa: N815
    onExit: Optional[Action] = Field(None)  # noqa: N815

    @root_validator(pre=True)
    def _requires_oneof(cls, values: dict[str, Any]) -> dict[str, Any]:
        """A validator that runs on the model data before parsing."""
        on_enter = values.get("onEnter")
        on_exit = values.get("onExit")
        if on_enter is None and on_exit is None:
            raise ValueError("Must define one of: onEnter or onExit")
        return values


# --------------------- Embedded Files type -------------------------


class EmbeddedFileTypes(str, Enum):
    TEXT = "TEXT"


if TYPE_CHECKING:
    Filename = str
else:
    # TODO - regex of allowable filename characters
    Filename = constr(min_length=1, max_length=64, strict=True)


class DataString(FormatString):
    _min_length = 1


class EmbeddedFileText(OpenJDModel_v2023_09):
    """A plain text file embedded directly into the Job Template.
    This file is materialized to a subdirectory of a Session's working directory
    when running a corresponding Action in the Session.

    Attributes:
        name (Identifier): A name by which the embedded file is referenced.
        type ("TEXT"): The type of the emdedded file: plain text.
        filename (Optional[str]): The filename to write the file as.
            Default: Randomly generated filename.
        runnable (Optional[bool]): A True value indicates that the written file
            will have its execute-permissions set.
            Default: False
        data (FormatString): The text data to write to the file.
    """

    name: Identifier
    type: Literal[EmbeddedFileTypes.TEXT]
    data: DataString
    filename: Optional[Filename] = None
    runnable: Optional[StrictBool] = None

    _template_variable_definitions = DefinesTemplateVariables(
        defines={TemplateVariableDef(prefix="File.", resolves=ResolutionScope.SESSION)},
        field="name",
    )
    _template_variable_sources = {
        "__export__": {"__self__"},
        "data": {"__self__"},
    }


# --------------------- Script types ----------------------------

if TYPE_CHECKING:
    EmbeddedFiles = list[EmbeddedFileText]
else:
    EmbeddedFiles = conlist(EmbeddedFileText, min_items=1)


class StepScript(OpenJDModel_v2023_09):
    """The Step Script is the information on what Actions to perform when running
    a Task for a Step.

    Attributes:
        embeddedFiles (Optional[list[EmbeddedFileText]]): List of text files embedded
           into the script. These will be written to disk prior to running each of the
           Actions in the script.
        actions (StepActions): The actions to run when running a Task for the Step.
    """

    actions: StepActions
    embeddedFiles: Optional[EmbeddedFiles] = None  # noqa: N815

    _template_variable_scope = ResolutionScope.TASK
    _template_variable_definitions = DefinesTemplateVariables(
        symbol_prefix="|Task.",
        inject={
            f"|{ValueReferenceConstants.WORKING_DIRECTORY.value}",
            f"|{ValueReferenceConstants.HAS_PATH_MAPPING_RULES.value}",
            f"|{ValueReferenceConstants.PATH_MAPPING_RULES_FILE.value}",
        },
    )
    _template_variable_sources = {
        "actions": {"embeddedFiles", "__self__"},
        "embeddedFiles": {"embeddedFiles", "__self__"},
    }

    @validator("embeddedFiles")
    def _unique_names(cls, v: Optional[EmbeddedFiles]) -> Optional[EmbeddedFiles]:
        if v is not None:
            return validate_unique_elements(v, item_value=lambda v: v.name, property="name")
        return v


class EnvironmentScript(OpenJDModel_v2023_09):
    """The Environment Script is the information on what Actions to perform when running
    an Environment within a Session.

    Attributes:
        embeddedFiles (Optional[list[EmbeddedFileText]]): List of text files embedded
           into the script. These will be written to disk prior to running each of the
           Actions in the script.
        actions (EnvironmentActions): The actions to run when at various stages of the Environment's
           lifecycle.
    """

    actions: EnvironmentActions
    embeddedFiles: Optional[EmbeddedFiles] = None  # noqa: N815

    _template_variable_definitions = DefinesTemplateVariables(
        symbol_prefix="|Env.",
        inject={
            f"|{ValueReferenceConstants.WORKING_DIRECTORY.value}",
            f"|{ValueReferenceConstants.HAS_PATH_MAPPING_RULES.value}",
            f"|{ValueReferenceConstants.PATH_MAPPING_RULES_FILE.value}",
        },
    )
    _template_variable_sources = {
        "actions": {"embeddedFiles", "__self__"},
        "embeddedFiles": {"embeddedFiles", "__self__"},
    }

    @validator("embeddedFiles")
    def _unique_names(cls, v: Optional[EmbeddedFiles]) -> Optional[EmbeddedFiles]:
        if v is not None:
            return validate_unique_elements(v, item_value=lambda v: v.name, property="name")
        return v


# ==================================================================
# ========================== Task Parameters =======================
# ==================================================================


class TaskParameterStringValue(FormatString):
    """A FormatString as an element of a Task's range list."""

    # Note: No maximum length. The max string length is enforced
    # as a TaskParameterStringValueAsJob type after the template
    # has been instantiated in to a Job, and this format string
    # has been evaluated.
    pass


class TaskParameterType(str, Enum):
    INT = "INT"
    FLOAT = "FLOAT"
    STRING = "STRING"
    PATH = "PATH"


class RangeString(FormatString):
    _min_length = 1


if TYPE_CHECKING:
    # Note: Ordering within the Unions is important. Pydantic will try to match in
    # the order given.
    IntRangeList = list[Union[int, TaskParameterStringValue]]
    FloatRangeList = list[Union[Decimal, TaskParameterStringValue]]
    StringRangeList = list[TaskParameterStringValue]
    TaskParameterStringValueAsJob = str
else:
    IntRangeList = conlist(Union[int, TaskParameterStringValue], min_items=1, max_items=1024)
    FloatRangeList = conlist(Union[Decimal, TaskParameterStringValue], min_items=1, max_items=1024)
    StringRangeList = conlist(TaskParameterStringValue, min_items=1, max_items=1024)
    TaskParameterStringValueAsJob = constr(min_length=0, max_length=1024)

TaskRangeList = list[TaskParameterStringValueAsJob]
TaskRangeExpression = RangeString


# Target model for task parameters when instantiating a job.
class RangeListTaskParameterDefinition(OpenJDModel_v2023_09):
    # element type of items in the range
    type: TaskParameterType
    range: TaskRangeList


class RangeExpressionTaskParameterDefinition(OpenJDModel_v2023_09):
    # element type of items in the range
    type: TaskParameterType
    range: TaskRangeExpression

    @validator("range")
    def _validate_range_expression(cls, value: Any) -> Any:
        """At this point, the format expressions have been resolved
        and we can determine if it's a valid RangeExpression"""
        try:
            IntRangeExpr.from_str(value)
        except Exception as e:
            raise ValueError(str(e))

        return value


class IntTaskParameterDefinition(OpenJDModel_v2023_09):
    """Definition of an integer-typed Task Parameter and its value range.

    Attributes:
        name (Identifier):  A name by which the parameter is referenced.
        type (TaskParameterType.INT): discriminator to identify the type of the parameter.
        range (IntRangeList | RangeString): The list of values that the parameter takes on.
    """

    name: Identifier
    type: Literal[TaskParameterType.INT]
    # Note: Ordering here is important. Pydantic will try to match in
    # the order given.
    range: Union[IntRangeList, RangeString]

    _template_variable_definitions = DefinesTemplateVariables(
        defines={
            TemplateVariableDef(prefix="|Task.Param.", resolves=ResolutionScope.TASK),
            TemplateVariableDef(prefix="|Task.RawParam.", resolves=ResolutionScope.TASK),
        },
        field="name",
    )
    _template_variable_sources = {"__export__": {"__self__"}}

    def _get_range_task_param_type(model: Any) -> Type[OpenJDModel]:
        if isinstance(model.range, RangeString):
            return RangeExpressionTaskParameterDefinition
        return RangeListTaskParameterDefinition

    _job_creation_metadata = JobCreationMetadata(
        create_as=JobCreateAsMetadata(callable=_get_range_task_param_type),
        resolve_fields={"range"},
        exclude_fields={"name"},
    )

    @validator("range", pre=True)
    def _validate_range_element_type(cls, value: Any) -> Any:
        # pydandic will automatically type coerse values into integers. We explicitly
        # want to reject non-integer values, so this *pre* validator validates the
        # value *before* pydantic tries to type coerse it.
        # We do allow coersion from a string since we want to allow "1", and
        # "1.2" or "a" will fail the type coersion
        if isinstance(value, list):
            errors = list[ErrorWrapper]()
            for v in value:
                if isinstance(v, bool) or not isinstance(v, (int, str)):
                    errors.append(
                        ErrorWrapper(
                            ValueError("Value must be an integer or integer string."), ("range", v)
                        )
                    )
            if errors:
                raise ValidationError(errors, IntTaskParameterDefinition)
        elif isinstance(value, RangeString):
            # TODO: nothing to do - it's guaranteed to be a format string at this point
            pass

        return value

    @validator("range")
    def _validate_range_elements(cls, value: Any) -> Any:
        if isinstance(value, list):
            errors = list[ErrorWrapper]()
            for v in value:
                if isinstance(v, TaskParameterStringValue):
                    # A TaskParameterStringValue is a FormatString.
                    # FormatString.expressions is the list of all expressions in the format string
                    # ( e.g. "{{ Param.Foo }}").
                    # Reject the string if it contains any expressions.
                    if len(v.expressions) == 0:
                        errors.append(
                            ErrorWrapper(
                                ValueError("String literal must contain an integer."), ("range", v)
                            )
                        )
            if errors:
                raise ValidationError(errors, IntTaskParameterDefinition)
        else:
            # If there are no format expressions, we can validate the range expression.
            # otherwise we defer to the RangeExressionTaskParameter model when
            # they've all been evaluated
            if len(value.expressions) == 0:
                try:
                    IntRangeExpr.from_str(value)
                except Exception as e:
                    raise ValueError(str(e))
        return value


class FloatTaskParameterDefinition(OpenJDModel_v2023_09):
    """Definition of a float-typed Task Parameter and its value range.

    Attributes:
        name (Identifier):  A name by which the parameter is referenced.
        type (TaskParameterType.FLOAT): discriminator to identify the type of the parameter.
        range (FloatRangeList): The list of values that the parameter takes on.
    """

    name: Identifier
    type: Literal[TaskParameterType.FLOAT]
    range: FloatRangeList

    _template_variable_definitions = DefinesTemplateVariables(
        defines={
            TemplateVariableDef(prefix="|Task.Param.", resolves=ResolutionScope.TASK),
            TemplateVariableDef(prefix="|Task.RawParam.", resolves=ResolutionScope.TASK),
        },
        field="name",
    )
    _template_variable_sources = {"__export__": {"__self__"}}
    _job_creation_metadata = JobCreationMetadata(
        create_as=JobCreateAsMetadata(model=RangeListTaskParameterDefinition),
        resolve_fields={"range"},
        exclude_fields={"name"},
    )

    @validator("range", each_item=True, pre=True)
    def _validate_range_element_type(cls, v: Any) -> Any:
        # pydandic will automatically type coerse values into floats. We explicitly
        # want to reject non-integer values, so this *pre* validator validates the
        # value *before* pydantic tries to type coerse it.
        # We do allow coersion from a string since we want to allow "1", and
        # "1.2" or "a" will fail the type coersion
        if isinstance(v, bool) or not isinstance(v, (int, float, str)):
            raise ValueError("Item must be a float, int, or float string.")
        return v

    @validator("range", each_item=True)
    def _validate_range_elements(
        cls, v: Union[Decimal, TaskParameterStringValue]
    ) -> Union[Decimal, TaskParameterStringValue]:
        if isinstance(v, TaskParameterStringValue):
            # A TaskParameterStringValue is a FormatString.
            # FormatString.expressions is the list of all expressions in the format string
            # ( e.g. "{{ Param.Foo }}").
            # Reject the string if it contains any expressions.
            if len(v.expressions) == 0:
                raise ValueError("String literal must contain an integer or float.")
        return v


class StringTaskParameterDefinition(OpenJDModel_v2023_09):
    """Definition of a string-typed Task Parameter and its value range.

    Attributes:
        name (Identifier):  A name by which the parameter is referenced.
        type (TaskParameterType.STRING): discriminator to identify the type of the parameter.
        range (StringRangeList): The list of values that the parameter takes on.
    """

    name: Identifier
    type: Literal[TaskParameterType.STRING]
    range: StringRangeList

    _template_variable_definitions = DefinesTemplateVariables(
        defines={
            TemplateVariableDef(prefix="|Task.Param.", resolves=ResolutionScope.TASK),
            TemplateVariableDef(prefix="|Task.RawParam.", resolves=ResolutionScope.TASK),
        },
        field="name",
    )
    _template_variable_sources = {"__export__": {"__self__"}}
    _job_creation_metadata = JobCreationMetadata(
        create_as=JobCreateAsMetadata(model=RangeListTaskParameterDefinition),
        resolve_fields={"range"},
        exclude_fields={"name"},
    )


class PathTaskParameterDefinition(OpenJDModel_v2023_09):
    """Definition of a path-typed Task Parameter and its value range.

    Attributes:
        name (Identifier):  A name by which the parameter is referenced.
        type (TaskParameterType.PATH): discriminator to identify the type of the parameter.
        range (StringRangeList): The list of values that the parameter takes on.
    """

    name: Identifier
    type: Literal[TaskParameterType.PATH]
    range: StringRangeList

    _template_variable_definitions = DefinesTemplateVariables(
        defines={
            TemplateVariableDef(prefix="|Task.Param.", resolves=ResolutionScope.TASK),
            TemplateVariableDef(prefix="|Task.RawParam.", resolves=ResolutionScope.TASK),
        },
        field="name",
    )
    _template_variable_sources = {"__export__": {"__self__"}}
    _job_creation_metadata = JobCreationMetadata(
        create_as=JobCreateAsMetadata(model=RangeListTaskParameterDefinition),
        resolve_fields={"range"},
        exclude_fields={"name"},
    )


TaskParameterDefinition = Union[
    IntTaskParameterDefinition,
    FloatTaskParameterDefinition,
    StringTaskParameterDefinition,
    PathTaskParameterDefinition,
]

if TYPE_CHECKING:
    TaskParameterList = list[TaskParameterDefinition]
    CombinationExpr = str
else:
    TaskParameterList = conlist(
        Annotated[TaskParameterDefinition, Field(..., discriminator="type")],
        min_items=1,
        max_items=16,
    )
    # Limit the CombinationExpr to characters allowed in an Identifier plus whitespace
    # and the operator characters.
    CombinationExpr = constr(
        min_length=1, max_length=1280, strict=True, regex=r"(?-m:^[A-Za-z0-9\*\(\), ]+\Z)"
    )

TaskRangeParameter = Union[RangeListTaskParameterDefinition, RangeExpressionTaskParameterDefinition]


# Target model for step template when instantiating a job.
class StepParameterSpace(OpenJDModel_v2023_09):
    # Note: taskParameterDefinitions is a dict here to make it easier to work with
    # programatically (e.g. finding the TaskRangeParameterDefinition for a given
    # identifier)
    taskParameterDefinitions: dict[Identifier, TaskRangeParameter]
    combination: Optional[CombinationExpr] = None

    @validator("combination")
    def _validate_parameter_space(cls, v: str, values: dict[str, Any]) -> str:
        if v is None:
            return v
        param_defs = cast(dict[Identifier, TaskRangeParameter], values["taskParameterDefinitions"])
        parameter_range_lengths = {
            id: (
                len(param.range)
                if isinstance(param.range, list)
                else len(IntRangeExpr.from_str(param.range))
            )
            for id, param in param_defs.items()
        }
        try:
            validate_step_parameter_space_dimensions(parameter_range_lengths, v)
        except ExpressionError as e:
            raise ValueError(str(e)) from None
        return v


class StepParameterSpaceDefinition(OpenJDModel_v2023_09):
    """Definition of a Step's parameter space. The parameter space is the multidimensional
    space of all possible task parameter sets that tasks will be run with.

    Attributes:
        parameters (TaskParameterList): Declaration of all of the task parameters.
        combination (Optional[str]): Combination string that instructs how to build the parameter
            space from the task parameters and their ranges.
    """

    taskParameterDefinitions: TaskParameterList
    combination: Optional[CombinationExpr] = None

    _template_variable_sources = {"__export__": {"taskParameterDefinitions"}}
    _job_creation_metadata = JobCreationMetadata(
        create_as=JobCreateAsMetadata(model=StepParameterSpace),
        reshape_field_to_dict={"taskParameterDefinitions": "name"},
    )

    @validator("taskParameterDefinitions")
    def _validate_parameters(cls, v: TaskParameterList) -> TaskParameterList:
        # Must have a unique name for each Task parameter
        return validate_unique_elements(v, item_value=lambda v: v.name, property="name")

    @root_validator
    def _validate_combination(cls, values: dict[str, Any]) -> dict[str, Any]:
        if values.get("combination") is None:
            return values
        if values.get("taskParameterDefinitions") is None:
            return values

        parameter_list: TaskParameterList = cast(
            TaskParameterList, values["taskParameterDefinitions"]
        )
        combination: CombinationExpr = cast(CombinationExpr, values["combination"])

        # Ensure that the 'combination' string:
        #   a) is a properly formed combination expression; and
        #   b) references all available task parameters exactly once each

        try:
            parse_tree = CombinationExpressionParser().parse(combination)
        except (ExpressionError, TokenError) as e:
            raise ValueError(str(e))

        expr_identifiers = list[str]()
        parse_tree.collect_identifiers(expr_identifiers)
        unique_expr_identifiers = set(expr_identifiers)
        parameter_names = [param.name for param in parameter_list]
        unique_parameter_names = set(parameter_names)

        errors = list[ErrorWrapper]()
        if len(unique_expr_identifiers) < len(unique_parameter_names):
            # Missing some parameter identifiers in the expression
            missing = sorted(list(unique_parameter_names - unique_expr_identifiers))
            errors.append(
                ErrorWrapper(
                    ValueError(f"Expression missing parameters: {','.join(missing)}"),
                    ("combination",),
                )
            )
        if len(unique_parameter_names) < len(unique_expr_identifiers):
            # Have some extra parameters referenced in the expression
            extra = sorted(list(unique_expr_identifiers - unique_parameter_names))
            errors.append(
                ErrorWrapper(
                    ValueError(f"Expression references undefined parameters: {','.join(extra)}"),
                    ("combination",),
                )
            )
        if len(expr_identifiers) != len(unique_expr_identifiers):
            # Some parameter names are used more than once in the expression
            duplicates = sorted(
                [id for id in expr_identifiers if id not in unique_expr_identifiers]
            )
            errors.append(
                ErrorWrapper(
                    ValueError(
                        f"Expression can only reference each parameter once: {','.join(duplicates)} "
                    ),
                    ("combination",),
                )
            )

        if errors:
            raise ValidationError(errors, StepParameterSpaceDefinition)

        return values


# ==================================================================
# ====================== Environments Variables ====================
# ==================================================================

if TYPE_CHECKING:
    EnvironmentVariableNameString = str
else:
    EnvironmentVariableNameString = constr(
        min_length=1, max_length=256, regex=r"(?-m:^[a-zA-Z_][a-zA-Z0-9_]*\Z)"
    )


class EnvironmentVariableValueString(FormatString):
    _max_length = 2048


EnvironmentVariableObject = dict[EnvironmentVariableNameString, EnvironmentVariableValueString]


# ==================================================================
# ========================== Environments ==========================
# ==================================================================


class Environment(OpenJDModel_v2023_09):
    """Definition of an Environment. Environments are entered at the start of a Session, and
    exited at the end of a Session. They are a vehicle for amortizing expensive or time-consuming
    setup and tear-down operations in the worker's environment before and after a sequence of Tasks.

    Attributes:
        name (EnvironmentName): A name by which the Environment is referenced.
        description (Optional[str]): A free form string that can be used to describe the environment.
            It has no functional purpose, but may appear in UI elements.
        script (Optional[EnvironmentScript]): The information on what Actions to perform when running an
            Environment within a Session.
        variables (Optional[EnvironmentVariableObject]): The environment variables that should be set when
            running an Environment within a Session.
    """

    name: EnvironmentName
    script: Optional[EnvironmentScript] = None
    variables: Optional[EnvironmentVariableObject] = None
    description: Optional[Description] = None

    _template_variable_scope = ResolutionScope.SESSION

    @root_validator(pre=True)
    def _validate_has_script_or_variables(cls, values: dict[str, Any]) -> dict[str, Any]:
        if values.get("script") is None and values.get("variables") is None:
            raise ValueError("Environment must have either a script or variables.")
        return values

    @validator("variables")
    def _validate_variables(
        cls, variables: Optional[EnvironmentVariableObject]
    ) -> Optional[EnvironmentVariableObject]:
        if variables is None:
            return variables
        if len(variables) == 0:
            raise ValueError("Environment variables cannot be an empty object.")
        return variables


# ==================================================================
# ========================== Job Parameters ========================
# ==================================================================


class JobParameterType(str, Enum):
    STRING = "STRING"
    PATH = "PATH"
    INT = "INT"
    FLOAT = "FLOAT"


if TYPE_CHECKING:
    AllowedParameterStringValueList = list[ParameterStringValue]
    AllowedIntParameterList = list[int]
    AllowedFloatParameterList = list[Decimal]
    UserInterfaceLabelStringValue = str
    FileDialogFilterPatternStringValue = str
    FileDialogFilterPatternStringValueList = list[FileDialogFilterPatternStringValue]
else:
    AllowedParameterStringValueList = conlist(ParameterStringValue, min_items=1)
    AllowedIntParameterList = conlist(int, min_items=1)
    AllowedFloatParameterList = conlist(Decimal, min_items=1)
    UserInterfaceLabelStringValue = constr(
        min_length=1, max_length=64, strict=True, regex=_standard_string_regex
    )
    FileDialogFilterPatternStringValue = constr(
        min_length=1, max_length=20, strict=True, regex=_file_dialog_filter_pattern_regex
    )
    FileDialogFilterPatternStringValueList = conlist(
        FileDialogFilterPatternStringValue, min_items=1, max_items=20
    )


# Target model for a job parameter when instantiating a job.
class JobParameter(OpenJDModel_v2023_09):
    type: JobParameterType
    value: str
    description: Optional[Description] = None


class StringUserInterfaceControl(str, Enum):
    LINE_EDIT = "LINE_EDIT"
    MULTILINE_EDIT = "MULTILINE_EDIT"
    DROPDOWN_LIST = "DROPDOWN_LIST"
    CHECK_BOX = "CHECK_BOX"
    HIDDEN = "HIDDEN"


# These are the permitted sets of values that can be in a string job parameter 'allowedValues'
# when the user interface control is CHECK_BOX.
ALLOWED_VALUES_FOR_CHECK_BOX = ({"TRUE", "FALSE"}, {"YES", "NO"}, {"ON", "OFF"}, {"1", "0"})


class JobStringParameterDefinitionUserInterface(OpenJDModel_v2023_09):
    """User interface attributes for a job string parameter.

    Attributes:
        control (StringUserInterfaceControl): The user interface control to use when editing this parameter.
        label (Optional[UserInterfaceLabelStringValue]): The label to display for the user interface control. Defaults
            to the `name` of the parameter.
        groupLabel (Optional[UserInterfaceLabelStringValue]): The label of the group box to place the user interface
            control in.
    """

    control: StringUserInterfaceControl
    label: Optional[UserInterfaceLabelStringValue]
    groupLabel: Optional[UserInterfaceLabelStringValue]


class JobStringParameterDefinition(OpenJDModel_v2023_09, JobParameterInterface):
    """A Job Parameter of type string.

    Attributes:
        name (Identifier): A name by which the parameter is referenced.
        type (JobParameterType.STRING): discriminator to identify the type of the parameter
        userInterface (Optional[JobStringParameterDefinitionUserInterface]): User interface properties
            for this parameter
        description (Optional[Description]): A free form string that can be used to describe
            the parameter. It has no functional purpose, but may appear in UI elements.
        default (Optional[ParameterStringValue]): Default value for the parameter if a value
            is not provided.
        allowedValues (Optional[AllowedParameterStringValueList]): Explicit list of values that the
            parameter is allowed to take on.
        minLength (Optional[int]): Minimum string length of the parameter value.
        maxLength (Optional[int]): Maximum string length of the parameter value.
    """

    name: Identifier
    type: Literal[JobParameterType.STRING]
    userInterface: Optional[JobStringParameterDefinitionUserInterface]
    description: Optional[Description] = None
    # Note: Ordering of the following fields is essential for the validators to work correctly.
    minLength: Optional[StrictInt] = None  # noqa: N815
    maxLength: Optional[StrictInt] = None  # noqa: N815
    allowedValues: Optional[AllowedParameterStringValueList] = None  # noqa: N815
    default: Optional[ParameterStringValue] = None

    _template_variable_definitions = DefinesTemplateVariables(
        defines={
            TemplateVariableDef(prefix="|Param.", resolves=ResolutionScope.TEMPLATE),
            TemplateVariableDef(prefix="|RawParam.", resolves=ResolutionScope.TEMPLATE),
        },
        field="name",
    )
    _template_variable_sources = {"__export__": {"__self__"}}
    _job_creation_metadata = JobCreationMetadata(
        create_as=JobCreateAsMetadata(model=JobParameter),
        exclude_fields={
            "name",
            "userInterface",
            "minLength",
            "maxLength",
            "allowedValues",
            "default",
        },
        adds_fields=lambda key, this, symtab: {
            "value": symtab[f"RawParam.{cast(JobStringParameterDefinition,this).name}"]
        },
    )

    @validator("minLength")
    def _validate_min_length(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v <= 0:
            raise ValueError("Required: 0 < minLength.")
        return v

    @validator("maxLength")
    def _validate_max_length(cls, v: Optional[int], values: dict[str, Any]) -> Optional[int]:
        if v is None:
            return v
        if v <= 0:
            raise ValueError("Required: 0 < maxLength.")
        min_length = values.get("minLength")
        if min_length is None:
            return v
        if min_length > v:
            raise ValueError("Required: minLength <= maxLength.")
        return v

    @validator("allowedValues", each_item=True)
    def _validate_allowed_values_item(
        cls, v: ParameterStringValue, values: dict[str, Any]
    ) -> ParameterStringValue:
        min_length = values.get("minLength")
        if min_length is not None:
            if len(v) < min_length:
                raise ValueError("Value is shorter than minLength.")
        max_length = values.get("maxLength")
        if max_length is not None:
            if len(v) > max_length:
                raise ValueError("Value is longer than maxLength.")
        return v

    @validator("default")
    def _validate_default(
        cls, v: ParameterStringValue, values: dict[str, Any]
    ) -> ParameterStringValue:
        min_length = values.get("minLength")
        if min_length is not None:
            if len(v) < min_length:
                raise ValueError("Value is shorter than minLength.")
        max_length = values.get("maxLength")
        if max_length is not None:
            if len(v) > max_length:
                raise ValueError("Value is longer than maxLength.")

        allowed_values = values.get("allowedValues")
        if allowed_values is not None:
            if v not in allowed_values:
                raise ValueError("Must be an allowed value.")
        return v

    @root_validator
    def _validate_user_interface_compatibility(cls, values: dict[str, Any]) -> dict[str, Any]:
        # validate that the user interface control is compatible with the value constraints
        if values.get("userInterface"):
            user_interface_control = values["userInterface"].control
            if values.get("allowedValues") and user_interface_control in (
                StringUserInterfaceControl.LINE_EDIT,
                StringUserInterfaceControl.MULTILINE_EDIT,
            ):
                raise ValueError(
                    f"User interface control {user_interface_control.name} cannot be used when 'allowedValues' is provided"
                )
            if (
                not values.get("allowedValues")
                and user_interface_control == StringUserInterfaceControl.DROPDOWN_LIST
            ):
                raise ValueError(
                    f"User interface control {user_interface_control.name} requires that 'allowedValues' be provided"
                )
            if user_interface_control == StringUserInterfaceControl.CHECK_BOX:
                allowed_values = set(v.upper() for v in values.get("allowedValues", []))
                if allowed_values not in ALLOWED_VALUES_FOR_CHECK_BOX:
                    raise ValueError(
                        f"User interface control {user_interface_control.name} requires that 'allowedValues' be "
                        + f"one of {ALLOWED_VALUES_FOR_CHECK_BOX} (case and order insensitive)"
                    )
        return values

    # override
    def _check_constraints(self, value: Any) -> None:
        if value is None:
            raise ValueError(f"No value given for {self.name}.")
        if not isinstance(value, str):
            raise ValueError(f"Value ({value}) for parameter {self.name} must be string type.")
        if self.allowedValues and value not in self.allowedValues:
            raise ValueError(f"Parameter {self.name} value ({value}) not in allowedValues.")
        if self.minLength and len(value) < self.minLength:
            raise ValueError(
                f"Value ({value}), with length {len(value)}, for parameter {self.name} value must be at least {self.minLength} characters."
            )
        if self.maxLength and self.maxLength < len(value):
            raise ValueError(
                f"Value ({value}), with length {len(value)}, for parameter {self.name} value must be at most {self.maxLength} characters."
            )


class PathUserInterfaceControl(str, Enum):
    CHOOSE_INPUT_FILE = "CHOOSE_INPUT_FILE"
    CHOOSE_OUTPUT_FILE = "CHOOSE_OUTPUT_FILE"
    CHOOSE_DIRECTORY = "CHOOSE_DIRECTORY"
    DROPDOWN_LIST = "DROPDOWN_LIST"
    HIDDEN = "HIDDEN"


class JobPathParameterDefinitionObjectType(str, Enum):
    FILE = "FILE"
    DIRECTORY = "DIRECTORY"


class JobPathParameterDefinitionDataFlow(str, Enum):
    NONE = "NONE"
    IN = "IN"
    OUT = "OUT"
    INOUT = "INOUT"


class JobPathParameterDefinitionFileFilter(OpenJDModel_v2023_09):
    """User interface attributes for a single file filter in a file choice dialog.

    Attributes:
        label (UserInterfaceLabelStringValue): The label for this file filter, e.g. "Image Files" or "All Files".
        patterns (list[FileDialogFilterPatternStringValue]): A list of possible glob file patterns for files to show.
            e.g. ["*.jpg", "*.png"]
    """

    label: UserInterfaceLabelStringValue
    patterns: FileDialogFilterPatternStringValueList


if TYPE_CHECKING:
    JobPathParameterDefinitionFileFilterList = list[JobPathParameterDefinitionFileFilter]
else:
    JobPathParameterDefinitionFileFilterList = conlist(
        JobPathParameterDefinitionFileFilter, min_items=1, max_items=20
    )


class JobPathParameterDefinitionUserInterface(OpenJDModel_v2023_09):
    """User interface attributes for a job path parameter.

    Attributes:
        control (PathUserInterfaceControl): The user interface control to use when editing this parameter.
        label (Optional[UserInterfaceLabelStringValue]): The label to display for the user interface control. Defaults
            to the `name` of the parameter.
        groupLabel (Optional[UserInterfaceLabelStringValue]): The label of the group box to place the user interface
            control in.
        fileFilters (Optional[list[JobPathParameterDefinitionFileFilter]]): Can be provided when the uiControl is “CHOOSE_INPUT_FILE” or
            “CHOOSE_OUTPUT_FILE”. Defines the file filters that are shown in the file choice dialog.
            Maximum of 20 filters.
        fileFilterDefault (Optional[JobPathParameterDefinitionFileFilter]): Can be provided when the uiControl is “CHOOSE_INPUT_FILE” or
            “CHOOSE_OUTPUT_FILE”. The default file filter that’s shown in the file choice dialog.
    """

    control: PathUserInterfaceControl
    label: Optional[UserInterfaceLabelStringValue]
    groupLabel: Optional[UserInterfaceLabelStringValue]
    fileFilters: Optional[JobPathParameterDefinitionFileFilterList]
    fileFilterDefault: Optional[JobPathParameterDefinitionFileFilter]


class JobPathParameterDefinition(OpenJDModel_v2023_09, JobParameterInterface):
    """A Job Parameter of type path.

    Attributes:
        name (Identifier): A name by which the parameter is referenced.
        type (JobParameterType.PATH): discriminator to identify the type of the parameter
        objectType (Optional[JobPathParameterDefinitionObjectType]): The type of object the path represents,
            either a FILE or a DIRECTORY.
        dataFlow (Optional[JobPathParameterDefinitionDataFlow]): Whether the object the path represents
            serves as input, output or both for the job.
        userInterface (Optional[JobPathParameterDefinitionUserInterface]): User interface properties
            for this parameter
        description (Optional[Description]): A free form string that can be used to describe
            the parameter. It has no functional purpose, but may appear in UI elements.
        default (Optional[ParameterStringValue]): Default value for the parameter if a value
            is not provided.
        allowedValues (Optional[AllowedParameterStringValueList]): Explicit list of values that the
            parameter is allowed to take on.
        minLength (Optional[int]): Minimum string length of the parameter value.
        maxLength (Optional[int]): Maximum string length of the parameter value.
    """

    name: Identifier
    type: Literal[JobParameterType.PATH]
    objectType: Optional[JobPathParameterDefinitionObjectType]
    dataFlow: Optional[JobPathParameterDefinitionDataFlow]
    userInterface: Optional[JobPathParameterDefinitionUserInterface]
    description: Optional[Description] = None
    # Note: Ordering of the following fields is essential for the validators to work correctly.
    minLength: Optional[StrictInt] = None  # noqa: N815
    maxLength: Optional[StrictInt] = None  # noqa: N815
    allowedValues: Optional[AllowedParameterStringValueList] = None  # noqa: N815
    default: Optional[ParameterStringValue] = None

    _template_variable_definitions = DefinesTemplateVariables(
        defines={
            TemplateVariableDef(prefix="|Param.", resolves=ResolutionScope.SESSION),
            TemplateVariableDef(prefix="|RawParam.", resolves=ResolutionScope.TEMPLATE),
        },
        field="name",
    )
    _template_variable_sources = {"__export__": {"__self__"}}
    _job_creation_metadata = JobCreationMetadata(
        create_as=JobCreateAsMetadata(model=JobParameter),
        exclude_fields={
            "name",
            "objectType",
            "dataFlow",
            "userInterface",
            "minLength",
            "maxLength",
            "allowedValues",
            "default",
        },
        adds_fields=lambda key, this, symtab: {
            "value": symtab[f"RawParam.{cast(JobStringParameterDefinition,this).name}"]
        },
    )

    @validator("minLength")
    def _validate_min_length(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v <= 0:
            raise ValueError("Required: 0 < minLength.")
        return v

    @validator("maxLength")
    def _validate_max_length(cls, v: Optional[int], values: dict[str, Any]) -> Optional[int]:
        if v is None:
            return v
        if v <= 0:
            raise ValueError("Required: 0 < maxLength.")
        min_length = values.get("minLength")
        if min_length is None:
            return v
        if min_length > v:
            raise ValueError("Required: minLength <= maxLength.")
        return v

    @validator("allowedValues", each_item=True)
    def _validate_allowed_values_item(
        cls, v: ParameterStringValue, values: dict[str, Any]
    ) -> ParameterStringValue:
        min_length = values.get("minLength")
        if min_length is not None:
            if len(v) < min_length:
                raise ValueError("Value is shorter than minLength.")
        max_length = values.get("maxLength")
        if max_length is not None:
            if len(v) > max_length:
                raise ValueError("Value is longer than maxLength.")
        return v

    @validator("default")
    def _validate_default(
        cls, v: ParameterStringValue, values: dict[str, Any]
    ) -> ParameterStringValue:
        min_length = values.get("minLength")
        if min_length is not None:
            if len(v) < min_length:
                raise ValueError("Value is shorter than minLength.")
        max_length = values.get("maxLength")
        if max_length is not None:
            if len(v) > max_length:
                raise ValueError("Value is longer than maxLength.")

        allowed_values = values.get("allowedValues")
        if allowed_values is not None:
            if v not in allowed_values:
                raise ValueError("Must be an allowed value.")
        return v

    @root_validator
    def _validate_user_interface_compatibility(cls, values: dict[str, Any]) -> dict[str, Any]:
        # validate that the user interface control is compatible with the value constraints
        if values.get("userInterface"):
            user_interface_control = values["userInterface"].control
            if values.get("allowedValues") and user_interface_control in (
                PathUserInterfaceControl.CHOOSE_INPUT_FILE,
                PathUserInterfaceControl.CHOOSE_OUTPUT_FILE,
                PathUserInterfaceControl.CHOOSE_DIRECTORY,
            ):
                raise ValueError(
                    f"User interface control {user_interface_control.name} cannot be used when 'allowedValues' is provided"
                )
            if (
                not values.get("allowedValues")
                and user_interface_control == PathUserInterfaceControl.DROPDOWN_LIST
            ):
                raise ValueError(
                    f"User interface control {user_interface_control.name} requires that 'allowedValues' be provided"
                )
            if (
                values["userInterface"].fileFilters or values["userInterface"].fileFilterDefault
            ) and user_interface_control not in [
                PathUserInterfaceControl.CHOOSE_INPUT_FILE,
                PathUserInterfaceControl.CHOOSE_OUTPUT_FILE,
            ]:
                raise ValueError(
                    f"User interface control {user_interface_control.name} cannot be used when 'fileFilters'"
                    + " or 'fileFilterDefault is provided"
                )
            if (
                values.get("objectType") == JobPathParameterDefinitionObjectType.FILE
                and user_interface_control == PathUserInterfaceControl.CHOOSE_DIRECTORY
            ):
                raise ValueError(
                    f"User interface control {user_interface_control.name} cannot be used with 'objectType' of FILE"
                )
            if values.get(
                "objectType"
            ) == JobPathParameterDefinitionObjectType.DIRECTORY and user_interface_control in [
                PathUserInterfaceControl.CHOOSE_INPUT_FILE,
                PathUserInterfaceControl.CHOOSE_OUTPUT_FILE,
            ]:
                raise ValueError(
                    f"User interface control {user_interface_control.name} cannot be used with 'objectType' of DIRECTORY"
                )

        return values

    # override
    def _check_constraints(self, value: Any) -> None:
        if value is None:
            raise ValueError(f"No value given for {self.name}.")
        if not isinstance(value, str):
            raise ValueError(f"Value ({value}) for parameter {self.name} must be string type.")
        if self.allowedValues and value not in self.allowedValues:
            raise ValueError(f"Parameter {self.name} value ({value}) not in allowedValues.")
        if self.minLength and len(value) < self.minLength:
            raise ValueError(
                f"Value ({value}), with length {len(value)}, for parameter {self.name} value must be at least {self.minLength} characters."
            )
        if self.maxLength and self.maxLength < len(value):
            raise ValueError(
                f"Value ({value}), with length {len(value)}, for parameter {self.name} value must be at most {self.maxLength} characters."
            )


class IntUserInterfaceControl(str, Enum):
    SPIN_BOX = "SPIN_BOX"
    DROPDOWN_LIST = "DROPDOWN_LIST"
    HIDDEN = "HIDDEN"


class JobIntParameterDefinitionUserInterface(OpenJDModel_v2023_09):
    """User interface attributes for a job int parameter.

    Attributes:
        control (IntUserInterfaceControl): The user interface control to use when editing this parameter.
        label (Optional[UserInterfaceLabelStringValue]): The label to display for the user interface control. Defaults
            to the `name` of the parameter.
        groupLabel (Optional[UserInterfaceLabelStringValue]): The label of the group box to place the user interface
            control in.
        singleStepDelta (Optional[PositiveInt]): How much the value changes for a single step modification, such
            as selecting an up or down arrow in the user interface control.
    """

    control: IntUserInterfaceControl
    label: Optional[UserInterfaceLabelStringValue]
    groupLabel: Optional[UserInterfaceLabelStringValue]
    singleStepDelta: Optional[PositiveInt]


class JobIntParameterDefinition(OpenJDModel_v2023_09):
    """A Job Parameter of type integer.

    Attributes:
        name (Identifier): A name by which the parameter is referenced.
        type (JobParameterType.INT): discriminator to identify the type of the parameter
        userInterface (Optional[JobIntParameterDefinitionUserInterface]): User interface properties
            for this parameter
        description (Optional[Description]): A free form string that can be used to describe
            the parameter. It has no functional purpose, but may appear in UI elements.
        default (Optional[int]): Default value for the parameter if a value
            is not provided.
        allowedValues (Optional[AllowedIntParameterList]): Explicit list of values that the
            parameter is allowed to take on.
        minValue (Optional[int]): Minimum value that the parameter is allowed to be.
        maxValue (Optional[int]): Minimum value that the parameter is allowed to be.
    """

    name: Identifier
    type: Literal[JobParameterType.INT]
    userInterface: Optional[JobIntParameterDefinitionUserInterface]
    description: Optional[Description] = None
    # Note: Ordering of the following fields is essential for the validators to work correctly.
    minValue: Optional[int] = None  # noqa: N815
    maxValue: Optional[int] = None  # noqa: N815
    allowedValues: Optional[AllowedIntParameterList] = None  # noqa: N815
    default: Optional[int] = None

    _template_variable_definitions = DefinesTemplateVariables(
        defines={
            TemplateVariableDef(prefix="|Param.", resolves=ResolutionScope.TEMPLATE),
            TemplateVariableDef(prefix="|RawParam.", resolves=ResolutionScope.TEMPLATE),
        },
        field="name",
    )
    _template_variable_sources = {"__export__": {"__self__"}}
    _job_creation_metadata = JobCreationMetadata(
        create_as=JobCreateAsMetadata(model=JobParameter),
        exclude_fields={
            "name",
            "userInterface",
            "minValue",
            "maxValue",
            "allowedValues",
            "default",
        },
        adds_fields=lambda key, this, symtab: {
            "value": symtab[f"RawParam.{cast(JobIntParameterDefinition,this).name}"]
        },
    )

    @classmethod
    def _precheck_is_int_type(cls, v: Any) -> None:
        # prevent floats, bools, and other types from coercing into an int.
        # strings that contain floats are handled by pydantic's checks.
        if not isinstance(v, (int, str)) or isinstance(v, bool):
            raise ValueError("Value must be an integer or integer string.")

    @validator("minValue", pre=True)
    def _validate_min_value_type(cls, v: Optional[Any]) -> Optional[Any]:
        if v is None:
            return v
        cls._precheck_is_int_type(v)
        return v

    @validator("maxValue", pre=True)
    def _validate_max_value_type(cls, v: Optional[Any]) -> Optional[Any]:
        if v is None:
            return v
        cls._precheck_is_int_type(v)
        return v

    @validator("allowedValues", each_item=True, pre=True)
    def _validate_allowed_values_item_type(cls, v: Any) -> Optional[Any]:
        cls._precheck_is_int_type(v)
        return v

    @validator("default", pre=True)
    def _validate_default_value_type(cls, v: Optional[Any]) -> Optional[Any]:
        if v is None:
            return v
        cls._precheck_is_int_type(v)
        return v

    @validator("maxValue")
    def _validate_max_value(cls, v: Optional[int], values: dict[str, Any]) -> Optional[int]:
        if v is None:
            return v
        min_value = values.get("minValue")
        if min_value is None:
            return v
        if min_value > v:
            raise ValueError("Required: minValue <= maxValue.")
        return v

    @validator("allowedValues", each_item=True)
    def _validate_allowed_values_item(cls, v: int, values: dict[str, Any]) -> int:
        min_value = values.get("minValue")
        if min_value is not None:
            if v < min_value:
                raise ValueError("Value less than minValue.")
        max_value = values.get("maxValue")
        if max_value is not None:
            if v > max_value:
                raise ValueError("Value larger than maxValue.")
        return v

    @validator("default")
    def _validate_default(cls, v: int, values: dict[str, Any]) -> int:
        min_value = values.get("minValue")
        if min_value is not None:
            if v < min_value:
                raise ValueError("Value less than minValue.")
        max_value = values.get("maxValue")
        if max_value is not None:
            if v > max_value:
                raise ValueError("Value larger than maxValue.")

        allowed_values = values.get("allowedValues")
        if allowed_values is not None:
            if v not in allowed_values:
                raise ValueError("Must be an allowed value.")
        return v

    @root_validator
    def _validate_user_interface_compatibility(cls, values: dict[str, Any]) -> dict[str, Any]:
        # validate that the user interface control is compatible with the value constraints
        if values.get("userInterface"):
            user_interface_control = values["userInterface"].control
            if (
                values.get("allowedValues")
                and user_interface_control == IntUserInterfaceControl.SPIN_BOX
            ):
                raise ValueError(
                    f"User interface control {user_interface_control.name} cannot be used when 'allowedValues' is provided"
                )
            if (
                not values.get("allowedValues")
                and user_interface_control == IntUserInterfaceControl.DROPDOWN_LIST
            ):
                raise ValueError(
                    f"User interface control {user_interface_control.name} requires that 'allowedValues' be provided"
                )
            if (
                values["userInterface"].singleStepDelta
                and user_interface_control != IntUserInterfaceControl.SPIN_BOX
            ):
                raise ValueError(
                    f"User interface control {user_interface_control.name} cannot be used when 'singleStepDelta' is provided"
                )

        return values

    # override
    def _check_constraints(self, value: Any) -> None:
        if value is None:
            raise ValueError(f"No value given for {self.name}.")
        if not isinstance(value, (str, int)) or isinstance(value, bool):
            raise ValueError(
                f"Value ({value}) for parameter {self.name} must an integer or integer string."
            )
        if isinstance(value, str):
            try:
                value = int(value)
            except ValueError:
                raise ValueError(
                    f"Value ({value}) for parameter {self.name} must an integer or integer string."
                )
        if self.allowedValues and value not in self.allowedValues:
            raise ValueError(f"Parameter {self.name} value ({value}) not in allowedValues.")
        if self.minValue and value < self.minValue:
            raise ValueError(
                f"Value ({value}) for parameter {self.name} must be at least {self.minValue}."
            )
        if self.maxValue and self.maxValue < value:
            raise ValueError(
                f"Value ({value}) for parameter {self.name} must be at most {self.maxValue}."
            )


class FloatUserInterfaceControl(str, Enum):
    SPIN_BOX = "SPIN_BOX"
    DROPDOWN_LIST = "DROPDOWN_LIST"
    HIDDEN = "HIDDEN"


class JobFloatParameterDefinitionUserInterface(OpenJDModel_v2023_09):
    """User interface attributes for a job float parameter.

    Attributes:
        control (FloatUserInterfaceControl): The user interface control to use when editing this parameter.
        label (Optional[UserInterfaceLabelStringValue]): The label to display for the user interface control. Defaults
            to the `name` of the parameter.
        groupLabel (Optional[UserInterfaceLabelStringValue]): The label of the group box to place the user interface
            control in.
        decimals (Optional[PositiveInt]): decimals — This is the number of places editable after the decimal point.
            If decimals is not provided then an adaptive decimal mode will be used.
        singleStepDelta (Optional[PositiveFloat]): How much the value changes for a single step modification, such
            as selecting an up or down arrow in the user interface control. If decimals is provided, this is an
            absolute value, otherwise it is the fraction of the current value to use as an adaptive step.
    """

    control: FloatUserInterfaceControl
    label: Optional[UserInterfaceLabelStringValue]
    groupLabel: Optional[UserInterfaceLabelStringValue]
    decimals: Optional[PositiveInt]
    singleStepDelta: Optional[PositiveFloat]


class JobFloatParameterDefinition(OpenJDModel_v2023_09):
    """A Job Parameter of type float.

    Attributes:
        name (Identifier): A name by which the parameter is referenced.
        type (JobParameterType.FLOAT): discriminator to identify the type of the parameter
        userInterface (Optional[JobFloatParameterDefinitionUserInterface]): User interface properties
            for this parameter.
        description (Optional[Description]): A free form string that can be used to describe
            the parameter. It has no functional purpose, but may appear in UI elements.
        default (Optional[Decimal]): Default value for the parameter if a value
            is not provided.
        allowedValues (Optional[AllowedFloatParameterList]): Explicit list of values that the
            parameter is allowed to take on.
        minValue (Optional[Decimal]): Minimum value that the parameter is allowed to be.
        maxValue (Optional[Decimal]): Minimum value that the parameter is allowed to be.
    """

    name: Identifier
    type: Literal[JobParameterType.FLOAT]
    userInterface: Optional[JobFloatParameterDefinitionUserInterface]
    description: Optional[Description] = None
    # Note: Ordering of the following fields is essential for the validators to work correctly.
    minValue: Optional[Decimal] = None  # noqa: N815
    maxValue: Optional[Decimal] = None  # noqa: N815
    allowedValues: Optional[AllowedFloatParameterList] = None  # noqa: N815
    default: Optional[Decimal] = None

    _template_variable_definitions = DefinesTemplateVariables(
        defines={
            TemplateVariableDef(prefix="|Param.", resolves=ResolutionScope.TEMPLATE),
            TemplateVariableDef(prefix="|RawParam.", resolves=ResolutionScope.TEMPLATE),
        },
        field="name",
    )
    _template_variable_sources = {"__export__": {"__self__"}}
    _job_creation_metadata = JobCreationMetadata(
        create_as=JobCreateAsMetadata(model=JobParameter),
        exclude_fields={
            "name",
            "userInterface",
            "minValue",
            "maxValue",
            "allowedValues",
            "default",
        },
        adds_fields=lambda key, this, symtab: {
            "value": symtab[f"RawParam.{cast(JobFloatParameterDefinition,this).name}"]
        },
    )

    @validator("maxValue")
    def _validate_max_value(cls, v: Optional[Decimal], values: dict[str, Any]) -> Optional[Decimal]:
        if v is None:
            return v
        min_value = values.get("minValue")
        if min_value is None:
            return v
        if min_value > v:
            raise ValueError("Required: minValue <= maxValue.")
        return v

    @validator("allowedValues", each_item=True)
    def _validate_allowed_values_item(cls, v: Decimal, values: dict[str, Any]) -> Decimal:
        min_value = values.get("minValue")
        if min_value is not None:
            if v < min_value:
                raise ValueError("Value less than minValue.")
        max_value = values.get("maxValue")
        if max_value is not None:
            if v > max_value:
                raise ValueError("Value larger than maxValue.")
        return v

    @validator("default")
    def _validate_default(cls, v: Decimal, values: dict[str, Any]) -> Decimal:
        min_value = values.get("minValue")
        if min_value is not None:
            if v < min_value:
                raise ValueError("Value less than minValue.")
        max_value = values.get("maxValue")
        if max_value is not None:
            if v > max_value:
                raise ValueError("Value larger than maxValue.")

        allowed_values = values.get("allowedValues")
        if allowed_values is not None:
            if v not in allowed_values:
                raise ValueError("Must be an allowed value.")
        return v

    @root_validator
    def _validate_user_interface_compatibility(cls, values: dict[str, Any]) -> dict[str, Any]:
        # validate that the user interface control is compatible with the value constraints
        if values.get("userInterface"):
            user_interface_control = values["userInterface"].control
            if (
                values.get("allowedValues")
                and user_interface_control == FloatUserInterfaceControl.SPIN_BOX
            ):
                raise ValueError(
                    f"User interface control {user_interface_control.name} cannot be used when 'allowedValues' is provided"
                )
            if (
                not values.get("allowedValues")
                and user_interface_control == FloatUserInterfaceControl.DROPDOWN_LIST
            ):
                raise ValueError(
                    f"User interface control {user_interface_control.name} requires that 'allowedValues' be provided"
                )
            if (
                values["userInterface"].singleStepDelta
                and user_interface_control != FloatUserInterfaceControl.SPIN_BOX
            ):
                raise ValueError(
                    f"User interface control {user_interface_control.name} cannot be used when 'singleStepDelta' is provided"
                )

        return values

    # override
    def _check_constraints(self, value: Any) -> None:
        if value is None:
            raise ValueError(f"No value given for {self.name}.")
        if not isinstance(value, (str, int, float, Decimal)) or isinstance(value, bool):
            raise ValueError(f"Value ({value}) for parameter {self.name} must be floating point.")
        try:
            # note: translate to string so that floats don't round poorly.
            #  e.g. Decimal(1.2) == Decimal('1.1999999999999999555910790149937383830547332763671875')
            #       Decimal(str(1.2)) == Decimal('1.2')
            value = Decimal(str(value))
        except InvalidOperation:
            raise ValueError(f"Value ({value}) for parameter {self.name} must be floating point.")
        if self.allowedValues and value not in self.allowedValues:
            raise ValueError(f"Parameter {self.name} value ({value}) not in allowedValues.")
        if self.minValue and value < self.minValue:
            raise ValueError(
                f"Value ({value}) for parameter {self.name} must be at least {self.minValue}."
            )
        if self.maxValue and self.maxValue < value:
            raise ValueError(
                f"Value ({value}) for parameter {self.name} must be at most {self.maxValue}."
            )


# ==================================================================
# =================== Step Requires/Capabilities ===================
# ==================================================================

STANDARD_ATTRIBUTE_CAPABILITIES: dict[str, Any] = {
    "attr.worker.os.family": {"values": {"linux", "windows", "macos"}, "multivalued": False},
    "attr.worker.cpu.arch": {"values": {"x86_64", "arm64"}, "multivalued": False},
}
_STANDARD_ATTRIBUTE_CAPABILITIES_NAMES = list(STANDARD_ATTRIBUTE_CAPABILITIES.keys())
STANDARD_AMOUNT_CAPABILITIES: dict[str, Any] = {
    "amount.worker.vcpu": {},
    "amount.worker.memory": {},
    "amount.worker.gpu": {},
    "amount.worker.gpu.memory": {},
    "amount.worker.disk.scratch": {},
}
_STANDARD_AMOUNT_CAPABILITIES_NAMES = list(STANDARD_AMOUNT_CAPABILITIES.keys())


class AmountCapabilityName(FormatString):
    """The name of an amount capability."""

    _min_length = 1
    _max_length = 100


class AttributeCapabilityName(FormatString):
    """The name of an attrubute capability."""

    _min_length = 1
    _max_length = 100


class AttributeCapabilityValue(FormatString):
    _min_length = 1


if TYPE_CHECKING:
    AttributeCapabilityList = list[AttributeCapabilityValue]
else:
    AttributeCapabilityList = conlist(AttributeCapabilityValue, min_items=1, max_items=50)


class AmountRequirement(OpenJDModel_v2023_09):
    """An amount requirement entry for a step, to specify which
    quanifiable host capabilities the step requires.

    Amount capabilities are the mechanism for defining
    a counted or measured attribute of the worker for a Step
    to require, such as number of CPUs, amount of memory, or
    number of licenses from a shared network license server.

    The values for amount capabilities can be either integer
    or floating point. The latter enables use cases like sharing
    VCPUs up to a limit, e.g. setting "amount.worker.vcpu" to 0.25.

    Note: This is the instantiated version of AttributeRequirementTemplate
    """

    name: str
    min: Optional[Decimal]
    max: Optional[Decimal]

    @root_validator(pre=True)
    def validate_concrete_model(cls, values: dict[str, Any]) -> dict[str, Any]:
        # Reuse the AmountRequirementTemplate validation. Because all the template
        # variables have been substituted, it will now run validation it couldn't
        # before.
        AmountRequirementTemplate.parse_obj(values)
        return values


class AmountRequirementTemplate(OpenJDModel_v2023_09):
    """An amount requirement entry for a step, to specify which
    quanifiable host capabilities the step requires.

    Amount capabilities are the mechanism for defining
    a counted or measured attribute of the worker for a Step
    to require, such as number of CPUs, amount of memory, or
    number of licenses from a shared network license server.

    The values for amount capabilities can be either integer
    or floating point. The latter enables use cases like sharing
    VCPUs up to a limit, e.g. setting "amount.worker.vcpu" to 0.25.
    """

    name: AmountCapabilityName
    min: Optional[Decimal]
    max: Optional[Decimal]

    _job_creation_metadata = JobCreationMetadata(
        create_as=JobCreateAsMetadata(model=AmountRequirement),
        resolve_fields={
            "name",
        },
    )

    @validator("name")
    def _validate_name(cls, v: str) -> str:
        validate_amount_capability_name(
            capability_name=v, standard_capabilities=_STANDARD_AMOUNT_CAPABILITIES_NAMES
        )
        return v

    @validator("min")
    def _validate_min(cls, v: Optional[Decimal], values: dict[str, Any]) -> Optional[Decimal]:
        if v is None:
            return v
        if v < 0:
            raise ValueError(f"Value {v} must be zero or greater")
        return v

    @validator("max")
    def _validate_max(cls, v: Optional[Decimal], values: dict[str, Any]) -> Optional[Decimal]:
        if v is None:
            return v
        if v <= 0:
            raise ValueError("Value must be greater than 0")
        v_min = values.get("min")
        if v_min is not None and v_min > v:
            raise ValueError("Value for 'max' must be greater or equal to 'min'")
        return v

    @root_validator(pre=True)
    def _validate_has_one_optional(cls, values: dict[str, Any]) -> dict[str, Any]:
        if not ("min" in values or "max" in values):
            raise ValueError("At least one of 'min' or 'max' must be defined.")
        return values


class AttributeRequirement(OpenJDModel_v2023_09):
    """An attribute requirement entry for a step, to specify which
    property or abstract host capabilities the step requires.

    Attribute capabilities are the mechanism for defining an
    attribute of the worker for a Step to require, such as its
    CPU architecture.

    Note: This is the instantiated version of AttributeRequirementTemplate
    """

    name: str
    anyOf: Optional[list[str]]
    allOf: Optional[list[str]]

    @root_validator(pre=True)
    def validate_concrete_model(cls, values: dict[str, Any]) -> dict[str, Any]:
        # Reuse the AttributeRequirementTemplate validation. Because all the template
        # variables have been substituted, it will now run validation it couldn't
        # before.
        AttributeRequirementTemplate.parse_obj(values)
        return values


class AttributeRequirementTemplate(OpenJDModel_v2023_09):
    """An attribute requirement entry for a step, to specify which
    host capabilities the step requires from.

    Attribute capabilities are the mechanism for defining an
    attribute of the worker for a Step to require, such as its
    CPU architecture.
    """

    name: AttributeCapabilityName
    anyOf: Optional[AttributeCapabilityList]  # noqa: N815
    allOf: Optional[AttributeCapabilityList]  # noqa: N815

    _job_creation_metadata = JobCreationMetadata(
        create_as=JobCreateAsMetadata(model=AttributeRequirement),
        resolve_fields={"name", "anyOf", "allOf"},
    )

    _attribute_capability_value_regex: ClassVar[re.Pattern] = re.compile(
        r"(?-m:^(?:[a-zA-Z_][a-zA-Z0-9_\-]*)\Z)"
    )
    _attribute_capability_value_max_length: int = 100

    @validator("name")
    def _validate_name(cls, v: str) -> str:
        validate_attribute_capability_name(
            capability_name=v, standard_capabilities=_STANDARD_ATTRIBUTE_CAPABILITIES_NAMES
        )
        return v

    @classmethod
    def _validate_attribute_list(
        cls, v: AttributeCapabilityList, values: dict[str, Any], is_allof: bool
    ) -> None:
        try:
            capability_name = values["name"].lower()
        except KeyError:
            # Just return as though there is no error. The missing name field
            # will be reported by the validation of 'name'
            return
        standard_capability = STANDARD_ATTRIBUTE_CAPABILITIES.get(capability_name, {})
        if standard_capability:
            if is_allof and not standard_capability["multivalued"] and len(v) > 1:
                raise ValueError(
                    f"Standard capability {capability_name} cannot have multiple values at once."
                )
            for item in v:
                # If it has expressions like "{{ Param.SomeValue }}", will
                # validate when those values are substituted.
                if len(item.expressions) > 0:
                    continue
                if item not in standard_capability["values"]:
                    raise ValueError(
                        f"Values must be from {' '.join(standard_capability['values'])}"
                    )
        else:
            for item in v:
                # If it has expressions like "{{ Param.SomeValue }}", will
                # validate when those values are substituted.
                if len(item.expressions) > 0:
                    continue
                if not cls._attribute_capability_value_regex.match(item):
                    raise ValueError(f"Value {item} is not a valid attribute capability value.")
                if len(item) > cls._attribute_capability_value_max_length:
                    raise ValueError(
                        f"Value {item} exceeds {cls._attribute_capability_value_max_length} character length limit."
                    )

    @validator("allOf")
    def _validate_allof(
        cls, v: Optional[AttributeCapabilityList], values: dict[str, Any]
    ) -> Optional[AttributeCapabilityList]:
        if v is None:
            return v
        cls._validate_attribute_list(v, values, True)
        return v

    @validator("anyOf")
    def _validate_anyof(
        cls, v: Optional[AttributeCapabilityList], values: dict[str, Any]
    ) -> Optional[AttributeCapabilityList]:
        if v is None:
            return v
        cls._validate_attribute_list(v, values, False)
        return v

    @root_validator(pre=True)
    def _validate_has_one_optional(cls, values: dict[str, Any]) -> dict[str, Any]:
        if not ("anyOf" in values or "allOf" in values):
            raise ValueError("At least one of 'anyOf' or 'allOf' must be defined.")
        return values


class HostRequirements(OpenJDModel_v2023_09):
    amounts: Optional[list[AmountRequirement]] = None
    attributes: Optional[list[AttributeRequirement]] = None


class HostRequirementsTemplate(OpenJDModel_v2023_09):
    amounts: Optional[list[AmountRequirementTemplate]] = None
    attributes: Optional[list[AttributeRequirementTemplate]] = None

    _job_creation_metadata = JobCreationMetadata(
        create_as=JobCreateAsMetadata(model=HostRequirements)
    )

    _max_allowed_requirements: int = 50

    @validator("amounts")
    def _validate_amounts(
        cls, v: Optional[list[AmountRequirementTemplate]]
    ) -> Optional[list[AmountRequirementTemplate]]:
        if v is None:
            return v
        if len(v) == 0:
            raise ValueError("List must contain at least one element or not be defined.")
        return v

    @validator("attributes")
    def _validate_attributes(
        cls, v: Optional[list[AttributeRequirementTemplate]]
    ) -> Optional[list[AttributeRequirementTemplate]]:
        if v is None:
            return v
        if len(v) == 0:
            raise ValueError("List must contain at least one element or not be defined.")
        return v

    @root_validator
    def _validate(cls, values: dict[str, Any]) -> dict[str, Any]:
        if not ("amounts" in values or "attributes" in values):
            raise ValueError(
                "Must define at least one of 'amounts' or 'attributes' if defining this property."
            )
        amounts = values.get("amounts")
        attributes = values.get("attributes")
        total_amounts = len(amounts) if amounts is not None else 0
        total_attributes = len(attributes) if attributes is not None else 0
        total = total_amounts + total_attributes
        if total > cls._max_allowed_requirements:
            raise ValueError(
                f"The total number of requirements must not exceed {cls._max_allowed_requirements}. {total} requirements defined."
            )
        return values


# ==================================================================
# ========================== Template Types ========================
# ==================================================================


class StepDependency(OpenJDModel_v2023_09):
    dependsOn: StepName


if TYPE_CHECKING:
    StepEnvironmentList = list[Environment]
    StepDependenciesList = list[StepDependency]
else:
    StepEnvironmentList = conlist(Environment, min_items=1)
    StepDependenciesList = conlist(StepDependency, min_items=1)


# Target model for a StepTemplate when instantiating a job.
class Step(OpenJDModel_v2023_09):
    name: StepName
    script: StepScript
    description: Optional[Description] = None
    stepEnvironments: Optional[StepEnvironmentList] = None
    parameterSpace: Optional[StepParameterSpace] = None  # noqa: N815
    hostRequirements: Optional[HostRequirements] = None
    dependencies: Optional[StepDependenciesList] = None


class StepTemplate(OpenJDModel_v2023_09):
    """Definition of a single Step within a Job Template.

    Attributes:
        name (StepName): The name by which the Step is referenced
        description (Optional[str]): A free form string that can be used to describe the Step.
            It has no functional purpose, but may appear in UI elements.
        script (StepScript): The information on what Actions to perform when running Tasks
            of the Step.
        stepEnvironments (Optional[StepEnvironmentList]): A list of the environments required to
            run Tasks that use this Step Script. This is an ordered list; environments are
            started in the order provided, and ended in the reverse order.
        parameterSpace (Optional[StepParameterSpaceDefinition]): Definition of the Step's parameter space.
        hostRequirements (Optional[HostRequirementsTemplate]): The capabilities that a host requires for
            this Step to run on it.
        dependencies (Optional[StepDependenciesList]): A list of this Step's dependencies.
    """

    name: StepName
    description: Optional[Description] = None
    script: StepScript
    stepEnvironments: Optional[StepEnvironmentList] = None
    parameterSpace: Optional[StepParameterSpaceDefinition] = None  # noqa: N815
    hostRequirements: Optional[HostRequirementsTemplate] = None
    dependencies: Optional[StepDependenciesList] = None

    _template_variable_sources = {
        "script": {"__self__", "parameterSpace"},
        "stepEnvironments": {"__self__"},
    }
    _job_creation_metadata = JobCreationMetadata(create_as=JobCreateAsMetadata(model=Step))

    @validator("dependencies")
    def _validate_no_duplicate_deps(
        cls, v: Optional[StepDependenciesList]
    ) -> Optional[StepDependenciesList]:
        if v is None:
            return v
        deps = set(v)
        if len(deps) != len(v):
            raise ValueError("Duplicate dependencies are not allowed.")
        return v

    @validator("stepEnvironments")
    def _unique_environment_names(
        cls, v: Optional[StepEnvironmentList]
    ) -> Optional[StepEnvironmentList]:
        if v is not None:
            return validate_unique_elements(v, item_value=lambda v: v.name, property="name")
        return v

    @root_validator
    def _validate_no_self_dependency(cls, values: dict[str, Any]) -> dict[str, Any]:
        # Dependency of the step upon itself is not allowed.
        deps: StepDependenciesList = values.get("dependencies", [])
        if not deps:
            return values
        stepname = values.get("name")
        if any(dep.dependsOn == stepname for dep in deps):
            raise ValueError("A step cannot depend upon itself.")
        return values


if TYPE_CHECKING:
    StepTemplateList = list[StepTemplate]
    JobParameterDefinitionList = list[
        Union[
            JobIntParameterDefinition,
            JobFloatParameterDefinition,
            JobStringParameterDefinition,
            JobPathParameterDefinition,
        ]
    ]
    JobEnvironmentsList = list[Environment]
else:
    StepTemplateList = conlist(StepTemplate, min_items=1)
    JobParameterDefinitionList = conlist(
        Annotated[
            Union[
                JobIntParameterDefinition,
                JobFloatParameterDefinition,
                JobStringParameterDefinition,
                JobPathParameterDefinition,
            ],
            Field(..., discriminator="type"),
        ],
        min_items=1,
        max_items=50,
    )
    JobEnvironmentsList = conlist(Environment, min_items=1)


JobParameters = dict[Identifier, JobParameter]


# Target model for a JobTemplate when instantiating a job.
class Job(OpenJDModel_v2023_09):
    name: JobName
    steps: list[Step]
    description: Optional[Description] = None
    parameters: Optional[JobParameters] = None
    jobEnvironments: Optional[JobEnvironmentsList] = None


class JobTemplate(OpenJDModel_v2023_09):
    """Definition of an Open Job Description Job Template.

    Attributes:
        specificationVersion (TemplateSpecificationVersion.v2023_09): The OpenJD schema version
            whose data model this follows.
        name (JobTemplateName): The name of Jobs constructed by this template.
        steps (StepTemplateList): The Step Templates that comprise the Job Template.
        description (Optional[str]): A free form string that can be used to describe the Job.
            It has no functional purpose, but may appear in UI elements.
        parameterDefinitions (Optional[JobParameterDefinitionList]): The job parameters that are available to Jobs
            created with this template.
        jobEnvironments (Optional[JobEnvironmentsList]): Definitions of Environments that are run at the start
            of every Session running Tasks in this Job.
        schemaStr (Optional[str]): Ignored. Allowed for compatibility with json editing IDEs.
    """

    specificationVersion: Literal[TemplateSpecificationVersion.JOBTEMPLATE_v2023_09]  # noqa: N815
    name: JobTemplateName
    steps: StepTemplateList
    description: Optional[Description] = None
    parameterDefinitions: Optional[JobParameterDefinitionList] = None
    jobEnvironments: Optional[JobEnvironmentsList] = None
    # Note: Cannot call the field 'schema'; it masks a base class field
    schemaStr: Optional[str] = Field(None, alias="$schema")  # noqa: N815

    _template_variable_scope = ResolutionScope.TEMPLATE
    _template_variable_sources = {
        "name": {"parameterDefinitions"},
        "steps": {"parameterDefinitions"},
        "jobEnvironments": {"parameterDefinitions"},
    }
    _job_creation_metadata = JobCreationMetadata(
        create_as=JobCreateAsMetadata(model=Job),
        resolve_fields={"name"},
        exclude_fields={"specificationVersion", "schemaStr"},
        reshape_field_to_dict={"parameterDefinitions": "name"},
        rename_fields={"parameterDefinitions": "parameters"},
    )

    @validator("steps")
    def _unique_step_names(cls, v: StepTemplateList) -> StepTemplateList:
        return validate_unique_elements(v, item_value=lambda v: v.name, property="name")

    @validator("parameterDefinitions")
    def _unique_parameter_names(
        cls, v: Optional[JobParameterDefinitionList]
    ) -> Optional[JobParameterDefinitionList]:
        if v is not None:
            return validate_unique_elements(v, item_value=lambda v: v.name, property="name")
        return v

    @validator("jobEnvironments")
    def _unique_environment_names(
        cls, v: Optional[JobEnvironmentsList]
    ) -> Optional[JobEnvironmentsList]:
        if v is not None:
            return validate_unique_elements(v, item_value=lambda v: v.name, property="name")
        return v

    @classmethod
    def _root_template_prevalidator(cls, values: dict[str, Any]) -> dict[str, Any]:
        # The name of this validator is very important. It is specifically looked for
        # in the _parse_model function to run this validation as a pre-root-validator
        # without the usual short-circuit of pre-root-validators that pydantic does.
        errors = prevalidate_model_template_variable_references(
            cast(Type[OpenJDModel], cls), values
        )
        if errors:
            raise ValidationError(errors, JobTemplate)
        return values

    @root_validator
    def _validate_no_step_dependency_cycles(cls, values: dict[str, Any]) -> dict[str, Any]:
        depgraph = dict[str, set[str]]()
        steplist = values.get("steps", [])
        for step in steplist:
            if step.dependencies is not None:
                dependsOn = set[str](dep.dependsOn for dep in step.dependencies)
                depgraph[step.name] = dependsOn

        sorter = TopologicalSorter(depgraph)
        try:
            # Raises CycleError
            sorter.prepare()
        except CycleError as exc:
            cycle = " -> ".join(exc.args[1])
            raise ValueError(f"Step dependencies form a cycle: {cycle}") from None

        return values

    @root_validator
    def _validate_step_deps_exist(cls, values: dict[str, Any]) -> dict[str, Any]:
        # Check that the deps referenced by all steps actually exist

        steplist = values.get("steps", [])
        if not steplist:
            return values

        errors = list[ErrorWrapper]()
        stepnames = set[str](step.name for step in steplist)
        for i, step in enumerate(steplist):
            if step.dependencies is not None:
                for j, dep in enumerate(step.dependencies):
                    if dep.dependsOn not in stepnames:
                        errors.append(
                            ErrorWrapper(
                                ValueError(f"Unknown step '{dep.dependsOn}'"),
                                # The path to the problematic dependsOn value
                                ("step", i, "dependencies", j, "dependsOn"),
                            )
                        )

        if errors:
            raise ValidationError(errors, JobTemplate)

        return values

    @root_validator
    def _validate_env_names_dont_match_step_env_names(
        cls, values: dict[str, Any]
    ) -> dict[str, Any]:
        # Check that if we have job-level Environments defined that none of the defined Step-level
        # environments have the same name.
        # Names must be unique between Steps & Jobs.

        steplist = values.get("steps", [])
        if not steplist:
            return values

        envlist = values.get("jobEnvironments", [])
        if not envlist:
            return values

        job_env_names = set(env.name for env in cast(JobEnvironmentsList, envlist))

        errors = list[ErrorWrapper]()
        for i, step in enumerate(steplist):
            if step.stepEnvironments is not None:
                for j, env in enumerate(step.stepEnvironments):
                    if env.name in job_env_names:
                        errors.append(
                            ErrorWrapper(
                                ValueError(
                                    f"Name {env.name} must differ from the names of Environments defined at the root of the template."
                                ),
                                # The path to the problematic environment name
                                ("step", i, "stepEnvironments", j, "name"),
                            )
                        )

        if errors:
            raise ValidationError(errors, JobTemplate)

        return values


class EnvironmentTemplate(OpenJDModel_v2023_09):
    """Definition of an Open Job Description Environment Template.

    Attributes:
        specificationVersion (TemplateSpecificationVersion.ENVIRONMENT_v2023_09): The OpenJD schema version
            whose data model this follows.
        parameterDefinitions (Optional[JobParameterDefinitionList]): The job parameters that are available for use
            within this template, and that must have values defined for them when creating jobs while this
            environment template is included.
        environment (Environment): The definition of the Environment that is applied.
    """

    specificationVersion: Literal[TemplateSpecificationVersion.ENVIRONMENT_v2023_09]
    parameterDefinitions: Optional[JobParameterDefinitionList] = None
    environment: Environment

    _template_variable_scope = ResolutionScope.TEMPLATE
    _template_variable_sources = {
        "environment": {"parameterDefinitions"},
    }

    @validator("parameterDefinitions")
    def _unique_parameter_names(
        cls, v: Optional[JobParameterDefinitionList]
    ) -> Optional[JobParameterDefinitionList]:
        if v is not None:
            return validate_unique_elements(v, item_value=lambda v: v.name, property="name")
        return v

    @classmethod
    def _root_template_prevalidator(cls, values: dict[str, Any]) -> dict[str, Any]:
        # The name of this validator is very important. It is specifically looked for
        # in the _parse_model function to run this validation as a pre-root-validator
        # without the usual short-circuit of pre-root-validators that pydantic does.
        errors = prevalidate_model_template_variable_references(
            cast(Type[OpenJDModel], cls), values
        )
        if errors:
            raise ValidationError(errors, EnvironmentTemplate)
        return values
