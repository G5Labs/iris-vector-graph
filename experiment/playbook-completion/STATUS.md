# Completion audit of iris-vector-graph: status

Product pin `3eaa79cf77d3e0a879b2cced634cf2729d81499e` (tree `b098a6f4`), unchanged: `check-product-scope.sh` passes at
every commit. Original submission `9c3719c1` unchanged and still attributable. Engine: InterSystems IRIS 2026.1
Community (Build 234U), dedicated container, client `intersystems_irispython 5.3.2` (the product's `uv.lock` pin, on
which the product misbehaves: F-C1706; driver 5.4.0 compared in the validation lane).
PGspec not used. Observation-only: defects are recorded, never fixed. One verification entry point: `verify.sh`.

**Verdict: not complete.** Candidate `0eec4df8` passed the single entry point (`verify.sh --live`, 33 steps, 708 s, `verify-final-candidate`), which reruns every gate's evidence; that run itself reproduces product defects (F-1201 4/4). The audit took every module through the playbook's phases and closed many gates with
registered evidence, but applicable gates remain open or failed: no proof connects the ObjectScript/Python code to the
models (no verifier exists for either), the product fails many obligations (findings below), the §3.8 independent
review did not sign off, and "every finding becomes a fix or a recorded decision" needs the maintainer.

Read the matrix (`matrix/MATRIX.md`, generated) as two separate questions per cell: was the verification step done
with adequate evidence (status), and does the product meet the obligation (product obligation). A model result never
counts as a product result: reviewed designs that are proved or model-checked are labelled model-level.

## Phase-by-phase verdict

| Phase | Baseline (submission 9c3719c1, per baseline-audit.md) | Now | Gate |
|---|---|---|---|
| §3.1 ontology | lexical-scope reading; 1,392 literal-rule pairs in 1,002 statements | literal rule enforced by a strengthened checker (42 negative controls, differential equal to the independent script); repaired ontology 3,877 statements, 0 violations; completion and follow-up findings cited (51 finding tags on 35 statements); 14 statements' model evidence marked model-only; a reproduced finding's named statement can no longer keep an uncited proof tag (`rr2-ontology-*`) | **open**. Closed: the four product-scope gates (3.1-parent, -grade, -terms, -index). Open in the matrix: 3.1-cells 10 of 19 module cells, 3.1-coverage 19 of 19 module cells plus 5 reach obligations (review R2-10), 3.1-intent 17 of 19. Also open: system-module terms are not checked across modules (maintainer question) |
| §3.2 environment | four IRIS behaviours sampled; no contract | reusable executable IRIS contract, extended with 10 clauses the modules rely on (functional indexes, %NOINDEX/BUILD INDEX, DDL in transactions, NULL/empty strings, statement atomicity, ordering, vectors); round r6 on a fresh seed: 516 cases, 0 outside, 515 single-outcome, 42/42 mutants (`env-ext-r6`, recheck `env-contract-r6-recheck`), again 0 outside and 42/42 on a new seed in the candidate run; the same contract holds on IRIS 2026.2 with drivers 5.3.2 and 5.4.0 (`ver-e262-d532-full`) | **closed** for the validated subset; outside-subset features keep module `3.2-coverage` cells open |
| §3.3 models, protocols, progress | one combined L1/L2 proof (53 verified), 11 explorer checks; no Protocol2; no progress-only control | core: 82 explorer checks (three predicates, concurrency, retry, readers), reviewed M2 refines an executable L1; `Protocol2` composition in two levels, 88 verified/0 errors, 4 located design controls, a progress-only control failing only `progress.rs:165` (model-level); breadth: 275 bounded checks with controls for modules 00-11, 15-18; Verus L1/L2 refinement for modules 11 and 04 (94 verified, 0 errors, 7 located controls, `proofs-breadth-*`, recheck `proofs-breadth-recheck`) | **closed at model level**; Verus refinement for the other 15 modules is proof debt (D-1); the proofs' premises are false at the pin (PROOFS.md, TRUST.md: P-C02, P-A3); no D-2 progress control (D-12). Product: every closed proof cell of modules 04 and 11-14 and the protocol cells show `fails` (located controls encode the pin's behaviour; reproduced findings) |
| §3.3a semantics | worked example only; 83 obligations from a hand manifest | source-derived writer census: 269 sites, 46 undeclared writers, 162 (invariant, writer) obligations, 20 conditional, 3 write-set gaps (`followup-writer-census`), each now an open matrix cell (`matrix-input/writer-census-obligations.json`) | **open**: obligations not discharged (3.3a-writesets: 199 open cells); product fails INV-no-live-tombstone (F-C1301, F-C1308) and restore's write-set gaps (F-1801) |
| §3.4-3.6 storage, handlers, composition | not done | correspondence for modules 11-14: 13 of 15 actions trace-checked against an executable abstraction to the proof models; unchecked lines listed exactly (281/1,760 ObjectScript, 181/690 Python); frame/keys/FK/integrity/capacity per module; 18 lock-plan probes match source; decoder map 15/15 (`corr-*`, `decoder-map-ledger`) | **open**: statement and handler proofs need a verifier that does not exist (D-2, D-3); several conditions failed (F-1801 keys, F-1306 FK); the abstraction check is blind to temporal-only edges and to completeness at Final (stated on the 3.5-handlers and 3.7-trace-replay cells); 5 ledger writers lie outside every modelled action, not 1 (closure scan reconciled with the census) |
| §3.7 validation | 14 scenarios, upstream spec-256 suite; no crash/lost-ack matrix, no perf | journal-oracled trace conformance (controls); F-1201 reproduced live 8/8; lost-ack world exactly-once in 6/6; instance crash world: all-or-nothing recovery, acknowledged commit lost with SynchCommit=0 (F-C1102, intent-undecided); fresh rerun of 10 original scenarios; upstream suites on the unchanged pin, every failure triaged: unit 24,794 passed, integration 2,651, e2e 3,348 (gate off) and 10,122 (146 gated files), r306 oracle 7,406, TCK 3,895/3,896, docs 15/16, multi-process ledger cases 15/15 x3 (`val-*`); spec 256 SC-002 verify equal and SC-003 100,000 records in 1.4 s, longest commit wait 28-311 ms (1 committer) and 31-36 ms (3 committer processes), Community 2-CPU container, not the spec's Enterprise laptop; version lane: driver 5.4.0 and IRIS 2026.2 give the same transaction-verb results as 2026.1 (F-C1705: only the unobtainable 2026.3 engine remains); validation's product defects filed as F-C1706, F-C0502, F-C1002, F-C0606 (`findings/audit/zz-validation.json`) | **open**: editions blocked; multi-node blocked; see Validation |
| §3.8 account | review signed off the worked example | STATUS, TRUST, PROOF-DEBT, matrix; independent review: **no sign-off** in either pass (`independent-review-1`, `independent-review-2`); conditions 1-5 and 7 of the second pass answered in `review/RESPONSE-2.md`; condition 6 needs an operator ruling; §5c's randomized simulator through the real product not run (`5c-reviewers` open) | **open** |

## What changed since the baseline (each with evidence)

- F-1201 moved from model-only to **reproduced live** (`live-f1201-reproduced`), with the journal as an independent
  oracle of the interleaving.
- All 197 original findings have a disposition with fresh evidence on the pin: 139 reproduced live, 35 confirmed from
  source, 12 by an upstream test, 3 by model, 3 intent-undecided (F-0401, F-0503, F-1201: the behaviour is observed,
  the intent rests only on an Assumption HD; review R-11, R2-08), 2 not reproduced, 2 blocked on access, 1 refuted
  (`findings/audit/*.json`, as the matrix counts them). 59 new findings (8 S1, 22 S2, 16 S3, 13 S4; 36 reproduced live,
  4 by an upstream test run here, 5 by model, 10 from source, 3 intent-undecided: F-C0402, F-C1102, F-C1108).
- The three targeting predicates, graph-blind node provenance, overlapping ids, statement/tuple maps, post-commit
  replay, per-target counters, marker ownership/absence, concurrent erase/start, abort and recovery are each modelled
  (`models/core/MODELS.md`).
- A version difference in the product's own environment premise is recorded: on 2026.1 with the locked driver, SQL
  `COMMIT`/`ROLLBACK` end one level, not every level (`iris-contract/CONTRACT.md`).
- The intent of all 61 decisions was recovered independently (`intent/`), with 49 discriminating probes; working
  answers that changed say why; none is presented as upstream approval.

## Highest-consequence product findings (S1)

| Id | Finding | Evidence |
|---|---|---|
| F-1302 | redaction tombstones history of content a concurrent commit made live (unlocked start, late marker) | original live run; core M2 |
| F-1303 | concurrent redactions mix audit counts; one removes the other's marker | `live-native-rerun-1314` |
| F-1304 | unprefixed default-graph redaction tombstones history of nodes live in a named graph | `live-native-rerun-1314` |
| F-1305 | graph-per-tenant redaction reports success while node history remains | `live-native-rerun-1314` |
| F-1306 | a retry re-applies post-commit properties and revives erased content | `live-native-rerun-1314` |
| F-1402 | a reader returns a partially redacted view (also across pages with no marker) | `live-native-rerun-1314`, `ib-HD1401-reader-full-race` |
| F-C1201 | redaction completes against an erasure still open; the erasure rolls back: content live, history redacted | `ib-HD1201-open-erasure` |
| F-C1306 | after a supported 4.5.x upgrade, redaction leaves the tenant's revision text in legacy rows (SC-001 fails) | `fc1306-legacy-ledger-rows` |
| F-C1308 / F-C1203 | live temporal-only edges are invisible to redaction's liveness check and survive a prefix erase | `fu-r04-temporal-only-live-b` |
| F-C1304 | snapshot archives keep and restore a redacted tenant; the receipt omits them | `fu-r01a-snapshot-copies` |
| F-C1301 | the liveness check reads any writer's uncommitted delete (model) | `core-m2-as-built-commit-rollback` |
| F-C0702 | a failing BM25 write inside a caller's transaction rolls back the caller's whole transaction | breadth B (`findings/audit/07.json`) |
| F-C1803 | `Graph.KG.Snapshot`'s unused file helpers read (shown live), write and delete server files for a Native API caller | breadth C (`findings/audit/18.json`) |
| F-C1804 | snapshots carry no routed edge vectors: after a restore the registry says present and search returns nothing | breadth C (`findings/audit/18.json`) |

Others of note: F-C1303 (a bounded redaction resume never finishes, live), F-C1307 (one writer keeps a redaction open
and blocks every tenant, live), F-1801 (restoring an older archive breaks every later commit), F-C1706 (the pin's own
uv.lock installs a driver on which scores come back as Decimal, duplicate skips raise and list parameters fail, S2).
Observed but intent-undecided: F-C1102 (acknowledged commit lost on crash with SynchCommit=0, live; no IVG document
states a durability premise) and F-1201 (a graph erasure removes the statement entry of a concurrent commit's edge,
live 8/8; its intent rests on HD-1201).

## Remaining blockers (exact)

- No verifier for ObjectScript or Python: §3.4 statement lemmas, §3.5 handler proofs and §3.6 composition over real
  transactions stay open; trace conformance and line coverage are the strongest correspondence (PROOF-DEBT D-2..D-6).
- Genuinely unavailable here (attempts recorded in `versions/AVAILABILITY.md`): an IRIS 2026.3 engine (no public tag;
  the cited `irishealth:2026.3.0AI.113.0` is on an internal registry); an Enterprise or IRIS for Health image/licence
  (SC-003's target platform, edition comparison, more than 8 licence units for the spec-236 scratch suites and
  8-writer soaks); `%AI` classes (MCP); FHIR server classes; a multi-node ECP/mirror setup; an x86_64
  `libarno_callout.so` (F-1001; documented path needs arm64). Driver 5.4.0, IRIS 2026.2 and a least-privilege user
  were set up and used (they are not blockers).
- Maintainer decisions for every finding (§3.8), and the residual questions below.

## Assumptions carried (named, with status in TRUST.md)

Progress premises (fair scheduling, operator re-runs, ledger re-enabled) are assumed; the fourth, no writer makes a
marked target live (P-C02 for progress), is false at the pin (F-C1307). The reviewed protocol's safety premises are
false at the pin (PROOFS.md), and so is the breadth proofs' P-A3 (an eraser overlaps no writer of its graph). Embedded
SQL is assumed equal to dynamic SQL for the contract's clauses; durability results are for SynchCommit=0 only (the
tested setting, `env-synchcommit-setting`). All of these are rows of TRUST.md's premise table.

## Residual maintainer questions, by consequence (working answer / best alternative)

1. **Tenant identity and completeness of tenant removal** (HD-1304, 1101, 1401, 1303b; F-1304, F-1305, F-C1306, F-C1308,
   F-C1304, F-C1305). Working: require tenant prefixes or return an explicit incomplete/refused result when node history
   cannot be attributed; name every store a removal does not reach in the receipt. Alternative: record each node
   record's graph and migrate history.
2. **Serialization of erase, writes and redaction** (HD-1201, 1301; F-1201, F-1302, F-1303, F-C1201, F-C1301, F-C1307).
   Working: erase, commits and redaction start serialize on one lock; the marker is owned per target from the start;
   callers may get busy/refused. Alternative: an enforced quiet admin mode that refuses open transactions and
   ledger-bypassing writers.
3. **Recovery of a stuck or interrupted redaction** (HD-1303a; F-C1303, F-C1307). Working: persist the scan cursor with
   the marker; re-erase and resume. Alternative: an audited cancel that records a partial redaction.
4. **Restore against a live ledger** (HD-1801; F-1801, F-C1304). Working: refuse before mutation when heads diverge.
   Alternative: explicit wholesale replacement that replays later redactions.
5. **Durability premise** (F-C1102). Working: require SynchCommit=1 (or a journal flush before acknowledging) and say
   so. Alternative: document that an acknowledged revision can be lost on a crash and that an idempotent retry recovers it.
6. **Retries after an unknown outcome** (HD-1305, 1603, 1702; F-1306, F-C1703). Working: retry only reads or writes known
   not to have run; never re-apply post-commit properties on replay. Alternative: record post-commit completion
   atomically with the revision.
7. **Strict-mode guard window** (HD-0801). Working: refuse with no cache window. Alternative: document the 5 s window and
   fail-open.
8. **Read consistency** (HD-1401, 0903, 1802). Working: an epoch check for multi-page readers and exports, or an explicit
   quiet-writer premise. Alternative: documented per-store dirty reads.
9. **Supported engine versions** (version difference above). Working: state that the main write path relies only on
   TSTART/TCOMMIT/TROLLBACK 1, and correct the 2026.3 premise text. Alternative: test the plain path on each version.
