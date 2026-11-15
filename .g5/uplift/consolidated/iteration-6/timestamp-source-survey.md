# Timestamp production: omitted time, epoch zero and bulk fallback

Read-only future-work selection at product `3eaa79cf`, while iteration6 is being
integrated. No native runtime, Git state, product, ontology, shared tool or register
was changed. This survey does not add current model credit or claim a new defect.
Its new executable evidence is only the Python-to-recording-port probe beside
this file; older native evidence remains inherited.

## Source-first expectations and their authority

Read the temporal user-guide section, CONTEXT definitions, API contract/signature,
and relevant tests before checking the implementation/model boundary. The guide
states Unix-second event time and demonstrates positive explicit timestamps.
CONTEXT.md:66-76 says time is when the event occurred, not ingestion time.
`specs/204-temporal-index-gaps/contracts/python.md` and API_REFERENCE expose
`timestamp=None` on the single write; they do not themselves explain its result.

Initial neighboring cases selected from those sources:

- A positive explicit timestamp100 should reach the same event-time coordinates
  on single and bulk paths. A window at100, rather than the current clock, is its
  distinguishing consumer.
- Explicit0 is the Unix epoch and passes the `timestamp >= 0` input boundary. It
  should not be silently conflated with omission merely because Python considers
  zero falsey. Whether the batch's historical zero sentinel is intentional still
  needs a real policy source; no signed decision authorizing it was found here.
- Single omission/None is an exposed API operation, while a bulk item lacking a
  timestamp is explicitly refused by the modern bulk contract. Do not infer that
  omitted bulk time is an accepted clock request from the single signature.

The tests supply two useful limits. The old test named
`test_timestamp_none_sends_empty_string` (`test_temporal_edges.py:58-62`) checks
only that source"A" appears in the store call; it never checks the timestamp.
`test_temporal_unit.py::test_no_timestamp_defaults_to_zero` explicitly checks
Python's store argument0. Neither observes a persisted timestamp or final window.
The unit contract cannot by itself settle whether that carrier implements the
intended public clock behavior.

## Actual path, with no inferred conversion

`TemporalMixin.create_edge_temporal` (`temporal.py:289-299`) validates and int-casts
an explicitly supplied timestamp, but maps None/omission to integer0. The actual
`IRISGraphStore.write_temporal_edge` (`iris_sql_store.py:2655-2692`) serializes it
with `str(timestamp)`, yielding string"0". `_call_classmethod` (`:1085-1088`)
checks namespace and forwards all arguments to `classMethodValue` unchanged.
No Python layer inspected here converts0 or string"0" to empty string.

`TemporalIndex.InsertEdge` (`TemporalIndex.cls:46-65`) substitutes the clock only
when its timestamp argument equals empty string. It then calls WriteStores with
that resolved time. Its default formal argument is empty string; the Python
caller does not leave that argument out.

Bulk first runs `_check_temporal_edges` (`temporal.py:138-154`): an absent, None or
empty timestamp with no alternate timestamp key is refused before the store call.
Zero is accepted. Normalization (`:427-441`) uses
`int(e.get('ts') or e.get('timestamp', 0))`; the store constructs JSON `ts` from that
normalized integer (`iris_sql_store.py:2719-2757`).

`TemporalIndex.BulkInsertCounts` (`TemporalIndex.cls:151-182`) reads
`ts = +item.%Get('ts')` and substitutes its current Unix-second clock when ts==0.
The clock is evaluated inside the per-item loop, not once for an entire batch.
The comment about resolving once concerns write mode, not a shared timestamp.

On a BulkInsertCounts exception, the real store fallback (`iris_sql_store.py:2759-2785`)
reuses the normalized raw timestamp through `write_temporal_edge -> InsertEdge`.
Thus it sends string"0" again instead of sending the batch's already-resolved
clock coordinate. No empty-string conversion occurs in this alternate Python
writer either. A legacy/missing batch procedure can take this fallback before
any batch write; partial failures are also possible but were not reproduced here.

## Reproduced Python boundary evidence

Run from repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python -B -I .g5/uplift/consolidated/iteration-6/timestamp-proxy.py
```

Actual pinned TemporalMixin caller, actual IRISGraphStore methods and its actual
`_call_classmethod` ran against a recording Native API endpoint. Namespace/ledger
setup guards and native endpoint are substitutes; no IRIS connection was opened.
Results in timestamp-proxy.json/log: **8 single and 11 batch cases**, plus a
specific empty-for-None carrier mutation detected. Probe wall0.00651s; whole
command wall0.614s. No native class execution, driver marshaling, clock or database
state/window is newly observed.

| Input / route | Actual Python port observation |
|---|---|
| single omitted or None | InsertEdge timestamp string"0" |
| single explicit0 or text"0" | InsertEdge timestamp string"0" |
| single100 or text"100" | InsertEdge timestamp string"100" |
| single empty text or negative1 | refuses before port (int/validation) |
| bulk short/long timestamp key0, or text"0" | BulkInsertCounts JSON ts0 |
| bulk100 | BulkInsertCounts JSON ts100 |
| bulk timestamp absent/None/empty | ValueError before port |
| bulk short ts0 plus long timestamp100 | accepted and normalized to100 |
| batch unavailable before writes, raw ts0 | records batch attempt, then InsertEdge timestamp string"0"; wrapper reports count1 |
| same fallback with100 | InsertEdge timestamp string"100"; wrapper reports count1 |

The two-alias case is an additional retained producer neighbor, not a new defect
claim: falsey short ts0 defers to the long key. A future equivalence claim must
state alias precedence rather than assuming "first key present".

## Existing evidence and current formal boundary

After freezing the product cases, checked the current canonical owner/registers
and relevant models. The clock discrepancy is **already recorded twice**:

- `bug-tmp-007` has the exact None -> Python0 -> string"0" source chain, the weak
  unit-test assertion, and the recent-window consequence; its original G entry
  remains source-only/Suspected, Low.
- Imported `F-0502` states the same missing-time trigger and reports a historical
  live observation on the playbook arm: single stored at0, bulk ts0 stored at
  1794609910. That is inherited native corroboration at the pin, not a run by this
  survey. It also proposes preserving explicit0 rather than using it as a missing
  value; that proposal is not an approved implementation change.

`temporal.edge` states the intended missing-time clock rule, and its metadata
already discloses the divergence. The main human-readable rule should expose
the API-specific as-built outcomes when this area is extended; runtime behavior
does not authorize weakening the intended requirement. The two existing findings
share the missing-time trigger/consequence and deserve reconciliation, retaining
both IDs/provenance and the stronger inherited evidence rather than counting a
third discovery.

The material gap is **formal timestamp production**, not an absent citation:

- G `temporal.rs::Coord` receives `ts:int` already resolved. `bulk_counts`,
  `fallback` and `bulk_write` all pass the same `Edge.c` into WriteStores. Existing
  batch/fallback proofs are about those provided coordinates and cannot tell
  raw bulk0 -> clock from raw fallback0 -> epoch.
- Imported active `proofs-d1c/src/tagg_l2.rs::TL2::Write` also receives ts directly;
  it models one bucket's stores, not omission/clock resolution.
- Current C `temporal_restore` receives an Edge tuple with timestamp already in
  it. Its successful epoch0 restoration/window evidence does not establish how
  each original write API chooses that timestamp.

The already-linked bulk fallback therefore offers a concrete partial-behavior
challenge. Under the inherited native semantics, a valid bulk0 write may land at
now with Counts available and at epoch0 when Counts is unavailable and InsertEdge
fallback succeeds, with a successful count in both cases. If a batch wrote a
prefix before failing, fallback timestamp resolution could also alter whether
that prefix is a collision or a second event. The latter is a source-derived
candidate only; ordering/reachability and final observations still need native
evidence, and no extra defect is counted.

## Recommended next check

This is a tractable iteration7 producer gap. Add a raw input / entry-point /
fallback / clock-resolution layer before an existing event-state/window contract.
Keep positive100 as a permitted neighbor; keep missing bulk time refused before
effects; distinguish omission, explicit0, empty native argument and alias0/100.
Represent the actual selected writer after a batch refusal, not a supplied
"resolved timestamp" decision. A per-item clock input should not accidentally
assume one fixed reading for an entire batch or across retries.

Root can use its own disposable runtime later to observe explicit0/None at the
single and Counts ports, the public batch-to-single fallback, and final epoch
versus recent-window answers. This survey does not replace that observation with
the recording endpoint. Keep historical F-0502 as inherited, the new Python
carrier probe as reproduced, and any new native run as separately reproduced.
Question/repair choices remain with the owner if implementation is ever requested.
No security scenario, new issue, accepted simplification or owner decision was
created. The formal producer gap can change a material prediction, so it is useful
next work and does not support convergence.

## Source identities

Survey recorded UTC 2026-11-15T17:55:10.916912+00:00. Source SHA-256:

- `docs/USER_GUIDE.md`: `4ca75aef844ec8122126d941677dd8e05a55f142f15c7adce36ac7bbec385551`
- `CONTEXT.md`: `f6c1367d11b11c66db9af4de77d762ab7be87170211b733ead195fdb18bad6d5`
- `tests/unit/test_temporal_edges.py`: `99639b97f55a27939c95deb8ff03885115351cce43edaa84e71b5d6ac76bffec`
- `tests/unit/test_temporal_unit.py`: `dfb5a09d1a0cdba1faec2f30b8f0e01849a0082122154748f6502ea91f7cff30`
- `iris_vector_graph/_engine/temporal.py`: `0dab28a4a76d088d31b87d4dea23699b3e15a33fc0a96785f66b1defdb164802`
- `iris_vector_graph/stores/iris_sql_store.py`: `737df8a794a979d2c2e4f3af100508fd05c1907893ec2fa65f2fc440e34ff153`
- `iris_src/src/Graph/KG/TemporalIndex.cls`: `4b00154628b5b77ae3bbae26c857f81d934d09d73bc271f65cb1e202d616cb54`
- `.g5/Verus_verification/models/temporal/temporal.rs`: `9bade6a42c06775640604bf1c3cd7d9ad940878c784ee4fee5fde0ea6576b950`
- `experiment/playbook-completion/proofs-d1c/src/tagg_l2.rs`: `01b70bb9170d2916c0c911a9a5a17ca9ef7cfd9eda2bac50682e7e84d91cb4f7`
- `.g5/Verus_verification/models/temporal_restore/temporal_restore.rs`: `ba855930771f858e31c543ca268e465d80df35e21165c0baa2bf7b5b938c4141`
