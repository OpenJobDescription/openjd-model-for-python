# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest
import string

from openjd.model._v1 import (
    standard_amount_capability_names,
    standard_attribute_capability_names,
    validate_amount_capability_name,
    validate_attribute_capability_name,
)


def _success_test_values(prefix: str, standard_names: list[str]) -> list:
    """Common success cases for both amount and attr validators.

    The validator accepts:
    - any spec-defined standard name (passed in via ``standard_names``)
    - any vendor-prefixed name with a valid regex shape
    - any non-vendor-prefixed name whose second dot-segment is NOT a
      reserved scope (worker/job/step/task)
    """
    return (
        [pytest.param(name, id=f"standard {name}") for name in standard_names]
        + [
            pytest.param(f"{prefix}.custom", id="customer-defined non-reserved"),
            pytest.param(f"vendor:{prefix}.custom", id="vendor-defined"),
            pytest.param(f"VENDOR:{prefix.upper()}.CUSTOM", id="caps vendor"),
        ]
        + [  # Test the vendor regex
            pytest.param(f"{letter}az09_:{prefix}.custom", id=f"vendor starts {letter}")
            for letter in "_az"
        ]
        + [  # Test the name regex, first segment
            pytest.param(f"{prefix}.{letter}az09_", id=f"segment starts {letter}")
            for letter in "_az"
        ]
        + [  # Test the name regex, second segment
            pytest.param(f"{prefix}.segment.{letter}az09_", id=f"2nd segment starts {letter}")
            for letter in "_az"
        ]
    )


def _error_test_values(prefix: str, other_prefix: str) -> list:
    """Common error cases for both amount and attr validators."""
    return (
        [
            pytest.param(f"{other_prefix}.worker.foo", id=f"must start with {prefix}"),
            pytest.param(f"{prefix}.worker.notstandard", id="reserved worker scope"),
            pytest.param(f"{prefix}.job.notstandard", id="reserved job scope"),
            pytest.param(f"{prefix}.step.notstandard", id="reserved step scope"),
            pytest.param(f"{prefix}.task.notstandard", id="reserved task scope"),
            pytest.param("foo.custom", id="bad prefix"),
            pytest.param(f"{prefix}.worker.foo\n", id="ends in newline"),
            pytest.param(f"{prefix}.worker.foo\n\n", id="ends in two newline"),
        ]
        + [
            pytest.param(f"{letter}:{prefix}.custom", id=f"vendor start {letter}")
            for letter in sorted(list(set(string.digits + string.punctuation) - set("_")))
        ]
        + [
            pytest.param(f"v{letter}:{prefix}.custom", id=f"vendor contains {letter}")
            for letter in sorted(list(set(string.punctuation) - set("_")))
        ]
        + [
            pytest.param(f"{prefix}.{letter}", id=f"name start {letter}")
            for letter in sorted(list(set(string.digits + string.punctuation) - set("_")))
        ]
        + [
            pytest.param(f"{prefix}.v{letter}", id=f"name contains {letter}")
            for letter in sorted(list(set(string.punctuation) - set("_")))
        ]
    )


class TestValidateAmountCapabilityName:
    @pytest.mark.parametrize(
        "value", _success_test_values("amount", standard_amount_capability_names())
    )
    def test_success(self, value: str) -> None:
        # WHEN
        validate_amount_capability_name(value)

        # THEN
        # does not raise

    @pytest.mark.parametrize("value", _error_test_values("amount", "attr"))
    def test_errors(self, value: str) -> None:
        # THEN
        with pytest.raises(ValueError):
            validate_amount_capability_name(value)

    def test_too_long(self) -> None:
        # 100-char cap is enforced
        long_name = "amount.foo." + "x" * 100
        with pytest.raises(ValueError, match="exceeds 100 characters"):
            validate_amount_capability_name(long_name)


class TestValidateAttributeCapabilityName:
    @pytest.mark.parametrize(
        "value", _success_test_values("attr", standard_attribute_capability_names())
    )
    def test_success(self, value: str) -> None:
        # WHEN
        validate_attribute_capability_name(value)

        # THEN
        # does not raise

    @pytest.mark.parametrize("value", _error_test_values("attr", "amount"))
    def test_errors(self, value: str) -> None:
        # THEN
        with pytest.raises(ValueError):
            validate_attribute_capability_name(value)

    def test_too_long(self) -> None:
        long_name = "attr.foo." + "x" * 100
        with pytest.raises(ValueError, match="exceeds 100 characters"):
            validate_attribute_capability_name(long_name)
