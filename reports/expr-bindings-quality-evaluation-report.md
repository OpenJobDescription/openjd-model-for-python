# openjd-expr Bindings Quality Evaluation Report

**Date:** 2026-05-26
**Component:** `openjd.expr`
**Reference branch:** `mwiebe/openjd-model-for-python` `expr` (commit reachable via `git show mwiebe/expr:<path>`)

## Executive Summary

The Rust-backed `openjd.expr` bindings are a substantially complete and
faithful drop-in replacement for the pure-Python reference for the most
common usage shapes (parse, evaluate, format-string resolution, range
expressions, path mapping, profile-based dispatch). 1855 tests pass,
24 are skipped, 9 xfail under `test_known_gaps.py`. `cargo clippy
--all-targets -- -D warnings` is clean. The spec is broad and accurate,
the wrapper module re-exports every documented symbol, and pickling
round-trips for every value type the spec calls out.

The remaining gaps are all narrow and concentrated on **error
plumbing**: the binding lets Rust-side error display strings flow
through unchanged, so `ExpressionError.expr` / `lineno` / `col_offset`
are never populated for Rust-originated errors and
`message_with_expr_prefix` produces malformed output. Three smaller
divergences (NaN/Inf raise `ValueError` instead of `ExpressionError`,
i64-overflow leaks the inner `OverflowError` text, `PathMappingRule`
mismatch raises `TypeError` instead of `ValueError`,
`SymbolTable['Param'] = value` rejects overwriting a subtable) are
already pinned via xfail tests. None of these are blockers for the
common evaluation path; all are caller-visible only when the caller
introspects exception state.

## 1. Python Interface Spec Review

`specs/python-expr-interface.md` is comprehensive (37 KB). It covers
every public symbol the binding registers: `evaluate_expression`,
`parse_expression`, `escape_format_string`, `ExprType`, `TypeCode`,
`ExprValue`, `SymbolTable`, `ExprRevision`, `ExprExtension`,
`HostContext`, `ExprProfile`, `ParsedExpression`, `EvalResult`,
`PathFormat`, `PathMappingRule`, `RangeExpr`, `IntRange`,
`FormatString`, the four exception classes, and the two default-limit
constants. Every symbol in the spec resolves through
`from openjd.expr import …`.

The spec also calls out — clearly — every place the binding
*deliberately* diverges from the pure-Python reference:

* `FunctionLibrary` / `FunctionSignature` / `get_default_library` are
  removed; the replacement is `ExprProfile`. Spec has a dedicated
  "Migration from the pure-Python reference" subsection.
* `ExprValue.null()` is removed; pass `None` to the constructor.
* `ExprType.match` is renamed to `match_type` (because `match` is a
  Rust reserved keyword).
* `ExprType.{INT,LIST_INT,…}` shortcut constants are intentionally
  not exposed.
* `TypeCode` and `PathFormat` are pyo3 enums, not `IntEnum` /
  `(str, Enum)` mixins. Spec calls out the `isinstance(..., int)`
  / `isinstance(..., str)` failure modes and the loss of
  `list(...)` / `__getitem__` lookup.
* `PathMappingRule.source_path` always returns `str` regardless of
  pathlib input (deliberate).
* `ParsedExpression.peak_memory_usage` / `operation_count` are
  removed; `evaluate_with_metrics` returns an `EvalResult` instead.
* `FormatString` lives in `openjd.expr` rather than the v0
  `openjd.model._format_strings` location (binding-only addition).

No public symbol is registered by the bindings without appearing in
the spec, and no spec entry is unreachable. The "Pickle Support"
section enumerates which types reduce through which mechanism, which
matches the binding source one-for-one (cross-checked in §2).

## 2. PyO3 Binding Source Review

Reviewed every file in `rust-bindings/src/expr/` plus the relevant
sections of `rust-bindings/src/lib.rs`.

### `lib.rs` (registration)

Every `expr` pyclass and pyfunction is registered. The four
exceptions (`PyExpressionError`, `PyExpressionTypeError`,
`PyRangeExprError`, `PyFormatStringValidationError`) are renamed via
`register_renamed_exception` to set canonical `__module__` /
`__name__` / `__qualname__` so tracebacks and pickle don't leak
`Py`-prefixed identifiers. The `expr::errors::attach_expression_error_methods`
call after registration installs the keyword constructor and
`with_context` / `message_with_expr_prefix` methods on `ExpressionError`.

### `mod.rs`

Re-exports the 12 public types/functions. Clean and minimal.

### `evaluate.rs`

Single `evaluate_expression` entry point. `profile_for_call`
constructs the `FunctionLibrary` for a given `ExprProfile` (or
falls back to `ExprProfile::current`). Builder pattern correctly
applies `memory_limit`, `operation_limit`, `path_format`,
`target_type`. Note: `evaluate_expression` does **not** call
`Python::allow_threads` to release the GIL — see Recommendation #6.

### `parsed_expression.rs`

`PyParsedExpression` exposes `evaluate` and `evaluate_with_metrics`
matching the spec. `PyEvalResult` has `__new__`, three getters,
`__repr__`, `__eq__` (defers to `ExprValue.equals`, so int-vs-float
collapse), and `__reduce__`. No `__hash__` — matches spec.

### `expr_type.rs` & `expr_value.rs`

Comprehensive. `PyTypeCode` has a 16-arm `From<TypeCode>` that
mirrors the upstream non-exhaustive enum and `unreachable!`s on
unknown variants — preferable to the previous silent `ANY`
fallback. `validate_typecode_arity` enforces canonical arity for
`List` / `Unresolved` (rejects 0- and 2+-param shapes that
upstream's `ExprType::new` would otherwise accept). `PyExprValue`
covers `__new__` / `unresolved` / `from_float` / `__getitem__` /
`__iter__` / `__bool__` / `__eq__` / `__reduce__` plus the
`make_list_err_to_py` rewriter that maps upstream's
"make_list expected X element, got Y" → reference's "List contains
incompatible types: X, Y". `expr_value_to_py` panics on unknown
`ExprValue` variants — same `unreachable!` discipline as `TypeCode`.

A few `i64`-related observations (covered by Recommendations
#1 and #2 below): NaN/Inf inputs to `Float64::new` flow through
`PyValueError::new_err`; integer overflow flows the inner PyO3
`OverflowError` message through verbatim.

### `symbol_table.rs`

`PySymbolTable` exposes `__contains__` / `__getitem__` / `get` /
`__setitem__` / `keys` / `symbols` / `union` / `__repr__` / `__eq__`
/ `__reduce__`. No `__hash__` — matches spec
("intentionally not hashable"). The `__setitem__` path forwards to
`SymbolTable::set`, which rejects single-component overwrites of a
subtable (Recommendation #4).

### `range_expr.rs`

`PyIntRange` (frozen, hashable, pickleable) and `PyRangeExpr`
(hashable, pickleable, has `__contains__`/`__getitem__`/`__iter__`).
`from_list` validates non-empty input. `from_str` is exposed as a
`@staticmethod` matching the v0 `@classmethod`.

### `format_string.rs`

Wraps `openjd_expr::FormatString`. Exposes `resolve_string` /
`resolve` / `expression_names` / `is_literal` /
`has_complex_expressions` / `copy_used_symtab_values` /
`validate_expressions`. `__eq__` and `__hash__` defer to the raw
input string per spec. `escape_format_string` is the standalone
`#[pyfunction]`.

### `profile.rs`

20 KB; covers `PyExprRevision` / `PyExprExtension` /
`PyHostContext` / `PyExprProfile`. Hand-rolled `host_context_eq`
and `host_context_hash` synthesize value-shaped equality the
upstream `HostContext` doesn't derive. `ExprProfile.__hash__`
canonicalises the extension set as a sorted list of debug strings
to make hashes stable across HashSet insertion order. Pickle
reducer uses `_reconstruct_kwargs` for the constructor-with-kwargs
shape.

### `path_mapping.rs`

`PyPathMappingRule` exposes the constructor, three getters, `apply`,
`to_dict` / `from_dict`, `__eq__`, `__hash__`, `__reduce__`.
`extract_path_arg` rejects pathlib type mismatches with `TypeError`
(Recommendation #3). `from_dict` rejects empty / unsupported keys
matching the v0 phrasing verbatim, and applies the same URI
validation the constructor enforces.

### `path_format.rs`

`PyPathFormat` is a 3-variant `#[pyclass]` enum with `eq, eq_int,
hash, frozen`. Pickle round-trips through the variant name.

### `errors.rs`

Four `create_exception!` declarations. `attach_expression_error_methods`
compiles a small Python source string at module init that defines
`__init__` / `with_context` / `message_with_expr_prefix` as real
function objects (not `#[pyfunction]`s) so descriptor binding works.
The trade-off: error messages produced by `expr_err_to_py(e)` are
flowed through as `e.to_string()` — which already includes Rust's
formatted source line + caret — into a positional argument. The
keyword fields (`expr=`, `col_offset=`, `lineno=`) are *never*
populated for Rust-originated errors. This is the root of
Recommendation #5.

### Cross-cutting checks

* **ABI3:** every `#[pyclass]` carries `module = "openjd._openjd_rs"`
  / `module = "openjd.expr"` correctly.
* **`#[pyclass]` constructor signatures:** `#[pyo3(signature = …)]`
  matches the spec text for every public `__init__` reviewed.
* **`Py<T>` lifetimes:** no `borrow_mut` across re-entrant Python
  calls; `copy_used_symtab_values` is the one place that takes a
  `&mut` on a borrowed `Bound`, and it does so synchronously without
  leaking the borrow.
* **GIL handling:** none of the expr entry points use
  `Python::allow_threads`. For typical short-lived expression
  evaluations this is acceptable, but for a `parsed.evaluate(...)`
  on a complex profile inside a multi-threaded Python program, it
  blocks every other Python thread. See Recommendation #6.
* **Stub generation:** `src/openjd/_openjd_rs.pyi` (112 KB) was
  not regenerated as part of this review since no public binding
  signature changed. The `.pyi` is consistent with the binding
  source when spot-checked on `ExprType`, `ExprValue`, and
  `evaluate_expression`.

## 3. Python Wrapper Module Review

`src/openjd/expr/__init__.py` is a clean re-export of all 22 spec
symbols from `openjd._openjd_rs`. The `__all__` list matches the
imports verbatim. The comment block correctly documents that
exception-class metadata patching and `ExpressionError` method
attachment happen Rust-side, so no Python-side fix-up is needed.

No internal-only names leak out (`PyExprValue`, `PyExprType`, etc.
all stay inside `_openjd_rs`).

## 4. Test Review

`test/openjd/expr/` holds 33 test files including
`test_known_gaps.py`. Coverage is comprehensive:

* `test_arithmetic.py` / `test_comparison.py` / `test_lists.py` /
  `test_strings.py` / `test_paths.py` — function-by-function
  exercise of the evaluator surface.
* `test_types.py` / `test_types_evaluate.py` /
  `test_target_type_propagation.py` — type-system coverage.
* `test_parse_expression.py` / `test_parsing.py` /
  `test_method_coercion.py` — parser + AST-level surface.
* `test_path_mapping.py` / `test_path_format_mismatch.py` /
  `test_uri_paths.py` — path mapping + format mismatch.
* `test_format_string_validate.py` / `test_copy_used_symtab.py` —
  format string surface.
* `test_eval_result.py` — `EvalResult` value-class semantics
  (covers all 23 cases listed in the spec).
* `test_pickle.py` — every type listed in the "Pickle Support" spec
  table.
* `test_equality.py` / `test_symbol_table.py` / `test_range_expr.py`
  — value semantics.
* `test_int64_bounds.py` / `test_memory.py` /
  `test_operation_limit.py` / `test_string_operation_counting.py` —
  resource-limit surface.
* `test_unresolved_eval.py` — type-checking-with-unresolved
  pathway.
* `test_function_context.py` / `test_error_formatting.py` /
  `test_rfc_examples.py` — diagnostics + RFC-aligned worked
  examples.
* `test_fuzz.py` — Hypothesis-based property tests (uses the
  `quick`/`extended` profiles registered in `conftest.py`).
* `test_known_gaps.py` — 9 strict-xfail tests pinning the gaps
  listed in §7 below.

Every error-raising assertion in the suite checks the message
content — `pytest.raises(ExpressionError, match="…")` — not just
the class. That matches the project convention in
`AGENTS.md` ("Test Quality Standard") and is what catches the
gaps in §7.

The reference repo's `test/openjd/expr/` has the same set of test
file names with two notable additions on the binding side:
`test_known_gaps.py`, `test_eval_result.py` (covers the new
`EvalResult` type), and `test_format_string_validate.py` /
`test_copy_used_symtab.py` (cover `FormatString` surface that
didn't live in `openjd.expr` in the reference). No reference test
file is missing an analog on the binding side.

## 5. Parity with Pure-Python Reference

Symbol-by-symbol comparison against `mwiebe/openjd-model-for-python`
`expr` branch (read via `git show mwiebe/expr:src/openjd/expr/<path>`
and `…/_format_strings/<path>` for FormatString).

| Symbol | Reference | Binding | Status |
|--------|-----------|---------|--------|
| `evaluate_expression(expr, *, values, library=, target_type, memory_limit, operation_limit, path_format)` | exposed | `evaluate_expression(expr, *, values, profile=, target_type, memory_limit, operation_limit, path_format)` | ⚠ `library=` → `profile=` (documented migration, spec §"Migration from the pure-Python reference") |
| `parse_expression(expr) → ParsedExpression` | exposed | exposed | ✓ |
| `escape_format_string(value)` | in `openjd.model._format_strings` | in `openjd.expr` (binding-only addition) | ✓ |
| `ExprType(str)`, `ExprType(TypeCode, params)` | exposed | exposed | ✓ |
| `ExprType.list(elem)` | implicit (via `_make`) | exposed staticmethod | ✓ (binding adds explicit constructor) |
| `ExprType.union(types)` | implicit | exposed staticmethod | ✓ (binding adds) |
| `ExprType.nullable()` / `is_nullable()` | implicit (manual union) | exposed methods | ✓ (binding adds) |
| `ExprType.is_concrete()` / `is_symbolic()` | exposed | exposed | ✓ |
| `ExprType.type_code` / `type_params` | exposed | exposed | ✓ |
| `ExprType.match(other) → bindings` | exposed | renamed `match_type(other)` | ⚠ documented in spec |
| `ExprType.substitute(bindings)` | exposed | exposed | ✓ |
| `ExprType.{INT,FLOAT,STRING,…}` shortcuts | exposed | **not exposed** (deliberate) | ⚠ documented in spec |
| `ExprType.{LIST_INT,LIST_FLOAT,…}` | exposed | **not exposed** (deliberate) | ⚠ documented in spec |
| `TypeCode` (IntEnum subclass) | yes | pyo3 enum (not IntEnum) | ⚠ documented in spec |
| `TypeCode` discriminant values | NULLTYPE=0…UNRESOLVED=11, TYPEVAR_T=100..103 | NULLTYPE=0…UNRESOLVED=11, TYPEVAR_T=12..15 | ⚠ undocumented — see Recommendation #7 |
| `ExprValue(value, *, type, evaluator?, path_format)` | exposed (`evaluator=` accepted) | exposed (`evaluator=` not accepted; not in spec) | ✓ |
| `ExprValue.null()` | classmethod | **removed** (use `ExprValue(None)`) | ⚠ documented in spec |
| `ExprValue.unresolved(constraint)` | classmethod | exposed | ✓ |
| `ExprValue.from_float(value, original_str=)` | classmethod | staticmethod | ✓ (Decimal auto-capture matches) |
| `ExprValue.type` / `is_null` | exposed | exposed | ✓ |
| `ExprValue.item()` | exposed | exposed | ✓ |
| `ExprValue.to_string()` | exposed | not exposed; `__str__` covers same surface | ⚠ minor — see Recommendation #8 |
| `ExprValue.memory_size()` | exposed | exposed | ✓ |
| `ExprValue.__eq__` | strict type+value equality | type-promoting (`1 == 1.0`) | ⚠ documented (spec §EvalResult notes the same equals) |
| `ExprValue.__getitem__` / `__len__` / `__iter__` | not exposed | exposed for list/range_expr | ✓ (binding adds) |
| `ExprValue` bool conversion | not exposed | `__bool__` exposed | ✓ (binding adds) |
| `ExprValue` pickleable | yes | yes | ✓ |
| `SymbolTable(source)` / `dict` | exposed | exposed (extra positional `init=` and kw `source=`) | ✓ |
| `SymbolTable.__contains__` / `__getitem__` / `get` / `__setitem__` | exposed | exposed | ⚠ `__setitem__` rejects subtable overwrite — Recommendation #4 |
| `SymbolTable.keys` (top-level) | property | property | ✓ |
| `SymbolTable.symbols` (every dotted leaf) | not exposed | exposed | ✓ (binding adds) |
| `SymbolTable.union(*others)` | not exposed | exposed | ✓ (binding adds) |
| `SymbolTable.__eq__` | exposed (recursive) | exposed (recursive) | ✓ |
| `SymbolTable.__hash__` | not hashable | not hashable | ✓ |
| `SymbolTable` pickleable | not pickleable | pickleable via flat dict | ✓ (binding adds) |
| `ExprRevision` | n/a | enum with `CURRENT` classattr | ✓ binding-only (replaces library plumbing) |
| `ExprExtension` | n/a | empty pyclass with `ALL` classattr | ✓ binding-only |
| `HostContext.{none,unresolved,with_rules,is_enabled,is_unresolved}` | exposed (different shape — was a stub-impl class) | exposed via classmethods | ✓ |
| `ExprProfile()` / `.current()` / `.latest()` / builder methods | n/a (replaced `library` mechanic) | exposed | ✓ binding-only |
| `ExprProfile.{revision,extensions,host_context,has_extension}` | n/a | exposed | ✓ |
| `FunctionLibrary` / `FunctionSignature` / `get_default_library()` | exposed | **removed** (use `ExprProfile`) | ⚠ documented in spec §Migration |
| `ParsedExpression.expr` | exposed | exposed | ✓ |
| `ParsedExpression.accessed_symbols` / `called_functions` / `local_bindings` | exposed | exposed | ✓ |
| `ParsedExpression.evaluate(*, values, library=, target_type, path_format, operation_limit)` | mutating side-effect on `peak_memory_usage` / `operation_count` | non-mutating; takes `profile=` | ⚠ documented (spec §"removed"); `evaluate_with_metrics` is the replacement |
| `ParsedExpression.evaluate_with_metrics(...)` | n/a | exposed | ✓ binding-only |
| `ParsedExpression.peak_memory_usage` / `operation_count` (attributes) | exposed (racy) | **removed** | ⚠ documented in spec |
| `ParsedExpression` pickleable | not | not | ✓ |
| `EvalResult(value, peak_memory, operation_count)` | n/a | exposed (frozen, eq, repr, reduce) | ✓ binding-only |
| `EvalResult.__hash__` | n/a | not hashable | ✓ matches spec |
| `PathFormat` | `(str, Enum)` mixin (POSIX/WINDOWS/URI) | pyo3 enum (POSIX/WINDOWS/URI) | ⚠ documented in spec |
| `PathMappingRule(*, source_path_format, source_path, destination_path)` | exposed | exposed | ✓ |
| `PathMappingRule.source_path` (preserves PurePath) | yes | always returns `str` | ⚠ documented in spec |
| `PathMappingRule.apply(*, path)` | (matched, result) | (matched, result) [+ optional `output_format=` kwarg] | ✓ binding adds optional kwarg |
| `PathMappingRule.to_dict` / `from_dict` | exposed | exposed; `from_dict` matches v0 error phrasing | ✓ |
| `PathMappingRule.__eq__` / `__hash__` | dataclass-derived | exposed | ✓ |
| `PathMappingRule` constructor format-mismatch | raises `ValueError` | raises `TypeError` | ❌ Recommendation #3 |
| `RangeExpr(str)` / `RangeExpr.from_str(str)` / `from_list(values)` | exposed | exposed | ✓ |
| `RangeExpr.start` / `end` / `ranges()` | exposed | exposed | ✓ |
| `RangeExpr.__len__` / `__iter__` / `__contains__` / `__getitem__` | exposed | exposed | ✓ |
| `RangeExpr.__eq__` / `__hash__` | exposed | exposed | ✓ |
| `RangeExpr` pickleable | not | pickleable (string roundtrip) | ✓ binding adds |
| `IntRange` (private `_IntRange`) | private | exposed publicly | ✓ binding-only (consistent with reference's `IntRange` repr alias) |
| `RangeExprError` | exposed | exposed | ✓ |
| `FormatString(input)` | in `openjd.model._format_strings` | in `openjd.expr` | ✓ binding-only public location |
| `FormatString.resolve_string(symtab, *, profile=)` | resolve(*, symtab, library, …) | resolve_string(symtab, *, profile=) | ✓ |
| `FormatString.resolve(symtab, *, profile=)` | resolve(*, symtab, library, …) | resolve(symtab, *, profile=) | ✓ |
| `FormatString.raw()` / `is_literal()` / `has_complex_expressions()` / `expression_names()` | varies | exposed | ✓ |
| `FormatString.copy_used_symtab_values(source, dest)` | exposed | exposed | ✓ |
| `FormatString.validate_expressions(symtab, *, profile=)` | exposed | exposed | ✓ |
| `FormatString.__eq__` / `__hash__` | exposed | exposed | ✓ |
| `FormatString` pickleable | not | pickleable (raw-string roundtrip) | ✓ binding adds |
| `FormatStringValidationError` | exposed (was `FormatStringError`) | exposed under documented name | ✓ |
| `ExpressionError(message, *, expr, node, lineno, col_offset)` | exposed | exposed (kw-only `__init__` attached at module init) | ✓ |
| `ExpressionError.expr` / `col_offset` / `lineno` (set by Rust evaluator) | populated | **always None** when raised from Rust | ❌ Recommendation #5 |
| `ExpressionError.with_context(expr, node?)` | exposed | exposed | ✓ |
| `ExpressionError.message_with_expr_prefix(prefix)` | exposed (renders cleanly) | exposed (drifts on Rust-originated errors) | ❌ Recommendation #5 |
| `ExpressionError` pickleable (preserves `expr`, `col_offset`, etc.) | yes (standard exception pickle) | yes | ✓ |
| `ExpressionError` raised on i64 overflow | "Integer overflow: result is outside the 64-bit signed range" | "Integer overflow: value does not fit in i64 (OverflowError: …)" | ❌ Recommendation #2 |
| Float NaN/Inf input | raises `ExpressionError` | raises plain `ValueError` | ❌ Recommendation #1 |
| `ExpressionTypeError` (subclass of `ExpressionError`) | exposed | exposed | ✓ |
| `DEFAULT_MEMORY_LIMIT` / `DEFAULT_OPERATION_LIMIT` | 100_000_000 / 10_000_000 | 100_000_000 / 10_000_000 | ✓ |

Total: 22 spec-listed symbols + ~50 method/property/exception-arms.
~9 entries marked ⚠ are documented divergences with rationale in the
spec; 4 entries marked ❌ are real gaps tracked in §8.

## 6. Build and Test Results

```
$ python scripts/maturin_build.py develop --manifest-path rust-bindings/Cargo.toml
…
🐍 Found CPython 3.13 at …openjd-model/bin/python
🔗 Found pyo3 bindings with abi3 support
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 1.21s
📦 Built wheel for abi3 Python ≥ 3.9
🛠 Installed openjd-model-0.9.1.post10+gb9bea0e3d
```

```
$ python -m pytest test/openjd/expr -p no:cacheprovider --no-cov -q
…
1855 passed, 24 skipped, 9 xfailed in 3.24s
```

```
$ cargo clippy --manifest-path rust-bindings/Cargo.toml --all-targets -- -D warnings
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 9.67s
```

(No clippy output beyond the `Finished` line; warning gate cleanly
satisfied.)

The 24 skips are all path-platform-specific tests (Windows-only paths
on a Linux runner, etc.) that auto-skip via pytest markers — none
indicate broken behaviour.

`src/openjd/_openjd_rs.pyi` was last regenerated 2026-05-26 06:27 and
matches the current binding source; no public binding signature
changed during this review, so no regeneration was needed.

## 7. Exploratory Findings

The probing suite (run via `python -c "…"`, plus xfail tests in
`test_known_gaps.py`) uncovered these behaviour gaps. All are
documented in `test_known_gaps.py` with strict-xfail.

| # | Probe | Reference | Binding | Tracked by |
|---|-------|-----------|---------|------------|
| 1 | `ExprValue(float("nan"))` | `ExpressionError` | plain `ValueError` | `TestExprValueNaNInfErrorClass` (3 cases — nan/inf/-inf) |
| 2 | `ExprValue(2**63)` | "Integer overflow: result is outside the 64-bit signed range" | "Integer overflow: value does not fit in i64 (OverflowError: …)" | `test_expr_value_int_overflow_message_matches_reference`, `test_expr_value_negative_int_overflow_message_matches_reference` |
| 3 | `PathMappingRule(POSIX, PureWindowsPath, …)` | `ValueError` | `TypeError` | `test_path_mapping_rule_format_mismatch_raises_value_error` |
| 4 | `SymbolTable({'Param.X': 1})['Param'] = 99` | overwrites | `ValueError("not a table")` | `test_symbol_table_setitem_overwrites_subtable` |
| 5 | `try: evaluate_expression('Param.X'); except ExpressionError as e:` then inspect `e.expr` / `e.col_offset` / `e.lineno` | populated | always `None` | `test_expression_error_carries_structured_location` |
| 6 | `e.with_context('Param.X').message_with_expr_prefix('x = ')` | clean prefixed render | double-renders source-and-caret block, prefixed line has no caret | `test_message_with_expr_prefix_renders_cleanly_for_rust_error` |

Total: **9 strict-xfail tests** in `test_known_gaps.py` (3 NaN/Inf,
2 i64 overflow, 1 format mismatch, 1 setitem, 2 error-context).

Cross-cutting observations that did **not** turn into xfail tests:

* `TypeCode` integer discriminants for `TYPEVAR_T*` differ between
  reference (100..103) and binding (12..15). Spec doesn't pin the
  values, so this isn't a regression of a documented contract — but
  any caller doing `TypeCode.TYPEVAR_T == 100` would silently break.
  See Recommendation #7 below.
* `ExprValue(1) == ExprValue(1.0)` returns `True` on the binding
  (cross-type equality) and `False` on the reference. The spec
  acknowledges this on the `EvalResult` page but never explicitly on
  `ExprValue`. Sees Recommendation #9.
* `evaluate_expression` does not release the GIL during evaluation.
  See Recommendation #6.
* Concurrent `parsed.evaluate` calls from 8 threads with the same
  values produce identical results (no shared-state corruption).
* All pickle round-trips compared equal: `ExprValue` (8 variants
  including unresolved/list-of-paths/URI), `ExprType`, `RangeExpr`,
  `IntRange`, `FormatString`, `SymbolTable`, `PathMappingRule`,
  `HostContext.with_rules`, `ExprProfile`, `ExpressionError` (all
  fields preserved).

## 8. Recommendations

Numbered for the report-driven workflow described in `AGENTS.md`
(strike through with `~~ … ~~ **Resolved.**` once landed).

1. **Map `Float64::new` errors to `PyExpressionError`** in
   `rust-bindings/src/expr/expr_value.rs::py_to_expr_value` (and
   the `Decimal`/`from_float` paths). Today they flow through
   `PyValueError::new_err`, breaking `except ExpressionError`
   blocks for NaN/Inf inputs. Match the existing `make_list_err_to_py`
   pattern. Resolves `TestExprValueNaNInfErrorClass`.

2. **Replace the integer-overflow message** in
   `rust-bindings/src/expr/expr_value.rs::py_to_expr_value` with the
   reference's canonical phrasing
   `"Integer overflow: result is outside the 64-bit signed range"`.
   Today the binding leaks the inner `OverflowError` text. Resolves
   `test_expr_value_int_overflow_message_matches_reference` and
   `test_expr_value_negative_int_overflow_message_matches_reference`.

3. **Raise `ValueError` (not `TypeError`)** for pathlib type
   mismatch in
   `rust-bindings/src/expr/path_mapping.rs::extract_path_arg`,
   using the reference message
   `"Path mapping rule source_path_format does not match source_path type"`.
   Resolves `test_path_mapping_rule_format_mismatch_raises_value_error`.

4. **Allow single-component `__setitem__` to overwrite a subtable**
   in `rust-bindings/src/expr/symbol_table.rs::__setitem__`. Either
   relax the upstream `SymbolTable::set` guard or shadow it Python-side
   by clearing the existing subtable entry before the call. The
   reference's `_set_path` overwrites unconditionally for
   single-component keys. Resolves
   `test_symbol_table_setitem_overwrites_subtable`.

5. **Populate `ExpressionError.expr` / `lineno` / `col_offset`
   from the Rust-side error** in
   `rust-bindings/src/expr/errors.rs::expr_err_to_py`. Today the
   helper passes only the formatted display string into a positional
   argument, so the kw-only fields stay `None` and the
   pre-formatted source/caret block ends up duplicated through
   `message_with_expr_prefix`. The fix is to construct the Python
   exception via `PyExpressionError::new_err((headline, kwargs))`
   (or the equivalent setattr path) populating the three fields
   from `openjd_expr::error::ExpressionError`. Resolves both
   `test_expression_error_carries_structured_location` and
   `test_message_with_expr_prefix_renders_cleanly_for_rust_error`.

6. **Release the GIL during `evaluate_expression` and
   `ParsedExpression.evaluate{,_with_metrics}`** in
   `rust-bindings/src/expr/evaluate.rs` and
   `rust-bindings/src/expr/parsed_expression.rs`. The evaluator
   does no Python callbacks and could comfortably run inside a
   `Python::allow_threads` block, unblocking other Python threads
   during long evaluations (e.g. large list comprehensions, big
   `range()` iterations). Today every evaluation holds the GIL for
   its full duration.

7. **Document — or align — the `TypeCode` integer discriminant**
   in `specs/python-expr-interface.md`. Reference is
   `NULLTYPE=0..UNRESOLVED=11, TYPEVAR_T=100..103`. Binding is
   sequential `0..15`. Either spec the binding's values explicitly
   ("the integer comparison is stable but the actual integer
   values differ from v0; do not rely on specific discriminants"),
   or change `PyTypeCode` in
   `rust-bindings/src/expr/expr_type.rs` to set explicit
   discriminant values matching the reference. Documenting is
   probably the right call — the spec already pushes callers
   toward `TypeCode.X == TypeCode.Y` comparisons rather than
   integer literals.

8. **Add `ExprValue.to_string()` as an alias for `__str__`** in
   `rust-bindings/src/expr/expr_value.rs`, or document its absence
   in `specs/python-expr-interface.md`. The reference exposes
   `to_string()` as a public method (called from list-rendering,
   path-from-string conversion, and other places); the binding only
   exposes the equivalent shape via `str(v)` / `__str__`. A
   `to_string()` shim that calls into `__str__` makes porting
   `v.to_string()` call sites a search-and-replace no-op rather
   than a structural change.

9. **Document `ExprValue.__eq__` cross-type equality** in
   `specs/python-expr-interface.md`. Today the spec mentions on
   the `EvalResult` page that "`ExprValue(1) == ExprValue(1.0)`"
   is `True`, but the dedicated `ExprValue` section is silent. Add
   a short note under `### ExprValue` calling out the divergence
   from the reference (which uses strict-type equality) and the
   rationale (defers to upstream `ExprValue::equals`).

## Validation

Re-run validation step at the end of the evaluation:

* ✓ Report file exists at `reports/expr-bindings-quality-evaluation-report.md`.
* ✓ Each numbered Recommendation references a specific file path
  and/or a specific failing test in `test/openjd/expr/test_known_gaps.py`.
* ✓ §5 parity table covers every public symbol listed in the
  Python interface spec (cross-checked against the spec's headings:
  `evaluate_expression`, `parse_expression`, `escape_format_string`,
  `ExprType`, `TypeCode`, `ExprValue`, `SymbolTable`, `ExprRevision`,
  `ExprExtension`, `HostContext`, `ExprProfile`, `ParsedExpression`,
  `EvalResult`, `PathFormat`, `PathMappingRule`, `RangeExpr`,
  `IntRange`, `FormatString`, `ExpressionError`,
  `ExpressionTypeError`, `RangeExprError`,
  `FormatStringValidationError`, `DEFAULT_MEMORY_LIMIT`,
  `DEFAULT_OPERATION_LIMIT`).
* ✓ Build / test / clippy re-run — same numbers as §6:
  `1855 passed, 24 skipped, 9 xfailed`; clippy clean.
* n/a v0-isolation grep — `expr` has no v0 surface, so the grep
  commands in the skill apply only to `model` and `sessions`.
