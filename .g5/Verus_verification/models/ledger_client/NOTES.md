# Ledger client, admission outcomes, caller transactions and readers

Product: `3eaa79cf77d3e0a879b2cced634cf2729d81499e`. Owners: `ledger.changeset`, `ledger.commit`, `ledger.commit.admission`,
`ledger.commit.expected-head`, `ledger.commit.size`, `ledger.commit.caller-transaction`, `ledger.idempotency`,
`ledger.lifecycle`, `ledger.readers`, `ledger.immutability`, `ledger.observability`. Added in iteration 60 from the
test-obligation map (`../../../uplift/consolidated/iteration-60/test-obligations.md`).
As-built transcription, **34 verified / 33 controls** after repair 2 (`run_verus.py prove|controls` on this directory;
final receipts `results/ledger_client/20261117T221544Z-prove` and `20261117T2215*/2216*-control-*`; the first repair's
`20261117T212536Z-prove` (30 / 28) and the iteration-60 `20261117T195357Z-prove` with their controls are kept as history).

## What repair 2 changed (round-1 validation, case V3)

- **A refused nested commit is never counted (model correction).** `txn_commit` counted a nested refusal until the
  caller's transaction ended. Natively the count is +0 at once: when `_commit` raises, the client's `write_txn` takes
  back IVG's level (`WriteTxn.__exit__` -> `rollback` -> `Txn_Undo`), and that level holds the Bump. The row lock the
  Bump took stays. `txn_commit` now restores `cnt` when the nested commit raises and decides `took_row` before that undo.
  **Withdrawn:** the repair's definition (a nested refusal's count kept until the caller's transaction ends); no proved
  claim relied on it. **New:** `theorem_nested_refusal_is_never_counted` (control `nested-refusal-counted`).
- **The counter row held without the head (bug-led-017).** `theorem_nested_lock_timeout_keeps_the_counter_row`: X holds
  the head with a plain lock; caller p's nested commit times out, is not counted, and keeps the counter row; once X lets
  go, q's valid commit is refused `inconsistent` with nothing written; after p's rollback it commits; the same refusal
  with no caller transaction is counted and holds nothing (controls `nested-refusal-counted`, `nested-refusal-frees-row`,
  `held-row-not-checked`). `theorem_held_counter_row_refuses_a_valid_commit` states the refusal whoever holds the row,
  with the free-row neighbour (control `held-row-not-checked`, which also fails `theorem_uncounted_outcomes`).
- **In-process counter-row saves.** `Via::{CallerConn, OwnConn}` (write_routing's `native_proc`) and
  `row_save(s, p, via, level, count)`: the strict guard's `Ledger.Count` and verify's `RecordVerify` reach the counter
  row through `engine._iris_obj()`, which is the caller's own process for an engine built on the caller's connection.
  `theorem_in_transaction_row_save_blocks_other_writers`: at level above 0 the save holds the row, q's valid commit is
  refused, the caller's rollback takes the strict count back and frees the row; at level 0 or on the engine's own
  connection the save commits at once and q commits (controls `in-transaction-save-commits-at-once`,
  `save-held-at-level-0`, `held-row-not-checked`).

## What the repair changed (review 60 FE-3, FE-4, FE-5, FE-6)

- **The counter row (FE-3).** The iteration-60 model claimed that a commit timing out behind a caller's transaction is
  counted (`rej_lock_timeout + 1`); natively it is not. A counted outcome saves the single `ledger_stats` row
  (`WriteRevision`'s `CommitsOk`, or `LedgerStats.Bump` after the commit's own level); inside a caller's transaction
  that row stays locked until the transaction ends, so another process's `Bump` waits about 10 s on the row, fails and
  is lost (observed: the competing commit fails after 40 s, not 30, with `rej_lock_timeout` +0; a `Ledger.Count` call
  in that window waits 10 s and moves nothing). The model now has `stats_holder`/`stats_base`, `stats_free`, a
  `refuse(s, w, p)` that counts only when the row is free, and `txn_commit` taking the row only on a counted outcome.
  `theorem_caller_transaction_holds_the_head` is **corrected** (the lock-timeout is not counted; after the rollback the
  counters are the caller's starting ones plus the competing commit). **Withdrawn:** the iteration-60 conclusions
  `o2.srv.cnt == lock + 1` and `o3.srv.cnt.lock == s.cnt.lock + 1`. **New:**
  `theorem_uncounted_nested_refusal_leaves_the_counter_row` (an uncounted nested refusal holds the head but not the
  row: the competing commit fails after 30 s and IS counted, and the count survives the rollback).
- **Uncounted outcomes (FE-4).** `theorem_uncounted_outcomes`: a redaction-blocked commit (`Apply.blocked` while
  `redacting`, decided by ledger_redaction), a revision row that does not fit its columns (`inconsistent`), and
  `not_enabled` move no counter; while another transaction holds the row no outcome of this process is counted, and the
  strict guard's `count_strict` is lost.
- **Revision-row field limits (FE-5).** `Cs.lens` and `fits` (LedgerRevision MAXLEN: message and source 4000; actor,
  correlation ID and idempotency key 256; actor type 32). A changeset that does not fit is applied, then refused as
  `inconsistent` when the revision row is saved, so nothing is written and nothing is counted;
  `theorem_field_limits_checked_after_the_key` shows a keyed retry with an over-long message still replays.
  `Code::Inconsistent` now has this deterministic producer as well as transport failure.
- **Readers (FE-6).** `seq_read` refuses an unfinished redaction (`RedactionInProgressError`) before looking the ID up;
  `theorem_revision_readers_resolve_ids` states both.

## Why this model

The inherited admission model (`ledger_redaction` `commit_outcome`) takes the idempotency binding, the fingerprint
match and "head known" as inputs, and no model covered the client: what the fingerprint hashes, what the client refuses
before sending, how a wire code becomes the exception a caller catches, which counter and hook event each outcome
produces, what a caller's transaction does to the head lock and to an idempotency key, or what the revision-ID readers
do with an unknown ID. `ledger_client` derives those outcomes from the ledger's own state (`idem`, `seq_of`, `id_of`,
`holder`, `state`, `max_ops`) and the changeset (`scope`, `ops`, `key`, `expected`).

## Claims (L1 → theorem) and the wrong outcome each control shows is excluded

| Claim | Theorem | Control (must fail) |
|---|---|---|
| Message, correlation ID, expected head and key are outside the fingerprint | `theorem_metadata_outside_fingerprint` | `message-fingerprinted` |
| Actor, actor type and the ordered operations decide it (collision-free hash premise) | `theorem_scope_decides_fingerprint` | — (premise-level) |
| A keyed retry with new metadata and any expected head replays, writes nothing, counts a replay | `theorem_retry_with_new_metadata_replays` | `message-fingerprinted`, `expected-head-before-idempotency`, `replay-counted-as-commit` |
| The same key with reordered operations is a conflict | `theorem_reordered_operations_conflict` | `ops-not-fingerprinted` |
| A replay returns no statement IDs (bug-led-003) | `witness_replay_returns_no_statement_ids` | — (as-built witness) |
| Every refusal leaves head, revisions, parents, bindings and content unchanged | `theorem_refusal_writes_nothing` | `key-bound-on-refusal` |
| A key used only by a refused commit stays free | `theorem_refused_key_stays_free` | `key-bound-on-refusal`, `stale-names-expected` |
| Stale vs unknown expected head: different classes, current head named, own counters | `theorem_expected_head_outcomes` | `unknown-as-stale`, `stale-names-expected` |
| Never enabled vs disabled: different classes; only disabled is counted | `theorem_disabled_and_never_enabled` | `never-counted-as-disabled` |
| Empty changeset refused before the server in every state: no change, counter, event or lock | `theorem_empty_refused_before_the_server` | `no-client-validate` |
| Size limit inclusive; one over is refused with the limit attached | `theorem_size_limit_boundary` | `size-limit-exclusive` |
| A failing op is reported by position; node_not_found narrows to NodeNotFoundError (still an operation error) | `theorem_failed_operation_reported`, `theorem_error_mapping_fallbacks` | `no-node-narrowing`, `op-index-lost` |
| A caller's transaction holds the head and the counter row: another commit times out, changes nothing and is not counted; after rollback it gets the next seq with the kept parent; after the caller's commit it builds on the caller's revision | `theorem_caller_transaction_holds_the_head` | `lock-released-inside-transaction`, `stats-row-not-held`, `bump-ignores-held-row` |
| An uncounted nested refusal holds the head but not the counter row: the competing lock-timeout is counted and survives the rollback | `theorem_uncounted_nested_refusal_leaves_the_counter_row` | `uncounted-refusal-holds-row`, `field-limits-unchecked` |
| Uncounted outcomes: redaction-blocked, field limits (`inconsistent`), not_enabled; nothing counted while another transaction holds the row; the strict count call is lost then | `theorem_uncounted_outcomes` | `redaction-block-counted`, `field-limits-unchecked`, `bump-ignores-held-row` |
| The field limits are met only when a revision row is written: a keyed retry with an over-long message replays; the same changeset unkeyed is `inconsistent` | `theorem_field_limits_checked_after_the_key` | `field-limits-before-key`, `field-limits-unchecked` |
| A caller's rollback frees the key and the seq | `theorem_rollback_frees_key_and_seq` | `idem-not-journaled` |
| Revision readers refuse an unfinished redaction first (any ID), then resolve the ID; unknown → UnknownRevisionError before any read or file | `theorem_revision_readers_resolve_ids` | `unknown-id-reads-genesis`, `lookup-before-redaction-check` |
| head() refused only before the first enable | `theorem_head_reader_states` | `head-refused-while-disabled` |
| Enable lifecycle: enabled → unchanged (strict included); re-enable takes strict from the call, keeps bounds; genesis fixes bounds; refused in a caller transaction | `theorem_enable_lifecycle` | `enable-on-enabled-sets-strict` |
| Disable idempotent; set_strict refused only before the first enable; strict set while disabled is reset by enable() | `theorem_disable_and_set_strict`, `witness_strict_set_while_disabled_is_reset_by_enable` | — |
| One hook event per server call, none for a client-side refusal | `theorem_one_event_per_server_call` | `event-on-client-refusal` |
| A text `source` is dropped; an object source matches only its exact stored JSON | `witness_text_source_is_dropped` | `text-source-kept` |
| Revision rows: no delete, no object re-save, update only as the four-field redaction exception | `theorem_revision_rows_immutable` | `update-without-emptying` |
| Staged changesets and answers split into chunks of at most 1,000,000 and join back exactly | `lemma_join_chunks`, `theorem_chunked_transport_roundtrip` | `chunk-off-by-one` |
| A nested commit that raises is never counted (write_txn undoes IVG's level) | `theorem_nested_refusal_is_never_counted` | `nested-refusal-counted` |
| A nested lock-timeout refusal keeps the counter row without the head; another process's valid commit is then refused `inconsistent`, nothing written; after the rollback it commits; with no caller transaction the refusal is counted and the commit goes through | `theorem_nested_lock_timeout_keeps_the_counter_row` | `nested-refusal-counted`, `nested-refusal-frees-row`, `held-row-not-checked` |
| A counter row held by another process's transaction refuses a valid commit once the head is free (bug-led-017); with the row free it writes and counts | `theorem_held_counter_row_refuses_a_valid_commit` | `held-row-not-checked` |
| A strict count or verify record made on the caller's own process inside its open transaction (level above 0) holds the row and refuses other writers until the rollback, which takes the count back; level 0 or the engine's own connection does not | `theorem_in_transaction_row_save_blocks_other_writers` | `in-transaction-save-commits-at-once`, `save-held-at-level-0`, `held-row-not-checked` |

## Source bindings and evidence

Rows in `crosswalk/decision-links.tsv` (family `C-ledger_client`) name the exact members: `Changeset.{_add,validate,
fingerprint,canonical_json,to_wire}`, `canonical_dumps`; `errors.from_commit_error` and the classes a caller catches;
`GraphLedger.{commit,_commit,_send_changeset,_call,_emit,register_metrics_hook,head,_seq_of,get_revision,diff,
reconstruct,export_reconstruction,enable,_refuse_in_caller_transaction,disable,set_strict,stats}`, `CommitResult`,
`_CommitWireResult`, `RevisionInfo`, `Revision`, `LedgerCounters`; `Ledger.cls::{Commit,CommitInTxn,WriteRevision,Err,
ErrLimit,RevisionResponse,Head,SeqOf,State,Enable,Disable,SetStrict,StageChunk,LargeOut,ReadLargeOutChunk,NewId}`;
`LedgerStats.cls::{Bump,PropertyFor,Ensure}`; `LedgerRevision.cls::{RejectUpdate,RejectDelete,%OnBeforeSave,%OnDelete}`. Repair 2 adds `_write_txn.py` `caller_transaction_level`, `WriteTxn.{rollback,__exit__}`, `Txn.cls::Undo`, `Ledger.cls::{RecordVerify,Count}`, `guard.py` `LedgerGuard.{check_structural_write,count_rejection}`, `engine.py` `IRISGraphEngine._iris_obj` and `replay.py` `verify` (the in-process counter-row paths and the nested-level undo).

`binding.py` (run with `.g5/uplift/consolidated/local-runtime/run_binding.py`) drives the actual product on the local
fixture `ivg-uplift-next-20261115`. **Repair-2 run** ([receipt](../../results/ledger_client/20261117T225756Z-binding/receipt.json),
namespaces `I60SB` (with the application table `SQLUser.i60s_app`), `I60SC` with `max_ops=2`, `I60SE` never enabled;
log `iteration-60/repair2/probes/ledger_client-binding-run1.log`): **58 native cases AGREE**, 32 of 33
control-equivalent mutations detected (`update-without-emptying` not natively exercisable, as before), a changed
observation caught. New cases: B21 (X's Native API lock on the head; A's nested commit times out after 30.1 s, +0; B's
valid commit `inconsistent` after 10.1 s, nothing written; after A's rollback B commits with the prior head as parent),
B21n (no caller transaction: +1, B commits at once), B22/B22z (strict refusal after / before the caller's first write:
B refused after 10.1 s and the strict count taken back by the rollback / B commits at once and the count is kept),
B23/B23z (the same for `verify()`). **Repair run** ([receipt](../../results/ledger_client/20261117T212518Z-binding/receipt.json),
namespaces `I60RA`, `I60RC` with `max_ops=2`, `I60RE` never enabled): **52 native cases AGREE**, 27 of 28
control-equivalent mutations detected, a changed observation caught. New cases: B8 now records the counter deltas read
from a third connection (lock +0 while the caller is open and after its rollback; the competing commit waited 40.0 s),
B8b (an uncounted nested refusal: 30.0 s and lock +1, surviving the rollback), B8c (the strict guard's `Ledger.Count`
waits 10.0 s and is lost, then +1), B18 (a redaction-blocked commit: one `redaction_in_progress` event, no counter,
nothing written; a neighbour outside the target commits), B19 (all four revision-ID readers raise
`RedactionInProgressError` for an unknown ID while the redaction is unfinished, `UnknownRevisionError` after), B20
(message 4,000 commits; message 5,000, key 300, correlation ID 300, actor 300 and a 4,100-character object source are
`LedgerInconsistencyError` with one `inconsistent` event, no counter and nothing written; a keyed retry with a
5,000-character message replays). Wall times are recorded in the receipt, not compared (the model has no time). Two
earlier repair runs are kept: run 1 crashed in its redaction setup (one batch of size 1 scanned no target record, so
no redaction was left unfinished; log `iteration-60/repair/probes/ledger_client-binding-run1-crashed.log`), run 2
(`20261117T212337Z-binding`) DISAGREED on one vacuous flag (a node-only replay has no statement IDs either way).
**Iteration-60 run** (namespaces `I60LA`, `I60LC`, `I60LE`): **35 native cases AGREE** with an unverified Python transcription of this file's spec functions fed with the observed pre-state;
20 of 21 control-equivalent mutations of the transcription disagree with an observation; the redaction-context row
update (`update-without-emptying`) is inspected only (the binding does not forge redaction internals). A changed
observation is caught. Receipt: `results/ledger_client/20261117T195905Z-binding/receipt.json` (an earlier run of the
same harness, `20261117T195805Z-binding`, DISAGREED only on detection coverage before the chained B3 case was added; it
is kept). The prediction probe (`iteration-60/probes/`) adds the native observations graded in `PREDICTIONS-graded.md`.

## Premises and limits

- Apply outcome supplied (`Apply`): decided by `ledger_apply`; composition is a premise.
- SHA-256 collision freedom only where `collision_free()` is required; `NewId` GUID freshness (`fresh` not yet a revision).
- The server compares the idempotency binding with the fingerprint the caller puts in `Commit`'s meta JSON (`CommitInTxn` reads `meta.fingerprint`); the model uses `fingerprint(c)` of the applied changeset. That holds for every commit sent by `GraphLedger._send_changeset` (it computes both from the same object); a direct caller of `Graph.KG.Ledger.Commit` can send any value, so its replay/conflict outcome is outside these claims (candidate simplification in the iteration-60 handoff: compute the fingerprint on the server).
- Caller rollback undoes every journaled write of its transaction, its counter changes included (back to `stats_base`,
  the counters when it took the row). `txn_rollback` restores the ledger fields to the before-image: it applies only
  while the caller holds the head or the counter row, so no other process could have written meanwhile (a caller
  holding neither has no ledger effect to take back). The stall-and-lose behaviour of another process's counter save is
  observed for `Bump` and `Count` and inferred for `RecordVerify`; a commit whose counter row another transaction holds
  while the head is free (`server`'s `!stats_free` branch, `inconsistent`) is observed in repair 2 (B21, B22, B23).
- The caller's `$TLEVEL` is an input to `row_save` (`level`), taken from write_routing's provider premise: 0 with the
  driver's autocommit off until the caller's first write (observed: B22z, B23z). `Via` is decided by
  `engine._iris_obj()` (an engine with connection parameters, `from_connect`, uses its own connection; not run here).
  `disable()` and `set_strict()` also save the counter row on the caller's process and are not refused inside a
  caller's transaction; not modelled or observed.
- Not modelled: whether a commit's records touch a redaction target (`Apply.blocked`, decided in ledger_redaction;
  `IdempotencyRedactedError` is mapped but not observed natively),
  the strict-mode guard (model `platform`), post-commit properties (`ledger_apply`/`ledger_content` scope and
  bug-led-003/009), auto-stub position shifts (owner text only), transport exceptions mapped to `inconsistent`
  (inspected), and the NKG dirty marker (candidate in the iteration-60 handoff).
- Direct executable-body proofs: **0**. This is a transcription with native agreement on the listed cases.

Trust inventory: bundled pinned `vstd`; one `uninterp` hash (`sha256`); no assume/admit/external_body.
