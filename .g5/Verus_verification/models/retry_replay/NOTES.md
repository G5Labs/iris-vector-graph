# Completed Counts prefix followed by whole-batch fallback

Product3eaa79cf, foundation9e6a876f, iteration8. As-built transcription, not executable
Python/ObjectScript-body verification. Current baseline **70 verified units =14 new
(13 behavior claims +1 unfolding lemma) +56 imported/rechecked**. All9 named controls
fail their named claims. Bundled vstd only; no new assume/admit/external body.

## Raw producer, effects and reader

The retained [retry panel](../../../uplift/consolidated/iteration-8/retry-PAIRS.md)
uses iteration7's source-derived native4 observations as known builder inputs. The
new boundary is not another clock rule: it composes the actual Counts prefix with
the store's catch and its replay of **every** normalized item through the single
writer, then observes actual stored coordinates and returned counts.

`counts` derives its state from imported `clock::fold` over a prefix of the actual
request sequence. `Fault::None` completes every item and returns normal counts;
`ErrorAfter(k)` completes min(k,length) item operations then supplies an exception
to the Python catch. Zero completed items is prewrite failure; length completed
items includes a lost reply after actual success. The provider supplies a failure
boundary, **not a completed state, expected final rows, or an ownership boolean**.
The prefix's raw caller fields pass the inherited normalization/time/writer rules.
The formal clock sequence is indexed by item, including unused entries for explicit
nonzero timestamps; these are not assumed shared, nonzero or monotone readings.

`run` keeps whole-batch validation before any port call. Empty batches return without
consulting Counts. On an error it starts from the derived prefix state and invokes
the fallback fold over the **entire original normalized sequence** with the single
writer's timestamp interpretation. The failed prefix's counts are discarded; the
fallback counts successful single calls and cannot report collisions. `read` uses
the inherited actual global/window point relation, not a supplied success flag.

Generic theorems establish:

- lost reply after a zero item preserves both current-time and epoch0 outgoing and
  inbound points while returning count1/collision0; prewrite failure has only epoch0;
- a positive explicit timestamp collides on replay, preserving one coordinate;
  an already-present coordinate can report count1 while changing no state;
- ordinary zero success has only current time; a clock reading0 is a legitimate
  overlap where replay has no extra coordinate; reverse suppression stays absent;
- a mixed zero/positive pair with distinct sources, after completed prefix1 **or2**,
  has all three final point observations and count2/collision0; its prefix is derived,
  not assumed. This is a point/content claim, not a newly proved whole row ordering;
- arbitrary valid request sequences have the specified prefix-then-entire-replay
  relation. The specific generic point/count contracts above are the new witnessed
  consequences; a universal new content-equivalence theorem is not claimed.

The new14 units do not turn inherited56 into new coverage. Imported files are byte
unchanged and explicitly stamped in the manifest, including transitive imports.
A provider error midway **inside** WriteStores may leave incomplete raw/structural/
attribute/aggregate state; that operation boundary remains outside this new proof.
Successful fallback item calls are assumed here. Errors during fallback, real TCP
failure, upsert/skip semantics, strict ledger, transaction rollback, aggregate/latest
footprints and concurrent writers remain inherited/open provider boundaries.

## Source roles

| Role | Actual product declaration at pin | Formal item / narrow correspondence |
|---|---|---|
| validation/raw normalization | `_engine/temporal.py::TemporalMixin.bulk_create_edges_temporal` | `run` + imported `clock::batch_valid`; actual complete caller body before store invocation |
| raw timestamp validation | `_engine/temporal.py::_check_temporal_edges` | imported producer; inherited clock role, not a new claim about every field |
| deciding catch/replay writer | `stores/iris_sql_store.py::IRISGraphStore.bulk_write_temporal_edges` | `counts/run`; actual catch resends every normalized item, ignores prefix counts |
| fallback carrier | same file `IRISGraphStore.write_temporal_edge` | imported single carrier/fold; integer0 becomes text0 |
| native primary writer | `iris_src/src/Graph/KG/TemporalIndex.cls::BulkInsertCounts` | `counts` + imported fold; integer0 clock per item and default insert return counts |
| alternate writer | same file `InsertEdge` | fallback fold; text0 remains epoch, accepts collisions |
| persistent effect | same file `WriteStores` | imported `clock::stores::insert`; completed default-insert raw out/in projection only |
| final read | `_engine/temporal.py::TemporalMixin.iter_edges_in_window`, `temporal_window.py::TemporalWindowCursor/event` | `read` + inherited window/cursor relation; actual Python cursor/public event read in binding |
| native final point read | `TemporalIndex.cls::QueryWindow/QueryWindowInbound`, `TemporalWindow.cls::Open/Page` | reused point/window relation; root native4 newly sampled legacy forward reader, provider details qualified |

These are scoped roles, not whole-member guarantees. The payload-normalizing caller,
catch and forwarding store are real; the child does not execute ObjectScript. Other
writers can interfere with those globals, but this sequential default-insert contract
does not assume ownership over every temporal operation. The full source/name gate
must reopen correspondence if competing/new writers change.

## Actual binding and native evidence

[binding.py](binding.py) executes real pinned TemporalMixin caller, IRISGraphStore
normalization/try/catch/whole-batch fallback and the real public paged reader over
an executing Native-port contract. It reuses only the explicit temporal_clock
adapter/reader support, whose whole source hash is stamped. The overridden Counts
port executes the prefix's insert operations before raising; it never supplies
preselected result rows. Its final state, return values and actual reader outputs
are compared to an independent `counts/run` transcription.

**872** cases, **6976 nested window comparisons**,0 mismatches: empty/single/two-item
zero, text0 and100 batches; same/distinct identities; default/named graph; reverse
on/off; no seed or occupied epoch/100/current coordinates; every completed-prefix
cutoff plus normal success; later missing/bad timestamp barrier. Item i's supplied
clock is200+i; the actual source resolves only zero items. Both model and adapter
interpret that as the available reading at item i, not a batch-wide clock.

Four meaningful rejections are required: change final timestamp and re-evaluate the
input-derived oracle, remove the actual fallback loop, change the actual fallback
zero carrier to empty (therefore clock), or stop counting accepted fallback calls.
The untouched normal-success neighbor still passes the fallback-loop mutant. These
are actual source method copies/reader comparisons, not edited!=original checks.
The socket guard is active before product imports and observes0 connection attempts.
The adapter is not IRIS, a network fault, or a native partial-prefix experiment.

Root's immutable iteration7 [posteffect-native.json](../../../uplift/consolidated/iteration-7/posteffect-native.json)
and script are stamped, not rerun by this child. Actual native Counts success is
followed by an injected port exception before caller acceptance; actual fallback
and final legacy windows give counts2/1/3 for zero/positive/mixed and2 for the
prewrite mixed neighbor. This independently supports the completed-whole-batch
and prewrite cases on the owned IRIS runtime. Partial-prefix1 is new adapter/formal
evidence, not a newly executed native prefix fault. No genuine transport failure
or arbitrary clock accuracy/availability claim follows.

## Controls, attempts and disposition

All9 formal controls fail their intended claims: discard prefix effects, resume
only the tail, accept the error reply, use Counts clock in fallback, add failed-prefix
counts, leak failed-prefix collisions, skip the first completed effect, remove raw
validation, or consult a faulting provider for an empty batch. No unrelated syntax
or proof failure is credited. Fresh receipts/logs retain exact controls and source
copies. One initial Python mutant anchor used the wrong indentation; assertion
stopped it before receipt generation. The raw failure is retained; corrected unique
anchor runs the actual catch loop mutation. Initial69 baseline predates the generic
mixed-prefix theorem; final70 supersedes it without narrowing input.

Known bug-tmp-001/F-0502 root consequences are strengthened, not newly counted. No
product fix, accepted simplification, owner decision or new policy question is
introduced. The intended event-time and honest count requirements remain distinct
from these as-built outcomes. Resending only the uncompleted tail is an as-built
mutation control, not an accepted repair or proof that a caller can know a lost
reply's effect. General retry repair requires its own design/policy work.

Replay with inherited Verus/vstd, `VERUS_RUN_THREADS=4`, a fresh RUN_DIR and the
pinned IVG_PIN_DIR, then run `prove`, `controls` and this binding. Expected70/9/AGREES872.
Validation, exact receipt hashes and available costs are in
[retry-validation.json](../../../uplift/consolidated/iteration-8/retry-validation.json).
No convergence claim or independent grading follows from this bounded package.
