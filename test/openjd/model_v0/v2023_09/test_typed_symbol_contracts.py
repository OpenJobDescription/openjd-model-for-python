# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""PATH/LIST[PATH] symbol contracts and per-step typed expression validation.

RFC 0005 "Job Parameter Types": processed ``Param.*`` values for path-typed
parameters are ``path``/``list[path]`` with path mapping applied and exist
only at host/session scope; ``RawParam.*`` values are template-scope
``string``/``list[string]``. Template validation types symbols per defining
model (per step for task parameters), mirroring openjd-rs's
``build_param_symtab``/``build_task_scope_symtab`` (format_strings.rs).
"""

import pytest

from openjd.model import DecodeValidationError, create_job, decode_job_template

EXT = ["EXPR"]
_RUN = {"actions": {"onRun": {"command": "echo"}}}


def _decode(t):
    return decode_job_template(template=t, supported_extensions=EXT)


def _base(**overrides):
    t = {
        "specificationVersion": "jobtemplate-2023-09",
        "extensions": EXT,
        "name": "T",
        "steps": [{"name": "S", "script": _RUN}],
    }
    t.update(overrides)
    return t


def _step_with_task_param(name, tp_type, arg_expr, param_name="File", range_=None):
    if range_ is None:
        range_ = [1, 2] if tp_type == "INT" else (["/a"] if tp_type == "PATH" else ["a"])
    return {
        "name": name,
        "parameterSpace": {
            "taskParameterDefinitions": [{"name": param_name, "type": tp_type, "range": range_}]
        },
        "script": {"actions": {"onRun": {"command": "echo", "args": [arg_expr]}}},
    }


class TestPerStepTaskParameterTyping:
    """Task.Param.*/Task.RawParam.* references are type-checked per step."""

    def test_raw_path_property_access_rejected(self):
        # Task.RawParam.<PATH> is a string (raw, unmapped) — path properties
        # are unavailable. Rust rejects this at check; previously Python only
        # failed at session evaluation.
        t = _base(steps=[_step_with_task_param("S", "PATH", "{{ Task.RawParam.File.name }}")])
        with pytest.raises(DecodeValidationError, match=r"'name' property is not available"):
            _decode(t)

    def test_processed_path_property_access_accepted(self):
        t = _base(steps=[_step_with_task_param("S", "PATH", "{{ Task.Param.File.name }}")])
        _decode(t)

    def test_int_task_param_path_property_rejected(self):
        t = _base(
            steps=[
                _step_with_task_param("S", "INT", "{{ Task.Param.Frame.name }}", param_name="Frame")
            ]
        )
        with pytest.raises(DecodeValidationError, match=r"not available for int"):
            _decode(t)

    def test_same_name_different_types_validate_per_step(self):
        # Two steps define task param "File": PATH in step A (property access
        # valid), STRING in step B (invalid). Only step B may error —
        # per-step type separation, as in Rust.
        t = _base(
            steps=[
                _step_with_task_param("A", "PATH", "{{ Task.Param.File.name }}"),
                _step_with_task_param("B", "STRING", "{{ Task.Param.File.name }}"),
            ]
        )
        with pytest.raises(DecodeValidationError) as exc_info:
            _decode(t)
        message = str(exc_info.value)
        assert "steps[1]" in message
        assert "steps[0]" not in message

    def test_let_name_mixed_with_typed_task_param_falls_back(self):
        # An expression touching an untyped (let-bound) name falls back to
        # name-only validation — no false rejection.
        t = _base(
            steps=[
                {
                    "name": "S",
                    "parameterSpace": {
                        "taskParameterDefinitions": [
                            {"name": "Frame", "type": "INT", "range": [1, 2]}
                        ]
                    },
                    "script": {
                        "let": ["msg = 'x'"],
                        "actions": {
                            "onRun": {
                                "command": "echo",
                                "args": ["{{ msg + Task.Param.Frame }}"],
                            }
                        },
                    },
                }
            ]
        )
        _decode(t)


class TestJobParameterRawPathTyping:
    """RawParam.<PATH> is a plain string at template scope."""

    def _job(self, name_expr):
        return _base(
            name=name_expr,
            parameterDefinitions=[{"name": "In", "type": "PATH", "default": "/x/y.exr"}],
        )

    def test_raw_path_property_access_rejected(self):
        with pytest.raises(DecodeValidationError, match=r"'name' property is not available"):
            _decode(self._job("{{ RawParam.In.name }}"))

    def test_raw_path_string_method_accepted(self):
        # Previously falsely rejected: RawParam.<PATH> was mistyped "path".
        _decode(self._job("{{ RawParam.In.upper() }}"))


class TestListPathScopeContract:
    """Param.<LIST[PATH]> is session-scope only; RawParam is list[string]."""

    def _job(self, **overrides):
        return _base(
            parameterDefinitions=[
                {"name": "Paths", "type": "LIST[PATH]", "default": ["/a/x.exr", "/b/y.exr"]}
            ],
            **overrides,
        )

    def test_processed_rejected_at_template_scope(self):
        # The job name resolves at template scope, where the processed
        # (path-mapped) value cannot exist. Rust: "Undefined variable ...
        # Did you mean: RawParam.Paths".
        t = self._job(name="{{ Param.Paths[0].name }}")
        with pytest.raises(DecodeValidationError, match=r"Param\.Paths does not exist"):
            _decode(t)

    def test_processed_accepted_at_session_scope(self):
        t = self._job(
            steps=[
                {
                    "name": "S",
                    "script": {
                        "actions": {"onRun": {"command": "echo", "args": ["{{ Param.Paths[0] }}"]}}
                    },
                }
            ]
        )
        _decode(t)

    def test_raw_list_path_items_are_strings(self):
        # string methods available; path properties not.
        _decode(self._job(name="{{ RawParam.Paths[0].upper() }}"))
        with pytest.raises(DecodeValidationError, match=r"'name' property is not available"):
            _decode(self._job(name="{{ RawParam.Paths[0].name }}"))

    def test_create_job_seeds_raw_only(self):
        # create_job must not seed a template-scope Param.* for LIST[PATH];
        # a typed range forwards the raw list[string] via RawParam.
        t = self._job(
            steps=[
                {
                    "name": "S",
                    "parameterSpace": {
                        "taskParameterDefinitions": [
                            {"name": "P", "type": "PATH", "range": "{{RawParam.Paths}}"}
                        ]
                    },
                    "script": _RUN,
                }
            ]
        )
        job = create_job(job_template=_decode(t), job_parameter_values={})
        steps = job.steps
        step = steps["S"] if isinstance(steps, dict) else steps[0]
        tpd = step.parameterSpace.taskParameterDefinitions
        tp = tpd["P"] if isinstance(tpd, dict) else tpd[0]
        assert len(tp.range) == 2
