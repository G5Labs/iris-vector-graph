#!/usr/bin/env python3
"""Module 11 follow-up two-process checks on AUDITB (F-1102 harder, F-1103 racing re-enables).

    bash experiment/playbook-completion/tools/locks.sh iris timeout 1200 python experiment/playbook-completion/live/breadth-b/11_concurrency2.py

- F-1102a: four processes bump one counter 1,000 times each (Ledger.Count -> LedgerStats.Bump); counted vs 4,000.
- F-1102b: process A holds a caller transaction that saved the stats row (a nested commit, Ledger.cls:559-565) for
  20 s; process B bumps a counter once; B's wait, B's status and the counters after A rolls back.
- F-1103b: two engines re-enable a disabled ledger released together (both Enable calls race on the unlocked state
  read, Ledger.cls:254); their verify(adopt=True) record reads are aligned with a barrier at a Python call boundary
  in this harness (replay.read_canonical wrapped; no product file changed); count adoption revisions of the same
  unrecorded write and verify afterwards.
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


def part_a(s, ws, per=1000):
    C.purge(s.c)
    s.eng.ledger.enable()
    base = C.stats_row(s.c)["rej_lock_timeout"]
    bar = threading.Barrier(len(ws))
    errs = [0] * len(ws)

    def bump(i, w):
        bar.wait()
        for _ in range(per):
            try:
                if str(w.call(L, "Count", "rej_lock_timeout")) != "1":
                    errs[i] += 1
            except Exception:  # noqa: BLE001
                errs[i] += 1
    th = [threading.Thread(target=bump, args=(i, w)) for i, w in enumerate(ws)]
    t0 = time.time()
    for x in th:
        x.start()
    for x in th:
        x.join(600)
    after = C.stats_row(s.c)["rej_lock_timeout"]
    out = {"processes": len(ws), "calls": per * len(ws), "errors": errs, "seconds": round(time.time() - t0, 2),
           "counted": after - base}
    out["reproduced"] = out["counted"] + sum(errs) < out["calls"] or (out["counted"] < out["calls"])
    return out


def part_b(s, wa, wb, hold=20.0):
    C.purge(s.c)
    s.eng.create_node("b11_hold", labels=["B11"])
    s.eng.ledger.enable()
    ea = s.engine_on(wa, embedding_dimension=4)
    before = C.stats_row(s.c)
    cur = wa.conn.cursor()
    cur.execute("START TRANSACTION")
    x = Changeset(actor="b11-tester", actor_type="service", message="b11 held caller txn")
    x.set_property("b11_hold", "k", "v")
    r = ea.ledger.commit(x)
    res = {}

    def bump_b():
        t = time.time()
        try:
            res["status"] = str(wb.call(L, "Count", "rej_stale_head"))[:300]
        except Exception as e:  # noqa: BLE001
            res["status"] = "exception: " + str(e)[:300]
        res["seconds"] = round(time.time() - t, 3)
    tb = threading.Thread(target=bump_b)
    tb.start()
    time.sleep(hold)
    during = C.stats_row(s.c)
    cur.execute("ROLLBACK")
    cur.close()
    tb.join(120)
    after = C.stats_row(s.c)
    out = {"held_seconds": hold, "commit_seq_in_txn": r.revision.seq, "b_bump": res, "before": before,
           "during": during, "after_rollback": after,
           "b_counted": after["rej_stale_head"] - before["rej_stale_head"],
           "commits_ok_after": after["commits_ok"]}
    out["reproduced"] = out["b_counted"] < 1
    return out


def part_c(s, e1, e2, trials=6):
    out = {"trials": []}
    orig = replay_mod.read_canonical
    for t in range(trials):
        C.purge(s.c)
        C.scrub(s.c)
        s.eng.create_node("b11_a", labels=["B11"])
        s.eng.ledger.enable()
        s.eng.ledger.disable()
        s.eng.create_node(f"b11_u{t}", labels=["B11"])
        vbar = threading.Barrier(2, timeout=8)
        sbar = threading.Barrier(2)

        def wrapped(*a, **k):
            try:
                vbar.wait()
            except threading.BrokenBarrierError:
                pass
            return orig(*a, **k)
        replay_mod.read_canonical = wrapped
        res = [None, None]

        def go(i, e):
            sbar.wait()
            try:
                info = e.ledger.enable()
                res[i] = {"seq": info.seq, "kind": getattr(info, "kind", None)}
            except Exception as ex:  # noqa: BLE001
                res[i] = {"exception": type(ex).__name__, "msg": str(ex)[:300]}
        th = [threading.Thread(target=go, args=(0, e1)), threading.Thread(target=go, args=(1, e2))]
        for x in th:
            x.start()
        for x in th:
            x.join(120)
        replay_mod.read_canonical = orig
        revs = C.revisions(s.c)
        adoptions = [r_[0] for r_ in revs if r_[1] == "adoption"]
        recs = {a: C.records(s.c, a) for a in adoptions}
        same = sum(1 for v in recs.values() if any(f"b11_u{t}" in r_ for r_ in v))
        try:
            rep = s.eng.ledger.verify()
            ver = {"result": rep.result, "classification": rep.classification, "b11": C.diffs(rep)[:10]}
        except Exception as ex:  # noqa: BLE001
            ver = {"exception": type(ex).__name__, "msg": str(ex)[:300]}
        out["trials"].append({"trial": t, "answers": res, "adoptions": adoptions, "adoptions_of_same_write": same,
                              "verify_after": ver})
    replay_mod.read_canonical = orig
    out["double_adoption_trials"] = sum(1 for x in out["trials"] if x["adoptions_of_same_write"] >= 2)
    out["diverged_after"] = sum(1 for x in out["trials"] if x["verify_after"].get("result") not in ("equal",))
    out["reproduced"] = out["double_adoption_trials"] > 0
    C.purge(s.c)
    C.scrub(s.c)
    return out


def main() -> int:
    out = {}
    with session("11-concurrency2") as s:
        ws = [s.conn2() for _ in range(4)]
        out["pids"] = [s.c.pid] + [w.pid for w in ws]
        try:
            e1, e2 = s.engine_on(ws[0], embedding_dimension=4), s.engine_on(ws[1], embedding_dimension=4)
            for name, fn in (("F-1102a", lambda: part_a(s, ws)), ("F-1102b", lambda: part_b(s, ws[0], ws[1])),
                             ("F-1103b", lambda: part_c(s, e1, e2))):
                try:
                    out[name] = fn()
                except Exception as e:  # noqa: BLE001
                    import traceback
                    out[name] = {"exception": type(e).__name__, "msg": str(e)[:500], "tb": traceback.format_exc()[-2000:]}
                write_log(s, {"part": name, "result": out[name], "pids": out["pids"]}, name=f"11-conc2-{name}")
                print(name, json.dumps(out[name], default=str)[:1800], flush=True)
        finally:
            out["finish"] = C.finish(s, "11_concurrency2.py end")
            write_log(s, {"finish": out["finish"],
                          "reproduced": {k: v.get("reproduced") for k, v in out.items() if k.startswith("F-")}},
                      name="11-conc2-summary")
    print(json.dumps(out["finish"], default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
