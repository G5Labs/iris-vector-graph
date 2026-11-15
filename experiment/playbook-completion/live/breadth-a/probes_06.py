"""Live checks of module 06 (vectors) findings in AUDITA that need no ledger. See probe_lib for the rules."""
from __future__ import annotations

import json
import sys

from probe_lib import Result, engine, erase, gname, run


class FakeModel:
    """A sentence-transformers-shaped model: encode(texts) -> list of vectors of a fixed width."""

    def __init__(self, width):
        self.width = width

    def encode(self, texts, **kw):
        import numpy as np  # embed_nodes calls .tolist() on each row, as sentence-transformers returns arrays
        if isinstance(texts, str):  # a single text gives one vector, as sentence-transformers does
            return np.array([float(j % 3 + 1) for j in range(self.width)])
        return np.array([[float((i + j) % 3 + 1) for j in range(self.width)] for i, _ in enumerate(texts)])


def _registry(c, g):
    return c.sql("SELECT table_name, graph_id, model_key, dimension FROM Graph_KG.embedding_registry WHERE graph_id = ?", g)


def p0604_queue_done_without_vector(r: Result):
    """F-0604: Graph.KG.EmbedQueue.ProcessBatch marks an entry DONE when EMBEDDING() cannot run (Community has no such
    config), with no vector and no error. Oracle: DONE is the result vector (SetResult docstring); a failure is ERROR."""
    c, eng = engine()
    nid = gname("q")
    try:
        eng.create_node(nid)
        n = r.obs("enqueued", eng.enqueue_for_embedding(node_ids=[nid], embedding_config="ba-no-such-config"))
        req = [k for k in _queue_ids(c) if str(c.o.get("^EmbedQueue", k, "node_id")) == nid]
        r.obs("req_ids", req)
        r.obs("process_batch", str(c.call("Graph.KG.EmbedQueue", "ProcessBatch", 100, 30)))
        st = {k: (str(c.o.get("^EmbedQueue", k, "status")), str(c.o.get("^EmbedQueue", k, "error") or ""),
                  int(c.o.isDefined("^EmbedQueue", k, "result"))) for k in req}
        r.obs("entry_status_error_result", st)
        vec = r.obs("vector_rows", c.sql("SELECT COUNT(*) FROM Graph_KG.kg_NodeEmbeddings WHERE node_id = ?", nid)[0][0])
        r["oracle"] = "an entry is DONE only with a stored vector; a failed EMBEDDING() is ERROR with the IRIS message"
        r["reproduced"] = n >= 1 and any(v[0] == "DONE" for v in st.values()) and vec == 0
        r["verdict"] = "entry DONE, no vector, no error" if r["reproduced"] else "not reproduced"
    finally:
        for k in _queue_ids(c):
            if str(c.o.get("^EmbedQueue", k, "node_id")) == nid:
                c.o.kill("^EmbedQueue", k)
        try:
            eng.delete_node(nid, graph=None)
        except Exception:
            pass
        c.close()


def _queue_ids(c):
    out, k = [], ""
    while True:
        k = c.o.nextSubscript(False, "^EmbedQueue", k)
        if k is None or k == "":
            return out
        if k != "$seq":
            out.append(k)


def p0606_erase_leaves_ivf(r: Result):
    """F-0606 (HD-0601): after erase_graph(g), an IVF index built over g's vectors still answers g's node ids and
    ^IVF still holds their vectors."""
    c, eng = engine()
    g = gname("iv")
    name = gname("ivf")
    try:
        items = []
        for i in range(4):
            eng.create_node(f"n{i}", graph=g)
            items.append({"node_id": f"n{i}", "embedding": [1.0 + i, 0.5, 0.25, 0.1 * i]})
        eng.store_embeddings(items, graph=g)
        r.obs("ivf_build", eng.ivf_build(name, nlist=2, graph=g))
        before = r.obs("search_before", eng.ivf_search(name, [1.0, 0.5, 0.25, 0.0], k=3))
        r.obs("erase_graph", eng.erase_graph(g))
        r.obs("rows_after_erase", c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE graph_id = ?", g)[0][0])
        after = r.obs("search_after_erase", eng.ivf_search(name, [1.0, 0.5, 0.25, 0.0], k=3))
        r.obs("ivf_info_after_erase", eng.ivf_info(name))
        r["oracle"] = "HD-0601 (assumption): erasure leaves no graph-owned index answering the erased graph's ids"
        r["reproduced"] = bool(after)
        r["verdict"] = f"IVF still answers {len(after)} erased ids" if after else "index purged"
    finally:
        try:
            eng.ivf_drop(name)
        except Exception as e:
            r.obs("cleanup_drop", str(e))
        erase(eng, g)
        c.close()


def p0607_ivf_cosine_is_dot(r: Result):
    """F-0607: IVF metric "cosine" ranks by unnormalised dot product: a long vector at 45 degrees outranks a short one
    pointing the query's way, and scores leave [-1, 1]."""
    c, eng = engine()
    g = gname("ic")
    name = gname("ivc")
    try:
        eng.create_node("long45", graph=g)
        eng.create_node("short0", graph=g)
        eng.store_embeddings([{"node_id": "long45", "embedding": [10.0, 0.0, 0.0, 0.0]},
                              {"node_id": "short0", "embedding": [0.1, 0.1, 0.0, 0.0]}], graph=g)
        eng.ivf_build(name, nlist=1, metric="cosine", graph=g)
        res = r.obs("ivf_search", eng.ivf_search(name, [1.0, 1.0, 0.0, 0.0], k=2))
        top = res[0][0] if res and isinstance(res[0], (list, tuple)) else (res[0].get("id") if res else None)
        r["oracle"] = "cosine ranks short0 (cos 1.0) above long45 (cos 0.707), scores within [-1, 1]"
        r["reproduced"] = top == "long45"
        r["verdict"] = "dot-product order and scores outside [-1, 1]" if r["reproduced"] else "cosine order"
    finally:
        try:
            eng.ivf_drop(name)
        except Exception:
            pass
        erase(eng, g)
        c.close()


def p0608_ivf_insert_duplicates(r: Result):
    """F-0608: IVFIndex.Insert of an id already indexed adds it to another cell without removing the old entry and
    counts it again; the stale vector still answers."""
    c, eng = engine()
    g = gname("id")
    name = gname("ivd")
    try:
        eng.create_node("a", graph=g)
        eng.create_node("b", graph=g)
        eng.store_embeddings([{"node_id": "a", "embedding": [1.0, 0.0, 0.0, 0.0]},
                              {"node_id": "b", "embedding": [0.0, 1.0, 0.0, 0.0]}], graph=g)
        eng.ivf_build(name, nlist=2, metric="dot", graph=g)
        r.obs("info_before", eng.ivf_info(name))
        eng.ivf_insert(name, "a", [0.0, 0.0, 0.0, 1.0])
        info = r.obs("info_after_reinsert", eng.ivf_info(name))
        cells = []
        cell = ""
        while True:
            cell = c.o.nextSubscript(False, "^IVF", name, "list", cell)
            if cell in (None, ""):
                break
            if c.o.isDefined("^IVF", name, "list", cell, "a"):
                cells.append(cell)
        r.obs("cells_holding_a", cells)
        res = r.obs("search_old_direction", eng.ivf_search(name, [1.0, 0.0, 0.0, 0.0], k=2, nprobe=8))
        r["oracle"] = "an id lives in at most one cell; indexed counts distinct ids"
        r["reproduced"] = len(cells) > 1 or int(info.get("indexed", 0)) > 2
        r["verdict"] = f"a in cells {cells}, indexed {info.get('indexed')}" if r["reproduced"] else "deduplicated"
    finally:
        try:
            eng.ivf_drop(name)
        except Exception:
            pass
        erase(eng, g)
        c.close()


def p0610_knn_vec_declared_model(r: Result):
    """F-0610: SQL kg_KNN_VEC answers no rows, without error, for a named graph whose vectors sit in a route with a
    declared model key. Oracle: KNOWN_ISSUES.md:702-714 (such a call raises) and 4.6.0 R265 (no silent empty)."""
    c, eng = engine()
    g = gname("kv")
    try:
        eng.create_node("v1", graph=g)
        eng.store_embedding("v1", [1.0, 0.0, 0.0, 0.0], graph=g, model_key="ba-model")
        r.obs("registry", _registry(c, g))
        try:
            rows = c.sql("SELECT node_id, score FROM Graph_KG.kg_KNN_VEC(?, ?, ?, ?)", json.dumps([1.0, 0, 0, 0]), 5, None, g)
            r.obs("kg_KNN_VEC", ["ok", rows])
        except Exception as e:
            r.obs("kg_KNN_VEC", ["error", str(e)[-250:]])
        r.obs("engine_search_nodes_by_vector", eng.search_nodes_by_vector([1.0, 0, 0, 0], k=5, graph=g, model_key="ba-model")
              if hasattr(eng, "search_nodes_by_vector") else "n/a")
        res = r["observed"]["kg_KNN_VEC"]
        r["oracle"] = "the SQL procedure answers the graph's vectors or raises; never an empty answer over held vectors"
        r["reproduced"] = res[0] == "ok" and res[1] == []
        r["verdict"] = "empty answer, no error" if r["reproduced"] else f"{res[0]}"
    finally:
        erase(eng, g)
        c.close()


def p0615_refused_batch_leaves_route(r: Result):
    """F-0615: store_embeddings refused for a missing node has already created (and committed) the route table and its
    registry row. Oracle: SYS-I3 (a refused write changes no store)."""
    c, eng = engine()
    g = gname("rb")
    try:
        r.obs("registry_before", _registry(c, g))
        try:
            eng.store_embeddings([{"node_id": "missing", "embedding": [0.1] * 6}], graph=g, model_key="ba-m6")
            r.obs("call", "accepted")
        except Exception as e:
            r.obs("call", f"refused {type(e).__name__}: {str(e)[:150]}")
        after = r.obs("registry_after", _registry(c, g))
        r["oracle"] = "a refused batch leaves the registry and routes as they were"
        r["reproduced"] = r["observed"]["call"].startswith("refused") and bool(after)
        r["verdict"] = "refused, yet a 6-wide route and registry row now exist" if r["reproduced"] else "unchanged"
    finally:
        erase(eng, g)
        r.obs("registry_after_erase", _registry(c, g))
        c.close()


def p0614_embed_nodes_refusal_counted(r: Result):
    """F-0614: embed_nodes against a route that records another width logs the EmbeddingIdentityConflict and returns
    {"embedded": 0, "errors": N} instead of raising. Oracle: ADR-0006 (spec 226 requires it to raise)."""
    c, eng = engine()
    g = gname("en")
    try:
        eng.create_node("p", graph=g)
        eng.create_node("q", graph=g)
        eng.store_embedding("p", [1.0, 0.0, 0.0, 0.0], graph=g, model_key="ba-w4")
        try:
            out = eng.embed_nodes(model=FakeModel(8), text_fn=lambda n, *a: str(n), graph=g, model_key="ba-w4",
                                  force=True)
            r.obs("embed_nodes", out)
        except Exception as e:
            r.obs("embed_nodes", f"raised {type(e).__name__}: {str(e)[:200]}")
        out = r["observed"]["embed_nodes"]
        r.obs("rows_in_route", c.sql("SELECT COUNT(*) FROM " + _route_table(c, g, "ba-w4") + " WHERE graph_id = ?", g)[0][0])
        conflict = r.obs("identity_conflict_logged", _log_has("EmbeddingIdentityConflict") or _log_has("identity"))
        r["oracle"] = "a recorded-identity conflict raises EmbeddingIdentityConflict"
        r["reproduced"] = isinstance(out, dict) and out.get("embedded") == 0 and out.get("errors", 0) > 0 and conflict
        r["verdict"] = ("identity conflict counted as errors; returned normally" if r["reproduced"]
                        else "raised, or failed for another reason (see log)")
    finally:
        erase(eng, g)
        c.close()


def p0616_selector_crosses_graphs_and_like(r: Result):
    """F-0616: embed_nodes(label=X, graph=g) also embeds g's node whose id carries X only in another graph; an
    exclude pattern holding "_" excludes nothing (LIKE without ESCAPE)."""
    c, eng = engine()
    g = gname("sl")
    lab = gname("X")
    try:
        eng.create_node("same", labels=[lab], graph=None)       # label X in the default graph only
        eng.create_node("same", labels=["Other"], graph=g)      # no X in g
        eng.create_node("x_1", labels=[lab], graph=g)
        eng.create_node("xy1", labels=[lab], graph=g)
        out1 = r.obs("label_run", eng.embed_nodes(model=FakeModel(4), text_fn=lambda n, *a: str(n), graph=g,
                                                  model_key="ba-sel", label=lab, exclude_pattern="x_*"))
        got = r.obs("embedded_in_g", sorted(x[0] for x in c.sql(
            "SELECT node_id FROM " + _route_table(c, g, "ba-sel") + " WHERE graph_id = ?", g)) if _route_table(c, g, "ba-sel") else [])
        r["oracle"] = "only g's nodes holding X in g are embedded; exclude x_* skips x_1"
        r["reproduced"] = "same" in got or "x_1" in got
        r["verdict"] = (("'same' embedded via another graph's label; " if "same" in got else "") +
                        ("x_1 not excluded" if "x_1" in got else "")) or "scoped"
    finally:
        erase(eng, g)
        try:
            eng.delete_node("same", graph=None)
        except Exception:
            pass
        c.close()


def _log_has(text):
    import logging
    for h in logging.getLogger().handlers:
        st = getattr(h, "stream", None)
        if st is not None and hasattr(st, "getvalue") and text in st.getvalue()[-20000:]:
            return True
    return False


def _route_table(c, g, mk):
    rows = c.sql("SELECT table_name FROM Graph_KG.embedding_registry WHERE graph_id = ? AND model_key = ?", g, mk)
    return f"Graph_KG.{rows[0][0]}" if rows else None


def pC0602_knn_vec_label_rows(r: Result):
    """New candidate (storage-order sub-lane note): SQL kg_KNN_VEC LEFT JOINs rdf_labels with no DISTINCT, so with no
    label filter a node with two labels fills two of the k places and pushes another node out (and kg_RRF_FUSE's vector
    leg passes no filter). Oracle: kg_KNN_VEC is a k-nearest-nodes search (one row per node)."""
    c, eng = engine()
    a, b = gname("kn1"), gname("kn2")
    try:
        eng.create_node(a, labels=["LA", "LB"])
        eng.create_node(b, labels=["LA"])
        eng.store_embedding(a, [1.0, 0.0, 0.0, 0.0])
        eng.store_embedding(b, [0.9, 0.1, 0.0, 0.0])
        q = json.dumps([1.0, 0.0, 0.0, 0.0])
        rows = r.obs("kg_KNN_VEC_k2", c.sql("SELECT node_id, score FROM Graph_KG.kg_KNN_VEC(?, ?, ?, ?)", q, 2, None, ""))
        ids = [x[0] for x in rows]
        r["oracle"] = "k nearest nodes: each node at most once; with k=2 both a and b answer"
        r["reproduced"] = ids.count(a) > 1 or (b not in ids)
        r["verdict"] = f"answer {ids}" + (" (a twice, b pushed out)" if r["reproduced"] else "")
    finally:
        for n in (a, b):
            try:
                eng.delete_node(n, graph=None)
            except Exception:
                pass
        c.close()


PROBES = {f.__name__: f for f in (pC0602_knn_vec_label_rows, p0604_queue_done_without_vector, p0606_erase_leaves_ivf, p0607_ivf_cosine_is_dot,
                                  p0608_ivf_insert_duplicates, p0610_knn_vec_declared_model,
                                  p0615_refused_batch_leaves_route, p0614_embed_nodes_refusal_counted,
                                  p0616_selector_crosses_graphs_and_like)}

if __name__ == "__main__":
    sys.exit(run("06", PROBES, sys.argv[1:]))
