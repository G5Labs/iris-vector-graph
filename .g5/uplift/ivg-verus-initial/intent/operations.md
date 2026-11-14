# IVG operation inventory (worker A-ops, independent of docs)

Baseline: worktree HEAD `0e441f1c` (product tree = `3eaa79cf`, v4.7.0 + checklist; the two later commits only add
`.g5`/uplift material). Built from code entry points only; no doc, ADR, spec, CHANGELOG or `experiment/g5-verus/index.md`
was read. Every statement below is **(O) observed implementation** unless tagged **(P) proposal/inference**. Code
comments are quoted as claims ("comment says"), not as intent. Bugs are SUSPECTED unless the code alone proves them.

## Method and roots

- Roots: `iris_vector_graph/` (engine + `_engine/*` mixins, `stores/`, `ledger/`, `cypher/`, `migrations/`, servers),
  `iris_src/src/Graph/KG/*.cls`, `iris_src/src/IVG/*.cls`, `api/`, `src/` (demo apps), `sql/`. Excluded:
  `browser_static`, `iris_src/dev/` (dev-only: `User.Exec`, `Graph.KG.Benchmark`, `Graph.KG.BenchFormat`,
  `iris.vector.graph.GraphOperators`), tests except as callers.
- Enumeration: `grep -n "    def [a-z]"` over `engine.py` and every `_engine/*.py`; `grep` for `write_txn|WriteTxn|
  .commit()|.rollback()|classMethodValue|classMethodVoid|_call_classmethod|_iris_obj|INSERT|DELETE FROM|UPDATE` per
  writer file; an awk pass listing every raw `conn.commit()/rollback()` with its enclosing function; for ObjectScript,
  `SqlProc|SqlName|TSTART|TCOMMIT|TROLLBACK|Lock|Set ^|Kill ^|$Increment`.
- Three read-only sub-sweeps (same rules) produced the ObjectScript (2 parts) and network-route inventories; I
  re-read the load-bearing spots myself: `Txn.cls:19-56`, `Ledger.cls:397-415,498-512`, `LedgerApply.cls:652-692`,
  `Adjacency.cls:147-160`, `TemporalIndex.cls:46-120`, `EmbedQueue.cls:112-137,300-330`, `Eraser.cls:1260-1330`,
  `AlgoCache.cls:14-68`, `bolt_server.py:495-512`, `api/routers/cypher.py:100-170`, `cypher_api.py:236-252`,
  `examples/domains/biomedical/resolver.py:258-278`. Citations from the sub-sweeps not in that list are marked `[s]`.
- Vocabulary. **Stores**: SQL tables `nodes`, `rdf_labels`, `rdf_props`, `rdf_edges`, `rdf_reifications`, `docs`,
  `kg_NodeEmbeddings(_optimized)`, `kg_EdgeEmbeddings`, routed `kg_emb_*`/`kg_eemb_*`, `embedding_registry`,
  quarantine, `fhir_*`, `table_mappings`, `relationship_mappings`, `code_crosswalk`, `rdf_namespaces`,
  `ledger_revisions`; globals `^KG("out"|"in"|"gen"|"label"|"prop"|"deg*"|"__version")` (adjacency, functional-index
  maintained), `^KG("tout"|"tin"|"bucket"|"tagg"|"edgeprop"|"tlast"|"labelset")` (temporal), `^NKG` (interned
  accelerator), `^IVG.Ledger(...)`, `^IVG.AlgoCache`, `^IVG.GraphMode`, `^IVG.TemporalStructural`, `^BM25Idx`,
  `^VecIdx`, `^IVF`, `^PLAID`, `^EmbedQueue`, `^ArnoKG`.
- **Commit primitive** (O): `WriteTxn` (`_write_txn.py:102-272`) runs `SELECT Graph_KG.Txn_Begin(hold)` /
  `Txn_End(level)` / `Txn_Undo(level)` on the writing cursor (`_write_txn.py:131-137`) =>
  `Graph.KG.Txn.Begin` TSTART (`Txn.cls:27,29`), `End` loops TCOMMIT while `$TLevel>=pLevel` (`Txn.cls:42`), `Undo`
  loops `TROLLBACK 1` (`Txn.cls:55`). Joined (nested) when the caller has `$TLEVEL>0` or driver autocommit off
  (`_write_txn.py:59-87,164-175`). Fallback for pre-4.6.4 namespaces: plain `START TRANSACTION/COMMIT/ROLLBACK`
  (`_write_txn.py:177-210`). `rollback()` swallows its own failure (`_write_txn.py:234-253`).
- **Two Native API transports** (O, central to every hazard below):
  `engine._iris_obj()` (`engine.py:1894-1943`) opens a **dedicated `iris.dbapi` connection** whenever `from_connect`
  credentials are known => a *different server process* from `engine.conn`; `store._iris_obj()` /
  `schema._call_classmethod` / `WriteTxn.native()` use `createIRIS(<same conn>)` (`iris_sql_store.py:842-848`,
  `schema.py:95-104`, `_write_txn.py:139-153`) => same process, inside the caller's/IVG's transaction.

## Inventory

Legend for "commit boundary": **W** = one `WriteTxn` (nests in caller txn); **W×n** = n separate WriteTxns;
**OS-T** = ObjectScript-owned TSTART/TCOMMIT; **raw** = `conn.commit()`; **auto** = statement autocommit / no txn;
**X** = runs on `engine._iris_obj()` (separate process: outside the caller's and IVG's transaction).
"Ledger" column: **rec** = writes a ledger revision; **guard** = `_ledger_check` strict-mode refusal only
(`_engine/ledger.py:72-79` -> `ledger/guard.py:75-80`, 5 s cached probe that fails open, `guard.py:20,38-56`);
**none** = neither.

### G1. Structural node/edge writers (engine `NodesEdgesMixin`, `SchemaMixin`, store protocol)

| operation(s) file:line | writes (stores) | commit boundary | ledger | readers | hazards |
|---|---|---|---|---|---|
| `create_node` `_engine/nodes_edges.py:968` | guarded `INSERT nodes ... WHERE NOT EXISTS` (:1024), `rdf_labels` (:1045/1050), `DELETE`+`INSERT rdf_props` (:1077-1091); `^KG("label")` via LabelIndex functional index [s `Adjacency.cls:768`] | W (:1016-1098); rollback + `False` when the node exists (:1028-1031) | guard (:1005) | `get_node` :563, Cypher MATCH, native `^KG("label")` | returns False on existing id (no update); label/prop rows keyed by node id |
| `create_edge` `nodes_edges.py:1151` (+`_GraphSubEngine` `engine.py:162`) | `_ensure_edge_endpoints` INSERT nodes (:1106-1150), guarded `INSERT rdf_edges` (:1214-1219); `^KG out/in/gen/__version`, `^NKG` via `idx_edges_adj` -> `Adjacency.RowPut/Put` [s]; **not indexed**: `EdgeScan.WriteAdjacency` via `_iris_obj()` (:1221-1234) | W (:1207-1239) + **X** for the ^KG write when not indexed | guard (:1195) | Cypher, BFS, algorithms, `verify_graph` | non-indexed ^KG write is on another process: survives rollback (comment :1247-1249 admits it) and is visible before commit; endpoint nodes created implicitly; duplicate -> `_adopt_temporal_row` UPDATE (:1275-1304) |
| `set_edge_weight` `nodes_edges.py:1306` | `UPDATE rdf_edges.qualifiers` per row (:1359-1362); non-indexed `WriteAdjacency` **X** (:1364-1368) | W (:1333-1372) | guard (:1327) | weight readers, Dijkstra | default graph only (`COALESCE(graph_id,'')=''` :1340); non-indexed X as above |
| `delete_edge` `nodes_edges.py:1382` | `DELETE rdf_edges` (:1419-1433); non-indexed `EdgeScan.DeleteAdjacency[AllGraphs]` **X** (:1435-1446) | W (:1414-1449) | guard (:1404) | — | **leaves `rdf_reifications`, `kg_EdgeEmbeddings`, `^IVG.Ledger("tuple"/"stmt")`** (Eraser.EraseEdgeRow cleans them [s `Eraser.cls:641-677`]) |
| `store_node` :2393 / `store_edge` :2532 | nodes/props/labels; rdf_edges | W (:2425-2526 / :2563-2584) | guard (:2420/:2559) | — | legacy shapes; edge relies on index for ^KG |
| store `write_nodes` `iris_sql_store.py:1214` / `write_edges` :1253 / `delete_edges` :1474 | nodes/labels/props; rdf_edges (+legacy `rdf_edges_adjout` :1290); delete via `Eraser.EraseEdges` per 500-chunk (:1489-1498) or SQL (:1500-1516) | W / `_eraser_txn` (:1451-1472): **OS-T per chunk** when no caller txn | `_ledger_guard.check_structural_write` (:1224/1262/1482) | — | `write_edges` writes no ^KG when not indexed; delete_edges multi-commit per chunk |
| `bulk_create_nodes` `nodes_edges.py:1648` | server path `EdgeScan.BulkIngestNodesSQL` (:1718-1756) [s `EdgeScan.cls:340` OS-T :352/424]; SQL path nodes/labels/props (`%NOINDEX` templates) + `_drop_orphaned_props` (:1617) | server: W (+OS-T nested). SQL path: W, but with `disable_indexes` **commit -> DROP INDEX (DDL) -> new W -> raw commit after rebuild** (:1764-1772, :1868-1871) | guard (:1693) | — | index drop window; `_rebuild_after_load` failure only logged |
| `bulk_create_edges` `nodes_edges.py:1873` | endpoints + rdf_edges; read-back check (:1982) | same pattern (:1928-1937, :2003-2012) | guard (:1894) | — | as above |
| `bulk_ingest_edges` `nodes_edges.py:2019` | server `EdgeScan.BulkIngestEdgesSQL` (:2048-2070) [s OS-T `EdgeScan.cls:277/307`, failed rows silently skipped]; fallback row INSERT + non-indexed `WriteAdjacency` **X** (:2083-2127) | W (+OS-T nested) | guard (:2039) | — | fallback X write; default graph only (`graph_id ''` :2097) |
| `bulk_load_session` `nodes_edges.py:370` (+`_BulkLoadSession.add_nodes/add_edges` :342/:349 via `_with_reconnect` `engine.py:924`) | as the two bulk calls; `InitNKGSkeleton` (:428); post-load `Adj.WarmCache`, `Build2HopStats` or `sync()` (:477-498) | per-call W; **raw commits** around disable/rebuild/tune (:422, :459, :472); derived rebuilds X | guard (:396) | — | many commits; on retry after a dropped connection a committed batch is re-sent (guarded inserts make it idempotent); `_bulk_load_drifted` swallows errors -> `True` (:504-515) |
| `delete_node` `nodes_edges.py:2227`, `bulk_delete_nodes` :2270 | `_delete_scopes` reads holder graphs (:2202-2225) then store `delete_nodes` -> `Eraser.EraseNodeIds` per 500-chunk (`iris_sql_store.py:1320-1361`) [s Eraser T :484/628: rows, `^KG` adjacency/prop/label, temporal `EraseNodes`, ledger stmt/tuple kill]; then reifier nodes in their own graphs (:2190-2199) | OS-T per chunk (no caller txn) inside `_eraser_txn`; reifiers in **separate** Eraser txns; bulk: one per batch, failures logged and counted (:2290-2298) | guard (:2257/:2281) + store guard (`iris_sql_store.py:1340`) | — | multi-commit (node then reifiers; comment-acknowledged partial :2193-2198); holder lookup outside the erasing txn (check-then-act) |
| `delete_nodes_by_prefix` :1529 | store -> `Eraser.EraseNodes` (`iris_sql_store.py:1420-1449`) [s prefix scan `Eraser.cls:333` before T] | OS-T in `_eraser_txn` | guard (:1553) | — | scan before TSTART |
| `erase_graph` :1473 (`drop_graph` :1588) | `Eraser.EraseGraph` **X** (:1514-1517) [s all content tables, routes, FHIR, `^KG(...)` per graph, temporal, `GraphMode`, `AlgoCache`, ledger stmt/tuple; T :56/258; `DROP TABLE` routes + registry `DELETE` **after** TCOMMIT :288/:292] | OS-T on X, then post-commit DDL | guard (:1513) | everything | runs on another process (no caller-txn refusal, no isolation from caller's uncommitted rows); post-commit DDL; route cache invalidated in Python after (:1524) |
| `erase_all` :1565 | `Eraser.EraseAll` **X** (:1582) [s T :714/814; `DROP` after :834; kills `^KG` label/prop/labelset/deg2p*, `^ArnoKG`, `GraphMode`, `TemporalStructural`, `AlgoCache`, `Ledger(stmt|tuple)`; keeps `Ledger("rec")`] | OS-T on X + post-commit DDL | guard (:1581) | — | as erase_graph |
| `bulk_delete_adjacency` (deprecated) :2301 | reads edges then `Eraser.EraseEdges` per graph **X** (:2332-2335); non-indexed `EdgeScan.BulkDeleteAdjacency` X (:2338) | OS-T per graph on X | **none** | — | no ledger guard; read-then-erase outside one txn |
| `reify_edge` `_engine/schema.py:3264` | `create_node` (nested) + `rdf_labels`, `rdf_reifications`, `rdf_props` (:3306-3320) | W (:3293-3329) | guard (:3286) | `get_reifications` :3335 | labels/props written unscoped (no graph_id) |
| `delete_reification` :3361 | `DELETE rdf_reifications/rdf_props/rdf_labels/nodes` (:3379-3389) | W | guard (:3372) | — | deletes reifier node in every graph (no graph predicate) |
| `materialize_inference` `_engine/schema.py:2966` | `INSERT rdf_edges` with inferred qualifier (:3049-3058); non-indexed `WriteAdjacency` **X** (:3072) | W (:3036) | guard (:2977) | — | `_exists` probe then insert (dup skipped, :3046-3062); X write survives rollback (message :3064-3068) |
| `retract_inference` :3186 | SELECT targets (:3215-3220), `DELETE rdf_edges` (:3224), then per-row `DeleteAdjacency` **X after commit** (:3239-3249) | W + post-commit X loop | guard (:3194) + caller-txn refusal when not indexed (:3199) | — | multi-step; check-then-act SELECT outside txn |

### G2. Cypher / AQL write path

| operation(s) file:line | writes (stores) | commit boundary | ledger | readers | hazards |
|---|---|---|---|---|---|
| `execute_cypher` `_engine/query.py:1746` (also `_CypherSubEngine` `engine.py:180`, `execute_aql` :1730 which cannot write: AQL parser has no mutations [s]) | translator DML: CREATE `INSERT nodes/rdf_labels/rdf_props ... WHERE NOT EXISTS` [s `translator.py:9699-9754`], rels `INSERT rdf_edges` [s :10183-10450], MERGE NOT-EXISTS rewrite [s :11508-11870], SET via `Prop_Set` [s :13575-13662], REMOVE [s :13902-13931], DELETE/DETACH with id capture and connected-node refusal [s :10625-10803]; `^KG` only through functional indexes [s `schema.py:774,780`] | outer W `_execute_cypher_write` (:1946-1967) + inner W per statement list `execute_transaction` (`iris_sql_store.py:1580-1818`); one commit overall | guard `cypher_dml` only on `is_transactional` plans (:2299-2300) | SQL MATCH; native `Cypher/Exec.cls` over `^KG` [s]; BFS | **no ledger record**; MERGE is check-then-insert without lock [s]; CREATE of an existing id behaves like MERGE (NOT EXISTS guards) [s]; `CALL{...}` write bodies dropped [s `translator.py:14632-14664`]; non-indexed install: Cypher writes no ^KG at all (engine writers compensate, Cypher does not) [s]; `_cypher_write_txn` flag per engine, not per thread (:1953) |
| `Prop_Set` SQL proc (`SqlProcs.cls:187` -> `PropWrite.SetVal` [s `PropWrite.cls:32-60`]) | sets the `rdf_props` row's data global directly (`Set @tRef`), row lock 10 s | caller's txn | none | props readers | bypasses the SQL filer and any index on `rdf_props` except what it maintains itself (P: check `idx_props_*`/iFind maintenance); no `__version` bump |
| `api/routers/cypher.py:89` POST `/api/cypher` (api.main) | `translate_to_sql` then **raw `cursor.execute` per statement** (:136-166) | own `START TRANSACTION`/`COMMIT`/`ROLLBACK` (:140,156,159) or autocommit | **none** (no `_ledger_check`) | — | **second executor**: never interprets the translator's pseudo-statements (`__capture_ids__`, `__constraint_check_delete_connected__`, `__after_result__`, `__snapshot_stage__`, `__pin_stage__`, `__capture_edge_hwm__` handled only in `iris_sql_store.py:1617-1777`); SQL COMMIT ends every level on a shared connection |
| `api/gql/schema.py:149` Query `executeCypher` | same raw executor [s :174-215] | same | none | — | same; reachable by HTTP GET |

### G3. Ledger (governed writes)

| operation(s) file:line | writes (stores) | commit boundary | ledger | readers | hazards |
|---|---|---|---|---|---|
| `engine.ledger.commit` `ledger/client.py:381` -> `_commit` :402 -> `_send_changeset` :320 -> `Graph.KG.Ledger.Commit` [`Ledger.cls:397`] | `CommitInTxn` [s :419]: head lock `Lock +^IVG.Ledger("head"):30` [s :440]; idem/expected_head/size checks [s :445-491]; `LedgerApply.ApplyAll` (`nodes`, `rdf_labels`, `rdf_props`, `rdf_edges`, `rdf_reifications`, embeddings deletes, `Adjacency.Put/Reweight/Remove`, `TemporalIndex.InsertEdge`, `^IVG.Ledger("stmtNext"|"stmt"|"tuple")`) [s `LedgerApply.cls:97-692`]; `WriteRevision` `^IVG.Ledger("rec",seq,..)`, `ledger_revisions` row, `head`, `revById`, `idBySeq` [s :532-563] | **OS-T** `Ledger.cls:402-405`; no caller txn: on **X** (`client.py:395-396`); caller txn: nested via `txn.native()` (`client.py:399-403`); `LedgerStats.Bump` in a **second txn after commit** (`Ledger.cls:413`) | rec | `history`, `get_revision`, `diff`, `reconstruct`, `verify` | seq = head+1 under lock, `stmtNext` read-then-set [s `LedgerApply.cls:162-163`]; `kind` is client-supplied: non-"changeset" skips size/empty checks [s :491]; `NodeExists` graph-blind while deletes target default graph [s `LedgerApply.cls:79-84,354-371`] |
| `post_commit_properties` `client.py:445-487` | `DELETE`+`INSERT rdf_props` (default graph) | **separate W after** the revision commit (when no caller txn) | **not recorded** (comment: "no new revision" :430) | props readers | 2 commits per `commit()`; failure returns `post_commit_error`, revision stays |
| `_mark_nkg_dirty_if_needed` `client.py:489-503` | Python flag `_nkg_dirty` | — | — | BFS route (`query.py:2455`) | — |
| `enable` `client.py:281` -> `Ledger.Enable` [s `Ledger.cls:252-325`] | `^IVG.Ledger("meta",...)`, `head=0`, `stmtNext=1`, genesis `Capture` stmts [s `LedgerGenesis.cls:14`], `WriteRevision` | OS-T on X; refused in caller txn (`client.py:268-284`); may chain `verify(adopt=True)` (:292-296) => second commit | rec (genesis, adoption) | — | state read [s :254] before T and lock (check-then-act; IdKey on Seq is the only backstop [s]) |
| `disable` :299 / `set_strict` :305 | `meta.state` / `meta.strict` [s :343/:366] | OS-T on X; no head lock [s] | — | guard probe (5 s TTL) | **no caller-txn refusal** (unlike enable); strict flag reaches other engines only after their 5 s cache |
| `redact` `client.py:633` -> `LedgerRedact.Redact` [s :185] | tombstones `rec`, clears idem/revision fields, `UPDATE ledger_revisions`, final redaction revision, drops stmt/tuple [s :302-467] | **N+1 OS-T** (one per batch + final) on X | rec (redaction) | `redaction_in_progress` gates readers (`client.py:687-693`) | resumable by design; marker digest not re-checked under lock [s :322] |
| `verify(adopt=True)` `client.py:741` -> `replay.verify` :806 | `RecordVerify` stats [s `Ledger.cls:192`]; adoption `commit(kind="adoption")` (`replay.py:846-854`) | reconstruct + `read_canonical` with **no lock/txn** (`replay.py:825-835`), then OS-T adoption | rec | — | **check-then-act**: divergence computed outside the head lock, adoption changeset has no `expected_head` (:848-853) |
| `Graph.KG.Ledger.PurgeAll` [s `Ledger.cls:242-246`] | `Kill ^IVG.Ledger`, `%KillExtent` revisions/stats | auto | wipes | — | no guard; only tests call it (`tests/conftest.py:1311`) |
| `rebuild_edge_indices` SQL proc (`SqlProcs.cls:200` -> `Ledger.RebuildEdgeIndices` [s :224-234]) | `BUILD INDEX` x4 => `Adjacency.RemoveAll/RemoveAllLabels` then refill | **none** | none | all ^KG readers | whole-subtree kill outside any txn |

### G4. Temporal writers

| operation(s) file:line | writes (stores) | commit boundary | ledger | readers | hazards |
|---|---|---|---|---|---|
| `create_edge_temporal` `_engine/temporal.py:246` -> store `write_temporal_edge` `iris_sql_store.py:2655` -> `TemporalIndex.InsertEdge` (`TemporalIndex.cls:46`) -> `WriteStores` :80 | `^KG("tout","tin","bucket","tagg","edgeprop","tlast")`; structural: indexed => `Adjacency.AssertTemporalRow` (SQL `nodes`+`rdf_edges` marked row) else `PutShadow` (`TemporalIndex.cls:109-115`); then Python step: `_own_structural_row` -> `create_edge` (`temporal.py:190-206`) **or** legacy mirror `INSERT nodes/rdf_edges` (`temporal.py:308-330`) | InsertEdge: **auto (no TSTART, no lock)** [s]; then a second, separate W (create_edge) or autocommit INSERTs | **none** (no `_ledger_check`; strict only suppresses the mirror :304) | window/aggregate readers, BFS via shadow | temporal globals committed even if the structural step fails (mirror failure is a WARNING, :322-330); **`mode="update"`/`upsert=True` re-increments `bucket` and `tagg` count/sum** (`TemporalIndex.cls:82-84,101,117-118`; contradicts comment :77-79 and docstring `temporal.py:270-276`) |
| `bulk_create_edges_temporal` `temporal.py:390` -> `BulkInsertCounts` (`iris_sql_store.py:2747-2756`); fallback per-edge InsertEdge (:2759-2786) | same per edge; mirror INSERTs (`temporal.py:447-466`) | auto per item [s `TemporalIndex.cls:142-151`]; throw mid-batch keeps earlier items | none | — | partial batch on error |
| `delete_edge_temporal` `temporal.py:334` -> `DeleteTemporalEdge` (`TemporalIndex.cls:325`) [s] | kills tout/tin/edgeprop, bucket -1, tagg rebuilt, tlast, `RetractTemporalRow`/`Remove`; then owned structural row delete (`temporal.py:376-388`) | auto + separate step | none | — | multi-store delete without txn |
| `purge_before` :623 / `purge_bucket_range` :642 / `purge_raw_before` :656 -> `TemporalIndex.PurgeBefore/PurgeBucketRange/PurgeRawBefore` [s :816/:1050/:866] | kills raw/aggregate subtrees, `RetractTemporalRows`, `Eraser.RetireBareNodes` | auto [s] | none | aggregates | `PurgeBucketRange` walks `tagg` only [s]; no txn |
| `erase_bare_nodes` :687 -> store :2816 -> `Eraser.EraseBareNodes`/`DeleteBareSet` (`Eraser.cls:1260-1313`) | `DELETE nodes` batches; `ForgetNodes` -> `Adjacency.RemoveSource`, `Kill ^KG("prop")` | **TCOMMIT per batch then global writes after each commit** (`Eraser.cls:1297-1304`), `InvalidateDerived` after the last (:1311-1312) | store guard (:2825) | — | multi-commit + post-commit global writes |
| `rebuild_temporal_latest` :613 -> `RebuildLatest` [s :581] | kill + refill `^KG("tlast",g)` | auto | none | `latest` readers | kill-then-rebuild (flag set last) |
| `set_temporal_structural` :722 -> `TemporalPolicy.Set/Apply` [s :41/:61] | `^IVG.TemporalStructural(g,p)` | auto | none | `IsStructuralKey` | — |
| `drop_temporal_structural_rows` :760 -> `TemporalPolicy.DropRows` [s :124-215] | `DELETE rdf_edges` batches, `RetireBareNodes` | **OS-T per batch** [s :175/202/210] | none | — | no `^IVG.Ledger` tuple cleanup [s] |
| `backfill_temporal_structural_rows` :811 (+ SQL proc `backfill_temporal_rows` `SqlProcs.cls:194`) | marked `rdf_edges` rows via `AssertTemporalRow` [s] | auto, long walk | none | — | idempotent, partial if interrupted |
| `intern_label_set` :835 | `^KG("labelset",hex)` append-only | auto | none | `resolve_label_set` | — |
| `TemporalIndex.Purge`/`EraseAll` [s :808/:381] (ObjectScript only) | kill every graph's temporal subtrees | auto | none | — | leaves marked structural rows behind [s] |
| `TemporalIndex.MigrateToGraphScoped` [s :1098] | relayout flat -> graph key 0 | one OS-T [s :1103-1108] | none | — | very large single txn |

### G5. Embeddings, vector and text indexes

| operation(s) file:line | writes (stores) | commit boundary | ledger | readers | hazards |
|---|---|---|---|---|---|
| `store_embedding` `_engine/embeddings.py:942` (+`store_embeddings` :1028, `store_edge_embedding` :1117, `store_edge_embeddings` :1207) | `_assert_node_exists` (:967) then route resolve; `DELETE`+`INSERT` target table (`kg_NodeEmbeddings` or routed) (:1005-1024) | W per call/batch | none | `kg_KNN_VEC` :504, `vector_search` :1169 | node-existence and identity checks before the txn (check-then-act; FK on routed tables is the backstop [s]) |
| route creation `_create_route` `embeddings.py:470` (first vector for a graph/model) | `CREATE TABLE kg_emb_*` (raw commit `_engine/schema.py:902`), ANN index (raw commit :922), registry `INSERT` (:1478), index state `UPDATE` (raw commit :948), final raw commit (`embeddings.py:537`); race loser `conn.rollback()` (:521) | **4 raw commits**; refused in caller txn (:494) | none | registry/route cache | crash between table commit and registry row leaves a routed table with an FK and no registry row (the condition the comment at :529-536 says breaks every erase) |
| `embed_nodes` :1291 / `embed_edges` :1502 | via `store_embeddings` per batch | **W per batch**; batch errors counted, not raised (:1466-1479) | none | — | partial runs by design |
| `set_embedding_identity` `_engine/schema.py:1086`, `adopt_embedding_identities` :1256, `_repair_legacy_edge_route_kind` :1337, `_sync_recorded_dimension` :1399, `_migrate_vector_dimensions` :1601, `place_quarantined` :1972, `_record_route_recall` (via `measure_route_recall` `vector.py:620`) | `embedding_registry` UPDATE/INSERT; quarantine -> routed INSERT + quarantine DELETE (:2054-2064); `ALTER TABLE ... VECTOR` | W (:1134, :2054, :971) or **raw commit** (:1320 rollback, :1352, :1417, :1675) | none | `enforce_embedding_identity` :1354, inventory :1715 | raw-commit helpers are reached from setup paths (refused in caller txn there) |
| `enqueue_for_embedding` :1803 -> `EmbedQueue.BulkEnqueue/BulkEnqueueText` [s `EmbedQueue.cls:64/83`] | `^EmbedQueue(id,...)`, `$I(^EmbedQueue("$seq"))` | auto (same process) | none | queue readers | PENDING-in-other-graph check then set [s :45] |
| `process_embed_queue` :1898 | `ClaimPendingBatch` (**read only, no status change**, `EmbedQueue.cls:112-136`), `SetResult DONE` (:1964-1967) **then** `_upsert_node_embedding` (:1978), ERROR on failure (:2020-2032) | auto global writes + W per vector | none | — | no claim => two workers process the same entry; DONE set before the vector commits |
| `start_background_embedding` :2105 -> `EmbedQueue.StartBackgroundTask` [s :347] -> task `ProcessBatch` (`EmbedQueue.cls:258-330`) | `%SYS.Task`, `^IVG.EmbedQueueTask`; `INSERT OR UPDATE` target table | auto | none | — | **entry marked DONE when Prepare fails or EMBEDDING returns no row** (`EmbedQueue.cls:308-327`) |
| `clear_done` :2076 | `Kill ^EmbedQueue(reqId)` | auto | none | — | — |
| `vec_create_index/insert/bulk_insert/build/drop` `_engine/vector.py:1548-1643` -> `VecIndex` [s] | `^VecIdx(name)` | auto, **X** | none | `vec_search` :1606 | `Build` kill-then-rebuild; re-insert inflates count [s `VecIndex.cls:149,163`] |
| `plaid_build/insert/drop` `vector.py:1652-1748` -> `PLAIDSearch` [s] | `^PLAID(name)` | auto, X | none | `plaid_search` | kill-then-rebuild; no delete [s] |
| `bm25_build/insert/delete/upgrade/drop` `vector.py:1749-1870` -> `BM25Index` [s] | `^BM25Idx(name)` | Build/Drop: **no txn, no lock** [s :97-170, :587]; Insert/Delete: OS-T + lock [s :442-512]; Upgrade: lock [s :526] | none | `bm25_search` :1786, `kg_BM25` SQL proc | Build without the writer lock races Insert [s] |
| `ivf_build/insert/delete/drop` `vector.py:1880-2060` -> `IVFIndex` [s] | `^IVF(name)`; `FinalizeIndex` recount | auto, X | none | `ivf_search`, `kg_IVF` | duplicate cells on re-insert, delete stops at first [s] |
| `create_index` `vector.py:243` (+`index_protocol.py`) | engine registry only; `replace=True` drops the existing index | — | none | `index(name)` | — |

### G6. Derived-index maintenance, setup, admin, bulk loader

| operation(s) file:line | writes (stores) | commit boundary | ledger | readers | hazards |
|---|---|---|---|---|---|
| `sync` `_engine/schema.py:2859` (`rebuild_kg` :2913, `rebuild_nkg` :2924; `_CypherSubEngine.sync` `engine.py:185`) | `Traversal.BuildKG` [s `TraversalBuild.cls:30`: kill `^KG("prop")`, possibly `RemoveAll`, refill, parallel `%BuildIndices`, `$I(__version)`], `BuildNKG` [s :288], `Build2HopStats` | **X**; BuildKG OS-T with **TCommit+TStart every 50k** [s :121/:211] | none | all ^KG/^NKG readers | partial rebuild visible to readers |
| `backfill_degp` :2935, `backfill_deg2p_exact` :2952, `backfill_2hop_exact` `nodes_edges.py:517` | `^KG("degc"/"degw")`, `^KG("deg2p_exact")` [s] | X, auto | none | degree readers | kill-then-rebuild |
| `verify_sync(heal=True)` `_engine/admin.py:756` | `sync()` | as sync | none | — | — |
| `set_multigraph` `admin.py:893` -> `GraphMode.Apply` [s `GraphMode.cls:66`] | `^IVG.GraphMode(g)` | X, auto | none | writers' ekey logic | `ParallelCount` check then set, no lock [s] |
| `kill_query` `admin.py:957` (+`DELETE /admin/queries/{id}`) | `%SYSTEM.SYS.KillProcess` | — | — | — | kills any PID the user may kill |
| `initialize_schema` `_engine/schema.py:2097` -> `_record_and_initialize` :2198 -> `_initialize_schema` :2410 | DDL, class deploy (`class_deploy.py:229,341`), `^IVG.Deploy("schema")`, grants, registry/quarantine/FHIR DDL (:544-640), migrations | **many raw commits** (:2313, :2573, :2679, :2701 + helpers); refused in caller txn (:2149-2156) | none | everything | non-atomic by design; compiled classes not rolled back |
| migrations `migrations/upgrade.py:130`, `docs_and_edge_vectors.py:474`, `graph_scoped_embeddings.py:235`, `kg_node_stores.py:113`, `temporal_structural_rows.py:66` | DDL, re-keys, data moves | `commit_step` per step (`migrations/_commit.py:25-35`); refused in caller txn | none | — | step-wise partial upgrade |
| `remove_legacy_objects(dry_run=False)` `admin.py:378` -> `legacy.py:654` | DROP/REVOKE SQLUser objects | raw commits (`legacy.py:525,576,685`) | none | — | refused in caller txn (:391) |
| `BulkLoader.load_nodes/load_edges/load_networkx/rebuild_all_indices/build_graph_globals` `bulk_loader.py:252/380/540/484/512` | `INSERT %NOINDEX %NOCHECK` nodes/labels/props/edges (:310-350, :456-460); `%BuildIndices`; `BuildKG`+`BuildNKG`+`Build2HopStats` (:531-536) | **raw commit per batch** (:116,:131), rollback (:167,:362); refused in caller txn (:156-167) | **none** (no strict guard) | — | `%NOINDEX` rows have no `^KG` until rebuild; `%NOCHECK` skips unique/FK checks |
| SQL procs `Txn_Begin/Txn_End/Txn_Undo` (`SqlProcs.cls:168-181` -> `Txn.cls:19-56`) | `$TLevel` only | callable by any SQL client | — | — | `End(1)`/`Undo(1)` end every level, including a caller's |
| `sql/globals_schema.sql:29` `kg_BUILD_GLOBALS` (legacy) [s] | `KILL ^KG` then pre-graph-key refill | auto | none | — | no loader found in product code; wipes temporal/version stores |
| `sql/fraud_sample_data.sql` [s :12-16, ~402 INSERTs] | DELETE+INSERT core tables | script | none | — | loaded by `scripts/setup/__init__.py:253` [s]; bypasses ledger |

### G7. Import, export, snapshot

| operation(s) file:line | writes (stores) | commit boundary | ledger | readers | hazards |
|---|---|---|---|---|---|
| `load_networkx` `_engine/snapshot.py:446`, `import_graph_ndjson` :1727, `load_obo` :1694 | per item `create_node`/`create_edge`/`bulk_create_edges_temporal` (:511, :528, :1796-1852); optional `sync()` (:554) | **W per node/edge** | guard at entry (:471, :1745) + per call | — | partial import on error; temporal batches unguarded |
| `import_rdf` :557 | batched node/label/prop/edge INSERTs (`_flush` :675-718); non-indexed `BuildKG` **X** (:779) | W per batch; refused in caller txn when not indexed (:622-632) | guard (:580) | — | multi-commit |
| `save_snapshot` :798 (+`POST /admin/snapshot`) | ZIP file on the server filesystem | — | — | `restore_snapshot` | reads DB without a consistent snapshot across tables/globals (P) |
| `restore_snapshot` :1077 | `erase_all()` **X** (:1152) unless merge; per-table INSERTs + `_commit` raw commit (:1205-1216, used :1232, :1305, :1369, :1491, :1551); globals via Native `set` (:1654-1692) incl. `^IVG.Ledger`, `LedgerRevisionD/I`, `^KG`, `^NKG`, `^BM25Idx`... (allow-list `snapshot.py:387-422`); version floors raised in `finally` (:1584-1586) | **many commits + non-transactional global writes on X**; refused in caller txn (:1099) | guard (:1095); does **not** reconcile the ledger | everything | per-line global write failures are logged at DEBUG and dropped (:1683-1684), not counted in `failed_rows`; merge or non-merge restore writes the archive's `^IVG.Ledger("head")`/`rec` over a live ledger (erase_all keeps `rec`) — SUSPECTED head/record mismatch |
| `export_graph_ndjson` :1857, `export_rdf` `rdf_export.py:96`, `prov_export` `prov.py:107`, `ledger.export_reconstruction` `client.py:730` | files only | — | — | — | — |
| `register_namespace` `rdf_export.py:53` | `rdf_namespaces` | W | none | `list_namespaces` | — |

### G8. FHIR and SQL-table bridges

| operation(s) file:line | writes (stores) | commit boundary | ledger | readers | hazards |
|---|---|---|---|---|---|
| `map_sql_table` `_engine/fhir.py:88`, `map_sql_relationship` :147, `remove_table_mapping` :237 | `table_mappings`, `relationship_mappings` | W (:129, :177, :249) | none | translator via mapping cache (`_invalidate_mapping_cache` `engine.py:904`) | — |
| `attach_embeddings_to_table` `fhir.py:267` | `store_embedding` per row | W per row | none | — | partial |
| `fhir_bridge_add` `fhir.py:390`, `code_crosswalk_add` `fhir_graph.py:607`, `migrate_fhir_bridges_to_crosswalk` :647 | `fhir_bridges`, `code_crosswalk` (`INSERT OR UPDATE`) | W | none | concept resolution | — |
| `fhir_graph_register/rebuild/sync/reinterpret/schedule/unschedule` `fhir_graph.py:222-310` via `_fhir_call` **X** (:183-188); `_ensure_fhir_graph_tables` raw commit (:216) | `FHIRGraph.Register/Rebuild/SyncOnce/Reinterpret/Schedule/Unschedule` [s `FHIRGraph.cls:167-729`]: `fhir_graphs`, `fhir_definitions/canonical_refs` (delete-all then refill across commits [s :1982-2001]), nodes/edges/labels/props/docs/embeddings in the FHIR graph, direct `^KG("label")` sets [s :2477-2616], `%SYS.Task` | OS-T per batch (watermark in the same txn [s :1927-1974]); Register/Schedule/final UPDATE outside txn [s] | **none** (no strict guard) | FHIR reports, `fhir_concept_ppr` | structural writes with no ledger guard; Register COUNT-then-INSERT race [s]; production fault hook `^IVG.FHIRGraphFault` [s :1970] |
| `FHIRGraphSyncTask.OnTask` [s :14] (Task Manager) | -> `SyncOnce` | as above | none | — | background writer |

### G9. Network entry points that change state (handler -> engine operation above)

| server: route/message file:line | calls | guard | commit | hazards |
|---|---|---|---|---|
| Bolt `RUN` `bolt_server.py:490` -> `_handle_run` :567 | `engine.execute_cypher` (:581) | API key if set (:477-479); `IVG_READ_ONLY` + `writes_cypher` (:570); access mode ignored | engine W per RUN | **`BEGIN`/`COMMIT`/`ROLLBACK` are no-ops** (`bolt_server.py:500-510`): ROLLBACK reports SUCCESS after RUNs committed |
| cypher_api `POST /api/cypher` :351, `/db/{db}/query/v2` :436, `/db/neo4j/tx/commit` :379 | `_run_cypher` -> `execute_cypher` (`cypher_api.py:239-251`) | key; read-only check | engine W; **tx/commit: one commit per statement** | `_run_cypher` **retries any exception once** on a fresh engine (:241-249) |
| cypher_api `/admin/schema/init` :578, `/admin/indexes/rebuild` :597, `/admin/embed` :613, `/admin/load` :628, `/admin/snapshot` :668, `DELETE /admin/queries/{id}` :702 | `initialize_schema`, `rebuild_kg`+`rebuild_nkg`, `embed_nodes`, `import_graph_ndjson`, `save_snapshot`, KillProcess | key; `ReadOnlyMiddleware` `/admin/` (`api_auth.py:126-177`) | per operation | schema/init mutates the cached engine's `embedding_dimension` (:583) [s] |
| api.main `POST /fhir-event/` `api/routers/fhir_event.py:283` | `create_node` x2, `create_edge_temporal`, background `store_embedding` (:155-166) | key; ReadOnly unless `IVG_ALLOW_FHIR_WRITES` | 3-4 separate commits | not atomic; background thread shares the connection |
| api.main GraphQL `createProtein`/`updateProtein`/`deleteProtein` (`api/gql/schema.py:253/264/275` -> `examples/domains/biomedical/resolver.py:186/240/299`) | `create_node`+`store_embedding`; **raw `UPDATE/INSERT Graph_KG.rdf_props`** (resolver.py:262-275); `delete_node` | `_check_read_only` | engine W + driver `commit()` (:278) | updateProtein: no graph scope, no ledger guard, no rollback; hard-coded `Graph_KG` |
| standalone gql Query `cypher` `iris_vector_graph/gql/resolvers.py:136` | `execute_cypher` | key + read-only check | engine W | write via GET |
| MCP `CypherQuery`/`RunSQL`/`LoadGraph` `MCPTools.cls:9/34/74` [s] | `execute_cypher` (embedded); `%SQL.Statement` arbitrary SQL; `load_obo`/`load_networkx` + `Traversal.BuildKG` | `%AI.Policy.ConsoleAudit` only [s `MCPToolSet.cls:20-22`] | engine / autocommit | RunSQL is DDL/DML-capable; no read-only mode |
| demo `POST /api/fhir/live/add`, `/api/fhir/live/sync` `src/iris_demo_server/routes/fhir.py:503/521` [s] | `IVGDemo.FHIRLoad.Dispatch` FHIR PUT; `fhir_graph_sync` | none (no auth middleware) | FHIR server / FHIRGraph | demo only |
| CLI `ivg query/load/schema init/indexes rebuild` `cli.py:150-235,443-470` -> SDK `IVGClient._post` (`sdk.py:210-225`); `ivg fhir register/rebuild/sync/schedule` `cli.py:323-413` -> engine X | HTTP routes above / FHIR mixin | as routes | as routes | SDK `_post` retries on 5xx and timeouts => a committed write can be re-sent |

### G10. Store -> writers -> readers matrix (for drift reasoning)

Each row names a store, every writer family found above, how the store is kept in step with its pair, and the final
readers. "FI" = maintained by a functional-index callback inside the row's own filing (same process, same txn) [s
`AdjIndex.cls:12-26`, `LabelIndex.cls:10-28`, `schema.py:774,780`].

| store | writers (group refs) | pairing mechanism | final readers |
|---|---|---|---|
| `rdf_edges` | G1 engine/store writers, G2 Cypher DML + api raw executor, G3 `LedgerApply.OpCreateRel/DeleteRelInternal`, G4 `AssertTemporalRow`/mirror/DropRows/backfill, G6 BulkLoader `%NOINDEX`, `EdgeScan.BulkIngestEdgesSQL`, G7 import/restore, G8 FHIRGraph, Eraser (all erasures) | FI -> `^KG("out"/"in")` when `idx_edges_adj` is functional (`engine.py:704-723`); otherwise each Python writer calls `EdgeScan` over X; `%NOINDEX` defers to `%BuildIndices`/`BuildKG` | SQL MATCH, `read_canonical` (ledger verify), `verify_graph`, `BuildKG`/`BuildNKG` |
| `^KG("out"/"in"/"gen")` | FI callbacks; `EdgeScan.WriteAdjacency/DeleteAdjacency*` (X); `TemporalIndex` `PutShadow`; `LedgerApply` `Adjacency.Put/Reweight/Remove`; `BuildKG`/`RebuildEdgeIndices`/`kg_BUILD_GLOBALS` rebuilds; Eraser `Remove*`; restore `set` (`snapshot.py:1675-1680`) | `$I(^KG("__version"))` on each mutation [s `Adjacency.cls:92,157,340`] | native Cypher `Cypher/Exec.cls`, BFS/var-length, algorithms, `EdgeScan.MatchEdges`, `Eraser.DeleteBareSet` bare test (`Eraser.cls:1278`) |
| `^NKG` | `Adjacency.Put/Remove/RemoveSource` incremental (after unlock) [s]; `BuildNKG`/`EnsureNKG` (also from read algorithms) [s]; `InitNKGSkeleton` (`nodes_edges.py:428`); Eraser `DropNKG` [s]; restore | `^NKG("$meta","version")`, `_nkg_dirty` Python flag (`client.py:489-503`, `nodes_edges.py:451`) | Arno/NKG traversal and centrality, `_bulk_load_drifted`, `verify_sync` |
| `rdf_labels` / `^KG("label")` | G1, G2, G3 `OpCreateNode/AddLabel/OpRemoveLabel`, G6, G7, G8 (FHIR also sets `^KG("label")` directly [s]), Eraser | FI (`LabelIndex`) | native label scans, `get_labels`, `get_nodes_by_label` |
| `rdf_props` / `^KG("prop")` | G1, G2 (`Prop_Set` data-global write), G3 `SetProp/OpRemoveProp` + `post_commit_properties`, G6, G7, G8, GraphQL `updateProtein`; `^KG("prop")` only killed (Eraser, BuildKG) [s] | none (no token, no FI) | Cypher property reads, `get_node`, ledger `read_canonical` |
| `nodes` | every structural writer (implicit endpoints in `create_edge` :1106, `_mirror_node` `temporal.py:98`, `EnsureEndpoint` [s], `RegisterDefaultNode` [s]); Eraser/`DeleteBareSet` | FKs from `rdf_edges` and routed vector tables [s] | all node reads |
| `^KG("tout"/"tin"/"bucket"/"tagg"/"edgeprop"/"tlast")` | G4 only (+ `LedgerApply.OpCreateTemporalEdge` [s :617], Eraser `TemporalIndex.EraseGraph/EraseNodes`) | none (no txn); structural pairing via marked row or shadow | temporal window/aggregate readers, `TemporalWindow` |
| `^IVG.Ledger`, `ledger_revisions`, `LedgerStats` | G3 only for `rec`/`head`; Eraser/TemporalPolicy kill or skip `stmt`/`tuple` [s]; restore imports all (`snapshot.py:403-404`); `PurgeAll` | head lock + OS-T (commit path only) | `history/get_revision/diff/reconstruct/verify`, guard `Meta()` |
| vector tables + `embedding_registry` | G5 `store_*`, route creation, quarantine, queue workers; Eraser deletes rows and drops routed tables [s] | identity checks before write (`embeddings.py:981`) | `kg_KNN_VEC`, `vector_search`, inventory |
| `^BM25Idx`, `^VecIdx`, `^IVF`, `^PLAID` | G5 index APIs only; restore imports | none with content (no eraser hook) | `bm25_search`/`kg_BM25`, `vec_search`, `ivf_search`/`kg_IVF`, `plaid_search` |
| `^IVG.AlgoCache` | `AlgoCache.Put` from read algorithms; Eraser kills per graph/all [s] | token = `^KG("__version")` at lookup time (`AlgoCache.cls:16-28`) | pagerank/ppr/wcc/cdlp via `iris_sql_store.py:930-988` |
| `^EmbedQueue` | G5 enqueue/claim/result/clear, background task | none (no txn, no claim) | `process_embed_queue`, `embed_queue_pending` |

## Read-only operations

- Node/graph reads (`nodes_edges.py`): `get_node` :563, `get_nodes` :621, `count_nodes` :733, `get_node_ids_by_label`
  :760, `get_nodes_by_label` :779, `get_node_ids_by_property` :801, `get_nodes_by_property` :833, property helpers
  :846-966, `get_node_properties/name/nodes_by_ids` :2341-2361, `node_count/edge_count` :2362-2391, `nodes_exist`
  :2590, `list_graphs` :1458; schema reads `_engine/schema.py:426-533`, `get_schema_visualization` :2772,
  `embedding_inventory` :1715, `list_quarantine` :1913, `get_embedding_identity` :1033, `get_reifications` :3335.
- Query: `execute_cypher`/`execute_aql` read plans, `khop2_count_fast/exact` `query.py:4519/4534`, system procedures
  `engine.py:1039-1740` (`db.*`, `dbms.*`, `apoc.meta.*`, `gds.*.stream`; unknown `apoc/db/dbms` answer empty success).
- Algorithms (`_engine/algorithms.py:216-1764`): PPR, khop, random walk, paths, PageRank, WCC, CDLP, subgraph,
  neighbors, centralities, Leiden, triangles, SCC, k-core. **Reads that write**: `AlgoCache.Put` into
  `^IVG.AlgoCache` (`iris_sql_store.py:976-988`), `TraversalBuild.EnsureNKG` can run a full `BuildNKG` [s
  `Communities.cls:58...`, `NKGAccelCentrality.cls:8...`], scratch `^ArnoKG("bfs_result")` shared across processes
  [s `NKGAccelTraversal.cls:290`], `Cypher/Gen.For` compiles a class and writes `^IVG.CypherCompiled` [s], lazy
  Arno SQL-function DDL with commit (`stores/arno_bridge.py:374,755,901`), BM25 stopword init [s `BM25Index.cls:48`].
- Vector/text search: `kg_KNN_VEC` `vector.py:504`, `search_nodes_by_vector` :748, `kg_TXT` :917,
  `vector_search` :1169, `multi_vector_search` :1288, `kg_RRF_FUSE` :1382, `kg_VECTOR_GRAPH_SEARCH` :1453,
  `edge_vector_search` :333, `vec_search*`, `plaid_search`, `bm25_search`, `ivf_search`, `*_info`, `list_indexes` :260,
  `get_embedding(s)` `embeddings.py:1694/1748`, `get_unembedded_nodes` :904, `embedding_count` :2124, `embed_text` :148.
- Temporal reads `temporal.py:478-1113` (window, iter, latest, velocity, bursts, attrs, aggregate, bucket groups,
  window sources, distinct count, `export_temporal_edges_ndjson`); `_engine/temporal_window.py` cursor (process-private
  `^||IVG.TWin`).
- Ledger reads `client.py:311-317, 542-731` (`meta`, `head`, `stats`, `history`, `get_revision`, `diff`,
  `reconstruct`, `export_reconstruction` (file), `redaction_in_progress`); `verify()` without adopt still writes
  `RecordVerify` stats.
- Admin/status: `status` `admin.py:396`, `verify_graph` :850, `verify_sync(heal=False)` :756, `is_multigraph` :917,
  `list_active_queries` :938, centrality/community warnings :971/:1008; FHIR reports `fhir_graph.py:260-605`,
  `get_kg_anchors` `fhir.py:444`; `validate_shacl` `shacl.py:203`; `prov_as_dict/export` `prov.py:86-141`.
- SQL procs: 26 read-only `SqlProcs.cls` forwarders (17 `CypherFn_*`, `JSON_KEYS`, `Percentile_*`, `kg_BM25`,
  `kg_IVF`, `MatchEdges[AllGraphs]`, `DijkstraPath`, `ledger_records`) [s]; `sql/operators*.sql`,
  `graph_path_globals.sql`, `graph_walk_tvf.sql` procedures [s]; CSP REST `Graph.KG.Service` `/vectorSearch`,
  `/hybridSearch`, `/metaPath` [s `Service.cls:7-9`].

## Cross-cutting hazards

### (a) One store written without its paired store (drift / bypass candidates)

1. **Non-indexed adjacency written on another process.** Without `idx_edges_adj` (`engine.py:704-723`), the engine
   edge writers call `EdgeScan.*Adjacency` through `engine._iris_obj()` = separate connection (`engine.py:1916-1943`):
   `create_edge` :1226, `set_edge_weight` :1366, `delete_edge` :1445, `bulk_ingest_edges` fallback :2113,
   `materialize_inference` `schema.py:3072`, `retract_inference` :3249. The ^KG write commits independently of the
   SQL row (rollback leaves it; readers see it before the row commits). Cypher writes and `store.write_edges` write
   **no** ^KG at all in that mode (they rely on the index). Distinguishing case: non-indexed namespace, `create_edge`
   whose `txn.commit()` fails => `^KG("out")` entry with no row.
2. **Edge deletes that leave satellites.** `engine.delete_edge` (`nodes_edges.py:1419-1433`) and Cypher `DELETE r`
   [s `translator.py:10699-10712`] remove only the `rdf_edges` row; `rdf_reifications`, `kg_EdgeEmbeddings` and
   `^IVG.Ledger("tuple"/"stmt")` stay, whereas `Eraser.EraseEdgeRow` [s `Eraser.cls:641-677`] removes all of them.
   Cypher `DETACH DELETE` clears `kg_NodeEmbeddings` but not `_optimized`/routed tables/temporal stores [s].
3. **Search indexes never follow content.** No eraser or writer touches `^BM25Idx`, `^VecIdx`, `^IVF`, `^PLAID`
   (`grep 'BM25Idx\|VecIdx\|\^IVF\|\^PLAID' Eraser.cls` -> none; only `index_protocol.py:41` calls `bm25_insert`).
   Deleted nodes remain retrievable from those indexes until a rebuild.
4. **Ledger bypass.** Only `ledger.commit` records (`Ledger.cls:397-415`). Structural writers without even the
   strict guard: temporal writers (`temporal.py:246-466`), `bulk_delete_adjacency` :2301, `BulkLoader` (all),
   `api/routers/cypher.py` and GraphQL `executeCypher`, GraphQL `updateProtein`, MCP `RunSQL`, FHIR graph sync,
   `Prop_Set` SQL proc, `post_commit_properties` (by design unrecorded), `restore_snapshot`'s global import. Eraser
   paths kill `^IVG.Ledger("stmt"/"tuple")` without the head lock or a revision [s `Eraser.cls:675-677,1139-1140`].
5. **Temporal vs structural.** `create_edge_temporal` commits the temporal globals (InsertEdge, no txn) before the
   structural row step; a failed mirror is only a WARNING (`temporal.py:322-330`). `TemporalIndex.Purge/EraseAll`
   leave marked structural rows [s]. `TemporalPolicy.DropRows` deletes rows without ledger tuple cleanup [s].
6. **Multigraph adjacency loss on ledger delete (SUSPECTED bug).** `LedgerApply.DeleteRelInternal` deletes one
   row by `%ID` (`LedgerApply.cls:678`) then calls `Adjacency.Remove` whenever `^KG("out",g,s,p,o)` still has data
   (:688), and `Remove` kills the whole triple node including the other parallel edges' ekey children
   (`Adjacency.cls:151-152`). Case: multigraph graph, two parallel s-p-o edges, ledger `delete_relationship` of one.
7. **Props path without version token.** `rdf_props`/`nodes` writes never bump `^KG("__version")` [s]; the
   algorithm cache only caches algorithms that do not read props (`algo_cache.py:13`), so this matters only if a
   cached algorithm starts reading props (P).
8. **FHIR writes `^KG("label")` directly** beside `rdf_labels` [s `FHIRGraph.cls:2477-2616`] (double writer with
   the LabelIndex functional index).

### (b) More than one commit, or non-transactional global writes

- Multi-commit by construction: `ledger.commit` + `post_commit_properties` (`client.py:395-436`) + `LedgerStats.Bump`
  (`Ledger.cls:413`); `ledger.enable` -> adoption commit (`client.py:292-296`); `redact` N+1 [s]; route creation (4
  raw commits, `embeddings.py:537`, `_engine/schema.py:902,922,948`); `store.delete_nodes`/`delete_edges` one Eraser
  txn per 500 ids (`iris_sql_store.py:1352-1360,1489-1498`); `delete_node` + reifier deletes (`nodes_edges.py:2185-
  2199`); `bulk_delete_nodes` per batch; `Eraser.DeleteBareSet` per batch with globals after each TCOMMIT
  (`Eraser.cls:1297-1312`); `erase_graph`/`erase_all` DDL after TCOMMIT [s :288/:834]; `bulk_create_*` with
  `disable_indexes` (`nodes_edges.py:1764-1772,1868-1871`); `bulk_load_session` (:422,:459,:472); `embed_nodes/edges`
  per batch; `import_rdf`, `load_networkx`, `import_graph_ndjson` per item/batch; `restore_snapshot` per table +
  globals (`snapshot.py:1205-1586`); `BuildKG` every 50k [s]; `FHIRGraph.SyncAllDefinitions` delete-all then per-200
  commits [s]; `TemporalPolicy.DropRows` per batch [s]; `BulkLoader` per batch; `initialize_schema`/migrations.
- Non-transactional global writes (no TSTART anywhere on the path): all of `TemporalIndex` except
  `MigrateToGraphScoped` [s]; `BM25Index.Build/Drop`, `VecIndex.*`, `IVFIndex.*`, `PLAIDSearch.*` [s];
  `EmbedQueue.*` (`EmbedQueue.cls:35-330`); `AlgoCache.Put` (`AlgoCache.cls:46-50`); `GraphMode.Apply` [s];
  `RebuildEdgeIndices` [s]; `Ledger.PurgeAll` [s]; `restore_snapshot`'s Native `set`s (`snapshot.py:1675-1680`).
- `$Increment` survives rollback (comment `Adjacency.cls:28`): `^KG("__version")`, `^KG("gen")`, `^NKG(-3,s)`,
  `edgeCount` [s `Adjacency.cls:89-105`] drift upward after rolled-back writes.

### (c) Guard reads state outside the transaction that writes (check-then-act)

1. Ledger strict guard: 5 s cached `Meta()` probe on `_iris_obj()`, fail-open on any error (`guard.py:20,38-56`);
   checked before the write txn opens (e.g. `nodes_edges.py:1195` vs :1209).
2. `verify(adopt=True)`: divergence read without lock, adoption commit without `expected_head` (`replay.py:825-853`).
3. `delete_node`/`bulk_delete_nodes`: holder-graph lookup (`nodes_edges.py:2202-2225`) before the Eraser txn;
   `bulk_delete_adjacency` edge SELECT before erasing (:2321-2335); `retract_inference` SELECT before its DELETE txn
   (`_engine/schema.py:3215-3221`).
4. `store_embedding*`: `_assert_node_exists` and `enforce_embedding_identity` before the write txn
   (`embeddings.py:967,981` vs :1005).
5. `process_embed_queue`: `ClaimPendingBatch` does not claim (`EmbedQueue.cls:112-136`); `Enqueue` PENDING check
   [s :45]; `FHIRGraph.Register` COUNT-then-INSERT, `Schedule` task-then-UPDATE [s]; `GraphMode.Apply`
   ParallelCount-then-set [s]; `Ledger.Enable` state read before T/L [s :254]; `TemporalIndex.WriteStores` `$Data`
   collision check with no lock (`TemporalIndex.cls:84`).
6. Cypher MERGE `INSERT ... WHERE NOT EXISTS` with no lock; multigraph `MAX(ekey)+1` [s `translator.py:10385-10450`].
7. **Algorithm cache vs uncommitted globals (SUSPECTED).** `Lookup` reads the token before computing
   (`AlgoCache.cls:20-28`; `iris_sql_store.py:959-975`). A writer's `$I(^KG("__version"))` and its `^KG`/`^NKG`
   entries are visible to other processes before commit; if that writer rolls back, the entry is undone but the
   token stays incremented, so a result computed from the uncommitted edge is cached under the current token.
   Case: two processes, writer rolls back after a reader's miss-compute-Put.
8. `Adjacency.WriterLock` proceeds **without** the lock after a 5 s timeout and marks `^IVG.AdjNoLock` [s
   `Adjacency.cls:61-75`]; `^NKG` adjustments in `Put/Remove/RemoveSource` happen after the unlock [s].

### (d) State-changing operations with no (live-DB) test caller

Grep run: for each operation name `grep -rlw --include=*.py "<op>" tests | wc -l` and the same restricted to
`tests/e2e tests/integration`; plus `grep -rn 'TAG_ROLLBACK\|TAG_BEGIN\|TAG_COMMIT' tests` and named-pattern greps.
- **No test reference at all**: Bolt `BEGIN`/`COMMIT`/`ROLLBACK` handling (`bolt_server.py:500-510`; grep -> 0);
  `kg_BUILD_GLOBALS` (`sql/globals_schema.sql:29`; 0).
- **Unit-only (no e2e/integration file)**: `store_edge_embeddings` (2/0; `tests/unit/test_230_edge_vector_routing.py:180`),
  `bm25_delete` (1/0; `tests/unit/test_bm25_index.py:229`), `bm25_upgrade` (1/0; `tests/unit/test_044_bm25_upgrade_wrapper.py:21`),
  `place_quarantined` (3/0; `tests/unit/test_227_quarantine_api.py:274`).
- **Scenario gaps in tests that do exist**: `tests/e2e/test_254_collisions_e2e.py:104-110` exercises `mode="update"` but
  asserts no aggregate after it (hazard (a)5 / InsertEdge update double count); no test combines multigraph with a
  ledger `delete_relationship` (`grep -l delete_relationship | xargs grep -l multigraph` -> only
  `tests/integration/test_236_token_write_paths.py`, whose multigraph test :289 is BuildKG, not delete);
  `Ledger.PurgeAll` is called only as test cleanup (`tests/conftest.py:1311`).
- Every other G1-G8 operation has at least one e2e/integration reference (e.g. `create_edge` 310 files, `erase_graph`
  122, `restore_snapshot` 22, `ledger.commit` 40, `purge_raw_before` 7, `set_multigraph` 14); whether those tests
  reach the hazardous branch (non-indexed install, caller transaction, concurrency) was not checked.

### (e) Outcome-changing cases a model of these operations must make representable

(P) Derived from the boundaries above; each case separates the as-built behavior from a plausible intended one.
1. **Adjacency mode**: functional index present vs absent (`engine.py:704-723`), crossed with writer family (engine
   edge writer / Cypher / store protocol / BulkLoader `%NOINDEX`). Only the first family writes `^KG` when absent.
2. **Transport**: `engine._iris_obj()` dedicated connection (credentials known) vs `createIRIS(engine.conn)`
   (credentials unknown, tests' `_safe_createIRIS`, embedded) (`engine.py:1916-1943`). The same call is inside or
   outside the write's transaction depending on how the engine was constructed.
3. **Caller transaction**: none / open with writes (`$TLEVEL>0`) / driver autocommit off with no writes
   (`_write_txn.py:59-87`); operations either nest (W), refuse (`refuse_in_caller_transaction`), or run on X and
   ignore it (`erase_graph`, `erase_all`, FHIR, vector/BM25 indexes, `disable`, `set_strict`).
4. **Failure point inside a multi-commit operation**: after the first of n commits (route table created, registry
   row absent; ledger revision committed, `post_commit_properties` failed; `DeleteBareSet` batch k committed,
   `ForgetNodes` threw; restore table k committed, global import failed).
5. **Rollback after a visible global write**: `$Increment` counters and X-transport `^KG` writes persist while the
   SQL rows are undone (algorithm cache, `^NKG` counters, non-indexed adjacency).
6. **Default vs named graph**: `set_edge_weight` (default only), `delete_edge` (`all_graphs`), `delete_node`
   omitted-graph refusal when an id is in two graphs (`nodes_edges.py:2210-2224`), ledger nodes graph-blind,
   `updateProtein` unscoped, `delete_reification` unscoped.
7. **Multigraph**: one vs several parallel edges for a triple under ledger delete, Eraser `EraseEdges` by (s,p,o),
   Cypher `MAX(ekey)+1`.
8. **Repeat / retry**: same Cypher write via `cypher_api._run_cypher` retry and SDK `_post` retry; ledger idempotency
   key replay (only the ledger path deduplicates); temporal `insert`/`skip`/`update` at an occupied coordinate.
9. **Competing writers**: two `ledger.commit` (serialized by head lock), two MERGEs (not serialized), two queue
   workers (not serialized), `BM25Index.Build` vs `Insert` (not serialized), redact vs commit (head lock per batch).

## Candidate findings (brief; for the intent reconciler)

- SUSPECTED bug: `TemporalIndex.WriteStores` update mode double-counts `bucket`/`tagg` (`TemporalIndex.cls:82-118`).
- SUSPECTED bug: ledger relationship delete wipes multigraph siblings' adjacency (`LedgerApply.cls:688`).
- SUSPECTED bug: `EmbedQueue.ProcessBatch` marks DONE without a vector (`EmbedQueue.cls:308-327`); Python worker sets
  DONE before writing (`embeddings.py:1964-1980`) and never claims.
- SUSPECTED bug: Bolt explicit transactions are not transactions (`bolt_server.py:500-510`).
- SUSPECTED bug: api.main Cypher executor ignores the translator's pseudo-statements (`api/routers/cypher.py:142-156`
  vs `iris_sql_store.py:1617-1777`) and the ledger guard.
- SUSPECTED bug: `restore_snapshot` drops per-line global failures silently (`snapshot.py:1683-1684`) and overwrites
  live ledger globals.
- Question: is `engine._iris_obj()` (separate process) intended for writers that run inside a WriteTxn? (non-indexed
  edge writers, `erase_graph`, `erase_all`, FHIR graph, vector indexes, ledger without caller txn).
- (P) Simplification: one edge-delete path (Eraser.EraseEdgeRow) for `delete_edge`, Cypher DELETE, and ledger apply,
  so satellites and ledger tuple state are removed identically.

## Counts

| group | state-changing operations (entry points) | read-only (approx.) |
|---|---|---|
| G1 structural engine/store writers | 24 (create_node, create_edge, set_edge_weight, delete_edge, store_node, store_edge, write_nodes, write_edges, delete_edges, bulk_create_nodes, bulk_create_edges, bulk_ingest_edges, bulk_load_session(+2 session methods), delete_node, bulk_delete_nodes, delete_nodes_by_prefix, erase_graph, drop_graph, erase_all, bulk_delete_adjacency, reify_edge, delete_reification, materialize_inference, retract_inference) | ~30 node/schema reads |
| G2 Cypher/AQL | 4 (execute_cypher write path, Prop_Set, api `/api/cypher`, gql `executeCypher`) | execute_cypher/aql reads, ~20 system procedures |
| G3 ledger | 9 (commit, post_commit_properties, enable, disable, set_strict, redact, verify(adopt), PurgeAll, rebuild_edge_indices) | 10 |
| G4 temporal | 14 | 12 |
| G5 embeddings/vector/text | 33 (4 store_*, route creation, 2 embed_*, 7 registry/quarantine/recall, 4 queue, 5 VecIdx, 3 PLAID, 5 BM25, 4 IVF, create_index) | ~25 |
| G6 maintenance/setup/admin/bulk | 20 (sync, rebuild_kg, rebuild_nkg, 3 backfills, verify_sync(heal), set_multigraph, kill_query, initialize_schema, 5 migrations, remove_legacy_objects, BulkLoader(5 as 1 group), Txn_* procs, kg_BUILD_GLOBALS, fraud sample SQL) | status/verify ~8 |
| G7 import/export | 7 (load_networkx, import_graph_ndjson, load_obo, import_rdf, save_snapshot (file), restore_snapshot, register_namespace) | 5 exporters |
| G8 FHIR | 15 (3 mapping, attach_embeddings, 3 bridge/crosswalk, 6 fhir_graph_*, `_ensure_fhir_graph_tables`, sync task) | ~10 reports |
| G9 network | 22 state-changing of ~86 routes/fields/messages/tools (api.main 6, cypher_api 9, Bolt 1, gql 1, MCP 3, demo 2) [s] | ~64 |
| ObjectScript (internal, reached by the above) | ~217 state-changing ClassMethods (~134 in ledger/adjacency/eraser/core classes, ~83 in temporal/index/queue/FHIR/cache classes) [s] | 32 SqlProcs total, 6 state-changing |

Totals for public Python/SQL entry points (G1-G8): **~126 state-changing**, **~130 read-only** (approximate: mixins
expose many thin wrappers; delegate sub-engines `engine.py:157-230` are counted once under their target).

## Not inspected / limits

- `cypher/translator.py` (31,908 lines) was traced only through the sub-sweep's grep of DML emission sites; per-clause
  line numbers marked [s] were not individually re-read. `merge_rows.py`, `count_create.py`, `native_plan.py` likewise.
- ObjectScript inventories outside the re-read list are [s]; IRIS runtime semantics assumed, not run: deferred unlock
  inside a transaction (relied on at `Ledger.cls:404-405`), `$Increment` not rolled back, globals readable before
  commit, SQL `COMMIT` ending every `$TLEVEL` (comment `_write_txn.py:15-17`).
- Not inspected: `iris_vector_graph/cypher/aql/*` beyond "no mutation", `_engine/shacl.py`, `prov.py`,
  `_engine/class_deploy.py` internals, `legacy_manifest.py`, `status.py`, `routing.py`, `host.py` internals,
  `src/iris_demo_server` services beyond the two writing routes, `examples/` other than the mounted biomedical resolver,
  `scripts/` (only as loaders of `sql/`).
- Test coverage was measured by file-name references only; whether a test is live-DB-backed or mocked was judged by
  directory (`tests/unit` vs `tests/e2e|integration`), not by reading fixtures.
- No intent sources (docs/ADRs/specs/index.md) were consulted, so no statement here is tagged (H) or (D); every
  "comment says" is a code claim, not a requirement.
