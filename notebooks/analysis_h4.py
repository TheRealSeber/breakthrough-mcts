"""H4: First-player (white) advantage on 8x8 board."""
import sys
from pathlib import Path

sys.path.insert(0, "notebooks")
from shared_utils import (
    load_games, wilson_ci, significance_test, cohens_h, save_fig, PALETTE,
)
import matplotlib.pyplot as plt

GAMES = Path("results/h4_first_player_8x8/games.jsonl")
if not GAMES.exists():
    print(f"No data at {GAMES}; run experiments/run_h4.py first.")
    sys.exit(0)

df = load_games(GAMES)
n = len(df)
white_wins = int((df["winner"] == "white").sum())
rate, lo, hi = wilson_ci(white_wins, n)
p_val = significance_test(white_wins, n)
effect = cohens_h(rate)

print(f"8x8: white wins {white_wins}/{n} = {rate:.3f}")
print(f"  CI=[{lo:.3f}, {hi:.3f}]  p={p_val:.4f}  h={effect:.3f}")

black_rate = 1 - rate

fig, ax = plt.subplots(figsize=(9, 3.4))
ax.barh(0, rate, color=PALETTE["uct"], edgecolor="white", height=0.5,
        label=f"Biały (1. gracz): {white_wins}/{n}")
ax.barh(0, black_rate, left=rate, color="#444444", edgecolor="white",
        height=0.5, label=f"Czarny (2. gracz): {n - white_wins}/{n}")

ax.text(rate / 2, 0, f"{rate*100:.1f}%", ha="center", va="center",
        color="white", fontweight="bold", fontsize=13)
ax.text(rate + black_rate / 2, 0, f"{black_rate*100:.1f}%", ha="center",
        va="center", color="white", fontweight="bold", fontsize=13)

ax.errorbar(rate, 0, xerr=[[rate - lo], [hi - rate]], fmt="none",
            ecolor="#FFD166", elinewidth=2.6, capsize=7, capthick=2.6, zorder=5)
ax.axvline(0.5, color=PALETTE["heuristic"], ls="--", lw=1.8, zorder=4)
ax.annotate("brak przewagi (50%)", xy=(0.5, 0.30), xytext=(0.5, 0.46),
            ha="center", fontsize=9.5, color=PALETTE["heuristic"],
            fontweight="bold")

ax.set_xlim(0, 1)
ax.set_ylim(-0.5, 0.6)
ax.set_yticks([])
ax.set_xlabel("Udział zwycięstw")
ax.xaxis.set_major_formatter(plt.matplotlib.ticker.PercentFormatter(xmax=1.0, decimals=0))
ax.spines[["top", "right", "left"]].set_visible(False)
ax.set_title(f"H4: Przewaga pierwszego gracza na planszy 8×8\n"
             f"biały {rate*100:.1f}% (95% CI {lo*100:.1f}–{hi*100:.1f}%)",
             fontsize=12)
ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.55), ncol=2)
save_fig("h4_first_player_advantage")
