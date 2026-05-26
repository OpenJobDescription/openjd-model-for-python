# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for string operations."""

import os
import pytest
from openjd.expr import evaluate_expression, ExpressionError, PathFormat


class TestStrings:
    def test_concatenation(self) -> None:
        assert evaluate_expression("'hello' + ' ' + 'world'").item() == "hello world"

    def test_string_range_expr_concatenation(self) -> None:
        assert evaluate_expression("'frames: ' + range_expr('1-3')").item() == "frames: 1-3"

    def test_range_expr_string_concatenation(self) -> None:
        assert evaluate_expression("range_expr('1-3') + ' are frames'").item() == "1-3 are frames"

    def test_repetition(self) -> None:
        assert evaluate_expression("'ab' * 3").item() == "ababab"

    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("upper('hello')", "HELLO"),
            ("lower('HELLO')", "hello"),
            ("strip('  hi  ')", "hi"),
            # strip/lstrip/rstrip with chars parameter
            ("strip('xxhelloxx', 'x')", "hello"),
            ("strip('...hi...', '.')", "hi"),
            ("strip('abcHELLOcba', 'abc')", "HELLO"),
            ("lstrip('xxhelloxx', 'x')", "helloxx"),
            ("lstrip('...hi...', '.')", "hi..."),
            ("rstrip('xxhelloxx', 'x')", "xxhello"),
            ("rstrip('...hi...', '.')", "...hi"),
            # method syntax
            ("'xxhelloxx'.strip('x')", "hello"),
            ("'xxhelloxx'.lstrip('x')", "helloxx"),
            ("'xxhelloxx'.rstrip('x')", "xxhello"),
        ],
    )
    def test_string_functions(self, expr: str, expected: str) -> None:
        assert evaluate_expression(expr).item() == expected

    def test_method_syntax(self) -> None:
        assert evaluate_expression("'hello'.upper()").item() == "HELLO"

    def test_startswith(self) -> None:
        assert evaluate_expression("startswith('hello', 'hel')").item() is True

    def test_endswith(self) -> None:
        assert evaluate_expression("endswith('hello', 'lo')").item() is True

    @pytest.mark.parametrize(
        "expr,expected",
        [
            # isdigit
            ("'123'.isdigit()", True),
            ("'12a'.isdigit()", False),
            ("''.isdigit()", False),
            # isalpha
            ("'abc'.isalpha()", True),
            ("'ab3'.isalpha()", False),
            ("''.isalpha()", False),
            # isalnum
            ("'abc123'.isalnum()", True),
            ("'abc 123'.isalnum()", False),
            ("''.isalnum()", False),
            # isspace
            ("'  \\t\\n'.isspace()", True),
            ("' hi '.isspace()", False),
            ("''.isspace()", False),
            # isupper
            ("'ABC'.isupper()", True),
            ("'ABc'.isupper()", False),
            ("'123'.isupper()", False),
            # islower
            ("'abc'.islower()", True),
            ("'aBc'.islower()", False),
            ("'123'.islower()", False),
            # isascii
            ("'hello'.isascii()", True),
            ("''.isascii()", True),
            ("'h\\xe9llo'.isascii()", False),
        ],
    )
    def test_string_classification(self, expr: str, expected: bool) -> None:
        assert evaluate_expression(expr).item() is expected

    def test_replace(self) -> None:
        assert evaluate_expression("replace('hello', 'l', 'L')").item() == "heLLo"

    def test_split(self) -> None:
        result = evaluate_expression("split('a,b,c', ',')")
        assert result.item() == ["a", "b", "c"]

    def test_split_whitespace(self) -> None:
        result = evaluate_expression("split('  hello \\t world \\n foo  ')")
        assert result.item() == ["hello", "world", "foo"]

    def test_split_whitespace_method(self) -> None:
        result = evaluate_expression("'one  two\\tthree\\nfour'.split()")
        assert result.item() == ["one", "two", "three", "four"]

    def test_split_whitespace_empty(self) -> None:
        result = evaluate_expression("split('   ')")
        assert result.item() == []

    def test_split_maxsplit(self) -> None:
        result = evaluate_expression("split('a,b,c,d', ',', 2)")
        assert result.item() == ["a", "b", "c,d"]

    def test_split_maxsplit_method(self) -> None:
        result = evaluate_expression("'a/b/c/d'.split('/', 1)")
        assert result.item() == ["a", "b/c/d"]

    def test_rsplit(self) -> None:
        result = evaluate_expression("rsplit('a,b,c', ',')")
        assert result.item() == ["a", "b", "c"]

    def test_rsplit_whitespace(self) -> None:
        result = evaluate_expression("rsplit('  hello \\t world \\n foo  ')")
        assert result.item() == ["hello", "world", "foo"]

    def test_rsplit_whitespace_method(self) -> None:
        result = evaluate_expression("'one  two\\tthree'.rsplit()")
        assert result.item() == ["one", "two", "three"]

    def test_rsplit_maxsplit(self) -> None:
        result = evaluate_expression("rsplit('a,b,c,d', ',', 2)")
        assert result.item() == ["a,b", "c", "d"]

    def test_rsplit_maxsplit_method(self) -> None:
        result = evaluate_expression("'a/b/c/d'.rsplit('/', 1)")
        assert result.item() == ["a/b/c", "d"]

    def test_rsplit_no_match(self) -> None:
        result = evaluate_expression("rsplit('abc', ',')")
        assert result.item() == ["abc"]

    def test_zfill_string(self) -> None:
        assert evaluate_expression("zfill('42', 5)").item() == "00042"

    def test_zfill_int(self) -> None:
        assert evaluate_expression("zfill(42, 5)").item() == "00042"

    def test_zfill_float(self) -> None:
        assert evaluate_expression("zfill(3.14, 8)").item() == "00003.14"

    def test_zfill_float_negative(self) -> None:
        assert evaluate_expression("zfill(-2.5, 8)").item() == "-00002.5"

    def test_zfill_float_preserves_round_precision(self) -> None:
        """zfill(float) uses to_string() so round() precision is preserved."""
        assert evaluate_expression("zfill(round(0.3, 2), 7)").item() == "0000.30"

    def test_zfill_float_method_syntax(self) -> None:
        assert evaluate_expression("(3.14).zfill(8)").item() == "00003.14"

    def test_len(self) -> None:
        assert evaluate_expression("len('hello')").item() == 5

    def test_find_found(self) -> None:
        assert evaluate_expression("find('hello', 'ell')").item() == 1

    def test_find_not_found(self) -> None:
        assert evaluate_expression("find('hello', 'xyz')").item() == -1

    def test_find_at_start(self) -> None:
        assert evaluate_expression("find('hello', 'hel')").item() == 0

    def test_find_empty_substring(self) -> None:
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("find('hello', '')")
        assert str(exc_info.value) == "".join(
            [
                "find failed: empty substring\n",
                "  find('hello', '')\n",
                "  ^~~~~~~~~~~~~~~~~",
            ]
        )

    def test_find_method_syntax(self) -> None:
        assert evaluate_expression("'hello'.find('lo')").item() == 3

    def test_rfind_found(self) -> None:
        assert evaluate_expression("rfind('hello hello', 'hello')").item() == 6

    def test_rfind_not_found(self) -> None:
        assert evaluate_expression("rfind('hello', 'xyz')").item() == -1

    def test_rfind_empty_substring(self) -> None:
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("rfind('hello', '')")
        assert str(exc_info.value) == "".join(
            [
                "rfind failed: empty substring\n",
                "  rfind('hello', '')\n",
                "  ^~~~~~~~~~~~~~~~~~",
            ]
        )

    def test_rfind_method_syntax(self) -> None:
        assert evaluate_expression("'abcabc'.rfind('bc')").item() == 4

    def test_index_found(self) -> None:
        assert evaluate_expression("index('hello', 'ell')").item() == 1

    def test_index_not_found(self) -> None:
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("index('hello', 'xyz')")
        assert str(exc_info.value) == "".join(
            [
                "index failed: substring 'xyz' not found\n",
                "  index('hello', 'xyz')\n",
                "  ^~~~~~~~~~~~~~~~~~~~~",
            ]
        )

    def test_index_empty_substring(self) -> None:
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("index('hello', '')")
        assert str(exc_info.value) == "".join(
            [
                "index failed: empty substring\n",
                "  index('hello', '')\n",
                "  ^~~~~~~~~~~~~~~~~~",
            ]
        )

    def test_index_method_syntax(self) -> None:
        assert evaluate_expression("'hello'.index('lo')").item() == 3

    def test_rindex_found(self) -> None:
        assert evaluate_expression("rindex('hello hello', 'hello')").item() == 6

    def test_rindex_not_found(self) -> None:
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("rindex('hello', 'xyz')")
        assert str(exc_info.value) == "".join(
            [
                "rindex failed: substring 'xyz' not found\n",
                "  rindex('hello', 'xyz')\n",
                "  ^~~~~~~~~~~~~~~~~~~~~~",
            ]
        )

    def test_rindex_empty_substring(self) -> None:
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("rindex('hello', '')")
        assert str(exc_info.value) == "".join(
            [
                "rindex failed: empty substring\n",
                "  rindex('hello', '')\n",
                "  ^~~~~~~~~~~~~~~~~~~",
            ]
        )

    def test_rindex_method_syntax(self) -> None:
        assert evaluate_expression("'abcabc'.rindex('bc')").item() == 4

    def test_count_empty_substring(self) -> None:
        with pytest.raises(ExpressionError, match="count failed: empty substring"):
            evaluate_expression("count('hello', '')")

    def test_replace_empty_old(self) -> None:
        with pytest.raises(ExpressionError, match="replace failed: empty old string"):
            evaluate_expression("'hello'.replace('', 'x')")

    def test_rsplit_empty_separator(self) -> None:
        with pytest.raises(ExpressionError, match="split failed"):
            evaluate_expression("'abc'.rsplit('')")

    def test_split_empty_string(self) -> None:
        """Splitting an empty string returns [''], not []."""
        r = evaluate_expression("''.split(',')")
        assert r.item() == [""]


class TestRemovePrefixSuffix:
    """Tests for removeprefix and removesuffix string functions."""

    def test_removeprefix_present(self) -> None:
        assert evaluate_expression("removeprefix('hello world', 'hello ')").item() == "world"

    def test_removeprefix_not_present(self) -> None:
        assert evaluate_expression("removeprefix('hello world', 'bye ')").item() == "hello world"

    def test_removeprefix_empty_prefix(self) -> None:
        assert evaluate_expression("removeprefix('hello', '')").item() == "hello"

    def test_removeprefix_full_string(self) -> None:
        assert evaluate_expression("removeprefix('hello', 'hello')").item() == ""

    def test_removeprefix_method_syntax(self) -> None:
        assert evaluate_expression("'hello world'.removeprefix('hello ')").item() == "world"

    def test_removesuffix_present(self) -> None:
        assert evaluate_expression("removesuffix('hello.txt', '.txt')").item() == "hello"

    def test_removesuffix_not_present(self) -> None:
        assert evaluate_expression("removesuffix('hello.txt', '.py')").item() == "hello.txt"

    def test_removesuffix_empty_suffix(self) -> None:
        assert evaluate_expression("removesuffix('hello', '')").item() == "hello"

    def test_removesuffix_full_string(self) -> None:
        assert evaluate_expression("removesuffix('hello', 'hello')").item() == ""

    def test_removesuffix_method_syntax(self) -> None:
        assert evaluate_expression("'hello.txt'.removesuffix('.txt')").item() == "hello"

    def test_removesuffix_compound_extension(self) -> None:
        """Test removing compound extensions like .tar.gz."""
        assert evaluate_expression("'archive.tar.gz'.removesuffix('.tar.gz')").item() == "archive"

    def test_removesuffix_with_suffixes_join(self) -> None:
        """Test the pattern for getting bare stem from compound extensions."""
        from openjd.expr import SymbolTable, ExprValue
        from openjd.expr import PathFormat

        symtab = SymbolTable(
            {"P": ExprValue("/data/archive.tar.gz", type="path", path_format=PathFormat.POSIX)}
        )
        result = evaluate_expression(
            "P.name.removesuffix(P.suffixes.join(''))",
            values=symtab,
            path_format=PathFormat.POSIX,
        )
        assert result.item() == "archive"


class TestStringMembership:
    """Tests for string in/not in operators (substring test)."""

    def test_substring_in_string(self) -> None:
        assert evaluate_expression('"ell" in "hello"').item() is True

    def test_substring_not_in_string(self) -> None:
        assert evaluate_expression('"xyz" in "hello"').item() is False

    def test_substring_at_start(self) -> None:
        assert evaluate_expression('"hel" in "hello"').item() is True

    def test_substring_at_end(self) -> None:
        assert evaluate_expression('"llo" in "hello"').item() is True

    def test_full_string_match(self) -> None:
        assert evaluate_expression('"hello" in "hello"').item() is True

    def test_empty_string_in_string(self) -> None:
        assert evaluate_expression('"" in "hello"').item() is True

    def test_string_in_empty_string(self) -> None:
        assert evaluate_expression('"a" in ""').item() is False

    def test_empty_in_empty(self) -> None:
        assert evaluate_expression('"" in ""').item() is True

    def test_not_in_operator_true(self) -> None:
        assert evaluate_expression('"xyz" not in "hello"').item() is True

    def test_not_in_operator_false(self) -> None:
        assert evaluate_expression('"ell" not in "hello"').item() is False

    def test_case_sensitive(self) -> None:
        assert evaluate_expression('"HELLO" in "hello"').item() is False
        assert evaluate_expression('"hello" in "HELLO"').item() is False

    def test_with_spaces(self) -> None:
        assert evaluate_expression('"lo wo" in "hello world"').item() is True

    def test_method_style_not_supported(self) -> None:
        # The 'in' operator is not a method, so this tests the function form
        # Using variables to test with symbol table
        from openjd.expr import SymbolTable

        symtab = SymbolTable({"haystack": "hello world", "needle": "world"})
        assert evaluate_expression("needle in haystack", values=symtab).item() is True


class TestReprFunctions:
    """Tests for repr_py, repr_json, and repr_pwsh functions."""

    def test_repr_py_list_string(self) -> None:
        assert evaluate_expression("repr_py(['a', 'b', 'c'])").item() == "['a', 'b', 'c']"

    def test_repr_py_list_int(self) -> None:
        assert evaluate_expression("repr_py([1, 2, 3])").item() == "[1, 2, 3]"

    def test_repr_py_list_bool(self) -> None:
        assert evaluate_expression("repr_py([True, False])").item() == "[True, False]"

    def test_repr_json_list_string(self) -> None:
        assert evaluate_expression("repr_json(['a', 'b', 'c'])").item() == '["a", "b", "c"]'

    def test_repr_json_list_int(self) -> None:
        assert evaluate_expression("repr_json([1, 2, 3])").item() == "[1, 2, 3]"

    def test_repr_json_list_bool(self) -> None:
        assert evaluate_expression("repr_json([True, False])").item() == "[true, false]"

    def test_repr_json_null(self) -> None:
        assert evaluate_expression("repr_json(null)").item() == "null"
        assert evaluate_expression("repr_json(None)").item() == "null"

    def test_repr_py_null(self) -> None:
        assert evaluate_expression("repr_py(null)").item() == "None"
        assert evaluate_expression("repr_py(None)").item() == "None"

    def test_repr_py_path(self, tmp_path) -> None:
        import sys
        from openjd.expr import SymbolTable, ExprValue
        from openjd.expr import PathFormat

        host_pf = PathFormat.WINDOWS if sys.platform == "win32" else PathFormat.POSIX
        p = tmp_path / "test.txt"
        symtab = SymbolTable({"p": ExprValue(str(p), type="path", path_format=host_pf)})
        result = evaluate_expression("repr_py(p)", values=symtab)
        assert result.item() == repr(str(p))

    def test_repr_py_list_path(self, tmp_path) -> None:
        import sys
        from openjd.expr import SymbolTable, ExprValue
        from openjd.expr import PathFormat

        host_pf = PathFormat.WINDOWS if sys.platform == "win32" else PathFormat.POSIX
        paths = [tmp_path / "a.txt", tmp_path / "b.txt"]
        symtab = SymbolTable(
            {
                "paths": ExprValue(
                    [ExprValue(str(p), type="path", path_format=host_pf) for p in paths]
                )
            }
        )
        result = evaluate_expression("repr_py(paths)", values=symtab)
        assert result.item() == repr([str(p) for p in paths])

    def test_repr_json_list_path(self, tmp_path) -> None:
        import json
        import sys

        from openjd.expr import SymbolTable, ExprValue
        from openjd.expr import PathFormat

        host_pf = PathFormat.WINDOWS if sys.platform == "win32" else PathFormat.POSIX
        paths = [tmp_path / "a.txt", tmp_path / "b.txt"]
        symtab = SymbolTable(
            {
                "paths": ExprValue(
                    [ExprValue(str(p), type="path", path_format=host_pf) for p in paths]
                )
            }
        )
        result = evaluate_expression("repr_json(paths)", values=symtab)
        assert result.item() == json.dumps([str(p) for p in paths])

    def test_repr_py_range_expr(self) -> None:
        from openjd.expr import SymbolTable
        from openjd.expr import RangeExpr

        symtab = SymbolTable({"Frames": RangeExpr("1-5")})
        assert evaluate_expression("repr_py(Frames)", values=symtab).item() == "'1-5'"

    def test_repr_json_range_expr(self) -> None:
        from openjd.expr import SymbolTable
        from openjd.expr import RangeExpr

        symtab = SymbolTable({"Frames": RangeExpr("1-5")})
        assert evaluate_expression("repr_json(Frames)", values=symtab).item() == '"1-5"'

    def test_repr_pwsh_string(self) -> None:
        assert evaluate_expression("repr_pwsh('hello world')").item() == "'hello world'"
        assert evaluate_expression('repr_pwsh("it\'s")').item() == "'it''s'"

    def test_repr_pwsh_int(self) -> None:
        assert evaluate_expression("repr_pwsh(42)").item() == "42"

    def test_repr_pwsh_float(self) -> None:
        assert evaluate_expression("repr_pwsh(3.14)").item() == "3.14"

    def test_repr_pwsh_bool(self) -> None:
        assert evaluate_expression("repr_pwsh(true)").item() == "$true"
        assert evaluate_expression("repr_pwsh(false)").item() == "$false"

    def test_repr_pwsh_list(self) -> None:
        assert evaluate_expression("repr_pwsh(['a', 'b', 'c'])").item() == "@('a', 'b', 'c')"
        assert evaluate_expression("repr_pwsh([\"it's\", 'done'])").item() == "@('it''s', 'done')"

    def test_repr_pwsh_path(self, tmp_path) -> None:
        import sys
        from openjd.expr import SymbolTable, ExprValue
        from openjd.expr import PathFormat

        host_pf = PathFormat.WINDOWS if sys.platform == "win32" else PathFormat.POSIX
        render_file = tmp_path / "Users" / "John's Files" / "render.exr"
        symtab = SymbolTable(
            {"MyPath": ExprValue(str(render_file), type="path", path_format=host_pf)}
        )
        result = evaluate_expression("repr_pwsh(MyPath)", values=symtab).item()
        # Path value uses native separators, then gets single-quoted for PowerShell
        expected_path = str(render_file)
        assert result == "'" + expected_path.replace("'", "''") + "'"


class TestReprPwshComprehensive:
    """Comprehensive tests for repr_pwsh covering all type overloads."""

    # String tests
    def test_pwsh_string_simple(self) -> None:
        assert evaluate_expression("repr_pwsh('hello')").item() == "'hello'"

    def test_pwsh_string_with_spaces(self) -> None:
        assert evaluate_expression("repr_pwsh('hello world')").item() == "'hello world'"

    def test_pwsh_string_with_single_quote(self) -> None:
        assert evaluate_expression('repr_pwsh("it\'s")').item() == "'it''s'"

    def test_pwsh_string_with_multiple_quotes(self) -> None:
        assert evaluate_expression("repr_pwsh(\"it's John's\")").item() == "'it''s John''s'"

    def test_pwsh_string_with_double_quote(self) -> None:
        # Double quotes don't need escaping in single-quoted PowerShell strings
        assert evaluate_expression("repr_pwsh('say \"hi\"')").item() == "'say \"hi\"'"

    def test_pwsh_string_with_dollar(self) -> None:
        # $ doesn't expand in single-quoted PowerShell strings
        assert evaluate_expression("repr_pwsh('$var')").item() == "'$var'"

    def test_pwsh_string_with_backtick(self) -> None:
        assert evaluate_expression("repr_pwsh('hello`nworld')").item() == "'hello`nworld'"

    def test_pwsh_string_empty(self) -> None:
        assert evaluate_expression("repr_pwsh('')").item() == "''"

    # Int tests
    def test_pwsh_int_positive(self) -> None:
        assert evaluate_expression("repr_pwsh(42)").item() == "42"

    def test_pwsh_int_negative(self) -> None:
        assert evaluate_expression("repr_pwsh(-123)").item() == "-123"

    def test_pwsh_int_zero(self) -> None:
        assert evaluate_expression("repr_pwsh(0)").item() == "0"

    # Float tests
    def test_pwsh_float_simple(self) -> None:
        assert evaluate_expression("repr_pwsh(3.14)").item() == "3.14"

    def test_pwsh_float_negative(self) -> None:
        assert evaluate_expression("repr_pwsh(-2.5)").item() == "-2.5"

    def test_pwsh_float_integer_value(self) -> None:
        assert evaluate_expression("repr_pwsh(5.0)").item() == "5.0"

    # Bool tests
    def test_pwsh_bool_true(self) -> None:
        assert evaluate_expression("repr_pwsh(true)").item() == "$true"

    def test_pwsh_bool_false(self) -> None:
        assert evaluate_expression("repr_pwsh(false)").item() == "$false"

    # Path tests
    def test_pwsh_path_simple(self, tmp_path) -> None:
        import sys
        from openjd.expr import SymbolTable, ExprValue
        from openjd.expr import PathFormat

        host_pf = PathFormat.WINDOWS if sys.platform == "win32" else PathFormat.POSIX
        p = tmp_path / "file.txt"
        symtab = SymbolTable({"P": ExprValue(str(p), type="path", path_format=host_pf)})
        assert evaluate_expression("repr_pwsh(P)", values=symtab).item() == f"'{p}'"

    def test_pwsh_path_windows(self, tmp_path) -> None:
        import sys
        from openjd.expr import SymbolTable, ExprValue
        from openjd.expr import PathFormat

        host_pf = PathFormat.WINDOWS if sys.platform == "win32" else PathFormat.POSIX
        p = tmp_path / "Program Files" / "App" / "file.exe"
        symtab = SymbolTable({"P": ExprValue(str(p), type="path", path_format=host_pf)})
        assert evaluate_expression("repr_pwsh(P)", values=symtab).item() == f"'{p}'"

    def test_pwsh_path_with_quote(self, tmp_path) -> None:
        import sys
        from openjd.expr import SymbolTable, ExprValue
        from openjd.expr import PathFormat

        host_pf = PathFormat.WINDOWS if sys.platform == "win32" else PathFormat.POSIX
        p = tmp_path / "Users" / "O'Brien" / "file.txt"
        symtab = SymbolTable({"P": ExprValue(str(p), type="path", path_format=host_pf)})
        assert (
            evaluate_expression("repr_pwsh(P)", values=symtab).item()
            == "'" + str(p).replace("'", "''") + "'"
        )

    # List tests
    def test_pwsh_list_empty(self) -> None:
        assert evaluate_expression("repr_pwsh([])").item() == "@()"

    def test_pwsh_list_single(self) -> None:
        assert evaluate_expression("repr_pwsh(['one'])").item() == "@('one')"

    def test_pwsh_list_multiple(self) -> None:
        assert evaluate_expression("repr_pwsh(['a', 'b', 'c'])").item() == "@('a', 'b', 'c')"

    def test_pwsh_list_with_quotes(self) -> None:
        assert (
            evaluate_expression('repr_pwsh(["it\'s", "John\'s"])').item() == "@('it''s', 'John''s')"
        )

    def test_pwsh_list_with_spaces(self) -> None:
        assert (
            evaluate_expression("repr_pwsh(['hello world', 'foo bar'])").item()
            == "@('hello world', 'foo bar')"
        )

    def test_pwsh_list_of_ints(self) -> None:
        assert evaluate_expression("repr_pwsh([1, 2, 3])").item() == "@(1, 2, 3)"

    def test_pwsh_list_of_floats(self) -> None:
        assert evaluate_expression("repr_pwsh([1.5, 2.5])").item() == "@(1.5, 2.5)"

    def test_pwsh_list_of_bools(self) -> None:
        assert evaluate_expression("repr_pwsh([true, false])").item() == "@($true, $false)"

    def test_pwsh_range_expr(self) -> None:
        from openjd.expr import SymbolTable
        from openjd.expr import RangeExpr

        symtab = SymbolTable({"Frames": RangeExpr("1-5")})
        assert evaluate_expression("repr_pwsh(Frames)", values=symtab).item() == "'1-5'"

    def test_pwsh_range_expr_with_step(self) -> None:
        from openjd.expr import SymbolTable
        from openjd.expr import RangeExpr

        symtab = SymbolTable({"Frames": RangeExpr("1-10:2")})
        # Range normalizes to actual end value (9 is last value in 1,3,5,7,9)
        assert evaluate_expression("repr_pwsh(Frames)", values=symtab).item() == "'1-9:2'"

    def test_pwsh_range_expr_as_list(self) -> None:
        """To get expanded array, use list() first."""
        from openjd.expr import SymbolTable
        from openjd.expr import RangeExpr

        symtab = SymbolTable({"Frames": RangeExpr("1-3")})
        assert evaluate_expression("repr_pwsh(list(Frames))", values=symtab).item() == "@(1, 2, 3)"


@pytest.mark.skipif(os.name != "nt", reason="PowerShell validation only on Windows")
class TestReprPwshWindowsValidation:
    """Validate repr_pwsh output by running PowerShell subprocess on Windows."""

    def _pwsh_eval(self, expr: str) -> str:
        """Write expr to a temporary .ps1 file and execute it, so PowerShell
        interprets the repr_pwsh output exactly once (no argument-layer parsing)."""
        import subprocess
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".ps1", delete=False) as f:
            f.write(expr + "\n")
            ps1_path = f.name
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1_path],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip()
        finally:
            os.remove(ps1_path)

    def test_pwsh_string_simple_roundtrip(self) -> None:
        quoted = evaluate_expression("repr_pwsh('hello')").item()
        assert self._pwsh_eval(f"Write-Output {quoted}") == "hello"

    def test_pwsh_string_roundtrip(self) -> None:
        quoted = evaluate_expression("repr_pwsh('hello world')").item()
        assert self._pwsh_eval(f"Write-Output {quoted}") == "hello world"

    def test_pwsh_string_empty_roundtrip(self) -> None:
        quoted = evaluate_expression("repr_pwsh('')").item()
        assert self._pwsh_eval(f"Write-Output {quoted}") == ""

    def test_pwsh_string_with_quote_roundtrip(self) -> None:
        quoted = evaluate_expression('repr_pwsh("it\'s")').item()
        assert self._pwsh_eval(f"Write-Output {quoted}") == "it's"

    def test_pwsh_string_with_double_quote_roundtrip(self) -> None:
        quoted = evaluate_expression("repr_pwsh('say \"hi\"')").item()
        assert self._pwsh_eval(f"Write-Output {quoted}") == 'say "hi"'

    def test_pwsh_string_with_dollar_roundtrip(self) -> None:
        quoted = evaluate_expression("repr_pwsh('$HOME')").item()
        assert self._pwsh_eval(f"Write-Output {quoted}") == "$HOME"

    def test_pwsh_string_with_backtick_roundtrip(self) -> None:
        quoted = evaluate_expression("repr_pwsh('hello`nworld')").item()
        assert self._pwsh_eval(f"Write-Output {quoted}") == "hello`nworld"

    def test_pwsh_int_roundtrip(self) -> None:
        quoted = evaluate_expression("repr_pwsh(42)").item()
        assert self._pwsh_eval(f"Write-Output {quoted}") == "42"

    def test_pwsh_float_roundtrip(self) -> None:
        quoted = evaluate_expression("repr_pwsh(3.14)").item()
        assert self._pwsh_eval(f"Write-Output {quoted}") == "3.14"

    def test_pwsh_bool_true_roundtrip(self) -> None:
        quoted = evaluate_expression("repr_pwsh(true)").item()
        assert self._pwsh_eval(f"Write-Output {quoted}") == "True"

    def test_pwsh_bool_false_roundtrip(self) -> None:
        quoted = evaluate_expression("repr_pwsh(false)").item()
        assert self._pwsh_eval(f"Write-Output {quoted}") == "False"

    def test_pwsh_list_roundtrip(self) -> None:
        quoted = evaluate_expression("repr_pwsh(['a', 'b', 'c'])").item()
        result = self._pwsh_eval(f"{quoted} -join ','")
        assert result == "a,b,c"

    def test_pwsh_list_with_quotes_roundtrip(self) -> None:
        quoted = evaluate_expression('repr_pwsh(["it\'s", "John\'s"])').item()
        result = self._pwsh_eval(f"{quoted} -join ','")
        assert result == "it's,John's"


class TestStringLiteralFormats:
    """Tests for string literal formats per RFC 5 grammar."""

    # Quote styles
    def test_single_quoted(self) -> None:
        assert evaluate_expression("'hello'").item() == "hello"

    def test_double_quoted(self) -> None:
        assert evaluate_expression('"hello"').item() == "hello"

    def test_triple_single_quoted(self) -> None:
        assert evaluate_expression("'''hello'''").item() == "hello"

    def test_triple_double_quoted(self) -> None:
        assert evaluate_expression('"""hello"""').item() == "hello"

    def test_triple_quoted_multiline(self) -> None:
        result = evaluate_expression('"""line1\nline2"""')
        assert result.item() == "line1\nline2"

    def test_triple_quoted_with_quotes_inside(self) -> None:
        assert evaluate_expression('"""he said "hi" """').item() == 'he said "hi" '

    # Escape sequences
    def test_escape_newline(self) -> None:
        assert evaluate_expression(r"'hello\nworld'").item() == "hello\nworld"

    def test_escape_tab(self) -> None:
        assert evaluate_expression(r"'hello\tworld'").item() == "hello\tworld"

    def test_escape_backslash(self) -> None:
        assert evaluate_expression(r"'hello\\world'").item() == "hello\\world"

    def test_escape_single_quote(self) -> None:
        assert evaluate_expression(r"'it\'s'").item() == "it's"

    def test_escape_double_quote(self) -> None:
        assert evaluate_expression(r'"say \"hi\""').item() == 'say "hi"'

    def test_escape_hex(self) -> None:
        assert evaluate_expression(r"'\x41'").item() == "A"

    def test_escape_unicode_16bit(self) -> None:
        assert evaluate_expression(r"'\u0041'").item() == "A"

    def test_escape_unicode_32bit(self) -> None:
        assert evaluate_expression(r"'\U00000041'").item() == "A"

    def test_escape_unicode_name(self) -> None:
        assert evaluate_expression(r"'\N{LATIN CAPITAL LETTER A}'").item() == "A"

    # Raw strings
    def test_raw_string_lowercase_r(self) -> None:
        assert evaluate_expression(r"r'hello\nworld'").item() == r"hello\nworld"

    def test_raw_string_uppercase_r(self) -> None:
        assert evaluate_expression(r"R'hello\nworld'").item() == r"hello\nworld"

    def test_raw_string_double_quoted(self) -> None:
        assert evaluate_expression(r'r"hello\nworld"').item() == r"hello\nworld"

    def test_raw_string_backslash_preserved(self) -> None:
        # In raw strings, backslashes are literal
        result = evaluate_expression(r"r'C:\Users\test'")
        assert result.item() == r"C:\Users\test"

    def test_raw_triple_quoted(self) -> None:
        assert evaluate_expression(r"r'''hello\nworld'''").item() == r"hello\nworld"

    # Unicode content
    def test_unicode_characters(self) -> None:
        assert evaluate_expression("'héllo'").item() == "héllo"

    def test_unicode_cjk(self) -> None:
        assert evaluate_expression("'日本語'").item() == "日本語"

    def test_unicode_emoji(self) -> None:
        assert evaluate_expression("'🎉'").item() == "🎉"


class TestRejectedStringFormats:
    """Tests for string formats that should be rejected."""

    def test_fstring_rejected(self) -> None:
        with pytest.raises(ExpressionError):
            evaluate_expression('f"hello {1+1}"')

    def test_fstring_single_quote_rejected(self) -> None:
        with pytest.raises(ExpressionError):
            evaluate_expression("f'hello {1+1}'")

    def test_bytes_literal_rejected(self) -> None:
        with pytest.raises(ExpressionError):
            evaluate_expression('b"hello"')

    def test_bytes_single_quote_rejected(self) -> None:
        with pytest.raises(ExpressionError):
            evaluate_expression("b'hello'")

    def test_unicode_prefix_rejected_parse(self) -> None:
        """Python 2 style u'...' prefix is rejected at parse time."""
        from openjd.expr import parse_expression

        with pytest.raises(ExpressionError) as exc_info:
            parse_expression('u"hello"')
        expected = [
            "Unicode string prefix u'...' is not supported. Use '...' or \"...\" instead.\n",
            '  u"hello"\n',
            "  ^~~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_unicode_prefix_rejected_evaluate(self) -> None:
        """Python 2 style u'...' prefix is rejected via evaluate_expression."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression('u"hello"')
        expected = [
            "Unicode string prefix u'...' is not supported. Use '...' or \"...\" instead.\n",
            '  u"hello"\n',
            "  ^~~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_unicode_prefix_in_expression(self) -> None:
        """u'...' prefix in larger expression points to correct location."""
        from openjd.expr import parse_expression

        with pytest.raises(ExpressionError) as exc_info:
            parse_expression('1 + u"hello"')
        expected = [
            "Unicode string prefix u'...' is not supported. Use '...' or \"...\" instead.\n",
            '  1 + u"hello"\n',
            "      ^~~~~~~~",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_raw_bytes_rejected(self) -> None:
        with pytest.raises(ExpressionError):
            evaluate_expression('rb"hello"')

    def test_br_bytes_rejected(self) -> None:
        with pytest.raises(ExpressionError):
            evaluate_expression('br"hello"')

    def test_raw_fstring_rejected(self) -> None:
        with pytest.raises(ExpressionError):
            evaluate_expression('rf"hello {1}"')

    def test_fr_string_rejected(self) -> None:
        with pytest.raises(ExpressionError):
            evaluate_expression('fr"hello {1}"')


class TestRegexWithRawStrings:
    """Tests for regex functions using raw string literals."""

    def test_re_search_with_group(self) -> None:
        """re_search returns [full_match, group1, ...]."""
        result = evaluate_expression('re_search("hello123", r"(\\d+)")')
        assert result.item() == ["123", "123"]  # full match, group1

    def test_re_search_no_match(self) -> None:
        """re_search returns null when no match."""
        assert evaluate_expression('re_search("hello", r"\\d+")').item() is None

    def test_re_search_no_groups(self) -> None:
        """re_search with no capture groups returns [full_match]."""
        result = evaluate_expression('re_search("hello123", r"\\d+")')
        assert result.item() == ["123"]

    def test_re_search_multiple_groups(self) -> None:
        """re_search with multiple groups returns [full, g1, g2, ...]."""
        result = evaluate_expression('re_search("hello123world", r"(\\d+)(\\w+)")')
        assert result.item() == ["123world", "123", "world"]

    def test_re_match_at_start(self) -> None:
        """re_match only matches at start of string."""
        result = evaluate_expression('re_match("hello", r"hel")')
        assert result.item() == ["hel"]

    def test_re_match_not_at_start(self) -> None:
        """re_match returns null if pattern not at start."""
        assert evaluate_expression('re_match("hello", r"llo")').item() is None

    def test_re_match_with_groups(self) -> None:
        """re_match returns [full_match, group1, ...]."""
        result = evaluate_expression('re_match("v042_final", r"v(\\d+)")')
        assert result.item() == ["v042", "042"]

    def test_re_findall_multiple(self) -> None:
        """re_findall returns all matches."""
        result = evaluate_expression('re_findall("a1b2c3", r"\\d")')
        assert result.item() == ["1", "2", "3"]

    def test_re_findall_with_groups(self) -> None:
        """re_findall with one group returns group values."""
        result = evaluate_expression('re_findall("shot010_shot020", r"shot(\\d+)")')
        assert result.item() == ["010", "020"]

    def test_re_findall_with_multiple_groups(self) -> None:
        """re_findall with multiple groups returns list of group lists."""
        result = evaluate_expression(r're_findall("v1.2.3 and v4.5.6", r"v(\d+)\.(\d+)\.(\d+)")')
        assert result.item() == [["1", "2", "3"], ["4", "5", "6"]]

    def test_re_findall_no_matches(self) -> None:
        """re_findall returns empty list when no matches."""
        result = evaluate_expression('re_findall("hello", r"\\d+")')
        assert result.item() == []

    def test_re_sub_digits(self) -> None:
        assert evaluate_expression('re_sub("a1b2c3", r"\\d", "X")').item() == "aXbXcX"

    def test_re_sub_whitespace(self) -> None:
        assert evaluate_expression('re_sub("a b  c", r"\\s+", "-")').item() == "a-b-c"

    def test_re_search_method_syntax(self) -> None:
        """Method syntax works for re_search."""
        result = evaluate_expression('"test123".re_search(r"(\\d+)")')
        assert result.item() == ["123", "123"]

    def test_re_sub_method_syntax(self) -> None:
        result = evaluate_expression('"hello".re_sub(r"l+", "L")')
        assert result.item() == "heLo"

    def test_re_sub_group_ref_backslash(self) -> None:
        with pytest.raises(ExpressionError, match="Group references"):
            evaluate_expression(r"""re_sub('hello', '(h)', r'\1')""")

    def test_re_sub_group_ref_dollar(self) -> None:
        with pytest.raises(ExpressionError, match="Group references"):
            evaluate_expression(r"""re_sub('hello', '(h)', '$1')""")

    def test_re_sub_group_ref_named(self) -> None:
        with pytest.raises(ExpressionError, match="Group references"):
            evaluate_expression(r"""re_sub('hello', '(h)', r'\g<1>')""")

    def test_re_sub_group_ref_dollar_brace(self) -> None:
        with pytest.raises(ExpressionError, match="Group references"):
            evaluate_expression(r"""re_sub('hello', '(h)', '${1}')""")

    def test_re_search_empty_pattern(self) -> None:
        with pytest.raises(ExpressionError, match="Empty regex pattern"):
            evaluate_expression("""re_search('hello', '')""")

    def test_re_match_empty_pattern(self) -> None:
        with pytest.raises(ExpressionError, match="Empty regex pattern"):
            evaluate_expression("""re_match('hello', '')""")

    def test_re_findall_empty_pattern(self) -> None:
        with pytest.raises(ExpressionError, match="Empty regex pattern"):
            evaluate_expression("""re_findall('hello', '')""")

    def test_re_sub_empty_pattern(self) -> None:
        with pytest.raises(ExpressionError, match="Empty regex pattern"):
            evaluate_expression("""re_sub('hello', '', 'x')""")

    def test_re_search_boolean_check(self) -> None:
        """Pattern to check if match exists."""
        assert evaluate_expression('re_search("hello123", r"\\d+") != null').item() is True
        assert evaluate_expression('re_search("hello", r"\\d+") != null').item() is False

    def test_re_escape_metacharacters(self) -> None:
        """re_escape escapes regex metacharacters."""
        result = evaluate_expression('re_escape("file[1].txt")')
        assert result.item() == r"file\[1\]\.txt"

    def test_re_escape_with_search(self) -> None:
        """Escaped string can be used for literal matching."""
        result = evaluate_expression('re_search("file[1].txt", re_escape("[1]"))')
        assert result.item() == ["[1]"]

    def test_re_split(self) -> None:
        result = evaluate_expression(r're_split("one,two;three", r"[,;]")')
        assert result.item() == ["one", "two", "three"]

    def test_re_split_digits(self) -> None:
        result = evaluate_expression(r're_split("abc123def4567ghi89", r"[0-9]+")')
        assert result.item() == ["abc", "def", "ghi", ""]

    def test_re_split_whitespace(self) -> None:
        result = evaluate_expression(r're_split("  hello   world  ", r"\s+")')
        assert result.item() == ["", "hello", "world", ""]

    def test_re_split_multi_char_delimiter(self) -> None:
        result = evaluate_expression(r're_split("foo::bar:::baz", r":+")')
        assert result.item() == ["foo", "bar", "baz"]

    def test_re_split_date_separators(self) -> None:
        result = evaluate_expression(r're_split("2024-01-15", r"[-/]")')
        assert result.item() == ["2024", "01", "15"]

    def test_re_split_maxsplit(self) -> None:
        result = evaluate_expression(r're_split("a1b2c3d4e", r"[0-9]+", 2)')
        assert result.item() == ["a", "b", "c3d4e"]

    def test_re_split_kv_pairs(self) -> None:
        result = evaluate_expression(r're_split("key1=val1,key2=val2", r"[=,]")')
        assert result.item() == ["key1", "val1", "key2", "val2"]

    def test_re_split_method_syntax(self) -> None:
        result = evaluate_expression(r'"one::two::three".re_split(r"::")')
        assert result.item() == ["one", "two", "three"]

    def test_re_split_no_match(self) -> None:
        result = evaluate_expression(r're_split("hello", r",")')
        assert result.item() == ["hello"]

    def test_re_split_invalid_pattern(self) -> None:
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression(r're_split("hello", r"[")')
        assert str(exc_info.value) == "".join(
            [
                "Invalid regex pattern: regex parse error:\n",
                "    [\n",
                "    ^\n",
                "error: unclosed character class\n",
                '  re_split("hello", r"[")\n',
                "  ^~~~~~~~~~~~~~~~~~~~~~~",
            ]
        )

    def test_re_split_empty_pattern(self) -> None:
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("re_split('hello', '')")
        assert str(exc_info.value) == "".join(
            [
                "Empty regex pattern is not allowed\n",
                "  re_split('hello', '')\n",
                "  ^~~~~~~~~~~~~~~~~~~~~",
            ]
        )

    def test_re_split_maxsplit_empty_pattern(self) -> None:
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("re_split('hello', '', 2)")
        assert str(exc_info.value) == "".join(
            [
                "Empty regex pattern is not allowed\n",
                "  re_split('hello', '', 2)\n",
                "  ^~~~~~~~~~~~~~~~~~~~~~~~",
            ]
        )


class TestRegexUnsupportedFeatures:
    """Tests that unsupported regex features are rejected for cross-platform compatibility."""

    def test_backreference_rejected(self) -> None:
        with pytest.raises(ExpressionError, match="backreferences"):
            evaluate_expression(r're_search("abab", r"(ab)\1")')

    def test_lookahead_rejected(self) -> None:
        with pytest.raises(ExpressionError, match="lookahead"):
            evaluate_expression(r're_search("foobar", r"foo(?=bar)")')

    def test_negative_lookahead_rejected(self) -> None:
        with pytest.raises(ExpressionError, match="negative lookahead"):
            evaluate_expression(r're_search("foobar", r"foo(?!baz)")')

    def test_lookbehind_rejected(self) -> None:
        with pytest.raises(ExpressionError, match="lookbehind"):
            evaluate_expression(r're_search("foobar", r"(?<=foo)bar")')

    def test_negative_lookbehind_rejected(self) -> None:
        with pytest.raises(ExpressionError, match="negative lookbehind"):
            evaluate_expression(r're_search("foobar", r"(?<!baz)bar")')

    def test_re_match_validates(self) -> None:
        with pytest.raises(ExpressionError, match="backreferences"):
            evaluate_expression(r're_match("abab", r"(ab)\1")')

    def test_re_findall_validates(self) -> None:
        with pytest.raises(ExpressionError, match="lookahead"):
            evaluate_expression(r're_findall("foobar", r"foo(?=bar)")')

    def test_re_sub_validates(self) -> None:
        with pytest.raises(ExpressionError, match="lookbehind"):
            evaluate_expression(r're_sub("foobar", r"(?<=foo)bar", "X")')

    def test_end_of_string_Z_rejected(self) -> None:
        """Python's \\Z is rejected (Rust uses \\z instead)."""
        with pytest.raises(ExpressionError, match=r"end-of-string anchor"):
            evaluate_expression(r're_search("foo", r"foo\Z")')


class TestRegexEscapedPatternsAccepted:
    """Tests that escaped versions of unsupported features are accepted as literals."""

    def test_escaped_backreference_accepted(self) -> None:
        """Literal \\1 in pattern should be accepted."""
        result = evaluate_expression(r're_search("test\\1", r"\\1")')
        assert result.item() == ["\\1"]

    def test_escaped_lookahead_accepted(self) -> None:
        """Literal (?= in pattern should be accepted."""
        result = evaluate_expression(r're_search("foo(?=bar)", r"\(\?=bar\)")')
        assert result.item() == ["(?=bar)"]

    def test_escaped_lookbehind_accepted(self) -> None:
        """Literal (?<= in pattern should be accepted."""
        result = evaluate_expression(r're_search("(?<=foo)bar", r"\(\?<=foo\)")')
        assert result.item() == ["(?<=foo)"]

    def test_escaped_negative_lookahead_accepted(self) -> None:
        """Literal (?! in pattern should be accepted."""
        result = evaluate_expression(r're_search("foo(?!baz)", r"\(\?!baz\)")')
        assert result.item() == ["(?!baz)"]

    def test_escaped_negative_lookbehind_accepted(self) -> None:
        """Literal (?<! in pattern should be accepted."""
        result = evaluate_expression(r're_search("(?<!baz)bar", r"\(\?<!baz\)")')
        assert result.item() == ["(?<!baz)"]

    def test_double_backslash_lookahead_rejected(self) -> None:
        """Literal backslash followed by lookahead should be rejected."""
        with pytest.raises(ExpressionError, match="lookahead"):
            evaluate_expression(r're_search("test", r"\\(?=bar)")')


class TestReprCmdComprehensive:
    """Comprehensive tests for repr_cmd covering string and list overloads."""

    # String tests - simple cases
    def test_cmd_string_simple(self) -> None:
        assert evaluate_expression("repr_cmd('hello')").item() == "hello"

    def test_cmd_string_with_spaces(self) -> None:
        assert evaluate_expression("repr_cmd('hello world')").item() == '"hello world"'

    def test_cmd_string_empty(self) -> None:
        assert evaluate_expression("repr_cmd('')").item() == '""'

    def test_cmd_string_newline(self) -> None:
        # Newlines are stripped before quoting per spec (cmd.exe cannot safely embed them)
        assert evaluate_expression(r"repr_cmd('a\nb')").item() == "ab"

    def test_cmd_string_carriage_return(self) -> None:
        # Carriage returns are stripped before quoting per spec
        assert evaluate_expression(r"repr_cmd('a\rb')").item() == "ab"

    # String tests - special characters
    def test_cmd_string_ampersand(self) -> None:
        assert evaluate_expression("repr_cmd('a & b')").item() == '"a & b"'

    def test_cmd_string_pipe(self) -> None:
        assert evaluate_expression("repr_cmd('a | b')").item() == '"a | b"'

    def test_cmd_string_less_than(self) -> None:
        assert evaluate_expression("repr_cmd('a < b')").item() == '"a < b"'

    def test_cmd_string_greater_than(self) -> None:
        assert evaluate_expression("repr_cmd('a > b')").item() == '"a > b"'

    def test_cmd_string_caret(self) -> None:
        assert evaluate_expression("repr_cmd('a ^ b')").item() == '"a ^^ b"'

    def test_cmd_string_double_quote(self) -> None:
        assert evaluate_expression("""repr_cmd('say "hi"')""").item() == '"say ^"hi^""'

    def test_cmd_string_multiple_special(self) -> None:
        assert evaluate_expression("repr_cmd('a & b | c')").item() == '"a & b | c"'

    def test_cmd_string_all_special(self) -> None:
        result = evaluate_expression("""repr_cmd('&|<>^"')""").item()
        assert result == '"&|<>^^^""'

    # String tests - paths
    def test_cmd_string_windows_path(self) -> None:
        assert (
            evaluate_expression(r"repr_cmd('C:\\Program Files\\App')").item()
            == r'"C:\Program Files\App"'
        )

    def test_cmd_string_path_with_spaces(self) -> None:
        assert (
            evaluate_expression(r"repr_cmd('C:\\My Files\\data.txt')").item()
            == r'"C:\My Files\data.txt"'
        )

    # List tests
    def test_cmd_list_empty(self) -> None:
        assert evaluate_expression("repr_cmd([])").item() == ""

    def test_cmd_list_single(self) -> None:
        assert evaluate_expression("repr_cmd(['echo'])").item() == "echo"

    def test_cmd_list_multiple(self) -> None:
        assert (
            evaluate_expression("repr_cmd(['echo', 'hello', 'world'])").item() == "echo hello world"
        )

    def test_cmd_list_with_spaces(self) -> None:
        assert (
            evaluate_expression("repr_cmd(['echo', 'hello world'])").item() == 'echo "hello world"'
        )

    def test_cmd_list_with_special(self) -> None:
        assert (
            evaluate_expression("repr_cmd(['cmd', '/c', 'echo a & b'])").item()
            == 'cmd /c "echo a & b"'
        )

    def test_cmd_list_with_quotes(self) -> None:
        result = evaluate_expression("""repr_cmd(['echo', 'say "hi"'])""").item()
        assert result == 'echo "say ^"hi^""'

    # Pattern: set VAR=value for CMD environment variables
    def test_cmd_set_variable_pattern(self) -> None:
        """Test pattern for safe CMD variable assignment: set {{repr_cmd('VAR=' + path)}}"""
        result = evaluate_expression(
            r"'set ' + repr_cmd('OUTPUT_DIR=' + path('C:\\Users\\test&user\\output'))",
            path_format=PathFormat.WINDOWS,
        ).item()
        assert result == r'set "OUTPUT_DIR=C:\Users\test&user\output"'

    def test_cmd_set_variable_with_spaces(self) -> None:
        result = evaluate_expression(
            r"'set ' + repr_cmd('MY_PATH=' + path('C:\\Program Files\\App'))",
            path_format=PathFormat.WINDOWS,
        ).item()
        assert result == r'set "MY_PATH=C:\Program Files\App"'


@pytest.mark.skipif(os.name != "nt", reason="CMD validation only on Windows")
class TestReprCmdWindowsValidation:
    """Validate repr_cmd output by running CMD subprocess on Windows."""

    def _cmd_eval(self, cmd: str) -> str:
        """Write cmd to a temporary .bat file and execute it, so CMD
        interprets the repr_cmd output exactly once (no double shell layer)."""
        import subprocess
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".bat", delete=False) as f:
            f.write(f"@echo off\n{cmd}\n")
            bat_path = f.name
        try:
            result = subprocess.run(
                [bat_path],
                capture_output=True,
                text=True,
                timeout=10,
                shell=True,
            )
            return result.stdout.strip()
        finally:
            os.remove(bat_path)

    def test_cmd_string_simple_roundtrip(self) -> None:
        quoted = evaluate_expression("repr_cmd('hello')").item()
        assert self._cmd_eval(f"echo {quoted}") == "hello"

    def test_cmd_string_roundtrip(self) -> None:
        quoted = evaluate_expression("repr_cmd('hello world')").item()
        assert self._cmd_eval(f"echo {quoted}") == '"hello world"'

    def test_cmd_string_ampersand_roundtrip(self) -> None:
        quoted = evaluate_expression("repr_cmd('a & b')").item()
        assert self._cmd_eval(f"echo {quoted}") == '"a & b"'

    def test_cmd_string_all_special_roundtrip(self) -> None:
        quoted = evaluate_expression("""repr_cmd('&|<>^"')""").item()
        assert self._cmd_eval(f"echo {quoted}") == '"&|<>^^^""'

    def test_cmd_string_double_quote_roundtrip(self) -> None:
        quoted = evaluate_expression("""repr_cmd('say "hi"')""").item()
        assert self._cmd_eval(f"echo {quoted}") == '"say ^"hi""'

    def test_cmd_string_windows_path_roundtrip(self) -> None:
        quoted = evaluate_expression(r"repr_cmd('C:\\Program Files\\App')").item()
        assert self._cmd_eval(f"echo {quoted}") == r'"C:\Program Files\App"'

    def test_cmd_list_roundtrip(self) -> None:
        quoted = evaluate_expression("repr_cmd(['echo', 'hello'])").item()
        assert self._cmd_eval(quoted) == "hello"

    def test_cmd_list_special_roundtrip(self) -> None:
        quoted = evaluate_expression("repr_cmd(['echo', 'a & b'])").item()
        assert self._cmd_eval(quoted) == '"a & b"'

    def test_cmd_string_newline_roundtrip(self) -> None:
        """Verify newlines are stripped per spec — cmd.exe cannot safely embed
        them, so they are removed before any quoting logic runs."""
        # Newlines and carriage returns are stripped, leaving just the
        # surrounding text concatenated together.
        result = evaluate_expression(r"repr_cmd('a\nb')").item()
        assert result == "ab", f"Expected newline stripped, got: {result!r}"
        result_cr = evaluate_expression(r"repr_cmd('a\rb')").item()
        assert result_cr == "ab", f"Expected CR stripped, got: {result_cr!r}"
        # Mixed newlines are all stripped
        result_mixed = evaluate_expression(r"repr_cmd('a\r\nb')").item()
        assert result_mixed == "ab", f"Expected CRLF stripped, got: {result_mixed!r}"

    def test_cmd_set_variable_roundtrip(self) -> None:
        # Note: CMD's set "VAR=value" does not protect & inside the value;
        # the & is interpreted as a command separator. This is a known CMD
        # limitation — set requires ^& escaping even inside double quotes.
        cmd = evaluate_expression(r"'set ' + repr_cmd('MY_VAR=hello world')").item()
        assert self._cmd_eval(f"{cmd}\necho %MY_VAR%") == "hello world"
