# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from unittest.mock import patch

import pytest

from openjd.model import TokenError
from openjd.model._tokenstream import Lexer, Token, TokenType


class DotToken(Token):
    pass


class NameToken(Token):
    pass


_tokenmap = {TokenType.NAME: NameToken, TokenType.DOT: DotToken}


class TestLexer:
    def test_initialize_does_not_lex(self):
        with patch.object(Lexer, "lex") as mocked:
            # Given

            # When
            Lexer("text", supported_tokens=_tokenmap)

            # Then
            mocked.assert_not_called()

    @pytest.mark.parametrize("token", ["-", "+", "=", "*", "/", "'string'"])
    def test_lex_nonvalid_tokens(self, token):
        # Given

        # When
        tok = Lexer(token, supported_tokens=_tokenmap)

        # Then
        with pytest.raises(TokenError):
            tok.lex()

    @pytest.mark.parametrize(
        "text", ["Job", "Task", "Test1", "multiple_words", "unicode_Ä", "Ä_unicode", "_Test"]
    )
    def test_lex_name(self, text):
        # GIVEN
        tok = Lexer(text, supported_tokens=_tokenmap)

        # WHEN
        tokens = tok.lex()

        # THEN
        assert len(tokens) == 1
        assert isinstance(tokens[0], NameToken)
        assert tokens[0].value == text

    def test_lex_dot(self):
        # GIVEN
        tok = Lexer(".", supported_tokens=_tokenmap)

        # WHEN
        tokens = tok.lex()

        # THEN
        assert len(tokens) == 1
        assert isinstance(tokens[0], DotToken)

    @pytest.mark.parametrize(
        "input,token_count",
        [("test", 1), (".", 1), ("test.", 2), (".test", 2), ("..test..", 5), ("word1.word2", 3)],
    )
    def test_multiple_valid_tokens(self, input, token_count):
        # Given
        # When
        tok = Lexer(input, supported_tokens=_tokenmap)

        # Then
        assert len(tok.lex()) == token_count

    @pytest.mark.parametrize("text", ["1Test", "^Test"])
    def test_handles_nonvalid_tokens(self, text):
        # Given
        tok = Lexer(text, supported_tokens=_tokenmap)

        # THEN
        with pytest.raises(TokenError):
            tok.lex()

    def test_handles_emptystring(self):
        # GIVEN
        expr = ""

        # WHEN
        tok = Lexer(expr, supported_tokens=_tokenmap)

        # THEN
        try:
            tok.lex()
        except:  # noqa: E722
            pytest.fail("Should not raise exception")
