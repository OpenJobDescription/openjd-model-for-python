# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from enum import Enum
import json
from typing import Any, Type

import pytest
import yaml

from openjd.model._v1 import (
    OpenJDModel,
    decode_environment_template,
    decode_environment_template_str,
    decode_job_template,
    decode_job_template_str,
    decode_template,
    document_string_to_object,
)
from openjd.model._v1.types import (
    DocumentType,
)
from openjd.model._v1.errors import (
    DecodeValidationError,
    ModelValidationError,
)
from openjd.model._v1.template import JobTemplate, EnvironmentTemplate


class TestDocStringToObject:
    @pytest.mark.parametrize(
        "document,doctype,expected",
        [
            pytest.param(
                json.dumps({"key": "value"}), DocumentType.JSON, {"key": "value"}, id="json doc"
            ),
            pytest.param(
                yaml.safe_dump({"key": "value"}), DocumentType.YAML, {"key": "value"}, id="yaml doc"
            ),
        ],
    )
    def test_success(self, document: str, doctype: DocumentType, expected: dict[str, Any]) -> None:
        # WHEN
        result = document_string_to_object(document=document, document_type=doctype)

        # THEN
        assert result == expected

    @pytest.mark.parametrize(
        "document,doctype",
        [
            pytest.param(json.dumps([1, 2, 3]), DocumentType.JSON, id="json doc"),
            pytest.param(yaml.safe_dump([1, 2, 3]), DocumentType.YAML, id="yaml doc"),
        ],
    )
    def test_not_a_dict(self, document: str, doctype: DocumentType) -> None:
        # THEN
        with pytest.raises(DecodeValidationError):
            document_string_to_object(document=document, document_type=doctype)

    @pytest.mark.parametrize(
        "document,doctype",
        [
            pytest.param("{", DocumentType.JSON, id="json doc"),
            pytest.param("-", DocumentType.YAML, id="yaml doc"),
        ],
    )
    def test_bad_parse(self, document: str, doctype: DocumentType) -> None:
        # THEN
        with pytest.raises(DecodeValidationError):
            document_string_to_object(document=document, document_type=doctype)


# `TestModelToObject` (and the `model_to_object` import) used to live
# here. The function was a v0/pydantic-era helper that walked a
# `BaseModel.model_dump()` result and converted nested `Decimal`
# instances back to strings; the v1 Rust-backed model types do not
# have an analogous "serialize whole model back to a JSON-shaped
# dict" method, and the spec now explicitly states `model_to_object`
# is a v0-only API. See `specs/python-model-interface.md`.


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
    def test_success(self, template: dict[str, Any], expected_class: Type[OpenJDModel]) -> None:
        # WHEN
        result = decode_job_template(template=template)

        # THEN
        assert isinstance(result, expected_class)


class TestDecodeTemplate:
    """``decode_template`` is a deprecated alias for ``decode_job_template``,
    kept for parity with the v0 / pure-Python reference module which also
    exports a deprecated ``decode_template``."""

    def test_returns_job_template(self) -> None:
        template = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "name",
            "steps": [{"name": "step", "script": {"actions": {"onRun": {"command": "echo"}}}}],
        }
        result = decode_template(template=template)
        assert isinstance(result, JobTemplate)
        assert result.name == "name"

    def test_forwards_supported_extensions(self) -> None:
        # An EXPR-extension expression in the template parses cleanly
        # only when the EXPR extension is in the caller's allowlist.
        template = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "name",
            "extensions": ["EXPR"],
            "steps": [{"name": "step", "script": {"actions": {"onRun": {"command": "echo"}}}}],
        }
        # Without EXPR in supported_extensions, the template fails decode
        # with ModelValidationError (the template requested an extension
        # the caller didn't allowlist).
        with pytest.raises(ModelValidationError):
            decode_template(template=template)
        # With EXPR allowed, the template decodes.
        result = decode_template(template=template, supported_extensions=["EXPR"])
        assert isinstance(result, JobTemplate)

    def test_rejects_environment_template(self) -> None:
        # Like ``decode_job_template``, the deprecated alias rejects
        # environment templates with ``DecodeValidationError``.
        with pytest.raises(DecodeValidationError):
            decode_template(template={"specificationVersion": "environment-2023-09"})


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
    def test_success(self, template: dict[str, Any], expected_class: Type[OpenJDModel]) -> None:
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
