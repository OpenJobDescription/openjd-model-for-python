# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any, Optional, Dict, Set

from openjd.model import (  # StepDependencyGraphNode,; ,
    StepDependencyGraph,
    StepDependencyGraphStepToStepEdge,
    create_job,
    parse_model,
)
from openjd.model.v2023_09 import JobTemplate as JobTemplate_2023_09


class TestStepDependencyGraph_2023_09:
    def create_step_template(
        self, name: str, dependsOn: Optional[Set[str]] = None
    ) -> Dict[str, Any]:
        """A helper for generating step template data."""
        toreturn: Dict[str, Any] = {
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
                self.create_step_template("Foo", {"Buz"}),
                self.create_step_template("Bar", {"Foo", "Buz"}),
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
