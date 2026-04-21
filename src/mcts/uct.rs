use pyo3::prelude::*;

#[pyclass]
pub struct UctAgent;

#[pymethods]
impl UctAgent {
    #[new]
    pub fn new(_iterations: usize) -> Self {
        UctAgent
    }
}
