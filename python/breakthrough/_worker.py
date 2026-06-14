"""Out-of-process move computation for the GUI."""
from breakthrough import GameState
from breakthrough.agents import make_agent


def compute_move(cfg, rows, cols, moves, seed):
    state = GameState(rows, cols)
    for frm, to in moves:
        state = state.apply(frm, to)
    agent = make_agent(cfg, seed=seed)
    return tuple(agent.select_move(state))
