# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

from typing import Optional
from openjd.model.v2023_09._model import OpenJDModel_v2023_09


# First define a class we'll reference properly
class ReferencedClass(OpenJDModel_v2023_09):
    value: str


class ClassWithoutForwardRef(OpenJDModel_v2023_09):
    # This won't create a ForwardRef since ReferencedClass is already defined
    ref: ReferencedClass


# Now try to reference a class before it's defined, like we did in _model.py
class ClassWithForwardRef(OpenJDModel_v2023_09):
    # This should create a ForwardRef since SecondReferencedClass isn't defined yet
    ref: Optional[SecondReferencedClass] = None


# Define the class after it's referenced
class SecondReferencedClass(OpenJDModel_v2023_09):
    value: str
