# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from .._tokenstream import Token


class NameToken(Token):
    """An identifier matching the regex: ^[^\\d\\W][\\w]*$
    [^\\d\\W] = _ or unicode non-digit letter
    [\\w] = _ or unicode letter including digits
    """

    pass


class DotToken(Token):
    """The '.' character."""

    pass
