# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.


def test_openjd_importable():
    import openjd  # noqa: F401


def test_openjd_model_importable():
    import openjd.model._v1  # noqa: F401


def test_top_level_error_classes_not_re_exported():
    """``DecodeValidationError``, ``ModelValidationError``, and
    ``UnsupportedSchema`` are deliberately *not* re-exported at the
    top of ``openjd.model._v1`` — their canonical home is
    ``openjd.model._v1.errors``. (See the v1-surface cleanup commit:
    structural and exception types live in their submodules; the
    top-level package re-exports only entry points and the
    ``SpecificationRevision`` / ``TemplateSpecificationVersion``
    pyclass enums.)"""
    import openjd.model._v1 as v1

    # None of the three appear in __all__.
    assert "DecodeValidationError" not in v1.__all__
    assert "ModelValidationError" not in v1.__all__
    assert "UnsupportedSchema" not in v1.__all__

    # Canonical location resolves; identity check ensures we're
    # talking about the Rust-pyclass classes (re-exported from
    # ``openjd._openjd_rs``) rather than name-shadowed Python
    # placeholders.
    from openjd.model._v1 import errors
    from openjd._openjd_rs import (
        DecodeValidationError as _RsDecodeValidationError,
        ModelValidationError as _RsModelValidationError,
        UnsupportedSchema as _RsUnsupportedSchema,
    )

    assert errors.DecodeValidationError is _RsDecodeValidationError
    assert errors.ModelValidationError is _RsModelValidationError
    assert errors.UnsupportedSchema is _RsUnsupportedSchema
