# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Sanity test for the openjd.model and openjd.model.v0 packages.

This test lives outside ``test/openjd/model_v0/`` so it is not affected by
the ``OPENJD_MODEL_V0_TEST_IMPORT`` conftest in that directory. It checks
that the canonical public surface of each package is importable and that a
minimal end-to-end flow (parse a template, create a job, iterate parameters)
works in both, regardless of which mode v0 tests are configured for.

Note: ``openjd.model.JobTemplate`` is a ``typing.Any`` alias at runtime —
the concrete class is ``openjd.model.v2023_09.JobTemplate``. So this test
does not use ``isinstance`` against the top-level alias; it asserts on
attributes, returned-class names, and behavior.
"""

import importlib

import pytest

# A minimal but real job template that exercises parsing, validation,
# job creation, and task parameter iteration.
_MINIMAL_JOB_TEMPLATE = {
    "specificationVersion": "jobtemplate-2023-09",
    "name": "SanityJob",
    "parameterDefinitions": [
        {"name": "Frames", "type": "STRING", "default": "1-3"},
    ],
    "steps": [
        {
            "name": "Render",
            "parameterSpace": {
                "taskParameterDefinitions": [
                    {
                        "name": "Frame",
                        "type": "INT",
                        "range": "{{Param.Frames}}",
                    }
                ],
            },
            "script": {
                "actions": {"onRun": {"command": "echo", "args": ["{{Task.Param.Frame}}"]}},
            },
        }
    ],
}


_PUBLIC_NAMES = (
    "create_job",
    "decode_job_template",
    "decode_environment_template",
    "JobTemplate",
    "EnvironmentTemplate",
    "DocumentType",
    "DecodeValidationError",
    "SymbolTable",
    "StepParameterSpaceIterator",
)


@pytest.fixture(params=["openjd.model", "openjd.model.v0"], ids=["root", "v0"])
def model_module(request):
    """Import each package fresh for every parametrization."""
    return importlib.import_module(request.param)


class TestModelPackageSanity:
    def test_public_symbols_are_present(self, model_module):
        missing = [n for n in _PUBLIC_NAMES if not hasattr(model_module, n)]
        assert not missing, f"{model_module.__name__} is missing expected public names: {missing}"

    def test_decode_job_template_returns_concrete_template(self, model_module):
        template = model_module.decode_job_template(template=_MINIMAL_JOB_TEMPLATE)
        # The concrete class lives in v2023_09; assert by class name to avoid
        # depending on the runtime ``Any`` alias of openjd.model.JobTemplate.
        assert type(template).__name__ == "JobTemplate"
        assert template.name == "SanityJob"
        assert len(template.steps) == 1
        assert template.steps[0].name == "Render"

    def test_create_job_succeeds(self, model_module):
        template = model_module.decode_job_template(template=_MINIMAL_JOB_TEMPLATE)
        job = model_module.create_job(job_template=template, job_parameter_values={})
        assert type(job).__name__ == "Job"
        assert hasattr(job, "steps")
        steps = list(job.steps)
        assert len(steps) == 1
        assert steps[0].name == "Render"

    def test_step_parameter_iteration(self, model_module):
        template = model_module.decode_job_template(template=_MINIMAL_JOB_TEMPLATE)
        job = model_module.create_job(job_template=template, job_parameter_values={})
        step = list(job.steps)[0]
        # The "Frames" parameter defaults to "1-3", so we expect 3 task parameter sets.
        iterator = model_module.StepParameterSpaceIterator(space=step.parameterSpace)
        params = list(iterator)
        assert len(params) == 3

    def test_decode_validation_error_on_bad_template(self, model_module):
        with pytest.raises(model_module.DecodeValidationError):
            model_module.decode_job_template(template={"specificationVersion": "bogus"})


class TestPackagesAreConsistent:
    """openjd.model and openjd.model.v0 should each expose the documented
    public surface and produce equivalent results for the same input.

    These tests intentionally do not assert class or module identity, so they
    keep passing if openjd.model.v0 later gains its own distinct
    implementation.
    """

    def test_root_and_v0_share_public_names(self):
        import openjd.model as root
        import openjd.model.v0 as v0

        for name in _PUBLIC_NAMES:
            assert hasattr(root, name), f"openjd.model missing {name}"
            assert hasattr(v0, name), f"openjd.model.v0 missing {name}"

    def test_decode_results_have_equivalent_shape(self):
        import openjd.model as root
        import openjd.model.v0 as v0

        from_root = root.decode_job_template(template=_MINIMAL_JOB_TEMPLATE)
        from_v0 = v0.decode_job_template(template=_MINIMAL_JOB_TEMPLATE)
        assert from_root.name == from_v0.name == "SanityJob"
        assert len(from_root.steps) == len(from_v0.steps) == 1
        assert from_root.steps[0].name == from_v0.steps[0].name == "Render"
