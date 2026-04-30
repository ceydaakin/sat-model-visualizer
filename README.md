# sat-model-visualizer

[![Tests](https://github.com/ceydaakin/sat-model-visualizer/actions/workflows/test.yml/badge.svg)](https://github.com/ceydaakin/sat-model-visualizer/actions/workflows/test.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Three textual visualisations of a DPLL SAT-solver proof — produced from
the solver's CNF, BCP trace, and final model.

The module reads:

| File                       | Source                                         |
| -------------------------- | ---------------------------------------------- |
| `initial_cnf.txt`          | A CNF dump (variable map + clause list).       |
| `execution_trace_*.txt`    | One or more BCP traces, one per decision-level run. |
| `final_model.txt`          | The solver's final SAT verdict + variable assignments. |

…and emits a single output file containing:

1. **Row Form** — a compact certificate that the model satisfies every clause.
2. **Inference Form** — symbolic clause simplification along the BCP trace.
3. **Tree Form** — an ASCII search tree showing decisions, propagations, conflicts, and the final SAT branch.

> Built as the visualisation stage of an academic SAT-solver pipeline
> (İTÜ BLG 345E — Logic and Computability, Project #5),
> kept here as a small standalone tool.

---

## Example

Given the four-clause CNF `(¬A∨B) ∧ (¬B∨¬C) ∧ (C∨A) ∧ (¬B∨C)` and the trace
of a DPLL run that backtracks once and then succeeds, the tool produces:

### 1. Row Form

```
Model: A=0, B=0, C=1

C1 | - +   | 1 + 0 = 1
C2 |   - - | 1 + 0 = 1
C3 | +   + | 0 + 1 = 1
C4 |   - + | 1 + 1 = 1
```

Every clause line ends in `= 1` — the model satisfies the whole CNF.

### 2. Inference Form

```
C1 | -A + B
C2 | -B + -C
C3 | C + A
C4 | -B + C
---------- Decision L=2
C2 | -C
C3 | C + A
C4 | C
---------- Unit L=-3
C3 | A
C4 | 0 | Conflict
---------- Decision L=-2
C1 | -A
C3 | C + A
---------- Unit L=-1
C3 | C
---------- Unit L=3
Satisfied
```

Each separator marks a DECIDE or a UNIT propagation; the surviving clauses
underneath are the simplified CNF after that step. An empty clause is
rendered `0 | Conflict`.

### 3. Tree Form

```
Root
 |
 |----- Decide B = 1
 |       |
 |       |----- Unit C = 0
 |       |
 |       |----- Conflict!
 |
 |----- Decide B = 0
         |
         |----- Unit A = 0
         |
         |----- Unit C = 1
         |
         |----- Satisfied!
```

---

## Install

No third-party dependencies. Python 3.10 or newer.

```bash
git clone https://github.com/ceydaakin/sat-model-visualizer
cd sat-model-visualizer
```

Optional editable install (registers a `sat-visualize` console script):

```bash
pip install -e .
```

## Usage

```bash
python sat_visualizer.py \
    --cnf   path/to/initial_cnf.txt \
    --model path/to/final_model.txt \
    --trace path/to/execution_trace_1.txt \
    --trace path/to/execution_trace_2.txt \
    --out   output.txt
```

`--trace` may be repeated; trace files are concatenated in the order given.

If you installed via `pip install -e .`, the same is available as:

```bash
sat-visualize --cnf … --model … --trace … --out output.txt
```

## Tests

```bash
python run_tests.py
```

Four fixtures live under `tests/`:

| Fixture                  | V | C | Decisions | Conflicts | Description                          |
| ------------------------ | - | - | --------- | --------- | ------------------------------------ |
| `test_1_spec_example`    | 3 | 4 | 2         | 1         | The example from the project spec.   |
| `test_2_pure_sat`        | 2 | 3 | 1         | 0         | One decision, one propagation.       |
| `test_3_multi_dl`        | 4 | 4 | 2         | 0         | Two decision levels, no backtrack.   |
| `test_4_two_backtracks`  | 4 | 5 | 4         | 2         | DL-1 conflict + DL-2 conflict + SAT. |

The driver checks each output's structural invariants (every clause
satisfied; one DECIDE separator per DECIDE event; correct counts of
`Conflict!` / `Satisfied!` nodes).

## Input file formats

The full grammar is documented in [REPORT.md](REPORT.md). In short:

### `initial_cnf.txt` — only the CLAUSE LIST is needed

```
[C_ID] | [Literals (Signed Ints)] | [Watched Indices]
------------------------------------------------------------------
C1     | [-1, 2]                  | [0, 1]
C2     | [-2, -3]                 | [0, 1]
…
```

### `final_model.txt`

```
STATUS: SAT

--- FINAL VARIABLE STATE ---
1 | FALSE
2 | FALSE
3 | TRUE
```

### `execution_trace_*.txt`

Only the `BCP EXECUTION LOG` block is consumed:

```
[DL1] DECIDE     L=2    |
[DL1] UNIT       L=-3   | C2
[DL1] ASSIGN     L=-3   |
[DL1] CONFLICT          | Violation: C4
[DL1] BACKTRACK         |
```

## Project layout

```
.
├── sat_visualizer.py          # Module — parsers + 3 renderers + CLI
├── run_tests.py               # Fixture-driven test driver
├── pyproject.toml             # Packaging metadata
├── REPORT.md                  # Technical write-up of the three forms
├── README.md                  # You are here
├── LICENSE                    # MIT
├── .github/workflows/test.yml # CI on Linux / macOS / Windows × Py 3.10–3.13
└── tests/
    ├── test_1_spec_example/
    ├── test_2_pure_sat/
    ├── test_3_multi_dl/
    └── test_4_two_backtracks/
```

## License

[MIT](LICENSE) © 2026 Ceyda Akın
