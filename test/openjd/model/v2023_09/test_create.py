# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

# Testing for the model metadata annotations that assist in generating a Job from the
# Job Template

from openjd.model import ParameterValue, ParameterValueType, create_job
from openjd.model.v2023_09 import (
    Action,
    AmountRequirement,
    AmountRequirementTemplate,
    AttributeRequirement,
    AttributeRequirementTemplate,
    CancelationMethodNotifyThenTerminate,
    CancelationMethodTerminate,
    EmbeddedFileText,
    Environment,
    EnvironmentActions,
    EnvironmentScript,
    FloatTaskParameterDefinition,
    HostRequirements,
    HostRequirementsTemplate,
    IntTaskParameterDefinition,
    Job,
    JobFloatParameterDefinition,
    JobIntParameterDefinition,
    JobParameter,
    JobStringParameterDefinition,
    JobTemplate,
    RangeExpressionTaskParameterDefinition,
    RangeListTaskParameterDefinition,
    Step,
    StepActions,
    StepParameterSpace,
    StepParameterSpaceDefinition,
    StepScript,
    StepTemplate,
    StringTaskParameterDefinition,
)


class TestCreateJob:
    def test(self) -> None:
        # One big test that does everything relevant for the create-job annotations.
        # Should be the only test that we need.
        #
        # Key things:
        #  1) Every format string has a job parameter reference - only some should be
        #     evaluated when creating jobs
        #     Specifically, only job name & task parameter range values should be evaluated.
        #  2) Every entity and every field that exists is defined at least once.
        #  3) Testing of _internal.create_job covers corner cases & exceptions; we don't worry
        #     about those here.

        # GIVEN
        extra_kwargs = {"$schema": "blah "}  # special snowflake due to field naming
        template = JobTemplate(
            **extra_kwargs,
            specificationVersion="jobtemplate-2023-09",
            name="{{ Param.StringParam }}",
            description="job description",
            jobEnvironments=[
                Environment(
                    name="JobEnv",
                    description="desc",
                    script=EnvironmentScript(
                        embeddedFiles=[
                            EmbeddedFileText(
                                name="File",
                                type="TEXT",
                                data="some data {{ Param.IntParam }}",
                                filename="filename.txt",
                                runnable=False,
                            )
                        ],
                        actions=EnvironmentActions(
                            onEnter=Action(
                                command="{{ Param.IntParam }}",
                                args=["{{ Param.FloatParam }}"],
                                timeout=10,
                                cancelation=CancelationMethodTerminate(mode="TERMINATE"),
                            ),
                            onExit=Action(
                                command="{{ Param.IntParam }}",
                                args=["{{ Param.FloatParam }}"],
                                timeout=10,
                                cancelation=CancelationMethodNotifyThenTerminate(
                                    mode="NOTIFY_THEN_TERMINATE", notifyPeriodInSeconds=30
                                ),
                            ),
                        ),
                    ),
                )
            ],
            parameterDefinitions=[
                JobStringParameterDefinition(
                    name="StringParam",
                    type="STRING",
                    description="desc",
                    minLength=1,
                    maxLength=20,
                    allowedValues=["TheJobName", "TheOtherJobName"],
                    default="TheOtherJobName",
                ),
                JobStringParameterDefinition(
                    name="AttrCapabilityName",
                    type="STRING",
                    description="desc",
                    minLength=1,
                    maxLength=20,
                    default="attr.mycapability",
                ),
                JobStringParameterDefinition(
                    name="AmountCapabilityName",
                    type="STRING",
                    description="desc",
                    minLength=1,
                    maxLength=20,
                    default="amount.mycapability",
                ),
                JobIntParameterDefinition(
                    name="RangeExpressionParam",
                    type="INT",
                    description="desc",
                    minValue=0,
                    maxValue=100,
                    allowedValues=[3, 75],
                    default=75,
                ),
                JobIntParameterDefinition(
                    name="IntParam",
                    type="INT",
                    description="desc",
                    minValue=0,
                    maxValue=100,
                    allowedValues=[5, 10, 20],
                    default=20,
                ),
                JobFloatParameterDefinition(
                    name="FloatParam",
                    type="FLOAT",
                    description="desc",
                    minValue=0.0,
                    maxValue=100.5,
                    allowedValues=[5, 10, "20.0"],
                    default=20,
                ),
            ],
            steps=[
                StepTemplate(
                    name="StepName",
                    description="desc",
                    stepEnvironments=[
                        Environment(
                            name="StepEnv",
                            description="desc",
                            script=EnvironmentScript(
                                embeddedFiles=[
                                    EmbeddedFileText(
                                        name="File",
                                        type="TEXT",
                                        data="some data {{ Param.IntParam }}",
                                        filename="filename.txt",
                                        runnable=False,
                                    )
                                ],
                                actions=EnvironmentActions(
                                    onEnter=Action(
                                        command="{{ Param.IntParam }}",
                                        args=["{{ Param.FloatParam }}"],
                                        timeout=10,
                                        cancelation=CancelationMethodTerminate(mode="TERMINATE"),
                                    ),
                                    onExit=Action(
                                        command="{{ Param.IntParam }}",
                                        args=["{{ Param.FloatParam }}"],
                                        timeout=10,
                                        cancelation=CancelationMethodNotifyThenTerminate(
                                            mode="NOTIFY_THEN_TERMINATE", notifyPeriodInSeconds=30
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    ],
                    parameterSpace=StepParameterSpaceDefinition(
                        taskParameterDefinitions=[
                            IntTaskParameterDefinition(
                                name="ParamE",
                                type="INT",
                                range="2 - {{ Param.RangeExpressionParam }}",
                            ),
                            IntTaskParameterDefinition(
                                name="ParamI", type="INT", range=[0, "{{ Param.IntParam }}"]
                            ),
                            FloatTaskParameterDefinition(
                                name="ParamF", type="FLOAT", range=[1.1, "{{ Param.FloatParam }}"]
                            ),
                            StringTaskParameterDefinition(
                                name="ParamS",
                                type="STRING",
                                range=["foo", "{{ Param.StringParam }}"],
                            ),
                        ],
                        combination="ParamS * ParamF * ParamI * ParamE",
                    ),
                    script=StepScript(
                        embeddedFiles=[
                            EmbeddedFileText(
                                name="File",
                                type="TEXT",
                                data="some data {{ Param.IntParam }}",
                                filename="filename.txt",
                                runnable=False,
                            )
                        ],
                        actions=StepActions(
                            onRun=Action(
                                command="{{ Param.IntParam }}",
                                args=["{{ Param.FloatParam }}"],
                                timeout=10,
                                cancelation=CancelationMethodTerminate(mode="TERMINATE"),
                            )
                        ),
                    ),
                    hostRequirements=HostRequirementsTemplate(
                        amounts=[
                            AmountRequirementTemplate(name="amount.worker.vcpu", min=3, max=8),
                            AmountRequirementTemplate(name="{{Param.AmountCapabilityName}}", min=2),
                        ],
                        attributes=[
                            AttributeRequirementTemplate(
                                name="attr.worker.os.family", anyOf=["linux"]
                            ),
                            AttributeRequirementTemplate(
                                name="{{Param.AttrCapabilityName}}", allOf=["{{Param.StringParam}}"]
                            ),
                        ],
                    ),
                )
            ],
        )
        job_parameter_values = {
            "IntParam": ParameterValue(type=ParameterValueType.INT, value="10"),
            "FloatParam": ParameterValue(type=ParameterValueType.FLOAT, value="10"),
            "RangeExpressionParam": ParameterValue(type=ParameterValueType.STRING, value="3"),
            # StringParam intentionally left undefined so that we get the default value
        }

        # WHEN
        result = create_job(job_template=template, job_parameter_values=job_parameter_values)

        # THEN
        expected = Job(
            name="TheOtherJobName",
            description="job description",
            jobEnvironments=[
                Environment(
                    name="JobEnv",
                    description="desc",
                    script=EnvironmentScript(
                        embeddedFiles=[
                            EmbeddedFileText(
                                name="File",
                                type="TEXT",
                                data="some data {{ Param.IntParam }}",
                                filename="filename.txt",
                                runnable=False,
                            )
                        ],
                        actions=EnvironmentActions(
                            onEnter=Action(
                                command="{{ Param.IntParam }}",
                                args=["{{ Param.FloatParam }}"],
                                timeout=10,
                                cancelation=CancelationMethodTerminate(mode="TERMINATE"),
                            ),
                            onExit=Action(
                                command="{{ Param.IntParam }}",
                                args=["{{ Param.FloatParam }}"],
                                timeout=10,
                                cancelation=CancelationMethodNotifyThenTerminate(
                                    mode="NOTIFY_THEN_TERMINATE", notifyPeriodInSeconds=30
                                ),
                            ),
                        ),
                    ),
                )
            ],
            parameters={
                "StringParam": JobParameter(
                    type="STRING", description="desc", value="TheOtherJobName"
                ),
                "AttrCapabilityName": JobParameter(
                    type="STRING", description="desc", value="attr.mycapability"
                ),
                "AmountCapabilityName": JobParameter(
                    type="STRING", description="desc", value="amount.mycapability"
                ),
                "RangeExpressionParam": JobParameter(type="INT", description="desc", value="3"),
                "IntParam": JobParameter(type="INT", description="desc", value="10"),
                "FloatParam": JobParameter(type="FLOAT", description="desc", value="10"),
            },
            steps=[
                Step(
                    name="StepName",
                    description="desc",
                    stepEnvironments=[
                        Environment(
                            name="StepEnv",
                            description="desc",
                            script=EnvironmentScript(
                                embeddedFiles=[
                                    EmbeddedFileText(
                                        name="File",
                                        type="TEXT",
                                        data="some data {{ Param.IntParam }}",
                                        filename="filename.txt",
                                        runnable=False,
                                    )
                                ],
                                actions=EnvironmentActions(
                                    onEnter=Action(
                                        command="{{ Param.IntParam }}",
                                        args=["{{ Param.FloatParam }}"],
                                        timeout=10,
                                        cancelation=CancelationMethodTerminate(mode="TERMINATE"),
                                    ),
                                    onExit=Action(
                                        command="{{ Param.IntParam }}",
                                        args=["{{ Param.FloatParam }}"],
                                        timeout=10,
                                        cancelation=CancelationMethodNotifyThenTerminate(
                                            mode="NOTIFY_THEN_TERMINATE", notifyPeriodInSeconds=30
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    ],
                    parameterSpace=StepParameterSpace(
                        taskParameterDefinitions={
                            "ParamE": RangeExpressionTaskParameterDefinition(
                                type="INT", range="2 - 3"
                            ),
                            "ParamI": RangeListTaskParameterDefinition(
                                type="INT", range=["0", "10"]
                            ),
                            "ParamF": RangeListTaskParameterDefinition(
                                type="FLOAT", range=["1.1", "10"]
                            ),
                            "ParamS": RangeListTaskParameterDefinition(
                                type="STRING", range=["foo", "TheOtherJobName"]
                            ),
                        },
                        combination="ParamS * ParamF * ParamI * ParamE",
                    ),
                    script=StepScript(
                        embeddedFiles=[
                            EmbeddedFileText(
                                name="File",
                                type="TEXT",
                                data="some data {{ Param.IntParam }}",
                                filename="filename.txt",
                                runnable=False,
                            )
                        ],
                        actions=StepActions(
                            onRun=Action(
                                command="{{ Param.IntParam }}",
                                args=["{{ Param.FloatParam }}"],
                                timeout=10,
                                cancelation=CancelationMethodTerminate(mode="TERMINATE"),
                            )
                        ),
                    ),
                    hostRequirements=HostRequirements(
                        amounts=[
                            AmountRequirement(name="amount.worker.vcpu", min=3, max=8),
                            AmountRequirement(name="amount.mycapability", min=2),
                        ],
                        attributes=[
                            AttributeRequirement(name="attr.worker.os.family", anyOf=["linux"]),
                            AttributeRequirement(
                                name="attr.mycapability", allOf=["TheOtherJobName"]
                            ),
                        ],
                    ),
                )
            ],
        )

        # Note: The dict compare generates an easier to read diff if there's a test failure.
        #  It is not essential to the test.
        assert result.dict() == expected.dict()
        # This is the important assertion.
        assert result == expected
