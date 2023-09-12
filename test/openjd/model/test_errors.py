# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from openjd.model import (
    DecodeValidationError,
    ExpressionError,
    TokenError,
    UnsupportedSchema,
)


class TestUnsupportedSchema:
    def test_msg(self):
        # GIVEN
        error = UnsupportedSchema("version")

        # THEN
        assert str(error) == "Unsupported schema version: version"


class TestDecodeValidationError:
    def test_msg(self):
        # GIVEN
        error = DecodeValidationError("Test message")

        # THEN
        assert str(error) == "Test message"


class TestExpressionError:
    def test_msg(self):
        # GIVEN
        error = ExpressionError("Test message")

        # THEN
        assert str(error) == "Test message"


class TestTokenError:
    def test_msg(self):
        # GIVEN
        error = TokenError("0123456789", "5", 5)

        # THEN
        assert str(error) == "Unexpected '5' in '0123456789' after '01234'"
