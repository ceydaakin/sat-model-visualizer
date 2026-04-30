# BLG 345E — Project #5 Technical Report
## SAT Model Visualizer

This report describes the implementation of the visualisation module that
acts as the final stage of the SAT-solver pipeline. It consumes the outputs
of Project #2 (CNF dump), Project #3 (per-decision-level BCP traces), and
Project #4 (final model) and emits three textual representations of the
satisfiability proof — the *Row*, *Inference*, and *Tree* forms — into a
single output file.

The full implementation lives in `sat_visualizer.py`. The driver is `run_tests.py`
and four worked examples sit under `tests/`. All three visualisations are
produced by a single invocation:

```
python sat_visualizer.py \
    --cnf  initial_cnf.txt \
    --model final_model.txt \
    --trace execution_trace_1.txt --trace execution_trace_2.txt \
    --out  output.txt
```

---

## 1. Row Form — Verifying the Model

**Goal.** For every clause in the original CNF, prove that the final model
makes at least one literal true.

**Logic.**
A row is constructed in three columns:

```
<C-id> | <sign-row> | <evaluation> = <result>
```

1.  **Sign row.** For every variable id `v` (in ascending order) we look up
    the literal on `v` (if any) inside the clause:
    `+` if the clause contains `+v`, `-` if it contains `-v`, blank otherwise.
    This gives a fixed-width column-aligned grid, one cell per variable.

2.  **Evaluation.** We walk the same variable columns left-to-right.
    For every column that contains a literal we print `1` if that literal
    evaluates to true under the model, else `0`. The function
    `lit_value(lit, model)` performs the obvious sign-aware evaluation:

    ```
    lit_value(+v, model) = model[v]
    lit_value(-v, model) = not model[v]
    ```

3.  **Result.** We print `= 1` when *any* literal in the clause evaluates
    to true (Boolean OR over the literals), otherwise `= 0`. In a
    correctly-found SAT model every clause must end with `= 1`; this is
    asserted in the test harness.

The variable-column ordering — rather than clause-literal ordering — is
chosen because it visually aligns the sign row with the value row. The
result is a compact, glanceable certificate that the model satisfies the
formula.

---

## 2. Inference Form — Replaying the Trace

**Goal.** Reproduce the symbolic state of the CNF after every step in
the BCP trace, making the dependency between decisions and propagations
visible.

**Logic.**
The trace is a flat list of `TraceEvent` tuples. We classify each event
into one of six kinds (`DECIDE`, `UNIT`, `ASSIGN`, `CONFLICT`,
`BACKTRACK`, `SATISFIED`) using a single regex and dispatch on `kind`:

| Event       | Effect on the inference rendering                                        |
| ----------- | ------------------------------------------------------------------------ |
| `DECIDE`    | Snapshot current clauses, apply the literal, print divider + new state.  |
| `UNIT`      | Apply the literal, print divider + new state.                            |
| `ASSIGN`    | Skipped. Always paired with the preceding DECIDE/UNIT and adds nothing. |
| `CONFLICT`  | Skipped — the empty clause was already marked when the unit was applied. |
| `BACKTRACK` | Pop the most recent snapshot, restoring the pre-decision clause state.   |
| `SATISFIED` | Emit a final `Satisfied` line.                                           |

The clause-simplification primitive `apply_literal(clauses, lit)`:

* drops every clause that contains `lit` (it became true),
* removes `-lit` from every other clause (it became false),
* returns the first clause that became empty as the conflict id, if any.

Because every `DECIDE` pushes a snapshot and every `BACKTRACK` pops one,
the rendering naturally supports chronological backtracking — including
nested decision levels (validated by `test_4_two_backtracks`, which
re-enters DL 2 with two different branches after a failure at DL 1).

The `0 | Conflict` annotation on the empty clause matches the spec's
sample exactly. The same divider style (`---------- Decision L=...`,
`---------- Unit L=...`) is used throughout for consistent diffing.

---

## 3. Tree Form — Visualising the Search Tree

**Goal.** Show the DPLL search graphically: each decision creates a
branch; each propagation, conflict, or success is a child of the
deepest open decision.

**Building the tree.**
We keep a stack `parents` indexed by decision level: `parents[d]` is the
node currently representing depth `d`. `parents[0]` is the synthetic
`Root`, which also catches any DL-0 unit propagations (none in the
provided sample, but supported).

```
DECIDE   at DL d   →  new node attached to parents[d-1]; push as parents[d]
UNIT     at DL d   →  leaf attached to parents[d]
CONFLICT           →  leaf "Conflict!" on parents[-1]
SATISFIED          →  leaf "Satisfied!" on parents[-1]
BACKTRACK          →  pop parents (the failed decision is closed)
ASSIGN             →  ignored
```

This mapping makes a sibling-of-Decide relationship between two opposing
DL-1 decisions (as in the sample), and a deeper-nested relationship when
DL 2 decisions follow DL 1 propagations (`test_3_multi_dl`,
`test_4_two_backtracks`).

**Rendering.**
The recursive helper `_render_children` carries a `prefix` string that
locates the column where each child's `|` lives. After every node line
we emit a 7-space indent so the next-deeper `|` aligns directly under
the dashes (`|----- `). The continuation character at the parent column
is:

* `|`  — when the parent still has more siblings below (its branch
  remains "open"),
* ` ` (space) — when the parent is the last child (its column collapses).

The result reproduces the spec example byte-for-byte (apart from the one
labelling inconsistency in the spec: `Assign C = 0` vs `Unit C = 0`,
where the underlying trace event is plainly `UNIT`, so we use `Unit`).

---

## 4. Test Suite

Four test fixtures live under `tests/`. Each fixture contains the three
input file types plus the produced `output.txt`.
The test driver verifies, for each output:

* **Row form** — `Model:` header is present and *every* clause line
  ends with `= 1` (i.e. the certificate is a valid satisfaction proof).
* **Inference form** — there is exactly one `---------- Decision`
  divider for every `DECIDE` event in the trace, and `Satisfied`
  appears iff a `SATISFIED` event was seen.
* **Tree form** — `Root` is present; the count of `Decide`,
  `Conflict!`, and `Satisfied!` nodes matches the trace.

| Test                      | V | C | DECIDEs | Conflicts | Satisfied | Notes                                      |
| ------------------------- | - | - | ------- | --------- | --------- | ------------------------------------------ |
| `test_1_spec_example`     | 3 | 4 | 2       | 1         | 1         | The exact example from the spec.           |
| `test_2_pure_sat`         | 2 | 3 | 1       | 0         | 1         | One decision, one unit, no backtracking.   |
| `test_3_multi_dl`         | 4 | 4 | 2       | 0         | 1         | Two decision levels, no backtracking.      |
| `test_4_two_backtracks`   | 4 | 5 | 4       | 2         | 1         | DL-1 conflict + DL-2 conflict, then SAT.   |

All four pass:

```
$ python3 run_tests.py
Running tests in /…/blg345e_project5/tests
  [PASS] test_1_spec_example  (decides=2, conflicts=1, satisfied=1)
  [PASS] test_2_pure_sat      (decides=1, conflicts=0, satisfied=1)
  [PASS] test_3_multi_dl      (decides=2, conflicts=0, satisfied=1)
  [PASS] test_4_two_backtracks (decides=4, conflicts=2, satisfied=1)

4 passed, 0 failed
```

The spec-example output is byte-identical with the project description
on every component except the noted `Unit`/`Assign` label, which we
explicitly chose to keep consistent with the trace data.

---

## 5. Implementation Notes & Design Choices

* **Single file, ~400 lines.** All logic — parsers, three renderers,
  CLI — lives in `sat_visualizer.py`. The module has no third-party
  dependencies; it runs on any Python 3.10+.

* **Separation of concerns.** Parsing returns plain immutable
  `NamedTuple`s (`Clause`, `TraceEvent`); rendering functions are pure
  on those values; the top-level `visualize()` is the only function
  that touches the filesystem. This makes every step independently
  unit-testable.

* **Variable-naming convention.** Variable ids 1–26 map to A–Z;
  beyond that we fall back to `x{id}` to avoid collisions. A future
  extension could read the Project #2 V-Map for human-readable names.

* **Snapshot-based backtracking.** A simple stack of clause-list
  snapshots gives correct semantics under chronological backtracking
  (the only kind required by the spec). Non-chronological/CDCL-style
  backjumping would require explicit DL information on the
  `BACKTRACK` event, which the trace format does not supply.

* **Empty / unit edge cases.** `apply_literal` correctly handles the
  empty-clause case (returns it as the conflict id) and the empty
  initial clause list (renders nothing in the inference form, just
  the dividers). Variables that are unassigned in the final model are
  treated as `0` in the row form's evaluation column; this is a
  conservative choice — no clause that depends on an unassigned
  variable is ever the *only* satisfying literal, since the SAT
  engine would not have terminated otherwise.
