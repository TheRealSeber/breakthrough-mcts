"""H4: First-player (white) advantage across board sizes."""
import sys
from pathlib import Path

sys.path.insert(0, "notebooks")
from shared_utils import load_games, wilson_ci, save_fig
import matplotlib.pyplot as plt

board_sizes = [(6, 6), (6, 8), (8, 8)]
results = []

for rows, cols in board_sizes:
    games_path = Path(f"results/h4_first_player_{rows}x{cols}/games.jsonl")
    if not games_path.exists():
        print(f"No data at {games_path}")
        continue
    df = load_games(games_path)
    n = len(df)
    white_wins = (df["winner"] == "white").sum()
    rate, lo, hi = wilson_ci(int(white_wins), int(n))
    results.append({"size": f"{rows}x{cols}", "n": n, "rate": rate, "ci_low": lo, "ci_high": hi})
    print(f"{rows}x{cols}: white wins {white_wins}/{n} = {rate:.3f}  CI [{lo:.3f}, {hi:.3f}]")

if not results:
    print("No H4 data; run experiments/run_h4.py first.")
    sys.exit(0)

fig, ax = plt.subplots(figsize=(7, 5))
labels = [r["size"] for r in results]
rates = [r["rate"] for r in results]
err_lo = [r["rate"] - r["ci_low"] for r in results]
err_hi = [r["ci_high"] - r["rate"] for r in results]
xs = list(range(len(results)))
ax.errorbar(xs, rates, yerr=[err_lo, err_hi], color="tab:purple", marker="o", capsize=5)
ax.set_xticks(xs)
ax.set_xticklabels(labels)
ax.axhline(0.5, color="gray", linestyle="--", alpha=0.5, label="50% (brak przewagi)")
ax.set_ylabel("Odsetek wygranych białych (95% CI)")
ax.set_xlabel("Rozmiar planszy (rzędy × kolumny)")
ax.set_title("H4: Przewaga pierwszego gracza vs rozmiar planszy")
ax.legend()
save_fig("h4_first_player_advantage")
