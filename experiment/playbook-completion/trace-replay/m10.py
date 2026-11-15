"""Module 10 (algorithms): trace replay through the cache machine (models/breadth-b/src/m10.rs:99-303).

Scenario cache (default graph; tr10a -[:TRR]-> tr10b and an emptied ^IVG.AlgoCache set up before the capture):
  kg_PERSONALIZED_PAGERANK(["tr10x"]) before tr10x exists (miss, computed, Put); create_node tr10x with no edge
  (no token move); the same PPR call (F-1004: answered from the cache although a fresh computation scores tr10x);
  delete_node tr10x (Eraser: token up, cache killed); PPR again; delete_edge tr10a->tr10b (token up); PPR again.
"""
from __future__ import annotations

import trlib
from common import engine, gkey, reset
from families_b import Cache, Degree

DESIGNS = ["as-built", "reviewed"]
A, R, B, X = "tr10a", "TRR", "tr10b", "tr10x"


def s_cache(cap: trlib.Capture):
    reset()
    from iris_conn import Conn
    c = Conn(trlib.NS)
    eng = engine(c)
    eng.create_node(A)
    eng.create_node(B)
    eng.create_edge(A, R, B)
    c.call("Graph.KG.AlgoCache", "InvalidateAll")
    c.close()
    cap.meta["gkey"] = gkey("")
    cap.begin()
    K = dict(family="cache")

    def ppr(c):
        res = engine(c).kg_PERSONALIZED_PAGERANK([X])
        txt = str(res)
        return {"answer": txt[:400], "x_scored": X in txt}
    cap.step("ppr", ppr, **K)
    cap.step("create_node", lambda c: engine(c).create_node(X), **K)
    cap.step("ppr", ppr, **K)
    cap.step("delete_node", lambda c: engine(c).delete_node(X), **K)
    cap.step("ppr", ppr, **K)
    cap.step("delete_edge", lambda c: engine(c).delete_edge(A, R, B), **K)
    cap.step("ppr", ppr, **K)


GM = "tr10m"
DA, DB, DC, DR = "tr10da", "tr10db", "tr10dc", "TRD"


def s_degree(cap: trlib.Capture):
    """Machine degree (graph tr10m in multigraph mode, set up before the capture): a->b created twice by Cypher
    (parallel edges), c->b once, each followed by degree_centrality out and in (the sums of the degrees)."""
    reset()
    from iris_conn import Conn
    c = Conn(trlib.NS)
    eng = engine(c, native_cypher=False)
    for n in (DA, DB, DC):
        eng.create_node(n, graph=GM)
    eng.set_multigraph(GM, True)
    c.close()

    def after():
        c = Conn(trlib.NS)
        try:
            engine(c).erase_graph(GM)
        finally:
            c.close()
    cap.after = [after]
    cap.begin()
    D = dict(family="degree")

    def cy(src):
        def f(c):
            r = engine(c, native_cypher=False).execute_cypher(
                f"USE GRAPH '{GM}' MATCH (a {{id:'{src}'}}), (b {{id:'{DB}'}}) CREATE (a)-[:{DR}]->(b)")
            if getattr(r, "error", None):
                raise RuntimeError(str(r.error)[:300])
            return "ok"
        return f

    def deg(c):
        eng = engine(c)
        out = eng.degree_centrality(direction="out", top_k=0, graph=GM)
        inn = eng.degree_centrality(direction="in", top_k=0, graph=GM)
        return {"out": out, "in": inn, "out_sum": sum(int(r["degree"]) for r in out),
                "in_sum": sum(int(r["degree"]) for r in inn)}
    cap.step("degree_centrality", deg, **D)
    cap.step("create-ab", cy(DA), **D)
    cap.step("degree_centrality", deg, **D)
    cap.step("create-ab", cy(DA), **D)
    cap.step("degree_centrality", deg, **D)
    cap.step("create-cb", cy(DC), **D)
    cap.step("degree_centrality", deg, **D)


SCENARIOS = {"cache": s_cache, "degree": s_degree}

EXPECT = {"cache": [("cache[as-built]", Cache.P_HIT, "F-1004")],
          "degree": [("degree[as-built]", Degree.I_HANDSHAKE, "F-1007")]}


def families(trace, design):
    if trace["name"].endswith("-degree"):
        return [Degree(GM, DA, DR, DB, DC, design)]
    return [Cache(A, R, B, X, trace["meta"]["gkey"], design)]


def footprint(trace):
    return {
        "ppr": trlib.declared("10", ["eng:IRISGraphEngine.kg_PERSONALIZED_PAGERANK", "cls:Graph.KG.AlgoCache.Put"]),
        "create_node": trlib.declared("03", ["py:IRISGraphEngine.create_node"]),
        "delete_node": trlib.declared("03", ["py:IRISGraphEngine.delete_node"]),
        "delete_edge": trlib.declared("03", ["py:IRISGraphEngine.delete_edge"]),
        "create-ab": trlib.declared("08", ["eng:IRISGraphEngine.execute_cypher"]),
        "create-cb": trlib.declared("08", ["eng:IRISGraphEngine.execute_cypher"]),
        "degree_centrality": trlib.declared("10", ["cls:Graph.KG.Centrality.DegreeCentralityJson"])
        if _has("10", "cls:Graph.KG.Centrality.DegreeCentralityJson") else set(),
    }


def _has(nn, entry):
    try:
        trlib.declared(nn, [entry])
        return True
    except KeyError:
        return False
