# Ledger client, admission outcomes, caller transactions and readers

Product: `3eaa79cf77d3e0a879b2cced634cf2729d81499e`. Owners: `ledger.changeset`, `ledger.commit`, `ledger.commit.admission`,
`ledger.commit.expected-head`, `ledger.commit.size`, `ledger.commit.caller-transaction`, `ledger.idempotency`,
`ledger.lifecycle`, `ledger.readers`, `ledger.immutability`, `ledger.observability`. Added in iteration 60 from the
test-obligation map (`../../../uplift/consolidated/iteration-60/test-obligations.md`).
As-built transcription, **27 verified / 21 controls** (`run_verus.py prove|controls` on this directory; receipts under
`results/ledger_client/`, final ones `20261117T195357Z-prove` and `20261117T1953*/1954*-control-*`).

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
| A caller's transaction holds the head: another commit times out and changes nothing; after rollback it gets the next seq with the kept parent; after the caller's commit it builds on the caller's revision | `theorem_caller_transaction_holds_the_head` | `lock-released-inside-transaction` |
| A caller's rollback frees the key and the seq | `theorem_rollback_frees_key_and_seq` | `idem-not-journaled` |
| Revision readers resolve the ID first; unknown → UnknownRevisionError before any read or file | `theorem_revision_readers_resolve_ids` | `unknown-id-reads-genesis` |
| head() refused only before the first enable | `theorem_head_reader_states` | `head-refused-while-disabled` |
| Enable lifecycle: enabled → unchanged (strict included); re-enable takes strict from the call, keeps bounds; genesis fixes bounds; refused in a caller transaction | `theorem_enable_lifecycle` | `enable-on-enabled-sets-strict` |
| Disable idempotent; set_strict refused only before the first enable; strict set while disabled is reset by enable() | `theorem_disable_and_set_strict`, `witness_strict_set_while_disabled_is_reset_by_enable` | — |
| One hook event per server call, none for a client-side refusal | `theorem_one_event_per_server_call` | `event-on-client-refusal` |
| A text `source` is dropped; an object source matches only its exact stored JSON | `witness_text_source_is_dropped` | `text-source-kept` |
| Revision rows: no delete, no object re-save, update only as the four-field redaction exception | `theorem_revision_rows_immutable` | `update-without-emptying` |
| Staged changesets and answers split into chunks of at most 1,000,000 and join back exactly | `lemma_join_chunks`, `theorem_chunked_transport_roundtrip` | `chunk-off-by-one` |

## Source bindings and evidence

Rows in `crosswalk/decision-links.tsv` (family `C-ledger_client`) name the exact members: `Changeset.{_add,validate,
fingerprint,canonical_json,to_wire}`, `canonical_dumps`; `errors.from_commit_error` and the classes a caller catches;
`GraphLedger.{commit,_commit,_send_changeset,_call,_emit,register_metrics_hook,head,_seq_of,get_revision,diff,
reconstruct,export_reconstruction,enable,_refuse_in_caller_transaction,disable,set_strict,stats}`, `CommitResult`,
`_CommitWireResult`, `RevisionInfo`, `Revision`, `LedgerCounters`; `Ledger.cls::{Commit,CommitInTxn,WriteRevision,Err,
ErrLimit,RevisionResponse,Head,SeqOf,State,Enable,Disable,SetStrict,StageChunk,LargeOut,ReadLargeOutChunk,NewId}`;
`LedgerStats.cls::{Bump,PropertyFor,Ensure}`; `LedgerRevision.cls::{RejectUpdate,RejectDelete,%OnBeforeSave,%OnDelete}`.

`binding.py` (run with `.g5/uplift/consolidated/local-runtime/run_binding.py`) drives the actual product on the local
fixture `ivg-uplift-next-20261115` (namespaces `I60LA`, `I60LC` with `max_ops=2`, `I60LE` never enabled): **35 native
cases AGREE** with an unverified Python transcription of this file's spec functions fed with the observed pre-state;
20 of 21 control-equivalent mutations of the transcription disagree with an observation; the redaction-context row
update (`update-without-emptying`) is inspected only (the binding does not forge redaction internals). A changed
observation is caught. Receipt: `results/ledger_client/20261117T195905Z-binding/receipt.json` (an earlier run of the
same harness, `20261117T195805Z-binding`, DISAGREED only on detection coverage before the chained B3 case was added; it
is kept). The prediction probe (`iteration-60/probes/`) adds the native observations graded in `PREDICTIONS-graded.md`.

## Premises and limits

- Apply outcome supplied (`Apply`): decided by `ledger_apply`; composition is a premise.
- SHA-256 collision freedom only where `collision_free()` is required; `NewId` GUID freshness (`fresh` not yet a revision).
- The server compares the idempotency binding with the fingerprint the caller puts in `Commit`'s meta JSON (`CommitInTxn` reads `meta.fingerprint`); the model uses `fingerprint(c)` of the applied changeset. That holds for every commit sent by `GraphLedger._send_changeset` (it computes both from the same object); a direct caller of `Graph.KG.Ledger.Commit` can send any value, so its replay/conflict outcome is outside these claims (candidate simplification in the iteration-60 handoff: compute the fingerprint on the server).
- Caller rollback undoes every journaled write of its transaction; while it holds the head the only counters others
  move are their own lock-timeout rejections. Counters after a rollback that interleaves other refusals are not claimed.
- Not modelled: the redaction marker (`BlocksCommit`, `IdempotencyRedactedError` is mapped but not observed natively),
  the strict-mode guard (model `platform`), post-commit properties (`ledger_apply`/`ledger_content` scope and
  bug-led-003/009), auto-stub position shifts (owner text only), transport exceptions mapped to `inconsistent`
  (inspected), and the NKG dirty marker (candidate in the iteration-60 handoff).
- Direct executable-body proofs: **0**. This is a transcription with native agreement on the listed cases.

Trust inventory: bundled pinned `vstd`; one `uninterp` hash (`sha256`); no assume/admit/external_body.
