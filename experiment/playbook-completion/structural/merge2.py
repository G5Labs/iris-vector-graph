#!/usr/bin/env python3
"""Second follow-up merge: the re-decided cells of frame2/ and reads2/ into MATRIX-INPUT-2.json (cells changed only)
and their findings into findings/audit/zz-structural.json (records already there win).

    python merge2.py [--check]

Checks as merge.py: gate known, status and product_obligation in the format, every "run:<id>" registered, finding ids
F-C<module>40..49 with matching module, no id twice; every cell re-decides a (gate, module) pair of MATRIX-INPUT.json.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PC = HERE.parent
SUBS = ["frame2", "reads2"]
GATES = {g["id"] for g in json.loads((PC / "matrix" / "gates.json").read_text())["gates"]}
RUNS = {p.stem for p in (PC / "evidence" / "runs").glob("*.json")}
FIRST = {(c["gate"], c["module"]): c for c in json.loads((HERE / "MATRIX-INPUT.json").read_text())["cells"]}


def main() -> int:
    cells, findings, problems = [], [], []
    for s in SUBS:
        cp = HERE / s / "cells.json"
        if cp.exists():
            for c in json.loads(cp.read_text())["cells"]:
                k = (c["gate"], c["module"])
                if c["gate"] not in GATES:
                    problems.append(f"{s}: unknown gate {k}")
                if k not in FIRST:
                    problems.append(f"{s}: {k} is not a cell of MATRIX-INPUT.json")
                if c.get("status") not in ("closed", "open", "blocked", "not-applicable"):
                    problems.append(f"{s}: {k} status {c.get('status')!r}")
                if c.get("product_obligation") not in ("fails", "holds-in-model-only", "unknown", "intent-undecided", "n/a"):
                    problems.append(f"{s}: {k} product_obligation {c.get('product_obligation')!r}")
                for ev in c.get("evidence", []):
                    if isinstance(ev, str) and ev.startswith("run:") and ev[4:].split()[0] not in RUNS:
                        problems.append(f"{s}: {k} cites unregistered {ev}")
                c.setdefault("sub_lane", s)
                c["supersedes"] = {"status": FIRST.get(k, {}).get("status"),
                                   "product_obligation": FIRST.get(k, {}).get("product_obligation")}
                cells.append(c)
        fp = HERE / s / "findings-proposed.json"
        if fp.exists():
            data = json.loads(fp.read_text())
            for f in (data["findings"] if isinstance(data, dict) else data):
                m = re.fullmatch(r"F-C(\d\d)(\d\d)", f["id"])
                if not m or not 40 <= int(m.group(2)) <= 49 or m.group(1) != f["module"]:
                    problems.append(f"{s}: finding id {f['id']} outside range or module mismatch")
                for ev in f.get("evidence", []):
                    if ev.get("kind") in ("live", "run", "check", "control", "mc", "trace", "probe") and ev["ref"] not in RUNS:
                        problems.append(f"{s}: {f['id']} cites unregistered run {ev['ref']}")
                findings.append(f)
    zz = PC / "findings" / "audit" / "zz-structural.json"
    old = json.loads(zz.read_text())
    old = old["findings"] if isinstance(old, dict) else old
    have = {f["id"] for f in old}
    new = [f for f in findings if f["id"] not in have]
    ids = [f["id"] for f in findings]
    for i in set(ids):
        if ids.count(i) > 1:
            problems.append(f"finding id {i} twice")
    keys = [(c["gate"], c["module"]) for c in cells]
    for k in set(keys):
        if keys.count(k) > 1:
            problems.append(f"cell {k} twice")
    print(f"{len(cells)} re-decided cells, {len(new)} new findings, {len(problems)} problems")
    for p in problems:
        print("PROBLEM", p)
    if "--check" in sys.argv or problems:
        return 1 if problems else 0
    cells.sort(key=lambda c: (c["gate"], c["module"]))
    (HERE / "MATRIX-INPUT-2.json").write_text(json.dumps(
        {"lane": "structural", "follow_up": "frame2 (DDL/dictionary frame oracle) and reads2 (non-interference extension)",
         "cells": cells}, indent=1) + "\n")
    zz.write_text(json.dumps(sorted(old + new, key=lambda f: f["id"]), indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
