# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest

from openjd.model import SymbolTable
from openjd.model._format_strings._nodes import FullNameNode


class TestFullNameNode:
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
        with pytest.raises(ValueError) as exc:
            node.evaluate(symtab=symtab)

        assert "Test.Fail" in str(exc), "Name should be in validation error"

    def test_repr(self):
        # GIVEN
        node = FullNameNode("Test.Name")

        # THEN
        assert str(node) == "FullName(Test.Name)"

    def test_evaluate_to_str_renders_none_as_empty(self):
        # A None value interpolates as the empty string, matching the EXPR
        # engine's null rendering (RFC 0005). Relevant for nullable injected
        # symbols such as WrappedAction.Cancelation.Mode (string?) and
        # WrappedAction.Cancelation.NotifyPeriodInSeconds (int?), which are
        # None when the wrapped action defines no <Cancelation>
        # (RFC 0008 follow-up).
        # GIVEN
        symtab = SymbolTable()
        symtab["Test.Name"] = None
        node = FullNameNode("Test.Name")

        # WHEN
        result = node.evaluate_to_str(symtab=symtab)

        # THEN
        assert result == ""

    def test_evaluate_to_str_coerces_value_with_str(self):
        # GIVEN
        symtab = SymbolTable()
        symtab["Test.Name"] = 45
        node = FullNameNode("Test.Name")

        # WHEN
        result = node.evaluate_to_str(symtab=symtab)

        # THEN
        assert result == "45"
