# Review-1: checkpoint review of iterations 61–65

**Sign-off:**
- **Q1 native executor:** conditional.
- **Q2 erasure:** not clean.
- **Q3 census:** conditional.

Two problems drive this. The shadow comparator cannot detect a wrong top-k or a wrong order under a partial `ORDER BY`. And `delete_node` deletes an unrelated node in another graph; I reproduced that live.

The census tool passes on a git clone and leaves `summary.md` byte-identical. On the samples, recorded full grades are about 96% right. My estimate of the true full share is 36% (roughly 34–37%), against the published 37.8%. The census also systematically merges outcomes that can fail separately.

I followed `uplift-review.md`: behaviours were derived from the specs and code first, and the authors' handoffs were read last. The work was split four ways:
- **Native executor (Q1):** I did this myself.
- **Erasure (Q2):** a fresh reviewer.
- **Census block sample:** a fresh reviewer, which ran four forks of itself, so those four are not independent of each other.
- **Census row sample:** a fresh reviewer.

I re-checked every material claim that came back from a reviewer. No repository file was edited. The STOP file never appeared.

## Checks run
All on the scratch clone `$G5_RUN_STATE/scratch/review-1/repo` (bc85521e).

| check | result |
|---|---|
| `census.py` | PASS, `summary.md` unchanged. On a `git archive` copy (as the assignment suggests) it fails with 53 "playbook crate tree changed" errors, because it calls `git rev-parse`. |
| `native_admission` proof | PASS, 54 verified |
| `native_admission` controls: complete-order-flag, anchor-ignores-privileges, drop-bulk-gate | EXPECTED_FAIL each |
| My witness `r1_witness_topk_wrong_group_passes` added to `native_admission.rs` | 55 verified, 0 errors |
| Real `plan_query` plus real `native_shadow.compare` (`scratch/review-1/native/topk_probe.py`) | wrong top-1 accepted; reversed count order accepted |
| `erasure_stores` proof | PASS, 49 verified |
| `erasure_stores` controls: frame-ignores-graph, edge-row-keeps-statement, failed-call-partial | EXPECTED_FAIL each |
| Erasure reviewer's own mutants | M1 (relationship erase also removes temporal events) still verifies 49/49; M2–M5 each fail |
| Live: namespace R1N, route alternation | reproduced (see R1-N2); namespace dropped, Exists 0,0 |
| Live: namespace R1E, cross-graph reifier delete | reproduced (see R1-ER-01); namespace dropped, Exists 0,0 |

**Not run:** the two model bindings. Both hard-code I62*/I65* namespaces and create users and roles, which is outside my R1-only permission. The master's replay logs show AGREES for both.

## Findings

### Native executor (Q1)

**R1-N1 · material · incorrect intent, plus a defect in the product's comparator.**
- **Trigger:** an aggregate ordered only by its count, e.g. `MATCH (a:Person)-[:KNOWS]->(b:Person) RETURN a.name AS n, count(*) AS c ORDER BY c DESC LIMIT 1`.
- **Discrepancy:** the planner marks this plan unordered (`native_plan.py:165-166, 478`). The comparator then applies its LIMIT rule (`native_shadow.py:43-52`), which accepts any k groups and any order.
  - So shadow mode would pass a native answer `[Bob,1]` where SQL answers `[Alice,3]`. Unlimited, it also passes a reversed count order.
  - query.native.equal-answers bullets 2–3 (and the model's `owner_equal`) accept the same wrong answers whenever the order does not cover the grouping keys. With tied counts they even admit a row below the cut-off.
  - FR-002 ("row order where the query orders") and FR-013 (exact comparison where the rows LIMIT keeps are totally ordered) rule these answers out.
  - F-0907 records only the opposite direction (false alarms on ties).
  - This is the common shape of the SNB BI queries whose shadow run justified turning native on by default (FR-010).
- **Evidence:** `topk_probe.py`; my witness (55 verified).
- **Limits:** no wrong native answer was observed; this is a blind spot in the check, not a known wrong answer.
- **Repair proposal:**
  - Comparator: check that native rows are sorted by the ORDER BY keys, and that the kept rows' order-key values equal SQL's.
  - Ontology: restate equal-answers for partial orders.

**R1-N2 · material · missing intent (cross-area: route plus known native/SQL divergences).**
- **Trigger:** the defaults (`native_cypher=True`, `native_route_ms=50`) and bug-cyp-104's query.
- **Observed (live, R1N):** across 12 identical calls, calls 1–3 were native. From call 4 the trial alternated SQL and native, returning `['', 'a','b',1,2,None]` and `['a','b',1,2,'',None]` in turn.
  - Each recheck (every 1,000 calls, or on drift) reopens the alternation.
- **Gap:** no owner states that an identical query can return different answers call to call. query.native.route only says it "relies on equal answers", and bug-cyp-104 says "can switch by timing".
- **Evidence:** `native_route.py` `next_path`; `query.py:2063-2082`; `scratch/review-1/native/live/r1_route_alternation.out`.

**R1-N3 · minor · model scope.**
- query.native.fallback#o01 promises "any native failure → SQL answer". Only the `Exec.Run` call is inside the try (`query.py:2144-2152`).
- Errors from `plan_query` (other than its "decline" exception), `_native_translation`, `_names_mapped_label`, or `_finish_sql_result` decoding native rows (`query.py:2127-2158`) would propagate as errors instead of falling back.
- The model's `try_native` lets only `run` fail. The premises column does not record this exclusion.
- No reachable trigger was constructed.

**R1-N4 · minor · owner not repaired.**
- query.native.reads-only still gives "the MATCH before a per-row MERGE" as an example of a read step that may run natively. The census itself (`reads-only#o05`, owner-contradicted since iteration 62) says it never does.
- Correspondence nuance: in the `merge_rows.py` branch where the MERGE follows a WITH (j==0, lines 133-170), the prefix carries no hidden `__` alias. The model's premise `hidden_alias: true` is therefore wrong for that branch. It is declined anyway by `_plan_chain` (a part with a WITH), so the outcome is unchanged.

**R1-N5 · minor · conditional refutation.**
- query.shadow#o03 (full, refuted) rests on the plain-`RuntimeError` branch, which was never constructed behind an admitted plan. The gap column is empty; the premise is recorded.
- The chained-query loop (`query.py:1904-1916`) does not convert `RuntimeError` at all, so the model's `reader` covers only the unchained path.

**R1-N6 · minor · scope.**
- query.compiled.deploy-discards#o01 is graded check_scope full, with the premise "successful deploy".
- But `DropAll` failures are swallowed at debug level (`schema.py:2936-2941`), so "a deploy deletes every compiled plan" is best-effort.
- Should be narrowed.

**R1-N7 · minor · correspondence.**
- Setup resets the executor-version answer only when `objectscript_deployed` is true (`_engine/schema.py:2648-2650`).
- The model's `setup()` resets it unconditionally, and the gates metadata says it unconditionally.

**R1-N8 · minor · contract readability.** query.native.route ends with a stray working assumption ("yes; today they run the translated SQL themselves.") that has no question attached.

**Reported bugs and ontology edits:**
- bug-cyp-159 is reachable as described (`engine.py:303-306`).
- bug-cyp-160 is reachable (`query.py:1904-1916`).
- bug-cyp-161 is reachable: `CypherQuery` has no `source_text`; only `ReturnItem` does (`ast.py:282`).
- The deploy-discards wording edit is correct per `Gen.cls:203-218`.
- The gates metadata edit is correct apart from R1-N7.

**Fidelity of native_admission:**
- The admission decision and the comparison are derived from inputs. Exceptions are the planner's grammar (`shape_ok`), the translation width, the anchor kind and both paths' rows: these are declared premises, and `shape_ok` is checked against the real planner on 16 queries.
- The controls remove decisive guards.
- The binding observes the path through `_native_answers`, which only a successful `_try_native` increments (`query.py:2159`). That is a faithful instrument. The "routed" label is supplied by the harness, but where it matters (shadow mode bypassing the route) the two outcomes are distinguishable.

**The four judgement calls:**
- **reads-only#o05 partial:** agree.
- **privileges#o01 refuted:** agree. The owner's lead ("never") contradicts the block's own working assumption, so the owner text needs repair.
- **equal-answers#o05 partial:** agree. Separately, its rule is too weak (R1-N1).
- **shadow#o03:** acceptable, subject to R1-N5.

### Erasure (Q2)

**R1-ER-01 · material · product defect and correspondence error.**
- **Trigger:** node `ev1` in graph h; edge a→b in graph g; `reify_edge(eid, reifier_id="ev1")`; then `delete_node("a", graph="g")`.
- **Observed (live, R1E):**
  - Before: `ev1` was held in graphs `''` and `h`.
  - After: in neither; `get_node("ev1", graph="h")` returned `None`.
- **Cause:** `_delete_in_scope` deletes reifier IDs in every graph holding that ID via `_graphs_holding` (`nodes_edges.py:2134-2153, 2185-2194`).
- **Model gap:** the model maps `delete_node` straight to `EraseNodeIds` (`erasure_stores.rs:405`). This bug family is recorded so far only for `delete_reification` (bugs_issues.md:830, 5706).
- **Scope:** `bulk_delete_nodes` takes the same path but was not tested.
- **Output:** `scratch/review-1/native/live/r1_reifier_cross_graph.out`.

**R1-ER-02 · material · model error and census grade error.**
- `call` defines a failed erase as "stores unchanged" (`:338-347`), and `joined_then` defines "the caller decides" (`:355`).
- So `theorem_failed_call_leaves_stores` and `theorem_joined_caller_decides` are true by definition, and the controls `failed-call-partial` and `joined-commits-own` mutate those definitions rather than a product step.
- erasure.atomic#o02 and #o03 should be partial.

**R1-ER-05 · material · missing intent / unresolved decision.**
- A relationship-list erase (`EraseEdges`, `Eraser.cls:395-463`) never touches the temporal index, so the erased triple's events stay readable. That contradicts ADR-0009, and node erase does clean them.
- The ontology is silent; q-tmp-006 covers only `delete_edge`.
- Mutant M1 still verifies, so no claim pins this behaviour.
- Not observed live.

**R1-CR-01 · minor (reachability unestablished).**
- `TemporalIndex.RemoveTemporalRow` decrements bucket counters with `$Increment(^KG("bucket"…),-1)` (`TemporalIndex.cls:357`). TROLLBACK does not undo that, so a failure after the temporal step leaves the counters changed.
- erasure.atomic#o01/#o02's premise exempts only the `^KG("__version")` increment.
- #o01 also cites a witness for the wrong case; the uncited `witness_list_erase_commits_earlier_chunk` is the one that carries its refutation.

**Other minor findings:**
- **R1-ER-03:** `method_ep` and `eraser_of` are constant tables, so `theorem_methods_reach_eraser` restates the model.
- **R1-ER-04:** the model has no live/closed distinction for ledger statements, so it claims more than `Eraser.cls:672-677` does.
- **R1-ER-06:** the reifier-node residue (F-1502, rated High) is tagged outside-statement and carried by no obligation.
- **R1-ER-07:** the binding never observes `ledger_revisions` or record content.
- **R1-ER-08:** keeping a graph's non-route registry rows is unratified, and `EraseAll`'s own comment argues the other way.
- **R1-ER-09:** "the store list is derived from GraphStores" is false; the list is hand-written.
- **R1-CB-07:** the model uses Python's control-character set (codes 0–31 and 127), but the Eraser validates through the server GraphKey, which also refuses codes 128–159. The graph-erase theorem also omits the version bump.

**The four iteration-65 bugs:**
- bug-str-118: reachable.
- bug-str-119: reachable on the caller's connection.
- bug-str-120: only if a post-commit DROP fails; not established.
- bug-srch-117: reachable.

**Erasure census rows:** 52 of 58 agree. These six should be partial:
- erasure.atomic#o02 and #o03
- erasure.entry-points#o01 and #o03
- erasure.entry-points.single-path#o02
- erasure.live-statements#o03

### Census (Q3)

**R1-CB-04 · material · stale evidence.** structure.write#o05 is still graded absent ("write_routing has no erase op"). The iteration-65 `theorem_joined_caller_decides` and `witness_dedicated_erase_survives_caller_rollback` now represent it, so it should be partial.

**R1-CB-05 · material · splitting.**
- ledger.observability#o03 is one partial row covering 11 outcomes. About 9 of them have their own proofs (`ledger_client.rs:519-741`).
- algorithms.op.paths.weighted#o06/#o08 each merge a Python refusal with a native outcome.
- This is the dominant error pattern across the sample.

**R1-CB-01 · material · grade error.** search.knn.threshold#o03 is full, but its theorem only checks sorted inputs. A "limit, then filter" variant satisfies every conclusion (I verified this), so it should be partial.

**R1-CR-02 · material · absent but modelled.**
- install.snapshot#o04 is represented by the d1b dirty-export counterexample (`cx_fc1801`, which has a control receipt), and no census row cites it.
- It may instead belong in the excluded list as an undecided policy alternative.

**Minor census findings:**
- **R1-CR-03:** install.schema.classes_follow#o01 and algorithms.owner#o01 are absent but modelled; should be partial.
- **R1-CR-04:** structure.adjacency.scan#o09 rests on an unstated premise (no inline relationship properties); check_scope should be narrowed.
- **R1-CB-02 (adjudicated):** search.fusion.python#o03 can keep full, but check_scope should be narrowed because the fused sort is a premise.
- **R1-CB-03:**
  - algorithms.op.paths.weighted#o18 should be partial.
  - search.fusion.python#o06 should be absent.
  - Seven partial rows have no model locator, and the lint does not catch this.
- **R1-CB-06:** ledger.commit.expected-head is missing the "naming the current head commits" row.
- **R1-CB-08:** erasure.kept#o06 check_scope should be narrowed.
- **R1-CR-07:** install.export.rdf.report#o02 is missing two locators.
- **R1-T1 (tooling):** `census.py` needs a git checkout. The README and runbook say a copy of `.g5/` works, but on a copy every playbook receipt fails as "crate tree changed".

## Census sample results

| sample | how drawn | agreement |
|---|---|---|
| Blocks | every 25th row of `blocks.tsv` (16 blocks) plus `graph.names.report` (the child of the only parent drawn): 17 blocks, 124 obligations | grades 119/124 (96.0%, Wilson 90.9–98.3%); 120/124 after my adjudication. About 25 obligations missed through merged rows. No exclusion hides a material obligation. No unsound parent entailment. No structural zeros in the draw. |
| Full rows, iteration ≥ 64 | 443 rows, every 22nd from the 22nd (N=22): 20 rows | 19/20 after adjudication (95%, 76–99%); 17/20 including check_scope |
| Absent rows, iteration ≥ 64 | 21 rows, every 2nd (N=2): 10 rows | 6/10 (31–83%). 3 are modelled and should be partial; 1 is borderline. |
| Erasure page (purposive, every row) | 53 full rows | 47/53 |

**Errors by pattern:**
- Merged outcomes deflating the denominator: dominant.
- Point checks graded full where the theorem never exercises the row's own contrasting case: 2.
- Definitional theorems: erasure, 3 rows.
- Stale rows not re-searched after new models: 1 found.
- Absent but modelled: 3–4.
- Narrowing premises recorded as check_scope full: 3.

The obligation statements themselves were faithful to their blocks in every sampled row.

**Estimate of the true full share:**
- Pooling the random full rows (block sample and row sample): 76/79 hold, about 96% (Wilson about 89–99%).
- The erasure page is worse (89%), so errors cluster in the newest rows.
- Applied to 794 recorded full rows: about **755 of 2,100 = 36%** (about 34–37%).
- The denominator itself is probably understated by roughly 10–20% because of merging. Splitting would add obligations in both directions (some full, some not), so treat the interval as wider in practice.

## Q4: most consequential uncovered behaviours
1. **Shadow parity under partial ORDER BY / top-k** (R1-N1): no owner and no check.
2. **Answers alternating call to call under default routing** wherever native and SQL differ (R1-N2): reproduced live, no owner.
3. **Erasing in one graph deletes a same-ID node in another graph** through reifier cleanup (R1-ER-01): reproduced live.
4. **Relationship erase leaving temporal events behind** (R1-ER-05), and bucket counters surviving rollback (R1-CR-01).
5. **Engine-level caches that never revalidate.** These are documented only as working assumptions or open questions:
   - privileges: no REVOKE reaches a running engine;
   - index declaration: the cached index answer is never re-checked;
   - another engine's bulk load: q-cyp-003, open.

## Conditions to clear sign-off
- **Q1:**
  - Record R1-N1 as a finding and add the complete-order direction to the model, with a control.
  - Amend query.native.equal-answers.
  - Record R1-N2 under query.native.route.
  - Repair the reads-only example and the privileges lead.
  - Narrow fallback#o01's premise and deploy-discards#o01's scope.
- **Q2:**
  - File R1-ER-01 and model the reifier step (or narrow the claim).
  - Regrade the six erasure rows.
  - Add an owner or question for R1-ER-05.
  - Add the reifier-residue obligation.
  - Fix erasure.atomic#o01's locators and premise.
- **Q3:**
  - Regrade R1-CB-01/03/04, R1-CR-02/03/04 and the scope rows.
  - Re-split the merged rows (ledger.observability, weighted paths, fusion, capabilities) under one stated rule.
  - Re-search rows older than iteration 65 against the iteration-65 models.

## Limitations
- The bindings were not replayed (namespace permission).
- R1-ER-04, R1-ER-05, R1-ER-08 and R1-CR-01 come from reading source only.
- The samples are small and sampling was not blind: reviewers saw the recorded grades.
- The four block-sample forks share one set of instructions.
- Split counts are judgement calls.

All notes and scripts are in `$G5_RUN_STATE/scratch/review-1/`: `native/` (`NOTES-q1.md`, probes, witness, live outputs), `erasure/`, `census-blocks/`, `census-rows/` and `sample-ids.txt`.
