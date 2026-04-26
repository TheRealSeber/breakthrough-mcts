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

fn rave_score(
    visits: u32,
    wins: f32,
    parent_amaf: Option<(u32, f32)>,
    log_parent_visits: f64,
    c: f64,
    rave_k: f64,
) -> f64 {
    if visits == 0 {
        return f64::INFINITY;
    }
    let n = visits as f64;
    let q_uct = wins as f64 / n;
    let q_rave = match parent_amaf {
        Some((av, aw)) if av > 0 => aw as f64 / av as f64,
        _ => 0.5,
    };
    let beta = (rave_k / (3.0 * n + rave_k)).sqrt();
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

fn backprop_rave(
    pool: &mut Vec<RaveNode>,
    leaf_idx: usize,
    sim_trace: &[(bool, u16)],
    winner: bool,
) {
    let mut idx_opt = Some(leaf_idx);
    while let Some(idx) = idx_opt {
        let node = &mut pool[idx];
        node.visits += 1;
        if winner != node.white_to_move {
            node.wins += 1.0;
        }
        // AMAF update: for each simulation move where the mover is the player-to-move
        // FROM this node, update amaf stats.
        let player_at_node = node.white_to_move;
        for &(sim_white_moved, mv_key) in sim_trace {
            if sim_white_moved == player_at_node {
                let entry = node.amaf.entry(mv_key).or_insert((0, 0.0));
                entry.0 += 1;
                if winner == player_at_node {
                    entry.1 += 1.0;
                }
            }
        }
        idx_opt = node.parent;
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
    rave_k: f64,
    rng: Xoshiro256PlusPlus,
}

#[pymethods]
impl RaveAgent {
    #[new]
    #[pyo3(signature = (iterations, c = 1.4142135623730951, rave_k = 1000.0, seed = None))]
    pub fn new(iterations: usize, c: f64, rave_k: f64, seed: Option<u64>) -> Self {
        let rng = match seed {
            Some(s) => Xoshiro256PlusPlus::seed_from_u64(s),
            None => Xoshiro256PlusPlus::from_entropy(),
        };
        RaveAgent {
            iterations,
            c,
            rave_k,
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
            // Selection
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
                        let rave_k = self.rave_k;
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
                                rave_score(
                                    pool[a].visits,
                                    pool[a].wins,
                                    amaf_a,
                                    log_n,
                                    c,
                                    rave_k,
                                )
                                .partial_cmp(&rave_score(
                                    pool[b].visits,
                                    pool[b].wins,
                                    amaf_b,
                                    log_n,
                                    c,
                                    rave_k,
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

            let (winner, sim_trace) = if let Some(w) = leaf_state.winner_raw() {
                (w, Vec::new())
            } else {
                let (child_idx, child_state) =
                    expand_rave(&mut pool, leaf_idx, &leaf_state, &mut self.rng);
                leaf_idx = child_idx;
                simulate_trace(&child_state, &mut self.rng)
            };

            backprop_rave(&mut pool, leaf_idx, &sim_trace, winner);
        }

        let best = *pool[0]
            .children
            .iter()
            .max_by_key(|&&c| pool[c].visits)
            .unwrap();
        pool[best].last_move.unwrap()
    }
}
