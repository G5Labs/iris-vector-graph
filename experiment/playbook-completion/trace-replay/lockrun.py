#!/usr/bin/env python3
"""Lock logs per module, checked against the lock plan (playbook §3.7).

    python lockrun.py NN [NN ...]      # live, under tools/locks.sh iris; writes $RUN_DIR/trace-replay/locklog/NN.json

For each module: workloads that run the module's writers in a loop in one process while locklog.Poller polls the
planned lock names (and a second poller scans the whole lock table for unplanned IVG/KG/table locks), and block probes
that hold one planned lock in another process. The plan (`PLANS`) is the footprint files' `locks` entries and the
source lines they cite; `check()` compares what was observed with it, item by item.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
import locklog  # noqa: E402
import trlib  # noqa: E402
from common import cs, engine, gkey, reset  # noqa: E402
from iris_conn import Conn  # noqa: E402

OUT = trlib.run_dir() / "locklog"


def _loop(deadline, fn):
    n, errors = 0, []
    while time.time() < deadline:
        try:
            fn(n)
        except Exception as ex:  # noqa: BLE001
            errors.append(f"{type(ex).__name__}: {str(ex)[:160]}")
        n += 1
    return {"iterations": n, "errors": errors[:5], "error_count": len(errors)}


def adjw(gk: str) -> str:
    return f'^IVG.AdjW({gk if gk.lstrip("-").isdigit() else json.dumps(gk)})'


# ------------------------------------------------------------------------------------------------ workloads per module

def m03() -> Dict:
    reset()
    g = "tr03lk"
    gk = gkey(g)
    names = [adjw(gk), "^IVG.AdjW", "^NKG", "^IVG.NKGBuild", '^IVG.Ledger("head")']
    res = {"plan_names": names, "workloads": {}, "probes": {}}

    def edges(x, deadline):
        e = engine(x)
        return _loop(deadline, lambda n: (e.create_edge(f"s{n}", "R", f"o{n}", graph=g),
                                          e.delete_edge(f"s{n}", "R", f"o{n}", graph=g)))
    res["workloads"]["create_edge+delete_edge"] = locklog.run_workload(names, 6, edges)

    def nodes(x, deadline):
        e = engine(x)
        return _loop(deadline, lambda n: e.create_node(f"n{n}", labels=["L"], properties={"p": n}, graph=g))
    res["workloads"]["create_node"] = locklog.run_workload(names, 4, nodes)
    res["probes"]["create_edge vs AdjW(g) held exclusively"] = locklog.block_probe(
        ["^IVG.AdjW", gk], "", lambda x: engine(x).create_edge("ps", "R", "po", graph=g), hold=7.0)
    return res


def m04() -> Dict:
    reset()
    g = "tr04lk"
    gk = gkey(g)
    c = Conn(trlib.NS)
    try:
        e = engine(c)
        for i in range(30):
            e.create_edge("hub", "R", f"t{i}", graph=g)
    finally:
        c.close()
    names = [adjw(gk), "^IVG.AdjW", "^NKG", "^IVG.NKGBuild", '^IVG.Ledger("head")']
    res = {"plan_names": names, "workloads": {}, "probes": {}}

    def degree(x, deadline):
        def one(n):
            x.call("Graph.KG.Adj", "Degree", gk, "hub")
            if n % 5 == 0:
                engine(x).create_edge("hub", "R", f"d{n}", graph=g)   # moves the generation: the next call recounts
        return _loop(deadline, one)
    res["workloads"]["Adj.Degree (+ a write every 5th call)"] = locklog.run_workload(names, 5, degree)

    def sync(x, deadline):
        e = engine(x)
        return _loop(deadline, lambda n: e.sync())
    res["workloads"]["sync (BuildKG)"] = locklog.run_workload(names, 8, sync)
    res["probes"]["sync vs ^IVG.AdjW held exclusively"] = locklog.block_probe(
        ["^IVG.AdjW"], "", lambda x: engine(x).sync(), hold=7.0)
    res["probes"]["Adj.Degree vs AdjW(g) held shared"] = locklog.block_probe(
        ["^IVG.AdjW", gk], "S", lambda x: x.call("Graph.KG.Adj", "Degree", gk, "hub"), hold=3.0)
    return res


def m05() -> Dict:
    reset()
    g = "tr05lk"
    gk = gkey(g)
    names = [adjw(gk), "^IVG.AdjW", "^NKG", "^IVG.NKGBuild", '^IVG.Ledger("head")']
    res = {"plan_names": names, "workloads": {}, "probes": {}}

    def temporal(x, deadline):
        e = engine(x)
        return _loop(deadline, lambda n: (e.create_edge_temporal(f"s{n}", "P", f"o{n}", timestamp=1000 + n, graph=g),
                                          e.delete_edge_temporal(f"s{n}", "P", f"o{n}", 1000 + n, graph=g)))
    res["workloads"]["create_edge_temporal+delete_edge_temporal"] = locklog.run_workload(names, 6, temporal)
    res["probes"]["create_edge_temporal vs AdjW(g) held exclusively"] = locklog.block_probe(
        ["^IVG.AdjW", gk], "", lambda x: engine(x).create_edge_temporal("ps", "P", "po", timestamp=5, graph=g), hold=7.0)
    return res


def m02() -> Dict:
    reset()
    g = "tr02lk"
    gk = gkey(g)
    names = [adjw(gk), "^IVG.AdjW", f'^IVG.GraphMode({json.dumps(g)})', "^IVG.GraphMode", '^IVG.Ledger("head")']
    res = {"plan_names": names, "workloads": {}, "probes": {}}

    def modes(x, deadline):
        e = engine(x)
        return _loop(deadline, lambda n: e.set_multigraph(g, n % 2 == 0))
    res["workloads"]["set_multigraph on/off"] = locklog.run_workload(names, 5, modes)
    res["probes"]["set_multigraph(off) vs AdjW(g) held exclusively"] = locklog.block_probe(
        ["^IVG.AdjW", gk], "", lambda x: engine(x).set_multigraph(g, False), hold=3.0,
        setup=lambda c: engine(c).set_multigraph(g, True))
    return res


def m06() -> Dict:
    reset()
    g = "tr06lk"
    gk = gkey(g)
    c = Conn(trlib.NS)
    try:
        e = engine(c)
        for i in range(5):
            e.create_node(f"v{i}", graph=g)
        c.call("Graph.KG.IVFIndex", "Build", "tr06lkivf", "2", '"cosine"', "[[1,0,0,0],[0,1,0,0]]", "[]", "")
    finally:
        c.close()
    names = [adjw(gk), "^IVG.AdjW", '^IVG.Ledger("head")', '^IVF("tr06lkivf")', "^EmbedQueue"]
    res = {"plan_names": names, "workloads": {}, "probes": {}}

    def vectors(x, deadline):
        e = engine(x)
        return _loop(deadline, lambda n: (e.store_embedding(f"v{n % 5}", [1.0, n % 3, 0.0, 0.0], graph=g),
                                          e.ivf_insert("tr06lkivf", f"v{n % 5}", [1.0, 0.0, 0.0, 0.0])))
    res["workloads"]["store_embedding+ivf_insert"] = locklog.run_workload(names, 5, vectors)
    res["probes"]["store_embedding vs ^IVG.Ledger(head) held exclusively"] = locklog.block_probe(
        ["^IVG.Ledger", "head"], "", lambda x: engine(x).store_embedding("v0", [0.0, 1.0, 0.0, 0.0], graph=g), hold=3.0)
    res["probes"]["store_embedding vs AdjW(g) held exclusively"] = locklog.block_probe(
        ["^IVG.AdjW", gk], "", lambda x: engine(x).store_embedding("v1", [0.0, 1.0, 0.0, 0.0], graph=g), hold=3.0)

    def after():
        c = Conn(trlib.NS)
        try:
            c.o.classMethodVoid("Graph.KG.IVFIndex", "Drop", "tr06lkivf")
        finally:
            c.close()
    after()
    return res


def m08() -> Dict:
    reset()
    g = "tr08lk"
    gk = gkey(g)
    names = [adjw(gk), "^IVG.AdjW", '^IVG.Ledger("head")', "^NKG"]
    res = {"plan_names": names, "workloads": {}, "probes": {}}

    def cypher(x, deadline):
        e = engine(x)
        return _loop(deadline, lambda n: (
            e.execute_cypher(f"USE GRAPH '{g}' CREATE (a:L {{node_id: 'c{n}'}})-[:R]->(b:L {{node_id: 'd{n}'}})", {},
                             raise_on_error=True),
            e.execute_cypher(f"USE GRAPH '{g}' MATCH (a {{node_id: 'c{n}'}})-[r:R]->() DELETE r", {}, raise_on_error=True)))
    res["workloads"]["Cypher CREATE + DELETE"] = locklog.run_workload(names, 6, cypher)
    res["probes"]["Cypher CREATE vs AdjW(g) held exclusively"] = locklog.block_probe(
        ["^IVG.AdjW", gk], "", lambda x: engine(x).execute_cypher(
            f"USE GRAPH '{g}' CREATE (a:L {{node_id: 'pc'}})-[:R]->(b:L {{node_id: 'pd'}})", {}, raise_on_error=True),
        hold=7.0)
    return res


def m10() -> Dict:
    reset()
    g = "tr10lk"
    gk = gkey(g)
    c = Conn(trlib.NS)
    try:
        e = engine(c)
        for i in range(20):
            e.create_edge(f"a{i}", "R", f"a{(i + 1) % 20}", graph=g)
    finally:
        c.close()
    names = [adjw(gk), "^IVG.AdjW", "^NKG", "^IVG.NKGBuild", '^IVG.Ledger("head")', "^IVG.AlgoCache"]
    res = {"plan_names": names, "workloads": {}, "probes": {}}

    def nkg(x, deadline):
        e = engine(x)
        return _loop(deadline, lambda n: e.rebuild_nkg())
    res["workloads"]["rebuild_nkg"] = locklog.run_workload(names, 6, nkg)
    res["probes"]["rebuild_nkg vs ^IVG.NKGBuild held exclusively"] = locklog.block_probe(
        ["^IVG.NKGBuild"], "", lambda x: engine(x).rebuild_nkg(), hold=4.0)
    return res


def m13() -> Dict:
    """Redaction with batch size 1 over a target of several records: every Batch and Final takes the head lock."""
    reset(ledger=True)
    c = Conn(trlib.NS)
    try:
        e = engine(c)
        for i in range(4):
            ch = cs(f"tenant node {i}")
            ch.create_node(f"lkx|{i}", properties={"secret": f"v{i}"})
            e.ledger.commit(ch)
            c.conn.commit()
        c.call("Graph.KG.Eraser", "EraseNodes", "", "lkx|")
        c.conn.commit()
    finally:
        c.close()
    names = ['^IVG.Ledger("head")', '^IVG.Ledger("redacting")', "^IVG.AdjW", "^IVG.AdjW(0)"]
    res = {"plan_names": names, "workloads": {}, "probes": {}}

    def redact(x, deadline):
        out = str(x.call("Graph.KG.LedgerRedact", "Redact", "", "lkx", "|", "audit:locklog", 1, 0, "Graph_KG"))
        if out.startswith("CHUNKED:"):
            _, tag, n = out.split(":")
            out = "".join(str(x.call("Graph.KG.Ledger", "ReadLargeOutChunk", tag, i)) for i in range(1, int(n) + 1))
        while time.time() < deadline:
            time.sleep(0.05)
        return {"receipt": json.loads(out)}
    res["workloads"]["Redact batch=1"] = locklog.run_workload(names, 4, redact)
    return res


def m18() -> Dict:
    reset(ledger=True)
    arch = str(trlib.run_dir() / "locklog" / "tr18lk.zip")
    c = Conn(trlib.NS)
    try:
        e = engine(c)
        ch = cs("before the archive")
        ch.create_node("tr18lka")
        e.ledger.commit(ch)
        c.conn.commit()
        e.save_snapshot(arch)
    finally:
        c.close()
    names = ['^IVG.Ledger("head")', "^IVG.AdjW", "^IVG.AdjW(0)", "^NKG", "^IVG.NKGBuild"]
    res = {"plan_names": names, "workloads": {}, "probes": {}, "archive": arch}

    def restore(x, deadline):
        e = engine(x)
        return _loop(deadline, lambda n: e.restore_snapshot(arch, merge=False))
    res["workloads"]["restore_snapshot(merge=False)"] = locklog.run_workload(names, 6, restore)
    res["probes"]["restore_snapshot vs ^IVG.Ledger(head) held exclusively"] = locklog.block_probe(
        ["^IVG.Ledger", "head"], "", lambda x: engine(x).restore_snapshot(arch, merge=False), hold=6.0)
    return res


def _m13_setup():
    reset(ledger=True)
    c = Conn(trlib.NS)
    try:
        e = engine(c)
        for i in range(4):
            ch = cs(f"tenant node {i}")
            ch.create_node(f"lkf|{i}", properties={"secret": f"v{i}"})
            e.ledger.commit(ch)
            c.conn.commit()
        c.call("Graph.KG.Eraser", "EraseNodes", "", "lkf|")
        c.conn.commit()
    finally:
        c.close()


def _redact(x, batch):
    out = str(x.call("Graph.KG.LedgerRedact", "Redact", "", "lkf", "|", "audit:locklog", batch, 0, "Graph_KG"))
    if out.startswith("CHUNKED:"):
        _, tag, n = out.split(":")
        out = "".join(str(x.call("Graph.KG.Ledger", "ReadLargeOutChunk", tag, i)) for i in range(1, int(n) + 1))
    return json.loads(out)


def m13b() -> Dict:
    """Isolating Final's head lock (LedgerRedact.cls:390). (a) P holds ^IVG.Ledger("head") before the redaction starts:
    the redaction waits at Batch's lock (:282). (b) P spins in its own session until the redaction marker appears
    (set by the first Batch inside its transaction, LedgerRedact.cls BatchInLock) and then requests the head lock,
    queueing behind that Batch; with one Batch covering the whole ledger (batch 1000) the redaction's next lock
    request is Final's, which then waits behind P. The journal mark taken while P holds the lock splits the
    redaction's records into those written before the wait (the tombstones) and after it (the redaction revision)."""
    import subprocess
    import os
    res = {"plan_names": ['^IVG.Ledger("head")'], "workloads": {}, "probes": {}}
    _m13_setup()
    res["probes"]["Redact vs head held from the start (Batch, :282)"] = locklog.block_probe(
        ["^IVG.Ledger", "head"], "", lambda x: _redact(x, 1000), hold=3.0)
    _m13_setup()
    script = (' for { quit:$data(^IVG.Ledger("redacting")) } lock +^IVG.Ledger("head"):30 write !,"GOT|",$test,!'
              ' hang 4 lock -^IVG.Ledger("head") write !,"REL|",! halt\n')
    X, obs = Conn(trlib.NS), Conn(trlib.NS)
    out = {"pids": {"X": X.pid}}
    try:
        m0 = trlib.journal.mark()
        pp = subprocess.Popen(["docker", "exec", "-i", os.environ["IVG_TEST_CONTAINER"], "iris", "session", "IRIS", "-U",
                               trlib.NS], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        pp.stdin.write(script.encode())
        pp.stdin.close()
        pp.stdin = None
        time.sleep(0.5)
        import threading
        done = {}

        def work():
            t = time.time()
            try:
                done["receipt"] = _redact(X, 1000)
            except Exception as ex:  # noqa: BLE001
                done["error"] = f"{type(ex).__name__}: {str(ex)[:300]}"
            done["t"] = round(time.time() - t, 3)
        th = threading.Thread(target=work)
        t0 = time.time()
        th.start()
        samples = []
        while time.time() - t0 < 3.0:
            time.sleep(0.25)
            samples.append({"t": round(time.time() - t0, 2), **locklog.proc_state(obs, X.pid),
                            "x_locks": locklog.lock_rows(obs, X.pid), "head_rows": [r for r in locklog.lock_rows(obs)
                                                                                    if "Ledger" in r["ref"]]})
        m_rel = trlib.journal.mark()
        th.join(60)
        pout, _ = pp.communicate(timeout=60)
        out["p_output"] = pout.decode("utf-8", "replace")[-300:]
        out["x_while_p_holds"] = samples
        out["x"] = {k: (v if k != "receipt" else {kk: v.get(kk) for kk in ("ok", "complete", "batches", "records_tombstoned")})
                    for k, v in done.items()}
        recs = [r for r in trlib.journal.records_since(m0, dbs={trlib.DB}, pids={X.pid}) if r["g"]]
        before = [r for r in recs if r["a"] <= m_rel.address]
        after = [r for r in recs if r["a"] > m_rel.address]
        out["records_before_mark"] = len(before)
        out["records_after_mark"] = len(after)
        out["tombstones_before_mark"] = sum(1 for r in before if r["g"].startswith('^IVG.Ledger("rec"') and r["t"] == "SET")
        out["revision_rows_before_mark"] = sorted({r["g"] for r in before if r["g"].startswith("^Graph.KG.LedgerRevisionD(")})
        out["revision_rows_after_mark"] = sorted({r["g"] for r in after if r["g"].startswith("^Graph.KG.LedgerRevisionD(")})
        out["head_after_mark"] = [r["g"] for r in after if r["g"] == '^IVG.Ledger("head")']
        waited = [s for s in samples if s.get("state", "").startswith("LOCK")]
        out["waited"] = bool(waited)
        out["wait_at"] = sorted({s["at"] for s in waited})
    finally:
        X.close()
        obs.close()
    res["probes"]["Redact vs head taken after the first Batch (Final, :390)"] = out
    return res


def m01() -> Dict:
    """initialize_schema() once on the lane's namespace (the pin's own deploy path, which deployed AUDITE) while the
    lock table is polled; a little content first so the setup's ^KG bootstrap and rebuild have rows to read."""
    reset()
    c = Conn(trlib.NS)
    try:
        e = engine(c)
        for i in range(10):
            e.create_edge(f"i{i}", "R", f"i{(i + 1) % 10}")
    finally:
        c.close()
    names = ["^IVG.AdjW", "^IVG.AdjW(0)", "^IVG.NKGBuild", "^NKG", '^IVG.Ledger("head")']
    res = {"plan_names": names, "workloads": {}, "probes": {}}

    def setup_once(x, deadline):
        t = time.time()
        info = engine(x).initialize_schema()
        return {"iterations": 1, "seconds": round(time.time() - t, 1),
                "reply": {k: (v if k != "objectscript_skipped" else sorted(v)) for k, v in dict(info).items()}
                if isinstance(info, dict) else str(info)[:300]}
    res["workloads"]["initialize_schema"] = locklog.run_workload(names, 90, setup_once)
    return res


def m09() -> Dict:
    """Compiled-plan build lock ^IVG.CypherCompiled(h) X:0 (Gen.cls:166-167), in AUDITC (TR_NAMESPACE=AUDITC; the
    orchestrator's scope decision: the executor compiling its own plan classes at run time is the product's normal
    operation). Each workload iteration runs Gen.DropAll (what a deploy runs) and a native read of one shape, so the
    shape is built again: in sync mode by the reader, in job mode by a background job."""
    import m09 as M
    reset()
    before = M._data(["T9L"])
    c = Conn(trlib.NS)
    try:
        c.call("Graph.KG.Cypher.Gen", "Mode", "sync")
        engine(c).execute_cypher(M.q_of("T9L"))
        h = [k for k, v in M.entries(c).items() if v[2] == "ok"][0]
        compiled_once = M.ivgc(c)
        c.call("Graph.KG.Cypher.Gen", "DropAll")
    finally:
        c.close()
    names = [f"^IVG.CypherCompiled({h})", "^IVG.CypherCompiled", '^IVG.Ledger("head")', "^IVG.AdjW"]
    res = {"plan_names": names, "workloads": {}, "probes": {}, "hash": h, "classes_before": before,
           "compiled_in_setup": compiled_once}

    def builds(mode):
        def work(x, deadline):
            e = engine(x)
            done, oks = 0, 0
            while time.time() < deadline:
                x.call("Graph.KG.Cypher.Gen", "DropAll")
                x.call("Graph.KG.Cypher.Gen", "Mode", mode)
                e.execute_cypher(M.q_of("T9L"))
                t0 = time.time()
                while time.time() - t0 < 60:
                    st = M.entries(x).get(h, (None, None, None))[2]
                    if st != "pending":
                        break
                    time.sleep(0.02)
                oks += int(st == "ok")
                done += 1
            return {"iterations": done, "builds_ok": oks, "classes_now": M.ivgc(x)}
        return work
    for mode in ("sync", "job"):
        w = locklog.run_workload(names, 8, builds(mode))
        others = sorted({(e["name"], e["mode"], e["owner"]) for e in w["log"]["events"]
                         if e["mode"] and e["owner"] and e["owner"] != w["pid"]})
        w["held_by_other_processes"] = [list(x) for x in others]
        res["workloads"][f"DropAll + read ({mode})"] = w

    def blocked_read(x):
        x.call("Graph.KG.Cypher.Gen", "DropAll")
        x.call("Graph.KG.Cypher.Gen", "Mode", "sync")
        r = engine(x).execute_cypher(M.q_of("T9L"))
        return {"rows": [list(y) for y in (r.rows or [])], "status": M.entries(x).get(h, (None, None, None))[2],
                "classes": len(M.ivgc(x))}
    res["probes"]["sync read vs ^IVG.CypherCompiled(h) held exclusively"] = locklog.block_probe(
        ["^IVG.CypherCompiled", h], "", blocked_read, hold=4.0)
    c = Conn(trlib.NS)
    try:
        c.call("Graph.KG.Cypher.Gen", "DropAll")
        c.call("Graph.KG.Cypher.Gen", "Mode", "")
        res["classes_after_dropall"] = M.ivgc(c)
    finally:
        c.close()
    return res


RUNS = {"09": m09, "01": m01, "13b": m13b, "02": m02, "03": m03, "04": m04, "05": m05, "06": m06, "08": m08, "10": m10, "13": m13, "18": m18}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for nn in sys.argv[1:]:
        t = time.time()
        print(f"# lock log {nn}", flush=True)
        res = RUNS[nn]()
        res["seconds"] = round(time.time() - t, 1)
        (OUT / f"{nn}.json").write_text(json.dumps(res, indent=1, default=str))
        for k, w in res["workloads"].items():
            print(f"  workload {k}: {w['work'] if 'receipt' not in str(w['work']) else 'redaction'} -> {w['summary']}")
        for k, p in res["probes"].items():
            if "held_while_waiting" not in p:
                print(f"  probe {k}: " + json.dumps({kk: v for kk, v in p.items() if kk != "x_while_p_holds"})[:900])
                continue
            print(f"  probe {k}: waited={p['waited']} at={p['wait_at']} held_while_waiting={p['held_while_waiting']} "
                  f"x={p['x']} finished_while_held={p['x_finished_while_held']} "
                  f"records_before_release={len(p['x_records_before_release'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
