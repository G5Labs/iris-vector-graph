# Raw temporal timestamp to stored window coordinate

Product `3eaa79cf77d3e0a879b2cced634cf2729d81499e`, input foundation
`709a497f1635f49b9f2f82b37cf4fd83e1e1cdd1`. Source-first panel:
[timestamp-PAIRS](../../../uplift/consolidated/iteration-7/timestamp-PAIRS.md);
prior [source survey](../../../uplift/consolidated/iteration-6/timestamp-source-survey.md).
Verus `0.2026.10.04.426d8b0`, bundled vstd, four threads. This is an as-built
transcription, not verification of executable Python/ObjectScript bodies.

## Contract and neighboring outcomes

`Raw` retains missing, None, empty text, integer, successful nonempty integer text,
failed conversion, and other successful int conversions together with their
original Python truthiness. `single_payload` derives the actual None/missing ->0
carrier and explicit nonnegative validation. `bulk_shape`, `bulk_selected` and
`bulk_payload` independently derive timestamp availability, falsey short-alias
fallback and integer conversion. Other required roles/unknown-key checks are an
explicit `shape_ok` boundary; this is not a supplied timestamp decision. `Bad` corresponds to the tested truthy nonnumeric text, not every failing Python
object. Falsey non-scalar objects such as an empty list/dict can select a long alias
before conversion and are outside this codec relation. Parsing arbitrary Python
objects itself is not proved. Boolean/finite-fractional examples
are executed by the actual product binding rather than silently excluded.

`coordinate` selects the real normal Counts writer or prewrite-unavailable
InsertEdge fallback. `single_clock` treats an empty native argument as clock and
numeric0 as epoch; `bulk_clock` treats numeric0 as clock. `write` derives the event
coordinate, invokes the reused global writer and derives insert/collision counts.
The fallback reports successful calls even on collisions. `observe` uses the
reused actual global/window projection. Generic raw-input-to-reader theorems cover
single and bulk inputs; the producer's timestamp is derived in each contract,
never supplied as an already-resolved edge field. Exact-zero/recent-window
theorems retain the decisive consequence of the known mismatch.

`call_batch` retains the caller's whole-batch validation barrier: every item is
checked and normalized before the first port write. A later missing timestamp or
failed conversion therefore prevents an earlier valid item from reaching the
port. `fold` composes each default-insert item using an individual clock reading;
empty batches succeed with count0 without consulting a provider. There is no
assumption that a batch's clocks are shared, nonzero, monotone or stable on retry.
The per-item clock sequence supplies readings indexed by item, used only when
needed; a faithful execution supplies one reading per item. The missing-clock
default in the total spec is a test-environment completion, not a product rule.

Fifty-six verified units include **31 reused** temporal_restore/window units and
**25 new** units (24 theorem bodies plus the recursive fold's termination check).
Do not count imports as newly modeled behavior. Sixteen altered rules fail their
named claims; the manifest identifies each theorem. There are no new assumes,
admits, external bodies or trusted axioms.

## Product roles, scope of each link

| Role | Product member at pin | Formal relation | Correspondence |
|---|---|---|---|
| raw single producer | `iris_vector_graph/_engine/temporal.py::TemporalMixin.create_edge_temporal` :246-304 | `single_payload` / `call_single` | actual caller, int conversion and validation run; None does not become empty wire |
| input validator | `iris_vector_graph/_validate.py::TemporalEdgeInput` :207-212 | `single_payload` | explicit timestamp nonnegative boundary; whole Pydantic class is not verified |
| bulk shape/alias producer | `iris_vector_graph/_engine/temporal.py::_check_temporal_edges` :138-154 and `TemporalMixin.bulk_create_edges_temporal` :390-453 | `bulk_shape` / `bulk_selected` / `bulk_payload` / `batch_valid` / `call_batch` | actual Python shapes/aliases/int conversion and late-invalid barrier run |
| single port producer | `iris_vector_graph/stores/iris_sql_store.py::IRISGraphStore.write_temporal_edge` :2655-2692 | `NativeTime::Number` / `write` | actual str(integer) port argument; no0-to-empty conversion |
| batch producer and alternate writer | `iris_vector_graph/stores/iris_sql_store.py::IRISGraphStore.bulk_write_temporal_edges` :2719-2785 | `call_bulk` / `call_batch` / `fold` | actual JSON ts integer and prewrite exception -> actual single fallback; counts contrasted |
| forwarding boundary | `iris_vector_graph/stores/iris_sql_store.py::IRISGraphStore._call_classmethod` :1085-1088 | same numeric carrier | actual forwarding runs; namespace guard and native endpoint substituted in child binding |
| single server decision | `iris_src/src/Graph/KG/TemporalIndex.cls::InsertEdge` :46-65 | `single_clock` / `write` | source + root's actual empty versus"0" native cases |
| alternate server decision | `iris_src/src/Graph/KG/TemporalIndex.cls::BulkInsertCounts` :151-182 | `bulk_clock` / `fold` | source per-item clock call + root's zero/positive native cases; no fixed-clock assumption |
| deciding global writer | `iris_src/src/Graph/KG/TemporalIndex.cls::WriteStores` :82-108 | reused `stores::insert` | default insert out/reverse/time coordinate and collision footprint only; other modes/aggregate structures remain inherited G coverage, not new claims |
| public paged final reader | `iris_vector_graph/_engine/temporal.py::TemporalMixin.iter_edges_in_window` :539-580; `temporal_window.py::window_spec`, `TemporalWindowCursor`, `event` | `observe` / reused `stores::weight` and `paging` | actual Python cursor and event projection over executing adapter; final coordinate, weight, graph, endpoints, reverse suppression and empty sources observed |
| native final point readers | `iris_src/src/Graph/KG/TemporalIndex.cls::QueryWindow` :688-721 and `QueryWindowInbound` :1406-1439; `TemporalWindow.cls::Open/Page` | reused `stores::weight` / `paging` | global/time/graph point membership projection; root independently observes public `get_edges_in_window` forward path. Whole legacy JSON serialization/predicate scan/inbound native behavior is not newly verified |

These are specific behavior roles, not whole-method links or a prevalence score.
`WriteStores` receives the newly derived timestamp: its coordinate input is no
longer an unchecked resolved-time premise of this package. Direct empty native
argument is a separate route, not a representation produced by public None.

## Binding and native evidence

The [binding](binding.py) runs pinned actual TemporalMixin caller, IRISGraphStore
methods, public iter_edges_in_window, window_spec, TemporalWindowCursor and event
against an executing in-memory specified Native API adapter. It compares 1,564
caller cases and 12,512 window observations; additional cases retain distinct
per-item clocks, native-empty sentinel, empty batch and two late-invalid barriers.
Four detections change the None carrier, alias precedence, fallback zero carrier
and final observed timestamp. Native-port adapter code is a Python transcription,
not IRIS: its clock/store/window agreement is not independent provider evidence.
Namespace/ledger setup and structural/SQL mirrors are substituted; default insert
and unchanged graph identities are explicit. Receipt hashes root/model/manifest,
both imported models, binding helper and root's native scripts/results/helper.

Root independently ran [timestamp-native.py](../../../uplift/consolidated/iteration-7/timestamp-native.py)
and retained [timestamp-native.json](../../../uplift/consolidated/iteration-7/timestamp-native.json)
on its identity-checked owned IRIS Community2026.1.0.234.1 runtime. **Nine** worlds
agree: four public single forms, bulk0/100, fallback0/100, and direct empty native
argument. Actual persisted public windows confirm epoch0 versus local wall-clock
bounds, correct graph and inclusive epoch endpoints. Duplicate positive100 yields
normal count0/collision1 versus fallback count1/collision0. The fallback failure is
injected before delegation/effects; all other native calls are unchanged. This
child never connects to that runtime. Native current time is bounded by sampled
local UTC seconds with tolerance, not proof of clock accuracy, monotonicity or
cross-machine synchronization. Root's initial wrong-keyword harness failure is
retained in timestamp-native-initial.log, not treated as a product failure.

107 relevant upstream tests pass (single/bulk caller, shape rejection, counts and
paged window reader). Their mocks do not establish persisted clock behavior.

## Limits and inherited findings

`bug-tmp-007` and `F-0502` describe one already-known missing-time mismatch with
different provenance; no new defect count is claimed. Bulk negative validation
is inherited F-0513. This package closes the missing raw-producer/formal boundary
and strengthens observed correspondence; it does not authorize changing intent
to match the defect or choose a bulk explicit-zero policy.

The modeled provider refusal happens before any effect. WriteStores can reach
other writers after raw stores, so neither an arbitrary server exception nor a
partially executed Counts call is claimed atomic here. Partial-prefix fallback,
errors after raw/global/structural effects, strict ledger transactions, upsert/skip
semantics, aggregate/latest/structural store consequences and concurrency remain
outside this package's new clock claims. Existing G proofs about equal resolved
coordinates must keep that qualification. General ObjectScript/native Integer
coercion (overflow/fractional/nonnumeric forms), other runtime versions, arbitrary
Python int objects, full JSON parsing and TemporalIndexMS are residuals. Native
tests support the sampled integer/string/empty fragment, not every marshaling case.

## Replay and retained costs

```sh
export VERUS_BIN=/Users/ziniuw/.cache/g5-verification/0.2026.10.04.426d8b0/verus-arm64-macos/verus
export VERUS_RUN_THREADS=4 RUN_DIR=/Users/ziniuw/runs/ivg-iteration7-timestamp-20261115
export IVG_PIN_DIR=/Users/ziniuw/runs/ivg-consolidated-20261114/pin PYTHONDONTWRITEBYTECODE=1
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/temporal_clock
python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/temporal_clock
/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python -B -I .g5/Verus_verification/models/temporal_clock/binding.py
```

Raw receipts/logs are in results/temporal_clock and the isolated RUN_DIR. Retained
attempts include missing VERUS_BIN setup, initial binding mutation-anchor ambiguity,
and 55-verified/1-error proof while the new batch theorem needed recursive unfolding.
The latter was repaired by explicit fold unfolding and the generic raw-reader
lemma, without changing its input domain or oracle. Earlier 50/52-unit successful
baselines/controls remain; final receipts supersede them. Earlier runs used the
runner's default8 threads, found during receipt inspection; the final proof and
all controls are explicitly replayed with inherited4, retaining the earlier runs.
Binding is about1.04s;
upstream tests2.14s total (pytest1.58s). Final-phase verifier costs and receipt
freshness are in iteration7/timestamp-validation.json. No independent grade exists.
