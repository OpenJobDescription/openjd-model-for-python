# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any

import pytest
from pydantic.v1 import ValidationError

from openjd.model._parse import _parse_model
from openjd.model.v2023_09 import StepTemplate

# Some minimal data to reference in tests.
ENV_SCRIPT = {"actions": {"onEnter": {"command": "foo"}}}
ENVIRONMENT = {"name": "Foo", "script": ENV_SCRIPT}
PARAMETER_SPACE = {"parameters": [{"name": "foo", "type": "INT", "range": [1]}]}
STEP_SCRIPT = {"actions": {"onRun": {"command": "foo"}}}


class TestStepTemplate:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": "Foo", "script": STEP_SCRIPT}, id="minimum required"),
            pytest.param(
                {"name": "Foo", "script": STEP_SCRIPT, "description": "some text"},
                id="with description",
            ),
            pytest.param(
                {"name": "Foo", "script": STEP_SCRIPT, "stepEnvironments": [ENVIRONMENT]},
                id="with defined environment",
            ),
            pytest.param({"name": "Foo", "script": STEP_SCRIPT}, id="with parameter space"),
            pytest.param(
                {"name": "Foo", "script": STEP_SCRIPT, "dependencies": [{"dependsOn": "Bar"}]},
                id="single dependency",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "script": STEP_SCRIPT,
                    "dependencies": [{"dependsOn": "Bar"}, {"dependsOn": "Fuz"}],
                },
                id="multiple dependency",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "script": STEP_SCRIPT,
                    "hostRequirements": {
                        "amounts": [{"name": "amount.custom", "min": 1}],
                        "attributes": [{"name": "attr.custom", "anyOf": ["foo"]}],
                    },
                },
                id="with requirements",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "script": STEP_SCRIPT,
                    "stepEnvironments": [
                        {"name": f"E{i}", "script": ENV_SCRIPT} for i in range(0, 2)
                    ],
                },
                id="different environment names",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        # Parsing tests of valid Open Job Description StepTemplate
        # It is sufficient to check that parsing the input does not
        # raise an exception. We trust the Pydantic package's testing
        # so, if the input parses then our StepTemplate model is correctly
        # constructed for valid input.

        # WHEN
        _parse_model(model=StepTemplate, obj=data)

        # THEN
        # no exception was raised.

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({}, id="empty object"),
            pytest.param(
                {"name": "Foo", "script": STEP_SCRIPT, "unknown": "key"}, id="unknown key"
            ),
            pytest.param({"script": STEP_SCRIPT}, id="missing name"),
            pytest.param({"name": "Foo"}, id="missing script"),
            pytest.param({"name": 12, "script": STEP_SCRIPT}, id="name not string"),
            pytest.param({"name": "Foo", "script": {}}, id="script empty"),
            pytest.param({"name": "Foo", "script": 12}, id="script not object"),
            pytest.param(
                {"name": "Foo", "script": STEP_SCRIPT, "description": 12},
                id="description not string",
            ),
            pytest.param(
                {"name": "Foo", "script": STEP_SCRIPT, "stepEnvironments": []},
                id="too few environments",
            ),
            pytest.param(
                {"name": "Foo", "script": STEP_SCRIPT, "parameterSpace": {}},
                id="parameter space empty",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "script": STEP_SCRIPT,
                    "dependencies": [{"dependsOn": "Foo"}],
                },
                id="self dependency",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "script": STEP_SCRIPT,
                    "dependencies": [{"dependsOn": "Bar"}, {"dependsOn": "Bar"}],
                },
                id="duplicate dependency",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "script": STEP_SCRIPT,
                    "hostRequirements": [
                        {"name": f"amount.custom{i}", "value": 1} for i in range(0, 51)
                    ],
                },
                id="too many capabilities",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "script": STEP_SCRIPT,
                    "stepEnvironments": [{"name": "E", "script": ENV_SCRIPT} for i in range(0, 2)],
                },
                id="duplicate env names",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # Failure case testing for Open Job Description StepTemplate.
        # - Constraint tests
        # - extra field test

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=StepTemplate, obj=data)

        # THEN
        assert len(excinfo.value.errors()) > 0
