# Restartable work queue

Ordered by value. Status: `todo`, `doing`, `done` (registered evidence ids / commit), `open` (stopped, with reason),
`blocked` (exact dependency). A successor resumes from the first non-done row. Lanes own disjoint paths
(`CONVENTIONS.md`); the orchestrator commits. Gate status lives in `matrix/obligations.json` (generated; verification
status, evidence level and product obligation per cell). Reconciled 2026-11-14 02:20 UTC against the committed tree.

| # | Lane | Item | Status |
|---|---|---|---|
| Q1 | orchestrator | Scaffolding, registry, locks, per-lane namespaces, journal oracle | done (c01a7ccd; fixes 5d876950, 88217557) |
| Q2 | orchestrator | IRIS 2026.1 contract: differential, sharpness, mutants | done: `env-contract-r2` (283 cases, 0 outside, 17/17) |
| Q2b | contract-ext | Contract extension with the lanes' env features (functional indexes, DDL, empty strings, vectors, ...) | doing: round r3 in progress (40 mutants defined); `VALIDATED_ROUND` set when it meets the gate |
| Q3 | core-models | Erase/redact/replay machines, controls, progress mutants, refinement audit | done: 82 checks (core-*), model-level (307a0a8c) |
| Q3b | orchestrator | Live checks of core proposals | done: F-C1303 `live-fc1303-bounded-resume`; F-C1301/F-C1302/F-C1202 model-only |
| Q4 | core-proofs | Protocol2 composition, safety, progress, controls | done: 88 verified, 0 errors (core-proofs-*, recheck core-proofs-recheck-*), model-level; refuted premises shown (b9192179) |
| Q5 | orchestrator | Journal trace conformance | done: `trace-conformance-ledger`, `trace-conformance-controls` |
| Q5b | orchestrator | F-1201 native reproduction | done: `live-f1201-reproduced` (8/8) |
| Q6 | correspondence | §3.4-3.6 map, unchecked lines, conditions, lock plans for 11-14 | done (09c52ae4): 13/15 actions trace-checked; handler/statement proofs open (no frontend) |
| Q7 | orchestrator | Obligation matrix | done and maintained (build_matrix.py) |
| Q8 | ontology | Literal §3.1 rule, repaired ontology, evidence tags, model-only qualifiers | done (bdcea01f, f3fe3917) |
| Q9 | intent-a/b | Intent recovery, 61 decisions | done (e1df8e3e) |
| Q10 | breadth-a/b/c | Modules 00-11, 15-18 | done (5d876950, 88217557, bd727838) |
| Q11 | validation | Suites, triage, SC-002/003, baselines, multi-process, editions | doing; reruns requested for USER 23:01:45-23:03:40 and scratch-236 licence-refused runs |
| Q12 | orchestrator | Findings 12-14; lost-ack world; crash world | done: findings/audit/12-14, `live-lost-ack-commit`, `live-crash-world-r2` (r1 invalid, recorded) |
| Q13 | review | Independent review | done: no sign-off (`independent-review-1`); dispositions: R-01..R-04, R-10 reproduced/recorded (followup, F-C1306 live), R-02 census corrected, R-05/R-07 matrix and ontology fixed, R-06 premises shown |
| Q13b | orchestrator | Second review pass after the dispositions | todo |
| Q14 | orchestrator | verify.sh on a candidate commit; STATUS, test reflection, phase verdict | doing: fast gate 20 s (18 steps); TRUST.md, PROOF-DEBT.md written |
| I-1..I-4 | orchestrator | Incidents: IVG460SNAP, USER-REDEPLOY-08, superseded proof logs, health alert | recorded in `incidents/` |

Operator-only dependencies: IRIS 2026.3 engine and driver 5.4.0 (version difference of SQL transaction verbs); an IRIS
Enterprise image/licence (SC-003 target and edition comparison); `%AI` classes (MCP module); FHIR server classes
(`HS.FHIRServer`, module 15); a multi-node ECP/mirror setup (multi-node e2e); a second IRIS user/role (least-privilege
checks, F-0908); the `arno-callout` library (F-1001); more licence connections than Community's 8 (throughput; the
licence refusals at 01:31-01:47 came from this cap).
