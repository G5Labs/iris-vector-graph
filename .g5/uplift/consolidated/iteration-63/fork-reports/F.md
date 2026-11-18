# F report — features/fhir (18 blocks)

Saved by the builder from the fork's final message. Fragment: 18 blocks complete, 81 obligations, 26 exclusions, no
owner-updates; merged check exit 0 PASS.

## 1. Per block (f/p/a, excl)
fhir.graph 0/2/3 (3, parent, projection obligations own); fhir.graph.install 0/0/4 (0); fhir.graph.lifecycle 1/1/1 (5,
parent, #o02 refuted two tasks F-C1501); .lifecycle.tasks 15/0/0 (1, fhir_tasks, all proved); fhir.sync 0/3/1 (5,
parent, proofs-d1f reviewed design); .sync.idempotent 0/1/5 (0); .sync.exclusive 0/2/0 (0); .sync.behind 0/0/2 (0);
fhir.rebuild 0/0/4 (0); fhir.erase 0/3/0 (4, two restatements of erasure.kept); fhir.interpretation 0/0/8 (0);
.interpretation.version 0/3/1 (0); fhir.sql_mapping 4/2/3 (2); .relationships 2/1/1 (0); .adjacency 0/0/2 (2);
.embeddings 0/0/2 (0); fhir.event 0/0/4 (2); fhir.event.access 0/0/0 (2, structural zero).
Unassessed 0. Exclusions 26: restatement 12, undecided-alternative 7, rationale 6, definition 1.

Page totals: full 22, partial 18, absent 41 (27.2%). Proved 33 (13 full scope, 20 narrowed); refuted 1; bounded 0.

## 2. Grades
Reused (fhir_tasks NOTES, iteration 8): all 15 lifecycle.tasks full, proved (prove 20261116T160725Z, latest named
controls, binding 20261115T185920Z AGREES); lifecycle#o02 full, refuted (`theorem_schedule_retry_can_leave_two_tasks`);
lifecycle#o03 partial (status only as task_id/interval/version projection).
Reused (sql_mapping NOTES, iteration 40): full proved sql_mapping#o01, #o04, #o07, #o08, relationships#o03, #o04;
partial sql_mapping#o03, #o09, relationships#o01 (join tables not modelled).
Reused (platform): fhir.graph#o05 (FHIR sync writes not refused under strict mode) partial, from
`witness_undecided_paths_write_under_strict`.
Changed: sql_mapping#o05 (removing a mapping removes its relationship mappings) absent — the crosswalk links
`remove_table_mapping` to `theorem_writer_reads_current`, which does not decide relationship removal.
New from proofs-d1f module 15: 16 obligations, all partial (reviewed design, not as-built); proved narrowed with
baseline receipt 20261115T035925Z where a theorem decides the case, otherwise no check.
New absent: everything else (source inspection).

## 3. Parents
Open: lifecycle#o02 ("one task per graph"): every tasks-child obligation can hold while a failed registry update plus a
retry leaves two tasks (F-C1501). No entailment claimed: fhir.graph, fhir.sync, fhir.interpretation, fhir.sql_mapping,
fhir.event have only their own obligations; fhir.sync's batch/watermark atomicity is not entailed by its children.
Three lifecycle bullets are restatements of tasks#o10, #o01, #o04; the lead's build/sync clauses point to
fhir.rebuild#o01 and tasks#o14.

## 4. Restatements
To enumerated owners: fhir.erase#x01 → erasure.kept#o03; #x02 → erasure.kept#o05; fhir.graph#x02 →
ledger.unrecorded#o02; fhir.event.access#x01 → access.api_key.every_route#o01; #x02 → access.read_only#o07.
Cross-fork: fhir.sql_mapping#x01 "…writes to IVG's configuration tables, which a snapshot carries" → install.snapshot.scope
(G) bullet 1 (configuration tables such as SQL table mappings match on their primary key).
install.deploy bullet 6 ("the FHIR sync task ships and stays inert") is distinct from fhir.graph.install#o01/#o02; both counted.

## 5. Grade-source errors and contradictions
1. coverage.md line 448 ("FHIR: all of fhir.*. No model") and line 502 stale: fhir_tasks and sql_mapping model those blocks.
2. fhir.interpretation bullet 3 (PageRank skips compartment edges by default) is only true of fhir_concept_ppr (fhir_graph.py:409); personalized_pagerank(graph=…) defaults exclude_predicates=None (algorithms.py:227, :434) and walks them.
3. fhir.graph.lifecycle lead implies registration builds the graph; a first Register does not rebuild; it rebuilds only when an existing graph's json_links change (FHIRGraph.cls:262-272).
4. erasure.kept#o03/#o05 graded absent ("no model") in iteration 61; proofs-d1f fhir_l2.rs::erased represents both (registration kept, watermark zeroed) on the same basis that makes fhir.erase#o01 partial. Master to decide alignment (not changed).
5. Crosswalk row for remove_table_mapping: the linked theorem does not decide the relationship-mapping removal.
6. proofs-d1f has only a baseline receipt; as-built counterexamples (HD-1503, F-C1501, F-1511, re-derivation restart) have no control receipts, so none can be cited as a refutation.
7. Minor: SyncOnce's "repository behind" branch releases the lock before Rebuild retakes it (FHIRGraph.cls:565-568); another caller can take it in between, so the sync answers busy instead of "rebuilt".

## 6. Ranked uncovered
1. Resync, delete and rebuild content (no model): idempotent#o01, #o03–#o06; rebuild#o01–#o04; behind#o01, #o02; graph#o03. Bind FHIRGraph.cls::ResyncKey, DropNode, RunBatch, Rebuild, SyncOnce; readers Status and the nodes/edges/fhir_unresolved tables.
2. Compartment edges (8 absent): interpretation#o01–#o08. Bind ResyncKey (:2212, :2279), DropNode (:2414), Status (:324-325), fhir_concept_ppr, Eraser.cls::EraseGraph.
3. Erase during a running sync: erase#o02 proved only with no sync running; RunBatch writes an absolute watermark (:1967-1969) after an unlocked EraseGraph. Running control_hd1503_erase_ignores_sync_lock is the cheapest refutation on this page.
4. Registration and naming: graph#o01, install#o01–#o04, lifecycle#o01 (Register, _fhir_graph, _ensure_fhir_graph_tables).
5. SQL mapping leftovers: sql_mapping#o02, #o05, #o06; relationships#o02; adjacency#o01, #o03; embeddings#o01, #o02 (fhir.py remove_table_mapping, map_sql_relationship, attach_embeddings_to_table, _nodes_present).
6. FHIR event route: event#o01–#o04 (api/routers/fhir_event.py).
7. Busy/last_error: exclusive#o02 (busy modelled for sync only), sync#o04 (offending key in last_error), version#o02 (Reinterpret).

## 7. Iteration-60 residual mapping
SDK/CLI/HTTP admin: /fhir-event route (event#o01–#o04), `ivg fhir` CLI (lifecycle#o01, fhir.sync blocks). Install
residue: install#o01–#o04. Migrations: interpretation-version upgrade (version#o01–#o04). Temporal residue: event's
timestamped edge (event#o03). None: store/iris_sql_store, GQL/GraphQL, translator, load_networkx/load_obo, operator,
retrieval.
Source-discovered omissions: re-registering keeps watermarks; changed denylist applies only at next rebuild; changed
json_links rebuilds immediately or records "rebuild pending" (Register :156-166, :262-272); a refused Register can keep
its new settings (F-1511, :235-249); Python layer refuses a graph whose interpretation version is newer (_interp_stale;
modelled by fhir_tasks, no owner); fhir_graph_register checks interval/denylist format before writing; concept readers
(ResolveConcepts, CoverageReport, ConceptGaps, PatientConcepts, LinkReport, GroupPPR) and fhir_bridge_add/get_kg_anchors
have no block.

## 8. Limitations
proofs-d1f grades held at partial (R15-1..R15-3, R15-P not as built); fhir_tasks provider premises narrow tasks#o03,
#o05, #o11, #o13–#o15; no native FHIR evidence (Community edition has no IRIS for Health); sql_mapping full grades rest on
decision-table theorems plus a binding over fixture tables; granularity (interpretation bullet 2 split into three readers;
lifecycle.tasks 15); "removed in 5.0" and "Scheduling proves neither…" excluded as rationale.
