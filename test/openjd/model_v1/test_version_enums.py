# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest

from openjd.model._v1 import TemplateSpecificationVersion


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
