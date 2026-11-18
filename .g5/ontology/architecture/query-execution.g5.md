# Cypher execution

Follow a query through the SQL and native paths, from admission and routing to compilation or fallback. For the meaning of the query and its results, see [Cypher](../features/cypher.g5.md).

## Definitions

- **Cypher query**: an openCypher text given to `execute_cypher` or to a server route. A **write** holds `CREATE`, `MERGE`, `SET`, `REMOVE`, `DELETE` or `FOREACH` anywhere in it; any other query is a **read**.
- **SQL path**: translating a query into SQL over the graph tables and running that SQL.
- **Native executor**: code inside IRIS that answers a supported read by walking the adjacency index and reading property rows directly, without SQL joins.
- **Plan**: the description of one read that Python hands the native executor. A **plan shape** is a plan without its parameter values: its hops with their types and directions, each node's labels, which properties it checks and how, and what it returns and groups.
- **Interpreter**: the native executor's general code, which reads the plan step by step as it walks.
- **Compiled plan**: the walk for one plan shape, written out as a class of its own and compiled in the namespace while IVG runs.
- **Shadow mode**: a checking mode that answers a native read on both paths and compares the answers.
- **Deploy**: installing IVG's ObjectScript classes into a namespace, as setup (`initialize_schema`) does.
- **TCK**: the openCypher Technology Compatibility Kit, the upstream conformance test suite.

## When does Cypher use SQL or the native executor?

<a id="query.paths"></a>
[D · query.paths]

IVG answers each Cypher query on one of two paths. The SQL path answers every query, including every write; the native executor answers only the reads it fully supports, and the SQL path is the reference it is held to.

- Python plans a native read and IRIS runs it; the native executor never parses Cypher.
- A query the native executor does not support takes the SQL path unchanged.

## Check whether a read can run natively

<a id="query.native"></a>
[D · query.native]

The native executor is on by default wherever the adjacency index is declared. One engine turns it off with `native_cypher=False`, and every engine in a process with `IVG_NATIVE_CYPHER=0`.

- Working assumption: Prefer closing native admission during index-bypassing load; a cache/probe that misses that interval cannot justify current-index reliance.

<a id="query.native.gates"></a>
[I · query.native.gates]

A read runs natively only when all of these hold; otherwise the SQL path answers it:

- The native executor is on for this engine.
- The adjacency index is declared on the edge and label tables.
- The engine is not inside its own bulk load session.
- The caller may read the graph tables (see [privileges](#query.native.privileges)).
- The deployed executor reads the plan format this package writes.
- No label in the query is mapped to an outside SQL table, since the native executor reads only the graph tables.

<a id="query.native.privileges"></a>
[D · query.native.privileges]

A caller without SQL `SELECT` on the node, label, property and edge tables gets the SQL path, never the native one. SQL table privileges keep deciding what a caller can read, even though native reads do not pass through SQL.

- Working assumption: Split the question. (1) A SQL REVOKE is not guaranteed to reach running engines' native reads. To cut native access, revoke the database resource or %Native_ClassExecution, or start new engines. Treat FR-011's executor-side check as an unimplemented spec requirement (F-0908) whose amendment is the maintainer's call. (2) For the route capability, keep FR-003: native reads require the index to be declared at the time of the read. Model an out-of-band drop under running engines as a premise violation ('the index is not dropped while engines run'), not a supported transition, unless Run checks Indexed().

<a id="query.native.reads-only"></a>
[I · query.native.reads-only]

No write runs on the native executor. A query with a write clause anywhere, a procedure call, a `UNION` or chained statements takes the SQL path.

- A read step inside a write, such as the `MATCH` before a per-row `MERGE`, may still run natively; it then sees the write's own uncommitted changes.

<a id="query.native.equal-answers"></a>
[I · query.native.equal-answers]

A native answer must equal the SQL path's answer:

- The same column names, values and value types; `1` and `'1'` are different answers.
- The same rows in the same order where the query orders them completely, and the same rows in any order otherwise.
- Where `LIMIT` or `SKIP` keeps rows the query does not fully order, the same number of rows, each a row of the SQL answer without the limit.

<a id="query.native.sql-first"></a>
[D · query.native.sql-first]

A defect found on the SQL path while building the native executor is fixed on the SQL path first, and the native executor copies the fixed behavior. Both paths preserve the stored node value types described in [values](../features/cypher.g5.md#query.values), and both retain the documented comparison and sorting limits in [conformance](../features/cypher.g5.md#query.conformance).

<a id="query.native.fallback"></a>
[I · query.native.fallback]

If the native executor fails for any reason, the SQL path answers the query instead. The engine logs a warning once per distinct reason.

<a id="query.native.route"></a>
[D · query.native.route]

For a read both paths can answer, the engine may send later runs of the same query shape to whichever path measured faster. It measures the paths again after 1,000 calls on the held path by default, and sooner after sustained timing drift; shadow mode bypasses this routing.

- A trial first warms native and takes two native timings. If their median reaches `small_ms`, SQL is not tried; otherwise SQL is warmed and the paths are timed in turn, up to five timings each by default.
- The held path keeps a near tie: the other path wins only when its median is strictly more than the configured margin faster (20% by default). A timed SQL run slower than four times native's slowest timing ends the trial on native.
- Only calls on the held path advance its recheck counter. The threshold call resets the trial; the next call starts with native again, even if SQL had held the shape. A SQL failure assigns the shape to native permanently for that route object, so later calls do not restart a trial.
- By default drift starts a trial after at least 50 held calls when the median of the last 20 calls exceeds twice the held path's trial median. Recheck and drift may each be disabled; route eviction or a new engine creates a new trial.

This routing relies on [equal answers](#query.native.equal-answers); the timing rules alone do not prove that equality.

- Working assumption: yes; today they run the translated SQL themselves.

## Compare both executors in shadow mode

<a id="query.shadow"></a>
[I · query.shadow]

In shadow mode every read the native executor answers also runs on the SQL path. A difference, or a SQL failure where the native executor answered, is raised as an error naming the query, its parameters and the first differing row; it is never returned as the answer.

- One engine turns it on with `cypher_shadow = True`, and every engine with `IVG_CYPHER_SHADOW=1`.

- Working assumption: Keep SQL fallback as the current shadow behavior; fail-fast diagnostic mode remains an unratified alternative.
- Working assumption: Keep ordinary SQL fallback. In shadow validation, record a native exception as an unsuccessful comparison: raise in shadow mode, or count failures and report them at the end of the run. Require a clean comparison (not a fallback) before claiming parity. The FR-010 default flip and the 3896/3896 figure establish only that no compared answer differed.

## Compile a read plan and decide when to reuse it

<a id="query.compiled"></a>
[D · query.compiled]

The native executor writes the walk of each plan shape that has at least one hop as a class of its own, and compiles it in the namespace while IVG runs. Later reads of that shape run the class instead of the interpreter.

<a id="query.compiled.equal-answers"></a>
[I · query.compiled.equal-answers]

A compiled plan answers exactly as the interpreter does: the same rows in the same order, including the order among ties. Both answer as the SQL path does.

<a id="query.compiled.modes"></a>
[D · query.compiled.modes]

A mode decides when shapes compile. The namespace sets a default, and one process can override it.

- `job`, the default: a new shape is answered by the interpreter while a background job compiles it.
- `sync`: a new shape is compiled before its first run.
- `off`: nothing is compiled. Answers stay the same; only speed changes.
- A site under change control, or one whose database may not be written, uses `off`.

<a id="query.compiled.never-stale"></a>
[I · query.compiled.never-stale]

A compiled plan runs only for the shape it was written for, and only while the executor, the code generator and the property table are the builds it was written against. Otherwise the read is interpreted and the shape is built again.

<a id="query.compiled.deploy-discards"></a>
[D · query.compiled.deploy-discards]

A deploy that installs IVG's classes deletes every compiled plan and its record, and so does an explicit drop of all compiled plans. Otherwise a class is removed only when a build of its shape fails to compile, and the shape's record stays with the error; so a namespace gains at most one class per distinct shape until the next deploy.

<a id="query.compiled.fallback"></a>
[I · query.compiled.fallback]

The interpreter answers any shape that is not compiled yet, is being compiled, failed to compile, or cannot be recorded by this process. Compiling must never make a read fail.

- A failed compile is logged once and not tried again until the compile stamp changes, which a deploy or a change of the property registry does.
- A plan with no hop is always interpreted.

- Working assumption: Treat a run-time failure of a compiled entry as a fallback outcome: quarantine the entry for that plan generation (as a failed build already is), let the interpreter answer, and retry only after invalidation (a new stamp, DropAll or a deploy). SQL fallback for every later read (as built) is a correct-answer but degraded baseline that violates ADR-0014's 'answers exactly as the interpreter'.

<a id="query.compiled.integrity"></a>
[D · query.compiled.integrity]

A compiled class runs only for the shape it was written for, and only code the generator itself wrote for that shape is compiled. No user, whether able to write the database or only to run Cypher reads, can make another user's read run other code.

## Metadata

### query.paths

- agent
- architecture-decision, user-facing-behavior

Sources: [CONTEXT.md, Query execution](../../../CONTEXT.md#L224-L232), [spec 253, decisions of 2026-10-20 and FR-001](../../../specs/253-native-cypher-executor/spec.md#L14-L18), [USER_GUIDE, Where a query runs](../../../docs/USER_GUIDE.md#L350-L368), [`_execute_parsed`](../../../iris_vector_graph/_engine/query.py#L2032-L2082). Note: USER_GUIDE says "the one known difference between the paths is listed in Known issues", and no such entry is named there.

Provenance: spec 253 is still "Draft" and its "Decided 2026-10-20" lines name no decider, so under the uplift's authority rule ([sources](../../uplift/ivg-verus-initial/sources.md)) the block is `agent` (review round 3 R3-reader M16).

### query.native

- uncertain
- Verus: [native_admission](../../Verus_verification/models/native_admission/NOTES.md) (as built, iteration 62) `theorem_switch_resolution`, `theorem_per_engine_switch`; `theorem_explicit_true_beats_env_zero`: `IVG_NATIVE_CYPHER=0` does not reach an engine built with `native_cypher=True`.
- agent
- architecture-decision, operations
- Children: [gates](#query.native.gates), [privileges](#query.native.privileges), [Should a bulk load by another process close the native query path while indexes lag the rows?](../../Verus_verification/open_questions.md#q-cyp-003), [reads only](#query.native.reads-only), [equal answers](#query.native.equal-answers), [SQL first](#query.native.sql-first), [fallback](#query.native.fallback), [route](#query.native.route).

Sources: [spec 253 decisions and FR-005, FR-010](../../../specs/253-native-cypher-executor/spec.md#L14-L18), [engine options](../../../iris_vector_graph/engine.py#L290-L317). The default was to flip only after a shadow run matched the SQL path on the full TCK and the 40 SNB queries; [TCK.md](../../../docs/dev/TCK.md#L215-L232) records the shadow run.


Findings: [IVG_NATIVE_CYPHER=0 does not turn off an engine built with native_cypher=True](../../Verus_verification/bugs_issues.md#bug-cyp-159)

Provenance: spec 253 is still "Draft" and its "Decided 2026-10-20" lines name no decider, so under the uplift's authority rule ([sources](../../uplift/ivg-verus-initial/sources.md)) the block is `agent` (review round 3 R3-reader M16).

Open questions: [Should a bulk load by another process close the native query path while indexes lag the rows?](../../Verus_verification/open_questions.md#q-cyp-003)

### query.native.gates

- Verus: [native_admission](../../Verus_verification/models/native_admission/NOTES.md) (as built, iteration 62) [`gate`](../../Verus_verification/models/native_admission/native_admission.rs) with its per-engine caches, `theorem_admitted_only_through_every_gate`, `theorem_closed_gate_answers_sql`, `theorem_bulk_session_keeps_sql`, `theorem_mapped_label_keeps_sql`, `theorem_version_gate`, `theorem_missing_class_gate`, `theorem_transient_probe_not_remembered`; the index gate reads only `idx_edges_adj` (F-0906 in `proofs-d1d`).
- agent
- operations, data-integrity
- test-coverage
- Expands: [Native executor](#query.native).

Sources: [spec 253 FR-003, FR-005, FR-011, FR-014](../../../specs/253-native-cypher-executor/spec.md#L98-L140), [`native_gate`](../../../iris_vector_graph/cypher/native_plan.py#L524-L536), [plan version check](../../../iris_src/src/Graph/KG/Cypher/Exec.cls#L13-L41), [mapped labels decline](../../../iris_vector_graph/_engine/query.py#L2162-L2184). Live: [`test_253_executor_version_e2e.py`](../../../tests/e2e/test_253_executor_version_e2e.py); the other gates are covered by mocked unit tests ([`test_253_native_gates.py`](../../../tests/unit/test_253_native_gates.py)). The engine caches the index, privilege and version answers per engine; setup (`initialize_schema`) resets the index and version answers but never the privilege answer, and a version probe that fails for another reason than a missing method or class is not remembered (corrected in iteration 62 from "until setup runs again": `_native_privileges_cached` is never reset, `engine.py:318`, `schema.py:2649-2650`; [native_admission](../../Verus_verification/models/native_admission/NOTES.md) `theorem_revoke_does_not_reach_running_engine`).

### query.native.privileges

- uncertain
- Verus: [native_admission](../../Verus_verification/models/native_admission/NOTES.md) (as built, iteration 62) `theorem_missing_select_keeps_sql`, `theorem_revoke_does_not_reach_running_engine` (the per-engine answer survives setup), `theorem_revoke_reaches_sql_anchor_only` (a REVOKE fails a running engine's property-lookup read, which falls back to SQL, and leaves its label scans native).
- agent
- security
- Expands: [Native executor](#query.native).

Sources: [spec 253 FR-011, decided 2026-10-20](../../../specs/253-native-cypher-executor/spec.md#L124-L127), [`_native_privileges`](../../../iris_vector_graph/engine.py#L559-L586). The check is a SELECT probe per engine rather than the per-process `CheckPrivilege` the FR names.

Provenance: spec 253 is still "Draft" and its "Decided 2026-10-20" lines name no decider, so under the uplift's authority rule ([sources](../../uplift/ivg-verus-initial/sources.md)) the block is `agent` (review round 3 R3-reader M16).

Open questions: [Should a running engine notice a revoked table right or a dropped adjacency index?](../../Verus_verification/open_questions.md#HD-0901)

### query.native.reads-only

- Verus: [native_admission](../../Verus_verification/models/native_admission/NOTES.md) (as built, iteration 62) `theorem_no_write_runs_natively`, `theorem_call_union_chained_skip_declined`, `theorem_chained_part_runs_natively`, `theorem_write_read_steps` (the per-row MERGE prefix and the count step are declined by the translation-width check), `theorem_read_part_of_chained_write_runs_natively`.
- agent
- data-integrity, architecture-decision
- Expands: [Native executor](#query.native).

Sources: [spec 253 decisions and FR-001, edge cases](../../../specs/253-native-cypher-executor/spec.md#L83-L99), [`plan_query`](../../../iris_vector_graph/cypher/native_plan.py#L50-L87), [`_try_native` declines a transactional translation](../../../iris_vector_graph/_engine/query.py#L2118-L2160). Three independent checks keep writes off the native path; the planner unit test lists the declined write clauses.


Findings: [A chained query's read statements are answered natively one by one](../../Verus_verification/bugs_issues.md#bug-cyp-160)

Provenance: spec 253 is still "Draft" and its "Decided 2026-10-20" lines name no decider, so under the uplift's authority rule ([sources](../../uplift/ivg-verus-initial/sources.md)) the block is `agent` (review round 3 R3-reader M16).

### query.native.equal-answers

- Verus: [native_admission](../../Verus_verification/models/native_admission/NOTES.md) (as built, iteration 62) the comparator only: `theorem_ordered_pass_iff_equal`, `theorem_type_is_part_of_the_value`, `theorem_limit_other_rows_pass`, `theorem_limit_outside_row_raises`, `theorem_limit_count_names_no_row`, `theorem_partial_order_compared_in_order` (an ORDER BY with ties is compared in order, so the LIMIT rule applies only without ORDER BY: F-0907). Native = SQL answers is not proved; the binding records a runtime sample.
- agent
- user-facing-behavior, data-integrity
- test-coverage
- Expands: [Native executor](#query.native).

Sources: [spec 253 FR-002, FR-012 (equality decided 2026-10-20), FR-013](../../../specs/253-native-cypher-executor/spec.md#L100-L137), [`native_shadow.compare`](../../../iris_vector_graph/cypher/native_shadow.py#L29-L69). Live: the family A and B end-to-end tests run in shadow mode ([`test_253_family_b_e2e.py`](../../../tests/e2e/test_253_family_b_e2e.py)). Model note: equality assumes the indexes are current ([Should a bulk load by another process close the native query path while indexes lag the rows?](../../Verus_verification/open_questions.md#q-cyp-003)).

Findings: [The native interpreter tells used relationships apart by CRC-32, so a hash collision drops a legitimate match](../../Verus_verification/bugs_issues.md#bug-cyp-002); [ORDER BY sorts an empty-string property with the nulls on the native executor and first on the SQL path](../../Verus_verification/bugs_issues.md#bug-cyp-104); [The SQL path and the native executor group the same stored values differently](../../Verus_verification/bugs_issues.md#bug-cyp-136)

Provenance: spec 253 is still "Draft" and its "Decided 2026-10-20" lines name no decider, so under the uplift's authority rule ([sources](../../uplift/ivg-verus-initial/sources.md)) the block is `agent` (review round 3 R3-reader M16).

### query.native.sql-first

- agent
- architecture-decision
- Expands: [Native executor](#query.native).

Sources: [spec 253 FR-012](../../../specs/253-native-cypher-executor/spec.md#L129-L134).

Provenance: spec 253 is still "Draft" and its "Decided 2026-10-20" lines name no decider, so under the uplift's authority rule ([sources](../../uplift/ivg-verus-initial/sources.md)) the block is `agent` (review round 3 R3-reader M16).

### query.native.fallback

- Verus: [native_admission](../../Verus_verification/models/native_admission/NOTES.md) (as built, iteration 62) `theorem_native_failure_answered_by_sql`, `theorem_one_warning_per_reason`, `theorem_reason_is_type_and_160_chars` (a reason is the exception type and the first 160 message characters), `theorem_warned_set_is_per_engine`.
- agent
- user-facing-behavior, operations
- Expands: [Native executor](#query.native).

Sources: [spec 253 US4 and FR-007](../../../specs/253-native-cypher-executor/spec.md#L71-L81), [`_try_native`](../../../iris_vector_graph/_engine/query.py#L2144-L2152), [`Exec.Run`](../../../iris_src/src/Graph/KG/Cypher/Exec.cls#L32-L52).

### query.native.route


- uncertain
- Playbook: [NAT-T7](../../../experiment/playbook-completion/ontology/09-native-executor.md)
- Verus: [route_recheck](../../Verus_verification/models/route_recheck/NOTES.md), as-built held-call recheck/reset and permanent SQL-failure rules; trial medians, drift selection and SQL/native answer equality remain unmodeled.
- Verus: [native_admission](../../Verus_verification/models/native_admission/NOTES.md) `theorem_shadow_bypasses_route` (shadow mode neither consults nor records the route; iteration 62).
- agent
- architecture-decision
- Expands: [Native executor](#query.native).

Sources: [`native_route.py`](../../../iris_vector_graph/cypher/native_route.py#L1-L16), [`_execute_parsed`](../../../iris_vector_graph/_engine/query.py#L2063-L2104). Shadow mode skips the route.

Open questions: [Should the second HTTP app's Cypher endpoints (`/api/cypher` and GraphQL `executeCypher`) answer through the engine, as the documented server and the Bolt listener do?](../../Verus_verification/open_questions.md#query.routes)

State machines: [route recheck](../../Verus_verification/models/route_recheck/manifest.json)

### query.shadow

- uncertain
- Verus: [native_admission](../../Verus_verification/models/native_admission/NOTES.md) (as built, iteration 62) `theorem_shadow_switches`, `theorem_shadow_returns_only_compared`, `theorem_shadow_difference_raises` (names the plan and parameters, not the Cypher text), `theorem_shadow_sql_failure`, `theorem_shadow_native_failure_uncompared`.
- agent
- data-integrity, operations
- test-coverage
- Children: [In shadow mode, should a native failure be raised instead of answered by SQL?](../../Verus_verification/open_questions.md#q-cyp-002).

Sources: [CONTEXT.md, Shadow mode](../../../CONTEXT.md#L234-L236), [spec 253 FR-006](../../../specs/253-native-cypher-executor/spec.md#L107-L108), [`_shadow_compare`](../../../iris_vector_graph/_engine/query.py#L2226-L2249), [TCK.md, how the native path is held to the SQL path](../../../docs/dev/TCK.md#L258-L271). Shadow mode compares native with SQL only; compiled against interpreted is checked by the compiled-plan tests.

Open questions: [Should shadow mode fail when the native path raises an error?](../../Verus_verification/open_questions.md#HD-0902), [In shadow mode, should a native failure be raised instead of answered by SQL?](../../Verus_verification/open_questions.md#q-cyp-002)

Iteration 58 (W62 D8, held within a narrower scope; observed only): with `IVG_CYPHER_SHADOW=1`, two native-accepted reads answered the same rows and types at `execute_cypher` and through Bolt under both IRIS drivers, with one comparison and no mismatch; their `ORDER BY` forms are not native-planned ([W62 predictions and results](../../uplift/consolidated/iteration-58/w62-PAIRS.md)).

Findings: [Shadow mode's mismatch names the native plan, not the query, and a SQL failure is named without the query or reported as an ordinary error](../../Verus_verification/bugs_issues.md#bug-cyp-161)


### query.compiled

- agent
- architecture-decision, operations
- Children: [equal answers](#query.compiled.equal-answers), [modes](#query.compiled.modes), [never stale](#query.compiled.never-stale), [deploy discards](#query.compiled.deploy-discards), [fallback](#query.compiled.fallback), [integrity](#query.compiled.integrity).

Sources: [ADR-0014](../../../docs/adr/0014-native-plans-are-compiled-to-classes-at-run-time.md#L10-L23), [CONTEXT.md, Plan shape and Compiled plan](../../../CONTEXT.md#L238-L246), [spec 257 plan](../../../specs/257-compiled-native-plans/plan.md#L7-L20), [`Graph.KG.Cypher.Gen`](../../../iris_src/src/Graph/KG/Cypher/Gen.cls). Spec 257 still says variable-length hops are interpreted; the generator now compiles them too.

### query.compiled.equal-answers

- agent
- data-integrity
- test-coverage
- Expands: [Compiled plans](#query.compiled).

Sources: [ADR-0014](../../../docs/adr/0014-native-plans-are-compiled-to-classes-at-run-time.md#L19-L20), [spec 257 US1](../../../specs/257-compiled-native-plans/spec.md#L50-L53), [spec 257 plan, tests](../../../specs/257-compiled-native-plans/plan.md#L51-L58). Live: [`test_257_compiled_plans_e2e.py`](../../../tests/e2e/test_257_compiled_plans_e2e.py) compares modes `off` and `sync` row for row with shadow mode on, in the default graph, a named graph and a multigraph. The TCK compiles few shapes and is not evidence here. Observed divergence: the interpreter tells used relationships apart by a 32-bit hash ([`Exec.Neighbours`](../../../iris_src/src/Graph/KG/Cypher/Exec.cls#L1239-L1248)) while compiled code compares them exactly, so a hash collision can drop a row only when interpreted ([A-cypher notes, F1](../../uplift/ivg-verus-initial/intent/cypher.md#candidate-findings)).

Findings: [A caller with Cypher read access can forge a CRC-32 collision so that another shape's queries run its compiled code](../../Verus_verification/bugs_issues.md#bug-cyp-001)

Iteration 58 (W62 D8, observed only): the same native-accepted reads answered identically in modes off, sync and job; a compiled class's second run was not isolated (the repeat was routed to SQL) ([W62 predictions and results](../../uplift/consolidated/iteration-58/w62-PAIRS.md)).

### query.compiled.modes

- Verus: see [compiled fallback](#query.compiled.fallback): `proofs-d1d` `planc_l2` (reviewed design) is active for job-mode answers during a build (public J08); `G-platform` (as-built) overlaps for stamps.
- agent
- operations
- Expands: [Compiled plans](#query.compiled).

Sources: [ADR-0014 decision and consequences](../../../docs/adr/0014-native-plans-are-compiled-to-classes-at-run-time.md#L16-L18), [ADMIN_GUIDE, Compiled native plans](../../../docs/ADMIN_GUIDE.md#L742-L780), [`Gen.Mode`, `Effective`, `ModeOf`](../../../iris_src/src/Graph/KG/Cypher/Gen.cls#L26-L50). Live: the job-mode test in `test_257_compiled_plans_e2e.py`.

State machines: [platform](../../Verus_verification/models/platform/manifest.json)

### query.compiled.never-stale

- agent
- data-integrity
- test-coverage
- Expands: [Compiled plans](#query.compiled).

Sources: [ADR-0014](../../../docs/adr/0014-native-plans-are-compiled-to-classes-at-run-time.md#L21), [spec 257 plan, question 2](../../../specs/257-compiled-native-plans/plan.md#L13-L15), [`Gen.For`, `Shape`, `Stamp`](../../../iris_src/src/Graph/KG/Cypher/Gen.cls#L59-L139), [`Exec.RunA` lookup](../../../iris_src/src/Graph/KG/Cypher/Exec.cls#L153-L168). Live: the stale-stamp test edits the recorded stamp; no test recompiles a class. Observed divergence: freshness is checked once per run, and a class is named by a 32-bit hash of its shape, so a colliding shape can recompile the same class while another run is using it, or leave one shape's record over the other's walk until a deploy ([integrity](#query.compiled.integrity); [A-cypher notes, F2](../../uplift/ivg-verus-initial/intent/cypher.md#candidate-findings)).

Findings: [A caller with Cypher read access can forge a CRC-32 collision so that another shape's queries run its compiled code](../../Verus_verification/bugs_issues.md#bug-cyp-001); [A run that started before a property-layout change can recompile a shape's class for the old layout under newer runs](../../Verus_verification/bugs_issues.md#bug-cyp-007)

### query.compiled.deploy-discards

- agent
- operations
- test-coverage
- Expands: [Compiled plans](#query.compiled).

Sources: [ADR-0014](../../../docs/adr/0014-native-plans-are-compiled-to-classes-at-run-time.md#L22-L23), [CONTEXT.md, Compiled plan](../../../CONTEXT.md#L243-L246), [setup calls `DropAll` when it deployed](../../../iris_vector_graph/schema.py#L2935-L2941), [`Gen.DropAll`](../../../iris_src/src/Graph/KG/Cypher/Gen.cls#L224-L230). Live: the `DropAll` test in `test_257_compiled_plans_e2e.py`; the deploy's call is checked by a mocked unit test ([`test_257_deploy_drops_compiled_plans.py`](../../../tests/unit/test_257_deploy_drops_compiled_plans.py)). The developer `compile` scripts do not drop plans and rely on [never stale](#query.compiled.never-stale).

Wording corrected in iteration 62 (the iteration-61 report, confirmed): "Nothing else removes them" was wrong. `Gen.Build` deletes the class it failed to compile (`Gen.cls:214`), which for a rebuild of a stale shape is the earlier compiled class; live in I62C a compiled `IVGC.P865046810` was gone after a rebuild failed through the `breaktest` hook, its `^IVG.CypherCompiled` entry kept the compile error and the read was answered by the interpreter ([observation](../../uplift/consolidated/iteration-62/probes/deploy_discards-observed-20261118T0206Z.json)).


### query.compiled.fallback


- uncertain
- Playbook: [NAT-B5.1](../../../experiment/playbook-completion/ontology/09-native-executor.md#L172), [NAT-T5.1](../../../experiment/playbook-completion/ontology/09-native-executor.md#L173)
- Verus: active for failed and pending builds answering through the interpreter (public J08, M20): the playbook's `proofs-d1d` [`planc_l2.rs`](../../../experiment/playbook-completion/proofs-d1d/src/planc_l2.rs) `theorem_ok_entry_runs_its_shapes_class`, `lemma_bcompile`, `lemma_for` (**reviewed design**; controls `control_f0901_shared_class_name`, `control_fc0901_mark_any_entry`, rerun here). Overlapping: `G-platform` (as-built) [`platform.rs`](../../Verus_verification/models/platform/platform.rs) stamps and eligibility (`witness_compiled_plan_is_used`).
- agent
- user-facing-behavior, operations
- Expands: [Compiled plans](#query.compiled).

Sources: [ADR-0014](../../../docs/adr/0014-native-plans-are-compiled-to-classes-at-run-time.md#L19-L20), [spec 257 US3](../../../specs/257-compiled-native-plans/spec.md#L60-L63), [`Exec.RunA` catches a failed lookup](../../../iris_src/src/Graph/KG/Cypher/Exec.cls#L153-L166), [`Gen.For`, `Build`](../../../iris_src/src/Graph/KG/Cypher/Gen.cls#L61-L222). Live: the failed-build, unrecordable shape and generator-failure tests in `test_257_compiled_plans_e2e.py`. A compiled class that fails while it runs falls to the SQL path under [native fallback](#query.native.fallback), and its shape keeps doing so until a deploy ([A-cypher notes, F12](../../uplift/ivg-verus-initial/intent/cypher.md#candidate-findings)).

Findings: [A build job queued before a layout change can leave a shape interpreted until the next change](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-cyp-009); [Mark a compiled entry failed when its walk raises, so the interpreter answers next time](../../Verus_verification/design_simplification.md#simp-cyp-003)

Open questions: [Should a compiled plan that fails while running be set aside?](../../Verus_verification/open_questions.md#HD-0904)

State machines: [platform](../../Verus_verification/models/platform/manifest.json)

### query.compiled.integrity

- agent
- security, data-integrity
- test-coverage
- Expands: [Compiled plans](#query.compiled).

Sources: [ADR-0014](../../../docs/adr/0014-native-plans-are-compiled-to-classes-at-run-time.md#L16-L23), [`Gen.For` hash, entry checks and pending write](../../../iris_src/src/Graph/KG/Cypher/Gen.cls#L69-L101), [`Gen.Build` digest check](../../../iris_src/src/Graph/KG/Cypher/Gen.cls#L163-L207), [ADMIN_GUIDE, writer roles](../../../docs/ADMIN_GUIDE.md#L600-L622), [review round 1, R1-3](../../uplift/ivg-verus-initial/review/round1-platform.md). Live: [`test_460_r311_writer_role_e2e.py`](../../../tests/e2e/test_460_r311_writer_role_e2e.py) covers planted lines from a writer, not colliding shapes. Observed divergence: a class is named by a 32-bit CRC of its shape and `Build` checks only the lines' digest, so when two colliding shapes are first run close together the entry can record one shape over the other shape's compiled walk, and that shape's reads then answer wrongly until a deploy, a stamp change or the other shape runs again (source reading; accidental odds about 1e-4 at 1,000 distinct shapes and 1% at 10,000). Suspected exploit, not run: a caller with only Cypher read access, on a server whose IRIS login can write the database, can craft a colliding shape (the CRC is affine and label and property names are free text) and repeat both reads until that ordering lands, persistently corrupting another caller's answers; proposed fixes are SHA-256 or sequence class names and a shape check in `Build` ([A-cypher notes, F2](../../uplift/ivg-verus-initial/intent/cypher.md#candidate-findings)).

Findings: [A caller with Cypher read access can forge a CRC-32 collision so that another shape's queries run its compiled code](../../Verus_verification/bugs_issues.md#bug-cyp-001); [The compiled-plan read-back after a synchronous build skips the class-name check](../../Verus_verification/bugs_issues.md#bug-cyp-008); [Name each compiled Cypher class by its code's digest instead of the shape's CRC-32](../../Verus_verification/design_simplification.md#simp-cyp-001)
