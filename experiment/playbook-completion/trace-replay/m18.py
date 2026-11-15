"""Module 18 (snapshots): trace replay through restore (M5) and snapcut (M4), models/breadth-c/src.

Scenarios (each from a clean namespace in AUDITE):
- restore: ledger enabled (genesis seq 1, outside the capture); commit A (tenant tr18a, unkeyed, seq 2);
  save_snapshot; commit B (tenant tr18b, keyed, seq 3); erase tenant tr18a and redact it (seq 2 tombstoned, the
  redaction's own revision seq 4); replacing restore of the archive (F-1801: head back to 2, revisions 3 and 4 and
  their records and the key binding stay, seq 2's tombstones overwritten by the archived content); a commit after
  the restore (refused: revision row 3 exists).
- snapcut: node a committed (outside the capture); a writer on its own connection opens a transaction and creates
  node b and edge a->b; save_snapshot on another connection; the writer rolls back (F-C1801: the archive holds b and
  a->b, a state that never committed).
"""
from __future__ import annotations

import trlib
from common import commit, cs, engine, reset
from families_c import SnpCut, SnpRestore

DESIGNS = ["as-built", "reviewed"]
KEY = "tr18-kB"
ARCH = trlib.run_dir() / "18" / "archives"

# module 12/13 have no footprints/ file: their footprints are the ones traces/conformance.py declares (FOOTPRINT)
ERASE = {"global:^IVG.Ledger", "global:^KG", "global:^NKG", "global:^IVG.AlgoCache", "global:^IVG.GraphMode",
         "global:^IVG.AdjNoLock", "global:^IVG.ArnoVersion", "sql:Graph_KG.nodes", "sql:Graph_KG.rdf_edges",
         "sql:Graph_KG.rdf_labels", "sql:Graph_KG.rdf_props", "sql:Graph_KG.docs", "sql:Graph_KG.kg_NodeEmbeddings",
         "sql:Graph_KG.kg_EdgeEmbeddings", "sql:Graph_KG.rdf_reifications", "sql:Graph_KG.kg_NodeEmbeddings_optimized"}
REDACT = {"global:^IVG.Ledger", "sql:Graph_KG.ledger_revisions", "sql:Graph_KG.ledger_stats",
          "global:^Graph.KG.LedgerRevisionD", "global:^Graph.KG.LedgerRevisionI"}


def s_restore(cap: trlib.Capture):
    reset(ledger=True)
    ARCH.mkdir(parents=True, exist_ok=True)
    path = str(ARCH / "restore.snapshot")
    cap.begin()
    a = cs("tenant a", None)
    a.create_node("tr18a|x", labels=["TR18"], properties={"secret": "tr18-sensitive"})
    cap.step("ledger-commit", commit(a), keyed=False)
    cap.step("save_snapshot", lambda c: engine(c).save_snapshot(path), path=path)
    b = cs("tenant b", KEY)
    b.create_node("tr18b|y", labels=["TR18"])
    cap.step("ledger-commit", commit(b), keyed=True)
    cap.step("erase", lambda c: engine(c).delete_nodes_by_prefix("tr18a|"))

    def redact(c):
        r = engine(c).ledger.redact(None, prefix="tr18a")
        c.conn.commit()
        return str(r)[:400]
    cap.step("redact", redact, redact_seqs=[2])
    cap.step("restore_snapshot", lambda c: engine(c).restore_snapshot(path, merge=False), path=path)
    cc = cs("after the restore", None)
    cc.create_node("tr18c|z")
    cap.step("ledger-commit", commit(cc), keyed=False)


G, A, B, P = "tr18g", "tr18na", "tr18nb", "TR"


def s_snapcut(cap: trlib.Capture):
    reset()
    ARCH.mkdir(parents=True, exist_ok=True)
    path = str(ARCH / "snapcut.snapshot")
    from iris_conn import Conn
    c = Conn(trlib.NS)
    engine(c).create_node(A, graph=G)
    c.close()
    cap.begin()

    def node(c):
        c.sql("START TRANSACTION")
        engine(c).create_node(B, graph=G)
        return {"tlevel": int(c.o.getTLevel())}
    cap.step("writer-create-node", node, who="W")
    cap.step("writer-create-edge", lambda c: (engine(c).create_edge(A, P, B, graph=G), int(c.o.getTLevel()))[1],
             who="W")
    cap.step("save_snapshot", lambda c: engine(c).save_snapshot(path), path=path)

    def rollback(c):
        c.o.tRollback()
        return {"tlevel": int(c.o.getTLevel())}
    cap.step("writer-rollback", rollback, who="W")


SCENARIOS = {"restore": s_restore, "snapcut": s_snapcut}

EXPECT = {
    "restore": [("snp_restore", SnpRestore.ONE, "F-1801"), ("snp_restore", SnpRestore.NOCONTENT, "F-1801"),
                ("snp_restore", SnpRestore.GROWS, "F-1801")],
    "snapcut": [("snp_cut", SnpCut.COMMITTED, "F-C1801")],
}


def families(trace, design):
    name = trace["name"].split("-", 1)[1]
    if name == "restore":
        return [SnpRestore(KEY, design)]
    if name == "snapcut":
        return [SnpCut(G, A, B, P, design)]
    raise KeyError(name)


def footprint(trace):
    led = trlib.declared("11", ["cls:Graph.KG.Ledger.Commit", "cls:Graph.KG.Ledger.CommitInTxn",
                                "py:iris_vector_graph/ledger/client.py:GraphLedger.commit",
                                "cls:Graph.KG.LedgerApply.OpCreateNode"])
    rest = trlib.declared("18", ["IRISGraphEngine.restore_snapshot(merge=False)",
                                 "IRISGraphEngine.restore_snapshot(merge=False) over an enabled ledger"])
    w = trlib.declared("03", ["py:IRISGraphEngine.create_node", "py:IRISGraphEngine.create_edge"])
    return {"ledger-commit": led, "save_snapshot": trlib.declared("18", ["IRISGraphEngine.save_snapshot"]),
            "erase": ERASE, "redact": REDACT, "restore_snapshot": rest,
            "writer-create-node": w, "writer-create-edge": w, "writer-rollback": w}
