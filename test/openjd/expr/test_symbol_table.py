# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import json
import pickle
from pathlib import Path
from typing import cast

import pytest

import sys

from openjd.expr import ExprValue, SerializedSymbolTable, SymbolTable, TypeCode
from openjd.expr import PathFormat

HOST_PATH_FORMAT = PathFormat.WINDOWS if sys.platform == "win32" else PathFormat.POSIX


class TestSymbolTable:
    def test_construct_empty(self) -> None:
        # WHEN
        symtab = SymbolTable()

        # THEN
        assert "Param" not in symtab

    def test_construct_from_dict_simple(self) -> None:
        # GIVEN
        source = {"Param.Frame": 42, "Param.Name": "test"}

        # WHEN
        symtab = SymbolTable(source)

        # THEN
        assert "Param" in symtab
        param = cast(SymbolTable, symtab["Param"])
        assert cast(ExprValue, param["Frame"]).item() == 42
        assert cast(ExprValue, param["Name"]).item() == "test"

    def test_construct_from_dict_with_path(self, tmp_path) -> None:
        # GIVEN
        input_file = tmp_path / "projects" / "render.exr"
        source = {
            "Param.InputFile": ExprValue(str(input_file), type="path", path_format=HOST_PATH_FORMAT)
        }

        # WHEN
        symtab = SymbolTable(source)

        # THEN
        param = cast(SymbolTable, symtab["Param"])
        assert str(cast(ExprValue, param["InputFile"])) == str(input_file)

    def test_construct_from_dict_nested(self) -> None:
        # GIVEN
        source = {"Param": {"Frame": 100, "Name": "nested"}}

        # WHEN
        symtab = SymbolTable(source)

        # THEN
        param = cast(SymbolTable, symtab["Param"])
        assert cast(ExprValue, param["Frame"]).item() == 100
        assert cast(ExprValue, param["Name"]).item() == "nested"

    def test_construct_from_symtab(self) -> None:
        # GIVEN
        original = SymbolTable({"Param.Frame": 42})

        # WHEN
        copy = SymbolTable(original)

        # THEN
        param = cast(SymbolTable, copy["Param"])
        assert cast(ExprValue, param["Frame"]).item() == 42

    def test_setitem_dotted_path(self) -> None:
        # GIVEN
        symtab = SymbolTable()

        # WHEN
        symtab["Task.Param.Index"] = 5

        # THEN
        task = cast(SymbolTable, symtab["Task"])
        param = cast(SymbolTable, task["Param"])
        assert cast(ExprValue, param["Index"]).item() == 5

    def test_setitem_creates_intermediate_tables(self) -> None:
        # GIVEN
        symtab = SymbolTable()

        # WHEN
        symtab["A.B.C.D"] = "deep"

        # THEN
        a = cast(SymbolTable, symtab["A"])
        b = cast(SymbolTable, a["B"])
        c = cast(SymbolTable, b["C"])
        assert cast(ExprValue, c["D"]).item() == "deep"

    @pytest.mark.parametrize(
        "value,expected_type",
        [
            pytest.param(True, TypeCode.BOOL, id="bool"),
            pytest.param(42, TypeCode.INT, id="int"),
            pytest.param(3.14, TypeCode.FLOAT, id="float"),
            pytest.param("hello", TypeCode.STRING, id="string"),
            pytest.param(None, TypeCode.NULLTYPE, id="none"),
        ],
    )
    def test_auto_conversion(self, value, expected_type: TypeCode) -> None:
        # GIVEN
        symtab = SymbolTable()

        # WHEN
        symtab["Test"] = value

        # THEN
        result = symtab["Test"]
        assert isinstance(result, ExprValue)
        assert result.type.type_code == expected_type

    def test_auto_conversion_rejects_purepath(self) -> None:
        symtab = SymbolTable()
        with pytest.raises(TypeError, match="Cannot convert"):
            symtab["Test"] = Path("/tmp")

    def test_setitem_expression_value_passthrough(self) -> None:
        # GIVEN
        symtab = SymbolTable()
        ev = ExprValue(999)

        # WHEN
        symtab["Test"] = ev

        # THEN
        assert symtab["Test"] == ev

    def test_get_existing(self) -> None:
        # GIVEN
        symtab = SymbolTable({"Param.X": 1})

        # WHEN/THEN
        assert symtab.get("Param") is not None
        assert symtab.get("Missing") is None

    def test_construct_from_dict_with_purepath_rejects(self, tmp_path) -> None:
        """PurePath values should be rejected by SymbolTable."""
        output_dir = tmp_path / "projects" / "output"
        with pytest.raises(TypeError, match="Cannot convert"):
            SymbolTable({"Param.Dir": output_dir})

    def test_keys_returns_set_of_top_level_names(self) -> None:
        """``SymbolTable.keys`` returns a ``set`` of top-level symbol names,
        as documented in ``specs/python-expr-interface.md``. Nested keys
        roll up under their root namespace."""
        symtab = SymbolTable({"Param.Frame": 1, "Param.Name": "x", "Task.Index": 0})

        assert symtab.keys == {"Param", "Task"}
        assert isinstance(symtab.keys, set)

    def test_keys_empty_table(self) -> None:
        assert SymbolTable().keys == set()

    def test_symbols_returns_dotted_leaf_paths(self) -> None:
        """``SymbolTable.symbols`` returns the set of every dotted leaf
        path. Top-level keys with leaf values appear bare; nested
        subtables flatten to their leaves."""
        symtab = SymbolTable({"Param": {"Frame": 1, "Name": "x"}, "Task.Index": 0})
        assert symtab.symbols == {"Param.Frame", "Param.Name", "Task.Index"}

    def test_symbols_empty_table(self) -> None:
        assert SymbolTable().symbols == set()

    def test_union_with_symbol_tables(self) -> None:
        """``union`` returns a fresh table; the original is not mutated.
        Later arguments win on key collision."""
        a = SymbolTable({"Shared": 1, "OnlyA": "a"})
        b = SymbolTable({"Shared": 2, "OnlyB": "b"})

        result = a.union(b)
        assert result is not a
        assert result is not b
        assert result["Shared"].item() == 2  # later argument wins
        assert result["OnlyA"].item() == "a"
        assert result["OnlyB"].item() == "b"
        # Original is not touched.
        assert a["Shared"].item() == 1

    def test_union_with_dict(self) -> None:
        a = SymbolTable({"X": 1})
        result = a.union({"Y": 2})
        assert result["X"].item() == 1
        assert result["Y"].item() == 2

    def test_union_multiple_args(self) -> None:
        a = SymbolTable({"X": 1})
        result = a.union(SymbolTable({"Y": 2}), {"Z": 3})
        assert result.symbols == {"X", "Y", "Z"}

    def test_repr_matches_reference_format(self) -> None:
        """``__repr__`` produces ``SymbolTable({...})`` with sorted keys,
        matching the pure-Python reference's debugging UX."""
        symtab = SymbolTable({"Task.Index": 0, "Param.Frame": 1})

        text = repr(symtab)
        assert text.startswith("SymbolTable(")
        assert text.endswith(")")
        # Top-level keys are sorted; their repr appears once each.
        assert text.index("'Param'") < text.index("'Task'")

    def test_repr_empty(self) -> None:
        assert repr(SymbolTable()) == "SymbolTable({})"


class TestDottedPathLookup:
    """Test dotted path lookup in __getitem__, __contains__, and get."""

    def test_getitem_dotted(self) -> None:
        st = SymbolTable({"Param.X": 42})
        assert st["Param.X"] == ExprValue(42)

    def test_getitem_dotted_deep(self) -> None:
        st = SymbolTable({"A.B.C": "hello"})
        assert st["A.B.C"] == ExprValue("hello")

    def test_getitem_dotted_missing_raises(self) -> None:
        st = SymbolTable({"Param.X": 42})
        with pytest.raises(KeyError):
            st["Param.Y"]

    def test_contains_dotted(self) -> None:
        st = SymbolTable({"Param.X": 42, "Param.Y": "hi"})
        assert "Param.X" in st
        assert "Param.Y" in st
        assert "Param.Z" not in st

    def test_get_dotted(self) -> None:
        st = SymbolTable({"Param.X": 42})
        assert st.get("Param.X") == ExprValue(42)
        assert st.get("Param.Y") is None

    def test_simple_key_still_works(self) -> None:
        st = SymbolTable({"X": 42})
        assert "X" in st
        assert st["X"] == ExprValue(42)
        assert st.get("X") == ExprValue(42)

    def test_getitem_returns_subtable(self) -> None:
        st = SymbolTable({"Param.X": 42, "Param.Y": "hi"})
        param = st["Param"]
        assert isinstance(param, SymbolTable)

    def test_contains_namespace(self) -> None:
        st = SymbolTable({"Param.X": 42})
        assert "Param" in st
        assert "Param.X" in st
        assert "Other" not in st


class TestSerializedSymbolTableJson:
    """``to_json_str`` / ``from_json_str`` are the supported way to move a
    serialized symbol table across a process or service boundary."""

    def test_round_trip_preserves_values(self) -> None:
        # GIVEN
        symtab = SymbolTable(
            {
                "Job.Name": "my-job",
                "Step.Name": "render",
                "Param.Count": 42,
                "Param.Scale": 1.5,
                "Param.Debug": True,
            }
        )
        serialized = SerializedSymbolTable.from_symtab(symtab)

        # WHEN
        json_text = serialized.to_json_str()
        restored = SerializedSymbolTable.from_json_str(json_text).to_symtab()

        # THEN
        assert restored["Job.Name"] == ExprValue("my-job")
        assert restored["Step.Name"] == ExprValue("render")
        assert restored["Param.Count"] == ExprValue(42)
        assert restored["Param.Scale"] == ExprValue(1.5)
        assert restored["Param.Debug"] == ExprValue(True)

    def test_transport_shape(self) -> None:
        """The transport form is an array of {name, type, value} objects in
        canonical path order, with scalars carried as strings."""
        # GIVEN
        symtab = SymbolTable({"Job.Name": "my-job", "Param.Count": 42})

        # WHEN
        entries = json.loads(SerializedSymbolTable.from_symtab(symtab).to_json_str())

        # THEN
        assert entries == [
            {"name": "Job.Name", "type": "string", "value": "my-job"},
            {"name": "Param.Count", "type": "int", "value": "42"},
        ]

    def test_to_json_str_is_stable(self) -> None:
        # GIVEN
        symtab = SymbolTable({"Param.B": 2, "Param.A": 1})

        # WHEN
        first = SerializedSymbolTable.from_symtab(symtab).to_json_str()
        second = SerializedSymbolTable.from_symtab(symtab).to_json_str()

        # THEN
        assert first == second

    def test_empty_table_round_trips(self) -> None:
        # WHEN
        json_text = SerializedSymbolTable.from_symtab(SymbolTable()).to_json_str()

        # THEN
        assert json_text == "[]"
        assert SerializedSymbolTable.from_json_str(json_text).to_symtab().symbols == set()

    def test_from_json_str_accepts_hand_built_transport(self) -> None:
        """A caller that builds the transport form itself, rather than going
        through ``from_symtab``, gets the same result."""
        # GIVEN
        hand_built = '[{"name": "Job.Name", "type": "string", "value": "hand-built"}]'

        # WHEN
        symtab = SerializedSymbolTable.from_json_str(hand_built).to_symtab()

        # THEN
        assert symtab["Job.Name"] == ExprValue("hand-built")

    def test_from_json_str_rejects_malformed_json(self) -> None:
        # WHEN / THEN
        with pytest.raises(ValueError, match="Failed to parse SerializedSymbolTable JSON"):
            SerializedSymbolTable.from_json_str("not json at all")

    def test_from_json_str_defers_content_validation_to_to_symtab(self) -> None:
        """Well-formed JSON that is not a valid table is accepted by
        ``from_json_str`` and rejected by ``to_symtab``."""
        # GIVEN
        well_formed_but_wrong = '{"not": "an array"}'

        # WHEN
        serialized = SerializedSymbolTable.from_json_str(well_formed_but_wrong)

        # THEN
        with pytest.raises(ValueError, match="expected JSON array"):
            serialized.to_symtab()

    def test_json_round_trip_matches_pickle_round_trip(self) -> None:
        """The JSON form carries the same content as the pickle form, which
        round-trips through the same transport text."""
        # GIVEN
        symtab = SymbolTable({"Job.Name": "my-job", "Param.Count": 42})
        serialized = SerializedSymbolTable.from_symtab(symtab)

        # WHEN
        via_json = SerializedSymbolTable.from_json_str(serialized.to_json_str()).to_symtab()
        via_pickle = pickle.loads(pickle.dumps(serialized)).to_symtab()

        # THEN
        assert via_json.symbols == via_pickle.symbols
        for name in via_json.symbols:
            assert via_json[name] == via_pickle[name]

    def test_path_values_round_trip_with_host_format(self) -> None:
        # GIVEN
        symtab = SymbolTable({"RawParam.Scene": "/proj/scene.blend"})
        json_text = SerializedSymbolTable.from_symtab(symtab).to_json_str()

        # WHEN
        restored = SerializedSymbolTable.from_json_str(json_text).to_symtab(
            path_format=HOST_PATH_FORMAT
        )

        # THEN
        assert "RawParam.Scene" in restored
