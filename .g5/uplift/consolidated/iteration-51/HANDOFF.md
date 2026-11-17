# Iteration 51: temporal statistics readers (W57)

Before image: `0532ac86` (seal 50 `63526c9a` plus the master's inventory commit). Product `3eaa79cf` unchanged: nothing
outside `.g5/` changed in this iteration (the `.agents/` and `experiment/` differences from the pin are older and
unchanged; `check_consolidated.py` confinement PASS). Native evidence comes only from `ivg-cont-20261117-iris`, using
fresh prefixes `i51_034349_` (probe) and `i51b_<tag>_` (bindings), each in dedicated graphs. Guidance:
`Verus/uplift-iteration.md` `7c5f718a…` (unchanged). The question cards in `open_questions.md` are unchanged; one
evidence paragraph was added above the q-tmp-002 card. No quarantined material (iteration-13 Cypher `MERGE`) and no
evaluator-private input was read.

Predictions were frozen first ([stats-PAIRS.md](stats-PAIRS.md), commit `7539e169`). They were taken from the API
reference, the USER_GUIDE, the CHANGELOG, the method docstrings (extracted without bodies), two e2e tests and the
owners. Only after that commit were `TemporalIndex.cls`, `TemporalIndexMS.cls`, `TemporalWindow.Latest` and the
engine/store bodies read.

## Result

The temporal analytics readers now have a model whose answers come from the modeled write history: `temporal_stats`,
with 51 verified, 16 controls, each failing exactly its named functions, and a native binding that AGREES on 139
cases with all 16 mutations and the tampered observation detected. Two new Medium defects were found:

- **bug-tmp-103:** `get_distinct_count` answers at least 11 whenever a window holds any target. One target reads as
  11, and three targets read as 11 to 13. The raw HyperLogLog estimator has no small-range correction. Proved for
  every sketch.
- **bug-tmp-104:** two different attribute sets can intern to the same label-set hash. `{"a": 'x","b":"y'}` and
  `{"a": "x", "b": "y"}` share one hash and one resolved text. Proved for all keys and values.

Strengthened inherited findings, with each new mechanism bound at the reader:
- bug-tmp-002: the update double count, now general.
- bug-tmp-003: a rolled-back first write leaves a count with no min or max, so `min` raises and the group row reads
  `(1, 3, null, null)`.
- bug-tmp-009: an unknown metric raises too, as does a whole bucket that a range purge emptied while its edges
  remain.
- F-0508: the ignored burst predicate is now a formal claim.
- F-0509: a value of 0.5 also resolves to non-JSON text, `.5`.

q-tmp-002 gained its mirror case. A delete after `purge_bucket_range` rebuilds the bucket's aggregates but not its
event counters.

## Predictions (35 frozen rows): 30 held, 1 partial, 4 missed

| Rows | Outcome |
|---|---|
| A1, A5-A8, G1-G4, V1, V2, V4, V5, B1-B4, D2-D5, L1-L7, S1, S2 | held. G4 was low confidence: targets use exactly the window. D4 held in direction; the values are estimates (12 → 11). |
| V3 | partial: the collision held. For the update, the docs are silent on the counter; the suspicion held (velocity 2). |
| A2 | missed the documented 0.0: min, max and avg raise `ValueError`. Inherited bug-tmp-009 held. |
| A3 | missed "original value": the whole bucket reads count 2, sum 11. Inherited bug-tmp-002 held. |
| A4 | missed "rollback removes the write": the whole bucket reads count 1, and min/max raise. Inherited bug-tmp-003 held, sharpened. |
| D1 | missed "≈1 vs ≈3 within 26%": 11 vs 11-13. **New bug-tmp-103.** |

Cases added after the source read (not frozen; kept as such):
- A5b/A6b: a delete after each kind of purge.
- An unknown metric.
- Velocity counting an event later than now in now's bucket.
- L8: a rollback of a newer write (latest stays at the committed event).
- S3/S4: label-set quoting and fractions.
- The ms class: explicit now counts; the default now in seconds counts nothing (the recorded divergence, confirmed).

Set aside: bursts ordering for numeric-looking ids; `get_distinct_count(source, "")`; `get_edge_attrs`;
`get_window_sources`.

## Findings

| ID | Severity | Trigger → observable | Formal claim | Status |
|---|---|---|---|---|
| [bug-tmp-103](../../../Verus_verification/bugs_issues.md#bug-tmp-103) | Medium | 1 to ~40 distinct targets → ≥ 11 | `theorem_distinct_nonempty_at_least_eleven`, `theorem_distinct_one_target_is_eleven` | new, E2E |
| [bug-tmp-104](../../../Verus_verification/bugs_issues.md#bug-tmp-104) | Medium | a quote in a string value → another set's hash and text | `theorem_label_sets_collide` | new, E2E |
| bug-tmp-002 | High | update → counted twice; delete leaves the counter | `theorem_update_counts_twice`, `theorem_update_whole_vs_cut`, `theorem_update_then_delete_leaves_velocity` | strengthened |
| bug-tmp-003 | High | rolled-back first write → count without extremes | `theorem_rolled_back_first_write`, `theorem_rolled_back_group_row` | strengthened |
| bug-tmp-009 | Medium | empty or unknown metric → `ValueError` | `theorem_empty_answer_raises` | strengthened |
| F-0508 | (imported) | burst predicate ignored | `theorem_bursts_ignore_predicate` | now formal (imported entry not edited) |
| F-0509 | (imported) | non-JSON canonical text | — (number text is a provider rule) | strengthened in the owner and bug-tmp-104 |

Simplifications: none proposed, tested or retired. Questions: none opened or resolved. q-tmp-002 gained evidence
(additive).

## Owners changed (`.g5/ontology/features/temporal.g5.md`)

- **Extended:** `temporal.stats` (one bullet, Children, Formal), and `temporal.stats.after-purge` (three bullets: the
  return value, whole versus cut after a range purge, and the delete after a range purge, linked to q-tmp-002;
  `uncertain`).
- **New children:** `temporal.stats.window`, `.writers` (uncertain, linked to `temporal.write.update-statistics`),
  `.velocity` and `.distinct`.
- **New owner:** `temporal.labelset`.
- **Definitions:** event counter, label set.

IDs are preserved. `check_ontology.py`: 382 blocks, 0 issues, 17 writing warnings (unchanged count).

Expected results come from the docs and intent:
- 0.0 for empty answers: the docstring.
- "About 26% error": the docstring and the API reference.
- Canonical JSON: spec 204 FR-012 and the docstring.

They do not come from a repair the builder prefers. Where intent is open (update statistics, the q-tmp-002 mirror),
the owner states the as-built behavior and links the question.

## Model

| Model | Verified | Controls | Binding |
|---|---|---|---|
| `temporal_stats` (new) | 51 ([receipt](../../../Verus_verification/results/temporal_stats/20261117T035909Z-prove/receipt.json)) | 16 of 16 EXPECTED_FAIL, each exactly its named theorems | AGREES 139; 16/16 mutations and tamper detected ([receipt](../../../Verus_verification/results/temporal_stats/20261117T040000Z-binding/receipt.json)) |

Every reader is a function of the state, and the state is built only by the modeled writers. No decision is a
constant premise. The theorems are general over every state, coordinate, hash or key wherever that is provable. Only
`theorem_velocity_boundaries` and `theorem_update_whole_vs_cut` instantiate times, and both are over every store and
weight.

Controls:
- Remove the collision guard.
- Updates keep the statistics.
- Journaled counters.
- Whole buckets read raw.
- Cut buckets read the statistics.
- None-checked conversion.
- A raw purge drops the statistics.
- A delete skips missing statistics.
- Bursts filter the predicate.
- A strict threshold.
- Unrounded velocity.
- An ms default now.
- A small-range correction.
- No empty guard.
- Distinct reads whole buckets only.
- Escaped label values.

Trust: no `assume`, `admit` or `external_body`; vstd only. Premises:
- P-INCR: `$Increment` is not undone by a rollback.
- The driver answers None for "".
- SHA-1 decides the register.
- IRIS number text.

Kept failures:
- Prove `20261117T035814Z`: UNEXPECTED, one implicit frame fact. It is now asserted and verified three times.
- Binding `20261117T035703Z`: one mutation was undetected because a later delete masked the purge. The histories
  were split.

## Recount ([member-delta.json](member-delta.json); `member_reach.py`, denominator 4,130)

Active bindings **505 → 537**: 32 newly reached and bound, 7 strengthened, overlap 0, lost 0 (39 distinct
additions). No newly reached member had a locator before.

**Newly reached and bound:**
- `TemporalIndex.cls`: `GetAggregate`, `GetBucketGroups`, `BucketGroupsEvents`, `GetBucketGroupTargets`,
  `GetVelocity`, `FindBursts`, `GetDistinctCount`, `HLLAdd`, `HLLEmpty`, `UpdateHLL`, `RemoveTemporalRow`,
  `RebuildBucketAggregate`, `PurgeRawBefore`, `PurgeBucketRange`, `InternLabelSet` and `ResolveLabelSet`.
- `TemporalIndexMS.GetBucketCount`.
- Engine: `get_temporal_aggregate`, `get_bucket_groups`, `get_bucket_group_targets`, `get_edge_velocity`,
  `find_burst_nodes`, `get_distinct_count`, `purge_bucket_range`, `purge_raw_before`, `intern_label_set` and
  `resolve_label_set`.
- Store: `get_temporal_aggregate` (the deciding conversion), `purge_bucket_range`, `purge_raw_before`,
  `intern_label_set` and `resolve_label_set`.

**Strengthened:** `WriteStores`, `InsertEdge`, `BulkInsertCounts`, `DeleteTemporalEdge`, `create_edge_temporal`,
`bulk_create_edges_temporal` and `delete_edge_temporal`.

**Delegates:** the callers that pass arguments unchanged are justified per row in `decision-links.tsv`.

**Excluded or unassessed:**
- `BulkInsert`: a wrapper not on any Python path.
- The latest-event index members: probe only.
- `GetEdgeAttrs`, `QueryWindowSources`, the erase and migrate members, `RebuildBucket` and the backfill members.

`TemporalIndex.cls` is now 23 of 48 bound; `_engine/temporal.py` is 18 of 45.

**Material predictions changed:**
- Gained: one target answers 11; label sets collide; a rolled-back first write makes `min` raise; a delete after a
  range purge revives the aggregates but not the counters; velocity counts events after now in now's bucket.
- Withdrawn: none.

## Correspondence

The [delta from 50](correspondence-delta-from-50.json) is STALE_ALL for proof and for correspondence. The changed
files are the new model, its binding, the crosswalk and the families. No product file changed. A fresh
[stamp](correspondence-inputs.json) checks as REUSABLE_INPUTS.

## Checks

- `check_ontology.py`: 0 issues.
- `check_findings.py` (`verification_root=.g5/Verus_verification`, with the pre-edit snapshot): no problems. The first
  run flagged the severity order, which was fixed.
- `check_evidence.py`: FRESH, including `temporal_stats` with 51 verified and 16 controls.
- `check_consolidated.py` (G5_GUIDE set): PASS, with 793 decision links resolved.
- Product diff vs pin: no change outside `.g5/` in this iteration.
- `link_verification.py`: not applicable (no TLA models).

## Limitations

- **Latest-event index:** L1-L8 held natively, but no Verus claim covers tlast exactness under delete, purge and
  rollback.
- **Concurrency:** not modeled (q-tmp-001).
- **Weights:** whole numbers in the model and the binding.
- **The 26% claim:** checked only as the ≥ 11 floor and observed large-n values, with no statistical test.
- **`get_distinct_count(source="")`:** the all-sources merge is observed only.
- **Repair proposals:** the HLL correction and the label-set escaping were not run on the product; the controls check
  the model's direction only.
- **Review:** this iteration was not independently reviewed.

## Residual list (first missing step for each)

- **tlast exactness:** an inductive `tlast_exact` invariant over write, delete, purge and rollback in
  `temporal_stats`, with `Relatest`/`RelatestRange`/`TemporalWindow.Latest` bound. The first missing step is a raw
  `newest` spec function and its lemmas over push, remove and filter.
- **`get_distinct_count(source, "")`:** probe whether a named source with an empty predicate raises `<SUBSCRIPT>`
  (`$Get(^KG("tagg", g, b, s, "", "hll"))`).
- **Bursts ordering:** numeric-looking source ids collate first in IRIS. Probe ids like `10` and `9`.
- **`get_edge_attrs` and `get_window_sources`:** small readers that need an owner bullet and a binding row.
- **Legacy `PurgeBefore`:** kills statistics only for buckets that still hold raw edges. A bucket whose raw edges an
  earlier raw purge removed keeps its statistics forever. Probe a raw purge, then `purge_before`.

Carried: the iteration-50 residual list and the consolidated queue.

## Cost

About 30 minutes of builder wall clock (03:36 to about 04:06 UTC). Tokens and currency are not available to the
builder.
