# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest

from openjd.model._v1 import TemplateSpecificationVersion, decode_job_template


# All known variants. Add new ones here as the spec evolves; the test
# ensures every variant is classified as exactly job-template OR
# environment-template, never both.
ALL_VERSIONS = (
    TemplateSpecificationVersion.JOBTEMPLATE_v2023_09,
    TemplateSpecificationVersion.ENVIRONMENT_v2023_09,
)


class TestTemplateSpecificationVersion:
    def test_classification_is_exclusive(self) -> None:
        # Every variant is exactly one of: job template, environment
        # template. Never neither, never both.
        for v in ALL_VERSIONS:
            assert v.is_job_template() != v.is_environment_template()

    @pytest.mark.parametrize("version", [TemplateSpecificationVersion.JOBTEMPLATE_v2023_09])
    def test_job_template_versions(self, version: TemplateSpecificationVersion) -> None:
        assert version.is_job_template()
        assert not version.is_environment_template()

    @pytest.mark.parametrize("version", [TemplateSpecificationVersion.ENVIRONMENT_v2023_09])
    def test_environment_template_versions(self, version: TemplateSpecificationVersion) -> None:
        assert version.is_environment_template()
        assert not version.is_job_template()

    def test_template_specification_version_returned_from_decode(self) -> None:
        # ``JobTemplate.specification_version`` returns an instance of
        # the same ``TemplateSpecificationVersion`` class that
        # ``openjd.model._v1`` re-exports — i.e. there is exactly one
        # class, the Rust pyclass at ``openjd._openjd_rs``, and the
        # comparison ``template.specification_version ==
        # TemplateSpecificationVersion.JOBTEMPLATE_v2023_09`` works as
        # written without any str-Enum shim. Regression test for the
        # historical gap where ``JobTemplate.specification_version``
        # returned the Rust pyclass but the public-name
        # ``TemplateSpecificationVersion`` was a separate Python
        # ``str``-Enum, so the natural-looking equality silently
        # returned ``False``.
        t = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "T",
                "steps": [{"name": "S", "script": {"actions": {"onRun": {"command": "echo"}}}}],
            }
        )
        assert t.specification_version == TemplateSpecificationVersion.JOBTEMPLATE_v2023_09
        assert type(t.specification_version) is TemplateSpecificationVersion
        # Equality is symmetric with the spec-form string (str-Enum-
        # like behaviour without being a str subclass).
        assert t.specification_version == "jobtemplate-2023-09"
        assert t.specification_version.value == "jobtemplate-2023-09"
