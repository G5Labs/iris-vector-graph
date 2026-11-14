#!/usr/bin/env python3
"""Module 11 (ledger core) two-process live checks on AUDITB: F-1104, F-1102, F-1103 (and the F-1113 redo).

    bash experiment/playbook-completion/tools/locks.sh iris timeout 900 python experiment/playbook-completion/live/breadth-b/11_concurrency.py

Three IRIS connections (one server process each): the session's, and two workers. Every part starts from the pin's
ledger reset (Ledger.PurgeAll, Ledger.cls:241-248) and the script ends with strict off and a never-enabled ledger.

- F-1104: two Graph.KG.Ledger.Enable calls released together on a never-enabled ledger (genesis over ~1,500 b11
  nodes so the genesis transaction is long enough to overlap); repeated trials; outcomes of both calls.
- F-1102: (a) two processes bump one counter concurrently (Ledger.Count -> LedgerStats.Bump, a %OpenId/%Save
  read-modify-write, LedgerStats.cls:65-88); final count vs calls; (b) process A commits inside its own caller
  transaction (stats row saved inside it, Ledger.cls:559-565), process B bumps a counter, A rolls back.
- F-1103: verify(adopt=True) with a forced interleaving at a Python call boundary in this harness process (no
  product file changed): replay.read_canonical is wrapped so another process's commit (or a whole concurrent
  re-enable) runs after verify read the records up to the head and before it reads the stores.
"""
from __future__ import annotations

import importlib
import json
import sys
import threading
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
C = importlib.import_module("11_common")
from blive import session, write_log  # noqa: E402

from iris_vector_graph.ledger.changeset import Changeset  # noqa: E402
import iris_vector_graph.ledger.replay as replay_mod  # noqa: E402

warnings.simplefilter("ignore", DeprecationWarning)
L = C.L


def cs(**kw):
    kw.setdefault("actor", "b11-tester")
    kw.setdefault("actor_type", "service")
    return Changeset(**kw)


def seed_nodes(c, n):
    cur = c.conn.cursor()
    try:
        cur.executemany("INSERT INTO Graph_KG.nodes (node_id) VALUES (?)", [(f"b11_g{i:05d}",) for i in range(n)])
        cur.executemany("INSERT INTO Graph_KG.rdf_props (s, \"key\", val) VALUES (?, ?, ?)",
                        [(f"b11_g{i:05d}", "name", f"n{i}") for i in range(n)])
    finally:
        cur.close()


def part_f1104(s, w1, w2, trials=8, n=1500):
    out = {"trials": []}
    C.scrub(s.c)
    seed_nodes(s.c, n)
    for t in range(trials):
        C.purge(s.c)
        res = [None, None]
        bar = threading.Barrier(2)

        def go(i, w):
            bar.wait()
            t0 = time.time()
            try:
                res[i] = {"answer": json.loads(str(w.call(L, "Enable", 0, 50000, 250000, "Graph_KG"))),
                          "t0": t0, "t1": time.time()}
            except Exception as e:  # noqa: BLE001
                res[i] = {"exception": str(e)[:300], "t0": t0, "t1": time.time()}
        th = [threading.Thread(target=go, args=(0, w1)), threading.Thread(target=go, args=(1, w2))]
        for x in th:
            x.start()
        for x in th:
            x.join(120)
        oks = [bool(r and r.get("answer", {}).get("ok")) for r in res]
        errs = [r.get("answer", {}).get("error") if r and "answer" in r else "exception" for r in res]
        out["trials"].append({"trial": t, "ok": oks, "errors": errs,
                              "reasons": [(r.get("answer", {}).get("reason") or "")[:160] if r else None for r in res],
                              "head_seen": [((r.get("answer", {}).get("revision") or {}).get("seq")) if r else None for r in res],
                              "elapsed": [round(r["t1"] - r["t0"], 3) if r else None for r in res],
                              "meta_after": C.meta(s.c), "revisions": len(C.revisions(s.c))})
    out["both_ok"] = sum(1 for t in out["trials"] if all(t["ok"]))
    out["one_failed"] = sum(1 for t in out["trials"] if not all(t["ok"]))
    out["reproduced"] = out["one_failed"] > 0
    C.purge(s.c)
    C.scrub(s.c)
    return out


def part_f1102(s, w1, w2, per=300):
    out = {}
    C.purge(s.c)
    s.eng.ledger.enable()
    base = C.stats_row(s.c)
    bar = threading.Barrier(2)
    errs = [0, 0]

    def bump(i, w):
        bar.wait()
        for _ in range(per):
            try:
                st = w.call(L, "Count", "rej_lock_timeout")
                if str(st) != "1":
                    errs[i] += 1
            except Exception:  # noqa: BLE001
                errs[i] += 1
    th = [threading.Thread(target=bump, args=(0, w1)), threading.Thread(target=bump, args=(1, w2))]
    t0 = time.time()
    for x in th:
        x.start()
    for x in th:
        x.join(300)
    after = C.stats_row(s.c)
    out["a_concurrent_bumps"] = {"calls": 2 * per, "errors": errs, "seconds": round(time.time() - t0, 2),
                                 "before": base["rej_lock_timeout"], "after": after["rej_lock_timeout"],
                                 "counted": after["rej_lock_timeout"] - base["rej_lock_timeout"]}
    out["a_reproduced"] = out["a_concurrent_bumps"]["counted"] < 2 * per

    # (b) caller transaction on w1 holds a nested commit (stats row saved inside it); w2 bumps; w1 rolls back
    e1 = s.engine_on(w1, embedding_dimension=4)
    before = C.stats_row(s.c)
    cur = w1.conn.cursor()
    cur.execute("START TRANSACTION")
    x = cs(message="b11 in caller txn")
    x.create_node("b11_ct1")
    r = e1.ledger.commit(x)
    out["b_commit_in_caller_txn"] = {"seq": r.revision.seq}
    mid = C.stats_row(s.c)
    bres = []

    def bump_b():
        for _ in range(3):
            t = time.time()
            try:
                st = str(w2.call(L, "Count", "rej_stale_head"))
            except Exception as e:  # noqa: BLE001
                st = "exception: " + str(e)[:200]
            bres.append({"status": st[:200], "seconds": round(time.time() - t, 3)})
    tb = threading.Thread(target=bump_b)
    tb.start()
    tb.join(2.5)
    mid2 = C.stats_row(s.c)
    cur.execute("ROLLBACK")
    cur.close()
    tb.join(120)
    after = C.stats_row(s.c)
    out["b_rollback_before_image"] = {"before": before, "after_commit_in_txn": mid, "while_b_bumped": mid2,
                                      "after_rollback": after, "b_calls": bres,
                                      "b_counted_after_rollback": after["rej_stale_head"] - before["rej_stale_head"],
                                      "b_successful_calls": sum(1 for b in bres if b["status"] == "1")}
    out["b_reproduced"] = (out["b_rollback_before_image"]["b_successful_calls"] >
                           out["b_rollback_before_image"]["b_counted_after_rollback"])
    out["reproduced"] = out["a_reproduced"] or out["b_reproduced"]
    C.purge(s.c)
    C.scrub(s.c)
    return out


def part_f1103(s, w1):
    """Forced interleavings around verify(adopt=True)."""
    out = {}
    e1 = s.engine_on(w1, embedding_dimension=4)
    orig = replay_mod.read_canonical

    # (a) a commit lands between the record read and the store read of a re-enable's adoption
    C.purge(s.c)
    C.scrub(s.c)
    s.eng.create_node("b11_a", labels=["B11"])
    s.eng.create_node("b11_b", labels=["B11"])
    s.eng.ledger.enable()
    s.eng.ledger.disable()
    s.eng.create_node("b11_u1", labels=["B11"])       # unrecorded while disabled
    injected = {}

    def wrapped(*a, **k):
        if not injected:
            x = cs(message="b11 commit during adoption")
            x.create_relationship("b11_a", "B11T", "b11_b")
            r = e1.ledger.commit(x)
            injected["commit"] = {"seq": r.revision.seq, "stmt_ids": {str(k2): v for k2, v in r.stmt_ids.items()}}
        return orig(*a, **k)
    replay_mod.read_canonical = wrapped
    try:
        info = s.eng.ledger.enable()
    finally:
        replay_mod.read_canonical = orig
    out["a_injected_commit"] = injected
    out["a_enable_answer"] = {"seq": info.seq, "kind": getattr(info, "kind", None)}
    out["a_revisions"] = C.revisions(s.c)
    out["a_adoption_records"] = C.records(s.c, info.seq)
    try:
        rep = s.eng.ledger.verify()
        out["a_verify_after"] = {"result": rep.result, "classification": rep.classification, "b11": C.diffs(rep)}
    except Exception as e:  # noqa: BLE001
        out["a_verify_after"] = {"exception": type(e).__name__, "msg": str(e)[:400]}
    out["a_reproduced"] = (any("B11T" in r for r in out["a_adoption_records"])
                           or out["a_verify_after"].get("result") != "equal")

    # (b) two re-enables: the second runs completely while the first sits between its record read and store read
    C.purge(s.c)
    C.scrub(s.c)
    s.eng.create_node("b11_a", labels=["B11"])
    s.eng.ledger.enable()
    s.eng.ledger.disable()
    s.eng.create_node("b11_u2", labels=["B11"])
    injected2 = {}

    def wrapped2(*a, **k):
        if not injected2:
            injected2["started"] = True
            info2 = e1.ledger.enable()
            injected2["other_enable"] = {"seq": info2.seq, "kind": getattr(info2, "kind", None)}
        return orig(*a, **k)
    replay_mod.read_canonical = wrapped2
    try:
        info = s.eng.ledger.enable()
    finally:
        replay_mod.read_canonical = orig
    out["b_other_enable"] = injected2
    out["b_enable_answer"] = {"seq": info.seq, "kind": getattr(info, "kind", None)}
    out["b_revisions"] = C.revisions(s.c)
    adoptions = [r for r in out["b_revisions"] if r[1] == "adoption"]
    out["b_adoption_records"] = {r[0]: C.records(s.c, r[0]) for r in adoptions}
    try:
        rep = s.eng.ledger.verify()
        out["b_verify_after"] = {"result": rep.result, "classification": rep.classification, "b11": C.diffs(rep)}
    except Exception as e:  # noqa: BLE001
        out["b_verify_after"] = {"exception": type(e).__name__, "msg": str(e)[:400]}
    out["b_reproduced"] = len(adoptions) >= 2 and sum(
        1 for recs in out["b_adoption_records"].values() if any("b11_u2" in r for r in recs)) >= 2
    out["reproduced"] = out["a_reproduced"] or out["b_reproduced"]
    C.purge(s.c)
    C.scrub(s.c)
    return out


def part_f1113(s):
    out = {}
    C.purge(s.c)
    s.eng.create_node("b11_src", labels=["B11"])
    s.eng.ledger.enable()
    x = cs(message="b11 sourced", source={"system": "cmms", "run": "b11"})
    x.set_property("b11_src", "k", "v")
    r = s.eng.ledger.commit(x)
    out["seq"] = r.revision.seq
    stored = s.c.sql("SELECT source FROM Graph_KG.ledger_revisions WHERE seq = ?", r.revision.seq)[0][0]
    out["stored_source_text"] = stored
    out["history_source_cmms"] = len(s.eng.ledger.history(source="cmms", limit=1000).revisions)
    out["history_source_stored_text"] = len(s.eng.ledger.history(source=stored, limit=1000).revisions)
    out["history_source_python_sorted_json"] = len(s.eng.ledger.history(
        source=json.dumps({"run": "b11", "system": "cmms"}, separators=(",", ":")), limit=1000).revisions)
    out["history_source_python_insertion_json"] = len(s.eng.ledger.history(
        source=json.dumps({"system": "cmms", "run": "b11"}, separators=(",", ":")), limit=1000).revisions)
    out["reproduced"] = out["history_source_cmms"] == 0 and out["history_source_stored_text"] >= 1
    C.purge(s.c)
    C.scrub(s.c)
    return out


def main() -> int:
    out = {}
    with session("11-concurrency") as s:
        w1, w2 = s.conn2(), s.conn2()
        out["pids"] = {"session": s.c.pid, "w1": w1.pid, "w2": w2.pid}
        out["meta_at_start"] = C.meta(s.c)
        try:
            for name, fn in (("F-1113", lambda: part_f1113(s)), ("F-1104", lambda: part_f1104(s, w1, w2)),
                             ("F-1102", lambda: part_f1102(s, w1, w2)), ("F-1103", lambda: part_f1103(s, w1))):
                try:
                    out[name] = fn()
                except Exception as e:  # noqa: BLE001
                    import traceback
                    out[name] = {"exception": type(e).__name__, "msg": str(e)[:500], "tb": traceback.format_exc()[-2000:]}
                write_log(s, {"part": name, "result": out[name], "pids": out["pids"]}, name=f"11-conc-{name}")
                print(name, json.dumps(out[name], default=str)[:1500], flush=True)
        finally:
            out["finish"] = C.finish(s, "11_concurrency.py end")
            write_log(s, {"finish": out["finish"],
                          "reproduced": {k: v.get("reproduced") for k, v in out.items() if k.startswith("F-")}},
                      name="11-conc-summary")
    print(json.dumps(out["finish"], default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
