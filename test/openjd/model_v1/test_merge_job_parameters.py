# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest
from typing import Any, Optional

from openjd.model._v1 import (
    decode_environment_template,
    decode_job_template,
    merge_job_parameter_definitions,
)
from openjd.model._v1.template import (
    EnvironmentTemplate,
    JobTemplate,
)

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
                decode_job_template(
                    template={
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
                    {"name": "Foo", "type": "INT", "source": "JobTemplate"},
                    {"name": "Bar", "type": "STRING", "source": "JobTemplate"},
                ],
                id="only job template",
            ),
            pytest.param(
                decode_job_template(
                    template={
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
                    decode_environment_template(
                        template={
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
                    decode_environment_template(
                        template={
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
                    {"name": "Foo", "type": "INT", "default": 8, "source": "JobTemplate"},
                    {
                        "name": "Bar",
                        "type": "STRING",
                        "default": "b" * 25,
                        "source": "JobTemplate",
                    },
                ],
                id="merging environments and job template - job template default wins",
            ),
            pytest.param(
                decode_job_template(
                    template={
                        "specificationVersion": "jobtemplate-2023-09",
                        "name": "Job",
                        "parameterDefinitions": [
                            {"name": "Foo", "type": "INT"},
                        ],
                        "steps": [BASIC_JOB_TEMPLATE_STEP_2023_09],
                    },
                ),
                [
                    decode_environment_template(
                        template={
                            "specificationVersion": "environment-2023-09",
                            "parameterDefinitions": [
                                {"name": "Foo", "type": "INT", "default": 42},
                            ],
                            "environment": {
                                "name": "Env1",
                                **BASIC_ENVIRONMENT_TEMPLATE_ACTION_2023_09,
                            },
                        },
                    ),
                ],
                [
                    {"name": "Foo", "type": "INT", "default": 42, "source": "JobTemplate"},
                ],
                id="environment default propagates when job template has none",
            ),
        ],
    )
    def test_success(
        self,
        given_job_template: JobTemplate,
        given_envs: Optional[list[EnvironmentTemplate]],
        expected: list[dict[str, Any]],
    ) -> None:
        # WHEN
        result = merge_job_parameter_definitions(
            job_template=given_job_template, environment_templates=given_envs
        )

        # THEN
        # Compare as sets of frozen items for order-agnostic comparison
        def _to_comparable(param_list):
            return {tuple(sorted(p.items())) for p in param_list}

        assert _to_comparable(result) == _to_comparable(expected)


class TestMergeDefaultNativeTypes:
    """``merge_job_parameter_definitions`` emits ``default`` in the
    parameter's native Python type — ``int`` for ``INT``, ``float`` for
    ``FLOAT``, ``bool`` for ``BOOL``, ``list[T]`` for the ``LIST[*]``
    variants, and ``str`` for ``STRING`` / ``PATH`` / ``RANGE_EXPR``.

    Pinned per `specs/python-model-interface.md`'s
    ``merge_job_parameter_definitions`` "Return shape" key list and the
    AGENTS.md "Test Quality Standard" guidance (assertions on type
    identity, not just equality, since ``5 == 5.0`` would otherwise
    let a regression slip through)."""

    @staticmethod
    def _merge_one(*, param_type: str, default: Any, **extra: Any) -> dict[str, Any]:
        # The EXPR-extension parameter types (BOOL, RANGE_EXPR,
        # LIST[*]) require the template to opt into the EXPR extension
        # both in its body and via supported_extensions. The base
        # STRING/INT/FLOAT/PATH variants are unaffected.
        t = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "T",
                "extensions": ["EXPR"],
                "parameterDefinitions": [
                    {"name": "P", "type": param_type, "default": default, **extra},
                ],
                "steps": [BASIC_JOB_TEMPLATE_STEP_2023_09],
            },
            supported_extensions=["EXPR"],
        )
        merged = merge_job_parameter_definitions(job_template=t)
        assert len(merged) == 1
        return merged[0]

    def test_int(self) -> None:
        m = self._merge_one(param_type="INT", default=5)
        assert m["default"] == 5
        assert isinstance(m["default"], int)

    def test_float(self) -> None:
        m = self._merge_one(param_type="FLOAT", default=3.14)
        assert m["default"] == 3.14
        assert isinstance(m["default"], float)

    def test_string(self) -> None:
        m = self._merge_one(param_type="STRING", default="hello")
        assert m["default"] == "hello"
        assert isinstance(m["default"], str)

    def test_path(self) -> None:
        m = self._merge_one(param_type="PATH", default="/tmp/out")
        assert m["default"] == "/tmp/out"
        assert isinstance(m["default"], str)

    def test_bool(self) -> None:
        m = self._merge_one(param_type="BOOL", default=True)
        assert m["default"] is True

    def test_list_int(self) -> None:
        m = self._merge_one(param_type="LIST[INT]", default=[1, 2, 3])
        assert m["default"] == [1, 2, 3]
        assert isinstance(m["default"], list)
        assert all(isinstance(v, int) and not isinstance(v, bool) for v in m["default"])

    def test_list_float(self) -> None:
        m = self._merge_one(param_type="LIST[FLOAT]", default=[1.5, 2.5])
        assert m["default"] == [1.5, 2.5]
        assert all(isinstance(v, float) for v in m["default"])

    def test_list_string(self) -> None:
        m = self._merge_one(param_type="LIST[STRING]", default=["a", "b"])
        assert m["default"] == ["a", "b"]
        assert all(isinstance(v, str) for v in m["default"])

    def test_list_bool(self) -> None:
        m = self._merge_one(param_type="LIST[BOOL]", default=[True, False])
        assert m["default"] == [True, False]
        assert all(isinstance(v, bool) for v in m["default"])

    def test_list_list_int(self) -> None:
        m = self._merge_one(param_type="LIST[LIST[INT]]", default=[[1, 2], [3, 4]])
        assert m["default"] == [[1, 2], [3, 4]]
        assert isinstance(m["default"], list)
        assert all(
            isinstance(inner, list) and all(isinstance(v, int) for v in inner)
            for inner in m["default"]
        )


class TestMergeDescriptionPropagation:
    """``merge_job_parameter_definitions`` propagates the per-parameter
    ``description`` from the originating template onto each merged
    dict, mirroring how ``default`` is carried.

    The upstream ``MergedParameterDefinition`` struct does not surface
    a description field — only ``name`` / ``param_type`` / ``default``
    / ``object_type`` / ``data_flow`` / ``source`` / merged
    constraints. The binding recovers it by walking the same template
    sources the merge walked (environment templates in order, then the
    job template), with later-defined descriptions overwriting earlier
    ones (matching how ``default`` is tracked upstream).

    The ``description`` key is **only** present when at least one
    contributing template provided one; templates without a
    ``description`` produce a dict that does not carry the key (vs.
    carrying ``None``)."""

    def test_description_from_job_template(self) -> None:
        t = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "T",
                "parameterDefinitions": [
                    {
                        "name": "Count",
                        "type": "INT",
                        "default": 5,
                        "description": "Number of frames",
                    },
                ],
                "steps": [BASIC_JOB_TEMPLATE_STEP_2023_09],
            }
        )
        [m] = merge_job_parameter_definitions(job_template=t)
        assert m["description"] == "Number of frames"

    def test_description_from_environment_template(self) -> None:
        t = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "T",
                "parameterDefinitions": [
                    {"name": "Count", "type": "INT", "default": 5},
                ],
                "steps": [BASIC_JOB_TEMPLATE_STEP_2023_09],
            }
        )
        env = decode_environment_template(
            template={
                "specificationVersion": "environment-2023-09",
                "parameterDefinitions": [
                    {"name": "Count", "type": "INT", "description": "env description"},
                ],
                "environment": {"name": "E", **BASIC_ENVIRONMENT_TEMPLATE_ACTION_2023_09},
            }
        )
        [m] = merge_job_parameter_definitions(job_template=t, environment_templates=[env])
        assert m["description"] == "env description"

    def test_job_template_description_overrides_environment(self) -> None:
        # When both an env template and the job template provide a
        # description, the job template's wins (it's walked last;
        # matches how ``default`` is tracked).
        t = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "T",
                "parameterDefinitions": [
                    {
                        "name": "Count",
                        "type": "INT",
                        "default": 5,
                        "description": "from job template",
                    },
                ],
                "steps": [BASIC_JOB_TEMPLATE_STEP_2023_09],
            }
        )
        env = decode_environment_template(
            template={
                "specificationVersion": "environment-2023-09",
                "parameterDefinitions": [
                    {"name": "Count", "type": "INT", "description": "from env template"},
                ],
                "environment": {"name": "E", **BASIC_ENVIRONMENT_TEMPLATE_ACTION_2023_09},
            }
        )
        [m] = merge_job_parameter_definitions(job_template=t, environment_templates=[env])
        assert m["description"] == "from job template"

    def test_later_environment_description_overrides_earlier(self) -> None:
        # When two env templates both provide a description (and the
        # job template doesn't), the later one wins.
        t = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "T",
                "parameterDefinitions": [
                    {"name": "Count", "type": "INT", "default": 5},
                ],
                "steps": [BASIC_JOB_TEMPLATE_STEP_2023_09],
            }
        )
        env1 = decode_environment_template(
            template={
                "specificationVersion": "environment-2023-09",
                "parameterDefinitions": [
                    {"name": "Count", "type": "INT", "description": "from env1"},
                ],
                "environment": {"name": "E1", **BASIC_ENVIRONMENT_TEMPLATE_ACTION_2023_09},
            }
        )
        env2 = decode_environment_template(
            template={
                "specificationVersion": "environment-2023-09",
                "parameterDefinitions": [
                    {"name": "Count", "type": "INT", "description": "from env2"},
                ],
                "environment": {"name": "E2", **BASIC_ENVIRONMENT_TEMPLATE_ACTION_2023_09},
            }
        )
        [m] = merge_job_parameter_definitions(job_template=t, environment_templates=[env1, env2])
        assert m["description"] == "from env2"

    def test_no_description_means_key_absent(self) -> None:
        # When no contributing template provides a description, the
        # ``description`` key is omitted from the merged dict (not
        # carried as ``None``). Consistent with how ``default`` /
        # ``objectType`` / ``dataFlow`` are conditionally emitted.
        t = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "T",
                "parameterDefinitions": [
                    {"name": "Count", "type": "INT", "default": 5},
                ],
                "steps": [BASIC_JOB_TEMPLATE_STEP_2023_09],
            }
        )
        [m] = merge_job_parameter_definitions(job_template=t)
        assert "description" not in m
