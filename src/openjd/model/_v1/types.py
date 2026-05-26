# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Cross-cutting model types.

Mirrors ``openjd_model::types`` (and ``openjd_model::parse::DocumentType``)
in the underlying Rust crate. These types are neither template-time nor
job-time but are referenced by both: enums for parameter types,
extension and revision descriptors, validation context, etc.
"""

from openjd._openjd_rs import (
    # Document parsing
    DocumentType,
    # Parameter type / value enums
    JobParameterType,
    JobParameterValue,
    TaskParameterType,
    TaskParameterValue,
    # Profile / extensions / limits / validation
    ModelExtension,
    ModelProfile,
    CallerLimits,
    ValidationContext,
    # Spec-revision and template-version pyclass enums (str-Enum-like;
    # also re-exported at the package top level for legacy callers).
    SpecificationRevision,
    TemplateSpecificationVersion,
)

__all__ = (
    "CallerLimits",
    "DocumentType",
    "JobParameterType",
    "JobParameterValue",
    "ModelExtension",
    "ModelProfile",
    "SpecificationRevision",
    "TaskParameterType",
    "TaskParameterValue",
    "TemplateSpecificationVersion",
    "ValidationContext",
)
