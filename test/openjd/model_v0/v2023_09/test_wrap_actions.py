# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for WRAP_ACTIONS (RFC 0008) model validation on EnvironmentActions.

Covers the structural rules enforced at decode/`check` time: extension gating,
the EXPR hard prerequisite, all-or-nothing wrap hooks, and the at-least-one
action rule. Runtime interception and precise per-hook variable scoping live in
the sessions runtime and are out of scope here.
"""

import pytest

from openjd.model import (
    DecodeValidationError,
    decode_environment_template,
    decode_job_template,
)

_ALL_EXTS = ["TASK_CHUNKING", "REDACTED_ENV_VARS", "FEATURE_BUNDLE_1", "EXPR", "WRAP_ACTIONS"]


def _env_template(actions, *, extensions):
    tmpl = {
        "specificationVersion": "environment-2023-09",
        "environment": {"name": "WrapEnv", "script": {"actions": actions}},
    }
    if extensions:
        tmpl["extensions"] = list(extensions)
    return tmpl


def _cmd(arg):
    return {"command": "echo", "args": [arg]}


_ALL_THREE = {
    "onWrapEnvEnter": _cmd("wrap-enter {{WrappedEnv.Name}}"),
    "onWrapTaskRun": _cmd("wrap-task {{WrappedAction.Command}}"),
    "onWrapEnvExit": _cmd("wrap-exit {{WrappedEnv.Name}}"),
}


def _decode(template, extensions=_ALL_EXTS):
    return decode_environment_template(template=template, supported_extensions=extensions)


class TestWrapActionsValid:
    def test_all_three_hooks_ok(self):
        tmpl = _env_template(dict(_ALL_THREE), extensions=["WRAP_ACTIONS", "EXPR"])
        _decode(tmpl)

    def test_wrap_with_onenter_onexit_ok(self):
        actions = dict(_ALL_THREE)
        actions["onEnter"] = _cmd("entered")
        actions["onExit"] = _cmd("exited")
        _decode(_env_template(actions, extensions=["WRAP_ACTIONS", "EXPR"]))

    def test_non_wrap_env_unchanged(self):
        # Legacy behaviour: an env with only onEnter still validates and does
        # not require WRAP_ACTIONS/EXPR.
        _decode(_env_template({"onEnter": _cmd("hi")}, extensions=[]))


class TestWrapActionsInvalid:
    def test_all_or_nothing_missing_one(self):
        actions = dict(_ALL_THREE)
        del actions["onWrapEnvExit"]
        with pytest.raises(DecodeValidationError, match="all of onWrapEnvEnter"):
            _decode(_env_template(actions, extensions=["WRAP_ACTIONS", "EXPR"]))

    def test_only_one_wrap_hook(self):
        actions = {"onWrapTaskRun": _cmd("only {{WrappedAction.Command}}")}
        with pytest.raises(DecodeValidationError, match="all of onWrapEnvEnter"):
            _decode(_env_template(actions, extensions=["WRAP_ACTIONS", "EXPR"]))

    def test_wrap_requires_extension(self):
        with pytest.raises(DecodeValidationError, match="require the WRAP_ACTIONS extension"):
            _decode(_env_template(dict(_ALL_THREE), extensions=["EXPR"]))

    def test_wrap_requires_expr(self):
        with pytest.raises(DecodeValidationError, match="requires the EXPR extension"):
            _decode(_env_template(dict(_ALL_THREE), extensions=["WRAP_ACTIONS"]))

    def test_empty_actions_rejected(self):
        with pytest.raises(DecodeValidationError):
            _decode(_env_template({}, extensions=["WRAP_ACTIONS", "EXPR"]))


# ── RFC 0008 single-wrap-layer rule (JobTemplate) ──────────────────────
#
# A session's environment stack is the job's jobEnvironments plus exactly one
# step's stepEnvironments, so at most one wrap-defining environment may be
# reachable in any single session. Mirrors openjd-rs
# validate_v2023_09/wrap_actions.rs.


def _wrap_env(name):
    return {"name": name, "script": {"actions": dict(_ALL_THREE)}}


def _plain_step(name, *, step_environments=None):
    step = {"name": name, "script": {"actions": {"onRun": _cmd("hi")}}}
    if step_environments is not None:
        step["stepEnvironments"] = step_environments
    return step


def _job_template(*, job_environments=None, steps=None, extensions=("WRAP_ACTIONS", "EXPR")):
    tmpl = {
        "specificationVersion": "jobtemplate-2023-09",
        "name": "T",
        "steps": steps or [_plain_step("S")],
    }
    if job_environments is not None:
        tmpl["jobEnvironments"] = job_environments
    if extensions:
        tmpl["extensions"] = list(extensions)
    return tmpl


def _decode_job(template, extensions=_ALL_EXTS):
    return decode_job_template(template=template, supported_extensions=extensions)


class TestSingleWrapLayerValid:
    def test_single_job_env_wrap_ok(self):
        _decode_job(_job_template(job_environments=[_wrap_env("W")]))

    def test_single_step_env_wrap_ok(self):
        _decode_job(_job_template(steps=[_plain_step("S", step_environments=[_wrap_env("W")])]))

    def test_wrap_envs_in_different_steps_ok(self):
        # Two steps, each with its own single wrap env, and no job-env wrap:
        # each session has exactly one wrap layer, so this is valid.
        _decode_job(
            _job_template(
                steps=[
                    _plain_step("S1", step_environments=[_wrap_env("W1")]),
                    _plain_step("S2", step_environments=[_wrap_env("W2")]),
                ]
            )
        )

    def test_non_wrap_job_envs_unaffected(self):
        # Plenty of non-wrap job environments are fine.
        envs = [
            {"name": "E1", "script": {"actions": {"onEnter": _cmd("a")}}},
            {"name": "E2", "script": {"actions": {"onEnter": _cmd("b")}}},
        ]
        _decode_job(_job_template(job_environments=envs))


class TestSingleWrapLayerInvalid:
    def test_two_job_env_wraps_rejected(self):
        with pytest.raises(
            DecodeValidationError, match="only one environment in the session stack"
        ):
            _decode_job(_job_template(job_environments=[_wrap_env("W1"), _wrap_env("W2")]))

    def test_job_env_plus_step_env_wrap_rejected(self):
        # One wrap env in jobEnvironments + one in a step's stepEnvironments =
        # two wrap layers in that step's session.
        with pytest.raises(
            DecodeValidationError, match="only one environment in the session stack"
        ):
            _decode_job(
                _job_template(
                    job_environments=[_wrap_env("W1")],
                    steps=[_plain_step("S", step_environments=[_wrap_env("W2")])],
                )
            )

    def test_two_wraps_in_one_step_rejected(self):
        with pytest.raises(
            DecodeValidationError, match="only one environment in the session stack"
        ):
            _decode_job(
                _job_template(
                    steps=[_plain_step("S", step_environments=[_wrap_env("W1"), _wrap_env("W2")])]
                )
            )

    def test_single_layer_not_enforced_without_extension(self):
        # Without WRAP_ACTIONS the wrap fields are rejected for a different
        # reason (extension gating), so the template still fails — but the
        # single-layer rule itself is only active under WRAP_ACTIONS.
        with pytest.raises(DecodeValidationError):
            _decode_job(
                _job_template(
                    job_environments=[_wrap_env("W1"), _wrap_env("W2")],
                    extensions=(),
                )
            )


# ── RFC 0008 per-hook wrapped-variable scoping ─────────────────────────
#
# WrappedAction.* may be referenced only in the three wrap hooks; WrappedEnv.*
# only in onWrapEnvEnter/onWrapEnvExit; WrappedStep.* only in onWrapTaskRun;
# and none of them in the ordinary onEnter/onExit actions.


class TestWrappedVariableScopeValid:
    def test_in_scope_references_ok(self):
        # _ALL_THREE already uses WrappedEnv.Name in the env enter/exit hooks
        # and WrappedAction.Command in the task-run hook — all in scope.
        _decode(_env_template(dict(_ALL_THREE), extensions=["WRAP_ACTIONS", "EXPR"]))

    def test_wrapped_step_in_task_run_ok(self):
        actions = dict(_ALL_THREE)
        actions["onWrapTaskRun"] = _cmd("run {{WrappedStep.Name}} {{WrappedAction.Command}}")
        _decode(_env_template(actions, extensions=["WRAP_ACTIONS", "EXPR"]))


class TestWrappedVariableScopeInvalid:
    def test_wrapped_action_in_on_enter_rejected(self):
        actions = dict(_ALL_THREE)
        actions["onEnter"] = _cmd("setup {{WrappedAction.Command}}")
        with pytest.raises(DecodeValidationError, match=r"WrappedAction\.\* variables may not"):
            _decode(_env_template(actions, extensions=["WRAP_ACTIONS", "EXPR"]))

    def test_wrapped_env_in_on_exit_rejected(self):
        actions = dict(_ALL_THREE)
        actions["onExit"] = _cmd("teardown {{WrappedEnv.Name}}")
        with pytest.raises(DecodeValidationError, match=r"WrappedEnv\.\* variables may not"):
            _decode(_env_template(actions, extensions=["WRAP_ACTIONS", "EXPR"]))

    def test_wrapped_step_in_env_enter_rejected(self):
        actions = dict(_ALL_THREE)
        actions["onWrapEnvEnter"] = _cmd("{{WrappedStep.Name}}")
        with pytest.raises(DecodeValidationError, match=r"WrappedStep\.\* variables may not"):
            _decode(_env_template(actions, extensions=["WRAP_ACTIONS", "EXPR"]))

    def test_wrapped_env_in_task_run_rejected(self):
        actions = dict(_ALL_THREE)
        actions["onWrapTaskRun"] = _cmd("{{WrappedEnv.Name}}")
        with pytest.raises(DecodeValidationError, match=r"WrappedEnv\.\* variables may not"):
            _decode(_env_template(actions, extensions=["WRAP_ACTIONS", "EXPR"]))
