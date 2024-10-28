# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any

import pytest
from pydantic.v1 import ValidationError

from openjd.model._parse import _parse_model
from openjd.model.v2023_09 import Environment

# A minimal environment script to reference in tests
ENV_SCRIPT = {"actions": {"onEnter": {"command": "foo"}}}
ENV_VARIABLE = {"FOO": "BAR", "BAZ": "QUX"}


class TestEnvironment:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": "Foo", "script": ENV_SCRIPT}, id="all required"),
            pytest.param(
                {"name": "Foo", "description": "text", "script": ENV_SCRIPT}, id="with description"
            ),
            pytest.param({"name": "Foo", "variables": ENV_VARIABLE}),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        # Parsing tests of valid Open Job Description Environment
        # It is sufficient to check that parsing the input does not
        # raise an exception. We trust the Pydantic package's testing
        # so, if the input parses then our Environment model is correctly
        # constructed for valid input.

        # WHEN
        _parse_model(model=Environment, obj=data)

        # THEN
        # no exception was raised.

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": "Foo", "script": ENV_SCRIPT, "unknown": "key"}, id="unknown key"),
            pytest.param({"script": ENV_SCRIPT}, id="missing name"),
            pytest.param({"name": 12, "script": ENV_SCRIPT}, id="name not string"),
            pytest.param(
                {"name": "Foo", "description": 12, "script": ENV_SCRIPT},
                id="description not string",
            ),
            pytest.param(
                {"name": "Foo", "variables": {"2FOO": "BAR"}}, id="variable name starts with digit"
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # Failure case testing for Open Job Description Environment.
        # - Constraint tests
        # - extra field test

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=Environment, obj=data)

        # THEN
        assert len(excinfo.value.errors()) > 0

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": "Foo"}, id="missing script and variables"),
            pytest.param(
                {"name": "Foo", "script": ENV_SCRIPT, "variables": {}}, id="empty variables"
            ),
        ),
    )
    def test_validation_fails(self, data: dict[str, Any]) -> None:
        # Failure case testing for Open Job Description Environment.
        # - Neither variables or a script
        # - Empty variables

        # WHEN
        with pytest.raises(ValueError):
            _parse_model(
                model=Environment,
                obj=data,
            )
