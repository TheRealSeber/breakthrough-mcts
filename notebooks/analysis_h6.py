"""H6: Decision time analysis by move number."""
import sys
from pathlib import Path

sys.path.insert(0, "notebooks")
from shared_utils import load_games, extract_move_times, save_fig
import matplotlib.pyplot as plt
import numpy as np

GAMES = Path("results/h6_decision_time/games.jsonl")
if not GAMES.exists():
    print(f"No data at {GAMES}; run experiments/run_h6.py first.")
    sys.exit(0)

df = load_games(GAMES)
print(f"Loaded {len(df)} games")

# Extract per-move timing data
mt = extract_move_times(df)
if mt.empty:
    print("No move_times data found.")
    sys.exit(0)

# Add iteration budget info per game
game_iters = {}
for _, row in df.iterrows():
    gid = row.get("game_id")
    # Use white agent's iterations as the budget label
    iters = row["agent_white"].get("iterations", 0)
    game_iters[gid] = iters

mt["iterations"] = mt["game_id"].map(game_iters)

# Summary stats
print("\nMean decision time by iteration budget:")
for iters in sorted(mt["iterations"].unique()):
    subset = mt[mt["iterations"] == iters]
    mean_t = subset["decision_time"].mean()
    std_t = subset["decision_time"].std()
    print(f"  {int(iters):>6d} iters: mean={mean_t:.4f}s, std={std_t:.4f}s")

# Plot: decision time vs move number, grouped by budget
fig, ax = plt.subplots(figsize=(10, 5))

for iters in sorted(mt["iterations"].unique()):
    subset = mt[mt["iterations"] == iters]
    grouped = subset.groupby("move_number")["decision_time"].agg(["mean", "std"])
    # Smooth: only plot up to a reasonable move number
    grouped = grouped[grouped.index <= 100]
    ax.plot(grouped.index, grouped["mean"], label=f"{int(iters)} iters")
    ax.fill_between(
        grouped.index,
        grouped["mean"] - grouped["std"],
        grouped["mean"] + grouped["std"],
        alpha=0.15,
    )

ax.set_xlabel("Numer ruchu")
ax.set_ylabel("Czas decyzji [s]")
ax.set_title("H6: Czas decyzji MCTS w funkcji numeru ruchu")
ax.legend()
save_fig("h6_decision_time")
