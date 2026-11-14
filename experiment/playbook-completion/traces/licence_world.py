#!/usr/bin/env python3
"""Failure scenario S6: licence refusal at product level (IRIS Community: a fixed number of licence units).

    bash tools/locks.sh iris python traces/licence_world.py OUT_DIR      # only while NO other lane uses IRIS

The product under test is the pin's engine built with IRISGraphEngine.from_connect (it keeps its credentials, so its
first Native API call opens a DEDICATED connection: engine.py:1919-1942; when that connect fails it falls back,
without a log line, to the caller's own connection, which the code's comment says must not be shared with cursor DDL).

Worlds (each from an emptied AUDITE through the product's own EraseAll/PurgeAll):
  C  control, licence free: an engine's first native operation (ledger enable + commit) opens its dedicated
     connection; the commit is all-or-nothing; verify() equal; parameterised reads correct.
  X  licence exhausted after the engine connected but before its first native call: idle holder connections take
     every free unit; then the same operations. Observed: was the dedicated connection refused, did the engine fall
     back (engine._native_conn stays None), was anything logged, is the commit all-or-nothing and verify() equal,
     do parameterised reads on the shared connection stay correct afterwards (the driver-state hazard the product's
     comment names), and does a later commit still work.
  R  licence exhausted before the engine connects: from_connect must raise; nothing is written (counts read by a
     holder connection before and after).
Holder connections are plain DB-API connections, closed at the end of each world. Nothing is compiled.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
from iris_conn import Conn, version  # noqa: E402

NS = "AUDITE"
HOST, PORT = "127.0.0.1", int(os.environ["IVG_PORT"])
CAP = 16  # never open more than this many holders


class Grab(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.records = []

    def emit(self, r):
        self.records.append(f"{r.levelname} {r.name}: {r.getMessage()[:300]}")


def raw_conn():
    import iris.dbapi
    return iris.dbapi.connect(hostname=HOST, port=PORT, namespace=NS, username="_SYSTEM", password="SYS")


def fill(holders: list) -> dict:
    """Open holder connections until IRIS refuses one; return how many and the refusal text."""
    refusal = None
    while len(holders) < CAP:
        try:
            holders.append(raw_conn())
        except Exception as e:  # noqa: BLE001
            refusal = f"{type(e).__name__}: {str(e)[:300]}"
            break
    return {"holders": len(holders), "refusal": refusal}


def release(holders: list) -> None:
    while holders:
        try:
            holders.pop().close()
        except Exception:  # noqa: BLE001
            pass


def counts(c) -> dict:
    cur = c.cursor()
    out = {}
    for t in ("nodes", "rdf_edges", "ledger_revisions"):
        cur.execute(f"SELECT COUNT(*) FROM Graph_KG.{t}")
        out[t] = int(cur.fetchone()[0])
    cur.close()
    return out


def reset():
    with Conn(NS) as c:
        c.call("Graph.KG.Eraser", "EraseAll")
        c.call("Graph.KG.Ledger", "PurgeAll")
        c.conn.commit()


def ops(engine, tag: str, reader=None) -> dict:
    """The operations each world runs through the engine: native calls (ledger) and parameterised SQL reads."""
    from iris_vector_graph.ledger import Changeset
    res = {}
    try:
        engine.ledger.enable()
        cs = Changeset(actor="audit:licence", actor_type="ingest", idempotency_key=f"lic-{tag}-1", auto_stub_missing_nodes=True)
        for i in range(50):
            cs.create_relationship(f"{tag}a{i}", "R", f"{tag}b{i}", graph="LIC")
        r = engine.ledger.commit(cs)
        engine.conn.commit()
        res["commit1"] = {"seq": r.revision.seq}
    except Exception as e:  # noqa: BLE001
        res["commit1"] = {"error": f"{type(e).__name__}: {str(e)[:300]}"}
    res["native_conn_dedicated"] = getattr(engine, "_native_conn", None) is not None
    # parameterised reads on the engine's own connection (cursor), checked against known answers
    bad = []
    try:
        for i in (0, 17, 49):
            cur = engine.conn.cursor()
            cur.execute("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE s = ? AND graph_id = ?", (f"{tag}a{i}", "LIC"))
            n = int(cur.fetchone()[0])
            cur.close()
            if n != 1:
                bad.append({"s": f"{tag}a{i}", "rows": n})
        res["param_reads_wrong"] = bad
    except Exception as e:  # noqa: BLE001
        res["param_reads_error"] = f"{type(e).__name__}: {str(e)[:300]}"
    try:
        cs2 = Changeset(actor="audit:licence", actor_type="ingest", idempotency_key=f"lic-{tag}-2", auto_stub_missing_nodes=True)
        cs2.create_relationship(f"{tag}c0", "R", f"{tag}c1", graph="LIC")
        r2 = engine.ledger.commit(cs2)
        engine.conn.commit()
        res["commit2"] = {"seq": r2.revision.seq}
    except Exception as e:  # noqa: BLE001
        res["commit2"] = {"error": f"{type(e).__name__}: {str(e)[:300]}"}
    try:
        v = engine.ledger.verify()
        res["verify"] = str(getattr(v, "result", v))
    except Exception as e:  # noqa: BLE001
        res["verify"] = f"error {type(e).__name__}: {str(e)[:200]}"
    # the harness's own count goes through a holder connection when the units are taken (a new one would be refused)
    if reader is not None:
        cur = reader.cursor()
        cur.execute("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE graph_id = 'LIC' AND s %STARTSWITH ?", (tag,))
        rows = int(cur.fetchone()[0])
        cur.close()
    else:
        with Conn(NS) as c:
            rows = int(c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE graph_id = 'LIC' AND s %STARTSWITH ?", tag)[0][0])
    res["edge_rows"] = rows
    res["all_or_nothing_commit1"] = rows in (0, 50, 51) and (rows >= 50) == ("seq" in res["commit1"])
    return res


def world(name: str, exhaust_before_engine: bool, exhaust_before_native: bool) -> dict:
    from iris_vector_graph.engine import IRISGraphEngine
    reset()
    grab = Grab()
    logging.getLogger().addHandler(grab)
    logging.getLogger().setLevel(logging.DEBUG)
    holders: list = []
    out = {"world": name}
    try:
        if exhaust_before_engine:
            out["fill"] = fill(holders)
            before = counts(holders[0]) if holders else None
            try:
                e = IRISGraphEngine.from_connect(hostname=HOST, port=PORT, namespace=NS, username="_SYSTEM",
                                                 password="SYS", embedding_dimension=4)
                out["from_connect"] = "connected (no refusal)"
                e.conn.close()
            except Exception as ex:  # noqa: BLE001
                out["from_connect"] = f"refused: {type(ex).__name__}: {str(ex)[:300]}"
            after = counts(holders[0]) if holders else None
            out["counts_before_after"] = [before, after]
            out["nothing_written"] = before == after
            return out
        engine = IRISGraphEngine.from_connect(hostname=HOST, port=PORT, namespace=NS, username="_SYSTEM",
                                              password="SYS", embedding_dimension=4)
        if exhaust_before_native:
            out["fill"] = fill(holders)
        out["ops"] = ops(engine, name.lower(), holders[0] if holders else None)
        try:
            engine.conn.close()
            if getattr(engine, "_native_conn", None) is not None:
                engine._native_conn.close()
        except Exception:  # noqa: BLE001
            pass
        return out
    finally:
        release(holders)
        logging.getLogger().removeHandler(grab)
        out["log_lines_warning_or_above"] = [r for r in grab.records if not r.startswith(("DEBUG", "INFO"))][:20]
        out["log_lines_mentioning_connection"] = [r for r in grab.records if "connect" in r.lower()][:20]
        time.sleep(2)


def main() -> int:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    with Conn(NS) as c:
        eng = version(c)
    res = {"engine": eng, "namespace": NS,
           "worlds": [world("C", False, False), world("X", False, True), world("R", True, False)]}
    reset()
    (out / "results.json").write_text(json.dumps(res, indent=1, default=str))
    for w in res["worlds"]:
        print(json.dumps({k: w.get(k) for k in ("world", "fill", "from_connect", "nothing_written", "ops",
                                                 "log_lines_warning_or_above")}, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
