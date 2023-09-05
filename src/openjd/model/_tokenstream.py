# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import re
from collections import namedtuple
from dataclasses import dataclass
from enum import Enum
from typing import Sequence, Type

from ._errors import TokenError

__all__ = ["TokenType", "Token", "TokenStream"]


class TokenType(Enum):
    r"""Types of tokens that can be recognized by the lexical analysis.

    NAME = identifier ([^\d\W][\w]*)
    DOT = '.' character
    STAR = '*' character
    LPAREN = '(' character
    RPAREN = ')' character
    COMMA = ',' character
    POSTINT = identifier ([0-9]+)
    HYPHEN = '-' character
    COLON = ':' character
    """

    NAME = "NAME"
    DOT = "DOT"
    STAR = "STAR"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    COMMA = "COMMA"
    POSINT = "POSINT"
    HYPHEN = "HYPHEN"
    COLON = "COLON"


# Regular expressions for recognizing each of the tokens during lexical analysis.
TokenSpec = namedtuple("TokenSpec", "name, pattern")
token_specification = (
    # [^\d\W] = _ or unicode non-digit letter
    # [\w] = _ or unicode letter including digits
    TokenSpec(TokenType.NAME.value, r"[^\d\W][\w]*"),
    TokenSpec(TokenType.DOT.value, r"\."),
    TokenSpec(TokenType.STAR.value, r"\*"),
    TokenSpec(TokenType.LPAREN.value, r"\("),
    TokenSpec(TokenType.RPAREN.value, r"\)"),
    TokenSpec(TokenType.COMMA.value, r","),
    TokenSpec(TokenType.POSINT.value, r"[0-9]+"),  # only 0 and positive integers
    TokenSpec(TokenType.HYPHEN.value, r"-"),
    TokenSpec(TokenType.COLON.value, r":"),
    TokenSpec("NONVALID", r"."),  # Must be last in the list
)

# Precompile a regular expression matcher that will recognize each of the tokens.
# A specific token match is identified by the name of the match group; the name
# will match the value of the corresponding TokenType enum
lexer_regex = "|".join(f"(?P<{pair.name}>{pair.pattern})" for pair in token_specification)
lexer_matcher = re.compile(lexer_regex)


@dataclass
class Token:
    """Base class for every token recognized by the lexical analysis.

    Attributes:
        value (str): Text that the token represents.
        start (int): Position in the input string of the start of the token.
        end (int): Position in the input string of the end of the token.
    """

    value: str
    start: int
    end: int


class TokenStream:
    """An instance of this class will perform a lexical analysis of a given string
    and makes available methods for consuming with the resulting token stream in
    a way suitable for LL(n) parsers.

    Attributes:
        None
    """

    _tokens: list[Token]
    """The tokens for the given expression"""

    _pos: int
    """Position in _tokens that the stream is currently at."""

    _expr: str
    """The expression that we're tokenizing."""

    def __init__(self, expr: str, *, supported_tokens: dict[TokenType, Type[Token]]):
        """Initialize the TokenStream

        Args:
            expr (str): The expression to stream tokens from.
            supported_tokens (dict[TokenType, Type[Token]]): A mapping of token type to
                Token class for the token types that this tokenstream will support.

        Raises:
            TokenError: If a badly formed or unsupported token is encountered in the expression.
        """
        # We allow any amount of whitespace, including a multi-line
        # expression. Simplify the expr by replacing each whitespace
        # blocks in the expr with a single space.
        expr = re.sub(r"\s+", " ", expr)
        lexer = Lexer(expr, supported_tokens=supported_tokens)

        # Take the expr from the Tokenizer so that we have the same string as it
        # inclusive of any modifications made by the Tokenizer (e.g. stripping whitespace)
        self._expr = lexer.expr

        # Raises: TokenError
        self._tokens = list(lexer.lex())

        self._pos = 0

    @property
    def expr(self) -> str:
        """Get the expression being tokenized."""
        return self._expr

    @property
    def expr_position(self) -> int:
        """Get the current position of the token stream within the expression string"""
        if self.at_end():
            return len(self._expr)
        # We're at the start position of the current token.
        return self._tokens[self._pos].start

    def next(self) -> Token:
        """Consume the next Token from the token stream.

        Raises:
            IndexError: When no tokens remain.

        Returns:
            Token: The next token in the stream
        """
        if self._pos < len(self._tokens):
            ret = self._tokens[self._pos]
            self._pos += 1
            return ret
        raise IndexError()

    def lookahead(self, amount: int) -> Token:
        """Peek at the token 'amount' steps ahead in the stream. Does not
        advance the token stream or consume the returned token.

        Args:
            amount (int): Number of tokens to look ahead.

        Raises:
            IndexError: When there is no token at the requested position in the stream.

        Returns:
            Token: The token 'amount' steps ahead in the stream.
        """
        if amount < 0:
            raise ValueError(f"Argument amount must be >= 0. Got {amount}")
        pos = self._pos + amount
        if pos < len(self._tokens):
            return self._tokens[pos]
        raise IndexError()

    def at_end(self) -> bool:
        """
        Returns:
            bool: True if no tokens remain in the stream.
        """
        return self._pos == len(self._tokens)


class Lexer:
    _supported_tokens: dict[TokenType, Type[Token]]

    def __init__(self, expr: str, *, supported_tokens: dict[TokenType, Type[Token]]) -> None:
        """Args:
        expr (str): String interpolation expression to tokenize.
            Note: Only space characters allowed for whitespace.
        """
        self.expr = expr.strip()
        self._supported_tokens = supported_tokens

    def lex(self) -> Sequence[Token]:
        """
        Lex all tokens from the expression this lexer was created for.

        Raises:
            TokenError: If a bad or unsupported Token is encountered.
        """
        results: list[Token] = []
        for match in lexer_matcher.finditer(self.expr):
            value = match.group()
            if value == " ":
                # Skip whitespace
                continue

            start = match.start()
            end = match.end()
            try:
                kind = TokenType(match.lastgroup)
                results.append(self._supported_tokens[kind](value, start, end))
            except (ValueError, KeyError):
                # ValueError = Resolving the enum failed => Nonvalid character in expression
                # KeyError = Lookup in _supported_tokens failed => Token not supported in this lex
                raise TokenError(self.expr, value, start)

        return results
