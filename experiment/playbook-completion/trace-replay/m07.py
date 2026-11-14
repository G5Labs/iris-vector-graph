"""Module 07 (text search): trace replay through the bm25 machine (models/breadth-b/src/m07.rs).

Scenario bm25 (graph tr07g; documents tr07d0 = "alpha bravo", tr07d1 = "bravo" as node property `name`, and an
inserted tr07d2 = "alpha"; the machine's docs 0, 1, 2 and tokens t0 = alpha, t1 = bravo):
  bm25_build over `name` (the corpus build), bm25_insert of tr07d2, bm25_delete of tr07d0, the index handle's
  build over a property no node has (F-0704: refused with IndexNotBuiltError after Build replaced the index),
  bm25_drop.
"""
from __future__ import annotations

import trlib
from common import engine, reset
from families_b import Bm25, Leg

DESIGNS = ["as-built", "reviewed"]
G = "tr07g"
IDX = "tr07idx"
DOCS = ["tr07d0", "tr07d1", "tr07d2"]
TOKENS = ["alpha", "bravo"]


def s_bm25(cap: trlib.Capture):
    reset()
    from iris_conn import Conn
    c = Conn(trlib.NS)
    eng = engine(c)
    try:
        eng.bm25_drop(IDX)
    except Exception:  # noqa: BLE001
        pass
    eng.create_node(DOCS[0], properties={"name": "alpha bravo"}, graph=G)
    eng.create_node(DOCS[1], properties={"name": "bravo"}, graph=G)
    c.close()

    def after():
        c = Conn(trlib.NS)
        try:
            engine(c).bm25_drop(IDX)
        finally:
            c.close()
    cap.after = [after]
    cap.begin()
    B = dict(family="bm25")
    cap.step("bm25_build", lambda c: engine(c).bm25_build(IDX, ["name"], graph=G), **B)
    cap.step("bm25_insert", lambda c: engine(c).bm25_insert(IDX, DOCS[2], "alpha"), **B)
    cap.step("bm25_delete", lambda c: engine(c).bm25_delete(IDX, DOCS[0]), **B)

    def empty_build(c):
        eng = engine(c)
        return eng.index(IDX).build(properties=["tr07_no_such_property"], graph=G)
    cap.step("index.build", empty_build, **B)
    cap.step("bm25_search", lambda c: engine(c).bm25_search(IDX, "bravo", 5), **B)
    cap.step("bm25_drop", lambda c: engine(c).bm25_drop(IDX), **B)


GA = "tr07gA"
LNAMES = ["tr07L0", "tr07L1", "tr07L2"]
LDOC = {"tr07Ld1": "D", "tr07La1": "A"}
GNAME = {"D": "", "A": GA}


def s_leg(cap: trlib.Capture):
    """Machine leg: index 0 built over graph A; indexes 1 and 2 created by a first bm25_insert (no recorded graph)
    of a default-graph and a graph-A document; scoped and unscoped ivg.bm25.search calls; a drop."""
    reset()
    from iris_conn import Conn
    c = Conn(trlib.NS)
    eng = engine(c)
    for n in LNAMES:
        try:
            eng.bm25_drop(n)
        except Exception:  # noqa: BLE001
            pass
    eng.create_node("tr07Ld1", properties={"name": "delta"})
    eng.create_node("tr07La1", properties={"name": "delta"}, graph=GA)
    c.close()

    def after():
        c = Conn(trlib.NS)
        try:
            for n in LNAMES:
                engine(c).bm25_drop(n)
        finally:
            c.close()
    cap.after = [after]
    cap.begin()
    L = dict(family="leg")
    cap.step("bm25_build", lambda c: engine(c).bm25_build(LNAMES[0], ["name"], graph=GA), slot=0, g="A", **L)
    cap.step("bm25_insert", lambda c: engine(c).bm25_insert(LNAMES[1], "tr07Ld1", "delta"), slot=1, g="D", **L)
    cap.step("bm25_insert", lambda c: engine(c).bm25_insert(LNAMES[2], "tr07La1", "delta"), slot=2, g="A", **L)

    def ask(scoped, k):
        def f(c):
            eng = engine(c)
            pre = f"USE GRAPH '{scoped}' " if scoped else ""
            r = eng.execute_cypher(pre + f"CALL ivg.bm25.search('{LNAMES[k]}', 'delta', 5) YIELD node, score "
                                         "RETURN node, score")
            if getattr(r, "error", None):
                raise RuntimeError(str(r.error)[:300])
            txt = str(r.rows)
            label = None
            if not scoped:
                ig = eng._index_graph(LNAMES[k], "bm25")
                label = None if ig is None else {v: kk for kk, v in GNAME.items()}.get(str(ig), "?" + str(ig))
            return {"rows": txt[:400], "docs": sorted(d for d in LDOC if d in txt), "label": label}
        return f
    cap.step("ask-scoped", ask(GA, 0), query=["CypherScoped", "A", 0], **L)
    cap.step("ask-scoped", ask(GA, 1), query=["CypherScoped", "A", 1], **L)
    cap.step("ask-all", ask(None, 2), query=["CypherAll", 2], **L)
    cap.step("ask-all", ask(None, 0), query=["CypherAll", 0], **L)
    cap.step("bm25_drop", lambda c: engine(c).bm25_drop(LNAMES[1]), slot=1, **L)


SCENARIOS = {"bm25": s_bm25, "leg": s_leg}

EXPECT = {"bm25": [("bm25[as-built]", Bm25.X2, "F-0704")],
          "leg": [("leg[as-built]", Leg.L_SCOPE, "F-0707"), ("leg[as-built]", Leg.L_LABEL, "F-0705")]}


def families(trace, design):
    if trace["name"].endswith("-leg"):
        return [Leg(LNAMES, LDOC, GNAME, design)]
    return [Bm25(IDX, DOCS, TOKENS, design)]


def footprint(trace):
    return {
        "bm25_build": trlib.declared("07", ["eng:IRISGraphEngine.bm25_build", "cls:Graph.KG.BM25Index.Build"]),
        "bm25_insert": trlib.declared("07", ["eng:IRISGraphEngine.bm25_insert", "cls:Graph.KG.BM25Index.Insert"]),
        "bm25_delete": trlib.declared("07", ["eng:IRISGraphEngine.bm25_delete", "cls:Graph.KG.BM25Index.Delete"]),
        "index.build": trlib.declared("07", ["py:iris_vector_graph/index_protocol.py:Index.build[fulltext]",
                                             "cls:Graph.KG.BM25Index.Build"]),
        "bm25_search": trlib.declared("07", ["eng:IRISGraphEngine.bm25_search"]),
        "bm25_drop": trlib.declared("07", ["eng:IRISGraphEngine.bm25_drop", "cls:Graph.KG.BM25Index.Drop"]),
        "ask-scoped": trlib.declared("07", ["cypher:ivg.bm25.search"]),
        "ask-all": trlib.declared("07", ["cypher:ivg.bm25.search"]),
    }
