# PROOFS-D1F: Verus L1/L2 refinement for modules 15 (integrations), 16 (interfaces) and 17 (operations) (proof debt D-1, playbook §3.3)

Crate `experiment/playbook-completion/proofs-d1f` (`ivg-d1f-proofs`), Verus 0.2026.10.04.426d8b0, vstd
0.0.0-2026-09-20-0158, `actors` at `c03f9fa`. Evidence grade: **proved** (`--no-cheating`, no trusted item in this
crate), about **models**. Every theorem here is a statement about an L1 contract or a reviewed L2 machine. None says
that the Python or ObjectScript at pin `3eaa79cf` has the property. The product's obligations stay as the as-built
evidence leaves them (failed or open: `findings/audit/15.json`, `16.json`, `17.json`, `zz-validation.json`).

| Gate item (§3.3) | 15 FHIR sync, erase, task, register | 16+17 one HTTP call | 16 unit of work | 16+17 authorization boundary | 17 SQL adapter | 17 status, capabilities, driver |
|---|---|---|---|---|---|---|
| L1 contract with the business invariants (`Contract` + `SafeContract`) | `src/fhir_l1.rs` | `src/call_l1.rs` | `src/unit_l1.rs` | `src/auth_l1.rs` | `src/sqla_l1.rs` | `src/opsc_l1.rs` |
| L2 machine over the stored / protocol state, reviewed design | `src/fhir_l2.rs` (fhir_graphs wm and interp_version, the Task Manager's tasks and task_id, the sync lock and SyncOnce's in-memory position, the projection, unreadable keys) | `src/call_l2.rs` (IVGClient attempts, the server's attempts and reply, IRIS commits) | `src/unit_l2.rs` (Bolt session phase, committed and buffered writes, driver retry) | `src/auth_l2.rs` (operator settings, the HTTP middleware stack, the Bolt listener's address, the SDK's exception mapping) | `src/sqla_l2.rs` (Graph_KG.nodes, rdf_labels with graph_id, pass-through writes) | `src/opsc_l2.rs` (STATUS_PARTS, deployed classes, the static catalogue, pyproject floor, uv.lock version, installed driver) |
| `Refines<L1>` for **every** L2 step | 14 labels (`lemma_step`) | 3 labels | 7 labels | 4 labels | 4 labels | 7 labels |
| L2 invariant inductive (`SafeContract`) | `inv15` (L1's 4 conjuncts + `run_ok`, cursor, `tasks_ok`) | `inv16c` (L1's 4 + 6) | `inv16u` (L1's + 8) | `inv16a` | `inv17q` | `inv17o` |
| Every raw L2 execution refines L1 and keeps both invariants | `fhir_l2::theorem_raw_executions_refine` | `call_l2::…` | `unit_l2::…` | `auth_l2::…` | `sqla_l2::…` | `opsc_l2::…` |
| Progress under fairness | `fhir_progress::theorem_watermark_advances` (+ `theorem_work_available`) | no | no | n/a | n/a | n/a |
| Broken-implementation controls rejected in the expected file | 3 of 3 in `fhir_l2.rs` + progress-only 1 of 1 in `fhir_progress.rs` | 3 of 3, `call_l2.rs` | 2 of 2, `unit_l2.rs` | 3 of 3, `auth_l2.rs` | 3 of 3, `sqla_l2.rs` | 2 of 2, `opsc_l2.rs` |
| Each control's counterexample proved reachable | `cx_hd1503`, `cx_fc1501`, `cx_f1511`, `cx_progress` (a fair infinite execution) | `cx_fc1604`, `cx_fc1602`, `cx_fc1703` | `cx_f1601`, `cx_f1610` | `cx_f1614`, `cx_fc1603`, `cx_f1714` | `cx_hd1701` (two), `cx_f1701` | `cx_f1713`, `cx_fc1706` |
| Non-vacuity (the reviewed L2 does real work) | `witness_fhir.rs` | `witness_call.rs` | `witness_unit.rs` | `witness_auth.rs` | `witness_sqla.rs` | `witness_opsc.rs` |
| Trust inventory | empty (this crate and `actors`) | same | same | same | same | same |

Baseline: `cargo verus verify -- --no-cheating`: **115 verified, 0 errors** (FHIR 33, call 17, unit 15, auth 19, SQL
adapter 16, ops claims 15); Verus 1.79 s, SMT 1.42 s, 3.41 M rlimit, wall 2.19 s, 0.44 GB peak (registry
`proofs-d1f-baseline`, log `$RUN_DIR/proofs-d1f/baseline.log`, which ends with the counts read from its JSON). Gate:
**pass** (`RESULTS.json`, sources SHA-256 `fce4cc117e95171a...`). An unregistered run of the whole gate over the same
sources (`$RUN_DIR/proofs-d1f/scratch-1/RESULTS.json`) gave the same result, run for run. Rerun:
`source experiment/playbook-completion/environment.sh; python3 experiment/playbook-completion/proofs-d1f/tools/run_proofs.py`
(each Verus run under `tools/locks.sh heavy timeout 3600` after `cargo clean -p`; `PROOFS_OUT_DIR=<dir>` writes logs and
RESULTS.json there; `--register` registers the decisive runs). `tools/dev_verify.sh` is the development helper
(unregistered logs under `$RUN_DIR/proofs-d1f/scratch/`).

Executable twins (explorer, breadth lane C, `models/breadth-c/src`): `retry.rs` M1 for the call family
(cmc-retry-*), `unit.rs` M2 for the unit family (cmc-unit-*), `fhir.rs` M3 for the FHIR erase/durable-removal part
(cmc-fhir-*), `register.rs` M6 for F-1511 (cmc-register-*). With no explorer twin: F-C1501's orphan task, the FHIR
progress proof and its control, the authorization family (F-1614, F-C1603, F-1714), the SQL adapter family (HD-1701,
F-1701) and the ops-claims family (F-1713, F-C1706, HD-1703).

## 1. Module 15: a FHIR graph's sync against erase, its sync task and its registration

### L1 contract (`fhir_l1.rs`)

State: the feed's highest row id `n` (keys 1..n), the projected keys `graph`, the watermark `wm`, `sched` (a task
runs the graph), `removed` (an operator's durable removal), `settings`. Labels: `Append`, `Batch{e}` (the keys after
the stored watermark up to e, with the watermark), `Erase` (transient clear), `Remove` (durable removal),
`Schedule{ok}`, `Unschedule{ok}`, `Register{ok, v}`. `inv1` (proved inductive, `lemma_l1_safe`): watermark soundness
(every key at or below `wm` is projected), projected keys are repository keys, and a removed graph is empty, unscheduled
and at watermark 0. Theorems: `theorem_caught_up_graph_is_the_repository` (FHIR_GRAPH.md:255-259: at `wm = n` the
graph is exactly the repository), `theorem_batch_moves_with_its_watermark` (INT-F5.2),
`theorem_durable_removal_stays_removed` (HD-1502 working answer), `theorem_refusals_change_nothing` (SYS-I3; INT-F3.9;
SYS-I4 for schedule), `theorem_register_keeps_watermarks` (INT-F3.7), `theorem_unschedule_stops_the_task` (INT-F9).

### L2 machine (`fhir_l2.rs`) and refinement

| L2 step (source at the pin) | L1 step | Proof |
|---|---|---|
| `Append` (a repository row) | `Append` | `lemma_step` |
| `Repair{k}` (HD-1504 recovery) | stutter | `lemma_step` |
| `Start{by_task}` (SyncOnce: lock, Open, MAX(ID) once, FHIRGraph.cls:543-558; the task's tick or a caller) | stutter | `lemma_step` |
| `RBatch`, `RDone` (Rederive :1451-1473, SetInterpVersion :577-580) | stutter | `lemma_step` |
| `Batch{e}` (RunBatch with its watermark, :585-609, 1923-1977) | `Batch{e}` | `lemma_batch` |
| `BatchFail{e}` (an unreadable key: rollback, RecordError, :620-624) | stutter | `lemma_step` |
| `Interrupt` (the process stops; SYS-P1), `End` (:611) | stutter | `lemma_step` |
| `Erase` (Eraser.EraseGraph :47-258, EraseFHIRGraphRows :1151-1180) | `Erase` | `lemma_erase` |
| `Remove` (Unschedule then EraseGraph) | `Remove` | `lemma_remove` |
| `Schedule{ok}` (:667-713) | `Schedule{ok}` | `lemma_schedule` |
| `Unschedule{ok}` (:716-741) | `Unschedule{ok}` | `lemma_unschedule` |
| `Register{ok, v}` (:167-278) | `Register{ok, v}` | `lemma_register` |

`inv15`: `inv1` of the abstraction (`sched` = the Task Manager holds a task of the graph); `run_ok` (a running sync's
feed position is the stored watermark, its pass position the durable cursor; it never runs on a removed graph);
`rcur <= wm`; `tasks_ok` (the graph's tasks are exactly the one `task_id` names). L2 theorems:
`theorem_sync_continues_from_the_stored_watermark` (HD-1503 on the layout) and
`theorem_durable_removal_stops_the_feed` (HD-1502 on the layout: no task, no running sync, no tick can start one).

### Progress (`fhir_progress.rs`)

The watch: a reachable, not removed state with a cohort n0 ≤ n. Rank: cohort rows past the watermark, plus (while the
interpretation is stale) the keys the re-derivation pass still has to do, plus one. `FairWork` is proved: feed batches
below n0, re-derivation batches and SetInterpVersion lower the rank; **no step raises it** (new rows lie past the
cohort; a failed batch rolls back with its watermark; a stopped sync keeps the committed watermark; the next sync
starts from the stored watermark; R15-P: a pass resumes from its durable cursor). `theorem_watermark_advances`
(`actors::fairness::eventually_drained`): under productive fairness the watermark reaches n0 with the interpretation
current, and every cohort key is projected. `theorem_work_available`: while the rank is positive a sync can start, a
pass can take its next batch or finish, a feed can commit its next one-key batch when that key is readable, or end.
Fairness premises (named, not proved): PF-1 no erase or durable removal during the watch; PF-2 a sync is started again
after each stop (the task, which counts busy as success, INT-F6.2, or an operator); PF-3 the next key is readable or an
operator repairs it (HD-1504: a failed batch never advances, by the documented contract); PF-4 a process with an
enabled step is eventually scheduled.

**Progress-only control** `control_progress_rederive_restart`: an interrupted pass starts again from the first key, as
at the pin (FHIRGraph.cls:573-581, 1451-1473; INT-F5.7; spec 235 FR-024, an intended behaviour, not a finding). Every
safety function still verifies (116 verified: the baseline's functions less the FHIR witness, plus the
counterexample's three); only
`FhirProgress::nonincreasing` fails, at `fhir_progress.rs:95` (`assert(v.s.rcur == s.rcur)`, the Start case).
`cx_progress::counterexample_progress` proves a productively fair infinite execution (Start, RBatch, Interrupt,
repeated; rank 2, 3, 2, ...) whose rank never reaches 0: under repeated interruption the watermark of a stale graph
never advances, whatever the scheduler does. What it shows: the durable cursor R15-P (this lane's proposal) is what
makes PF-4 enough; at the pin a re-derivation pass must complete in one uninterrupted run.

## 2. Modules 16 and 17: one HTTP call through IVGClient and the Cypher HTTP server (`call_l1.rs`, `call_l2.rs`)

L1: `{op, applied, answer}`; labels `Apply`, `Answer{o}` (Success, Failed, Unknown). Rules (HD-1603, HD-1702 working
answers, one combined protocol): at most once; a definite failure applied nothing (now or later); success means applied
once. `inv1` is inductive; `theorem_at_most_once`, `theorem_definite_failure_applied_nothing`,
`theorem_success_means_applied_once`.

L2: client `Ready | Waiting | Done(o)` with its attempts (max_retries 3, sdk.py:93), server `Idle | Executing |
Replied(ok) | Lost` with its attempts (range(2), cypher_api.py:241), IRIS commits `applied`, ghost `sent`. Steps:
`Send{delivered, ans}` (a connect error, or the POST delivered), `Exec{pre_send, committed, ack, applies}` (one server
attempt), `Reply{delivered, ans}` (the reply arrives, or a timeout / proxy 5xx). `Exec` with `applies` maps to `Apply`,
any step with an answer to `Answer`, every other step stutters. `inv16c` ties the client and server phases and
`sent`/`applied` (a write's server is executing only before its statement left; `Replied(true)` means applied once,
`Replied(false)` nothing; a ready client has sent nothing). L2 theorem `theorem_server_answers_are_honest`.

## 3. Module 16: a unit of work over Bolt and the Neo4j HTTP commit route (`unit_l1.rs`, `unit_l2.rs`)

L1: visible applications `v1`, `v2` of the unit's two writes, `done`; `Commit` (once), `Abort`, `Read{a, b}`. Rules
(API-B9.10; API-B8.6.1, Neo4j tx/commit, P-1612; SYS-I4): all or none, at most once. `theorem_reader_sees_whole_units`,
`theorem_unit_at_most_once`. L2: entry Bolt or HTTP, phase, committed and buffered writes, last failure, attempts,
committed units; `Begin`, `Run1`, `Run2{ok, http}`, `Commit`, `Rollback`, `Retry` (the driver's managed retry), `Read`.
Bolt `Commit` and a successful HTTP `Run2` map to `Commit`; Bolt `Rollback` and a failed HTTP `Run2` to `Abort`.
`inv16u`: buffers by phase, a committed unit is over (no retry after it).

## 4. Modules 16 and 17: the authorization boundary and the client's status map (`auth_l1.rs`, `auth_l2.rs`)

L1: the operator's settings (key, read-only, host) and the route code that ran. `Request{r, st}` with `st` the
contract's decision `decide` (unreachable from another machine when the operator named the loopback address; 401
without the key on a non-public path; 403 for a write in read-only mode; else the route runs), and `ClientSees{st, cls}`
(a 401 or 403 is IVGClientError). Theorems: `theorem_no_route_code_without_the_key` (API-T1, API-X1.5),
`theorem_read_only_after_the_key_gate` (API-T3), `theorem_loopback_server_unreachable_from_other_machines`
(ADMIN_API.md:26-28), `theorem_graph_is_not_authorization` (HD-1601, supported), `theorem_refusals_raise_ivg_client_error`
(sdk.py:195-201). L2: the HTTP listener's middleware stack (cypher_api.py:95-118; api_auth.py:77-187; the Cypher
routes' own checks cypher_api.py:353-354, 381-385, 438), the Bolt TCP listener opened by the lifespan
(cypher_api.py:47-63) with HELLO/LOGON and RUN's AccessMode check (bolt_server.py:570-577), and the SDK's mapping by
call kind. `inv16a`: the Bolt listener is bound where the operator said. The L1 invariant is weak (`writes <= runs`):
the business rules are the contract's transition relation (as `bulk_l1` in `proofs-d1c`).

## 5. Module 17: the SQL adapter (`sqla_l1.rs`, `sqla_l2.rs`)

L1: nodes `NK{g, n}`, labels `LK{g, n, l}`, pass-through writes. `Exec{write, ro, ok}` (HD-1701 working answer (a): a
read-only non-SELECT is refused and writes nothing; an answer with an error ran nothing; OPS-B5.9) and
`GetNodes{ids, graph, ans}` (OPS-B5.3, CONTEXT.md:38-43: the answer is exactly each node's own label facts, in the named
graph or in every graph). `inv1` (labels belong to existing nodes) inductive. Theorems:
`theorem_read_only_call_writes_nothing`, `theorem_failure_report_means_nothing_ran`,
`theorem_node_read_keeps_graphs_apart`. L2: the rdf_labels rows as the adapter's SQL returns them; as built with
graph None the labels are folded by id (premise P-Q1 below).

## 6. Module 17: status, capability claims and the driver pin (`opsc_l1.rs`, `opsc_l2.rs`)

L1: deployed capabilities, the installed driver, node rows. Rules: every part a report marks unknown is in the
published list (OPS-I2.3.3); an availability claim is a fact about the namespace and a call answers only from a
deployed class (HD-1703 working answer); every admitted install gets a driver the product works with, under which a
duplicate row is skipped (F-C1706; OPS-B5.4). Theorems: `theorem_unknown_parts_are_listed`,
`theorem_catalogue_is_not_availability` (a supported but undeployed capability is catalogued, not available, and its
call raises: the HD-1703 separation, **held by the as-built design in the model**, so no control), and
`theorem_duplicate_is_skipped`. L2: STATUS_PARTS and the parts the report can mark (status.py:11; admin.py:551,
752-753), engine.capabilities, the static catalogue (iris_sql_store.py:2991-2992), routing with its fallback, the
pyproject floor and the lock's version, is_duplicate's recognition (_write_txn.py:46-49).

## 7. Reviewed design and its status at the pin

| Id | Element | Source | At the pin |
|---|---|---|---|
| R15-1 | an erase (and a durable removal's erase) of a FHIR graph takes the sync lock and waits or answers busy | HD-1503 working answer, alternative (a) | no: Eraser.cls takes no lock; RunBatch writes an absolute watermark (FHIRGraph.cls:1967-1969) |
| R15-2 | Schedule writes the task and task_id in one transaction | F-C1501 remedy | no: %Save (:701), separate UPDATE (:703) |
| R15-3 | Register validates and loads before it writes | F-1511 remedy | no: upsert (:235-245) before Open/LoadColumns (:247-249) |
| R15-P | a re-derivation pass resumes from a durable cursor (progress only) | this lane's proposal | no: the pass restarts (INT-F5.7, FR-024; intended) |
| R16-1 | the server re-runs only a read or a statement that never left | HD-1603 working answer | no: any exception (cypher_api.py:239-250) |
| R16-2 | an unacknowledged write is answered "outcome unknown" | HD-1603 working answer; F-C1602 remedy | no: HTTP 400 / Neo.ClientError (cypher_api.py:369-376) |
| R16-3 | every app has the key gate | CHANGELOG.md:994-996; F-1614 remedy | no for the demo server (src/iris_demo_server/app.py:1-22); yes for cypher_api |
| R16-4 | the Bolt listener binds the host the operator named | ADMIN_API.md:26-28; F-C1603 remedy | only under `ivg server start` (cli.py:429); else 0.0.0.0 (cypher_api.py:51) |
| R16-5 | a unit's statements run in one engine transaction | F-1601, F-1610 remedies | no (bolt_server.py:500-510, 579-581; cypher_api.py:391-401) |
| R17-1 | the client resends only a read or a request that never left | HD-1702 working answer | no: sdk.py:209-228 |
| R17-2 | every SDK call maps 401/403 to IVGClientError | sdk.py:195-201; F-1714 remedy | no for explain, load_ndjson, AsyncIVGClient |
| R17-3 | execute_sql(read_only=True) refuses a non-SELECT | HD-1701 working answer (a) | no: the flag is unread (iris_sql_store.py:1522-1531) |
| R17-4 | a statement that ran is answered without an error | OPS-B5.9 with SYS-I3 | no: fetchall on no result set (iris_sql_store.py:1531, 1537-1553) |
| R17-5 | an unscoped node read keeps each graph's node apart | F-1701 remedy; OPS-B5.3 | no: folded by id (iris_sql_store.py:1116-1150) |
| R17-6 | STATUS_PARTS names every part status() can mark unknown | F-1713 remedy | no: lacks adjacency, routines |
| R17-7 | the driver floor and the lock are versions the product works with | F-C1706 remedy | no: >=1.0.0 and 5.3.2 |
| as built | the sync lock excludes a second sync (INT-F6); a batch commits with its watermark; a failed batch moves neither; erase keeps the registration; Unschedule deletes the named task; the key gate runs before read-only; the engine's capability claim is a namespace fact and routing falls back | FHIRGraph.cls, Eraser.cls, api_auth.py, capabilities | yes |

## 8. Broken-implementation controls

Each feature puts back one as-built decision. Every error is in the expected file, every failing function is in that
file's module, every function of every other module verifies (`RESULTS.json`, `failing_outside_expected_module`
empty), and each control's counterexample (compiled only with it) is a proved run of the L2 step relation, as the
control changes it, from its initial state to a step that is not an L1 step.

| Control (finding) | Rejected at (function: obligation) | Proved counterexample | Registry |
|---|---|---|---|
| `control_hd1503_erase_ignores_sync_lock` (HD-1503, HD-1502; explorer cmc-fhir-erase-as-built, cmc-fhir-durable-as-built) | `fhir_l2.rs:227` `lemma_erase`, `:237` `lemma_remove`: `run_ok(t)` (no sync runs past an erase with an old position) | 4 steps: sync; batch 1-2 (wm 2); erase (wm 0); the running sync's batch writes keys 3-4 and wm 4 (not an L1 step; `!inv1`: keys 1-2 below the watermark and missing; wm = n, so no later sync brings them back). Same with a durable removal: the running sync refills the removed graph | `proofs-d1f-hd1503-erase-ignores-sync-lock` |
| `control_fc1501_schedule_untransacted` (F-C1501) | `fhir_l2.rs:252` `lemma_schedule`: a refused schedule changes nothing | 6 steps: refused schedule leaves an orphan task (not an L1 step); unschedule answers ok, task stays (not an L1 step); durable removal leaves it (not an L1 step); its tick syncs the removed graph back (`!inv1`) | `proofs-d1f-fc1501-schedule-untransacted` |
| `control_f1511_upsert_before_load` (F-1511) | `fhir_l2.rs:270` `lemma_register`: a refused register changes nothing | 1 step: refused register with new settings kept | `proofs-d1f-f1511-upsert-before-load` |
| `control_progress_rederive_restart` (progress only; INT-F5.7) | `fhir_progress.rs:95` `FhirProgress::nonincreasing`: a pass resumes from its cursor | a productively fair infinite execution (Start, RBatch, Interrupt)* whose rank never reaches 0 | `proofs-d1f-progress-rederive-restart` |
| `control_fc1604_server_reruns_write` (F-C1604; live c16-s4-server-retry) | `call_l2.rs:167` `lemma_exec`: a write whose statement left is not run again | 4 steps: send; commit with the ack lost (server re-runs); second commit (not an L1 step); 200 with the write applied twice | `proofs-d1f-fc1604-server-reruns-write` |
| `control_fc1602_unknown_as_client_error` (F-C1602; probe c16-s6-status-maps) | `call_l2.rs:169` `lemma_exec`: an unacknowledged write is answered unknown | 3 steps: send; commit with the ack lost (server answers 400); the caller is told "failed" for an applied write (not an L1 step) | `proofs-d1f-fc1602-unknown-as-client-error` |
| `control_fc1703_client_resends_write` (F-C1703; live c17-live-server) | `call_l2.rs:180` `lemma_reply`: after a timeout or 5xx a write is reported unknown | 6 steps: send; commit and reply; the reply is late (client resends); second commit (not an L1 step); success with two writes | `proofs-d1f-fc1703-client-resends-write` |
| `control_f1601_bolt_run_commits` (F-1601; live c16-s1-cypher-http) | `unit_l2.rs:143` `lemma_run1`, `:159` `lemma_run2`, `:168` `lemma_commit`: nothing is visible before COMMIT, which publishes both | 9 steps: BEGIN; RUN w1 commits (not an L1 step); RUN w2 fails; ROLLBACK leaves w1 (`!inv1`: a reader sees half the unit); the driver's retry commits w1 again (w1 visible twice) | `proofs-d1f-f1601-bolt-run-commits` |
| `control_f1610_tx_commit_per_statement` (F-1610; live c16-s1-cypher-http) | `unit_l2.rs:146` `lemma_run1`, `:156` `lemma_run2`: a request's statements are visible together or not at all | 4 steps: the request arrives; its first statement commits (not an L1 step); the second fails, 400; a reader sees w1 without w2 | `proofs-d1f-f1610-tx-commit-per-statement` |
| `control_f1614_app_without_key_gate` (F-1614; live c16-s8-followup) | `auth_l2.rs:131` `lemma_http`: the app decides as the contract | 1 step: a write without the key from another machine runs (not an L1 step: 401) | `proofs-d1f-f1614-app-without-key-gate` |
| `control_fc1603_bolt_binds_every_interface` (F-C1603; probe c16-s6-status-maps) | `auth_l2.rs:123` `lemma_listen`: Bolt binds the operator's host | 2 steps: the lifespan binds Bolt on 0.0.0.0 though the operator named loopback (`!inv16a`); a write from another machine runs over Bolt with no key set (not an L1 step: unreachable) | `proofs-d1f-fc1603-bolt-binds-every-interface` |
| `control_f1714_unmapped_refusal` (F-1714; live c17-live-server) | `auth_l2.rs:146` `lemma_client`: a 401/403 is IVGClientError | 1 step: explain's 401 surfaces as HTTPStatusError (not an L1 step) | `proofs-d1f-f1714-unmapped-refusal` |
| `control_hd1701_read_only_ignored` (HD-1701; live ib-HD1701-readonly-flag) | `sqla_l2.rs:111` `lemma_exec`: a read-only non-SELECT runs nothing | 1 step: an INSERT runs under read_only=True (not an L1 step) | `proofs-d1f-hd1701-read-only-ignored` |
| `control_hd1701_write_reported_failed` (HD-1701 observation, unfiled candidate S3; same probe) | `sqla_l2.rs:113` `lemma_exec`: an error answer ran nothing | 1 step: an INSERT runs and is answered with an error (not an L1 step) | `proofs-d1f-hd1701-write-reported-failed` |
| `control_f1701_unscoped_merge` (F-1701; live c17-live-engine) | `sqla_l2.rs:125` `lemma_getnodes`: the unscoped answer is each node's own labels | 4 steps: id 7 in graphs 1 and 2, label 5 in graph 1; the unscoped read answers label 5 for graph 2's node (not an L1 step) | `proofs-d1f-f1701-unscoped-merge` |
| `control_f1713_status_parts_short` (F-1713; check c17-offline) | `opsc_l2.rs:108` `lemma_report`: STATUS_PARTS covers every part | 1 step: the adjacency probe fails and the report names a part the list does not (not an L1 step) | `proofs-d1f-f1713-status-parts-short` |
| `control_fc1706_driver_floor` (F-C1706; val-driver532-1 vs val-driver540-1) | `opsc_l2.rs:116` `lemma_install`: admitted installs get a working driver | 2 steps: uv sync installs 5.3.2 (not an L1 step; pip may install anything >= 1.0.0); a duplicate write raises instead of skipping (not an L1 step) | `proofs-d1f-fc1706-driver-floor` |

Counts (verified / errors, each including its counterexample and excluding its family's witness): HD-1503 113/2,
F-1601 112/3, F-1610 113/2, progress control 116/1, every other control 114/1. Each control run took 1.61-1.72 s of
wall time (28.5 s for all 17).

Identifier notes. HD-1503 has no finding id: the as-built interleaving is reasoned from source (intent record
HD-1503) and reproduced in the explorer (cmc-fhir-erase-as-built, cmc-fhir-durable-as-built); live reproduction is
blocked-access (no FHIR repository on IRIS Community). F-C1501 is confirmed in source only and F-1511 in the explorer
only (both blocked-access live, same reason); `cx_fc1501` and `cx_f1511` reproduce them in these models, not live.
`control_hd1701_write_reported_failed` controls an observation of the HD-1701 probe that no finding records (the
intent record names it a candidate S3). In F-1701's counterexample the second graph's node is unlabelled, as in the
live case; the model's reading of the folded row as a claim about every node of the id is premise P-Q1.

## 9. Premises (named; none is an assumption inside a proof)

| Id | Premise | The pin |
|---|---|---|
| P-F1 | one feed (Rsrc; RsrcVer alike), keys = row ids 1..n, a key's projection is one fact per batch; deleted resources, canonical dependants, compartment edges, Rebuild, json-link changes, the repository-behind rebuild and the ledger (HD-1501) are not modelled | modelling restriction |
| P-F2 | after a durable removal nobody schedules the graph or syncs it by hand | **not enforced**: no single-graph deregistration exists; fhir_graph_sync still works after unschedule (fhir_graph.py:302-310); HD-1502's working answer makes it an operator premise |
| P-F3 | each modelled call is one atomic step; calls interleave between steps | holds for RunBatch (one transaction with its watermark) and EraseGraph; **violated** for Schedule (F-C1501) and Register (F-1511), both controls; SyncOnce's own steps are separate steps (that is the HD-1503 interleaving) |
| P-F4 | the sync lock admits one sync per graph; a killed process frees it (SYS-P4) | holds by source (INT-F6) and premise SYS-P4 |
| PF-1..PF-4 | progress: no erase/removal during the watch; a sync is started again after each stop; the next key is readable or repaired; enabled processes are eventually scheduled | PF-1 not enforced; PF-3 **fails** for any unreadable resource until an operator repairs it (HD-1504, the documented contract); with the pin's restarting pass (no R15-P) PF-4 is not enough (progress-only control) |
| P-C1 | one call, one request in flight per call; IVGClient 3 attempts, server 2 attempts; a statement commits whole or not at all | modelling restriction (defaults at the pin) |
| P-C2 | a ConnectError means nothing left the client | assumed (httpx) |
| P-C3 | the reviewed server can tell a statement that never left from one whose outcome is unknown | **not at the pin**: `_run_cypher` sees only an exception |
| P-C4 | the reviewed client treats the server's "unknown" answer as unknown and does not resend | **not at the pin**: no such answer exists, and the SDK resends any 5xx |
| P-U1 | a unit of two writes on one session; the driver retries at most once | modelling restriction |
| P-U2 | readers see committed state only (so a reviewed unit is visible whole) | **violated by default**: IRIS SQL's default isolation is READ UNCOMMITTED and global reads are not isolated (SYS-P2; live c18-live-dirty-export); the reviewed units are whole for READ COMMITTED readers only |
| P-A1 | the operator's settings are fixed while the server runs; BOLT_TCP_HOST unset; public paths are read routes | modelling restriction (configured_key() is read per request, API-T1.1) |
| P-A2 | "remote" is another machine reaching a non-loopback interface, with no proxy on the host | assumed (a same-host proxy makes every request local, API-P1.14) |
| P-A3 | the namespace is the authorization boundary; graph names confer none | decided (HD-1601, supported) |
| P-A4 | each route's read-only check is one decision; MCP tools (API-T3.6, documented) and the REST dispatcher (IRIS login) are outside | modelling restriction |
| P-Q1 | an answer row that names no graph is a claim about every node of its id | modelling premise of F-1701's model |
| P-Q2 | the pass-through's write effect is one counter; labels only (rdf_props and query_nodes read alike, not modelled) | modelling restriction |
| P-D1 | driver versions from 5.4.0 on work with the product, 5.3.2 does not | observed for 5.3.2 and 5.4.0 only (validation A/B); every other version is an extrapolation; the reviewed R17-7 rests on it |
| P-O1 | ten status parts (eight listed, adjacency, routines); capabilities as numbers; one write_nodes row; F-C1706's score types and list parameters not modelled | modelling restriction |

## Premises the pin violates

By this audit's own evidence the pin violates P-U2 (uncommitted reads, SYS-P2, live) and, for the reviewed call
protocol, P-C3 and P-C4 (no pre-send/unknown distinction on either side); it does not enforce P-F2 (no
deregistration, and F-C1501's orphan task outlives a successful unschedule) or progress premises PF-1 and PF-3
(HD-1504: one unreadable resource stalls the graph until repaired), and P-F3 fails for Schedule and Register (the
controls F-C1501, F-1511). P-D1 is an extrapolation from two driver versions. Every reviewed-design element R15-1..R15-3,
R15-P, R16-1..R16-5 and R17-1..R17-7 is absent at the pin (section 7), and each control shows the corresponding
as-built decision breaking the model's contract on a reachable run (the progress control: a fair run that never
finishes). The working answers behind R15-1 (HD-1503), R16-1/R16-2 (HD-1603), R17-1 (HD-1702) and R17-3 (HD-1701) are
assumptions, not maintainer decisions; R15-P is this lane's proposal. So no safety or progress result here transfers to
the product. What transfers is the negative: each as-built decision of section 8 breaks the contract on a reachable run
of the model.

## 10. Module 00 (system root): not applicable

Module 00 has no operations of its own, so there is no system-wide invariant of its operations to prove as a
composition. Source: `experiment/playbook-completion/ontology/00-system.md:1-7` (Root SYS-0; the file "holds the terms
every module uses and the universal rules ... that every module's statements trace to") and `:46-96` (its statements
are of kinds R, D, I and P only: SYS-0, SYS-D1..D32, SYS-I1..I10, SYS-P1..P4; no operation, no store, no cell);
`experiment/playbook-completion/modules/00.json` `gates_by_id` 3.3-L1, 3.3-L2, 3.3-refinement and 3.3-controls are
`not-applicable` ("module 00 owns no code or store: ... each checked inside the owning modules"). Disposition:
**not-applicable**. The universal axioms are instantiated inside the owning modules' contracts; in this crate (each a
model-level statement, none composed with another family or module): SYS-I2 in `sqla_l1::theorem_node_read_keeps_graphs_apart`
(and `auth_l1::theorem_graph_is_not_authorization` for SYS-I10's namespace boundary), SYS-I3 in
`fhir_l1::theorem_refusals_change_nothing` and `sqla_l1::theorem_failure_report_means_nothing_ran`, SYS-I4 in
`fhir_l2::tasks_ok` (task and registry) and `unit_l1::theorem_reader_sees_whole_units`, SYS-I6's "never saves twice"
for HTTP calls (not the ledger retry key) in `call_l1::theorem_at_most_once`, and SYS-I9's honest refusal in R16-2 and
`auth_l1::theorem_refusals_raise_ivg_client_error`. No cross-module composition of these is proved (D-5).

## 11. Cost (measured, `RESULTS.json`)

Baseline: Verus 1.79 s, SMT 1.42 s, 3.41 M rlimit over 115 functions, wall 2.19 s, 0.44 GB.

| Module proof | Functions | SMT ms | rlimit | Largest function | Largest proof lemma |
|---|---|---|---|---|---|
| 15 FHIR (`fhir_l1`, `fhir_l2`, `fhir_runs`, `fhir_progress`, `witness_fhir`) | 33 | 629 | 1.53 M | `witness_fhir::witness_fhir` 0.32 M | `fhir_l2::lemma_step` 0.21 M |
| 16+17 one HTTP call (`call_*`, `witness_call`) | 17 | 233 | 0.62 M | `witness_call::witness_call` 0.35 M | `call_runs::lemma_c_steps` 0.06 M |
| 16 unit of work (`unit_*`, `witness_unit`) | 15 | 188 | 0.48 M | `witness_unit::witness_unit` 0.19 M | `unit_l2::lemma_step` 0.07 M |
| 16+17 authorization (`auth_*`, `witness_auth`) | 19 | 191 | 0.41 M | `witness_auth::witness_auth` 0.13 M | `auth_l2::lemma_http` 0.05 M |
| 17 SQL adapter (`sqla_*`, `witness_sqla`) | 16 | 81 | 0.19 M | `sqla_l2::lemma_step` 0.03 M | same |
| 17 ops claims (`opsc_*`, `witness_opsc`) | 15 | 80 | 0.17 M | `witness_opsc::witness_opsc` 0.03 M | `opsc_l2::theorem_raw_executions_refine` 0.03 M |

No rlimit was raised and no proof looped or timed out. The 18 decisive runs took about 31 s of Verus wall time (plus the
same for the scratch gate run); the first build of the target directory (vstd and actors) took 48 s. Development took
about 30 short Verus runs (`$RUN_DIR/proofs-d1f/scratch/dev*.log`). What it needed: this vstd's `Set::new` returns an
`Option` (finite sets only), so key ranges are `Set::<nat>::range` with `range_set_properties` and node-read answers
are characterised by a predicate rather than built; a `forall` written `#[trigger] a <==> b` was never instantiated
where used, fixed by naming the predicate with `#![trigger ...]` and `==`; two trigger hints through the abstraction
`absf`; three invariant strengthenings in the unit family (attempts and last failure by phase) and one in the FHIR
family (`wm <= max` in both phases).

## 12. Trust inventory

This crate has no `assume`, `admit`, `external_body`/`external`, `axiom`, `assume_specification` or `uninterp`
(`--no-cheating` also enforces the first two). The scan of `actors` (`c03f9fa`) finds none either. vstd is Verus's
trusted base (finite `Set`, `Map`, `Seq` and their axioms, including `range_set_properties`). The gate status is
**declared empty** (`RESULTS.json` `trust_inventory`). Line citations in the sources were checked against the pin
before the decisive run (two findings' citations are a few lines off and are cited here as the pin has them:
Register's catch is FHIRGraph.cls:274-276, the HTTP 400 handler cypher_api.py:369-376).

## 13. What is NOT proved (open obligations)

- **No proof connects the Python or ObjectScript to these L2 machines** (D-2, D-3). The six
  `theorem_raw_executions_refine` are the plug-in points for trace conformance; no trace is replayed through them.
- **The families are not composed.** The call and unit families share `_run_cypher` (F-1610's live run also shows the
  server's reset-and-retry inside a tx/commit request); the client's retries over a tx/commit request, and the
  driver's retries over the server's, are not modelled jointly. No joint invariant is proved.
- Module 15 not modelled: deleted resources and the RsrcVer feed, Rebuild and json-link changes (INT-F3.8, INT-F4),
  canonical dependants, the quarantine alternative of HD-1504 (explorer only, cmc-fhir-poison-quarantine), HD-1501
  (FHIR writes and the ledger), the reifiers (F-1502, F-1503, F-C1502, S1), F-1501, F-1504..F-1510.
- Module 16 not modelled: graph isolation in the GraphQL servers and the sample API (F-1603, F-1604 S1, F-1605,
  F-1607), the FHIR event route (F-1609), Bolt PULL (F-1602), Bolt connection release (F-C1601), health (F-1611),
  timeouts (F-1606), MCP (F-1613), the fraud server (F-1615), HD-1602, HD-1604, HD-1605.
- Module 17 not modelled: F-1702 (EmbeddedCursor transactions), F-1703, F-1704, F-1705, F-C1704, F-1706, F-1707,
  F-1708..F-1711 (documents), F-1712, F-C1701, F-C1702, F-C1706's score types and list parameters; HD-1704 (supported,
  no defect). The capability part (HD-1703) has no control: the as-built design meets the working answer in the model;
  its gap is documentation.
- Progress is proved for the FHIR feed only; that a call or a unit completes is not proved.
- The L1s are new contracts written for this lane; their correspondence to the ontology statements (INT-*, API-*,
  OPS-*) and to the explorer models' properties is by inspection.

## Debt accounting (for `PROOF-DEBT.md` D-1)

Paid, model-level only, by `proofs-d1f-baseline` and the 17 `proofs-d1f-*` control runs: the §3.3 L1, L2, refinement,
invariant and control items for module 15 (FHIR sync against erase and durable removal, the sync task, registration;
plus progress of the watermark under fairness with a progress-only control), module 16 (retries after ambiguous
outcomes and the status map of the Cypher HTTP server, Bolt and HTTP units of work, the authorization boundary) and
module 17 (the HTTP client's retries and status map, the SQL adapter's read_only, error answers and node reads, status
and capability claims, the driver pin), as modelled. Module 00: **not-applicable** (section 10). Still owed under D-1:
modules 01, 02 and 07-10, and the unmodelled parts of 15-17 listed in section 13. This lane does not edit
`PROOF-DEBT.md`, `STATUS.md` or `modules/*.json` (outside its write scope); the orchestrator moves the row.
