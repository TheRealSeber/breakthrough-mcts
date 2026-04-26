"""H3 extended: heurystyka vs UCT przy znacznie większych budżetach.

Przy budżetach do 10000 heurystyka (alpha-beta d=5) ogrywała UCT 98-100%.
Aby znaleźć punkt krzyżowania z hipotezy H3, dodajemy budżety 20k, 50k, 100k.

UWAGA: UCT(100000) jest ~20x wolniejsze niż UCT(5000). Spodziewany czas
działania (60 gier × 4 budżety, 8 rdzeni równolegle): ~1-2 godziny.
"""
from pathlib import Path
from breakthrough.experiments.harness import Experiment, AgentConfig, run_experiment

if __name__ == "__main__":
    agents = [AgentConfig(type="heuristic", depth=5)]
    for iters in [20000, 50000, 100000]:
        agents.append(AgentConfig(type="uct", iterations=iters))

    exp = Experiment(
        name="h3_heuristic_vs_uct_extended",
        agents=agents,
        n_games_per_pair=60,
        master_seed=144,
        output_dir=Path("results"),
    )
    run_experiment(exp)
