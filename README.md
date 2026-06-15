# Breakthrough 8×8 — MCTS / UCT

Projekt na przedmiot Metody Sztucznej Inteligencji 2 (MSI 2): porównanie MCTS
z regułą UCT i jego rozszerzeń (RAVE, Progressive Bias) oraz heurystyki
alpha-beta w grze Breakthrough 8×8.

Silnik gry i agenci w **Rust** (bitboardy, Zobrist hashing), orkiestracja,
GUI i analiza w **Python 3.12**, wiązanie przez **PyO3 + maturin**.

**Autorzy:** Hubert Sobociński, Sebastian Rydz

## Instalacja

Wymagania: Rust ≥ 1.78, Python 3.12, `uv`.

```bash
git clone git@github.com:TheRealSeber/breakthrough-mcts.git
cd breakthrough-mcts
uv venv && source .venv/bin/activate  
uv pip install maturin pytest scipy seaborn
maturin develop --release 
```

## Eksperymenty

Plansza 8×8, 100 partii na parę agentów. Reprodukowalne (master seed → seedy
partii), wznawialne. Wyniki w `results/<nazwa>/games.jsonl`.

```bash
python -m breakthrough.experiments.run_h1   # RAVE vs UCT (5k–100k iter)
python -m breakthrough.experiments.run_h2   # Progressive Bias vs UCT
python -m breakthrough.experiments.run_h3   # heurystyka (d=5) vs UCT (500–300k)
python -m breakthrough.experiments.run_h4   # przewaga pierwszego gracza
python -m breakthrough.experiments.run_h5   # strojenie stałej eksploracji c
python -m breakthrough.experiments.run_h6   # czas decyzji
```

## Wykresy

Każdy skrypt liczy statystyki (win-rate, 95% CI Wilsona, istotność) i zapisuje
wykresy PDF do `report/figures/`:

```bash
python notebooks/analysis_h1.py    # ... analysis_h2.py ... analysis_h6.py
python notebooks/analysis_cross.py # analizy przekrojowe H1–H6
python notebooks/analysis_human.py # partie człowiek vs AI
```

Wspólny motyw i funkcje pomocnicze: `notebooks/shared_utils.py`.

## GUI

```bash
python -m breakthrough.gui
```

Ekran startowy pozwala wybrać algorytm, budżet i kolor. Partie logowane do `results/human_games/`.

## Raport

```bash
cd report && make report     # PDF: report/main.pdf (wymaga TeX Live / XeLaTeX)
```

## Wyniki

Szczegóły w raporcie końcowym (`report/main.pdf`).

## Licencja

Projekt akademicki. W razie pytań — kontakt z autorami.
