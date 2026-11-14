"""Module 04 (adjacency): trace replay through adj_degree and adj_rebuild_txn (Caller).

Scenarios:
- degree: one source with edges to t0 (set up) and t1: Degree reads (miss, hit), a committed Put, a Remove inside a
  caller transaction that is rolled back (its generation step survives the rollback, P-0401), a committed Remove,
  EraseGraph (kills out, the generation and the cache), each followed by a Degree read whose answer is checked.
- rebuild: engine.sync() inside a caller transaction on the caller's own process, first failing on a poisoned edge
  row (graph_id '0', the upstream fixture's way, F-0409), then succeeding after the row is removed.
"""
from __future__ import annotations

import trlib
from common import engine, gkey, reset
from families_a import AdjDegree, AdjRebuildCaller, AdjToken

DESIGNS = ["as-built", "hd0401"]
G = "tr04g"
S, R, T0, T1 = "tr04s", "TR", "tr04t0", "tr04t1"


def s_degree(cap: trlib.Capture):
    reset()
    gk = gkey(G)
    cap.meta["gkey"] = gk
    from iris_conn import Conn
    c = Conn(trlib.NS)
    eng = engine(c)
    for n in (S, T0, T1):
        eng.create_node(n, graph=G)
    eng.create_edge(S, R, T0, graph=G)
    c.close()
    cap.begin()

    def degree(c):
        return int(c.call("Graph.KG.Adj", "Degree", gk, S))
    D = dict(family="adj_degree")
    cap.step("Adj.Degree", degree, **D)
    cap.step("Adj.Degree", degree, **D)
    cap.step("create_edge", lambda c: engine(c).create_edge(S, R, T1, graph=G), **D)
    cap.step("Adj.Degree", degree, **D)

    def w_delete(c):
        c.o.tStart()
        r = engine(c).delete_edge(S, R, T0, graph=G)
        return {"deleted": r, "tlevel": int(c.o.getTLevel())}
    cap.step("delete_edge", w_delete, who="W", w_open=True, **D)

    def w_rollback(c):
        c.o.tRollback()
        return {"tlevel": int(c.o.getTLevel())}
    cap.step("caller-rollback", w_rollback, who="W", **D)
    cap.step("Adj.Degree", degree, **D)
    cap.step("delete_edge", lambda c: engine(c).delete_edge(S, R, T0, graph=G), **D)
    cap.step("Adj.Degree", degree, **D)
    cap.step("erase_graph", lambda c: engine(c).erase_graph(G), **D)
    cap.step("Adj.Degree", degree, **D)


POISON = ("tr04pzs", "tr04pzo")
ERASE = {"global:^IVG.Ledger", "global:^KG", "global:^NKG", "global:^IVG.AlgoCache", "global:^IVG.GraphMode",
         "global:^IVG.AdjNoLock", "global:^IVG.ArnoVersion", "sql:Graph_KG.nodes", "sql:Graph_KG.rdf_edges",
         "sql:Graph_KG.rdf_labels", "sql:Graph_KG.rdf_props", "sql:Graph_KG.docs", "sql:Graph_KG.kg_NodeEmbeddings",
         "sql:Graph_KG.kg_EdgeEmbeddings", "sql:Graph_KG.rdf_reifications", "sql:Graph_KG.kg_NodeEmbeddings_optimized",
         # EraseGraph also drops the graph's routed vector tables and their registry rows (Eraser.cls, FR-006)
         "sql:Graph_KG.embedding_registry", "sql:Graph_KG.kg_emb_*", "sql:Graph_KG.kg_eemb_*"}


def _poison():
    from iris_conn import Conn
    c = Conn(trlib.NS)
    cur = c.conn.cursor()
    for node_id in POISON:
        cur.execute("INSERT INTO Graph_KG.nodes (node_id, graph_id) VALUES (?, '0')", [node_id])
    cur.execute("INSERT %NOINDEX INTO Graph_KG.rdf_edges (s, p, o_id, graph_id) VALUES (?, 'POISONS', ?, '0')",
                list(POISON))
    c.conn.commit()
    cur.close()
    c.close()


def _unpoison(c):
    cur = c.conn.cursor()
    try:
        cur.execute("DELETE %NOINDEX FROM Graph_KG.rdf_edges WHERE %NOINDEX graph_id = '0' AND %NOINDEX s = ?",
                    [POISON[0]])
        cur.execute('BUILD INDEX FOR TABLE Graph_KG.rdf_edges INDEX "%%DDLBEIndex"')
        cur.execute("DELETE FROM Graph_KG.nodes WHERE node_id %STARTSWITH ? AND graph_id = '0'", ["tr04pz"])
        c.conn.commit()
    finally:
        cur.close()
    return "poison rows removed"


def s_rebuild(cap: trlib.Capture):
    reset()
    _poison()

    def after():
        from iris_conn import Conn
        c = Conn(trlib.NS)
        try:
            if int(c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE graph_id = '0'")[0][0]):
                _unpoison(c)
        finally:
            c.close()
    cap.after = [after]
    cap.begin()
    for run, node in ((1, "tr04keep1"), (2, "tr04keep2")):
        def begin(c):
            c.o.tStart()
            return int(c.o.getTLevel())
        cap.step("caller-begin", begin, who=f"C{run}", run=run)
        cap.steps[-1]["tlevel"] = cap.steps[-1]["reply"]

        def write(c, node=node):
            engine(c).create_node(node)
            return int(c.o.getTLevel())
        cap.step("caller-create_node", write, who=f"C{run}", run=run)
        cap.steps[-1]["tlevel"] = cap.steps[-1]["reply"]

        def sync(c):
            try:
                engine(c).sync()
            finally:
                cap.meta[f"tlevel_after_sync_{run}"] = int(c.o.getTLevel())
            return "returned"
        cap.step("sync", sync, who=f"C{run}", run=run)
        cap.steps[-1]["tlevel"] = cap.meta[f"tlevel_after_sync_{run}"]

        def end(c):
            tl = int(c.o.getTLevel())
            if tl > 0:
                c.o.tCommit()
            return int(c.o.getTLevel())
        cap.step("caller-commit", end, who=f"C{run}", run=run)
        cap.steps[-1]["tlevel"] = cap.steps[-1]["reply"]
        if run == 1:
            cap.step("cleanup-poison", _unpoison, harness=True)


X, Y, Z = "tr04x", "tr04y", "tr04z"


def s_token(cap: trlib.Capture):
    """F-0402: W opens a transaction and creates x-R->y (its token step is not undone); a builder computes WCC while W
    is open and caches it under the token; W rolls back; a fresh engine is served the cached answer."""
    reset()
    from iris_conn import Conn
    c = Conn(trlib.NS)
    try:
        e = engine(c)
        for n in (X, Y, Z):
            e.create_node(n)
        e.create_edge(X, "R", Z)
    finally:
        c.close()
    cap.meta["gkey"] = gkey("")
    cap.begin()

    def w_open(c):
        c.o.tStart()
        engine(c).create_edge(X, "R", Y)
        return {"tlevel": int(c.o.getTLevel())}
    cap.step("create_edge", w_open, who="W", token_op="WOpen")

    def wcc(c):
        comp = engine(c).kg_WCC()
        return {"x_y_joined": comp.get(X) == comp.get(Y), "x_z_joined": comp.get(X) == comp.get(Z)}
    cap.step("kg_WCC", wcc, token_op="Build")

    def w_rollback(c):
        c.o.tRollback()
        return {"tlevel": int(c.o.getTLevel())}
    cap.step("caller-rollback", w_rollback, who="W", token_op="WRollback")

    def wcc_fresh(c):
        eng = engine(c)
        comp = eng.kg_WCC()
        return {"x_y_joined": comp.get(X) == comp.get(Y), "cache_stats": dict(getattr(eng._store, "_algo_cache_stats", {}))}
    cap.step("kg_WCC-fresh-engine", wcc_fresh)


SCENARIOS = {"degree": s_degree, "rebuild": s_rebuild, "token": s_token}

EXPECT = {
    "degree": [],
    "rebuild": [("adj_rebuild_caller[as-built]1", AdjRebuildCaller.B89, "F-0409")],
    "token": [("adj_token[as-built]", AdjToken.INV, "F-0402")],
}


def families(trace, design):
    name = trace["name"].split("-", 1)[1]
    if name == "degree":
        return [AdjDegree(trace["meta"]["gkey"], S, R, [T0, T1], design)]
    if name == "token":
        return [AdjToken(trace["meta"]["gkey"], X, Y, Z, "kg_WCC", "as-built" if design == "as-built" else "probe")]
    if name == "rebuild":
        d = {"as-built": "as-built", "hd0401": "reviewed"}[design]
        return [AdjRebuildCaller(1, "tr04keep1", d), AdjRebuildCaller(2, "tr04keep2", d)]
    raise KeyError(name)


def footprint(trace):
    return {
        "Adj.Degree": trlib.declared("04", ["cls:Graph.KG.Adj.Degree"]),
        "create_edge": trlib.declared("03", ["py:IRISGraphEngine.create_edge"]),
        "delete_edge": trlib.declared("03", ["py:IRISGraphEngine.delete_edge"]),
        "caller-rollback": trlib.declared("03", ["py:IRISGraphEngine.delete_edge"]),
        # module 12 has no footprints/ file; its erase footprint is the one traces/conformance.py declares (FOOTPRINT)
        "erase_graph": ERASE,
        "caller-begin": set(),
        "caller-create_node": trlib.declared("03", ["py:IRISGraphEngine.create_node"]),
        "sync": trlib.declared("04", ["py:IRISGraphEngine.sync"]) | trlib.declared("03", ["py:IRISGraphEngine.create_node"]),
        "caller-commit": set(),
        "cleanup-poison": {"sql:Graph_KG.rdf_edges", "sql:Graph_KG.nodes"},
        "kg_WCC": trlib.declared("04", ["cls:Graph.KG.AlgoCache.Put"]),
        "kg_WCC-fresh-engine": trlib.declared("04", ["cls:Graph.KG.AlgoCache.Put"]),
    }
