# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

__all__ = [
    "CompatibilityError",
    "DecodeValidationError",
    "ExpressionError",
    "ModelValidationError",
    "TokenError",
    "UnsupportedSchema",
]


class _BaseMessageError(Exception):
    """A base class for exceptions that have an error message"""

    msg: str
    """The error message"""

    def __init__(self, msg: str) -> None:
        self.msg = msg
        super(_BaseMessageError, self).__init__(msg)

    def __str__(self) -> str:
        return self.msg


class UnsupportedSchema(_BaseMessageError):
    """Error raised when an attempt is made to decode a template with
    an unknown or otherwise nonvalid schema identification.
    """

    _version: str

    def __init__(self, version: str):
        self._version = version
        super().__init__(f"Unsupported schema version: {self._version}")


class DecodeValidationError(_BaseMessageError):
    """Error raised when an decoding error is encountered while decoding
    a template.
    """

    pass


class ModelValidationError(_BaseMessageError):
    """Error raised when a validation error is encountered while validating
    a model.
    """

    pass


class ExpressionError(_BaseMessageError):
    """Error raised when there is an error in the form of an expression that is being
    parsed.
    """

    pass


class TokenError(ExpressionError):
    """Error raised when performing lexical analysis on an expression for parsing."""

    def __init__(self, expression: str, token_value: str, position: int):
        msg = f"Unexpected '{token_value}' in '{expression}' after '{expression[:position]}'"
        super().__init__(msg)


class CompatibilityError(_BaseMessageError):
    """Error raised when a check that two, or more, models are compatible determines that
    there are non-compatibilities between the models.
    """

    pass
