"""H5: Exploration constant c tuning — heatmap of win rates."""
import sys
from pathlib import Path

sys.path.insert(0, "notebooks")
from shared_utils import load_games, wilson_ci, significance_test, cohens_h, save_fig
import matplotlib.pyplot as plt
import numpy as np

GAMES = Path("results/h5_c_tuning/games.jsonl")
if not GAMES.exists():
    print(f"No data at {GAMES}; run experiments/run_h5.py first.")
    sys.exit(0)

df = load_games(GAMES)
print(f"Loaded {len(df)} games")

# Collect all c values
c_values = set()
for _, row in df.iterrows():
    c_values.add(row["agent_white"].get("c"))
    c_values.add(row["agent_black"].get("c"))
c_values = sorted(c_values)
n_c = len(c_values)
c_idx = {c: i for i, c in enumerate(c_values)}

# Build win-rate matrix: matrix[i][j] = win rate of c_i as white vs c_j as black
matrix = np.full((n_c, n_c), np.nan)
for i, c_w in enumerate(c_values):
    for j, c_b in enumerate(c_values):
        if i == j:
            continue
        wins = 0
        n = 0
        for _, row in df.iterrows():
            if (row["agent_white"].get("c") == c_w and
                    row["agent_black"].get("c") == c_b):
                n += 1
                if row["winner"] == "white":
                    wins += 1
        if n > 0:
            rate, _, _ = wilson_ci(wins, n)
            matrix[i, j] = rate

# Overall win rate per c value (across both colors)
print("\nOverall win rates by c value:")
overall_rates = []
for c in c_values:
    wins = 0
    n = 0
    for _, row in df.iterrows():
        if row["agent_white"].get("c") == c:
            n += 1
            if row["winner"] == "white":
                wins += 1
        if row["agent_black"].get("c") == c:
            n += 1
            if row["winner"] == "black":
                wins += 1
    if n > 0:
        rate, lo, hi = wilson_ci(wins, n)
        p_val = significance_test(wins, n)
        effect = cohens_h(rate)
        overall_rates.append(rate)
        print(f"  c={c:.1f}: rate={rate:.3f} CI=[{lo:.3f}, {hi:.3f}] "
              f"p={p_val:.4f} h={effect:.3f} (n={n})")
    else:
        overall_rates.append(0.5)

# Heatmap
fig, ax = plt.subplots(figsize=(7, 6))
c_labels = [f"{c:.1f}" for c in c_values]
im = ax.imshow(matrix, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
ax.set_xticks(range(n_c))
ax.set_xticklabels(c_labels)
ax.set_yticks(range(n_c))
ax.set_yticklabels(c_labels)
ax.set_xlabel("c przeciwnika")
ax.set_ylabel("c gracza (biały)")
ax.set_title("H5: Macierz win rate — stała eksploracji c")
for i in range(n_c):
    for j in range(n_c):
        if not np.isnan(matrix[i, j]):
            ax.text(j, i, f"{matrix[i, j]:.2f}", ha="center", va="center", fontsize=9)
plt.colorbar(im, ax=ax, label="Win rate białego")
save_fig("h5_c_heatmap")

# Bar chart of overall rates
fig, ax = plt.subplots(figsize=(7, 4))
ax.bar(c_labels, overall_rates, color="tab:cyan")
ax.axhline(0.5, color="gray", linestyle="--", alpha=0.5)
ax.set_xlabel("Stała eksploracji c")
ax.set_ylabel("Ogólny win rate (95% CI)")
ax.set_title("H5: Win rate vs stała eksploracji c")
ax.set_ylim(0, 1)
save_fig("h5_c_bar")
