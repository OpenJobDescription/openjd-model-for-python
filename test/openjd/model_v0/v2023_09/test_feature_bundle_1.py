# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.


import pytest
from pydantic import TypeAdapter, ValidationError

from openjd.model import create_job, decode_job_template
from openjd.model._errors import DecodeValidationError
from openjd.model._format_strings import FormatString
from openjd.model._parse import _parse_model
from openjd.model._types import ParameterValue, ParameterValueType
from openjd.model.v2023_09 import (
    Action,
    ArgString,
    AmountRequirementTemplate,
    CancelationMethodNotifyThenTerminate,
    CommandString,
    DataString,
    EmbeddedFileText,
    Environment,
    ExtensionName,
    JobName,
    JobTemplate,
    EnvironmentTemplate,
    ModelParsingContext,
    SimpleAction,
    Step,
    StepTemplate,
)


# Helper to create context with FEATURE_BUNDLE_1 extension
def fb1_context() -> ModelParsingContext:
    return ModelParsingContext(supported_extensions=[ExtensionName.FEATURE_BUNDLE_1])


# Minimal valid data for reuse
STEP_SCRIPT = {"actions": {"onRun": {"command": "echo"}}}


class TestFeatureBundle1Extension:
    """Tests for FEATURE_BUNDLE_1 extension registration and support."""

    def test_extension_supported(self) -> None:
        """Test that FEATURE_BUNDLE_1 extension can be used in a job template."""
        data = {
            "specificationVersion": "jobtemplate-2023-09",
            "extensions": ["FEATURE_BUNDLE_1"],
            "name": "Test Job",
            "steps": [{"name": "step1", "script": STEP_SCRIPT}],
        }
        _parse_model(model=JobTemplate, obj=data, context=fb1_context())

    def test_extension_not_supported(self) -> None:
        """Test that using FEATURE_BUNDLE_1 fails when not supported."""
        data = {
            "specificationVersion": "jobtemplate-2023-09",
            "extensions": ["FEATURE_BUNDLE_1"],
            "name": "Test Job",
            "steps": [{"name": "step1", "script": STEP_SCRIPT}],
        }
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=JobTemplate, obj=data, context=ModelParsingContext())
        assert "FEATURE_BUNDLE_1" in str(excinfo.value)


class TestExtensionFieldEnablement:
    """Tests for extension enablement based on template's extensions field and supported_extensions."""

    @pytest.mark.parametrize(
        "template_declares_ext,supported_extensions,param_count,should_pass",
        [
            # Template declares extension, supported includes it - passes with 51 params
            (True, ["FEATURE_BUNDLE_1"], 51, True),
            # Template declares extension, supported excludes it - fails (unsupported ext)
            (True, ["TASK_CHUNKING"], 51, False),
            # Template declares extension, supported is None - fails (unsupported ext)
            (True, None, 51, False),
            # Template omits extension, supported includes it - fails (50 param limit)
            (False, ["FEATURE_BUNDLE_1"], 51, False),
            # Template omits extension, all supported - fails (50 param limit)
            (False, ["TASK_CHUNKING", "REDACTED_ENV_VARS", "FEATURE_BUNDLE_1"], 51, False),
            # Template omits extension, none supported - fails (50 param limit)
            (False, [], 51, False),
            # Template omits extension, supported is None - fails (50 param limit)
            (False, None, 51, False),
            # Template within default limit - passes regardless
            (False, ["FEATURE_BUNDLE_1"], 50, True),
            # Template omits extension, supported is None, within limit - passes
            (False, None, 50, True),
        ],
    )
    def test_extension_enablement(
        self,
        template_declares_ext: bool,
        supported_extensions: list[str],
        param_count: int,
        should_pass: bool,
    ) -> None:
        """Test that extension features require explicit declaration in template."""
        params = [{"name": f"P{i}", "type": "INT", "default": i} for i in range(param_count)]
        data: dict = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Test",
            "parameterDefinitions": params,
            "steps": [{"name": "s", "script": STEP_SCRIPT}],
        }
        if template_declares_ext:
            data["extensions"] = ["FEATURE_BUNDLE_1"]

        if should_pass:
            result = decode_job_template(template=data, supported_extensions=supported_extensions)
            assert result.parameterDefinitions is not None
            assert len(result.parameterDefinitions) == param_count
        else:
            with pytest.raises(Exception):
                decode_job_template(template=data, supported_extensions=supported_extensions)


class TestActionTimeoutFormatString:
    """Tests for timeout format string support in Action."""

    def test_timeout_format_string_with_extension(self) -> None:
        """Test that timeout can be a format string with FEATURE_BUNDLE_1."""
        data = {"command": "echo", "timeout": "{{Param.Timeout}}"}
        result = _parse_model(model=Action, obj=data, context=fb1_context())
        assert str(result.timeout) == "{{Param.Timeout}}"

    def test_timeout_format_string_without_extension_fails(self) -> None:
        """Test that timeout format string fails without extension."""
        data = {"command": "echo", "timeout": "{{Param.Timeout}}"}
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=Action, obj=data, context=ModelParsingContext())
        assert "FEATURE_BUNDLE_1" in str(excinfo.value)

    def test_timeout_int_string_without_extension(self) -> None:
        """Test that timeout as int string works without extension."""
        data = {"command": "echo", "timeout": "60"}
        result = _parse_model(model=Action, obj=data, context=ModelParsingContext())
        assert result.timeout == 60

    def test_timeout_int_with_extension(self) -> None:
        """Test that timeout as int still works with extension."""
        data = {"command": "echo", "timeout": 60}
        result = _parse_model(model=Action, obj=data, context=fb1_context())
        assert result.timeout == 60


class TestNotifyPeriodFormatString:
    """Tests for notifyPeriodInSeconds format string support."""

    def test_notify_period_format_string_with_extension(self) -> None:
        """Test that notifyPeriodInSeconds can be a format string with FEATURE_BUNDLE_1."""
        data = {"mode": "NOTIFY_THEN_TERMINATE", "notifyPeriodInSeconds": "{{Param.Period}}"}
        result = _parse_model(
            model=CancelationMethodNotifyThenTerminate, obj=data, context=fb1_context()
        )
        assert str(result.notifyPeriodInSeconds) == "{{Param.Period}}"

    def test_notify_period_format_string_without_extension_fails(self) -> None:
        """Test that notifyPeriodInSeconds format string fails without extension."""
        data = {"mode": "NOTIFY_THEN_TERMINATE", "notifyPeriodInSeconds": "{{Param.Period}}"}
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(
                model=CancelationMethodNotifyThenTerminate, obj=data, context=ModelParsingContext()
            )
        assert "FEATURE_BUNDLE_1" in str(excinfo.value)

    def test_notify_period_int_string_without_extension(self) -> None:
        """Test that notifyPeriodInSeconds as int string works without extension."""
        data = {"mode": "NOTIFY_THEN_TERMINATE", "notifyPeriodInSeconds": "120"}
        result = _parse_model(
            model=CancelationMethodNotifyThenTerminate, obj=data, context=ModelParsingContext()
        )
        assert result.notifyPeriodInSeconds == 120


class TestAmountRequirementFormatStrings:
    """Tests for min/max format string support in AmountRequirementTemplate."""

    def test_min_format_string_with_extension(self) -> None:
        """Test that min can be a format string with FEATURE_BUNDLE_1."""
        data = {"name": "amount.worker.vcpu", "min": "{{Param.CpuMin}}"}
        result = _parse_model(model=AmountRequirementTemplate, obj=data, context=fb1_context())
        assert str(result.min) == "{{Param.CpuMin}}"

    def test_max_format_string_with_extension(self) -> None:
        """Test that max can be a format string with FEATURE_BUNDLE_1."""
        data = {"name": "amount.worker.vcpu", "max": "{{Param.CpuMax}}"}
        result = _parse_model(model=AmountRequirementTemplate, obj=data, context=fb1_context())
        assert str(result.max) == "{{Param.CpuMax}}"

    def test_min_format_string_without_extension_fails(self) -> None:
        """Test that min format string fails without extension."""
        data = {"name": "amount.worker.vcpu", "min": "{{Param.CpuMin}}"}
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=AmountRequirementTemplate, obj=data, context=ModelParsingContext())
        assert "FEATURE_BUNDLE_1" in str(excinfo.value)

    def test_max_format_string_without_extension_fails(self) -> None:
        """Test that max format string fails without extension."""
        data = {"name": "amount.worker.vcpu", "max": "{{Param.CpuMax}}"}
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=AmountRequirementTemplate, obj=data, context=ModelParsingContext())
        assert "FEATURE_BUNDLE_1" in str(excinfo.value)

    def test_min_decimal_string_without_extension(self) -> None:
        """Test that min as decimal string works without extension."""
        data = {"name": "amount.worker.vcpu", "min": "2.5"}
        result = _parse_model(
            model=AmountRequirementTemplate, obj=data, context=ModelParsingContext()
        )
        assert result.min is not None
        assert float(result.min) == 2.5

    def test_min_max_both_format_strings(self) -> None:
        """Test that both min and max can be format strings."""
        data = {
            "name": "amount.worker.vcpu",
            "min": "{{Param.CpuMin}}",
            "max": "{{Param.CpuMax}}",
        }
        result = _parse_model(model=AmountRequirementTemplate, obj=data, context=fb1_context())
        assert str(result.min) == "{{Param.CpuMin}}"
        assert str(result.max) == "{{Param.CpuMax}}"


class TestEndOfLine:
    """Tests for endOfLine property in EmbeddedFileText."""

    @pytest.mark.parametrize("eol", ["AUTO", "LF", "CRLF"])
    def test_end_of_line_with_extension(self, eol: str) -> None:
        """Test that endOfLine can be set with FEATURE_BUNDLE_1."""
        data = {"name": "run", "type": "TEXT", "data": "echo hello", "endOfLine": eol}
        result = _parse_model(model=EmbeddedFileText, obj=data, context=fb1_context())
        assert result.endOfLine is not None
        assert result.endOfLine.value == eol

    def test_end_of_line_without_extension_fails(self) -> None:
        """Test that endOfLine fails without extension."""
        data = {"name": "run", "type": "TEXT", "data": "echo hello", "endOfLine": "LF"}
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=EmbeddedFileText, obj=data, context=ModelParsingContext())
        assert "FEATURE_BUNDLE_1" in str(excinfo.value)

    def test_end_of_line_invalid_value(self) -> None:
        """Test that invalid endOfLine value fails."""
        data = {"name": "run", "type": "TEXT", "data": "echo hello", "endOfLine": "INVALID"}
        with pytest.raises(ValidationError):
            _parse_model(model=EmbeddedFileText, obj=data, context=fb1_context())


class TestFilenameExtendedLength:
    """Tests for extended filename length with FEATURE_BUNDLE_1."""

    def test_filename_256_chars_with_extension(self) -> None:
        """Test that filename can be 256 chars with FEATURE_BUNDLE_1."""
        data = {"name": "run", "type": "TEXT", "data": "echo", "filename": "f" * 256}
        result = _parse_model(model=EmbeddedFileText, obj=data, context=fb1_context())
        assert result.filename is not None
        assert len(result.filename) == 256

    def test_filename_65_chars_without_extension_fails(self) -> None:
        """Test that filename > 64 chars fails without extension."""
        data = {"name": "run", "type": "TEXT", "data": "echo", "filename": "f" * 65}
        with pytest.raises(ValidationError):
            _parse_model(model=EmbeddedFileText, obj=data, context=ModelParsingContext())

    def test_filename_257_chars_with_extension_fails(self) -> None:
        """Test that filename > 256 chars fails even with extension."""
        data = {"name": "run", "type": "TEXT", "data": "echo", "filename": "f" * 257}
        with pytest.raises(ValidationError):
            _parse_model(model=EmbeddedFileText, obj=data, context=fb1_context())


class TestParameterDefinitionsCount:
    """Tests for extended parameterDefinitions count with FEATURE_BUNDLE_1."""

    def test_51_params_with_extension(self) -> None:
        """Test that 51 params works with FEATURE_BUNDLE_1."""
        params = [{"name": f"P{i}", "type": "INT", "default": i} for i in range(51)]
        data = {
            "specificationVersion": "jobtemplate-2023-09",
            "extensions": ["FEATURE_BUNDLE_1"],
            "name": "Test",
            "parameterDefinitions": params,
            "steps": [{"name": "s", "script": STEP_SCRIPT}],
        }
        result = _parse_model(model=JobTemplate, obj=data, context=fb1_context())
        assert result.parameterDefinitions is not None
        assert len(result.parameterDefinitions) == 51

    def test_51_params_without_extension_fails(self) -> None:
        """Test that 51 params fails without extension."""
        params = [{"name": f"P{i}", "type": "INT", "default": i} for i in range(51)]
        data = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Test",
            "parameterDefinitions": params,
            "steps": [{"name": "s", "script": STEP_SCRIPT}],
        }
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=JobTemplate, obj=data, context=ModelParsingContext())
        assert "50" in str(excinfo.value)

    def test_200_params_with_extension(self) -> None:
        """Test that 200 params works with FEATURE_BUNDLE_1."""
        params = [{"name": f"P{i}", "type": "INT", "default": i} for i in range(200)]
        data = {
            "specificationVersion": "jobtemplate-2023-09",
            "extensions": ["FEATURE_BUNDLE_1"],
            "name": "Test",
            "parameterDefinitions": params,
            "steps": [{"name": "s", "script": STEP_SCRIPT}],
        }
        result = _parse_model(model=JobTemplate, obj=data, context=fb1_context())
        assert result.parameterDefinitions is not None
        assert len(result.parameterDefinitions) == 200

    def test_201_params_with_extension_fails(self) -> None:
        """Test that 201 params fails even with extension."""
        params = [{"name": f"P{i}", "type": "INT", "default": i} for i in range(201)]
        data = {
            "specificationVersion": "jobtemplate-2023-09",
            "extensions": ["FEATURE_BUNDLE_1"],
            "name": "Test",
            "parameterDefinitions": params,
            "steps": [{"name": "s", "script": STEP_SCRIPT}],
        }
        with pytest.raises(ValidationError):
            _parse_model(model=JobTemplate, obj=data, context=fb1_context())

    def test_environment_template_51_params_without_extension_fails(self) -> None:
        """Test that EnvironmentTemplate with 51 params fails without extension."""
        params = [{"name": f"P{i}", "type": "INT", "default": i} for i in range(51)]
        data = {
            "specificationVersion": "environment-2023-09",
            "parameterDefinitions": params,
            "environment": {"name": "Env", "script": {"actions": {"onEnter": {"command": "echo"}}}},
        }
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=EnvironmentTemplate, obj=data, context=ModelParsingContext())
        assert "50" in str(excinfo.value)

    def test_environment_template_50_params_without_extension_succeeds(self) -> None:
        """Test that EnvironmentTemplate with 50 params succeeds without extension."""
        params = [{"name": f"P{i}", "type": "INT", "default": i} for i in range(50)]
        data = {
            "specificationVersion": "environment-2023-09",
            "parameterDefinitions": params,
            "environment": {"name": "Env", "script": {"actions": {"onEnter": {"command": "echo"}}}},
        }
        result = _parse_model(model=EnvironmentTemplate, obj=data, context=ModelParsingContext())
        assert result.parameterDefinitions is not None
        assert len(result.parameterDefinitions) == 50

    def test_environment_template_50_params_with_extension_succeeds(self) -> None:
        """Test that EnvironmentTemplate with 50 params succeeds with extension."""
        params = [{"name": f"P{i}", "type": "INT", "default": i} for i in range(50)]
        data = {
            "specificationVersion": "environment-2023-09",
            "extensions": ["FEATURE_BUNDLE_1"],
            "parameterDefinitions": params,
            "environment": {"name": "Env", "script": {"actions": {"onEnter": {"command": "echo"}}}},
        }
        result = _parse_model(model=EnvironmentTemplate, obj=data, context=fb1_context())
        assert result.parameterDefinitions is not None
        assert len(result.parameterDefinitions) == 50

    def test_environment_template_51_params_with_extension_fails(self) -> None:
        """Test that EnvironmentTemplate with 51 params fails even with extension."""
        params = [{"name": f"P{i}", "type": "INT", "default": i} for i in range(51)]
        data = {
            "specificationVersion": "environment-2023-09",
            "extensions": ["FEATURE_BUNDLE_1"],
            "parameterDefinitions": params,
            "environment": {"name": "Env", "script": {"actions": {"onEnter": {"command": "echo"}}}},
        }
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=EnvironmentTemplate, obj=data, context=fb1_context())
        assert "50" in str(excinfo.value)


class TestSimpleAction:
    """Tests for SimpleAction model."""

    def test_simple_action_parse(self) -> None:
        """Test that SimpleAction parses correctly."""
        data = {"script": "print('hello')"}
        result = _parse_model(model=SimpleAction, obj=data, context=fb1_context())
        assert "print" in str(result.script)

    def test_simple_action_with_args(self) -> None:
        """Test SimpleAction with args."""
        data = {"script": "print('hello')", "args": ["--verbose"]}
        result = _parse_model(model=SimpleAction, obj=data, context=fb1_context())
        assert result.args is not None
        assert result.args[0] == "--verbose"

    def test_simple_action_with_timeout(self) -> None:
        """Test SimpleAction with timeout."""
        data = {"script": "print('hello')", "timeout": 60}
        result = _parse_model(model=SimpleAction, obj=data, context=fb1_context())
        assert result.timeout == 60

    def test_simple_action_with_timeout_format_string(self) -> None:
        """Test SimpleAction with timeout as format string."""
        data = {"script": "print('hello')", "timeout": "{{Param.Timeout}}"}
        result = _parse_model(model=SimpleAction, obj=data, context=fb1_context())
        assert str(result.timeout) == "{{Param.Timeout}}"

    def test_simple_action_with_cancelation(self) -> None:
        """Test SimpleAction with cancelation."""
        data = {
            "script": "print('hello')",
            "cancelation": {"mode": "NOTIFY_THEN_TERMINATE", "notifyPeriodInSeconds": 30},
        }
        result = _parse_model(model=SimpleAction, obj=data, context=fb1_context())
        assert result.cancelation is not None
        assert isinstance(result.cancelation, CancelationMethodNotifyThenTerminate)
        assert result.cancelation.notifyPeriodInSeconds == 30


class TestSimpleActionFieldScopes:
    """Parity with Action: a SimpleAction's timeout/cancelation validate at
    TEMPLATE scope (no Task.*/Session.* symbols), exactly like the script-form
    Action the sugar desugars to. Regression: they used to validate at the
    ambient TASK scope, accepting references the desugared form rejects."""

    @staticmethod
    def _template_with_bash_step(bash: dict) -> dict:
        return {
            "specificationVersion": "jobtemplate-2023-09",
            "extensions": ["FEATURE_BUNDLE_1"],
            "name": "Test",
            "parameterDefinitions": [{"name": "TO", "type": "INT", "default": 30}],
            "steps": [
                {
                    "name": "Step1",
                    "parameterSpace": {
                        "taskParameterDefinitions": [
                            {"name": "Frame", "type": "INT", "range": "1-3"}
                        ]
                    },
                    "bash": bash,
                }
            ],
        }

    def test_timeout_task_param_rejected(self) -> None:
        """A task-parameter reference in a SimpleAction timeout is rejected,
        matching the script-form equivalent."""
        template = self._template_with_bash_step(
            {"script": "echo hi", "timeout": "{{Task.Param.Frame}}"}
        )
        with pytest.raises(DecodeValidationError, match=r"Task\.Param\.Frame does not exist"):
            decode_job_template(template=template, supported_extensions=["FEATURE_BUNDLE_1"])

    def test_timeout_job_param_accepted(self) -> None:
        """A job-parameter reference (template scope) is still accepted."""
        template = self._template_with_bash_step({"script": "echo hi", "timeout": "{{Param.TO}}"})
        decode_job_template(template=template, supported_extensions=["FEATURE_BUNDLE_1"])

    def test_cancelation_notify_period_task_param_rejected(self) -> None:
        """cancelation validates at template scope too."""
        template = self._template_with_bash_step(
            {
                "script": "echo hi",
                "cancelation": {
                    "mode": "NOTIFY_THEN_TERMINATE",
                    "notifyPeriodInSeconds": "{{Task.Param.Frame}}",
                },
            }
        )
        with pytest.raises(DecodeValidationError, match=r"Task\.Param\.Frame does not exist"):
            decode_job_template(template=template, supported_extensions=["FEATURE_BUNDLE_1"])

    def test_cancelation_notify_period_job_param_accepted(self) -> None:
        template = self._template_with_bash_step(
            {
                "script": "echo hi",
                "cancelation": {
                    "mode": "NOTIFY_THEN_TERMINATE",
                    "notifyPeriodInSeconds": "{{Param.TO}}",
                },
            }
        )
        decode_job_template(template=template, supported_extensions=["FEATURE_BUNDLE_1"])

    def test_script_task_param_still_accepted(self) -> None:
        """The SimpleAction's script/args remain TASK-scoped."""
        template = self._template_with_bash_step(
            {"script": "echo {{Task.Param.Frame}}", "args": ["{{Task.Param.Frame}}"]}
        )
        decode_job_template(template=template, supported_extensions=["FEATURE_BUNDLE_1"])


class TestScriptInterpreterSyntaxSugar:
    """Tests for script interpreter syntax sugar in StepTemplate."""

    @pytest.mark.parametrize("interpreter", ["python", "bash", "cmd", "powershell", "node"])
    def test_interpreter_with_extension(self, interpreter: str) -> None:
        """Test that interpreter syntax sugar works with FEATURE_BUNDLE_1."""
        data = {"name": "Step1", interpreter: {"script": "echo hello"}}
        result = _parse_model(model=StepTemplate, obj=data, context=fb1_context())
        assert getattr(result, interpreter) is not None
        assert result.script is None

    def test_python_interpreter_without_extension_fails(self) -> None:
        """Test that python interpreter fails without extension."""
        data = {"name": "Step1", "python": {"script": "print('hello')"}}
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=StepTemplate, obj=data, context=ModelParsingContext())
        assert "FEATURE_BUNDLE_1" in str(excinfo.value)

    def test_script_and_interpreter_fails(self) -> None:
        """Test that specifying both script and interpreter fails."""
        data = {"name": "Step1", "script": STEP_SCRIPT, "python": {"script": "print('hello')"}}
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=StepTemplate, obj=data, context=fb1_context())
        assert "Cannot specify both" in str(excinfo.value)

    def test_multiple_interpreters_fails(self) -> None:
        """Test that specifying multiple interpreters fails."""
        data = {
            "name": "Step1",
            "python": {"script": "print('hello')"},
            "bash": {"script": "echo hello"},
        }
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=StepTemplate, obj=data, context=fb1_context())
        assert "multiple" in str(excinfo.value).lower()

    def test_no_script_or_interpreter_fails(self) -> None:
        """Test that missing both script and interpreter fails."""
        data = {"name": "Step1"}
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=StepTemplate, obj=data, context=fb1_context())
        assert "Must specify" in str(excinfo.value)

    def test_interpreter_with_timeout(self) -> None:
        """Test interpreter with timeout."""
        data = {"name": "Step1", "python": {"script": "print('hello')", "timeout": 60}}
        result = _parse_model(model=StepTemplate, obj=data, context=fb1_context())
        assert result.python is not None
        assert result.python.timeout == 60

    def test_interpreter_with_args(self) -> None:
        """Test interpreter with args."""
        data = {"name": "Step1", "python": {"script": "print('hello')", "args": ["-v"]}}
        result = _parse_model(model=StepTemplate, obj=data, context=fb1_context())
        assert result.python is not None
        assert result.python.args is not None
        assert result.python.args[0] == "-v"


class TestJobTemplateWithFeatureBundle1:
    """Integration tests for JobTemplate with FEATURE_BUNDLE_1 features."""

    def test_full_template_with_all_features(self) -> None:
        """Test a job template using multiple FEATURE_BUNDLE_1 features."""
        data = {
            "specificationVersion": "jobtemplate-2023-09",
            "extensions": ["FEATURE_BUNDLE_1"],
            "name": "Test Job",
            "parameterDefinitions": [
                {"name": "Timeout", "type": "INT", "default": 60},
                {"name": "CpuMin", "type": "INT", "default": 2},
            ],
            "steps": [
                {
                    "name": "Step1",
                    "python": {"script": "print('hello')", "timeout": "{{Param.Timeout}}"},
                    "hostRequirements": {
                        "amounts": [{"name": "amount.worker.vcpu", "min": "{{Param.CpuMin}}"}]
                    },
                }
            ],
        }
        result = _parse_model(model=JobTemplate, obj=data, context=fb1_context())
        assert result.steps[0].python is not None
        assert str(result.steps[0].python.timeout) == "{{Param.Timeout}}"

    def test_template_with_embedded_file_eol(self) -> None:
        """Test job template with embedded file endOfLine."""
        data = {
            "specificationVersion": "jobtemplate-2023-09",
            "extensions": ["FEATURE_BUNDLE_1"],
            "name": "Test Job",
            "steps": [
                {
                    "name": "Step1",
                    "script": {
                        "actions": {"onRun": {"command": "bash", "args": ["{{Task.File.run}}"]}},
                        "embeddedFiles": [
                            {
                                "name": "run",
                                "type": "TEXT",
                                "data": "echo hello",
                                "endOfLine": "LF",
                            }
                        ],
                    },
                }
            ],
        }
        result = _parse_model(model=JobTemplate, obj=data, context=fb1_context())
        assert result.steps[0].script is not None
        assert result.steps[0].script.embeddedFiles is not None
        assert result.steps[0].script.embeddedFiles[0].endOfLine is not None
        assert result.steps[0].script.embeddedFiles[0].endOfLine.value == "LF"


class TestCreateJobWithFormatStrings:
    """Tests for create_job with FEATURE_BUNDLE_1 format string resolution."""

    def test_amount_requirement_min_max_resolved_valid(self) -> None:
        """Test that resolved min/max values are validated correctly."""

        template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["FEATURE_BUNDLE_1"],
                "name": "Test",
                "parameterDefinitions": [
                    {"name": "CpuMin", "type": "INT", "default": 2},
                    {"name": "CpuMax", "type": "INT", "default": 8},
                ],
                "steps": [
                    {
                        "name": "Step1",
                        "script": STEP_SCRIPT,
                        "hostRequirements": {
                            "amounts": [
                                {
                                    "name": "amount.worker.vcpu",
                                    "min": "{{Param.CpuMin}}",
                                    "max": "{{Param.CpuMax}}",
                                }
                            ]
                        },
                    }
                ],
            },
            supported_extensions=[ExtensionName.FEATURE_BUNDLE_1],
        )
        job = create_job(
            job_template=template,
            job_parameter_values={
                "CpuMin": ParameterValue(type=ParameterValueType.INT, value="2"),
                "CpuMax": ParameterValue(type=ParameterValueType.INT, value="8"),
            },
        )
        assert job.steps[0].hostRequirements is not None
        assert job.steps[0].hostRequirements.amounts is not None
        assert job.steps[0].hostRequirements.amounts[0].min == 2
        assert job.steps[0].hostRequirements.amounts[0].max == 8

    def test_amount_requirement_min_greater_than_max_resolved_fails(self) -> None:
        """Test that resolved min > max fails validation."""

        template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["FEATURE_BUNDLE_1"],
                "name": "Test",
                "parameterDefinitions": [
                    {"name": "CpuMin", "type": "INT", "default": 2},
                    {"name": "CpuMax", "type": "INT", "default": 8},
                ],
                "steps": [
                    {
                        "name": "Step1",
                        "script": STEP_SCRIPT,
                        "hostRequirements": {
                            "amounts": [
                                {
                                    "name": "amount.worker.vcpu",
                                    "min": "{{Param.CpuMin}}",
                                    "max": "{{Param.CpuMax}}",
                                }
                            ]
                        },
                    }
                ],
            },
            supported_extensions=[ExtensionName.FEATURE_BUNDLE_1],
        )
        with pytest.raises(DecodeValidationError) as excinfo:
            create_job(
                job_template=template,
                job_parameter_values={
                    "CpuMin": ParameterValue(type=ParameterValueType.INT, value="10"),
                    "CpuMax": ParameterValue(type=ParameterValueType.INT, value="5"),
                },
            )
        assert "max" in str(excinfo.value).lower()

    def test_timeout_and_notify_period_carried_through_unresolved(self) -> None:
        """timeout and notifyPeriodInSeconds format strings are NOT resolved
        at job creation: they are carried through the instantiated Job as raw
        FormatStrings and resolved at run time by the session, matching
        openjd-rs (job/create_job/instantiate.rs clones timeout+cancelation
        unresolved into the Job). This is what allows RFC 0008 wrap hooks to
        forward run-time-only symbols such as WrappedAction.Timeout."""

        template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["FEATURE_BUNDLE_1"],
                "name": "Test",
                "parameterDefinitions": [{"name": "TO", "type": "INT", "default": 30}],
                "steps": [
                    {
                        "name": "Step1",
                        "script": {
                            "actions": {
                                "onRun": {
                                    "command": "echo",
                                    "timeout": "{{Param.TO}}",
                                    "cancelation": {
                                        "mode": "NOTIFY_THEN_TERMINATE",
                                        "notifyPeriodInSeconds": "{{Param.TO}}",
                                    },
                                }
                            }
                        },
                    }
                ],
            },
            supported_extensions=[ExtensionName.FEATURE_BUNDLE_1],
        )

        # WHEN
        job = create_job(
            job_template=template,
            job_parameter_values={"TO": ParameterValue(type=ParameterValueType.INT, value="30")},
        )

        # THEN: creation succeeds and both fields carry the raw FormatString.
        on_run = job.steps[0].script.actions.onRun
        assert isinstance(on_run.timeout, FormatString)
        assert str(on_run.timeout) == "{{Param.TO}}"
        assert on_run.cancelation is not None
        assert isinstance(on_run.cancelation.notifyPeriodInSeconds, FormatString)
        assert str(on_run.cancelation.notifyPeriodInSeconds) == "{{Param.TO}}"

    def test_literal_timeout_and_notify_period_stay_ints_through_create_job(self) -> None:
        """Literal integer timeout/notifyPeriodInSeconds are unaffected by
        the run-time deferral of format-string values."""

        template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["FEATURE_BUNDLE_1"],
                "name": "Test",
                "steps": [
                    {
                        "name": "Step1",
                        "script": {
                            "actions": {
                                "onRun": {
                                    "command": "echo",
                                    "timeout": 30,
                                    "cancelation": {
                                        "mode": "NOTIFY_THEN_TERMINATE",
                                        "notifyPeriodInSeconds": 15,
                                    },
                                }
                            }
                        },
                    }
                ],
            },
            supported_extensions=[ExtensionName.FEATURE_BUNDLE_1],
        )
        job = create_job(job_template=template, job_parameter_values={})
        on_run = job.steps[0].script.actions.onRun
        assert on_run.timeout == 30
        assert on_run.cancelation is not None
        assert on_run.cancelation.notifyPeriodInSeconds == 15


class TestAmountRequirementEdgeCases:
    """Edge case tests for AmountRequirementTemplate."""

    def test_min_negative_fails(self) -> None:
        """Test that negative min value fails."""
        data = {"name": "amount.worker.vcpu", "min": -1}
        with pytest.raises(ValidationError):
            _parse_model(model=AmountRequirementTemplate, obj=data, context=fb1_context())

    def test_max_zero_fails(self) -> None:
        """Test that zero max value fails."""
        data = {"name": "amount.worker.vcpu", "max": 0}
        with pytest.raises(ValidationError):
            _parse_model(model=AmountRequirementTemplate, obj=data, context=fb1_context())

    def test_min_greater_than_max_fails(self) -> None:
        """Test that min > max fails when both are concrete values."""
        data = {"name": "amount.worker.vcpu", "min": 10, "max": 5}
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=AmountRequirementTemplate, obj=data, context=fb1_context())
        assert "max" in str(excinfo.value).lower()

    def test_min_zero_succeeds(self) -> None:
        """Test that min=0 succeeds."""
        data = {"name": "amount.worker.vcpu", "min": 0, "max": 1}
        result = _parse_model(model=AmountRequirementTemplate, obj=data, context=fb1_context())
        assert result.min is not None
        assert float(result.min) == 0

    def test_min_max_equal_succeeds(self) -> None:
        """Test that min=max succeeds."""
        data = {"name": "amount.worker.vcpu", "min": 5, "max": 5}
        result = _parse_model(model=AmountRequirementTemplate, obj=data, context=fb1_context())
        assert result.min is not None
        assert result.max is not None
        assert float(result.min) == float(result.max)


class TestActionTimeoutEdgeCases:
    """Edge case tests for Action timeout."""

    def test_timeout_zero_fails(self) -> None:
        """Test that timeout=0 fails."""
        data = {"command": "echo", "timeout": 0}
        with pytest.raises(ValidationError):
            _parse_model(model=Action, obj=data, context=fb1_context())

    def test_timeout_negative_fails(self) -> None:
        """Test that negative timeout fails."""
        data = {"command": "echo", "timeout": -1}
        with pytest.raises(ValidationError):
            _parse_model(model=Action, obj=data, context=fb1_context())

    def test_timeout_float_string_fails(self) -> None:
        """Test that float string timeout fails."""
        data = {"command": "echo", "timeout": "1.5"}
        with pytest.raises(ValidationError):
            _parse_model(model=Action, obj=data, context=fb1_context())


class TestNotifyPeriodEdgeCases:
    """Edge case tests for notifyPeriodInSeconds."""

    def test_notify_period_zero_fails(self) -> None:
        """Test that notifyPeriodInSeconds=0 fails."""
        data = {"mode": "NOTIFY_THEN_TERMINATE", "notifyPeriodInSeconds": 0}
        with pytest.raises(ValidationError):
            _parse_model(
                model=CancelationMethodNotifyThenTerminate, obj=data, context=fb1_context()
            )

    def test_notify_period_over_600_fails(self) -> None:
        """Test that notifyPeriodInSeconds > 600 fails."""
        data = {"mode": "NOTIFY_THEN_TERMINATE", "notifyPeriodInSeconds": 601}
        with pytest.raises(ValidationError):
            _parse_model(
                model=CancelationMethodNotifyThenTerminate, obj=data, context=fb1_context()
            )

    def test_notify_period_600_succeeds(self) -> None:
        """Test that notifyPeriodInSeconds=600 succeeds."""
        data = {"mode": "NOTIFY_THEN_TERMINATE", "notifyPeriodInSeconds": 600}
        result = _parse_model(
            model=CancelationMethodNotifyThenTerminate, obj=data, context=fb1_context()
        )
        assert result.notifyPeriodInSeconds == 600


class TestJobNameLength:
    """Tests for JobName length validation (128 base, 512 with extension)."""

    def test_job_name_129_chars_without_extension_fails(self) -> None:
        """Test that job name > 128 chars fails without extension."""
        data = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "J" * 129,
            "steps": [{"name": "s", "script": STEP_SCRIPT}],
        }
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=JobTemplate, obj=data, context=ModelParsingContext())
        assert "128" in str(excinfo.value)

    def test_job_name_128_chars_without_extension_succeeds(self) -> None:
        """Test that job name = 128 chars works without extension."""
        data = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "J" * 128,
            "steps": [{"name": "s", "script": STEP_SCRIPT}],
        }
        result = _parse_model(model=JobTemplate, obj=data, context=ModelParsingContext())
        assert len(result.name) == 128

    def test_job_name_512_chars_with_extension_succeeds(self) -> None:
        """Test that job name = 512 chars works with extension."""
        data = {
            "specificationVersion": "jobtemplate-2023-09",
            "extensions": ["FEATURE_BUNDLE_1"],
            "name": "J" * 512,
            "steps": [{"name": "s", "script": STEP_SCRIPT}],
        }
        result = _parse_model(model=JobTemplate, obj=data, context=fb1_context())
        assert len(result.name) == 512

    def test_job_name_513_chars_with_extension_fails(self) -> None:
        """Test that job name > 512 chars fails even with extension."""
        data = {
            "specificationVersion": "jobtemplate-2023-09",
            "extensions": ["FEATURE_BUNDLE_1"],
            "name": "J" * 513,
            "steps": [{"name": "s", "script": STEP_SCRIPT}],
        }
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=JobTemplate, obj=data, context=fb1_context())
        assert "512" in str(excinfo.value)

    def test_job_name_format_string_longer_than_limit_succeeds(self) -> None:
        """Test that format string longer than limit passes if resolved value is shorter."""

        # Template name with format string is > 128 chars, but resolved is short
        long_prefix = "J" * 120
        template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": f"{long_prefix}_{{{{Param.Name}}}}",  # 135 chars unresolved
                "parameterDefinitions": [{"name": "Name", "type": "STRING", "default": "X"}],
                "steps": [{"name": "s", "script": STEP_SCRIPT}],
            },
        )
        # Resolved name will be 120 + 1 + 4 = 125 chars, under 128
        job = create_job(
            job_template=template,
            job_parameter_values={
                "Name": ParameterValue(type=ParameterValueType.STRING, value="Test"),
            },
        )
        assert job.name == f"{long_prefix}_Test"
        assert len(job.name) == 125


class TestStepNameLength:
    """Tests for StepName length validation (64 base, 512 with extension)."""

    def test_step_name_65_chars_without_extension_fails(self) -> None:
        """Test that step name > 64 chars fails without extension."""
        data = {"name": "S" * 65, "script": STEP_SCRIPT}
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=StepTemplate, obj=data, context=ModelParsingContext())
        assert "64" in str(excinfo.value)

    def test_step_name_64_chars_without_extension_succeeds(self) -> None:
        """Test that step name = 64 chars works without extension."""
        data = {"name": "S" * 64, "script": STEP_SCRIPT}
        result = _parse_model(model=StepTemplate, obj=data, context=ModelParsingContext())
        assert len(result.name) == 64

    def test_step_name_512_chars_with_extension_succeeds(self) -> None:
        """Test that step name = 512 chars works with extension."""
        data = {"name": "S" * 512, "script": STEP_SCRIPT}
        result = _parse_model(model=StepTemplate, obj=data, context=fb1_context())
        assert len(result.name) == 512

    def test_step_name_513_chars_with_extension_fails(self) -> None:
        """Test that step name > 512 chars fails even with extension."""
        data = {"name": "S" * 513, "script": STEP_SCRIPT}
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=StepTemplate, obj=data, context=fb1_context())
        assert "512" in str(excinfo.value)


class TestEnvironmentNameLength:
    """Tests for EnvironmentName length validation (64 base, 512 with extension)."""

    def test_env_name_65_chars_without_extension_fails(self) -> None:
        """Test that environment name > 64 chars fails without extension."""
        from openjd.model.v2023_09 import Environment

        data = {"name": "E" * 65, "variables": {"FOO": "bar"}}
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=Environment, obj=data, context=ModelParsingContext())
        assert "64" in str(excinfo.value)

    def test_env_name_64_chars_without_extension_succeeds(self) -> None:
        """Test that environment name = 64 chars works without extension."""
        from openjd.model.v2023_09 import Environment

        data = {"name": "E" * 64, "variables": {"FOO": "bar"}}
        result = _parse_model(model=Environment, obj=data, context=ModelParsingContext())
        assert len(result.name) == 64

    def test_env_name_512_chars_with_extension_succeeds(self) -> None:
        """Test that environment name = 512 chars works with extension."""
        from openjd.model.v2023_09 import Environment

        data = {"name": "E" * 512, "variables": {"FOO": "bar"}}
        result = _parse_model(model=Environment, obj=data, context=fb1_context())
        assert len(result.name) == 512

    def test_env_name_513_chars_with_extension_fails(self) -> None:
        """Test that environment name > 512 chars fails even with extension."""
        from openjd.model.v2023_09 import Environment

        data = {"name": "E" * 513, "variables": {"FOO": "bar"}}
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=Environment, obj=data, context=fb1_context())
        assert "512" in str(excinfo.value)


class TestIdentifierLength:
    """Tests for Identifier length validation in EmbeddedFileText.name (64 base, 512 with extension)."""

    def test_identifier_65_chars_without_extension_fails(self) -> None:
        """Test that identifier > 64 chars fails without extension."""
        data = {"name": "I" * 65, "type": "TEXT", "data": "echo"}
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=EmbeddedFileText, obj=data, context=ModelParsingContext())
        assert "64" in str(excinfo.value)

    def test_identifier_64_chars_without_extension_succeeds(self) -> None:
        """Test that identifier = 64 chars works without extension."""
        data = {"name": "I" * 64, "type": "TEXT", "data": "echo"}
        result = _parse_model(model=EmbeddedFileText, obj=data, context=ModelParsingContext())
        assert len(result.name) == 64

    def test_identifier_512_chars_with_extension_succeeds(self) -> None:
        """Test that identifier = 512 chars works with extension."""
        data = {"name": "I" * 512, "type": "TEXT", "data": "echo"}
        result = _parse_model(model=EmbeddedFileText, obj=data, context=fb1_context())
        assert len(result.name) == 512

    def test_identifier_513_chars_with_extension_fails(self) -> None:
        """Test that identifier > 512 chars fails even with extension."""
        data = {"name": "I" * 513, "type": "TEXT", "data": "echo"}
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=EmbeddedFileText, obj=data, context=fb1_context())
        assert "512" in str(excinfo.value)


class TestResolveSyntaxSugar:
    """Tests for StepTemplate.resolve_syntax_sugar() method."""

    def test_returns_self_when_using_script(self) -> None:
        """Test that resolve_syntax_sugar returns self when already using script."""
        data = {"name": "Step1", "script": STEP_SCRIPT}
        template = _parse_model(model=StepTemplate, obj=data, context=ModelParsingContext())
        result = template.resolve_syntax_sugar()
        assert result is template

    def test_python_desugaring(self) -> None:
        """Test Python interpreter de-sugaring."""
        data = {"name": "Step1", "python": {"script": "print('hello')"}}
        template = _parse_model(model=StepTemplate, obj=data, context=fb1_context())
        result = template.resolve_syntax_sugar()

        assert result is not template
        assert result.script is not None
        assert result.python is None
        assert result.script.actions.onRun.command == "python"
        assert result.script.embeddedFiles is not None
        assert len(result.script.embeddedFiles) == 1
        # Filename should be based on step name with .py extension
        assert result.script.embeddedFiles[0].filename is not None
        assert result.script.embeddedFiles[0].filename.startswith("Step1_")
        assert result.script.embeddedFiles[0].filename.endswith(".py")
        assert "print" in str(result.script.embeddedFiles[0].data)
        # Args should contain file reference
        assert result.script.actions.onRun.args is not None
        assert any("Task.File." in arg for arg in result.script.actions.onRun.args)

    def test_bash_desugaring(self) -> None:
        """Test Bash interpreter de-sugaring."""
        data = {"name": "Step1", "bash": {"script": "echo hello"}}
        template = _parse_model(model=StepTemplate, obj=data, context=fb1_context())
        result = template.resolve_syntax_sugar()

        assert result.script is not None
        assert result.script.actions.onRun.command == "bash"
        assert result.script.embeddedFiles is not None
        assert result.script.embeddedFiles[0].filename is not None
        assert result.script.embeddedFiles[0].filename.endswith(".sh")

    def test_cmd_desugaring_has_c_flag(self) -> None:
        """Test cmd interpreter de-sugaring includes /C flag."""
        data = {"name": "Step1", "cmd": {"script": "echo hello"}}
        template = _parse_model(model=StepTemplate, obj=data, context=fb1_context())
        result = template.resolve_syntax_sugar()

        assert result.script is not None
        assert result.script.actions.onRun.command == "cmd"
        assert result.script.actions.onRun.args is not None
        assert result.script.actions.onRun.args[0] == "/C"
        assert result.script.embeddedFiles is not None
        assert result.script.embeddedFiles[0].filename is not None
        assert result.script.embeddedFiles[0].filename.endswith(".bat")

    def test_powershell_desugaring_has_file_flag(self) -> None:
        """Test PowerShell interpreter de-sugaring includes -File flag."""
        data = {"name": "Step1", "powershell": {"script": "Write-Host 'hello'"}}
        template = _parse_model(model=StepTemplate, obj=data, context=fb1_context())
        result = template.resolve_syntax_sugar()

        assert result.script is not None
        assert result.script.actions.onRun.command == "powershell"
        assert result.script.actions.onRun.args is not None
        assert result.script.actions.onRun.args[0] == "-File"
        assert result.script.embeddedFiles is not None
        assert result.script.embeddedFiles[0].filename is not None
        assert result.script.embeddedFiles[0].filename.endswith(".ps1")

    def test_node_desugaring(self) -> None:
        """Test Node.js interpreter de-sugaring."""
        data = {"name": "Step1", "node": {"script": "console.log('hello')"}}
        template = _parse_model(model=StepTemplate, obj=data, context=fb1_context())
        result = template.resolve_syntax_sugar()

        assert result.script is not None
        assert result.script.actions.onRun.command == "node"
        assert result.script.embeddedFiles is not None
        assert result.script.embeddedFiles[0].filename is not None
        assert result.script.embeddedFiles[0].filename.endswith(".js")

    def test_preserves_user_args(self) -> None:
        """Test that user-provided args are preserved after file reference."""
        data = {"name": "Step1", "python": {"script": "print('hello')", "args": ["-v", "--debug"]}}
        template = _parse_model(model=StepTemplate, obj=data, context=fb1_context())
        result = template.resolve_syntax_sugar()

        assert result.script is not None
        args = result.script.actions.onRun.args
        assert args is not None
        # Find the file reference arg
        file_ref_idx = next(i for i, arg in enumerate(args) if "Task.File." in arg)
        assert "-v" in args
        assert "--debug" in args
        # File ref should come before user args
        assert args.index(ArgString("-v")) > file_ref_idx

    def test_special_characters_in_step_name(self) -> None:
        """Test that special characters in step name are replaced with underscores."""
        data = {"name": "My Step-Name.v2", "python": {"script": "print('hello')"}}
        template = _parse_model(model=StepTemplate, obj=data, context=fb1_context())
        result = template.resolve_syntax_sugar()

        assert result.script is not None
        assert result.script.embeddedFiles is not None
        filename = result.script.embeddedFiles[0].filename
        assert filename is not None
        # Should start with sanitized step name
        assert filename.startswith("My_Step_Name_v2_")
        assert filename.endswith(".py")

    def test_long_step_name_truncated(self) -> None:
        """Test that long step names are truncated to fit filename limit."""
        long_name = "A" * 512  # Max step name with FEATURE_BUNDLE_1
        data = {"name": long_name, "python": {"script": "print('hello')"}}
        template = _parse_model(model=StepTemplate, obj=data, context=fb1_context())
        result = template.resolve_syntax_sugar()

        assert result.script is not None
        assert result.script.embeddedFiles is not None
        filename = result.script.embeddedFiles[0].filename
        assert filename is not None
        # Filename must be <= 256 chars
        assert len(filename) <= 256
        assert filename.endswith(".py")

    def test_unique_names_per_call(self) -> None:
        """Test that each call generates a unique embedded file name."""
        data = {"name": "Step1", "python": {"script": "print('hello')"}}
        template = _parse_model(model=StepTemplate, obj=data, context=fb1_context())

        result1 = template.resolve_syntax_sugar()
        result2 = template.resolve_syntax_sugar()

        assert result1.script is not None
        assert result2.script is not None
        name1 = result1.script.embeddedFiles[0].name  # type: ignore
        name2 = result2.script.embeddedFiles[0].name  # type: ignore
        # Names should be different due to random suffix
        assert name1 != name2

    def test_preserves_timeout(self) -> None:
        """Test that timeout is preserved."""
        data = {"name": "Step1", "python": {"script": "print('hello')", "timeout": 60}}
        template = _parse_model(model=StepTemplate, obj=data, context=fb1_context())
        result = template.resolve_syntax_sugar()

        assert result.script is not None
        assert result.script.actions.onRun.timeout == 60

    def test_preserves_timeout_format_string(self) -> None:
        """Test that timeout format string is preserved."""
        data = {"name": "Step1", "python": {"script": "print('hello')", "timeout": "{{Param.T}}"}}
        template = _parse_model(model=StepTemplate, obj=data, context=fb1_context())
        result = template.resolve_syntax_sugar()

        assert result.script is not None
        assert str(result.script.actions.onRun.timeout) == "{{Param.T}}"

    def test_preserves_cancelation(self) -> None:
        """Test that cancelation settings are preserved."""
        data = {
            "name": "Step1",
            "python": {
                "script": "print('hello')",
                "cancelation": {"mode": "NOTIFY_THEN_TERMINATE", "notifyPeriodInSeconds": 30},
            },
        }
        template = _parse_model(model=StepTemplate, obj=data, context=fb1_context())
        result = template.resolve_syntax_sugar()

        assert result.script is not None
        assert result.script.actions.onRun.cancelation is not None
        assert isinstance(
            result.script.actions.onRun.cancelation, CancelationMethodNotifyThenTerminate
        )
        assert result.script.actions.onRun.cancelation.notifyPeriodInSeconds == 30

    def test_preserves_step_metadata(self) -> None:
        """Test that step metadata (name, description, etc.) is preserved."""

        data = {
            "name": "MyStep",
            "description": "A test step",
            "python": {"script": "print('hello')"},
            "stepEnvironments": [{"name": "Env1", "variables": {"FOO": "bar"}}],
        }
        template = _parse_model(model=StepTemplate, obj=data, context=fb1_context())
        result = template.resolve_syntax_sugar()

        assert result.name == "MyStep"
        assert result.description == "A test step"
        assert result.stepEnvironments is not None
        assert len(result.stepEnvironments) == 1
        assert result.stepEnvironments[0].name == "Env1"

    def test_embedded_file_is_runnable(self) -> None:
        """Test that the generated embedded file is marked as runnable."""
        data = {"name": "Step1", "python": {"script": "print('hello')"}}
        template = _parse_model(model=StepTemplate, obj=data, context=fb1_context())
        result = template.resolve_syntax_sugar()

        assert result.script is not None
        assert result.script.embeddedFiles is not None
        assert result.script.embeddedFiles[0].runnable is True


class TestStepResolveSyntaxSugar:
    """Tests for syntax sugar resolution during create_job."""

    def _create_step(self, step_data: dict) -> Step:
        """Helper: create JobTemplate with step, run create_job, return the Step."""
        template_data = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "TestJob",
            "steps": [step_data],
            "extensions": ["FEATURE_BUNDLE_1"],
        }
        template = _parse_model(model=JobTemplate, obj=template_data, context=fb1_context())
        job = create_job(job_template=template, job_parameter_values={})
        return job.steps[0]

    def test_script_preserved(self) -> None:
        """Test that script is preserved when already using script."""
        step = self._create_step({"name": "Step1", "script": STEP_SCRIPT})
        assert step.script is not None
        assert step.script.actions.onRun.command == "echo"

    def test_python_desugaring(self) -> None:
        """Test Python interpreter de-sugaring."""
        step = self._create_step({"name": "Step1", "python": {"script": "print('hello')"}})

        assert step.script is not None
        assert step.script.actions.onRun.command == "python"
        assert step.script.embeddedFiles is not None
        assert len(step.script.embeddedFiles) == 1
        assert step.script.embeddedFiles[0].filename is not None
        assert step.script.embeddedFiles[0].filename.endswith(".py")
        assert step.script.actions.onRun.args is not None
        assert any("Task.File." in arg for arg in step.script.actions.onRun.args)

    def test_bash_desugaring(self) -> None:
        """Test Bash interpreter de-sugaring."""
        step = self._create_step({"name": "Step1", "bash": {"script": "echo hello"}})

        assert step.script is not None
        assert step.script.actions.onRun.command == "bash"
        assert step.script.embeddedFiles is not None
        assert step.script.embeddedFiles[0].filename is not None
        assert step.script.embeddedFiles[0].filename.endswith(".sh")

    def test_cmd_desugaring_has_c_flag(self) -> None:
        """Test cmd interpreter de-sugaring includes /C flag."""
        step = self._create_step({"name": "Step1", "cmd": {"script": "echo hello"}})

        assert step.script is not None
        assert step.script.actions.onRun.command == "cmd"
        assert step.script.actions.onRun.args is not None
        assert step.script.actions.onRun.args[0] == "/C"
        assert step.script.embeddedFiles is not None
        assert step.script.embeddedFiles[0].filename is not None
        assert step.script.embeddedFiles[0].filename.endswith(".bat")

    def test_powershell_desugaring_has_file_flag(self) -> None:
        """Test PowerShell interpreter de-sugaring includes -File flag."""
        step = self._create_step({"name": "Step1", "powershell": {"script": "Write-Host 'hello'"}})

        assert step.script is not None
        assert step.script.actions.onRun.command == "powershell"
        assert step.script.actions.onRun.args is not None
        assert step.script.actions.onRun.args[0] == "-File"
        assert step.script.embeddedFiles is not None
        assert step.script.embeddedFiles[0].filename is not None
        assert step.script.embeddedFiles[0].filename.endswith(".ps1")

    def test_node_desugaring(self) -> None:
        """Test Node.js interpreter de-sugaring."""
        step = self._create_step({"name": "Step1", "node": {"script": "console.log('hello')"}})

        assert step.script is not None
        assert step.script.actions.onRun.command == "node"
        assert step.script.embeddedFiles is not None
        assert step.script.embeddedFiles[0].filename is not None
        assert step.script.embeddedFiles[0].filename.endswith(".js")

    def test_preserves_user_args(self) -> None:
        """Test that user-provided args are preserved after file reference."""
        step = self._create_step(
            {"name": "Step1", "python": {"script": "print('hello')", "args": ["-v"]}}
        )

        assert step.script is not None
        args = step.script.actions.onRun.args
        assert args is not None
        file_ref_idx = next(i for i, arg in enumerate(args) if "Task.File." in arg)
        assert "-v" in args
        assert args.index(ArgString("-v")) > file_ref_idx

    def test_preserves_timeout(self) -> None:
        """Test that timeout is preserved."""
        step = self._create_step(
            {"name": "Step1", "python": {"script": "print('hello')", "timeout": 60}}
        )

        assert step.script is not None
        assert step.script.actions.onRun.timeout == 60


# FEATURE_BUNDLE_1 raises the length ceilings for a job name, environment name,
# embedded-file name, and embedded-file filename during template decode. The
# job-creation path re-instantiates the models without a parsing context, so a
# name that decode accepted under FEATURE_BUNDLE_1 must still survive
# create_job. The group-A and group-F tests below assert that survival: these
# failed before create_job seeded the FEATURE_BUNDLE_1 parsing context.
_FB1_SUPPORTED = [ExtensionName.FEATURE_BUNDLE_1]


class TestCreateJobPreservesFeatureBundle1Lengths:
    """Length-ceiling behaviour for names/filenames across decode and create_job.

    FEATURE_BUNDLE_1 decode accepts the raised length ceilings (512 for names,
    256 for filenames); create_job's re-validation of the instantiated models
    must apply the same extension-aware limits, so a value decode accepted
    survives create_job, and the resolved job name is still checked against the
    128/512 limit after the format string has been resolved.

    Groups:
      A. FEATURE_BUNDLE_1 decode -> create_job SURVIVE: a 512/512/512/256 name/name/name/filename accepted at decode must be
         preserved by create_job.
      B. FEATURE_BUNDLE_1 decode ceiling (expected PASS): one past the ceiling
         is rejected at decode.
      C. Non-FEATURE_BUNDLE_1 decode (expected PASS): the default 128/64/64/64
         ceilings apply.
      D. static type ceilings without a parsing context (expected PASS): 512 for
         ``JobName``/``Identifier``/``EnvironmentName``, 256 for ``Filename``.
         Says nothing about the extension-specific validators, which apply the
         base limits when no context is present.
      E. Separator (expected PASS): a filename containing a path separator is
         rejected both during FEATURE_BUNDLE_1 decode and during direct
         ``EmbeddedFileText.model_validate`` with no context.
      F. Round trip: all four lengthened fields survive
         create_job simultaneously.
      G. Resolved job name (matrix): the resolved job name is checked against
         the extension-aware 128/512 limit after format-string substitution.
    """

    @staticmethod
    def _template(
        *,
        job_name: str = "J",
        env_name: str = "Env1",
        ef_name: str = "Run",
        ef_filename: str = "run.sh",
        declare_fb1: bool = True,
    ) -> dict:
        """Build a minimal valid template with one step, one embedded file, and one job environment.

        The onRun command does not reference the embedded file, so the file's
        name length is exercised without a Task.File.* reference constraining it.
        """
        template: dict = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": job_name,
            "steps": [
                {
                    "name": "s",
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

    @staticmethod
    def _create(template: dict):
        """Decode the template with FEATURE_BUNDLE_1 supported, then create a job from it."""
        job_template = decode_job_template(template=template, supported_extensions=_FB1_SUPPORTED)
        return create_job(job_template=job_template, job_parameter_values={})

    # ---- Group A: FEATURE_BUNDLE_1 decode -> create_job SURVIVE ----

    def test_job_name_512_chars_fb1_create_job_preserved(self) -> None:
        """A 512-char job name accepted by FEATURE_BUNDLE_1 decode must survive create_job."""
        job = self._create(self._template(job_name="a" * 512))
        assert len(job.name) == 512

    def test_environment_name_512_chars_fb1_create_job_preserved(self) -> None:
        """A 512-char job-environment name must survive create_job."""
        job = self._create(self._template(env_name="a" * 512))
        assert len(job.jobEnvironments[0].name) == 512

    def test_embedded_file_name_512_chars_fb1_create_job_preserved(self) -> None:
        """A 512-char embedded-file name must survive create_job."""
        job = self._create(self._template(ef_name="a" * 512))
        assert len(job.steps[0].script.embeddedFiles[0].name) == 512

    def test_embedded_file_filename_256_chars_fb1_create_job_preserved(self) -> None:
        """A 256-char embedded-file filename must survive create_job."""
        job = self._create(self._template(ef_filename="a" * 256))
        assert len(job.steps[0].script.embeddedFiles[0].filename) == 256

    # ---- Group B: FEATURE_BUNDLE_1 decode ceiling (PASS) ----

    def test_job_name_513_chars_fb1_decode_rejected(self) -> None:
        """One past the 512 job-name ceiling is rejected at FEATURE_BUNDLE_1 decode."""
        with pytest.raises(DecodeValidationError, match="512"):
            decode_job_template(
                template=self._template(job_name="a" * 513),
                supported_extensions=_FB1_SUPPORTED,
            )

    def test_environment_name_513_chars_fb1_decode_rejected(self) -> None:
        """One past the 512 environment-name ceiling is rejected at FEATURE_BUNDLE_1 decode."""
        with pytest.raises(DecodeValidationError, match="512"):
            decode_job_template(
                template=self._template(env_name="a" * 513),
                supported_extensions=_FB1_SUPPORTED,
            )

    def test_embedded_file_name_513_chars_fb1_decode_rejected(self) -> None:
        """One past the 512 embedded-file-name ceiling is rejected at FEATURE_BUNDLE_1 decode."""
        with pytest.raises(DecodeValidationError, match="512"):
            decode_job_template(
                template=self._template(ef_name="a" * 513),
                supported_extensions=_FB1_SUPPORTED,
            )

    def test_embedded_file_filename_257_chars_fb1_decode_rejected(self) -> None:
        """One past the 256 embedded-file-filename ceiling is rejected at FEATURE_BUNDLE_1 decode."""
        with pytest.raises(DecodeValidationError, match="256"):
            decode_job_template(
                template=self._template(ef_filename="a" * 257),
                supported_extensions=_FB1_SUPPORTED,
            )

    # ---- Group C: non-FEATURE_BUNDLE_1 decode default ceilings (PASS) ----

    def test_job_name_128_chars_no_extension_decode_accepted(self) -> None:
        """Without FEATURE_BUNDLE_1 the default 128 job-name ceiling accepts 128 chars."""
        result = decode_job_template(
            template=self._template(job_name="a" * 128, declare_fb1=False),
            supported_extensions=[],
        )
        assert len(result.name) == 128

    def test_job_name_129_chars_no_extension_decode_rejected(self) -> None:
        """Without FEATURE_BUNDLE_1 a 129-char job name is rejected at the default 128 ceiling."""
        with pytest.raises(DecodeValidationError, match="128"):
            decode_job_template(
                template=self._template(job_name="a" * 129, declare_fb1=False),
                supported_extensions=[],
            )

    def test_environment_name_64_chars_no_extension_decode_accepted(self) -> None:
        """Without FEATURE_BUNDLE_1 the default 64 environment-name ceiling accepts 64 chars."""
        result = decode_job_template(
            template=self._template(env_name="a" * 64, declare_fb1=False),
            supported_extensions=[],
        )
        assert len(result.jobEnvironments[0].name) == 64

    def test_environment_name_65_chars_no_extension_decode_rejected(self) -> None:
        """Without FEATURE_BUNDLE_1 a 65-char environment name is rejected at the default 64 ceiling."""
        with pytest.raises(DecodeValidationError, match="64"):
            decode_job_template(
                template=self._template(env_name="a" * 65, declare_fb1=False),
                supported_extensions=[],
            )

    def test_embedded_file_name_64_chars_no_extension_decode_accepted(self) -> None:
        """Without FEATURE_BUNDLE_1 the default 64 embedded-file-name ceiling accepts 64 chars."""
        result = decode_job_template(
            template=self._template(ef_name="a" * 64, declare_fb1=False),
            supported_extensions=[],
        )
        assert len(result.steps[0].script.embeddedFiles[0].name) == 64

    def test_embedded_file_name_65_chars_no_extension_decode_rejected(self) -> None:
        """Without FEATURE_BUNDLE_1 a 65-char embedded-file name is rejected at the default 64 ceiling."""
        with pytest.raises(DecodeValidationError, match="64"):
            decode_job_template(
                template=self._template(ef_name="a" * 65, declare_fb1=False),
                supported_extensions=[],
            )

    def test_embedded_file_filename_64_chars_no_extension_decode_accepted(self) -> None:
        """Without FEATURE_BUNDLE_1 the default 64 embedded-file-filename ceiling accepts 64 chars."""
        result = decode_job_template(
            template=self._template(ef_filename="a" * 64, declare_fb1=False),
            supported_extensions=[],
        )
        assert len(result.steps[0].script.embeddedFiles[0].filename) == 64

    def test_embedded_file_filename_65_chars_no_extension_decode_rejected(self) -> None:
        """Without FEATURE_BUNDLE_1 a 65-char embedded-file filename is rejected at the default 64 ceiling."""
        with pytest.raises(DecodeValidationError, match="64"):
            decode_job_template(
                template=self._template(ef_filename="a" * 65, declare_fb1=False),
                supported_extensions=[],
            )

    # ---- Group D: static type ceilings, no parsing context (PASS) ----

    def test_job_name_512_chars_type_adapter_no_context_accepted(self) -> None:
        """The JobName type alias alone accepts 512 chars: its static ceiling is 512."""
        adapter = TypeAdapter(JobName)
        assert len(adapter.validate_python("a" * 512)) == 512

    def test_job_name_513_chars_type_adapter_no_context_rejected(self) -> None:
        """Direct construction semantics: 513 chars exceeds the static JobName type ceiling (512)."""
        adapter = TypeAdapter(JobName)
        with pytest.raises(ValidationError, match="512"):
            adapter.validate_python("a" * 513)

    @staticmethod
    def _direct_env(name: str) -> dict:
        """A context-free Environment dict: the script command is a pre-built
        CommandString instance so no parsing context is required, leaving the
        name validator as the only length gate exercised."""
        return {
            "name": name,
            "script": {"actions": {"onEnter": {"command": CommandString("echo")}}},
        }

    @staticmethod
    def _direct_ef(**overrides) -> dict:
        """A context-free EmbeddedFileText dict: ``data`` is a pre-built
        DataString instance (DynamicConstrainedStr._validate takes the
        ``type(value) is cls`` branch), so no parsing context is required."""
        d: dict = {"name": "Run", "type": "TEXT", "data": DataString("x")}
        d.update(overrides)
        return d

    def test_environment_name_513_chars_no_context_rejected(self) -> None:
        """Direct construction: 513 chars exceeds the static EnvironmentName type ceiling (512)."""
        with pytest.raises(ValidationError, match="512"):
            Environment.model_validate(self._direct_env("a" * 513))

    def test_embedded_file_name_513_chars_no_context_rejected(self) -> None:
        """Direct construction: 513 chars exceeds the static Identifier type ceiling (512)."""
        with pytest.raises(ValidationError, match="512"):
            EmbeddedFileText.model_validate(self._direct_ef(name="a" * 513))

    def test_embedded_file_filename_257_chars_no_context_rejected(self) -> None:
        """Direct construction: 257 chars exceeds the static Filename type ceiling (256)."""
        with pytest.raises(ValidationError, match="256"):
            EmbeddedFileText.model_validate(self._direct_ef(filename="a" * 257))

    # ---- Group E: filename path separator (PASS) ----

    def test_embedded_file_filename_forward_slash_fb1_decode_rejected(self) -> None:
        """A filename containing '/' is rejected during FEATURE_BUNDLE_1 decode."""
        with pytest.raises(DecodeValidationError, match="path separators"):
            decode_job_template(
                template=self._template(ef_filename="a/b"),
                supported_extensions=_FB1_SUPPORTED,
            )

    def test_embedded_file_filename_backslash_fb1_decode_rejected(self) -> None:
        """A filename containing '\\' is rejected during FEATURE_BUNDLE_1 decode."""
        with pytest.raises(DecodeValidationError, match="path separators"):
            decode_job_template(
                template=self._template(ef_filename="a\\b"),
                supported_extensions=_FB1_SUPPORTED,
            )

    def test_embedded_file_filename_forward_slash_no_context_rejected(self) -> None:
        """Direct construction: a filename containing '/' is rejected by the
        path-separator check, which runs regardless of parsing context."""
        with pytest.raises(ValidationError, match="path separators"):
            EmbeddedFileText.model_validate(self._direct_ef(filename="a/b"))

    def test_embedded_file_filename_backslash_no_context_rejected(self) -> None:
        """Direct construction: a filename containing '\\' is rejected by the
        path-separator check, which runs regardless of parsing context."""
        with pytest.raises(ValidationError, match="path separators"):
            EmbeddedFileText.model_validate(self._direct_ef(filename="a\\b"))

    # ---- Group F: round trip, all four fields at once ----

    def test_all_four_fields_at_ceiling_fb1_create_job_preserved(self) -> None:
        """All four FEATURE_BUNDLE_1-lengthened fields must survive create_job simultaneously."""
        job = self._create(
            self._template(
                job_name="a" * 512,
                env_name="a" * 512,
                ef_name="a" * 512,
                ef_filename="a" * 256,
            )
        )
        assert (
            len(job.name),
            len(job.jobEnvironments[0].name),
            len(job.steps[0].script.embeddedFiles[0].name),
            len(job.steps[0].script.embeddedFiles[0].filename),
        ) == (512, 512, 512, 256)

    # ---- Group G: resolved job name matrix ----

    def _create_with_resolved_job_name(self, declare_fb1: bool, resolved_len: int):
        """Decode a template whose job name is ``{{Param.N}}`` and create a job
        whose parameter resolves the name to ``resolved_len`` characters, so the
        resolved-value length is checked (not the literal template value)."""
        template = self._template(job_name="{{Param.N}}", declare_fb1=declare_fb1)
        template.setdefault("parameterDefinitions", []).append({"name": "N", "type": "STRING"})
        supported = [ExtensionName.FEATURE_BUNDLE_1] if declare_fb1 else []
        decoded = decode_job_template(template=template, supported_extensions=supported)
        values = {"N": ParameterValue(type=ParameterValueType.STRING, value="a" * resolved_len)}
        return create_job(job_template=decoded, job_parameter_values=values)

    def test_resolved_job_name_512_chars_fb1_create_job_preserved(self) -> None:
        assert len(self._create_with_resolved_job_name(True, 512).name) == 512

    def test_resolved_job_name_513_chars_fb1_create_job_rejected(self) -> None:
        with pytest.raises(DecodeValidationError, match="512"):
            self._create_with_resolved_job_name(True, 513)

    def test_resolved_job_name_128_chars_no_extension_create_job_accepted(self) -> None:
        assert len(self._create_with_resolved_job_name(False, 128).name) == 128

    def test_resolved_job_name_129_chars_no_extension_create_job_rejected(self) -> None:
        with pytest.raises(DecodeValidationError, match="128"):
            self._create_with_resolved_job_name(False, 129)
