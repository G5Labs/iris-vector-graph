"""Shared helpers for intent lane B (fork 3) ledger/snapshot probes in namespace AUDITIB.

Every probe that uses these helpers must run under the EXCLUSIVE lane lock
($RUN_DIR/intent-b/auditib.lock): it purges and enables the namespace's ledger. Data written by these probes carries
the prefix ib3_ (node ids, graph ids) and is removed at the end with the pin's own erase calls plus a raw-SQL sweep of
leftover ib3_ property/label rows. The ledger is left never-enabled (Graph.KG.Ledger.PurgeAll, the pin's own
test/admin reset, iris_src/src/Graph/KG/Ledger.cls:241-248).
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.environ["WORK_DIR"], "experiment/playbook-completion/tools"))
from iris_conn import Conn  # noqa: E402

from iris_vector_graph.engine import IRISGraphEngine  # noqa: E402

NS = "AUDITIB"
PFX = "ib3_"


def out(label, value=None):
    if value is None:
        print(label, flush=True)
    else:
        print(f"{label}: {value}", flush=True)


def engine_on(c: Conn) -> IRISGraphEngine:
    """An engine built on a connection the caller made (no stored credentials): its Native API calls run on the
    same server process as its SQL (engine.py:1922-1929)."""
    return IRISGraphEngine(c.conn, namespace=NS, embedding_dimension=4)


def engine_native_elsewhere(c_sql: Conn, c_native: Conn) -> IRISGraphEngine:
    """An engine whose Native API connection is a second server process, the topology from_connect produces
    (engine.py:1922-1942 keeps a dedicated `_native_conn`). The second connection is an identity-checked Conn, so no
    connection bypasses tools/iris_conn.py; `_iris_obj()` then takes its own production branch
    `return _create(self._native_conn)`."""
    e = IRISGraphEngine(c_sql.conn, namespace=NS, embedding_dimension=4)
    e._native_conn = c_native.conn
    return e


def meta(c: Conn) -> dict:
    return json.loads(str(c.call("Graph.KG.Ledger", "Meta")))


def purge_ledger(c: Conn) -> None:
    c.call("Graph.KG.Ledger", "PurgeAll")


def foreign_rows(c: Conn) -> dict:
    """Rows in AUDITIB that this fork did not write (another lane-B probe's leftovers)."""
    return {
        "nodes": c.sql(f"SELECT COUNT(*) FROM Graph_KG.nodes WHERE NOT (node_id %STARTSWITH '{PFX}')")[0][0],
        "rdf_edges": c.sql(f"SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE NOT (s %STARTSWITH '{PFX}')")[0][0],
    }


def cleanup(c: Conn, graphs=()) -> None:
    """Remove this fork's data: ledger purged first (so the erase calls are not guarded), then the pin's erase
    calls, then a sweep of leftover ib3_ rows that no node row selects (orphan property rows, F-1306)."""
    purge_ledger(c)
    e = engine_on(c)
    for g in graphs:
        try:
            e.erase_graph(g)
        except Exception as ex:  # noqa: BLE001
            out(f"cleanup erase_graph({g}) failed", repr(ex))
    try:
        e.delete_nodes_by_prefix(PFX)
    except Exception as ex:  # noqa: BLE001
        out("cleanup delete_nodes_by_prefix failed", repr(ex))
    for t, col in (("rdf_edges", "s"), ("rdf_labels", "s"), ("rdf_props", "s"), ("nodes", "node_id")):
        try:
            c.sql(f"DELETE FROM Graph_KG.{t} WHERE {col} %STARTSWITH '{PFX}'")
        except Exception as ex:  # noqa: BLE001
            out(f"cleanup sweep {t} failed", repr(ex))
    try:
        c.conn.commit()
    except Exception:  # noqa: BLE001
        pass
    purge_ledger(c)
    left = {t: c.sql(f"SELECT COUNT(*) FROM Graph_KG.{t} WHERE {col} %STARTSWITH '{PFX}'")[0][0]
            for t, col in (("nodes", "node_id"), ("rdf_edges", "s"), ("rdf_labels", "s"), ("rdf_props", "s"))}
    out("cleanup: ib3_ rows left", left)
    out("cleanup: ledger meta", meta(c))
