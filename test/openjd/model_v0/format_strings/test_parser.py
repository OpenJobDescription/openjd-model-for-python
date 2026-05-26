# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest

from openjd.model import ExpressionError, TokenError
from openjd.model._format_strings._nodes import FullNameNode
from openjd.model._format_strings._parser import parse_format_string_expr
from openjd.model.v2023_09 import ModelParsingContext as ModelParsingContext_v2023_09


class TestParser:
    def test_propagates_error(self):
        with pytest.raises(TokenError):
            parse_format_string_expr("!", context=ModelParsingContext_v2023_09())

    @pytest.mark.parametrize("name", ["Foo", "Foo.Bar", "Foo.Bar.Baz", "Foo.Bar.Baz.Wuz"])
    def test_parse_names(self, name):
        # WHEN
        result = parse_format_string_expr(name, context=ModelParsingContext_v2023_09())

        # THEN
        assert isinstance(result, FullNameNode)
        assert result.name == name

    def test_fails_empty(self):
        with pytest.raises(ExpressionError):
            parse_format_string_expr("", context=ModelParsingContext_v2023_09())

    @pytest.mark.parametrize("text", [".", "Foo.", "Foo..", "Foo.Bar Foo", "Foo.Bar ."])
    def test_fails_nonvalid(self, text):
        with pytest.raises(ExpressionError):
            parse_format_string_expr(text, context=ModelParsingContext_v2023_09())
