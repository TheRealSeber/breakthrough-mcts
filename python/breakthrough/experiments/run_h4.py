"""H4: First-player (white) advantage on 8x8 board."""
from pathlib import Path
from breakthrough.experiments.harness import Experiment, AgentConfig, run_experiment

if __name__ == "__main__":
    agents = [
        AgentConfig(type="uct", iterations=5000),
        AgentConfig(type="uct", iterations=5000),
    ]
    exp = Experiment(
        name="h4_first_player_8x8",
        agents=agents,
        n_games_per_pair=100,
        master_seed=45,
        output_dir=Path("results"),
        board_rows=8,
        board_cols=8,
    )
    run_experiment(exp)
