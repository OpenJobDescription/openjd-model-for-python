# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for EXPR task-parameter range expressions (RFC 0007): a STRING/FLOAT/
PATH task parameter `range` given as a single `{{ ... }}` expression that
resolves to a list, mirroring the existing INT behaviour. Gated on EXPR."""

import pytest

from openjd.model import DecodeValidationError, decode_job_template


def _tmpl(task_param, *, extensions=("EXPR",)):
    t = {
        "specificationVersion": "jobtemplate-2023-09",
        "name": "T",
        "parameterDefinitions": [{"name": "Prefix", "type": "STRING", "default": "x"}],
        "steps": [
            {
                "name": "S",
                "parameterSpace": {"taskParameterDefinitions": [task_param]},
                "script": {"actions": {"onRun": {"command": "echo", "args": ["{{Task.Param.P}}"]}}},
            }
        ],
    }
    if extensions:
        t["extensions"] = list(extensions)
    return t


def _decode(t):
    return decode_job_template(template=t, supported_extensions=["EXPR"])


class TestTaskRangeExpr:
    @pytest.mark.parametrize("ptype", ["STRING", "FLOAT", "PATH"])
    def test_range_expression_accepted_with_expr(self, ptype):
        _decode(_tmpl({"name": "P", "type": ptype, "range": "{{ [Param.Prefix] }}"}))

    @pytest.mark.parametrize("ptype", ["STRING", "FLOAT", "PATH"])
    def test_literal_list_range_still_accepted(self, ptype):
        rng = ["1.0"] if ptype == "FLOAT" else ["a"]
        _decode(_tmpl({"name": "P", "type": ptype, "range": rng}))

    def test_range_expression_requires_expr(self):
        # Without EXPR the expression range is rejected (either by the EXPR
        # gate or because the `[...]` grammar is invalid in the legacy parser).
        with pytest.raises(DecodeValidationError):
            _decode(
                _tmpl(
                    {"name": "P", "type": "STRING", "range": "{{ [Param.Prefix] }}"},
                    extensions=(),
                )
            )
