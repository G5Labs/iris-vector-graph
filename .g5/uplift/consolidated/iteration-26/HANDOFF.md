# Iteration 26: engine writes inside a caller's transaction

Before image: seal 25 `2300521b`. Product `3eaa79cf` unchanged. Guidance as in
[retest-run.json](../iteration-25/retest-run.json). Native evidence only from `ivg-retest-20261116-iris`.

## Correction carried from iteration 25

bug-plt-106 duplicated the inherited bug-plt-027 (same trigger and reader consequence; `structure.adjacency.bulk`
already linked it). The evidence now sits on bug-plt-027 (live, E2E reproduced, Medium); `bug-plt-106` stays as a
navigation span and a crosswalk row marked duplicate. Iteration 25's A1 result is a repair of a known suspicion, not a
discovery.

## W31: why, predictions and outcome

Step-1 inventory: `_write_txn.py` had 20 of 20 members without an active binding, and it decides whether every engine
write commits, nests or refuses. Predictions were frozen from the owners and USER_GUIDE before reading the source
([caller-txn-PAIRS.md](caller-txn-PAIRS.md)); source-informed cases were added, marked, before any observation; the
autocommit cases were added after the first binding run disagreed, before their targeted observation.

- Held: ordinary writes on both engines (T1-T3), the loader refusal after a write (T7), the purge contrast (T9 on the
  caller's connection is undone; T10 on `from_connect` is not and retires the bare endpoint nodes).
- **Missed**: T5 (USER_GUIDE says a `from_connect` engine's temporal edge stores run outside the caller's transaction;
  `create_edge_temporal` joins) → Low **bug-plt-107**; T8 (after `START TRANSACTION`, `$TLEVEL` is already 1, so the
  loader refuses before any write) → owner now states it.
- **New discovery, High bug-tmp-102**: with the driver's autocommit off and nothing written yet, a rolled-back
  `create_edge_temporal` keeps its temporal stores (`InsertEdge` sets them at `$TLEVEL` 0) while its marked structural
  row and endpoint nodes (embedded SQL, implicit transaction) are rolled back. Both engines. Neighbors: `START
  TRANSACTION` → nothing left; commit → all readers see it. Found because the first native binding run DISAGREED.
- `set_temporal_structural` also survives an autocommit-off rollback on the caller's connection and any rollback on
  `from_connect`; recorded as evidence on the open question `structure.write.engine-connection`, not as a defect,
  because which calls must join is that question.

Owners: [structure.write](../../../ontology/features/graph-structure.g5.md#structure.write) now states the
four-way rule; [temporal.write](../../../ontology/features/temporal.g5.md#temporal.write) points to it. Formal:
[models/write_routing](../../../Verus_verification/models/write_routing/NOTES.md), 8 verified, 8 controls
EXPECTED_FAIL; native binding AGREES over 36 histories after the model gained the call shapes (first run DISAGREES,
kept; a first 5-theorem version and its 6 controls are kept too). The premise comment was corrected against F-C1705
(on 2026.1 SQL COMMIT/ROLLBACK end one level) and everything rerun.

## Recount

Active behavioral bindings 287 → **305** of 4,130 ([member-delta.json](member-delta.json)): 18 newly reached and bound
(`WriteTxn.begin/commit/rollback/_call`, `caller_transaction_level`, `refuse_in_caller_transaction`,
`_driver_autocommit_off`, `BulkLoader._refuse_in_caller_transaction`, `IRISGraphEngine._iris_obj`, `.from_connect`,
`IRISGraphStore._iris_obj`, `TemporalMixin.purge_before`, `.set_temporal_structural`, `Txn.Begin/End/Undo`,
`TemporalIndex.PurgeBefore`, `TemporalPolicy.Apply`); 4 existing members gain a claim (`create_edge_temporal`,
`write_temporal_edge`, `InsertEdge`, `WriteStores`); overlap 0; distinct additions 22; lost 0. `WriteTxn.rollback` and
`Txn.Undo` are bound by inspection only (the failed-write case is not natively exercised).

## Next

A large, little-linked ObjectScript module whose public outcome matters: `VecIndex.cls` (32/32 unbound, vector search
results) or `TraversalBuild.cls` (38/38). Then re-run step 5 (product-wide inventory) before any convergence claim.
