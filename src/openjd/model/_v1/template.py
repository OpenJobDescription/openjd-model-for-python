# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Template-time model types.

Mirrors ``openjd_model::template`` in the underlying Rust crate.
These are the types you get back from ``decode_job_template`` and
``decode_environment_template`` — the raw, parsed template before
job creation has resolved parameters and let-bindings.

For job-time (resolved, post-``create_job``) types, see
``openjd.model._v1.job``.

The structural types whose names collide with their job-time
counterparts (``Action``, ``Environment``, ``CancelationMode``, …)
are exposed under both their short name (``Action``) and a
``Template``-prefixed alias (``TemplateAction``). The Rust pyclass
itself is registered with the prefixed name to disambiguate from
the job-time class with the same short name.
"""

from openjd._openjd_rs import (
    # Top-level documents (no collision)
    JobTemplate,
    EnvironmentTemplate,
    # Structural types — Template-prefixed to disambiguate from job-time
    TemplateAction,
    TemplateAmountRequirement,
    TemplateAttributeRequirement,
    TemplateCancelationMode,
    TemplateEmbeddedFile,
    TemplateEnvironment,
    TemplateEnvironmentActions,
    TemplateEnvironmentScript,
    TemplateHostRequirements,
    TemplateStepActions,
    TemplateStepDependency,
    TemplateStepScript,
    # Structural types with no name collision
    StepTemplate,
    SimpleAction,
    # JobParameterDefinition — 12 typed variants returned by
    # ``JobTemplate.parameter_definitions`` and
    # ``EnvironmentTemplate.parameter_definitions``.
    JobStringParameterDefinition,
    JobIntParameterDefinition,
    JobFloatParameterDefinition,
    JobPathParameterDefinition,
    # EXPR-extension job-parameter variants
    JobBoolParameterDefinition,
    JobRangeExprParameterDefinition,
    JobListStringParameterDefinition,
    JobListPathParameterDefinition,
    JobListIntParameterDefinition,
    JobListFloatParameterDefinition,
    JobListBoolParameterDefinition,
    JobListListIntParameterDefinition,
    # StepParameterSpaceDefinition + 5 typed task-parameter
    # definitions, returned by ``StepTemplate.parameter_space``.
    StepParameterSpaceDefinition,
    ChunksDefinition,
    IntTaskParameterDefinition,
    FloatTaskParameterDefinition,
    StringTaskParameterDefinition,
    PathTaskParameterDefinition,
    ChunkIntTaskParameterDefinition,
    # userInterface pyclasses (template-time, mirror the Rust
    # `template::*UserInterface` struct types). Returned by the
    # `user_interface` getter on each `Job*ParameterDefinition`.
    FileFilter,
    StringUserInterface,
    IntUserInterface,
    FloatUserInterface,
    PathUserInterface,
    BoolUserInterface,
    RangeExprUserInterface,
    ListSimpleUserInterface,
    ListPathUserInterface,
    ListIntUserInterface,
    ListFloatUserInterface,
    HiddenOnlyUserInterface,
)

# Short aliases for ergonomics. Both names refer to the same class
# object — ``Action is TemplateAction`` is True.
Action = TemplateAction
AmountRequirement = TemplateAmountRequirement
AttributeRequirement = TemplateAttributeRequirement
CancelationMode = TemplateCancelationMode
EmbeddedFile = TemplateEmbeddedFile
Environment = TemplateEnvironment
EnvironmentActions = TemplateEnvironmentActions
EnvironmentScript = TemplateEnvironmentScript
HostRequirements = TemplateHostRequirements
StepActions = TemplateStepActions
StepDependency = TemplateStepDependency
StepScript = TemplateStepScript


__all__ = (
    # Top-level
    "JobTemplate",
    "EnvironmentTemplate",
    # Short aliases
    "Action",
    "AmountRequirement",
    "AttributeRequirement",
    "CancelationMode",
    "EmbeddedFile",
    "Environment",
    "EnvironmentActions",
    "EnvironmentScript",
    "HostRequirements",
    "SimpleAction",
    "StepActions",
    "StepDependency",
    "StepScript",
    "StepTemplate",
    # Disambiguating aliases (same classes; useful in pickle bytes
    # and where users want to be explicit about template vs job time)
    "TemplateAction",
    "TemplateAmountRequirement",
    "TemplateAttributeRequirement",
    "TemplateCancelationMode",
    "TemplateEmbeddedFile",
    "TemplateEnvironment",
    "TemplateEnvironmentActions",
    "TemplateEnvironmentScript",
    "TemplateHostRequirements",
    "TemplateStepActions",
    "TemplateStepDependency",
    "TemplateStepScript",
    # JobParameterDefinition variants
    "JobBoolParameterDefinition",
    "JobFloatParameterDefinition",
    "JobIntParameterDefinition",
    "JobListBoolParameterDefinition",
    "JobListFloatParameterDefinition",
    "JobListIntParameterDefinition",
    "JobListListIntParameterDefinition",
    "JobListPathParameterDefinition",
    "JobListStringParameterDefinition",
    "JobPathParameterDefinition",
    "JobRangeExprParameterDefinition",
    "JobStringParameterDefinition",
    # StepParameterSpaceDefinition + 5 typed task-parameter
    # definitions, returned by ``StepTemplate.parameter_space``.
    "StepParameterSpaceDefinition",
    "ChunksDefinition",
    "IntTaskParameterDefinition",
    "FloatTaskParameterDefinition",
    "StringTaskParameterDefinition",
    "PathTaskParameterDefinition",
    "ChunkIntTaskParameterDefinition",
    # userInterface pyclasses
    "FileFilter",
    "StringUserInterface",
    "IntUserInterface",
    "FloatUserInterface",
    "PathUserInterface",
    "BoolUserInterface",
    "RangeExprUserInterface",
    "ListSimpleUserInterface",
    "ListPathUserInterface",
    "ListIntUserInterface",
    "ListFloatUserInterface",
    "HiddenOnlyUserInterface",
)
