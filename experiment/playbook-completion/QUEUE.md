# Restartable work queue

Ordered by value. Status: `todo`, `doing`, `done` (registered evidence ids), `open` (stopped, with reason),
`blocked` (exact dependency). A successor resumes from the first non-done row of each lane. Lanes own disjoint paths
(`CONVENTIONS.md`); the orchestrator commits. Gate-level status lives in `matrix/obligations.json` (generated; every
`closed` cell cites registered passing runs; `python matrix/build_matrix.py --check`). Reconciled 2026-11-14 00:30 UTC.

| # | Lane | Item | Status |
|---|---|---|---|
| Q1 | orchestrator | Scaffolding: conventions, registry, locks, per-lane namespaces, journal oracle | done (c01a7ccd; journal vector fix 5d876950) |
| Q2 | orchestrator | IRIS 2026.1 environment contract, native differential, sharpness, mutants | done: env-contract-r2 (0 outside, 282/283 singleton, 17/17 mutants), env-contract-selftest; env-contract-r1 kept (fail, first draft) |
| Q2b | orchestrator | Extend the contract with features the breadth lanes list in `modules/NN.json` env_features (vector SQL, %NOINDEX, functional indexes, Task Manager, `$vector`) | todo; until then those modules' `3.2-coverage` stays open |
| Q3 | core-models | Erase/redact/replay machines M1 targeting, M2 concurrency, M3 retry/readers; controls; progress mutants; refinement audit | done: 82 checks met (core-*); reviewed results are model-level |
| Q3b | orchestrator | Live checks of the core lane's proposed findings: F-C1303 (bounded resume never finishes) running; F-C1301/F-C1302/F-C1202 model-only | doing (traces/fc1303_resume.py) |
| Q4 | core-proofs | Participant contracts, Protocol2 composition (two levels), safety theorems, progress under fairness, controls incl. progress-only | done: core-proofs-baseline (88 verified, 0 errors), 5 located controls; independent recheck running; model-level |
| Q5 | orchestrator | Journal trace conformance of product operations | done for the two-tenant ledger/erase/redact scenario: trace-conformance-ledger, trace-conformance-controls |
| Q5b | orchestrator | F-1201 native reproduction | done: live-f1201-reproduced (8/8, fail = product defect); live-erase-vs-commit-fk, live-erase-vs-commit-emptygraph |
| Q6 | orchestrator | §3.4-3.6 correspondence for modules 11-14: statement/handler map, unchecked lines, lock plan, frame/keys/FK/capacity conditions | todo (highest remaining gate; trace conformance is the strongest correspondence so far) |
| Q7 | orchestrator | Obligation matrix | done and maintained (build_matrix.py; starting inventories reproduced exactly) |
| Q8 | ontology | Literal §3.1 rule, checker, controls, repaired ontology | done: ontology-check-final, ontology-self-test, ontology-independent-recheck |
| Q8b | ontology | Tag the repaired ontology with completion evidence (C- refs) | todo |
| Q9 | intent-a / intent-b | Intent recovery for 61 HD questions with probes | done (intent/*.json; intent-a-*, ib-*) |
| Q10 | breadth-a | Modules 01-06 | done (breadth-a-*) |
| Q10 | breadth-c | Modules 00, 15-18 | done (c15..c18-*, cmc-*); incident IVG460SNAP dispositioned |
| Q10 | breadth-b | Modules 07-11 | doing; rerun of runs active 23:02:53-23:03:40 under the lock requested |
| Q11 | validation | Existing suites on the pin, triage, SC-002/003 and baselines, multi-process, editions | doing; rerun of the USER chunk active in the incident window requested |
| Q12 | orchestrator | Findings audit 12-14 | done (findings/audit/12-14.json); lost-ack world live-lost-ack-commit |
| Q12b | orchestrator | Instance crash world (container restart with all lanes quiet) | todo (end of run) |
| Q13 | review | Independent intent review (§3.8): omitted writers, over-narrow domains, assumed fairness, model-to-code relation | todo (after Q6) |
| Q14 | orchestrator | verify.sh against a candidate commit; trust inventory; proof debt; phase verdict; STATUS | todo (verify.sh drafted, cff144dc) |

Operator-only dependencies so far: IRIS 2026.3 engine and driver 5.4.0 (to attribute the SQL-transaction version
difference); an IRIS Enterprise image/licence (SC-003 target, edition comparison); `%AI` classes (MCP module);
FHIR server classes (`HS.FHIRServer`, module 15); a multi-node ECP/mirror setup (multi-node e2e); more licence
connections than Community's 8 would remove the main throughput limit.
