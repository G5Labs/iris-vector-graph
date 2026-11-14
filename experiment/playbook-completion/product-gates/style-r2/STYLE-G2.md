<!-- markdownlint-disable MD013 -->

# 3.5-style round 2, group G2: modules 04 adjacency, 05 temporal, 06 vectors, 07 text search

Module 04: 16 deviations of 9 conventions (primary sources: 15 of 8; secondary BRIEF.md: 1)
Module 05: 14 deviations of 9 conventions (primary sources: 10 of 7; secondary BRIEF.md: 4)
Module 06: 17 deviations of 5 conventions (primary sources: 14 of 4; secondary BRIEF.md: 3)
Module 07: 8 deviations of 5 conventions (primary sources: 7 of 4; secondary BRIEF.md: 1)

Lane product-gates, observation only. I read the product at ROOT (HEAD `14678055`; `git diff --stat 3eaa79cf HEAD -- . ':(exclude)experiment'` is empty, so every `path:line` is at the pin). I ran nothing and connected to nothing. I wrote only this file and `counts-G2.json`, with scratch scripts under `/tmp/g2`. All evidence is from reading the source. I checked every cited line with `sed -n`/`grep -n`. "X of Y" counts the distinct conventions broken, as round 1 does.

**How I judged**: as in `../STYLE.md`, using C-1..C-26 as defined there and C-27..C-35 from the brief. In ObjectScript, a swallowed error stays in the B-2 family and is not counted. For C-17 I count a broad `except` on a data-changing path when the caller is told nothing, even if a log line is written: the handler returns a normal-looking value (0, "", None, True, an empty result) or passes. If the failure reaches the caller through an error field or count, or the path writes only a derived cache that is documented as safe to lose, the case is borderline (B-3 family). One new convention is added:

- **C-40G2** (primary, PRE_RELEASE_CHECKLIST.md:354-356): "every IVG write runs as a nested level of its own (`Graph.KG.Txn` ...), so it never commits or rolls back a transaction its caller opened". CHANGELOG.md:410-422 corroborates it. Known exceptions are listed at PRE_RELEASE_CHECKLIST.md:384: `bulk_load_session`, `embed_nodes` and setup. Those are not counted. In ObjectScript, a bare `TRollback` ends every level.

**Shared method**: for each file I ran the brief's searches (step 2) over the whole file or over the named part, and read every hit in context. To find candidates I used `/tmp/g2/c25.py`, a heuristic for compound conditions whose first operand is an unparenthesised comparison, and `/tmp/g2/exc.py`, which lists every `except` handler that does not re-raise, with its kind. I read the header of every in-scope class and checked its claims against the class body (C-14). A class that is fully in scope but has no header at all is counted under C-14. ARCHITECTURE.md:203 makes "the class header comments ... the reference for each" class listed at :193-201. For classes that are only partly in scope (Service, PyOps), a missing header is borderline.

## Module 04 adjacency

| File | Lines | Coverage | Conventions judged |
| --- | --- | --- | --- |
| iris_src/src/Graph/KG/Adjacency.cls | 904 | full | 4,5,6,7,8,14,18,19,21-26,30,31,32 |
| AdjIndex.cls / AlgoCache.cls | 44 / 68 | full | 4,6,14,21,22 |
| Adj.cls | 252 | full | 8,14,19,23,25,26,31,32 |
| EdgeScan.cls | 474 | full | 4,5,6,7,14,21,22,25,26,40G2 |
| Edgeless.cls / GraphIndex.cls / GraphVerify.cls | 163 / 188 / 218 | full | 4,6,10,14,25,31 |
| TraversalBuild.cls | 1105 | full on 1-340 and 820-1105; sweep on 340-820 (^NKG rewrite) | 4,5,6,7,8,10,14,21,22,25,26,31,32,40G2 |
| iris_vector_graph/_edgeless.py, freshness.py, algo_cache.py | 114 / 77 / 64 | full | 2,4,17,35 |
| _engine/schema.py sync, rebuild_kg/nkg, backfill_degp, backfill_deg2p_exact (2858-2963) | 3397 | named part, full read | 2,17,18 |
| _engine/admin.py status adjacency (60-91, 470-575), verify_sync, verify_graph (756-891) | 1041 | named part, full read | 2,4,15,16,17,18,35 |
| _engine/nodes_edges.py bulk_delete_adjacency (2301-2339), bulk-load warm-up (476-515) | 2625 | named part | 2,17,18,35 |
| stores/iris_sql_store.py `_cached_algorithm` (921-988) | 4279 | named part (file >3,000 lines; sweep elsewhere not in scope) | 4,17 |

| ID | Conv. | Location | What deviates |
| --- | --- | --- | --- |
| D-04-01 | C-4 | EdgeScan.cls:51, 56-58 | MatchEdges derives the ^KG default key inline (`$Char(0)`→"", `If graph = "" { Set graph = 0 }`) instead of through GraphKey (ADR-0003:68) |
| D-04-02 | C-4 | Adjacency.cls:583, 627, 654, 698, 889 | AssertTemporalRow, RetractTemporalRow(s), RetractTemporalShadows and OtherEdgeKeys turn the index key back into a graph_id inline (`$Select(pGKey = 0: $Char(0), 1: pGKey)`). The caller had the name (TemporalIndex), so ADR-0003:22-25 applies, and GraphKey.cls:57-63 makes the SQL name GraphKey's own derivation |
| D-04-03 | C-7 | TraversalBuild.cls:67, 83 | BuildKG kills and refills `^KG("label")` directly, not through Adjacency.RemoveAllLabels/PutLabel (Adjacency.cls:768-795). ADR-0008:18-20 names TraversalBuild as a writer that must go through the one module |
| D-04-04 | C-8 | TraversalBuild.cls:65 | `Kill ^KG("prop")` outside the owners (same family as round-1 D-04/D-06; F-C0440) |
| D-04-05 | C-14 | Adjacency.cls:34-36 | Header: a lock not granted is "an error status and nothing is written, but for the row writers". In fact every per-edge writer goes on without the lock, including PutShadow (127) and RemoveSource/RemoveNode (354, 398), which TemporalIndex.cls:113 and Eraser.cls:547, 1326 reach without any row. Only RemoveGraph, RemoveAll and BeginRebuild refuse (431-434, 455-458, 817-820) |
| D-04-06 | C-14 | Adj.cls:1-3 | "Every reader of the out-adjacency goes through here". EdgeScan.cls:93-140, GraphVerify.cls:83-100 and TraversalBuild.cls:1071-1094 read it themselves; the last also re-applies the "#" rule (1090) |
| D-04-07 | C-14 | EdgeScan.cls:9 | "gen ... (bumped by every write)": Reweight bumps no generation (Adjacency.cls:323-342; F-0407) |
| D-04-08 | C-14 | GraphIndex.cls:11-14 | Names EdgeScan as a caller and says "three callers". EdgeScan has no GraphIndex call; Adjacency (96-98, 163, 386) and Eraser do |
| D-04-09 | C-14 | GraphVerify.cls:4-5, 12-16 | Header says only some writes keep ^KG and that drop_graph leaves adjacency behind. drop_graph is erase_graph now (nodes_edges.py:1588-1595), and the index keeps ^KG with its rows (ARCHITECTURE.md:105-107) (F-0408 family) |
| D-04-10 | C-16 | _engine/admin.py:760-766 | verify_sync calls drop_graph, delete_node and raw SQL inserts **BYPASS** paths that skip the globals. In the glossary a declared Adjacency Index cannot be bypassed this way (CONTEXT.md:88-95, 121-126) (F-0408 family) |
| D-04-11 | C-17 | _engine/schema.py:2958-2963 | backfill_deg2p_exact: `except Exception: warning; return 0` on a rebuild that kills the store first (TraversalBuild.cls:1007) |
| D-04-12 | C-17 | _engine/nodes_edges.py:487-490 | `except Exception: pass` around Build2HopStats (writes ^KG("deg2p")) |
| D-04-13 | C-17 | _engine/nodes_edges.py:496-499 | A failed closing `sync()` of bulk_load_session is only logged. The session ends normally and nothing goes into `stats` |
| D-04-14 | C-18 | _engine/admin.py:526-527, 561-562 | status() hints "Call engine.sync() ..." and "run initialize_schema()" name writing calls without saying that they write |
| D-04-15 | C-40G2 | TraversalBuild.cls:155-156 | BuildKG's Catch runs a bare `TRollback`, which ends the caller's transaction (F-0409, reproduced live) |
| D-04-16 | C-25 (sec.) | GraphIndex.cls:146 | `If zeroCount > 0 && (...)`: unparenthesised first operand. Left-to-right evaluation gives the intended result, so this is style only |

**Borderline (not counted)**: B-04-1: reads of ^KG("out"/"in") outside Adjacency (EdgeScan.cls:93-140, 198-226, 442-470; Edgeless.cls:63, 71-86; GraphVerify.cls:83-128; TraversalBuild.cls:816-895, 953-1093). These are the round-1 B-1 family (ADR-0001:48-49 and ADR-0008:25-26 against ADR-0011:12 and CONTEXT.md:224-227). B-04-2: TraversalBuild writes `deg2p`/`deg2p_exact` (949, 986, 1007, 1059). ADR-0001:48-49 forbids it, while ADR-0008:23-26 and ADR-0010:14-15 make them Rebuilt stores "computed during the rebuild". B-04-3: `^KG("__version")` bumps outside Adjacency (TraversalBuild.cls:145, 162). ADR-0008:18-19 gives the stamp to the one module; CONTEXT.md:117-118 says "every write path ... increments" it. B-04-4: inline reads of degc (TraversalBuild.cls:846-847, 974-982). ADR-0010:12-14 sends readers through Degree, but they follow ADR-0012:13-17's protocol, and Adj.cls:207-213 allows whole-graph readers to read entries directly. B-04-5: enumerators that turn a found key into a name (EdgeScan.cls:97; admin.py:68, 90). GraphKey has no inverse, and ADR-0003 covers derivation from a name. B-04-6: C-21 in RemoveNode, whose first statement is `Set tSC = ..RemoveSource(...)` (Adjacency.cls:398); the status is carried, not dropped. B-04-7: B-2 family: TraversalBuild.cls:117 and 1014; EdgeScan.cls:300 and 467; Adjacency.cls:745 and 762. B-04-8: broad catches that only lose a derived cache, logged: nodes_edges.py:483-486 (WarmCache) and iris_sql_store.py:985-987 (AlgoCache Put). B-04-9: Adj writes degc/degw (Adj.cls:77, 160-166, 200-202), which is not one of C-8's three owners. ADR-0012:15-17 makes the reader the cache's writer.

**Conforming (a few per convention)**: C-4 AlgoCache.cls:30, 48; GraphVerify.cls:41; algo_cache.py:35-36; iris_sql_store.py:945. C-5 Adjacency.cls:435-443. C-6: no Set/Kill of out/in outside Adjacency; EdgeScan.cls:154-189 delegate. C-10 only GraphIndex.cls:22-27 kills ^NKG. C-15 admin.py:556. C-18 Adjacency.cls:69 ("until sync() rebuilds ^KG"); nodes_edges.py:2309-2313 ("deletes rows"). C-19 Adjacency.cls:586; Adj.cls:65. C-30 Adjacency.cls:631 and 661-674 (rows deleted only while marked). C-31: deg/degp only killed as residue (Adjacency.cls:380-381, 442-443, 467-468); TraversalBuild.cls:927-930. C-32 Adj.cls:63-80, 143-172; Adjacency.cls:86-93, 150-157. C-35 nodes_edges.py:2326 (`self._t`); _edgeless.py:21-48 (schema passed in). C-21/22 Adjacency.cls:80-117, 399-401; TraversalBuild.cls:126-153. C-23/24: no hits. C-26 Adjacency.cls:179, 877. C-2: none.

**Reviewer notes**: R-04-1: Adjacency.cls:527 calls degw "the weighted degree cache". It is the whole-graph warm stamp (Adj.cls:198-216). R-04-2: the comment on GraphIndex.cls:160-167 ("Called by EdgeScan:DeleteAdjacency ... EdgeScan owns ^KG adjacency") is out of date. R-04-3: verify_graph's docstring repeats the drop_graph claim (admin.py:858-861; F-0408). R-04-4: `_sync_nkg` calls Build2HopStats again (schema.py:2908) after BuildNKG has just run it (TraversalBuild.cls:309). R-04-5: nodes_edges.py:517-529 `backfill_2hop_exact` has the same return-0 swallow, outside the named scope.

**Limitations**: TraversalBuild's ^NKG rewrite (340-820) was swept, not read line by line. I did not trace who reads the status hints at runtime.

## Module 05 temporal

| File | Lines | Coverage | Conventions judged |
| --- | --- | --- | --- |
| TemporalIndex.cls | 1651 | convention sweep, plus every hit method read (InsertEdge, WriteStores, BulkInsertCounts, Delete/Remove, Erase*, RetireExpired, Migrate*) | 4,5,8,9,13,14,19,21-26,30,34,40G2 |
| TemporalIndexMS.cls / TemporalPolicy.cls / TemporalWindow.cls | 19 / 274 / 444 | full (Window body: sweep of its walk 128-437) | 4,9,13,14,18,21-26,34,40G2 |
| _engine/temporal.py | 1155 | sweep, plus write paths read (98-118, 196-335, 400-476, 720-830) | 2,15,16,17,18,19,34,35,40G2 |
| temporal_window.py / temporal_only_warning.py / _tz.py | 171 / 82 / 40 | full | 2,17,35 |
| migrations/temporal_structural_rows.py | 116 | full | 2,17,34,35 |
| scripts/sweep_bare_nodes_interim.py / backfill_temporal_edges.py | 105 / 198 | full | 17,35,40G2 |

| ID | Conv. | Location | What deviates |
| --- | --- | --- | --- |
| D-05-01 | C-2 | _engine/temporal.py:292 | `# type: ignore[call-arg]` with no stated justification |
| D-05-02 | C-4 | TemporalIndex.cls:818 | PurgeBefore: `Set tGKey = 0  // default graph`, an inline derivation (ADR-0003:68; ADR-0003:53 counts these "hardcoded Set tGKey = 0") |
| D-05-03 | C-4 | TemporalIndex.cls:1149-1157, 1194, 1236-1246 | The flat-to-graph migration writes the default key as a literal 0 |
| D-05-04 | C-9 | TemporalWindow.cls:143-174, 209-233, 276, 309-437 | TemporalWindow extends %RegisteredObject (33), not TemporalIndex, yet reads tout/tin/edgeprop/tlast directly, partly through `^KG(tStore, ...)`. ADR-0002:9-11 forbids reads too, and the write-only guard (tests/unit/test_temporal_single_owner.py:8-12) cannot see reads |
| D-05-05 | C-14 | TemporalIndex.cls:1 | No class header, although ARCHITECTURE.md:196, :203 make the header the reference for the temporal index |
| D-05-06 | C-16 | _engine/temporal.py:280-287 | Says "Edges are only mirrored into the rdf_edges SQL table when graph= is supplied" and that a shadow is written at `^KG("out",0,...)`. In the glossary every Temporal Edge implies a Structural Edge in its own graph (CONTEXT.md:65-72) |
| D-05-07 | C-17 | _engine/temporal.py:114-118, 324-332 | The create_edge_temporal mirror (no adjacency index, graph given): a failed endpoint or row insert is logged and the call returns True |
| D-05-08 | C-17 | _engine/temporal.py:469-473 | The same in bulk_create_edges_temporal: the count returned does not reflect a missing row |
| D-05-09 | C-17 | scripts/backfill_temporal_edges.py:130-131, 139-140 | `except Exception: pass` around create_node writes |
| D-05-10 | C-35 | scripts/backfill_temporal_edges.py:182-184 | Hard-coded `Graph_KG.nodes`/`kg_NodeEmbeddings`, not the engine's schema |
| D-05-11 | C-22 (sec.) | TemporalIndex.cls:46, 64 | An `As %Status` method returns the literal `1`, not `$$$OK` |
| D-05-12 | C-25 (sec.) | TemporalIndex.cls:659 | GetDistinctCount: `If predicate '= "" && (...)` |
| D-05-13 | C-25 (sec.) | TemporalIndex.cls:1521, 1526, 1534, 1535 | GetBucketGroups: same pattern, four lines |
| D-05-14 | C-25 (sec.) | TemporalIndex.cls:1614 | GetBucketGroupTargets: same pattern (all style only, since left-to-right evaluation gives the intended result) |

**Borderline**: B-05-1: TemporalPolicy.cls:99 turns found keys into names in ListAll (an enumerator, as B-04-5). B-05-2: the C-30 paths without the adjacency index. InsertEdge writes only a shadow (TemporalIndex.cls:112-113), and DeleteTemporalEdge's `Remove` (338-340) removes the structural entry without any marker test. C-30's wording concerns the row, and the fallback is documented as such (Adjacency.cls:689-693). See candidate N-05-a. B-05-3: TemporalPolicy.cls:14-16 says the class is "the only writer of the registry", but snapshot restore writes it (snapshot.py:163, 408). ADR-0015:12-13 against :29. B-05-4: broad catches that report the failure: backfill_temporal_edges.py:154-155 and 165-166 (printed per failure, with run totals); temporal.py:446-447 (specific errors, counts fall back to 0). B-05-5: sweep_bare_nodes_interim.py:36-63 hard-codes `Graph_KG`, but it targets 4.4.1/4.4.2, before ADR-0016's record existed.

**Conforming**: C-4 TemporalIndex.cls:50, 153, 327; TemporalWindow.cls:47, 308; TemporalIndexMS.cls:15. C-9 TemporalIndexMS.cls:13-17 (subclass, ADR-0002:10). C-13/C-34: TemporalPolicy.cls:41-58 is the writer; registry read at TemporalIndex.cls:109, 277, 966, temporal.py:743, 751, temporal_structural_rows.py:98. C-16 temporal.py:260-271, 406-419 match the Collision glossary entry (CONTEXT.md:173-177). C-18 TemporalPolicy.cls:133 ("register it temporal-only"); TemporalWindow.cls:324 ("rebuild it once"). C-19 TemporalIndex.cls:94-96, 328. C-30 TemporalIndex.cls:109-114, 335-337. C-35 temporal.py:109-110 and temporal_structural_rows.py (via `engine._t`). C-40G2 TemporalPolicy.cls:175-215 and TemporalIndex.cls:1103-1108 (`TROLLBACK 1` to the level found); temporal.py:322, 474. C-21 TemporalIndex.cls:366-377. C-15: no hits.

**Reviewer notes**: R-05-1: temporal.py:277 advises "call Purge() and rebuild". Purge wipes every graph's index (F-0507). R-05-2: temporal_structural_rows.py:107 says create_edge "commits per call", which is out of date since 4.6.4. R-05-3: sweep_bare_nodes_interim.py:19-20 says gen/degc are "killed here"; the code does not kill them, and it calls ArnoAccel.BumpVersion (80; F-C1040 family). R-05-4: temporal.py:210 accepts only JSON `true` as the marker, while Adjacency.IsTemporalMarked accepts `= 1` (F-0505). R-05-5: temporal.py:294 passes 0 for a missing time, and InsertEdge defaults only `""` (TemporalIndex.cls:51) (F-0502).

**Limitations**: TemporalIndex's analytics readers (632-806, 1406-1651) were swept, not read line by line. Whether no install still lacks the adjacency index is outside source reading.

## Module 06 vectors

| File | Lines | Coverage | Conventions judged |
| --- | --- | --- | --- |
| IVFIndex.cls / VecIndex.cls / PLAIDSearch.cls | 285 / 477 / 256 | full on headers and write paths; sweep of the scoring maths | 4,14,21-26,40G2 |
| EmbedQueue.cls / EmbedQueueTask.cls | 375 / 34 | full | 4,14,18,21-27,35 |
| embedding_identity.py / embed_selector.py / _widths.py | 241 / 176 / 32 | full | 2,16,28,35 |
| vector_utils.py | 472 | full | 2,17,27,35 |
| _engine/vector.py vector parts (56-916, 1055-1381, 1453-1748, 1880-2068) | 2068 | sweep, plus every hit read | 2,17,27,35 |
| _engine/embeddings.py | 2164 | sweep, plus write paths read (500-545, 990-1290, 1400-1500, 1830-2120) | 2,16,17,18,27,28,35,40G2 |
| migrations/graph_scoped_embeddings.py / docs_and_edge_vectors.py / kg_node_stores.py | 1469 / 678 / 432 | sweep, plus vector-writing and identity paths | 2,17,18,27,28,35,40G2 |
| _engine/schema.py registry half (538-602, 987-1514, 1811-1831) | 3397 | named part (file >3,000 lines) | 17,28,35 |
| iris_vector_graph/schema.py kg_KNN_VEC (2144-2156, 2437-2483) | 3360 | named part | 24,27,35 |

| ID | Conv. | Location | What deviates |
| --- | --- | --- | --- |
| D-06-01 | C-14 | IVFIndex.cls:1 | No class header (ARCHITECTURE.md:199, :203) |
| D-06-02 | C-14 | PLAIDSearch.cls:1 | No class header |
| D-06-03 | C-14 | EmbedQueue.cls:23-25 | The class description says the embedding "is performed Python-side". ProcessBatch embeds through SQL `EMBEDDING` and writes vectors itself (308-320), and EmbedQueueTask runs it (EmbedQueueTask.cls:1-6) (F-0603 family) |
| D-06-04 | C-14 | VecIndex.cls:4, 9 | The header lists mahalanobis as a supported metric, but Metrics/CheckMetric refuse it since 4.7.0 (26-40) |
| D-06-05 | C-17 | _engine/schema.py:1054-1056 | get_embedding_identity turns an unreadable registry into None (no identity), which the write-path check then passes (F-0601) |
| D-06-06 | C-17 | _engine/embeddings.py:1916-1918 | process_embed_queue: a failed claim answers `{"processed": 0, "errors": 0}`, the same as an empty queue |
| D-06-07 | C-17 | _engine/embeddings.py:2084-2086 | clear_done (deletes entries): `except Exception: return 0` |
| D-06-08 | C-17 | _engine/embeddings.py:2117-2119 | start_background_embedding (saves and starts a task): `except Exception: return ""` |
| D-06-09 | C-17 | migrations/kg_node_stores.py:285-287 | An exception from the iFind repair (a write) is logged at debug level and the migration goes on |
| D-06-10 | C-27 | _engine/vector.py:368 | edge_vector_search builds `TO_VECTOR(?, dtype, dim)` for the query vector (F-0612) |
| D-06-11 | C-27 | _engine/vector.py:1239-1240 | vector_search does the same (F-0612 "table searches") |
| D-06-12 | C-27 | vector_utils.py:111-124 | check_hnsw_availability puts the column's declared width into the query `TO_VECTOR`, the exact pattern ADR-0005:16-19 forbids |
| D-06-13 | C-27 | vector_utils.py:319-321 | benchmark_vector_search does the same |
| D-06-14 | C-35 | vector_utils.py:26, 46-50, 295, 322, 352 | VectorOptimizer, which is public (`__init__.py:94`), hard-codes `_SCHEMA = "Graph_KG"` for reads and writes and takes no schema |
| D-06-15 | C-25 (sec.) | IVFIndex.cls:34 | Build: `If assignmentsJSON '= "" && (...)` |
| D-06-16 | C-25 (sec.) | IVFIndex.cls:200 | Insert: `If metric = "cosine" || (...)` |
| D-06-17 | C-25 (sec.) | EmbedQueue.cls:313 | ProcessBatch: `If rs.%SQLCODE = 0 && rs.%Next()` (style only) |

**Borderline**: B-06-1: embed_selector.py:35 `# type: ignore[no-redef]`. The if/else fallback for when pydantic is missing makes the reason visible, but no comment states it. B-06-2: broad catches whose failure reaches the caller: vector_utils.py:247-249 (counted `failed`; F-0613 is the success flag); embeddings.py:1409-1414, 1474-1480, 1599-1605, 1665-1671 (returned `errors`; F-0614); embeddings.py:2030-2031 (the caller already counted the error); _engine/schema.py:597-602 (per-step outcomes returned); graph_scoped_embeddings.py:1011-1017 (warning names the remedy; rationale at 1004-1006); kg_node_stores.py:255-256 (a later check raises); embeddings.py:1891-1892. B-06-3: vector_utils.py:239 converts a *stored* vector with a width, which ADR-0005:21-23 does not cover. B-06-4: graph_scoped_embeddings.py:99 matches `UPDATE Graph_KG.`; this 3.2.0→4.0.0 step predates ADR-0016.

**Conforming**: C-27 schema.py:2469 and 2144-2156 (no embedding_dimension); PyOps.cls:335; translator.py:3235, 3295-3296; EmbedQueue.cls:316 (stored value). C-28: identity is in the registry (embedding_identity.py:8-10; _engine/schema.py:1426-1481); `metadata` holds the caller's data only (embeddings.py:997, 1014). C-35 embeddings.py:1014, 1193 (`self._t`); docs_and_edge_vectors.py:154-225 (schema parameter); embed_selector callers pass `self._schema_prefix` (embeddings.py:1332-1335). A `Graph_KG` literal in a deployed class (EmbedQueue.cls:282) is B-5, not a deviation. C-40G2 embeddings.py:1022-1024, 1482, 1673; `_create_route` refuses inside a caller's transaction before it commits (532-537). C-18 graph_scoped_embeddings.py:1014 ("declare them"); EmbedQueue.cls:298-300 ("create it with ..."). C-21/22 EmbedQueue.cls:35-60, 138-150; EmbedQueueTask.cls:15-30. C-15, C-23, C-24 (in ObjectScript): no hits. C-4: no graph key in these classes. C-2: none apart from B-06-1.

**Reviewer notes**: R-06-1: ADR-0005:17-18 says `embedding_dimension` "exists, is accepted, and is read nowhere"; schema.py:2150 shows it was removed in 4.0.0, so the ADR text is out of date. R-06-2: the glossary says a write under another model "is refused" (CONTEXT.md:154-157), while the code routes it (F-0617). That is the glossary's error, not a C-16 deviation in code. R-06-3: VecIndex keeps Mahalanobis/SetInverseCov (119-142), which no search reads. R-06-4: vector.py:399-409 silently turns an invalid k into 50 (read path).

**Limitations**: the scoring maths in IVF/PLAID/VecIndex and the migrations' row moves were swept, not read line by line. Vector parts of vector.py are taken as everything outside module 07's ranges.

## Module 07 text search

| File | Lines | Coverage | Conventions judged |
| --- | --- | --- | --- |
| BM25Index.cls | 635 | full | 14,18,19,21-26,29,40G2 |
| SqlProcs.cls kgBM25 (115-135) / Service.cls HybridSearch (286-302) / PyOps.cls HybridSearch (370-421) with RouteVectorRows (305-349) | 227 / 347 / 430 | named parts | 14,21-24,27,35 |
| text_search.py / fusion.py / operators.py | 255 / 309 / 146 | full | 2,15,16,17,35 |
| _engine/vector.py kg_TXT (917-1054), kg_RRF_FUSE (1382-1452), bm25_* (1749-1879) | 2068 | named parts, full read | 2,17,18,27,35,40G2 |
| schema.py kg_TXT/kg_RRF_FUSE (2485-2581) | 3360 | named part | 24,35 |
| cypher/translator.py ivg.bm25.search/ivg.retrieve (3145-3375) | 31908 | named part (file >3,000 lines: convention sweep) | 2,27,35 |

| ID | Conv. | Location | What deviates |
| --- | --- | --- | --- |
| D-07-01 | C-14 | BM25Index.cls:28-29 | Says stopwords are stored "at class-load time". InitStopwords runs on the first Tokenize (41-50, 58) |
| D-07-02 | C-29 | BM25Index.cls:97-175 | Build kills the index and writes df, doc and the counters with no index lock and no transaction (ADR-0007:3-5) (F-0701) |
| D-07-03 | C-29 | BM25Index.cls:587-591 | Drop kills the index without the write lock (F-0701) |
| D-07-04 | C-35 | text_search.py:44-55, 73-84 | search_documents and its fallback name `{table_name}` ("docs") unqualified, so it resolves outside the IVG Schema (ADR-0016:12) (F-0711) |
| D-07-05 | C-35 | text_search.py:22-29 | With no `schema=`, TextSearchEngine falls back to the module prefix or literal `Graph_KG`. It skips `IVG_SCHEMA_PREFIX` and the record (schema_name.py:167-172) |
| D-07-06 | C-40G2 | BM25Index.cls:486-490 | Insert's Catch runs a bare `TRollback`, which ends the caller's transaction. BM25Index is missing from CHANGELOG.md:422's list of classes that roll back only to their level |
| D-07-07 | C-40G2 | BM25Index.cls:507-511 | Delete, the same |
| D-07-08 | C-25 (sec.) | BM25Index.cls:241, 309 | SearchCore: `If N = 0 \|\| (...)`, `If df = 0 \|\| (...)` (style only) |

**Borderline**: B-07-1: Upgrade (526-581) writes under the lock but outside a transaction. ADR-0007:5 says "every write ... in a transaction", but Upgrade's own contract is a re-runnable single pass (519-524). B-07-2: `SELECT TOP ... ORDER BY` outside ObjectScript: text_search.py:49-54 and 78-83; vector.py:979-984, 998-1002; schema.py:2513-2522 and 2545-2578; translator.py:3330-3352, where 3336-3337 documents that IRIS needs TOP with an ORDER BY in a CTE; PyOps.cls:337-345, a Python-language method. Same as round-1 B-4. B-07-3: Service.cls:1 and PyOps.cls:1 have no class header, but only their HybridSearch parts are in scope. B-07-4: B-2 family: BM25Index.cls:130 (`Do stmt.%Prepare(sql)` unchecked) and 59-61 (the iFind tokenizer's documented fallback).

**Conforming**: C-29 Insert/Delete take the lock, `TStart` and plain `Set` (BM25Index.cls:442-514, RemoveDoc 416-437). An unmigrated index is refused, naming Upgrade (392, which also meets C-18). C-17: every swallow in module 07 Python is on a read path (fusion.py:151-152, 204-205, 301-310; text_search.py:61-64, 90-92; vector.py:1435-1436), so the rule does not apply (F-0709, F-0711 cover the behaviour). C-27 translator.py:3235; PyOps.cls:335. C-35 vector.py:964 (`self._t("docs")`); schema.py `{table_schema}` throughout 2485-2581; SqlProcs.cls:126-129. C-15 text_search.py:23-25. C-16: BM25 docstrings match the BM25 Index, Document Frequency and Index Schema entries (CONTEXT.md:132-152; vector.py:1758-1773). C-21/22/23 Service.cls:286-302; SqlProcs.cls:131-135. C-26 BM25Index.cls:632. C-2: none.

**Reviewer notes**: R-07-1: BM25Index.cls:38 "once per process"; the stopword global outlives the process. R-07-2: BM25Index mixes four-space indentation with tabs (List, 630-633). R-07-3: "No SQL tables" (BM25Index.cls:4) means none are stored; Build does read `nodes`/`rdf_props`.

**Limitations**: in translator.py only the two procedure translators were read. Fusion's maths was not judged (no documented rule).

## Candidate findings (inspected-grade; not runtime evidence)

Existing findings: F-0409 (D-04-15), F-0407 (D-04-07), F-0408 (D-04-09, D-04-10), F-C0440 (D-04-04), F-0601 (D-06-05), F-0612 (D-06-10/11), F-0613 (B-06-2), F-0603 (D-06-03), F-0701 (D-07-02/03), F-0711 (D-07-04). New candidates:

1. **N-07-a: a failed bm25_insert/bm25_delete inside a caller's transaction rolls back the caller's work** (07; BM25Index.cls:486-490, 507-511; vector.py:1840-1855 calls with no Txn level). Any error inside the locked section ends every level. That includes a raced Upgrade (re-check at 459), `<PROTECT>`, or a `<SUBSCRIPT>` on an over-long token at 474 (the F-C0748 trigger). This is the same mechanism as F-0409 and breaks the 4.6.4 rule (PRE_RELEASE_CHECKLIST.md:354-356). Proposed S2, confidence medium (needs the F-0409 precondition: the engine shares the caller's process).
2. **N-05-a: without the adjacency index, deleting a triple's last timestamp removes an explicitly created edge's adjacency** (05; TemporalIndex.cls:334-341). The non-indexed branch calls `Adjacency.Remove` with no row test. The purge's equivalent keeps the shadow when an `rdf_edges` row exists (Adjacency.cls:689-733). The explicit row stays without its ^KG entry (Drift, CONTEXT.md:121-126) until `sync()`. Proposed S3, medium.
3. **N-05-b: without the adjacency index, create_edge_temporal(graph=...) and bulk_create_edges_temporal answer success when the structural mirror fails** (05; temporal.py:114-118, 320-332, 456-473). The edge stays temporal-only, against ADR-0009:11-12, with only a WARNING logged. Related to F-0506. Proposed S3, medium.
4. **N-04-a: backfill_deg2p_exact answers 0 when the rebuild fails** (04; _engine/schema.py:2952-2963). Build2HopExactStats kills the store and its stamp first (TraversalBuild.cls:1007), so a failure leaves it empty, and the caller cannot tell that from "no pairs". Proposed S4, medium.
5. **N-04-b: bulk_load_session ends normally when its closing two-hop rebuild or `sync()` fails** (04; nodes_edges.py:487-499). Nothing reaches `stats` or the caller. Proposed S4, medium.
6. **N-06-a: VectorOptimizer reads and writes `Graph_KG` whatever the namespace's IVG Schema** (06; vector_utils.py:26, 46-50, 235-240, 295, 322, 352). Under another schema it migrates or benchmarks the wrong tables, or fails. Same shape as F-0309 (module 03). Proposed S4, high.
7. **N-06-b: embed-queue admin calls answer "nothing done" when the call fails** (06; embeddings.py:1916-1918, 2084-2086, 2117-2119). A failed claim, clear or task start reads as an empty queue, 0 cleared, or no task id. Proposed S4, medium.
8. **N-07-b: TextSearchEngine without `schema=` ignores `IVG_SCHEMA_PREFIX`** (07; text_search.py:22-29). It reads `Graph_KG` unless a translator prefix was set in the process. Proposed S4, low (depends on process state).

Deviations that are not candidates: C-14/C-16 text, C-25/C-22 style, the C-27 cases where the length is the query's own (D-06-10/11, already F-0612) or where test vectors are made at that width (D-06-12/13), and kg_node_stores.py:285-287 (best effort, documented at 276-278).

## Conventions with no documented rule, and other limitations

No documented rule exists for: ObjectScript indentation, `Quit` versus `Return`, the `p`/`t` prefixes, single-line `If ... Set` forms, and class or method naming (round-1 L-2). There is none for Python docstrings and naming beyond the tools (L-3), for who owns and locks `^IVF`, `^VecIdx`, `^PLAID` and `^EmbedQueue` (ARCHITECTURE.md:153-160 gives layouts only), for fusion weights and scoring, or for time-zone handling (`_tz.py`). C-1 is left to the tool run; C-3 and C-20 are not judged. C-11, C-12 and C-33 do not apply to G2. Source reading only: N-05-a, N-05-b and N-07-a need a live check before they become findings.
