use crate::game::GameState;
use pyo3::prelude::*;
use rand::Rng;
use rand::SeedableRng;
use rand_xoshiro::Xoshiro256PlusPlus;
use std::collections::HashMap;

fn encode_move(from: u8, to: u8) -> u16 {
    (from as u16) * 64 + (to as u16)
}

struct RaveNode {
    parent: Option<usize>,
    children: Vec<usize>,
    unexpanded: Vec<(u8, u8)>,
    visits: u32,
    wins: f32,
    white_to_move: bool,
    last_move: Option<(u8, u8)>,
    amaf: HashMap<u16, (u32, f32)>,
}

// β formula uses BOTH visit count n and AMAF count ñ. When AMAF data is
// missing (ñ=0), β=0 → pure UCT. When AMAF is rich and n is small, β is high.
fn rave_score(
    visits: u32,
    wins: f32,
    parent_amaf: Option<(u32, f32)>,
    log_parent_visits: f64,
    c: f64,
    rave_b_squared: f64,
) -> f64 {
    if visits == 0 {
        return f64::INFINITY;
    }
    let n = visits as f64;
    let q_uct = wins as f64 / n;
    let (q_rave, beta) = match parent_amaf {
        Some((av, aw)) if av > 0 => {
            let n_tilde = av as f64;
            let qr = aw as f64 / n_tilde;
            let b = n_tilde / (n + n_tilde + 4.0 * n * n_tilde * rave_b_squared);
            (qr, b)
        }
        _ => (0.0, 0.0), // no AMAF data → pure UCT
    };
    (1.0 - beta) * q_uct + beta * q_rave + c * (log_parent_visits / n).sqrt()
}

fn simulate_trace(
    state: &GameState,
    rng: &mut Xoshiro256PlusPlus,
) -> (bool, Vec<(bool, u16)>) {
    let mut s = state.clone();
    let mut trace = Vec::new();
    loop {
        if let Some(w) = s.winner_raw() {
            return (w, trace);
        }
        let moves = s.generate_moves_raw();
        let mv = moves[rng.gen_range(0..moves.len())];
        trace.push((s.white_to_move, encode_move(mv.0, mv.1)));
        s = s.apply_raw(mv.0, mv.1);
    }
}

fn expand_rave(
    pool: &mut Vec<RaveNode>,
    idx: usize,
    state: &GameState,
    rng: &mut Xoshiro256PlusPlus,
) -> (usize, GameState) {
    let ulen = pool[idx].unexpanded.len();
    let mv_idx = rng.gen_range(0..ulen);
    let mv = pool[idx].unexpanded.swap_remove(mv_idx);
    let new_state = state.apply_raw(mv.0, mv.1);
    let child_idx = pool.len();
    let child_unexpanded = if new_state.winner_raw().is_none() {
        new_state.generate_moves_raw()
    } else {
        vec![]
    };
    pool.push(RaveNode {
        parent: Some(idx),
        children: vec![],
        unexpanded: child_unexpanded,
        visits: 0,
        wins: 0.0,
        white_to_move: new_state.white_to_move,
        last_move: Some(mv),
        amaf: HashMap::new(),
    });
    pool[idx].children.push(child_idx);
    (child_idx, new_state)
}

#[pyclass]
pub struct RaveAgent {
    iterations: usize,
    c: f64,
    rave_b_squared: f64,
    rng: Xoshiro256PlusPlus,
}

#[pymethods]
impl RaveAgent {
    // rave_k kept as positional name for back-compat with experiment configs;
    // semantically it's now b² in Silver's formula β = ñ / (n + ñ + 4·n·ñ·b²).
    // Default 0.01 chosen empirically for Breakthrough 6×6 (Go-tuned 1e-4 puts
    // too much weight on noisy rollout AMAF; larger b² gives β a faster decay).
    #[new]
    #[pyo3(signature = (iterations, c = 1.4142135623730951, rave_k = 0.01, seed = None))]
    pub fn new(iterations: usize, c: f64, rave_k: f64, seed: Option<u64>) -> Self {
        let rng = match seed {
            Some(s) => Xoshiro256PlusPlus::seed_from_u64(s),
            None => Xoshiro256PlusPlus::from_entropy(),
        };
        RaveAgent {
            iterations,
            c,
            rave_b_squared: rave_k,
            rng,
        }
    }

    pub fn select_move(&mut self, state: &GameState) -> (u8, u8) {
        let mut pool: Vec<RaveNode> = Vec::with_capacity(self.iterations + 1);
        pool.push(RaveNode {
            parent: None,
            children: vec![],
            unexpanded: state.generate_moves_raw(),
            visits: 0,
            wins: 0.0,
            white_to_move: state.white_to_move,
            last_move: None,
            amaf: HashMap::new(),
        });

        for _ in 0..self.iterations {
            // Selection: walk down, recording the path so AMAF backprop has
            // the in-tree moves available at every ancestor.
            let mut path_idx: Vec<usize> = vec![0];
            let mut path_moves: Vec<(bool, u16)> = Vec::new(); // (mover_was_white, mv_key)
            let mut s = state.clone();
            let mut idx = 0usize;

            loop {
                if !pool[idx].unexpanded.is_empty() || pool[idx].children.is_empty() {
                    break;
                }
                let best = {
                    let parent = &pool[idx];
                    let log_n = (parent.visits as f64).ln();
                    let c = self.c;
                    let b2 = self.rave_b_squared;
                    *parent
                        .children
                        .iter()
                        .max_by(|&&a, &&b| {
                            let mv_a = encode_move(
                                pool[a].last_move.unwrap().0,
                                pool[a].last_move.unwrap().1,
                            );
                            let mv_b = encode_move(
                                pool[b].last_move.unwrap().0,
                                pool[b].last_move.unwrap().1,
                            );
                            let amaf_a = parent.amaf.get(&mv_a).copied();
                            let amaf_b = parent.amaf.get(&mv_b).copied();
                            rave_score(pool[a].visits, pool[a].wins, amaf_a, log_n, c, b2)
                                .partial_cmp(&rave_score(
                                    pool[b].visits,
                                    pool[b].wins,
                                    amaf_b,
                                    log_n,
                                    c,
                                    b2,
                                ))
                                .unwrap_or(std::cmp::Ordering::Equal)
                        })
                        .unwrap()
                };
                let mv = pool[best].last_move.unwrap();
                path_moves.push((pool[idx].white_to_move, encode_move(mv.0, mv.1)));
                s = s.apply_raw(mv.0, mv.1);
                idx = best;
                path_idx.push(idx);
            }

            let leaf_idx = idx;
            let leaf_state = s;

            let (winner, sim_trace) = if let Some(w) = leaf_state.winner_raw() {
                (w, Vec::new())
            } else {
                let mover_at_leaf = pool[leaf_idx].white_to_move;
                let (child_idx, child_state) =
                    expand_rave(&mut pool, leaf_idx, &leaf_state, &mut self.rng);
                let exp_mv = pool[child_idx].last_move.unwrap();
                path_idx.push(child_idx);
                path_moves.push((mover_at_leaf, encode_move(exp_mv.0, exp_mv.1)));
                simulate_trace(&child_state, &mut self.rng)
            };

            // Backprop with full trace at each level. At node path_idx[k], the
            // AMAF-relevant moves are path_moves[k..] (tree moves below this
            // node, plus expansion move) plus sim_trace.
            let total_path_moves = path_moves.len();
            for k in 0..path_idx.len() {
                let node_idx = path_idx[k];
                let player_at_node = pool[node_idx].white_to_move;
                pool[node_idx].visits += 1;
                if winner != player_at_node {
                    pool[node_idx].wins += 1.0;
                }
                for j in k..total_path_moves {
                    let (mover, mv_key) = path_moves[j];
                    if mover == player_at_node {
                        let entry = pool[node_idx].amaf.entry(mv_key).or_insert((0, 0.0));
                        entry.0 += 1;
                        if winner == player_at_node {
                            entry.1 += 1.0;
                        }
                    }
                }
                for &(sim_white_moved, mv_key) in &sim_trace {
                    if sim_white_moved == player_at_node {
                        let entry = pool[node_idx].amaf.entry(mv_key).or_insert((0, 0.0));
                        entry.0 += 1;
                        if winner == player_at_node {
                            entry.1 += 1.0;
                        }
                    }
                }
            }
        }

        let best = *pool[0]
            .children
            .iter()
            .max_by_key(|&&c| pool[c].visits)
            .unwrap();
        pool[best].last_move.unwrap()
    }
}
