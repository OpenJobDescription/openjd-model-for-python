# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Model exceptions.

Mirrors ``openjd_model::error`` in the underlying Rust crate. These
are the exception classes raised by ``decode_*`` and ``create_job``.
"""

from openjd._openjd_rs import (
    DecodeValidationError,
    ModelValidationError,
    UnsupportedSchema,
)

__all__ = (
    "DecodeValidationError",
    "ModelValidationError",
    "UnsupportedSchema",
)
