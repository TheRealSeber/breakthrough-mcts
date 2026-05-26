"""H1: RAVE vs UCT at varying iteration budgets."""
from pathlib import Path
from breakthrough.experiments.harness import Experiment, AgentConfig, run_experiment

if __name__ == "__main__":
    agents = []
    for iters in [5000, 10000, 50000, 100000]:
        agents.append(AgentConfig(type="uct", iterations=iters))
        agents.append(AgentConfig(type="rave", iterations=iters, rave_k=0.01))

    exp = Experiment(
        name="h1_rave_vs_uct",
        agents=agents,
        n_games_per_pair=100,
        master_seed=42,
        output_dir=Path("results"),
        board_rows=8,
        board_cols=8,
    )
    run_experiment(exp)
