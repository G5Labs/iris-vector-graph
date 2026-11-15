#!/usr/bin/env python3
"""Write refusals/audit/11.json (module 11, LED X statements) from the registered live run's results.

    python audit_11.py <run-id> <results.json> [<rerun-id> <rerun-results.json> <statement,...>]

A rerun replaces the first run's cases for the statements it names (the first run's cases stay cited in the notes).

Implementing code was read at the pin (cited below). For each statement the live cases are taken from the results
file (refusal cases only; observations are cited in the notes): holds-live when every case holds, product-defect
when one does not (finding named below), otherwise the outcome given here with its reason.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

LANE = Path(__file__).resolve().parent

CODE = {
    "LED-B1.9": ["iris_src/src/Graph/KG/Ledger.cls:252-261"],
    "LED-B1.10": ["iris_vector_graph/ledger/client.py:268-284", "iris_vector_graph/_write_txn.py:64-87"],
    "LED-B1.11": ["iris_src/src/Graph/KG/Ledger.cls:263-270"],
    "LED-B3.4": ["iris_src/src/Graph/KG/Ledger.cls:158-164"],
    "LED-B4.4": ["iris_src/src/Graph/KG/Ledger.cls:440-444", "iris_src/src/Graph/KG/Ledger.cls:397-414"],
    "LED-B4.5": ["iris_src/src/Graph/KG/Ledger.cls:445-446"],
    "LED-B4.6": ["iris_src/src/Graph/KG/Ledger.cls:447-450"],
    "LED-B4.7.1": ["iris_src/src/Graph/KG/Ledger.cls:454-465"],
    "LED-B4.8": ["iris_src/src/Graph/KG/Ledger.cls:475-486", "iris_vector_graph/ledger/errors.py:182-183"],
    "LED-B4.8.1": ["iris_src/src/Graph/KG/Ledger.cls:475-481"],
    "LED-B4.9": ["iris_src/src/Graph/KG/Ledger.cls:488-492"],
    "LED-B4.9.1": ["iris_src/src/Graph/KG/Ledger.cls:493-497", "iris_src/src/Graph/KG/Ledger.cls:72-80"],
    "LED-B4.9.2": ["iris_src/src/Graph/KG/Ledger.cls:488-509", "iris_vector_graph/ledger/client.py:381-401"],
    "LED-B4.11.8": ["iris_src/src/Graph/KG/Ledger.cls:554-555", "iris_src/src/Graph/KG/LedgerRevision.cls:30"],
    "LED-B4.13": ["iris_src/src/Graph/KG/Ledger.cls:397-414"],
    "LED-B5.6": ["iris_src/src/Graph/KG/LedgerApply.cls:223-228", "iris_src/src/Graph/KG/LedgerApply.cls:266-269",
                 "iris_src/src/Graph/KG/LedgerApply.cls:312-314", "iris_vector_graph/ledger/changeset.py:63-67"],
    "LED-B5.8": ["iris_src/src/Graph/KG/LedgerApply.cls:294-302"],
    "LED-B5.10": ["iris_src/src/Graph/KG/LedgerApply.cls:319-328"],
    "LED-B5.11": ["iris_src/src/Graph/KG/LedgerApply.cls:290", "iris_src/src/Graph/KG/LedgerApply.cls:380",
                  "iris_vector_graph/ledger/errors.py:184-195"],
    "LED-B5.12": ["iris_src/src/Graph/KG/LedgerApply.cls:197-203", "iris_src/src/Graph/KG/LedgerApply.cls:220",
                  "iris_src/src/Graph/KG/LedgerApply.cls:312"],
    "LED-B5.13": ["iris_src/src/Graph/KG/LedgerApply.cls:374-402", "iris_vector_graph/ledger/changeset.py:159-163"],
    "LED-B5.18": ["iris_src/src/Graph/KG/LedgerApply.cls:457-471"],
    "LED-B5.21": ["iris_src/src/Graph/KG/LedgerApply.cls:463", "iris_src/src/Graph/KG/LedgerApply.cls:576",
                  "iris_src/src/Graph/KG/LedgerApply.cls:593"],
    "LED-B5.26": ["iris_src/src/Graph/KG/LedgerApply.cls:581-584"],
    "LED-B5.27": ["iris_src/src/Graph/KG/LedgerApply.cls:182-211"],
    "LED-B6.7": ["iris_src/src/Graph/KG/LedgerApply.cls:204-206"],
    "LED-B7.1": ["iris_src/src/Graph/KG/LedgerRevision.cls:87-101"],
    "LED-B7.2": ["iris_src/src/Graph/KG/LedgerRevision.cls:103-108"],
    "LED-B7.3": ["iris_src/src/Graph/KG/LedgerRevision.cls:110-123"],
    "LED-B8.2": ["iris_vector_graph/ledger/changeset.py:47-60"],
    "LED-B8.4": ["iris_vector_graph/ledger/changeset.py:290-305", "iris_vector_graph/ledger/client.py:392"],
    "LED-B15.1": ["iris_src/src/Graph/KG/Ledger.cls:224-228", "iris_src/src/Graph/KG/SqlProcs.cls:200-202"],
}

FINDING = {"LED-B4.9.2": "F-1107"}

EXTRA = {
    "LED-B5.11": "Refused as not found (NodeNotFoundError, missing_node set) for set_property, add_label and delete_node; "
                 "the decoded message names create_relationship for every op (existing decoder finding F-C1109, not a "
                 "refusal defect).",
    "LED-B5.18": "The missing-end-node case decodes to NodeNotFoundError (narrowed from failed_op node_not_found).",
    "LED-B4.13": "The fault used is a malformed meta JSON (the server entry point the client calls; the client always "
                 "sends well-formed JSON), so it occurs before any write; a fault after a write was not constructed "
                 "(every malformed op shape found returns a reason instead of faulting). Inside a caller's "
                 "transaction the answer is inconsistent and $TLEVEL returns to the caller's level with the caller's "
                 "row still visible.",
    "LED-B4.4": "The head lock was held by the product itself: process 2 committed inside its own open transaction "
                "(4.7.0 keeps the head lock until that transaction ends); the refused commit waited the 30 s timeout.",
    "LED-B4.9.2": "Reproduces F-1107 live again: any kind string is accepted and stored, and only kind changeset gets "
                  "the empty and size checks.",
}

# statements whose stated condition no entry point can produce here
NOT_LIVE = {
    "LED-B3.4": ("holds-inspected",
                 "Enabled with head 0 is not reachable through any entry point: Enable writes the state, head and the "
                 "genesis revision in one transaction (Ledger.cls:288-319) and PurgeAll removes all three; forging it "
                 "would need a harness write into ^IVG.Ledger, which the audit does not make. Read at Ledger.cls:162 "
                 "(Err inconsistent before RevisionResponse). Live: the neighbouring branch (never enabled -> "
                 "not_enabled) holds."),
}


def main() -> int:
    run_id, res = sys.argv[1], Path(sys.argv[2])
    doc = json.loads(res.read_text())
    rerun = None
    if len(sys.argv) > 3:
        rerun = (sys.argv[3], json.loads(Path(sys.argv[4]).read_text()), set(sys.argv[5].split(",")))
    xs = {s["id"]: s for s in json.loads((LANE / "x-statements.json").read_text())["statements"] if s["module"] == "11"}
    cases = {}
    obs = {}
    for c in doc["cases"]:
        sid = c.get("statement")
        if not sid:
            continue
        if c.get("outcome") == "observation":
            obs.setdefault(sid, []).append(c)
        elif c.get("outcome") in ("holds-live", "refused-but-changed", "not-refused-as-stated"):
            cases.setdefault(sid, []).append(c)
    first = {}
    if rerun:
        first = {sid: cases.pop(sid, []) for sid in rerun[2]}
        for sid in rerun[2]:
            obs.pop(sid, None)
        for c in rerun[1]["cases"]:
            sid = c.get("statement")
            if sid in rerun[2]:
                if c.get("outcome") == "observation":
                    obs.setdefault(sid, []).append(c)
                elif c.get("outcome") in ("holds-live", "refused-but-changed", "not-refused-as-stated"):
                    cases.setdefault(sid, []).append(c)
    out = []
    for sid, s in xs.items():
        cs = cases.get(sid, [])
        rid = rerun[0] if rerun and sid in rerun[2] else run_id
        e = {"id": sid, "text": s["text"], "implementing_code": CODE[sid], "evidence": [f"run:{rid}"],
             "live_cases": [c["case"] for c in cs]}
        notes = []
        if sid in first:  # the first run is named in the notes only: its same-named cases used the strict oracle
            notes.append(f"Re-run as {rid} after {run_id}'s strict oracle flagged " + "; ".join(
                f"[{c['case']}] {c['outcome']}, net changes {c['journal']['changed_outside_allowed'][:4]}"
                for c in first[sid]) + ". The re-run reports nodes written only non-transactionally inside the "
                "commit's bracket (IRIS $INCREMENT-style, not undone by a rollback by design) separately")
        if sid in NOT_LIVE:
            e["outcome"], why = NOT_LIVE[sid]
            notes.append(why)
            if not cs:
                e.pop("live_cases")
        elif cs and all(c["outcome"] == "holds-live" for c in cs):
            e["outcome"] = "holds-live"
        elif cs:
            e["outcome"] = "product-defect"
            e["finding"] = FINDING.get(sid)
        else:
            e["outcome"] = "holds-inspected"
            e.pop("live_cases")
            notes.append("no live case recorded")
        for c in cs:
            ex = c.get("exception") or {}
            got = f"{ex.get('type')}: {ex.get('message', '')[:140]}" if ex else f"returned {str(c.get('returned'))[:140]}"
            j = c["journal"]
            notes.append(f"[{c['case']}] {c['outcome']}; {got}; journal records {j['records']}, "
                         f"net changes outside allowed {len(j['changed_outside_allowed'])}"
                         + (f", allowed changed {j['allowed_changed'][:3]}" if j['allowed_changed'] else "")
                         + (f", non-transactional increments {j.get('nontxn_increment_nodes')[:4]}"
                            if j.get('nontxn_increment_nodes') else "")
                         + (f"; obs {json.dumps(c.get('observations'))[:200]}" if c.get("observations") else ""))
        for o in obs.get(sid, []):
            d = {k: v for k, v in o.items() if k not in ("statement", "case", "outcome")}
            notes.append(f"(observation) {o['case']}: {json.dumps(d)[:200]}")
        if sid in EXTRA:
            notes.insert(0, EXTRA[sid])
        e["notes"] = " | ".join(notes)
        out.append(e)
    (LANE / "audit" / "11.json").write_text(json.dumps({"module": "11", "statements": out}, indent=1) + "\n")
    from collections import Counter
    print(Counter(e["outcome"] for e in out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
