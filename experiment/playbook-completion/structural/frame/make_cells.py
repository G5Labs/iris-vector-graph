#!/usr/bin/env python3
"""Write structural/frame/cells.json and method.json from the aggregate of the registered runs.

    python make_cells.py AGGREGATE.json RUNS.json

RUNS.json: {"live": "<run id>", "control": "<run id>", "check": "<run id>"} (registered ids).
Rule (stated in method.json): a module's 3.6-frame cell is closed only if (1) the control passed (registered),
(2) the decisive live run exercised at least one writer action of the module and every exercised action's
store-level and key-level excursions are dispositioned (a finding, or a declaration gap of the footprint the check
used - reported, never widened), and (3) every statement-shape class present in the module's source
(shape_census.py) was observed in the journal of the module's actions. Otherwise open, with the exact remainder.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NOTES = json.loads((HERE / "dispositions.json").read_text())


def main() -> int:
    agg = json.loads(Path(sys.argv[1]).read_text())["modules"]
    runs = json.loads(Path(sys.argv[2]).read_text())
    cells = []
    for mod in ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15", "17", "18"]:
        m = agg.get(mod)
        note = NOTES["modules"].get(mod, {})
        ev = [f"run:{runs['live']}", f"run:{runs['control']}", f"run:{runs['check']}",
              "experiment/playbook-completion/structural/frame/method.json"]
        if m is None:
            cells.append({"gate": "3.6-frame", "module": mod, "status": "open", "evidence": ev, "evidence_grade": "open",
                          "level": "product", "product_obligation": "unknown", "product_basis": "no action run",
                          "as_built_findings": [], "remaining": note.get("remaining", "no writer action exercised")})
            continue
        undispositioned = [x for x in m["store_excursions"] + m["key_excursions"]
                           if x["action"] not in note.get("dispositioned_actions", [])]
        closed = (m["exercised"] > 0 and not undispositioned and not m["static_classes_unexercised"]
                  and not note.get("force_open"))
        rem = []
        if m["static_classes_unexercised"]:
            rem.append("statement-shape classes present in the module's source but not observed in the journal of its "
                       "exercised actions: " + ", ".join(m["static_classes_unexercised"]))
        if m["not_exercised"]:
            rem.append("writer actions run but not exercised (error or no journaled write): " + "; ".join(m["not_exercised"]))
        if undispositioned:
            rem.append(f"{len(undispositioned)} excursions not dispositioned")
        if note.get("remaining"):
            rem.append(note["remaining"])
        cells.append({
            "gate": "3.6-frame", "module": mod, "status": "closed" if closed else "open", "evidence": ev,
            "evidence_grade": "live",
            "level": "product",
            "product_obligation": note.get("product_obligation", "unknown"),
            "product_basis": (f"{m['exercised']} of {m['actions']} writer actions exercised live on AUDITD under the journal "
                              f"({', '.join(m['action_ids'])}); store-level frame held on {m['store_ok']}, key-level on "
                              f"{m['key_ok']}; journal statement classes {m['journal_classes']}; source classes "
                              f"{m['static_classes']}. " + note.get("basis", "")),
            "as_built_findings": note.get("findings", []),
            "declaration_gaps": note.get("gaps", []),
            "remaining": " | ".join(rem),
        })
    (HERE / "cells.json").write_text(json.dumps({"cells": cells}, indent=1) + "\n")
    for c in cells:
        print(c["module"], c["status"], c["product_obligation"], c["remaining"][:160])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
