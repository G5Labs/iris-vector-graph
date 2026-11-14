#!/usr/bin/env python3
"""Two redactions of different targets started together (model witness W1).

A long, ordinary ledger commit holds the head lock (a production ordering: Commit holds it while it
applies). Two redactions start while it runs; both pass LedgerRedact.Redact's marker and liveness checks,
which run before any lock, then wait for the head lock in their first batch. A watcher polls the marker
and, if it disappears while either run is still going, commits a node into that run's target.

Expected (spec 256 Decisions 1 and 3, ADR-0013): each run ends with its own content-free redaction
revision naming exactly the revisions it redacted and counting its own records; while a redaction of
a target is unfinished, a commit into that target is refused (redaction_in_progress).
"""
from __future__ import annotations

import json
import threading
import time

from redaction_common import connect, cs, engine, ensure_schema, ledger_records, marker, revision_rows, sha256, verdict, reset

N_TENANT = 5
N_FILLER = 3000
N_LOCKER = 12000


def main() -> int:
    conn, native = connect()
    eng = engine(conn)
    ensure_schema(eng)
    reset(eng, native)
    led = eng.ledger
    led.enable()
    for t in ("tA", "tB"):
        c = cs(f"{t} load", f"{t}|c", f"{t}-k", f"{t}-feed")
        for i in range(N_TENANT):
            c.create_node(f"{t}|{i}", properties={"v": f"{t}secret{i}"})
        led.commit(c)
    c = cs("filler", None, None, None)
    for i in range(N_FILLER):
        c.create_node(f"tC|{i}")
    led.commit(c)
    eng.delete_nodes_by_prefix("tA|")
    eng.delete_nodes_by_prefix("tB|")
    revs_seed = revision_rows(conn)
    seq_a = [s for s, r in revs_seed.items() if r["correlation_id"] == "tA|c"]
    seq_b = [s for s, r in revs_seed.items() if r["correlation_id"] == "tB|c"]

    events, results = [], {}
    running = {"A": False, "B": False}
    t0 = time.monotonic()

    def log(what, **kw):
        events.append({"t": round(time.monotonic() - t0, 4), "what": what, **kw})

    def locker():
        c2, _n2 = connect()
        e2 = engine(c2)
        big = cs("locker", None, None, None)
        for i in range(N_LOCKER):
            big.create_node(f"tD|{i}")
        log("locker start")
        e2.ledger.commit(big)
        log("locker end")

    def redactor(name, prefix, batch):
        c3, _n3 = connect()
        e3 = engine(c3)
        running[name] = True
        log(f"{name} start")
        try:
            r = e3.ledger.redact(None, prefix=prefix, batch_size=batch)
            results[name] = {"ok": True, "receipt": vars(r)}
        except Exception as ex:
            results[name] = {"ok": False, "error": type(ex).__name__, "message": str(ex)}
        running[name] = False
        log(f"{name} end", result=results[name].get("ok"))

    late = {}

    def watcher():
        c4, n4 = connect()
        e4 = engine(c4)
        while not (running["A"] or running["B"]):
            time.sleep(0.001)
        seen, ever = None, False
        while running["A"] or running["B"]:
            m = marker(n4)
            cur = m["target_sha256"] if m else None
            if cur != seen:
                log("marker", target_sha256=cur)
                seen = cur
            ever = ever or cur is not None
            if ever and cur is None and "commit" not in late and (running["A"] or running["B"]):
                who = "A" if running["A"] else "B"
                c = cs("late write", None, None, None)
                c.create_node(f"t{who}|late", properties={"v": "late"})
                try:
                    r = e4.ledger.commit(c)
                    late["commit"] = {"into": who, "accepted": True, "seq": r.revision.seq}
                except Exception as ex:
                    late["commit"] = {"into": who, "accepted": False, "error": type(ex).__name__, "message": str(ex)}
                log("late commit", **late["commit"])
            time.sleep(0.002)

    th_lock = threading.Thread(target=locker)
    th_lock.start()
    time.sleep(0.8)
    th_w = threading.Thread(target=watcher)
    th_a = threading.Thread(target=redactor, args=("A", "tA", N_TENANT))
    th_b = threading.Thread(target=redactor, args=("B", "tB", 2000))
    th_w.start()
    th_a.start()
    th_b.start()
    for th in (th_a, th_b, th_lock):
        th.join()
    running["A"] = running["B"] = False
    th_w.join()

    lock_end = next(e["t"] for e in events if e["what"] == "locker end")
    starts = [e["t"] for e in events if e["what"] in ("A start", "B start")]
    raced = all(s < lock_end for s in starts)
    revs = revision_rows(conn)
    audits = [r for r in revs.values() if r["kind"] == "redaction"]
    recs = ledger_records(native)
    audit_named = {a["seq"]: sorted(int(f[2]) for (s, _o), f in recs.items() if s == a["seq"] and f[0] == "redact") for a in audits}
    for a in audits:
        a["source_parsed"] = json.loads(a["source"]) if a["source"] else None
    dig = {"A": sha256("\x00tA|"), "B": sha256("\x00tB|")}
    tomb_seqs = sorted({s for (s, _o), f in recs.items() if f[0] == "redacted"})
    data = {"events": events, "results": results, "late": late, "raced_entry_checks": raced,
            "seq_tenant_a": seq_a, "seq_tenant_b": seq_b, "audit_revisions": audits, "audit_names": audit_named,
            "target_digests": dig, "tombstoned_seqs": tomb_seqs, "marker_after": marker(native)}
    if not raced:
        data["verdict"] = "INCONCLUSIVE"
        print("redaction_concurrent_targets: INCONCLUSIVE — the locker commit finished before both redactions started")
        from redaction_common import record
        record("redaction_concurrent_targets", data)
        return 0
    per_target_ok = len(audits) == 2 and all(
        sorted(audit_named[a["seq"]]) == sorted(seq_a if a["source_parsed"]["target_sha256"] == dig["A"] else seq_b)
        for a in audits)
    late_ok = ("commit" not in late) or (not late["commit"]["accepted"])
    ok = per_target_ok and late_ok
    reason = (f"audit revisions={len(audits)} names={audit_named} digests={[a['source_parsed']['target_sha256'][:8] for a in audits]} "
              f"A={results.get('A')} B={results.get('B')} late={late.get('commit')}")
    return verdict("redaction_concurrent_targets", ok, reason, data)


if __name__ == "__main__":
    raise SystemExit(main())
