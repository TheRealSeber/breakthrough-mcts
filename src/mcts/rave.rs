use pyo3::prelude::*;

#[pyclass]
pub struct RaveAgent;

#[pymethods]
impl RaveAgent {
    #[new]
    pub fn new(_iterations: usize) -> Self {
        RaveAgent
    }
}
