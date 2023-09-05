# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest
import string
from typing import Union

from openjd.model import validate_amount_capability_name, validate_attribute_capability_name
from openjd.model.v2023_09 import FormatString

TEST_BUILTIN_AMOUNTS: list[str] = [
    "amount.worker.foo",
    "amount.job.foo",
    "amount.step.foo",
    "amount.task.foo",
]
TEST_BUILTIN_ATTRIBUTES: list[str] = [
    "attr.worker.foo",
    "attr.job.foo",
    "attr.step.foo",
    "attr.task.foo",
]


def _success_test_values(prefix: str) -> list:
    return (
        [
            pytest.param(f"{prefix}.worker.foo", id="builtin worker"),
            pytest.param(f"{prefix}.job.foo", id="builtin job"),
            pytest.param(f"{prefix}.step.foo", id="builtin step"),
            pytest.param(f"{prefix}.task.foo", id="builtin task"),
            pytest.param(f"{prefix}.custom", id="customer-defined"),
            pytest.param(f"vendor:{prefix}.custom", id="vendor-defined"),
            pytest.param(f"{prefix.upper()}.WORKER.FOO", id="caps"),
            pytest.param(f"VENDOR:{prefix.upper()}.CUSTOM", id="caps vendor"),
            pytest.param(FormatString(f"{prefix}.worker.foo"), id="format string no expression"),
            pytest.param(
                FormatString(f"{prefix.upper()}.WORKER.FOO"), id="caps format string no expression"
            ),
            pytest.param(FormatString("{{ Param.Foo }}"), id="format string with expression"),
            pytest.param(
                FormatString(f"{prefix}.{{{{ Param.Foo }}}}"), id="format string partial expression"
            ),
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
    return (
        [
            pytest.param(f"vendor:{prefix}.worker.foo", id="vendor scoped builtin"),
            pytest.param(f"{other_prefix}.worker.foo", id=f"must start with {prefix}"),
            pytest.param(f"{prefix}.worker.notreserved", id="reserved worker scope"),
            pytest.param(f"{prefix}.job.notreserved", id="reserved job scope"),
            pytest.param(f"{prefix}.step.notreserved", id="reserved step scope"),
            pytest.param(f"{prefix}.task.notreserved", id="reserved task scope"),
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
    @pytest.mark.parametrize("value", _success_test_values("amount"))
    def test_success(self, value: Union[str, FormatString]) -> None:
        # WHEN
        validate_amount_capability_name(
            capability_name=value, standard_capabilities=TEST_BUILTIN_AMOUNTS
        )

        # THEN
        # does not raise

    @pytest.mark.parametrize("value", _error_test_values("amount", "attr"))
    def test_errors(self, value: Union[str, FormatString]) -> None:
        # THEN
        with pytest.raises(ValueError):
            validate_amount_capability_name(
                capability_name=value, standard_capabilities=TEST_BUILTIN_AMOUNTS
            )


class TestValidateAttributeCapabilityName:
    @pytest.mark.parametrize("value", _success_test_values("attr"))
    def test_success(self, value: Union[str, FormatString]) -> None:
        # WHEN
        validate_attribute_capability_name(
            capability_name=value, standard_capabilities=TEST_BUILTIN_ATTRIBUTES
        )

        # THEN
        # does not raise

    @pytest.mark.parametrize("value", _error_test_values("attr", "amount"))
    def test_errors(self, value: Union[str, FormatString]) -> None:
        # THEN
        with pytest.raises(ValueError):
            validate_attribute_capability_name(
                capability_name=value, standard_capabilities=TEST_BUILTIN_ATTRIBUTES
            )
