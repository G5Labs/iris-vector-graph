# FHIR task ownership through final readers

As-built transcription at product `3eaa79cf77d3e0a879b2cced634cf2729d81499e`,
foundation input `9e6a876feac7306bd442bacfff4b28a2fac436d4`. Governing intent is
`fhir.graph.lifecycle`; source-first [panel](../../../uplift/consolidated/iteration-8/fhir-PAIRS.md)
inherits [iteration7's independent FHIR survey](../../../uplift/consolidated/iteration-7/next-survey-fhir.md).
Pinned Verus0.2026.10.04.426d8b0, bundled vstd only, four threads. **27 units**
(26 proof declarations plus graph_setting termination); **19 named controls**.
No imports, admits, assumes or external bodies. No product executable body is
proved by this transcription and no independent held-out grade is available.

## Producer, alternate writers and consumer

State contains every admitted registry row and raw task object, across graphs.
Tasks are not prefiltered as own tasks. `graph_setting` scans the raw alternating
Settings string list: only exact GraphId keys in key positions count, the last
match wins, and an odd trailing GraphId supplies the native empty default. `ownership`
checks raw TaskClass, then namespace, then decoded GraphId. The task name is not an
ownership key. Foreign-object refusals derive error replies and an unchanged state;
they are not supplied as an ok boolean. A missing/empty registry ID and a nonempty
stale ID naming no object remain distinct raw inputs with the same allocation/clear
behavior. The stored ID alone never proves that an object exists or belongs here.

The interval caller retains omission separately from an explicit integer0 or
non-integer. Only None forwards0; explicit integers below60 are refused. Native
Schedule uses a positive override or the registered seconds and refuses an effective
interval below60. `minutes` proves upward rounding; stored interval_s remains raw
seconds, while the task's DailyIncrement is rounded minutes. Existing task minutes
and registry seconds may disagree initially: Register can change interval_s without
resaving the task, and restores/provider errors can also leave such states.

`schedule` and `unschedule` follow the actual task write then registry SQL order.
Assign/Save/Delete/Sql fault tags describe provider operation outcomes, not ownership.
A failed Assign/Save/Delete stops before later SQL. A later SQL failure retains the
saved or deleted task and old registry. Unschedule's successful reply includes the
**old** context task ID even after clearing the registry; removedfalse covers stale
or empty IDs. `status` reads the registry task_id and interval independently of the
task map, normalizes interpreted version state, and refuses future versions or a
later provider read failure. No task existence/ownership join is invented for Status.

The generic `theorem_raw_caller_to_registry_status_and_tick` derives the sent and
effective interval, existing/new selection, ownership, saved task, registry fields
and eligible invocation target. It does not take a resolved ownership/target result
as an input. `allocation_frame` is explicit in successful generic contracts: a new
provider ID must be nonempty and unused, while an existing object retains its ID.
**A fresh allocation may equal a nonempty stale registry ID when that ID is unused.**
That neighbor becomes an own task even if later SQL fails, so retry reuses it.
The separate orphan/two-task theorems require the newly allocated ID to differ from
the stale/empty registry ID; the full input domain is retained. Retrying after a
post-delete SQL failure sees a stale ID and succeeds with removedfalse.

`tick` represents the specified TaskManager loader/canonical target and calls
`on_task`. A decoded busy or ok reply succeeds as an invocation; error, thrown
SyncOnce call or JSON/parser failure fails. This is not proof that sync completed.
The general JSON parser/dynamic-object access is a provider boundary; Parsed tags
are decoded string-status fragments, not predictions for arbitrary raw JSON.
The canonical AssignSettings [GraphId,g] loader fragment connects successful writes
to the actual definition's GraphId. Arbitrary native loader behavior on duplicate
or malformed Settings is not established by that connection; last-key ownership
decoding is modeled independently. OnTask itself receives a loaded GraphId property.

## Bound roles and projection limits

| Role | Production member / pin lines | Formal relation | Evidence and qualification |
|---|---|---|---|
| public interval producer | `iris_vector_graph/_engine/fhir_graph.py::FhirGraphMixin.fhir_graph_schedule` :291-300 | `caller_interval` / `public_schedule` | actual Python caller runs; None/0/59/60/61/type boundary |
| public removal caller | same module `FhirGraphMixin.fhir_graph_unschedule` :302-310 | `unschedule` | actual forwarding and returned old-ID/error fields |
| graph canonicalization boundary | same module `_fhir_graph` :56-62; `_validate.py::validate_graph_name` :19-48 | validated canonical g input | actual source observed: no fhir: prefix restriction, NUL stripped, unsafe/default refused; graph normalizer is not newly formalized |
| registry/context producer | `iris_src/src/Graph/KG/FHIRGraph.cls::Open` :1713-1744 | `schedule` registry lookup / `State.rows` | actual native Open on registration-only fixture; raw IDs/intervals are not prefiltered |
| ownership producer | same class `CheckOwnTask` :744-769 | `graph_setting` / `ownership` | raw class/ns/alternating Settings; valid decoded list fragment, no assumed owner flag |
| task writer | same class `Schedule` :667-713 | `effective` / `minutes` / `schedule` | AssignSettings -> Save -> registry UPDATE; actual native accepted/rejected neighbors, SQL-fault ordering source/adapter only |
| alternate task writer | same class `Unschedule` :716-736 | `unschedule` | Delete -> registry clear, stale/no-ID still SQL clear; old ID in response |
| provider task persistence | `%SYS.Task` ExistsId/OpenId/New/AssignSettings/Save/DeleteId, called above | `State.tasks` and `Fault` | external provider; sampled native effects, freshness and pre-effect fault contracts are premises |
| saved-task consumer | `iris_src/src/Graph/KG/FHIRGraphSyncTask.cls::OnTask` :14-27 | `tick` / `on_task` | specified loader plus actual source; root native observes missing-repository failure only, busy/ok/error/parse variants adapter/source only |
| native final registry reader | `FHIRGraph.cls::Status` :303-345 | `status` | task_id/interval point projection plus provider refusal; full counts/FHIR LoadColumns unproved |
| public final reader/error | `FhirGraphMixin._fhir_call` :183-188; `fhir_graph_status` :260-274; `_interp_stale` :65-77 | reply error / `status` | actual Python JSON, errors, version int/None/staleness and future-version refusal run |

Rows/task IDs across every graph are admitted; unrelated rows/tasks have frame
theorems. This is a projection of TaskClass, namespace, Settings and DailyIncrement,
and registry task_id/interval/version. Suspended, StartDate and other unassigned
task properties are not modeled. Name/period writes are inspected/adapter-observed
but not whole-object formal fidelity. A `scheduled` reply or tick target therefore
does **not** establish background activation, timing, eligibility under every task
field, or a running job. TaskManager scheduling/execution remains a provider.

Registry writers beyond these operations include FHIRGraph.Register :235-245,
which can update interval_s while preserving task_id, and generic snapshot restore
of fhir_graphs (`_engine/snapshot.py`:232/259/288) or administrative SQL. Arbitrary
committed rows admit their possible outcomes without claiming their transactions
are verified. External TaskManager edits, deletion and ID reuse likewise supply raw
task maps, not an assumed preexisting own task set. Concurrent transitions during
Exists/Open/Save or SQL are not proved; this package is sequential with faithful
provider reads. The full FHIR sync/current-resource/two-feed graph relation remains
outside scope.

## Provider contracts and inherited finding

g/ns are validated canonical graph/current namespace names. Raw arbitrary graph
coercion is not part of this formal model; the binding explicitly observes its
relevant caller neighbors. Settings are valid decoded native lists of strings;
invalid binary-list decode exceptions, arbitrary scalar cell coercions and other
provider versions are residuals. Malformed decoded **odd** lists remain in scope.
Class and namespace guards precede Settings decoding in the source, so a native
decode failure is not to be relabeled an ordinary foreign-task boolean.

Fault Assign/Save/Delete/Sql is specified **pre-effect at that operation**. Earlier
completed operations remain in state. The model does not prove atomicity of a
TaskManager save/delete/AssignSettings operation or an SQL provider that writes
then raises/loses its acknowledgment. Allocation uniqueness and successful native
Task save behavior are provider premises; the two-task retry is conditional on
that second save succeeding, including general provider name/validation rules.
Open/read failures and arbitrary Settings/native equality/coercion also remain
provider limits. No stronger no-effect-on-any-error claim is made.

Identifier lookup has an explicit external-provider relation: an accepted stored
ID string names that exact task-map key, and the opened object's `%Id()` is that
same canonical string. The model's existing-object ID reuse relies on this
relation; it does not prove a universal native ID parser. Root separately checked
one owned on-demand object with **nine** lookup carriers: canonical string and
integer forms both opened the object and returned its canonical ID; seven strings
with leading zeros, plus prefix, decimal suffix, leading/trailing space or exponent
did not exist/open. No alias counterexample was found in that finite sample. The
object was deleted afterward. Untested normalization/coercion forms and providers
remain unassessed; a provider accepting an alias but returning a different `%Id()`
would require an explicit raw lookup -> returned object ID extension. Arbitrary
stored strings remain representable as missing/stale/foreign/own according to the
task-map/provider relation; no sampled input or theorem domain was removed.

Separate TaskManager/registry ordering is **inherited F-C1501**, not a new defect
or a repair. Current intended all-or-none behavior and existing remediation remain
unchanged. The package represents as-built divergence and alternatives; no human
decision, approved simplification, new issue or hidden evaluator credit is inferred.

## Executed evidence and meaningful controls

`binding.py` executes actual pinned FhirGraphMixin Python methods over a Python
TaskManager/ObjectScript transcription and real in-memory SQLite registry SQL.
**731** caller/state/fault journeys agree; extra retained scenarios cover eight
retry combinations plus orphan unschedule/tick, eight version cases plus a later
status read failure, and eight graph-name cases. The adapter executes ownership,
task mutation, actual registry UPDATE/SELECT and final actual Python reader; it
does not execute native ObjectScript, TaskManager or a FHIR repository. Failure
tags and successful metadata-read projection are conditional provider contracts.
The busy/ok/error/parse cases use a specified OnTask adapter, not an actual native
successful FHIR sync. The binding distinguishes its three actual Python mutants
(valid60 refusal, folded server error, accepted future version) from four adapter
mutants (class, namespace, last GraphId, rollback of saved task on SQL failure).
Each reruns the same journey/reference comparison. No recorded answer is changed
to manufacture a control detection.

Root's [final native20](../../../uplift/consolidated/iteration-8/fhir-native.json)
independently executes actual Python/Open/CheckOwnTask/Schedule/Unschedule,
TaskManager and SQL registry point reads on the identity-checked owned Community
runtime. It confirms new/rescheduled ID/minutes, stale replacement/clear,
other-class/other-graph refusals, missing/duplicate/odd Settings outcomes and
registered59 None refusal versus60 override. **Namespace mutation setup itself
was refused** because the sync class is absent in %SYS; that ownership branch is
source/adapter-only. Direct OnTask and public Status return actual missing-repository
SQL-30 errors: no full successful Status/FHIR job claim follows. No native SQL-fault
injection, post-effect operation fault, background run or race was performed.
All five created task IDs were absent afterward. Native script/results/helper,
selected source inputs and exact pin/export/current identity checks are stamped
by the binding. Earlier18 and20 metadata-predecessor runs are retained separately;
an initial zero-comparison false AGREES was retracted by root, not counted.

45 upstream unit/mock/source-guard tests pass in1.31s pytest (1.82s total).
Child binding about0.6s. Native root runtime0.80s at final metadata run, separately
owned; counts do not merge with adapter cases. Final verifier phase timings and
freshness are in iteration8/fhir-validation.json. No token/cache/currency or full
solver-only CPU measurement is available.

## Replay and attempts retained

```sh
export VERUS_BIN=/Users/ziniuw/.cache/g5-verification/0.2026.10.04.426d8b0/verus-arm64-macos/verus
export VERUS_RUN_THREADS=4 RUN_DIR=/Users/ziniuw/runs/ivg-iteration8-fhir-20261115
export IVG_PIN_DIR=/Users/ziniuw/runs/ivg-consolidated-20261114/pin PYTHONDONTWRITEBYTECODE=1
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/fhir_tasks
python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/fhir_tasks
/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python -B -I .g5/Verus_verification/models/fhir_tasks/binding.py
```

Parse attempts (enum-struct parentheses, reserved exists name, integer literal
suffix) and all raw logs/receipts remain. The 22-verified/2-error retry baseline
was a real unsupported theorem premise: unused fresh ID need not differ from a
stale registry ID. Exact failed source is retained in iteration8/fhir-model-attempts/
retry22-2.rs with hash/receipt. It was corrected with both neighboring outcomes,
not by excluding that input from the model/binding. Early controls ran before
this correction and are not the final positive evidence; final27/19 fresh results
supersede them. Earlier successful21/25/27 baselines, binding receipts and native
attempts remain recoverable. No product, shared ontology/tool, Git or runtime was
mutated by this child.

Crosswalk integration qualification: `_fhir_call` is an exercised wire/error
conversion context, recorded as observation rather than new formal reach. Its
general JSON/status decoding is not newly formalized by the point-status model.
Open's active role is its admitted registry lookup within schedule; repository,
JSON/context fields and provider read failures remain outside that projection.

Final root provider supplement: [same-name native saves](../../../uplift/consolidated/iteration-8/fhir-name-native.json) creates two valid task-owned daily definitions with identical generated Name/class/namespace/GraphId. Both saves succeed with distinct IDs and both are deleted. This corroborates the successful-second-save premise of the conditional two-task outcome for those fields; it is not an actual registry-SQL-failure/retry experiment or a universal validation/allocation proof. The supplemental two saves stay separate from native20/ID9 and add no formal coverage. General name/other-field validation remains a provider limit.
