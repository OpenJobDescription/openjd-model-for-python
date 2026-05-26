# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for string/path operation counting (spec section 1.3.10 rule 3).

When a function processes a string or path value, ceil(len/256) is added
to the operation count. This ensures functions doing work proportional to
string length are bounded.
"""

import pytest
from openjd.expr import (
    evaluate_expression,
    parse_expression,
    ExpressionError,
)


def _ceil_div(n: int, d: int) -> int:
    """ceil(n / d) using integer arithmetic."""
    return -(-n // d)


class TestStringOperationCounting:
    """Tests that string processing adds ceil(len/256) to the operation count."""

    def test_short_string_upper(self) -> None:
        """Short string (<= 256 chars): ceil(5/256) = 1 string op."""
        result = parse_expression("'hello'.upper()").evaluate_with_metrics()
        # 1 (upper call) + 1 (ceil(5/256)) = 2
        assert result.operation_count == 2

    def test_empty_string_upper(self) -> None:
        """Empty string: 0 string ops (length 0)."""
        result = parse_expression("''.upper()").evaluate_with_metrics()
        # 1 (upper call) + 0 (empty string) = 1
        assert result.operation_count == 1

    def test_256_char_string_upper(self) -> None:
        """Exactly 256 chars: ceil(256/256) = 1 string op."""
        result = parse_expression("('a' * 256).upper()").evaluate_with_metrics()
        # __mul__: 1 call + ceil(256/256)=1 = 2
        # upper: 1 call + ceil(256/256)=1 = 2
        # total = 4
        assert result.operation_count == 4

    def test_257_char_string_upper(self) -> None:
        """257 chars crosses boundary: ceil(257/256) = 2 string ops."""
        result = parse_expression("('a' * 257).upper()").evaluate_with_metrics()
        # __mul__: 1 call + ceil(257/256)=2 = 3
        # upper: 1 call + ceil(257/256)=2 = 3
        # total = 6
        assert result.operation_count == 6

    def test_1000_char_string_upper(self) -> None:
        """1000 chars: ceil(1000/256) = 4 string ops per function."""
        result = parse_expression("('a' * 1000).upper()").evaluate_with_metrics()
        # __mul__: 1 + 4 = 5
        # upper: 1 + 4 = 5
        # total = 10
        assert result.operation_count == 10

    def test_string_replace(self) -> None:
        """replace() counts string ops on the input string."""
        result = parse_expression("('abc' * 100).replace('a', 'x')").evaluate_with_metrics()
        # __mul__: 1 + ceil(300/256)=2 = 3
        # replace: 1 + ceil(300/256)=2 = 3
        # total = 6
        assert result.operation_count == 6

    def test_string_split(self) -> None:
        """split() counts string ops on the input string."""
        result = parse_expression("('a,' * 200).split(',')").evaluate_with_metrics()
        # __mul__: 1 + ceil(400/256)=2 = 3
        # split: 1 + ceil(400/256)=2 = 3
        # total = 6
        assert result.operation_count == 6

    def test_string_concat(self) -> None:
        """String concatenation counts ops on both operands."""
        result = parse_expression("('a' * 300) + ('b' * 300)").evaluate_with_metrics()
        # __mul__ for 'a'*300: 1 + ceil(300/256)=2 = 3
        # __mul__ for 'b'*300: 1 + ceil(300/256)=2 = 3
        # __add__: 1 + ceil(600/256)=3 = 4
        # total = 10
        assert result.operation_count == 10

    def test_string_repetition(self) -> None:
        """String repetition counts ops on the result."""
        result = parse_expression("'a' * 1000").evaluate_with_metrics()
        # __mul__: 1 + ceil(1000/256)=4 = 5
        assert result.operation_count == 5

    def test_string_contains(self) -> None:
        """'in' operator on strings counts string ops."""
        result = parse_expression("'x' in ('a' * 500)").evaluate_with_metrics()
        # Rust counts: __mul__ (3) + __contains__ (3) + 1 dispatch = 7
        assert result.operation_count == 7

    def test_regex_search(self) -> None:
        """re_search() counts string ops on the input string and pattern."""
        result = parse_expression("re_search('a' * 500, r'b')").evaluate_with_metrics()
        # __mul__: 1 + ceil(500/256)=2 = 3
        # re_search: 1 + ceil((500+1)/256)=2 = 3
        # total = 6
        assert result.operation_count == 6

    def test_repr_sh_string(self) -> None:
        """repr_sh() on a string counts string ops."""
        result = parse_expression("repr_sh('a' * 500)").evaluate_with_metrics()
        # __mul__: 1 + ceil(500/256)=2 = 3
        # repr_sh: 1 + ceil(500/256)=2 = 3
        # total = 6
        assert result.operation_count == 6

    def test_len_does_not_count_string_ops(self) -> None:
        """len() is a simple lookup and does NOT add string ops."""
        result = parse_expression("len('a' * 1000)").evaluate_with_metrics()
        # __mul__: 1 + ceil(1000/256)=4 = 5
        # len: 1 (just the function call, no string processing)
        # total = 6
        assert result.operation_count == 6


class TestPathOperationCounting:
    """Tests that path processing adds ceil(len/256) to the operation count."""

    def test_path_name(self) -> None:
        """path.name counts string ops on the path string."""
        result = parse_expression("path('/a/b/c/d/e/f').name").evaluate_with_metrics()
        # path(): 1 + ceil(12/256)=1 = 2
        # .name: 1 + ceil(12/256)=1 = 2
        # total = 4
        assert result.operation_count == 4

    def test_path_parent(self) -> None:
        """path.parent counts string ops."""
        result = parse_expression("path('/a/b/c').parent").evaluate_with_metrics()
        # path(): 1 + ceil(6/256)=1 = 2
        # .parent: 1 + ceil(6/256)=1 = 2
        # total = 4
        assert result.operation_count == 4

    def test_path_join(self) -> None:
        """path / child counts string ops on both operands."""
        result = parse_expression("path('/a/b') / 'c/d'").evaluate_with_metrics()
        # path(): 1 + ceil(4/256)=1 = 2
        # /: 1 + ceil(8/256)=1 = 2
        # total = 4
        assert result.operation_count == 4

    def test_path_add_suffix(self) -> None:
        """path + suffix counts string ops."""
        result = parse_expression("path('/a/b/file') + '.txt'").evaluate_with_metrics()
        # path(): 1 + ceil(8/256)=1 = 2
        # +: 1 + ceil(12/256)=1 = 2
        # total = 4
        assert result.operation_count == 4


class TestStringOpLimitExceeded:
    """Tests that string operations can trigger the operation limit."""

    def test_large_string_upper_exceeds_limit(self) -> None:
        """Processing a large string can exceed a small operation limit."""
        # 'a' * 10000 then .upper()
        # __mul__: 1 + ceil(10000/256)=40 = 41
        # upper: 1 + ceil(10000/256)=40 = 41
        # total = 82
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("('a' * 10000).upper()", operation_limit=50)
        assert "exceeded limit" in str(exc_info.value).lower()

    def test_large_string_replace_exceeds_limit(self) -> None:
        """replace() on a large string can exceed a small operation limit."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("('a' * 10000).replace('a', 'b')", operation_limit=50)
        assert "exceeded limit" in str(exc_info.value).lower()

    def test_large_string_split_exceeds_limit(self) -> None:
        """split() on a large string can exceed a small operation limit."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("('a,' * 5000).split(',')", operation_limit=30)
        assert "exceeded limit" in str(exc_info.value).lower()

    def test_large_string_regex_exceeds_limit(self) -> None:
        """re_search() on a large string can exceed a small operation limit."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("re_search('a' * 10000, r'b')", operation_limit=50)
        assert "exceeded limit" in str(exc_info.value).lower()

    def test_large_string_repetition_exceeds_limit(self) -> None:
        """String repetition producing a large result exceeds limit."""
        # 'a' * 100000: 1 + ceil(100000/256) = 392
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("'a' * 100000", operation_limit=100)
        assert str(exc_info.value) == "".join(
            [
                "Expression operation count (392) exceeded limit (100)\n",
                "  'a' * 100000\n",
                "  ~~~~^~~~~~~~",
            ]
        )

    def test_chained_string_ops_accumulate(self) -> None:
        """Chained string operations accumulate string op counts."""
        # Each operation on a 1000-char string adds ceil(1000/256)=4 string ops
        # 'a'*1000: 1+4=5, .upper(): 1+4=5, .lower(): 1+4=5, .strip(): 1+4=5
        # total = 20
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("('a' * 1000).upper().lower().strip()", operation_limit=15)
        assert "exceeded limit" in str(exc_info.value).lower()

    def test_large_path_operation_exceeds_limit(self) -> None:
        """Path operations on long paths count string ops."""
        # path('a'*1000): 1+4=5 for path(), then .name: 1+4=5
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("path('a' * 1000).name", operation_limit=8)
        assert "exceeded limit" in str(exc_info.value).lower()

    def test_string_concat_large_exceeds_limit(self) -> None:
        """Concatenating large strings counts ops on both."""
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression("('a' * 5000) + ('b' * 5000)", operation_limit=50)
        assert "exceeded limit" in str(exc_info.value).lower()


class TestStringOpCountPrecise:
    """Precise operation count verification for various string functions."""

    @pytest.mark.parametrize(
        "expr, expected_count",
        [
            # lower: 1 call + ceil(5/256)=1 = 2
            ("'hello'.lower()", 2),
            # strip: 1 call + ceil(7/256)=1 = 2
            ("'  hi  '.strip()", 2),
            # startswith: 1 call + ceil(5/256)=1 = 2
            ("'hello'.startswith('he')", 2),
            # endswith: 1 call + ceil(5/256)=1 = 2
            ("'hello'.endswith('lo')", 2),
            # find: 1 call + ceil(5/256)=1 = 2
            ("'hello'.find('l')", 2),
            # count: 1 call + ceil(5/256)=1 = 2
            ("'hello'.count('l')", 2),
            # capitalize: 1 call + ceil(5/256)=1 = 2
            ("'hello'.capitalize()", 2),
            # title: 1 call + ceil(5/256)=1 = 2
            ("'hello'.title()", 2),
            # isdigit: 1 call + ceil(3/256)=1 = 2
            ("'123'.isdigit()", 2),
            # removeprefix: 1 call + ceil(5/256)=1 = 2
            ("'hello'.removeprefix('he')", 2),
            # re_escape: 1 call + ceil(5/256)=1 = 2
            ("re_escape('he[l]')", 2),
            # repr_sh: 1 call + ceil(5/256)=1 = 2
            ("repr_sh('hello')", 2),
            # repr_py: 1 call + ceil(5/256)=1 = 2
            ("repr_py('hello')", 2),
            # repr_json: 1 call + ceil(5/256)=1 = 2
            ("repr_json('hello')", 2),
            # repr_cmd: 1 call + ceil(5/256)=1 = 2
            ("repr_cmd('hello')", 2),
            # repr_pwsh: 1 call + ceil(5/256)=1 = 2
            ("repr_pwsh('hello')", 2),
        ],
    )
    def test_short_string_functions(self, expr: str, expected_count: int) -> None:
        """Short string functions add 1 string op (ceil(len/256) for len <= 256)."""
        result = parse_expression(expr).evaluate_with_metrics()
        assert result.operation_count == expected_count

    def test_join_counts_list_and_string(self) -> None:
        """join() counts list iteration AND string ops on separator processing."""
        # join(['a','b','c'], ',') = 1 call + 3 list iterations = 4
        # (join counts list items, not string ops on the items themselves)
        result = parse_expression("['a','b','c'].join(',')").evaluate_with_metrics()
        assert result.operation_count == 4

    def test_zfill_counts_string_ops(self) -> None:
        """zfill() counts string ops on the input."""
        result = parse_expression("('a' * 300).zfill(500)").evaluate_with_metrics()
        # __mul__: 1 + ceil(300/256)=2 = 3
        # zfill: 1 + ceil(300/256)=2 = 3
        # total = 6
        assert result.operation_count == 6
