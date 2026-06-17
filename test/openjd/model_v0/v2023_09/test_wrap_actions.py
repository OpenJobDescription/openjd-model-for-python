# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for WRAP_ACTIONS (RFC 0008) model validation on EnvironmentActions.

Covers the structural rules enforced at decode/`check` time: extension gating,
the EXPR hard prerequisite, all-or-nothing wrap hooks, and the at-least-one
action rule. Runtime interception and precise per-hook variable scoping live in
the sessions runtime and are out of scope here.
"""

import pytest

from openjd.model import DecodeValidationError, decode_environment_template

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
