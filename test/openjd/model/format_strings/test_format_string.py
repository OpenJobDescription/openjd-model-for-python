# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest
from typing import Union

from openjd.model import SymbolTable
from openjd.model._format_strings import FormatString, FormatStringError


def test_original_value():
    # GIVEN
    input = "input"

    # WHEN
    format_string = FormatString(input)

    # THEN
    assert format_string.original_value == input


def test_expression_property():
    # GIVEN
    input = "a{{ Test.val }}"

    # WHEN
    format_string = FormatString(input)

    # THEN
    assert len(format_string.expressions) == 1
    assert format_string.expressions[0].start_pos == 1
    assert format_string.expressions[0].end_pos == len(input)
    assert format_string.expressions[0].expression is not None
    assert format_string.expressions[0].expression.expr == " Test.val "


@pytest.mark.parametrize(
    "input",
    [
        "Test.val}}",
        "{Test.val}}",
        "{{Test.val",
        "{{Test.val}",
        "{{Test.val}} {{",
        "{{Test.val}} }}",
        "}} {{Test.val}}",
        "{{Test*val}}",
    ],
)
def test_nonvalid_strings(input):
    # THEN
    with pytest.raises(FormatStringError, match="Failed to parse interpolation expression"):
        FormatString(input)


class TestFormatStringResolve:
    @pytest.mark.parametrize("input", ["", "input"])
    def test_with_empty_table(self, input: str) -> None:
        # GIVEN
        symtab = SymbolTable()

        # WHEN
        format_string = FormatString(input)

        # THEN
        assert format_string.resolve(symtab=symtab) == input

    @pytest.mark.parametrize(
        "input, expected",
        [
            pytest.param("{{Test.val}}", "4"),
            pytest.param(" {{Test.val}} ", " 4 "),
            pytest.param(" {{ Test.val }} ", " 4 "),
        ],
    )
    def test_with_value(self, input: str, expected: str) -> None:
        # GIVEN
        symtab = SymbolTable()

        # WHEN
        format_string = FormatString(input)
        symtab["Test.val"] = 4

        # THEN
        assert format_string.resolve(symtab=symtab) == expected

    @pytest.mark.parametrize(
        "input,expected,val,end",
        [
            ("{{ Test.val }}-{{    Test.end}}", "4-10", 4, 10),
            (" {{ Test.val }}-{{    Test.end}}  ", " 4-10  ", 4, 10),
            (" {{ Test.val }} - {{    Test.end}}  ", " 4 - 10  ", 4, 10),
            (" {{ Test.val }}-{{    Test.end}}  ", " 4.098-10  ", 4.098, 10),
            (" {{ Test.val }}-{{    Test.end}}  ", " 4.098-hello1  ", 4.098, "hello1"),
        ],
    )
    def test_multiple_expressions(
        self, input: str, expected: str, val: Union[float, int], end: Union[float, int]
    ):
        # GIVEN
        symtab = SymbolTable()

        # WHEN
        format_string = FormatString(input)
        symtab["Test.val"] = val
        symtab["Test.end"] = end

        # THEN
        assert format_string.resolve(symtab=symtab) == expected

    def test_without_entry_in_table(self):
        # GIVEN
        input = " {{ Test.val }}-{{    Test.end}}  "
        symtab = SymbolTable()

        # WHEN
        format_string = FormatString(input)
        symtab["Test.val"] = 4.098

        # THEN
        with pytest.raises(FormatStringError, match="Failed to parse interpolation expression"):
            format_string.resolve(symtab=symtab)
