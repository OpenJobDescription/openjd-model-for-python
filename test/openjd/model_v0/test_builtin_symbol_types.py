# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Static EXPR typing of runtime-injected built-in symbols.

openjd-rs validates expressions against typed symtabs containing the
built-ins (format_strings.rs build_task_scope_symtab: Job.Name/Step.Name are
strings, Session.WorkingDirectory a path, ...; add_wrapped_action_scope types
the nullable forwarding symbols as ``int?``/``string?`` unions). Without the
same typing, Python accepted expressions like ``Job.Name + 1`` that only
failed on a worker.
"""

import pytest

from openjd.model import DecodeValidationError, decode_job_template

EXT = ["EXPR", "WRAP_ACTIONS", "FEATURE_BUNDLE_1"]
RUN = {"actions": {"onRun": {"command": "echo"}}}


def _decode(t):
    return decode_job_template(template=t, supported_extensions=EXT)


def _job(**overrides):
    t = {
        "specificationVersion": "jobtemplate-2023-09",
        "extensions": EXT,
        "name": "T",
        "steps": [{"name": "S", "script": RUN}],
    }
    t.update(overrides)
    return t


def _step_arg(expr):
    return [{"name": "S", "script": {"actions": {"onRun": {"command": "echo", "args": [expr]}}}}]


class TestBuiltinSymbolTyping:
    @pytest.mark.parametrize(
        "expr",
        [
            pytest.param("{{ Job.Name + 1 }}", id="job-name-plus-int"),
            pytest.param("{{ Session.WorkingDirectory + 1 }}", id="workdir-plus-int"),
            pytest.param("{{ Step.Name + 1 }}", id="step-name-plus-int"),
        ],
    )
    def test_invalid_builtin_expressions_rejected(self, expr):
        with pytest.raises(DecodeValidationError, match=r"Cannot use '\+' operator"):
            _decode(_job(steps=_step_arg(expr)))

    def test_wrapped_action_command_plus_int_rejected(self):
        t = _job(
            jobEnvironments=[
                {
                    "name": "W",
                    "script": {
                        "actions": {
                            "onWrapEnvEnter": {
                                "command": "echo",
                                "args": ["{{ WrappedAction.Command + 1 }}"],
                            },
                            "onWrapTaskRun": {"command": "echo"},
                            "onWrapEnvExit": {"command": "echo"},
                        }
                    },
                }
            ]
        )
        with pytest.raises(DecodeValidationError, match=r"Cannot use '\+' operator"):
            _decode(t)

    def test_step_let_binding_rhs_is_type_checked(self):
        t = _job(steps=[{"name": "S", "let": ["x = Step.Name + 1"], "script": RUN}])
        with pytest.raises(DecodeValidationError, match=r"Cannot use '\+' operator"):
            _decode(t)

    @pytest.mark.parametrize(
        "expr",
        [
            pytest.param("{{ Job.Name + '-suffix' }}", id="string-concat"),
            pytest.param("{{ Session.WorkingDirectory }}/out.exr", id="workdir-plain"),
            pytest.param("{{ Session.WorkingDirectory.name }}", id="workdir-path-property"),
        ],
    )
    def test_valid_builtin_expressions_accepted(self, expr):
        _decode(_job(steps=_step_arg(expr)))

    def test_full_wrap_forwarding_still_accepted(self):
        # The nullable typed symbols (int?/string?) must not over-reject the
        # RFC 0008 round-trip forwarding case.
        t = _job(
            jobEnvironments=[
                {
                    "name": "W",
                    "script": {
                        "actions": {
                            "onWrapEnvEnter": {
                                "command": "{{WrappedAction.Command}}",
                                "args": ["{{ WrappedEnv.Name }}"],
                                "timeout": "{{WrappedAction.Timeout}}",
                                "cancelation": {
                                    "mode": "{{WrappedAction.Cancelation.Mode}}",
                                    "notifyPeriodInSeconds": "{{WrappedAction.Cancelation.NotifyPeriodInSeconds}}",
                                },
                            },
                            "onWrapTaskRun": {
                                "command": "run",
                                "args": [
                                    "{{WrappedStep.Name}}",
                                    "{{ repr_sh(WrappedAction.Args) }}",
                                ],
                            },
                            "onWrapEnvExit": {"command": "exit"},
                        }
                    },
                }
            ]
        )
        _decode(t)
