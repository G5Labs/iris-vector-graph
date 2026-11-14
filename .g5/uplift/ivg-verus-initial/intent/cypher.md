# Intent recovery: Cypher query execution (worker A-cypher)

Product baseline `3eaa79cf` (v4.7.0 + checklist). Worktree HEAD `0e441f1c` differs only under `.agents/` and
`experiment/`. Everything below is from reading source, docs and history; nothing was run. Tags: **(H)** a human
requirement or answered question, **(D)** an accepted design decision, **(O)** observed implementation only, **(P)** a
proposal. All commits have the same author name, so a "decided" line in a commit or spec is a recorded decision. It is
not independent agreement.

## Scope and sources inspected

| Locator | Revision / date | Authority | Inspected portion | Follow-up |
|---|---|---|---|---|
| `CONTEXT.md` §Graph, All-graphs read/write, Graph Key, §Query execution (l. 27-60, 224-250) | All-graphs read added `c76abaa1` (2026-10-20, v4.3.0); All-graphs write added `b1af594e` (2026-11-06, v4.6.0); Compiled plan `5d1e4768` (v4.4.0) | D (glossary decisions, dated "Decided") | full entries | none |
| `docs/adr/0014-native-plans-are-compiled-to-classes-at-run-time.md` | 2026-10-24, `5d1e4768`, Accepted | D | whole | none |
| `docs/adr/0016`, `0011`, `0008` | Accepted | D | 0016 l. 1-28 (schema); 0011, 0008 decision paragraphs | A-platform / A-structure own these |
| `specs/253-native-cypher-executor/spec.md`, `research.md` §E-H | Created 2026-10-20, Status "Draft" (shipped in 4.3.0) | D (the "Decisions (2026-10-20)" paragraph and FR-001..015) | spec whole; research §E-H | tasks.md not read line by line |
| `specs/257-compiled-native-plans/spec.md`, `plan.md` | 2026-10-22; "Built for fixed-length chains" (the code now also compiles variable-length hops: `Gen.VarHop`) | D (plan.md "open questions, settled") | whole | spec status is stale against code |
| `specs/259-compiled-plan-levers/notes.md` | notes | P (measured levers) | grep for oracle/decisions | not a contract |
| `specs/258-node-property-index/spec.md` | Draft, prototype "gain is small" | P (not built) | whole | none |
| `specs/229-tck-write-verification/spec.md` | Partially implemented 2026-09-26 | D (harness FRs) | header, FR list | harness side-effect counting not traced |
| `specs/201`, `203` (TCK harness), `025` (named paths) | 201 Draft; 203 Complete 2026-09-26; 025 Draft, amended 2026-10-07 | D/P | headers only | peripheral to this domain |
| `docs/dev/TCK.md` | at pin | O/D (run record) | l. 150-300 | none |
| `docs/KNOWN_ISSUES.md` | at pin | D (documented deviations) | index; l. 23-120 | none |
| `docs/ADMIN_GUIDE.md` §Compiled native plans (l. 742-780), inventory rows l. 241, 318-320 | at pin | D (operator contract) | listed lines | none |
| `docs/USER_GUIDE.md` l. 321-330 (all-graphs write), l. 1095-1120 (writes outside the ledger) | at pin | D | listed lines | none |
| `CHANGELOG.md` v4.6.0 l. 1700-1745 (all-graphs write fixes), v4.6.4 l. 410-425 (transactions), v4.6.5 l. 355-362, v4.7.0 l. 5-60, 205-246 (MERGE SET) | at pin | D/O (release record) | listed lines | earlier native entries (4.3.0-4.4.x) only grepped |
| Commits `c76abaa1`, `56de32f5`, `b1af594e`, `c3a05900`, `5d1e4768`, `9c683292` | 2026-04-10 .. 2026-11-06 | O (with recorded rationale) | messages; diff of `b1af594e` | none |
| `iris_vector_graph/_engine/query.py` | pin | O | l. 1740-2311, 2408-2540, 4294-4354 | other routes (`_route_var_length` body) only skimmed |
| `iris_vector_graph/cypher/native_plan.py`, `native_shadow.py`, `native_route.py`, `read_only.py`, `ast.py` (l. 510-550), `parser.py` (l. 170-200) | pin | O | whole files, except native_route past l. 60 | none |
| `iris_vector_graph/cypher/translator.py` (31,908 lines) | pin | O | l. 290-470, 560-1240, 1380-1400, 2075-2140, 5640-5680, 6025-6050, 7330-7386, 10183-10800 (CREATE/DELETE), 11508-11560, 12040-12070, 12440-12460, 12510-12620, 13069-13165 | most clause translators, expression typing and UNWIND/WITH not read; `merge_rows.py`, `count_create.py`, `row_where.py` not read |
| `iris_vector_graph/stores/iris_sql_store.py` | pin | O | l. 130-380, 1580-1860 | none |
| `iris_src/src/Graph/KG/Cypher/Exec.cls`, `Gen.cls`, `Props.cls` | pin | O | Exec l. 1-290, 826-1420; Gen whole; Props whole | Exec parallel split (290-590), sort/trim and Stage2 only skimmed; `SortKey.cls` not read |
| `iris_src/src/Graph/KG/GraphKey.cls` | pin | O | l. 1-70 | none |
| `iris_vector_graph/engine.py` | pin | O | l. 286-320, 559-720 | none |
| `iris_vector_graph/schema.py` | pin | O | l. 38-45, 380-420, 1640-1685, 2880-2950 | none |
| `iris_vector_graph/ledger/guard.py`, `_engine/ledger.py` l. 72-87 | pin | O | whole guard | ledger semantics are A-history's |
| `iris_vector_graph/cypher_api.py`, `bolt_server.py`, `api/routers/cypher.py`, `api/gql/schema.py` l. 150-200, `api/main.py` | pin | O | grep for entry points; router l. 94-260 | Bolt's packing not inspected |
| `iris_vector_graph/bulk_loader.py` l. 1-40, 150-170; `_engine/nodes_edges.py` l. 371-450 | pin | O | listed lines | A-structure owns |
| Tests: `tests/e2e/test_257_compiled_plans_e2e.py`, `test_253_all_graphs_read_e2e.py`, `test_460_all_graphs_writes_e2e.py`; `tests/unit/test_253_native_gates.py`, `test_253_shadow_compare.py`, `test_257_deploy_drops_compiled_plans.py`, `test_460_all_graphs_writes.py`; `tests/tck/environment.py` | pin | O (evidence) | test lists, fixtures, `_check` | other `test_253_*` e2e files: names only |

## Capabilities

### C1. Which path answers a Cypher query, and why a write never takes the native path

Governing statements

- (D) The native executor "takes only the reads it supports; every other query, and every write, takes the SQL
  path. On by default." The SQL path "is the reference the native executor is held to" (CONTEXT.md l. 224-232).
- (D) FR-001: "produce a native plan only for read-only queries it fully supports; anything else MUST take today's
  SQL path unchanged". FR-003, FR-005, FR-011 and FR-014 are the gates: index declared, opt-out, SELECT privilege,
  not inside `bulk_load_session` (spec 253 l. 98-140).
- (D) FR-007: "Any exception in the native executor MUST fall back to the SQL path and log a warning once per reason
  per engine." US4: "a caller must never see one as a wrong answer" (spec 253 l. 71-81).
- (D) `read_only` and every server's `IVG_READ_ONLY` apply one rule, `writes_cypher`. It counts a query that does not
  parse as a write (`read_only.py:92-104`; CHANGELOG R113).

Operations (entry, then guards, then writer or reader)

1. `execute_cypher` (`_engine/query.py:1746`). `writes_cypher(text)` (`:1783`) refuses under `read_only` (`:1784-1789`).
   Otherwise a writing text goes to `_execute_cypher_write` (`:1790-1791`, `:1946-1967`). That opens an IVG transaction
   level (`write_txn`) and re-enters `execute_cypher` with `_cypher_write_txn` set.
2. Before parsing, every text passes `_try_khop_fast_path` (`:1803`, `:4294-4354`; answers only when the default graph
   is the only one with edges, `:4319-4321`). It then passes the text shortcuts (`:1809-1856`, see F4), the
   `;`+`CALL` split (`:1858-1876`), `EXPLAIN`/`SHOW`/DDL no-ops (`:1878-1895`), chained parts (`:1904-1920`), the
   row-merge and count-create planners (`:1922-1930`), and finally `_execute_parsed` (`:1932`).
3. `_execute_parsed` (`:2032-2082`). Procedure handlers come first. Unless shadow mode is on, a per-shape `NativeRoute`
   may send the shape to SQL (`:2065-2069`). `_try_native` (`:2118-2160`) returns None for the SQL path when:
   `plan_query` declines (`native_plan.py:50-59`: `is_mutation`, procedure call, UNION, chained parts; `_plan_chain`
   accepts only MATCH and WHERE clauses, `:84-87`); or `native_gate` is closed (`native_plan.py:524-536`); or a label
   is mapped to a SQL table (`:2162-2184`); or the statement's own translation `is_transactional`, or its column count
   differs from the plan's (`:2140-2141`); or the executor raised (`:2144-2152`, a warning once per reason).
4. `_execute_parsed_sql` (`:2286-2311`). Transactional statements call `_ledger_check(self, "cypher_dml")` (`:2300`)
   and `store.execute_transaction` (`:2301`). Reads go to `execute_sql`. Variable-length reads go to the BFS routes
   (`:2291-2297`).

Why no write can reach `Graph.KG.Cypher.Exec` (three independent guards, O):
(a) `plan_query` returns None for `is_mutation` (`native_plan.py:52`). (b) `_plan_chain` rejects any clause other than
MATCH or WHERE, so `CALL { CREATE ... }`, FOREACH, MERGE, SET, REMOVE and DELETE in a part are declined (`:84-87`).
(c) `_try_native` declines a translation that `is_transactional` (`query.py:2140`). The executor itself writes only
process-private globals, `^IRIS.Temp.IVG.Cypher`, and the compiled-plan cache (`Exec.cls:4-6`, `Gen.cls:80-101`).
Read parts of a write can still run natively inside the write's transaction: a row-merge prefix (`query.py:1999`),
count steps (`:1977`) and chained read parts. The spec expects this: "A query planned natively inside an open
transaction sees that transaction's own writes" (spec 253 l. 91-92).

Outcome-changing cases: a read containing a write keyword in a string literal (a read: `read_only.py:61-81`); an
unparseable text (refused under `read_only`); a UNION with a write branch (`ast.writes`, `ast.py:535-550`; the planner
declines a UNION anyway); a gate closed mid-life of an engine. `_adjacency_indexed`, privileges and the executor
version are cached per engine (`engine.py:568-586`, `:593-610`, `:712-720`), so a change in another process is not
seen until `initialize_schema`.

Tests: `tests/unit/test_253_native_gates.py` (mocked engine; planner declines CREATE, SET, DETACH DELETE, MERGE, CALL,
UNION, unknown function; no FOREACH, REMOVE or `CALL {}` case). `test_r113_read_only_one_rule.py`,
`test_r115_read_only_verdict_independent.py` (unit). `test_253_native_plumbing_e2e.py`,
`test_253_executor_version_e2e.py` (live).

### C2. The native answer equals the SQL path's (shadow mode is the check)

Governing statements

- (D) FR-002: "A native result MUST equal the SQL path's: column names, value rendering ..., value types, row order
  where the query orders, row multiset otherwise." FR-013 covers a LIMIT/SKIP over a partial order. FR-006: "A shadow
  mode MUST run both paths and raise on any difference, with the query, parameters and the first differing row in the
  message." FR-012: a SQL-path defect is fixed on the SQL path first, and "the shadow gate stays plain equality"
  (decided 2026-10-20).
- (D) CONTEXT "Shadow mode": "a difference is raised as an error, not returned" (l. 234-236).
- (D) NativeRoute rests on the equality: "Both paths give the same answer (the shadow gate, FR-010), so the choice is
  speed alone" (`native_route.py:1-16`).

Operations: shadow switch `cypher_shadow` or `IVG_CYPHER_SHADOW=1` (`query.py:2112-2116`). In shadow mode the route is
skipped (`:2065`), native answers, the SQL path also answers (`:2075-2077`), and `_shadow_compare` (`:2226-2249`)
raises `NativeMismatch` if the SQL path errored, then calls `native_shadow.compare` (`native_shadow.py:29-69`). That
compares columns exactly and keys values by `(type name, value)`. It is ordered when the plan says `ordered`. With a
LIMIT and no total order it checks the count plus a bag inclusion against the unlimited SQL rows (`query.py:2234-2238`).
Otherwise it compares bags. The native result is named and decoded by the SQL translation's own aliases and decoders
(`query.py:2131-2142`, `:2153-2158`).

Preconditions for equality (O; the model must make them explicit):

- `^KG` equals the rows. The gate trusts the declared functional index and `_in_bulk_load` of *this* engine only
  (`native_plan.py:528-531`). A `BulkLoader` in another process loads `%NOINDEX`, commits per batch and rebuilds
  `^KG` at the end (`bulk_loader.py:1-12`, `:157-163`). spec 253 research §H names this trap. See F7.
- The rdf_props direct reader's layout is right. A layout other than the expected one falls back to prepared SQL, read
  per run (`Props.cls:14-25`, `:76-79`).
- SQL and native use the same graph rule (C4).

Outcome-changing cases: unordered LIMIT (either path may keep any rows); ties under ORDER BY (allowed to differ from
SQL; must match between compiled and interpreted, C3); `''` stored as `$Char(0)` (`Props.cls:41-72`, R295/R307);
missing property in a comparison (filters the row, `Exec.cls:924-939`); parallel relationships in a multigraph
(`Exec.cls:1204-1225`); a cycle closed on the anchor (`native_plan.py:98-110`).

Behaviour to note (O): in shadow mode, a native exception still falls back silently (warning once,
`query.py:2144-2152`). Shadow mode raises only on an answered difference (F11). Outside shadow mode, a native/SQL
difference that exists is invisible. The route trial (`native_route.py`) then can switch one shape's answer between
the two paths over repeated calls.

Tests: `tests/unit/test_253_shadow_compare.py` (pure unit of `compare`). `test_253_shadow_unlimited.py` (unit).
Family A/B e2e (`test_253_family_a_e2e.py`, `test_253_family_b_e2e.py`, live, shadow on). TCK shadow run at spec 253
completion: 3896/3896 (TCK.md l. 221-222, a recorded run, not re-run here). The TCK harness does not set shadow mode in
normal runs (TCK.md l. 217-218).

### C3. Compiled plans: lifecycle, staleness, equality to the interpreter, fallback

Governing statements

- (D) ADR-0014 l. 16-23. `Gen` owns the code, the map `^IVG.CypherCompiled(hash)` and the modes `job` (default), `sync`
  and `off`. "A compiled class answers exactly as the interpreter does. The interpreter stays, and answers every shape
  that is not compiled, failed to compile, or cannot be recorded." "An entry records the `rdf_props` stamp and the
  build times of `Exec` and `Gen`. A stale entry is never run; its shape is built again." "A deploy that installs
  classes, and `Gen.DropAll()`, delete every compiled class and entry. Nothing else prunes them."
- (D) CONTEXT "Compiled plan" (l. 243-246): "A deploy discards every Compiled plan."
- (D) spec 257 US1: "three-way: ... compiled routine, the interpreter and the SQL path; all three equal". plan.md l.
  56-58: "The compiled answer equals the interpreted one row for row, including the order among ties." US3 / ADR:
  compilation never costs a caller.
- (D) ADMIN_GUIDE l. 241, 742-780: mode `off` for change-controlled or read-only sites. "a stale one never runs".

Operations

- Mode: `Gen.Mode` (per process, `^||IVG.CypherGenMode`), `Effective` (`^IVG.CypherGen("mode")`, default `job`), and
  `ModeOf` (a worker takes its coordinator's mode) (`Gen.cls:28-50`).
- Lookup: `Exec.RunA` calls `Gen.For(.tQ, anchor)` **once per run** inside Try/Catch (`Exec.cls:156-166`). The answer is
  then used for every anchor via `$ClassMethod(tGen, "Walk1", ...)` (`:198-199`, `:257-258`).
- `Gen.For` (`Gen.cls:61-105`) returns "" for `off` (`:64`), for no direct property layout (`:67`), and for no hop
  (`:68`, `:108-111`). It computes `tShape` (`:115-132`), `tStamp` = Props stamp | `Exec.BuiltAt` | `Gen.BuiltAt`
  (`:136-139`; `BuiltAt` are objectgenerator constants, `Exec.cls:25-29`, `Gen.cls:53-57`), and `tH = $ZCRC(tShape,
  7)` (CRC-32). It runs the class only if the entry's shape and stamp are equal, the status is `ok`, and the class name
  is `IVGC.P<tH>` (`:70-73`). A failed status is never retried (`:75`). A pending one is left alone for 120 s
  (`:76`). Otherwise it marks the entry pending (`:80`), writes the lines (`:82-89`), digests them with SHA-256
  (`:91`, `:147-156`), and either `Job`s `Build` (`job`: answers "" now, `:92-100`) or builds inline (`sync`,
  `:101-104`).
- `Gen.Build` (`:163-222`) takes a `Lock +^IVG.CypherCompiled(pH):0` (a second builder quits). It requires a pending
  status with lines present, and the lines' digest must equal the digest `For` computed (R311, `:177-182`). It then
  loads and compiles `IVGC.P<pH> Extends Graph.KG.Cypher.Exec` with one method `Walk1`. On success the status becomes
  `ok`. On failure it records the error, writes `messages.log`, and deletes the class.
- `Gen.DropAll` (`:225-230`) deletes package `IVGC` and kills the map. It is called by
  `GraphSchema.deploy_objectscript_classes` only `if result.deployed` (`schema.py:2935-2941`, failure logged at debug)
  and by `scripts/enterprise-container.sh:348` (tcp-deploy). The dev `compile`/`compile-all` paths do not call it.
  They rely on the stamp.
- Fallback layers (O): any reason `For` gives "" means the run is interpreted. An exception in `For` (e.g. `<PROTECT>`
  on a read-only database) is caught and logged once per error name per process (`Exec.cls:157-166`). **An error raised
  inside a compiled `Walk1`** is not caught by RunA. `Run` re-throws it (`Exec.cls:43-49`), so that read falls to the
  **SQL path**, not to the interpreter (`query.py:2144-2152`). The entry stays `ok`, so the shape keeps failing over to
  SQL until a deploy.

Equality between interpreter and generated code, as written (O):
- Node checks (`Gen.Check`, `Gen.cls:496-527`) mirror `NodeOK` (`Exec.cls:908-964`), including `''` as `$Char(0)`
  (`Gen.cls:279-280`, fixed after R307 "{p: ''} matched nothing compiled"). Cross filters call `NodeOK` itself.
- Relationship uniqueness differs in mechanism. The interpreter keeps a string of `$ZCRC($ListBuild(src, p, dst,
  ekey), 7)` hashes and skips an edge whose hash is in it (`Exec.cls:1243-1244`). The generated code keeps each hop's
  endpoints, type and key as locals and compares them exactly (plan.md l. 24-26; `Gen.cls:414-420`). See F1.
- What the shape holds versus what the generated code bakes in: `Emission`, `Hop`, `VarHop` and `Check` branch at
  generation time only on `acc`, `agg`, `ret`, `kvars`, `aggs`, `mult`, per-hop list and tally/vl flags, node
  labels, property keys, comparison ops, id presence and cross filters. All of these are in `Shape` (`Gen.cls:117-130`).
  DISTINCT, ORDER, LIMIT, split and mayfill are read from `pQ` at run time (`Gen.cls:268`, `:539-541`). I found no
  baked value missing from the shape in the parts read.

Outcome-changing cases: a first run in `job` mode (interpreted) versus the second (compiled); a read-only database or
role (`For` raises, interpreted); a process killed during `Build` (pending, retried after 120 s); two processes
building one shape (lock; the second quits); a deploy while a run is mid-walk (class deleted: `<CLASS DOES NOT EXIST>`,
SQL fallback); two shapes with one CRC-32 (F2); an `rdf_props` recreate (`TimeChanged` changes, so the stamp changes);
the stamp read per run (`Props.Layout` re-reads `TimeChanged` on every `Begin`, `Props.cls:16-22`, `:76-79`).

Tests: `tests/e2e/test_257_compiled_plans_e2e.py` (live). `_check` (l. 251-267) runs mode `off`, then `sync`, and
asserts row-for-row string equality with shadow on, over each case in three scopes (default, named graph, multigraph,
l. 236-243). Lifecycle cases (l. 328-544) cover job mode, `DropAll`, a stale stamp (simulated by editing the global's
stamp field, l. 359-368, not by a real recompile), a failed build (test hook), a process that cannot record the shape,
and a generator failure. `tests/unit/test_257_deploy_drops_compiled_plans.py` (mocked) checks that the deploy calls
`DropAll` only when it deployed. The TCK compiles few reads (5 shapes in 4.4.0, TCK.md l. 228-232), so it is not
evidence for compiled equals interpreted.

**Seed-claim check (index.md row "Cypher execution").**
- "The compiled plan and interpreter owe the caller the same result": **confirmed** (D: ADR-0014, CONTEXT,
  spec 257). **Corrected in scope**: the governing reference is the SQL path (CONTEXT l. 230-232, FR-002). The full
  obligation is compiled = interpreted = SQL (spec 257 US1). Between compiled and interpreted, plan.md asks for equal
  order among ties. The seed's evidence pointer "TCK harness" is weak. The TCK compiles few shapes and does not run in
  shadow mode by default. The live oracle is `test_257_compiled_plans_e2e.py`.
- "A stale plan must never run": **confirmed as design** (stamp + shape + class-name + digest checks; deploy
  `DropAll`). **Qualified**: the check is made once per run, at `For`. Nothing ties the class that later runs to that
  check. A rebuild of the same `IVGC.P<h>` during a run is possible when two shapes share a CRC-32 (F2).
- "The interpreter can answer when compilation is unavailable": **confirmed** for not built, pending, failed, refused,
  mode off, non-direct layout, and an unrecordable shape. **Corrected**: a compiled class that fails while running
  falls back to the SQL path, not the interpreter.

### C4. Graph scope: `USE GRAPH`, the all-graphs read, and graph keys

Governing statements

- (D) "**All-graphs read**: A read that names no graph ... sees every graph, and its answer is the union of each
  graph's own answer: a node is still its own graph's node (the same node ID in two graphs is two nodes), its labels
  and properties are that graph's, and an edge meets only nodes of its own graph. (Decided 2026-10-20.)" (CONTEXT
  l. 38-42). Spec 253 FR-009 repeats it and requires the SQL path to be fixed first (l. 116-120).
- (D) Graph Key: the default graph's `^KG` key is 0. The SQL column spells it `''`. The two are derived from the name
  and never converted. "A scoped lookup never falls through to the default graph" (CONTEXT l. 50-58; ADR-0001, 0003;
  `GraphKey.cls:1-70`, which reserves the name `"0"`).
- (D) KNOWN_ISSUES l. 43-66: an all-graphs read cannot say which graph a row came from (`graph_id` reads null). The
  workaround is one `USE GRAPH` per graph, with `USE GRAPH ''` for the default graph.
- (O) `USE GRAPH ''` is the default graph, not all graphs. The translator tests `is not None` (`translator.py:2081-2086`,
  `:5647-5649`; spec 230 FR-001). The native plan carries `graph: ""` as a string, so it is scoped
  (`native_plan.py:245`; `Exec.cls:112-113`).

Operations

- Parse: `USE [GRAPH] <string|identifier>` is the first token (`parser.py:174-192`). The name is **not validated**
  here (`validate_graph_name` is used only by engine methods, `_validate.py:19`). See F8.
- SQL path, scoped: `_apply_graph_scope_to_reads` (`translator.py:719-779`) adds `COALESCE(x.graph_id,'') =
  COALESCE('<g>','')` to every graph-owned FROM/JOIN, cross join and sub-SELECT, as text rewrites
  (`_graph_scope_fragment`, `_scope_from_lists`, `:564-700`).
- SQL path, all graphs: `_all_graphs_correlated` (`:782-794`) asks `engine._more_than_one_graph()` (`engine.py:612-639`,
  which reads **`nodes` only**). If true, `_correlate_graphs_in_reads` (`:898-1035`) appends `a.graph_id = b.graph_id`
  after every join equality it can find by regex. It also ties each crossed-in node (`MATCH (a),(b)`) to the first
  node's graph (`:931-945`), carries the graph through WITH stages (`__g_<var>`, `:881-895`, R226), and handles
  procedure CTEs (R192). Variable-length reads run the BFS routes once per graph with edges
  (`query.py:2472-2479`, `:2422-2452`). Procedures union per graph or refuse (`translator.py:290-323`).
- Native: `GraphKeys` gives the plan's graph key `ForIndex(g)` or every key under `^KG("label")`
  (`Exec.cls:832-845`). `Anchors` takes id/property candidates per graph from SQL with `COALESCE(graph_id,'') =
  COALESCE(?, '')`, passing `$Char(0)` for the default graph (`:848-904`). Each candidate carries (graph key, graph
  name, id). The whole walk then uses that key for `^KG(dir, key, ...)` and that name for property reads
  (`Exec.cls:999-1250`; `Props.Get` maps `""` to `$Char(0)`, `Props.cls:47`). count(DISTINCT) keys a node as
  `$ListBuild(graph, id)` (`:1309-1312`). The k-hop fast path answers only when the default graph is the only graph
  with edges (`query.py:4317-4321`).

Outcome-changing cases: the same id in two graphs with different labels and properties; an edge in g1 whose endpoint id
also exists in g2; `MATCH (a), (b)` across graphs (paired within one graph only, CHANGELOG 4.6.0 `02cb72e3`); a graph
holding only nodes (no `^KG("label")` entry if unlabelled; the native id anchor without a label reads `nodes` by SQL,
`Exec.cls:855-871`); legacy NULL `graph_id` rows (COALESCE); a namespace with nodes in one graph but property rows
left in another (F6); `USE GRAPH '0'` (F8); a non-default IVG Schema. Exec and Props name `Graph_KG` literally
(`Exec.cls:858`, `:886`, `:1101`; `Props.cls:31-34`, `:66`), while the privilege probe uses the engine's schema
(`engine.py:574-576`). ADR-0016 says spec 262 (pending) moves the ObjectScript classes to the recorded schema. This is
A-platform's to settle.

Tests: `tests/e2e/test_253_all_graphs_read_e2e.py` (live; two graphs; default engine, native on). It covers properties,
labels, edge to own-graph node, count over a hop, label filter, var-length, `USE GRAPH` unchanged.
`test_460_r319_zero_hop_all_graphs_e2e.py`, `test_460_r192_all_graphs_procedures_e2e.py`,
`test_461_shortest_path_all_graphs_e2e.py` (live). `test_257_compiled_plans_e2e.py` runs each compiled case in a named
graph. The TCK runs in the default graph only (`tests/tck/environment.py:301-310`; its "named graphs" are labelled
fixtures, l. 209-214), so it never exercises the correlation pass (`_all_graphs_correlated` is false with one graph).

### C5. Cypher writes: all-graphs write semantics, statements, transaction, ledger, adjacency

Governing statements

- (D) "**All-graphs write**: ... `SET`, `REMOVE` and `DELETE` change each node and relationship the `MATCH` bound, in
  that node's own graph, and nothing else ... `CREATE` writes the default graph, and `MERGE` matches and creates
  there, so its `ON MATCH` changes the default graph's node only. (Decided 2026-11-06.)" (CONTEXT l. 44-48;
  USER_GUIDE l. 324-329: "Under `USE GRAPH 'g'` every write reads and writes graph g alone.")
- (D) CHANGELOG v4.6.0 l. 1700-1745 (`b1af594e`). Since 4.0.0 an unscoped SET/REMOVE/DELETE matched through joins on the
  id alone and changed other graphs' nodes; `MERGE ... ON MATCH SET` changed every graph's node; `-119`/`-121`
  failures; `ON MATCH SET n += map` wrote a label spelling the map. KNOWN_ISSUES l. 104-117 refuses `MERGE ... SET n =
  {...}` on a node.
- (D) "Every statement of a write uses the rows its MATCH bound" (R186), and DELETE captures ids up front (spec 229).
- (D) v4.6.4 (CHANGELOG l. 410-425): every Cypher write is one nested IVG transaction level. The caller's commit or
  rollback decides. A write in steps is one transaction. A failed write takes back only itself.
- (D) Adjacency: `^KG("out"/"in"/"label")` follow the rows by functional index "inside the transaction of the row";
  Cypher DML is one of the writers named (ADR-0008 l. 14-15; CONTEXT l. 89-95). Degree comes from the
  generation-validated cache (ADR-0012), which is A-structure's.
- (D) Ledger: writes outside the ledger are not recorded; strict mode refuses them (USER_GUIDE l. 1107-1110).

Operations

- Translation: `add_dml` (`translator.py:2075-2095`) scopes each DML statement. Under `USE GRAPH` it calls
  `_scope_dml_statement(sql, g)` (`:1137-1217`): a predicate for UPDATE/DELETE, a `graph_id` column and value for
  INSERT...SELECT, and a scoped NOT EXISTS guard. A MERGE action with no USE GRAPH is scoped to `''`
  (`_merge_writes_default`, set at `:12061`, cleared at `:12452`). With no USE GRAPH, a statement that reads exactly
  one graph-carrying capture is rewritten with `__GRAPH_<key>__` / `__GRAPHV_<key>__` tokens (`_scope_dml_to_capture`,
  `:1225-1235`). The MATCH used for a write is correlated per graph (`build_dml_subquery`, `:2112-2127`). `_write_ids`
  always captures `(id, graph)` when the namespace has several graphs (`:13093-13131`). `_capture_key` emits
  `__capture_ids__ <key>` or `__capture_pairs__ <key>` once and places it before the first write (`:13134-13164`).
  DELETE captures its targets with their graph and scopes labels, props, nodes and incident edges by `graph_id =
  __GRAPH_<key>__` (`:10625-10800`).
- CREATE: node and relationship inserts carry `_graph_of(context)`, which is `''` with no USE GRAPH
  (`translator.py:429-438`, `:10241-10247`, `:10351-10365`, `:10377-10387`). MERGE first runs the create path, then
  rewrites the existence checks (`:11508-11560`).
- Execution: `IRISGraphStore.execute_transaction` (`stores/iris_sql_store.py:1580-1818`) opens a nested `write_txn`
  (`:1582`). It handles the statement protocol: `__snapshot_stage__`, `__pin_stage__`, captures, pairs,
  `__constraint_check_delete_connected__`, `__capture_edge_hwm__`, `__after_result__`, pre-delete result snapshot. It
  expands each statement once per captured graph with that graph's ids (`_expand_captured`, `:185-211`: one graph
  token per statement, else `RuntimeError`; no capture runs once and matches nothing) and in chunks of at most 900
  literals (`:319-373`). It commits its level (`:1788`), or rolls back and raises `GraphWriteError` (`:1811-1818`).
  The outer `_execute_cypher_write` commits, or rolls back on an exception or `result.error` (`query.py:1958-1966`).
- Ledger: `_ledger_check(self, "cypher_dml")` runs before each transactional statement batch (`query.py:2300`). The
  guard probes `Graph.KG.Ledger.Meta()` at most every 5 s (`ledger/guard.py:20`, `:37-60`) and raises
  `LedgerStrictModeError` only in strict mode (`:75-80`). Otherwise Cypher DML goes to the tables with no ledger record
  (O; documented in general, not per Cypher, see F12).
- Adjacency and degree: no Cypher code writes `^KG` (O: no `_adjacency_indexed` or `^KG` writes in translator or
  store). Maintenance is the functional index's (ADR-0008/0011).

Outcome-changing cases (the e2e matrix covers most): a pattern with and without a label where another graph holds
the id; three graph modes (`test_460_all_graphs_writes_e2e.py:162-166`); SET of a new key, `+=`, `=`, labels,
REMOVE, relationship SET, DELETE, DETACH DELETE, `MERGE ... ON MATCH SET`; a SET read from another variable or a
relationship (pairs per graph, `iris_sql_store.py:214-242`); nothing captured (runs once and matches nothing); more
than 500 ids (chunking); a strict ledger turned on in another process within 5 s; a caller-open transaction; and
**CREATE or MERGE of a relationship between nodes bound in a named graph** with no USE GRAPH. The edge goes to the
default graph between the same ids (`translator.py:10351-10365`). The composite FK `(graph_id, s)` on `rdf_edges`
(`schema.py:42-43`) then refuses it, or it connects the default graph's homonymous nodes. Untested; see F5.

Tests: `tests/e2e/test_460_all_graphs_writes_e2e.py` (live, native on and off, state read back with plain SQL,
l. 1-26, 133-240). `tests/unit/test_460_all_graphs_writes.py` (executor expansion, unit). The TCK side-effect
counting (spec 229) runs in one graph.

### C6. Other entry points and pre-parse shortcuts

- (O) `cypher_api.py` (the documented HTTP server, ADMIN_API.md l. 9) and `bolt_server.py:570-581` call
  `engine.execute_cypher` after `writes_cypher`. They get every path above.
- (O) The second FastAPI app (`api/main.py:13`, `:115`) serves `POST /api/cypher` (`api/routers/cypher.py:28`,
  `:94-166`) and GraphQL `executeCypher` (`api/gql/schema.py:150-200`). These call `translate_to_sql` and run each
  statement with a bare cursor between `START TRANSACTION` and `COMMIT`. See F3.
- (O) `execute_cypher` answers three text patterns without parsing (`query.py:1809-1856`): Neo4j Browser metadata
  (`9c683292`, v1.47.0). See F4.

## Candidate obligations for formal modeling

**O1. Native answer equality (compiled = interpreted = SQL) under explicit preconditions.**
L1: for every read the planner accepts, the native answer (compiled or interpreted) equals the SQL path's under
FR-002/FR-013. Compiled and interpreted also agree on order among ties. A native failure never becomes a wrong answer
(FR-007).
L2: data are the rows (`nodes`, `rdf_labels`, `rdf_props`, `rdf_edges` with `(graph_id, s, p, o_id, ekey)`) and the
derived `^KG` out/in/label per graph key. Guards are `native_gate` and `plan_query`. There is no commit boundary
(reads only); the executor runs in the caller's process and sees its uncommitted writes.
L3 to bind: `native_plan.plan_query` / `_plan_chain` (`native_plan.py:50-262`), `Exec.RunA` / `Walk` / `Neighbours` /
`NodeOK` / `Emit` / `Group` (`Exec.cls:110-281`, `:908-1316`), generated `Walk1` (`Gen.Hop`/`VarHop`/`Check`/
`Emission`, `Gen.cls:262-602`), `native_shadow.compare` (`native_shadow.py:29-69`), and an abstract SQL-path
semantics for the same fragment.
Cases a model must represent: two graphs sharing an id; a multigraph with parallel edges; two hops of one type (edge
uniqueness, F1); a cycle closed on the anchor; a missing property; `''`; DISTINCT; LIMIT with and without ORDER BY;
ties; an index that lags the rows (precondition violated, F7).

**O2. Compiled-plan cache: a class runs only for its own current shape.**
L1: a compiled class runs only for the shape and the build stamp it was written for. A deploy discards all of them. A
missing, pending, failed or unrecordable entry means the interpreter answers.
L2: the entry `^IVG.CypherCompiled(h) = (class, shape, stamp, status, builtAt)`, the lines, the digest, a build lock
with `:0` timeout, a 120 s pending retry, `IVGC.P<h>` with `h` = CRC-32(shape), modes per process and namespace.
L3 to bind: `Gen.For` (`Gen.cls:61-105`), `Gen.Build` (`:163-222`), `Gen.DropAll` (`:225-230`), `Exec.RunA` lookup
and calls (`Exec.cls:156-168`, `:198-201`, `:257-261`), `deploy_objectscript_classes` (`schema.py:2935-2941`).
Cases: concurrent `For` of one shape (job mode); two shapes with equal CRC-32; DropAll or deploy during a run; a stamp
change between two runs; a killed build job; a role without write on the database; a planted entry pointing at
another class (`:73`) or with planted lines (`:177-182`).

**O3. Write routing and atomicity.**
L1: no Cypher write is answered by the native executor or by a pre-parse shortcut. Every Cypher write is one IVG
transaction level. On error it leaves nothing of its own. Under a strict ledger it is refused before writing.
L2: `writes_cypher` verdict; `_cypher_write_txn`; `write_txn` nesting (outer in `_execute_cypher_write`, inner in
`execute_transaction`); `_ledger_check` per transactional batch; `GraphWriteError` on refusal.
L3 to bind: `execute_cypher` (`query.py:1782-1943`), `_execute_cypher_write` (`:1946-1967`), `_execute_parsed`
(`:2032-2082`), `_execute_parsed_sql` (`:2299-2303`), `execute_transaction` (`iris_sql_store.py:1580-1818`), and the
api/ routes (F3), which do not satisfy it.
Cases: a write keyword in a literal; a write in a UNION branch or `CALL {}`; per-row MERGE (several steps); a
caller-open transaction; a failure in the third statement; strict mode turned on in another process.

**O4. Graph scope of reads (all-graphs and `USE GRAPH`).**
L1: as CONTEXT All-graphs read. Under `USE GRAPH g`, only g; `''` names the default graph.
L2: SQL predicates by graph name (`''` / COALESCE NULL); native keys `ForIndex(name)` (0 for default) for `^KG`, the
name (`$Char(0)` for default) for `rdf_props` index subscripts and SQL arguments.
L3 to bind: `_apply_graph_scope_to_reads`, `_all_graphs_correlated`, `_correlate_graphs_in_reads`
(`translator.py:719-1035`), `engine._more_than_one_graph` (`engine.py:612-639`), `Exec.GraphKeys`/`Anchors`/`NodeOK`
(`Exec.cls:832-964`), `Props.Get` (`Props.cls:44-72`), `GraphKey.ForIndex` (`GraphKey.cls:51-56`).
Cases: same id in 2 graphs with different labels; a cross-graph edge id; a props row whose graph has no node row (F6);
`USE GRAPH ''`; `USE GRAPH '0'`.

**O5. Graph scope of writes.**
L1: as CONTEXT All-graphs write. SET/REMOVE/DELETE change exactly the (graph, id) pairs the MATCH bound. CREATE writes
`''`. MERGE matches, creates and runs ON MATCH/ON CREATE in `''`. `USE GRAPH g` confines everything to g.
L2: the captures `(id, graph)` and pairs `(id, value, graph)`; statement expansion per captured graph; the
`_merge_writes_default` flag.
L3 to bind: `add_dml`, `_scope_dml_statement`, `_scope_dml_to_capture`, `_write_ids`, `_capture_key`,
`translate_delete_clause` (`translator.py:1137-1235`, `2075-2127`, `10625-10800`, `13093-13164`),
`_capture_rows`/`_capture_pairs`/`_expand_captured` (`iris_sql_store.py:163-242`).
Cases: a statement that reads two capture keys (left unscoped by `add_dml`, `:2092-2094`); no row captured; a
relationship CREATE/MERGE between bound named-graph nodes (F5); DETACH DELETE of a reified edge with no USE GRAPH.

## Candidate findings

**F1. SUSPECTED bug: the interpreter's relationship uniqueness compares CRC-32 hashes.** Expected: compiled =
interpreted = SQL (ADR-0014; spec 257 US1). Observed: `Neighbours` keeps the edges a match has used as a comma
string of `$ZCRC($ListBuild(src, p, dst, ekey), 7)` and skips an edge whose 32-bit hash is already there
(`Exec.cls:1243-1244`). The generated walk compares the endpoints and key exactly (plan.md l. 24-26), and the SQL path
compares `edge_id`. Two distinct relationships whose `$ListBuild` encodings share a CRC-32 make the interpreter drop a
legitimate match. CRC-32 collisions are easy to construct deliberately (node ids are free text). The case that tells
them apart: `MATCH (a:P)-[:K]->(b)-[:K]->(c) RETURN count(*)` over edges a→b and b→c whose tuples collide. Mode `off`
answers 0, mode `sync` and SQL answer 1. P: key `pUsed` by the full `$ListBuild`, or hold used edges in a local
array subscripted by the tuple.

**F2. SUSPECTED bug (low likelihood): a compiled class can be replaced for another shape while a run uses it.**
Expected: "A stale entry is never run" (ADR-0014). Observed: the class name is `IVGC.P<CRC-32(shape)>`
(`Gen.cls:69`, `:183`). `For` detects a colliding shape by comparing the stored shape (`:71`), then *rebuilds the same
class name* for the new shape (`:80-101`, `:183-207`). `RunA` verifies the entry once (`Exec.cls:158`) and calls
`$ClassMethod(tGen,"Walk1")` per anchor for the rest of the run (`:199`, `:258`), with no lock held. A concurrent
rebuild for the colliding shape changes the code mid-run, so a walk written for another shape answers part of this
read. Collisions also thrash: each shape rebuilds the other's class on every alternate `For`. P: name the class by the
SHA-256 already computed for the lines (or by a sequence number stored in the entry), store shape and stamp as class
parameters and have `RunA` compare them. The behaviour to keep is one class per shape, interpreted until built. The
distinguishing case is two shapes forced to one hash (a test hook).

**F3. SUSPECTED bug: the `api/` app's Cypher routes bypass the engine's executor.** Expected: one write rule and one
execution path for every route. `read_only.py:3-7` lists "api.main's `/api/cypher` and GraphQL `executeCypher`" among
the routes the rule covers. Spec 229 / R186 captures and per-graph expansion are the only way deletes and all-graphs
writes are executed (C5). The strict ledger refuses Cypher DML (`query.py:2300`). Observed: `api/routers/cypher.py:129-166`
and `api/gql/schema.py:174-200` run `translate_to_sql(...).sql` statement by statement with a bare cursor. The
statement protocol (`__capture_ids__`, `__capture_pairs__`, `__pin_stage__`, `__IDS_*`, `__GRAPH_*`,
`__constraint_check_delete_connected__`, `__after_result__`) is sent to IRIS as SQL. So every DELETE, every pinned SET
and every all-graphs write in a multi-graph namespace should fail. These routes also skip `_ledger_check` (a simple
CREATE commits under a strict ledger), the variable-length BFS routes (`SQLQuery.graph_context` comment,
`translator.py:1391-1395`), result decoding (`_finish_sql_result`) and the native path. The source text proves the
protocol is unhandled (no `__capture` handling under `api/`). The exact responses are not observed. Case: `POST
/api/cypher {"query": "MATCH (n:X {id:'a'}) DELETE n"}` against `api.main` versus `cypher_api`.

**F4. SUSPECTED bug: text shortcuts answer unrelated reads with canned rows.** Observed: any non-write text whose
upper-cased form contains `"MATCH ()"`, `"COUNT(*)"` and `"UNION ALL"` returns `[{"name":"nodes","data":N}],
[{"name":"relationships",...}]` counted over every graph. Any text containing `"RETURN DISTINCT"`, `"UNION ALL"` and
`"ENTITY"` returns 25 node ids and 25 predicates (`query.py:1829-1856`). Both ignore `USE GRAPH`, the query's patterns
and its columns. The conditions are substring tests over the whole text, string literals and property names included.
Origin: Neo4j Browser metadata queries, `9c683292` (v1.47.0). `read_only.answered_without_parsing` does not list them,
so they are not a documented contract. A write that matches reaches them too, from inside `_execute_cypher_write`'s
re-entry, and would commit nothing. Case: `MATCH (e:Entity) RETURN DISTINCT e.name AS x UNION ALL MATCH
(e:Entity) RETURN DISTINCT e.kind AS x`. P: match the Browser's exact texts, or parse first.

**F5. Open question: CREATE / MERGE of a relationship between nodes an all-graphs MATCH bound in a named graph.**
Evidence: the decision says "`CREATE` writes the default graph" (CONTEXT l. 46-48). The edge insert uses
`_graph_of(context)` = `''` (`translator.py:10351-10365`) with the bound pair's ids. The FK `(graph_id, s/o_id) →
nodes` (`schema.py:42-43`) refuses it when the default graph lacks those ids (`GraphWriteError`, nothing written).
When the default graph has nodes of the same ids, it connects *those* nodes, not the ones the MATCH bound. The e2e
matrix has no such case (`test_460_all_graphs_writes_e2e.py:133-147`). Interpretations: (a) the decision is literal,
and a relationship is created only between default-graph nodes, so the error is intended. (b) Cypher's binding wins,
and a relationship between bound nodes is created in their graph, which is the rule SET/DELETE already follow. A human
must choose and say whether the error should name the cause.

**F6. SUSPECTED bug (data-dependent): the all-graphs correlation is skipped when only `nodes` looks single-graph.**
Expected: CONTEXT All-graphs read. Observed: `_all_graphs_correlated` asks `_more_than_one_graph`, which reads only
`nodes` (`engine.py:612-639`; `translator.py:782-794`). `rdf_props` has no FK to `nodes` (`schema.py:411-418`), and
v4.7.0 states that property rows "a node removed by SQL left behind under its id in its graph" exist (CHANGELOG
l. 54-58). With nodes in one graph and orphan property rows in another, the uncorrelated SQL join `p.s = n.node_id`
reads the other graph's rows for the same id. The native reader (`Props.Get(graph, s, key)`) does not, so shadow
mode raises, or the SQL answer breaks the rule when the shape is declined natively. Case: default node `x {k:1}`, plus
a leftover `rdf_props('g', 'x', 'k', 2)` and no `g` node row; `MATCH (n {node_id:'x'}) RETURN n.k`. P: probe
`rdf_props` too, or correlate whenever any graph-owned table holds two graphs.

**F7. Limit / SUSPECTED: the native gate does not see another process's unindexed load.** FR-014 is implemented
per engine (`native_plan.py:530`). `BulkLoader` writes `%NOINDEX %NOCHECK`, commits per batch and rebuilds indices and
`^KG` at the end (`bulk_loader.py:1-12`, `:157-163`). spec 253 research §H names the trap. During that window other
engines' native reads read `^KG` and `pkprops` behind the rows. The SQL path's index-backed plans may lag too, so
which answer is "right" is undefined. The modeling consequence is that "index current" is a precondition of O1, not
an invariant. Question: should a load publish a namespace-wide marker that `native_gate` checks?

**F8. Minor: `USE GRAPH` names are not validated on the Cypher path.** `parser.py:174-192` accepts any string. The
reserved `"0"` and control characters (`GraphKey.cls:24-48`) are refused only where `ForIndex` runs: functional-index
label and edge writes fail, native reads throw and fall back to SQL. A label-less `USE GRAPH '0' CREATE ({id:'a'})`
writes a `nodes` row in graph `'0'` that `^KG` cannot represent. P: call `validate_graph_name` on `graph_context` at
parse or translate.

**F9. Simplification (P): carry the graph in the translator's bindings instead of regex-correlating SQL text.** The
all-graphs rule is added after translation by regex over join and sub-SELECT text (`translator.py:564-1035`). It took
fixes surface by surface from 2026-10-20 to 2026-11-10 (`56de32f5`, R157, R158, R192, R226/R260 `c3a05900`, R308
`ecc07c57`, R310, R319, `b1af594e`, 4.7.0 row 11, 4.6.1/4.6.2 shortestPath). Proposal: a node binding is `(alias,
graph_expr)` from the start. Every join and sub-SELECT is emitted with the graph equality, and `USE GRAPH` becomes a
binding of `graph_expr` to a literal. Behaviour to keep: the plans IRIS gets when only one graph exists (the reason
`_all_graphs_correlated` skips the predicates, `:783-785`), the LEFT JOIN null-row placement (`:730-733`), and every
row of the e2e write matrix. Distinguishing case: a pattern comprehension or `EXISTS {}` over a node id shared by two
graphs, a spelling the regexes may not match.

**F10. Simplification (P): make Cypher's place relative to the ledger explicit.** Observed: Cypher DML is refused in
strict mode, with a 5 s cached probe (`ledger/guard.py:20`, `:75-80`). Otherwise it is unrecorded. USER_GUIDE
l. 1107-1110 says this for "`create_node`, `create_edge` and the other methods". CONTEXT says a Structural Edge is
"Subject to the revision ledger" (l. 60-63). Proposal: one sentence in USER_GUIDE/CONTEXT that Cypher writes are
outside the ledger (refused under strict). This is a decision for a human, and A-history should confirm whether
`verify()` reports Cypher-written rows.

**F11. Open question: should shadow mode surface a native exception?** FR-007 (fallback) and FR-006 (raise on a
difference) both hold today. In shadow mode a native exception is still answered by SQL with one warning
(`query.py:2144-2152`), so a native defect that raises is invisible to a shadow run, including TCK shadow runs. Shadow
mode also never compares compiled with interpreted. Spec 257 US1's three-way check exists only in
`test_257_compiled_plans_e2e.py`. Options: raise in shadow mode (stricter checks) or keep the fallback (spec as
written).

**F12. Note: a compiled walk that raises falls to SQL, not to the interpreter.** This is consistent with FR-007. Since
the entry stays `ok`, the shape pays a failed native run and a SQL run on every call until a deploy, warned once per
engine. P: mark the entry failed when `Walk1` raises (in `RunA`'s caller), so the interpreter answers next time.

## Not inspected / limits

- Nothing was executed. The suspected findings F1-F4 and F6 come from source reading. Their observable responses
  (error codes, HTTP statuses) are inferred. The orchestrator owns native confirmation.
- Most of `translator.py` (31,908 lines) was not read: expression typing, UNWIND/WITH stages, OPTIONAL MATCH, procedure
  translation, `merge_rows.py`, `count_create.py`, `row_where.py`. The claim that every DML goes through `add_dml`
  rests on its comment (`:2076-2079`) and the call sites read.
- `Exec.cls` parallel split (`Parallel`/`Part`/`Export`, l. 287-590), the sort/trim and `Stage2` paths, `SortKey.cls`,
  `VarLength`, `Adj.Cached` and `native_route.py` past l. 60 were skimmed or not read. Degree cache validity
  (ADR-0012) is A-structure's.
- spec 253 `tasks.md`, spec 257's implementation history, the spec 259 levers and the TCK harness side-effect code
  were not traced. The TCK pass figures are cited from TCK.md, not re-derived.
- The ADR-0016 schema behaviour of the native executor (literal `Graph_KG` in Exec and Props) is noted only. A-platform
  owns it.
- The two Python HTTP apps (`cypher_api` and `api.main`): which one a deployment runs was not settled from the docs
  beyond ADMIN_API.md l. 9.
