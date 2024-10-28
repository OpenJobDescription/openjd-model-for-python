# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any

import pytest
from pydantic.v1 import ValidationError

from openjd.model._parse import _parse_model
from openjd.model.v2023_09 import JobTemplate

# Some minimal data to reference in tests.
ENV_SCRIPT = {"actions": {"onEnter": {"command": "foo"}}}
ENVIRONMENT = {"name": "Foo", "script": ENV_SCRIPT}
STEP_SCRIPT = {"actions": {"onRun": {"command": "foo"}}}
STEP_TEMPLATE = {"name": "StepName", "script": STEP_SCRIPT}


class TestJobTemplate:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [STEP_TEMPLATE],
                },
                id="minimum required",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [{"name": f"S{i}", "script": STEP_SCRIPT} for i in range(0, 100)],
                },
                id="with most steps",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [STEP_TEMPLATE],
                    "description": "some text",
                },
                id="with description",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [STEP_TEMPLATE],
                    "parameterDefinitions": [{"name": "P", "type": "INT"}],
                },
                id="with least parameters",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [STEP_TEMPLATE],
                    "parameterDefinitions": [
                        {"name": f"P{i}", "type": "INT"} for i in range(0, 50)
                    ],
                },
                id="with most parameters",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [STEP_TEMPLATE],
                    "jobEnvironments": [ENVIRONMENT],
                },
                id="with least environments",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [STEP_TEMPLATE],
                    "jobEnvironments": [
                        {"name": f"E{i}", "script": ENV_SCRIPT} for i in range(0, 10)
                    ],
                },
                id="with most environments",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [STEP_TEMPLATE],
                    "jobEnvironments": [
                        {"name": f"E{i}", "script": ENV_SCRIPT} for i in range(0, 2)
                    ],
                },
                id="different environment names",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [STEP_TEMPLATE],
                    "$schema": "some text",
                },
                id="with $schema",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [
                        {
                            "name": "StepOne",
                            "script": STEP_SCRIPT,
                        },
                        {
                            "name": "StepTwo",
                            "script": STEP_SCRIPT,
                            "dependencies": [{"dependsOn": "StepOne"}],
                        },
                    ],
                },
                id="with step dependencies in declared order",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [
                        {
                            "name": "StepOne",
                            "script": STEP_SCRIPT,
                            "dependencies": [{"dependsOn": "StepTwo"}],
                        },
                        {
                            "name": "StepTwo",
                            "script": STEP_SCRIPT,
                        },
                    ],
                },
                id="with step dependencies out of declared order",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [
                        {
                            "name": "StepOne",
                            "script": STEP_SCRIPT,
                            "stepEnvironments": [
                                {"name": f"A{i}", "script": ENV_SCRIPT} for i in range(0, 2)
                            ],
                        },
                        {
                            "name": "StepTwo",
                            "script": STEP_SCRIPT,
                            "stepEnvironments": [
                                {"name": f"B{i}", "script": ENV_SCRIPT} for i in range(0, 2)
                            ],
                        },
                    ],
                    "jobEnvironments": [
                        {"name": f"J{i}", "script": ENV_SCRIPT} for i in range(0, 2)
                    ],
                },
                id="job and step env names all differ",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        # Parsing tests of valid Open Job Description JobTemplate
        # It is sufficient to check that parsing the input does not
        # raise an exception. We trust the Pydantic package's testing
        # so, if the input parses then our JobTemplate model is correctly
        # constructed for valid input.

        # WHEN
        _parse_model(model=JobTemplate, obj=data)

        # THEN
        # no exception was raised.

    @pytest.mark.parametrize(
        "data,expected_num_errors",
        (
            pytest.param({}, 3, id="empty object"),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [STEP_TEMPLATE],
                    "unknown": "key",
                },
                1,
                id="unknown key",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "steps": [STEP_TEMPLATE],
                },
                1,
                id="missing spec ver",
            ),
            #
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [STEP_TEMPLATE],
                    "description": 12,
                },
                1,
                id="description not string",
            ),
            #
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                },
                1,
                id="missing steps",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [],
                },
                1,
                id="empty steps",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [{"name": "S", "script": STEP_SCRIPT} for i in range(0, 2)],
                },
                1,
                id="duplicate step names",
            ),
            #
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [STEP_TEMPLATE],
                    "parameterDefinitions": [],
                },
                1,
                id="empty parameters",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [STEP_TEMPLATE],
                    "parameterDefinitions": [
                        {"name": f"P{i}", "type": "INT"} for i in range(0, 51)
                    ],
                },
                1,
                id="too many job parameters",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [STEP_TEMPLATE],
                    "parameterDefinitions": [{"name": "P", "type": "INT"} for i in range(0, 2)],
                },
                1,
                id="duplicate parameter names",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [STEP_TEMPLATE],
                    "parameterDefinitions": [
                        {
                            "name": "foo",
                        },
                    ],
                },
                # If the discriminator ("type" field) is missing then we should only see a single
                # error if the typed union discriminator is set up correctly. If it's not
                # set up correctly, then we'll get one error for every type in the union.
                1,
                id="discriminator missing",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [STEP_TEMPLATE],
                    "parameterDefinitions": [
                        {"name": "foo", "type": "INT", "default": "nine"},
                    ],
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
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [STEP_TEMPLATE],
                    "jobEnvironments": [],
                },
                1,
                id="empty environments",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [STEP_TEMPLATE],
                    "jobEnvironments": [{"name": "E", "script": ENV_SCRIPT} for i in range(0, 2)],
                },
                1,
                id="duplicate environment names",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [
                        {
                            "name": "StepOne",
                            "script": STEP_SCRIPT,
                            "dependencies": [{"dependsOn": "StepThree"}],
                        },
                        {
                            "name": "StepTwo",
                            "script": STEP_SCRIPT,
                            "dependencies": [{"dependsOn": "StepOne"}],
                        },
                        {
                            "name": "StepThree",
                            "script": STEP_SCRIPT,
                            "dependencies": [{"dependsOn": "StepTwo"}],
                        },
                    ],
                },
                1,
                id="with step dependency cycle",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [
                        {
                            "name": "StepOne",
                            "script": STEP_SCRIPT,
                        },
                        {
                            "name": "StepTwo",
                            "script": STEP_SCRIPT,
                            "dependencies": [{"dependsOn": "StepUnknown"}],
                        },
                    ],
                },
                1,
                id="refs unknown step",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [
                        {
                            "name": "StepOne",
                            "script": STEP_SCRIPT,
                            "stepEnvironments": [
                                {"name": f"A{i}", "script": ENV_SCRIPT} for i in range(0, 2)
                            ],
                        },
                        {
                            "name": "StepTwo",
                            "script": STEP_SCRIPT,
                            "stepEnvironments": [
                                {"name": f"B{i}", "script": ENV_SCRIPT} for i in range(0, 2)
                            ],
                        },
                    ],
                    "jobEnvironments": [
                        {"name": "A0", "script": ENV_SCRIPT},
                        {"name": "B0", "script": ENV_SCRIPT},
                    ],
                },
                2,
                id="step env name duplicates job env name",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any], expected_num_errors: int) -> None:
        # Failure case testing for Open Job Description JobTemplate.
        # - Constraint tests
        # - extra field test

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=JobTemplate, obj=data)

        # THEN
        assert len(excinfo.value.errors()) == expected_num_errors
