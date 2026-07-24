# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Coercion of SUBMITTED string values for EXPR-typed job parameters.

The public input type is ``dict[str, str]``, so string forms must be
accepted: BOOL takes the spec's boolean strings and LIST[*] takes JSON,
mirroring openjd-rs's ``coerce_from_str`` (job/create_job/parameters.rs).
Previously BOOL ``"no"`` was stored verbatim and JSON list strings were
rejected outright while the Rust CLI accepted both.
"""

import pytest

from openjd.model import create_job, decode_job_template, preprocess_job_parameters

_TEMPLATE = {
    "specificationVersion": "jobtemplate-2023-09",
    "extensions": ["EXPR"],
    "name": "T",
    "parameterDefinitions": [
        {"name": "Flag", "type": "BOOL"},
        {"name": "Values", "type": "LIST[INT]"},
        {"name": "Nested", "type": "LIST[LIST[INT]]"},
    ],
    "steps": [
        {
            "name": "S",
            "script": {
                "actions": {
                    "onRun": {
                        "command": "echo",
                        "args": [
                            "{{ Param.Flag }}",
                            "{{ Param.Values[0] + 1 }}",
                            "{{ Param.Nested[0][1] }}",
                        ],
                    }
                }
            },
        }
    ],
}


@pytest.fixture
def template():
    return decode_job_template(template=_TEMPLATE, supported_extensions=["EXPR"])


def _preprocess(template, values, tmp_path):
    return preprocess_job_parameters(
        job_template=template,
        job_parameter_values=values,
        job_template_dir=tmp_path,
        current_working_dir=tmp_path,
    )


class TestExprParameterValueCoercion:
    @pytest.mark.parametrize(
        "submitted, expected",
        [
            pytest.param("true", True, id="true"),
            pytest.param("no", False, id="no"),
            pytest.param("ON", True, id="on-case-insensitive"),
            pytest.param("0", False, id="zero"),
            pytest.param(True, True, id="native-bool-passthrough"),
        ],
    )
    def test_bool_string_forms_coerced(self, template, tmp_path, submitted, expected):
        pv = _preprocess(template, {"Flag": submitted, "Values": [1], "Nested": [[1, 2]]}, tmp_path)
        assert pv["Flag"].value is expected

    def test_json_list_strings_coerced(self, template, tmp_path):
        pv = _preprocess(
            template, {"Flag": "true", "Values": "[1,2]", "Nested": "[[1,2],[3]]"}, tmp_path
        )
        assert pv["Values"].value == [1, 2]
        assert pv["Nested"].value == [[1, 2], [3]]
        # And the coerced values evaluate as their native types end-to-end.
        create_job(job_template=template, job_parameter_values=pv)

    def test_native_lists_pass_through(self, template, tmp_path):
        pv = _preprocess(template, {"Flag": False, "Values": [3, 4], "Nested": [[5]]}, tmp_path)
        assert pv["Values"].value == [3, 4]

    def test_invalid_bool_rejected_with_rust_message(self, template, tmp_path):
        with pytest.raises(ValueError, match=r"not a valid boolean\. Accepted: true/false"):
            _preprocess(template, {"Flag": "nope", "Values": [1], "Nested": [[1]]}, tmp_path)

    @pytest.mark.parametrize(
        "bad",
        [
            pytest.param("[1,2", id="malformed-json"),
            pytest.param('{"a": 1}', id="json-but-not-a-list"),
        ],
    )
    def test_invalid_list_json_rejected_with_rust_message(self, template, tmp_path, bad):
        with pytest.raises(ValueError, match=r"not valid JSON for a list parameter"):
            _preprocess(template, {"Flag": "true", "Values": bad, "Nested": [[1]]}, tmp_path)
