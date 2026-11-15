# Trust inventory and premises (completion audit)

Product pin `3eaa79cf`; original submission `9c3719c1` (its own `TRUST.md` and `trust/NN.md` list the 138 named
premises; they are not restated here). This file lists what the completion's evidence trusts, and the premises whose
status this audit changed.

## Trusted items

| Item | Where | Why it is trusted | What checks it |
|---|---|---|---|
| Verus toolchain `0.2026.10.04.426d8b0` and `vstd` | `proofs/` | the verifier; `--no-cheating` is applied to the audit crate only, because `vstd` itself contains admitted lemmas | none here (upstream) |
| `actors` / `explorer` at `c03f9fa` | `proofs/`, every model crate, `iris-contract` | generic theorems (`theorem_compose`, `refinement_preserves_safety`, `eventually_drained`) verified in the same build; the explorer is executable and unproved | the original run verified `actors` (121 verified); explorer self-tests upstream; each model has a control the explorer must catch |
| Audit proof crate | `proofs/src` | nothing trusted: no `assume`, `admit`, `external_body` or uninterpreted functions (scanned by `proofs/tools/run_proofs.py`) | `core-proofs-baseline`, `core-proofs-recheck-baseline` |
| IRIS environment contract | `iris-contract/src/lib.rs`; its Verus specification `proofs-env`, extended by `proofs-env2` (D-7) | an executable model, not a proof; trusted only inside its stated semantic subset; for the Verus subset the proof premises are derived from a Verus specification whose exec model agrees with it on every recorded case (`proofs-env-differential-r3`; extended subset `proofs-env2-differential`: 2,430 of 2,943 recorded case runs, 0 disagreements; 9 clause families, 513 case runs, stay executable evidence only) | differential `env-contract-r2` (0 outside), 17 mutants killed, self-test |
| IRIS journal as oracle | `traces/journal.py` | the engine journals every update of a journaled database with process and transaction markers | self-tests on nested levels and rollback; replayed ledger equals the engine's (`trace-conformance-ledger`); vector values recorded as opaque |
| Harness drivers | `iris-contract/native/driver.py`, `traces/*.py`, lanes' `live/` probes | test code | each oracle has a self-test or control (`trace-conformance-controls`, lost-ack and crash oracles) |
| Upstream fixtures and tests | `tests/` at the pin | product's own tests; Community deploy path replaces only the `%AI`-dependent deploy function | validation lane triage |

The proof inventory is empty of trusted items; every other row is executable evidence and is graded as such
(`mc`, `trace`, `live`, `run`), never as proved.

## Premises whose status changed in this audit

| Premise | Original status | Now | Evidence |
|---|---|---|---|
| P-0001 steps are transactions (rollback on stop) | observed live (4 samples) | contract clause, validated: nested levels, partial rollback, stop rolls back every level | `env-contract-r2` |
| P-0003 unlock inside a transaction is deferred | observed | contract clause incl. locks taken before the transaction and release-all | `env-contract-r2` |
| P-1201 a SQL delete waits for a row another transaction holds | assumed (row-lock probe) | contract clause (insert, update, delete; rollback; autocommit) | `env-contract-r2` |
| P-1306 writers quiet during a run | assumed | narrowed: quiet is not enough; a writer's uncommitted delete that later rolls back defeats the liveness check (F-C1301, live since steer 7: `ws-live-fc1301-delete-reification`) | `core-m2-as-built-commit-rollback`, `core-m2-as-built-bypass-rollback` |
| P-1311 no erasure open at redaction start | assumed (proof premise) | **refuted**: counterexample on the pin (F-C1201) | `ib-HD1201-open-erasure` |
| Txn.cls:8 / `_write_txn.py:15`: SQL COMMIT and ROLLBACK end every level | product premise (2026.3) | **false on 2026.1** with the locked driver; START TRANSACTION clause holds | `env-contract-r2` (mutants killed by 4 and 6 cases) |
| P-1310 one target predicate stands for three scopes | assumed | **false**: the three predicates differ; F-1304/F-1305 follow | `core-m1-as-built-F1304`, `live-native-rerun-1314` |

## New premises introduced by this audit's proofs and models (named, with their status)

| Premise | Used by | Status |
|---|---|---|
| Enabled steps are eventually scheduled; the operator re-runs after a stop; the ledger is (re-)enabled; every erasure releases its lock | `proofs/src/progress.rs` | assumed; not discharged against IRIS scheduling |
| The run's cursor survives a stop and the scan bound is fixed at marking | reviewed protocol (model) | design choice of the reviewed model; the pin rewinds (F-C1303, live) |
| Writers go quiet, the operator resumes, nothing is stopped forever, erasure may be repeated | core models' AG EF | assumed (stated in `models/core/MODELS.md`) |
| P-C02 for progress: no writer makes a marked target live (every write to the modelled content goes through a ledger commit, which the marker refuses, or an erasure) | `proofs/src/progress.rs` (a run can finish only if its target stays erased), core models' AG EF, `PROOF-DEBT.md` D-8 | **violated at the pin**: `engine.create_node('fa3\|zombie')` on a non-strict ledger is accepted while the marker exists, the re-run is refused at its entry check, and the run never finishes while the writer writes (F-C1307, `fu-r03-marker-held-open`); strict mode is client-side (HD-1103) and does not cover `POST /admin/load` or temporal writes with a graph. As a safety premise P-C02 is listed in `proofs/PROOFS.md` "Premises the pin violates" (review R-03, R2-04) |
| Durability of an acknowledged commit: a revision the ledger reports as committed survives an instance crash, which needs IRIS `SynchCommit=1` or a journal flush before the acknowledgement | readers of spec 213's "the returned revision exists"; the crash worlds | **not met under the container's default `SynchCommit=0`**: an acknowledged commit was lost after SIGKILL and journal recovery in 1 of 1 trial (`live-crash-world-r2`) and 3 of 3 trials (`live-crash-repeat-sc0`); **under `SynchCommit=1` no acknowledged commit was lost in 3 of 3 trials** (`live-crash-repeat-sc1`; the setting was changed through `Config.Miscellaneous`, then restored to 0, `incidents/SYNCHCOMMIT-WORLDS.md`). Three trials are evidence, not proof. F-C1102 (intent-undecided: no IVG document states the premise) is attributable to the `SynchCommit=0` setting |
| P-A3: an eraser of graph g overlaps no writer of g | `proofs-breadth` (modules 04 and 11; `inv_procs`, explorer restriction: the eraser's row deletes wait on writer row locks) | **violated at the pin**: EraseGraph takes no ledger head lock, and a ledger commit into G lands between its row delete and its statement cleanup (F-1201's interleaving, live 8/8, `live-f1201-reproduced`; the overlap is observed even though F-1201's intent is undecided); EraseGraph's adjacency kill drops an edge committed after its row delete (F-C1202, core model `core-m2-as-built-F1201-adjacency`). Not established for inserts of new rows. Omitted from `proofs-breadth/PROOFS.md` "Premises the pin violates" (P-L4, P-L6, P-A4 there); recorded here (review R2-06) Since steer 7: no longer a premise of `proofs-pa3` (modules 04 and 11 re-proved with the erase interleaving its graph's writers). What replaces it under the reviewed guards (review R4-05): module 04: a weakened form, `theorem_pa3_from_guard` (under R04-5 a writer and an eraser of one graph are open together only while the eraser has passed TSTART but not executed its DELETE and the writer is a lock-less one already in flight, whose row then blocks the eraser's DELETE); module 11: `er_ok` excludes only ledger commits during an open erasure (R11-7), while ledger-bypassing writes of new rows still overlap (`witness_erase`, an unrecorded write). The pin has neither guard (`proofs-pa3-f1201-erase-no-head-lock`, `proofs-pa3-fc1202-erase-unguarded`) |
| M07-L4 progress: the queue worker is weakly fair; a stopped run is resumed `3 - cursor` more times | `proofs-mech` (M-07 queue) | assumed: hypotheses of the progress theorems, not discharged against IRIS scheduling (the pin's node-id order, F-C0605, and LIFO are refuted under the same premise) |
| Embedded SQL (`&sql`) behaves as dynamic SQL for the clauses used | contract (E-1) | **validated** for the pin's own compiled embedded SQL in AUDITCORE (nothing compiled by the audit): 67 cases, 0 outside the permitted sets, 14/14 mutants (`env2-e1-r1`); journal equality of embedded and dynamic writes (`env2-e1-r1-journal`); `Txn_Begin`/`Txn_End`/`Txn_Undo` act on the caller's transaction (`env2-e1-r2`, 54 cases, 8/8 mutants). Residual by analogy: embedded UPDATE and long cursors. In the Verus specification E-1 is **proved** as a premise (`proofs-env2`, `premise_trust_e1`: same effect, answer, visibility and waits as the dynamic statement; 4 located controls) |

## Log provenance

Each registered run record (`evidence/runs/*.json`) carries the SHA-256 of its primary log; `tools/check_registry.py`
re-hashes every log and the fast gate runs it. Independent checks of these digests:

| Check | Records | Current digest matches | Not original | Source |
|---|---|---|---|---|
| Operator, after the account switch (2026-11-14) | 1,237 primary log records | 1,231 | 6 | operator message to the orchestrator (recorded in `LANES.md`) |
| Fourth independent review | 221 records added since `1f7f22fd` | 221 | 0 | `review/REVIEW-4.md` section 2 |
| Third independent review | 782 logs | 776 | 6 (the same six) | `review/REVIEW-3.md` |

The six are the original `proofs/` gate logs (`core-proofs-baseline` and five control runs) that the orchestrator's
recheck overwrote on 2026-11-14 ~00:40 UTC (`incidents/superseded-logs.json`). Their records were not rewritten; `incidents/superseded-logs.json`
names, for each, an explicitly superseding rerun (`core-proofs-recheck-*`) whose digest matches its own log, on the same sources
with the same result (88 verified, 0 errors; each control failing at its located line). They are **superseded**, not
original log matches: the original logs of those six runs are lost, and nothing in this audit relabels them. The cause
(a shared output directory) is fixed (`PROOFS_OUT_DIR`; every verify run writes under its own directory).
Separately, a few records were corrected in place before their first commit; each is disclosed in
`evidence/errata.json` (in-place corrections) together with all other errata.
