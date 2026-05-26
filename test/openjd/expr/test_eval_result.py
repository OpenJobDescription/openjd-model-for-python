# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Focused tests for the EvalResult value class.

`EvalResult` is the structured return type of
`ParsedExpression.evaluate_with_metrics()`. It bundles the evaluated
`ExprValue` together with the per-call `peak_memory` (bytes) and
`operation_count` resource counters tracked by the Rust evaluator —
mirroring the `EvalResult` struct in the underlying `openjd_expr` crate.

These tests cover the class's intrinsic shape: construction, getters,
``__repr__``, ``__eq__``, pickle, and module/qualname hygiene. The
`peak_memory > 0` / `operation_count > 0` semantics through actual
evaluation are covered by `test_memory.py` and `test_operation_limit.py`.
"""

from __future__ import annotations

import pickle

import pytest
from openjd.expr import EvalResult, ExprValue, parse_expression


class TestConstruction:
    """`EvalResult` is directly constructible — required for pickle."""

    def test_constructor_positional(self) -> None:
        r = EvalResult(ExprValue(42), 128, 7)
        assert r.value.item() == 42
        assert r.peak_memory == 128
        assert r.operation_count == 7

    def test_constructor_keyword(self) -> None:
        r = EvalResult(value=ExprValue("hi"), peak_memory=64, operation_count=2)
        assert r.value.item() == "hi"
        assert r.peak_memory == 64
        assert r.operation_count == 2

    def test_constructor_with_zero_metrics(self) -> None:
        """Zero is a valid value for both counters (a bare constant has
        operation_count == 0; peak_memory >= 0)."""
        r = EvalResult(ExprValue(1), 0, 0)
        assert r.peak_memory == 0
        assert r.operation_count == 0

    def test_constructor_rejects_negative_metrics(self) -> None:
        """`peak_memory` and `operation_count` are `usize` on the Rust
        side; negative values raise OverflowError on conversion."""
        with pytest.raises(OverflowError):
            EvalResult(ExprValue(1), -1, 0)
        with pytest.raises(OverflowError):
            EvalResult(ExprValue(1), 0, -1)


class TestFields:
    """Field getters are read-only and return the constructor arguments."""

    def test_value_getter_returns_expr_value(self) -> None:
        r = EvalResult(ExprValue([1, 2, 3]), 10, 5)
        assert isinstance(r.value, ExprValue)
        assert r.value.item() == [1, 2, 3]

    def test_peak_memory_getter_is_int(self) -> None:
        r = EvalResult(ExprValue(1), 1024, 1)
        assert isinstance(r.peak_memory, int)
        assert r.peak_memory == 1024

    def test_operation_count_getter_is_int(self) -> None:
        r = EvalResult(ExprValue(1), 0, 99)
        assert isinstance(r.operation_count, int)
        assert r.operation_count == 99

    def test_fields_are_read_only(self) -> None:
        """`#[pyclass(frozen)]` — assigning to a getter raises AttributeError."""
        r = EvalResult(ExprValue(1), 0, 0)
        with pytest.raises(AttributeError):
            r.value = ExprValue(2)  # type: ignore[misc]
        with pytest.raises(AttributeError):
            r.peak_memory = 99  # type: ignore[misc]
        with pytest.raises(AttributeError):
            r.operation_count = 99  # type: ignore[misc]


class TestRepr:
    """`__repr__` is parseable and includes all three fields."""

    def test_repr_int_value(self) -> None:
        r = EvalResult(ExprValue(42), 128, 7)
        assert repr(r) == "EvalResult(value=ExprValue(42), peak_memory=128, operation_count=7)"

    def test_repr_string_value(self) -> None:
        r = EvalResult(ExprValue("hi"), 16, 1)
        assert repr(r) == "EvalResult(value=ExprValue('hi'), peak_memory=16, operation_count=1)"

    def test_repr_zero_metrics(self) -> None:
        r = EvalResult(ExprValue(1), 0, 0)
        assert repr(r) == "EvalResult(value=ExprValue(1), peak_memory=0, operation_count=0)"


class TestEquality:
    """`__eq__` compares all three fields; equal values defer to
    ``ExprValue.equals`` (so `1 == 1.0` cross-type equality holds)."""

    def test_equal_results_equal(self) -> None:
        a = EvalResult(ExprValue(42), 128, 7)
        b = EvalResult(ExprValue(42), 128, 7)
        assert a == b

    def test_different_value_not_equal(self) -> None:
        a = EvalResult(ExprValue(42), 128, 7)
        b = EvalResult(ExprValue(99), 128, 7)
        assert a != b

    def test_different_peak_memory_not_equal(self) -> None:
        a = EvalResult(ExprValue(42), 128, 7)
        b = EvalResult(ExprValue(42), 256, 7)
        assert a != b

    def test_different_operation_count_not_equal(self) -> None:
        a = EvalResult(ExprValue(42), 128, 7)
        b = EvalResult(ExprValue(42), 128, 8)
        assert a != b

    def test_value_equality_uses_expr_value_equals(self) -> None:
        """`ExprValue(1) == ExprValue(1.0)` is True (cross-type numeric
        equality), so two `EvalResult`s differing only by int-vs-float
        on the value field compare equal."""
        a = EvalResult(ExprValue(1), 0, 0)
        b = EvalResult(ExprValue(1.0), 0, 0)
        assert a == b

    def test_not_equal_to_other_types(self) -> None:
        r = EvalResult(ExprValue(42), 128, 7)
        # Tuples and dicts with the same shape are not equal —
        # __eq__ returns NotImplemented for unknown types.
        assert r != (ExprValue(42), 128, 7)
        assert r != {"value": ExprValue(42), "peak_memory": 128, "operation_count": 7}
        assert r != ExprValue(42)


class TestNotHashable:
    """`EvalResult` is not hashable — its `value` field can hold list /
    path / range values that aren't themselves hashable, so pinning a
    hash here would diverge from `ExprValue` (which deliberately omits
    `__hash__`)."""

    def test_unhashable(self) -> None:
        r = EvalResult(ExprValue(42), 128, 7)
        with pytest.raises(TypeError, match="unhashable type"):
            hash(r)

    def test_unusable_as_set_member(self) -> None:
        r = EvalResult(ExprValue(42), 128, 7)
        with pytest.raises(TypeError, match="unhashable type"):
            {r}

    def test_unusable_as_dict_key(self) -> None:
        r = EvalResult(ExprValue(42), 128, 7)
        with pytest.raises(TypeError, match="unhashable type"):
            {r: 1}


class TestPickle:
    """`__reduce__` round-trips through the constructor."""

    def test_pickle_round_trip_int(self) -> None:
        r = EvalResult(ExprValue(42), 128, 7)
        loaded = pickle.loads(pickle.dumps(r))
        assert loaded == r
        assert loaded.value.item() == 42
        assert loaded.peak_memory == 128
        assert loaded.operation_count == 7

    def test_pickle_round_trip_list(self) -> None:
        r = EvalResult(ExprValue([1, 2, 3]), 256, 11)
        loaded = pickle.loads(pickle.dumps(r))
        assert loaded == r
        assert loaded.value.item() == [1, 2, 3]

    def test_pickle_round_trip_string(self) -> None:
        r = EvalResult(ExprValue("hello"), 64, 2)
        loaded = pickle.loads(pickle.dumps(r))
        assert loaded == r
        assert loaded.value.item() == "hello"

    def test_pickle_preserves_type(self) -> None:
        r = EvalResult(ExprValue(1), 0, 0)
        loaded = pickle.loads(pickle.dumps(r))
        assert isinstance(loaded, EvalResult)
        assert type(loaded) is EvalResult


class TestModuleHygiene:
    """`EvalResult.__module__` / `__qualname__` resolve to the canonical
    user-facing name, so tracebacks and IDE tooltips don't leak the
    `Py`-prefixed Rust identifier."""

    def test_module_is_openjd_expr(self) -> None:
        # pyo3 sets __module__ from the `module = "openjd.expr"` attr.
        assert EvalResult.__module__ == "openjd.expr"

    def test_name_is_evalresult(self) -> None:
        assert EvalResult.__name__ == "EvalResult"

    def test_qualname_is_evalresult(self) -> None:
        assert EvalResult.__qualname__ == "EvalResult"


class TestFromEvaluateWithMetrics:
    """End-to-end: `evaluate_with_metrics` returns a real `EvalResult`."""

    def test_returns_eval_result_instance(self) -> None:
        r = parse_expression("1 + 2").evaluate_with_metrics()
        assert isinstance(r, EvalResult)

    def test_value_field_holds_evaluation_result(self) -> None:
        r = parse_expression("[1, 2, 3]").evaluate_with_metrics()
        assert isinstance(r.value, ExprValue)
        assert r.value.item() == [1, 2, 3]

    def test_metrics_are_populated(self) -> None:
        """For a non-trivial expression, both metrics are positive."""
        r = parse_expression("sum(range(100))").evaluate_with_metrics()
        assert r.peak_memory > 0
        assert r.operation_count > 0

    def test_two_calls_return_independent_results(self) -> None:
        """Each call returns its own result, no shared mutable state.

        This is the core safety property the EvalResult refactor
        provides: the previous racy `peak_memory_usage` / `operation_count`
        attributes were overwritten on every call. Now each call's
        metrics are pinned to the returned value."""
        parsed = parse_expression("Param.X * 100")
        r1 = parsed.evaluate_with_metrics(values={"Param.X": "a" * 1000})
        r2 = parsed.evaluate_with_metrics(values={"Param.X": "b"})
        # r1 reflects the large input; calling again with a small input
        # does NOT mutate r1.
        assert r1.peak_memory > r2.peak_memory
        assert r1.value.item() == "a" * 100000
        assert r2.value.item() == "b" * 100


class TestEvaluateReturnsValueOnly:
    """Companion check: the lighter `evaluate()` skips metric tracking
    and returns just the value. This pins the documented contract."""

    def test_evaluate_returns_expr_value_not_eval_result(self) -> None:
        v = parse_expression("1 + 2").evaluate()
        assert isinstance(v, ExprValue)
        assert not isinstance(v, EvalResult)
        assert v.item() == 3

    def test_parsed_expression_no_longer_carries_metric_attributes(self) -> None:
        """The racy `peak_memory_usage` / `operation_count` attributes
        on `ParsedExpression` are gone. Callers that need metrics must
        use `evaluate_with_metrics`."""
        parsed = parse_expression("1 + 2")
        parsed.evaluate()
        assert not hasattr(parsed, "peak_memory_usage")
        assert not hasattr(parsed, "operation_count")
