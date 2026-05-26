# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for Rust model bindings: decode, create_job, and type wrappers."""

import json
import pytest

from openjd._openjd_rs import (
    decode_job_template_str,
    decode_job_template_dict,
    decode_environment_template_str,
    decode_environment_template_dict,
    create_job,
    DocumentType,
    DecodeValidationError,
    ModelValidationError,
    JobTemplate,
    EnvironmentTemplate,
    Job,
)

MINIMAL_JOB = {
    "specificationVersion": "jobtemplate-2023-09",
    "name": "Test",
    "steps": [
        {
            "name": "Step1",
            "script": {
                "actions": {"onRun": {"command": "echo", "args": ["hello"]}},
            },
        }
    ],
}

MINIMAL_ENV = {
    "specificationVersion": "environment-2023-09",
    "environment": {
        "name": "TestEnv",
        "script": {
            "actions": {
                "onEnter": {"command": "setup"},
                "onExit": {"command": "teardown"},
            },
        },
    },
}


class TestDecodeJobTemplate:
    def test_decode_json_string(self) -> None:
        template = decode_job_template_str(json.dumps(MINIMAL_JOB), DocumentType.JSON)
        assert isinstance(template, JobTemplate)
        assert template.name == "Test"
        assert (
            str(template.specification_version) == "jobtemplate-2023-09"
            or template.specification_version.name == "JOBTEMPLATE_2023_09"
        )

    def test_specification_version_camelcase_alias(self) -> None:
        """``specificationVersion`` is exposed as a camelCase alias for
        ``specification_version`` (mirrors the JSON/YAML field name)."""
        template = decode_job_template_dict(MINIMAL_JOB)
        assert template.specificationVersion is not None
        assert template.specificationVersion == template.specification_version

    def test_decode_yaml_string(self) -> None:
        yaml = """
specificationVersion: jobtemplate-2023-09
name: YAMLTest
steps:
  - name: S
    script:
      actions:
        onRun:
          command: echo
"""
        template = decode_job_template_str(yaml, DocumentType.YAML)
        assert template.name == "YAMLTest"

    def test_decode_from_dict(self) -> None:
        template = decode_job_template_dict(MINIMAL_JOB)
        assert template.name == "Test"

    def test_missing_spec_version_raises(self) -> None:
        with pytest.raises(DecodeValidationError, match="specificationVersion"):
            decode_job_template_str('{"name": "Bad"}', DocumentType.JSON)

    def test_unknown_spec_version_raises(self) -> None:
        with pytest.raises(DecodeValidationError, match="Unknown template version"):
            decode_job_template_str(
                '{"specificationVersion": "jobtemplate-9999-99", "name": "Bad"}',
                DocumentType.JSON,
            )

    def test_empty_command_raises(self) -> None:
        bad = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Test",
            "steps": [
                {
                    "name": "S",
                    "script": {"actions": {"onRun": {"command": ""}}},
                }
            ],
        }
        with pytest.raises((DecodeValidationError, ModelValidationError)):
            decode_job_template_dict(bad)

    def test_no_steps_raises(self) -> None:
        bad = {"specificationVersion": "jobtemplate-2023-09", "name": "Test", "steps": []}
        with pytest.raises((DecodeValidationError, ModelValidationError)):
            decode_job_template_dict(bad)


class TestDecodeEnvironmentTemplate:
    def test_decode_json(self) -> None:
        template = decode_environment_template_str(json.dumps(MINIMAL_ENV), DocumentType.JSON)
        assert isinstance(template, EnvironmentTemplate)

    def test_decode_from_dict(self) -> None:
        template = decode_environment_template_dict(MINIMAL_ENV)
        assert isinstance(template, EnvironmentTemplate)

    def test_specification_version_camelcase_alias(self) -> None:
        """``specificationVersion`` is exposed as a camelCase alias for
        ``specification_version`` (mirrors the JSON/YAML field name)."""
        template = decode_environment_template_dict(MINIMAL_ENV)
        assert template.specificationVersion is not None
        assert template.specificationVersion == template.specification_version


class TestCreateJob:
    def test_basic_job(self) -> None:
        template = decode_job_template_dict(MINIMAL_JOB)
        job = create_job(job_template=template, job_parameter_values={})
        assert isinstance(job, Job)
        assert job.name == "Test"
        assert len(job.steps) == 1

    def test_step_properties(self) -> None:
        template = decode_job_template_dict(MINIMAL_JOB)
        job = create_job(job_template=template, job_parameter_values={})
        step = job.steps[0]
        assert step.name == "Step1"
        assert step.script.actions.on_run.command.raw() == "echo"
        assert step.script.actions.on_run.args is not None
        assert [a.raw() for a in step.script.actions.on_run.args] == ["hello"]

    def test_job_with_parameters(self) -> None:
        tmpl = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "{{Param.Name}}",
            "parameterDefinitions": [{"name": "Name", "type": "STRING", "default": "DefaultJob"}],
            "steps": [
                {
                    "name": "S",
                    "script": {
                        "actions": {"onRun": {"command": "echo", "args": ["{{Param.Name}}"]}},
                    },
                }
            ],
        }
        template = decode_job_template_dict(tmpl)
        job = create_job(
            job_template=template,
            job_parameter_values={"Name": {"type": "STRING", "value": "MyJob"}},
        )
        assert job.name == "MyJob"
        args = job.steps[0].script.actions.on_run.args
        assert args is not None
        assert "Param.Name" in args[0].raw()

    def test_job_with_description(self) -> None:
        tmpl = dict(MINIMAL_JOB, description="A test job")
        template = decode_job_template_dict(tmpl)
        job = create_job(job_template=template, job_parameter_values={})
        assert job.description == "A test job"

    def test_job_without_description(self) -> None:
        template = decode_job_template_dict(MINIMAL_JOB)
        job = create_job(job_template=template, job_parameter_values={})
        assert job.description is None


class TestJobEnvironments:
    def test_step_environments(self) -> None:
        tmpl = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Test",
            "steps": [
                {
                    "name": "S",
                    "stepEnvironments": [
                        {
                            "name": "StepEnv",
                            "variables": {"KEY": "VALUE"},
                        }
                    ],
                    "script": {
                        "actions": {"onRun": {"command": "echo"}},
                    },
                }
            ],
        }
        template = decode_job_template_dict(tmpl)
        job = create_job(job_template=template, job_parameter_values={})
        envs = job.steps[0].step_environments
        assert envs is not None
        assert len(envs) == 1
        assert envs[0].name == "StepEnv"
        assert envs[0].variables == {"KEY": "VALUE"}


class TestStepParameterSpaceIterator:
    """Tests for StepParameterSpaceIterator."""

    @pytest.fixture
    def job_with_params(self):
        tmpl = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Test",
            "steps": [
                {
                    "name": "Render",
                    "parameterSpace": {
                        "taskParameterDefinitions": [
                            {"name": "Frame", "type": "INT", "range": "1-10"}
                        ]
                    },
                    "script": {"actions": {"onRun": {"command": "render"}}},
                }
            ],
        }
        template = decode_job_template_dict(tmpl)
        return create_job(job_template=template, job_parameter_values={})

    def test_len(self, job_with_params) -> None:
        from openjd._openjd_rs import StepParameterSpaceIterator

        it = StepParameterSpaceIterator(step=job_with_params.steps[0])
        assert len(it) == 10

    def test_getitem(self, job_with_params) -> None:
        from openjd._openjd_rs import StepParameterSpaceIterator

        it = StepParameterSpaceIterator(step=job_with_params.steps[0])
        assert it[0]["Frame"].value == "1"
        assert it[9]["Frame"].value == "10"

    def test_negative_index(self, job_with_params) -> None:
        from openjd._openjd_rs import StepParameterSpaceIterator

        it = StepParameterSpaceIterator(step=job_with_params.steps[0])
        assert it[-1]["Frame"].value == "10"
        assert it[-10]["Frame"].value == "1"

    def test_index_out_of_bounds(self, job_with_params) -> None:
        from openjd._openjd_rs import StepParameterSpaceIterator

        it = StepParameterSpaceIterator(step=job_with_params.steps[0])
        with pytest.raises(IndexError):
            it[10]

    def test_iteration(self, job_with_params) -> None:
        from openjd._openjd_rs import StepParameterSpaceIterator

        it = StepParameterSpaceIterator(step=job_with_params.steps[0])
        frames = [params["Frame"].value for params in it]
        assert frames == [str(i) for i in range(1, 11)]

    def test_names(self, job_with_params) -> None:
        from openjd._openjd_rs import StepParameterSpaceIterator

        it = StepParameterSpaceIterator(step=job_with_params.steps[0])
        assert it.names == {"Frame"}

    def test_step_without_params(self) -> None:
        from openjd._openjd_rs import StepParameterSpaceIterator

        tmpl = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Test",
            "steps": [{"name": "S", "script": {"actions": {"onRun": {"command": "echo"}}}}],
        }
        template = decode_job_template_dict(tmpl)
        job = create_job(job_template=template, job_parameter_values={})
        it = StepParameterSpaceIterator(step=job.steps[0])
        assert len(it) == 1


class TestStepDependencyGraph:
    """Tests for StepDependencyGraph."""

    def test_topo_sorted(self) -> None:
        from openjd._openjd_rs import StepDependencyGraph

        tmpl = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Test",
            "steps": [
                {"name": "A", "script": {"actions": {"onRun": {"command": "a"}}}},
                {
                    "name": "B",
                    "dependencies": [{"dependsOn": "A"}],
                    "script": {"actions": {"onRun": {"command": "b"}}},
                },
                {
                    "name": "C",
                    "dependencies": [{"dependsOn": "B"}],
                    "script": {"actions": {"onRun": {"command": "c"}}},
                },
            ],
        }
        template = decode_job_template_dict(tmpl)
        job = create_job(job_template=template, job_parameter_values={})
        graph = StepDependencyGraph(job=job)
        order = [s.name for s in graph.topo_sorted()]
        assert order.index("A") < order.index("B") < order.index("C")

    def test_step_names(self) -> None:
        from openjd._openjd_rs import StepDependencyGraph

        tmpl = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Test",
            "steps": [
                {"name": "X", "script": {"actions": {"onRun": {"command": "x"}}}},
                {"name": "Y", "script": {"actions": {"onRun": {"command": "y"}}}},
            ],
        }
        template = decode_job_template_dict(tmpl)
        job = create_job(job_template=template, job_parameter_values={})
        graph = StepDependencyGraph(job=job)
        assert set(graph.step_names()) == {"X", "Y"}

    def test_no_dependencies(self) -> None:
        from openjd._openjd_rs import StepDependencyGraph

        tmpl = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Test",
            "steps": [
                {"name": "A", "script": {"actions": {"onRun": {"command": "a"}}}},
            ],
        }
        template = decode_job_template_dict(tmpl)
        job = create_job(job_template=template, job_parameter_values={})
        graph = StepDependencyGraph(job=job)
        assert [s.name for s in graph.topo_sorted()] == ["A"]
