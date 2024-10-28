# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import re
from typing import TYPE_CHECKING, Any, Callable, Optional, Pattern, Union

from pydantic.v1.errors import AnyStrMaxLengthError, AnyStrMinLengthError, StrRegexError
from pydantic.v1.utils import update_not_none
from pydantic.v1.validators import strict_str_validator

if TYPE_CHECKING:
    from pydantic.v1.typing import CallableGenerator


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
    def __modify_schema__(cls, field_schema: dict[str, Any]) -> None:
        update_not_none(
            field_schema,
            minLength=cls._min_length,
            maxLength=cls._get_max_length(),
        )

    @classmethod
    def __get_validators__(cls) -> "CallableGenerator":
        yield strict_str_validator  # Always strict string.
        yield cls._validate_min_length
        yield cls._validate_max_length
        yield cls._validate_regex

    @classmethod
    def _validate_min_length(cls, value: str) -> str:
        if cls._min_length is not None and len(value) < cls._min_length:
            raise AnyStrMinLengthError(limit_value=cls._min_length)
        return value

    @classmethod
    def _validate_max_length(cls, value: str) -> str:
        max_length = cls._get_max_length()
        if max_length is not None and len(value) > max_length:
            raise AnyStrMaxLengthError(limit_value=max_length)
        return value

    @classmethod
    def _validate_regex(cls, value: str) -> str:
        if cls._regex is not None:
            if not re.match(cls._regex, value):
                pattern: str = cls._regex if isinstance(cls._regex, str) else cls._regex.pattern
                raise StrRegexError(pattern=pattern)
        return value
