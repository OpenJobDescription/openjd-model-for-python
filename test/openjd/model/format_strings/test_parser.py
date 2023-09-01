# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest

from openjd.model import ExpressionError, TokenError
from openjd.model._format_strings._nodes import FullNameNode
from openjd.model._format_strings._parser import Parser


class TestParser:
    def test_propagates_error(self):
        # GIVEN
        parser = Parser()

        # THEN
        with pytest.raises(TokenError):
            parser.parse("!")

    @pytest.mark.parametrize("name", ["Foo", "Foo.Bar", "Foo.Bar.Baz", "Foo.Bar.Baz.Wuz"])
    def test_parse_names(self, name):
        # GIVEN
        parser = Parser()

        # WHEN
        result = parser.parse(name)

        # THEN
        assert isinstance(result, FullNameNode)
        assert result.name == name

    def test_fails_empty(self):
        # GIVEN
        parser = Parser()

        # THEN
        with pytest.raises(ExpressionError):
            parser.parse("")

    @pytest.mark.parametrize("text", [".", "Foo.", "Foo..", "Foo.Bar Foo", "Foo.Bar ."])
    def test_fails_nonvalid(self, text):
        # GIVEN
        parser = Parser()

        # THEN
        with pytest.raises(ExpressionError):
            parser.parse(text)
