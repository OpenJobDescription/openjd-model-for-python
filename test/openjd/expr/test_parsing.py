# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for expression parsing, whitespace handling, and contextual keywords."""

import pytest
from openjd.expr import evaluate_expression, SymbolTable, ExpressionError


class TestContextualKeywords:
    """Tests for Python keywords used as attribute names."""

    @pytest.mark.parametrize(
        "keyword",
        ["if", "else", "and", "or", "not", "for", "in", "True", "False", "None"],
    )
    def test_keyword_as_attribute(self, keyword: str) -> None:
        symtab = SymbolTable({f"Param.{keyword}": 42})
        assert evaluate_expression(f"Param.{keyword}", values=symtab).item() == 42

    def test_keyword_in_expression_context(self) -> None:
        symtab = SymbolTable({"Param.if": 10, "Param.else": 20})
        assert evaluate_expression("Param.if + Param.else", values=symtab).item() == 30

    def test_keyword_with_conditional(self) -> None:
        symtab = SymbolTable({"Param.if": 100})
        assert evaluate_expression("Param.if if True else 0", values=symtab).item() == 100

    def test_keyword_multiline_list(self) -> None:
        symtab = SymbolTable({"Param.if": 10, "Param.else": 20})
        result = evaluate_expression(
            """[
            Param.if,
            Param.else
        ]""",
            values=symtab,
        )
        assert result.item() == [10, 20]

    def test_keyword_multiline_parens(self) -> None:
        symtab = SymbolTable({"Param.if": 10, "Param.else": 20})
        result = evaluate_expression(
            """(
            Param.if +
            Param.else
        )""",
            values=symtab,
        )
        assert result.item() == 30


class TestWhitespaceHandling:
    """Tests for whitespace handling in expressions."""

    def test_leading_space(self) -> None:
        assert evaluate_expression(" 1 + 2").item() == 3

    def test_leading_tab(self) -> None:
        assert evaluate_expression("\t1 + 2").item() == 3

    def test_leading_and_trailing_whitespace(self) -> None:
        assert evaluate_expression("  \t  3 * 4  \n").item() == 12

    def test_multiline_with_parens(self) -> None:
        result = evaluate_expression(
            """(
            1 + 2 +
            3
        )"""
        )
        assert result.item() == 6

    def test_multiline_list(self) -> None:
        result = evaluate_expression(
            """[
            1,
            2,
            3
        ]"""
        )
        assert result.item() == [1, 2, 3]

    def test_multiline_conditional(self) -> None:
        result = evaluate_expression(
            """
            1 if True else 2
        """
        )
        assert result.item() == 1


class TestSyntaxErrors:
    """Tests for syntax error handling."""

    def test_invalid_syntax(self) -> None:
        with pytest.raises(ExpressionError, match="Syntax error"):
            evaluate_expression("1 +")

    def test_unclosed_paren(self) -> None:
        with pytest.raises(ExpressionError, match="Syntax error"):
            evaluate_expression("(1 + 2")

    def test_unclosed_bracket(self) -> None:
        with pytest.raises(ExpressionError, match="Syntax error"):
            evaluate_expression("[1, 2, 3")

    def test_colon_only(self) -> None:
        """Regression test: colon-only input should not cause IndexError."""
        with pytest.raises(ExpressionError, match="Syntax error"):
            evaluate_expression(":")

    def test_method_on_int_literal_without_parens(self) -> None:
        """Method calls on int literals need parentheses: (42).zfill(5) not 42.zfill(5)."""
        with pytest.raises(ExpressionError, match="Syntax error"):
            evaluate_expression("42.zfill(5)")

    def test_method_on_int_literal_with_parens(self) -> None:
        """Method calls on int literals work with parentheses."""
        assert evaluate_expression("(42).zfill(5)").item() == "00042"

    def test_chained_comparison(self) -> None:
        assert evaluate_expression("1 < 2 < 3").item() is True
        assert evaluate_expression("1 < 2 < 2").item() is False
        assert evaluate_expression("3 > 2 > 1").item() is True
        assert evaluate_expression("1 <= 2 <= 3").item() is True
        assert evaluate_expression("3 >= 2 >= 1").item() is True
        assert evaluate_expression("1 < 2 <= 2").item() is True
        assert evaluate_expression("1 <= 2 < 3").item() is True
        assert evaluate_expression("3 > 2 >= 2").item() is True
        assert evaluate_expression("3 >= 2 > 1").item() is True


class TestDunderMethodsRejected:
    """Tests that direct dunder method calls are rejected."""

    def test_add_rejected(self) -> None:
        with pytest.raises(ExpressionError, match="Cannot call '__add__' directly"):
            evaluate_expression("(1).__add__(2)")

    def test_sub_rejected(self) -> None:
        with pytest.raises(ExpressionError, match="Cannot call '__sub__' directly"):
            evaluate_expression("(5).__sub__(3)")

    def test_mul_rejected(self) -> None:
        with pytest.raises(ExpressionError, match="Cannot call '__mul__' directly"):
            evaluate_expression("(6).__mul__(7)")

    def test_truediv_rejected(self) -> None:
        with pytest.raises(ExpressionError, match="Cannot call '__truediv__' directly"):
            evaluate_expression("(10).__truediv__(3)")

    def test_floordiv_rejected(self) -> None:
        with pytest.raises(ExpressionError, match="Cannot call '__floordiv__' directly"):
            evaluate_expression("(10).__floordiv__(3)")

    def test_mod_rejected(self) -> None:
        with pytest.raises(ExpressionError, match="Cannot call '__mod__' directly"):
            evaluate_expression("(10).__mod__(3)")

    def test_neg_rejected(self) -> None:
        with pytest.raises(ExpressionError, match="Cannot call '__neg__' directly"):
            evaluate_expression("(-5).__neg__()")

    def test_lt_rejected(self) -> None:
        with pytest.raises(ExpressionError, match="Cannot call '__lt__' directly"):
            evaluate_expression("(1).__lt__(2)")

    def test_eq_rejected(self) -> None:
        with pytest.raises(ExpressionError, match="Cannot call '__eq__' directly"):
            evaluate_expression("(1).__eq__(1)")

    def test_not_rejected(self) -> None:
        with pytest.raises(ExpressionError, match="Cannot call '__not__' directly"):
            evaluate_expression("True.__not__()")

    def test_getitem_rejected(self) -> None:
        with pytest.raises(ExpressionError, match="Cannot call '__getitem__' directly"):
            evaluate_expression("[1,2,3].__getitem__(0)")

    def test_contains_rejected(self) -> None:
        with pytest.raises(ExpressionError, match="Cannot call '__contains__' directly"):
            evaluate_expression("[1,2,3].__contains__(2)")

    def test_property_dunder_rejected(self) -> None:
        with pytest.raises(ExpressionError, match="Cannot call '__property_name__' directly"):
            evaluate_expression('path("/a/b").__property_name__()')


class TestNumericLiteralFormats:
    """Tests for numeric literal formats per RFC 5 grammar."""

    # Decimal integers
    def test_decimal_int(self) -> None:
        assert evaluate_expression("42").item() == 42
        assert evaluate_expression("0").item() == 0

    # Hexadecimal integers
    def test_hex_int_lowercase(self) -> None:
        assert evaluate_expression("0x2a").item() == 42

    def test_hex_int_uppercase(self) -> None:
        assert evaluate_expression("0X2A").item() == 42

    def test_hex_int_mixed_case(self) -> None:
        assert evaluate_expression("0xDeAdBeEf").item() == 0xDEADBEEF

    # Octal integers
    def test_octal_int_lowercase(self) -> None:
        assert evaluate_expression("0o52").item() == 42

    def test_octal_int_uppercase(self) -> None:
        assert evaluate_expression("0O52").item() == 42

    def test_old_octal_format_rejected(self) -> None:
        """Old C-style octal format 0777 should not be accepted."""
        # In Python 3, 0777 is a syntax error - leading zeros are not allowed
        with pytest.raises(ExpressionError, match="Syntax error"):
            evaluate_expression("0777")

    def test_leading_zero_rejected(self) -> None:
        """Leading zeros on decimal integers are not allowed."""
        with pytest.raises(ExpressionError, match="Syntax error"):
            evaluate_expression("007")

    def test_double_zero_accepted(self) -> None:
        """00 is valid (just zero)."""
        assert evaluate_expression("00").item() == 0

    # Binary integers
    def test_binary_int_lowercase(self) -> None:
        assert evaluate_expression("0b101010").item() == 42

    def test_binary_int_uppercase(self) -> None:
        assert evaluate_expression("0B101010").item() == 42

    # Underscore separators in integers
    def test_underscore_in_decimal(self) -> None:
        assert evaluate_expression("1_000_000").item() == 1_000_000

    def test_underscore_in_hex(self) -> None:
        assert evaluate_expression("0xFF_FF").item() == 0xFFFF

    def test_underscore_in_octal(self) -> None:
        assert evaluate_expression("0o7_7_7").item() == 0o777

    def test_underscore_in_binary(self) -> None:
        assert evaluate_expression("0b1010_1010").item() == 0b10101010

    # Underscore constraints - these should fail
    def test_underscore_at_start_is_variable(self) -> None:
        """Leading underscore makes it a variable name, not a number."""
        with pytest.raises(ExpressionError, match="Undefined variable"):
            evaluate_expression("_123")

    def test_underscore_at_end_rejected(self) -> None:
        with pytest.raises(ExpressionError, match="Syntax error"):
            evaluate_expression("123_")

    def test_double_underscore_rejected(self) -> None:
        with pytest.raises(ExpressionError, match="Syntax error"):
            evaluate_expression("1__000")

    def test_underscore_after_hex_prefix_accepted(self) -> None:
        """Python allows underscore after 0x prefix."""
        assert evaluate_expression("0x_FF").item() == 0xFF

    def test_underscore_after_octal_prefix_accepted(self) -> None:
        """Python allows underscore after 0o prefix."""
        assert evaluate_expression("0o_77").item() == 0o77

    def test_underscore_after_binary_prefix_accepted(self) -> None:
        """Python allows underscore after 0b prefix."""
        assert evaluate_expression("0b_10").item() == 0b10

    # Float literals
    def test_decimal_float(self) -> None:
        assert evaluate_expression("3.14").item() == 3.14

    def test_float_no_integer_part(self) -> None:
        assert evaluate_expression(".5").item() == 0.5

    def test_float_no_decimal_part(self) -> None:
        assert evaluate_expression("3.").item() == 3.0

    # Scientific notation
    def test_scientific_notation_lowercase(self) -> None:
        assert evaluate_expression("1e10").item() == 1e10

    def test_scientific_notation_uppercase(self) -> None:
        assert evaluate_expression("1E10").item() == 1e10

    def test_scientific_notation_positive_exponent(self) -> None:
        assert evaluate_expression("1e+10").item() == 1e10

    def test_scientific_notation_negative_exponent(self) -> None:
        assert evaluate_expression("1.5e-3").item() == 1.5e-3

    def test_scientific_notation_with_decimal(self) -> None:
        assert evaluate_expression("6.022e23").item() == 6.022e23

    # Underscore in floats
    def test_underscore_in_float_integer_part(self) -> None:
        assert evaluate_expression("1_000.5").item() == 1000.5

    def test_underscore_in_float_decimal_part(self) -> None:
        assert evaluate_expression("3.141_592").item() == 3.141592

    def test_underscore_in_exponent(self) -> None:
        assert evaluate_expression("1e1_0").item() == 1e10

    # Underscore constraints in floats
    def test_underscore_adjacent_to_decimal_rejected(self) -> None:
        with pytest.raises(ExpressionError, match="Syntax error"):
            evaluate_expression("1_.5")

    def test_underscore_after_decimal_rejected(self) -> None:
        with pytest.raises(ExpressionError, match="Syntax error"):
            evaluate_expression("1._5")

    def test_underscore_adjacent_to_exponent_rejected(self) -> None:
        with pytest.raises(ExpressionError, match="Syntax error"):
            evaluate_expression("1_e10")

    def test_underscore_after_exponent_rejected(self) -> None:
        with pytest.raises(ExpressionError, match="Syntax error"):
            evaluate_expression("1e_10")


class TestUnsupportedPythonFeatures:
    """Verify Python features NOT in the expression language spec are rejected.

    Cross-checked against Python 3.14 grammar (https://docs.python.org/3.14/reference/grammar.html).
    These tests ensure we don't accidentally support more than specified.
    """

    # === Statements (should all fail - expressions only) ===

    @pytest.mark.parametrize(
        "code",
        [
            "x = 1",  # Assignment
            "x += 1",  # Augmented assignment
            "x := 1",  # Walrus operator (assignment_expression)
            "del x",  # Delete
            "pass",  # Pass
            "break",  # Break
            "continue",  # Continue
            "return 1",  # Return
            "raise Exception()",  # Raise
            "yield 1",  # Yield
            "yield from [1]",  # Yield from
            "global x",  # Global
            "nonlocal x",  # Nonlocal
            "assert True",  # Assert
            "import os",  # Import
            "from os import path",  # From import
            "type X = int",  # Type alias (Python 3.12+)
        ],
    )
    def test_statements_rejected(self, code: str) -> None:
        """Python statements must be rejected (expression-only language)."""
        with pytest.raises((SyntaxError, ExpressionError)):
            evaluate_expression(code)

    # === Compound statements ===

    @pytest.mark.parametrize(
        "code",
        [
            "if True: 1",  # If statement (not ternary)
            "for x in []: pass",  # For loop
            "while True: pass",  # While loop
            "with open('f'): pass",  # With statement
            "try: 1\nexcept: 2",  # Try/except
            "def f(): pass",  # Function def
            "class C: pass",  # Class def
            "async def f(): pass",  # Async function
            "async for x in []: pass",  # Async for
            "async with x: pass",  # Async with
            "match x:\n  case 1: pass",  # Match statement (Python 3.10+)
        ],
    )
    def test_compound_statements_rejected(self, code: str) -> None:
        """Compound statements must be rejected."""
        with pytest.raises((SyntaxError, ExpressionError)):
            evaluate_expression(code)

    # === Expressions that should NOT be supported ===

    @pytest.mark.parametrize(
        "code",
        [
            "lambda x: x",  # Lambda
            "lambda: 1",  # Lambda no args
            "(x for x in [1])",  # Generator expression
            "{x for x in [1]}",  # Set comprehension
            "{x: 1 for x in [1]}",  # Dict comprehension
            "{1, 2, 3}",  # Set literal
            "{'a': 1}",  # Dict literal
            "await foo()",  # Await expression
            "f'{x}'",  # F-string
            "t'{x}'",  # T-string (template string, Python 3.14+)
            "b'bytes'",  # Bytes literal
        ],
    )
    def test_unsupported_expressions_rejected(self, code: str) -> None:
        """Unsupported expression types must be rejected."""
        with pytest.raises((SyntaxError, ExpressionError, NameError)):
            evaluate_expression(code)

    def test_raw_string_is_supported(self) -> None:
        """Raw strings r'...' are supported (they're just regular strings)."""
        result = evaluate_expression(r"r'\n'")
        assert result.item() == "\\n"  # Literal backslash-n, not newline

    # === Operators that should NOT be supported ===

    @pytest.mark.parametrize(
        "code",
        [
            "1 & 2",  # Bitwise AND
            "1 | 2",  # Bitwise OR
            "1 ^ 2",  # Bitwise XOR
            "~1",  # Bitwise NOT
            "1 << 2",  # Left shift
            "1 >> 2",  # Right shift
            "1 @ 2",  # Matrix multiply
            "1 is 1",  # Identity comparison
            "1 is not 2",  # Identity comparison (negated)
        ],
    )
    def test_unsupported_operators_rejected(self, code: str) -> None:
        """Bitwise, matrix, and identity operators must be rejected."""
        with pytest.raises(ExpressionError):
            evaluate_expression(code)

    # === Built-in functions that should NOT be available ===

    @pytest.mark.parametrize(
        "code",
        [
            "eval('1')",
            "exec('1')",
            "compile('1', '', 'eval')",
            "open('file')",
            "input()",
            "print(1)",
            "__import__('os')",
            "globals()",
            "locals()",
            "vars()",
            "dir()",
            "type(1)",
            "isinstance(1, int)",
            "issubclass(int, object)",
            "getattr(1, 'x')",
            "setattr(1, 'x', 1)",
            "delattr(1, 'x')",
            "hasattr(1, 'x')",
            "id(1)",
            "hash(1)",
            "callable(1)",
            "enumerate([1])",
            "zip([1], [2])",
            "map(str, [1])",
            "filter(None, [1])",
            "reduce(lambda a,b: a+b, [1])",
            "iter([1])",
            "next(iter([1]))",
            "slice(1)",
            "object()",
            "super()",
            "property()",
            "staticmethod(lambda: 1)",
            "classmethod(lambda: 1)",
            "memoryview(b'')",
            "bytearray()",
            "bytes()",
            "frozenset()",
            "set()",
            "dict()",
            "tuple()",
            "complex(1, 2)",
            "oct(8)",
            "hex(16)",
            "bin(2)",
            "ord('a')",
            "chr(97)",
            "ascii('a')",
            "format(1, 'd')",
            "pow(2, 3, 5)",  # pow with modulo (3-arg)
            "divmod(7, 3)",
            "help()",
            "breakpoint()",
            "exit()",
            "quit()",
        ],
    )
    def test_python_builtins_not_available(self, code: str) -> None:
        """Python built-in functions must not be available."""
        with pytest.raises(ExpressionError):
            evaluate_expression(code)


class TestASTNodeRejection:
    """Tests that parse_expression rejects unsupported Python AST nodes at parse time.

    These complement TestUnsupportedPythonFeatures by verifying rejection happens
    during parsing (not evaluation), matching the spec's fail-fast requirement.
    """

    @pytest.mark.parametrize(
        "expr,match",
        [
            # Expressions
            pytest.param("(x := 5)", "Walrus", id="walrus"),
            pytest.param("lambda x: x + 1", "Lambda", id="lambda"),
            pytest.param("lambda: 1", "Lambda", id="lambda-no-args"),
            pytest.param("(1, 2, 3)", "Tuple", id="tuple"),
            pytest.param("{'a': 1}", "Dict", id="dict-literal"),
            pytest.param("{1, 2, 3}", "Set", id="set-literal"),
            pytest.param("{k: k for k in [1]}", "Dict comp", id="dict-comp"),
            pytest.param("{x for x in [1]}", "Set comp", id="set-comp"),
            pytest.param("(x for x in [1])", "Generator", id="generator-expr"),
            pytest.param("f'hello'", "f-string", id="fstring"),
            pytest.param("b'hello'", "Byte string", id="bstring"),
            pytest.param("await x", "Await", id="await"),
            pytest.param("...", "Ellipsis", id="ellipsis"),
            # Star unpacking
            pytest.param("[*[1, 2], 3]", "Star", id="star-unpack"),
            # Operators
            pytest.param("5 & 3", "Bitwise AND", id="bitwise-and"),
            pytest.param("5 | 3", "Bitwise OR", id="bitwise-or"),
            pytest.param("5 ^ 3", "Bitwise XOR", id="bitwise-xor"),
            pytest.param("~5", "Bitwise NOT", id="bitwise-not"),
            pytest.param("5 << 1", "Left shift", id="left-shift"),
            pytest.param("5 >> 1", "Right shift", id="right-shift"),
            pytest.param("x @ y", "Matrix multiply", id="matmul"),
            pytest.param("x is None", "'is'", id="is-operator"),
            pytest.param("x is not None", "'is not'", id="is-not-operator"),
            # Call syntax
            pytest.param("f(x=1)", "Keyword", id="keyword-arg"),
            pytest.param("f(**d)", "not supported", id="double-star-arg"),
        ],
    )
    def test_rejected_at_parse_time(self, expr: str, match: str) -> None:
        from openjd.expr import parse_expression

        with pytest.raises(ExpressionError, match=match):
            parse_expression(expr)

    @pytest.mark.parametrize(
        "expr,match",
        [
            # Multiple generators
            pytest.param(
                "[x + y for x in [1] for y in [2]]",
                "Multiple 'for'",
                id="multi-generator",
            ),
            # Multiple if clauses
            pytest.param(
                "[x for x in [1, 2, 3] if x > 1 if x < 3]",
                "Multiple 'if'",
                id="multi-if",
            ),
            # Tuple unpacking in comprehension
            pytest.param(
                "[a for a, b in [[1, 2]]]",
                "Tuple",
                id="tuple-unpack-comp",
            ),
        ],
    )
    def test_comprehension_restrictions(self, expr: str, match: str) -> None:
        from openjd.expr import parse_expression

        with pytest.raises(ExpressionError, match=match):
            parse_expression(expr)

    @pytest.mark.parametrize(
        "expr",
        [
            # These should all parse successfully
            "1 + 2",
            "[1, 2, 3]",
            "[x for x in [1, 2] if x > 0]",
            "'hello'.upper()",
            "x if True else y",
            "not True",
            "-5",
            "+5",
            "1 < 2 < 3",
            "x in [1, 2]",
            "x not in [1, 2]",
            "1 == 2",
            "1 != 2",
            "2 ** 3",
            "[1, 2][0]",
            "[1, 2][0:1]",
            "'hello'",
            "r'raw\\n'",
            "'''triple'''",
            "0x2A",
            "0o52",
            "0b101010",
            "1_000",
            "1.5e3",
            "True",
            "False",
            "None",
            "null",
            "true",
            "false",
            "[]",
            "[1,]",
        ],
    )
    def test_allowed_syntax_still_parses(self, expr: str) -> None:
        """Ensure the AST validation doesn't reject valid EXPR syntax."""
        from openjd.expr import parse_expression

        parse_expression(expr)  # Should not raise


class TestLoopVariableValidation:
    def test_lowercase_loop_var_accepted(self) -> None:
        from openjd.expr import parse_expression

        parse_expression("[x for x in [1, 2]]")

    def test_underscore_loop_var_accepted(self) -> None:
        from openjd.expr import parse_expression

        parse_expression("[_x for _x in [1, 2]]")

    def test_uppercase_loop_var_rejected(self) -> None:
        from openjd.expr import parse_expression

        with pytest.raises(
            ExpressionError, match="must start with a lowercase letter or underscore"
        ):
            parse_expression("[X for X in [1, 2]]")
