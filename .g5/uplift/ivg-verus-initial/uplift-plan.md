# Initial Verus uplift of iris-vector-graph — plan and state

This file owns the uplift's baseline, assignments, open obligations and the review-round counter.
Resume from the artifacts and raw logs listed here, not from an agent's final message.

## Baseline and permissions

| Item | Value |
|---|---|
| Product baseline | `3eaa79cf77d3e0a879b2cced634cf2729d81499e` (parent `fabf4fae`, the v4.7.0 release) |
| Worktree HEAD at start | `0e441f1c557b8d4c7d18eb54bfa98a95d77919a9` — differs from the baseline only under `.agents/` (44 files) and `experiment/` (4 files); `git diff --name-only 3eaa79cf HEAD -- . ':!.agents' ':!experiment'` is empty |
| Branch | `experiment/iris-vector-graph-g5-verus-20261113` |
| Scope | Backend behavior (Python package, ObjectScript classes, SQL, HTTP API). The browser UI under `iris_vector_graph/browser_static` is out of scope. |
| Product permission | Read-only. No product source, test, configuration, dependency or shipped-document change, even temporarily. Proposed fixes go to the findings register only. |
| Uplift write area | `.g5/` only. Raw logs and scratch output in `$RUN_DIR` (`~/runs/iris-vector-graph-g5-verus-20261113`). |
| IRIS instance for this arm | Container `ivg-g5-verus-20261113-iris`, `127.0.0.1:35972`, namespace `USER` (see `experiment/g5-verus/environment.sh`). Other containers on the host belong to other runs and must not be touched. |
| Verus | `$VERUS_BIN` = Verus `0.2026.10.04.426d8b0` (experiment environment). bank-of-ziniu pins `0.2026.09.27.3cf1832`; see [SOURCE.json](../../Verus_verification/SOURCE.json). |
| Start date | 2026-11-13 |

## Stage status

| Stage | Status | Artifacts |
|---|---|---|
| A. Intent recovery | complete: 13 ontology pages, 358 blocks (168 I, 127 D, 63 Q), `check_ontology.py` 0 issues; fresh-reader reconstruction check applied; round-3 reader corrections applied ([dispositions](review/round3-reader-repairs.md)). Ordering note: stage-B modeling of the ledger core started before the fresh-reader check because the request named that area first; its results fed back into the redaction/ledger/erasure pages. | [sources](sources.md), [intent notes](intent/), [operation inventory](intent/operations.md), [ontology root](../../ontology/root.g5.md) |
| B. Models and binding | complete: 5 models, 328 obligations, 128 controls all `EXPECTED_FAIL`; twin 51; 35 native probes / 40 observations on this arm's IRIS; upstream suites run against the baseline | [Verus verification](../../Verus_verification/runbook.md), [coverage map](../../Verus_verification/coverage.md) |
| C. Independent review | complete: round counter 3 of 3; every finding adjudicated; round-3 repairs validated by targeted re-check (no fourth round) | this file, section “Review rounds” |
| Handoff | complete: runbook, coverage map, findings register (`check_findings.py` clean), freshness gate FRESH, confinement check in the final report | [runbook](../../Verus_verification/runbook.md), [findings](../../Verus_verification/findings.md), [final report](final-report.md) |

## Assignments (stage A)

Each worker is read-only on the product and writes only its own file. No worker runs tests or touches IRIS; the orchestrator owns the single IRIS instance and runs native checks serially.

| Worker | Question | Output |
|---|---|---|
| A-history | Ledger, erasure, redaction, replay: requirements, decisions, history | `intent/ledger-history.md` |
| A-structure | Graph scope, graph keys, nodes and edges, parallel edges, adjacency, degree, version token | `intent/graph-structure.md` |
| A-temporal | Temporal edges, structural rows, opt-out, collisions, window reader, temporal purge | `intent/temporal.md` |
| A-search | Embeddings registry, vector width, quarantine, BM25 schema 2, text search, fusion | `intent/search.md` |
| A-cypher | Cypher translation, native executor, compiled plans, shadow mode, all-graphs semantics | `intent/cypher.md` |
| A-platform | IVG schema per namespace, install/upgrade/migrations, HTTP API/auth, FHIR, algorithms/Arno | `intent/platform.md` |
| A-ops | Independent operation inventory from entry points to writers, commits and readers | `intent/operations.md` |
| Orchestrator | Erasure/redaction/replay code reading, models, native checks, integration | ontology, `Verus_verification/` |

## Review rounds

Round counter: **3 of 3** (final round; at the cap no fourth round is started) (persist here; a resumed worker continues the count).

| Round | Started | Reviewers (fresh, isolated) | Output | Status |
|---|---|---|---|---|
| 1 | 2026-11-13 23:34 UTC | R1-core (ledger, erasure, redaction), R2-data (graph structure, temporal), R3-platform (install, access, Cypher, search, FHIR, algorithms + cross-domain) | [core](review/round1-core.md), [data](review/round1-data.md), [platform](review/round1-platform.md) | findings adjudicated; repairs in progress (see below) |

| 2 | 2026-11-14 03:4x UTC | R2-core (ledger/erasure/redaction + cross-domain; reproduces the runbook incl. one native result and its distinguishing control), R2-domains (structure, temporal, search, platform) | [core](review/round2-core.md), [domains](review/round2-domains.md) | adjudicated; repairs below |

Resumption note: the session was interrupted by an API rate limit (2026-11-14 ~01:30–03:20 UTC) while four modelers were writing coverage rows. On resumption the artifacts and raw logs were inspected (final native battery complete, 37 hash-stamped observations; cited tests complete), the modelers were resumed from their saved state, and the round counter was continued, not reset.
| 3 | 2026-11-14 04:2x UTC | R3-validation (round-2 repairs + final coverage/fidelity pass, all domains), R3-reader (ontology read as a rebuilder; lost conditions vs the pre-round-2 snapshot and stage-A notes) | [validation](review/round3-validation.md), [reader](review/round3-reader.md), [reader dispositions](review/round3-reader-repairs.md) | adjudicated; repaired in uplift artifacts and validated by re-running proofs, controls, twin, probe, checkers and the freshness gate (no fourth round) |

### Round 3 adjudication

Final round (3 of 3). Repairs were applied to uplift artifacts only and validated by a targeted re-check, not a fourth review round: core model re-proved (41 verified; [receipt](../../Verus_verification/results/ledger_redaction/20261114T042922Z-prove/receipt.json)), all 16 core controls `EXPECTED_FAIL` (`20261114T043*-control-*`), twin rebuilt (51 verified); re-run at this arm's 4-thread setting with the same verdicts ([prove](../../Verus_verification/results/ledger_redaction/20261114T044401Z-prove/receipt.json), controls `20261114T0444*`–`0446*`; R3-validation had noted the earlier receipts used 6 threads), native probe `redaction_orphan_prop_blocks` run on this arm's IRIS, `check_ontology.py` and `check_findings.py` clean, `tools/check_evidence.py` FRESH.

| Finding | Category | Disposition | Owner |
|---|---|---|---|
| validation R3-1 ontology contract still wrong after round 2 (temporal Q premise, resume "proved", final re-check, competing targets, erasure concurrency) | incorrect intent; stale evidence | accepted: bodies and metadata of `redaction.after-erasure.temporal`, `redaction.batches.resume`/`.abort`/`.competing`, `erasure.concurrency`, `erasure.atomic.caller-transaction` corrected (also R3-reader H2, L1) | orchestrator (done), ontology fork |
| validation R3-2 final report / runbook overclaim and stale counts | stale evidence | accepted: resume moved to Observed; counts regenerated (328 obligations, 128 controls, 35 probes / 40 observations, core 41 / 16 / twin 51); bug-led-007 added to the seed rows; runbook marks the knowledge lemmas as classification facts | orchestrator (done) |
| validation R3-3 bug-led-007 consequence overclaimed; simp-003 precondition | correspondence error | accepted: consequence corrected (explicit-id erase or temporal delete removes them); simp-003 depends on the erase repair, with the two distinguishing native cases | orchestrator (done) |
| validation R3-4 `NodeRow` hides orphan property rows | model error + product defect | accepted: `Item::PropRow` with product-faithful `erased_in`, witness W6, control `prefix-erase-takes-orphan-props`; native probe OBSERVED_DEFECT; new [bug-led-010](../../Verus_verification/bugs_issues.md#bug-led-010) (Low, observed); bug-led-009 consequence corrected | orchestrator (done) |
| validation R3-5 omitted core clauses; graph-blind erase undetected | missing intent (coverage) | accepted: frame lemmas `lemma_erase_stays_in_target_graph`/`lemma_erase_keeps_other_graphs` + control `graph-blind-erase`; coverage rows for immutability, commit, lifecycle/readers/verify scope, erasure scope/count/history/kept, redaction audit/receipt/refusals/out-of-reach; Cypher native/shadow listed as Observed (upstream), not modelled | orchestrator (done) |
| validation R3-6 stale "not run" texts in the temporal coverage section | stale evidence | accepted: superseded rows struck and pointed at their round-2 rows; both statements corrected from the logs | orchestrator (done) |
| validation R3-7 bug-srch-016 repair incomplete | missing intent (repair) | accepted: both changes required, with `theorem_repair_delete_takes_effect` under `locked_build()` | orchestrator (done) |
| validation R3-8 bug-str-016 classification; bug-tmp-011/013 links; status word | register defect | accepted: bug-str-016 moved to the bugs as Suspected Low with Expected/Observed; temporal entries relinked to `20261114T040433Z-prove` and RACE-4/5 plus the repair witnesses; row status "Observed violation (native only)" | orchestrator (done), ontology fork (metadata) |
| reader H1–H4, M1–M25, L1–L11 | incorrect intent, lost conditions, stale evidence, provenance, links | see [round3-reader-repairs.md](review/round3-reader-repairs.md) for each disposition. Register side done by the orchestrator: [bug-plt-026](../../Verus_verification/bugs_issues.md#bug-plt-026) (H3, suspected), [bug-led-011](../../Verus_verification/bugs_issues.md#bug-led-011) (M4, suspected), [q-plt-018](../../Verus_verification/open_questions.md#q-plt-018) and [q-srch-006](../../Verus_verification/open_questions.md#q-srch-006) (M22), [q-plt-019](../../Verus_verification/open_questions.md#q-plt-019) (M14), [bug-srch-017](../../Verus_verification/bugs_issues.md#bug-srch-017) (M25), [bug-plt-027](../../Verus_verification/bugs_issues.md#bug-plt-027) (M6), [bug-str-017](../../Verus_verification/bugs_issues.md#bug-str-017) (M10), q-plt-002 narrowed (H3), "Open statement" links for q-led-003, q-tmp-006, q-plt-006 moved to the new Q blocks; M17 is already [bug-tmp-006](../../Verus_verification/bugs_issues.md#bug-tmp-006) and the `bulk_delete_nodes` reporting gap is in bug-led-011; "Open statement" links for q-001…q-010 (M22); bug-led-007 lowered from High to Medium (H2: spec 256 deferred the shared-graph case) | ontology fork, orchestrator |

### Round 2 adjudication

Both reviewers assessed coverage and fidelity on the integrated artifacts; R2-core reproduced the runbook (proof 37, 13/13 controls, twin bit-identical, binding probe as expected, distinguishing product control `OBSERVED_DEFECT` incl. a commit admitted mid-run). Accepted unless noted.

| Finding | Category | Disposition | Owner |
|---|---|---|---|
| core R2-1 prefix erase misses temporal-only events | product defect + model correspondence | accepted: native probe `erasure_prefix_temporal_only` OBSERVED_DEFECT; model `erased_in` made product-faithful, witness W5, control `prefix-erase-reaches-temporal` (38 verified, 14/14) | orchestrator (done), register |
| core R2-2 R1-1 repair not real (knowledge lemmas standalone) | model error / overclaim | accepted: lemmas re-documented as classification facts; resume across calls re-tagged Observed only in coverage; "model per-call knowledge as state" left as next action | orchestrator (done) |
| core R2-3 strict-mode deletes leave non-ledger stores | product defect (suspected) | accepted | register |
| core R2-4 post-commit properties bypass strict mode and the commit block | product defect (Low) | accepted | register |
| core R2-5 stale claim about the final re-check | stale evidence | accepted: observed in the final concurrent run | orchestrator, register |
| core R2-6 runbook commands write into `.g5/` | runbook defect | accepted: scratch-copy procedure documented | orchestrator (done) |
| core R2-7 receipts hash no product files | evidence limit | accepted as a stated limit (product binding = baseline commit + confinement check); twin receipt carries the binary hash | orchestrator (done) |
| domains R2-1 BM25 Delete during Build lost | product defect (suspected) + repair gap | accepted | search modeler, register |
| domains R2-2 purge decide not product-faithful | model correspondence | accepted | temporal modeler, register |
| domains R2-3 coverage/NOTES contradict run logs | stale evidence | accepted: 8 coverage statements corrected; NOTES by modeler | orchestrator (done), temporal modeler |
| domains R2-4 zero counter treated as absent | model weakness | accepted | temporal modeler |
| domains R2-5 token not moved by a non-indexed temporal reweight | intent divergence (code reading) | accepted: observed divergence in `structure.rebuilt.token` | orchestrator (done), register |
| domains R2-6 missing back-link; unexplained severity raise | register defect | accepted | register |

### Round 1 adjudication

Both coverage and fidelity were assessed by every reviewer. Accepted unless noted.

| Finding | Category | Disposition | Repair owner |
|---|---|---|---|
| core R1-1 `K()` constant hides per-call knowledge | model error | accepted: knowledge-as-state section, `lemma_serial_resume_keeps_attribution`, `witness_race_then_resume_loses_attribution`; resume claim made conditional on serialisation | orchestrator (done, 37 verified) |
| core R1-2 prefix resume never observed | missing evidence | accepted: probe `redaction_prefix_resume` → OBSERVED_AS_EXPECTED | orchestrator (done) |
| core R1-3 stale control receipts | stale evidence | accepted: all 13 controls re-run on the final model into `results/` | orchestrator (done) |
| core R1-4 erasure atomicity cited without a passing test | stale evidence | accepted: scratch-namespace suites blocked by the Community connection license; claim re-tagged Assumed | orchestrator (coverage) |
| core R1-5 coverage status words | correspondence | accepted | orchestrator (coverage) |
| core R1-6 register gaps | missing intent | accepted | register worker |
| core R1-7 bug-003 consequence and severity | incorrect claim | accepted: consequence corrected; severity High → Medium (narrow, operator-initiated trigger) | register worker |
| core R1-8 model Erase graph-blind | correspondence | accepted: product-faithful `erased()`; W3 now derived through `Erase` | orchestrator (done) |
| core R1-9 completion only for started runs | model scope | accepted: condition stated in coverage; extra controls A1/B1 added (both EXPECTED_FAIL) | orchestrator (done) |
| core R1-10 interrupt probe step 4 refused at entry; missing receipt copy; no probe hashes | stale evidence | accepted: wording fixed; receipts copied; harness now records probe hashes; final probe battery re-run on the final candidate | orchestrator |
| core R1-11 reifier cascade records unreachable; DropStatements unmodeled | missing intent | accepted (suspected); exclusions stated | ledger page owner, register |
| core R1-12 bug-002 "found by model" | incorrect claim | accepted | register worker |
| data R1-1 / platform R1-1 register and coverage missing domains | missing evidence | accepted (register consolidation was in progress) | register worker, orchestrator |
| data R1-2..R1-5, R1-9 product defects | product defect | accepted with native evidence; R1-5 new | register worker |
| data R1-7 temporal model lacks ADR-0009 main rule and the write-vs-purge race | model coverage | accepted | temporal modeler |
| data R1-8/R1-10 degree ABA via erase killing the generation | model coverage | accepted | structure modeler |
| data R1-11 cited live tests not run | missing evidence | accepted: every ontology-cited e2e/integration file run per file against the baseline | orchestrator (running) |
| platform R1-2 BM25 failure rolls back the caller's transaction | product defect | accepted (observed) | register, search page owner |
| platform R1-3 CRC-32 plan names forgeable | product defect (suspected, security) | accepted | platform modeler, Cypher page owner, register |
| platform R1-4/R1-5 setup race decided by FR-005/006; waiver over another schema | incorrect classification | accepted: bugs, not questions (no-record case stays open) | platform modeler, install page owner, register |
| platform R1-6/R1-7 BM25 erasure decided by CONTEXT/ADR-0004/0013 | incorrect classification | accepted: bug, not question | search page owner, register |
| platform R1-8 hand-assembled Drop witness | model error | accepted | search modeler |
| platform R1-10 stale Cypher observation | stale evidence | accepted: re-run after the probe fix → refused with SQLCODE -12, nothing written | orchestrator (done) |
| platform R1-11 strict-mode bypass classification | incorrect classification | accepted | platform modeler, access page owner, register |

## Open obligations

Carried to the next uplift (see the [final report](final-report.md#6-coverage-gaps-and-incomplete-work)): model per-call statement knowledge as state; run the erasure failure-injection suites on a licensed instance; natively reproduce the suspected High entries (bug-plt-001, bug-cyp-001); human decisions on the open questions.

## Incidents

| When (UTC) | What | Action |
|---|---|---|
| 2026-11-13 22:50 | Running the upstream unit suite created `.sesskey` (36 bytes, a web session key written to the working directory by a test; ignored by the product's `.gitignore`). | Its SHA-256 and timestamp were kept in `$RUN_DIR/incidents/sesskey.sha256` (content not copied: it is a secret), and the file was removed before handoff. |
| 2026-11-13 22:26 | An untracked 26-byte file `iris_src/src/Graph/KG/tTxnLevel` (content `215 While { TROLLBACK 1 }`, matching `TemporalPolicy.cls:215`) appeared in the product tree during stage A. It is consistent with an unquoted `>` in a stage-A worker's grep pattern. Workers A-platform and A-temporal reported it; neither claims it. | Copied to `$RUN_DIR/incidents/tTxnLevel.stray` with its SHA-256, removed from the worktree at 22:4x, and all workers told to quote `>`/`<` patterns. Tracked product files were never modified (`git diff` empty). The final confinement check covers untracked files too. |
