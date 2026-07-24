# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for the v0 ``openjd.model.evaluate_let_bindings`` helper.

This is the shared EXPR ``let``-binding evaluation loop (RFC 0007 §3.6) used
by the model's job instantiation and by the ``openjd-sessions`` runtime. It
mutates a :class:`SymbolTable` in place, seeding each binding's typed engine
value under the bound name.

Not to be confused with ``openjd.model._v1.evaluate_let_bindings`` (the
Rust-backed v1 surface, tested in ``test/openjd/model_v1``), which returns a
new symbol table.
"""

import pytest

from openjd.model import SymbolTable, evaluate_let_bindings
from openjd.model._let_bindings import _parse_rhs


class TestEvaluateLetBindings:
    def test_single_binding(self) -> None:
        # GIVEN
        symtab = SymbolTable()

        # WHEN
        evaluate_let_bindings(symtab=symtab, let_bindings=["End = 1 + 9"])

        # THEN
        assert "End" in symtab
        assert symtab["End"].item() == 10

    def test_chained_bindings_reference_earlier_names(self) -> None:
        # Each binding is evaluated against the symbol table built so far,
        # so later bindings can reference earlier ones.
        symtab = SymbolTable()

        evaluate_let_bindings(
            symtab=symtab,
            let_bindings=[
                "A = 10 + 1",
                "B = A * 2",
                "C = A + B",
            ],
        )

        assert symtab["A"].item() == 11
        assert symtab["B"].item() == 22
        assert symtab["C"].item() == 33

    def test_existing_symbols_visible_to_bindings(self) -> None:
        # Bindings evaluate against the caller's symbol table, so pre-seeded
        # symbols (e.g. job parameters) are referencable.
        symtab = SymbolTable()
        symtab["Param.X"] = 10
        symtab.expr_types["Param.X"] = "INT"

        evaluate_let_bindings(symtab=symtab, let_bindings=["Doubled = Param.X * 2"])

        assert symtab["Doubled"].item() == 20

    def test_float_rendering_fidelity_preserved(self) -> None:
        # The engine's typed value is stored (not a Python float), so the
        # declared trailing zeros survive str() coercion (RFC 0005).
        symtab = SymbolTable()

        evaluate_let_bindings(symtab=symtab, let_bindings=["F = 1.50"])

        assert str(symtab["F"]) == "1.50"

    def test_let_bound_path_keeps_property_access(self) -> None:
        # A let-bound path stays a path: a later binding can use path
        # property access on it, matching the Rust runtime's typed table.
        symtab = SymbolTable()

        evaluate_let_bindings(
            symtab=symtab,
            let_bindings=[
                "P = path('/a/b/render.exr')",
                "N = P.name",
            ],
        )

        assert str(symtab["N"]) == "render.exr"

    @pytest.mark.parametrize(
        "binding",
        [
            pytest.param("no equals sign here", id="missing-equals"),
            pytest.param(" = 1 + 2", id="empty-name"),
            pytest.param("Name = ", id="empty-rhs"),
            pytest.param("=", id="only-equals"),
        ],
    )
    def test_malformed_bindings_are_skipped(self, binding: str) -> None:
        # Malformed bindings are rejected by the `let` field validator at
        # decode time; the evaluation loop skips them defensively without
        # raising or seeding anything.
        symtab = SymbolTable()

        evaluate_let_bindings(symtab=symtab, let_bindings=[binding])

        assert len(symtab.symbols) == 0

    def test_evaluation_error_raises_valueerror_naming_binding(self) -> None:
        # An RHS that fails to evaluate raises ValueError with the binding
        # name in the message.
        symtab = SymbolTable()

        with pytest.raises(ValueError) as excinfo:
            evaluate_let_bindings(symtab=symtab, let_bindings=["X = Undefined.Y + 1"])

        assert str(excinfo.value).startswith("let binding 'X':")

    def test_parse_error_raises_valueerror_naming_binding(self) -> None:
        # A parse failure (ExpressionError is a ValueError) is re-raised
        # naming the binding, same as an evaluation failure.
        symtab = SymbolTable()

        with pytest.raises(ValueError) as excinfo:
            evaluate_let_bindings(symtab=symtab, let_bindings=["Bad = 1 +"])

        assert str(excinfo.value).startswith("let binding 'Bad':")

    def test_rhs_parse_is_memoized(self) -> None:
        # The RHS parse is lru_cached: re-applying the same binding string
        # (as the sessions runtime does per env enter/exit and task run)
        # parses once and hits the cache thereafter.
        _parse_rhs.cache_clear()

        evaluate_let_bindings(symtab=SymbolTable(), let_bindings=["A = 2 + 3"])
        info = _parse_rhs.cache_info()
        assert info.misses == 1
        assert info.hits == 0

        evaluate_let_bindings(symtab=SymbolTable(), let_bindings=["A = 2 + 3"])
        info = _parse_rhs.cache_info()
        assert info.misses == 1
        assert info.hits == 1

    def test_parse_errors_are_not_cached(self) -> None:
        # lru_cache does not cache raised exceptions: the same bad RHS
        # raises on every application rather than serving a stale success.
        _parse_rhs.cache_clear()

        for _ in range(2):
            with pytest.raises(ValueError) as excinfo:
                evaluate_let_bindings(symtab=SymbolTable(), let_bindings=["Bad = 1 +"])
            assert str(excinfo.value).startswith("let binding 'Bad':")

        info = _parse_rhs.cache_info()
        assert info.hits == 0
        assert info.misses == 2
