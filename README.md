# Breakthrough 6×6 — MCTS / UCT

Projekt na przedmiot Metody Sztucznej Inteligencji 2 (MSI 2) — porównanie
algorytmu Monte Carlo Tree Search z regułą UCT i jego rozszerzeń (RAVE,
Progressive Bias) oraz heurystyki alpha-beta w grze Breakthrough na
planszy 6×6.

**Autorzy:** Hubert Sobociński, Sebastian Rydz

## Stos technologiczny

- **Rust** — silnik gry, agenci MCTS (UCT, RAVE, Progressive Bias),
  heurystyka alpha-beta. Reprezentacja bitboardowa (`u64`), Zobrist hashing.
- **Python 3.12** — orkiestracja eksperymentów, GUI, analiza statystyczna.
- **PyO3 + maturin** — wiązanie Rust ↔ Python.
- **LaTeX (XeLaTeX)** — raport końcowy.

## Wymagania systemowe

- Rust ≥ 1.78 (`rustup`)
- Python 3.12 (`pyenv` lub system)
- `uv` (manager zależności Pythona)
- `maturin` (zostanie zainstalowany przez `uv pip`)
- (Opcjonalnie, do raportu) TeX Live z pakietami:
  `texlive-binextra`, `texlive-xetex`, `texlive-langeuropean`,
  `texlive-bibtexextra`, `texlive-langpolish`, `texlive-fontsrecommended`

## Instalacja

```bash
# Klon
git clone git@github.com:TheRealSeber/breakthrough-mcts.git
cd breakthrough-mcts

# Środowisko Python
uv venv
source .venv/bin/activate         # Linux/macOS
# .venv\Scripts\activate          # Windows

# Zależności + build rozszerzenia Rust
uv pip install maturin pytest scipy seaborn
maturin develop --release         # tryb release dla wydajności
```

Po `maturin develop` paczka `breakthrough` jest dostępna w bieżącym venvie.

## Smoke test

```bash
python -c "from breakthrough import GameState; g = GameState(6, 6); print(g)"
```

Powinno wyświetlić planszę 6×6 z białymi pionkami w rzędach 0–1 i czarnymi
w rzędach 4–5.

## Walidacja silnika (wymagane przed eksperymentami)

```bash
pytest tests/test_rust_vs_python.py -v
```

Test gra 1000 losowych partii równolegle przez silnik Rust i referencyjny
silnik Python, sprawdzając identyczność legalnych ruchów, stanu
terminalnego i zwycięzcy w każdym kroku. **Niepoprawny silnik
unieważniłby wyniki eksperymentów.**

## Uruchamianie eksperymentów

Wszystkie eksperymenty są w pełni reprodukowalne (master seed → SHA-256 →
seedy partii). Wyniki zapisywane są do `results/<nazwa>/games.jsonl`
(format crash-safe append-only, wznawialny przy ponownym uruchomieniu).

```bash
# H1: RAVE vs UCT (budżety 1k, 5k, 10k iteracji); 900 partii, ~10–15 min
python -m breakthrough.experiments.run_h1

# H2: Progressive Bias vs UCT; 900 partii, ~10–15 min
python -m breakthrough.experiments.run_h2

# H3: Heurystyka (alpha-beta d=5) vs UCT (200–10k iter); 900 partii, ~5 min
python -m breakthrough.experiments.run_h3

# H3 rozszerzony: dodaje UCT(20k, 50k, 100k); 360 partii, ~1–2 h
python -m breakthrough.experiments.run_h3_extended

# H4: Przewaga pierwszego gracza, 3 rozmiary planszy (6×6, 6×8, 8×8);
#     1500 partii, ~25–30 min
python -m breakthrough.experiments.run_h4
```

Skrypty wznawialne: jeśli przerwiesz uruchamianie, kolejne wywołanie
pomija już rozegrane partie.

## Generowanie wykresów

Po uruchomieniu eksperymentów:

```bash
python notebooks/analysis_h1.py
python notebooks/analysis_h2.py
python notebooks/analysis_h3.py
python notebooks/analysis_h4.py
```

Wykresy PDF zapisywane są do `report/figures/`.

## Interfejs człowiek–komputer (GUI)

```bash
python -m breakthrough.gui
```

Przeciwnik domyślny: UCT z 3000 iteracji, ludzki gracz gra białymi.
(Konfigurację można zmienić w `python/breakthrough/gui.py`, linia 43.)

Każda rozegrana partia jest logowana do
`results/human_games/<timestamp>.jsonl` (lista wszystkich ruchów).

## Raport

Konspekt projektu (PDF):

```bash
cd konspekt && make build
```

Raport końcowy (PDF):

```bash
cd report && make report
```

PDF: `report/main.pdf`. Wymaga pełnej instalacji TeX Live (zob. „Wymagania
systemowe" wyżej).

## Struktura repozytorium

```
breakthrough-mcts/
├── Cargo.toml, pyproject.toml       # build
├── src/                              # Rust
│   ├── game.rs                       # bitboardy, ruchy, terminale
│   ├── mcts/
│   │   ├── uct.rs                    # vanilla UCT
│   │   ├── rave.rs                   # UCT + RAVE
│   │   └── progressive_bias.rs       # UCT + Progressive Bias
│   └── heuristic.rs                  # alpha-beta z głębokością 5
├── python/breakthrough/
│   ├── reference_game.py             # referencyjny silnik (walidacja krzyżowa)
│   ├── agents.py                     # wrapper Python + RandomAgent
│   ├── gui.py                        # Pygame GUI
│   └── experiments/
│       ├── harness.py                # runner z multiprocessing + JSONL
│       └── run_h{1,2,3,3_extended,4}.py
├── tests/test_rust_vs_python.py      # gate poprawności silnika
├── notebooks/                        # skrypty analityczne
├── konspekt/                         # konspekt LaTeX
├── report/                           # raport LaTeX + figures/
└── results/                          # wyniki JSONL (.gitignore)
```

## Hipotezy badawcze i wyniki

| Hipoteza | Wynik | Status |
|---|---|---|
| H1: RAVE > UCT | 50,0% / 48,3% / 30,0% wygranych RAVE (1k / 5k / 10k iter) | **Sfalsyfikowana** |
| H2: Progressive Bias > UCT | 41,7% / 53,3% / 53,3% wygranych PB | **Niejednoznaczna** |
| H3: Heurystyka > UCT przy niskich, < UCT przy wysokich budżetach | 100% → 85% przy budżetach 200 → 100k iter | **Częściowo potwierdzona** |
| H4: Przewaga białych maleje z planszą | 49,4% / 50,8% / 49,4% (6×6, 6×8, 8×8) | **Sfalsyfikowana** |

Szczegóły metodologii i interpretacji w raporcie końcowym (`report/main.pdf`).

## Licencja

Projekt akademicki — nie przewidujemy publicznego użytkowania. Dla pytań
proszę o kontakt z autorami.
