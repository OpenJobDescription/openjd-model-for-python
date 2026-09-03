# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Coercion of SUBMITTED string values for EXPR-typed job parameters.

The public input type is ``dict[str, str]``, so string forms must be
accepted: BOOL takes the spec's boolean strings and LIST[*] takes JSON,
mirroring openjd-rs's ``coerce_from_str`` (job/create_job/parameters.rs).
Previously BOOL ``"no"`` was stored verbatim and JSON list strings were
rejected outright while the Rust CLI accepted both.
"""

import pytest

from openjd.model import (
    create_job,
    decode_environment_template,
    decode_job_template,
    preprocess_job_parameters,
)

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


_LIST_BOOL_TEMPLATE = {
    "specificationVersion": "jobtemplate-2023-09",
    "extensions": ["EXPR"],
    "name": "T",
    "parameterDefinitions": [{"name": "Flags", "type": "LIST[BOOL]"}],
    "steps": [
        {
            "name": "S",
            "script": {"actions": {"onRun": {"command": "echo", "args": ["{{ Param.Flags[0] }}"]}}},
        }
    ],
}


@pytest.fixture
def list_bool_template():
    return decode_job_template(template=_LIST_BOOL_TEMPLATE, supported_extensions=["EXPR"])


class TestListBoolValueCoercion:
    """RFC 0007 §2.15: each LIST[BOOL] item accepts the same spellings as scalar
    BOOL and is coerced per item. Heterogeneous native lists and JSON-string forms both
    normalize to a list[bool]; an unrecognized item is rejected with the
    offending parameter named. Previously items passed through unchanged and a
    heterogeneous list only failed later with an opaque Rust type error.
    """

    def test_native_list_coerced_per_item(self, list_bool_template, tmp_path) -> None:
        pv = _preprocess(list_bool_template, {"Flags": ["yes", 0, True]}, tmp_path)
        assert pv["Flags"].value == [True, False, True]
        # equality alone passes for ints ([1,0,1] == [True,False,True]).
        assert all(type(x) is bool for x in pv["Flags"].value)

    def test_json_string_list_coerced_per_item(self, list_bool_template, tmp_path) -> None:
        pv = _preprocess(list_bool_template, {"Flags": '[true, "off", 1]'}, tmp_path)
        assert pv["Flags"].value == [True, False, True]
        # equality alone passes for ints ([1,0,1] == [True,False,True]).
        assert all(type(x) is bool for x in pv["Flags"].value)

    def test_json_string_float_spelling_coerced_per_item(
        self, list_bool_template, tmp_path
    ) -> None:
        # The valid float spelling 1.0/0.0 is accepted per item and stored as
        # canonical booleans; equality alone would pass ([1.0, 0.0] ==
        # [True, False]), so the type check proves per-item coercion ran.
        pv = _preprocess(list_bool_template, {"Flags": "[1.0, 0.0]"}, tmp_path)
        assert pv["Flags"].value == [True, False]
        assert all(type(x) is bool for x in pv["Flags"].value)

    def test_invalid_item_rejected_with_parameter_name(self, list_bool_template, tmp_path) -> None:
        with pytest.raises(ValueError, match=r"Parameter Flags"):
            _preprocess(list_bool_template, {"Flags": ["maybe"]}, tmp_path)

    def test_json_string_invalid_item_rejected_with_parameter_name(
        self, list_bool_template, tmp_path
    ) -> None:
        # The JSON-string form must ALSO name the parameter on a bad item,
        # exercising the parse-then-coerce error branch (the native-list form
        # is covered by test_invalid_item_rejected_with_parameter_name).
        with pytest.raises(ValueError, match=r"Parameter Flags"):
            _preprocess(list_bool_template, {"Flags": '["maybe"]'}, tmp_path)

    @pytest.mark.parametrize(
        "submitted",
        [
            pytest.param("[[true]]", id="nested-list-item"),
            pytest.param("[null]", id="null-item"),
            pytest.param("[2]", id="int-out-of-range-item"),
            pytest.param("[2.0]", id="float-out-of-range-item"),
        ],
    )
    def test_json_string_invalid_items_rejected_with_parameter_name(
        self, list_bool_template, tmp_path, submitted
    ) -> None:
        # Each parsed item fails _coerce_bool_value (a list, null, an int
        # other than 0/1, or a float other than 0.0/1.0), so the JSON-string
        # form must name the parameter on the offending item.
        with pytest.raises(ValueError, match=r"Parameter Flags"):
            _preprocess(list_bool_template, {"Flags": submitted}, tmp_path)

    @pytest.mark.parametrize(
        "submitted",
        [
            pytest.param([None], id="null-item"),
            pytest.param([2], id="int-out-of-range-item"),
            pytest.param([2.0], id="float-out-of-range-item"),
            pytest.param([[True]], id="nested-list-item"),
        ],
    )
    def test_native_list_invalid_items_rejected_with_parameter_name(
        self, list_bool_template, tmp_path, submitted
    ) -> None:
        # The native-list submitted branch (not the JSON-string parse-then-
        # coerce branch) must also name the parameter when an item fails
        # _coerce_bool_value: null, an int other than 0/1, a float other than
        # 0.0/1.0, or a nested list each pin the existing per-item guard.
        with pytest.raises(ValueError, match=r"Parameter Flags"):
            _preprocess(list_bool_template, {"Flags": submitted}, tmp_path)

    def test_json_object_not_a_list_rejected(self, list_bool_template, tmp_path) -> None:
        # A JSON object (not an array) hits the non-list JSON guard before any
        # per-item coercion runs.
        with pytest.raises(ValueError, match=r"not valid JSON for a list parameter"):
            _preprocess(list_bool_template, {"Flags": '{"a": 1}'}, tmp_path)

    @pytest.mark.parametrize(
        "bad",
        [
            pytest.param("[1,2", id="malformed-json"),
            pytest.param('{"a": 1}', id="json-but-not-a-list"),
        ],
    )
    def test_json_parse_error_not_prefixed_matches_other_list_types(
        self, list_bool_template, template, tmp_path, bad
    ) -> None:
        # The JSON-level parse error is shared by all LIST[*] types and is not a
        # per-item coercion failure, so LIST[BOOL] must NOT prefix it with the
        # parameter name; the message must be byte-identical to the one a
        # LIST[INT] parameter produces for the same bad input.
        with pytest.raises(ValueError) as bool_exc:
            _preprocess(list_bool_template, {"Flags": bad}, tmp_path)
        with pytest.raises(ValueError) as int_exc:
            _preprocess(template, {"Flag": "true", "Values": bad, "Nested": [[1]]}, tmp_path)
        # The parse error is the first collected error; the trailing
        # missing-value line names each template's own list parameter, so
        # compare the parse-error line itself.
        assert not str(bool_exc.value).startswith("Parameter")
        assert str(bool_exc.value).splitlines()[0] == str(int_exc.value).splitlines()[0]

    def test_empty_native_list_passes_through(self, list_bool_template, tmp_path) -> None:
        # The LIST[BOOL] definition declares no minLength, so an empty list is
        # accepted and stored unchanged (per-item coercion of [] yields []).
        pv = _preprocess(list_bool_template, {"Flags": []}, tmp_path)
        assert pv["Flags"].value == []

    @pytest.mark.parametrize(
        "submitted",
        [
            pytest.param([1, 0], id="ints"),
            pytest.param([1.0, 0.0], id="floats"),
            pytest.param(["yes", "off"], id="strings"),
        ],
    )
    def test_homogeneous_list_coerced_to_bools(
        self, list_bool_template, tmp_path, submitted
    ) -> None:
        # Homogeneous rows are the silent-failure case: [1, 0] and [1.0, 0.0]
        # each compare equal to [True, False] in Python (bool is an int
        # subclass, 1.0 == True), so an equality-only assertion would pass even
        # if coercion never ran. The type check is what proves per-item
        # coercion actually happened; the all-strings row would store verbatim
        # (and later fail with an opaque type error) without the fix.
        pv = _preprocess(list_bool_template, {"Flags": submitted}, tmp_path)
        assert pv["Flags"].value == [True, False]
        assert all(type(x) is bool for x in pv["Flags"].value)


_NONBOOL_LIST_TEMPLATE = {
    "specificationVersion": "jobtemplate-2023-09",
    "extensions": ["EXPR"],
    "name": "T",
    "parameterDefinitions": [
        {"name": "Ints", "type": "LIST[INT]"},
        {"name": "Strs", "type": "LIST[STRING]"},
    ],
    "steps": [
        {
            "name": "S",
            "script": {"actions": {"onRun": {"command": "echo", "args": ["{{ Param.Ints[0] }}"]}}},
        }
    ],
}


@pytest.fixture
def nonbool_list_template():
    return decode_job_template(template=_NONBOOL_LIST_TEMPLATE, supported_extensions=["EXPR"])


class TestNonBoolListCoercionGuards:
    """Per-item BOOL coercion must apply ONLY to LIST[BOOL]. Other LIST[*] types
    keep their prior behavior: LIST[INT] still parses a JSON-string form, and a
    native LIST[STRING] value passes through untouched (no per-item coercion).
    """

    def test_list_int_json_string_still_parsed(self, nonbool_list_template, tmp_path) -> None:
        pv = _preprocess(nonbool_list_template, {"Ints": "[1, 2, 3]", "Strs": ["a", "b"]}, tmp_path)
        assert pv["Ints"].value == [1, 2, 3]

    def test_list_string_native_passthrough(self, nonbool_list_template, tmp_path) -> None:
        pv = _preprocess(nonbool_list_template, {"Ints": [1], "Strs": ["a", "b"]}, tmp_path)
        assert pv["Strs"].value == ["a", "b"]


# A job template that declares the EXPR extension and a step but defines no
# job parameters of its own — the LIST[BOOL] parameter is contributed solely by
# an environment template, so its default flows through the merge path.
_JOB_TEMPLATE_NO_PARAMS = {
    "specificationVersion": "jobtemplate-2023-09",
    "extensions": ["EXPR"],
    "name": "T",
    "steps": [
        {
            "name": "S",
            "script": {"actions": {"onRun": {"command": "echo", "args": ["hi"]}}},
        }
    ],
}


def _env_template(default):
    return {
        "specificationVersion": "environment-2023-09",
        "extensions": ["EXPR"],
        "parameterDefinitions": [{"name": "Flags", "type": "LIST[BOOL]", "default": default}],
        "environment": {
            "name": "Env1",
            "script": {"actions": {"onEnter": {"command": "bar"}}},
        },
    }


class TestEnvironmentTemplateListBoolDefaultCoercion:
    """RFC 0007 §2.15: a LIST[BOOL] default supplied by an environment template
    (not the job template) is normalized per item at the create boundary, just
    like a job-template default. The merged definition reaches
    ``_collect_defaults_2023_09`` via ``merge_job_parameter_definitions``, whose
    ``model_copy`` carry-over deliberately skips validators, so the coercion
    must happen at collection time rather than being assumed to have run during
    decode/merge.
    """

    def test_env_template_mixed_spelling_default_coerced(self, tmp_path) -> None:
        jt = decode_job_template(template=_JOB_TEMPLATE_NO_PARAMS, supported_extensions=["EXPR"])
        env = decode_environment_template(
            template=_env_template([True, "yes", 0]), supported_extensions=["EXPR"]
        )
        pv = preprocess_job_parameters(
            job_template=jt,
            job_parameter_values={},
            job_template_dir=tmp_path,
            current_working_dir=tmp_path,
            environment_templates=[env],
        )
        assert pv["Flags"].value == [True, True, False]
        # equality alone passes for ints ([1,1,0] == [True,True,False]); the
        # type check proves the mixed-spelling items were coerced to bools.
        assert all(type(x) is bool for x in pv["Flags"].value)

    def test_env_template_empty_list_default_passes_through(self, tmp_path) -> None:
        jt = decode_job_template(template=_JOB_TEMPLATE_NO_PARAMS, supported_extensions=["EXPR"])
        env = decode_environment_template(template=_env_template([]), supported_extensions=["EXPR"])
        pv = preprocess_job_parameters(
            job_template=jt,
            job_parameter_values={},
            job_template_dir=tmp_path,
            current_working_dir=tmp_path,
            environment_templates=[env],
        )
        assert pv["Flags"].value == []
