"""H3: Heuristic alpha-beta vs UCT — cross-over at varying iteration budgets."""
import sys
from pathlib import Path

sys.path.insert(0, "notebooks")
from shared_utils import (
    load_games, wilson_ci, significance_test, cohens_h, save_fig,
    style_winrate_axis, winrate_series, PALETTE,
)
import numpy as np
import matplotlib.pyplot as plt

GAMES = Path("results/h3_heuristic_vs_uct/games.jsonl")
if not GAMES.exists():
    print(f"No data at {GAMES}; run experiments/run_h3.py first.")
    sys.exit(0)

df = load_games(GAMES)
print(f"Loaded {len(df)} games")

iters_set = set()
for _, row in df.iterrows():
    if row["agent_white"].get("type") == "uct":
        iters_set.add(row["agent_white"].get("iterations", 0))
    if row["agent_black"].get("type") == "uct":
        iters_set.add(row["agent_black"].get("iterations", 0))

xs, rates, los, his, pvals = [], [], [], [], []
for iters in sorted(iters_set):
    wins = 0
    n = 0
    for _, row in df.iterrows():
        white_h = row["agent_white"].get("type") == "heuristic"
        black_h = row["agent_black"].get("type") == "heuristic"
        white_uct = row["agent_white"].get("type") == "uct" and row["agent_white"].get("iterations") == iters
        black_uct = row["agent_black"].get("type") == "uct" and row["agent_black"].get("iterations") == iters
        if (white_h and black_uct) or (black_h and white_uct):
            n += 1
            if white_h and row["winner"] == "white":
                wins += 1
            if black_h and row["winner"] == "black":
                wins += 1
    if n > 0:
        rate, lo, hi = wilson_ci(wins, n)
        p_val = significance_test(wins, n)
        effect = cohens_h(rate)
        xs.append(iters)
        rates.append(rate)
        los.append(lo)
        his.append(hi)
        pvals.append(p_val)
        print(f"  UCT iters={iters:>6d}: heuristic rate={rate:.3f} "
              f"CI=[{lo:.3f}, {hi:.3f}] p={p_val:.4f} h={effect:.3f}")

crossover = None
for i in range(1, len(rates)):
    if (rates[i - 1] - 0.5) * (rates[i] - 0.5) <= 0 and rates[i - 1] != rates[i]:
        lx0, lx1 = np.log10(xs[i - 1]), np.log10(xs[i])
        frac = (0.5 - rates[i - 1]) / (rates[i] - rates[i - 1])
        crossover = 10 ** (lx0 + frac * (lx1 - lx0))
        break

fig, ax = plt.subplots(figsize=(8.5, 5.2))
winrate_series(ax, xs, rates, los, his,
               label="Heurystyka (alpha-beta d=5)", color=PALETTE["heuristic"],
               marker="o", pvals=pvals, annotate_last=False)
style_winrate_axis(ax, ylabel="Odsetek wygranych heurystyki (95% CI)")
ax.set_xscale("log")

if crossover is not None:
    ax.axvline(crossover, color=PALETTE["accent"], ls="-.", lw=1.8, zorder=3)
    ax.annotate(f"punkt krzyżowania\n≈ {crossover:,.0f} iter.".replace(",", " "),
                xy=(crossover, 0.5), xytext=(0, 30), textcoords="offset points",
                ha="center", fontsize=9.5, fontweight="bold", color=PALETTE["accent"],
                arrowprops=dict(arrowstyle="->", color=PALETTE["accent"], lw=1.4))
    print(f"\nPunkt krzyżowania ≈ {crossover:.0f} iteracji UCT")

ax.set_xlabel("Budżet iteracji UCT — przeciwnik (skala log)")
ax.set_title("H3: Heurystyka vs UCT — punkt krzyżowania")
ax.legend(loc="center left")
save_fig("h3_heuristic_vs_uct")
