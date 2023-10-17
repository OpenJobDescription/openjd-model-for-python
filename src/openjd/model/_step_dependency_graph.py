# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

from dataclasses import dataclass

from ._types import Job, SchemaVersion, Step, dataclass_kwargs


@dataclass(frozen=True, **dataclass_kwargs)
class StepDependencyGraphNode:
    step: Step
    """The Step that this node represents
    """

    in_edges: list["StepDependencyGraphEdgeBase"]
    """Edges wherein this step depends upon another.
    """

    out_edges: list["StepDependencyGraphEdgeBase"]
    """Edges wherein this step is depended-upon by another.
    """


# Dev note: The edges are using a base/derived class relationship to be
#  forward looking. We'll add addition edge types when we get different kinds
#  of dependencies between steps (e.g. task-task dependencies)
@dataclass(frozen=True, **dataclass_kwargs)
class StepDependencyGraphEdgeBase:
    """Represents that the 'dependent' step depends upon
    the 'origin' step in some way.
    """

    origin: StepDependencyGraphNode
    """The origin Step of the dependency edge. This is the Step
    that is depended-upon.
    """

    dependent: StepDependencyGraphNode
    """The node that depends-upon the 'step' node.
    """


@dataclass(frozen=True, **dataclass_kwargs)
class StepDependencyGraphStepToStepEdge(StepDependencyGraphEdgeBase):
    """The edge denotes a dependency whereby no Tasks of a dependent
    Step can be started until the successful completion of all Tasks
    of another Step.
    """

    pass


class StepDependencyGraph:
    """The Step dependency graph of a given Job.

    The nodes in the graph each correspond to a single Step in the Job, and
    edges represent a dependency relationship between Steps.

    Each node in the graph contains the sets of its in-edges and out-edges.
    An in-edge for Step S is a dependency wherein S depends upon another Step.
    An out-edge for Step S is a dependency wherein S is depended upon by another Step.
    """

    # map from step name -> graph node
    _nodes: dict[str, StepDependencyGraphNode]

    def __init__(self, *, job: Job) -> None:
        # The only version supported at the moment.
        # Assert's here as a signal to change this class when we add a new spec rev.
        assert job.version == SchemaVersion.v2023_09

        # Step 1 - create all of the graph nodes (one per step)
        self._nodes = dict()
        for step in job.steps:
            self._nodes[step.name] = StepDependencyGraphNode(
                step=step, in_edges=list(), out_edges=list()
            )

        # Step 2 -- create the dependency edges
        for step in job.steps:
            if step.dependencies:
                step_node = self._nodes[step.name]
                for dep in step.dependencies:
                    origin = self._nodes[dep.dependsOn]
                    edge = StepDependencyGraphStepToStepEdge(origin=origin, dependent=step_node)
                    step_node.in_edges.append(edge)
                    origin.out_edges.append(edge)

    def __del__(self) -> None:
        for node in self._nodes.values():
            # delete the references to all edges, so they can be GC'd
            node.in_edges.clear()
            node.out_edges.clear()

        # delete the references to all nodes, so that they can be GC'd
        self._nodes.clear()

    def step_node(self, *, stepname: str) -> StepDependencyGraphNode:
        """Given the name of a step in the graph, return the dependency graph
        node for that step; the returned node contains the sets of dependency
        edges in and out of the step.

        Do not modify the returned object.
        """
        return self._nodes[stepname]

    @property
    def max_indegree(self) -> int:
        """Calculate and return the maximum indegree over all steps in the graph.
        The indegree of a Step is the number of Steps that it depends upon; equivalently,
        the number of edges where the Step is the 'dependent' in the edge.
        """
        return max(len(node.in_edges) for node in self._nodes.values())

    @property
    def max_outdegree(self) -> int:
        """Calculate and return the maximum outdegree over all steps in the graph.
        The outdegree of a Step is the number of Steps that depend upon it; equivalently,
        the number of edges where the Step is the 'origin' in the edge.
        """
        return max(len(node.out_edges) for node in self._nodes.values())
