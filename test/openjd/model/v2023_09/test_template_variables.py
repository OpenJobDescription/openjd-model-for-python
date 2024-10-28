# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any

import pytest
from pydantic.v1 import ValidationError

from openjd.model._parse import _parse_model
from openjd.model.v2023_09 import JobTemplate

# Some minimal data to reference in tests.
ENV_SCRIPT_FOO = {
    "actions": {
        "onEnter": {"command": "foo {{Param.Foo}} {{RawParam.Foo}} {{Session.WorkingDirectory}}"}
    }
}
ENVIRONMENT_FOO = {"name": "FooEnv", "script": ENV_SCRIPT_FOO}
STEP_SCRIPT = {"actions": {"onRun": {"command": "foo"}}}
STEP_TEMPLATE = {"name": "StepName", "script": STEP_SCRIPT}
STEP_SCRIPT_FOO = {
    "actions": {
        "onRun": {
            "command": "foo {{Param.Foo}} {{RawParam.Foo}} {{Session.WorkingDirectory}}",
            "args": ["foo {{Param.Foo}} {{RawParam.Foo}} {{Session.WorkingDirectory}}"],
        }
    }
}
STEP_TEMPLATE_FOO = {"name": "StepName", "script": STEP_SCRIPT_FOO}
FOO_PARAMETER_INT = {"name": "Foo", "type": "INT"}
FOO_PARAMETER_FLOAT = {"name": "Foo", "type": "FLOAT"}
FOO_PARAMETER_STRING = {"name": "Foo", "type": "STRING"}
FOO_PARAMETER_PATH = {"name": "Foo", "type": "PATH"}


def make_script(env_or_task: str, scriptname: str, scriptdata: str) -> dict:
    return {
        "actions": {
            ("onEnter" if env_or_task == "Env" else "onRun"): {
                "command": ("{{%s.File.%s}}" % (env_or_task, scriptname))
            }
        },
        "embeddedFiles": [{"name": scriptname, "type": "TEXT", "data": scriptdata}],
    }


class TestJobTemplate:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo {{Param.Foo}}",
                    "parameterDefinitions": [FOO_PARAMETER_INT],
                    "steps": [STEP_TEMPLATE_FOO],
                },
                id="minimum int parameter",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo {{Param.Foo}}",
                    "parameterDefinitions": [FOO_PARAMETER_FLOAT],
                    "steps": [STEP_TEMPLATE_FOO],
                },
                id="minimum float parameter",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo {{Param.Foo}}",
                    "parameterDefinitions": [FOO_PARAMETER_STRING],
                    "steps": [STEP_TEMPLATE_FOO],
                },
                id="minimum string parameter",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo {{RawParam.Foo}}",
                    "parameterDefinitions": [FOO_PARAMETER_PATH],
                    "steps": [STEP_TEMPLATE_FOO],
                },
                id="minimum path parameter",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "parameterDefinitions": [FOO_PARAMETER_INT],
                    "steps": [STEP_TEMPLATE_FOO],
                    "description": "some text {{Param.NotSubstituted}}",
                },
                id="with description",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "parameterDefinitions": [FOO_PARAMETER_INT],
                    "steps": [STEP_TEMPLATE_FOO],
                    "jobEnvironments": [ENVIRONMENT_FOO],
                },
                id="with environments",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "parameterDefinitions": [FOO_PARAMETER_PATH],
                    "steps": [STEP_TEMPLATE],
                    "jobEnvironments": [ENVIRONMENT_FOO],
                },
                id="path in environments",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo {{Param.Foo}}",
                    "parameterDefinitions": [FOO_PARAMETER_STRING],
                    "steps": [
                        STEP_TEMPLATE_FOO,
                        {
                            "name": "BarStep",
                            "script": make_script("Task", "BarScript", "echo {{Param.Foo}}"),
                        },
                        {
                            "name": "BazStep",
                            "script": make_script(
                                "Task", "BazScript", "echo {{Param.Foo}} {{Task.File.BazScript}}"
                            ),
                        },
                    ],
                },
                id="multiple steps",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "parameterDefinitions": [FOO_PARAMETER_INT],
                    "steps": [STEP_TEMPLATE_FOO],
                    "jobEnvironments": [
                        ENVIRONMENT_FOO,
                        {
                            "name": "BarEnv",
                            "script": make_script(
                                "Env", "BarScript", "echo {{Param.Foo}} {{Env.File.BarScript}}"
                            ),
                        },
                        {
                            "name": "BazEnv",
                            "script": make_script(
                                "Env",
                                "BazScript",
                                "echo {{Param.Foo}} {{Session.WorkingDirectory}}",
                            ),
                        },
                    ],
                },
                id="multiple environments",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo {{Param.Foo}}",
                    "parameterDefinitions": [FOO_PARAMETER_STRING],
                    "steps": [
                        {
                            "name": "BarStep",
                            "script": make_script(
                                "Task",
                                "BarScript",
                                "echo {{Param.Foo}} {{Task.Param.Foo}} {{Task.RawParam.Foo}}",
                            ),
                            "parameterSpace": {
                                "taskParameterDefinitions": [
                                    {"name": "Foo", "type": "INT", "range": [1, 2]}
                                ]
                            },
                        },
                    ],
                },
                id="step with parameter space",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "parameterDefinitions": [FOO_PARAMETER_PATH],
                    "steps": [
                        {
                            "name": "BarStep",
                            "script": make_script(
                                "Task", "BarScript", "echo {{Param.Foo}} {{Task.Param.Foo}}"
                            ),
                            "parameterSpace": {
                                "taskParameterDefinitions": [
                                    {
                                        "name": "Foo",
                                        "type": "STRING",
                                        "range": ["blah", "{{RawParam.Foo}}"],
                                    }
                                ]
                            },
                        },
                    ],
                },
                id="raw path in parameter space",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo {{Param.Foo}}",
                    "parameterDefinitions": [FOO_PARAMETER_STRING],
                    "steps": [
                        {
                            "name": "BarStep",
                            "script": make_script(
                                "Task", "BarScript", "echo {{Param.Foo}} {{Task.Param.Foo}}"
                            ),
                            "parameterSpace": {
                                "taskParameterDefinitions": [
                                    {"name": "Foo", "type": "INT", "range": [1, 2]}
                                ]
                            },
                            "stepEnvironments": [
                                {
                                    "name": "BarEnv",
                                    "script": make_script(
                                        "Env",
                                        "BarScript",
                                        "echo {{Param.Foo}} {{Env.File.BarScript}} {{Session.WorkingDirectory}}",
                                    ),
                                }
                            ],
                        },
                    ],
                },
                id="step with parameter space and environment",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo {{Param.Foo}}",
                    "parameterDefinitions": [FOO_PARAMETER_STRING],
                    "steps": [
                        {
                            "name": "BarStep",
                            "script": make_script(
                                "Task",
                                "BarScript",
                                "echo {{Param.Foo}} {{Task.Param.Foo}} {{Task.Param.Bar}} {{Task.Param.Baz}}",
                            ),
                            "parameterSpace": {
                                "taskParameterDefinitions": [
                                    {"name": "Foo", "type": "INT", "range": [1, 2]},
                                    {"name": "Bar", "type": "FLOAT", "range": [1, 2]},
                                    {
                                        "name": "Baz",
                                        "type": "STRING",
                                        "range": ["{{Param.Foo}}"],
                                    },
                                ]
                            },
                            "stepEnvironments": [
                                {
                                    "name": "BarEnv",
                                    "script": make_script(
                                        "Env",
                                        "BarScript",
                                        "echo {{Param.Foo}} {{Env.File.BarScript}} {{Session.WorkingDirectory}}",
                                    ),
                                }
                            ],
                        },
                    ],
                },
                id="string task param can see the job params",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo {{Param.Foo}}",
                    "parameterDefinitions": [FOO_PARAMETER_STRING],
                    "steps": [
                        {
                            "name": "BarStep",
                            "script": make_script(
                                "Task",
                                "BarScript",
                                "echo Hi",
                            ),
                            "hostRequirements": {
                                "amounts": [
                                    {
                                        "name": "amount.{{Param.Foo}}",
                                        "min": 3,
                                    },
                                ],
                                "attributes": [
                                    {
                                        "name": "attr.{{Param.Foo}}",
                                        "anyOf": ["{{Param.Foo}}"],
                                    },
                                    {
                                        "name": "attr.allof",
                                        "allOf": ["{{Param.Foo}}"],
                                    },
                                ],
                            },
                        },
                    ],
                },
                id="capabilities can see the job params",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [
                        {
                            "name": "BarStep",
                            "script": make_script(
                                "Task",
                                "BarScript",
                                "echo {{Session.WorkingDirectory}} {{Session.HasPathMappingRules}} {{Session.PathMappingRulesFile}}",
                            ),
                            "stepEnvironments": [
                                {
                                    "name": "BarEnv",
                                    "script": make_script(
                                        "Env",
                                        "BarScript",
                                        "echo {{Session.WorkingDirectory}} {{Session.HasPathMappingRules}} {{Session.PathMappingRulesFile}}",
                                    ),
                                }
                            ],
                        },
                    ],
                },
                id="Can reference Session values",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [
                        {
                            "name": "BarStep",
                            "script": {
                                "embeddedFiles": [
                                    {
                                        "name": "file1",
                                        "type": "TEXT",
                                        "data": "{{Task.File.file1}} {{Task.File.file2}}",
                                    },
                                    {
                                        "name": "file2",
                                        "type": "TEXT",
                                        "data": "{{Task.File.file1}} {{Task.File.file2}}",
                                    },
                                ],
                                "actions": {
                                    "onRun": {"command": "{{Task.File.file1}} {{Task.File.file2}}"}
                                },
                            },
                        },
                    ],
                },
                id="embedded stepscript files can reference themself and others.",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "jobEnvironments": [
                        {
                            "name": "JobEnv",
                            "script": {
                                "embeddedFiles": [
                                    {
                                        "name": "file1",
                                        "type": "TEXT",
                                        "data": "{{Env.File.file1}} {{Env.File.file2}} {{Session.WorkingDirectory}}",
                                    },
                                    {
                                        "name": "file2",
                                        "type": "TEXT",
                                        "data": "{{Env.File.file1}} {{Env.File.file2}} {{Session.WorkingDirectory}}",
                                    },
                                ],
                                "actions": {
                                    "onEnter": {
                                        "command": "{{Env.File.file1}} {{Env.File.file2}} {{Session.WorkingDirectory}}"
                                    },
                                    "onExit": {
                                        "command": "{{Env.File.file1}} {{Env.File.file2}} {{Session.WorkingDirectory}}"
                                    },
                                },
                            },
                        }
                    ],
                    "steps": [
                        {
                            "name": "BarStep",
                            "stepEnvironments": [
                                {
                                    "name": "StepEnv",
                                    "script": {
                                        "embeddedFiles": [
                                            {
                                                "name": "fileA",
                                                "type": "TEXT",
                                                "data": "{{Env.File.fileA}} {{Env.File.fileB}} {{Session.WorkingDirectory}}",
                                            },
                                            {
                                                "name": "fileB",
                                                "type": "TEXT",
                                                "data": "{{Env.File.fileA}} {{Env.File.fileB}} {{Session.WorkingDirectory}}",
                                            },
                                        ],
                                        "actions": {
                                            "onEnter": {
                                                "command": "{{Env.File.fileA}} {{Env.File.fileB}} {{Session.WorkingDirectory}}"
                                            },
                                            "onExit": {
                                                "command": "{{Env.File.fileA}} {{Env.File.fileB}} {{Session.WorkingDirectory}}"
                                            },
                                        },
                                    },
                                }
                            ],
                            "script": {
                                "actions": {"onRun": {"command": "foo"}},
                            },
                        },
                    ],
                },
                id="embedded env script files can reference themself and others.",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "parameterDefinitions": [FOO_PARAMETER_STRING],
                    "steps": [STEP_TEMPLATE_FOO],
                    "jobEnvironments": [
                        {
                            "name": "VariableEnv",
                            "variables": {
                                "VAR_NAME": "{{ Param.Foo }}",
                            },
                        }
                    ],
                }
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo {{Param.Foo}}",
                    "parameterDefinitions": [FOO_PARAMETER_INT],
                    "steps": [
                        {
                            "name": "BarStep",
                            "script": make_script(
                                "Task", "BarScript", "echo {{Param.Foo}} {{Task.Param.Foo}}"
                            ),
                            "parameterSpace": {
                                "taskParameterDefinitions": [
                                    {
                                        "name": "Foo",
                                        "type": "INT",
                                        "range": "1 - {{Param.Foo}}",
                                    }
                                ]
                            },
                        },
                    ],
                },
                id="int range expression can see params",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        # Parsing tests of valid Open Job Description JobTemplate
        # It is sufficient to check that parsing the input does not
        # raise an exception. We trust the Pydantic package's testing
        # so, if the input parses then our JobTemplate model is correctly
        # constructed for valid input.

        # WHEN
        _parse_model(model=JobTemplate, obj=data)

        # THEN
        # no exception was raised.

    @pytest.mark.parametrize(
        "data,error_count",
        (
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo {{Session.WorkingDirectory}}",
                    "steps": [STEP_TEMPLATE],
                },
                1,
                id="session working directory not in 'name' scope",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo {{Param.Foo}}",
                    "parameterDefinitions": [FOO_PARAMETER_PATH],
                    "steps": [STEP_TEMPLATE],
                },
                1,
                id="path parameter not in 'name' scope",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [STEP_TEMPLATE_FOO],
                },
                4,
                id="step missing parameter",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "parmDef": [FOO_PARAMETER_INT],
                    "steps": [STEP_TEMPLATE_FOO],
                },
                5,  # extra field + 2 param refs in each of command+args
                id="key error and path parameter 'Foo' missing",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [STEP_TEMPLATE],
                    "jobEnvironments": [ENVIRONMENT_FOO],
                },
                2,
                id="environment missing parameter",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [STEP_TEMPLATE_FOO],
                    "jobEnvironments": [ENVIRONMENT_FOO],
                },
                6,
                id="step and environment missing parameter",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "parameterDefinitions": [FOO_PARAMETER_PATH],
                    "steps": [
                        {
                            "name": "BarStep",
                            "script": make_script("Task", "BarScript", "echo"),
                            "parameterSpace": {
                                "taskParameterDefinitions": [
                                    {
                                        "name": "Foo",
                                        "type": "STRING",
                                        "range": ["blah", "{{Param.Foo}}"],
                                    }
                                ]
                            },
                        },
                    ],
                },
                1,
                id="parameter space cannot ref path parameter",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo {{Param.Foo}}",
                    "parameterDefinitions": [FOO_PARAMETER_STRING],
                    "steps": [
                        STEP_TEMPLATE_FOO,
                        {
                            "name": "BarStep",
                            "script": make_script(
                                "Task", "BarScript", "echo {{Task.File.BazScript}}"
                            ),
                        },
                        {
                            "name": "BazStep",
                            "script": make_script(
                                "Task", "BazScript", "echo {{Task.File.BarScript}}"
                            ),
                        },
                    ],
                },
                2,
                id="multiple steps can't reference other files",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "parameterDefinitions": [FOO_PARAMETER_INT],
                    "steps": [STEP_TEMPLATE_FOO],
                    "jobEnvironments": [
                        ENVIRONMENT_FOO,
                        {
                            "name": "BarEnv",
                            "script": make_script(
                                "Env", "BarScript", "echo {{Env.File.BazScript}}"
                            ),
                        },
                        {
                            "name": "BazEnv",
                            "script": make_script(
                                "Env", "BazScript", "echo {{Env.File.BarScript}}"
                            ),
                        },
                    ],
                },
                2,
                id="multiple environments can't reference other files",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo {{Param.Foo}}",
                    "parameterDefinitions": [FOO_PARAMETER_STRING],
                    "steps": [
                        {
                            "name": "BarStep",
                            "script": make_script(
                                "Task", "BarScript", "echo {{Param.Foo}} {{Task.Param.Foo}}"
                            ),
                            "parameterSpace": {
                                "taskParameterDefinitions": [
                                    {"name": "Foo", "type": "INT", "range": [1, 2]}
                                ]
                            },
                            "stepEnvironments": [
                                {
                                    "name": "BarEnv",
                                    "script": make_script(
                                        "Env",
                                        "BarScript",
                                        "echo {{Param.Foo}} {{Env.File.BarScript}} {{Session.WorkingDirectory}} {{Task.Param.Foo}}",
                                    ),
                                }
                            ],
                        },
                    ],
                },
                1,
                id="step environment cannot see task params",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo {{Param.Foo}}",
                    "parameterDefinitions": [FOO_PARAMETER_STRING],
                    "steps": [
                        {
                            "name": "BarStep",
                            "script": make_script(
                                "Task",
                                "BarScript",
                                "echo {{Param.Foo}} {{Task.Param.Foo}} {{Env.File.BarScript}}",
                            ),
                            "parameterSpace": {
                                "taskParameterDefinitions": [
                                    {"name": "Foo", "type": "INT", "range": [1, 2]}
                                ]
                            },
                            "stepEnvironments": [
                                {
                                    "name": "BarEnv",
                                    "script": make_script(
                                        "Env",
                                        "BarScript",
                                        "echo {{Param.Foo}} {{Env.File.BarScript}} {{Session.WorkingDirectory}}",
                                    ),
                                }
                            ],
                        },
                    ],
                },
                1,
                id="step script cannot see environment",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo {{Param.Foo}}",
                    "parameterDefinitions": [FOO_PARAMETER_STRING],
                    "steps": [
                        {
                            "name": "BarStep",
                            "script": make_script(
                                "Task",
                                "BarScript",
                                "echo {{Param.Foo}} {{Task.Param.Foo}} {{Task.Param.Bar}} {{Task.Param.Baz}}",
                            ),
                            "parameterSpace": {
                                "taskParameterDefinitions": [
                                    {"name": "Foo", "type": "INT", "range": [1, 2]},
                                    {"name": "Bar", "type": "FLOAT", "range": [1, 2]},
                                    {
                                        "name": "Baz",
                                        "type": "STRING",
                                        "range": [
                                            "{{Task.Param.Foo}}",  # Not other task params
                                            "{{Task.Param.Bar}}",
                                            "{{Task.Param.Baz}}",
                                            "{{Env.File.BarScript}}",  # Not env scripts
                                            "{{Session.WorkingDirectory}}",  # Not the session
                                        ],
                                    },
                                ]
                            },
                            "stepEnvironments": [
                                {
                                    "name": "BarEnv",
                                    "script": make_script(
                                        "Env",
                                        "BarScript",
                                        "echo {{Param.Foo}} {{Env.File.BarScript}} {{Session.WorkingDirectory}}",
                                    ),
                                }
                            ],
                        },
                    ],
                },
                5,
                id="task params cannot see each other, envs, or the session",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo {{Param.Foo}}",
                    "parameterDefinitions": [FOO_PARAMETER_STRING],
                    "steps": [
                        {
                            "name": "BarStep",
                            "script": make_script(
                                "Task",
                                "BarScript",
                                "echo {{Param.Foo}} {{Task.Param.Foo}} {{Task.Param.Bar}} {{Task.Param.Baz}}",
                            ),
                            "parameterSpace": {
                                "taskParameterDefinitions": [
                                    {"name": "Foo", "type": "INT", "range": [1, 2]},
                                    {"name": "Bar", "type": "FLOAT", "range": [1, 2]},
                                    {
                                        "name": "Baz",
                                        "type": "STRING",
                                        "range": [
                                            "{{Param.Foo}}",
                                            "BazValue",
                                        ],
                                    },
                                ]
                            },
                            "stepEnvironments": [
                                {
                                    "name": "BarEnv",
                                    "script": make_script(
                                        "Env",
                                        "BarScript",
                                        "echo {{Param.Foo}} {{Env.File.BarScript}} {{Session.WorkingDirectory}}",
                                    ),
                                }
                            ],
                        },
                        {
                            "name": "PubStep",
                            "script": make_script(
                                "Task",
                                "PubScript",
                                # errors: Task.Param.Foo, Task.Param.Bar, Task.Param.Baz
                                "echo {{Param.Foo}} {{Task.Param.Foo}} {{Task.Param.Bar}} {{Task.Param.Baz}} {{Task.Param.Pub1}} {{Task.Param.Pub2}}",
                            ),
                            "parameterSpace": {
                                "taskParameterDefinitions": [
                                    {"name": "Pub1", "type": "INT", "range": [1, 2]},
                                    {"name": "Pub2", "type": "FLOAT", "range": [1, 2]},
                                    {
                                        "name": "Pub3",
                                        "type": "STRING",
                                        "range": [
                                            # errors: Task.Param.Foo, Task.Param.Pub1
                                            "{{Task.Param.Foo}}",
                                            "{{Task.Param.Pub1}}",
                                        ],
                                    },
                                ]
                            },
                            "stepEnvironments": [
                                {
                                    "name": "PubEnv",
                                    "script": make_script(
                                        "Env",
                                        "PubScript",
                                        # errors: Env.File.BarScript
                                        "echo {{Param.Foo}} {{Env.File.PubScript}} {{Env.File.BarScript}} {{Session.WorkingDirectory}}",
                                    ),
                                }
                            ],
                        },
                    ],
                },
                6,
                id="task params cannot be seen across steps",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "parameterDefinitions": [FOO_PARAMETER_INT],
                    "jobEnvironments": [
                        {
                            "name": "BarEnv",
                            "script": make_script(
                                "Env", "BarScript", "echo {{Env.File.BarScript}}"
                            ),
                        },
                    ],
                    "steps": [
                        {
                            "name": "PubStep",
                            "script": make_script(
                                "Task",
                                "PubScript",
                                # errors: Env.File.BarScript, Env.File.PubScript
                                "echo {{Param.Foo}} {{Task.Param.Pub1}} {{Task.Param.Pub2}} {{Task.File.PubScript}}, {{Env.File.BarScript}} {{Env.File.PubScript}}",
                            ),
                            "parameterSpace": {
                                "taskParameterDefinitions": [
                                    {"name": "Pub1", "type": "INT", "range": [1, 2]},
                                    {"name": "Pub2", "type": "FLOAT", "range": [1, 2]},
                                ]
                            },
                            "stepEnvironments": [
                                {
                                    "name": "PubEnv",
                                    "script": make_script(
                                        "Env",
                                        "PubScript",
                                        # errors: Env.File.BarScript, Task.File.PubScript
                                        "echo {{Param.Foo}} {{Env.File.PubScript}} {{Env.File.BarScript}} {{Task.File.PubScript}} {{Session.WorkingDirectory}}",
                                    ),
                                }
                            ],
                        },
                    ],
                },
                4,
                id="files from job env cannot be seen in step scripts or step envs",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [
                        {
                            "name": "BarStep",
                            "script": make_script(
                                "Task",
                                "BarScript",
                                "echo 'Hi there''",
                            ),
                            "parameterSpace": {
                                "taskParameterDefinitions": [
                                    {
                                        "name": "Baz",
                                        "type": "STRING",
                                        "range": [
                                            "{{Session.WorkingDirectory}}",  # Not the session dir
                                            "{{Session.HasPathMappingRules}}",  # Not the path mapping reference
                                            "{{Session.PathMappingRulesFile}}",  # Not the path mapping file reference
                                        ],
                                    },
                                ]
                            },
                        },
                    ],
                },
                3,
                id="Cannot reference Session values in a Task Parameter",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [
                        {
                            "name": "BarStep",
                            "script": make_script(
                                "Task",
                                "BarScript",
                                "echo 'Hi there''",
                            ),
                            "hostRequirements": {
                                "amounts": [
                                    {
                                        "name": "amount.{{Session.PathMappingRulesFile}}",
                                        "min": 3,
                                    },
                                ],
                                "attributes": [
                                    {
                                        "name": "attr.{{Session.WorkingDirectory}}",
                                        "anyOf": ["{{Session.HasPathMappingRules}}"],
                                    },
                                ],
                            },
                        },
                    ],
                },
                3,
                id="Cannot reference Session values in a Capability",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "steps": [
                        {
                            "name": "BarStep",
                            "stepEnvironments": [
                                {
                                    "name": "StepEnvA",
                                    "script": {
                                        "embeddedFiles": [
                                            {
                                                "name": "fileA",
                                                "type": "TEXT",
                                                # References the other step env
                                                "data": "{{Env.File.file1}}",
                                            },
                                        ],
                                        "actions": {
                                            # References the other step env
                                            "onEnter": {"command": "{{Env.File.file1}}"},
                                        },
                                    },
                                },
                                {
                                    "name": "StepEnv1",
                                    "script": {
                                        "embeddedFiles": [
                                            {
                                                "name": "file1",
                                                "type": "TEXT",
                                                # References the other step env
                                                "data": "{{Env.File.fileA}}",
                                            },
                                        ],
                                        "actions": {
                                            # References the other step env
                                            "onEnter": {"command": "{{Env.File.fileA}}"},
                                        },
                                    },
                                },
                            ],
                            "script": {
                                "actions": {"onRun": {"command": "foo"}},
                            },
                        },
                    ],
                },
                4,
                id="embedded env script files cannot reference other envs",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "jobEnvironments": [
                        {
                            "name": "BarEnv",
                            "script": make_script(
                                "Env", "BarScript", "echo {{Env.File.BarScript}}"
                            ),
                        },
                    ],
                    "steps": [
                        {
                            "name": "BarStep",
                            "parameterSpace": {
                                "taskParameterDefinitions": [
                                    {"name": "Pub1", "type": "INT", "range": [1, 2]},
                                    {"name": "Pub2", "type": "FLOAT", "range": [1, 2]},
                                ]
                            },
                            "stepEnvironments": [
                                {
                                    "name": "StepEnvA",
                                    "script": {
                                        "embeddedFiles": [
                                            {
                                                "name": "fileA",
                                                "type": "TEXT",
                                                "data": "filedata",
                                            },
                                        ],
                                        "actions": {
                                            "onEnter": {"command": "filedata"},
                                        },
                                    },
                                },
                                {
                                    "name": "StepEnv1",
                                    "script": {
                                        "actions": {
                                            "onEnter": {"command": "command"},
                                        },
                                    },
                                },
                            ],
                            "script": {
                                "actions": {"onRun": {"command": "foo"}},
                                "embeddedFiles": [
                                    {
                                        "name": "file1",
                                        "type": "TEXT",
                                        "data": "filedata",
                                    },
                                ],
                            },
                            "hostRequirements": {
                                "amounts": [
                                    {
                                        # Reference a job environment file
                                        "name": "amount.{{Env.File.BarScript}}",
                                        "min": 3,
                                    },
                                ],
                                "attributes": [
                                    {
                                        # Reference a step script file
                                        "name": "attr.{{Env.File.file1}}",
                                        # Reference a step environment file, and two task parameters
                                        "anyOf": [
                                            "{{Env.File.fileA}}",
                                            "{{Task.Param.Pub1}} {{Task.Param.Pub2}}",
                                        ],
                                    },
                                ],
                            },
                        },
                    ],
                },
                5,
                id="Capabilities cannot reference envs or steps",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo",
                    "parameterDefinitions": [FOO_PARAMETER_STRING],
                    "steps": [STEP_TEMPLATE_FOO],
                    "jobEnvironments": [
                        {
                            "name": "VariableEnv",
                            "variables": {
                                "VAR_NAME": "{{ Param.DoNotCreateAParamWithThisName }}",
                            },
                        }
                    ],
                },
                1,
                id="Environment variable value referencing non-existant parameter",
            ),
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Foo {{Param.Foo}}",
                    "parameterDefinitions": [FOO_PARAMETER_INT],
                    "steps": [
                        {
                            "name": "BarStep",
                            "script": make_script(
                                "Task", "BarScript", "echo {{Param.Foo}} {{Task.Param.Foo}}"
                            ),
                            "parameterSpace": {
                                "taskParameterDefinitions": [
                                    {"name": "Foo", "type": "INT", "range": "1-{{Fake.Parameter}}"}
                                ]
                            },
                        },
                    ],
                },
                1,
                id="int range expression fails on fake format string",
            ),
            # Test that we still properly collect parameter definitions for format string
            # validation when we have a validation error in a parameter definition.
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "DemoJob",
                    "parameterDefinitions": [
                        {"name": "Foo", "type": "INT", "default": "Blah"},
                        {"name": "Fuzz", "type": "INT"},
                    ],
                    "steps": [
                        {
                            "name": "DemoStep",
                            "parameterSpace": {
                                "taskParameterDefinitions": [
                                    {"name": "Foo", "type": "INT", "range": "a-b"},
                                    {"name": "Fuzz", "type": "INT", "range": "1-10"},
                                ]
                            },
                            "script": {
                                "actions": {
                                    "onRun": {
                                        "command": "echo",
                                        "args": [
                                            "{{Param.Foo}}",
                                            "{{Param.Fuzz}}",
                                            "{{Task.Param.Foo}}",
                                            "{{Task.Param.Fuzz}}",
                                        ],
                                    }
                                }
                            },
                        }
                    ],
                },
                2,  # Validation of Job Foo & Task Foo
                id="all parameter symbols are defined when validation errors",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any], error_count: int) -> None:
        # Failure case testing for Open Job Description JobTemplate.

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=JobTemplate, obj=data)

        # THEN
        assert len(excinfo.value.errors()) == error_count, str(excinfo.value)
