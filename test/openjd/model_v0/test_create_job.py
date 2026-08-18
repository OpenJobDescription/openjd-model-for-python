# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import json
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
    decode_job_template,
    decode_environment_template,
)
from openjd.model._parse import _parse_model
from openjd.model.v2023_09 import (
    Job as Job_2023_09,
    JobParameterType as JobParameterType_2023_09,
)

minimal_steps_v2023_09 = [
    {"name": "step", "script": {"actions": {"onRun": {"command": "do thing"}}}}
]
minimal_environment_2023_09 = {
    "name": "env",
    "script": {"actions": {"onEnter": {"command": "do a thing"}}},
}


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
            if param_type.value in ("STRING", "PATH", "INT", "FLOAT")
        ],
    )
    def test_preprocess_job_parameters_handles_parameter_type(self, param_type: str) -> None:
        # Test that we can process all known kinds of parameters

        # GIVEN
        job_parameter_values: JobParameterInputValues = {"Foo": "12"}
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                parameterDefinitions=[{"name": "Foo", "type": param_type}],
                steps=minimal_steps_v2023_09,
            )
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
            if param_type.value in ("STRING", "PATH", "INT", "FLOAT")
        ],
    )
    def test_handles_parameter_type_without_path_escape_validation(self, param_type: str) -> None:
        # Test that we can process all known kinds of parameters

        # GIVEN
        job_parameter_values: JobParameterInputValues = {"Foo": "12"}
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                parameterDefinitions=[{"name": "Foo", "type": param_type}],
                steps=minimal_steps_v2023_09,
            )
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
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                steps=minimal_steps_v2023_09,
                parameterDefinitions=[{"name": "Foo", "type": "PATH", "default": escaping_dir}],
            )
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
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                steps=minimal_steps_v2023_09,
                parameterDefinitions=[{"name": "Foo", "type": "PATH", "default": "defaultValue"}],
            )
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
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                steps=minimal_steps_v2023_09,
                parameterDefinitions=[{"name": "Foo", "type": "PATH", "default": escaping_dir}],
            )
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
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                steps=minimal_steps_v2023_09,
                parameterDefinitions=[{"name": "Foo", "type": "PATH", "default": escaping_dir}],
            )
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
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                steps=minimal_steps_v2023_09,
            )
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
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                steps=minimal_steps_v2023_09,
            )
        )
        env_template = decode_environment_template(
            template=dict(
                specificationVersion="environment-2023-09",
                environment=minimal_environment_2023_09,
                parameterDefinitions=[{"name": "ThisIsKnown", "type": "STRING"}],
            )
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
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                parameterDefinitions=[{"name": "ThisIsNotDefined", "type": "STRING"}],
                steps=minimal_steps_v2023_09,
            )
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
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                parameterDefinitions=[{"name": "ThisIsNotDefined", "type": "STRING"}],
                steps=minimal_steps_v2023_09,
            )
        )
        env_template = decode_environment_template(
            template=dict(
                specificationVersion="environment-2023-09",
                environment=minimal_environment_2023_09,
                parameterDefinitions=[{"name": "ThisIsAlsoMissing", "type": "STRING"}],
            )
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
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                parameterDefinitions=[
                    {"name": "Foo", "type": "STRING", "default": "defaultValue"},
                    {"name": "Bar", "type": "PATH", "default": "defaultPathValue"},
                ],
                steps=minimal_steps_v2023_09,
            )
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
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                parameterDefinitions=[
                    {"name": "Foo", "type": "PATH", "default": ""},
                    {"name": "Bar", "type": "PATH", "default": "defaultPathValue"},
                ],
                steps=minimal_steps_v2023_09,
            )
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
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                parameterDefinitions=[{"name": "Foo", "type": "STRING", "default": "defaultValue"}],
                steps=minimal_steps_v2023_09,
            )
        )
        env_template = decode_environment_template(
            template=dict(
                specificationVersion="environment-2023-09",
                environment=minimal_environment_2023_09,
                parameterDefinitions=[
                    {"name": "Bar", "type": "STRING", "default": "alsoDefaultValue"}
                ],
            )
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
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                parameterDefinitions=[{"name": "Foo", "type": "STRING", "default": "defaultValue"}],
                steps=minimal_steps_v2023_09,
            )
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
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                parameterDefinitions=[{"name": "Foo", "type": "STRING", "maxLength": 1}],
                steps=minimal_steps_v2023_09,
            )
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
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                parameterDefinitions=[{"name": "Foo", "type": "STRING", "maxLength": 1}],
                steps=minimal_steps_v2023_09,
            )
        )
        env_template = decode_environment_template(
            template=dict(
                specificationVersion="environment-2023-09",
                environment=minimal_environment_2023_09,
                parameterDefinitions=[{"name": "Bar", "type": "STRING", "minLength": 5}],
            )
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
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                parameterDefinitions=[
                    {"name": "Foo", "type": "STRING", "maxLength": 1},
                    {"name": "Buz", "type": "STRING"},
                ],
                steps=minimal_steps_v2023_09,
            )
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
        job_template = decode_job_template(
            template={
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
        job_template = decode_job_template(
            template={
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
        job_template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "Job",
                "parameterDefinitions": [{"name": "Foo", "type": "INT"}],
                "steps": [
                    {"name": "Step", "script": {"actions": {"onRun": {"command": "do something"}}}}
                ],
            },
        )
        env_template = decode_environment_template(
            template={
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
        job_template = decode_job_template(
            template={
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
            "1 validation errors for JobTemplate\nname:\n\tString should have at most 128 characters"
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
        job_template = decode_job_template(
            template={
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
            "1 validation errors for JobTemplate\nsteps[0] -> parameterSpace -> combination:\n\tAssociative expressions must have arguments with identical ranges. Expression (A, B) has argument lengths (10, 2)."
            in str(excinfo.value)
        )


class TestCreateJobWithSymbolTables:
    """``create_job_with_symbol_tables`` returns the tables that ``create_job``
    discards, in the transport form openjd-rs uses."""

    EXPR_TEMPLATE: dict[str, Any] = {
        "specificationVersion": "jobtemplate-2023-09",
        "extensions": ["EXPR"],
        "name": "my-job",
        "parameterDefinitions": [
            {"name": "Count", "type": "INT", "default": 21},
            {"name": "Tag", "type": "STRING", "default": "abc"},
            {"name": "Scene", "type": "PATH", "default": "scene.blend"},
        ],
        "steps": [
            {
                "name": "render",
                "let": ["twice = Param.Count * 2", "tag = Job.Name + '-' + Step.Name"],
                "script": {
                    "let": ["sess = Job.Name + '!'"],
                    "actions": {
                        "onRun": {
                            "command": "echo",
                            "args": ["{{ twice }}", "{{ tag }}", "{{ sess }}"],
                        }
                    },
                },
            },
            {
                "name": "publish",
                "script": {"actions": {"onRun": {"command": "echo", "args": ["{{ Param.Tag }}"]}}},
            },
        ],
    }

    @staticmethod
    def _entries(serialized: Any) -> dict[str, tuple[str, Any]]:
        """Decode the transport form into {name: (type, value)}."""
        _helper, (text,) = serialized.__reduce__()
        return {e["name"]: (e["type"], e["value"]) for e in json.loads(text)}

    def _create(self) -> Any:
        from openjd.model import create_job_with_symbol_tables

        job_template = decode_job_template(
            template=self.EXPR_TEMPLATE, supported_extensions=["EXPR"]
        )
        parameter_values = preprocess_job_parameters(
            job_template=job_template,
            job_parameter_values={},
            job_template_dir=Path(),
            current_working_dir=Path(),
            allow_job_template_dir_walk_up=True,
        )
        return create_job_with_symbol_tables(
            job_template=job_template, job_parameter_values=parameter_values
        )

    def test_returns_the_same_job_as_create_job(self) -> None:
        # GIVEN
        job_template = decode_job_template(
            template=self.EXPR_TEMPLATE, supported_extensions=["EXPR"]
        )
        parameter_values = preprocess_job_parameters(
            job_template=job_template,
            job_parameter_values={},
            job_template_dir=Path(),
            current_working_dir=Path(),
            allow_job_template_dir_walk_up=True,
        )

        # WHEN
        plain = create_job(job_template=job_template, job_parameter_values=parameter_values)
        result = self._create()

        # THEN
        assert result.job == plain

    def test_job_scope_table(self) -> None:
        # WHEN
        entries = self._entries(self._create().job_symbol_table)

        # THEN
        assert entries["Job.Name"] == ("string", "my-job")
        assert entries["Param.Count"] == ("int", "21")
        assert entries["Param.Tag"] == ("string", "abc")
        # PATH parameters carry RawParam only at template scope: the mapped
        # Param.* value only exists at session scope.
        assert entries["RawParam.Scene"] == ("string", "scene.blend")
        assert "Param.Scene" not in entries
        # Job scope has no step in it
        assert "Step.Name" not in entries

    def test_step_scope_tables_are_keyed_by_step_name(self) -> None:
        # WHEN
        tables = self._create().step_symbol_tables

        # THEN
        assert set(tables) == {"render", "publish"}

    def test_step_scope_adds_step_name_and_template_let_results(self) -> None:
        # WHEN
        entries = self._entries(self._create().step_symbol_tables["render"])

        # THEN
        assert entries["Step.Name"] == ("string", "render")
        # Template-scope `let` results are resolved and frozen into the table
        assert entries["twice"] == ("int", "42")
        assert entries["tag"] == ("string", "my-job-render")

    def test_script_scope_let_is_not_in_the_table(self) -> None:
        """Script-scope `let` resolves at session time, so only the symbols it
        references travel — not its results."""
        # WHEN
        entries = self._entries(self._create().step_symbol_tables["render"])

        # THEN
        assert "sess" not in entries
        assert "Job.Name" in entries

    def test_each_step_gets_its_own_scope(self) -> None:
        # WHEN
        tables = self._create().step_symbol_tables

        # THEN
        assert self._entries(tables["publish"])["Step.Name"] == ("string", "publish")
        # `render`'s let bindings do not leak into `publish`
        assert "twice" not in self._entries(tables["publish"])

    def test_non_expr_template_has_no_job_name(self) -> None:
        from openjd.model import create_job_with_symbol_tables

        # GIVEN
        template = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "plain",
            "parameterDefinitions": [{"name": "Tag", "type": "STRING", "default": "x"}],
            "steps": [{"name": "s", "script": {"actions": {"onRun": {"command": "echo"}}}}],
        }
        job_template = decode_job_template(template=template)
        parameter_values = preprocess_job_parameters(
            job_template=job_template,
            job_parameter_values={},
            job_template_dir=Path(),
            current_working_dir=Path(),
            allow_job_template_dir_walk_up=True,
        )

        # WHEN
        result = create_job_with_symbol_tables(
            job_template=job_template, job_parameter_values=parameter_values
        )

        # THEN — Job.Name is EXPR-gated
        assert "Job.Name" not in self._entries(result.job_symbol_table)
        assert self._entries(result.job_symbol_table)["Param.Tag"] == ("string", "x")

    def test_matches_the_rust_implementation(self) -> None:
        """Every symbol openjd-rs' create_job puts in Step.resolved_symtab appears
        here with an identical type and value.

        This is the property that lets a v0 producer and a Rust consumer share the
        channel. The table here is a superset: openjd-rs filters its table down to
        the symbols the step references, which is a payload optimization rather
        than a semantic difference.
        """
        from openjd._openjd_rs import create_job as rs_create_job
        from openjd._openjd_rs import decode_job_template as rs_decode

        # GIVEN
        rs_job = rs_create_job(
            job_template=rs_decode(self.EXPR_TEMPLATE, supported_extensions=["EXPR"]),
            job_parameter_values={},
        )
        v0_tables = self._create().step_symbol_tables

        # WHEN / THEN
        compared = 0
        for rs_step in rs_job.steps:
            if rs_step.resolved_symtab is None:
                continue
            rust_entries = self._entries(rs_step.resolved_symtab)
            v0_entries = self._entries(v0_tables[str(rs_step.name)])
            for name, rust_value in rust_entries.items():
                assert (
                    name in v0_entries
                ), f"{name} missing from the v0 table for step {rs_step.name}"
                assert v0_entries[name] == rust_value, f"{name} differs for step {rs_step.name}"
                compared += 1
        # Guard against the assertions above passing vacuously
        assert compared > 0
