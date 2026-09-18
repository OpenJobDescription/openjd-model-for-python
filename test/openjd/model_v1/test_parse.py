# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from enum import Enum
import json
from typing import Any, Optional, Type, Union

import pytest

from openjd.model._v1 import (
    CallerLimits,
    decode_environment_template,
    decode_environment_template_str,
    decode_job_template,
    decode_job_template_str,
)
from openjd.model._v1.types import (
    DocumentType,
)
from openjd.model._v1.errors import (
    DecodeValidationError,
    ModelValidationError,
)
from openjd.model._v1.template import JobTemplate, EnvironmentTemplate


class TestDecodeJobTemplate:
    @pytest.mark.parametrize(
        "template",
        [
            pytest.param({"notspecversion": "badvalue"}, id="missing specificationVersion field"),
            pytest.param({"specificationVersion": "badvalue"}, id="unknown version"),
            pytest.param(
                {"specificationVersion": "environment-2023-09"}, id="not a job template version"
            ),
        ],
    )
    def test_fail_cases(self, template: dict[str, Any]) -> None:
        # THEN
        with pytest.raises(DecodeValidationError):
            decode_job_template(template=template)

    @pytest.mark.parametrize(
        "template,expected_class",
        [
            pytest.param(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "name",
                    "steps": [
                        {"name": "step", "script": {"actions": {"onRun": {"command": "do thing"}}}}
                    ],
                },
                JobTemplate,
                id="2023-09",
            ),
        ],
    )
    def test_success(
        self,
        template: dict[str, Any],
        expected_class: Union[Type[JobTemplate], Type[EnvironmentTemplate]],
    ) -> None:
        # WHEN
        result = decode_job_template(template=template)

        # THEN
        assert isinstance(result, expected_class)

    def test_empty_steps_raises_model_validation_error(self) -> None:
        # ``steps: []`` is structurally well-formed (parses cleanly) but
        # fails the model-level invariant that a job template must have
        # at least one step. This is a model-validation concern, not a
        # decode-validation concern, so v1 raises
        # ``ModelValidationError`` rather than ``DecodeValidationError``
        # (v0 raised the latter, which v1 deliberately corrects —
        # ``DecodeValidationError`` is reserved for parse-stage failures
        # like unknown specificationVersion or malformed YAML/JSON).
        # The divergence is documented in
        # ``specs/python-model-interface.md`` under "Exceptions".
        template = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "T",
            "steps": [],
        }
        with pytest.raises(ModelValidationError) as exc_info:
            decode_job_template(template=template)
        # Pin the message body (per the AGENTS.md "Test Quality Standard":
        # exception class + message body, not just class).
        assert str(exc_info.value) == (
            "1 validation error for JobTemplate\n" "JobTemplate: must have at least one step."
        )


class TestDecodeEnvironmentTemplate:
    @pytest.mark.parametrize(
        "template",
        [
            pytest.param({"notspecversion": "badvalue"}, id="missing specificationVersion field"),
            pytest.param({"specificationVersion": "badvalue"}, id="unknown version"),
            pytest.param(
                {"specificationVersion": "jobtemplate-2023-09"},
                id="not an environment template version",
            ),
        ],
    )
    def test_fail_cases(self, template: dict[str, Any]) -> None:
        # THEN
        with pytest.raises(DecodeValidationError):
            decode_environment_template(template=template)

    @pytest.mark.parametrize(
        "template,expected_class",
        [
            pytest.param(
                {
                    "specificationVersion": "environment-2023-09",
                    "environment": {
                        "name": "FooEnv",
                        "description": "A description",
                        "script": {
                            "actions": {"onEnter": {"command": "echo", "args": ["Hello", "World"]}}
                        },
                    },
                },
                EnvironmentTemplate,
                id="2023-09",
            ),
        ],
    )
    def test_success(
        self,
        template: dict[str, Any],
        expected_class: Union[Type[JobTemplate], Type[EnvironmentTemplate]],
    ) -> None:
        # WHEN
        result = decode_environment_template(template=template)

        # THEN
        assert isinstance(result, expected_class)


class MockExtensionName(str, Enum):
    """A mock enum with only SUPPORTED_NAME for testing."""

    SUPPORTED_NAME = "SUPPORTED_NAME"


class MockExtensionNameWithTwoNames(str, Enum):
    """A mock enum with only SUPPORTED_NAME for testing."""

    SUPPORTED_NAME = "SUPPORTED_NAME"
    ANOTHER_SUPPORTED_NAME = "ANOTHER_SUPPORTED_NAME"


@pytest.mark.parametrize(
    "template,template_type,decode_function",
    [
        pytest.param(
            {
                "name": "DemoJob",
                "specificationVersion": "jobtemplate-2023-09",
                "parameterDefinitions": [{"name": "Foo", "type": "FLOAT", "default": "12"}],
                "steps": [
                    {
                        "name": "DemoStep",
                        "script": {"actions": {"onRun": {"command": "echo"}}},
                    }
                ],
            },
            "JobTemplate",
            decode_job_template,
            id="job template",
        ),
        pytest.param(
            {
                "specificationVersion": "environment-2023-09",
                "environment": {
                    "name": "FooEnv",
                    "description": "A description",
                    "script": {"actions": {"onEnter": {"command": "echo"}}},
                },
            },
            "EnvironmentTemplate",
            decode_environment_template,
            id="environment template",
        ),
    ],
)
def test_template_extensions_list(template, template_type, decode_function) -> None:
    # Confirm the template doesn't include extensions yet and can be decoded
    assert "extensions" not in template
    decode_function(template=template)

    # When a known extension name is in the supported list, it's accepted
    template["extensions"] = ["TASK_CHUNKING"]
    decode_function(template=template, supported_extensions=["TASK_CHUNKING"])

    # If provided, the extensions list cannot be empty
    template["extensions"] = []
    with pytest.raises(ValueError) as excinfo:
        decode_function(template=template, supported_extensions=["TASK_CHUNKING"])
    assert "if provided, must be a non-empty list" in str(excinfo.value)

    # Extension not in supported_extensions is rejected
    template["extensions"] = ["TASK_CHUNKING"]
    with pytest.raises(ValueError) as excinfo:
        decode_function(template=template)
    assert "Unsupported extension names: TASK_CHUNKING" in str(excinfo.value)

    # Extension names cannot be repeated
    template["extensions"] = ["TASK_CHUNKING", "TASK_CHUNKING"]
    with pytest.raises(ValueError) as excinfo:
        decode_function(template=template, supported_extensions=["TASK_CHUNKING"])
        assert "Duplicate values for extension name are not allowed." in str(excinfo.value)

        # When the request list includes an unsupported extension name
        template["extensions"] = ["SUPPORTED_NAME"]
        with pytest.raises(ValueError) as excinfo:
            decode_function(template=template, supported_extensions=["UNSUPPORTED_NAME"])
        assert (
            f"1 validation errors for {template_type}\nextensions:\n\tUnsupported extension names: SUPPORTED_NAME"
            in str(excinfo.value)
        )

    # Unknown extension name is rejected even if in supported_extensions
    template["extensions"] = ["UNSUPPORTED_NAME"]
    with pytest.raises(ValueError) as excinfo:
        decode_function(template=template, supported_extensions=["UNSUPPORTED_NAME"])
    assert "Unsupported extension names: UNSUPPORTED_NAME" in str(excinfo.value)

    # Multiple known extensions can be enabled simultaneously
    template["extensions"] = ["TASK_CHUNKING", "EXPR"]
    decode_function(template=template, supported_extensions=["TASK_CHUNKING", "EXPR"])


class TestLetIdentifierLengthCap(object):
    """A ``let`` binding's ``<UserIdentifier>`` is capped at 512 characters
    (Template Schemas §3.6.1). Enforced by openjd-model 0.6.0 (openjd-rs#358);
    before that a 513-character name was accepted here. The v0 side has its own
    coverage in ``test/openjd/model_v0/v2023_09/test_let_bindings.py``; this is the
    v1 path, which had none.

    The cap is flat, not the §7.1 ``<Identifier>`` cap of 64 rising to 512 with
    ``FEATURE_BUNDLE_1``. The 512-character accept with ``EXPR`` alone is what makes
    the difference observable, and is why the fix upstream did not reuse
    ``EffectiveLimits::max_identifier_len``.
    """

    @staticmethod
    def _template(name: str, extensions: list[str]) -> dict[str, Any]:
        return {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "T",
            "extensions": extensions,
            "steps": [
                {
                    "name": "Step1",
                    "let": [f"{name} = 42"],
                    "script": {"actions": {"onRun": {"command": "echo", "args": ["hi"]}}},
                }
            ],
        }

    @pytest.mark.parametrize(
        "extensions",
        [
            pytest.param(["EXPR"], id="EXPR only"),
            pytest.param(["EXPR", "FEATURE_BUNDLE_1"], id="with FEATURE_BUNDLE_1"),
        ],
    )
    def test_512_characters_is_accepted(self, extensions: list[str]) -> None:
        """Both extension sets accept the boundary. Without ``FEATURE_BUNDLE_1`` the
        §7.1 cap would be 64, so this is the case that pins the cap as flat."""
        template = self._template("a" * 512, extensions)
        assert decode_job_template(template=template, supported_extensions=extensions)

    @pytest.mark.parametrize(
        "extensions",
        [
            pytest.param(["EXPR"], id="EXPR only"),
            pytest.param(["EXPR", "FEATURE_BUNDLE_1"], id="with FEATURE_BUNDLE_1"),
        ],
    )
    def test_513_characters_is_rejected(self, extensions: list[str]) -> None:
        template = self._template("a" * 513, extensions)
        with pytest.raises(ModelValidationError) as excinfo:
            decode_job_template(template=template, supported_extensions=extensions)
        message = str(excinfo.value)
        assert "steps[0] -> let[0]" in message
        assert "exceeds 512 characters" in message

    def test_a_short_name_is_unaffected(self) -> None:
        """Control. 65 characters is over the §7.1 cap of 64 and under §3.6.1's, so it
        must be accepted -- a regression to the wrong constant would reject it."""
        template = self._template("a" * 65, ["EXPR"])
        assert decode_job_template(template=template, supported_extensions=["EXPR"])


class TestDecodeJobTemplateStr:
    """``decode_job_template_str`` wrapper: parses YAML or JSON
    directly, no intermediate dict. The wrapper lives on
    ``openjd.model._v1`` (re-exported); the underlying Rust function
    is in ``openjd._openjd_rs``."""

    _VALID_YAML = """
specificationVersion: jobtemplate-2023-09
name: SimpleJob
steps:
  - name: Step1
    script:
      actions:
        onRun:
          command: echo
          args: ["hello"]
"""
    _VALID_JSON = json.dumps(
        {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "JsonJob",
            "steps": [
                {
                    "name": "Step1",
                    "script": {"actions": {"onRun": {"command": "echo", "args": ["hi"]}}},
                }
            ],
        }
    )

    def test_yaml_default(self) -> None:
        t = decode_job_template_str(self._VALID_YAML)
        assert isinstance(t, JobTemplate)
        assert t.name == "SimpleJob"

    def test_yaml_explicit(self) -> None:
        t = decode_job_template_str(self._VALID_YAML, DocumentType.YAML)
        assert t.name == "SimpleJob"

    def test_json_explicit(self) -> None:
        t = decode_job_template_str(self._VALID_JSON, DocumentType.JSON)
        assert t.name == "JsonJob"

    def test_json_via_yaml_default(self) -> None:
        # YAML is a JSON superset; JSON parses fine under the YAML
        # default. Pin that.
        t = decode_job_template_str(self._VALID_JSON)
        assert t.name == "JsonJob"

    def test_supported_extensions_forwarded(self) -> None:
        # Template requests EXPR; supported_extensions allowlist must
        # include it for decoding to succeed.
        with_ext = """
specificationVersion: jobtemplate-2023-09
name: ExprJob
extensions: ["EXPR"]
steps:
  - name: S
    script:
      actions:
        onRun: {command: echo, args: ["hi"]}
"""
        # Allowed.
        t = decode_job_template_str(with_ext, supported_extensions=["EXPR"])
        assert t.name == "ExprJob"
        # Rejected with empty allowlist.
        with pytest.raises(ModelValidationError, match="Unsupported extension"):
            decode_job_template_str(with_ext)

    def test_invalid_yaml_raises(self) -> None:
        with pytest.raises(DecodeValidationError):
            decode_job_template_str("specificationVersion: nope")


class TestDecodeEnvironmentTemplateStr:
    """``decode_environment_template_str`` wrapper: parses YAML or
    JSON directly. Mirrors ``decode_job_template_str`` for environment
    templates."""

    _VALID_YAML = """
specificationVersion: environment-2023-09
environment:
  name: PythonVenv
  script:
    actions:
      onEnter: {command: python, args: ["-m", "venv", ".venv"]}
      onExit:  {command: rm, args: ["-rf", ".venv"]}
"""
    _VALID_JSON = json.dumps(
        {
            "specificationVersion": "environment-2023-09",
            "environment": {
                "name": "Env1",
                "script": {"actions": {"onEnter": {"command": "echo", "args": ["enter"]}}},
            },
        }
    )

    def test_yaml_default(self) -> None:
        e = decode_environment_template_str(self._VALID_YAML)
        assert isinstance(e, EnvironmentTemplate)
        assert e.environment.name == "PythonVenv"

    def test_json_explicit(self) -> None:
        e = decode_environment_template_str(self._VALID_JSON, DocumentType.JSON)
        assert e.environment.name == "Env1"

    def test_invalid_yaml_raises(self) -> None:
        with pytest.raises(DecodeValidationError):
            decode_environment_template_str(": not a mapping")


class TestStepEnvironmentNameScope(object):
    """A Step Environment's ``name`` is scoped to the Step that defines it (Template
    Schemas §3 StepTemplate, §4 Environment): unique within that Step's list, and
    distinct from every Job Environment. Different Steps may reuse a name.

    openjd-model 0.7.1 (openjd-rs#381) relaxed an over-strict check that held every
    environment name in the template in one set, so the second Step to declare
    ``StepEnv`` was rejected. The v0 path always accepted this; this is the v1 path,
    which had no coverage.

    The error-text assertions below pin the v1 wording as it stands. It differs from
    v0 on purpose-of-record, not by design: v0 reports the step-vs-job rule as
    ``Name X must differ from the names of Environments defined at the root of the
    template.`` at ``step[i] -> stepEnvironments[j] -> name``, while v1 reports both
    the per-Step and the step-vs-job rule as ``duplicate environment name: 'X'`` at
    ``steps[i] -> stepEnvironments[j]``. Aligning the two is an openjd-rs concern;
    these assertions only guard against the relaxation dropping a rule.
    """

    @staticmethod
    def _environment(name: str) -> dict[str, Any]:
        return {
            "name": name,
            "script": {"actions": {"onEnter": {"command": "echo", "args": [name]}}},
        }

    @classmethod
    def _step(cls, name: str, environment_names: list[str]) -> dict[str, Any]:
        return {
            "name": name,
            "stepEnvironments": [cls._environment(n) for n in environment_names],
            "script": {"actions": {"onRun": {"command": "echo", "args": [name]}}},
        }

    @classmethod
    def _template(cls, steps: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "T",
            "jobEnvironments": [cls._environment("JobEnv")],
            "steps": steps,
        }

    def test_same_name_across_steps_is_accepted(self) -> None:
        """Four Steps each declare ``StepEnv``. Only one Step's environments are ever
        active in a Session, so these names never collide."""
        template = self._template([self._step(f"Step{i}", ["StepEnv"]) for i in range(4)])
        job_template = decode_job_template(template=template, supported_extensions=[])
        names = [[e.name for e in (s.step_environments or [])] for s in job_template.steps]
        assert names == [["StepEnv"]] * 4

    def test_duplicate_within_one_step_is_rejected(self) -> None:
        """Control for §3 rule 1: the per-Step uniqueness check must survive the relaxation."""
        template = self._template(
            [self._step("Step0", ["StepEnv"]), self._step("Step1", ["StepEnv", "StepEnv"])]
        )
        with pytest.raises(ModelValidationError) as excinfo:
            decode_job_template(template=template, supported_extensions=[])
        message = str(excinfo.value)
        assert "steps[1] -> stepEnvironments[1]" in message
        assert "duplicate environment name: 'StepEnv'" in message

    def test_step_env_named_like_job_env_is_rejected(self) -> None:
        """Control for §3 rule 2: a Step Environment may not reuse a Job Environment name."""
        template = self._template(
            [self._step("Step0", ["StepEnv"]), self._step("Step1", ["JobEnv"])]
        )
        with pytest.raises(ModelValidationError) as excinfo:
            decode_job_template(template=template, supported_extensions=[])
        message = str(excinfo.value)
        assert "steps[1] -> stepEnvironments[0]" in message
        assert "duplicate environment name: 'JobEnv'" in message

    def test_duplicate_job_env_names_is_rejected(self) -> None:
        """Control for §4 uniqueness within ``jobEnvironments``. The relaxation split one
        template-wide set into a job set plus a per-Step set; this pins the job set."""
        template = self._template([self._step("Step0", ["StepEnv"])])
        template["jobEnvironments"] = [self._environment("JobEnv"), self._environment("JobEnv")]
        with pytest.raises(ModelValidationError) as excinfo:
            decode_job_template(template=template, supported_extensions=[])
        message = str(excinfo.value)
        assert "jobEnvironments[1]" in message
        assert "duplicate environment name: 'JobEnv'" in message

    def test_max_env_count_counts_repeated_names_separately(self) -> None:
        """``max_env_count`` bounds the number of environments, not the number of distinct
        names. Four Steps each declaring ``StepEnv`` plus ``JobEnv`` is 5 environments
        under 2 names, so a limit of 4 must reject; counting distinct names would not."""
        template = self._template([self._step(f"Step{i}", ["StepEnv"]) for i in range(4)])
        with pytest.raises(ModelValidationError) as excinfo:
            decode_job_template(
                template=template,
                supported_extensions=[],
                caller_limits=CallerLimits(max_env_count=4),
            )
        assert "total environments (5) exceeds caller limit of 4" in str(excinfo.value)


def _one_step_template(**overrides: Any) -> dict[str, Any]:
    """Minimal 2023-09 job template with one echo step; ``overrides`` replace
    top-level fields."""
    template: dict[str, Any] = {
        "specificationVersion": "jobtemplate-2023-09",
        "name": "T",
        "steps": [{"name": "S", "script": {"actions": {"onRun": {"command": "echo"}}}}],
    }
    template.update(overrides)
    return template


class TestEmbeddedFileFilenameIsASinglePathComponent(object):
    """openjd-sessions joins an embedded file's ``filename`` to the session
    directory, so openjd-model requires it to be a plain single path component.
    Template Schemas §6.1.1 only says "characters allowed in filenames on the host
    operating system", so this is the implementation's rule, not a conformance one.
    openjd-model 0.8.0 (openjd-rs#359) rejects ``.``, ``..`` and a null byte; 0.7.1
    only rejected ``/`` and ``\\``. The v0 reference accepts all three, so this pins
    a v1 behaviour v0 does not share.
    """

    @staticmethod
    def _template(filename: str) -> dict[str, Any]:
        return _one_step_template(
            steps=[
                {
                    "name": "S",
                    "script": {
                        "actions": {"onRun": {"command": "echo"}},
                        "embeddedFiles": [
                            {"name": "F", "type": "TEXT", "filename": filename, "data": "x"}
                        ],
                    },
                }
            ]
        )

    @pytest.mark.parametrize(
        "filename, detail",
        [
            pytest.param(".", "must not be '.'.", id="dot"),
            pytest.param("..", "must not be '..'.", id="dot-dot"),
            pytest.param("a\x00b", "must not contain null characters.", id="null byte"),
        ],
    )
    def test_unsafe_filename_is_rejected(self, filename: str, detail: str) -> None:
        with pytest.raises(ModelValidationError) as excinfo:
            decode_job_template(template=self._template(filename))
        message = str(excinfo.value)
        assert "steps[0] -> script -> embeddedFiles[0] -> filename" in message
        assert detail in message

    def test_plain_filename_is_accepted(self) -> None:
        """Control: a dotted basename is still a single component."""
        assert decode_job_template(template=self._template("scene.v2.ma"))


class TestResolvedValueConstraintsAtTemplateValidation(object):
    """Constraints the spec places on what a format string resolves to are
    checked at template validation when the value is statically knowable.
    openjd-model 0.8.0 (openjd-rs#383, follow-ups in #397). Each test says what
    0.7.1 did with the same template; two cases below are controls 0.7.1 already
    handled, kept so the checks they exercise cannot regress together.
    """

    def test_job_name_that_resolves_over_128_characters_is_rejected(self) -> None:
        """Template Schemas §1.1.1: the job name resolves to at most 128 characters.
        The expression has no free symbols, so the length is known at validation.
        0.7.1 accepted this template."""
        template = _one_step_template(extensions=["EXPR"], name="{{ 'x' * 129 }}")
        with pytest.raises(ModelValidationError) as excinfo:
            decode_job_template(template=template, supported_extensions=["EXPR"])
        message = str(excinfo.value)
        assert "name:" in message
        assert "resolves to at least 129 characters, exceeding the maximum of 128." in message

    def test_job_name_that_resolves_to_128_characters_is_accepted(self) -> None:
        """Boundary control."""
        template = _one_step_template(extensions=["EXPR"], name="{{ 'x' * 128 }}")
        assert decode_job_template(template=template, supported_extensions=["EXPR"])

    def test_control_character_in_a_literal_run_of_an_interpolated_name_is_rejected(
        self,
    ) -> None:
        """A literal run appears verbatim in every resolution, so a tab there is a
        certain §1.1.1 violation even though ``Param.S`` is unknown until job
        creation. 0.8.0 checks ``FormatString.literal_segments``; 0.7.1 also
        rejected this, by scanning the raw string, so this is a control."""
        template = _one_step_template(
            extensions=["EXPR"],
            name="a\t-{{ Param.S }}",
            parameterDefinitions=[{"name": "S", "type": "STRING"}],
        )
        with pytest.raises(ModelValidationError) as excinfo:
            decode_job_template(template=template, supported_extensions=["EXPR"])
        message = str(excinfo.value)
        assert "name:" in message
        assert "contains control characters." in message

    def test_interpolated_name_with_clean_literal_runs_is_accepted(self) -> None:
        """Control: what the expression resolves to is not this check's business."""
        template = _one_step_template(
            extensions=["EXPR"],
            name="a-{{ Param.S }}",
            parameterDefinitions=[{"name": "S", "type": "STRING"}],
        )
        assert decode_job_template(template=template, supported_extensions=["EXPR"])

    @staticmethod
    def _os_family_all_of(values: list[str]) -> dict[str, Any]:
        return _one_step_template(
            extensions=["EXPR"],
            parameterDefinitions=[{"name": "X", "type": "STRING"}],
            steps=[
                {
                    "name": "S",
                    "script": {"actions": {"onRun": {"command": "echo"}}},
                    "hostRequirements": {
                        "attributes": [{"name": "attr.worker.os.family", "allOf": values}]
                    },
                }
            ],
        )

    @pytest.mark.parametrize(
        "values",
        [
            pytest.param(["linux", "windows"], id="two literals"),
            pytest.param(["linux", "{{ Param.X }}-y"], id="literal and multi-segment"),
            pytest.param(["{{ Param.X }}-a", "{{ Param.X }}-b"], id="two multi-segment"),
        ],
    )
    def test_two_certain_allof_values_on_a_single_valued_attribute_are_rejected(
        self, values: list[str]
    ) -> None:
        """A host has one ``attr.worker.os.family`` (Template Schemas §3.3.2), so an
        ``allOf`` with two elements is unsatisfiable. An element is certain to be
        present when it is a literal or has more than one segment: a multi-segment
        format string always concatenates to one string (Expression Language §1.3.2).
        0.7.1 rejected all three shapes too; this is the control for the deferral
        test below."""
        with pytest.raises(ModelValidationError) as excinfo:
            decode_job_template(
                template=self._os_family_all_of(values), supported_extensions=["EXPR"]
            )
        message = str(excinfo.value)
        assert "steps[0] -> hostRequirements -> attributes[0] -> allOf" in message
        assert "single-valued attribute cannot have more than 1 element." in message

    def test_a_whole_field_expression_allof_element_is_deferred_to_job_creation(self) -> None:
        """Only a whole-field single-expression element can resolve to ``null`` and skip
        itself, so its contribution is unknowable at validation. 0.8.0 (openjd-rs#397)
        accepts the template here; 0.7.1 rejected it. Job creation re-checks the
        resolved count, so the constraint is deferred, not dropped."""
        template = self._os_family_all_of(["linux", "{{ Param.X }}"])
        assert decode_job_template(template=template, supported_extensions=["EXPR"])


class TestResolvedValueCapsAtTemplateValidation(object):
    """``max_resolved_arg_len`` and ``max_resolved_data_len`` cap the length of a
    resolved action ``command`` / argv entry (Template Schemas §5.1, §5.2) and of a
    resolved embedded-file ``data`` value (§6.1.2). The spec sets no maximum for
    either and defers to the operating system, so these are caller policy, not
    conformance rules. openjd-model 0.8.0 had no such fields — a caller could not
    express either cap — so every case here was accepted before the bump
    (openjd-rs#399).

    Validation checks the guaranteed lower bound of every possible resolution: a
    literal is exact, so it is rejected here, while a value that depends on a job
    parameter is only bounded by its literal runs and is deferred to job creation
    (see ``TestResolvedValueCapsAtJobCreation`` in ``test_create_job.py``).
    """

    @staticmethod
    def _template(action: dict[str, Any], embedded: Optional[list[dict[str, Any]]] = None) -> dict:
        script: dict[str, Any] = {"actions": {"onRun": action}}
        if embedded is not None:
            script["embeddedFiles"] = embedded
        return {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "T",
            "steps": [{"name": "S", "script": script}],
        }

    def test_literal_command_over_cap_is_rejected(self) -> None:
        template = self._template({"command": "a" * 20})
        with pytest.raises(ModelValidationError) as excinfo:
            decode_job_template(
                template=template,
                supported_extensions=[],
                caller_limits=CallerLimits(max_resolved_arg_len=5),
            )
        message = str(excinfo.value)
        assert "steps[0] -> script -> actions -> onRun -> command" in message
        assert "is 20 characters, exceeding the maximum of 5" in message

    def test_literal_arg_over_cap_is_rejected(self) -> None:
        """The cap applies per argv entry, not to the ``args`` list as a whole."""
        template = self._template({"command": "echo", "args": ["b" * 20]})
        with pytest.raises(ModelValidationError) as excinfo:
            decode_job_template(
                template=template,
                supported_extensions=[],
                caller_limits=CallerLimits(max_resolved_arg_len=5),
            )
        message = str(excinfo.value)
        assert "steps[0] -> script -> actions -> onRun -> args[0]" in message
        assert "is 20 characters, exceeding the maximum of 5" in message

    def test_command_under_cap_is_accepted(self) -> None:
        """Negative control: the same template passes under a cap it fits."""
        template = self._template({"command": "a" * 20, "args": ["b" * 20]})
        assert decode_job_template(
            template=template,
            supported_extensions=[],
            caller_limits=CallerLimits(max_resolved_arg_len=100),
        )

    def test_no_cap_accepts_any_length(self) -> None:
        """Negative control: omitting the cap imposes no limit, which is the only
        behaviour 0.8.0 had."""
        assert decode_job_template(
            template=self._template({"command": "a" * 20}), supported_extensions=[]
        )

    def test_embedded_file_data_over_cap_is_rejected(self) -> None:
        template = self._template(
            {"command": "echo"},
            embedded=[{"name": "F", "type": "TEXT", "data": "d" * 20}],
        )
        with pytest.raises(ModelValidationError) as excinfo:
            decode_job_template(
                template=template,
                supported_extensions=[],
                caller_limits=CallerLimits(max_resolved_data_len=5),
            )
        message = str(excinfo.value)
        assert "steps[0] -> script -> embeddedFiles[0] -> data" in message
        assert "is 20 characters, exceeding the maximum of 5" in message

    def test_embedded_file_data_under_cap_is_accepted(self) -> None:
        """Negative control, and it also pins that the two caps are independent: a
        20-character ``data`` passes while ``max_resolved_arg_len`` is 5."""
        template = self._template(
            {"command": "echo"},
            embedded=[{"name": "F", "type": "TEXT", "data": "d" * 20}],
        )
        assert decode_job_template(
            template=template,
            supported_extensions=[],
            caller_limits=CallerLimits(max_resolved_arg_len=5, max_resolved_data_len=100),
        )


class TestEvaluationBudgetsAtTemplateValidation(object):
    """``max_eval_memory_bytes`` and ``max_eval_operations`` are the Expression
    Language spec's memory-bounded-evaluation budgets (§1.3.9, §1.3.10), applied per
    format-string expression. Both have spec-recommended defaults (100 MB, 10
    million) rather than limits, so lowering them is configuration. openjd-model
    0.8.0 exposed no way to lower either (openjd-rs#399); the expression below was
    accepted.
    """

    @staticmethod
    def _template(expression: str) -> dict[str, Any]:
        return {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "T",
            "extensions": ["EXPR"],
            "steps": [
                {
                    "name": "S",
                    "script": {"actions": {"onRun": {"command": "echo", "args": [expression]}}},
                }
            ],
        }

    def test_memory_budget_rejects_a_large_value(self) -> None:
        with pytest.raises(ModelValidationError) as excinfo:
            decode_job_template(
                template=self._template("{{ 'a' * 100000 }}"),
                supported_extensions=["EXPR"],
                caller_limits=CallerLimits(max_eval_memory_bytes=1024),
            )
        assert "memory usage (100136 bytes) exceeded limit (1024 bytes)" in str(excinfo.value)

    def test_operation_budget_rejects_a_long_evaluation(self) -> None:
        with pytest.raises(ModelValidationError) as excinfo:
            decode_job_template(
                template=self._template("{{ 'a' * 100000 }}"),
                supported_extensions=["EXPR"],
                caller_limits=CallerLimits(max_eval_operations=5),
            )
        assert "operation count (392) exceeded limit (5)" in str(excinfo.value)

    def test_default_budgets_accept_it(self) -> None:
        """Negative control: the same expression is well within the spec-recommended
        defaults, so omitting the budgets accepts it."""
        assert decode_job_template(
            template=self._template("{{ 'a' * 100000 }}"), supported_extensions=["EXPR"]
        )


class TestEnvironmentTemplateCallerLimits(object):
    """``decode_environment_template`` gained a ``caller_limits`` argument with
    openjd-model 0.9.0 (openjd-rs#399); 0.8.0 took only the extension allowlist, and
    this package's docstrings said environment templates do not accept caller limits.
    The document-shape caps have no environment-template counterpart, but the
    resolved-value caps and evaluation budgets apply to its script the same way.
    """

    _TEMPLATE: dict[str, Any] = {
        "specificationVersion": "environment-2023-09",
        "environment": {
            "name": "E",
            "script": {"actions": {"onEnter": {"command": "e" * 20}}},
        },
    }

    def test_dict_entry_point_applies_the_cap(self) -> None:
        with pytest.raises(ModelValidationError) as excinfo:
            decode_environment_template(
                template=self._TEMPLATE,
                supported_extensions=[],
                caller_limits=CallerLimits(max_resolved_arg_len=5),
            )
        message = str(excinfo.value)
        assert "environment -> script -> actions -> onEnter -> command" in message
        assert "is 20 characters, exceeding the maximum of 5" in message

    def test_str_entry_point_applies_the_cap(self) -> None:
        document = json.dumps(self._TEMPLATE)
        with pytest.raises(ModelValidationError) as excinfo:
            decode_environment_template_str(
                document,
                DocumentType.JSON,
                supported_extensions=[],
                caller_limits=CallerLimits(max_resolved_arg_len=5),
            )
        assert "is 20 characters, exceeding the maximum of 5" in str(excinfo.value)

    def test_cap_that_fits_is_accepted(self) -> None:
        """Negative control on both entry points."""
        assert decode_environment_template(
            template=self._TEMPLATE,
            supported_extensions=[],
            caller_limits=CallerLimits(max_resolved_arg_len=100),
        )
        assert decode_environment_template_str(
            json.dumps(self._TEMPLATE), DocumentType.JSON, supported_extensions=[]
        )


class TestMaxTemplateSizeReachesTheParser(object):
    """``max_template_size`` is checked in one place only: the document-string parse
    in ``openjd_model::template::parse::document_string_to_object``, against the
    byte length before parsing.

    This binding's ``parse_string`` helper passed ``CallerLimits::default()`` there,
    so the field was inert on both ``*_str`` entry points even though they accept it
    — a caller asking for a 10-byte ceiling got no ceiling. Found while documenting
    the field, and fixed by passing the caller's own limits. The dict entry points
    are handed an already-parsed mapping and have no document string to measure, so
    they are unaffected either way.
    """

    _JOB = (
        "specificationVersion: jobtemplate-2023-09\n"
        "name: T\n"
        "steps:\n"
        "  - name: S\n"
        "    script:\n"
        "      actions:\n"
        "        onRun:\n"
        "          command: echo\n"
    )
    _ENV = (
        "specificationVersion: environment-2023-09\n"
        "environment:\n"
        "  name: E\n"
        "  script:\n"
        "    actions:\n"
        "      onEnter:\n"
        "        command: echo\n"
    )

    def test_job_template_str_over_the_limit_is_rejected(self) -> None:
        with pytest.raises(ModelValidationError) as excinfo:
            decode_job_template_str(
                self._JOB,
                supported_extensions=[],
                caller_limits=CallerLimits(max_template_size=10),
            )
        assert f"Template document size ({len(self._JOB)} bytes) exceeds caller limit of 10" in str(
            excinfo.value
        )

    def test_environment_template_str_over_the_limit_is_rejected(self) -> None:
        with pytest.raises(ModelValidationError) as excinfo:
            decode_environment_template_str(
                self._ENV,
                supported_extensions=[],
                caller_limits=CallerLimits(max_template_size=10),
            )
        assert f"Template document size ({len(self._ENV)} bytes) exceeds caller limit of 10" in str(
            excinfo.value
        )

    def test_a_limit_the_document_fits_is_accepted(self) -> None:
        """Negative control: the check is a ceiling, not a rejection of the field."""
        assert decode_job_template_str(
            self._JOB,
            supported_extensions=[],
            caller_limits=CallerLimits(max_template_size=len(self._JOB)),
        )
        assert decode_environment_template_str(
            self._ENV,
            supported_extensions=[],
            caller_limits=CallerLimits(max_template_size=len(self._ENV)),
        )

    def test_the_dict_entry_points_have_nothing_to_measure(self) -> None:
        """The same limit on a dict entry point is inert by construction — there is no
        document string — so the template is accepted. Pins the asymmetry the
        docstrings now state, so a future change that starts re-encoding the dict to
        measure it has to update both."""
        template = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "T",
            "steps": [{"name": "S", "script": {"actions": {"onRun": {"command": "echo"}}}}],
        }
        assert decode_job_template(
            template=template,
            supported_extensions=[],
            caller_limits=CallerLimits(max_template_size=10),
        )
