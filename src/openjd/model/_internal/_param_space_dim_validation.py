# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from functools import reduce
from operator import mul
from ._combination_expr import AssociationNode, IdentifierNode, Node, Parser, ProductNode
from .._errors import ExpressionError


def validate_step_parameter_space_dimensions(
    parameter_range_lengths: dict[str, int], combination: str
) -> None:
    """This validates that a CombinationExpr satisfies constraints placed
    on the ranges of the elements of the expression.
    Specifically that the arguments to an Associative operator all have
    the exact same number of elements.

    Args:
      - parameter_range_lengths: dict[str,int] -- A map from identifier name
          to the number of elements in that parameter's range.
      - combination: str -- The combination expression.

    Raises:
       ExpressionError if the combination expression violates constraints.
    """
    parse_tree = Parser().parse(combination)
    _validate_expr_tree(parse_tree, parameter_range_lengths)


def _validate_expr_tree(root: Node, parameter_range_lengths: dict[str, int]) -> int:
    # Returns the length of the subtree while recursively validating it.
    if isinstance(root, IdentifierNode):
        name = root.parameter
        return parameter_range_lengths[name]
    elif isinstance(root, AssociationNode):
        # Association requires that all arguments are the exact same length.
        # Ensure that is the case
        arg_lengths = tuple(
            _validate_expr_tree(child, parameter_range_lengths) for child in root.children
        )
        if len(set(arg_lengths)) > 1:
            raise ExpressionError(
                (
                    "Associative expressions must have arguments with identical ranges. "
                    "Expression %s has argument lengths %s." % (str(root), arg_lengths)
                )
            )
        return arg_lengths[0]
    else:
        # For type hinting
        assert isinstance(root, ProductNode)
        return reduce(
            mul, (_validate_expr_tree(child, parameter_range_lengths) for child in root.children), 1
        )
