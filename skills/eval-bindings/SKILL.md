---
name: eval-bindings
description: Perform a quality evaluation of the Rust→Python bindings for an openjd component by reviewing the Python interface spec, the PyO3 binding source, the Python wrapper module, the test suite, and parity with the pure-Python reference implementation. Use when running `/eval-bindings COMPONENT_NAME` where component-name is one of expr, model, or sessions.
tags: [openjd, rust, python, pyo3, bindings, quality, evaluation]
---

# Eval Bindings

## Overview
Evaluate one of the three Rust→Python binding components (`expr`, `model`, `sessions`) for alignment between the Python interface spec, the PyO3 wrapper code, the Python module that re-exports the bindings, the tests, and parity with the pure-Python reference implementation. The goal is to confirm the Rust-backed binding is provide functionality that meets the same requirements as the pure-Python implementation. The bindings do not use pydantic as a dependency, but the pure-Python implementation does, so we do expect there to be differences. Produces a detailed quality report with actionable recommendations.

## Usage
Use this skill when:
- Evaluating the quality of a specific binding component (e.g. `/eval-bindings expr`)
- The user provides a component name as the first argument

Valid component names: `expr`, `model`, `sessions`

## Prerequisites

### Repository Layout

This skill assumes the `openjd-model-for-python` repo is the active workspace and that the relevant pure-Python reference repos are checked out side by side in the same parent directory. Paths in this skill are resolved relative to the `openjd-model-for-python` repo root.

```
<parent>/
├── openjd-model-for-python/    # This repo — Both v0 (pure-Python) and _v1 (Rust bindings) for `expr` and `model`. Rust bindings module also includes `sessions` but does not expose it. See GitHub mwiebe/bindings-rs branch.
├── openjd-sessions-for-python/ # Both v0 (pure-Python) and _v1 (Rust bindings) for `sessions`. Exposes functions from the single Rust bindings module in openjd-model-for-python. See GitHub mwiebe/bindings-rs branch.
├── openjd-cli/                 # Reference for sanity checks
├── openjd-rs/                  # Rust crate implementations
└── openjd-specifications/      # Canonical specs
```

### Pure-Python Reference Branch

The reference repository **MUST** be on the correct branch for the component being evaluated:

| Component | Repo | GitHub org/user | Branch |
|--------|------|-----------------|--------|
| `expr` | `openjd-model-for-python` (separate clone, or worktree) | mwiebe (fork) | `expr` |
| `model` | `openjd-model-for-python` (separate clone, or worktree) | OpenJobDescription | `mainline` |
| `sessions` | `openjd-sessions-for-python` | OpenJobDescription | `mainline` |

For `expr` and `model` the comparison is against an **earlier history of this same repo**, before it was converted to Rust-backed bindings The `v0` interface should be identical, and the `_v1` interface is under evaluation. Use a separate worktree, a separate clone, or `git show <ref>:<path>` to read the reference Python source — do NOT check out the reference branch into the active working copy.

### Specification References

The `openjd-specifications` repo (mainline branch) contains the canonical
language and runtime specifications. Cross-reference these whenever
behavior is in question:

| Component | Primary References |
|--------|--------------------|
| `expr` | `wiki/2026-02-Expression-Language.md` |
| `model` | `wiki/2023-09-Template-Schemas.md` |
| `sessions` | `wiki/2023-09-Template-Schemas.md`, `wiki/How-Jobs-Are-Run.md` |

## Core Concepts

### Four Artifacts

Every binding component has four complementary artifacts that **MUST** be reviewed together:

1. **Python interface spec** — `specs/python-<component>-interface.md`. The contract the bindings advertise to Python users. This is the public-API spec for the component.
2. **PyO3 binding source** — `rust-bindings/src/<component>/`. Rust code that wraps the underlying `openjd-<component>` crate and exposes it to Python via PyO3.
3. **Python wrapper module** — `src/openjd/<component>/` (and for `model`, `src/openjd/model/_v1/`). The Python-facing package that re-exports symbols from `_openjd_rs` under user-friendly names.
4. **Tests** — `test/openjd/<component>/` for `expr` and `sessions`; `test/openjd/model_v0/` and `test/openjd/model_v1/` for `model`.

### Five Alignment Criteria

The evaluation checks all four artifacts plus the pure-Python reference for alignment:

1. **Spec ↔ Bindings**: The Python interface spec **MUST** accurately and completely describe what the bindings expose. Every public symbol (class, function, exception, constant) the bindings register **MUST** appear in the spec; every entry in the spec **MUST** correspond to a real symbol the user can import.
2. **Bindings ↔ Wrapper Module**: Symbols re-exported by `src/openjd/<component>/__init__.py` (or its `_v1/__init__.py` for `model`) **MUST** match what the bindings register, with the names and modules the spec promises. Watch for name-mangled exception classes (`PyXxxError` instead of `XxxError`) and missing re-exports.
3. **Bindings ↔ Pure-Python Reference**: For each public function, class, method, and exception in the reference, the binding **MUST** offer a counterpart with compatible name, signature, return type, and error behaviour. Note any meaningful divergence: missing methods, renamed parameters, error messages, exception class hierarchy, default values, edge-case results. The pure-Python interface depends on pydantic within the interface definition, while the Rust bindings do not. The spec should explain why for every choice where the bindings differ from the pure-Python reference.
4. **Bindings ↔ Underlying Rust Crate**: The bindings **SHOULD** be a thin shim. The bindings **MUST NOT** silently introduce behavior that contradicts the Rust crate they wrap, because the Python contract is supposed to be the same as the Rust contract — divergence here makes the bindings unreliable for users porting between Python and Rust. The PyO3-specific glue (type conversions, GIL release, exception mapping) **SHOULD** stay idiomatic and minimal.
5. **Tests ↔ Reference Tests**: For each test file in the reference repo, there **SHOULD** be a corresponding test in this repo exercising the same behavior through the binding. Note tests that exist in the reference but have no analog here, and tests that exist here but cover behavior the reference never had.

### Isolation Requirement: `_v1` Stands Alone

The Rust-backed `_v1` surface **MUST NOT** depend on the v0
(pure-Python, pydantic-based) implementation in any way. The
intent is that v0 and `_v1` are independent ports of the same
specification — v0 will be removed once `_v1` is fully adopted,
and any v1 code that delegates to v0 would silently break at that
moment.

Concretely, the evaluator **MUST** verify the following at every
step of the review:

* `src/openjd/model/_v1/`, `src/openjd/sessions_v1/`, and the
  Rust binding source under `rust-bindings/src/<component>/`
  **MUST NOT** import from any v0 module. That includes
  `openjd.model` (top-level — it currently *is* the v0 module),
  `openjd.model.v0`, `openjd.model.v2023_09`, the v0
  `_capabilities`, `_create_job`, `_format_strings`,
  `_merge_job_parameter`, `_parse`, `_range_expr`, `_types`
  modules, and any other internal v0 helper.
* If a v1 function needs behaviour that today lives only in v0,
  the right resolution is to **re-implement** that behaviour in
  v1 using the Rust-backed types (e.g. `openjd.expr.FormatString`
  instead of v0's `openjd.model._format_strings.FormatString`),
  not to delegate or re-export. If a re-implementation is
  non-trivial, raise it as a recommendation in the report.
* Tests in `test/openjd/model_v1/`, `test/openjd/sessions-v1/`,
  and `test/openjd/expr/` **MUST NOT** import from v0 modules
  either. v0 tests live in `test/openjd/model_v0/` and
  `test/openjd/sessions-v0/` and use v0 imports — those are
  separate suites that exist only as long as v0 itself does.

When the report's parity table in §5 calls out a gap, the
recommendation **MUST** specify a v1-internal fix path — never
"delegate to v0".

### PyO3-Specific Concerns

When reviewing `rust-bindings/src/<component>/`, the agent **MUST** check the following items, because they are common sources of behavior drift between the binding and the underlying Rust crate:

- **Exception class registration**: PyO3's `create_exception!` produces a type whose `__name__` defaults to the binding-internal `Py`-prefixed identifier. Without `register_renamed_exception` (in `lib.rs`) the canonical name leaks into tracebacks, pickle, and IDE tooltips. Verify every exception is registered with the public-facing `__name__`, `__module__`, and `__qualname__`.
- **Type conversions**: `IntoPyObject`/`FromPyObject` impls **MUST** preserve types faithfully. In particular: `int` ↔ `i64`/`u64` boundary handling, `float` NaN/Inf passthrough, `pathlib.Path` ↔ `Path`/`PathBuf`, `bytes` vs `str`, and ordered vs unordered collections.
- **GIL handling**: Long-running Rust calls **SHOULD** use `Python::allow_threads` to release the GIL. Holding the GIL across blocking I/O (sessions subprocess wait, snapshots S3 ops) blocks every other Python thread.
- **`#[pyclass]` constructor signatures**: Python `__init__` signatures must match what the spec advertises. Look for `#[pyo3(signature = ...)]` mismatches against `text_signature` and the spec.
- **`Py<T>` lifetime correctness**: Make sure objects passed across the boundary are not reborrowed in ways that cause `BorrowMutError` or use-after-free in PyO3 0.20+ semantics.
- **ABI3 compatibility**: `Cargo.toml` declares `abi3-py39`. Any binding code that uses Python C API features beyond ABI3 will fail at compile time on a strict ABI3 build — but check that there are no quietly-leaked feature flags.
- **Stub generation**: `cargo run --bin stub_gen` produces `src/openjd/_openjd_rs.pyi`. This file **MUST** match the bindings; if it has drifted, regenerate it during the evaluation.

### Evaluation Procedure

Follow these steps in order:

1. **Clean slate**: Delete `reports/<component>-bindings-quality-evaluation-report.md` if it exists, **without reading it**. Starting fresh prevents bias from a previous report's framing.
2. **Read and understand the Python interface spec** in `specs/python-<component>-interface.md`.
3. **Read and understand the PyO3 binding source** in `rust-bindings/src/<component>/` and the relevant exception/registration code in `rust-bindings/src/lib.rs`.
4. **Read and understand the Python wrapper module** in `src/openjd/<component>/` (and `src/openjd/model/_v1/` for `model`).
5. **Read and understand the tests** in the corresponding `test/openjd/...` subdirectory.
6. **Compare with the pure-Python reference** (see Pure-Python Reference Branch table). Use `git show <ref>:<path>` or a worktree at the reference branch. For each public symbol in the reference, verify the binding has a behaviorally equivalent counterpart.
7. **Build and test**: Run `python scripts/maturin_build.py develop` (or `python scripts/maturin_build.py develop --features stub-gen` if regenerating stubs) and `python -m pytest test/openjd/<component>` (or `model_v0` and `model_v1` for `model`). Confirm clean compilation (no errors or warnings) and all tests pass. Run `cargo clippy --workspace -- -D warnings` against `rust-bindings/`.
8. **Verify v0 isolation**: Grep the v1 surface for any imports
   from v0. The following commands **MUST** all return zero
   matches for `model` and `sessions`:
   ```bash
   grep -rn 'from openjd\.model[^._]' src/openjd/model/_v1/ rust-bindings/src/ test/openjd/model_v1/ \
     | grep -v 'from openjd\.model\._v1' \
     | grep -v 'from openjd\.model\.errors\|from openjd\.model\.types'  # standalone v1 submodules
   grep -rn 'from openjd\.model\.v\(0\|2023_09\)' src/openjd/model/_v1/ rust-bindings/src/ test/openjd/model_v1/
   grep -rn 'from \.\._range_expr\|from \.\._capabilities\|from \.\._create_job\|from \.\._parse' src/openjd/model/_v1/
   ```
   If any v0-import slips through into the v1 surface, flag it
   as a high-priority recommendation. The fix is always to
   re-implement the needed behaviour in v1, not to keep the v0
   dependency.
9. **Exploratory testing**: Actively try to find behavior gaps between the binding and the reference. Common probes:
    - Pickle a binding object and unpickle it; verify exception class names round-trip.
    - Hash and equality of value types across types that should compare equal (e.g. `1 == 1.0`).
    - Boundary integers (`i64::MIN`, `i64::MAX`, `u64::MAX`).
    - Unicode/path edge cases that differ between Python `str` and Rust `String`.
    - Concurrent calls into the bindings from multiple Python threads.
    - The full set of error messages from the reference: do bindings raise the same exception class with the same message format?

   Write failing tests that demonstrate any issues. Land them in `test/openjd/<component>/test_known_gaps.py` (or `~/openjd-sessions-for-python/test/openjd/sessions-v1/test_known_gaps.py` for `sessions`) marked `pytest.mark.xfail` with the reason. **Every test in `test_known_gaps.py` MUST be `xfail`** — when a gap is resolved, the test moves to its proper home alongside the rest of the regular tests for that surface, not stays in `test_known_gaps.py` as a passing regression. Reference each new xfail in the report's Recommendations section so the report-driven workflow can resolve it precisely.
10. **Write the report** to `reports/<component>-bindings-quality-evaluation-report.md`.

### Report Structure

The report **MUST** include:

```markdown
# openjd-<component> Bindings Quality Evaluation Report

**Date:** YYYY-MM-DD
**Component:** `openjd.<component>`
**Reference branch:** <repo>@<ref>

## Executive Summary
Overall assessment in one paragraph. Lead with whether the bindings are a
faithful drop-in for the pure-Python reference.

## 1. Python Interface Spec Review
Coverage, accuracy, and gaps in `specs/python-<component>-interface.md`.
Note every public symbol in the bindings that the spec omits, and every
spec entry that has no live binding.

## 2. PyO3 Binding Source Review
Per-file review of `rust-bindings/src/<component>/` and the relevant pieces of
`rust-bindings/src/lib.rs`. Check exception registration, type conversions,
GIL handling, signature/text_signature alignment, ABI3 compliance.

## 3. Python Wrapper Module Review
Re-exports in `src/openjd/<component>/__init__.py` (and `_v1/__init__.py` for
`model`). Verify spec symbols are reachable through the documented import
paths and that no internal-only names leak.

## 4. Test Review
Coverage of binding-specific surface (Python types, exception classes,
import paths) plus underlying behavior. Organization, happy path vs edge
cases.

## 5. Parity with Pure-Python Reference
**This is the most important section.** Symbol-by-symbol comparison:

| Symbol | Reference | Binding | Status |
|--------|-----------|---------|--------|
| `evaluate_expression` | … | … | ✓ / ⚠ / ❌ |

Behavioral differences, error message comparison, exception hierarchy
divergences, missing or renamed parameters.

## 6. Build and Test Results
maturin output, pytest output, clippy output, stub-gen output diff (if any).

## 7. Exploratory Findings
Bugs found, failing tests written, divergences from reference behavior.

## 8. Recommendations
Prioritized list of improvements. Number them so the
[report-driven workflow in `~/openjd-rs/AGENTS.md`](https://github.com/OpenJobDescription/openjd-rs/blob/main/AGENTS.md#report-driven-development)
can resolve items by striking them through with `~~ ... ~~ **Resolved.**`.
```

## Quick Reference

| Input | Spec | Binding source | Wrapper module | Tests | Reference branch | Report |
|-------|------|----------------|----------------|-------|------------------|--------|
| `expr` | `specs/python-expr-interface.md` | `rust-bindings/src/expr/` | `src/openjd/expr/` | `test/openjd/expr/` | `openjd-model-for-python` (mwiebe fork) `expr` | `reports/expr-bindings-quality-evaluation-report.md` |
| `model` | `specs/python-model-interface.md` | `rust-bindings/src/model/` | `src/openjd/model/_v1/` (and `src/openjd/model/`) | `test/openjd/model_v0/`, `test/openjd/model_v1/` | `openjd-model-for-python` (OpenJobDescription) `mainline` | `reports/model-bindings-quality-evaluation-report.md` |
| `sessions` | `specs/python-sessions-interface.md` | `rust-bindings/src/sessions/` |  `src/sessions/model/_v1/` (and `src/openjd/sessions/`) | `test/openjd/sessions-v0/`, `test/openjd/sessions-v1/`  | `openjd-sessions-for-python` `mainline` | `reports/sessions-bindings-quality-evaluation-report.md` |

### Note on `sessions`

The Python `openjd.sessions` module lives in the separate
`~/openjd-sessions-for-python` repo (its `bindings-rs` branch is the
binding-aware variant; `mainline` is the pure-Python reference).
When evaluating `sessions`, the **wrapper module** and **tests** are
in that other repo, not in `openjd-model-for-python`. Read them there
and write the report file in `openjd-model-for-python/reports/`.

## Validation

Run this validation step at the end of every evaluation:

* Verify the report file exists at the expected path.
* Verify each numbered Recommendation references either a specific file path or a specific failing test, so future commits can resolve it precisely.
* Verify the Parity table in §5 covers every public symbol listed in the Python interface spec — no gaps.
* Re-run the build/test commands from §7 and confirm the reported numbers in §6 match what you see now.
* Re-run the v0-isolation grep commands from §8 and confirm no v1
  module or test imports from v0. If anything slips through,
  the report **MUST** call it out as a high-priority
  recommendation with a v1-internal fix path.
