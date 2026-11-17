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

## AQL translation


<a id="query.paths.varlength"></a>
[I · query.paths.varlength]

A variable-length pattern returns one row per path, as openCypher does, on both paths: from `a` over `a→x→b`, `a→y→b` and `a→b`, `-[:R*1..2]->(t)` returns `b` three times and `x` and `y` once each, `*2..2` returns `b` twice, and `*0..1` includes `a` itself. The ends-only walk the SQL functions use for low bounds keeps these counts.


<a id="query.aql"></a>
[I · query.aql]

`execute_aql` translates AQL into Cypher and passes that text and its bindings to the Cypher reader. For traversal depth, a single integer becomes equal lower and upper bounds; `1..2` keeps both integer bounds, while a decimal depth raises `AQLParseError` before execution.

- Against a literal null on the right, equality becomes `IS NULL` and inequality becomes `IS NOT NULL`. The string `"null"` stays a string comparison, and other operators keep their comparison form.
- This is a translation contract. It does not prove traversal results, Cypher null semantics, bound-parameter null rewriting or the whole AQL language.

## Native executor


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

- Working assumption: yes; today they run the translated SQL themselves.


## Shadow mode


<a id="query.shadow"></a>
[I · query.shadow]

In shadow mode every read the native executor answers also runs on the SQL path. A difference, or a SQL failure where the native executor answered, is raised as an error naming the query, its parameters and the first differing row; it is never returned as the answer.

- One engine turns it on with `cypher_shadow = True`, and every engine with `IVG_CYPHER_SHADOW=1`.

- Working assumption: Keep SQL fallback as the current shadow behavior; fail-fast diagnostic mode remains an unratified alternative.
- Working assumption: Keep ordinary SQL fallback. In shadow validation, record a native exception as an unsuccessful comparison: raise in shadow mode, or count failures and report them at the end of the run. Require a clean comparison (not a fallback) before claiming parity. The FR-010 default flip and the 3896/3896 figure establish only that no compared answer differed.


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

- Working assumption: Treat a run-time failure of a compiled entry as a fallback outcome: quarantine the entry for that plan generation (as a failed build already is), let the interpreter answer, and retry only after invalidation (a new stamp, DropAll or a deploy). SQL fallback for every later read (as built) is a correct-answer but degraded baseline that violates ADR-0014's 'answers exactly as the interpreter'.


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

- Working assumption: Prefer the bound endpoints graph, with ambiguity refused; the actual default-write rule remains a behavior fact pending intent confirmation.


<a id="query.graph-scope.read"></a>
[I · query.graph-scope.read]

A Cypher read with no `USE GRAPH` keeps each match inside one graph, through every clause:

- The nodes and relationships of one `MATCH`, including comma-separated patterns, come from one graph.
- A node carried through `WITH` keeps its graph in later clauses.
- Variable-length and shortest-path reads walk each graph on its own.
- A procedure call answers the union of each graph's own answer, or refuses when it cannot answer per graph.

- Working assumption: Treat a mapping registration as namespace-wide (the as-built baseline). Under a named USE GRAPH scope, require either graph-aware mapping provenance or an explicitly documented exception. Model the current global visibility as a known deviation from the glossary's isolation rule. It is not a security breach, because the namespace is the boundary (USER_GUIDE:467-468).


<a id="query.graph-scope.row-graph"></a>
[D · query.graph-scope.row-graph]

A row of an all-graphs read does not say which graph it came from. To label rows by graph, run the query once per graph with `USE GRAPH`.


<a id="query.graph-scope.write"></a>
[I · query.graph-scope.write]

Every Cypher write clause with no `USE GRAPH` follows the [all-graphs write](../concepts/graph-scope.g5.md#graph.all_graphs_write) rule:

- `SET` of a value read from another variable, such as `SET n.p = m.x`, reads it from that row's own graph.
- A relationship `SET`, `DELETE` and `DETACH DELETE` change only the bound rows in their own graph.
- `MERGE` looks for its pattern in the default graph only, and its `ON MATCH` and `ON CREATE` actions change only the default graph's node.


<a id="query.graph-scope.names"></a>
[I · query.graph-scope.names]

`USE GRAPH` refuses a graph name the way every other IVG write does, as [graph names](../concepts/graph-scope.g5.md#graph.names) requires, before anything is read or written.

## Writes


<a id="query.writes"></a>
[I · query.writes]

Every Cypher write runs on the SQL path, and every statement of one write uses the rows its `MATCH` bound before anything was written.

- A later `SET` item, `REMOVE` or `DELETE` in the same query acts on the same matched rows, even when an earlier item changed what the `MATCH` tests.

- Working assumption: `DETACH DELETE` removes the node's labels, properties, default-route vector, incident edges and those edges' reifications, but not vectors in other routes or temporal entries. `DELETE r` removes only the relationship row and leaves its reification, the same open question as [edge delete reifications](../../Verus_verification/open_questions.md#structure.edge.delete.reifications).


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


## Entry points


<a id="query.read-only"></a>
[I · query.read-only]

`execute_cypher(read_only=True)` refuses any query that may write, before any part of it runs, by the same [parser-based rule](../concepts/access.g5.md#access.read_only.verdict) the servers' read-only mode uses.

- A write clause anywhere counts: a `UNION` branch, a `CALL { }` body, or any statement of a `;`-separated text.
- A text that does not parse is refused too.


<a id="query.browser-metadata"></a>
[I · query.browser-metadata]

IVG answers the fixed metadata queries Neo4j Browser sends without running them, and gives those fixed answers to no other query.

- Working assumption: Treat the accepted DDL as an acknowledged no-op that establishes no invariant (supported by f4a13d75 and pinned by tests). Model no uniqueness guarantee from it. As a proposed strengthening, not a decision: document it in USER_GUIDE beside the parse-error rule and add a metadata warning. Refusal (option c) would reverse a maintainer decision.


## System procedures


<a id="query.system-procedures"></a>
[D · query.system-procedures]

So that Neo4j tools work, IVG answers some Neo4j procedure calls itself, outside SQL.

- `db.*` and `dbms.*` metadata calls, such as `db.labels`, `db.relationshipTypes`, `db.propertyKeys` and `dbms.components`, and `apoc.meta.data` and `apoc.meta.schema`.
- `gds.pageRank.stream`, `gds.betweenness.stream` and `gds.shortestPath.dijkstra.stream`, with GDS's graph-name and configuration arguments; the graph name is not read.
- A `gds.*` call takes after its `YIELD` only a `WHERE` and a `RETURN` of yielded names.
- A `db.*`, `dbms.*` or `apoc.*` call takes after its `YIELD` only a `WHERE`, one `WITH` of yielded names, a `RETURN` of yielded names, `ORDER BY`, `SKIP` and `LIMIT`; any other clause is refused, naming it.
- Another `gds.*` call is refused, naming IVG's own procedure to call instead; `gds.nodeSimilarity.stream` is the exception, passed to IVG's vector search with its arguments as given.

- Working assumption: Prefer declared YIELD aliases at the public reader, while documenting current handled-call names until the owner decides.
- Working assumption: Prefer validating a requested WHERE independent of row count; current empty-provider acceptance does not settle intent.
- Working assumption: Prefer a clear unknown-procedure refusal; preserve present empty results as observed compatibility until the owner decides.


<a id="query.system-procedures.results"></a>
[D · query.system-procedures.results]

Handled metadata rows apply the following result rules.

- A `YIELD` alias names the value read by `WHERE` and `RETURN`; only a true condition keeps a row, so a comparison with null does not. Filtering precedes `SKIP` and `LIMIT`.
- As built, bare `db.labels() YIELD label AS l` keeps result column `label`, while `RETURN l` projects column `l`. `ORDER BY` reads a returned column and refuses another name even on empty data, so bare `ORDER BY l` refuses while `RETURN l ORDER BY l` succeeds.
- A RETURN list already equal to the physical result columns bypasses source-name validation: `YIELD absent AS label RETURN label` keeps actual label values, while alias `l` refuses on nonempty rows.
- Unsupported WHERE expressions and missing parameters are evaluated only when producer rows exist; an empty producer can return no rows without that error. Unsupported structural clauses such as `MATCH` refuse independently of whether rows exist.


## Aggregate results


<a id="query.aggregation"></a>
[I · query.aggregation]

An aggregate uses the rows reaching its query stage, and grouping chooses which rows contribute to each result. The result keeps the types required by the aggregate and its typed inputs.

- `COUNT(*)` counts rows, while `COUNT(value)` leaves out null or missing values. `DISTINCT` removes repeated equal values before aggregation.
- Empty input without grouping yields one aggregate row: count 0, sum 0, average null and an empty collection. Empty grouped input yields no group.
- SUM leaves out null and returns 0 if no value contributes. With typed numeric inputs, it stays an integer when every contributor is an integer and a float when one is a float, even for a whole total; `WITH` preserves that type.
- A collection leaves out null and preserves its elements' types; a nested list or map is different from text spelling it.
- Aggregation precedes final ordering, skipping and limiting. An empty result still has its declared return columns.

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

- Working assumption: Prefer a consistent structured path value; driver/path-dependent text is current behavior requiring a compatibility decision.


## Values in results


<a id="query.values"></a>
[D · query.values]

A node property read preserves its stored numeric type: a D-marked IRIS double becomes a Python float, and an N-marked integer becomes an int (a fractional or exponent N spelling becomes a float). Unmarked numeric-looking node text stays text; a string beginning with the mark is escaped with S and unwrapped once, so its contents are not decoded again.

- Since 4.6.4 the Python node writers bind signed 64-bit integers and finite floats as numbers; booleans become `true`/`false` text, lists and maps JSON text, and larger integers and nonfinite floats text. Earlier Python numeric text stays text after setup. The engine's node read API decodes stored booleans and valid JSON lists/maps; a string spelling a list/map also reads as one.
- `CY_TYPED` decides the tag from the stored IRIS value, rather than the driver's column type. SQL result decoding and the node read API consume that tag. The [batched node reader](graph-structure.g5.md#structure.node.read) also protects its structural keys.
- Relationship properties are stored in qualifier text and follow their separately owned decoder; preserving a node's stored type does not establish that relationship values preserve their original type.


<a id="query.values.equality"></a>
[I · query.values.equality]

A `WHERE` equality between a stored property and a boolean or integer literal follows how each kind of property is stored, not the value `RETURN` shows.
- A boolean literal matches the stored text `true`, `1` or `True` (for `false`: `false`, `0`, `False`) on nodes and relationships. A node's stored integer 1 or 0 matches too, so `n.p = true` keeps a node whose `p` reads back as the integer 1 or the string "1".
- An integer literal on a node matches only a stored number of that value: the string "1" and a node boolean do not equal 1.
- An integer literal on a relationship matches the qualifier text that spells the integer or its float twin (`1`, `1.0`), so a JSON boolean (read as 1 or 0), the string "1" and the string "1.0" all equal 1.
- A whole JSON float on a relationship keeps its spelling (`1.0`), so it equals 1 but not `true`; the same value stored as a node double equals both.
- The boolean legacy match is a documented known issue that typed storage is planned to remove in 4.8.0; openCypher equality matches only values of the same type.


<a id="query.values.ordering"></a>
[I · query.values.ordering]

A `WHERE` ordering comparison (`<`, `>`, `<=`, `>=`) between a stored property and a number literal treats node and relationship properties differently.
- A node property orders only when it holds a stored number; a string or boolean is null against a number, so the row is dropped, as openCypher requires.
- A relationship property is cast from its qualifier text to a number: numeric text orders by its value, a JSON boolean orders as 1 or 0, text with a leading number orders by that number (`"12abc"` as 12), and any other text, including the empty string, orders as 0.
- So `r.p < 2` keeps a relationship whose `p` is `"x"`, while `RETURN r.p` reads `"x"`; the same node property is dropped.
- Comparisons between two stored properties, and against a boolean, already use Cypher orderability on both kinds.


<a id="query.values.sorting"></a>
[I · query.values.sorting]

`ORDER BY` sorts property values by a key whose first part is the value's kind: strings, then booleans, then numbers, then NaN, then null last (first with `DESC`).
- A node property that is a string spelling a number (`"9"`) sorts among the numbers, although `RETURN` reads it as a string and a `WHERE` ordering drops it. This is the documented known issue that a property cannot tell a number from a string that spells it. Relationship text that spells a number reads back as a number, so its sort agrees with `RETURN`.
- On the SQL path an empty-string property sorts first, as a string. On the native executor it sorts with the nulls, so the two paths order the same rows differently.


<a id="query.values.nulls"></a>
[I · query.values.nulls]

A missing property, and on a relationship an absent qualifier object, an empty one or an explicit JSON `null`, all read as null in `WHERE`: `=`, `<>`, `IN` and their negations with `NOT` drop the row, and `IS NULL` keeps it, on nodes and relationships alike.


<a id="query.values.string_predicates"></a>
[I · query.values.string_predicates]

`STARTS WITH`, `ENDS WITH` and `CONTAINS` test the stored text of a property, whatever its type.
- A node property stored as a number is tested through its canonical text: the number 12 starts with `'1'`, and the number 0.95 is tested as `.95`, while `RETURN` reads both as numbers. openCypher makes a string predicate on a number null.
- A relationship property is tested through its `JSON_VALUE` text, so a JSON number behaves the same way.


<a id="query.values.in_lists"></a>
[I · query.values.in_lists]

`x.p IN [list]` compares the property's stored text with each list value's text, not by the rules of `=`.
- A node string that spells an integer exactly (`"1"`) is `IN [1]`, although `x.p = 1` is false for it; a node number 1 is `IN ['1']`. Near spellings (`"01"`, `"1.0"`) match neither.
- A relationship number written as a whole float (`1.0`) is not `IN [1]`, although `x.p = 1` is true for it.
- A boolean in the list matches the legacy spellings, as `=` does.


<a id="query.values.relationship_text"></a>
[I · query.values.relationship_text]

A relationship property read in a Cypher result is decoded from its stored text. `true` and `false` become booleans, canonical integer text becomes an integer, canonical decimal text becomes a float, list or map text becomes a list or map, and any other text stays the string it is.
- Canonical integer text is an optional minus sign, then `0` or a digit 1 to 9 followed by more digits. Canonical decimal text adds a point and at least one digit.
- So `01`, `+1`, `1.`, `.5`, `1e5` and text with spaces stay text. `True`, `1` and `0` are not booleans here; `1` and `0` become integers.
- Only the columns the translator marks as relationship property reads are decoded, and only when the row has as many values as the result has columns.
- Today a text with one trailing line break, or with non-ASCII digits after its first digit, is also read as a number: `"12\n"` and `"1٢"` both read back as 12.
- A result column that is not itself a relationship property read is not decoded: `coalesce(r.p, 'z')` returns the stored text (`'7'` for the number 7, `'1'` for the boolean `true`), while `RETURN r.p` returns 7 and `true`.
- In arithmetic a relationship boolean reads as 1 (`r.p + 1` is 2), while a node boolean is the text `true` and concatenates (`n.p + 1` is `'true1'`), the documented string-arithmetic behavior.

## Metadata

### query.paths
- agent
- architecture-decision, user-facing-behavior

Sources: [CONTEXT.md, Query execution](../../../CONTEXT.md#L224-L232), [spec 253, decisions of 2026-10-20 and FR-001](../../../specs/253-native-cypher-executor/spec.md#L14-L18), [USER_GUIDE, Where a query runs](../../../docs/USER_GUIDE.md#L350-L368), [`_execute_parsed`](../../../iris_vector_graph/_engine/query.py#L2032-L2082). Note: USER_GUIDE says "the one known difference between the paths is listed in Known issues", and no such entry is named there.

Provenance: spec 253 is still "Draft" and its "Decided 2026-10-20" lines name no decider, so under the uplift's authority rule ([sources](../../uplift/ivg-verus-initial/sources.md)) the block is `agent` (review round 3 R3-reader M16).

### query.paths.varlength
- Sources: [4.7.0 changelog: CY_VLP_ENDS reads ^KG](../../../CHANGELOG.md#L3057-L3060), [`Graph.KG.VarLength`](../../../iris_src/src/Graph/KG/VarLength.cls)
- Evidence: [predictions and native observations on both engines](../../uplift/consolidated/iteration-21/varlength-PAIRS.md)
- Expands: [Two query paths](#query.paths)
- agent
- user-facing-behavior

As-built agreement with openCypher, observed natively; no formal contract.

### query.aql

- design-verified

- Sources: [numeric lexer](../../../iris_vector_graph/cypher/aql/lexer.py#L164-L174), [depth parser](../../../iris_vector_graph/cypher/aql/parser.py#L89-L105), [null translator](../../../iris_vector_graph/cypher/aql/translator.py#L97-L110), [hop writer](../../../iris_vector_graph/cypher/aql/translator.py#L159-L180), [execute_aql](../../../iris_vector_graph/_engine/query.py#L1730-L1745)
- Verus: [aql_frontend](../../Verus_verification/models/aql_frontend/NOTES.md), as-built `lex`, `depth`, `hops`, `resolve`; raw suffix/typed token/AST/predicate projection. Actual output text and public adapter observed with a recorded Cypher consumer; query execution remains unproved.
- Expands: [query paths](#query.paths)
- agent
- user-facing-behavior

Audit reproduction: [F-0824](../../Verus_verification/bugs_issues.md#F-0824) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [Two slashes inside an AQL string start a comment](../../Verus_verification/bugs_issues.md#F-0824).

State machines: [aql frontend](../../Verus_verification/models/aql_frontend/manifest.json)

### query.native

- uncertain
- agent
- architecture-decision, operations
- Children: [gates](#query.native.gates), [privileges](#query.native.privileges), [Should a bulk load by another process close the native query path while indexes lag the rows?](../../Verus_verification/open_questions.md#q-cyp-003), [reads only](#query.native.reads-only), [equal answers](#query.native.equal-answers), [SQL first](#query.native.sql-first), [fallback](#query.native.fallback), [route](#query.native.route).

Sources: [spec 253 decisions and FR-005, FR-010](../../../specs/253-native-cypher-executor/spec.md#L14-L18), [engine options](../../../iris_vector_graph/engine.py#L290-L317). The default was to flip only after a shadow run matched the SQL path on the full TCK and the 40 SNB queries; [TCK.md](../../../docs/dev/TCK.md#L215-L232) records the shadow run.

Provenance: spec 253 is still "Draft" and its "Decided 2026-10-20" lines name no decider, so under the uplift's authority rule ([sources](../../uplift/ivg-verus-initial/sources.md)) the block is `agent` (review round 3 R3-reader M16).

Open questions: [Should a bulk load by another process close the native query path while indexes lag the rows?](../../Verus_verification/open_questions.md#q-cyp-003)

### query.native.gates
- agent
- operations, data-integrity
- test-coverage
- Expands: [Native executor](#query.native).

Sources: [spec 253 FR-003, FR-005, FR-011, FR-014](../../../specs/253-native-cypher-executor/spec.md#L98-L140), [`native_gate`](../../../iris_vector_graph/cypher/native_plan.py#L524-L536), [plan version check](../../../iris_src/src/Graph/KG/Cypher/Exec.cls#L13-L41), [mapped labels decline](../../../iris_vector_graph/_engine/query.py#L2162-L2184). Live: [`test_253_executor_version_e2e.py`](../../../tests/e2e/test_253_executor_version_e2e.py); the other gates are covered by mocked unit tests ([`test_253_native_gates.py`](../../../tests/unit/test_253_native_gates.py)). The engine caches the index, privilege and version answers until setup runs again.

### query.native.privileges

- uncertain
- agent
- security
- Expands: [Native executor](#query.native).

Sources: [spec 253 FR-011, decided 2026-10-20](../../../specs/253-native-cypher-executor/spec.md#L124-L127), [`_native_privileges`](../../../iris_vector_graph/engine.py#L559-L586). The check is a SELECT probe per engine rather than the per-process `CheckPrivilege` the FR names.

Provenance: spec 253 is still "Draft" and its "Decided 2026-10-20" lines name no decider, so under the uplift's authority rule ([sources](../../uplift/ivg-verus-initial/sources.md)) the block is `agent` (review round 3 R3-reader M16).

Open questions: [Should a running engine notice a revoked table right or a dropped adjacency index?](../../Verus_verification/open_questions.md#HD-0901)

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

Sources: [spec 253 FR-002, FR-012 (equality decided 2026-10-20), FR-013](../../../specs/253-native-cypher-executor/spec.md#L100-L137), [`native_shadow.compare`](../../../iris_vector_graph/cypher/native_shadow.py#L29-L69). Live: the family A and B end-to-end tests run in shadow mode ([`test_253_family_b_e2e.py`](../../../tests/e2e/test_253_family_b_e2e.py)). Model note: equality assumes the indexes are current ([Should a bulk load by another process close the native query path while indexes lag the rows?](../../Verus_verification/open_questions.md#q-cyp-003)).

Findings: [The native interpreter tells used relationships apart by CRC-32, so a hash collision drops a legitimate match](../../Verus_verification/bugs_issues.md#bug-cyp-002); [ORDER BY sorts an empty-string property with the nulls on the native executor and first on the SQL path](../../Verus_verification/bugs_issues.md#bug-cyp-104)

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

- design-verified

- uncertain
- Playbook: [NAT-T7](../../../experiment/playbook-completion/ontology/09-native-executor.md)
- Verus: [route_recheck](../../Verus_verification/models/route_recheck/NOTES.md), as-built held-call recheck/reset and permanent SQL-failure rules; trial medians, drift selection and SQL/native answer equality remain unmodeled.
- agent
- architecture-decision
- Expands: [Native executor](#query.native).

Sources: [`native_route.py`](../../../iris_vector_graph/cypher/native_route.py#L1-L16), [`_execute_parsed`](../../../iris_vector_graph/_engine/query.py#L2063-L2104). Shadow mode skips the route.

Open questions: [Should the second HTTP app's Cypher endpoints (`/api/cypher` and GraphQL `executeCypher`) answer through the engine, as the documented server and the Bolt listener do?](../../Verus_verification/open_questions.md#query.routes)

State machines: [route recheck](../../Verus_verification/models/route_recheck/manifest.json)

### query.shadow

- uncertain
- agent
- data-integrity, operations
- test-coverage
- Children: [In shadow mode, should a native failure be raised instead of answered by SQL?](../../Verus_verification/open_questions.md#q-cyp-002).

Sources: [CONTEXT.md, Shadow mode](../../../CONTEXT.md#L234-L236), [spec 253 FR-006](../../../specs/253-native-cypher-executor/spec.md#L107-L108), [`_shadow_compare`](../../../iris_vector_graph/_engine/query.py#L2226-L2249), [TCK.md, how the native path is held to the SQL path](../../../docs/dev/TCK.md#L258-L271). Shadow mode compares native with SQL only; compiled against interpreted is checked by the compiled-plan tests.

Open questions: [Should shadow mode fail when the native path raises an error?](../../Verus_verification/open_questions.md#HD-0902), [In shadow mode, should a native failure be raised instead of answered by SQL?](../../Verus_verification/open_questions.md#q-cyp-002)

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

- design-verified
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

### query.compiled.fallback

- design-verified

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

### query.graph-scope

- uncertain
- human-verified
- user-facing-behavior, data-integrity
- Children: [reads](#query.graph-scope.read), [row graph](#query.graph-scope.row-graph), [writes](#query.graph-scope.write), [When a write without USE GRAPH creates a relationship between nodes its MATCH bound in a named graph, which graph gets it?](../../Verus_verification/open_questions.md#q-cyp-001), [names](#query.graph-scope.names).

Sources: [CONTEXT.md, All-graphs read and write](../../../CONTEXT.md#L38-L48), [USER_GUIDE section 4](../../../docs/USER_GUIDE.md#L321-L330), [`USE GRAPH ''` scopes the default graph](../../../iris_vector_graph/cypher/translator.py#L5647-L5666). The rules themselves are owned by the graph scope page; this block states only that Cypher applies them.

Open questions: [When a write without USE GRAPH creates a relationship between nodes its MATCH bound in a named graph, which graph gets it?](../../Verus_verification/open_questions.md#q-cyp-001)

### query.graph-scope.read

- uncertain
- human-verified
- user-facing-behavior, data-integrity
- test-coverage
- Expands: [Graph scope](#query.graph-scope).

Sources: [CONTEXT.md, All-graphs read, decided 2026-10-20](../../../CONTEXT.md#L38-L42), [spec 253 FR-009](../../../specs/253-native-cypher-executor/spec.md#L116-L120), [SQL path correlation](../../../iris_vector_graph/cypher/translator.py#L898-L1035), [native per-graph walk](../../../iris_src/src/Graph/KG/Cypher/Exec.cls#L832-L904). Live: [`test_253_all_graphs_read_e2e.py`](../../../tests/e2e/test_253_all_graphs_read_e2e.py), [`test_460_r192_all_graphs_procedures_e2e.py`](../../../tests/e2e/test_460_r192_all_graphs_procedures_e2e.py), [`test_461_shortest_path_all_graphs_e2e.py`](../../../tests/e2e/test_461_shortest_path_all_graphs_e2e.py). The TCK runs in one graph and does not exercise this rule. Observed divergence: the SQL path skips the per-graph joins when the node table holds one graph, though property rows of another graph can remain without a node row ([A-cypher notes, F6](../../uplift/ivg-verus-initial/intent/cypher.md#candidate-findings)).

Findings: [An all-graphs read skips graph correlation when only the nodes table looks single-graph](../../Verus_verification/bugs_issues.md#bug-cyp-005); [Carry each node binding's graph through Cypher translation instead of correlating graphs by regex afterwards](../../Verus_verification/design_simplification.md#simp-cyp-002)

Open questions: [Does a mapped label belong to every graph?](../../Verus_verification/open_questions.md#HD-0802)

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

### query.graph-scope.names
- agent
- data-integrity
- Expands: [Graph scope](#query.graph-scope).

Sources: [`GraphKey.Validate`](../../../iris_src/src/Graph/KG/GraphKey.cls#L23-L48), [`validate_graph_name`](../../../iris_vector_graph/_validate.py#L19-L45), [`USE GRAPH` parsing](../../../iris_vector_graph/cypher/parser.py#L174-L192). Observed divergence: the Cypher path does not validate the name, so a label-free node can be written under graph `"0"` while label and edge writes there fail in the index ([A-cypher notes, F8](../../uplift/ivg-verus-initial/intent/cypher.md#candidate-findings)).

Findings: [USE GRAPH accepts graph names the graph keys refuse](../../Verus_verification/bugs_issues.md#bug-cyp-006)

### query.writes

- uncertain
- agent
- user-facing-behavior, data-integrity
- test-coverage
- Children: [atomic](#query.writes.atomic), [adjacency](#query.writes.adjacency), [ledger](#query.writes.ledger), [subquery](#query.writes.subquery), [create existing](#query.writes.create-existing), [Should a Cypher `DELETE` clean up everything the engine's own [node delete](graph-structure.g5.md#structure.node.delete) and edge delete clean up?](../../Verus_verification/open_questions.md#query.writes.delete-scope).

Sources: [CHANGELOG 4.6.0, every statement uses the rows its MATCH bound](../../../CHANGELOG.md#L1742-L1744), [spec 229](../../../specs/229-tck-write-verification/spec.md), [`_write_ids`, `_capture_key`](../../../iris_vector_graph/cypher/translator.py#L13093-L13164), [`execute_transaction`](../../../iris_vector_graph/stores/iris_sql_store.py#L1580-L1818). Live: the TCK's write scenarios with side-effect counting, and `test_460_all_graphs_writes_e2e.py`.

Audit reproduction: [F-C0848](../../Verus_verification/bugs_issues.md#F-C0848) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [A Cypher CREATE or MERGE with literal or parameter endpoint ids drops a parameter-bound relationship property without an error](../../Verus_verification/bugs_issues.md#F-C0848).

Audit reproduction: [F-0822](../../Verus_verification/bugs_issues.md#F-0822) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [CREATE or MERGE after UNWIND $p AS e WITH e fails](../../Verus_verification/bugs_issues.md#F-0822).

Audit reproduction: [F-C0849](../../Verus_verification/bugs_issues.md#F-C0849) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [A relationship property bound by a WITH before a literal-endpoint CREATE is stored as text that is not JSON](../../Verus_verification/bugs_issues.md#F-C0849).

Open questions: [Should a Cypher `DELETE` clean up everything the engine's own [node delete](graph-structure.g5.md#structure.node.delete) and edge delete clean up?](../../Verus_verification/open_questions.md#query.writes.delete-scope)

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

Findings: [The glossary says structural edges are subject to the ledger, but Cypher writes are never recorded](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-doc-012)

### query.writes.subquery
- agent
- data-integrity, user-facing-behavior
- Expands: [Writes](#query.writes).

Sources: [read-only rule counts a `CALL { }` body's write](../../../iris_vector_graph/cypher/ast.py#L535-L550), [subquery translation](../../../iris_vector_graph/cypher/translator.py#L14561-L14703), [clause dispatch](../../../iris_vector_graph/cypher/translator.py#L5134-L5136), [reconstruction check 2(a)15 and correction 22](../../uplift/ivg-verus-initial/reconstruction-check.md). Native probe ([receipt](../../Verus_verification/receipts/native/cypher_subquery_write.json), current probe re-run): `CALL { CREATE ... } RETURN 1` writes nothing and returns IRIS's raw SQL syntax error (SQLCODE -12) in the result's error field, while a plain `CREATE` control writes its node. That meets this block, but the refusal is returned rather than raised as the `GraphWriteError` of [atomic writes](#query.writes.atomic), and the strict-mode check is never reached. The subquery translation reads only the body's `MATCH`, `WHERE` and `UNWIND` clauses, so a silent drop when the body's `RETURN` reads only matched variables is still suspected from source reading and not observed ([review round 1, R1-10](../../uplift/ivg-verus-initial/review/round1-platform.md)); KNOWN_ISSUES does not list either case.

Findings: [A write inside CALL { } is refused with a raw SQL syntax error instead of a clear refusal](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-cyp-004)

### query.writes.create-existing
- agent
- user-facing-behavior, data-integrity
- Expands: [Writes](#query.writes).

Sources: [USER_GUIDE, a node's ID is its identity](../../../docs/USER_GUIDE.md#L142-L147), [CHANGELOG 4.6.5](../../../CHANGELOG.md#L359-L362), [reconstruction check 2(a)15](../../uplift/ivg-verus-initial/reconstruction-check.md). `create_node` returns False and adds nothing for an existing ID, and `store_node` replaces properties; the structure page owns those.

### query.read-only
- agent
- security, user-facing-behavior
- test-coverage

Sources: [`writes_cypher`](../../../iris_vector_graph/cypher/read_only.py#L92-L104), [`execute_cypher`](../../../iris_vector_graph/_engine/query.py#L1746-L1791). Live: [`test_read_only_bypass_e2e.py`](../../../tests/e2e/test_read_only_bypass_e2e.py). Before 4.6.0 the servers matched keywords in the raw text. The rule and its server routes are owned by [access.read_only](../concepts/access.g5.md#access.read_only) and [its verdict](../concepts/access.g5.md#access.read_only.verdict).

### query.browser-metadata

- uncertain
- agent
- user-facing-behavior

Sources: [`execute_cypher` shortcuts](../../../iris_vector_graph/_engine/query.py#L1807-L1856), [`answered_without_parsing`](../../../iris_vector_graph/cypher/read_only.py#L53-L58). Observed divergence: two shortcuts match on words anywhere in the text (for example `RETURN DISTINCT`, `UNION ALL` and `ENTITY`), so other reads get the fixed answers, ignoring `USE GRAPH` ([A-cypher notes, F4](../../uplift/ivg-verus-initial/intent/cypher.md#candidate-findings)).

Findings: [Text shortcuts meant for Neo4j Browser answer unrelated queries with canned rows](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-cyp-003)

Open questions: [Should `CREATE CONSTRAINT` / `CREATE INDEX` be refused rather than accepted as a no-op?](../../Verus_verification/open_questions.md#HD-0804)

### query.system-procedures

- design-verified

- uncertain
- agent
- user-facing-behavior
- Formal: [procedure results and qualified source roles](../../Verus_verification/models/procedure_results/NOTES.md).
- Children: [result rules](#query.system-procedures.results), [Should a call to an unknown apoc, db or dbms procedure be refused?](../../Verus_verification/open_questions.md#q-cyp-005), [Should standalone handled metadata calls expose YIELD aliases as result columns?](../../Verus_verification/open_questions.md#q-iter-004), [Should handled WHERE validation happen when no rows exist?](../../Verus_verification/open_questions.md#q-iter-005).

Sources: [USER_GUIDE, procedures](../../../docs/USER_GUIDE.md#L803-L821), [handler table](../../../iris_vector_graph/engine.py#L944-L966), [`_try_system_procedure`](../../../iris_vector_graph/engine.py#L1676-L1722), [GDS answers and shims](../../../iris_vector_graph/_engine/query.py#L650-L705), [reconstruction check G25 and correction 21](../../uplift/ivg-verus-initial/reconstruction-check.md). Live: [`test_460_r314_call_yield_values_e2e.py`](../../../tests/e2e/test_460_r314_call_yield_values_e2e.py). The `ivg.*` procedures are IVG's own and are not covered here; `gds.louvain.stream` maps to `ivg.leiden`, which no handler answers, so it is refused too.

Open questions: [Should a call to an unknown apoc, db or dbms procedure be refused?](../../Verus_verification/open_questions.md#q-cyp-005), [Should standalone handled metadata calls expose YIELD aliases as result columns?](../../Verus_verification/open_questions.md#q-iter-004), [Should handled WHERE validation happen when no rows exist?](../../Verus_verification/open_questions.md#q-iter-005)

State machines: [procedure results](../../Verus_verification/models/procedure_results/manifest.json)

### query.system-procedures.results

- design-verified
- agent
- user-facing-behavior
- Expands: [System procedures](#query.system-procedures).
- Formal: [procedure result model and exact source roles](../../Verus_verification/models/procedure_results/NOTES.md).

Evidence: [actual SQLite and native scope](../../Verus_verification/models/procedure_results/NOTES.md), [native empty/nonempty neighbors](../../uplift/consolidated/iteration-7/procedure-native.json). Full grammar, general expressions, multi-column providers and arbitrary collation remain outside the new proof.

State machines: [procedure results](../../Verus_verification/models/procedure_results/manifest.json)

### query.aggregation

- design-verified
- Sources: [USER_GUIDE, grouped reporting](../../../docs/USER_GUIDE.md#L165); [typed property sums and WITH](../../../tests/unit/test_sum_column_typing.py); [known-list typed collection](../../../tests/unit/test_460_r308_collect_typed.py); [empty result columns](../../../tests/unit/test_empty_result_columns.py); [aggregate order and page scope](../../../tests/unit/test_order_limit_aggregate_scope.py); [count DISTINCT with LIMIT](../../../tests/e2e/test_470_issue13_count_distinct_limit_e2e.py)
- Verus: [aggregate_results.rs](../../Verus_verification/models/aggregate_results/aggregate_results.rs) `theorem_raw_group_SUM_reaches_typed_scalar_reader`, `theorem_key_enumeration_complete_unique`, `theorem_full_output_before_page` and `theorem_reader_projection_keeps_exact_public_cells`; [scope](../../Verus_verification/models/aggregate_results/NOTES.md). Raw rows and a RETURN AST fragment derive groups, folds, result kind and full output before paging; exact integer/half-unit arithmetic, SQL equality/aggregate operations, JSON spelling/parsing, raw-name generation and collation remain stated provider frames. Native Group/GroupOf/EmitGroups have inspected typed count transcriptions only, under their nonnull/pW1/equality/order premises; the SQL native panels do not execute those bodies. OPTIONAL synthetic fallback remains observed and partial under bug-agg-001.
- agent
- user-facing-behavior, data-integrity

This owner makes the ordinary aggregate reporting contract explicit before the new formal model. Exact numeric equality, SQL/JSON carriers, unsupported expressions, runtime list ambiguity, numeric overflow, collation and ordering without a total sort key remain source conditions to state in the model and binding, not supplied aggregate answers. Scalar typed-reader proofs and a native planner accepting COUNT do not establish the aggregate producer.

Finite correspondence: [eight ordinary native cases](../../uplift/consolidated/iteration-13/root-aggregate-native.json), with [predictions frozen before execution](../../uplift/consolidated/iteration-13/root-aggregate-native-PAIRS.md), derive bag/null/distinct counts, global versus grouped empty input, post-aggregate pagination and fresh graph isolation. The [independent35-check audit](../../uplift/consolidated/iteration-13/review-aggregate-native-audit.json) derives expectations from the raw fixture. These sampled counts do not certify SUM, AVG, collection, arbitrary numeric/JSON providers or native executable bodies; the selected ordinary fragment has been independently replayed within its stated domain. Existing [typed values](#query.values) and [conformance limits](#query.conformance) retain their own scope.

[Four further native neighbors](../../uplift/consolidated/iteration-13/root-aggregate-types-native.json) check integer SUM, a whole-valued float SUM, its type through WITH, and float AVG over newly created exact half-unit values. The [independent27-check audit](../../uplift/consolidated/iteration-13/review-aggregate-types-audit.json) derives sums and mean from the raw values and checks the returned Python types. These finite cases keep the general numeric, storage, driver and JSON provider limits open.

The [newer all-null SUM regression](../../../tests/unit/test_460_r308_guards.py#L53) explicitly requires zero when no value contributes. [Four fresh native empty/optional contrasts](../../uplift/consolidated/iteration-13/root-optional-aggregate-native.json), with [independent29-check audit and authority triage](../../uplift/consolidated/iteration-13/review-optional-aggregate-audit.json), confirm that a leading grouped OPTIONAL instead emits NULL from its synthetic fallback. The older [R298 helper test](../../../tests/unit/test_460_r298_fixes46_leftovers.py#L28) preserves that as-built NULL. This exception stays an observed partial caller boundary in Verus; it does not weaken the intended SUM identity or turn an ordinary legal query into a refusal.

Findings: [A grouped empty OPTIONAL returns NULL instead of a zero sum](../../Verus_verification/bugs_issues.md#bug-agg-001).

Audit reproduction: [F-0823](../../Verus_verification/bugs_issues.md#F-0823) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [An aggregate in a CALL subquery that matches nothing answers 0](../../Verus_verification/bugs_issues.md#F-0823).

Audit reproduction: [bug-agg-001](../../Verus_verification/bugs_issues.md#bug-agg-001) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

State machines: [aggregate results](../../Verus_verification/models/aggregate_results/manifest.json)

### query.conformance

- uncertain
- agent
- user-facing-behavior
- test-coverage

Sources: [TCK.md](../../../docs/dev/TCK.md#L157-L256), [KNOWN_ISSUES, application developers](../../../docs/KNOWN_ISSUES.md#L23-L117), [KNOWN_ISSUES, untyped values](../../../docs/KNOWN_ISSUES.md#L183-L190), [KNOWN_ISSUES, variable-length limits](../../../docs/KNOWN_ISSUES.md#L452-L481), [KNOWN_ISSUES, UNWIND then CREATE](../../../docs/KNOWN_ISSUES.md#L585-L596), [spec 229](../../../specs/229-tck-write-verification/spec.md). Recorded runs: 3896 of 3896 eligible scenarios at 4.6.0 with multigraph on and the native executor on; seven fail with multigraph off. The TCK at the pinned revision has no `CALL { }` write scenarios, and a dropped `CALL { }` write is not a listed deviation: it is held to [query.writes.subquery](#query.writes.subquery) instead.

Findings: [A write inside CALL { } is refused with a raw SQL syntax error instead of a clear refusal](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-cyp-004); [Does a Cypher path value come back as JSON text or as a map, and may that depend on the driver or execution path?](../../Verus_verification/open_questions.md#q-cyp-004)

Audit (q-cyp-004): Open owner decision. Working assumption (agent, unratified): Prefer a consistent structured path value; driver/path-dependent text is current behavior requiring a compatibility decision. See [current behavior, alternatives and settling sources](../../Verus_verification/audits/register-20261115/question-review.md#q-cyp-004).

Audit reproduction: [F-0803](../../Verus_verification/bugs_issues.md#F-0803) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [A WHERE after RETURN is parsed and dropped](../../Verus_verification/bugs_issues.md#F-0803).

Audit reproduction: [F-C0101](../../Verus_verification/bugs_issues.md#F-C0101) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [An inline relationship property in a Cypher pattern fails on an edge with no properties](../../Verus_verification/bugs_issues.md#F-C0101).

Audit reproduction: [F-0808](../../Verus_verification/bugs_issues.md#F-0808) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [FOREACH over a parameter list does not run per item](../../Verus_verification/bugs_issues.md#F-0808).

Audit reproduction: [F-C0841](../../Verus_verification/bugs_issues.md#F-C0841) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [Cypher range() with a step of 0 known only at run time answers [] instead of raising NumberOutOfRange](../../Verus_verification/bugs_issues.md#F-C0841).

Open questions: [Does a Cypher path value come back as JSON text or as a map, and may that depend on the driver or execution path?](../../Verus_verification/open_questions.md#q-cyp-004)

### query.values

- design-verified
- Sources: [`iris_vector_graph/prop_values.py`](../../../iris_vector_graph/prop_values.py#L1-L77) (the typed-values contract, 4.6.0 R308 and R310)
- Children: [relationship property text](#query.values.relationship_text), [equality in WHERE](#query.values.equality), [ordering in WHERE](#query.values.ordering), [sorting](#query.values.sorting), [nulls](#query.values.nulls), [string predicates](#query.values.string_predicates), [IN lists](#query.values.in_lists)
- Verus: [node_read](../../Verus_verification/models/node_read/NOTES.md), as-built numeric writer, D/N tag selection, S escape and numeric/text read distinctions. The scalar node-property projection reaches the final result in `theorem_sql_scalar_read_reaches_result`; JSON/J tags, N fractional/exponent parsing, nonfinite values, mixed expressions and the remaining SQL finishing pipeline are open modeling gaps. Numeric spelling/parse identity in `CY_TYPED` is an inspected provider premise, not a proved IRIS function.
- agent
- user-facing-behavior

New owner in the consolidated uplift. Node values and the typed-value marks are the playbook's `CYP-B17` family.

Audit reproduction: [F-0810](../../Verus_verification/bugs_issues.md#F-0810) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [SET n.p = null keeps the key](../../Verus_verification/bugs_issues.md#F-0810); [A boolean equality also matches stored integers 1 and 0, beyond the legacy strings the known issue names](../../Verus_verification/bugs_issues.md#bug-cyp-102); [A relationship property that is not a number orders as one against a number literal](../../Verus_verification/bugs_issues.md#bug-cyp-103); [A string predicate matches a node property stored as a number by its digits](../../Verus_verification/bugs_issues.md#bug-cyp-105).; [import_rdf drops a literal's datatype](../../Verus_verification/bugs_issues.md#bug-str-109)

State machines: [node read](../../Verus_verification/models/node_read/manifest.json)

### query.values.equality

- design-verified
- Sources: [boolean spellings](../../../iris_vector_graph/prop_values.py#L87-L88), [`_stored_bool_in`, `_stored_bool_comparison`](../../../iris_vector_graph/cypher/translator.py#L17851-L17870), [`_stored_number_test`, `_number_texts`, `_node_number_eq_sql`, `_number_eq_sql`](../../../iris_vector_graph/cypher/translator.py#L16231-L16310); [known issue: a boolean in an equality also matches a stored '1' or 'True'](../../../docs/KNOWN_ISSUES.md#L597-L612); [4.1.0 changelog: boolean equality still matches legacy rows](../../../CHANGELOG.md#L3862-L3865)
- Verus: [typed_equality.rs](../../Verus_verification/models/typed_equality/typed_equality.rs) `theorem_node_true_exact`, `theorem_node_where_return_disagree`, `theorem_node_bool_not_integer`, `theorem_node_integer_needs_stored_number`, `theorem_node_bool_agrees_outside_legacy`, `theorem_rel_bool_equals_integer`, `theorem_rel_integer_equals_true`, `theorem_rel_twin_spelling_equals_integer` and `theorem_string_integer_kind_asymmetry`; [scope](../../Verus_verification/models/typed_equality/NOTES.md)
- Evidence: [predictions and native observations](../../uplift/consolidated/iteration-16/typed-equality-PAIRS.md)
- Expands: [Values in results](#query.values)
- agent
- user-facing-behavior, data-integrity

As-built SQL-path behavior on IRIS 2026.1 for values written by `create_node` and `create_edge`. The native executor declines every non-string equality value ([`native_plan._value`](../../../iris_vector_graph/cypher/native_plan.py#L62-L74); [observation](../../uplift/consolidated/iteration-17/native-equality-PAIRS.md)), so these rules hold on both paths. Parameters, `IN` lists, `MERGE` patterns and Cypher-written values were not checked.

Findings: [A boolean equality also matches stored integers 1 and 0, beyond the legacy strings the known issue names](../../Verus_verification/bugs_issues.md#bug-cyp-102); [A string predicate matches a node property stored as a number by its digits](../../Verus_verification/bugs_issues.md#bug-cyp-105); [IN lists compare a property's text with each value's spelling, so they disagree with = on nodes and relationships](../../Verus_verification/bugs_issues.md#bug-cyp-106)

State machines: [typed equality](../../Verus_verification/models/typed_equality/manifest.json)

### query.values.ordering

- design-verified
- Sources: [`_translate_boolean_expression` ordering branch and `_as_number`](../../../iris_vector_graph/cypher/translator.py#L19003-L19040), [`_stored_number_value`](../../../iris_vector_graph/cypher/translator.py#L16244-L16249), [property-to-property orderability (R308)](../../../iris_vector_graph/cypher/translator.py#L18932-L18952), [boolean orderability (R307)](../../../iris_vector_graph/cypher/translator.py#L18973-L18980)
- Verus: [typed_equality.rs](../../Verus_verification/models/typed_equality/typed_equality.rs) `theorem_node_text_never_orders`, `theorem_node_integer_orders_by_value`, `theorem_rel_text_orders_as_cast` and `theorem_rel_bool_orders_as_number`; [scope](../../Verus_verification/models/typed_equality/NOTES.md)
- Evidence: [predictions and native observations](../../uplift/consolidated/iteration-17/ordering-PAIRS.md)
- Expands: [Values in results](#query.values)
- agent
- user-facing-behavior, data-integrity

As-built SQL-path behavior on IRIS 2026.1 with `create_node`/`create_edge` values and integer literals. The product's own fixes (R307, R308, 4.7.0 row 24) treat a string read as 0 as a defect on every other comparison path.

Findings: [A relationship property that is not a number orders as one against a number literal](../../Verus_verification/bugs_issues.md#bug-cyp-103); [A string predicate matches a node property stored as a number by its digits](../../Verus_verification/bugs_issues.md#bug-cyp-105)

State machines: [typed equality](../../Verus_verification/models/typed_equality/manifest.json)

### query.values.sorting

- design-verified
- Sources: [`Graph.KG.Cypher.SortKey.Key`](../../../iris_src/src/Graph/KG/Cypher/SortKey.cls#L8-L153), [native `Exec.SortKey`](../../../iris_src/src/Graph/KG/Cypher/Exec.cls#L967-L973), [translator `_sort_key`](../../../iris_vector_graph/cypher/translator.py#L7762-L7770); [known issue: a property cannot tell a number from a string that spells it](../../../docs/KNOWN_ISSUES.md#L183-L200)
- Verus: [sort_key.rs](../../Verus_verification/models/sort_key/sort_key.rs) `theorem_rank_order`, `theorem_untyped_numeric_text_sorts_as_number`, `theorem_word_sorts_as_string`, `theorem_empty_string_sorts_as_string`, `theorem_null_sorts_last`, `theorem_node_where_and_order_by_disagree` and `theorem_executors_disagree_on_empty_string`; [scope](../../Verus_verification/models/sort_key/NOTES.md)
- Evidence: [predictions and native observations](../../uplift/consolidated/iteration-18/order-by-PAIRS.md)
- Expands: [Values in results](#query.values)
- agent
- user-facing-behavior, data-integrity

As-built for ordinary scalar values on IRIS 2026.1; lists, maps, graph values, durations and temporal text follow further key branches not modeled here.

Findings: [ORDER BY sorts an empty-string property with the nulls on the native executor and first on the SQL path](../../Verus_verification/bugs_issues.md#bug-cyp-104)

State machines: [sort key](../../Verus_verification/models/sort_key/manifest.json)

### query.values.nulls
- Sources: openCypher null semantics; translator `_number_eq_sql` ("`negate` is `<>`: NOT IN, still null for a null property")
- Evidence: [predictions and native observations](../../uplift/consolidated/iteration-20/null-semantics-PAIRS.md)
- Expands: [Values in results](#query.values)
- agent
- user-facing-behavior

As-built agreement with openCypher, observed natively on the SQL path for literal comparisons; no formal contract.

### query.values.string_predicates

- design-verified
- Sources: [`_boolean_expr_comparison_ops`](../../../iris_vector_graph/cypher/translator.py#L17757-L17794)
- Verus: [typed_equality.rs](../../Verus_verification/models/typed_equality/typed_equality.rs) `theorem_node_number_matches_string_prefix`; [scope](../../Verus_verification/models/typed_equality/NOTES.md)
- Evidence: [predictions and native observations](../../uplift/consolidated/iteration-20/null-semantics-PAIRS.md)
- Expands: [Values in results](#query.values)
- agent
- user-facing-behavior, data-integrity

Findings: [A string predicate matches a node property stored as a number by its digits](../../Verus_verification/bugs_issues.md#bug-cyp-105)

State machines: [typed equality](../../Verus_verification/models/typed_equality/manifest.json)

### query.values.in_lists

- design-verified
- Sources: [`_boolean_expr_in`](../../../iris_vector_graph/cypher/translator.py#L18274-L18330); [known issue: a property cannot tell a number from a string that spells it](../../../docs/KNOWN_ISSUES.md#L183-L200) (names `=`, inline maps and `WITH` columns, not `IN`)
- Verus: [typed_equality.rs](../../Verus_verification/models/typed_equality/typed_equality.rs) `theorem_node_in_disagrees_with_equality`; [scope](../../Verus_verification/models/typed_equality/NOTES.md)
- Evidence: [predictions and native observations](../../uplift/consolidated/iteration-23/remaining-operators-PAIRS.md)
- Expands: [Values in results](#query.values)
- agent
- user-facing-behavior, data-integrity

Findings: [IN lists compare a property's text with each value's spelling, so they disagree with = on nodes and relationships](../../Verus_verification/bugs_issues.md#bug-cyp-106)

State machines: [typed equality](../../Verus_verification/models/typed_equality/manifest.json)

### query.values.relationship_text

- design-verified
- Sources: [`iris_vector_graph/prop_values.py::parse_rel_prop_text`](../../../iris_vector_graph/prop_values.py#L141-L168), [`::parse_prop_text`](../../../iris_vector_graph/prop_values.py#L129-L138), [`::decode_json_list_map`](../../../iris_vector_graph/prop_values.py#L234-L248), the two patterns [`_CANONICAL_INT_RE`, `_CANONICAL_FLOAT_RE`](../../../iris_vector_graph/prop_values.py#L90-L91); [`iris_vector_graph/_engine/query.py::_decode_rel_prop_text_columns`](../../../iris_vector_graph/_engine/query.py#L1200-L1216) (arity guard `:1207`); [`iris_vector_graph/cypher/translator.py::_rel_prop_text_columns`](../../../iris_vector_graph/cypher/translator.py#L7517-L7556); unit tests [test_relationship_property_typing.py](../../../tests/unit/test_relationship_property_typing.py)
- Playbook: no statement for this decoder in either arm; neighbor [CYP-B17.1](../../../experiment/playbook-completion/ontology/08-cypher-sql.md#L307) (finding F-0811: no 64-bit cap on this path)
- Verus: see [rel_prop_text](../../Verus_verification/models/rel_prop_text/NOTES.md) (`theorem_decode_classes`, `theorem_noncanonical_stays_text`; reviewed design over ASCII text; control `leading-zero-canonical`). The as-built divergence is recorded as a finding and is observed at unit level on the real function.
- Expands: [Values in results](#query.values)
- Evidence (cloud iteration 24): [value-function observations](../../uplift/consolidated/iteration-24/patterns-params-PAIRS.md)
- agent
- user-facing-behavior, data-integrity

Public case M18. The canonical rule is the decoder's own docstring and patterns; Python's `\d` also matches non-ASCII digits and `$` matches before a final line break, which is where the pin departs from it.

Findings: [Relationship property text with a trailing line break or non-ASCII digits is read back as a number](../../Verus_verification/bugs_issues.md#bug-cyp-101); [coalesce over a relationship property returns its stored text, and a boolean as '1'](../../Verus_verification/bugs_issues.md#bug-cyp-107)

Audit reproduction: [bug-cyp-101](../../Verus_verification/bugs_issues.md#bug-cyp-101) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

State machines: [rel prop text](../../Verus_verification/models/rel_prop_text/manifest.json)
