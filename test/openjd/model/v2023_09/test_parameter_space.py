# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any

import pytest
from pydantic.v1 import ValidationError

from openjd.model._parse import _parse_model
from openjd.model.v2023_09 import (
    FloatTaskParameterDefinition,
    IntTaskParameterDefinition,
    PathTaskParameterDefinition,
    StepParameterSpaceDefinition,
    StringTaskParameterDefinition,
)


class TestIntTaskParameterDefinition:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": "foo", "type": "INT", "range": [1]}, id="min len int list"),
            pytest.param(
                {"name": "foo", "type": "INT", "range": [1] * 1024}, id="max len int list"
            ),
            pytest.param({"name": "foo", "type": "INT", "range": ["1"]}, id="int as string"),
            pytest.param({"name": "foo", "type": "INT", "range": ["1", 2]}, id="mixed int types"),
            pytest.param(
                {"name": "foo", "type": "INT", "range": ["{{Param.Value}}"]},
                id="format string",
            ),
            pytest.param(
                {"name": "foo", "type": "INT", "range": [1, "2", "{{Param.Value}}"]},
                id="mix of item types",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        # Parsing tests of valid Open Job Description IntTaskParameterDefinition
        # It is sufficient to check that parsing the input does not
        # raise an exception. We trust the Pydantic package's testing
        # so, if the input parses then our IntTaskParameterDefinition model is correctly
        # constructed for valid input.

        # WHEN
        _parse_model(model=IntTaskParameterDefinition, obj=data)

        # THEN
        # does not raise an exception

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({}, id="empty object"),
            pytest.param({"name": "foo", "type": "FLOAT", "range": [1]}, id="wrong type"),
            pytest.param({"type": "INT", "range": [1]}, id="missing name"),
            pytest.param({"name": "foo", "range": [1]}, id="missing type"),
            pytest.param({"name": "foo", "type": "INT"}, id="missing range"),
            pytest.param({"name": "foo", "type": "INT", "range": []}, id="range too short"),
            pytest.param(
                {"name": "foo", "type": "INT", "range": [1], "unknown": "key"}, id="unknown key"
            ),
            pytest.param({"name": "foo", "type": "INT", "range": [1] * 1025}, id="range too long"),
            pytest.param({"name": "foo", "type": "INT", "range": [1.1]}, id="disallow floats"),
            pytest.param({"name": "foo", "type": "INT", "range": [True]}, id="disallow bool"),
            pytest.param(
                {"name": "foo", "type": "INT", "range": ["1.1"]}, id="disallow float strings"
            ),
            pytest.param(
                {"name": "foo", "type": "INT", "range": ["{{ Job.Parameter.Foo"]},
                id="malformed format string",
            ),
            pytest.param(
                {"name": "foo", "type": "INT", "range": ["notint"]},
                id="literal string not an int",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # Failure case testing for Open Job Description TaskParameterDecl.
        # - Constraint tests
        # - extra field test

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=IntTaskParameterDefinition, obj=data)

        # THEN
        assert len(excinfo.value.errors()) > 0


class TestFloatTaskParameterDefinition:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": "foo", "type": "FLOAT", "range": [1]}, id="min len list"),
            pytest.param({"name": "foo", "type": "FLOAT", "range": [1] * 1024}, id="max len list"),
            pytest.param({"name": "foo", "type": "FLOAT", "range": [1.1]}, id="float value"),
            pytest.param({"name": "foo", "type": "FLOAT", "range": ["1"]}, id="int as string"),
            pytest.param({"name": "foo", "type": "FLOAT", "range": ["1.1"]}, id="float as string"),
            pytest.param(
                {"name": "foo", "type": "FLOAT", "range": ["1", 2, 3.3, "3.4"]},
                id="mixed number types",
            ),
            pytest.param(
                {"name": "foo", "type": "FLOAT", "range": ["{{Param.Value}}"]},
                id="format string",
            ),
            pytest.param(
                {
                    "name": "foo",
                    "type": "FLOAT",
                    "range": [1, "2", 3.3, "3.4", "{{Param.Value}}"],
                },
                id="mix of item types",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        # Parsing tests of valid Open Job Description TestFloatTaskParameterDefinition
        # It is sufficient to check that parsing the input does not
        # raise an exception. We trust the Pydantic package's testing
        # so, if the input parses then our TestFloatTaskParameterDefinition model is correctly
        # constructed for valid input.

        # WHEN
        _parse_model(model=FloatTaskParameterDefinition, obj=data)

        # THEN
        # does not raise an exception

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({}, id="empty object"),
            pytest.param({"name": "foo", "type": "INT", "range": [1]}, id="wrong type"),
            pytest.param({"type": "FLOAT", "range": [1]}, id="missing name"),
            pytest.param({"name": "foo", "range": [1]}, id="missing type"),
            pytest.param({"name": "foo", "type": "FLOAT"}, id="missing range"),
            pytest.param({"name": "foo", "type": "FLOAT", "range": []}, id="range too short"),
            pytest.param(
                {"name": "foo", "type": "FLOAT", "range": [1], "unknown": "key"}, id="unknown key"
            ),
            pytest.param(
                {"name": "foo", "type": "FLOAT", "range": [1] * 1025}, id="range too long"
            ),
            pytest.param({"name": "foo", "type": "FLOAT", "range": [True]}, id="disallow bool"),
            pytest.param(
                {"name": "foo", "type": "FLOAT", "range": ["{{ Job.Parameter.Foo"]},
                id="malformed format string",
            ),
            pytest.param(
                {"name": "foo", "type": "FLOAT", "range": ["notnumber"]},
                id="literal string not a number",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # Failure case testing for Open Job Description TaskParameterDecl.
        # - Constraint tests
        # - extra field test

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=FloatTaskParameterDefinition, obj=data)

        # THEN
        assert len(excinfo.value.errors()) > 0


class TestStringTaskParameterDefinition:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": "foo", "type": "STRING", "range": ["a"]}, id="min len list"),
            pytest.param(
                {"name": "foo", "type": "STRING", "range": ["a"] * 1024}, id="max len list"
            ),
            pytest.param(
                {"name": "foo", "type": "STRING", "range": ["{{Param.Value}}"]},
                id="format string",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        # Parsing tests of valid Open Job Description StringTaskParameterDefinition
        # It is sufficient to check that parsing the input does not
        # raise an exception. We trust the Pydantic package's testing
        # so, if the input parses then our StringTaskParameterDefinition model is correctly
        # constructed for valid input.

        # WHEN
        _parse_model(model=StringTaskParameterDefinition, obj=data)

        # THEN
        # does not raise an exception

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({}, id="empty object"),
            pytest.param({"name": "foo", "type": "INT", "range": [1]}, id="wrong type"),
            pytest.param({"type": "STRING", "range": ["a"]}, id="missing name"),
            pytest.param({"name": "foo", "range": ["a"]}, id="missing type"),
            pytest.param({"name": "foo", "type": "STRING"}, id="missing range"),
            pytest.param({"name": "foo", "type": "STRING", "range": []}, id="range too short"),
            pytest.param(
                {"name": "foo", "type": "STRING", "range": ["a"], "unknown": "key"},
                id="unknown key",
            ),
            pytest.param(
                {"name": "foo", "type": "STRING", "range": ["a"] * 1025}, id="list too long"
            ),
            pytest.param(
                {"name": "foo", "type": "STRING", "range": ["{{ Job.Parameter.Foo"]},
                id="malformed format string",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # Failure case testing for Open Job Description TaskParameterDecl.
        # - Constraint tests
        # - extra field test

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=StringTaskParameterDefinition, obj=data)

        # THEN
        assert len(excinfo.value.errors()) > 0


class TestPathTaskParameterDefinition:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": "foo", "type": "PATH", "range": ["a"]}, id="min len list"),
            pytest.param({"name": "foo", "type": "PATH", "range": ["a"] * 1024}, id="max len list"),
            pytest.param(
                {"name": "foo", "type": "PATH", "range": ["{{Job.Parameter.Value}}"]},
                id="format string",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        # Parsing tests of valid Open Job Description PathTaskParameterDefinition
        # It is sufficient to check that parsing the input does not
        # raise an exception. We trust the Pydantic package's testing
        # so, if the input parses then our PathTaskParameterDefinition model is correctly
        # constructed for valid input.

        # WHEN
        _parse_model(model=PathTaskParameterDefinition, obj=data)

        # THEN
        # does not raise an exception

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({}, id="empty object"),
            pytest.param({"name": "foo", "type": "INT", "range": [1]}, id="wrong type"),
            pytest.param({"type": "PATH", "range": ["a"]}, id="missing name"),
            pytest.param({"name": "foo", "range": ["a"]}, id="missing type"),
            pytest.param({"name": "foo", "type": "PATH"}, id="missing range"),
            pytest.param({"name": "foo", "type": "PATH", "range": []}, id="range too short"),
            pytest.param(
                {"name": "foo", "type": "PATH", "range": ["a"], "unknown": "key"},
                id="unknown key",
            ),
            pytest.param(
                {"name": "foo", "type": "PATH", "range": ["a"] * 1025}, id="list too long"
            ),
            pytest.param(
                {"name": "foo", "type": "PATH", "range": ["{{ Job.Parameter.Foo"]},
                id="malformed format string",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # Failure case testing for Open Job Description TaskParameterDecl.
        # - Constraint tests
        # - extra field test

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=PathTaskParameterDefinition, obj=data)

        # THEN
        assert len(excinfo.value.errors()) > 0


class TestRangeExpressionTaskParameterDefinition:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": "foo", "type": "INT", "range": "1"}, id="one item"),
            pytest.param({"name": "foo", "type": "INT", "range": "1-10"}, id="one range of items"),
            pytest.param(
                {"name": "foo", "type": "INT", "range": "10--5:-1"},
                id="one negative range of items",
            ),
            pytest.param(
                {"name": "foo", "type": "INT", "range": "1-10:2"},
                id="one range of items with steps",
            ),
            pytest.param(
                {"name": "foo", "type": "INT", "range": "-5--14:-2"},
                id="negative range with negative steps",
            ),
            pytest.param({"name": "foo", "type": "INT", "range": "-10-0,1-10"}, id="two ranges"),
            pytest.param(
                {"name": "foo", "type": "INT", "range": "10-1:-1,11-20:2"},
                id="two ranges with opposite signs",
            ),
            pytest.param(
                {"name": "foo", "type": "INT", "range": "1-10:2"},
                id="one range of items with steps",
            ),
            pytest.param(
                {"name": "foo", "type": "INT", "range": "{{Param.Value}}"},
                id="format string",
            ),
            pytest.param(
                {
                    "name": "foo",
                    "type": "INT",
                    "range": "{{Job.Parameter.Start}}-{{Job.Parameter.End}}:{{Job.Parameter.Step}}",
                },
                id="format string with multiple",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, str]) -> None:
        # Parsing tests of valid Open Job Description RangeExpression
        # It is sufficient to check that parsing the input does not
        # raise an exception. We trust the Pydantic package's testing
        # so, if the input parses then our IntTaskParameterDefinition model is correctly
        # constructed for valid input.

        # WHEN
        _parse_model(model=IntTaskParameterDefinition, obj=data)

        # THEN
        # does not raise an exception

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": "foo", "type": "STRING", "range": ["1"]}, id="wrong type"),
            pytest.param({"type": "INT", "range": "1"}, id="missing name"),
            pytest.param({"name": "foo", "range": "1"}, id="missing type"),
            pytest.param({"name": "foo", "type": "INT"}, id="missing range"),
            pytest.param({"name": "foo", "type": "INT", "range": ""}, id="range too short"),
            pytest.param(
                {"name": "foo", "type": "INT", "range": "1", "unknown": "key"},
                id="unknown key",
            ),
            pytest.param(
                {"name": "foo", "type": "INT", "range": "{{ Job.Parameter.Foo"},
                id="malformed format string",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # Failure case testing for Open Job Description TaskParameterDecl.
        # - Constraint tests
        # - extra field test

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=IntTaskParameterDefinition, obj=data)

        # THEN
        assert len(excinfo.value.errors()) > 0


class TestStepParameterSpaceDefinition:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param(
                {"taskParameterDefinitions": [{"name": "foo", "type": "INT", "range": [1]}]},
                id="int parameter",
            ),
            pytest.param(
                {"taskParameterDefinitions": [{"name": "foo", "type": "FLOAT", "range": [1]}]},
                id="float parameter",
            ),
            pytest.param(
                {"taskParameterDefinitions": [{"name": "foo", "type": "STRING", "range": ["1"]}]},
                id="string parameter",
            ),
            pytest.param(
                {"taskParameterDefinitions": [{"name": "foo", "type": "PATH", "range": ["/tmp"]}]},
                id="path parameter",
            ),
            pytest.param(
                {
                    "taskParameterDefinitions": [
                        {"name": f"foo{i}", "type": "INT", "range": [1]} for i in range(0, 16)
                    ]
                },
                id="most number of parameters",
            ),
            pytest.param(
                {
                    "taskParameterDefinitions": [
                        {"name": "foo", "type": "INT", "range": [1]},
                        {"name": "bar", "type": "INT", "range": [1]},
                    ],
                    "combination": "foo * bar",
                },
                id="with combination expr",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        # Parsing tests of valid Open Job Description StepParameterSpaceDefinition
        # It is sufficient to check that parsing the input does not
        # raise an exception. We trust the Pydantic package's testing
        # so, if the input parses then our StepParameterSpaceDefinition model is correctly
        # constructed for valid input.

        # WHEN
        _parse_model(model=StepParameterSpaceDefinition, obj=data)

        # THEN
        # no exception is raised

    @pytest.mark.parametrize(
        "data,expected_num_errors",
        (
            pytest.param({}, 1, id="empty object"),
            pytest.param({"taskParameterDefinitions": []}, 1, id="empty parameter list"),
            pytest.param(
                {
                    "taskParameterDefinitions": [
                        {"name": f"foo{i}", "type": "INT", "range": [1]} for i in range(0, 17)
                    ]
                },
                1,
                id="too many parameters",
            ),
            pytest.param(
                {
                    "taskParameterDefinitions": [
                        {"name": "foo", "type": "INT", "range": [1]},
                        {"name": "foo", "type": "INT", "range": [1]},
                    ],
                },
                1,
                id="duplicate parameter name",
            ),
            pytest.param(
                {
                    "taskParameterDefinitions": [
                        {"name": "foo", "range": [1]},
                    ]
                },
                # If the discriminator ("type" field) is missing then we should only see a single
                # error if the typed union discriminator is set up correctly. If it's not
                # set up correctly, then we'll get one error for every type in the union.
                1,
                id="discriminator missing",
            ),
            pytest.param(
                {
                    "taskParameterDefinitions": [
                        {"name": "foo", "type": "INT"},
                    ]
                },
                # If we're missing a required field ("range") and the Union discriminator
                # is set up correctly, then we should only see a single error for the field being
                # missing in the specific Unioned type. If it's not set up correctly, then we'll
                # see at least an error from each type in the Union.
                1,
                id="discriminator works",
            ),
            pytest.param(
                {
                    "taskParameterDefinitions": [
                        {"name": "foo", "type": "INT", "range": [1]},
                        {"name": "bar", "type": "INT", "range": [1]},
                    ],
                    "combination": "foo  bar",
                },
                1,
                id="malformed combination expr",
            ),
            pytest.param(
                {
                    "taskParameterDefinitions": [
                        {"name": "foo", "type": "INT", "range": [1]},
                        {"name": "bar", "type": "INT", "range": [1]},
                    ],
                    "combination": "foo",
                },
                1,
                id="combination expr doesn't reference all parameters #1",
            ),
            pytest.param(
                {
                    "taskParameterDefinitions": [
                        {"name": "foo", "type": "INT", "range": [1]},
                        {"name": "bar", "type": "INT", "range": [1]},
                    ],
                    "combination": "foo * bar * baz",
                },
                1,
                id="combination expr refs undefined parameter",
            ),
            pytest.param(
                {
                    "taskParameterDefinitions": [
                        {"name": "foo", "type": "INT", "range": [1]},
                        {"name": "bar", "type": "INT", "range": [1]},
                    ],
                    "combination": "foo * bar * foo",
                },
                1,
                id="combination expr double refs a parameter",
            ),
            pytest.param(
                {
                    "taskParameterDefinitions": [
                        {"name": "foo", "type": "INT", "range": [1]},
                        {"name": "bar", "type": "INT", "range": [1]},
                    ],
                    "combination": "foo * foo",
                },
                2,
                id="combination expr double refs & missing ref",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any], expected_num_errors: int) -> None:
        # Failure case testing for Open Job Description StepParameterSpaceDefinition.
        # - Constraint tests
        # - extra field test

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=StepParameterSpaceDefinition, obj=data)

        # THEN
        assert len(excinfo.value.errors()) == expected_num_errors, str(excinfo.value)
