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
    _validate_expr_tree_dimensions(parse_tree, parameter_range_lengths)


def validate_step_parameter_space_chunk_constraint(chunk_parameter: str, parse_tree: Node) -> bool:
    """This validates that the task parameter of type CHUNK[INT] never appears
    within scope of an associative expression. A single chunk consists of
    individual values from the non-chunk parameters, and a set of values from the
    chunk parameter. With this restriction, the session script code can interpret
    these parameters easily, while without it the specification would need to define
    how the associations are represented and provided to the script.

    Raises:
      ExpressionError if the combination expression violates the chunk constraint.
    """
    # Returns True if the subtree includes the chunk parameter, otherwise False
    if isinstance(parse_tree, IdentifierNode):
        return parse_tree.parameter == chunk_parameter
    elif isinstance(parse_tree, AssociationNode):
        for child in parse_tree.children:
            if validate_step_parameter_space_chunk_constraint(chunk_parameter, child):
                raise ExpressionError(
                    (
                        f"CHUNK[INT] parameter {chunk_parameter} must not be part of an associative expression. "
                    )
                )
        return False
    else:
        # For type hinting
        assert isinstance(parse_tree, ProductNode)
        return any(
            validate_step_parameter_space_chunk_constraint(chunk_parameter, child)
            for child in parse_tree.children
        )


def _validate_expr_tree_dimensions(root: Node, parameter_range_lengths: dict[str, int]) -> int:
    # Returns the length of the subtree while recursively validating it.
    if isinstance(root, IdentifierNode):
        name = root.parameter
        return parameter_range_lengths[name]
    elif isinstance(root, AssociationNode):
        # Association requires that all arguments are the exact same length.
        # Ensure that is the case
        arg_lengths = tuple(
            _validate_expr_tree_dimensions(child, parameter_range_lengths)
            for child in root.children
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
            mul,
            (
                _validate_expr_tree_dimensions(child, parameter_range_lengths)
                for child in root.children
            ),
            1,
        )
