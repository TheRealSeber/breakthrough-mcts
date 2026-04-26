"""Thin Python wrappers + random agent for use by the harness and GUI."""
import random as _random
from breakthrough import (
    GameState,
    UctAgent,
    RaveAgent,
    ProgressiveBiasAgent,
    HeuristicAgent,
)


class RandomAgent:
    """Uniformly random move selector. Useful as a baseline opponent."""

    def __init__(self, seed: int | None = None):
        self._rng = _random.Random(seed)

    def select_move(self, state: GameState) -> tuple[int, int]:
        moves = state.legal_moves()
        return self._rng.choice(moves)


def make_agent(config: dict, seed: int | None = None):
    """Construct an agent from a config dict.

    Recognized types: 'random', 'uct', 'rave', 'pb', 'heuristic'.
    """
    t = config["type"]
    if t == "random":
        return RandomAgent(seed=seed)
    if t == "uct":
        return UctAgent(
            config.get("iterations", 1000),
            config.get("c", 1.4142135623730951),
            seed=seed,
        )
    if t == "rave":
        return RaveAgent(
            config.get("iterations", 1000),
            config.get("c", 1.4142135623730951),
            config.get("rave_k", 1000.0),
            seed=seed,
        )
    if t == "pb":
        return ProgressiveBiasAgent(
            config.get("iterations", 1000),
            config.get("c", 1.4142135623730951),
            config.get("bias_weight", 1.0),
            seed=seed,
        )
    if t == "heuristic":
        return HeuristicAgent(config.get("depth", 5))
    raise ValueError(f"Unknown agent type: {t}")
