# Shared mechanisms of IVG (playbook 3.3a step 2)

Product pin `3eaa79cf`. Semantics lane. Machine-readable: `mechanisms.json` (built by `tools/build_semantics.py` from
`src/mechanisms_src.json` and `models/semantics/RESULTS.json`); rendered by `tools/render_docs.py`. Models:
`models/semantics/` (explorer and actors at `c03f9fa`), one file per mechanism.

**How the models are generic.** Each mechanism is one machine generic over a trait (`LedgerObject`, `RetryObject`,
`ExclObject`, `DerivedObject`, ...). Each object (or group of objects with the same variant) that uses the mechanism is
one trait instance that declares its as-built variant (the policies, programs or paths the pin implements, each with
the source lines in the file's comments) and the reviewed variant (the mechanism's canonical policies). The laws are
written once per machine; an instance adds no law. Per instance: as-built checks attributed with `Keep::only` to the law
each variant departs from (the shortest counterexample violates that law), or a pass where the pin keeps every law, and a
reviewed check expected to pass. Per mechanism: at least one negative control per law (a generic mutant of a canonical
instance) and sharpness witnesses. Every check is exhaustive within its declared bounds; none was truncated. All of it is
model-level: a twin abstracts the cited code, it is not the code; these are explorer checks, not Verus lemmas over the
trait (PROOF-DEBT D-14).

**Attribution and the complement (review 4, R4-08).** `Keep::only` keeps only the attributed law, so a counterexample is
a violation *of that law*, not proof that no other law is violated. Since the rerun every Keep check also runs the
complement: each safety law of the underlying model explored alone, recorded in `RESULTS.json` (`violates`,
`also_violates`). Of the 140 violation checks, 58 also violate another law; they are listed per
law below (`also violated by`). For every instance, the laws its as-built model violates equal its declared departures,
each with a finding or a named exception (`check_semantics.py`, rules `departure-undeclared` and `departure-unshown`);
a departure that is a consequence of the same defect in the model says so in its `why`.

Results: 272 checks, 272 met their expectation, 0 truncated (`sem-mc-all-r2`; per family
`sem-mc-<family>-as-built-r2` expected-violation, `sem-mc-<family>-reviewed-r2` pass, `sem-control-<family>-r2`
expected-violation).

## Summary

| Id | Mechanism | Implements | Laws | Objects using it (canonical / hand-rolled) | Declared departures (law, object) | Checks |
|---|---|---|---:|---|---:|---:|
| M-01 | Ledger commit with record | AX-05, AX-07, AX-04 | 4 | 12 (3 / 9) | 9 | 16 |
| M-02 | Retry and idempotency binding | AX-06, AX-12 | 4 | 7 (3 / 4) | 5 | 17 |
| M-03 | Exclusive section: lock and marker | AX-11, AX-12 | 5 | 12 (5 / 7) | 11 | 26 |
| M-04 | Derived store with staleness | AX-08 | 4 | 18 (4 / 14) | 37 | 36 |
| M-05 | Store inventory and removal | AX-10, AX-02, AX-04 | 3 | 13 (4 / 9) | 17 | 27 |
| M-06 | Snapshot save and restore | AX-12, AX-05, AX-10 | 3 | 2 (0 / 2) | 3 | 11 |
| M-07 | Background job and queue | AX-14, AX-12, AX-11 | 4 | 5 (3 / 2) | 5 | 19 |
| M-08 | Install, settings and version gate | AX-09, AX-03 | 4 | 13 (8 / 5) | 5 | 15 |
| M-09 | Graph key and tenant scope | AX-02 | 4 | 22 (7 / 15) | 15 | 19 |
| M-10 | Unit of work: all or none, inert refusal | AX-04, AX-03, AX-12 | 3 | 19 (4 / 15) | 15 | 18 |
| M-11 | Capability gate | AX-13, AX-03 | 3 | 13 (8 / 5) | 8 | 15 |
| M-12 | Catalog binding of artifacts to graph and identity | AX-02, AX-01, AX-08 | 3 | 9 (4 / 5) | 7 | 17 |
| M-13 | Read epoch: consistent multi-step read | AX-12 | 1 | 3 (1 / 2) | 2 | 7 |

## M-01 Ledger commit with record

- Implements: AX-05 History only grows, AX-07 A governed change is recorded with it, AX-04 All or none across stores
- State: governed content C; records R[1..head] (each content, or a tombstone); head; ledger state never-enabled | enabled | disabled; strict flag; an engine's cached copy of the strict flag
- Operations: commit(changeset, expected_head?); insert-if-absent commit (temporal insert mode); write outside the ledger (bypass path); set strict; redact a record (tombstone)
- Effect kinds: append record, change governed content, move head, refuse; events: revision committed (seq, id), refusal code
- Model: `models/semantics/src/ledger.rs` (16 checks, 16 met, exhaustive)

| Law | Kind | Statement | Negative control(s) | As-built checks attributed to it | Also violated by (complement) |
|---|---|---|---|---|---|
| M01-L1 | action | History only grows: every step keeps each record or turns it into its tombstone, and never lowers the head. | `ledger-control-C2-overwrite-record` | - | - |
| M01-L2 | invariant | Record and change together: when no transaction is open, the governed content equals the replay of the records, unless an unrecorded write was allowed (non-strict) and is flagged. | `ledger-control-C1-two-step-record` | `ledger-node-delete-named-only-as-built`, `ledger-temporal-insert-collision-as-built` | - |
| M01-L3 | action | A stale expected head (or a disabled ledger) refuses with a code and changes nothing. | `ledger-control-C3-ignore-head` | - | - |
| M01-L4 | action | Strict mode: no write outside the ledger changes governed content while strict is on. | `ledger-control-C4-unguarded-bypass` | `ledger-strict-cached-guard-as-built`, `ledger-bypass-unchecked-as-built` | - |

| Object | Use | Departures (law: findings or exception; why) | Where (pin) | Model checks |
|---|---|---|---|---|
| 11/ledger | canonical | - | `iris_src/src/Graph/KG/Ledger.cls:397-528` | `ledger-commit-core-as-built`, `ledger-commit-core-reviewed`, `ledger-control-C1-two-step-record`, `ledger-control-C2-overwrite-record`, `ledger-control-C3-ignore-head`, `ledger-control-C4-unguarded-bypass` |
| 11/node-id | hand-rolled | M01-L2: F-1105 | `iris_src/src/Graph/KG/LedgerApply.cls:79-84, 354-385` | `ledger-node-delete-named-only-as-built`, `ledger-node-delete-named-only-reviewed` |
| 05/temporal-coordinates | hand-rolled | M01-L2: F-0511 | `iris_src/src/Graph/KG/LedgerApply.cls (temporal insert op)` | `ledger-temporal-insert-collision-as-built`, `ledger-temporal-insert-collision-reviewed` |
| 03/ledger-state | hand-rolled | M01-L4: F-0302, F-0801 | `iris_vector_graph/ledger/guard.py:20-59` | `ledger-strict-cached-guard-as-built`, `ledger-strict-cached-guard-reviewed`, `ledger-sharp-two-records`, `ledger-sharp-strict-refusal` |
| 03/node-in-one-graph | hand-rolled | M01-L4: F-0301, F-0504, F-1108 | `iris_vector_graph/bulk_loader.py:252-272; iris_vector_graph/_engine/temporal.py:623-641` | `ledger-bypass-unchecked-as-built`, `ledger-bypass-unchecked-reviewed` |
| 03/edge-in-one-graph | hand-rolled | M01-L4: F-0503 | `iris_src/src/Graph/KG/Adjacency.cls:575-603` | `ledger-bypass-unchecked-as-built`, `ledger-bypass-unchecked-reviewed` |
| 08/cypher-node | hand-rolled | M01-L4: F-0801 | `iris_vector_graph/_engine/query.py:2299-2301` | `ledger-strict-cached-guard-as-built`, `ledger-strict-cached-guard-reviewed`, `ledger-sharp-two-records`, `ledger-sharp-strict-refusal` |
| 08/cypher-edge | hand-rolled | M01-L4: F-0801 | `iris_vector_graph/_engine/query.py:2299-2301` | `ledger-strict-cached-guard-as-built`, `ledger-strict-cached-guard-reviewed`, `ledger-sharp-two-records`, `ledger-sharp-strict-refusal` |
| 08/cypher-call | hand-rolled | M01-L4: F-0801 | `iris_vector_graph/ledger/guard.py:20-80` | `ledger-strict-cached-guard-as-built`, `ledger-strict-cached-guard-reviewed`, `ledger-sharp-two-records`, `ledger-sharp-strict-refusal` |
| 11/edge-statement | canonical | - | `iris_src/src/Graph/KG/LedgerApply.cls` | `ledger-commit-core-as-built`, `ledger-commit-core-reviewed`, `ledger-control-C1-two-step-record`, `ledger-control-C2-overwrite-record`, `ledger-control-C3-ignore-head`, `ledger-control-C4-unguarded-bypass` |
| 14/ledger-view | canonical | - | `iris_vector_graph/ledger/replay.py:155-210` | `ledger-commit-core-as-built`, `ledger-commit-core-reviewed`, `ledger-control-C1-two-step-record`, `ledger-control-C2-overwrite-record`, `ledger-control-C3-ignore-head`, `ledger-control-C4-unguarded-bypass` |
| 18/namespace | hand-rolled | M01-L1: F-1801 | `iris_vector_graph/_engine/snapshot.py:1554-1588` | not modelled: shown in the snapshot family: snapshot-replacing-restore-as-built (law M06-L2, the restore form of M01-L1: a restore lowers the head) |

- 11/node-id: a delete of a node only a named graph holds is recorded although it removed nothing; replay then deletes what the store kept
- 03/ledger-state: strict mode is a client-side check over a 5 s cache that fails open
- 03/node-in-one-graph: bulk loader, purges and two other write paths write governed rows with no strict check and no record
- 03/edge-in-one-graph: a temporal write creates node rows the ledger never records
- 14/ledger-view: replay is the L2 law's fold

## M-02 Retry and idempotency binding

- Implements: AX-06 At most once per retry key, AX-12 Truthful outcomes and committed observations
- State: binding per request identity: free | bound(answer, fingerprint) | redacted; effect count; post-commit effect count; a client's view of the answer (seen | lost)
- Operations: send(request); retry same request; retry with another payload under the same key; post-commit step; redact the bound revision
- Effect kinds: apply effect once, bind, replay answer, refuse conflict, refuse redacted; events: answer (first or replayed), idempotency_conflict, idempotency_redacted
- Model: `models/semantics/src/retry.rs` (17 checks, 17 met, exhaustive)

| Law | Kind | Statement | Negative control(s) | As-built checks attributed to it | Also violated by (complement) |
|---|---|---|---|---|---|
| M02-L1 | invariant | At most one effect per request identity (post-commit effects included). | `retry-control-C1-bind-after-effect` | `retry-client-resend-as-built`, `retry-server-rerun-as-built` | `retry-ledger-key-as-built`, `retry-control-C2-post-on-replay`, `retry-control-C3-apply-conflict` |
| M02-L2 | action | A replay returns the first answer and changes nothing. | `retry-control-C2-post-on-replay` | `retry-ledger-key-as-built` | - |
| M02-L3 | action | Another payload under a bound key is refused and changes nothing. | `retry-control-C3-apply-conflict` | - | - |
| M02-L4 | invariant | After the bound revision is redacted, the binding is gone (no replay, no text) and a retry is refused. | `retry-control-C4-redaction-keeps-binding` | `retry-zero-record-revision-as-built` | - |

| Object | Use | Departures (law: findings or exception; why) | Where (pin) | Model checks |
|---|---|---|---|---|
| 11/retry-key | hand-rolled | M02-L1: F-1101, F-1306<br>M02-L2: F-1101, F-1306 | `iris_src/src/Graph/KG/Ledger.cls:454-473; iris_vector_graph/ledger/client.py:418-487` | `retry-ledger-key-as-built`, `retry-ledger-key-reviewed`, `retry-control-C1-bind-after-effect`, `retry-control-C2-post-on-replay`, `retry-control-C3-apply-conflict`, `retry-control-C4-redaction-keeps-binding`, `retry-sharp-replay`, `retry-sharp-conflict`, `retry-sharp-redacted-refusal` |
| 13/redaction-target | hand-rolled | M02-L4: F-CS01 | `iris_src/src/Graph/KG/LedgerApply.cls:229-233, 252-284` | `retry-zero-record-revision-as-built`, `retry-zero-record-revision-reviewed` |
| 17/client-request | hand-rolled | M02-L1: F-C1703 | `iris_vector_graph/sdk.py:209-228` | `retry-client-resend-as-built`, `retry-client-resend-reviewed` |
| 16/cypher-http-call | hand-rolled | M02-L1: F-C1604 | `iris_vector_graph/cypher_api.py:239-268` | `retry-server-rerun-as-built`, `retry-server-rerun-reviewed` |
| 01/setup-routine | canonical | - | `iris_vector_graph/schema.py (initialize_schema)` | `retry-idempotent-setup-as-built`, `retry-idempotent-setup-reviewed` |
| 06/registry-row | canonical | - | `iris_vector_graph/_engine/embeddings.py:157-197` | `retry-idempotent-setup-as-built`, `retry-idempotent-setup-reviewed` |
| 06/queue-entry | canonical | - | `iris_src/src/Graph/KG/EmbedQueue.cls:35-60` | `retry-idempotent-setup-as-built`, `retry-idempotent-setup-reviewed` |

- 11/retry-key: the server binding is atomic with the commit; the client re-applies post-commit properties on a replayed answer
- 13/redaction-target: a revision whose changeset recorded nothing is never touched by redaction, so its key stays bound
- 06/registry-row: setting the same model again changes nothing (VEC-B1.18)
- 06/queue-entry: one entry per node id: a second enqueue overwrites; its lost-update race is M-07's

## M-03 Exclusive section: lock and marker

- Implements: AX-11 Conflicting commands serialize, AX-12 Truthful outcomes and committed observations
- State: lock holder(s) (exclusive or shared); marker: none | (target, owner); per target: live?, history tombstoned?
- Operations: take lock (exclusive / shared); release; check the target is not live; check no marker on the target; set marker; clear marker; guarded effect (commit into, tombstone, erase)
- Effect kinds: acquire, release, mark, unmark, guarded write, refuse (busy, marked, live); events: redaction_in_progress, lock_timeout, target_live
- Model: `models/semantics/src/excl.rs` (26 checks, 26 met, exhaustive)

| Law | Kind | Statement | Negative control(s) | As-built checks attributed to it | Also violated by (complement) |
|---|---|---|---|---|---|
| M03-L1 | invariant | Mutual exclusion: an exclusive holder excludes every other holder. | `excl-control-C1-lock-admits-two` | - | - |
| M03-L2 | action | Every guarded effect is made by a process that holds the lock. | `excl-control-C2-writer-without-lock` | `excl-eraser-no-head-lock-as-built`, `excl-adjacency-writer-lock-as-built`, `excl-bm25-write-lock-as-built`, `excl-plan-build-lock-as-built`, `excl-mode-switch-as-built` | - |
| M03-L3 | invariant | A marker is valid: while target t is marked, t is not live. | `excl-control-C3-check-before-lock` | `excl-redaction-marker-as-built-F1302-marker` | `excl-redaction-marker-as-built`, `excl-redaction-marker-as-built-F1302-tomb-live`, `excl-control-C2-writer-without-lock`, `excl-control-C5-tomb-without-check` |
| M03-L4 | action | Only the marker's owner clears it. | `excl-control-C4-clear-any` | `excl-redaction-marker-as-built` | `excl-redaction-marker-as-built-F1302-marker`, `excl-redaction-marker-as-built-F1302-tomb-live` |
| M03-L5 | action | No history of live content is tombstoned. | `excl-control-C5-tomb-without-check` | `excl-redaction-marker-as-built-F1302-tomb-live` | `excl-redaction-marker-as-built`, `excl-redaction-marker-as-built-F1302-marker`, `excl-control-C2-writer-without-lock`, `excl-control-C3-check-before-lock` |

| Object | Use | Departures (law: findings or exception; why) | Where (pin) | Model checks |
|---|---|---|---|---|
| 11/ledger | canonical | - | `iris_src/src/Graph/KG/Ledger.cls:440-444, 404` | `excl-head-lock-commit-as-built`, `excl-head-lock-commit-reviewed` |
| 13/redaction-target | hand-rolled | M03-L3: F-1302<br>M03-L4: F-1303<br>M03-L5: F-1302, F-C1350 | `iris_src/src/Graph/KG/LedgerRedact.cls:185-211, 302-330, 384-430` | `excl-redaction-marker-as-built`, `excl-redaction-marker-reviewed`, `excl-redaction-marker-as-built-F1302-marker`, `excl-redaction-marker-as-built-F1302-tomb-live`, `excl-control-C1-lock-admits-two`, `excl-control-C2-writer-without-lock`, `excl-control-C3-check-before-lock`, `excl-control-C4-clear-any`, `excl-control-C5-tomb-without-check`, `excl-sharp-redaction-finishes`, `excl-sharp-commit-refused-by-marker`, `excl-sharp-run-refused-live` |
| 12/graph-content | hand-rolled | M03-L2: F-1201, F-1114, F-C1201 | `iris_src/src/Graph/KG/Eraser.cls:665-678, 809-811` | `excl-eraser-no-head-lock-as-built`, `excl-eraser-no-head-lock-reviewed` |
| 04/graph-writer-lock | hand-rolled | M03-L2: F-0407 | `iris_src/src/Graph/KG/Adjacency.cls:61-75` | `excl-adjacency-writer-lock-as-built`, `excl-adjacency-writer-lock-reviewed` |
| 04/no-lock-mark | canonical | - | `iris_src/src/Graph/KG/Adjacency.cls:55-75` | `excl-adjacency-no-lock-mark-as-built`, `excl-adjacency-no-lock-mark-reviewed` |
| 07/bm25-index | hand-rolled | M03-L2: F-0701 | `iris_src/src/Graph/KG/BM25Index.cls:97-175, 403-410, 587-591` | `excl-bm25-write-lock-as-built`, `excl-bm25-write-lock-reviewed` |
| 09/compiled-shape | hand-rolled | M03-L2: F-0905 | `iris_src/src/Graph/KG/Cypher/Gen.cls:166, 225-230` | `excl-plan-build-lock-as-built`, `excl-plan-build-lock-reviewed` |
| 02/graph-mode | hand-rolled | M03-L2: F-0207 | `iris_src/src/Graph/KG/GraphMode.cls:26-61` | `excl-mode-switch-as-built`, `excl-mode-switch-reviewed` |
| 13/redaction-run | hand-rolled | M03-L3: F-1302 (the run checks liveness before its lock and sets the marker in its first batch)<br>M03-L4: F-1303 (the run's Final clears the one global marker whoever set it)<br>M03-L5: F-1302, F-C1350 (a batch tombstones history of content made live after the run's check) | `iris_src/src/Graph/KG/LedgerRedact.cls:275-300` | `excl-redaction-marker-as-built`, `excl-redaction-marker-reviewed`, `excl-redaction-marker-as-built-F1302-marker`, `excl-redaction-marker-as-built-F1302-tomb-live`, `excl-control-C1-lock-admits-two`, `excl-control-C2-writer-without-lock`, `excl-control-C3-check-before-lock`, `excl-control-C4-clear-any`, `excl-control-C5-tomb-without-check`, `excl-sharp-redaction-finishes`, `excl-sharp-commit-refused-by-marker`, `excl-sharp-run-refused-live` |
| 10/interned-snapshot | canonical | - | `iris_src/src/Graph/KG/NKGAccelLoader.cls` | `excl-head-lock-commit-as-built`, `excl-head-lock-commit-reviewed` |
| 15/fhir-graph | canonical | - | `iris_src/src/Graph/KG/FHIRGraph.cls:543-626` | not modelled: not modelled here: the sync lock against erasure is breadth-c machine M3 (HD-1502..1504) |
| 15/fhir-sync-task | canonical | - | `iris_src/src/Graph/KG/FHIRGraph.cls:543-626` | not modelled: not modelled here: the sync lock (busy refused), breadth-c machine M3 |

- 13/redaction-target: the liveness check is unlocked and the marker is set in the first batch; Final clears the one global marker whoever set it
- 12/graph-content: erasure changes the statement maps and rows a commit also writes, without the head lock
- 04/graph-writer-lock: writers share the lock and proceed without it after 5 s, setting the no-lock mark (a signalled degraded mode); Reweight takes none
- 04/no-lock-mark: the mark is the signal of an unlocked write
- 13/redaction-run: the redaction run is the actor of the redaction target's marker handling; same model as 13/redaction-target
- 10/interned-snapshot: rebuilt under lock ^IVG.NKGBuild; staleness is M-04's

## M-04 Derived store with staleness

- Implements: AX-08 Derived stores match or say they are stale
- State: committed source S (and an open writer's uncommitted value); derived D (the S it was computed from); D's stamp; the live token T (monotone, not undone by rollback)
- Operations: source write in a transaction, maintained per write path: in the same transaction (functional index), by moving the token, or not at all; commit / roll back / stop; reader fill (read token, read source, store D with that stamp); rebuild under lock; clear without restamp; read through a gate
- Effect kinds: update source, update derived, move token, stamp, refuse or fall back when stale; events: stale (stamp != token), rebuilt
- Model: `models/semantics/src/derived.rs` (36 checks, 36 met, exhaustive)

| Law | Kind | Statement | Negative control(s) | As-built checks attributed to it | Also violated by (complement) |
|---|---|---|---|---|---|
| M04-L1 | invariant | Current or stale: when no writer is open, stamp = token implies D = f(S). | `derived-control-C2-token-after-compute`, `derived-control-C5-probe-late` | `derived-degree-cache-as-built-F0402`, `derived-degree-cache-as-built-FC0401`, `derived-degree-cache-as-built-F0406`, `derived-result-cache-04-as-built-F0402`, `derived-interned-snapshot-as-built-FC0801`, `derived-bucket-aggregate-update-as-built-F0501` | `derived-algo-cache-edgeless-as-built-F1004`, `derived-interned-snapshot-as-built-F1005`, `derived-bm25-text-change-as-built-F0703`, `derived-statement-map-direct-delete-as-built-F0303`, `derived-engine-mode-cache-as-built-F0208`, `derived-ttl-cache-as-built-F0302`, `derived-ttl-cache-as-built-EXC05`, `derived-native-gate-label-index-as-built-F0906`, `derived-ivf-erase-as-built-F0606`, `derived-control-C1-unmaintained-path`, `derived-control-C3-rebuild-stamp-only` |
| M04-L2 | action | Every source write path updates D in its transaction or moves the token. | `derived-control-C1-unmaintained-path` | `derived-algo-cache-edgeless-as-built-F1004`, `derived-interned-snapshot-as-built-F1005`, `derived-bm25-text-change-as-built-F0703`, `derived-statement-map-direct-delete-as-built-F0303`, `derived-engine-mode-cache-as-built-F0208`, `derived-ttl-cache-as-built-F0302`, `derived-ttl-cache-as-built-EXC05`, `derived-ivf-erase-as-built-F0606` | `derived-native-gate-label-index-as-built-F0906` |
| M04-L3 | invariant | A rebuild leaves D = f(S) with the current stamp, or leaves it stale. | `derived-control-C3-rebuild-stamp-only` | - | - |
| M04-L4 | action | A read from D answers f(S) or checks the signal and falls back. | `derived-control-C4-unchecked-gate` | `derived-native-gate-label-index-as-built-F0906` | `derived-degree-cache-as-built-F0402`, `derived-degree-cache-as-built-FC0401`, `derived-degree-cache-as-built-F0406`, `derived-result-cache-04-as-built-F0402`, `derived-algo-cache-edgeless-as-built-F1004`, `derived-interned-snapshot-as-built-F1005`, `derived-interned-snapshot-as-built-FC0801`, `derived-bm25-text-change-as-built-F0703`, `derived-statement-map-direct-delete-as-built-F0303`, `derived-bucket-aggregate-update-as-built-F0501`, `derived-engine-mode-cache-as-built-F0208`, `derived-ttl-cache-as-built-F0302`, `derived-ttl-cache-as-built-EXC05`, `derived-ivf-erase-as-built-F0606`, `derived-control-C1-unmaintained-path`, `derived-control-C2-token-after-compute`, `derived-control-C3-rebuild-stamp-only`, `derived-control-C5-probe-late` |

| Object | Use | Departures (law: findings or exception; why) | Where (pin) | Model checks |
|---|---|---|---|---|
| 04/adjacency-entry | canonical | - | `iris_src/src/Graph/KG/AdjIndex.cls:12-23 (functional index, X-FX)` | `derived-adjacency-functional-as-built`, `derived-adjacency-functional-reviewed` |
| 04/degree-cache-entry | hand-rolled | M04-L1: F-0402, F-0406, F-C0401<br>M04-L4: F-0402, F-C0401, F-0406 (consequence in this model: a read through the gate returns the stale value as current) | `iris_src/src/Graph/KG/Adjacency.cls:80-160` | `derived-degree-cache-as-built-F0402`, `derived-degree-cache-as-built-FC0401`, `derived-degree-cache-as-built-F0406`, `derived-degree-cache-reviewed`, `derived-control-C1-unmaintained-path`, `derived-control-C2-token-after-compute`, `derived-control-C3-rebuild-stamp-only`, `derived-control-C4-unchecked-gate`, `derived-control-C5-probe-late`, `derived-sharp-stale`, `derived-sharp-fill-current`, `derived-sharp-rebuilt` |
| 04/result-cache-entry | hand-rolled | M04-L1: F-0402<br>M04-L4: F-0402 (consequence in this model: a read through the gate returns the stale value as current) | `iris_src/src/Graph/KG/AlgoCache.cls:1-50` | `derived-result-cache-04-as-built-F0402`, `derived-result-cache-04-reviewed` |
| 10/result-cache-entry | hand-rolled | M04-L2: F-1004<br>M04-L1: F-1004 (consequence in this model of the same unmaintained write: the derived entry keeps a current stamp while it no longer equals its source)<br>M04-L4: F-1004 (consequence in this model: a read through the gate returns the stale value as current) | `iris_vector_graph/stores/iris_sql_store.py:921-983, 2231-2275` | `derived-algo-cache-edgeless-as-built-F1004`, `derived-algo-cache-edgeless-reviewed` |
| 10/interned-snapshot | hand-rolled | M04-L2: F-1005<br>M04-L1: F-1005, F-C0801<br>M04-L4: F-1005, F-C0801 (consequence in this model: a read through the gate returns the stale value as current) | `iris_src/src/Graph/KG/TemporalIndex.cls:104-112; iris_src/src/Graph/KG/Adjacency.cls:111-140` | `derived-interned-snapshot-as-built-F1005`, `derived-interned-snapshot-as-built-FC0801`, `derived-interned-snapshot-reviewed` |
| 07/bm25-index | hand-rolled | M04-L2: F-0703<br>M04-L1: F-0703 (consequence in this model of the same unmaintained write: the derived entry keeps a current stamp while it no longer equals its source)<br>M04-L4: F-0703 (consequence in this model: a read through the gate returns the stale value as current) | `docs/USER_GUIDE.md:893-894; iris_src/src/Graph/KG/BM25Index.cls` | `derived-bm25-text-change-as-built-F0703`, `derived-bm25-text-change-reviewed` |
| 11/edge-statement | hand-rolled | M04-L2: F-0303<br>M04-L1: F-0303 (consequence in this model of the same unmaintained write: the derived entry keeps a current stamp while it no longer equals its source)<br>M04-L4: F-0303 (consequence in this model: a read through the gate returns the stale value as current) | `iris_vector_graph/_engine/nodes_edges.py (direct delete_edge)` | `derived-statement-map-direct-delete-as-built-F0303`, `derived-statement-map-direct-delete-reviewed` |
| 05/latest-event-index | canonical | - | `iris_src/src/Graph/KG/TemporalIndex.cls` | `derived-adjacency-functional-as-built`, `derived-adjacency-functional-reviewed` |
| 05/temporal-coordinates | hand-rolled | M04-L1: F-0501<br>M04-L4: F-0501 (consequence in this model: a read through the gate returns the stale value as current) | `iris_src/src/Graph/KG/TemporalIndex.cls (bucket aggregate)` | `derived-bucket-aggregate-update-as-built-F0501`, `derived-bucket-aggregate-update-reviewed` |
| 02/graph-mode | hand-rolled | M04-L2: F-0208<br>M04-L1: F-0208 (consequence in this model of the same unmaintained write: the derived entry keeps a current stamp while it no longer equals its source)<br>M04-L4: F-0208 (consequence in this model: a read through the gate returns the stale value as current) | `iris_vector_graph/_engine (engine mode cache)` | `derived-engine-mode-cache-as-built-F0208`, `derived-engine-mode-cache-reviewed` |
| 03/ledger-state | hand-rolled | M04-L2: F-0302<br>M04-L1: F-0302 (consequence in this model of the same unmaintained write: the derived entry keeps a current stamp while it no longer equals its source)<br>M04-L4: F-0302 (consequence in this model: a read through the gate returns the stale value as current) | `iris_vector_graph/ledger/guard.py:20-59` | `derived-ttl-cache-as-built-F0302`, `derived-ttl-cache-as-built-EXC05`, `derived-ttl-cache-reviewed` |
| 06/route | hand-rolled | M04-L2: EXC-05<br>M04-L1: EXC-05 (within the documented 30 s route memory)<br>M04-L4: EXC-05 (within the documented 30 s route memory) | `iris_vector_graph/_engine/vector.py (route memory)` | `derived-ttl-cache-as-built-F0302`, `derived-ttl-cache-as-built-EXC05`, `derived-ttl-cache-reviewed` |
| 09/engine-native-path | hand-rolled | M04-L4: F-0906 (the native gate reads the label index without checking that it is declared)<br>M04-L2: EXC-11 (an undeclared label index is kept only by the engine's own writers; other writes leave it stale, by design)<br>M04-L1: EXC-11 (an undeclared index's staleness signal is its declaration flag, not a stamp; the abstraction shows it as current and wrong) | `iris_vector_graph/cypher/native_plan.py:528-529; iris_vector_graph/engine.py:703-724` | `derived-native-gate-label-index-as-built-F0906`, `derived-native-gate-label-index-reviewed` |
| 09/compiled-shape | canonical | - | `iris_src/src/Graph/KG/Cypher/Gen.cls:13-16, 225-230` | `derived-adjacency-functional-as-built`, `derived-adjacency-functional-reviewed` |
| 06/ivf-index | hand-rolled | M04-L2: F-0606<br>M04-L1: F-0606 (consequence in this model of the same unmaintained write: the derived entry keeps a current stamp while it no longer equals its source)<br>M04-L4: F-0606 (consequence in this model: a read through the gate returns the stale value as current) | `iris_src/src/Graph/KG/IVFIndex.cls` | `derived-ivf-erase-as-built-F0606`, `derived-ivf-erase-reviewed` |
| 17/index-handle | hand-rolled | M04-L2: F-0703<br>M04-L1: F-0703 (consequence in this model of the same unmaintained write: the derived entry keeps a current stamp while it no longer equals its source)<br>M04-L4: F-0703 (consequence in this model: a read through the gate returns the stale value as current) | `iris_vector_graph (index handle, BM25)` | `derived-bm25-text-change-as-built-F0703`, `derived-bm25-text-change-reviewed` |
| 05/triple-row | canonical | - | `iris_src/src/Graph/KG/TemporalIndex.cls` | `derived-adjacency-functional-as-built`, `derived-adjacency-functional-reviewed` |
| 18/namespace | hand-rolled | M04-L1: F-1805 | `iris_vector_graph/_engine/snapshot.py:1679` | not modelled: shown in the snapshot family: snapshot-merge-aggregates-as-built (law M06-L3: a merge restore overwrites a derived aggregate) |

- 04/degree-cache-entry: the token moves before commit and a rollback does not move it again, so a reader fill of the uncommitted count stays current; clearing the cache keeps the warm stamp
- 10/result-cache-entry: a node written without an edge moves no token
- 07/bm25-index: a node text change neither reindexes nor marks the index stale
- 05/latest-event-index: complete / incomplete is the staleness signal; rebuild makes it complete
- 05/temporal-coordinates: an update-mode write counts its edge again in the bucket aggregate
- 03/ledger-state: a 5 s cache with no staleness signal
- 06/route: the documented 30 s route memory (VEC-T2.13)
- 09/compiled-shape: a deploy discards every compiled plan (stamp); key collisions are M-12's
- 06/ivf-index: erasure leaves the index's entries; modelled as the erasure write path not maintaining it
- 05/triple-row: the marked structural row is derived from the temporal edge; its ownership departures are M-01/AX-01 findings (F-0506, F-0304)

## M-05 Store inventory and removal

- Implements: AX-10 Removal reaches every store and copy, AX-02 Graph and tenant scope, AX-04 All or none across stores
- State: stores s1..sn each holding content per target; the eraser's inventory; redaction's reach over history (records, revision text, retry keys); the receipt's list of what remains
- Operations: write content of a target into the stores its path reaches; erase target; redact target; read receipt
- Effect kinds: remove from inventoried stores, tombstone history, report remaining; events: receipt
- Model: `models/semantics/src/removal.rs` (27 checks, 27 met, exhaustive)

| Law | Kind | Statement | Negative control(s) | As-built checks attributed to it | Also violated by (complement) |
|---|---|---|---|---|---|
| M05-L1 | invariant | After erasure and a successful redaction of t, no store holds t's content unless the receipt names that store. | `removal-control-C1-store-dropped` | `removal-bm25-as-built`, `removal-vector-indexes-as-built`, `removal-quarantine-as-built`, `removal-snapshot-archives-as-built`, `removal-reifier-default-graph-as-built`, `removal-temporal-only-prefix-as-built`, `removal-history-text-as-built`, `removal-default-routed-vectors-as-built` | `removal-bm25-as-built-M05-L3`, `removal-vector-indexes-as-built-M05-L3`, `removal-control-C1b-store-dropped-inventory` |
| M05-L2 | action | Removing t changes no other target's content. | `removal-control-C2-cross-target` | `removal-temporal-purge-all-graphs-as-built` | - |
| M05-L3 | invariant | The inventory lists every store any write path reaches. | `removal-control-C1b-store-dropped-inventory` | `removal-bm25-as-built-M05-L3`, `removal-vector-indexes-as-built-M05-L3` | `removal-bm25-as-built`, `removal-vector-indexes-as-built`, `removal-quarantine-as-built`, `removal-snapshot-archives-as-built`, `removal-reifier-default-graph-as-built`, `removal-temporal-only-prefix-as-built`, `removal-history-text-as-built`, `removal-default-routed-vectors-as-built`, `removal-control-C1-store-dropped` |

| Object | Use | Departures (law: findings or exception; why) | Where (pin) | Model checks |
|---|---|---|---|---|
| 12/graph-content | canonical | - | `iris_src/src/Graph/KG/Eraser.cls:47-260; iris_src/src/Graph/KG/GraphStores.cls:26-133` | `removal-rows-adjacency-temporal-as-built`, `removal-rows-adjacency-temporal-reviewed`, `removal-control-C1-store-dropped`, `removal-control-C1b-store-dropped-inventory`, `removal-control-C2-cross-target`, `removal-sharp-removed-other-kept`, `removal-sharp-erased-history-kept` |
| 07/bm25-index | hand-rolled | M05-L1: F-0702<br>M05-L3: F-0702 | `iris_src/src/Graph/KG/Eraser.cls:138-147` | `removal-bm25-as-built`, `removal-bm25-as-built-M05-L3`, `removal-bm25-reviewed` |
| 06/ivf-index | hand-rolled | M05-L1: F-0606<br>M05-L3: F-0606 | `iris_src/src/Graph/KG/GraphStores.cls:26-133` | `removal-vector-indexes-as-built`, `removal-vector-indexes-as-built-M05-L3`, `removal-vector-indexes-reviewed` |
| 06/quarantined-row | hand-rolled | M05-L1: F-C1305<br>M05-L3: F-C1305 (the same defect seen as inventory incompleteness: a write path reaches a store that neither erasure, redaction nor the receipt reaches) | `iris_src/src/Graph/KG/Eraser.cls:300-302, 752-758` | `removal-quarantine-as-built`, `removal-quarantine-reviewed` |
| 18/snapshot-archive | hand-rolled | M05-L1: F-C1304<br>M05-L3: F-C1304 (the same defect seen as inventory incompleteness: a write path reaches a store that neither erasure, redaction nor the receipt reaches) | `iris_vector_graph/_engine/snapshot.py:387-422` | `removal-snapshot-archives-as-built`, `removal-snapshot-archives-reviewed` |
| 15/reifier | hand-rolled | M05-L1: F-1502<br>M05-L3: F-1502 (the same defect seen as inventory incompleteness: a write path reaches a store that neither erasure, redaction nor the receipt reaches) | `iris_vector_graph/_engine/schema.py:3296-3322; iris_src/src/Graph/KG/Eraser.cls:185-189` | `removal-reifier-default-graph-as-built`, `removal-reifier-default-graph-reviewed` |
| 05/edge-type-in-a-graph | hand-rolled | M05-L1: F-C1203, F-C1308<br>M05-L3: F-C1203, F-C1308 (the same defect seen as inventory incompleteness: a write path reaches a store that neither erasure, redaction nor the receipt reaches) | `iris_src/src/Graph/KG/Eraser.cls:322-348, 590-610; iris_src/src/Graph/KG/LedgerRedact.cls:149-178` | `removal-temporal-only-prefix-as-built`, `removal-temporal-only-prefix-reviewed` |
| 13/redaction-target | hand-rolled | M05-L1: F-C1306, F-CS01, F-C1309<br>M05-L3: F-C1306, F-CS01, F-C1309 (the same defect seen as inventory incompleteness: a write path reaches a store that neither erasure, redaction nor the receipt reaches) | `iris_vector_graph/_engine/legacy.py:606-646; iris_src/src/Graph/KG/LedgerApply.cls:229-233` | `removal-history-text-as-built`, `removal-history-text-reviewed` |
| 06/route | hand-rolled | M05-L1: F-0618<br>M05-L3: F-0618 (the same defect seen as inventory incompleteness: a write path reaches a store that neither erasure, redaction nor the receipt reaches) | `iris_src/src/Graph/KG/LedgerApply.cls:353-370` | `removal-default-routed-vectors-as-built`, `removal-default-routed-vectors-reviewed` |
| 05/temporal-coordinates | hand-rolled | M05-L2: F-0507 | `iris_src/src/Graph/KG/TemporalIndex.cls (Purge)` | `removal-temporal-purge-all-graphs-as-built`, `removal-temporal-purge-all-graphs-reviewed` |
| 15/fhir-graph | canonical | - | `iris_src/src/Graph/KG/FHIRGraph.cls` | not modelled: not modelled here: erase against sync is breadth-c M3 |
| 12/whole-namespace | canonical | - | `iris_src/src/Graph/KG/Eraser.cls:699-845` | `removal-rows-adjacency-temporal-as-built`, `removal-rows-adjacency-temporal-reviewed`, `removal-control-C1-store-dropped`, `removal-control-C1b-store-dropped-inventory`, `removal-control-C2-cross-target`, `removal-sharp-removed-other-kept`, `removal-sharp-erased-history-kept` |
| 12/node-in-a-sweep | canonical | - | `iris_src/src/Graph/KG/Eraser.cls:1182-1248` | `removal-rows-adjacency-temporal-as-built`, `removal-rows-adjacency-temporal-reviewed`, `removal-control-C1-store-dropped`, `removal-control-C1b-store-dropped-inventory`, `removal-control-C2-cross-target`, `removal-sharp-removed-other-kept`, `removal-sharp-erased-history-kept` |

- 06/route: the ledger's node delete does not reach a default-graph node's routed vectors
- 12/whole-namespace: EraseAll empties every store on the list (ERS-B93; F-C1240 refuted: GraphStores lists ^ArnoKG)
- 12/node-in-a-sweep: the sweep removes nodes that hold nothing (ERS-B94)

## M-06 Snapshot save and restore

- Implements: AX-12 Truthful outcomes and committed observations, AX-05 History only grows, AX-10 Removal reaches every store and copy
- State: live stores (rows, routed node vectors, routed edge vectors, ledger head and records, temporal aggregates); at most one archive (the stores it carries)
- Operations: save; write and commit after the save; replacing restore; merge restore
- Effect kinds: copy, replace, merge, report counts; events: restore report
- Model: `models/semantics/src/snapshot.rs` (11 checks, 11 met, exhaustive)

| Law | Kind | Statement | Negative control(s) | As-built checks attributed to it | Also violated by (complement) |
|---|---|---|---|---|---|
| M06-L1 | invariant | Round trip: a replacing restore of an archive saved at state s, with nothing written since, gives s on every store. | `snapshot-control-C1-store-left-out` | `snapshot-edge-vectors-missing-as-built` | - |
| M06-L2 | action | A restore never lowers the ledger head below a live commit (it refuses or replays). | `snapshot-control-C2-head-laid-over` | `snapshot-replacing-restore-as-built` | - |
| M06-L3 | action | A merge restore combines aggregates and counts only what it restored. | `snapshot-control-C3-aggregates-overwritten` | `snapshot-merge-aggregates-as-built` | - |

| Object | Use | Departures (law: findings or exception; why) | Where (pin) | Model checks |
|---|---|---|---|---|
| 18/snapshot-archive | hand-rolled | M06-L1: F-C1804, F-1803, F-1804 | `iris_vector_graph/_engine/snapshot.py:299-344, 960-1025` | `snapshot-edge-vectors-missing-as-built`, `snapshot-edge-vectors-missing-reviewed`, `snapshot-control-C1-store-left-out`, `snapshot-control-C2-head-laid-over`, `snapshot-control-C3-aggregates-overwritten`, `snapshot-sharp-restore-refused`, `snapshot-sharp-round-trip` |
| 18/namespace | hand-rolled | M06-L2: F-1801, F-C1850<br>M06-L3: F-1805, F-1802 | `iris_vector_graph/_engine/snapshot.py:1554-1588, 1654-1692, 1679` | `snapshot-replacing-restore-as-built`, `snapshot-replacing-restore-reviewed`, `snapshot-merge-aggregates-as-built`, `snapshot-merge-aggregates-reviewed` |

## M-07 Background job and queue

- Implements: AX-14 Accepted work progresses, AX-12 Truthful outcomes and committed observations, AX-11 Conflicting commands serialize
- State: entries (absent | pending | in flight | done | failed) with a text version; a worker's claim; a service order; a resumable run's cursor
- Operations: enqueue (or re-enqueue); claim / serve next; work; mark done or failed; resume a bounded run
- Effect kinds: serve, store result, mark, advance cursor; events: DONE, ERROR
- Model: `models/semantics/src/queue.rs` (19 checks, 19 met, exhaustive)

| Law | Kind | Statement | Negative control(s) | As-built checks attributed to it | Also violated by (complement) |
|---|---|---|---|---|---|
| M07-L1 | invariant | Done means done: an entry is done only when its result was made from its current text. | `queue-control-C3-mark-always` | `queue-embed-queue-as-built-F0604`, `queue-embed-queue-as-built-FC0601` | `queue-embed-queue-as-built-HD0604`, `queue-control-C2-two-consumers` |
| M07-L2 | invariant | One worker per entry at a time. | `queue-control-C2-two-consumers` | `queue-embed-queue-as-built-HD0604` | - |
| M07-L3 | invariant | Bounded overtaking: while an entry is pending, at most N-1 other entries are served before it (N = distinct entries). | `queue-control-C1-lifo-overtaking` | `queue-embed-queue-as-built-FC0605-overtaking` | - |
| M07-L4 | progress | Under weak fairness of the worker, every pending entry is served (no fair cycle keeps it pending); a resumed run can always finish. | `queue-control-C1b-lifo-fair-lasso`, `queue-control-C4-restart-scan` | `queue-embed-queue-as-built-FC0605-fair-lasso`, `queue-bounded-redaction-resume-as-built` | - |

| Object | Use | Departures (law: findings or exception; why) | Where (pin) | Model checks |
|---|---|---|---|---|
| 06/queue-entry | hand-rolled | M07-L1: F-0604, F-C0601<br>M07-L2: F-C0670<br>M07-L3: F-C0605<br>M07-L4: F-C0605 | `iris_src/src/Graph/KG/EmbedQueue.cls:35-60, 106-134, 258-338` | `queue-embed-queue-as-built-F0604`, `queue-embed-queue-as-built-FC0601`, `queue-embed-queue-as-built-HD0604`, `queue-embed-queue-reviewed-entry`, `queue-control-C2-two-consumers`, `queue-control-C3-mark-always`, `queue-embed-queue-as-built-FC0605-overtaking`, `queue-embed-queue-as-built-FC0605-fair-lasso`, `queue-embed-queue-as-built-FC0605-agef-blind`, `queue-embed-queue-reviewed-overtaking`, `queue-embed-queue-reviewed-fair-lasso`, `queue-control-C1-lifo-overtaking`, `queue-control-C1b-lifo-fair-lasso`, `queue-sharp-fifo-serves-high`, `queue-sharp-fifo-overtake-2` |
| 13/redaction-run | hand-rolled | M07-L4: F-C1303 | `iris_src/src/Graph/KG/LedgerRedact.cls:185-240` | `queue-bounded-redaction-resume-as-built`, `queue-bounded-redaction-resume-reviewed`, `queue-control-C4-restart-scan`, `queue-sharp-resume-finishes` |
| 09/compiled-shape | canonical | - | `iris_src/src/Graph/KG/Cypher/Gen.cls:61-105` | not modelled: not modelled here: the build job is breadth-b machine planc |
| 15/fhir-graph | canonical | - | `iris_src/src/Graph/KG/FHIRGraph.cls:543-626` | not modelled: not modelled here: the sync job is breadth-c machine M3 |
| 15/fhir-sync-task | canonical | - | `iris_src/src/Graph/KG/FHIRGraphSyncTask.cls` | not modelled: not modelled here: the task runs SyncOnce, breadth-c machine M3 |

- 06/queue-entry: as built: DONE without a vector (F-0604), DONE with an old text (F-C0601), node-id service order (F-C0605); two workers (the IRIS task and process_embed_queue) can work one entry at once: the single-consumer premise (HD-0604) is neither enforced nor documented (new finding F-C0670)

## M-08 Install, settings and version gate

- Implements: AX-09 One install, one schema, one version per namespace, AX-03 Explicit, inert refusals
- State: the namespace's recorded schema; the deployed class set and its version; the objects setup touched; settings (process mode, graph mode, optional dependencies)
- Operations: setup(schema); setup again; first use by an engine (schema, version); set a setting
- Effect kinds: record schema, create objects, refuse, report failures; events: setup reply with warnings, schema refusal
- Model: `models/semantics/src/install.rs` (15 checks, 15 met, exhaustive)

| Law | Kind | Statement | Negative control(s) | As-built checks attributed to it | Also violated by (complement) |
|---|---|---|---|---|---|
| M08-L1 | invariant | One schema: once recorded, the namespace's schema never changes and an engine asking for another is refused. | `install-control-C1-first-use-accepts-any` | `install-first-use-no-record-as-built` | - |
| M08-L2 | action | Idempotent: setup on a current install changes nothing. | `install-control-C4-enable-race-errors` | `install-concurrent-first-enable-as-built` | - |
| M08-L3 | action | Setup touches only the namespace's schema (and the fixed legacy manifest). | `install-control-C2-unqualified-drop` | `install-unqualified-drop-as-built` | - |
| M08-L4 | action | A setting outside its domain is refused, never read as another value. | `install-control-C3-setting-unchecked` | `install-unchecked-setting-as-built` | - |

| Object | Use | Departures (law: findings or exception; why) | Where (pin) | Model checks |
|---|---|---|---|---|
| 01/namespace | hand-rolled | M08-L1: F-0103 | `iris_vector_graph/schema_name.py:220-235` | `install-first-use-no-record-as-built`, `install-first-use-no-record-reviewed` |
| 01/setup-routine | hand-rolled | M08-L3: F-0107 | `iris_vector_graph/schema.py:655-658` | `install-unqualified-drop-as-built`, `install-unqualified-drop-reviewed` |
| 01/class-set | canonical | - | `iris_vector_graph/schema.py (deploy)` | `install-canonical-as-built`, `install-control-C1-first-use-accepts-any`, `install-control-C2-unqualified-drop`, `install-control-C3-setting-unchecked`, `install-control-C4-enable-race-errors`, `install-sharp-other-schema-refused`, `install-sharp-both-enables-ok` |
| 01/legacy-object | canonical | exception EXC-09 | `iris_vector_graph/_engine/legacy.py` | `install-canonical-as-built`, `install-control-C1-first-use-accepts-any`, `install-control-C2-unqualified-drop`, `install-control-C3-setting-unchecked`, `install-control-C4-enable-race-errors`, `install-sharp-other-schema-refused`, `install-sharp-both-enables-ok` |
| 09/process-mode | hand-rolled | M08-L4: F-0903 | `iris_src/src/Graph/KG/Cypher/Gen.cls:41-44, 61-105` | `install-unchecked-setting-as-built`, `install-unchecked-setting-reviewed` |
| 15/rdf-extra | hand-rolled | M08-L4: F-1506 | `iris_vector_graph/_engine/_rdf_utils.py:125-133` | `install-unchecked-setting-as-built`, `install-unchecked-setting-reviewed` |
| 16/rest-web-app-path | canonical | - | `iris_vector_graph (web app setup)` | `install-canonical-as-built`, `install-control-C1-first-use-accepts-any`, `install-control-C2-unqualified-drop`, `install-control-C3-setting-unchecked`, `install-control-C4-enable-race-errors`, `install-sharp-other-schema-refused`, `install-sharp-both-enables-ok` |
| 16/mcp-tool-set | canonical | - | `iris_src/src/Graph/KG/MCPToolSet.cls` | `install-canonical-as-built`, `install-control-C1-first-use-accepts-any`, `install-control-C2-unqualified-drop`, `install-control-C3-setting-unchecked`, `install-control-C4-enable-race-errors`, `install-sharp-other-schema-refused`, `install-sharp-both-enables-ok` |
| 17/namespace | canonical | - | `iris_vector_graph/_engine/admin.py` | `install-canonical-as-built`, `install-control-C1-first-use-accepts-any`, `install-control-C2-unqualified-drop`, `install-control-C3-setting-unchecked`, `install-control-C4-enable-race-errors`, `install-sharp-other-schema-refused`, `install-sharp-both-enables-ok` |
| 03/ledger-state | canonical | - | `iris_src/src/Graph/KG/Ledger.cls:252-380` | `install-canonical-as-built`, `install-control-C1-first-use-accepts-any`, `install-control-C2-unqualified-drop`, `install-control-C3-setting-unchecked`, `install-control-C4-enable-race-errors`, `install-sharp-other-schema-refused`, `install-sharp-both-enables-ok` |
| 11/ledger | hand-rolled | M08-L2: F-1104 | `iris_src/src/Graph/KG/Ledger.cls:252-329` | `install-concurrent-first-enable-as-built`, `install-concurrent-first-enable-reviewed` |
| 15/prefix-registry | canonical | - | `iris_vector_graph (RDF prefix registry)` | `install-canonical-as-built`, `install-control-C1-first-use-accepts-any`, `install-control-C2-unqualified-drop`, `install-control-C3-setting-unchecked`, `install-control-C4-enable-race-errors`, `install-sharp-other-schema-refused`, `install-sharp-both-enables-ok` |
| 15/ivg-fhir-cli | canonical | - | `iris_vector_graph (ivg fhir commands)` | `install-canonical-as-built`, `install-control-C1-first-use-accepts-any`, `install-control-C2-unqualified-drop`, `install-control-C3-setting-unchecked`, `install-control-C4-enable-race-errors`, `install-sharp-other-schema-refused`, `install-sharp-both-enables-ok` |

- 01/legacy-object: listed from a fixed manifest; its removal report is F-0101 (AX-12)
- 15/rdf-extra: rdflib 8 is reported as rdflib absent
- 16/mcp-tool-set: Community has no %AI: the tool set is absent, by edition
- 03/ledger-state: enable / disable / set-strict are settings with refusals
- 11/ledger: two first enables at once: the second fails instead of returning the genesis
- 15/prefix-registry: a saved prefix is a setting (INT-R1.14)
- 15/ivg-fhir-cli: the CLI front of the FHIR graph setting; Schedule/Unschedule's untransacted steps are F-C1501 on 15/fhir-graph

## M-09 Graph key and tenant scope

- Implements: AX-02 Graph and tenant scope
- State: two graphs with overlapping node ids; content per graph; the key derivations; the target predicates (erase, liveness, record match)
- Operations: make a key from a name; scoped read; all-graphs read; scoped write; evaluate the three target predicates
- Effect kinds: read in scope, write in scope, refuse a bad name; events: invalid graph name
- Model: `models/semantics/src/scope.rs` (19 checks, 19 met, exhaustive)

| Law | Kind | Statement | Negative control(s) | As-built checks attributed to it | Also violated by (complement) |
|---|---|---|---|---|---|
| M09-L1 | invariant | Every entry validates the name; distinct valid names give distinct keys. | `scope-control-C1-key-ignores-name` | `scope-name-check-missing-as-built` | - |
| M09-L2 | invariant | A scoped read answers from its graph alone; an all-graphs read is the union of each graph's answer. | `scope-control-C2-join-across-graphs` | `scope-all-graphs-walk-as-built`, `scope-unscoped-read-as-built`, `scope-interned-no-graph-dimension-as-built` | - |
| M09-L3 | action | A scoped write changes only its graph. | `scope-control-C3-delete-every-graph` | `scope-delete-every-graph-as-built` | - |
| M09-L4 | invariant | The erase, liveness and record-match predicates of a target select the same content. | `scope-control-C4-graph-blind-match` | `scope-three-predicates-as-built` | - |

| Object | Use | Departures (law: findings or exception; why) | Where (pin) | Model checks |
|---|---|---|---|---|
| 02/graph-name | hand-rolled | M09-L1: F-0202, F-0203 | `iris_vector_graph/_engine/nodes_edges.py:968-1015` | `scope-name-check-missing-as-built`, `scope-name-check-missing-reviewed` |
| 08/graph-scope | hand-rolled | M09-L2: F-0818, F-0819, F-0820 | `iris_vector_graph/cypher/translator.py:15404-15431` | `scope-all-graphs-walk-as-built`, `scope-all-graphs-walk-reviewed` |
| 10/default-graph-algorithm-call | hand-rolled | M09-L2: F-1002, F-1006, F-1008, F-1013, F-1001; EXC-06 | `iris_vector_graph/_engine/algorithms.py:658-678` | `scope-unscoped-read-as-built`, `scope-unscoped-read-reviewed` |
| 16/graph-a-caller-names | hand-rolled | M09-L2: F-1603, F-1604 | `api (GraphQL resolvers)` | `scope-unscoped-read-as-built`, `scope-unscoped-read-reviewed` |
| 17/link | hand-rolled | M09-L2: F-1701 | `iris_vector_graph/stores/iris_sql_store.py:1116-1210` | `scope-unscoped-read-as-built`, `scope-unscoped-read-reviewed` |
| 15/reifier | hand-rolled | M09-L3: F-1503 | `iris_vector_graph/_engine/schema.py:3361-3397` | `scope-delete-every-graph-as-built`, `scope-delete-every-graph-reviewed` |
| 13/redaction-target | hand-rolled | M09-L4: F-1304, F-1305 | `iris_src/src/Graph/KG/LedgerRedact.cls:89-178` | `scope-three-predicates-as-built`, `scope-three-predicates-reviewed` |
| 11/node-id | hand-rolled | M09-L4: F-1105, F-1401 | `iris_src/src/Graph/KG/LedgerApply.cls:79-84` | `scope-three-predicates-as-built`, `scope-three-predicates-reviewed` |
| 03/node-in-one-graph | canonical | - | `iris_vector_graph/schema.py:395-402` | `scope-canonical-as-built`, `scope-control-C1-key-ignores-name`, `scope-control-C2-join-across-graphs`, `scope-control-C3-delete-every-graph`, `scope-control-C4-graph-blind-match`, `scope-sharp-same-id-two-graphs-differ`, `scope-sharp-named-write` |
| 03/edge-in-one-graph | canonical | - | `iris_vector_graph/schema.py:34-45` | `scope-canonical-as-built`, `scope-control-C1-key-ignores-name`, `scope-control-C2-join-across-graphs`, `scope-control-C3-delete-every-graph`, `scope-control-C4-graph-blind-match`, `scope-sharp-same-id-two-graphs-differ`, `scope-sharp-named-write` |
| 05/temporal-coordinates | canonical | - | `docs/adr/0001-graph-key-as-first-subscript.md` | `scope-canonical-as-built`, `scope-control-C1-key-ignores-name`, `scope-control-C2-join-across-graphs`, `scope-control-C3-delete-every-graph`, `scope-control-C4-graph-blind-match`, `scope-sharp-same-id-two-graphs-differ`, `scope-sharp-named-write` |
| 08/cypher-node | canonical | - | `iris_vector_graph/cypher/translator.py` | `scope-canonical-as-built`, `scope-control-C1-key-ignores-name`, `scope-control-C2-join-across-graphs`, `scope-control-C3-delete-every-graph`, `scope-control-C4-graph-blind-match`, `scope-sharp-same-id-two-graphs-differ`, `scope-sharp-named-write` |
| 08/cypher-edge | canonical | - | `iris_vector_graph/cypher/translator.py` | `scope-canonical-as-built`, `scope-control-C1-key-ignores-name`, `scope-control-C2-join-across-graphs`, `scope-control-C3-delete-every-graph`, `scope-control-C4-graph-blind-match`, `scope-sharp-same-id-two-graphs-differ`, `scope-sharp-named-write` |
| 07/fused-search | hand-rolled | M09-L2: F-0609, F-0711 | `iris_vector_graph/_engine/vector.py:194-225` | `scope-unscoped-read-as-built`, `scope-unscoped-read-reviewed` |
| 06/route | hand-rolled | M09-L2: F-0605, F-0616 | `iris_vector_graph/_engine/embeddings.py:1803-1850` | `scope-unscoped-read-as-built`, `scope-unscoped-read-reviewed` |
| 12/graph-content | canonical | - | `iris_src/src/Graph/KG/Eraser.cls:113-125` | `scope-canonical-as-built`, `scope-control-C1-key-ignores-name`, `scope-control-C2-join-across-graphs`, `scope-control-C3-delete-every-graph`, `scope-control-C4-graph-blind-match`, `scope-sharp-same-id-two-graphs-differ`, `scope-sharp-named-write` |
| 10/interned-snapshot | hand-rolled | M09-L2: EXC-06 | `CONTEXT.md:97-102` | `scope-interned-no-graph-dimension-as-built`, `scope-interned-no-graph-dimension-reviewed` |
| 10/native-route | hand-rolled | M09-L2: F-1001 | `iris_vector_graph/_engine/algorithms.py` | `scope-unscoped-read-as-built`, `scope-unscoped-read-reviewed` |
| 07/docs-table-search | canonical | - | `iris_vector_graph/_engine/vector.py:917-1054` | `scope-canonical-as-built`, `scope-control-C1-key-ignores-name`, `scope-control-C2-join-across-graphs`, `scope-control-C3-delete-every-graph`, `scope-control-C4-graph-blind-match`, `scope-sharp-same-id-two-graphs-differ`, `scope-sharp-named-write` |
| 07/older-text-search | hand-rolled | M09-L2: F-0711 | `iris_vector_graph/text_search.py:17-256` | `scope-unscoped-read-as-built`, `scope-unscoped-read-reviewed` |
| 15/fhir-bridge | hand-rolled | M09-L2: F-1507 | `iris_vector_graph/_engine/fhir.py:444-481` | `scope-unscoped-read-as-built`, `scope-unscoped-read-reviewed` |
| 16/generated-graphql-call | hand-rolled | M09-L2: F-1603 | `iris_vector_graph/gql (generated server)` | `scope-unscoped-read-as-built`, `scope-unscoped-read-reviewed` |

- 11/node-id: ledger node records are graph-blind
- 10/interned-snapshot: documented: no graph dimension
- 10/native-route: F-1001 is blocked-access (x86_64 library)
- 07/docs-table-search: searches one graph (TXT-B12)

## M-10 Unit of work: all or none, inert refusal

- Implements: AX-04 All or none across stores, AX-03 Explicit, inert refusals, AX-12 Truthful outcomes and committed observations
- State: the caller's transaction level and its earlier write; the unit's writes to two stores; a failure point; the reply
- Operations: begin (nested in the caller's level); write store A; write store B; fail; commit; roll back
- Effect kinds: commit all, roll back own level, report code; events: reply (ok, refused with code)
- Model: `models/semantics/src/unit.rs` (18 checks, 18 met, exhaustive)

| Law | Kind | Statement | Negative control(s) | As-built checks attributed to it | Also violated by (complement) |
|---|---|---|---|---|---|
| M10-L1 | invariant | All or none: at the end of a unit, both of its writes are kept or neither. | `unit-control-C1-per-statement` | `unit-per-chunk-commit-as-built`, `unit-per-statement-commit-as-built`, `unit-no-transaction-as-built` | - |
| M10-L2 | invariant | Inert refusal: a refused unit leaves the caller's earlier writes as they were. | `unit-control-C2-rollback-all-levels` | `unit-rollback-all-levels-as-built` | - |
| M10-L3 | invariant | A refused unit replies refused, with a code of its family; an ok reply means both writes are kept. | `unit-control-C3-ok-on-failure` | `unit-wrong-reply-as-built`, `unit-hidden-failure-as-built` | - |

| Object | Use | Departures (law: findings or exception; why) | Where (pin) | Model checks |
|---|---|---|---|---|
| 03/caller-transaction | hand-rolled | M10-L1: F-0305 | `iris_vector_graph/bulk_loader.py (server-loader path)` | `unit-per-chunk-commit-as-built`, `unit-per-chunk-commit-reviewed` |
| 07/bm25-index | hand-rolled | M10-L2: F-C0702, F-0704 | `iris_src/src/Graph/KG/BM25Index.cls (insert in a caller transaction)` | `unit-rollback-all-levels-as-built`, `unit-rollback-all-levels-reviewed` |
| 04/adjacency-entry | hand-rolled | M10-L2: F-0409 | `iris_src/src/Graph/KG/Adjacency.cls (rebuild)` | `unit-rollback-all-levels-as-built`, `unit-rollback-all-levels-reviewed` |
| 16/bolt-session-with-a-key-set | hand-rolled | M10-L1: F-1601 | `iris_vector_graph/bolt_server.py:500-510, 567-622` | `unit-per-statement-commit-as-built`, `unit-per-statement-commit-reviewed` |
| 16/cypher-http-call | hand-rolled | M10-L1: F-1610, F-1609 | `iris_vector_graph/cypher_api.py:379-410` | `unit-per-statement-commit-as-built`, `unit-per-statement-commit-reviewed` |
| 15/fhir-graph | hand-rolled | M10-L1: F-1511, F-C1501 | `iris_src/src/Graph/KG/FHIRGraph.cls:167-279` | `unit-no-transaction-as-built`, `unit-no-transaction-reviewed` |
| 15/reifier | hand-rolled | M10-L1: F-C1502 | `iris_vector_graph/_engine/nodes_edges.py:2176-2199` | `unit-per-statement-commit-as-built`, `unit-per-statement-commit-reviewed` |
| 06/route | hand-rolled | M10-L1: F-0615 | `iris_vector_graph/_engine/embeddings.py (store_embeddings route creation)` | `unit-no-transaction-as-built`, `unit-no-transaction-reviewed` |
| 08/cypher-call | hand-rolled | M10-L3: F-0807, F-0804, F-0817 | `iris_vector_graph/_engine/query.py:1946-1966` | `unit-wrong-reply-as-built`, `unit-wrong-reply-reviewed` |
| 03/node-in-one-graph | hand-rolled | M10-L3: F-0306, F-0307 | `iris_vector_graph/_engine/nodes_edges.py (create_node)` | `unit-hidden-failure-as-built`, `unit-hidden-failure-reviewed` |
| 11/caller-transaction | canonical | - | `iris_src/src/Graph/KG/Ledger.cls:390-415` | `unit-canonical-as-built`, `unit-control-C1-per-statement`, `unit-control-C2-rollback-all-levels`, `unit-control-C3-ok-on-failure`, `unit-sharp-refused-inside-caller`, `unit-sharp-ok` |
| 07/fused-search | hand-rolled | M10-L3: F-0709 | `iris_vector_graph/_engine (fusion)` | `unit-hidden-failure-as-built`, `unit-hidden-failure-reviewed` |
| 05/temporal-coordinates | hand-rolled | M10-L1: F-C0501 | `iris_src/src/Graph/KG/TemporalIndex.cls (refused write)` | `unit-no-transaction-as-built`, `unit-no-transaction-reviewed` |
| 17/link | canonical | - | `iris_vector_graph/_write_txn.py:15-90` | `unit-canonical-as-built`, `unit-control-C1-per-statement`, `unit-control-C2-rollback-all-levels`, `unit-control-C3-ok-on-failure`, `unit-sharp-refused-inside-caller`, `unit-sharp-ok` |
| 07/docs-table-search | canonical | - | `iris_vector_graph/schema.py:2485-2523` | not modelled: not modelled: the SQL procedure without a word index refuses (TXT-B12.91) |
| 15/concept-pipeline | canonical | - | `iris_vector_graph/_engine/fhir_graph.py:395-484` | not modelled: not modelled: an unregistered graph is refused (INT-F8.1) |
| 15/cypher-anchors | hand-rolled | M10-L3: F-1508 (a failed FHIR-graph anchor read is answered as a bridge lookup) | `iris_vector_graph/cypher_api.py:327-347` | `unit-hidden-failure-as-built`, `unit-hidden-failure-reviewed` |
| 16/bolt-explicit-transaction | hand-rolled | M10-L1: F-1601 | `iris_vector_graph/bolt_server.py:500-510, 567-622` | `unit-per-statement-commit-as-built`, `unit-per-statement-commit-reviewed` |
| 16/fraud-server-call | hand-rolled | M10-L3: F-1615 (the vector lookup fails and the server scores with zeros as if it had succeeded) | `src/iris_demo_server/routes/fraud.py:107-145` | `unit-hidden-failure-as-built`, `unit-hidden-failure-reviewed` |

- 16/bolt-session-with-a-key-set: F-1601's reply aspect (BEGIN and COMMIT answer SUCCESS and do nothing) is not modelled separately; it is attributed to M10-L1 (each RUN commits on its own)
- 06/route: the route is made in its own steps before the batch, so a refused batch leaves it
- 08/cypher-call: refusals of the wrong class or answered as no rows
- 11/caller-transaction: the commit is a nested level; a refused changeset takes back its own level alone
- 07/fused-search: a failed leg is hidden in an ok answer
- 16/bolt-explicit-transaction: PULL n dropping rows (F-1602) is a functional finding

## M-11 Capability gate

- Implements: AX-13 Least capability, AX-03 Explicit, inert refusals
- State: the caller's key (none, wrong, ok) and role (read-write, read-only); the entry point's checks; the stores
- Operations: read; write; admin write; server-file call
- Effect kinds: allow, refuse before effect; events: 401 / 403
- Model: `models/semantics/src/cap.rs` (15 checks, 15 met, exhaustive)

| Law | Kind | Statement | Negative control(s) | As-built checks attributed to it | Also violated by (complement) |
|---|---|---|---|---|---|
| M11-L1 | action | A read-only caller changes nothing. | `cap-control-C1-write-without-read-only-check` | `cap-aql-as-built` | `cap-snapshot-file-helpers-as-built` |
| M11-L2 | action | With keys on, a missing or wrong key is refused before any effect. | `cap-control-C2-route-without-key-check` | `cap-demo-server-as-built`, `cap-privilege-in-engine-only-as-built` | `cap-snapshot-file-helpers-as-built` |
| M11-L3 | action | No entry point reads, writes or deletes server files, or runs caller text as code. | `cap-control-C3-file-route` | `cap-aql-code-text-as-built`, `cap-snapshot-file-helpers-as-built` | - |

| Object | Use | Departures (law: findings or exception; why) | Where (pin) | Model checks |
|---|---|---|---|---|
| 16/cypher-http-call | canonical | - | `iris_vector_graph/cypher_api.py; docs/ADMIN_GUIDE.md:824-840` | `cap-http-server-as-built`, `cap-control-C1-write-without-read-only-check`, `cap-control-C2-route-without-key-check`, `cap-control-C3-file-route`, `cap-sharp-keyed-write` |
| 16/rest-web-app-path | hand-rolled | M11-L2: F-1614 | `src/iris_demo_server/app.py:1-22` | `cap-demo-server-as-built`, `cap-demo-server-reviewed` |
| 08/cypher-call | hand-rolled | M11-L1: F-0814<br>M11-L3: F-0815, F-0814 | `iris_vector_graph/cypher/aql/translator.py:50-58, 154-168` | `cap-aql-as-built`, `cap-aql-reviewed`, `cap-aql-code-text-as-built`, `cap-aql-code-text-reviewed` |
| 18/snapshot-archive | hand-rolled | M11-L3: F-C1803, F-1806<br>M11-L1: F-C1803, F-1806 (the helpers run for a read-only caller too: no role check)<br>M11-L2: F-C1803, F-1806 (the helpers run for any Native API caller: no credential check) | `iris_src/src/Graph/KG/Snapshot.cls:4-73` | `cap-snapshot-file-helpers-as-built`, `cap-snapshot-file-helpers-reviewed` |
| 09/engine-native-path | hand-rolled | M11-L2: F-0908 | `iris_src/src/Graph/KG/Cypher/Exec.cls:32-72` | `cap-privilege-in-engine-only-as-built`, `cap-privilege-in-engine-only-reviewed` |
| 16/bolt-session-with-a-key-set | canonical | - | `iris_vector_graph/bolt_server.py` | `cap-http-server-as-built`, `cap-control-C1-write-without-read-only-check`, `cap-control-C2-route-without-key-check`, `cap-control-C3-file-route`, `cap-sharp-keyed-write` |
| 16/mcp-tool-set | canonical | - | `iris_src/src/Graph/KG/MCPTools.cls` | not modelled: not modelled: %AI classes absent on Community (F-1613 blocked-access) |
| 17/client-request | canonical | - | `iris_vector_graph/sdk.py` | `cap-http-server-as-built`, `cap-control-C1-write-without-read-only-check`, `cap-control-C2-route-without-key-check`, `cap-control-C3-file-route`, `cap-sharp-keyed-write` |
| 17/namespace | canonical | - | `iris_vector_graph/_engine/admin.py (reader role)` | `cap-http-server-as-built`, `cap-control-C1-write-without-read-only-check`, `cap-control-C2-route-without-key-check`, `cap-control-C3-file-route`, `cap-sharp-keyed-write` |
| 17/link | canonical | - | `iris_vector_graph/_write_txn.py` | `cap-http-server-as-built`, `cap-control-C1-write-without-read-only-check`, `cap-control-C2-route-without-key-check`, `cap-control-C3-file-route`, `cap-sharp-keyed-write` |
| 16/generated-graphql-call | canonical | - | `iris_vector_graph/gql (generated server)` | `cap-http-server-as-built`, `cap-control-C1-write-without-read-only-check`, `cap-control-C2-route-without-key-check`, `cap-control-C3-file-route`, `cap-sharp-keyed-write` |
| 16/demo-server-call | hand-rolled | M11-L2: F-1614 | `src/iris_demo_server/app.py:1-22, 131-136` | `cap-demo-server-as-built`, `cap-demo-server-reviewed` |
| 16/fraud-server-call | canonical | - | `src/iris_demo_server (fraud server)` | `cap-http-server-as-built`, `cap-control-C1-write-without-read-only-check`, `cap-control-C2-route-without-key-check`, `cap-control-C3-file-route`, `cap-sharp-keyed-write` |

- 16/bolt-session-with-a-key-set: keys are checked on HELLO/LOGON; F-C1603 (Bolt listens on every interface unless started by ivg server start) is network exposure, outside this machine's subset (no network model)
- 17/client-request: 401/403 mapping is F-1714 (AX-03)
- 16/generated-graphql-call: key and read-only checks per the cells (API-X1.5, API-X10.2); health always healthy is F-1611 (AX-12)

## M-12 Catalog binding of artifacts to graph and identity

- Implements: AX-02 Graph and tenant scope, AX-01 One writer per fact, AX-08 Derived stores match or say they are stale
- State: artifacts (index, route, compiled class) each with the (graph, identity) it records; the key that names an artifact; a reader's check
- Operations: create an artifact for (graph, identity); write through the catalog's check; read an artifact for (graph, identity); derive an artifact's name
- Effect kinds: bind, refuse a clash, read the bound artifact; events: identity clash, no route
- Model: `models/semantics/src/catalog.rs` (17 checks, 17 met, exhaustive)

| Law | Kind | Statement | Negative control(s) | As-built checks attributed to it | Also violated by (complement) |
|---|---|---|---|---|---|
| M12-L1 | invariant | Every artifact records the graph and identity it was built for. | `catalog-control-C3-no-record` | `catalog-bm25-index-graph-unchecked-as-built-M12-L1-F-0705` | `catalog-bm25-index-graph-unchecked-as-built-M12-L2-F-0705` |
| M12-L2 | action | A read or write checks the binding before using an artifact; a failed check refuses, never passes through. | `catalog-control-C1-unchecked-read`, `catalog-control-C4-fail-open` | `catalog-bm25-index-graph-unchecked-as-built`, `catalog-bm25-index-graph-unchecked-as-built-M12-L2-F-0705`, `catalog-ivf-index-graph-unchecked-as-built`, `catalog-identity-fail-open-as-built` | `catalog-bm25-index-graph-unchecked-as-built-M12-L1-F-0705`, `catalog-control-C3-no-record` |
| M12-L3 | invariant | Distinct (graph, identity) pairs name distinct artifacts. | `catalog-control-C2-short-hash` | `catalog-short-hash-name-as-built` | - |

| Object | Use | Departures (law: findings or exception; why) | Where (pin) | Model checks |
|---|---|---|---|---|
| 07/bm25-index | hand-rolled | M12-L1: F-0705<br>M12-L2: F-0705, F-0707 | `iris_src/src/Graph/KG/BM25Index.cls:608-612; iris_vector_graph/cypher/translator.py:3133-3134, 3283-3292` | `catalog-bm25-index-graph-unchecked-as-built`, `catalog-bm25-index-graph-unchecked-as-built-M12-L1-F-0705`, `catalog-bm25-index-graph-unchecked-as-built-M12-L2-F-0705`, `catalog-bm25-index-graph-unchecked-reviewed` |
| 06/ivf-index | hand-rolled | M12-L2: F-0609 | `iris_vector_graph/_engine/vector.py:194-225` | `catalog-ivf-index-graph-unchecked-as-built`, `catalog-ivf-index-graph-unchecked-reviewed` |
| 06/registry-row | hand-rolled | M12-L2: F-0601, F-0602, F-0603, F-0613 | `iris_vector_graph/_engine/schema.py:1033-1061; iris_vector_graph/_engine/embeddings.py:157-197, 2033-2049` | `catalog-identity-fail-open-as-built`, `catalog-identity-fail-open-reviewed` |
| 09/compiled-shape | hand-rolled | M12-L3: F-0901, F-C0901 | `iris_src/src/Graph/KG/Cypher/Gen.cls:69-80` | `catalog-short-hash-name-as-built`, `catalog-short-hash-name-reviewed` |
| 06/route | canonical | - | `iris_vector_graph/_engine/vector.py:164-226 (registry row names the table, VEC-I2.3)` | `catalog-canonical-as-built`, `catalog-canonical-reviewed`, `catalog-control-C1-unchecked-read`, `catalog-control-C2-short-hash`, `catalog-control-C3-no-record`, `catalog-control-C4-fail-open`, `catalog-sharp-three-artifacts` |
| 15/table-mapping | canonical | - | `iris_vector_graph (map_sql_table)` | `catalog-canonical-as-built`, `catalog-canonical-reviewed`, `catalog-control-C1-unchecked-read`, `catalog-control-C2-short-hash`, `catalog-control-C3-no-record`, `catalog-control-C4-fail-open`, `catalog-sharp-three-artifacts` |
| 10/native-route | canonical | - | `iris_vector_graph (proof record)` | `catalog-canonical-as-built`, `catalog-canonical-reviewed`, `catalog-control-C1-unchecked-read`, `catalog-control-C2-short-hash`, `catalog-control-C3-no-record`, `catalog-control-C4-fail-open`, `catalog-sharp-three-artifacts` |
| 17/index-handle | hand-rolled | M12-L2: F-0705<br>M12-L1: F-0705 (the handle's BM25 index records no graph (F-0705)) | `iris_vector_graph (index handle)` | `catalog-bm25-index-graph-unchecked-as-built`, `catalog-bm25-index-graph-unchecked-as-built-M12-L1-F-0705`, `catalog-bm25-index-graph-unchecked-as-built-M12-L2-F-0705`, `catalog-bm25-index-graph-unchecked-reviewed` |
| 15/code-crosswalk | canonical | - | `iris_vector_graph/_engine/fhir_graph.py` | `catalog-canonical-as-built`, `catalog-canonical-reviewed`, `catalog-control-C1-unchecked-read`, `catalog-control-C2-short-hash`, `catalog-control-C3-no-record`, `catalog-control-C4-fail-open`, `catalog-sharp-three-artifacts` |

- 15/table-mapping: F-1504 (schema USER) is a functional finding
- 10/native-route: routes by reader revision, not library version (CONTEXT.md:266-282)
- 15/code-crosswalk: a code crosswalk row binds a code to its concept (INT-C5)

## M-13 Read epoch: consistent multi-step read

- Implements: AX-12 Truthful outcomes and committed observations
- State: a multi-step change (marker set, step 1, step 2, cleared) and a reader that reads two parts in two steps; the reader's marker checks
- Operations: start a change; change part 1; change part 2; finish; reader: check, read part 1, read part 2, check
- Effect kinds: read, report interrupted; events: RedactionInProgress, interrupted read
- Model: `models/semantics/src/epoch.rs` (7 checks, 7 met, exhaustive)

| Law | Kind | Statement | Negative control(s) | As-built checks attributed to it | Also violated by (complement) |
|---|---|---|---|---|---|
| M13-L1 | invariant | A finished read returns parts of one committed state, or reports that it was interrupted. | `epoch-control-C1-no-end-check` | `epoch-check-at-start-as-built`, `epoch-no-check-as-built` | - |

| Object | Use | Departures (law: findings or exception; why) | Where (pin) | Model checks |
|---|---|---|---|---|
| 14/ledger-view | hand-rolled | M13-L1: F-1402 | `iris_vector_graph/ledger (record readers)` | `epoch-check-at-start-as-built`, `epoch-check-at-start-reviewed`, `epoch-control-C1-no-end-check`, `epoch-sharp-interrupted`, `epoch-sharp-new-state-read` |
| 18/snapshot-archive | hand-rolled | M13-L1: F-C1801 | `iris_vector_graph/_engine/snapshot.py:864-1034` | `epoch-no-check-as-built`, `epoch-no-check-reviewed` |
| 05/reader-handle | canonical | - | `iris_src/src/Graph/KG/TemporalWindow.cls` | not modelled: not modelled here: the paged window reader's consistency is HD-1401/HD-0903 working answers (quiet-writer premise) |

## Axiom-breaking findings not attached to a mechanism instance

88 findings break an axiom (`axioms.json`) but are not attached to a mechanism instance above, because the
mechanism instances model one representative variant per object and these findings are further variants, or because
the departure lies outside every machine's subset (network exposure, resource release, error-class mapping, cost):
F-0101, F-0102, F-0105, F-0106, F-0109, F-0204, F-0206, F-0209, F-0304, F-0308, F-0309, F-0401, F-0403, F-0404, F-0405, F-0505, F-0506, F-0513, F-0608, F-0614, F-0802, F-0803, F-0806, F-0816, F-0825, F-1009, F-1102, F-1103, F-1106, F-1107, F-1111, F-1509, F-1605, F-1611, F-1704, F-1709, F-1714, F-1807, F-C0150, F-C0151, F-C0301, F-C0330, F-C0340, F-C0341, F-C0347, F-C0348, F-C0349, F-C0350, F-C0351, F-C0402, F-C0415, F-C0440, F-C0450, F-C0640, F-C0690, F-C0701, F-C0717, F-C0748, F-C0840, F-C0841, F-C0848, F-C0940, F-C1001, F-C1040, F-C1041, F-C1101, F-C1102, F-C1107, F-C1108, F-C1109, F-C1110, F-C1150, F-C1202, F-C1250, F-C1301, F-C1302, F-C1307, F-C1351, F-C1540, F-C1547, F-C1548, F-C1601, F-C1602, F-C1603, F-C1640, F-C1740, F-C1741, F-C1802.
They stay counted against their axioms; attaching them (one more trait instance each) is an open part of 3.3a-mechanisms.
