"""Shared helpers of the lockplans lane (namespace AUDITD only, observation only).

Every script runs under `bash experiment/playbook-completion/tools/locks.sh iris python ...`, opens at most 4
identity-checked connections (tools/iris_conn.Conn), starts from `reset()` (the product's own Graph.KG.Eraser.EraseAll
and Graph.KG.Ledger.PurgeAll) and compiles nothing. Probe observations follow correspondence/tools/lockplan.py:
%SYS.ProcessQuery (State, CurrentLineAndRoutine, InTransaction) of the waiting process and %SYS.LockQuery_List().
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PC = HERE.parents[1]                       # experiment/playbook-completion
REPO = PC.parents[1]
for p in (PC / "tools", PC / "traces", REPO):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from iris_conn import Conn, version  # noqa: E402,F401

NS = "AUDITD"
DB = "/usr/irissys/mgr/auditd/"
RUN_DIR = Path(os.environ["RUN_DIR"])
OUT = RUN_DIR / "lockplans"


def conn() -> Conn:
    c = Conn(NS)
    if c.namespace != NS:
        raise RuntimeError("wrong namespace")
    return c


def engine(c: Conn, **kw):
    from iris_vector_graph.engine import IRISGraphEngine
    kw.setdefault("embedding_dimension", 4)
    return IRISGraphEngine(c.conn, namespace=NS, **kw)


def store(c: Conn):
    from iris_vector_graph.stores.iris_sql_store import IRISGraphStore
    return IRISGraphStore(c.conn, namespace=NS)


def reset(c: Conn) -> None:
    with contextlib.suppress(Exception):
        c.conn.rollback()
    c.call("Graph.KG.Eraser", "EraseAll")
    c.call("Graph.KG.Ledger", "PurgeAll")
    c.conn.commit()


def tlevel(c: Conn) -> int:
    return int(c.sql("SELECT $TLEVEL")[0][0])


def proc_state(obs: Conn, pid: str) -> dict:
    try:
        r = obs.sql("SELECT State, CurrentLineAndRoutine, InTransaction FROM %SYS.ProcessQuery WHERE Pid = ?", pid)
        return {"state": str(r[0][0]), "at": str(r[0][1]), "in_txn": str(r[0][2])} if r else {}
    except Exception as ex:  # noqa: BLE001
        return {"error": str(ex)[:200]}


def lock_table(obs: Conn, pids=None, needle: str | None = None) -> list:
    """Rows of %SYS.LockQuery_List(): those owned by `pids`, or naming `needle` in the reference."""
    out = []
    for r in obs.sql("SELECT * FROM %SYS.LockQuery_List()"):
        r = [None if v is None else str(v) for v in r]
        ref = " ".join(v or "" for v in r[6:8])
        if (pids and r[1] in pids) or (needle and needle in ref):
            out.append({"owner": r[1], "mode": r[2], "flags": r[3], "counts": r[4], "ref": r[6], "full": r[7]})
    return out


def call(f):
    t = time.time()
    try:
        v = f()
        err = getattr(v, "error", None)
        if isinstance(err, str) and err:
            return {"ok": False, "error": "IVGResult.error: " + err[:400], "t": round(time.time() - t, 3)}
        return {"ok": True, "answer": str(getattr(v, "rows", v))[:300], "t": round(time.time() - t, 3)}
    except Exception as ex:  # noqa: BLE001
        return {"ok": False, "error": f"{type(ex).__name__}: {str(ex)[:400]}", "t": round(time.time() - t, 3)}


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, default=str))
