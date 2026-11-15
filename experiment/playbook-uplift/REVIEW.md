# Independent review (playbook §3.8)

Reviewer: a separate read-only agent with no part in writing the worked example, briefed with the code, the intent sources
(ADR-0004, ADR-0013, spec 256) and the uplift's claims, asked to confirm or refute them adversarially. Scope: modules 12–14,
`FINDINGS.md` F-1201..F-1402, `semantics/SEMANTICS.md`, `proofs/src/l2.rs`, `model/src/redaction.rs`, the live traces.

## First pass: NO SIGN-OFF

Findings F-1302, F-1303, F-1304, F-1305, F-1306 and F-1401 were confirmed real at the pin and not artefacts of the harness (for
F-1302 the reviewer checked that the late commit ran committed at `$TLEVEL` 0 in the lock holder's process, and that the same
interleaving occurs without the harness because batches that match nothing release the lock without setting the marker).

Every review finding and what was done (playbook: each becomes a fix or a recorded decision):

| # | Review finding | Resolution |
|---|---|---|
| 1 | One target predicate stands for three scopes in the code (Eraser SQL, `LiveRows`, `Matches`); F-1305 refutes RPL-B3 and SEMANTICS §4 as stated | Fixed: premise P-1310 added; RPL-B3, SEMANTICS §4, STATUS and MODELS now state the theorem only for one-scope separable targets and record the F-1305 failure |
| 2 | The reviewed-design proof of RED-B1.1 assumes an atomic erasure; the liveness check reads uncommitted deletes and erasure takes no head lock | Fixed: premise P-1311 added and cited with `open:HD-1201` on RED-B1.1; STATUS row qualified; MODELS lists it as unmodelled |
| 3 | Cell "redacting / retry an old key" is wrong: a still-bound key is replayed before the commit check, re-applying post-commit properties | Fixed: cell is now open on HD-1305; F-1306 records that it happens during a run too |
| 4 | "`control_unmarked_start` is the pin" is incomplete; L2 cannot express audit counts | Fixed: module 13 scope, RED-Q1, F-1302, `proofs/src/l2.rs` header, MODELS and STATUS now say the pin is `control_unmarked_start` with `control_other_target`, and that L2 has no counts |
| 5 | Stale live numbers (F-1303, RED-B6.1, RED-I3) | Fixed: counts from every run quoted (10/6, 14/2, 1/15 against 9/7); six stops in the final campaign |
| 6 | SC-001 and US3/FR-006 not stated; RED-T1 cites a plan that endorses the defect | Fixed: RED-B12 (SC-001), RED-T3.1 (FR-006, US3), RED-T3.2 (SC-003, not measured) added; RED-T1 and F-1302 now cite `plan.md:23` as prescribing the late marker |
| 7 | Cell "running / disable the ledger" is wrong: `Disable` does not check the marker | Fixed: outcome `ok`; the run stops at its next batch (RED-X3) |
| 8 | RED-I3 cites a proof for batch atomicity, which the model assumes | Fixed: the proof citation removed; Notes say the models assume it (P-0001) and the live runs observe it |
| 9 | The models omit statement state and `DropStatements` | Recorded in MODELS ("Not in the proofs"); the live scenarios check statement entries after every step |
| 10 | RED-B2 claims "proved" without the unattributed-records exception | Fixed: Notes state the exception and the P-1301 premise |
| 11 | RED-B2.1 says the tombstone keeps "nothing else", but it keeps flags | Fixed: statement now names digest, kind of change and flags |
| 12 | F-1304 omits the intent it violates | Fixed: cites `plan.md:10` |
| — | Spec items also missing: author fields kept; deletes still refused; one added revision | Fixed: RED-B3.2, RED-T2.1, RED-B7.3 added (RED-B7.3 notes the spec edge case that contradicts Decision 1) |

Raised during the review window by the uplift itself: F-1402 was reproduced live (`reader_races_redaction`) and three
ObjectScript mutants were killed live (`native/mutants.py`).

## Second pass: SIGN-OFF

The reviewer re-checked every resolution against the files and traces and marked all 12 RESOLVED. It also checked the new
evidence: `reader_races_redaction` commits one real batch from another IRIS process between `reconstruct()`'s marker check
and its read (no product code changed), and `mutants.json` shows each mutant killed by the expected checks with the restored
classes passing all 14 scenarios.

Four wording problems introduced by the fixes, all corrected afterwards:

| Problem | Correction |
|---|---|
| P-1310 said `LiveRows` checks every graph for any prefix target | Now: every graph for a default-graph prefix target, the target graph only for a named-graph target (`LedgerRedact.cls:161-164`) |
| RED-B12 named only F-1305 as a failure of SC-001 | Notes now add unattributed records and a stuck run's plain-text marker |
| RED-B7.3 "adds just one revision" contradicted RED-B7.2 (a no-op adds none) | Now "at most one" |
| RPL-B3 said "six scenarios" while citing four; a lowercase sentence start in RED-T1 | Fixed |

Sign-off text: "the six defects are confirmed real at the pin. Every 'proved' claim is now limited to the reviewed design under
named premises (P-1301, P-1310, P-1311), the wrong cells and stale numbers are fixed, and the gaps in the models are listed."
