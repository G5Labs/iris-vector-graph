# Independent review, second pass (playbook §3.8, §5c)

Reviewer: independent reviewer lane (read-only). Product pin `3eaa79cf` (tree `b098a6f4`, unchanged). No IRIS
connection, no live run, no commit; I wrote only `review/REVIEW-2.md` and `review/review-2.json`.
`PC/` = `experiment/playbook-completion/`. First pass: `review/REVIEW.md` (R-01..R-13).

**What was reviewed, and when.** Sections 1-3 review audit state `3d1095e3` plus the lanes' uncommitted work at about
04:40 UTC. While I worked, the orchestrator read my **unfinished draft** of this file, registered it as
`independent-review-2` (05:14, `$RUN_DIR/review/REVIEW-2.md`, which still holds an unfilled evidence section) and
committed responses to its conditions (`0eec4df8` "Address the second review's conditions 1-5 and 7", `fd0020f1`
final account, `739ddb8e`). Section 4 checks those commits up to `739ddb8e` (06:07 UTC). This file supersedes the draft;
the registered `independent-review-2` record does not describe the final review (see §5, row 39).

Scope notes. `PC/iris-contract/` (`VALIDATED_ROUND` = r6 appeared at 05:04) and `PC/versions/` (`VERSIONS.md` appeared
later) were reviewed only through their registered runs in §5 (`env-ext-r6`, `ver-e262-d540-full`); I did not review
the contract extension's clauses or the version lane's conclusions in depth.

## Decision: **no sign-off**

The audit has now answered almost everything both reviews raised, and the answers check out against the logs:
F-C1304 to F-C1309 and F-C1203 are recorded with live evidence (F-C1306 and F-C1308 are S1). The matrix separates
verification status, product obligation and level, and labels the product as failing wherever as-built evidence says
so (216 `fails`). The corrected writer census is in the matrix as open obligations. The ontology cites the new
findings, and the proofs and TRUST name the premises the pin violates. The final `verify.sh --live` run reran 33
steps, and every step log matches its recorded hash.

Three things remain, all small, and one needs the operator:

1. **Scope record (R2-07).** The F-C1306 probe compiled a non-pin release (v4.5.1) and possibly a helper into `%SYS`,
   which the written conventions exclude. No operator ruling for this is on record. An agent cannot authorise it.
2. **Evidence records (R2-12).**
   - `corr-trace-conf` claims store-side contract steps that its log says were skipped.
   - `CORRESPONDENCE.md` overstates its controls and α coverage.
   - `independent-review-2` registers my unfinished draft, not this review.
3. **One over-correction (R2-11).** F-1201 was moved to `intent-undecided`, but ADR-0004 does settle it.

Once these three are fixed, I would sign off on spec against intent and on the account's accuracy (the first clause of
the §3.8 gate). The second clause ("every finding becomes a fix or a recorded decision") stays open until a
maintainer answers; an observation-only audit cannot close it. Exact conditions are in §6.

## 1. Responses to the first review, checked against the evidence (state `3d1095e3`)

| Item | Response | What I checked | Verdict |
|---|---|---|---|
| R-01(a) snapshot copies | F-C1304, S2, `fu-r01a-snapshot-copies` | `$RUN_DIR/followup/r01a.json`: `archive_token_totals` (pre-erase and after-erase archives hold the tenant; after-redaction none), `sc001_scan_after_restore` non-zero (`idem`, `rec 2 3`), `revision_row_after_restore` `[2, "fu1 onboarding note", "fu1\|corr-1", "fu1-idem-1"]`; archive modes 0600 under this process's umask | **addressed** |
| R-01(b) embedding_quarantine | F-C1305, S3, confirmed-source by design | `Eraser.cls:300-302, 756-758`; the run's log shows only the 3 upstream quarantine tests passing (§5 row 2) | **addressed** |
| R-01(c) legacy `Graph_KG.ledger_revisions` | F-C1306, S1, `fc1306-legacy-ledger-rows` (live) | `$RUN_DIR/fc1306/probe.json` `verdict`: `Graph_KG.ledger_revisions` hits for T (`"two nodes and a relationship"`, `"a property"`, `fc1306T-` x2), RAG copy cleared, `receipt_metadata_cleared` 4, `out_of_reach` names exports/journals/backups only | **addressed**; scope deviation R2-07 |
| R-02 writer census | corrected census, `followup-writer-census`: 269 sites, 46 undeclared writers, 162 obligations, 20 conditional, 3 write-set gaps | `$RUN_DIR/followup/writer-census.json` by file and mechanism | **tool addressed** (it now sees restore, `ImportGlobals`, `SetNodeJSON`, `Disable`/`SetStrict`, the SQL INSERT surface, `copy_ledger_history`, 20 `os-concat` LedgerApply sites, 86 translator sites); still unseen: `PropWrite.SetVal` (`PropWrite.cls:55`, re-types an unchanged value: harmless here), migration statement lists (`schema.py:1461-1495`), 15 unresolved sites |
| R-03 marker held open | F-C1307, S2, `fu-r03-marker-held-open` | `$RUN_DIR/followup/r03.json` `verdict`: 9 conditions true (bypass write accepted while marked, Final refused `target_live`, tenant B read refused, other redaction refused, ...) | **addressed** |
| R-04 temporal-only edges | F-C1308 S1, F-C1203 S1, `fu-r04-temporal-only-live-b` | `$RUN_DIR/followup/r04.json`: `G_content_rows_in_graph` all 0, `G_redact_unerased.complete` true with 1 tombstone, `G_window_after` still returns the edge (w 7.5), `P_window_after_redact` still returns fq5's edge, `G_verify_after` equal | **addressed**, confirmed |
| R-05 model results as product status | status/product/level split; findings gate open; `PROOFS.md:152` corrected; 11 statements `[model-only]` | `build_matrix.py`, `MATRIX.md`, ontology rows | partly at `3d1095e3` (R2-01, R2-03, R2-04); **addressed by `0eec4df8`** (§4) |
| R-06 proof premises | "Premises the pin violates" in `PROOFS.md`; `premises_refuted_at_pin` on proof-level cells | `PROOFS.md:240-254`; cells | **addressed for the account**; D-2 control and P-A3 then added as debt (§4) |
| R-07 closed-cell guard | closed needs a decisive registered run or is graded `inspected`; breadth-B registered from a decisive full run | builder; `$RUN_DIR/breadth-b/mc/full-decisive-20261114T012246Z.log` (sha matches the records' `full_log_sha256`, "132 of 132 met their expectation") | **addressed** |
| R-08 misstated descriptions | errata on `trace-conformance-ledger` (17) and `writer-census` (31 + 25 + 48) | records' git history; logs | **addressed**; now in `evidence/errata.json` with the first `registered_utc` kept |
| R-09 trace-conformance blind spots | correspondence lane: α contract-step check, line coverage, lock probes | `CORRESPONDENCE.md`, `tools/abstraction.py:440-505` | **partly** (R2-05, R2-12) |
| R-10 target digest | F-C1309, S3, `fu-r10-target-digest` | `r10.json`: 200,006 candidates, 0.133 s, `guessed_tenant_confirmed` true | **addressed** |
| R-11 assumed intent graded as defect | unchanged at `3d1095e3` (R2-08) | findings 04, 05, 12 | **addressed by `0eec4df8`**, with one over-correction (R2-11) |
| R-12 narrow model domains | disclosed debt (`PROOF-DEBT.md` D-9, D-10) | | accepted |
| R-13 incident reruns | `b-08-*-rerun`, `val-integration-1-c00-rerun` (identical outcomes) | registry; `SUITES.md` | **addressed** |

## 2. Findings of this pass (raised against `3d1095e3`; status after `739ddb8e` in §4)

- **R2-01 (S2): the product column under-reported failures.** `holds-in-model-only` needed `level == "model"`, but
  orchestrator cells said `"reviewed model"` and correspondence cells a free-text level. Product-scope cells never got
  findings (findings attached by module number). 08 and 15 / 3.3-model-check were `holds-in-model-only` while citing
  as-built expected violations. 11 and 04 proof cells were `holds-in-model-only` although their controls reproduce the
  pin.
- **R2-02 (S2): the corrected census was not in the matrix.** 3.3a-writesets still cited `writer-census` ("100 new
  obligations"); `followup-writer-census` was cited nowhere.
- **R2-03 (S3): the ontology predated the follow-up.** None of F-C1304..F-C1309, F-C1203 was cited. RED-B4 still
  carried an uncited `proved:theorem_retry_refused` (F-1801 contradicts it). The `[model-only]` rule fired only on
  cited findings, so it could not catch a missing citation.
- **R2-04 (S3): account inconsistencies.**
  - STATUS marked §3.1 "closed" while the matrix had 3.1-cells/coverage/intent at 10/19/18 open.
  - `5c-reviewers` was closed while its own `remaining` said the randomized simulator was not run.
  - `corr-closure-scan` ("all but one") disagreed with the census's ledger writers.
  - Validation's product defects were in no findings file.
  - TRUST omitted P-C02 for progress and the SynchCommit premise.
- **R2-05 (S3): the correspondence check is blind to F-C1308 and to completeness.**
  - α maps `create_temporal_edge` to no content and excludes temporal-marked rows (`CORRESPONDENCE.md` §2), so the
    "tombstone of live content" check (`abstraction.py:466-472`) cannot see a live temporal-only edge.
  - Nothing checks completeness at Final, so F-1305 / F-C1302-class outcomes pass.
  - The traces are sequential, apart from the F-1201 pair.
- **R2-06 (S3): premise gaps.** No progress-only control exists for D-2 (scan bound fixed at marking). The breadth
  proofs omit P-A3 (an eraser overlaps no writer of its graph) from the premises the pin violates, although F-1201
  (live) and F-C1202 show exactly that overlap.
- **R2-07 (S3, process): out-of-rule compile.** F-C1306's probe compiled v4.5.1's classes into IVG262FC1306 and
  possibly `IVGDev.Setup` into `%SYS` (`fc1306/RESULT.md` "Scope notes"; `SUITES.md` "Upstream side effects").
  `CONVENTIONS.md` allows scratch fixtures that compile the pin's unmodified classes only, and was not amended. No
  operator ruling for this exists. The evidence itself is sound.
- **R2-08 (S3): assumed intent still graded as defect.** F-0401, F-0503 and F-C1102 rested on an Assumption HD or on
  no source. F-C1102's own `intended` reads "No IVG document states a durability premise", yet it was
  `reproduced-live` S2.
- **R2-09 (S4): errata edited records in place.** They replaced `registered_utc`.
- **R2-10 (S3, adversarial): tenant copies still unrecorded.**
  - `^EmbedQueue(reqId, "text" | "node_id" | "result" | "graph")` is kept until `ClearDone`, which removes DONE
    entries only; ERROR and PENDING entries stay, and no erase path touches the queue (`EmbedQueue.cls:2-20, 181-195`).
  - `docs_quarantine` and `edge_vector_quarantine`.
  - The stale `^ArnoKG` snapshot, kept until `EraseAll` (`ArnoAccel.cls:299-303`).
  - The 3.2.0 rescue/unplaced edge tables (`schema.py:50-54, 2976-3013`).

New in the final pass:

- **R2-11 (S3, angle 1): F-1201 over-corrected.** `0eec4df8` moved F-1201 to `intent-undecided` ("spec 213's contracts
  state no statement-map completeness rule ... The remaining basis is HD-1201"). But ADR-0004 (Accepted) settles the
  defect itself, if not the remedy, in two places:
  - Consequences: "Every deletion path funnels through the Eraser's transaction, so a write path that touches one
    store without the others is a bug rather than a documented mode." In F-1201, EraseGraph kills the statement and
    tuple entries of an edge whose row it did not delete. `live-f1201-reproduced` and `verify-final-candidate`'s
    `f1201-live.log` show `"uv_edge_live": true, "uv_live_stmt": false` in 4 of 4 trials.
  - Context: leaving the ledger's indexes inconsistent "is what actually breaks".

  What stays undecided is the remedy (HD-1201: which lock), not whether this is a defect. F-1201 should be
  `reproduced-live` grounded in ADR-0004's Consequences, with the serialization remedy marked conditional on HD-1201.
- **R2-12 (S3, angle 5): correspondence evidence overstates its coverage.**
  - Of the five checked traces, only `ext` has per-operation row snapshots. `conf`, `f1201-1`, `f1201-2` and
    `lostack` record `"skipped": "trace has no per-operation row snapshots (ledger-side checks only)"`
    (`$RUN_DIR/correspondence/checks/trace-*.json`). So the store-side α steps (Store.Apply, EraseRows, the
    tombstone-of-live-content check) ran on one 32-operation trace.
  - `corr-trace-conf`'s `observes` says "every operation a step of the participant contracts (Ledger.Commit/Batch/
    Audit, Store.EraseRows+EraseIndex)", which its log contradicts.
  - `CORRESPONDENCE.md:23` says "10/10 negative controls rejected"; the self-test log rejects 9 and records the
    frame mutation as "not caught (expected: a frame property)".
  - No negative control exercises the tombstone-of-live-content check at all.

## 3. New material (state `3d1095e3`)

- **`STATUS.md`** is honest in its verdict ("not complete") and in keeping model and product apart. Its §3.1 line was
  wrong (R2-04, since fixed), and its S1 table matches the findings files.
- **`TRUST.md`, `PROOF-DEBT.md`**: the proof crates' trust inventories are empty and scanned. The premise gaps were
  R2-04 and R2-06, since fixed.
- **`correspondence/`**: the strongest code correspondence in the audit, and candid about it.
  - No handler is claimed as proved, and the unchecked lines are listed exactly: 281 of 1,760 ObjectScript and 181 of
    690 Python lines.
  - Lock plans were observed through `%SYS.LockQuery`. In 18 probes (16 + 1 + 1 in `lockplan.json`), production
    matches the source plans everywhere.
  - Its limits are R2-05 and R2-12. 3.6-keys and 3.6-fk are closed for 12-14 on sequential traces only; read them as
    "no violation observed", which the matrix's product label `unknown` correctly says.
- **`proofs-breadth/`** (modules 11 and 04): 94 verified, and 7 controls each located with a proved reachable
  counterexample. The recheck log carries its counts (`baseline: 94 verified, 0 errors`); the baseline log does not.
  Everything is model-level and labelled so.
- **Crash world** (`traces/crash_world.py`):
  - r1 is correctly kept `incomplete`. The 60,000-operation changeset was refused (`max_ops`); the refusal is now
    logged (`live-maxops-60000-refused`), and an erratum fixes r1's "no commit in flight" wording.
  - r2: the in-flight commit recovered all-or-nothing. The acknowledged commit (seq 3, 12,000 rows) was absent after
    restart with SynchCommit=0 (now evidenced: `env-synchcommit-setting`, `iris.cpf` line 325). The exactly-once retry
    held. There was one trial per world, and SynchCommit=1 was not tested.
  - No other registered run fell in the crash window (01:19:03-01:21:11).
- **`traces/lost_ack.py`**: the oracle is sound, except that a `verify` of `None` is accepted (`lost_ack.py:77`). The
  server-side-rollback branch was not observed, which is disclosed.
- **`traces/fc1303_resume.py`**: the world is deterministic (60 records ahead of acme, batch 1, scan cap 20), so 60
  calls stand for "never". The unbounded control completes in 14 batches.
- **`incidents/`**: USER-REDEPLOY-08 and HEALTH-ALERT-0119 are dispositioned with reruns.
- **`validation/`**: SC-002 (10,000 revisions, verify equal) and SC-003 have one decisive run each on Community, and I
  checked both logs.
  - SC-003: 100,000 records redacted in 1.42 s, longest batch 39 ms.
  - Committer side: the longest commit overlapping a redaction took 311.3 ms (n=77), then 55.0 ms and 57.0 ms.
  - Triage is rule-based, with reruns for every product-defect class; intermittent classes are kept as leads.

## 4. Commits made during this pass (`0eec4df8`, `fd0020f1`, `739ddb8e`), checked

| Draft condition | What changed | What I checked | Verdict |
|---|---|---|---|
| 1 product column (R2-01) | `fails` wherever as-built evidence violates the obligation, with a recorded basis; levels normalised; m07-m11 refs resolve; `--check` rejects an as-built violation beside a non-`fails` label | `obligations.json`: levels now `method` 144 / `model` 307 / `product` 296; product `fails` 216, `holds-in-model-only` 1, `intent-undecided` 3. 08 and 15 / 3.3-model-check, 3.3a-domain-contract, 3.3-progress-controls (F-C1303, F-C1307), 3.3-protocol, 11 / 3.3-L1 all `fails` with their basis; 09 cites `b-mc-m09-*`. `build_matrix.py --check`: "matrix current ... 0 problem(s)" | **met** |
| 2 census in the matrix (R2-02) | `matrix-input/writer-census-obligations.json`; closure scan reconciled | 13 / 3.3a-writesets cites `followup-writer-census` ("162 ... 20 conditional ... 3"); 18 shows the three restore write-set gaps as open `fails` cells; product 3.6-closure records the reconciliation (1 of 44 literal sites versus 8 census writers, 4 in common) | **met** |
| 3 ontology (R2-03) | 11 more citations; checker rule for uncited contradictions (`rr2-ontology-*`) | F-C1304..F-C1309 cited in `13-redaction.md`, F-C1203 in `12-erasure.md`; RED-B4 now `proved:theorem_retry_refused [model-only]; finding:F-1801`; RED-B7 cites F-C1309, RED-B12 F-C1306, RED-B1.1 F-C1308. Not opened: the new rule's control run | **met** (rule's control not checked by me) |
| 4 account consistency (R2-04, R2-09) | STATUS, 5c-reviewers, validation findings, TRUST, errata | STATUS §3.1 now **open** with the matrix's counts; `5c-reviewers` open; F-C1706, F-C0502, F-C1002, F-C0606 filed (`zz-validation.json`); TRUST adds P-C02 (progress), durability/SynchCommit, P-A3; erratum records keep their first `registered_utc`; `evidence/errata.json` holds later corrections | **met** |
| 5 classification (R2-08) | Assumption-only findings marked `intent-undecided` | F-0401, F-0503, F-C1102 `intent-undecided` (good); F-1201 too, which ADR-0004 does settle (R2-11) | **met, with one over-correction** |
| 6 scope ruling (R2-07) | none | `CONVENTIONS.md` unchanged; no ruling on record | **open (operator)** |
| 7 disclosed gaps (R2-05, R2-06, R2-10) | α limits stated; D-12 (D-2 control), D-13 (P-A3) added to `PROOF-DEBT.md`; 5 reach obligations | the 3.7-trace-replay cells state the α limits; `PROOF-DEBT.md` D-12, D-13; STATUS 3.1-coverage lists "5 reach obligations (review R2-10)" | **met** (as recorded limits, not checks) |
| 8 pending items | validation complete (`4cfb0374`), contract r6 validated, versions lane, final `verify.sh --live` | `verify-final-candidate`: 33 steps, all exit 0, 707 s, every step-log hash matches `summary.jsonl`; `f1201-live.log` "ERS-I3 violated in 4 of 4 trials"; `models-compare.log` all reruns reproduce; `registry.log` "750 registered runs; 0 problem(s)" (superseded logs reported as such) | **met** for what I checked |

## 5. Evidence audit (second pass: 39 runs registered since the first pass)

Method:
- I recomputed the SHA-256 of every registered log as of about 04:50 UTC: 711 records, of which 705 match and 6 do not.
  The 6 are the known, disclosed overwritten `core-proofs-*` originals.
- I read 39 runs registered after the first pass against their `observes`, prioritising the follow-up's S1 and S2
  reproductions, the correspondence and crash worlds, proofs, validation and the errata.
- A helper agent was started for this audit but returned nothing, so every row below is my own reading.
- MATCH means every factual claim is in the registered log, or in a file whose hash the record pins. PARTIAL means
  some claims are only elsewhere or absent. MISMATCH means the log contradicts a claim.

| # | Registry id | kind / result | SHA | Verdict | Note |
|---|---|---|---|---|---|
| 1 | fu-r01a-snapshot-copies | live / fail | ok | MATCH | token totals per archive, SC-001 scans, restored revision row, `receipt_names_snapshots` false |
| 2 | fu-r01b-quarantine-erase-plan | run / pass | ok | PARTIAL | log shows only "3 passed" of `test_227_erase_plan.py`; the source claims are not in it |
| 3 | fu-r03-marker-held-open | live / fail | ok | MATCH | 9 verdict conditions true |
| 4 | fu-r04-temporal-only-live-a | live / fail | ok | MATCH | `verify_equal_after` false, as its record says (control graph left live) |
| 5 | fu-r04-temporal-only-live-b | live / fail | ok | MATCH | read in full (see §1) |
| 6 | fu-r10-target-digest | check / fail | ok | MATCH | 200,006 candidates, 0.133 s, 1,506,817/s, `guessed_tenant_confirmed` |
| 7 | followup-writer-census | check / incomplete | ok | MATCH | 269/267/48/138/83/46/162/20/3/15 |
| 8 | fc1306-legacy-ledger-rows | live / fail | ok | MATCH | `verdict` hits in `Graph_KG.ledger_revisions`; RAG cleared; receipt |
| 9 | live-crash-world-r1-invalid | live / incomplete | ok | MISMATCH (erratum filed) | log `"commit_running_at_crash": true` versus "no commit was in flight"; the refusal is not in the log; corrected in `evidence/errata.json` with `live-maxops-60000-refused` |
| 10 | live-crash-world-r2 | live / fail | ok | PARTIAL (erratum filed) | ack seq 3, after crash head 2 / 0 rows, retry seq 3, `"acknowledged commit lost"`; SynchCommit=0 was not in the run's files (now `env-synchcommit-setting`) |
| 11 | trace-conformance-ledger (erratum) | trace / pass | ok | MATCH | 17 = 4 + 1 + 11 + 1 |
| 12 | writer-census (erratum) | check / incomplete | ok | MATCH | 31 + 25 = 56 covered, 48 outside |
| 13 | corr-trace-conf | trace / pass | ok | **MISMATCH** | claims Store.EraseRows+EraseIndex steps checked; log `abstraction.skipped`: "trace has no per-operation row snapshots (ledger-side checks only)" |
| 14 | corr-trace-f1201 | trace / fail | ok | PARTIAL | non-serializable pair and the ERS-I3 final note present; α store side skipped (ledger-side only) in both trials |
| 15 | corr-lockplan | live / pass | ok | MATCH | 16 + 1 + 1 probes |
| 16 | corr-capacity | live / fail | ok | PARTIAL | its `observes` names F-C1102 / F-C1103 / F-C1203, ids since reassigned to other findings (`correspondence/RENUMBERED.md`) |
| 17 | corr-line-coverage | check / pass | ok | MATCH | per-class counts in the log; per-handler totals in `coverage.json`, whose hash the record pins and I recomputed |
| 18 | corr-closure-scan | check / fail | ok | MATCH | "44 writer sites ... 1 not owned"; reconciled later on the 3.6-closure cell |
| 19 | corr-abstraction-selftest | control / pass | ok | MATCH | 9 REJECTED + frame "not caught (expected)"; `CORRESPONDENCE.md` says 10/10 (R2-12) |
| 20 | proofs-breadth-baseline | proof / pass | ok | PARTIAL | "94 verified, 0 errors" only in the unpinned `baseline.json` |
| 21 | proofs-breadth-recheck | proof / pass | ok | MATCH | "baseline: 94 verified, 0 errors", 7 controls REJECTED with counterexamples |
| 22 | proofs-breadth-fc1101-stats-whole-row | control / expected-violation | ok | MATCH | errors at `ledger_l2.rs:895`, `:925` |
| 23 | ontology-r05-check | check / pass | ok | PARTIAL | 61-byte log ("3877 statements, 0 violation(s) ... index current"); the tag counts are not in it |
| 24 | ontology-r05-check-before | check / fail | ok | MATCH | "14 violation(s) by rule: model-only=14" |
| 25 | val-perf-sc256-upstream-1 | run / pass | ok | MATCH | SC-002 and SC-003 lines verbatim |
| 26 | val-perf-committer-n1-1 | run / pass | ok | MATCH | `SC003-COMMITTER` lines: B-during max 311.3 / 55.0 / 57.0 ms, n 77/231/184, verify equal |
| 27 | val-e2e-1-c03 | run / fail | ok | MATCH | 1 failed, 30 passed, 399 skipped, 4 errors |
| 28 | val-tck-1 | run / fail | ok | MATCH | "3895 / 3896 eligible ... failed 1" |
| 29 | val-scratch-1 | run / pass | ok | MATCH | "90 passed, 7 skipped" |
| 30 | b-08-live-f0814-rerun | live / fail | ok | MATCH | `F-0814.verdict` reproduced, `execute_aql_has_read_only` false, AUDITB |
| 31 | b-10-live-scope2 | live / fail | ok | MATCH | F-1006 / F-1007 true with the stated vectors and degrees |
| 32 | b-mc-m07-bm25-as-built-I2 | mc / expected-violation | ok (+ full log) | MATCH | counterexample excerpt; full decisive log hash ok |
| 33 | b-mc-m09-planc-reviewed | mc / pass | ok | MATCH | "MET \| 2184 states ... exhaustive within bounds" |
| 34 | independent-review-1 | review / fail | ok | MATCH | identical to `review/REVIEW.md` |
| 35 | env-ext-r6 | check / pass | ok | MATCH | 516 cases, 0 outside, 515 singleton, 42 of 42 mutants killed |
| 36 | env-synchcommit-setting | check / pass | ok | MATCH | `325:SynchCommit=0` |
| 37 | live-maxops-60000-refused | probe / pass | ok | MATCH | "ChangesetTooLargeError changeset has 60000 operations; max_ops is 50000" |
| 38 | ver-e262-d540-full | check / fail | ok | MATCH | 515 cases, 1 outside, 41 mutants killed in all, 40 by in-contract cases |
| 39 | independent-review-2 | review / fail | ok | **MISMATCH** | the registered log is my unfinished draft (05:14, still holds a `PLACEHOLDER`); this file supersedes it |

**Result: 3 mismatches** (rows 9, 13, 39; row 9 already has an erratum), **6 partial**, 30 match. All 39 hashes
match. Across the whole registry, 705 of 711 hashes match; the 6 that do not are the disclosed superseded logs.

**Ratchet.** These items join the first pass's list and leave it only when fixed:
- RC-E7, observes claiming a check the log says was skipped (row 13).
- RC-E8, a draft registered as a review (row 39).
- RC-E1, claims supported only outside the registered log (rows 2, 14, 20, 23).
- RC-E9, ids reassigned under an unchanged record (row 16).

Rows 9 and 10 have left the list through `evidence/errata.json`.

## 6. Conditions for sign-off (exact)

1. **R2-07:** an operator ruling, from the user or operator and not an agent, on compiling a non-pin release (v4.5.1)
   and the `IVGDev.Setup` helper into `%SYS` through a pinned fixture. The alternative is to re-grade the evidence
   behind F-C1306 as outside the conventions. In both cases `CONVENTIONS.md` must say which rule applies.
2. **R2-12, RC-E7, RC-E8:** three evidence corrections.
   - An erratum for `corr-trace-conf`, and corrected statements in `CORRESPONDENCE.md`: α's store side was checked on
     the `ext` trace only, and the self-test rejects 9 of 9 α controls, with the frame control out of scope.
   - A negative control for the tombstone-of-live-content check, or a statement that it has none.
   - The final `review/REVIEW-2.md` registered under a new id, with `independent-review-2` marked superseded (a draft).
3. **R2-11:** F-1201 re-grounded in ADR-0004's Consequences clause and restored to `reproduced-live`, with only its
   remedy conditional on HD-1201. If the audit disagrees, it should record why that clause does not apply.

When these are done I will sign off on spec against intent and the account's accuracy (§3.8, first clause). The
second clause stays open for the maintainer's decisions in `decisions.md`, whatever I decide, and my sign-off would
cover the account, not the product.
