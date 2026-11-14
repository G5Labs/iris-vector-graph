# Review follow-up: R-01, R-02, R-03, R-04, R-10

Lane `followup`, pin `3eaa79cf`. Live work only in `AUDITA`, through the pin's public Python API, every IRIS command
under `tools/locks.sh iris`, at most two connections. Each check began and ended with `Eraser.EraseAll` and
`Ledger.PurgeAll`. Nothing was compiled and no product file was changed (`check-product-scope.sh` passed at every
registration). Finding records: `followup/findings.json`. Raw logs: `$RUN_DIR/followup/`.

| Item | Disposition | Finding | Evidence |
|---|---|---|---|
| R-01(a) snapshot archives | reproduced-live, S2 | F-C1304 | `fu-r01a-snapshot-copies` |
| R-01(b) embedding_quarantine | confirmed-source (by design), S3 | F-C1305 | `fu-r01b-quarantine-erase-plan`, Eraser.cls:300-302, 752-758 |
| R-01(c) legacy `Graph_KG.ledger_revisions` | confirmed-source, S1, confidence medium | F-C1306 | legacy.py:606-646, LedgerRedact.cls:351-376, schema.py:2223-2226 |
| R-02 writer census | census corrected, obligations listed | none (tool) | `followup-writer-census` (incomplete) |
| R-03 marker held open | reproduced-live, S2 | F-C1307 | `fu-r03-marker-held-open` |
| R-04 temporal-only edges | reproduced-live, S1 | F-C1308, F-C1203 | `fu-r04-temporal-only-live-b` (and `-a`) |
| R-10 target digest | reproduced-live, S3 | F-C1309 | `fu-r10-target-digest`, `fu-r01a-snapshot-copies` |

## R-01: tenant copies the receipt does not name

**(a) Snapshot archives (F-C1304).** The probe used `engine.save_snapshot`, the same call `POST /admin/snapshot` makes
(cypher_api.py:668-678). It wrote archives before the erase, after the erase and after the redaction. The redaction
completed, `verify()` reported equal, and the SC-001 scan of the ledger found no tenant tokens. Two of the three
archives still held the tenant:
- The pre-erase archive held the content tables, the ledger records and `LedgerRevisionD` with the revision's
  message, source, correlation id and idempotency key.
- The post-erase archive held the full history.

The receipt names only exports, journals and backups. Restoring the pre-erase archive brought back the content, the
history, the revision free text and the live idempotency binding.

**(b) Quarantine (F-C1305).** The behaviour is by design (FR-039/040), and the pin's own tests for it pass. The gap
is that neither the receipt nor ADR-0013 mentions the quarantine. No live row was built. The only writer is the 4.0.0
migration from a 3.2.0 install, and planting a row by SQL would bypass the product path.

**(c) Legacy revision rows (F-C1306).**
- **What the source shows.** `copy_ledger_history` copies the rows and leaves the `Graph_KG` originals in place. The
  deploy rewrites `ClearRevision`'s `Graph_KG.ledger_revisions` to the IVG Schema's table, so a redaction clears only
  that copy. Migration step 4 (`%NODELDATA`) drops the legacy table but leaves its rows in `^Graph.KG.LedgerRevisionD`.
- **Why the pin can't build it here.** Setup refuses a namespace whose recorded schema differs (schema.py:2223-2226),
  so the copy path only runs on an unrecorded namespace with 4.5.x ledger rows.
- **What a live probe needs.**
  1. The upstream fixture `tests/e2e/test_460_upgrade_ledger_history_e2e.py`, which builds `IVG262FX8U` by compiling
     v4.5.1's code.
  2. The pin's `initialize_schema(schema_prefix="RAG")`.
  3. An erase and `redact(None, prefix="r114", separator=":")`.
  4. A scan of both `Graph_KG.ledger_revisions` and `RAG.ledger_revisions`.

  This would compile a non-pin release into a new scratch namespace, so it is outside this lane's scope. The
  orchestrator can schedule it under the scratch-namespace rule.

## R-03: one writer blocks every tenant (F-C1307)

The probe confirmed every part of the review's claim:
- A bounded run left the marker set.
- `engine.create_node` into the marked target was accepted (non-strict ledger), while a ledger commit into the target
  was refused.
- Re-running the redaction was refused at the entry liveness check.
- A second connection held the head lock and wrote the target during the wait. The run then tombstoned every target
  record, and Final refused with "became live again". The marker stayed.
- While the marker existed, tenant B's `get_revision`, `diff` and `reconstruct` were refused, `verify()` returned
  `redaction_in_progress`, and the redaction of erased tenant C was refused.
- `history()` was not refused and returned the half-done state (this belongs to the reader part of R-02).
- Only erasing the target again cleared it. There is no abandon call: only Final (LedgerRedact.cls:439) and `PurgeAll`
  remove the marker.

## R-04: temporal-only edges (F-C1308, F-C1203)

The control behaved as expected: with a structural temporal predicate, the redaction is refused because the target
is live. With a temporal-only predicate (ADR-0015):
- **Graph target, not erased.** No content row exists, so `redact(graph)` completes and tombstones the
  `create_temporal_edge` record. The edge is still returned by `get_edges_in_window`.
- **Prefix tenant, documented erase-then-redact order.** `delete_nodes_by_prefix` leaves the temporal-only edge
  (F-C1203: `EraseNodes` selects ids from `Graph_KG.nodes` only). The redaction then completes with the edge still
  live.
- **`verify()`.** It reports equal in both cases, so it cannot notice.

The first run (`-a`) reported "diverges" because its control graph was left live. The rerun (`-b`) erased the control
graph and is the decisive record.

## R-10: target digest (F-C1309)

The redaction revision stores `target_sha256`, readable through `history()` and SQL. It equals
SHA-256(`"" NUL "fu1|"`), which is also what `LedgerRedact.TargetDigest` returns. A dictionary of 200,006 names
confirmed exactly `fu1` in 0.13 s, about 1.5 million guesses per second on one Python core.

This conflicts with spec 256 Decision 1 and with ADR-0013's "Nothing in it comes from the target". Which intent wins
is undecided: a content-free audit, or one an auditor can verify. That is a maintainer question.

## R-02: corrected writer census

`tools/writer_census.py` now also sees writes whose table or global name is built at run time:
- **Python SQL text.** f-strings, `+`, `%` and `.format`, with table-name calls such as `self._t('nodes')` and
  `_table('rdf_edges')` rendered to the table. A run-time table variable is resolved from constants, loops, tuple
  assignment, module dicts, or one level of callers.
- **ObjectScript.** `"INSERT INTO " _ pSchema _ ".nodes"` joined across lines and resolved from `Set` and `For`;
  `Set/Kill/Merge @ref`; and `$System.OBJ.Load`.
- **Ledger globals.** `^IVG.Ledger("meta")` (Disable/SetStrict) as store `state`.
- **Native API.** Writes with a variable global name. Restore is resolved through its `restorable_globals` allow-list
  (the one declared `RESOLVE_HINTS` entry).
- **Unguarded SQL surface.** The SQL INSERT into `ledger_revisions`, which no trigger refuses.
- **Macros.** iris_src defines no `$$$` macros of its own, so there were none to resolve.

Cleanups:
- Docstrings are skipped.
- Sites are de-duplicated; the original census counted an f-string twice.
- A nested helper belongs to the function that encloses it.
- Python callees resolve to a same-file definition first.
- DB-API and protocol names are not followed. Measured on the pin, that only removed the 4.0.0 migration's helpers.

Self-test: the original assertion still passes, and four planted writers are all found: the original stray plus an
f-string table, an ObjectScript concatenated table and a variable-name `^IVG.Ledger` write. As a control, the
original census at HEAD misses all three planted dynamic writers and reproduces its registered numbers (log:
`$RUN_DIR/followup/writer-census.log`).

| | original (`writer-census`) | corrected (`followup-writer-census`) |
|---|---|---|
| sites (distinct lines) | 104 | 269 (267) |
| inside the 15 plan ranges | 31 | 48 |
| reached by call from a plan | 25 | 138 (86 are Cypher translator sites, via `cypher.write`) |
| outside every plan | 48 | 83 |
| writer methods no plan declares | 25 | 46 |
| (invariant, writer) obligations | 100 | 162 (62 new pairs; 8 re-attributed after 2 renames) |
| conditional obligations (unresolved name) | – | 20, for 4 writers |
| write-set-gap obligations | – | 3 |

**23 new uncovered writers:**
- `<any SQL client>::INSERT INTO Graph_KG.ledger_revisions`
- `Snapshot.cls::ImportGlobals` and `::SetNodeJSON` (any global, 8 obligations each)
- `Ledger.cls::Disable` and `::SetStrict` (state, no invariant reads it)
- `legacy.py::copy_ledger_history`
- `bulk_loader.py::_register_endpoints` (BulkLoader)
- `temporal.py::create_edge_temporal`, `::bulk_create_edges_temporal` and `::_mirror_node`
- `nodes_edges.py::store_edge`, `::set_edge_weight` and `::_drop_orphaned_props`
- `schema.py::reify_edge`, `::delete_reification` and `::tighten_graph_id_column`
- `snapshot.py::import_rdf`
- `dbapi_utils.py::insert_vector`
- `graph_scoped_embeddings.py::_backfill_graph_id`, `::_dedupe` and `::_redistribute` (unresolved, conditional)
- Two renames: `nodes_edges.py::?` is now `bulk_create_edges`, and `_write_inferred` is now `materialize_inference`

**Write-set gaps.** `restore_snapshot` writes the redaction stores `marker`, `idemRedacted` and `redactedRev`
(snapshot.py:1679). The plan `snapshot.restore_replace` does not declare them, which gives `INV-marker`, `INV-retry`
and `INV-text`. The pairs are in the manifest's coverage, but their justification did not consider these stores.

**Ledger-global writers outside the ledger classes:**
- `restore_snapshot` (`_import_global_from_ndjson`)
- `Snapshot.ImportGlobals` and `Snapshot.SetNodeJSON`
- `legacy.copy_ledger_history`
- the SQL INSERT surface
- the Eraser's `stmt`/`tuple` kills (declared)

Still open: the census is lexical. 15 sites have unresolved run-time names (5 of them, in 4 writers, outside every plan). Reach is by name.
`Disable`/`SetStrict` matter for progress, not for any of the 8 manifest invariants. The inferred revision-insert
wedge (R-02) was not probed.

## For the orchestrator

- Add F-C1304 to F-C1309 and F-C1203 to the module 13/12 finding sets. Add the 62 new obligations, 20 conditional
  obligations and 3 write-set gaps to the §3.3a matrix as open.
- Schedule the 4.5.1 upgrade probe for F-C1306.
- Add "no writer makes a marked target live" as a progress premise (P-C02).
