# Whether an engine write joins the caller's transaction

Product `3eaa79cf`, unchanged. Iteration 26 (retest). Predictions frozen before native observation in
[caller-txn-PAIRS.md](../../../uplift/consolidated/iteration-26/caller-txn-PAIRS.md). Owners:
[structure.write](../../../ontology/features/graph-structure.g5.md#structure.write),
[temporal.write](../../../ontology/features/temporal.g5.md#temporal.write).

## What the model decides

The caller's server process has a `$TLEVEL`, uncommitted writes and durable writes. The caller opens its transaction
either with SQL `START TRANSACTION` (`$TLEVEL` 1 at once) or by turning the driver's autocommit off (`$TLEVEL` 0 until
the first SQL write, which opens level 1 implicitly). Each engine call is routed to a process (`route`): ordinary
writes and `create_edge_temporal` run on the engine's SQL connection's process; `purge_before` and
`set_temporal_structural` go through `engine._iris_obj()`, which opens a Native API connection of its own when the
engine knows its credentials (`from_connect`). On its own process a call is a transaction of its own. On the caller's
process a call either goes through `WriteTxn` (`begin` opens the caller's level first when autocommit is off, then
IVG's level; `commit` lowers back to the caller's level; `rollback` takes back IVG's level only), or calls ObjectScript
directly as an ordered list of global (G) and SQL (S) writes: `InsertEdge` G then S, `PurgeBefore` S then G,
`TemporalPolicy.Apply` G. A G write at `$TLEVEL` 0 is durable at once. Source lines are in the header of
[write_routing.rs](write_routing.rs).

## Theorems (8, all new; no imports)

| Theorem | Claim | Observed as |
|---|---|---|
| `theorem_writetxn_call_follows_caller_end` | a WriteTxn call is kept exactly when the caller commits, however it opened its transaction | T1-T3, binding |
| `theorem_start_transaction_direct_call_follows_caller_end` | after `START TRANSACTION`, every effect of a direct call on the caller's process follows the caller | T4, T5, T9, binding |
| `theorem_autocommit_off_temporal_edge_splits` | autocommit off, nothing written: a rolled-back `create_edge_temporal` keeps its temporal stores and loses its marked row and nodes (bug-tmp-102) | T11, T12, binding |
| `theorem_autocommit_off_purge_follows` | the same caller: a purge on the caller's process follows the caller (its SQL comes first) | binding |
| `theorem_own_process_write_survives_rollback` | a call on the engine's own connection is durable whatever the caller does | T10, binding |
| `theorem_routing` | the routing above, for both engines | T5, T10 |
| `theorem_failed_write_keeps_caller_work` | a failed IVG write takes back its own level only | not natively exercised |
| `theorem_loader_refusal` | the loader refuses after `START TRANSACTION` even before a write; with autocommit off only after a write | T7, T8, binding |

No `assume`, `admit` or `external_body`; bundled vstd only.

## Controls

Eight, all EXPECTED_FAIL full and isolated: `commit-ends-all-levels` (4.6.3's SQL COMMIT), `temporal-on-own-connection`
(the USER_GUIDE's description), `purge-on-caller-connection`, `undo-ends-all-levels`, `refuse-only-after-a-write`,
`own-process-joins`, `temporal-sql-first` (the repair direction for bug-tmp-102), `no-implicit-level` (the provider
premise). The first five-theorem version of this model and its six controls are kept in `results/write_routing/`.

## Binding

[binding.py](binding.py): actual engine calls on the run-isolated retest fixture over 32 histories (engine on the
caller's connection or `from_connect` × ordinary node+edge, temporal edge, purge, policy × `START TRANSACTION` or
autocommit off × commit or rollback) and 4 loader-refusal histories, each read afterwards on a separate observer
connection (temporal window, Cypher count, `get_node`, `get_temporal_structural`). **AGREES** with the port; every
required mutation is detected (`undo_ends_all_levels` is not exercised). The **first run DISAGREED** in three
autocommit-off rollback histories; the targeted probe (`iteration-26/autocommit_probe.py`) showed the split state, and
the model gained the call shapes. That receipt is kept.

## Limits

Transcription with native agreement; no product body is verified. Not exercised: a write that fails inside the
caller's transaction, `bulk_create_edges_temporal`, `delete_edge_temporal`, `rebuild_temporal_latest`, structural
drop/backfill, BM25, vector and ledger calls, embedded (in-process) connections, a namespace without the declared
adjacency index (where `^KG` goes over a second connection, bug-str-015), and IRIS 2026.3 (F-C1705).
