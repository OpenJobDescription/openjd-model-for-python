# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Support for the EXPR extension (RFCs 0005/0006/0007) in the pure-Python
(v0) model.

The pure-Python model does not implement the EXPR expression grammar. When a
template declares the ``EXPR`` extension, format-string expressions are parsed
and evaluated by the Rust ``openjd-expr`` engine through the ``openjd._openjd_rs``
bindings. This module is the thin bridge between the two.

Design reference:
``SuperDaveDocs/.../delivery-estimate-v3/rs/python-model-with-rust-expr``.

First-cut note: this is the "pure-Python orchestration" path (no Rust binding
change). The eventual home for the symbol-table conversion is a Rust
``build_symbol_table`` ``#[pyfunction]``; the ``ExprNode`` call site is
identical either way.
"""

from __future__ import annotations

from typing import Any, Optional

from .._errors import ExpressionError as _ModelExpressionError
from .._symbol_table import SymbolTable

# The EXPR engine lives in the compiled extension. Import lazily-tolerant: the
# extension is always present in a released wheel, but keeping the imports here
# (rather than at the package root) means the non-EXPR parse path never touches
# the Rust expr surface.
from openjd.expr import (  # type: ignore[import-not-found]
    ExprProfile,
    ExprType,
    ExprValue,
    FormatString as _RustFormatString,
    HostContext,
    parse_expression,
)
from openjd.expr import (  # noqa: F401  re-exported for callers/tests
    ExpressionError as RustExpressionError,
    ExpressionTypeError as RustExpressionTypeError,
    FormatStringValidationError as RustFormatStringValidationError,
    RangeExprError as RustRangeExprError,
)

EXPR_EXTENSION = "EXPR"
WRAP_ACTIONS_EXTENSION = "WRAP_ACTIONS"

# Errors raised by the Rust expr engine. All subclass ValueError but are
# distinct classes from the model's own ExpressionError, so they must be
# caught explicitly at the binding boundary and re-raised as model errors.
_RUST_EXPR_ERRORS = (
    RustExpressionError,
    RustExpressionTypeError,
    RustFormatStringValidationError,
    RustRangeExprError,
)

# Map an OpenJD parameter type name (spec form) to the EXPR engine's spec-form
# type string consumed by ExprType(...). Scalars coerce a string value via
# ExprValue(str, type=...); list/range types are handled in _to_expr_value.
_OPENJD_TYPE_TO_EXPR_TYPE = {
    "INT": "int",
    "FLOAT": "float",
    "STRING": "string",
    "PATH": "path",
    "BOOL": "bool",
}


def expr_profile_from_context(context: Any) -> ExprProfile:
    """Build the EXPR profile used to parse/evaluate expressions for a template.

    First cut: the current revision with the standard function library (which
    includes ``repr_sh``/``len``/arithmetic). Host-context-gated functions such
    as ``apply_path_mapping`` require path-mapping rules supplied at run time by
    the session runtime, and are intentionally not available on the model
    create-job path.
    """
    # context is a ModelParsingContextInterface; reserved for future use
    # (selecting revision / extensions). current() is sufficient for the
    # first cut because ExprExtension is empty upstream.
    return ExprProfile.current()


def _to_expr_value(value: Any, type_name: Optional[str], path_format: Any) -> Any:
    """Convert a single symbol-table value to something the EXPR engine accepts.

    - If an OpenJD type is known, coerce the (string) value to that EXPR type so
      ``Param.X`` of type INT becomes a real integer rather than the string
      ``"10"``.
    - Otherwise pass the native Python value through; ``ExprValue`` infers
      int/float/bool/str/list at the boundary.
    """
    if type_name is None:
        return value

    expr_type = _OPENJD_TYPE_TO_EXPR_TYPE.get(type_name.upper())
    if expr_type is None:
        # Unknown/aggregate type (e.g. LIST[*], RANGE_EXPR) — let the engine
        # infer from the native value for now. Typed list/range coercion is
        # follow-up work (RFC 0007 parameter types).
        return value
    if expr_type == "path":
        return ExprValue(str(value), type=ExprType("path"), path_format=path_format)
    return ExprValue(str(value), type=ExprType(expr_type))


def symtab_to_expr_values(
    symtab: SymbolTable,
    *,
    types: Optional[dict[str, str]] = None,
    path_format: Any = None,
) -> dict[str, Any]:
    """Convert the v0 (flat dotted-key) SymbolTable into a nested value tree the
    EXPR engine can consume.

    The v0 SymbolTable uses flat dotted keys (``"Param.Frame"``) and direct
    lookup; the Rust ``dict_to_symtab`` builds subtables from nested dicts. We
    split each dotted key on ``.`` (parameter names cannot contain ``.``) and
    nest accordingly, re-typing each leaf from ``types`` when available.
    """
    types = types or {}
    nested: dict[str, Any] = {}
    for dotted_name in symtab.symbols:
        leaf_value = _to_expr_value(symtab[dotted_name], types.get(dotted_name), path_format)
        cursor = nested
        segments = dotted_name.split(".")
        for segment in segments[:-1]:
            cursor = cursor.setdefault(segment, {})
        cursor[segments[-1]] = leaf_value
    return nested


def parse_expr_or_raise(expr: str) -> Any:
    """Parse an EXPR expression string with the Rust engine, re-raising parse
    failures as the model's ``ExpressionError``.
    """
    try:
        return parse_expression(expr.strip())
    except _RUST_EXPR_ERRORS as exc:
        raise _ModelExpressionError(str(exc))


def _static_validation_profile() -> ExprProfile:
    """Profile for static (parse-time) expression validation.

    Uses ``HostContext.unresolved()`` so host-context-gated functions such as
    ``apply_path_mapping`` resolve to unresolved values (valid) rather than
    raising "Unknown function", while genuinely unknown functions still fail.
    """
    return ExprProfile.current().with_host_context(HostContext.unresolved())


def static_validate_symbol_free(expr: str) -> None:
    """Statically validate an expression that references no free symbols.

    Catches literal/semantic errors that the Rust engine only raises at
    evaluation time — int64 overflow, division by zero, unknown functions,
    type mismatches, slice-step-zero, null-in-list, etc. — so that
    ``openjd check`` rejects them. Safe only for symbol-free expressions:
    with no symbols there is no risk of a wrong placeholder type causing a
    false rejection. Symbol-referencing expressions are validated once their
    symbol types are known (RFC 0007 parameter types — follow-up).
    """
    try:
        _RustFormatString("{{ " + expr + " }}").validate_expressions(
            {}, profile=_static_validation_profile()
        )
    except _RUST_EXPR_ERRORS as exc:
        raise _ModelExpressionError(str(exc))


def map_eval_error(exc: BaseException) -> _ModelExpressionError:
    """Wrap a Rust evaluation error as the model's ``ExpressionError``."""
    return _ModelExpressionError(str(exc))


def expr_type_for_openjd_type(openjd_type: str) -> Optional[str]:
    """Map an OpenJD parameter type name (e.g. ``PATH``, ``LIST[INT]``) to the
    EXPR engine's spec-form type string (``path``, ``list[int]``), or ``None``
    if there is no confident mapping (so callers fall back to name-only
    validation rather than risk a wrong type).
    """
    t = openjd_type.strip().upper()
    scalar = _OPENJD_TYPE_TO_EXPR_TYPE.get(t)
    if scalar is not None:
        return scalar
    if t.startswith("LIST[") and t.endswith("]"):
        inner = expr_type_for_openjd_type(t[len("LIST[") : -1])
        if inner is not None:
            return f"list[{inner}]"
    return None


def longest_defined_prefix(name: str, defined: set) -> Optional[str]:
    """Return the longest dotted prefix of ``name`` that is a defined symbol,
    treating any remaining segments as method/property access. E.g. for
    ``"Param.File.name"`` with ``Param.File`` defined, returns ``"Param.File"``.
    """
    segments = name.split(".")
    for end in range(len(segments), 0, -1):
        prefix = ".".join(segments[:end])
        if prefix in defined:
            return prefix
    return None


def validate_typed_expression(parsed: Any, *, typed_symbols: dict[str, str]) -> None:
    """Statically validate a parsed expression against symbols of known EXPR
    type (provided as ``{dotted_name: expr_type_string}``). Catches type
    mismatches and invalid method/property access. Raises the model's
    ``ExpressionError`` on failure.

    Symbols are supplied as ``ExprValue.unresolved(<type>)`` placeholders so the
    engine type-checks without concrete values.
    """
    values: dict[str, Any] = {}
    for dotted, type_str in typed_symbols.items():
        ev = ExprValue.unresolved(ExprType(type_str))
        cursor = values
        segs = dotted.split(".")
        for seg in segs[:-1]:
            cursor = cursor.setdefault(seg, {})
        cursor[segs[-1]] = ev
    try:
        parsed.evaluate(
            values=values,
            profile=ExprProfile.current().with_host_context(HostContext.unresolved()),
        )
    except _RUST_EXPR_ERRORS as exc:
        msg = str(exc)
        # A valid expression that merely depends on a runtime value surfaces as
        # an "unresolved" extraction error — that is success, not a failure.
        if "unresolved" in msg and "Cannot extract value" in msg:
            return
        raise _ModelExpressionError(msg)
