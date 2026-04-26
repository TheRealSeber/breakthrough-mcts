"""H3: HeuristicAgent vs UCT — cross-over exists at some iteration budget."""
from pathlib import Path
from breakthrough.experiments.harness import Experiment, AgentConfig, run_experiment

if __name__ == "__main__":
    agents = [AgentConfig(type="heuristic", depth=5)]
    for iters in [200, 500, 1000, 5000, 10000]:
        agents.append(AgentConfig(type="uct", iterations=iters))

    exp = Experiment(
        name="h3_heuristic_vs_uct",
        agents=agents,
        n_games_per_pair=60,
        master_seed=44,
        output_dir=Path("results"),
    )
    run_experiment(exp)
