# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import os
import tempfile
import pytest
from pathlib import Path
from typing import Any

from openjd.model import (
    DecodeValidationError,
    JobParameterInputValues,
    ParameterValue,
    ParameterValueType,
    create_job,
    preprocess_job_parameters,
)
from openjd.model._parse import _parse_model
from openjd.model.v2023_09 import (
    Environment as Environment_2023_09,
    EnvironmentTemplate as EnvironmentTemplate_2023_09,
    Job as Job_2023_09,
    JobTemplate as JobTemplate_2023_09,
    JobParameterType as JobParameterType_2023_09,
)

minimal_job_template_2023_09 = _parse_model(
    model=JobTemplate_2023_09,
    obj={
        "specificationVersion": "jobtemplate-2023-09",
        "name": "name",
        "steps": [{"name": "step", "script": {"actions": {"onRun": {"command": "do thing"}}}}],
    },
)
minimal_environment_2023_09 = _parse_model(
    model=Environment_2023_09,
    obj={"name": "env", "script": {"actions": {"onEnter": {"command": "do a thing"}}}},
)


class TestPreprocessJobParameters_2023_09:  # noqa: N801
    """Tests for preprocess_job_parameters with the 2023-09 schema."""

    template_dir: Path
    current_working_dir: Path

    @staticmethod
    @pytest.fixture(scope="class", autouse=True)
    def fake_template_dir_and_cwd():
        """Creates two temporary directories for the test to use as the template dir and cwd, respectively."""
        with tempfile.TemporaryDirectory() as tmpdir:
            TestPreprocessJobParameters_2023_09.template_dir = Path(tmpdir) / "template_dir"
            TestPreprocessJobParameters_2023_09.current_working_dir = (
                Path(tmpdir) / "current_working_dir"
            )
            os.makedirs(TestPreprocessJobParameters_2023_09.template_dir)
            os.makedirs(TestPreprocessJobParameters_2023_09.current_working_dir)
            yield None

    @pytest.mark.parametrize(
        "param_type",
        [
            pytest.param(param_type.value, id=f"{param_type.value} type")
            for param_type in JobParameterType_2023_09
        ],
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
            job_template=job_template,
            job_parameter_values=job_parameter_values,
            job_template_dir=self.template_dir,
            current_working_dir=self.current_working_dir,
        )

        # THEN
        assert len(result) == 1
        assert "Foo" in result
        if param_type == "PATH":
            # "12" is a relative path that gets joined with the current working directory
            assert result["Foo"].value == str(self.current_working_dir / "12")
        else:
            assert result["Foo"].value == "12"
        assert result["Foo"].type == ParameterValueType(param_type)

    @pytest.mark.parametrize(
        "param_type",
        [
            pytest.param(param_type.value, id=f"{param_type.value} type")
            for param_type in JobParameterType_2023_09
        ],
    )
    def test_handles_parameter_type_without_path_escape_validation(self, param_type: str) -> None:
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
            job_template=job_template,
            job_parameter_values=job_parameter_values,
            job_template_dir=Path(),
            current_working_dir=Path(),
            allow_job_template_dir_walk_up=True,
        )

        # THEN
        assert len(result) == 1
        assert "Foo" in result
        # "12" remains the same relative path when used as a PATH parameter
        assert result["Foo"].value == "12"
        assert result["Foo"].type == ParameterValueType(param_type)

    @pytest.mark.parametrize(
        "escaping_dir,expect_in_exc",
        [
            pytest.param(
                "..",
                "references a path outside of the template directory",
                id="relative dir up one level",
            ),
            pytest.param(
                "./..",
                "references a path outside of the template directory",
                id="relative dir up one level variation 1",
            ),
            pytest.param(
                "../.",
                "references a path outside of the template directory",
                id="relative dir one level variation 2",
            ),
            pytest.param(
                "down/down/../../down/../..",
                "references a path outside of the template directory",
                id="up and down, ending up escaped",
            ),
            pytest.param(
                os.getcwd(),
                "is an absolute path. Default paths must be relative, and are joined to the job template's directory.",
                id="current working directory, an abs path",
            ),
        ],
    )
    def test_path_parameter_default_cannot_escape(
        self, escaping_dir: str, expect_in_exc: str
    ) -> None:
        # Test that defaults provided for path parameters are not permitted to escape the job template directory

        # GIVEN
        job_parameter_values: JobParameterInputValues = {}
        job_template = JobTemplate_2023_09(
            specificationVersion="jobtemplate-2023-09",
            name="test",
            steps=minimal_job_template_2023_09.steps,
            parameterDefinitions=[{"name": "Foo", "type": "PATH", "default": escaping_dir}],
        )

        # WHEN
        with pytest.raises(ValueError) as excinfo:
            preprocess_job_parameters(
                job_template=job_template,
                job_parameter_values=job_parameter_values,
                job_template_dir=self.template_dir,
                current_working_dir=self.current_working_dir,
            )

        # THEN
        assert expect_in_exc in str(excinfo.value)

    def test_job_template_dir_must_be_absolute(self) -> None:
        # Test that the provided job template dir must be absolute (by default)

        # GIVEN
        job_parameter_values: JobParameterInputValues = {}
        job_template = JobTemplate_2023_09(
            specificationVersion="jobtemplate-2023-09",
            name="test",
            steps=minimal_job_template_2023_09.steps,
            parameterDefinitions=[{"name": "Foo", "type": "PATH", "default": "defaultValue"}],
        )

        # WHEN
        with pytest.raises(ValueError) as excinfo:
            preprocess_job_parameters(
                job_template=job_template,
                job_parameter_values=job_parameter_values,
                job_template_dir=Path("relative/path"),
                current_working_dir=self.current_working_dir,
            )

        # THEN
        assert "the job template dir" in str(excinfo.value)
        assert "is not an absolute path. It must be absolute to enforce that" in str(excinfo.value)

    @pytest.mark.parametrize(
        "escaping_dir",
        [
            pytest.param("..", id="relative dir up one level"),
            pytest.param("./..", id="relative dir up one level variation 1"),
            pytest.param("../.", id="relative dir one level variation 2"),
            pytest.param("down/down/../../down/../..", id="up and down, ending up escaped"),
            pytest.param(os.getcwd(), id="current working directory, an abs path"),
        ],
    )
    def test_path_parameter_default_escape_without_validation(self, escaping_dir: str) -> None:
        # Test that when path parameters are permitted to escape, the result is a normalized path join.

        # GIVEN
        job_parameter_values: JobParameterInputValues = {}
        job_template = JobTemplate_2023_09(
            specificationVersion="jobtemplate-2023-09",
            name="test",
            steps=minimal_job_template_2023_09.steps,
            parameterDefinitions=[{"name": "Foo", "type": "PATH", "default": escaping_dir}],
        )

        # WHEN
        result = preprocess_job_parameters(
            job_template=job_template,
            job_parameter_values=job_parameter_values,
            job_template_dir=self.template_dir,
            current_working_dir=self.current_working_dir,
            allow_job_template_dir_walk_up=True,
        )

        # THEN
        assert "Foo" in result
        assert result["Foo"] == ParameterValue(
            type=ParameterValueType.PATH, value=os.path.normpath(self.template_dir / escaping_dir)
        )

    @pytest.mark.parametrize(
        "escaping_dir",
        [
            pytest.param("..", id="relative dir up one level"),
            pytest.param("./..", id="relative dir up one level variation 1"),
            pytest.param("../.", id="relative dir one level variation 2"),
            pytest.param("down/down/../../down/../..", id="up and down, ending up escaped"),
            pytest.param(os.getcwd(), id="current working directory, an abs path"),
        ],
    )
    def test_path_parameter_default_escape_without_validation_and_empty_paths(
        self, escaping_dir: str
    ) -> None:
        # Test that when path parameters are permitted to escape, and empty paths are provided
        # for the template dir and cwd, the result is to leave the input as-is.

        # GIVEN
        job_parameter_values: JobParameterInputValues = {}
        job_template = JobTemplate_2023_09(
            specificationVersion="jobtemplate-2023-09",
            name="test",
            steps=minimal_job_template_2023_09.steps,
            parameterDefinitions=[{"name": "Foo", "type": "PATH", "default": escaping_dir}],
        )

        # WHEN
        result = preprocess_job_parameters(
            job_template=job_template,
            job_parameter_values=job_parameter_values,
            job_template_dir=Path(),
            current_working_dir=Path(),
            allow_job_template_dir_walk_up=True,
        )

        # THEN
        assert "Foo" in result
        assert result["Foo"] == ParameterValue(type=ParameterValueType.PATH, value=escaping_dir)

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
                job_template=job_template,
                job_parameter_values=job_parameter_values,
                job_template_dir=self.template_dir,
                current_working_dir=self.current_working_dir,
            )

        # THEN
        assert (
            "Job parameter values provided for parameters that are not defined in the template: ThisIsUnknown"
            in str(excinfo.value)
        )

    def test_reports_extra_with_environments(self) -> None:
        # Test that we get errors if we have extra job parameters defined.

        # GIVEN
        job_parameter_values: JobParameterInputValues = {
            "ThisIsUnknown": "value",
            "ThisIsKnown": "value",
        }
        job_template = JobTemplate_2023_09(
            specificationVersion="jobtemplate-2023-09",
            name="test",
            steps=minimal_job_template_2023_09.steps,
        )
        env_template = EnvironmentTemplate_2023_09(
            specificationVersion="environment-2023-09",
            environment=minimal_environment_2023_09,
            parameterDefinitions=[{"name": "ThisIsKnown", "type": "STRING"}],
        )

        # WHEN
        with pytest.raises(ValueError) as excinfo:
            preprocess_job_parameters(
                job_template=job_template,
                job_parameter_values=job_parameter_values,
                job_template_dir=self.template_dir,
                current_working_dir=self.current_working_dir,
                environment_templates=[env_template],
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
                job_template=job_template,
                job_parameter_values=job_parameter_values,
                job_template_dir=self.template_dir,
                current_working_dir=self.current_working_dir,
            )

        # THEN
        assert "Values missing for required job parameters: ThisIsNotDefined" in str(excinfo.value)

    def test_reports_missing_with_environments(self) -> None:
        # Test that we get errors if we have missed defining job parameters

        # GIVEN
        job_parameter_values: JobParameterInputValues = dict()
        job_template = JobTemplate_2023_09(
            specificationVersion="jobtemplate-2023-09",
            name="test",
            parameterDefinitions=[{"name": "ThisIsNotDefined", "type": "STRING"}],
            steps=minimal_job_template_2023_09.steps,
        )
        env_template = EnvironmentTemplate_2023_09(
            specificationVersion="environment-2023-09",
            environment=minimal_environment_2023_09,
            parameterDefinitions=[{"name": "ThisIsAlsoMissing", "type": "STRING"}],
        )

        # WHEN
        with pytest.raises(ValueError) as excinfo:
            preprocess_job_parameters(
                job_template=job_template,
                job_parameter_values=job_parameter_values,
                job_template_dir=self.template_dir,
                current_working_dir=self.current_working_dir,
                environment_templates=[env_template],
            )

        # THEN
        assert (
            "Values missing for required job parameters: ThisIsAlsoMissing, ThisIsNotDefined"
            in str(excinfo.value)
        )

    def test_collects_defaults(self) -> None:
        # Test that we add values for missing job parameters that have
        # defaults defined.

        # GIVEN
        job_parameter_values: JobParameterInputValues = {}
        job_template = JobTemplate_2023_09(
            specificationVersion="jobtemplate-2023-09",
            name="test",
            parameterDefinitions=[
                {"name": "Foo", "type": "STRING", "default": "defaultValue"},
                {"name": "Bar", "type": "PATH", "default": "defaultPathValue"},
            ],
            steps=minimal_job_template_2023_09.steps,
        )

        # WHEN
        result = preprocess_job_parameters(
            job_template=job_template,
            job_parameter_values=job_parameter_values,
            job_template_dir=self.template_dir,
            current_working_dir=self.current_working_dir,
        )

        # THEN
        assert "Foo" in result
        assert result["Foo"] == ParameterValue(type=ParameterValueType.STRING, value="defaultValue")
        assert "Bar" in result
        assert result["Bar"] == ParameterValue(
            type=ParameterValueType.PATH, value=str(self.template_dir / "defaultPathValue")
        )

    def test_empty_path_parameter_passthrough(self) -> None:
        # Test that empty values for PATH parameter defaults or passed parameters are
        # passed through instead of being treated as the directory "."

        # GIVEN
        job_parameter_values: JobParameterInputValues = {"Bar": ""}
        job_template = JobTemplate_2023_09(
            specificationVersion="jobtemplate-2023-09",
            name="test",
            parameterDefinitions=[
                {"name": "Foo", "type": "PATH", "default": ""},
                {"name": "Bar", "type": "PATH", "default": "defaultPathValue"},
            ],
            steps=minimal_job_template_2023_09.steps,
        )

        # WHEN
        result = preprocess_job_parameters(
            job_template=job_template,
            job_parameter_values=job_parameter_values,
            job_template_dir=self.template_dir,
            current_working_dir=self.current_working_dir,
        )

        # THEN
        assert "Foo" in result
        assert result["Foo"] == ParameterValue(type=ParameterValueType.PATH, value="")
        assert "Bar" in result
        assert result["Bar"] == ParameterValue(type=ParameterValueType.PATH, value="")

    def test_collects_defaults_with_environments(self) -> None:
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
        env_template = EnvironmentTemplate_2023_09(
            specificationVersion="environment-2023-09",
            environment=minimal_environment_2023_09,
            parameterDefinitions=[{"name": "Bar", "type": "STRING", "default": "alsoDefaultValue"}],
        )

        # WHEN
        result = preprocess_job_parameters(
            job_template=job_template,
            job_parameter_values=job_parameter_values,
            job_template_dir=self.template_dir,
            current_working_dir=self.current_working_dir,
            environment_templates=[env_template],
        )

        # THEN
        assert "Foo" in result
        assert result["Foo"] == ParameterValue(type=ParameterValueType.STRING, value="defaultValue")
        assert "Bar" in result
        assert result["Bar"] == ParameterValue(
            type=ParameterValueType.STRING, value="alsoDefaultValue"
        )

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
            job_template=job_template,
            job_parameter_values=job_parameter_values,
            job_template_dir=self.template_dir,
            current_working_dir=self.current_working_dir,
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
                job_template=job_template,
                job_parameter_values=job_parameter_values,
                job_template_dir=self.template_dir,
                current_working_dir=self.current_working_dir,
            )

        # THEN
        assert "parameter Foo value must be at most 1 characters" in str(excinfo.value)
        assert len(str(excinfo.value).split("\n")) == 1

    def test_checks_contraints_with_environments(self) -> None:
        # Test that we see errors if a constraint is violated.

        # GIVEN
        job_parameter_values: JobParameterInputValues = {"Foo": "two", "Bar": "one"}
        job_template = JobTemplate_2023_09(
            specificationVersion="jobtemplate-2023-09",
            name="test",
            parameterDefinitions=[{"name": "Foo", "type": "STRING", "maxLength": 1}],
            steps=minimal_job_template_2023_09.steps,
        )
        env_template = EnvironmentTemplate_2023_09(
            specificationVersion="environment-2023-09",
            environment=minimal_environment_2023_09,
            parameterDefinitions=[{"name": "Bar", "type": "STRING", "minLength": 5}],
        )

        # WHEN
        with pytest.raises(ValueError) as excinfo:
            preprocess_job_parameters(
                job_template=job_template,
                job_parameter_values=job_parameter_values,
                job_template_dir=self.template_dir,
                current_working_dir=self.current_working_dir,
                environment_templates=[env_template],
            )

        # THEN
        assert "parameter Foo value must be at most 1 characters" in str(excinfo.value)
        assert "parameter Bar value must be at least 5 characters" in str(excinfo.value)
        assert len(str(excinfo.value).split("\n")) == 2

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
                job_template=job_template,
                job_parameter_values=job_parameter_values,
                job_template_dir=self.template_dir,
                current_working_dir=self.current_working_dir,
            )

        # THEN
        assert "parameter Foo value must be at most 1 characters" in str(excinfo.value)
        assert (
            "Job parameter values provided for parameters that are not defined in the template: Bar"
            in str(excinfo.value)
        )
        assert "Values missing for required job parameters: Buz" in str(excinfo.value)
        assert len(str(excinfo.value).split("\n")) == 3


class TestCreateJob_2023_09:
    def test_success(self) -> None:
        # GIVEN
        job_template = _parse_model(
            model=JobTemplate_2023_09,
            obj={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "Job",
                "parameterDefinitions": [{"name": "Foo", "type": "INT", "minValue": 10}],
                "steps": [
                    {"name": "Step", "script": {"actions": {"onRun": {"command": "do something"}}}}
                ],
            },
        )
        parameter_values = {"Foo": ParameterValue(type=ParameterValueType.INT, value="20")}
        expected = _parse_model(
            model=Job_2023_09,
            obj={
                "name": "Job",
                "parameters": {"Foo": {"type": "INT", "value": "20"}},
                "steps": [
                    {"name": "Step", "script": {"actions": {"onRun": {"command": "do something"}}}}
                ],
            },
        )

        # WHEN
        result = create_job(job_template=job_template, job_parameter_values=parameter_values)

        # THEN
        assert result == expected

    def test_with_preprocess_error_from_job_template(self) -> None:
        # GIVEN
        job_template = _parse_model(
            model=JobTemplate_2023_09,
            obj={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "Job",
                "parameterDefinitions": [{"name": "Foo", "type": "INT", "minValue": 10}],
                "steps": [
                    {"name": "Step", "script": {"actions": {"onRun": {"command": "do something"}}}}
                ],
            },
        )
        parameter_values = {"Foo": ParameterValue(type=ParameterValueType.INT, value="5")}

        # WHEN
        with pytest.raises(DecodeValidationError) as excinfo:
            create_job(job_template=job_template, job_parameter_values=parameter_values)

        # THEN
        assert "parameter Foo must be at least 10" in str(excinfo.value)

    def test_with_preprocess_error_from_environment_template(self) -> None:
        # GIVEN
        job_template = _parse_model(
            model=JobTemplate_2023_09,
            obj={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "Job",
                "parameterDefinitions": [{"name": "Foo", "type": "INT"}],
                "steps": [
                    {"name": "Step", "script": {"actions": {"onRun": {"command": "do something"}}}}
                ],
            },
        )
        env_template = _parse_model(
            model=EnvironmentTemplate_2023_09,
            obj={
                "specificationVersion": "environment-2023-09",
                "parameterDefinitions": [{"name": "Foo", "type": "INT", "minValue": 10}],
                "environment": {
                    "name": "Env",
                    "script": {"actions": {"onEnter": {"command": "do something"}}},
                },
            },
        )
        parameter_values = {"Foo": ParameterValue(type=ParameterValueType.INT, value="5")}

        # WHEN
        with pytest.raises(DecodeValidationError) as excinfo:
            create_job(
                job_template=job_template,
                job_parameter_values=parameter_values,
                environment_templates=[env_template],
            )

        # THEN
        assert "parameter Foo must be at least 10" in str(excinfo.value)

    def test_fails_to_instantiate(self) -> None:
        # GIVEN
        job_template = _parse_model(
            model=JobTemplate_2023_09,
            obj={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "{{Param.Foo}}",
                "parameterDefinitions": [{"name": "Foo", "type": "STRING"}],
                "steps": [
                    {"name": "Step", "script": {"actions": {"onRun": {"command": "do something"}}}}
                ],
            },
        )
        parameter_values = {"Foo": ParameterValue(type=ParameterValueType.STRING, value="a" * 256)}

        # WHEN
        with pytest.raises(DecodeValidationError) as excinfo:
            # This'll have an error when instantiating the Job due to the Job's name being too long.
            create_job(
                job_template=job_template,
                job_parameter_values=parameter_values,
            )

        # THEN
        assert (
            "1 validation errors for JobTemplate\nname:\n\tensure this value has at most 128 characters"
            in str(excinfo.value)
        )

    def test_uneven_parameter_space_association(self) -> None:
        # Test that when the arguments to an Association operator in a
        # parameter space combination expression have differing lengths then
        # we raise an appropriate exception.
        #
        # Note: This validation is run in the create job flow because we need
        # to have a fully instantiated the step parameter space's task parameter
        # definitions to know how large each parameter range is.

        # GIVEN
        job_template = _parse_model(
            model=JobTemplate_2023_09,
            obj={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "Job",
                "steps": [
                    {
                        "name": "Step",
                        "parameterSpace": {
                            "taskParameterDefinitions": [
                                {"name": "A", "type": "INT", "range": "1-10"},
                                {"name": "B", "type": "INT", "range": [1, 2]},
                            ],
                            "combination": "(A,B)",
                        },
                        "script": {"actions": {"onRun": {"command": "do something"}}},
                    }
                ],
            },
        )
        parameter_values = dict[str, Any]()

        # WHEN
        with pytest.raises(DecodeValidationError) as excinfo:
            # This'll have an error when instantiating the Job due to the Job's name being too long.
            create_job(
                job_template=job_template,
                job_parameter_values=parameter_values,
            )

        # THEN
        assert (
            "1 validation errors for JobTemplate\nsteps[0] -> steps[0] -> parameterSpace -> combination:\n\tAssociative expressions must have arguments with identical ranges. Expression (A, B) has argument lengths (10, 2)."
            in str(excinfo.value)
        )
