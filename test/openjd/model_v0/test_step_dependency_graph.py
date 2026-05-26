# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any, Optional
import random
import pytest

from openjd.model import (  # StepDependencyGraphNode,; ,
    StepDependencyGraph,
    StepDependencyGraphStepToStepEdge,
    create_job,
    parse_model,
)
from openjd.model.v2023_09 import JobTemplate as JobTemplate_2023_09


class TestStepDependencyGraph_2023_09:
    def create_step_template(
        self, name: str, dependsOn: Optional[list[str]] = None
    ) -> dict[str, Any]:
        """A helper for generating step template data."""
        toreturn: dict[str, Any] = {
            "name": name,
            "script": {"actions": {"onRun": {"command": "foo"}}},
        }
        if dependsOn:
            toreturn["dependencies"] = [{"dependsOn": dep} for dep in dependsOn]
        return toreturn

    def test_empty_graph(self) -> None:
        # GIVEN
        template_data = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Job",
            "steps": [
                self.create_step_template("Foo"),
                self.create_step_template("Bar"),
                self.create_step_template("Buz"),
            ],
        }
        job_template = parse_model(model=JobTemplate_2023_09, obj=template_data)
        job = create_job(job_template=job_template, job_parameter_values=dict())

        # WHEN
        result = StepDependencyGraph(job=job)

        # THEN
        assert len(result._nodes) == 3
        for name in ("Foo", "Bar", "Buz"):
            node = result.step_node(stepname=name)
            assert node.step.name == name
            assert len(node.in_edges) == 0
            assert len(node.out_edges) == 0

    def test_with_deps(self) -> None:
        # GIVEN
        template_data = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Job",
            "steps": [
                self.create_step_template("Foo", ["Buz"]),
                self.create_step_template("Bar", ["Foo", "Buz"]),
                self.create_step_template("Buz"),
            ],
        }
        job_template = parse_model(model=JobTemplate_2023_09, obj=template_data)
        job = create_job(job_template=job_template, job_parameter_values=dict())

        # WHEN
        result = StepDependencyGraph(job=job)

        # THEN
        assert len(result._nodes) == 3

        # Check Foo's deps
        node = result.step_node(stepname="Foo")
        assert node.step.name == "Foo"

        assert len(node.in_edges) == 1
        edge = node.in_edges[0]
        assert type(edge) is StepDependencyGraphStepToStepEdge
        assert edge.origin.step.name == "Buz"
        assert edge.dependent.step.name == "Foo"

        assert len(node.out_edges) == 1
        edge = node.out_edges[0]
        assert type(edge) is StepDependencyGraphStepToStepEdge
        assert edge.origin.step.name == "Foo"
        assert edge.dependent.step.name == "Bar"

        # Check Bar's deps
        node = result.step_node(stepname="Bar")
        assert node.step.name == "Bar"

        assert len(node.in_edges) == 2
        edge1, edge2 = node.in_edges
        assert type(edge1) is StepDependencyGraphStepToStepEdge
        assert type(edge2) is StepDependencyGraphStepToStepEdge
        assert edge1.origin.step.name == "Foo" or edge2.origin.step.name == "Foo"
        assert edge1.origin.step.name == "Buz" or edge2.origin.step.name == "Buz"
        assert edge1.dependent.step.name == "Bar"
        assert edge2.dependent.step.name == "Bar"

        assert len(node.out_edges) == 0

        # Check Buz's deps
        node = result.step_node(stepname="Buz")
        assert node.step.name == "Buz"
        assert len(node.in_edges) == 0
        assert len(node.out_edges) == 2
        edge1, edge2 = node.out_edges
        assert type(edge1) is StepDependencyGraphStepToStepEdge
        assert type(edge2) is StepDependencyGraphStepToStepEdge
        assert edge1.origin.step.name == "Buz"
        assert edge2.origin.step.name == "Buz"
        assert edge1.dependent.step.name == "Foo" or edge2.dependent.step.name == "Foo"
        assert edge1.dependent.step.name == "Bar" or edge2.dependent.step.name == "Bar"

    def test_topo_sort_no_deps_preserves_order(self) -> None:
        # If there are no edges, the topological sort should leave the ordering unchanged
        # GIVEN
        template_data: dict[str, Any] = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Job",
            "steps": [],
        }
        for _ in range(100):
            # Randomly generate the step names to rule out name-based ordering
            template_data["steps"].append(
                self.create_step_template("".join(random.sample("abcdefghijklmnop", 10)))
            )
        job_template = parse_model(model=JobTemplate_2023_09, obj=template_data)
        job = create_job(job_template=job_template, job_parameter_values=dict())
        graph = StepDependencyGraph(job=job)

        # WHEN
        topo_sorted_steps = graph.topo_sorted()

        # THEN
        assert job.steps == topo_sorted_steps

    def test_topo_sort_reverse_chain(self) -> None:
        # A chain going from the last to the first step should reverse the order
        # GIVEN
        template_data = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Job",
            "steps": [
                self.create_step_template("S1", ["S2"]),
                self.create_step_template("S2", ["S3"]),
                self.create_step_template("S3", ["S4"]),
                self.create_step_template("S4", ["S5"]),
                self.create_step_template("S5", ["S6"]),
                self.create_step_template("S6", ["S7"]),
                self.create_step_template("S7"),
            ],
        }
        job_template = parse_model(model=JobTemplate_2023_09, obj=template_data)
        job = create_job(job_template=job_template, job_parameter_values=dict())
        graph = StepDependencyGraph(job=job)

        # WHEN
        topo_sorted_steps = graph.topo_sorted()

        # THEN
        assert list(reversed(job.steps)) == topo_sorted_steps

    @pytest.mark.parametrize(
        "ordered_s1_deps",
        [
            pytest.param(["S2", "S3", "S5", "S6", "S7"], id="sorted"),
            pytest.param(["S7", "S6", "S5", "S3", "S2"], id="reverse sorted"),
            pytest.param(["S2", "S6", "S5", "S7", "S3"], id="random order"),
        ],
    )
    def test_topo_sort_dep_order(self, ordered_s1_deps: list[str]) -> None:
        # When steps are reordered, they stay stable according to the definition in the topo_sorted docstring
        # GIVEN
        template_data = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Job",
            "steps": [
                self.create_step_template("S1", ordered_s1_deps),
                self.create_step_template("S2"),
                self.create_step_template("S3"),
                self.create_step_template("S4"),
                self.create_step_template("S5"),
                self.create_step_template("S6"),
                self.create_step_template("S7"),
            ],
        }
        job_template = parse_model(model=JobTemplate_2023_09, obj=template_data)
        job = create_job(job_template=job_template, job_parameter_values=dict())
        graph = StepDependencyGraph(job=job)

        # WHEN
        topo_sorted_steps = graph.topo_sorted()

        # THEN
        assert ["S2", "S3", "S5", "S6", "S7", "S1", "S4"] == [
            step.name for step in topo_sorted_steps
        ]

    def test_topo_sort_cycle_error(self) -> None:
        # A cycle raises an exception
        # GIVEN
        template_data = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Job",
            "steps": [
                self.create_step_template("S1", ["S2"]),
                self.create_step_template("S2", ["S3"]),
                self.create_step_template("S3", ["S4"]),
                self.create_step_template("S4", ["S5"]),
                self.create_step_template("S5", ["S6"]),
                self.create_step_template("S6", ["S7"]),
                self.create_step_template("S7"),
            ],
        }
        job_template = parse_model(model=JobTemplate_2023_09, obj=template_data)
        job = create_job(job_template=job_template, job_parameter_values=dict())
        graph = StepDependencyGraph(job=job)
        # By hand, poke into the graph and finish the cycle
        node_S7 = graph.step_node(stepname="S7")
        node_S1 = graph.step_node(stepname="S1")
        edge = StepDependencyGraphStepToStepEdge(origin=node_S1, dependent=node_S7)
        node_S7.in_edges.append(edge)
        node_S1.out_edges.append(edge)

        # WHEN
        with pytest.raises(ValueError) as e:
            graph.topo_sorted()

        # THEN
        assert "circular dependency was found" in str(e)
        assert "S1 -> S2 -> S3 -> S4 -> S5 -> S6 -> S7 -> S1" in str(e)
