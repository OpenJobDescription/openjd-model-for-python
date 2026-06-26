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

# The EXPR engine lives in the compiled extension. These module-level imports
# are reached only by code that handles an EXPR template: callers import this
# module lazily (inside functions), and the EXPR_EXTENSION gate constant lives
# in ._parser so that merely importing the parser does not load the Rust expr
# surface. The non-EXPR parse path therefore never imports this module.
from openjd._openjd_rs import (  # type: ignore[import-not-found]
    build_symbol_table,
    job_parameter_type_expr_spec,
)
from openjd.expr import (  # type: ignore[import-not-found]
    ExprProfile,
    ExprType,
    ExprValue,
    ExpressionError as RustExpressionError,
    ExpressionTypeError as RustExpressionTypeError,
    FormatString as _RustFormatString,
    FormatStringValidationError as RustFormatStringValidationError,
    HostContext,
    RangeExprError as RustRangeExprError,
    parse_expression,
)

# Errors raised by the Rust expr engine. All subclass ValueError but are
# distinct classes from the model's own ExpressionError, so they must be
# caught explicitly at the binding boundary and re-raised as model errors.
_RUST_EXPR_ERRORS = (
    RustExpressionError,
    RustExpressionTypeError,
    RustFormatStringValidationError,
    RustRangeExprError,
)


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
    """Map an OpenJD parameter type name (e.g. ``PATH``, ``LIST[INT]``,
    ``RANGE_EXPR``; case-insensitive) to the EXPR engine's spec-form type
    string (``path``, ``list[int]``, ``range_expr``), or ``None`` if the name
    is not a recognized job-parameter type.

    Delegates to the Rust ``job_parameter_type_expr_spec`` binding so the
    OpenJD-type → EXPR-type mapping (including ``LIST[...]`` nesting) lives in a
    single place — the ``openjd-model`` crate — rather than a parallel
    hand-maintained Python table that could drift.
    """
    return job_parameter_type_expr_spec(openjd_type)


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
        # typecheck() evaluates without extracting the result, so an expression
        # that is well-typed but depends on an unresolved runtime symbol passes
        # (no "cannot extract value from unresolved" boundary error to sniff for).
        parsed.typecheck(
            values=values,
            profile=ExprProfile.current().with_host_context(HostContext.unresolved()),
        )
    except _RUST_EXPR_ERRORS as exc:
        raise _ModelExpressionError(str(exc))
