#!/usr/bin/env python3
"""Trace scenarios of the correspondence lane, run on the pin in namespace AUDITC (one IRIS process per operation).

    python scenarios.py OUT_DIR SCENARIO [--monitor]

SCENARIO:
  conf      the exact scenario of traces/conformance.py (its run() with NS/DB patched to AUDITC)
  ext       an extended scenario reaching the handlers conf does not: every changeset op kind, replay and the refusal
            paths of commit, genesis over pre-enable rows, strict/disable/enable, a ledger-bypassing write and its
            adoption, EraseEdges, EraseGraph, a graph-target redaction, refusals of redact (target_live, another
            marker), a bounded run, a commit refused by BlocksCommit, readers and verify while marked, the resumed run,
            verify, EraseAll
  f1201     F-1201 (traces/f1201_native.py's 'other' world, two trials) recorded as conformance traces
  lostack   the lost-acknowledgement world (traces/lost_ack.py, three kill delays) recorded as a conformance trace

Each scenario writes OUT_DIR/<scenario>[-<n>]/trace.json in conformance.py's format (before/final ledger snapshots,
ops with their server pids, journal records of AUDITC since a mark, storage map) plus per-operation row snapshots
(`rows_before`/`rows_after`) for the abstraction check (abstraction.py). With --monitor the IRIS line-by-line monitor
runs around each scenario (monitor.py) and its counts are saved next to the trace.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (NS, DB, Conn, conformance, dump, engine, journal, reset, rows, version)  # noqa: E402
import monitor  # noqa: E402

from iris_vector_graph.ledger import Changeset  # noqa: E402

SEP = "|"

# Python line coverage of the product's ledger/erasure client code (stdlib tracer; no coverage package here): only
# frames of these files are traced, and the set restarts at the journal mark like the IRIS line monitor.
_REPO = str(Path(__file__).resolve().parents[4])
PY_TARGETS = tuple(f"{_REPO}/iris_vector_graph/{x}" for x in ("ledger/", "_write_txn.py", "_engine/nodes_edges.py",
                                                               "_engine/ledger.py", "stores/iris_sql_store.py"))
PYCOV: dict = {}


def _pylocal(frame, event, arg):
    if event == "line":
        PYCOV.setdefault(frame.f_code.co_filename, set()).add(frame.f_lineno)
    return _pylocal


def _pyglobal(frame, event, arg):
    if event == "call" and frame.f_code.co_filename.startswith(PY_TARGETS):
        PYCOV.setdefault(frame.f_code.co_filename, set()).add(frame.f_lineno)
        return _pylocal
    return None


class Recorder:
    """Runs operations one per IRIS process and keeps conformance.py's trace layout."""

    def __init__(self, out: Path, enable: bool = True, pre=None):
        self.out = out
        ctl = Conn(NS)
        reset(ctl)
        if pre:
            pre(ctl)
        self.smap = journal.storage_map(ctl)
        self.before0 = conformance.snapshot(ctl)
        self.rows0 = rows(ctl)
        ctl.close()
        self.m = journal.mark()
        self.ops = []

    def op(self, name: str, fn, expect: str = "ok", **info):
        ctl = Conn(NS)
        rb = rows(ctl)
        ctl.close()
        c = Conn(NS)
        t = time.time()
        try:
            res, ok = fn(c), True
        except Exception as ex:  # noqa: BLE001
            res, ok = f"{type(ex).__name__}: {str(ex)[:400]}", False
        rec = {"op": name, "pid": c.pid, "ok": ok, "expect": expect, "label": info.pop("label", name),
               "result": res if isinstance(res, (str, int, float, dict, list, type(None))) else str(res),
               "seconds": round(time.time() - t, 3), **info}
        c.close()
        ctl = Conn(NS)
        rec["rows_before"], rec["rows_after"] = rb, rows(ctl)
        ctl.close()
        self.ops.append(rec)
        print(json.dumps({"op": name, "label": rec["label"], "ok": ok, "expect": expect,
                          "result": str(rec["result"])[:160]}), flush=True)
        return rec

    def finish(self, extra=None):
        ctl = Conn(NS)
        final = conformance.snapshot(ctl)
        rows_final = rows(ctl)
        ctl.close()
        recs = journal.records_since(self.m, dbs={DB})
        trace = {"namespace": NS, "before": [[list(k), v] for k, v in self.before0.items()],
                 "final": [[list(k), v] for k, v in final.items()], "ops": self.ops, "journal": recs,
                 "smap": self.smap, "rows0": self.rows0, "rows_final": rows_final, **(extra or {})}
        dump(self.out / "trace.json", trace)
        return trace


def cs(msg, key=None, **kw):
    return Changeset(actor="audit:corr", actor_type="ingest", message=msg, idempotency_key=key, source={"feed": msg},
                     **kw)


def commit_fn(changeset, kind="changeset"):
    def f(c):
        r = engine(c).ledger.commit(changeset, kind=kind)
        c.conn.commit()
        return {"seq": r.revision.seq, "replayed": bool(r.replayed), "stmt_ids": r.stmt_ids}
    return f


def redact_fn(graph, prefix, batch=2, max_batches=0):
    def f(c):
        o = str(c.call("Graph.KG.LedgerRedact", "Redact", graph, prefix, SEP, "audit:corr", batch, max_batches,
                       "Graph_KG"))
        if o.startswith("CHUNKED:"):
            _, tag, n = o.split(":")
            o = "".join(str(c.call("Graph.KG.Ledger", "ReadLargeOutChunk", tag, i)) for i in range(1, int(n) + 1))
        return json.loads(o)
    return f


def digest(graph, match):
    c = Conn(NS)
    try:
        return str(c.call("Graph.KG.LedgerRedact", "TargetDigest", graph, match))
    finally:
        c.close()


def py_redact(graph, prefix, batch=2, max_batches=0):
    """ledger.redact (client.py:633-680), the public entry point over LedgerRedact.Redact."""
    def f(c):
        r = engine(c).ledger.redact(graph or None, prefix or None, batch_size=batch, max_batches=max_batches,
                                    actor="audit:corr")
        return {"complete": bool(r.complete), "records_tombstoned": getattr(r, "records_tombstoned", None)}
    return f


# ------------------------------------------------------------------------------------------------ ext

def scenario_ext(out: Path) -> dict:
    def pre(ctl):
        e = engine(ctl)
        e.create_node("pre|1", labels=["Old"], properties={"k": "v"})
        e.create_node("pre|2")
        e.create_edge("pre|1", "R", "pre|2", qualifiers={"q": "1"})
        ctl.conn.commit()

    R = Recorder(out, pre=pre)
    R.op("commit", lambda c: engine(c).ledger.enable().seq, label="enable-genesis")
    a = cs("A", "kA")
    a.create_node("x|1", labels=["P"], properties={"name": "n1"})
    a.create_node("x|2", labels=["P"])
    a.create_relationship("x|1", "R", "x|2", qualifiers={"w": "1"})
    a.create_relationship("x|1", "S", "x|2", graph="G")
    a.create_relationship("x|2", "S", "x|1", graph="G")
    R.op("commit", commit_fn(a), label="commit-create")
    b = cs("B", "kB")
    b.set_property("x|1", "name", "n1b")
    b.add_label("x|2", "Q")
    b.set_qualifier(("x|1", "R", "x|2"), "w", "2")
    b.replace_qualifiers(("x|1", "S", "x|2", "G"), qualifiers={"z": "9"})
    b.upsert_node("x|1", properties={"extra": "e"})
    b.upsert_relationship("x|1", "R", "x|2", qualifiers={"w": "3", "v": "a"})
    R.op("commit", commit_fn(b), label="commit-update")
    b2 = cs("B", "kB")
    for op in b.ops:
        b2.ops.append(dict(op))
    R.op("commit", commit_fn(b2), label="commit-replay")
    b3 = cs("B'", "kB")
    b3.add_label("x|1", "Z")
    R.op("commit", commit_fn(b3), expect="IdempotencyConflictError", label="commit-idem-conflict")

    def stale(c):
        ch = cs("stale")
        ch.add_label("x|1", "Z")
        ch.expected_head = str(json.loads(str(c.call("Graph.KG.Ledger", "Head")))["revision"]["parent_id"])
        return commit_fn(ch)(c)
    R.op("commit", stale, expect="StaleHeadError", label="commit-stale-head")
    unk = cs("unknown head")
    unk.add_label("x|1", "Z")
    unk.expected_head = "0" * 32
    R.op("commit", commit_fn(unk), expect="UnknownRevisionError", label="commit-unknown-head")
    bad = cs("failing op")
    bad.create_node("x|3")
    bad.add_label("nope|1", "L")
    R.op("commit", commit_fn(bad), expect="NodeNotFoundError", label="commit-failed-op")
    cc = cs("C", "kC")
    cc.remove_label("x|2", "Q")
    cc.remove_property("x|1", "extra")
    cc.remove_qualifier(("x|1", "R", "x|2"), key="v")
    cc.delete_relationship(("x|1", "S", "x|2", "G"))
    cc.create_node("x|3")
    r3 = cc.create_relationship("x|3", "R", "x|1")
    cc.set_qualifier(r3, "w", "5")
    cc.delete_node("x|3", mode="detach")
    R.op("commit", commit_fn(cc), label="commit-delete")
    pc = cs("with a post-commit property")
    pc.add_label("x|2", "PC")
    pc.post_commit_properties = {"x|2": {"pc": "v"}}
    R.op("commit", commit_fn(pc), pcp={"x|2": {"pc": "v"}}, label="commit-post-commit-property")
    t = cs("temporal")
    t.create_temporal_edge("x|1", "T", "x|2", ts=1700000000, weight=2.0)
    R.op("commit", commit_fn(t), expect="any", label="commit-temporal")
    R.op("setenabled", lambda c: engine(c).ledger.set_strict(True), label="strict-on")
    R.op("setenabled", lambda c: engine(c).ledger.set_strict(False), label="strict-off")
    R.op("setenabled", lambda c: engine(c).ledger.disable(), label="disable")
    d = cs("while disabled")
    d.add_label("x|1", "Z")
    R.op("commit", commit_fn(d), expect="LedgerDisabledError", label="commit-disabled")

    def bypass(c):
        e = engine(c)
        e.create_node("y|1", labels=["Y"])
        e.create_edge("y|1", "R", "x|1")
        c.conn.commit()
        return "ok"
    R.op("bypass", bypass, label="bypass-write")
    R.op("setenabled", lambda c: json.loads(str(c.call("Graph.KG.Ledger", "Enable", 0, 50000, 250000, "Graph_KG"))),
         label="reenable")

    def adopt(c):
        rep = engine(c).ledger.verify(adopt=True)
        c.conn.commit()
        return {"result": rep.result, "adoption": getattr(rep.adoption_revision, "seq", None)}
    R.op("commit", adopt, label="verify-adopt")
    ee = [{"s": "x|2", "p": "S", "o": "x|1"}]
    R.op("erase", lambda c: int(c.call("Graph.KG.Eraser", "EraseEdges", "G", json.dumps(ee))),
         target=("G", None), edges=ee, label="erase-edges")
    R.op("erase", lambda c: int(engine(c).erase_graph("G")), target=("G", None), label="erase-graph")
    dg = digest("G", "")
    R.op("redact", py_redact("G", "", 2, 0), target=("G", ""), digest=dg, label="redact-graph")
    dx = digest("", "x|")
    R.op("redact", py_redact("", "x", 2, 0), target=("", "x|"), digest=dx, expect="RedactionTargetLiveError", label="redact-live")
    R.op("erase", lambda c: int(engine(c).delete_nodes_by_prefix("x|")), target=("", "x|"), label="erase-nodes")
    R.op("redact", py_redact("", "x", 1, 1), target=("", "x|"), digest=dx, label="redact-bounded")
    blk = cs("into the marked target")
    blk.create_node("x|9")
    R.op("commit", commit_fn(blk), expect="RedactionInProgressError", label="commit-blocked")

    def readers(c):
        led = engine(c).ledger
        outv = {}
        for name, fn in (("get_revision", lambda: led.get_revision(led.head().revision_id)),
                         ("reconstruct", lambda: led.reconstruct(led.head().revision_id)),
                         ("diff", lambda: led.diff(led.head().revision_id, led.head().revision_id)),
                         ("history", lambda: len(led.history().revisions))):
            try:
                fn()
                outv[name] = "answered"
            except Exception as ex:  # noqa: BLE001
                outv[name] = type(ex).__name__
        return outv
    R.op("read", readers, label="readers-marked")
    R.op("verify", lambda c: engine(c).ledger.verify().result, label="verify-marked")
    dy = digest("", "y|")
    R.op("redact", py_redact("", "y", 2, 0), target=("", "y|"), digest=dy, expect="RedactionInProgressError",
         label="redact-other-marker")
    R.op("redact", py_redact("", "x", 2, 0), target=("", "x|"), digest=dx, label="redact-resume")
    R.op("read", readers, label="readers-after")
    R.op("verify", lambda c: engine(c).ledger.verify().result, label="verify-after")
    R.op("erase", lambda c: int(engine(c).erase_all()), target=("*", None), label="erase-all")
    return R.finish()


# ------------------------------------------------------------------------------------------------ f1201

def scenario_f1201(out: Path, release_after: float) -> dict:
    G = "G"

    def pre(ctl):
        eng = engine(ctl)
        eng.ledger.enable()
        for chunk in range(4):
            bulk = Changeset(actor="audit:f1201", actor_type="ingest", auto_stub_missing_nodes=True)
            for k in range(1000):
                bulk.create_relationship(f"h{chunk}_{k}", "R", f"h{chunk}_{k + 1}", graph="H")
            eng.ledger.commit(bulk)
            ctl.conn.commit()

    R = Recorder(out, pre=pre)
    q, e, p = Conn(NS), Conn(NS), Conn(NS)
    q.o.lock("", 0, "^IVG.AdjW", G)
    t0 = time.time()
    er, cr = {}, {}

    def erase():
        try:
            er["removed"] = int(e.call("Graph.KG.Eraser", "EraseGraph", G))
        except Exception as ex:  # noqa: BLE001
            er["error"] = str(ex)[:300]
        er["t"] = time.time() - t0

    def commit():
        try:
            ch = Changeset(actor="audit:f1201", actor_type="ingest", auto_stub_missing_nodes=True)
            ch.create_relationship("u", "R", "v", graph=G)
            r = engine(p).ledger.commit(ch)
            p.conn.commit()
            cr["seq"] = r.revision.seq
        except Exception as ex:  # noqa: BLE001
            cr["error"] = str(ex)[:300]
        cr["t"] = time.time() - t0
    te = threading.Thread(target=erase)
    te.start()
    time.sleep(0.8)
    tc = threading.Thread(target=commit)
    tc.start()
    time.sleep(release_after)
    q.o.releaseAllLocks()
    te.join(60)
    tc.join(60)
    R.ops = [{"op": "erase", "pid": e.pid, "ok": "removed" in er, "result": er, "target": (G, None), "label": "erase-graph"},
             {"op": "commit", "pid": p.pid, "ok": "seq" in cr, "result": cr, "label": "commit-into-G"},
             {"op": "probe", "pid": q.pid, "ok": True, "result": "held ^IVG.AdjW(G) exclusively", "label": "probe"}]
    for x in (q, e, p):
        x.close()
    return R.finish({"release_after_s": release_after})


# ------------------------------------------------------------------------------------------------ lost-ack

CLIENT = r'''
import sys, json
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
from iris_conn import Conn
from iris_vector_graph.engine import IRISGraphEngine
from iris_vector_graph.ledger import Changeset
key, n, tag, ns = sys.argv[3], int(sys.argv[4]), sys.argv[5], sys.argv[6]
c = Conn(ns)
print(json.dumps({"pid": c.pid}), flush=True)
cs = Changeset(actor="audit:lostack", actor_type="ingest", idempotency_key=key, auto_stub_missing_nodes=True)
for i in range(n):
    cs.create_relationship(f"{tag}a{i}", "R", f"{tag}b{i}", graph="LA")
r = IRISGraphEngine(c.conn, namespace=ns, embedding_dimension=4).ledger.commit(cs)
c.conn.commit()
print(json.dumps({"seq": r.revision.seq, "replayed": bool(getattr(r, "replayed", False))}), flush=True)
'''


def scenario_lostack(out: Path, delays=(0.3, 0.8, 3.0), n=1500) -> dict:
    from common import PC
    R = Recorder(out, pre=lambda c: (engine(c).ledger.enable(), c.conn.commit()))
    ctl = Conn(NS)
    worlds = []

    def client(key, tag):
        return subprocess.Popen([sys.executable, "-c", CLIENT, str(PC / "tools"), str(PC.parents[1]), key, str(n), tag, NS],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for i, delay in enumerate(delays):
        key, tag = f"corr-lostack-{i}", f"t{i}_"
        pr = client(key, tag)
        first = json.loads(pr.stdout.readline() or "{}")
        time.sleep(delay)
        killed = pr.poll() is None
        if killed:
            os.kill(pr.pid, signal.SIGKILL)
        pr.wait(30)
        srv = first.get("pid")
        end = time.time() + 60
        while srv and time.time() < end and int(ctl.call("%SYS.ProcessQuery", "%ExistsId", srv) or 0):
            time.sleep(0.2)
        R.ops.append({"op": "commit", "pid": str(srv), "ok": not killed, "label": f"first-attempt-{delay}s",
                      "result": {"killed": killed}})
        r2 = client(key, tag)
        f2 = json.loads(r2.stdout.readline() or "{}")
        o2, e2 = r2.communicate(timeout=300)
        res2 = [json.loads(x) for x in o2.splitlines() if x.startswith("{")]
        R.ops.append({"op": "commit", "pid": str(f2.get("pid")), "ok": bool(res2), "label": f"retry-{delay}s",
                      "result": res2[-1] if res2 else e2[-300:]})
        worlds.append({"delay": delay, "killed": killed, "retry": res2[-1] if res2 else None})
        print(json.dumps(worlds[-1]), flush=True)
    ctl.close()
    v = R.op("verify", lambda c: engine(c).ledger.verify().result, label="verify-after-worlds")
    return R.finish({"worlds": worlds, "verify": str(v["result"])})


def main() -> int:
    out = Path(sys.argv[1])
    which = sys.argv[2]
    mon = "--monitor" in sys.argv
    c = Conn(NS)
    print("engine:", version(c), "namespace:", NS, flush=True)
    c.close()
    runs = {"conf": [("conf", lambda d: conformance.run(d, 1))],
            "ext": [("ext", scenario_ext)],
            "f1201": [("f1201-1", lambda d: scenario_f1201(d, 0.5)), ("f1201-2", lambda d: scenario_f1201(d, 1.5))],
            "lostack": [("lostack", scenario_lostack)]}[which]
    for name, fn in runs:
        d = out / name
        d.mkdir(parents=True, exist_ok=True)
        on = False
        if mon:
            try:
                monitor.start(d)
                on = True
                # the counters restart at the journal mark: setup before it (reset, seeding) is not counted
                orig_mark = journal.mark

                def mark_and_clear(_orig=orig_mark):
                    m = _orig()
                    monitor.clear()
                    PYCOV.clear()
                    return m
                journal.mark = mark_and_clear
                PYCOV.clear()
                sys.settrace(_pyglobal)
                threading.settrace(_pyglobal)
            except Exception as ex:  # noqa: BLE001
                (d / "monitor-unavailable.log").write_text(repr(ex))
                print("line monitor unavailable:", repr(ex)[:300], flush=True)
        try:
            fn(d)
        finally:
            if on:
                journal.mark = orig_mark
                sys.settrace(None)
                threading.settrace(None)
                (d / "pycov.json").write_text(json.dumps({f[len(_REPO) + 1:]: sorted(v) for f, v in PYCOV.items()}))
                try:
                    monitor.collect(d)
                finally:
                    monitor.stop(d)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
