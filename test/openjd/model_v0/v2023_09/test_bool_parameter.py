# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for the EXPR-extension BOOL job parameter type (RFC 0007)."""

import pytest

from openjd.model import DecodeValidationError, decode_job_template

_MINIMAL_STEP = {
    "name": "S",
    "script": {"actions": {"onRun": {"command": "echo", "args": ["hi"]}}},
}


def _template(param_def, *, extensions=("EXPR",)):
    tmpl = {
        "specificationVersion": "jobtemplate-2023-09",
        "name": "T",
        "parameterDefinitions": [param_def],
        "steps": [_MINIMAL_STEP],
    }
    if extensions:
        tmpl["extensions"] = list(extensions)
    return tmpl


def _decode(tmpl):
    return decode_job_template(template=tmpl, supported_extensions=["EXPR"])


class TestBoolParameterValid:
    @pytest.mark.parametrize(
        "default",
        [
            True,
            False,
            1,
            0,
            1.0,
            0.0,
            "true",
            "false",
            "TRUE",
            "False",
            "yes",
            "no",
            "on",
            "off",
            "1",
            "0",
        ],
    )
    def test_accepts_boolish_defaults(self, default):
        _decode(_template({"name": "Flag", "type": "BOOL", "default": default}))

    def test_no_default_ok(self):
        _decode(_template({"name": "Flag", "type": "BOOL"}))

    def test_user_interface_checkbox(self):
        _decode(
            _template(
                {
                    "name": "Flag",
                    "type": "BOOL",
                    "default": True,
                    "userInterface": {"control": "CHECK_BOX", "label": "Enable"},
                }
            )
        )


class TestBoolParameterInvalid:
    def test_requires_expr_extension(self):
        with pytest.raises(DecodeValidationError, match="requires the EXPR extension"):
            _decode(_template({"name": "Flag", "type": "BOOL", "default": True}, extensions=()))

    @pytest.mark.parametrize("default", [2, 0.5, "maybe", -1, 42])
    def test_rejects_non_bool_defaults(self, default):
        with pytest.raises(DecodeValidationError):
            _decode(_template({"name": "Flag", "type": "BOOL", "default": default}))
