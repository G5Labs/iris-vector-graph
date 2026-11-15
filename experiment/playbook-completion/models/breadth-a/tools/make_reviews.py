#!/usr/bin/env python3
"""Hand reviews of the most important writer footprints (playbook §3.4 declared reads/writes, §3.5 lock plans).

Each review was made by reading the cited source at pin 3eaa79cf next to the extracted record. It states the
footprint as the reviewer reads it (`writes`, `reads`: store -> condition), the transaction boundary and server process
(`transactions`), the locks (`locks`), what the extraction got wrong (`corrections`), any atomicity the source or the
docs claim (`atomicity_claim`), and finding candidates (`notes`). Regenerate footprint_reviews.json with this script.
"""
import json
from pathlib import Path

ENGINE_PROC = ("the engine's DB-API cursor process; IVG's WriteTxn (iris_vector_graph/_write_txn.py:102-277) opens a "
               "level there, or joins the caller's transaction (CHANGELOG 4.6.4; docs/USER_GUIDE.md:236-241)")
NATIVE_PROC = ("self._iris_obj() (iris_vector_graph/engine.py:1894-1942): the cursor's own process when the engine was "
               "built on a DB-API connection, but a second DB-API connection (another server process) on an engine "
               "made by from_connect (connection params with a username)")
ROW_HOOK = ("with the adjacency index declared (setup declares it: iris_vector_graph/schema.py:774), every rdf_edges "
            "INSERT/UPDATE/DELETE runs Graph.KG.AdjIndex -> Graph.KG.Adjacency.RowPut/RowUpdate/RowRemove inside the "
            "row's transaction (AdjIndex.cls:11-27): ^KG(\"out\"), ^KG(\"in\"), ^KG(\"gen\"), ^KG(\"__version\") "
            "($Increment, not undone by rollback: P-0401), and under shared lock ^IVG.AdjW(g)#\"S\":5 "
            "(Adjacency.cls:55-75; ^IVG.AdjNoLock(g) incremented when not granted)")
LABEL_HOOK = ("rdf_labels writes run Graph.KG.LabelIndex -> Adjacency.PutLabel/RemoveLabel: ^KG(\"label\", g, label, s) "
              "and ^KG(\"__version\") (LabelIndex.cls:7-30)")
IFIND = "rdf_props.val carries an iFind index (schema.py:566): ^IRIS.IF.* word globals, partly journaled outside the transaction"
GUARD = ("ledger strict-mode guard: LedgerGuard._probe reads Graph.KG.Ledger.Meta (^IVG.Ledger(\"meta\"), "
         "^IVG.Ledger(\"head\")) at most once per 5 s per engine (iris_vector_graph/ledger/guard.py:38-59)")

R = {}

R["py:IRISGraphEngine.create_node"] = {
    "reviewed_against": "iris_vector_graph/_engine/nodes_edges.py:968-1108",
    "writes": {"sql:Graph_KG.nodes": "INSERT ... WHERE NOT EXISTS (one row, _bulk_sql('nodes_with_graph'))",
               "sql:Graph_KG.rdf_labels": "INSERT per label -> " + LABEL_HOOK,
               "sql:Graph_KG.rdf_props": "DELETE of the node's props in its graph, then guarded INSERT per prop; " + IFIND},
    "reads": {"global:^IVG.Ledger(\"meta\")": GUARD, "sql:Graph_KG.rdf_props": "NOT EXISTS guard"},
    "transactions": "one WriteTxn on the cursor (nodes_edges.py:1012-1014, commit 1095, rollback 1098); " + ENGINE_PROC,
    "locks": "no explicit lock; SQL row locks of the inserts; LabelIndex callbacks take none",
    "corrections": ["the extraction lists ^KG(\"out\"/\"in\"/\"gen\"), ^NKG and kg_NodeEmbeddings through the _bulk_sql "
                    "dispatcher (schema.py:1780-1840 builds SQL for any table); create_node executes only the nodes "
                    "statement from it and writes no edge or vector"],
    "atomicity_claim": {"claim": "Create a node with its labels and properties in one graph, in one transaction.",
                        "source": "iris_vector_graph/_engine/nodes_edges.py:975"},
    "notes": ["F-0306: any error text containing 'validation failed' is answered False as a duplicate "
              "(nodes_edges.py:1097-1102); the graph name is not width-checked (1006-1013)",
              "F-0202: no validate_graph_name call on this path (graph name written as given)"],
}
R["py:IRISGraphEngine.create_edge"] = {
    "reviewed_against": "iris_vector_graph/_engine/nodes_edges.py:1151-1304",
    "writes": {"sql:Graph_KG.nodes": "endpoint rows (_ensure_edge_endpoints, 1103-1149), duplicates tolerated",
               "sql:Graph_KG.rdf_edges": "guarded INSERT at ekey 0 (1213-1219) -> " + ROW_HOOK,
               "global:^KG(\"out\"/\"in\"/\"gen\"/\"__version\") via EdgeScan.WriteAdjacency":
                   "only when the adjacency index is NOT declared (1222-1232), through " + NATIVE_PROC,
               "sql:Graph_KG.rdf_edges (UPDATE qualifiers)": "_adopt_temporal_row (1275-1304) when the insert was a "
                   "duplicate and the triple's one row is temporal-marked; runs AFTER txn.commit() on a fresh cursor"},
    "reads": {"global:^IVG.Ledger(\"meta\")": GUARD, "global:^IVG.GraphMode": "AdjIndex callback (Adjacency.RowPut) per row",
              "catalog:INFORMATION_SCHEMA.COLUMNS": "ekey probe once per engine (1257-1273)"},
    "transactions": "one WriteTxn on the cursor around endpoints + edge (1207-1238); the adopt UPDATE is a separate "
                    "statement after the commit (autocommit, or the caller's transaction); " + ENGINE_PROC,
    "locks": "^IVG.AdjW(g)#\"S\":5 inside the row hook (Adjacency.WriterLock, Adjacency.cls:62-75); no lock across "
             "the guarded insert (the NOT EXISTS guard relies on the unique key u_spo_graph incl. ekey)",
    "corrections": ["kg_NodeEmbeddings/rdf_props/rdf_labels/^NKG writes in the extraction come from the _bulk_sql "
                    "dispatcher and from conditional ^NKG upkeep (Adjacency.Put writes ^NKG only when "
                    "^NKG(\"$meta\",\"nodeCount\") exists)"],
    "atomicity_claim": {"claim": "The endpoint rows and the edge row are one transaction: a failed edge leaves nothing; "
                                 "Nothing was written.", "source": "iris_vector_graph/_engine/nodes_edges.py:1181-1191"},
    "notes": ["F-0201: the guard compares ekey 0 only (_ekey_guard 1257-1273), so a triple whose one edge sits at "
              "ekey 1 gets a second row",
              "candidate: without the row hook WriteAdjacency runs through self._iris_obj(); on a from_connect engine "
              "that is another process, so a later rollback of the row cannot take the ^KG entry back (the code says so "
              "in the error text, 1241-1251: 'the edge's ^KG entry may remain')",
              "candidate: the temporal adoption (ADR-0009) is outside the create's transaction: a failure between the "
              "commit and the UPDATE leaves the row marked while create_edge reports success only if the UPDATE ran"],
}
R["py:IRISGraphEngine.store_node"] = {
    "reviewed_against": "iris_vector_graph/_engine/nodes_edges.py:2393-2530",
    "writes": {"sql:Graph_KG.nodes": "INSERT, duplicate swallowed (_swallow_duplicate re-reads the row)",
               "sql:Graph_KG.rdf_props": "DELETE+INSERT per key; " + IFIND,
               "sql:Graph_KG.rdf_labels": "INSERT per label, duplicate swallowed -> " + LABEL_HOOK},
    "reads": {"global:^IVG.Ledger(\"meta\")": GUARD},
    "transactions": "one WriteTxn on the cursor (2424-2528); " + ENGINE_PROC,
    "locks": "none explicit",
    "corrections": ["no edge, vector or ^NKG write (dispatcher over-approximation)"],
    "atomicity_claim": {"claim": "The node row, its properties and its labels are one transaction.",
                        "source": "iris_vector_graph/_engine/nodes_edges.py:2415"},
    "notes": ["F-0202: no validate_graph_name on this path (2421)"],
}
R["py:IRISGraphEngine.store_edge"] = {
    "reviewed_against": "iris_vector_graph/_engine/nodes_edges.py:2532-2588",
    "writes": {"sql:Graph_KG.nodes": "endpoint rows (_ensure_edge_endpoints)",
               "sql:Graph_KG.rdf_edges": "plain INSERT at the column default ekey 0, duplicate swallowed -> " + ROW_HOOK},
    "reads": {"global:^IVG.Ledger(\"meta\")": GUARD, "sql:Graph_KG.rdf_edges": "duplicate check after a refused insert"},
    "transactions": "one WriteTxn on the cursor (2563-2584); " + ENGINE_PROC,
    "locks": "row hook's ^IVG.AdjW(g)#\"S\":5 only",
    "corrections": ["no label/prop/vector writes (dispatcher over-approximation)"],
    "atomicity_claim": {"claim": "The endpoint rows and the edge row are one transaction; ... nothing written",
                        "source": "iris_vector_graph/_engine/nodes_edges.py:2555-2557"},
    "notes": ["F-0304: a duplicate over a temporal-marked row is swallowed and the mark is kept (no "
              "_ADOPT_TEMPORAL_ROW_SQL), unlike create_edge/bulk_create_edges",
              "F-0201: insert lands at ekey 0 regardless of the graph's mode"],
}
R["py:IRISGraphEngine.delete_edge"] = {
    "reviewed_against": "iris_vector_graph/_engine/nodes_edges.py:1382-1456",
    "writes": {"sql:Graph_KG.rdf_edges": "DELETE by triple (+graph unless all_graphs) -> " + ROW_HOOK +
                                         " (RowRemove/RemoveKeyed)",
               "global:^KG via EdgeScan.DeleteAdjacency[AllGraphs]": "only without the row hook, through " + NATIVE_PROC},
    "reads": {"global:^IVG.Ledger(\"meta\")": GUARD},
    "transactions": "one WriteTxn on the cursor (1414-1449); " + ENGINE_PROC,
    "locks": "row hook's ^IVG.AdjW(g)#\"S\":5",
    "corrections": [],
    "atomicity_claim": {"claim": "A delete IRIS refuses raises GraphWriteError and deletes nothing",
                        "source": "iris_vector_graph/_engine/nodes_edges.py:1391-1393"},
    "notes": ["F-0303: writes no ^IVG.Ledger(\"stmt\")/(\"tuple\") entry: the ledger's live link for the triple "
              "survives a direct delete (only Ledger*/Eraser classes touch them)",
              "HD-0302/F-0304 family: deletes a temporal-marked row as readily as an explicit one (no marker check)"],
}
R["py:IRISGraphEngine.delete_node"] = {
    "reviewed_against": "iris_vector_graph/_engine/nodes_edges.py:2227-2268; iris_vector_graph/stores/iris_sql_store.py:1318-1365",
    "writes": {"via Graph.KG.Eraser.EraseNodeIds (store.delete_nodes)": "nodes, rdf_labels, rdf_props, rdf_edges "
               "(row hook), vector routes, docs, ^IVG.Ledger(\"stmt\"/\"tuple\") of each erased edge "
               "(Eraser.cls:641-680), temporal stores of the node; owned by the erasure module"},
    "reads": {"global:^IVG.Ledger(\"meta\")": GUARD, "sql:Graph_KG.nodes": "_graphs_holding (scope resolution)"},
    "transactions": "store._eraser_txn per chunk (iris_sql_store.py:1351); one EraseNodeIds transaction per graph; "
                    "reifier deletes run as later, separate calls (nodes_edges.py:_delete_in_scope)",
    "locks": "those of Graph.KG.Eraser (erasure module)",
    "corrections": ["the extraction follows only 3 resolvable hops into the store; the Eraser footprint is the erasure "
                    "module's and is not repeated here"],
    "atomicity_claim": {"claim": "Each graph's delete is one Graph.KG.Eraser.EraseNodeIds transaction",
                        "source": "iris_vector_graph/_engine/nodes_edges.py:2231-2232"},
    "notes": ["reifier nodes are deleted after the node's transaction committed: a failure there leaves the node "
              "deleted and its reifiers (documented in the GraphWriteError text, _delete_in_scope)"],
}
R["py:IRISGraphEngine.bulk_create_nodes"] = {
    "reviewed_against": "iris_vector_graph/_engine/nodes_edges.py:1648-1871; iris_src/src/Graph/KG/EdgeScan.cls:340-430",
    "writes": {"server path (objectscript deployed, no node carries 'graph')": "Graph.KG.EdgeScan.BulkIngestNodesSQL per "
               "1,000-node chunk: nodes, rdf_labels (" + LABEL_HOOK + "), rdf_props DELETE+INSERT (" + IFIND + ")",
               "SQL fallback / graph path": "executemany into nodes, rdf_labels, rdf_props (guarded), "
               "_drop_orphaned_props DELETE on rdf_props",
               "DDL when disable_indexes=True": "GraphSchema.disable_indexes (DROP INDEX ...) then _rebuild_after_load "
               "(%BuildIndices + Graph.KG.Adj.WarmCache + Traversal.Build2HopStats) in the finally clause"},
    "reads": {"global:^IVG.Ledger(\"meta\")": GUARD, "sql:Graph_KG.nodes": "_check_nodes_written"},
    "transactions": "server path: a WriteTxn on the cursor (1718) that covers NOTHING the loader writes when the loader "
                    "runs through " + NATIVE_PROC + "; each BulkIngestNodesSQL call has its own TSTART/TCOMMIT "
                    "(EdgeScan.cls:352, 424; TROLLBACK 1 to its level, 426). On failure the WriteTxn is rolled back and "
                    "the WHOLE batch is re-run on the SQL path (1753-1757) in a new WriteTxn. disable_indexes commits "
                    "the open txn first (1767-1772) and conn.commit() runs in finally (1871)",
    "locks": "none explicit",
    "corrections": ["^KG(\"out\"/\"in\"), ^NKG, rdf_edges and kg_NodeEmbeddings in the extraction are dispatcher and "
                    "_rebuild_after_load over-approximations; no edge row is written"],
    "atomicity_claim": {"claim": "each write (create_node, ..., the bulk loaders, ...) is a transaction of its own",
                        "source": "docs/USER_GUIDE.md:238-241"},
    "notes": ["F-0305: on a from_connect engine chunk k commits in another process before chunk k+1 runs; a failure "
              "leaves earlier chunks committed (then the SQL fallback re-runs the batch)",
              "journal check: expect BeginTrans/CommitTrans pairs under a pid different from the cursor's, one per chunk"],
}
R["py:IRISGraphEngine.bulk_create_edges"] = {
    "reviewed_against": "iris_vector_graph/_engine/nodes_edges.py:1873-2017",
    "writes": {"sql:Graph_KG.nodes": "endpoint rows", "sql:Graph_KG.rdf_edges": "guarded INSERTs -> " + ROW_HOOK,
               "sql:Graph_KG.rdf_edges (UPDATE)": "_ADOPT_TEMPORAL_ROW_SQL executemany (1985-1991): clears the "
               "temporal mark of a triple re-created explicitly (ADR-0009)",
               "sync() when auto_sync": "TraversalBuild.BuildKG/BuildNKG after the commit (2012-2016)"},
    "reads": {"global:^IVG.Ledger(\"meta\")": GUARD, "sql:Graph_KG.rdf_edges": "missing_rows check (1975-1979)"},
    "transactions": "one write_txn on the cursor (commit 1993); disable_indexes path commits and rebuilds in finally; "
                    "auto_sync runs sync() after the commit (separate transactions, " + NATIVE_PROC + ")",
    "locks": "row hook's ^IVG.AdjW(g)#\"S\":5",
    "corrections": [],
    "atomicity_claim": {"claim": "each write (... the bulk loaders ...) is a transaction of its own",
                        "source": "docs/USER_GUIDE.md:238-241"},
    "notes": ["F-0202: neither graph= nor an edge's own graph key is validated (1941-1967)"],
}
R["py:IRISGraphEngine.bulk_ingest_edges"] = {
    "reviewed_against": "iris_vector_graph/_engine/nodes_edges.py:2019-2125; iris_src/src/Graph/KG/EdgeScan.cls:267-313",
    "writes": {"server path": "EdgeScan.BulkIngestEdgesSQL per 1,000-edge chunk: default-graph nodes "
               "(RegisterDefaultNode) and rdf_edges INSERT -> " + ROW_HOOK + "; WriteAdjacency when not indexed",
               "SQL fallback": "nodes (endpoints) and guarded rdf_edges INSERTs, one per edge",
               "sync() when auto_sync": "after the commit"},
    "reads": {"global:^IVG.Ledger(\"meta\")": GUARD},
    "transactions": "server path as bulk_create_nodes: per-chunk TSTART/TCOMMIT in the loader's process "
                    "(EdgeScan.cls:277, 307; TROLLBACK 1 to its level, 309), WriteTxn on the cursor around it covers "
                    "nothing on a from_connect engine; fallback re-runs the batch",
    "locks": "row hook's ^IVG.AdjW(g)#\"S\":5",
    "corrections": [],
    "atomicity_claim": {"claim": "each write (... the bulk loaders ...) is a transaction of its own",
                        "source": "docs/USER_GUIDE.md:238-241"},
    "notes": ["F-0305 (same shape as bulk_create_nodes)",
              "F-0307: BulkIngestEdgesSQL skips an edge on any INSERT error other than -119 and on a failed endpoint "
              "registration (EdgeScan.cls:290-300) without counting it; no width check in Python"],
}
for name, fn_range in (("load_nodes", "252-378"), ("load_edges", "380-482"), ("load_networkx", "540-610")):
    R[f"py:iris_vector_graph.bulk_loader.BulkLoader.{name}"] = {
        "reviewed_against": f"iris_vector_graph/bulk_loader.py:{fn_range}; 83-150; 484-510",
        "writes": {"sql:Graph_KG.nodes / rdf_labels / rdf_props / rdf_edges": "INSERT %NOINDEX %NOCHECK (default "
                   "use_noindex=True) in batches; %NOINDEX skips every index of the statement, the functional "
                   "AdjIndex/LabelIndex and iFind included, so ^KG(\"out\"/\"in\"/\"label\") is NOT written at insert "
                   "time", "indices": "rebuild_all_indices / _rebuild_indices: %BuildIndices of the FIXED classes "
                   "Graph.KG.rdfedges, rdflabels, rdfprops, nodes (bulk_loader.py:495) -> AdjIndex.PurgeIndex "
                   "(Adjacency.RemoveAll) + InsertIndex per row",
                   "load_networkx build_globals": "BuildKG/BuildNKG via build_graph_globals"} if name == "load_networkx" else
                  {"sql:Graph_KG." + ("nodes / rdf_labels / rdf_props" if name == "load_nodes" else "rdf_edges (+ nodes for endpoints, not %NOINDEX)"):
                   "INSERT %NOINDEX %NOCHECK by default, per batch; no row hook runs for %NOINDEX rows"},
        "reads": {"sql:Graph_KG.nodes": "existing ids with WHERE %NOINDEX (bulk_loader.py:182-199)"},
        "transactions": "commit per batch (_executemany_batched, commit_per_batch=True, bulk_loader.py:111-135); "
                        "refuses a caller transaction first (_refuse_in_caller_transaction, 156-163); NOT atomic across "
                        "batches by design",
        "locks": "none; %NOCHECK skips unique and foreign-key checks",
        "corrections": ["the extracted implicit row-hook writes do not happen for %NOINDEX inserts; the extraction "
                        "marks this as '[no row hook: %NOINDEX ...]'"],
        "atomicity_claim": None,
        "notes": ["F-0301: no ledger_check on BulkLoader paths (HD-0301: excluded from strict mode by spec 213)",
                  "F-0309: index rebuild names the Graph_KG classes whatever schema= was given",
                  "F-0308: qualifiers json.dumps without allow_nan=False (load_edges 453)"] if name != "load_nodes" else
                 ["F-0301: no ledger_check", "between the %NOINDEX insert and the rebuild, indexed reads and the "
                  "adjacency index do not see the rows (P-0304)"],
    }
R["py:IRISGraphEngine.set_multigraph"] = {
    "reviewed_against": "iris_vector_graph/_engine/admin.py:893-936; iris_src/src/Graph/KG/GraphMode.cls:20-61",
    "writes": {"global:^IVG.GraphMode(key)": "Set \"multi\" (on) or Kill (off) by Graph.KG.GraphMode.Apply -> Set",
               "engine cache _graph_mode_cache": "this engine's entry only (_graph_mode_forget)"},
    "reads": {"sql:Graph_KG.rdf_edges": "ParallelCount GROUP BY s, p, o_id HAVING COUNT(*) > 1 (off only)"},
    "transactions": "none: count and Kill are two steps with no TSTART; Native API call through " + NATIVE_PROC,
    "locks": "none (no ^IVG.AdjW or other lock around count+kill)",
    "corrections": [],
    "atomicity_claim": {"claim": "Turning it off is refused while any triple of the graph still has two edges",
                        "source": "iris_src/src/Graph/KG/GraphMode.cls:21-24; specs/234-multigraph-parallel-edges FR-002"},
    "notes": ["F-0207: a concurrent Cypher CREATE can add a parallel edge between ParallelCount and the Kill",
              "F-0208: other engines keep their cached mode (admin.py:917-936)",
              "F-0201: ParallelCount counts only triples with >=2 rows; a lone edge at ekey 1 passes"],
}
R["cls:Graph.KG.GraphMode.Set"] = dict(R["py:IRISGraphEngine.set_multigraph"],
                                       reviewed_against="iris_src/src/Graph/KG/GraphMode.cls:26-61")
R["cls:Graph.KG.Adjacency.Put"] = {
    "reviewed_against": "iris_src/src/Graph/KG/Adjacency.cls:55-109",
    "writes": {"global:^KG(\"out\"/\"in\")": "Set weight", "global:^KG(\"gen\", g, s)": "$Increment (every call)",
               "global:^KG(\"__version\")": "$Increment", "global:^IVG.AdjNoLock(g)": "$Increment when the writer lock "
               "is not granted in 5 s (WriterLock)", "global:^NKG": "only when ^NKG(\"$meta\",\"nodeCount\") exists "
               "(interning via GraphIndex, under LOCK ^NKG)"},
    "reads": {},
    "transactions": "none of its own: runs in the caller's transaction (row hook: the row's)",
    "locks": "LOCK +^IVG.AdjW(g)#\"S\":5, released right after the writes (Lock:tLocked -...#\"S\"); inside a "
             "transaction the release is deferred to its end (P-0003); GraphIndex.InternNode LOCK +^NKG (no timeout)",
    "corrections": [],
    "atomicity_claim": {"claim": "Every adjacency write must bump the generation and hold the shared lock",
                        "source": "docs/adr/0012-degree-is-served-from-a-generation-validated-cache.md:31"},
    "notes": ["$Increment of gen/__version is not undone by a rollback (P-0401): see F-0402"],
}
R["cls:Graph.KG.Adjacency.Remove"] = {
    "reviewed_against": "iris_src/src/Graph/KG/Adjacency.cls:147-167",
    "writes": {"global:^KG(\"out\"/\"in\")": "Kill leaf", "global:^KG(\"gen\", g, s)": "$Increment if the leaf existed",
               "global:^KG(\"__version\")": "$Increment", "global:^NKG": "GraphIndex.DeleteIndex when no other graph holds "
               "the triple", "global:^KG (graph-gone marks)": "MarkGraphGone"},
    "reads": {"global:^KG(\"out\")": "$Data before the kill"},
    "transactions": "caller's", "locks": "^IVG.AdjW(g)#\"S\":5 via WriterLock",
    "corrections": [], "atomicity_claim": None,
    "notes": ["F-0201: with the mode off one unkeyed leaf stands for the triple; Remove kills it whichever row went"],
}
R["cls:Graph.KG.Adjacency.RemoveGraph"] = {
    "reviewed_against": "iris_src/src/Graph/KG/Adjacency.cls:428-447",
    "writes": {"global:^KG(\"out\"/\"in\"/\"gen\"/\"degc\"/\"degw\"/\"deg\"/\"degp\", g)": "Kill subtree",
               "global:^IVG.AdjNoLock(g)": "Kill", "global:^KG(\"__version\")": "$Increment"},
    "reads": {}, "transactions": "caller's (Eraser.EraseGraph's)",
    "locks": "LOCK +^IVG.AdjW(g)#\"S\":5, error when not granted; released at the end",
    "corrections": [], "atomicity_claim": None,
    "notes": ["F-0401: Kill ^KG(\"gen\", g) resets every source generation to 0 instead of stepping it; a reader that "
              "read generation 0 earlier can store a count as current"],
}
R["cls:Graph.KG.Adjacency.Reweight"] = {
    "reviewed_against": "iris_src/src/Graph/KG/Adjacency.cls:323-342",
    "writes": {"global:^KG(\"out\"/\"in\")": "Set weight where the leaf exists", "global:^KG(\"__version\")": "$Increment"},
    "reads": {"global:^KG(\"out\"/\"in\")": "$Data"}, "transactions": "caller's",
    "locks": "none (deliberately: comment at 327; LOCK_EXEMPT_METHODS in tests/unit/test_degree_cache_writers.py)",
    "corrections": [],
    "atomicity_claim": {"claim": "Every adjacency write must bump the generation and hold the shared lock",
                        "source": "docs/adr/0012-degree-is-served-from-a-generation-validated-cache.md:31; spec 252 FR-004"},
    "notes": ["F-0407: no writer lock and no generation step, against the ADR's literal rule (harmless for counts)"],
}
R["cls:Graph.KG.Adjacency.PutShadow"] = {
    "reviewed_against": "iris_src/src/Graph/KG/Adjacency.cls:121-139",
    "writes": {"global:^KG(\"out\"/\"in\")": "Set weight", "global:^KG(\"gen\")/(\"__version\")":
               "$Increment ONLY when the leaf did not exist"},
    "reads": {"global:^KG(\"out\")": "$Data"}, "transactions": "caller's",
    "locks": "^IVG.AdjW(g)#\"S\":5 via WriterLock",
    "corrections": [], "atomicity_claim": None,
    "notes": ["F-0405: a weight change on an existing leaf moves neither gen nor the graph-version token"],
}
R["cls:Graph.KG.TraversalBuild.BuildKG"] = {
    "reviewed_against": "iris_src/src/Graph/KG/TraversalBuild.cls:30-165",
    "writes": {"global:^KG(\"prop\")": "Kill", "indexed namespace": "%BuildIndices of idxedgesadj and idxlabelsadj "
               "(TraversalBuild.cls:88-91) -> AdjIndex.PurgeIndex (Adjacency.RemoveAll) + InsertIndex per row",
               "non-indexed namespace": "Kill ^KG(\"label\"), Adjacency.RemoveAll, then FillEdge per row and "
               "^KG(\"label\") per label row", "global:^NKG": "BuildNKG afterwards",
               "global:^KG(\"degc\"/\"degw\")": "EndRebuild(1) warm fill (Adj.WarmAll)"},
    "reads": {"sql:Graph_KG.rdf_edges": "cursor over every row", "sql:Graph_KG.rdf_labels": "every row",
              "global:^IVG.GraphMode": "per row (keyed vs unkeyed)"},
    "transactions": "TStart (TraversalBuild.cls:40), TCommit then TStart every 50,000 rows (121), TCommit (125); on "
                    "error 'If $TLevel > 0 { TRollback }' with NO level (156): rolls back every level, the caller's "
                    "included (P-0409). Outside a caller transaction the rebuild is committed in 50,000-row pieces",
    "locks": "Adjacency.BeginRebuild: LOCK +^IVG.AdjW#\"S\":5 on the PARENT name in SHARED mode (Adjacency.cls:814-822), "
             "held to EndRebuild: it blocks the readers' exclusive child probes (P-0404) but not another rebuild",
    "corrections": [],
    "atomicity_claim": {"claim": "An IVG write never commits or rolls back a transaction its caller opened",
                        "source": "CHANGELOG.md:410-424 (4.6.4)"},
    "notes": ["F-0409: TRollback without a level at TraversalBuild.cls:156 (file line) discards a caller's open work "
              "when sync() runs in the caller's process (engine on a DB-API connection, not from_connect)",
              "candidate (HD-0402): two rebuilds (sync, rebuild_kg, a second BuildKG) both get the shared parent lock "
              "and run at once; nothing makes a rebuild exclusive"],
}
R["py:IRISGraphEngine.sync"] = {
    "reviewed_against": "iris_vector_graph/_engine/schema.py:2859-2911",
    "writes": {"via Graph.KG.Traversal.BuildKG -> TraversalBuild.BuildKG": "see that record",
               "via Graph.KG.Traversal.BuildNKG, Build2HopStats": "^NKG, ^KG(\"deg2p\")"},
    "reads": {},
    "transactions": "three separate class-method calls through " + NATIVE_PROC + "; no caller-transaction refusal "
                    "(unlike initialize_schema 2148-2156)",
    "locks": "those of BuildKG/BuildNKG",
    "corrections": [], "atomicity_claim": None,
    "notes": ["F-0409 applies when _iris_obj() is the cursor's own process"],
}
R["cls:Graph.KG.Adj.Degree"] = {
    "reviewed_against": "iris_src/src/Graph/KG/Adj.cls:52-89",
    "writes": {"global:^KG(\"degc\", g, s, key)": "Set $ListBuild(gen, count) when the probe was granted, no "
               "^IVG.AdjNoLock(g), and the generation did not move; Kill if it moved right after"},
    "reads": {"global:^KG(\"gen\", g, s)": "before and after the count", "global:^KG(\"degc\")": "cache hit check",
              "global:^KG(\"out\", g, s)": "Count (with \"#\" multiplicity)", "global:^IVG.AdjNoLock(g)": "$Data"},
    "transactions": "none (reader); a <PROTECT> on the store is swallowed (read-only login)",
    "locks": "probe LOCK +^IVG.AdjW(g)#\"E\":0, released at once when granted (Adj.cls:68-72)",
    "corrections": [],
    "atomicity_claim": {"claim": "the cache entry is never wrongly current (generation-validated cache)",
                        "source": "docs/adr/0012-degree-is-served-from-a-generation-validated-cache.md:12-26"},
    "notes": ["F-0401: soundness needs every writer to move gen after its change; RemoveSource/RemoveGraph/RemoveAll "
              "kill it (back to 0) and FillEdge refills without stepping"],
}
R["py:IRISGraphEngine.create_edge_temporal"] = {
    "reviewed_against": "iris_vector_graph/_engine/temporal.py:246-332; iris_vector_graph/stores/iris_sql_store.py:2655-2690; iris_src/src/Graph/KG/TemporalIndex.cls:46-140",
    "writes": {"global:^KG(\"tout\"/\"tin\")": "Set weight (tin unless suppressed)", "global:^KG(\"bucket\", g, b, s)":
               "$Increment (also on update: F-0501)", "global:^KG(\"tagg\", g, b, s, p, ...)": "count/sum $Increment, "
               "min/max", "global:^KG(\"edgeprop\")": "attributes (Kill first on update)", "global:^KG(\"tlast\"/latest)":
               "NoteLatest", "HLL": "UpdateHLL",
               "structural row (structural predicate)": "indexed: Adjacency.AssertTemporalRow -> SQL INSERT of a "
               "temporal-marked rdf_edges row and missing endpoint nodes (Adjacency.cls:591-602) -> row hook; "
               "not indexed: Adjacency.PutShadow",
               "Python mirror (not indexed, graph given)": "rdf_edges INSERT without qualifiers + _mirror_node nodes "
               "(temporal.py:309-331)"},
    "reads": {"global:^IVG.Ledger(\"meta\")": "_ledger_strict decides whether the Python mirror/own-row step runs "
              "(temporal.py:304-306); no ledger_check refusal on this path",
              "global:^IVG.TemporalPolicy": "IsStructuralKey (opt-out registry)"},
    "transactions": "none of its own: InsertEdge/WriteStores have no TSTART; the class method runs through the "
                    "store's Native API object (iris_sql_store.py:1085-1088); the Python mirror INSERT is a separate "
                    "autocommit statement (temporal.py:322)",
    "locks": "only the row hook's / PutShadow's ^IVG.AdjW(g)#\"S\":5",
    "corrections": [],
    "atomicity_claim": None,
    "notes": ["candidate (new): WriteStores sets tout/tin/bucket/latest before AssertTemporalRow, which "
              "$$$ThrowOnError's (TemporalIndex.cls:107-111); with no transaction a refused row insert leaves the "
              "temporal edge stored without its aggregate (tagg) and without its structural row",
              "F-0502: timestamp=None is sent as 0 (epoch), not now", "F-0503: AssertTemporalRow inserts endpoint "
              "nodes no ledger record names", "F-0506: Python mirror writes an unmarked row and ignores the opt-out"],
}
R["py:IRISGraphEngine.bulk_create_edges_temporal"] = {
    "reviewed_against": "iris_vector_graph/_engine/temporal.py:390-476; iris_src/src/Graph/KG/TemporalIndex.cls:142-200",
    "writes": {"as create_edge_temporal, per edge": "BulkInsertCounts -> WriteStores; ts 0 means now (F-0502); "
               "field 'sri' suppresses tin (F-0512)", "Python mirror": "rdf_edges + nodes when not indexed"},
    "reads": {}, "transactions": "none: one BulkInsertCounts call per batch, no TSTART; partial on error",
    "locks": "row hook's", "corrections": [], "atomicity_claim": None,
    "notes": ["F-0513: only presence/keys validated (temporal.py:138-154)"],
}
R["py:IRISGraphEngine.delete_edge_temporal"] = {
    "reviewed_against": "iris_vector_graph/_engine/temporal.py:334-388; iris_vector_graph/stores/iris_sql_store.py:2692-2717",
    "writes": {"via TemporalIndex.DeleteTemporalEdge (TemporalIndex.cls:325-343) -> Remove": "tout/tin/edgeprop of "
               "the event, bucket/tagg counters (F-0501 notes a counter of 1 left after update+delete), latest index "
               "(Relatest)", "structural row": "Adjacency.RetractTemporalRow when it was the triple's last timestamp "
               "(deletes the row if IsTemporalMarked: F-0505); RemoveTemporalRow on the non-indexed path"},
    "reads": {}, "transactions": "none of its own", "locks": "row hook's",
    "corrections": [], "atomicity_claim": None,
    "notes": ["F-0505: IsTemporalMarked accepts temporal: 1 / \"1\" as a mark; the ledger requires JSON true"],
}
R["py:IRISGraphEngine.purge_before"] = {
    "reviewed_against": "iris_vector_graph/_engine/temporal.py:623-640; iris_src/src/Graph/KG/TemporalIndex.cls:816-864",
    "writes": {"global:^KG(\"tout\"/\"tin\"/\"edgeprop\"/\"tagg\"/\"bucket\", 0, ...)": "Kill before tsEnd, default "
               "graph only", "structural rows + bare nodes": "RetireExpired -> retract marked rows; "
               "Eraser.RetireBareNodes SQL DELETE of Graph_KG.nodes when retire_bare_nodes (default True)"},
    "reads": {"global:^KG(\"tout\", 0)": "$Order scan"},
    "transactions": "none (no TSTART); class method through " + NATIVE_PROC,
    "locks": "none of its own (row hook's on retired rows)",
    "corrections": [], "atomicity_claim": None,
    "notes": ["F-0504: no ledger_check although it deletes node rows (erase_bare_nodes has one)"],
}
R["cls:Graph.KG.TemporalIndex.Purge"] = {
    "reviewed_against": "iris_src/src/Graph/KG/TemporalIndex.cls:381-391, 808-811",
    "writes": {"global:^KG(\"tout\"/\"tin\"/\"bucket\"/\"tagg\"/\"edgeprop\"/\"tlast\")": "Kill for EVERY graph (EraseAll)"},
    "reads": {}, "transactions": "none", "locks": "none",
    "corrections": [], "atomicity_claim": None,
    "notes": ["F-0507: leaves the temporal-marked rdf_edges rows and their ^KG(\"out\"/\"in\") entries"],
}
R["py:IRISGraphEngine.store_embedding"] = {
    "reviewed_against": "iris_vector_graph/_engine/embeddings.py:942-1026",
    "writes": {"route table (kg_NodeEmbeddings or Graph_KG.kg_emb_<hash>)": "DELETE + INSERT TO_VECTOR",
               "route creation (first write of a (graph, model) pair)": "_route_for_write -> _create_route: CREATE TABLE "
               "kg_emb_<hash>, HNSW index attempt, INSERT embedding_registry, conn.commit() (embeddings.py:470-560)"},
    "reads": {"sql:Graph_KG.nodes": "_assert_node_exists", "sql:Graph_KG.embedding_registry":
              "route + identity (get_embedding_identity swallows every error: F-0601)"},
    "transactions": "route creation commits on its own (refused inside a caller txn); the vector DELETE+INSERT is one "
                    "write_txn (embeddings.py:1003-1026)",
    "locks": "route creation under a Python threading.Lock per (registry, graph, model, kind) (embeddings.py:68-104, "
             "292-293): process-local, not an IRIS lock",
    "corrections": [],
    "atomicity_claim": {"claim": "the DELETE and the INSERT are one transaction of IVG's (_write_txn)",
                        "source": "iris_vector_graph/_engine/embeddings.py:1003"},
    "notes": ["candidate: route creation is serialized only within one Python process; two processes creating the "
              "same route rely on the registry's own uniqueness (P-0605)", "F-0601: identity read failure -> no check"],
}
R["py:IRISGraphEngine.store_embeddings"] = dict(R["py:IRISGraphEngine.store_embedding"],
    reviewed_against="iris_vector_graph/_engine/embeddings.py:1028-1114",
    notes=["F-0615: _route_for_write(create=True) commits a new route (table, index, registry row) BEFORE the per-item "
           "_assert_node_exists loop (1064-1084): a batch refused for a missing node leaves the route behind",
           "F-0601"])
R["py:IRISGraphEngine.ivf_build"] = {
    "reviewed_against": "iris_vector_graph/_engine/vector.py:1880-2027; iris_src/src/Graph/KG/IVFIndex.cls:6-53, 237-276",
    "writes": {"global:^IVF(name, ...)": "Build (cfg, centroids; kills the old index), AddBatch per batch (lists), "
               "FinalizeIndex (counts)"},
    "reads": {"route table": "SELECT node_id, emb (scoped by graph)", "sql:Graph_KG.embedding_registry": "route"},
    "transactions": "none: Build, every AddBatch and FinalizeIndex are separate class-method calls; readers see the "
                    "index half-built (HD-0602)",
    "locks": "none", "corrections": [], "atomicity_claim": None,
    "notes": ["F-0606: ^IVF records the source table, not the graph; erasure does not touch it",
              "F-0607: 'cosine' scored as unnormalised dot product"],
}
R["cls:Graph.KG.IVFIndex.Insert"] = {
    "reviewed_against": "iris_src/src/Graph/KG/IVFIndex.cls:180-215",
    "writes": {"global:^IVF(name, \"list\", cell, id)": "Set vector (no delete from another cell)",
               "global:^IVF(name, \"cfg\", \"indexed\")": "Set $Get(...)+1 (read-modify-write, not $Increment)"},
    "reads": {"global:^IVF(name, \"cfg\"/\"centroid\")": "nlist, metric, dim, centroids"},
    "transactions": "none", "locks": "none", "corrections": [], "atomicity_claim": None,
    "notes": ["F-0608: duplicate across cells; dim read but never compared",
              "candidate (new, S4): 'indexed' is incremented by Set $Get+1 with no lock, so concurrent inserts lose "
              "counts (IVFIndex.cls:213)"],
}
R["py:IRISGraphEngine.enqueue_for_embedding"] = {
    "reviewed_against": "iris_vector_graph/_engine/embeddings.py:1803-1896; iris_src/src/Graph/KG/EmbedQueue.cls:35-110",
    "writes": {"global:^EmbedQueue(nodeId, ...)": "BulkEnqueue -> Enqueue (EmbedQueue.cls:35-79): status PENDING, "
               "text, node_id, result, error, config, graph, queued_at, keyed by the NODE ID; a PENDING entry for "
               "another graph is refused (EmbedQueue.cls:38-50), one for the same graph is overwritten"},
    "reads": {"sql:Graph_KG.embedding_registry": "enforce_embedding_identity('kg_NodeEmbeddings', graph '') "
              "(F-0605)", "sql:Graph_KG.nodes": "selection of nodes"},
    "transactions": "none; class method over self.conn's Native API (_call_classmethod)",
    "locks": "none", "corrections": [], "atomicity_claim": None,
    "notes": ["F-0605: identity enforced against the default table's row whatever the target graph",
              "candidate (new, low): Enqueue's PENDING-other-graph refusal is a check then a Set with no lock "
              "(EmbedQueue.cls:45-58): two concurrent enqueues of one node for two graphs can both pass, and a "
              "same-graph enqueue for another model overwrites a PENDING entry's config"],
}
R["cls:Graph.KG.EmbedQueue.ProcessBatch"] = {
    "reviewed_against": "iris_src/src/Graph/KG/EmbedQueue.cls:258-338",
    "writes": {"global:^EmbedQueue(id, \"status\"/\"error\"/\"result\")": "DONE/ERROR per entry",
               "route table or Graph_KG.kg_NodeEmbeddings": "INSERT OR UPDATE ... TO_VECTOR (dynamic SQL)"},
    "reads": {"global:^EmbedQueue": "$Order scan of PENDING entries (no claim)", "sql:Graph_KG.nodes": "NodeInGraph",
              "sql:Graph_KG.embedding_registry": "RouteTable/RouteDtype (named graphs only)",
              "SQL EMBEDDING()": "IRIS embedding function"},
    "transactions": "none: the vector upsert autocommits, then the status Set; not atomic together",
    "locks": "none: two workers scanning concurrently can both process an entry (HD-0604)",
    "corrections": [], "atomicity_claim": None,
    "notes": ["F-0604: a failed Prepare, SQLCODE <> 0 or no row falls through to status DONE with no vector",
              "F-0603: default-graph entries always target kg_NodeEmbeddings; no registry identity check",
              "HD-0604: no claim protocol; single-consumer is a premise (P-0606)"],
}
R["py:IRISGraphEngine.initialize_schema"] = {
    "reviewed_against": "iris_vector_graph/_engine/schema.py:2097-2770",
    "writes": {"DDL": "CREATE TABLE/INDEX of the IVG schema, ALTER for upgrades (vector width, graph_id, ekey, "
               "val), DROP INDEX idx_props_key_val UNQUALIFIED (schema.py:656-657, F-0107)",
               "routines": "CREATE OR REPLACE FUNCTION/PROCEDURE Graph_KG.* (get_procedures_sql_list), record "
               "^IVG.Deploy(\"routines\") (routine_record.py:95)",
               "classes": "upload + compile of iris_src classes (class_deploy.upload_and_compile), "
               "^IVG.Deploy(\"fingerprint\") killed then set (class_deploy.py:255, 296)",
               "record": "^IVG.Deploy(\"schema\") and (\"schema\",\"recorded\") (schema_name.write_record 194-198)",
               "registry": "Graph_KG.embedding_registry/quarantine create+adopt", "^KG": "bootstrap_kg_global",
               "privileges": "GRANT/REVOKE on read-path routines, legacy Arno revoke"},
    "reads": {"catalog": "%Dictionary, INFORMATION_SCHEMA", "global:^IVG.Deploy": "record and fingerprints"},
    "transactions": "refuses a caller transaction ($TLEVEL > 0) first (2148-2156); otherwise commits as it goes "
                    "(conn.commit at 2313, 2573, 2679, 2701); DDL and compiles are not transactional",
    "locks": "none: two concurrent setups are not serialized",
    "corrections": [], "atomicity_claim": None,
    "notes": ["F-0102: several failures are logged only (2508-2511, 1666-1671, 2680-2681)",
              "candidate: no lock serializes two setups of one namespace (both compile and both write the record)"],
}
R["py:iris_vector_graph._engine.legacy.remove_legacy_objects"] = {
    "reviewed_against": "iris_vector_graph/_engine/legacy.py:654-698",
    "writes": {"catalog": "DROP VIEW / DROP FUNCTION of 4.5.x objects; %Dictionary class delete (_delete_class)"},
    "reads": {"catalog": "present_legacy_objects (%Dictionary, INFORMATION_SCHEMA)"},
    "transactions": "conn.commit() at the end (legacy.py:687); DDL autocommits",
    "locks": "none", "corrections": [], "atomicity_claim": None,
    "notes": ["F-0101: removed=True after DROP VIEW without reading _drop's result (670-672) and for later items of a "
              "handled class (679-684)"],
}
R["py:IRISGraphEngine.remove_legacy_objects"] = dict(R["py:iris_vector_graph._engine.legacy.remove_legacy_objects"],
    reviewed_against="iris_vector_graph/_engine/admin.py:378-394 -> legacy.remove_legacy_objects")

out = Path(__file__).resolve().parent / "footprint_reviews.json"
out.write_text(json.dumps({"_doc": __doc__.strip(), "reviewer": "breadth lane A (static review at pin 3eaa79cf)",
                           "reviews": R}, indent=1) + "\n")
print(f"{len(R)} reviews -> {out}")
