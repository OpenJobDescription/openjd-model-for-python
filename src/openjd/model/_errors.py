# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

__all__ = [
    "CompatibilityError",
    "DecodeValidationError",
    "ExpressionError",
    "ModelValidationError",
    "TokenError",
    "UnsupportedSchema",
]


class UnsupportedSchema(ValueError):
    """Error raised when an attempt is made to decode a template with
    an unknown or otherwise nonvalid schema identification.
    """

    _version: str

    def __init__(self, version: str):
        self._version = version
        super().__init__(f"Unsupported schema version: {self._version}")


class DecodeValidationError(ValueError):
    """Error raised when an decoding error is encountered while decoding
    a template.
    """


class ModelValidationError(ValueError):
    """Error raised when a validation error is encountered while validating
    a model.
    """


class ExpressionError(ValueError):
    """Error raised when there is an error in the form of an expression that is being
    parsed.
    """


class TokenError(ExpressionError):
    """Error raised when performing lexical analysis on an expression for parsing."""

    def __init__(self, expression: str, token_value: str, position: int):
        msg = f"Unexpected '{token_value}' in '{expression}' after '{expression[:position]}'"
        super().__init__(msg)


class CompatibilityError(ValueError):
    """Error raised when a check that two, or more, models are compatible determines that
    there are non-compatibilities between the models.
    """
