use crate::game::GameState;
use pyo3::prelude::*;
use rand::Rng;
use rand::SeedableRng;
use rand_xoshiro::Xoshiro256PlusPlus;

fn heuristic_move(state: &GameState, _from: u8, to: u8) -> f32 {
    let rows = state.rows as f32;
    let cols = state.cols;
    let to_row = (to / cols) as f32;
    let advancement = if state.white_to_move {
        to_row / (rows - 1.0)
    } else {
        (rows - 1.0 - to_row) / (rows - 1.0)
    };
    let is_capture = if state.white_to_move {
        state.black & (1u64 << to) != 0
    } else {
        state.white & (1u64 << to) != 0
    };
    let capture_bonus = if is_capture { 0.2f32 } else { 0.0 };
    (advancement + capture_bonus).min(1.0)
}

fn pb_score(visits: u32, wins: f32, h: f32, bias_weight: f32, log_parent: f64, c: f64) -> f64 {
    if visits == 0 {
        return f64::INFINITY;
    }
    let q = wins as f64 / visits as f64;
    let exploration = c * (log_parent / visits as f64).sqrt();
    let bias = (bias_weight as f64) * (h as f64) / (visits as f64 + 1.0);
    q + exploration + bias
}

struct PbNode {
    parent: Option<usize>,
    children: Vec<usize>,
    unexpanded: Vec<(u8, u8)>,
    visits: u32,
    wins: f32,
    white_to_move: bool,
    last_move: Option<(u8, u8)>,
    h: f32,
}

fn simulate(state: &GameState, rng: &mut Xoshiro256PlusPlus) -> bool {
    let mut s = state.clone();
    loop {
        if let Some(w) = s.winner_raw() {
            return w;
        }
        let moves = s.generate_moves_raw();
        let mv = moves[rng.gen_range(0..moves.len())];
        s = s.apply_raw(mv.0, mv.1);
    }
}

fn backprop(pool: &mut Vec<PbNode>, mut idx: usize, winner: bool) {
    loop {
        pool[idx].visits += 1;
        if winner != pool[idx].white_to_move {
            pool[idx].wins += 1.0;
        }
        match pool[idx].parent {
            Some(p) => idx = p,
            None => break,
        }
    }
}

fn expand(
    pool: &mut Vec<PbNode>,
    idx: usize,
    state: &GameState,
    rng: &mut Xoshiro256PlusPlus,
) -> (usize, GameState) {
    let ulen = pool[idx].unexpanded.len();
    let mv_idx = rng.gen_range(0..ulen);
    let mv = pool[idx].unexpanded.swap_remove(mv_idx);
    let new_state = state.apply_raw(mv.0, mv.1);
    let child_idx = pool.len();
    let h = heuristic_move(state, mv.0, mv.1);
    let child_unexpanded = if new_state.winner_raw().is_none() {
        new_state.generate_moves_raw()
    } else {
        vec![]
    };
    pool.push(PbNode {
        parent: Some(idx),
        children: vec![],
        unexpanded: child_unexpanded,
        visits: 0,
        wins: 0.0,
        white_to_move: new_state.white_to_move,
        last_move: Some(mv),
        h,
    });
    pool[idx].children.push(child_idx);
    (child_idx, new_state)
}

#[pyclass]
pub struct ProgressiveBiasAgent {
    iterations: usize,
    c: f64,
    bias_weight: f32,
    rng: Xoshiro256PlusPlus,
}

#[pymethods]
impl ProgressiveBiasAgent {
    #[new]
    #[pyo3(signature = (iterations, c = 1.4142135623730951, bias_weight = 1.0, seed = None))]
    pub fn new(iterations: usize, c: f64, bias_weight: f32, seed: Option<u64>) -> Self {
        let rng = match seed {
            Some(s) => Xoshiro256PlusPlus::seed_from_u64(s),
            None => Xoshiro256PlusPlus::from_entropy(),
        };
        ProgressiveBiasAgent { iterations, c, bias_weight, rng }
    }

    pub fn select_move(&mut self, state: &GameState) -> (u8, u8) {
        let mut pool: Vec<PbNode> = Vec::with_capacity(self.iterations + 1);
        pool.push(PbNode {
            parent: None,
            children: vec![],
            unexpanded: state.generate_moves_raw(),
            visits: 0,
            wins: 0.0,
            white_to_move: state.white_to_move,
            last_move: None,
            h: 0.0,
        });

        for _ in 0..self.iterations {
            let (mut leaf_idx, leaf_state) = {
                let mut idx = 0usize;
                let mut s = state.clone();
                loop {
                    if !pool[idx].unexpanded.is_empty() || pool[idx].children.is_empty() {
                        break;
                    }
                    let best = {
                        let parent = &pool[idx];
                        let log_n = (parent.visits as f64).ln();
                        let c = self.c;
                        let bw = self.bias_weight;
                        *parent
                            .children
                            .iter()
                            .max_by(|&&a, &&b| {
                                pb_score(pool[a].visits, pool[a].wins, pool[a].h, bw, log_n, c)
                                    .partial_cmp(&pb_score(
                                        pool[b].visits,
                                        pool[b].wins,
                                        pool[b].h,
                                        bw,
                                        log_n,
                                        c,
                                    ))
                                    .unwrap_or(std::cmp::Ordering::Equal)
                            })
                            .unwrap()
                    };
                    let mv = pool[best].last_move.unwrap();
                    s = s.apply_raw(mv.0, mv.1);
                    idx = best;
                }
                (idx, s)
            };

            let winner = if let Some(w) = leaf_state.winner_raw() {
                w
            } else {
                let (child_idx, child_state) = expand(&mut pool, leaf_idx, &leaf_state, &mut self.rng);
                leaf_idx = child_idx;
                simulate(&child_state, &mut self.rng)
            };

            backprop(&mut pool, leaf_idx, winner);
        }

        let best = *pool[0].children.iter().max_by_key(|&&c| pool[c].visits).unwrap();
        pool[best].last_move.unwrap()
    }
}
