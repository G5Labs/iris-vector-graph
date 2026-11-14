#!/usr/bin/env python3
"""One simulator worker: an OS process with its own IRIS connection that runs a list of public IVG operations.

    python worker.py PLAN_JSON WIDX          # prints one JSON line per event on stdout

Each operation attempt is bracketed by two scratch-global SETs, ^IVGAuditSim(widx, i, attempt, "b"|"e") = server pid,
made outside any transaction. The IRIS journal records them in this process's stream, so every journaled write of
the process between the two markers belongs to that attempt (the oracle's attribution; nothing is compiled, the
scratch global is removed by the driver). When the IRIS server process is terminated mid-operation (the driver's
%SYSTEM.Process.Terminate), the worker reconnects and, for a commit with an idempotency key or a redaction, retries
the same operation once (a lost acknowledgement / a resumed redaction).

Only the pin's public Python API is used: IRISGraphEngine, engine.ledger.{commit, redact, verify, head, reconstruct},
engine.{create_node, create_edge, delete_edge, delete_nodes_by_prefix, erase_graph}. The probe role holds product
lock names from the Native API (as traces/f1201_native.py does).
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
import logging  # noqa: E402

logging.disable(logging.CRITICAL)
from iris_conn import Conn  # noqa: E402

from iris_vector_graph.engine import IRISGraphEngine  # noqa: E402
from iris_vector_graph.ledger import Changeset  # noqa: E402

NS = "AUDITA"
OUT = sys.stdout


def emit(**kw) -> None:
    kw["wall"] = round(time.time(), 4)
    OUT.write(json.dumps(kw, default=str) + "\n")
    OUT.flush()


def connect(retries: int = 40):
    last = None
    for _ in range(retries):
        try:
            return Conn(NS)
        except Exception as ex:  # noqa: BLE001 - license slot of a killed process may lag
            last = ex
            time.sleep(0.5)
    raise RuntimeError(f"cannot reconnect: {last}")


def changeset(spec: dict) -> Changeset:
    cs = Changeset(actor=spec["actor"], actor_type="ingest", message=spec.get("message"), source=spec.get("source"),
                   correlation_id=spec.get("correlation_id"), idempotency_key=spec.get("key"),
                   post_commit_properties=spec.get("pcp") or {})
    cs.ops = [dict(o) for o in spec["ops"]]
    return cs


def comparable(state) -> dict:
    """reconstruct()'s GraphState as plain JSON (nodes with labels/props; statements by id)."""
    return {"nodes": {nid: [sorted(n.labels), dict(sorted(n.props.items()))] for nid, n in state.nodes.items()},
            "rels": {sid: [st.s, st.p, st.o, st.graph, dict(sorted(st.quals.items()))]
                     for sid, st in state.statements.items()}}


def run_op(c: Conn, eng: IRISGraphEngine, op: dict) -> dict:
    k = op["kind"]
    if k == "commit":
        cs = changeset(op["cs"])
        out = {"fingerprint": cs.fingerprint(), "key": cs.idempotency_key}
        r = eng.ledger.commit(cs)
        c.conn.commit()
        out.update(seq=r.revision.seq, replayed=bool(r.replayed), pcp_applied=bool(r.post_commit_applied),
                   pcp_error=r.post_commit_error)
        return out
    if k == "direct":
        a = op["args"]
        if op["fn"] == "create_node":
            v = eng.create_node(a["id"], labels=a.get("labels"), properties=a.get("props"), graph=a.get("graph"))
        elif op["fn"] == "create_edge":
            v = eng.create_edge(a["s"], a["p"], a["o"], qualifiers=a.get("quals"), graph=a.get("graph"))
        elif op["fn"] == "delete_edge":
            v = eng.delete_edge(a["s"], a["p"], a["o"], graph=a.get("graph"))
        else:
            raise ValueError(op["fn"])
        c.conn.commit()
        return {"value": v}
    if k == "erase":
        if op.get("graph_erase"):
            v = eng.erase_graph(op["graph_erase"])
            c.conn.commit()
            return {"erase_graph": v}
        v = eng.delete_nodes_by_prefix(op["prefix"], graph=op.get("graph"))
        c.conn.commit()
        return {"erase_nodes": v}
    if k == "redact":
        r = eng.ledger.redact(op.get("graph"), op.get("prefix"), actor="audit:sim", batch_size=op["batch"],
                              max_batches=op["max_batches"])
        return {"complete": bool(r.complete), "target_sha256": r.target_sha256,
                "records_tombstoned": r.records_tombstoned, "revision_seqs": list(r.revision_seqs),
                "batches": r.batches, "statements_removed": r.statements_removed,
                "redaction_seq": getattr(r.redaction, "seq", None) if r.redaction else None}
    if k == "verify":
        rep = eng.ledger.verify()
        return {"result": rep.result, "seq": rep.verified_seq, "n_diff": len(rep.differences),
                "diff": [str(d)[:160] for d in rep.differences[:6]]}
    if k == "reconstruct":
        h = eng.ledger.head()
        st = eng.ledger.reconstruct(h.revision_id)
        return {"seq": h.seq, "state": comparable(st)}
    if k == "hold":
        subs = op["subs"]
        ok = c.o.lock("", 2, op["global"], *subs)
        time.sleep(op["seconds"])
        c.o.releaseAllLocks()
        return {"held": bool(ok)}
    raise ValueError(k)


RETRY_AFTER_KILL = {"commit", "redact", "erase"}


def main() -> int:
    plan = json.loads(Path(sys.argv[1]).read_text())
    widx = int(sys.argv[2])
    me = plan["workers"][str(widx)]
    c = connect()
    eng = IRISGraphEngine(c.conn, namespace=NS, embedding_dimension=4)
    emit(ev="hello", w=widx, pid=c.pid)
    for i, op in enumerate(me["ops"]):
        time.sleep(op.get("think", 0.0))
        attempt = 0
        while True:
            pid = c.pid
            rec = {"ev": "op", "w": widx, "i": i, "attempt": attempt, "kind": op["kind"], "pid": pid}
            try:
                c.o.set(pid, "^IVGAuditSim", widx, i, attempt, "b")
            except Exception as ex:  # noqa: BLE001 - the server process was terminated between operations
                emit(ev="dead-before-op", w=widx, i=i, attempt=attempt, pid=pid, msg=str(ex)[:160])
                c.close()
                c = connect()
                eng = IRISGraphEngine(c.conn, namespace=NS, embedding_dimension=4)
                emit(ev="reconnect", w=widx, pid=c.pid)
                attempt += 1
                if attempt > 3:
                    break
                continue
            emit(ev="begin", w=widx, i=i, attempt=attempt, kind=op["kind"], pid=pid)
            t0 = time.time()
            killed = False
            try:
                res = run_op(c, eng, op)
                rec.update(ok=True, res=res)
            except Exception as ex:  # noqa: BLE001 - every refusal and failure is an observation
                rec.update(ok=False, err=type(ex).__name__, msg=str(ex)[:400])
                if op["kind"] == "commit":
                    try:
                        rec["fingerprint"] = changeset(op["cs"]).fingerprint()
                    except Exception:  # noqa: BLE001
                        pass
                try:
                    c.conn.rollback()
                except Exception:  # noqa: BLE001
                    pass
            rec["t0"], rec["t1"] = round(t0, 4), round(time.time(), 4)
            try:
                c.o.set(pid, "^IVGAuditSim", widx, i, attempt, "e")
            except Exception:  # noqa: BLE001 - the server process is gone
                killed = True
            rec["killed"] = killed
            emit(**rec)
            if not killed:
                break
            c.close()
            c = connect()
            eng = IRISGraphEngine(c.conn, namespace=NS, embedding_dimension=4)
            emit(ev="reconnect", w=widx, pid=c.pid)
            if op["kind"] not in RETRY_AFTER_KILL or attempt >= 1:
                break
            attempt += 1
    emit(ev="done", w=widx)
    c.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:  # noqa: BLE001
        emit(ev="crash", tb=traceback.format_exc()[-1500:])
        raise SystemExit(3)
