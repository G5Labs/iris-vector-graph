# Iteration 62 handoff — native Cypher admission, SQL fallback and shadow comparison, through `execute_cypher`

Builder: Opus 5.5 (high). Assignment: [ASSIGNMENT.txt](ASSIGNMENT.txt). Start commit `a24c04db`; product pin `3eaa79cf`, no
product file edited (check_consolidated item 1: ok). Fixture: the run's own `ivg-cov-20261118-a-iris` (127.0.0.1:36481),
namespaces `I62A` (exploration), `I62V` (setup timing only), `I62B` and `I62C` (the binding re-creates both). No
other container was touched. Scratch lives in `$G5_RUN_STATE/scratch/iteration-62/`. The STOP file was absent at every
check. No process was left running, and the binding's users and roles were deleted (checked in %SYS).

Commits on `consolidated_uplift`:
- `e443e7ee` predictions, frozen before the deciding code was read;
- `4ad7081d` model;
- `06cecedd` binding and links;
- `b3523adc` findings and ontology;
- `32f2c2b8` the LIMIT soundness theorem and re-runs;
- `ebdd0726` census;
- `1f6607ad` grading, runbook, stamp;
- this handoff.

## 1. Obligations recovered from tests (step 1)

The tests define the following obligations. Mocks supply the parts noted in each row, and anything learned from a test
is marked [test] in my predictions.

| test | obligation (test-derived) | what the mock supplies |
|---|---|---|
| `unit/test_253_native_gates.py` | the planner declines CREATE, SET, DELETE, MERGE, CALL, UNION and unknown functions; the gate reasons; default on; the environment or the engine turns it off | MagicMock connection; every cached gate answer is set by hand |
| `unit/test_253_native_declines_mapped_tables.py` | a mapped label anywhere in the query declines | `_table_mapping_cache` and `_run_native_plan` |
| `unit/test_253_native_executor_version.py` | a version mismatch keeps SQL; a missing method is remembered; a transient error is asked again; setup resets; every plan carries `v` | `classMethodValue` |
| `unit/test_253_shadow_compare.py`, `test_253_shadow_unlimited.py` | the comparator's rules; the unlimited rerun for LIMIT without order | rows given directly; `_execute_parsed_sql` |
| `unit/test_253_native_route.py`, `test_460_native_route_trial.py` | shadow runs both paths on every call; the route rules | clock and both paths |
| `integration/test_native_privileges.py` | a user lacking SELECT on `rdf_edges` gets `_native_privileges() False` | real IRIS; asserts the probe only, not which path answers |
| `e2e/test_253_executor_version_e2e.py` | the executor refuses another version; a planner version bump answers on SQL | monkeypatched `PLAN_VERSION` |
| `e2e/test_253_native_plumbing_e2e.py` | one fallback warning; `native_cypher` off; shadow raises on a difference | monkeypatched `plan_query` with debug ops |

Two notes on these tests:
- The plumbing plans carry no `v`, while `Exec.Run` refuses a family-A plan of another version. They are not family A,
  so they pass that check. Not run here.
- `test_embedded_no_data_and_native.py` concerns the Native API subset (`EmbeddedIRIS`), not native Cypher. It is not
  relevant to this family.

The gaps found against the tests:
- No test reaches a REVOKE under a running engine.
- No test reaches chained statements.
- No test reaches the read steps of writes.
- No test reaches the mismatch message's content beyond the parameters.

## 2. Predictions (step 2)

The builder's predictions are frozen in [PREDICTIONS-builder.md](PREDICTIONS-builder.md) (sha256 in the `.sha256`
file, commit `e443e7ee`). They were written before reading `_try_native`, `_execute_parsed`, `_shadow_compare`,
`plan_query`, `native_gate`, `native_shadow`, the engine options and `Exec.Run`. The master's file was read only after
that commit, and its sha256 matched. Both sets are graded in [PREDICTIONS-graded.md](PREDICTIONS-graded.md):

| set | predictions | supported | wrong | partial | unconfirmed |
|---|---:|---:|---:|---:|---:|
| builder | 24 | 17 | 1 | 5 | 1 |
| master | 15 | 9 | 0 | 5 | 1 |

The master has two wrong halves, inside partial rows A5 and A7.

Material predictions that were wrong or partial, and what they became:
- **Precedence of the process switch.**
  - Builder PA2 and master A7 predicted that `IVG_NATIVE_CYPHER=0` reaches every engine.
  - As built, an explicit `native_cypher=True` wins (bug-cyp-159).
- **Chained statements.**
  - Master A5 predicted that chained statements take the SQL path.
  - As built, each supported read statement runs natively (bug-cyp-160).
- **The read step of a write.**
  - Builder PA5 and master A4 had it partly right.
  - The owner's example, the read before a per-row MERGE, never runs natively: the translation-width check declines it.
  - A read statement chained after a write does run natively, and it sees that write's uncommitted change.
- **REVOKE under a running engine.**
  - Builder PA7 held only for label scans.
  - A property-lookup read fails inside Exec's SQL anchor and falls back to SQL.
- **Shadow.**
  - Builder PS1/PS2/PS4 and master C5: the mismatch names the plan, not the query (bug-cyp-161).
  - A raised SQL error becomes an error result, not a NativeMismatch.
  - The environment variable is read on every call, not when the engine is built.

## 3. The model (step 3): `models/native_admission`

**Files:**
- [native_admission.rs](../../../Verus_verification/models/native_admission/native_admission.rs);
- [NOTES.md](../../../Verus_verification/models/native_admission/NOTES.md), which has the transcription table, the
  premises and the trust inventory;
- [model.json](../../../Verus_verification/models/native_admission/model.json);
- [manifest.json](../../../Verus_verification/models/native_admission/manifest.json);
- family `C-native_admission`.

It is a new model, not an extension of `route_recheck`. The route's timing machine stays separate; only "shadow mode
skips the route" is modelled here.

The model derives, as spec functions of the deciding inputs (none of these decisions is an input):
- (a) **switch resolution**;
- (b) **admission**:
  - the planner's top-level declines and the SKIP/clause-kind decline;
  - the ordered and limited flags;
  - the gate order, with each answer's per-engine cache: setup resets the index and version answers and never the
    privilege answer, and a transient probe error is not remembered;
  - the mapped-label check;
  - the translation width and hidden-alias check;
- (c) **the executor outcome**:
  - a missing class;
  - a plan of another version;
  - an anchor that Exec finds through `%SQL.Statement` and that SQL privileges refuse;
  - any other fault;
  - the fallback, and the warned-reason set (type plus the first 160 characters, per engine);
- (d) **the comparator, the shadow branch and the reader**:
  - `native_shadow.compare` as written: columns; the LIMIT rule only when the plan is limited and not ordered; ordered
    row by row; multisets otherwise; a value's type is part of the key;
  - `_shadow_compare`'s branches;
  - `_execute_parsed` with and without shadow and a held route;
  - `execute_cypher`'s conversion of a plain RuntimeError into an error result.

**Proof:** **54 verified, 0 errors**, vstd only, no `assume`/`admit`/`external_body`. Receipt:
`results/native_admission/20261118T021637Z-prove`.

**Properties proved as built:**
- switch resolution; the per-engine switch;
- a native answer implies every gate held; any closed gate answers on SQL;
- the bulk session; the mapped label; the version and missing-class gates; the transient probe;
- a fresh engine is kept off when SELECT is missing;
- a REVOKE does not reach a running engine, even through setup, while a new engine sees it;
- no write is planned and no write runs natively: a write clause at the top level, in a chained part, in a UNION branch
  or in a `CALL { }`;
- CALL, UNION, chained and SKIP are declined;
- the write read steps are declined;
- a read part chained after a write is admitted;
- a native failure is answered by SQL;
- one warning per reason; the reason is the type plus 160 characters; the warned set is per engine;
- the shadow switches;
- shadow bypasses the route;
- shadow returns only compared answers;
- a difference raises and is never returned;
- the SQL-failure branches;
- a native failure in shadow mode is uncompared;
- `ordered` passes iff the answers are equal, for all sizes;
- type is part of the value (`1`, `'1'`, `1.0`, `true`);
- columns are checked first;
- a permutation passes when unordered;
- a multiset difference names a row;
- **the LIMIT rule is sound for all sizes** (`theorem_limit_pass_means_rows_of_full_answer`, through
  `lemma_fits_bounded`/`lemma_cnt_remove1`);
- with LIMIT, a different subset passes and an outside row raises; a count mismatch names no row;
- SKIP is never compared;
- the aggregate's order flag.

**Refuted (modeled as-built witnesses of owner promises):**

| owner promise | witness |
|---|---|
| query.native#o03: `IVG_NATIVE_CYPHER=0` turns off every engine | `theorem_explicit_true_beats_env_zero` |
| query.native.privileges#o01: never native without SELECT | running-engine label scan: `theorem_revoke_does_not_reach_running_engine` and `theorem_revoke_reaches_sql_anchor_only` |
| reads-only#o04: chained statements take SQL | `theorem_chained_part_runs_natively` |
| equal-answers#o05: the LIMIT rule as the comparator decides it | `theorem_partial_order_compared_in_order`: an ORDER BY with ties marks the plan ordered, so a pick the rule admits raises (F-0907) |
| query.shadow#o02: names the query | `theorem_shadow_difference_raises` |
| query.shadow#o03: a SQL failure is raised | `theorem_shadow_sql_failure` |

**Controls: 23, all EXPECTED_FAIL in their named functions.** Receipts are `results/native_admission/20261118T0216*-control-*`.

| group | controls |
|---|---|
| decisive gates and effects removed | `drop-bulk-gate`, `plan-admits-mutation`, `warn-every-time`, `shadow-returns-difference`, `shadow-sql-error-answered`, `key-without-type`, `limit-without-count`, `limit-skips-spent-check`, `failure-answers-empty`, `shadow-consults-route`, `mapped-label-ignored`, `version-gate-dropped`, `transient-remembered`, `drop-native-off-gate`, `key-whole-message`, `anchor-ignores-privileges`, `show-internal-alias`, `recheck-privileges` |
| owner policy or a proposed repair (show the as-built theorem distinguishes) | `env-wins`, `complete-order-flag`, `names-query`, `chained-part-keeps-chain`, `setup-resets-privileges` |

`limit-skips-spent-check` first ran FAIL_ELSEWHERE (it is caught in the lemma rather than the theorem it serves); its
expected functions were corrected, and that receipt is kept.

**Premises and limits:**
- `Query.shape_ok` (the planner's grammar below the declines), `Query.transactional`, `width_ok`, `hidden_alias` and
  `anchor` are declared, not derived.
- Each path's rows are provider inputs, so **native = SQL answer parity is not proved**. equal-answers#o01 and #o02
  hold formally only in shadow mode: a returned answer passed `compare`.
- One engine and sequential calls. No other process's bulk load (q-cyp-003). Route timing is abstracted to "a route
  holds SQL".

## 4. Runtime correspondence (step 4)

**Binding:** [binding.py](../../../Verus_verification/models/native_admission/binding.py), latest receipt
`results/native_admission/20261118T021610Z-binding`: **AGREES**, 34 s.
- **What it runs:** 50 live cases through the real engine; the real `plan_query` over 16 queries; the real
  `native_shadow.compare` over 2,116 inputs; F-0907's rule with the real planner flag; the real `_try_native` warned
  set at unit level.
- **Detection:** a changed observed path (`bulk_inside` flipped to native), a comparator with the value types removed
  and a dropped warned set are each caught.
- **How expectations are derived:** a transcription of the spec functions computes every expected outcome from inputs
  the harness sets or observes, never from the deciding code. Those inputs are:
  - the parser's clause flags;
  - the grants it made;
  - the executor class it compiled;
  - the labels it mapped;
  - the environment;
  - each path's own answer (a `native_cypher=False` engine; a native engine with routing off).
- **Earlier receipts kept as unsuccessful runs:** four DISAGREES runs.
  - Two were harness errors.
  - One found the two distinctions the model lacked: Exec's SQL anchor after a REVOKE, and the hidden-alias decline
    of the write read steps. Both were then modelled.
  - One was a route-threshold slip.

**Observed per obligation.** Every row's observed path, rows, types and warning counts are in the receipt's `live_cases`.

| obligation | binding cases (observed) |
|---|---|
| query.native#o01, o02, gates#o01 | `switch_argNone_envunset` native; `switch_argFalse_envunset` SQL; `switch_argNone_env1` native |
| query.native#o03 (refuted) | `switch_argTrue_env0` **native**; `switch_argNone_env0` SQL |
| gates#o03 | `bulk_before` native; `bulk_inside` SQL; `bulk_after` native |
| gates#o04 | `exec_v2_new_engine_gate` and `exec_missing_new_engine_gate`: SQL with one `native Cypher off … redeploy` warning; `exec_restored_cached_engine_stays_sql` SQL; `exec_restored_new_engine` and `exec_restored_after_setup` native |
| gates#o05 | `mapped_label` SQL with the outside table's row; `unmapped_label_same_engine` native |
| privileges#o01 (refuted), #o02, #o03 | `priv_i62_all` native; `priv_i62_part` (no SELECT on `rdf_edges`) SQL with rows; after `REVOKE SELECT ON rdf_props`, the running engine's `…_label_scan` **native** and `…_props_anchor` an error result after one fallback warning (`Cypher anchor SQLCODE -99`); `priv_rev_new_engine` an error result |
| reads-only#o01–#o03 | `write_set`, `union`, `call`, `skip`: SQL; planner domain 16/16 |
| reads-only#o04 (refuted) | `chained_parts`: parent declined, **2 native runs** |
| reads-only#o05 | `row_merge_prefix` and `count_create_step`: whole declined, step alias hidden, 0 native; `chained_write_then_read`: write part SQL, read part native, returned the row the uncommitted SET changed |
| fallback#o01, #o02 | `exec_v2_running_engine_falls_back` SQL with 1 warning; `exec_v2_same_reason_again` 0; `exec_missing_running_engine_new_reason` 1; unit warned set [1,1,2,2,3] |
| shadow#o01, #o02 (refuted), route#o03 | `shadow_eq_read` native, compared; `shadow_order_empty_string` NativeMismatch "row 0", names the plan and the parameters, **not the Cypher text**; `shadow_group_mixed_types` NativeMismatch "missing from native"; `shadow_limit_unordered` passes; `route_held_sql_no_shadow` routed SQL beside `route_held_sql_shadow` native; `shadow_records_no_route` 0 |
| shadow#o03 (refuted) | `priv_rev_running_engine_shadow_scan`: NativeMismatch "the SQL path failed where native answered" naming neither query nor parameters; `…_shadow_props`: an error result (native failed first) |
| shadow#o04 | `shadow_env_on` (variable set after the engine was built) raises; `shadow_env_off` answers |
| shadow#o05 | `exec_v2_shadow_native_failure`: SQL answer, no raise, 1 warning |
| equal-answers#o01/#o02 (runtime sample only) | native with routing off vs SQL: `eq_read`, `limit_unordered` and `order_ties` were equal in columns, values and Python types; `order_empty_string` differed in order (bug-cyp-104); `group_mixed_types` differed in values (bug-cyp-136) |

**Substitutions and injected faults, and why production can reach each:**
- **Exec recompiled at PLANVERSION 2, or deleted, in I62C.** Production reaches this through a namespace deployed by
  another package version (spec 253's 2026-10-21 incident), a partial deploy, or another process running setup while
  an engine runs.
- **A NativeRoute held on SQL.** It was built by the real NativeRoute from synthetic timings (as in `route_recheck`).
  It is the state after any trial SQL won.
- **The F-0907 SQL tie order, supplied as a permutation at unit level.** SQL may return ties in any order; the
  playbook observed it live. On this data the two paths agreed.
- **REVOKE under a running engine.** It is an ordinary DBA action on our own users.

## 5. Bindings and ontology (step 5)

**Crosswalk:** 50 rows in `crosswalk/decision-links.tsv`, family `C-native_admission`. They bind:
- the deciders: `IRISGraphEngine.__init__` 303-306, `_cypher_shadow`, `native_gate`, `_adjacency_indexed`,
  `_native_privileges`, `_native_executor_current`, `plan_query`, `_plan_chain`, `_plan_stages`,
  `CypherQuery.is_mutation`, `_names_mapped_label`, `_try_native`, `_shadow_compare`, `compare`, `_key`;
- the writers and producers: `bulk_load_session` 440-446, `initialize_schema` 2649-2650, `Exec.Run`, `Exec.Anchors`,
  `Exec.PlanVersion`, `_run_native_plan`, `plan_count_create`, `plan_row_merge`, `_fail`;
- the readers and consumers: `_execute_parsed` 2063-2082, `execute_cypher` 1904-1943, `_execute_cypher_write`,
  `NativeMismatch`;
- with `cites` or `observes` only: `_native_translation` and `_routed_sql`.

Every symbol and formal item resolves (check_consolidated item 7).

**Ontology metadata:** each of the eight blocks (query.native, gates, privileges, reads-only, equal-answers, fallback,
route, shadow) has a `Verus:` line naming the native_admission claims. Findings links were added for bug-cyp-159
(query.native), bug-cyp-160 (reads-only) and bug-cyp-161 (shadow).

**Ontology wording corrected (evidence shows the statement was factually wrong):**

1. **query.compiled.deploy-discards (governed text).**
   - The old text said "Nothing else removes them, so a namespace gains one class per distinct shape until the next
     deploy".
   - It now says: "Otherwise a class is removed only when a build of its shape fails to compile, and the shape's record
     stays with the error; so a namespace gains at most one class per distinct shape until the next deploy."
   - **Confirmed** (iteration-61 report 5.2) by source (`Gen.cls:214` `$System.OBJ.Delete(tCls)`) and live in I62C.
     The compiled class `IVGC.P865046810` existed before; after a stale-stamp rebuild failed through the product's
     `breaktest` hook it was gone, its `^IVG.CypherCompiled` entry kept the compile error, and the read was answered by
     the interpreter ([probe](probes/deploy_discards_probe2.py),
     [observation](probes/deploy_discards-observed-20261118T0206Z.json)).
   - The reason is recorded in the block's metadata. The block hash changed, and the block was regraded (#o03 stays
     partial: no as-built model of a failed build).
2. **query.native.gates (metadata).**
   - The old text said "caches the index, privilege and version answers until setup runs again".
   - It now says that setup resets the index and version answers but never the privilege answer, and that a transient
     version-probe error is not remembered (`engine.py:318`, `schema.py:2649-2650`).

**Left unchanged on purpose:**
- reads-only bullet 1's example, "such as the MATCH before a per-row MERGE". It is a permission ("may"), and it never
  happens as built; the gap is recorded in the census.
- The lead claims refuted above. Each is graded refuted and has a finding.

## 6. Findings (step 6)

**New, all Low and Open, each E2E-reproduced and modeled, in `bugs_issues.md` and `crosswalk/findings.tsv`:**

| finding | trigger and effect |
|---|---|
| **bug-cyp-159** | `IVG_NATIVE_CYPHER=0` does not turn off an engine built with `native_cypher=True` |
| **bug-cyp-160** | A chained query's read statements are answered natively one by one (also inside a write's transaction, reading its uncommitted rows) |
| **bug-cyp-161** | The shadow mismatch names the native plan, not the query; a SQL failure is named without query or parameters, or comes back as an ordinary error result (the RuntimeError branch is modeled only) |

**Linked, not duplicated:**
- bug-cyp-104 (reproduced again, live sample and shadow raise) and bug-cyp-136 (same).
- bug-cyp-002: not exercised.
- F-0907: the decision is reproduced with the real planner flag and the real comparator at unit level. No live raise:
  the tie orders agreed on this data. Its review record still says "not reproduced in this audit"; I did not edit
  that audit file.
- F-0908 and HD-0901: the running-engine REVOKE is now modeled and observed through the engine, and is
  anchor-dependent.
- q-cyp-002 and HD-0902: the as-built behaviour is proved (`theorem_shadow_native_failure_uncompared`); the policy is
  still open.
- q-cyp-003: untouched.

check_findings: no problems.

## 7. Census (step 7)

`tools/census.py` **PASS**; regenerating gives identical bytes. 28 obligations regraded across 10 blocks (iteration 62).

| obligation | before | after |
|---|---|---|
| query.native#o01 | absent, none | **full, proved (full)** |
| query.native#o02 | absent, none | **full, proved (full)** |
| query.native#o03 | absent, none | **full, refuted (full)** |
| query.native.gates#o01 | absent, none | **full, proved (full)** |
| query.native.gates#o03 | absent, none | **full, proved (full)** |
| query.native.gates#o04 | absent, none | **full, proved (full)** |
| query.native.gates#o05 | absent, none | **full, proved (full)** |
| query.native.privileges#o01 | partial, none | **full, refuted (full)** |
| query.native.privileges#o02 | full, refuted (narrowed) | full, refuted (narrowed); now also through the engine |
| query.native.privileges#o03 | partial, proved (narrowed) | partial, proved (narrowed); resource revocation not modeled |
| query.native.reads-only#o01 | absent, none | **full, proved (full)** |
| query.native.reads-only#o02 | absent, none | **full, proved (full)** |
| query.native.reads-only#o03 | absent, none | **full, proved (full)** |
| query.native.reads-only#o04 | absent, none | **full, refuted (full)** |
| query.native.reads-only#o05 | partial, proved (narrowed) | **full, proved (narrowed)** |
| query.native.equal-answers#o01 | absent, none | **partial, proved (narrowed: shadow mode)** |
| query.native.equal-answers#o02 | absent, none | **partial, proved (narrowed: shadow mode)** |
| query.native.equal-answers#o05 | absent, none | **full, refuted (narrowed)** |
| query.native.fallback#o01 | partial, proved (narrowed) | **full, proved (full)** |
| query.native.fallback#o02 | absent, none | **full, proved (full)** |
| query.native.route#o03 | absent, none | **full, proved (full)** |
| query.shadow#o01 | partial, proved (narrowed) | **full, proved (full)** |
| query.shadow#o02 | partial, proved (narrowed) | **full, refuted (full)** |
| query.shadow#o03 | partial, proved (narrowed) | **full, refuted (narrowed)** |
| query.shadow#o04 | absent, none | **full, proved (full)** |
| query.shadow#o05 | partial, none | **full, proved (full)** |
| query.compiled.deploy-discards#o03 | partial, none | partial, none (statement reworded with the owner) |
| access.iris_boundary#o05 | absent, none | **partial, proved (narrowed)**: one class method, through the engine |

Per block, full/total before → after:

| block | before | after |
|---|---|---|
| query.native | 0/3 | **3/3** |
| query.native.gates | 1/5 | **5/5** |
| query.native.privileges | 1/3 | 2/3 |
| query.native.reads-only | 0/5 | **5/5** |
| query.native.equal-answers | 2/5 | 3/5 |
| query.native.fallback | 0/2 | **2/2** |
| query.native.route | 3/15 | 4/15 |
| query.shadow | 0/5 | **5/5** |
| query.compiled.deploy-discards | 1/3 | 1/3 |
| access.iris_boundary | 2/6 | 2/6 (partial 2 → 3) |

Per page and pooled:

| scope | blocks | full | partial | absent | total | full/total | proved, full scope | proved | refuted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| architecture/query-execution, before | 17 | 15 | 24 | 31 | 70 | 21.4% | 6 | 17 | 9 |
| architecture/query-execution, after | 17 | **37** | 19 | 14 | 70 | **52.9%** | 21 | 30 | 15 |
| concepts/access, before | 13 | 12 | 5 | 27 | 44 | 27.3% | 0 | 11 | 6 |
| concepts/access, after | 13 | 12 | 6 | 26 | 44 | 27.3% | 0 | 12 | 6 |
| pooled, enumerated scope, before | 119 | 224 | 123 | 188 | 535 | 41.9% | 101 | 265 | 38 |
| pooled, enumerated scope, after | 119 | **246** | 119 | 170 | 535 | **46.0%** | 116 | 279 | 44 |

The denominator is unchanged (535). This is change on retained obligations, not a change in scope.

- **Gained full (22):**
  - query.native#o01–#o03;
  - gates#o01, #o03, #o04, #o05;
  - privileges#o01;
  - reads-only#o01–#o05;
  - equal-answers#o05;
  - fallback#o01, #o02;
  - route#o03;
  - shadow#o01–#o05.
- **Of those, refuted (6):**
  - query.native#o03;
  - privileges#o01;
  - reads-only#o04;
  - equal-answers#o05;
  - shadow#o02, #o03.
- **Withdrawn: none.** No grade went down.
- **Parents:** query.native's three obligations are now its own, modelled directly. The iteration-61 residual ("every
  child holds while the default resolves to off") is closed by `theorem_switch_resolution`.
- The whole-foundation percentage is still unmeasured (287 blocks not started).

**Judgement calls a reviewer should challenge:**
- **reads-only#o05 graded full and proved (narrowed).** The routing is as built. The visibility composes the
  reviewed-design `proofs-d1d` theorem (another connection's open transaction) with a live same-transaction
  observation.
- **privileges#o01 graded refuted on the running-engine history.** That history is the owner's own working
  assumption, and the fresh-engine case is proved.
- **equal-answers#o05 read as "the rule as the comparator decides it".** Native answers themselves are not shown to
  satisfy the rule.
- **shadow#o03's RuntimeError branch.** Its product reachability behind an admitted plan was not constructed live; a
  family-B read whose SQL route raises is the plausible path.

## 8. Member reach

`tools/member_reach.py` (active behavioural bindings) gives **774 → 798** of 4,130. Member lists are in
[member-delta.json](member-delta.json).

| measure | count |
|---|---:|
| gained an active binding | 24 |
| newly reached by a crosswalk locator | 23 |
| overlap | 22 |
| distinct | 25 |
| losses | 0 |

- `_cypher_shadow` and `_shadow_compare` were already cited ("decision not modeled", result_decoders) and now carry
  active bindings.
- `_native_translation` is newly reached as a citation only.
- The iteration-60 union instrument (`recount.py`) is not on this host. "Newly reached" counts only the crosswalk's
  resolvable locators (920 → 943 members), not inline model citations.

## 9. Gates (raw outputs in [gates/](gates/); `*.before.txt` were run on a clean worktree of `a24c04db`)

| gate | start (`a24c04db`) | end |
|---|---|---|
| `tools/census.py` | exit 0 | **exit 0**, PASS, deterministic |
| `tools/check_evidence.py` | FRESH | **FRESH** |
| `tools/check_consolidated.py` | PASS | **PASS** |
| `check_ontology.py .g5/ontology` | 0 issues, 17 warnings | 0 issues, 17 warnings |
| `check_findings.py` | No problems found | No problems found |

**Correspondence stamp:**
- Against the iteration-61 stamp, the gate reported STALE_ALL ([check](gates/correspondence_check_vs_61.json)). The
  only changes it listed were this batch's: the new model's `.rs`/`model.json`/`binding.py`, `decision-links.tsv` and
  `families.tsv`. No product file and no other model changed.
- This is the gate reopening every binding when a new writer is registered, as designed.
- Every changed input has a fresh receipt from this host's toolchain (the same `VERUS_BIN` as the iteration-61 stamp).
  So I captured [correspondence-inputs.json](correspondence-inputs.json), which checks REUSABLE_INPUTS.
- The master may prefer to recapture at integration.

## 10. Limitations

- No independent review of this batch.
- Native = SQL answer parity over the admitted language is not proved, by design of the assignment. The five-shape
  runtime sample is an observation.
- Not run live:
  - an undeclared index (gates#o02 stays F-0906 in the reviewed crate);
  - a transient version-probe error (model and unit test only);
  - a SQL RuntimeError behind an admitted plan in shadow mode;
  - F-0907's tie permutation (unit level only);
  - revoking the database resource or `%Native_ClassExecution`;
  - another process's bulk load.
- `Query.shape_ok` abstracts the planner's grammar. The 16-query planner domain checks the declared value against the
  real planner, not every shape.
- Route timing (route#o05–#o08, #o12, #o14) is out of scope and untouched.

## 11. Residual work in this family and recommendation

**Residual, by consequence:**
1. **Native = SQL parity on the admitted grammar** (equal-answers#o01–#o04). Transcribe Exec's property, type and
   sort transport for family A over a bounded value domain. Then prove (or refute) column, value and order equality
   against the translator's decoders; bug-cyp-104, -136 and -002 are the known witnesses.
2. **The planner's grammar.** Turn `shape_ok` into a derived predicate over the `_plan_chain` checks: anchors, cycles,
   variable-length uniqueness, aggregates.
3. **The policy decisions**, which belong to the owner: q-cyp-002/HD-0902 (raise in shadow on a native failure),
   bug-cyp-159/-160/-161 (narrow the owner or change the code), and HD-0901 (whether a REVOKE should reach running
   engines).
4. **The route's timing rules** (route#o05–#o08, #o12, #o14), cheap to add to `route_recheck`.

**Recommendation for the next material gap: erasure across stores** (iteration-61 queue item 1).
- It remains the lowest-covered privacy-material family (6/47 full, 33 absent). Its roles are concentrated in
  `Eraser.cls` and the store layer.
- This family is now 37/70 full on its page, and its largest remaining gap (answer parity) is a deep, separate
  campaign rather than another admission variant.
- After erasure, the API-key gate (item 2).
