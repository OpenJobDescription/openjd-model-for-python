# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import json
import os
import sys
import tempfile
import pytest
from pathlib import Path
from typing import Any, Optional

from openjd.expr import ExpressionError
from openjd.model._v1 import (
    CallerLimits,
    ModelProfile,
    create_job,
    decode_environment_template,
    decode_job_template,
    merge_job_parameter_definitions,
    preprocess_job_parameters,
)
from openjd.model._v1.types import (
    JobParameterType,
    JobParameterValue,
    ModelExtension,
    ValidationContext,
)
from openjd.model._v1.errors import (
    DecodeValidationError,
    ModelValidationError,
)


class _JobParamTypeCompat:
    """Wrapper to give Rust enum members a .value attribute like Python's enum.Enum."""

    def __init__(self, member):
        self._member = member
        self.value = member.as_str()

    def __repr__(self):
        return repr(self._member)


# The 2023-09 schema supported these four job parameter types.
JobParameterType_2023_09 = [
    _JobParamTypeCompat(JobParameterType.STRING),
    _JobParamTypeCompat(JobParameterType.INT),
    _JobParamTypeCompat(JobParameterType.FLOAT),
    _JobParamTypeCompat(JobParameterType.PATH),
]


def _parameter_value_type_from_str(s: str) -> JobParameterType:
    """Look up a JobParameterType member by its string name."""
    return getattr(JobParameterType, s)


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
        ],
    )
    def test_preprocess_job_parameters_handles_parameter_type(self, param_type: str) -> None:
        # Test that we can process all known kinds of parameters

        # GIVEN
        job_parameter_values: dict[str, str] = {"Foo": "12"}
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
        assert result["Foo"].type == _parameter_value_type_from_str(param_type)

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
        job_parameter_values: dict[str, str] = {"Foo": "12"}
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
        assert result["Foo"].type == _parameter_value_type_from_str(param_type)

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
        job_parameter_values: dict[str, str] = {}
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
        job_parameter_values: dict[str, str] = {}
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                steps=minimal_steps_v2023_09,
                parameterDefinitions=[{"name": "Foo", "type": "PATH", "default": "defaultValue"}],
            )
        )

        # WHEN
        tdir = Path("relative/path")
        with pytest.raises(ValueError) as excinfo:
            preprocess_job_parameters(
                job_template=job_template,
                job_parameter_values=job_parameter_values,
                job_template_dir=tdir,
                current_working_dir=self.current_working_dir,
            )

        # THEN
        assert "the job template dir" in str(excinfo.value)
        assert "is not an absolute path. It must be absolute to enforce that" in str(excinfo.value)
        # Regression for report rec #17: the user-supplied relative
        # path must appear verbatim in the diagnostic. Earlier
        # versions stripped it (the message read "..., , is not an
        # absolute path." with an empty placeholder).
        #
        # The path round-trips through ``os.fspath`` at the binding
        # boundary, so on Windows ``Path("relative/path")`` becomes
        # ``"relative\\path"``. Assert against ``str(tdir)`` so this
        # works on both POSIX and Windows hosts.
        assert str(tdir) in str(excinfo.value)

    @pytest.mark.parametrize(
        "tdir,expected_in_message",
        [
            pytest.param(Path("."), ".", id="dot-path"),
            pytest.param(Path(""), ".", id="empty-path"),  # PathBuf normalises "" -> "."
            pytest.param(Path("rel/dir"), None, id="relative-multi-segment"),
            pytest.param(Path("relative"), "relative", id="relative-single-segment"),
        ],
    )
    def test_preprocess_relative_path_error_includes_path(
        self, tdir: Path, expected_in_message: "str | None"
    ) -> None:
        """``preprocess_job_parameters`` rejects relative or sentinel
        ``job_template_dir`` values when ``allow_job_template_dir_walk_up``
        is False, and the diagnostic must name the user-supplied
        path so the caller can identify which value was wrong.
        Regression for report rec #17 — earlier versions emitted
        ``"the job template dir, ,"`` with an empty placeholder for
        ``Path(".")`` and ``Path("")`` because the binding rewrote
        them to ``""`` before validation.

        The path round-trips through ``os.fspath`` at the binding
        boundary, so a multi-segment path like ``Path("rel/dir")``
        appears in the diagnostic with the host's separator —
        ``rel/dir`` on POSIX, ``rel\\dir`` on Windows.
        Single-segment paths and the ``"."`` / ``""`` sentinels are
        separator-free and thus host-invariant. Cases where
        ``expected_in_message`` is ``None`` substitute ``str(tdir)``
        so the assertion holds on both POSIX and Windows hosts.
        """
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                steps=minimal_steps_v2023_09,
                parameterDefinitions=[{"name": "Foo", "type": "PATH", "default": "defaultValue"}],
            )
        )
        with pytest.raises(ValueError) as excinfo:
            preprocess_job_parameters(
                job_template=job_template,
                job_parameter_values={},
                job_template_dir=tdir,
                current_working_dir=self.current_working_dir,
            )
        msg = str(excinfo.value)
        # The path appears verbatim in the diagnostic — using
        # ``str(tdir)`` (i.e., the host-OS form) for the
        # ``relative-multi-segment`` case so the assertion is
        # portable across POSIX and Windows.
        needle = expected_in_message if expected_in_message is not None else str(tdir)
        assert f"the job template dir, {needle}," in msg, f"Expected path {needle!r} in {msg!r}"

    def test_preprocess_walk_up_true_accepts_dot_path(self) -> None:
        """With ``allow_job_template_dir_walk_up=True``, the
        ``"."`` / ``""`` sentinel paths are accepted (used by
        ``create_job`` itself when the caller hasn't supplied a
        real template directory). This is the inverse of
        ``test_preprocess_relative_path_error_includes_path``: the
        same path that's rejected with walk-up disabled is
        accepted with walk-up enabled."""
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                steps=minimal_steps_v2023_09,
                parameterDefinitions=[{"name": "Foo", "type": "STRING", "default": "x"}],
            )
        )
        # No exception.
        result = preprocess_job_parameters(
            job_template=job_template,
            job_parameter_values={},
            job_template_dir=Path("."),
            current_working_dir=Path("."),
            allow_job_template_dir_walk_up=True,
        )
        assert "Foo" in result

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
        job_parameter_values: dict[str, str] = {}
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
        assert result["Foo"] == JobParameterValue(
            type=JobParameterType.PATH, value=os.path.normpath(self.template_dir / escaping_dir)
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
        job_parameter_values: dict[str, str] = {}
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
        assert result["Foo"] == JobParameterValue(type=JobParameterType.PATH, value=escaping_dir)

    def test_reports_extra(self) -> None:
        # Test that we get errors if we have extra job parameters defined.

        # GIVEN
        job_parameter_values: dict[str, str] = {"ThisIsUnknown": "value"}
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
        job_parameter_values: dict[str, str] = {
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
        job_parameter_values: dict[str, str] = dict()
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
        job_parameter_values: dict[str, str] = dict()
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
        job_parameter_values: dict[str, str] = {}
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
        assert result["Foo"] == JobParameterValue(
            type=JobParameterType.STRING, value="defaultValue"
        )
        assert "Bar" in result
        assert result["Bar"] == JobParameterValue(
            type=JobParameterType.PATH, value=str(self.template_dir / "defaultPathValue")
        )

    def test_empty_path_parameter_passthrough(self) -> None:
        # Test that empty values for PATH parameter defaults or passed parameters are
        # passed through instead of being treated as the directory "."

        # GIVEN
        job_parameter_values: dict[str, str] = {"Bar": ""}
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
        assert result["Foo"] == JobParameterValue(type=JobParameterType.PATH, value="")
        assert "Bar" in result
        assert result["Bar"] == JobParameterValue(type=JobParameterType.PATH, value="")

    def test_collects_defaults_with_environments(self) -> None:
        # Test that we add values for missing job parameters that have
        # defaults defined.

        # GIVEN
        job_parameter_values: dict[str, str] = {}
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
        assert result["Foo"] == JobParameterValue(
            type=JobParameterType.STRING, value="defaultValue"
        )
        assert "Bar" in result
        assert result["Bar"] == JobParameterValue(
            type=JobParameterType.STRING, value="alsoDefaultValue"
        )

    def test_ignores_defaults(self) -> None:
        # Test that we do not add values for job parameters that have
        # defaults defined, but that we've already defined.

        # GIVEN
        job_parameter_values: dict[str, str] = {"Foo": "FooValue"}
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
        assert result["Foo"] == JobParameterValue(type=JobParameterType.STRING, value="FooValue")

    def test_checks_contraints(self) -> None:
        # Test that we see errors if a constraint is violated.

        # GIVEN
        job_parameter_values: dict[str, str] = {"Foo": "two"}
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
        assert str(excinfo.value) == "Parameter 'Foo': value length 3 exceeds maximum 1"

    def test_checks_contraints_with_environments(self) -> None:
        # Test that we see errors if a constraint is violated.

        # GIVEN
        job_parameter_values: dict[str, str] = {"Foo": "two", "Bar": "one"}
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

        # THEN — all errors collected (env template params processed first)
        assert str(excinfo.value) == "\n".join(
            [
                "Parameter 'Bar': value length 3 is less than minimum 5",
                "Parameter 'Foo': value length 3 exceeds maximum 1",
            ]
        )

    def test_collects_multiple_errors(self) -> None:
        # Test that see all errors if we have multiple in the same run.

        # GIVEN
        job_parameter_values: dict[str, str] = {
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

        # THEN — all errors collected
        assert str(excinfo.value) == "\n".join(
            [
                "Parameter 'Foo': value length 3 exceeds maximum 1",
                "Job parameter values provided for parameters that are not defined in the template: Bar",
                "Values missing for required job parameters: Buz",
            ]
        )


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
        parameter_values = {"Foo": JobParameterValue(type=JobParameterType.INT, value="20")}

        # WHEN
        result = create_job(job_template=job_template, job_parameter_values=parameter_values)

        # THEN
        assert result.name == "Job"
        assert len(result.steps) == 1
        assert result.steps[0].name == "Step"
        assert "Foo" in result.parameters
        assert result.parameters["Foo"].value.item() == 20

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
        parameter_values = {"Foo": JobParameterValue(type=JobParameterType.INT, value="5")}

        # WHEN
        with pytest.raises(DecodeValidationError) as excinfo:
            create_job(job_template=job_template, job_parameter_values=parameter_values)

        # THEN
        assert str(excinfo.value) == "Parameter 'Foo': value 5 is less than minimum 10"

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
        parameter_values = {"Foo": JobParameterValue(type=JobParameterType.INT, value="5")}

        # WHEN
        with pytest.raises(DecodeValidationError) as excinfo:
            create_job(
                job_template=job_template,
                job_parameter_values=parameter_values,
                environment_templates=[env_template],
            )

        # THEN
        assert str(excinfo.value) == "Parameter 'Foo': value 5 is less than minimum 10"

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
        parameter_values = {"Foo": JobParameterValue(type=JobParameterType.STRING, value="a" * 256)}

        # WHEN
        with pytest.raises(DecodeValidationError) as excinfo:
            # This'll have an error when instantiating the Job due to the Job's name being too long.
            create_job(
                job_template=job_template,
                job_parameter_values=parameter_values,
            )

        # THEN
        assert str(excinfo.value) == "Job name exceeds maximum length of 128 characters (got 256)"

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
            str(excinfo.value)
            == "Associative combination: all members must have the same number of values, got 10 and 2"
        )


class TestParametersDict:
    """``Job.parameters`` is the resolved parameter set: every parameter
    defined in the template (defaults plus explicit values) keyed by
    name, with each ``JobParameter.value`` resolved to the chosen
    ``ExprValue``. This matches the v0 reference's behaviour and is
    relied on by every downstream consumer that walks the resolved set
    (sessions, the worker agent, deadline-cli)."""

    @staticmethod
    def _two_param_template() -> dict[str, Any]:
        return {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "T",
            "parameterDefinitions": [
                {"name": "Frame", "type": "INT", "default": 5},
                {"name": "Name", "type": "STRING", "default": "render"},
            ],
            "steps": [
                {
                    "name": "S",
                    "script": {
                        "actions": {
                            "onRun": {
                                "command": "echo",
                                "args": [
                                    "{{Param.Name}}",
                                    "{{Param.Frame}}",
                                ],
                            }
                        }
                    },
                }
            ],
        }

    def test_defaults_only_populated(self) -> None:
        """No values supplied — all defaults appear in
        ``Job.parameters``."""
        t = decode_job_template(template=self._two_param_template())
        j = create_job(job_template=t, job_parameter_values={})
        assert set(j.parameters.keys()) == {"Frame", "Name"}
        assert j.parameters["Frame"].type is JobParameterType.INT
        assert j.parameters["Frame"].value.item() == 5
        assert j.parameters["Name"].type is JobParameterType.STRING
        assert j.parameters["Name"].value.item() == "render"

    def test_explicit_values_override_defaults(self) -> None:
        """Explicit values override defaults; un-supplied parameters
        still show up via their defaults."""
        t = decode_job_template(template=self._two_param_template())
        j = create_job(
            job_template=t,
            job_parameter_values={"Frame": JobParameterValue(type=JobParameterType.INT, value="7")},
        )
        assert set(j.parameters.keys()) == {"Frame", "Name"}
        assert j.parameters["Frame"].value.item() == 7
        assert j.parameters["Name"].value.item() == "render"

    def test_bare_scalar_input(self) -> None:
        """Bare-scalar input (``{"Frame": 7}``) is accepted and the
        un-supplied parameter falls back to its default."""
        t = decode_job_template(template=self._two_param_template())
        j = create_job(
            job_template=t,
            job_parameter_values={"Frame": 7},
        )
        assert j.parameters["Frame"].value.item() == 7
        assert j.parameters["Name"].value.item() == "render"

    def test_dict_shaped_input(self) -> None:
        """Dict-shaped input (``{"type": ..., "value": ...}``) is
        accepted; defaults still fill in the missing names."""
        t = decode_job_template(template=self._two_param_template())
        j = create_job(
            job_template=t,
            job_parameter_values={"Name": {"type": "STRING", "value": "foo"}},
        )
        assert j.parameters["Name"].value.item() == "foo"
        assert j.parameters["Frame"].value.item() == 5

    def test_all_explicit_no_defaults_used(self) -> None:
        """When every parameter is supplied explicitly, no default is
        consulted; ``Job.parameters`` reflects the supplied values."""
        t = decode_job_template(template=self._two_param_template())
        j = create_job(
            job_template=t,
            job_parameter_values={
                "Frame": JobParameterValue(type=JobParameterType.INT, value="42"),
                "Name": JobParameterValue(type=JobParameterType.STRING, value="bar"),
            },
        )
        assert j.parameters["Frame"].value.item() == 42
        assert j.parameters["Name"].value.item() == "bar"

    def test_required_param_no_default_no_value_raises(self) -> None:
        """A parameter with no default and no supplied value triggers
        the standard 'Values missing for required job parameters' error
        (this lives in ``preprocess_job_parameters``, which
        ``create_job`` now routes through internally)."""
        template = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "T",
            "parameterDefinitions": [
                {"name": "Required", "type": "INT"},  # no default
            ],
            "steps": [
                {
                    "name": "S",
                    "script": {
                        "actions": {
                            "onRun": {
                                "command": "echo",
                                "args": ["{{Param.Required}}"],
                            }
                        }
                    },
                }
            ],
        }
        t = decode_job_template(template=template)
        with pytest.raises(DecodeValidationError, match="missing"):
            create_job(job_template=t, job_parameter_values={})

    def test_constraint_check_runs_via_create_job(self) -> None:
        """Constraint checks (e.g. ``minValue``) run during
        ``create_job`` itself — callers don't need to call
        ``preprocess_job_parameters`` first."""
        template = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "T",
            "parameterDefinitions": [
                {"name": "Frame", "type": "INT", "default": 5, "minValue": 1},
            ],
            "steps": [
                {
                    "name": "S",
                    "script": {
                        "actions": {
                            "onRun": {
                                "command": "echo",
                                "args": ["{{Param.Frame}}"],
                            }
                        }
                    },
                }
            ],
        }
        t = decode_job_template(template=template)
        # Below-min value rejected.
        with pytest.raises(DecodeValidationError):
            create_job(
                job_template=t,
                job_parameter_values={
                    "Frame": JobParameterValue(type=JobParameterType.INT, value="0")
                },
            )
        # Default (5) passes constraints — Job.parameters gets the
        # default.
        j = create_job(job_template=t, job_parameter_values={})
        assert j.parameters["Frame"].value.item() == 5


class TestJobTimeFieldExposure:
    """Job-time pyclass field-coverage tests covering the P1 recommendations
    in ``reports/model-bindings-quality-evaluation-report.md``: the
    ``JobParameter.type`` alias, ``Step.host_requirements`` /
    ``hostRequirements``, and ``EmbeddedFile.runnable`` /
    ``end_of_line`` / ``endOfLine`` getters.

    These cover the v0-parity contract: every field that the v0 reference
    materialised onto its job-time pydantic models must have an equivalent
    accessor on the v1 Rust-backed pyclasses.
    """

    def test_job_parameter_type_returns_enum(self) -> None:
        """``JobParameter.type`` returns a :class:`JobParameterType`
        enum, mirroring the v0 reference's ``JobParameter.type``
        field type and the underlying Rust
        ``job::JobParameter.param_type`` field. The previous
        string-returning ``param_type`` getter is gone — there is
        exactly one accessor for the parameter's type."""
        t = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "T",
                "parameterDefinitions": [{"name": "Count", "type": "INT", "default": 5}],
                "steps": [
                    {
                        "name": "S",
                        "script": {"actions": {"onRun": {"command": "echo"}}},
                    }
                ],
            }
        )
        j = create_job(job_template=t, job_parameter_values={})
        param = j.parameters["Count"]

        assert isinstance(param.type, JobParameterType)
        assert param.type is JobParameterType.INT

        # ``str(param.type)`` returns the spec-form string for callers
        # that need it; ``.as_str()`` is the explicit method.
        assert str(param.type) == "INT"
        assert param.type.as_str() == "INT"

        # The previous string-returning getter is gone — there is one
        # canonical accessor.
        assert not hasattr(param, "param_type")

    def test_step_exposes_host_requirements(self) -> None:
        """``Step.host_requirements`` (and the camelCase alias
        ``hostRequirements``) returns a job-time
        :class:`HostRequirements` from ``openjd.model._v1.job`` —
        distinct from the template-time ``TemplateHostRequirements``."""
        from openjd.model._v1.job import (
            AmountRequirement as JobAmountRequirement,
            AttributeRequirement as JobAttributeRequirement,
            HostRequirements as JobHostRequirements,
        )

        t = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "T",
                "steps": [
                    {
                        "name": "S",
                        "hostRequirements": {
                            "amounts": [{"name": "amount.worker.vcpu", "min": 4, "max": 8}],
                            "attributes": [
                                {
                                    "name": "attr.worker.os.family",
                                    "anyOf": ["linux"],
                                }
                            ],
                        },
                        "script": {"actions": {"onRun": {"command": "echo"}}},
                    }
                ],
            }
        )
        j = create_job(job_template=t, job_parameter_values={})
        step = j.steps[0]

        hr = step.host_requirements
        assert hr is not None
        assert isinstance(hr, JobHostRequirements)

        # camelCase alias resolves to the same shape.
        hr_camel = step.hostRequirements
        assert hr_camel is not None
        assert isinstance(hr_camel, JobHostRequirements)

        # Amounts: resolved to concrete f64.
        assert hr.amounts is not None
        assert len(hr.amounts) == 1
        amount = hr.amounts[0]
        assert isinstance(amount, JobAmountRequirement)
        assert amount.name == "amount.worker.vcpu"
        assert amount.min == 4.0
        assert amount.max == 8.0

        # Attributes: resolved to concrete strings, with both snake_case and
        # camelCase aliases on the ``any_of`` / ``all_of`` getters.
        assert hr.attributes is not None
        assert len(hr.attributes) == 1
        attr = hr.attributes[0]
        assert isinstance(attr, JobAttributeRequirement)
        assert attr.name == "attr.worker.os.family"
        assert attr.any_of == ["linux"]
        assert attr.anyOf == ["linux"]
        assert attr.all_of is None
        assert attr.allOf is None

    def test_step_host_requirements_none_when_omitted(self) -> None:
        """A step with no ``hostRequirements`` reports ``None``."""
        t = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "T",
                "steps": [
                    {
                        "name": "S",
                        "script": {"actions": {"onRun": {"command": "echo"}}},
                    }
                ],
            }
        )
        j = create_job(job_template=t, job_parameter_values={})
        step = j.steps[0]
        assert step.host_requirements is None
        assert step.hostRequirements is None

    def test_step_host_requirements_distinct_from_template_class(self) -> None:
        """Job-time and template-time ``HostRequirements`` are distinct
        pyclass types — the job-time pyclass exposes resolved ``f64`` /
        ``str`` fields, the template-time pyclass exposes raw
        ``FormatString`` fields. Pinning the class identity here so a
        future refactor doesn't accidentally collapse them into one."""
        from openjd.model._v1.job import (
            HostRequirements as JobHostRequirements,
        )
        from openjd.model._v1.template import (
            HostRequirements as TemplateHR_alias,
            TemplateHostRequirements,
        )

        # Template-side aliases collapse onto the same class object.
        assert TemplateHR_alias is TemplateHostRequirements

        # Job-time and template-time are distinct.
        assert JobHostRequirements is not TemplateHostRequirements
        assert JobHostRequirements.__module__ == "openjd.model._v1.job"
        assert TemplateHostRequirements.__module__ == "openjd.model._v1.template"

    def test_embedded_file_exposes_runnable(self) -> None:
        """``EmbeddedFile.runnable`` is exposed on the job-time pyclass
        (and matches the template-time pyclass's existing field). The
        sessions runtime reads this to set the executable bit when
        materialising the file."""
        t = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "T",
                "steps": [
                    {
                        "name": "S",
                        "script": {
                            "actions": {"onRun": {"command": "./run.sh"}},
                            "embeddedFiles": [
                                {
                                    "name": "RunScript",
                                    "type": "TEXT",
                                    "filename": "run.sh",
                                    "data": "#!/bin/sh\necho hi",
                                    "runnable": True,
                                }
                            ],
                        },
                    }
                ],
            }
        )
        j = create_job(job_template=t, job_parameter_values={})
        embedded = j.steps[0].script.embeddedFiles
        assert embedded is not None
        ef = embedded[0]
        assert ef.runnable is True

    def test_embedded_file_runnable_none_when_omitted(self) -> None:
        """Omitted ``runnable`` reports ``None`` — distinct from
        ``False``, since the template did not state a preference."""
        t = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "T",
                "steps": [
                    {
                        "name": "S",
                        "script": {
                            "actions": {"onRun": {"command": "echo"}},
                            "embeddedFiles": [
                                {
                                    "name": "Note",
                                    "type": "TEXT",
                                    "data": "hello",
                                }
                            ],
                        },
                    }
                ],
            }
        )
        j = create_job(job_template=t, job_parameter_values={})
        embedded = j.steps[0].script.embeddedFiles
        assert embedded is not None
        ef = embedded[0]
        assert ef.runnable is None

    @pytest.mark.parametrize(
        ("eol_input", "expected"),
        [
            ("LF", "LF"),
            ("CRLF", "CRLF"),
        ],
    )
    def test_embedded_file_exposes_end_of_line(self, eol_input: str, expected: str) -> None:
        """``EmbeddedFile.end_of_line`` (and camelCase alias
        ``endOfLine``) returns the spec-form string. Sessions need
        this to convert line endings before writing the file."""
        t = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "T",
                "extensions": ["FEATURE_BUNDLE_1"],
                "steps": [
                    {
                        "name": "S",
                        "script": {
                            "actions": {"onRun": {"command": "echo"}},
                            "embeddedFiles": [
                                {
                                    "name": "Note",
                                    "type": "TEXT",
                                    "data": "hello",
                                    "endOfLine": eol_input,
                                }
                            ],
                        },
                    }
                ],
            },
            supported_extensions=["FEATURE_BUNDLE_1"],
        )
        j = create_job(job_template=t, job_parameter_values={})
        embedded = j.steps[0].script.embeddedFiles
        assert embedded is not None
        ef = embedded[0]
        assert ef.end_of_line == expected
        assert ef.endOfLine == expected

    def test_embedded_file_end_of_line_none_when_omitted(self) -> None:
        """Omitted ``endOfLine`` reports ``None``."""
        t = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "T",
                "steps": [
                    {
                        "name": "S",
                        "script": {
                            "actions": {"onRun": {"command": "echo"}},
                            "embeddedFiles": [
                                {
                                    "name": "Note",
                                    "type": "TEXT",
                                    "data": "hello",
                                }
                            ],
                        },
                    }
                ],
            }
        )
        j = create_job(job_template=t, job_parameter_values={})
        embedded = j.steps[0].script.embeddedFiles
        assert embedded is not None
        ef = embedded[0]
        assert ef.end_of_line is None
        assert ef.endOfLine is None


class TestStepParameterSpaceIteratorValidateContainment:
    """``validate_containment`` mirrors the v0 reference: returns ``None``
    on success, raises ``ValueError`` with a detailed diagnostic on
    failure. Wraps the underlying Rust crate's
    ``StepParameterSpaceIterator::validate_containment``."""

    def _build_iter(self):
        from openjd.model._v1.job import StepParameterSpaceIterator

        t = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "T",
                "steps": [
                    {
                        "name": "S",
                        "parameterSpace": {
                            "taskParameterDefinitions": [
                                {"name": "Frame", "type": "INT", "range": [1, 2, 3]},
                            ],
                        },
                        "script": {"actions": {"onRun": {"command": "echo"}}},
                    }
                ],
            }
        )
        j = create_job(job_template=t, job_parameter_values={})
        return StepParameterSpaceIterator(space=j.steps[0].parameterSpace)

    def _v(self, value: str):
        """Build a TaskParameterValue with type INT (matching the
        space's `Frame` parameter)."""
        from openjd.model._v1.types import (
            TaskParameterType,
            TaskParameterValue,
        )

        return TaskParameterValue(type=TaskParameterType.INT, value=value)

    def test_method_is_exposed(self) -> None:
        it = self._build_iter()
        assert hasattr(it, "validate_containment")
        assert callable(it.validate_containment)

    def test_returns_none_on_contained_value(self) -> None:
        """A parameter set inside the space returns ``None``
        (matching the v0 reference's implicit-``None`` shape)."""
        it = self._build_iter()
        result = it.validate_containment({"Frame": self._v("1")})
        assert result is None

    def test_raises_value_error_on_missing_name(self) -> None:
        """A parameter set missing a name from the space raises
        ``ValueError`` with a diagnostic message that names both the
        observed and expected parameter sets."""
        it = self._build_iter()
        with pytest.raises(ValueError) as excinfo:
            it.validate_containment({})
        msg = str(excinfo.value)
        # Pin substantive substrings rather than the whole message —
        # the precise wording is set by the Rust crate.
        assert "do not match" in msg
        assert "Frame" in msg

    def test_raises_value_error_on_extra_name(self) -> None:
        """Extra parameter names raise ``ValueError`` for the same
        reason — the names must match the space's names exactly."""
        it = self._build_iter()
        with pytest.raises(ValueError) as excinfo:
            it.validate_containment({"Frame": self._v("1"), "Extra": self._v("0")})
        msg = str(excinfo.value)
        assert "do not match" in msg
        assert "Extra" in msg

    def test_raises_value_error_on_out_of_range_value(self) -> None:
        """A parameter value outside the declared range raises
        ``ValueError`` with a message naming the offending parameter."""
        it = self._build_iter()
        with pytest.raises(ValueError) as excinfo:
            it.validate_containment({"Frame": self._v("999")})
        msg = str(excinfo.value)
        # The Rust crate's diagnostic names the offending parameter.
        assert "Frame" in msg


class TestStepDependencyGraphMaxDegreeProperties:
    """``max_indegree`` and ``max_outdegree`` mirror the v0 reference's
    properties; both are ``O(V)`` walks over the node list and return
    ``0`` for an empty graph."""

    def _build_graph(self, deps_spec):
        """Build a graph from a list of (step_name, [depends_on_names])
        tuples. Returns a StepDependencyGraph."""
        from openjd.model._v1.job import StepDependencyGraph

        steps = []
        for name, deps in deps_spec:
            step = {
                "name": name,
                "script": {"actions": {"onRun": {"command": "echo"}}},
            }
            if deps:
                step["dependencies"] = [{"dependsOn": d} for d in deps]
            steps.append(step)
        t = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "T",
                "steps": steps,
            }
        )
        j = create_job(job_template=t, job_parameter_values={})
        return StepDependencyGraph(job=j)

    def test_chain_dependency(self) -> None:
        """A → B → C: max in-degree and max out-degree are both 1."""
        g = self._build_graph([("A", []), ("B", ["A"]), ("C", ["B"])])
        assert g.max_indegree == 1
        assert g.max_outdegree == 1

    def test_fan_in(self) -> None:
        """A → C ← B: max in-degree is 2, max out-degree is 1."""
        g = self._build_graph([("A", []), ("B", []), ("C", ["A", "B"])])
        assert g.max_indegree == 2
        assert g.max_outdegree == 1

    def test_fan_out(self) -> None:
        """A → B, A → C: max in-degree is 1, max out-degree is 2."""
        g = self._build_graph([("A", []), ("B", ["A"]), ("C", ["A"])])
        assert g.max_indegree == 1
        assert g.max_outdegree == 2

    def test_no_dependencies(self) -> None:
        """A graph with no edges reports zero for both degrees."""
        g = self._build_graph([("A", []), ("B", []), ("C", [])])
        assert g.max_indegree == 0
        assert g.max_outdegree == 0


class TestActionTimeoutShape:
    """``Action.timeout`` returns ``Optional[FormatString]`` — mirroring
    template-time ``Action.timeout``. Callers can read the unresolved
    template form via ``.raw()`` or evaluate against runtime symbols
    via ``.resolve(...)``."""

    def test_integer_timeout_returns_format_string(self) -> None:
        from openjd.expr import FormatString

        t = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "T",
                "steps": [
                    {
                        "name": "S",
                        "script": {
                            "actions": {"onRun": {"command": "echo", "timeout": 60}},
                        },
                    }
                ],
            }
        )
        j = create_job(job_template=t, job_parameter_values={})
        timeout = j.steps[0].script.actions.onRun.timeout
        assert isinstance(timeout, FormatString)
        assert timeout.raw() == "60"

    def test_no_timeout_returns_none(self) -> None:
        t = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "T",
                "steps": [
                    {
                        "name": "S",
                        "script": {"actions": {"onRun": {"command": "echo"}}},
                    }
                ],
            }
        )
        j = create_job(job_template=t, job_parameter_values={})
        assert j.steps[0].script.actions.onRun.timeout is None


class TestTokenErrorRemovedFromV1:
    """``TokenError`` is intentionally **not** part of the v1 surface.
    It existed as a v0-compat re-export shim, but no v1 code path
    raises it — every actual raise lives in the v0 (pure-Python)
    parser modules. Pinning the absence so a future refactor doesn't
    silently re-introduce a dead-code shim."""

    def test_not_in_v1_top_level(self) -> None:
        import openjd.model._v1 as v1

        assert not hasattr(v1, "TokenError")
        assert "TokenError" not in v1.__all__

    def test_import_raises_import_error(self) -> None:
        with pytest.raises(ImportError):
            from openjd.model._v1 import TokenError  # type: ignore[attr-defined]  # noqa: F401


class TestPreprocessAcceptsItsOwnEmptyListPath:
    """``preprocess_job_parameters`` must accept every value it emits, because
    callers feed it its own output (preprocess, then ``create_job``, which
    re-checks constraints). openjd-model 0.8.0 (openjd-rs#384) fixes the one
    value that broke this: a ``LIST[PATH]`` parameter defaulting to ``[]``, which
    0.7.1 refused on the second pass with ``Cannot coerce list to LIST[PATH]``.
    """

    @staticmethod
    def _template() -> Any:
        return decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "T",
                "extensions": ["EXPR"],
                "parameterDefinitions": [{"name": "Empty", "type": "LIST[PATH]", "default": []}],
                "steps": [{"name": "S", "script": {"actions": {"onRun": {"command": "echo"}}}}],
            },
            supported_extensions=["EXPR"],
        )

    def test_second_pass_accepts_the_first_pass_output(self) -> None:
        template = self._template()
        first = preprocess_job_parameters(
            job_template=template,
            job_parameter_values={},
            job_template_dir=Path.cwd(),
            current_working_dir=Path.cwd(),
        )
        second = preprocess_job_parameters(
            job_template=template,
            job_parameter_values=first,
            job_template_dir=Path.cwd(),
            current_working_dir=Path.cwd(),
        )
        assert first == second
        assert first["Empty"].type == JobParameterType.LIST_PATH
        assert first["Empty"].value == "[]"

    def test_create_job_accepts_the_preprocessed_value(self) -> None:
        template = self._template()
        values = preprocess_job_parameters(
            job_template=template,
            job_parameter_values={},
            job_template_dir=Path.cwd(),
            current_working_dir=Path.cwd(),
        )
        job = create_job(job_template=template, job_parameter_values=values)
        assert job.parameters["Empty"].value.item() == []


class TestResolvedJobNameControlCharacters:
    """Template Schemas §1.1.1 forbids Cc characters in the job name. When the name
    is interpolated, the resolved value is only known at ``create_job``, which
    since openjd-model 0.8.0 (openjd-rs#397) rejects a control character there.
    0.7.1 re-checked only emptiness and length, so ``Suffix = "a\\nb"`` produced a
    job named ``render-a\\nb``.
    """

    @staticmethod
    def _template() -> Any:
        return decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "render-{{ Param.Suffix }}",
                "extensions": ["EXPR"],
                "parameterDefinitions": [{"name": "Suffix", "type": "STRING"}],
                "steps": [{"name": "S", "script": {"actions": {"onRun": {"command": "echo"}}}}],
            },
            supported_extensions=["EXPR"],
        )

    @pytest.mark.parametrize("suffix", ["a\nb", "a\tb", "\x7f"], ids=["newline", "tab", "DEL"])
    def test_control_character_in_the_resolved_name_is_rejected(self, suffix: str) -> None:
        with pytest.raises(DecodeValidationError) as excinfo:
            create_job(job_template=self._template(), job_parameter_values={"Suffix": suffix})
        assert "Job name must not contain control characters" in str(excinfo.value)

    def test_clean_resolved_name_is_accepted(self) -> None:
        job = create_job(job_template=self._template(), job_parameter_values={"Suffix": "ok"})
        assert job.name == "render-ok"


class TestDeferredSingleValuedAllOfIsRecheckedAtJobCreation:
    """Companion to ``test_parse.py::TestResolvedValueConstraintsAtTemplateValidation``.
    A whole-field expression element of a single-valued ``allOf`` passes template
    validation because it may resolve to ``null`` and skip itself. openjd-model
    0.8.0 (openjd-rs#397) then re-checks the resolved element count at job creation.
    """

    @staticmethod
    def _template() -> Any:
        return decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "T",
                "extensions": ["EXPR"],
                "parameterDefinitions": [{"name": "X", "type": "STRING"}],
                "steps": [
                    {
                        "name": "S",
                        "script": {"actions": {"onRun": {"command": "echo"}}},
                        "hostRequirements": {
                            "attributes": [
                                {
                                    "name": "attr.worker.os.family",
                                    "allOf": [
                                        "linux",
                                        "{{ Param.X if Param.X != 'skip' else null }}",
                                    ],
                                }
                            ]
                        },
                    }
                ],
            },
            supported_extensions=["EXPR"],
        )

    def test_a_second_resolved_value_is_rejected(self) -> None:
        with pytest.raises(DecodeValidationError) as excinfo:
            create_job(job_template=self._template(), job_parameter_values={"X": "windows"})
        assert (
            "steps[0] -> hostRequirements -> attributes[0] -> allOf: "
            "single-valued attribute cannot have more than 1 element after resolution"
        ) in str(excinfo.value)

    def test_a_null_skipped_element_leaves_one_value(self) -> None:
        job = create_job(job_template=self._template(), job_parameter_values={"X": "skip"})
        host_requirements = job.steps[0].host_requirements
        assert host_requirements is not None
        assert host_requirements.attributes is not None
        assert host_requirements.attributes[0].all_of == ["linux"]


class TestCreateJobPreservesFeatureBundle1Lengths:
    """The FEATURE_BUNDLE_1 raised length ceilings survive job creation on the v1 lane.

    FEATURE_BUNDLE_1 raises four string-length ceilings: job name and environment name
    to 512, embedded-file filename to 256, and the section 7.1 identifier -- an
    embedded-file name or a job parameter name -- to 512. A value template validation
    accepted under the extension must survive preprocess_job_parameters and create_job.

    The v0 lane lost the extension set between decode and job creation and rejected such
    values, first when create_job reconstructed the target models and separately in the
    job-parameter merge. v1 validates in a single pass in Rust and never re-validates a
    constructed model, so it is expected to pass throughout; these tests pin that so a
    re-validation pass cannot be added to the Rust implementation unnoticed.

    Groups:
      A. Each of the four ceilings survives create_job.
      B. The job parameter name survives the merge, preprocess_job_parameters and
         create_job, for every scalar parameter type.
      C. Controls: 513 and 65 are rejected, and the base ceiling is preserved.
      D. Round trip: every lengthened field at once.
    """

    _FB1 = ["FEATURE_BUNDLE_1"]

    #: Defaults per scalar parameter type, so one template shape covers all four.
    _TYPE_DEFAULTS = {"STRING": "v", "PATH": "/tmp/v", "INT": "1", "FLOAT": "1.5"}

    @classmethod
    def _template(
        cls,
        *,
        job_name: str = "J",
        env_name: str = "Env1",
        ef_name: str = "Run",
        ef_filename: str = "run.sh",
        param_name: str = "P",
        param_type: str = "STRING",
        declare_fb1: bool = True,
    ) -> dict:
        """A minimal template with one step, one embedded file, one job environment and
        one job parameter, so all four ceilings are reachable from one shape."""
        template: dict = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": job_name,
            "parameterDefinitions": [
                {
                    "name": param_name,
                    "type": param_type,
                    "default": cls._TYPE_DEFAULTS[param_type],
                }
            ],
            "steps": [
                {
                    "name": "S",
                    "script": {
                        "actions": {"onRun": {"command": "echo"}},
                        "embeddedFiles": [
                            {
                                "name": ef_name,
                                "type": "TEXT",
                                "data": "echo hi",
                                "filename": ef_filename,
                            }
                        ],
                    },
                }
            ],
            "jobEnvironments": [
                {
                    "name": env_name,
                    "script": {"actions": {"onEnter": {"command": "echo enter"}}},
                }
            ],
        }
        if declare_fb1:
            template["extensions"] = ["FEATURE_BUNDLE_1"]
        return template

    @classmethod
    def _preprocess(cls, template: dict, supported: list, env_templates: Any = None) -> dict:
        """Decode the template and run it through preprocess_job_parameters.

        Paths do not matter to a name-length check, so this uses the walk-up form rather
        than real directories.
        """
        job_template = decode_job_template(template=template, supported_extensions=supported)
        return preprocess_job_parameters(
            job_template=job_template,
            job_parameter_values={},
            job_template_dir=Path(),
            current_working_dir=Path(),
            allow_job_template_dir_walk_up=True,
            environment_templates=env_templates,
        )

    @classmethod
    def _create(cls, template: dict) -> Any:
        """Decode with FEATURE_BUNDLE_1 supported, apply defaults, then create the job."""
        job_template = decode_job_template(template=template, supported_extensions=cls._FB1)
        values = preprocess_job_parameters(
            job_template=job_template,
            job_parameter_values={},
            job_template_dir=Path(),
            current_working_dir=Path(),
            allow_job_template_dir_walk_up=True,
        )
        return create_job(job_template=job_template, job_parameter_values=values)

    # ---- Group A: each ceiling survives create_job ----

    def test_job_name_512_chars_fb1_create_job_preserved(self) -> None:
        """A 512-char job name accepted at FEATURE_BUNDLE_1 decode survives create_job."""
        job = self._create(self._template(job_name="a" * 512))
        assert len(job.name) == 512

    def test_environment_name_512_chars_fb1_create_job_preserved(self) -> None:
        """A 512-char job-environment name survives create_job."""
        job = self._create(self._template(env_name="a" * 512))
        environments = job.jobEnvironments
        assert environments is not None
        assert len(environments[0].name) == 512

    def test_embedded_file_name_512_chars_fb1_create_job_preserved(self) -> None:
        """A 512-char embedded-file name survives create_job."""
        job = self._create(self._template(ef_name="a" * 512))
        embedded = job.steps[0].script.embeddedFiles
        assert embedded is not None
        assert len(embedded[0].name) == 512

    def test_embedded_file_filename_256_chars_fb1_create_job_preserved(self) -> None:
        """A 256-char embedded-file filename survives create_job."""
        job = self._create(self._template(ef_filename="a" * 256))
        embedded = job.steps[0].script.embeddedFiles
        assert embedded is not None
        assert len(embedded[0].filename) == 256

    # ---- Group B: the job parameter name, through every stage ----

    @pytest.mark.parametrize("param_type", sorted(_TYPE_DEFAULTS))
    def test_parameter_name_512_chars_fb1_merge_preserved(self, param_type: str) -> None:
        """The job-parameter merge preserves a 512-char name. This is the stage the v0
        lane re-validated without the extension set."""
        name = "a" * 512
        job_template = decode_job_template(
            template=self._template(param_name=name, param_type=param_type),
            supported_extensions=self._FB1,
        )
        merged = merge_job_parameter_definitions(job_template=job_template)
        assert [d["name"] for d in merged] == [name]

    @pytest.mark.parametrize("param_type", sorted(_TYPE_DEFAULTS))
    def test_parameter_name_512_chars_fb1_preprocess_preserved(self, param_type: str) -> None:
        """preprocess_job_parameters preserves a 512-char parameter name."""
        name = "a" * 512
        values = self._preprocess(self._template(param_name=name, param_type=param_type), self._FB1)
        assert name in values

    @pytest.mark.parametrize("param_type", sorted(_TYPE_DEFAULTS))
    def test_parameter_name_512_chars_fb1_create_job_preserved(self, param_type: str) -> None:
        """create_job preserves a 512-char parameter name."""
        name = "a" * 512
        job = self._create(self._template(param_name=name, param_type=param_type))
        assert name in job.parameters

    def test_parameter_name_512_chars_from_environment_template_preserved(self) -> None:
        """A 512-char name declared by an environment template that enables
        FEATURE_BUNDLE_1 survives even though the job template does not enable it."""
        name = "a" * 512
        env_template = decode_environment_template(
            template={
                "specificationVersion": "environment-2023-09",
                "extensions": ["FEATURE_BUNDLE_1"],
                "parameterDefinitions": [{"name": name, "type": "STRING", "default": "v"}],
                "environment": minimal_environment_2023_09,
            },
            supported_extensions=self._FB1,
        )
        plain_template = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "J",
            "steps": minimal_steps_v2023_09,
        }
        values = self._preprocess(plain_template, [], env_templates=[env_template])
        assert name in values

    # ---- Group C: controls ----

    def test_parameter_name_513_chars_rejected_by_static_ceiling(self) -> None:
        """512 is the hard identifier ceiling regardless of extension: at 513 the
        identifier length check rejects before any extension-aware limit applies."""
        with pytest.raises(DecodeValidationError) as excinfo:
            decode_job_template(
                template=self._template(param_name="a" * 513),
                supported_extensions=self._FB1,
            )
        assert "Identifier length must be 1..=512, got 513" in str(excinfo.value)

    def test_parameter_name_65_chars_no_extension_decode_rejected(self) -> None:
        """Without the extension the base 64-character limit applies, and it is reached at
        decode -- before the merge ever runs."""
        with pytest.raises(ModelValidationError) as excinfo:
            decode_job_template(
                template=self._template(param_name="a" * 65, declare_fb1=False),
                supported_extensions=[],
            )
        assert "parameterDefinitions[0]:\n\tname exceeds 64 characters." in str(excinfo.value)

    def test_job_name_129_chars_no_extension_decode_rejected(self) -> None:
        """Without the extension the base 128-character job-name limit applies."""
        with pytest.raises(ModelValidationError) as excinfo:
            decode_job_template(
                template=self._template(job_name="a" * 129, declare_fb1=False),
                supported_extensions=[],
            )
        assert "exceeds 128 characters" in str(excinfo.value)

    def test_parameter_name_64_chars_no_extension_create_job_preserved(self) -> None:
        """A parameter name at the base ceiling survives create_job with no extension."""
        name = "a" * 64
        job_template = decode_job_template(
            template=self._template(param_name=name, declare_fb1=False),
            supported_extensions=[],
        )
        values = preprocess_job_parameters(
            job_template=job_template,
            job_parameter_values={},
            job_template_dir=Path(),
            current_working_dir=Path(),
            allow_job_template_dir_walk_up=True,
        )
        job = create_job(job_template=job_template, job_parameter_values=values)
        assert name in job.parameters

    # ---- Group D: round trip ----

    def test_all_five_fields_at_ceiling_fb1_create_job_preserved(self) -> None:
        """Every FEATURE_BUNDLE_1-lengthened field survives create_job at once."""
        param_name = "a" * 512
        job = self._create(
            self._template(
                job_name="a" * 512,
                env_name="a" * 512,
                ef_name="a" * 512,
                ef_filename="a" * 256,
                param_name=param_name,
            )
        )
        environments = job.jobEnvironments
        embedded = job.steps[0].script.embeddedFiles
        assert environments is not None
        assert embedded is not None
        assert (
            len(job.name),
            len(environments[0].name),
            len(embedded[0].name),
            len(embedded[0].filename),
            param_name in job.parameters,
        ) == (512, 512, 512, 256, True)


class TestResolvedValueCapsAtJobCreation:
    """Companion to ``test_parse.py::TestResolvedValueCapsAtTemplateValidation``.
    ``max_resolved_arg_len`` / ``max_resolved_data_len`` (openjd-model 0.9.0,
    openjd-rs#399) are checked twice on this path: at template validation against
    the guaranteed lower bound of every resolution, then again at job creation with
    the job parameters bound. A field whose value comes from a parameter has a lower
    bound of 0 at validation, so job creation is the stage that can reject it.

    Caller limits reach ``create_job`` through a ``ValidationContext``; omitting one
    uses the template's default context, which carries no limits.
    """

    _LIMITS = CallerLimits(max_resolved_arg_len=10, max_resolved_data_len=10)

    @classmethod
    def _decoded(cls, **script_extras: Any) -> Any:
        action: dict[str, Any] = {"command": "echo", "args": ["{{Param.P}}"]}
        script: dict[str, Any] = {"actions": {"onRun": action}}
        script.update(script_extras)
        return decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "T",
                "parameterDefinitions": [{"name": "P", "type": "STRING"}],
                "steps": [{"name": "S", "script": script}],
            },
            supported_extensions=[],
            caller_limits=cls._LIMITS,
        )

    @classmethod
    def _context(cls, decoded: Any) -> Any:
        return ValidationContext(decoded.profile, caller_limits=cls._LIMITS)

    def test_template_passes_validation_because_the_bound_is_unknown(self) -> None:
        """Control for the deferral: the cap is 10 and the only literal run in the
        argument is empty, so validation cannot reject."""
        assert self._decoded()

    def test_a_parameter_value_over_the_cap_is_rejected(self) -> None:
        decoded = self._decoded()
        with pytest.raises(ModelValidationError) as excinfo:
            create_job(
                job_template=decoded,
                job_parameter_values={"P": "c" * 30},
                validation_context=self._context(decoded),
            )
        message = str(excinfo.value)
        assert "steps[0] -> script -> actions -> onRun -> args[0]" in message
        assert "resolves to at least 30 characters, exceeding the maximum of 10" in message

    def test_a_parameter_value_under_the_cap_is_accepted(self) -> None:
        """Negative control: the same template and context with a value that fits.

        The argument stays a ``FormatString`` on the created job — job creation
        checks the resolved length without substituting it, because an action's
        arguments also depend on task parameters and resolve in the session."""
        decoded = self._decoded()
        job = create_job(
            job_template=decoded,
            job_parameter_values={"P": "short"},
            validation_context=self._context(decoded),
        )
        args = job.steps[0].script.actions.onRun.args
        assert args is not None
        assert [str(a) for a in args] == ["{{Param.P}}"]
        assert "P" in job.parameters

    def test_without_caller_limits_any_length_is_accepted(self) -> None:
        """Negative control: with no limits in the context the value passes, which is
        the only behaviour openjd-model 0.8.0 had."""
        decoded = self._decoded()
        assert create_job(job_template=decoded, job_parameter_values={"P": "c" * 30})

    def test_embedded_file_data_over_the_cap_is_rejected(self) -> None:
        decoded = self._decoded(
            embeddedFiles=[{"name": "F", "type": "TEXT", "data": "{{Param.P}}"}]
        )
        with pytest.raises(ModelValidationError) as excinfo:
            create_job(
                job_template=decoded,
                job_parameter_values={"P": "d" * 30},
                validation_context=self._context(decoded),
            )
        message = str(excinfo.value)
        assert "steps[0] -> script -> embeddedFiles[0] -> data" in message
        assert "resolves to at least 30 characters, exceeding the maximum of 10" in message


class TestJobEnvironmentResolvedValueCapsAtJobCreation:
    """openjd-model 0.9.0 (openjd-rs#404) re-runs the resolved-value checks on the
    job environments that ``create_job`` carries forward into the job, against a
    session-scope symbol table. A job environment's script is not part of a step, so
    the step-walking re-check of openjd-rs#399 alone did not reach it: on 0.9.0
    without #404 the same template would produce a job whose ``onEnter`` argument is
    30 characters under a cap of 10.
    """

    _LIMITS = CallerLimits(max_resolved_arg_len=10)

    @classmethod
    def _decoded(cls) -> Any:
        return decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "T",
                "parameterDefinitions": [{"name": "P", "type": "STRING"}],
                "jobEnvironments": [
                    {
                        "name": "JobEnv",
                        "script": {
                            "actions": {"onEnter": {"command": "echo", "args": ["{{Param.P}}"]}}
                        },
                    }
                ],
                "steps": [{"name": "S", "script": {"actions": {"onRun": {"command": "echo"}}}}],
            },
            supported_extensions=[],
            caller_limits=cls._LIMITS,
        )

    def test_job_environment_argument_over_the_cap_is_rejected(self) -> None:
        decoded = self._decoded()
        with pytest.raises(ModelValidationError) as excinfo:
            create_job(
                job_template=decoded,
                job_parameter_values={"P": "e" * 30},
                validation_context=ValidationContext(decoded.profile, caller_limits=self._LIMITS),
            )
        message = str(excinfo.value)
        assert "jobEnvironments[0] -> script -> actions -> onEnter -> args[0]" in message
        assert "resolves to at least 30 characters, exceeding the maximum of 10" in message

    def test_job_environment_argument_under_the_cap_is_accepted(self) -> None:
        """Negative control, and it pins that the environment is still carried
        forward onto the job with its argument unsubstituted — the check reads the
        resolved length, it does not rewrite the field."""
        decoded = self._decoded()
        job = create_job(
            job_template=decoded,
            job_parameter_values={"P": "short"},
            validation_context=ValidationContext(decoded.profile, caller_limits=self._LIMITS),
        )
        environments = job.jobEnvironments
        assert environments is not None
        script = environments[0].script
        assert script is not None
        on_enter = script.actions.onEnter
        assert on_enter is not None
        args = on_enter.args
        assert args is not None
        assert [str(a) for a in args] == ["{{Param.P}}"]


class TestFormatStringCapabilityNamesAtJobCreation:
    """Companion to ``test_parse.py::TestFormatStringCapabilityNames``. A capability
    ``name`` that depends on a job parameter is only fully known at job creation, so
    that is where openjd-model 0.10.0 (openjd-rs#409) applies the §3.3.1.1 /
    §3.3.2.1 constraints and the case-insensitive uniqueness rule.

    Every rejection here was unreachable on 0.9.0: the template did not decode. Each
    rule is exercised on both ``amounts`` and ``attributes``, which upstream checks
    through separate call sites with separate messages.
    """

    _KINDS = [pytest.param("amounts", id="amounts"), pytest.param("attributes", id="attributes")]

    @staticmethod
    def _entry(kind: str, name: str) -> dict[str, Any]:
        if kind == "amounts":
            return {"name": name, "min": "1"}
        return {"name": name, "anyOf": ["linux"]}

    @classmethod
    def _template(cls, kind: str, *names: str) -> dict[str, Any]:
        return {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "T",
            "parameterDefinitions": [{"name": "Attr", "type": "STRING"}],
            "steps": [
                {
                    "name": "S",
                    "hostRequirements": {kind: [cls._entry(kind, n) for n in names]},
                    "script": {"actions": {"onRun": {"command": "echo"}}},
                }
            ],
        }

    @classmethod
    def _created_names(cls, kind: str, value: str, *names: str) -> list[str]:
        decoded = decode_job_template(template=cls._template(kind, *names))
        job = create_job(job_template=decoded, job_parameter_values={"Attr": value})
        requirements = job.steps[0].host_requirements
        assert requirements is not None
        entries = requirements.amounts if kind == "amounts" else requirements.attributes
        assert entries is not None
        return [e.name for e in entries]

    @classmethod
    def _created_name(cls, kind: str, value: str) -> str:
        return cls._created_names(kind, value, "{{Param.Attr}}")[0]

    @pytest.mark.parametrize("kind", _KINDS)
    @pytest.mark.parametrize(
        "value",
        [
            pytest.param("custom.x", id="customer-defined"),
            pytest.param("vendor:custom.x", id="vendor-prefixed"),
        ],
    )
    def test_the_resolved_name_is_written_onto_the_job(self, kind: str, value: str) -> None:
        prefix = "amount" if kind == "amounts" else "attr"
        name = value.replace("custom.x", f"{prefix}.custom.x")
        assert self._created_name(kind, name) == name

    @pytest.mark.parametrize(
        "kind,name",
        [
            pytest.param("amounts", "amount.worker.vcpu", id="amounts"),
            pytest.param("attributes", "attr.worker.os.family", id="attributes"),
        ],
    )
    def test_a_resolved_standard_capability_name_is_accepted(self, kind: str, name: str) -> None:
        assert self._created_name(kind, name) == name

    @pytest.mark.parametrize("kind", _KINDS)
    @pytest.mark.parametrize(
        "value,expected_message",
        [
            pytest.param(
                "not a name",
                "name 'not a name' does not match capability name pattern.",
                id="pattern",
            ),
            pytest.param("PREFIX.worker.made_up", "reserved scope 'worker'", id="reserved scope"),
        ],
    )
    def test_a_resolved_name_violating_its_constraints_is_rejected(
        self, kind: str, value: str, expected_message: str
    ) -> None:
        prefix = "amount" if kind == "amounts" else "attr"
        with pytest.raises(ModelValidationError) as excinfo:
            self._created_name(kind, value.replace("PREFIX", prefix))
        assert expected_message in str(excinfo.value)

    @pytest.mark.parametrize("kind", _KINDS)
    def test_a_resolved_name_over_100_characters_is_rejected(self, kind: str) -> None:
        prefix = "amount.custom." if kind == "amounts" else "attr.custom."
        name = prefix + "a" * (101 - len(prefix))
        assert len(name) == 101
        with pytest.raises(ModelValidationError) as excinfo:
            self._created_name(kind, name)
        assert "exceeds 100 characters." in str(excinfo.value)

    @pytest.mark.parametrize("kind", _KINDS)
    def test_the_100_character_boundary_is_accepted(self, kind: str) -> None:
        """Negative control for the length case above: exactly 100 characters passes,
        so the check is a boundary and not an unconditional rejection."""
        prefix = "amount.custom." if kind == "amounts" else "attr.custom."
        name = prefix + "a" * (100 - len(prefix))
        assert len(name) == 100
        assert self._created_name(kind, name) == name

    @pytest.mark.parametrize(
        "kind,literal,value",
        [
            pytest.param("amounts", "amount.custom.x", "AMOUNT.CUSTOM.X", id="amounts"),
            pytest.param("attributes", "attr.custom.x", "ATTR.CUSTOM.X", id="attributes"),
        ],
    )
    def test_a_resolved_name_colliding_with_a_literal_is_rejected(
        self, kind: str, literal: str, value: str
    ) -> None:
        """Uniqueness is case-insensitive and spans both spellings, so a format string
        cannot smuggle in a duplicate of a literal sibling."""
        singular = "amount" if kind == "amounts" else "attribute"
        with pytest.raises(ModelValidationError) as excinfo:
            self._created_names(kind, value, literal, "{{Param.Attr}}")
        assert f"duplicate {singular} name '{value}'." in str(excinfo.value)

    @pytest.mark.parametrize(
        "kind,literal,value",
        [
            pytest.param("amounts", "amount.custom.x", "amount.custom.y", id="amounts"),
            pytest.param("attributes", "attr.custom.x", "attr.custom.y", id="attributes"),
        ],
    )
    def test_two_distinct_resolved_names_are_accepted(
        self, kind: str, literal: str, value: str
    ) -> None:
        """Negative control for the collision case: the uniqueness check compares the
        resolved names, so a distinct resolution is fine."""
        assert self._created_names(kind, value, literal, "{{Param.Attr}}") == [literal, value]

    @pytest.mark.parametrize(
        "any_of,expected_message",
        [
            pytest.param(
                ["plan9"], "value 'plan9' is not valid for attr.worker.os.family.", id="rejected"
            ),
            pytest.param(["linux"], None, id="accepted"),
        ],
    )
    def test_the_resolved_name_identifies_a_standard_attribute_for_its_value_checks(
        self, any_of: list[str], expected_message: Optional[str]
    ) -> None:
        """Whether a capability is standard — and therefore which values are legal —
        is decided by the *resolved* name. At decode the name was unknown, so no value
        check could attach; this is the stage that supplies one."""
        template = self._template("attributes", "{{Param.Attr}}")
        template["steps"][0]["hostRequirements"]["attributes"][0]["anyOf"] = any_of
        decoded = decode_job_template(template=template)
        if expected_message is None:
            job = create_job(
                job_template=decoded, job_parameter_values={"Attr": "attr.worker.os.family"}
            )
            assert job.name == "T"
            return
        with pytest.raises(ModelValidationError) as excinfo:
            create_job(job_template=decoded, job_parameter_values={"Attr": "attr.worker.os.family"})
        assert expected_message in str(excinfo.value)


class TestCreateJobContextExtensionContract:
    """openjd-model 0.10.0 (openjd-rs#407) requires ``create_job``'s context to cover
    every extension the template declares. On 0.9.0 passing a context that stripped
    ``EXPR`` created the job, and the resolved-value checks silently skipped every
    evaluation error as possibly-a-context-artifact.

    ``create_job`` without ``validation_context`` derives the context from the
    template, so the default path cannot violate the contract.
    """

    _TEMPLATE: dict[str, Any] = {
        "specificationVersion": "jobtemplate-2023-09",
        "extensions": ["EXPR"],
        "name": "T",
        "steps": [{"name": "S", "script": {"actions": {"onRun": {"command": "echo"}}}}],
    }

    @classmethod
    def _decoded(cls) -> Any:
        return decode_job_template(template=cls._TEMPLATE, supported_extensions=["EXPR"])

    def test_the_default_context_satisfies_the_contract(self) -> None:
        assert create_job(job_template=self._decoded(), job_parameter_values={}).name == "T"

    def test_a_context_derived_from_the_template_satisfies_the_contract(self) -> None:
        decoded = self._decoded()
        job = create_job(
            job_template=decoded,
            job_parameter_values={},
            validation_context=ValidationContext(decoded.profile),
        )
        assert job.name == "T"

    def test_a_context_that_strips_a_declared_extension_is_rejected(self) -> None:
        with pytest.raises(ModelValidationError) as excinfo:
            create_job(
                job_template=self._decoded(),
                job_parameter_values={},
                validation_context=ValidationContext(ModelProfile(extensions=[])),
            )
        message = str(excinfo.value)
        assert "every extension the template declares" in message
        assert "missing EXPR" in message

    def test_a_context_enabling_more_than_the_template_declares_is_accepted(self) -> None:
        """Cover, not equality: the contract is that the context is a superset."""
        job = create_job(
            job_template=self._decoded(),
            job_parameter_values={},
            validation_context=ValidationContext(
                ModelProfile(extensions=[ModelExtension.EXPR, ModelExtension.TASK_CHUNKING])
            ),
        )
        assert job.name == "T"


class TestValueDependentEvaluationErrorAtJobCreation:
    """With the context contract enforced (openjd-rs#407), every evaluation error at
    job creation is a real defect, so the lenient policy that skipped them is gone.
    On 0.9.0 the failing case below created a job and the failure surfaced on every
    worker that ran the task instead.
    """

    _TEMPLATE: dict[str, Any] = {
        "specificationVersion": "jobtemplate-2023-09",
        "extensions": ["EXPR"],
        "name": "T",
        "parameterDefinitions": [{"name": "N", "type": "INT"}],
        "steps": [
            {
                "name": "S",
                "script": {
                    "actions": {"onRun": {"command": "echo", "args": ["{{ 10 // Param.N }}"]}}
                },
            }
        ],
    }

    @classmethod
    def _create(cls, divisor: int) -> Any:
        return create_job(
            job_template=decode_job_template(template=cls._TEMPLATE, supported_extensions=["EXPR"]),
            job_parameter_values={"N": divisor},
        )

    def test_a_healthy_value_creates_the_job(self) -> None:
        """Negative control, and it pins that the check reads the resolved value
        without rewriting the field: the argument stays a format string on the job,
        because task parameters resolve in the session."""
        job = self._create(2)
        args = job.steps[0].script.actions.onRun.args
        assert args is not None
        assert [str(a) for a in args] == ["{{ 10 // Param.N }}"]

    def test_a_value_dependent_error_fails_job_creation(self) -> None:
        with pytest.raises(ModelValidationError) as excinfo:
            self._create(0)
        message = str(excinfo.value)
        assert "Division by zero" in message
        assert "steps[0] -> script -> actions -> onRun -> args[0]" in message


class TestEvaluationBudgetsInsideUnresolvedConditionals:
    """openjd-rs#407 stopped the evaluator absorbing *budget* errors raised inside a
    branch of a conditional whose test is unresolved. The budget is spent in this
    evaluation whichever branch run time takes, so a caller who lowered
    ``max_eval_operations`` had it silently stop applying — this is the idiomatic
    construction for a worker-resolved test, so the bypass was reachable.

    The expression-level pins live in
    ``test/openjd/expr/test_unresolved_eval.py``; this class covers the path through
    ``create_job``, where the budget arrives on a ``CallerLimits``.
    """

    _TEMPLATE: dict[str, Any] = {
        "specificationVersion": "jobtemplate-2023-09",
        "extensions": ["EXPR"],
        "name": "T",
        "parameterDefinitions": [{"name": "N", "type": "INT"}],
        "steps": [
            {
                "name": "S",
                "script": {
                    "actions": {
                        "onRun": {
                            "command": "echo",
                            "args": ["{{ 'A' * Param.N if Session.HasPathMappingRules else 'B' }}"],
                        }
                    }
                },
            }
        ],
    }

    @classmethod
    def _create(cls, max_eval_operations: int) -> Any:
        decoded = decode_job_template(template=cls._TEMPLATE, supported_extensions=["EXPR"])
        return create_job(
            job_template=decoded,
            job_parameter_values={"N": 100_000},
            validation_context=ValidationContext(
                decoded.profile,
                caller_limits=CallerLimits(max_eval_operations=max_eval_operations),
            ),
        )

    def test_a_lowered_operation_budget_is_enforced_inside_the_conditional(self) -> None:
        with pytest.raises(ModelValidationError) as excinfo:
            self._create(5)
        message = str(excinfo.value)
        assert "operation count" in message
        assert "exceeded limit (5)" in message

    def test_a_budget_the_expression_fits_within_creates_the_job(self) -> None:
        """Negative control: the same template and the same parameter value, so the
        rejection above is the budget and not the construction."""
        assert self._create(1_000_000).name == "T"


class TestUnresolvedFilterComprehensionAtJobCreation:
    """The reviewer's repro from openjd-rs#407. Job creation evaluates under a symbol
    state no other stage sees — ``Param.*`` concrete, ``Task.*`` / ``Session.*``
    unresolved — so it is the only stage where this comprehension has a concrete
    iterable and an unresolved filter.

    This test does **not** discriminate 0.9.0 from 0.10.0: it creates a job on both,
    for different reasons. On 0.9.0 the comprehension raised and the lenient error
    policy silently skipped it; on 0.10.0 it raises nothing. It is here because the two
    halves of that release have to hold *together* — the strict policy of openjd-rs#407
    without its companion listcomp fix rejects this template, which is what upstream
    found in review. The discriminating pins are in
    ``test/openjd/expr/test_unresolved_eval.py::TestConcreteIterableUnresolvedFilter``.
    """

    _TEMPLATE: dict[str, Any] = {
        "specificationVersion": "jobtemplate-2023-09",
        "extensions": ["EXPR"],
        "name": "T",
        "parameterDefinitions": [{"name": "Files", "type": "STRING"}],
        "steps": [
            {
                "name": "S",
                "parameterSpace": {
                    "taskParameterDefinitions": [{"name": "Skip", "type": "STRING", "range": ["b"]}]
                },
                "script": {
                    "actions": {
                        "onRun": {
                            "command": "echo",
                            "args": [
                                "{{ [f for f in Param.Files.split(',') if f != Task.Param.Skip] }}"
                            ],
                        }
                    }
                },
            }
        ],
    }

    def test_the_template_creates_a_job(self) -> None:
        decoded = decode_job_template(template=self._TEMPLATE, supported_extensions=["EXPR"])
        job = create_job(job_template=decoded, job_parameter_values={"Files": "a,b,c"})
        args = job.steps[0].script.actions.onRun.args
        assert args is not None
        assert [str(a) for a in args] == [
            "{{ [f for f in Param.Files.split(',') if f != Task.Param.Skip] }}"
        ]


class TestValidationIsIndependentOfTheHostPathFormat:
    """openjd-rs#407 also made every stage that evaluates outside host context do so
    under ``PathFormat::Posix``. ``create_job`` already built its symbol tables that
    way, but its resolved-value re-checks and template validation's pass 8 evaluated
    under the *host* format — so a PATH value flowing from a ``let`` binding into an
    argument drew ``Path format mismatch`` on Windows, masked until the strict error
    policy exposed it as 11 conformance failures.

    On a POSIX host the host format *is* POSIX, so this assertion is a no-op here and
    carries its weight only on the Windows CI lane. It is the only change in this bump
    whose effect is platform-dependent.
    """

    def test_a_path_from_a_let_binding_reaches_an_argument(self) -> None:
        decoded = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["EXPR"],
                "name": "T",
                "parameterDefinitions": [{"name": "P", "type": "PATH"}],
                "steps": [
                    {
                        "name": "S",
                        "let": ["p = RawParam.P"],
                        "script": {
                            "actions": {"onRun": {"command": "echo", "args": ["{{ string(p) }}"]}}
                        },
                    }
                ],
            },
            supported_extensions=["EXPR"],
        )
        job = create_job(job_template=decoded, job_parameter_values={"P": "/tmp/x"})
        args = job.steps[0].script.actions.onRun.args
        assert args is not None
        assert [str(a) for a in args] == ["{{ string(p) }}"]


class TestSimpleActionCapsAtJobCreation:
    """openjd-model 0.11.0 (openjd-rs#419) reports a ``SimpleAction`` step's
    job-creation cap failures at the authored path. On 0.10.0 the same failures
    named the desugared step: ``steps[0] -> script -> embeddedFiles[0] -> data`` for
    the script and ``... -> onRun -> args[3]`` for ``cmd``'s ``args[1]``.
    """

    @staticmethod
    def _decoded(kind: str) -> Any:
        return decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["FEATURE_BUNDLE_1"],
                "name": "T",
                "parameterDefinitions": [{"name": "X", "type": "STRING"}],
                "steps": [
                    {
                        "name": "S",
                        kind: {"script": "{{Param.X}}", "args": ["--flag", "{{Param.X}}"]},
                    }
                ],
            },
            supported_extensions=["FEATURE_BUNDLE_1"],
        )

    @pytest.mark.parametrize(
        "kind,limits,expected",
        [
            pytest.param(
                "bash",
                CallerLimits(max_resolved_data_len=100),
                "steps[0] -> bash -> script:\n\t"
                "resolves to at least 200 characters, exceeding the maximum of 100.",
                id="script over the data cap",
            ),
            pytest.param(
                "cmd",
                CallerLimits(max_resolved_arg_len=100),
                "steps[0] -> cmd -> args[1]:\n\t"
                "resolves to at least 200 characters, exceeding the maximum of 100.",
                id="argument over the arg cap",
            ),
        ],
    )
    def test_a_parameter_value_over_the_cap_is_reported_at_the_authored_path(
        self, kind: str, limits: CallerLimits, expected: str
    ) -> None:
        decoded = self._decoded(kind)
        with pytest.raises(ModelValidationError) as excinfo:
            create_job(
                job_template=decoded,
                job_parameter_values={"X": "A" * 200},
                validation_context=ValidationContext(decoded.profile, caller_limits=limits),
            )
        assert str(excinfo.value) == "1 validation error for JobTemplate\n" + expected

    def test_a_value_under_both_caps_desugars(self) -> None:
        """Control: the created step carries the desugared action, with the generated
        script file as the first argument."""
        decoded = self._decoded("python")
        limits = CallerLimits(max_resolved_data_len=100, max_resolved_arg_len=100)
        job = create_job(
            job_template=decoded,
            job_parameter_values={"X": "short"},
            validation_context=ValidationContext(decoded.profile, caller_limits=limits),
        )
        on_run = job.steps[0].script.actions.onRun
        assert on_run.command.raw() == "python"
        assert on_run.args is not None
        assert [a.raw() for a in on_run.args] == ["{{Task.File.S_script}}", "--flag", "{{Param.X}}"]


def _preprocess_posix(
    definitions: list[dict[str, Any]],
    values: Optional[dict[str, Any]] = None,
    *,
    walk_up: bool = False,
    environment_definitions: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """``preprocess_job_parameters`` with upstream's fixture directories. The binding
    resolves paths under the host format, so callers skip on Windows."""
    job_template: dict[str, Any] = {
        "specificationVersion": "jobtemplate-2023-09",
        "extensions": ["EXPR"],
        "name": "T",
        "steps": [{"name": "S", "script": {"actions": {"onRun": {"command": "echo"}}}}],
    }
    if definitions:
        job_template["parameterDefinitions"] = definitions
    template = decode_job_template(template=job_template, supported_extensions=["EXPR"])
    environments = None
    if environment_definitions:
        environments = [
            decode_environment_template(
                template={
                    "specificationVersion": "environment-2023-09",
                    "extensions": ["EXPR"],
                    "parameterDefinitions": environment_definitions,
                    "environment": {"name": "E", "variables": {"A": "b"}},
                },
                supported_extensions=["EXPR"],
            )
        ]
    return preprocess_job_parameters(
        job_template=template,
        job_parameter_values=values or {},
        environment_templates=environments,
        job_template_dir=Path("/a/job1"),
        current_working_dir=Path("/tmp/cwd"),
        allow_job_template_dir_walk_up=walk_up,
    )


_POSIX_ONLY = pytest.mark.skipif(
    sys.platform == "win32",
    reason="The binding resolves paths with PathFormat::host(); the Windows rows are separate.",
)
_OUTSIDE = (
    "references a path outside of the template directory. "
    "Walking up from the template directory is not permitted."
)
_ABSOLUTE = "is an absolute path. Default paths must be relative, and are joined to the job template's directory."


def _list_path(default: list[str]) -> list[dict[str, Any]]:
    return [{"name": "Paths", "type": "LIST[PATH]", "default": default}]


@_POSIX_ONLY
class TestListPathDefaultRules:
    """openjd-model 0.11.0 (openjd-rs#421, openjd-specifications#191, Template Schemas
    §2.2 and §2.12) applies the PATH default rules to each ``LIST[PATH]`` default
    element: it must be relative, must not walk out of the template directory unless
    the caller allows it, and is joined to the template directory and normalized. On
    0.10.0 every default here came back unchanged.

    v0 (``openjd.model.preprocess_job_parameters``) still returns every one of these
    defaults unjoined; see ``test_known_gaps.py``.
    """

    def test_relative_elements_are_joined_and_normalized(self) -> None:
        out = _preprocess_posix(_list_path(["./output", "sub/dir", "sub/../other", "."]))
        assert json.loads(out["Paths"].value) == [
            "/a/job1/output",
            "/a/job1/sub/dir",
            "/a/job1/other",
            "/a/job1",
        ]

    @pytest.mark.parametrize(
        "default,expected",
        [
            pytest.param(
                ["a.exr", "/abs/b.exr"],
                f"The default value of LIST[PATH] parameter Paths at item[1] {_ABSOLUTE}",
                id="absolute element",
            ),
            pytest.param(
                ["inside/a.exr", "../outside/b.exr"],
                f"The default value of LIST[PATH] parameter Paths at item[1] {_OUTSIDE}",
                id="escaping element",
            ),
            pytest.param(
                ["/x", "ok", "a/../../y"],
                f"The default value of LIST[PATH] parameter Paths at item[0] {_ABSOLUTE}\n"
                f"The default value of LIST[PATH] parameter Paths at item[2] {_OUTSIDE}",
                id="every bad element is reported",
            ),
            pytest.param(
                ["a/..", "..name", "a/../../b"],
                f"The default value of LIST[PATH] parameter Paths at item[2] {_OUTSIDE}",
                id="interior walk-up after valid elements",
            ),
            pytest.param(
                ["a.exr", "s3://bucket/key"],
                "Parameter 'Paths': URI path values are not permitted in defaults. "
                "Got 's3://bucket/key' at item[1]",
                id="URI element",
            ),
        ],
    )
    def test_a_bad_element_is_rejected(self, default: list[str], expected: str) -> None:
        with pytest.raises(DecodeValidationError) as excinfo:
            _preprocess_posix(_list_path(default))
        assert str(excinfo.value) == expected

    def test_walk_up_allows_absolute_and_escaping_elements(self) -> None:
        out = _preprocess_posix(_list_path(["/abs/a.exr", "../up/b.exr"]), walk_up=True)
        assert json.loads(out["Paths"].value) == ["/abs/a.exr", "/a/up/b.exr"]


@_POSIX_ONLY
class TestSubmittedPathNormalization:
    """openjd-model 0.11.0 (openjd-rs#421, Template Schemas §2.2) lexically normalizes
    a relative submitted PATH or ``LIST[PATH]`` value after joining it to the current
    working directory. On 0.10.0 ``sub/../other`` came back as
    ``/tmp/cwd/sub/../other`` and ``LIST[PATH]`` elements were not joined at all.
    Absolute submitted values are returned as written, before and after.
    """

    @pytest.mark.parametrize(
        "value,expected",
        [
            pytest.param(".", "/tmp/cwd", id="dot"),
            pytest.param("./b.exr", "/tmp/cwd/b.exr", id="dot slash"),
            pytest.param("sub/../other", "/tmp/cwd/other", id="dot dot"),
            pytest.param(
                "C:\\foo\\..\\bar",
                "/tmp/cwd/C:\\foo\\..\\bar",
                id="backslash is a filename character under POSIX",
            ),
        ],
    )
    def test_relative_path_value_is_joined_and_normalized(self, value: str, expected: str) -> None:
        out = _preprocess_posix([{"name": "P", "type": "PATH"}], {"P": value})
        assert out["P"].value == expected

    def test_list_path_elements_are_joined_and_normalized(self) -> None:
        out = _preprocess_posix(
            [{"name": "Paths", "type": "LIST[PATH]"}],
            {"Paths": ["rel/a.exr", "./b.exr", "/abs/c.exr", "../up"]},
        )
        assert json.loads(out["Paths"].value) == [
            "/tmp/cwd/rel/a.exr",
            "/tmp/cwd/b.exr",
            "/abs/c.exr",
            "/tmp/up",
        ]

    def test_a_submitted_uri_element_is_rejected(self) -> None:
        with pytest.raises(DecodeValidationError) as excinfo:
            _preprocess_posix(
                [{"name": "Paths", "type": "LIST[PATH]"}], {"Paths": ["a.exr", "s3://bucket/key"]}
            )
        assert str(excinfo.value) == (
            "Parameter 'Paths': URI path values are not permitted. Got 's3://bucket/key' at item[1]"
        )


@_POSIX_ONLY
class TestPathDefaultConstraintsAfterTheJoin:
    """openjd-model 0.11.0 (openjd-rs#421, Template Schemas §2.2) checks a PATH or
    ``LIST[PATH]`` default's constraints against the joined value, in the job and
    environment templates alike. On 0.10.0 all three cases passed: the scalar
    ``maxLength`` and ``allowedValues`` defaults were never re-checked after the join,
    and ``LIST[PATH]`` defaults were not joined.
    """

    def test_list_path_item_allowed_values_see_the_joined_element(self) -> None:
        definitions = [
            {
                "name": "Scenes",
                "type": "LIST[PATH]",
                "default": ["assets/a.blend"],
                "item": {"allowedValues": ["assets/a.blend", "assets/b.blend"]},
            }
        ]
        with pytest.raises(DecodeValidationError) as excinfo:
            _preprocess_posix(definitions)
        assert str(excinfo.value) == (
            "Parameter 'Scenes': item[0] value '/a/job1/assets/a.blend' is not in allowed values"
        )

    def test_path_max_length_sees_the_joined_value(self) -> None:
        with pytest.raises(DecodeValidationError) as excinfo:
            _preprocess_posix([{"name": "Short", "type": "PATH", "default": "a", "maxLength": 3}])
        assert str(excinfo.value) == "Parameter 'Short': value length 9 exceeds maximum 3"

    def test_environment_template_defaults_are_checked_too(self) -> None:
        with pytest.raises(DecodeValidationError) as excinfo:
            _preprocess_posix(
                [],
                environment_definitions=[
                    {
                        "name": "EnvScalar",
                        "type": "PATH",
                        "default": "cfg/a",
                        "allowedValues": ["cfg/a"],
                    },
                    {
                        "name": "EnvPaths",
                        "type": "LIST[PATH]",
                        "default": ["env/a"],
                        "item": {"allowedValues": ["env/a"]},
                    },
                ],
            )
        assert str(excinfo.value) == (
            "Parameter 'EnvScalar': value '/a/job1/cfg/a' is not in allowed values\n"
            "Parameter 'EnvPaths': item[0] value '/a/job1/env/a' is not in allowed values"
        )


@pytest.mark.skipif(
    sys.platform != "win32", reason="Windows path rules; the binding uses the host format."
)
class TestPathDefaultRulesWindows:
    """The Windows rows of openjd-rs#421: a drive-letter element is absolute, and a
    walk-up is detected across mixed separators."""

    @staticmethod
    def _preprocess(definitions: list[dict[str, Any]]) -> dict[str, Any]:
        template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["EXPR"],
                "name": "T",
                "parameterDefinitions": definitions,
                "steps": [{"name": "S", "script": {"actions": {"onRun": {"command": "echo"}}}}],
            },
            supported_extensions=["EXPR"],
        )
        return preprocess_job_parameters(
            job_template=template,
            job_parameter_values={},
            job_template_dir=Path("C:\\templates\\job1"),
            current_working_dir=Path("C:\\cwd"),
        )

    def test_a_drive_letter_element_is_absolute(self) -> None:
        with pytest.raises(DecodeValidationError) as excinfo:
            self._preprocess(_list_path(["renders\\a.exr", "D:\\renders\\b.exr"]))
        assert str(excinfo.value) == (
            f"The default value of LIST[PATH] parameter Paths at item[1] {_ABSOLUTE}"
        )

    def test_walk_up_across_mixed_separators_is_rejected(self) -> None:
        with pytest.raises(DecodeValidationError) as excinfo:
            self._preprocess(
                [
                    {"name": "A", "type": "PATH", "default": "a\\..\\..\\b"},
                    {"name": "B", "type": "PATH", "default": "a/..\\../b"},
                    {"name": "C", "type": "PATH", "default": "a\\../b"},
                ]
            )
        assert str(excinfo.value) == (
            f"The default value of PATH parameter A {_OUTSIDE}\n"
            f"The default value of PATH parameter B {_OUTSIDE}"
        )


class TestCreateJobLetFailureMessages:
    """openjd-model 0.10.1 (openjd-rs#410) evaluates a job environment's ``let`` under
    the caller's profile with the same diagnostic as a step script's ``let``. On
    0.10.0 the environment form read ``Error evaluating let binding 'q': ...`` and
    quoted the whole binding, ``q = 1 / int(Param.X)``.
    """

    _LET = ["q = 1 / int(Param.X)"]
    _EXPECTED = "script let binding 'q': Division by zero\n  1 / int(Param.X)\n  ~~^~~~~~~~~~~~~~"

    @classmethod
    def _decoded(cls, where: str) -> Any:
        on_run = {"actions": {"onRun": {"command": "echo"}}}
        template: dict[str, Any] = {
            "specificationVersion": "jobtemplate-2023-09",
            "extensions": ["EXPR"],
            "name": "T",
            "parameterDefinitions": [{"name": "X", "type": "STRING"}, {"name": "N", "type": "INT"}],
            "steps": [{"name": "S", "script": on_run}],
        }
        if where == "step":
            template["steps"][0]["script"] = {"let": cls._LET, **on_run}
        else:
            template["jobEnvironments"] = [
                {
                    "name": "E",
                    "script": {"let": cls._LET, "actions": {"onEnter": {"command": "echo"}}},
                }
            ]
        return decode_job_template(template=template, supported_extensions=["EXPR"])

    @pytest.mark.parametrize("where", ["step", "job environment"])
    def test_the_diagnostic_is_the_same_for_both(self, where: str) -> None:
        with pytest.raises(ExpressionError) as excinfo:
            create_job(job_template=self._decoded(where), job_parameter_values={"X": "0", "N": "1"})
        assert str(excinfo.value) == self._EXPECTED

    @pytest.mark.parametrize("where", ["step", "job environment"])
    def test_a_value_that_evaluates_creates_the_job(self, where: str) -> None:
        job = create_job(
            job_template=self._decoded(where), job_parameter_values={"X": "2", "N": "1"}
        )
        assert job.name == "T"


class TestCreateJobMissingExtensionsAreSorted:
    """openjd-model 0.10.1 (openjd-rs#410) lists the extensions a ``create_job``
    context is missing in sorted order, whatever order the template declares them in."""

    def test_two_missing_extensions_are_listed_sorted(self) -> None:
        decoded = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["FEATURE_BUNDLE_1", "EXPR"],
                "name": "T",
                "steps": [{"name": "S", "script": {"actions": {"onRun": {"command": "echo"}}}}],
            },
            supported_extensions=["EXPR", "FEATURE_BUNDLE_1"],
        )
        with pytest.raises(ModelValidationError) as excinfo:
            create_job(
                job_template=decoded,
                job_parameter_values={},
                validation_context=ValidationContext(ModelProfile(extensions=[])),
            )
        assert str(excinfo.value) == (
            "create_job requires a context enabling every extension the template declares: "
            "missing EXPR, FEATURE_BUNDLE_1. An application that does not support an extension "
            "should reject the template at decode via its supported-extensions list."
        )
