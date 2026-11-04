# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Job creation for the format string elements of task parameter range lists.

Template Schemas §3.4.1.1 and §3.4.1.2: an element of an INT, CHUNK[INT] or
FLOAT range list may be a <TaskParameterStringValue>, which must resolve to
the string representation of a number. With the EXPR extension, Expression
Language §1.3.2 makes every range list element a list item, with target type
``T? | list[T]``: a whole-field ``null`` drops the element, a list flattens
into one element per member, and a value that does not coerce is rejected.
openjd-rs (crates/openjd-model/src/job/create_job/ranges.rs) does the same.
"""

from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

import pytest

from openjd.model import (
    DecodeValidationError,
    create_job,
    decode_job_template,
    preprocess_job_parameters,
)


def _range(
    tmp_path: Path,
    task_param: dict[str, Any],
    params: list[dict[str, Any]],
    values: dict[str, str],
    extensions: Optional[list[str]] = None,
) -> list[Any]:
    """Create a job with one task parameter, X, and return its resolved range."""
    template: dict[str, Any] = {
        "specificationVersion": "jobtemplate-2023-09",
        "name": "T",
        "parameterDefinitions": params,
        "steps": [
            {
                "name": "S",
                "parameterSpace": {"taskParameterDefinitions": [{"name": "X", **task_param}]},
                "script": {"actions": {"onRun": {"command": "echo"}}},
            }
        ],
    }
    if extensions:
        template["extensions"] = extensions
    job_template = decode_job_template(
        template=template, supported_extensions=["EXPR", "TASK_CHUNKING"]
    )
    processed = preprocess_job_parameters(
        job_template=job_template,
        job_parameter_values=values,
        job_template_dir=tmp_path,
        current_working_dir=tmp_path,
    )
    job = create_job(job_template=job_template, job_parameter_values=processed)
    assert job.steps[0].parameterSpace is not None
    return list(job.steps[0].parameterSpace.taskParameterDefinitions["X"].range)


def _range_error(tmp_path: Path, *args: Any, **kwargs: Any) -> str:
    with pytest.raises(DecodeValidationError) as excinfo:
        _range(tmp_path, *args, **kwargs)
    return str(excinfo.value)


_CHUNKS = {"defaultTaskCount": 1, "rangeConstraint": "NONCONTIGUOUS"}
_STRING_S = [{"name": "S", "type": "STRING"}]
_ELEMENT_1 = (
    "1 validation errors for JobTemplate\n"
    "steps[0] -> parameterSpace -> taskParameterDefinitions[0] -> range[1]:\n\t"
)


class TestWithoutExpr:
    """Without EXPR an element resolves to a string, parsed as an <intstring>
    or <floatstring>."""

    @pytest.mark.parametrize(
        "task_param, extensions",
        [
            pytest.param({"type": "INT"}, None, id="INT"),
            pytest.param({"type": "CHUNK[INT]", "chunks": _CHUNKS}, ["TASK_CHUNKING"], id="CHUNK"),
        ],
    )
    def test_int_elements_resolve(self, tmp_path, task_param, extensions) -> None:
        params = [{"name": "I", "type": "INT"}, {"name": "S", "type": "STRING"}]
        result = _range(
            tmp_path,
            {**task_param, "range": [1, "2", "{{Param.I}}", "{{Param.S}}", "1{{Param.I}}"]},
            params,
            {"I": "7", "S": " 9 "},
            extensions,
        )
        assert result == [1, 2, 7, 9, 17]

    @pytest.mark.parametrize(
        "task_param, extensions",
        [
            pytest.param({"type": "INT"}, None, id="INT"),
            # CHUNK[INT] used to keep the text and raise an uncaught ValueError
            # when the parameter space was iterated.
            pytest.param({"type": "CHUNK[INT]", "chunks": _CHUNKS}, ["TASK_CHUNKING"], id="CHUNK"),
        ],
    )
    @pytest.mark.parametrize("value", ["abc", "2.5", ""])
    def test_int_element_not_an_integer(self, tmp_path, task_param, extensions, value) -> None:
        error = _range_error(
            tmp_path,
            {**task_param, "range": [1, "{{Param.S}}"]},
            _STRING_S,
            {"S": value},
            extensions,
        )
        assert error == _ELEMENT_1 + f"value {value!r} is not an integer."

    def test_float_elements_resolve_and_keep_their_spelling(self, tmp_path) -> None:
        params = [{"name": "F", "type": "FLOAT"}, {"name": "I", "type": "INT"}]
        result = _range(
            tmp_path,
            {"type": "FLOAT", "range": [1.5, "{{Param.F}}", "{{Param.I}}", " 02.50 "]},
            params,
            {"F": "2.50", "I": "10"},
        )
        assert result == [Decimal("1.5"), "2.50", "10", "2.50"]

    @pytest.mark.parametrize(
        "value, problem",
        [
            ("abc", "is not a number"),
            ("", "is not a number"),
            ("inf", "is not finite"),
            ("nan", "is not finite"),
        ],
    )
    def test_float_element_not_a_finite_number(self, tmp_path, value, problem) -> None:
        error = _range_error(
            tmp_path, {"type": "FLOAT", "range": [1.5, "{{Param.S}}"]}, _STRING_S, {"S": value}
        )
        assert error == _ELEMENT_1 + f"value {value!r} {problem}."

    def test_string_elements_are_not_list_items(self, tmp_path) -> None:
        # Without EXPR an element cannot produce null or a list, and resolves
        # to its string unchanged.
        result = _range(
            tmp_path, {"type": "STRING", "range": ["a", " {{Param.S}} "]}, _STRING_S, {"S": "b"}
        )
        assert result == ["a", " b "]


class TestWithExpr:
    """With EXPR a whole-field element is a list item (Expression Language §1.3.2)."""

    @pytest.mark.parametrize(
        "task_param, extensions",
        [
            pytest.param({"type": "INT"}, ["EXPR"], id="INT"),
            pytest.param(
                {"type": "CHUNK[INT]", "chunks": _CHUNKS}, ["EXPR", "TASK_CHUNKING"], id="CHUNK"
            ),
        ],
    )
    def test_int_null_drops_list_flattens_and_coerces(
        self, tmp_path, task_param, extensions
    ) -> None:
        params = [{"name": "L", "type": "LIST[INT]"}, {"name": "S", "type": "STRING"}]
        result = _range(
            tmp_path,
            {
                **task_param,
                "range": [
                    1,
                    "{{ null }}",
                    "{{ Param.L }}",
                    "{{ range_expr('7-8') }}",
                    "{{ 3.0 * 3 }}",
                    "{{ Param.S }}",
                ],
            },
            params,
            {"L": "[3, 4]", "S": "5"},
            extensions,
        )
        assert result == [1, 3, 4, 7, 8, 9, 5]

    def test_float_null_drops_list_flattens_and_keeps_spelling(self, tmp_path) -> None:
        params = [
            {"name": "F", "type": "FLOAT"},
            {"name": "I", "type": "INT"},
            {"name": "L", "type": "LIST[INT]"},
        ]
        result = _range(
            tmp_path,
            {
                "type": "FLOAT",
                "range": [
                    1.5,
                    "{{ null }}",
                    "{{ Param.F }}",
                    "{{ Param.I }}",
                    "{{ [Param.F] }}",
                    "{{ Param.L }}",
                ],
            },
            params,
            {"F": "2.50", "I": "10", "L": "[3, 4]"},
            ["EXPR"],
        )
        # A float keeps its spelling, an integer is written as is, and the
        # integer members of a list converted to float are written as floats,
        # as in openjd-rs.
        assert result == [Decimal("1.5"), "2.50", "10", "2.50", "3.0", "4.0"]

    @pytest.mark.parametrize("param_type", ["STRING", "PATH"])
    def test_string_and_path_null_drops_and_list_flattens(self, tmp_path, param_type) -> None:
        result = _range(
            tmp_path,
            {"type": param_type, "range": ["/c", "{{ null }}", "{{ Param.L }}", " {{ 'x' }} "]},
            [{"name": "L", "type": "LIST[STRING]"}],
            {"L": '["/a", "/b"]'},
            ["EXPR"],
        )
        # Text around the expression, even white space, makes the element a
        # string rather than a list item.
        assert result == ["/c", "/a", "/b", " x "]

    @pytest.mark.parametrize(
        "task_param, extensions, target",
        [
            pytest.param({"type": "INT"}, ["EXPR"], "int | list[int] | nulltype", id="INT"),
            pytest.param(
                {"type": "CHUNK[INT]", "chunks": _CHUNKS},
                ["EXPR", "TASK_CHUNKING"],
                "int | list[int] | nulltype",
                id="CHUNK",
            ),
            pytest.param(
                {"type": "FLOAT"}, ["EXPR"], "float | int | list[float] | nulltype", id="FLOAT"
            ),
        ],
    )
    def test_list_of_wrong_type_rejected(self, tmp_path, task_param, extensions, target) -> None:
        error = _range_error(
            tmp_path,
            {**task_param, "range": [1, "{{ Param.L }}"]},
            [{"name": "L", "type": "LIST[STRING]"}],
            {"L": '["a"]'},
            extensions,
        )
        assert error == _ELEMENT_1 + (
            "Failed to parse interpolation expression at [0, 13]. Expression:  Param.L . "
            f"Reason: Expression failed validation: Cannot coerce list[string] to {target}\n"
            "  Param.L\n  ~~~~~~^."
        )

    def test_padded_string_does_not_coerce(self, tmp_path) -> None:
        # Expression Language §1.2.3 coercion does not trim, unlike the
        # <intstring> parse without EXPR.
        error = _range_error(
            tmp_path,
            {"type": "INT", "range": [1, "{{Param.S}}"]},
            _STRING_S,
            {"S": " 7 "},
            ["EXPR"],
        )
        assert error == _ELEMENT_1 + (
            "Failed to parse interpolation expression at [0, 11]. Expression: Param.S. "
            "Reason: Expression failed validation: Cannot coerce string to int | list[int] | nulltype\n"
            "  Param.S\n  ~~~~~~^."
        )

    def test_text_around_expression_resolves_to_string(self, tmp_path) -> None:
        result = _range(
            tmp_path,
            {"type": "INT", "range": ["1{{ Param.S }}", "{{ 2 }}{{ 3 }}"]},
            _STRING_S,
            {"S": "5"},
            ["EXPR"],
        )
        assert result == [15, 23]

    @pytest.mark.parametrize(
        "task_param, extensions",
        [
            pytest.param({"type": "INT"}, ["EXPR"], id="INT"),
            pytest.param({"type": "FLOAT"}, ["EXPR"], id="FLOAT"),
            pytest.param({"type": "STRING"}, ["EXPR"], id="STRING"),
            pytest.param(
                {"type": "CHUNK[INT]", "chunks": _CHUNKS}, ["EXPR", "TASK_CHUNKING"], id="CHUNK"
            ),
        ],
    )
    def test_list_emptied_by_null_rejected(self, tmp_path, task_param, extensions) -> None:
        error = _range_error(
            tmp_path,
            {**task_param, "range": ["{{ null }}", "{{ null if Param.S == 'x' else 1 }}"]},
            _STRING_S,
            {"S": "x"},
            extensions,
        )
        assert error == (
            "1 validation errors for JobTemplate\n"
            "steps[0] -> parameterSpace -> taskParameterDefinitions[0] -> range:\n\t"
            "has no elements after resolution."
        )

    def test_flattened_list_past_element_limit_rejected(self, tmp_path) -> None:
        error = _range_error(
            tmp_path,
            {"type": "INT", "range": [0, "{{ range_expr('1-1024') }}"]},
            _STRING_S,
            {"S": "x"},
            ["EXPR"],
        )
        assert "steps[0] -> parameterSpace -> taskParameterDefinitions[0] -> range:\n\t" in error
        assert "1024" in error
