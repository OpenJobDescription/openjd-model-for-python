# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Backward compatibility shim — re-exports from openjd.model._v1."""

from openjd.model._v1 import (
    FormatString,
    STANDARD_AMOUNT_CAPABILITIES,  # noqa: F401
    STANDARD_ATTRIBUTE_CAPABILITIES,  # noqa: F401
)
from openjd.model._v1.template import (
    EnvironmentTemplate,  # noqa: F401
    JobTemplate,  # noqa: F401
)
from openjd.model._v1.job import (
    Action,  # noqa: F401
    EmbeddedFile as EmbeddedFileText,  # noqa: F401
    Environment,  # noqa: F401
    EnvironmentScript,  # noqa: F401
    Job,  # noqa: F401
    Step,  # noqa: F401
    StepActions,  # noqa: F401
    StepParameterSpace,  # noqa: F401
    StepParameterSpaceIterator,  # noqa: F401
    StepScript,  # noqa: F401
)

RangeExpressionTaskParameterDefinition = dict
RangeListTaskParameterDefinition = dict

# Aliases matching old Pydantic model names
CommandString = FormatString
ArgString = FormatString
DataString = FormatString
EmbeddedFiles = list


class EmbeddedFileTypes:
    TEXT = "TEXT"


class ExtensionName:
    TASK_CHUNKING = "TASK_CHUNKING"
    REDACTED_ENV_VARS = "REDACTED_ENV_VARS"
    EXPR = "EXPR"
    FEATURE_BUNDLE_1 = "FEATURE_BUNDLE_1"

    def __iter__(self):
        return iter([self.TASK_CHUNKING, self.REDACTED_ENV_VARS, self.EXPR, self.FEATURE_BUNDLE_1])
