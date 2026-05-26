# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the structural template-time pyclasses (resolves
report finding #11 part 2).

The Rust types in ``openjd_model::template`` (``StepTemplate``,
``Environment``, ``Action``, ``EnvironmentScript``, etc.) are
mirrored 1:1 as pyclasses under ``openjd.model._v1.template``. The
classes that collide with their job-time counterparts in
``openjd.model._v1.job`` (``Action``, ``Environment``,
``CancelationMode``, etc.) are exposed under both their short name
and a ``Template``-prefixed alias.
"""

import pickle

import pytest

from openjd.expr import FormatString
from openjd.model._v1 import decode_environment_template, decode_job_template
from openjd.model._v1.template import (
    Action,
    AmountRequirement,
    AttributeRequirement,
    CancelationMode,
    EmbeddedFile,
    Environment,
    EnvironmentActions,
    EnvironmentScript,
    EnvironmentTemplate,
    HostRequirements,
    JobTemplate,
    SimpleAction,
    StepActions,
    StepDependency,
    StepScript,
    StepTemplate,
    TemplateAction,
    TemplateCancelationMode,
    TemplateEmbeddedFile,
    TemplateEnvironment,
    TemplateEnvironmentActions,
    TemplateEnvironmentScript,
    TemplateStepActions,
    TemplateStepDependency,
    TemplateStepScript,
)


def _job_template(**overrides) -> JobTemplate:
    template = {
        "specificationVersion": "jobtemplate-2023-09",
        "name": "T",
        "steps": [
            {
                "name": "S",
                "script": {"actions": {"onRun": {"command": "echo"}}},
            }
        ],
    }
    template.update(overrides)
    return decode_job_template(template=template)


class TestShortAliasIdentity:
    """The short-alias names are the same Python class object as the
    Template-prefixed pyclasses they alias."""

    @pytest.mark.parametrize(
        ("short", "prefixed"),
        [
            (Action, TemplateAction),
            (CancelationMode, TemplateCancelationMode),
            (EmbeddedFile, TemplateEmbeddedFile),
            (Environment, TemplateEnvironment),
            (EnvironmentActions, TemplateEnvironmentActions),
            (EnvironmentScript, TemplateEnvironmentScript),
            (StepActions, TemplateStepActions),
            (StepDependency, TemplateStepDependency),
            (StepScript, TemplateStepScript),
        ],
    )
    def test_alias_is_same_class(self, short, prefixed):
        assert short is prefixed


class TestJobTemplateAccessors:
    def test_steps_returns_step_templates(self):
        t = _job_template()
        steps = t.steps
        assert len(steps) == 1
        assert isinstance(steps[0], StepTemplate)
        assert steps[0].name == "S"

    def test_steps_with_multiple(self):
        t = _job_template(
            steps=[
                {"name": "A", "script": {"actions": {"onRun": {"command": "echo"}}}},
                {
                    "name": "B",
                    "dependencies": [{"dependsOn": "A"}],
                    "script": {"actions": {"onRun": {"command": "echo"}}},
                },
            ]
        )
        assert [s.name for s in t.steps] == ["A", "B"]

    def test_job_environments_none_when_absent(self):
        t = _job_template()
        assert t.job_environments is None
        assert t.jobEnvironments is None  # camelCase alias

    def test_job_environments_with_envs(self):
        t = _job_template(
            jobEnvironments=[
                {"name": "Env1", "variables": {"X": "1"}},
                {"name": "Env2", "variables": {"Y": "2"}},
            ]
        )
        envs = t.jobEnvironments
        assert envs is not None
        assert len(envs) == 2
        assert all(isinstance(e, Environment) for e in envs)
        assert [e.name for e in envs] == ["Env1", "Env2"]

    def test_job_environments_camelcase_alias(self):
        t = _job_template(
            jobEnvironments=[
                {"name": "Env1", "variables": {"X": "1"}},
            ]
        )
        assert t.job_environments is not None
        assert t.jobEnvironments is not None
        # Same content (each call constructs new pyclass instances —
        # we don't require identity, just structural equality of names)
        assert [e.name for e in t.job_environments] == [e.name for e in t.jobEnvironments]


class TestEnvironmentTemplateAccessors:
    def test_environment_accessor(self):
        et = decode_environment_template(
            template={
                "specificationVersion": "environment-2023-09",
                "environment": {"name": "EnvX", "variables": {"K": "v"}},
            }
        )
        assert isinstance(et, EnvironmentTemplate)
        e = et.environment
        assert isinstance(e, Environment)
        assert e.name == "EnvX"


class TestStepTemplate:
    def test_basic_fields(self):
        t = _job_template(
            steps=[
                {
                    "name": "S",
                    "description": "a step",
                    "script": {"actions": {"onRun": {"command": "echo"}}},
                }
            ]
        )
        s = t.steps[0]
        assert s.name == "S"
        assert s.description == "a step"
        assert s.let_bindings is None
        assert s.dependencies is None
        assert s.host_requirements is None

    def test_dependencies(self):
        t = _job_template(
            steps=[
                {"name": "A", "script": {"actions": {"onRun": {"command": "echo"}}}},
                {
                    "name": "B",
                    "dependencies": [{"dependsOn": "A"}],
                    "script": {"actions": {"onRun": {"command": "echo"}}},
                },
            ]
        )
        deps = t.steps[1].dependencies
        assert deps is not None
        assert len(deps) == 1
        assert isinstance(deps[0], StepDependency)
        assert deps[0].depends_on == "A"
        assert deps[0].dependsOn == "A"  # camelCase alias

    def test_host_requirements(self):
        t = _job_template(
            steps=[
                {
                    "name": "S",
                    "hostRequirements": {
                        "amounts": [{"name": "amount.worker.vcpu", "min": "4", "max": "8"}],
                        "attributes": [
                            {"name": "attr.worker.os.family", "anyOf": ["linux"]},
                            {"name": "attr.worker.cpu.arch", "allOf": ["x86_64"]},
                        ],
                    },
                    "script": {"actions": {"onRun": {"command": "echo"}}},
                }
            ]
        )
        s = t.steps[0]
        hr = s.host_requirements
        assert isinstance(hr, HostRequirements)
        # amounts
        amts = hr.amounts
        assert amts is not None and len(amts) == 1
        assert isinstance(amts[0], AmountRequirement)
        assert amts[0].name == "amount.worker.vcpu"
        assert isinstance(amts[0].min, FormatString)
        assert amts[0].min.raw() == "4"
        assert amts[0].max.raw() == "8"
        # attributes
        attrs = hr.attributes
        assert attrs is not None and len(attrs) == 2
        assert isinstance(attrs[0], AttributeRequirement)
        assert attrs[0].name == "attr.worker.os.family"
        assert attrs[0].any_of[0].raw() == "linux"
        assert attrs[0].anyOf[0].raw() == "linux"  # camelCase alias
        assert attrs[1].all_of[0].raw() == "x86_64"

    def test_step_environments(self):
        t = _job_template(
            steps=[
                {
                    "name": "S",
                    "stepEnvironments": [{"name": "StepEnv", "variables": {"Y": "2"}}],
                    "script": {"actions": {"onRun": {"command": "echo"}}},
                }
            ]
        )
        s = t.steps[0]
        ses = s.step_environments
        assert ses is not None and len(ses) == 1
        assert isinstance(ses[0], Environment)
        assert ses[0].name == "StepEnv"

    def test_simple_action_sugar(self):
        t = (
            _job_template(
                extensions=["FEATURE_BUNDLE_1"],
                steps=[
                    {
                        "name": "S",
                        "bash": {"script": "echo hi"},
                    }
                ],
                supported_extensions=["FEATURE_BUNDLE_1"],
            )
            if False
            else decode_job_template(
                template={
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "T",
                    "extensions": ["FEATURE_BUNDLE_1"],
                    "steps": [
                        {
                            "name": "S",
                            "bash": {"script": "echo hi"},
                        }
                    ],
                },
                supported_extensions=["FEATURE_BUNDLE_1"],
            )
        )
        s = t.steps[0]
        assert s.script is None
        assert isinstance(s.bash, SimpleAction)
        assert s.bash.script == "echo hi"
        assert s.python is None


class TestEnvironment:
    def test_minimal(self):
        et = decode_environment_template(
            template={
                "specificationVersion": "environment-2023-09",
                "environment": {"name": "E", "variables": {"X": "1"}},
            }
        )
        e = et.environment
        assert e.name == "E"
        assert e.description is None
        assert e.script is None
        assert set(e.variables.keys()) == {"X"}
        assert e.variables["X"].raw() == "1"

    def test_with_script(self):
        et = decode_environment_template(
            template={
                "specificationVersion": "environment-2023-09",
                "environment": {
                    "name": "E",
                    "description": "an env",
                    "script": {
                        "actions": {"onEnter": {"command": "echo", "args": ["enter"]}},
                        "embeddedFiles": [{"name": "f", "type": "TEXT", "data": "hello"}],
                    },
                },
            }
        )
        e = et.environment
        assert e.description == "an env"
        assert isinstance(e.script, EnvironmentScript)
        assert isinstance(e.script.actions, EnvironmentActions)
        on_enter = e.script.actions.on_enter
        assert isinstance(on_enter, Action)
        assert on_enter.command.raw() == "echo"
        assert [a.raw() for a in on_enter.args] == ["enter"]


class TestStepScript:
    def test_actions_and_embedded_files(self):
        t = _job_template(
            steps=[
                {
                    "name": "S",
                    "script": {
                        "actions": {"onRun": {"command": "echo"}},
                        "embeddedFiles": [
                            {"name": "f", "type": "TEXT", "data": "hello"},
                        ],
                    },
                }
            ]
        )
        s = t.steps[0]
        assert isinstance(s.script, StepScript)
        assert isinstance(s.script.actions, StepActions)
        assert isinstance(s.script.actions.on_run, Action)
        files = s.script.embedded_files
        assert files is not None and len(files) == 1
        assert isinstance(files[0], EmbeddedFile)
        assert files[0].name == "f"
        assert files[0].type == "TEXT"
        assert files[0].data.raw() == "hello"


class TestAction:
    def test_minimal(self):
        t = _job_template()
        on_run = t.steps[0].script.actions.on_run
        assert on_run.command.raw() == "echo"
        assert on_run.args is None
        assert on_run.timeout is None
        assert on_run.cancelation is None

    def test_full(self):
        t = _job_template(
            steps=[
                {
                    "name": "S",
                    "script": {
                        "actions": {
                            "onRun": {
                                "command": "echo",
                                "args": ["a", "b"],
                                "timeout": "60",
                                "cancelation": {
                                    "mode": "NOTIFY_THEN_TERMINATE",
                                    "notifyPeriodInSeconds": "30",
                                },
                            }
                        }
                    },
                }
            ]
        )
        on_run = t.steps[0].script.actions.on_run
        assert on_run.command.raw() == "echo"
        assert [a.raw() for a in on_run.args] == ["a", "b"]
        assert on_run.timeout.raw() == "60"
        cm = on_run.cancelation
        assert isinstance(cm, CancelationMode)
        assert cm.mode == "NOTIFY_THEN_TERMINATE"
        assert cm.notify_period_in_seconds.raw() == "30"
        assert cm.notifyPeriodInSeconds.raw() == "30"  # camelCase alias


class TestCancelationMode:
    def test_terminate(self):
        cm = CancelationMode(mode="TERMINATE")
        assert cm.mode == "TERMINATE"
        assert cm.notify_period_in_seconds is None

    def test_notify_then_terminate(self):
        cm = CancelationMode(
            mode="NOTIFY_THEN_TERMINATE",
            notify_period_in_seconds=FormatString("30"),
        )
        assert cm.mode == "NOTIFY_THEN_TERMINATE"
        assert cm.notify_period_in_seconds.raw() == "30"

    def test_terminate_with_notify_period_raises(self):
        with pytest.raises(ValueError):
            CancelationMode(
                mode="TERMINATE",
                notify_period_in_seconds=FormatString("30"),
            )

    def test_unknown_mode_raises(self):
        with pytest.raises(ValueError):
            CancelationMode(mode="bogus")


class TestPickle:
    """Pickle round-trip for all the new pyclasses."""

    def test_step_dependency(self):
        sd = StepDependency(depends_on="Foo")
        loaded = pickle.loads(pickle.dumps(sd))
        assert loaded.depends_on == "Foo"

    def test_amount_requirement(self):
        ar = AmountRequirement(
            name="amount.worker.vcpu",
            min=FormatString("4"),
            max=FormatString("8"),
        )
        loaded = pickle.loads(pickle.dumps(ar))
        assert loaded.name == ar.name
        assert loaded.min.raw() == "4"
        assert loaded.max.raw() == "8"

    def test_attribute_requirement(self):
        ar = AttributeRequirement(
            name="attr.worker.os.family",
            any_of=[FormatString("linux")],
        )
        loaded = pickle.loads(pickle.dumps(ar))
        assert loaded.name == ar.name
        assert [v.raw() for v in loaded.any_of] == ["linux"]

    def test_cancelation_mode_terminate(self):
        cm = CancelationMode(mode="TERMINATE")
        loaded = pickle.loads(pickle.dumps(cm))
        assert loaded.mode == "TERMINATE"

    def test_cancelation_mode_notify_then_terminate(self):
        cm = CancelationMode(
            mode="NOTIFY_THEN_TERMINATE",
            notify_period_in_seconds=FormatString("30"),
        )
        loaded = pickle.loads(pickle.dumps(cm))
        assert loaded.mode == "NOTIFY_THEN_TERMINATE"
        assert loaded.notify_period_in_seconds.raw() == "30"

    def test_action(self):
        a = Action(
            command=FormatString("echo"),
            args=[FormatString("x")],
            timeout=FormatString("60"),
        )
        loaded = pickle.loads(pickle.dumps(a))
        assert loaded.command.raw() == "echo"
        assert [v.raw() for v in loaded.args] == ["x"]

    def test_embedded_file(self):
        ef = EmbeddedFile(
            name="f",
            type="TEXT",
            data=FormatString("hello"),
            runnable=True,
        )
        loaded = pickle.loads(pickle.dumps(ef))
        assert loaded.name == "f"
        assert loaded.type == "TEXT"
        assert loaded.data.raw() == "hello"
        assert loaded.runnable is True

    def test_pickle_uses_template_module_path(self):
        """The pickled bytes carry the pyclass's
        ``openjd.model._v1.template`` module path."""
        sd = StepDependency(depends_on="Foo")
        data = pickle.dumps(sd)
        # The pickled bytes contain the module path the class is
        # registered at — the class is registered under
        # `TemplateStepDependency` (with `module = ...template`).
        assert b"openjd.model._v1.template" in data
        assert b"TemplateStepDependency" in data
