# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest

from openjd.model import SymbolTable, ValidationError
from openjd.model._format_strings._nodes import FullNameNode


class TestFullNameNode:
    def test_validate_success(self):
        # GIVEN
        symtab = SymbolTable()
        symtab["Test.Name"] = "value"

        # WHEN
        node = FullNameNode("Test.Name")

        # THEN
        try:
            node.validate(symtab=symtab)
        except ValidationError:
            pytest.fail("Incorrectly identified expression as nonvalid.")

    def test_validate_fails(self):
        # GIVEN
        symtab = SymbolTable()
        symtab["Test.Name"] = "value"

        # WHEN
        node = FullNameNode("Test.Fail")

        # THEN
        with pytest.raises(ValidationError) as exc:
            node.validate(symtab=symtab)

        assert "Test.Fail" in str(exc), "Name should be in validation error"

    def test_evaluate_success(self):
        # GIVEN
        symtab = SymbolTable()
        symtab["Test.Name"] = "value"
        node = FullNameNode("Test.Name")

        # WHEN
        result = node.evaluate(symtab=symtab)

        # THEN
        assert result == "value"

    def test_evaluate_fails(self):
        # GIVEN
        symtab = SymbolTable()
        symtab["Test.Name"] = "value"

        # WHEN
        node = FullNameNode("Test.Fail")

        # THEN
        with pytest.raises(ValidationError) as exc:
            node.evaluate(symtab=symtab)

        assert "Test.Fail" in str(exc), "Name should be in validation error"

    def test_repr(self):
        # GIVEN
        node = FullNameNode("Test.Name")

        # THEN
        assert str(node) == "FullName(Test.Name)"
