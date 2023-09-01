# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator, Sized
from dataclasses import dataclass, field
from functools import reduce
from operator import mul
from typing import AbstractSet, Optional, Union

from ._internal import (
    CombinationExpressionAssociationNode,
    CombinationExpressionIdentifierNode,
    CombinationExpressionNode,
    CombinationExpressionParser,
    CombinationExpressionProductNode,
    IntRangeExpression,
    RangeExpressionParser,
)
from ._types import ParameterValue, ParameterValueType, StepParameterSpace, TaskParameterSet
from .v2023_09 import (
    RangeExpressionTaskParameterDefinition as RangeExpressionTaskParameterDefinition_2023_09,
)
from .v2023_09 import RangeListTaskParameterDefinition as RangeListTaskParameterDefinition_2023_09

__all__ = ["StepParameterSpaceIterator"]


RangeTaskParameter = Union[
    RangeListTaskParameterDefinition_2023_09, RangeExpressionTaskParameterDefinition_2023_09
]
TaskParameter = RangeTaskParameter


class StepParameterSpaceIterator(Iterable[TaskParameterSet], Sized):
    """The multidimensional space formed by all possible task parameter values.

    The iteration order is dictated by the order of each parameter's values, and
    the order of the expressions within the combination expression of the StepParameterSpace.
    Ordering is row-major (right-most moves fastest) for products ('*') in the expression.

    For example, given:
        A = [1,2,3]
        B = [1,2]
        C = [10,11]
    Then:
        combination = "A * (B,C)"
        results in the order:
        (A=1,B=1,C=10), (A=1,B=2,C=11), (A=2,B=1,C=10), (A=2,B=2,C=11), (A=3,B=1,C=10), (A=3,B=2,C=11)
    Or
        combination = "(B,C) * A"
        results in the order:
        (A=1,B=1,C=10), (A=2,B=1,C=10), (A=3,B=1,C=10), (A=1,B=2,C=11), (A=2,B=2,C=11), (A=3,B=2,C=11)

    For comparison:
        A = [3,2,1]
        B = [1,2]
        C = [10,11]
        combination = "A * (B,C)"
    would be the order:
        (A=3,B=1,C=10), (A=3,B=2,C=11), (A=2,B=1,C=10), (A=2,B=2,C=11), (A=1,B=1,C=10), (A=1,B=2,C=11)

    Attributes:
        None
    """

    _parameters: dict[str, TaskParameter]
    _expr_tree: Node
    _parsedtree: CombinationExpressionNode

    def __init__(self, *, space: StepParameterSpace):
        if space.combination is None:
            # space.taskParameterDefinitions is a dict[str,TaskParameter]
            combination = "*".join(name for name in space.taskParameterDefinitions)
        else:
            combination = space.combination
        self._parameters = dict(space.taskParameterDefinitions)

        # Raises: TokenError, ExpressionError
        self._parsetree = CombinationExpressionParser().parse(combination)
        self._expr_tree = self._create_expr_tree(self._parsetree)

    @property
    def names(self) -> AbstractSet[str]:
        """Get the names of all parameters in the parameter space."""
        return self._parameters.keys()

    def __iter__(self) -> Iterator[TaskParameterSet]:
        """Obtain an iterator that will iterate over every task parameter set
        in this parameter space.

        Note: The ordering of inputs generated by this iterator is **NOT**
        guaranteed to be invariant across versions of this library.
        """

        class Iter:
            _root: NodeIterator

            def __init__(self, root: Node):
                self._root = root.iter()

            def __iter__(self):  # pragma: no cover
                return self

            def __next__(self) -> TaskParameterSet:
                result: TaskParameterSet = TaskParameterSet()
                self._root.next(result)
                return result

        return Iter(self._expr_tree)

    def __len__(self) -> int:
        """The number of task parameter sets that are defined by this parameter space"""
        return len(self._expr_tree)

    def __getitem__(self, index: int) -> TaskParameterSet:
        """Get a specific task parameter set given an index.

        Note: The ordering of inputs is **NOT** guaranteed to be
        invariant across versions of this library.

        Args:
            index (int): Index for a task parameter set to fetch.

        Returns:
            dict[str, Union[int, float, str]]: Values of every task parameter. Dictionary key
                is the parameter  name.
        """
        return self._expr_tree[index]

    def _create_expr_tree(self, root: CombinationExpressionNode) -> Node:
        """Recursively make a copy of the given Parser-generated expression tree using
        the Node types defined in this file.
        """
        if isinstance(root, CombinationExpressionIdentifierNode):
            name = root.parameter
            parameter = self._parameters[name]
            if isinstance(parameter.range, list):
                return RangeListIdentifierNode(
                    name,
                    ParameterValueType(parameter.type),
                    parameter.range,
                )
            else:
                return RangeExpressionIdentifierNode(
                    name,
                    ParameterValueType(parameter.type),
                    parameter.range,
                )
        elif isinstance(root, CombinationExpressionAssociationNode):
            return AssociationNode(tuple(self._create_expr_tree(child) for child in root.children))
        else:
            assert isinstance(root, CombinationExpressionProductNode)
            return ProductNode(tuple(self._create_expr_tree(child) for child in root.children))

    def __eq__(self, other: object) -> bool:
        # For assisting unit testing
        if not isinstance(other, StepParameterSpaceIterator):  # pragma: no cover
            return NotImplemented
        return self._parameters == other._parameters and repr(self._parsetree) == repr(
            other._parsetree
        )


# -------
# Mirror classes for the parsed combination expression tree.
# We create these to separate out the functionality required by this class
# around iterating, length calculations, getitem, etc from the needs of
# an expression validator. To validate the expression it is sufficient to
# parse the expression and then collect all referenced identifiers into a list.


class NodeIterator(ABC):
    """Our own special iterator base class. We don't use the standard
    Python iterator interface. For efficiency we need to pass a
    dict into the next() operator and have the method add/modify the
    appropriate key/values in it. With the standard iterator we would
    have __next__ returning a dict and end up with a tonne of intermediary
    dicts created as we ran __next__ on the entire tree.
    """

    @abstractmethod
    def next(self, result: TaskParameterSet) -> None:
        raise NotImplementedError("Base class")  # pragma: no cover

    @abstractmethod
    def reset_iter(self) -> None:
        raise NotImplementedError("Base class")  # pragma: no cover


class Node(ABC, Sized):
    @abstractmethod
    def __getitem__(self, index: int) -> TaskParameterSet:
        raise NotImplementedError("Base class")  # pragma: no cover

    @abstractmethod
    def iter(self) -> NodeIterator:
        raise NotImplementedError("Base class")  # pragma: no cover


class ProductNodeIter(NodeIterator):
    """Iterator for a ProductNode

    Attributes:
        _children: Iterators for the child nodes of this node in the expression tree.
        _prev_result: Cached result from the previous iteration. See next() for explanation.
        _first_value: True if and only if we have not yet evaluated the first value of the iterator.
    """

    _children: tuple[NodeIterator, ...]
    _prev_result: TaskParameterSet
    _first_value: bool

    def __init__(self, children: tuple[Node, ...]):
        self._children = tuple(child.iter() for child in children)
        self._prev_result = TaskParameterSet()
        self._first_value = True

    def reset_iter(self) -> None:
        self._first_value = True
        for child in self._children:
            child.reset_iter()

    def next(self, result: TaskParameterSet) -> None:
        # We have to start from the previous result because we don't 'next' every
        # iterator when evaluting a ProductNode since not every value changes on each
        # iteration. So we start from the previous values and overwrite the values that
        # change
        if self._first_value:
            self._first_value = False
            for child in self._children:
                # Raises: StopIteration
                child.next(self._prev_result)
        else:
            # The way to think of the next() operation on a product node is
            # a row-major order traversal of a multidimensional space.
            # For example, if we have:
            #   A = [1,2]; B = [3,4]; C = [5,6]; and
            #  expr="A * B * C"
            # then the parameters on the right change more rapidly
            # than the parmeters on the left. In this case our traversal
            # order is:
            #    A  |  B  |  C
            #   ---------------
            #    1  |  3  |  5
            #    1  |  3  |  6
            #    1  |  4  |  5
            #    1  |  4  |  6
            #    2  |  3  |  5
            #    2  |  3  |  6
            #    2  |  4  |  5
            #    2  |  4  |  6
            #
            # To acheive, algorithmically, think about grade-school addition by
            # 1 with a carry.
            # We advance the right-most parameter by one. If that overflows (i.e.
            # hits the end of the iterator) then we reset its iterator and advance
            # the next parameter to its left. Repeating as neccessary until we have
            # hit the end of the left-most iterator -- which indicates the end of
            # the product iteration.

            pos = len(self._children) - 1
            while True:
                try:
                    # Raises: StopIteration
                    self._children[pos].next(self._prev_result)
                    break
                except StopIteration as e:
                    if pos > 0:
                        self._children[pos].reset_iter()
                        self._children[pos].next(self._prev_result)
                        pos -= 1
                    else:
                        raise e from None
        result.update(self._prev_result)


@dataclass
class ProductNode(Node):
    children: tuple[Node, ...]
    _len: Optional[int] = field(default=None, init=False, repr=False, compare=False)

    def __len__(self) -> int:
        if self._len is None:
            self._len = reduce(mul, (len(child) for child in self.children), 1)
        return self._len

    def __getitem__(self, index: int) -> TaskParameterSet:
        if index < 0:
            index = len(self) + index
        if not (0 <= index < len(self)):
            raise IndexError()
        result = dict()
        # See ProductNodeIter.next() for a long comment on how we define the ordering
        # of a product node's values.
        # To go from a specific index to the value we use the fact that we're doing
        # a row-major-ordering. Say we have the product "A * B * C" and we're looking
        # for the index of a product-value where the components of that product-value
        # are at indicies (a, b, c) --  i.e. A at index 'a', B at index 'b', and C at
        # index 'c'.
        # Then, the product-value index is simply:
        #   index = (a * len(B) + b)*len(C) + c
        # This generalizes... it's a big nested multiply-add.
        # Our algorithm here just finds (a,b,c) given index -- which we can do
        # because we know index, len(A), len(B), and len(C) -- and then recursively
        # finds the values of A @ index a, B @ index b, and C & index c to compose the
        # value for this product node.
        pos = len(self.children)
        while pos > 0:
            pos -= 1
            if pos > 0:
                child_length = len(self.children[pos])
                child_index = index % child_length
                index = index // child_length
            else:
                child_index = index
            result.update(self.children[pos][child_index])
        return result

    def iter(self) -> ProductNodeIter:
        return ProductNodeIter(self.children)


class AssociationNodeIter(NodeIterator):
    """Iterator for an AssociationNode

    Attributes:
        _children: Iterators for the child nodes of this node in the expression tree.
    """

    _children: tuple[NodeIterator, ...]

    def __init__(self, children: tuple[Node, ...]):
        self._children = tuple(child.iter() for child in children)

    def reset_iter(self) -> None:
        for child in self._children:
            child.reset_iter()

    def next(self, result: TaskParameterSet) -> None:
        for child in self._children:
            # Raises: StopIteration
            child.next(result)


@dataclass
class AssociationNode(Node):
    children: tuple[Node, ...]
    _len: Optional[int] = field(default=None, init=False, repr=False, compare=False)

    def __len__(self) -> int:
        if self._len is None:
            self._len = len(self.children[0])
        return self._len

    def __getitem__(self, index: int) -> TaskParameterSet:
        result = TaskParameterSet()
        for child in self.children:
            result.update(child[index])
        return result

    def iter(self) -> AssociationNodeIter:
        return AssociationNodeIter(self.children)


class RangeListIdentifierNodeIterator(NodeIterator):
    """Iterator for a RangeListIdentifierNode

    Attributes:
        _it: Iterator for the corresponding task parameter
        _parameter: The RangeListIdentifierNode this is iterating over.
    """

    _it: Iterator[str]
    _node: RangeListIdentifierNode

    def __init__(self, node: RangeListIdentifierNode):
        self._node = node
        self.reset_iter()

    def reset_iter(self) -> None:
        self._it = iter(self._node.range)

    def next(self, result: TaskParameterSet) -> None:
        # Raises: StopIteration
        v = next(self._it)
        result[self._node.name] = ParameterValue(type=self._node.type, value=v)


@dataclass
class RangeListIdentifierNode(Node):
    name: str
    type: ParameterValueType
    range: list[str]
    _len: int = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        self._len = len(self.range)

    def __len__(self) -> int:
        return self._len

    def __getitem__(self, index: int) -> TaskParameterSet:
        return {self.name: ParameterValue(type=self.type, value=self.range[index])}

    def iter(self) -> RangeListIdentifierNodeIterator:
        return RangeListIdentifierNodeIterator(self)


class RangeExpressionIdentifierNodeIterator(NodeIterator):
    """Iterator for a RangeExpressionIdentifierNode

    Attributes:
        _it: Iterator for the corresponding task parameter
        _parameter: The RangeExpressionIdentifierNode this is iterating over.
    """

    _it: Iterator[int]
    _node: RangeExpressionIdentifierNode

    def __init__(self, node: RangeExpressionIdentifierNode):
        self._node = node
        self.reset_iter()

    def reset_iter(self) -> None:
        self._it = iter(self._node.range_expression)

    def next(self, result: TaskParameterSet) -> None:
        # Raises: StopIteration
        v = next(self._it)
        result[self._node.name] = ParameterValue(type=self._node.type, value=str(v))


@dataclass
class RangeExpressionIdentifierNode(Node):
    name: str
    type: ParameterValueType
    range: str
    range_expression: IntRangeExpression = field(init=False, repr=False, compare=False)
    _len: int = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        self.range_expression = RangeExpressionParser().parse(self.range)
        self._len = len(self.range_expression)

    def __len__(self) -> int:
        return self._len

    def __getitem__(self, index: int) -> TaskParameterSet:
        return {self.name: ParameterValue(type=self.type, value=str(self.range_expression[index]))}

    def iter(self) -> RangeExpressionIdentifierNodeIterator:
        return RangeExpressionIdentifierNodeIterator(self)
