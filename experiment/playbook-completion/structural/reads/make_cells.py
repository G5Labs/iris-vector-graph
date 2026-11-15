#!/usr/bin/env python3
"""Assemble structural/reads/{cells.json, method.json} from the registered runs' result files.

    python make_cells.py SELFTEST.json RESULT.json [RESULT.json ...]

Per module: the read actions checked (oracle A verdicts), the violations and the finding each is attributed to
(FINDING_OF, by case id), and the inventoried read entry points no case covers (footprints/NN.json role reader/both;
correspondence.json actions for 11-14), which stay in the cell's 'remaining'.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
META = json.loads((HERE / "attribution.json").read_text())
FINDING_OF = META["finding_of"]
RUN_OF = META["run_of_module"]
SELFTEST_RUN = META["selftest_run"]
FEASIBILITY_RUNS = META["feasibility_runs"]


def footprint_entries(module):
    p = ROOT / "footprints" / f"{module}.json"
    if not p.exists():
        return []
    d = json.loads(p.read_text())
    return d.get("entry_points") or d.get("entries") or []


def inventory(module):
    """[(name, covered-by short name or None)]."""
    if module in META["inventory_11_14"]:
        return list(META["inventory_11_14"][module].items())
    return [((e.get("id") or e.get("entry")), None) for e in footprint_entries(module)
            if str(e.get("role", "")).startswith(("reader", "both"))]


def declared_stores(module, entry):
    """sql: and catalog: stores the footprint declares for entry (reads and writes), or None."""
    if not entry:
        return None
    for e in footprint_entries(module):
        i = e.get("id") or e.get("entry") or ""
        if i in (f"py:{entry}", entry, f"eng:{entry}"):
            st = []
            for key in ("reads", "writes"):
                v = e.get(key)
                if isinstance(v, dict):
                    st += ["sql:" + t for t in v.get("tables", [])]
                elif isinstance(v, list):
                    st += [x["store"] if isinstance(x, dict) else x for x in v]
            return sorted({s.split(" ")[0].split(":", 1)[1] for s in st if s.startswith(("sql:", "catalog:"))})
    return None


def oracle_b(module, case, entry):
    read = (case.get("base") or {}).get("sql_tables") or []
    decl = declared_stores(module, entry)
    if decl is None:
        return {"tables_read": read, "declared": None, "undeclared": None, "note": "no footprint entry with tables for this action"}
    dyn = [d for d in decl if "<dynamic" in d]
    und = [t for t in read if t not in decl and not (dyn and t.startswith("Graph_KG."))]
    by_dyn = [t for t in read if t not in decl and dyn and t.startswith("Graph_KG.")]
    return {"tables_read": read, "declared": decl, "undeclared": und, "resolved_dynamic_names": by_dyn}


def short(name):
    return name.split(":")[-1].split(".")[-1].split(" ")[0].split("(")[0]


ENTRY = {}


def main() -> int:
    st = json.loads(Path(sys.argv[1]).read_text())
    latest = {}
    for p in sys.argv[2:]:                       # a later result file supersedes an earlier one per (module, case)
        for c in json.loads(Path(p).read_text())["cases"]:
            latest[(c["module"], c["id"])] = c
    by = {}
    for (m, _), c in latest.items():
        by.setdefault(m, []).append(c)
    import noninterference as NI  # case table: the footprint entry of each case
    for x in NI.cases():
        ENTRY[(x["module"], x["id"])] = x["entry"]
    cells, per_module = [], {}
    for m in sorted(by):
        cs = by[m]
        inv = inventory(m)
        checked_names = {re.match(r"[\w.]+", c["id"]).group(0).split(".")[-1] for c in cs}
        unchecked = [n for n, cov in inv if (cov is None if m in META["inventory_11_14"] else short(n) not in checked_names)]
        viol = [c for c in cs if c["verdict"] == "violation"]
        und = [c for c in cs if c["verdict"] not in ("violation", "holds")]
        insens = [c["id"] for c in cs if c.get("insensitive")]
        fids = sorted({FINDING_OF.get(c["id"], "UNATTRIBUTED") for c in viol})
        ob = {c["id"]: oracle_b(m, c, ENTRY.get((m, c["id"]))) for c in cs}
        run = RUN_OF[m]
        ev = [f"run:{SELFTEST_RUN}", f"run:{run}", "experiment/playbook-completion/structural/reads/method.json",
              "experiment/playbook-completion/structural/reads/noninterference.py"]
        if m == "18":
            ev.insert(2, "run:st-live-reads-b (module 18 verdict there is a harness artifact, superseded)")
        checked_txt = (f"{len(cs)} read actions checked by non-interference (oracle A, self-tested): "
                       f"{sum(1 for c in cs if c['verdict']=='holds')} hold, {len(viol)} violate, {len(und)} undecided")
        rem = []
        if unchecked:
            rem.append(f"{len(unchecked)} of {len(inv)} inventoried read/both entry points not checked: " + ", ".join(unchecked))
        if und:
            rem.append("undecided: " + "; ".join(f"{c['id']} ({((c.get('base') or {}).get('error') or (c.get('base') or {}).get('setup_error') or c.get('error') or '')[:120] or 'vacuous: no walk steps without the Arno library (F-1002)'})" for c in und))
        if insens:
            rem.append("inside perturbation did not change the answer (sensitivity not shown): " + "; ".join(insens))
        rem.append("non-interference sees only reads that reach the answer, and only under the perturbations listed per action in structural/reads/method.json")
        if viol:
            status, po = "closed", "fails"
            basis = f"{checked_txt}. Violations: " + "; ".join(
                f"{c['id']} changed under '{', '.join(c['violations'])}' ({FINDING_OF.get(c['id'], 'UNATTRIBUTED')})" for c in viol)
        elif not unchecked and not und:
            status, po = "closed", "holds-live"
            basis = checked_txt
        else:
            status, po = "open", "unknown"
            basis = checked_txt + "; no violation among the checked actions"
        cell = {"gate": "3.4-declared-reads", "module": m, "status": status, "evidence": ev, "evidence_grade": "live",
                "level": "product", "product_obligation": po, "product_basis": basis,
                "as_built_findings": [f for f in fids if f != "UNATTRIBUTED"], "remaining": " | ".join(rem)}
        if m in META["emit_cells_for"]:
            cells.append(cell)
        per_module[m] = {"run": run, "checked": [{"id": c["id"], "verdict": c["verdict"], "violations": c.get("violations"),
                                                  "declared": c.get("declared"),
                                                  "outside_perturbations": sorted((c.get("outside") or {}).keys()),
                                                  "inside_changed": (c.get("inside") or {}).get("changed"),
                                                  "declared_inside_perturbations": {k: v["changed"] for k, v in (c.get("inside_declared") or {}).items()},
                                                  "oracle_b": ob[c["id"]]} for c in cs],
                         "unchecked": unchecked, "decision": status + "/" + po,
                         "cell_emitted": m in META["emit_cells_for"], "why_not_emitted": META["not_emitted"].get(m)}
    (HERE / "cells.json").write_text(json.dumps({"cells": cells}, indent=1) + "\n")
    method = json.loads((HERE / "method-static.json").read_text())
    method["self_test"]["result"] = st["summary"]
    method["self_test"]["run"] = SELFTEST_RUN
    method["runs"] = {"feasibility": FEASIBILITY_RUNS, "self_test": SELFTEST_RUN,
                      "decisive": sorted(set(RUN_OF.values())), "superseded_for_module_18": "st-live-reads-b"}
    method["per_module"] = per_module
    (HERE / "method.json").write_text(json.dumps(method, indent=1) + "\n")
    for c in cells:
        print(c["module"], c["status"], c["product_obligation"], c["as_built_findings"], "| rem:", c["remaining"][:200])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
