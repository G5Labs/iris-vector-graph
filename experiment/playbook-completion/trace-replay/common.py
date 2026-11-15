"""Shared helpers for the trace-replay scenarios (namespace AUDITE only)."""
from __future__ import annotations

import os
from typing import Any

import trlib  # noqa: F401  (sets sys.path)
from iris_conn import Conn  # noqa: E402

NS = trlib.NS


def engine(c: Conn, **kw):
    from iris_vector_graph.engine import IRISGraphEngine
    kw.setdefault("embedding_dimension", 4)
    return IRISGraphEngine(c.conn, namespace=NS, **kw)


def from_connect(**kw):
    from iris_vector_graph.engine import IRISGraphEngine
    kw.setdefault("embedding_dimension", 4)
    return IRISGraphEngine.from_connect("127.0.0.1", port=int(os.environ["IVG_PORT"]), namespace=NS,
                                        username="_SYSTEM", password="SYS", **kw)


def pid_of_dbapi(conn) -> str:
    import iris
    return str(iris.createIRIS(conn).classMethodValue("%SYSTEM.SYS", "ProcessID"))


def reset(ledger: bool = False, strict: bool = False) -> None:
    """Empty the lane's namespace content through the product's own erase paths (outside every capture)."""
    c = Conn(NS)
    try:
        try:
            engine(c).ledger.disable()
        except Exception:  # noqa: BLE001
            pass
        c.conn.commit()
        c.call("Graph.KG.Eraser", "EraseAll")
        c.call("Graph.KG.Ledger", "PurgeAll")
        c.conn.commit()
        c.o.kill("IVGAuditE")
        if ledger:
            engine(c).ledger.enable(strict=strict)
            c.conn.commit()
    finally:
        c.close()


def gkey(g: str) -> str:
    c = Conn(NS)
    try:
        return str(c.call("Graph.KG.GraphKey", "ForIndex", g))
    finally:
        c.close()


def ledger_gkey(g: str) -> str:
    c = Conn(NS)
    try:
        return str(c.call("Graph.KG.Ledger", "GKey", g))
    finally:
        c.close()


def cs(msg: str, key: Any = None):
    from iris_vector_graph.ledger import Changeset
    return Changeset(actor="audit:trace-replay", actor_type="ingest", message=msg, idempotency_key=key)


def commit(cs_):
    def f(c: Conn):
        r = engine(c).ledger.commit(cs_)
        c.conn.commit()
        return {"seq": r.revision.seq, "stmt_ids": dict(r.stmt_ids) if getattr(r, "stmt_ids", None) else {}}
    return f
