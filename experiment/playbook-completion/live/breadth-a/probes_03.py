"""Live checks of module 03 (direct writes) findings in AUDITA that need no ledger. See probe_lib for the rules."""
from __future__ import annotations

import math
import os
import sys
import threading
import time

from probe_lib import DB, J, Result, conn, engine, erase, gname, run


def p0305_bulk_chunks_not_one_transaction(r: Result):
    """F-0305: on a from_connect engine, bulk_create_nodes sends 1,000-node chunks to EdgeScan.BulkIngestNodesSQL through
    the engine's own Native API connection (another server process), each chunk its own TSTART/TCOMMIT, outside the
    WriteTxn opened on the cursor. Observation: chunk 2's nodes carry a label and a second connection holds a table lock
    on rdf_labels, so the call stalls inside chunk 2; meanwhile a third connection at READ COMMITTED counts the batch's
    committed nodes. The lock is then released (before IRIS's lock timeout) and the call completes. The journal is the
    independent oracle for which process committed what, in how many transactions.
    Oracle: USER_GUIDE.md:238-241 (each bulk write is a transaction of its own): no other process may see part of it."""
    from iris_vector_graph.engine import IRISGraphEngine
    import iris as _iris
    probe = conn()  # identity check of the dedicated container on this host:port
    smap = J.storage_map(probe)
    eng = IRISGraphEngine.from_connect("127.0.0.1", port=int(os.environ["IVG_PORT"]), namespace="AUDITA",
                                       username="_SYSTEM", password="SYS", embedding_dimension=4)
    blocker = conn()
    prefix = gname("bk")
    nodes = [{"id": f"{prefix}_{i:04d}"} for i in range(1000)] + \
            [{"id": f"{prefix}_{i:04d}", "labels": ["BK"]} for i in range(1000, 2000)]
    count_sql = "SELECT COUNT(*) FROM Graph_KG.nodes WHERE graph_id = '' AND node_id %STARTSWITH ?"
    out = {}
    try:
        r.obs("objectscript_deployed", eng.capabilities.objectscript_deployed)
        r.obs("cursor_pid", str(_iris.createIRIS(eng.conn).classMethodValue("%SYSTEM.SYS", "ProcessID")))
        blocker.o.tStart()
        blocker.sql("LOCK TABLE Graph_KG.rdf_labels IN EXCLUSIVE MODE")
        r.obs("blocker_pid", blocker.pid)
        m = J.mark()

        def call():
            t = time.time()
            try:
                out["result"] = f"returned {len(eng.bulk_create_nodes(nodes, disable_indexes=False))} ids"
            except Exception as e:
                out["result"] = f"raised {type(e).__name__}: {str(e)[:300]}"
            out["seconds"] = round(time.time() - t, 1)

        th = threading.Thread(target=call)
        th.start()
        time.sleep(4)
        r.obs("call_still_running_at_4s", th.is_alive())
        probe.sql("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
        mid = r.obs("committed_nodes_visible_to_another_process_mid_call", probe.sql(count_sql, prefix + "_")[0][0])
        blocker.sql("UNLOCK TABLE Graph_KG.rdf_labels IN EXCLUSIVE MODE")
        blocker.o.tRollback()
        th.join(timeout=300)
        r.obs("call", out)
        recs = J.records_since(m, dbs={DB})
        node_units = []
        for u in J.transactions(recs):
            stores = sorted({J.store_of(x["g"], smap) for x in u["records"] if x["g"]})
            if u["kind"] == "txn" and any("Graph_KG.nodes" in s for s in stores):
                node_units.append({"pid": u["pid"], "committed": u["committed"], "rolled_back": u["rolled_back"],
                                   "records": len(u["records"]), "stores": stores})
        r.obs("journal_node_transactions", node_units)
        r.obs("nodes_committed_after_call", probe.sql(count_sql, prefix + "_")[0][0])
        cursor_pid = r["observed"]["cursor_pid"]
        r["oracle"] = "no other process sees part of one bulk write; its writes are one transaction of the caller's"
        r["reproduced"] = 0 < mid < 2000 or any(u["pid"] != cursor_pid for u in node_units)
        r["verdict"] = (f"{mid} of 2000 nodes committed and visible to another process while the call ran; "
                        f"{len(node_units)} node-writing transactions, pids {sorted({u['pid'] for u in node_units})} "
                        f"(cursor pid {cursor_pid})" if r["reproduced"] else "atomic")
    finally:
        if blocker.o.getTLevel():
            blocker.o.tRollback()
        blocker.close()
        for t in ("rdf_props", "rdf_labels"):
            probe.sql(f"DELETE FROM Graph_KG.{t} WHERE graph_id = '' AND s %STARTSWITH ?", prefix + "_")
        probe.sql("DELETE FROM Graph_KG.nodes WHERE graph_id = '' AND node_id %STARTSWITH ?", prefix + "_")
        r.obs("cleanup_left", probe.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH ?", prefix)[0][0])
        probe.close()
        for cn in (getattr(eng, "_native_conn", None), eng.conn):
            try:
                cn.close()
            except Exception:
                pass


def p0306_long_graph_name_reads_as_duplicate(r: Result):
    """F-0306: create_node with a graph name over the column width answers False ("already exists") although nothing
    was written: the 'validation failed' text of SQLCODE -104 is matched as a duplicate."""
    c, eng = engine()
    g = "ba" + "g" * 300
    nid = gname("ln")
    try:
        try:
            r.obs("create_node", eng.create_node(nid, graph=g))
        except Exception as e:
            r.obs("create_node", f"{type(e).__name__}: {str(e)[:200]}")
        n = r.obs("rows_written", c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = ?", nid)[0][0])
        r["oracle"] = "False means the node already exists (create_node docstring); a refusal raises (R203)"
        r["reproduced"] = r["observed"]["create_node"] is False and n == 0
        r["verdict"] = "answered False (exists) with nothing written" if r["reproduced"] else "not reproduced"
    finally:
        c.close()


def p0307_ingest_drops_refused_edge(r: Result):
    """F-0307: bulk_ingest_edges on the server path drops an edge IRIS refuses (a 129-character predicate) and returns a
    smaller count with no error; its SQL path raises GraphWriteError for the same row."""
    c, eng = engine()
    a, b = gname("ia"), gname("ib")
    long_p = "P" * 129
    try:
        r.obs("objectscript_deployed", eng.capabilities.objectscript_deployed)
        try:
            n = r.obs("count", eng.bulk_ingest_edges([(a, b, "OK"), (a, b, long_p)], auto_sync=False))
        except Exception as e:
            n = None
            r.obs("count", f"raised {type(e).__name__}: {str(e)[:200]}")
        rows = r.obs("rows", c.sql("SELECT p FROM Graph_KG.rdf_edges WHERE graph_id = '' AND s = ?", a))
        r["oracle"] = "a refused row raises (4.7.0 row 14 for every other bulk writer; the SQL path raises)"
        r["reproduced"] = n == 1 and len(rows) == 1
        r["verdict"] = "the too-wide edge was dropped, count 1, no error" if r["reproduced"] else "raised/kept"
    finally:
        for nid in (a, b):
            try:
                eng.delete_node(nid, graph=None)
            except Exception as e:
                r.obs(f"cleanup_{nid}", str(e)[:100])
        c.close()


def p0308_loader_nan_breaks_reads(r: Result):
    """F-0308: BulkLoader.load_edges stores a NaN qualifier as bare JSON NaN; a later Cypher relationship read of the
    graph then fails. create_edge refuses the same value (4.6.0 R307)."""
    from iris_vector_graph.bulk_loader import BulkLoader
    c, eng = engine()
    g = gname("nan")
    try:
        try:
            eng.create_edge("x", "R", "y", qualifiers={"w": math.nan}, graph=g)
            r.obs("create_edge_nan", "accepted")
        except Exception as e:
            r.obs("create_edge_nan", f"refused {type(e).__name__}")
        BulkLoader(c.conn, graph=g).load_edges([("a", "R", "b", {"w": math.nan}), ("a", "R", "c", {"w": 1.0})],
                                               use_noindex=False)
        r.obs("stored_qualifiers", c.sql("SELECT o_id, qualifiers FROM Graph_KG.rdf_edges WHERE graph_id = ?", g))
        try:
            res = eng.execute_cypher(f"USE GRAPH '{g}' MATCH (a)-[r:R]->(b) RETURN b.node_id, r.w", {},
                                     raise_on_error=True)
            r.obs("cypher_read", ["ok", res.rows])
        except Exception as e:
            r.obs("cypher_read", ["error", str(e)[-250:]])
        r["oracle"] = "a stored edge never makes a relationship read fail (R307 refuses NaN on create_edge)"
        r["reproduced"] = r["observed"]["cypher_read"][0] == "error"
        r["verdict"] = "loader stored NaN and the Cypher read failed" if r["reproduced"] else "read succeeded"
    finally:
        erase(eng, g)
        c.close()


PROBES = {f.__name__: f for f in (p0305_bulk_chunks_not_one_transaction, p0306_long_graph_name_reads_as_duplicate,
                                  p0307_ingest_drops_refused_edge, p0308_loader_nan_breaks_reads)}

if __name__ == "__main__":
    sys.exit(run("03", PROBES, sys.argv[1:]))
