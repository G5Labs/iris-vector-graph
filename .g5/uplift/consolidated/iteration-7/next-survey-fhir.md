# FHIR breadth audit and next-work recommendation

Source-first [panel](next-survey-PAIRS.md) is retained. Product3eaa79cf,
iteration6 foundation709a497f. Selection came independently from README's FHIR
entry, the FHIR guide, API reference and ordinary lifecycle/reset/task tests.
No product, shared foundation, Git, native runtime, network or security scenario
was changed/run. This is builder-visible discovery, with no independent grade.

## Result

FHIR remains a substantial material complement. The iteration6 mechanical reach
snapshot lists **154 FHIR-named members without a valid C/G role link and zero
FHIR-named linked members** under that search. That is a census of that snapshot,
not zero formal coverage: imported P L1/L2/progress models already reason about
FHIR lifecycle and one feed. Large source/file counts do not establish prevalence
or rank the next work by themselves.

Strongest tractable next package: **derive scheduled-task ownership and lifecycle
from the registry ID and actual task rows, then follow it to OnTask and the caller's
status/error**. The current code distinguishes a missing object from an existing
task with the wrong class, namespace or GraphId. The imported proof takes `ok:bool`
and defines its task set to contain only this graph's tasks, so it cannot derive
these neighboring outcomes. This is a missing producer/alternate-writer/final-reader
contract, not evidence of a newly broken ownership check. The source matches the
canonical intended refusal on ordinary restored registrations.

The larger two-feed/current-resource projection remains material and is costlier:
the current imported model explicitly covers one append feed and a set of keys,
not Rsrc/RsrcVer SQL production, version/deletion payloads, unresolved/canonical
edges or exact final node/edge equality with rebuild. Task work can settle a useful
boundary without pretending that the full FHIR projection is then verified.

## Deciding writers and final readers traced

1. `_engine/fhir_graph.py::fhir_graph_schedule` (:291-300) rejects explicit
   non-integers or seconds<60; None sends0 and means retain the registered interval.
   Explicit0 is refused at this caller, so do not model it as accepted omission.
   Graph validation requires a safe nonempty named graph; registration existence
   is a server check. `fhir_graph_unschedule` forwards the graph. `_fhir_call`
   (:183-188) parses the actual JSON and raises FHIRGraphError only for statuserror;
   busy returns normally. The bounded probe executes these real pinned bodies.
2. `FHIRGraph.Open` (:1713-1744) reads persisted task_id and interval from the
   registry. `Schedule` (:667-713) uses a positive override or the registered
   interval, refuses an effective interval<60, and rounds it upward in minutes.
   It checks existence, opens that exact task and invokes `CheckOwnTask` before
   assigning any task properties. Missing object/stale ID creates a fresh task.
3. `CheckOwnTask` (:744-769) decides from TaskClass, NameSpace and decoded Settings
   GraphId; all must name this graph in this namespace. It scans alternating
   setting keys/values and retains the last GraphId key if repeated. A missing
   GraphId remains empty and refuses. This deciding producer is absent from L2's
   prefiltered own-task set; setting decode must not be replaced by an assumed
   ownership boolean in a new model. Full native Settings encoding/equality is
   a provider boundary to validate, not SQLUPPER behavior borrowed from history.
4. After successful ownership, Schedule AssignSettings then saves `%SYS.Task`,
   then separately updates `fhir_graphs.task_id,interval_s`. Unschedule (:716-736)
   checks the same ownership, deletes the task, then clears registry task_id.
   An existing foreign task refuses before these writes; a stale ID clears on
   unschedule with removedfalse. Valid own task reschedule retains its ID.
5. `%SYS.Task` is a competing persistence owner. `FHIRGraphSyncTask.OnTask`
   (:14-27) calls SyncOnce with its own saved GraphId, parses the result and turns
   only statuserror or a thrown exception into failure. Busy succeeds; task
   invocation is not proof that a graph sync completed. `FHIRGraph.Status`
   (:303-345) reads the registry ID/interval and actual graph/feed counts; Python
   `fhir_graph_status` normalizes interpretation_version and derives staleness,
   refusing a future version. It does not independently verify task_id ownership.

Provider save/delete and registry update are separate writes. F-C1501 already
records this in both Schedule and Unschedule; the imported L2 reviewed design
makes Schedule atomic and keeps an as-built control. No new defect count is
claimed for either ordering. A future as-built model must retain saved-orphan or
deleted-task/stale-registry outcomes after the later SQL failure, as well as the
stronger no-change guarantee for an ownership refusal. Arbitrary method errors
cannot all be modeled as pre-effect refusal. Concurrent task deletion/ID reuse,
object-open races, Task Manager scheduling and cross-database transaction behavior
are additional provider/competing-writer boundaries, not discharged by the probe.

## Two-feed producer and retained misses

`SyncOnce` (:543-626) obtains the graph lock with zero timeout. It reads both
repository maxima; **either** maximum below its stored watermark triggers a
rebuild, after releasing the old lock so Rebuild takes it itself. Equal/caught-up
maxima simply skip that feed. New Rsrc IDs and later RsrcVer IDs are selected with
`ID > from AND ID <= to ORDER BY ID`. Batch contents are keys, while the watermark
is the last feed ID. An unconditional tail batch moves to the captured maximum
even when no remaining row was scanned; IDs need not be dense. Resource keys can
repeat across feeds or versions.

`RunBatch` (:1923-1977) starts a transaction, syncs definitions, resyncs each not-yet-
Done key, follows affected dependants/pending keys, updates only the named feed's
watermark, then commits. In-memory watermark advances after commit. SyncOnce catch
rolls back its open transaction and records last_error outside it. `ResyncKey`
(:2039 onward) reads the repository's **current** state, rather than an archived
feed payload. The source's end-to-end convergence needs a relation between feed
rows, current resources, derived graph and both durable cursors; assigning a
preselected successful batch endpoint is insufficient for that relation.

Kept misses/candidates rather than turning each into new model credit:

- Existing single-sync exclusion is already a substantive P contract. Bind its
  deciding lock/source role if extending it; do not create another boolean lock
  model merely because the G/C member census lacks a link.
- Batch rollback with its watermark is already covered abstractly by L1/L2 and
  matches the source transaction boundary. Faithful IRIS rollback across every
  actual side effect is still a provider premise needing evidence, not another
  new transactional theorem obtained by assuming the whole batch atomic.
- Reinterpretation restart and its progress difference are explicit existing
  R15-P/INT-F5.7 controls. The proposed durable cursor differs from the pin; it
  must not be presented as shipped behavior or rediscovered as a new issue.
- Erase/sync interference and strict-ledger ownership are already unresolved
  canonical questions (HD-1503 / fhir.sync.other_writers and fhir.ledger). No new
  owner decision was inferred, and no native race/security probe was attempted.
- Patient-compartment/canonical/version resolution and numerical PPR grouping
  are not settled by this lifecycle survey. They remain unexamined residual
  subworkflows here, not classified trivial or covered by wrapper tests.

## Executed evidence and costs

[Actual Python probe](next-survey-fhir-probe.py): **288** schedule/sync/unschedule
wrapper cases and **8** final status-version cases agree, with two changed-rule
detections. The Native API endpoint only records arguments and supplies JSON;
it does not execute ownership, Task Manager, SQL, locks or FHIR resources. It
distinguishes None from refused explicit0/<60, valid60 from61, invalid graph from
named graph, returned busy from server-error exception, current/old/missing
interpretation from future-version refusal. Probe elapsed0.00267s; command0.486s.

**45** existing unit/mock/source-guard tests pass (FHIR wrappers, sync-task source,
session reset, lazy FHIR tables): pytest1.16s, total1.65s. These observe/guard the
Python and source contract; no live Task Manager or two-feed behavior is claimed.
Raw paths, inputs and costs are in the JSON/log files beside this survey.

## Next-step cost and convergence decision

Task ownership is a bounded next-iteration model: raw task map plus settings list,
registry lookup, same/missing/foreign selection, effective interval, provider
save/delete/SQL outcomes and real final reader. Include named changed-rule controls
for each ownership component, stale-vs-foreign distinction, provider ordering and
busy-vs-error. Estimated builder cost is one iteration (roughly30–90 minutes plus
review), not a measured promise. Actual Task Manager observation should be root-
owned and serial. The current repository's ownership E2E fixture seeds only the
lazy registration tables with two ordinary graph rows; Open/Schedule do not need
to query an actual FHIR resource table. Thus this narrower provider check may be
possible on Community without a full IRIS for Health repository, despite the old
F-C1501 note's environment limitation. That feasibility is source/test evidence,
not a newly executed native run by this survey.

The full two-feed-to-rebuild claim likely needs several hours and a legitimate
IRIS for Health FHIR repository/fixture. Existing upstream E2E tests provide a
starting fixture; obtaining its available environment and faithfully representing
canonical/compartment parsing may dominate cost. A purely in-process SQL adapter
could settle selection, sparse IDs, duplicate keys and commit/error bookkeeping,
but cannot settle native FHIR JSON/storage/transaction semantics by itself. Exact
cost is unresolved until that provider inventory is inspected by the owning root.

The canonical task rule does predict the desired own/foreign neighbor, but the
current active model does not derive it. The wider current-state feed/graph relation
also remains open. **This audit does not support convergence or diminishing returns.**
It recommends a tractable useful next package and preserves the expensive unknowns.
