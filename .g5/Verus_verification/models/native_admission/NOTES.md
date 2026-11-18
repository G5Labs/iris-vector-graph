# Native admission, fallback and shadow comparison

As-built transcription at `3eaa79cf` (iteration 62; repaired in iteration 66 after review-1, see the last section). Owners:
- [query.native](../../../ontology/architecture/query-execution.g5.md#query.native), with its children
  [gates](../../../ontology/architecture/query-execution.g5.md#query.native.gates),
  [privileges](../../../ontology/architecture/query-execution.g5.md#query.native.privileges),
  [reads only](../../../ontology/architecture/query-execution.g5.md#query.native.reads-only),
  [fallback](../../../ontology/architecture/query-execution.g5.md#query.native.fallback) and
  [equal answers](../../../ontology/architecture/query-execution.g5.md#query.native.equal-answers) (the owner's FR-002/FR-013 rule as `fr013_equal`, and the comparator against it);
- [query.shadow](../../../ontology/architecture/query-execution.g5.md#query.shadow);
- [query.native.route](../../../ontology/architecture/query-execution.g5.md#query.native.route) #o03 (shadow bypasses the
  route) and, since iteration 66, the trial's path order and its consequence for answers (`call_routed`). The route's
  recheck state machine is [route_recheck](../route_recheck/NOTES.md).

The model derives, from the deciding inputs, which path answers a Cypher read at `_execute_parsed` and what
`execute_cypher` returns or raises. The admission decision and the comparison are spec functions of the inputs, never
inputs themselves.

## What is transcribed

| spec fn | source (pin) | what it decides |
|---|---|---|
| `resolve_native` | `engine.py` `IRISGraphEngine.__init__` 303-306 | `native_cypher`: the argument when given, else `IVG_NATIVE_CYPHER != "0"` |
| `shadow_on` | `_engine/query.py` `_cypher_shadow` 2112-2116 | the attribute, or `IVG_CYPHER_SHADOW == "1"`, read on every call |
| `plan` | `cypher/native_plan.py` `plan_query` 50-59, `_plan_chain` 77-262, `_plan_stages` 384-480 | declines a mutation, a procedure call, a UNION, a chained query, SKIP and any clause other than MATCH/WHERE (a `CALL { }`); the plan's `ordered` (ORDER BY present; for an aggregate, ordered on every grouping key) and `limited` flags |
| `gate` with `idx_probe`, `priv_probe`, `exec_probe` | `native_plan.py` `native_gate` 524-536; `engine.py` `_adjacency_indexed` 704-723, `_native_privileges` 559-586, `_native_executor_current` 588-610 | the gate order and reasons; each answer cached per engine; setup (`initialize_schema`, schema.py 2647-2650) resets the index and executor answers only when `capabilities.objectscript_deployed` (iteration 66, R1-N7: `setup(e, objectscript_deployed)`), and never the privilege answer; a transient version-probe error is not remembered |
| `names_mapped` | `_engine/query.py` `_names_mapped_label` 2162-2184 | a label mapped with `map_sql_table` anywhere in the query |
| `try_native` | `_engine/query.py` `_try_native` 2118-2160 | plan, gate, mapped label, the translation check (`is_transactional`, visible columns = plan width), run; the warned set |
| `run` | `Exec.cls` `Run` 32-72, `Anchors` 848-904 | a missing class, a plan of another version, a property-lookup anchor (reads `rdf_props` through `%SQL.Statement`) or an unlabelled-id anchor (reads `nodes`) refused by SQL privileges, any other fault |
| `warn`, `key` | `_try_native` 2146-2152 | one WARNING per distinct `type: message[:160]`, per engine |
| `compare`, `fail` | `cypher/native_shadow.py` `compare` 29-69, `_key` 19-21, `_fail` 24-26 | columns first; the LIMIT rule only when the plan is limited and **not ordered** (count, then every native row spent from the full answer's multiset); ordered row by row; otherwise multisets; a value's type is part of it; the message names the plan's repr (`CypherQuery` has no `source_text`), the parameters, and a row except for a column or LIMIT-count difference |
| `shadow_out` | `_engine/query.py` `_shadow_compare` 2226-2249 | a SQL error result raises `NativeMismatch` naming only the SQL error; a SQL exception propagates; the unlimited rerun for a limited unordered plan |
| `exec_parsed` | `_engine/query.py` `_execute_parsed` 2063-2082 | without shadow, a route holding SQL answers first and a native answer is recorded; with shadow, no route is consulted or recorded and every native answer is compared |
| `reader` | `_engine/query.py` `execute_cypher` 1931-1943 | a plain `RuntimeError` becomes an error result (unless `raise_on_error`); `NativeMismatch` (an `AssertionError`) is raised |
| `chain_part`, `count_step`, `merge_prefix` | `execute_cypher` 1904-1920; `count_create.py` `plan_count_create` (alias `__rows`); `merge_rows.py` `plan_row_merge` (`__rm<i>`) | a chained part is planned with its chain emptied; a write's count/merge read step returns an internal alias, which the translation hides, so its width check declines it |
| `merge_prefix_after_with` | `merge_rows.py` `plan_row_merge` j==0 branch 133-170 | a MERGE right after a WITH: the prefix ends in that WITH part, which `_plan_chain` declines (`shape_ok` false); it has a `__rm` alias only when the MERGE reads a graph variable's properties (R1-N4: the iteration-62 premise `hidden_alias: true` was wrong for this branch; the outcome is the same) |
| `fr013_equal` (`okey`, `okeys`, `total_on`, `order_agrees`, `rows_agree`) | owner: [equal answers](../../../ontology/architecture/query-execution.g5.md#query.native.equal-answers), spec 253 FR-002/FR-013 | not a product function: the owner's rule over the rows and the ORDER BY columns. Exact where the order keys separate every row of the full answer; otherwise the order-key values in SQL's order, and the same multiset (no LIMIT) or the same count of rows of the full answer (LIMIT/SKIP) |
| `RouteT`, `next_rpath`, `record_trial`, `call_routed` | `cypher/native_route.py` `NativeRoute.__init__`/`_start_trial` 38-63, `next_path` 76-83, `record` 85-108; `_engine/query.py` `_execute_parsed` 2063-2082, `_routed_sql` 2084-2104 | a shape's route is created on its first native answer; during a trial native answers until two timed runs follow its warm-up, then SQL's warm-up, then the paths alternate on `_last`; a routed SQL run and a native answer are recorded, a declined native attempt is not. The trial's end (small_ms, the 4x SQL cut-off, the median decision) is not transcribed: `record_trial` is a record that does not end the trial |

## Claims (62 verified, vstd only)

As built:
- **Switches.** `theorem_switch_resolution`; `theorem_per_engine_switch` (one engine with `native_cypher=False` answers
  on SQL while another answers natively); `theorem_explicit_true_beats_env_zero`: `IVG_NATIVE_CYPHER=0` does **not**
  reach an engine built with `native_cypher=True` (refutes query.native#o03's "every engine"; bug-cyp-159).
- **Gates.** `theorem_admitted_only_through_every_gate` (a native answer implies the plan, every gate, no mapped label,
  the translation check and a successful run); `theorem_closed_gate_answers_sql`; `theorem_bulk_session_keeps_sql`;
  `theorem_mapped_label_keeps_sql`; `theorem_version_gate` (cached, remembered until setup, setup asks again);
  `theorem_missing_class_gate`; `theorem_transient_probe_not_remembered`; `theorem_missing_select_keeps_sql`.
- **Privileges.** `theorem_revoke_does_not_reach_running_engine` (the cached answer, through setup too; a new engine
  sees the REVOKE); `theorem_revoke_reaches_sql_anchor_only`: after a REVOKE on `rdf_props` a running engine's
  property-lookup read fails natively and falls back to SQL with one warning, while a label-scan read keeps answering
  natively.
- **Reads only.** `theorem_no_write_is_planned`, `theorem_no_write_runs_natively` (a write clause anywhere: top level, a
  chained part, a UNION branch, a `CALL { }` body); `theorem_call_union_chained_skip_declined`;
  `theorem_chained_part_runs_natively` (the chained parent is declined, its supported parts are admitted one by one:
  refutes reads-only#o04 at `execute_cypher`; bug-cyp-160); `theorem_write_read_steps` (the per-row MERGE prefix and
  count_create's count are declined by the width check); `theorem_read_part_of_chained_write_runs_natively` (a read
  statement chained after a write is admitted inside the write's transaction).
- **Fallback.** `theorem_native_failure_answered_by_sql`; `theorem_one_warning_per_reason`;
  `theorem_reason_is_type_and_160_chars`; `theorem_warned_set_is_per_engine`.
- **Shadow.** `theorem_shadow_switches`; `theorem_shadow_bypasses_route` (route#o03); `theorem_shadow_returns_only_compared`
  (an answer returned in shadow mode passed `compare`); `theorem_shadow_difference_raises` (never returned; the message
  names the plan, not the Cypher text: bug-cyp-161); `theorem_shadow_sql_failure` (a SQL error result raises naming only
  the SQL error; a SQL `RuntimeError` reaches the caller as an error result, not raised; a typed SQL error is raised);
  `theorem_shadow_native_failure_uncompared` (q-cyp-002's working assumption).
- **Comparator.** `theorem_ordered_pass_iff_equal` (all sizes); `theorem_type_is_part_of_the_value` (`1`, `'1'`, `1.0`,
  `true`); `theorem_columns_checked_first`; `theorem_unordered_permutation_passes`;
  `theorem_unordered_difference_names_missing_row` (bug-cyp-136's shape); `theorem_limit_other_rows_pass`;
  `theorem_limit_outside_row_raises`; `theorem_limit_count_names_no_row`; `theorem_limit_pass_means_rows_of_full_answer` (all sizes: a passing LIMIT comparison means the same count and every native row spent from the full answer's multiset, through `lemma_fits_bounded`); `theorem_partial_order_compared_in_order`
  (F-0907 and equal-answers#o05: an ORDER BY that leaves ties marks the plan ordered, so a tie permutation the owner's
  rule admits raises, with or without LIMIT; restated over `fr013_equal` in iteration 66, premise: the two rows tie on
  every ORDER BY column); `theorem_skip_never_compared`; `theorem_aggregate_order_flag`.
- **FR-013 and the comparator (iteration 66, R1-N1, bug-cyp-162).** `witness_comparator_accepts_wrong_topk` (an
  aggregate ordered on its count with LIMIT 1 is planned unordered; `compare` passes `[bob, 1]` where SQL answers
  `[alice, 3]`; `fr013_equal` rejects it because the counts order the full answer totally);
  `witness_comparator_accepts_reversed_count_order` (the same without LIMIT: a reversed order passes the multiset
  comparison); `theorem_blind_spot_is_partial_aggregate_order` (all queries: the plan's ordered flag differs from
  "has an ORDER BY" exactly for an aggregate whose ORDER BY misses a grouping key);
  `theorem_comparator_sound_off_partial_aggregate_order` (all sizes and all ORDER BY columns: off that shape a passing
  comparison implies `fr013_equal`; premise `fits(sql, u)`, SQL's limited rows are rows of its own unlimited answer).
  Limitation: `okey` reads the ORDER BY columns from the returned row; an ORDER BY on an expression the query does not
  return is represented only through the returned columns (F-0907's case uses the empty key: every row ties).
- **Route trial (iteration 66, R1-N2).** `theorem_route_trial_alternates_answers` (from a shape's first call on a warm
  engine, six identical calls take native, native, native, routed SQL, native, routed SQL, and the fifth and sixth
  return each path's own rows, so they differ wherever the paths differ); `theorem_successive_calls_differ_in_trial`
  (any two successive identical calls inside a trial past SQL's warm-up return different rows when the paths differ).
  Premises: a warm engine (its gate answers cached open), an admissible read, the SQL path answers rows, and the trial
  does not end within these calls (a timing premise: native's median under `small_ms`, no SQL timing over 4x native's
  slowest, fewer than `trials` timings of either path; at the defaults calls 1-13 of a fast shape).
- **Setup (iteration 66, R1-N7).** `theorem_setup_resets_only_after_deploy`: a cached "executor not current" answer
  survives an `initialize_schema` whose deploy did not leave the classes in place, and is asked again after one that did.
- **Write read steps (iteration 66, R1-N4).** `theorem_write_read_steps` also covers `merge_prefix_after_with` for
  either value of `refs`.

Controls (30, each failing in its named function): `drop-bulk-gate`, `plan-admits-mutation`, `warn-every-time`,
`shadow-returns-difference`, `shadow-sql-error-answered`, `key-without-type`, `limit-without-count`, `env-wins`,
`recheck-privileges`, `setup-resets-privileges`, `complete-order-flag`, `failure-answers-empty`,
`shadow-consults-route`, `mapped-label-ignored`, `version-gate-dropped`, `transient-remembered`, `drop-native-off-gate`,
`key-whole-message`, `names-query`, `chained-part-keeps-chain`, `show-internal-alias`, `anchor-ignores-privileges`, `limit-skips-spent-check` (caught in `lemma_fits_bounded` and `theorem_limit_outside_row_raises`);
added in iteration 66: `topk-plan-ordered` (the planner marks any aggregate with an ORDER BY ordered: both blind-spot
witnesses fail), `owner-drops-order-keys` (the pre-66 owner rule without order-key agreement: both witnesses fail, i.e.
the owner rule is what rejects them), `ordered-compared-as-bag` (caught in `theorem_ordered_pass_iff_equal`, which the
soundness theorem uses, and `theorem_type_is_part_of_the_value`), `plan-drops-order` (a non-aggregate ORDER BY planned
unordered: the soundness theorem and `theorem_blind_spot_is_partial_aggregate_order` fail), `trial-no-alternation`
(`next_path` always SQL after the warm-up: both route theorems fail), `setup-resets-unconditionally`,
`merge-after-with-planned`.
`env-wins`, `complete-order-flag`, `names-query`, `chained-part-keeps-chain` and `setup-resets-privileges` are the
owner's or a proposed policy; their failure shows the as-built theorem distinguishes the two, not that the repair is
chosen.

## Premises and what is abstract

- `Query.shape_ok` stands for every planner check below the top-level declines and SKIP (the supported grammar of
  families A/B and stages). The binding declares it per query and checks it against the real `plan_query` (16 queries).
- `Query.transactional`, `width_ok` and `hidden_alias` stand for the shared translation's `is_transactional` and
  visible aliases; `Query.anchor` for the planner's anchor choice. The binding derives `hidden_alias` from the step's
  RETURN aliases and declares the anchor from the query.
- `World.native_rows` and `World.sql` are each path's own answer (providers). The model does not compute answers, so
  native = SQL answer parity (equal-answers#o01-#o04) is **not** proved; the binding records a runtime sample. What is
  proved about equal answers is the owner rule (`fr013_equal`) and how far the comparator enforces it.
- Fallback scope (iteration 66, R1-N3): `try_native` lets only `run` (Exec.Run) fail. In the product only the
  `_run_native_plan` call is inside the try (`query.py:2144-2152`); a raise from `plan_query` other than its decline,
  `_native_translation`, `_names_mapped_label` or `_finish_sql_result` decoding the native rows (2127-2158) would
  propagate instead of falling back. No reachable trigger has been constructed; this is an open obligation
  (query.native.fallback), not a modelled outcome.
- `reader` covers the unchained path only (R1-N5): `execute_cypher`'s chained loop (1904-1916) does not turn a plain
  `RuntimeError` into an error result.
- One engine, sequential calls; no concurrent writer or other process (a bulk load by another process is q-cyp-003).
  Route timing (trial medians, drift) is abstracted to "a route holds SQL for this shape".
- Trust inventory: no `assume`, `admit` or `external_body`; vstd only.

## Product binding

[`binding.py`](binding.py), run through the fixture's `run_binding.py` (see the runbook). It drops and re-creates
namespaces I62B and I62C in `ivg-cov-20261118-a-iris` (from %SYS through `docker exec`), creates users `i62_all`,
`i62_part` (no SELECT on `rdf_edges`) and `i62_rev` with roles `i62r_*` and deletes them after. A Python transcription
of the spec functions above computes each expected outcome from inputs the harness sets or observes (clause flags from
the parser, the grants it made, the executor class it compiled, the labels it mapped, the environment, each path's own
answer). Latest receipt (iteration 66): `results/native_admission/20261118T051407Z-binding` (AGREES; 55 live cases, adding the
route alternation pair and the three blind-spot shadow cases below, the reviewer's top-k probe at unit level
(`topk_r1_n1`, `r1_n1_reproduced` true), setup's reset fed the observed `objectscript_deployed`; detection adds a planner
flag forced ordered, a route transcription without alternation and a changed observed answer, each caught). Iteration 62's receipt: `results/native_admission/20261118T021610Z-binding` (AGREES; 50 live cases, the real planner
over 16 queries, the real comparator over 2,116 inputs, F-0907's tie rule, the real `_try_native` warned set at unit
level; detection: a changed observed path, a comparator without value types and a dropped warned set are each
caught); prove `results/native_admission/20261118T021637Z-prove` (PASS 54) and 23 control receipts of the same run. Earlier receipts of the same day are kept: four unsuccessful binding runs the first two found harness errors, the
third found two real distinctions the transcription lacked (Exec's SQL anchor fails after a REVOKE; the write read
steps are declined by the width check), which were then added to the model, and the fourth a harness route-threshold
slip; an AGREES binding (020559Z) before the LIMIT soundness theorem was added; and a control run in which `limit-skips-spent-check` failed elsewhere (in the lemma rather than the theorem it serves), after which its expected functions were corrected.

Disclosed substitutions, each reachable in production: the executor class is recompiled at PLANVERSION 2 or deleted in
I62C (a namespace deployed by another package version, a partial deploy, or another process running setup while an
engine runs); a NativeRoute held on SQL is built by the real NativeRoute from synthetic timings; F-0907's SQL tie order
is supplied as a permutation at unit level (SQL is free to return ties in any order; on this fixture's data both paths
returned the same tie order). Iteration 66 adds two: the three `blind_spot_*` cases replace the decoded rows of the real
`_try_native`'s answer with a wrong one (no wrong native answer is known; the planner, shadow switch, `_shadow_compare`
and `compare` are real), and the route cases read the real route's `_trial` flag before each call as the timing premise
(it stayed in trial through all twelve calls; native timings about 1 ms, SQL about 1.6 ms).

Runtime sample for equal-answers#o01/#o02 (admitted reads, native engine with routing off vs `native_cypher=False`):
a property read, a LIMIT without ORDER BY and an ORDER BY with ties agreed in columns, values and Python types;
ORDER BY over `''` differed in order (bug-cyp-104); grouping `1`/`'1'`/`2`/`'2'` differed (bug-cyp-136). This is an
observation on five shapes, not a formal claim.

## Receipts kept as history (documented in iteration 64)

[`20261118T015505Z-control-read-step-keeps-write`](../../results/native_admission/20261118T015505Z-control-read-step-keeps-write/receipt.json)
(EXPECTED_FAIL in `theorem_read_step_of_write_runs_natively`) ran against an intermediate iteration-62 revision of
this model. That theorem and the control are not in the current `native_admission.rs` or `model.json`, so the receipt's
recorded inputs no longer match and nothing cites it (the census and `check_evidence` read only declared controls). It
is kept as evidence of that revision, not counted as a current control.

## Iteration 66 repairs (review-1)

| finding | model change | evidence |
|---|---|---|
| R1-N1 (bug-cyp-162) | `owner_equal` replaced by `fr013_equal`; two as-built witnesses, the blind-spot characterisation and the soundness theorem; controls `topk-plan-ordered`, `owner-drops-order-keys`, `ordered-compared-as-bag`, `plan-drops-order` | binding `topk_r1_n1`, `blind_spot_*` |
| R1-N2 | `call_routed` with the trial's path order; two theorems; control `trial-no-alternation` | binding `route_alternation_bug_cyp_104` (two answers in turn) and `route_alternation_paths_agree` (one answer) |
| R1-N3 | none: recorded as an open obligation (premises above) | source reading |
| R1-N4 | `merge_prefix_after_with`; control `merge-after-with-planned` | the planner domain declines a WITH part |
| R1-N5 | none: `reader`'s scope recorded (premises above) | source reading |
| R1-N7 | `setup(e, objectscript_deployed)`; `theorem_setup_resets_only_after_deploy`; control `setup-resets-unconditionally` | binding passes the observed flag |

