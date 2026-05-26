# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Equality and hashing contracts on the value-shaped pyclasses
exposed by ``openjd.expr``:

* ``PathMappingRule`` — eq + hash.
* ``FormatString`` — eq + hash.
* ``HostContext`` — eq + hash.
* ``ExprProfile`` — eq + hash.
* ``SymbolTable`` — eq only (mutable; intentionally not hashable).

Pins the contracts called out in
``reports/expr-bindings-quality-evaluation-report.md`` (P1
recommendations 1-5 in the original §8 list). All five types
compose their equality/hash on the visible field values rather
than on Python identity, so distinct constructions that yield
the same logical state compare equal.
"""

from __future__ import annotations

import pytest

from openjd.expr import (
    ExprProfile,
    ExprRevision,
    FormatString,
    HostContext,
    PathFormat,
    PathMappingRule,
    SymbolTable,
)


def _rule(src: str = "/a", dst: str = "/b") -> PathMappingRule:
    return PathMappingRule(
        source_path_format=PathFormat.POSIX,
        source_path=src,
        destination_path=dst,
    )


# ── PathMappingRule ────────────────────────────────────────────────


class TestPathMappingRuleEquality:
    def test_eq_identical(self) -> None:
        assert _rule() == _rule()

    def test_eq_differs_on_source(self) -> None:
        assert _rule(src="/a") != _rule(src="/A")

    def test_eq_differs_on_destination(self) -> None:
        assert _rule(dst="/b") != _rule(dst="/B")

    def test_eq_differs_on_format(self) -> None:
        posix = PathMappingRule(
            source_path_format=PathFormat.POSIX,
            source_path="/a",
            destination_path="/b",
        )
        windows = PathMappingRule(
            source_path_format=PathFormat.WINDOWS,
            source_path="/a",
            destination_path="/b",
        )
        assert posix != windows

    def test_eq_with_non_rule_returns_false(self) -> None:
        # Not a rule on the right-hand side ⇒ False (not raises).
        assert _rule() != "string"
        assert _rule() != 42
        assert _rule() != {"source_path": "/a", "destination_path": "/b"}

    def test_hash_consistent_with_eq(self) -> None:
        # Equal rules MUST hash equal (Python contract).
        assert hash(_rule()) == hash(_rule())

    def test_hashable_in_set(self) -> None:
        rules = {_rule("/a", "/b"), _rule("/a", "/b"), _rule("/c", "/d")}
        assert len(rules) == 2

    def test_hashable_as_dict_key(self) -> None:
        d = {_rule("/a", "/b"): "first", _rule("/c", "/d"): "second"}
        assert d[_rule("/a", "/b")] == "first"


# ── FormatString ───────────────────────────────────────────────────


class TestFormatStringEquality:
    def test_eq_identical_raw(self) -> None:
        assert FormatString("hello {{X}}") == FormatString("hello {{X}}")

    def test_eq_pure_literals(self) -> None:
        assert FormatString("just text") == FormatString("just text")

    def test_eq_differs_on_whitespace(self) -> None:
        # Lexical differences within `{{...}}` are preserved as
        # inequalities — equality is on the raw source string,
        # not on the parsed AST.
        assert FormatString("{{ X }}") != FormatString("{{X}}")

    def test_eq_with_non_format_string_returns_false(self) -> None:
        assert FormatString("hello") != "hello"
        assert FormatString("hello") != 42

    def test_hash_consistent_with_eq(self) -> None:
        assert hash(FormatString("a {{x}}")) == hash(FormatString("a {{x}}"))

    def test_hashable_in_set(self) -> None:
        s = {
            FormatString("a {{x}}"),
            FormatString("a {{x}}"),
            FormatString("b {{y}}"),
        }
        assert len(s) == 2


# ── HostContext ────────────────────────────────────────────────────


class TestHostContextEquality:
    def test_none_eq_none(self) -> None:
        assert HostContext.none() == HostContext.none()

    def test_unresolved_eq_unresolved(self) -> None:
        assert HostContext.unresolved() == HostContext.unresolved()

    def test_none_ne_unresolved(self) -> None:
        assert HostContext.none() != HostContext.unresolved()

    def test_with_rules_eq_same_rules(self) -> None:
        assert HostContext.with_rules([_rule()]) == HostContext.with_rules([_rule()])

    def test_with_rules_value_compare_not_arc_identity(self) -> None:
        # Two distinct constructions of the same rule list are
        # equal — the underlying `Arc` is unwrapped for comparison.
        assert HostContext.with_rules(
            [_rule("/a", "/b"), _rule("/c", "/d")]
        ) == HostContext.with_rules([_rule("/a", "/b"), _rule("/c", "/d")])

    def test_with_rules_differs_on_payload(self) -> None:
        assert HostContext.with_rules([_rule("/a", "/b")]) != HostContext.with_rules(
            [_rule("/x", "/y")]
        )

    def test_with_rules_order_significant(self) -> None:
        # Rule order *does* matter for path-mapping resolution
        # (longest-source-first is the documented contract), so
        # equality treats the list as ordered, not as a set.
        a = HostContext.with_rules([_rule("/a", "/A"), _rule("/b", "/B")])
        b = HostContext.with_rules([_rule("/b", "/B"), _rule("/a", "/A")])
        assert a != b

    def test_empty_with_rules_ne_none(self) -> None:
        # `with_rules([])` registers `apply_path_mapping` (no
        # rewrites), `none()` does not register it. Different.
        assert HostContext.with_rules([]) != HostContext.none()

    def test_eq_with_non_host_context_returns_false(self) -> None:
        assert HostContext.none() != "none"
        assert HostContext.unresolved() != 0

    def test_hash_consistent_with_eq(self) -> None:
        assert hash(HostContext.none()) == hash(HostContext.none())
        assert hash(HostContext.unresolved()) == hash(HostContext.unresolved())
        assert hash(HostContext.with_rules([_rule()])) == hash(HostContext.with_rules([_rule()]))

    def test_hashable_in_set(self) -> None:
        s = {
            HostContext.none(),
            HostContext.none(),
            HostContext.unresolved(),
            HostContext.with_rules([_rule()]),
            HostContext.with_rules([_rule()]),
        }
        assert len(s) == 3


# ── ExprProfile ────────────────────────────────────────────────────


class TestExprProfileEquality:
    def test_eq_default(self) -> None:
        assert ExprProfile() == ExprProfile()

    def test_eq_explicit_revision(self) -> None:
        assert ExprProfile(ExprRevision.CURRENT) == ExprProfile(ExprRevision.CURRENT)

    def test_eq_with_extensions(self) -> None:
        # Today `ExprExtension` has no variants, so the extension
        # set is always empty. This pins the future contract:
        # profiles built with the same (currently empty) extension
        # parameter compare equal regardless of construction.
        a = ExprProfile(ExprRevision.CURRENT, extensions=[])
        b = ExprProfile(ExprRevision.CURRENT, extensions=[])
        assert a == b

    def test_differs_on_host_context(self) -> None:
        plain = ExprProfile()
        unresolved = ExprProfile(host_context=HostContext.unresolved())
        with_rules = ExprProfile(host_context=HostContext.with_rules([_rule()]))
        assert plain != unresolved
        assert plain != with_rules
        assert unresolved != with_rules

    def test_eq_same_host_rules(self) -> None:
        a = ExprProfile(host_context=HostContext.with_rules([_rule()]))
        b = ExprProfile(host_context=HostContext.with_rules([_rule()]))
        assert a == b

    def test_eq_with_non_profile_returns_false(self) -> None:
        assert ExprProfile() != "profile"
        assert ExprProfile() != ExprRevision.CURRENT

    def test_hash_consistent_with_eq(self) -> None:
        assert hash(ExprProfile()) == hash(ExprProfile())
        assert hash(ExprProfile(host_context=HostContext.unresolved())) == hash(
            ExprProfile(host_context=HostContext.unresolved())
        )
        assert hash(ExprProfile(host_context=HostContext.with_rules([_rule()]))) == hash(
            ExprProfile(host_context=HostContext.with_rules([_rule()]))
        )

    def test_hashable_in_set(self) -> None:
        s = {
            ExprProfile(),
            ExprProfile(),
            ExprProfile(host_context=HostContext.unresolved()),
            ExprProfile(host_context=HostContext.with_rules([_rule()])),
        }
        assert len(s) == 3


# ── SymbolTable ────────────────────────────────────────────────────


class TestSymbolTableEquality:
    def test_eq_empty(self) -> None:
        assert SymbolTable() == SymbolTable()

    def test_eq_same_entries(self) -> None:
        a = SymbolTable({"Param.Frame": 1, "Param.Name": "x"})
        b = SymbolTable({"Param.Name": "x", "Param.Frame": 1})  # reverse order
        assert a == b

    def test_eq_recursive_through_subtables(self) -> None:
        # `Param.Inner.Frame` and `Param.Inner.Name` materialise
        # as a nested subtable; equality walks recursively.
        a = SymbolTable({"Param.Inner.Frame": 1, "Param.Inner.Name": "x"})
        b = SymbolTable({"Param.Inner.Name": "x", "Param.Inner.Frame": 1})
        assert a == b

    def test_differs_on_value(self) -> None:
        a = SymbolTable({"Param.Frame": 1})
        b = SymbolTable({"Param.Frame": 2})
        assert a != b

    def test_differs_on_missing_key(self) -> None:
        a = SymbolTable({"Param.Frame": 1})
        b = SymbolTable()
        assert a != b

    def test_differs_on_extra_key(self) -> None:
        a = SymbolTable({"Param.Frame": 1})
        b = SymbolTable({"Param.Frame": 1, "Param.Name": "x"})
        assert a != b

    def test_eq_with_dict_returns_false(self) -> None:
        # `dict` is not auto-coerced to `SymbolTable` for
        # comparison; callers must construct explicitly.
        assert SymbolTable({"a": 1}) != {"a": 1}

    def test_eq_with_non_symbol_table_returns_false(self) -> None:
        assert SymbolTable() != "table"
        assert SymbolTable() != 0

    def test_not_hashable(self) -> None:
        # `SymbolTable` is mutable (`__setitem__` is supported), so
        # it is intentionally not hashable per Python's hash/eq
        # contract.
        with pytest.raises(TypeError):
            hash(SymbolTable())

    def test_not_usable_as_set_member(self) -> None:
        with pytest.raises(TypeError):
            {SymbolTable()}
