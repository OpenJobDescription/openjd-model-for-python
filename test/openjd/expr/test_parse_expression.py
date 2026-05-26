# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for EXPR extension parsing and FormatString."""

import pytest

from openjd.expr import (
    parse_expression,
    evaluate_expression,
    ExpressionError,
    FormatString,
    SymbolTable,
)


class TestParseExpression:
    """Tests for openjd.expr.parse_expression symbol collection."""

    def test_simple_variable(self):
        parsed = parse_expression("Param.InputFile")
        assert parsed.accessed_symbols == {"Param.InputFile"}

    def test_property_access(self):
        parsed = parse_expression("Param.InputFile.stem")
        assert parsed.accessed_symbols == {"Param.InputFile.stem"}

    def test_method_call(self):
        parsed = parse_expression("Param.InputFile.stem.upper()")
        assert parsed.accessed_symbols == {"Param.InputFile.stem"}

    def test_arithmetic(self):
        parsed = parse_expression("Param.Start + Param.End")
        assert parsed.accessed_symbols == {"Param.Start", "Param.End"}

    def test_conditional(self):
        parsed = parse_expression("Param.A if Param.Flag else Param.B")
        assert parsed.accessed_symbols == {"Param.A", "Param.Flag", "Param.B"}

    def test_slicing(self):
        parsed = parse_expression("Param.Items[1:3]")
        assert parsed.accessed_symbols == {"Param.Items"}

    def test_list_comprehension(self):
        parsed = parse_expression("[x for x in Param.Items]")
        assert parsed.accessed_symbols == {"Param.Items"}

    def test_list_comprehension_with_filter(self):
        parsed = parse_expression("[x for x in Param.Items if x > Param.Min]")
        assert parsed.accessed_symbols == {"Param.Items", "Param.Min"}

    def test_list_comprehension_nested_expression(self):
        parsed = parse_expression("[x * 2 for x in Param.Values]")
        assert parsed.accessed_symbols == {"Param.Values"}

    def test_list_comprehension_with_external_in_body(self):
        parsed = parse_expression("[x + Param.Offset for x in Param.Items]")
        assert parsed.accessed_symbols == {"Param.Items", "Param.Offset"}

    def test_same_name_outside_and_inside_comprehension(self):
        parsed = parse_expression("[x] + [x for x in []]")
        assert parsed.accessed_symbols == {"x"}

    def test_different_name_outside_comprehension(self):
        parsed = parse_expression("[y] + [x for x in []]")
        assert parsed.accessed_symbols == {"y"}

    def test_builtin_function_not_in_symbols(self):
        parsed = parse_expression("string(Param.Count)")
        assert parsed.accessed_symbols == {"Param.Count"}

    def test_multiple_builtin_functions(self):
        parsed = parse_expression("len(Param.Items) + int(Param.Value)")
        assert parsed.accessed_symbols == {"Param.Items", "Param.Value"}

    def test_min_max_functions(self):
        parsed = parse_expression("min(Param.A, Param.B)")
        assert parsed.accessed_symbols == {"Param.A", "Param.B"}

    def test_method_on_int_literal_without_parens_fails(self):
        with pytest.raises(ExpressionError, match="Syntax error"):
            parse_expression("42.zfill(5)")

    def test_method_on_int_literal_with_parens(self):
        parsed = parse_expression("(42).zfill(5)")
        assert parsed.accessed_symbols == set()


class TestCalledFunctions:
    """Tests for parse_expression called_functions collection."""

    def test_no_function_calls(self):
        parsed = parse_expression("Param.A + Param.B")
        assert parsed.called_functions == set()

    def test_builtin_function(self):
        parsed = parse_expression("min(Param.A, Param.B)")
        assert parsed.called_functions == {"min"}

    def test_method_call(self):
        parsed = parse_expression("Param.Name.upper()")
        assert parsed.called_functions == {"upper"}

    def test_method_with_args(self):
        parsed = parse_expression("Param.File.stem.replace('a', 'b')")
        assert parsed.called_functions == {"replace"}

    def test_apply_path_mapping(self):
        parsed = parse_expression("RawParam.File.apply_path_mapping()")
        assert parsed.called_functions == {"apply_path_mapping"}

    def test_chained_methods(self):
        parsed = parse_expression("Param.Items.split(',').join(';')")
        assert parsed.called_functions == {"split", "join"}

    def test_function_in_list_comprehension(self):
        parsed = parse_expression("[string(x) for x in Param.Values]")
        assert parsed.called_functions == {"string"}

    def test_multiple_functions(self):
        parsed = parse_expression("min(len(Param.A), len(Param.B))")
        assert parsed.called_functions == {"min", "len"}

    def test_function_in_conditional(self):
        parsed = parse_expression("Param.A.upper() if Param.Flag else Param.B.lower()")
        assert parsed.called_functions == {"upper", "lower"}

    def test_nested_method_calls(self):
        parsed = parse_expression("Param.Path.parent.name.upper()")
        assert parsed.called_functions == {"upper"}

    def test_function_and_method_combined(self):
        parsed = parse_expression("len(Param.Name.upper())")
        assert parsed.called_functions == {"len", "upper"}


class TestLocalBindings:
    """Tests for local_bindings collection from list comprehensions."""

    def test_no_comprehension(self):
        parsed = parse_expression("x + y")
        assert parsed.local_bindings == set()
        assert parsed.accessed_symbols == {"x", "y"}

    def test_simple_comprehension(self):
        parsed = parse_expression("[x * 2 for x in items]")
        assert parsed.local_bindings == {"x"}
        assert parsed.accessed_symbols == {"items"}

    def test_multiple_generators_rejected(self):
        with pytest.raises(ExpressionError, match="Multiple 'for'"):
            parse_expression("[x + y for x in a for y in b]")

    def test_nested_comprehension(self):
        parsed = parse_expression("[[y for y in x] for x in items]")
        assert parsed.local_bindings == {"x", "y"}
        assert parsed.accessed_symbols == {"items"}

    def test_comprehension_with_filter(self):
        parsed = parse_expression("[x for x in items if x > 0]")
        assert parsed.local_bindings == {"x"}
        assert parsed.accessed_symbols == {"items"}

    def test_independent_branches(self):
        parsed = parse_expression(
            "[x for x in Param.Values] if Param.Boolean else [[y for y in z] for z in Param.Nested]"
        )
        assert parsed.local_bindings == {"x", "y", "z"}
        assert parsed.accessed_symbols == {"Param.Values", "Param.Boolean", "Param.Nested"}

    def test_nested_shadowing_rejected(self):
        with pytest.raises(ExpressionError, match="shadows"):
            parse_expression("[[x for x in Param.A] for x in Param.B]")

    def test_sibling_comprehensions_same_var_allowed(self):
        parsed = parse_expression("[x for x in a] + [x for x in b] + [x for x in c]")
        assert parsed.local_bindings == {"x"}
        assert parsed.accessed_symbols == {"a", "b", "c"}


class TestDictConvenience:
    """Tests for dict convenience parameters."""

    def test_evaluate_expression_with_dict_values(self):
        result = evaluate_expression("X + Y", values={"X": 1, "Y": 2})
        assert result.item() == 3


class TestFormatString:
    """Tests for FormatString parsing and resolution."""

    def test_literal(self):
        fs = FormatString("hello world")
        assert fs.is_literal()
        assert fs.raw() == "hello world"

    def test_simple_interpolation(self):
        fs = FormatString("Hello {{Param.Name}}!")
        assert not fs.is_literal()
        assert fs.expression_names() == ["Param.Name"]

    def test_resolve_string(self):
        fs = FormatString("Hello {{Param.Name}}!")
        st = SymbolTable({"Param.Name": "World"})
        assert fs.resolve_string(st) == "Hello World!"

    def test_resolve_multiple(self):
        fs = FormatString("{{Param.A}} + {{Param.B}}")
        st = SymbolTable({"Param.A": "foo", "Param.B": "bar"})
        assert fs.resolve_string(st) == "foo + bar"

    def test_resolve_returns_value(self):
        fs = FormatString("{{Param.X}}")
        st = SymbolTable({"Param.X": 42})
        result = fs.resolve(st)
        assert result.item() == 42

    def test_has_complex_expressions(self):
        assert not FormatString("{{Param.Name}}").has_complex_expressions()
        assert FormatString("{{Param.A + Param.B}}").has_complex_expressions()

    def test_literal_resolve(self):
        fs = FormatString("no interpolation")
        st = SymbolTable()
        assert fs.resolve_string(st) == "no interpolation"

    def test_escaped_braces(self):
        from openjd.expr import escape_format_string

        escaped = escape_format_string("{{literal}}")
        fs = FormatString(escaped)
        st = SymbolTable()
        assert fs.resolve_string(st) == "{{literal}}"
