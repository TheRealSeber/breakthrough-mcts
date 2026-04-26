"""H2: Progressive Bias vs UCT at varying iteration budgets."""
from pathlib import Path
from breakthrough.experiments.harness import Experiment, AgentConfig, run_experiment

if __name__ == "__main__":
    agents = []
    for iters in [1000, 5000, 10000]:
        agents.append(AgentConfig(type="uct", iterations=iters))
        agents.append(AgentConfig(type="pb", iterations=iters, bias_weight=1.0))

    exp = Experiment(
        name="h2_pb_vs_uct",
        agents=agents,
        n_games_per_pair=60,
        master_seed=43,
        output_dir=Path("results"),
    )
    run_experiment(exp)
