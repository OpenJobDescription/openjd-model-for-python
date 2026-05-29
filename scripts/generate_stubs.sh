#!/bin/bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# Regenerate the _openjd_rs.pyi type stub from Rust source.
# Requires: pyo3-stub-gen annotations on all #[pyclass]/#[pyfunction]/#[pymethods]
#
# Note: pyo3-stub-gen 0.21 has a bug with abi3-py39 (references PyEncodingWarning
# which is behind #[cfg(Py_3_10)]). We use a patched local copy at /tmp/pyo3-stub-gen.
# If not present, the script will clone and patch it automatically.
set -e

cd "$(dirname "$0")/.."

# Ensure patched pyo3-stub-gen exists
if [ ! -d /tmp/pyo3-stub-gen ]; then
    git clone --depth 1 https://github.com/Jij-Inc/pyo3-stub-gen.git /tmp/pyo3-stub-gen
    sed -i 's/^impl_exception_stub_type!(PyEncodingWarning, "EncodingWarning");/#[cfg(Py_3_10)]\nimpl_exception_stub_type!(PyEncodingWarning, "EncodingWarning");/' \
        /tmp/pyo3-stub-gen/pyo3-stub-gen/src/exception.rs
fi

PYTHON_LIB=$(python3 -c "import sysconfig; print(sysconfig.get_config_var('LIBDIR'))")

# Build the stub_gen binary (without extension-module so it can link against libpython)
LIBRARY_PATH="$PYTHON_LIB" cargo build --manifest-path rust-bindings/Cargo.toml --features stub-gen --bin stub_gen

# Create a temporary pyproject.toml symlink for pyo3-stub-gen
ln -sf ../pyproject.toml rust-bindings/pyproject.toml

# Run the generator
CARGO_MANIFEST_DIR=rust-bindings LD_LIBRARY_PATH="$PYTHON_LIB" ./target/debug/stub_gen

# Move to correct location
mv rust-bindings/src/openjd/_openjd_rs/__init__.pyi src/openjd/_openjd_rs.pyi
rm -rf rust-bindings/src/openjd
rm rust-bindings/pyproject.toml

# Post-process: fix Rust raw identifiers and remove internal types
sed -i 's/r#type/type/g' src/openjd/_openjd_rs.pyi
# Also strip Rust raw-identifier prefix on `r#let` (used to take a `let`
# kwarg in EnvironmentScript / StepScript constructors). Unlike
# `r#type`, pyo3-stub-gen does not strip this one automatically.
sed -i 's/r#let/let/g' src/openjd/_openjd_rs.pyi
sed -i '/"PyExprValueIter"/d; /"PyRangeExprIter"/d; /"PyStepParamSpaceIter"/d' src/openjd/_openjd_rs.pyi

# Tighten `__next__` return types: pyo3-stub-gen reflects the Rust
# `Option<T>` signature (where `None` triggers StopIteration in
# PyO3's glue), but at the Python level `__next__` should be typed
# as returning `T` directly.
sed -i 's|def __next__(self) -> typing\.Optional\[dict\]: \.\.\.|def __next__(self) -> dict: ...|' src/openjd/_openjd_rs.pyi

# Fill in iterator-protocol methods on the internal `Py*Iter` classes.
# pyo3-stub-gen emits them as empty marker classes (`class Foo: ...`),
# but they're returned from `__iter__` accessors elsewhere in the
# stub, so mypy needs `__next__` to type-check `for x in obj` and
# `list(obj)` patterns at call sites.
python3 - <<'PYI_FIXUP'
import re
from pathlib import Path

p = Path("src/openjd/_openjd_rs.pyi")
text = p.read_text()

iter_classes = {
    "PyExprValueIter": "ExprValue",
    "PyRangeExprIter": "builtins.int",
}
for cls, item in iter_classes.items():
    body = (
        f"@typing.final\n"
        f"class {cls}:\n"
        f'    def __iter__(self) -> "{cls}": ...\n'
        f"    def __next__(self) -> {item}: ..."
    )
    # Match both the pyo3-stub-gen single-line form
    # `class Foo: ...` and the black-expanded multi-line form
    # `class Foo:\n    ...`. Use \s+ between `:` and `...` to
    # cover both.
    pattern = rf"@typing\.final\nclass {cls}:\s*\.\.\."
    new_text, n = re.subn(pattern, body, text, count=1)
    if n != 1:
        raise SystemExit(f"PYI_FIXUP: failed to match {cls} marker class")
    text = new_text

p.write_text(text)
PYI_FIXUP

# Suppress F821 false positives. pyo3-stub-gen emits forward references
# in default-value expressions (e.g. `revision: SpecificationRevision =
# SpecificationRevision.V2023_09`) which ruff flags as undefined names
# even though they resolve at runtime. Add F821 to the existing noqa
# comment so the generated stub passes lint cleanly.
sed -i 's|^# ruff: noqa: E501, F401, F403, F405$|# ruff: noqa: E501, F401, F403, F405, F821|' src/openjd/_openjd_rs.pyi

# Append manually-tracked declarations for symbols that pyo3-stub-gen
# does not see. These are runtime-registered in `lib.rs` via
# `register_renamed_exception` (the four `openjd.expr` exception
# classes plus the three `openjd.model._v1.errors` exception classes)
# and via `m.add(...)` for the two integer constants. They are part
# of the public binding surface but live behind macros that the stub
# generator does not crawl, so without this block mypy reports
# "Module 'openjd._openjd_rs' has no attribute 'ExpressionError'"
# (and so on) at every import site in the wrapper modules.
cat >> src/openjd/_openjd_rs.pyi <<'PYI'

# ── Manually-tracked declarations ───────────────────────────────────
# Items below are not emitted by pyo3-stub-gen. They live behind
# `register_renamed_exception` / `m.add(...)` calls in `lib.rs` rather
# than `#[pyclass]` / `#[pyfunction]` macros. Keep this block in sync
# with the `mod_init` body whenever new exceptions or constants are
# added.

# openjd.expr exception classes (registered as ValueError subclasses).
class ExpressionError(builtins.ValueError):
    expr: typing.Optional[builtins.str]
    node: typing.Optional[typing.Any]
    lineno: typing.Optional[builtins.int]
    col_offset: typing.Optional[builtins.int]
    def __init__(
        self,
        *args: typing.Any,
        expr: typing.Optional[builtins.str] = None,
        node: typing.Optional[typing.Any] = None,
        lineno: typing.Optional[builtins.int] = None,
        col_offset: typing.Optional[builtins.int] = None,
    ) -> None: ...
    def with_context(
        self,
        expr: builtins.str,
        node: typing.Optional[typing.Any] = None,
    ) -> "ExpressionError": ...
    def message_with_expr_prefix(self, prefix: builtins.str) -> builtins.str: ...
class ExpressionTypeError(ExpressionError): ...
class RangeExprError(builtins.ValueError): ...
class FormatStringValidationError(builtins.ValueError): ...

# openjd.model._v1.errors exception classes (registered as ValueError
# subclasses).
class DecodeValidationError(builtins.ValueError): ...
class ModelValidationError(builtins.ValueError): ...
class UnsupportedSchema(builtins.ValueError): ...

# Integer constants from the openjd-expr crate, exposed at module
# level for callers that want to inspect or override the limits.
DEFAULT_MEMORY_LIMIT: builtins.int
DEFAULT_OPERATION_LIMIT: builtins.int
PYI

# Run black on the final .pyi so the file matches the project's
# formatting conventions and `hatch run lint` doesn't flag it on
# the next CI run.
python3 -m black -q src/openjd/_openjd_rs.pyi || true

echo "Generated src/openjd/_openjd_rs.pyi"
