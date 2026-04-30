#!/usr/bin/env python3
"""
Test driver for the SAT Model Visualizer.

For every directory under tests/ it
    1. discovers initial_cnf.txt, final_model.txt, execution_trace_*.txt
    2. runs visualize() to produce output.txt
    3. checks a small set of structural invariants on the output

The point is not bit-perfect golden comparison (formatting may legitimately
vary in width) but to verify the *content* is correct.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import sat_visualizer as sv


HERE = Path(__file__).resolve().parent
TESTS = HERE / "tests"


def _check_row_form(text: str, model: dict) -> list[str]:
    """The Row Form must:
        * print the model header for every variable
        * print every clause with a final '= 1' (every clause must be satisfied)
    """
    errs: list[str] = []
    if "Model:" not in text:
        errs.append("Row form is missing the 'Model:' header")

    # Each clause line ends with '= <0|1>' -- they must all be 1 in a SAT case.
    clause_results = re.findall(r'C\d+\s+\|.*=\s*(\d)\s*$', text, flags=re.M)
    if not clause_results:
        errs.append("Row form has no parsable clause lines")
    elif any(r != '1' for r in clause_results):
        errs.append(f"Row form has unsatisfied clauses: {clause_results}")
    return errs


def _check_inference_form(text: str, n_decides: int, n_satisfied: int) -> list[str]:
    """The Inference Form must contain one '---------- Decision' separator per
    DECIDE event, and 'Satisfied' iff a SATISFIED event was seen.
    """
    errs: list[str] = []
    decisions = len(re.findall(r'^-{10} Decision', text, flags=re.M))
    if decisions != n_decides:
        errs.append(f"Inference form: expected {n_decides} Decision lines, "
                    f"found {decisions}")
    if n_satisfied:
        if "Satisfied" not in text:
            errs.append("Inference form: missing 'Satisfied' terminator")
    return errs


def _check_tree_form(text: str, n_decides: int, n_conflicts: int,
                     n_satisfied: int) -> list[str]:
    errs: list[str] = []
    if "Root" not in text:
        errs.append("Tree form: missing 'Root'")
    decides_in_tree = len(re.findall(r'\|----- Decide', text))
    if decides_in_tree != n_decides:
        errs.append(f"Tree form: expected {n_decides} Decide nodes, "
                    f"found {decides_in_tree}")
    conflicts = len(re.findall(r'\|----- Conflict!', text))
    if conflicts != n_conflicts:
        errs.append(f"Tree form: expected {n_conflicts} Conflict! nodes, "
                    f"found {conflicts}")
    sats = len(re.findall(r'\|----- Satisfied!', text))
    if sats != n_satisfied:
        errs.append(f"Tree form: expected {n_satisfied} Satisfied! nodes, "
                    f"found {sats}")
    return errs


def run_test(tdir: Path) -> bool:
    cnf = tdir / "initial_cnf.txt"
    model = tdir / "final_model.txt"
    traces = sorted(tdir.glob("execution_trace_*.txt"))
    out = tdir / "output.txt"

    if not (cnf.exists() and model.exists() and traces):
        print(f"  [SKIP] {tdir.name}: missing input files")
        return False

    text = sv.visualize(str(cnf), str(model), [str(p) for p in traces], str(out))

    # Parse a minimal expectation set straight from the inputs themselves.
    _, model_dict = sv.parse_final_model(str(model))
    events = sv.combine_traces([str(p) for p in traces])
    n_decides = sum(1 for e in events if e.kind == 'DECIDE')
    n_conflicts = sum(1 for e in events if e.kind == 'CONFLICT')
    n_satisfied = sum(1 for e in events if e.kind == 'SATISFIED')

    errs: list[str] = []
    errs += _check_row_form(text, model_dict)
    errs += _check_inference_form(text, n_decides, n_satisfied)
    errs += _check_tree_form(text, n_decides, n_conflicts, n_satisfied)

    if errs:
        print(f"  [FAIL] {tdir.name}")
        for e in errs:
            print(f"         - {e}")
        return False
    print(f"  [PASS] {tdir.name}  "
          f"(decides={n_decides}, conflicts={n_conflicts}, satisfied={n_satisfied})")
    return True


def main() -> int:
    print(f"Running tests in {TESTS}")
    passed = failed = 0
    for tdir in sorted(TESTS.iterdir()):
        if not tdir.is_dir():
            continue
        ok = run_test(tdir)
        passed += ok
        failed += not ok
    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
