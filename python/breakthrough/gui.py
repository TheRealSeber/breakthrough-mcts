"""Human-vs-AI Pygame interface. Run with: python -m breakthrough.gui"""
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from datetime import datetime

import pygame
from pygame import gfxdraw


def _enable_dpi_awareness():
    if sys.platform != "win32":
        return
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

from breakthrough import GameState
from breakthrough._worker import compute_move

ROWS, COLS = 8, 8
AGENT_CFG = {"type": "uct", "iterations": 3000}
HUMAN_PLAYS = "white"

BG = (33, 31, 28)
PANEL_BG = (44, 42, 38)
PANEL_LINE = (66, 63, 57)
LIGHT_SQ = (236, 237, 210)
DARK_SQ = (115, 149, 82)
FRAME = (52, 60, 44)
SEL_HL = (250, 224, 90, 120)
LASTMOVE_HL = (250, 224, 90, 70)
MOVE_DOT = (30, 30, 30, 90)
CAPTURE_RING = (30, 30, 30, 115)
WHITE_EDGE = (150, 150, 140)
BLACK_EDGE = (12, 12, 16)
TEXT = (238, 238, 232)
TEXT_DIM = (158, 156, 148)
ACCENT = (140, 198, 110)
GOLD = (250, 205, 60)


def agent_param_lines(cfg):
    names = {
        "uct": "UCT (MCTS)",
        "rave": "RAVE",
        "pb": "Progressive Bias",
        "heuristic": "Heuristic (alpha-beta)",
        "random": "Random",
    }
    t = cfg["type"]
    lines = [("Algorithm", names.get(t, t))]
    if t in ("uct", "rave", "pb"):
        lines.append(("Iterations", str(cfg.get("iterations", 1000))))
        lines.append(("Exploration c", f"{cfg.get('c', 1.4142135623730951):.3f}"))
    if t == "rave":
        lines.append(("RAVE b²", str(cfg.get("rave_k", 0.01))))
    if t == "pb":
        lines.append(("Bias weight", str(cfg.get("bias_weight", 1.0))))
    if t == "heuristic":
        lines.append(("Search depth", str(cfg.get("depth", 5))))
    return lines


def fmt_duration(sec):
    sec = int(sec)
    return f"{sec // 60:02d}:{sec % 60:02d}"


def fmt_think(sec):
    m = int(sec) // 60
    return f"{m}:{sec - m * 60:04.1f}"


def _fmt_count(v):
    return f"{v // 1000}k" if v >= 1000 and v % 1000 == 0 else str(int(v))

ALGOS = [
    ("uct", "UCT"),
    ("rave", "RAVE"),
    ("pb", "Prog. Bias"),
    ("heuristic", "Heuristic"),
    ("random", "Random"),
]
PARAM_SPECS = {
    "iterations":  dict(label="Iterations",     default=10000, presets=[10000, 50000, 100000, 200000, 500000], fmt=lambda v: str(int(round(v)))),
    "c":           dict(label="Exploration c",  default=1.4142135623730951,  min=0.0, max=3.0,   step=0.1,  fmt=lambda v: f"{v:.2f}"),
    "rave_k":      dict(label="RAVE b²",    default=0.01,                min=0.0, max=1.0,   step=0.01, fmt=lambda v: f"{v:.2f}"),
    "bias_weight": dict(label="Bias weight",    default=1.0,                 min=0.0, max=5.0,   step=0.25, fmt=lambda v: f"{v:.2f}"),
    "depth":       dict(label="Search depth",   default=5,                   min=1,   max=7,     step=1,    fmt=lambda v: str(int(round(v)))),
}

ALGO_PARAMS = {
    "uct": ["iterations", "c"],
    "rave": ["iterations", "c", "rave_k"],
    "pb": ["iterations", "c", "bias_weight"],
    "heuristic": ["depth"],
    "random": [],
}

COLOR_CHOICES = [("white", "White"), ("black", "Black"), ("random", "Random")]


def _menu_button(screen, rect, label, font, selected, hover):
    if selected:
        bg, fg = ACCENT, (28, 28, 28)
    elif hover:
        bg, fg = PANEL_LINE, TEXT
    else:
        bg, fg = (54, 52, 47), TEXT
    pygame.draw.rect(screen, bg, rect, border_radius=10)
    pygame.draw.rect(screen, PANEL_LINE, rect, 2, border_radius=10)
    surf = font.render(label, True, fg)
    screen.blit(surf, surf.get_rect(center=rect.center))


def setup_screen(screen, SW, SH):
    clock = pygame.time.Clock()

    def font(px, bold=False):
        return pygame.font.SysFont("Segoe UI,Arial", int(px), bold=bold)

    f_title = font(SH * 0.040, bold=True)
    f_h = font(SH * 0.024, bold=True)
    f_lbl = font(SH * 0.020)
    f_btn = font(SH * 0.018, bold=True)
    f_val = font(SH * 0.022, bold=True)
    f_start = font(SH * 0.028, bold=True)
    f_hint = font(SH * 0.016)

    algo = AGENT_CFG.get("type", "uct")
    color = HUMAN_PLAYS
    param_values = {k: spec["default"] for k, spec in PARAM_SPECS.items()}
    for k in param_values:
        if k in AGENT_CFG:
            param_values[k] = AGENT_CFG[k]
    for k, spec in PARAM_SPECS.items():
        if spec.get("presets") and param_values[k] not in spec["presets"]:
            param_values[k] = min(spec["presets"], key=lambda pv: abs(pv - param_values[k]))
    dragging = None
    editing = None  
    edit_buffer = "" 
    caret_tick = 0
    player_name = "" 
    name_focus = False 
    def commit_edit():
        nonlocal editing
        if editing is None:
            return
        spec = PARAM_SPECS[editing]
        try:
            v = float(edit_buffer)
        except ValueError:
            editing = None
            return
        v = min(spec["max"], max(spec["min"], v))
        param_values[editing] = int(round(v)) if editing in ("iterations", "depth") else round(v, 6)
        editing = None

    top_pad = int(SH * 0.022)
    title_h = int(SH * 0.052)
    lbl_h = int(SH * 0.034)     
    bh = int(SH * 0.050)    
    row_h = int(SH * 0.046) 
    row_gap = int(SH * 0.013)
    sec_gap = int(SH * 0.020) 
    start_h = int(SH * 0.058)
    hint_h = int(SH * 0.028)
    step_w = int(SH * 0.05)
    MAX_PARAM_ROWS = 3       

    params_h = lbl_h + MAX_PARAM_ROWS * (row_h + row_gap)
    content_h = (top_pad + title_h
                 + (lbl_h + bh + sec_gap)  
                 + (lbl_h + bh + sec_gap) 
                 + (lbl_h + bh + sec_gap)  
                 + (params_h + sec_gap) 
                 + start_h + sec_gap + hint_h + top_pad)
    card_w = min(int(SW * 0.62), 1100)
    card_h = min(content_h, int(SH * 0.96))
    card_x, card_y = (SW - card_w) // 2, (SH - card_h) // 2
    pad = int(card_w * 0.07)
    left = card_x + pad
    right = card_x + card_w - pad
    inner_w = right - left
    gap = int(inner_w * 0.02)

    def text(f, s, col, x, y, anchor="topleft"):
        surf = f.render(s, True, col)
        rect = surf.get_rect()
        setattr(rect, anchor, (x, y))
        screen.blit(surf, rect)
        return rect

    while True:
        mx, my = pygame.mouse.get_pos()
        caret_tick += 1
        clicks = []
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            elif event.type == pygame.KEYDOWN:
                if name_focus:
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
                        name_focus = False
                    elif event.key == pygame.K_BACKSPACE:
                        player_name = player_name[:-1]
                    elif event.unicode and event.unicode.isprintable() and len(player_name) < 20:
                        player_name += event.unicode
                elif editing is not None:
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        commit_edit()
                    elif event.key == pygame.K_ESCAPE:
                        editing = None 
                    elif event.key == pygame.K_BACKSPACE:
                        edit_buffer = edit_buffer[:-1]
                    elif event.unicode.isdigit() and len(edit_buffer) < 9:
                        edit_buffer += event.unicode
                    elif event.unicode == "." and PARAM_SPECS[editing]["step"] < 1 and "." not in edit_buffer:
                        edit_buffer += event.unicode
                elif event.key == pygame.K_ESCAPE:
                    return None
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                clicks.append(event.pos)

        widgets = {"algo": {}, "color": {}, "minus": {}, "plus": {}, "track": {}, "preset": {}, "start": None}
        y = card_y + top_pad + title_h

        name_lbl_y = y
        y += lbl_h
        widgets["name"] = pygame.Rect(left, y, inner_w, bh)
        y += bh + sec_gap

        algo_lbl_y = y
        y += lbl_h
        n = len(ALGOS)
        bw = (inner_w - gap * (n - 1)) // n
        for i, (key, _) in enumerate(ALGOS):
            widgets["algo"][key] = pygame.Rect(left + i * (bw + gap), y, bw, bh)
        y += bh + sec_gap

        color_lbl_y = y
        y += lbl_h
        ncol = len(COLOR_CHOICES)
        cbw = (inner_w - gap * (ncol - 1)) // ncol
        for i, (key, _) in enumerate(COLOR_CHOICES):
            widgets["color"][key] = pygame.Rect(left + i * (cbw + gap), y, cbw, bh)
        y += bh + sec_gap

        param_lbl_y = y
        y += lbl_h
        params = ALGO_PARAMS[algo]
        param_rows = []
        for p in params:
            spec = PARAM_SPECS[p]
            if spec.get("presets"):
                presets = spec["presets"]
                bx0 = left + int(inner_w * 0.20)
                avail = right - bx0
                npre = len(presets)
                pbw = (avail - gap * (npre - 1)) // npre
                widgets["preset"][p] = [
                    (val, pygame.Rect(bx0 + k * (pbw + gap), y, pbw, row_h))
                    for k, val in enumerate(presets)
                ]
                param_rows.append((p, None))
                y += row_h + row_gap
                continue
            plus = pygame.Rect(right - step_w, y, step_w, row_h)
            vw = int(SH * 0.17)
            valbox = pygame.Rect(plus.x - vw, y, vw, row_h)
            minus = pygame.Rect(valbox.x - step_w, y, step_w, row_h)
            widgets["minus"][p] = minus
            widgets["plus"][p] = plus
            if PARAM_SPECS[p].get("slider"):
                tx0 = left + int(inner_w * 0.22)
                tx1 = minus.x - gap
                th = max(5, int(SH * 0.010))
                widgets["track"][p] = pygame.Rect(tx0, y + row_h // 2 - th // 2,
                                                  max(20, tx1 - tx0), th)
            param_rows.append((p, valbox))
            y += row_h + row_gap

        sbw = int(card_w * 0.34)
        start_y = param_lbl_y + lbl_h + MAX_PARAM_ROWS * (row_h + row_gap) + sec_gap
        widgets["start"] = pygame.Rect(card_x + card_w // 2 - sbw // 2, start_y, sbw, start_h)

        def slider_value_at(spec, track, x):
            frac = min(1.0, max(0.0, (x - track.x) / track.w))
            raw = spec["min"] + frac * (spec["max"] - spec["min"])
            snapped = round(raw / spec["step"]) * spec["step"]
            return min(spec["max"], max(spec["min"], round(snapped, 6)))

        for pos in clicks:
            if widgets["name"].collidepoint(pos):
                commit_edit()
                editing = None
                name_focus = True
                continue
            name_focus = False
            hit_value = next((p for p, vb in param_rows if vb is not None and vb.collidepoint(pos)), None)
            if hit_value is not None:
                commit_edit()     
                editing = hit_value
                edit_buffer = ""
                continue
            commit_edit()            
            for key, rect in widgets["algo"].items():
                if rect.collidepoint(pos):
                    algo = key
            for key, rect in widgets["color"].items():
                if rect.collidepoint(pos):
                    color = key
            for p, rect in widgets["minus"].items():
                if rect.collidepoint(pos):
                    spec = PARAM_SPECS[p]
                    param_values[p] = max(spec["min"], round(param_values[p] - spec["step"], 6))
            for p, rect in widgets["plus"].items():
                if rect.collidepoint(pos):
                    spec = PARAM_SPECS[p]
                    param_values[p] = min(spec["max"], round(param_values[p] + spec["step"], 6))
            for p, rects in widgets["preset"].items():
                for val, rect in rects:
                    if rect.collidepoint(pos):
                        param_values[p] = val
            for p, track in widgets["track"].items():
                if track.inflate(int(SH * 0.03), row_h).collidepoint(pos):
                    dragging = p
                    param_values[p] = slider_value_at(PARAM_SPECS[p], track, pos[0])
            if widgets["start"].collidepoint(pos):
                cfg = {"type": algo}
                for p in ALGO_PARAMS[algo]:
                    v = param_values[p]
                    cfg[p] = int(round(v)) if p in ("iterations", "depth") else v
                return cfg, color, player_name.strip()

        if dragging is not None:
            track = widgets["track"].get(dragging)
            if track is not None and pygame.mouse.get_pressed()[0]:
                param_values[dragging] = slider_value_at(PARAM_SPECS[dragging], track, mx)
            else:
                dragging = None

        screen.fill(BG)
        pygame.draw.rect(screen, PANEL_BG, (card_x, card_y, card_w, card_h), border_radius=18)
        pygame.draw.rect(screen, PANEL_LINE, (card_x, card_y, card_w, card_h), 2, border_radius=18)
        text(f_title, "Breakthrough — Game Setup", TEXT,
             card_x + card_w // 2, card_y + top_pad + title_h // 2, anchor="center")

        text(f_h, "Player name", ACCENT, left, name_lbl_y)
        nb = widgets["name"]
        pygame.draw.rect(screen, BG, nb, border_radius=8)
        pygame.draw.rect(screen, ACCENT if name_focus else (WHITE_EDGE if nb.collidepoint(mx, my) else PANEL_LINE),
                         nb, 2, border_radius=8)
        if player_name or name_focus:
            caret = "|" if (name_focus and (caret_tick // 30) % 2 == 0) else ""
            text(f_lbl, player_name + caret, TEXT, nb.x + int(SH * 0.014), nb.centery, anchor="midleft")
        else:
            text(f_lbl, "Click to enter your name…", TEXT_DIM, nb.x + int(SH * 0.014), nb.centery, anchor="midleft")

        text(f_h, "Algorithm", ACCENT, left, algo_lbl_y)
        for key, label in ALGOS:
            r = widgets["algo"][key]
            _menu_button(screen, r, label, f_btn, key == algo, r.collidepoint(mx, my))

        text(f_h, "Play as", ACCENT, left, color_lbl_y)
        for key, label in COLOR_CHOICES:
            r = widgets["color"][key]
            _menu_button(screen, r, label, f_btn, key == color, r.collidepoint(mx, my))

        text(f_h, "Parameters", ACCENT, left, param_lbl_y)
        if params:
            for p, valbox in param_rows:
                spec = PARAM_SPECS[p]
                if spec.get("presets"):
                    rects = widgets["preset"][p]
                    text(f_lbl, spec["label"], TEXT, left, rects[0][1].centery, anchor="midleft")
                    for val, rect in rects:
                        _menu_button(screen, rect, _fmt_count(val), f_btn,
                                     param_values[p] == val, rect.collidepoint(mx, my))
                    continue
                text(f_lbl, spec["label"], TEXT, left, valbox.centery, anchor="midleft")
                track = widgets["track"].get(p)
                if track is not None:
                    frac = min(1.0, max(0.0, (param_values[p] - spec["min"]) / (spec["max"] - spec["min"])))
                    hx = int(track.x + frac * track.w)
                    rad = track.h // 2
                    pygame.draw.rect(screen, (54, 52, 47), track, border_radius=rad)
                    if hx > track.x:
                        pygame.draw.rect(screen, ACCENT, pygame.Rect(track.x, track.y, hx - track.x, track.h),
                                         border_radius=rad)
                    grabbed = dragging == p or track.inflate(int(SH * 0.03), row_h).collidepoint(mx, my)
                    hr = int(SH * 0.015)
                    gfxdraw.filled_circle(screen, hx, track.centery, hr,
                                          (245, 245, 240) if grabbed else (214, 214, 208))
                    gfxdraw.aacircle(screen, hx, track.centery, hr, (70, 70, 70))
                _menu_button(screen, widgets["minus"][p], "−", f_val, False,
                             widgets["minus"][p].collidepoint(mx, my))
                _menu_button(screen, widgets["plus"][p], "+", f_val, False,
                             widgets["plus"][p].collidepoint(mx, my))
                editing_this = editing == p
                hov_val = valbox.collidepoint(mx, my)
                pygame.draw.rect(screen, BG, valbox, border_radius=8)
                pygame.draw.rect(screen, ACCENT if editing_this else (PANEL_LINE if not hov_val else WHITE_EDGE),
                                 valbox, 2, border_radius=8)
                if editing_this:
                    caret = "|" if (caret_tick // 30) % 2 == 0 else ""
                    text(f_val, edit_buffer + caret, TEXT, valbox.centerx, valbox.centery, anchor="center")
                else:
                    text(f_val, spec["fmt"](param_values[p]), TEXT, valbox.centerx, valbox.centery, anchor="center")
        else:
            text(f_lbl, "No parameters — plays uniformly at random.", TEXT_DIM,
                 left, param_lbl_y + int(SH * 0.05))

        start = widgets["start"]
        hov = start.collidepoint(mx, my)
        pygame.draw.rect(screen, (120, 180, 92) if hov else ACCENT, start, border_radius=12)
        text(f_start, "Start Game", (24, 24, 24), start.centerx, start.centery, anchor="center")
        text(f_hint, "Click a value to type it (Enter to confirm) · ESC to quit", TEXT_DIM,
             card_x + card_w // 2, start.bottom + sec_gap + hint_h // 2, anchor="center")

        pygame.display.flip()
        clock.tick(60)


def run_gui():
    _enable_dpi_awareness()
    pygame.init()
    info = pygame.display.Info()
    SW, SH = info.current_w, info.current_h
    os.environ.setdefault("SDL_VIDEO_WINDOW_POS", "0,0")
    screen = pygame.display.set_mode((SW, SH), pygame.NOFRAME)
    pygame.display.set_caption("Breakthrough 8x8")
    clock = pygame.time.Clock()

    setup = setup_screen(screen, SW, SH)
    if setup is None:
        pygame.quit()
        return
    AGENT_CFG, color_choice, player_name = setup
    if color_choice == "random":
        HUMAN_PLAYS = "white" if (int(time.time()) & 1) == 0 else "black"
    else:
        HUMAN_PLAYS = color_choice

    def sysfont(px, bold=False):
        return pygame.font.SysFont("Segoe UI,Arial", px, bold=bold)

    f_title = sysfont(int(SH * 0.030), bold=True)
    f_h = sysfont(int(SH * 0.022), bold=True)
    f_status = sysfont(int(SH * 0.020))
    f_small = sysfont(int(SH * 0.0145))
    f_win = sysfont(int(SH * 0.046), bold=True)
    f_btn = sysfont(int(SH * 0.024), bold=True)

    LABEL = int(SH * 0.026)
    MARGIN = int(SW * 0.028)
    PANEL_W = max(340, int(SW * 0.22))
    left_area_w = SW - PANEL_W - 2 * MARGIN
    CELL = min(left_area_w - 2 * LABEL, SH - 2 * MARGIN - 2 * LABEL) // 8
    BOARD = CELL * 8
    BOARD_X0 = MARGIN + LABEL + (left_area_w - 2 * LABEL - BOARD) // 2
    BOARD_Y0 = (SH - BOARD) // 2
    PANEL_X = SW - PANEL_W - MARGIN
    PANEL_RW = PANEL_W

    flip = HUMAN_PLAYS == "white"

    def logical_to_screen(r, c):
        return (ROWS - 1 - r, COLS - 1 - c) if flip else (r, c)

    def screen_to_logical(sr, sc):
        return (ROWS - 1 - sr, COLS - 1 - sc) if flip else (sr, sc)

    def sq_to_screen(sq):
        return logical_to_screen(*divmod(sq, COLS))

    def pixel_to_sq(x, y):
        sc = (x - BOARD_X0) // CELL
        sr = (y - BOARD_Y0) // CELL
        if 0 <= sr < ROWS and 0 <= sc < COLS:
            r, c = screen_to_logical(sr, sc)
            return r * COLS + c
        return None

    SS = 5

    def _piece_surf(is_white, selected):
        size = CELL * SS
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        c = size // 2
        r = int(CELL * 0.40 * SS)
        sh = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(sh, (0, 0, 0, 85), (c, c + int(CELL * 0.045 * SS)), r)
        s.blit(sh, (0, 0))
        if is_white:
            base, light, rim = (224, 224, 215), (252, 252, 248), (150, 150, 140)
            gloss_a = 95
        else:
            base, light, rim = (42, 42, 50), (86, 86, 100), (10, 10, 14)
            gloss_a = 70
        pygame.draw.circle(s, base, (c, c), r)
        lyr = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(lyr, (*light, 205), (c, c - int(r * 0.20)), int(r * 0.82))
        s.blit(lyr, (0, 0))
        pygame.draw.circle(s, rim, (c, c), r, max(2, int(CELL * 0.018 * SS)))
        gloss = pygame.Surface((size, size), pygame.SRCALPHA)
        gw, gh = int(r * 1.05), int(r * 0.55)
        pygame.draw.ellipse(gloss, (255, 255, 255, gloss_a),
                            pygame.Rect(c - gw // 2, c - int(r * 0.66), gw, gh))
        s.blit(gloss, (0, 0))
        if selected:
            pygame.draw.circle(s, GOLD, (c, c), r + int(CELL * 0.03 * SS),
                               max(3, int(CELL * 0.028 * SS)))
        return pygame.transform.smoothscale(s, (CELL, CELL)).convert_alpha()

    def _dot_surf(capture):
        size = CELL * SS
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        c = size // 2
        if capture:
            pygame.draw.circle(s, CAPTURE_RING, (c, c), int((CELL * 0.46) * SS),
                               int(CELL * 0.07 * SS))
        else:
            pygame.draw.circle(s, MOVE_DOT, (c, c), int(CELL * 0.16 * SS))
        return pygame.transform.smoothscale(s, (CELL, CELL)).convert_alpha()

    piece_sprites = {(w, sel): _piece_surf(w, sel) for w in (True, False) for sel in (True, False)}
    dot_sprites = {cap: _dot_surf(cap) for cap in (True, False)}

    ov_w = min(int(SW * 0.58), 920)
    ov_h = min(int(SH * 0.60), 640)
    ov_x, ov_y = (SW - ov_w) // 2, (SH - ov_h) // 2
    rate_y = ov_y + int(ov_h * 0.60)
    bpad = int(ov_w * 0.05)
    bgap = int(ov_w * 0.012)
    bw = (ov_w - 2 * bpad - 9 * bgap) // 10
    bh = min(bw, int(SH * 0.07))
    rating_rects = {
        n: pygame.Rect(ov_x + bpad + (n - 1) * (bw + bgap), rate_y, bw, bh)
        for n in range(1, 11)
    }
    quit_rect = pygame.Rect(ov_x + ov_w // 2 - int(ov_w * 0.16),
                            ov_y + ov_h - int(ov_h * 0.16),
                            int(ov_w * 0.32), int(ov_h * 0.11))

    state = GameState(ROWS, COLS)
    selected_sq = None
    legal_from_selected = []
    last_move = None
    hover_sq = None
    agent_thinking = False
    game_log = []
    frame = 0
    start_time = time.time()
    end_time = None
    difficulty_rating = None
    status_msg = "Your turn" if HUMAN_PLAYS == "white" else "AI's turn"
    human_think_total = 0.0
    ai_think_total = 0.0
    turn_start = start_time

    param_lines = agent_param_lines(AGENT_CFG)
    executor = ProcessPoolExecutor(max_workers=1)
    ai_future = None
    ai_base_seed = int(time.time()) & 0xFFFFFFFF

    def square_overlay(sr, sc, rgba):
        ov = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
        ov.fill(rgba)
        screen.blit(ov, (BOARD_X0 + sc * CELL, BOARD_Y0 + sr * CELL))

    def text(font, s, color, x, y, center=False, right=False):
        surf = font.render(s, True, color)
        rect = surf.get_rect()
        if center:
            rect.center = (x, y)
        elif right:
            rect.topright = (x, y)
        else:
            rect.topleft = (x, y)
        screen.blit(surf, rect)
        return rect

    def draw_panel(elapsed):
        pygame.draw.rect(screen, PANEL_BG, (PANEL_X, BOARD_Y0, PANEL_RW, BOARD), border_radius=14)
        pygame.draw.rect(screen, PANEL_LINE, (PANEL_X, BOARD_Y0, PANEL_RW, BOARD), 2, border_radius=14)
        px = PANEL_X + int(PANEL_RW * 0.08)
        pr = PANEL_X + PANEL_RW - int(PANEL_RW * 0.08)
        y = BOARD_Y0 + int(BOARD * 0.05)
        text(f_title, "Breakthrough", TEXT, px, y)
        y += int(SH * 0.05)
        text(f_h, "Opponent", ACCENT, px, y)
        y += int(SH * 0.038)
        for k, v in param_lines:
            text(f_small, k, TEXT_DIM, px, y)
            text(f_status, v, TEXT, pr, y - int(SH * 0.003), right=True)
            y += int(SH * 0.037)
        y += int(SH * 0.02)
        pygame.draw.line(screen, PANEL_LINE, (px, y), (pr, y), 1)
        y += int(SH * 0.025)
        text(f_h, "Game", ACCENT, px, y)
        y += int(SH * 0.038)
        hsum, asum = human_think_total, ai_think_total
        if not state.is_terminal():
            live = time.time() - turn_start
            if state.current_player() == HUMAN_PLAYS:
                hsum += live
            else:
                asum += live
        for k, v in [("You play", HUMAN_PLAYS.capitalize()),
                     ("Move", str(state.get_move_count())),
                     ("Time", fmt_duration(elapsed)),
                     ("Your think time", fmt_think(hsum)),
                     ("AI think time", fmt_think(asum))]:
            text(f_small, k, TEXT_DIM, px, y)
            text(f_status, v, TEXT, pr, y - int(SH * 0.003), right=True)
            y += int(SH * 0.037)
        ty = BOARD_Y0 + BOARD - int(BOARD * 0.10)
        if not state.is_terminal():
            is_white_turn = state.current_player() == "white"
            cx = px + int(SH * 0.013)
            gfxdraw.filled_circle(screen, cx, ty, int(SH * 0.013),
                                  (245, 245, 240) if is_white_turn else (50, 50, 56))
            gfxdraw.aacircle(screen, cx, ty, int(SH * 0.013),
                             WHITE_EDGE if is_white_turn else BLACK_EDGE)
            text(f_status, status_msg, TEXT, px + int(SH * 0.035), ty - int(SH * 0.012))

    def draw_overlay(elapsed):
        veil = pygame.Surface((SW, SH), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 170))
        screen.blit(veil, (0, 0))
        pygame.draw.rect(screen, (246, 246, 241), (ov_x, ov_y, ov_w, ov_h), border_radius=18)
        pygame.draw.rect(screen, ACCENT, (ov_x, ov_y, ov_w, ov_h), 4, border_radius=18)
        won = state.winner() == HUMAN_PLAYS
        cx = ov_x + ov_w // 2
        text(f_win, "You win!" if won else "You lose", (40, 40, 40), cx, ov_y + int(ov_h * 0.11), center=True)
        # stats row
        stats = [("Time", fmt_duration(elapsed)),
                 ("Moves", str(len(game_log))),
                 ("Winner", (state.winner() or "-").capitalize())]
        n = len(stats)
        for i, (k, v) in enumerate(stats):
            sx = ov_x + int(ov_w * (0.2 + 0.3 * i))
            text(f_h, v, (40, 40, 40), sx, ov_y + int(ov_h * 0.30), center=True)
            text(f_small, k, (120, 120, 120), sx, ov_y + int(ov_h * 0.38), center=True)
        text(f_small,
             f"Think time — You: {fmt_think(human_think_total)}    AI: {fmt_think(ai_think_total)}",
             (90, 90, 90), cx, ov_y + int(ov_h * 0.45), center=True)
        text(f_status, "Rate AI difficulty (1–10) — required:", (70, 70, 70), cx, ov_y + int(ov_h * 0.52), center=True)
        for n_, rect in rating_rects.items():
            sel = difficulty_rating == n_
            pygame.draw.rect(screen, ACCENT if sel else (228, 228, 222), rect, border_radius=8)
            pygame.draw.rect(screen, (150, 150, 145), rect, 2, border_radius=8)
            text(f_status, str(n_), (255, 255, 255) if sel else (60, 60, 60),
                 rect.centerx, rect.centery, center=True)
        rated = difficulty_rating is not None
        if not rated:
            text(f_small, "Select a difficulty rating to save and quit.", (176, 64, 56),
                 cx, quit_rect.top - int(ov_h * 0.045), center=True)
        pygame.draw.rect(screen, (60, 60, 64) if rated else (158, 158, 160), quit_rect, border_radius=10)
        text(f_btn, "Save & Quit", (245, 245, 240) if rated else (212, 212, 212),
             quit_rect.centerx, quit_rect.centery, center=True)

    def draw(elapsed):
        screen.fill(BG)
        pygame.draw.rect(screen, FRAME, (BOARD_X0 - 4, BOARD_Y0 - 4, BOARD + 8, BOARD + 8), border_radius=6)
        for sr in range(ROWS):
            for sc in range(COLS):
                color = LIGHT_SQ if (sr + sc) % 2 == 0 else DARK_SQ
                pygame.draw.rect(screen, color, (BOARD_X0 + sc * CELL, BOARD_Y0 + sr * CELL, CELL, CELL))
        if last_move:
            for s in last_move:
                square_overlay(*sq_to_screen(s), LASTMOVE_HL)
        if selected_sq is not None:
            square_overlay(*sq_to_screen(selected_sq), SEL_HL)
        if hover_sq is not None:
            sr, sc = sq_to_screen(hover_sq)
            pygame.draw.rect(screen, (255, 255, 255), (BOARD_X0 + sc * CELL, BOARD_Y0 + sr * CELL, CELL, CELL), 2)
        for sc in range(COLS):
            c = screen_to_logical(0, sc)[1]
            text(f_small, str(c), TEXT_DIM, BOARD_X0 + sc * CELL + CELL // 2, BOARD_Y0 + BOARD + int(LABEL * 0.4), center=True)
        for sr in range(ROWS):
            r = screen_to_logical(sr, 0)[0]
            text(f_small, str(r), TEXT_DIM, BOARD_X0 - int(LABEL * 0.5), BOARD_Y0 + sr * CELL + CELL // 2, center=True)
        for sq in range(ROWS * COLS):
            bit = 1 << sq
            sr, sc = sq_to_screen(sq)
            tx, ty = BOARD_X0 + sc * CELL, BOARD_Y0 + sr * CELL
            if state.white & bit:
                screen.blit(piece_sprites[(True, sq == selected_sq)], (tx, ty))
            elif state.black & bit:
                screen.blit(piece_sprites[(False, sq == selected_sq)], (tx, ty))
        for to_sq in legal_from_selected:
            sr, sc = sq_to_screen(to_sq)
            cap = bool((state.white | state.black) & (1 << to_sq))
            screen.blit(dot_sprites[cap], (BOARD_X0 + sc * CELL, BOARD_Y0 + sr * CELL))
        draw_panel(elapsed)
        if state.is_terminal():
            draw_overlay(elapsed)
        pygame.display.flip()

    running = True
    while running:
        clock.tick(60)
        frame += 1
        terminal = state.is_terminal()
        if terminal and end_time is None:
            end_time = time.time()
        elapsed = (end_time or time.time()) - start_time

        if not terminal and state.current_player() != HUMAN_PLAYS and ai_future is None:
            moves = [tuple(e["move"]) for e in game_log]
            seed = (ai_base_seed + len(moves)) & 0xFFFFFFFF
            ai_future = executor.submit(compute_move, AGENT_CFG, ROWS, COLS, moves, seed)

        if ai_future is not None and ai_future.done():
            dt = time.time() - turn_start
            ai_think_total += dt
            turn_start = time.time()
            mv = ai_future.result()
            ai_future = None
            game_log.append({"player": "ai", "move": list(mv), "think_sec": round(dt, 3)})
            state = state.apply(mv[0], mv[1])
            last_move = (mv[0], mv[1])

        agent_thinking = ai_future is not None

        if not agent_thinking and not terminal and state.current_player() == HUMAN_PLAYS:
            hover_sq = pixel_to_sq(*pygame.mouse.get_pos())
        else:
            hover_sq = None

        if terminal:
            status_msg = "You win!" if state.winner() == HUMAN_PLAYS else "You lose."
        elif agent_thinking:
            status_msg = "AI is thinking" + "." * (1 + (frame // 30) % 3)
        elif state.current_player() == HUMAN_PLAYS:
            status_msg = "Your turn"
        else:
            status_msg = "AI's turn"

        for event in pygame.event.get():
            may_exit = (not terminal) or difficulty_rating is not None
            if event.type == pygame.QUIT:
                if may_exit:
                    running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if may_exit:
                    running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if terminal:
                    for n_, rect in rating_rects.items():
                        if rect.collidepoint(event.pos):
                            difficulty_rating = n_
                    if quit_rect.collidepoint(event.pos) and difficulty_rating is not None:
                        running = False
                elif not agent_thinking and state.current_player() == HUMAN_PLAYS:
                    sq = pixel_to_sq(event.pos[0], event.pos[1])
                    if sq is not None:
                        if selected_sq is None:
                            bit = 1 << sq
                            own = state.white if HUMAN_PLAYS == "white" else state.black
                            if own & bit:
                                selected_sq = sq
                                legal_from_selected = [to for (fr, to) in state.legal_moves() if fr == sq]
                        else:
                            if sq in legal_from_selected:
                                dt = time.time() - turn_start
                                human_think_total += dt
                                turn_start = time.time()
                                mv = (selected_sq, sq)
                                game_log.append({"player": "human", "move": list(mv), "think_sec": round(dt, 3)})
                                state = state.apply(mv[0], mv[1])
                                last_move = mv
                            selected_sq = None
                            legal_from_selected = []

        draw(elapsed)

    executor.shutdown(wait=False, cancel_futures=True)

    total_time = (end_time or time.time()) - start_time
    Path("results/human_games").mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in player_name).strip("_")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{safe_name}_{stamp}.jsonl" if safe_name else f"{stamp}.jsonl"
    log_path = Path("results/human_games") / fname
    with open(log_path, "w") as f:
        for entry in game_log:
            f.write(json.dumps(entry) + "\n")
        n_human = sum(1 for e in game_log if e["player"] == "human")
        n_ai = sum(1 for e in game_log if e["player"] == "ai")
        summary = {
            "player_name": player_name,
            "winner": state.winner(),
            "n_moves": len(game_log),
            "duration_sec": round(total_time, 1),
            "human_plays": HUMAN_PLAYS,
            "agent": AGENT_CFG,
            "difficulty_rating": difficulty_rating,
            "human_think_sec": round(human_think_total, 2),
            "ai_think_sec": round(ai_think_total, 2),
            "human_avg_think_sec": round(human_think_total / n_human, 2) if n_human else 0.0,
            "ai_avg_think_sec": round(ai_think_total / n_ai, 2) if n_ai else 0.0,
        }
        f.write(json.dumps(summary) + "\n")
    print(f"Game log saved to {log_path}")

    pygame.quit()


if __name__ == "__main__":
    run_gui()
