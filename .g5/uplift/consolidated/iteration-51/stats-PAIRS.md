# W57: temporal statistics readers — write history → bucket statistics → analytics answer (frozen predictions)

Frozen 2026-11-17T03:40Z, **before** reading the deciding bodies of `iris_src/src/Graph/KG/TemporalIndex.cls`
(`GetAggregate`, `GetBucketGroups`, `BucketGroupsEvents`, `GetBucketGroupTargets`, `GetVelocity`, `FindBursts`,
`GetDistinctCount`, `HLL*`, `RebuildBucketAggregate`, `RebuildBucket`, `NoteLatest`, `Relatest*`, `RebuildLatest`,
`Purge*`, `InternLabelSet`, `ResolveLabelSet`), `iris_src/src/Graph/KG/TemporalWindow.cls` (`Latest`) and the bodies of
the engine/store methods in `iris_vector_graph/_engine/temporal.py` and `stores/iris_sql_store.py`. Sources used:
`docs/API_REFERENCE.md` (the engine entries), `docs/USER_GUIDE.md` §8 (aggregates, retention), `CHANGELOG.md` (R217,
R249), the method docstrings only (extracted with `ast.get_docstring`, bodies not read), the tests
`tests/e2e/test_460_r217_temporal_aggregate_window_e2e.py` and `tests/e2e/test_460_r249_counters_default_graph_e2e.py`,
and the owners [temporal.stats](../../../ontology/features/temporal.g5.md#temporal.stats),
[temporal.stats.after-purge](../../../ontology/features/temporal.g5.md#temporal.stats.after-purge),
[temporal.latest](../../../ontology/features/temporal.g5.md#temporal.latest),
[temporal.latest.exact](../../../ontology/features/temporal.g5.md#temporal.latest.exact),
[temporal.delete](../../../ontology/features/temporal.g5.md#temporal.delete),
[temporal.purge](../../../ontology/features/temporal.g5.md#temporal.purge) and
[temporal.write](../../../ontology/features/temporal.g5.md#temporal.write).

Prior knowledge carried in (agent findings, not product observation at this iteration): bug-tmp-002 (update counts the
edge twice), bug-tmp-003 (rolled-back write leaves counts), bug-tmp-009 (empty-window min/max/avg raises), bug-tmp-010
(rolled-back delete undercounts), F-0508 (burst predicate ignored), the recorded divergence "the millisecond entry
point's default now is in seconds". Where the documented contract and a suspicion disagree, the prediction follows
the **documented contract** and the row says so; a departure is then a miss of the contract, not of the suspicion.

Common fixture: `ivg-cont-20261117-iris`, fresh prefix `i51_<stamp>_`, one dedicated named graph per case family plus
a default-graph neighbor where scope matters. `T` is a multiple of 300 (the bucket width) far from the wall clock.
Readers: the engine method's Python return value; for ObjectScript-only members the class method's return through
the driver.

| ID | Case (changing input or history) | Neighbor | Predicted (source) |
|---|---|---|---|
| A1 | `get_temporal_aggregate(s,p,m,T+100,T+300)` over s→ at T+5 (w2), T+100 (4), T+299 (9), T+300 (1), T+650 (5) | `[T, T+299]` (one whole bucket) | test/doc: cut window count 3, sum 14, min 1, max 9, avg 4.666667; whole bucket count 3, sum 15, min 2, max 9 |
| A2 | `[T+301, T+649]` (no event) metric `min`/`max`/`avg` | same window, metric `count`/`sum` | doc (`get_temporal_aggregate` docstring): `0.0` for min/max/avg, `0`/`0.0` for count/sum. Suspicion bug-tmp-009: min/max/avg raise `ValueError` |
| A3 | insert w=2 then `mode="update"` w=9 at the same coordinate; read the whole bucket | the same coordinate read through a window that cuts the bucket | doc ("aggregates remain based on the original value"): whole bucket count 1, sum 2.0, max 2.0; cut window (edge by edge) count 1, sum 9.0. Suspicion bug-tmp-002: whole bucket count 2, sum 11 |
| A4 | `create_edge_temporal` inside a caller transaction that is rolled back; whole-bucket read | the same write committed | USER_GUIDE "Writes inside your transaction" (rollback removes the write): whole bucket count 0; committed count 1. Suspicion bug-tmp-003: rolled back still counts 1 in the whole bucket, 0 in a cut window |
| A5 | `purge_raw_before(T+300)` then read `[T, T+299]` (whole) | the same purge, read `[T+100, T+299]` (cut) | doc/USER_GUIDE: whole bucket still answers the aggregate (count 3); the cut window counts nothing of the purged bucket (count 0) |
| A6 | `purge_bucket_range(b, b)` for bucket `b = T//300`, then read `[T, T+299]` (whole) | the same purge, read the cut window `[T+100, T+299]` | API: statistics gone, raw edges kept → whole bucket count 0; cut window reads raw edges → count 2 (T+100, T+299). Return value 1 (one bucket removed); `bucket_start > bucket_end` returns 0 |
| A7 | delete the minimum-weight edge of a bucket, then read `min` over the whole bucket | delete a non-extreme edge | owner temporal.delete (recomputed from the remaining edges): min moves to the next-smallest weight; neighbor min unchanged |
| A8 | aggregate on graph g1 when graph g2 holds edges of the same s,p in the same bucket | g2 itself | temporal.edge.graph-scope: g1 counts only its own edges |
| G1 | `get_bucket_groups(p, T+100, T+300, source_prefix=pfx)` | `[T, T+1000]` and `[T+301, T+649]` | test: `{ann: (3, 14, 1, 9)}`; whole `{ann: (5,21,1,9), ben: (1,7,7,7)}`; no-event window `[]` (a source with nothing in the window is absent, not a zero row) |
| G2 | `get_bucket_groups(predicate="")` with s having two predicates | `predicate="P"` | doc: one row per (source, predicate) pair; empty predicate matches all; `P` gives only `P`'s row |
| G3 | `get_bucket_groups` after `purge_raw_before` of a whole bucket, window holds it whole | window cuts it | as A5 (doc): whole counts the aggregate; cut counts none |
| G4 | `get_bucket_group_targets(s,p,T+100,T+200)` where target x appears only at T+5 (same bucket, outside the window) | target y at T+150 | doc ("over a time window"), working assumption the exact window: y listed, x not listed (low confidence: may read whole buckets) |
| V1 | `get_edge_velocity(s, window_seconds=300, now_ts=T+650)`, events at T+299 and T+300 and T+600 | the same with `now_ts=T+599` | doc ("rounded out to whole buckets", "edges up to a bucket before now−window count too"): buckets from (now−window)//300 to now//300: now T+650 → buckets T+300, T+600 → velocity 2 (T+300, T+600), T+299 excluded; now T+599 → buckets T, T+300 → T+299, T+300 → 2 (T+600 excluded) |
| V2 | velocity of s over two predicates in the window | one predicate | doc: every predicate counted (sum over predicates) |
| V3 | velocity after `mode="update"` at an occupied coordinate | after an insert collision at the same coordinate | doc of `create_edge_temporal` (collision changes no store): collision leaves velocity 1. Update: doc silent for the counter; suspicion bug-tmp-002: 2 |
| V4 | velocity after `purge_raw_before` covering the bucket | after `purge_bucket_range` of the bucket | temporal.stats.after-purge: raw purge keeps the counter (velocity unchanged); bucket-range purge removes it (velocity 0) |
| V5 | velocity after deleting one of two edges in the bucket | before the delete | temporal.delete: goes down by one |
| B1 | `find_burst_nodes(predicate="Q", threshold=2, now_ts=…)` where s has 2 events all of predicate P | `predicate=""` | docstring body text: predicate passed and not used → s listed with velocity 2 in both (F-0508: the parameter doc says it filters) |
| B2 | threshold equal to the velocity (2) | threshold 3 | doc ("at least"): listed at 2, not at 3 |
| B3 | bursts on graph g1 when g2 has a bursting source | g2 | graph-scoped: g2's source absent from g1's answer |
| B4 | bursts with `now_ts=0` and fixture timestamps far in the past | explicit `now_ts` | doc: wall clock → fixture sources absent; explicit now lists them |
| D1 | `get_distinct_count(s,p,T,T+299)` with three edges to one target | three edges to three targets | doc: estimate ≈1 vs ≈3 (within 26%; for such small sets the estimate is expected exact) |
| D2 | distinct count over `[T+100, T+200]` where target x is only at T+5 (bucket touched, outside the window) | a window not touching x's bucket | doc ("merged over the buckets the window touches"): x counted (window rounded out); neighbor not counted |
| D3 | distinct count after `purge_raw_before` of the bucket | after `purge_bucket_range` of the bucket | statistics stay → unchanged; bucket range → 0 |
| D4 | distinct count after deleting the only edge to target x | before | delete docstring ("recomputed from the bucket's surviving edges"): x no longer counted |
| D5 | `source=""` | a named source | doc: merges every source's sketch for the predicate |
| L1 | `get_latest_edges([s])` with edges at T+5 and T+650 | `before=T+650` | owner temporal.latest: newest T+650; with before=T+650 (exclusive) → T+5 |
| L2 | `before=T+650, lookback=100` | `lookback=700` | ignores events older than before−lookback = T+550 → s absent; 700 → T+5 |
| L3 | delete the newest edge (T+650) | no delete | temporal.latest.exact: latest moves back to T+5 |
| L4 | `purge_raw_before(T+1000)` removing all of s's edges | purge removing only T+5 | exact through purge: s absent; neighbor still T+650 |
| L5 | `source_prefix=pfx` and every-source (no names) | named sources | the same newest edges for the matching sources |
| L6 | `rebuild_temporal_latest(graph)` on a current graph | — | returns the number of (source, predicate) pairs; answers unchanged |
| L7 | update the newest edge's weight/attrs with `mode="update"` | insert collision there | latest returns the updated weight/attrs; collision keeps the first |
| S1 | `intern_label_set({"port": 1972, "a": true})` then `resolve_label_set(h)` | `resolve_label_set("ffff…")` (unknown) | canonical JSON with `1972` as a number and `true` as boolean; unknown → `''`; key order does not change the hash |
| S2 | `purge_raw_before` then resolve | — | append-only: still resolves |

Ranking by consequence: aggregates and groups (dashboards read them; the window and purge contrasts change the number),
then velocity and bursts (alerting; the threshold and predicate contrasts change who is listed), then distinct counts,
then latest reads (already partly modeled by the window reader), then label sets.
