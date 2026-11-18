# G report — features/graph-structure (20) and operations/snapshots-and-bulk-load (11)

Saved by the builder from the fork's final message. Fragment: 31 blocks complete, 155 obligations, 36 exclusions,
owner-updates 2; merged check PASS.

## 1. Per block (f/p/a/u, excl) — all complete, none structural zero
structure.write 5/1/5/0 (6); structure.node 0/2/2/0 (1); .node.bulk 9/1/0/0 (2); .node.delete 2/1/2/0 (1);
.node.delete.bulk 5/1/1/0 (1); .node.update 5/0/1/0 (0); .node.read 5/1/1/0 (1); .node.read.properties 0/0/8/0 (1);
structure.edge 1/1/0/0 (1); .edge.single 1/1/0/0 (0); .edge.weight 2/0/1/0 (0); .edge.weight.set 2/1/1/0 (0);
.edge.delete 3/0/3/0 (0); structure.reification 0/0/7/0 (0); structure.multigraph 0/2/1/0 (1); .multigraph.off
0/1/1/0 (1); .multigraph.switch 0/0/2/0 (1); .multigraph.count 2/0/5/0 (0); .multigraph.restore 0/0/2/0 (0);
structure.degree 0/1/0/0 (1); install.snapshot 0/2/2/0 (2); .snapshot.scope 2/3/1/0 (1); .snapshot.failure 0/0/2/0 (1);
.snapshot.derived 0/0/3/0 (0); .snapshot.routes 8/4/1/0 (0); .snapshot.temporal 6/2/0/0 (2); .snapshot.info 1/1/2/0 (0);
install.bulk_load 0/1/1/0 (7); .bulk_load.loader 5/1/3/0 (0); .bulk_load.ledger 0/0/1/0 (3); .bulk_load.rebuild
1/0/3/0 (2).

## 2. Totals
graph-structure 20 blocks: 42/14/43/0 of 99 (42.4%), proved full scope 8, proved 53, refuted 0. snapshots-and-bulk-load
11 blocks: 23/14/19/0 of 56 (41.1%), proved full scope 0, proved 32, refuted 4. Exclusions 36: restatement 19,
undecided-alternative 7, cross-reference 5, definition 2, rationale 2, navigation 1. Full with no design check:
structure.write#o10 (a global write at $TLEVEL 0 is durable; model step definition).
Refuted (all full, narrowed): install.snapshot.scope#o03 (merge guard compares only the first exported column; snapshot_routes
theorem_merge_parent_collision_blocks_vector); install.snapshot.temporal#o05 (numeric attribute types do not survive,
F-1804); install.snapshot.temporal#o07 (a refused global line is not reported, F-C1802); install.bulk_load.loader#o06
(loader ignores the namespace's IVG Schema, bug-plt-012).

## 3. Grades: reused 60, changed 0, new 95
Reused: NOTES of write_routing, node_edge_update, bulk_children, bulk_delete, node_read, edge_acceptance, adjacency_maint
(D1–D4), weighted_paths, snapshot_routes, temporal_restore, operator_reports, bulk_load, ndjson_import; coverage.md rows
for structure.multigraph.count and iteration 1's structure.node.read. structure.multigraph.count keeps "Proved (index
declared)" as full, proved, narrowed. coverage.md ~147 ("Nodes, edges, reifications CRUD … not modeled") is stale for
nodes and edges, still true for reifications.
Judgement: structure.node#o01 partial (ndjson_import theorem_duplicate_count_not_upsert shows the kept value through the
importer; the False return is not modelled); structure.node.bulk#o02 partial (falsey-ID decision is a model input);
structure.edge.single#o01 partial (sequential repeats proved; bug-str-008's stale mode cache / unlocked switch not
modelled); install.snapshot.scope#o03 uses the node-parent merge witness to refute the intended rule;
install.snapshot.routes#o12 states the same defect as current behaviour and is graded proved.

## 4. Parents
No entailment credited. Own text: structure.node (create_node), structure.edge (endpoint registration),
structure.edge.weight, structure.node.delete, install.bulk_load (BulkLoader's unindexed insert, load_networkx's rebuild).
Open: structure.multigraph#o01 — off/switch/count/restore children hold while an engine's cached mode (F-0208) disagrees
with ^IVG.GraphMode; structure.degree#o01 — degree-cache children constrain cached hits only, the sum over entries is a
binding port not a theorem; install.snapshot#o01 — routes, temporal and info children hold while a label, property or
reification row, or a BM25/IVF global, fails to come back.

## 5. Restatements
owner-updates: graph.default#x04 → structure.edge.delete#o02; graph.default#x05 → structure.reification#o07.
Cross-fork (owner A's structure.adjacency.bulk): install.bulk_load#x02 "Every one of them must follow the bulk index rule,
which that page owns"; install.bulk_load#x05 "bulk_create_nodes and bulk_create_edges drop some SQL indexes around a
large batch … bulk_load_session does the same"; install.bulk_load.rebuild#x01 "the adjacency index … must reflect the
loaded rows before a read uses them". install.bulk_load.loader owns the BulkLoader contract adjacency.bulk bullet 3
points to. To enumerated owners: graph.default#o02, #o04, erasure.kept#o04, erasure.atomic#o01, ledger.strict#o02, #o05,
access.ledger_strict.surfaces#o02, ledger.changeset#o02.

## 6. Grade-source errors and contradictions
1. structure.node lead ("A write that IRIS refuses raises an error"): _engine/nodes_edges.py:1097-1104 returns False for any exception whose text contains "unique", "-119" or "validation failed"; such refusals look like duplicates.
2. install.bulk_load.rebuild lead ("an index that fails to come back is named in a warning, and reads scan the table") holds for engine paths (nodes_edges.py:67-80); BulkLoader.load_networkx raises RuntimeError and says the rows are invisible to SQL (bulk_loader.py:586-598).
3. install.snapshot.derived ("moves the graph-version token past both values"): _raise_kg_version and ArnoAccel.BumpVersion run only inside `if global_files:` (snapshot.py:1555-1585); an SQL-only archive restore does not bump the token there (other writers not traced).
4. structure.reification bullets 1 and 3: reify_edge property guard and get_reifications join match on s = reifier_id with no graph (_engine/schema.py:3318-3324, 3340-3345); a same-ID property in another graph can suppress a write or leak into the result; returned values are raw stored text.
5. structure.edge.delete WA (deletion removes only the rows its implementation cleans up) vs erasure.entry-points.single-path#o01 (every delete goes through the Eraser): delete_edge runs its own DELETE FROM rdf_edges (nodes_edges.py:1426-1440), contradicting the erasure obligation's wording for this path.
6. coverage.md ~147 stale for nodes and edges.
7. decision-links row for structure.multigraph.count cites routine_reporting theorem_appending_row_counts_physical_multiplicity (SQL census counts, not the Cypher one-hop reader); not used for credit.

## 7. Ranked uncovered
1. Reifications (structure.reification#o01–#o07, 7 absent, no model): reifier in default graph for a named-graph edge; refusal of a second edge per reifier; only missing properties added; atomic refusal; missing edge → None; delete in every graph. Bind _engine/schema.py::SchemaMixin.reify_edge, ::get_reifications, ::delete_reification; nodes_edges.py::NodesEdgesMixin._reifiers_of.
2. Multigraph switch and restore (multigraph.off#o02, switch#o01–#o02, restore#o01–#o02, multigraph#o03): stale per-engine mode cache and unlocked count-then-switch race (bug-str-008, F-0208); restore writing rows before the mode (bug-str-007). Bind GraphMode.cls::Set, ::ParallelCount; _engine/admin.py::set_multigraph, ::is_multigraph; nodes_edges.py::_ekey_guard; snapshot.py::restore_snapshot; observe Adj.Count and ^KG keyed children.
3. Routing of native-connection calls (structure.write#o05–#o09): whether erase, sync, set_multigraph, BM25/vector index writes and FHIR calls join the caller's transaction (bug-srch-002 contradicts #o03 for BM25). Bind engine.py::IRISGraphEngine._iris_obj, nodes_edges.py::erase_graph, index writers; observe on another connection after rollback.
4. Restore derived state and failure reporting (snapshot.derived#o01–#o03, failure#o01–#o02, scope#o04): snapshot.py::_raise_kg_version, ::restore_snapshot (_commit, CONFIGURATION_TABLES branch), ::save_snapshot.
5. Property readers (node.read.properties#o01–#o08; native observations only): get_nodes_by_property, get_node_ids_by_property, get_property_values, get_property_pairs, nodes_exist, list_graphs.
6. BulkLoader edges and duplicate-or-refusal (bulk_load.loader#o02, #o08, #o09; rebuild#o02, #o04; bulk_load#o02): BulkLoader.load_edges, ::_register_endpoints, ::_executemany_batched (_is_duplicate), ::load_networkx.
7. Token and degree-cache freshness after a bulk load (bulk_load.rebuild#o01): nodes_edges.py::_rebuild_after_load, bulk_load_session, $Increment(^KG("__version")) in Adjacency.cls.
8. Partly covered: node.delete#o02, #o04 (Eraser.cls::EraseIdSet); edge.delete#o02, #o04, #o06; edge.weight#o02 (Cypher r.weight); multigraph.count#o02–#o06 (TraversalKHop.cls::KHopNeighborIds, query.py::_try_khop_fast_path).

## 8. Iteration-60 residual mapping
store/iris_sql_store: structure.node.delete.bulk#o06 (chunk commits in IRISGraphStore.delete_nodes), structure.write#o05.
load_networkx: install.bulk_load#o02, install.bulk_load.rebuild#o02 (+ contradiction §6.2). load_obo: no owner on these
pages (snapshot.py::load_obo; S2 counts install.import). install residue: install.snapshot*, install.bulk_load*. None:
migrations, GQL/GraphQL, SDK/CLI/HTTP admin, translator, temporal/operator/retrieval.
Source-discovered omissions: reification property guard and join not graph-scoped; bulk_ingest_edges missing from
install.bulk_load's "three ways"; restore_snapshot's _register_endpoints recovery for pre-4.0 archives (creates endpoint
nodes); HTTP snapshot directory (IVG_SNAPSHOT_DIR) in metadata only.

## 9. Limitations
No independent review; no reruns; split granularity (8 property-reader, 5 routing obligations); many full grades rest on
transcription models with substituted stores (SQLite for bulk_children and edge_acceptance, scripted providers for
bulk_delete), narrowed; structure.write#o10 full with no named theorem; fork A's enumeration not read.
