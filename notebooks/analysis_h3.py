"""H3: Heuristic alpha-beta vs UCT — cross-over at varying iteration budgets."""
import sys
from pathlib import Path

sys.path.insert(0, "notebooks")
from shared_utils import load_games, wilson_ci, save_fig
import matplotlib.pyplot as plt

GAMES = Path("results/h3_heuristic_vs_uct/games.jsonl")
if not GAMES.exists():
    print(f"No data at {GAMES}; run experiments/run_h3.py first.")
    sys.exit(0)

df = load_games(GAMES)
print(f"Loaded {len(df)} games")

# For each UCT iteration budget, compute heuristic's win rate vs that UCT config
iters_set = set()
for _, row in df.iterrows():
    if row["agent_white"].get("type") == "uct":
        iters_set.add(row["agent_white"].get("iterations", 0))
    if row["agent_black"].get("type") == "uct":
        iters_set.add(row["agent_black"].get("iterations", 0))

xs, rates, los, his = [], [], [], []
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
        xs.append(iters); rates.append(rate); los.append(lo); his.append(hi)

fig, ax = plt.subplots(figsize=(8, 5))
err_lo = [r - l for r, l in zip(rates, los)]
err_hi = [h - r for r, h in zip(rates, his)]
ax.errorbar(xs, rates, yerr=[err_lo, err_hi], color="tab:red", marker="o", capsize=5,
            label="Heurystyka (alpha-beta d=5)")
ax.axhline(0.5, color="gray", linestyle="--", alpha=0.5, label="50%")
ax.set_xscale("log")
ax.set_xlabel("Budżet iteracji UCT (przeciwnik)")
ax.set_ylabel("Odsetek wygranych heurystyki (95% CI)")
ax.set_title("H3: Heurystyka vs UCT — punkt krzyżowania")
ax.legend()
save_fig("h3_heuristic_vs_uct")
