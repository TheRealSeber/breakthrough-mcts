"""Shared analysis utilities. Imported by all analysis_h*.py scripts."""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_theme(style="whitegrid", palette="colorblind")
FIGURES_DIR = Path("report/figures")
FIGURES_DIR.mkdir(parents=True, exist_ok=True)


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
