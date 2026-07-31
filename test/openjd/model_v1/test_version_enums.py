# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest

from openjd.model._v1 import TemplateSpecificationVersion, decode_job_template
from openjd.model._v1.types import ModelExtension
from openjd.model.v2023_09 import ExtensionName

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


def _rust_extension_members() -> set[str]:
    # `ModelExtension` is a PyO3 pyclass enum, not a real `enum.Enum`, so
    # it is not iterable. Discover members by identity instead of relying
    # on the enum protocol or a hardcoded list.
    return {
        name
        for name in dir(ModelExtension)
        if isinstance(getattr(ModelExtension, name), ModelExtension)
    }


class TestModelExtension:
    """Drift guard for the `ModelExtension` PyO3 binding.

    `openjd_model::types::ModelExtension` is `#[non_exhaustive]`, so
    `From<ModelExtension> for PyModelExtension` must carry a catch-all
    arm and the compiler cannot warn when the Rust crate gains a variant
    the binding does not map. These tests are that warning.

    Regression: `WRAP_ACTIONS` landed in the Rust crate six days after
    the binding was written; the binding was never updated, so the
    catch-all silently mapped it to `EXPR`. A profile built with
    `WRAP_ACTIONS` therefore enabled `EXPR` instead, and templates using
    `onWrapEnvEnter`/`onWrapTaskRun`/`onWrapEnvExit` were rejected with
    an error that did not name the real cause.
    """

    def test_binding_members_match_python_extension_names(self) -> None:
        # The binding enum and the Python model layer describe the same
        # set of 2023-09 extensions. Divergence in either direction is a
        # bug: a missing member means the catch-all aliases it to the
        # wrong extension; an extra member means Python cannot name it.
        assert _rust_extension_members() == {e.value for e in ExtensionName}

    @pytest.mark.parametrize("name", [e.value for e in ExtensionName])
    def test_name_round_trips_to_its_own_member(self, name: str) -> None:
        # Catches aliasing directly, independent of member-set equality:
        # every spec name must parse back to the member of the same name,
        # never to a different extension.
        parsed = ModelExtension.from_str(name)
        assert parsed is not None, f"{name} is not recognized by the Rust binding"
        assert parsed.name == name
        assert parsed.as_str() == name
