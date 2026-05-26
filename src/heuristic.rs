use crate::game::GameState;
use pyo3::prelude::*;
use std::collections::HashMap;

/// Advancement weights by row index (Algorithm 1, line 1).
const ADVANCEMENT_WEIGHTS: [f32; 8] = [1.0, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0];

/// Check if a specific bit (piece) is set at (row, col) on the given board.
fn has_bit(board: u64, row: i32, col: i32, cols: u8, rows: u8) -> bool {
    if row < 0 || row >= rows as i32 || col < 0 || col >= cols as i32 {
        return false;
    }
    board & (1u64 << (row as u8 * cols + col as u8)) != 0
}

/// Count legal moves for a specific side without allocating a Vec.
fn count_legal_moves(state: &GameState, for_white: bool) -> usize {
    let cols = state.cols as u32;
    let occupied = state.white | state.black;
    let empty = !occupied & state.board_mask;

    if for_white {
        let straight = (state.white << cols) & empty & state.board_mask;
        let diag_l = ((state.white & !state.left_edge) << (cols - 1))
            & (empty | state.black)
            & state.board_mask;
        let diag_r = ((state.white & !state.right_edge) << (cols + 1))
            & (empty | state.black)
            & state.board_mask;
        (straight.count_ones() + diag_l.count_ones() + diag_r.count_ones()) as usize
    } else {
        let straight = (state.black >> cols) & empty;
        let diag_l =
            ((state.black & !state.left_edge) >> (cols + 1)) & (empty | state.white);
        let diag_r =
            ((state.black & !state.right_edge) >> (cols - 1)) & (empty | state.white);
        (straight.count_ones() + diag_l.count_ones() + diag_r.count_ones()) as usize
    }
}

/// Algorithm 1: Position evaluation for Breakthrough 8×8.
/// Positive score favours White; negative favours Black.
fn evaluate(state: &GameState, for_white: bool) -> f32 {
    if let Some(winner) = state.winner_raw() {
        return if winner == for_white {
            f32::INFINITY
        } else {
            f32::NEG_INFINITY
        };
    }

    let rows = state.rows;
    let cols = state.cols;
    let mut v_white: f32 = 0.0;

    // --- Breakthrough threat for White (pieces on row rows-2 that can reach rows-1) ---
    {
        let threat_row = rows - 2;
        let target_row = rows - 1;
        let mut wb = state.white;
        while wb != 0 {
            let sq = wb.trailing_zeros() as u8;
            let r = sq / cols;
            let c = sq % cols;
            if r == threat_row {
                let occupied = state.white | state.black;
                // Straight: target empty
                let straight_sq = target_row * cols + c;
                let can_straight = occupied & (1u64 << straight_sq) == 0;
                // Diagonal left: empty or black
                let can_diag_l =
                    c > 0 && (state.white & (1u64 << (target_row * cols + c - 1))) == 0;
                // Diagonal right: empty or black
                let can_diag_r = c < cols - 1
                    && (state.white & (1u64 << (target_row * cols + c + 1))) == 0;
                if can_straight || can_diag_l || can_diag_r {
                    v_white += 200.0;
                }
            }
            wb &= wb - 1;
        }
    }

    // --- Per-piece scoring for White ---
    {
        let mut wb = state.white;
        while wb != 0 {
            let sq = wb.trailing_zeros() as u8;
            let r = sq / cols;
            let c = sq % cols;
            let ri = r as i32;
            let ci = c as i32;

            // a: advancement weight
            let a = if (r as usize) < ADVANCEMENT_WEIGHTS.len() {
                ADVANCEMENT_WEIGHTS[r as usize]
            } else {
                *ADVANCEMENT_WEIGHTS.last().unwrap()
            };

            // d: defender count
            let mut d: i32 = 0;
            if has_bit(state.white, ri - 1, ci - 1, cols, rows) {
                d += 1;
            }
            if has_bit(state.white, ri - 1, ci + 1, cols, rows) {
                d += 1;
            }

            // k: centrality bonus (for 8-column board)
            let k: f32 = if cols == 8 {
                match c {
                    3 | 4 => 1.15,
                    2 | 5 => 1.05,
                    _ => 1.0,
                }
            } else {
                1.0
            };

            // f: free path — no Black piece in expanding triangle ahead
            let mut free = true;
            'fw: for rr in (r + 1)..rows {
                let dist = (rr - r) as i32;
                let c_min = (ci - dist).max(0);
                let c_max = (ci + dist).min(cols as i32 - 1);
                for cc in c_min..=c_max {
                    if has_bit(state.black, rr as i32, cc, cols, rows) {
                        free = false;
                        break 'fw;
                    }
                }
            }
            let f = if free { 1.5 } else { 1.0 };

            // g: isolation — no friendly neighbour behind/beside
            let has_neighbour = has_bit(state.white, ri - 1, ci - 1, cols, rows)
                || has_bit(state.white, ri - 1, ci + 1, cols, rows)
                || has_bit(state.white, ri, ci - 1, cols, rows)
                || has_bit(state.white, ri, ci + 1, cols, rows);
            let g = if has_neighbour { 1.0 } else { 0.8 };

            v_white += a * (1.0 + 0.3 * d as f32) * k * f * g;

            wb &= wb - 1;
        }
    }

    // --- Breakthrough threat for Black (pieces on row 1 that can reach row 0) ---
    let mut v_black: f32 = 0.0;
    {
        let threat_row: u8 = 1;
        let target_row: u8 = 0;
        let mut bb = state.black;
        while bb != 0 {
            let sq = bb.trailing_zeros() as u8;
            let r = sq / cols;
            let c = sq % cols;
            if r == threat_row {
                let occupied = state.white | state.black;
                let straight_sq = target_row * cols + c;
                let can_straight = occupied & (1u64 << straight_sq) == 0;
                let can_diag_l =
                    c > 0 && (state.black & (1u64 << (target_row * cols + c - 1))) == 0;
                let can_diag_r = c < cols - 1
                    && (state.black & (1u64 << (target_row * cols + c + 1))) == 0;
                if can_straight || can_diag_l || can_diag_r {
                    v_black += 200.0;
                }
            }
            bb &= bb - 1;
        }
    }

    // --- Per-piece scoring for Black (mirrored direction) ---
    {
        let mut bb = state.black;
        while bb != 0 {
            let sq = bb.trailing_zeros() as u8;
            let r = sq / cols;
            let c = sq % cols;
            let ri = r as i32;
            let ci = c as i32;

            // a: advancement weight (mirrored row)
            let eff_row = (rows - 1 - r) as usize;
            let a = if eff_row < ADVANCEMENT_WEIGHTS.len() {
                ADVANCEMENT_WEIGHTS[eff_row]
            } else {
                *ADVANCEMENT_WEIGHTS.last().unwrap()
            };

            // d: defenders behind Black piece
            let mut d: i32 = 0;
            if has_bit(state.black, ri + 1, ci - 1, cols, rows) {
                d += 1;
            }
            if has_bit(state.black, ri + 1, ci + 1, cols, rows) {
                d += 1;
            }

            // k: centrality
            let k: f32 = if cols == 8 {
                match c {
                    3 | 4 => 1.15,
                    2 | 5 => 1.05,
                    _ => 1.0,
                }
            } else {
                1.0
            };

            // f: free path downward — no White piece in expanding triangle
            let mut free = true;
            'fb: for rr in (0..r).rev() {
                let dist = (r - rr) as i32;
                let c_min = (ci - dist).max(0);
                let c_max = (ci + dist).min(cols as i32 - 1);
                for cc in c_min..=c_max {
                    if has_bit(state.white, rr as i32, cc, cols, rows) {
                        free = false;
                        break 'fb;
                    }
                }
            }
            let f = if free { 1.5 } else { 1.0 };

            // g: isolation
            let has_neighbour = has_bit(state.black, ri + 1, ci - 1, cols, rows)
                || has_bit(state.black, ri + 1, ci + 1, cols, rows)
                || has_bit(state.black, ri, ci - 1, cols, rows)
                || has_bit(state.black, ri, ci + 1, cols, rows);
            let g = if has_neighbour { 1.0 } else { 0.8 };

            v_black += a * (1.0 + 0.3 * d as f32) * k * f * g;

            bb &= bb - 1;
        }
    }

    // --- Global factors ---
    let mut v = v_white - v_black;

    // Mobility (Algorithm 1, line 17)
    let white_moves = count_legal_moves(state, true) as f32;
    let black_moves = count_legal_moves(state, false) as f32;
    v += 0.3 * (white_moves - black_moves);

    // Material advantage (Algorithm 1, line 18)
    let white_count = state.white.count_ones() as f32;
    let black_count = state.black.count_ones() as f32;
    v += 2.0 * (white_count - black_count);

    if for_white { v } else { -v }
}

/// Algorithm 2: Move ordering heuristic.
/// Higher π ⇒ search this move first.
pub(crate) fn move_ordering_score(state: &GameState, from: u8, to: u8) -> i32 {
    let rows = state.rows;
    let cols = state.cols;
    let to_row = to / cols;
    let to_col = to % cols;

    // Winning move — reaches opponent's last row
    if state.white_to_move && to_row == rows - 1 {
        return 1000;
    }
    if !state.white_to_move && to_row == 0 {
        return 1000;
    }

    let mut pi: i32 = 0;

    // Capture bonus
    let opponent = if state.white_to_move {
        state.black
    } else {
        state.white
    };
    let is_capture = opponent & (1u64 << to) != 0;
    if is_capture {
        pi += 50;
        let captured_adv = if state.white_to_move {
            (rows - 1 - to_row) as i32 // Black piece advancement
        } else {
            to_row as i32 // White piece advancement
        };
        pi += 5 * captured_adv;
    }

    // Defended after move
    let own = if state.white_to_move {
        state.white
    } else {
        state.black
    };
    let own_after = own & !(1u64 << from); // piece left 'from'
    let defended = if state.white_to_move {
        has_bit(own_after, to_row as i32 - 1, to_col as i32 - 1, cols, rows)
            || has_bit(own_after, to_row as i32 - 1, to_col as i32 + 1, cols, rows)
    } else {
        has_bit(own_after, to_row as i32 + 1, to_col as i32 - 1, cols, rows)
            || has_bit(own_after, to_row as i32 + 1, to_col as i32 + 1, cols, rows)
    };
    if defended {
        pi += 10;
    }

    // Forward advancement
    let adv = if state.white_to_move {
        to_row as i32
    } else {
        (rows - 1 - to_row) as i32
    };
    pi += 2 * adv;

    pi
}

/// Algorithm 3: Minimax with alpha-beta pruning (negamax formulation).
fn alpha_beta(
    state: &GameState,
    depth: i32,
    mut alpha: f32,
    beta: f32,
    for_white: bool,
) -> f32 {
    if let Some(winner) = state.winner_raw() {
        return if winner == for_white {
            f32::INFINITY
        } else {
            f32::NEG_INFINITY
        };
    }
    if depth == 0 {
        return evaluate(state, for_white);
    }

    let moves = state.generate_moves_raw();

    // Sort by move ordering heuristic (Algorithm 2) — descending
    let mut scored: Vec<(i32, u8, u8)> = moves
        .iter()
        .map(|&(f, t)| (move_ordering_score(state, f, t), f, t))
        .collect();
    scored.sort_unstable_by(|a, b| b.0.cmp(&a.0));

    let mut best = f32::NEG_INFINITY;

    for (_, from, to) in scored {
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

/// Algorithm 4: Best-move selection — entry point for the heuristic agent.
#[pyclass]
pub struct HeuristicAgent {
    depth: i32,
}

#[pymethods]
impl HeuristicAgent {
    #[new]
    #[pyo3(signature = (depth = 5, weights = None))]
    pub fn new(depth: i32, weights: Option<HashMap<String, f32>>) -> Self {
        let _ = weights;
        HeuristicAgent { depth }
    }

    pub fn select_move(&self, state: &GameState) -> (u8, u8) {
        let for_white = state.white_to_move;
        let moves = state.generate_moves_raw();
        assert!(!moves.is_empty(), "select_move called on terminal state");

        // Sort root moves by Algorithm 2
        let mut scored: Vec<(i32, u8, u8)> = moves
            .iter()
            .map(|&(f, t)| (move_ordering_score(state, f, t), f, t))
            .collect();
        scored.sort_unstable_by(|a, b| b.0.cmp(&a.0));

        let mut best_move = (scored[0].1, scored[0].2);
        let mut best_score = f32::NEG_INFINITY;

        for &(_, from, to) in &scored {
            let child = state.apply_raw(from, to);
            let score = -alpha_beta(
                &child,
                self.depth - 1,
                f32::NEG_INFINITY,
                f32::INFINITY,
                !for_white,
            );
            if score > best_score {
                best_score = score;
                best_move = (from, to);
            }
        }
        best_move
    }
}
