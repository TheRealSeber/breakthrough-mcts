"""H4: First-player (white) advantage across board sizes 6x6, 6x8, 8x8."""
from pathlib import Path
from breakthrough.experiments.harness import Experiment, AgentConfig, run_experiment

if __name__ == "__main__":
    for rows, cols in [(6, 6), (6, 8), (8, 8)]:
        agents = [
            AgentConfig(type="uct", iterations=5000),
            AgentConfig(type="uct", iterations=5000),
        ]
        exp = Experiment(
            name=f"h4_first_player_{rows}x{cols}",
            agents=agents,
            n_games_per_pair=500,
            master_seed=45,
            output_dir=Path("results"),
            board_rows=rows,
            board_cols=cols,
        )
        run_experiment(exp)
