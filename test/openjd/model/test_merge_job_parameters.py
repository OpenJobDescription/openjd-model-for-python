# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest

from openjd.model._merge_job_parameter import (
    SourcedParamDefinition,
    merge_job_parameter_definitions_for_one,
)
from openjd.model.v2023_09 import (
    JobStringParameterDefinition,
    JobPathParameterDefinition,
    JobIntParameterDefinition,
    JobFloatParameterDefinition,
)
from openjd.model import CompatibilityError, JobParameterDefinition, parse_model


class Test_v2023_09:
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
                                "maxValue": 50,
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
                                "maxValue": 40,
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
                                "maxValue": 50,
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
                                "maxValue": 40,
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
                                "maxLength": 10,
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
                                "maxLength": 9,
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
                "Parameter types differ",
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
                            obj={"name": "foo", "type": "INT", "allowedValues": [10, 40]},
                        ),
                    ),
                ],
                "allowedValues for 'JobTemplate' contains non-compatible",
                id="non-compatible allowedValues",
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
                            obj={"name": "foo", "type": "STRING", "minLength": 10},
                        ),
                    ),
                    SourcedParamDefinition(
                        source="JobTemplate",
                        definition=parse_model(
                            model=JobStringParameterDefinition,
                            obj={"name": "foo", "type": "STRING", "minLength": 5},
                        ),
                    ),
                ],
                "minLength of 'JobTemplate'",
                id="non-compatible minLength",
            ),
            pytest.param(
                [
                    SourcedParamDefinition(
                        source="Env",
                        definition=parse_model(
                            model=JobStringParameterDefinition,
                            obj={"name": "foo", "type": "STRING", "maxLength": 10},
                        ),
                    ),
                    SourcedParamDefinition(
                        source="JobTemplate",
                        definition=parse_model(
                            model=JobStringParameterDefinition,
                            obj={"name": "foo", "type": "STRING", "maxLength": 15},
                        ),
                    ),
                ],
                "maxLength of 'JobTemplate'",
                id="non-compatible maxLength",
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
                                "minValue": 5,
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
                                "minValue": 0,
                            },
                        ),
                    ),
                ],
                "minValue of 'JobTemplate'",
                id="non-compatible minValue",
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
                                "maxValue": 50,
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
                                "maxValue": 55,
                            },
                        ),
                    ),
                ],
                "maxValue of 'JobTemplate'",
                id="non-compatible maxValue",
            ),
        ],
    )
    def test_not_compatible(self, given: list[SourcedParamDefinition], expected: str) -> None:
        # WHEN
        with pytest.raises(CompatibilityError) as excinfo:
            merge_job_parameter_definitions_for_one(given)

        # THEN
        assert expected in str(excinfo.value)
