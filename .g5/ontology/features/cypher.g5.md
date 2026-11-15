# Cypher

How IVG answers openCypher queries: the SQL path that answers everything, the native executor that answers supported reads faster, the compiled plans that speed up the native executor, and how Cypher applies IVG's graph scope, write and ledger rules.

## Definitions

- **Cypher query**: an openCypher text given to `execute_cypher` or to a server route. A **write** holds `CREATE`, `MERGE`, `SET`, `REMOVE`, `DELETE` or `FOREACH` anywhere in it; any other query is a **read**.
- **SQL path**: translating a query into SQL over the graph tables and running that SQL.
- **Native executor**: code inside IRIS that answers a supported read by walking the adjacency index and reading property rows directly, without SQL joins.
- **Plan**: the description of one read that Python hands the native executor. A **plan shape** is a plan without its parameter values: its hops with their types and directions, each node's labels, which properties it checks and how, and what it returns and groups.
- **Interpreter**: the native executor's general code, which reads the plan step by step as it walks.
- **Compiled plan**: the walk for one plan shape, written out as a class of its own and compiled in the namespace while IVG runs.
- **Shadow mode**: a checking mode that answers a native read on both paths and compares the answers.
- **`USE GRAPH`**: the optional first clause that names the graph a query reads and writes. `USE GRAPH ''` names the default graph.
- **Deploy**: installing IVG's ObjectScript classes into a namespace, as setup (`initialize_schema`) does.
- **Strict mode**: a ledger setting that refuses writes made outside the ledger.
- **TCK**: the openCypher Technology Compatibility Kit, the upstream conformance test suite.

## Two paths

<a id="query.paths"></a>
[D · query.paths]

IVG answers each Cypher query on one of two paths. The SQL path answers every query, including every write; the native executor answers only the reads it fully supports, and the SQL path is the reference it is held to.

- Python plans a native read and IRIS runs it; the native executor never parses Cypher.
- A query the native executor does not support takes the SQL path unchanged.

## Native executor

<a id="query.native"></a>
[D · query.native]

The native executor is on by default wherever the adjacency index is declared. One engine turns it off with `native_cypher=False`, and every engine in a process with `IVG_NATIVE_CYPHER=0`.

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

<a id="query.native.index-current"></a>
[Q · query.native.index-current]

Should a bulk load run by another process close the native path while the adjacency and property indexes lag behind the rows? Provisional answer: no; only the engine's own bulk load session closes it, so equal answers assume the indexes are current.

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

A defect found on the SQL path while building the native executor is fixed on the SQL path first, and the native executor copies the fixed behavior. Both paths preserve the stored node value types described in [values](#query.values), and both retain the documented comparison and sorting limits in [conformance](#query.conformance).

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

## Shadow mode

<a id="query.shadow"></a>
[I · query.shadow]

In shadow mode every read the native executor answers also runs on the SQL path. A difference, or a SQL failure where the native executor answered, is raised as an error naming the query, its parameters and the first differing row; it is never returned as the answer.

- One engine turns it on with `cypher_shadow = True`, and every engine with `IVG_CYPHER_SHADOW=1`.

<a id="query.shadow.native-failure"></a>
[Q · query.shadow.native-failure]

In shadow mode, should a native failure be raised instead of answered by the SQL path? Provisional answer: no; the fallback rule applies in shadow mode too, so a shadow run does not reveal a native defect that raises an error.

## Compiled plans

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

A deploy that installs IVG's classes deletes every compiled plan and its record, and so does an explicit drop of all compiled plans. Nothing else removes them, so a namespace gains one class per distinct shape until the next deploy.

<a id="query.compiled.fallback"></a>
[I · query.compiled.fallback]

The interpreter answers any shape that is not compiled yet, is being compiled, failed to compile, or cannot be recorded by this process. Compiling must never make a read fail.

- A failed compile is logged once and not tried again until the compile stamp changes, which a deploy or a change of the property registry does.
- A plan with no hop is always interpreted.

<a id="query.compiled.integrity"></a>
[D · query.compiled.integrity]

A compiled class runs only for the shape it was written for, and only code the generator itself wrote for that shape is compiled. No user, whether able to write the database or only to run Cypher reads, can make another user's read run other code.

## Graph scope

<a id="query.graph-scope"></a>
[I · query.graph-scope]

Every Cypher read and write follows IVG's graph scope rules, on both paths alike.

- `USE GRAPH g` confines the whole query, its reads and its writes, to graph g.
- `USE GRAPH ''` names the default graph, not every graph.
- With no `USE GRAPH`, reads follow the [all-graphs read](../concepts/graph-scope.g5.md#graph.all_graphs_read) rule and writes follow the [all-graphs write](../concepts/graph-scope.g5.md#graph.all_graphs_write) rule.

<a id="query.graph-scope.read"></a>
[I · query.graph-scope.read]

A Cypher read with no `USE GRAPH` keeps each match inside one graph, through every clause:

- The nodes and relationships of one `MATCH`, including comma-separated patterns, come from one graph.
- A node carried through `WITH` keeps its graph in later clauses.
- Variable-length and shortest-path reads walk each graph on its own.
- A procedure call answers the union of each graph's own answer, or refuses when it cannot answer per graph.

<a id="query.graph-scope.row-graph"></a>
[D · query.graph-scope.row-graph]

A row of an all-graphs read does not say which graph it came from. To label rows by graph, run the query once per graph with `USE GRAPH`.

<a id="query.graph-scope.write"></a>
[I · query.graph-scope.write]

Every Cypher write clause with no `USE GRAPH` follows the [all-graphs write](../concepts/graph-scope.g5.md#graph.all_graphs_write) rule:

- `SET` of a value read from another variable, such as `SET n.p = m.x`, reads it from that row's own graph.
- A relationship `SET`, `DELETE` and `DETACH DELETE` change only the bound rows in their own graph.
- `MERGE` looks for its pattern in the default graph only, and its `ON MATCH` and `ON CREATE` actions change only the default graph's node.

<a id="query.graph-scope.bound-create"></a>
[Q · query.graph-scope.bound-create]

When a write with no `USE GRAPH` creates or merges a relationship between nodes its `MATCH` bound in a named graph, which graph gets the relationship?

- Provisional answer, as built: the default graph, between its nodes of the same IDs; the write is refused when the default graph lacks them.
- Alternative: the bound nodes' own graph, as `SET` and `DELETE` treat bound nodes.

<a id="query.graph-scope.names"></a>
[I · query.graph-scope.names]

`USE GRAPH` refuses a graph name the way every other IVG write does, as [graph names](../concepts/graph-scope.g5.md#graph.names) requires, before anything is read or written.

## Writes

<a id="query.writes"></a>
[I · query.writes]

Every Cypher write runs on the SQL path, and every statement of one write uses the rows its `MATCH` bound before anything was written.

- A later `SET` item, `REMOVE` or `DELETE` in the same query acts on the same matched rows, even when an earlier item changed what the `MATCH` tests.

<a id="query.writes.atomic"></a>
[I · query.writes.atomic]

One Cypher write is one IVG write transaction:

- With no transaction open by the caller, it commits when the call returns.
- Inside the caller's transaction, the caller's commit keeps it and the caller's rollback removes it.
- A write that fails raises `GraphWriteError` and takes back only its own changes.
- A write that runs in steps, such as one `MERGE` per row, is still one transaction.

<a id="query.writes.adjacency"></a>
[I · query.writes.adjacency]

Where the adjacency index is declared, the rows a Cypher write changes update the adjacency and label indexes in the same transaction, so the next read sees the write on either path. Where it is not declared, Cypher writes leave the adjacency stale until a rebuild ([undeclared index](graph-structure.g5.md#structure.adjacency.undeclared)).

<a id="query.writes.ledger"></a>
[D · query.writes.ledger]

Today Cypher writes are not recorded in the ledger. In [strict mode](ledger.g5.md#ledger.strict) they are refused before anything is written; otherwise ledger verification reports them as unrecorded writes. No document decides whether they should be recorded.

<a id="query.writes.subquery"></a>
[I · query.writes.subquery]

A write clause inside a `CALL { }` body is carried out, or the whole query is refused. It is never skipped silently.

<a id="query.writes.create-existing"></a>
[D · query.writes.create-existing]

A node's ID is its identity, so a Cypher `CREATE` of a node whose ID already exists in that graph merges into that node instead of making a second one. The node gains the new labels and any property it lacked, and keeps its old values; to change a value, `SET` it.

<a id="query.writes.delete-scope"></a>
[Q · query.writes.delete-scope]

Should a Cypher `DELETE` clean up everything the engine's own [node delete](graph-structure.g5.md#structure.node.delete) and edge delete clean up? Provisional answer, as built: `DETACH DELETE` removes the node's labels, properties, default-route vector, incident edges and those edges' reifications, but not vectors in other routes or temporal entries. `DELETE r` removes only the relationship row and leaves its reification, the same open question as [edge delete reifications](graph-structure.g5.md#structure.edge.delete.reifications).

## Entry points

<a id="query.read-only"></a>
[I · query.read-only]

`execute_cypher(read_only=True)` refuses any query that may write, before any part of it runs, by the same [parser-based rule](../concepts/access.g5.md#access.read_only.verdict) the servers' read-only mode uses.

- A write clause anywhere counts: a `UNION` branch, a `CALL { }` body, or any statement of a `;`-separated text.
- A text that does not parse is refused too.

<a id="query.routes"></a>
[Q · query.routes]

Should the second HTTP app's Cypher endpoints (`/api/cypher` and GraphQL `executeCypher`) answer through the engine, as the documented server and the Bolt listener do? Provisional answer: yes; today they run the translated SQL themselves.

<a id="query.browser-metadata"></a>
[I · query.browser-metadata]

IVG answers the fixed metadata queries Neo4j Browser sends without running them, and gives those fixed answers to no other query.

## System procedures

<a id="query.system-procedures"></a>
[D · query.system-procedures]

So that Neo4j tools work, IVG answers some Neo4j procedure calls itself, outside SQL.

- `db.*` and `dbms.*` metadata calls, such as `db.labels`, `db.relationshipTypes`, `db.propertyKeys` and `dbms.components`, and `apoc.meta.data` and `apoc.meta.schema`.
- `gds.pageRank.stream`, `gds.betweenness.stream` and `gds.shortestPath.dijkstra.stream`, with GDS's graph-name and configuration arguments; the graph name is not read.
- A `gds.*` call takes after its `YIELD` only a `WHERE` and a `RETURN` of yielded names.
- A `db.*`, `dbms.*` or `apoc.*` call takes after its `YIELD` only a `WHERE`, one `WITH` of yielded names, a `RETURN` of yielded names, `ORDER BY`, `SKIP` and `LIMIT`; any other clause is refused, naming it.
- Another `gds.*` call is refused, naming IVG's own procedure to call instead; `gds.nodeSimilarity.stream` is the exception, passed to IVG's vector search with its arguments as given.

<a id="query.system-procedures.unknown"></a>
[Q · query.system-procedures.unknown]

Should a call to an unknown `apoc.*`, `db.*` or `dbms.*` procedure be refused, as an unknown `ivg.*` or `gds.*` procedure is? Provisional answer, as built: it answers no rows and no error.

## Conformance

<a id="query.conformance"></a>
[D · query.conformance]

IVG holds its Cypher to the openCypher TCK and lists each known deviation in its known-issues guide. Notable deviations:

- Outside multigraph mode, `CREATE` of a relationship that already exists between two nodes adds nothing.
- The headline TCK figure is measured with multigraph mode on; with it off, the scenarios that need two relationships of one type between one pair fail.
- A `CALL { }` subquery's columns come first in the result.
- `MERGE ... ON CREATE SET n = {...}` and `ON MATCH SET n = {...}` on a node are refused.
- A relationship property computed from the row is refused when creating between matched nodes.
- Node reads distinguish a stored number from the string spelling it, and node filters use that stored type from 4.7.0. Earlier Python writes stored numbers as text; setup does not retype them. Relationship qualifier text still loses the number/string distinction, and its decoder follows [relationship text](#query.values.relationship_text).
- Sorting and arithmetic still coerce numeric-looking text, on nodes and relationships; typed reads do not remove those documented deviations.
- Two `OPTIONAL MATCH` variable-length shapes are refused, and a variable-length read from a large hub can exceed IRIS's string limit.
- A `CREATE` or `MERGE` after `UNWIND $p AS e WITH e` fails.

## Values in results

<a id="query.values"></a>
[D · query.values]

A node property read preserves its stored numeric type: a D-marked IRIS double becomes a Python float, and an N-marked integer becomes an int (a fractional or exponent N spelling becomes a float). Unmarked numeric-looking node text stays text; a string beginning with the mark is escaped with S and unwrapped once, so its contents are not decoded again.

- Since 4.6.4 the Python node writers bind signed 64-bit integers and finite floats as numbers; booleans become `true`/`false` text, lists and maps JSON text, and larger integers and nonfinite floats text. Earlier Python numeric text stays text after setup. The engine's node read API decodes stored booleans and valid JSON lists/maps; a string spelling a list/map also reads as one.
- `CY_TYPED` decides the tag from the stored IRIS value, rather than the driver's column type. SQL result decoding and the node read API consume that tag. The [batched node reader](graph-structure.g5.md#structure.node.read) also protects its structural keys.
- Relationship properties are stored in qualifier text and follow their separately owned decoder; preserving a node's stored type does not establish that relationship values preserve their original type.

<a id="query.values.relationship_text"></a>
[I · query.values.relationship_text]

A relationship property read in a Cypher result is decoded from its stored text. `true` and `false` become booleans, canonical integer text becomes an integer, canonical decimal text becomes a float, list or map text becomes a list or map, and any other text stays the string it is.
- Canonical integer text is an optional minus sign, then `0` or a digit 1 to 9 followed by more digits. Canonical decimal text adds a point and at least one digit.
- So `01`, `+1`, `1.`, `.5`, `1e5` and text with spaces stay text. `True`, `1` and `0` are not booleans here; `1` and `0` become integers.
- Only the columns the translator marks as relationship property reads are decoded, and only when the row has as many values as the result has columns.
- Today a text with one trailing line break, or with non-ASCII digits after its first digit, is also read as a number: `"12\n"` and `"1٢"` both read back as 12.

## Metadata

### query.paths
- agent
- architecture-decision, user-facing-behavior

Sources: [CONTEXT.md, Query execution](../../../CONTEXT.md#L224-L232), [spec 253, decisions of 2026-10-20 and FR-001](../../../specs/253-native-cypher-executor/spec.md#L14-L18), [USER_GUIDE, Where a query runs](../../../docs/USER_GUIDE.md#L350-L368), [`_execute_parsed`](../../../iris_vector_graph/_engine/query.py#L2032-L2082). Note: USER_GUIDE says "the one known difference between the paths is listed in Known issues", and no such entry is named there.

Provenance: spec 253 is still "Draft" and its "Decided 2026-10-20" lines name no decider, so under the uplift's authority rule ([sources](../../uplift/ivg-verus-initial/sources.md)) the block is `agent` (review round 3 R3-reader M16).

### query.native
- agent
- architecture-decision, operations
- Children: [gates](#query.native.gates), [privileges](#query.native.privileges), [index currency](#query.native.index-current), [reads only](#query.native.reads-only), [equal answers](#query.native.equal-answers), [SQL first](#query.native.sql-first), [fallback](#query.native.fallback), [route](#query.native.route).

Sources: [spec 253 decisions and FR-005, FR-010](../../../specs/253-native-cypher-executor/spec.md#L14-L18), [engine options](../../../iris_vector_graph/engine.py#L290-L317). The default was to flip only after a shadow run matched the SQL path on the full TCK and the 40 SNB queries; [TCK.md](../../../docs/dev/TCK.md#L215-L232) records the shadow run.

Provenance: spec 253 is still "Draft" and its "Decided 2026-10-20" lines name no decider, so under the uplift's authority rule ([sources](../../uplift/ivg-verus-initial/sources.md)) the block is `agent` (review round 3 R3-reader M16).

### query.native.gates
- agent
- operations, data-integrity
- test-coverage
- Expands: [Native executor](#query.native).

Sources: [spec 253 FR-003, FR-005, FR-011, FR-014](../../../specs/253-native-cypher-executor/spec.md#L98-L140), [`native_gate`](../../../iris_vector_graph/cypher/native_plan.py#L524-L536), [plan version check](../../../iris_src/src/Graph/KG/Cypher/Exec.cls#L13-L41), [mapped labels decline](../../../iris_vector_graph/_engine/query.py#L2162-L2184). Live: [`test_253_executor_version_e2e.py`](../../../tests/e2e/test_253_executor_version_e2e.py); the other gates are covered by mocked unit tests ([`test_253_native_gates.py`](../../../tests/unit/test_253_native_gates.py)). The engine caches the index, privilege and version answers until setup runs again.

### query.native.privileges
- agent
- security
- Expands: [Native executor](#query.native).

Sources: [spec 253 FR-011, decided 2026-10-20](../../../specs/253-native-cypher-executor/spec.md#L124-L127), [`_native_privileges`](../../../iris_vector_graph/engine.py#L559-L586). The check is a SELECT probe per engine rather than the per-process `CheckPrivilege` the FR names.

Provenance: spec 253 is still "Draft" and its "Decided 2026-10-20" lines name no decider, so under the uplift's authority rule ([sources](../../uplift/ivg-verus-initial/sources.md)) the block is `agent` (review round 3 R3-reader M16).

### query.native.index-current
- agent
- uncertain
- data-integrity, operations
- Expands: [Native executor](#query.native).

Sources: [spec 253 FR-014 and research §H](../../../specs/253-native-cypher-executor/research.md#L80-L86), [`BulkLoader` loads without index maintenance and rebuilds after](../../../iris_vector_graph/bulk_loader.py#L1-L12), [A-cypher notes, F7](../../uplift/ivg-verus-initial/intent/cypher.md#candidate-findings). The bulk loads themselves belong to the install page.

Findings: [Should a bulk load by another process close the native query path while indexes lag the rows?](../../Verus_verification/open_questions.md#q-cyp-003)

### query.native.reads-only
- agent
- data-integrity, architecture-decision
- Expands: [Native executor](#query.native).

Sources: [spec 253 decisions and FR-001, edge cases](../../../specs/253-native-cypher-executor/spec.md#L83-L99), [`plan_query`](../../../iris_vector_graph/cypher/native_plan.py#L50-L87), [`_try_native` declines a transactional translation](../../../iris_vector_graph/_engine/query.py#L2118-L2160). Three independent checks keep writes off the native path; the planner unit test lists the declined write clauses.

Provenance: spec 253 is still "Draft" and its "Decided 2026-10-20" lines name no decider, so under the uplift's authority rule ([sources](../../uplift/ivg-verus-initial/sources.md)) the block is `agent` (review round 3 R3-reader M16).

### query.native.equal-answers
- agent
- user-facing-behavior, data-integrity
- test-coverage
- Expands: [Native executor](#query.native).

Sources: [spec 253 FR-002, FR-012 (equality decided 2026-10-20), FR-013](../../../specs/253-native-cypher-executor/spec.md#L100-L137), [`native_shadow.compare`](../../../iris_vector_graph/cypher/native_shadow.py#L29-L69). Live: the family A and B end-to-end tests run in shadow mode ([`test_253_family_b_e2e.py`](../../../tests/e2e/test_253_family_b_e2e.py)). Model note: equality assumes the indexes are current ([index currency](#query.native.index-current)).

Findings: [The native interpreter tells used relationships apart by CRC-32, so a hash collision drops a legitimate match](../../Verus_verification/bugs_issues.md#bug-cyp-002)

Provenance: spec 253 is still "Draft" and its "Decided 2026-10-20" lines name no decider, so under the uplift's authority rule ([sources](../../uplift/ivg-verus-initial/sources.md)) the block is `agent` (review round 3 R3-reader M16).

### query.native.sql-first
- agent
- architecture-decision
- Expands: [Native executor](#query.native).

Sources: [spec 253 FR-012](../../../specs/253-native-cypher-executor/spec.md#L129-L134).

Provenance: spec 253 is still "Draft" and its "Decided 2026-10-20" lines name no decider, so under the uplift's authority rule ([sources](../../uplift/ivg-verus-initial/sources.md)) the block is `agent` (review round 3 R3-reader M16).

### query.native.fallback
- agent
- user-facing-behavior, operations
- Expands: [Native executor](#query.native).

Sources: [spec 253 US4 and FR-007](../../../specs/253-native-cypher-executor/spec.md#L71-L81), [`_try_native`](../../../iris_vector_graph/_engine/query.py#L2144-L2152), [`Exec.Run`](../../../iris_src/src/Graph/KG/Cypher/Exec.cls#L32-L52).

### query.native.route
- Playbook: [NAT-T7](../../../experiment/playbook-completion/ontology/09-native-executor.md)
- Verus: [route_recheck](../../Verus_verification/models/route_recheck/NOTES.md), as-built held-call recheck/reset and permanent SQL-failure rules; trial medians, drift selection and SQL/native answer equality remain unmodeled.
- agent
- architecture-decision
- Expands: [Native executor](#query.native).

Sources: [`native_route.py`](../../../iris_vector_graph/cypher/native_route.py#L1-L16), [`_execute_parsed`](../../../iris_vector_graph/_engine/query.py#L2063-L2104). Shadow mode skips the route.

### query.shadow
- agent
- data-integrity, operations
- test-coverage
- Children: [native failure](#query.shadow.native-failure).

Sources: [CONTEXT.md, Shadow mode](../../../CONTEXT.md#L234-L236), [spec 253 FR-006](../../../specs/253-native-cypher-executor/spec.md#L107-L108), [`_shadow_compare`](../../../iris_vector_graph/_engine/query.py#L2226-L2249), [TCK.md, how the native path is held to the SQL path](../../../docs/dev/TCK.md#L258-L271). Shadow mode compares native with SQL only; compiled against interpreted is checked by the compiled-plan tests.

### query.shadow.native-failure
- agent
- uncertain
- data-integrity
- Expands: [Shadow mode](#query.shadow).

Sources: [spec 253 FR-006 and FR-007](../../../specs/253-native-cypher-executor/spec.md#L107-L110), [`_try_native`](../../../iris_vector_graph/_engine/query.py#L2144-L2152), [A-cypher notes, F11](../../uplift/ivg-verus-initial/intent/cypher.md#candidate-findings).

Findings: [In shadow mode, should a native failure be raised instead of answered by SQL?](../../Verus_verification/open_questions.md#q-cyp-002)

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

### query.compiled.modes
- Verus: see [compiled fallback](#query.compiled.fallback): `proofs-d1d` `planc_l2` (reviewed design) is active for job-mode answers during a build (public J08); `G-platform` (as-built) overlaps for stamps.
- agent
- operations
- test-coverage
- Expands: [Compiled plans](#query.compiled).

Sources: [ADR-0014 decision and consequences](../../../docs/adr/0014-native-plans-are-compiled-to-classes-at-run-time.md#L16-L18), [ADMIN_GUIDE, Compiled native plans](../../../docs/ADMIN_GUIDE.md#L742-L780), [`Gen.Mode`, `Effective`, `ModeOf`](../../../iris_src/src/Graph/KG/Cypher/Gen.cls#L26-L50). Live: the job-mode test in `test_257_compiled_plans_e2e.py`.

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

### query.compiled.fallback
- Playbook: [NAT-B5.1](../../../experiment/playbook-completion/ontology/09-native-executor.md#L172), [NAT-T5.1](../../../experiment/playbook-completion/ontology/09-native-executor.md#L173)
- Verus: active for failed and pending builds answering through the interpreter (public J08, M20): the playbook's `proofs-d1d` [`planc_l2.rs`](../../../experiment/playbook-completion/proofs-d1d/src/planc_l2.rs) `theorem_ok_entry_runs_its_shapes_class`, `lemma_bcompile`, `lemma_for` (**reviewed design**; controls `control_f0901_shared_class_name`, `control_fc0901_mark_any_entry`, rerun here). Overlapping: `G-platform` (as-built) [`platform.rs`](../../Verus_verification/models/platform/platform.rs) stamps and eligibility (`witness_compiled_plan_is_used`).
- agent
- user-facing-behavior, operations
- test-coverage
- Expands: [Compiled plans](#query.compiled).

Sources: [ADR-0014](../../../docs/adr/0014-native-plans-are-compiled-to-classes-at-run-time.md#L19-L20), [spec 257 US3](../../../specs/257-compiled-native-plans/spec.md#L60-L63), [`Exec.RunA` catches a failed lookup](../../../iris_src/src/Graph/KG/Cypher/Exec.cls#L153-L166), [`Gen.For`, `Build`](../../../iris_src/src/Graph/KG/Cypher/Gen.cls#L61-L222). Live: the failed-build, unrecordable shape and generator-failure tests in `test_257_compiled_plans_e2e.py`. A compiled class that fails while it runs falls to the SQL path under [native fallback](#query.native.fallback), and its shape keeps doing so until a deploy ([A-cypher notes, F12](../../uplift/ivg-verus-initial/intent/cypher.md#candidate-findings)).

Findings: [A build job queued before a layout change can leave a shape interpreted until the next change](../../Verus_verification/bugs_issues.md#bug-cyp-009); [Mark a compiled entry failed when its walk raises, so the interpreter answers next time](../../Verus_verification/design_simplification.md#simp-cyp-003)

### query.compiled.integrity
- agent
- security, data-integrity
- test-coverage
- Expands: [Compiled plans](#query.compiled).

Sources: [ADR-0014](../../../docs/adr/0014-native-plans-are-compiled-to-classes-at-run-time.md#L16-L23), [`Gen.For` hash, entry checks and pending write](../../../iris_src/src/Graph/KG/Cypher/Gen.cls#L69-L101), [`Gen.Build` digest check](../../../iris_src/src/Graph/KG/Cypher/Gen.cls#L163-L207), [ADMIN_GUIDE, writer roles](../../../docs/ADMIN_GUIDE.md#L600-L622), [review round 1, R1-3](../../uplift/ivg-verus-initial/review/round1-platform.md). Live: [`test_460_r311_writer_role_e2e.py`](../../../tests/e2e/test_460_r311_writer_role_e2e.py) covers planted lines from a writer, not colliding shapes. Observed divergence: a class is named by a 32-bit CRC of its shape and `Build` checks only the lines' digest, so when two colliding shapes are first run close together the entry can record one shape over the other shape's compiled walk, and that shape's reads then answer wrongly until a deploy, a stamp change or the other shape runs again (source reading; accidental odds about 1e-4 at 1,000 distinct shapes and 1% at 10,000). Suspected exploit, not run: a caller with only Cypher read access, on a server whose IRIS login can write the database, can craft a colliding shape (the CRC is affine and label and property names are free text) and repeat both reads until that ordering lands, persistently corrupting another caller's answers; proposed fixes are SHA-256 or sequence class names and a shape check in `Build` ([A-cypher notes, F2](../../uplift/ivg-verus-initial/intent/cypher.md#candidate-findings)).

Findings: [A caller with Cypher read access can forge a CRC-32 collision so that another shape's queries run its compiled code](../../Verus_verification/bugs_issues.md#bug-cyp-001); [The compiled-plan read-back after a synchronous build skips the class-name check](../../Verus_verification/bugs_issues.md#bug-cyp-008); [Name each compiled Cypher class by its code's digest instead of the shape's CRC-32](../../Verus_verification/design_simplification.md#simp-cyp-001)

### query.graph-scope
- human-verified
- user-facing-behavior, data-integrity
- Children: [reads](#query.graph-scope.read), [row graph](#query.graph-scope.row-graph), [writes](#query.graph-scope.write), [bound create](#query.graph-scope.bound-create), [names](#query.graph-scope.names).

Sources: [CONTEXT.md, All-graphs read and write](../../../CONTEXT.md#L38-L48), [USER_GUIDE section 4](../../../docs/USER_GUIDE.md#L321-L330), [`USE GRAPH ''` scopes the default graph](../../../iris_vector_graph/cypher/translator.py#L5647-L5666). The rules themselves are owned by the graph scope page; this block states only that Cypher applies them.

### query.graph-scope.read
- human-verified
- user-facing-behavior, data-integrity
- test-coverage
- Expands: [Graph scope](#query.graph-scope).

Sources: [CONTEXT.md, All-graphs read, decided 2026-10-20](../../../CONTEXT.md#L38-L42), [spec 253 FR-009](../../../specs/253-native-cypher-executor/spec.md#L116-L120), [SQL path correlation](../../../iris_vector_graph/cypher/translator.py#L898-L1035), [native per-graph walk](../../../iris_src/src/Graph/KG/Cypher/Exec.cls#L832-L904). Live: [`test_253_all_graphs_read_e2e.py`](../../../tests/e2e/test_253_all_graphs_read_e2e.py), [`test_460_r192_all_graphs_procedures_e2e.py`](../../../tests/e2e/test_460_r192_all_graphs_procedures_e2e.py), [`test_461_shortest_path_all_graphs_e2e.py`](../../../tests/e2e/test_461_shortest_path_all_graphs_e2e.py). The TCK runs in one graph and does not exercise this rule. Observed divergence: the SQL path skips the per-graph joins when the node table holds one graph, though property rows of another graph can remain without a node row ([A-cypher notes, F6](../../uplift/ivg-verus-initial/intent/cypher.md#candidate-findings)).

Findings: [An all-graphs read skips graph correlation when only the nodes table looks single-graph](../../Verus_verification/bugs_issues.md#bug-cyp-005); [Carry each node binding's graph through Cypher translation instead of correlating graphs by regex afterwards](../../Verus_verification/design_simplification.md#simp-cyp-002)

### query.graph-scope.row-graph
- agent
- user-facing-behavior
- Expands: [Graph scope](#query.graph-scope).

Sources: [KNOWN_ISSUES, a query over every graph cannot say which graph a row came from](../../../docs/KNOWN_ISSUES.md#L43-L66).

### query.graph-scope.write
- human-verified
- user-facing-behavior, data-integrity
- test-coverage
- Expands: [Graph scope](#query.graph-scope).

Sources: [CONTEXT.md, All-graphs write, decided 2026-11-06](../../../CONTEXT.md#L44-L48), [USER_GUIDE section 4](../../../docs/USER_GUIDE.md#L324-L329), [CHANGELOG 4.6.0 fixes](../../../CHANGELOG.md#L1700-L1745), [`add_dml` and per-graph captures](../../../iris_vector_graph/cypher/translator.py#L2075-L2127), [per-graph statement expansion](../../../iris_vector_graph/stores/iris_sql_store.py#L185-L211). Live: [`test_460_all_graphs_writes_e2e.py`](../../../tests/e2e/test_460_all_graphs_writes_e2e.py), native on and off. Before 4.6.0 an unscoped write also changed other graphs' nodes of the same ID.

### query.graph-scope.bound-create
- agent
- uncertain
- user-facing-behavior, data-integrity
- Expands: [Graph scope](#query.graph-scope).

Sources: [CONTEXT.md, All-graphs write](../../../CONTEXT.md#L44-L48), [relationship insert uses the default graph](../../../iris_vector_graph/cypher/translator.py#L10351-L10365), [edge foreign keys to `(graph_id, node_id)`](../../../iris_vector_graph/schema.py#L38-L45), [A-cypher notes, F5](../../uplift/ivg-verus-initial/intent/cypher.md#candidate-findings). No test covers this case.

Findings: [When a write without USE GRAPH creates a relationship between nodes its MATCH bound in a named graph, which graph gets it?](../../Verus_verification/open_questions.md#q-cyp-001)

### query.graph-scope.names
- agent
- data-integrity
- Expands: [Graph scope](#query.graph-scope).

Sources: [`GraphKey.Validate`](../../../iris_src/src/Graph/KG/GraphKey.cls#L23-L48), [`validate_graph_name`](../../../iris_vector_graph/_validate.py#L19-L45), [`USE GRAPH` parsing](../../../iris_vector_graph/cypher/parser.py#L174-L192). Observed divergence: the Cypher path does not validate the name, so a label-free node can be written under graph `"0"` while label and edge writes there fail in the index ([A-cypher notes, F8](../../uplift/ivg-verus-initial/intent/cypher.md#candidate-findings)).

Findings: [USE GRAPH accepts graph names the graph keys refuse](../../Verus_verification/bugs_issues.md#bug-cyp-006)

### query.writes
- agent
- user-facing-behavior, data-integrity
- test-coverage
- Children: [atomic](#query.writes.atomic), [adjacency](#query.writes.adjacency), [ledger](#query.writes.ledger), [subquery](#query.writes.subquery), [create existing](#query.writes.create-existing), [delete scope](#query.writes.delete-scope).

Sources: [CHANGELOG 4.6.0, every statement uses the rows its MATCH bound](../../../CHANGELOG.md#L1742-L1744), [spec 229](../../../specs/229-tck-write-verification/spec.md), [`_write_ids`, `_capture_key`](../../../iris_vector_graph/cypher/translator.py#L13093-L13164), [`execute_transaction`](../../../iris_vector_graph/stores/iris_sql_store.py#L1580-L1818). Live: the TCK's write scenarios with side-effect counting, and `test_460_all_graphs_writes_e2e.py`.

### query.writes.atomic
- agent
- user-facing-behavior, data-integrity
- test-coverage
- Expands: [Writes](#query.writes).

Sources: [CHANGELOG 4.6.4](../../../CHANGELOG.md#L410-L425), [USER_GUIDE, Writes inside your transaction](../../../docs/USER_GUIDE.md#L236-L272), [`_execute_cypher_write`](../../../iris_vector_graph/_engine/query.py#L1946-L1967). Live: [`test_464_caller_txn_e2e.py`](../../../tests/e2e/test_464_caller_txn_e2e.py) (Cypher CREATE, MERGE, SET, DELETE). A rolled-back write leaves two counters raised; the structure page owns that detail.

### query.writes.adjacency
- agent
- data-integrity
- test-coverage
- Expands: [Writes](#query.writes).

Sources: [ADR-0008](../../../docs/adr/0008-the-adjacency-index-is-maintained-by-the-engine.md#L14-L15), [CONTEXT.md, Adjacency Index](../../../CONTEXT.md#L89-L95). Live: [`test_252_cypher_read_after_write_e2e.py`](../../../tests/e2e/test_252_cypher_read_after_write_e2e.py). The structure page owns how the index is kept; no Cypher code writes it directly.

### query.writes.ledger
- agent
- uncertain
- data-integrity, architecture-decision
- test-coverage
- Expands: [Writes](#query.writes).

Sources: [USER_GUIDE, writes outside the ledger](../../../docs/USER_GUIDE.md#L1107-L1110), [`_ledger_check` before each write batch](../../../iris_vector_graph/_engine/query.py#L2299-L2303), [`LedgerGuard`](../../../iris_vector_graph/ledger/guard.py#L20-L80). Live: [`test_ledger_us05_compat.py`](../../../tests/integration/test_ledger_us05_compat.py). CONTEXT.md says structural edges are "subject to the revision ledger" ([CONTEXT.md](../../../CONTEXT.md#L56-L59)); stage-A F10 left the decision to a human (review round 3 R3-reader M15). The guides name the engine's write methods, not Cypher, and the strict setting is re-read at most every 5 seconds; the [ledger strict rule](ledger.g5.md#ledger.strict) and [strict-mode surfaces](../concepts/access.g5.md#access.ledger_strict) own the general rule ([A-cypher notes, F10](../../uplift/ivg-verus-initial/intent/cypher.md#candidate-findings)).

Findings: [The glossary says structural edges are subject to the ledger, but Cypher writes are never recorded](../../Verus_verification/bugs_issues.md#bug-doc-012)

### query.writes.subquery
- agent
- data-integrity, user-facing-behavior
- Expands: [Writes](#query.writes).

Sources: [read-only rule counts a `CALL { }` body's write](../../../iris_vector_graph/cypher/ast.py#L535-L550), [subquery translation](../../../iris_vector_graph/cypher/translator.py#L14561-L14703), [clause dispatch](../../../iris_vector_graph/cypher/translator.py#L5134-L5136), [reconstruction check 2(a)15 and correction 22](../../uplift/ivg-verus-initial/reconstruction-check.md). Native probe ([receipt](../../Verus_verification/receipts/native/cypher_subquery_write.json), current probe re-run): `CALL { CREATE ... } RETURN 1` writes nothing and returns IRIS's raw SQL syntax error (SQLCODE -12) in the result's error field, while a plain `CREATE` control writes its node. That meets this block, but the refusal is returned rather than raised as the `GraphWriteError` of [atomic writes](#query.writes.atomic), and the strict-mode check is never reached. The subquery translation reads only the body's `MATCH`, `WHERE` and `UNWIND` clauses, so a silent drop when the body's `RETURN` reads only matched variables is still suspected from source reading and not observed ([review round 1, R1-10](../../uplift/ivg-verus-initial/review/round1-platform.md)); KNOWN_ISSUES does not list either case.

Findings: [A write inside CALL { } is refused with a raw SQL syntax error instead of a clear refusal](../../Verus_verification/bugs_issues.md#bug-cyp-004)

### query.writes.create-existing
- agent
- user-facing-behavior, data-integrity
- Expands: [Writes](#query.writes).

Sources: [USER_GUIDE, a node's ID is its identity](../../../docs/USER_GUIDE.md#L142-L147), [CHANGELOG 4.6.5](../../../CHANGELOG.md#L359-L362), [reconstruction check 2(a)15](../../uplift/ivg-verus-initial/reconstruction-check.md). `create_node` returns False and adds nothing for an existing ID, and `store_node` replaces properties; the structure page owns those.

### query.writes.delete-scope
- agent
- uncertain
- data-integrity
- Expands: [Writes](#query.writes).

Sources: [`translate_delete_clause`](../../../iris_vector_graph/cypher/translator.py#L10625-L10803), [node delete](graph-structure.g5.md#structure.node.delete), [reconstruction check 2(a)15](../../uplift/ivg-verus-initial/reconstruction-check.md). Read in the translator: a node delete removes labels, properties, `kg_NodeEmbeddings`, reifier links and the node row; `DETACH DELETE` also removes incident edges and their reifications; `DELETE r` removes only the `rdf_edges` row. Ledger tuple entries are the ledger's ([query.writes.ledger](#query.writes.ledger)).

Findings: [Deleting a relationship with delete_edge or Cypher DELETE leaves its reifications, edge embeddings and ledger statement behind](../../Verus_verification/bugs_issues.md#bug-str-013)

### query.read-only
- agent
- security, user-facing-behavior
- test-coverage

Sources: [`writes_cypher`](../../../iris_vector_graph/cypher/read_only.py#L92-L104), [`execute_cypher`](../../../iris_vector_graph/_engine/query.py#L1746-L1791). Live: [`test_read_only_bypass_e2e.py`](../../../tests/e2e/test_read_only_bypass_e2e.py). Before 4.6.0 the servers matched keywords in the raw text. The rule and its server routes are owned by [access.read_only](../concepts/access.g5.md#access.read_only) and [its verdict](../concepts/access.g5.md#access.read_only.verdict).

### query.routes
- agent
- uncertain
- security, data-integrity

Sources: [`api/routers/cypher.py`](../../../api/routers/cypher.py#L94-L166), [`api/gql/schema.py`](../../../api/gql/schema.py#L150-L200), [documented server](../../../docs/ADMIN_API.md#L1-L10), [A-cypher notes, F3](../../uplift/ivg-verus-initial/intent/cypher.md#candidate-findings). Those endpoints skip the engine's write handling (so deletes and multi-graph writes should fail), the ledger check, the native path and value decoding. Under strict mode the REST route commits Cypher writes unrecorded: [access.ledger_strict.bypasses](../concepts/access.g5.md#access.ledger_strict.bypasses) (observed).

Findings: [The sample API's Cypher endpoints run translated SQL on a raw cursor, bypassing strict mode and the engine's statement protocol](../../Verus_verification/bugs_issues.md#bug-plt-005)

### query.browser-metadata
- agent
- user-facing-behavior

Sources: [`execute_cypher` shortcuts](../../../iris_vector_graph/_engine/query.py#L1807-L1856), [`answered_without_parsing`](../../../iris_vector_graph/cypher/read_only.py#L53-L58). Observed divergence: two shortcuts match on words anywhere in the text (for example `RETURN DISTINCT`, `UNION ALL` and `ENTITY`), so other reads get the fixed answers, ignoring `USE GRAPH` ([A-cypher notes, F4](../../uplift/ivg-verus-initial/intent/cypher.md#candidate-findings)).

Findings: [Text shortcuts meant for Neo4j Browser answer unrelated queries with canned rows](../../Verus_verification/bugs_issues.md#bug-cyp-003)

### query.system-procedures
- agent
- user-facing-behavior
- test-coverage
- Children: [unknown names](#query.system-procedures.unknown).

Sources: [USER_GUIDE, procedures](../../../docs/USER_GUIDE.md#L803-L821), [handler table](../../../iris_vector_graph/engine.py#L944-L966), [`_try_system_procedure`](../../../iris_vector_graph/engine.py#L1676-L1722), [GDS answers and shims](../../../iris_vector_graph/_engine/query.py#L650-L705), [reconstruction check G25 and correction 21](../../uplift/ivg-verus-initial/reconstruction-check.md). Live: [`test_460_r314_call_yield_values_e2e.py`](../../../tests/e2e/test_460_r314_call_yield_values_e2e.py). The `ivg.*` procedures are IVG's own and are not covered here; `gds.louvain.stream` maps to `ivg.leiden`, which no handler answers, so it is refused too.

### query.system-procedures.unknown
- agent
- uncertain
- user-facing-behavior
- Expands: [System procedures](#query.system-procedures).

Sources: [`_try_system_procedure` answers an unknown `apoc.`, `db.` or `dbms.` name with no rows](../../../iris_vector_graph/engine.py#L1716-L1720), [unknown `ivg.*` raises](../../../iris_vector_graph/cypher/translator.py#L2265-L2270), [unknown `gds.*` answers an error](../../../iris_vector_graph/_engine/query.py#L682-L695). The empty answers date from the Bolt server and graph browser release; no source says why an unknown name should succeed.

Findings: [Should a call to an unknown apoc, db or dbms procedure be refused?](../../Verus_verification/open_questions.md#q-cyp-005)

### query.conformance
- agent
- user-facing-behavior
- test-coverage

Sources: [TCK.md](../../../docs/dev/TCK.md#L157-L256), [KNOWN_ISSUES, application developers](../../../docs/KNOWN_ISSUES.md#L23-L117), [KNOWN_ISSUES, untyped values](../../../docs/KNOWN_ISSUES.md#L183-L190), [KNOWN_ISSUES, variable-length limits](../../../docs/KNOWN_ISSUES.md#L452-L481), [KNOWN_ISSUES, UNWIND then CREATE](../../../docs/KNOWN_ISSUES.md#L585-L596), [spec 229](../../../specs/229-tck-write-verification/spec.md). Recorded runs: 3896 of 3896 eligible scenarios at 4.6.0 with multigraph on and the native executor on; seven fail with multigraph off. The TCK at the pinned revision has no `CALL { }` write scenarios, and a dropped `CALL { }` write is not a listed deviation: it is held to [query.writes.subquery](#query.writes.subquery) instead.

Findings: [A write inside CALL { } is refused with a raw SQL syntax error instead of a clear refusal](../../Verus_verification/bugs_issues.md#bug-cyp-004); [Does a Cypher path value come back as JSON text or as a map, and may that depend on the driver or execution path?](../../Verus_verification/open_questions.md#q-cyp-004)

### query.values
- Sources: [`iris_vector_graph/prop_values.py`](../../../iris_vector_graph/prop_values.py#L1-L77) (the typed-values contract, 4.6.0 R308 and R310)
- Children: [relationship property text](#query.values.relationship_text)
- Verus: [node_read](../../Verus_verification/models/node_read/NOTES.md), as-built numeric writer, D/N tag selection, S escape and numeric/text read distinctions. The scalar node-property projection reaches the final result in `theorem_sql_scalar_read_reaches_result`; JSON/J tags, N fractional/exponent parsing, nonfinite values, mixed expressions and the remaining SQL finishing pipeline are open modeling gaps. Numeric spelling/parse identity in `CY_TYPED` is an inspected provider premise, not a proved IRIS function.
- agent
- user-facing-behavior

New owner in the consolidated uplift. Node values and the typed-value marks are the playbook's `CYP-B17` family.

### query.values.relationship_text
- Sources: [`iris_vector_graph/prop_values.py::parse_rel_prop_text`](../../../iris_vector_graph/prop_values.py#L141-L168), [`::parse_prop_text`](../../../iris_vector_graph/prop_values.py#L129-L138), [`::decode_json_list_map`](../../../iris_vector_graph/prop_values.py#L234-L248), the two patterns [`_CANONICAL_INT_RE`, `_CANONICAL_FLOAT_RE`](../../../iris_vector_graph/prop_values.py#L90-L91); [`iris_vector_graph/_engine/query.py::_decode_rel_prop_text_columns`](../../../iris_vector_graph/_engine/query.py#L1200-L1216) (arity guard `:1207`); [`iris_vector_graph/cypher/translator.py::_rel_prop_text_columns`](../../../iris_vector_graph/cypher/translator.py#L7517-L7556); unit tests [test_relationship_property_typing.py](../../../tests/unit/test_relationship_property_typing.py)
- Playbook: no statement for this decoder in either arm; neighbor [CYP-B17.1](../../../experiment/playbook-completion/ontology/08-cypher-sql.md#L307) (finding F-0811: no 64-bit cap on this path)
- Verus: see [rel_prop_text](../../Verus_verification/models/rel_prop_text/NOTES.md) (`theorem_decode_classes`, `theorem_noncanonical_stays_text`; reviewed design over ASCII text; control `leading-zero-canonical`). The as-built divergence is recorded as a finding and is observed at unit level on the real function.
- Expands: [Values in results](#query.values)
- agent
- user-facing-behavior, data-integrity
- test-coverage

Public case M18. The canonical rule is the decoder's own docstring and patterns; Python's `\d` also matches non-ASCII digits and `$` matches before a final line break, which is where the pin departs from it.

Findings: [Relationship property text with a trailing line break or non-ASCII digits is read back as a number](../../Verus_verification/bugs_issues.md#bug-cyp-101)
