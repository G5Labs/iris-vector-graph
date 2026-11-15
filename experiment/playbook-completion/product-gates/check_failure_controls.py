#!/usr/bin/env python3
"""Check FAILURE-CONTROLS.md against the run registry (gate 3.7-failure-controls).

    python experiment/playbook-completion/product-gates/check_failure_controls.py [--self-test]

Every backticked run id in the scenario table must be a record in evidence/runs/ (an id ending in '-*' must match at
least one record); every scenario row must name a negative control or say "none" with the missing piece, or be marked
blocked-access. Prints one line per row and a summary; exit 0 when the document agrees with the registry.
--self-test feeds the checker a row citing an unregistered id and a row with neither a control nor a "none" note,
and requires both to be reported.
"""
from __future__ import annotations

import fnmatch
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = {p.stem for p in (HERE.parent / "evidence" / "runs").glob("*.json")}
ID = re.compile(r"`([A-Za-z0-9][A-Za-z0-9.-]*-[A-Za-z0-9.*-]+)`")
NOT_RUN_IDS = {"product-gates/disconnect_world.py"}


def rows(text: str):
    for line in text.splitlines():
        m = re.match(r"\| (S\d+b?) \|", line)
        if m:
            cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
            yield m.group(1), cells


def check_row(sid: str, cells: list) -> list:
    bad = []
    run_cell, ctl_cell, status = cells[3], cells[4], cells[5]
    for cell in (run_cell, ctl_cell):
        for rid in ID.findall(cell):
            if "/" in rid or rid.endswith((".py", ".md")) or rid in NOT_RUN_IDS:
                continue
            if "*" in rid:
                if not fnmatch.filter(RUNS, rid):
                    bad.append(f"{sid}: no run matches {rid}")
            elif rid not in RUNS:
                bad.append(f"{sid}: {rid} is not a registered run")
    has_ctl = bool(ID.findall(ctl_cell))
    if not has_ctl and "none" not in ctl_cell.lower() and "blocked" not in status.lower() and "covered by" not in status:
        bad.append(f"{sid}: neither a control nor a stated missing piece")
    return bad


def main() -> int:
    if "--self-test" in sys.argv:
        b1 = check_row("SX", ["SX", "f", "o", "`no-such-run-xyz`", "`pg-disconnect-selftest`", "ok"])
        b2 = check_row("SY", ["SY", "f", "o", "`pg-disconnect-commit`", "nothing here", "ok"])
        good = check_row("SZ", ["SZ", "f", "o", "`pg-disconnect-commit`", "`pg-disconnect-selftest`", "ok"])
        ok = bool(b1) and bool(b2) and not good
        print("self-test", "PASS" if ok else "FAIL", b1, b2, good)
        return 0 if ok else 1
    text = (HERE / "FAILURE-CONTROLS.md").read_text()
    allbad, n, with_ctl, covered, none, blocked = [], 0, 0, 0, 0, 0
    for sid, cells in rows(text):
        n += 1
        b = check_row(sid, cells)
        allbad += b
        ctl = cells[4]
        kind = ("blocked" if "blocked" in cells[5].lower() else "control" if ID.findall(ctl)
                else "covered" if "covered by" in cells[5] else "none")
        with_ctl += kind == "control"
        covered += kind == "covered"
        none += kind == "none"
        blocked += kind == "blocked"
        print(sid, kind, "ids:", ID.findall(cells[3] + " " + ctl), "problems:", b)
    print(f"rows {n}: with a registered control {with_ctl}, covered by another row's control {covered}, "
          f"without {none}, blocked {blocked}; "
          f"problems {len(allbad)}")
    return 0 if not allbad else 1


if __name__ == "__main__":
    raise SystemExit(main())
