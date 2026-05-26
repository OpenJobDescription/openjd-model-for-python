# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""openjd.model.v0 — alias for openjd.model.

Today, ``openjd.model`` is the v0 implementation. This subpackage exposes the
exact same public surface (and the same underscore-prefixed submodules used by
internal tests) so that consumers can pin to v0 explicitly:

    from openjd.model.v0 import create_job, JobTemplate
    from openjd.model.v0.v2023_09 import StepTemplate
    from openjd.model.v0._parse import _parse_model  # internal

In the future the relationship will flip — ``openjd.model`` will re-export from
v1 while v0 will retain its current behaviour. Code that imports via
``openjd.model.v0`` will continue to work without change.

This module is implemented purely via ``sys.modules`` aliases so there is no
duplication of symbols, no second copy of any class, and
``openjd.model.v0.X is openjd.model.X`` for every alias X.
"""

import importlib as _importlib
import sys as _sys

# Re-export the public surface of openjd.model into this package's namespace.
import openjd.model as _root  # noqa: F401  -- ensures parent finishes loading

from openjd.model import *  # noqa: F401,F403
from openjd.model import __all__ as _root_all

__all__ = tuple(_root_all)


# Alias submodules so that ``import openjd.model.v0.X`` (and
# ``from openjd.model.v0.X import Y``) resolve to ``openjd.model.X``.
#
# Listing submodules explicitly (rather than walking the package) keeps the
# public/private surface intentional: only modules explicitly enumerated below
# can be imported as ``openjd.model.v0.<name>``.

# Top-level submodules of openjd.model
_TOP_LEVEL_SUBMODULES = (
    # Public
    "v2023_09",
    # Underscore-private (used by internal tests / advanced consumers)
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

# Nested submodules of openjd.model._format_strings
_FORMAT_STRINGS_SUBMODULES = (
    "_dyn_constrained_str",
    "_edit_distance",
    "_expression",
    "_format_string",
    "_nodes",
    "_parser",
    "_tokens",
)

# Nested submodules of openjd.model._internal
_INTERNAL_SUBMODULES = (
    "_combination_expr",
    "_create_job",
    "_param_space_dim_validation",
    "_validator_functions",
    "_variable_reference_validation",
)

# Nested submodules of openjd.model.v2023_09
_V2023_09_SUBMODULES = ("_model",)


def _alias(src: str, dst: str) -> None:
    """Register *src* as a module under *dst* in sys.modules.

    Also binds *dst*'s leaf name as an attribute on its parent package so that
    attribute access (``openjd.model.v0._parse``) resolves the same way as
    ``import`` does.
    """
    mod = _importlib.import_module(src)
    _sys.modules[dst] = mod
    parent_name, _, leaf = dst.rpartition(".")
    if parent_name and parent_name in _sys.modules:
        setattr(_sys.modules[parent_name], leaf, mod)


for _name in _TOP_LEVEL_SUBMODULES:
    _alias(f"openjd.model.{_name}", f"openjd.model.v0.{_name}")

for _name in _FORMAT_STRINGS_SUBMODULES:
    _alias(
        f"openjd.model._format_strings.{_name}",
        f"openjd.model.v0._format_strings.{_name}",
    )

for _name in _INTERNAL_SUBMODULES:
    _alias(
        f"openjd.model._internal.{_name}",
        f"openjd.model.v0._internal.{_name}",
    )

for _name in _V2023_09_SUBMODULES:
    _alias(
        f"openjd.model.v2023_09.{_name}",
        f"openjd.model.v0.v2023_09.{_name}",
    )

del _alias, _name
