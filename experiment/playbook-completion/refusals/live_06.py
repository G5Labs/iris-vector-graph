#!/usr/bin/env python3
"""Module 06 (vectors): live probes of the stated refusals (VEC kind X) in namespace AUDITE.

    bash experiment/playbook-completion/tools/locks.sh iris timeout 1500 \
        python experiment/playbook-completion/refusals/live_06.py [--out NAME] [case ...]

Each case triggers the refused condition through the product's real entry point (engine methods: set_embedding_identity,
store_embedding(s), initialize_schema, kg_KNN_VEC, search_nodes_by_vector, vector_search, embed_nodes,
enqueue_for_embedding, process_embed_queue, list_quarantine, the migrations, the index API; the server class
Graph.KG.EmbedQueue.ProcessBatch / Graph.KG.VecIndex.Create through the Native API) inside a journal window (rxlib):
it holds when the product refuses as the statement says and the journal shows no net change outside what the
statement itself says is written (the queue entry an embed-queue refusal marks failed). Setup (nodes, first vectors,
claimed identities, queue entries) runs outside the windows; every case starts from the product's own EraseAll/PurgeAll.
Queue entries this lane makes are removed with the product's own Graph.KG.EmbedQueue.SetResult + ClearDone (EraseAll
does not reach ^EmbedQueue). Embedders here are harness stubs (a Python object with encode/model_name that is never a
real model): no model is downloaded and nothing needs %Embedding/%AI. Scratch ids and graphs start with rx06.
Results: $RUN_DIR/refusals/06/<out>.json (default results.json).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rxlib import Lane, raises, returns, either, run_cases, engine, tlevel, open_caller_txn, rollback_all  # noqa: E402

from iris_vector_graph.embedding_identity import EmbeddingIdentity, identity_from_config  # noqa: E402
from iris_vector_graph.schema import GraphSchema  # noqa: E402

W = 4  # AUDITE's vector columns are declared VECTOR(DOUBLE, 4)


def vec(n, seed=0.1):
    return [round(seed + 0.01 * i, 4) for i in range(n)]


class Stub:
    """A harness embedder: answers encode() with fixed-width vectors; optionally names a model. Never a real model."""

    def __init__(self, width, model_name=None):
        self.width = width
        if model_name:
            self.model_name = model_name

    def encode(self, texts, **kw):
        import numpy as np
        if isinstance(texts, str):
            return np.array(vec(self.width, 0.2))
        return np.array([vec(self.width, 0.2 + 0.01 * i) for i in range(len(texts))])


def widths(L):
    cur = L.c.conn.cursor()
    try:
        return {t: GraphSchema.get_embedding_dimension(cur, "Graph_KG." + t)
                for t in ("kg_NodeEmbeddings", "kg_NodeEmbeddings_optimized", "kg_EdgeEmbeddings")}
    finally:
        cur.close()


def registry(L):
    return [list(r) for r in L.c.sql("SELECT table_name, graph_id, kind, mechanism, model_key, dimension, set_by "
                                    "FROM Graph_KG.embedding_registry ORDER BY table_name, graph_id")]


def rows_in(L, table, where="", *p):
    return int(L.c.sql(f"SELECT COUNT(*) FROM Graph_KG.{table} {where}", *p)[0][0])


def nodes(L, *ids, graph=None):
    for i in ids:
        L.eng.create_node(i, labels=["RX06"], properties={"name": i}, graph=graph)
    L.c.conn.commit()


def route_of(L, graph, model_key=None):
    r = L.eng.resolve_route(graph=graph, model_key=model_key)
    return None if r is None else r.table_name


def queue_cleanup(L, req_ids):
    """Remove this lane's queue entries with the product's own API (SetResult DONE, then ClearDone)."""
    for r in req_ids:
        try:
            L.c.call("Graph.KG.EmbedQueue", "SetResult", r, "DONE", "")
        except Exception:  # noqa: BLE001
            pass
    try:
        L.c.call("Graph.KG.EmbedQueue", "ClearDone")
    except Exception:  # noqa: BLE001
        pass
    L.c.conn.commit()


def entry(L, req_id):
    return json.loads(str(L.c.call("Graph.KG.EmbedQueue", "GetEntry", req_id)))


# ------------------------------------------------------------------------------------------------ identity (X1)
def c_x1_5(L):
    L.reset()
    L.refusal("VEC-X1.5", "set_embedding_identity with a blank model key -> ValueError",
              lambda: L.eng.set_embedding_identity(EmbeddingIdentity(mechanism="external", model_key="   ", dimension=W),
                                                   "kg_NodeEmbeddings"),
              raises("ValueError", match="model_key cannot be empty"), entry="engine.set_embedding_identity")
    u = identity_from_config(None)
    L.note("VEC-X1.5", "a writer with no model offers the undeclared identity (no model key)",
           mechanism=u.mechanism, model_key=u.model_key, is_unknown=u.is_unknown)


def c_x1_6(L):
    L.reset()
    L.refusal("VEC-X1.6", "set_embedding_identity with mechanism 'word2vec' -> ValueError",
              lambda: L.eng.set_embedding_identity(EmbeddingIdentity(mechanism="word2vec", model_key="rx06-m",
                                                                     dimension=W), "kg_NodeEmbeddings"),
              raises("ValueError", match="not one of"), entry="engine.set_embedding_identity")
    L.refusal("VEC-X1.6", "IRISGraphEngine path: identity_from_config(mechanism='word2vec') -> ValueError",
              lambda: identity_from_config("rx06-m", mechanism="word2vec"),
              raises("ValueError", match="not one of"), entry="embedding_identity.identity_from_config")


def c_x1_13(L):
    L.reset()
    nodes(L, "rx06:seed", "rx06:b1", "rx06:b2", graph="rx06g13")
    ea = engine(L.c, embedding_config="rx06-alpha")
    ea.store_embedding("rx06:seed", vec(W), graph="rx06g13")
    L.c.conn.commit()
    table = route_of(L, "rx06g13", "rx06-alpha")
    eb = engine(L.c, embedding_config="rx06-alpha")
    items = [{"node_id": n, "embedding": vec(W + 1, 0.3)} for n in ("rx06:b1", "rx06:b2")]
    L.refusal("VEC-X1.13", "store_embeddings batch at width 5 into a width-4 route -> EmbeddingIdentityConflict, "
              "names the graph, writes nothing",
              lambda: eb.store_embeddings(items, graph="rx06g13"),
              raises("EmbeddingIdentityConflict", match="rx06g13"),
              after=lambda: {"route": table, "rows_in_route": rows_in(L, table)},
              entry="engine.store_embeddings")
    # mechanism clash, same model name: sentence-transformers claim vs an IRIS embedding_config writer
    L.reset()
    nodes(L, "rx06:ma", "rx06:mb")
    est = engine(L.c, embedder=Stub(W, "rx06-shared"))
    est.store_embedding("rx06:ma", vec(W))
    L.c.conn.commit()
    table = route_of(L, "", "rx06-shared") or "?"
    ecfg = engine(L.c, embedding_config="rx06-shared")
    L.refusal("VEC-X1.13", "store_embedding by an embedding_config writer into a route claimed by sentence-transformers "
              "-> EmbeddingIdentityConflict, writes nothing",
              lambda: ecfg.store_embedding("rx06:mb", vec(W, 0.4)),
              raises("EmbeddingIdentityConflict", match="sentence-transformers"),
              after=lambda: {"registry": registry(L)}, entry="engine.store_embedding")


def c_x1_19(L):
    L.reset()
    L.eng.set_embedding_identity(EmbeddingIdentity("external", "rx06-m1", dimension=W), "kg_NodeEmbeddings")
    L.c.conn.commit()
    L.note("VEC-X1.19", "setup: kg_NodeEmbeddings claimed for rx06-m1", registry=registry(L))
    L.refusal("VEC-X1.19", "set_embedding_identity rx06-m2 on a row claimed for rx06-m1 -> EmbeddingIdentityConflict",
              lambda: L.eng.set_embedding_identity(EmbeddingIdentity("external", "rx06-m2", dimension=W),
                                                   "kg_NodeEmbeddings"),
              raises("EmbeddingIdentityConflict"), after=lambda: {"registry": registry(L)},
              entry="engine.set_embedding_identity")


def c_x1_21(L):
    L.reset()
    L.refusal("VEC-X1.21", "set_embedding_identity with the undeclared identity -> ValueError",
              lambda: L.eng.set_embedding_identity(EmbeddingIdentity(None, None, dimension=W), "kg_NodeEmbeddings"),
              raises("ValueError", match="requires a declared model"), entry="engine.set_embedding_identity")
    L.refusal("VEC-X1.21", "set_embedding_identity(None) -> ValueError",
              lambda: L.eng.set_embedding_identity(None, "kg_NodeEmbeddings"),
              raises("ValueError", match="requires a declared model"), entry="engine.set_embedding_identity")


def c_x1_22(L):
    L.reset()
    ident = EmbeddingIdentity("external", "rx06-m", dimension=W)
    L.refusal("VEC-X1.22", "set_embedding_identity on table 'nodes' -> ValueError",
              lambda: L.eng.set_embedding_identity(ident, "nodes"),
              raises("ValueError", match="not an embedding table"), entry="engine.set_embedding_identity")
    L.refusal("VEC-X1.22", "set_embedding_identity on an edge route name kg_eemb_<16 hex> -> ValueError",
              lambda: L.eng.set_embedding_identity(ident, "kg_eemb_0123456789abcdef"),
              raises("ValueError", match="not an embedding table"), entry="engine.set_embedding_identity")


def c_x1_29(L):
    L.reset()
    before = widths(L)
    e6 = engine(L.c, embedding_dimension=6)
    L.refusal("VEC-X1.29", "initialize_schema at width 6 over empty width-4 columns, no rewidth -> "
              "EmbeddingIdentityConflict before setup writes",
              lambda: e6.initialize_schema(auto_deploy_objectscript=False),
              raises("EmbeddingIdentityConflict", match="rewidth"),
              after=lambda: {"widths_before": before, "widths_after": widths(L)}, entry="engine.initialize_schema")
    nodes(L, "rx06:w1")
    L.eng.store_embedding("rx06:w1", vec(W))
    L.c.conn.commit()
    e6 = engine(L.c, embedding_dimension=6)
    L.refusal("VEC-X1.29", "initialize_schema(rewidth=True) at width 6 while kg_NodeEmbeddings holds a vector -> "
              "EmbeddingIdentityConflict before setup writes",
              lambda: e6.initialize_schema(auto_deploy_objectscript=False, rewidth=True),
              raises("EmbeddingIdentityConflict", match="holds"),
              after=lambda: {"widths_after": widths(L), "rows": rows_in(L, "kg_NodeEmbeddings")},
              entry="engine.initialize_schema")
    after = widths(L)
    if after != before:  # a refusal that did not hold must not leave AUDITE at another width for the other lanes
        L.reset()
        r = engine(L.c, embedding_dimension=W).initialize_schema(auto_deploy_objectscript=False, rewidth=True)
        L.note("VEC-X1.29", "RESTORE: widths changed; re-declared at 4 by the pin's initialize_schema(rewidth=True)",
               before=before, after=after, restored=widths(L), status=str(r)[:300])


# ------------------------------------------------------------------------------------------------ routes (X2)
def c_x2_8(L):
    L.reset()
    nodes(L, "rx06:t1", graph="rx06g28")
    lvl = open_caller_txn(L.c.conn, "INSERT INTO Graph_KG.nodes (node_id, graph_id) VALUES ('rx06:txn', 'rx06g28')")
    L.note("VEC-X2.8", "setup: caller transaction open", tlevel=lvl)
    L.refusal("VEC-X2.8", "store_embedding into an unrouted pair inside the caller's transaction -> "
              "CallerTransactionOpenError, no route made",
              lambda: L.eng.store_embedding("rx06:t1", vec(W), graph="rx06g28"),
              raises("CallerTransactionOpenError"), keep_txn=True, entry="engine.store_embedding")
    rollback_all(L.c.conn)
    L.note("VEC-X2.8", "after rollback: no route for (rx06g28, None)", route=route_of(L, "rx06g28"),
           registry=registry(L))


# ------------------------------------------------------------------------------------------------ writes (X3)
def c_x3_1(L):
    L.reset()
    nodes(L, "rx06:d1")                      # in the default graph only
    L.refusal("VEC-X3.1", "store_embedding for a node that exists only in another graph -> ValueError",
              lambda: L.eng.store_embedding("rx06:d1", vec(W), graph="rx06g31"),
              raises("ValueError", match="does not exist in graph"), entry="engine.store_embedding")
    L.refusal("VEC-X3.1", "store_embedding for a node in no graph -> ValueError",
              lambda: L.eng.store_embedding("rx06:absent", vec(W)),
              raises("ValueError", match="does not exist in graph"), entry="engine.store_embedding")


def c_x3_2(L):
    L.reset()
    nodes(L, "rx06:r1", "rx06:r2", graph="rx06g32")
    L.eng.store_embedding("rx06:r1", vec(W), graph="rx06g32")
    L.c.conn.commit()
    table = route_of(L, "rx06g32")
    L.refusal("VEC-X3.2", "store_embedding 5-wide into graph rx06g32's 4-wide route -> refused, error names the graph",
              lambda: L.eng.store_embedding("rx06:r2", vec(W + 1), graph="rx06g32"),
              raises("ValueError", match="rx06g32"), after=lambda: {"route": table, "rows": rows_in(L, table)},
              entry="engine.store_embedding")


def c_x3_7(L):
    L.reset()
    nodes(L, "rx06:m1", "rx06:m2", graph="rx06g37")
    items = [{"node_id": "rx06:m1", "embedding": vec(W)}, {"node_id": "rx06:m2", "embedding": vec(W + 1)}]
    L.refusal("VEC-X3.7", "store_embeddings with widths 4 and 5 -> ValueError before anything (no route made)",
              lambda: L.eng.store_embeddings(items, graph="rx06g37"),
              raises("ValueError", match="holds widths"), after=lambda: {"registry": registry(L)},
              entry="engine.store_embeddings")


def c_x3_9(L):
    L.reset()
    nodes(L, "rx06:p1", graph="rx06g39")
    items = [{"node_id": "rx06:p1", "embedding": vec(W)}, {"node_id": "rx06:missing", "embedding": vec(W)}]
    L.refusal("VEC-X3.9", "store_embeddings into an unrouted pair with one missing node -> refused, no new route left",
              lambda: L.eng.store_embeddings(items, graph="rx06g39"),
              raises("ValueError", match="does not exist"), after=lambda: {"registry": registry(L)},
              entry="engine.store_embeddings")


def c_x3_16(L):
    from iris_vector_graph.vector_utils import VectorOptimizer
    L.reset()
    nodes(L, "rx06:o1")
    L.eng.store_embedding("rx06:o1", vec(W))   # the default pair: kg_NodeEmbeddings
    L.c.conn.commit()
    L.eng.set_embedding_identity(EmbeddingIdentity("external", "rx06-src", dimension=W), "kg_NodeEmbeddings")
    L.eng.set_embedding_identity(EmbeddingIdentity("external", "rx06-dst", dimension=W), "kg_NodeEmbeddings_optimized")
    L.c.conn.commit()
    L.note("VEC-X3.16", "setup: source claimed rx06-src, target claimed rx06-dst", registry=registry(L),
           source_rows=rows_in(L, "kg_NodeEmbeddings"))
    L.refusal("VEC-X3.16", "VectorOptimizer.migrate_to_optimized copies rx06-src vectors into a table claimed for "
              "rx06-dst -> refused by the identity check",
              lambda: VectorOptimizer(L.c.conn).migrate_to_optimized(),
              either(raises("EmbeddingIdentityConflict"),
                     returns(lambda r: isinstance(r, dict) and not r.get("success") and not r.get("migrated")
                             and "identity" in str(r.get("reason", "")).lower(),
                             "success False for the identity clash, nothing migrated")),
              after=lambda: {"target_rows": rows_in(L, "kg_NodeEmbeddings_optimized")},
              entry="vector_utils.VectorOptimizer.migrate_to_optimized")
    L.c.conn.commit()


# ------------------------------------------------------------------------------------------------ search (X5)
def c_x5_5(L):
    L.reset()
    nodes(L, "rx06:q1", graph="rx06g55")
    L.eng.store_embedding("rx06:q1", vec(W), graph="rx06g55")
    L.c.conn.commit()
    L.refusal("VEC-X5.5", "kg_KNN_VEC with a 5-wide query on a 4-wide route -> ValueError naming both widths",
              lambda: L.eng.kg_KNN_VEC(json.dumps(vec(W + 1)), k=3, graph="rx06g55"),
              raises("ValueError", match=r"5 dimensions.*4-dimensional"), entry="engine.kg_KNN_VEC")
    L.refusal("VEC-X5.5", "search_nodes_by_vector with a 5-wide query on a 4-wide route -> ValueError",
              lambda: L.eng.search_nodes_by_vector(vec(W + 1), k=3, graph="rx06g55"),
              raises("ValueError", match=r"5 dimensions.*4-dimensional"), entry="engine.search_nodes_by_vector")


def c_x5_11(L):
    L.reset()
    nodes(L, "rx06:i1", graph="rx06g511")
    L.eng.store_embedding("rx06:i1", vec(W), graph="rx06g511")
    L.c.conn.commit()
    e = engine(L.c)
    e._native_vec_available = False   # SIMULATED: a server without VECTOR_COSINE (this IRIS has it)
    L.refusal("VEC-X5.11", "SIMULATED no-VECTOR_COSINE: search_nodes_by_vector naming a graph -> ValueError",
              lambda: e.search_nodes_by_vector(vec(W), k=3, graph="rx06g511"),
              raises("ValueError", match="IVF index"), entry="engine.search_nodes_by_vector (native probe forced off)")
    L.refusal("VEC-X5.11", "SIMULATED no-VECTOR_COSINE: search_nodes_by_vector naming a model -> ValueError",
              lambda: e.search_nodes_by_vector(vec(W), k=3, model_key="rx06-m"),
              raises("ValueError", match="IVF index"), entry="engine.search_nodes_by_vector (native probe forced off)")
    L.note("VEC-X5.11", "this server's own native probe", native_vec=engine(L.c)._probe_native_vec())


def c_x5_15(L):
    L.reset()
    nodes(L, "rx06:s1", "rx06:s2", graph="rx06g515")
    L.eng.store_embedding("rx06:s1", vec(W), graph="rx06g515")
    L.eng.create_edge("rx06:s1", "RX", "rx06:s2", graph="rx06g515")
    L.eng.store_edge_embedding("rx06:s1", "RX", "rx06:s2", vec(W), graph="rx06g515")
    L.c.conn.commit()
    ntab = route_of(L, "rx06g515")
    etab = L.eng.resolve_route(graph="rx06g515", kind="edge")
    etab = etab.table_name if etab is not None else None
    L.note("VEC-X5.15", "setup: routes", node_route=ntab, edge_route=etab, registry=registry(L))
    L.refusal("VEC-X5.15", "vector_search on a node route (kg_emb_) with no graph -> ValueError",
              lambda: L.eng.vector_search(f"Graph_KG.{ntab}", "emb", vec(W), top_k=3, id_col="node_id"),
              raises("ValueError", match="routed embedding table"), entry="engine.vector_search")
    L.refusal("VEC-X5.15", "vector_search on an edge route (kg_eemb_) with no graph -> ValueError",
              lambda: L.eng.vector_search(f"Graph_KG.{etab}", "emb", vec(W), top_k=3, id_col="s"),
              raises("ValueError", match="routed embedding table"), entry="engine.vector_search")


# ------------------------------------------------------------------------------------------------ bulk embed (X6)
def c_x6_7(L):
    L.reset()
    nodes(L, "rx06:e1", "rx06:e2", graph="rx06g67")
    L.eng.store_embedding("rx06:e1", vec(W), graph="rx06g67")      # route (rx06g67, undeclared) at width 4
    L.c.conn.commit()
    e5 = engine(L.c, embedder=Stub(W + 1))                         # undeclared model, 5-wide vectors
    L.refusal("VEC-X6.7", "embed_nodes whose batch clashes with the route's width -> EmbeddingIdentityConflict raised",
              lambda: e5.embed_nodes(graph="rx06g67", force=True),
              raises("EmbeddingIdentityConflict"), entry="engine.embed_nodes")


# ------------------------------------------------------------------------------------------------ queue (X7)
def _foreign_pending(L):
    return int(str(L.c.call("Graph.KG.EmbedQueue", "PendingCount")))


def c_x7_2(L):
    L.reset()
    nodes(L, "rx06:qn", graph="rx06qa")
    nodes(L, "rx06:qn", graph="rx06qb")
    n1 = L.eng.enqueue_for_embedding(node_ids=["rx06:qn"], graph="rx06qa")
    L.c.conn.commit()
    L.note("VEC-X7.2", "setup: queued for rx06qa", count=n1, entry=entry(L, "rx06:qn"))
    L.refusal("VEC-X7.2", "enqueue the same node for rx06qb while pending for rx06qa -> count 0, entry unchanged",
              lambda: L.eng.enqueue_for_embedding(node_ids=["rx06:qn"], graph="rx06qb"),
              returns(lambda r: r == 0, "0 enqueued"), after=lambda: {"entry": entry(L, "rx06:qn")},
              entry="engine.enqueue_for_embedding -> Graph.KG.EmbedQueue.BulkEnqueue")
    queue_cleanup(L, ["rx06:qn"])


def c_x7_5(L):
    L.reset()
    nodes(L, "rx06:qc")
    L.eng.set_embedding_identity(EmbeddingIdentity("external", "rx06-qm", dimension=W), "kg_NodeEmbeddings")
    L.c.conn.commit()
    L.refusal("VEC-X7.5", "enqueue_for_embedding with a config the kg_NodeEmbeddings row refuses -> "
              "EmbeddingIdentityConflict, nothing queued",
              lambda: L.eng.enqueue_for_embedding(node_ids=["rx06:qc"], embedding_config="rx06-other"),
              raises("EmbeddingIdentityConflict"), after=lambda: {"entry": entry(L, "rx06:qc")},
              entry="engine.enqueue_for_embedding")
    queue_cleanup(L, ["rx06:qc"])


def c_x7_10(L):
    L.reset()
    if _foreign_pending(L):
        L.note("VEC-X7.10", "skipped: foreign PENDING entries in ^EmbedQueue", pending=_foreign_pending(L))
        return
    nodes(L, "rx06:w1", "rx06:w2")
    L.eng.enqueue_for_embedding(node_ids=["rx06:w1"], embedding_config="rx06-other")
    L.eng.enqueue_for_embedding(node_ids=["rx06:w2"])
    L.c.conn.commit()
    worker = engine(L.c, embedder=Stub(W, "rx06-worker"))

    def act():
        r = worker.process_embed_queue(batch_size=10)
        return {"result": r, "w1": entry(L, "rx06:w1"), "w2": entry(L, "rx06:w2"),
                "w1_vectors": sum(rows_in(L, t, "WHERE node_id = ?", "rx06:w1")
                                  for t in ["kg_NodeEmbeddings"] + [x[0] for x in registry(L) if x[0].startswith("kg_emb_")])}

    def ok(d):
        return (d["w1"]["status"] == "ERROR" and "does not produce" in d["w1"]["error"]
                and d["w2"]["status"] == "DONE" and d["w1_vectors"] == 0
                and d["result"].get("processed") == 1 and d["result"].get("errors") == 1)
    L.refusal("VEC-X7.10", "process_embed_queue: entry for another model marked ERROR with the reason, the other "
              "entry DONE (writes by design: queue status, the honoured vector and its route)",
              act, returns(ok, "w1 ERROR with reason, w2 DONE, no vector for w1"),
              allowed=[r".*"], entry="engine.process_embed_queue")
    queue_cleanup(L, ["rx06:w1", "rx06:w2"])


def c_x7_16(L):
    L.reset()
    if _foreign_pending(L):
        L.note("VEC-X7.16", "skipped: foreign PENDING entries in ^EmbedQueue", pending=_foreign_pending(L))
        return
    nodes(L, "rx06:sx")                      # default graph only
    nodes(L, "rx06:sy", graph="rx06qy")      # in rx06qy, which has no route
    L.eng.enqueue_for_embedding(node_ids=["rx06:sx"], graph="rx06qx")
    L.eng.enqueue_for_embedding(node_ids=["rx06:sy"], graph="rx06qy")
    L.c.conn.commit()

    def act():
        r = json.loads(str(L.c.call("Graph.KG.EmbedQueue", "ProcessBatch", 10, 30)))
        return {"result": r, "sx": entry(L, "rx06:sx"), "sy": entry(L, "rx06:sy")}

    def ok(d):
        return (d["sx"]["status"] == "ERROR" and "is not in graph" in d["sx"]["error"]
                and d["sy"]["status"] == "ERROR" and "no embedding route" in d["sy"]["error"]
                and d["result"].get("errors") == 2 and d["result"].get("processed") == 0)
    L.refusal("VEC-X7.16", "server ProcessBatch: node not in its graph, and a graph with no route -> both ERROR, "
              "no vector written (only the queue entries change)",
              act, returns(ok, "both ERROR with their reasons"), allowed=[r"global:\^EmbedQueue"],
              entry="Graph.KG.EmbedQueue.ProcessBatch (Native API)")
    queue_cleanup(L, ["rx06:sx", "rx06:sy"])


# ------------------------------------------------------------------------------------------------ quarantine (X9)
def c_x9_2(L):
    L.reset()
    L.refusal("VEC-X9.2", "list_quarantine(reason='rx06-bogus') -> ValueError, not []",
              lambda: L.eng.list_quarantine(reason="rx06-bogus"),
              raises("ValueError", match="not a quarantine reason"), entry="engine.list_quarantine")


# ------------------------------------------------------------------------------------------------ migrations (X10)
def c_x10_9(L):
    from iris_vector_graph.migrations.graph_scoped_embeddings import migrate_to_graph_scoped_embeddings
    from iris_vector_graph.migrations.docs_and_edge_vectors import migrate_docs_and_edge_vectors
    from iris_vector_graph.migrations.kg_node_stores import rekey_kg_node_stores
    L.reset()
    for name, fn in (("migrate_to_graph_scoped_embeddings", lambda: migrate_to_graph_scoped_embeddings(L.c.conn)),
                     ("migrate_docs_and_edge_vectors", lambda: migrate_docs_and_edge_vectors(L.c.conn, W)),
                     ("rekey_kg_node_stores", lambda: rekey_kg_node_stores(L.c.conn))):
        lvl = open_caller_txn(L.c.conn, "INSERT INTO Graph_KG.nodes (node_id) VALUES ('rx06:mtxn')")
        L.note("VEC-X10.9", f"setup: caller transaction open before {name}", tlevel=lvl)
        L.refusal("VEC-X10.9", f"{name} inside the caller's transaction -> CallerTransactionOpenError",
                  fn, raises("CallerTransactionOpenError"), keep_txn=True, entry=f"migrations.{name}")
        rollback_all(L.c.conn)


# ------------------------------------------------------------------------------------------------ indexes (X11)
def c_x11_1(L):
    L.reset()
    L.refusal("VEC-X11.1", "engine.index('rx06-nosuch') -> IndexNotFoundError listing the known names",
              lambda: L.eng.index("rx06-nosuch"),
              raises("IndexNotFoundError", match="Known indexes|No indexes exist yet"), entry="engine.index")


def c_x11_3(L):
    from iris_vector_graph.index_config import NeighborhoodVectorConfig
    L.reset()
    h = L.eng.create_index(NeighborhoodVectorConfig(name="rx06nb"))
    L.refusal("VEC-X11.3", "neighborhood_vector index build -> NotImplementedError",
              lambda: h.build(), raises("NotImplementedError"), entry="engine.create_index(...).build")
    L.refusal("VEC-X11.3", "neighborhood_vector index search -> NotImplementedError",
              lambda: h.search(vec(W), k=3), raises("NotImplementedError", "IndexNotBuiltError"),
              entry="engine.create_index(...).search")


def c_x11_7(L):
    L.reset()
    L.refusal("VEC-X11.7", "ivf_build for a pair with no route -> ValueError",
              lambda: L.eng.ivf_build("rx06ivf", nlist=2, graph="rx06g117"),
              raises("ValueError", match="no embedding table is routed"), entry="engine.ivf_build")
    L.eng.resolve_route(graph="rx06g117e", create=True, dimension=W)   # a route with no vectors
    L.c.conn.commit()
    L.refusal("VEC-X11.7", "ivf_build for a route with no vectors -> ValueError",
              lambda: L.eng.ivf_build("rx06ivf", nlist=2, graph="rx06g117e"),
              raises("ValueError", match="no vectors found"), entry="engine.ivf_build")


def c_x11_13(L):
    L.reset()
    L.refusal("VEC-X11.13", "ivf_insert into an IVF index that does not exist -> ValueError",
              lambda: L.eng.ivf_insert("rx06-noivf", "rx06:x", vec(W)),
              raises("ValueError", match="not found"), entry="engine.ivf_insert")


def c_x11_20(L):
    L.reset()
    L.refusal("VEC-X11.20", "vec_create_index(metric='mahalanobis') -> ValueError, nothing written",
              lambda: L.eng.vec_create_index("rx06vec", dim=W, metric="mahalanobis"),
              raises("ValueError", match="metric must be one of"), entry="engine.vec_create_index")
    L.refusal("VEC-X11.20", "server Graph.KG.VecIndex.Create(metric='mahalanobis') -> throws, nothing written",
              lambda: L.c.call("Graph.KG.VecIndex", "Create", "rx06vec2", W, "mahalanobis", 4, 50),
              raises("Exception", match="metric must be one of"), entry="Graph.KG.VecIndex.Create (Native API)")


def c_x11_25(L):
    L.reset()
    docs = [{"id": "rx06:d1", "tokens": [vec(W), vec(W + 1)]}]
    L.refusal("VEC-X11.25", "plaid_build with one token of another width -> ValueError, nothing written",
              lambda: L.eng.plaid_build("rx06plaid", docs), raises("ValueError", match="not dim="),
              entry="engine.plaid_build")


CASES = [("x1_5", c_x1_5), ("x1_6", c_x1_6), ("x1_13", c_x1_13), ("x1_19", c_x1_19), ("x1_21", c_x1_21),
         ("x1_22", c_x1_22), ("x1_29", c_x1_29), ("x2_8", c_x2_8), ("x3_1", c_x3_1), ("x3_2", c_x3_2),
         ("x3_7", c_x3_7), ("x3_9", c_x3_9), ("x3_16", c_x3_16), ("x5_5", c_x5_5), ("x5_11", c_x5_11),
         ("x5_15", c_x5_15), ("x6_7", c_x6_7), ("x7_2", c_x7_2), ("x7_5", c_x7_5), ("x7_10", c_x7_10),
         ("x7_16", c_x7_16), ("x9_2", c_x9_2), ("x10_9", c_x10_9), ("x11_1", c_x11_1), ("x11_3", c_x11_3),
         ("x11_7", c_x11_7), ("x11_13", c_x11_13), ("x11_20", c_x11_20), ("x11_25", c_x11_25)]


def main():
    args = sys.argv[1:]
    out = "results.json"
    if args[:1] == ["--out"]:
        out, args = args[1], args[2:]
    only = args or None
    with Lane("06") as L:
        L.reset()
        L.control()
        L.note("(setup)", "AUDITE vector widths at start", widths=widths(L))
        run_cases(L, CASES, only)
        L.reset()
        L.note("(setup)", "AUDITE vector widths at end", widths=widths(L),
               pending=int(str(L.c.call("Graph.KG.EmbedQueue", "PendingCount"))))
        L.save(out if not only or out != "results.json" else "results-partial.json")


if __name__ == "__main__":
    main()
