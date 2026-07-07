# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Regression tests for create-time and merge-time constraint validation of the
EXPR-extension (RFC 0007) job-parameter types — LIST[*] and RANGE_EXPR.

These guard against three previously-found gaps:

* ``preprocess_job_parameters`` did not enforce ``item.*`` / length / range
  constraints on a *user-supplied* value for these types (only the template
  ``default`` was validated at decode time).
* ``merge_job_parameter_definitions_for_one`` applied a merged default via
  ``model_copy``, which skips validators, so a default carried over from one
  source that violated another source's constraints went unchecked.
"""

from pathlib import Path

import pytest

from openjd.model import (
    decode_environment_template,
    decode_job_template,
    preprocess_job_parameters,
)


def _template(param_def):
    return {
        "specificationVersion": "jobtemplate-2023-09",
        "name": "T",
        "extensions": ["EXPR"],
        "parameterDefinitions": [param_def],
        "steps": [{"name": "S", "script": {"actions": {"onRun": {"command": "echo"}}}}],
    }


def _env_template(param_def):
    return {
        "specificationVersion": "environment-2023-09",
        "extensions": ["EXPR"],
        "parameterDefinitions": [param_def],
        "environment": {"name": "E", "script": {"actions": {"onEnter": {"command": "echo"}}}},
    }


def _preprocess(param_def, values, *, environment_templates=None):
    jt = decode_job_template(template=_template(param_def), supported_extensions=["EXPR"])
    return preprocess_job_parameters(
        job_template=jt,
        job_parameter_values=values,
        job_template_dir=Path(),
        current_working_dir=Path(),
        allow_job_template_dir_walk_up=True,
        environment_templates=environment_templates,
    )


class TestListParameterValueConstraints:
    """A user-supplied value for a LIST[*] parameter is checked against the
    definition's length and per-item constraints at preprocess/create time."""

    def test_item_maxvalue_violation_rejected(self):
        with pytest.raises(ValueError, match=r"item 999 is above item\.maxValue 10"):
            _preprocess(
                {"name": "Nums", "type": "LIST[INT]", "item": {"maxValue": 10}},
                {"Nums": [999]},
            )

    def test_item_allowedvalues_violation_rejected(self):
        with pytest.raises(ValueError, match=r"not in item\.allowedValues"):
            _preprocess(
                {"name": "Tags", "type": "LIST[STRING]", "item": {"allowedValues": ["a", "b"]}},
                {"Tags": ["z"]},
            )

    def test_maxlength_violation_rejected(self):
        with pytest.raises(ValueError, match=r"list length 3 exceeds maxLength 2"):
            _preprocess(
                {"name": "Nums", "type": "LIST[INT]", "maxLength": 2},
                {"Nums": [1, 2, 3]},
            )

    def test_wrong_item_type_rejected(self):
        with pytest.raises(ValueError, match=r"list items must be integers"):
            _preprocess({"name": "Nums", "type": "LIST[INT]"}, {"Nums": ["not-an-int"]})

    def test_non_list_value_rejected(self):
        with pytest.raises(ValueError, match=r"value must be a list"):
            _preprocess({"name": "Nums", "type": "LIST[INT]"}, {"Nums": "5"})

    def test_list_list_int_inner_constraint_enforced(self):
        with pytest.raises(ValueError, match=r"item 99 is above item\.maxValue 10"):
            _preprocess(
                {
                    "name": "M",
                    "type": "LIST[LIST[INT]]",
                    "item": {"item": {"maxValue": 10}},
                },
                {"M": [[1, 2], [99]]},
            )

    def test_valid_value_accepted(self):
        result = _preprocess(
            {"name": "Nums", "type": "LIST[INT]", "item": {"maxValue": 10}},
            {"Nums": [5, 6]},
        )
        assert result["Nums"].value == [5, 6]


class TestRangeExprValueConstraints:
    """A user-supplied RANGE_EXPR value is validated against the IntRangeExpr
    grammar at preprocess/create time."""

    def test_malformed_range_rejected(self):
        with pytest.raises(ValueError, match=r"parameter R"):
            _preprocess({"name": "R", "type": "RANGE_EXPR"}, {"R": "1-abc"})

    def test_non_string_range_rejected(self):
        with pytest.raises(ValueError, match=r"must be a string"):
            _preprocess({"name": "R", "type": "RANGE_EXPR"}, {"R": [1, 2, 3]})

    def test_valid_range_accepted(self):
        result = _preprocess({"name": "R", "type": "RANGE_EXPR"}, {"R": "1-100:10"})
        assert result["R"].value == "1-100:10"


class TestMergedDefaultRevalidation:
    """When the same EXPR parameter is defined in more than one template, the
    merged (last-defined) default is re-validated against the surviving (job
    template) definition's constraints — model_copy alone skips validators."""

    def test_merged_default_violating_maxlength_rejected(self):
        # The environment template supplies default [1,2,3,4,5]; the job template
        # constrains the same parameter to maxLength 2 and supplies no default.
        # The carried-over default must be rejected.
        env = decode_environment_template(
            template=_env_template(
                {"name": "Nums", "type": "LIST[INT]", "default": [1, 2, 3, 4, 5]}
            ),
            supported_extensions=["EXPR"],
        )
        with pytest.raises(ValueError, match=r"list length 5 exceeds maxLength 2"):
            _preprocess(
                {"name": "Nums", "type": "LIST[INT]", "maxLength": 2},
                {},
                environment_templates=[env],
            )

    def test_merged_default_violating_item_constraint_rejected(self):
        env = decode_environment_template(
            template=_env_template({"name": "Nums", "type": "LIST[INT]", "default": [99]}),
            supported_extensions=["EXPR"],
        )
        with pytest.raises(ValueError, match=r"item 99 is above item\.maxValue 10"):
            _preprocess(
                {"name": "Nums", "type": "LIST[INT]", "item": {"maxValue": 10}},
                {},
                environment_templates=[env],
            )

    def test_compatible_merged_default_accepted(self):
        env = decode_environment_template(
            template=_env_template({"name": "Nums", "type": "LIST[INT]", "default": [1, 2]}),
            supported_extensions=["EXPR"],
        )
        result = _preprocess(
            {"name": "Nums", "type": "LIST[INT]", "maxLength": 5},
            {},
            environment_templates=[env],
        )
        assert result["Nums"].value == [1, 2]
