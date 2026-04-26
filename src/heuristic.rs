use crate::game::GameState;
use pyo3::prelude::*;
use std::collections::HashMap;

#[derive(Clone)]
struct Weights {
    advancement: f32,
    material: f32,
    mobility: f32,
}

impl Default for Weights {
    fn default() -> Self {
        Weights { advancement: 1.0, material: 3.0, mobility: 0.1 }
    }
}

fn evaluate(state: &GameState, for_white: bool) -> f32 {
    let rows = state.rows as f32;
    let cols = state.cols;
    let w = Weights::default();
    let mut score = 0.0f32;

    // Advancement
    let mut wb = state.white;
    while wb != 0 {
        let sq = wb.trailing_zeros() as u8;
        let row = (sq / cols) as f32;
        score += row / (rows - 1.0) * w.advancement;
        wb &= wb - 1;
    }
    let mut bb = state.black;
    while bb != 0 {
        let sq = bb.trailing_zeros() as u8;
        let row = (sq / cols) as f32;
        score -= (rows - 1.0 - row) / (rows - 1.0) * w.advancement;
        bb &= bb - 1;
    }

    // Material
    let white_count = state.white.count_ones() as f32;
    let black_count = state.black.count_ones() as f32;
    score += (white_count - black_count) * w.material;

    // Mobility (current player only)
    let mobility = state.generate_moves_raw().len() as f32;
    if state.white_to_move {
        score += mobility * w.mobility;
    } else {
        score -= mobility * w.mobility;
    }

    if for_white { score } else { -score }
}

fn alpha_beta(state: &GameState, depth: i32, mut alpha: f32, beta: f32, for_white: bool) -> f32 {
    if let Some(winner) = state.winner_raw() {
        return if winner == for_white { 1000.0 } else { -1000.0 };
    }
    if depth == 0 {
        return evaluate(state, for_white);
    }

    let moves = state.generate_moves_raw();
    let mut best = f32::NEG_INFINITY;

    for (from, to) in moves {
        let child = state.apply_raw(from, to);
        let score = -alpha_beta(&child, depth - 1, -beta, -alpha, !for_white);
        if score > best {
            best = score;
        }
        if score > alpha {
            alpha = score;
        }
        if alpha >= beta {
            break;
        }
    }
    best
}

#[pyclass]
pub struct HeuristicAgent {
    depth: i32,
}

#[pymethods]
impl HeuristicAgent {
    #[new]
    #[pyo3(signature = (depth = 5, weights = None))]
    pub fn new(depth: i32, weights: Option<HashMap<String, f32>>) -> Self {
        let _ = weights; // Reserved for future tuning; default weights used now.
        HeuristicAgent { depth }
    }

    pub fn select_move(&self, state: &GameState) -> (u8, u8) {
        let for_white = state.white_to_move;
        let moves = state.generate_moves_raw();
        assert!(!moves.is_empty(), "select_move called on terminal state");

        let mut best_move = moves[0];
        let mut best_score = f32::NEG_INFINITY;

        for (from, to) in &moves {
            let child = state.apply_raw(*from, *to);
            let score = -alpha_beta(
                &child,
                self.depth - 1,
                f32::NEG_INFINITY,
                f32::INFINITY,
                !for_white,
            );
            if score > best_score {
                best_score = score;
                best_move = (*from, *to);
            }
        }
        best_move
    }
}
