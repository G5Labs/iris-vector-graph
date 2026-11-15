#!/usr/bin/env python3
"""Checks over the correspondence lane's traces: conformance step rules and frame, the abstraction function, keys
and foreign keys (§3.6), aggregated.

    python check_all.py TRACE_DIR... --json OUT

Per trace:
- conformance.check_trace (the orchestrator's oracle, unchanged; run as conformance_fast.check_trace, its equivalent): spec step rules of commit/erase/redact, ledger
  invariants (stmt/tuple, tombstone shape, counters), frame (every store a transaction wrote is in its operation's
  declared footprint) and the faithful replay of ^IVG.Ledger. Operation kinds the scenario adds get declared footprints
  here (from source reading, cited); conformance.FOOTPRINT's own entries are not changed.
- abstraction.check: alpha(before) -> alpha(after) is a step of the participant contracts with the operation's label.
- keys: ^IVG.Ledger("head") and ("stmtNext") SET values strictly increase by one in journal order; a statement id is
  created (SET with no old value) at most once and never after it was killed; ledger_revisions seqs are unique and
  are exactly 1..head; idBySeq/revById are mutually inverse and agree with ledger_revisions.revision_id.
- fk: in the final rows every rdf_edges (graph_id, s) and (graph_id, o_id), and every rdf_labels (graph_id, s), has its
  nodes row; every transaction of an erasure committed (IRIS enforces the composite FKs at statement time, so a
  committed erasure deleted in an FK-safe order).
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import abstraction  # noqa: E402
import conformance_fast  # noqa: E402
from common import conformance, journal  # noqa: E402

CONTENT = {"sql:Graph_KG.nodes", "sql:Graph_KG.rdf_edges", "sql:Graph_KG.rdf_labels", "sql:Graph_KG.rdf_props",
           "global:^KG", "global:^NKG", "global:^IVG.AdjNoLock", "global:^IVG.ArnoVersion", "global:^IVG.AlgoCache",
           "global:^IVG.GraphMode"}
EXTRA_FOOTPRINT = {
    # Ledger.Disable / SetStrict / Enable from disabled (Ledger.cls:252-383): meta state/strict and the stats row
    "setenabled": {"global:^IVG.Ledger", "sql:Graph_KG.ledger_stats"},
    # engine.create_node / create_edge (nodes_edges.py:968, 1151): the content tables and derived globals only
    "bypass": CONTENT | {"sql:Graph_KG.docs"},
    # Python readers (client.py:695-739, replay.py): nothing
    "read": set(),
    # a probe process holding a lock: nothing
    "probe": set(),
}


def keys_check(trace):
    notes = []
    recs = sorted(trace["journal"], key=lambda r: r["a"])
    units = journal.transactions(recs)
    rolled = {id(r) for u in units if u.get("rolled_back") for r in u["records"]}
    last = {}
    created, killed = set(), set()
    for r in recs:
        if id(r) in rolled or not r["g"].startswith("^IVG.Ledger"):
            continue
        _, subs = conformance.parse_ref(r["g"])
        if subs in (("head",), ("stmtNext",)) and r["t"] == "SET":
            v = int(conformance.decode_value(r["n"]) or 0)
            p = last.get(subs)
            if p is not None and v != p + 1 and not (subs == ("head",) and v == 0):
                notes.append(f"{subs[0]}: {p} -> {v}")
            last[subs] = v
        if len(subs) == 2 and subs[0] == "stmt":
            sid = subs[1]
            if r["t"] == "SET" and r["o"] is None:
                if sid in created or sid in killed:
                    notes.append(f"stmt id {sid} created twice (reuse)")
                created.add(sid)
                nxt = last.get(("stmtNext",))
                if nxt is not None and int(sid) >= nxt:
                    notes.append(f"stmt id {sid} >= stmtNext {nxt}")
            elif r["t"] in ("KILL", "ZKILL"):
                killed.add(sid)
    fin = conformance._state(trace["final"])
    head = int(fin.get(("head",)) or 0)
    rf = trace.get("rows_final")
    if rf:
        seqs = [int(r[0]) for r in rf["revisions"]]
        if len(seqs) != len(set(seqs)):
            notes.append(f"ledger_revisions seq not unique: {Counter(seqs).most_common(2)}")
        if sorted(seqs) != list(range(1, head + 1)):
            notes.append(f"ledger_revisions seqs {sorted(seqs)[:5]}.. != 1..{head}")
        rid = {int(r[0]): r[1] for r in rf["revisions"]}
        for s in range(1, head + 1):
            i = fin.get(("idBySeq", s))
            if i is None or str(fin.get(("revById", str(i)))) != str(s) or rid.get(s) != str(i):
                notes.append(f"seq {s}: idBySeq {i} revById {fin.get(('revById', str(i)))} row {rid.get(s)}")
    return notes, {"stmt_ids_created": len(created), "stmt_ids_killed": len(killed), "head": head,
                   "last_stmtNext": last.get(("stmtNext",))}


def fk_check(trace):
    rf = trace.get("rows_final")
    notes = []
    if rf:
        nodes = {(abstraction.gname(g), n) for n, g in rf["nodes"]}
        for _e, s, p, o, g, _q in rf["edges"]:
            g = abstraction.gname(g)
            if (g, s) not in nodes or (g, o) not in nodes:
                notes.append(f"edge {(g, s, p, o)} without its node rows")
        for s, label, g in rf["labels"]:
            if (abstraction.gname(g), s) not in nodes:
                notes.append(f"label {(g, s, label)} without node")
    for o in trace["ops"]:
        if o["op"] == "erase" and o.get("ok") is False and o.get("expect", "ok") == "ok":
            notes.append(f"erasure {o.get('label')} failed: {str(o.get('result'))[:200]}")
    return notes


def main() -> int:
    dirs = [Path(a) for a in sys.argv[1:] if not a.startswith("--")]
    out = Path(sys.argv[sys.argv.index("--json") + 1])
    dirs = [d for d in dirs if d != out]
    for k, v in EXTRA_FOOTPRINT.items():
        conformance.FOOTPRINT.setdefault(k, v)
    agg = {"traces": {}}
    for d in dirs:
        t = json.loads((d / "trace.json").read_text())
        # conformance_fast.check_trace: conformance.check_trace's logic with its two quadratic loops indexed; identical
        # reports on every trace and mutation control it was compared on (conformance_fast.py --equivalence)
        rep = conformance_fast.check_trace(json.loads(json.dumps(t)))
        ab = abstraction.check(t)
        kn, kinfo = keys_check(t)
        fk = fk_check(t)
        stores = sorted({s for tr in rep["transactions"] for s in tr["stores"]})
        agg["traces"][d.name] = {
            "conformance": {"violations": rep["violations"], "frame": rep["frame"], "checked": rep["checked"],
                            "replay_matches_engine": rep["replay_matches_engine"], "unclassified": rep["unclassified"],
                            "transactions": len(rep["transactions"]), "stores_written": stores,
                            "per_op_stores": sorted({(tr["op"], s) for tr in rep["transactions"] for s in tr["stores"]})},
            "abstraction": {"violations": ab["violations"], "premise_instances": ab["premise_instances"],
                            "protocol": ab.get("protocol", []), "mode": ab.get("mode", "per-operation"),
                            "invariant_notes": ab["invariant_notes"], "skipped": ab.get("skipped"),
                            "ops": [{k: o[k] for k in ("label", "op", "ok", "notes")} for o in ab["ops"]]},
            "keys": {"notes": kn, **kinfo}, "fk": fk,
            "ops": [{"label": o.get("label", o["op"]), "op": o["op"], "ok": o["ok"], "expect": o.get("expect"),
                     "result": str(o.get("result"))[:200]} for o in t["ops"]],
        }
        s = agg["traces"][d.name]
        print(d.name, "conformance violations", len(rep["violations"]), "frame", len(rep["frame"]), "replay",
              rep["replay_matches_engine"], "| abstraction violations", len(ab["violations"]), "premises",
              len(ab["premise_instances"]), "protocol", len(ab.get("protocol", [])), "inv notes", len(ab["invariant_notes"]), "| keys", len(kn), "| fk", len(fk))
    out.write_text(json.dumps(agg, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
