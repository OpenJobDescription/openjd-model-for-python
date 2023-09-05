# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Sequence, Union
import re

from ._format_strings import FormatString

_name_regex: re.Pattern = re.compile(
    r"^(?:[a-z_][a-z0-9_]+:)?(?:amount|attr)(?:\.[a-z_][a-z0-9_]*)+$"
)

_reserved_scopes = ("worker", "job", "step", "task")


def _split_vendor(capability_name: str) -> tuple[str, str]:
    if ":" in capability_name:
        # Code is like this to satisfy mypy.
        split = capability_name.split(":", 1)
        return (split[0], split[1])
    return ("", capability_name)


def _validate_capability_name(
    capability_name: Union[FormatString, str],
    standard_capabilities: Sequence[str],
    required_name_prefix: str,
) -> None:
    # If it has expressions like "{{ Param.SomeValue }}", will
    # validate when those values are substituted.
    if isinstance(capability_name, FormatString) and len(capability_name.expressions) > 0:
        return
    capability_name = capability_name.lower()
    if _name_regex.fullmatch(capability_name) is None:
        raise ValueError(f"Value is not a valid Capability name: {capability_name}")
    vendor, capability = _split_vendor(capability_name)

    if not vendor and capability in standard_capabilities:
        # Standard capability names are okay
        return

    if not capability.startswith(required_name_prefix):
        raise ValueError(
            f"Capability name after the vendor prefix must start with '{required_name_prefix}': {capability_name}"
        )

    # Make sure one of the reserved names isn't being used.
    scope = capability_name.split(".")[1]
    if scope in _reserved_scopes:
        raise ValueError(
            f"Only Open Job Description defined capabilities may start with '{required_name_prefix}{scope}': {capability_name}"
        )


def validate_amount_capability_name(
    *,
    capability_name: Union[FormatString, str],
    standard_capabilities: Sequence[str],
) -> None:
    """Checks whether or not the given string's contents

    Args:
        capability_name (Union[FormatString, str]): _description_
        standard_capabilities (Sequence[str]): _description_
    """
    _validate_capability_name(capability_name, standard_capabilities, "amount.")


def validate_attribute_capability_name(
    *,
    capability_name: Union[FormatString, str],
    standard_capabilities: Sequence[str],
) -> None:
    _validate_capability_name(capability_name, standard_capabilities, "attr.")
