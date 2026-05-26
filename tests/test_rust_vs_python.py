"""
Cross-validation gate: Rust and Python implementations must agree on
legal moves, winner, is_terminal, and board representation for 1000
random games. Run this before collecting any experiment data.
"""
import random
from breakthrough import GameState
from breakthrough.reference_game import RefGameState


def test_cross_validation():
    rng = random.Random(42)

    for game_num in range(1000):
        rust = GameState(8, 8)
        ref = RefGameState(8, 8)

        for _ in range(200):  # max moves per game
            rust_moves = sorted(rust.legal_moves())
            ref_moves = sorted(ref.legal_moves())

            assert rust_moves == ref_moves, (
                f"Game {game_num}: legal_moves mismatch at move {rust.get_move_count()}\n"
                f"Rust: {rust_moves}\nRef:  {ref_moves}\nRust board:\n{rust}\nRef board:\n{ref.to_string()}"
            )
            assert rust.is_terminal() == ref.is_terminal(), (
                f"Game {game_num}: is_terminal mismatch at move {rust.get_move_count()}"
            )
            assert rust.winner() == ref.winner(), (
                f"Game {game_num}: winner mismatch: rust={rust.winner()} ref={ref.winner()}"
            )
            assert rust.to_string() == ref.to_string(), (
                f"Game {game_num}: to_string mismatch at move {rust.get_move_count()}"
            )

            if rust.is_terminal():
                break

            mv = rng.choice(rust_moves)
            rust = rust.apply(mv[0], mv[1])
            ref = ref.apply(mv[0], mv[1])
