# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from enum import Enum
import json
from typing import Any, Type
from unittest.mock import patch

import pytest
import yaml

from openjd.model import (
    DecodeValidationError,
    DocumentType,
    decode_environment_template,
    decode_job_template,
    document_string_to_object,
    model_to_object,
)
from openjd.model._types import OpenJDModel
import openjd
from openjd.model.v2023_09 import JobTemplate as JobTemplate_2023_09
from openjd.model.v2023_09 import EnvironmentTemplate as EnvironmentTemplate_2023_09


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


class TestModelToObject:
    @pytest.mark.parametrize(
        "template",
        [
            pytest.param(
                {
                    "name": "DemoJob",
                    "specificationVersion": "jobtemplate-2023-09",
                    "parameterDefinitions": [{"name": "Foo", "type": "FLOAT", "default": "12"}],
                    "steps": [
                        {
                            "name": "DemoStep",
                            "parameterSpace": {
                                "taskParameterDefinitions": [
                                    {"name": "Foo", "type": "FLOAT", "range": ["1.1", "1.2"]}
                                ]
                            },
                            "script": {
                                "actions": {
                                    "onRun": {"command": "echo", "args": ["Foo={{Param.Foo}}"]}
                                }
                            },
                        }
                    ],
                },
                id="translates Decimal to string",
            )
        ],
    )
    def test(self, template: dict[str, Any]) -> None:
        # GIVEN
        model = decode_job_template(template=template)

        # WHEN
        result = model_to_object(model=model)

        # THEN
        assert result == template


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
                JobTemplate_2023_09,
                id="2023-09",
            ),
        ],
    )
    def test_success(self, template: dict[str, Any], expected_class: Type[OpenJDModel]) -> None:
        # WHEN
        result = decode_job_template(template=template)

        # THEN
        assert isinstance(result, expected_class)


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
                EnvironmentTemplate_2023_09,
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
    FEATURE_BUNDLE_1 = "FEATURE_BUNDLE_1"


class MockExtensionNameWithTwoNames(str, Enum):
    """A mock enum with only SUPPORTED_NAME for testing."""

    SUPPORTED_NAME = "SUPPORTED_NAME"
    ANOTHER_SUPPORTED_NAME = "ANOTHER_SUPPORTED_NAME"
    FEATURE_BUNDLE_1 = "FEATURE_BUNDLE_1"


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
    with patch.object(openjd.model.v2023_09._model, "ExtensionName", MockExtensionName):
        # Confirm the template doesn't include extensions yet and can be decoded
        assert "extensions" not in template
        decode_function(template=template)

        # If an unimplemented name is provided to supported_extensions, it is ignored
        decode_function(template=template, supported_extensions=["UNSUPPORTED_NAME"])

        # When the requested extension name is in the supported list
        template["extensions"] = ["SUPPORTED_NAME"]
        model = decode_function(template=template, supported_extensions=["SUPPORTED_NAME"])
        assert model.extensions == ["SUPPORTED_NAME"]

        # If provided, the extensions list cannot be empty
        template["extensions"] = []
        with pytest.raises(DecodeValidationError) as excinfo:
            decode_function(template=template)
        assert (
            f"1 validation errors for {template_type}\nextensions:\n\tList should have at least 1 item after validation, not 0"
            in str(excinfo.value)
        )

        # By default no extensions are supported
        template["extensions"] = ["SUPPORTED_NAME"]
        with pytest.raises(DecodeValidationError) as excinfo:
            decode_function(template=template)
        assert (
            f"1 validation errors for {template_type}\nextensions:\n\tUnsupported extension names: SUPPORTED_NAME"
            in str(excinfo.value)
        )

        # Extension names cannot be repeated
        template["extensions"] = ["SUPPORTED_NAME", "SUPPORTED_NAME"]
        with pytest.raises(DecodeValidationError) as excinfo:
            decode_function(template=template)
        assert "Duplicate values for extension name are not allowed." in str(excinfo.value)

        # When the request list includes an unsupported extension name
        template["extensions"] = ["SUPPORTED_NAME"]
        with pytest.raises(DecodeValidationError) as excinfo:
            decode_function(template=template, supported_extensions=["UNSUPPORTED_NAME"])
        assert (
            f"1 validation errors for {template_type}\nextensions:\n\tUnsupported extension names: SUPPORTED_NAME"
            in str(excinfo.value)
        )

        # If an unimplemented name is provided to supported_extensions, it still can't be requested by the template
        template["extensions"] = ["UNSUPPORTED_NAME"]
        with pytest.raises(DecodeValidationError) as excinfo:
            decode_function(template=template, supported_extensions=["UNSUPPORTED_NAME"])
        assert (
            f"1 validation errors for {template_type}\nextensions:\n\tUnsupported extension names: UNSUPPORTED_NAME"
            in str(excinfo.value)
        )

    # For this test, there are two different extension names supported
    with patch.object(openjd.model.v2023_09._model, "ExtensionName", MockExtensionNameWithTwoNames):
        # When the requested extension name is in the supported list
        template["extensions"] = ["ANOTHER_SUPPORTED_NAME"]
        model = decode_function(template=template, supported_extensions=["ANOTHER_SUPPORTED_NAME"])
        assert model.extensions == ["ANOTHER_SUPPORTED_NAME"]
