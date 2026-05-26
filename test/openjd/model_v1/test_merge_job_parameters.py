# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest
from typing import Any, Optional

from openjd.model._v1 import (
    decode_environment_template,
    decode_job_template,
    merge_job_parameter_definitions,
)
from openjd.model._v1.template import (
    EnvironmentTemplate,
    JobTemplate,
)


BASIC_JOB_TEMPLATE_STEP_2023_09: dict[str, Any] = {
    "name": "Test",
    "script": {"actions": {"onRun": {"command": "foo"}}},
}
BASIC_ENVIRONMENT_TEMPLATE_ACTION_2023_09: dict[str, Any] = {
    "script": {"actions": {"onEnter": {"command": "bar"}}}
}


class TestMergeTemplates_v2023_09:
    @pytest.mark.parametrize(
        "given_job_template, given_envs, expected",
        [
            pytest.param(
                decode_job_template(
                    template={
                        "specificationVersion": "jobtemplate-2023-09",
                        "name": "Job",
                        "parameterDefinitions": [
                            {"name": "Foo", "type": "INT", "maxValue": 50},
                            {"name": "Bar", "type": "STRING", "minLength": 1},
                        ],
                        "steps": [BASIC_JOB_TEMPLATE_STEP_2023_09],
                    },
                ),
                None,  # No environments
                [
                    {"name": "Foo", "type": "INT", "source": "JobTemplate"},
                    {"name": "Bar", "type": "STRING", "source": "JobTemplate"},
                ],
                id="only job template",
            ),
            pytest.param(
                decode_job_template(
                    template={
                        "specificationVersion": "jobtemplate-2023-09",
                        "name": "Job",
                        "parameterDefinitions": [
                            {"name": "Foo", "type": "INT", "minValue": 5, "maxValue": 10},
                            {
                                "name": "Bar",
                                "type": "STRING",
                                "minLength": 20,
                                "maxLength": 30,
                                "default": "b" * 25,
                            },
                        ],
                        "steps": [BASIC_JOB_TEMPLATE_STEP_2023_09],
                    },
                ),
                [
                    decode_environment_template(
                        template={
                            "specificationVersion": "environment-2023-09",
                            "parameterDefinitions": [
                                {"name": "Foo", "type": "INT", "minValue": 1, "default": 8},
                                {"name": "Bar", "type": "STRING", "minLength": 5},
                            ],
                            "environment": {
                                "name": "Env1",
                                **BASIC_ENVIRONMENT_TEMPLATE_ACTION_2023_09,
                            },
                        },
                    ),
                    decode_environment_template(
                        template={
                            "specificationVersion": "environment-2023-09",
                            "parameterDefinitions": [
                                {"name": "Foo", "type": "INT", "maxValue": 20},
                                {
                                    "name": "Bar",
                                    "type": "STRING",
                                    "maxLength": 50,
                                    "default": "a" * 40,
                                },
                            ],
                            "environment": {
                                "name": "Env2",
                                **BASIC_ENVIRONMENT_TEMPLATE_ACTION_2023_09,
                            },
                        },
                    ),
                ],
                [
                    {"name": "Foo", "type": "INT", "default": "8", "source": "JobTemplate"},
                    {
                        "name": "Bar",
                        "type": "STRING",
                        "default": "b" * 25,
                        "source": "JobTemplate",
                    },
                ],
                id="merging environments and job template - job template default wins",
            ),
            pytest.param(
                decode_job_template(
                    template={
                        "specificationVersion": "jobtemplate-2023-09",
                        "name": "Job",
                        "parameterDefinitions": [
                            {"name": "Foo", "type": "INT"},
                        ],
                        "steps": [BASIC_JOB_TEMPLATE_STEP_2023_09],
                    },
                ),
                [
                    decode_environment_template(
                        template={
                            "specificationVersion": "environment-2023-09",
                            "parameterDefinitions": [
                                {"name": "Foo", "type": "INT", "default": 42},
                            ],
                            "environment": {
                                "name": "Env1",
                                **BASIC_ENVIRONMENT_TEMPLATE_ACTION_2023_09,
                            },
                        },
                    ),
                ],
                [
                    {"name": "Foo", "type": "INT", "default": "42", "source": "JobTemplate"},
                ],
                id="environment default propagates when job template has none",
            ),
        ],
    )
    def test_success(
        self,
        given_job_template: JobTemplate,
        given_envs: Optional[list[EnvironmentTemplate]],
        expected: list[dict[str, Any]],
    ) -> None:
        # WHEN
        result = merge_job_parameter_definitions(
            job_template=given_job_template, environment_templates=given_envs
        )

        # THEN
        # Compare as sets of frozen items for order-agnostic comparison
        def _to_comparable(param_list):
            return {tuple(sorted(p.items())) for p in param_list}

        assert _to_comparable(result) == _to_comparable(expected)
