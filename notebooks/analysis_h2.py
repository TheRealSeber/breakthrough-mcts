"""H2: Progressive Bias vs UCT — win-rate scaling with iteration budget."""
import sys
from pathlib import Path

sys.path.insert(0, "notebooks")
from shared_utils import load_games, aggregate_winrate_by_iters, save_fig
import matplotlib.pyplot as plt

GAMES = Path("results/h2_pb_vs_uct/games.jsonl")
if not GAMES.exists():
    print(f"No data at {GAMES}; run experiments/run_h2.py first.")
    sys.exit(0)

df = load_games(GAMES)
print(f"Loaded {len(df)} games")

uct_summary = aggregate_winrate_by_iters(df, "uct")
pb_summary = aggregate_winrate_by_iters(df, "pb")

fig, ax = plt.subplots(figsize=(8, 5))
for label, summary, color in [("UCT", uct_summary, "tab:blue"), ("Progressive Bias", pb_summary, "tab:green")]:
    err_lo = summary["rate"] - summary["ci_low"]
    err_hi = summary["ci_high"] - summary["rate"]
    ax.errorbar(
        summary["iterations"], summary["rate"],
        yerr=[err_lo, err_hi],
        label=label, color=color, marker="o", capsize=5,
    )

ax.axhline(0.5, color="gray", linestyle="--", alpha=0.5, label="50% (losowy)")
ax.set_xscale("log")
ax.set_xlabel("Liczba iteracji MCTS")
ax.set_ylabel("Odsetek wygranych (95% CI Wilsona)")
ax.set_title("H2: Progressive Bias vs UCT — skalowanie z budżetem iteracji")
ax.legend()
save_fig("h2_pb_vs_uct")
