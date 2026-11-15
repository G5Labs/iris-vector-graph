# Minimal root-owned native panel (child does not execute)

Reuse the current `test_470_fhir_task_ownership_e2e.py` fixture approach: initialize
only GraphSchema.get_fhir_graph_schema_sql, insert two task-owned named registration
rows with repo_id X0470, schema names HSFHIR_X0470_{R,S,V}, interval3600, and no
resource rows. `FHIRGraph.Open/Schedule/Unschedule` read registration without
LoadColumns, so no actual FHIR repository should be needed for this bounded path.
This is source feasibility, not a claim that the fixture has already run.

Use root's existing runtime identity/ownership guard. Track exactly the created
registration IDs and Task Manager IDs, read snapshots before/after and remove
only those objects afterward. Task definitions must name only these fixture
graphs. Avoid touching installed system tasks: an alternate safe task can be a
new task-owned `%SYS.Task` object or a second fixture graph's sync task. Do not
start or wait for background scheduled jobs; inspect metadata and clean up promptly.

Minimal useful cases:

1. Schedule new graph at60 then61: same task ID, saved TaskClass/namespace/GraphId,
   DailyIncrement1 then2, persisted interval61. Unschedule removes own object/id.
2. Stale fixture task ID whose object was deleted: Unschedule returns removedfalse
   and clears ID; Schedule creates a new object and records its ID.
3. Existing fixture task belonging to other graph: Schedule and Unschedule each
   refuse, preserving both task snapshot and the caller's registry row. If easy,
   add same owned fixture with alternate TaskClass or namespace and restore it
   immediately; never modify a preexisting system task.
4. Registered interval59 + caller None refuses without writes; caller60 succeeds.
5. F-C1501 boundary: if safe injection exists at **only the registry UPDATE** after
   a confirmed successful task save/delete, observe task/registry state and public
   error, then retry. Do not substitute a pre-call failure for this boundary. If
   a native injection cannot be localized safely, retain as source/adapter-only.
6. Optional Settings list duplicate GraphId/missing GraphId cases on an owned
   fixture task, to corroborate last-key ownership. Preserve raw list ordering.

The fake registration does not make public Status succeed: Status later calls
LoadColumns and scans real FHIR tables. Read final registry task_id/interval via
SQL directly and qualify this as a point projection unless a real FHIR fixture is
already available. OnTask busy/error can be left adapter/source-only rather than
changing SyncOnce or creating background work merely to get a native count.
Native TaskManager outcomes must stay separate from conditional adapter evidence.
