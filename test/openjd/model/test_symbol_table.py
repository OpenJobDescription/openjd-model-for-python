# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any

import pytest

from openjd.model import SymbolTable


class TestSymbolTable:
    def test_bad_symbol_type(self):
        table = SymbolTable()
        with pytest.raises(TypeError):
            table[4] = 12  # type: ignore # The point is to verify incorrect type

    def test_copy_construct_from_symtab(self):
        # GIVEN
        given = SymbolTable()
        given["Test.Symtab1"] = "One"
        given["Test.Symtab2"] = 1

        # WHEN
        result = SymbolTable(source=given)

        # THEN
        assert result.symbols == set(("Test.Symtab1", "Test.Symtab2"))
        assert result["Test.Symtab1"] == "One"
        assert result["Test.Symtab2"] == 1

    def test_copy_construct_from_dict(self):
        # GIVEN
        given = {"Test.Symtab1": "One", "Test.Symtab2": 1}

        # WHEN
        result = SymbolTable(source=given)

        # THEN
        assert result.symbols == set(("Test.Symtab1", "Test.Symtab2"))
        assert result["Test.Symtab1"] == "One"
        assert result["Test.Symtab2"] == 1

    def test_copy_construct_from_badtype(self) -> None:
        # GIVEN
        given: list[str] = list()

        # THEN
        with pytest.raises(TypeError):
            SymbolTable(source=given)  # type: ignore # Purpose is to check type validation

    @pytest.mark.parametrize("value", [0, 4, 7.4, "Value"])
    def test_add_value(self, value):
        table = SymbolTable()
        table["Test"] = value

        symbols = table.symbols
        assert {"Test"} == symbols
        assert "Test" in table, "Test __contains__"
        assert table["Test"] == value

    def test_union(self):
        # GIVEN
        symtab1 = SymbolTable()
        symtab1["Test.Symtab1"] = "One"
        symtab1["Overlap1"] = 1
        symtab2 = SymbolTable()
        symtab2["Test.Symtab2"] = "Two"
        symtab2["Overlap1"] = 2
        symtab2["Overlap2"] = 2

        # WHEN
        result = symtab1.union(symtab2)

        # THEN
        assert result is not symtab1
        symbols = result.symbols
        assert {"Test.Symtab1", "Test.Symtab2", "Overlap1", "Overlap2"} == symbols
        assert result["Test.Symtab1"] == "One"
        assert result["Test.Symtab2"] == "Two"
        assert result["Overlap1"] == 2, "Later arguments win duplicates"
        assert result["Overlap2"] == 2

    def test_union_dict(self) -> None:
        # GIVEN
        symtab1 = SymbolTable()
        symtab1["Test.Symtab1"] = "One"
        symtab1["Overlap1"] = 1
        symtab2: dict[str, Any] = dict()
        symtab2["Test.Symtab2"] = "Two"
        symtab2["Overlap1"] = 2
        symtab2["Overlap2"] = 2

        # WHEN
        result = symtab1.union(symtab2)

        # THEN
        assert result is not symtab1
        symbols = result.symbols
        assert {"Test.Symtab1", "Test.Symtab2", "Overlap1", "Overlap2"} == symbols
        assert result["Test.Symtab1"] == "One"
        assert result["Test.Symtab2"] == "Two"
        assert result["Overlap1"] == 2, "Later arguments win duplicates"
        assert result["Overlap2"] == 2

    def test_union_bad_type(self) -> None:
        # GIVEN
        symtab1 = SymbolTable()
        symtab1["Test.Symtab1"] = "One"
        symtab1["Overlap1"] = 1
        symtab2: list[str] = list()

        # THEN
        with pytest.raises(TypeError):
            symtab1.union(symtab2)  # type: ignore # Purpose is to validate type check

    def test_union_multiple(self):
        # GIVEN
        symtab1 = SymbolTable()
        symtab1["Test.Symtab1"] = "One"
        symtab1["Overlap1"] = 1
        symtab2 = SymbolTable()
        symtab2["Test.Symtab2"] = "Two"
        symtab2["Overlap1"] = 2
        symtab2["Overlap2"] = 2
        symtab3 = SymbolTable()
        symtab3["Test.Symtab3"] = "Three"
        symtab3["Overlap2"] = 3

        # WHEN
        result = symtab1.union(symtab2, symtab3)

        # THEN
        assert result is not symtab1
        symbols = result.symbols
        assert {"Test.Symtab1", "Test.Symtab2", "Test.Symtab3", "Overlap1", "Overlap2"} == symbols
        assert result["Test.Symtab1"] == "One"
        assert result["Test.Symtab2"] == "Two"
        assert result["Test.Symtab3"] == "Three"
        assert result["Overlap1"] == 2, "Later arguments win duplicates"
        assert result["Overlap2"] == 3, "Later arguments win duplicates"
