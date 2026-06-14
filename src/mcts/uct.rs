use crate::game::GameState;
use pyo3::prelude::*;
use rand::Rng;
use rand::SeedableRng;
use rand_xoshiro::Xoshiro256PlusPlus;

struct UctNode {
    parent: Option<usize>,
    children: Vec<usize>,
    unexpanded: Vec<(u8, u8)>,
    visits: u32,
    wins: f32,
    white_to_move: bool,
    last_move: Option<(u8, u8)>,
}

fn ucb1(node: &UctNode, log_parent_visits: f64, c: f64) -> f64 {
    if node.visits == 0 {
        return f64::INFINITY;
    }
    (node.wins as f64 / node.visits as f64)
        + c * (log_parent_visits / node.visits as f64).sqrt()
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

fn backprop(pool: &mut Vec<UctNode>, mut idx: usize, winner: bool) {
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
    pool: &mut Vec<UctNode>,
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
    pool.push(UctNode {
        parent: Some(idx),
        children: vec![],
        unexpanded: child_unexpanded,
        visits: 0,
        wins: 0.0,
        white_to_move: new_state.white_to_move,
        last_move: Some(mv),
    });
    pool[idx].children.push(child_idx);
    (child_idx, new_state)
}

#[pyclass]
pub struct UctAgent {
    iterations: usize,
    c: f64,
    rng: Xoshiro256PlusPlus,
}

#[pymethods]
impl UctAgent {
    #[new]
    #[pyo3(signature = (iterations, c = 1.4142135623730951, seed = None))]
    pub fn new(iterations: usize, c: f64, seed: Option<u64>) -> Self {
        let rng = match seed {
            Some(s) => Xoshiro256PlusPlus::seed_from_u64(s),
            None => Xoshiro256PlusPlus::from_entropy(),
        };
        UctAgent { iterations, c, rng }
    }

    pub fn select_move(&mut self, state: &GameState) -> (u8, u8) {
        let mut pool: Vec<UctNode> = Vec::with_capacity(self.iterations + 1);
        let root_moves = state.generate_moves_raw();
        pool.push(UctNode {
            parent: None,
            children: vec![],
            unexpanded: root_moves,
            visits: 0,
            wins: 0.0,
            white_to_move: state.white_to_move,
            last_move: None,
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
                        *parent
                            .children
                            .iter()
                            .max_by(|&&a, &&b| {
                                ucb1(&pool[a], log_n, c)
                                    .partial_cmp(&ucb1(&pool[b], log_n, c))
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
                let (child_idx, child_state) =
                    expand(&mut pool, leaf_idx, &leaf_state, &mut self.rng);
                leaf_idx = child_idx;
                simulate(&child_state, &mut self.rng)
            };

            backprop(&mut pool, leaf_idx, winner);
        }

        let best = *pool[0]
            .children
            .iter()
            .max_by_key(|&&c| pool[c].visits)
            .expect("root must have at least one child");
        pool[best].last_move.unwrap()
    }
}
