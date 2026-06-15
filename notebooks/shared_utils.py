"""Shared analysis utilities. Imported by all analysis_h*.py scripts."""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns

FIGURES_DIR = Path("report/figures")
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

PALETTE = {
    "uct": "#4C72B0",
    "rave": "#DD8452",
    "pb": "#55A868",
    "heuristic": "#C44E52",
    "accent": "#8172B3",
    "neutral": "#7F7F7F",
    "win": "#2A9D8F",
    "loss": "#E76F51",
}


def setup_style():
    """Globalny, spójny motyw dla wszystkich wykresów (wektorowy PDF)."""
    sns.set_theme(style="whitegrid", context="notebook",
                  palette="colorblind", font="DejaVu Sans")
    plt.rcParams.update({
        "figure.dpi": 120,
        "figure.facecolor": "white",
        "axes.titleweight": "bold",
        "axes.titlesize": 14,
        "axes.titlepad": 12,
        "axes.labelsize": 12,
        "axes.labelweight": "medium",
        "axes.edgecolor": "#444444",
        "axes.linewidth": 1.0,
        "axes.grid.axis": "both",
        "grid.alpha": 0.30,
        "grid.linewidth": 0.7,
        "legend.frameon": True,
        "legend.framealpha": 0.92,
        "legend.edgecolor": "#dddddd",
        "legend.fancybox": True,
        "savefig.bbox": "tight",
        "pdf.fonttype": 42,
    })


setup_style()


def style_winrate_axis(ax, ylabel="Odsetek wygranych (95% CI Wilsona)",
                       shade=True):
    """Wspólny wygląd osi dla wykresów odsetka wygranych: linia 50%,
    delikatne tło regionów przewagi/słabości, ograniczenie [0, 1]."""
    if shade:
        ax.axhspan(0.5, 1.0, color=PALETTE["win"], alpha=0.06, zorder=0)
        ax.axhspan(0.0, 0.5, color=PALETTE["loss"], alpha=0.06, zorder=0)
    ax.axhline(0.5, color=PALETTE["neutral"], linestyle=(0, (5, 4)),
               lw=1.3, zorder=1)
    ax.set_ylim(0, 1)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0, decimals=0))
    ax.set_ylabel(ylabel)
    ax.spines[["top", "right"]].set_visible(False)


def winrate_series(ax, x, rate, lo, hi, label, color, marker="o",
                   pvals=None, annotate_last=True):
    """Rysuje serię odsetka wygranych jako wstęgę CI + linię z markerami.
    Punkty istotne (p<0.05) są wypełnione, nieistotne — puste w środku."""
    x = np.asarray(x, dtype=float)
    rate = np.asarray(rate, dtype=float)
    lo = np.asarray(lo, dtype=float)
    hi = np.asarray(hi, dtype=float)

    ax.fill_between(x, lo, hi, color=color, alpha=0.16, lw=0, zorder=2)
    ax.plot(x, rate, color=color, lw=2.4, zorder=4,
            solid_capstyle="round", label=label)

    if pvals is not None:
        pvals = np.asarray(pvals, dtype=float)
        sig = pvals < 0.05
    else:
        sig = np.ones_like(rate, dtype=bool)
    ax.scatter(x[sig], rate[sig], s=70, color=color, zorder=6,
               edgecolor="white", linewidth=1.4, marker=marker)
    ax.scatter(x[~sig], rate[~sig], s=70, facecolor="white", zorder=6,
               edgecolor=color, linewidth=1.8, marker=marker)

    if annotate_last and len(rate):
        ax.annotate(f"{rate[-1]*100:.0f}%",
                    xy=(x[-1], rate[-1]),
                    xytext=(8, 0), textcoords="offset points",
                    va="center", ha="left", fontsize=10,
                    fontweight="bold", color=color)


def plot_game_length(df, name, title, color):
    """Ładny rozkład długości partii: histogram + KDE + mediana/średnia."""
    lengths = df["n_moves"].dropna()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    sns.histplot(lengths, kde=True, color=color, edgecolor="white",
                 alpha=0.55, ax=ax, line_kws={"lw": 2.2})
    med, mean = lengths.median(), lengths.mean()
    ax.axvline(med, color=PALETTE["neutral"], ls="--", lw=1.6,
               label=f"mediana = {med:.0f}")
    ax.axvline(mean, color=PALETTE["heuristic"], ls=":", lw=1.8,
               label=f"średnia = {mean:.1f}")
    ax.set_xlabel("Długość partii (półruchy)")
    ax.set_ylabel("Liczba partii")
    ax.set_title(title)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend()
    save_fig(name)


def load_games(path: str | Path) -> pd.DataFrame:
    records = []
    with open(path) as f:
        for line in f:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return pd.DataFrame(records)


def wilson_ci(wins: int, n: int, alpha: float = 0.05) -> tuple[float, float, float]:
    """Wilson score interval. Returns (rate, low, high)."""
    from scipy.stats import norm
    if n == 0:
        return 0.5, 0.0, 1.0
    z = norm.ppf(1 - alpha / 2)
    p = wins / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    low = min(p, max(0.0, center - margin))
    high = max(p, min(1.0, center + margin))
    return p, low, high


def significance_test(wins: int, n: int) -> float:
    """Two-sided binomial test, H0: p = 0.5. Returns p-value."""
    from scipy.stats import binomtest
    return binomtest(wins, n, 0.5, alternative="two-sided").pvalue


def cohens_h(p1: float, p2: float = 0.5) -> float:
    """Cohen's h effect size for two proportions."""
    return 2 * (math.asin(math.sqrt(p1)) - math.asin(math.sqrt(p2)))


def game_length_stats(df: pd.DataFrame) -> dict:
    """Compute median, IQR, mean of n_moves."""
    lengths = df["n_moves"]
    return {
        "median": lengths.median(),
        "q1": lengths.quantile(0.25),
        "q3": lengths.quantile(0.75),
        "iqr": lengths.quantile(0.75) - lengths.quantile(0.25),
        "mean": lengths.mean(),
    }


def extract_move_times(df: pd.DataFrame) -> pd.DataFrame:
    """Explode move_times into long-form: one row per (game, move_number, time)."""
    rows = []
    for _, game in df.iterrows():
        for i, t in enumerate(game.get("move_times", []) or []):
            rows.append({
                "game_id": game.get("game_id"),
                "move_number": i,
                "decision_time": t,
            })
    return pd.DataFrame(rows)


def save_fig(name: str):
    path = FIGURES_DIR / f"{name}.pdf"
    plt.savefig(path, bbox_inches="tight")
    plt.close()
    print(f"Saved: {path}")


def aggregate_winrate_by_iters(df: pd.DataFrame, agent_type: str) -> pd.DataFrame:
    """For each iteration budget, compute win rate of `agent_type` (across both colors)."""
    rows = []
    iters_set = set()
    for _, row in df.iterrows():
        if row["agent_white"].get("type") == agent_type:
            iters_set.add(row["agent_white"].get("iterations", 0))
        if row["agent_black"].get("type") == agent_type:
            iters_set.add(row["agent_black"].get("iterations", 0))

    for iters in sorted(iters_set):
        wins = 0
        n = 0
        for _, row in df.iterrows():
            white_is = row["agent_white"].get("type") == agent_type and row["agent_white"].get("iterations") == iters
            black_is = row["agent_black"].get("type") == agent_type and row["agent_black"].get("iterations") == iters
            if not (white_is or black_is):
                continue
            n += 1
            if white_is and row["winner"] == "white":
                wins += 1
            if black_is and row["winner"] == "black":
                wins += 1
        rate, lo, hi = wilson_ci(wins, n)
        p_val = significance_test(wins, n) if n > 0 else 1.0
        effect = cohens_h(rate) if n > 0 else 0.0
        rows.append({
            "iterations": iters,
            "wins": wins,
            "n": n,
            "rate": rate,
            "ci_low": lo,
            "ci_high": hi,
            "p_value": p_val,
            "cohens_h": effect,
        })
    return pd.DataFrame(rows)
