#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""
Build the openjd-model wheel/extension via maturin with a VCS-derived
version string.

maturin reads the wheel version from `[project].version` in
pyproject.toml, or — when `[project].dynamic` lists "version" — from
`[package].version` in Cargo.toml. Neither source supports
hatch-vcs / setuptools_scm out of the box.

This wrapper:
  1. Computes the same `0.9.0.post<N>+g<hash>` version that
     `generate_version.py` writes to `_version.py`.
  2. Writes `_version.py` so the in-Python `__version__` matches.
  3. Patches pyproject.toml in place — replaces
     `dynamic = ["version"]` with a static `version = "<v>"`.
  4. Runs `maturin <args>` (defaults to `develop`).
  5. Restores pyproject.toml in `finally`, so the working tree is
     clean whether the build succeeds, fails, or is interrupted.

A backup is written to `pyproject.toml.vcs-bak` and removed on success.
If a previous run died before restoring, that file is detected and
restored before this run starts.

Usage:
    python scripts/maturin_build.py develop --release --manifest-path rust-bindings/Cargo.toml
    python scripts/maturin_build.py build --release
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
PYPROJECT_BAK = REPO_ROOT / "pyproject.toml.vcs-bak"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from generate_version import compute_version, write_version_file  # noqa: E402


def _patch_pyproject(version: str) -> str:
    """Replace `dynamic = ["version"]` with a static version. Returns original text."""
    original = PYPROJECT.read_text(encoding="utf-8")

    needle = 'dynamic = ["version"]'
    if needle not in original:
        sys.stderr.write(
            f"ERROR: expected to find {needle!r} in pyproject.toml — did the file change?\n"
        )
        sys.exit(1)

    patched = original.replace(needle, f'version = "{version}"', 1)
    PYPROJECT.write_text(patched, encoding="utf-8")
    return original


def main(argv: list[str]) -> int:
    if PYPROJECT_BAK.exists():
        # Previous run died before restoring — recover.
        sys.stderr.write(
            f"WARN: {PYPROJECT_BAK.name} found from a prior interrupted run; restoring.\n"
        )
        shutil.move(str(PYPROJECT_BAK), str(PYPROJECT))

    maturin_args = argv or ["develop"]

    version = compute_version()
    if write_version_file(version):
        print(f"Wrote src/openjd/model/_version.py (version {version})")

    shutil.copy2(PYPROJECT, PYPROJECT_BAK)
    try:
        _patch_pyproject(version)
        print(f"Patched pyproject.toml: project.version = {version!r}")
        rc = subprocess.call(["maturin", *maturin_args], cwd=str(REPO_ROOT))
    finally:
        shutil.move(str(PYPROJECT_BAK), str(PYPROJECT))
        print("Restored pyproject.toml")

    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
