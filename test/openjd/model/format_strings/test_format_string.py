# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest

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
    def test_empty_string(self):
        # GIVEN
        input = ""
        symtab = SymbolTable()

        # WHEN
        format_string = FormatString(input)

        # THEN
        assert format_string.resolve(symtab=symtab) == ""

    def test_no_expressions(self):
        # GIVEN
        input = "input"
        symtab = SymbolTable()

        # WHEN
        format_string = FormatString(input)

        # THEN
        assert format_string.resolve(symtab=symtab) == "input"

    def test_single_expr_no_space(self):
        # GIVEN
        input = "{{Test.val}}"
        symtab = SymbolTable()

        # WHEN
        format_string = FormatString(input)
        symtab["Test.val"] = 4

        # THEN
        assert format_string.resolve(symtab=symtab) == "4"

    def test_single_expr_with_space(self):
        # GIVEN
        input = " {{Test.val}} "
        symtab = SymbolTable()

        # WHEN
        format_string = FormatString(input)
        symtab["Test.val"] = 4

        # THEN
        assert format_string.resolve(symtab=symtab) == " 4 "

    def test_with_spaces_on_both_sides(self):
        # GIVEN
        input = " {{ Test.val }} "
        symtab = SymbolTable()

        # WHEN
        format_string = FormatString(input)
        symtab["Test.val"] = 4

        # THEN
        assert format_string.resolve(symtab=symtab) == " 4 "

    def test_multiple_expressions(self):
        # GIVEN
        input = " {{ Test.val }}-{{    Test.end}}  "
        symtab = SymbolTable()

        # WHEN
        format_string = FormatString(input)
        symtab["Test.val"] = 4
        symtab["Test.end"] = 10

        # THEN
        assert format_string.resolve(symtab=symtab) == " 4-10  "

    def test_with_floating_point(self):
        # GIVEN
        input = " {{ Test.val }}-{{    Test.end}}  "
        symtab = SymbolTable()

        # WHEN
        format_string = FormatString(input)
        symtab["Test.val"] = 4.098
        symtab["Test.end"] = 10

        # THEN
        assert format_string.resolve(symtab=symtab) == " 4.098-10  "

    def test_with_string(self):
        # GIVEN
        input = " {{ Test.val }}-{{    Test.end}}  "
        symtab = SymbolTable()

        # WHEN
        format_string = FormatString(input)
        symtab["Test.val"] = 4.098
        symtab["Test.end"] = "hello1"

        # THEN
        assert format_string.resolve(symtab=symtab) == " 4.098-hello1  "

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


class TestFormatStringValidate:
    @pytest.mark.parametrize("input", ["", "input"])
    def test_correct_validation_with_empty_table(self, input):
        # GIVEN
        symtab = SymbolTable()

        # WHEN
        format_string = FormatString(input)

        # THEN
        assert format_string.validate(symtab=symtab) == []

    @pytest.mark.parametrize("input", ["{{Test.val}}", " {{Test.val}} ", " {{ Test.val }} "])
    def test_correct_validation_with_table(self, input):
        # GIVEN
        symtab = SymbolTable()

        # WHEN
        format_string = FormatString(input)
        symtab["Test.val"] = 4

        # THEN
        assert format_string.validate(symtab=symtab) == []

    @pytest.mark.parametrize(
        "input,val,end",
        [
            (" {{ Test.val }}-{{    Test.end}}  ", 4, 10),
            (" {{ Test.val }}-{{    Test.end}}  ", 4.098, 10),
            (" {{ Test.val }}-{{    Test.end}}  ", 4.098, "hello1"),
        ],
    )
    def test_multiple_expressions(self, input, val, end):
        # GIVEN
        symtab = SymbolTable()

        # WHEN
        format_string = FormatString(input)
        symtab["Test.val"] = val
        symtab["Test.end"] = end

        # THEN
        assert format_string.validate(symtab=symtab) == []

    def test_without_one_entry_in_table(self):
        # GIVEN
        input = " {{ Test.val }}-{{    Test.end}}  "
        symtab = SymbolTable()

        # WHEN
        format_string = FormatString(input)
        symtab["Test.val"] = 4.098
        errors = format_string.validate(symtab=symtab)

        # THEN
        assert len(errors) == 1

    def test_without_multiple_entries_in_table(self):
        # GIVEN
        input = " {{ Test.val }}-{{    Test.end}}  "
        symtab = SymbolTable()

        # WHEN
        format_string = FormatString(input)
        errors = format_string.validate(symtab=symtab)

        # THEN
        assert len(errors) == 2
