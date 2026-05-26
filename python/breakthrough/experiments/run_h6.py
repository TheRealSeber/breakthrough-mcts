"""H6: Decision time analysis by move number."""
from pathlib import Path
from breakthrough.experiments.harness import Experiment, AgentConfig, run_experiment

if __name__ == "__main__":
    agents = []
    for iters in [5000, 10000, 50000]:
        agents.append(AgentConfig(type="uct", iterations=iters))

    exp = Experiment(
        name="h6_decision_time",
        agents=agents,
        n_games_per_pair=100,
        master_seed=47,
        output_dir=Path("results"),
        board_rows=8,
        board_cols=8,
    )
    run_experiment(exp)
