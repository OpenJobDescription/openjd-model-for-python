# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from decimal import Decimal
from typing import Any

import pytest
from pydantic.v1 import ValidationError

from openjd.model._parse import _parse_model
from openjd.model.v2023_09 import (
    JobFloatParameterDefinition,
    JobIntParameterDefinition,
    JobPathParameterDefinition,
    JobStringParameterDefinition,
)


class TestJobStringParameterDefinition:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": "Foo", "type": "STRING"}, id="minimal required"),
            pytest.param(
                {"name": "Foo", "type": "STRING", "description": "some test"}, id="description"
            ),
            pytest.param(
                {"name": "Foo", "type": "STRING", "default": "some value"}, id="has default"
            ),
            pytest.param(
                {"name": "Foo", "type": "STRING", "minLength": 1}, id="smallest min length"
            ),
            pytest.param(
                {"name": "Foo", "type": "STRING", "maxLength": 1}, id="smallest max length"
            ),
            pytest.param(
                {"name": "Foo", "type": "STRING", "allowedValues": ["a"]}, id="has allowedValues"
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "STRING", "minLength": 1, "maxLength": 1}, id="min = max"
            ),
            pytest.param(
                {"name": "Foo", "type": "STRING", "minLength": 1, "maxLength": 2}, id="min < max"
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "STRING", "allowedValues": ["aa"], "minLength": 2},
                id="allowed is min length",
            ),
            pytest.param(
                {"name": "Foo", "type": "STRING", "allowedValues": ["aa"], "maxLength": 2},
                id="allowed is max length",
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "STRING", "default": "aa", "minLength": 2},
                id="default is minLength",
            ),
            pytest.param(
                {"name": "Foo", "type": "STRING", "default": "aa", "maxLength": 2},
                id="default is maxLength",
            ),
            pytest.param(
                {"name": "Foo", "type": "STRING", "default": "aa", "allowedValues": ["aa", "bb"]},
                id="default is allowed",
            ),
            pytest.param(
                {"name": "Foo", "type": "STRING", "description": "aa\nbb\ncc\r\ndd\t\ttabs\n"},
                id="description with newlines and tabs",
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "STRING", "userInterface": {"control": "LINE_EDIT"}},
                id="user interface LINE_EDIT",
            ),
            pytest.param(
                {"name": "Foo", "type": "STRING", "userInterface": {"control": "MULTILINE_EDIT"}},
                id="user interface MULTILINE_EDIT",
            ),
            pytest.param(
                {"name": "Foo", "type": "STRING", "userInterface": {"control": "HIDDEN"}},
                id="user interface HIDDEN",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "STRING",
                    "userInterface": {"control": "DROPDOWN_LIST"},
                    "allowedValues": ["aa"],
                },
                id="user interface DROPDOWN_LIST",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "STRING",
                    "userInterface": {"control": "CHECK_BOX"},
                    "allowedValues": ["True", "False"],
                },
                id="user interface CHECKBOX with True/False",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "STRING",
                    "userInterface": {"control": "CHECK_BOX"},
                    "allowedValues": ["False", "True"],
                },
                id="user interface CHECKBOX with False/True",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "STRING",
                    "userInterface": {"control": "CHECK_BOX"},
                    "allowedValues": ["OFF", "ON"],
                },
                id="user interface CHECKBOX with OFF/ON",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "STRING",
                    "userInterface": {"control": "CHECK_BOX"},
                    "allowedValues": ["yes", "no"],
                },
                id="user interface CHECKBOX with yes/no",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "STRING",
                    "userInterface": {"control": "CHECK_BOX"},
                    "allowedValues": ["0", "1"],
                },
                id="user interface CHECKBOX with 0/1",
            ),
            #
            pytest.param(
                {
                    "name": "Foo",
                    "type": "STRING",
                    "userInterface": {
                        "control": "HIDDEN",
                        "label": "Foo Label",
                        "groupLabel": "Bar",
                    },
                    "default": "aa",
                    "allowedValues": ["aa", "bb"],
                    "minLength": 1,
                    "maxLength": 3,
                },
                id="all fields",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        # Parsing tests of valid Open Job Description JobStringParameterDefinition
        # It is sufficient to check that parsing the input does not
        # raise an exception. We trust the Pydantic package's testing
        # so, if the input parses then our JobStringParameterDefinition model is correctly
        # constructed for valid input.

        # WHEN
        _parse_model(model=JobStringParameterDefinition, obj=data)

        # THEN
        # no exception was raised.

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({}, id="empty object"),
            pytest.param({"name": "Foo", "type": "FLOAT"}, id="wrong type"),
            pytest.param({"name": "Foo"}, id="missing type"),
            pytest.param({"type": "STRING"}, id="missing name"),
            pytest.param({"name": 12, "type": "STRING"}, id="name not a string"),
            #
            pytest.param(
                {"name": "Foo", "type": "STRING", "description": 12}, id="description not string"
            ),
            pytest.param({"name": "Foo", "type": "STRING", "default": 12}, id="default not string"),
            pytest.param(
                {"name": "Foo", "type": "STRING", "minLength": 1.2}, id="min length float"
            ),
            pytest.param(
                {"name": "Foo", "type": "STRING", "maxLength": 1.2}, id="max length float"
            ),
            pytest.param(
                {"name": "Foo", "type": "STRING", "minLength": "1"}, id="min length string"
            ),
            pytest.param(
                {"name": "Foo", "type": "STRING", "maxLength": "1"}, id="max length string"
            ),
            pytest.param(
                {"name": "Foo", "type": "STRING", "allowedValues": []}, id="allowedValues too small"
            ),
            pytest.param(
                {"name": "Foo", "type": "STRING", "allowedValues": [12]},
                id="allowedValues item not string",
            ),
            #
            pytest.param({"name": "Foo", "type": "STRING", "minLength": 0}, id="0 < min"),
            pytest.param({"name": "Foo", "type": "STRING", "maxLength": 0}, id="0 < max"),
            pytest.param(
                {"name": "Foo", "type": "STRING", "minLength": 2, "maxLength": 1}, id="min > max"
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "STRING", "allowedValues": ["aa"], "minLength": 3},
                id="allowed less than min length",
            ),
            pytest.param(
                {"name": "Foo", "type": "STRING", "allowedValues": ["aa"], "maxLength": 1},
                id="allowed exceeds max length",
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "STRING", "default": "aa", "minLength": 3},
                id="default less than minLength",
            ),
            pytest.param(
                {"name": "Foo", "type": "STRING", "default": "aa", "maxLength": 1},
                id="default exceeds maxLength",
            ),
            pytest.param(
                {"name": "Foo", "type": "STRING", "default": "cc", "allowedValues": ["aa", "bb"]},
                id="default not allowed",
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "STRING", "userInterface": {"control": "UNSUPPORTED"}},
                id="unsupported user interface control",
            ),
            pytest.param(
                {"name": "Foo", "type": "STRING", "userInterface": {"label": "\n"}},
                id="wrong character in user interface label",
            ),
            pytest.param(
                {"name": "Foo", "type": "STRING", "userInterface": {"label": ""}},
                id="user interface label too short",
            ),
            pytest.param(
                {"name": "Foo", "type": "STRING", "userInterface": {"label": "a" * 65}},
                id="user interface label too long",
            ),
            pytest.param(
                {"name": "Foo", "type": "STRING", "userInterface": {"groupLabel": ""}},
                id="user interface groupLabel too short",
            ),
            pytest.param(
                {"name": "Foo", "type": "STRING", "userInterface": {"groupLabel": "a" * 65}},
                id="user interface groupLabel too long",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "STRING",
                    "userInterface": {"control": "LINE_EDIT"},
                    "allowedValues": ["aa"],
                },
                id="user interface LINE_EDIT can't have allowedValues",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "STRING",
                    "userInterface": {"control": "MULTILINE_EDIT"},
                    "allowedValues": ["aa"],
                },
                id="user interface MULTILINE_EDIT can't have allowedValues",
            ),
            pytest.param(
                {"name": "Foo", "type": "STRING", "userInterface": {"control": "DROPDOWN_LIST"}},
                id="user interface DROPDOWN_LIST requires allowedValues",
            ),
            #
            pytest.param(
                {
                    "name": "Foo",
                    "type": "STRING",
                    "userInterface": {"control": "CHECK_BOX"},
                    "allowedValues": ["Ture", "False"],
                },
                id="user interface CHECKBOX with unsupported Ture/False",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "STRING",
                    "userInterface": {"control": "CHECK_BOX"},
                    "allowedValues": ["Ture"],
                },
                id="user interface CHECKBOX with too few allowedValues",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "STRING",
                    "userInterface": {"control": "CHECK_BOX"},
                    "allowedValues": ["True", "False", "On", "Off"],
                },
                id="user interface CHECKBOX with too many allowedValues",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # Failure case testing for Open Job Description JobStringParameterDefinition.
        # - Constraint tests
        # - extra field test

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=JobStringParameterDefinition, obj=data)

        # THEN
        assert len(excinfo.value.errors()) > 0

    @pytest.mark.parametrize(
        "value,parameter",
        [
            pytest.param(
                "value", JobStringParameterDefinition(name="Foo", type="STRING"), id="passes type"
            ),
            pytest.param(
                "value",
                JobStringParameterDefinition(name="Foo", type="STRING", minLength=1),
                id="min length",
            ),
            pytest.param(
                "value",
                JobStringParameterDefinition(name="Foo", type="STRING", minLength=5),
                id="min length",
            ),
            pytest.param(
                "value",
                JobStringParameterDefinition(name="Foo", type="STRING", maxLength=5),
                id="max length",
            ),
            pytest.param(
                "value",
                JobStringParameterDefinition(name="Foo", type="STRING", maxLength=15),
                id="max length",
            ),
            pytest.param(
                "value1",
                JobStringParameterDefinition(
                    name="Foo", type="STRING", allowedValues=["value1", "value2"]
                ),
                id="allowed value 1",
            ),
            pytest.param(
                "value2",
                JobStringParameterDefinition(
                    name="Foo", type="STRING", allowedValues=["value1", "value2"]
                ),
                id="allowed value 2",
            ),
        ],
    )
    def test_check_constraints_noraise(
        self, value: Any, parameter: JobStringParameterDefinition
    ) -> None:
        # WHEN
        #  will raise if the value doesn't pass the checks
        parameter._check_constraints(value)

        # THEN
        assert True

    @pytest.mark.parametrize(
        "value,parameter",
        [
            pytest.param(
                None, JobStringParameterDefinition(name="Foo", type="STRING"), id="none type"
            ),
            pytest.param(
                12, JobStringParameterDefinition(name="Foo", type="STRING"), id="int type"
            ),
            pytest.param(
                True, JobStringParameterDefinition(name="Foo", type="STRING"), id="bool type"
            ),
            pytest.param(
                1.2, JobStringParameterDefinition(name="Foo", type="STRING"), id="float type"
            ),
            pytest.param(
                Decimal(1),
                JobStringParameterDefinition(name="Foo", type="STRING"),
                id="decimal type",
            ),
            pytest.param(
                list(), JobStringParameterDefinition(name="Foo", type="STRING"), id="list type"
            ),
            pytest.param(
                dict(), JobStringParameterDefinition(name="Foo", type="STRING"), id="dict type"
            ),
            pytest.param(
                "value",
                JobStringParameterDefinition(name="Foo", type="STRING", minLength=6),
                id="min length",
            ),
            pytest.param(
                "value",
                JobStringParameterDefinition(name="Foo", type="STRING", maxLength=4),
                id="max length",
            ),
            pytest.param(
                "value",
                JobStringParameterDefinition(
                    name="Foo", type="STRING", allowedValues=["value1", "value2"]
                ),
                id="allowed value",
            ),
        ],
    )
    def test_check_constraints_raises(
        self, value: Any, parameter: JobStringParameterDefinition
    ) -> None:
        # WHEN
        with pytest.raises(ValueError):
            parameter._check_constraints(value)


class TestJobPathParameterDefinition:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": "Foo", "type": "PATH"}, id="minimal required"),
            pytest.param(
                {"name": "Foo", "type": "PATH", "description": "some test"}, id="description"
            ),
            pytest.param(
                {"name": "Foo", "type": "PATH", "default": "some value"}, id="has default"
            ),
            pytest.param({"name": "Foo", "type": "PATH", "minLength": 1}, id="smallest min length"),
            pytest.param({"name": "Foo", "type": "PATH", "maxLength": 1}, id="smallest max length"),
            pytest.param(
                {"name": "Foo", "type": "PATH", "allowedValues": ["a"]}, id="has allowedValues"
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "PATH", "minLength": 1, "maxLength": 1}, id="min = max"
            ),
            pytest.param(
                {"name": "Foo", "type": "PATH", "minLength": 1, "maxLength": 2}, id="min < max"
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "PATH", "allowedValues": ["aa"], "minLength": 2},
                id="allowed is min length",
            ),
            pytest.param(
                {"name": "Foo", "type": "PATH", "allowedValues": ["aa"], "maxLength": 2},
                id="allowed is max length",
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "PATH", "default": "aa", "minLength": 2},
                id="default is minLength",
            ),
            pytest.param(
                {"name": "Foo", "type": "PATH", "default": "aa", "maxLength": 2},
                id="default is maxLength",
            ),
            pytest.param(
                {"name": "Foo", "type": "PATH", "default": "aa", "allowedValues": ["aa", "bb"]},
                id="default is allowed",
            ),
            pytest.param(
                {"name": "Foo", "type": "PATH", "description": "aa\nbb\ncc\r\ndd\t\ttabs\n"},
                id="description with newlines and tabs",
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "PATH", "userInterface": {"control": "CHOOSE_INPUT_FILE"}},
                id="user interface CHOOSE_INPUT_FILE",
            ),
            pytest.param(
                {"name": "Foo", "type": "PATH", "userInterface": {"control": "CHOOSE_OUTPUT_FILE"}},
                id="user interface CHOOSE_OUTPUT_FILE",
            ),
            pytest.param(
                {"name": "Foo", "type": "PATH", "userInterface": {"control": "CHOOSE_DIRECTORY"}},
                id="user interface CHOOSE_DIRECTORY",
            ),
            pytest.param(
                {"name": "Foo", "type": "PATH", "userInterface": {"control": "HIDDEN"}},
                id="user interface HIDDEN",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "PATH",
                    "userInterface": {"control": "DROPDOWN_LIST"},
                    "allowedValues": ["/aa/bb"],
                },
                id="user interface DROPDOWN_LIST",
            ),
            #
            pytest.param(
                {
                    "name": "Foo",
                    "type": "PATH",
                    "userInterface": {
                        "control": "CHOOSE_INPUT_FILE",
                        "fileFilters": [{"label": "All Files", "patterns": ["*.*"]}],
                        "fileFilterDefault": {
                            "label": "Some Files",
                            "patterns": ["*.jpg", "*.png"],
                        },
                    },
                },
                id="user interface CHOOSE_INPUT_FILE with file filters",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "PATH",
                    "userInterface": {
                        "control": "CHOOSE_OUTPUT_FILE",
                        "fileFilters": [{"label": "All Files", "patterns": ["*", "*.*"]}],
                        "fileFilterDefault": {
                            "label": "Some Files",
                            "patterns": ["*.jpg", "*.png", "*.c++", "*.psppalette"],
                        },
                    },
                },
                id="user interface CHOOSE_OUTPUT_FILE with file filters",
            ),
            #
            pytest.param(
                {
                    "name": "Foo",
                    "type": "PATH",
                    "objectType": "FILE",
                    "userInterface": {"control": "CHOOSE_INPUT_FILE"},
                },
                id="path object type FILE with CHOOSE_INPUT_FILE",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "PATH",
                    "objectType": "FILE",
                    "userInterface": {"control": "CHOOSE_OUTPUT_FILE"},
                },
                id="path object type FILE with CHOOSE_OUTPUT_FILE",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "PATH",
                    "objectType": "DIRECTORY",
                    "userInterface": {"control": "CHOOSE_DIRECTORY"},
                },
                id="path object type DIRECTORY with CHOOSE_DRECTORY",
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "PATH", "dataFlow": "NONE"},
                id="path data flow NONE",
            ),
            pytest.param(
                {"name": "Foo", "type": "PATH", "dataFlow": "IN"},
                id="path data flow IN",
            ),
            pytest.param(
                {"name": "Foo", "type": "PATH", "dataFlow": "OUT"},
                id="path data flow OUT",
            ),
            pytest.param(
                {"name": "Foo", "type": "PATH", "dataFlow": "INOUT"},
                id="path data flow INOUT",
            ),
            #
            pytest.param(
                {
                    "name": "Foo",
                    "type": "PATH",
                    "objectType": "DIRECTORY",
                    "dataFlow": "INOUT",
                    "userInterface": {
                        "control": "DROPDOWN_LIST",
                        "label": "Foo Label",
                        "groupLabel": "Foo Group",
                    },
                    "default": "aa",
                    "allowedValues": ["aa", "bb"],
                    "minLength": 1,
                    "maxLength": 3,
                },
                id="all fields",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        # Parsing tests of valid Open Job Description JobPathParameterDefinition
        # It is sufficient to check that parsing the input does not
        # raise an exception. We trust the Pydantic package's testing
        # so, if the input parses then our JobPathParameterDefinition model is correctly
        # constructed for valid input.

        # WHEN
        _parse_model(model=JobPathParameterDefinition, obj=data)

        # THEN
        # no exception was raised.

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({}, id="empty object"),
            pytest.param({"name": "Foo", "type": "FLOAT"}, id="wrong type"),
            pytest.param({"name": "Foo"}, id="missing type"),
            pytest.param({"type": "PATH"}, id="missing name"),
            pytest.param({"name": 12, "type": "PATH"}, id="name not a string"),
            #
            pytest.param(
                {"name": "Foo", "type": "PATH", "description": 12}, id="description not string"
            ),
            pytest.param({"name": "Foo", "type": "PATH", "default": 12}, id="default not string"),
            pytest.param({"name": "Foo", "type": "PATH", "minLength": 1.2}, id="min length float"),
            pytest.param({"name": "Foo", "type": "PATH", "maxLength": 1.2}, id="max length float"),
            pytest.param({"name": "Foo", "type": "PATH", "minLength": "1"}, id="min length string"),
            pytest.param({"name": "Foo", "type": "PATH", "maxLength": "1"}, id="max length string"),
            pytest.param(
                {"name": "Foo", "type": "PATH", "allowedValues": []}, id="allowedValues too small"
            ),
            pytest.param(
                {"name": "Foo", "type": "PATH", "allowedValues": [12]},
                id="allowedValues item not string",
            ),
            #
            pytest.param({"name": "Foo", "type": "PATH", "minLength": 0}, id="0 < min"),
            pytest.param({"name": "Foo", "type": "PATH", "maxLength": 0}, id="0 < max"),
            pytest.param(
                {"name": "Foo", "type": "PATH", "minLength": 2, "maxLength": 1}, id="min > max"
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "PATH", "allowedValues": ["aa"], "minLength": 3},
                id="allowed less than min length",
            ),
            pytest.param(
                {"name": "Foo", "type": "PATH", "allowedValues": ["aa"], "maxLength": 1},
                id="allowed exceeds max length",
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "PATH", "default": "aa", "minLength": 3},
                id="default less than minLength",
            ),
            pytest.param(
                {"name": "Foo", "type": "PATH", "default": "aa", "maxLength": 1},
                id="default exceeds maxLength",
            ),
            pytest.param(
                {"name": "Foo", "type": "PATH", "default": "cc", "allowedValues": ["aa", "bb"]},
                id="default not allowed",
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "PATH", "userInterface": {"control": "UNSUPPORTED"}},
                id="unsupported user interface control",
            ),
            pytest.param(
                {"name": "Foo", "type": "PATH", "userInterface": {"label": "\n"}},
                id="wrong character in user interface label",
            ),
            pytest.param(
                {"name": "Foo", "type": "PATH", "userInterface": {"label": ""}},
                id="user interface label too short",
            ),
            pytest.param(
                {"name": "Foo", "type": "PATH", "userInterface": {"label": "a" * 65}},
                id="user interface label too long",
            ),
            pytest.param(
                {"name": "Foo", "type": "PATH", "userInterface": {"groupLabel": ""}},
                id="user interface groupLabel too short",
            ),
            pytest.param(
                {"name": "Foo", "type": "PATH", "userInterface": {"groupLabel": "a" * 65}},
                id="user interface groupLabel too long",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "PATH",
                    "userInterface": {"control": "CHOOSE_INPUT_FILE"},
                    "allowedValues": ["aa"],
                },
                id="user interface CHOOSE_INPUT_FILE can't have allowedValues",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "PATH",
                    "userInterface": {"control": "CHOOSE_OUTPUT_FILE"},
                    "allowedValues": ["aa"],
                },
                id="user interface CHOOSE_OUTPUT_FILE can't have allowedValues",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "PATH",
                    "userInterface": {"control": "CHOOSE_DIRECTORY"},
                    "allowedValues": ["aa"],
                },
                id="user interface CHOOSE_DIRECTORY can't have allowedValues",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "PATH",
                    "userInterface": {
                        "control": "CHOOSE_DIRECTORY",
                        "fileFilters": [{"label": "All Files", "patterns": ["*.*"]}],
                    },
                },
                id="user interface CHOOSE_DIRECTORY can't have fileFilters",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "PATH",
                    "userInterface": {
                        "control": "CHOOSE_DIRECTORY",
                        "fileFilterDefault": {
                            "label": "Some Files",
                            "patterns": ["*.jpg", "*.png"],
                        },
                    },
                },
                id="user interface CHOOSE_DIRECTORY can't have fileFilterDefault",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "PATH",
                    "userInterface": {
                        "control": "DROPDOWN_LIST",
                        "fileFilters": [{"label": "All Files", "patterns": ["*.*"]}],
                    },
                    "allowedValues": ["aa"],
                },
                id="user interface DROPDOWN_LIST can't have fileFilters",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "PATH",
                    "userInterface": {
                        "control": "DROPDOWN_LIST",
                        "fileFilterDefault": {
                            "label": "Some Files",
                            "patterns": ["*.jpg", "*.png"],
                        },
                    },
                    "allowedValues": ["aa"],
                },
                id="user interface DROPDOWN_LIST can't have fileFilterDefault",
            ),
            pytest.param(
                {"name": "Foo", "type": "PATH", "userInterface": {"control": "DROPDOWN_LIST"}},
                id="user interface DROPDOWN_LIST requires allowedValues",
            ),
            #
            pytest.param(
                {
                    "name": "Foo",
                    "type": "PATH",
                    "userInterface": {
                        "control": "CHOOSE_INPUT_FILE",
                        "fileFilters": [{"label": "", "patterns": ["*.*"]}],
                    },
                },
                id="user interface file filter name too small",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "PATH",
                    "userInterface": {
                        "control": "CHOOSE_INPUT_FILE",
                        "fileFilters": [{"label": "a" * 65, "patterns": ["*.*"]}],
                    },
                },
                id="user interface file filter name too large",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "PATH",
                    "userInterface": {
                        "control": "CHOOSE_INPUT_FILE",
                        "fileFilters": [{"label": "All Files", "patterns": []}],
                    },
                },
                id="user interface file filter pattern list too small",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "PATH",
                    "userInterface": {
                        "control": "CHOOSE_INPUT_FILE",
                        "fileFilters": [{"label": "All Files", "patterns": ["*.*"] * 21}],
                    },
                },
                id="user interface file filter pattern list too large",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "PATH",
                    "userInterface": {
                        "control": "CHOOSE_INPUT_FILE",
                        "fileFilters": [],
                    },
                },
                id="user interface file filter list too small",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "PATH",
                    "userInterface": {
                        "control": "CHOOSE_INPUT_FILE",
                        "fileFilters": [{"label": "All Files", "patterns": ["*.*"]}] * 21,
                    },
                },
                id="user interface file filter list too large",
            ),
            #
            pytest.param(
                {
                    "name": "Foo",
                    "type": "PATH",
                    "objectType": "DIRECTORY",
                    "userInterface": {"control": "CHOOSE_INPUT_FILE"},
                },
                id="path object type DIRECTORY incompatible with CHOOSE_INPUT_FILE",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "PATH",
                    "objectType": "DIRECTORY",
                    "userInterface": {"control": "CHOOSE_OUTPUT_FILE"},
                },
                id="path object type DIRECTORY incompatible with CHOOSE_OUTPUT_FILE",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "PATH",
                    "objectType": "FILE",
                    "userInterface": {"control": "CHOOSE_DIRECTORY"},
                },
                id="path object type FILE incompatible with CHOOSE_DIRECTORY",
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "PATH", "objectType": "UNSUPPORTED"},
                id="path object type unsupported",
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "PATH", "dataFlow": "UNSUPPORTED"},
                id="path data flow unsupported",
            ),
            #
            pytest.param(
                {
                    "name": "Foo",
                    "type": "PATH",
                    "userInterface": {
                        "control": "CHOOSE_INPUT_FILE",
                        "fileFilters": [{"label": "X", "patterns": ["**"]}],
                    },
                },
                id="user interface file filter unsupported '**' pattern",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "PATH",
                    "userInterface": {
                        "control": "CHOOSE_INPUT_FILE",
                        "fileFilters": [{"label": "X", "patterns": ["*.?"]}],
                    },
                },
                id="user interface file filter unsupported '*.?' pattern",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # Failure case testing for Open Job Description JobPathParameterDefinition.
        # - Constraint tests
        # - extra field test

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=JobPathParameterDefinition, obj=data)

        # THEN
        assert len(excinfo.value.errors()) > 0

    @pytest.mark.parametrize(
        "value,parameter",
        [
            pytest.param(
                "value", JobPathParameterDefinition(name="Foo", type="PATH"), id="passes type"
            ),
            pytest.param(
                "value",
                JobPathParameterDefinition(name="Foo", type="PATH", minLength=1),
                id="min length",
            ),
            pytest.param(
                "value",
                JobPathParameterDefinition(name="Foo", type="PATH", minLength=5),
                id="min length",
            ),
            pytest.param(
                "value",
                JobPathParameterDefinition(name="Foo", type="PATH", maxLength=5),
                id="max length",
            ),
            pytest.param(
                "value",
                JobPathParameterDefinition(name="Foo", type="PATH", maxLength=15),
                id="max length",
            ),
            pytest.param(
                "value1",
                JobPathParameterDefinition(
                    name="Foo", type="PATH", allowedValues=["value1", "value2"]
                ),
                id="allowed value 1",
            ),
            pytest.param(
                "value2",
                JobPathParameterDefinition(
                    name="Foo", type="PATH", allowedValues=["value1", "value2"]
                ),
                id="allowed value 2",
            ),
        ],
    )
    def test_check_constraints_noraise(
        self, value: Any, parameter: JobPathParameterDefinition
    ) -> None:
        # WHEN
        #  will raise if the value doesn't pass the checks
        parameter._check_constraints(value)

        # THEN
        assert True

    @pytest.mark.parametrize(
        "value,parameter",
        [
            pytest.param(None, JobPathParameterDefinition(name="Foo", type="PATH"), id="none type"),
            pytest.param(12, JobPathParameterDefinition(name="Foo", type="PATH"), id="int type"),
            pytest.param(True, JobPathParameterDefinition(name="Foo", type="PATH"), id="bool type"),
            pytest.param(1.2, JobPathParameterDefinition(name="Foo", type="PATH"), id="float type"),
            pytest.param(
                Decimal(1), JobPathParameterDefinition(name="Foo", type="PATH"), id="decimal type"
            ),
            pytest.param(
                list(), JobPathParameterDefinition(name="Foo", type="PATH"), id="list type"
            ),
            pytest.param(
                dict(), JobPathParameterDefinition(name="Foo", type="PATH"), id="dict type"
            ),
            pytest.param(
                "value",
                JobPathParameterDefinition(name="Foo", type="PATH", minLength=6),
                id="min length",
            ),
            pytest.param(
                "value",
                JobPathParameterDefinition(name="Foo", type="PATH", maxLength=4),
                id="max length",
            ),
            pytest.param(
                "value",
                JobPathParameterDefinition(
                    name="Foo", type="PATH", allowedValues=["value1", "value2"]
                ),
                id="allowed value",
            ),
        ],
    )
    def test_check_constraints_raises(
        self, value: Any, parameter: JobPathParameterDefinition
    ) -> None:
        # WHEN
        with pytest.raises(ValueError):
            parameter._check_constraints(value)


class TestJobIntParameterDefinition:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": "Foo", "type": "INT"}, id="minimal required"),
            pytest.param(
                {"name": "Foo", "type": "INT", "description": "some text"}, id="description"
            ),
            pytest.param({"name": "Foo", "type": "INT", "default": 1}, id="has default as int"),
            pytest.param(
                {"name": "Foo", "type": "INT", "default": -1}, id="has default as negative int"
            ),
            pytest.param(
                {"name": "Foo", "type": "INT", "default": "1"}, id="has default as string"
            ),
            pytest.param({"name": "Foo", "type": "INT", "minValue": 1}, id="has min value as int"),
            pytest.param(
                {"name": "Foo", "type": "INT", "minValue": "1"}, id="has min value as string"
            ),
            pytest.param({"name": "Foo", "type": "INT", "maxValue": 1}, id="has max value as int"),
            pytest.param(
                {"name": "Foo", "type": "INT", "maxValue": "1"}, id="has max value as string"
            ),
            pytest.param(
                {"name": "Foo", "type": "INT", "allowedValues": [1]}, id="has allowedValues int"
            ),
            pytest.param(
                {"name": "Foo", "type": "INT", "allowedValues": ["1"]},
                id="has allowedValues string",
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "INT", "minValue": 1, "maxValue": 1}, id="min = max"
            ),
            pytest.param(
                {"name": "Foo", "type": "INT", "minValue": 1, "maxValue": 2}, id="min < max"
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "INT", "allowedValues": [2], "minValue": 2},
                id="allowed is min value",
            ),
            pytest.param(
                {"name": "Foo", "type": "INT", "allowedValues": [2], "maxValue": 2},
                id="allowed is max value",
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "INT", "default": 2, "minValue": 2},
                id="default is min value",
            ),
            pytest.param(
                {"name": "Foo", "type": "INT", "default": 2, "maxValue": 2},
                id="default is max value",
            ),
            pytest.param(
                {"name": "Foo", "type": "INT", "default": 2, "allowedValues": [1, "2"]},
                id="default is allowed",
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "INT", "userInterface": {"control": "SPIN_BOX"}},
                id="user interface SPIN_BOX",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "INT",
                    "userInterface": {"control": "SPIN_BOX", "singleStepDelta": 3},
                },
                id="user interface SPIN_BOX",
            ),
            pytest.param(
                {"name": "Foo", "type": "INT", "userInterface": {"control": "HIDDEN"}},
                id="user interface HIDDEN",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "INT",
                    "userInterface": {"control": "DROPDOWN_LIST"},
                    "allowedValues": [1],
                },
                id="user interface DROPDOWN_LIST",
            ),
            #
            pytest.param(
                {
                    "name": "Foo",
                    "type": "INT",
                    "userInterface": {
                        "control": "DROPDOWN_LIST",
                        "label": "Foo Label",
                        "groupLabel": "Group Label",
                    },
                    "default": 1,
                    "allowedValues": [1, "2"],
                    "minValue": 1,
                    "maxValue": 3,
                },
                id="all fields",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        # Parsing tests of valid Open Job Description JobIntParameterDefinition
        # It is sufficient to check that parsing the input does not
        # raise an exception. We trust the Pydantic package's testing
        # so, if the input parses then our JobIntParameterDefinition model is correctly
        # constructed for valid input.

        # WHEN
        _parse_model(model=JobIntParameterDefinition, obj=data)

        # THEN
        # no exception was raised.

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({}, id="empty object"),
            pytest.param({"name": "Foo", "type": "STRING"}, id="wrong type"),
            pytest.param({"name": "Foo"}, id="missing type"),
            pytest.param({"type": "INT"}, id="missing name"),
            pytest.param({"name": 12, "type": "INT"}, id="name not a string"),
            #
            pytest.param(
                {"name": "Foo", "type": "INT", "description": 12}, id="description not string"
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "INT", "allowedValues": []}, id="allowedValues too small"
            ),
            pytest.param(
                {"name": "Foo", "type": "INT", "allowedValues": ["aa"]},
                id="allowedValues item not number",
            ),
            pytest.param(
                {"name": "Foo", "type": "INT", "allowedValues": ["1.2"]},
                id="allowedValues item not int string",
            ),
            pytest.param(
                {"name": "Foo", "type": "INT", "allowedValues": [True]},
                id="allowedValues item a bool",
            ),
            #
            pytest.param({"name": "Foo", "type": "INT", "minValue": True}, id="min a bool"),
            pytest.param({"name": "Foo", "type": "INT", "minValue": 1.1}, id="min a float"),
            pytest.param({"name": "Foo", "type": "INT", "minValue": "1.1"}, id="min a float str"),
            pytest.param({"name": "Foo", "type": "INT", "maxValue": True}, id="max a bool"),
            pytest.param({"name": "Foo", "type": "INT", "maxValue": 1.1}, id="max a float"),
            pytest.param({"name": "Foo", "type": "INT", "maxValue": "1.1"}, id="max a float str"),
            pytest.param(
                {"name": "Foo", "type": "INT", "minValue": 2, "maxValue": 1}, id="min > max"
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "INT", "allowedValues": [2], "minValue": 3},
                id="allowed less than min value",
            ),
            pytest.param(
                {"name": "Foo", "type": "INT", "allowedValues": [2], "maxValue": 1},
                id="allowed exceeds max value",
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "INT", "default": True},
                id="default a bool",
            ),
            pytest.param(
                {"name": "Foo", "type": "INT", "default": 1.1},
                id="default a float",
            ),
            pytest.param(
                {"name": "Foo", "type": "INT", "default": "1.1"},
                id="default a float str",
            ),
            pytest.param(
                {"name": "Foo", "type": "INT", "default": 2, "minValue": 3},
                id="default less than min value",
            ),
            pytest.param(
                {"name": "Foo", "type": "INT", "default": 2, "maxLength": 1},
                id="default exceeds max value",
            ),
            pytest.param(
                {"name": "Foo", "type": "INT", "default": 0, "allowedValues": [1, 2]},
                id="default not allowed",
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "STRING", "default": "aa", "minLength": 3},
                id="default less than minLength",
            ),
            pytest.param(
                {"name": "Foo", "type": "STRING", "default": "aa", "maxLength": 1},
                id="default exceeds maxLength",
            ),
            pytest.param(
                {"name": "Foo", "type": "STRING", "default": "cc", "allowedValues": ["aa", "bb"]},
                id="default not allowed",
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "INT", "userInterface": {"control": "UNSUPPORTED"}},
                id="unsupported user interface control",
            ),
            pytest.param(
                {"name": "Foo", "type": "INT", "userInterface": {"label": "\n"}},
                id="wrong character in user interface label",
            ),
            pytest.param(
                {"name": "Foo", "type": "INT", "userInterface": {"label": ""}},
                id="user interface label too short",
            ),
            pytest.param(
                {"name": "Foo", "type": "INT", "userInterface": {"label": "a" * 65}},
                id="user interface label too long",
            ),
            pytest.param(
                {"name": "Foo", "type": "INT", "userInterface": {"groupLabel": ""}},
                id="user interface groupLabel too short",
            ),
            pytest.param(
                {"name": "Foo", "type": "INT", "userInterface": {"groupLabel": "a" * 65}},
                id="user interface groupLabel too long",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "INT",
                    "userInterface": {"control": "SPIN_BOX"},
                    "allowedValues": [1],
                },
                id="user interface SPIN_BOX can't have allowedValues",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "INT",
                    "userInterface": {"control": "HIDDEN", "singleStepDelta": 3},
                },
                id="user interface HIDDEN cannot use singleStepDelta",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "INT",
                    "userInterface": {"control": "DROPDOWN_LIST", "singleStepDelta": 3},
                    "allowedValues": [1, 2],
                },
                id="user interface DROPDOWN_LIST cannot use singleStepDelta",
            ),
            pytest.param(
                {"name": "Foo", "type": "INT", "userInterface": {"control": "DROPDOWN_LIST"}},
                id="user interface DROPDOWN_LIST requires allowedValues",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # Failure case testing for Open Job Description JobIntParameterDefinition.
        # - Constraint tests
        # - extra field test
        # - type cooersion

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=JobIntParameterDefinition, obj=data)

        # THEN
        assert len(excinfo.value.errors()) > 0

    @pytest.mark.parametrize(
        "value,parameter",
        [
            pytest.param(
                5, JobIntParameterDefinition(name="Foo", type="INT"), id="passes type int"
            ),
            pytest.param(
                "5", JobIntParameterDefinition(name="Foo", type="INT"), id="passes type str"
            ),
            pytest.param(
                5, JobIntParameterDefinition(name="Foo", type="INT", minValue=0), id="min value"
            ),
            pytest.param(
                5, JobIntParameterDefinition(name="Foo", type="INT", minValue=5), id="min value"
            ),
            pytest.param(
                5, JobIntParameterDefinition(name="Foo", type="INT", maxValue=5), id="max value"
            ),
            pytest.param(
                5, JobIntParameterDefinition(name="Foo", type="INT", maxValue=15), id="max value"
            ),
            pytest.param(
                5,
                JobIntParameterDefinition(name="Foo", type="INT", allowedValues=[5, 6]),
                id="allowed value 5",
            ),
            pytest.param(
                6,
                JobIntParameterDefinition(name="Foo", type="INT", allowedValues=[5, 6]),
                id="allowed value 6",
            ),
            pytest.param(
                "5",
                JobIntParameterDefinition(name="Foo", type="INT", allowedValues=[5, 6]),
                id="allowed value 5 str",
            ),
            pytest.param(
                "6",
                JobIntParameterDefinition(name="Foo", type="INT", allowedValues=[5, 6]),
                id="allowed value 6 str",
            ),
            pytest.param(
                5,
                JobIntParameterDefinition(name="Foo", type="INT", allowedValues=["5", "6"]),
                id="allowed values are str",
            ),
        ],
    )
    def test_check_constraints_noraise(
        self, value: Any, parameter: JobIntParameterDefinition
    ) -> None:
        # WHEN
        #  will raise if the value doesn't pass the checks
        parameter._check_constraints(value)

        # THEN
        assert True

    @pytest.mark.parametrize(
        "value,parameter",
        [
            pytest.param(None, JobIntParameterDefinition(name="Foo", type="INT"), id="none type"),
            pytest.param("foo", JobIntParameterDefinition(name="Foo", type="INT"), id="bad string"),
            pytest.param(
                "1.2", JobIntParameterDefinition(name="Foo", type="INT"), id="float string"
            ),
            pytest.param(True, JobIntParameterDefinition(name="Foo", type="INT"), id="bool type"),
            pytest.param(1.2, JobIntParameterDefinition(name="Foo", type="INT"), id="float type"),
            pytest.param(list(), JobIntParameterDefinition(name="Foo", type="INT"), id="list type"),
            pytest.param(dict(), JobIntParameterDefinition(name="Foo", type="INT"), id="dict type"),
            pytest.param(
                Decimal(1), JobIntParameterDefinition(name="Foo", type="INT"), id="decimal type"
            ),
            pytest.param(
                5, JobIntParameterDefinition(name="Foo", type="INT", minValue=6), id="min value"
            ),
            pytest.param(
                5, JobIntParameterDefinition(name="Foo", type="INT", maxValue=4), id="max value"
            ),
            pytest.param(
                4,
                JobIntParameterDefinition(name="Foo", type="INT", allowedValues=[5, 6]),
                id="allowed value",
            ),
            pytest.param(
                4,
                JobIntParameterDefinition(name="Foo", type="INT", allowedValues=["5", "6"]),
                id="allowed value",
            ),
            pytest.param(
                "4",
                JobIntParameterDefinition(name="Foo", type="INT", allowedValues=[5, 6]),
                id="allowed value",
            ),
            pytest.param(
                "4",
                JobIntParameterDefinition(name="Foo", type="INT", allowedValues=["5", "6"]),
                id="allowed value",
            ),
        ],
    )
    def test_check_constraints_raises(
        self, value: Any, parameter: JobIntParameterDefinition
    ) -> None:
        # WHEN
        with pytest.raises(ValueError):
            parameter._check_constraints(value)


class TestJobFloatParameterDefinition:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": "Foo", "type": "FLOAT"}, id="minimal required"),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "description": "some text"}, id="description"
            ),
            pytest.param({"name": "Foo", "type": "FLOAT", "default": 1}, id="has default as int"),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "default": 1.2}, id="has default as float"
            ),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "default": "1.2"}, id="has default as string"
            ),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "minValue": 1}, id="has min value as int"
            ),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "minValue": 1.2}, id="has min value as float"
            ),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "minValue": "1.2"}, id="has min value as string"
            ),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "maxValue": 1}, id="has max value as int"
            ),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "maxValue": 1.2}, id="has max value as float"
            ),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "maxValue": "1.2"}, id="has max value as string"
            ),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "allowedValues": [1]}, id="has allowedValues int"
            ),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "allowedValues": [1.2]},
                id="has allowedValues float",
            ),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "allowedValues": ["1.2"]},
                id="has allowedValues string",
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "minValue": 1, "maxValue": 1}, id="min = max"
            ),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "minValue": 1, "maxValue": 2}, id="min < max"
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "allowedValues": [2], "minValue": 2},
                id="allowed is min value",
            ),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "allowedValues": [2], "maxValue": 2},
                id="allowed is max value",
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "default": 2, "minValue": 2},
                id="default is min value",
            ),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "default": 2, "maxValue": 2},
                id="default is max value",
            ),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "default": 2, "allowedValues": [1, "2"]},
                id="default is allowed",
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "userInterface": {"control": "SPIN_BOX"}},
                id="user interface SPIN_BOX",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "FLOAT",
                    "userInterface": {"control": "SPIN_BOX", "singleStepDelta": 3.5},
                },
                id="user interface SPIN_BOX",
            ),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "userInterface": {"control": "HIDDEN"}},
                id="user interface HIDDEN",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "FLOAT",
                    "userInterface": {"control": "DROPDOWN_LIST"},
                    "allowedValues": [1],
                },
                id="user interface DROPDOWN_LIST",
            ),
            #
            pytest.param(
                {
                    "name": "Foo",
                    "type": "FLOAT",
                    "userInterface": {
                        "control": "DROPDOWN_LIST",
                        "label": "Foo Label",
                        "groupLabel": "Group Label",
                    },
                    "default": 1,
                    "allowedValues": [1, "2"],
                    "minValue": 1,
                    "maxValue": 3,
                },
                id="all fields",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        # Parsing tests of valid Open Job Description JobFloatParameterDefinition
        # It is sufficient to check that parsing the input does not
        # raise an exception. We trust the Pydantic package's testing
        # so, if the input parses then our JobFloatParameterDefinition model is correctly
        # constructed for valid input.

        # WHEN
        _parse_model(model=JobFloatParameterDefinition, obj=data)

        # THEN
        # no exception was raised.

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({}, id="empty object"),
            pytest.param({"name": "Foo", "type": "STRING"}, id="wrong type"),
            pytest.param({"name": "Foo"}, id="missing type"),
            pytest.param({"type": "FLOAT"}, id="missing name"),
            pytest.param({"name": 12, "type": "FLOAT"}, id="name not a string"),
            #
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "description": 12}, id="description not string"
            ),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "allowedValues": []}, id="allowedValues too small"
            ),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "allowedValues": ["aa"]},
                id="allowedValues item not number",
            ),
            #
            pytest.param({"name": "Foo", "type": "FLOAT", "minValue": True}, id="min a bool"),
            pytest.param({"name": "Foo", "type": "FLOAT", "maxValue": True}, id="max a bool"),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "minValue": 2, "maxValue": 1}, id="min > max"
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "allowedValues": [True]},
                id="allowed item is a bool",
            ),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "allowedValues": [2], "minValue": 3},
                id="allowed less than min value",
            ),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "allowedValues": [2], "maxValue": 1},
                id="allowed exceeds max value",
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "default": True},
                id="default is a bool",
            ),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "default": 2, "minValue": 3},
                id="default less than min value",
            ),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "default": 2, "maxLength": 1},
                id="default exceeds max value",
            ),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "default": 0, "allowedValues": [1, 2]},
                id="default not allowed",
            ),
            #
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "userInterface": {"control": "UNSUPPORTED"}},
                id="unsupported user interface control",
            ),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "userInterface": {"label": "\n"}},
                id="wrong character in user interface label",
            ),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "userInterface": {"label": ""}},
                id="user interface label too short",
            ),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "userInterface": {"label": "a" * 65}},
                id="user interface label too long",
            ),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "userInterface": {"groupLabel": ""}},
                id="user interface groupLabel too short",
            ),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "userInterface": {"groupLabel": "a" * 65}},
                id="user interface groupLabel too long",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "FLOAT",
                    "userInterface": {"control": "SPIN_BOX"},
                    "allowedValues": [1],
                },
                id="user interface SPIN_BOX can't have allowedValues",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "FLOAT",
                    "userInterface": {"control": "HIDDEN", "singleStepDelta": 3},
                },
                id="user interface HIDDEN cannot use singleStepDelta",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "FLOAT",
                    "userInterface": {"control": "DROPDOWN_LIST", "singleStepDelta": 3},
                    "allowedValues": [1, 2],
                },
                id="user interface DROPDOWN_LIST cannot use singleStepDelta",
            ),
            pytest.param(
                {"name": "Foo", "type": "FLOAT", "userInterface": {"control": "DROPDOWN_LIST"}},
                id="user interface DROPDOWN_LIST requires allowedValues",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # Failure case testing for Open Job Description JobFloatParameterDefinition.
        # - Constraint tests
        # - extra field test

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=JobFloatParameterDefinition, obj=data)

        # THEN
        assert len(excinfo.value.errors()) > 0

    @pytest.mark.parametrize(
        "value,parameter",
        [
            pytest.param(
                5, JobFloatParameterDefinition(name="Foo", type="FLOAT"), id="passes type int"
            ),
            pytest.param(
                "5", JobFloatParameterDefinition(name="Foo", type="FLOAT"), id="passes type str int"
            ),
            pytest.param(
                5.5, JobFloatParameterDefinition(name="Foo", type="FLOAT"), id="passes type float"
            ),
            pytest.param(
                "5.5",
                JobFloatParameterDefinition(name="Foo", type="FLOAT"),
                id="passes type str float",
            ),
            #
            pytest.param(
                Decimal("5.5"),
                JobFloatParameterDefinition(name="Foo", type="FLOAT"),
                id="passes type decimal",
            ),
            #
            pytest.param(
                5.5,
                JobFloatParameterDefinition(name="Foo", type="FLOAT", minValue=0),
                id="min value",
            ),
            pytest.param(
                5.5,
                JobFloatParameterDefinition(name="Foo", type="FLOAT", minValue=5.5),
                id="min value",
            ),
            pytest.param(
                5.5,
                JobFloatParameterDefinition(name="Foo", type="FLOAT", maxValue=5.5),
                id="max value",
            ),
            pytest.param(
                5.5,
                JobFloatParameterDefinition(name="Foo", type="FLOAT", maxValue=15),
                id="max value",
            ),
            #
            pytest.param(
                1.2,
                JobFloatParameterDefinition(
                    name="Foo", type="FLOAT", allowedValues=[Decimal("1.2"), 5.5]
                ),
                id="allowed value 1.2 float",
            ),
            pytest.param(
                5.5,
                JobFloatParameterDefinition(
                    name="Foo", type="FLOAT", allowedValues=[Decimal("1.2"), 5.5]
                ),
                id="allowed value 5.5 float",
            ),
            pytest.param(
                "1.2",
                JobFloatParameterDefinition(
                    name="Foo", type="FLOAT", allowedValues=[Decimal("1.2"), 5.5]
                ),
                id="allowed value 1.2 str",
            ),
            pytest.param(
                "5.5",
                JobFloatParameterDefinition(
                    name="Foo", type="FLOAT", allowedValues=[Decimal("1.2"), 5.5]
                ),
                id="allowed value 5.5 str",
            ),
            pytest.param(
                Decimal("1.2"),
                JobFloatParameterDefinition(
                    name="Foo", type="FLOAT", allowedValues=[Decimal("1.2"), 5.5]
                ),
                id="allowed value 1.2 decimal",
            ),
            pytest.param(
                Decimal("5.5"),
                JobFloatParameterDefinition(
                    name="Foo", type="FLOAT", allowedValues=[Decimal("1.2"), 5.5]
                ),
                id="allowed value 5.5 decimal",
            ),
        ],
    )
    def test_check_constraints_noraise(
        self, value: Any, parameter: JobFloatParameterDefinition
    ) -> None:
        # WHEN
        #  will raise if the value doesn't pass the checks
        parameter._check_constraints(value)

        # THEN
        assert True

    @pytest.mark.parametrize(
        "value,parameter",
        [
            pytest.param(
                None, JobFloatParameterDefinition(name="Foo", type="FLOAT"), id="none type"
            ),
            pytest.param(
                True, JobFloatParameterDefinition(name="Foo", type="FLOAT"), id="bool type"
            ),
            pytest.param(
                list(), JobFloatParameterDefinition(name="Foo", type="FLOAT"), id="list type"
            ),
            pytest.param(
                dict(), JobFloatParameterDefinition(name="Foo", type="FLOAT"), id="dict type"
            ),
            pytest.param(
                "foo", JobFloatParameterDefinition(name="Foo", type="FLOAT"), id="bad string"
            ),
            pytest.param(
                5.4,
                JobFloatParameterDefinition(name="Foo", type="FLOAT", minValue=5.5),
                id="min value",
            ),
            pytest.param(
                5.6,
                JobFloatParameterDefinition(name="Foo", type="FLOAT", maxValue=5.5),
                id="max value",
            ),
            pytest.param(
                4,
                JobFloatParameterDefinition(name="Foo", type="FLOAT", allowedValues=[5, 6]),
                id="allowed value",
            ),
            pytest.param(
                "4",
                JobFloatParameterDefinition(name="Foo", type="FLOAT", allowedValues=[5, 6]),
                id="allowed value",
            ),
            pytest.param(
                4,
                JobFloatParameterDefinition(name="Foo", type="FLOAT", allowedValues=["5", "6"]),
                id="allowed value",
            ),
        ],
    )
    def test_check_constraints_raises(
        self, value: Any, parameter: JobFloatParameterDefinition
    ) -> None:
        # WHEN
        with pytest.raises(ValueError):
            parameter._check_constraints(value)
