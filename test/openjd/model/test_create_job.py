# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest

from openjd.model import (
    JobParameterInputValues,
    ParameterValue,
    ParameterValueType,
    preprocess_job_parameters,
)
from openjd.model._parse import _parse_model
from openjd.model.v2023_09 import (
    JobParameterType as JobParameterType_2023_09,
)
from openjd.model.v2023_09 import JobTemplate as JobTemplate_2023_09

minimal_job_template_2023_09 = _parse_model(
    model=JobTemplate_2023_09,
    obj={
        "specificationVersion": "jobtemplate-2023-09",
        "name": "name",
        "steps": [{"name": "step", "script": {"actions": {"onRun": {"command": "do thing"}}}}],
    },
)


class TestPreprocessJobParameters_2023_09:  # noqa: N801
    """Tests for preprocess_job_parameters with the 2023-09 schema."""

    @pytest.mark.parametrize(
        "param_type",
        [pytest.param(param.value, id=f"{param.value} type") for param in JobParameterType_2023_09],
    )
    def test_handles_parameter_type(self, param_type: str) -> None:
        # Test that we can process all known kinds of parameters

        # GIVEN
        job_parameter_values: JobParameterInputValues = {"Foo": "12"}
        job_template = JobTemplate_2023_09(
            specificationVersion="jobtemplate-2023-09",
            name="test",
            steps=minimal_job_template_2023_09.steps,
            parameterDefinitions=[{"name": "Foo", "type": param_type}],
        )

        # WHEN
        result = preprocess_job_parameters(
            job_template=job_template, job_parameter_values=job_parameter_values
        )

        # THEN
        assert len(result) == 1
        assert "Foo" in result
        assert result["Foo"].value == "12"
        assert result["Foo"].type == ParameterValueType(param_type)

    def test_reports_extra(self) -> None:
        # Test that we get errors if we have extra job parameters defined.

        # GIVEN
        job_parameter_values: JobParameterInputValues = {"ThisIsUnknown": "value"}
        job_template = JobTemplate_2023_09(
            specificationVersion="jobtemplate-2023-09",
            name="test",
            steps=minimal_job_template_2023_09.steps,
        )

        # WHEN
        with pytest.raises(ValueError) as excinfo:
            preprocess_job_parameters(
                job_template=job_template, job_parameter_values=job_parameter_values
            )

        # THEN
        assert (
            "Job parameter values provided for parameters that are not defined in the template: ThisIsUnknown"
            in str(excinfo.value)
        )

    def test_reports_missing(self) -> None:
        # Test that we get errors if we have missed defining job parameters

        # GIVEN
        job_parameter_values: JobParameterInputValues = dict()
        job_template = JobTemplate_2023_09(
            specificationVersion="jobtemplate-2023-09",
            name="test",
            parameterDefinitions=[{"name": "ThisIsNotDefined", "type": "STRING"}],
            steps=minimal_job_template_2023_09.steps,
        )

        # WHEN
        with pytest.raises(ValueError) as excinfo:
            preprocess_job_parameters(
                job_template=job_template, job_parameter_values=job_parameter_values
            )

        # THEN
        assert "Values missing for required job parameters: ThisIsNotDefined" in str(excinfo.value)

    def test_collects_defaults(self) -> None:
        # Test that we add values for missing job parameters that have
        # defaults defined.

        # GIVEN
        job_parameter_values: JobParameterInputValues = {}
        job_template = JobTemplate_2023_09(
            specificationVersion="jobtemplate-2023-09",
            name="test",
            parameterDefinitions=[{"name": "Foo", "type": "STRING", "default": "defaultValue"}],
            steps=minimal_job_template_2023_09.steps,
        )

        # WHEN
        result = preprocess_job_parameters(
            job_template=job_template, job_parameter_values=job_parameter_values
        )

        # THEN
        assert "Foo" in result
        assert result["Foo"] == ParameterValue(type=ParameterValueType.STRING, value="defaultValue")

    def test_ignores_defaults(self) -> None:
        # Test that we do not add values for job parameters that have
        # defaults defined, but that we've already defined.

        # GIVEN
        job_parameter_values: JobParameterInputValues = {"Foo": "FooValue"}
        job_template = JobTemplate_2023_09(
            specificationVersion="jobtemplate-2023-09",
            name="test",
            parameterDefinitions=[{"name": "Foo", "type": "STRING", "default": "defaultValue"}],
            steps=minimal_job_template_2023_09.steps,
        )

        # WHEN
        result = preprocess_job_parameters(
            job_template=job_template, job_parameter_values=job_parameter_values
        )

        # THEN
        assert "Foo" in result
        assert result["Foo"] == ParameterValue(type=ParameterValueType.STRING, value="FooValue")

    def test_checks_contraints(self) -> None:
        # Test that we see errors if a constraint is violated.

        # GIVEN
        job_parameter_values: JobParameterInputValues = {"Foo": "two"}
        job_template = JobTemplate_2023_09(
            specificationVersion="jobtemplate-2023-09",
            name="test",
            parameterDefinitions=[{"name": "Foo", "type": "STRING", "maxLength": 1}],
            steps=minimal_job_template_2023_09.steps,
        )

        # WHEN
        with pytest.raises(ValueError) as excinfo:
            preprocess_job_parameters(
                job_template=job_template, job_parameter_values=job_parameter_values
            )

        # THEN
        assert "parameter Foo value must be at most 1 characters" in str(excinfo.value)
        assert len(str(excinfo.value).split("\n")) == 1

    def test_collects_multiple_errors(self) -> None:
        # Test that see all errors if we have multiple in the same run.

        # GIVEN
        job_parameter_values: JobParameterInputValues = {
            "Foo": "two",  # Too long of a value
            "Bar": "three",  # An extra parameter
            # missing buz
        }
        job_template = JobTemplate_2023_09(
            specificationVersion="jobtemplate-2023-09",
            name="test",
            parameterDefinitions=[
                {"name": "Foo", "type": "STRING", "maxLength": 1},
                {"name": "Buz", "type": "STRING"},
            ],
            steps=minimal_job_template_2023_09.steps,
        )

        # WHEN
        with pytest.raises(ValueError) as excinfo:
            preprocess_job_parameters(
                job_template=job_template, job_parameter_values=job_parameter_values
            )

        # THEN
        assert "parameter Foo value must be at most 1 characters" in str(excinfo.value)
        assert (
            "Job parameter values provided for parameters that are not defined in the template: Bar"
            in str(excinfo.value)
        )
        assert "Values missing for required job parameters: Buz" in str(excinfo.value)
        assert len(str(excinfo.value).split("\n")) == 3
