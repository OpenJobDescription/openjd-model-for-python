# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Pickle round-trip tests for the ``openjd.expr`` value types.

Every public value type listed in ``specs/python-expr-interface.md``
should round-trip through ``pickle.dumps`` / ``pickle.loads`` and
compare equal to the original. Exception classes pickle correctly via
the ``register_renamed_exception`` plumbing in ``rust-bindings/src/lib.rs``;
the value-type reducers were added alongside model and sessions
counterparts.

Cross-reference: ``reports/expr-bindings-quality-evaluation-report.md``
recommendation #6.
"""

import pickle

import pytest

from openjd.expr import (
    ExprProfile,
    ExprRevision,
    ExprType,
    ExprValue,
    FormatString,
    HostContext,
    PathFormat,
    PathMappingRule,
    RangeExpr,
    SymbolTable,
    TypeCode,
)

# ── Group A: enums round-trip via variant name ───────────────────


@pytest.mark.parametrize(
    "value",
    [
        PathFormat.POSIX,
        PathFormat.WINDOWS,
        PathFormat.URI,
    ],
)
def test_path_format_pickle_round_trip(value):
    loaded = pickle.loads(pickle.dumps(value))
    assert loaded == value
    assert loaded is value  # enum singletons


@pytest.mark.parametrize(
    "value",
    [
        TypeCode.NULLTYPE,
        TypeCode.BOOL,
        TypeCode.INT,
        TypeCode.FLOAT,
        TypeCode.STRING,
        TypeCode.PATH,
        TypeCode.LIST,
        TypeCode.RANGE_EXPR,
        TypeCode.UNRESOLVED,
        TypeCode.UNION,
        TypeCode.ANY,
        TypeCode.NORETURN,
        TypeCode.TYPEVAR_T,
        TypeCode.TYPEVAR_T1,
        TypeCode.TYPEVAR_T2,
        TypeCode.TYPEVAR_T3,
    ],
)
def test_type_code_pickle_round_trip(value):
    loaded = pickle.loads(pickle.dumps(value))
    assert loaded == value
    assert loaded is value


def test_expr_revision_pickle_round_trip():
    loaded = pickle.loads(pickle.dumps(ExprRevision.V2026_02))
    assert loaded == ExprRevision.V2026_02


def test_pickled_enum_qualifies_under_canonical_module():
    """Sanity: pickled bytes reference ``openjd.expr.PathFormat``."""
    data = pickle.dumps(PathFormat.WINDOWS)
    assert b"openjd.expr" in data
    assert b"PathFormat" in data


# ── Group B: flat value types round-trip through their constructor ──


def test_path_mapping_rule_round_trip():
    rule = PathMappingRule(
        source_path_format=PathFormat.POSIX,
        source_path="/mnt/shared",
        destination_path="/local/cache",
    )
    loaded = pickle.loads(pickle.dumps(rule))
    # Per the equality contract pinned in test_equality.py, the
    # round-tripped rule compares equal to the original (and hashes
    # equal too).
    assert loaded == rule
    assert hash(loaded) == hash(rule)
    # `to_dict` round-trip is now redundant but kept as a sanity
    # check on the field-level reconstruction.
    assert loaded.to_dict() == rule.to_dict()


@pytest.mark.parametrize(
    "spec",
    [
        "int",
        "string",
        "path",
        "list[int]",
        "list[string]",
        "list[path]",
        "list[list[int]]",
        "int | string",
        "int | string | path",
        "unresolved",
    ],
)
def test_expr_type_round_trip(spec):
    """``ExprType`` reduces through its spec-form string."""
    t = ExprType(spec)
    loaded = pickle.loads(pickle.dumps(t))
    assert str(loaded) == str(t)
    assert loaded == t


@pytest.mark.parametrize(
    "spec",
    [
        "1-10",
        "1-10:2",
        "1,3,5,7-10",
        "100",
    ],
)
def test_range_expr_round_trip(spec):
    r = RangeExpr(spec)
    loaded = pickle.loads(pickle.dumps(r))
    assert str(loaded) == str(r)
    assert loaded == r


@pytest.mark.parametrize(
    "raw",
    [
        "literal text",
        "hello {{Param.Name}}",
        "no expressions here",
        "",
    ],
)
def test_format_string_round_trip(raw):
    fs = FormatString(raw)
    loaded = pickle.loads(pickle.dumps(fs))
    assert loaded == fs
    assert hash(loaded) == hash(fs)
    assert loaded.raw() == fs.raw()


def test_symbol_table_round_trip_flat():
    st = SymbolTable({"a": 1, "b": "hello", "c": [1, 2, 3]})
    loaded = pickle.loads(pickle.dumps(st))
    assert loaded == st
    assert loaded["a"].item() == 1
    assert loaded["b"].item() == "hello"
    assert loaded["c"][0].item() == 1


def test_symbol_table_round_trip_nested():
    st = SymbolTable({"Param": {"Frame": 42, "Name": "test"}, "Task": {"Index": 5}})
    loaded = pickle.loads(pickle.dumps(st))
    assert loaded == st
    assert loaded["Param.Frame"].item() == 42
    assert loaded["Param.Name"].item() == "test"
    assert loaded["Task.Index"].item() == 5


def test_symbol_table_round_trip_empty():
    st = SymbolTable({})
    loaded = pickle.loads(pickle.dumps(st))
    assert loaded == st
    assert loaded.symbols == set()


def test_host_context_none_round_trip():
    h = HostContext.none()
    loaded = pickle.loads(pickle.dumps(h))
    assert loaded == h
    assert hash(loaded) == hash(h)
    assert not loaded.is_enabled()
    assert not loaded.is_unresolved()


def test_host_context_unresolved_round_trip():
    h = HostContext.unresolved()
    loaded = pickle.loads(pickle.dumps(h))
    assert loaded == h
    assert hash(loaded) == hash(h)
    assert loaded.is_enabled()
    assert loaded.is_unresolved()


def test_host_context_with_rules_round_trip():
    rule = PathMappingRule(
        source_path_format=PathFormat.POSIX,
        source_path="/a",
        destination_path="/b",
    )
    h = HostContext.with_rules([rule])
    loaded = pickle.loads(pickle.dumps(h))
    assert loaded == h
    assert hash(loaded) == hash(h)
    assert loaded.is_enabled()
    assert not loaded.is_unresolved()


def test_expr_profile_round_trip_default():
    p = ExprProfile()
    loaded = pickle.loads(pickle.dumps(p))
    assert loaded == p
    assert hash(loaded) == hash(p)
    assert loaded.revision == p.revision


def test_expr_profile_round_trip_with_host_context():
    p = ExprProfile(host_context=HostContext.unresolved())
    loaded = pickle.loads(pickle.dumps(p))
    assert loaded == p
    assert hash(loaded) == hash(p)
    assert loaded.host_context.is_unresolved()


@pytest.mark.parametrize(
    "value, type_str",
    [
        (42, "int"),
        (3.14, "float"),
        ("hello", "string"),
        (True, "bool"),
        (False, "bool"),
        (None, "nulltype"),
    ],
)
def test_expr_value_scalar_round_trip(value, type_str):
    v = ExprValue(value)
    loaded = pickle.loads(pickle.dumps(v))
    assert loaded == v
    assert str(loaded.type) == type_str


def test_expr_value_list_round_trip():
    v = ExprValue([1, 2, 3])
    loaded = pickle.loads(pickle.dumps(v))
    assert loaded == v
    assert str(loaded.type) == "list[int]"


def test_expr_value_path_round_trip():
    v = ExprValue("/tmp/x", type="path", path_format=PathFormat.POSIX)
    loaded = pickle.loads(pickle.dumps(v))
    assert loaded == v


def test_expr_value_list_path_round_trip():
    v = ExprValue(["/a", "/b"], type="list[path]", path_format=PathFormat.POSIX)
    loaded = pickle.loads(pickle.dumps(v))
    assert loaded == v


def test_expr_value_unresolved_round_trip():
    v = ExprValue.unresolved("int")
    loaded = pickle.loads(pickle.dumps(v))
    assert loaded == v
    assert str(loaded.type) == "unresolved[int]"


def test_expr_value_range_expr_round_trip():
    v = ExprValue("1-10", type="range_expr")
    loaded = pickle.loads(pickle.dumps(v))
    assert loaded == v
