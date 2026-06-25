# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Support for the EXPR extension (RFCs 0005/0006/0007) in the pure-Python
(v0) model.

The pure-Python model does not implement the EXPR expression grammar. When a
template declares the ``EXPR`` extension, format-string expressions are parsed
and evaluated by the Rust ``openjd-expr`` engine through the ``openjd._openjd_rs``
bindings. This module is the thin bridge between the two.

The typed symbol-table construction (coercing the v0 model's flat, stringly
typed values into a typed EXPR ``SymbolTable``) is performed by the Rust
``build_symbol_table`` binding; this module supplies the OpenJD-type → EXPR
type-spec mapping and re-raises Rust errors as the model's own
``ExpressionError`` at the boundary.
"""

from __future__ import annotations

from typing import Any, Optional

from .._errors import ExpressionError as _ModelExpressionError
from .._symbol_table import SymbolTable

# The EXPR engine lives in the compiled extension. Import lazily-tolerant: the
# extension is always present in a released wheel, but keeping the imports here
# (rather than at the package root) means the non-EXPR parse path never touches
# the Rust expr surface.
from openjd._openjd_rs import build_symbol_table  # type: ignore[import-not-found]
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
# ExprValue(str, type=...); list/range types are handled by the Rust
# build_symbol_table binding via expr_type_for_openjd_type below.
_OPENJD_TYPE_TO_EXPR_TYPE = {
    "INT": "int",
    "FLOAT": "float",
    "STRING": "string",
    "PATH": "path",
    "BOOL": "bool",
}

# Spelling of the LIST[...] compound type name in OpenJD spec form. Used to
# recognize and unwrap list types in expr_type_for_openjd_type.
_LIST_TYPE_PREFIX = "LIST["
_LIST_TYPE_SUFFIX = "]"


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


def symtab_to_expr_values(
    symtab: SymbolTable,
    *,
    types: Optional[dict[str, str]] = None,
    path_format: Any = None,
) -> Any:
    """Build a typed EXPR ``SymbolTable`` from the v0 (flat dotted-key)
    ``SymbolTable``.

    The typed coercion (e.g. a stored ``"10"`` of type INT → a real integer)
    and the dotted-key → nested-subtable construction are delegated to the
    Rust ``build_symbol_table`` binding, so the value typing lives next to the
    engine and stays consistent with it (PR #285 review, C3/C5).

    ``types`` maps dotted symbol names to OpenJD type names (e.g. ``"INT"``,
    ``"LIST[INT]"``); each is translated to the EXPR type spec the engine
    expects (``"int"``, ``"list[int]"``) via :func:`expr_type_for_openjd_type`.
    Names whose type has no confident EXPR mapping (e.g. ``RANGE_EXPR``) are
    omitted so the engine infers them from the value.

    Note: end-to-end evaluation of LIST[*]/RANGE_EXPR job parameters on the v0
    ``create_job`` path additionally requires those values to reach the symbol
    table as native Python values rather than stringified (``ParameterValueType``
    has no LIST/RANGE/BOOL members today), which is tracked separately.
    """
    flat = {name: symtab[name] for name in symtab.symbols}
    expr_types: dict[str, str] = {}
    for name, openjd_type in (types or {}).items():
        spec = expr_type_for_openjd_type(openjd_type)
        if spec is not None:
            expr_types[name] = spec
    return build_symbol_table(flat, expr_types or None, path_format=path_format)


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
    if t.startswith(_LIST_TYPE_PREFIX) and t.endswith(_LIST_TYPE_SUFFIX):
        inner = t[len(_LIST_TYPE_PREFIX) : -len(_LIST_TYPE_SUFFIX)]
        inner_spec = expr_type_for_openjd_type(inner)
        if inner_spec is not None:
            return f"list[{inner_spec}]"
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
