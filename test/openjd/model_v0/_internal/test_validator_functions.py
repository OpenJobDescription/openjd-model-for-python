# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Direct unit tests for ``openjd.model._internal._validator_functions``.

These validators back the int/float format-string model fields; the happy
paths are exercised end-to-end via template parsing, so this file pins the
error paths that templates cannot cheaply reach: the missing-context
internal errors, constraint violations, and per-item error aggregation in
``validate_list_field``.
"""

from decimal import Decimal
from functools import partial

import pytest
from pydantic_core import PydanticKnownError, ValidationError

from openjd.model._internal import (
    validate_float_fmtstring_field,
    validate_int_fmtstring_field,
    validate_list_field,
)


class TestMissingContextInternalError:
    def test_int_validator_str_without_context_raises(self) -> None:
        # A raw str with no parsing context is an internal error: the value
        # should already have been converted to a FormatString upstream.
        with pytest.raises(ValueError, match="Internal parsing error"):
            validate_int_fmtstring_field("10", context=None)

    def test_float_validator_str_without_context_raises(self) -> None:
        with pytest.raises(ValueError, match="Internal parsing error"):
            validate_float_fmtstring_field("1.5", context=None)


class TestFloatConstraint:
    def test_ge_violation_raises_known_error(self) -> None:
        with pytest.raises(PydanticKnownError) as excinfo:
            validate_float_fmtstring_field(Decimal("-1.5"), ge=Decimal("0"), context=None)
        assert excinfo.value.type == "greater_than_equal"

    def test_ge_satisfied_returns_value(self) -> None:
        assert validate_float_fmtstring_field(
            Decimal("1.5"), ge=Decimal("0"), context=None
        ) == Decimal("1.5")


class TestValidateListField:
    def test_known_error_items_collected_with_location(self) -> None:
        # An item validator raising PydanticKnownError (e.g. a ge constraint)
        # is copied verbatim into the aggregate error with the item's index.
        validator = partial(validate_int_fmtstring_field, ge=0)
        with pytest.raises(ValidationError) as excinfo:
            validate_list_field([1, -2, 3, -4], validator, context=None)
        errors = excinfo.value.errors()
        assert [e["loc"] for e in errors] == [(1,), (3,)]
        assert all(e["type"] == "greater_than_equal" for e in errors)

    def test_value_error_items_collected_with_location(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            validate_list_field([1, "not-an-int"], validate_int_fmtstring_field, context=None)
        errors = excinfo.value.errors()
        assert [e["loc"] for e in errors] == [(1,)]
        assert errors[0]["type"] == "value_error"

    def test_all_valid_returns_value_unchanged(self) -> None:
        value = [1, 2, 3]
        assert validate_list_field(value, validate_int_fmtstring_field, context=None) is value
