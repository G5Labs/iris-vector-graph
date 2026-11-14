# Temporal edges — Verus model notes (worker B-temporal; 2026-11-13; review rounds 1 and 2 on 2026-11-14)

Product baseline `3eaa79cf`. The model is `temporal.rs` (root) with controls in `model.json`. Intent notes are in
`.g5/uplift/ivg-verus-initial/intent/temporal.md` (O1–O6, F1–F12). The review is
`.g5/uplift/ivg-verus-initial/review/round1-data.md` (R1-7, R1-9 and R1-12 are addressed here) and
`.g5/uplift/ivg-verus-initial/review/round2-domains.md` (R2-2, R2-3 and R2-4 are addressed here). Every premise below was
re-read at its producer in the code. Line numbers are at the pin.

## Run results (receipts)

| What | Result | Receipt |
|---|---|---|
| prove (round 2) | PASS: 113 verified, 0 errors | `.g5/Verus_verification/results/temporal/20261114T040433Z-prove/receipt.json` |
| controls (33, round 2) | all 33 EXPECTED_FAIL | `.g5/Verus_verification/results/temporal/20261114T040447Z-control-no-collision-guard/receipt.json` … `20261114T041017Z-control-kill-no-reretract/receipt.json` |
| failed attempt kept (round 2) | `decide-rows-only` FAIL_ELSEWHERE | `.g5/Verus_verification/results/temporal/20261114T040331Z-control-decide-rows-only/receipt.json` (round-2 attempt 1; superseded) |
| prove (round 1, superseded) | PASS: 104 verified, 0 errors | `.g5/Verus_verification/results/temporal/20261114T001508Z-prove/receipt.json` |
| controls (29, round 1, superseded) | all 29 EXPECTED_FAIL | `.g5/Verus_verification/results/temporal/20261114T001520Z-control-no-collision-guard/receipt.json` … `20261114T001954Z-control-rebuild-not-journaled/receipt.json` |
| failed attempt kept (round 1) | `rebuild-not-journaled` FAIL_ELSEWHERE | `.g5/Verus_verification/results/temporal/20261114T001431Z-control-rebuild-not-journaled/receipt.json` |
| round 0 (superseded) | PASS: 75 verified; 25 controls EXPECTED_FAIL | `.g5/Verus_verification/receipts/temporal/20261113T232106Z-prove.json` and `…T2321*-T2323*` |
| failed attempt kept (round 0) | `write-ignores-registry` FAIL_ELSEWHERE | `.g5/Verus_verification/receipts/temporal/20261113T231448Z-control-write-ignores-registry.json` |

Both FAIL_ELSEWHERE runs had the same cause, and neither weakened a property. The control named a function that
consumes the mutated function's postcondition, which is trusted when the caller is verified alone. The caller then
verifies vacuously, and the failure lands correctly in the shape lemma.

* Round 0: I corrected the control's expectation.
* Round 1: I rewrote `witness_rolled_back_delete_undercounts` so that it no longer calls
  `lemma_remove_temporal_row_shape`. It now stands on the definitions alone and detects the mutation; I checked this
  on a scratch copy before re-running.

Toolchain: Verus `0.2026.10.04.426d8b0`, bundled vstd, `--num-threads 4`. Native observations (round 0 probes, run
by the orchestrator) are kept at `.g5/Verus_verification/receipts/native/temporal_*.json`.

## What changed in round 2

* **R2-2: the purge decision is now product-faithful.** `doomed_set` is the whole `^||IVG.TPurge` after the
  survivor walk (TemporalIndex.cls:956-1013). That is every triple of a structural predicate with a timestamp in the
  range and none outside it, whether or not it has a row when the purge decides. `RetractTemporalRows` tests the
  marker only when its DELETE runs (Adjacency.cls:674).
  * `lemma_doomed_set_iff` binds the set to `purge_candidate`.
  * `lemma_phased_purge_serial` still proves that the serial phased purge equals the atomic one.
  * Every round 1 obligation still holds.
  * New witness `witness_purge_write_race_rowless_route` (W-RACE-4). It starts from a reachable rowless triple
    (`s_rowless`: written while opted out, then opted back in, which is ADR-0015's gap; F2's throw is the other way
    there).
    1. The purge decides.
    2. A write at ts 1200 finds no row and asserts one.
    3. The retraction deletes it.

    The result is a live timestamp with no row: `!fwd_ok`.
  * New witness `witness_purge_write_race_strands_new_triple` (W-RACE-5). A back-dated ingest of a triple the purge
    never decided on lands inside the range after the retraction, asserts its marked row, and loses its only
    timestamp to the kill loop: `!rows_ok`.
  * **bug-tmp-011's repair is now modelled** as the variant `race_recheck` (`raced()`). The retraction re-tests "no
    surviving timestamp" when it runs, and the kill loop re-retracts every structural triple whose timestamps it
    removed and that it left without one. Each step is atomic with respect to a writer of the triple (premise
    P-LOCK: a per-triple lock that AssertTemporalRow also takes; proposed, not in the product).
  * Every race route is closed in a witness:
    * `witness_recheck_closes_race_row_at_decide`
    * `witness_recheck_closes_race_rowless_route`
    * `witness_recheck_closes_delete_race`
    * `witness_recheck_closes_kill_window` (RACE-2 and RACE-5)
  * These are witnesses, not an all-interleavings theorem: the repair is not proved for every schedule.
  * Controls `decide-rows-only`, `retract-no-recheck` and `kill-no-reretract`.
* **R2-4: L1-AGG now tells a zero counter from an absent one.** `exact` requires a bucket or tagg-count key with no
  raw edge to be absent. Reason: "A zero counter is not neutral" (TemporalIndex.cls:355-357), and FindBursts lists
  every source present in a bucket (:784-803).
  * Every statistics lemma proves the presence conjuncts.
  * `lemma_delete_exact` now derives the counter step from `remove_raw`'s definition instead of the shape lemma.
    The reviewer's faulty "keep zero counters" implementation (control `zero-counter-kept`) therefore fails the L1
    obligation itself, not only a witness.
  * Native R5 and R6 left exactly such a node (raw bucket 0).
* **R2-3: statuses refreshed.** The R5, R5b and R6 rows (O6 and Candidate findings) are now OBSERVED from the final
  native battery. Upstream suites that were run in this uplift (`$RUN_DIR/tests/cited/summary.txt`, all
  exit 0) are listed below.

  | Suite | Passed |
  |---|---|
  | test_254_collisions_e2e | 10 |
  | test_254_rebuild_e2e | 3 |
  | test_254_purge_e2e | 22 |
  | test_252_temporal_rows_e2e | 7 |
  | test_temporal_structural_optout_e2e | 26 |
  | test_temporal_bare_nodes_e2e | 27 |
  | test_ledger_us11_temporal_coexist | 6 |
  | test_224_temporal_changeset_e2e | 4 |
  | test_460_ledger_temporal_edge_e2e | 2 |
  | test_delete_temporal_edge | 15 |
  | test_223_temporal_graph_scope | 8 |
  | test_255_window_reader_us1/us2/us3 | 19/6/14 |
  | test_460_r217_temporal_aggregate_window_e2e | 6 |

  These pass while bugs F1–F8 hold. That agrees with the earlier analysis: the suites do not drive update-mode
  aggregates, a throw in AssertTemporalRow, rollbacks after a temporal op, or new endpoint ids under the ledger.

## What changed in round 1

* **R1-7.**
  * The forward rule of ADR-0009 is now an L1 property, `fwd_ok`, with enumerated exceptions. It is backed by
    `theorem_fwd_as_built`, `theorem_fwd_assert_first_writes` and `lemma_backfill_restores_fwd`.
  * The purge and the temporal delete can be split where another process can interleave: the phased actions
    `PurgeDecide`, `DeleteDecide`, `Retract` and `PurgeKill`.
  * They are bound to the atomic steps by `lemma_phased_purge_serial` and `lemma_phased_delete_serial`.
  * The write/purge race is a witness, and so is the write/delete race. The reviewer's Check C race is reproduced,
    and a second, unrecorded purge window strands a marked row.
  * Explicit `delete_edge` of a marked row with live timestamps is now an explicit exception: open question 4 below.
* **R1-9.** TROLLBACK of the `$Increment` counters now follows IRIS journaling. Each transaction level keeps
  before-images of the counter nodes that were Set or Killed in it; nodes that were only `$Increment`'ed keep their
  current value. Delete and Purge are no longer stuttered inside a transaction. New witnesses:
  `witness_rolled_back_delete_undercounts` and `witness_rolled_back_delete_exact_if_counters_undone` (the valid
  outcome).
* **R1-12 and R1-6.** Every probe case records as it runs, so a crash keeps the views, and checks its precondition
  and failure site. A case that cannot show the mechanism is INCONCLUSIVE (see "Native probes"). New probe cases
  R5, R5b and R6 cover R1-9.
* **Statuses.** F1, F2, F2b, F3 (R1–R4), F4 (V1–V5) and F8 are now observed, from the native receipts.

## Layout of the model

* **State `St`** has these fields:
  * `tout`, `eprop`, `bucket` ($Increment), `cnt`/`sum` (tagg count/sum, $Increment), `rows` (rdf_edges, `true` =
    marked), `nodes`, `optout` (^IVG.TemporalStructural), `gov_nodes`/`gov_rels` (ledger replay), and the ghost
    `purged`
  * `txn: Seq<Snap>`, the TSTART stack. Each `Snap` carries the stores at TSTART plus three journals
    (`jbucket`/`jcnt`/`jsum`) of before-images of counter nodes Set or Killed in that level.
  * `plans: Map<int, Plan>`, the purges and deletes in flight per process (process-private and not journaled).
* **Variants:**
  * `as_built()`: the pin.
  * `repaired()`: the structural step first (S2), counters rolled back, update rebuilds (Q1 b), and the opt-in guard
    (Q4).
  * `guarded()`: `as_built` plus the opt-in guard.
* **Steps:**
  * Write, Delete (in or out of a transaction), Purge (complete or stopped after its row step), CreateEdge,
    DeleteEdge, SetStructural, DropRows, Backfill, Begin, End, Rollback, and Commit(ops, blocked)
  * the phased PurgeDecide, DeleteDecide, Retract and PurgeKill

## O1 — write modes and statistics (Q1; F1, F2, F7)

**Governing sources and authority, per mode**

| Mode | Source | Authority | Expected statistics |
|---|---|---|---|
| insert, occupied | spec 254 FR-003 and US2 scenario 1; Decision 2 (Tom, 2026-10-22) | human requirement (secondhand) | no store changes; a collision in bulk |
| insert or skip, free | spec 254 US2 motivation; `RebuildBucketAggregate` "the aggregate describes the surviving edges" | requirement plus observed rule | count, sum and bucket equal the raw edges (L1-AGG) |
| skip, occupied | `BulkInsert` doc; CHANGELOG spec 221 | accepted decision | no store changes |
| update, occupied | spec 254 US2 scenario 2 is silent on aggregates; CHANGELOG 4669-4670, 4914-4915 ("not adjusted"); `WriteStores` doc :77-79 and `temporal.py:273-279` ("original value") | **OPEN (Q1)**; the code contradicts the docs | none settled |
| any, structural step throws | `create_edge_temporal` doc `temporal.py:260-261` ("writes nothing"), which `_temporal_left` `temporal.py:12-17` contradicts; ADR-0009 | contradictory docs; accepted decision | nothing written, or a retry completes the write |

**L1-AGG** (`exact`) and **L1-W** (`lemma_collision_changes_nothing`) are unchanged from round 0.

**L2 → L3 bindings.** WriteStores `TemporalIndex.cls:80-133`:

| Code | Lines |
|---|---|
| guard | :82-86 |
| tout, tin, bucket `$Increment` | :97, :99, :102 |
| structural step → `AssertTemporalRow` | :109-115 → `Adjacency.cls:575-618` |
| tagg `$Increment` | :117-118 |

The other bindings:

| Model or product | Lines |
|---|---|
| `InsertEdge` | :46-65 (returns 1 always, :64) |
| `BulkInsertCounts` | :151-182 |
| `RemoveTemporalRow` | :348-360 (`$Increment(bucket,-1)` :357; Kill at ≤0 :358; `RebuildBucketAggregate` :359 → :455-488) |
| `DeleteTemporalEdge` | :325-345 |
| `PurgeRawBefore` / `RetireExpired` | :866-920 / :944-1046 |
| `bulk_write_temporal_edges` | `iris_sql_store.py:2719-2786` (the fallback at :2759-2785) |

**Proved**

* `theorem_stats_as_built_fragment` holds except for update over an occupied coordinate, a throw, and rollbacks. It
  now includes Delete and Purge inside an open transaction, and the phased steps.
* `theorem_stats_repaired_total`.
* Supporting lemmas: `lemma_write_exact`, `lemma_collision_changes_nothing`, `lemma_delete_exact`,
  `lemma_kill_exact`, `lemma_purge_exact`, `lemma_batch_split`.

**Witnesses**

* `witness_update_double_counts` (F1). After writing w=2 then w=9 there is one raw edge with count 2, sum 11 and
  bucket 2. After deleting it, bucket stays 1 over zero edges.
* `witness_partial_write_is_not_repaired_by_retry` (F2) and `witness_partial_write_breaks_fwd`.
* `witness_bulk_fallback_reports_success` (F2b).
* `witness_concurrent_inserts_double_count` (F7).
* Valid outcomes: `witness_same_batch_collision_first_write_wins` and `witness_assert_first_repairs_the_retry`.

**Premises.**

* P-IDX: `^KG("out")` exists iff a row exists, given the functional index (spec 252).
* P-NODES: the `pNodes` memo (`Adjacency.cls:566-570, 604-608`).
* The install is indexed. Every probe records `Indexed()`; it was 1 in all native runs.

## O2 — the structural row (Q2; ADR-0009 and its spec 254 amendment)

**Sources**

* ADR-0009 Decision (accepted decision): a temporal write asserts the row, and the marker governs retraction.
* Spec 254 amendment and Decision 1 (Tom, human, secondhand): the implication ends with the last timestamp.
* FR-002 (human): an explicit row outlives the purge.
* ADR-0009:43-44, "rows first" (accepted decision).
* Spec 254 `tasks.md:80-81` (sign-off, "Open"): "A temporal write racing a purge on the same triple can leave a new
  timestamp without its row ... `DeleteTemporalEdge` has the same window." This is recorded as an open defect.

**L1**

* **L1-ROW (amendment):** `rows_ok`. A marked row's triple has a timestamp, unless the predicate is registered
  temporal-only.
* **L1-FWD (Decision; new in round 1):** `fwd_ok`. With the index declared, every timestamp of a predicate that is
  structural in its graph has its triple's row.

  The enumerated exceptions (`fwd_step_ok`):

  | Exception | Status |
  |---|---|
  | (a) a throw from the structural step | F2; a defect unless S2 |
  | (b) a purge stopped after its row step | accepted by ADR-0009:43-44; the rerun finishes, `lemma_purge_rerun_finishes` |
  | (c) opting a predicate back in | accepted by ADR-0015 "Rollback" until backfill; `lemma_backfill_restores_fwd`, `witness_optin_gap_closed_by_backfill` |
  | (d) `engine.delete_edge` of a row whose triple has timestamps | open question 4; `witness_explicit_delete_edge_drops_live_row` |
  | (e) interleaving with a writer (the phased steps) | open defect, see "Races" |

**L2 → L3 bindings**

| Model | Product |
|---|---|
| `assert_row` | `AssertTemporalRow` |
| `retract` and the phased `Retract` | `RetractTemporalRow` `Adjacency.cls:623-645` (re-reads `IsTemporalMarked` :631) and `RetractTemporalRows` :650-689 (the DELETE carries the marker test) |
| `delete_temporal` | `DeleteTemporalEdge` :325-345 (`HasTemporalEdge` :334, retract :337) |
| `purge`, and the phased `PurgeDecide`, `Retract` and `PurgeKill` | `RetireExpired` :944-1013 (decision), :1016 (retraction); raw kill loop in `PurgeRawBefore` :876-915 |
| `create_edge` | `_adopt_temporal_row` (`nodes_edges.py:1275-1300`) and `bulk_create_edges` adopt |
| `LOp::CreateRel` adopt | `LedgerApply.cls:469` |

**Proved**

* `theorem_rows_as_built`: serial steps (not the phased ones) except opting back in.
* `theorem_fwd_as_built`: serial steps outside exceptions (a)–(e).
* `theorem_fwd_assert_first_writes`: under S2, a throwing write keeps L1-FWD.
* `lemma_marked_row_goes_with_last_timestamp`: delete and complete purge.
* `lemma_temporal_ops_keep_explicit_rows`. It now includes the phased steps under any interleaving, because the
  retraction re-tests the marker when it runs. That is FR-002 under concurrency.
* `lemma_explicit_create_clears_marker`.
* `lemma_purge_rerun_finishes`.
* `lemma_phased_purge_serial` and `lemma_phased_delete_serial`: the phased steps, run without interleaving, equal
  the atomic ones.

**Races (as built, witnesses).** Each witness is a step sequence the model permits, because TemporalIndex holds no
lock.

* `witness_purge_write_race_drops_row` (W-RACE-1, spec 254's open item; the reviewer's Check C).
  1. The purge of [0, 1000) decides that the triple's only timestamp goes.
  2. A write at ts 1200 commits. It trusts `^KG("out")` and writes no row.
  3. The retraction deletes the still-marked row.

  The result is a live timestamp with no row: `!fwd_ok`, while `rows_ok` holds.
* `witness_purge_write_race_strands_row` (W-RACE-2, **new**; not in spec 254's sign-off).
  1. The purge has retracted the row.
  2. A write at ts 500, inside the range, asserts a fresh marked row.
  3. The raw kill loop removes that timestamp.

  The result is a marked row of a structural predicate with no timestamp: `!rows_ok`. No later purge or delete can
  find it, the same stranding as F8.
* `witness_delete_write_race_drops_row` (W-RACE-3). `DeleteTemporalEdge` decides on the last timestamp, a write
  commits, and RetractTemporalRow deletes the row: `!fwd_ok`.
* Valid outcomes:
  * `witness_adoption_between_decide_and_retract_survives`: an explicit adopt between decision and retraction keeps
    the row.
  * `witness_purge_then_write_reasserts_row`: serial order keeps both rules.

## O3 — temporal-only opt-out (Q2; ADR-0015, accepted decision, Tom 2026-10-25)

Unchanged from round 0. These hold:

* `lemma_optout_write_writes_no_row`
* `lemma_purge_leaves_registered_rows`
* `theorem_rows_optin_guarded`
* `witness_optin_guard_allows_clean_optin` (the valid outcome)

The witnesses are:

* `witness_optin_strands_marked_row` (F8). **OBSERVED**: `receipts/native/temporal_marked_row_lifecycle.json` case
  F8. The run showed delete → False, purge deleted=1, drop refused "still structural", and backfill left the row.
* `witness_optin_strand_recovery_by_drop` (the way out).
* `witness_optin_guard_refuses`.
* `witness_delete_and_purge_disagree_when_opted_out` (open). This is observed as the model reads the code: case K4
  OBSERVED_AS_EXPECTED.

K1–K3, which bind the proved lifecycle (marked row, adoption, opt-out write), were observed as expected.

## O6 — the ledger temporal op at its commit boundary, and rollbacks (Q3; F3; R1-9)

**Sources**

* `Changeset.create_temporal_edge` doc `changeset.py:321-336` (spec 224, accepted decision): "atomically with all
  structural ops".
* USER_GUIDE "Writes inside your transaction" (accepted decision): "your rollback removes both".
* `temporal.erase` (intent): node erasure keeps the remaining statistics exact; erasure is all-or-nothing.

**L1-ATOMIC:** a rolled-back temporal write or delete leaves the stores and statistics as they were.

**L2 → L3 bindings**

| Model | Product |
|---|---|
| `commit` | `Ledger.Commit` `Ledger.cls:397-415` (TSTART :402; TCOMMIT/TROLLBACK 1 :405; Catch → TROLLBACK :407); `ApplyAll` `LedgerApply.cls:18-49`; `BlocksCommit` `Ledger.cls:514-517`; `OpCreateTemporalEdge` `LedgerApply.cls:617-641` |
| `trollback` | IRIS TROLLBACK 1, now with journaled counter restoration (`restore_j`) |
| `remove_raw` | the `$Increment(bucket,-1)` is unjournaled; the Kill at ≤0 is journaled (`journal_bucket`, before-image = the decremented value) |
| `remove_temporal_row` | journals RebuildBucketAggregate's Sets/Kill (`journal_agg`) |
| node erasure | `delete_node` → `Eraser.EraseNodeIds` → `TemporalIndex.EraseNodes` :400-447 runs the same `RemoveTemporalRow`, so it is bound to `remove_temporal_row` and not modeled as a separate action |

**Premise P-INCR:** TROLLBACK does not undo `$Increment`. It is now **OBSERVED** for the temporal counters (R1–R4
below). The journaling of Set and Kill is standard IRIS transaction semantics. The specific consequence for the
delete path (a Kill at 0 restored as 0) is predicted by the model and **OBSERVED**: R5 found raw bucket 0 after the
rollback.

**Proved**

* `lemma_refused_commit_restores_journaled`: tout, eprop, rows, nodes, the registry and the ledger state are
  restored. The counters are restored only under the "counters undone" variant.
* `witness_counters_undone_keep_exact` (control).
* `witness_rolled_back_delete_exact_if_counters_undone` (control).

**Witnesses (as built)**

* **F3, write rolled back.** **OBSERVED**: `receipts/native/temporal_rollback_counters.json`.

  | Witness | Native case | Observed |
  |---|---|---|
  | `witness_refused_changeset_leaves_counts` | R1 | no raw edge after refusal, count 1, sum 2, velocity 1; retry count 2, sum 4, velocity 2 |
  | `witness_caller_rollback_of_ledger_commit_leaves_counts` | R2 | count 1, sum 3, velocity 1 |
  | `witness_caller_rollback_leaves_counts` | R3 | count 1, sum 4, velocity 1 |
  | `witness_throw_in_changeset_leaves_bucket` | R4 | count 0, velocity 1 |
  | `witness_blocked_changeset_leaves_counts` (BlocksCommit) | not driven natively | — |

  The round 0 judge did not check that op 0 ran (R1) or that the failure was in AssertTemporalRow (R4). The round 1
  probe checks both.
* **R1-9, delete rolled back (new).** `witness_rolled_back_delete_undercounts`: a caller's transaction deletes the
  only edge of a source's bucket, then rolls back.
  * tout, edgeprop and the row come back.
  * tagg count 1 and sum 2 come back (the journaled Kill).
  * `^KG("bucket")` comes back as **0**: its decrement was unjournaled and its Kill was journaled with before-image 0.

  So one raw edge has velocity 0, which is `!agg_exact`. With two edges the decrement simply stays (bucket 1 over
  2 edges). This mirrors F3. **OBSERVED** in the final native battery (`receipts/native/temporal_rollback_counters.json`):

  | Case | Observed | Expected |
  |---|---|---|
  | R5 (only edge) | count 1, sum 2.0, velocity 0, raw bucket 0 | 1/2.0/1 |
  | R5b (one of two) | count 2, sum 5.0, velocity 1 | 2/5.0/2 |
  | R6 (`delete_node` rolled back) | velocity 0, raw bucket 0 | 1 |

## Q4 — temporal endpoints and ledger verify (F4)

Source: commit `43efd473` ("a temporal mirror is no longer an unrecorded write"; open question 3 decides whether that
covers endpoint nodes). The proved lemma and the controls are unchanged.

**OBSERVED** in `receipts/native/temporal_endpoint_nodes_verify.json`:

| Case | Observed |
|---|---|
| C0 control (known ids, named graph) | equal |
| C1 control (opt-out) | equal |
| V1 (direct write) | diverges (unrecorded_writes) only on the new endpoint node |
| V2 (ledger op) | diverges, same |
| V3 (temporal op then `upsert_node`) | diverges |
| V4 (temporal op then `create_node`) | op 1 refused `node_exists`; [create_node, temporal] commits |
| V5 (strict mode) | the temporal write is not refused, and verify diverges |

The round 1 judge additionally requires that the only difference is the new node and that its row exists, and that
V4's refusal is op 1 with `node_exists`.

## Trust inventory

* No `assume`, `admit`, `external_body`, `assume_specification` or `uninterp` in `temporal.rs`.
* Bundled vstd only.
* Premises:
  * P-IDX
  * P-NODES
  * P-INCR (observed)
  * IRIS journaling of Set/Kill, with before-images restored in reverse by TROLLBACK (platform)
  * indexed install

## Not represented (scope limits)

* `tin`, `tlast` (O5, F6), min/max/HLL, edgeprop contents, the window reader (O4), `PurgeBefore`,
  `PurgeBucketRange`, `EraseGraph`, `retire_bare_nodes`.
* Node erasure is bound to `remove_temporal_row` but is not its own action. Its retraction is the Eraser's, not
  RetractTemporalRow.
* The non-indexed install, the Python mirror and the spec-246 flag (F9, R1-13). Multigraph `ekey`.
* Concurrency other than writer versus purge and writer versus delete (F7 is a single witness; it is not a phased
  model).
* Ledger idempotency, head lock and redaction state (BlocksCommit is an input); F5 (an insert collision still records
  `create_temporal_edge`).

## Candidate findings

### Bugs

1. **F1: "update" double-counts statistics, and a later delete leaves the bucket inflated.**
   * Expected: the aggregate docs say "original value" (Q1 open).
   * Evidence: `witness_update_double_counts`.
   * **OBSERVED** (`temporal_write_modes.json` update_double_count): one raw edge w=9 gives count 2, sum 11.0,
     velocity 2. The bulk update case corroborates it.
2. **F2: a throw from AssertTemporalRow leaves raw stores and the bucket count without row or tagg; the insert retry
   is a silent collision; the bulk fallback reports success.**
   * Evidence: the F2 witnesses and `witness_partial_write_breaks_fwd`.
   * **OBSERVED** (partial_write_retry: 1 raw edge, bucket 1, no tagg, the retry returns without error).
   * **OBSERVED** (bulk_fallback_insert: written=2, collisions=0, no error; raw 2/6.0 against tagg 1/1.0).
   * **OBSERVED** (bulk_fallback_update: count/sum/velocity 2/2.0/4 against raw 2/6.0/2; the error names
     AssertTemporalRow).
3. **F3: a rolled-back temporal write leaves `bucket` and tagg `count`/`sum`.** **OBSERVED** in R1–R4. The USER_GUIDE
   rollback list is incomplete.
4. **R1-9: a rolled-back temporal delete or node erasure under-counts `bucket`.** It is the mirror of F3, and the
   zero node it leaves is itself a reportable source (R2-4). **OBSERVED** (R5, R5b, R6).
5. **F4: temporal writes create ungoverned node rows, verify diverges, and changeset op order decides refusal versus
   permanent divergence; strict mode does not stop it.** **OBSERVED** in V1–V5.
6. **Race RACE-1/3/4: a write racing a purge or a delete leaves a live timestamp without its row.** It violates
   ADR-0009's Decision (L1-FWD).
   * RACE-4 (R2-2) is the route where the triple had no row when the purge decided.
   * This is spec 254's known open item, now model witnesses. No probe was written: it needs a writer timed inside
     `RetireExpired`.
   * The repair must re-test every `^||IVG.TPurge` candidate, rows or not, when the retraction runs. Proved closed
     in witnesses under P-LOCK.
7. **Race RACE-2/5 (new): a write inside the purge range after the purge's retraction leaves a marked row with no
   timestamp.** This covers the same triple (RACE-2) or a back-dated new triple (RACE-5). It violates L1-ROW, and the
   row is stranded as in F8.
   * CONFIRMED-BY-PROOF-OF-MODEL; SUSPECTED for the product (needs a timed writer).
   * The repair's kill loop must re-retract what it leaves without a timestamp.
8. **F7: concurrent inserts double count.** CONFIRMED-BY-PROOF-OF-MODEL; SUSPECTED.
9. **F8: opting back in before the drop strands marked rows.** **OBSERVED**. It can be recovered through re-register,
   drop, opt-in and backfill.
10. **R1-5 (found by the reviewer and the native runs, not by this model): `get_temporal_aggregate` min/max/avg raises
    `ValueError` for an empty bucket, and for a half-rolled-back one.** The docstring `temporal.py:948-951` says "0 or
    0.0, never None".
    * Cause: `iris_sql_store.py:2987` `float(val) if val else 0.0`. Native returns `None` for `""`, and `str(None)`
      is `'None'`.
    * F3 makes the half-rolled-back case reachable. The rollback takes back tagg min/max (Sets) but leaves
      count/sum (`$Increment`), so count reads 1 while min/max raise. This was observed in the R1 receipt.
    * The model does not represent min/max.

### Open questions

1. **Q1: aggregate meaning under update.** Option (b) is proved consistent with L1-AGG.
2. **Q4: refuse an opt-in while stranded rows exist, or let DropRows accept them.** The guard is proved sufficient.
   The question also covers whether delete should follow purge's registry rule.
3. **Q3: are temporal endpoint nodes governed?**
4. **(new, R1-7) should an explicit `delete_edge` of a marked row be allowed while the triple has timestamps?**
   Today the row goes and the timestamps stay (test_254_purge_e2e.py:322), and the next write re-asserts it
   (`witness_explicit_delete_edge_drops_live_row`). No source decides it.
5. **Race repair.** Spec 254 left the write/purge race open. The modelled proposal (`race_recheck`, premise P-LOCK)
   has two parts:
   * a per-triple lock shared with AssertTemporalRow;
   * under it, the retraction re-tests survivors for every candidate (rows or not), and the kill loop re-retracts the
     triples it left without a timestamp.

   It closes RACE-1 to RACE-5 in witnesses. An all-schedules proof and the lock's cost are open.

### Simplifications (proposals)

* **S2:** put the structural step first. It closes F2 and the F2 exception to L1-FWD.
* **S3:** a bulk fallback that does not re-send written edges.
* **Counters inside transactions:** Sets that are journaled, or a rebuild after a rollback. This would close F3 and
  R1-9 together. For both, compare `witness_counters_undone_keep_exact` and
  `witness_rolled_back_delete_exact_if_counters_undone` with the as-built witnesses.

## Native probes (round 1 versions; run by the orchestrator in the final battery, all four OBSERVED_DEFECT as listed above)

| Probe | Round 1 changes (review R1-12, R1-6) |
|---|---|
| `.g5/Verus_verification/native/probes/temporal_write_modes.py` | cases record as they run; update requires exact statistics after the first insert and separates tagg (raw-exact or original-value) from the bucket count; partial_write requires the error to name AssertTemporalRow and the retry to change nothing; the bulk cases require the refused edge's raw entry and (update) an AssertTemporalRow error; min/max reader errors (R1-5) are recorded but do not decide |
| `.g5/Verus_verification/native/probes/temporal_rollback_counters.py` | R1 requires `op_index == 1`; R2/R3 require the edge visible inside the transaction; R4 requires AssertTemporalRow; new R5, R5b (rolled-back `delete_edge_temporal`) and R6 (rolled-back `delete_node`) with preconditions: the delete removed the edge inside the transaction, the raw edges came back, statistics were exact before |
| `.g5/Verus_verification/native/probes/temporal_endpoint_nodes_verify.py` | a divergence counts only if every difference is the new endpoint's node and its row exists; V1 requires no revision; V2/V3 require no `create_node` record; V4 requires op 1 refused `node_exists` |
| `.g5/Verus_verification/native/probes/temporal_marked_row_lifecycle.py` | F8 requires the purge to delete exactly one timestamp, delete to find nothing, and drop to be refused as "still structural" |

## Controls (round 1)

All are listed in `model.json` (29) with what each removes and where it must fail. The receipts are under
`.g5/Verus_verification/results/temporal/<stamp>-control-<name>/receipt.json`.

* Round 0 controls kept. Four anchors were re-pointed after the refactor: `no-bucket-decrement` (now attributed to
  `lemma_remove_raw_shape`), `no-rebuild`, `purge-forgets-cut` (now `lemma_kill_exact`), and
  `rollback-keeps-bucket-anyway`.
* New controls:
  * `write-skips-assert-row` (L1-FWD)
  * `retract-ignores-marker-at-effect` (FR-002 under interleaving; valid-outcome witness)
  * `delete-decide-always-dooms` (phased-delete binding)
  * `rebuild-not-journaled` (R1-9 fidelity)

## Controls (round 2)

`model.json` lists 33 controls.

* The round 1 anchors moved for `retract-ignores-marker-at-effect` and the three `repaired-without-*` controls. The
  `repaired()` literal gained `race_recheck`.
* New controls:
  * `zero-counter-kept` (R2-4; must fail `lemma_delete_exact`)
  * `decide-rows-only` (R2-2; must fail `lemma_doomed_set_iff` and `witness_purge_write_race_rowless_route`)
  * `retract-no-recheck` (repair without its retract-time re-test)
  * `kill-no-reretract` (repair without the kill re-retraction)
* Before adding it, I checked the reviewer's zero-counter mutation (T-b) on a scratch copy. It fails at
  `lemma_delete_exact` (L1) and at the R1-9 witness.

**Round 2 results.** Prove: PASS, 113 verified, 0 errors (`results/temporal/20261114T040433Z-prove/receipt.json`). All 33 controls EXPECTED_FAIL, with stamps
20261114T040447Z through 20261114T041017Z.

The first round 2 attempt had one FAIL_ELSEWHERE, `decide-rows-only` (receipt 20261114T040331Z). It was the same
attribution trap as rounds 0 and 1. `witness_purge_write_race_rowless_route` consumed `lemma_doomed_set_iff`'s
mutated, trusted postcondition and verified vacuously. The witness now proves set membership from `doomed_set`'s
definition. I checked the mutation on a scratch copy (the witness fails), then re-ran prove and all controls.
