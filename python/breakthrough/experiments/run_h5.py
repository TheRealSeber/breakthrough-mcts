"""H5: Exploration constant c tuning — round-robin among c values."""
from pathlib import Path
from breakthrough.experiments.harness import Experiment, AgentConfig, run_experiment

if __name__ == "__main__":
    agents = []
    for c in [0.5, 1.0, 1.5, 2.0, 3.0]:
        agents.append(AgentConfig(type="uct", iterations=10000, c=c))

    exp = Experiment(
        name="h5_c_tuning",
        agents=agents,
        n_games_per_pair=100,
        master_seed=46,
        output_dir=Path("results"),
        board_rows=8,
        board_cols=8,
    )
    run_experiment(exp)
