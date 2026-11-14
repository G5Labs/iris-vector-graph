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
| IRIS environment contract | `iris-contract/src/lib.rs` | an executable model, not a proof; trusted only inside its stated semantic subset | differential `env-contract-r2` (0 outside), 17 mutants killed, self-test |
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
| P-1306 writers quiet during a run | assumed | narrowed: quiet is not enough; a writer's uncommitted delete that later rolls back defeats the liveness check (F-C1301, model) | `core-m2-as-built-commit-rollback`, `core-m2-as-built-bypass-rollback` |
| P-1311 no erasure open at redaction start | assumed (proof premise) | **refuted**: counterexample on the pin (F-C1201) | `ib-HD1201-open-erasure` |
| Txn.cls:8 / `_write_txn.py:15`: SQL COMMIT and ROLLBACK end every level | product premise (2026.3) | **false on 2026.1** with the locked driver; START TRANSACTION clause holds | `env-contract-r2` (mutants killed by 4 and 6 cases) |
| P-1310 one target predicate stands for three scopes | assumed | **false**: the three predicates differ; F-1304/F-1305 follow | `core-m1-as-built-F1304`, `live-native-rerun-1314` |

## New premises introduced by this audit's proofs and models (named, with their status)

| Premise | Used by | Status |
|---|---|---|
| Enabled steps are eventually scheduled; the operator re-runs after a stop; the ledger is (re-)enabled; every erasure releases its lock | `proofs/src/progress.rs` | assumed; not discharged against IRIS scheduling |
| The run's cursor survives a stop and the scan bound is fixed at marking | reviewed protocol (model) | design choice of the reviewed model; the pin rewinds (F-C1303, live) |
| Writers go quiet, the operator resumes, nothing is stopped forever, erasure may be repeated | core models' AG EF | assumed (stated in `models/core/MODELS.md`) |
| Embedded SQL (`&sql`) behaves as dynamic SQL for the clauses used | contract (E-1) | untested |
