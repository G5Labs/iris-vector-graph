# Independent source-first FHIR breadth panel

Selected from README's integration entry, docs/FHIR_GRAPH.md and API_REFERENCE,
then `test_231_fhir_sync_task.py`, `test_411_fhir_session_reset.py` and the named
expectations in `test_470_fhir_task_ownership_e2e.py`. No implementation bodies
have been followed for this new survey yet. Product3eaa79cf, foundation iteration6
709a497f; current iteration7 timestamp/CALL/health work is excluded from selection.
No native/runtime/network or security probe is planned. This is builder-visible
breadth discovery, not an independent hidden grade and not a new model request.

FHIR is large and relatively unfamiliar here: the guide includes two change feeds,
transactional batches, current-state resync, reinterpretation, unresolved edges,
canonical definitions and Task Manager integration. Selection was not made from
a missing formal-link percentage. The current source-first cases are material
ordinary operations after a restored registration or repository reset.

| Panel | Ontology / docs expectation | Current formal prediction before implementation inspection |
|---|---|---|
| Task ID missing / existing own task | create once / update that same task; interval rounds up minutes | imported fhir_l2 `scheduled` reuses an ID in its one-graph `tasks` set, else allocates; no class/namespace/GraphId ownership predicate |
| Existing foreign task / stale ID naming no object | foreign refused unchanged; stale cleared on unschedule or replaced on schedule | L1/L2 `Schedule{ok}` / `Unschedule{ok}` take successful/refused decision as input. The model can preserve a supplied refusal but cannot derive it from a raw task row |
| Same class+graph / class or namespace or graph mismatch | only the complete own-task identity can be modified/deleted | L2 tasks are defined to contain this graph's tasks; it does not represent the competing task row or distinguish the three ownership components |
| Unschedule own task / graph already unscheduled | remove own task and registry ID / no task mutation | formal own-task removal exists; actual provider object's delete/save and persisted registry ordering remain premises |
| Task result busy / error | busy succeeds as a scheduled invocation; error becomes failed status | imported progress/Start abstraction assumes task starts SyncOnce when eligible; final OnTask status conversion is not derived there |
| New Rsrc row / later version or delete of an existing resource | different feeds; each moves its watermark atomically with resync, and failure advances neither | imported fhir_l2 explicitly models one graph, one feed with monotone key append and a provided batch endpoint. It cannot by itself derive second-feed key dedup/current version selection |
| Feed maxima below stored watermark / caught-up feed | reset/restore triggers rebuild / no feed work | canonical `fhir.sync.behind` predicts rebuild. One-feed abstract `wm>=n` and modeled erase/rebuild assumptions do not yet establish the real producer's deciding comparison |
| Interrupted reinterpretation / successful pass | leave version old and restart / stamp current only after completion | imported L2 reviewed progress design adds durable cursor, explicitly different from as-built restart; its control preserves that difference, not a new gap to re-count |
| Erase during sync / strict ledger | canonical questions remain undecided | existing G/P formal findings already retain these owner/lock/ledger gaps. Do not invent an answer or count a new bug |

Source-first formal basis already read: G platform only classifies FhirSync as an
undecided strict-write path. Imported `proofs-d1f/src/fhir_l1.rs`, `fhir_l2.rs` and
`fhir_progress.rs` cover one-feed lifecycle/transaction/refinement/progress with
explicit reviewed design changes and controls. Their existence is not ignored;
the new question is which deciding producers and final outcomes they can derive.

Next: trace schedule/unschedule -> real task row -> OnTask -> SyncOnce/status,
and two-feed producer -> RunBatch -> durable watermarks/final graph. Use only
actual pinned Python wrappers and bounded in-process adapters/tests. Retain a
miss if the existing contract already answers it. Quantify tractable new producer
work separately from provider transaction/locking, real FHIR parsing/SQL and
clinical-code numerical premises requiring a different environment.
