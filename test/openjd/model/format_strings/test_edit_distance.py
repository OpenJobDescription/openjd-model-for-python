# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest

from openjd.model._format_strings._edit_distance import _edit_distance, closest


class TestEditDistance:
    @pytest.mark.parametrize(
        "s1,s2,expected",
        [
            pytest.param("", "", 0, id="empty strings"),
            pytest.param("", "a", 1, id="empty s1"),
            pytest.param("a", "", 1, id="empty s2"),
            pytest.param("a", "bc", 2, id="seq1"),
            pytest.param("ab", "bc", 2, id="seq2"),
            pytest.param("abc", "bc", 1, id="seq3/delete-start"),
            pytest.param("abc", "ac", 1, id="delete inside"),
            pytest.param("abc", "ab", 1, id="delete end"),
            pytest.param("abc", "zabc", 1, id="insert start"),
            pytest.param("abc", "azbc", 1, id="insert inside"),
            pytest.param("abc", "abcz", 1, id="insert end"),
            pytest.param(
                "abcdefghijklmnopqrstuvwxyz", "zyxwvutsrqponmlkjihgfedcba", 26, id="reverse"
            ),
        ],
    )
    def test(self, s1: str, s2: str, expected: int) -> None:
        # WHEN
        result = _edit_distance(s1, s2)

        # THEN
        assert result == expected


class TestClosest:
    @pytest.mark.parametrize(
        "given, match, expected",
        [
            pytest.param(set(), "Param.Foo", (10, set()), id="no match"),
            pytest.param(
                set(("Param.Foo", "Param.Boo", "Param.Another")),
                "Parm.Foo",
                (1, set(("Param.Foo",))),
                id="One close",
            ),
            pytest.param(
                set(("Param.Foo", "Param.Boo", "Param.Another")),
                "Param.Zoo",
                (1, set(("Param.Foo", "Param.Boo"))),
                id="Two closest",
            ),
        ],
    )
    def test(self, given: set[str], match: str, expected: tuple[int, set[str]]) -> None:
        # WHEN
        result = closest(given, match)

        # THEN
        assert result == expected
