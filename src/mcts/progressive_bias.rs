use pyo3::prelude::*;

#[pyclass]
pub struct ProgressiveBiasAgent;

#[pymethods]
impl ProgressiveBiasAgent {
    #[new]
    pub fn new(_iterations: usize) -> Self {
        ProgressiveBiasAgent
    }
}
