# Writer-census obligations of gate 3.3a-writesets: discharges

Lane `writesets`, pin `3eaa79cf`. Playbook §3.3a item 5 and the gate "no uncovered (invariant, plan) pair" for the
corrected writer census (`followup-writer-census`; `matrix-input/writer-census-obligations.json`: 162 WS-OBL, 20
WS-COND, 3 WS-GAP = 185 cells). Live work only in `AUDITB` (the pin by its own `initialize_schema`, re-checked
`ws-deploy-auditb`: 66 classes unchanged), every IRIS command under `tools/locks.sh iris`, at most 4 connections,
through the product's own entry points. Raw logs: `$RUN_DIR/writesets/`. Nothing compiled, no product file changed
(`check-product-scope.sh` passed before every registration).

Files: `DISCHARGES.json` (one entry per census obligation id and per open module cell, `module:NN`),
`tools/build_discharges.py` (the per-writer analysis that generates it), `tools/check_discharges.py` (checker and
self-test), `live/ws_probes.py` (probes), `MATRIX-INPUT.json` (module cells), `../findings/audit/zz-writesets.json`
(new findings).

## Method

1. **Writers as entry points.** A census writer is the function that owns a write site. Its obligation is judged on
   what one call of it can write, callees included (store_edge's endpoint nodes, ResyncKey's EnsureNode), because that
   is what a caller can make it do and what a live probe exercises. Every writer's code was read at the pin
   (`path:lines` in each entry).
2. **The invariants as the product implements them.** INV-marker reads marker, rec and content: while the marker names
   t no record of t is added and t's content stays not live (the condition under which batches may tombstone and Final
   can finish; LiveRows `LedgerRedact.cls:149-178`, Final `:409-416`). INV-no-live-tombstone: a record becomes a
   tombstone only while its content is not live (RED-B1.1, the product's own entry and Final checks). INV-replay holds
   under "no unrecorded writes" (RPL-B3), unrecorded writes being classified by verify() (RPL-B7.1,
   `replay.py:645-698`). INV-stmt: the live statements are exactly the live recorded edges (ERS-I2/I3). The L1 model's
   `marker_ok` reads only history; a bypass write is the L1 `Write` step and preserves it, which is why the original
   manifest discharged these pairs; the as-built content reading is what the probes test.
3. **Structural facts that decide many pairs.** (a) `LiveRows` counts node, label, property and edge rows of a target;
   record membership (`Matches`, `:89-112`) reads only ledger globals, never content. (b) Edge rows carry composite
   foreign keys to their endpoint nodes and label rows to their node (`schema.py:34-44, 403-409`); property rows have
   none (`:411-418`). So edge or label rows alone never turn a target live or not live: an edge that matches a target
   has an endpoint node row that matches it too (live: `ws-live-fk-guard`). (c) Only ledger commits read the marker
   (`BlocksCommit`, `:258-269`); no census writer reads `^IVG.Ledger("redacting")` (grep of every writer's file).
   (d) `BatchInLock` (`:302-330`) tombstones without re-checking liveness. (e) `LiveRows` reads uncommitted data, and
   `WriteTxn` (`_write_txn.py:1-30`) nests a writer's work in a caller's transaction.
4. **Live probes** (`live/ws_probes.py`, journal oracle `traces/journal.py` for what each writer's process wrote):
   - `ins-*` (12 inserters): INV-replay sub-check (verify before/after a write of a control tenant; journal: content
     written, no `^IVG.Ledger` node), then the interleave: target erased; a redaction passes its entry check while a
     second connection holds `^IVG.Ledger("head")` (as a concurrent commit does) and waits; the writer writes the
     target; the journal orders the writer's commit before every tombstone; Final refuses, the marker stays, verify()
     = redaction_in_progress, a commit into the target and a re-run are refused.
   - `rb-delete_reification`: F-C1301 with a real bypass deleter inside a caller transaction (phase 1: redaction
     completes, rollback restores content under tombstones; phase 2: bounded run, rollback makes the marked target live).
   - `stmt-collision`, `stmt-purge`: ledger relationships whose qualifiers carry the temporal or inferred marker key.
   - `snap-importglobals`/`snap-helpers`, `snap-setnodejson`, `sql-guard`, `sql-insert`, `gap-restore`, `gap-marker`,
     `migrations`, `fhir-blocked`, and (outside the census) `noindex`.
5. **One discharge per obligation** (`tools/build_discharges.py`): lemma (proved / mc / live / inspected; inspected is
   the weakest and is labelled so), guard (a check in the code, confirmed live), finding (a finding whose evidence covers
   this writer: the cited ws-live run is that evidence where the finding's own record does not cover it), or open with
   the exact reason. A finding closes the verification cell; the product obligation stays failed.

## Registered runs

| Run | Result | Observes |
|---|---|---|
| `ws-deploy-auditb` | pass | AUDITB holds the pin (initialize_schema: 66 classes unchanged) |
| `ws-live-ins-<writer>` x12 | fail | store_node, store_edge, bulk_create_nodes (BulkIngestNodesSQL+RegisterDefaultNode), bulk_ingest_edges (BulkIngestEdgesSQL), bulk_create_edges, store_write_nodes, store_write_edges, create_edge_temporal, bulk_create_edges_temporal, reify_edge, bulkloader_load_edges (_register_endpoints), import_rdf: each tombstones 7 records of a target the writer made live after the entry check; marker held |
| `ws-live-fk-guard` | pass | edge and label rows without their node refused; a property row accepted |
| `ws-live-fc1301-delete-reification` | fail | F-C1301 live: redaction completes on an uncommitted delete; rollback restores content under tombstones; bounded run: marker names a live target |
| `ws-live-stmt-collision` | fail | RetractTemporalRow, DropRows, retract_inference delete ledger relationships (qualifiers temporal=1 / inferred), statements stay live |
| `ws-live-stmt-purge` | fail | purge_before -> RetractTemporalRows fallback deletes a ledger relationship, statement live |
| `ws-live-snap-importglobals` | fail | ImportGlobals overwrites ^IVG.Ledger rec/head/meta with another history's export |
| `ws-live-snap-setnodejson` | pass | SetNodeJSON refuses every invariant store (40 calls), writes nothing |
| `ws-live-sql-guard` | pass | INSERT of an existing seq refused (SeqIdx), UPDATE refused (trigger), text stays cleared |
| `ws-live-sql-insert-wedge` | fail | an SQL INSERT of seq head+1 is accepted and every later commit fails |
| `ws-live-gap-restore` | fail | after a replacing restore, a second redaction keeps the revision's text and live retry key; a retry replays it |
| `ws-live-gap-marker` | fail | a marker survives a replacing restore that brings the target back live |
| `ws-live-migrations` | fail | three migrations leave a marked target untouched; add_graph_id_to_nodes moves a '__graph' node into it |
| `ws-live-fhir-blocked` | blocked | no FHIR repository in AUDITB (HS_FHIRServer absent): FHIR writers not runnable |
| `ws-live-noindex` | fail | (outside the census) %NOINDEX bulk-load rows invisible to LiveRows: redaction completes on a live tenant |
| `ws-check`, `ws-check-selftest` | pass | this checker on DISCHARGES.json; 19/19 seeded mutations caught |

## Counts

185 census obligations: **lemma 105** (inspected 85, live 20), **finding 64** (live 41, inspected 23), **guard 9** (live 9),
**open 7**.

| Invariant | lemma | guard | finding | open |
|---|---|---|---|---|
| INV-marker (43) | 15 | 1 | 26 | 1 |
| INV-no-live-tombstone (42) | 15 | 1 | 25 | 1 |
| INV-replay (42) | 40 | 1 | 1 | 0 |
| INV-stmt (42) | 31 | 1 | 5 | 5 |
| INV-text (9) | 4 | 2 | 3 | 0 |
| INV-retry (3) | 0 | 1 | 2 | 0 |
| INV-isolation (2) | 0 | 1 | 1 | 0 |
| INV-shape (2) | 0 | 1 | 1 | 0 |

S1 invariants (INV-text, INV-isolation, INV-no-live-tombstone, INV-marker; 96 cells): 94 discharged, 2 open.

## Per writer

L lemma, G guard, F finding, O open; live / insp(ected).

| Writer | Mod | INV-marker | INV-no-live-tombstone | INV-replay | INV-stmt | other |
|---|---|---|---|---|---|---|
| `dbapi_utils.py::insert_vector` | 17 | L/insp | L/insp | L/insp | L/insp | text: L/insp |
| `migrations/graph_scoped_embeddings.py::_backfill_graph_id` | 06 | L/insp | L/insp | L/insp | L/insp | text: L/insp |
| `migrations/graph_scoped_embeddings.py::_dedupe` | 06 | L/insp | L/insp | L/insp | L/insp | text: L/insp |
| `migrations/graph_scoped_embeddings.py::_redistribute` | 06 | L/insp | L/insp | L/insp | L/insp | text: L/insp |
| `_engine/snapshot.py::_import_global_from_ndjson` | 18 | F/live F-C1850,F-1801 | – | – | – | retry: F/live F-C1850,F-1801; text: F/live F-C1850,F-1801 |
| `<any SQL client>::INSERT INTO Graph_KG.ledger_revisions` | 11 | – | – | – | – | text: G/live |
| `Adjacency.cls::RetractTemporalRow` | 04 | L/insp | L/insp | L/live | F/live F-C0450 | – |
| `Adjacency.cls::RetractTemporalRows` | 04 | L/insp | L/insp | L/live | F/live F-C0450 | – |
| `EdgeScan.cls::BulkIngestEdgesSQL` | 04 | F/live F-C1307 | F/live F-C1350 | L/live | L/insp | – |
| `EdgeScan.cls::BulkIngestNodesSQL` | 04 | F/live F-C1307 | F/live F-C1350 | L/live | L/insp | – |
| `EdgeScan.cls::RegisterDefaultNode` | 04 | F/live F-C1307 | F/live F-C1350 | L/live | L/insp | – |
| `Eraser.cls::DeleteBareSet` | 12 | F/insp F-C1301 | F/insp F-C1301 | L/live | L/insp | – |
| `FHIRGraph.cls::DeleteEdge` | 15 | L/insp | L/insp | L/insp | O | – |
| `FHIRGraph.cls::DropNode` | 15 | F/insp F-C1301 | F/insp F-C1301 | L/insp | O | – |
| `FHIRGraph.cls::EnsureNode` | 15 | F/insp F-C1307 | F/insp F-C1350 | L/insp | L/insp | – |
| `FHIRGraph.cls::ResyncKey` | 15 | F/insp F-C1307 | F/insp F-C1350 | L/insp | O | – |
| `FHIRGraph.cls::SyncProps` | 15 | F/insp F-C1307 | F/insp F-C1350 | L/insp | L/insp | – |
| `Snapshot.cls::ImportGlobals` | 18 | F/insp F-1806 | F/insp F-1806 | F/live F-1806 | F/insp F-1806 | shape/isolation/text/retry: F/insp F-1806 / F/live F-1806 |
| `Snapshot.cls::SetNodeJSON` | 18 | G/live | G/live | G/live | G/live | shape/isolation/text/retry: G/live |
| `TemporalPolicy.cls::DropRows` | 05 | F/insp F-C1301 | F/insp F-C1301 | L/live | F/live F-C0450 | – |
| `_engine/legacy.py::copy_ledger_history` | 01 | – | – | – | – | text: F/live F-C1306 |
| `_engine/nodes_edges.py::_drop_orphaned_props` | 03 | F/insp F-C1301 | F/insp F-C1301 | L/insp | L/insp | – |
| `_engine/nodes_edges.py::bulk_create_edges` | 03 | F/live F-C1307 | F/live F-C1350 | L/live | L/insp | – |
| `_engine/nodes_edges.py::bulk_ingest_edges` | 03 | F/live F-C1307 | F/live F-C1350 | L/live | L/insp | – |
| `_engine/nodes_edges.py::set_edge_weight` | 03 | L/insp | L/insp | L/insp | L/insp | – |
| `_engine/nodes_edges.py::store_edge` | 03 | F/live F-C1307 | F/live F-C1350 | L/live | L/insp | – |
| `_engine/nodes_edges.py::store_node` | 03 | F/live F-C1307 | F/live F-C1350 | L/live | L/insp | – |
| `_engine/schema.py::delete_reification` | 15 | F/live F-C1301 | F/live F-C1301 | L/live | L/insp | – |
| `_engine/schema.py::materialize_inference` | 01 | L/insp | L/insp | L/insp | L/insp | – |
| `_engine/schema.py::reify_edge` | 15 | F/live F-C1307 | F/live F-C1350 | L/live | L/insp | – |
| `_engine/schema.py::retract_inference` | 01 | L/insp | L/insp | L/live | F/live F-C0151 | – |
| `_engine/snapshot.py::import_rdf` | 18 | F/live F-C1307 | F/live F-C1350 | L/live | L/insp | – |
| `_engine/temporal.py::_mirror_node` | 05 | F/insp F-C1307 | F/insp F-C1350 | L/insp | L/insp | – |
| `_engine/temporal.py::bulk_create_edges_temporal` | 05 | F/live F-C1307 | F/live F-C1350 | L/live | L/insp | – |
| `_engine/temporal.py::create_edge_temporal` | 05 | F/live F-C1307 | F/live F-C1350 | L/live | L/insp | – |
| `bulk_loader.py::_register_endpoints` | 03 | F/live F-C1307 | F/live F-C1350 | L/live | L/insp | – |
| `schema.py::_restore_rescued_rdf_edges` | 01 | L/insp | L/insp | L/insp | L/insp | – |
| `schema.py::add_graph_id_to_nodes` | 01 | F/live F-C0150 | F/insp F-C0150 | L/insp | L/insp | – |
| `schema.py::ensure_ekey` | 01 | L/insp | L/insp | L/insp | L/insp | – |
| `schema.py::ensure_props_value_key` | 01 | L/insp | L/insp | L/insp | L/insp | – |
| `schema.py::tighten_graph_id_column` | 01 | L/insp | L/insp | L/insp | L/insp | – |
| `stores/iris_sql_store.py::_delete_nodes_sql` | 17 | O | O | L/insp | O | – |
| `stores/iris_sql_store.py::delete_edges` | 17 | L/insp | L/insp | L/insp | O | – |
| `stores/iris_sql_store.py::write_edges` | 17 | F/live F-C1307 | F/live F-C1350 | L/live | L/insp | – |
| `stores/iris_sql_store.py::write_nodes` | 17 | F/live F-C1307 | F/live F-C1350 | L/live | L/insp | – |

## Open (7)

| Id | Writer | Invariant | Reason |
|---|---|---|---|
| WS-OBL-029 | FHIRGraph.DeleteEdge | INV-stmt | blocked-access (HS_FHIRServer absent, `ws-live-fhir-blocked`); inspected: deletes an rdf_edges row by edge_id with no statement cleanup, called by ResyncKey/DropNode for rows the repository does not want, a ledger relationship in a FHIR graph included |
| WS-OBL-033 | FHIRGraph.DropNode | INV-stmt | same: DropNode deletes every edge naming the key through DeleteEdge (FHIRGraph.cls:2406-2440) |
| WS-OBL-041 | FHIRGraph.ResyncKey | INV-stmt | same: ResyncKey's edge diff (FHIRGraph.cls:2216-2240) |
| WS-OBL-147, -148, -150 | iris_sql_store._delete_nodes_sql | INV-marker, INV-no-live-tombstone, INV-stmt | unreached at the pin's deploy: the SQL fallback runs only when `_has_eraser_method` answers False (iris_sql_store.py:1307-1318; any probe exception is cached as absent); on that path it deletes recorded rows with no statement cleanup inside a WriteTxn that can roll back; not reproduced |
| WS-OBL-154 | iris_sql_store.delete_edges | INV-stmt | same fallback (iris_sql_store.py:1504-1518) |

## New findings (`findings/audit/zz-writesets.json`)

| Id | Title | Severity | Evidence |
|---|---|---|---|
| F-C1350 | Redaction batches tombstone the history of content a ledger-bypassing writer made live after the run's entry check | S1, high | 12 `ws-live-ins-*` |
| F-C1351 | The liveness check misses rows a %NOINDEX bulk load wrote: the redaction completes while the tenant's rows exist | S1, high | `ws-live-noindex` (outside the census) |
| F-C1850 | A replacing restore leaves the live ledger's marker, redactedRev and idemRedacted: a marked target comes back live; a second redaction keeps the revision's text and retry key | S1, high | `ws-live-gap-restore`, `ws-live-gap-marker` |
| F-C0450 | A ledger relationship whose qualifiers hold temporal=1 is deleted as a temporal edge's derived row; its statement stays live | S2, high | `ws-live-stmt-collision`, `ws-live-stmt-purge` |
| F-C0151 | retract_inference deletes a ledger relationship with an 'inferred' qualifier key; its statement stays live | S2, high | `ws-live-stmt-collision` |
| F-C0150 | initialize_schema moves a node with a '__graph' property into that graph (also into a marked graph); the engine still writes such a property | S2, high | `ws-live-migrations` |
| F-C1150 | An SQL INSERT into Graph_KG.ledger_revisions is accepted; a row at head+1 makes every later commit fail | S2, high | `ws-live-sql-insert-wedge`, `ws-live-sql-guard` |

## Existing findings this lane's runs extend (the orchestrator may add the runs to their records)

- **F-C1301** (reproduced-model): now reproduced live with a real bypass deleter (`ws-live-fc1301-delete-reification`).
- **F-C1307**: the same defect live for 12 more writers (`ws-live-ins-*`); FHIR writers by inspection.
- **F-1806**: ImportGlobals shown overwriting the ledger global (`ws-live-snap-importglobals`); its record showed only
  that the method is callable.

## Observations for the orchestrator

- F-C1301's note says it contradicts WRITESETS.md:62 (`engine.direct_edge_delete`: "removes content only"). For an
  edge-only delete that claim survives: an edge row that matches a target has an endpoint node row that matches it
  (composite foreign keys), so deleting edges, committed or not, never makes a live target look not live. F-C1301
  applies to writers that delete node rows (or a target's only rows); the discharges here follow that split.
- The census reads `Snapshot.SetNodeJSON`'s `Set @tRef` as "any global"; NodeRef's allow-list (^IVF, ^PLAID, ^VecIdx)
  refuses every invariant store (guard, live).
- verify() reads node rows graph-blind (`replay.py:597-600`), so add_graph_id_to_nodes' cross-graph move is invisible
  to it (F-1304/F-1305's blindness).
- Interpretation recorded in F-C1350's notes: the original discharge ("old records of an erased id are erased history")
  is the alternative reading; the product's own entry and Final checks treat such rows as live.

## Re-running

    bash experiment/playbook-completion/tools/locks.sh iris timeout 1200 \
        python experiment/playbook-completion/writesets/live/ws_probes.py ins-all
    bash experiment/playbook-completion/tools/locks.sh iris timeout 900 \
        python experiment/playbook-completion/writesets/live/ws_probes.py rb-delete_reification stmt-collision stmt-purge \
        snap-helpers snap-setnodejson sql-guard sql-insert gap-restore gap-marker migrations fhir-blocked fk-guard noindex
    python experiment/playbook-completion/writesets/tools/build_discharges.py
    python experiment/playbook-completion/writesets/tools/check_discharges.py
    python experiment/playbook-completion/writesets/tools/check_discharges.py --self-test
