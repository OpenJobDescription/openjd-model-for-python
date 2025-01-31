# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
from typing_extensions import Self

from pydantic import BaseModel, Field, model_validator
from pydantic_core import ErrorDetails
from typing import Literal, Union

from openjd.model._convert_pydantic_error import (
    pydantic_validationerrors_to_str,
    _error_dict_to_str,
)


class TestValidationErrorsToStr:
    def test(self) -> None:
        # Just making sure that pydantic_validationerrors_to_str()
        # prints out all of the given errors.

        # GIVEN
        class Model(BaseModel):
            f1: str
            f2: int

        errors: list[ErrorDetails] = [
            {
                "loc": ("f1",),
                "msg": "error message1",
                "type": "error-type",
                "input": "input-value1",
            },
            {
                "loc": ("f2",),
                "msg": "error message2",
                "type": "error-type",
                "input": "input-value2",
            },
        ]
        expected = "2 validation errors for Model\nf1:\n\terror message1\nf2:\n\terror message2"

        # WHEN
        result = pydantic_validationerrors_to_str(Model, errors)

        # THEN
        assert result == expected


class TestSimpleModels:
    """Tests of converting validation errors from "simple" models. These
    are models that contain no sequence types or unions as field types.
    """

    def test_single_level(self) -> None:
        # Make sure that our path to error is correct for a single-level
        # error

        # GIVEN
        class Model(BaseModel):
            f1: str
            f2: int

        error: ErrorDetails = {
            "loc": ("f2",),
            "msg": "error message",
            "type": "error-type",
            "input": "input-value",
        }
        expected = "f2:\n\terror message"

        # WHEN
        result = _error_dict_to_str(Model, error)

        # THEN
        assert result == expected

    def test_nesting_level(self) -> None:
        # Make sure that our path to error is correct for a multi-level
        # error

        # GIVEN
        class Inner(BaseModel):
            ff: str

        class Model(BaseModel):
            inner: Inner

        error: ErrorDetails = {
            "loc": (
                "inner",
                "ff",
            ),
            "msg": "error message",
            "type": "error-type",
            "input": "input-value",
        }
        expected = "inner -> ff:\n\terror message"

        # WHEN
        result = _error_dict_to_str(Model, error)

        # THEN
        assert result == expected

    def test_base_model_validator_error(self) -> None:
        # Make sure that our path to error is correct for validation error
        # at the base level's root validator
        # This is a special case where we do not want the error message to be indented
        # at all. This conveys that the error is not nested.
        # Errors raised by a root validator have a special "__root__" field name

        # GIVEN
        class Model(BaseModel):
            ff: str

            @model_validator(mode="after")
            def _validate(self) -> Self:
                raise ValueError("error message")

        error: ErrorDetails = {
            "loc": ("__root__",),
            "msg": "error message",
            "type": "error-type",
            "input": "input-value",
        }
        expected = "Model: error message"

        # WHEN
        result = _error_dict_to_str(Model, error)

        # THEN
        assert result == expected

    def test_inner_model_validator_error(self) -> None:
        # Make sure that our path to error is correct for validation error
        # at a nested level's root validator.
        # In this case we drop the '__root__' field at the end and report the error
        # as being for the field one level up.
        # Errors raised by a root validator have a special "__root__" field name

        # GIVEN
        class Inner(BaseModel):
            ff: str

            @model_validator(mode="after")
            def _validate(self) -> Self:
                raise ValueError("error message")

        class Model(BaseModel):
            inner: Inner

        error: ErrorDetails = {
            "loc": (
                "inner",
                "__root__",
            ),
            "msg": "error message",
            "type": "error-type",
            "input": "input-value",
        }
        expected = "inner:\n\terror message"

        # WHEN
        result = _error_dict_to_str(Model, error)

        # THEN
        assert result == expected


class TestArrayFields:
    """Testing that we print the locations of errors correctly when there are array
    fields in the model.
    """

    def test_scalar(self) -> None:
        # Test the case where there's an error in one of the elements of
        # a scalar array (e.g. its the wrong type)

        # GIVEN
        class Model(BaseModel):
            field: list[int]

        error: ErrorDetails = {
            "loc": (
                "field",
                2,
            ),
            "msg": "error message",
            "type": "error-type",
            "input": "input-value",
        }
        expected = "field[2]:\n\terror message"

        # WHEN
        result = _error_dict_to_str(Model, error)

        # THEN
        assert result == expected

    def test_inner_model(self) -> None:
        # Test the case where there's an error in one of the elements of
        # an array of models

        # GIVEN
        class Inner(BaseModel):
            ff: int

        class Model(BaseModel):
            inner: list[Inner]

        error: ErrorDetails = {
            "loc": (
                "inner",
                2,
                "ff",
            ),
            "msg": "error message",
            "type": "error-type",
            "input": "input-value",
        }
        expected = "inner[2] -> ff:\n\terror message"

        # WHEN
        result = _error_dict_to_str(Model, error)

        # THEN
        assert result == expected


# Due to the nature of how we defermine locations with discriminated unions,
# these classes *must* be defined in the module.
class UnionInner1(BaseModel):
    type: Literal["Inner1"]
    ff: int


class UnionInner2(BaseModel):
    type: Literal["Inner2"]
    ff: str


class UnionModel(BaseModel):
    inner: Union[UnionInner1, UnionInner2] = Field(..., discriminator="type")


class TestDiscriminatedUnion:
    """Testing that the location is correct in the presence of a discriminated union.
    When an error is through a discriminated union, pydantic will include the name
    of the union class type that contains the error as one of the location elements.
    """

    def test(self) -> None:
        # GIVEN
        error: ErrorDetails = {
            "loc": (
                "inner",
                2,
                "UnionInner1",
                "ff",
            ),
            "msg": "error message",
            "type": "error-type",
            "input": "input-value",
        }
        expected = "inner[2] -> ff:\n\terror message"

        # WHEN
        result = _error_dict_to_str(UnionModel, error)

        # THEN
        assert result == expected
