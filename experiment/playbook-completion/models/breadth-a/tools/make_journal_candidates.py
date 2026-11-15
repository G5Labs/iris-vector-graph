#!/usr/bin/env python3
"""Writer entry points best suited for journal validation (traces/journal.py), with concrete invocations.

Context assumed by every `invoke` snippet:
    import os, json; from iris_conn import Conn          # experiment/playbook-completion/tools
    from iris_vector_graph.engine import IRISGraphEngine
    c = Conn("AUDITA"); o = c.o                          # one server process: c.pid
    eng = IRISGraphEngine(c.conn, namespace="AUDITA", embedding_dimension=4)   # _iris_obj() == c's process
    G = "jv_<run-tag>"                                   # a fresh named graph per candidate
Signatures were checked against the pin (path:line in `signature`). `expect` is what the declared footprint
(footprints/NN.json) predicts the journal shows; `discriminates` names the claim or finding the observation tests.
"""
import json
from pathlib import Path

C = []


def add(**kw):
    C.append(kw)


add(id="J01", module="03", footprint="py:IRISGraphEngine.create_node",
    signature="iris_vector_graph/_engine/nodes_edges.py:968",
    invoke='eng.create_node("jv_n1", labels=["L"], properties={"k": "v"}, graph=G)',
    expect={"stores": ["sql:Graph_KG.nodes", "sql:Graph_KG.rdf_labels", "sql:Graph_KG.rdf_props", "global:^KG(\"label\")",
                       "global:^KG(\"__version\")", "global:^IRIS.IF.* (iFind)"],
            "transactions": "one outermost transaction (nested levels from WriteTxn) under c.pid; row-id counters, "
                            "^KG(\"__version\") ($Increment) and iFind word globals journaled outside it",
            "pids": "c.pid only"},
    discriminates="atomicity claim nodes_edges.py:975; undeclared writes")
add(id="J02", module="03", footprint="py:IRISGraphEngine.create_edge",
    signature="iris_vector_graph/_engine/nodes_edges.py:1151",
    invoke='eng.create_edge("jv_a", "R", "jv_b", weight=2.0, graph=G)',
    expect={"stores": ["sql:Graph_KG.nodes (2 endpoints)", "sql:Graph_KG.rdf_edges", "global:^KG(\"out\")",
                       "global:^KG(\"in\")", "global:^KG(\"gen\")", "global:^KG(\"__version\")"],
            "transactions": "one transaction under c.pid containing nodes, rdf_edges and ^KG(\"out\"/\"in\") (row hook "
                            "inside the row's transaction, ADR-0008); gen/__version as $Increment",
            "pids": "c.pid only"},
    discriminates="ROW_HOOK in the row's transaction (P-0407); atomicity nodes_edges.py:1181")
add(id="J03", module="03", footprint="py:IRISGraphEngine.store_edge",
    signature="iris_vector_graph/_engine/nodes_edges.py:2532",
    invoke='eng.create_edge_temporal("jv_s", "T", "jv_t", timestamp=1700000000, graph=G); '
           'eng.store_edge("jv_s", "T", "jv_t", qualifiers={"w": 1}, graph=G)',
    expect={"stores": ["store_edge part: sql:Graph_KG.nodes (endpoint re-insert attempts) only; NO rdf_edges UPDATE"],
            "transactions": "one transaction, duplicate swallowed", "pids": "c.pid"},
    discriminates="F-0304: no adoption UPDATE of the marked row's qualifiers (compare create_edge, which issues one)")
add(id="J04", module="03", footprint="py:IRISGraphEngine.delete_edge",
    signature="iris_vector_graph/_engine/nodes_edges.py:1382",
    invoke='eng.create_edge("jv_a", "R", "jv_b", graph=G); m = mark(); eng.delete_edge("jv_a", "R", "jv_b", graph=G)',
    expect={"stores": ["sql:Graph_KG.rdf_edges (DELETE)", "global:^KG(\"out\")/(\"in\") KILL",
                       "global:^KG(\"gen\")", "global:^KG(\"__version\")"],
            "absent": ["global:^IVG.Ledger(\"stmt\")", "global:^IVG.Ledger(\"tuple\")"],
            "transactions": "one transaction under c.pid", "pids": "c.pid"},
    discriminates="F-0303 (run once with the ledger enabled and a ledger-created edge: the stmt/tuple entries are "
                  "not killed)")
add(id="J05", module="03", footprint="py:IRISGraphEngine.bulk_create_nodes",
    signature="iris_vector_graph/_engine/nodes_edges.py:1648",
    invoke='eng.bulk_create_nodes([{"id": f"jv_b{i}", "labels": ["B"]} for i in range(2500)], disable_indexes=False)',
    expect={"stores": ["sql:Graph_KG.nodes", "sql:Graph_KG.rdf_labels", "sql:Graph_KG.rdf_props", "^KG(\"label\")"],
            "transactions": "3 separate committed transactions (one per 1,000-node chunk, EdgeScan.cls:352/424)",
            "pids": "c.pid for this engine; repeat with eng2 = IRISGraphEngine.from_connect(hostname='127.0.0.1', "
                    "port=int(os.environ['IVG_PORT']), namespace='AUDITA', username='_SYSTEM', password='SYS', "
                    "embedding_dimension=4) (after Conn's identity check): the chunks then commit under a pid other "
                    "than eng2's cursor process"},
    discriminates="F-0305 (non-atomic multi-chunk bulk write; claim docs/USER_GUIDE.md:238-241). Nodes carry no "
                  "'graph' key, so the server loader path is taken; they land in the default graph: use unique ids "
                  "and erase them after")
add(id="J06", module="03", footprint="py:IRISGraphEngine.bulk_ingest_edges",
    signature="iris_vector_graph/_engine/nodes_edges.py:2019",
    invoke='eng.bulk_ingest_edges([{"s": f"jv_e{i}", "o": f"jv_e{i+1}"} for i in range(1500)], predicate="JV", '
           'auto_sync=False)',
    expect={"stores": ["sql:Graph_KG.nodes (default graph)", "sql:Graph_KG.rdf_edges", "^KG(\"out\"/\"in\"/\"gen\")"],
            "transactions": "2 committed transactions (1,000 + 500), not one", "pids": "as J05"},
    discriminates="F-0305/F-0307 (the default graph is written: clean up with delete_node/erase of the jv_e* ids)")
add(id="J07", module="03", footprint="py:iris_vector_graph.bulk_loader.BulkLoader.load_edges",
    signature="iris_vector_graph/bulk_loader.py:56, 380",
    invoke='from iris_vector_graph.bulk_loader import BulkLoader; bl = BulkLoader(c.conn, graph=G, batch_size=100); '
           'bl.load_nodes([(f"jv_l{i}", {}) for i in range(3)]); m = mark(); '
           'bl.load_edges([("jv_l0", "LL", "jv_l1", None), ("jv_l1", "LL", "jv_l2", None)])',
    expect={"stores": ["sql:Graph_KG.rdf_edges data global only (no index nodes)"],
            "absent": ["global:^KG(\"out\")", "global:^KG(\"in\")"],
            "transactions": "commit per batch", "pids": "c.pid"},
    discriminates="%NOINDEX skips the functional index: no row hook writes ^KG (footprint correction); then "
                  "bl.rebuild_all_indices() shows AdjIndex.PurgeIndex = Adjacency.RemoveAll (KILL ^KG(\"out\") for "
                  "EVERY graph) + refill: run only on AUDITA, it rebuilds the namespace's adjacency")
add(id="J08", module="02", footprint="py:IRISGraphEngine.set_multigraph",
    signature="iris_vector_graph/_engine/admin.py:893",
    invoke='eng.set_multigraph(G, True); m = mark(); eng.set_multigraph(G, False)',
    expect={"stores": ["global:^IVG.GraphMode (KILL)"], "transactions": "no transaction (auto)",
            "locks": "none observable", "pids": "c.pid"},
    discriminates="F-0207: the kill is a lone non-transactional record after a read-only ParallelCount")
add(id="J09", module="04", footprint="cls:Graph.KG.Adjacency.PutShadow",
    signature="iris_src/src/Graph/KG/Adjacency.cls:121",
    invoke='o.classMethodValue("Graph.KG.Adjacency", "PutShadow", G, "jv_p", "W", "jv_q", "1.0"); m = mark(); '
           'o.classMethodValue("Graph.KG.Adjacency", "PutShadow", G, "jv_p", "W", "jv_q", "5.0")',
    expect={"stores": ["global:^KG(\"out\")", "global:^KG(\"in\")"], "absent": ["global:^KG(\"gen\")",
            "global:^KG(\"__version\")"], "transactions": "none", "pids": "c.pid"},
    discriminates="F-0405 (weight refresh moves no token). Writes ^KG without a row: remove with "
                  "o.classMethodValue('Graph.KG.Adjacency','Remove',G,'jv_p','W','jv_q')")
add(id="J10", module="04", footprint="cls:Graph.KG.Adjacency.Reweight",
    signature="iris_src/src/Graph/KG/Adjacency.cls:328",
    invoke='eng.create_edge("jv_r", "RW", "jv_s2", graph=G); m = mark(); '
           'o.classMethodValue("Graph.KG.Adjacency", "Reweight", G, "jv_r", "RW", "jv_s2", "3.0")',
    expect={"stores": ["global:^KG(\"out\")", "global:^KG(\"in\")", "global:^KG(\"__version\")"],
            "absent": ["global:^KG(\"gen\")"], "locks": "no ^IVG.AdjW", "pids": "c.pid"},
    discriminates="F-0407")
add(id="J11", module="04", footprint="cls:Graph.KG.Adj.Degree",
    signature="iris_src/src/Graph/KG/Adj.cls:52",
    invoke='eng.create_edge("jv_d", "D", "jv_e", graph=G); o.kill("^KG", "degc", G, "jv_d"); m = mark(); '
           'o.classMethodValue("Graph.KG.Adj", "Degree", G, "jv_d", "")',
    expect={"stores": ["global:^KG(\"degc\") SET $ListBuild(gen, 1)"], "transactions": "none",
            "pids": "c.pid"},
    discriminates="reader that writes: the cache store is the only write (ADR-0012)")
add(id="J12", module="04", footprint="py:IRISGraphEngine.sync",
    signature="iris_vector_graph/_engine/schema.py:2859",
    invoke='eng.sync()',
    expect={"stores": ["^KG(\"out\"/\"in\"/\"gen\"/\"degc\"/\"degw\") for EVERY graph", "^KG(\"prop\")", "^NKG",
                       "^KG(\"deg2p\")"],
            "transactions": "BuildKG: one transaction (or pieces of 50,000 rows), then BuildNKG/Build2HopStats in "
                            "their own", "pids": "c.pid (createIRIS on the engine's connection)"},
    discriminates="F-0409 precondition (which process); heavy on a full namespace: AUDITA only, run under "
                  "locks.sh iris if timing matters")
add(id="J13", module="05", footprint="py:IRISGraphEngine.create_edge_temporal",
    signature="iris_vector_graph/_engine/temporal.py:246",
    invoke='eng.create_edge_temporal("jv_ta", "TT", "jv_tb", timestamp=1700000000, weight=2.0, graph=G)',
    expect={"stores": ["^KG(\"tout\"/\"tin\"/\"bucket\"/\"tagg\"/\"tlast\"...)", "sql:Graph_KG.rdf_edges (marked row "
                       "via AssertTemporalRow)", "sql:Graph_KG.nodes (endpoints)", "^KG(\"out\"/\"in\") via row hook"],
            "transactions": "^KG temporal sets journaled OUTSIDE any transaction (no TSTART in InsertEdge/WriteStores); "
                            "the SQL row inserts as their own statements", "pids": "c.pid"},
    discriminates="non-atomic temporal write (new candidate in footprints/05.json); F-0503 endpoint nodes")
add(id="J14", module="05", footprint="py:IRISGraphEngine.create_edge_temporal",
    signature="iris_vector_graph/_engine/temporal.py:246",
    invoke='eng.create_edge_temporal("jv_u", "TU", "jv_v", timestamp=1700000100, weight=1.0, graph=G); m = mark(); '
           'eng.create_edge_temporal("jv_u", "TU", "jv_v", timestamp=1700000100, weight=5.0, graph=G, mode="update")',
    expect={"stores": ["^KG(\"tout\") SET", "^KG(\"bucket\") $Increment (count 2)", "^KG(\"tagg\") count/sum $Increment"],
            "pids": "c.pid"},
    discriminates="F-0501 (update counts the edge again in the bucket aggregate)")
add(id="J15", module="05", footprint="py:IRISGraphEngine.delete_edge_temporal",
    signature="iris_vector_graph/_engine/temporal.py:334",
    invoke='eng.create_edge("jv_x", "TX", "jv_y", qualifiers={"temporal": 1}, graph=G); '
           'eng.create_edge_temporal("jv_x", "TX", "jv_y", timestamp=1700000200, graph=G); m = mark(); '
           'eng.delete_edge_temporal("jv_x", "TX", "jv_y", 1700000200, graph=G)',
    expect={"stores": ["^KG(\"tout\"/\"tin\") KILL", "sql:Graph_KG.rdf_edges DELETE of the explicit row"],
            "pids": "c.pid"},
    discriminates="F-0505 (IsTemporalMarked treats temporal: 1 as a mark)")
add(id="J16", module="05", footprint="cls:Graph.KG.TemporalIndex.Purge",
    signature="iris_src/src/Graph/KG/TemporalIndex.cls:808",
    invoke='eng.create_edge_temporal("jv_pa", "TP", "jv_pb", timestamp=1700000300, graph=G); m = mark(); '
           'o.classMethodVoid("Graph.KG.TemporalIndex", "Purge")',
    expect={"stores": ["^KG(\"tout\"/\"tin\"/\"bucket\"/\"tagg\"/\"edgeprop\"/\"tlast\") KILL (all graphs)"],
            "absent": ["sql:Graph_KG.rdf_edges", "^KG(\"out\")"], "transactions": "none", "pids": "c.pid"},
    discriminates="F-0507. DESTRUCTIVE for every graph's temporal data in AUDITA: run last or alone")
add(id="J17", module="06", footprint="py:IRISGraphEngine.store_embedding",
    signature="iris_vector_graph/_engine/embeddings.py:942",
    invoke='eng.create_node("jv_v1", graph=G); m = mark(); eng.store_embedding("jv_v1", [0.1, 0.2, 0.3, 0.4], graph=G)',
    expect={"stores": ["route table data (Graph_KG.kg_NodeEmbeddings for graph '' or a kg_emb_<hash> route)",
                       "first write of a pair: CREATE TABLE (catalog globals ^oddDEF/^rINDEXSQL are system and "
                       "filtered unless keep_system=True), sql:Graph_KG.embedding_registry INSERT"],
            "transactions": "route creation committed on its own; then DELETE+INSERT in one transaction",
            "pids": "c.pid"},
    discriminates="atomicity claim embeddings.py:1003")
add(id="J18", module="06", footprint="py:IRISGraphEngine.store_embeddings",
    signature="iris_vector_graph/_engine/embeddings.py:1028",
    invoke='m = mark(); eng.store_embeddings([{"node_id": "jv_missing", "embedding": [0.1, 0.2, 0.3, 0.4]}], '
           'graph=G + "_fresh", model_key="jv-model")  # expected to raise for the missing node',
    expect={"stores": ["sql:Graph_KG.embedding_registry INSERT and a new kg_emb_<hash> table committed BEFORE the "
                       "refusal"], "pids": "c.pid"},
    discriminates="F-0615 (a refused batch leaves a route)")
add(id="J19", module="06", footprint="cls:Graph.KG.IVFIndex.Insert",
    signature="iris_src/src/Graph/KG/IVFIndex.cls:180",
    invoke='for i, v in enumerate([[1, 0, 0, 0], [0.9, 0.1, 0, 0], [0, 0, 1, 0], [0, 0, 0.9, 0.1]]): '
           'eng.create_node(f"jv_i{i}", graph=G); eng.store_embedding(f"jv_i{i}", v, graph=G)\n'
           'eng.ivf_build("jv_ivf", nlist=2, metric="dot", graph=G)  # needs numpy + scikit-learn in the venv\n'
           'm = mark(); eng.ivf_insert("jv_ivf", "jv_i0", [0, 0, 1, 0])  # re-insert an indexed id with a new vector',
    expect={"stores": ["^IVF(\"jv_ivf\",\"list\",cell,id) SET twice (possibly two cells)",
                       "^IVF(\"jv_ivf\",\"cfg\",\"indexed\") SET (not $Increment)"], "transactions": "none",
            "pids": "c.pid"},
    discriminates="F-0608 (no delete across cells; count drift); ^IVF is not one of AUDITA's product indexes: "
                  "kill ^IVF(\"jv_ivf\") afterwards")
add(id="J20", module="06", footprint="cls:Graph.KG.EmbedQueue.ProcessBatch",
    signature="iris_src/src/Graph/KG/EmbedQueue.cls:258",
    invoke='eng.create_node("jv_q1"); o.classMethodValue("Graph.KG.EmbedQueue", "Enqueue", "jv_q1", "jv-no-such-config", '
           '"hello", ""); m = mark(); o.classMethodValue("Graph.KG.EmbedQueue", "ProcessBatch", 10, 5)',
    expect={"stores": ["^EmbedQueue(\"jv_q1\",\"status\") SET DONE (no vector table write)"],
            "absent": ["sql:Graph_KG.kg_NodeEmbeddings"], "transactions": "none", "pids": "c.pid"},
    discriminates="F-0604 on Community (no EMBEDDING config); other PENDING entries in AUDITA would also be processed: "
                  "check ^EmbedQueue is empty first")
add(id="J21", module="01", footprint="py:IRISGraphEngine.initialize_schema",
    signature="iris_vector_graph/_engine/schema.py:2097",
    invoke='eng.initialize_schema()  # second run on an already set-up namespace',
    expect={"stores": ["^IVG.Deploy(\"schema\"/\"recorded\"/\"routines\"/\"fingerprint\")", "DDL catalog (system, "
                       "filtered by default)", "Graph_KG.embedding_registry"],
            "transactions": "several autocommit units; no lock records", "pids": "c.pid"},
    discriminates="F-0107 (look for the effect of the unqualified DROP INDEX idx_props_key_val with keep_system=True); "
                  "re-runs setup on AUDITA (allowed: the pin's own deploy path)")

doc = {"_doc": __doc__.strip(), "pin": "3eaa79cf77d3e0a879b2cced634cf2729d81499e",
       "generated_by": "experiment/playbook-completion/models/breadth-a/tools/make_journal_candidates.py",
       "candidates": C}
out = Path(__file__).resolve().parents[1] / "inventory" / "journal-candidates.json"
out.write_text(json.dumps(doc, indent=1) + "\n")
print(len(C), "candidates ->", out)
