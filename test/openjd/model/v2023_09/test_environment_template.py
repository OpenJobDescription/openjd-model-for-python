# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any

import pytest
from pydantic.v1 import ValidationError

from openjd.model._parse import _parse_model
from openjd.model.v2023_09 import EnvironmentTemplate

# Some minimal data to reference in tests.
ENV_SCRIPT = {"actions": {"onEnter": {"command": "foo"}}}
ENVIRONMENT = {"name": "Foo", "script": ENV_SCRIPT}


class TestEnvironmentTemplate:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param(
                {"specificationVersion": "environment-2023-09", "environment": ENVIRONMENT},
                id="minimum required",
            ),
            pytest.param(
                {
                    "specificationVersion": "environment-2023-09",
                    "parameterDefinitions": [{"name": "P", "type": "INT"}],
                    "environment": ENVIRONMENT,
                },
                id="with least parameters",
            ),
            pytest.param(
                {
                    "specificationVersion": "environment-2023-09",
                    "parameterDefinitions": [
                        {"name": f"P{i}", "type": "INT"} for i in range(0, 50)
                    ],
                    "environment": ENVIRONMENT,
                },
                id="with most parameters",
            ),
            pytest.param(
                {
                    "specificationVersion": "environment-2023-09",
                    "parameterDefinitions": [{"name": "P", "type": "INT"}],
                    "environment": {
                        "name": "AnEnv",
                        "script": {
                            "embeddedFiles": [
                                {"name": "Enter", "type": "TEXT", "data": "testing {{Param.P}}"}
                            ],
                            "actions": {
                                "onEnter": {"command": "{{Param.P}}", "args": ["{{Param.P}}"]},
                                "onExit": {"command": "{{Param.P}}", "args": ["{{Param.P}}"]},
                            },
                        },
                        "variables": {"Foo": "{{Param.P}}"},
                    },
                },
                id="with parameter references",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        # Parsing tests of valid Open Job Description Environment Template
        # It is sufficient to check that parsing the input does not
        # raise an exception. We trust the Pydantic package's testing
        # so, if the input parses then our EnvironmentTemplate model is correctly
        # constructed for valid input.

        # WHEN
        _parse_model(model=EnvironmentTemplate, obj=data)

        # THEN
        # no exception was raised.

    @pytest.mark.parametrize(
        "data,expected_num_errors",
        (
            pytest.param({}, 2, id="empty object"),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "environment": ENVIRONMENT,
                },
                1,
                id="incorrect spec ver",
            ),
            pytest.param(
                {
                    "specificationVersion": "environment-2023-09",
                    "environment": ENVIRONMENT,
                    "unknown": "key",
                },
                1,
                id="unknown key",
            ),
            pytest.param(
                {
                    "environment": ENVIRONMENT,
                },
                1,
                id="missing spec ver",
            ),
            #
            pytest.param(
                {
                    "specificationVersion": "environment-2023-09",
                    "parameterDefinitions": [],
                    "environment": ENVIRONMENT,
                },
                1,
                id="empty parameters",
            ),
            pytest.param(
                {
                    "specificationVersion": "environment-2023-09",
                    "parameterDefinitions": [
                        {"name": f"P{i}", "type": "INT"} for i in range(0, 51)
                    ],
                    "environment": ENVIRONMENT,
                },
                1,
                id="too many job parameters",
            ),
            #
            pytest.param(
                {
                    "specificationVersion": "environment-2023-09",
                    "parameterDefinitions": [{"name": "P", "type": "INT"} for i in range(0, 2)],
                    "environment": ENVIRONMENT,
                },
                1,
                id="duplicate parameter names",
            ),
            pytest.param(
                {
                    "specificationVersion": "environment-2023-09",
                    "parameterDefinitions": [
                        {
                            "name": "foo",
                        },
                    ],
                    "environment": ENVIRONMENT,
                },
                # If the discriminator ("type" field) is missing then we should only see a single
                # error if the typed union discriminator is set up correctly. If it's not
                # set up correctly, then we'll get one error for every type in the union.
                1,
                id="discriminator missing",
            ),
            pytest.param(
                {
                    "specificationVersion": "environment-2023-09",
                    "parameterDefinitions": [
                        {"name": "foo", "type": "INT", "default": "nine"},
                    ],
                    "environment": ENVIRONMENT,
                },
                # If have a single error in the parameter definition and the Union discriminator
                # is set up correctly, then we should only see a single error for the field in
                # the specific Unioned type. If it's not set up correctly, then we'll
                # see at least an error from each type in the Union.
                1,
                id="discriminator works",
            ),
            #
            pytest.param(
                {
                    "specificationVersion": "environment-2023-09",
                    "parameterDefinitions": [{"name": "P", "type": "INT"}],
                    "environment": {
                        "name": "AnEnv",
                        "script": {
                            "embeddedFiles": [
                                {
                                    "name": "Enter",
                                    "type": "TEXT",
                                    "data": "testing {{Param.Unknown}}",
                                }
                            ],
                            "actions": {
                                "onEnter": {
                                    "command": "{{Param.Unknown}}",
                                    "args": ["{{Param.Unknown}}"],
                                },
                                "onExit": {
                                    "command": "{{Param.Unknown}}",
                                    "args": ["{{Param.Unknown}}"],
                                },
                            },
                        },
                        "variables": {"Foo": "{{Param.Unknown}}"},
                    },
                },
                6,
                id="unknown parameter reference",
            ),
            # Test that we still properly collect parameter definitions for format string
            # validation when we have a validation error in a parameter definition.
            pytest.param(
                {
                    "specificationVersion": "environment-2023-09",
                    "parameterDefinitions": [
                        {"name": "Foo", "type": "INT", "default": "Blah"},
                        {"name": "Fuzz", "type": "INT"},
                    ],
                    "environment": {
                        "name": "DemoEnvironment",
                        "script": {
                            "actions": {
                                "onEnter": {
                                    "command": "echo",
                                    "args": [
                                        "{{Param.Foo}}",
                                        "{{Param.Fuzz}}",
                                        "{{Task.Param.Foo}}",
                                        "{{Task.Param.Fuzz}}",
                                    ],
                                }
                            }
                        },
                    },
                },
                3,  # "Blah" is not a valid integer + Validation of Job Foo & Task Foo
                id="all parameter symbols are defined when validation errors",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any], expected_num_errors: int) -> None:
        # Failure case testing for Open Job Description EnvironmentTemplate.
        # - Constraint tests
        # - extra field test

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=EnvironmentTemplate, obj=data)

        # THEN
        assert len(excinfo.value.errors()) == expected_num_errors
