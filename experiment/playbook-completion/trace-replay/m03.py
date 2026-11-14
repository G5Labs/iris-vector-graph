"""Module 03 (direct writes): trace replay through wrt_ledger_stmt, wrt_bulk_atomic and tmp_mark.

Scenarios (each from a clean namespace; entry points are the pin's public engine API and ledger client):
- stmt: a ledger-created edge deleted and re-created directly, then updated, deleted and re-created through the
  ledger, then its node deleted (F-0303: the direct delete leaves the statement; the update joins two lifetimes).
- bulk: bulk_create_nodes of 2,000 nodes (two server-loader chunks) on a from_connect engine whose last node carries
  a property value IRIS refuses, so the second chunk and the SQL fallback fail (F-0305: the first chunk stays
  committed although the call raised).
- mark: over a temporal edge's marked row, store_edge (F-0304) and, on a second triple, create_edge (the adopting
  control), each followed by the triple's last temporal delete.
"""
from __future__ import annotations

import time

import trlib
from common import commit, cs, engine, from_connect, gkey, ledger_gkey, pid_of_dbapi, reset
from families_a import TmpMark, WrtBulkAtomic, WrtLedgerStmt

DESIGNS = ["as-built", "reviewed"]
A, R, B = "tr03a", "TR", "tr03b"
G = "tr03g"


def s_stmt(cap: trlib.Capture):
    reset(ledger=True)
    cap.meta["ledger_gkey"] = ledger_gkey("")
    cap.begin()
    t = [A, R, B]
    c1 = cs("create a, b and a-[TR]->b", "k-create")
    c1.create_node(A)
    c1.create_node(B)
    c1.create_relationship(A, R, B)
    cap.step("ledger-create-rel", commit(c1), triple=t, entry=["py:iris_vector_graph/ledger/client.py:GraphLedger.commit"])
    cap.step("delete_edge", lambda c: engine(c).delete_edge(A, R, B), triple=t)
    cap.step("create_edge", lambda c: engine(c).create_edge(A, R, B), triple=t)
    c2 = cs("set a qualifier on a-[TR]->b by tuple", "k-update")
    c2.set_qualifier((A, R, B), "w", "1")
    cap.step("ledger-update-rel", commit(c2), triple=t)
    c3 = cs("delete a-[TR]->b by tuple", "k-delete")
    c3.delete_relationship((A, R, B))
    cap.step("ledger-delete-rel", commit(c3), triple=t)
    c4 = cs("re-create a-[TR]->b", "k-recreate")
    c4.create_relationship(A, R, B)
    cap.step("ledger-create-rel", commit(c4), triple=t)
    cap.step("delete_node", lambda c: engine(c).delete_node(A), triple=t)


def s_bulk(cap: trlib.Capture):
    reset()
    prefix = "tr03bk"
    chunk_a = [f"{prefix}_{i:04d}" for i in range(1000)]
    chunk_b = [f"{prefix}_{i:04d}" for i in range(1000, 2000)]
    # the last node of the second chunk carries a property value wider than rdf_props.val (VARCHAR(64000),
    # iris_vector_graph/schema.py:415); _check_create_nodes checks id, label and key widths only
    # (nodes_edges.py:243-262), so the loader's chunk 2 and the SQL fallback are refused by IRIS
    nodes = [{"id": n} for n in chunk_a] + [{"id": n} for n in chunk_b[:-1]] + \
        [{"id": chunk_b[-1], "properties": {"blob": "x" * 70000}}]
    cap.meta["chunks"] = [chunk_a, chunk_b]
    cap.begin()

    def bulk(c):
        eng = from_connect()
        try:
            cap.meta["objectscript_deployed"] = bool(eng.capabilities.objectscript_deployed)
            cursor_pid = pid_of_dbapi(eng.conn)
            native = eng._iris_obj()
            loader_pid = str(native.classMethodValue("%SYSTEM.SYS", "ProcessID"))
            cap.meta["pids"] = {"cursor": cursor_pid, "loader": loader_pid}
            t0 = time.time()
            try:
                out = f"returned {len(eng.bulk_create_nodes(nodes, disable_indexes=False))} ids"
            except Exception as e:  # noqa: BLE001
                cap.meta["raised"] = f"{type(e).__name__}: {str(e)[:300]}"
                cap.meta["seconds"] = round(time.time() - t0, 1)
                raise
            cap.meta["seconds"] = round(time.time() - t0, 1)
            return out, [cursor_pid, loader_pid]
        finally:
            for cn in (getattr(eng, "_native_conn", None), eng.conn):
                try:
                    cn.close()
                except Exception:  # noqa: BLE001
                    pass
    cap.step("bulk_create_nodes", bulk)
    st = cap.steps[-1]
    st["pids"] = sorted(set(st["pids"]) | set(cap.meta.get("pids", {}).values()))
    st["loader_pids"] = [cap.meta.get("pids", {}).get("loader")]
    cap.step("count-committed", lambda c: c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH ?",
                                                prefix)[0][0])


def s_mark(cap: trlib.Capture):
    reset()
    cap.meta["gkey"] = gkey(G)
    cap.begin()
    for writer in ("store_edge", "create_edge"):
        s, o = f"tr03{writer[:2]}s", f"tr03{writer[:2]}o"
        t = [s, R, o]
        cap.step("create_edge_temporal", lambda c, s=s, o=o: engine(c).create_edge_temporal(s, R, o, timestamp=100,
                                                                                            graph=G), triple=t)
        cap.step(writer, lambda c, s=s, o=o, w=writer: getattr(engine(c), w)(s, R, o, graph=G), triple=t)
        cap.step("delete_edge_temporal", lambda c, s=s, o=o: engine(c).delete_edge_temporal(s, R, o, 100, graph=G),
                 triple=t)


SCENARIOS = {"stmt": s_stmt, "bulk": s_bulk, "mark": s_mark}

EXPECT = {
    "stmt": [("wrt_ledger_stmt", WrtLedgerStmt.STMT, "F-0303"), ("wrt_ledger_stmt", WrtLedgerStmt.IDENT, "F-0303")],
    "bulk": [("wrt_bulk_atomic", WrtBulkAtomic.INV, "F-0305")],
    "mark": [("tmp_mark[as-built]tr03sts", TmpMark.EXPL, "F-0304")],
}


def families(trace, design):
    name = trace["name"].split("-", 1)[1]
    if name == "stmt":
        d = {"as-built": "as-built", "reviewed": "reviewed"}[design]
        return [WrtLedgerStmt((A, R, B), trace["meta"]["ledger_gkey"], d)]
    if name == "bulk":
        return [WrtBulkAtomic(trace["meta"]["chunks"], design)]
    if name == "mark":
        gk = trace["meta"]["gkey"]
        return [TmpMark(G, gk, ("tr03sts", R, "tr03sto"), design), TmpMark(G, gk, ("tr03crs", R, "tr03cro"), design)]
    raise KeyError(name)


def footprint(trace):
    fp = {
        "ledger-create-rel": trlib.declared("11", ["cls:Graph.KG.Ledger.Commit", "cls:Graph.KG.Ledger.CommitInTxn",
                                                   "py:iris_vector_graph/ledger/client.py:GraphLedger.commit",
                                                   "cls:Graph.KG.LedgerApply.OpCreateNode",
                                                   "cls:Graph.KG.LedgerApply.OpCreateRel"]),
        "ledger-update-rel": trlib.declared("11", ["cls:Graph.KG.Ledger.Commit", "cls:Graph.KG.Ledger.CommitInTxn",
                                                   "py:iris_vector_graph/ledger/client.py:GraphLedger.commit",
                                                   "cls:Graph.KG.LedgerApply.OpCreateRel"]),
        "ledger-delete-rel": trlib.declared("11", ["cls:Graph.KG.Ledger.Commit", "cls:Graph.KG.Ledger.CommitInTxn",
                                                   "py:iris_vector_graph/ledger/client.py:GraphLedger.commit",
                                                   "cls:Graph.KG.LedgerApply.OpDeleteRel",
                                                   "cls:Graph.KG.LedgerApply.DeleteRelInternal"]),
        "delete_edge": trlib.declared("03", ["py:IRISGraphEngine.delete_edge"]),
        "create_edge": trlib.declared("03", ["py:IRISGraphEngine.create_edge"]),
        "store_edge": trlib.declared("03", ["py:IRISGraphEngine.store_edge"]),
        "delete_node": trlib.declared("03", ["py:IRISGraphEngine.delete_node"]),
        "bulk_create_nodes": trlib.declared("03", ["py:IRISGraphEngine.bulk_create_nodes"]),
        "create_edge_temporal": trlib.declared("05", ["py:IRISGraphEngine.create_edge_temporal"]),
        "delete_edge_temporal": trlib.declared("05", ["py:IRISGraphEngine.delete_edge_temporal"]),
        "count-committed": set(),
    }
    return fp
