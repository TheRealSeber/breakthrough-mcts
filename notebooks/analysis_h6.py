"""H6: Decision time analysis by move number."""
import sys
from pathlib import Path

sys.path.insert(0, "notebooks")
from shared_utils import load_games, save_fig

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors

GAMES = Path("results/h6_decision_time/games.jsonl")
if not GAMES.exists():
    print(f"No data at {GAMES}; run experiments/run_h6.py first.")
    sys.exit(0)

df = load_games(GAMES)
print(f"Loaded {len(df)} games")

rows = []
for _, g in df.iterrows():
    wi = g["agent_white"].get("iterations", 0)
    bi = g["agent_black"].get("iterations", 0)
    for i, t in enumerate(g.get("move_times", []) or []):
        rows.append({
            "move_number": i,
            "decision_time": t,
            "budget": wi if i % 2 == 0 else bi,
        })
mt = pd.DataFrame(rows)
if mt.empty:
    print("No move_times data found.")
    sys.exit(0)

budgets = sorted(mt["budget"].unique())
norm = mcolors.LogNorm(vmin=min(budgets), vmax=max(budgets))
cmap = cm.viridis


def fmt(v):
    v = int(v)
    return f"{v // 1000}k" if v >= 1000 and v % 1000 == 0 else str(v)


print("\nCzas na ruch wg własnego budżetu agenta (oba kolory razem):")
for b in budgets:
    s = mt[mt["budget"] == b]["decision_time"]
    print(f"  {fmt(b):>5}: mediana={s.median():.3f}s  średnia={s.mean():.3f}s  n={len(s)}")

fig, (ax1, ax2) = plt.subplots(
    1, 2, figsize=(13, 5.3), gridspec_kw={"width_ratios": [2.5, 1]})

for b in budgets:
    grp = mt[mt["budget"] == b].groupby("move_number")["decision_time"]
    cnt = grp.size()
    keep = cnt[cnt >= 10].index
    med = grp.median()[keep].rolling(3, center=True, min_periods=1).mean()
    q1 = grp.quantile(0.25)[keep].rolling(3, center=True, min_periods=1).mean()
    q3 = grp.quantile(0.75)[keep].rolling(3, center=True, min_periods=1).mean()
    color = cmap(norm(b))
    ax1.fill_between(med.index, q1, q3, color=color, alpha=0.12, lw=0, zorder=2)
    ax1.plot(med.index, med.values, color=color, lw=2.6, zorder=4,
             label=f"{fmt(b)} iter.")
    ax1.annotate(f"{fmt(b)}", xy=(med.index[-1], med.values[-1]),
                 xytext=(6, 0), textcoords="offset points", va="center",
                 fontsize=9.5, fontweight="bold", color=color)

ax1.set_xlabel("Numer półruchu w partii")
ax1.set_ylabel("Czas decyzji [s] (mediana, wstęga IQR)")
ax1.set_title("Przebieg w trakcie partii")
ax1.set_ylim(bottom=0)
ax1.spines[["top", "right"]].set_visible(False)
ax1.legend(title="Budżet iteracji", loc="upper right")

meds = [mt[mt["budget"] == b]["decision_time"].median() for b in budgets]
colors = [cmap(norm(b)) for b in budgets]
ax2.bar([fmt(b) for b in budgets], meds, color=colors, edgecolor="white")
for i, m in enumerate(meds):
    ax2.text(i, m, f"{m:.2f}s", ha="center", va="bottom",
             fontsize=9.5, fontweight="bold")
ax2.set_xlabel("Budżet iteracji")
ax2.set_ylabel("Mediana czasu na ruch [s]")
ax2.set_title("Skalowanie z budżetem")
ax2.set_ylim(0, max(meds) * 1.18)
ax2.spines[["top", "right"]].set_visible(False)

fig.suptitle("H6: Czas decyzji MCTS — rośnie z budżetem iteracji, maleje w trakcie partii",
             fontsize=14, fontweight="bold")
fig.tight_layout(rect=(0, 0, 1, 0.95))
save_fig("h6_decision_time")
