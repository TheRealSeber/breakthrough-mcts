from __future__ import annotations
from copy import deepcopy

class RefGameState:
    """Pure-Python Breakthrough implementation. Clarity over performance."""

    def __init__(self, rows: int = 8, cols: int = 8):
        self.rows = rows
        self.cols = cols
        self.board: list[list[str | None]] = [[None] * cols for _ in range(rows)]
        for c in range(cols):
            self.board[0][c] = 'W'
            self.board[1][c] = 'W'
            self.board[rows - 2][c] = 'B'
            self.board[rows - 1][c] = 'B'
        self.white_to_move = True
        self.move_count = 0

    def current_player(self) -> str:
        return 'white' if self.white_to_move else 'black'

    def legal_moves(self) -> list[tuple[int, int]]:
        """Returns list of (from_sq, to_sq) using same encoding as Rust."""
        moves = []
        player = 'W' if self.white_to_move else 'B'
        dr = 1 if self.white_to_move else -1

        for r in range(self.rows):
            for c in range(self.cols):
                if self.board[r][c] != player:
                    continue
                from_sq = r * self.cols + c
                nr = r + dr
                if not (0 <= nr < self.rows):
                    continue
                # Straight: must be empty
                if self.board[nr][c] is None:
                    moves.append((from_sq, nr * self.cols + c))
                # Diagonal left
                if c > 0:
                    target = self.board[nr][c - 1]
                    if target is None or target != player:
                        moves.append((from_sq, nr * self.cols + (c - 1)))
                # Diagonal right
                if c < self.cols - 1:
                    target = self.board[nr][c + 1]
                    if target is None or target != player:
                        moves.append((from_sq, nr * self.cols + (c + 1)))
        return moves

    def apply(self, from_sq: int, to_sq: int) -> RefGameState:
        new = deepcopy(self)
        fr, fc = divmod(from_sq, self.cols)
        tr, tc = divmod(to_sq, self.cols)
        piece = new.board[fr][fc]
        new.board[fr][fc] = None
        new.board[tr][tc] = piece
        new.white_to_move = not self.white_to_move
        new.move_count += 1
        return new

    def winner(self) -> str | None:
        # White wins by reaching last row
        if any(self.board[self.rows - 1][c] == 'W' for c in range(self.cols)):
            return 'white'
        # Black wins by reaching row 0
        if any(self.board[0][c] == 'B' for c in range(self.cols)):
            return 'black'
        # Win by capturing all opponent pieces
        whites = sum(1 for r in range(self.rows) for c in range(self.cols) if self.board[r][c] == 'W')
        blacks = sum(1 for r in range(self.rows) for c in range(self.cols) if self.board[r][c] == 'B')
        if blacks == 0:
            return 'white'
        if whites == 0:
            return 'black'
        # Win by no legal moves
        if not self.legal_moves():
            return 'black' if self.white_to_move else 'white'
        return None

    def is_terminal(self) -> bool:
        return self.winner() is not None

    def to_string(self) -> str:
        rows = []
        for r in range(self.rows):
            rows.append(''.join(cell or '.' for cell in self.board[r]))
        rows.append('W' if self.white_to_move else 'B')
        return '\n'.join(rows)
