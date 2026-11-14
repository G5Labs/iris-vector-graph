#!/usr/bin/env python3
"""Merge the structural lane's sub-lane outputs into its deliverables.

    python merge.py [--check]

Inputs: structural/<sub>/cells.json ({"cells": [...]}) and structural/<sub>/findings-proposed.json for
sub in capkeys, ownership, order, frame, reads.
Outputs: structural/MATRIX-INPUT.json (one cell per (gate, module); a duplicate pair is an error) and
findings/audit/zz-structural.json (new findings only: ids F-C<module>40..49 whose module digits match the record's
module). Checks: every "run:<id>" evidence names a registered run (evidence/runs/<id>.json) of lane structural or an
earlier registered run; every finding id is in the lane's range and unique; every cell's gate is in matrix/gates.json.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PC = HERE.parent
SUBS = ["capkeys", "ownership", "order", "frame", "reads", "susp"]
GATES = {g["id"] for g in json.loads((PC / "matrix" / "gates.json").read_text())["gates"]}
RUNS = {p.stem for p in (PC / "evidence" / "runs").glob("*.json")}


def main() -> int:
    cells, findings, problems = [], [], []
    seen = {}
    for s in SUBS:
        cp = HERE / s / "cells.json"
        if cp.exists():
            for c in json.loads(cp.read_text())["cells"]:
                k = (c["gate"], c["module"])
                if c.get("product_obligation") not in ("fails", "holds-in-model-only", "unknown", "intent-undecided", "n/a"):
                    problems.append(f"{s}: cell {k} product_obligation {c.get('product_obligation')!r} not in the format")
                if c.get("status") not in ("closed", "open", "blocked", "not-applicable"):
                    problems.append(f"{s}: cell {k} status {c.get('status')!r} not in the format")
                if c["gate"] not in GATES:
                    problems.append(f"{s}: unknown gate {c['gate']}")
                if k in seen:
                    problems.append(f"duplicate cell {k} from {s} and {seen[k]}")
                    continue
                seen[k] = s
                for ev in c.get("evidence", []):
                    if isinstance(ev, str) and ev.startswith("run:") and ev[4:].split()[0] not in RUNS:
                        problems.append(f"{s}: cell {k} cites unregistered {ev}")
                c.setdefault("sub_lane", s)
                cells.append(c)
        fp = HERE / s / "findings-proposed.json"
        if fp.exists():
            data = json.loads(fp.read_text())
            for f in (data["findings"] if isinstance(data, dict) else data):
                m = re.fullmatch(r"F-C(\d\d)(\d\d)", f["id"])
                if not m or not 40 <= int(m.group(2)) <= 49 or m.group(1) != f["module"]:
                    problems.append(f"{s}: finding id {f['id']} outside F-C<module>40..49 or module mismatch")
                for ev in f.get("evidence", []):
                    if ev.get("kind") in ("live", "run", "check", "control", "mc", "trace", "probe") and ev["ref"] not in RUNS:
                        problems.append(f"{s}: {f['id']} cites unregistered run {ev['ref']}")
                findings.append(f)
    ids = [f["id"] for f in findings]
    for i in set(ids):
        if ids.count(i) > 1:
            problems.append(f"finding id {i} used twice")
    cells.sort(key=lambda c: (c["gate"], c["module"]))
    findings.sort(key=lambda f: f["id"])
    print(f"{len(cells)} cells, {len(findings)} findings, {len(problems)} problems")
    for p in problems:
        print("PROBLEM", p)
    if "--check" in sys.argv:
        return 1 if problems else 0
    (HERE / "MATRIX-INPUT.json").write_text(json.dumps({"lane": "structural", "cells": cells}, indent=1) + "\n")
    # a record already in zz-structural.json wins: the orchestrator may have updated it (e.g. F-C1240 refuted)
    zz = PC / "findings" / "audit" / "zz-structural.json"
    if zz.exists():
        old = json.loads(zz.read_text())
        old = old["findings"] if isinstance(old, dict) else old
        kept = {f["id"]: f for f in old}
        findings = [kept.get(f["id"], f) for f in findings] + [f for f in old if f["id"] not in {x["id"] for x in findings}]
        findings.sort(key=lambda f: f["id"])
    zz.write_text(json.dumps(findings, indent=1) + "\n")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
