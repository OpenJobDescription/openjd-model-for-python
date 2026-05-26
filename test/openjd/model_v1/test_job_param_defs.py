# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the 12-variant ``JobParameterDefinition`` typed
dispatch (final part of report finding #11).

``JobTemplate.parameter_definitions`` and
``EnvironmentTemplate.parameter_definitions`` return a list of
typed pyclasses, one per
``openjd_model::template::JobParameterDefinition`` runtime variant.

Variants: STRING, INT, FLOAT, PATH (base 4) plus BOOL, RANGE_EXPR,
LIST[STRING], LIST[PATH], LIST[INT], LIST[FLOAT], LIST[BOOL],
LIST[LIST[INT]] (eight EXPR-extension types).
"""

from openjd.model._v1 import decode_environment_template, decode_job_template
from openjd.model._v1.template import (
    JobBoolParameterDefinition,
    JobFloatParameterDefinition,
    JobIntParameterDefinition,
    JobListBoolParameterDefinition,
    JobListFloatParameterDefinition,
    JobListIntParameterDefinition,
    JobListListIntParameterDefinition,
    JobListPathParameterDefinition,
    JobListStringParameterDefinition,
    JobPathParameterDefinition,
    JobRangeExprParameterDefinition,
    JobStringParameterDefinition,
)
from openjd.model._v1.types import JobParameterType


def _decode_with_params(*params, extensions=None):
    template = {
        "specificationVersion": "jobtemplate-2023-09",
        "name": "T",
        "parameterDefinitions": list(params),
        "steps": [{"name": "S", "script": {"actions": {"onRun": {"command": "echo"}}}}],
    }
    if extensions:
        template["extensions"] = extensions
    return decode_job_template(
        template=template,
        supported_extensions=extensions,
    )


class TestEmptyCase:
    def test_no_parameter_definitions_returns_none(self):
        t = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "T",
                "steps": [{"name": "S", "script": {"actions": {"onRun": {"command": "echo"}}}}],
            }
        )
        assert t.parameter_definitions is None
        assert t.parameterDefinitions is None  # camelCase alias


class TestJobStringParameterDefinition:
    def test_minimal(self):
        t = _decode_with_params({"name": "S", "type": "STRING"})
        d = t.parameter_definitions[0]
        assert isinstance(d, JobStringParameterDefinition)
        assert d.name == "S"
        assert d.type == JobParameterType.STRING
        assert d.default is None
        assert d.allowed_values is None
        assert d.min_length is None
        assert d.max_length is None
        assert d.description is None

    def test_full(self):
        t = _decode_with_params(
            {
                "name": "S",
                "type": "STRING",
                "description": "a string",
                "default": "hello",
                "allowedValues": ["hello", "world"],
                "minLength": 1,
                "maxLength": 100,
            }
        )
        d = t.parameter_definitions[0]
        assert isinstance(d, JobStringParameterDefinition)
        assert d.description == "a string"
        assert d.default == "hello"
        assert d.allowed_values == ["hello", "world"]
        assert d.allowedValues == ["hello", "world"]
        assert d.min_length == 1
        assert d.minLength == 1
        assert d.max_length == 100
        assert d.maxLength == 100


class TestJobIntParameterDefinition:
    def test_full(self):
        t = _decode_with_params(
            {
                "name": "I",
                "type": "INT",
                "default": 42,
                "minValue": 1,
                "maxValue": 100,
                "allowedValues": [1, 2, 42],
            }
        )
        d = t.parameter_definitions[0]
        assert isinstance(d, JobIntParameterDefinition)
        assert d.type == JobParameterType.INT
        assert d.default == 42
        assert d.min_value == 1
        assert d.max_value == 100
        assert d.minValue == 1
        assert d.maxValue == 100
        assert d.allowed_values == [1, 2, 42]


class TestJobFloatParameterDefinition:
    def test_full(self):
        t = _decode_with_params(
            {
                "name": "F",
                "type": "FLOAT",
                "default": 3.14,
                "minValue": 0.0,
                "maxValue": 10.0,
            }
        )
        d = t.parameter_definitions[0]
        assert isinstance(d, JobFloatParameterDefinition)
        assert d.type == JobParameterType.FLOAT
        assert d.default == 3.14
        assert d.min_value == 0.0
        assert d.max_value == 10.0


class TestJobPathParameterDefinition:
    def test_full(self):
        t = _decode_with_params(
            {
                "name": "P",
                "type": "PATH",
                "default": "/tmp/x",
                "minLength": 1,
                "maxLength": 256,
                "objectType": "FILE",
                "dataFlow": "IN",
            }
        )
        d = t.parameter_definitions[0]
        assert isinstance(d, JobPathParameterDefinition)
        assert d.type == JobParameterType.PATH
        assert d.default == "/tmp/x"
        assert d.min_length == 1
        assert d.max_length == 256
        assert d.object_type == "FILE"
        assert d.objectType == "FILE"
        assert d.data_flow == "IN"
        assert d.dataFlow == "IN"


class TestExprBoolVariants:
    def test_bool(self):
        t = _decode_with_params(
            {"name": "B", "type": "BOOL", "default": True},
            extensions=["EXPR"],
        )
        d = t.parameter_definitions[0]
        assert isinstance(d, JobBoolParameterDefinition)
        assert d.type == JobParameterType.BOOL
        assert d.default is True

    def test_bool_default_false(self):
        t = _decode_with_params(
            {"name": "B", "type": "BOOL", "default": False},
            extensions=["EXPR"],
        )
        d = t.parameter_definitions[0]
        assert d.default is False

    def test_bool_no_default(self):
        t = _decode_with_params(
            {"name": "B", "type": "BOOL"},
            extensions=["EXPR"],
        )
        d = t.parameter_definitions[0]
        assert d.default is None


class TestExprRangeExprVariant:
    def test_full(self):
        t = _decode_with_params(
            {
                "name": "R",
                "type": "RANGE_EXPR",
                "default": "1-10",
                "minLength": 1,
                "maxLength": 100,
            },
            extensions=["EXPR"],
        )
        d = t.parameter_definitions[0]
        assert isinstance(d, JobRangeExprParameterDefinition)
        assert d.type == JobParameterType.RANGE_EXPR
        assert d.default == "1-10"
        assert d.min_length == 1
        assert d.max_length == 100


class TestExprListVariants:
    def test_list_string(self):
        t = _decode_with_params(
            {
                "name": "LS",
                "type": "LIST[STRING]",
                "default": ["a", "b"],
                "minLength": 1,
                "maxLength": 5,
            },
            extensions=["EXPR"],
        )
        d = t.parameter_definitions[0]
        assert isinstance(d, JobListStringParameterDefinition)
        assert d.type == JobParameterType.LIST_STRING
        assert d.default == ["a", "b"]
        assert d.min_length == 1
        assert d.max_length == 5

    def test_list_path(self):
        t = _decode_with_params(
            {
                "name": "LP",
                "type": "LIST[PATH]",
                "default": ["/x", "/y"],
                "objectType": "DIRECTORY",
                "dataFlow": "OUT",
            },
            extensions=["EXPR"],
        )
        d = t.parameter_definitions[0]
        assert isinstance(d, JobListPathParameterDefinition)
        assert d.type == JobParameterType.LIST_PATH
        assert d.default == ["/x", "/y"]
        assert d.object_type == "DIRECTORY"
        assert d.data_flow == "OUT"

    def test_list_int(self):
        t = _decode_with_params(
            {"name": "LI", "type": "LIST[INT]", "default": [1, 2, 3]},
            extensions=["EXPR"],
        )
        d = t.parameter_definitions[0]
        assert isinstance(d, JobListIntParameterDefinition)
        assert d.type == JobParameterType.LIST_INT
        assert d.default == [1, 2, 3]

    def test_list_float(self):
        t = _decode_with_params(
            {"name": "LF", "type": "LIST[FLOAT]", "default": [1.1, 2.2]},
            extensions=["EXPR"],
        )
        d = t.parameter_definitions[0]
        assert isinstance(d, JobListFloatParameterDefinition)
        assert d.type == JobParameterType.LIST_FLOAT
        assert d.default == [1.1, 2.2]

    def test_list_bool(self):
        t = _decode_with_params(
            {"name": "LB", "type": "LIST[BOOL]", "default": [True, False]},
            extensions=["EXPR"],
        )
        d = t.parameter_definitions[0]
        assert isinstance(d, JobListBoolParameterDefinition)
        assert d.type == JobParameterType.LIST_BOOL
        assert d.default == [True, False]

    def test_list_list_int(self):
        t = _decode_with_params(
            {"name": "LLI", "type": "LIST[LIST[INT]]", "default": [[1, 2], [3, 4]]},
            extensions=["EXPR"],
        )
        d = t.parameter_definitions[0]
        assert isinstance(d, JobListListIntParameterDefinition)
        assert d.type == JobParameterType.LIST_LIST_INT
        assert d.default == [[1, 2], [3, 4]]


class TestMultipleDefinitions:
    def test_dispatch_correctly(self):
        t = _decode_with_params(
            {"name": "S", "type": "STRING"},
            {"name": "I", "type": "INT"},
            {"name": "F", "type": "FLOAT"},
            {"name": "P", "type": "PATH"},
        )
        defs = t.parameter_definitions
        assert len(defs) == 4
        assert isinstance(defs[0], JobStringParameterDefinition)
        assert isinstance(defs[1], JobIntParameterDefinition)
        assert isinstance(defs[2], JobFloatParameterDefinition)
        assert isinstance(defs[3], JobPathParameterDefinition)

    def test_ordering_preserved(self):
        t = _decode_with_params(
            {"name": "Z", "type": "STRING"},
            {"name": "A", "type": "INT"},
            {"name": "M", "type": "FLOAT"},
        )
        defs = t.parameter_definitions
        assert [d.name for d in defs] == ["Z", "A", "M"]


class TestEnvironmentTemplate:
    def test_parameter_definitions_accessor(self):
        et = decode_environment_template(
            template={
                "specificationVersion": "environment-2023-09",
                "parameterDefinitions": [
                    {"name": "S", "type": "STRING", "default": "x"},
                    {"name": "I", "type": "INT", "default": 5},
                ],
                "environment": {"name": "E", "variables": {"v": "1"}},
            }
        )
        defs = et.parameter_definitions
        assert defs is not None
        assert len(defs) == 2
        assert isinstance(defs[0], JobStringParameterDefinition)
        assert isinstance(defs[1], JobIntParameterDefinition)
        # camelCase alias
        assert et.parameterDefinitions is not None

    def test_parameter_definitions_none_when_absent(self):
        et = decode_environment_template(
            template={
                "specificationVersion": "environment-2023-09",
                "environment": {"name": "E", "variables": {"v": "1"}},
            }
        )
        assert et.parameter_definitions is None
