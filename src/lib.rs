use pyo3::prelude::*;

mod game;
mod heuristic;
mod mcts;

#[pymodule]
fn breakthrough_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<game::GameState>()?;
    m.add_class::<mcts::uct::UctAgent>()?;
    m.add_class::<mcts::rave::RaveAgent>()?;
    m.add_class::<mcts::progressive_bias::ProgressiveBiasAgent>()?;
    m.add_class::<heuristic::HeuristicAgent>()?;
    Ok(())
}
