"""H4: First-player (white) advantage on 8x8 board."""
import sys
from pathlib import Path

sys.path.insert(0, "notebooks")
from shared_utils import load_games, wilson_ci, significance_test, cohens_h, save_fig
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

fig, ax = plt.subplots(figsize=(5, 4))
ax.bar(["8x8"], [rate], yerr=[[rate - lo], [hi - rate]], color="tab:purple", capsize=8)
ax.axhline(0.5, color="gray", linestyle="--", alpha=0.5, label="50% (brak przewagi)")
ax.set_ylabel("Odsetek wygranych białych (95% CI)")
ax.set_title("H4: Przewaga pierwszego gracza (8x8)")
ax.legend()
ax.set_ylim(0, 1)
save_fig("h4_first_player_advantage")
