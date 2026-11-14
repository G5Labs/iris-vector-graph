<!-- markdownlint-disable MD013 -->

# Intent recovery: graph scope and structural storage (worker A-structure)

Product pin `3eaa79cf` (v4.7.0 + checklist). Read-only. No test, no IRIS. Tags: **(H)** human requirement or answered
question, **(D)** accepted design decision, **(O)** observed implementation only, **(P)** proposal. All commits carry one
author name, so a spec "Clarifications" answer is the strongest human-side evidence available here; it is still
secondhand. "SUSPECTED" means the interleaving or input is derived from source text and has not been run.

## Scope and sources inspected

| Locator | Revision / date | Authority | Inspected portion | Follow-up |
|---|---|---|---|---|
| `CONTEXT.md` (glossary) | pin | D (glossary of accepted terms; dated decisions inline) | Graph, Named Graph, Graph Key, Structural Edge, Multigraph mode, Adjacency Index, Interned snapshot, Degree, Rebuilt store, Graph-Version Token, Drift (lines 27-126) | Glossary claims checked below; several are stronger than the code |
| `docs/adr/0001` graph key first subscript | 2026-09-11, Accepted | D | all | Its "only TemporalIndex/EdgeScan touch ^KG" clause amended by ADR-0011 |
| `docs/adr/0003` two derivations | 2026-09-14, Accepted | D | all | Consequence "verify_graph reports existing violations" has no implementation found (F-Q3) |
| `docs/adr/0008` index maintained by engine | 2026-10-12; step 2 2026-10-20 | D | all | Consequence "^NKG interning cannot live in the index" contradicted by code (F9) |
| `docs/adr/0010`, `0012` degree | 2026-10-12 | D | all | 0012's lock rule later relaxed by 4.7.0 row 17 (`b741dbdc`, CHANGELOG:176-178), not by an ADR |
| `docs/adr/0011` one writer module | 2026-10-12 | D | all | Guard test scans ObjectScript only |
| `specs/234-multigraph-parallel-edges/{spec,tasks}.md` | created 2026-09-26; status "Partially implemented ... ledger/restore (US4) ... not done" (spec.md:5-6) | H (Clarifications session 2026-09-26, spec.md:39-53) + D (FRs) | spec.md all; tasks.md unchecked items | tasks.md checkboxes are not maintained (US3 work shipped yet unchecked); used only as weak evidence |
| `specs/248-alt-parity-os/{spec,plan}.md` | 2026-10-12, "Draft (exploratory, not adopted)" but shipped in 4.3.0 | D (design text) | edge cases spec.md:70-77; plan.md:28-36 | Status line stale |
| `specs/252-adjacency-functional-index/spec.md` | 2026-10-19, "Draft", shipped 4.3.0 (CHANGELOG:3031-3039) | D | FR-001..016, SC, assumptions (lines 104-160) | |
| `specs/242,243,245` (alt adjacency helpers/readers/owner) | 2026-10-12, "exploratory, not adopted" | D (superseded by shipped code) | status lines, FR list of 242 | Not relied on beyond naming |
| `specs/244-alt-freshness-module/spec.md` | 2026-10-12, Draft, "not adopted"; FR-008 "No existing file changes. The engine wiring is a later decision" | D (module contract only) | all | `iris_vector_graph/freshness.py` is imported by nothing in the product |
| `specs/236-arno-callout-adoption/research-token-audit.md` | 4.2.x era | D (recorded audit + fixes) | lines 15-40, 145-175, 255-290 | Its own "bump after TRollback" reasoning (fix 3) is applied to BuildKG only (F1) |
| `CHANGELOG.md` | 4.1.0 (3623-4046), 4.3.0 (2788-3166), 4.7.0 (5-277) | D/O (release record) | multigraph 3830-3853; spec 252 3031-3050; degree 2952-2958; row 17 174-178 | |
| `docs/KNOWN_ISSUES.md` | 4.6.0 issues | D/O | first two entries | |
| `docs/API_REFERENCE.md`, `docs/USER_GUIDE.md` | pin | D (public contract) | create_edge 474-487, delete_edge 502-514, delete_node 516-522, set_multigraph/is_multigraph 2678-2716, USER_GUIDE 465-473 | |
| `iris_src/src/Graph/KG/GraphKey.cls` | pin | O | all (87 lines) | |
| All `GraphKey.For*` callers (28 ObjectScript classes, 3 Python files) | pin | O | grep inventory; Adjacency, Eraser, LedgerApply, GraphMode, AlgoCache, TraversalBuild, TraversalKHop, GraphVerify, GraphStores read in place | Cypher/Exec, Temporal*, FHIR callers only grep-checked |
| `Adjacency.cls`, `Adj.cls`, `AdjIndex.cls`, `LabelIndex.cls`, `GraphIndex.cls`, `GraphMode.cls`, `GraphVerify.cls`, `Txn.cls`, `PropWrite.cls`, `AlgoCache.cls` | pin | O | all | |
| `LedgerApply.cls` | pin | O | FindEdge 144-157, AllocStmt 160-170, ResolveRef 173-212, OpCreateRel 450-528, PersistQuals 552-565, DeleteRelInternal 652-693 | Ledger semantics proper belong to A-history |
| `Eraser.cls` | pin | O | EraseGraph 47-260, EraseEdges 395-462, EraseIdSet 467-632 | Erasure semantics belong to A-history |
| `TraversalBuild.cls`, `TraversalKHop.cls` | pin | O | BuildKG 30-172, MergedDegree 836-850, Build2HopStats 939-992; KHopCount 1-21, Fresh 236-243 | |
| `iris_vector_graph/_engine/nodes_edges.py`, `_write_txn.py`, `_validate.py`, `admin.py`, `snapshot.py`, `stores/iris_sql_store.py`, `stores/lazy_kg.py`, `freshness.py`, `algo_cache.py`, `cypher/translator.py:441-457` | pin | O | create_node 968-1115, create_edge 1151-1304, set_edge_weight 1306-1380, delete_edge 1382-1456, delete scopes 2134-2268; WriteTxn all; restore 1077-1600, 1654-1693 | |
| Tests (see per-capability lists) | pin | evidence only | headers and test names; a few bodies | None run (brief) |

## Capabilities

### C1. Graph scope and the Graph Key derivations

Governing statements

- (D) Every node, structural edge, adjacency entry belongs to exactly one graph; the default graph is the one named `""` (CONTEXT.md:27-31). Named graphs are storage-isolated: "two named graphs' content never shares an index entry" (CONTEXT.md:33-36).
- (D) The graph key is the first subscript of every `^KG` store; the default graph is integer `0` (ADR-0001:9-24).
- (D) Two derivations, never a conversion: `ForIndex` (`^KG`, default `0`) and `ForLedger` (`^IVG.Ledger("tuple")`, default `$Char(1)`); "No module may derive a graph key inline"; "a caller holding only a key and not the graphId it came from is a design error"; both reject `"0"` and `$Char(1)` (ADR-0003:10-27, 66-74). Reason for keeping `$Char(1)`: IRIS canonicalizes subscript `"0"` to `0` (ADR-0003:42-48).
- (D) "A scoped lookup never falls through to the default graph: a wrong key reads nothing, never another graph's data" (CONTEXT.md:57-58).
- (O) A third derivation `ForName` gives the SQL `graph_id` spelling (GraphKey.cls:58-69). `Validate` strips every `$Char(0)` (not only padding) and rejects `"0"` and any other control character (GraphKey.cls:38-48, 82-85). ADR-0003's table still shows `$ZStrip(graphId,"*C")` (ADR-0003:14); the code rejects instead of stripping.
- (O) Python mirror `validate_graph_name` / `graph_index_key` (`_validate.py:19-71`) rejects `ord<32` and `127` only; IRIS's `$ZStrip` "C" class also covers C1 controls 128-159 (my understanding of IRIS; unverified), so a name with `\x85` passes Python and is refused by `ForIndex` inside IRIS.

Operations (entry -> derivation -> store)

- Index form (`ForIndex`): Adjacency.RowPut/RowRemove/RowUpdate (Adjacency.cls:482, 496, 507-509), PutLabel/RemoveLabel (773, 784), GraphMode (GraphMode.cls:18, 30), AlgoCache (AlgoCache.cls:30, 48, 56), Eraser (Eraser.cls:50, 328, 374, 397, 1210), LedgerApply's `^KG` writes (LedgerApply.cls:505, 561, 688), TraversalBuild row loops (82, 111, 190), GraphVerify (42), GraphStores (191), PageRank/Centrality/TraversalBFS/TraversalPaths/VarLength/Cypher Exec. Each touches `^KG`, `^IVG.GraphMode`, `^IVG.AlgoCache` or `^IVG.TemporalStructural`, all index-keyed. Correct store/derivation pairing at every inspected site.
- Ledger form (`ForLedger` via `Ledger.GKey`, Ledger.cls:49): LedgerApply tuple index (165, 192, 391, 473, 680), Eraser tuple kills (672-677, 1139), LedgerRedact (463). Correct pairing.
- Inline default-graph `0` without a derivation (O): `TraversalKHop.cls:15-20, 29, 63, 218` (default-graph-only readers by documented design), `Algorithms.cls:12, 95`, `TemporalIndex.cls:818, 1149-1246` (flat-layout migration). None takes a graph argument, so none can fall through from a named graph; they violate ADR-0003's "no inline derivation" in letter only.
- Inverse conversions key -> name (O, contrary to ADR-0003's "never a conversion" in spirit): `Adjacency.cls:583, 627, 654, 698` (`$Select(pGKey = 0: $Char(0), 1: pGKey)`), `Adjacency.cls:889`, `EdgeScan.cls:97`, `Cypher/Exec.cls:226, 740, 878`, `TemporalPolicy.cls:99`, `nodes_edges.py:1432`, `lazy_kg.py:78`. They are injective inverses of `ForIndex` given that `"0"` is rejected, so no wrong-graph result follows; the risk is a second owner of the mapping.
- Python passes the *raw* name to SQL while the index uses the canonical one: `create_edge` binds `gid = graph or ""` (nodes_edges.py:1213) after `graph_index_key(graph)` canonicalized only the key (1197); `create_node` binds `graph if graph is not None else ""` without any validation (nodes_edges.py:1019). A name carrying `\x00` would key `^KG` as the stripped name and SQL as the padded name (O; impact unverified).

Outcome-changing cases

- `""`, `None`, `$Char(0)` -> default graph in every store (GraphKey.Canonical; Python `replace("\x00","")`).
- `"0"` refused by both validators; but `create_node(graph="0")` has no Python check and writes a `nodes` row in graph `'0'`; the label functional index then calls `ForIndex("0")`, which throws (behaviour of a throwing functional-index callback not verified).
- Legacy rows whose `graph_id` is `"0"` or holds a control character: every rebuild path calls `ForIndex` per row (TraversalBuild.cls:82, 111, 190; AdjIndex via RowPut) and throws; TraversalBuild's own comment names this failure (lines 46-49). ADR-0003 says `verify_graph` reports such graphs; no code found that lists them (`GraphVerify.VerifyGraph` starts with `ForIndex(pGraph)` and so throws on `"0"`).
- Numeric-looking names: `"1"` or `"-1"` are canonical numbers and collate before/after `0`; round trips through `$Order` give the same text back. A canonical decimal such as `".5"` may come back from the Python driver as a float and print as `"0.5"` (lazy_kg.py:78 uses `str(key)`). Unverified driver behaviour; low priority.
- `^NKG` has no graph dimension (CONTEXT.md:97-101). Readers that use it refuse when any named graph has an edge: `NKGAccel.RefuseMergedGraphs` (NKGAccel.cls:208-224), Python `named_graph_with_edges` (lazy_kg.py:45-62) used by algorithms (algorithms.py:171-176). This is the one store where a "wrong key" would merge graphs, and it is guarded by refusal, not by keying.

Tests: `tests/unit/test_graph_key_module.py` (source-text, 6 tests), `tests/integration/test_graph_key_behaviour.py` (live, 11), `tests/integration/test_ledger_adjacency_graph_key.py` (live, 12), `tests/e2e/test_delete_graph_scope_e2e.py`, `test_460_r184_default_graph_scope_e2e.py`, `test_use_graph_scope_shapes_e2e.py` (live).

Seed claim "Graph scope" (index.md): **confirmed**, with corrections. Both keys derive from the name at every inspected `^KG`/ledger site. Corrections: (a) there are three derivations (`ForName` is the third); (b) the "never a conversion" rule is kept for index<->ledger but not for index->name (ten sites above); (c) the ADR-0003 promise to report legacy `"0"` graphs is unimplemented.

### C2. Node, edge and property CRUD in the engine; delete cascades

Governing statements

- (D) `create_edge`: endpoints and edge in one transaction; True for a new edge or an adopted temporal row, False for a duplicate; IRIS refusal raises `GraphWriteError` with nothing written (docstring nodes_edges.py:1160-1194; API_REFERENCE.md:474-487).
- (D) `delete_edge` deletes one graph's row(s) of the triple; `all_graphs=True` every graph's; True even when nothing matched (nodes_edges.py:1390-1403; API_REFERENCE.md:514).
- (D) `delete_node` deletes the node "with its labels, props, documents, vectors and incident edges, and the reifier nodes of those edges"; omitted `graph` means "the one graph holding it", and an id held by two graphs is refused (API_REFERENCE.md:522; nodes_edges.py:2202-2268, 4.6.0 #112).
- (D) IVG's write is a nested level in a caller's transaction: commit lowers `$TLEVEL`, undo takes back IVG's level only (`_write_txn.py:1-28`; `Txn.cls:15-58`, 4.6.4).
- (D) An edge's weight lives in its row's `qualifiers` (spec 252 FR-015; CHANGELOG:3040-3042).
- (O) `PropWrite.SetVal` writes the row's data node directly only when new and stored values have equal text and different type, under the row lock and in the caller's transaction (PropWrite.cls:1-62). It changes no index value and no adjacency; out of the structural-model core.

Operations

- `create_edge`: `IRISGraphEngine.create_edge` (engine.py:162) -> `NodesEdgesMixin.create_edge` (nodes_edges.py:1151) -> `WriteTxn.begin` (`Txn_Begin`, Txn.cls:19-31) -> `_ensure_edge_endpoints` (1106-1150) -> guarded `INSERT ... WHERE NOT EXISTS ... AND ekey = 0` (1214-1219, `_ekey_guard` 1257-1273) -> with the index declared, `AdjIndex.InsertIndex` -> `Adjacency.RowPut` -> `Put`/`PutKeyed` inside the row's transaction (AdjIndex.cls:12-15; Adjacency.cls:477-488); without it, `EdgeScan.WriteAdjacency` over the Native API before commit (1221-1235) -> `txn.commit` (`Txn_End`) -> readers: `^KG("out"/"in")`, `Adj.Degree`. On a duplicate: `_adopt_temporal_row` (1275-1304) updates a marked row in place.
- `delete_edge`: `DELETE ... WHERE s,p,o_id AND COALESCE(graph_id,'') = ?` (1429-1433) -> per-row `AdjIndex.DeleteIndex` -> `RowRemove` -> `Remove`/`RemoveKeyed` (Adjacency.cls:491-501); non-indexed: `EdgeScan.DeleteAdjacency[AllGraphs]` (1434-1446). In a multigraph it deletes every parallel edge of the triple (no `ekey` parameter).
- `delete_node`: `_delete_scopes` (2202-2225) -> `_delete_in_scope` (2176-2200) -> `store.delete_nodes` -> `Eraser.EraseNodeIds` (Eraser.cls:372) -> `EraseIdSet` (467-632): one `TSTART`; incident edge rows (two cursors, 497-528) via `EraseEdgeRow` (535, rows go through the index); `Adjacency.RemoveNode(pKey, tId)` (547) which kills the node's `gen` and `degc` (Adjacency.cls:373-381); labels, props, docs, vectors; `TCOMMIT`. Reifier nodes are deleted afterwards in separate transactions (nodes_edges.py:2191-2199), so a failure there leaves the node deleted and the reifiers present (documented in the raised message).
- `set_edge_weight`: default graph only; updates every row of the triple in one transaction (nodes_edges.py:1306-1380); the index's `RowUpdate` reweights (Adjacency.cls:505-534).

Outcome-changing cases

- Duplicate create in mode off: NOT EXISTS skips; concurrent duplicate -119 is swallowed as `inserted = 0` (1243-1245).
- Caller transaction open vs not; driver autocommit off (`Txn_Begin(1)`, Txn.cls:26-28); namespace without `Txn_Begin` (plain START TRANSACTION, `_write_txn.py:177-210`).
- Non-indexed namespace: the `^KG` write may go over a separate Native API connection, so a rollback leaves the `^KG` entry (message at nodes_edges.py:1247-1249). Drift by design in legacy namespaces.
- `delete_edge` and reifications: `rdf_reifications` has no foreign key to `rdf_edges` (schema.py:514-520). `delete_edge` deletes rows only; the ledger's `delete_rel` (LedgerApply.cls:654-670), `EraseEdges` (Eraser.cls:390-393) and Cypher `DETACH DELETE` (CHANGELOG:179) cascade reifications. Unresolved (F-Q1).

Tests: `tests/e2e/test_252_writer_paths_e2e.py` (live, 20; one per FR-005 writer path), `tests/e2e/test_set_edge_weight_txn_e2e.py` (live), `tests/e2e/test_duplicate_edge_cost_e2e.py` (live), `tests/e2e/test_delete_graph_scope_e2e.py` (live).

### C3. Multigraph mode and edge identity

Governing statements

- (H, spec 234 Clarifications 2026-09-26, spec.md:41-53) Opt-in; **per graph** including the default graph, in `^IVG.GraphMode(gKey)`; parallel edges as children under the existing leaf only while 2+ share a triple; degree counts live edges; PPR/PageRank/Arno use set semantics; `create_edge` keeps True/False and a new `create_edge_returning_id()` returns the `edge_id`.
- (D) FR-002: enabling always allowed; disabling fails with `parallel_edges_present` while any triple has more than one live row (spec.md:215-218). FR-003: `u_spo_graph_ekey (s,p,o_id,graph_id,ekey)`; "In single-edge graphs every writer writes `ekey = 0`, so the constraint still enforces one edge per triple" (221-226). FR-004: leaf = weight of lowest live `ekey` (229-233). FR-006: `BuildKG` result MUST equal incremental writes (240-242). FR-007: in a multigraph `create_edge` MUST always create a new edge (246-250). FR-013: ledger tuple index keyed with `ekey`, `ambiguous_tuple` (283-291). FR-014: restore of an archive without `ekey` lands at 0 (295-303).
- (D) Spec status: "Mode, storage and Cypher shipped in 4.1.0; ledger/restore (US4) and SC-004 timing not done" (spec.md:5-6). CHANGELOG 4.1.0 (3835-3853) lists Cypher CREATE/MERGE/DELETE, `set_multigraph`, erase clears the mode, schema change; it does not mention `create_edge` or the ledger.
- (O) `GraphMode.Set(on)` writes the flag unconditionally; `Set(off)` counts parallel triples by SQL and then kills the flag, with no lock between the two (GraphMode.cls:26-45). `is_multigraph` is cached per engine (admin.py:917-926; documented "Cached per engine", API_REFERENCE.md:2684); the Cypher translator decides its SQL from that cache once per statement (translator.py:441-457).
- (O) The index decides per row from the live flag: `RowPut`/`RowRemove` read `^IVG.GraphMode(tG)` (Adjacency.cls:484, 497).

Operations

- Keyed write: `RowPut` -> `PutKeyed` (Adjacency.cls:210-269): absent leaf -> `Put`; leaf without `#` -> `OtherEdgeKeys` SQL (886-902) then children for every other row and this one; `#` = `KeyCount` recount (255); `gen` bump on a new child or the 1->2 transition (256); `SetLeafFromLowest` (874-881); token bump (260).
- Keyed delete: `RowRemove` -> `RemoveKeyed` (275-321): no `#` -> if another row of the triple exists, no-op, else `Remove`; with `#` -> kill child, bump `gen`, recount, either re-point the leaf or collapse to one edge.
- Rebuild: non-indexed `BuildKGKeyed` + `FillTriple` (Adjacency.cls:837-855); indexed `%BuildIndices` with up to 8 jobs (TraversalBuild.cls:126-136), which runs `RowPut` per row in several processes.
- Ledger: no `ekey` and no mode awareness anywhere in `Ledger*.cls` or `iris_vector_graph/ledger` (grep). `FindEdge` returns the first matching row (LedgerApply.cls:144-157); `AllocStmt` keeps one statement per triple (160-170); `DeleteRelInternal` deletes that one row by `%ID` and then calls `Adjacency.Remove` on the whole triple whenever its leaf exists (678, 688-689), with no `Indexed()` guard (unlike OpCreateRel, 508-514).
- Restore: tables first (snapshot.py:1234-1300), then globals including `^IVG.GraphMode` (1554-1590; list at 386-407). A replacing restore first runs `erase_all`, which clears every mode (CHANGELOG:3846). No rebuild runs afterwards.

Outcome-changing cases

- Mode off, one row per triple (normal); mode off with a second row at `ekey<>0` (raw SQL, a stale per-engine mode cache, the `Set(off)` race, a restore before the mode flag lands): the index writes one leaf (`Put` overwrites), and deleting either row kills the leaf while the other row remains -> "missing" drift (F6).
- 0 -> 1 -> 2 -> 1 -> 0 edges; deletion of the lowest `ekey` (leaf re-points); repeated delete of a gone `ekey` (no second bump, 290).
- Two writers on one triple; one rolls back; `%BuildIndices` jobs processing two rows of one triple at once (F4).
- Ledger tuple refs to a triple with several live rows: picks the first row; `delete_rel` then removes the survivors' adjacency (F3); `upsert`/`set_qual` reweights the leaf to that row's weight even when it is not the lowest `ekey` (PersistQuals 552-565 calls `Reweight` unconditionally; F11).
- `create_edge` in a multigraph: still guarded on `ekey = 0` (nodes_edges.py:1214-1219), returns False for an existing triple; no `create_edge_returning_id` exists (grep). FR-007 unimplemented at the pin (F-Q2).

Tests: `tests/e2e/test_234_multigraph_storage_e2e.py` (live: mode set/refuse/erase, 1->3->1 layouts, BuildKG equals 200 random keyed ops, upgrade byte-identity), `test_234_multigraph_cypher_e2e.py`, `test_multigraph_rel_identity_e2e.py`, `test_460_one_hop_parallel_edges_e2e.py` (live: one-hop shortcut answers b, b, c), `test_degree_cache_live.py::test_parallel_edges_count_their_multiplicity` (live). None exercises concurrency, rollback, the ledger, or restore with parallel edges (grep of test bodies).

Seed claim "Edge identity" (index.md): **corrected**. The mode is per graph, not per deployment (spec.md:42-43). Mode-off `^KG` layout and SQL are unchanged (FillTriple 839-846; `_ekey_guard`), so the compatibility promise holds for cooperative writers. But one row per triple in a mode-off graph is enforced by writers, not by the constraint. At this pin the ledger surface (FR-013) and `create_edge` (FR-007) are unimplemented. The restore surface restores the mode flag after the rows, so a restore into an indexed namespace loses multiplicity (F5).

### C4. Adjacency Index ownership and the declared functional index; Drift

Governing statements

- (D) One module, `Graph.KG.Adjacency`, sets or kills `^KG("out")`/`("in")`; enforced by `tests/unit/test_adjacency_single_writer.py` with an empty allow-list (ADR-0011:12-17; Adjacency.cls:1-19).
- (D) Where declared, the index is derived from the rows: "every row written, changed or deleted by any path ... changes it in the same transaction, and it holds no entry without a row behind it" (CONTEXT.md:88-95; spec 252 FR-001, FR-016; ADR-0008:12-16, 43-46).
- (D) FR-004: every index change moves the source's generation and the token (spec 252:111).
- (D) "A declared Adjacency Index cannot drift from the rows; declaring it on a drifted install repairs it" (CONTEXT.md:121-126).
- (D, 4.7.0 row 17) A row writer whose shared lock is not granted in 5 s writes `^KG` without it, marks `^IVG.AdjNoLock(g)` and turns the degree cache off for that graph until a rebuild; reason: "IRIS's SQL filing does not read [an error status] from a functional index callback" (Adjacency.cls:51-73; CHANGELOG:176-178).
- (O) `Indexed()` is true only for a functional `idx_edges_adj` (Adjacency.cls:536-557; 4.7.0 row 16).

Operations

- Live: `AdjIndex.{Insert,Update,Delete}Index` -> `Adjacency.RowPut/RowUpdate/RowRemove` (AdjIndex.cls:12-26; Adjacency.cls:477-534); labels via `LabelIndex` -> `PutLabel/RemoveLabel` (LabelIndex.cls:10-28; Adjacency.cls:768-787). Commit boundary = the SQL row's transaction (caller's `WriteTxn` level or the Eraser/Ledger `TSTART`).
- Rebuild: `sync()` (schema.py:2859) -> `TraversalBuild.BuildKG` (TraversalBuild.cls:30-172): `BeginRebuild` takes `^IVG.AdjW#"S"`; indexed branch commits an almost empty transaction and then runs `%BuildIndices` (126-136), whose `PurgeIndex` is `RemoveAll` (AdjIndex.cls:29-32). The build therefore runs outside any transaction.
- Python second writer: snapshot restore sets `^KG("out"/"in")` lines directly in non-indexed namespaces (snapshot.py:1654-1693) and afterwards kills `degw`, `degc`, `gen` per graph written (1688-1691). The single-writer guard scans ObjectScript only (test_adjacency_single_writer.py:20-22).
- Verification: `GraphVerify.VerifyGraph` (GraphVerify.cls:39-160) compares rows with `^KG` per graph and checks current `degc` entries.

Outcome-changing cases

- SQL insert/update/delete from any path; `%NOINDEX` bulk loads (stale until their `%BuildIndices`; FR-008).
- Error status vs exception inside a callback: `Put`/`Remove` let exceptions propagate; `PutKeyed`/`RemoveKeyed` catch and return a status (Adjacency.cls:264-267, 316-319), which per 4.7.0 row 17 IRIS ignores, so the row stays without its entry (F10).
- Failure during indexed `%BuildIndices`: adjacency already purged, partial thereafter, not rolled back. This contradicts spec 248's edge case "out/in and the cache roll back together" (spec.md:74-75) and the BuildKG comment (TraversalBuild.cls:46-58), which describe the non-indexed path (F8).
- Row update moving an edge between graphs or endpoints: `RowUpdate` = remove old + put new (Adjacency.cls:510-516).
- `GraphVerify` on a multigraph: `tSqlEdges` counts rows, `tOutMatched` counts distinct triples, so `missing = rows - triples` is reported on every graph with parallel edges (GraphVerify.cls:65-78, 81-104, 105-128); it also never compares `#` with the row count. Open task T036 (tasks.md:198) names exactly this (F7).

Tests: `tests/unit/test_adjacency_single_writer.py` (source-text), `tests/e2e/test_adjacency_owner_live.py` (live), `tests/e2e/test_252_writer_paths_e2e.py`, `test_252_drifted_install_e2e.py`, `test_252_fresh_namespace_e2e.py`, `test_252_cypher_read_after_write_e2e.py` (live), `tests/unit/test_252_buildkg_parallel.py` (source-text: job count passed).

### C5. Degree and the generation-validated degree cache

Governing statements

- (D) Degree is counted from `out`, never stored; a parallel edge counts through `#` (ADR-0010:12-15; CONTEXT.md:103-107).
- (D) Served from `^KG("degc", g, src, key) = $LB(gen, count)` when `gen` equals `^KG("gen", g, src)`; writers bump `gen` under a shared lock `^IVG.AdjW(g)`; a reader stores only if its exclusive no-wait probe succeeded and `gen` did not move; the cache is derived (ADR-0012:12-17). "A rolled-back write over-bumps a generation, which only invalidates" (ADR-0012:23-25).
- (D) "Erase kills `gen`, so a counter restarts at 0. A reader that stored after the kill is detected by the post-store generation check" (spec 248 spec.md:76-77; plan.md:31-34).
- (O) A second serving path not in any ADR: the whole-graph warm stamp `^KG("degw", g) = ^KG("__version")`. While it equals the token, an entry is used without reading `gen` and an absent entry means 0 (Adj.cls:177-217). Readers: `TraversalKHop.KHopCount` (TraversalKHop.cls:13-20), `Centrality` (Centrality.cls:78-133), `TraversalBuild.MergedDegree` and `Build2HopStats` (TraversalBuild.cls:846-847, 955-978).
- (O) `Adj.Degree` also refuses to store while `^IVG.AdjNoLock(g)` is set (Adj.cls:75, 159), and turns a `<PROTECT>` store into "return the count" (Adj.cls:76-86).

Operations

- Reader: `Adj.Degree` (Adj.cls:52-89): read `gen` -> hit? -> probe `Lock +^IVG.AdjW(g)#"E":0` and release -> `Count` -> store if probe, no AdjNoLock, `gen` unchanged -> re-read `gen`, kill if moved. `Adj.Cached` (93-106) reads only. `WarmFill`/`WarmAll`/`WarmCache` (138-230).
- Writers (all in Adjacency.cls): `Put` 80-109 (out/in then `gen`++, token++), `PutShadow` 121-139 (bump only when new), `Remove` 147-167 (`gen`++ only if present, token++ always), `PutKeyed` 210-269, `RemoveKeyed` 275-321, `Reweight` 328-342 (token only), `RowUpdate` keyed 521-531 (`gen`++ though degree unchanged), `RemoveSource` 348-391 (kills `gen` then `degc`), `RemoveGraph` 428-447, `RemoveAll` 452-472, `BeginRebuild`/`FillEdge`/`FillTriple`/`EndRebuild` 814-869.
- Commit boundary: the writer's transaction. Inside it the shared lock's release is deferred (Adj.cls:17-21), so a reader's probe fails until commit or rollback; `$Increment` of `gen` and the token is not undone by rollback.

Outcome-changing cases

- Writer in flight (probe fails, count includes uncommitted entry, nothing stored); reader inside the writer's own transaction (stores, rolled back with it, Adj.cls:40-45); rollback after a read (entry never stored; `gen` over-bumped); lockless writer (AdjNoLock).
- `gen` killed by `RemoveSource` (every `delete_node` via `RemoveNode`, Eraser.cls:547), `RemoveGraph`, `RemoveAll`, restore (snapshot.py:1688-1691), then rebuilt by new writes to the same value: the pre-store check and the post-store re-read both pass (ABA, F2). A rolled-back erase restores the killed `gen` and `degc` values while other processes' increments in the window are overwritten (Kill is journaled, `$Increment` is not), which also moves `gen` backwards (F2).
- AllWarm: a writer bumps the token, so the stamp turns off. `BuildKG` stamps through `EndRebuild(1)` and then bumps the token (TraversalBuild.cls:142-145), so the stamp it just set is dead on arrival. Per-source entries stay valid; only the O(1)-per-node path is lost (S5).

Tests: `tests/e2e/test_degree_cache_live.py` (live, scratch namespace IVGPAROS: rollback race over two connections, reader in writer's transaction, multiplicity, erase clears, BuildKG warm, randomized sequence with rollbacks), `test_degree_warm_stamp_live.py` (live: stamp on/off, absent = 0), `test_adj_degree_live.py` (live), `tests/unit/test_degree_cache_writers.py` (source-text). No test interleaves a reader's recount with an erase and re-creation of the same source.

Seed claim "Adjacency and degree" (index.md): **confirmed with corrections**. One module writes `out`/`in` from ObjectScript, now mostly invoked by the functional index from any SQL path. The Python restore remains a second writer in non-indexed namespaces. A cached degree is also served without a generation check while the whole-graph stamp holds. The writer lock is best-effort since 4.7.0. Generation equality is not a sound freshness test across a `gen` kill (F2).

### C6. Graph-Version Token and Rebuilt stores

Governing statements

- (D) Token = namespace-wide counter that every write path able to change an algorithm's answer increments; "It never falls and is never reused. A cached algorithm result is valid only while the token it was computed under is current" (CONTEXT.md:116-119).
- (D) A Rebuilt store "records the Graph-Version Token it was built from. It is current while that equals the live token and stale otherwise, so a failed rebuild leaves it stale and every process gets the same answer" (CONTEXT.md:109-114; ADR-0008:23-26).
- (D) AlgoCache: token read before compute, stored with the answer; mismatch is a miss (AlgoCache.cls:1-13; iris_sql_store.py:921-987). Only pagerank, ppr, wcc, cdlp are cacheable (algo_cache.py:94).
- (D) Token audit fixes: `$Increment` everywhere; restore bumps after import; BuildKG bumps in its multigraph branch and "in the Catch ... after TRollback: a failed rebuild has already exposed a partial ^KG to readers (reads are uncommitted in IRIS)" (research-token-audit.md:149-171).
- (O) Per-store mechanisms differ. `deg2p`/`deg2p_exact` use `^IVG.BuiltFrom(store)` stamped with the token read first (TraversalBuild.cls:946-992, 1007-1065; reader TraversalKHop.cls:236-243). `^ArnoKG` stamps the token read before its build (ArnoAccel.cls:305-318). `^NKG` uses `^NKG("$meta","stale")`, `^NKG("$meta","version")` and the in-process `_nkg_dirty` flag (TraversalBuild.cls:399-425; engine.py:354; admin.py:802-805), and is also maintained incrementally by `Put`/`Remove` (Adjacency.cls:94-107, 161-165). `iris_vector_graph/freshness.py` is imported nowhere (spec 244 FR-008).
- (O) Restore writes the archive's values, then sets the token to `max(floor, current)` and bumps once more (`_raise_kg_version`, snapshot.py:48-58).

Outcome-changing cases

- Committed write during a compute: the entry is stamped with the pre-write token -> stale. Correct.
- **Uncommitted write visible during the compute, later rolled back**: the token was bumped by the write (not undone); the reader read the token after that bump, computed over the uncommitted content and stored the answer under the current token; nothing moves the token after the rollback, so the entry is current and wrong (F1). The same holds for `^ArnoKG` and the `deg2p` stamps. No AlgoCache path has a probe like ADR-0012's. `WriteTxn.rollback`, the Eraser catch blocks (Eraser.cls:260, 459, 630, 816, 1308) and the Ledger rollbacks do not bump after rolling back; only BuildKG does (TraversalBuild.cls:164-170).
- Node-only writes do not move the token. PageRank adds a node-set token to its key (algorithms.py:179-195, 787); not checked for wcc/cdlp (limit).
- `^NKG` interning inside a functional-index callback: `$Increment(^NKG(-3,s))`, `edgeCount` and `nodeCount` survive a rollback, and `InternNode`'s locks are held to commit inside a transaction (GraphIndex.cls:43-76). ADR-0008 lists both effects as the reason interning "cannot" live in the index (ADR-0008:66-67) (F9).

Tests: `tests/integration/test_236_token_write_paths.py` (live, ~30 write paths; test_25 checks only that a rolled-back bump is not undone, 485-494), `tests/unit/test_freshness.py` (in-memory host), `tests/unit/test_411_nkg_version_monotonic.py` (unit). No test computes a cached answer during an uncommitted write that is then rolled back.

## Candidate obligations for formal modeling

**O1. Graph-scoped storage keys (per store, injective, no cross-store use).**
L1: Each store keys a graph by its own derivation from the graph name. The default graph and every valid name map to distinct keys within a store. No operation scoped to graph g reads or writes another graph's entries. A name a store cannot represent is refused before any write.
L2: `Canonical` = remove `$Char(0)`; `Validate` refuses `"0"` and control characters; `ForIndex` maps `""` to `0`, `ForLedger` maps `""` to `$Char(1)`, `ForName` is the identity (GraphKey.cls:38-85). Subscript canonicalization: numeric-canonical strings collide with numbers.
L3 binds: `GraphKey.Validate/ForIndex/ForLedger/ForName`; `_validate.validate_graph_name/graph_index_key`; the inverse sites (Adjacency.cls:583, 627, 654, 698, 889; nodes_edges.py:1432; lazy_kg.py:78).
Cases: `""`, `$Char(0)`, padded names, `"0"`, `"00"`, `"1"`, `".5"`, control and C1 characters, legacy rows already holding a refused name; Python vs ObjectScript validator disagreement.

**O2. The Adjacency Index equals a function of the committed rows (keyed layout included).**
L1: For each graph g, after every committed transaction: for every triple with n >= 1 rows, the triple has an `out`/`in` entry; when the graph is in multigraph mode and n >= 2 it has n children, `# = n` and leaf = weight of the lowest `ekey`; otherwise one bare leaf; no entry without a row. Rollback restores the previous function value.
L2: Functional-index callbacks inside the row's transaction (AdjIndex.cls; Adjacency.RowPut/RowRemove/RowUpdate); keyed transitions read rows by SQL (`OtherEdgeKeys`) and recount `#`; shared locks only; IRIS globals are read-uncommitted; `$Increment` not transactional; callback error statuses ignored.
L3 binds: `Adjacency.Put`, `Remove`, `PutKeyed`, `RemoveKeyed`, `RowUpdate`, `SetLeafFromLowest`, `KeyCount`, `OtherEdgeKeys`, `RemoveSource/RemoveNode/RemoveGraph/RemoveAll`, `FillTriple`; `LedgerApply.DeleteRelInternal` (678-689), `PersistQuals` (552-565); `GraphMode.Set` (26-45).
Cases the model must represent: two processes on one triple (insert/insert, delete/delete, insert then rollback); mode flag flips between a row write and its delete; `ekey<>0` rows in a mode-off graph; restore ordering (rows before mode flag); %BuildIndices with two jobs on one triple; a callback that returns an error status.

**O3. A served degree equals the count of the visible `out` entries at a point where no uncommitted entry was counted.**
L1: `Degree(g,s[,p])` returns either a fresh count or a cached count that equals the current committed count.
L2: `gen` per source; `degc = (gen, count)`; probe of `^IVG.AdjW(g)` exclusive no-wait; writers hold it shared to commit; `AdjNoLock` marker; post-store re-read; AllWarm stamp keyed on the token.
L3 binds: `Adj.Degree`, `Adj.Cached`, `Adj.WarmFill/WarmAll/AllWarm`, `TraversalKHop.KHopCount`, every `gen` bump/kill in Adjacency.cls, `snapshot._import_global_from_ndjson` kills.
Cases: reader concurrent with writer (commit or rollback); reader in writer's transaction; `gen` killed and re-incremented to the same value during a recount (F2); rollback of a kill; lockless writer; AllWarm with an absent entry.

**O4. A token-validated cache never serves an answer computed over content that did not commit.**
L1: If an AlgoCache/`^ArnoKG`/`deg2p` entry is current, its answer equals the answer over the current committed graph.
L2: Token = `^KG("__version")`, bumped by `$Increment` inside writes (not undone by rollback); entry stamped with the token read before the compute; no writer-lock probe.
L3 binds: `AlgoCache.Lookup/Put/Token`, `IRISSQLStore._cached_algorithm` (iris_sql_store.py:921-987), `ArnoAccel.CacheGraphJson` (305-318), `TraversalBuild.Build2HopStats` (939-992), `TraversalKHop.Fresh`, `snapshot._raise_kg_version`.
Cases: committed write during compute; uncommitted write visible during compute, then rollback (F1); restore transiently writing an archive token value; two concurrent bumps.

**O5. Multigraph mode lifecycle.**
L1: A graph in mode off holds at most one row per triple. Turning off is refused while two rows share a triple. Erase clears the mode. A restore reproduces mode and layout.
L2: `^IVG.GraphMode(ForIndex(name))`; unlocked count-then-kill; per-engine cache in Python; writers' `ekey = 0` guard; restore order tables-then-globals.
L3 binds: `GraphMode.Set/IsMulti/ParallelCount`, `admin.set_multigraph/is_multigraph`, `translator._multigraph`, `create_edge` guard, `Eraser.EraseGraph` (244), `restore_snapshot`.
Cases: two engines with different cached modes; `Set(off)` racing a multigraph CREATE; replace-restore of a multigraph archive into an indexed namespace.

## Candidate findings

### Bugs (all SUSPECTED unless stated)

**F1. A rolled-back write can poison a token-validated cache** (AlgoCache, `^ArnoKG`, `deg2p`).
Expected: CONTEXT.md:118-119; ADR-0012:23-26, which names "a reader caching an uncommitted edge that is then rolled back" as the unsafe case; token audit fix 3 (research-token-audit.md:167-171), which bumps after `TRollback` for exactly this reason.
Observed: `Put` bumps the token inside the writer's transaction (Adjacency.cls:92). `_cached_algorithm` reads the token and stores the answer with no lock probe (iris_sql_store.py:960-981). The rollback paths do not bump (`_write_txn.py:234-253`; Eraser.cls:260, 459, 630, 816, 1308).
Interleaving: W `INSERT` edge (token T to T+1, uncommitted); R `Lookup` misses at T+1, computes PageRank over the edge, `Put(T+1)`; W rolls back; the next `Lookup` hits at T+1 with an answer that includes a non-existent edge, until any later write.
Distinguishing test: two connections, as `test_degree_cache_live.py:171-190` does for degree.

**F2. Degree-cache ABA after a `gen` kill.**
Expected: ADR-0012:12-17; spec 248 spec.md:76-77 claims the post-store re-read closes the erase window.
Observed: `RemoveSource` kills `gen` and `degc` (Adjacency.cls:376-377). `RemoveGraph`/`RemoveAll` and restore do the same (436-439, 459-463; snapshot.py:1688-1691). `$Increment` then restarts `gen` at 1.
Interleaving: R reads `gen = k` and passes the probe, then counts a large source; `delete_node(s)` commits; writers re-create s with k writes, so `gen = k` again; R's pre-store and post-store checks both see k; R stores `(k, old count)`. The wrong degree is served until the next write to s.
Second route: a rolled-back erase restores the killed `gen`/`degc` (journaled Kill) and overwrites increments made in the meantime by other processes.
Window: one recount (ADR-0010 measures 12.9 ms for a 100k hub).

**F3. Ledger `delete_rel` on a multigraph triple removes the surviving parallel edges' adjacency.**
Expected: spec 252 FR-001/FR-016; CONTEXT.md:90-95.
Observed: `DeleteRelInternal` deletes one row by `%ID` (LedgerApply.cls:678). The index then runs `RemoveKeyed`, which leaves the survivors with a leaf. Next, `If $Data(^KG("out", ...)) Do Adjacency.Remove(...)` (689) kills the leaf and its children. Line 689 dates from `fa67b2b3` (2026-10-12), before spec 252; it has no `Indexed()` guard, unlike OpCreateRel (508).
Result: rows remain with no adjacency ("missing" drift) and the degree is wrong. Reachable in non-strict ledger mode on a graph with parallel edges; spec 234 lists the ledger as not done (spec.md:5-6) but does not refuse it.

**F4. Concurrent keyed writers can lose multiplicity or leave ghost children.**
Expected: spec 234 FR-004/FR-006; spec 252 FR-003.
Observed: `PutKeyed` checks `'$Data(leaf)` and calls `Put` without mutual exclusion (Adjacency.cls:220-223). Writers hold shared locks only.
- Route a: two first puts of one triple (two `%BuildIndices` jobs, TraversalBuild.cls:131-133, or two transactions) both take the `Put` branch, and the triple ends with one leaf and no `#`.
- Route b: T2 builds children from T1's uncommitted leaf and row (read-uncommitted); T1 rolls back, so its leaf value is removed while T2's child for T1's `ekey` and `# = 2` remain, leaving a ghost.
- Route c: two `RemoveKeyed` of a 2-edge triple pass their guards before either collapses the triple, and a leaf can remain with no rows.
The PutKeyed comment (227-230) covers only the case where the leaf already exists. Not covered by any test.

**F5. Restoring a multigraph archive into an indexed namespace loses multiplicity.**
Expected: spec 234 FR-001 (mode in `STORE_PLAN`, snapshot.py:157-160 comment: "Without it a restored multigraph's parallel edges come back in a graph that refuses a second edge").
Observed: the replace-restore runs `erase_all` (clears modes) and inserts rows (snapshot.py:1234-1300); `RowPut` sees mode off and calls `Put` per row. `^IVG.GraphMode` arrives later with the globals (1554-1590). With the index declared, `out`/`in` lines are skipped (1659-1663), and no rebuild follows.
Result: degree 1 for parallel triples, and one-hop Cypher answers once, until `sync()`.

**F6. "Mode off implies one row per triple" holds only while every writer cooperates.**
`u_spo_graph_ekey` admits `ekey<>0` rows in a mode-off graph (schema.py:44). Three producers:
- `GraphMode.Set(off)` counts and then kills with no lock (GraphMode.cls:35-40).
- Another engine's cached "on" (admin.py:922-926; translator.py:441-457) keeps emitting the `MAX(ekey)+1` insert (translator.py:10368-10386).
- F5.
Consequence: deleting either row kills the shared leaf (`RowRemove` -> `Remove`), and the remaining row has no adjacency.

**F7. `verify_graph` reports false "missing" drift on any graph with parallel edges, and cannot see lost multiplicity.**
GraphVerify.cls:78, 104, 128 (`missing = rows - matched distinct triples`). Corroborated by the open task T036 (tasks.md:198) and the unmet SC-005 (spec.md:355-356). Source text alone shows the arithmetic: **confirmed by reading**; a live run would show the report.

**F8. A failed indexed rebuild leaves a partial adjacency.**
`%BuildIndices` runs after `TCommit`, and `PurgeIndex` = `RemoveAll` (TraversalBuild.cls:124-136; AdjIndex.cls:29-32). This contradicts spec 248 spec.md:74-75 and the BuildKG comment (46-58), which promise that a failed rebuild "leaves the previous adjacency intact" (true only for the non-indexed path). The catch block does bump the token (164-170).

**F9. `^NKG` is interned inside the functional-index callback, against ADR-0008.**
`RowPut` -> `Put` interns when `^NKG` is built (Adjacency.cls:95-107). ADR-0008:66-67 says interning "cannot" live in the index because a rollback leaves nameless ids and the locks deadlock under overlapping writers.
Observed: inside a transaction `InternNode`'s lock is held to commit, and after a 5 s wait it returns another transaction's possibly uncommitted index or `""` (GraphIndex.cls:49-54). `$Increment(^NKG(-3,s))` and `edgeCount` survive a rollback.
Impact depends on readers of `^NKG(-3)` values (TraversalBuild sweep repairs them at the next build, 478-479).

**F10. Callback error statuses from the keyed writers are swallowed.**
`PutKeyed`/`RemoveKeyed` convert exceptions to statuses (Adjacency.cls:264-267, 316-319). Per 4.7.0 row 17 IRIS does not read a functional index callback's status (Adjacency.cls:51-53), so the row commits without its entry. `Put`/`Remove` let exceptions through, which presumably fails the statement. The two behaviours are inconsistent.

**F11. `LedgerApply.PersistQuals` reweights a multigraph leaf to a non-lowest edge.**
`Reweight` sets the leaf unconditionally (LedgerApply.cls:561-563; Adjacency.cls:334-339), contrary to FR-004 when the updated row is not the lowest `ekey`. In indexed namespaces the call is also redundant with the index's `RowUpdate`.

### Design simplifications (P)

- **S1. Draw generations from the never-killed token**: `Set ^KG("gen",g,s) = $Increment(^KG("__version"))` in place of the two `$Increment`s.
  - Rationale: removes the ABA family (F2) because a re-created source can never repeat an old value; one counter per write instead of two.
  - Preserve: "Erase leaves no residue" (kill still allowed); the token stays monotone; AllWarm semantics unchanged.
  - Distinguishing case: F2's interleaving must not store a wrong entry; the randomized live test must still agree with a recount.
- **S2. Give AlgoCache and the stamped Rebuilt stores the ADR-0012 discipline**: probe `^IVG.AdjW` (parent, exclusive, no wait) before the compute and refuse to store if the probe failed, plus the AdjNoLock check.
  - Alternative: bump the token in every rollback path (`Txn.Undo`, the Eraser and Ledger catches), as BuildKG already does.
  - Preserve: hit rate with no writers in flight.
  - Distinguishing case: F1's two-connection test.
- **S3. One owner for the inverse mapping**: add `GraphKey.NameOf(indexKey)` (or pass names to `AssertTemporalRow`, `Retract*`, `OtherEdgeKeys`, Python `delete_edge`).
  - Preserve: every SQL `COALESCE(graph_id,'')` predicate.
  - Distinguishing case: default and named graph rows deleted through each site.
- **S4. Guard `LedgerApply.DeleteRelInternal`'s `Remove` with `'Indexed()`**, as OpCreateRel does. This fixes F3 in indexed namespaces with no change elsewhere.
  - Distinguishing case: delete one of two parallel edges through the ledger; the survivor keeps its entry.
- **S5. Bump the token before `EndRebuild(1)` in `BuildKG`**, not after (TraversalBuild.cls:142-145). The warm stamp then survives and the O(1) bulk readers work after `sync()`, as ADR-0012 and Adj.cls:180-183 intend.
  - Distinguishing case: `AllWarm(g) = 1` right after `BuildKG` with no writer.
- **S6. Serialize keyed transitions per triple**: an exclusive lock on `^IVG.AdjT(g,s,p,o)` held to commit around the read-modify-write in `PutKeyed`/`RemoveKeyed`, or derive `#` and children only from committed rows at rebuild.
  - Preserve: mode-off writers never take it (FR-016 cost, SC-004).
  - Distinguishing case: F4 routes a-c.

### Open questions (human decision needed)

- **Q1. Should `delete_edge` cascade reifications and edge embeddings?** `delete_node`, ledger `delete_rel`, `EraseEdges` and `DETACH DELETE` (fixed in 4.7.0) all do; `delete_edge` does not, and `rdf_reifications` has no FK.
  - Interpretations: (a) intended as a low-level primitive; (b) omission.
- **Q2. Is spec 234 FR-007 (`create_edge` always creates in a multigraph, plus `create_edge_returning_id`) still a requirement?**
  - Evidence: the code returns False, the method is absent, and CHANGELOG/API docs are silent; KNOWN_ISSUES steers users to Cypher.
  - Decision needed: drop the FR or treat it as a defect.
- **Q3. How should installs with legacy `graph_id = "0"` (or control characters) be found and migrated?**
  - Evidence: ADR-0003:69-70 promises `verify_graph` reports them; none does, and every `ForIndex` caller (including `%BuildIndices` callbacks) throws on such rows.
  - Decision needed: what an upgrade should do with such rows.
- **Q4. Which character set does the graph-name validator reject?**
  - Evidence: Python rejects 0-31 and 127; IRIS `"*C"` may also cover 128-159.
  - Decision needed: one definition, owned by `GraphKey`, with Python asking or mirroring it exactly.
- **Q5. Should the SQL `graph_id` always be the canonical name?** At present `create_edge`/`create_node` bind the raw name, and `create_node` validates nothing.
- **Q6. Is a per-engine `is_multigraph` cache acceptable, given F6's storage consequence?**
  - Options: (a) re-read the flag per statement; (b) have the functional index refuse an `ekey<>0` row in a mode-off graph; (c) document the hazard.
- **Q7. Should the 4.7.0 lockless-writer fallback (AdjNoLock) amend ADR-0012?** At present it lives only in a CHANGELOG row and code comments.
- **Q8. Does the token need to move on node-only writes for wcc/cdlp, or do those algorithms ignore edgeless nodes?** Not inspected.

## Not inspected / limits

- Nothing was executed. Every interleaving above is derived from source text and the IRIS semantics the code itself documents: read-uncommitted globals, `$Increment` not rolled back, deferred unlock inside a transaction. Three IRIS behaviours are assumed rather than verified:
  - that an exception thrown inside a functional-index callback fails the statement;
  - that `%BuildIndices` with jobs can process two rows of one triple concurrently;
  - the exact `$ZStrip "C"` class.
- Cypher translation and the native executor (one-hop shortcuts, compiled plans) are A-cypher's. I only checked where they read the multigraph mode and `degc`.
- Temporal structural rows (`AssertTemporalRow`, `Retract*`, ADR-0009/0015) were read only for their key handling; their semantics belong to A-temporal.
- Ledger, erasure and redaction semantics are A-history's. I inspected only how `LedgerApply` and `Eraser` touch adjacency and keys.
- I did not read `TemporalIndex.cls`, `FHIRGraph.cls`, `Cypher/Exec.cls`, `TraversalBFS/Paths.cls`, `PageRank.cls` or `Centrality.cls` beyond grep hits for key derivation and `degc`.
- The `NKGAccel*` classes and the full `^NKG` lifecycle (EnsureNKG, sweeps, `$NX` retirement) were skimmed, not traced. F9's impact depends on them.
- The bulk loaders (`bulk_load_session`, `%NOINDEX` + `%BuildIndices`, `_bulk_load_drifted`) and merge-restore keys were not traced.
- I ran no history beyond a few `git log -S`/`git blame` checks: `9c25eaab` (degree cache), `c5a1b214` (warm stamp), `b741dbdc` (4.7.0 row 17), `fa67b2b3` (LedgerApply line 689), `a0b30ca5` (GraphVerify counting).
