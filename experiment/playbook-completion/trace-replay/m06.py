"""Module 06 (vectors): trace replay through vec_ivf and vec_route_batch.

Scenarios:
- ivf: an IVF index over graph g with two cells (built before the capture with fixed centroids); ivf_insert of a and
  b into their cells, ivf_insert of a again with a vector of the other cell (F-0608: a is listed in two cells and
  counted twice), ivf_delete of a (removes the first cell only), erase_graph(g) (F-0606: the index keeps g's ids).
- route: store_embeddings for graph g under a model key with no route: a batch [a, m] (m missing) of width 2 (F-0615:
  refused after the route was created and committed), [a] of width 2 (stored), [a] of width 3 (refused by the
  route's identity, no change).
"""
from __future__ import annotations

import json

import trlib
from common import engine, reset
from families_a import VecIvf, VecRouteBatch

DESIGNS = ["as-built", "reviewed"]
G = "tr06g"
IDX = "tr06ivf"


def s_ivf(cap: trlib.Capture):
    reset()
    from iris_conn import Conn
    c = Conn(trlib.NS)
    try:
        eng = engine(c)
        for n, v in (("tr06a", [1.0, 0.0, 0.0, 0.0]), ("tr06b", [0.0, 1.0, 0.0, 0.0])):
            eng.create_node(n, graph=G)
            eng.store_embedding(n, v, graph=G)
        c.call("Graph.KG.IVFIndex", "Build", IDX, "2", '"cosine"', json.dumps([[1, 0, 0, 0], [0, 1, 0, 0]]), "[]", "")
        c.conn.commit()
    finally:
        c.close()
    cap.begin()
    for node, vec in (("tr06a", [1, 0, 0, 0]), ("tr06b", [0, 1, 0, 0]), ("tr06a", [0, 1, 0, 0])):
        cap.step("ivf_insert", lambda c, node=node, vec=vec: engine(c).ivf_insert(IDX, node, vec), ivf="Insert", node=node)
    cap.step("ivf_delete", lambda c: engine(c).ivf_delete(IDX, "tr06a"), ivf="Delete", node="tr06a")
    cap.step("erase_graph", lambda c: engine(c).erase_graph(G), ivf="EraseGraph")

    def after():
        c = Conn(trlib.NS)
        try:
            c.o.classMethodVoid("Graph.KG.IVFIndex", "Drop", IDX)
        finally:
            c.close()
    cap.after = [after]


def s_route(cap: trlib.Capture):
    reset()
    from iris_conn import Conn
    c = Conn(trlib.NS)
    try:
        engine(c).create_node("tr06ra", graph=G)
    finally:
        c.close()
    cap.begin()
    mk = "tr06-model"
    for items, nodes, w in ((2, ["tr06ra", "tr06rm"], 2), (0, ["tr06ra"], 2), (0, ["tr06ra"], 3)):
        batch = [{"node_id": n, "embedding": [0.5] * w} for n in nodes]
        cap.step("store_embeddings", lambda c, batch=batch: engine(c).store_embeddings(batch, graph=G, model_key=mk),
                 vrb_items=items, vrb_width=w)


SCENARIOS = {"ivf": s_ivf, "route": s_route}
EXPECT = {"ivf": [("vec_ivf", VecIvf.ONE, "F-0608"), ("vec_ivf", VecIvf.COUNT, "F-0608"),
                  ("vec_ivf", VecIvf.LIVE, "F-0606")],
          "route": [("vec_route_batch", VecRouteBatch.X39, "F-0615")]}


def families(trace, design):
    name = trace["name"].split("-", 1)[1]
    if name == "ivf":
        return [VecIvf(IDX, G, ["tr06a", "tr06b"], design)]
    return [VecRouteBatch(G, "tr06-model", design)]


ERASE = {"global:^IVG.Ledger", "global:^KG", "global:^NKG", "global:^IVG.AlgoCache", "global:^IVG.GraphMode",
         "global:^IVG.AdjNoLock", "global:^IVG.ArnoVersion", "sql:Graph_KG.nodes", "sql:Graph_KG.rdf_edges",
         "sql:Graph_KG.rdf_labels", "sql:Graph_KG.rdf_props", "sql:Graph_KG.docs", "sql:Graph_KG.kg_NodeEmbeddings",
         "sql:Graph_KG.kg_EdgeEmbeddings", "sql:Graph_KG.rdf_reifications", "sql:Graph_KG.kg_NodeEmbeddings_optimized",
         # EraseGraph also drops the graph's routed vector tables and their registry rows (Eraser.cls, FR-006)
         "sql:Graph_KG.embedding_registry", "sql:Graph_KG.kg_emb_*", "sql:Graph_KG.kg_eemb_*"}


def footprint(trace):
    return {"ivf_insert": trlib.declared("06", ["py:IRISGraphEngine.ivf_insert"]),
            "ivf_delete": trlib.declared("06", ["py:IRISGraphEngine.ivf_delete"]),
            "erase_graph": ERASE,
            "store_embeddings": trlib.declared("06", ["py:IRISGraphEngine.store_embeddings"])}
