from __future__ import annotations
import hashlib
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from pathlib import Path

from tqdm import tqdm

from breakthrough import GameState
from breakthrough.agents import make_agent


@dataclass
class AgentConfig:
    type: str
    iterations: int = 1000
    c: float = 1.4142135623730951
    rave_k: float = 0.01
    bias_weight: float = 1.0
    depth: int = 5


@dataclass
class Experiment:
    name: str
    agents: list[AgentConfig]
    n_games_per_pair: int = 100
    master_seed: int = 42
    parallel: int = -1
    output_dir: Path = field(default_factory=lambda: Path("results"))
    board_rows: int = 8
    board_cols: int = 8


def _derive_seed(master_seed: int, game_id: str) -> int:
    h = hashlib.sha256(f"{master_seed}:{game_id}".encode()).digest()
    return int.from_bytes(h[:8], "little") & 0xFFFF_FFFF_FFFF_FFFF


def _play_game(
    white_cfg: dict,
    black_cfg: dict,
    seed: int,
    rows: int,
    cols: int,
    experiment: str,
) -> dict:
    white_agent = make_agent(white_cfg, seed=seed)
    black_agent = make_agent(black_cfg, seed=seed ^ 0xDEADBEEF)
    state = GameState(rows, cols)
    moves: list[list[int]] = []
    move_times: list[float] = []
    t_white = t_black = 0.0

    while not state.is_terminal():
        agent = white_agent if state.current_player() == "white" else black_agent
        t0 = time.perf_counter()
        mv = agent.select_move(state)
        dt = time.perf_counter() - t0
        if state.current_player() == "white":
            t_white += dt
        else:
            t_black += dt
        moves.append([int(mv[0]), int(mv[1])])
        move_times.append(round(dt, 6))
        state = state.apply(mv[0], mv[1])

    return {
        "experiment": experiment,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "agent_white": white_cfg,
        "agent_black": black_cfg,
        "seed": seed,
        "winner": state.winner(),
        "n_moves": int(state.get_move_count()),
        "moves": moves,
        "move_times": move_times,
        "time_white": round(t_white, 3),
        "time_black": round(t_black, 3),
    }


def _load_done_ids(jsonl_path: Path) -> set[str]:
    done: set[str] = set()
    if jsonl_path.exists():
        with open(jsonl_path) as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    if "game_id" in rec:
                        done.add(rec["game_id"])
                except json.JSONDecodeError:
                    pass
    return done


def run_experiment(exp: Experiment) -> None:
    out_dir = Path(exp.output_dir) / exp.name
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "games.jsonl"

    meta = asdict(exp)
    meta["output_dir"] = str(exp.output_dir)
    with open(out_dir / "experiment_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    jobs = []
    n_per_side = exp.n_games_per_pair // 2
    for i in range(len(exp.agents)):
        for j in range(len(exp.agents)):
            if i == j:
                continue
            for game_num in range(n_per_side):
                game_id = f"{i}v{j}_{game_num}"
                seed = _derive_seed(exp.master_seed, game_id)
                jobs.append((asdict(exp.agents[i]), asdict(exp.agents[j]), seed, game_id))

    done_ids = _load_done_ids(jsonl_path)
    pending = [(w, b, s, gid) for (w, b, s, gid) in jobs if gid not in done_ids]

    workers = exp.parallel if exp.parallel > 0 else max(1, (os.cpu_count() or 2) - 1)

    if not pending:
        print(f"[{exp.name}] all {len(jobs)} games already complete")
        return

    with open(jsonl_path, "a") as out_f:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    _play_game, w, b, s, exp.board_rows, exp.board_cols, exp.name
                ): gid
                for (w, b, s, gid) in pending
            }
            for fut in tqdm(as_completed(futures), total=len(futures), desc=exp.name):
                gid = futures[fut]
                try:
                    result = fut.result()
                    result["game_id"] = gid
                    out_f.write(json.dumps(result) + "\n")
                    out_f.flush()
                except Exception as e:
                    print(f"Game {gid} failed: {e}")
