# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.


def test_openjd_importable():
    import openjd  # noqa: F401


def test_openjd_model_importable():
    import openjd.model._v1  # noqa: F401


def test_top_level_error_classes_re_exported():
    """``DecodeValidationError``, ``ModelValidationError``, and
    ``UnsupportedSchema`` are all importable from the top level
    (in addition to their canonical home under
    ``openjd.model._v1.errors``). The three classes are re-exported
    as a convenience because they appear directly in user code that
    catches decode/validation failures."""
    from openjd.model._v1 import (
        DecodeValidationError,
        ModelValidationError,
        UnsupportedSchema,
    )
    from openjd.model._v1 import errors

    # Identity: the top-level re-exports must be the same class
    # objects as those in the .errors submodule. Catching the
    # top-level form must catch the .errors form (and vice versa).
    assert DecodeValidationError is errors.DecodeValidationError
    assert ModelValidationError is errors.ModelValidationError
    assert UnsupportedSchema is errors.UnsupportedSchema

    # All three appear in __all__.
    import openjd.model._v1 as v1

    assert "DecodeValidationError" in v1.__all__
    assert "ModelValidationError" in v1.__all__
    assert "UnsupportedSchema" in v1.__all__
