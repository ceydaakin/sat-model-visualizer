#!/usr/bin/env python3
"""
SAT Model Visualizer  --  BLG 345E Project #5
================================================

Reads the outputs of the previous SAT-solver projects and produces three
human-readable visualisations of the satisfiability proof:

    1. Row Form        -- per-clause line that confirms M satisfies the CNF
    2. Inference Form  -- step-by-step clause simplification along the trace
    3. Tree Form       -- ASCII search tree (decisions / units / outcomes)

Inputs (text files):

    initial_cnf.txt        The Project #2 CNF dump.
                           Only the first two columns of the CLAUSE LIST
                           section are required.

    final_model.txt        The Project #4 final model dump
                           (STATUS + per-variable TRUE/FALSE/UNASSIGNED).

    execution_trace_*.txt  One or more Project #3 trace dumps.  The
                           BCP EXECUTION LOG sections are concatenated in
                           the given order to form the full trace.

Output:

    A single text file containing all three forms, clearly delimited.

Usage:

    python sat_visualizer.py \\
        --cnf initial_cnf.txt \\
        --model final_model.txt \\
        --trace execution_trace_1.txt --trace execution_trace_2.txt \\
        --out output.txt
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import NamedTuple, Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class Clause(NamedTuple):
    """A single clause: identifier (e.g. 'C3') plus signed-int literals."""
    cid: str
    literals: tuple  # tuple[int, ...]


class TraceEvent(NamedTuple):
    """One BCP-log line, parsed."""
    dl: int                     # decision level
    kind: str                   # DECIDE | UNIT | ASSIGN | CONFLICT | BACKTRACK | SATISFIED
    literal: Optional[int]      # signed literal, or None
    info: Optional[str]         # extra text (e.g. unit-propagating clause id)


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

# Matches a clause line such as:  "C1   | [-1, 2]   | [0, 1]"
_CLAUSE_RE = re.compile(r'^\s*(C\d+)\s*\|\s*\[([^\]]*)\]')


def parse_initial_cnf(path: str) -> tuple[list[Clause], list[int]]:
    """Read Project #2's CNF dump.

    Only the *first two* columns of the CLAUSE LIST section are needed
    (clause id and signed literals).  Variable ids are derived from the
    literals so we never depend on the V-Map being present.

    Returns:
        (clauses, var_ids)  -- clauses preserve file order; var_ids are sorted.
    """
    text = Path(path).read_text()
    clauses: list[Clause] = []
    for line in text.splitlines():
        m = _CLAUSE_RE.match(line)
        if not m:
            continue
        cid = m.group(1)
        body = m.group(2).strip()
        if not body:
            literals: tuple = tuple()
        else:
            literals = tuple(int(x.strip()) for x in body.split(',') if x.strip())
        clauses.append(Clause(cid, literals))
    var_ids = sorted({abs(l) for c in clauses for l in c.literals})
    return clauses, var_ids


# Matches a model line such as:  "1 | TRUE"
_MODEL_RE = re.compile(r'^\s*(\d+)\s*\|\s*(TRUE|FALSE|UNASSIGNED)\s*$')


def parse_final_model(path: str) -> tuple[str, dict]:
    """Read Project #4's final model.  Returns (status, {var_id: bool|None})."""
    text = Path(path).read_text()
    status_match = re.search(r'STATUS:\s*(\w+)', text)
    status = status_match.group(1) if status_match else 'UNKNOWN'

    model: dict[int, Optional[bool]] = {}
    for line in text.splitlines():
        m = _MODEL_RE.match(line)
        if not m:
            continue
        var = int(m.group(1))
        val = m.group(2)
        if val == 'TRUE':
            model[var] = True
        elif val == 'FALSE':
            model[var] = False
        else:
            model[var] = None
    return status, model


# Matches a BCP-log line such as:
#   [DL1] DECIDE  L=2   |
#   [DL1] UNIT    L=-3  | C2
#   [DL1] CONFLICT      | Violation: C4
_TRACE_RE = re.compile(
    r'^\s*\[DL(\d+)\]\s+(\S+)(?:\s+L=(-?\d+))?\s*(?:\|\s*(.*?))?\s*$'
)


def parse_trace(path: str) -> list[TraceEvent]:
    """Read one Project #3 trace file -- only its BCP EXECUTION LOG section."""
    text = Path(path).read_text()
    events: list[TraceEvent] = []
    in_log = False
    for line in text.splitlines():
        # Section markers tell us when the BCP log begins/ends.
        if 'BCP EXECUTION LOG' in line:
            in_log = True
            continue
        if 'CURRENT VARIABLE STATE' in line or '--- STATUS' in line:
            in_log = False
            continue
        if not in_log:
            continue
        m = _TRACE_RE.match(line)
        if not m:
            continue
        dl = int(m.group(1))
        kind = m.group(2)
        lit_str = m.group(3)
        info = m.group(4).strip() if m.group(4) else None
        literal = int(lit_str) if lit_str else None
        events.append(TraceEvent(dl, kind, literal, info or None))
    return events


def combine_traces(paths: list[str]) -> list[TraceEvent]:
    """Concatenate all BCP logs in the given file order."""
    out: list[TraceEvent] = []
    for p in paths:
        out.extend(parse_trace(p))
    return out


# ---------------------------------------------------------------------------
# Helpers (variable / literal rendering)
# ---------------------------------------------------------------------------

def var_name(var_id: int) -> str:
    """Map 1..26 -> A..Z; everything beyond falls back to 'x{id}'."""
    if 1 <= var_id <= 26:
        return chr(ord('A') + var_id - 1)
    return f"x{var_id}"


def lit_str(lit: int) -> str:
    """Symbolic literal: 1 -> 'A', -1 -> '-A'."""
    name = var_name(abs(lit))
    return f"-{name}" if lit < 0 else name


def clause_str(literals: tuple) -> str:
    """Symbolic clause: (-1, 2) -> '-A + B'.  Empty clause prints as '0'."""
    if not literals:
        return "0"
    return ' + '.join(lit_str(l) for l in literals)


def lit_value(lit: int, model: dict) -> Optional[bool]:
    """Evaluate a signed literal under a partial model, or None if unassigned."""
    var = abs(lit)
    val = model.get(var)
    if val is None:
        return None
    return val if lit > 0 else not val


# ---------------------------------------------------------------------------
# Form 1  --  Row form
# ---------------------------------------------------------------------------

def row_form(clauses: list[Clause], var_ids: list[int], model: dict) -> str:
    """Build the row-form text.

    Layout per clause:

        Cid | sign-row | per-literal-values = result

    The sign row uses one column per variable (in ascending id order):
        '+'  literal v in clause      '-'  literal -v in clause     ' '  not present.

    The per-literal values are listed in the *variable-column* order, so the
    output matches the visual order of the sign row.
    """
    lines: list[str] = []
    head_parts = [f"{var_name(v)}={1 if model.get(v) else 0}" for v in var_ids]
    lines.append("Model: " + ", ".join(head_parts))
    lines.append("")

    cid_width = max((len(c.cid) for c in clauses), default=2)

    for c in clauses:
        # Variable -> signed literal that appears in this clause.
        var_to_lit = {abs(l): l for l in c.literals}

        # 1) Sign row, one cell per variable column.
        cells = []
        for v in var_ids:
            if v in var_to_lit:
                cells.append('-' if var_to_lit[v] < 0 else '+')
            else:
                cells.append(' ')
        symbol_row = ' '.join(cells)

        # 2) Value row -- evaluate each present literal in column order.
        values = []
        for v in var_ids:
            if v in var_to_lit:
                values.append('1' if lit_value(var_to_lit[v], model) else '0')

        # 3) Result -- the clause is satisfied iff at least one literal is true.
        result = 1 if any(lit_value(l, model) for l in c.literals) else 0

        if values:
            value_row = ' + '.join(values) + f" = {result}"
        else:
            value_row = f"(empty) = {result}"

        lines.append(f"{c.cid:<{cid_width}} | {symbol_row} | {value_row}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Form 2  --  Inference form
# ---------------------------------------------------------------------------

def apply_literal(clauses: list[Clause], lit: int) -> tuple[list[Clause], Optional[str]]:
    """Make `lit` true and return the simplified clause list.

    Rules:
        * Clauses containing `lit` become satisfied -> dropped.
        * The opposite literal (`-lit`) is removed from the remaining clauses.
        * The first clause that becomes empty marks the conflict (its id is
          returned alongside the new clause list).
    """
    new_clauses: list[Clause] = []
    conflict_cid: Optional[str] = None
    for c in clauses:
        if lit in c.literals:
            continue                       # satisfied -- drop the clause
        new_lits = tuple(l for l in c.literals if l != -lit)
        new_clauses.append(Clause(c.cid, new_lits))
        if not new_lits and conflict_cid is None:
            conflict_cid = c.cid
    return new_clauses, conflict_cid


def render_simplified(clauses: list[Clause], conflict_cid: Optional[str]) -> list[str]:
    """Render the current (simplified) clause set, marking a conflict if any."""
    out = []
    for c in clauses:
        if c.cid == conflict_cid:
            out.append(f"{c.cid} | 0 | Conflict")
        elif not c.literals:
            out.append(f"{c.cid} | 0")
        else:
            out.append(f"{c.cid} | {clause_str(c.literals)}")
    return out


def inference_form(initial_clauses: list[Clause], events: list[TraceEvent]) -> str:
    """Replay the trace symbolically.

    For each DECIDE / UNIT we apply the literal to the *current* clause set
    and re-print the simplified clauses.  Each DECIDE pushes a snapshot so
    a BACKTRACK can restore the pre-decision state (chronological backtrack
    -- adequate for the project specification).
    """
    lines: list[str] = []
    # 1) Start with the original CNF.
    for c in initial_clauses:
        lines.append(f"{c.cid} | {clause_str(c.literals)}")

    snapshots: list[list[Clause]] = []
    current: list[Clause] = list(initial_clauses)

    for ev in events:
        if ev.kind == 'DECIDE':
            snapshots.append(list(current))
            current, conflict = apply_literal(current, ev.literal)
            lines.append(f"---------- Decision L={ev.literal}")
            lines.extend(render_simplified(current, conflict))

        elif ev.kind == 'UNIT':
            current, conflict = apply_literal(current, ev.literal)
            lines.append(f"---------- Unit L={ev.literal}")
            lines.extend(render_simplified(current, conflict))

        elif ev.kind == 'ASSIGN':
            # ASSIGN repeats the literal already handled by DECIDE/UNIT;
            # nothing extra to render in the inference form.
            continue

        elif ev.kind == 'CONFLICT':
            # The empty clause was already marked by render_simplified
            # when the unit producing the conflict was applied.
            continue

        elif ev.kind == 'BACKTRACK':
            if snapshots:
                current = snapshots.pop()

        elif ev.kind == 'SATISFIED':
            lines.append("Satisfied")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Form 3  --  Tree form
# ---------------------------------------------------------------------------

class TreeNode:
    """One node of the search tree -- label plus ordered children."""
    __slots__ = ('label', 'children')

    def __init__(self, label: str):
        self.label = label
        self.children: list['TreeNode'] = []


def build_tree(events: list[TraceEvent]) -> TreeNode:
    """Translate the linear trace into a search-tree structure.

    Idea: keep a stack `parents[d]` = the most recent node at decision level
    d.  parents[0] is the synthetic Root (DL 0 propagations attach there).

        DECIDE  at DL d  -> child of parents[d-1]; pushed as parents[d].
        UNIT    at DL d  -> leaf child of parents[d] (current decision node).
        CONFLICT/SATISFIED -> leaf child of parents[-1].
        BACKTRACK -> pop one level (the failed decision is closed).

    This handles arbitrary decision depth and chronological backtracking.
    """
    root = TreeNode("Root")
    parents: list[TreeNode] = [root]

    for ev in events:
        if ev.kind == 'DECIDE':
            # Defensive: drop any deeper-level parents that linger if the
            # trace omits an explicit BACKTRACK.
            while len(parents) > ev.dl:
                parents.pop()
            label = f"Decide {var_name(abs(ev.literal))} = {1 if ev.literal > 0 else 0}"
            node = TreeNode(label)
            parents[-1].children.append(node)
            parents.append(node)

        elif ev.kind == 'UNIT':
            label = f"Unit {var_name(abs(ev.literal))} = {1 if ev.literal > 0 else 0}"
            parents[-1].children.append(TreeNode(label))

        elif ev.kind == 'ASSIGN':
            continue

        elif ev.kind == 'CONFLICT':
            parents[-1].children.append(TreeNode("Conflict!"))

        elif ev.kind == 'BACKTRACK':
            if len(parents) > 1:
                parents.pop()

        elif ev.kind == 'SATISFIED':
            parents[-1].children.append(TreeNode("Satisfied!"))

    return root


def render_tree(root: TreeNode) -> str:
    """ASCII-render the tree.  Connector convention follows the spec example."""
    lines: list[str] = [root.label]
    _render_children(root, lines, prefix=" ")
    return "\n".join(lines)


def _render_children(parent: TreeNode, lines: list[str], prefix: str) -> None:
    """Recursive helper.  `prefix` is the column padding before each child's
    own '|'.  When a parent still has more siblings below us we keep its '|'
    visible in the column; otherwise that column becomes a space.
    """
    children = parent.children
    n = len(children)
    for i, child in enumerate(children):
        is_last = (i == n - 1)
        # Connector line above the node.
        lines.append(prefix + "|")
        # Node line.
        lines.append(prefix + "|----- " + child.label)
        # Recursion: 7-space indent aligns the next '|' under the dashes.
        cont_char = " " if is_last else "|"
        grand_prefix = prefix + cont_char + "       "
        _render_children(child, lines, grand_prefix)


# ---------------------------------------------------------------------------
# Top-level driver
# ---------------------------------------------------------------------------

def visualize(initial_cnf_path: str,
              final_model_path: str,
              trace_paths: list[str],
              output_path: str) -> str:
    """Read inputs, build all three forms, write a single output file.

    Returns the rendered text (handy for tests).
    """
    clauses, var_ids = parse_initial_cnf(initial_cnf_path)
    status, model = parse_final_model(final_model_path)
    events = combine_traces(trace_paths)

    sections: list[str] = []
    sections.append("=" * 72)
    sections.append("SAT MODEL VISUALIZER  --  OUTPUT")
    sections.append(f"Status: {status}")
    sections.append(f"Variables: {len(var_ids)}    Clauses: {len(clauses)}    "
                    f"Trace events: {len(events)}")
    sections.append("=" * 72)
    sections.append("")
    sections.append("--- 1. ROW FORM (MODEL VERIFICATION) ---")
    sections.append("")
    sections.append(row_form(clauses, var_ids, model))
    sections.append("")
    sections.append("--- 2. INFERENCE FORM (LOGICAL TRACE) ---")
    sections.append("")
    sections.append(inference_form(clauses, events))
    sections.append("")
    sections.append("--- 3. TREE FORM (SEARCH TREE) ---")
    sections.append("")
    sections.append(render_tree(build_tree(events)))
    sections.append("")

    rendered = "\n".join(sections)
    Path(output_path).write_text(rendered)
    return rendered


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_cli(argv: list[str]) -> dict:
    """Tiny hand-rolled CLI -- avoids argparse dependency complications."""
    args = {'cnf': None, 'model': None, 'traces': [], 'out': 'output.txt'}
    it = iter(argv)
    for tok in it:
        if tok == '--cnf':
            args['cnf'] = next(it)
        elif tok == '--model':
            args['model'] = next(it)
        elif tok == '--trace':
            args['traces'].append(next(it))
        elif tok == '--out':
            args['out'] = next(it)
        elif tok in ('-h', '--help'):
            print(__doc__)
            sys.exit(0)
        else:
            raise SystemExit(f"Unknown argument: {tok!r}")
    if not (args['cnf'] and args['model'] and args['traces']):
        raise SystemExit(
            "usage: sat_visualizer.py --cnf F --model F "
            "--trace F [--trace F ...] [--out F]"
        )
    return args


def _cli_entry() -> None:
    """Entry point used by the ``sat-visualize`` console script."""
    a = _parse_cli(sys.argv[1:])
    visualize(a['cnf'], a['model'], a['traces'], a['out'])
    print(f"Wrote {a['out']}")


if __name__ == '__main__':
    _cli_entry()
