# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Type, cast

from .._errors import ExpressionError, TokenError
from .._tokenstream import Token, TokenStream, TokenType
from ._nodes import ExprNode, FullNameNode, Node
from ._tokens import DotToken, NameToken
from .._types import ModelParsingContextInterface

# Defined here (rather than imported from ._expr_support) so that importing the
# parser does not transitively load the Rust expr surface. ExprNode itself
# imports the Rust bindings lazily, so the non-EXPR parse path never touches
# them.
EXPR_EXTENSION = "EXPR"

_tokens: dict[TokenType, Type[Token]] = {TokenType.NAME: NameToken, TokenType.DOT: DotToken}


def parse_format_string_expr(expr: str, *, context: ModelParsingContextInterface) -> Node:
    """Generate an expression tree for the given string interpolation expression.

    When the template declares the ``EXPR`` extension, parsing is delegated to
    the Rust ``openjd-expr`` engine (via :class:`ExprNode`); otherwise the
    legacy ``Name.Dot.Name`` parser is used. Templates that do not declare
    ``EXPR`` are byte-for-byte unaffected.

    Args:
        expr (str): A string interpolation expression

    Raises:
        ExpressionError: If the given expression does not adhere to the grammar.
        TokenError: If the given expression contains nonvalid or unexpected tokens.

    Returns:
        Node: Root of the expression tree.
    """
    if EXPR_EXTENSION in context.extensions:
        # Raises: model ExpressionError on parse failure.
        return ExprNode(expr)
    return FormatStringExprParser_v2023_09().parse(expr)


class FormatStringExprParser_v2023_09:
    """
    Parser used to build an AST of format strings for the 2023-09 specification.
    """

    def parse(self, expr: str) -> Node:
        """Generate an expression tree for the given string interpolation expression.

        Args:
            expr (str): A string interpolation expression

        Raises:
            ExpressionError: If the given expression does not adhere to the grammar.
            TokenError: If the given expression contains nonvalid or unexpected tokens.

        Returns:
            Node: Root of the expression tree.
        """

        # Raises: TokenError
        self._tokens = TokenStream(expr, supported_tokens=_tokens)

        result = self._expression()
        if not self._tokens.at_end():
            token = self._tokens.next()
            raise TokenError(self._tokens.expr, token.value, token.start)

        return result

    def _expression(self) -> Node:
        """Matches the root of the expression grammar.

        Grammar:
        <Expression> ::= <FullName>
        <FullName> ::= <Name> ( <Dot> <Name> )*
        <Name> ::= [A-Za-z_][A-Za-z0-9_]*
        <Dot> ::= '.'

        Raises:
            ExpressionError: When there is an error parsing the expression.
            TokenError: If the expression contains unexpected tokens.

        Returns:
            Node: Root node of the expression tree.
        """
        if self._tokens.at_end():
            raise ExpressionError("Empty expression")

        if isinstance(self._tokens.lookahead(0), NameToken):
            # Raises: ExpressionError, TokenError
            return self._match_name()

        token = self._tokens.next()
        raise TokenError(self._tokens.expr, token.value, token.start)

    def _match_name(self) -> FullNameNode:
        """Matches:
        <FullName> ::= <Name> ( <Dot> <Name> )*

        Raises:
            ExpressionError: When there is an error parsing the expression.
            TokenError: If the expression contains unexpected tokens.
        """
        token: Token = cast(NameToken, self._tokens.next())
        names = [token.value]

        try:
            while isinstance(self._tokens.lookahead(0), DotToken):
                _ = self._tokens.next()
                try:
                    token = self._tokens.next()
                except IndexError:
                    raise ExpressionError(
                        f"Unexpected end of name '{'.'.join(names)}.'",
                    )
                if not isinstance(token, NameToken):
                    raise TokenError(self._tokens.expr, token.value, token.start)
                names.append(token.value)
        except IndexError:
            # Catches the lookahead on the while condition. Not having a dot after the name is okay.
            pass

        return FullNameNode(".".join(names))
