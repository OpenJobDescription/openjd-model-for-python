# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import re
import secrets
import string
from decimal import Decimal, InvalidOperation
from enum import Enum
from graphlib import CycleError, TopologicalSorter
from typing import Any, ClassVar, Literal, Optional, Type, Union, cast, Iterable
from typing_extensions import Annotated, Self

from pydantic import (
    field_validator,
    model_validator,
    ConfigDict,
    Discriminator,
    StringConstraints,
    Field,
    PositiveInt,
    PositiveFloat,
    StrictBool,
    StrictInt,
    Tag,
    ValidationError,
    ValidationInfo,
)
from pydantic_core import InitErrorDetails
from pydantic.fields import ModelPrivateAttr

from .._format_strings import FormatString
from .._errors import ExpressionError, TokenError
from .._capabilities import (
    validate_amount_capability_name,
    validate_attribute_capability_name,
)
from .._internal import (
    CombinationExpressionParser,
    validate_step_parameter_space_dimensions,
    validate_step_parameter_space_chunk_constraint,
    validate_unique_elements,
    validate_int_fmtstring_field,
    validate_float_fmtstring_field,
    validate_list_field,
)
from .._internal._variable_reference_validation import (
    prevalidate_model_template_variable_references,
)
from .._range_expr import IntRangeExpr
from .._symbol_table import SymbolTable
from .._types import (
    DefinesTemplateVariables,
    JobCreateAsMetadata,
    JobCreationMetadata,
    JobParameterInterface,
    ModelParsingContextInterface,
    OpenJDModel,
    ResolutionScope,
    SpecificationRevision,
    TemplateSpecificationVersion,
    TemplateVariableDef,
)

# Error message constants
_ALLOWED_VALUES_NONE_ERROR = "allowedValues cannot be None. The field must contain at least one value or be omitted entirely."
_VALUE_LESS_THAN_MIN_ERROR = "Value less than minValue."
_VALUE_LARGER_THAN_MAX_ERROR = "Value larger than maxValue."

# Interpreter syntax sugar configuration: (command, extension, arg_prefix)
_INTERPRETER_MAP: dict[str, tuple[str, str, list[str]]] = {
    "python": ("python", ".py", []),
    "bash": ("bash", ".sh", []),
    "cmd": ("cmd", ".bat", ["/C"]),
    "powershell": ("powershell", ".ps1", ["-File"]),
    "node": ("node", ".js", []),
}


class ModelParsingContext(ModelParsingContextInterface):
    """Context required while parsing an OpenJDModel. An instance of this class
    must be provided when calling model_validate.

        OpenJDModelSubclass.model_validate(data, context=ModelParsingContext())

    Individual validators receive this value as ValidationInfo.context.
    """

    def __init__(self, *, supported_extensions: Optional[Iterable[str]] = None) -> None:
        super().__init__(
            spec_rev=SpecificationRevision.v2023_09, supported_extensions=supported_extensions
        )


class OpenJDModel_v2023_09(OpenJDModel):  # noqa: N801
    revision = SpecificationRevision.v2023_09
    model_parsing_context_type = ModelParsingContext

    @staticmethod
    def supported_extension_names() -> set[str]:
        """Returns the list of all extension names supported by the 2023-09 specification version."""
        return {v.value for v in ExtensionName}


class ExtensionName(str, Enum):
    """Enumeration of all extensions supported for the 2023-09 specification revision.
    This appears in the 'extensions' list property of all model instances.
    """

    # https://github.com/OpenJobDescription/openjd-specifications/blob/mainline/rfcs/0001-task-chunking.md
    TASK_CHUNKING = "TASK_CHUNKING"
    # Extension that enables the use of openjd_redacted_env for setting environment variables with redacted values in logs
    REDACTED_ENV_VARS = "REDACTED_ENV_VARS"
    # Extension for increased limits, format strings in timeout/min/max/notifyPeriodInSeconds,
    # endOfLine control, and script interpreter syntax sugar
    FEATURE_BUNDLE_1 = "FEATURE_BUNDLE_1"
    # Expression Language (RFCs 0005/0006/0007): rich {{ }} expressions, function
    # library, and extended job-parameter types. Evaluated by the Rust openjd-expr
    # engine via the openjd._openjd_rs bindings.
    EXPR = "EXPR"
    # Environment Wrap Actions (RFC 0008): onWrapEnvEnter/onWrapTaskRun/onWrapEnvExit
    # on <EnvironmentActions>. Requires EXPR.
    WRAP_ACTIONS = "WRAP_ACTIONS"


ExtensionNameList = Annotated[list[str], Field(min_length=1)]


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
_standard_string_regex = rf"(?-m:^[^{_Cc_characters}]+\z)"

# Latin alphanumeric, starting with a letter
_identifier_regex = r"(?-m:^[A-Za-z_][A-Za-z0-9_]*\z)"

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
    rf"\\\":@`|=]+)\z)"
)


class JobTemplateName(FormatString):
    _min_length = 1
    # Max length is validated after resolution in Job model, not here
    # because the template name can contain format strings
    # All unicode except the [Cc] (control characters) category
    _regex = f"(?-m:^[^{_Cc_characters}]+\\Z)"

    def __new__(cls, value: str, *, context: ModelParsingContextInterface = ModelParsingContext()):
        return super().__new__(cls, value, context=context)


JobName = Annotated[
    str,
    StringConstraints(min_length=1, max_length=512, strict=True, pattern=_standard_string_regex),
]
Identifier = Annotated[
    str, StringConstraints(min_length=1, max_length=512, strict=True, pattern=_identifier_regex)
]
Description = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=2048,
        strict=True,
        # All unicode except the [Cc] (control characters) category
        # Allow CR, LF, and TAB.
        pattern=f"(?-m:^(?:[^{_Cc_characters}]|[\r\n\t])+\\z)",
    ),
]
EnvironmentName = Annotated[
    str,
    StringConstraints(min_length=1, max_length=512, strict=True, pattern=_standard_string_regex),
]
StepName = Annotated[
    str,
    StringConstraints(min_length=1, max_length=512, strict=True, pattern=_standard_string_regex),
]
ParameterStringValue = Annotated[str, StringConstraints(min_length=0, max_length=1024, strict=True)]

# ==================================================================
# ============================= Script types =======================
# ==================================================================


# ---------------------------- Action type -------------------------


class CommandString(FormatString):
    _min_length = 1
    # All unicode except the [Cc] (control characters) category
    _regex = f"(?-m:^[^{_Cc_characters}]+\\Z)"

    def __new__(cls, value: str, *, context: ModelParsingContextInterface = ModelParsingContext()):
        return super().__new__(cls, value, context=context)


class ArgString(FormatString):
    # All unicode except the [Cc] (control characters) category, plus the line
    # breaks LF (\n) and CR (\r) so multi-line inline scripts can be passed as
    # arguments (e.g. `python -c "<multi-line>"`). Matches the openjd-rs
    # reference, which accepts LF/CR (but not TAB or other control chars) in
    # args with no extension required.
    _regex = f"(?-m:^(?:[^{_Cc_characters}]|[\r\n])*\\Z)"

    def __new__(cls, value: str, *, context: ModelParsingContextInterface = ModelParsingContext()):
        return super().__new__(cls, value, context=context)


class CancelationMode(str, Enum):
    NOTIFY_THEN_TERMINATE = "NOTIFY_THEN_TERMINATE"
    TERMINATE = "TERMINATE"


NotifyPeriodType = Annotated[int, Field(ge=1, le=600)]


def _validate_notify_period_value(
    v: Any, info: ValidationInfo
) -> Optional[Union[int, FormatString]]:
    """Shared notifyPeriodInSeconds validation for
    CancelationMethodNotifyThenTerminate and CancelationMethodDeferred."""
    if v is None:
        return v
    context = cast(Optional[ModelParsingContext], info.context)
    if isinstance(v, str):
        if context and "FEATURE_BUNDLE_1" not in context.extensions:
            # Try to parse as int, fail if not
            try:
                return int(v)
            except ValueError:
                raise ValueError(
                    "notifyPeriodInSeconds as a format string requires the FEATURE_BUNDLE_1 extension."
                )
        return validate_int_fmtstring_field(v, ge=1, context=context)
    if isinstance(v, int):
        if v < 1 or v > 600:
            raise ValueError("notifyPeriodInSeconds must be between 1 and 600")
        return v
    return v


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
    notifyPeriodInSeconds: Optional[Union[NotifyPeriodType, FormatString]] = None  # noqa: N815

    # A FormatString notifyPeriodInSeconds is NOT resolved at job creation:
    # it is carried through unresolved and resolved at run time by the
    # session, matching openjd-rs (job/create_job/instantiate.rs clones the
    # cancelation object unresolved into the Job). This is what lets RFC 0008
    # wrap hooks forward "{{WrappedAction.Cancelation.NotifyPeriodInSeconds}}",
    # whose symbols only exist at run time.
    _job_creation_metadata = JobCreationMetadata()

    @field_validator("notifyPeriodInSeconds", mode="before")
    @classmethod
    def _validate_notify_period(
        cls, v: Any, info: ValidationInfo
    ) -> Optional[Union[int, FormatString]]:
        return _validate_notify_period_value(v, info)


class CancelationMethodTerminate(OpenJDModel_v2023_09):
    """Terminate cancelation mode for an Action.

    On Posix systems — Send SIGKILL to the entire process tree when a cancel is requested.

    On Windows systems - Terminate the entire process tree when a cancel is requested.

    Attributes:
        mode ("TERMINATE"): The mode of the cancelation to use.
    """

    mode: Literal[CancelationMode.TERMINATE]


class CancelationMethodDeferred(OpenJDModel_v2023_09):
    """A cancelation whose ``mode`` is a format string, resolved at run
    time (Template Schemas 5.3, FEATURE_BUNDLE_1 extension).

    What is the problem this solves?

    Format strings in general are *already* delay-processed: when a template
    says ``args: ["{{WrappedAction.Command}}"]``, the parser just stores
    "this is a format string" and the value gets resolved much later, inside
    a running session, right before the action launches — that's when the
    runtime seeds the ``WrappedAction.*`` variables from the action being
    wrapped. "Resolve later" is the normal pipeline for every other field.

    ``mode`` is different because it isn't a normal value field — it's the
    *schema selector*. The parser needs to know TERMINATE vs
    NOTIFY_THEN_TERMINATE at parse time to decide what shape of object it's
    even reading (only one of them allows ``notifyPeriodInSeconds``). So the
    "which shape?" decision happens at parse time, but a forwarded value
    like ``mode: "{{WrappedAction.Cancelation.Mode}}"`` only exists at run
    time — that mismatch made round-trip cancelation forwarding in RFC 0008
    wrap hooks impossible (pydantic's discriminated union rejected the
    template with "does not match any of the expected tags").

    The fix is this class: the parser accepts a format string in ``mode``
    as a third, "decided later" state (gated on the FEATURE_BUNDLE_1
    extension), and the shape decision moves to resolution time, right
    before the action runs:

    1. The runtime seeds ``WrappedAction.Cancelation.Mode`` from the
       wrapped action (``"TERMINATE"``, ``"NOTIFY_THEN_TERMINATE"``, or
       ``None``).
    2. It resolves the ``mode:`` expression against that.
    3. ``"TERMINATE"``/``"NOTIFY_THEN_TERMINATE"`` — the cancelation block
       now acts as that method, and its sibling fields are validated
       against that shape. ``None`` (null, whole-field expressions only) —
       the whole ``cancelation:`` block is treated as never written.
       Anything else — the action fails.

    Static validation is *not* deferred: at parse time the validator still
    checks the expression is well-formed and that ``WrappedAction.*`` is
    only referenced inside wrap hooks. Any format string is accepted —
    normal interpolation like ``"{{Prefix}}_THEN_TERMINATE"`` is permitted;
    only the resolved value is constrained. You just can't know *which* of
    the two modes it'll be until the wrapped action is in front of you —
    which is inherent to forwarding: the same wrap environment gets reused
    across many steps whose cancelation settings differ.

    Mirrors ``CancelationMode::DeferredMode`` in openjd-rs. See
    openjd-specifications Template Schemas 5.3 and RFC 0008 "Cancelation
    behavior".

    Attributes:
        mode (FormatString): A format string resolving to "TERMINATE" or
            "NOTIFY_THEN_TERMINATE"; a whole-field interpolation expression
            may also resolve to null.
        notifyPeriodInSeconds (Optional[Union[int, FormatString]]): As on
            CancelationMethodNotifyThenTerminate; only meaningful when the
            mode resolves to NOTIFY_THEN_TERMINATE, and must resolve to
            null when the mode resolves to TERMINATE.
    """

    mode: FormatString
    notifyPeriodInSeconds: Optional[Union[NotifyPeriodType, FormatString]] = None  # noqa: N815

    # Neither `mode` nor a FormatString `notifyPeriodInSeconds` is resolved
    # at job creation: the whole deferred cancelation object is carried
    # through unresolved and resolved at run time by the session, matching
    # openjd-rs (job/create_job/instantiate.rs). Run-time-only symbols such
    # as WrappedAction.Cancelation.* are how RFC 0008 wrap hooks forward the
    # wrapped action's cancelation.
    _job_creation_metadata = JobCreationMetadata()

    @field_validator("mode", mode="before")
    @classmethod
    def _validate_mode(cls, v: Any, info: ValidationInfo) -> Any:
        if isinstance(v, str):
            context = cast(Optional[ModelParsingContext], info.context)
            if context and "FEATURE_BUNDLE_1" not in context.extensions:
                raise ValueError(
                    "a format string in cancelation mode requires the FEATURE_BUNDLE_1 extension."
                )
            # Any format string is permitted (normal format string
            # behavior, Template Schemas 5.3); the resolved value is
            # checked against the two mode names at run time. Only a
            # whole-field expression additionally gets string? null
            # semantics (a null result drops the cancelation object).
        return v

    @field_validator("notifyPeriodInSeconds", mode="before")
    @classmethod
    def _validate_notify_period(
        cls, v: Any, info: ValidationInfo
    ) -> Optional[Union[int, FormatString]]:
        return _validate_notify_period_value(v, info)


def _cancelation_discriminator(v: Any) -> Optional[str]:
    """Callable discriminator for the cancelation union: routes the two
    literal modes to their fixed-shape classes and a format-string mode to
    :class:`CancelationMethodDeferred` (see that class's docstring for why
    the mode decision can be deferred at all)."""
    mode = v.get("mode") if isinstance(v, dict) else getattr(v, "mode", None)
    if isinstance(mode, CancelationMode):
        mode = mode.value
    if isinstance(mode, str):
        if mode == CancelationMode.NOTIFY_THEN_TERMINATE.value:
            return "notify_then_terminate"
        if mode == CancelationMode.TERMINATE.value:
            return "terminate"
        if "{{" in mode:
            return "deferred"
    if isinstance(v, CancelationMethodNotifyThenTerminate):
        return "notify_then_terminate"
    if isinstance(v, CancelationMethodTerminate):
        return "terminate"
    if isinstance(v, CancelationMethodDeferred):
        return "deferred"
    return None


CancelationMethod = Annotated[
    Union[
        Annotated[CancelationMethodNotifyThenTerminate, Tag("notify_then_terminate")],
        Annotated[CancelationMethodTerminate, Tag("terminate")],
        Annotated[CancelationMethodDeferred, Tag("deferred")],
    ],
    Discriminator(_cancelation_discriminator),
]


ArgListType = Annotated[list[ArgString], Field(min_length=1)]

# WRAP_ACTIONS (RFC 0008) wrap-hook field names on EnvironmentActions.
_WRAP_ACTION_FIELDS = ("onWrapEnvEnter", "onWrapTaskRun", "onWrapEnvExit")

# RFC 0008 single-wrap-layer rule. Mirrors the message emitted by openjd-rs
# (validate_v2023_09/wrap_actions.rs::SINGLE_WRAP_LAYER_MSG).
_SINGLE_WRAP_LAYER_MSG = (
    "only one environment in the session stack may define any of onWrapEnvEnter, "
    "onWrapTaskRun, onWrapEnvExit (RFC 0008)."
)


def _env_defines_wrap_hook(env: Any) -> bool:
    """True if the given Environment's script defines any WRAP_ACTIONS hook.

    Used by the single-wrap-layer validation to count the wrap-defining
    environments reachable in a session stack.
    """
    script = getattr(env, "script", None)
    actions = getattr(script, "actions", None) if script is not None else None
    if actions is None:
        return False
    return any(getattr(actions, name, None) is not None for name in _WRAP_ACTION_FIELDS)


# RFC 0008 wrapped-context variable namespaces and where each may be
# referenced. `WrappedAction.*` is available in all three wrap hooks;
# `WrappedEnv.*` only in the env-enter/exit hooks; `WrappedStep.*` only in the
# task-run hook. None of them may be referenced outside the wrap hooks.
_WRAPPED_NAMESPACES = ("WrappedAction", "WrappedEnv", "WrappedStep")
_WRAP_HOOK_ALLOWED_NAMESPACES = {
    "onWrapEnvEnter": {"WrappedAction", "WrappedEnv"},
    "onWrapEnvExit": {"WrappedAction", "WrappedEnv"},
    "onWrapTaskRun": {"WrappedAction", "WrappedStep"},
}


def _action_referenced_namespaces(action: Any) -> set[str]:
    """Collect the set of wrapped-context namespaces (``WrappedAction`` /
    ``WrappedEnv`` / ``WrappedStep``) referenced by an Action's format strings.

    Inspects every FormatString-bearing field of the Action: ``command``, each
    of ``args``, and ``timeout`` (which is a FormatString under the
    FEATURE_BUNDLE_1 extension, and a plain int otherwise — non-FormatString
    values are skipped).
    """
    referenced: set[str] = set()
    if action is None:
        return referenced
    format_strings = [
        getattr(action, "command", None),
        *(getattr(action, "args", None) or []),
        getattr(action, "timeout", None),
    ]
    for fs in format_strings:
        if not isinstance(fs, FormatString):
            continue
        for expr_info in fs.expressions:
            expr = expr_info.expression
            if expr is None:
                continue
            for symbol in expr.accessed_symbols:
                namespace = symbol.split(".", 1)[0]
                if namespace in _WRAPPED_NAMESPACES:
                    referenced.add(namespace)
    return referenced


class Action(OpenJDModel_v2023_09):
    """An Action to run.

    Attributes:
        command (FormatString): The command/executable that will be run.
        args (Optional[list[FormatString]]): The arguments that are provided to the command
            when it is run.
        timeout (Optional[int]): Maximum allowed runtime of the Action in seconds.
            Can be a format string with FEATURE_BUNDLE_1 extension.
            Default: No timeout
        cancelation (Optional[CancelationMethod]): If defined, provides details
            regarding how this action should be canceled. One of
            CancelationMethodNotifyThenTerminate, CancelationMethodTerminate, or
            CancelationMethodDeferred (a format-string mode resolved
            at run time; FEATURE_BUNDLE_1).
            Default: CancelationMethodTerminate
    """

    command: CommandString
    args: Optional[ArgListType] = None
    timeout: Optional[Union[PositiveInt, FormatString]] = None
    cancelation: Optional[CancelationMethod] = None

    # A FormatString `timeout` is NOT resolved at job creation: it is carried
    # through job instantiation unresolved and resolved at run time by the
    # session, matching openjd-rs (job/create_job/instantiate.rs clones
    # timeout and cancelation unresolved into the Job, and the session
    # resolves them right before the action runs). This is what lets RFC 0008
    # wrap hooks forward "{{WrappedAction.Timeout}}" — those symbols only
    # exist at run time.
    _job_creation_metadata = JobCreationMetadata()

    # `timeout` and `cancelation` (its notifyPeriodInSeconds and a deferred
    # format-string mode) still VALIDATE at template scope: no Session.*, no
    # Env.File.*/Task.File.*, and no host-context functions (matching
    # openjd-rs format_strings.rs). The RFC 0008 wrap hooks may forward the
    # wrapped action's values ("{{WrappedAction.Timeout}}"): the
    # WrappedAction.* symbols are injected per-hook at every scope via
    # EnvironmentActions._template_field_inject, and openjd-rs's
    # symtab-filter preserves them for run time.
    _template_field_scopes = {
        "timeout": ResolutionScope.TEMPLATE,
        "cancelation": ResolutionScope.TEMPLATE,
    }

    @field_validator("timeout", mode="before")
    @classmethod
    def _validate_timeout(cls, v: Any, info: ValidationInfo) -> Optional[Union[int, FormatString]]:
        if v is None:
            return v
        context = cast(Optional[ModelParsingContext], info.context)
        if isinstance(v, str):
            if context and "FEATURE_BUNDLE_1" not in context.extensions:
                # Try to parse as int, fail if not
                try:
                    return int(v)
                except ValueError:
                    raise ValueError(
                        "timeout as a format string requires the FEATURE_BUNDLE_1 extension."
                    )
            return validate_int_fmtstring_field(v, ge=1, context=context)
        if isinstance(v, int):
            if v < 1:
                raise ValueError("timeout must be a positive integer")
            return v
        return v


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
        onWrapEnvEnter (Optional[Action]): WRAP_ACTIONS — runs instead of the
            onEnter of every inner environment while this environment is active.
        onWrapTaskRun (Optional[Action]): WRAP_ACTIONS — runs instead of every
            task's onRun while this environment is active.
        onWrapEnvExit (Optional[Action]): WRAP_ACTIONS — runs instead of the
            onExit of every inner environment while this environment is active.

    Note: Must define at least one of onEnter or onExit (or, with the
    WRAP_ACTIONS extension, the wrap actions). The three wrap actions are
    all-or-nothing and require the WRAP_ACTIONS extension (which itself
    requires EXPR).
    """

    onEnter: Optional[Action] = Field(None)  # noqa: N815
    onExit: Optional[Action] = Field(None)  # noqa: N815
    # WRAP_ACTIONS extension (RFC 0008). Gated in the validator below.
    onWrapEnvEnter: Optional[Action] = Field(None)  # noqa: N815
    onWrapTaskRun: Optional[Action] = Field(None)  # noqa: N815
    onWrapEnvExit: Optional[Action] = Field(None)  # noqa: N815

    # RFC 0008: the wrapped-context variables exist only within their wrap
    # hook's action, seeded by the runtime when the hook runs in place of the
    # wrapped action. WrappedAction.* is available in all three hooks;
    # WrappedEnv.Name only in the env-enter/exit hooks; WrappedStep.Name only
    # in the task-run hook.
    #
    # WrappedAction.* is injected at every scope so a hook's template-scoped
    # fields (timeout/cancelation) can round-trip forward the wrapped
    # action's values ("{{WrappedAction.Timeout}}",
    # "{{WrappedAction.Cancelation.Mode}}"). WrappedEnv.Name /
    # WrappedStep.Name are injected at SESSION scope only: a hook's
    # command/args may reference them, but its timeout/cancelation may not —
    # matching openjd-rs (format_strings.rs validates hook
    # timeout/cancelation against template symbols + WrappedAction.* only).
    _WRAPPED_ACTION_SYMBOLS: ClassVar[set[str]] = {
        "|WrappedAction.Command",
        "|WrappedAction.Args",
        "|WrappedAction.Environment",
        "|WrappedAction.Timeout",
        "|WrappedAction.Cancelation.Mode",
        "|WrappedAction.Cancelation.NotifyPeriodInSeconds",
    }
    _template_field_inject = {
        "onWrapEnvEnter": _WRAPPED_ACTION_SYMBOLS,
        "onWrapEnvExit": _WRAPPED_ACTION_SYMBOLS,
        "onWrapTaskRun": _WRAPPED_ACTION_SYMBOLS,
    }
    _template_field_inject_session = {
        "onWrapEnvEnter": {"|WrappedEnv.Name"},
        "onWrapEnvExit": {"|WrappedEnv.Name"},
        "onWrapTaskRun": {"|WrappedStep.Name"},
    }

    @model_validator(mode="before")
    @classmethod
    def _requires_oneof(cls, values: dict[str, Any], info: ValidationInfo) -> dict[str, Any]:
        """A validator that runs on the model data before parsing.

        Enforces, for the WRAP_ACTIONS extension (RFC 0008):
        - wrap actions require the WRAP_ACTIONS extension to be declared;
        - WRAP_ACTIONS requires the EXPR extension (hard prerequisite);
        - the three wrap actions are all-or-nothing.
        Otherwise preserves the legacy "must define onEnter or onExit" rule.
        """
        if not isinstance(values, dict):
            raise ValueError("Expected a dictionary of values")

        context = cast(Optional[ModelParsingContext], info.context) if info else None
        extensions = context.extensions if context else set()

        wrap_values = {name: values.get(name) for name in _WRAP_ACTION_FIELDS}
        any_wrap = any(v is not None for v in wrap_values.values())

        if any_wrap:
            # Extension gating is a template-decode concern and only applies
            # when a parsing context is present. During job instantiation
            # (create_job re-validates the model without a ModelParsingContext)
            # the template has already been validated at decode time, so the
            # extension-requirement checks are skipped then -- mirroring the
            # `if context` guard the other extension gates in this module use.
            if context is not None:
                if "WRAP_ACTIONS" not in extensions:
                    raise ValueError(
                        "The onWrapEnvEnter, onWrapTaskRun, and onWrapEnvExit actions "
                        "require the WRAP_ACTIONS extension."
                    )
                if "EXPR" not in extensions:
                    raise ValueError("The WRAP_ACTIONS extension requires the EXPR extension.")
            if not all(v is not None for v in wrap_values.values()):
                raise ValueError(
                    "When any wrap action is defined, all of onWrapEnvEnter, "
                    "onWrapTaskRun, and onWrapEnvExit must be defined."
                )
            # A wrap environment with the three hooks satisfies the
            # "at least one action" requirement.
            return values

        on_enter = values.get("onEnter")
        on_exit = values.get("onExit")
        # Base 2023-09 (§3.5) requires onEnter whenever a script is present;
        # RFC 0008 relaxes this to "at least one action" when the
        # WRAP_ACTIONS extension is declared. The strict base rule is only
        # applied at template decode (context present) — job-instantiation
        # re-validation has no parsing context, matching the other extension
        # gates in this module.
        if context is not None and "WRAP_ACTIONS" not in extensions:
            if on_enter is None:
                raise ValueError("onEnter is required.")
        if on_enter is None and on_exit is None:
            raise ValueError("Must define one of: onEnter or onExit")
        return values

    @model_validator(mode="after")
    def _validate_wrapped_variable_scope(self, info: ValidationInfo) -> Self:
        # RFC 0008 scope rule: WrappedAction.* may be referenced only in the
        # three wrap hooks; WrappedEnv.* only in onWrapEnvEnter/onWrapEnvExit;
        # WrappedStep.* only in onWrapTaskRun. None of them may appear in the
        # ordinary onEnter/onExit actions. Schedulers must reject templates
        # that violate this; mirrors openjd-rs (which enforces it via its
        # per-scope function/symbol library split).
        context = cast(Optional[ModelParsingContext], info.context) if info else None
        extensions = context.extensions if context else set()
        if "EXPR" not in extensions:
            # Without EXPR the wrapped variables are never resolvable symbols,
            # and the format strings carry no accessed-symbol set to inspect.
            return self

        errors = list[InitErrorDetails]()
        for field_name in ("onEnter", "onExit", *_WRAP_ACTION_FIELDS):
            action = getattr(self, field_name, None)
            if action is None:
                continue
            allowed = _WRAP_HOOK_ALLOWED_NAMESPACES.get(field_name, set())
            referenced = _action_referenced_namespaces(action)
            for namespace in sorted(referenced - allowed):
                errors.append(
                    InitErrorDetails(
                        type="value_error",
                        loc=(field_name,),
                        ctx={
                            "error": ValueError(
                                f"The {namespace}.* variables may not be referenced in "
                                f"{field_name} (RFC 0008)."
                            )
                        },
                        input=action,
                    )
                )
        if errors:
            raise ValidationError.from_exception_data(self.__class__.__name__, errors)
        return self


# --------------------- Embedded Files type -------------------------


class EmbeddedFileTypes(str, Enum):
    TEXT = "TEXT"


class EndOfLine(str, Enum):
    """Line ending style for embedded files."""

    AUTO = "AUTO"
    LF = "LF"
    CRLF = "CRLF"


# TODO - regex of allowable filename characters
Filename = Annotated[str, StringConstraints(min_length=1, max_length=256, strict=True)]


class DataString(FormatString):
    _min_length = 1

    def __new__(cls, value: str, *, context: ModelParsingContextInterface = ModelParsingContext()):
        return super().__new__(cls, value, context=context)


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
        endOfLine (Optional[EndOfLine]): The line endings that the embedded file will have when
            written to disk. If AUTO the embedded file will have the default line endings of the
            host operating system. Requires FEATURE_BUNDLE_1 extension.
            Default: AUTO
    """

    name: Identifier
    type: Literal[EmbeddedFileTypes.TEXT]
    data: DataString
    filename: Optional[Filename] = None
    runnable: Optional[StrictBool] = None
    endOfLine: Optional[EndOfLine] = None  # noqa: N815

    _template_variable_definitions = DefinesTemplateVariables(
        defines={TemplateVariableDef(prefix="File.", resolves=ResolutionScope.SESSION)},
        field="name",
    )
    _template_variable_sources = {
        "__export__": {"__self__"},
        "data": {"__self__"},
    }

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str, info: ValidationInfo) -> str:
        context = cast(Optional[ModelParsingContext], info.context)
        max_len = 512 if context and "FEATURE_BUNDLE_1" in context.extensions else 64
        if len(v) > max_len:
            raise ValueError(f"name must be at most {max_len} characters long")
        return v

    @field_validator("filename")
    @classmethod
    def _validate_filename(cls, v: Optional[Filename], info: ValidationInfo) -> Optional[Filename]:
        if v is None:
            return v
        if "/" in v or "\\" in v:
            raise ValueError(
                "filename must be a basename only and cannot contain path separators ('/' or '\\\\')"
            )
        context = cast(Optional[ModelParsingContext], info.context)
        max_len = 256 if context and "FEATURE_BUNDLE_1" in context.extensions else 64
        if len(v) > max_len:
            raise ValueError(f"String must be at most {max_len} characters long")
        return v

    @field_validator("endOfLine")
    @classmethod
    def _validate_end_of_line(
        cls, v: Optional[EndOfLine], info: ValidationInfo
    ) -> Optional[EndOfLine]:
        if v is None:
            return v
        context = cast(Optional[ModelParsingContext], info.context)
        # Skip extension check if no context (e.g., during job creation from validated template)
        if context and "FEATURE_BUNDLE_1" not in context.extensions:
            raise ValueError("The endOfLine property requires the FEATURE_BUNDLE_1 extension.")
        return v


# --------------------- Script types ----------------------------

EmbeddedFiles = Annotated[list[EmbeddedFileText], Field(min_length=1)]


class ScriptInterpreter(str, Enum):
    """Script interpreter types for SimpleAction syntax sugar."""

    PYTHON = "python"
    BASH = "bash"
    CMD = "cmd"
    POWERSHELL = "powershell"
    NODE = "node"


LET_MAX_BINDINGS = 50
_LET_NAME_RE = re.compile(r"^[a-z_][A-Za-z0-9_]*$")


def parse_let_bindings(value: Any) -> list[tuple[str, str]]:
    """Parse a ``let`` field value (list of ``"name = expression"`` strings)
    into ``(name, expression)`` pairs. Raises ValueError on malformed input.
    """
    if not isinstance(value, list):
        raise ValueError("'let' must be a list of 'name = expression' bindings.")
    result: list[tuple[str, str]] = []
    for binding in value:
        if not isinstance(binding, str):
            raise ValueError("Each 'let' binding must be a 'name = expression' string.")
        name, sep, expr = binding.partition("=")
        if not sep:
            raise ValueError(
                f"A 'let' binding must be of the form 'name = expression': {binding!r}"
            )
        name = name.strip()
        expr = expr.strip()
        if not _LET_NAME_RE.match(name):
            raise ValueError(f"A 'let' binding name must be a valid identifier: {name!r}")
        if not expr:
            raise ValueError(f"A 'let' binding must define an expression: {binding!r}")
        result.append((name, expr))
    return result


def validate_let_field(value: Any, info: ValidationInfo, *, simple_action: bool = False) -> Any:
    """Validate a ``let`` field: EXPR (and FEATURE_BUNDLE_1 for SimpleAction)
    gating, non-empty, at most ``LET_MAX_BINDINGS``, each binding parses, and
    unique names. Symbol-reference and shadow rules are validated separately by
    the variable-reference prevalidator.
    """
    if value is None:
        return value
    context = cast(Optional[ModelParsingContext], info.context)
    if context and "EXPR" not in context.extensions:
        raise ValueError("The 'let' field requires the EXPR extension.")
    if simple_action and context and "FEATURE_BUNDLE_1" not in context.extensions:
        raise ValueError("A SimpleAction 'let' requires the FEATURE_BUNDLE_1 extension.")
    if isinstance(value, list) and len(value) == 0:
        raise ValueError("'let' must define at least one binding.")
    if isinstance(value, list) and len(value) > LET_MAX_BINDINGS:
        raise ValueError(f"'let' must define at most {LET_MAX_BINDINGS} bindings.")
    bindings = parse_let_bindings(value)
    names = [name for name, _ in bindings]
    if len(names) != len(set(names)):
        raise ValueError("'let' binding names must be unique.")
    return value


# §3.4: the maximum number of values a task parameter's range may take on.
# Not raised by FEATURE_BUNDLE_1 in 2023-09 (matches openjd-rs's
# EffectiveLimits.max_task_param_range_len).
_MAX_TASK_PARAM_RANGE_LEN = 1024


class NameIdentifierLengthMixin:
    """Applies the §7.1 identifier length limit — 64 characters, or 512 with
    FEATURE_BUNDLE_1 — to a model's ``name`` field.

    The static ``Identifier`` type constraint is the FEATURE_BUNDLE_1 maximum
    (512); this tightens it to 64 when the extension is not declared. The
    check is skipped when no parsing context is present (job-instantiation
    re-validation), matching the other extension gates in this module.
    """

    @field_validator("name", check_fields=False)
    @classmethod
    def _validate_name_identifier_length(cls, v: str, info: ValidationInfo) -> str:
        context = cast(Optional[ModelParsingContext], info.context)
        if context is None:
            return v
        max_len = 512 if "FEATURE_BUNDLE_1" in context.extensions else 64
        if len(v) > max_len:
            raise ValueError(f"name must be at most {max_len} characters long")
        return v


def validate_task_param_range_list_len(value: Any) -> Any:
    """§3.4: a task parameter's list-form range may define at most
    ``_MAX_TASK_PARAM_RANGE_LEN`` values."""
    if isinstance(value, list) and len(value) > _MAX_TASK_PARAM_RANGE_LEN:
        raise ValueError(f"range exceeds {_MAX_TASK_PARAM_RANGE_LEN} elements.")
    return value


class SimpleAction(OpenJDModel_v2023_09):
    """Syntax sugar for a script action with a specific interpreter.

    This is only available with the FEATURE_BUNDLE_1 extension.

    Attributes:
        script (DataString): The script content to execute.
        args (Optional[list[ArgString]]): Additional arguments to pass to the interpreter.
        timeout (Optional[Union[int, FormatString]]): Maximum allowed runtime in seconds.
            Can be a format string.
        cancelation (Optional[CancelationMethod]): How to cancel the action.
    """

    script: DataString
    args: Optional[ArgListType] = None
    timeout: Optional[Union[PositiveInt, FormatString]] = None
    cancelation: Optional[CancelationMethod] = None
    let: Optional[list[str]] = None

    # SimpleAction is syntax sugar that resolves to a StepScript (TASK scope),
    # so it sees the same session-scope variables, and its `let` names (in
    # __self__) are visible to its script and args.
    _template_variable_scope = ResolutionScope.TASK
    _template_variable_definitions = DefinesTemplateVariables(
        inject={
            f"|{ValueReferenceConstants.WORKING_DIRECTORY.value}",
            f"|{ValueReferenceConstants.HAS_PATH_MAPPING_RULES.value}",
            f"|{ValueReferenceConstants.PATH_MAPPING_RULES_FILE.value}",
        },
    )
    _template_variable_sources = {
        "script": {"__self__"},
        "args": {"__self__"},
    }

    # Parity with Action: `timeout` and `cancelation` VALIDATE at template
    # scope (no Session.*, no Env.File.*/Task.File.*, no host-context
    # functions) even though the desugared SimpleAction is otherwise
    # TASK-scoped. The desugared form is an ordinary Action, whose identical
    # fields validate at template scope — matching openjd-rs
    # (format_strings.rs validates these fields against the template symtab).
    _template_field_scopes = {
        "timeout": ResolutionScope.TEMPLATE,
        "cancelation": ResolutionScope.TEMPLATE,
    }

    @field_validator("let")
    @classmethod
    def _validate_let(cls, v: Any, info: ValidationInfo) -> Any:
        return validate_let_field(v, info, simple_action=True)

    @field_validator("timeout", mode="before")
    @classmethod
    def _validate_timeout(cls, v: Any, info: ValidationInfo) -> Optional[Union[int, FormatString]]:
        if v is None:
            return v
        context = cast(Optional[ModelParsingContext], info.context)
        if isinstance(v, str):
            # SimpleAction always requires FEATURE_BUNDLE_1, so format strings are allowed
            return validate_int_fmtstring_field(v, ge=1, context=context)
        if isinstance(v, int):
            if v < 1:
                raise ValueError("timeout must be a positive integer")
            return v
        return v


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
    let: Optional[list[str]] = None

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

    @field_validator("let")
    @classmethod
    def _validate_let(cls, v: Any, info: ValidationInfo) -> Any:
        return validate_let_field(v, info)

    @field_validator("embeddedFiles")
    @classmethod
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
    let: Optional[list[str]] = None

    _template_variable_definitions = DefinesTemplateVariables(
        symbol_prefix="|Env.",
        inject={
            f"|{ValueReferenceConstants.WORKING_DIRECTORY.value}",
            f"|{ValueReferenceConstants.HAS_PATH_MAPPING_RULES.value}",
            f"|{ValueReferenceConstants.PATH_MAPPING_RULES_FILE.value}",
            # The WRAP_ACTIONS (RFC 0008) WrappedAction.* / WrappedEnv.* /
            # WrappedStep.* variables are injected per wrap hook via
            # EnvironmentActions._template_field_inject, so they are visible
            # only within their hook's action — including its creation-scoped
            # timeout/cancelation fields for round-trip forwarding.
        },
    )
    _template_variable_sources = {
        "actions": {"embeddedFiles", "__self__"},
        "embeddedFiles": {"embeddedFiles", "__self__"},
    }

    @field_validator("let")
    @classmethod
    def _validate_let(cls, v: Any, info: ValidationInfo) -> Any:
        return validate_let_field(v, info)

    @field_validator("embeddedFiles")
    @classmethod
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
    def __new__(cls, value: str, *, context: ModelParsingContextInterface = ModelParsingContext()):
        return super().__new__(cls, value, context=context)


class TaskParameterType(str, Enum):
    INT = "INT"
    FLOAT = "FLOAT"
    STRING = "STRING"
    PATH = "PATH"
    CHUNK_INT = "CHUNK[INT]"


class RangeString(FormatString):
    _min_length = 1

    def __new__(cls, value: str, *, context: ModelParsingContextInterface = ModelParsingContext()):
        return super().__new__(cls, value, context=context)


# Note: Ordering within the Unions is important. Pydantic will try to match in
# the order given.
IntRangeList = Annotated[
    list[Union[int, TaskParameterStringValue]], Field(min_length=1, max_length=1024)
]
FloatRangeList = Annotated[
    list[Union[Decimal, TaskParameterStringValue]], Field(min_length=1, max_length=1024)
]
StringRangeList = Annotated[list[TaskParameterStringValue], Field(min_length=1, max_length=1024)]
TaskParameterStringValueAsJob = Annotated[str, StringConstraints(min_length=0, max_length=1024)]

TaskRangeList = list[Union[TaskParameterStringValueAsJob, int, float, Decimal]]


class TaskChunksRangeConstraint(str, Enum):
    CONTIGUOUS = "CONTIGUOUS"
    NONCONTIGUOUS = "NONCONTIGUOUS"


class TaskChunksDefinition(OpenJDModel_v2023_09):
    defaultTaskCount: Union[int, FormatString]
    targetRuntimeSeconds: Optional[Union[int, FormatString]] = None
    rangeConstraint: TaskChunksRangeConstraint

    _job_creation_metadata = JobCreationMetadata(
        resolve_fields={"defaultTaskCount", "targetRuntimeSeconds"},
    )

    @field_validator("defaultTaskCount", mode="before")
    @classmethod
    def _validate_default_task_count(cls, value: Any, info: ValidationInfo) -> Any:
        context = cast(Optional[ModelParsingContextInterface], info.context)
        return validate_int_fmtstring_field(value, ge=1, context=context)

    @field_validator("targetRuntimeSeconds", mode="before")
    @classmethod
    def _validate_target_runtime_seconds(cls, value: Any, info: ValidationInfo) -> Any:
        if value is None:
            return value
        context = cast(Optional[ModelParsingContextInterface], info.context)
        return validate_int_fmtstring_field(value, ge=0, context=context)


# Target model for task parameters when instantiating a job.
class RangeListTaskParameterDefinition(OpenJDModel_v2023_09):
    # element type of items in the range
    type: TaskParameterType
    # NOTE: Pydantic V1 was allowing non-string values in this range, V2 is enforcing that type.
    range: TaskRangeList
    # has a value when type is CHUNK[INT], which is only possible from the TASK_CHUNKING extension
    chunks: Optional[TaskChunksDefinition] = None

    @field_validator("range")
    @classmethod
    def _validate_range_len(cls, value: Any) -> Any:
        # §3.4: enforce the range cap on the instantiation target as well, so
        # ranges produced by RFC 0006 typed whole-field resolution (e.g.
        # `range: "{{Param.Values}}"` with a LIST[*] parameter) are subject to
        # the same limit as literal template ranges — matching openjd-rs's
        # resolve-time checks in create_job (ranges.rs).
        return validate_task_param_range_list_len(value)

    @field_validator("range")
    @classmethod
    def _validate_no_empty_path_values(cls, value: Any, info: ValidationInfo) -> Any:
        # §3.4.2: an empty string is not a valid path on any OS, so a PATH
        # task parameter's range may not contain one. The template model's
        # parse-time validator cannot see values that arrive via RFC 0006
        # typed whole-field resolution (e.g. `range: "{{Param.Paths}}"` with
        # a LIST[PATH] job parameter), so the check is enforced on the
        # instantiation target as well — matching openjd-rs's resolve-time
        # check in create_job (ranges.rs).
        if info.data.get("type") == TaskParameterType.PATH and isinstance(value, list):
            for i, item in enumerate(value):
                if str(item) == "":
                    raise ValueError(f"range[{i}] must not be an empty string.")
        return value


class RangeExpressionTaskParameterDefinition(OpenJDModel_v2023_09):
    # element type of items in the range
    type: TaskParameterType
    range: IntRangeExpr
    # has a value when type is CHUNK[INT], which is only possible from the TASK_CHUNKING extension
    chunks: Optional[TaskChunksDefinition] = None

    @field_validator("range")
    @classmethod
    def _validate_range_len(cls, value: Any) -> Any:
        # §3.4: a range expression that arrives via format-string resolution
        # (e.g. `range: "{{RawParam.Frames}}"` with a RANGE_EXPR parameter) is
        # only parsed at instantiation, so the expansion cap must be enforced
        # here too — matching openjd-rs's resolve-time checks in create_job.
        if isinstance(value, IntRangeExpr):
            _check_range_expr_len(value)
        return value


def _check_range_expr_len(parsed_range: IntRangeExpr) -> None:
    """§3.4: a range expression may expand to at most 1024 values."""
    if len(parsed_range) > _MAX_TASK_PARAM_RANGE_LEN:
        raise ValueError(
            f"range expression expands to {len(parsed_range)} elements "
            f"(max {_MAX_TASK_PARAM_RANGE_LEN})."
        )


def _range_task_param_target(model: Any, typed_values: dict) -> Type[OpenJDModel]:
    """``create_as`` target-model selector shared by the INT and CHUNK[INT]
    task-parameter definitions.

    RFC 0006 typed whole-field resolution: a ``range`` that is a single
    whole-field expression evaluating to a list instantiates as a literal
    value list (matching openjd-rs); otherwise the resolved string is parsed
    as a range expression. ``typed_values`` holds the typed resolutions that
    ``instantiate_model`` computed once for this model's
    ``typed_resolve_fields`` — the same values the field instantiation will
    use — so the target decision and the field value never disagree, and the
    expression is not evaluated a second time here.
    """
    if isinstance(model.range, RangeString):
        if "range" in typed_values:
            return RangeListTaskParameterDefinition
        return RangeExpressionTaskParameterDefinition
    return RangeListTaskParameterDefinition


def _range_element_type_name(elem: Any) -> str:
    """The engine type name of a range element for error messages, in the
    shape openjd-rs uses (nested lists report as plain "list")."""
    type_str = str(getattr(elem, "type", type(elem).__name__))
    return "list" if type_str.startswith("list[") else type_str


def _coerce_typed_range_elements(model: Any, field_name: str, raw: Any) -> list:
    """``typed_resolve_coerce`` hook for task-parameter ``range`` fields.

    Enforces element/target type agreement on RFC 0006 typed whole-field
    range resolutions, mirroring openjd-rs's per-variant checks in create_job
    (ranges.rs): an INT (or CHUNK[INT]) range accepts only int elements, a
    FLOAT range accepts int or float, and STRING/PATH ranges take every
    element's spec display form (a bool renders ``true``/``false``, a nested
    list ``[1, 2]``) — without this, unwrapping the engine list erases the
    variants and e.g. a LIST[BOOL] parameter silently becomes 1/0 task values
    that the Rust implementation rejects outright.

    ``raw`` is the engine's list ``ExprValue`` (elements keep their typed
    variants) or, on the non-engine fallback path, a native Python list.
    """
    target = model.type
    out: list = []
    for elem in raw:
        elem_type = getattr(elem, "type", None)
        if elem_type is not None:
            # Engine element ExprValue.
            type_str = str(elem_type)
            if target in (TaskParameterType.INT, TaskParameterType.CHUNK_INT):
                if type_str != "int":
                    raise ValueError(f"Expected int in range, got {_range_element_type_name(elem)}")
                out.append(elem.item())
            elif target == TaskParameterType.FLOAT:
                if type_str not in ("int", "float"):
                    raise ValueError(
                        f"Expected float in range, got {_range_element_type_name(elem)}"
                    )
                out.append(elem.item())
            else:  # STRING / PATH: spec display coercion.
                out.append(str(elem))
        else:
            # Native Python element (non-engine fallback). bool subclasses
            # int, so it is checked first.
            if target in (TaskParameterType.INT, TaskParameterType.CHUNK_INT):
                if isinstance(elem, bool) or not isinstance(elem, int):
                    raise ValueError(
                        f"Expected int in range, got {_native_element_type_name(elem)}"
                    )
                out.append(elem)
            elif target == TaskParameterType.FLOAT:
                if isinstance(elem, bool) or not isinstance(elem, (int, float)):
                    raise ValueError(
                        f"Expected float in range, got {_native_element_type_name(elem)}"
                    )
                out.append(elem)
            else:
                if isinstance(elem, bool):
                    out.append("true" if elem else "false")
                else:
                    out.append(str(elem))
    return out


def _native_element_type_name(elem: Any) -> str:
    """Engine-style type name for a native Python range element."""
    if isinstance(elem, bool):
        return "bool"
    if isinstance(elem, int):
        return "int"
    if isinstance(elem, float):
        return "float"
    if isinstance(elem, str):
        return "string"
    if isinstance(elem, list):
        return "list"
    return type(elem).__name__


def _validate_int_range_elements(value: Any) -> Any:
    """Shared ``range`` post-validator for the INT and CHUNK[INT]
    task-parameter definitions: a literal range-expression string must parse
    and may expand to at most 1024 values (§3.4); a list-form range is
    length-capped. Ranges containing format expressions defer to the
    RangeExpressionTaskParameterDefinition model once they are resolved.
    """
    if isinstance(value, FormatString):
        # If there are no format expressions, we can validate the range expression.
        # otherwise we defer to the RangeExressionTaskParameter model when
        # they've all been evaluated
        if len(value.expressions) == 0:
            try:
                parsed_range = IntRangeExpr.from_str(value)
            except Exception as e:
                raise ValueError(str(e))
            # §3.4: the range may take on at most 1024 values.
            _check_range_expr_len(parsed_range)
    else:
        validate_task_param_range_list_len(value)
    return value


class IntTaskParameterDefinition(NameIdentifierLengthMixin, OpenJDModel_v2023_09):
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
            TemplateVariableDef(prefix="|Task.RawParam.", resolves=ResolutionScope.TASK, raw=True),
        },
        field="name",
    )
    _template_variable_sources = {"__export__": {"__self__"}}

    _job_creation_metadata = JobCreationMetadata(
        create_as=JobCreateAsMetadata(callable=_range_task_param_target),
        resolve_fields={"range"},
        typed_resolve_fields={"range"},
        typed_resolve_coerce=_coerce_typed_range_elements,
        exclude_fields={"name"},
    )

    @field_validator("range", mode="before")
    @classmethod
    def _validate_range_element_type(cls, value: Any, info: ValidationInfo) -> Any:
        # pydantic will automatically type coerce values into integers. We explicitly
        # want to reject non-integer values, so this *pre* validator validates the
        # value *before* pydantic tries to type coerce it.
        # We do allow coersion from a string since we want to allow "1", and
        # "1.2" or "a" will fail the type coersion
        if isinstance(value, list):
            context = cast(Optional[ModelParsingContextInterface], info.context)
            return validate_list_field(value, validate_int_fmtstring_field, context=context)
        elif isinstance(value, RangeString):
            # Nothing to do - it's guaranteed to be a format string at this point
            pass

        return value

    @field_validator("range")
    @classmethod
    def _validate_range_elements(cls, value: Any) -> Any:
        return _validate_int_range_elements(value)


def _validate_range_expr_requires_expr(value: Any, info: ValidationInfo) -> Any:
    """Shared ``range`` field validator for task-parameter definitions: a range
    expression (a ``RangeString`` format string, RFC 0007) requires the EXPR
    extension to be declared, and a list-form range may take on at most 1024
    values (§3.4). Used by the Float/String/Path task-parameter definitions so
    the gate and its message are single-sourced.
    """
    if isinstance(value, RangeString):
        context = cast(Optional[ModelParsingContext], info.context)
        if context and "EXPR" not in context.extensions:
            raise ValueError("A range expression (format string) requires the EXPR extension.")
    else:
        validate_task_param_range_list_len(value)
    return value


class FloatTaskParameterDefinition(NameIdentifierLengthMixin, OpenJDModel_v2023_09):
    """Definition of a float-typed Task Parameter and its value range.

    Attributes:
        name (Identifier):  A name by which the parameter is referenced.
        type (TaskParameterType.FLOAT): discriminator to identify the type of the parameter.
        range (FloatRangeList): The list of values that the parameter takes on.
    """

    name: Identifier
    type: Literal[TaskParameterType.FLOAT]
    range: Union[FloatRangeList, RangeString] = Field(union_mode="left_to_right")

    _template_variable_definitions = DefinesTemplateVariables(
        defines={
            TemplateVariableDef(prefix="|Task.Param.", resolves=ResolutionScope.TASK),
            TemplateVariableDef(prefix="|Task.RawParam.", resolves=ResolutionScope.TASK, raw=True),
        },
        field="name",
    )
    _template_variable_sources = {"__export__": {"__self__"}}
    _job_creation_metadata = JobCreationMetadata(
        create_as=JobCreateAsMetadata(model=RangeListTaskParameterDefinition),
        resolve_fields={"range"},
        typed_resolve_fields={"range"},
        typed_resolve_coerce=_coerce_typed_range_elements,
        exclude_fields={"name"},
    )

    @field_validator("range", mode="before")
    @classmethod
    def _validate_range_element_type(cls, value: Any, info: ValidationInfo) -> Any:
        # pydantic will automatically type coerce values into floats. We explicitly
        # want to reject non-integer values, so this *pre* validator validates the
        # value *before* pydantic tries to type coerce it.
        if isinstance(value, list):
            context = cast(Optional[ModelParsingContextInterface], info.context)
            return validate_list_field(value, validate_float_fmtstring_field, context=context)
        return value

    @field_validator("range")
    @classmethod
    def _range_expr_requires_expr(cls, value: Any, info: ValidationInfo) -> Any:
        return _validate_range_expr_requires_expr(value, info)


class StringTaskParameterDefinition(NameIdentifierLengthMixin, OpenJDModel_v2023_09):
    """Definition of a string-typed Task Parameter and its value range.

    Attributes:
        name (Identifier):  A name by which the parameter is referenced.
        type (TaskParameterType.STRING): discriminator to identify the type of the parameter.
        range (StringRangeList): The list of values that the parameter takes on.
    """

    name: Identifier
    type: Literal[TaskParameterType.STRING]
    range: Union[StringRangeList, RangeString] = Field(union_mode="left_to_right")

    _template_variable_definitions = DefinesTemplateVariables(
        defines={
            TemplateVariableDef(prefix="|Task.Param.", resolves=ResolutionScope.TASK),
            TemplateVariableDef(prefix="|Task.RawParam.", resolves=ResolutionScope.TASK, raw=True),
        },
        field="name",
    )
    _template_variable_sources = {"__export__": {"__self__"}}
    _job_creation_metadata = JobCreationMetadata(
        create_as=JobCreateAsMetadata(model=RangeListTaskParameterDefinition),
        resolve_fields={"range"},
        typed_resolve_fields={"range"},
        typed_resolve_coerce=_coerce_typed_range_elements,
        exclude_fields={"name"},
    )

    @field_validator("range")
    @classmethod
    def _range_expr_requires_expr(cls, value: Any, info: ValidationInfo) -> Any:
        return _validate_range_expr_requires_expr(value, info)


class PathTaskParameterDefinition(NameIdentifierLengthMixin, OpenJDModel_v2023_09):
    """Definition of a path-typed Task Parameter and its value range.

    Attributes:
        name (Identifier):  A name by which the parameter is referenced.
        type (TaskParameterType.PATH): discriminator to identify the type of the parameter.
        range (StringRangeList): The list of values that the parameter takes on.
    """

    name: Identifier
    type: Literal[TaskParameterType.PATH]
    range: Union[StringRangeList, RangeString] = Field(union_mode="left_to_right")

    _template_variable_definitions = DefinesTemplateVariables(
        defines={
            TemplateVariableDef(prefix="|Task.Param.", resolves=ResolutionScope.TASK),
            TemplateVariableDef(prefix="|Task.RawParam.", resolves=ResolutionScope.TASK, raw=True),
        },
        field="name",
    )
    _template_variable_sources = {"__export__": {"__self__"}}
    _job_creation_metadata = JobCreationMetadata(
        create_as=JobCreateAsMetadata(model=RangeListTaskParameterDefinition),
        resolve_fields={"range"},
        typed_resolve_fields={"range"},
        typed_resolve_coerce=_coerce_typed_range_elements,
        exclude_fields={"name"},
    )

    @field_validator("range")
    @classmethod
    def _range_expr_requires_expr(cls, value: Any, info: ValidationInfo) -> Any:
        return _validate_range_expr_requires_expr(value, info)

    @field_validator("range")
    @classmethod
    def _validate_no_empty_path_values(cls, value: Any) -> Any:
        # §3.4.2: an empty string is not a valid path on any OS, so a PATH
        # task parameter's range may not contain one. Format-string items
        # with expressions resolve later; literal empties are rejected here.
        if isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, FormatString) and len(item.expressions) > 0:
                    continue
                if str(item) == "":
                    raise ValueError(f"range[{i}] must not be an empty string.")
        return value


class ChunkIntTaskParameterDefinition(NameIdentifierLengthMixin, OpenJDModel_v2023_09):
    """Definition of an integer-typed Task Parameter, that is processed as
     chunks of tasks insteas of as individual tasks when running.

    Attributes:
        name (Identifier):  A name by which the parameter is referenced.
        type (TaskParameterType.CHUNK_INT): discriminator to identify the type of the parameter.
        range (IntRangeList | RangeString): The list of values that the parameter takes on.
        chunks (TaskChunkProperties): Properties that specify how to form chunks of tasks.
    """

    name: Identifier
    type: Literal[TaskParameterType.CHUNK_INT]
    # Note: Ordering here is important. Pydantic will try to match in
    # the order given.
    range: Union[IntRangeList, RangeString]
    chunks: TaskChunksDefinition

    _template_variable_definitions = DefinesTemplateVariables(
        defines={
            TemplateVariableDef(prefix="|Task.Param.", resolves=ResolutionScope.TASK),
            TemplateVariableDef(prefix="|Task.RawParam.", resolves=ResolutionScope.TASK, raw=True),
        },
        field="name",
    )
    _template_variable_sources = {"__export__": {"__self__"}}

    _job_creation_metadata = JobCreationMetadata(
        create_as=JobCreateAsMetadata(callable=_range_task_param_target),
        resolve_fields={"range"},
        typed_resolve_fields={"range"},
        typed_resolve_coerce=_coerce_typed_range_elements,
        exclude_fields={"name"},
    )

    @model_validator(mode="before")
    @classmethod
    def _validate_task_chunking_extension(
        cls, values: dict[str, Any], info: ValidationInfo
    ) -> dict[str, Any]:
        if info.context:
            context = cast(ModelParsingContext, info.context)
            if ExtensionName.TASK_CHUNKING not in context.extensions:
                raise ValueError(
                    "The CHUNK[INT] task parameter requires the TASK_CHUNKING extension."
                )
        return values

    @field_validator("range", mode="before")
    @classmethod
    def _validate_range_element_type(cls, value: Any, info: ValidationInfo) -> Any:
        # pydantic will automatically type coerce values into integers. We explicitly
        # want to reject non-integer values, so this *pre* validator validates the
        # value *before* pydantic tries to type coerce it.
        # We do allow coersion from a string since we want to allow "1", and
        # "1.2" or "a" will fail the type coersion
        if isinstance(value, list):
            context = cast(Optional[ModelParsingContextInterface], info.context)
            return validate_list_field(value, validate_int_fmtstring_field, context=context)
        elif isinstance(value, RangeString):
            # Nothing to do - it's guaranteed to be a format string at this point
            pass

        return value

    @field_validator("range")
    @classmethod
    def _validate_range_elements(cls, value: Any) -> Any:
        return _validate_int_range_elements(value)


TaskParameterDefinition = Union[
    IntTaskParameterDefinition,
    FloatTaskParameterDefinition,
    StringTaskParameterDefinition,
    PathTaskParameterDefinition,
    ChunkIntTaskParameterDefinition,
]

TaskParameterList = Annotated[
    list[Annotated[TaskParameterDefinition, Field(..., discriminator="type")]],
    Field(
        min_length=1,
        max_length=16,
    ),
]
# Limit the CombinationExpr to characters allowed in an Identifier plus whitespace
# and the operator characters.
CombinationExpr = Annotated[
    str,
    StringConstraints(
        min_length=1, max_length=1280, strict=True, pattern=r"(?-m:^[A-Za-z0-9\*\(\), ]+\z)"
    ),
]

TaskRangeParameter = Union[RangeListTaskParameterDefinition, RangeExpressionTaskParameterDefinition]


# Target model for step template when instantiating a job.
class StepParameterSpace(OpenJDModel_v2023_09):
    # Note: taskParameterDefinitions is a dict here to make it easier to work with
    # programatically (e.g. finding the TaskRangeParameterDefinition for a given
    # identifier)
    taskParameterDefinitions: dict[Identifier, TaskRangeParameter]
    combination: Optional[CombinationExpr] = None

    @field_validator("combination")
    @classmethod
    def _validate_parameter_space(cls, v: str, info: ValidationInfo) -> str:
        if v is None:
            return v
        param_defs = cast(
            dict[Identifier, TaskRangeParameter], info.data["taskParameterDefinitions"]
        )
        parameter_range_lengths = {id: len(param.range) for id, param in param_defs.items()}
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

    @field_validator("taskParameterDefinitions")
    @classmethod
    def _validate_parameters(cls, v: TaskParameterList) -> TaskParameterList:
        # Only one CHUNK[INT] parameter is permitted
        if len([param for param in v if param.type == TaskParameterType.CHUNK_INT]) > 1:
            raise ValueError("Only one CHUNK[INT] task parameter is permitted")
        # Must have a unique name for each Task parameter
        return validate_unique_elements(v, item_value=lambda v: v.name, property="name")

    @model_validator(mode="after")
    def _validate_combination(self) -> Self:
        if self.combination is None or self.taskParameterDefinitions is None:
            return self

        parameter_def_list: TaskParameterList = self.taskParameterDefinitions
        combination: CombinationExpr = self.combination

        # Ensure that the 'combination' string:
        #   a) is a properly formed combination expression; and
        #   b) references all available task parameters exactly once each
        #   c) does not include a CHUNK[INT] parameter in an associative expression

        try:
            parse_tree = CombinationExpressionParser().parse(combination)
        except (ExpressionError, TokenError) as e:
            raise ValueError(str(e))

        expr_identifiers = list[str]()
        parse_tree.collect_identifiers(expr_identifiers)
        unique_expr_identifiers = set(expr_identifiers)
        parameter_names = [param.name for param in parameter_def_list]
        unique_parameter_names = set(parameter_names)

        errors = list[InitErrorDetails]()
        if len(unique_expr_identifiers) < len(unique_parameter_names):
            # Missing some parameter identifiers in the expression
            missing = sorted(list(unique_parameter_names - unique_expr_identifiers))
            errors.append(
                InitErrorDetails(
                    type="value_error",
                    loc=("combination",),
                    ctx={
                        "error": ValueError(f"Expression missing parameters: {','.join(missing)}")
                    },
                    input=combination,
                )
            )
        if len(unique_parameter_names) < len(unique_expr_identifiers):
            # Have some extra parameters referenced in the expression
            extra = sorted(list(unique_expr_identifiers - unique_parameter_names))
            errors.append(
                InitErrorDetails(
                    type="value_error",
                    loc=("combination",),
                    ctx={
                        "error": ValueError(
                            f"Expression references undefined parameters: {','.join(extra)}"
                        )
                    },
                    input=combination,
                )
            )
        if len(expr_identifiers) != len(unique_expr_identifiers):
            # Some parameter names are used more than once in the expression
            duplicates = sorted(
                [id for id in expr_identifiers if id not in unique_expr_identifiers]
            )
            errors.append(
                InitErrorDetails(
                    type="value_error",
                    loc=("combination",),
                    ctx={
                        "error": ValueError(
                            f"Expression can only reference each parameter once: {','.join(duplicates)} "
                        )
                    },
                    input=combination,
                )
            )

        # If a parameter has type CHUNK[INT], get its name
        chunk_parameter = None
        for param in self.taskParameterDefinitions:
            if param.type == TaskParameterType.CHUNK_INT:
                chunk_parameter = param.name

        try:
            if chunk_parameter is not None:
                validate_step_parameter_space_chunk_constraint(chunk_parameter, parse_tree)
        except ExpressionError as e:
            errors.append(
                InitErrorDetails(
                    type="value_error",
                    loc=("combination",),
                    ctx={"error": ValueError(str(e))},
                    input=combination,
                )
            )

        if errors:
            raise ValidationError.from_exception_data(self.__class__.__name__, errors)

        return self


# ==================================================================
# ====================== Environments Variables ====================
# ==================================================================

EnvironmentVariableNameString = Annotated[
    str,
    StringConstraints(min_length=1, max_length=256, pattern=r"(?-m:^[a-zA-Z_][a-zA-Z0-9_]*\z)"),
]


class EnvironmentVariableValueString(FormatString):
    _max_length = 2048

    def __new__(cls, value: str, *, context: ModelParsingContextInterface = ModelParsingContext()):
        return super().__new__(cls, value, context=context)


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
    # §7.3.1: an environment's `variables` values are format strings resolved
    # at session scope, so the Session.* value references are available to
    # them — matching the script's actions (whose injection lives on the
    # script model) and the openjd-rs validator.
    _template_variable_definitions = DefinesTemplateVariables(
        inject={
            f"|{ValueReferenceConstants.WORKING_DIRECTORY.value}",
            f"|{ValueReferenceConstants.HAS_PATH_MAPPING_RULES.value}",
            f"|{ValueReferenceConstants.PATH_MAPPING_RULES_FILE.value}",
        },
    )
    _template_variable_sources = {
        "variables": {"__self__"},
    }

    @field_validator("name")
    @classmethod
    def _validate_environment_name(cls, v: str, info: ValidationInfo) -> str:
        context = cast(Optional[ModelParsingContext], info.context)
        max_len = 512 if context and "FEATURE_BUNDLE_1" in context.extensions else 64
        if len(v) > max_len:
            raise ValueError(f"name must be at most {max_len} characters long")
        return v

    @model_validator(mode="before")
    @classmethod
    def _validate_has_script_or_variables(cls, values: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(values, dict):
            raise ValueError("Environment must be a mapping.")
        if values.get("script") is None and values.get("variables") is None:
            raise ValueError("Environment must have either a script or variables.")
        return values

    @field_validator("variables")
    @classmethod
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
    # EXPR extension (RFC 0007) — gated on the EXPR extension in the
    # per-definition validators.
    BOOL = "BOOL"
    LIST_STRING = "LIST[STRING]"
    LIST_PATH = "LIST[PATH]"
    LIST_INT = "LIST[INT]"
    LIST_FLOAT = "LIST[FLOAT]"
    LIST_BOOL = "LIST[BOOL]"
    LIST_LIST_INT = "LIST[LIST[INT]]"
    RANGE_EXPR = "RANGE_EXPR"


AllowedParameterStringValueList = Annotated[list[ParameterStringValue], Field(min_length=1)]
AllowedIntParameterList = Annotated[list[int], Field(min_length=1)]
AllowedFloatParameterList = Annotated[list[Decimal], Field(min_length=1)]
UserInterfaceLabelStringValue = Annotated[
    str,
    StringConstraints(min_length=1, max_length=64, strict=True, pattern=_standard_string_regex),
]
FileDialogFilterPatternStringValue = Annotated[
    str,
    StringConstraints(
        min_length=1, max_length=20, strict=True, pattern=_file_dialog_filter_pattern_regex
    ),
]
FileDialogFilterPatternStringValueList = Annotated[
    list[FileDialogFilterPatternStringValue], Field(min_length=1, max_length=20)
]


# Target model for a job parameter when instantiating a job.
class JobParameter(OpenJDModel_v2023_09):
    type: JobParameterType
    # For the original scalar types the value is a string. For the EXPR
    # extension types (RFC 0007: BOOL and the LIST[*] variants) the value is the
    # native Python value (bool / list) produced by create_job.
    value: Any
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
        control (Optional[StringUserInterfaceControl]): The user interface control to use when editing this parameter.
            Default is LINE_EDIT when allowedValues is not provided, DROPDOWN_LIST when it is.
        label (Optional[UserInterfaceLabelStringValue]): The label to display for the user interface control. Defaults
            to the `name` of the parameter.
        groupLabel (Optional[UserInterfaceLabelStringValue]): The label of the group box to place the user interface
            control in.
    """

    control: Optional[StringUserInterfaceControl] = None
    label: Optional[UserInterfaceLabelStringValue] = None
    groupLabel: Optional[UserInterfaceLabelStringValue] = None


class JobStringParameterDefinition(
    NameIdentifierLengthMixin, OpenJDModel_v2023_09, JobParameterInterface
):
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
    userInterface: Optional[JobStringParameterDefinitionUserInterface] = None
    description: Optional[Description] = None
    # Note: Ordering of the following fields is essential for the validators to work correctly.
    minLength: Optional[StrictInt] = None  # noqa: N815
    maxLength: Optional[StrictInt] = None  # noqa: N815
    allowedValues: Optional[AllowedParameterStringValueList] = None  # noqa: N815
    default: Optional[ParameterStringValue] = None

    _template_variable_definitions = DefinesTemplateVariables(
        defines={
            TemplateVariableDef(prefix="|Param.", resolves=ResolutionScope.TEMPLATE),
            TemplateVariableDef(prefix="|RawParam.", resolves=ResolutionScope.TEMPLATE, raw=True),
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
        adds_fields=lambda this, symtab: {
            "value": symtab[f"RawParam.{cast(JobStringParameterDefinition, this).name}"]
        },
    )

    @field_validator("minLength")
    @classmethod
    def _validate_min_length(cls, value: Optional[int]) -> Optional[int]:
        if value is None:
            return value
        if value < 0:
            raise ValueError("Required: 0 <= minLength.")
        return value

    @field_validator("maxLength")
    @classmethod
    def _validate_max_length(cls, value: Optional[int], info: ValidationInfo) -> Optional[int]:
        if value is None:
            return value
        if value <= 0:
            raise ValueError("Required: 0 < maxLength.")
        min_length = info.data.get("minLength")
        if min_length is None:
            return value
        if min_length > value:
            raise ValueError("Required: minLength <= maxLength.")
        return value

    @field_validator("allowedValues")
    @classmethod
    def _validate_allowed_values_item(
        cls, value: AllowedParameterStringValueList, info: ValidationInfo
    ) -> AllowedParameterStringValueList:
        if value is None:
            raise ValueError(_ALLOWED_VALUES_NONE_ERROR)
        min_length = info.data.get("minLength")
        max_length = info.data.get("maxLength")
        errors = list[InitErrorDetails]()
        for i, item in enumerate(value):
            if min_length is not None:
                if len(item) < min_length:
                    errors.append(
                        InitErrorDetails(
                            type="value_error",
                            loc=(i,),
                            ctx={"error": ValueError("Value is shorter than minLength.")},
                            input=item,
                        )
                    )
            if max_length is not None:
                if len(item) > max_length:
                    errors.append(
                        InitErrorDetails(
                            type="value_error",
                            loc=(i,),
                            ctx={"error": ValueError("Value is longer than maxLength.")},
                            input=item,
                        )
                    )
        if errors:
            raise ValidationError.from_exception_data(cls.__name__, line_errors=errors)
        return value

    @field_validator("default")
    @classmethod
    def _validate_default(
        cls, value: ParameterStringValue, info: ValidationInfo
    ) -> ParameterStringValue:
        min_length = info.data.get("minLength")
        if min_length is not None:
            if len(value) < min_length:
                raise ValueError("Value is shorter than minLength.")
        max_length = info.data.get("maxLength")
        if max_length is not None:
            if len(value) > max_length:
                raise ValueError("Value is longer than maxLength.")

        allowed_values = info.data.get("allowedValues")
        if allowed_values is not None:
            if value not in allowed_values:
                raise ValueError("Must be an allowed value.")
        return value

    @model_validator(mode="after")
    def _validate_user_interface_compatibility(self) -> Self:
        # validate that the user interface control is compatible with the value constraints
        if self.userInterface:
            user_interface_control = self.userInterface.control
            if user_interface_control is None:
                return self
            if self.allowedValues and user_interface_control in (
                StringUserInterfaceControl.LINE_EDIT,
                StringUserInterfaceControl.MULTILINE_EDIT,
            ):
                raise ValueError(
                    f"User interface control {user_interface_control.name} cannot be used when 'allowedValues' is provided"
                )
            if (
                not self.allowedValues
                and user_interface_control == StringUserInterfaceControl.DROPDOWN_LIST
            ):
                raise ValueError(
                    f"User interface control {user_interface_control.name} requires that 'allowedValues' be provided"
                )
            if user_interface_control == StringUserInterfaceControl.CHECK_BOX:
                allowed_values = set(v.upper() for v in self.allowedValues or [])
                if allowed_values not in ALLOWED_VALUES_FOR_CHECK_BOX:
                    raise ValueError(
                        f"User interface control {user_interface_control.name} requires that 'allowedValues' be "
                        + f"one of {ALLOWED_VALUES_FOR_CHECK_BOX} (case and order insensitive)"
                    )
        return self

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


JobPathParameterDefinitionFileFilterList = Annotated[
    list[JobPathParameterDefinitionFileFilter], Field(min_length=1, max_length=20)
]


class JobPathParameterDefinitionUserInterface(OpenJDModel_v2023_09):
    """User interface attributes for a job path parameter.

    Attributes:
        control (Optional[PathUserInterfaceControl]): The user interface control to use when editing this parameter.
            Default depends on objectType, dataFlow, and allowedValues.
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

    control: Optional[PathUserInterfaceControl] = None
    label: Optional[UserInterfaceLabelStringValue] = None
    groupLabel: Optional[UserInterfaceLabelStringValue] = None
    fileFilters: Optional[JobPathParameterDefinitionFileFilterList] = None
    fileFilterDefault: Optional[JobPathParameterDefinitionFileFilter] = None


class JobPathParameterDefinition(
    NameIdentifierLengthMixin, OpenJDModel_v2023_09, JobParameterInterface
):
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
    objectType: Optional[JobPathParameterDefinitionObjectType] = None
    dataFlow: Optional[JobPathParameterDefinitionDataFlow] = None
    userInterface: Optional[JobPathParameterDefinitionUserInterface] = None
    description: Optional[Description] = None
    # Note: Ordering of the following fields is essential for the validators to work correctly.
    minLength: Optional[StrictInt] = None  # noqa: N815
    maxLength: Optional[StrictInt] = None  # noqa: N815
    allowedValues: Optional[AllowedParameterStringValueList] = None  # noqa: N815
    default: Optional[ParameterStringValue] = None

    _template_variable_definitions = DefinesTemplateVariables(
        defines={
            TemplateVariableDef(prefix="|Param.", resolves=ResolutionScope.SESSION),
            TemplateVariableDef(prefix="|RawParam.", resolves=ResolutionScope.TEMPLATE, raw=True),
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
        adds_fields=lambda this, symtab: {
            "value": symtab[f"RawParam.{cast(JobPathParameterDefinition, this).name}"]
        },
    )

    @field_validator("minLength")
    @classmethod
    def _validate_min_length(cls, value: Optional[int]) -> Optional[int]:
        if value is None:
            return value
        if value < 0:
            raise ValueError("Required: 0 <= minLength.")
        return value

    @field_validator("maxLength")
    @classmethod
    def _validate_max_length(cls, value: Optional[int], info: ValidationInfo) -> Optional[int]:
        if value is None:
            return value
        if value <= 0:
            raise ValueError("Required: 0 < maxLength.")
        min_length = info.data.get("minLength")
        if min_length is None:
            return value
        if min_length > value:
            raise ValueError("Required: minLength <= maxLength.")
        return value

    @field_validator("allowedValues")
    @classmethod
    def _validate_allowed_values_item(
        cls, value: AllowedParameterStringValueList, info: ValidationInfo
    ) -> AllowedParameterStringValueList:
        if value is None:
            raise ValueError(_ALLOWED_VALUES_NONE_ERROR)
        min_length = info.data.get("minLength")
        max_length = info.data.get("maxLength")
        errors = list[InitErrorDetails]()
        for i, item in enumerate(value):
            if min_length is not None:
                if len(item) < min_length:
                    errors.append(
                        InitErrorDetails(
                            type="value_error",
                            loc=(i,),
                            ctx={"error": ValueError("Value is shorter than minLength.")},
                            input=item,
                        )
                    )
            if max_length is not None:
                if len(item) > max_length:
                    errors.append(
                        InitErrorDetails(
                            type="value_error",
                            loc=(i,),
                            ctx={"error": ValueError("Value is longer than maxLength.")},
                            input=item,
                        )
                    )
        if errors:
            raise ValidationError.from_exception_data(cls.__name__, line_errors=errors)
        return value

    @field_validator("default")
    @classmethod
    def _validate_default(
        cls, value: ParameterStringValue, info: ValidationInfo
    ) -> ParameterStringValue:
        min_length = info.data.get("minLength")
        if min_length is not None:
            if len(value) < min_length:
                raise ValueError("Value is shorter than minLength.")
        max_length = info.data.get("maxLength")
        if max_length is not None:
            if len(value) > max_length:
                raise ValueError("Value is longer than maxLength.")

        allowed_values = info.data.get("allowedValues")
        if allowed_values is not None:
            if value not in allowed_values:
                raise ValueError("Must be an allowed value.")
        return value

    @model_validator(mode="after")
    def _validate_user_interface_compatibility(self) -> Self:
        # validate that the user interface control is compatible with the value constraints
        if self.userInterface:
            user_interface_control = self.userInterface.control
            if user_interface_control is None:
                return self
            if self.allowedValues and user_interface_control in (
                PathUserInterfaceControl.CHOOSE_INPUT_FILE,
                PathUserInterfaceControl.CHOOSE_OUTPUT_FILE,
                PathUserInterfaceControl.CHOOSE_DIRECTORY,
            ):
                raise ValueError(
                    f"User interface control {user_interface_control.name} cannot be used when 'allowedValues' is provided"
                )
            if (
                not self.allowedValues
                and user_interface_control == PathUserInterfaceControl.DROPDOWN_LIST
            ):
                raise ValueError(
                    f"User interface control {user_interface_control.name} requires that 'allowedValues' be provided"
                )
            if (
                self.userInterface.fileFilters or self.userInterface.fileFilterDefault
            ) and user_interface_control not in [
                PathUserInterfaceControl.CHOOSE_INPUT_FILE,
                PathUserInterfaceControl.CHOOSE_OUTPUT_FILE,
            ]:
                raise ValueError(
                    f"User interface control {user_interface_control.name} cannot be used when 'fileFilters'"
                    + " or 'fileFilterDefault is provided"
                )
            if (
                self.objectType == JobPathParameterDefinitionObjectType.FILE
                and user_interface_control == PathUserInterfaceControl.CHOOSE_DIRECTORY
            ):
                raise ValueError(
                    f"User interface control {user_interface_control.name} cannot be used with 'objectType' of FILE"
                )
            if (
                self.objectType == JobPathParameterDefinitionObjectType.DIRECTORY
                and user_interface_control
                in [
                    PathUserInterfaceControl.CHOOSE_INPUT_FILE,
                    PathUserInterfaceControl.CHOOSE_OUTPUT_FILE,
                ]
            ):
                raise ValueError(
                    f"User interface control {user_interface_control.name} cannot be used with 'objectType' of DIRECTORY"
                )

        return self

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
        control (Optional[IntUserInterfaceControl]): The user interface control to use when editing this parameter.
            Default is SPIN_BOX when allowedValues is not provided, DROPDOWN_LIST when it is.
        label (Optional[UserInterfaceLabelStringValue]): The label to display for the user interface control. Defaults
            to the `name` of the parameter.
        groupLabel (Optional[UserInterfaceLabelStringValue]): The label of the group box to place the user interface
            control in.
        singleStepDelta (Optional[PositiveInt]): How much the value changes for a single step modification, such
            as selecting an up or down arrow in the user interface control.
    """

    control: Optional[IntUserInterfaceControl] = None
    label: Optional[UserInterfaceLabelStringValue] = None
    groupLabel: Optional[UserInterfaceLabelStringValue] = None
    singleStepDelta: Optional[PositiveInt] = None


class JobIntParameterDefinition(NameIdentifierLengthMixin, OpenJDModel_v2023_09):
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
        maxValue (Optional[int]): Maximum value that the parameter is allowed to be.
    """

    name: Identifier
    type: Literal[JobParameterType.INT]
    userInterface: Optional[JobIntParameterDefinitionUserInterface] = None
    description: Optional[Description] = None
    # Note: Ordering of the following fields is essential for the validators to work correctly.
    minValue: Optional[int] = None  # noqa: N815
    maxValue: Optional[int] = None  # noqa: N815
    allowedValues: Optional[AllowedIntParameterList] = None  # noqa: N815
    default: Optional[int] = None

    _template_variable_definitions = DefinesTemplateVariables(
        defines={
            TemplateVariableDef(prefix="|Param.", resolves=ResolutionScope.TEMPLATE),
            TemplateVariableDef(prefix="|RawParam.", resolves=ResolutionScope.TEMPLATE, raw=True),
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
        adds_fields=lambda this, symtab: {
            "value": symtab[f"RawParam.{cast(JobIntParameterDefinition, this).name}"]
        },
    )

    @classmethod
    def _precheck_is_int_type(cls, value: Any) -> None:
        # prevent floats, bools, and other types from coercing into an int.
        # strings that contain floats are handled by pydantic's checks.
        if not isinstance(value, (int, str)) or isinstance(value, bool):
            raise ValueError("Value must be an integer or integer string.")

    @field_validator("minValue", mode="before")
    @classmethod
    def _validate_min_value_type(cls, value: Optional[Any]) -> Optional[Any]:
        if value is None:
            return value
        cls._precheck_is_int_type(value)
        return value

    @field_validator("maxValue", mode="before")
    @classmethod
    def _validate_max_value_type(cls, value: Optional[Any]) -> Optional[Any]:
        if value is None:
            return value
        cls._precheck_is_int_type(value)
        return value

    @field_validator("allowedValues", mode="before")
    @classmethod
    def _validate_allowed_values_item_type(
        cls, value: AllowedIntParameterList
    ) -> AllowedIntParameterList:
        if value is None:
            raise ValueError(_ALLOWED_VALUES_NONE_ERROR)

        errors = list[InitErrorDetails]()
        for i, item in enumerate(value):
            if isinstance(item, bool) or not isinstance(item, (int, str)):
                try:
                    cls._precheck_is_int_type(value)
                except ValueError as e:
                    errors.append(
                        InitErrorDetails(
                            type="value_error",
                            loc=(i,),
                            ctx={"error": e},
                            input=item,
                        )
                    )
        if errors:
            raise ValidationError.from_exception_data(cls.__name__, line_errors=errors)
        return value

    @field_validator("default", mode="before")
    @classmethod
    def _validate_default_value_type(cls, value: Optional[Any]) -> Optional[Any]:
        if value is None:
            return value
        cls._precheck_is_int_type(value)
        return value

    @field_validator("maxValue")
    @classmethod
    def _validate_max_value(cls, value: Optional[int], info: ValidationInfo) -> Optional[int]:
        if value is None:
            return value
        min_value = info.data.get("minValue")
        if min_value is None:
            return value
        if min_value > value:
            raise ValueError("Required: minValue <= maxValue.")
        return value

    @field_validator("allowedValues")
    @classmethod
    def _validate_allowed_values_item(
        cls, value: AllowedIntParameterList, info: ValidationInfo
    ) -> AllowedIntParameterList:
        if value is None:
            raise ValueError(_ALLOWED_VALUES_NONE_ERROR)
        min_value = info.data.get("minValue")
        max_value = info.data.get("maxValue")
        errors = list[InitErrorDetails]()
        for i, item in enumerate(value):
            if min_value is not None:
                if item < min_value:
                    errors.append(
                        InitErrorDetails(
                            type="value_error",
                            loc=(i,),
                            ctx={"error": ValueError(_VALUE_LESS_THAN_MIN_ERROR)},
                            input=item,
                        )
                    )
            if max_value is not None:
                if item > max_value:
                    errors.append(
                        InitErrorDetails(
                            type="value_error",
                            loc=(i,),
                            ctx={"error": ValueError(_VALUE_LARGER_THAN_MAX_ERROR)},
                            input=item,
                        )
                    )
        if errors:
            raise ValidationError.from_exception_data(cls.__name__, line_errors=errors)
        return value

    @field_validator("default")
    @classmethod
    def _validate_default(cls, value: int, info: ValidationInfo) -> int:
        min_value = info.data.get("minValue")
        if min_value is not None:
            if value < min_value:
                raise ValueError(_VALUE_LESS_THAN_MIN_ERROR)
        max_value = info.data.get("maxValue")
        if max_value is not None:
            if value > max_value:
                raise ValueError(_VALUE_LARGER_THAN_MAX_ERROR)

        allowed_values = info.data.get("allowedValues")
        if allowed_values is not None:
            if value not in allowed_values:
                raise ValueError("Must be an allowed value.")
        return value

    @model_validator(mode="after")
    def _validate_user_interface_compatibility(self) -> Self:
        # validate that the user interface control is compatible with the value constraints
        if self.userInterface:
            user_interface_control = self.userInterface.control
            if user_interface_control is None:
                return self
            if self.allowedValues and user_interface_control == IntUserInterfaceControl.SPIN_BOX:
                raise ValueError(
                    f"User interface control {user_interface_control.name} cannot be used when 'allowedValues' is provided"
                )
            if (
                not self.allowedValues
                and user_interface_control == IntUserInterfaceControl.DROPDOWN_LIST
            ):
                raise ValueError(
                    f"User interface control {user_interface_control.name} requires that 'allowedValues' be provided"
                )
            if (
                self.userInterface.singleStepDelta
                and user_interface_control != IntUserInterfaceControl.SPIN_BOX
            ):
                raise ValueError(
                    f"User interface control {user_interface_control.name} cannot be used when 'singleStepDelta' is provided"
                )

        return self

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
        control (Optional[FloatUserInterfaceControl]): The user interface control to use when editing this parameter.
            Default is SPIN_BOX when allowedValues is not provided, DROPDOWN_LIST when it is.
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

    control: Optional[FloatUserInterfaceControl] = None
    label: Optional[UserInterfaceLabelStringValue] = None
    groupLabel: Optional[UserInterfaceLabelStringValue] = None
    decimals: Optional[PositiveInt] = None
    singleStepDelta: Optional[PositiveFloat] = None


class JobFloatParameterDefinition(NameIdentifierLengthMixin, OpenJDModel_v2023_09):
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
        maxValue (Optional[Decimal]): Maximum value that the parameter is allowed to be.
    """

    name: Identifier
    type: Literal[JobParameterType.FLOAT]
    userInterface: Optional[JobFloatParameterDefinitionUserInterface] = None
    description: Optional[Description] = None
    # Note: Ordering of the following fields is essential for the validators to work correctly.
    minValue: Optional[Decimal] = None  # noqa: N815
    maxValue: Optional[Decimal] = None  # noqa: N815
    allowedValues: Optional[AllowedFloatParameterList] = None  # noqa: N815
    default: Optional[Decimal] = None

    @model_validator(mode="after")
    def _validate_decimals_requires_spin_box(self) -> Self:
        # §2.4: `decimals` configures the places editable in a SPIN_BOX; it is
        # meaningless for DROPDOWN_LIST and HIDDEN controls. The effective
        # control defaults to DROPDOWN_LIST when allowedValues is provided and
        # SPIN_BOX otherwise, matching openjd-rs's validate_ui rules.
        ui = self.userInterface
        if ui is not None and ui.decimals is not None:
            control = ui.control
            if control is None:
                control = (
                    FloatUserInterfaceControl.DROPDOWN_LIST
                    if self.allowedValues is not None
                    else FloatUserInterfaceControl.SPIN_BOX
                )
            if control != FloatUserInterfaceControl.SPIN_BOX:
                raise ValueError("decimals can only be provided when the control is SPIN_BOX.")
        return self

    _template_variable_definitions = DefinesTemplateVariables(
        defines={
            TemplateVariableDef(prefix="|Param.", resolves=ResolutionScope.TEMPLATE),
            TemplateVariableDef(prefix="|RawParam.", resolves=ResolutionScope.TEMPLATE, raw=True),
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
        adds_fields=lambda this, symtab: {
            "value": symtab[f"RawParam.{cast(JobFloatParameterDefinition, this).name}"]
        },
    )

    @field_validator("maxValue")
    @classmethod
    def _validate_max_value(
        cls, value: Optional[Decimal], info: ValidationInfo
    ) -> Optional[Decimal]:
        if value is None:
            return value
        min_value = info.data.get("minValue")
        if min_value is None:
            return value
        if min_value > value:
            raise ValueError("Required: minValue <= maxValue.")
        return value

    @field_validator("allowedValues")
    @classmethod
    def _validate_allowed_values_item(
        cls, value: AllowedFloatParameterList, info: ValidationInfo
    ) -> AllowedFloatParameterList:
        if value is None:
            raise ValueError(_ALLOWED_VALUES_NONE_ERROR)
        min_value = info.data.get("minValue")
        max_value = info.data.get("maxValue")
        errors = list[InitErrorDetails]()
        for i, item in enumerate(value):
            if min_value is not None:
                if item < min_value:
                    errors.append(
                        InitErrorDetails(
                            type="value_error",
                            loc=(i,),
                            ctx={"error": ValueError(_VALUE_LESS_THAN_MIN_ERROR)},
                            input=item,
                        )
                    )
            if max_value is not None:
                if item > max_value:
                    errors.append(
                        InitErrorDetails(
                            type="value_error",
                            loc=(i,),
                            ctx={"error": ValueError(_VALUE_LARGER_THAN_MAX_ERROR)},
                            input=item,
                        )
                    )
        if errors:
            raise ValidationError.from_exception_data(cls.__name__, line_errors=errors)
        return value

    @field_validator("default")
    @classmethod
    def _validate_default(cls, value: Decimal, info: ValidationInfo) -> Decimal:
        min_value = info.data.get("minValue")
        if min_value is not None:
            if value < min_value:
                raise ValueError(_VALUE_LESS_THAN_MIN_ERROR)
        max_value = info.data.get("maxValue")
        if max_value is not None:
            if value > max_value:
                raise ValueError(_VALUE_LARGER_THAN_MAX_ERROR)

        allowed_values = info.data.get("allowedValues")
        if allowed_values is not None:
            if value not in allowed_values:
                raise ValueError("Must be an allowed value.")
        return value

    @model_validator(mode="after")
    def _validate_user_interface_compatibility(self) -> Self:
        # validate that the user interface control is compatible with the value constraints
        if self.userInterface:
            user_interface_control = self.userInterface.control
            if user_interface_control is None:
                return self
            if self.allowedValues and user_interface_control == FloatUserInterfaceControl.SPIN_BOX:
                raise ValueError(
                    f"User interface control {user_interface_control.name} cannot be used when 'allowedValues' is provided"
                )
            if (
                not self.allowedValues
                and user_interface_control == FloatUserInterfaceControl.DROPDOWN_LIST
            ):
                raise ValueError(
                    f"User interface control {user_interface_control.name} requires that 'allowedValues' be provided"
                )
            if (
                self.userInterface.singleStepDelta
                and user_interface_control != FloatUserInterfaceControl.SPIN_BOX
            ):
                raise ValueError(
                    f"User interface control {user_interface_control.name} cannot be used when 'singleStepDelta' is provided"
                )

        return self

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

    def __new__(cls, value: str, *, context: ModelParsingContextInterface = ModelParsingContext()):
        return super().__new__(cls, value, context=context)


class AttributeCapabilityName(FormatString):
    """The name of an attrubute capability."""

    _min_length = 1
    _max_length = 100

    def __new__(cls, value: str, *, context: ModelParsingContextInterface = ModelParsingContext()):
        return super().__new__(cls, value, context=context)


class AttributeCapabilityValue(FormatString):
    _min_length = 1

    def __new__(cls, value: str, *, context: ModelParsingContextInterface = ModelParsingContext()):
        return super().__new__(cls, value, context=context)


AttributeCapabilityList = Annotated[
    list[AttributeCapabilityValue], Field(min_length=1, max_length=50)
]


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
    min: Optional[Decimal] = None
    max: Optional[Decimal] = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str, info: ValidationInfo) -> str:
        validate_amount_capability_name(
            capability_name=v, standard_capabilities=_STANDARD_AMOUNT_CAPABILITIES_NAMES
        )
        return v

    @field_validator("min")
    @classmethod
    def _validate_min(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is None:
            return v
        if v < 0:
            raise ValueError(f"Value {v} must be zero or greater")
        return v

    @field_validator("max")
    @classmethod
    def _validate_max(cls, v: Optional[Decimal], info: ValidationInfo) -> Optional[Decimal]:
        if v is None:
            return v
        if v <= 0:
            raise ValueError("Value must be greater than 0")
        v_min = info.data.get("min")
        if v_min is not None and v_min > v:
            raise ValueError("Value for 'max' must be greater or equal to 'min'")
        return v


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
    min: Optional[Union[Decimal, FormatString]] = None
    max: Optional[Union[Decimal, FormatString]] = None

    _job_creation_metadata = JobCreationMetadata(
        create_as=JobCreateAsMetadata(model=AmountRequirement),
        resolve_fields={"name", "min", "max"},
    )

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: AmountCapabilityName, info: ValidationInfo) -> AmountCapabilityName:
        validate_amount_capability_name(
            capability_name=v, standard_capabilities=_STANDARD_AMOUNT_CAPABILITIES_NAMES
        )
        return v

    @field_validator("min", mode="before")
    @classmethod
    def _validate_min(
        cls, v: Optional[Any], info: ValidationInfo
    ) -> Optional[Union[Decimal, FormatString]]:
        if v is None:
            return v
        context = cast(Optional[ModelParsingContext], info.context)
        if isinstance(v, str):
            if context and "FEATURE_BUNDLE_1" not in context.extensions:
                # Try to parse as Decimal, fail if not
                try:
                    dec_val = Decimal(v)
                    if dec_val < 0:
                        raise ValueError("Value must be zero or greater")
                    return dec_val
                except InvalidOperation:
                    raise ValueError(
                        "min as a format string requires the FEATURE_BUNDLE_1 extension."
                    )
            return validate_float_fmtstring_field(v, ge=Decimal(0), context=context)
        if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool):
            dec_val = Decimal(str(v))
            if dec_val < 0:
                raise ValueError(f"Value {v} must be zero or greater")
            return dec_val
        raise ValueError("Value must be a number or string")

    @field_validator("max", mode="before")
    @classmethod
    def _validate_max(
        cls, v: Optional[Any], info: ValidationInfo
    ) -> Optional[Union[Decimal, FormatString]]:
        if v is None:
            return v
        context = cast(Optional[ModelParsingContext], info.context)
        if isinstance(v, str):
            if context and "FEATURE_BUNDLE_1" not in context.extensions:
                # Try to parse as Decimal, fail if not
                try:
                    dec_val = Decimal(v)
                    if dec_val <= 0:
                        raise ValueError("Value must be greater than 0")
                    return dec_val
                except InvalidOperation:
                    raise ValueError(
                        "max as a format string requires the FEATURE_BUNDLE_1 extension."
                    )
            return validate_float_fmtstring_field(v, ge=Decimal(0), context=context)
        if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool):
            dec_val = Decimal(str(v))
            if dec_val <= 0:
                raise ValueError("Value must be greater than 0")
            return dec_val
        raise ValueError("Value must be a number or string")

    @model_validator(mode="after")
    def _validate_min_max_relationship(self) -> Self:
        # Can only validate relationship if both are concrete values (not format strings)
        if (
            self.min is not None
            and self.max is not None
            and not isinstance(self.min, FormatString)
            and not isinstance(self.max, FormatString)
        ):
            if self.min > self.max:
                raise ValueError("Value for 'max' must be greater or equal to 'min'")
        return self

    @model_validator(mode="before")
    @classmethod
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
    anyOf: Optional[list[str]] = None
    allOf: Optional[list[str]] = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        validate_attribute_capability_name(
            capability_name=v, standard_capabilities=_STANDARD_ATTRIBUTE_CAPABILITIES_NAMES
        )
        return v

    @field_validator("allOf")
    @classmethod
    def _validate_allof(
        cls, v: Optional[AttributeCapabilityList], info: ValidationInfo
    ) -> Optional[AttributeCapabilityList]:
        if v is None:
            return v
        AttributeRequirementTemplate._validate_attribute_list(v, info, True)
        return v

    @field_validator("anyOf")
    @classmethod
    def _validate_anyof(
        cls, v: Optional[AttributeCapabilityList], info: ValidationInfo
    ) -> Optional[AttributeCapabilityList]:
        if v is None:
            return v
        AttributeRequirementTemplate._validate_attribute_list(v, info, False)
        return v


class AttributeRequirementTemplate(OpenJDModel_v2023_09):
    """An attribute requirement entry for a step, to specify which
    host capabilities the step requires from.

    Attribute capabilities are the mechanism for defining an
    attribute of the worker for a Step to require, such as its
    CPU architecture.
    """

    name: AttributeCapabilityName
    anyOf: Optional[AttributeCapabilityList] = None  # noqa: N815
    allOf: Optional[AttributeCapabilityList] = None  # noqa: N815

    _job_creation_metadata = JobCreationMetadata(
        create_as=JobCreateAsMetadata(model=AttributeRequirement),
        resolve_fields={"name", "anyOf", "allOf"},
    )

    _attribute_capability_value_regex: ClassVar[re.Pattern] = re.compile(
        r"(?-m:^(?:[a-zA-Z_][a-zA-Z0-9_\-]*)\Z)"
    )
    _attribute_capability_value_max_length: int = 100

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        validate_attribute_capability_name(
            capability_name=v, standard_capabilities=_STANDARD_ATTRIBUTE_CAPABILITIES_NAMES
        )
        return v

    @classmethod
    def _validate_attribute_list(
        cls,
        v: Union[list[Union[AttributeCapabilityValue, str]], AttributeCapabilityList],
        info: ValidationInfo,
        is_allof: bool,
    ) -> None:
        # This function is also called from AttributeRequirement
        try:
            capability_name = info.data["name"].lower()
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
                if isinstance(item, FormatString) and len(item.expressions) > 0:
                    continue
                # §3.3.2: attribute values follow capability naming, which is
                # case-insensitive, so "LINUX" matches "linux".
                if item.lower() not in standard_capability["values"]:
                    raise ValueError(
                        f"Values must be from {' '.join(standard_capability['values'])}"
                    )
        else:
            for item in v:
                # If it has expressions like "{{ Param.SomeValue }}", will
                # validate when those values are substituted.
                if isinstance(item, FormatString) and len(item.expressions) > 0:
                    continue
                if not cls._attribute_capability_value_regex.match(item):
                    raise ValueError(f"Value {item} is not a valid attribute capability value.")
                attribute_capability_value_max_length = cast(
                    ModelPrivateAttr, cls._attribute_capability_value_max_length
                ).get_default()
                if len(item) > attribute_capability_value_max_length:
                    raise ValueError(
                        f"Value {item} exceeds {attribute_capability_value_max_length} character length limit."
                    )

    @field_validator("allOf")
    @classmethod
    def _validate_allof(
        cls, v: Optional[AttributeCapabilityList], info: ValidationInfo
    ) -> Optional[AttributeCapabilityList]:
        if v is None:
            return v
        cls._validate_attribute_list(v, info, True)
        return v

    @field_validator("anyOf")
    @classmethod
    def _validate_anyof(
        cls, v: Optional[AttributeCapabilityList], info: ValidationInfo
    ) -> Optional[AttributeCapabilityList]:
        if v is None:
            return v
        cls._validate_attribute_list(v, info, False)
        return v

    @model_validator(mode="before")
    @classmethod
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

    @field_validator("amounts")
    @classmethod
    def _validate_amounts(
        cls, v: Optional[list[AmountRequirementTemplate]]
    ) -> Optional[list[AmountRequirementTemplate]]:
        if v is None:
            return v
        if len(v) == 0:
            raise ValueError("List must contain at least one element or not be defined.")
        return validate_unique_elements(v, item_value=lambda v: v.name.lower(), property="name")

    @field_validator("attributes")
    @classmethod
    def _validate_attributes(
        cls, v: Optional[list[AttributeRequirementTemplate]]
    ) -> Optional[list[AttributeRequirementTemplate]]:
        if v is None:
            return v
        if len(v) == 0:
            raise ValueError("List must contain at least one element or not be defined.")
        return validate_unique_elements(v, item_value=lambda v: v.name.lower(), property="name")

    @model_validator(mode="after")
    def _validate(self) -> Self:
        amounts = self.amounts
        attributes = self.attributes
        if amounts is None and attributes is None:
            raise ValueError(
                "Must define at least one of 'amounts' or 'attributes' if defining this property."
            )
        total_amounts = len(amounts) if amounts is not None else 0
        total_attributes = len(attributes) if attributes is not None else 0
        total = total_amounts + total_attributes
        if total > self._max_allowed_requirements:
            raise ValueError(
                f"The total number of requirements must not exceed {self._max_allowed_requirements}. {total} requirements defined."
            )
        return self


# ==================================================================
# ========================== Template Types ========================
# ==================================================================


class StepDependency(OpenJDModel_v2023_09):
    dependsOn: StepName


StepEnvironmentList = Annotated[list[Environment], Field(min_length=1)]
StepDependenciesList = Annotated[list[StepDependency], Field(min_length=1)]


# Target model for a StepTemplate when instantiating a job.
class Step(OpenJDModel_v2023_09):
    name: StepName
    script: StepScript
    description: Optional[Description] = None
    stepEnvironments: Optional[StepEnvironmentList] = None
    parameterSpace: Optional[StepParameterSpace] = None  # noqa: N815
    hostRequirements: Optional[HostRequirements] = None
    dependencies: Optional[StepDependenciesList] = None
    # RFC 0007 (EXPR): the step-level `let` bindings, preserved from the
    # StepTemplate so the runtime can seed them when entering the step's
    # environments — a step environment's variables and actions may reference
    # them. The step's own script carries a merged copy (step bindings first)
    # for the task-run path.
    let: Optional[list[str]] = None


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
        python (Optional[SimpleAction]): Python script syntax sugar (FEATURE_BUNDLE_1).
        bash (Optional[SimpleAction]): Bash script syntax sugar (FEATURE_BUNDLE_1).
        cmd (Optional[SimpleAction]): Windows cmd script syntax sugar (FEATURE_BUNDLE_1).
        powershell (Optional[SimpleAction]): PowerShell script syntax sugar (FEATURE_BUNDLE_1).
        node (Optional[SimpleAction]): Node.js script syntax sugar (FEATURE_BUNDLE_1).
    """

    name: StepName
    description: Optional[Description] = None
    script: Optional[StepScript] = None
    stepEnvironments: Optional[StepEnvironmentList] = None
    parameterSpace: Optional[StepParameterSpaceDefinition] = None  # noqa: N815
    hostRequirements: Optional[HostRequirementsTemplate] = None
    dependencies: Optional[StepDependenciesList] = None
    python: Optional[SimpleAction] = None
    bash: Optional[SimpleAction] = None
    cmd: Optional[SimpleAction] = None
    powershell: Optional[SimpleAction] = None
    node: Optional[SimpleAction] = None
    let: Optional[list[str]] = None

    # Step.Name is available to the step's script and step environments, but
    # only when the EXPR extension is enabled (RFC 0007).
    _template_variable_definitions = DefinesTemplateVariables(expr_inject={"|Step.Name"})

    @field_validator("let")
    @classmethod
    def _validate_let(cls, v: Any, info: ValidationInfo) -> Any:
        return validate_let_field(v, info)

    def _extend_step_symtab(self: Any, symtab: SymbolTable) -> SymbolTable:
        """Per-step symbol table for job instantiation, mirroring openjd-rs's
        ``instantiate_step``: seeds ``Step.Name`` and evaluates the step-level
        EXPR ``let`` bindings (RFC 0007 §3.6) in template scope, so the step's
        parameter space, host requirements, and script instantiate against
        them. Script-level ``let`` bindings are *not* evaluated here — they
        resolve at session time.

        ``Step.Name`` and ``let`` references only pass template validation
        with the EXPR extension enabled, so seeding them unconditionally does
        not change the behavior of non-EXPR templates.
        """
        step_symtab = SymbolTable(source=symtab)
        step_symtab["Step.Name"] = str(self.name)
        if self.let:
            from .._let_bindings import evaluate_let_bindings

            evaluate_let_bindings(symtab=step_symtab, let_bindings=self.let)
        return step_symtab

    _template_variable_sources = {
        "script": {"__self__", "parameterSpace"},
        "stepEnvironments": {"__self__"},
        # RFC 0007 §3.6: step-level `let` names (defined on __self__) are in
        # scope for the step's parameter space and host requirements.
        "parameterSpace": {"__self__"},
        "hostRequirements": {"__self__"},
        "python": {"__self__", "parameterSpace"},
        "bash": {"__self__", "parameterSpace"},
        "cmd": {"__self__", "parameterSpace"},
        "powershell": {"__self__", "parameterSpace"},
        "node": {"__self__", "parameterSpace"},
    }
    _job_creation_metadata = JobCreationMetadata(
        create_as=JobCreateAsMetadata(model=Step),
        exclude_fields={"python", "bash", "cmd", "powershell", "node"},
        transform=lambda t: cast("StepTemplate", t).resolve_syntax_sugar(),
        extends_symtab=_extend_step_symtab,
    )

    @field_validator("name")
    @classmethod
    def _validate_step_name(cls, v: str, info: ValidationInfo) -> str:
        context = cast(Optional[ModelParsingContext], info.context)
        max_len = 512 if context and "FEATURE_BUNDLE_1" in context.extensions else 64
        if len(v) > max_len:
            raise ValueError(f"name must be at most {max_len} characters long")
        return v

    @model_validator(mode="before")
    @classmethod
    def _validate_script_or_interpreter(
        cls, values: dict[str, Any], info: ValidationInfo
    ) -> dict[str, Any]:
        if not isinstance(values, dict):
            raise ValueError("Expected a dictionary of values")

        context = cast(Optional[ModelParsingContext], info.context)
        interpreter_keys = {i.value for i in ScriptInterpreter}
        has_script = "script" in values
        has_interpreter = any(k in values for k in interpreter_keys)
        interpreter_count = sum(1 for k in interpreter_keys if k in values)

        # Check for FEATURE_BUNDLE_1 extension if using interpreter syntax sugar
        if has_interpreter:
            if context and "FEATURE_BUNDLE_1" not in context.extensions:
                raise ValueError(
                    "Script interpreter syntax sugar (python, bash, cmd, powershell, node) "
                    "requires the FEATURE_BUNDLE_1 extension."
                )

        # Must have exactly one of: script or an interpreter
        if has_script and has_interpreter:
            raise ValueError(
                "Cannot specify both 'script' and script interpreter "
                "(python, bash, cmd, powershell, node)."
            )
        if not has_script and not has_interpreter:
            raise ValueError(
                "Must specify either 'script' or a script interpreter "
                "(python, bash, cmd, powershell, node)."
            )
        if interpreter_count > 1:
            raise ValueError(
                "Cannot specify multiple script interpreters. "
                "Choose one of: python, bash, cmd, powershell, node."
            )

        return values

    @field_validator("dependencies")
    @classmethod
    def _validate_no_duplicate_deps(
        cls, v: Optional[StepDependenciesList]
    ) -> Optional[StepDependenciesList]:
        if v is None:
            return v
        deps = set(v)
        if len(deps) != len(v):
            raise ValueError("Duplicate dependencies are not allowed.")
        return v

    @field_validator("stepEnvironments")
    @classmethod
    def _unique_environment_names(
        cls, v: Optional[StepEnvironmentList]
    ) -> Optional[StepEnvironmentList]:
        if v is not None:
            return validate_unique_elements(v, item_value=lambda v: v.name, property="name")
        return v

    @model_validator(mode="after")
    def _validate_no_self_dependency(self) -> Self:
        # Dependency of the step upon itself is not allowed.
        deps: StepDependenciesList = self.dependencies or []
        if not deps:
            return self
        stepname = self.name
        if any(dep.dependsOn == stepname for dep in deps):
            raise ValueError("A step cannot depend upon itself.")
        return self

    def resolve_syntax_sugar(self) -> "StepTemplate":
        """Transform interpreter syntax sugar into equivalent script + embeddedFiles.

        If this StepTemplate uses script interpreter syntax sugar (python, bash, cmd,
        powershell, node) introduced in RFC 0004 (FEATURE_BUNDLE_1), returns a new
        StepTemplate with the equivalent script and embeddedFiles structure.
        If already using script, returns self unchanged.

        Returns:
            StepTemplate: A new StepTemplate with de-sugared script, or self if no sugar.
        """
        if self.script:
            # Step-level `let` (RFC 0007) is excluded from the instantiated Step
            # by the job-creation metadata, so fold it into the script's own
            # `let` (step bindings first, then the script's) so it survives into
            # the Job and the runtime resolves it. The model has already
            # validated reference/shadowing rules across both scopes at decode.
            if self.let:
                # The step's own `let` is preserved too (Step.let): the
                # runtime seeds it when entering the step's environments.
                merged_let = [*self.let, *(self.script.let or [])]
                new_script = self.script.model_copy(update={"let": merged_let})
                return self.model_copy(update={"script": new_script})
            return self

        for name, (command, ext, arg_prefix) in _INTERPRETER_MAP.items():
            simple_action = getattr(self, name, None)
            if simple_action is not None:
                break
        else:
            return self

        # Generate unique embedded file name from step name + random suffix
        # Max filename is 256, reserve 7 for "_" + 6-char suffix, and len(ext) for extension
        safe_name = re.sub(r"[^a-zA-Z0-9]", "_", self.name)
        max_name_len = 256 - 7 - len(ext)
        safe_name = safe_name[:max_name_len]
        suffix = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(6))
        embedded_name = f"{safe_name}_{suffix}"
        file_ref = f"{{{{Task.File.{embedded_name}}}}}"

        # Build args: prefix + file reference + user args
        args: list[ArgString] = [*(ArgString(arg) for arg in arg_prefix), ArgString(file_ref)]
        if simple_action.args:
            args.extend(simple_action.args)

        # Construct directly - inputs are already validated
        return StepTemplate.model_construct(
            name=self.name,
            description=self.description,
            script=StepScript.model_construct(
                actions=StepActions.model_construct(
                    onRun=Action.model_construct(
                        command=CommandString(command),
                        args=args,
                        timeout=simple_action.timeout,
                        cancelation=simple_action.cancelation,
                    )
                ),
                # Carry step-level `let` (RFC 0007) and the SimpleAction's own
                # `let` onto the de-sugared script (step bindings first) so they
                # are preserved into the Job and resolved at runtime.
                let=([*(self.let or []), *(simple_action.let or [])] or None),
                embeddedFiles=[
                    EmbeddedFileText.model_construct(
                        name=embedded_name,
                        type=EmbeddedFileTypes.TEXT,
                        filename=f"{embedded_name}{ext}",
                        runnable=True,
                        data=simple_action.script,
                    )
                ],
            ),
            stepEnvironments=self.stepEnvironments,
            parameterSpace=self.parameterSpace,
            hostRequirements=self.hostRequirements,
            dependencies=self.dependencies,
            # Preserved for the runtime to seed when entering the step's
            # environments (RFC 0007).
            let=self.let,
        )


StepTemplateList = Annotated[list[StepTemplate], Field(min_length=1)]
# ----- EXPR extension (RFC 0007) BOOL job parameter -----


class BoolUserInterfaceControl(str, Enum):
    CHECK_BOX = "CHECK_BOX"
    HIDDEN = "HIDDEN"


class JobBoolParameterDefinitionUserInterface(OpenJDModel_v2023_09):
    """User interface attributes for a job bool parameter."""

    control: Optional[BoolUserInterfaceControl] = None
    label: Optional[UserInterfaceLabelStringValue] = None
    groupLabel: Optional[UserInterfaceLabelStringValue] = None  # noqa: N815


# Accepted string spellings for boolean defaults/values (case-insensitive),
# per RFC 0007 (BOOL parameter type).
_BOOL_TRUE_STRINGS = frozenset({"true", "yes", "on", "1"})
_BOOL_FALSE_STRINGS = frozenset({"false", "no", "off", "0"})


def _coerce_bool_value(value: Any) -> bool:
    """Coerce an RFC 0007 BOOL value to a Python bool, raising ValueError for
    anything outside the accepted set (bool, int 0/1, float 0.0/1.0, or a
    case-insensitive true/false/yes/no/on/off/1/0 string).
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int):  # bool already handled above
        if value in (0, 1):
            return bool(value)
        raise ValueError("BOOL value as an integer must be 0 or 1.")
    if isinstance(value, float):
        if value in (0.0, 1.0):
            return bool(value)
        raise ValueError("BOOL value as a float must be 0.0 or 1.0.")
    if isinstance(value, str):
        low = value.lower()
        if low in _BOOL_TRUE_STRINGS:
            return True
        if low in _BOOL_FALSE_STRINGS:
            return False
        raise ValueError(
            "BOOL value as a string must be one of (case-insensitive): "
            "true, false, yes, no, on, off, 1, 0."
        )
    raise ValueError("BOOL value must be a boolean, 0/1, 0.0/1.0, or a boolean string.")


class JobBoolParameterDefinition(NameIdentifierLengthMixin, OpenJDModel_v2023_09):
    """A Job Parameter of type bool (EXPR extension, RFC 0007).

    Attributes:
        name (Identifier): A name by which the parameter is referenced.
        type (JobParameterType.BOOL): discriminator to identify the type.
        userInterface (Optional[JobBoolParameterDefinitionUserInterface]):
            User interface properties for this parameter.
        description (Optional[Description]): Free-form description.
        default (Optional[bool]): Default value if one is not provided.
    """

    name: Identifier
    type: Literal[JobParameterType.BOOL]
    userInterface: Optional[JobBoolParameterDefinitionUserInterface] = None
    description: Optional[Description] = None
    default: Optional[bool] = None

    _template_variable_definitions = DefinesTemplateVariables(
        defines={
            TemplateVariableDef(prefix="|Param.", resolves=ResolutionScope.TEMPLATE),
            TemplateVariableDef(prefix="|RawParam.", resolves=ResolutionScope.TEMPLATE, raw=True),
        },
        field="name",
    )
    _template_variable_sources = {"__export__": {"__self__"}}
    _job_creation_metadata = JobCreationMetadata(
        create_as=JobCreateAsMetadata(model=JobParameter),
        exclude_fields={"name", "userInterface", "default"},
        adds_fields=lambda this, symtab: {
            "value": symtab[f"RawParam.{cast(JobBoolParameterDefinition, this).name}"]
        },
    )

    @field_validator("type")
    @classmethod
    def _requires_expr_extension(
        cls, value: JobParameterType, info: ValidationInfo
    ) -> JobParameterType:
        context = cast(Optional[ModelParsingContext], info.context)
        if context and "EXPR" not in context.extensions:
            raise ValueError("The BOOL job parameter type requires the EXPR extension.")
        return value

    @field_validator("default", mode="before")
    @classmethod
    def _validate_default(cls, value: Optional[Any]) -> Optional[bool]:
        if value is None:
            return None
        # Raises ValueError for values outside the accepted boolean set.
        return _coerce_bool_value(value)

    # override
    def _check_constraints(self, value: Any) -> None:
        if value is None:
            raise ValueError(f"No value given for {self.name}.")
        try:
            _coerce_bool_value(value)
        except ValueError as exc:
            raise ValueError(f"Value ({value}) for parameter {self.name}: {exc}")


# ----- EXPR extension (RFC 0007) LIST[*] and RANGE_EXPR job parameters -----


class _ListParameterUserInterface(OpenJDModel_v2023_09):
    # Permissive: list parameter UI controls vary by element type
    # (LINE_EDIT_LIST, SPIN_BOX_LIST, CHECK_BOX_LIST, HIDDEN, ...) and carry
    # type-specific fields (singleStepDelta, decimals, fileFilters, ...).
    # The UI block is non-functional metadata and not exercised by the
    # conformance .invalid fixtures, so accept any control name and ignore
    # extra UI fields rather than enumerating every variant.
    model_config = ConfigDict(extra="ignore", frozen=True)

    control: Optional[str] = None
    label: Optional[UserInterfaceLabelStringValue] = None
    groupLabel: Optional[UserInterfaceLabelStringValue] = None  # noqa: N815


class _ListStringItemConstraint(OpenJDModel_v2023_09):
    """`item:` constraints for LIST[STRING] / LIST[PATH] elements."""

    allowedValues: Optional[list[ParameterStringValue]] = None  # noqa: N815
    minLength: Optional[StrictInt] = None  # noqa: N815
    maxLength: Optional[StrictInt] = None  # noqa: N815


class _ListIntItemConstraint(OpenJDModel_v2023_09):
    """`item:` constraints for LIST[INT] elements (and the inner items of
    LIST[LIST[INT]])."""

    allowedValues: Optional[list[StrictInt]] = None  # noqa: N815
    minValue: Optional[StrictInt] = None  # noqa: N815
    maxValue: Optional[StrictInt] = None  # noqa: N815


class _ListFloatItemConstraint(OpenJDModel_v2023_09):
    """`item:` constraints for LIST[FLOAT] elements."""

    allowedValues: Optional[list[Decimal]] = None  # noqa: N815
    minValue: Optional[Decimal] = None  # noqa: N815
    maxValue: Optional[Decimal] = None  # noqa: N815


class _ListListIntInnerConstraint(OpenJDModel_v2023_09):
    """`item:` constraints for the inner lists of LIST[LIST[INT]]."""

    minLength: Optional[StrictInt] = None  # noqa: N815
    maxLength: Optional[StrictInt] = None  # noqa: N815
    item: Optional[_ListIntItemConstraint] = None


def _check_list_length(
    name: str, values: list[Any], min_len: Optional[int], max_len: Optional[int]
) -> None:
    if min_len is not None and len(values) < min_len:
        raise ValueError(
            f"Parameter {name}: list length {len(values)} is below minLength {min_len}."
        )
    if max_len is not None and len(values) > max_len:
        raise ValueError(
            f"Parameter {name}: list length {len(values)} exceeds maxLength {max_len}."
        )


def _check_string_item(name: str, item: Any, c: Optional[_ListStringItemConstraint]) -> None:
    if not isinstance(item, str):
        raise ValueError(
            f"Parameter {name}: list items must be strings, got {type(item).__name__}."
        )
    if c is None:
        return
    if c.minLength is not None and len(item) < c.minLength:
        raise ValueError(
            f"Parameter {name}: item {item!r} is shorter than item.minLength {c.minLength}."
        )
    if c.maxLength is not None and len(item) > c.maxLength:
        raise ValueError(
            f"Parameter {name}: item {item!r} is longer than item.maxLength {c.maxLength}."
        )
    if c.allowedValues is not None and item not in c.allowedValues:
        raise ValueError(f"Parameter {name}: item {item!r} is not in item.allowedValues.")


def _check_numeric_item_bounds(
    name: str,
    item: Any,
    compare: Any,
    min_value: Any,
    max_value: Any,
    allowed_values: Any,
) -> None:
    """Shared minValue / maxValue / allowedValues check for the numeric LIST
    item types. ``item`` is used only in error messages; ``compare`` is the
    value the bounds are tested against (the int itself for LIST[INT], the
    Decimal form for LIST[FLOAT])."""
    if min_value is not None and compare < min_value:
        raise ValueError(f"Parameter {name}: item {item} is below item.minValue {min_value}.")
    if max_value is not None and compare > max_value:
        raise ValueError(f"Parameter {name}: item {item} is above item.maxValue {max_value}.")
    if allowed_values is not None and compare not in allowed_values:
        raise ValueError(f"Parameter {name}: item {item} is not in item.allowedValues.")


def _check_int_item(name: str, item: Any, c: Optional[_ListIntItemConstraint]) -> None:
    if isinstance(item, bool) or not isinstance(item, int):
        raise ValueError(
            f"Parameter {name}: list items must be integers, got {type(item).__name__}."
        )
    if c is None:
        return
    _check_numeric_item_bounds(name, item, item, c.minValue, c.maxValue, c.allowedValues)


def _check_float_item(name: str, item: Any, c: Optional[_ListFloatItemConstraint]) -> None:
    if isinstance(item, bool) or not isinstance(item, (int, float, Decimal)):
        raise ValueError(
            f"Parameter {name}: list items must be numbers, got {type(item).__name__}."
        )
    val = Decimal(str(item))
    if c is None:
        return
    _check_numeric_item_bounds(name, item, val, c.minValue, c.maxValue, c.allowedValues)


def _expr_param_gate(value: JobParameterType, info: ValidationInfo) -> JobParameterType:
    context = cast(Optional[ModelParsingContext], info.context)
    if context and "EXPR" not in context.extensions:
        raise ValueError(f"The {value.value} job parameter type requires the EXPR extension.")
    return value


def _normalize_parameter_type_case(value: Any, info: ValidationInfo) -> Any:
    """Uppercase the ``type`` discriminator of each parameter definition when
    the EXPR extension is enabled (RFC 0007 makes parameter type names
    case-insensitive, e.g. ``int`` == ``INT``, ``list[int]`` == ``LIST[INT]``).
    Runs before discriminated-union resolution.
    """
    context = cast(Optional[ModelParsingContext], info.context)
    if not (context and "EXPR" in context.extensions):
        return value
    if not isinstance(value, list):
        return value
    normalized: list[Any] = []
    for item in value:
        if isinstance(item, dict) and isinstance(item.get("type"), str):
            item = {**item, "type": item["type"].upper()}
        normalized.append(item)
    return normalized


_LIST_PARAM_VARS = DefinesTemplateVariables(
    defines={
        TemplateVariableDef(prefix="|Param.", resolves=ResolutionScope.TEMPLATE),
        TemplateVariableDef(prefix="|RawParam.", resolves=ResolutionScope.TEMPLATE, raw=True),
    },
    field="name",
)

# Shared create-job metadata for the EXPR LIST[*]/RANGE_EXPR job-parameter
# definitions (RFC 0007). Like the scalar definitions, instantiation produces a
# JobParameter carrying the resolved value taken from the symbol table. The
# native value is supplied by create_job (RawParam.<name>); the type-specific
# definition fields (constraints, userInterface) are dropped. The exclude set
# is a superset covering every constraint field used across the list/range
# definitions, so the same metadata applies to all of them.
_LIST_RANGE_JOB_CREATION_METADATA = JobCreationMetadata(
    create_as=JobCreateAsMetadata(model=JobParameter),
    exclude_fields={
        "name",
        "userInterface",
        "default",
        "minLength",
        "maxLength",
        "item",
        "objectType",
        "dataFlow",
    },
    adds_fields=lambda this, symtab: {"value": symtab[f"RawParam.{getattr(this, 'name')}"]},
)


class _JobListParameterDefinitionBase(
    NameIdentifierLengthMixin, OpenJDModel_v2023_09, JobParameterInterface
):
    """Shared base for the EXPR (RFC 0007) ``LIST[*]`` job-parameter definitions.

    Collects the fields and machinery common to every list parameter type — the
    name/type-gate, the shared create-job metadata and template-variable
    definitions, list-length checking, and the EXPR-extension gate. Each concrete
    subclass declares only its ``type`` literal, its ``item`` constraint (if any),
    and overrides :meth:`_check_item` to validate a single element.

    Both the template ``default`` (via :meth:`_validate_default`) and any
    user-supplied value at create time (via :meth:`_check_constraints`) are
    validated through the same length + per-item checks, so list constraints are
    enforced consistently in both paths.
    """

    name: Identifier
    userInterface: Optional[_ListParameterUserInterface] = None
    description: Optional[Description] = None
    minLength: Optional[StrictInt] = None  # noqa: N815
    maxLength: Optional[StrictInt] = None  # noqa: N815
    default: Optional[list[Any]] = None

    _job_creation_metadata = _LIST_RANGE_JOB_CREATION_METADATA
    _template_variable_definitions = _LIST_PARAM_VARS
    _template_variable_sources = {"__export__": {"__self__"}}

    @field_validator("type", check_fields=False)
    @classmethod
    def _validate_type_gate(cls, value: JobParameterType, info: ValidationInfo) -> JobParameterType:
        return _expr_param_gate(value, info)

    def _check_item(self, item: Any) -> None:  # pragma: no cover - overridden
        """Validate a single list element. Overridden per element type."""
        raise NotImplementedError

    def _check_list_value(self, value: list[Any]) -> None:
        """Length + per-item validation shared by default- and value-checking."""
        _check_list_length(self.name, value, self.minLength, self.maxLength)
        for it in value:
            self._check_item(it)

    @model_validator(mode="after")
    def _validate_default(self) -> Self:
        if self.default is not None:
            self._check_list_value(self.default)
        return self

    # override (JobParameterInterface) — enforce list constraints on a
    # user-supplied value at create time, mirroring the scalar definitions.
    def _check_constraints(self, value: Any) -> None:
        if value is None:
            raise ValueError(f"No value given for {self.name}.")
        if not isinstance(value, list):
            raise ValueError(
                f"Parameter {self.name}: value must be a list, got {type(value).__name__}."
            )
        self._check_list_value(value)


class JobListStringParameterDefinition(_JobListParameterDefinitionBase):
    """LIST[STRING] job parameter (EXPR extension, RFC 0007)."""

    type: Literal[JobParameterType.LIST_STRING]
    item: Optional[_ListStringItemConstraint] = None

    def _check_item(self, item: Any) -> None:
        _check_string_item(self.name, item, self.item)


class JobListPathParameterDefinition(_JobListParameterDefinitionBase):
    """LIST[PATH] job parameter (EXPR extension, RFC 0007)."""

    type: Literal[JobParameterType.LIST_PATH]
    objectType: Optional[JobPathParameterDefinitionObjectType] = None  # noqa: N815
    dataFlow: Optional[JobPathParameterDefinitionDataFlow] = None  # noqa: N815
    item: Optional[_ListStringItemConstraint] = None

    # Path-typed parameters follow the scalar PATH scoping contract, not the
    # shared _LIST_PARAM_VARS: the processed Param.* value (list[path], with
    # path mapping applied) only exists at host/session scope, while the raw
    # RawParam.* value is a template-scope list[string] (RFC 0005 "Job
    # Parameter Types"; Template Schemas §2.12/§7.3.1). Mirrors openjd-rs's
    # build_template_scope_symtab, which excludes Param.* for PATH and
    # LIST[PATH] alike.
    _template_variable_definitions = DefinesTemplateVariables(
        defines={
            TemplateVariableDef(prefix="|Param.", resolves=ResolutionScope.SESSION),
            TemplateVariableDef(prefix="|RawParam.", resolves=ResolutionScope.TEMPLATE, raw=True),
        },
        field="name",
    )

    def _check_item(self, item: Any) -> None:
        _check_string_item(self.name, item, self.item)


class JobListIntParameterDefinition(_JobListParameterDefinitionBase):
    """LIST[INT] job parameter (EXPR extension, RFC 0007)."""

    type: Literal[JobParameterType.LIST_INT]
    item: Optional[_ListIntItemConstraint] = None

    def _check_item(self, item: Any) -> None:
        _check_int_item(self.name, item, self.item)


class JobListFloatParameterDefinition(_JobListParameterDefinitionBase):
    """LIST[FLOAT] job parameter (EXPR extension, RFC 0007)."""

    type: Literal[JobParameterType.LIST_FLOAT]
    item: Optional[_ListFloatItemConstraint] = None

    def _check_item(self, item: Any) -> None:
        _check_float_item(self.name, item, self.item)


class JobListBoolParameterDefinition(_JobListParameterDefinitionBase):
    """LIST[BOOL] job parameter (EXPR extension, RFC 0007)."""

    type: Literal[JobParameterType.LIST_BOOL]

    def _check_item(self, item: Any) -> None:
        # Reuse the BOOL coercion: each item must be boolean-like.
        try:
            _coerce_bool_value(item)
        except ValueError as exc:
            raise ValueError(f"Parameter {self.name}: {exc}")


class JobListListIntParameterDefinition(_JobListParameterDefinitionBase):
    """LIST[LIST[INT]] job parameter (EXPR extension, RFC 0007)."""

    type: Literal[JobParameterType.LIST_LIST_INT]
    item: Optional[_ListListIntInnerConstraint] = None

    def _check_item(self, item: Any) -> None:
        inner_c = self.item
        inner_item_c = inner_c.item if inner_c else None
        if not isinstance(item, list):
            raise ValueError(
                f"Parameter {self.name}: every element of LIST[LIST[INT]] must be a list."
            )
        if inner_c is not None:
            _check_list_length(self.name, item, inner_c.minLength, inner_c.maxLength)
        for it in item:
            _check_int_item(self.name, it, inner_item_c)


class JobRangeExprParameterDefinition(
    NameIdentifierLengthMixin, OpenJDModel_v2023_09, JobParameterInterface
):
    """RANGE_EXPR job parameter (EXPR extension, RFC 0007).

    The value is an integer range expression string (e.g. ``"1-100:10"``)
    validated against the existing ``IntRangeExpr`` grammar.
    """

    name: Identifier
    type: Literal[JobParameterType.RANGE_EXPR]
    _job_creation_metadata = _LIST_RANGE_JOB_CREATION_METADATA
    userInterface: Optional[_ListParameterUserInterface] = None
    description: Optional[Description] = None
    minLength: Optional[StrictInt] = None  # noqa: N815
    maxLength: Optional[StrictInt] = None  # noqa: N815
    default: Optional[ParameterStringValue] = None

    _template_variable_definitions = _LIST_PARAM_VARS
    _template_variable_sources = {"__export__": {"__self__"}}

    _validate_type_gate = field_validator("type")(
        classmethod(lambda cls, v, info: _expr_param_gate(v, info))
    )

    @field_validator("default")
    @classmethod
    def _validate_default(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        # Raises: ExpressionError / TokenError on a malformed range expression.
        IntRangeExpr.from_str(value)
        return value

    # override (JobParameterInterface) — validate a user-supplied range
    # expression string at create time against the IntRangeExpr grammar.
    def _check_constraints(self, value: Any) -> None:
        if value is None:
            raise ValueError(f"No value given for {self.name}.")
        if not isinstance(value, str):
            raise ValueError(
                f"Parameter {self.name}: RANGE_EXPR value must be a string, "
                f"got {type(value).__name__}."
            )
        try:
            # Raises: ExpressionError / TokenError on a malformed range expression.
            IntRangeExpr.from_str(value)
        except (ExpressionError, TokenError) as exc:
            raise ValueError(f"Value ({value}) for parameter {self.name}: {exc}")


JobParameterDefinitionList = Annotated[
    list[
        Annotated[
            Union[
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
            ],
            Field(..., discriminator="type"),
        ]
    ],
    Field(
        min_length=1,
        max_length=200,  # Extended limit; base limit of 50 is validated in JobTemplate
    ),
]
JobEnvironmentsList = Annotated[list[Environment], Field(min_length=1)]

JobParameters = dict[Identifier, JobParameter]


# Target model for a JobTemplate when instantiating a job.
class Job(OpenJDModel_v2023_09):
    name: JobName
    steps: list[Step]
    description: Optional[Description] = None
    parameters: Optional[JobParameters] = None
    jobEnvironments: Optional[JobEnvironmentsList] = None
    extensions: Optional[list[ExtensionName]] = None

    @field_validator("name")
    @classmethod
    def _validate_job_name_length(cls, v: str, info: ValidationInfo) -> str:
        context = cast(Optional[ModelParsingContext], info.context)
        max_len = 512 if context and "FEATURE_BUNDLE_1" in context.extensions else 128
        if len(v) > max_len:
            raise ValueError(f"String should have at most {max_len} characters")
        return v


class JobTemplate(OpenJDModel_v2023_09):
    """Definition of an Open Job Description Job Template.

    Attributes:
        specificationVersion (TemplateSpecificationVersion.v2023_09): The OpenJD schema version
            whose data model this follows.
        extensions (Optional[ExtensionNameList]): If provided, a non-empty list of named extensions to enable.
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
    extensions: Optional[ExtensionNameList] = Field(default=None, validate_default=True)
    name: JobTemplateName
    steps: StepTemplateList
    description: Optional[Description] = None
    parameterDefinitions: Optional[JobParameterDefinitionList] = None
    jobEnvironments: Optional[JobEnvironmentsList] = None
    # Note: Cannot call the field 'schema'; it masks a base class field
    schemaStr: Optional[str] = Field(None, alias="$schema")  # noqa: N815

    _template_variable_scope = ResolutionScope.TEMPLATE
    # Job.Name is available to the job's steps and environments, but only
    # when the EXPR extension is enabled (RFC 0007 §7.3.1).
    _template_variable_definitions = DefinesTemplateVariables(expr_inject={"|Job.Name"})
    _template_variable_sources = {
        "name": {"parameterDefinitions"},
        "steps": {"parameterDefinitions", "__self__"},
        "jobEnvironments": {"parameterDefinitions", "__self__"},
    }
    _job_creation_metadata = JobCreationMetadata(
        create_as=JobCreateAsMetadata(model=Job),
        resolve_fields={"name"},
        exclude_fields={"specificationVersion", "schemaStr"},
        reshape_field_to_dict={"parameterDefinitions": "name"},
        rename_fields={"parameterDefinitions": "parameters"},
    )

    @field_validator("name")
    @classmethod
    def _validate_job_name_length(cls, v: JobTemplateName, info: ValidationInfo) -> JobTemplateName:
        # Only validate length if there are no expressions to resolve
        if len(v.expressions) > 0:
            return v
        context = cast(Optional[ModelParsingContext], info.context)
        max_len = 512 if context and "FEATURE_BUNDLE_1" in context.extensions else 128
        if len(v) > max_len:
            raise ValueError(f"name must be at most {max_len} characters long")
        return v

    @field_validator("extensions")
    @classmethod
    def _unique_extension_names(
        cls, value: Optional[ExtensionNameList]
    ) -> Optional[ExtensionNameList]:
        if value is not None:
            return validate_unique_elements(
                value, item_value=lambda v: v, property="extension name"
            )
        return value

    @field_validator("extensions")
    @classmethod
    def _permitted_extension_names(
        cls, value: Optional[ExtensionNameList], info: ValidationInfo
    ) -> Optional[ExtensionNameList]:
        if info.context:
            context = cast(ModelParsingContext, info.context)
            if value is not None:
                # Before processing the extensions field, context.extensions is the list of supported extensions
                # that were requested in the call of the parse_job_template function.
                # Take the intersection of the input supported extensions with what is implemented
                # in this list, as the implementation needs to support an extension for it to be supported.
                supported_extensions = context.extensions.intersection(
                    cls.supported_extension_names()
                )

                unsupported_extensions = set(value).difference(supported_extensions)
                if unsupported_extensions:
                    raise ValueError(
                        f"Unsupported extension names: {', '.join(sorted(unsupported_extensions))}"
                    )

                # After processing the extensions field, context.extensions is the list of
                # extension names used by the template.
                context.extensions = set(value)
            else:
                context.extensions = set()
        return value

    @field_validator("steps")
    @classmethod
    def _unique_step_names(cls, v: StepTemplateList) -> StepTemplateList:
        return validate_unique_elements(v, item_value=lambda v: v.name, property="name")

    @field_validator("parameterDefinitions", mode="before")
    @classmethod
    def _normalize_parameter_type_case(cls, v: Any, info: ValidationInfo) -> Any:
        return _normalize_parameter_type_case(v, info)

    @field_validator("parameterDefinitions")
    @classmethod
    def _validate_parameter_definitions(
        cls, v: Optional[JobParameterDefinitionList], info: ValidationInfo
    ) -> Optional[JobParameterDefinitionList]:
        if v is not None:
            # Validate max length based on extension
            context = cast(Optional[ModelParsingContext], info.context)
            max_len = 200 if context and "FEATURE_BUNDLE_1" in context.extensions else 50
            if len(v) > max_len:
                raise ValueError(
                    f"parameterDefinitions must have at most {max_len} elements"
                    + (" (use FEATURE_BUNDLE_1 extension for up to 200)" if max_len == 50 else "")
                )
            return validate_unique_elements(v, item_value=lambda v: v.name, property="name")
        return v

    @field_validator("jobEnvironments")
    @classmethod
    def _unique_environment_names(
        cls, v: Optional[JobEnvironmentsList]
    ) -> Optional[JobEnvironmentsList]:
        if v is not None:
            return validate_unique_elements(v, item_value=lambda v: v.name, property="name")
        return v

    @classmethod
    def _root_template_prevalidator(
        cls, values: dict[str, Any], context: Optional[ModelParsingContextInterface]
    ) -> dict[str, Any]:
        # The name of this validator is very important. It is specifically looked for
        # in the _parse_model function to run this validation as a pre-root-validator
        # without the usual short-circuit of pre-root-validators that pydantic does.
        errors = prevalidate_model_template_variable_references(
            cast(Type[OpenJDModel], cls), values, context=context
        )
        if errors:
            raise ValidationError.from_exception_data(cls.__name__, line_errors=errors)
        return values

    @model_validator(mode="after")
    def _validate_no_step_dependency_cycles(self) -> Self:
        depgraph = dict[str, set[str]]()
        steplist = self.steps or []
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

        return self

    @model_validator(mode="after")
    def _validate_step_deps_exist(self) -> Self:
        # Check that the deps referenced by all steps actually exist

        steplist = self.steps or []
        if not steplist:
            return self

        errors = list[InitErrorDetails]()
        stepnames = set[str](step.name for step in steplist)
        for i, step in enumerate(steplist):
            if step.dependencies is not None:
                for j, dep in enumerate(step.dependencies):
                    if dep.dependsOn not in stepnames:
                        errors.append(
                            InitErrorDetails(
                                type="value_error",
                                # The path to the problematic dependsOn value
                                loc=("step", i, "dependencies", j, "dependsOn"),
                                ctx={"error": ValueError(f"Unknown step '{dep.dependsOn}'")},
                                input=dep.dependsOn,
                            )
                        )

        if errors:
            raise ValidationError.from_exception_data(self.__class__.__name__, errors)

        return self

    @model_validator(mode="after")
    def _validate_env_names_dont_match_step_env_names(self) -> Self:
        # Check that if we have job-level Environments defined that none of the defined Step-level
        # environments have the same name.
        # Names must be unique between Steps & Jobs.

        steplist = self.steps or []
        if not steplist:
            return self

        envlist = self.jobEnvironments or []
        if not envlist:
            return self

        job_env_names = set(env.name for env in envlist)

        errors = list[InitErrorDetails]()
        for i, step in enumerate(steplist):
            if step.stepEnvironments is not None:
                for j, env in enumerate(step.stepEnvironments):
                    if env.name in job_env_names:
                        errors.append(
                            InitErrorDetails(
                                type="value_error",
                                # The path to the problematic environment name
                                loc=("step", i, "stepEnvironments", j, "name"),
                                ctx={
                                    "error": ValueError(
                                        f"Name {env.name} must differ from the names of Environments defined at the root of the template."
                                    )
                                },
                                input=env.name,
                            )
                        )

        if errors:
            raise ValidationError.from_exception_data(self.__class__.__name__, errors)

        return self

    @model_validator(mode="after")
    def _validate_single_wrap_layer(self, info: ValidationInfo) -> Self:
        # RFC 0008 single-wrap-layer rule: at most one environment in any
        # session's stack may define wrap hooks. A session's stack is the
        # job's jobEnvironments plus exactly one step's stepEnvironments, so
        # "one wrap layer per session" reduces to: for every step,
        # (wrap envs in jobEnvironments) + (wrap envs in that step's
        # stepEnvironments) must be <= 1. Mirrors openjd-rs
        # validate_v2023_09/wrap_actions.rs.
        context = cast(Optional[ModelParsingContext], info.context) if info else None
        extensions = context.extensions if context else set()
        if "WRAP_ACTIONS" not in extensions:
            return self

        job_envs = self.jobEnvironments or []
        job_env_wrap_count = sum(1 for env in job_envs if _env_defines_wrap_hook(env))

        errors = list[InitErrorDetails]()

        # Multiple wrap layers in jobEnvironments are reachable from every
        # session, independent of any step's stepEnvironments.
        if job_env_wrap_count > 1:
            errors.append(
                InitErrorDetails(
                    type="value_error",
                    loc=("jobEnvironments",),
                    ctx={"error": ValueError(_SINGLE_WRAP_LAYER_MSG)},
                    input=self.jobEnvironments,
                )
            )

        # Each step's session is jobEnvironments + that step's
        # stepEnvironments. Only steps that declare stepEnvironments are
        # checked (a step with none adds no wrap layer of its own).
        for i, step in enumerate(self.steps or []):
            if step.stepEnvironments is None:
                continue
            step_env_wrap_count = sum(
                1 for env in step.stepEnvironments if _env_defines_wrap_hook(env)
            )
            if job_env_wrap_count + step_env_wrap_count > 1:
                errors.append(
                    InitErrorDetails(
                        type="value_error",
                        loc=("steps", i, "stepEnvironments"),
                        ctx={"error": ValueError(_SINGLE_WRAP_LAYER_MSG)},
                        input=step.stepEnvironments,
                    )
                )

        if errors:
            raise ValidationError.from_exception_data(self.__class__.__name__, errors)

        return self


class EnvironmentTemplate(OpenJDModel_v2023_09):
    """Definition of an Open Job Description Environment Template.

    Attributes:
        specificationVersion (TemplateSpecificationVersion.ENVIRONMENT_v2023_09): The OpenJD schema version
            whose data model this follows.
        extensions (Optional[ExtensionNameList]): If provided, a non-empty list of named extensions to enable.
        parameterDefinitions (Optional[JobParameterDefinitionList]): The job parameters that are available for use
            within this template, and that must have values defined for them when creating jobs while this
            environment template is included.
        environment (Environment): The definition of the Environment that is applied.
    """

    specificationVersion: Literal[TemplateSpecificationVersion.ENVIRONMENT_v2023_09]
    extensions: Optional[ExtensionNameList] = Field(default=None, validate_default=True)
    parameterDefinitions: Optional[JobParameterDefinitionList] = None
    environment: Environment

    _template_variable_scope = ResolutionScope.TEMPLATE
    # Job.Name is available within an environment template's environment
    # (RFC 0007 §7.3.1) when the EXPR extension is enabled: external
    # environments run within a session that always belongs to a job.
    _template_variable_definitions = DefinesTemplateVariables(expr_inject={"|Job.Name"})
    _template_variable_sources = {
        "environment": {"parameterDefinitions", "__self__"},
    }

    @field_validator("extensions")
    @classmethod
    def _unique_extension_names(
        cls, value: Optional[ExtensionNameList]
    ) -> Optional[ExtensionNameList]:
        if value is not None:
            return validate_unique_elements(
                value, item_value=lambda v: v, property="extension name"
            )
        return value

    @field_validator("extensions")
    @classmethod
    def _permitted_extension_names(
        cls, value: Optional[ExtensionNameList], info: ValidationInfo
    ) -> Optional[ExtensionNameList]:
        context = cast(ModelParsingContext, info.context)
        if value is not None:
            # Before processing the extensions field, context.extensions is the list of supported extensions.
            # Take the intersection of the input supported extensions with what is implemented
            # in this list, as the implementation needs to support an extension for it to be supported.
            supported_extensions = context.extensions.intersection(cls.supported_extension_names())

            unsupported_extensions = set(value).difference(supported_extensions)
            if unsupported_extensions:
                raise ValueError(
                    f"Unsupported extension names: {', '.join(sorted(unsupported_extensions))}"
                )

            # After processing the extensions field, context.extensions is the list of
            # extension names used by the template.
            context.extensions = set(value)
        else:
            context.extensions = set()
        return value

    @field_validator("parameterDefinitions", mode="before")
    @classmethod
    def _normalize_parameter_type_case(cls, v: Any, info: ValidationInfo) -> Any:
        return _normalize_parameter_type_case(v, info)

    @field_validator("parameterDefinitions")
    @classmethod
    def _validate_parameter_definitions(
        cls, v: Optional[JobParameterDefinitionList], info: ValidationInfo
    ) -> Optional[JobParameterDefinitionList]:
        if v is not None:
            # EnvironmentTemplate always has max 50 parameters (no extension increases this)
            if len(v) > 50:
                raise ValueError("parameterDefinitions must have at most 50 elements")
            return validate_unique_elements(v, item_value=lambda v: v.name, property="name")
        return v

    @classmethod
    def _root_template_prevalidator(
        cls, values: dict[str, Any], context: Optional[ModelParsingContextInterface]
    ) -> dict[str, Any]:
        # The name of this validator is very important. It is specifically looked for
        # in the _parse_model function to run this validation as a pre-root-validator
        # without the usual short-circuit of pre-root-validators that pydantic does.
        errors = prevalidate_model_template_variable_references(
            cast(Type[OpenJDModel], cls), values, context=context
        )
        if errors:
            raise ValidationError.from_exception_data(cls.__name__, line_errors=errors)
        return values
