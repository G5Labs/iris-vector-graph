# Snapshots and bulk loading

Use this page to restore a snapshot or load data through the bulk loader. For file interchange and validation, see [graph import and export](../features/data-interchange.g5.md).

## Definitions

- **Integer adjacency copy**: `^NKG`, the copy of the adjacency index the graph algorithms read. It has no graph dimension: an edge held by two graphs is one entry. `engine.sync()` rebuilds it.
- **Routed vector table**: a node-vector table made for one graph or model, named `kg_emb_` plus 16 hex digits and recorded in the embedding registry; `kg_NodeEmbeddings` is the legacy table.

## Save or restore a snapshot

<a id="install.snapshot"></a>
[I · install.snapshot]

A snapshot copies the namespace's graph content to a file and back. One server-side inventory of IVG's stores decides what is archived and what is derived. A snapshot is not a backup: it leaves out IVG's deploy record and compiled-plan state, its embedding queue, the quarantine table and the derived vector table.

- Working assumption: Prefer refusal while a live ledger exists until replace/merge history semantics are specified; do not count the current overlay as a decided contract.
- Working assumption: Claim a consistent snapshot only when writers are quiescent (an operator premise) or under a verified snapshot/epoch protocol; for the current exporter declare the quiet-writer premise.

<a id="install.snapshot.scope"></a>
[D · install.snapshot.scope]

Snapshots cover the whole namespace; there is no per-graph snapshot. `restore_snapshot(path)` replaces: it empties every graph and loads the archive. `restore_snapshot(path, merge=True)` keeps what is there and adds the archive's rows that are not.

- Configuration tables, such as FHIR registrations and SQL table mappings, match on their primary key: a replacing restore writes the archive's row, a merge keeps the live one.
- A restore is refused in ledger strict mode and while the caller has an open transaction.
- A restore refuses, before erasing anything, an archive whose recorded storage layout differs from the namespace's. An archive with no layout stamp is accepted.

<a id="install.snapshot.failure"></a>
[D · install.snapshot.failure]

Saving fails with no archive written if any table or global cannot be read. A restore is not atomic as a whole: a failed table commit raises an error naming the tables already committed. The erase that starts a replacing restore is one transaction.

<a id="install.snapshot.derived"></a>
[I · install.snapshot.derived]

A restore never brings back derived caches, and it moves the graph-version token past both its value before the restore and the archive's value. A cached answer from before the restore can therefore never be served after it.

<a id="install.snapshot.routes"></a>
[I · install.snapshot.routes]

A snapshot saves each routed vector table and restores it at the width the archive records, with each graph's vectors kept to that graph. After a restore, a width-checked vector search on each route reads its own table at its own width.
- A route is saved from its registry row. A row whose table name is not the routed shape, or that has no positive width, is not saved, and a warning says so.
- A restore creates each routed table at the archived width, not at the restoring engine's width, then loads it, builds its index and records the index state the database really has.
- A routed table found in the archive with no width entry takes its width from the restored registry row.
- Node vectors and routed vectors are matched on graph and node, so two graphs' rows stay apart. Edge vectors match on source, predicate and target with no graph.
- Observed limits: an existing routed table keeps its current width; an incompatible empty table refuses incoming vectors and reports failed rows. A merge keeps an existing graph/node vector and counts that skipped row as restored, even when the incoming vector has another width.
- A failed registry index-state update is logged and clears this engine's route cache, but can leave the archive's old index claim. A route with invalid width metadata may remain registered without a table; its vector reader then raises rather than answering empty.
- The generic node merge guard uses only the exported first column. A node with the same ID in another graph can therefore suppress the required parent, making its archived vector fail and its reader answer empty; this is a known merge defect, not the intended graph-key rule.

<a id="install.snapshot.temporal"></a>
[I · install.snapshot.temporal]

A temporal event saved in a snapshot answers a [window read](../features/temporal.g5.md#temporal.window) after a restore, not only a row count. The native subtrees the archive holds are read from the same store plan the restore uses, so every temporal subtree goes out and comes back.
- The default graph and timestamp zero are included. A suppressed reverse entry stays absent, so an outgoing event need not appear in an inbound window.
- Attribute types should survive too. Today scalar export turns numbers into text: a numeric attribute returns as a string after restore, while text stays text; the weight reader still returns a number. This is a known failure of type preservation.
- A refused global line can be skipped without an error or failed-row count while valid neighbors restore. This is a known failure of the required restore error report.
- An archive naming another storage layout is refused before anything is erased. The current reader admits an archive with no layout stamp; this does not establish compatibility for arbitrary old global shapes.
- The temporal subtrees saved are the events by time in both directions, the time buckets and their aggregates, the edge attributes, and the latest-event index.

<a id="install.snapshot.info"></a>
[I · install.snapshot.info]

`snapshot_info(path)` reads an archive's metadata without a connection and reports what a replacing restore will load: each table's row count over every graph at save time, and the non-empty globals.
- A replacing restore brings the status counts to those row counts.
- Its `version` is the archive format (`"1.1"`), not the IVG release; the release that wrote the archive is the metadata's `ivg_version`.
- A file without `metadata.json` raises `KeyError`.

## Load data in bulk

<a id="install.bulk_load"></a>
[D · install.bulk_load]

IVG has three ways to load many rows quickly, and they do not give the same guarantees. Every one of them must follow the [bulk index rule](../architecture/adjacency-and-derived-data.g5.md#structure.adjacency.bulk), which that page owns. The two engine paths are also refused in ledger strict mode; the `BulkLoader` class is outside strict mode by documented decision.

- `bulk_create_nodes` and `bulk_create_edges` drop some SQL indexes around a large batch and rebuild them after.
- `bulk_load_session` does the same around a session of batches.
- `BulkLoader` inserts rows without index upkeep or key checks. Its `load_networkx` then rebuilds the namespace's indexes and adjacency index; its `load_nodes` and `load_edges` leave the rebuild to the caller.

- Working assumption: Keep documented loader exemptions and chunking; preserve other graphs and multigraph data unless a narrower supported envelope is expressly adopted.

<a id="install.bulk_load.loader"></a>
[D · install.bulk_load.loader]

The `BulkLoader` class trades per-row checks for speed.

- One loader writes one graph, and the default graph is written explicitly.
- It drops duplicates within a load and skips rows already stored, so loading the same data again changes nothing.
- Today it skips an input node as soon as its node row is stored, with that node's labels and properties. A load that failed after writing node rows therefore cannot be finished by loading again: those nodes keep no labels or properties.
- It refuses a caller's open transaction and commits per batch.
- It writes and rebuilds in the namespace's recorded IVG Schema, like every other IVG writer.
- Today it uses `Graph_KG` unless it is given the schema, and its index rebuild always names the `Graph_KG` classes. In a namespace with another IVG Schema, a load without the schema fails, and an unindexed load cannot be made readable by the loader's rebuild.
- Before its unindexed edge load writes any edge, it adds each edge's two end nodes to the loader's graph, so every edge it writes has both endpoints.
- A row that IRIS refuses for a reason other than a repeat stops the load with a bulk load error that says how many rows went in first. It is never reported as zero rows inserted.

<a id="install.bulk_load.ledger"></a>
[D · install.bulk_load.ledger]

The engine's bulk paths are refused in ledger strict mode, but the `BulkLoader` class is not governed by it and its writes are not recorded. The [ledger page](../features/ledger.g5.md#ledger.strict) owns the list of governed calls.

<a id="install.bulk_load.rebuild"></a>
[I · install.bulk_load.rebuild]

After any bulk load finishes, the adjacency index, the degree cache and the graph-version token must reflect the loaded rows before a read uses them. An SQL index that fails to come back is named in a warning, and reads that need it scan the table instead. Today `BulkLoader.load_nodes` and `load_edges` leave that rebuild to the caller, against the [bulk index rule](../architecture/adjacency-and-derived-data.g5.md#structure.adjacency.bulk), so a caller who skips it leaves those rows invisible to index-based reads.

## Metadata

### install.snapshot

- uncertain
- Sources: [USER_GUIDE §10](../../../docs/USER_GUIDE.md); [ADMIN_GUIDE: backups and snapshots](../../../docs/ADMIN_GUIDE.md); [_engine/snapshot.py STORE_PLAN](../../../iris_vector_graph/_engine/snapshot.py); [ADR-0004](../../../docs/adr/0004-erasure-removes-content-not-history.md)
- Children: [scope](#install.snapshot.scope), [failure](#install.snapshot.failure), [derived](#install.snapshot.derived), [What should a restore do when the namespace already has a live ledger?](../../Verus_verification/open_questions.md#q-plt-004), [routed vectors](#install.snapshot.routes), [temporal events](#install.snapshot.temporal), [archive info](#install.snapshot.info)
- agent
- user-facing-behavior, operations
- test-coverage

Live coverage of the inventory: `tests/integration/test_snapshot_inventory.py`. Snapshots made through the HTTP server land in the temporary directory unless `IVG_SNAPSHOT_DIR` is set (KNOWN_ISSUES).

Findings: [A merge restore keeps at most one row per graph in the core tables and reports every row restored](../../Verus_verification/bugs_issues.md#bug-plt-004)

Audit reproduction: [bug-plt-004](../../Verus_verification/bugs_issues.md#bug-plt-004) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Open questions: [Should a snapshot be a point-in-time view?](../../Verus_verification/open_questions.md#HD-1802), [What should a restore do when the namespace already has a live ledger?](../../Verus_verification/open_questions.md#q-plt-004)

Assumption review evidence: Changed from decisions.md: **no**.

### install.snapshot.scope

- Sources: [USER_GUIDE §10](../../../docs/USER_GUIDE.md); [ADMIN_GUIDE (configuration tables)](../../../docs/ADMIN_GUIDE.md); [_engine/snapshot.py restore_snapshot](../../../iris_vector_graph/_engine/snapshot.py); [Stage A notes F-B1, F-B2](../../uplift/ivg-verus-initial/intent/platform.md)
- Expands: [Snapshots](#install.snapshot)
- agent
- user-facing-behavior, data-integrity

Suspected divergence: a merging restore matches the core tables' rows on the first exported column only (in practice the graph ID), so it may add at most one row per graph while counting every row as restored. A multigraph graph restored into an indexed namespace may lose its parallel-edge layout.

Findings: [A replacing restore leaves the live search indexes in place and merges the archive's into them](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-plt-024)


Layout check: [snapshot.py restore_snapshot](../../../iris_vector_graph/_engine/snapshot.py#L1086-L1129) (added by review round 3 R3-reader M24).

### install.snapshot.failure

- Sources: [_engine/snapshot.py](../../../iris_vector_graph/_engine/snapshot.py); [ADMIN_GUIDE](../../../docs/ADMIN_GUIDE.md); [Eraser.cls](../../../iris_src/src/Graph/KG/Eraser.cls)
- Expands: [Snapshots](#install.snapshot)
- agent
- data-integrity, operations

Introduced in 4.6.0 (R271, R276). Suspected divergence: one global line that fails to write during restore is logged and skipped without being counted or reported.

Findings: [A restore swallows a global line that fails to import](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-plt-016)

### install.snapshot.derived

- Sources: [_engine/snapshot.py](../../../iris_vector_graph/_engine/snapshot.py); [Spec 236 FR-018](../../../specs/236-arno-callout-adoption/spec.md)
- Tests (live): `tests/integration/test_236_token_write_paths.py` (restore and merge cases)
- Expands: [Snapshots](#install.snapshot)
- agent
- data-integrity
- test-coverage

### install.snapshot.routes

- design-verified
- Sources: [`iris_vector_graph/_engine/snapshot.py::routed_export_plan`](../../../iris_vector_graph/_engine/snapshot.py#L299-L344); [`iris_vector_graph/_engine/snapshot.py::SnapshotMixin.restore_snapshot`](../../../iris_vector_graph/_engine/snapshot.py#L1077-L1611) (routed tables at the archived width `:1372-1500`; node and routed vectors matched on graph and node `:1341-1350`, `:1473-1480`); live tests [test_snapshot_routed_embeddings.py](../../../tests/integration/test_snapshot_routed_embeddings.py#L152-L200), unit [test_snapshot_inventory.py](../../../tests/unit/test_snapshot_inventory.py)
- Playbook: [SNP-B1.7](../../../experiment/playbook-completion/ontology/18-snapshot.md#L51), [SNP-B2.11](../../../experiment/playbook-completion/ontology/18-snapshot.md#L84), [SNP-B4.5](../../../experiment/playbook-completion/ontology/18-snapshot.md#L119)
- Formal contract: [routed snapshot stages and reader](../../Verus_verification/models/snapshot_routes/snapshot_routes.rs). It covers decoded node routes, declaration/registry/row stages and literal width admission; full archive loops, temporal globals and arbitrary provider failure outcomes remain open. The imported reviewed `snap_l2` is retained as partial historical evidence.
- Findings: [generic merge key](../../Verus_verification/bugs_issues.md#bug-plt-004)
- Expands: [Snapshots](#install.snapshot)
- agent
- user-facing-behavior, data-integrity

Public case J01. Edge vectors matching with no graph is the playbook's finding F-1803.

Audit reproduction: [bug-plt-004](../../Verus_verification/bugs_issues.md#bug-plt-004) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Audit reproduction: [F-1802](../../Verus_verification/bugs_issues.md#F-1802) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [A merge restore guards plain tables on their first column only, and counts skipped rows as restored](../../Verus_verification/bugs_issues.md#F-1802).

State machines: [snapshot routes](../../Verus_verification/models/snapshot_routes/manifest.json)

### install.snapshot.temporal

- design-verified
- Sources: [`iris_vector_graph/_engine/snapshot.py::snapshot_globals`](../../../iris_vector_graph/_engine/snapshot.py#L387-L408), [`::kg_export_subscripts`](../../../iris_vector_graph/_engine/snapshot.py#L425-L437), `STORE_PLAN` temporal entries [`snapshot.py`](../../../iris_vector_graph/_engine/snapshot.py#L136-L144); live tests [`test_the_restored_temporal_edge_answers_a_window_query`](../../../tests/integration/test_snapshot_inventory.py#L116-L130), unit `tests/unit/test_snapshot_inventory.py::test_the_globals_export_is_derived_from_the_plan`
- Playbook: [SNP-I1.1](../../../experiment/playbook-completion/ontology/18-snapshot.md#L40), [SNP-B1](../../../experiment/playbook-completion/ontology/18-snapshot.md#L42), [TMP-B6](../../../experiment/playbook-completion/ontology/05-temporal.md#L201)
- Formal contract: [temporal restore, scalar types and window projection](../../Verus_verification/models/temporal_restore/temporal_restore.rs). Critical source keys are derived from the finite source map under the Native API enumeration contract; full page-sequence/global-loop composition and general codecs remain open. The unchanged paging family is an explicitly stamped dependency, not new proof credit.
- Findings: [scalar type loss](../../Verus_verification/bugs_issues.md#F-1804), [silent global-line loss](../../Verus_verification/audits/register-20261115/bugs-review.md#F-C1802)
- Expands: [Snapshots](#install.snapshot)
- agent
- user-facing-behavior, data-integrity

Public case J02. A hand-kept second list of exported subtrees once dropped all five temporal subtrees from every archive (playbook note on SNP-I1.1); the list is now derived.

Audit reproduction: [F-1804](../../Verus_verification/bugs_issues.md#F-1804) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

State machines: [temporal restore](../../Verus_verification/models/temporal_restore/manifest.json)

### install.snapshot.info

- Sources: [snapshot_info](../../../iris_vector_graph/_engine/snapshot.py#L1051-L1074), [save_snapshot metadata](../../../iris_vector_graph/_engine/snapshot.py#L835-L1048), [API reference](../../../docs/API_REFERENCE.md#L2244-L2251), [ADMIN_GUIDE §8](../../../docs/ADMIN_GUIDE.md#L976-L1000)
- Expands: [Snapshots](#install.snapshot)
- agent
- operations
- design-verified
- Formal: [`theorem_snapshot_info_matches_restore`](../../Verus_verification/models/operator_reports/operator_reports.rs)

Observed (iteration 52): `version` "1.1", `metadata.ivg_version` "4.7.0", and `KeyError` for a ZIP without `metadata.json`.

State machines: [operator reports](../../Verus_verification/models/operator_reports/manifest.json)

### install.bulk_load

- uncertain
- Sources: [ADR-0008](../../../docs/adr/0008-the-adjacency-index-is-maintained-by-the-engine.md); [_engine/nodes_edges.py](../../../iris_vector_graph/_engine/nodes_edges.py); [bulk_loader.py](../../../iris_vector_graph/bulk_loader.py); [structure.adjacency.bulk](../architecture/adjacency-and-derived-data.g5.md#structure.adjacency.bulk)
- Children: [loader](#install.bulk_load.loader), [ledger](#install.bulk_load.ledger), [rebuild](#install.bulk_load.rebuild), [Is BulkLoader meant to be the only writer, on single-edge graphs, outside the ledger?](../../Verus_verification/open_questions.md#q-plt-005)
- agent
- architecture-decision, data-integrity
- test-coverage

The engine paths drop indexes only for batches of 500 rows or more. Inside a caller's transaction, `bulk_load_session` keeps its indexes and leaves the adjacency to rebuild after the caller commits (4.7.0); that rule is owned by [structure.adjacency.bulk](../architecture/adjacency-and-derived-data.g5.md#structure.adjacency.bulk). Observed divergence (review round 3 R3-reader M6): spec 252 FR-008 and ADR-0008 require every `%NOINDEX` bulk path to rebuild before it returns, but `BulkLoader.load_nodes` and `load_edges` tell the caller to call `rebuild_all_indices()` ([bulk_loader.py](../../../iris_vector_graph/bulk_loader.py#L380-L395)). Live coverage: `tests/integration/test_bulk_loader_live.py`, `tests/integration/test_bulk_loader_endpoints.py`.

Findings: [An interrupted BulkLoader node load cannot be resumed: re-loading skips the labels and properties of nodes already written](../../Verus_verification/bugs_issues.md#bug-plt-011); [BulkLoader's node and edge loads write without indexes and return before rebuilding them](../../Verus_verification/bugs_issues.md#bug-plt-027)

Open questions: [Is BulkLoader meant to be the only writer, on single-edge graphs, outside the ledger?](../../Verus_verification/open_questions.md#q-plt-005)

### install.bulk_load.loader

- Sources: [bulk_loader.py](../../../iris_vector_graph/bulk_loader.py); [USER_GUIDE](../../../docs/USER_GUIDE.md); [ADR-0016](../../../docs/adr/0016-one-ivg-schema-per-namespace.md); endpoints: [`iris_vector_graph/bulk_loader.py::BulkLoader._register_endpoints`](../../../iris_vector_graph/bulk_loader.py#L201-L228) (indexed insert into the loader's graph); refusals: [`::BulkLoader._executemany_batched`](../../../iris_vector_graph/bulk_loader.py#L83-L154) (batch failure or short count goes row by row `:118-143`; `BulkLoadError` `:126`, `:142`); live tests [test_bulk_loader_endpoints.py](../../../tests/integration/test_bulk_loader_endpoints.py), unit `tests/unit/test_bulk_loader_unit.py::TestExecutemanyBatched::test_non_unique_error_raises`
- Playbook: [WRT-B7.12](../../../experiment/playbook-completion/ontology/03-writes.md#L207), [WRT-B7.14](../../../experiment/playbook-completion/ontology/03-writes.md#L209)
- Verus: [bulk_load](../../Verus_verification/models/bulk_load/NOTES.md) `theorem_complete_rerun_is_noop`, `theorem_interrupted_load_is_never_completed`, `theorem_noindex_invisible_until_rebuild`, `theorem_done_then_rebuild_reads_input`, `theorem_same_id_other_graph_is_written`, `theorem_loader_without_schema_writes_nothing`, `theorem_rebuild_in_other_schema_leaves_rows_unreadable` (as-built, node loads). Endpoint registration and the duplicate-or-refusal decision have no formal contract; the playbook's `proofs-d1c` `bulk_l2` (reviewed design) models chunk checkpoints only.
- Expands: [Bulk loading](#install.bulk_load)
- agent
- user-facing-behavior, operations

Metadata note: the phase order and the re-run outcome after an interrupted load are in the statement; the default unindexed load's visibility is owned by [rebuild](#install.bulk_load.rebuild).

Public case M23. A repeat is told from a refusal by the error text: SQLCODE -119 or the word "unique" in the message (`bulk_loader.py:105-106`), so a non-repeat refusal whose message happens to contain "unique" would be skipped as a repeat (code reading; not run). Observed divergence: the loader defaults to `Graph_KG`, and its index rebuild names the `Graph_KG` table classes whatever schema it was given.

Findings: [BulkLoader ignores the namespace's IVG Schema](../../Verus_verification/bugs_issues.md#bug-plt-012); [An interrupted BulkLoader node load cannot be resumed: re-loading skips the labels and properties of nodes already written](../../Verus_verification/bugs_issues.md#bug-plt-011); [BulkLoader's node and edge loads write without indexes and return before rebuilding them](../../Verus_verification/bugs_issues.md#bug-plt-027)

State machines: [bulk load](../../Verus_verification/models/bulk_load/manifest.json)

### install.bulk_load.ledger

- Sources: [Ledger API contract: strict-mode guard](../../../specs/213-graph-revision-ledger/contracts/ledger-api.md); [ledger.strict](../features/ledger.g5.md#ledger.strict)
- Expands: [Bulk loading](#install.bulk_load)
- agent
- data-integrity

Audit (HD-0301): Existing authority: The standalone BulkLoader and raw SQL are expressly outside the client strict-mode guard. That exception does not exempt other engine writers. See [current behavior, alternatives and settling sources](../../Verus_verification/audits/register-20261115/question-review.md#HD-0301).

Findings: [Does ledger strict mode cover the standalone bulk loader?](../../Verus_verification/open_questions.md#HD-0301).

### install.bulk_load.rebuild

- Sources: [bulk_loader.py](../../../iris_vector_graph/bulk_loader.py); [_engine/nodes_edges.py _rebuild_after_load](../../../iris_vector_graph/_engine/nodes_edges.py); [ADR-0011](../../../docs/adr/0011-the-adjacency-index-has-one-writer-module.md); [ADR-0012](../../../docs/adr/0012-degree-is-served-from-a-generation-validated-cache.md)
- Verus: [bulk_load](../../Verus_verification/models/bulk_load/NOTES.md) `theorem_done_then_rebuild_reads_input` (`BulkLoader.rebuild_all_indices` for node loads)
- Expands: [Bulk loading](#install.bulk_load)
- agent
- data-integrity

The warning for an index that was not rebuilt dates from 4.6.0 (R257). The `BulkLoader` rebuild goes through the adjacency index's own writer, so it keeps ADR-0011's single writer. No test checks the degree cache or the token after a bulk load.

Findings: [Rebuild adjacency once after load_networkx](../../Verus_verification/design_simplification.md#simp-plt-004)

State machines: [bulk load](../../Verus_verification/models/bulk_load/manifest.json)
