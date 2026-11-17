# Iteration 60: obligations recovered from the ledger tests

Scope: the 50 ledger test files at the pin (16 unit, 27 integration, 7 e2e; about 7,500 lines) plus ledger assertions in
76 other test files, with `specs/213-graph-revision-ledger/contracts/{ledger-api.md,changeset.schema.json}`, USER_GUIDE
section 9 and "Writes inside your transaction", `docs/ledger-prometheus-hook.md`, KNOWN_ISSUES and CHANGELOG ledger
entries, and `git log` of the test and source files. Detailed per-test rows (U1-U67 unit, I1-I93 integration, E1-E27
e2e, O1-O31 elsewhere; every test function assigned, skip/xfail lists, destructive setup, product functions with pin
lines) are in [test-reading/](test-reading/); they were produced by three read-only reader sub-agents and spot-checked
against the pin by the builder (the auto-stub, `meta()` key, source-filter, contract-drift and hook-doc claims were
re-read in source and reproduced natively before use). This file groups them by rule and gives each group's status and
disposition. Redaction/erasure tests (`test_256_*`, `test_edgescan_ledger_erase.py`) were skimmed for their assertions
about non-redaction readers only (excluded area).

**Test status tiers.** RUN-UNIT: the unit file was executed in-process by the reader (187 items, 0 failures, 0 skips,
`SKIP_IRIS_TESTS=true` only to stop the gate plugin probing for a server); it uses fakes/mocks or reads `.cls` text, so it
is not runtime evidence about IRIS. NOT-RUN: integration/e2e tests need live IRIS and were **not** executed here — most
of their fixtures are destructive for a shared namespace (`ledger_reset` runs `Eraser.EraseAll` and `Ledger.PurgeAll`
before and after every test; snapshot, store-failure, compat and upgrade files drop tables, add triggers, purge or
recreate namespaces), so they are obligation sources only. NATIVE: the same obligation was observed by this
iteration's own probe or binding on the local fixture (task-owned namespaces `I60LA`-`I60LE`). No test is marked
xfail; perf tests are deselected by default (`-m "not perf"`), the embedded test skips outside `irispython`, the
two-namespace test skips when `IVGTEST` shares USER's globals, scratch-namespace e2e files skip without their
`IVG_NS_*` variables.

**Dispositions.** D = already derived by an existing model and its control excludes the asserted wrong outcome;
N = newly represented in iteration 60 (`ledger_client`, `ledger_verify`, or new bindings on an existing model);
O = represented in the canonical owner only (no formal claim); OC = owner text corrected or added in iteration 60;
M = missing distinction left open; P = mismatched premise; C = conflicts with owner/docs (finding or question);
T = test-only policy not promoted (reason given).

## A. Changeset builder, canonical form and fingerprint (owner `ledger.changeset`, `ledger.idempotency`)

| ID | Rule (outcome + essential conditions) | Test examples | Fixtures supply | Status | Formal claim | Disp. |
|---|---|---|---|---|---|---|
| A1 | Each builder call appends exactly one op, in call order; the ordered list is what is fingerprinted | U1, U2 (`test_all_op_kinds_serialize`, schema validation), U13 (`test_op_order_changes_fingerprint`) | pure builder | RUN-UNIT; NATIVE P1.2, B2 | `ledger_client::scope`, `theorem_scope_decides_fingerprint` (control `ops-not-fingerprinted`) | N |
| A2 | Fingerprint = SHA-256 of sorted-key compact JSON of {actor, actor_type, ops}; message, source, correlation ID, expected head and key do not change it | U10-U12, U215 metadata cases, I31 (key reuse with new message) | pure | RUN-UNIT; NATIVE P1.1, P1.2, S1.4, B1 | `theorem_metadata_outside_fingerprint` (control `message-fingerprinted`); collision freedom a premise | N |
| A3 | Values travel as strings (`42`→`"42"`, bools `"true"`/`"false"`); null refused | U6, KNOWN_ISSUES 305-330 | pure | RUN-UNIT; NATIVE S1.4 | `ledger_content::theorem_null_text_and_public_value_boundaries` (bound `_str_value`) | D |
| A4 | Reserved property names refused when the op is added, as `ChangesetOperationError` naming the op position; the server re-checks a raw op | U7, I17 (`test_reserved_property_rejected_before_any_apply`) | pure / live | RUN-UNIT; I17 NOT-RUN; NATIVE S1.3 | server side `ledger_apply::theorem_reserved_key_refuses`; client side owner only | D + OC (class now in owner) |
| A5 | A relationship reference is exactly one of statement ID, tuple, earlier OpRef; both/neither refused at the builder (`ValueError`) | U3, U4 | pure | RUN-UNIT; NATIVE S1.3, N7 | none (argument check) | O |
| A6 | `delete_node` defaults to strict: refused (`node_has_relationships`) with live relationships; detach records the relationship deletions first, in statement order | U5, I69, I70 | pure / live | RUN-UNIT; I69-70 NOT-RUN; NATIVE R2.A | none in a ledger model (`ledger_apply` has no delete op; `ledger_content::theorem_delete_node_is_not_relationship_cascade` covers records only) | OC + M |
| A7 | Auto-stub adds an `upsert_node` before the relationship for each endpoint no earlier op names; positions shift | U14, I55, 217 e2e | pure / live | RUN-UNIT; NATIVE P3.1-B (statement ID keyed at 3, not 2) | none | OC (position shift now stated). The suppression when an earlier `delete_node`/`set_prop` names the ID is test-only detail with no outcome change (the server refuses those cases anyway) — T |
| A8 | Empty changeset and an op_ref to a non-earlier/non-relationship op are refused before any server call | U8, U9, I13 | mock server records calls | RUN-UNIT; NATIVE S2.3, B5 | `theorem_empty_refused_before_the_server` (control `no-client-validate`), `client_commit` bad_ref branch | N + OC |

## B. Transport (owner `ledger.commit`, `ledger.commit.size`)

| ID | Rule | Tests | Fixtures | Status | Formal | Disp. |
|---|---|---|---|---|---|---|
| B1 | Payload ≤ 1,000,000 chars sent inline; above it staged in order and joined exactly; large answers returned as `CHUNKED:tag:n` and joined | U15-U17, I87 (2.5M answer), I88 (1.2 MB changeset) | mock / live | RUN-UNIT; NATIVE N10 (5.1 MB), B15 | `theorem_chunked_transport_roundtrip`, `lemma_join_chunks` (control `chunk-off-by-one`) | N + OC |
| B2 | Commit meta carries fingerprint, expected head, key, kind, schema | U18 | mock | RUN-UNIT | `client_commit` wire fields; exact meta key names are implementation detail | N / T |
| B3 | One `Commit` call per `commit()`, never retried | U19, U25 | mock | RUN-UNIT; NATIVE (one hook event per call) | `theorem_one_event_per_server_call` | N |
| B4 | Transport failures never raise from the transport layer; they become `inconsistent` → `LedgerInconsistencyError` | U23, U24 | mock raising | RUN-UNIT | `from_commit_error` (Inconsistent) — inspected, not observed natively | N (inspected). A failure after the server committed is reported as inconsistent though the revision exists — M (no idempotent recovery claim) |

## C. Error classes and mapping (owner `ledger.commit`, `.expected-head`, `.size`)

| ID | Rule | Tests | Status | Formal | Disp. |
|---|---|---|---|---|---|
| C1 | Every ledger error is a `LedgerError`/`IVGError`; `NodeNotFoundError` is a `ChangesetOperationError`; `IdempotencyRedactedError` an `IdempotencyConflictError` | U27, U31 | RUN-UNIT; NATIVE S3.3 | `is_op_error`, `is_conflict`, class rows bound | N |
| C2 | Attributes: `current_head`, `op_index` (zero-based; -1 if absent), `reason`, `limit`, `missing_node`, `bound`/`estimate` | U28, U30, U32, I15, I19, I26 | RUN-UNIT; NATIVE P2.1, P3.1, S3.5, R2-B | `theorem_failed_operation_reported`, `theorem_error_mapping_fallbacks`, `theorem_expected_head_outcomes`, `theorem_size_limit_boundary`; reconstruction `theorem_transient_oversize_refuses` | N |
| C3 | Each wire code maps to its class; unknown code → plain `LedgerError` with the text; `node_not_found:` narrows | U29, U33, U34, I56 | RUN-UNIT; NATIVE S3.3, B7 | `theorem_error_mapping_fallbacks` (controls `no-node-narrowing`, `op-index-lost`) | N |
| C4 | Two `NodeNotFoundError` classes exist (top-level and ledger); US02 and 217 expect different ones and pass only through subclassing | I15 vs I56 (reader conflict C5) | NOT-RUN | — | T (naming hazard noted; no outcome change) |

## D. Admission, idempotency, concurrency (owner `ledger.commit.admission`, `.idempotency`, `.expected-head`, `.serial`, `.size`)

| ID | Rule | Tests | Status | Formal | Disp. |
|---|---|---|---|---|---|
| D1 | Order lock → state → key → redacted key → expected head → empty/size → apply; a keyed retry replays even with a stale expected head | I30, U215 (`replayed=True` with different expected_head), changeset docstring | NOT-RUN; NATIVE P2.2, B1 | previously `ledger_redaction::theorem_retry_replays_first` with the binding supplied; now derived from `idem` state: `theorem_retry_with_new_metadata_replays` (control `expected-head-before-idempotency`) | N |
| D2 | Same key + same fingerprint replays: same revision, nothing applied, head and history unchanged | I29, I34 | NOT-RUN; NATIVE P1.1, N8 | same theorem; `witness_replay_returns_no_statement_ids` | N (bug-led-003 observation formalised) |
| D3 | Same key + different payload → `IdempotencyConflictError`, nothing applied | I31 | NOT-RUN; NATIVE P1.1-B, P1.2, B2 | `theorem_reordered_operations_conflict` | N |
| D4 | A key used only by a refused commit is free | I32 | NOT-RUN; NATIVE N2, B3 | `theorem_refused_key_stays_free` (control `key-bound-on-refusal`) | N |
| D5 | ... and so is a key whose commit the caller's rollback took back | **no test** | NATIVE N2.A, B9 | `theorem_rollback_frees_key_and_seq` (control `idem-not-journaled`) | N + OC (new obligation) |
| D6 | Unknown expected head → `UnknownRevisionError` (distinct from stale); stale names the current head; neither writes | I25, I26, U19 | NOT-RUN; NATIVE P2.1, P2.2, B3, B4 | `theorem_expected_head_outcomes` (controls `unknown-as-stale`, `stale-names-expected`) | N |
| D7 | Two writers with the same expected head: exactly one wins; same key and payload concurrently: one revision | I26, I33 | NOT-RUN (multi-process) | playbook `proofs-pa3` head lock / `theorem_key_binds_one_fingerprint` (reviewed design) | D |
| D8 | Many writers keep one contiguous single-parent chain | I27, I28, I93 | NOT-RUN (perf/soak, destructive reset) | `proofs-pa3` serialization (reviewed design); `ledger_client::write` (parent = head) | D |
| D9 | Over `max_ops` refused with the limit before apply; exactly `max_ops` commits | I19, observability too_large | NOT-RUN; NATIVE S3.5, B6 | `theorem_size_limit_boundary` (control `size-limit-exclusive`) | N |
| D10 | A failing op rolls back the whole changeset; position reported; references to entities deleted earlier in the changeset fail at that op | I15, I16, I21, I22 | NOT-RUN; NATIVE P3.1, N3 | `ledger_apply::theorem_mid_failure_rolls_back_prefix` | D |
| D11 | Duplicate set in one changeset records both; same-value write records nothing; an all-no-op changeset is still a revision | I20, I67 | NOT-RUN; NATIVE N4 | `ledger_apply::theorem_two_writes_produce_priors`, `theorem_noop_has_no_property_record`; empty revision owner only | D + OC |
| D12 | Statement IDs are never reused | I21 | NOT-RUN | `ledger_content` fresh coherent identities | D |
| D13 | A store refusal (trigger `%ok=0`) fails the whole commit | I23 | NOT-RUN (adds triggers to shared tables) | `ledger_apply` assumes successful SQL | P (provider refusal not modelled) |
| D14 | Lock held by another process > 30 s → `LedgerLockTimeoutError` for commit and enable; then succeeds | I9 | NOT-RUN (holds the lock 38 s) ; NATIVE N1 (40 s, through a caller transaction) | `theorem_caller_transaction_holds_the_head`; enable's lock wait not modelled | N (commit) / M (enable) |

## E. Caller transactions (owner `ledger.commit.caller-transaction`)

| ID | Rule | Tests | Status | Formal | Disp. |
|---|---|---|---|---|---|
| E1 | A commit joins the caller's open transaction (`$TLEVEL` stays); caller commit keeps both, rollback removes revision, writes and post-commit properties with no seq gap | E20-E23, E25, I24 | NOT-RUN; NATIVE P5.2-B, N2.A, B9 | `theorem_rollback_frees_key_and_seq`, `txn_rollback` | N |
| E2 | The head stays locked until the caller's transaction ends; another connection's commit times out and changes nothing | E24 (raw `lock` with timeout 0 only), USER_GUIDE 296-300 | E24 NOT-RUN; **no test drives a competing commit**; NATIVE N1, B8 | `theorem_caller_transaction_holds_the_head` (control `lock-released-inside-transaction`) | N + OC |
| E3 | `enable()`/`redact()` refuse an open caller transaction (`LedgerTransactionOpenError`), nothing done | E26, I8 | NOT-RUN; NATIVE S4.3 | `theorem_enable_lifecycle` (in-transaction branch) | N |
| E4 | `disable()`/`set_strict()` join the caller transaction (not refused) | none | NATIVE S4.3 (disable joined, rolled back) | none | O (HD-1102 open; evidence added in handoff) |
| E5 | Autocommit off counts as a caller transaction | none (doc only) | NATIVE (probes use `setAutoCommit(False)`) | not distinguished in the model | O |
| E6 | A failing changeset inside the caller's transaction rolls back only its own level | none | not observed | none | M |
| E7 | The contract still lists `LedgerTransactionOpenError` for `commit` and only lock timeout for `enable` | reader conflicts C1/C2 (all three readers) | text | — | C → bug-doc-014 |

## F. Lifecycle (owner `ledger.lifecycle`, `.genesis`)

| ID | Rule | Tests | Status | Formal | Disp. |
|---|---|---|---|---|---|
| F1 | First enable writes genesis seq 1, no parent; enabling again returns the head and writes nothing | I1, U20-U21 | NOT-RUN / RUN-UNIT; NATIVE c.enable, P4.2-B | `theorem_enable_lifecycle` | N |
| F2 | ... and does not switch strict on (`enable(strict=True)` on an enabled ledger) | none | NATIVE P4.2-B, B12 | `theorem_enable_lifecycle` (control `enable-on-enabled-sets-strict`) | N + OC |
| F3 | Genesis describes the pre-populated graph (temporal marked rows excluded); verify equal right after | I2, I3, E1-E3, I92 | NOT-RUN | `ledger_content` Capture (partial); `ledger_verify` equal | D (partial) + N |
| F4 | Never enabled: legacy writes create no ledger data; `head()`/`verify()`/`set_strict()` → `LedgerNotEnabledError`; status `never-enabled` | I5, I6, U22 | NOT-RUN / RUN-UNIT; NATIVE N6-A, P3.2-A, B11, B13 | `theorem_head_reader_states`, `theorem_disabled_and_never_enabled`, `theorem_disable_and_set_strict` | N + OC |
| F5 | Disabled: commit refused + `rej_disabled`; head/history readable; disable repeatable; re-enable adopts unrecorded writes | I7 | NOT-RUN; NATIVE P3.2-B, N6-B, P4.2 | same theorems; re-enable adoption = `ledger_verify` adoption | N + OC (re-enable adopts **every** difference, not only writes made while disabled; strict from the call) |
| F6 | `set_strict` while disabled is reset by the next `enable()` | none | NATIVE B12 | `witness_strict_set_while_disabled_is_reset_by_enable` | N + OC |
| F7 | Two namespaces have independent ledgers | I42 | skipped by default (shared globals) | not modelled (per-namespace globals) | O |
| F8 | R281/R290 fixtures read `meta()["enabled"]`, which does not exist, so teardown always disables the shared namespace's ledger | E8-E13 fixtures (reader finding) | partial NATIVE (meta key set) | — | C → bug-test-004 (test-suite defect) |

## G. Strict mode guard (owner `ledger.strict`, `access.ledger_strict*`)

| ID | Rule | Tests | Status | Formal | Disp. |
|---|---|---|---|---|---|
| G1 | Each guarded call raises `LedgerStrictModeError` and changes nothing; Cypher updating clauses refused; reads allowed | I36, O1, O3 | NOT-RUN; NATIVE P4.1, V1-B | `platform::theorem_strict_paths` (now bound to guard members) | D + N (bindings) |
| G2 | Guard caches `Meta` for 5 s, `refresh()` applies at once to the calling engine; probe failure fails open; class absence cached | U35-U38 | RUN-UNIT; NATIVE P4.1 (same engine at once), S4.5 (other engine 5.07 s) | `platform` `seen_strict`, `probe_value`, witnesses | D + N (bindings) |
| G3 | A strict refusal counts `rej_strict_block` | U35, I84 | RUN-UNIT; NATIVE N8 | `theorem_strict_paths` (refusals+1) | D |
| G4 | Temporal write with a graph under strict writes the temporal edge and skips the structural mirror | U39, I37, O2 | RUN-UNIT; I37 NOT-RUN | platform/temporal models | D (reader C7: the promise is unobservable through verify, which drops marked rows — T) |

## H. Readers (owner `ledger.readers`, `.history`, `.diff`, `.bound`)

| ID | Rule | Tests | Status | Formal | Disp. |
|---|---|---|---|---|---|
| H1 | History ascending, paged exactly once, filters (actor, actor_type, time, correlation) keep order | I43-I46, U60, E4-E6 | NOT-RUN / RUN-UNIT; NATIVE H1, H2 | `history_paging` | D |
| H2 | `history(source=...)` filters by source | U60 (SQL text only) | NATIVE: a text source is dropped; only exact compact JSON of an object matches | `witness_text_source_is_dropped` (control `text-source-kept`) | C → bug-led-012; OC |
| H3 | `get_revision` returns ordinal-ordered records with prior/new; records SQL proc pages; `CanonicalRecord` sorted keys | I47, I85, I86, O17-O19 | NOT-RUN | `ledger_apply::revision`, `ledger_content` records | D (CanonicalRecord unbound; redaction-adjacent) |
| H4 | Unknown revision ID → `UnknownRevisionError` from `get_revision`/`diff` (and reconstruct/export) | I48 | NOT-RUN; NATIVE N5, B10 | `theorem_revision_readers_resolve_ids` (control `unknown-id-reads-genesis`) | N + OC |
| H5 | Diff is net, deterministic, node-before-rel ordered, exact inverse, lifecycle-aware, empty for equal endpoints | I49-I54, U47-U52 | NOT-RUN / RUN-UNIT; NATIVE D1, D2 | `history_diff`, `ledger_content` | D (new bindings for `Diff`, `DiffEntry.inverse`, `Diff.__eq__`) |
| H6 | Reconstruct at a revision; bound refuses intermediate oversize; stream and export unbounded; export round-trips through `import_graph_ndjson` | I57-I61, U53-U55 | NOT-RUN; NATIVE R1, R2 | `reconstruction`, `ledger_content` | D; the import half of I61 not modelled — M |

## I. Verify and adoption (owner `ledger.verify`, `.scope`, `ledger.unrecorded`)

| ID | Rule | Tests | Status | Formal | Disp. |
|---|---|---|---|---|---|
| I1 | Clean ledger → `equal`, no differences, verified head = head; result recorded in stats | I62 | NOT-RUN; NATIVE V1, N9, V0 | `ledger_verify::theorem_equal_iff_views_agree`, `theorem_adoption_only_when_needed` | N (stats `last_verify_*` owner `install.status.ledger` only — O) |
| I2 | Legacy, Cypher and raw SQL writes are unrecorded: diverges with node/label/prop/rel entries | I35, I63, I4 | NOT-RUN; NATIVE V1-B, V2-A, C2, verify binding V1 | `theorem_entries_for_created_and_deleted_nodes` (control `new-entity-attributes-dropped`) | N |
| I3 | `verify(adopt=True)` writes one adoption revision (actor `system:ledger-verify`, parent the old head), one record per difference; next verify equal | I64 | NOT-RUN; NATIVE N9, C2, verify binding V2 | `theorem_adoption_closes_the_difference` (control `adopt-without-cascade`) | N + OC |
| I4 | Verify without adopt is read-only; with adopt and no differences writes nothing | I65 | NOT-RUN; NATIVE N9, V0 | `theorem_adoption_only_when_needed` (control `adopt-when-equal`) | N + OC |
| I5 | Temporal edges are not structural: marked rows out on both sides; a governed create adopts the row | I37, I40, I41, E3, U59 | NOT-RUN / RUN-UNIT; NATIVE V2-B, C1 | `theorem_temporal_marked_rows_left_out` (controls `temporal-row-governed`, `replay-keeps-marked`) | N (the replay half inspected only; U59's fake has no marked row — reader note) |
| I6 | Nodes by ID across graphs; reserved props out; statement IDs not compared | I3 (named graph), r290 (no verify call) | NOT-RUN; NATIVE verify binding (`uy` in a named graph) | `theorem_node_identity_ignores_graph`, `theorem_reserved_properties_left_out`, `theorem_statement_ids_not_compared` | N. A node ID with property rows in two graphs merges in row order — M (q-led-004) |
| I7 | Verify alongside a commit reports a head it observed at the start and claims no false deletion | I66 | NOT-RUN | premise of quiescence (q-led-006) | P (the model assumes what the test probes) |

## J. Observability (owner `ledger.observability` — new)

| ID | Rule | Tests | Status | Formal | Disp. |
|---|---|---|---|---|---|
| J1 | Each server outcome is logged once, sent to every hook once (success, replayed, stale_head, idempotency_conflict, failed_op, too_large, disabled, not_enabled, lock_timeout) and counted (`commits_ok` incl. genesis, `replays_idem`, `rej_*`; not_enabled uncounted) | I83, I84, U40, U41 | NOT-RUN / RUN-UNIT; NATIVE N8, S3.4, P3.2, binding deltas on every case | counter and event conclusions of the `ledger_client` theorems; `theorem_one_event_per_server_call` | N + OC |
| J2 | A raising hook is logged and does not change the result; `enable()` emits no event (adoption on re-enable does, through `verify`) | U41 | RUN-UNIT; NATIVE S3.4 | owner only | OC |
| J3 | Client-side refusals reach no hook, against the hook doc | **no test** | NATIVE S2.3, B5 | `theorem_one_event_per_server_call` (control `event-on-client-refusal`) | C → bug-doc-013 |
| J4 | `status().ledger` for a never-enabled or unreadable ledger | I6, O24 | NOT-RUN / RUN-UNIT | `operator_reports` | D |

## K. Immutability (owner `ledger.immutability`)

| ID | Rule | Tests | Status | Formal | Disp. |
|---|---|---|---|---|---|
| K1 | SQL UPDATE/DELETE of `ledger_revisions` refused; no public mutator | I14 | NOT-RUN; NATIVE V1-B, B14 | `theorem_revision_rows_immutable` | N |
| K2 | The single redaction exception (four free-text fields emptied) | `test_256_*` (excluded) | NOT-RUN | same theorem (control `update-without-emptying`, inspected only) | N (inspected) |

## L. Adjacency, post-commit, scope, setup and migration (neighbors)

| ID | Rule | Tests | Status | Formal | Disp. |
|---|---|---|---|---|---|
| L1 | Ledger relationship commits land on the index key, refresh weights in their own graph, delete only their own graph's adjacency; no drift | I79-I82, O4-O7 | NOT-RUN | `graph_structure`, `adjacency_maint` | D |
| L2 | Ledger node operations touch only default-graph rows | E8-E13, U67 | NOT-RUN / RUN-UNIT (source text) | `ledger_content` default profile (partial) | D (partial); verify never called on the two-graph fixture — M |
| L3 | Post-commit properties: sentinel substituted, default graph only, unrecorded, joins the caller transaction, refused DELETE reported | O9, O10, E8, E23 | NOT-RUN / RUN-UNIT; NATIVE P5.1, P5.2 | none (owner `ledger.commit.post-commit`; bug-led-003/009) | O |
| L4 | Setup creates and builds the correlation index; a class reload keeps it; an unbuilt declared index makes `history(correlation_id=)` find nothing until setup builds it | U61-U66, E4-E6, O15 | RUN-UNIT; e2e NOT-RUN | none | M (install-area residual; history result depends on it) |
| L5 | Snapshot save/wipe/restore preserves head, history and verify | I89 | NOT-RUN (destructive) | none | M |
| L6 | Upgrade copies ledger history into the schema's own tables, idempotently; dry run writes nothing | E14-E19, O12, O14, O18, O27 | NOT-RUN (drops/recreates a namespace) | none | M (migrations queue Q9) |
| L7 | Commit latency, reconstruct and genesis time thresholds | I90-I92 | deselected perf | — | T (performance policy, not a behavioral obligation) |
| L8 | NKG staleness: a refused commit leaves `_nkg_dirty` unset; a relationship commit marks it when `^NKG` is absent | U26, I18 | RUN-UNIT (weak: its changeset never marks even on success); NATIVE S5.3: the flag was never set after a relationship commit (Native API answers `None` for the absent count, `str(None) != ""`) | none | M (candidate; consequence not established — handoff) |

## Summary

Recovered obligation groups: **76** (A 8, B 4, C 4, D 14, E 7, F 8, G 4, H 6, I 7, J 4, K 2, L 8), covering 148 unit
functions (187 items), 118 integration functions (123 items), 35 e2e items and 31 cross-file rows.

| Primary disposition | Groups | Which |
|---|---|---|
| Newly represented in iteration 60 (N: formal claim with control + native binding or observation) | 36 | A1, A2, A8, B1-B4, C1-C3, D1-D6, D9, D14, E1-E3, F1, F2, F4-F6, H4, I1-I6, J1, K1, K2 |
| Already derived by an existing model (D, some partial) | 19 | A3, A4, D7, D8, D10-D12, F3, G1-G4, H1, H3, H5, H6, J4, L1, L2 |
| Owner only, no formal claim (O) | 6 | A5, E4, E5, F7, J2, L3 |
| Owner corrected, no formal claim (OC) | 1 | A7 |
| Missing distinction left open (M) | 6 | A6, E6, L4, L5, L6, L8 (also secondary in B4, D14, H6, I6, L2) |
| Mismatched premise (P) | 2 | D13 (provider refusal), I7 (concurrent verify) |
| Conflict with owner/docs → finding (C) | 4 | E7 → bug-doc-014, F8 → bug-test-004, H2 → bug-led-012, J3 → bug-doc-013 |
| Test-only policy not promoted (T) | 2 | C4, L7 (also secondary in A7, B2, G4) |

Owner text was corrected or added for 18 groups (A4, A6, A7, A8, B1, D5, D11, E2, F2, F4, F5, F6, H2, H4, I3, I4, J1,
J2), including the new block `ledger.observability`. Of the 36 newly represented groups, four have no test at all (D5, E2's competing commit, F2, F6), H4 is tested only for
`get_revision`/`diff`, and A1-A2, A8, B1-B4 and C1-C3 are asserted only by in-process unit tests with mocks; the rest have
live-IRIS tests that were not run here and are now matched by this iteration's native observations.

**Material obligations the tests do not state** (found by predictions and source reading, now owned and modelled):
the caller's rollback frees the idempotency key (D5); a competing commit times out while a caller transaction holds the
head (E2; the only test takes a raw lock with timeout 0); `enable(strict=True)` on an enabled ledger leaves strict off
(F2); `set_strict` while disabled is lost on re-enable (F6); re-enable adopts every unrecorded difference, not only
writes made while disabled (F5); client-side refusals reach no hook (J3); a text source is dropped (H2).

**Weak or vacuous tests noted by the readers** (not product findings): `test_216` "actor_type" test passes `actor=`;
`test_read_canonical_ignores_temporal_only_edges` has no edge rows; `test_nkg_dirty_not_set_on_transport_failure`
uses an op that never marks; the adjacency `deg == ""` checks are vacuous (`^KG("deg")` never set); the reifier test
inserts the node it says is absent; `test_262_alt_schema_paths.py:464` counts `'altrd:x'` for a node written as
`'altrd|x'`; `ledger_reset` calls `PurgeAll` through a second connection inside `suppress`, a pattern
`test_master_cleanup.py:7-14` says never worked (unverified here).
