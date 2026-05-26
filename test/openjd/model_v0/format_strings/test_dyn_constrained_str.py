# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import re

import pytest
from pydantic import BaseModel, ValidationError

from openjd.model._format_strings._dyn_constrained_str import DynamicConstrainedStr
from openjd.model.v2023_09 import ModelParsingContext as ModelParsingContext_v2023_09


class TestDyanamicConstrainedStr:
    def test_no_constraints(self) -> None:
        # Ensure that the validators correctly implement
        # having no constraint applied.

        # GIVEN
        class Model(BaseModel):
            s: DynamicConstrainedStr

        # WHEN
        Model.model_validate({"s": "123"}, context=ModelParsingContext_v2023_09())

        # THEN
        # raised no error

    def test_encodes_as_str(self) -> None:
        # Make sure that none of the constraint fields like
        # _min_length get output when encoding a Model

        # GIVEN
        class Model(BaseModel):
            s: DynamicConstrainedStr

        model = Model.model_validate({"s": "12"}, context=ModelParsingContext_v2023_09())

        # WHEN
        as_dict = model.model_dump()

        # THEN
        assert as_dict == {"s": "12"}

    def test_no_type_coersion(self) -> None:
        # Ensure that non-strings aren't converted into strings.

        # GIVEN
        class Model(BaseModel):
            s: DynamicConstrainedStr

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            Model.model_validate({"s": 123}, context=ModelParsingContext_v2023_09())

        # THEN
        assert len(excinfo.value.errors()) == 1

    def test_min_length_success(self) -> None:
        # Make sure that strings that are long enough pass validation

        # GIVEN
        class StrType(DynamicConstrainedStr):
            _min_length = 10

        class Model(BaseModel):
            s: StrType

        # WHEN
        Model.model_validate({"s": "0" * 10}, context=ModelParsingContext_v2023_09())

        # THEN
        # raised no error

    def test_too_short(self) -> None:
        # Make sure that strings that are too short fail validation

        # GIVEN
        class StrType(DynamicConstrainedStr):
            _min_length = 10

        class Model(BaseModel):
            s: StrType

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            Model.model_validate({"s": "0" * 9}, context=ModelParsingContext_v2023_09())

        # THEN
        assert len(excinfo.value.errors()) == 1

    def test_max_length_success(self) -> None:
        # Make sure that strings that are long enough pass validation

        # GIVEN
        class StrType(DynamicConstrainedStr):
            _max_length = 10

        class Model(BaseModel):
            s: StrType

        # WHEN
        Model.model_validate({"s": "0" * 10}, context=ModelParsingContext_v2023_09())

        # THEN
        # raised no error

    def test_too_long(self) -> None:
        # Make sure that strings that are too short fail validation

        # GIVEN
        class StrType(DynamicConstrainedStr):
            _max_length = 10

        class Model(BaseModel):
            s: StrType

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            Model.model_validate({"s": "0" * 11}, context=ModelParsingContext_v2023_09())

        # THEN
        assert len(excinfo.value.errors()) == 1

    def test_regex_match_str(self) -> None:
        # Test a string that matches a regex defined as a string

        # GIVEN
        class StrType(DynamicConstrainedStr):
            _regex = r"0+"

        class Model(BaseModel):
            s: StrType

        # WHEN
        Model.model_validate({"s": "0" * 10}, context=ModelParsingContext_v2023_09())

        # THEN
        # no errors raised

    def test_regex_fail_str(self) -> None:
        # Test a string that does not validate against a regex defined as a string

        # GIVEN
        class StrType(DynamicConstrainedStr):
            _regex = r"0+"

        class Model(BaseModel):
            s: StrType

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            Model.model_validate({"s": "1" * 10}, context=ModelParsingContext_v2023_09())

        # THEN
        assert len(excinfo.value.errors()) == 1

    def test_regex_match(self) -> None:
        # Test a string that matches a regex defined as a compiled regex

        # GIVEN
        class StrType(DynamicConstrainedStr):
            _regex = re.compile(r"0+")

        class Model(BaseModel):
            s: StrType

        # WHEN
        Model.model_validate({"s": "0" * 10}, context=ModelParsingContext_v2023_09())

        # THEN
        # no errors raised

    def test_regex_fail(self) -> None:
        # Test a string that does not validate against a regex defined as a compiled regex

        # GIVEN
        class StrType(DynamicConstrainedStr):
            _regex = re.compile(r"0+")

        class Model(BaseModel):
            s: StrType

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            Model.model_validate({"s": "1" * 10}, context=ModelParsingContext_v2023_09())

        # THEN
        assert len(excinfo.value.errors()) == 1

    def test_get_json_schema(self) -> None:
        # GIVEN
        class StrType(DynamicConstrainedStr):
            _min_length = 10
            _regex = re.compile(r"0+")

            @classmethod
            def _max_length(cls):
                return 20

        class Model(BaseModel):
            s: StrType

        # WHEN
        schema = Model.model_json_schema()

        # THEN
        assert schema == {
            "title": "Model",
            "type": "object",
            "properties": {
                "s": {
                    "title": "S",
                    "type": "string",
                    "minLength": 10,
                    "maxLength": 20,
                    "pattern": "0+",
                }
            },
            "required": ["s"],
        }
