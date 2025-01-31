# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any, Callable, Optional, Pattern, Union

from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema
import re


class DynamicConstrainedStr(str):
    """Constrained string type for interfacing with Pydantic.
    The maximum string length can be dynamically defined at runtime.

    Note: Does *not* run model validation when constructed.
    """

    _min_length: Optional[int] = None
    _max_length: Optional[Union[int, Callable[[], int]]] = None
    _regex: Optional[Union[str, Pattern[str]]] = None

    # Pydantic datamodel interfaces
    # ================================
    # Reference: https://pydantic-docs.helpmanual.io/usage/types/#custom-data-types

    @classmethod
    def _get_max_length(cls) -> Optional[int]:
        if callable(cls._max_length):
            return cls._max_length()
        return cls._max_length

    @classmethod
    def _validate(cls, value: str) -> Any:
        if not isinstance(value, str):
            raise ValueError("String required")

        if cls._min_length is not None and len(value) < cls._min_length:
            raise ValueError(f"String must be at least {cls._min_length} characters long")
        max_length = cls._get_max_length()

        if max_length is not None and len(value) > max_length:
            raise ValueError(f"String must be at most {max_length} characters long")

        if cls._regex is not None:
            if not re.match(cls._regex, value):
                pattern: str = cls._regex if isinstance(cls._regex, str) else cls._regex.pattern
                raise ValueError(f"String does not match the required pattern: {pattern}")

        return cls(value)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: type[Any], handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_plain_validator_function(cls._validate)

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        json_schema: dict[str, Any] = {"type": "string"}
        if cls._min_length is not None:
            json_schema["minLength"] = cls._min_length
        max_length = cls._get_max_length()
        if max_length is not None:
            json_schema["maxLength"] = max_length
        if cls._regex is not None:
            json_schema["pattern"] = (
                cls._regex if isinstance(cls._regex, str) else cls._regex.pattern
            )

        return json_schema
