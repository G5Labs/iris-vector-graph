#!/usr/bin/env python3
"""Render STRUCTURAL.md from STRUCTURAL.md.in (prose) and MATRIX-INPUT.json (the gate x module table).

    python render.py

The table lists, per gate and module, the cell status, the product obligation and the findings; the marker line
'<!-- TABLE -->' in STRUCTURAL.md.in is replaced by it.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GATES = ["3.4-ownership", "3.4-storage-order", "3.4-declared-reads", "3.6-keys", "3.6-fk", "3.6-capacity",
         "3.6-row-permutation", "3.6-frame"]


def main() -> int:
    cells = json.loads((HERE / "MATRIX-INPUT.json").read_text())["cells"]
    by = {(c["gate"], c["module"]): c for c in cells}
    mods = sorted({c["module"] for c in cells})
    out = ["| Module | " + " | ".join(g.replace("3.4-", "").replace("3.6-", "") for g in GATES) + " |",
           "|---|" + "---|" * len(GATES)]
    for m in mods:
        row = []
        for g in GATES:
            c = by.get((g, m))
            if not c:
                row.append("")
                continue
            st = {"closed": "C", "open": "O", "blocked": "B", "not-applicable": "n/a"}[c["status"]]
            po = {"fails": "fails", "unknown": "no violation seen", "intent-undecided": "intent-undecided",
                  "n/a": "n/a", "holds-in-model-only": "model only"}[c["product_obligation"]]
            f = ", ".join(c.get("as_built_findings") or [])
            row.append(f"{st}: {po}" + (f" ({f})" if f else ""))
        out.append(f"| {m} | " + " | ".join(row) + " |")
    legend = ("C = closed (registered decisive run + self-test, or a committed analysis graded inspected), "
              "O = open (the cell's 'remaining' text in MATRIX-INPUT.json says exactly what is missing); "
              "'no violation seen' is product_obligation 'unknown': the probes found no violation, which is not a proof. "
              "An empty cell is a (gate, module) pair this lane did not decide (closed earlier by another lane, or not "
              "in the task's open list).")
    src = (HERE / "STRUCTURAL.md.in").read_text()
    opens = []
    for c in sorted(cells, key=lambda c: (c["gate"], c["module"])):
        if c["status"] != "closed" and c["status"] != "not-applicable":
            opens.append(f"- {c['gate']} / {c['module']} ({c['status']}): {(c.get('remaining') or '').strip()[:900]}")
    closed_rem = [c for c in cells if c["status"] == "closed" and (c.get("remaining") or "").strip()]
    opens.append("")
    opens.append(f"Closed cells with a stated residue ({len(closed_rem)}): see each cell's `remaining` in MATRIX-INPUT.json.")
    frame = (HERE / "frame" / "STRUCTURAL-frame.txt")
    src = src.replace("<!-- FRAME -->", frame.read_text().strip() if frame.exists() else "(frame sub-lane result pending)")
    src = src.replace("<!-- OPEN -->", "\n".join(opens))
    (HERE / "STRUCTURAL.md").write_text(src.replace("<!-- TABLE -->", "\n".join(out) + "\n\n" + legend))
    print(f"{len(cells)} cells, {len(mods)} modules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
