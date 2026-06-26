# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Regression test: importing the v0 format-string parser must NOT eagerly load
the Rust expr surface.

The EXPR engine bindings (``openjd._openjd_rs`` / ``openjd.expr``) are loaded
lazily, only when an EXPR template is actually parsed (via ``ExprNode``). The
``EXPR_EXTENSION`` gate constant lives in ``_parser`` precisely so that merely
importing the parser does not pull in the compiled extension. This guards
against re-introducing a top-level ``from ._expr_support import ...`` in the
parser, which would force the Rust import on every non-EXPR parse path.

A subprocess with a fresh interpreter is used because the in-process test runner
has already imported these modules.
"""

import subprocess
import sys


def test_importing_parser_does_not_load_rust_expr_surface():
    code = (
        "import sys\n"
        "import openjd.model._format_strings._parser\n"
        "loaded = [m for m in ('openjd._openjd_rs', 'openjd.expr') if m in sys.modules]\n"
        "print(','.join(loaded))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    leaked = result.stdout.strip()
    assert leaked == "", f"Rust expr modules eagerly imported by the parser: {leaked}"
