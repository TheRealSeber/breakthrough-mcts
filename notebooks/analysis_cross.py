"""Cross-cutting analyses over the H1-H6 datasets."""
import sys
from pathlib import Path

sys.path.insert(0, "notebooks")
from shared_utils import load_games, wilson_ci, save_fig

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

RESULTS = Path("results")

DATASETS = {
    "H1\nRAVE vs UCT": "h1_rave_vs_uct",
    "H2\nPB vs UCT": "h2_pb_vs_uct",
    "H3\nHeur. vs UCT": "h3_heuristic_vs_uct",
    "H4\npierwszy gracz": "h4_first_player_8x8",
    "H5\nstrojenie c": "h5_c_tuning",
    "H6\nczas decyzji": "h6_decision_time",
}


def _load(name: str) -> pd.DataFrame | None:
    path = RESULTS / name / "games.jsonl"
    if not path.exists():
        print(f"  skip: no data at {path}")
        return None
    return load_games(path)


def plot_game_length_distributions():
    print("\n[1] Game-length distributions per experiment")
    frames = []
    for label, name in DATASETS.items():
        df = _load(name)
        if df is None or "n_moves" not in df:
            continue
        sub = df[["n_moves"]].copy()
        sub["experiment"] = label
        frames.append(sub)
        print(f"  {name}: n={len(sub)} median={sub['n_moves'].median():.0f} "
              f"mean={sub['n_moves'].mean():.1f}")
    if not frames:
        return
    data = pd.concat(frames, ignore_index=True)

    fig, ax = plt.subplots(figsize=(10, 5.5))
    sns.violinplot(data=data, x="experiment", y="n_moves", ax=ax,
                   inner="quartile", cut=0, density_norm="width")
    ax.set_xlabel("")
    ax.set_ylabel("Długość partii (półruchy)")
    ax.set_title("Rozkład długości partii według eksperymentu")
    save_fig("cross_game_length_distributions")


def plot_first_player_advantage():
    print("\n[2] First-player (white) win rate across experiments")
    rows = []
    for label, name in DATASETS.items():
        df = _load(name)
        if df is None or "winner" not in df:
            continue
        decided = df[df["winner"].isin(["white", "black"])]
        n = len(decided)
        if n == 0:
            continue
        w = int((decided["winner"] == "white").sum())
        rate, lo, hi = wilson_ci(w, n)
        rows.append({"experiment": label.replace("\n", " "), "rate": rate,
                     "lo": lo, "hi": hi, "n": n})
        print(f"  {name}: white {w}/{n} = {rate:.3f}  CI=[{lo:.3f}, {hi:.3f}]")
    if not rows:
        return
    res = pd.DataFrame(rows)

    fig, ax = plt.subplots(figsize=(10, 5.5))
    x = np.arange(len(res))
    err = [res["rate"] - res["lo"], res["hi"] - res["rate"]]
    ax.bar(x, res["rate"], color=sns.color_palette("colorblind")[0],
           yerr=err, capsize=5, width=0.6)
    ax.axhline(0.5, color="black", ls="--", lw=1, label="brak przewagi (0,5)")
    ax.set_xticks(x)
    ax.set_xticklabels(res["experiment"], rotation=20, ha="right")
    ax.set_ylabel("Odsetek wygranych białych (pierwszy gracz)")
    ax.set_ylim(0, 1)
    ax.set_title("Przewaga pierwszego gracza w eksperymentach (95% CI Wilsona)")
    ax.legend()
    save_fig("cross_first_player_advantage")


def plot_opening_heatmap(side: int = 8):
    print("\n[3] Opening-move destination heatmap (white's first move)")
    counts = np.zeros((side, side))
    n = 0
    for name in DATASETS.values():
        df = _load(name)
        if df is None or "moves" not in df:
            continue
        for _, g in df.iterrows():
            moves = g.get("moves") or []
            if not moves:
                continue
            dest = moves[0][1]
            counts[dest // side, dest % side] += 1
            n += 1
    if n == 0:
        return
    print(f"  aggregated {n} opening moves over an {side}x{side} board")

    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    sns.heatmap(counts, annot=True, fmt=".0f", cmap="magma", square=True,
                cbar_kws={"label": "Liczba wyborów jako pierwszy ruch"}, ax=ax)
    ax.invert_yaxis()
    ax.set_xlabel("Kolumna (plik)")
    ax.set_ylabel("Rząd (wiersz)")
    ax.set_title(f"Gdzie białe grają pierwszy ruch ({n} partii)")
    save_fig("cross_opening_heatmap")


def plot_h3_time_asymmetry():
    print("\n[4] Thinking-time asymmetry: heuristic vs UCT (H3)")
    df = _load("h3_heuristic_vs_uct")
    if df is None or "time_white" not in df:
        return
    rows = []
    for _, g in df.iterrows():
        sides = {"white": g["agent_white"], "black": g["agent_black"]}
        times = {"white": g.get("time_white"), "black": g.get("time_black")}
        heur = next((c for c, a in sides.items() if a["type"] == "heuristic"), None)
        uct_c = next((c for c, a in sides.items() if a["type"] == "uct"), None)
        if heur is None or uct_c is None:
            continue
        n_moves = g["n_moves"]
        heur_moves = (n_moves + 1) // 2 if heur == "white" else n_moves // 2
        uct_moves = (n_moves + 1) // 2 if uct_c == "white" else n_moves // 2
        rows.append({"iters": sides[uct_c]["iterations"],
                     "heuristic": times[heur] / max(heur_moves, 1),
                     "uct": times[uct_c] / max(uct_moves, 1)})
    td = pd.DataFrame(rows).groupby("iters").mean().reset_index()

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(td["iters"], td["heuristic"], marker="s", label="Heurystyka (alpha-beta d=5)")
    ax.plot(td["iters"], td["uct"], marker="o", label="UCT")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Budżet iteracji UCT")
    ax.set_ylabel("Średni czas na ruch [s]")
    ax.set_title("Czas namysłu na ruch: heurystyka o stałej głębokości vs skalujący UCT (H3)")
    ax.legend()
    for r in td.itertuples():
        print(f"  {int(r.iters):>7d} iters: heuristic={r.heuristic*1000:.1f} ms  "
              f"uct={r.uct*1000:.1f} ms")
    save_fig("cross_h3_time_asymmetry")


if __name__ == "__main__":
    plot_game_length_distributions()
    plot_first_player_advantage()
    plot_opening_heatmap()
    plot_h3_time_asymmetry()
    print("\nDone.")
