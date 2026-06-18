# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for EXPR `let` bindings (RFC 0007 §3.6), Step.Name in step
environments, host-context function scoping, and type-aware expression
validation."""

import pytest

from openjd.model import DecodeValidationError, decode_job_template

_EXTS = ["EXPR", "FEATURE_BUNDLE_1"]


def _decode(template):
    return decode_job_template(template=template, supported_extensions=_EXTS)


def _job(steps, *, params=None, extensions=("EXPR",)):
    t = {"specificationVersion": "jobtemplate-2023-09", "name": "T", "steps": steps}
    if params is not None:
        t["parameterDefinitions"] = params
    if extensions:
        t["extensions"] = list(extensions)
    return t


def _onrun(arg):
    return {"actions": {"onRun": {"command": "echo", "args": [arg]}}}


class TestLetValid:
    def test_step_let_visible_in_script(self):
        _decode(
            _job(
                [{"name": "S", "let": ["x = 1", "y = x + 1"], "script": _onrun("{{y}}")}],
            )
        )

    def test_script_let(self):
        _decode(
            _job([{"name": "S", "script": {"let": ["a = 2"], **_onrun("{{a}}")}}]),
        )

    def test_chained_and_functions(self):
        _decode(
            _job(
                [
                    {
                        "name": "S",
                        "let": ["total = sum(Param.Items)", "n = len(Param.Items)"],
                        "script": _onrun("{{total}}-{{n}}"),
                    }
                ],
                params=[{"name": "Items", "type": "LIST[INT]", "default": [1, 2, 3]}],
            )
        )


class TestLetInvalid:
    def test_requires_expr(self):
        with pytest.raises(DecodeValidationError, match="requires the EXPR extension"):
            _decode(_job([{"name": "S", "let": ["x = 1"], "script": _onrun("hi")}], extensions=()))

    def test_empty(self):
        with pytest.raises(DecodeValidationError, match="at least one"):
            _decode(_job([{"name": "S", "let": [], "script": _onrun("hi")}]))

    def test_duplicate_name(self):
        with pytest.raises(DecodeValidationError, match="unique"):
            _decode(_job([{"name": "S", "let": ["x = 1", "x = 2"], "script": _onrun("hi")}]))

    def test_too_many(self):
        many = [f"v{i} = {i}" for i in range(51)]
        with pytest.raises(DecodeValidationError, match="at most"):
            _decode(_job([{"name": "S", "let": many, "script": _onrun("hi")}]))

    def test_uppercase_name(self):
        with pytest.raises(DecodeValidationError, match="identifier"):
            _decode(_job([{"name": "S", "let": ["Foo = 1"], "script": _onrun("hi")}]))

    def test_shadow_enclosing(self):
        with pytest.raises(DecodeValidationError, match="shadows"):
            _decode(
                _job(
                    [
                        {
                            "name": "S",
                            "let": ["x = 1"],
                            "script": {"let": ["x = 2"], **_onrun("hi")},
                        }
                    ]
                )
            )

    def test_comprehension_shadows_let(self):
        with pytest.raises(DecodeValidationError, match="shadows"):
            _decode(
                _job(
                    [
                        {
                            "name": "S",
                            "let": ["x = 10"],
                            "script": _onrun("{{ [x for x in Param.Items] }}"),
                        }
                    ],
                    params=[{"name": "Items", "type": "LIST[INT]", "default": [1, 2]}],
                )
            )


class TestStepName:
    def test_step_name_in_step_environment_with_expr(self):
        _decode(
            _job(
                [
                    {
                        "name": "Render",
                        "stepEnvironments": [
                            {"name": "Setup", "variables": {"CUR": "{{ Step.Name }}"}}
                        ],
                        "script": _onrun("hi"),
                    }
                ]
            )
        )

    def test_step_name_requires_expr(self):
        with pytest.raises(DecodeValidationError):
            _decode(
                _job(
                    [
                        {
                            "name": "Render",
                            "stepEnvironments": [
                                {"name": "Setup", "variables": {"CUR": "{{ Step.Name }}"}}
                            ],
                            "script": _onrun("hi"),
                        }
                    ],
                    extensions=(),
                )
            )


class TestHostContextScope:
    def test_apply_path_mapping_in_job_name_rejected(self):
        with pytest.raises(DecodeValidationError, match="only available at runtime"):
            _decode(
                _job([{"name": "S", "script": _onrun("hi")}])
                | {"name": "{{ apply_path_mapping('/x') }}"}
            )

    def test_apply_path_mapping_in_task_arg_ok(self):
        _decode(_job([{"name": "S", "script": _onrun("{{ apply_path_mapping('/x') }}")}]))


class TestSymbolTyping:
    def test_path_method_access(self):
        _decode(
            _job(
                [{"name": "S", "script": _onrun("{{ Param.File.name }}")}],
                params=[{"name": "File", "type": "PATH", "default": "/a/b.exr"}],
            )
        )

    def test_string_type_mismatch_rejected(self):
        with pytest.raises(DecodeValidationError):
            _decode(
                _job(
                    [{"name": "S", "script": _onrun("{{ Param.Name + 1 }}")}],
                    params=[{"name": "Name", "type": "STRING", "default": "hi"}],
                )
            )
