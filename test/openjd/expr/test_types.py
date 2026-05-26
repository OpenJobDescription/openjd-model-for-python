# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest

from openjd.expr import ExprValue, ExprType, TypeCode
from openjd.expr import PathFormat

BOOL = ExprType("bool")
INT = ExprType("int")
FLOAT = ExprType("float")
STRING = ExprType("string")
PATH = ExprType("path")


class TestExprType:
    def test_basic_types(self) -> None:
        assert BOOL.type_code == TypeCode.BOOL
        assert INT.type_code == TypeCode.INT
        assert FLOAT.type_code == TypeCode.FLOAT
        assert STRING.type_code == TypeCode.STRING
        assert PATH.type_code == TypeCode.PATH

    def test_nullable(self) -> None:
        # WHEN - nullable is now a union with NULLTYPE
        nullable_int = ExprType(TypeCode.UNION, [INT, ExprType("nulltype")])

        # THEN
        assert nullable_int.type_code == TypeCode.UNION
        assert str(nullable_int) == "int?"

    def test_list_of(self) -> None:
        # WHEN
        list_int = ExprType(TypeCode.LIST, [INT])

        # THEN
        assert list_int.type_code == TypeCode.LIST
        assert list_int.type_params == [INT]

    def test_equality(self) -> None:
        assert INT == ExprType(TypeCode.INT)
        assert INT != FLOAT
        assert ExprType(TypeCode.LIST, [INT]) == ExprType(TypeCode.LIST, [INT])
        assert ExprType(TypeCode.LIST, [INT]) != ExprType(TypeCode.LIST, [STRING])

    def test_hash(self) -> None:
        # Types should be hashable for use in sets
        types = {INT, FLOAT, STRING, INT}
        assert len(types) == 3

    def test_repr(self) -> None:
        assert repr(INT) == 'ExprType("int")'
        assert repr(BOOL) == 'ExprType("bool")'
        assert repr(ExprType(TypeCode.LIST, [INT])) == 'ExprType("list[int]")'
        assert repr(ExprType(TypeCode.UNION, [INT, ExprType("nulltype")])) == 'ExprType("int?")'

    def test_str(self) -> None:
        assert str(INT) == "int"
        assert str(BOOL) == "bool"
        assert str(ExprType(TypeCode.LIST, [INT])) == "list[int]"
        assert str(ExprType(TypeCode.UNION, [INT, ExprType("nulltype")])) == "int?"


class TestExprTypeStringConstruction:
    """Tests for ExprType string-based construction."""

    def test_basic_types(self) -> None:
        assert ExprType("int") == ExprType("int")
        assert ExprType("float") == ExprType("float")
        assert ExprType("string") == ExprType("string")
        assert ExprType("bool") == ExprType("bool")
        assert ExprType("path") == ExprType("path")
        assert ExprType("range_expr") == ExprType("range_expr")
        assert ExprType("nulltype") == ExprType("nulltype")

    def test_case_insensitive(self) -> None:
        # Type names are case-sensitive (must be lowercase)
        with pytest.raises(ValueError, match="Unknown type string"):
            ExprType("INT")
        with pytest.raises(ValueError, match="Unknown type string"):
            ExprType("String")

    def test_whitespace_rejected(self) -> None:
        # No whitespace allowed
        with pytest.raises(ValueError, match="Unknown type string"):
            ExprType(" int")
        with pytest.raises(ValueError, match="Unknown type string"):
            ExprType("int ")
        with pytest.raises(ValueError, match="Unknown type string"):
            ExprType("list[int ]")
        with pytest.raises(ValueError, match="Unknown type string"):
            ExprType("list[ int]")

    def test_list_types(self) -> None:
        assert ExprType("list[int]") == ExprType("list[int]")
        assert ExprType("list[string]") == ExprType("list[string]")
        assert ExprType("list[float]") == ExprType("list[float]")
        assert ExprType("list[path]") == ExprType("list[path]")
        assert ExprType("list[bool]") == ExprType("list[bool]")

    def test_nested_list(self) -> None:
        assert ExprType("list[list[int]]") == ExprType("list[list[int]]")

    def test_optional_types(self) -> None:
        # T? is now parsed as T | null (union)
        int_opt = ExprType("int?")
        assert int_opt.type_code == TypeCode.UNION
        assert str(int_opt) == "int?"

        string_opt = ExprType("string?")
        assert string_opt.type_code == TypeCode.UNION
        assert str(string_opt) == "string?"

        list_opt = ExprType("list[int]?")
        assert list_opt.type_code == TypeCode.UNION
        assert str(list_opt) == "list[int]?"

    def test_unknown_type_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown type string"):
            ExprType("notavalidtype")


class TestUnionTypes:
    """Tests for ANY and UNION type codes."""

    def test_any_type(self) -> None:
        any_type = ExprType(TypeCode.ANY)
        assert any_type.type_code == TypeCode.ANY
        assert str(any_type) == "any"

    def test_noreturn_type(self) -> None:
        noreturn = ExprType(TypeCode.NORETURN)
        assert noreturn.type_code == TypeCode.NORETURN
        assert str(noreturn) == "noreturn"
        assert ExprType("noreturn") == ExprType("noreturn")

    def test_noreturn_collapses_in_union(self) -> None:
        # T | noreturn -> T
        union = ExprType(TypeCode.UNION, [ExprType("int"), ExprType("noreturn")])
        assert union == ExprType("int")

    def test_noreturn_collapses_with_multiple_types(self) -> None:
        # int | string | noreturn -> int | string
        union = ExprType(
            TypeCode.UNION, [ExprType("int"), ExprType("string"), ExprType("noreturn")]
        )
        assert union.type_code == TypeCode.UNION
        assert ExprType("noreturn") not in union.type_params
        assert str(union) == "int | string"

    def test_noreturn_only_union(self) -> None:
        # noreturn | noreturn -> noreturn
        union = ExprType(TypeCode.UNION, [ExprType("noreturn"), ExprType("noreturn")])
        assert union == ExprType("noreturn")

    def test_union_construction(self) -> None:
        union = ExprType(TypeCode.UNION, [ExprType("int"), ExprType("string")])
        assert union.type_code == TypeCode.UNION
        assert str(union) == "int | string"

    def test_union_deduplication(self) -> None:
        # Duplicate types should be removed
        union = ExprType(TypeCode.UNION, [ExprType("int"), ExprType("int")])
        assert union.type_code == TypeCode.INT  # Unwrapped to single type

    def test_union_single_element_unwrap(self) -> None:
        # Single-element union should unwrap
        union = ExprType(TypeCode.UNION, [ExprType("string")])
        assert union.type_code == TypeCode.STRING

    def test_union_flattening(self) -> None:
        # Nested unions should flatten
        u1 = ExprType(TypeCode.UNION, [ExprType("int"), ExprType("string")])
        u2 = ExprType(TypeCode.UNION, [ExprType("float"), ExprType("bool")])
        combined = ExprType(TypeCode.UNION, [u1, u2])
        assert combined.type_code == TypeCode.UNION
        assert len(combined.type_params) == 4
        assert str(combined) == "bool | float | int | string"

    def test_union_any_absorption(self) -> None:
        # ANY absorbs all other types
        union = ExprType(TypeCode.UNION, [ExprType("int"), ExprType(TypeCode.ANY)])
        assert union.type_code == TypeCode.ANY

    def test_union_string_parsing(self) -> None:
        union = ExprType("int | string")
        assert union.type_code == TypeCode.UNION
        assert str(union) == "int | string"

    def test_union_string_parsing_multiple(self) -> None:
        union = ExprType("bool | float | int")
        assert union.type_code == TypeCode.UNION
        assert len(union.type_params) == 3

    def test_union_nullable_display_single(self) -> None:
        # T | null displays as T?
        union = ExprType(TypeCode.UNION, [ExprType("int"), ExprType("nulltype")])
        assert str(union) == "int?"

    def test_union_nullable_display_multiple(self) -> None:
        # Multiple types + null: null at end as ?
        union = ExprType(TypeCode.UNION, [ExprType("int"), ExprType("float"), ExprType("nulltype")])
        assert str(union) == "float | int | nulltype"

    def test_union_equality(self) -> None:
        u1 = ExprType(TypeCode.UNION, [ExprType("int"), ExprType("string")])
        u2 = ExprType(TypeCode.UNION, [ExprType("string"), ExprType("int")])  # Different order
        assert u1 == u2  # Should be equal after normalization

    def test_union_hash(self) -> None:
        u1 = ExprType(TypeCode.UNION, [ExprType("int"), ExprType("string")])
        u2 = ExprType("int | string")
        assert hash(u1) == hash(u2)
        # Should be usable in sets
        s = {u1, u2}
        assert len(s) == 1

    def test_union_roundtrip(self) -> None:
        original = ExprType(TypeCode.UNION, [ExprType("int"), ExprType("string")])
        roundtrip = ExprType(str(original))
        assert roundtrip == original

    def test_union_inside_list(self) -> None:
        # list[int | float] should parse correctly
        t = ExprType("list[int | float]")
        assert t.type_code == TypeCode.LIST
        assert t.type_params[0].type_code == TypeCode.UNION
        assert str(t) == "list[float | int]"

    def test_union_of_list_with_union_element(self) -> None:
        # list[int | string] | path
        t = ExprType("list[int | string] | path")
        assert t.type_code == TypeCode.UNION
        assert str(t) == "list[int | string] | path"

    def test_any_matches_anything(self) -> None:
        any_type = ExprType(TypeCode.ANY)
        assert any_type.match_type(ExprType("int")) == {}
        assert any_type.match_type(ExprType("string")) == {}
        assert any_type.match_type(ExprType("list[int]")) == {}

    def test_anything_matches_any(self) -> None:
        any_type = ExprType(TypeCode.ANY)
        assert ExprType("int").match_type(any_type) == {}
        assert ExprType("string").match_type(any_type) == {}

    def test_is_concrete(self) -> None:
        T1 = ExprType("T1")

        # Concrete types
        assert ExprType("int").is_concrete()
        assert ExprType("string").is_concrete()
        assert ExprType("list[int]").is_concrete()

        # Symbolic - not concrete
        assert not T1.is_concrete()
        assert not ExprType(TypeCode.LIST, [T1]).is_concrete()

        # Abstract - not concrete
        assert not ExprType(TypeCode.ANY).is_concrete()
        assert not ExprType(TypeCode.UNION, [ExprType("int"), ExprType("string")]).is_concrete()

        # Nested union - not concrete
        list_union = ExprType(
            TypeCode.LIST, [ExprType(TypeCode.UNION, [ExprType("int"), ExprType("string")])]
        )
        assert not list_union.is_concrete()

    def test_union_matches_member(self) -> None:
        union = ExprType(TypeCode.UNION, [ExprType("int"), ExprType("string")])
        assert union.match_type(ExprType("int")) == {}
        assert union.match_type(ExprType("string")) == {}
        assert union.match_type(ExprType("float")) is None

    def test_member_matches_union(self) -> None:
        union = ExprType(TypeCode.UNION, [ExprType("int"), ExprType("string")])
        assert ExprType("int").match_type(union) == {}
        assert ExprType("string").match_type(union) == {}
        assert ExprType("float").match_type(union) is None

    def test_union_matches_union_with_overlap(self) -> None:
        u1 = ExprType(TypeCode.UNION, [ExprType("int"), ExprType("string")])
        u2 = ExprType(TypeCode.UNION, [ExprType("string"), ExprType("float")])
        # string is in both, so they match
        assert u1.match_type(u2) == {}
        assert u2.match_type(u1) == {}

    def test_typevar_binds_to_union(self) -> None:
        T1 = ExprType("T1")

        union = ExprType(TypeCode.UNION, [ExprType("int"), ExprType("string")])
        # T1 should bind to the whole union
        assert T1.match_type(union) == {TypeCode.TYPEVAR_T1: union}
        assert union.match_type(T1) == {TypeCode.TYPEVAR_T1: union}

    def test_nested_typevar_binds_to_union(self) -> None:
        T1 = ExprType("T1")

        list_t1 = ExprType(TypeCode.LIST, [T1])
        inner_union = ExprType(TypeCode.UNION, [ExprType("int"), ExprType("string")])
        list_union = ExprType(TypeCode.LIST, [inner_union])
        # T1 should bind to int|string
        result = list_t1.match_type(list_union)
        assert result == {TypeCode.TYPEVAR_T1: inner_union}

    def test_any_with_typevar(self) -> None:
        T1 = ExprType("T1")

        any_type = ExprType(TypeCode.ANY)
        # Both directions bind T1 to any
        assert T1.match_type(any_type) == {TypeCode.TYPEVAR_T1: any_type}
        assert any_type.match_type(T1) == {TypeCode.TYPEVAR_T1: any_type}


class TestExprValue:
    def test_from_bool(self) -> None:
        # WHEN
        val = ExprValue(True)

        # THEN
        assert val.type == BOOL
        assert val.item() is True
        assert val.is_null is False

    def test_from_int(self) -> None:
        # WHEN
        val = ExprValue(42)

        # THEN
        assert val.type == INT
        assert val.item() == 42

    def test_from_float(self) -> None:
        # WHEN
        val = ExprValue(3.14)

        # THEN
        assert val.type == FLOAT
        assert val.item() == 3.14

    def test_from_float_with_original_str(self) -> None:
        # WHEN
        val = ExprValue.from_float(3.5, original_str="3.500")

        # THEN
        assert val.item() == 3.5
        assert str(val) == "3.500"

    def test_from_string(self) -> None:
        # WHEN
        val = ExprValue("hello")

        # THEN
        assert val.type == STRING
        assert val.item() == "hello"

    def test_from_path(self) -> None:
        # WHEN
        val = ExprValue("/tmp/test", type=ExprType("path"), path_format=PathFormat.POSIX)

        # THEN
        assert val.type == PATH
        assert str(val) == "/tmp/test"

    def test_null(self) -> None:
        # WHEN
        val = ExprValue(None)

        # THEN
        assert val.is_null is True
        assert val.type.type_code == TypeCode.NULLTYPE

    def test_to_string_bool(self) -> None:
        assert str(ExprValue(True)) == "true"
        assert str(ExprValue(False)) == "false"

    def test_to_string_int(self) -> None:
        assert str(ExprValue(42)) == "42"
        assert str(ExprValue(-5)) == "-5"

    def test_to_string_float(self) -> None:
        assert str(ExprValue(3.14)) == "3.14"

    def test_to_string_null(self) -> None:
        assert str(ExprValue(None)) == "null"

    def test_equality(self) -> None:
        assert ExprValue(5) == ExprValue(5)
        assert ExprValue(5) != ExprValue(6)
        assert ExprValue(5) != ExprValue("5")

    def test_purepath_rejected(self) -> None:
        """PurePath is not accepted by ExprValue constructor."""
        from pathlib import PurePath

        with pytest.raises(TypeError, match="Cannot convert"):
            ExprValue(PurePath("/tmp"))

    def test_list_empty(self) -> None:
        """Empty list has NULLTYPE element type."""
        v = ExprValue([])
        assert v.type == ExprType("list[nulltype]")

    def test_list_int_float_mix(self) -> None:
        """Mixed int/float list promotes to list[float]."""
        v = ExprValue([1, 2.0, 3])
        assert v.type == ExprType("list[float]")
        # All elements coerced to float
        assert all(e.type == FLOAT for e in v)

    def test_list_nested(self) -> None:
        """Nested list type inference."""
        v = ExprValue([[1, 2], [3, 4]])
        assert v.type == ExprType("list[list[int]]")

    def test_list_nested_int_float_mix(self) -> None:
        """Nested list with int/float mix promotes inner type."""
        v = ExprValue([[1, 2], [3.0, 4.0]])
        assert v.type == ExprType(TypeCode.LIST, [ExprType("list[float]")])

    def test_list_nested_int_float_mix_coerces_values(self) -> None:
        """Nested list with int/float mix coerces int elements to float (_from_python path)."""
        v = ExprValue([[1], [2.0]])
        inner_first = v[0]
        assert str(inner_first.type) == "list[float]"
        assert isinstance(inner_first[0].item(), float)

    def test_list_path_string_mix(self) -> None:
        """path/string mix promotes to string (_from_python path)."""
        v = ExprValue([ExprValue("/a", type="path", path_format=PathFormat.POSIX), "b"])
        assert str(v.type) == "list[string]"
        assert v.item() == ["/a", "b"]

    def test_list_nested_path_string_mix_coerces_values(self) -> None:
        """Nested list with path/string mix coerces path elements to string (_from_python path)."""
        v = ExprValue([[ExprValue("/a", type="path", path_format=PathFormat.POSIX)], ["b"]])
        inner_first = v[0]
        assert str(inner_first.type) == "list[string]"
        assert isinstance(inner_first[0].item(), str)

    def test_type_coercion(self) -> None:
        """Test type= parameter for explicit coercion."""
        assert ExprValue("42", type=ExprType("int")).item() == 42
        assert ExprValue("3.14", type=ExprType("float")).item() == 3.14
        assert ExprValue("true", type=ExprType("bool")).item() is True
        assert ExprValue("false", type=ExprType("bool")).item() is False
        assert ExprValue(
            "/tmp", type=ExprType("path"), path_format=PathFormat.POSIX
        ).type == ExprType("path")
        assert list(ExprValue("1-3", type=ExprType("range_expr")).item()) == [1, 2, 3]
        assert ExprValue(["1", "2"], type=ExprType("list[int]")).item() == [1, 2]


class TestTypeVariables:
    """Tests for type variable functionality."""

    def test_is_symbolic_simple(self) -> None:
        T1 = ExprType("T1")

        assert T1.is_symbolic() is True
        assert ExprType("int").is_symbolic() is False

    def test_is_symbolic_nested(self) -> None:
        T1 = ExprType("T1")

        list_t1 = ExprType(TypeCode.LIST, [T1])
        list_int = ExprType(TypeCode.LIST, [ExprType("int")])
        assert list_t1.is_symbolic() is True
        assert list_int.is_symbolic() is False

    def test_match_simple(self) -> None:
        T1 = ExprType("T1")

        bindings = T1.match_type(ExprType("int"))
        assert bindings == {TypeCode.TYPEVAR_T1: ExprType("int")}

    def test_match_nested(self) -> None:
        T1 = ExprType("T1")

        list_t1 = ExprType(TypeCode.LIST, [T1])
        list_int = ExprType(TypeCode.LIST, [ExprType("int")])
        bindings = list_t1.match_type(list_int)
        assert bindings == {TypeCode.TYPEVAR_T1: ExprType("int")}

    def test_match_no_match(self) -> None:
        T1 = ExprType("T1")

        list_t1 = ExprType(TypeCode.LIST, [T1])
        assert list_t1.match_type(ExprType("int")) is None  # Not a list
        assert list_t1.match_type(ExprType("string")) is None  # Not a list

    def test_substitute(self) -> None:
        T1 = ExprType("T1")

        list_t1 = ExprType(TypeCode.LIST, [T1])
        list_int = list_t1.substitute({TypeCode.TYPEVAR_T1: ExprType("int")})
        assert list_int == ExprType(TypeCode.LIST, [ExprType("int")])


class TestUnknownType:
    """Tests for the unresolved[T] type."""

    # -- Construction from TypeCode --

    def test_construct_with_constraint(self) -> None:
        t = ExprType(TypeCode.UNRESOLVED, [ExprType("int")])
        assert t.type_code == TypeCode.UNRESOLVED
        assert t.type_params == [ExprType("int")]

    def test_parse_bare_unknown(self) -> None:
        t = ExprType("unresolved")
        assert t.type_code == TypeCode.UNRESOLVED
        assert t.type_params == [ExprType(TypeCode.ANY)]

    def test_parse_unknown_int(self) -> None:
        t = ExprType("unresolved[int]")
        assert t.type_code == TypeCode.UNRESOLVED
        assert t.type_params == [ExprType("int")]

    def test_parse_unknown_list(self) -> None:
        t = ExprType("unresolved[list[string]]")
        assert t.type_code == TypeCode.UNRESOLVED
        assert t.type_params == [ExprType("list[string]")]

    def test_parse_unknown_union(self) -> None:
        t = ExprType("unresolved[int | float]")
        assert t.type_code == TypeCode.UNRESOLVED
        assert t.type_params[0].type_code == TypeCode.UNION

    def test_parse_unknown_any(self) -> None:
        t = ExprType("unresolved[any]")
        assert t == ExprType("unresolved")

    # -- String representation --

    def test_str_bare_unknown(self) -> None:
        assert str(ExprType("unresolved")) == "unresolved"

    def test_str_unknown_any_is_bare(self) -> None:
        assert str(ExprType(TypeCode.UNRESOLVED, [ExprType(TypeCode.ANY)])) == "unresolved"

    def test_str_unknown_int(self) -> None:
        assert str(ExprType("unresolved[int]")) == "unresolved[int]"

    def test_str_unknown_list(self) -> None:
        assert str(ExprType("unresolved[list[string]]")) == "unresolved[list[string]]"

    def test_repr(self) -> None:
        assert repr(ExprType("unresolved")) == 'ExprType("unresolved")'
        assert repr(ExprType("unresolved[int]")) == 'ExprType("unresolved[int]")'

    # -- Roundtrip (parse -> str -> parse) --

    def test_roundtrip_bare(self) -> None:
        t = ExprType("unresolved")
        assert ExprType(str(t)) == t

    def test_roundtrip_constrained(self) -> None:
        for s in ["unresolved[int]", "unresolved[list[string]]", "unresolved[int | float]"]:
            t = ExprType(s)
            assert ExprType(str(t)) == t, f"Roundtrip failed for {s}"

    # -- Equality and hashing --

    def test_equality(self) -> None:
        assert ExprType("unresolved[int]") == ExprType("unresolved[int]")
        assert ExprType("unresolved[int]") != ExprType("unresolved[float]")
        assert ExprType("unresolved") == ExprType("unresolved[any]")

    def test_hash(self) -> None:
        s = {ExprType("unresolved[int]"), ExprType("unresolved[int]")}
        assert len(s) == 1

    # -- is_concrete / is_symbolic --

    def test_not_concrete(self) -> None:
        assert not ExprType("unresolved").is_concrete()
        assert not ExprType("unresolved[int]").is_concrete()

    def test_not_symbolic(self) -> None:
        assert not ExprType("unresolved[int]").is_symbolic()

    def test_symbolic_if_constraint_is(self) -> None:
        T1 = ExprType("T1")

        t = ExprType(TypeCode.UNRESOLVED, [T1])
        assert t.is_symbolic()

    # -- match() behavior --

    def test_match_delegates_to_constraint(self) -> None:
        t = ExprType("unresolved[int]")
        assert t.match_type(ExprType("int")) == {}
        assert t.match_type(ExprType("string")) is None
        assert t.match_type(ExprType("float")) is None

    def test_match_symmetric(self) -> None:
        t = ExprType("unresolved[int]")
        assert ExprType("int").match_type(t) == {}
        assert ExprType("string").match_type(t) is None

    def test_match_union_constraint(self) -> None:
        t = ExprType("unresolved[int | float]")
        assert t.match_type(ExprType("int")) == {}
        assert t.match_type(ExprType("float")) == {}
        assert t.match_type(ExprType("string")) is None

    def test_match_any_constraint(self) -> None:
        t = ExprType("unresolved")
        assert t.match_type(ExprType("int")) == {}
        assert t.match_type(ExprType("string")) == {}
        assert t.match_type(ExprType("list[int]")) == {}

    def test_match_unknown_vs_unknown(self) -> None:
        # unresolved[int] vs unresolved[int] - delegates to int.match_type(unresolved[int]) -> int.match_type(int)
        t1 = ExprType("unresolved[int]")
        t2 = ExprType("unresolved[int]")
        assert t1.match_type(t2) == {}

    def test_match_unknown_vs_any(self) -> None:
        t = ExprType("unresolved[int]")
        assert t.match_type(ExprType(TypeCode.ANY)) == {}
        assert ExprType(TypeCode.ANY).match_type(t) == {}

    # -- ExprValue rejects unresolved type --

    def test_exprvalue_unknown_creation(self) -> None:
        v = ExprValue.unresolved(ExprType("int"))
        assert v.type == ExprType("unresolved[int]")
        assert v.type.type_code == TypeCode.UNRESOLVED

    def test_exprvalue_unknown_from_string(self) -> None:
        v = ExprValue.unresolved("list[string]")
        assert v.type == ExprType("unresolved[list[string]]")

    def test_exprvalue_unknown_equality(self) -> None:
        assert ExprValue.unresolved(ExprType("int")) == ExprValue.unresolved(ExprType("int"))
        assert ExprValue.unresolved(ExprType("int")) != ExprValue.unresolved(ExprType("float"))
        assert ExprValue.unresolved(ExprType("int")) != ExprValue(None)

    def test_exprvalue_unknown_repr(self) -> None:
        assert (
            repr(ExprValue.unresolved(ExprType("int"))) == 'ExprValue.unresolved(ExprType("int"))'
        )
        assert (
            repr(ExprValue.unresolved("list[string]"))
            == 'ExprValue.unresolved(ExprType("list[string]"))'
        )

    def test_substitute_constraint(self) -> None:
        T1 = ExprType("T1")

        t = ExprType(TypeCode.UNRESOLVED, [T1])
        result = t.substitute({TypeCode.TYPEVAR_T1: ExprType("int")})
        assert result == ExprType("unresolved[int]")


class TestUnknownTypeNormalization:
    """Tests for unresolved type hoisting/normalization rules."""

    # -- Rule: list[unresolved[T]] -> unresolved[list[T]] --

    def test_list_of_unknown_hoists(self) -> None:
        t = ExprType("list[unresolved[int]]")
        assert t.type_code == TypeCode.UNRESOLVED
        assert t == ExprType("unresolved[list[int]]")

    def test_list_of_unknown_union_constraint(self) -> None:
        t = ExprType("list[unresolved[int | float]]")
        assert t.type_code == TypeCode.UNRESOLVED
        assert t == ExprType("unresolved[list[int | float]]")

    def test_list_of_concrete_unchanged(self) -> None:
        t = ExprType("list[int]")
        assert t.type_code == TypeCode.LIST

    # -- Rule: T | unresolved[S] -> unresolved[T | S] --

    def test_union_with_unknown_hoists(self) -> None:
        t = ExprType("string | unresolved[int]")
        assert t.type_code == TypeCode.UNRESOLVED
        assert t == ExprType("unresolved[int | string]")

    def test_union_with_unknown_preserves_all_members(self) -> None:
        t = ExprType("string | bool | unresolved[int]")
        assert t.type_code == TypeCode.UNRESOLVED
        assert t == ExprType("unresolved[bool | int | string]")

    def test_union_without_unknown_unchanged(self) -> None:
        t = ExprType("int | string")
        assert t.type_code == TypeCode.UNION

    # -- Rule: unresolved[T] | unresolved[S] -> unresolved[T | S] --

    def test_union_of_two_unknowns_merges(self) -> None:
        t = ExprType("unresolved[int] | unresolved[float]")
        assert t.type_code == TypeCode.UNRESOLVED
        assert t == ExprType("unresolved[float | int]")

    def test_union_of_same_unknowns_deduplicates(self) -> None:
        t = ExprType("unresolved[int] | unresolved[int]")
        assert t.type_code == TypeCode.UNRESOLVED
        assert t == ExprType("unresolved[int]")

    # -- Rule: unresolved[unresolved[T]] -> unresolved[T] --

    def test_nested_unknown_flattens(self) -> None:
        t = ExprType("unresolved[unresolved[int]]")
        assert t.type_code == TypeCode.UNRESOLVED
        assert t == ExprType("unresolved[int]")

    def test_triple_nested_unknown_flattens(self) -> None:
        t = ExprType("unresolved[unresolved[unresolved[int]]]")
        assert t.type_code == TypeCode.UNRESOLVED
        assert t == ExprType("unresolved[int]")

    # -- Composite cases --

    def test_list_unknown_then_union(self) -> None:
        """list[unresolved[T]] | S -> unresolved[list[T] | S]"""
        t = ExprType("list[unresolved[int]] | string")
        assert t.type_code == TypeCode.UNRESOLVED
        assert t == ExprType("unresolved[list[int] | string]")

    def test_union_unknown_with_any_absorbs(self) -> None:
        """unresolved[T] | any -> any (ANY still absorbs everything)"""
        assert ExprType("unresolved[int] | any").type_code == TypeCode.ANY

    def test_union_unknown_with_noreturn_collapses(self) -> None:
        """unresolved[T] | noreturn -> unresolved[T]"""
        assert ExprType("unresolved[int] | noreturn") == ExprType("unresolved[int]")

    def test_unknown_never_inside_list(self) -> None:
        """After normalization, UNKNOWN never appears inside list type_params."""
        t = ExprType("list[unresolved[string]]")
        assert t.type_code == TypeCode.UNRESOLVED
        assert t.type_params[0] == ExprType("list[string]")

    def test_unknown_never_inside_union(self) -> None:
        """After normalization, UNKNOWN never appears inside union type_params."""
        t = ExprType("int | unresolved[float]")
        assert t.type_code == TypeCode.UNRESOLVED
        constraint = t.type_params[0]
        if constraint.type_code == TypeCode.UNION:
            for member in constraint.type_params:
                assert member.type_code != TypeCode.UNRESOLVED


class TestExprTypeArityValidation:
    """``ExprType(TypeCode.X)`` validates that the parameter count
    matches the canonical arity for variant X. Without this, callers
    can construct non-canonical shapes (e.g. ``unresolved`` with no
    type parameter, or ``list`` with two element types) that don't
    appear anywhere in well-formed evaluation but compile fine through
    the upstream Rust ``ExprType::new``."""

    def test_unresolved_requires_one_param(self) -> None:
        with pytest.raises(ValueError, match="exactly one type parameter"):
            ExprType(TypeCode.UNRESOLVED)

    def test_unresolved_rejects_empty_params(self) -> None:
        with pytest.raises(ValueError, match="exactly one type parameter"):
            ExprType(TypeCode.UNRESOLVED, [])

    def test_unresolved_rejects_two_params(self) -> None:
        with pytest.raises(ValueError, match="exactly one type parameter"):
            ExprType(TypeCode.UNRESOLVED, [ExprType("int"), ExprType("string")])

    def test_unresolved_with_one_param_succeeds(self) -> None:
        # Canonical form — should construct cleanly and round-trip.
        t = ExprType(TypeCode.UNRESOLVED, [ExprType("int")])
        assert str(t) == "unresolved[int]"

    def test_list_requires_one_param(self) -> None:
        with pytest.raises(ValueError, match="exactly one type parameter"):
            ExprType(TypeCode.LIST)

    def test_list_rejects_two_params(self) -> None:
        with pytest.raises(ValueError, match="exactly one type parameter"):
            ExprType(TypeCode.LIST, [ExprType("int"), ExprType("string")])

    def test_list_with_one_param_succeeds(self) -> None:
        t = ExprType(TypeCode.LIST, [ExprType("int")])
        assert str(t) == "list[int]"

    def test_union_zero_or_one_param_normalises(self) -> None:
        # Union is intentionally lax — upstream `normalize_union`
        # unwraps a single-element union to the element and turns a
        # zero-element union into `noreturn`. Pin that contract.
        single = ExprType(TypeCode.UNION, [ExprType("string")])
        assert single.type_code == TypeCode.STRING
        empty = ExprType(TypeCode.UNION, [])
        assert empty.type_code == TypeCode.NORETURN

    def test_primitive_rejects_params(self) -> None:
        # Primitives (INT, STRING, BOOL, FLOAT, PATH, RANGE_EXPR,
        # NULLTYPE) take no type parameters.
        for tc in (
            TypeCode.INT,
            TypeCode.STRING,
            TypeCode.BOOL,
            TypeCode.FLOAT,
            TypeCode.PATH,
            TypeCode.NULLTYPE,
        ):
            with pytest.raises(ValueError, match="does not accept type parameters"):
                ExprType(tc, [ExprType("int")])
