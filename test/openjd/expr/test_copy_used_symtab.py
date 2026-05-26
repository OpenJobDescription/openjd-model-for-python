# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from openjd.expr import FormatString, SymbolTable


class TestCopyUsedSymtabValues:
    def test_simple(self):
        src = SymbolTable({"Param": {"Frame": 42, "Name": "test", "Unused": 99}})
        dest = SymbolTable()
        FormatString("render --frame {{Param.Frame}}").copy_used_symtab_values(src, dest)

        assert "Param.Frame" in dest
        assert dest["Param.Frame"].item() == 42
        assert "Param.Name" not in dest
        assert "Param.Unused" not in dest

    def test_method_call_stops_at_value(self):
        src = SymbolTable({"Param": {"Name": "hello"}})
        dest = SymbolTable()
        FormatString("{{Param.Name.upper()}}").copy_used_symtab_values(src, dest)

        assert dest["Param.Name"].item() == "hello"
        assert "Param.Name.upper" not in dest

    def test_chained_property(self):
        src = SymbolTable({"Param": {"Path": "/foo/bar.exr"}})
        dest = SymbolTable()
        FormatString("{{Param.Path.stem.upper()}}").copy_used_symtab_values(src, dest)

        assert dest["Param.Path"].item() == "/foo/bar.exr"
        assert "Param.Path.stem" not in dest

    def test_missing_symbol_no_error(self):
        src = SymbolTable()
        dest = SymbolTable()
        FormatString("{{Param.Missing + Task.Param.Also.Missing}}").copy_used_symtab_values(
            src, dest
        )

        assert dest.keys == set()

    def test_partial_missing(self):
        src = SymbolTable({"Param": {"Frame": 1}})
        dest = SymbolTable()
        FormatString("{{Param.Frame + Param.Missing}}").copy_used_symtab_values(src, dest)

        assert dest["Param.Frame"].item() == 1
        assert "Param.Missing" not in dest

    def test_multiple_format_strings(self):
        src = SymbolTable({"Param": {"Frame": 1, "Name": "job"}, "Task": {"Param": {"Index": 5}}})
        dest = SymbolTable()
        FormatString("{{Param.Frame}}").copy_used_symtab_values(src, dest)
        FormatString("{{Task.Param.Index}}").copy_used_symtab_values(src, dest)

        assert "Param.Frame" in dest
        assert "Task.Param.Index" in dest
        assert "Param.Name" not in dest

    def test_literal_no_copy(self):
        src = SymbolTable({"Param": {"X": 1}})
        dest = SymbolTable()
        FormatString("just a literal").copy_used_symtab_values(src, dest)

        assert dest.keys == set()

    def test_expression_with_multiple_refs(self):
        src = SymbolTable({"Param": {"Start": 1, "End": 10, "Other": 99}})
        dest = SymbolTable()
        FormatString("{{Param.Start + Param.End}}").copy_used_symtab_values(src, dest)

        assert "Param.Start" in dest
        assert "Param.End" in dest
        assert "Param.Other" not in dest

    def test_accumulates_across_calls(self):
        src = SymbolTable({"Param": {"A": 1, "B": 2, "C": 3}})
        dest = SymbolTable()
        FormatString("{{Param.A}}").copy_used_symtab_values(src, dest)
        FormatString("{{Param.B}}").copy_used_symtab_values(src, dest)

        assert dest["Param.A"].item() == 1
        assert dest["Param.B"].item() == 2
        assert "Param.C" not in dest
