# Restartable work queue

Ordered by value. Status: `todo`, `doing`, `done` (registered evidence ids / commit), `open` (stopped, with reason),
`blocked` (exact dependency). A successor resumes from the first non-done row. Lanes own disjoint paths
(`CONVENTIONS.md`); the orchestrator commits. Gate status lives in `matrix/obligations.json` (generated; verification
status, evidence level and product obligation per cell). Reconciled 2026-11-14 (steer 7) against the committed tree `1f7f22fd`.

| # | Lane | Item | Status |
|---|---|---|---|
| Q1 | orchestrator | Scaffolding, registry, locks, per-lane namespaces, journal oracle | done (c01a7ccd; fixes 5d876950, 88217557) |
| Q2 | orchestrator | IRIS 2026.1 contract: differential, sharpness, mutants | done: `env-contract-r2` (283 cases, 0 outside, 17/17) |
| Q2b | contract-ext | Contract extension with the lanes' env features | done: r6 (516 cases, 0 outside, 42/42), VALIDATED_ROUND=r6; r3-r5 kept as fail |
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
| Q11 | validation | Suites, triage, SC-002/003, baselines, multi-process, editions | done (val-*; validation/SUITES.md); spec-236 scratch suites blocked by the 8-unit licence |
| Q12 | orchestrator | Findings 12-14; lost-ack world; crash world | done: findings/audit/12-14, `live-lost-ack-commit`, `live-crash-world-r2` (r1 invalid, recorded) |
| Q13 | review | Independent review | done: no sign-off (`independent-review-1`); dispositions: R-01..R-04, R-10 reproduced/recorded (followup, F-C1306 live), R-02 census corrected, R-05/R-07 matrix and ontology fixed, R-06 premises shown |
| Q13b | review | Second review pass | done: no sign-off (`independent-review-2`); conditions 1-5, 7 addressed (review/RESPONSE-2.md); 6 needs an operator ruling; 8 items now exist for review |
| Q14 | orchestrator | verify.sh on a candidate commit; STATUS, phase verdict | done: candidate 0eec4df8, `verify.sh --live` 33/33 steps, 708 s (`verify-final-candidate`) |
| Q15 | proofs-breadth / versions | Verus for modules 11 and 04; version, privilege and availability lane | done (proofs-breadth-*, ver-*) |
| Q16a | proofs-d9 | D-9 protocol proofs with three predicates, bypass writers, erasure rollback | done: 115 verified (proofs-d9-*, recheck), model-level |
| Q16b | simulator | §5c randomized simulator through the real product | done: 304 schedules, 13,282 commits checked; new F-CS01 (sim-*) |
| Q16c | proofs-d1b | D-1 for modules 18 and 06 | done: 92 verified (proofs-d1b-*, recheck), model-level |
| Q16d | review | Third review pass; operator scope ruling R2-07 | done: no sign-off (`independent-review-3`); A-1..A-4 applied; operator ruling R2-07/O-1 still requested |
| Q16e | proofs-d1c | D-1 for modules 03 and 05 | done: 111 verified (proofs-d1c-*, recheck), model-level |
| Q16f | proofs-d1d/e/f | D-1 for 07-09, 01-02+10, 15-17 (+00) | done: 118, 115, 115 verified (rechecks), model-level; module 00 not applicable |
| Q17a | proofs-d9b | D-9 remainder: readers/verify racing a redaction, statement history, Decision 2, retry-key movement, F-1306, F-CS01 (empty revision), original F-1302/F-1303/F-1306 controls; D-12 progress-only control | done (e8a0d08a): 158 verified, 13 located controls, D-12 progress-only control; model-level |
| Q17b | semantics | §3.3a system-wide: axioms, shared mechanisms with generic controls, canonical lifecycles, per-object declarations, requirement trace; module 00 model check; F-C0605 model (module 06) | done (b0433157): 14 axioms, 13 mechanisms, 266 checks, 8 lifecycles, 2,545/2,600 requirements traced; F-C0670 |
| Q17c | writesets | 3.3a-writesets: discharge each census obligation (WS-OBL/WS-COND/WS-GAP) by lemma, guard or recorded finding | done (ed0fc784): 185 census obligations, 178 closed, 7 open; F-C1350, F-C1351, F-C1850 (S1) and 4 S2 |
| Q17d | models-2 | D-10 (M1 2+2 by partition), D-13 (eraser overlapping a writer of the same graph in the module 04/11 proofs) | done (8d11c49c): proofs-pa3 108 verified; core-partition (2+2) exhaustive; model-level |
| Q17e | product-gates | 3.5-lint/style, disconnect world (3.7-integration-worlds), failure controls | done (7b72fc52, 32db5be8): lint and style fail; disconnect world 49 trials, 0 violations; 17/20 failure scenarios with controls, S6 blocked |
| Q17f | review | Fourth review pass over proofs-d1c..d1f and Q17a-h | done: no sign-off (`independent-review-4`, f497a387); R4-01..R4-13 being addressed |
| Q17g | structural | 3.4 ownership/storage-order/declared-reads, 3.6 keys/fk/capacity/row-permutation/frame per module (AUDITD) | done (7b72fc52, 625194dc, a6892eb4, 82027430) |
| Q17h | trace-replay | 3.7 trace replay through the breadth machines and lock logs per module (AUDITE) | done (e8a3ab67, e4fd212b): 13 modules replayed; 09 open, 15 blocked |
| Q17i | orchestrator | 3.1-intent per module: structural intent check (`intent-structure-check`, `-selftest`) | done (05a86981) |
| Q17j | ontology-2 | 3.1-coverage and remaining 3.1-cells | done (e4fd212b): 3.1-coverage 0 uncovered; 3.1-cells closed |
| Q17k | contract-2 | 3.2-coverage per module; premise E-1 via the pin's own compiled &sql (AUDITCORE, AUDITENV) | done (cd45f771): 3.2-coverage closed; E-1 validated |
| Q17l | reflection | 5c root causes, 3.8 test reflection | done (bad04b31): 33 root causes, 224 premises mapped |
| Q18a | proofs-d9c | Review R4-01/03/04: guard G-BM, F-C1350 control, F-1306 as direct SQL | done (cd45f771): 158 verified, 14 controls |
| Q18b | proofs-mech | D-14: mechanism laws proved once over a trait in Verus | done (e9041b19) |
| Q18c | refusals | 5c-refusals for 01, 04, 06, 10, 11, 15-18; 3.5-decoders 07, 10, 18 (AUDITE) | done (1529a141, 95abaf5f) |
| Q18d | writesets | breadth-a module-invariant pairs for 01, 03-06; 08; 18 restore_merge | done (728e18a1): 561/566, 5 open |
| Q18e | reflection | root causes and premise map for every new finding and crate; TEST-REFLECTION refresh | done (3d75a633) |
| Q18f | orchestrator | exclusive-container worlds: repeated crash trials, SynchCommit=1, product-level licence refusal (S6) | done: live-crash-repeat-sc0, -sc1, live-licence-world |
| Q18h | proofs-env | D-7: the IRIS environment contract as a Verus specification, premises linked, differential link to the executable contract | doing (steer 12) |
| Q18g | orchestrator | STATUS/TRUST/PROOF-DEBT refresh; verify.sh --live --clean on a committed tree; fifth review | doing: account refreshed (1dff8e3c, 82027430); clean gate on the candidate running |
| I-1..I-4 | orchestrator | Incidents: IVG460SNAP, USER-REDEPLOY-08, superseded proof logs, health alert | recorded in `incidents/` |

Genuinely unavailable (attempts in `versions/AVAILABILITY.md`): an IRIS 2026.3 engine (no public tag; the cited
`irishealth:2026.3.0AI.113.0` is on an internal registry); an IRIS Enterprise / IRIS for Health image or licence (SC-003's
target, edition comparison, more than 8 licence units); `%AI` classes (MCP); FHIR server classes (`HS.FHIRServer`); a
multi-node ECP/mirror setup; an x86_64 `libarno_callout.so` (F-1001). Set up and used, so not blockers: driver 5.4.0,
IRIS 2026.2 (isolated container, stopped and kept), a disposable least-privilege user (disabled). Operator ruling O-1
(review-2 condition 6) given on 2026-11-14: the pinned 4.5.1 fixture and the `IVGDev` helpers are authorized setup
(`incidents/O-1-FIXTURES.md`); the operator applied it also to the second fixture namespace `IVG262CAP` (22:42 UTC).
