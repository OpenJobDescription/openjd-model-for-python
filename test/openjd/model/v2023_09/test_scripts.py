# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any

import pytest
from pydantic.v1 import ValidationError

from openjd.model._parse import _parse_model
from openjd.model.v2023_09 import EnvironmentScript, StepScript


class TestStepScript:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"actions": {"onRun": {"command": "foo"}}}, id="all required"),
            pytest.param(
                {
                    "actions": {"onRun": {"command": "foo"}},
                    "embeddedFiles": [{"name": "Foo", "type": "TEXT", "data": "data"}],
                },
                id="min len embedded files",
            ),
            pytest.param(
                {
                    "actions": {"onRun": {"command": "foo"}},
                    "embeddedFiles": [
                        {
                            "name": f"Name{i}",  # each must have a unique name
                            "type": "TEXT",
                            "data": "data",
                        }
                        for i in range(0, 5)
                    ],
                },
                id="max len embedded files",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        # Parsing tests of valid Open Job Description StepScript
        # It is sufficient to check that parsing the input does not
        # raise an exception. We trust the Pydantic package's testing
        # so, if the input parses then our StepScript model is correctly
        # constructed for valid input.

        # WHEN
        _parse_model(model=StepScript, obj=data)

        # THEN
        # no exception was raised.

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({}, id="empty object"),
            pytest.param(
                {"actions": {"onRun": {"command": "foo"}}, "unknown": "name"}, id="unknown key"
            ),
            pytest.param(
                {
                    "actions": {"onRun": {"command": "foo"}},
                    "embeddedFiles": [],
                },
                id="too few embedded files",
            ),
            pytest.param(
                {
                    "actions": {"onRun": {"command": "foo"}},
                    "embeddedFiles": [
                        {
                            "name": "Name",  # each must have a unique name
                            "type": "TEXT",
                            "data": "data",
                        }
                        for i in range(0, 2)
                    ],
                },
                id="embedded file duplicate names",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # Failure case testing for Open Job Description StepScript.
        # - Constraint tests
        # - extra field test

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=StepScript, obj=data)

        # THEN
        assert len(excinfo.value.errors()) > 0


class TestEnvironmentScript:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"actions": {"onEnter": {"command": "foo"}}}, id="minimal"),
            pytest.param(
                {
                    "actions": {"onEnter": {"command": "foo"}},
                    "embeddedFiles": [{"name": "Foo", "type": "TEXT", "data": "data"}],
                },
                id="min len embedded files",
            ),
            pytest.param(
                {
                    "actions": {"onEnter": {"command": "foo"}},
                    "embeddedFiles": [
                        {
                            "name": f"Name{i}",  # each must have a unique name
                            "type": "TEXT",
                            "data": "data",
                        }
                        for i in range(0, 5)
                    ],
                },
                id="max len embedded files",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        # Parsing tests of valid Open Job Description EnvironmentScript
        # It is sufficient to check that parsing the input does not
        # raise an exception. We trust the Pydantic package's testing
        # so, if the input parses then our EnvironmentScript model is correctly
        # constructed for valid input.

        # WHEN
        _parse_model(model=EnvironmentScript, obj=data)

        # THEN
        # no exception was raised.

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({}, id="empty object"),
            pytest.param(
                {"actions": {"onEnter": {"command": "foo"}}, "unknown": "name"}, id="unknown key"
            ),
            pytest.param(
                {
                    "actions": {"onEnter": {"command": "foo"}},
                    "embeddedFiles": [],
                },
                id="too few embedded files",
            ),
            pytest.param(
                {
                    "actions": {"onEnter": {"command": "foo"}},
                    "embeddedFiles": [
                        {
                            "name": "Name",  # each must have a unique name
                            "type": "TEXT",
                            "data": "data",
                        }
                        for i in range(0, 2)
                    ],
                },
                id="embedded file duplicate names",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # Failure case testing for Open Job Description EnvironmentScript.
        # - Constraint tests
        # - extra field test

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=EnvironmentScript, obj=data)

        # THEN
        assert len(excinfo.value.errors()) > 0
