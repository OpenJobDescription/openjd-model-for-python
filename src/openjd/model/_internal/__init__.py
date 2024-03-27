# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any, Callable, TypeVar

from ._combination_expr import AssociationNode as CombinationExpressionAssociationNode
from ._combination_expr import IdentifierNode as CombinationExpressionIdentifierNode
from ._combination_expr import Node as CombinationExpressionNode
from ._combination_expr import Parser as CombinationExpressionParser
from ._combination_expr import ProductNode as CombinationExpressionProductNode
from ._create_job import instantiate_model
from ._param_space_dim_validation import validate_step_parameter_space_dimensions
from ._variable_reference_validation import prevalidate_model_template_variable_references

__all__ = (
    "instantiate_model",
    "prevalidate_model_template_variable_references",
    "validate_step_parameter_space_dimensions",
    "validate_unique_elements",
    "CombinationExpressionAssociationNode",
    "CombinationExpressionIdentifierNode",
    "CombinationExpressionNode",
    "CombinationExpressionParser",
    "CombinationExpressionProductNode",
)

T = TypeVar("T")


def validate_unique_elements(
    lst: list[T], *, item_value: Callable[[T], Any], property: str
) -> list[T]:
    """Pydantic validator that can be used that every item in a list has a unique
    value for a specific property.

    Args:
        lst: The list to check
        item_value: A callable that extracts the value-to-compare from an element
            of the list.
        property: Name of the property for error messages
    """
    items = tuple(item_value(i) for i in lst)
    item_set = set(items)
    if len(lst) != len(item_set):
        items_seen = set()
        duplicate_items = set()
        for i in items:
            if i in items_seen:
                duplicate_items.add(i)
            else:
                items_seen.add(i)
        raise ValueError(
            f"Duplicate values for {property} are not allowed. Duplicate values: {','.join(duplicate_items)}"
        )
    return lst
