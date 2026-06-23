# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""
In-tree PEP 517 build backend that wraps `maturin` to inject a
VCS-derived version.

Why this exists: maturin reads the wheel version from
`[project].version` in pyproject.toml (or `[package].version` in
Cargo.toml when `dynamic = ["version"]` is set). It has no built-in
mechanism to derive the version from git, the way hatchling+hatch-vcs
does. This wrapper:

  1. Computes the same VCS version as `scripts/generate_version.py`
     (via setuptools_scm with the same config as `[tool.hatch.version]`).
  2. Writes `src/openjd/model/_version.py` so the in-Python
     `__version__` matches the wheel.
  3. Patches pyproject.toml in place — replaces `dynamic = ["version"]`
     with a static `version = "<v>"`.
  4. Delegates to maturin's PEP 517 hooks.
  5. Restores pyproject.toml in `finally`.

Wired in via:
    [build-system]
    requires = ["maturin>=1.0,<2.0", "setuptools_scm"]
    build-backend = "_build_backend"
    backend-path = ["."]

The companion script `scripts/maturin_build.py` does the same patching
around `maturin develop` / `maturin build` for users who prefer those
direct commands. Either path produces wheels with the VCS version.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import sys
from pathlib import Path

# Windows MSVC linker fails with LNK1104 when paths exceed MAX_PATH (260 chars).
# Building from an extracted sdist produces deeply nested target directories.
# Redirect Cargo's output to a short path to avoid this.
if sys.platform == "win32" and "CARGO_TARGET_DIR" not in os.environ:
    os.environ["CARGO_TARGET_DIR"] = "C:\\cargo-target"

import maturin

REPO_ROOT = Path(__file__).resolve().parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
PYPROJECT_BAK = REPO_ROOT / "pyproject.toml.vcs-bak"
DYNAMIC_NEEDLE = 'dynamic = ["version"]'

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from generate_version import compute_version, write_version_file  # noqa: E402


def _recover_orphan_bak() -> None:
    """If a previous build died before restoring pyproject.toml, recover."""
    if PYPROJECT_BAK.exists():
        sys.stderr.write(
            f"WARN: {PYPROJECT_BAK.name} found from a prior interrupted build; restoring.\n"
        )
        shutil.move(str(PYPROJECT_BAK), str(PYPROJECT))


@contextlib.contextmanager
def _patched_pyproject():
    """
    Patch [project] to have a static VCS version. Restore on exit.

    If the version cannot be computed (e.g. building from an sdist with
    no .git directory), yield without patching — maturin will fall back
    to the static [package].version in Cargo.toml, same as today.
    """
    _recover_orphan_bak()

    try:
        version = compute_version()
    except SystemExit:
        sys.stderr.write(
            "WARN: setuptools_scm could not derive a version (no git? no setuptools_scm?). "
            "Falling back to static version from Cargo.toml.\n"
        )
        yield None
        return

    write_version_file(version)
    original = PYPROJECT.read_text(encoding="utf-8")
    if DYNAMIC_NEEDLE not in original:
        sys.stderr.write(
            f"WARN: expected {DYNAMIC_NEEDLE!r} in pyproject.toml but did not find it; "
            "skipping version patch.\n"
        )
        yield version
        return

    shutil.copy2(PYPROJECT, PYPROJECT_BAK)
    try:
        patched = original.replace(DYNAMIC_NEEDLE, f'version = "{version}"', 1)
        PYPROJECT.write_text(patched, encoding="utf-8")
        yield version
    finally:
        shutil.move(str(PYPROJECT_BAK), str(PYPROJECT))


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    with _patched_pyproject():
        return maturin.build_wheel(wheel_directory, config_settings, metadata_directory)


def build_editable(wheel_directory, config_settings=None, metadata_directory=None):
    with _patched_pyproject():
        return maturin.build_editable(wheel_directory, config_settings, metadata_directory)


def build_sdist(sdist_directory, config_settings=None):
    with _patched_pyproject():
        return maturin.build_sdist(sdist_directory, config_settings)


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):
    with _patched_pyproject():
        return maturin.prepare_metadata_for_build_wheel(metadata_directory, config_settings)


prepare_metadata_for_build_editable = prepare_metadata_for_build_wheel

# Pass-through hooks: no version patching needed for requirement queries.
get_requires_for_build_wheel = maturin.get_requires_for_build_wheel
get_requires_for_build_editable = maturin.get_requires_for_build_editable
get_requires_for_build_sdist = maturin.get_requires_for_build_sdist
