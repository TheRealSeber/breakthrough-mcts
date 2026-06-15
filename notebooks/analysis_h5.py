"""H5: Exploration constant c tuning — heatmap of win rates."""
import sys
from pathlib import Path

sys.path.insert(0, "notebooks")
from shared_utils import (
    load_games, wilson_ci, significance_test, cohens_h, save_fig, PALETTE,
)
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

GAMES = Path("results/h5_c_tuning/games.jsonl")
if not GAMES.exists():
    print(f"No data at {GAMES}; run experiments/run_h5.py first.")
    sys.exit(0)

df = load_games(GAMES)
print(f"Loaded {len(df)} games")

c_values = set()
for _, row in df.iterrows():
    c_values.add(row["agent_white"].get("c"))
    c_values.add(row["agent_black"].get("c"))
c_values = sorted(c_values)
n_c = len(c_values)
c_idx = {c: i for i, c in enumerate(c_values)}

wins = np.zeros((n_c, n_c))
total = np.zeros((n_c, n_c))
for _, row in df.iterrows():
    iw, ib = c_idx[row["agent_white"].get("c")], c_idx[row["agent_black"].get("c")]
    total[iw, ib] += 1
    total[ib, iw] += 1
    if row["winner"] == "white":
        wins[iw, ib] += 1
    elif row["winner"] == "black":
        wins[ib, iw] += 1
with np.errstate(invalid="ignore", divide="ignore"):
    matrix = np.where(total > 0, wins / total, np.nan)

print("\nOverall win rates by c value:")
overall_rates, overall_lo, overall_hi = [], [], []
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
        overall_lo.append(lo)
        overall_hi.append(hi)
        print(f"  c={c:.1f}: rate={rate:.3f} CI=[{lo:.3f}, {hi:.3f}] "
              f"p={p_val:.4f} h={effect:.3f} (n={n})")
    else:
        overall_rates.append(0.5)
        overall_lo.append(0.5)
        overall_hi.append(0.5)

fig, ax = plt.subplots(figsize=(7.5, 6.2))
c_labels = [f"{c:.1f}" for c in c_values]
norm = mcolors.TwoSlopeNorm(vmin=0, vcenter=0.5, vmax=1)
masked = np.ma.masked_invalid(matrix)
cmap = plt.cm.RdBu_r.copy()
cmap.set_bad("#e8e8e8")
im = ax.imshow(masked, cmap=cmap, norm=norm, aspect="equal")
ax.set_xticks(range(n_c)); ax.set_xticklabels(c_labels)
ax.set_yticks(range(n_c)); ax.set_yticklabels(c_labels)
ax.set_xlabel("c przeciwnika (kolumna)")
ax.set_ylabel("c gracza (wiersz)")
ax.set_title("H5: Bezpośrednie pojedynki — odsetek wygranych\n"
             "(wiersz vs kolumna; czerwony = wiersz wygrywa)")
for i in range(n_c):
    for j in range(n_c):
        if not np.ma.is_masked(masked[i, j]):
            val = matrix[i, j]
            tc = "white" if abs(val - 0.5) > 0.32 else "#222222"
            ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                    fontsize=9, color=tc, fontweight="medium")
ax.set_xticks(np.arange(-.5, n_c, 1), minor=True)
ax.set_yticks(np.arange(-.5, n_c, 1), minor=True)
ax.grid(which="minor", color="white", linewidth=1.5)
ax.tick_params(which="minor", length=0)
plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04,
             label="Odsetek wygranych: wiersz vs kolumna")
save_fig("h5_c_heatmap")

best = int(np.argmax(overall_rates))
fig, ax = plt.subplots(figsize=(8, 4.6))
colors = [PALETTE["pb"] if i == best else PALETTE["uct"]
          for i in range(len(c_values))]
err = [np.array(overall_rates) - np.array(overall_lo),
       np.array(overall_hi) - np.array(overall_rates)]
bars = ax.bar(c_labels, overall_rates, color=colors, edgecolor="white",
              yerr=err, capsize=5, error_kw={"ecolor": "#555555", "lw": 1.4})
ax.axhline(0.5, color=PALETTE["neutral"], ls="--", lw=1.3)
for i, r in enumerate(overall_rates):
    ax.text(i, overall_hi[i] + 0.02, f"{r*100:.0f}%", ha="center",
            fontsize=9, fontweight="bold",
            color=PALETTE["pb"] if i == best else "#333333")
ax.set_xlabel("Stała eksploracji c")
ax.set_ylabel("Ogólny odsetek wygranych (95% CI)")
ax.yaxis.set_major_formatter(plt.matplotlib.ticker.PercentFormatter(xmax=1.0, decimals=0))
ax.set_title("H5: Ogólny odsetek wygranych w funkcji stałej eksploracji c")
ax.set_ylim(0, 1)
ax.spines[["top", "right"]].set_visible(False)
save_fig("h5_c_bar")
