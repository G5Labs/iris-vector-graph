# Iteration 60 handoff (builder): ledger client, admission, readers and verify from the test-obligation map

Assignment: [ASSIGNMENT.md](ASSIGNMENT.md). Builder session started 2026-11-17T19:28Z, batch committed 20:19Z, handoff
20:20Z (about 55 minutes wall clock; three read-only test-reader sub-agents ran in parallel for ~16 minutes each).
Foundation before `01e8ccba7` (verified as HEAD at start; no new commits) → checkpoints `ebb8a679d` (frozen
predictions), `fe413416c` (ledger_client), `ee69d59e3` (batch) → this handoff commit. Product pin `3eaa79cf` unchanged
(consolidated confinement check passes). Fixture: local `ivg-uplift-next-20261115` (127.0.0.1:35975, IRIS 2026.1 Build
234U, instance hostname `1a97b1515453` checked on every connection by
[local-runtime/runtime.py](../local-runtime/runtime.py)); task-owned namespaces created additively with SQL
`CREATE DATABASE` from `%SYS` and deployed with `initialize_schema()`: **I60LA** (W1 client/admission, lock, large),
**I60LB** (W2 readers, verify binding), **I60LC** (never enabled, then `max_ops=2`, `recon_bound=1`), **I60LD**
(`recon_bound=2`), **I60LE** (never enabled; never enabled by this work). Nothing was written to USER except the
`bolt_tx` binding's per-run prefixed nodes (its own design; additive). No erase/kill/drop.

## 1. Test-obligation map

[test-obligations.md](test-obligations.md): **76 rule groups** from the 50 ledger test files and 31 ledger rows in other
tests (raw per-test readings in [test-reading/](test-reading/)). Unit tests were run in-process by the reader (187 items
pass; mocks only, so they are not IRIS evidence); integration/e2e tests were **read, not run** (live IRIS; most
fixtures erase or purge the namespace).

| Primary disposition | Groups |
|---|---|
| Newly represented in iteration 60 (formal claim + control + native observation) | 36 |
| Already derived by an existing model | 19 |
| Owner only / owner corrected without a formal claim | 7 |
| Missing distinction left open | 6 (+5 secondary) |
| Mismatched premise | 2 |
| Conflict with owner/docs → finding | 4 |
| Test-only policy not promoted | 2 (+3 secondary) |

Most material: the keyed-replay/conflict decision was formal only with the binding **supplied as input**
(`ledger_redaction::commit_outcome`); it is now derived from the ledger's own state and the changeset's scope. Verify
(`ledger.verify`, `.scope`, `ledger.unrecorded`) had **no formal claim at all**. Behavior no test drives but the
predictions exposed: a caller rollback frees the idempotency key and seq; a competing commit times out (40 s) while a
caller transaction holds the head; `enable(strict=True)` on an enabled ledger leaves strict off; `set_strict` made while
disabled is reset by the next enable; re-enable adopts every unrecorded difference (not only writes made while
disabled); client-side refusals reach no metrics hook; a text `source` is dropped.

## 2. Canonical owners changed (`.g5/ontology/features/ledger.g5.md`, one metadata line in `concepts/access.g5.md`)

- `ledger.lifecycle`: readers keep working while disabled; before the first enable `head()`/`verify()`/`set_strict()`
  are refused and history is empty; enabling an enabled ledger leaves strict as it was; re-enable records **every**
  difference verify finds as one adoption by `system:ledger-verify` and takes strict from the call (corrected wording).
- `ledger.changeset`: reserved-name refusal class and timing; node deletion mode (strict default refuses with live
  relationships; detach records relationship deletions first).
- `ledger.commit`: statement-ID positions count auto-stub operations; an all-no-op changeset is a revision with no records.
- `ledger.commit.size`: limit inclusive and carried by the error; empty changeset and bad op reference refused by the
  client before anything is sent (state-independent, uncounted, no hook); payloads above one transport piece arrive whole.
- `ledger.commit.caller-transaction`: rollback frees the key; a competing commit fails with `LedgerLockTimeoutError`.
- `ledger.idempotency`: key free after a refusal or a caller rollback.
- `ledger.readers`: source kept only as an object's compact JSON (text dropped today, bug-led-012); every revision-ID
  reader refuses an unknown ID before reading or writing.
- `ledger.verify`: nothing recorded when equal; created entities reported with attributes, deleted ones as one deletion.
- **New block `ledger.observability`**: one log line, one hook event and one counter per server outcome; client-side
  refusals and not-enabled refusals uncounted; raising hooks logged.
- Metadata: formal links (ontology → model only) on 13 blocks; findings back-links; `access.bolt.transactions` now links
  bug-plt-136 back (inherited checker problem fixed).

`check_ontology.py`: 0 issues, 17 writing warnings (baseline 0 / 17), 406 blocks (+1).

## 3. New formal distinctions (Verus; transcription with native agreement; direct body proofs 0)

[ledger_client](../../../Verus_verification/models/ledger_client/NOTES.md) — 27 verified, 21/21 controls
(`results/ledger_client/20261117T195357Z-prove`, controls `20261117T1953*`/`1954*`). Each control removes a deciding
guard or effect and the named theorem fails:

| Theorem | Wrong outcome now excluded (control) |
|---|---|
| `theorem_metadata_outside_fingerprint`, `theorem_retry_with_new_metadata_replays` | a retry with a new message conflicts (`message-fingerprinted`); a stale expected head beats the key (`expected-head-before-idempotency`); a replay counted as a commit (`replay-counted-as-commit`) |
| `theorem_reordered_operations_conflict` | reordered ops replay (`ops-not-fingerprinted`) |
| `theorem_refusal_writes_nothing`, `theorem_refused_key_stays_free` | a refusal binds its key (`key-bound-on-refusal`) |
| `theorem_expected_head_outcomes` | unknown head treated as stale (`unknown-as-stale`); StaleHeadError names the expected head (`stale-names-expected`) |
| `theorem_disabled_and_never_enabled` | never-enabled counted as disabled (`never-counted-as-disabled`) |
| `theorem_empty_refused_before_the_server` | empty check moved to the server (`no-client-validate`) |
| `theorem_size_limit_boundary` | exactly max_ops refused (`size-limit-exclusive`) |
| `theorem_failed_operation_reported`, `theorem_error_mapping_fallbacks` | NodeNotFoundError not narrowed (`no-node-narrowing`); position lost (`op-index-lost`) |
| `theorem_caller_transaction_holds_the_head` | head released at the nested commit (`lock-released-inside-transaction`) |
| `theorem_rollback_frees_key_and_seq` | key binding survives rollback (`idem-not-journaled`) |
| `theorem_revision_readers_resolve_ids`, `theorem_head_reader_states` | unknown ID reads genesis (`unknown-id-reads-genesis`); head refused while disabled (`head-refused-while-disabled`) |
| `theorem_enable_lifecycle` | enable on an enabled ledger switches strict (`enable-on-enabled-sets-strict`) |
| `theorem_one_event_per_server_call` | client refusal emits an event (`event-on-client-refusal`) |
| `witness_text_source_is_dropped` | text source kept (`text-source-kept`) |
| `theorem_revision_rows_immutable` | redaction exception without emptying (`update-without-emptying`) |
| `lemma_join_chunks`, `theorem_chunked_transport_roundtrip` | off-by-one chunking (`chunk-off-by-one`) |

[ledger_verify](../../../Verus_verification/models/ledger_verify/NOTES.md) — 8 verified, 8/8 controls
(`results/ledger_verify/20261117T200656Z-prove`): `theorem_equal_iff_views_agree`, `theorem_adoption_closes_the_difference`
(controls `adopt-without-cascade`, `new-entity-attributes-dropped`), `theorem_entries_for_created_and_deleted_nodes`,
`theorem_adoption_only_when_needed` (`adopt-when-equal`), `theorem_node_identity_ignores_graph`
(`graph-scoped-node-identity`), `theorem_reserved_properties_left_out` (`reserved-kept`),
`theorem_temporal_marked_rows_left_out` (`temporal-row-governed`, `replay-keeps-marked`),
`theorem_statement_ids_not_compared` (`statement-ids-compared`).

Premises kept explicit: apply outcome supplied (ledger_apply); collision-free SHA-256 where required; the server trusts
the meta fingerprint the Python client computes (direct `Graph.KG.Ledger.Commit` callers outside the claim);
quiescent verify inputs (q-led-006); one value per (node, key) in verify (two-graph merge outside, q-led-004).

## 4. Bindings and receipts (local fixture)

- `ledger_client` binding ([receipt](../../../Verus_verification/results/ledger_client/20261117T195905Z-binding/receipt.json)):
  **AGREES, 35 native cases**, 0 mismatches; 20/21 mutations detected (the redaction-context update is inspected only);
  a changed observation is caught. The first run of the harness (`195805Z`) is kept: it DISAGREED only because one
  mutation was undetectable before the chained B3 case was added.
- `ledger_verify` binding ([receipt](../../../Verus_verification/results/ledger_verify/20261117T200650Z-binding/receipt.json)):
  **AGREES, 3 cases / 9 entry facts** over seven kinds of unrecorded write; 6/8 mutations detected (2 need forged history).
- Prediction probe ([probes/](probes/), [grades](PREDICTIONS-graded.md)) adds the W1/W2/N native observations.
- Inherited stale receipts refreshed by faithful reruns: `adjacency_maint` prove 35 verified + 15/15 controls
  (`20261117T2015*`), `bolt_tx` prove 35 verified + 15/15 controls (`20261117T2016*`), and the `bolt_tx` binding rerun
  on the local fixture (**AGREES 26 cases**, every sensitivity detected, receipt `20261117T201659Z-binding` recording
  `ivg-uplift-next-20261115`). The cloud receipts are kept and not relabelled.
- Crosswalk: `decision-links.tsv` 1175 → 1273 rows (90 `C-ledger_client`/`G-platform`/reader rows with exact pin lines,
  8 `C-ledger_verify`); `families.tsv` +2 active families. Guard members are bound to the existing `platform` claims with
  fresh native observations (same-engine refusal at once, other engine 5.07 s, `rej_strict_block` 0→1); platform proofs
  were not rerun.

## 5. Recount (pinned instrument, `recount.py HEAD`, out `$G5_RUN_STATE/counts/iteration-60-builder/ee69d59e`)

Union **956 → 1028** (+72), active **706 → 793** (+87). Newly reached 72; gained an active binding 87; overlap 72
(the 15 that were locator-only before: `GraphLedger.disable/set_strict`, `Changeset.fingerprint`,
`replay.read_canonical/verify`, `LedgerGuard.__init__/_probe/check_structural_write/count_rejection/is_strict`,
`LedgerMixin._ledger_guard`, `Ledger.Enable/SetStrict`, `LedgerStats.Bump/Ensure`); distinct 87; **losses 0**. By file (gained active): errors.py 21, client.py 17, Ledger.cls 14,
replay.py 11, changeset.py 6, guard.py 6, LedgerRevision.cls 4, _engine/ledger.py 3, LedgerStats.cls 3, export.py 2.
Member lists: [member-delta.json](member-delta.json). New locators are exact declarations; every new active row names a
formal function that resolves once, a role and an evidence grade; class/value members are bound as the outcome types a
caller catches, not as whole-method proofs.

## 6. Predictions

Adopted (iteration-59 W1/W2 tables, frozen by another session for the cloud fixture; graded unedited, fixture names
translated only): 20 rows — **16 held, 3 partial, 1 missed**. Partial: S1.3 (reserved-name class is
`ChangesetOperationError`), P3.1 (auto-stub shifts the statement-ID position to 3), S4.4 (`head()` before enable raises).
Missed: S5.3 (no commit set the NKG dirty flag). New (frozen before any test or source, commit `ebb8a679d`): 10 rows —
**10 held**. None of the 30 rows was test-informed. Material predictions gained: N1/N2 (caller transaction holds the head;
rollback frees key and seq), N3, N4, N10 bound behavior no model had. The adopted S5.3 miss exposed the NKG candidate.

## 7. Findings, questions, simplifications

New (all Low, Decision: Open, placed before the non-actionable entries):
- **bug-led-012** text `source` dropped; history source filter matches only exact compact JSON — **E2E** (I60LB).
- **bug-doc-013** metrics hook not called for client-side refusals against its document — **E2E**.
- **bug-doc-014** spec 213 contract lists pre-4.7.0 transaction errors, lacks history filters and wire fields — behavior
  half **E2E**, document half text comparison.
- **bug-test-004** R281/R290 fixtures read `meta()["enabled"]` (no such key), so teardown always disables the shared
  scratch ledger — **partial** (meta key set observed; teardown not run on a shared namespace).

Strengthened (no new count): bug-led-003 (replay re-applies post-commit properties and returns no statement IDs:
re-observed natively and formalised as `witness_replay_returns_no_statement_ids`), bug-led-009 (post-commit under
strict, re-observed), bug-tmp-004 (verify names temporal endpoints, re-observed V2/C2), bug-led-101 (diff range prior,
re-observed D2-B), F-0801 (5 s strict window, re-observed 5.07 s). Withdrawn: none.

`findings.tsv`: rows added for the 4 new entries and for the 3 inherited entries missing at baseline (bug-cyp-157,
bug-cyp-158, bug-plt-136). Format-only repair: the 276 inherited `Run:` paragraphs were moved directly after their
status lines (all 277 entries were `Decision: Open`; identical non-blank lines before/after), so the findings checker
passes. `findings.md` was not regenerated: `make_findings_index.py` refuses to overwrite the audited index.

Questions: none opened. New native evidence for existing open questions (generated entries, not edited): HD-1102
(`disable()` in a caller transaction joins it and is undone by the rollback: S4.3), HD-1104 (re-enable takes strict from
the call and keeps `max_ops`/`recon_bound`: P4.2, B12), q-led-005 (unchanged), q-led-006 (now a named premise of
`ledger_verify`), q-led-004 (two-graph property merge outside the verify claim).

Simplifications: none registered. Candidate (no comparison run): compute the idempotency fingerprint on the server
from the payload it applies; it removes the "meta fingerprint equals the applied changeset" premise from every
admission claim and the duplicated canonicalisation contract; tradeoff: ObjectScript canonical JSON must match Python's
for keys already bound (one-time conflict risk for in-flight retries).

Investigated, not registered: the NKG dirty marker (`_mark_nkg_dirty_if_needed`) never fires on this driver because the
Native API answers `None` for an absent `^NKG("$meta","nodeCount")` (observed); the consequence (a missing
`pending_sync`/var-length warning when `^NKG` was never built) is not established. `IRISSQLStore.execute_sql` ignores
its `read_only` argument; no caller passes it.

## 8. Gates (raw outputs in [gates/](gates/); baseline outputs in `$G5_RUN_STATE/baseline-checks/`)

| Gate | Baseline (01e8ccba) | After |
|---|---|---|
| `check_evidence.py` | 32 problems (adjacency_maint, bolt_tx stale) | **FRESH, exit 0** (all inherited problems resolved by reruns; new models fresh) |
| `check_consolidated.py` | 4 failures | **PASS** |
| findings checker | 277 problems | **No problems found** |
| `check_ontology.py` | 0 issues, 17 warnings | 0 issues, 17 warnings |
| correspondence | STALE_ALL vs iteration-58 capture (cloud Verus paths) | new capture [correspondence-inputs.json](correspondence-inputs.json) with **local** Verus paths; check REUSABLE_INPUTS; delta from 58 in [gates/correspondence-check-vs-58.json](gates/correspondence-check-vs-58.json) |

## 9. Residual queue for this family (first missing step each)

1. Node deletion mode and two-graph node scope at verify (A6, I6, L2): owner now states the mode; first missing step is
   a `ledger_apply` delete-node/detach operation and a verify case with one ID in two graphs (q-led-004 decides intent).
2. `enable()`'s own head-lock wait (D14): no observation of `enable` timing out behind a caller transaction.
3. Transport failure after the server committed (B4): first step a fault-injected disconnect between `Commit` and the
   answer, then the next keyed retry's outcome.
4. Provider refusal premise (D13): `ledger_apply` assumes successful SQL; a trigger-refused insert on a disposable
   namespace would bind the refusal path.
5. Concurrent verify (I7, q-led-006): needs an explicit interleaving model of verify's record read and table read.
6. Correlation-index build state and `history(correlation_id=...)` (L4): install-area decision; first step an owner
   statement for "declared but unbuilt index" and a disposable-namespace probe.
7. Snapshot and upgrade survival of the ledger (L5, L6): destructive; disposable namespace needed (migrations queue).
8. NKG dirty marker (L8): first step establish what reads `_nkg_dirty`/`pending_sync` when `^NKG` was never built.
9. Server-side fingerprint (simplification candidate): a comparison run would add a `meta_fp` input to `ledger_client`.

## 10. Step 5 challenge and recommendation (outside the ledger family)

Challenged Q3 (store protocol / `iris_sql_store.py`): `store_protocol.py`'s 45 members are a `typing.Protocol` of 44
`...` declarations — no behavior to bind, so adding locators there would inflate reach without a decision; classify them
as declaration-only (recorded in [master-inventory](../master-inventory.md) row 12b). The material Q3 decisions are in
`IRISSQLStore` (DML detection `_stmt_is_dml`, `execute_transaction`, namespace check). `execute_sql`'s `read_only` flag is
never read, but no caller passes it, so it is a latent API hazard, not a reachable defect.

**Recommended next gap: Q2, the native Cypher executor and its gates (`Exec.cls`/`Gen.cls`, 93 members, 19 reached,
7 active) with the `test_253_native_*` unit family.** It is the strongest remaining match for this run's test-obligation
procedure (a large, mostly unit-runnable test family; consequential read answers on every query the native gate
admits), and the formal side has no claim deciding which queries the native path admits versus falls back and whether
both paths give the same rows. First missing step: recover the `test_253_native_*` obligations (gate admission,
fallback triggers, shadow comparison) and freeze native-vs-SQL row predictions for value types, ordering and OPTIONAL
nulls before reading `Exec.cls`; then model the gate decision with the reader being `execute_cypher().rows` on both paths.

## Limitations

- Integration/e2e ledger tests were not executed (destructive fixtures); their obligations are matched by this
  iteration's own native observations where listed, not by test runs.
- The reader sub-agents' per-test tables were spot-checked, not re-read line by line; claims used for owner text,
  findings or models were re-read in source and observed natively.
- Bindings use unverified Python transcriptions of the spec functions; ObjectScript bodies are executed, not proved.
- The redaction exception, marked replay statements and statement-ID mismatches were not forged natively.
- No independent review has run on this batch yet.

## Repair after review 60 (round 1)

The independent review (`$G5_RUN_STATE/review-60/REVIEW.md`, CONDITIONAL) found four material defects in this batch;
all were reproduced natively and repaired: see [repair/DISPOSITIONS.md](repair/DISPOSITIONS.md). In short: verify's two
temporal-marker rules (bug-led-013, Medium; `ledger_verify` now 15 verified / 12 controls, the unconditional adoption
theorem withdrawn and narrowed), the counter row a caller's transaction holds (bug-led-014; the iteration-60
`theorem_caller_transaction_holds_the_head` asserted lock + 1, now + 0), field limits refused as `inconsistent`
(bug-led-015), the ledger's `NodeNotFoundError` vs the documented root class (bug-led-016; map row C4 was wrong), D10
partial, 24 declaration-only classes relabelled `cites` (recount union 1007, active 772). Sections 3, 5, 7 and 9 above
are the iteration-60 state; the repair's figures supersede them where they differ.
