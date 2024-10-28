# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest
from pydantic.v1 import BaseModel
from typing import Type
import openjd.model.v2023_09 as mod
from inspect import getmembers, getmodule, isclass


ALL_MODELS = sorted(
    [obj for name, obj in getmembers(mod) if isclass(obj) and issubclass(obj, BaseModel)],
    key=lambda o: o.__name__,
)


@pytest.mark.parametrize("model", ALL_MODELS)
def test_models_in_same_module(model: Type[BaseModel]) -> None:
    # For our error reporting of discriminated union fields to be correctly reported
    # we require that *all* of the models are defined in exactly the same module as the JobTemplate
    # model.
    # This is to identify when a name in an error location is actually a class name from
    # a typed union.
    assert getmodule(mod.JobTemplate) == getmodule(model)
