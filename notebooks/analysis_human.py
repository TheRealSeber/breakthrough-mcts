"""Analiza partii człowiek vs AI (results/human_games/*.jsonl).

Każdy plik partii zawiera log ruchów ({"player", "move", "think_sec"}) oraz
ostatni wiersz z podsumowaniem ({"player_name", "winner", "human_plays",
"agent", "difficulty_rating", czasy namysłu, ...}).

Wykresy (prefiks human_) — bez podziału na poszczególnych graczy:
  1. wynik każdej partii (przegląd: agent, długość, kolor, wynik)
  2. ocena trudności vs siła AI (liczba iteracji)
  3. średni czas namysłu AI na ruch vs liczba iteracji (log-log)
  4. łączny czas namysłu: człowiek vs AI per partia
  5. czas na ruch w trakcie partii (człowiek vs AI)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "notebooks")
from shared_utils import save_fig

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

HUMAN_DIR = Path("results/human_games")


def _fmt_iters(v):
    v = int(v)
    if v >= 1_000_000 and v % 1_000_000 == 0:
        return f"{v // 1_000_000}M"
    if v >= 1000 and v % 1000 == 0:
        return f"{v // 1000}k"
    return str(v)


def load_human_games():
    """Return (games_df, moves_df) parsed from results/human_games/*.jsonl."""
    game_rows, move_rows = [], []
    for path in sorted(HUMAN_DIR.glob("*.jsonl")):
        moves, summary = [], None
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "player_name" in rec:
                    summary = rec
                elif "move" in rec:
                    moves.append(rec)
        if summary is None:
            continue
        gid = path.stem
        agent = summary.get("agent", {})
        human_plays = summary.get("human_plays")
        winner = summary.get("winner")
        game_rows.append({
            "game_id": gid,
            "human_plays": human_plays,
            "winner": winner,
            "human_won": winner == human_plays,
            "n_moves": summary.get("n_moves", len(moves)),
            "duration_sec": summary.get("duration_sec"),
            "agent_type": agent.get("type"),
            "iterations": agent.get("iterations"),
            "difficulty_rating": summary.get("difficulty_rating"),
            "human_think_sec": summary.get("human_think_sec"),
            "ai_think_sec": summary.get("ai_think_sec"),
            "human_avg_think_sec": summary.get("human_avg_think_sec"),
            "ai_avg_think_sec": summary.get("ai_avg_think_sec"),
        })
        for ply, mv in enumerate(moves, start=1):
            move_rows.append({
                "game_id": gid,
                "ply": ply,
                "player": "Człowiek" if mv.get("player") == "human" else "AI",
                "to_sq": mv["move"][1] if mv.get("move") else None,
                "think_sec": mv.get("think_sec"),
                "agent_type": agent.get("type"),
                "iterations": agent.get("iterations"),
                "human_plays": human_plays,
            })
    return pd.DataFrame(game_rows), pd.DataFrame(move_rows)


def _glabels(g):
    """Per-game axis labels by agent/iterations/color (no player identity),
    disambiguated with a #n suffix when several games share the same config."""
    base = [f"{r['agent_type']}/{_fmt_iters(r['iterations'])} · "
            f"{'biały' if r['human_plays'] == 'white' else 'czarny'}"
            for _, r in g.iterrows()]
    seen, out = {}, []
    for b in base:
        seen[b] = seen.get(b, 0) + 1
        out.append(b if base.count(b) == 1 else f"{b} #{seen[b]}")
    return out


def plot_outcome_per_game(games):
    print("\n[1] Wynik każdej partii")
    g = games.sort_values("iterations").reset_index(drop=True)
    labels = _glabels(g)
    cb = sns.color_palette("colorblind")
    colors = [cb[2] if w else cb[3] for w in g["human_won"]]
    y = np.arange(len(g))
    total_w = int(games["human_won"].sum())
    print(f"  człowiek wygrał {total_w}/{len(games)}")

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(y, g["n_moves"], color=colors)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("Długość partii (półruchy)")
    ax.set_title("Przegląd partii vs AI (zielony = człowiek wygrał, czerwony = przegrał)")
    save_fig("human_outcome_per_game")


def plot_difficulty_vs_strength(games):
    print("\n[2] Ocena trudności vs liczba iteracji AI")
    g = games.dropna(subset=["difficulty_rating", "iterations"])
    if g.empty:
        return
    fig, ax = plt.subplots(figsize=(9, 5.5))
    sns.scatterplot(data=g, x="iterations", y="difficulty_rating", hue="agent_type",
                    style="agent_type", s=140, ax=ax)
    ax.set_xscale("log")
    ax.set_ylim(0, 10.5)
    ax.set_xlabel("Liczba iteracji AI")
    ax.set_ylabel("Ocena trudności (1–10)")
    ax.set_title("Postrzegana trudność vs siła obliczeniowa AI")
    ax.legend(title="Algorytm")
    save_fig("human_difficulty_vs_strength")


def plot_ai_thinktime_scaling(games):
    print("\n[3] Średni czas AI na ruch vs liczba iteracji")
    g = games.dropna(subset=["ai_avg_think_sec", "iterations"])
    if g.empty:
        return
    fig, ax = plt.subplots(figsize=(9, 5.5))
    sns.scatterplot(data=g, x="iterations", y="ai_avg_think_sec", hue="agent_type",
                    style="agent_type", s=140, ax=ax)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Liczba iteracji AI")
    ax.set_ylabel("Średni czas AI na ruch [s]")
    ax.set_title("Skalowanie czasu namysłu AI z budżetem iteracji")
    ax.legend(title="Algorytm")
    for _, r in g.iterrows():
        print(f"  {r['agent_type']}/{_fmt_iters(r['iterations'])}: "
              f"{r['ai_avg_think_sec']:.2f} s/ruch")
    save_fig("human_ai_thinktime_scaling")


def plot_thinktime_human_vs_ai(games):
    print("\n[4] Łączny czas namysłu: człowiek vs AI")
    g = games.sort_values("iterations").reset_index(drop=True)
    labels = _glabels(g)
    x = np.arange(len(g))
    w = 0.4
    cb = sns.color_palette("colorblind")
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.bar(x - w / 2, g["human_think_sec"], w, label="Człowiek", color=cb[0])
    ax.bar(x + w / 2, g["ai_think_sec"], w, label="AI", color=cb[1])
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_ylabel("Łączny czas namysłu [s]")
    ax.set_title("Łączny czas namysłu w partii: człowiek vs AI")
    ax.legend()
    save_fig("human_thinktime_human_vs_ai")


def plot_thinktime_over_game(moves):
    print("\n[6] Czas na ruch w funkcji numeru półruchu")
    m = moves.dropna(subset=["think_sec"])
    if m.empty:
        return
    fig, ax = plt.subplots(figsize=(10, 5.5))
    sns.lineplot(data=m, x="ply", y="think_sec", hue="player",
                 errorbar=("ci", 95), ax=ax)
    ax.set_xlabel("Półruch (numer)")
    ax.set_ylabel("Czas na ruch [s]")
    ax.set_title("Czas namysłu w trakcie partii (średnia ± 95% CI, wszystkie partie)")
    ax.legend(title="")
    save_fig("human_thinktime_over_game")


if __name__ == "__main__":
    games, moves = load_human_games()
    if games.empty:
        print(f"Brak danych w {HUMAN_DIR}; zagraj kilka partii przez GUI.")
        sys.exit(0)
    print(f"Wczytano {len(games)} partii, {len(moves)} ruchów.")

    plot_outcome_per_game(games)
    plot_difficulty_vs_strength(games)
    plot_ai_thinktime_scaling(games)
    plot_thinktime_human_vs_ai(games)
    plot_thinktime_over_game(moves)
    print("\nDone.")
