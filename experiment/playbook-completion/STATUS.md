# Completion audit of iris-vector-graph: status

Product pin `3eaa79cf77d3e0a879b2cced634cf2729d81499e` (tree `b098a6f4`), unchanged: `check-product-scope.sh` passes at
every commit. Original submission `9c3719c1` unchanged and attributable. Engine: InterSystems IRIS 2026.1 Community
(Build 234U), dedicated container, client `intersystems_irispython 5.3.2` (the product's `uv.lock` pin, on which the
product misbehaves: F-C1706; 5.4.0 and IRIS 2026.2 compared). PGspec not used. Observation-only: every defect is
recorded, none fixed. One verification entry point: `verify.sh` (`--fast`, `--full`, `--live`, `--clean`). Scope
clarification O-1 (operator, `incidents/O-1-FIXTURES.md`): the pinned 4.5.1 fixture and the `IVGDev` helpers are
authorized test setup.

**Verdict: not complete.** Every module went through every phase, and most matrix cells are closed with registered
evidence (counts in Numbers, below, generated and checked by the fast gate). Applicable gates remain open or failed:
- no proof connects the ObjectScript/Python code to the models, because no verifier exists for either language
  (PROOF-DEBT D-2..D-6: 3.4-statements, 3.5-handlers, 3.5-lockplans, 3.6-composition);
- the product fails most obligations the evidence touches (findings below; cells labelled `fails` in Numbers);
- every finding still needs a maintainer's fix or recorded decision (3.8-findings-disposed);
- the independent review signed off the account (the specification against intent and its accuracy, not the product) in its sixth
  pass, for candidate `76fb07ce` (`independent-review-6`); passes 1-5 did not, and their conditions are answered in `review/`;
- the clean live gate passed on candidate `25ba22dd` (`verify-clean-25ba22dd`: 73/73 steps exit 0, 5,119 s, every crate built
  from an empty target; the earlier run on `a42f10c8` failed nine proof readers and is kept); its slowest step,
  `proofs-mech`, takes 2,230 s, above the 20-minute single-gate target (5a-gate-20min stays open).

Read the matrix (`matrix/MATRIX.md`) as two questions per cell: was the verification step done with adequate evidence
(status), and does the product meet the obligation (product label). A model result never counts as a product result.
`holds-live`/`holds-inspected`/`holds-as-detection` appear only on single write-set pairs discharged at the pin.

## Phase-by-phase verdict

| Phase | Baseline (submission 9c3719c1) | Now | Gate |
|---|---|---|---|
| §3.1 ontology | lexical-scope reading; 1,392 literal-rule pairs | literal rule enforced (42 negative controls); 4,216 statements, 0 violations; coverage reconciled against the source inventory: 3,580 entries, 0 uncovered (`ont2-coverage-r2`); intent recovered for all 61 decisions (`intent-structure-check`) | **closed** except 5 reach obligations (REACH-1..5: should erase/redact reach these stores? maintainer) |
| §3.2 environment | four behaviours sampled | the clauses the proofs rely on as a Verus specification (`proofs-env`, D-7 paid for its Verus subset: every proof premise linked by a theorem or a verdict; an exec model verified against it agrees with the executable contract on every recorded in-subset case, 29/29 model mutants killed); executable IRIS contract r6 (516 cases, 0 outside, 42/42 mutants) plus contract-2: E-1 (embedded SQL) validated on the pin's compiled code, 7 X2 clauses (190 cases, 0 outside, 29/29 mutants); every IRIS feature the product's code uses classified as inside, validated or outside with a named premise, none unclassified (totals over all 19 modules in Numbers; `env2-coverage-2`) | **closed** |
| §3.3 models, protocols, progress | one proof (53 verified), 11 checks | 12 Verus crates for the models (with `proofs-env`, §3.2, 13 crates in Numbers), 0 errors, empty trust inventory, every crate rechecked: Protocol2 composition; D-9 under the pin's real premises (`proofs-d9`, `-d9b`, `-d9c`, where a locked Start and the assumed guard G-BM exclude F-C1350); L1/L2 refinement for every module with operations (`proofs-breadth`, `-d1b`..`-d1f`, `-pa3` without premise P-A3); progress-only controls (incl. D-12); 6 explorer crates, 645 checks, incl. M1 (2+2) exhaustive by partition | **closed at model level**; no reviewed guard exists at the pin, so no result transfers to the product |
| §3.3a semantics | worked example; 83 obligations by hand | 14 axioms, 13 mechanisms whose 45 laws are proved once over a trait (`proofs-mech`, 1,149 verified, 120 located controls), 8 lifecycles, 77 objects; 2,884 of 2,939 requirements traced; write sets: 185 census obligations and 566 breadth-a module-invariant pairs discharged by lemma, guard or finding, the rest open with a reason (counts in Numbers; `ws-check-r4`) | **open**: 3.3a-trace (55 requirements outside the validated contract), 12 write-set cells (FHIR classes absent; unreached SQL fallbacks; four purge pairs whose intent is undecided) |
| §3.4-3.6 storage, handlers, composition | not done | ownership, storage order, row permutation, keys, FK, capacity, frame (catalog/dictionary oracle) and declared reads (non-interference oracle) per module; decoders and status maps; trace conformance; CLOSURE.md: every environment condition (177 at this commit), each validated, partly validated, assumed with its consequence, or false at the pin | **open**: statement, handler and lock-plan proofs and composition (no verifier); declared reads 10 fails (F-C1041, F-C1046: ^NKG class methods answer all graphs merged) and 8 Arno-library readers cannot run here (F-1001); frame 07, 09, 15 (an older release's edge rescue, plan compilation, FHIR classes). Capacity 01 closed: the pin's upgrade of a loaded v4.5.1 namespace (built by the O-1 fixture) completes in 14 s with no limit hit; the 3.x whole-table migrations need the v3.2.0 fixture, which O-1 does not cover |
| §3.7 validation | 14 scenarios; no crash/perf | upstream suites on the unchanged pin with every failure triaged; trace replay of 17 modules through their machines with controls, lock logs; crash world 3+3 trials per SynchCommit setting; lost-ack; disconnect (49 trials); licence refusal (S6); every failure scenario with a negative control; SC-002/SC-003 measured; lint and style under the product's own rules (fail) | **closed** except blocked: editions (2026.3, Enterprise), multi-node, licence-bound suites, perf baselines needing Enterprise/Arno, mutation of product code (operator question O-2), FHIR (15); full clean rerun passed (`verify-clean-25ba22dd`) |
| §3.8 account | review signed off the worked example | STATUS (this file, numbers generated and checked), TRUST (incl. log provenance), PROOF-DEBT, matrix, root causes (36 causes, `rf-root-causes-check-r3`), test reflection (274 premises mapped), four independent reviews | **open** only for maintainer decisions on every finding (3.8-findings-disposed); review signed off in pass 6 (`independent-review-6`) |
| §5 hygiene, proof debt | — | locks, timeouts, disk floor; every unproved obligation in PROOF-DEBT.md | **open**: lock holds are not logged (5-hygiene); `proofs-mech`'s gate takes ~35 min, above the 20-minute single-gate target (5a-gate-20min) |

## What changed since the baseline (each with evidence)

- All 197 original findings have fresh evidence on the pin, and the audit added new ones (counts in Numbers, below).
  F-1201 and F-C1301 are reproduced live; F-0601 live with the disposable least-privilege user.
- Proof debt D-1, D-7 (for the contract's Verus subset), D-9, D-10, D-12, D-13 and D-14 are paid at model level
  (PROOF-DEBT.md); D-2..D-6 and D-8 remain.
- The randomized simulator (304 schedules, 13,282 commits checked) found F-CS01; the stated-refusal audit (244 X
  statements: 186 hold live, 29 by upstream tests, 13 defects, 11 blocked) found 8 more defects.
- Durability: under SynchCommit=0 an acknowledged commit is lost in 3 of 3 crash trials; under SynchCommit=1 in 0 of 3
  (`live-crash-repeat-sc0`, `-sc1`; the container is restored to SynchCommit=0). F-C1102 stays intent-undecided.
- Version difference in the product's premise: on 2026.1 and 2026.2 SQL `COMMIT`/`ROLLBACK` end one level, not every
  level (F-C1705).

## Highest-consequence product findings (S1)

Every reproduced or source-confirmed S1 finding is listed in Numbers (generated). The ones with the widest reach:

| Id | Finding | Evidence |
|---|---|---|
| F-1302, F-1303 | redaction start is unlocked and its marker late: history of content a concurrent commit made live is tombstoned; concurrent redactions mix counts | original live run; `live-native-rerun-1314` |
| F-1304, F-1305 | default-graph or graph-per-tenant redaction tombstones history of live nodes, or reports success while history remains | `live-native-rerun-1314` |
| F-C1350, F-C1351, F-C1250 | ledger-bypassing writers re-create a target's content after the entry check and batches tombstone it; `%NOINDEX` bulk loads escape the liveness check and survive erasure | `ws-live-ins-*`, `ws-live-noindex`, `ws-live-noindex-erase` |
| F-C1201, F-C1301 | redaction completes against an open erasure or bypass delete that later rolls back | `ib-HD1201-open-erasure`, `ws-live-fc1301-delete-reification` |
| F-C1850, F-1801 | a restore lays the archive's ledger and redaction state over the live ones | `ws-live-gap-restore`, `ws-live-gap-marker`, `c18-live-ledger-overlay` |
| F-C1306 | after a supported 4.5.x upgrade, redaction leaves revision text in legacy rows | `fc1306-legacy-ledger-rows` (setup authorized, O-1) |
| F-1306, F-1402 | a retry re-applies post-commit properties; readers return partially redacted views | `live-native-rerun-1314`, `ib-HD1401-reader-full-race` |
| F-C1308, F-C1203 | temporal-only edges are invisible to redaction's liveness check and survive a prefix erase | `fu-r04-temporal-only-live-b` |
| F-C0702 | a failing BM25 write rolls back the caller's whole transaction | `findings/audit/07.json` |

## Remaining blockers (exact)

- **No verifier for ObjectScript or Python**: §3.4 statement lemmas, §3.5 handler and lock-plan proofs, §3.6
  composition over real transactions (PROOF-DEBT D-2..D-6). Trace replay, frame/read oracles and conformance are the
  strongest correspondence evidence.
- **Genuinely unavailable** (attempts in `versions/AVAILABILITY.md`): IRIS 2026.3 (internal registry only); Enterprise
  or IRIS for Health and its licence (FHIR server classes, more than 8 licence units, SC-003's target platform);
  `%AI` classes; multi-node ECP/mirror; x86_64 `libarno_callout.so`.
- **Operator question O-2**: mutation testing of product code (3.7-mutation) needs mutated copies of product code,
  which the binding rule excludes (model mutations only).
- **Maintainer decisions** for every finding (§3.8) and the residual questions below.

## Assumptions carried (named, with status in TRUST.md)

Progress premises (fair scheduling, operator re-runs, a weakly fair queue worker) are assumed; "no writer makes a
marked target live" is false at the pin (F-C1307). The reviewed designs' guards do not exist at the pin. 65 environment
conditions are assumed with their consequence (CLOSURE.md). Durability results hold per setting as tested.

## Residual maintainer questions, by consequence (working answer / best alternative)

1. **Tenant identity and completeness of removal** (HD-1304, 1101, 1401, 1303b; F-1304, F-1305, F-C1306, F-C1308,
   F-C1304, F-C1250, REACH-1..5). Working: require tenant prefixes or return an explicit incomplete result; name every
   store a removal does not reach. Alternative: record each node record's graph and migrate history.
2. **Writers outside the ledger during redaction** (F-C1350, F-C1301, F-C1307; the RED-B1.1 reading). Working: bypass
   writers honour the marker (G-BM, an assumed reviewed guard; with it and a locked Start, `proofs-d9c` proves that no live
   content is tombstoned). Alternative: each batch re-checks liveness on
   committed state; or an enforced quiet admin mode.
3. **Serialization of erase, writes and redaction start** (HD-1201, 1301; F-1201, F-1302, F-1303, F-C1201). Working: one
   lock across erase, commits and redaction start. Alternative: refuse while transactions are open.
4. **Recovery of a stuck redaction** (HD-1303a; F-C1303, F-C1307). Working: persist the scan cursor with the marker.
   Alternative: an audited cancel recording a partial redaction.
5. **Restore against a live ledger** (HD-1801; F-1801, F-C1850, F-C1304). Working: refuse when heads diverge.
   Alternative: explicit wholesale replacement that replays later redactions.
6. **A changeset that changes nothing** (F-CS01). Working: write no revision (or clear zero-record revisions at Final).
   Alternative: content-free no-op records.
7. **Durability premise** (F-C1102). Working: require SynchCommit=1 (no acknowledged commit lost in 3 of 3 crash trials with it: evidence, not proof) and say so.
   Alternative: document that an acknowledged revision can be lost on a crash and that an idempotent retry recovers it.
8. **Retries after an unknown outcome** (HD-1305, 1603, 1702; F-1306, F-C1703). Working: never re-apply post-commit
   properties on replay. Alternative: record post-commit completion with the revision.
9. **Cross-graph blocking by lock escalation** (F-C0347). Working: keep caller transactions below the escalation
   threshold and document it. Alternative: configure the threshold for IVG's tables.
10. **Supported engine versions** (F-C1705). Working: rely only on TSTART/TCOMMIT/TROLLBACK 1 and correct the premise
    text. Alternative: test the plain path per version.

## Numbers

<!-- numbers:begin (generated by tools/status_numbers.py; do not edit) -->

| Quantity | Value |
|---|---|
| Original findings (submission 9c3719c1) | 197: blocked-access 2, confirmed-source 34, intent-undecided 2, not-reproduced 2, refuted 1, reproduced-live 141, reproduced-model 3, reproduced-test 12 |
| New findings (F-C*, duplicates excluded) | 114: confirmed-source 22, intent-undecided 4, not-reproduced 1, refuted 1, reproduced-live 78, reproduced-model 4, reproduced-test 4; S1 12, S2 37, S3 33, S4 32 |
| Duplicate finding records (merged into another id) | F-C1720 |
| Reproduced or source-confirmed S1 findings | 43: F-0304, F-0409, F-0505, F-0606, F-0702, F-0705, F-0707, F-0711, F-0802, F-0814, F-0815, F-0816, F-0818, F-0820, F-1002, F-1008, F-1101, F-1114, F-1302, F-1303, F-1304, F-1305, F-1306, F-1402, F-1502, F-1503, F-1603, F-1604, F-1701, F-1709, F-1801, F-C0702, F-C1201, F-C1203, F-C1250, F-C1301, F-C1306, F-C1308, F-C1350, F-C1351, F-C1803, F-C1804, F-C1850 |
| Verus crates (baseline verified / errors / controls) | 13 crates, 2726 verified in total: `proofs` 88/0/5; `proofs-breadth` 94/0/7; `proofs-d1b` 92/0/11; `proofs-d1c` 111/0/10; `proofs-d1d` 118/0/21; `proofs-d1e` 115/0/15; `proofs-d1f` 115/0/17; `proofs-d9` 115/0/7; `proofs-d9b` 158/0/15; `proofs-d9c` 158/0/16; `proofs-env` 305/0/17; `proofs-mech` 1149/0/120; `proofs-pa3` 108/0/9 |
| Explorer crates (checks in RESULTS.json) | `breadth-a` 104; `breadth-b` 132; `breadth-c` 39; `core` 82; `core-partition` 16; `semantics` 272 |
| Write-set discharges (census obligations; breadth-a module-invariant pairs) | census 185: finding 64, guard 9, lemma 105, open 7; breadth-a 566: finding 190, guard 20, lemma 352, open 4 |
| IRIS features used by the product's code, all 19 modules (contract-2) | inside 784, validated 324, outside 1237, unclassified 0 |
| Matrix cells by status | blocked 24, closed 611, not-applicable 35, open 82 |
| Matrix cells by product obligation | fails 408, holds-as-detection 36, holds-in-model-only 1, holds-inspected 69, holds-live 9, intent-undecided 6, n/a 33, unknown 190 |

<!-- numbers:end -->
