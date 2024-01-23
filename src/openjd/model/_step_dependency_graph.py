# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.


from dataclasses import dataclass

from ._types import Job, SpecificationRevision, Step, dataclass_kwargs


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
        assert job.revision == SpecificationRevision.v2023_09

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

    def topo_sorted(self) -> list[Step]:
        """Return a sorted list of the Steps in the graph, in topological order.

        This is a stable sort as follows. Each Step, in order of appearance in the template,
        is placed as early as it can be without being earlier than a dependency or earlier than
        an already placed Step.

        Example uses for this ordering:
        1. To run all the Steps of a job in serial order. In topological order, every
            Step will run after all its dependencies.
        2. To submit a job to a render farm, one step at a time. In topological order,
            all the dependencies of each Step will have already been submitted, so all
            the IDs needed to specify dependencies in the destination render farm are
            available.
        """
        # Note: Python's stdlib includes graphlib.TopologicalSorter, but it does not
        #       act as a stable sort in the way we've defined in the docstring.

        started_names: set[str] = set()
        completed_names: set[str] = set()
        name_to_index: dict[str, int] = {name: index for index, name in enumerate(self._nodes)}
        node_stack: list[StepDependencyGraphNode] = []
        result: list[Step] = []

        # Process the nodes in the order they were defined in the template
        for node in self._nodes.values():
            # Add the node to the stack
            node_stack.append(node)
            # Process it and its dependencies until the stack is empty
            while len(node_stack) > 0:
                top_node = node_stack[-1]
                if top_node.step.name in completed_names:
                    # Node was already completed, nothing more to process
                    node_stack.pop()
                elif top_node.step.name in started_names:
                    # Node is now complete, append to the result list
                    result.append(top_node.step)
                    completed_names.add(top_node.step.name)
                else:
                    # Node is ready to start
                    started_names.add(top_node.step.name)
                    # Add all the dependencies that aren't completed to the stack
                    dep_names = [
                        dep.origin.step.name
                        for dep in top_node.in_edges
                        if dep.origin.step.name not in completed_names
                    ]
                    # Sort them in reverse of the index order from the template, to process them earliest first
                    dep_names = sorted(
                        dep_names, key=lambda name: name_to_index[name], reverse=True
                    )
                    for dep_name in dep_names:
                        # If a dependency was started but not completed, we found a circular dependency
                        # The template validation should have caught this if it was parsed from an object,
                        # but if the model object was assembled by hand, this could happen.
                        if dep_name in started_names and dep_name not in completed_names:
                            cycle = " -> ".join(
                                cycle_node.step.name
                                for cycle_node in node_stack
                                if cycle_node.step.name in started_names
                            )
                            raise ValueError(
                                f"A circular dependency was found in the step dependency graph:\n{cycle} -> {dep_name}"
                            )
                        node_stack.append(self._nodes[dep_name])

        return result
