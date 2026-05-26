# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest
from typing import Any, Optional

from openjd.model._merge_job_parameter import (
    SourcedParamDefinition,
    merge_job_parameter_definitions,
    merge_job_parameter_definitions_for_one,
)
from openjd.model.v2023_09 import (
    EnvironmentTemplate,
    JobStringParameterDefinition,
    JobPathParameterDefinition,
    JobIntParameterDefinition,
    JobFloatParameterDefinition,
    JobTemplate,
)
from openjd.model import CompatibilityError, JobParameterDefinition, parse_model


class TestMergeForOne_v2023_09:
    @pytest.mark.parametrize(
        "given, expected",
        [
            # ========================================
            #
            pytest.param(
                [
                    SourcedParamDefinition(
                        source="Env", definition=JobIntParameterDefinition(name="foo", type="INT")
                    ),
                    SourcedParamDefinition(
                        source="JobTemplate",
                        definition=JobIntParameterDefinition(name="foo", type="INT"),
                    ),
                ],
                JobIntParameterDefinition(name="foo", type="INT"),
                id="simple int",
            ),
            pytest.param(
                [
                    SourcedParamDefinition(
                        source="Env",
                        definition=parse_model(
                            model=JobIntParameterDefinition,
                            obj={
                                "name": "foo",
                                "type": "INT",
                                "allowedValues": [10, 20, 30],
                                "minValue": 0,
                                "maxValue": 40,
                                "default": 20,
                            },
                        ),
                    ),
                    SourcedParamDefinition(
                        source="JobTemplate",
                        definition=parse_model(
                            model=JobIntParameterDefinition,
                            obj={
                                "name": "foo",
                                "type": "INT",
                                "allowedValues": [10, 30],
                                "minValue": 5,
                                "maxValue": 50,
                                "default": 10,
                            },
                        ),
                    ),
                ],
                parse_model(
                    model=JobIntParameterDefinition,
                    obj={
                        "name": "foo",
                        "type": "INT",
                        "allowedValues": [10, 30],
                        "minValue": 5,
                        "maxValue": 40,
                        "default": 10,
                    },
                ),
                id="all int property checks",
            ),
            # ========================================
            #
            pytest.param(
                [
                    SourcedParamDefinition(
                        source="Env",
                        definition=JobFloatParameterDefinition(name="foo", type="FLOAT"),
                    ),
                    SourcedParamDefinition(
                        source="JobTemplate",
                        definition=JobFloatParameterDefinition(name="foo", type="FLOAT"),
                    ),
                ],
                JobFloatParameterDefinition(name="foo", type="FLOAT"),
                id="simple float",
            ),
            pytest.param(
                [
                    SourcedParamDefinition(
                        source="Env",
                        definition=parse_model(
                            model=JobFloatParameterDefinition,
                            obj={
                                "name": "foo",
                                "type": "FLOAT",
                                "allowedValues": [10, 20, 30],
                                "minValue": 0,
                                "maxValue": 40,
                                "default": 20,
                            },
                        ),
                    ),
                    SourcedParamDefinition(
                        source="JobTemplate",
                        definition=parse_model(
                            model=JobFloatParameterDefinition,
                            obj={
                                "name": "foo",
                                "type": "FLOAT",
                                "allowedValues": [10, 30],
                                "minValue": 5,
                                "maxValue": 50,
                                "default": 10,
                            },
                        ),
                    ),
                ],
                parse_model(
                    model=JobFloatParameterDefinition,
                    obj={
                        "name": "foo",
                        "type": "FLOAT",
                        "allowedValues": [10, 30],
                        "minValue": 5,
                        "maxValue": 40,
                        "default": 10,
                    },
                ),
                id="all float property checks",
            ),
            # ========================================
            #
            pytest.param(
                [
                    SourcedParamDefinition(
                        source="Env",
                        definition=JobStringParameterDefinition(name="foo", type="STRING"),
                    ),
                    SourcedParamDefinition(
                        source="JobTemplate",
                        definition=JobStringParameterDefinition(name="foo", type="STRING"),
                    ),
                ],
                JobStringParameterDefinition(name="foo", type="STRING"),
                id="simple string",
            ),
            pytest.param(
                [
                    SourcedParamDefinition(
                        source="Env",
                        definition=parse_model(
                            model=JobStringParameterDefinition,
                            obj={
                                "name": "foo",
                                "type": "STRING",
                                "allowedValues": ["aaa", "bbbbb", "cccccc"],
                                "minLength": 1,
                                "maxLength": 9,
                                "default": "aaa",
                            },
                        ),
                    ),
                    SourcedParamDefinition(
                        source="JobTemplate",
                        definition=parse_model(
                            model=JobStringParameterDefinition,
                            obj={
                                "name": "foo",
                                "type": "STRING",
                                "allowedValues": ["bbbbb", "cccccc"],
                                "minLength": 2,
                                "maxLength": 10,
                                "default": "bbbbb",
                            },
                        ),
                    ),
                ],
                parse_model(
                    model=JobStringParameterDefinition,
                    obj={
                        "name": "foo",
                        "type": "STRING",
                        "allowedValues": ["bbbbb", "cccccc"],
                        "minLength": 2,
                        "maxLength": 9,
                        "default": "bbbbb",
                    },
                ),
                id="all string property checks",
            ),
            # ========================================
            #
            pytest.param(
                [
                    SourcedParamDefinition(
                        source="Env", definition=JobPathParameterDefinition(name="foo", type="PATH")
                    ),
                    SourcedParamDefinition(
                        source="JobTemplate",
                        definition=JobPathParameterDefinition(name="foo", type="PATH"),
                    ),
                ],
                JobPathParameterDefinition(name="foo", type="PATH"),
                id="simple path",
            ),
            pytest.param(
                [
                    SourcedParamDefinition(
                        source="Env",
                        definition=parse_model(
                            model=JobPathParameterDefinition,
                            obj={
                                "name": "foo",
                                "type": "PATH",
                                "objectType": "FILE",
                                "dataFlow": "IN",
                                "allowedValues": ["aaa", "bbbbb", "cccccc"],
                                "minLength": 1,
                                "maxLength": 10,
                                "default": "aaa",
                            },
                        ),
                    ),
                    SourcedParamDefinition(
                        source="JobTemplate",
                        definition=parse_model(
                            model=JobPathParameterDefinition,
                            obj={
                                "name": "foo",
                                "type": "PATH",
                                "objectType": "FILE",
                                "dataFlow": "IN",
                                "allowedValues": ["bbbbb", "cccccc"],
                                "minLength": 2,
                                "maxLength": 9,
                                "default": "bbbbb",
                            },
                        ),
                    ),
                ],
                parse_model(
                    model=JobPathParameterDefinition,
                    obj={
                        "name": "foo",
                        "type": "PATH",
                        "objectType": "FILE",
                        "dataFlow": "IN",
                        "allowedValues": ["bbbbb", "cccccc"],
                        "minLength": 2,
                        "maxLength": 9,
                        "default": "bbbbb",
                    },
                ),
                id="all path property checks",
            ),
        ],
    )
    def test_success(
        self, given: list[SourcedParamDefinition], expected: JobParameterDefinition
    ) -> None:
        # WHEN
        result = merge_job_parameter_definitions_for_one(given)
        # THEN
        assert result == expected

    @pytest.mark.parametrize(
        "given, expected",
        [
            pytest.param(
                [
                    SourcedParamDefinition(
                        source="Env", definition=JobIntParameterDefinition(name="foo", type="INT")
                    ),
                    SourcedParamDefinition(
                        source="JobTemplate",
                        definition=JobIntParameterDefinition(name="bar", type="INT"),
                    ),
                ],
                "Parameter names differ",
                id="parameter names",
            ),
            pytest.param(
                [
                    SourcedParamDefinition(
                        source="Env", definition=JobIntParameterDefinition(name="foo", type="INT")
                    ),
                    SourcedParamDefinition(
                        source="JobTemplate",
                        definition=JobFloatParameterDefinition(name="foo", type="FLOAT"),
                    ),
                ],
                "Parameter type in 'Env' differs from expected type 'FLOAT'",
                id="types differ",
            ),
            pytest.param(
                [
                    SourcedParamDefinition(
                        source="Env",
                        definition=parse_model(
                            model=JobIntParameterDefinition,
                            obj={"name": "foo", "type": "INT", "allowedValues": [10, 20]},
                        ),
                    ),
                    SourcedParamDefinition(
                        source="JobTemplate",
                        definition=parse_model(
                            model=JobIntParameterDefinition,
                            obj={"name": "foo", "type": "INT", "allowedValues": [30, 40]},
                        ),
                    ),
                ],
                "The intersection of all allowedValues is empty. There are no values that can satisfy all constraints.",
                id="non-compatible allowedValues",
            ),
            pytest.param(
                [
                    SourcedParamDefinition(
                        source="Env",
                        definition=parse_model(
                            model=JobPathParameterDefinition,
                            obj={"name": "foo", "type": "PATH"},  # default objectType is DIRECTORY
                        ),
                    ),
                    SourcedParamDefinition(
                        source="JobTemplate",
                        definition=parse_model(
                            model=JobPathParameterDefinition,
                            obj={"name": "foo", "type": "PATH", "objectType": "FILE"},
                        ),
                    ),
                ],
                "Parameter objectTypes differ",
                id="non-compatible PATH objectType with default",
            ),
            pytest.param(
                [
                    SourcedParamDefinition(
                        source="Env",
                        definition=parse_model(
                            model=JobPathParameterDefinition,
                            obj={"name": "foo", "type": "PATH", "objectType": "FILE"},
                        ),
                    ),
                    SourcedParamDefinition(
                        source="JobTemplate",
                        definition=parse_model(
                            model=JobPathParameterDefinition,
                            obj={"name": "foo", "type": "PATH", "objectType": "DIRECTORY"},
                        ),
                    ),
                ],
                "Parameter objectTypes differ",
                id="non-compatible PATH objectType",
            ),
            pytest.param(
                [
                    SourcedParamDefinition(
                        source="Env",
                        definition=parse_model(
                            model=JobPathParameterDefinition,
                            obj={"name": "foo", "type": "PATH", "dataFlow": "IN"},
                        ),
                    ),
                    SourcedParamDefinition(
                        source="JobTemplate",
                        definition=parse_model(
                            model=JobPathParameterDefinition,
                            obj={"name": "foo", "type": "PATH", "dataFlow": "OUT"},
                        ),
                    ),
                ],
                "Parameter dataFlows differ",
                id="non-compatible PATH dataFlow",
            ),
            pytest.param(
                [
                    SourcedParamDefinition(
                        source="Env",
                        definition=parse_model(
                            model=JobStringParameterDefinition,
                            obj={"name": "foo", "type": "STRING", "minLength": 10, "maxLength": 20},
                        ),
                    ),
                    SourcedParamDefinition(
                        source="JobTemplate",
                        definition=parse_model(
                            model=JobStringParameterDefinition,
                            obj={"name": "foo", "type": "STRING", "minLength": 5, "maxLength": 8},
                        ),
                    ),
                ],
                "Merged constraint minLength (10) <= maxLength (8) is not satisfyable.",
                id="non-compatible length constraints",
            ),
            pytest.param(
                [
                    SourcedParamDefinition(
                        source="Env",
                        definition=parse_model(
                            model=JobIntParameterDefinition,
                            obj={
                                "name": "foo",
                                "type": "INT",
                                "minValue": 10,
                                "maxValue": 20,
                            },
                        ),
                    ),
                    SourcedParamDefinition(
                        source="JobTemplate",
                        definition=parse_model(
                            model=JobIntParameterDefinition,
                            obj={"name": "foo", "type": "INT", "minValue": 5, "maxValue": 8},
                        ),
                    ),
                ],
                "Merged constraint minValue (10) <= maxValue (8) is not satisfyable.",
                id="non-compatible value constraints",
            ),
        ],
    )
    def test_not_compatible(self, given: list[SourcedParamDefinition], expected: str) -> None:
        # WHEN
        with pytest.raises(CompatibilityError) as excinfo:
            merge_job_parameter_definitions_for_one(given)

        # THEN
        assert expected in str(excinfo.value)


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
                parse_model(
                    model=JobTemplate,
                    obj={
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
                    parse_model(
                        model=JobIntParameterDefinition,
                        obj={"name": "Foo", "type": "INT", "maxValue": 50},
                    ),
                    parse_model(
                        model=JobStringParameterDefinition,
                        obj={"name": "Bar", "type": "STRING", "minLength": 1},
                    ),
                ],
                id="only job template",
            ),
            pytest.param(
                None,  # No job template
                [
                    parse_model(
                        model=EnvironmentTemplate,
                        obj={
                            "specificationVersion": "environment-2023-09",
                            "parameterDefinitions": [
                                {"name": "Foo", "type": "INT", "minValue": 1},
                                {"name": "Bar", "type": "STRING", "minLength": 5},
                            ],
                            "environment": {
                                "name": "Env1",
                                **BASIC_ENVIRONMENT_TEMPLATE_ACTION_2023_09,
                            },
                        },
                    ),
                    parse_model(
                        model=EnvironmentTemplate,
                        obj={
                            "specificationVersion": "environment-2023-09",
                            "parameterDefinitions": [
                                {"name": "Foo", "type": "INT", "maxValue": 10},
                                {"name": "Bar", "type": "STRING", "maxLength": 50},
                            ],
                            "environment": {
                                "name": "Env2",
                                **BASIC_ENVIRONMENT_TEMPLATE_ACTION_2023_09,
                            },
                        },
                    ),
                ],
                [
                    parse_model(
                        model=JobIntParameterDefinition,
                        obj={"name": "Foo", "type": "INT", "minValue": 1, "maxValue": 10},
                    ),
                    parse_model(
                        model=JobStringParameterDefinition,
                        obj={"name": "Bar", "type": "STRING", "minLength": 5, "maxLength": 50},
                    ),
                ],
                id="merging two environments",
            ),
            pytest.param(
                parse_model(
                    model=JobTemplate,
                    obj={
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
                    parse_model(
                        model=EnvironmentTemplate,
                        obj={
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
                    parse_model(
                        model=EnvironmentTemplate,
                        obj={
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
                    parse_model(
                        model=JobIntParameterDefinition,
                        obj={
                            "name": "Foo",
                            "type": "INT",
                            "minValue": 5,
                            "maxValue": 10,
                            "default": 8,
                        },
                    ),
                    parse_model(
                        model=JobStringParameterDefinition,
                        obj={
                            "name": "Bar",
                            "type": "STRING",
                            "minLength": 20,
                            "maxLength": 30,
                            "default": "b" * 25,
                        },
                    ),
                ],
                id="merging environments and job template in correct order",
            ),
        ],
    )
    def test_success(
        self,
        given_job_template: Optional[JobTemplate],
        given_envs: Optional[list[EnvironmentTemplate]],
        expected: list[JobParameterDefinition],
    ) -> None:
        # WHEN
        result = merge_job_parameter_definitions(
            job_template=given_job_template, environment_templates=given_envs
        )

        # THEN
        # note: convert to sets in the compare to be order-agnostic
        assert set(result) == set(expected)

    @pytest.mark.parametrize(
        "given_job_template, given_envs, expected",
        [
            pytest.param(
                parse_model(
                    model=JobTemplate,
                    obj={
                        "specificationVersion": "jobtemplate-2023-09",
                        "name": "Job",
                        "parameterDefinitions": [
                            # Only Bar is in conflict
                            {"name": "Foo", "type": "INT", "minValue": 5},
                            {"name": "Bar", "type": "STRING", "minLength": 5, "maxLength": 10},
                        ],
                        "steps": [BASIC_JOB_TEMPLATE_STEP_2023_09],
                    },
                ),
                [
                    parse_model(
                        model=EnvironmentTemplate,
                        obj={
                            "specificationVersion": "environment-2023-09",
                            "parameterDefinitions": [
                                {"name": "Foo", "type": "INT", "minValue": 10},
                            ],
                            "environment": {
                                "name": "Env1",
                                **BASIC_ENVIRONMENT_TEMPLATE_ACTION_2023_09,
                            },
                        },
                    ),
                    parse_model(
                        model=EnvironmentTemplate,
                        obj={
                            "specificationVersion": "environment-2023-09",
                            "parameterDefinitions": [
                                {"name": "Foo", "type": "INT", "minValue": 5},
                                {"name": "Bar", "type": "STRING", "minLength": 20},
                            ],
                            "environment": {
                                "name": "Env2",
                                **BASIC_ENVIRONMENT_TEMPLATE_ACTION_2023_09,
                            },
                        },
                    ),
                ],
                "The definitions for job parameter 'Bar' are in conflict:\n\tMerged constraint minLength (20) <= maxLength (10) is not satisfyable.",
                id="two defs conflict",
            ),
        ],
    )
    def test_not_compatible(
        self,
        given_job_template: Optional[JobTemplate],
        given_envs: Optional[list[EnvironmentTemplate]],
        expected: str,
    ):
        # WHEN
        with pytest.raises(CompatibilityError) as excinfo:
            merge_job_parameter_definitions(
                job_template=given_job_template, environment_templates=given_envs
            )

        # THEN
        assert str(excinfo.value) == expected
