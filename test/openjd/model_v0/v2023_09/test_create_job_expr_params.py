# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for instantiating a Job from a template that declares EXPR-extension
job parameter types (RFC 0007): BOOL, RANGE_EXPR, and the LIST[*] variants.

These exercise the pure-Python v0 ``create_job`` path, which previously could
only handle the original scalar types. The new types carry their values
natively (lists/bools) into the instantiated ``JobParameter`` so the typed EXPR
symbol table can coerce them.
"""

from pathlib import Path

import pytest

from openjd.model import (
    DecodeValidationError,
    create_job,
    decode_job_template,
    model_to_object,
    preprocess_job_parameters,
)


def _template(param_def, *, on_run_args=("hi",)):
    return {
        "specificationVersion": "jobtemplate-2023-09",
        "name": "T",
        "extensions": ["EXPR"],
        "parameterDefinitions": [param_def],
        "steps": [
            {
                "name": "S",
                "script": {"actions": {"onRun": {"command": "echo", "args": list(on_run_args)}}},
            }
        ],
    }


def _create(param_def):
    jt = decode_job_template(template=_template(param_def), supported_extensions=["EXPR"])
    return create_job(job_template=jt, job_parameter_values={})


def _stored_value(job, name):
    obj = model_to_object(model=job)
    return obj["parameters"][name]["value"]


class TestCreateJobExprParams:
    @pytest.mark.parametrize(
        "param_def,expected",
        [
            ({"name": "Nums", "type": "LIST[INT]", "default": [1, 2, 3]}, [1, 2, 3]),
            ({"name": "Flag", "type": "BOOL", "default": True}, True),
            ({"name": "Off", "type": "BOOL", "default": "no"}, False),
            ({"name": "Tags", "type": "LIST[STRING]", "default": ["a", "b"]}, ["a", "b"]),
            ({"name": "Fs", "type": "LIST[FLOAT]", "default": [1.5, 2.5]}, [1.5, 2.5]),
            ({"name": "Bs", "type": "LIST[BOOL]", "default": [True, False]}, [True, False]),
            ({"name": "Ps", "type": "LIST[PATH]", "default": ["/a", "/b"]}, ["/a", "/b"]),
            ({"name": "M", "type": "LIST[LIST[INT]]", "default": [[1, 2], [3]]}, [[1, 2], [3]]),
            ({"name": "R", "type": "RANGE_EXPR", "default": "1-3"}, "1-3"),
        ],
    )
    def test_create_job_stores_native_value(self, param_def, expected):
        job = _create(param_def)
        assert _stored_value(job, param_def["name"]) == expected

    def test_create_job_case_insensitive_type(self):
        job = _create({"name": "Nums", "type": "list[int]", "default": [1, 2]})
        assert _stored_value(job, "Nums") == [1, 2]

    def test_create_job_scalar_types_unchanged(self):
        # The original scalar types still round-trip as strings.
        job = _create({"name": "N", "type": "INT", "default": 7})
        assert _stored_value(job, "N") == "7"

    def test_list_bool_default_mixed_spellings_normalized(self) -> None:
        # RFC 0007 §2.15: each LIST[BOOL] item accepts the same spellings as a
        # scalar BOOL and is coerced per item into canonical booleans, not
        # stored verbatim as a heterogeneous list.
        job = _create(
            {"name": "Bs", "type": "LIST[BOOL]", "default": [True, "false", "yes", "off", "1", 0]}
        )
        assert _stored_value(job, "Bs") == [True, False, True, False, True, False]
        # equality alone passes for ints ([1,0,1] == [True,False,True]).
        assert all(type(x) is bool for x in _stored_value(job, "Bs"))

    def test_list_bool_default_mixed_case_strings_normalized(self) -> None:
        # Per-item coercion is case-insensitive, matching the scalar BOOL forms.
        job = _create(
            {
                "name": "Bs",
                "type": "LIST[BOOL]",
                "default": ["TRUE", "False", "YES", "no", "On", "OFF"],
            }
        )
        assert _stored_value(job, "Bs") == [True, False, True, False, True, False]
        # equality alone passes for ints ([1,0,1] == [True,False,True]).
        assert all(type(x) is bool for x in _stored_value(job, "Bs"))

    @pytest.mark.parametrize(
        "default",
        [
            pytest.param([1, 0], id="ints"),
            pytest.param([1.0, 0.0], id="floats"),
            pytest.param(["yes", "off"], id="strings"),
        ],
    )
    def test_list_bool_homogeneous_default_normalized(self, default) -> None:
        # Homogeneous defaults are the silent-failure case: [1, 0] and
        # [1.0, 0.0] each compare equal to [True, False] in Python, so an
        # equality-only assertion would pass even if coercion never ran. The
        # type check is what proves the template default was coerced per item.
        job = _create({"name": "Bs", "type": "LIST[BOOL]", "default": default})
        assert _stored_value(job, "Bs") == [True, False]
        assert all(type(x) is bool for x in _stored_value(job, "Bs"))

    def test_list_bool_empty_default_passes_through(self) -> None:
        # The LIST[BOOL] definition declares no minLength, so an empty default
        # is accepted and reaches create_job unchanged (coercion of [] is []).
        job = _create({"name": "Bs", "type": "LIST[BOOL]", "default": []})
        assert _stored_value(job, "Bs") == []

    def test_list_bool_default_template_not_mutated(self) -> None:
        # create_job coerces a LIST[BOOL] template default to canonical booleans
        # for the created Job, but must build a NEW list and leave the template's
        # own default (and its serialized form) with the raw submitted spellings.
        jt = decode_job_template(
            template=_template({"name": "Bs", "type": "LIST[BOOL]", "default": ["yes", 0, True]}),
            supported_extensions=["EXPR"],
        )
        job = create_job(job_template=jt, job_parameter_values={})
        created = _stored_value(job, "Bs")
        assert created == [True, False, True]
        # equality alone passes for ints ([1,0,1] == [True,False,True]).
        assert all(type(x) is bool for x in created)
        # The template object's default is untouched, with its original item types.
        default = jt.parameterDefinitions[0].default
        assert default == ["yes", 0, True]
        assert [type(x) for x in default] == [str, int, bool]
        # The serialized template still carries the raw spellings, not the coerced booleans.
        dumped = model_to_object(model=jt)["parameterDefinitions"][0]["default"]
        assert dumped == ["yes", 0, True]
        assert [type(x) for x in dumped] == [str, int, bool]

    def test_list_bool_none_default_flows_without_type_error(self) -> None:
        # A LIST[BOOL] definition with no default (default None) must not reach
        # the per-item coercion comprehension: the outer `is not None` check plus
        # the `isinstance(param.default, list)` guard keep None from being
        # iterated. Job creation must surface the normal missing-required-value
        # error, never a TypeError from iterating None.
        jt = decode_job_template(
            template=_template({"name": "Bs", "type": "LIST[BOOL]"}),
            supported_extensions=["EXPR"],
        )
        assert jt.parameterDefinitions[0].default is None
        with pytest.raises(DecodeValidationError, match=r"missing for required job parameters"):
            create_job(job_template=jt, job_parameter_values={})

    def test_list_bool_invalid_default_error_names_parameter(self) -> None:
        # The template-default coercion path must name the offending parameter,
        # matching the submitted-value path. Defaults are normally pre-validated
        # at decode, so bypass decode validation with model_copy to place an
        # invalid item on the default (mirroring the merge path's model_copy
        # carry-over, which skips validators) and reach collection-time coercion.
        jt = decode_job_template(
            template=_template({"name": "Flags", "type": "LIST[BOOL]", "default": [True]}),
            supported_extensions=["EXPR"],
        )
        bad_param = jt.parameterDefinitions[0].model_copy(update={"default": ["maybe"]})
        bad_jt = jt.model_copy(update={"parameterDefinitions": [bad_param]})
        with pytest.raises(ValueError, match=r"Parameter Flags"):
            preprocess_job_parameters(
                job_template=bad_jt,
                job_parameter_values={},
                job_template_dir=Path(),
                current_working_dir=Path(),
                allow_job_template_dir_walk_up=True,
            )

    @pytest.mark.parametrize(
        "param_def,expected",
        [
            ({"name": "Ps", "type": "LIST[PATH]", "default": ["/a", "/b"]}, ["/a", "/b"]),
            ({"name": "Ss", "type": "LIST[STRING]", "default": ["a", "b"]}, ["a", "b"]),
            ({"name": "Ms", "type": "LIST[LIST[INT]]", "default": [[1, 2], [3]]}, [[1, 2], [3]]),
        ],
    )
    def test_non_bool_list_default_unchanged(self, param_def, expected) -> None:
        # Per-item BOOL coercion applies ONLY to LIST[BOOL] defaults; other
        # LIST[*] defaults must reach create_job untouched (no cross-type
        # effect from the LIST[BOOL] normalization added for RFC 0007 §2.15).
        job = _create(param_def)
        assert _stored_value(job, param_def["name"]) == expected


class TestRangeExprTypedValidation:
    """A RANGE_EXPR parameter now carries a typed (``range_expr``) EXPR symbol,
    so expressions referencing it are type-validated at decode time rather than
    only name-checked. Mirrors openjd-rs.
    """

    def _decode_with_expr(self, expr):
        tmpl = _template(
            {"name": "Frames", "type": "RANGE_EXPR", "default": "1-10"},
            on_run_args=["{{ " + expr + " }}"],
        )
        return decode_job_template(template=tmpl, supported_extensions=["EXPR"])

    def test_valid_range_expr_use_accepted(self):
        # Subscripting a RANGE_EXPR parameter is well-typed and must decode.
        self._decode_with_expr("Param.Frames[0]")

    def test_type_mismatch_rejected_at_decode(self):
        # Arithmetic on a RANGE_EXPR is a type error; type-aware validation now
        # catches it (it previously slipped through name-only validation).
        with pytest.raises(DecodeValidationError, match=r"range_expr"):
            self._decode_with_expr("Param.Frames + 1")


class TestTypedPathRangeEmptyValues:
    """§3.4.2: an empty string is not a valid path on any OS. The template
    model rejects literal empty items in a PATH task parameter's range at
    parse time, but a range that arrives via RFC 0006 typed whole-field
    resolution (``range: "{{Param.Paths}}"`` with a LIST[PATH] job parameter)
    is only seen at instantiation — the target model must reject it there,
    matching openjd-rs's resolve-time check in create_job (ranges.rs).
    """

    def _create_with_typed_range(self, list_type, task_type, default, *, ref="Param"):
        jt = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "T",
                "extensions": ["EXPR"],
                "parameterDefinitions": [{"name": "Items", "type": list_type, "default": default}],
                "steps": [
                    {
                        "name": "S",
                        "parameterSpace": {
                            "taskParameterDefinitions": [
                                {"name": "V", "type": task_type, "range": f"{{{{{ref}.Items}}}}"}
                            ]
                        },
                        "script": {
                            "actions": {"onRun": {"command": "echo", "args": ["{{Task.Param.V}}"]}}
                        },
                    }
                ],
            },
            supported_extensions=["EXPR"],
        )
        return create_job(job_template=jt, job_parameter_values={})

    def test_empty_path_in_typed_range_rejected(self):
        # A LIST[PATH] parameter containing "" must not flow into the
        # instantiated Job's PATH task-parameter range.
        with pytest.raises(DecodeValidationError, match=r"must not be an empty string"):
            # LIST[PATH] has no template-scope Param.* (RFC 0005): the range
            # forwards the raw list[string] value via RawParam, as in Rust.
            self._create_with_typed_range("LIST[PATH]", "PATH", ["/a", "", "/b"], ref="RawParam")

    def test_valid_paths_in_typed_range_accepted(self):
        # Positive polarity: valid paths still instantiate.
        job = self._create_with_typed_range("LIST[PATH]", "PATH", ["/a", "/b"], ref="RawParam")
        steps = job.steps
        step = steps["S"] if isinstance(steps, dict) else steps[0]
        assert step.parameterSpace is not None
        tpd = step.parameterSpace.taskParameterDefinitions
        tp = tpd["V"] if isinstance(tpd, dict) else tpd[0]
        # The range forwards the RAW list[string] value (RawParam, RFC 0005):
        # raw values are the original unmapped strings, so no path-separator
        # normalization applies on any platform (unlike processed Param.*
        # path values, whose normalization test_lists.py covers).
        assert [str(v) for v in tp.range] == ["/a", "/b"]

    def test_empty_string_in_typed_string_range_accepted(self):
        # No over-rejection: STRING task parameters legitimately allow "".
        job = self._create_with_typed_range("LIST[STRING]", "STRING", ["a", "", "b"])
        steps = job.steps
        step = steps["S"] if isinstance(steps, dict) else steps[0]
        assert step.parameterSpace is not None
        tpd = step.parameterSpace.taskParameterDefinitions
        tp = tpd["V"] if isinstance(tpd, dict) else tpd[0]
        assert [str(v) for v in tp.range] == ["a", "", "b"]


class TestTypedRangeElementSemantics:
    """RFC 0006 typed whole-field ranges must preserve element type variants
    and enforce element/target agreement, matching openjd-rs's per-variant
    checks in create_job (ranges.rs): an INT range accepts only int elements,
    a FLOAT range accepts int or float, and STRING/PATH ranges take each
    element's spec display form (bool renders true/false, a nested list
    "[1, 2]"). Without this, unwrapping the engine list erased the variants —
    a LIST[BOOL] parameter silently produced 1/0 task values that the Rust
    implementation rejects outright.
    """

    def _create(self, list_type, task_type, default):
        jt = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "T",
                "extensions": ["EXPR"],
                "parameterDefinitions": [{"name": "Items", "type": list_type, "default": default}],
                "steps": [
                    {
                        "name": "S",
                        "parameterSpace": {
                            "taskParameterDefinitions": [
                                {"name": "V", "type": task_type, "range": "{{Param.Items}}"}
                            ]
                        },
                        "script": {
                            "actions": {"onRun": {"command": "echo", "args": ["{{Task.Param.V}}"]}}
                        },
                    }
                ],
            },
            supported_extensions=["EXPR"],
        )
        return create_job(job_template=jt, job_parameter_values={})

    def _range_of(self, job):
        steps = job.steps
        step = steps["S"] if isinstance(steps, dict) else steps[0]
        tpd = step.parameterSpace.taskParameterDefinitions
        tp = tpd["V"] if isinstance(tpd, dict) else tpd[0]
        return [str(v) for v in tp.range]

    @pytest.mark.parametrize(
        "list_type, task_type, default, message",
        [
            pytest.param(
                "LIST[BOOL]",
                "INT",
                [True, False],
                r"Expected int in range, got bool",
                id="bool-into-int",
            ),
            pytest.param(
                "LIST[BOOL]",
                "FLOAT",
                [True, False],
                r"Expected float in range, got bool",
                id="bool-into-float",
            ),
            pytest.param(
                "LIST[STRING]",
                "INT",
                ["1", "2"],
                r"Expected int in range, got string",
                id="string-into-int",
            ),
            pytest.param(
                "LIST[FLOAT]",
                "INT",
                [1.5, 2.5],
                r"Expected int in range, got float",
                id="float-into-int",
            ),
            pytest.param(
                "LIST[LIST[INT]]",
                "INT",
                [[1, 2], [3]],
                r"Expected int in range, got list",
                id="nested-list-into-int",
            ),
        ],
    )
    def test_mismatched_elements_rejected(self, list_type, task_type, default, message):
        with pytest.raises(DecodeValidationError, match=message):
            self._create(list_type, task_type, default)

    def test_bool_into_string_range_uses_display_form(self):
        # Matches Rust to_display_string: true/false, not Python's True/False
        # or the int 1/0 the erased-variant path produced.
        assert self._range_of(self._create("LIST[BOOL]", "STRING", [True, False])) == [
            "true",
            "false",
        ]

    def test_nested_list_into_string_range_uses_display_form(self):
        assert self._range_of(self._create("LIST[LIST[INT]]", "STRING", [[1, 2], [3]])) == [
            "[1, 2]",
            "[3]",
        ]

    def test_int_into_float_range_accepted(self):
        # Rust's resolve_float_range accepts Int elements.
        assert self._range_of(self._create("LIST[INT]", "FLOAT", [1, 2])) == ["1", "2"]

    @pytest.mark.parametrize(
        "list_type, task_type, default, expected",
        [
            pytest.param("LIST[INT]", "INT", [1, 2, 3], ["1", "2", "3"], id="int-int"),
            pytest.param("LIST[STRING]", "STRING", ["a", "b"], ["a", "b"], id="string-string"),
        ],
    )
    def test_matching_elements_accepted(self, list_type, task_type, default, expected):
        assert self._range_of(self._create(list_type, task_type, default)) == expected
