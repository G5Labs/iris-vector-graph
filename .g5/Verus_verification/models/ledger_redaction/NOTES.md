# ledger_redaction — notes

Model of ledger commit admission, erasure scope, the redaction lifecycle and replay/verify, at product baseline `3eaa79cf`. Root: [redaction.rs](redaction.rs); executable twin: [twin.rs](twin.rs); expected count and controls: [model.json](model.json) (41 verified; 16 controls, each with the functions that must fail). Latest receipts: [prove](../../results/ledger_redaction/20261114T044401Z-prove/receipt.json), controls `results/ledger_redaction/20261114T0445*/0446*-control-* (4 threads)`, [twin build](../../results/ledger_redaction/20261114T043140Z-twin/receipt.json) (51 verified). Every claim's status, source and native evidence is in the [coverage map](../../coverage.md#ledger-erasure-and-redaction); this file only orients a reader in the model.

## Obligations (L1) and where they are proved

| Area | Results |
|---|---|
| Target matching (separator, no doubling) | `lemma_match_string_has_separator_boundary`, `lemma_match_string_not_doubled`, `lemma_acme_does_not_select_acme_health`; twin `exec_match_string`, `exec_matches` |
| Tombstone in place, frame for every other record | `lemma_frame_and_tombstone`, `lemma_shape_kept`, `lemma_tomb_never_matches`, `theorem_step_frame` |
| Batches within one call | `lemma_batches_compose`, `lemma_rescan_is_harmless`, `lemma_complete_scan_leaves_no_match` (one fixed knowledge `K()`) |
| Lifecycle invariant and completion (serialised redactions) | `inv`, `lemma_init_establishes_inv`, `lemma_step_preserves_inv`, `theorem_completion`, `lemma_complete_run_removes_every_target_record` (premise P_ends) |
| Commit admission (lock → state → idempotency → redacted key → expected head → size → apply → BlocksCommit) | `theorem_retry_replays_first`, `theorem_redacted_key_refused_before_apply`, `theorem_commit_writes_only_when_admitted`, `lemma_commit_admits_matches_outcome`, `theorem_redacted_key_refused` |
| Replay and verify | `theorem_replay_skips_target`, `theorem_replay_independence`, `theorem_verify_equal_after_redaction` (no unrecorded writes) |
| Erase frame | `lemma_erase_stays_in_target_graph`, `lemma_erase_keeps_other_graphs` |

## As-built witnesses (L2 violates L1)

W1 `witness_concurrent_targets_break_the_marker` (bug-001; repair `witness_repair_refuses_the_interleaving`); W2 `witness_temporal_only_content_is_not_seen` (q-009); W3 `witness_default_graph_target_is_not_graph_blind` (bug-003); W4 `witness_unattributed_qualifier_survives` (bug-004); W5 `witness_prefix_erase_leaves_temporal_only_content` (bug-led-007); W6 `witness_orphan_prop_row_blocks_prefix_redaction` (bug-led-010); `witness_without_blockscommit` (why BlocksCommit is needed); `witness_full_check_refuses_the_gaps` (simp-003 proposal); valid outcome `witness_erase_then_redact_completes`.

`lemma_serial_resume_keeps_attribution` and `witness_race_then_resume_loses_attribution` are classification facts about `matches` under a given knowledge. The lifecycle uses one constant knowledge `K()`, so resume across calls is not proved; it is observed natively (`redaction_interrupt_resume`, `redaction_prefix_resume`).

## Bindings (L2 → product)

`Start`/`Batch`/`Final` ↔ `LedgerRedact.Redact`, `BatchInLock`, `FinalInLock`; `checked` ↔ `LedgerRedact.LiveRows`; `matches`/`match_string` ↔ `LedgerRedact.Matches`/`MatchString`; `commit_admits` ↔ `Ledger.CommitInTxn` with `LedgerRedact.BlocksCommit`; `Erase`/`erased_in` ↔ `Eraser.EraseGraph`, `EraseNodes` (ids from node rows) and `TemporalIndex.EraseNodes`; `replay`/`keep` ↔ `ledger/replay.py`. Native binding: [redaction_binding](../../native/probes/redaction_binding.py) classifies real ledger records with the twin.

## Premises and trust

Serialised redactions (except in W1); the head lock is exclusive and held to transaction end; IRIS transactions undo SQL and journaled globals together; P_ends (an attributable record's endpoints are known); no unrecorded writes for the verify theorem. Uninterpreted spec functions `digest_of`, `upd`, `K()` (no axioms). The twin's line adapter (`main`, `unhex`) and the probe's own attribution are unverified. No `assume`, `admit` or `external_body`.

## Not modelled

`FinalInLock`'s `DropStatements` and its audit-without-marker branch; per-call statement knowledge; uncommitted state (bug-002 is native only); post-commit properties (bug-led-009, q-010); receipt fields; readers (`redaction.batches.readers`).

## Latest receipts (checked in iteration 64)

The latest prove receipt, as `tools/census.py` resolves it, is [20261116T160746Z-prove](../../results/ledger_redaction/20261116T160746Z-prove/receipt.json) (41 verified, as the 20261114T044401Z receipt named above); the latest receipt for each of the 16 named controls is the newest `results/ledger_redaction/*-control-<name>`.
