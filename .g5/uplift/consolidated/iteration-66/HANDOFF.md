# Iteration 66 handoff — repairs of review-1's accepted findings (native, erasure, census)

Builder: Opus 5.5 (high). Assignment: [ASSIGNMENT.txt](ASSIGNMENT.txt). Start commit `fb6660a0` (review-1 and its
[dispositions](../review-1/DISPOSITIONS.md)). Product pin `3eaa79cf`: no product file was edited (`check_consolidated`
confinement: product paths equal the pin in HEAD and the working tree). The STOP file was checked between steps and was
never present. Fixture: the run's own `ivg-cov-20261118-a-iris` (127.0.0.1:36481); namespaces `I62B`/`I62C` (native
binding), `I65B`-`I65E` and `I66E` (erasure binding).

How the work was split: the native repairs were done by the builder itself. Two forks of the builder session did the
other two areas, each with its own files: erasure (model, binding and erasure page; it drafted findings, questions,
crosswalk rows and a census ledger) and census (the TSVs, README, `census.py`). The builder:
- merged their drafts;
- adjudicated the two open choices (§4);
- regraded the four node-delete rows neither fork owned;
- ran every gate on the merged tree.

The forks are not independent reviewers. Commits:
- `d05b1aef`: native and census;
- `32f809f8`: the erasure merge, crosswalks and correspondence stamp;
- this handoff's commit.

## 1. Result

| | start (`fb6660a0`) | end |
|---|---:|---:|
| whole foundation: full / partial / absent of total | 794 / 666 / 640 of 2100 | **839 / 688 / 670 of 2197** |
| full/total | 37.8% | 38.2% |
| retained 2100 obligations: full / partial / absent | 794 / 666 / 640 | 802 / 667 / 631 (38.2%) |
| scope change: 97 added obligations | — | 37 full, 21 partial, 39 absent |
| proved over the full stated scope | 227 | 225 |
| proved incl. narrowed / bounded / refuted | 1138 / 1 / 152 | 1187 / 1 / 156 |
| active bindings (member_reach) | 824 / 4130 | **829 / 4130** |

**Models.**

| model | proof | controls | binding |
|---|---|---|---|
| native_admission | 54 → 62 verified | 23 → 30, all EXPECTED_FAIL | AGREES, 50 → 55 live cases; R1-N1 reproduced with the real planner and comparator |
| erasure_stores | 49 → 66 verified | 20 → 28, all EXPECTED_FAIL | AGREES, 28 → 36 cases; R1-ER-01 reproduced live in I66E |
| route_recheck | re-proved, 6 (unchanged) | — | — |

All three models use bundled vstd only, with no `assume`, `admit` or `external_body`.

**Detection.**
- native: 6 of 6 detections fire, 3 of them new;
- erasure: 11 of 11 fire, 6 new;
- the reviewer's mutant M1 now fails erasure_stores, in `theorem_edges_erase_keeps_temporal`.

**Findings and questions.**
- new findings: [bug-cyp-162](../../../Verus_verification/bugs_issues.md#bug-cyp-162) (Medium, R1-N1) and
  [bug-str-121](../../../Verus_verification/bugs_issues.md#bug-str-121) (Medium, R1-ER-01);
- new questions: [q-tmp-007](../../../Verus_verification/open_questions.md#q-tmp-007) (R1-ER-05) and
  [q-srch-007](../../../Verus_verification/open_questions.md#q-srch-007) (R1-ER-08);
- reproduction notes added to bug-cyp-104, F-1502 and bug-str-014.

**Gates on the final tree** (raw output in [gates/](gates/)):
- `census.py`: PASS, including the lint with the new LINT-4;
- `check_evidence`: FRESH;
- `check_consolidated` (`G5_GUIDE=$G5_HARNESS/guidance`, against the new
  [correspondence stamp](correspondence-inputs.json)): PASS;
- `check_ontology`: 0 issues, 17 warnings (unchanged);
- `check_findings`: no problems.

Before the stamp was recaptured, the correspondence gate listed only this iteration's files as changed: the two models,
the two bindings, the two `model.json` files and `decision-links.tsv`. Each of them was re-proved or replayed after its
final edit.

## 2. Every DISPOSITIONS row

Receipt paths are under `.g5/Verus_verification/results/`:
- native: prove `native_admission/20261118T051854Z-prove`; 30 controls `20261118T051858Z`…`052057Z-control-*`;
  binding `native_admission/20261118T051407Z-binding`;
- erasure: prove `erasure_stores/20261118T051838Z-prove`; 28 controls `051842Z`…`052020Z-control-*`; binding
  `erasure_stores/20261118T052216Z-binding`.

| row | outcome | what was done | evidence |
|---|---|---|---|
| R1-N1 | **repaired** + finding + owner amended | Finding bug-cyp-162 filed. Owner [query.native.equal-answers](../../../ontology/architecture/query-execution.g5.md#query.native.equal-answers) restated to FR-002/FR-013: exact equality where nothing ties; with ties, sort values in SQL's order; multiset without ORDER BY; the LIMIT rule plus sort-value order. A "Today" bullet states the comparator's blind spot. Model: `owner_equal` → `fr013_equal`, plus `witness_comparator_accepts_wrong_topk`, `witness_comparator_accepts_reversed_count_order`, `theorem_blind_spot_is_partial_aggregate_order` and `theorem_comparator_sound_off_partial_aggregate_order` (off the blind spot, a passing comparison implies the rule, all sizes). Controls: `topk-plan-ordered` (planner step), `owner-drops-order-keys` (the pre-66 owner rule fails the witnesses), `ordered-compared-as-bag`, `plan-drops-order`. Regraded rows: equal-answers #o03-#o05; new #o06 (partial) and #o07 (full); shadow#o02 gets a second refutation. | **Reproduced** with the real `plan_query` and `native_shadow.compare` (`topk_r1_n1.r1_n1_reproduced` true): the wrong top-1 and the reversed order are accepted by the comparator and rejected by `fr013_t`; ordering by the grouping key raises. **Live** in shadow mode with a substituted wrong native answer: `blind_spot_wrong_top1` returned `[['bob',1]]` where SQL answers `[['alice',3]]`; `blind_spot_reversed_order` likewise; the neighbour `blind_spot_neighbour_key_order` raised. |
| R1-N2 | **repaired** (modelled) + owner "Today" bullet | `call_routed` transcribes `next_path`/`record`/`_routed_sql`. `theorem_route_trial_alternates_answers` (from a shape's first call: native ×3, then SQL and native in turn; calls 5 and 6 return each path's own rows) and `theorem_successive_calls_differ_in_trial`; control `trial-no-alternation`. Route bullet: identical calls alternate during a trial and every recheck or drift trial restarts it. New rows route#o16 (full) and #o17 (partial: the recheck restart lives in route_recheck and drift is unmodelled). | Live `route_alternation_bug_cyp_104`: 12 identical calls N,N,N,S,N,S,…, two answers in turn, trial premise observed on the real route each call. Neighbour `route_alternation_paths_agree`: same paths, one answer. Note added to bug-cyp-104. |
| R1-N3 | **open obligation recorded**; row split | fallback#o01's premise narrowed to failures inside `Exec.Run`. New fallback#o03 (absent) covers the Python steps outside the try: planning, translation, the mapped-label check, decoding. NOTES and metadata name them; no reachable trigger has been constructed. | source reading, `query.py:2127-2158` |
| R1-N4 | **repaired** | reads-only bullet 1 is now the chained read after a write (the case that does run natively). New bullet 2: a write's own read steps always take SQL. Model: `merge_prefix_after_with` (the after-WITH prefix is declined by the planner; a hidden alias only with `refs`); control `merge-after-with-planned`. reads-only#o05 is still partial (visibility is observed live only); new #o06 is full. | binding `chained_write_then_read`, `count_create_step`, `row_merge_prefix`; the planner domain declines a WITH part |
| R1-N5 | **recorded** | shadow#o03's premises now name the unconstructed `RuntimeError` branch and state that `reader` covers only the unchained path (the chained loop at 1904-1916 does not convert). NOTES updated. | — |
| R1-N6 | **regraded** | deploy-discards#o01 check_scope full → narrowed (`DropAll` failures are swallowed at debug level); metadata note added. | `schema.py:2936-2941` |
| R1-N7 | **repaired** | `setup(e, objectscript_deployed)`, `theorem_setup_resets_only_after_deploy`, control `setup-resets-unconditionally`. The gates metadata and the crosswalk row are corrected. The binding passes the observed `capabilities.objectscript_deployed`. gates#o04 premise updated. | binding `exec_restored_after_setup` |
| R1-N8 | **repaired** | The stray assumption is now attached to its question ("on whether the second HTTP app's Cypher endpoints should answer through the engine", [query.routes](../../../Verus_verification/open_questions.md#query.routes)); route#o15 locator updated. | — |
| privileges lead (census owner-contradicted) | **repaired** | The lead now states the FR-011 requirement. A "Today" bullet states the per-engine check: a new engine keeps the caller on SQL; a later REVOKE misses index-anchored native reads, while SQL-anchored reads fail and fall back. New row privileges#o04, full. | existing `priv_*` live cases |
| R1-ER-01 | **repaired** + finding + live | Finding bug-str-121 (Medium) filed. Model: `delete_in_scope`/`reifier_sel`/`holding_graphs` replace the delete_node → EraseNodeIds mapping; `theorem_delete_node_sweeps_reifier_everywhere`, `witness_delete_node_erases_reifier_in_other_graph`; controls `delete-node-is-erase-ids` (iteration 65's mapping) and `reifier-sweep-default-graph-only` (repair). erasure.scope gets a "Today" bullet. bulk_delete_nodes shares the path and was reproduced too. The builder regraded structure.node.delete#o03 to full; #o01's statement is scoped to its graph, with a gap naming bug-str-121; structure.write#o11 stays partial with the new locator. | **Live** I66E `R1_delete_node_reifier_other_graph`: node rows 14 → 11; `ev1` gone from graph h and from the default graph; `get_node("ev1", graph="h")` returned the node before and None after. `R2_*` shows the same through `bulk_delete_nodes`; neighbour `C4_delete_node`. |
| R1-ER-02 | **repaired** (non-trivial); grades kept full (§4) | The transaction is modelled as a stack of journal levels (`tstart`, `tcommit`, `trollback1`, `rollback_to`). A fault may leave any partial write (`Fault::At{mid, late, dbucket}`), and the Catch rolls back to the level it found. `theorem_failed_call_leaves_stores`, `theorem_joined_caller_decides` and `theorem_joined_list_erase_keeps_caller_work` follow from these steps. The controls now mutate product steps: `failed-call-partial` (the Catch closes instead of rolling back), `joined-commits-own` (TCOMMIT ends every level), `catch-rolls-back-every-level` (pre-4.6.4 Catch), `writetxn-undo-ends-caller-level`. | live E1-E6 (unchanged cases) |
| R1-ER-03 | **regraded** | erasure.entry-points#o01 full → partial: the method table is a transcription; metadata says so. | — |
| R1-ER-04 | **repaired** | `live_stmt`: a row-level erase removes only the live statement, a graph erase removes both. `witness_list_erase_keeps_closed_statement`; control `edge-row-kills-closed`. live-statements#o03 kept full. | live `R4_relationship_erase_keeps_closed_statement` |
| R1-ER-05 | **repaired**: claim + owner "Today" bullet + question | `theorem_edges_erase_keeps_temporal`, `witness_edge_erase_leaves_triple_events`. M1 and control `edges-erase-temporal` both fail. erasure.entry-points has a "Today" bullet; question q-tmp-007 sits beside q-tmp-006. New row entry-points#o07. | live `R3_relationship_erase_keeps_events`; `R3_reader_…` shows `get_edges_in_window` still returns the event |
| R1-ER-06 | **obligation added** | erasure.scope#o10 (lead, refuted by `witness_named_erase_keeps_reifier_node`) and #o11 (the "Today" bullet); note added to F-1502. | binding `B1_reader_reifier_node_after_erase` |
| R1-ER-07 | **repaired** (binding) | The observer reads every `^IVG.Ledger("rec")` node (CRC) and every `ledger_revisions` row (digest); new detection `observed_history_changed`. | erasure binding receipt |
| R1-ER-08 | **question opened** | q-srch-007, with EraseAll's comment as evidence; the "kept on purpose" wording removed from NOTES, the model comment and the erasure.history metadata. | — |
| R1-ER-09 | **corrected** | "derived from GraphStores" corrected in the erasure.scope metadata, NOTES and BINDINGS: the list is written by hand. | — |
| R1-CR-01 | **premise / open obligation recorded**; citation fixed | `St.bucket` and `witness_failed_call_keeps_increments`: the bucket counter's `$Increment` survives rollback, recorded on atomic#o01/#o02 (reachability unestablished). #o01 now cites `witness_list_erase_commits_earlier_chunk`. | — |
| R1-CB-07 | **repaired** | `ctl` uses GraphKey's set (0-31, 127, 128-159), control `python-control-set`; `theorem_graph_erase_call` includes the version bump, control `no-version-bump`. | live B8: `"bad\x85"` passes Python's check, the Eraser refuses it, stores unchanged |
| R1-CB-08 | **regraded** | erasure.kept#o06 check_scope → narrowed; `theorem_node_delete_and_bypass_keep_never_kinds` added. | — |
| R1-CB-04 | **regraded** | structure.write#o05 absent → partial (erasure_stores joined/dedicated theorems, now non-trivial). | census ledger |
| R1-CB-01 | **regraded** | search.knn.threshold#o03 full → partial (a point check on sorted input). | — |
| R1-CB-02 | **regraded** | search.fusion.python#o03 kept full, check_scope narrowed (the fused sort is a premise). | — |
| R1-CB-03 | **regraded** + lint | algorithms.op.paths.weighted#o18 → partial. search.fusion.python#o06 → absent (then split). Of the seven partial rows without a locator, four gained locators; structure.rebuild#o06 and search.fusion.surfaces#o06 → absent (the latter split in three). **LINT-4** (a partial row must carry a model locator) added; it catches exactly these rows. | `census.py` |
| R1-CB-05 | **repaired** | One splitting rule written in [census/README](../../../Verus_verification/census/README.md) (split when one outcome can fail while another holds, including a Python refusal against a native outcome, and separable entry points). Named rows re-split: ledger.observability#o03 → 11 rows, #o04 → 3; weighted paths #o01/#o03/#o04/#o06/#o08; fusion; capabilities#o02 → 3. A mechanical sweep ([sweep.py](census/sweep/sweep.py)) flagged 279 rows: 41 split, 236 not split with a reason code ([decisions](census/sweep/decisions.tsv)), 2 left to erasure. | [scope.tsv](census/scope.tsv) |
| R1-CB-06 | **added** | ledger.commit.expected-head#o03 ("naming the current head commits"), partial. | — |
| R1-CR-02 | **regraded** (obligation, not alternative) | install.snapshot#o04 absent → partial. The block's "for the current exporter" states current behaviour, so it is an obligation; it cites `cx_fc1801` (proofs-d1b) with its control. | — |
| R1-CR-03 | **regraded** | install.schema.classes_follow#o01 → partial (`platform`); algorithms.owner#o01 → partial (`traversal_strategy`). | — |
| R1-CR-04 | **regraded** | structure.adjacency.scan#o09 check_scope narrowed (no inline relationship properties). | — |
| R1-CR-07 | **repaired** | install.export.rdf.report#o02: the two missing `rdf_reporting` locators added. | — |
| re-search | **done** | 122 candidate rows graded before iteration 65 were re-searched against native_admission and erasure_stores ([candidates](census/research-candidates.tsv), [decisions](census/research-decisions.tsv)): 16 regraded, 3 given a locator only, the rest unchanged with a reason. | — |
| R1-T1 | **repaired** | The README and runbook say `census.py` needs a git checkout. Outside a git work tree it now skips the crate-tree check with a note instead of failing; output is unchanged on a checkout. | — |

## 3. Census before and after

Full per-page and transition table: [census-delta.md](census-delta.md), produced by
[regrade-tools/census_delta.py](regrade-tools/census_delta.py) against `fb6660a0`. Per-row ledgers:
- [census/ledger.tsv](census/ledger.tsv) (census worker);
- [regrade-tools/native-ledger.tsv](regrade-tools/native-ledger.tsv);
- [regrade-tools/census-ledger.tsv](regrade-tools/census-ledger.tsv) and `census-newrows.tsv` (erasure);
- [regrade-tools/node-delete-ledger.tsv](regrade-tools/node-delete-ledger.tsv).

**Scope change, reported separately from repair.** 97 obligations were added and none removed:

| source | added | full | partial | absent |
|---|---:|---:|---:|---:|
| census splits (R1-CB-05 named rows and the sweep) | 84 | 28 | 18 | 38 |
| R1-CB-06 missed row | 1 | — | 1 | — |
| native owner edits and the fallback split | 7 | 4 | 2 | 1 |
| erasure owner edits and one split by entry point | 5 | 5 | — | — |

The reviewer estimated that the denominator was understated by 10-20%. This repair adds 4.6%, because the sweep split
only the rows it judged separable. Most "not split" decisions used the default reason code and were not read one by one
(§6).

**Retained change on the original 2100 obligations:** full 794 → 802, partial 666 → 667, absent 640 → 631.

| transition | rows |
|---|---:|
| partial → full | 10 (8 split originals now graded on their first outcome; structure.node.delete#o03; re-search) |
| absent → full | 3 (re-search: search.routes.orphan#o02, fhir.interpretation#o04, structure.edge.delete#o06) |
| absent → partial | 11 (R1-CB-04, R1-CR-02/03, re-search) |
| full → partial | 5 (R1-CB-01, R1-CB-03 weighted#o18; erasure entry-points#o01, #o03, single-path#o02) |
| partial → absent | 5 (R1-CB-03 locator-less rows, mostly split originals) |

**Per page (full/total, before → after):**

| page | before | after | change |
|---|---:|---:|---|
| features/erasure | 45/49 | 47/54 | retained 45 → 42, +5 added (all full) |
| architecture/query-execution | 34/70 | 38/78 | retained 34 → 34, +8 added (4 full) |
| operations/ledger | 19/36 | 36/57 | ledger.observability split |
| features/algorithms | 35/137 | 39/148 | |
| features/temporal | 68/169 | 72/177 | |
| features/graph-structure | 29/99 | 32/100 | |
| features/search | 61/133 | 61/140 | |
| features/cypher | 107/322 | 109/333 | |
| others | | | ±0-2 each: see census-delta.md |

## 4. Choices this builder made

1. **erasure.atomic#o02, #o03 and erasure.live-statements#o03 stay full.** The reviewer listed them as partial, and
   R1-ER-02 offered either path: model the failing step, or regrade. The failing step is now modelled. The fault leaves
   an arbitrary partial write, and the store returns to its found state only through the transcribed Catch,
   `rollback_to(found)`. Each control mutates a product step (the Catch, TCOMMIT, WriteTxn's undo) and makes the
   theorems fail. live-statements#o03 now distinguishes live from closed statements (R1-ER-04).

   The remaining premise is IRIS's own rollback semantics, an environment premise checked live at three failure points
   (E3-E5). A reviewer who considers that premise a narrowing should read these rows as "full, narrowed".
2. **structure.node.delete#o03 → full.** It states the as-built sweep, including "in each graph holding them", which
   is now modelled and reproduced. Its conflict with erasure.scope is bug-str-121.
3. **bug-cyp-162 is graded Medium.** It is a blind spot of the gate that justified the FR-010 default, not an
   observed wrong answer.
4. **No separate finding for R1-N2.** The divergences are bug-cyp-104 and bug-cyp-136. The alternation is the route's
   consequence, so it is stated in query.native.route as built and attached to bug-cyp-104 as reproduced evidence.

## 5. Owner (governing text) edits and why

| block | edit | reason |
|---|---|---|
| query.native.equal-answers | bullets 2-3 restated to FR-002/FR-013; added the tie bullet, the no-ORDER-BY bullet, sort-value order in the LIMIT bullet, and the "Today" comparator bullet | R1-N1: the old text admitted a wrong top-k |
| query.native.privileges | the lead is the FR-011 requirement; a "Today" bullet gives the per-engine check | the census's owner-contradicted note; review agreed |
| query.native.reads-only | bullet 1 is the chained read after a write; bullet 2 says a write's own read steps take SQL | R1-N4 (owner-contradicted since iteration 62) |
| query.native.route | a "Today" alternation bullet; the working assumption is attached to its question | R1-N2, R1-N8 |
| erasure.scope | two "Today" bullets: the graph erase keeps reifier nodes (F-1502); delete_node and bulk_delete_nodes sweep reifier IDs in every graph (bug-str-121) | R1-ER-01, R1-ER-06 |
| erasure.entry-points | a "Today" bullet: a relationship-list erase leaves temporal events (q-tmp-007) | R1-ER-05 |

Metadata-only edits were made to: gates (setup's conditional reset), fallback (the open obligation), deploy-discards
(DropAll best effort), shadow and equal-answers (finding links), and the erasure blocks (R1-ER-02/03/04/07/08/09 notes).

## 6. Limitations and residual work

- **Transcriptions, not proofs of the bodies.** Both models are transcriptions; their product correspondence rests on
  the live bindings, which use small fixtures.
- **R1-N1 live evidence uses a substitute.** It replaces the native rows (disclosed); no wrong native answer is known.
  The FR-013 owner rule reads ORDER BY keys only from returned columns. An ORDER BY on an expression the query does not
  return is checked only through the returned columns, so F-0907's case uses the empty key.
- **R1-N2 depends on timing.** The model holds while a trial does not end, which is a timing premise: native median
  under `small_ms`, and no SQL timing over 4x native's slowest. The binding reads the real route's `_trial` flag as
  that premise. The trial's end (route#o05/#o07/#o08) and drift (#o12, #o17) stay unmodelled.
- **R1-N3 has no trigger.** It stays an open obligation, fallback#o03, absent, because no reachable raise in the
  Python steps has been constructed.
- **Erasure residue:**
  - the reifier sweep's own failure after the node delete committed (structure.write#o11 partial);
  - bucket-counter reachability (R1-CR-01);
  - temporal aggregates of list erases (entry-points#o03 partial);
  - stores not populated live (edge vectors and routes, IVF, PLAID, label sets, Arno);
  - R1-ER-03, where the method table is still a transcription (regraded, not repaired).
- **The sweep was not exhaustive.** Of 279 flagged rows, 236 were not split, mostly under the default "two sides of
  one decision" code, and not each was read. A reviewer should sample them. The denominator may still be understated.
- **No independent review yet.** The forks share the builder's context. The next review round should sample:
  - the 37 added full rows;
  - the 10 partial → full rows;
  - the three erasure rows kept full (§4.1);
  - the sweep's "not split" decisions.
- **Member reach** ([member-delta.json](member-delta.json)): active 824 → 829. Gained: `_graphs_holding`,
  `_reifiers_of`, `QueryMixin._routed_sql`, `NativeRoute.__init__` and `NativeRoute.record`. Four of these were also
  newly reached by a locator (overlap 4, distinct 5); no losses. The other members the erasure worker expected, such as
  `RemoveTemporalRow` and `WriteTxn.rollback`, were already counted or are outside the census.
- **Not done:** nothing in DISPOSITIONS is left undone. R1-N3 and R1-CR-01 are recorded as open obligations by design.

## 7. Replay

The runbook's iteration-66 sections have the commands (prove, controls, binding, census replays) and worked lookups:
- native: `witness_comparator_accepts_wrong_topk` ↔ `_plan_stages`/`compare`;
- route: `theorem_route_trial_alternates_answers` ↔ `NativeRoute.next_path`;
- erasure: `witness_delete_node_erases_reifier_in_other_graph` ↔ `_delete_in_scope`.

Census replay order, from the `fb6660a0` TSVs:
1. `census/tools/apply.py`;
2. `regrade-tools/apply_native.py`;
3. `census/tools/repoint.py`;
4. `regrade-tools/apply_ledger.py … census-ledger.tsv --in-place`;
5. the node-delete ledger;
6. `census.py`.
