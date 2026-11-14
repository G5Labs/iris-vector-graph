#!/usr/bin/env python3
"""Build the machine-readable obligation matrix (matrix/obligations.json) and its summary (matrix/MATRIX.md).

    python build_matrix.py [--check]

Starting inventories (original submission 9c3719c1, read-only): 19 modules, cells, 61 decisions, 138 premises, 197
findings, 8 not-implemented behaviours, 83 writer obligations. Completion evidence: evidence/runs/*.json and every
lane's machine-readable output (modules/NN.json, findings/audit/NN.json, footprints/NN.json, intent/*.json,
models/*/RESULTS.json, proofs/RESULTS.json, validation/results.json, matrix/orchestrator_status.json).

Every (gate, module) cell gets a status from the strongest available source, in this order: an explicit lane or
orchestrator status with evidence; otherwise `open` with "no evidence". Statuses: closed, failed (a product defect
violates the obligation), open, blocked (exact dependency), not-applicable (with a source reason). IDs, overlaps and
evidence grades are preserved: an original finding keeps its F-id and grade; the audit disposition is added beside it.
--check fails if the committed obligations.json differs from what this script would write, or if any inventory
count differs from the stated starting inventory.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
UPLIFT = ROOT.parent / "playbook-uplift"
sys.path.insert(0, str(UPLIFT / "tools"))
from ontology_index import parse_module  # noqa: E402

EXPECTED = {"modules": 19, "cells": 904, "decisions": 61, "premises": 138, "findings": 197, "not_implemented": 8,
            "writer_obligations": 83}
STATUSES = ["closed", "failed", "open", "blocked", "not-applicable"]


def load(p: Path, default=None):
    try:
        return json.loads(p.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def ids_in(text: str, prefix: str) -> list:
    return sorted(set(re.findall(rf"^#+\s*({prefix}-\d{{4}})\b", text, re.M)))


def inventories() -> dict:
    errors: list = []
    mods = []
    stm = {}
    for p in sorted((UPLIFT / "ontology").glob("[0-9][0-9]-*.md")):
        m = parse_module(p, errors, len(stm) + len(mods))
        mods.append((p, m))
        stm.update((s.id, s) for s in m.statements)
    out = {"modules": [], "findings": [], "decisions": [], "premises": [], "not_implemented": [], "cells": []}
    for p, m in mods:
        nn = p.name[:2]
        text = p.read_text()
        scope = re.search(r"^Scope:\s*(.+?)(?:\n\n|\n##)", text, re.S | re.M)
        out["modules"].append({"nn": nn, "code": getattr(m, "code", None) or p.stem, "file": p.name,
                               "statements": len(m.statements), "scope": scope.group(1).strip() if scope else ""})
        for s in m.statements:
            if "not-implemented" in getattr(s, "evidence", ""):
                out["not_implemented"].append({"id": s.id, "module": nn, "text": s.text})
        for c in getattr(m, "cells", []):
            d = c if isinstance(c, dict) else c.__dict__
            out["cells"].append({"module": nn, **{k: d.get(k) for k in ("entity", "state", "command", "outcome",
                                                                          "statements", "decision")}})
    # findings / decisions / premises: per-module files and the module-12..14 files
    for kind, prefix, sub, top in (("findings", "F", "findings", "FINDINGS.md"), ("decisions", "HD", "decisions", "DECISIONS.md"),
                                   ("premises", "P", "trust", "TRUST.md")):
        seen = set()
        for f in sorted((UPLIFT / sub).glob("*.md")):
            for i in ids_in(f.read_text(), prefix):
                if i not in seen:
                    seen.add(i)
                    out[kind].append({"id": i, "module": f.stem, "source": f"{sub}/{f.name}"})
        for i in ids_in((UPLIFT / top).read_text(), prefix):
            if i not in seen:
                seen.add(i)
                out[kind].append({"id": i, "module": i.split("-")[1][:2], "source": top})
    ws = load(UPLIFT / "semantics" / "writesets.json", {})
    out["writer_obligations"] = [{"pair": k, **(v if isinstance(v, dict) else {"discharge": v})}
                                 for k, v in ws.get("coverage", {}).items()]
    out["parse_errors"] = errors
    return out


def level_of(gate: str) -> str:
    """What a gate's evidence is about: the verification method, a model, or the product."""
    if gate.startswith(("3.3-", "3.3a-")) or gate in ("3.7-explorers",):
        return "model"
    if gate.startswith(("3.1-", "3.2-", "3.8-", "5")) or gate in ("3.4-generator", "3.7-differential"):
        return "method"
    return "product"


def runs() -> dict:
    return {p.stem: load(p) for p in sorted((ROOT / "evidence" / "runs").glob("*.json"))}


def main() -> int:
    inv = inventories()
    counts = {k: len(inv[k]) for k in ("modules", "findings", "decisions", "premises", "not_implemented", "cells",
                                         "writer_obligations")}
    gates = load(HERE / "gates.json")["gates"]
    reg = runs()
    lane_modules = {p.stem: load(p, {}) for p in sorted((ROOT / "modules").glob("*.json"))}
    audits = {p.stem: load(p, []) for p in sorted((ROOT / "findings" / "audit").glob("*.json"))}
    orch = load(HERE / "orchestrator_status.json", {"cells": []})

    cells = []
    nns = [m["nn"] for m in inv["modules"]]
    explicit = {(c["gate"], c.get("module", "product")): c for c in orch.get("cells", [])}
    # lane inputs (e.g. matrix-input/correspondence_status.json) take precedence for the cells they state
    for f in sorted((ROOT / "matrix-input").glob("*.json")):
        data = load(f, [])
        for c in (data if isinstance(data, list) else data.get("cells", [])):
            explicit[(c["gate"], c.get("module", "product"))] = {**c, "source": f"matrix-input/{f.name}"}
    audits_by_mod = defaultdict(list)
    for stem, recs in audits.items():
        for r in (recs if isinstance(recs, list) else recs.get("findings", []) + recs.get("new_findings", [])):
            audits_by_mod[str(r.get("module") or stem)[:2]].append(r)
    reproduced = ("reproduced-live", "reproduced-test", "reproduced-model", "confirmed-source", "product-defect")
    for g in gates:
        targets = ["product"] if g["scope"] == "product" else nns
        for nn in targets:
            c = explicit.get((g["id"], nn))
            if c is None and nn != "product":
                lm = lane_modules.get(nn, {})
                gs = lm.get("gates_by_id", {}) if isinstance(lm, dict) else {}
                if g["id"] in gs:
                    c = {"gate": g["id"], "module": nn, **gs[g["id"]], "source": f"modules/{nn}.json"}
            if c is None and g.get("na_reason"):
                c = {"gate": g["id"], "module": nn, "status": "not-applicable", "reason": g["na_reason"]}
            if c is None:
                c = {"gate": g["id"], "module": nn, "status": "open", "evidence": [], "remaining": "no evidence recorded"}
            c = dict(c)
            c.setdefault("level", level_of(g["id"]))
            ev = [str(e) for e in c.get("evidence", [])]
            ids = sorted({x for e in ev for x in reg if (e == x or e == "run:" + x or e.endswith("/" + x) or e.endswith(x + ".json"))})
            # decisive: the run settled something (a pass, an expected violation, or a product failure)
            passing = [i for i in ids if (reg[i] or {}).get("result") in ("pass", "expected-violation", "fail")]
            if c.get("level") != "method" and any((reg[i] or {}).get("result") == "fail" for i in ids):
                c["product_obligation"] = "fails"
            nonpass = [i for i in ids if i not in passing]
            files = [e for e in ev if (ROOT / e).exists() or (ROOT.parent.parent / e).exists()]
            # product obligation, separate from the verification status
            hits = [f["id"] for f in audits_by_mod.get(nn, []) if g["id"] in (f.get("gates") or [])
                    and f.get("disposition") in reproduced]
            st = c.get("status", "open")
            if st == "failed":            # lanes' "failed" = a product defect: the verification itself is done
                st = "closed"
                c["product_obligation"] = "fails"
            if hits:
                c["product_obligation"] = "fails"
                c["findings"] = hits
            if g["id"] == "3.8-findings-disposed" and st == "closed":
                st = "open"
                c["remaining"] = ("every finding is recorded with evidence and a disposition; a fix or a maintainer "
                                  "decision per finding is outside this observation-only audit")
            if st == "closed":
                if passing:
                    c["evidence_grade"] = "registered-run"
                elif files:
                    c["evidence_grade"] = "inspected"
                else:
                    st = "open"
                    c["remaining"] = "closed claim cites no registered run or committed artifact"
                if nonpass and not passing:
                    st = "open"
                    c["remaining"] = f"closed claim cites only non-decisive runs {nonpass}"
            if c.get("level") == "model" and st == "closed":
                c.setdefault("product_obligation", "holds-in-model-only")
            c.setdefault("product_obligation", "unknown" if st != "not-applicable" else "n/a")
            c["status"] = st
            c["cited_runs"] = ids
            cells.append(c)

    audited = {}
    for nn, recs in audits.items():
        for r in recs if isinstance(recs, list) else recs.get("findings", []) + recs.get("new_findings", []):
            audited[r["id"]] = {k: r.get(k) for k in ("disposition", "severity", "confidence", "gates", "evidence")}
    findings = [{**f, "audit": audited.get(f["id"])} for f in inv["findings"]]
    new_findings = [{"id": i, **v} for i, v in audited.items() if not any(f["id"] == i for f in inv["findings"])]

    obligations = {"pin": "3eaa79cf77d3e0a879b2cced634cf2729d81499e", "submission": "9c3719c1",
                   "starting_inventory": counts, "expected_inventory": EXPECTED,
                   "inventory_matches": {k: counts[k] == EXPECTED[k] for k in EXPECTED},
                   "gates": gates, "cells": cells,
                   "status_counts": dict(Counter(c["status"] for c in cells)),
                   "modules": inv["modules"], "findings": findings, "new_findings": new_findings,
                   "decisions": inv["decisions"], "premises": inv["premises"], "not_implemented": inv["not_implemented"],
                   "writer_obligations": inv["writer_obligations"], "registry_runs": len(reg)}
    text = json.dumps(obligations, indent=1, sort_keys=True, default=str) + "\n"
    target = HERE / "obligations.json"
    if "--check" in sys.argv:
        ok = target.exists() and target.read_text() == text and all(obligations["inventory_matches"].values())
        print("matrix", "current" if ok else "STALE or inventory mismatch", obligations["inventory_matches"])
        return 0 if ok else 1
    target.write_text(text)
    by_gate = defaultdict(Counter)
    prod = defaultdict(Counter)
    for c in cells:
        by_gate[c["gate"]][c["status"]] += 1
        prod[c["gate"]][c.get("product_obligation")] += 1
    PO = ["fails", "holds-in-model-only", "unknown", "n/a"]
    lines = ["# Obligation matrix (generated by build_matrix.py; do not edit)", "",
             f"Starting inventory: {counts} (expected {EXPECTED}).", "",
             "Two separate questions per cell. **Status**: was the verification step done with adequate evidence "
             "(closed needs a registered passing run, or is graded `inspected` when it rests on a committed analysis). "
             "**Product obligation**: does the product at the pin meet it — `fails` (a reproduced finding cites the "
             "gate), `holds-in-model-only` (only a model result supports it; the code correspondence is not "
             "discharged), `unknown`. **Level**: what the evidence is about (method, model, product).", "",
             "| Gate | Level | " + " | ".join(STATUSES) + " | " + " | ".join("product " + p for p in PO) + " |",
             "|---|---|" + "---:|" * (len(STATUSES) + len(PO))]
    for g in gates:
        lines.append(f"| {g['id']} | {level_of(g['id'])} | " + " | ".join(str(by_gate[g['id']].get(s, 0)) for s in STATUSES)
                     + " | " + " | ".join(str(prod[g['id']].get(p, 0)) for p in PO) + " |")
    lines += ["", f"Totals: {dict(Counter(c['status'] for c in cells))}; evidence grade of closed cells: "
              f"{dict(Counter(c.get('evidence_grade') for c in cells if c['status'] == 'closed'))}; product: "
              f"{dict(Counter(c.get('product_obligation') for c in cells))}"]
    (HERE / "MATRIX.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"inventory_matches": all(obligations["inventory_matches"].values()),
                      "status_counts": obligations["status_counts"],
                      "closed_grades": dict(Counter(c.get("evidence_grade") for c in cells if c["status"] == "closed")),
                      "product": dict(Counter(c.get("product_obligation") for c in cells))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
