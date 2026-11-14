#!/usr/bin/env python3
"""An equivalent, sub-quadratic `conformance.check_trace` for large traces (F-1201's 4,000 statements, lost-ack).

conformance.py (the orchestrator's oracle, unchanged) recomputes `recs(prior)` once per record of the state in its
tombstone count and, in `check_invariants`, scans every tuple entry for every live statement. Both are quadratic, so a
4,000-statement trace does not finish. This module repeats check_trace's logic line for line with two changes only:
`recs(prior)`/`recs(state)` computed once per transaction, and the stmt/tuple test done with a set of tuple values.
The rules (`conformance.step_rule`), frame, footprints and replay are conformance.py's own functions.

    python conformance_fast.py --equivalence TRACE.json...   # identical reports to conformance.check_trace,
                                                             # unmutated and under the five mutation controls
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import conformance, journal  # noqa: E402

C = conformance


def check_invariants(state, notes):
    tuple_vals = {str(v) for k, v in state.items() if len(k) == 5 and k[0] == "tuple"}
    for sid, row in C.stmts(state).items():
        if isinstance(row, tuple) and len(row) >= 6 and str(row[5]) == "":
            if sid not in tuple_vals:
                notes.append(f"INV stmt/tuple: live statement {sid} has no tuple entry")
    for (seq, ordn), v in C.recs(state).items():
        if isinstance(v, tuple) and v and v[0] == "redacted":
            if len(v) != 5 or not re.fullmatch(r"[0-9a-f]{64}", str(v[1])):
                notes.append(f"INV tombstone shape at ({seq},{ordn}): {v!r}")
    revs = {k[2]: v for k, v in state.items() if len(k) == 3 and k[:2] == ("redacting", "revs")}
    n = state.get(("redacting", "n", "records"))
    if revs and n is not None and sum(int(x) for x in revs.values()) != int(n):
        notes.append(f"INV counters: per-revision sum {sum(int(x) for x in revs.values())} != records {n}")


def check_trace(trace):
    before0, final_engine = C._state(trace["before"]), C._state(trace["final"])
    ops, recs_j, smap = trace["ops"], trace["journal"], trace["smap"]
    for o in ops:
        if "target" in o:
            o["target"] = tuple(o["target"])
    pid_ops = defaultdict(list)
    for o in ops:
        pid_ops[o["pid"]].append(o)
    units = journal.transactions(recs_j)
    state = dict(before0)
    report = {"ops": ops, "transactions": [], "violations": [], "frame": [], "unclassified": [], "checked": Counter()}
    for u in sorted(units, key=lambda u: u.get("end") or u.get("begin") or 0):
        olist = pid_ops.get(u["pid"])
        prior = dict(state)
        for r in u["records"]:
            if r["g"].startswith("^IVG.Ledger"):
                C.apply(state, r)
        if not olist:
            report["unclassified"].append({"pid": u["pid"], "n": len(u["records"])})
            continue
        o = olist[0]
        stores = {journal.store_of(r["g"], smap) for r in u["records"] if r["g"]}
        outside = sorted(stores - C.FOOTPRINT[o["op"]])
        notes = []
        if outside:
            report["frame"].append({"op": o["op"], "pid": u["pid"], "outside": outside})
        if u["kind"] == "txn" and u["committed"] and not u.get("rolled_back"):
            C.step_rule(o["op"], o, prior, state, notes)
            report["checked"][o["op"]] += 1
            rp, rs = C.recs(prior), C.recs(state)
            report["checked"]["tombstones"] += sum(1 for k, v in rs.items()
                                                   if isinstance(v, tuple) and v and v[0] == "redacted" and rp.get(k) != v)
        check_invariants(state, notes)
        report["transactions"].append({"op": o["op"], "pid": u["pid"], "kind": u["kind"], "committed": u["committed"],
                                       "rolled_back": u.get("rolled_back"), "records": len(u["records"]),
                                       "nested_levels": u.get("nested_levels"), "stores": sorted(stores), "notes": notes})
        report["violations"] += [f"{o['op']}@{u['pid']}: {n}" for n in notes]
    diff = [k for k in set(state) | set(final_engine) if state.get(k) != final_engine.get(k)]
    report["replay_matches_engine"] = not diff
    report["replay_diff_sample"] = [str(k) for k in diff[:10]]
    per_op = Counter((o["op"], o["pid"]) for o in ops)
    report["txn_count_per_op"] = {f"{k[0]}@{k[1]}": sum(1 for t in report["transactions"]
                                                         if t["pid"] == k[1] and t["kind"] == "txn") for k in per_op}
    report["checked"] = dict(report["checked"])
    return report


def _cmp(a, b):
    keys = ("violations", "frame", "checked", "replay_matches_engine", "unclassified", "txn_count_per_op")
    return all(json.dumps(a[k], sort_keys=True, default=str) == json.dumps(b[k], sort_keys=True, default=str) for k in keys)


def equivalence(paths) -> int:
    from check_all import EXTRA_FOOTPRINT
    for k, v in EXTRA_FOOTPRINT.items():
        C.FOOTPRINT.setdefault(k, v)
    ok = True
    for p in paths:
        t = json.loads(Path(p).read_text())
        variants = {"unmutated": t}
        for k in C.CONTROLS:
            try:
                variants[k] = C.mutate(t, k)
            except (StopIteration, IndexError):
                pass
        for name, v in variants.items():
            a = C.check_trace(json.loads(json.dumps(v)))
            b = check_trace(json.loads(json.dumps(v)))
            same = _cmp(a, b)
            ok &= same
            print(f"{Path(p).parent.name} {name}: {'identical' if same else 'DIFFERENT'} "
                  f"(violations {len(a['violations'])}/{len(b['violations'])}, frame {len(a['frame'])}/{len(b['frame'])})")
    print("equivalence", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--equivalence" in sys.argv:
        raise SystemExit(equivalence([a for a in sys.argv[1:] if a != "--equivalence"]))
