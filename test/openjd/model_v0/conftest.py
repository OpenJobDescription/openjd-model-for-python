# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""conftest for openjd.model v0 tests.

Lets you choose how the v0 test suite's ``openjd.model[.X]`` imports resolve,
via the ``OPENJD_MODEL_V0_TEST_IMPORT`` environment variable:

    root  (default) – Imports resolve normally to ``openjd.model[.X]``.

    v0              – Re-route every ``from openjd.model[.X] import Y`` to
                      resolve via ``openjd.model.v0[.X]`` instead. Specifically:
                      for each submodule X in v0's mirror set, this conftest
                      points ``sys.modules['openjd.model.X']`` at
                      ``sys.modules['openjd.model.v0.X']`` and rebinds the
                      attribute on the parent package to match. The parent
                      ``openjd.model`` module object itself is kept (so its
                      identity stays stable) but its public attributes are
                      overwritten with the values from ``openjd.model.v0``.

While ``openjd.model.v0`` remains a thin alias for ``openjd.model``, both
modes resolve to the same module objects. The variable is wired up now so
that when v0 grows its own implementation (or when ``openjd.model`` flips to
re-export from v1), this is the single switch that makes the v0 test suite
exercise the v0 implementation instead of the root.
"""

import importlib
import os
import sys


_VAR = "OPENJD_MODEL_V0_TEST_IMPORT"
_DEFAULT = "root"
_CHOICES = ("root", "v0")


# Submodules of openjd.model that are mirrored under openjd.model.v0.
# Kept in sync with src/openjd/model/v0/__init__.py.
_TOP_LEVEL_SUBMODULES = (
    "v2023_09",
    "_capabilities",
    "_convert_pydantic_error",
    "_create_job",
    "_errors",
    "_format_strings",
    "_internal",
    "_merge_job_parameter",
    "_parse",
    "_range_expr",
    "_step_dependency_graph",
    "_step_param_space_iter",
    "_symbol_table",
    "_tokenstream",
    "_types",
    "_version",
)
_FORMAT_STRINGS_SUBMODULES = (
    "_dyn_constrained_str",
    "_edit_distance",
    "_expression",
    "_format_string",
    "_nodes",
    "_parser",
    "_tokens",
)
_INTERNAL_SUBMODULES = (
    "_combination_expr",
    "_create_job",
    "_param_space_dim_validation",
    "_validator_functions",
    "_variable_reference_validation",
)
_V2023_09_SUBMODULES = ("_model",)


def _import_mode() -> str:
    mode = os.environ.get(_VAR, _DEFAULT).lower()
    if mode not in _CHOICES:
        raise ValueError(f"{_VAR}={mode!r} is not one of {_CHOICES}. Set {_VAR}=root or {_VAR}=v0.")
    return mode


def _redirect_one(root_dotted: str, v0_dotted: str) -> None:
    """Make ``sys.modules[root_dotted]`` resolve to whatever module
    ``v0_dotted`` points at, and bind the attribute on the parent package."""
    src = importlib.import_module(v0_dotted)
    sys.modules[root_dotted] = src
    parent_name, _, leaf = root_dotted.rpartition(".")
    if parent_name and parent_name in sys.modules:
        setattr(sys.modules[parent_name], leaf, src)


def _redirect_root_to_v0() -> None:
    """Route ``openjd.model[.X]`` imports through ``openjd.model.v0[.X]``."""

    # Make sure both packages are loaded before we touch sys.modules.
    importlib.import_module("openjd.model")
    importlib.import_module("openjd.model.v0")

    # Overwrite public attributes on the ``openjd.model`` module object so
    # ``from openjd.model import X`` returns v0's X. Keeps the
    # ``openjd.model`` module identity stable (so anything that already
    # holds a reference to it is unaffected), while changing what its
    # public names point at.
    root = sys.modules["openjd.model"]
    v0 = sys.modules["openjd.model.v0"]
    for name in getattr(v0, "__all__", ()):
        if hasattr(v0, name):
            setattr(root, name, getattr(v0, name))

    # Redirect each mirrored submodule.
    for name in _TOP_LEVEL_SUBMODULES:
        _redirect_one(f"openjd.model.{name}", f"openjd.model.v0.{name}")
    for name in _FORMAT_STRINGS_SUBMODULES:
        _redirect_one(
            f"openjd.model._format_strings.{name}",
            f"openjd.model.v0._format_strings.{name}",
        )
    for name in _INTERNAL_SUBMODULES:
        _redirect_one(
            f"openjd.model._internal.{name}",
            f"openjd.model.v0._internal.{name}",
        )
    for name in _V2023_09_SUBMODULES:
        _redirect_one(
            f"openjd.model.v2023_09.{name}",
            f"openjd.model.v0.v2023_09.{name}",
        )


# Run at conftest import time, before any test module is collected.
_mode = _import_mode()
if _mode == "v0":
    _redirect_root_to_v0()
# else: default 'root' — no remapping; tests import from openjd.model directly.
