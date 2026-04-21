use pyo3::prelude::*;

#[pyclass]
pub struct HeuristicAgent;

#[pymethods]
impl HeuristicAgent {
    #[new]
    pub fn new(_depth: i32) -> Self {
        HeuristicAgent
    }
}
