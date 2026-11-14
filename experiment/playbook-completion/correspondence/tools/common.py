"""Shared helpers of the correspondence lane: namespace AUDITC, the journal oracle, and conformance.py's functions
used with the namespace patched (conformance.py itself is not edited)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PC = HERE.parents[1]                      # experiment/playbook-completion
sys.path.insert(0, str(PC / "tools"))
sys.path.insert(0, str(PC / "traces"))
from iris_conn import Conn, version  # noqa: E402,F401
import journal  # noqa: E402
import conformance  # noqa: E402

NS = "AUDITC"
DB = "/usr/irissys/mgr/auditc/"
conformance.NS = NS          # module globals, read at call time by conformance.run/snapshot users
conformance.DB = DB

RUN_DIR = Path(os.environ["RUN_DIR"])
OUT = RUN_DIR / "correspondence"

# Routines watched by the line monitor: the classes of modules 11-14 and the adjacency writer whose locks they take.
CLASSES = ["Graph.KG.Ledger", "Graph.KG.LedgerApply", "Graph.KG.LedgerRedact", "Graph.KG.LedgerGenesis",
           "Graph.KG.LedgerRevision", "Graph.KG.LedgerStats", "Graph.KG.Eraser", "Graph.KG.Txn",
           "Graph.KG.Adjacency", "Graph.KG.GraphKey", "Graph.KG.SqlProcs"]


def reset(c: Conn) -> None:
    c.call("Graph.KG.Eraser", "EraseAll")
    c.call("Graph.KG.Ledger", "PurgeAll")
    c.conn.commit()


def engine(c: Conn):
    from iris_vector_graph.engine import IRISGraphEngine
    return IRISGraphEngine(c.conn, namespace=NS, embedding_dimension=4)


def rows(c: Conn) -> dict:
    """The content tables as plain rows (the store side of the abstraction function)."""
    q = {
        "nodes": "SELECT node_id, graph_id FROM Graph_KG.nodes",
        "labels": "SELECT s, label, graph_id FROM Graph_KG.rdf_labels",
        "props": 'SELECT s, "key", val, graph_id FROM Graph_KG.rdf_props',
        "edges": "SELECT edge_id, s, p, o_id, graph_id, qualifiers FROM Graph_KG.rdf_edges",
        "revisions": "SELECT seq, revision_id, kind, idempotency_key, message, source FROM Graph_KG.ledger_revisions",
    }
    out = {}
    for k, s in q.items():
        out[k] = [[None if v is None else str(v) for v in r] for r in c.sql(s)]
    return out


def session(script: str, ns: str = NS, timeout: int = 600) -> str:
    """Run an ObjectScript script in an `iris session` terminal (nothing compiled)."""
    r = subprocess.run(["docker", "exec", "-i", os.environ["IVG_TEST_CONTAINER"], "iris", "session", "IRIS", "-U", ns],
                       input=script, capture_output=True, text=True, errors="replace", timeout=timeout)
    return r.stdout.replace("\r", "")


def marked(out: str, tag: str):
    return [ln[1:] for ln in out.split("\n") if ln.startswith("\x1e" + tag + "|")]


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, default=str))


def now() -> float:
    return time.time()
