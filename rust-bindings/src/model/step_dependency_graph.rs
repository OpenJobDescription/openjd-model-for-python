// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use pyo3::prelude::*;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_model::StepDependencyGraph;

use super::job::{PyJob, PyStep};
use crate::model::errors::model_err_to_py;

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.model._v1.job", name = "StepDependencyGraph")]
pub(crate) struct PyStepDependencyGraph {
    inner: StepDependencyGraph,
    job_steps: Vec<openjd_model::job::Step>,
}

impl PyStepDependencyGraph {
    fn make_node(&self, node_index: usize) -> PyStepDependencyNode {
        let node = self.inner.node(node_index).unwrap();
        let in_edges: Vec<PyStepDependencyEdge> = node
            .in_edges
            .iter()
            .filter_map(|&edge_idx| {
                let edge = self.inner.edge(edge_idx)?;
                Some(PyStepDependencyEdge {
                    origin_step: self.job_steps[edge.origin].clone(),
                    dependent_step: self.job_steps[edge.dependent].clone(),
                })
            })
            .collect();
        let out_edges: Vec<PyStepDependencyEdge> = node
            .out_edges
            .iter()
            .filter_map(|&edge_idx| {
                let edge = self.inner.edge(edge_idx)?;
                Some(PyStepDependencyEdge {
                    origin_step: self.job_steps[edge.origin].clone(),
                    dependent_step: self.job_steps[edge.dependent].clone(),
                })
            })
            .collect();
        PyStepDependencyNode {
            step: PyStep {
                inner: self.job_steps[node.step_index].clone(),
            },
            in_edges,
            out_edges,
        }
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyStepDependencyGraph {
    #[new]
    #[pyo3(signature = (*, job))]
    fn new(job: &PyJob) -> PyResult<Self> {
        let graph = StepDependencyGraph::new(&job.inner).map_err(model_err_to_py)?;
        Ok(Self {
            inner: graph,
            job_steps: job.inner.steps.clone(),
        })
    }

    #[getter]
    fn _nodes(&self) -> Vec<PyStepDependencyNode> {
        (0..self.inner.node_count())
            .map(|i| self.make_node(i))
            .collect()
    }

    fn step_node(&self, stepname: &str) -> PyResult<PyStepDependencyNode> {
        let node = self.inner.step_node(stepname).ok_or_else(|| {
            pyo3::exceptions::PyKeyError::new_err(format!("No step named '{stepname}'"))
        })?;
        Ok(self.make_node(node.step_index))
    }

    fn topo_sorted(&self) -> PyResult<Vec<PyStep>> {
        let indices = self.inner.topo_sorted().map_err(model_err_to_py)?;
        Ok(indices
            .into_iter()
            .map(|i| PyStep {
                inner: self.job_steps[i].clone(),
            })
            .collect())
    }

    fn step_names(&self) -> PyResult<Vec<String>> {
        self.inner.topo_sorted_names().map_err(model_err_to_py)
    }

    /// Maximum in-degree across all nodes — the largest number of
    /// dependencies any single step has. Returns ``0`` for an empty
    /// graph. Mirrors the underlying Rust crate's
    /// ``StepDependencyGraph::max_indegree``.
    #[getter]
    fn max_indegree(&self) -> usize {
        self.inner.max_indegree()
    }

    /// Maximum out-degree across all nodes — the largest number of
    /// steps that depend on any single step. Returns ``0`` for an
    /// empty graph. Mirrors the underlying Rust crate's
    /// ``StepDependencyGraph::max_outdegree``.
    #[getter]
    fn max_outdegree(&self) -> usize {
        self.inner.max_outdegree()
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.job",
    name = "StepDependencyNode",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyStepDependencyNode {
    #[pyo3(get)]
    step: PyStep,
    #[pyo3(get)]
    in_edges: Vec<PyStepDependencyEdge>,
    #[pyo3(get)]
    out_edges: Vec<PyStepDependencyEdge>,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.job",
    name = "StepDependencyEdge",
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyStepDependencyEdge {
    origin_step: openjd_model::job::Step,
    dependent_step: openjd_model::job::Step,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyStepDependencyEdge {
    #[getter]
    fn origin(&self) -> PyStepDependencyNode {
        PyStepDependencyNode {
            step: PyStep {
                inner: self.origin_step.clone(),
            },
            in_edges: vec![],
            out_edges: vec![],
        }
    }

    #[getter]
    fn dependent(&self) -> PyStepDependencyNode {
        PyStepDependencyNode {
            step: PyStep {
                inner: self.dependent_step.clone(),
            },
            in_edges: vec![],
            out_edges: vec![],
        }
    }
}
