#!/usr/bin/env python3
"""F-1201 on the real engine: a graph erasure and a ledger commit into the same graph.

    python f1201_native.py OUT_DIR [--trials N]

Interleaving control without touching the product: a probe process holds the adjacency writer lock name
^IVG.AdjW("G") exclusively. Graph.KG.Eraser.EraseGraph deletes the graph's rows first and then asks for that lock in
Graph.KG.Adjacency.RemoveGraph (shared, 5 s timeout, Adjacency.cls:431), so it pauses after its row deletes and before
EraseLedgerFor (Eraser.cls:258). A ledger commit of create_relationship(u, R, v) into G starts meanwhile; its row
insert asks for the same lock shared (Adjacency.WriterLock, 5 s timeout, then writes without it). The probe then
releases; both proceed and race. The eraser never takes the ledger head lock (Eraser.cls:47-261).

Oracle (independent of the product): the IRIS journal records of the two processes (traces/journal.py), and the
stored state after both finish. ERS-I3 ("no recorded live edge loses its statement entry"): every rdf_edges row of
G created by a committed ledger revision has a live ("stmt") entry with an empty deletedSeq. A trial is a
reproduction when an edge row the commit created is live and its statement entry is gone.

Runs only in namespace AUDITCORE, under the IRIS lock. Product classes are the pin's, deployed by initialize_schema.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
sys.path.insert(0, str(HERE))
from iris_conn import Conn, version  # noqa: E402
import journal  # noqa: E402

from iris_vector_graph.engine import IRISGraphEngine  # noqa: E402
from iris_vector_graph.ledger import Changeset  # noqa: E402

NS = "AUDITCORE"
DB = "/usr/irissys/mgr/auditcore/"
G = "G"
# "edge": G holds x-R-y before the erase (the eraser's rdf_edges DELETE then waits on the writer lock);
# "none": G is empty, so the eraser's row DELETEs touch nothing and it pauses in Adjacency.RemoveGraph, after them.
# "other": as "none", plus 4,000 statements in graph H, which lengthens the eraser's statement scan after the pause.
SEED = "edge"


def engine(c: Conn) -> IRISGraphEngine:
    return IRISGraphEngine(c.conn, namespace=NS, embedding_dimension=4)


def reset(c: Conn) -> None:
    c.call("Graph.KG.Eraser", "EraseAll")
    c.call("Graph.KG.Ledger", "PurgeAll")
    c.conn.commit()


def stmt_entries(c: Conn):
    out = {}
    for sub, _ in c.o.iterator("^IVG.Ledger", "stmt").items():
        lst = c.o.getIRISList("^IVG.Ledger", "stmt", sub)
        out[str(sub)] = [lst.get(i) for i in range(1, lst.count() + 1)]
    return out


def trial(i: int, release_after: float, out: Path) -> dict:
    ctl = Conn(NS)
    try:
        reset(ctl)
        eng = engine(ctl)
        eng.ledger.enable()
        r0 = None
        if SEED == "other":
            # many statements in another graph: EraseLedgerFor scans every ("stmt") entry, so its scan is long
            for chunk in range(4):
                bulk = Changeset(actor="audit:f1201", actor_type="ingest", auto_stub_missing_nodes=True)
                for k in range(1000):
                    bulk.create_relationship(f"h{chunk}_{k}", "R", f"h{chunk}_{k + 1}", graph="H")
                eng.ledger.commit(bulk)
                ctl.conn.commit()
        if SEED == "edge":
            seed = Changeset(actor="audit:f1201", actor_type="ingest", auto_stub_missing_nodes=True)
            seed.create_relationship("x", "R", "y", graph=G)
            r0 = eng.ledger.commit(seed)
            ctl.conn.commit()
    finally:
        ctl.close()

    q, e, p = Conn(NS), Conn(NS), Conn(NS)
    res = {"trial": i, "release_after_s": release_after, "pids": {"probe": q.pid, "eraser": e.pid, "committer": p.pid},
           "seed": SEED, "seed_revision": getattr(r0, "revision", None) and str(r0.revision.seq)}
    m = journal.mark()
    q.o.lock("", 0, "^IVG.AdjW", G)  # exclusive: the eraser and the committer will each ask for it shared
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
            cs = Changeset(actor="audit:f1201", actor_type="ingest", auto_stub_missing_nodes=True)
            cs.create_relationship("u", "R", "v", graph=G)
            r = engine(p).ledger.commit(cs)
            p.conn.commit()
            cr["seq"] = r.revision.seq
        except Exception as ex:  # noqa: BLE001
            cr["error"] = str(ex)[:300]
        cr["t"] = time.time() - t0

    te = threading.Thread(target=erase)
    te.start()
    time.sleep(0.8)  # the eraser has deleted the rows and waits for ^IVG.AdjW("G")
    tc = threading.Thread(target=commit)
    tc.start()
    time.sleep(release_after)
    q.o.releaseAllLocks()
    res["released_at_s"] = time.time() - t0
    te.join(30)
    tc.join(30)
    res["erase"], res["commit"] = er, cr

    ctl = Conn(NS)
    try:
        edges = ctl.sql("SELECT s, p, o_id FROM Graph_KG.rdf_edges WHERE graph_id = ?", G)
        nodes = ctl.sql("SELECT node_id FROM Graph_KG.nodes WHERE graph_id = ?", G)
        stmts = stmt_entries(ctl)
        adj = int(ctl.o.isDefined("^KG", "out", G))
        res["after"] = {"edges_in_G": [list(map(str, r)) for r in edges], "nodes_in_G": sorted(str(r[0]) for r in nodes),
                        "stmt": stmts, "kg_out_G_defined": adj,
                        "adj_nolock": str(ctl.o.get("^IVG.AdjNoLock", G))}
        recs = journal.records_since(m, dbs={DB}, pids={e.pid, p.pid})
        stmt_ops = [{"a": r["a"], "who": "eraser" if r["p"] == e.pid else "committer", "t": r["t"], "g": r["g"]}
                    for r in recs if r["g"].startswith('^IVG.Ledger("stmt"') or r["g"].startswith('^IVG.Ledger("tuple"')]
        edge_rows = [{"a": r["a"], "who": "eraser" if r["p"] == e.pid else "committer", "t": r["t"]}
                     for r in recs if journal.global_root(r["g"]).startswith("^t52S.BWr6")]
        txns = journal.transactions(recs)
        res["journal"] = {"records": len(recs), "stmt_tuple_ops": stmt_ops, "edge_row_ops": edge_rows[:20],
                          "transactions": [{"pid": u["pid"], "kind": u["kind"], "committed": u["committed"],
                                            "n": len(u["records"]), "begin": u.get("begin"), "end": u.get("end")}
                                           for u in txns if u["kind"] == "txn"]}
        live_uv = any(r[0] == "u" and r[2] == "v" for r in res["after"]["edges_in_G"])
        uv_stmt = [k for k, v in stmts.items() if str(v[0]) == "u" and str(v[2]) == "v" and str(v[5] or "") == ""]
        res["verdict"] = {
            "commit_ok": "seq" in cr, "erase_ok": "removed" in er,
            "uv_edge_live": live_uv, "uv_live_stmt": bool(uv_stmt),
            "ERS-I3_violated": bool(live_uv and "seq" in cr and not uv_stmt),
            "edge_without_kg_out": bool(live_uv and not adj),
        }
    finally:
        ctl.close()
        for c in (q, e, p):
            c.close()
    (out / f"trial-{i}.json").write_text(json.dumps(res, indent=1, default=str))
    return res


def main() -> int:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    n = int(sys.argv[sys.argv.index("--trials") + 1]) if "--trials" in sys.argv else 8
    global SEED
    SEED = sys.argv[sys.argv.index("--seed") + 1] if "--seed" in sys.argv else "edge"
    c = Conn(NS)
    print("engine:", version(c), flush=True)
    c.close()
    summary = []
    for i in range(n):
        delay = [0.5, 1.0, 1.5, 2.0][i % 4]
        r = trial(i, delay, out)
        print(json.dumps({"trial": i, "delay": delay, **r["verdict"], "erase": r["erase"], "commit": r["commit"]},
                         default=str), flush=True)
        summary.append(r["verdict"])
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    hits = sum(1 for v in summary if v["ERS-I3_violated"])
    print(f"ERS-I3 violated in {hits} of {n} trials")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
