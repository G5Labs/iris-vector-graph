# Round 3 review — R3-validation (round-2 repairs, final coverage and fidelity pass, all domains)

Reviewer: R3-validation (fresh, isolated). Round 3 of 3, the final round. Date 2026-11-14. Product baseline `3eaa79cf`; worktree HEAD `0e441f1c`.
Scratch and raw logs: `$RUN_DIR/agents/R3-validation/` (`$RUN_DIR` = `~/runs/iris-vector-graph-g5-verus-20261113`), written `$SCR` below.
The product was not touched. Nothing under `.g5/` was edited except this file. No IRIS, docker, probe or test was run. I read raw native observations under `$RUN_DIR/native/` and test logs under `$RUN_DIR/tests/`.

Order of work. The task names the round-2 repairs, so I read the plan's round-2 adjudication table first. Before reading the ontology, models, coverage map or register, I read the governing sources and code entry points:

- ADR-0004, 0007, 0009, 0012, 0013 and 0015; CONTEXT.md in full;
- `Eraser.cls` (`EraseNodes`, `EraseNodeIds`, `EraseIdSet`, `EraseEdges`);
- `TemporalIndex.cls` (`EraseNodes`, `RemoveTemporalRow`, `RebuildBucketAggregate`);
- `BM25Index.cls` (`Build`, `Delete`, `Drop`);
- `schema.py` DDL for `nodes`, `rdf_labels`, `rdf_props`;
- `client.py` `_apply_post_commit_properties`;
- `iris_sql_store.delete_nodes` and `nodes_edges.delete_node`.

So the expectations below are independent of the uplift's artifacts, but not blind to the round-2 topics.

## Independent expectations

**Erasure (ADR-0004, CONTEXT "Erasure")**

- X1. An erase removes the target's content from every store, the temporal index included. It is atomic, and it leaves another graph's content untouched. Both default-graph spellings are erased; an invalid name is refused first; a returned 0 means nothing matched.
- X2. `EraseNodes(g, prefix)` selects ids **from `Graph_KG.nodes` only** (Eraser.cls:331-349). `EraseNodeIds(g, ids)` puts **every named id** into the erase set, present or not. "The ^KG sweep runs for every id named, present or not" (:352-389), and `EraseIdSet` deletes `rdf_props`/`rdf_labels`/`docs`/vectors per id and calls `TemporalIndex.EraseNodes` for the whole set.
- X3. `TemporalIndex.EraseNodes` removes every `tout` edge whose source **or** target is in the set (:421). So a prefix erase reaches a temporal-only event only through an endpoint that has a node row in that graph. An explicit-id erase reaches it whether or not a node row exists.
- X4. `rdf_props` has **no foreign key** to `nodes` (schema.py:411-418), unlike `rdf_labels` and `rdf_edges`. `post_commit_properties` INSERTs `rdf_props` rows for any id by direct SQL (client.py:466-473). So an id can have property rows and no node row. Such rows are invisible to `EraseNodes(prefix)`, but `LiveRows` reads them.

**Redaction (ADR-0013, spec 256)**

- X5. Redaction is refused while the target is live. Liveness reads `nodes`, `rdf_labels`, `rdf_props` and `rdf_edges`, not the temporal index.
- X6. The run's lifecycle:
  - Batches run under the head lock; the marker is set at the first tombstone.
  - Final re-checks liveness and kills the marker.
  - Resume rebuilds per-call knowledge: PrePass, the `("redacting","stmt")` set and the live statement map.
  - Whether attribution survives a pause is a lifecycle property, not a one-call classification fact.
- X7. Immutability has one exception: `RejectUpdate` with four conditions. It is a security-relevant rule and must be covered or listed as a gap.

**Temporal (ADR-0009 amendment, ADR-0015)**

- X8. The purge decides survivorship with one walk. `^||IVG.TPurge` holds every structural candidate without survivors, row or not, and the marker is tested only at the DELETE.
- X9. A zero bucket counter is not neutral (TemporalIndex.cls:355-358). The aggregate node is killed at 0 (:477-480). So "exact statistics" must require absent, not 0.

**BM25 (ADR-0007)**

- X10. Every write runs under the index lock in a transaction. `Delete` tests `cfg N` **before** the lock (:498). `Build` kills, scans and publishes N last (:99, :160), without a lock. So a delete during a Build answers False and can be undone by the Build's publish.
- X11. A repair must put both Build under the lock **and** Delete's N test under the lock. Either change alone leaves the lost delete.

**Query execution (CONTEXT)**

- X12. The native executor answers exactly as the SQL path does. Shadow mode raises on a difference. These are core obligations, and the coverage map should state their status.

## Validation of the round-2 repairs

`python3 .g5/Verus_verification/tools/check_evidence.py` (repository root) reports:

- **FRESH**, exit 0;
- ledger_redaction 38 / 14 controls, graph_structure 67 / 22, platform 51 / 30, search 56 / 27, temporal 113 / 33;
- 39 native observations.

Raw output: `$SCR/check_evidence.out`.

I re-proved byte-identical copies (same SHA-256 as the current files) at 4 threads:

| Model | Result | Log |
|---|---|---|
| ledger_redaction | 38 verified, 0 errors | `$SCR/logs/base-ledger_redaction.log` |
| search | 56 verified, 0 errors | `$SCR/logs/base-search.log` |
| temporal | 113 verified, 0 errors | `$SCR/logs/base-temporal.log` |

I re-applied two new controls from `model.json` to scratch copies. Both fail exactly where `expect_fail_in` says:

- `prefix-erase-reaches-temporal`: 37 verified, 1 error, at `redaction.rs:1647` inside W5. Log: `$SCR/controls/prefix-erase-reaches-temporal/verus.log`.
- `repair-delete-checks-n-first`: 54 verified, 2 errors, at :1078 in `theorem_repair_delete_takes_effect` and :1255 in `witness_repair_delete_after_build`. Log: `$SCR/controls/repair-delete-checks-n-first/verus.log`.

Native copies `erasure_prefix_temporal_only.json` and `search_bm25_delete_during_build.json` are byte-identical (`cmp`) to `$RUN_DIR/native/…-20261114T034853Z.json` and `…-20261114T041018Z.json`.

The twin was rebuilt (47 → 48, because `redaction.rs` gained an obligation). Its binary SHA-256 `823bfbfb…a452` is unchanged and equals the binary the binding probe used, so the binding observation still applies.

| Round-2 item | Claimed repair | Real? | Sufficient? | Fresh? |
|---|---|---|---|---|
| core R2-1 prefix erase misses temporal-only events | `erased_in` product-faithful; W5; control `prefix-erase-reaches-temporal`; probe `erasure_prefix_temporal_only`; bug-led-007 | **Real.** `erased_in` matches `EraseNodes` + `TemporalIndex.EraseNodes`: either endpoint with the prefix **and** a node row in the same graph. W5 holds. The control makes W5 fail. The probe has a distinguishing pair: `tE|1` with a node row is erased, `tE|x` without one survives. | **Partly.** The model and evidence are right. The ontology Q still offers "rely on erasure, which removes them anyway" (R3-1). bug-led-007's "no erase short of erasing the whole shared graph" is false (R3-3). simp-003 was not qualified (R3-3). The same over-approximation remains for `rdf_props` rows without a node row (R3-4). W5 stops at the tombstone step, not completion; its description says so, and my L-c / R2-core d2 cover completion. | yes |
| core R2-2 resume re-tag | coverage row "Observed only"; lemmas described as classification facts; trust inventory | **Real in coverage.md and the model's doc comments** | **No.** `redaction.g5.md#redaction.batches.resume` metadata still says "resume of a prefix target is proved … (`lemma_serial_resume_keeps_attribution`)" and cites the superseded receipt `20261113T235716Z`. final-report §3 says "Proved: … batch composition and resume (serialised redactions)". The runbook lists the lemma among key results without the qualifier (R3-1, R3-2). | n/a |
| core R2-3 strict-mode ledger delete | bug-led-008 (Low, Suspected) | Real (register, single-path findings link) | Partly. The Q `redaction.strict-mode` body still describes only the refused erase methods. | n/a |
| core R2-4 post-commit properties | bug-led-009 (Low, Suspected) | Real | Its consequence is wrong for prefix targets (R3-4). `ledger.commit.admission` does not link it. | n/a |
| core R2-5 Final's re-check observed | coverage "completion" row cites `redaction_concurrent_targets` | Real in coverage. The raw observation does contain A's `RedactionTargetLiveError … became live again`. | **No.** `redaction.g5.md#redaction.batches.abort` metadata still says it "has not been observed natively" (R3-1). | yes |
| core R2-6 runbook | scratch-copy procedure; 38/14/48 | Real | Step 6 still does not say the probe leaves A's marker behind (minor). | yes |
| core R2-7 receipt limits | stated in the runbook | Real (stated limit) | yes, as a stated limit | yes |
| domains R2-1 lost BM25 delete | `gone_ok`; witnesses W-O1e and round-1-repair; `theorem_repair_delete_takes_effect` under `locked_build()`; 2 controls; probe; bug-srch-016 | **Real.** The theorem is inductive over all `wstep` actions. My faulty control S-b is detected. The valid outcome S-c survives. | Model yes. bug-srch-016's repair text alone ("test N under the lock in Delete") is insufficient; S-a still loses the delete (R3-7). | yes |
| domains R2-2 purge decide | `doomed_set` = all candidates without survivors; `lemma_doomed_set_iff`; RACE-4 from the reachable `s_rowless` (a derived trace: opt out, write, opt in); recheck-repair witnesses; controls `decide-rows-only`, `retract-no-recheck`, `kill-no-reretract` | **Real** | Model yes. The register entries bug-tmp-011/013 still cite the superseded receipt and the reviewer's scratch witness, not the integrated RACE-4/RACE-5 witnesses (R3-8). | yes |
| domains R2-3 stale "not run" texts | "8 coverage statements corrected"; temporal NOTES refreshed | Real for the Round-2 rows and NOTES | **No.** Contradictory statements remain in non-superseded rows and gap lists (R3-6). | n/a |
| domains R2-4 zero vs absent | `exact` now requires presence ⇔ raw edges for bucket and tagg; control `zero-counter-kept` fails `lemma_delete_exact` | **Real.** It now matches the product's Kill-at-zero for both bucket (:358) and tagg (:477-480), and an obligation catches it, not just a witness. | yes | yes |
| domains R2-5 token not moved by `PutShadow` | `structure.rebuilt.token` divergence; bug-str-016 | Real | Classification and consequence are inconsistent (R3-8). | n/a |
| domains R2-6 back-link, severity reason | bug-tmp-012 linked from `temporal.structural.end`; bug-str-002 reason recorded | Real | yes | n/a |

## Coverage findings

- **R3-5 Important in-scope clauses appear neither as rows nor in any gap list of the coverage map.** Category: missing intent (coverage record). I compared every ontology anchor with `coverage.md`: about 90 anchors are absent, and I discounted wildcard and short-form gap entries.
  - **Material omissions in the core domain:**
    - [ledger.immutability](../../../ontology/features/ledger.g5.md#ledger.immutability) and [redaction.metadata.exception](../../../ontology/features/redaction.g5.md#redaction.metadata.exception). This is the only exception to immutability, ADR-0013's four-condition `RejectUpdate` rule. It is security-relevant, and upstream tests exist: `test_ledger_us01_commit_head::test_revisions_are_immutable_via_sql` and `test_256…::test_outside_the_redaction_a_redacted_revision_is_still_immutable`.
    - `ledger.commit.serial`, `ledger.commit.caller-transaction`, `ledger.commit.expected-head`, `ledger.commit.size`, `ledger.lifecycle` (+ `genesis`), `ledger.readers` and `ledger.verify.scope`.
    - `erasure.scope`'s own frame: another graph never touched, both default-graph spellings, invalid name refused first. Also `erasure.count`, `erasure.kept` and `erasure.history`.
    - `redaction.audit`, `redaction.receipt`, `redaction.refusals` and `redaction.out-of-reach`.
  - **Cypher:** `query.native.*` and `query.shadow*`, the CONTEXT core concepts "Native executor" and "Shadow mode". The platform gap list names compiled plans, graph scope and writes, but not the executor's equal-answers obligation. test_253_* passed upstream (8, 4 and 43).
  - My adversarial L-b shows that a graph-blind `Erase` (removing another graph's edge rows and temporal events) is undetected by every ledger-model obligation (38 verified). So `erasure.scope`'s "another graph's content is never touched" rests on upstream `test_erase_graph` only, and the map should say so.
- **R3-4 (coverage side)** Orphan property rows (X4) are a second store blind spot in the prefix recipe. They are not in the model, the map or the register. See Fidelity.
- **Gap-list honesty elsewhere.** The structure, temporal, search and platform gap lists match what I found unmodelled, apart from the omissions above. The temporal list's "test_255_* was not run" is wrong (R3-6).

## Fidelity findings

- **R3-4 `NodeRow` conflates node, label and property rows, so the model's prefix erase over-approximates the product for an `rdf_props` row whose id has no node row.** Category: model error (abstraction); product defect (suspected, code reading).
  - **Mechanism:**
    - `rdf_props` has no FK (schema.py:411-418), and `post_commit_properties` INSERTs props for any id (client.py:466-473).
    - `EraseNodes(prefix)` selects ids from `Graph_KG.nodes` only (Eraser.cls:331-349).
    - So such a row survives the documented `delete_nodes_by_prefix`.
    - `LiveRows` reads `rdf_props`, graph-blind for a default-graph prefix target. Every later `redact(None, prefix=…)` is refused `target_live`, and erasing by prefix again changes nothing.
  - **Model:** `erased(NodeRow)` removes it, so `witness_erase_then_redact_completes` holds in the model while the product refuses.
  - **Scratch L-d:** a `PropOnly` item with product-faithful `erased`/`checked`. All 38 original obligations still verify, and `r3_witness_orphan_prop_blocks_redaction_after_prefix_erase` verifies (39 verified, 0 errors): Erase → Start refused → Erase again → Start refused.
  - **Consequence for the register:** bug-led-009 says a mid-run post-commit property leaves the marker "until the target is erased again". For a prefix target, an erase by prefix cannot clear it. Only `delete_nodes([ids])` (EraseNodeIds) or raw SQL can. Until then the namespace-wide marker blocks readers, verify and other targets.
  - The failure is loud (refusal), not silent, so Low.
- **R3-3 bug-led-007's consequence overstates the impossibility of cleanup.** Category: correspondence error (register claim).
  - "No erase short of erasing the whole shared graph removes them" is false. `store.delete_nodes(ids, graph=…)` / `delete_node(id, graph=…)` → `EraseNodeIds` erases events incident on any named id with or without a node row (X2, X3), and `delete_temporal_edge` removes single events.
  - The defect stands: the documented prefix recipe misses them, and the IDs must be known. But the "permanently unredactable" reasoning carried into simp-003 is wrong.
  - simp-003's "behavior to preserve: a target whose content was erased is not refused" is unqualified. Under the as-built `EraseNodes` it turns bug-led-007 into a refusal after every prefix erase (and the same for R3-4's rows). simp-003 needs bug-led-007's erase repair as a precondition, and `erasure_prefix_temporal_only` as a distinguishing case.
- **Checked and faithful:**
  - `erased_in` vs `Eraser.EraseNodes` + `TemporalIndex.EraseNodes` (graph test, either endpoint, node row in the same graph, ids collected before the erase);
  - `DelBegin`'s no-N early return vs `BM25Index.Delete:498`;
  - `doomed_set` vs `RetireExpired` `^||IVG.TPurge`;
  - `rebuild` killing tagg at 0 vs :477-480;
  - `remove_raw` Kill at ≤ 0 vs :357-358;
  - `s_rowless` is a derived trace (`SetStructural` off → `Write` → on), not a hand-built state.
- **Witness reachability.** The native observation matches each new as-built witness:
  - W5 ↔ `erasure_prefix_temporal_only` (tE|x survives; tE|1 removed);
  - W-O1e ↔ `search_bm25_delete_during_build` (two deletes inside the 0.71 s window answered False, and both documents are returned afterwards).

## Adversarial checks

Each check edits a scratch copy of the current model (SHA-256 identical before the edit). Command in each directory: `$VERUS_BIN <file>.rs --crate-type=lib --num-threads 4 --triggers-mode silent` (Verus 0.2026.10.04.426d8b0). Log: `$SCR/adv/<name>/verus.log`. No run hit a timeout or resource limit.

| Kind | Model / name | What I changed | Verdict | Meaning |
|---|---|---|---|---|
| (a) false premise | ledger_redaction / `L_a_prefix_erase_clears_temporal` | Added `r3_false_premise_prefix_erase_clears_temporal_only`: for every state and prefix target, after `Erase` no live `TemporalOnly` item is target content (the ontology Q's "rely on erasure, which removes them anyway") | 38 verified, **1 error** (postcondition not satisfied) | **Rejected.** The repaired model no longer hides R2-1 (round-2 d1 showed the old model accepted it). |
| (b) faulty implementation | ledger_redaction / `L_b_erase_graph_blind` | `erased_in`/`erased`: `EdgeRow` and the prefix `TemporalOnly` clause without `g == t.g`, so an erase removes another graph's edges and events | **38 verified, 0 errors (survives)** | Not detected. No ledger-model obligation constrains `Erase` beyond W3/W5, so `erasure.scope`'s graph frame is not formally supported (R3-5). |
| (c) valid outcome | ledger_redaction / `L_c_recipe_clean_with_node_row` | Added `r3_valid_prefix_erase_with_node_row_then_redact_is_clean`: the event's endpoint has a node row (the native `tE|1` case). Erase removes row and event, then Start → Step → Final completes with `!any_content` | 39 verified, 0 errors | The product-faithful erase still allows the legitimate clean completion. |
| (a) premise / model fidelity | ledger_redaction / `L_d_orphan_props` | Added `Item::PropOnly` (rdf_props row with no node row) with product-faithful `content`/`erased`/`checked`, plus witness `r3_witness_orphan_prop_blocks_redaction_after_prefix_erase` | 39 verified, 0 errors | Every original obligation holds and the refusal-forever trace exists (R3-4). |
| (a) erroneously permitted repair | search / `S_a_delete_lock_only` | New variant `{build_locked: false, delete_under_lock: true}` (bug-srch-016's repair text alone) and witness `r3_witness_delete_lock_only_still_loses_delete` | 57 verified, 0 errors (witness holds: deleted doc published, `!gone_ok`) | The register's repair proposal alone does not close the lost delete; it needs bug-srch-003's locked Build too (R3-7). |
| (b) faulty implementation | search / `S_b_build_releases_lock_in_scan` | The full repair with a Build that releases the lock during its scan: `DelBegin` waits only for `s.run` | 54 verified, **2 errors**: `theorem_repair_delete_takes_effect` (:1078), `witness_repair_delete_after_build` (:1255) | **Detected.** |
| (c) valid outcome | search / `S_c_rebuild_after_delete` | Added `r3_valid_rebuild_after_completed_delete` under `locked_build()`: Insert d1, Delete d1 (commits), then a later Build scans d1 (node still exists) and republishes it; `gone_ok` holds | 57 verified, 0 errors | `gone_ok` does not forbid legitimate re-publication, and the repair is not over-restrictive. |

## Evidence findings

- **Receipts.** All latest prove and control receipts are FRESH (gate exit 0). My base re-proofs and the two re-applied controls reproduce the receipts' verdicts and attributions. The control receipts record per-function failures, for example `zero-counter-kept` → `lemma_delete_exact` with errors 1. The ledger prove and control receipts were produced with `--num-threads 6`, against the 4-thread limit for this arm; the 4-thread re-run gives the same 38 verified, so it is not material.
- **Observed claims checked against raw observations:**
  - `erasure_prefix_temporal_only`: before {tE|1: 1, tE|x: 1}; after erase {tE|1: 0, tE|x: 1}; redaction complete with 4 tombstoned; verify equal.
  - `search_bm25_delete_during_build`: 2 deletes inside the window, both False, both resurrected.
  - `redaction_concurrent_targets`: "became live again" refusal present.
  - The receipt copies are byte-identical to the raw files.
- **R3-6 (stale evidence, temporal section of coverage.md).** These are left from R2-3:
  - The non-superseded row "explicit `delete_edge` of a marked row with live timestamps" says "upstream test not run". The test it cites, `test_254_purge_e2e.py:322`, is in the suite that passed 22/22 (`$RUN_DIR/tests/cited/test_254_purge_e2e.log`).
  - The gap list says "test_255_* was not run", but us1/us2/us3 passed 19/6/14, as the round-2 table itself says.
  - The superseded rows (for example `temporal.stats.after-purge` "test_ledger_us11 … not run", which passed 6) stay in the same file. A reader sees two statuses for one clause.
- **R3-2 (stale evidence and overclaim in handoff documents):**
  - final-report.md §3 says "Proved: … batch composition and resume (serialised redactions)", contrary to R2-2.
  - Its counts are stale:
    - 309 obligations / 119 controls → 325 / 126;
    - 32 probes / 37 observations → 34 / 39;
    - "13 High" → 14;
    - runbook "proof (37), 13 controls" → 38 / 14;
    - twin 47 → 48.
  - Its seed rows "Live erasure" and "Redaction and isolation" do not mention bug-led-007 (High, observed). "Redaction and isolation" still calls temporal-only content just "an open question".
  - The coverage "Native suites" row still says "32 files, 37 observations".
  - The placeholders ROUND2_SUMMARY, HIGH_LIST, REPRO_SUMMARY, COVERAGE_GAPS and CONFINEMENT are unfilled. That is expected before handoff, but listed so it is not missed.

## Findings-register check

- **Classification and severity:**
  - bug-led-007 High: supported (native, documented recipe, privacy primitive). Its consequence text overclaims (R3-3).
  - bug-led-008/009 Low (Suspected): consistent with the convention. bug-led-009's consequence is wrong (R3-4).
  - bug-srch-016 Medium (observed): supported. Its repair text is incomplete (R3-7).
  - bug-str-002 High: the reason is now stated and is acceptable.
  - bug-plt-001 and bug-cyp-001 High while Suspected: consistent with the stated rule (Critical consequence lowered one level).
- **Suspected marker.** A script over `bugs_issues.md` found every main-section bug without a native reproduction marked "Suspected", except bug-srch-010. bug-srch-010's "Reproduced by" is a KNOWN_ISSUES record (a documented, accepted behavior), which is acceptable. "27 of 88 natively reproduced" matches.
- **R3-8 (register defects):**
  - bug-str-016 has the wrong classification and an inconsistent consequence:
    - It is a product divergence from a governing glossary rule (CONTEXT "Graph-Version Token"), found by code reading, but it sits under "Observations and documentation drift" with no Expected/Observed/"Suspected".
    - The ontology metadata says "a weighted algorithm answer cached before it would stay current", while the register says the cached algorithms ignore weights and only `^ArnoKG` could be stale, which is untraced.
  - bug-tmp-011 and bug-tmp-013 "Found by" link the superseded temporal receipt `20261114T001508Z-prove` and the round-2 reviewer's scratch witness. They should link the integrated witnesses:
    - `witness_purge_write_race_rowless_route` (RACE-4);
    - `witness_purge_write_race_strands_new_triple` (RACE-5);
    - the recheck-repair witnesses (receipt `20261114T040433Z-prove`).
    The coverage row's own next action ("register the RACE-4/5 routes and the repair shape on bug-tmp-011") is still open.
  - The coverage row `redaction.after-erasure` says **Violated** for bug-002, but the map's own definition requires a model witness and there is none. bug-002 is "found by source review", per R1-12. It should read "Observed violation (native only)", as the search rollback row does.
- **Missing entries:** R3-4 (orphan property rows block prefix redaction; suspected). No other new bug is material in my scope.
- **Simplifications:** simp-003 needs the precondition and distinguishing case in R3-3. simp-001's scope note is still honest.

## Summary table of material findings

| ID | Severity | Category | Owning artifact | Finding | Proposed correction |
|---|---|---|---|---|---|
| R3-1 | Medium | incorrect intent; missing or stale evidence | `ontology/features/redaction.g5.md` (Q `redaction.after-erasure.temporal`; metadata of `redaction.batches.resume`, `.abort`, `.competing`); `ontology/features/erasure.g5.md` (metadata of `erasure.concurrency`, `erasure.atomic.caller-transaction`) | Round-2 repairs left the governing contract wrong: (1) the Q still offers "rely on erasure, which removes them anyway", which is false for prefix targets (bug-led-007, observed); (2) resume of a prefix target is still "proved" (stale receipt `20261113T235716Z`); (3) Final's re-check "not observed natively" although `redaction_concurrent_targets` shows it; (4) concurrent targets "suspected, untested" although bug-001 is observed; (5) erasure.concurrency "neither tested" although bug-002 is observed; caller-transaction "the probe will observe" although it did | Replace the Q's second option with "rely on erasure, which today removes them only for a whole-graph erase or an explicit-id erase (bug-led-007)". Re-tag resume as "Observed (`redaction_interrupt_resume`, `redaction_prefix_resume`); the model proves one call's knowledge only". Cite `redaction_concurrent_targets` for Final's re-check and for bug-001. Cite bug-002 and `erasure_caller_transaction_*` in the erasure metadata. |
| R3-2 | Low | missing or stale evidence (overclaim) | `uplift/…/final-report.md` §2, §3, §5; `Verus_verification/runbook.md` key results; coverage.md "Native suites" row | "Proved … resume (serialised redactions)"; stale counts (309/119/37/13 High/37/13/47); bug-led-007 missing from the erasure and redaction seed rows | Move resume to "Observed". Regenerate the counts (325 obligations, 126 controls, 34 probes / 39 observations, 14 High, 38/14/48). Add bug-led-007 to the "Live erasure" and "Redaction and isolation" rows. Mark `lemma_serial_resume_keeps_attribution` in the runbook as a classification fact. |
| R3-3 | Low | correspondence error (register claim) | `bugs_issues.md#bug-led-007`; `design_simplification.md#simp-003` | "No erase short of erasing the whole shared graph removes them" is false: `EraseNodeIds` (store `delete_nodes`, `delete_node(graph=…)`) erases events of any named id, node row or not (Eraser.cls:352-389, TemporalIndex.cls:421). simp-003's "a target whose content was erased is not refused" turns bug-led-007 into a refusal after every as-built prefix erase. | Correct the consequence ("the documented prefix recipe misses them; removing them needs the event IDs and an explicit-id erase or a temporal delete"). Make simp-003 depend on bug-led-007's erase repair, and add `erasure_prefix_temporal_only` (and R3-4's case) as distinguishing cases. |
| R3-4 | Low | model error (abstraction); product defect (suspected) | `models/ledger_redaction/redaction.rs` (`Item::NodeRow`, `erased`); `bugs_issues.md#bug-led-009`; `erasure.g5.md#erasure.prefix-match` metadata; register (new entry) | `rdf_props` has no FK, and `post_commit_properties` (or raw SQL) can leave a tenant's property rows with no node row. `EraseNodes(prefix)` never selects them, `LiveRows` reads them, so every later prefix redaction is refused and erasing by prefix again changes nothing. The model's `erased(NodeRow)` removes them and hides this (scratch L-d: 39 verified). bug-led-009's "marker stays until the target is erased again" is wrong for prefix targets. | Split property rows from node rows in `Item`, make `erased` product-faithful, add the L-d witness and a control. Correct bug-led-009's consequence ("only an explicit-id erase or raw SQL clears it; until then the marker blocks readers, verify and other targets"). Register a Suspected Low entry, with a native probe: post-commit property on `tP|x` (no node) → `delete_nodes_by_prefix("tP|")` → `redact(None, prefix="tP")` (expect `target_live`) → `delete_nodes(["tP|x"])` → redact completes. |
| R3-5 | Medium | missing intent (coverage record) | `Verus_verification/coverage.md` (ledger/erasure/redaction section and its "Not modeled" list; platform Cypher gap list) | No row and no gap entry for: `ledger.immutability` / `redaction.metadata.exception` (the only immutability exception); `ledger.commit.serial`, `.caller-transaction`, `.expected-head`, `.size`; `ledger.lifecycle` (+genesis); `ledger.readers`; `ledger.verify.scope`; `erasure.scope`'s graph frame and default-graph spellings; `erasure.count`; `erasure.kept`; `erasure.history`; `redaction.audit`, `.receipt`, `.refusals`, `.out-of-reach`; `query.native.*`; `query.shadow*`. Adversarial L-b: a graph-blind erase passes every ledger obligation. | Add rows with the existing upstream observations (`test_ledger_us01` immutability, the test_256 redacted-immutability test, `test_erase_graph` other-graph and both-spellings cases, `test_253_*`, `test_ledger_us03`), marking them "Observed (upstream); not modelled". Or list each in the domain's gap list. Optionally add an `Erase` frame lemma (another graph's items unchanged) to redaction.rs. |
| R3-6 | Low | missing or stale evidence | coverage.md temporal section | Non-superseded text contradicts the logs: "explicit `delete_edge`" row "upstream test not run" (test_254_purge_e2e 22 passed); gap list "test_255_* was not run" (19/6/14 passed); superseded rows kept beside their replacements | Delete or strike the superseded rows. Fix both statements from `$RUN_DIR/tests/cited/summary.txt`. |
| R3-7 | Low | missing intent (repair proposal) | `bugs_issues.md#bug-srch-016` | The repair "test N under the lock in Delete (and Insert)" alone still loses the delete. Scratch S-a, Delete locked and Build unlocked: witness verifies (57 verified). The proved repair `locked_build()` needs bug-srch-003's locked Build/Drop **and** the reordered Delete. | State that both changes are required (or build-and-swap with replay of overlapped deletes), and cite `theorem_repair_delete_takes_effect` with its variant. |
| R3-8 | Low | register defect (classification, stale links); status word | `bugs_issues.md#bug-str-016`, `#bug-tmp-011`, `#bug-tmp-013`; `graph-structure.g5.md#structure.rebuilt.token` metadata; coverage.md `redaction.after-erasure` row | bug-str-016 is a suspected product divergence filed as an observation, without Expected/Observed/Suspected, and its consequence disagrees with the ontology metadata. bug-tmp-011/013 link a superseded receipt and a scratch witness, not the integrated RACE-4/RACE-5 and repair witnesses. The `redaction.after-erasure` row says "Violated" with no model witness. | Move bug-str-016 to the bugs section as Suspected Low with Expected (CONTEXT token rule) and Observed (`Adjacency.cls:128-136`), name the `^ArnoKG` weighted readers or say none, and align the ontology metadata. Relink bug-tmp-011/013 to receipt `20261114T040433Z-prove` and the RACE-4/5 witnesses. Change the row status to "Observed violation (native only)". |

No Critical or High findings. The round-2 model repairs are real, fresh and reproduce: W5 and its control, the BM25 lost-delete witnesses and extended-repair theorem, the faithful purge decide, and zero ≠ absent. The remaining defects are in the contract text, the coverage record and the register that people will read. This is round 3 of 3, so per the guidance no fourth round is started: R3-1, R3-5 and R3-4 should be repaired and validated within this round, or reported as unresolved gaps at handoff.
