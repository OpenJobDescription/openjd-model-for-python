# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from unittest.mock import patch

import pytest

from openjd.model import TokenError
from openjd.model._tokenstream import Lexer, Token, TokenStream, TokenType


class DotToken(Token):
    pass


class NameToken(Token):
    pass


_tokenmap = {TokenType.NAME: NameToken, TokenType.DOT: DotToken}


class TestTokenStream:
    def test_next(self):
        # GIVEN
        expr = "Foo.Bar"

        # WHEN
        tokstream = TokenStream(expr, supported_tokens=_tokenmap)

        # THEN
        # We expect the token stream to be:
        #  [NameToken("Foo"), DotToken, NameToken("Bar")]
        tok = tokstream.next()
        assert isinstance(tok, NameToken)
        assert tok.value == "Foo"
        tok = tokstream.next()
        assert isinstance(tok, DotToken)
        tok = tokstream.next()
        assert isinstance(tok, NameToken)
        assert tok.value == "Bar"
        assert tokstream.at_end() is True
        with pytest.raises(IndexError):
            tokstream.next()

    def test_get_position(self):
        # GIVEN
        expr = "Foo.Bar"

        # WHEN
        tokstream = TokenStream(expr, supported_tokens=_tokenmap)

        # THEN
        # We expect the token stream to be:
        #  [NameToken("Foo"), DotToken, NameToken("Bar")]
        assert tokstream.expr_position == 0
        tokstream.next()
        assert tokstream.expr_position == 3
        tokstream.next()
        assert tokstream.expr_position == 4
        tokstream.next()
        assert tokstream.expr_position == 7
        assert tokstream.at_end() is True

    def test_lookahead(self):
        # GIVEN
        expr = "Foo.Bar"

        # WHEN
        tokstream = TokenStream(expr, supported_tokens=_tokenmap)

        # THEN
        # We expect the token stream to be:
        #  [NameToken("Foo"), DotToken, NameToken("Bar")]
        with pytest.raises(ValueError):
            tokstream.lookahead(-1)
        tok = tokstream.lookahead(0)
        assert isinstance(tok, NameToken)
        assert tok.value == "Foo"
        tok = tokstream.lookahead(1)
        assert isinstance(tok, DotToken)
        tok = tokstream.lookahead(2)
        assert isinstance(tok, NameToken)
        assert tok.value == "Bar"
        with pytest.raises(IndexError):
            tokstream.lookahead(3)

    def test_propagates_error(self):
        with patch.object(Lexer, "lex") as mock:
            # GIVEN
            mock.side_effect = TokenError("mocked expr", "mocked", 0)

            # THEN
            with pytest.raises(TokenError):
                TokenStream("Foo.Bar", supported_tokens=_tokenmap)

    def test_tokenize_whitespace(self):
        # GIVEN
        expr = "   Name1\t\t\t   \n\n\nName2   "

        # WHEN
        tokstream = TokenStream(expr, supported_tokens=_tokenmap)

        # THEN
        tok = tokstream.next()
        assert isinstance(tok, NameToken)
        assert tok.value == "Name1"
        tok = tokstream.next()
        assert isinstance(tok, NameToken)
        assert tok.value == "Name2"
        assert tokstream.at_end() is True
        assert tokstream.expr == "Name1 Name2"
