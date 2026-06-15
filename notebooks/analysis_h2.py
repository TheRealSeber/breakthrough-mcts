"""H2: Progressive Bias vs UCT — win-rate scaling with iteration budget."""
import sys
from pathlib import Path

sys.path.insert(0, "notebooks")
from shared_utils import (
    load_games, aggregate_winrate_by_iters, game_length_stats, save_fig,
    style_winrate_axis, winrate_series, plot_game_length, PALETTE,
)
import matplotlib.pyplot as plt

GAMES = Path("results/h2_pb_vs_uct/games.jsonl")
if not GAMES.exists():
    print(f"No data at {GAMES}; run experiments/run_h2.py first.")
    sys.exit(0)

df = load_games(GAMES)
print(f"Loaded {len(df)} games")

uct_summary = aggregate_winrate_by_iters(df, "uct")
pb_summary = aggregate_winrate_by_iters(df, "pb")

for label, summary in [("UCT", uct_summary), ("PB", pb_summary)]:
    print(f"\n{label}:")
    for _, row in summary.iterrows():
        print(f"  iters={int(row['iterations']):>6d}: rate={row['rate']:.3f} "
              f"CI=[{row['ci_low']:.3f}, {row['ci_high']:.3f}] "
              f"p={row['p_value']:.4f} h={row['cohens_h']:.3f}")

fig, ax = plt.subplots(figsize=(8.5, 5.2))
for label, summary, color, marker in [
    ("UCT", uct_summary, PALETTE["uct"], "o"),
    ("Progressive Bias", pb_summary, PALETTE["pb"], "D"),
]:
    winrate_series(ax, summary["iterations"], summary["rate"],
                   summary["ci_low"], summary["ci_high"],
                   label=label, color=color, marker=marker,
                   annotate_last=True, significance=False, ci=False)

style_winrate_axis(ax, ylabel="Odsetek wygranych")
ax.set_xscale("log")
ax.set_xlabel("Liczba iteracji MCTS (skala log)")
ax.set_title("H2: Progressive Bias vs UCT — skalowanie z budżetem iteracji")
ax.legend(title="Algorytm", loc="upper left")
save_fig("h2_pb_vs_uct")

stats = game_length_stats(df)
print(f"\nGame length: median={stats['median']}, IQR={stats['iqr']:.1f}, mean={stats['mean']:.1f}")

plot_game_length(df, "h2_game_length", "H2: Rozkład długości partii",
                 PALETTE["pb"])
