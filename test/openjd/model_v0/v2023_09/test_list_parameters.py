# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for the EXPR-extension LIST[*] and RANGE_EXPR job parameter types
(RFC 0007): structural parsing, list/item constraints, EXPR gating, and
case-insensitive type names."""

import pytest

from openjd.model import DecodeValidationError, decode_job_template

_STEP = {"name": "S", "script": {"actions": {"onRun": {"command": "echo", "args": ["hi"]}}}}


def _tmpl(param_def, *, extensions=("EXPR",)):
    t = {
        "specificationVersion": "jobtemplate-2023-09",
        "name": "T",
        "parameterDefinitions": [param_def],
        "steps": [_STEP],
    }
    if extensions:
        t["extensions"] = list(extensions)
    return t


def _decode(t):
    return decode_job_template(template=t, supported_extensions=["EXPR"])


class TestListValid:
    @pytest.mark.parametrize(
        "param",
        [
            {"name": "S", "type": "LIST[STRING]", "default": ["a", "b"]},
            {
                "name": "P",
                "type": "LIST[PATH]",
                "default": ["/a", "/b"],
                "objectType": "FILE",
                "dataFlow": "IN",
            },
            {"name": "I", "type": "LIST[INT]", "default": [1, 2, 3]},
            {"name": "F", "type": "LIST[FLOAT]", "default": [1.0, 2.5]},
            {"name": "B", "type": "LIST[BOOL]", "default": [True, False]},
            {"name": "LL", "type": "LIST[LIST[INT]]", "default": [[1, 2], [3]]},
            {"name": "R", "type": "RANGE_EXPR", "default": "1-100:10"},
        ],
    )
    def test_accepts(self, param):
        _decode(_tmpl(param))

    def test_item_constraints_ok(self):
        _decode(
            _tmpl(
                {
                    "name": "S",
                    "type": "LIST[STRING]",
                    "default": ["alpha"],
                    "minLength": 1,
                    "maxLength": 5,
                    "item": {"allowedValues": ["alpha", "beta"], "minLength": 3},
                }
            )
        )

    def test_case_insensitive_type(self):
        _decode(_tmpl({"name": "I", "type": "list[int]", "default": [1]}))


class TestListInvalid:
    def test_requires_expr(self):
        with pytest.raises(DecodeValidationError, match="requires the EXPR extension"):
            _decode(_tmpl({"name": "I", "type": "LIST[INT]", "default": [1]}, extensions=()))

    @pytest.mark.parametrize(
        "param",
        [
            {"name": "S", "type": "LIST[STRING]", "default": "notalist"},  # scalar not list
            {"name": "I", "type": "LIST[INT]", "default": ["not", "ints"]},  # wrong item type
            {
                "name": "I",
                "type": "LIST[INT]",
                "default": [-5],
                "item": {"minValue": 0},
            },  # below min
            {
                "name": "S",
                "type": "LIST[STRING]",
                "default": [""],
                "item": {"minLength": 1},
            },  # too short
            {
                "name": "S",
                "type": "LIST[STRING]",
                "default": ["a", "b", "c"],
                "maxLength": 2,
            },  # too long
            {"name": "LL", "type": "LIST[LIST[INT]]", "default": [[1, "a"]]},  # string in inner
            {"name": "LL", "type": "LIST[LIST[INT]]", "default": [[1], 3]},  # scalar in outer
            {
                "name": "LL",
                "type": "LIST[LIST[INT]]",
                "default": [[999]],
                "item": {"item": {"maxValue": 100}},
            },
            {"name": "R", "type": "RANGE_EXPR", "default": "not-a-range"},  # bad range expr
        ],
    )
    def test_rejects(self, param):
        with pytest.raises(DecodeValidationError):
            _decode(_tmpl(param))
