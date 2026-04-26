"""Human-vs-AI Pygame interface. Run with: python -m breakthrough.gui"""
import json
import threading
import time
from pathlib import Path
from datetime import datetime

import pygame

from breakthrough import GameState
from breakthrough.agents import make_agent

CELL = 90
MARGIN = 40
ROWS, COLS = 6, 6
W = COLS * CELL + 2 * MARGIN
H = ROWS * CELL + 2 * MARGIN + 60

WHITE_COLOR = (240, 220, 180)
BLACK_COLOR = (60, 40, 20)
BOARD_LIGHT = (210, 180, 140)
BOARD_DARK = (160, 120, 80)
HIGHLIGHT = (100, 200, 100, 160)
BG = (40, 30, 20)
TEXT_COLOR = (255, 255, 255)


def pixel_to_sq(x: int, y: int, cols: int) -> int | None:
    c = (x - MARGIN) // CELL
    r = (y - MARGIN) // CELL
    if 0 <= r < ROWS and 0 <= c < cols:
        return r * cols + c
    return None


def run_gui():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Breakthrough 6x6")
    font = pygame.font.SysFont("monospace", 18)
    clock = pygame.time.Clock()

    agent_cfg = {"type": "uct", "iterations": 3000}
    human_plays = "white"

    state = GameState(ROWS, COLS)
    selected_sq: int | None = None
    legal_from_selected: list[int] = []
    agent_thinking = False
    agent_move_result: list[tuple[int, int] | None] = [None]
    status_msg = "Your turn (White)"
    game_log: list[dict] = []

    agent = make_agent(agent_cfg, seed=int(time.time()) & 0xFFFFFFFF)

    def think_thread():
        mv = agent.select_move(state)
        agent_move_result[0] = mv

    def draw():
        screen.fill(BG)
        for r in range(ROWS):
            for c in range(COLS):
                color = BOARD_LIGHT if (r + c) % 2 == 0 else BOARD_DARK
                pygame.draw.rect(
                    screen, color, (MARGIN + c * CELL, MARGIN + r * CELL, CELL, CELL)
                )

        surf = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
        surf.fill(HIGHLIGHT)
        for to_sq in legal_from_selected:
            tr, tc = divmod(to_sq, COLS)
            screen.blit(surf, (MARGIN + tc * CELL, MARGIN + tr * CELL))

        for sq in range(ROWS * COLS):
            bit = 1 << sq
            r, c = divmod(sq, COLS)
            cx = MARGIN + c * CELL + CELL // 2
            cy = MARGIN + r * CELL + CELL // 2
            if state.white & bit:
                pygame.draw.circle(screen, WHITE_COLOR, (cx, cy), CELL // 2 - 6)
                if sq == selected_sq:
                    pygame.draw.circle(screen, (0, 255, 0), (cx, cy), CELL // 2 - 6, 3)
            elif state.black & bit:
                pygame.draw.circle(screen, BLACK_COLOR, (cx, cy), CELL // 2 - 6)

        status_surf = font.render(status_msg, True, TEXT_COLOR)
        screen.blit(status_surf, (MARGIN, H - 50))

        for c in range(COLS):
            lbl = font.render(str(c), True, TEXT_COLOR)
            screen.blit(lbl, (MARGIN + c * CELL + CELL // 2 - 5, MARGIN - 25))

        pygame.display.flip()

    running = True
    while running:
        clock.tick(30)

        if (
            not state.is_terminal()
            and state.current_player() != human_plays
            and not agent_thinking
        ):
            agent_thinking = True
            agent_move_result[0] = None
            status_msg = "AI thinking..."
            t = threading.Thread(target=think_thread, daemon=True)
            t.start()

        if agent_thinking and agent_move_result[0] is not None:
            mv = agent_move_result[0]
            game_log.append({"player": "ai", "move": list(mv)})
            state = state.apply(mv[0], mv[1])
            agent_thinking = False
            agent_move_result[0] = None
            if state.is_terminal():
                status_msg = f"Game over: {state.winner()} wins!"
            else:
                status_msg = "Your turn"

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and not agent_thinking:
                if state.current_player() == human_plays and not state.is_terminal():
                    sq = pixel_to_sq(event.pos[0], event.pos[1], COLS)
                    if sq is not None:
                        if selected_sq is None:
                            bit = 1 << sq
                            own = state.white if human_plays == "white" else state.black
                            if own & bit:
                                selected_sq = sq
                                legal_from_selected = [
                                    to for (fr, to) in state.legal_moves() if fr == sq
                                ]
                        else:
                            if sq in legal_from_selected:
                                mv = (selected_sq, sq)
                                game_log.append({"player": "human", "move": list(mv)})
                                state = state.apply(mv[0], mv[1])
                                if state.is_terminal():
                                    status_msg = f"Game over: {state.winner()} wins!"
                                else:
                                    status_msg = "AI thinking..."
                            selected_sq = None
                            legal_from_selected = []

        draw()

    Path("results/human_games").mkdir(parents=True, exist_ok=True)
    log_path = Path("results/human_games") / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    with open(log_path, "w") as f:
        for entry in game_log:
            f.write(json.dumps(entry) + "\n")
    print(f"Game log saved to {log_path}")

    pygame.quit()


if __name__ == "__main__":
    run_gui()
