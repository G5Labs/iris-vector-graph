# temporal_stats — temporal statistics readers (W57, iteration 51)

Product pin `3eaa79cf`. Root [temporal_stats.rs](temporal_stats.rs), controls in [model.json](model.json), native
binding [binding.py](binding.py). Frozen predictions: [stats-PAIRS.md](../../../uplift/consolidated/iteration-51/stats-PAIRS.md)
(committed before the deciding source was read). Owners: [temporal.stats](../../../ontology/features/temporal.g5.md#temporal.stats)
and its children `.after-purge`, `.window`, `.writers`, `.velocity`, `.distinct`, and
[temporal.labelset](../../../ontology/features/temporal.g5.md#temporal.labelset).

## Results (final candidate)

| Run | Result | Receipt |
|---|---|---|
| prove | PASS 51 verified, 0 errors | `results/temporal_stats/20261117T035909Z-prove` |
| controls | 16 of 16 EXPECTED_FAIL; each fails exactly its named functions (full-run error count = named count) | `results/temporal_stats/20261117T0359*-control-*` |
| binding | AGREES, 139 cases, all 16 mutations detected, tampered observation detected | `results/temporal_stats/20261117T040000Z-binding` |

Kept failures: `20261117T035814Z-prove` was UNEXPECTED (50 verified, 1 error): `theorem_targets_follow_raw` left the
frame fact `purge_buckets(..).raw == st.raw` implicit and the solver did not find it on that run. The proof now
asserts it; three consecutive local runs and the final receipt verify. `20261117T035703Z-binding` AGREES (133 cases)
but its `raw-purge-drops-statistics` mutation went undetected: the raw-purge history also deleted in the purged bucket,
which hides the purge's frame. The histories were split (`p`/`pb`, `q`/`qb`); the final binding detects it (3 cases).
Earlier prove/control receipts (`20261117T035348Z`…`T035438Z`) are of the model before `bucket_count` was added.

## What is modeled

State `St`: the raw edges `raw` (^KG("tout"); write order, coordinates unique), tagg `cnt`/`sum` ($Increment), `mn`/`mx`
and the sketch `hll` (Set), and the event counters `bkt` (^KG("bucket"), $Increment). Every reader answer is computed
from this state, and the state only from the modeled writers applied to a history:

| Spec function | Source | Role |
|---|---|---|
| `write`, `stores_written` | `WriteStores` 80-133 (`InsertEdge` 46-65, `BulkInsertCounts` 151-183 call it) | decision (collision/skip guard 82-86; update has none) and effects |
| `hll_empty`, `hll_add`, `wf_hash` | `HLLEmpty` 196-199, `HLLAdd` 210-224, `UpdateHLL` 185-193 | effect; SHA-1 register choice is the provider input `hf` |
| `rolled_back` | IRIS journaling (P-INCR) | Set/Kill undone, `$Increment` kept |
| `delete_at`, `rebuild` | `DeleteTemporalEdge` 325-343, `RemoveTemporalRow` 348-360, `RebuildBucketAggregate` 455-486 | effect |
| `purge_raw_before` | `PurgeRawBefore` 866-920 | effect (raw only; statistics frame) |
| `purge_buckets`, `purged_count` | `PurgeBucketRange` 1050-1065 | effect and return value |
| `get_aggregate`, `agg_from`, `bucket_part`, `server_answer` | `GetAggregate` 1445-1493 | decision (whole vs cut) and reader |
| `py_value`, `get_temporal_aggregate` | `iris_sql_store.py` 2971-2987, `temporal.py` 934-959 | decision (`float(str(v)) if str(v)`) and final reader |
| `group_row`, `row_part`, `tagg_present` | `GetBucketGroups` 1495-1559, `BucketGroupsEvents` 1564-1596 | reader |
| `is_target` | `GetBucketGroupTargets` 1598-1633 | reader |
| `velocity`, `bkt_sum`, `now_of`, `bucket_count` | `GetVelocity` 757-770, `TemporalIndexMS.GetBucketCount` | reader |
| `burst_listed`, `present` | `FindBursts` 772-806 | reader (predicate unused) |
| `distinct`, `merged`, `estimate`, `zs` | `GetDistinctCount` 632-682 | reader and estimator |
| `canon`, `body`, `pair_text`, `enc` (`esc` for the repair) | `InternLabelSet` 1341-1391, `ResolveLabelSet` 1394-1397 | effect and reader |

## Claims (general unless marked)

- `theorem_one_whole_bucket_reads_statistics`, `theorem_cut_bucket_is_exact` (valid neighbor): whole bucket → statistics;
  a window inside one bucket that cuts it → exactly the raw window, for every state.
- `theorem_update_counts_twice` (bug-tmp-002): for every state and occupied coordinate, an update adds one to count and
  event counter while the raw count is unchanged. `theorem_update_whole_vs_cut`: insert w0 then update w1 → whole read
  count 2, sum w0+w1; cut read one(w1). `theorem_update_then_delete_leaves_velocity`: then deleting leaves counter 1
  with no edge. `theorem_collision_changes_nothing` (neighbor).
- `theorem_rolled_back_first_write`, `theorem_rolled_back_group_row` (bug-tmp-003 sharpened): a rolled-back first write
  of a bucket leaves count 1 and sum w with no min, max or sketch; Python min/max raise; the group row is
  (1, w, null, null). `theorem_committed_first_write` (neighbor).
- `theorem_empty_answer_raises` (bug-tmp-009, general over every aggregate and metric).
- `theorem_raw_purge_keeps_statistics`, `theorem_raw_purge_whole_vs_cut`, `theorem_bucket_purge_whole_vs_cut`,
  `theorem_bucket_purge_reversed_range`, `theorem_delete_after_bucket_purge_recreates` (q-tmp-002 mirror),
  `theorem_delete_rebuilds_from_survivors` (neighbor), `theorem_targets_follow_raw`.
- `theorem_velocity_counts_touched_buckets` (general: a fresh event raises velocity by one iff its bucket lies in
  [(now − window) \ 300, now \ 300]); `theorem_velocity_boundaries` (its instances at T+299/T+300/T+590, for every
  store); `theorem_bursts_ignore_predicate` (F-0508); `theorem_burst_threshold_inclusive`; `theorem_ms_default_now_misses`.
- `theorem_distinct_empty_is_zero`; `theorem_distinct_nonempty_at_least_eleven` (bug-tmp-103: every sketch with a set
  register answers ≥ 11); `theorem_distinct_one_target_is_eleven` (every hash); `theorem_same_target_twice`;
  `theorem_distinct_window_rounded_out` (a target before the window's start in a touched bucket counts).
- `theorem_label_sets_collide` (bug-tmp-104, for all keys and values).

## Premises and trust

No `assume`, `admit`, `external_body` or `uninterp`; bundled vstd (`arithmetic::div_mod`). Premises: P-INCR (IRIS does
not undo `$Increment` on rollback; observed again here, case `rb`); the driver returns None for an empty string
(observed: `ValueError: could not convert string to float: 'None'`); SHA-1 bytes decide the register (binding computes
them as HLLAdd does); ObjectScript decimal arithmetic in the estimator rounds as the integer formula does (exact on all
139 cases); IRIS number text (`.5`) is a provider rule outside the model. Weights are integers in the model; the binding
uses whole-number weights. Single process: no concurrency (q-tmp-001 unchanged).

## Not represented

The newest-event index (`NoteLatest`, `Relatest`, `RelatestRange`, `RebuildLatest`, `TemporalWindow.Latest`): the
iteration-51 probe observed L1-L8 and every prediction held, but no Verus claim covers tlast exactness yet.
`get_edge_attrs`, `get_window_sources`, `BulkInsert` (a wrapper returning the first count of `BulkInsertCounts`, not
exercised), legacy `PurgeBefore`'s statistics kill, `RebuildBucket` (migration only), `EraseNodes`/`EraseGraph`,
the all-sources distinct merge (`source=""`, observed in the probe only), `get_distinct_count(source, "")`.
