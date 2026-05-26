# openjd-model Bindings Quality Evaluation Report

**Date:** 2026-05-26
**Component:** `openjd.model._v1`
**Reference branch:** `OpenJobDescription/openjd-model-for-python` `mainline` (also accessible in this repo at `openjd.model` / `openjd.model.v0`)

## Executive Summary

The Rust-backed `openjd.model._v1` is a substantial and largely faithful port
of the v0 (pure-Python, pydantic-based) reference. Decode, `create_job`,
`preprocess_job_parameters`, the iterator and the dependency graph all
produce shape-equivalent outputs, and the test suite passes cleanly
(3 262 collected, 0 failed). The four-artifact split (spec, PyO3 source,
wrapper module, tests) is well-organized — `_v1` is fully isolated from v0
(every grep returns zero matches), the `from_py_object` annotation is
consistent across pyclasses, exception classes are registered through
`register_renamed_exception`, and pickle support is documented and
implemented for the small set of value types it covers.

The findings below are concentrated in three areas: (1) **error-class
parity** — empty-steps validation surfaces under a different exception
class than v0 raised; (2) **enum class identity** —
`JobTemplate.specification_version` returns the Rust pyclass enum, but the
public `v1.TemplateSpecificationVersion` is a Python `str`-Enum shim, so a
natural-looking equality comparison silently returns `False`; (3) **shape
drift in `merge_job_parameter_definitions`** — `default` values are always
emitted as strings and the `description` field is dropped, both deviating
from the spec and the v0 reference. None of these block the binding from
being usable, but each one will surprise a v0 caller who reads the spec
literally.

## 1. Python Interface Spec Review

`specs/python-model-interface.md` is comprehensive (~1300 lines) and
covers the four-submodule split (`template`, `job`, `types`, `errors`),
the 12 typed `Job*ParameterDefinition` variants, the 5 task-parameter
variants, the userInterface pyclasses, profile machinery, pickle
support, and exceptions. The deliberate divergences from v0 are called
out with rationale: no per-revision class hierarchy
(`v2023_09.JobTemplate` etc.); `merge_job_parameter_definitions`
returns `list[dict]` instead of typed pyclasses; `UnsupportedSchema`
constructor takes the message verbatim; validation error wording is
reworded; `JobParameter` drops `description`.

**Spec gaps observed:**

* The `StepDependencyGraph` example shows `graph.topo_sorted() #
  ["Render", "Composite"]`, suggesting strings, but the binding returns a
  list of `Step` objects (only `step_names()` returns strings). This is
  a documentation bug — the binding's behavior is the right one for
  scheduling consumers, but the spec example needs to read
  `[Step(name="Render"), Step(name="Composite")]` (or call
  `step_names()`). See Recommendation #7.
* The `TemplateSpecificationVersion` block mixes the Rust pyclass and
  Python str-Enum. The example
  `template.specification_version    # TemplateSpecificationVersion enum`
  is ambiguous: the binding returns the Rust class, but the public name
  refers to the Python str-Enum — and the two are mutually
  incomparable. See Recommendation #2.
* The merge dict shape lists keys `name`, `type`, `source`, `default`,
  `objectType`, `dataFlow` — but **no `description`**, even though v0's
  typed defs carried a description per parameter. See Recommendations
  #4 and #3 (the latter pins `default` type).
* The spec promises `param.type is JobParameterType.INT` works for
  identity comparison; this is true today (verified empirically — see
  exploratory probe in §7).

Otherwise, every public symbol the bindings register has a
corresponding spec entry, and every spec entry resolves to a real
import path.

## 2. PyO3 Binding Source Review

`rust-bindings/src/model/` is organized into focused submodules
(`decode.rs`, `template.rs`, `template_types.rs`, `job.rs`,
`job_param_defs.rs`, `step_param_space.rs`, `step_param_space_def.rs`,
`step_dependency_graph.rs`, `task_parameter.rs`, `user_interfaces.rs`,
`types.rs`, `profile.rs`, `errors.rs`, `create_job_fns.rs`). Every
pyclass has `from_py_object` (allowing extraction from `&Bound<PyAny>`),
every public-facing type uses `#[pyo3(name = "...")]`, every exception
goes through `register_renamed_exception` in `lib.rs`. ABI3-py39 is
enforced. Doc comments on functions and classes use `///` and feed
into the stub generator.

**Per-file observations:**

* **`errors.rs`** — Exception → Python mapping is complete. The
  Python-only `CompatibilityError` is resolved at error-mapping time
  by importing from `openjd.model._v1` and instantiating; falls back
  to `PyModelValidationError` if import fails. `model_err_to_py`
  routes `ModelError::FormatStringError` to
  `PyFormatStringValidationError` (matching v0's hierarchy) and
  `ModelError::Expression` to `PyExpressionError` (the same class
  `evaluate_expression` raises). The catch-all `_ =>
  PyModelValidationError` is a defensible default but masks
  potentially-meaningful future variants.
* **`decode.rs`** — Four entry points (`*_str` and `*_dict`) with
  consistent kwarg-only signatures. The dict path round-trips through
  `json.dumps` + `serde_json::from_str` (documented in spec). No GIL
  release — decode is fast enough that this is fine.
* **`template.rs` / `template_types.rs`** — All template-time
  pyclasses are present, complete with camelCase aliases and
  `repr`. `JobTemplate.specification_version` parses the
  underlying string to `TemplateSpecificationVersion` and returns
  the Rust pyclass enum (see Recommendation #2 for the parity
  consequence). Job-parameter-definition variants live in their own
  file (`job_param_defs.rs`) and dispatch through
  `job_param_def_to_py`.
* **`job.rs`** — All job-time pyclasses are present. `Step` defines
  `__eq__` and `__hash__` by name only, matching the spec.
  `EmbeddedFile` accepts `endOfLine` / `end_of_line` and validates
  the type / EOL strings. `JobParameter` exposes `(name, type, value)`
  — note that `name` is on the v1 binding but **not** on v0's
  `JobParameter` (v0 inferred name from the dict key). This is a small
  ergonomic improvement; not a parity issue.
* **`step_param_space.rs`** — `StepParameterSpaceIterator` holds an
  `Arc<Mutex<...>>` for thread-safe `Sync` and exposes
  `__iter__`/`__next__`, `__contains__`, `validate_containment`,
  `reset_iter`, and the `chunks_*` getters/setters. `__getitem__` uses
  a fresh iterator to avoid disturbing the persistent cursor. Adaptive
  chunked spaces correctly raise from `__len__`.
* **`step_param_space_def.rs`** — All five typed task-parameter
  definition variants are present and dispatched through
  `step_param_to_py` (verified by reading test coverage).
* **`step_dependency_graph.rs`** — Graph operations dispatch through
  the underlying Rust `StepDependencyGraph`. `topo_sorted()` returns
  `Vec<PyStep>`; `step_names()` returns `Vec<String>`. The
  `max_indegree` / `max_outdegree` getters expose the underlying
  Rust crate's metrics.
* **`task_parameter.rs`** — Pickle reducers are present for every
  variant. `TaskParameterValue` / `JobParameterValue` use
  `DefaultHasher` for `__hash__`, which produces a hash incompatible
  with Python's `hash((type_str, value_str))` used by the
  Python-side `ParameterValue` compat class. See Recommendation #6.
* **`types.rs`** — `JobParameterType` and `TaskParameterType` are
  proper pyo3 enums (`eq, eq_int, frozen, hash, from_py_object`).
  `TemplateSpecificationVersion` is also a pyo3 enum but with
  *different variant names* (`JOBTEMPLATE_2023_09` vs the public
  `JOBTEMPLATE_v2023_09`). See Recommendation #2.
* **`profile.rs`** — `ModelProfile` / `CallerLimits` /
  `ValidationContext` all have hand-rolled `__eq__` (because the
  upstream Rust types don't derive `PartialEq` for the
  `HashSet`-typed extensions field). Pickle support is complete and
  tested.
* **`create_job_fns.rs`** — `py_merge_job_parameter_definitions`
  emits `default` via `to_display_string()`, which forces the value
  to a string regardless of variant. See Recommendation #3.
  `description` is not surfaced on the merged dict at all. See
  Recommendation #4.

**Top-level lib.rs observations:** Every model pyclass and function is
registered. The pickle-helper functions (`_reconstruct_enum`,
`_reconstruct_kwargs`) are registered for the wire-format contract.
GIL release via `Python::allow_threads` is **not** used in any model
path; given that `create_job` and template validation are typically
fast, this is acceptable, but if templates ever grow large enough that
full validation takes >10ms, releasing the GIL during
`decode_job_template` and `create_job` would be valuable. Not flagged
as a recommendation today because no concrete regression has been
measured.

## 3. Python Wrapper Module Review

`src/openjd/model/_v1/__init__.py` (582 lines) is the entry point. It:

* Re-exports the four submodules (`errors`, `job`, `template`,
  `types`) with explicit `from . import` statements.
* Re-exports the entry-point functions (`decode_*`, `create_job`,
  `preprocess_job_parameters`,
  `merge_job_parameter_definitions`, `evaluate_let_bindings`,
  `decode_template`).
* Defines Python-only compatibility classes — `ParameterValue`,
  `RevisionExtensions`, `CancelationMethodTerminate`,
  `CancelationMethodNotifyThenTerminate`, `CompatibilityError`,
  `ValueReferenceConstants`, the str-Enum shims for
  `SpecificationRevision` / `TemplateSpecificationVersion`.
* Implements capability-name validation (`validate_amount_capability_name`,
  `validate_attribute_capability_name`).
* Defines `decode_job_template` / `decode_environment_template` thin
  wrappers that adapt v0's `template=...` kwarg to the binding's
  positional form.

`src/openjd/model/_v1/errors.py`, `_v1/job.py`, `_v1/template.py`,
`_v1/types.py` are simple re-export modules pulling everything from
`openjd._openjd_rs` and aliasing as needed.

**Issues observed:**

* The internal imports (`from typing import Any, Optional, Sequence,
  Union`, `from enum import Enum`, `import re`) in `_v1/__init__.py`
  are not prefixed with `_`. Even though they're absent from
  `__all__`, plain attribute access (`openjd.model._v1.Optional`,
  `openjd.model._v1.re`) still resolves them. v0's
  `_v1/__init__.py` predecessors are pristine on this front; the
  fix is the standard `import re as _re`, `from typing import Any
  as _Any` rewrite. See Recommendation #5.
* Several v0 names that this wrapper module documents as "compat
  shim" are missing — `TokenError` (raised by v0's tokenstream
  parser; in v1 the equivalent surfaces as `ExpressionError` from
  `openjd.expr`), and `parse_model` (v0's internal pydantic-driven
  parser). The first is a real downstream surface change (consumers
  catching `TokenError` will miss the v1 case); the second is
  internal-only and fine to drop. See Recommendation #9 (TokenError)
  and §7 ("Exploratory Findings").

## 4. Test Review

`test/openjd/model_v1/` contains 26 test files plus a benchmark
subtree, mirroring the v0 layout (`test/openjd/model_v0/`):

* `test_create_job.py` (61 KB) — full-coverage create-job tests
  including the rare cases (chunked tasks, host requirements, dependency
  resolution).
* `test_step_param_space_iter.py` (22 KB) — iterator semantics, edge
  cases, adaptive chunking.
* `test_template_types.py`, `test_job_param_defs.py`,
  `test_user_interfaces.py`, `test_step_param_space_def.py` — typed
  pyclass coverage.
* `test_pickle.py`, `test_errors.py`, `test_let_bindings.py`,
  `test_capabilities.py`, `test_merge_job_parameters.py` — focused
  coverage of the cross-cutting paths.
* `test_pyclass_modules.py` — verifies every pyclass's `__module__` is
  the right import path.
* `test_rust_model_bindings.py` — direct round-trips through the
  Rust-side surface.
* `test_fuzz.py` — randomized templates.

**Reference parity:** every v0 test file under `test/openjd/model_v0/`
has at least one analog under `test/openjd/model_v1/`. The v0 suite
runs alongside v1 in the same pytest invocation (3 262 tests total,
all passing). The v1 suite has uniformly high quality — assertions
match on the exception class **and** the message body
(consistent with the AGENTS.md "Test Quality Standard" guidance).

**Coverage gaps observed:**

* No test asserts that `JobTemplate.specification_version` is
  comparable to `TemplateSpecificationVersion.JOBTEMPLATE_v2023_09`
  (the Python str-Enum). v0 had this implicitly because both sides
  were the same Python enum; v1 silently broke it. (See
  `test_known_gaps.py::test_template_specification_version_comparable_to_python_str_enum`.)
* No test pins the exception class for empty-steps validation (v0
  raised `DecodeValidationError`, v1 raises `ModelValidationError`).
  (See
  `test_known_gaps.py::test_empty_steps_raises_decode_validation_error_like_v0`.)
* No test pins the type of `default` in
  `merge_job_parameter_definitions` output. (See the two tests
  `test_merge_default_int_returned_as_int` and
  `test_merge_default_float_returned_as_float`.)
* No test asserts that internal typing imports do not leak as public
  attributes on `openjd.model._v1`. (See
  `test_known_gaps.py::test_no_internal_imports_leak_at_top_level`.)

These gaps are addressed by the seven new failing tests (13 xfail
parametrized cases) added in this evaluation. See §7.

## 5. Parity with Pure-Python Reference

The reference is `openjd.model` / `openjd.model.v0` (the same repo's
v0 surface — accessible via `import openjd.model` since the v1 surface
lives at `openjd.model._v1`). Every public symbol in the reference is
checked below. ✓ = parity, ⚠ = documented divergence, ❌ = unclassified
divergence flagged in §8.

| Symbol | v0 reference | v1 binding | Status |
|--------|--------------|-----------|--------|
| `decode_job_template` | `openjd.model.decode_job_template` | `openjd.model._v1.decode_job_template` | ✓ same kwargs (`template`, `supported_extensions`, `caller_limits`); v1 adds `caller_limits` because Rust crate carries spec-defined limit overrides |
| `decode_environment_template` | same module | same module under `_v1` | ✓ |
| `decode_template` (deprecated) | present | present | ✓ both alias `decode_job_template` |
| `decode_job_template_str` | present | present | ✓ |
| `decode_environment_template_str` | present | present | ✓ |
| `create_job` | `openjd.model.create_job` | `openjd.model._v1.create_job` | ✓ |
| `preprocess_job_parameters` | present | present | ✓ shape-equivalent: returns `dict[str, ParameterValue|JobParameterValue]` |
| `merge_job_parameter_definitions` | returns `list[Job*ParameterDefinition]` | returns `list[dict]` | ⚠ shape change documented; ❌ `default` always str (Rec #3); ❌ `description` dropped (Rec #4) |
| `model_to_object` | present | absent | ⚠ documented as v0-only |
| `parse_model` | present | absent | ❌ undocumented (Rec #9 — covered alongside `TokenError`) |
| `evaluate_let_bindings` | not in v0 (lived inside `_create_job`) | present | ✓ — new public surface for v1 |
| `document_string_to_object` | present | present | ✓ |
| `validate_amount_capability_name` | present | present | ✓ same regex / reserved scopes |
| `validate_attribute_capability_name` | present | present | ✓ |
| `STANDARD_AMOUNT_CAPABILITIES` | top-level | top-level | ✓ |
| `STANDARD_ATTRIBUTE_CAPABILITIES` | top-level | top-level | ✓ |
| `JobTemplate` | `openjd.model.JobTemplate` (from `_types`) | `openjd.model._v1.template.JobTemplate` | ✓ shape parity; `.specification_version` returns Rust enum (❌ Rec #2) |
| `EnvironmentTemplate` | top-level | `_v1.template.EnvironmentTemplate` | ✓ |
| `Job` | top-level | `_v1.job.Job` | ✓ |
| `Step` | top-level | `_v1.job.Step` | ✓ |
| `StepParameterSpace` | top-level | `_v1.job.StepParameterSpace` | ✓ |
| `StepParameterSpaceIterator` | top-level | `_v1.job.StepParameterSpaceIterator` | ✓ |
| `StepDependencyGraph` | top-level | `_v1.job.StepDependencyGraph` | ✓; spec example mismatches reality (Rec #7) |
| `StepDependencyGraphNode` | top-level | aliased on `_v1` to `_v1.job.StepDependencyNode` | ✓ |
| `StepDependencyGraphStepToStepEdge` | top-level | aliased on `_v1` to `_v1.job.StepDependencyEdge` | ✓ |
| `JobParameter` | `v2023_09.JobParameter` (`type`, `value`, `description`) | `_v1.job.JobParameter` (`name`, `type`, `value`) | ⚠ documented: no `description` (read off the definition); v1 adds `name` |
| `JobParameterType` | str-Enum | pyo3 eq_int enum | ⚠ documented in spec |
| `TaskParameterType` | str-Enum (via v2023_09) | pyo3 eq_int enum | ⚠ documented |
| `ParameterValue` | top-level (kwargs `type`, `value`) | top-level (kwargs `type`, `value`) | ✓ |
| `ParameterValueType` | top-level | aliased to `JobParameterType` on `_v1` | ✓ |
| `TaskParameterValue` | (no public class — used `ParameterValue`) | top-level (`_v1.types.TaskParameterValue`) | ✓ new typed class; `__eq__` agrees with `ParameterValue` but `__hash__` doesn't (❌ Rec #6) |
| `JobParameterValue` | n/a | new | same hash issue as `TaskParameterValue` |
| `RevisionExtensions` | top-level | top-level | ✓ |
| `SpecificationRevision` (Python str-Enum) | top-level | top-level | ✓ |
| `TemplateSpecificationVersion` (Python str-Enum) | top-level | top-level | ✓ — but `JobTemplate.specification_version` returns the **Rust** enum, not this Python class (❌ Rec #2) |
| `ModelProfile` | n/a (v0 used `RevisionExtensions`) | new | ✓ |
| `CallerLimits` | n/a | new | ✓ |
| `ValidationContext` | n/a | new | ✓ |
| `ModelExtension` | n/a (v0 used strings) | new pyo3 enum | ✓ |
| `DocumentType` | top-level (Python `enum.Enum`) | top-level (pyo3 enum) | ✓ same variant names |
| `DecodeValidationError` | top-level | top-level | ✓ class identity preserved; ❌ different class fires for empty-steps (Rec #1) |
| `ModelValidationError` | top-level | top-level | ✓ same hierarchy |
| `UnsupportedSchema` | top-level | top-level | ⚠ constructor takes message verbatim, no `_version` attr (documented) |
| `CompatibilityError` | top-level | top-level | ✓ ValueError subclass parity |
| `ExpressionError` | top-level (re-exported from `_errors`) | re-exported from `openjd.expr` | ✓ same class identity expected (the `openjd.expr` class) |
| `FormatStringError` | top-level | re-exported from `openjd.expr` | ✓ |
| `TokenError` | top-level (subclass of `ExpressionError`) | absent | ❌ undocumented (Rec #9) |
| `IntRangeExpr` | top-level | absent (use `openjd.expr.RangeExpr`) | ⚠ documented (the spec has a "Behavior change" section about `RangeExpr` iteration) |
| `SymbolTable` | top-level (Python class) | re-exported from `openjd.expr` | ✓ |
| `FormatString` | top-level | re-exported from `openjd.expr` | ✓ |
| `RangeExpr` | (v0 has `IntRangeExpr` not `RangeExpr`) | re-exported from `openjd.expr` | ✓ |
| `ValueReferenceConstants` | top-level | top-level | ✓ same members |
| `CommandString`, `ArgString` | top-level (subclasses of `FormatString`) | aliases to `FormatString` | ✓ |
| `EmbeddedFileText`, `EmbeddedFiles` | top-level | aliases | ✓ |
| `JobParameterValues`, `JobParameterInputValues`, `TaskParameterSet` | top-level | top-level | ✓ |

**Behavioral differences pinned:**

* **Empty steps** — v0 `DecodeValidationError` ↔ v1
  `ModelValidationError`. Both inherit `ValueError`, but neither
  inherits the other. Cross-test the inheritance: `except
  DecodeValidationError` no longer catches the case under v1.
* **`JobTemplate.specification_version` enum class identity** — v0
  returned the Python str-Enum (so `==` comparison worked); v1
  returns the Rust pyo3 enum (so `==` always returns `False`).
* **`merge_job_parameter_definitions` `default` type** — v0 returned
  the typed value (`int` for INT, `float` for FLOAT, etc.) on the
  typed pyclass; v1 returns it as `str` for every variant.
* **`merge_job_parameter_definitions` `description` field** — v0
  carried it on the typed pyclass; v1 drops it.
* **`TaskParameterValue` / `ParameterValue` hash** — equality is
  cross-class but `hash()` domains differ, so `tp == pv but hash(tp)
  != hash(pv)`. Breaks set/dict membership.
* **Top-level package leaks** — `openjd.model._v1.{Any, Optional,
  Sequence, Union, Enum, re}` resolve as public attributes.
* **`StepDependencyGraph.topo_sorted()`** — spec shows strings,
  binding returns `Step` objects. Spec is the docs bug; the binding
  is correct.
* **`TokenError`, `parse_model`** — exposed on v0, absent on v1. The
  former is a downstream-visible surface change; the latter was
  internal.

## 6. Build and Test Results

All commands run from `/home/markw/openjd-model-for-python` with
`VIRTUAL_ENV` pointing to the hatch-managed venv at
`/home/markw/.local/share/hatch/env/virtual/openjd-model/h_Y-O7uL/openjd-model`.

```
$ python scripts/maturin_build.py develop --manifest-path rust-bindings/Cargo.toml
🍹 Building a mixed python/rust project
🐍 Found CPython 3.13 at .../openjd-model/bin/python
🔗 Found pyo3 bindings with abi3 support
📡 Using build options features from pyproject.toml
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 1.04s
📦 Built wheel for abi3 Python ≥ 3.9
✏️ Setting installed package as editable
🛠 Installed openjd-model-0.9.1.post10+gb9bea0e3d.d20260526
```

Build succeeded; cdylib `_openjd_rs.abi3.so` rebuilt and reinstalled.

```
$ python -m pytest test/openjd/model_v0 test/openjd/model_v1 -p no:cacheprovider --no-cov -q
================ 3262 passed in 9.78s ================
```

All 3 262 tests pass (v0 + v1 combined). The five slowest tests are all
benchmark cases (≤4.5s each).

After the seven new failing tests in `test_known_gaps.py` were added:

```
$ python -m pytest test/openjd/model_v1/test_known_gaps.py -v --no-cov
============================= 13 xfailed in 1.27s =============================
```

Every gap test is `xfail(strict=True)`, so each will start xpassing the
moment the corresponding fix lands.

```
$ cargo clippy --manifest-path rust-bindings/Cargo.toml --all-targets -- -D warnings
   Compiling pyo3-build-config v0.28.3
   Compiling pyo3-ffi v0.28.3
   Compiling pyo3-macros-backend v0.28.3
   Compiling pyo3 v0.28.3
   Compiling pyo3-macros v0.28.3
    Checking pyo3-log v0.13.3
    Checking openjd-python v0.9.0 (/home/markw/openjd-model-for-python/rust-bindings)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 8.45s
```

Clippy is clean: no warnings.

Stub generation (`scripts/generate_stubs.sh`) was not re-run during this
evaluation since no public-binding signatures changed.

## 7. Exploratory Findings

In addition to the v0/v1 surface diff in §5, the following were
exercised manually:

* **Pickle of decoded models** — `JobTemplate`, `Job`, `Step` all raise
  `TypeError: cannot pickle ...` (matching the spec, which documents
  these as not-pickleable).
* **`Step.__eq__` by name** — confirmed: two `Step` objects from
  different jobs but with the same name compare equal and hash
  identically. Matches the spec.
* **`StepParameterSpaceIterator` semantics** — `len()`, indexing
  (`it[0]`, `it[-1]`, `it[len]→IndexError`), iteration, `reset_iter`,
  `__contains__`, and `validate_containment` all behave as documented.
* **`pyo3` enum identity** — `param.type is JobParameterType.INT`
  works (this initially looked like it might fail on each-access copy
  semantics; it does not). The spec's `is`-comparison guidance is
  correct.
* **`ParameterValue` ↔ `TaskParameterValue` equality** — symmetric
  equality holds, but the two classes use different `__hash__`
  implementations. This is the one Python data-model contract
  violation surfaced by the evaluation.
* **`v0.UnsupportedSchema('x')` vs `v1.UnsupportedSchema('x')`** — the
  spec documents the divergence; downstream tests in `test_errors.py`
  have already been adapted (`UnsupportedSchema("Unsupported schema
  version: version")` to make the messages line up).
* **Cross-class type identity for `TemplateSpecificationVersion`** —
  the Rust pyclass enum (`openjd._openjd_rs.TemplateSpecificationVersion`)
  and the Python str-Enum shim (`openjd.model._v1.TemplateSpecificationVersion`)
  are different classes with different variant names and never compare
  equal. Pinned in
  `test_known_gaps.py::test_template_specification_version_comparable_to_python_str_enum`.
* **`merge_job_parameter_definitions` shape audit** — `default` values
  are always strings, regardless of variant; `description` is missing
  entirely. Pinned in three test cases.
* **Empty-steps decode error class** — `ModelValidationError` rather
  than `DecodeValidationError`. Pinned in
  `test_known_gaps.py::test_empty_steps_raises_decode_validation_error_like_v0`.
* **Top-level `openjd.model._v1` namespace pollution** — `Any`,
  `Optional`, `Sequence`, `Union`, `Enum`, `re` all accessible.
  Pinned via parameterized test (six cases).

## 8. Recommendations

The list below is ordered by surface impact (each items breaks an
established v0 idiom or a spec-promised behavior). Numbers are stable
so future fix commits can resolve them with the
`~~ ... ~~ **Resolved.**` strikethrough convention.

1. **Empty-steps validation should raise `DecodeValidationError`, not
   `ModelValidationError`** — for v0 parity. Either remap the
   empty-steps case in
   `rust-bindings/src/model/errors.rs::model_err_to_py` (or in the
   upstream Rust validator) so it surfaces under
   `PyDecodeValidationError`, or update the spec to call out the
   exception-class change explicitly. Pinned in
   `test/openjd/model_v1/test_known_gaps.py::test_empty_steps_raises_decode_validation_error_like_v0`.

2. **`JobTemplate.specification_version` should return a value
   comparable to `v1.TemplateSpecificationVersion`** — today it
   returns the Rust pyo3 enum
   (`openjd._openjd_rs.TemplateSpecificationVersion`, variants
   `JOBTEMPLATE_2023_09` / `ENVIRONMENT_2023_09`), but
   `v1.TemplateSpecificationVersion` is a Python str-Enum (variants
   `JOBTEMPLATE_v2023_09` / `ENVIRONMENT_v2023_09`). The two are
   incomparable. Two viable fixes: (a) have
   `rust-bindings/src/model/template.rs::specification_version` return
   the Python str-Enum value (look up via attribute access on the
   shim); (b) drop the Python str-Enum shim and re-export the Rust
   pyclass under `v1.TemplateSpecificationVersion` (requires renaming
   variants for v0 parity — `JOBTEMPLATE_v2023_09` style). Pinned in
   `test/openjd/model_v1/test_known_gaps.py::test_template_specification_version_comparable_to_python_str_enum`.

3. **`merge_job_parameter_definitions` should emit `default` as the
   parameter's native Python type, not as a string** — `int` for
   `INT`, `float` for `FLOAT`, `bool` for `BOOL`, `list[T]` for the
   `LIST[*]` variants, and `str` for `STRING` / `PATH` /
   `RANGE_EXPR`. The fix lives in
   `rust-bindings/src/model/create_job_fns.rs::py_merge_job_parameter_definitions`
   — replace the `default.to_display_string()` call with a per-
   `param_type` dispatch that converts the underlying typed value into
   the right Python type. Pinned in
   `test/openjd/model_v1/test_known_gaps.py::test_merge_default_int_returned_as_int`
   and `test_merge_default_float_returned_as_float`.

4. **`merge_job_parameter_definitions` should include the `description`
   field on each merged dict** — v0's typed defs carried it, and the
   upstream `openjd_model::merge_job_parameter_definitions` produces
   it on each input definition. The fix at the binding layer is to
   read `description` off the originating
   `JobParameterDefinition` (looked up by `name`) on either the job
   template or the relevant environment template, and add it to the
   merged dict when present. Update the spec's "Return shape" key
   list to include `description`. Pinned in
   `test/openjd/model_v1/test_known_gaps.py::test_merge_includes_description`.

5. **Internal typing imports in `openjd.model._v1.__init__.py` should
   be prefixed with `_`** — `from typing import Any, Optional,
   Sequence, Union` → `from typing import Any as _Any, Optional as
   _Optional, ...`. Same for `from enum import Enum as _Enum` and
   `import re as _re`. Today these names leak as public attributes on
   `openjd.model._v1`. Pinned via parameterized test in
   `test/openjd/model_v1/test_known_gaps.py::test_no_internal_imports_leak_at_top_level`.

6. **`TaskParameterValue.__hash__` and `JobParameterValue.__hash__`
   must agree with `ParameterValue.__hash__`** — today
   `TaskParameterValue == ParameterValue` is True (good) but
   `hash(TaskParameterValue) != hash(ParameterValue)` (bad), violating
   Python's data-model contract. The Rust-side `__hash__`
   implementation in `rust-bindings/src/model/types.rs` uses
   `std::collections::hash_map::DefaultHasher`, which is unrelated to
   Python's hash. The fix is to match what the Python compat class
   does: `hash((self.type.as_str(), self.value))` — easiest done by
   delegating to Python via `Python::attach |py| { py.eval("hash((...,
   ...))") }`, or by reimplementing the Python tuple-hash algorithm
   in Rust. Pinned in
   `test/openjd/model_v1/test_known_gaps.py::test_task_parameter_value_and_parameter_value_hash_compatibility`.

7. **`StepDependencyGraph.topo_sorted()` spec example should show
   `Step` objects, not strings** — the spec's example (`# ["Render",
   "Composite"] — dependency order`) implies strings, but the binding
   returns `list[Step]`. The binding is the right behavior — worker
   agent and openjd-cli rely on `Step` objects for scheduling. Update
   the example in `specs/python-model-interface.md` →
   "StepDependencyGraph" subsection to read `[Step(name="Render"),
   Step(name="Composite")]`, and explicitly call out
   `step_names()` for the string list. Pinned in
   `test/openjd/model_v1/test_known_gaps.py::test_topo_sorted_returns_strings_per_spec_example`.

8. **Add docstrings to the binding's main pyclasses** — `JobTemplate`,
   `EnvironmentTemplate`, `Job`, `Step`, `JobParameter`,
   `TemplateSpecificationVersion`, `JobParameterType`,
   `TaskParameterType`, `DocumentType`. Today these have no
   `__doc__`. PyO3 propagates `///` doc comments to the generated
   `_openjd_rs.pyi`, so any addition shows up in IDE tooltips and
   help. Mirror what `ModelProfile` and `CallerLimits` already do
   (they have detailed `///` doc comments at the `#[pyclass]` level).

9. **Restore `TokenError` (or document its removal) and remove the
   `parse_model` reference from any downstream consumer documentation**
   — v0 exposed `TokenError` as a `ValueError → ExpressionError`
   subclass; the spec doesn't list it, and the binding doesn't
   register it. Downstream callers that did `except TokenError` for
   tokenstream errors silently catch nothing under v1. Two options:
   (a) port `TokenError` to v1 by re-exposing it from `openjd.expr`
   (or from `openjd.model._v1.errors`) and have the parser raise it
   for tokenization-stage failures; (b) update
   `specs/python-model-interface.md` to call out the removal and
   recommend `except ExpressionError` instead. `parse_model` was a
   v0-internal helper and is fine to drop, but the spec should
   mention its absence so downstream consumers don't search for it.
