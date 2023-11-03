# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest

from openjd.model import SchemaVersion


class TestSchemaVersion:
    def test_all_values_classified(self) -> None:
        # Testing that all of the values, except for UNDEFINED, is returned in one of the version
        # getter staticmethods. This ensures that the getters are updated when new schema versions are
        # added.

        # GIVEN
        defined_versions = set(v for v in SchemaVersion) - set((SchemaVersion.UNDEFINED,))
        job_template_versions = set(v for v in SchemaVersion.job_template_versions())
        env_template_versions = set(v for v in SchemaVersion.environment_template_versions())

        # THEN
        assert len(job_template_versions.intersection(env_template_versions)) == 0
        assert (job_template_versions | env_template_versions) == defined_versions

    @pytest.mark.parametrize("version", SchemaVersion.job_template_versions())
    def test_job_template_versions(self, version: SchemaVersion) -> None:
        # Test that is_job_template() correctly identifies all versions that are job template versions.
        # THEN
        assert SchemaVersion.is_job_template(version)

    @pytest.mark.parametrize(
        "version",
        sorted(list(set(v for v in SchemaVersion) - set(SchemaVersion.job_template_versions()))),
    )
    def test_not_job_template_versions(self, version: SchemaVersion) -> None:
        # Test that is_job_template() correctly identifies all versions that are job template versions.
        # THEN
        assert not SchemaVersion.is_job_template(version)

    @pytest.mark.parametrize("version", SchemaVersion.environment_template_versions())
    def test_environment_template_versions(self, version: SchemaVersion) -> None:
        # Test that is_environment_template() correctly identifies all versions that are environment template versions.
        # THEN
        assert SchemaVersion.is_environment_template(version)

    @pytest.mark.parametrize(
        "version",
        sorted(
            list(set(v for v in SchemaVersion) - set(SchemaVersion.environment_template_versions()))
        ),
    )
    def test_not_environment_template_versions(self, version: SchemaVersion) -> None:
        # Test that is_environment_template() correctly identifies all versions that are environment template versions.
        # THEN
        assert not SchemaVersion.is_environment_template(version)
