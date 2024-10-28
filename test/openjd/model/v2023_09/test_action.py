# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any

import pytest
from pydantic.v1 import ValidationError

from openjd.model._parse import _parse_model
from openjd.model.v2023_09 import Action, EnvironmentActions, StepActions


class TestAction:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"command": "1"}, id="command min len"),
            pytest.param({"command": "1" * (32 * 1024)}, id="command really long len"),
            pytest.param({"command": "{{ Job.Parameter.Foo }}"}, id="command format string"),
            pytest.param({"command": "foo", "args": [""]}, id="arg min item len"),
            pytest.param({"command": "foo", "args": ["1" * (32 * 1024)]}, id="arg really long len"),
            pytest.param({"command": "foo", "args": ["1"] * (32 * 64)}, id="arg many items"),
            pytest.param(
                {"command": "foo", "args": ["{{ Job.Parameter.Foo }}"]}, id="arg arg format string"
            ),
            pytest.param({"command": "foo", "timeout": 1}, id="timeout min value"),
            pytest.param({"command": "foo", "timeout": 600}, id="timeout max value"),
            pytest.param({"command": "foo", "timeout": "1"}, id="timeout intstring"),
            pytest.param(
                {"command": "foo", "cancelation": {"mode": "TERMINATE"}}, id="cancel terminate"
            ),
            pytest.param(
                {
                    "command": "foo",
                    "cancelation": {"mode": "NOTIFY_THEN_TERMINATE", "notifyPeriodInSeconds": 1},
                },
                id="cancel notify min value",
            ),
            pytest.param(
                {
                    "command": "foo",
                    "cancelation": {"mode": "NOTIFY_THEN_TERMINATE", "notifyPeriodInSeconds": "1"},
                },
                id="cancel notify as string",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        # Parsing tests of valid Open Job Description Actions
        # It is sufficient to check that parsing the input does not
        # raise an exception. We trust the Pydantic package's testing
        # so, if the input parses then our Action model is correctly
        # constructed for valid input.

        # WHEN
        _parse_model(model=Action, obj=data)

        # THEN
        # no exception was raised.

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({}, id="empty object"),
            pytest.param({"command": "foo", "extra": 12}, id="unknown key"),
            pytest.param({"command": ""}, id="command too short"),
            pytest.param(
                {"command": "{{ Job.Parameter.Foo "}, id="command malformed format string"
            ),
            pytest.param({"command": 1}, id="command not a string"),
            pytest.param({"command": "1", "args": []}, id="args no items"),
            pytest.param({"command": "1", "args": [12]}, id="args item not string"),
            pytest.param({"command": "1", "timeout": 0}, id="timeout too small"),
            pytest.param({"command": "1", "timeout": 601}, id="timeout too large"),
            pytest.param({"command": "1", "timeout": 0.5}, id="timeout not int"),
            pytest.param({"command": "1", "timeout": "0.5"}, id="timeout not intstring"),
            pytest.param({"command": "1", "cancelation": "TERMINATE"}, id="cancelation not obj"),
            pytest.param(
                {"command": "1", "cancelation": {"mode": "UNKNOWN"}}, id="cancelation unknown mode"
            ),
            pytest.param(
                {"command": "1", "cancelation": {"mode": "terminate"}},
                id="cancelation terminate lowercase",
            ),
            pytest.param(
                {"command": "1", "cancelation": {"mode": "notify_then_terminate"}},
                id="cancelation notify-terminate lowercase",
            ),
            pytest.param(
                {
                    "command": "1",
                    "cancelation": {"mode": "NOTIFY_THEN_TERMINATE", "notifyPeriodInSeconds": 0},
                },
                id="cancelation notify too small",
            ),
            pytest.param(
                {
                    "command": "1",
                    "cancelation": {"mode": "NOTIFY_THEN_TERMINATE", "notifyPeriodInSeconds": 0.5},
                },
                id="cancelation notify is float",
            ),
            pytest.param(
                {
                    "command": "1",
                    "cancelation": {
                        "mode": "NOTIFY_THEN_TERMINATE",
                        "notifyPeriodInSeconds": "0.5",
                    },
                },
                id="cancelation notify not intstring",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # Failure case testing for Open Job Description Actions.
        # - Constraint tests
        # - extra field test

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=StepActions, obj=data)

        # THEN
        assert len(excinfo.value.errors()) > 0


class TestStepActions:
    @pytest.mark.parametrize(
        "data", (pytest.param({"onRun": {"command": "foo"}}, id="has required"),)
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        # Parsing tests of valid Open Job Description StepActions
        # It is sufficient to check that parsing the input does not
        # raise an exception. We trust the Pydantic package's testing
        # so, if the input parses then our StepActions model is correctly
        # constructed for valid input.

        # WHEN
        _parse_model(model=StepActions, obj=data)

        # THEN
        # no exception was raised.

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({}, id="empty object"),
            pytest.param({"onRun": {"command": "foo"}, "onUnknown": "blah"}, id="unknown field"),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # Failure case testing for Open Job Description StepActions.

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=Action, obj=data)

        # THEN
        assert len(excinfo.value.errors()) > 0


class TestEnvironmentActions:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"onEnter": {"command": "foo"}}, id="has onEnter"),
            pytest.param({"onExit": {"command": "foo"}}, id="has onExit"),
            # For making sure our pre-validator logic is correct
            pytest.param(
                {
                    "onEnter": {"command": "foo"},
                    "onExit": {"command": "foo"},
                },
                id="has both",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        # Parsing tests of valid Open Job Description StepActions
        # It is sufficient to check that parsing the input does not
        # raise an exception. We trust the Pydantic package's testing
        # so, if the input parses then our StepActions model is correctly
        # constructed for valid input.

        # WHEN
        _parse_model(model=EnvironmentActions, obj=data)

        # THEN
        # no exception was raised.

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({}, id="empty object"),
            pytest.param({"onEnter": {"command": "foo"}, "onUnknown": "blah"}, id="unknown field"),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # Failure case testing for Open Job Description StepActions.

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=EnvironmentActions, obj=data)

        # THEN
        assert len(excinfo.value.errors()) > 0
