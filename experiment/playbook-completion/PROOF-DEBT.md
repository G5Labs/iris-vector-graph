# Proof debt (playbook §5a): every unproved obligation, with where it stands

"Proved" in this audit means a decisive Verus run of `proofs/` (88 verified, 0 errors, `--no-cheating`, empty trust
inventory) or of the original `experiment/playbook-uplift/proofs` (53 verified). Everything else below is debt. Each
row says what evidence exists instead and why the proof is missing. Nothing in this table is reported as proved.

| # | Obligation | Scope | Evidence instead | Why unproved |
|---|---|---|---|---|
| D-1 | L1/L2 refinement proofs for modules 00-11 and 15-18 | 17 modules | bounded explorer models with as-built, reviewed, control and reachability checks (`models/breadth-*`, 145+ checks) | specification-first (§5a): models first; Verus layers not written for these modules |
| D-2 | Statement lemmas: each IRIS SQL statement and ObjectScript global operation equals its model evaluation (§3.4) | every writer and reader | journal-validated footprints (breadth lanes, `trace-conformance-ledger`), source inspection | no Verus frontend or IRIS SQL semantics library exists (PGspec is PostgreSQL and is skipped); the IRIS contract is executable, not a Verus spec |
| D-3 | Handler proofs: each Python/ObjectScript entry point performs its spec step (§3.5) | all handlers | trace conformance of one two-tenant scenario; correspondence lane's map and unchecked-line list (`correspondence/`) | no verifier for ObjectScript or Python |
| D-4 | Lock-plan obligations per handler (§3.5) | writers of modules 11-14 and AdjW users | controlled lock probes and journal order; IRIS contract lock clauses | as D-3; F-1201 shows the eraser's plan is incomplete at the pin |
| D-5 | Composition: a committed IRIS transaction refines the serial step, chained over executions (§3.6) | product | `proofs/` composes participant **contracts**; trace conformance checks committed transactions of one scenario | needs D-2 and D-3 |
| D-6 | Frame, key, FK, capacity, row-permutation conditions (§3.6) | modules 11-14 first | correspondence lane checks (see `correspondence/`) | as D-2 |
| D-7 | The IRIS environment contract as a Verus specification linked to the participant contracts | environment | executable contract validated differentially (`env-contract-r2`, 17 mutants) | the link from `proofs/` participant contracts to `iris-contract` clauses is by inspection |
| D-8 | Progress premises: fair scheduling of enabled steps, operator re-runs after a stop, ledger re-enabled, no write outside the ledger | `proofs/src/progress.rs`, core models' AG EF | none derived or tested against IRIS scheduling | premises, named in `TRUST.md` |
| D-9 | Reviewed protocol under the pin's real premises: bypass writers, three distinct target predicates, erasure rollback, readers, statement history, Decision 2 and retry-key movement | erase/redact/replay | explorer: core M1 (three predicates), M2 (bypass writer, rollback, dirty reads), M3 (retry, readers), each bounded | the Verus outer contract collapses these (PROOFS.md, "Premises the pin violates") |
| D-10 | M1 targeting with 2 pre-enable writes and 2 commits | core models | profiles (1+2), (2+1), (0+3) exhaustive | (2+2) exceeded 8M states; not claimed |
| D-11 | Original proof `l2.rs` refinement covers the reviewed design only | modules 12-14 | original 53 verified, 6 controls rejected (submission 9c3719c1) | by design; product violates it (F-1302, F-1303) |

Debt is paid only by a decisive run; a resource-limit or timeout result never counts. When a proof is added, its row
moves to `STATUS.md` with the registry id of the run.
