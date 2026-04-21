use pyo3::prelude::*;

#[pyclass]
#[derive(Clone)]
pub struct GameState {
    pub white_to_move: bool,
}

#[pymethods]
impl GameState {
    #[new]
    pub fn new(_rows: u8, _cols: u8) -> Self {
        GameState { white_to_move: true }
    }
}
