# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any
import string

import pytest
from pydantic.v1 import ValidationError

from openjd.model._parse import _parse_model
from openjd.model.v2023_09 import (
    AmountRequirementTemplate,
    AttributeRequirementTemplate,
    HostRequirementsTemplate,
)


class TestAttributeRequirementTemplate:
    @pytest.mark.parametrize(
        "data",
        (
            # All the built-in attribute capabilities
            pytest.param(
                {"name": "attr.worker.os.family", "anyOf": ["linux"]},
                id="os family anyOf single",
            ),
            pytest.param(
                {"name": "attr.worker.os.family", "anyOf": ["linux", "windows"]},
                id="os family anyOf multiple",
            ),
            pytest.param(
                {"name": "attr.worker.os.family", "allOf": ["linux"]},
                id="os family allOf single",
            ),
            pytest.param(
                {"name": "attr.worker.cpu.arch", "anyOf": ["x86_64"]},
                id="cpu arch anyOf single",
            ),
            pytest.param(
                {"name": "attr.worker.cpu.arch", "anyOf": ["x86_64", "arm64"]},
                id="cpu arch anyOf multiple",
            ),
            pytest.param(
                {"name": "attr.worker.cpu.arch", "allOf": ["x86_64"]},
                id="cpu arch allOf single",
            ),
            pytest.param(
                {"name": "attr.worker.cpu.arch", "allOf": ["{{ Param.Foo }}"]},
                id="allOf accepts format string",
            ),
            pytest.param(
                {"name": "attr.worker.cpu.arch", "anyOf": ["{{ Param.Foo }}"]},
                id="anyOf accepts format string",
            ),
            # User-defined attributes
            pytest.param(
                {"name": "attr.mycapability", "anyOf": ["somevalue"]},
                id="user defined - anyOf single",
            ),
            pytest.param(
                {
                    "name": "attr.mycapability",
                    "anyOf": [f"value{i}" for i in range(0, 50)],
                },
                id="user defined - anyOf max elements",
            ),
            pytest.param(
                {"name": "attr.mycapability", "allOf": ["somevalue"]},
                id="user defined - allOf single",
            ),
            pytest.param(
                {
                    "name": "attr.mycapability",
                    "allOf": [f"value{i}" for i in range(0, 50)],
                },
                id="user defined - allOf max elements",
            ),
            pytest.param(
                {"name": "attr.mycapability", "allOf": ["foo", "bar"], "anyOf": ["buz", "wuz"]},
                id="allows both anyOf and allOf",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        # Success case testing for Open Job Description AttributeRequirementTemplate.

        # WHEN
        _parse_model(model=AttributeRequirementTemplate, obj=data)

        # THEN
        # no exception was raised.

    @pytest.mark.parametrize(
        "data,error_count",
        (
            pytest.param(
                {"allOf": ["a", "b"]},
                1,
                id="allOf missing name",
            ),
            pytest.param(
                {"anyOf": ["a", "b"]},
                1,
                id="anyOf missing name",
            ),
            # All the built-in attribute capabilities
            pytest.param(
                {"name": "attr.worker.os.family"},
                1,
                id="os family missing anyOf/allOf",
            ),
            pytest.param(
                {"name": "attr.worker.os.family", "anyOf": ["personalos"]},
                1,
                id="os family anyOf unknown value",
            ),
            pytest.param(
                {"name": "attr.worker.os.family", "anyOf": []},
                1,
                id="os family anyOf empty",
            ),
            pytest.param(
                {"name": "attr.worker.os.family", "allOf": ["linux", "windows"]},
                1,
                id="os family allOf multiple",
            ),
            pytest.param(
                {"name": "attr.worker.cpu.arch", "allOf": ["x86_128"]},
                1,
                id="cpu arch allOf unknown value",
            ),
            pytest.param(
                {"name": "attr.worker.cpu.arch", "allOf": []},
                1,
                id="cpu arch allOf empty",
            ),
            pytest.param(
                {"name": "attr.worker.cpu.arch", "allOf": ["x86_64", "arm64"]},
                1,
                id="cpu arch allOf multiple",
            ),
            # User-defined attribute capabilities
            pytest.param(
                {"name": "attr.mycapability"},
                1,
                id="user attribute capability - missing anyOf/allOf",
            ),
            pytest.param(
                {"name": "attr.mycapability", "anyOf": []},
                1,
                id="user attribute capability - anyOf empty",
            ),
            pytest.param(
                {
                    "name": "attr.mycapability",
                    "anyOf": [f"value{i}" for i in range(0, 51)],
                },
                1,
                id="user attribute capability - anyOf too many elements",
            ),
            pytest.param(
                {"name": "attr.mycapability", "allOf": []},
                1,
                id="user attribute capability - allOf empty",
            ),
            pytest.param(
                {
                    "name": "attr.mycapability",
                    "allOf": [f"value{i}" for i in range(0, 51)],
                },
                1,
                id="user attribute capability - allOf too many elements",
            ),
            pytest.param(
                {"name": "attr.mycapability", "allOf": "stringvalue"},
                1,
                id="user attribute capability - incorrect allOf type",
            ),
            pytest.param(
                {"name": "attr.mycapability", "allOf": {"key": "stringvalue"}},
                1,
                id="user attribute capability - incorrect allOf type",
            ),
            # Vendor-defined attribute capabilities
            pytest.param(
                {"name": "vendor:attr.somecapability"},
                1,
                id="vendor attribute capability - missing anyOf/allOf",
            ),
            pytest.param(
                {"name": "vendor:attr.somecapability", "anyOf": []},
                1,
                id="vendor attribute capability - anyOf empty",
            ),
            pytest.param(
                {"name": "vendor:attr.somecapability", "allOf": []},
                1,
                id="vendor attribute capability - allOf empty",
            ),
            pytest.param(
                {"name": "vendor:attr.somecapability", "allOf": "stringvalue"},
                1,
                id="vendor attribute capability - incorrect allOf type",
            ),
            pytest.param(
                {"name": "vendor:attr.somecapability", "allOf": {"key": "stringvalue"}},
                1,
                id="vendor attribute capability - incorrect allOf type",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any], error_count: int) -> None:
        # Failure case testing for Open Job Description AttributeRequirementTemplate.

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=AttributeRequirementTemplate, obj=data)

        # THEN
        assert len(excinfo.value.errors()) == error_count, str(excinfo.value)

    @pytest.mark.parametrize(
        "value",
        [
            pytest.param("a", id="min length"),
            pytest.param("a" * 100, id="maximum allowed length"),
            pytest.param(
                "A" + string.ascii_letters + string.digits + "_-", id="allowable characters"
            ),
            pytest.param("_a", id="starts with underscore"),
            pytest.param("Aa", id="starts with capital letter"),
        ],
    )
    @pytest.mark.parametrize("field", ["anyOf", "allOf"])
    def test_non_standard_attribute_capability_value_string(self, field: str, value: str) -> None:
        # Test the constraints on an attribute capability value within the
        # anyOf and allOf clauses don't raise validation errros when the value
        # is compliant.

        # GIVEN
        data = {"name": "attr.custom", field: [value]}

        # WHEN
        _parse_model(model=AttributeRequirementTemplate, obj=data)

        # THEN
        # doesn't raise an exception when we parse the model

    @pytest.mark.parametrize(
        "value,error_count",
        [
            pytest.param("", 1, id="too short"),
            pytest.param("a" * 101, 1, id="too long"),
            pytest.param("0a", 1, id="cannot start with digit"),
        ]
        + [
            pytest.param(f"A{letter}", 1, id=f"'{letter}' not allowed")
            for letter in sorted(
                list(
                    set(string.printable)
                    - set(string.ascii_letters)
                    - set(string.digits)
                    - set("-_")
                )
            )
        ],
    )
    @pytest.mark.parametrize("field", ["anyOf", "allOf"])
    def test_non_standard_attribute_capability_noncompliant_value_string(
        self, field: str, value: str, error_count: int
    ) -> None:
        # Test the constraints on an amount capability value within the
        # anyOf and allOf clauses raise validation errors when they're violated.

        # GIVEN
        data = {"name": "attr.custom", field: [value]}

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=AmountRequirementTemplate, obj=data)

        # THEN
        assert len(excinfo.value.errors()) == error_count, str(excinfo.value)


class TestAmountRequirementTemplate:
    @pytest.mark.parametrize(
        "data",
        (
            # All the built-in amount capabilities
            pytest.param(
                {"name": "amount.worker.gpu", "min": 2},
                id="amount.worker.gpu min int",
            ),
            pytest.param(
                {"name": "amount.worker.gpu.memory", "min": 2.25},
                id="amount.worker.gpu.memory min float",
            ),
            pytest.param(
                {"name": "amount.worker.disk.scratch", "min": 10, "max": 50},
                id="amount.worker.disk.scratch min max int",
            ),
            # User-defined amount capabilities
            pytest.param(
                {"name": "amount.mycapability", "min": 0.5, "max": 2.9},
                id="user amount capability - min max float",
            ),
            pytest.param(
                {"name": "amount.mycapability", "min": 0.6, "max": 0.61},
                id="user amount capability - min max float close values",
            ),
            pytest.param(
                {"name": "amount.mycapability", "max": 1000},
                id="user amount capability - max int",
            ),
            pytest.param(
                {"name": "amount.mycapability", "max": 10.79},
                id="user amount capability - max float",
            ),
            # Vendor-defined amount capabilities
            pytest.param(
                {"name": "vendor:amount.capability", "min": 0.5, "max": 2.9},
                id="vendor amount capability - min max float",
            ),
            pytest.param(
                {"name": "vendor:amount.capability", "min": 6, "max": 6},
                id="vendor amount capability - min max equal",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        # Success case testing for Open Job Description AmountRequirementTemplate.

        # WHEN
        _parse_model(model=AmountRequirementTemplate, obj=data)

        # THEN
        # no exception was raised.

    @pytest.mark.parametrize(
        "data,error_count",
        (
            pytest.param(
                {"min": 0},
                1,
                id="min missing name",
            ),
            pytest.param(
                {"max": 2},
                1,
                id="max missing name",
            ),
            # All the built-in amount capabilities
            pytest.param(
                {"name": "amount.worker.gpu.memory", "min": -2},
                1,
                id="amount.worker.gpu.memory min negative int",
            ),
            pytest.param(
                {"name": "amount.worker.disk.scratch", "min": -1.5},
                1,
                id="amount.worker.disk.scratch min negative float",
            ),
            # User-defined amount capabilities
            pytest.param(
                {"name": "amount.mycap", "min": 3, "max": 2},
                1,
                id="user amount capability min bigger than max",
            ),
            pytest.param(
                {"name": "amount.{{Param.Cap}}", "min": 3, "max": 2},
                1,
                id="user amount capability min bigger than max",
            ),
            pytest.param(
                {"name": "amount.{{Param.Cap}}", "min": 0.3, "max": 0.29},
                1,
                id="user amount capability min bigger than max float close values",
            ),
            pytest.param(
                {"name": "amount.mycap", "max": 0},
                1,
                id="user amount capability max equals zero",
            ),
            pytest.param(
                {"name": "amount.{{Param.Cap}}", "max": 0},
                1,
                id="user amount capability max equals zero",
            ),
            pytest.param(
                {"name": "amount.mycap", "max": {}},
                1,
                id="user amount capability max is wrong type",
            ),
            pytest.param(
                {"name": "amount.mycap", "min": [1, 2]},
                1,
                id="user amount capability min is wrong type",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any], error_count: int) -> None:
        # Failure case testing for Open Job Description AmountRequirementTemplate.

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=AmountRequirementTemplate, obj=data)

        # THEN
        assert len(excinfo.value.errors()) == error_count, str(excinfo.value)


class TestHostRequirementsTemplate:
    @pytest.mark.parametrize(
        "data",
        [
            pytest.param({"amounts": [{"name": "amount.mycap", "min": 1}]}, id="single amount"),
            pytest.param(
                {"attributes": [{"name": "attr.mycap", "anyOf": ["foo"]}]}, id="single amount"
            ),
            pytest.param(
                {
                    "amounts": [{"name": "amount.mycap", "min": 1}],
                    "attributes": [{"name": "attr.mycap", "anyOf": ["foo"]}],
                },
                id="single amount & attriubute",
            ),
            pytest.param(
                {"amounts": [{"name": f"amount.mycap{i}", "min": 1} for i in range(0, 50)]},
                id="maximum as only amounts",
            ),
            pytest.param(
                {
                    "attributes": [
                        {"name": f"attr.mycap{i}", "anyOf": ["foo"]} for i in range(0, 50)
                    ]
                },
                id="maximum as only attributes",
            ),
            pytest.param(
                {
                    "amounts": [{"name": f"amount.mycap{i}", "min": 1} for i in range(0, 25)],
                    "attributes": [
                        {"name": f"attr.mycap{i}", "anyOf": ["foo"]} for i in range(0, 25)
                    ],
                },
                id="maximum as combination",
            ),
        ],
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        # Success case testing for Open Job Description HostRequirementsTemplate.

        # WHEN
        _parse_model(model=HostRequirementsTemplate, obj=data)

        # THEN
        # no exception was raised.

    @pytest.mark.parametrize(
        "data,error_count",
        [
            pytest.param({}, 1, id="missing amounts & attributes"),
            pytest.param({"unknown": "value"}, 1, id="unknown field"),
            pytest.param({"amounts": []}, 1, id="too few amounts"),
            pytest.param({"attributes": []}, 1, id="too few attributes"),
            pytest.param(
                {"amounts": [{"name": f"amount.mycap{i}", "min": 1} for i in range(0, 51)]},
                1,
                id="too many as only amounts",
            ),
            pytest.param(
                {
                    "attributes": [
                        {"name": f"attr.mycap{i}|", "anyOf": ["foo"]} for i in range(0, 51)
                    ]
                },
                1,
                id="too many as only attributes",
            ),
            pytest.param(
                {
                    "amounts": [{"name": f"amount.mycap{i}", "min": 1} for i in range(0, 26)],
                    "attributes": [
                        {"name": f"attr.mycap{i}", "anyOf": ["foo"]} for i in range(0, 25)
                    ],
                },
                1,
                id="too many as combination",
            ),
        ],
    )
    def test_parse_fails(self, data: dict[str, Any], error_count: int) -> None:
        # Failure case testing for Open Job Description AmountRequirementTemplate.

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=AmountRequirementTemplate, obj=data)

        # THEN
        assert len(excinfo.value.errors()) == error_count, str(excinfo.value)
