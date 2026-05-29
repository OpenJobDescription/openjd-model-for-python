# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from decimal import Decimal

import pytest

from openjd.expr import ExprValue, ExprType, ExpressionTypeError
from openjd.expr import PathFormat


class TestFromFloat:
    def test_from_float_basic(self) -> None:
        v = ExprValue(3.14)
        assert v.item() == 3.14
        assert str(v) == "3.14"

    def test_from_float_one_arg(self) -> None:
        # ``original_str`` is optional; when omitted the canonical
        # f64 ``Display`` form is used. Pinned for parity with the
        # pure-Python reference's
        # ``ExprValue.from_float(value, original_str=None)``
        # signature.
        v = ExprValue.from_float(3.14)
        assert v.item() == 3.14
        assert str(v) == "3.14"

    def test_from_float_explicit_none(self) -> None:
        # Explicit ``None`` is equivalent to omitting the argument.
        v = ExprValue.from_float(3.14, None)
        assert v.item() == 3.14
        assert str(v) == "3.14"

    def test_from_float_with_original_str(self) -> None:
        v = ExprValue.from_float(3.14, "3.140")
        assert v.item() == 3.14
        assert str(v) == "3.140"

    def test_from_float_one_arg_loses_trailing_zero(self) -> None:
        # Without ``original_str``, the f64 → str round-trip drops
        # trailing zeros (Rust's ``f64`` ``Display`` shows the
        # shortest round-trippable form: ``1.0`` not ``1.000``).
        # With it, the user-supplied form is preserved verbatim.
        assert str(ExprValue.from_float(1.0)) == "1.0"
        assert str(ExprValue.from_float(1.0, "1.000")) == "1.000"

    def test_from_float_rejects_nan(self) -> None:
        import math
        from openjd.expr import ExpressionError

        with pytest.raises(ExpressionError) as excinfo:
            ExprValue.from_float(math.nan)
        # AGENTS.md "Test Quality Standard": pin the full message.
        assert str(excinfo.value) == "Float operation produced NaN"

    def test_from_float_rejects_nan_with_original_str(self) -> None:
        # The optional-arg path doesn't bypass NaN validation.
        import math
        from openjd.expr import ExpressionError

        with pytest.raises(ExpressionError) as excinfo:
            ExprValue.from_float(math.nan, "nan")
        assert str(excinfo.value) == "Float operation produced NaN"

    def test_from_float_decimal(self) -> None:
        v = ExprValue(Decimal("3.140"))
        assert v.item() == 3.14
        assert str(v) == "3.140"

    def test_from_float_decimal_trailing_zeros(self) -> None:
        v = ExprValue(Decimal("1.000"))
        assert v.item() == 1.0
        assert str(v) == "1.000"

    def test_from_float_decimal_no_trailing_zeros(self) -> None:
        v = ExprValue(Decimal("2.5"))
        assert v.item() == 2.5
        assert str(v) == "2.5"

    def test_from_float_decimal_input_preserves_string(self) -> None:
        # Passing a ``Decimal`` to ``from_float`` (not just to the
        # main constructor) automatically captures its string form,
        # so ``str()`` shows the original lexical form including
        # trailing zeros. This keeps ``ExprValue.from_float(d)``
        # consistent with ``ExprValue(d)`` for ``Decimal`` inputs;
        # callers don't have to remember which constructor preserves
        # the lexical form.
        v = ExprValue.from_float(Decimal("1.00"))
        assert v.item() == 1.0
        assert str(v) == "1.00"

        v = ExprValue.from_float(Decimal("3.140"))
        assert v.item() == 3.14
        assert str(v) == "3.140"

    def test_from_float_decimal_consistent_with_main_constructor(self) -> None:
        # The two entry points produce identical output for the same
        # ``Decimal`` input. Pinned so a future refactor to either
        # path doesn't silently re-introduce the asymmetry.
        for src in ("1.00", "3.140", "0.001", "100.0", "0", "1"):
            d = Decimal(src)
            assert str(ExprValue(d)) == str(
                ExprValue.from_float(d)
            ), f"Mismatch for Decimal({src!r})"

    def test_from_float_decimal_input_explicit_original_str_wins(self) -> None:
        # When the caller passes ``original_str`` explicitly with a
        # ``Decimal`` value, the explicit string overrides the
        # auto-captured Decimal form. The explicit-override path is
        # an escape hatch for callers that want a custom display
        # form unrelated to the ``Decimal``'s own lexical form.
        v = ExprValue.from_float(Decimal("1.00"), "custom")
        assert v.item() == 1.0
        assert str(v) == "custom"

    def test_from_float_int_input(self) -> None:
        # ``from_float`` accepts ``int`` (PyO3 coerces via
        # ``__float__``). The resulting value is a Float, not an
        # Int — callers who want an Int should use the main
        # ``ExprValue(...)`` constructor.
        v = ExprValue.from_float(42)
        assert v.item() == 42.0
        assert str(v) == "42.0"

    def test_from_float_decimal_rejects_nan(self) -> None:
        # NaN rejection still fires on the Decimal-input path.
        with pytest.raises(ValueError) as excinfo:
            ExprValue.from_float(Decimal("NaN"))
        assert str(excinfo.value) == "Float operation produced NaN"


class TestFromList:
    def test_list_string(self) -> None:
        v = ExprValue(["a", "b", "c"])
        assert len(v.item()) == 3
        assert v.item()[0] == "a"

    def test_list_int(self) -> None:
        v = ExprValue([1, 2, 3])
        assert len(v.item()) == 3
        assert v.item()[0] == 1

    def test_list_bool(self) -> None:
        v = ExprValue([True, False, True])
        assert len(v.item()) == 3
        assert v.item()[0] is True
        assert v.item()[1] is False

    def test_list_list_int(self) -> None:
        v = ExprValue([[1, 2], [3, 4, 5]])
        assert len(v.item()) == 2
        assert len(v.item()[0]) == 2
        assert v.item()[0][0] == 1
        assert len(v.item()[1]) == 3


class TestExprValueConstruction:
    def test_from_value_bool(self) -> None:
        v = ExprValue(True)
        assert v.item() is True

    def test_from_value_int(self) -> None:
        v = ExprValue(42)
        assert v.item() == 42

    def test_from_value_float(self) -> None:
        v = ExprValue(3.14)
        assert v.item() == 3.14

    def test_from_value_decimal(self) -> None:
        v = ExprValue(Decimal("3.140"))
        assert v.item() == 3.14
        assert str(v) == "3.140"

    def test_from_value_string(self) -> None:
        v = ExprValue("hello")
        assert v.item() == "hello"

    def test_from_value_none(self) -> None:
        v = ExprValue(None)
        assert v.is_null

    def test_from_value_list(self) -> None:
        v = ExprValue([1, 2, 3])
        assert len(v.item()) == 3
        assert v.item()[0] == 1

    def test_from_value_list_decimal(self) -> None:
        v = ExprValue([Decimal("1.100"), Decimal("2.200")])
        assert v.item() == [1.1, 2.2]

    def test_from_value_list_mixed_float_decimal(self) -> None:
        v = ExprValue([1.5, Decimal("2.500")])
        assert v.item() == [1.5, 2.5]

    def test_from_value_nested_list(self) -> None:
        v = ExprValue([[1, 2], [3]])
        assert v.item() == [[1, 2], [3]]

    def test_from_value_unsupported_type(self) -> None:
        with pytest.raises(TypeError, match="Cannot convert"):
            ExprValue(object())


class TestExprValueNaNInf:
    """``ExprValue(float)`` rejects NaN and infinity, surfacing the
    rejection as ``ExpressionError`` (a ``ValueError`` subclass) with
    the pure-Python reference's canonical message. Mirrors the
    ``ExprValue.from_float`` covers above for the main-constructor
    path."""

    def test_nan_raises_expression_error(self) -> None:
        from openjd.expr import ExpressionError

        with pytest.raises(ExpressionError) as excinfo:
            ExprValue(float("nan"))
        assert str(excinfo.value) == "Float operation produced NaN"

    def test_inf_raises_expression_error(self) -> None:
        from openjd.expr import ExpressionError

        with pytest.raises(ExpressionError) as excinfo:
            ExprValue(float("inf"))
        assert str(excinfo.value) == "Float operation produced infinity"

    def test_neg_inf_raises_expression_error(self) -> None:
        from openjd.expr import ExpressionError

        with pytest.raises(ExpressionError) as excinfo:
            ExprValue(float("-inf"))
        assert str(excinfo.value) == "Float operation produced infinity"


class TestExprValueTypeCoercionWithString:
    """Test ExprValue construction with type= as a string."""

    def test_string_to_int(self) -> None:
        v = ExprValue("42", type="int")
        assert v.item() == 42

    def test_string_to_float(self) -> None:
        v = ExprValue("3.14", type="float")
        assert v.item() == 3.14

    def test_string_to_bool_true(self) -> None:
        v = ExprValue("true", type="bool")
        assert v.item() is True

    def test_string_to_bool_false(self) -> None:
        v = ExprValue("false", type="bool")
        assert v.item() is False

    def test_string_to_path(self) -> None:
        v = ExprValue("/tmp/file.txt", type="path", path_format=PathFormat.POSIX)
        assert str(v) == "/tmp/file.txt"
        assert v.item() == "/tmp/file.txt"

    def test_string_to_range_expr(self) -> None:
        v = ExprValue("1-5", type="range_expr")
        assert list(v.item()) == [1, 2, 3, 4, 5]

    def test_list_with_string_type(self) -> None:
        v = ExprValue([1, 2, 3], type="list[int]")
        assert v.item() == [1, 2, 3]

    def test_list_string_with_string_type(self) -> None:
        v = ExprValue(["a", "b"], type="list[string]")
        assert v.item() == ["a", "b"]

    def test_nested_list_with_string_type(self) -> None:
        v = ExprValue([[1, 2], [3]], type="list[list[int]]")
        assert v.item() == [[1, 2], [3]]

    def test_int_to_float_coercion(self) -> None:
        v = ExprValue(42, type="float")
        assert v.item() == 42.0


class TestExprValueRepr:
    """Test ExprValue __repr__ output."""

    def test_repr_int(self) -> None:
        assert repr(ExprValue(42)) == "ExprValue(42)"

    def test_repr_float(self) -> None:
        assert repr(ExprValue(3.14)) == "ExprValue(3.14)"

    def test_repr_float_with_preserved_decimals(self) -> None:
        assert repr(ExprValue(Decimal("3.50"))) == "ExprValue('3.50', type='float')"

    def test_repr_float_with_trailing_zeros(self) -> None:
        assert repr(ExprValue(Decimal("1.000"))) == "ExprValue('1.000', type='float')"

    def test_repr_float_from_float_with_string(self) -> None:
        assert repr(ExprValue.from_float(2.5, "2.500")) == "ExprValue('2.500', type='float')"

    def test_repr_bool_true(self) -> None:
        assert repr(ExprValue(True)) == "ExprValue(True)"

    def test_repr_bool_false(self) -> None:
        assert repr(ExprValue(False)) == "ExprValue(False)"

    def test_repr_string(self) -> None:
        assert repr(ExprValue("hello")) == "ExprValue('hello')"

    def test_repr_none(self) -> None:
        assert repr(ExprValue(None)) == "ExprValue(None)"

    def test_repr_list_int(self) -> None:
        assert repr(ExprValue([1, 2, 3])) == "ExprValue([1, 2, 3], type='list[int]')"

    def test_repr_list_string(self) -> None:
        assert repr(ExprValue(["a", "b"])) == "ExprValue(['a', 'b'], type='list[string]')"

    def test_repr_list_nested(self) -> None:
        assert repr(ExprValue([[1, 2], [3]])) == "ExprValue([[1, 2], [3]], type='list[list[int]]')"

    def test_repr_path(self) -> None:
        assert (
            repr(ExprValue("/tmp/file", type="path", path_format=PathFormat.POSIX))
            == "ExprValue('/tmp/file', type='path', path_format=PathFormat.POSIX)"
        )

    def test_repr_range_expr(self) -> None:
        assert repr(ExprValue("1-5", type="range_expr")) == "ExprValue('1-5', type='range_expr')"

    def test_repr_empty_list_path(self) -> None:
        import sys

        v = ExprValue([], type="list[path]")
        expected_fmt = "PathFormat.WINDOWS" if sys.platform == "win32" else "PathFormat.POSIX"
        assert repr(v) == f"ExprValue([], type='list[path]', path_format={expected_fmt})"

    def test_repr_empty_list_list_path(self) -> None:
        v = ExprValue([], type="list[list[path]]")
        assert repr(v) == "ExprValue([], type='list[list[path]]')"
        assert eval(repr(v)) == v

    @pytest.mark.parametrize("pf", [PathFormat.POSIX, PathFormat.WINDOWS])
    def test_repr_list_path_with_format(self, pf: PathFormat) -> None:
        import re

        v = ExprValue(["/a", "/b"], type="list[path]", path_format=pf)
        r = repr(v)
        assert re.match(
            r"ExprValue\(\['(/|\\)a', '(/|\\)b'\], type='list\[path\]', "
            rf"path_format=PathFormat\.{pf.name}\)",
            r,
        )

    @pytest.mark.parametrize("pf", [PathFormat.POSIX, PathFormat.WINDOWS])
    def test_repr_list_list_path_with_format(self, pf: PathFormat) -> None:
        import re

        v = ExprValue([["/a"], ["/b"]], type="list[list[path]]", path_format=pf)
        r = repr(v)
        assert re.match(
            r"ExprValue\(\[\['(/|\\)a'\], \['(/|\\)b'\]\], type='list\[list\[path\]\]', "
            rf"path_format=PathFormat\.{pf.name}\)",
            r,
        )


class TestMemorySize:
    """Tests for ``ExprValue.memory_size()``.

    The method mirrors ``ExprValue::memory_size`` in the underlying Rust
    crate (size of the inline enum plus heap allocations). Callers
    should treat the result as opaque bytes for memory-limit accounting,
    not a portable measurement.
    """

    def test_returns_positive_int(self) -> None:
        for v in [
            ExprValue(0),
            ExprValue(False),
            ExprValue(""),
            ExprValue(None),
            ExprValue([]),
        ]:
            assert v.memory_size() > 0
            assert isinstance(v.memory_size(), int)

    def test_string_grows_with_payload(self) -> None:
        small = ExprValue("a")
        large = ExprValue("a" * 1000)
        assert large.memory_size() > small.memory_size()

    def test_list_grows_with_payload(self) -> None:
        small = ExprValue([1])
        large = ExprValue(list(range(1000)))
        assert large.memory_size() > small.memory_size()


class TestDecimalConversion:
    """Tests that ExprValue accepts ``decimal.Decimal`` and any subclass via
    proper ``isinstance`` dispatch (rather than a string type-name compare)."""

    def test_decimal_subclass_accepted(self) -> None:
        class MyDecimal(Decimal):
            pass

        v = ExprValue(MyDecimal("3.14"))
        assert str(v) == "3.14"

    def test_unrelated_class_named_decimal_rejected(self) -> None:
        """A user-defined class named ``Decimal`` that is not a real
        ``decimal.Decimal`` falls through to the generic ``TypeError``
        rather than being silently coerced."""

        class Decimal:  # noqa: F811 — intentional shadow to defeat type-name compare
            def __float__(self) -> float:
                return 0.0

            def __str__(self) -> str:
                return "fake"

        with pytest.raises(TypeError, match="Cannot convert"):
            ExprValue(Decimal())


class TestI64OverflowMapping:
    """Out-of-range integers are reported as ``ExpressionError``, not
    PyO3's default ``OverflowError``, matching the pure-Python
    reference's ``Integer overflow ...`` contract."""

    def test_int_above_i64_max(self) -> None:
        from openjd.expr import ExpressionError

        with pytest.raises(ExpressionError) as excinfo:
            ExprValue(2**63)
        # Full message pinned per AGENTS.md "Test Quality Standard":
        # the binding must produce the reference's canonical phrasing
        # rather than leaking PyO3's internal OverflowError text.
        assert str(excinfo.value) == "Integer overflow: result is outside the 64-bit signed range"

    def test_int_below_i64_min(self) -> None:
        from openjd.expr import ExpressionError

        with pytest.raises(ExpressionError) as excinfo:
            ExprValue(-(2**63) - 1)
        assert str(excinfo.value) == "Integer overflow: result is outside the 64-bit signed range"

    def test_i64_max_accepted(self) -> None:
        v = ExprValue(2**63 - 1)
        assert v.item() == 2**63 - 1

    def test_i64_min_accepted(self) -> None:
        v = ExprValue(-(2**63))
        assert v.item() == -(2**63)


class TestUnresolvedExtraction:
    """``ExprValue.unresolved(T)`` is a placeholder that carries a type
    constraint but no concrete value. Calls that try to extract a
    Python value from it (``.item()``, ``str(...)``) must raise
    ``ExpressionTypeError`` — silently returning ``None`` or a debug
    sentinel like ``"<unresolved[T]>"`` would let static-validation
    code accidentally consume placeholder values as if they were real,
    masking real bugs in evaluation paths."""

    def test_item_raises_on_unresolved(self) -> None:
        with pytest.raises(ExpressionTypeError, match="value is not known"):
            ExprValue.unresolved(ExprType("int")).item()

    def test_item_raises_with_type_name_in_message(self) -> None:
        # The error message names the unresolved type so callers can
        # see *what kind* of placeholder they tried to extract from.
        with pytest.raises(ExpressionTypeError, match="unresolved"):
            ExprValue.unresolved(ExprType("string")).item()

    def test_str_raises_on_unresolved(self) -> None:
        with pytest.raises(ExpressionTypeError, match="value is not known"):
            str(ExprValue.unresolved(ExprType("int")))

    def test_repr_does_not_raise_on_unresolved(self) -> None:
        # ``__repr__`` is a debug-print convenience and *should* still
        # work — Python's debugging convention is that ``repr`` does
        # not raise. Only ``str``/``__str__`` and ``item()`` raise.
        r = repr(ExprValue.unresolved(ExprType("int")))
        assert "unresolved" in r
