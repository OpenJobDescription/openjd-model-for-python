# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any

import pytest
from pydantic import ValidationError

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
        "data",
        (
            pytest.param({}, id="empty object"),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [STEP_TEMPLATE],
                    "unknown": "key",
                },
                id="unknown key",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "steps": [STEP_TEMPLATE],
                },
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
                id="description not string",
            ),
            #
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                },
                id="missing steps",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [],
                },
                id="empty steps",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [{"name": "S", "script": STEP_SCRIPT} for i in range(0, 2)],
                },
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
                id="too many job parameters",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [STEP_TEMPLATE],
                    "parameterDefinitions": [{"name": "P", "type": "INT"} for i in range(0, 2)],
                },
                id="duplicate parameter names",
            ),
            #
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [STEP_TEMPLATE],
                    "jobEnvironments": [],
                },
                id="empty environments",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [STEP_TEMPLATE],
                    "jobEnvironments": [{"name": "E", "script": ENV_SCRIPT} for i in range(0, 2)],
                },
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
                id="step env name duplicates job env name",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # Failure case testing for Open Job Description JobTemplate.
        # - Constraint tests
        # - extra field test

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=JobTemplate, obj=data)

        # THEN
        assert len(excinfo.value.errors()) > 0
