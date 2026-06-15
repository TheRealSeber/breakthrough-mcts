"""H3: HeuristicAgent vs UCT — cross-over exists at some iteration budget."""
from pathlib import Path
from breakthrough.experiments.harness import Experiment, AgentConfig, run_experiment

if __name__ == "__main__":
    agents = [AgentConfig(type="heuristic", depth=5)]
    for iters in [500, 1000, 5000, 10000, 50000, 100000, 200000, 300000, 500000]:
        agents.append(AgentConfig(type="uct", iterations=iters))

    exp = Experiment(
        name="h3_heuristic_vs_uct",
        agents=agents,
        n_games_per_pair=100,
        master_seed=44,
        output_dir=Path("results"),
        board_rows=8,
        board_cols=8,
    )
    run_experiment(exp)
