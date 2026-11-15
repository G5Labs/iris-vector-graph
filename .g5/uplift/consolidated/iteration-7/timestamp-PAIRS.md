# Timestamp producer panel, frozen before the iteration7 model

Product pin `3eaa79cf77d3e0a879b2cced634cf2729d81499e`; inherited foundation
`709a497f1635f49b9f2f82b37cf4fd83e1e1cdd1`. This is builder-visible discovery,
not a held-out grade. The iteration6 [source survey](../iteration-6/timestamp-source-survey.md)
and its raw recording-port cases are already available inputs. No live native
runtime is used by this agent.

## Predictions retained before new model inspection

The owning `temporal.edge` intent calls for current event time when single time is
omitted. Explicit zero is a legal epoch coordinate at the single input boundary;
a positive explicit time is event time on either write route. Modern bulk items
require a timestamp rather than inheriting the single API's omitted-time rule.
Existing fixed-coordinate G `temporal::bulk_write` and C `temporal_restore::insert`
cannot derive any difference caused by raw zero, a clock call or fallback: their
input edge already contains its resolved timestamp. Their existing equivalence
therefore predicts equal states only for equal **resolved** coordinates.

| Neighbor | Intended/public prediction | As-built prediction from the frozen survey to test |
|---|---|---|
| single omitted / explicit100 | omitted uses clock;100 stays100 | None/omitted port sends"0", stored epoch;100 stays100 |
| single0 / bulk0 with nonzero clock | explicit epoch should remain epoch; bulk policy unresolved | single epoch, normal bulk clock |
| normal bulk0 / prewrite-unavailable fallback0 | same accepted write should retain its chosen event coordinate | normal resolves clock, fallback sends"0" and stores epoch |
| bulk100 normal / fallback | same event-time coordinate100 | equal coordinates100 |
| missing/None/empty bulk / explicit0 | first group refused;0 accepted | no port/state change vs ts0 port |
| short alias0 + long100 / short text"0" + long100 | record exact alias precedence | falsey numeric0 selects100; truthy text"0" selects0 |
| short0 + longNone / short0 with long missing | shape has a time in both; conversion still decisive | presentNone raises int conversion; missing defaults0 |
| single negative / bulk negative | preserve known validation boundary | single refuses, bulk carries negative (known F-0513) |
| duplicate normal / duplicate fallback | coordinate plus actual count must remain distinguishable | normal collision count; fallback counts successful calls even if collision |
| different per-item clock values / same clock | do not assume batch-shared or monotonic time | each bulk item resolves at its own call; current-clock window may differ |
| provider InsertEdge refusal / accepted empty native argument | failed write changes no state; empty direct native arg invokes clock | public Python None never produces the empty native arg |
| inclusive timestamp endpoints / wrong graph or outside window | admitted exact coordinate appears in correct graph window only | final temporal window reads the written coordinate, not returned count |

Known discrepancy `bug-tmp-007` / `F-0502` is one inherited missing-time issue with
two provenance records, not a new discovery. Bulk negative validation is inherited
`F-0513`. The alternate fallback clock consequence must be tested without claiming
partial-prefix behavior or a new independent defect count. Clock domain and native
integer marshaling remain explicit provider limits until root's serial native
observations supply evidence.

## Planned evidence and exclusions

New proof transcribes raw caller normalization, Python payload creation, alternate
prewrite fallback, server timestamp resolution and the existing global writer / final
window projection. Imported proof units will be reported separately. Actual pinned
Python bindings use an executing in-memory native-port adapter for globals/window;
that adapter is a specified transcription, not IRIS. Root alone runs any native
probe. Keep failed attempts, decisive altered-rule controls and all sampled misses.

Graph/edge identity, accepted integer/text timestamp fragment and zero/clock/refusal
are in scope. Unicode/nonnumeric ObjectScript coercion, fractional/overflow native
marshaling, millisecond class behavior, structural mirror transactions, dynamic
JSON parsing, strict ledger and partial-prefix batch failure are explicit residuals.
