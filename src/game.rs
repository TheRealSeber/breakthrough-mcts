use pyo3::prelude::*;
use rand::RngCore;
use rand::SeedableRng;
use rand_xoshiro::Xoshiro256PlusPlus;
use std::sync::Arc;

#[pyclass(frozen)]
#[derive(Clone)]
pub struct GameState {
    pub white: u64,
    pub black: u64,
    pub rows: u8,
    pub cols: u8,
    pub white_to_move: bool,
    pub move_count: u32,
    pub hash: u64,
    pub left_edge: u64,
    pub right_edge: u64,
    pub board_mask: u64,
    pub top_row: u64,
    pub bot_row: u64,
    zobrist: Arc<Vec<u64>>,
}

impl GameState {
    fn make_masks(rows: u8, cols: u8) -> (u64, u64, u64, u64, u64) {
        let n = (rows * cols) as u32;
        let board_mask = if n == 64 { u64::MAX } else { (1u64 << n) - 1 };
        let mut left_edge = 0u64;
        let mut right_edge = 0u64;
        for r in 0..rows {
            left_edge |= 1u64 << (r * cols);
            right_edge |= 1u64 << (r * cols + cols - 1);
        }
        let mut top_row = 0u64;
        let mut bot_row = 0u64;
        for c in 0..cols {
            top_row |= 1u64 << ((rows - 1) * cols + c);
            bot_row |= 1u64 << c;
        }
        (left_edge, right_edge, board_mask, top_row, bot_row)
    }

    fn make_zobrist(rows: u8, cols: u8) -> Arc<Vec<u64>> {
        let n = (rows * cols) as usize;
        let mut rng = Xoshiro256PlusPlus::seed_from_u64(0xdeadbeef_cafebabe);
        let table: Vec<u64> = (0..2 * n).map(|_| rng.next_u64()).collect();
        Arc::new(table)
    }

    fn compute_hash(white: u64, black: u64, zobrist: &[u64], n: usize) -> u64 {
        let mut h = 0u64;
        let mut w = white;
        while w != 0 {
            h ^= zobrist[w.trailing_zeros() as usize];
            w &= w - 1;
        }
        let mut b = black;
        while b != 0 {
            h ^= zobrist[n + b.trailing_zeros() as usize];
            b &= b - 1;
        }
        h
    }

    pub fn generate_moves_raw(&self) -> Vec<(u8, u8)> {
        let cols = self.cols as u32;
        let occupied = self.white | self.black;
        let empty = !occupied & self.board_mask;
        let mut moves = Vec::with_capacity(32);

        if self.white_to_move {
            let straight = (self.white << cols) & empty & self.board_mask;
            let diag_l = ((self.white & !self.left_edge) << (cols - 1))
                & (empty | self.black) & self.board_mask;
            let diag_r = ((self.white & !self.right_edge) << (cols + 1))
                & (empty | self.black) & self.board_mask;
            extract_moves(straight, -(cols as i32), &mut moves);
            extract_moves(diag_l, -(cols as i32 - 1), &mut moves);
            extract_moves(diag_r, -(cols as i32 + 1), &mut moves);
        } else {
            let straight = (self.black >> cols) & empty;
            let diag_l = ((self.black & !self.left_edge) >> (cols + 1)) & (empty | self.white);
            let diag_r = ((self.black & !self.right_edge) >> (cols - 1)) & (empty | self.white);
            extract_moves(straight, cols as i32, &mut moves);
            extract_moves(diag_l, cols as i32 + 1, &mut moves);
            extract_moves(diag_r, cols as i32 - 1, &mut moves);
        }
        moves
    }

    pub fn apply_raw(&self, from: u8, to: u8) -> GameState {
        let from_bit = 1u64 << from;
        let to_bit = 1u64 << to;
        let (new_white, new_black) = if self.white_to_move {
            ((self.white & !from_bit) | to_bit, self.black & !to_bit)
        } else {
            (self.white & !to_bit, (self.black & !from_bit) | to_bit)
        };
        let n = (self.rows * self.cols) as usize;
        let hash = Self::compute_hash(new_white, new_black, &self.zobrist, n);
        GameState {
            white: new_white,
            black: new_black,
            white_to_move: !self.white_to_move,
            move_count: self.move_count + 1,
            hash,
            zobrist: Arc::clone(&self.zobrist),
            ..*self
        }
    }

    pub fn winner_raw(&self) -> Option<bool> {
        if self.white & self.top_row != 0 { return Some(true); }
        if self.black & self.bot_row != 0 { return Some(false); }
        if self.black == 0 { return Some(true); }
        if self.white == 0 { return Some(false); }
        if self.generate_moves_raw().is_empty() {
            return Some(!self.white_to_move);
        }
        None
    }
}

fn extract_moves(mut bb: u64, offset: i32, out: &mut Vec<(u8, u8)>) {
    while bb != 0 {
        let to = bb.trailing_zeros() as i32;
        let from = to + offset;
        out.push((from as u8, to as u8));
        bb &= bb - 1;
    }
}

#[pymethods]
impl GameState {
    #[new]
    #[pyo3(signature = (rows=6, cols=6))]
    pub fn new(rows: u8, cols: u8) -> Self {
        assert!(rows * cols <= 64, "board too large for u64 bitboard");
        let (left_edge, right_edge, board_mask, top_row, bot_row) = Self::make_masks(rows, cols);
        let zobrist = Self::make_zobrist(rows, cols);

        let mut white = 0u64;
        let mut black = 0u64;
        for c in 0..cols {
            white |= 1u64 << c;
            white |= 1u64 << (cols + c);
            black |= 1u64 << ((rows - 2) * cols + c);
            black |= 1u64 << ((rows - 1) * cols + c);
        }
        let n = (rows * cols) as usize;
        let hash = Self::compute_hash(white, black, &zobrist, n);
        GameState {
            white, black, rows, cols,
            white_to_move: true,
            move_count: 0,
            hash,
            left_edge, right_edge, board_mask, top_row, bot_row,
            zobrist,
        }
    }

    pub fn legal_moves(&self) -> Vec<(u8, u8)> {
        self.generate_moves_raw()
    }

    pub fn apply(&self, from_sq: u8, to_sq: u8) -> Self {
        self.apply_raw(from_sq, to_sq)
    }

    pub fn is_terminal(&self) -> bool {
        self.winner_raw().is_some()
    }

    pub fn winner(&self) -> Option<&'static str> {
        self.winner_raw().map(|w| if w { "white" } else { "black" })
    }

    pub fn current_player(&self) -> &'static str {
        if self.white_to_move { "white" } else { "black" }
    }

    pub fn get_move_count(&self) -> u32 {
        self.move_count
    }

    pub fn zobrist_hash(&self) -> u64 {
        self.hash
    }

    pub fn to_string(&self) -> String {
        let mut s = String::new();
        for r in 0..self.rows {
            for c in 0..self.cols {
                let sq = r * self.cols + c;
                let ch = if self.white & (1u64 << sq) != 0 { 'W' }
                         else if self.black & (1u64 << sq) != 0 { 'B' }
                         else { '.' };
                s.push(ch);
            }
            s.push('\n');
        }
        s.push(if self.white_to_move { 'W' } else { 'B' });
        s
    }

    #[staticmethod]
    pub fn from_string(s: &str, rows: u8, cols: u8) -> PyResult<Self> {
        let mut base = GameState::new(rows, cols);
        base.white = 0;
        base.black = 0;
        let lines: Vec<&str> = s.lines().collect();
        for (r, line) in lines[..rows as usize].iter().enumerate() {
            for (c, ch) in line.chars().enumerate() {
                let sq = (r as u8) * cols + (c as u8);
                match ch {
                    'W' => base.white |= 1u64 << sq,
                    'B' => base.black |= 1u64 << sq,
                    _ => {}
                }
            }
        }
        base.white_to_move = lines.last().map(|l| *l == "W").unwrap_or(true);
        let n = (rows * cols) as usize;
        base.hash = Self::compute_hash(base.white, base.black, &base.zobrist, n);
        Ok(base)
    }

    fn __repr__(&self) -> String {
        self.to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn start_position_has_legal_moves() {
        let g = GameState::new(6, 6);
        let moves = g.generate_moves_raw();
        assert!(!moves.is_empty(), "should have legal moves at start");
        // Hand-counted: row 1 (advancing front) pieces only — row 0 pieces are blocked
        // by row 1 own pieces both straight and diagonally.
        // col 0: straight + diag_right = 2 moves
        // col 1-4: straight + diag_left + diag_right = 3 each (4 pieces × 3 = 12)
        // col 5: straight + diag_left = 2 moves
        // Total = 2 + 12 + 2 = 16 moves
        assert_eq!(moves.len(), 16, "expected 16 moves at start");
    }

    #[test]
    fn white_wins_by_reaching_top_row() {
        let mut g = GameState::new(6, 6);
        g.white = 1u64 << (4 * 6);
        g.black = 1u64 << (3 * 6 + 3);
        g.white_to_move = true;
        let g2 = g.apply_raw(24, 30);
        assert_eq!(g2.winner_raw(), Some(true), "white should win by reaching row 5");
    }

    #[test]
    fn black_wins_by_reaching_bot_row() {
        let mut g = GameState::new(6, 6);
        g.white = 1u64 << (2 * 6 + 3);
        g.black = 1u64 << 6;
        g.white_to_move = false;
        let g2 = g.apply_raw(6, 0);
        assert_eq!(g2.winner_raw(), Some(false), "black should win by reaching row 0");
    }

    #[test]
    fn serialization_round_trip() {
        let g = GameState::new(6, 6);
        let s = g.to_string();
        let g2 = GameState::from_string(&s, 6, 6).unwrap();
        assert_eq!(g.white, g2.white);
        assert_eq!(g.black, g2.black);
        assert_eq!(g.white_to_move, g2.white_to_move);
    }

    #[test]
    fn capture_removes_opponent_piece() {
        let mut g = GameState::new(6, 6);
        g.white = 1u64 << (2 * 6 + 2); // sq 14
        g.black = 1u64 << (3 * 6 + 3); // sq 21
        g.white_to_move = true;
        let g2 = g.apply_raw(14, 21);
        assert_eq!(g2.white & (1u64 << 21), 1u64 << 21, "white should be at sq 21");
        assert_eq!(g2.black, 0, "black piece should be captured");
    }

    #[test]
    fn capture_all_opponent_pieces_wins() {
        let mut g = GameState::new(6, 6);
        g.white = 1u64 << (2 * 6 + 2);
        g.black = 1u64 << (3 * 6 + 3);
        g.white_to_move = true;
        let g2 = g.apply_raw(14, 21);
        assert_eq!(g2.winner_raw(), Some(true), "capturing last black piece should win");
    }
}
