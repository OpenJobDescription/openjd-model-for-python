# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from openjd.expr import ExpressionError
from openjd.model._v1 import (
    decode_environment_template,
    decode_job_template,
    merge_job_parameter_definitions,
    create_job,
)
from openjd.model._v1.errors import (
    DecodeValidationError,
    UnsupportedSchema,
)
import pytest


class TestUnsupportedSchema:
    def test_msg(self):
        # GIVEN
        error = UnsupportedSchema("Unsupported schema version: version")

        # THEN
        assert str(error) == "Unsupported schema version: version"


class TestDecodeValidationError:
    def test_msg(self):
        # GIVEN
        error = DecodeValidationError("Test message")

        # THEN
        assert str(error) == "Test message"


class TestExpressionError:
    def test_msg(self):
        # GIVEN
        error = ExpressionError("Test message")

        # THEN
        assert str(error) == "Test message"


class TestMergeRaisesOnConflict:
    """Merging job- and environment-template parameter definitions for
    the same name with conflicting types raises a ``ValueError`` —
    confirms the runtime path raises through to ``ValueError`` callers
    catching constraint-validation failures."""

    def test_raised_via_merge_caught_as_value_error(self) -> None:
        job_t = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "T",
                "parameterDefinitions": [{"name": "Frame", "type": "INT", "default": 5}],
                "steps": [
                    {
                        "name": "S",
                        "script": {"actions": {"onRun": {"command": "echo"}}},
                    }
                ],
            }
        )
        env_t = decode_environment_template(
            template={
                "specificationVersion": "environment-2023-09",
                "parameterDefinitions": [{"name": "Frame", "type": "STRING", "default": "x"}],
                "environment": {
                    "name": "E",
                    "script": {"actions": {"onEnter": {"command": "echo"}}},
                },
            }
        )
        with pytest.raises(ValueError, match="conflicting types"):
            merge_job_parameter_definitions(job_template=job_t, environment_templates=[env_t])


class TestExpressionErrorMapping:
    """``ModelError::Expression(...)`` raised during ``create_job``
    surfaces as ``openjd.expr.ExpressionError`` (the same class
    raised by ``evaluate_expression``), not as the generic
    ``ModelValidationError``. Pinned for parity with the v0
    reference's exception class hierarchy."""

    def test_chunk_default_task_count_invalid_int(self) -> None:
        """A CHUNK[INT] ``defaultTaskCount`` format string that
        resolves to a non-integer value at ``create_job`` time
        raises ``ExpressionError`` (not the generic
        ``ModelValidationError``)."""
        t = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "T",
                "extensions": ["TASK_CHUNKING"],
                "parameterDefinitions": [
                    {
                        "name": "Count",
                        "type": "STRING",
                        "default": "not-an-integer",
                    }
                ],
                "steps": [
                    {
                        "name": "S",
                        "parameterSpace": {
                            "taskParameterDefinitions": [
                                {
                                    "name": "Frame",
                                    "type": "CHUNK[INT]",
                                    "range": "1-10",
                                    "chunks": {
                                        "defaultTaskCount": "{{Param.Count}}",
                                        "rangeConstraint": "CONTIGUOUS",
                                    },
                                }
                            ]
                        },
                        "script": {
                            "actions": {
                                "onRun": {
                                    "command": "echo",
                                    "args": ["{{Task.Param.Frame}}"],
                                }
                            }
                        },
                    }
                ],
            },
            supported_extensions=["TASK_CHUNKING"],
        )
        with pytest.raises(ExpressionError, match="not a valid integer"):
            create_job(job_template=t, job_parameter_values={})
