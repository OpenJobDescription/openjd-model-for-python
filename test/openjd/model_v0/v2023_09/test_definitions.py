# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest
from pydantic import BaseModel
from typing import Type, ForwardRef
import openjd.model.v2023_09 as mod
from inspect import getmembers, getmodule, isclass


from .test_module import ClassWithForwardRef, ClassWithoutForwardRef

ALL_MODELS = sorted(
    [obj for name, obj in getmembers(mod) if isclass(obj) and issubclass(obj, BaseModel)],
    key=lambda o: o.__name__,
)


def test_forward_ref_detection():
    """Test that our ForwardRef detection works by checking classes that use ForwardRefs vs direct references."""
    # When referencing a class that's already defined, no ForwardRef is created
    field = ClassWithoutForwardRef.model_fields["ref"]
    assert not isinstance(field.annotation, ForwardRef), (
        "Expected ClassWithoutForwardRef.ref to NOT be a ForwardRef since ReferencedClass "
        "is defined before it's used"
    )

    # When referencing a class that's defined later, a ForwardRef is created
    field = ClassWithForwardRef.model_fields["ref"]
    assert isinstance(field.annotation, ForwardRef), (
        "Expected ClassWithForwardRef.ref to be a ForwardRef since SecondReferencedClass "
        "is defined after it's used"
    )


@pytest.mark.parametrize("model", ALL_MODELS)
def test_models_in_same_module(model: Type[BaseModel]) -> None:
    # For our error reporting of discriminated union fields to be correctly reported
    # we require that *all* of the models are defined in exactly the same module as the JobTemplate
    # model.
    # This is to identify when a name in an error location is actually a class name from
    # a typed union.
    assert getmodule(mod.JobTemplate) == getmodule(model)


@pytest.mark.parametrize("model", ALL_MODELS)
def test_no_forward_refs_in_models(model: Type[BaseModel]) -> None:
    """Test that no models in _model.py use ForwardRefs in their field annotations.

    ForwardRefs indicate that a type is being referenced before it's defined, which can lead
    to issues in pydantic validation. This test ensures all types are properly defined before
    they're used.
    """
    for field_name, field in model.model_fields.items():
        assert not isinstance(field.annotation, ForwardRef), (
            f"Field '{field_name}' in model '{model.__name__}' uses a ForwardRef. "
            "The referenced type should be defined before it's used."
        )
