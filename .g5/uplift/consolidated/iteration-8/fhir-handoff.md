# FHIR task workflow handoff

Input seal9e6a876f, unchanged product3eaa79cf. New fhir_tasks model represents raw
registry/task maps, raw alternating Settings, derived ownership, public/effective
interval, native task/SQL write order, retry outcomes and final registry/status/
eligible canonical target invocation. It does not prefilter own tasks or take
ownership as an ok flag. Provider outcome faults and allocation frame are explicit.

Expected final **27 verified units (26 theorem bodies, one termination)** and
**19 named changed-rule controls**; actual Python/Task+SQLite binding **731** core
journeys, nine retry/tick scenarios, nine version/read-failure scenarios, eight
graph cases, seven meaningful detections (three product Python, four adapter).
45 upstream unit/mock tests pass. Root independently supplies native20 with honest
namespace/Status/OnTask/provider-fault limits. See [NOTES](../../../Verus_verification/models/fhir_tasks/NOTES.md)
for every source role, exact scope, hashes/receipts, replay and retained attempts.
Final freshness and costs are in fhir-validation.json. Independent grade unavailable.

## Exact canonical recommendation for root

Keep `fhir.graph.lifecycle`'s one-own-task/no-change-on-foreign-ID intent. Add a
specific child (suggested ID `fhir.graph.lifecycle.tasks`) or concise body detail:

> Scheduling uses a supplied integer interval of at least60 seconds, or the
> registered interval when None is supplied, and rounds upward to whole minutes.
> It reuses the saved ID only when that object is this graph's sync task in this
> namespace. An existing foreign object is refused before changes; a stale ID
> naming no object is replaced on schedule or cleared on unschedule.
>
> Task save/delete precedes the registry update. Today a failure in that later
> update can leave them disagreeing (F-C1501); a status ID alone does not prove a
> live own task. Unschedule returns the old saved ID even after clearing the row.
> A scheduled invocation that finds sync busy succeeds as an invocation. A decoded
> error status, a thrown call or malformed JSON fails it. Scheduling does not
> establish a completed sync.

Metadata should link the stable formal file
`../../../Verus_verification/models/fhir_tasks/fhir_tasks.rs` and NOTES. Ownership
declarations are `graph_setting` / `ownership`; writer chain `public_schedule` /
`schedule` / `unschedule`; consumer `status` / `tick` / `on_task`; generic composition
`theorem_raw_caller_to_registry_status_and_tick`. Explain that native full Status
needs a repository and current evidence reads registry SQL directly; source/model
full-reader success remains conditional. Do not tag executable bodies verified.

Retain inherited F-C1501 and its intended atomicity/remedy; do not count a new bug.
The retry extension preserves the fresh==stale-ID neighbor: when allocation reuses
the stale registry ID, even a later SQL failure leaves it pointing at the new own
task. Genuine orphan/two-task outcomes require a different new ID and successful
provider saves. No owner policy, simplification or additional defect is inferred.

## Source-role integration and residuals

NOTES maps actual caller, interval validator, `_fhir_call` final error reader,
native Open/CheckOwnTask/Schedule/Unschedule, external `%SYS.Task` provider,
FHIRGraphSyncTask.OnTask and native/public Status version reader. Canonical graph
normalization and external registry writers (Register/snapshot/admin SQL) are
explicit boundaries rather than whole-method newly modeled claims. No shared
crosswalk or canonical file was edited by this builder.

Current native20 corroborates class/graph/missing/duplicate/odd ownership and
task+registry effects. Namespace setup refusal, missing-repository OnTask/Status,
Assign/Save/Delete/SQL pre-effect contracts, lost acknowledgments, races, allocation/
Name validation, unassigned task fields and full two-feed/current-resource FHIR
projection remain as NOTES states. This is useful incremental work, not convergence.

Root additionally checked nine ID carriers on one owned on-demand object: canonical
string/int opened with matching `%Id()`, while seven alternate string spellings
missed. The object was deleted. This is finite corroboration of the exact canonical
ID lookup/returned-ID fragment, not a universal native coercion proof. The binding
stamps fhir-id-native.py/json/log/helper; model/theorem inputs are unchanged and
no alias case was removed from the admitted domain.
