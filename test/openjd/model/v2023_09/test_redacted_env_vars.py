# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest
from pydantic import ValidationError

from openjd.model._parse import _parse_model
from openjd.model.v2023_09 import (
    JobTemplate,
    ModelParsingContext,
)


def test_redacted_env_vars_extension_supported() -> None:
    """Test that the REDACTED_ENV_VARS extension can be used in a job template."""
    data = {
        "specificationVersion": "jobtemplate-2023-09",
        "extensions": ["REDACTED_ENV_VARS"],
        "name": "Test Job",
        "steps": [
            {
                "name": "step1",
                "script": {
                    "actions": {"onRun": {"command": "python", "args": ["{{Task.File.Run}}"]}},
                    "embeddedFiles": [
                        {
                            "name": "Run",
                            "type": "TEXT",
                            "data": 'print("openjd_redacted_env: SECRETVAR=SECRETVAL")',
                        }
                    ],
                },
            }
        ],
    }

    # It parses successfully when the REDACTED_ENV_VARS extension is requested
    _parse_model(
        model=JobTemplate,
        obj=data,
        context=ModelParsingContext(supported_extensions=["REDACTED_ENV_VARS"]),
    )


def test_redacted_env_vars_extension_not_supported() -> None:
    """Test that using REDACTED_ENV_VARS extension fails when not supported."""
    data = {
        "specificationVersion": "jobtemplate-2023-09",
        "extensions": ["REDACTED_ENV_VARS"],
        "name": "Test Job",
        "steps": [
            {
                "name": "step1",
                "script": {"actions": {"onRun": {"command": "echo", "args": ["test"]}}},
            }
        ],
    }

    # It fails to parse when REDACTED_ENV_VARS extension is not supported
    with pytest.raises(ValidationError) as excinfo:
        _parse_model(
            model=JobTemplate,
            obj=data,
            context=ModelParsingContext(),
        )
    assert "Unsupported extension names: REDACTED_ENV_VARS" in str(excinfo.value)
