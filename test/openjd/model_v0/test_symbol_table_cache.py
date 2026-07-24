# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Regression tests for the EXPR evaluation cache on SymbolTable.

The engine symbol table (a Rust-boundary construction) and the evaluation
profile are cached per symbol-table mutation version so a session action
that resolves many expressions (command, args, timeout, embedded files)
against one unchanged table does not rebuild the engine table per
expression — and so any mutation (``__setitem__``, ``expr_types``,
``expr_host_rules``) invalidates the cache.
"""

from pathlib import Path

import pytest

from openjd.model import SymbolTable
from openjd.model._format_strings._expr_support import (
    profile_for_symtab,
    symtab_to_expr_values,
)


class TestSymtabEngineTableCache:
    def test_repeated_builds_are_cached(self) -> None:
        # GIVEN
        symtab = SymbolTable()
        symtab["Param.X"] = "10"
        symtab.expr_types["Param.X"] = "INT"

        # WHEN
        first = symtab_to_expr_values(symtab, types=symtab.expr_types or None)
        second = symtab_to_expr_values(symtab, types=symtab.expr_types or None)

        # THEN: the exact same engine table object is returned.
        assert first is second

    def test_setitem_invalidates(self) -> None:
        # GIVEN
        symtab = SymbolTable()
        symtab["Param.X"] = "10"
        first = symtab_to_expr_values(symtab, types=None)

        # WHEN
        symtab["Param.Y"] = "20"
        second = symtab_to_expr_values(symtab, types=None)

        # THEN
        assert first is not second

    def test_expr_types_mutation_invalidates(self) -> None:
        # GIVEN
        symtab = SymbolTable()
        symtab["Param.X"] = "10"
        first = symtab_to_expr_values(symtab, types=symtab.expr_types or None)

        # WHEN: a direct expr_types mutation (how create_job and the session
        # runtime record types) must be observed by the cache.
        symtab.expr_types["Param.X"] = "INT"
        second = symtab_to_expr_values(symtab, types=symtab.expr_types or None)

        # THEN
        assert first is not second

    def test_expr_types_update_invalidates(self) -> None:
        symtab = SymbolTable()
        symtab["Param.X"] = "10"
        first = symtab_to_expr_values(symtab, types=symtab.expr_types or None)
        symtab.expr_types.update({"Param.X": "INT"})
        second = symtab_to_expr_values(symtab, types=symtab.expr_types or None)
        assert first is not second

    def test_untyped_prime_does_not_poison_typed_call(self) -> None:
        # Regression: priming the cache with types=None on a symbol table
        # whose expr_types is non-empty must NOT cache an untyped engine
        # table — a later typed call at the same mutation version would be
        # served the stale untyped table and lose the type coercions.
        from openjd.expr import ExprProfile

        from openjd.model._format_strings._expr_support import parse_expr_or_raise

        symtab = SymbolTable()
        symtab["Param.X"] = "10"
        symtab.expr_types["Param.X"] = "INT"

        # WHEN: prime with an untyped build on the typed symtab.
        untyped = symtab_to_expr_values(symtab, types=None)

        # THEN: the subsequent typed call is not served the stale table...
        typed = symtab_to_expr_values(symtab, types=symtab.expr_types or None)
        assert typed is not untyped

        # ...and coerces correctly: arithmetic sees the int 10, not "10".
        parsed = parse_expr_or_raise("Param.X + 1")
        result = parsed.evaluate(values=typed, profile=ExprProfile.current())
        assert result.item() == 11

        # The typed build is the one cached for the standard call form.
        assert symtab_to_expr_values(symtab, types=symtab.expr_types or None) is typed

    def test_untyped_call_still_cached_when_symtab_has_no_types(self) -> None:
        # types=None on a symtab without expr_types remains cacheable (this
        # is the evaluation layer's call form for untyped tables).
        symtab = SymbolTable()
        symtab["Param.X"] = "10"
        first = symtab_to_expr_values(symtab, types=symtab.expr_types or None)
        assert symtab_to_expr_values(symtab, types=symtab.expr_types or None) is first

    def test_foreign_types_mapping_bypasses_cache(self) -> None:
        # A caller-supplied types mapping that is not the table's own
        # expr_types must not poison or consult the cache.
        symtab = SymbolTable()
        symtab["Param.X"] = "10"
        cached = symtab_to_expr_values(symtab, types=None)
        foreign = symtab_to_expr_values(symtab, types={"Param.X": "INT"})
        assert cached is not foreign
        # And the cached entry is still served for the standard call form.
        assert symtab_to_expr_values(symtab, types=None) is cached

    def test_path_format_is_part_of_the_key(self) -> None:
        from openjd.expr import PathFormat

        symtab = SymbolTable()
        symtab["Param.P"] = "/tmp/x"
        posix = symtab_to_expr_values(symtab, types=None, path_format=PathFormat.POSIX)
        windows = symtab_to_expr_values(symtab, types=None, path_format=PathFormat.WINDOWS)
        assert posix is not windows
        assert symtab_to_expr_values(symtab, types=None, path_format=PathFormat.POSIX) is posix

    def test_expr_types_ior_invalidates(self) -> None:
        # `symtab.expr_types |= {...}` goes through dict.__ior__, which the
        # versioned dict must intercept (a C-level merge would silently skip
        # the version bump and serve a stale engine table).
        symtab = SymbolTable()
        symtab["Param.X"] = "10"
        first = symtab_to_expr_values(symtab, types=symtab.expr_types or None)
        symtab.expr_types |= {"Param.X": "INT"}
        second = symtab_to_expr_values(symtab, types=symtab.expr_types or None)
        assert first is not second

    def test_expr_types_reassignment_invalidates_and_stays_tracked(self) -> None:
        # Reassigning a whole new mapping must invalidate, and subsequent
        # in-place mutations of the new mapping must keep invalidating.
        symtab = SymbolTable()
        symtab["Param.X"] = "10"
        first = symtab_to_expr_values(symtab, types=symtab.expr_types or None)
        symtab.expr_types = {"Param.X": "INT"}
        second = symtab_to_expr_values(symtab, types=symtab.expr_types or None)
        assert first is not second
        symtab.expr_types["Param.Y"] = "FLOAT"
        third = symtab_to_expr_values(symtab, types=symtab.expr_types or None)
        assert second is not third

    def test_pickle_round_trip(self) -> None:
        # The versioned dict's owner backref cannot survive plain
        # dict-subclass pickling; SymbolTable.__reduce__ rebuilds instead.
        import pickle

        symtab = SymbolTable()
        symtab["Param.X"] = "10"
        symtab.expr_types["Param.X"] = "INT"
        restored = pickle.loads(pickle.dumps(symtab))
        assert restored["Param.X"] == "10"
        assert restored.expr_types == {"Param.X": "INT"}
        # The restored table's cache tracking works.
        first = symtab_to_expr_values(restored, types=restored.expr_types or None)
        assert symtab_to_expr_values(restored, types=restored.expr_types or None) is first
        restored["Param.Y"] = "20"
        assert symtab_to_expr_values(restored, types=restored.expr_types or None) is not first

    def test_copies_do_not_share_cache(self) -> None:
        symtab = SymbolTable()
        symtab["Param.X"] = "10"
        original = symtab_to_expr_values(symtab, types=None)
        derived = SymbolTable(source=symtab)
        # The derived table builds its own engine table...
        assert symtab_to_expr_values(derived, types=None) is not original
        # ...and the original's cache entry is untouched.
        assert symtab_to_expr_values(symtab, types=None) is original


class TestProfileCache:
    def test_profile_cached_and_invalidated_by_host_rules(self) -> None:
        symtab = SymbolTable()
        symtab["Param.X"] = "10"
        first = profile_for_symtab(symtab)
        assert profile_for_symtab(symtab) is first

        # Assigning host rules (how the session runtime enables the host
        # context) must invalidate the cached profile.
        symtab.expr_host_rules = []
        second = profile_for_symtab(symtab)
        assert second is not first
        assert profile_for_symtab(symtab) is second


class TestTypedResolutionSingleEvaluation:
    def test_range_expression_evaluated_once_per_definition(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """RFC 0006 typed whole-field range resolution: the expression is
        evaluated exactly once per task-parameter definition — the create_as
        target-model decision and the field value share the result."""

        from openjd.model import create_job, decode_job_template, preprocess_job_parameters
        from openjd.model._internal import _create_job as internal_create_job

        calls: list[str] = []
        real = internal_create_job.resolve_whole_field_typed_list

        def counting(value, symtab):  # type: ignore[no-untyped-def]
            calls.append(value.original_value)
            return real(value, symtab)

        monkeypatch.setattr(internal_create_job, "resolve_whole_field_typed_list", counting)

        template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["EXPR"],
                "name": "T",
                "parameterDefinitions": [
                    {"name": "Values", "type": "LIST[INT]", "default": [1, 2, 3]}
                ],
                "steps": [
                    {
                        "name": "S",
                        "parameterSpace": {
                            "taskParameterDefinitions": [
                                {"name": "V", "type": "INT", "range": "{{Param.Values}}"}
                            ]
                        },
                        "script": {"actions": {"onRun": {"command": "echo"}}},
                    }
                ],
            },
            supported_extensions=["EXPR"],
        )
        params = preprocess_job_parameters(
            job_template=template,
            job_parameter_values={},
            job_template_dir=tmp_path,
            current_working_dir=tmp_path,
        )
        job = create_job(job_template=template, job_parameter_values=params)

        # THEN: exactly one evaluation of the range expression...
        assert calls == ["{{Param.Values}}"]
        # ...and it instantiated as the native list.
        steps = job.steps
        step = steps["S"] if isinstance(steps, dict) else steps[0]
        assert step.parameterSpace is not None
        tpd = step.parameterSpace.taskParameterDefinitions
        tp = tpd["V"] if isinstance(tpd, dict) else tpd[0]
        assert list(tp.range) == [1, 2, 3]


class TestVersionedDictMutationsBumpVersion:
    """Every ``_VersionedDict`` mutation method must bump the owning
    SymbolTable's version, or the EXPR evaluation cache would serve a stale
    engine table after that mutation. ``__setitem__``/``update``/``__ior__``
    are covered above via cache invalidation; this pins the remaining
    mutators directly against the version counter."""

    def test_delitem_bumps_version(self) -> None:
        symtab = SymbolTable()
        symtab.expr_types["Param.X"] = "INT"
        before = symtab._version
        del symtab.expr_types["Param.X"]
        assert symtab._version > before
        assert "Param.X" not in symtab.expr_types

    def test_setdefault_bumps_version(self) -> None:
        symtab = SymbolTable()
        before = symtab._version
        inserted = symtab.expr_types.setdefault("Param.X", "INT")
        assert inserted == "INT"
        assert symtab._version > before
        # setdefault on an existing key still bumps (conservative: a no-op
        # bump only invalidates a cache entry, never poisons one).
        before = symtab._version
        existing = symtab.expr_types.setdefault("Param.X", "FLOAT")
        assert existing == "INT"
        assert symtab._version > before

    def test_pop_bumps_version(self) -> None:
        symtab = SymbolTable()
        symtab.expr_types["Param.X"] = "INT"
        before = symtab._version
        popped = symtab.expr_types.pop("Param.X")
        assert popped == "INT"
        assert symtab._version > before

    def test_popitem_bumps_version(self) -> None:
        symtab = SymbolTable()
        symtab.expr_types["Param.X"] = "INT"
        before = symtab._version
        popped_item = symtab.expr_types.popitem()
        assert popped_item == ("Param.X", "INT")
        assert symtab._version > before

    def test_clear_bumps_version(self) -> None:
        symtab = SymbolTable()
        symtab.expr_types["Param.X"] = "INT"
        before = symtab._version
        symtab.expr_types.clear()
        assert symtab._version > before
        assert symtab.expr_types == {}

    def test_delitem_invalidates_engine_table_cache(self) -> None:
        # End-to-end: a deletion mutation must be observed by the cache.
        symtab = SymbolTable()
        symtab["Param.X"] = "10"
        symtab.expr_types["Param.X"] = "INT"
        first = symtab_to_expr_values(symtab, types=symtab.expr_types or None)
        del symtab.expr_types["Param.X"]
        second = symtab_to_expr_values(symtab, types=symtab.expr_types or None)
        assert first is not second
