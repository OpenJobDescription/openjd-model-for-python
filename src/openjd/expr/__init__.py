# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""OpenJD Expression Language — Rust-backed implementation."""

from openjd._openjd_rs import (
    EvalResult,
    ExprType,
    ExprValue,
    SymbolTable,
    SerializedSymbolTable,
    evaluate_expression,
    parse_expression,
    ParsedExpression,
    ExpressionError,
    ExpressionTypeError,
    PathMappingRule,
    PathFormat,
    RangeExpr,
    IntRange,
    RangeExprError,
    FormatString,
    FormatStringValidationError,
    escape_format_string,
    TypeCode,
    DEFAULT_MEMORY_LIMIT,
    DEFAULT_OPERATION_LIMIT,
    # Profile types — pass to entry points like
    # `evaluate_expression(..., profile=...)`,
    # `ParsedExpression.evaluate(..., profile=...)`, and
    # `FormatString.resolve*(..., profile=...)`. Mirror
    # openjd_expr's profile module:
    # https://github.com/OpenJobDescription/openjd-rs/blob/main/crates/openjd-expr/src/profile.rs
    ExprProfile,
    ExprRevision,
    ExprExtension,
    HostContext,
)

# Note: the `__module__` / `__name__` / `__qualname__` of the Rust-backed
# exceptions (ExpressionError, FormatStringValidationError, etc.) are set by
# the `_openjd_rs` module init in Rust to their canonical user-facing values
# (e.g. `openjd.expr.ExpressionError`). The keyword constructor and
# `with_context` / `message_with_expr_prefix` methods on `ExpressionError`
# are also installed Rust-side, in `rust-bindings/src/expr/errors.rs`
# (`attach_expression_error_methods`). No Python-side fix-up needed.


__all__ = [
    # Types
    "ExprType",
    "TypeCode",
    "ExprValue",
    "SymbolTable",
    "SerializedSymbolTable",
    "ParsedExpression",
    "EvalResult",
    "PathMappingRule",
    "PathFormat",
    "RangeExpr",
    "IntRange",
    "FormatString",
    # Profile
    "ExprProfile",
    "ExprRevision",
    "ExprExtension",
    "HostContext",
    # Functions
    "evaluate_expression",
    "parse_expression",
    "escape_format_string",
    # Errors
    "ExpressionError",
    "ExpressionTypeError",
    "RangeExprError",
    "FormatStringValidationError",
    # Constants
    "DEFAULT_MEMORY_LIMIT",
    "DEFAULT_OPERATION_LIMIT",
]
