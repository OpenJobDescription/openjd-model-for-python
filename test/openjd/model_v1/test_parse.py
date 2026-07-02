# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from enum import Enum
import json
from typing import Any, Type, Union

import pytest

from openjd.model._v1 import (
    decode_environment_template,
    decode_environment_template_str,
    decode_job_template,
    decode_job_template_str,
)
from openjd.model._v1.types import (
    DocumentType,
)
from openjd.model._v1.errors import (
    DecodeValidationError,
    ModelValidationError,
)
from openjd.model._v1.template import JobTemplate, EnvironmentTemplate


class TestDecodeJobTemplate:
    @pytest.mark.parametrize(
        "template",
        [
            pytest.param({"notspecversion": "badvalue"}, id="missing specificationVersion field"),
            pytest.param({"specificationVersion": "badvalue"}, id="unknown version"),
            pytest.param(
                {"specificationVersion": "environment-2023-09"}, id="not a job template version"
            ),
        ],
    )
    def test_fail_cases(self, template: dict[str, Any]) -> None:
        # THEN
        with pytest.raises(DecodeValidationError):
            decode_job_template(template=template)

    @pytest.mark.parametrize(
        "template,expected_class",
        [
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "name",
                    "steps": [
                        {"name": "step", "script": {"actions": {"onRun": {"command": "do thing"}}}}
                    ],
                },
                JobTemplate,
                id="2023-09",
            ),
        ],
    )
    def test_success(
        self,
        template: dict[str, Any],
        expected_class: Union[Type[JobTemplate], Type[EnvironmentTemplate]],
    ) -> None:
        # WHEN
        result = decode_job_template(template=template)

        # THEN
        assert isinstance(result, expected_class)

    def test_empty_steps_raises_model_validation_error(self) -> None:
        # ``steps: []`` is structurally well-formed (parses cleanly) but
        # fails the model-level invariant that a job template must have
        # at least one step. This is a model-validation concern, not a
        # decode-validation concern, so v1 raises
        # ``ModelValidationError`` rather than ``DecodeValidationError``
        # (v0 raised the latter, which v1 deliberately corrects —
        # ``DecodeValidationError`` is reserved for parse-stage failures
        # like unknown specificationVersion or malformed YAML/JSON).
        # The divergence is documented in
        # ``specs/python-model-interface.md`` under "Exceptions".
        template = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "T",
            "steps": [],
        }
        with pytest.raises(ModelValidationError) as exc_info:
            decode_job_template(template=template)
        # Pin the message body (per the AGENTS.md "Test Quality Standard":
        # exception class + message body, not just class).
        assert str(exc_info.value) == (
            "1 validation error for JobTemplate\n" "JobTemplate: must have at least one step."
        )


class TestDecodeEnvironmentTemplate:
    @pytest.mark.parametrize(
        "template",
        [
            pytest.param({"notspecversion": "badvalue"}, id="missing specificationVersion field"),
            pytest.param({"specificationVersion": "badvalue"}, id="unknown version"),
            pytest.param(
                {"specificationVersion": "jobtemplate-2023-09"},
                id="not an environment template version",
            ),
        ],
    )
    def test_fail_cases(self, template: dict[str, Any]) -> None:
        # THEN
        with pytest.raises(DecodeValidationError):
            decode_environment_template(template=template)

    @pytest.mark.parametrize(
        "template,expected_class",
        [
            pytest.param(
                {
                    "specificationVersion": "environment-2023-09",
                    "environment": {
                        "name": "FooEnv",
                        "description": "A description",
                        "script": {
                            "actions": {"onEnter": {"command": "echo", "args": ["Hello", "World"]}}
                        },
                    },
                },
                EnvironmentTemplate,
                id="2023-09",
            ),
        ],
    )
    def test_success(
        self,
        template: dict[str, Any],
        expected_class: Union[Type[JobTemplate], Type[EnvironmentTemplate]],
    ) -> None:
        # WHEN
        result = decode_environment_template(template=template)

        # THEN
        assert isinstance(result, expected_class)


class MockExtensionName(str, Enum):
    """A mock enum with only SUPPORTED_NAME for testing."""

    SUPPORTED_NAME = "SUPPORTED_NAME"


class MockExtensionNameWithTwoNames(str, Enum):
    """A mock enum with only SUPPORTED_NAME for testing."""

    SUPPORTED_NAME = "SUPPORTED_NAME"
    ANOTHER_SUPPORTED_NAME = "ANOTHER_SUPPORTED_NAME"


@pytest.mark.parametrize(
    "template,template_type,decode_function",
    [
        pytest.param(
            {
                "name": "DemoJob",
                "specificationVersion": "jobtemplate-2023-09",
                "parameterDefinitions": [{"name": "Foo", "type": "FLOAT", "default": "12"}],
                "steps": [
                    {
                        "name": "DemoStep",
                        "script": {"actions": {"onRun": {"command": "echo"}}},
                    }
                ],
            },
            "JobTemplate",
            decode_job_template,
            id="job template",
        ),
        pytest.param(
            {
                "specificationVersion": "environment-2023-09",
                "environment": {
                    "name": "FooEnv",
                    "description": "A description",
                    "script": {"actions": {"onEnter": {"command": "echo"}}},
                },
            },
            "EnvironmentTemplate",
            decode_environment_template,
            id="environment template",
        ),
    ],
)
def test_template_extensions_list(template, template_type, decode_function) -> None:
    # Confirm the template doesn't include extensions yet and can be decoded
    assert "extensions" not in template
    decode_function(template=template)

    # When a known extension name is in the supported list, it's accepted
    template["extensions"] = ["TASK_CHUNKING"]
    decode_function(template=template, supported_extensions=["TASK_CHUNKING"])

    # If provided, the extensions list cannot be empty
    template["extensions"] = []
    with pytest.raises(ValueError) as excinfo:
        decode_function(template=template, supported_extensions=["TASK_CHUNKING"])
    assert "if provided, must be a non-empty list" in str(excinfo.value)

    # Extension not in supported_extensions is rejected
    template["extensions"] = ["TASK_CHUNKING"]
    with pytest.raises(ValueError) as excinfo:
        decode_function(template=template)
    assert "Unsupported extension names: TASK_CHUNKING" in str(excinfo.value)

    # Extension names cannot be repeated
    template["extensions"] = ["TASK_CHUNKING", "TASK_CHUNKING"]
    with pytest.raises(ValueError) as excinfo:
        decode_function(template=template, supported_extensions=["TASK_CHUNKING"])
        assert "Duplicate values for extension name are not allowed." in str(excinfo.value)

        # When the request list includes an unsupported extension name
        template["extensions"] = ["SUPPORTED_NAME"]
        with pytest.raises(ValueError) as excinfo:
            decode_function(template=template, supported_extensions=["UNSUPPORTED_NAME"])
        assert (
            f"1 validation errors for {template_type}\nextensions:\n\tUnsupported extension names: SUPPORTED_NAME"
            in str(excinfo.value)
        )

    # Unknown extension name is rejected even if in supported_extensions
    template["extensions"] = ["UNSUPPORTED_NAME"]
    with pytest.raises(ValueError) as excinfo:
        decode_function(template=template, supported_extensions=["UNSUPPORTED_NAME"])
    assert "Unsupported extension names: UNSUPPORTED_NAME" in str(excinfo.value)

    # Multiple known extensions can be enabled simultaneously
    template["extensions"] = ["TASK_CHUNKING", "EXPR"]
    decode_function(template=template, supported_extensions=["TASK_CHUNKING", "EXPR"])


class TestDecodeJobTemplateStr:
    """``decode_job_template_str`` wrapper: parses YAML or JSON
    directly, no intermediate dict. The wrapper lives on
    ``openjd.model._v1`` (re-exported); the underlying Rust function
    is in ``openjd._openjd_rs``."""

    _VALID_YAML = """
specificationVersion: jobtemplate-2023-09
name: SimpleJob
steps:
  - name: Step1
    script:
      actions:
        onRun:
          command: echo
          args: ["hello"]
"""
    _VALID_JSON = json.dumps(
        {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "JsonJob",
            "steps": [
                {
                    "name": "Step1",
                    "script": {"actions": {"onRun": {"command": "echo", "args": ["hi"]}}},
                }
            ],
        }
    )

    def test_yaml_default(self) -> None:
        t = decode_job_template_str(self._VALID_YAML)
        assert isinstance(t, JobTemplate)
        assert t.name == "SimpleJob"

    def test_yaml_explicit(self) -> None:
        t = decode_job_template_str(self._VALID_YAML, DocumentType.YAML)
        assert t.name == "SimpleJob"

    def test_json_explicit(self) -> None:
        t = decode_job_template_str(self._VALID_JSON, DocumentType.JSON)
        assert t.name == "JsonJob"

    def test_json_via_yaml_default(self) -> None:
        # YAML is a JSON superset; JSON parses fine under the YAML
        # default. Pin that.
        t = decode_job_template_str(self._VALID_JSON)
        assert t.name == "JsonJob"

    def test_supported_extensions_forwarded(self) -> None:
        # Template requests EXPR; supported_extensions allowlist must
        # include it for decoding to succeed.
        with_ext = """
specificationVersion: jobtemplate-2023-09
name: ExprJob
extensions: ["EXPR"]
steps:
  - name: S
    script:
      actions:
        onRun: {command: echo, args: ["hi"]}
"""
        # Allowed.
        t = decode_job_template_str(with_ext, supported_extensions=["EXPR"])
        assert t.name == "ExprJob"
        # Rejected with empty allowlist.
        with pytest.raises(ModelValidationError, match="Unsupported extension"):
            decode_job_template_str(with_ext)

    def test_invalid_yaml_raises(self) -> None:
        with pytest.raises(DecodeValidationError):
            decode_job_template_str("specificationVersion: nope")


class TestDecodeEnvironmentTemplateStr:
    """``decode_environment_template_str`` wrapper: parses YAML or
    JSON directly. Mirrors ``decode_job_template_str`` for environment
    templates."""

    _VALID_YAML = """
specificationVersion: environment-2023-09
environment:
  name: PythonVenv
  script:
    actions:
      onEnter: {command: python, args: ["-m", "venv", ".venv"]}
      onExit:  {command: rm, args: ["-rf", ".venv"]}
"""
    _VALID_JSON = json.dumps(
        {
            "specificationVersion": "environment-2023-09",
            "environment": {
                "name": "Env1",
                "script": {"actions": {"onEnter": {"command": "echo", "args": ["enter"]}}},
            },
        }
    )

    def test_yaml_default(self) -> None:
        e = decode_environment_template_str(self._VALID_YAML)
        assert isinstance(e, EnvironmentTemplate)
        assert e.environment.name == "PythonVenv"

    def test_json_explicit(self) -> None:
        e = decode_environment_template_str(self._VALID_JSON, DocumentType.JSON)
        assert e.environment.name == "Env1"

    def test_invalid_yaml_raises(self) -> None:
        with pytest.raises(DecodeValidationError):
            decode_environment_template_str(": not a mapping")
