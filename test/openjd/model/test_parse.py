# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import json
from typing import Any, Type

import pytest
import yaml

from openjd.model import (
    DecodeValidationError,
    DocumentType,
    decode_template,
    document_string_to_object,
)
from openjd.model._types import OpenJDModel
from openjd.model.v2023_09 import JobTemplate as JobTemplate_2023_09


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


class TestDecodeTemplate:
    @pytest.mark.parametrize(
        "template",
        [
            pytest.param({"notspecversion": "badvalue"}, id="missing specificationVersion field"),
            pytest.param({"specificationVersion": "badvalue"}, id="unknown version"),
        ],
    )
    def test_fail_cases(self, template: dict[str, Any]) -> None:
        # THEN
        with pytest.raises(DecodeValidationError):
            decode_template(template=template)

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
        result = decode_template(template=template)

        # THEN
        assert isinstance(result, expected_class)
