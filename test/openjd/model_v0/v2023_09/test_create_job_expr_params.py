# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for instantiating a Job from a template that declares EXPR-extension
job parameter types (RFC 0007): BOOL, RANGE_EXPR, and the LIST[*] variants.

These exercise the pure-Python v0 ``create_job`` path, which previously could
only handle the original scalar types. The new types carry their values
natively (lists/bools) into the instantiated ``JobParameter`` so the typed EXPR
symbol table can coerce them.
"""

import pytest

from openjd.model import (
    DecodeValidationError,
    create_job,
    decode_job_template,
    model_to_object,
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
