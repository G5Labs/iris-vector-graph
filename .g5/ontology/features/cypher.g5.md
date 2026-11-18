# Write and read Cypher queries

Find what a Cypher query reads or writes, how clauses and functions behave, and how values appear in results. For native routing, compiled plans and fallback, see [Cypher execution](../architecture/query-execution.g5.md).

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

## Variable-length patterns

<a id="query.paths.varlength"></a>
[I · query.paths.varlength]

A variable-length pattern returns one row per path, as openCypher does, on both paths: from `a` over `a→x→b`, `a→y→b` and `a→b`, `-[:R*1..2]->(t)` returns `b` three times and `x` and `y` once each, `*2..2` returns `b` twice, and `*0..1` includes `a` itself. The ends-only walk the SQL functions use for low bounds keeps these counts.
- The breadth-first route the variable-length fallback reads (`execute_bfs`) lists each node other than the start once, at its least depth, ordered by depth and then ID; a cap keeps the first rows. Its ObjectScript walk and its SQL fallback answer the same rows, and another graph's edges change neither.
- The accelerator walk is chosen only for an outbound walk of the default graph while no other graph holds edges. Otherwise the ObjectScript walk answers, and the SQL walk answers when it walks no edge.
- The ends-only walk uses no relationship twice, so it can end at the start over a cycle; the breadth-first route never lists the start.
- Today a direction other than exactly `out`, `in` or `both` is not refused: `OUT` and unknown text are walked both ways, and `outbound` or `inbound` from the edge rows ([finding](../../Verus_verification/bugs_issues.md#bug-str-114)). Working assumption: refuse it, as for the path routines ([open question](../../Verus_verification/open_questions.md#HD-1003)).

## AQL translation

<a id="query.aql"></a>
[I · query.aql]

`execute_aql` translates AQL into Cypher and passes that text and its bindings to the Cypher reader. For traversal depth, a single integer becomes equal lower and upper bounds; `1..2` keeps both integer bounds, while a decimal depth raises `AQLParseError` before execution.

- Against a literal null on the right, equality becomes `IS NULL` and inequality becomes `IS NOT NULL`. The string `"null"` stays a string comparison, and other operators keep their comparison form.
- This is a translation contract. It does not prove traversal results, Cypher null semantics, bound-parameter null rewriting or the whole AQL language.

## Choose which graph a query reads or writes

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
- Today a `FOREACH` over a literal list whose `SET` reads the loop variable, such as `FOREACH (x IN [1, 2] | SET n.f = x)`, fails with `UndefinedVariable` and writes nothing; a `CREATE` body that reads it runs ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-152)).

<a id="query.writes.atomic"></a>
[I · query.writes.atomic]

One Cypher write is one IVG write transaction:

- With no transaction open by the caller, it commits when the call returns.
- Inside the caller's transaction, the caller's commit keeps it and the caller's rollback removes it.
- A write that fails raises `GraphWriteError` and takes back only its own changes.
- A write that runs in steps, such as one `MERGE` per row, is still one transaction.

<a id="query.writes.adjacency"></a>
[I · query.writes.adjacency]

Where the adjacency index is declared, the rows a Cypher write changes update the adjacency and label indexes in the same transaction, so the next read sees the write on either path. Where it is not declared, Cypher writes leave the adjacency stale until a rebuild ([undeclared index](../architecture/adjacency-and-derived-data.g5.md#structure.adjacency.undeclared)).

<a id="query.writes.ledger"></a>
[D · query.writes.ledger]

Today Cypher writes are not recorded in the ledger. In [strict mode](ledger.g5.md#ledger.strict) they are refused before anything is written; otherwise ledger verification reports them as unrecorded writes. No document decides whether they should be recorded.

<a id="query.writes.subquery"></a>
[I · query.writes.subquery]

A write clause inside a `CALL { }` body is carried out, or the whole query is refused. It is never skipped silently.

<a id="query.writes.create-existing"></a>
[D · query.writes.create-existing]

A node's ID is its identity, so a Cypher `CREATE` of a node whose ID already exists in that graph merges into that node instead of making a second one. The node gains the new labels and any property it lacked, and keeps its old values; to change a value, `SET` it.

<a id="query.writes.computed_values"></a>
[I · query.writes.computed_values]

A `CREATE` stores each property value its map computes, as a `SET` of the same expression stores it.
- Today a node `CREATE` whose value calls a function IVG cannot work out before running the query, such as `size()`, `abs()`, `toInteger()` of a string, `substring()`, `replace()`, `randomUUID()` or `rand()`, is refused with nothing written. `toUpper()`, `trim()`, `coalesce()`, `toString()` and arithmetic are stored ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-119)).
- Today a relationship `CREATE` whose end nodes the same `CREATE` makes keeps only literal values and `UNWIND` literals. Any other value, a computed one such as `1 + 1` or a plain parameter such as `$k`, is dropped without an error, and the relationship has no such property ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-120)). Between matched nodes a literal or a parameter is stored and a computed value is refused ([conformance](#query.conformance)).
- Today a `SET` or `CREATE` whose value is a list holding a property read, such as `[n.a, 1]`, fails with a Python `TypeError` and writes nothing; lists of literals, parameters, `UNWIND` values and arithmetic are stored ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-128)).
- `SET n += {a: 1, b: null}` stores `a` as an integer, removes `b` and keeps the other properties; `SET n = {a: 1}` keeps only `a`; `SET n += {t: toUpper('x')}` stores `'X'`.

<a id="query.writes.retype"></a>
[D · query.writes.retype]

A `SET` that gives a node property a value with the same text and another type stores the new type: `SET n.age = toInteger(n.age)` over the string `'30'` stores the integer 30, as `SET n.age = 30` does.
- From 4.7.0 IVG writes such a value through the `Prop_Set` SQL function. A namespace whose IVG classes predate 4.7.0 keeps the old string until setup deploys the function. IVG checks once per engine whether the function exists, and takes an unreadable answer as yes, so a missing function then fails the write instead of keeping the old type.
- This covers node properties. A relationship property is stored as text and read back by its spelling ([relationship text](#query.values.relationship_text)). Today a relationship `SET` from a function of its own property, such as `SET r.age = toInteger(r.age)`, is refused with a message saying that reading its own property is allowed ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-132)).

<a id="query.writes.delete"></a>
[I · query.writes.delete]

`DELETE n` of a node that has any relationship in its graph, outgoing or incoming, is refused with `GraphWriteError` (ConstraintVerificationFailed) and deletes nothing, whichever writer made the relationship. A node without relationships is deleted, and `DETACH DELETE` removes the node with its relationships, so `get_node` returns None and the native walk no longer reaches it.
- `DELETE r` removes that relationship only. Its endpoints stay, and a later `create_edge` of the same triple makes a new edge. In multigraph mode, deleting one of two parallel edges leaves the other.
- Under `USE GRAPH` only that graph's rows are touched. Without it, a node with the same ID in another graph, and that node's relationships, neither block nor follow the delete.
- `REMOVE n.p` and `REMOVE n:L` remove the property or label for `keys(n)`, `labels(n)` and `get_node` alike.

## Use Cypher through the server

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

<a id="query.aggregation.keys"></a>
[I · query.aggregation.keys]

Grouping keys, `DISTINCT` and `count(DISTINCT)` treat two values as one when they are [equal](#query.values.equality), on both paths. A number and a string are never one value, so the integer 1 and the string "1" are two groups. Whether an integer and a float of equal value, such as 1 and 1.0, are one value is [still open](../../Verus_verification/open_questions.md#query.aggregation.keys.numbers); openCypher compares numbers by value.
- Today on the SQL path a grouping key, `count(DISTINCT)` and `WITH DISTINCT` compare a stored value's text. So a stored number and the string that spells it (1 and "1", 1.0 and "1") are one group, whose key reads as one of them, while `RETURN DISTINCT` and `collect(DISTINCT)` keep them apart ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-135)).
- Today the native executor groups by type, so the same grouped query answers different groups on the two paths ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-136)).
- Over a list the query holds, `UNWIND [1, '1'] AS k` also gives one group and one `DISTINCT` row.
- A boolean and the string that spells it are one stored value ([documented known issue](../../../docs/KNOWN_ISSUES.md#L332-L368)), so they stay one group on both paths.
- Working assumption: an integer and a float of equal value (1 and 1.0) are two groups, as the native executor answers; this is provisional.
- Today on the SQL path, for stored properties, a grouping key and `count(DISTINCT)` make 1 and 1.0 one value, while `RETURN DISTINCT` keeps them apart. Over a list the query holds, `RETURN DISTINCT` and `UNION` also make them one row (`UNWIND [1, 1.0] AS x RETURN DISTINCT x` and `RETURN 1 AS x UNION RETURN 1.0 AS x` each answer one row). Which side departs depends on the open question.
- Today over a list the query holds, a grouping key and `count(DISTINCT)` also make the integer 1 and `true` (0 and `false`) one value, and a list and the string spelling it (`[1]` and `'[1]'`) one value, while `RETURN DISTINCT` keeps them apart. The string `'true'` and `true` stay two groups ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-149)).

<a id="query.aggregation.arithmetic"></a>
[I · query.aggregation.arithmetic]

Arithmetic over aggregates gives the openCypher number: over `v` 1, 2 and `f` 2.5, 1.0, `sum(n.v) + sum(n.f)` is 6.5.
- Today arithmetic that combines two aggregates of stored properties, or such an aggregate with an integer, is read back as a whole number rounded half to even: 6.5 answers 6, 2.5 answers 2 and 3.5 answers 4, on nodes and relationships, whichever writer stored the values ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-137)). An aggregate alone, or beside a float literal, keeps its value.

## Reading clauses

<a id="query.optional"></a>
[I · query.optional]

`OPTIONAL MATCH` keeps every row that reaches it. Where its pattern has no match, the row continues once with the pattern's new variables null, and later expressions read them as null.
- A `WHERE` inside the `OPTIONAL MATCH` filters only its matches and never drops the row; a `WITH ... WHERE` after it drops the rows whose test is null.
- A relationship type or label that no edge or node has gives that null row, not an error and not zero rows.
- Aggregates leave the nulls out: for an unmatched row `count(b)` is 0, `collect(b.x)` is `[]`, `sum` is 0 and `avg` is null, while `count(*)` counts the row ([aggregation](#query.aggregation)).
- It reads relationships written by the API, by Cypher and in a named graph alike, and always runs on the SQL path.
- Today a `WHERE` inside it that combines a variable bound earlier with arithmetic or `OR`, such as `b.v = a.v + 1`, fails the query with SQLCODE -94 ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-142)).
- Today a comparison in that `WHERE` on a property of a variable bound earlier, such as `b.v = a.v`, drops the rows of the nodes that lack the property instead of keeping them with nulls ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-143)).
- A path variable the `OPTIONAL MATCH` did not bind is null, and so are `length(p)`, `nodes(p)` and `relationships(p)`. Today `length(p)` of an unbound fixed-length path answers the pattern's relationship count instead, such as 1 for `p = (a)-[:K]->(b)`, while `p IS NULL` is true. A variable-length path gives null as it should ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-146)).
- A leading `OPTIONAL MATCH` with no match gives one row: with aggregates alone, `count(*)` is 1, `count(b)` 0, `sum` 0, `avg` null and `collect` `[]`. Today, when the `RETURN` also has a grouping key, `sum` on that row is null instead of 0 ([finding](../../Verus_verification/bugs_issues.md#bug-agg-001)).
- A `WHERE` inside it that reads only its new variables runs and keeps every row, whatever its `AND`, `OR`, `NOT` and arithmetic, such as `b.v = 2 OR b.v = 3` or `b.v - 1 = 2`. Today the SQLCODE -94 refusal follows negation: `NOT (b.v = a.v OR b.v = 10)` runs, while `NOT (b.v = a.v + 1)` and `NOT (b.v = 10 AND b.v = a.v)` are refused ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-142)).
- A property of a node the `OPTIONAL MATCH` did not bind is null at every reader and under both IRIS drivers, also through a `WITH`, and `collect()` of the unbound node is `[]`. Today the unbound node itself, at `execute_cypher`, `/api/cypher` and tx/commit (its three columns), answers `b_id` null but `b_labels` and `b_props` as `'[]'`; Bolt answers the node as null ([finding](../../Verus_verification/bugs_issues.md#bug-plt-135)).

<a id="query.with"></a>
[I · query.with]

`WITH` ends one part of a query and passes its rows on: the next part sees exactly the variables `WITH` names, and `WITH *` passes every variable in scope, nodes, relationships and values alike.
- `WITH *` may be followed by more items, such as `WITH *, a.v AS av`, which add to the variables passed on.
- A `CALL { }` subquery imports variables with a first `WITH`; it may import any variable in scope, whatever clause bound it, and runs once per incoming row.
- `DISTINCT`, `ORDER BY`, `SKIP` and `LIMIT` after `WITH` follow [paging](#query.paging); aggregation in `WITH` follows [aggregation](#query.aggregation).
- Today `WITH *` does not carry a relationship variable, so a later `type(r)` fails with SQLCODE -29 ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-150)), and `WITH *, a.v AS av` does not parse ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-151)).
- Today a `CALL { }` subquery that imports an `UNWIND` variable fails, and so does one that imports a node and has no `MATCH` of its own; importing a node into a subquery that matches from it works ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-157)).

<a id="query.paging"></a>
[I · query.paging]

`DISTINCT`, `ORDER BY`, `SKIP` and `LIMIT` apply in that order to the rows a `RETURN` or `WITH` produces.
- `RETURN DISTINCT n` keeps two nodes that share every property value; `RETURN DISTINCT n.name` keeps one row per value.
- `ORDER BY` may name a returned alias, or after `WITH` a column that is not returned. Null sorts last ascending and first descending ([sorting](#query.values.sorting)).
- `SKIP` and `LIMIT` take a non-negative integer, written in the query or passed as a parameter. A negative one is refused with NegativeIntegerArgument, a fractional float with InvalidArgumentType, and `LIMIT 0` gives no rows.
- Today a parameter of another type is used as a count: the string "2" as 2, true as 1 and 2.0 as 2. The string "x" fails with a Python `ValueError`, and a null parameter is reported as not provided ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-139)).

<a id="query.parameters"></a>
[I · query.parameters]

A parameter supplies a value of its own type wherever the query could hold a literal, on `execute_cypher`, Bolt and the HTTP routes. The answer should not depend on which IRIS Python driver runs the query.
- Working assumption: intersystems-irispython 5.3.x, the version the repository's lock file pins, is a supported driver ([question](../../Verus_verification/open_questions.md#query.parameters.drivers)).
- Scalars, lists, maps and null come back unchanged from `RETURN $x`, and `IN $list`, `SKIP $s` and `LIMIT $l` work on both drivers. A parameter that is not supplied is refused as an undefined variable.
- Today with driver 5.3.2, `UNWIND $list`, `$l[$i]` and `$l[$s..$e]` fail with "Invalid number of parameters"; with 5.4.1 they run. Passing the list through `WITH $list AS l` first works with both ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-125)).
- Today with driver 5.4.1, `$l[$s..$e]` answers the empty list, and `$l[$i]` answers the element as text ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-144)).
- A string parameter is compared as a string literal is ([equality](#query.values.equality)).

<a id="query.union"></a>
[I · query.union]

`UNION` combines the rows of its branches and removes duplicate rows; `UNION ALL` keeps them. Every branch returns the same column names, and one query does not mix the two; IVG refuses either mistake with a `SyntaxError` that names it.
- Each value keeps its type, and duplicate rows are rows of [equal](#query.values.equality) values.
- Today a stored property value in a branch reaches the reader as its storage text: the integer 1 as "\x01N1", 2.5 as "\x01D2.5", a list as JSON text, a boolean as "true", and a relationship number as text. Duplicate removal compares those raw values, so a stored 1 and a literal 1 stay two rows while the literals 1 and true become one ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-138)).
- Today a branch that is a whole-label count, such as `MATCH (n:L) RETURN count(n) AS x`, fails with SQLCODE -1 ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-140)).
- The refusals do not use the TCK's error names (DifferentColumnsInUnion, InvalidClauseComposition).
- Today a relationship in a `UNION ALL` branch reaches the reader as its JSON text, such as `'{"type":"K","props":{}}'`, while `RETURN r` alone answers a map ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-138)).
- Today a literal list in a branch also reaches the reader as its JSON text (`'[1, 2]'`), while `RETURN [1,2]` alone answers a list ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-138)).

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
- Relationship properties are stored in qualifier text and follow their separately owned decoder; preserving a node's stored type does not establish that relationship values preserve their original type.
- A returned value keeps its Cypher type at every reader and with every supported IRIS driver, whatever expression produced it: a number stays a number, a boolean a boolean, and a list or map a list or map. The four readers are the Python engine, Bolt, `/api/cypher` and `/db/neo4j/tx/commit`.
- Today a `CASE` column whose branches are node properties is not decoded: a stored boolean answers `'true'`, a stored list or map its JSON text, and with IRIS driver 5.4.1 a stored number its text (`'3'`), on every reader ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-156)).
- Today `WITH coalesce(n.a, n.b) AS x ... RETURN x` answers a stored number or boolean as text (`'3'`, `'true'`) under both drivers, while `RETURN coalesce(n.a, n.b)` is typed ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-155)).

<a id="query.values.equality"></a>
[I · query.values.equality]

A `WHERE` equality between a stored property and a boolean or integer literal follows how each kind of property is stored, not the value `RETURN` shows.
- A boolean literal matches the stored text `true`, `1` or `True` (for `false`: `false`, `0`, `False`) on nodes and relationships. A node's stored integer 1 or 0 matches too, so `n.p = true` keeps a node whose `p` reads back as the integer 1 or the string "1".
- An integer literal on a node matches only a stored number of that value: the string "1" and a node boolean do not equal 1.
- An integer literal on a relationship matches the qualifier text that spells the integer or its float twin (`1`, `1.0`), so a JSON boolean (read as 1 or 0), the string "1" and the string "1.0" all equal 1.
- A whole JSON float on a relationship keeps its spelling (`1.0`), so it equals 1 but not `true`; the same value stored as a node double equals both.
- The boolean legacy match is a documented known issue that typed storage is planned to remove in 4.8.0; openCypher equality matches only values of the same type.
- Today a string literal or string parameter that spells a node's stored number equals it: `n.v = '1'` and `n.v = $x` with `$x = '1'` keep a node whose `v` is the integer 1, although an integer literal or parameter matches only the number ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-145)).

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
- Today over a list the query holds, `RETURN ... ORDER BY` sorts a boolean among the numbers (`UNWIND [2,'a',null,1.5,true] AS x RETURN x ORDER BY x` answers `1.5, true, 2, 'a', null`), while the same list sorted after `WITH` follows the key ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-158)).

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

<a id="query.values.conditions"></a>
[I · query.values.conditions]

A boolean value can be a `CASE WHEN` or `WHERE` condition wherever it comes from: a stored property, a literal, a comparison, an `UNWIND` row, a `WITH` column or a parameter. A generic `CASE` over stored or run-time values gives the openCypher answer, a simple `CASE` takes the first `WHEN` [equal](#query.values.equality) to its test, and a missing value takes the `ELSE`.
- Today a bare boolean from an `UNWIND` row, a `WITH` column or a parameter fails the whole query (`UNWIND [true] AS b RETURN CASE WHEN b THEN 1 END`, `WITH b WHERE b`). Comparing it (`b = true`) or negating it (`NOT b`) works ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-118)).
- Today a simple `CASE` whose test is a property or a run-time value takes a `WHEN` of another type when the text matches: with `n.s = '1'`, `CASE n.s WHEN 1 THEN 'num' END` gives `'num'`, although `n.s = 1` is false. A literal test, and a `WHEN` of the same type, follow the rule ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-127)).

## Built-in functions

<a id="query.functions"></a>
[I · query.functions]

Cypher's built-in list, string, map and aggregate functions give the openCypher answer whether an argument is written in the query or is known only when the query runs: a stored property, an `UNWIND` row, a `WITH` column or a parameter.
- `head()` and `last()` of an empty list are null, and `tail()` of one is the empty list. Elements keep their types, for lists written by Cypher or by the Python API.
- `split()` keeps empty pieces (`split('a,b,,c', ',')` is `['a', 'b', '', 'c']`), `split('', ',')` is `['']`, a null string gives null, and an empty separator splits into characters.
- `keys()` of a relationship lists its properties, and `keys()` of a map lists every key, including one whose value is null.
- `s =~ p` matches the whole string, and a null string gives null.
- A function given a value of the wrong type fails the query. Today the error text does not say `TypeError` ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-116)).

<a id="query.functions.list_index"></a>
[I · query.functions.list_index]

`list[i]` counts a negative `i` from the end, an `i` past either end gives null, a null `i` gives null, and the element keeps its type.
- Today this holds for an index written in the query, and for a run-time index into a list a `WITH` holds from a literal (`WITH [1, 2, 3] AS l UNWIND [-1] AS i RETURN l[i]` gives 3).
- Today, for a list read from a property (directly or through a `WITH` column), a negative run-time index fails the whole query and a non-negative one answers the element as text (`'1'` for 1); a negative parameter index fails for every list ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-111)).
- Today a null index taken from a row (`UNWIND [null] AS i`), and `l[null]` on a list a row holds, give the list's first element ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-126)).
- Today a null parameter index (`l[$i]` with `i` null) fails the whole query with "Incorrect number of parameters", for every list. `[1, 2, 3][null]` written in the query gives null, as the rule says.

<a id="query.functions.reverse"></a>
[I · query.functions.reverse]

`reverse()` of a list is the list in reverse order, and of a string the reversed string.
- Today `reverse()` of a list read from a property, a slice, a subscript or a `coalesce()` reverses the list's JSON text, so `[1, 2, 3]` gives the string `']3 ,2 ,1['` ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-112)).
- Today `reverse()` of a `WITH` column that holds a list from a property reverses the list but answers its JSON text, the string `'[3,2,1]'`. A list literal, a list a `WITH` holds from a literal, and a call that answers a list (`tail()`, `split()`, `+`) give the list ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-112)).

<a id="query.functions.dynamic_access"></a>
[I · query.functions.dynamic_access]

`n[k]` reads the property of node `n` whose name is the value of `k`, and `m[k]` reads that key of map `m`; a missing name gives null.
- Today a node key that comes from `UNWIND` is read as the literal name `k`, so `UNWIND keys(n) AS k RETURN n[k]` gives null for every key, and a key from a `WITH` column (`WITH n, 'num' AS k RETURN n[k]`) fails the query; a parameter key works ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-113)).
- Today a map value read by key comes back as text: `'1'` for 1 and for `true` ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-115)).

<a id="query.functions.range"></a>
[I · query.functions.range]

`range(start, end, step)` lists `start`, `start + step`, ... up to `end`, and is empty when the step points away from `end`. A step of 0 is an error (NumberOutOfRange).
- Today a step of 0 that is known only at run time gives `[]` instead of the error; a step of 0 written in the query is refused ([finding](../../Verus_verification/bugs_issues.md#F-C0841)).
- The arguments are integers. Today a fractional step known only at run time is used as it is (`range(1, 3, s)` with `s = 1.5` gives `[1, 2.5]`); one written in the query is refused ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-131)).

<a id="query.functions.percentile"></a>
[D · query.functions.percentile]

`percentileDisc(x, p)` returns the stored value at the nearest rank, and `percentileCont(x, p)` interpolates between the two nearest values. Both leave out nulls, give null when no value remains, and fail with NumberOutOfRange when `p` is outside 0 to 1.
- Over 10, 20, 30 and 40 at 0.5, `percentileDisc` gives 20 and `percentileCont` 25.0, as Neo4j does.
- Today `percentileDisc` takes the value at position (n − 1) × p rounded down, not the nearest rank. Over 10, 20, 30 and 40, p 0.6 gives 20 and p 0.9 gives 30, where Neo4j gives 30 and 40; p 0.95 over 1 to 10 gives 9, not 10 ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-134)).
- `percentileDisc` answers one of the values, so over integers it answers an integer, as Neo4j does; `percentileCont` answers a float. Today both answer a float, also over integers (20.0) ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-147)).
- `p` must be a number. Today a null `$p` parameter fails with Python's raw `TypeError` and other text with a raw `ValueError`; a numeric string or a boolean parameter is used as a number (true as 1); and a literal `null` answers the p = 0 value ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-148)).

<a id="query.functions.random"></a>
[I · query.functions.random]

Each call of `randomUUID()` returns a new UUID, and each call of `rand()` a new number from 0 up to 1.
- Today every row of a query gets the same value from each, and a `CREATE` that sets a property from `randomUUID()` or `rand()` is refused with nothing written ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-114)). The refusal is shared with other functions; [computed values](#query.writes.computed_values) owns it.

<a id="query.functions.sql_helpers"></a>
[D · query.functions.sql_helpers]

The SQL functions `CypherFn_IVG*` are kept for SQL callers. Cypher queries reach only four of them: the run-time `range()`, the type-error signal, and the relationship property set and remove helpers. The other list, map, string and regex functions that Cypher uses are separate SQL functions created at setup.
- So the answers above come from the translator and those setup functions. `CypherFn_IVGLISTGET` already counts a negative index from the end, but Cypher does not use it.

<a id="query.functions.slice"></a>
[I · query.functions.slice]

`list[a..b]` gives the elements from position `a` up to, but not including, `b`. A negative bound counts from the end, a bound past either end is clamped to the list, and a null bound gives null.
- Today this holds for bounds written in the query and for run-time bounds of 0 or more. A negative bound known only at run time counts as 0, so `l[-3..5]` gives the whole list and `l[0..-1]` gives `[]` ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-117)).
- Today a lower bound that is a variable name does not parse: `l[a..3]`, `l[a..b]` and `l[a..]` are refused, while `l[$a..3]` and `l[x[0]..3]` work ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-122)).
- Today slicing a null list gives `[]` instead of null ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-129)). With the fixture's driver a slice of a parameter list by parameter bounds (`$l[$s..$e]`) fails, while `WITH $l AS l RETURN l[$s..$e]` works ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-125)).

<a id="query.functions.strings"></a>
[I · query.functions.strings]

String functions give the openCypher answer for literal and run-time arguments alike. `toUpper`, `toLower`, `trim`, `ltrim`, `rtrim` and `replace` (every occurrence) work on the text, and the trim functions remove leading or trailing whitespace; `substring(s, start, length)` counts from 0 and takes at most `length` characters; `left` and `right` take at most that many; `size()` counts a string's characters or a list's elements; `toInteger` and `toFloat` read numeric text and give null for other text.
- A negative start or length is an error. Today a negative `substring` start answers leading characters (`substring('hello', -1, 2)` is `'h'`), a negative length fails with an IRIS error that names no Cypher error, and `left(s, -1)` is null ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-123)).
- A length of 0 gives the empty string. Today `left(s, 0)`, `right(s, 0)` and `substring(s, 1, 0)` give null ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-124)).
- Today `trim()` in a result or a `SET` removes spaces only, so `trim('\t a \n')` is unchanged and `rtrim()` keeps a line break, while a node `CREATE` of the same `trim()` removes tabs and line breaks too ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-130)).

<a id="query.functions.coalesce"></a>
[I · query.functions.coalesce]

`coalesce(...)` gives its first argument that is not null, with that argument's type.
- Today the type is kept only when one argument is a node property and every other is a node property, a single literal value or a parameter. Otherwise a number or boolean comes back as text: `UNWIND [7] AS x RETURN coalesce(x, 1)` gives `'7'` and `coalesce(null, 1)` gives `'1'` ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-121)). A relationship property follows [relationship text](#query.values.relationship_text).

<a id="query.functions.path_elements"></a>
[I · query.functions.path_elements]

Path functions read the path the pattern matched, whichever writer made its edges and in whichever graph. `length(p)` counts its relationships, `nodes(p)` and `relationships(p)` list them in order, `type(r)` names the type, and `startNode(r)` and `endNode(r)` are the edge's source and target whatever direction the pattern used.
- `nodes(p)` of a variable-length path answers node ids ([documented known issue](../../../docs/KNOWN_ISSUES.md#L421-L433)); `[x IN nodes(p) | x.name]` reads through the path.
- Today `startNode(r)` and `endNode(r)` of an element of `relationships(p)` fail with SQLCODE -29, while `type(r)` and `r.p` of it answer ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-141)).
- Outside multigraph mode a pattern sees one relationship per source, type and target, however often `create_edge` or `bulk_create_edges` wrote it. `create_edge` keeps one edge per triple in multigraph mode too ([multigraph](graph-structure.g5.md#structure.multigraph)); there only a Cypher `CREATE` adds a parallel edge.

## Earlier links

These links take you to the current sections and statements.

<a id="cypher"></a>

[Write and read Cypher queries](#write-and-read-cypher-queries)

<a id="two-paths"></a>

[When does Cypher use SQL or the native executor?](../architecture/query-execution.g5.md#when-does-cypher-use-sql-or-the-native-executor)

<a id="native-executor"></a>

[Check whether a read can run natively](../architecture/query-execution.g5.md#check-whether-a-read-can-run-natively)

<a id="shadow-mode"></a>

[Compare both executors in shadow mode](../architecture/query-execution.g5.md#compare-both-executors-in-shadow-mode)

<a id="compiled-plans"></a>

[Compile a read plan and decide when to reuse it](../architecture/query-execution.g5.md#compile-a-read-plan-and-decide-when-to-reuse-it)

<a id="graph-scope"></a>

[Choose which graph a query reads or writes](#choose-which-graph-a-query-reads-or-writes)

<a id="entry-points"></a>

[Use Cypher through the server](#use-cypher-through-the-server)

<a id="query.paths"></a>

[query.paths](../architecture/query-execution.g5.md#query.paths)

<a id="query.native"></a>

[query.native](../architecture/query-execution.g5.md#query.native)

<a id="query.native.gates"></a>

[query.native.gates](../architecture/query-execution.g5.md#query.native.gates)

<a id="query.native.privileges"></a>

[query.native.privileges](../architecture/query-execution.g5.md#query.native.privileges)

<a id="query.native.reads-only"></a>

[query.native.reads-only](../architecture/query-execution.g5.md#query.native.reads-only)

<a id="query.native.equal-answers"></a>

[query.native.equal-answers](../architecture/query-execution.g5.md#query.native.equal-answers)

<a id="query.native.sql-first"></a>

[query.native.sql-first](../architecture/query-execution.g5.md#query.native.sql-first)

<a id="query.native.fallback"></a>

[query.native.fallback](../architecture/query-execution.g5.md#query.native.fallback)

<a id="query.native.route"></a>

[query.native.route](../architecture/query-execution.g5.md#query.native.route)

<a id="query.shadow"></a>

[query.shadow](../architecture/query-execution.g5.md#query.shadow)

<a id="query.compiled"></a>

[query.compiled](../architecture/query-execution.g5.md#query.compiled)

<a id="query.compiled.equal-answers"></a>

[query.compiled.equal-answers](../architecture/query-execution.g5.md#query.compiled.equal-answers)

<a id="query.compiled.modes"></a>

[query.compiled.modes](../architecture/query-execution.g5.md#query.compiled.modes)

<a id="query.compiled.never-stale"></a>

[query.compiled.never-stale](../architecture/query-execution.g5.md#query.compiled.never-stale)

<a id="query.compiled.deploy-discards"></a>

[query.compiled.deploy-discards](../architecture/query-execution.g5.md#query.compiled.deploy-discards)

<a id="query.compiled.fallback"></a>

[query.compiled.fallback](../architecture/query-execution.g5.md#query.compiled.fallback)

<a id="query.compiled.integrity"></a>

[query.compiled.integrity](../architecture/query-execution.g5.md#query.compiled.integrity)

## Metadata

### query.paths.varlength

- uncertain
- Sources: [4.7.0 changelog: CY_VLP_ENDS reads ^KG](../../../CHANGELOG.md#L3057-L3060), [`Graph.KG.VarLength`](../../../iris_src/src/Graph/KG/VarLength.cls)
- Evidence: [predictions and native observations on both engines](../../uplift/consolidated/iteration-21/varlength-PAIRS.md)
- Expands: [Two query paths](../architecture/query-execution.g5.md#query.paths)
- agent
- user-facing-behavior
- Verus: [traversal_strategy](../../Verus_verification/models/traversal_strategy/NOTES.md) `theorem_os_rows_eq_sql_rows`, `theorem_bfs_never_lists_source`, `theorem_one_row_per_node`, `theorem_cap_keeps_nearest_prefix`, `theorem_arno_only_default_outbound`, `theorem_fixture_path`, `theorem_vl_ends_list_source_bfs_does_not`, `theorem_vl_both_no_backtrack`, `theorem_unknown_direction_walks_both` (as built, iteration 57)
- Evidence: [iteration-57 frozen predictions B1-B7](../../uplift/consolidated/iteration-57/w61-PAIRS.md), [observations](../../uplift/consolidated/iteration-57/strategy/OBSERVED.md)
- Findings: [bug-str-114](../../Verus_verification/bugs_issues.md#bug-str-114)

As-built agreement with openCypher, observed natively. From iteration 57 the breadth-first and ends-only routes have an as-built formal contract (`traversal_strategy`); the Cypher row projection over them does not.

### query.aql

- design-verified

- Sources: [numeric lexer](../../../iris_vector_graph/cypher/aql/lexer.py#L164-L174), [depth parser](../../../iris_vector_graph/cypher/aql/parser.py#L89-L105), [null translator](../../../iris_vector_graph/cypher/aql/translator.py#L97-L110), [hop writer](../../../iris_vector_graph/cypher/aql/translator.py#L159-L180), [execute_aql](../../../iris_vector_graph/_engine/query.py#L1730-L1745)
- Verus: [aql_frontend](../../Verus_verification/models/aql_frontend/NOTES.md), as-built `lex`, `depth`, `hops`, `resolve`; raw suffix/typed token/AST/predicate projection. Actual output text and public adapter observed with a recorded Cypher consumer; query execution remains unproved.
- Expands: [query paths](../architecture/query-execution.g5.md#query.paths)
- agent
- user-facing-behavior

Audit reproduction: [F-0824](../../Verus_verification/bugs_issues.md#F-0824) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [Two slashes inside an AQL string start a comment](../../Verus_verification/bugs_issues.md#F-0824).

State machines: [aql frontend](../../Verus_verification/models/aql_frontend/manifest.json)

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
- Children: [atomic](#query.writes.atomic), [adjacency](#query.writes.adjacency), [ledger](#query.writes.ledger), [subquery](#query.writes.subquery), [create existing](#query.writes.create-existing), [computed values](#query.writes.computed_values), [retype](#query.writes.retype), [delete](#query.writes.delete), [Should a Cypher `DELETE` clean up everything the engine's own [node delete](graph-structure.g5.md#structure.node.delete) and edge delete clean up?](../../Verus_verification/open_questions.md#query.writes.delete-scope).

Sources: [CHANGELOG 4.6.0, every statement uses the rows its MATCH bound](../../../CHANGELOG.md#L1742-L1744), [spec 229](../../../specs/229-tck-write-verification/spec.md), [`_write_ids`, `_capture_key`](../../../iris_vector_graph/cypher/translator.py#L13093-L13164), [`execute_transaction`](../../../iris_vector_graph/stores/iris_sql_store.py#L1580-L1818). Live: the TCK's write scenarios with side-effect counting, and `test_460_all_graphs_writes_e2e.py`.

Audit reproduction: [F-C0848](../../Verus_verification/bugs_issues.md#F-C0848) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [A Cypher CREATE or MERGE with literal or parameter endpoint ids drops a parameter-bound relationship property without an error](../../Verus_verification/bugs_issues.md#F-C0848).

Audit reproduction: [F-0822](../../Verus_verification/bugs_issues.md#F-0822) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [CREATE or MERGE after UNWIND $p AS e WITH e fails](../../Verus_verification/bugs_issues.md#F-0822).

Audit reproduction: [F-C0849](../../Verus_verification/bugs_issues.md#F-C0849) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [A relationship property bound by a WITH before a literal-endpoint CREATE is stored as text that is not JSON](../../Verus_verification/bugs_issues.md#F-C0849).

Open questions: [Should a Cypher `DELETE` clean up everything the engine's own [node delete](graph-structure.g5.md#structure.node.delete) and edge delete clean up?](../../Verus_verification/open_questions.md#query.writes.delete-scope)

Iteration 58 (W62 C6, partial): [W62 predictions and results](../../uplift/consolidated/iteration-58/w62-PAIRS.md). Findings: [FOREACH with a SET body that reads the loop variable fails](../../Verus_verification/bugs_issues.md#bug-cyp-152).

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

### query.writes.computed_values

- agent
- user-facing-behavior, data-integrity
- Expands: [Writes](#query.writes).
- Sources: openCypher (`Create*`, `Set*`); [`translator.py` `_create_resolve_prop_value`, `_fold_constant`](../../../iris_vector_graph/cypher/translator.py#L9319-L9671); [`_create_clause_relationship_entry`](../../../iris_vector_graph/cypher/translator.py#L10183-L10246); [W55 predictions and results](../../uplift/consolidated/iteration-48/cypherexpr-PAIRS.md)
- Verus: active: [`cypher_exprs.rs`](../../Verus_verification/models/cypher_exprs/NOTES.md) `folds`, `create_node_value`, `create_rel_value`; neighbors `theorem_folded_create_value_written`, `theorem_inline_rel_literal_written`; as-built departures `theorem_unfolded_create_value_refused` (control `create-value-translated` is the repair), `theorem_inline_rel_expression_dropped` (control `rel-value-kept`) and `theorem_inline_rel_param_dropped` (control `rel-param-kept`, iteration 50); the node refusal rests on observed driver behavior. The list-literal `TypeError` (third bullet) is observed only

Recovered in iteration 48. A `SET` of each of the 15 function shapes probed is stored; the two `CREATE` paths decide by the value's syntax and by what the Python constant folder can work out.

Simplification: [One SQL path for values a write computes](../../Verus_verification/design_simplification.md#simp-cyp-102)

Findings: [A node CREATE whose map value calls an unfolded function is refused](../../Verus_verification/bugs_issues.md#bug-cyp-119); [A relationship CREATE between new nodes drops every computed or parameter property value](../../Verus_verification/bugs_issues.md#bug-cyp-120); [A SET or CREATE of a list literal that holds a property read fails with a raw Python TypeError](../../Verus_verification/bugs_issues.md#bug-cyp-128); [randomUUID() and rand() in a CREATE](../../Verus_verification/bugs_issues.md#bug-cyp-114)

Iteration 58 (W62 C7, held; observed only): [W62 predictions and results](../../uplift/consolidated/iteration-58/w62-PAIRS.md).

### query.writes.retype

- agent
- data-integrity, architecture-decision
- Expands: [Writes](#query.writes).
- Sources: KNOWN_ISSUES "A property cannot tell a number from a string that spells it" (workaround, 4.7.0); [`translator.py` `_prop_set`](../../../iris_vector_graph/cypher/translator.py#L12960-L12968); [`PropWrite.cls` `SetVal`](../../../iris_src/src/Graph/KG/PropWrite.cls); [`SqlProcs.cls` `PropSet`](../../../iris_src/src/Graph/KG/SqlProcs.cls#L187-L190); [`engine.py` `_prop_set_deployed`](../../../iris_vector_graph/engine.py#L1762-L1781); [W55 predictions and results](../../uplift/consolidated/iteration-48/cypherexpr-PAIRS.md)
- Verus: active: [`cypher_exprs.rs`](../../Verus_verification/models/cypher_exprs/NOTES.md) `setval`, `node_update`; `prop_set_deployed`; `theorem_prop_set_retypes`, `theorem_prop_set_switch_decides_retype` (the engine's switch from its dictionary read, iteration 50; control `unreadable-taken-as-absent`), neighbor `theorem_without_prop_set_same_text_keeps_old` (conditional on the filer premise; controls `setval-skips-retype`, `prop-set-not-emitted`, `filer-writes-same-text`). The relationship bullet is observed only

Recovered in iteration 48; frozen prediction W4 held. The binding observed both paths on the fixture, the second through the product's own switch for a namespace without `Prop_Set`.

Findings: [A relationship SET from a function of its own property is refused with a message that says such a read is allowed](../../Verus_verification/bugs_issues.md#bug-cyp-132)

### query.writes.delete

- Expands: [Writes](#query.writes)
- Sources: [USER_GUIDE, DELETE refusal](../../../docs/USER_GUIDE.md#L334-L345); openCypher TCK `Delete1`-`6`; [`translate_delete_clause`](../../../iris_vector_graph/cypher/translator.py#L10625-L10816); [`IRISGraphStore.execute_transaction`](../../../iris_vector_graph/stores/iris_sql_store.py#L1746-L1756); [W59 predictions DL1-DL6 and results](../../uplift/consolidated/iteration-54/clauses-PAIRS.md)
- Verus: active: [`cypher_clauses.rs`](../../Verus_verification/models/cypher_clauses/cypher_clauses.rs) `as_built_delete`, `theorem_delete_follows_rule`, `theorem_incoming_only_refused` (controls `delete-outgoing-only`, `delete-no-check`); [scope](../../Verus_verification/models/cypher_clauses/NOTES.md)
- agent
- user-facing-behavior, data-integrity

Recovered in iteration 54 from the frozen predictions DL1-DL6, which all held on API-written edges in the default graph, a named graph and a multigraph graph; the cross-graph neighbor was checked after the source was read and agreed. Whether a Cypher `DELETE` should also clean up what the engine's own deletes clean up stays the open question [query.writes.delete-scope](../../Verus_verification/open_questions.md#query.writes.delete-scope).

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
- Children: [keys](#query.aggregation.keys), [arithmetic](#query.aggregation.arithmetic)
- Sources: [USER_GUIDE, grouped reporting](../../../docs/USER_GUIDE.md#L165); [typed property sums and WITH](../../../tests/unit/test_sum_column_typing.py); [known-list typed collection](../../../tests/unit/test_460_r308_collect_typed.py); [empty result columns](../../../tests/unit/test_empty_result_columns.py); [aggregate order and page scope](../../../tests/unit/test_order_limit_aggregate_scope.py); [count DISTINCT with LIMIT](../../../tests/e2e/test_470_issue13_count_distinct_limit_e2e.py)
- Verus: [aggregate_results.rs](../../Verus_verification/models/aggregate_results/aggregate_results.rs) `theorem_raw_group_SUM_reaches_typed_scalar_reader`, `theorem_key_enumeration_complete_unique`, `theorem_full_output_before_page` and `theorem_reader_projection_keeps_exact_public_cells`; [scope](../../Verus_verification/models/aggregate_results/NOTES.md). Narrowed (iterations 54 and 56, [model NOTES](../../Verus_verification/models/aggregate_results/NOTES.md#narrowed-scope-iterations-54-and-56)): `theorem_key_enumeration_complete_unique` takes key equality as a premise that IRIS meets only for keys of one kind ([keys](#query.aggregation.keys)); `theorem_numeric_distinct_normalizes_int_and_whole_double` is conditional on the open question [query.aggregation.keys.numbers](../../Verus_verification/open_questions.md#query.aggregation.keys.numbers) and is not a guarantee under the provisional working assumption. Raw rows and a RETURN AST fragment derive groups, folds, result kind and full output before paging; exact integer/half-unit arithmetic, SQL equality/aggregate operations, JSON spelling/parsing, raw-name generation and collation remain stated provider frames. Native Group/GroupOf/EmitGroups have inspected typed count transcriptions only, under their nonnull/pW1/equality/order premises; the SQL native panels do not execute those bodies. OPTIONAL synthetic fallback remains observed and partial under bug-agg-001.
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

Findings: [A grouping key and count(DISTINCT) treat a stored number and the string spelling it as one value, while RETURN DISTINCT keeps them apart](../../Verus_verification/bugs_issues.md#bug-cyp-135) (iteration 54: grouping keys and DISTINCT, owned by [keys](#query.aggregation.keys)); [Arithmetic over two property aggregates answers a rounded integer: sum(n.v) + sum(n.f) of 3 and 3.5 answers 6](../../Verus_verification/bugs_issues.md#bug-cyp-137) (owned by [arithmetic](#query.aggregation.arithmetic))

Iteration 58 (W62 C1, held): the aggregates over an `OPTIONAL MATCH` null row after a `MATCH` (`count(b)` 0, `count(*)` 1, `collect` `[]`, `sum` 0, `avg` null) are modeled in [clause_combos](../../Verus_verification/models/clause_combos/NOTES.md). Findings: [Over a list the query holds, grouping merges 1 with true](../../Verus_verification/bugs_issues.md#bug-cyp-149).

### query.aggregation.keys

- uncertain
- Expands: [Aggregate results](#query.aggregation)
- Sources: openCypher TCK `Return6`, `Aggregation*`; CIP2016-06-14 (equivalence); [`translate_return_clause` 30676 and 30777](../../../iris_vector_graph/cypher/translator.py#L30670-L30777); [`_expr_aggregation` 24431](../../../iris_vector_graph/cypher/translator.py#L24425-L24431); [`Graph.KG.Cypher.Exec.GroupOf`](../../../iris_src/src/Graph/KG/Cypher/Exec.cls#L1349-L1380); [W59 predictions AG1, AG2 and results](../../uplift/consolidated/iteration-54/clauses-PAIRS.md)
- Verus: active: [`cypher_clauses.rs`](../../Verus_verification/models/cypher_clauses/cypher_clauses.rs) `key_of`, `together`; departures `theorem_sql_group_merges_number_and_its_text`, `theorem_paths_disagree_exactly_on_marked_text`, `theorem_sql_group_and_distinct_disagree_on_marked_text`; neighbors `theorem_sql_return_distinct_keeps_kinds`, `theorem_native_group_follows_rule` (controls `group-by-typed`, `return-distinct-text`, `native-text-key`, `int-unmarked`)
- agent
- user-facing-behavior, data-integrity

Recovered in iteration 54: the frozen predictions AG1 and AG2 missed. This also bounds the inherited [aggregate results](../../Verus_verification/models/aggregate_results/NOTES.md) model, whose SQL key equality was a named provider premise: on IRIS it holds only for keys of one kind. Iteration 56 (review 53-55 F3): the opening sentence no longer states the integer/float case as settled, and the model's `theorem_numeric_distinct_normalizes_int_and_whole_double` is marked conditional on the open question. The bullet on 1 and 1.0 today rests on the reviewer's probe (`int_float_group`: one group of two; `int_float_countdistinct`: 1; `int_float_distinct`: two rows; [observations](../../uplift/consolidated/iteration-56/review-probes/rv55-observed-20261117T064229Z.json)).

Findings: [A grouping key and count(DISTINCT) treat a stored number and the string spelling it as one value, while RETURN DISTINCT keeps them apart](../../Verus_verification/bugs_issues.md#bug-cyp-135); [The SQL path and the native executor group the same stored values differently](../../Verus_verification/bugs_issues.md#bug-cyp-136)

Open questions: [Do an integer and a float of equal value fall in one group?](../../Verus_verification/open_questions.md#query.aggregation.keys.numbers)

Iteration 58 (W62 C2, missed as expected): Evidence [W62 predictions and results](../../uplift/consolidated/iteration-58/w62-PAIRS.md); Verus [clause_combos](../../Verus_verification/models/clause_combos/NOTES.md) `theorem_group_iff_bound_text`, `theorem_group_and_distinct_disagree`. Findings: [Over a list the query holds, grouping merges 1 with true](../../Verus_verification/bugs_issues.md#bug-cyp-149).

### query.aggregation.arithmetic

- Expands: [Aggregate results](#query.aggregation)
- Sources: openCypher arithmetic; [`_numeric_static_type`](../../../iris_vector_graph/cypher/translator.py#L22046-L22118), [`_arith_operand_type`](../../../iris_vector_graph/cypher/translator.py#L22136-L22153); [`_int_expr_value`](../../../iris_vector_graph/_engine/query.py#L1219-L1240); [W59 results](../../uplift/consolidated/iteration-54/clauses-PAIRS.md)
- Verus: active: [`cypher_clauses.rs`](../../Verus_verification/models/cypher_clauses/cypher_clauses.rs) `column_type`, `answered`; departures `theorem_sum_of_property_sums_is_int_column`, `theorem_int_column_loses_any_half`, `theorem_probe_totals`; neighbors `theorem_float_operand_or_bare_sum_keeps_value`, `theorem_whole_total_unchanged` (controls `prop-default-unknown`, `float-literal-int`, `int-read-exact`)
- agent
- user-facing-behavior, data-integrity

Recovered in iteration 54 after the first observation; the frozen sums (AG4) were single aggregates and held.

Findings: [Arithmetic over two property aggregates answers a rounded integer: sum(n.v) + sum(n.f) of 3 and 3.5 answers 6](../../Verus_verification/bugs_issues.md#bug-cyp-137)

### query.optional

- Sources: openCypher TCK `Null1`-`2`, `Graph3`-`9` and `Aggregation*`; [ADMIN_GUIDE, OPTIONAL MATCH is SQL-only](../../../docs/ADMIN_GUIDE.md#L756-L769); [W59 predictions OM1-OM7 and results](../../uplift/consolidated/iteration-54/clauses-PAIRS.md)
- Verus: active: [`cypher_clauses.rs`](../../Verus_verification/models/cypher_clauses/cypher_clauses.rs) `placed_in_on`, `outer_guarded`, `as_built_opt`; departures `theorem_outer_guard_drops_row`, `theorem_outer_arith_or_refused` (conditional on the IRIS premise P-OUTER-ON); neighbor `theorem_opt_neighbors_follow_rule` (controls `opt-guard-in-on`, `range-guarded`, `iris-accepts-outer-on`, `opt-cond-in-where`). Path functions of an unbound path (iteration 56): `as_built_path_fn`, `length_from_pattern`; departure `theorem_unmatched_fixed_path_length_is_hops`, general `theorem_path_fn_departs_exactly_on_unmatched_fixed_length`, neighbor `theorem_bound_or_varlen_path_follows_rule` (controls `fixed-length-from-row`, `varlen-length-from-pattern`, `anchor-null-ignored`)
- agent
- user-facing-behavior

Recovered in iteration 54; every frozen prediction OM1-OM7 held on API-written, Cypher-written and named-graph data, and the native executor declined every shape, as documented. The WHERE placement was then read in the source and checked over seven condition shapes; two of them depart.

Iteration 56 (review 53-55 F2): the reviewer found that `length(p)` of an unbound path answers 1; reproduced on both engines, with `nodes(p)`, `relationships(p)`, a variable-length path and a null anchor as neighbors.

Findings: [A WHERE inside OPTIONAL MATCH that combines an earlier variable's property with arithmetic or OR fails the query with SQLCODE -94](../../Verus_verification/bugs_issues.md#bug-cyp-142); [A comparison on an earlier variable's property inside an OPTIONAL MATCH WHERE drops the rows of nodes that lack the property](../../Verus_verification/bugs_issues.md#bug-cyp-143); [length(p) of a path an OPTIONAL MATCH did not bind answers the pattern's length instead of null](../../Verus_verification/bugs_issues.md#bug-cyp-146) The inherited exceptions stay with their owners: [a leading grouped OPTIONAL MATCH's sum](../../Verus_verification/bugs_issues.md#bug-agg-001) and the two refused variable-length shapes ([conformance](#query.conformance)).

Iteration 58 (W62 C1, C3, D2): C1 and C3 held; D2 partial. Evidence: [W62 predictions and results](../../uplift/consolidated/iteration-58/w62-PAIRS.md); Verus [clause_combos](../../Verus_verification/models/clause_combos/NOTES.md) `theorem_null_row_count_zero`-family and `theorem_negation_polarity`, `theorem_new_alias_only_keeps_row`, `theorem_leading_grouped_sum_is_null`; [result_decoders](../../Verus_verification/models/result_decoders/NOTES.md) `theorem_null_row_every_decoder`, `theorem_optional_node_labels`. Findings: [An OPTIONAL MATCH node with no match answers labels '[]' and properties '[]'](../../Verus_verification/bugs_issues.md#bug-plt-135).

### query.with

- Sources: openCypher `WITH` and `CALL { }` importing `WITH` (TCK `With*`, `Call*`); [`translate_with_clause`](../../../iris_vector_graph/cypher/translator.py#L30857-L30872) (star branch); [`translate_subquery_call`](../../../iris_vector_graph/cypher/translator.py#L14697); [W62 predictions C5 and C8](../../uplift/consolidated/iteration-58/w62-PAIRS.md)
- Evidence: [iteration-58 C8 probes](../../uplift/consolidated/iteration-58/clauses/probe1.out); [iteration-59 G2 observation](../../uplift/consolidated/iteration-59/review-repairs/minor-observed-20261117T090528Z.json)
- agent
- user-facing-behavior

Recovered in iteration 59 (review 56-58 m4): the `WITH *` findings had been placed in [conformance](#query.conformance), which lists documented TCK deviations; `WITH *` is not one. No Verus claim: bug-cyp-150, -151 and -157 are probe-only; iteration 58 C5 (a MATCH-anchored import with its null-row aggregates) is modeled in [clause_combos](../../Verus_verification/models/clause_combos/NOTES.md).

Iteration 58 (W62 C5 held, C8 missed): [W62 predictions and results](../../uplift/consolidated/iteration-58/w62-PAIRS.md). Findings: [WITH * drops a relationship variable](../../Verus_verification/bugs_issues.md#bug-cyp-150); [WITH *, items does not parse](../../Verus_verification/bugs_issues.md#bug-cyp-151); [A CALL { } subquery importing an UNWIND variable fails](../../Verus_verification/bugs_issues.md#bug-cyp-157) (iteration 59, review 56-58 G2).

### query.paging

- Sources: openCypher TCK `ReturnSkipLimit1`-`3`, `WithSkipLimit*`; [`_resolve_pagination_value`](../../../iris_vector_graph/cypher/translator.py#L8095-L8134); [W59 predictions WS1-WS7 and results](../../uplift/consolidated/iteration-54/clauses-PAIRS.md)
- Verus: active: [`cypher_clauses.rs`](../../Verus_verification/models/cypher_clauses/cypher_clauses.rs) `as_built_page`, `rule_page`; departure `theorem_non_integer_parameter_used`; neighbor `theorem_integer_and_fraction_follow_rule` (controls `page-int-only`, `page-no-negative-check`, `page-no-fraction-check`)
- agent
- user-facing-behavior

Recovered in iteration 54; the frozen predictions WS1-WS7 held. The other parameter kinds were checked after the first observation.

Findings: [SKIP and LIMIT use a string, boolean or whole-float parameter as a count, and call a null parameter "not provided"](../../Verus_verification/bugs_issues.md#bug-cyp-139)

Iteration 58 (W62 D9, held; observed only): variable-length reads with `LIMIT`, `ORDER BY ... LIMIT`, `DESC` and `SKIP 1 LIMIT 2` answered the right rows at all four readers; these shapes run in SQL (`CY_VLP_PATHS` with `FETCH FIRST`), not through `_route_var_length` ([W62 predictions and results](../../uplift/consolidated/iteration-58/w62-PAIRS.md)).

### query.parameters

- design-verified
- uncertain
- Sources: openCypher parameters; [README conformance (drivers 5.4.0, 5.4.1)](../../../README.md), [`docs/dev/TCK.md`](../../../docs/dev/TCK.md), [`docs/dev/driver-drift.md` item 6](../../../docs/dev/driver-drift.md), [`uv.lock` (intersystems-irispython 5.3.2)](../../../uv.lock); [`_expr_slice`](../../../iris_vector_graph/cypher/translator.py#L23778-L23789)
- Verus: [bolt_answers.rs](../../Verus_verification/models/bolt_answers/bolt_answers.rs) `binds_json_table_marker` (provider premise P-DRV-JT), `theorem_unwind_param_depends_on_driver`, `params_order`, `slice_answer`, `theorem_param_slice_answers_empty` (controls `driver-532-binds`, `slice-markers-in-order`); [scope](../../Verus_verification/models/bolt_answers/NOTES.md)
- Evidence: [W60 predictions PA1-PA8 and results, both drivers](../../uplift/consolidated/iteration-55/pipeline-PAIRS.md)
- agent
- user-facing-behavior

Recovered in iteration 55. PA1, PA5, PA7 and PA8 held on both drivers and over Bolt; PA3 and PA4 missed (5.4.1 binds the marker; the slice answers []).

Open questions: [Which IRIS Python drivers must IVG's Cypher parameters work with?](../../Verus_verification/open_questions.md#query.parameters.drivers)

Findings: [With the driver 5.3.2 an UNWIND of a list parameter fails](../../Verus_verification/bugs_issues.md#bug-cyp-125); [A slice of a list parameter by parameters answers the empty list](../../Verus_verification/bugs_issues.md#bug-cyp-144)

State machines: [bolt answers](../../Verus_verification/models/bolt_answers/manifest.json)

### query.union

- Sources: openCypher TCK `Union1`-`3`; [`_tts_union_branches`](../../../iris_vector_graph/cypher/translator.py#L4632-L4714); [`_lone_label_count`](../../../iris_vector_graph/cypher/translator.py#L7413-L7459); [W59 predictions UN1-UN3 and results](../../uplift/consolidated/iteration-54/clauses-PAIRS.md)
- Verus: active: [`cypher_clauses.rs`](../../Verus_verification/models/cypher_clauses/cypher_clauses.rs) `union_dec`, `read`, `prepares`; departures `theorem_union_answers_marked_text`, `theorem_union_dedup_by_raw`, `theorem_label_count_branch_fails`; neighbors `theorem_single_query_decodes`, `theorem_all_bool_union_stays_bool`, `theorem_count_alone_and_other_branches_prepare`
- agent
- user-facing-behavior

Recovered in iteration 54: UN1 and UN3 held; UN2 held on the row count and missed on the value. The TCK's UNION scenarios return literals only, which the product decodes.

Findings: [A UNION answers stored property values as their storage text: 1 as "\x01N1", 2.5 as "\x01D2.5", a list as JSON text](../../Verus_verification/bugs_issues.md#bug-cyp-138); [A UNION whose branch is a whole-label count fails with SQLCODE -1](../../Verus_verification/bugs_issues.md#bug-cyp-140)

Iteration 58 (W62 C4, partial): a relationship in a UNION ALL branch is JSON text; observed only ([W62 predictions and results](../../uplift/consolidated/iteration-58/w62-PAIRS.md)).

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

Findings: [With the driver 5.3.2 an UNWIND of a list parameter fails "Invalid number of parameters"](../../Verus_verification/bugs_issues.md#bug-cyp-125) (a driver-conditional potential problem, iteration 48).

Audit reproduction: [F-0808](../../Verus_verification/bugs_issues.md#F-0808) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [FOREACH over a parameter list does not run per item](../../Verus_verification/bugs_issues.md#F-0808).

Audit reproduction: [F-C0841](../../Verus_verification/bugs_issues.md#F-C0841) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [Cypher range() with a step of 0 known only at run time answers [] instead of raising NumberOutOfRange](../../Verus_verification/bugs_issues.md#F-C0841).

Open questions: [Does a Cypher path value come back as JSON text or as a map, and may that depend on the driver or execution path?](../../Verus_verification/open_questions.md#q-cyp-004)

Iteration 59 (review 56-58 m4): the `WITH *` findings (bug-cyp-150, -151) moved to [WITH](#query.with); `WITH *` is not a documented deviation.

### query.values

- design-verified
- Sources: [`iris_vector_graph/prop_values.py`](../../../iris_vector_graph/prop_values.py#L1-L77) (the typed-values contract, 4.6.0 R308 and R310)
- Children: [relationship property text](#query.values.relationship_text), [conditions](#query.values.conditions), [equality in WHERE](#query.values.equality), [ordering in WHERE](#query.values.ordering), [sorting](#query.values.sorting), [nulls](#query.values.nulls), [string predicates](#query.values.string_predicates), [IN lists](#query.values.in_lists)
- Verus: [node_read](../../Verus_verification/models/node_read/NOTES.md), as-built numeric writer, D/N tag selection, S escape and numeric/text read distinctions. The scalar node-property projection reaches the final result in `theorem_sql_scalar_read_reaches_result`; JSON/J tags, N fractional/exponent parsing, nonfinite values, mixed expressions and the remaining SQL finishing pipeline are open modeling gaps. Numeric spelling/parse identity in `CY_TYPED` is an inspected provider premise, not a proved IRIS function.
- agent
- user-facing-behavior

New owner in the consolidated uplift. Node values and the typed-value marks are the playbook's `CYP-B17` family.

Audit reproduction: [F-0810](../../Verus_verification/bugs_issues.md#F-0810) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [SET n.p = null keeps the key](../../Verus_verification/bugs_issues.md#F-0810); [A boolean equality also matches stored integers 1 and 0, beyond the legacy strings the known issue names](../../Verus_verification/bugs_issues.md#bug-cyp-102); [A relationship property that is not a number orders as one against a number literal](../../Verus_verification/bugs_issues.md#bug-cyp-103); [A string predicate matches a node property stored as a number by its digits](../../Verus_verification/bugs_issues.md#bug-cyp-105).; [import_rdf drops a literal's datatype](../../Verus_verification/bugs_issues.md#bug-str-109)

State machines: [node read](../../Verus_verification/models/node_read/manifest.json)

Findings: [A UNION answers stored property values as their storage text: 1 as "\x01N1", 2.5 as "\x01D2.5", a list as JSON text](../../Verus_verification/bugs_issues.md#bug-cyp-138) (iteration 54: a UNION drops the type decoders this block's reads rely on)

Iteration 58 (W62 D1 missed; D3-D6 held): [W62 predictions and results](../../uplift/consolidated/iteration-58/w62-PAIRS.md); Verus [result_decoders](../../Verus_verification/models/result_decoders/NOTES.md) `theorem_typed_roundtrip`, `theorem_property_reads_roundtrip`, `theorem_strings_held_everywhere`, `theorem_with_coalesce_number_is_text`, `theorem_case_bool_is_text`, `theorem_case_container_is_text`, `theorem_case_number_by_driver`, `theorem_compare_is_boolean_or_null`. Findings: [A WITH column of coalesce() answers a stored number as its text](../../Verus_verification/bugs_issues.md#bug-cyp-155); [A CASE column answers a stored boolean as 'true'](../../Verus_verification/bugs_issues.md#bug-cyp-156).

Mechanism (moved from the governing text in iteration 59, review 56-58 m2): `CY_TYPED` decides the tag from the stored IRIS value, rather than the driver's column type; SQL result decoding and the node read API consume that tag, and the [batched node reader](graph-structure.g5.md#structure.node.read) also protects its structural keys. The translator decides per `RETURN` item which columns are decoded: a node property, a `WITH` variable bound to a bare node property, and a `RETURN` `coalesce()` of node properties and scalars read through `CY_TYPED`; a comparison is a boolean column; a list or map expression is a JSON column; any other column reaches the reader as the IRIS driver hands it, which is how [bug-cyp-155](../../Verus_verification/bugs_issues.md#bug-cyp-155) and [bug-cyp-156](../../Verus_verification/bugs_issues.md#bug-cyp-156) arise. Each typed read answers the value written, of every kind, under IRIS drivers 5.3.2 and 5.4.1 and at all four readers ([result_decoders](../../Verus_verification/models/result_decoders/NOTES.md) `theorem_typed_roundtrip`, `theorem_property_reads_roundtrip`).

### query.values.equality

- design-verified
- Sources: [boolean spellings](../../../iris_vector_graph/prop_values.py#L87-L88), [`_stored_bool_in`, `_stored_bool_comparison`](../../../iris_vector_graph/cypher/translator.py#L17851-L17870), [`_stored_number_test`, `_number_texts`, `_node_number_eq_sql`, `_number_eq_sql`](../../../iris_vector_graph/cypher/translator.py#L16231-L16310); [known issue: a boolean in an equality also matches a stored '1' or 'True'](../../../docs/KNOWN_ISSUES.md#L597-L612); [4.1.0 changelog: boolean equality still matches legacy rows](../../../CHANGELOG.md#L3862-L3865)
- Verus: [typed_equality.rs](../../Verus_verification/models/typed_equality/typed_equality.rs) `theorem_node_true_exact`, `theorem_node_where_return_disagree`, `theorem_node_bool_not_integer`, `theorem_node_integer_needs_stored_number`, `theorem_node_bool_agrees_outside_legacy`, `theorem_rel_bool_equals_integer`, `theorem_rel_integer_equals_true`, `theorem_rel_twin_spelling_equals_integer` and `theorem_string_integer_kind_asymmetry`; [scope](../../Verus_verification/models/typed_equality/NOTES.md)
- Evidence: [predictions and native observations](../../uplift/consolidated/iteration-16/typed-equality-PAIRS.md)
- Expands: [Values in results](#query.values)
- agent
- user-facing-behavior, data-integrity

As-built SQL-path behavior on IRIS 2026.1 for values written by `create_node` and `create_edge`. The native executor declines every non-string equality value ([`native_plan._value`](../../../iris_vector_graph/cypher/native_plan.py#L62-L74); [observation](../../uplift/consolidated/iteration-17/native-equality-PAIRS.md)), so these rules hold on both paths. Parameters, `IN` lists, `MERGE` patterns and Cypher-written values were not checked.

Findings: [A boolean equality also matches stored integers 1 and 0, beyond the legacy strings the known issue names](../../Verus_verification/bugs_issues.md#bug-cyp-102); [A string predicate matches a node property stored as a number by its digits](../../Verus_verification/bugs_issues.md#bug-cyp-105); [IN lists compare a property's text with each value's spelling, so they disagree with = on nodes and relationships](../../Verus_verification/bugs_issues.md#bug-cyp-106); [A simple CASE over a property or a row value takes a WHEN of another type when the text matches](../../Verus_verification/bugs_issues.md#bug-cyp-127)

State machines: [typed equality](../../Verus_verification/models/typed_equality/manifest.json)

Findings: [A grouping key and count(DISTINCT) treat a stored number and the string spelling it as one value, while RETURN DISTINCT keeps them apart](../../Verus_verification/bugs_issues.md#bug-cyp-135) (iteration 54: grouping compares text, unlike `=`)

Findings: [A string literal or string parameter equals a stored node number that it spells](../../Verus_verification/bugs_issues.md#bug-cyp-145) (iteration 55; [bolt_answers](../../Verus_verification/models/bolt_answers/bolt_answers.rs) `theorem_string_operand_matches_number`, `theorem_int_operands_and_string_values_follow_rule`; controls `string-compare-typed`, `int-param-raw`)

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

Findings: [ORDER BY over a list the query holds sorts booleans among the numbers](../../Verus_verification/bugs_issues.md#bug-cyp-158) (iteration 59, review 56-58 G3; observed only).

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

Findings: [Relationship property text with a trailing line break or non-ASCII digits is read back as a number](../../Verus_verification/bugs_issues.md#bug-cyp-101); [coalesce over a relationship property returns its stored text, and a boolean as '1'](../../Verus_verification/bugs_issues.md#bug-cyp-107); [A relationship SET from a function of its own property is refused with a message that says such a read is allowed](../../Verus_verification/bugs_issues.md#bug-cyp-132)

Audit reproduction: [bug-cyp-101](../../Verus_verification/bugs_issues.md#bug-cyp-101) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

State machines: [rel prop text](../../Verus_verification/models/rel_prop_text/manifest.json)

### query.values.conditions

- agent
- user-facing-behavior
- Expands: [Values in results](#query.values)
- Sources: openCypher TCK `Conditional1`, `Conditional2`; KNOWN_ISSUES "A boolean property of a map row reads as false in a `CASE WHEN`"; [`translator.py` `_expr_case`](../../../iris_vector_graph/cypher/translator.py#L22189-L22238), [`_translate_boolean_expression`](../../../iris_vector_graph/cypher/translator.py#L18651-L18716); [W55 predictions and results](../../uplift/consolidated/iteration-48/cypherexpr-PAIRS.md)
- Verus: active: [`cypher_exprs.rs`](../../Verus_verification/models/cypher_exprs/NOTES.md) `condition_sql`, `case_when`; neighbor `theorem_predicate_condition_follows_rule`; as-built departure `theorem_row_boolean_condition_fails`, conditional on the observed IRIS premise (controls `row-condition-compared`, `iris-accepts-scalar-condition`); simple CASE: `simple_case_takes`, as-built departure `theorem_simple_case_coerces_across_kinds` (control `case-kinds-compared`), neighbor `theorem_simple_case_same_kind_or_literal_follows_rule` (iteration 50)

Recovered in iteration 48. Frozen predictions C1, C2 and the stored half of C4 held; the `UNWIND` half of C4 missed.

Iteration 50 (review 47-49 item 7): the opening sentence claimed the openCypher answer for simple CASE over stored and run-time values; corrected, with the departure as a bullet.

Findings: [A boolean known only at run time cannot be a CASE WHEN or WHERE condition](../../Verus_verification/bugs_issues.md#bug-cyp-118); [A simple CASE over a property or a row value takes a WHEN of another type when the text matches](../../Verus_verification/bugs_issues.md#bug-cyp-127)

### query.functions

- Sources: openCypher TCK (`List*`, `String*`, `Map*`); [query.conformance](#query.conformance); [`translator.py` `_expr_subscript`](../../../iris_vector_graph/cypher/translator.py#L23509-L23656), [`_scalar_string`](../../../iris_vector_graph/cypher/translator.py#L24475-L24513), [`_expr_fn_list_ops`](../../../iris_vector_graph/cypher/translator.py#L29102-L29122); [`schema.py` Cypher SQL functions](../../../iris_vector_graph/schema.py#L2179-L2380); [`CypherFn.cls`](../../../iris_src/src/Graph/KG/CypherFn.cls); [W54 predictions and results](../../uplift/consolidated/iteration-47/cypherfn-PAIRS.md)
- Verus: [`cypher_fns.rs`](../../Verus_verification/models/cypher_fns/NOTES.md) (the run-time distinctions in the children); the rest observed only
- agent
- user-facing-behavior

Recovered in iteration 47. Frozen predictions L3, L5, L6 (relationship and map), L8 held on the fixture; `keys(n)` of a node written by `create_node` also lists `id` (not assessed). The native executor declined every function shape probed.

Findings: [head() of a number fails with an error that does not name TypeError](../../Verus_verification/bugs_issues.md#bug-cyp-116)

### query.functions.list_index

- Sources: openCypher TCK `List1`; CHANGELOG 4.6.0 R267; [`translator.py` `_expr_subscript`](../../../iris_vector_graph/cypher/translator.py#L23509-L23656), [`_is_row_list_elem`](../../../iris_vector_graph/cypher/translator.py#L7681-L7732); [`schema.py` Cypher SQL functions](../../../iris_vector_graph/schema.py#L2179-L2380); [`CypherFn.cls`](../../../iris_src/src/Graph/KG/CypherFn.cls); [W54 predictions and results](../../uplift/consolidated/iteration-47/cypherfn-PAIRS.md)
- Expands: [Built-in functions](#query.functions)
- Verus: active: [`cypher_fns.rs`](../../Verus_verification/models/cypher_fns/NOTES.md) `rule_index_opt`, `translated_index` (by list source and index kind), `translated_type`, `json_arrayget_opt`, `json_value_index`, `cy_list_elem`, `ivglistget`; neighbors `theorem_with_literal_row_index_follows_rule`, `theorem_literal_index_follows_rule`, `theorem_row_nonnegative_index_follows_rule`, `theorem_ivglistget_is_rule`; as-built departures `theorem_row_negative_index_fails`, `theorem_param_negative_index_fails` (control `row-index-through-ivglistget` is the repair) and `theorem_null_index_reads_first_element` (control `null-index-is-null`)
- agent
- user-facing-behavior

Iteration 50 (review 47-49 items 2 and 6): narrowed to lists from a property and parameter indexes; the null index added.

Findings: [A list index known only at run time fails the query when it is negative, for a list read from a property or indexed by a parameter](../../Verus_verification/bugs_issues.md#bug-cyp-111); [A null list index known only at run time answers the list's first element](../../Verus_verification/bugs_issues.md#bug-cyp-126)

Simplification: [One run-time path for list positions, whatever the index or bound's syntax](../../Verus_verification/design_simplification.md#simp-cyp-101)

### query.functions.reverse

- Sources: openCypher; CHANGELOG 4.7.0 (row 20b); [`translator.py` `_scalar_string` (reverse)](../../../iris_vector_graph/cypher/translator.py#L24495-L24513), [`_container_kind`](../../../iris_vector_graph/cypher/translator.py#L21911-L21963); [`schema.py` Cypher SQL functions](../../../iris_vector_graph/schema.py#L2179-L2380); [`CypherFn.cls`](../../../iris_src/src/Graph/KG/CypherFn.cls); [W54 predictions and results](../../uplift/consolidated/iteration-47/cypherfn-PAIRS.md)
- Expands: [Built-in functions](#query.functions)
- Verus: active: [`cypher_fns.rs`](../../Verus_verification/models/cypher_fns/NOTES.md) `uses_cy_reverse`, `reverse_result` (argument kind and whether the column is known to be a list); neighbor `theorem_reverse_neighbors`; as-built departures `theorem_stored_list_reversed_as_text` (control `property-to-cy-reverse`) and `theorem_unknown_list_variable_answered_as_text` (control `reverse-column-typed`)
- agent
- user-facing-behavior

Iteration 50 (review 47-49 item 3): widened to slices, subscripts and `coalesce()`, and the `WITH` column answered as text.

Findings: [reverse() of a list held in a property, a slice, a subscript or a coalesce reverses its JSON text](../../Verus_verification/bugs_issues.md#bug-cyp-112)

### query.functions.dynamic_access

- Sources: openCypher (`Map*`, dynamic property access); [`translator.py` `_expr_subscript`](../../../iris_vector_graph/cypher/translator.py#L23509-L23656); [`schema.py` Cypher SQL functions](../../../iris_vector_graph/schema.py#L2179-L2380); [`CypherFn.cls`](../../../iris_src/src/Graph/KG/CypherFn.cls); [W54 predictions and results](../../uplift/consolidated/iteration-47/cypherfn-PAIRS.md)
- Expands: [Built-in functions](#query.functions)
- Verus: active: [`cypher_fns.rs`](../../Verus_verification/models/cypher_fns/NOTES.md) `node_key_read`; neighbor `theorem_param_key_follows_rule`; as-built departures `theorem_row_key_reads_variable_name` (control `row-key-by-value`) and `theorem_with_column_key_fails` (control `with-key-by-value`, iteration 50). The map value types (second bullet) are probe only.
- agent
- user-facing-behavior

Findings: [n[k] with a key from UNWIND reads the property named "k"](../../Verus_verification/bugs_issues.md#bug-cyp-113); [A map value read by a key answers numbers and booleans as text](../../Verus_verification/bugs_issues.md#bug-cyp-115)

### query.functions.range

- Sources: openCypher TCK `List11`; [`translator.py` `_expr_fn_list_ops` (range)](../../../iris_vector_graph/cypher/translator.py#L29114-L29122); [`schema.py` Cypher SQL functions](../../../iris_vector_graph/schema.py#L2179-L2380); [`CypherFn.cls`](../../../iris_src/src/Graph/KG/CypherFn.cls); [W54 predictions and results](../../uplift/consolidated/iteration-47/cypherfn-PAIRS.md)
- Expands: [Built-in functions](#query.functions)
- Verus: active: [`cypher_fns.rs`](../../Verus_verification/models/cypher_fns/NOTES.md) `ivgrange`, `rule_range`; neighbor `theorem_nonzero_step_follows_rule`; as-built departure `theorem_runtime_zero_step_empty` (control `range-zero-raises`)
- agent
- user-facing-behavior

The fractional step (second bullet) is observed only; the model's range covers integer steps.

Findings: [Cypher range() with a step of 0 known only at run time answers [] instead of raising NumberOutOfRange](../../Verus_verification/bugs_issues.md#F-C0841); [range() with a step known only at run time accepts a fractional step](../../Verus_verification/bugs_issues.md#bug-cyp-131)

### query.functions.percentile

- Sources: openCypher TCK `Aggregation6`; CHANGELOG (`IVG.Percentile`, R269); [W54 predictions and results](../../uplift/consolidated/iteration-47/cypherfn-PAIRS.md)
- Expands: [Built-in functions](#query.functions)
- agent
- user-facing-behavior
- design-verified

Frozen predictions L9 and L10 held (nearest rank 20, interpolation 25.0, quartiles 10, 30 and 17.5, empty null, nulls left out, NumberOutOfRange for 1.5 and -1). Iteration 56 (review 53-55 minors) registered the result type ([bug-cyp-147](../../Verus_verification/bugs_issues.md#bug-cyp-147)) and the p argument's kinds ([bug-cyp-148](../../Verus_verification/bugs_issues.md#bug-cyp-148)); whether a null p should fail or answer null is not stated by openCypher, and both readings reject today's answers. openCypher says only "nearest". Iteration 53 corrected the iteration-47 reading that "the rounding follows Neo4j": the quartiles and the median give the same answer under rounding down and under nearest rank, but p 0.6 and 0.9 do not ([bug-cyp-134](../../Verus_verification/bugs_issues.md#bug-cyp-134)).

- Formal: [`theorem_disc_never_above_rule`, `theorem_disc_top_percentile_misses_max`, `theorem_disc_rounds_down_p90`, `theorem_disc_agrees_at_ends_and_median`, `theorem_cont_follows_rule`, `theorem_empty_and_out_of_range`](../../Verus_verification/models/percentile/percentile.rs); iteration 56: answer type `theorem_disc_over_ints_answers_float`, neighbor `theorem_float_and_cont_kinds_follow_rule` (control `disc-keeps-input-kind`); the p argument `theorem_non_number_p_not_refused`, general `theorem_p_departs_exactly_on_non_numbers` (controls `null-param-refused`, `literal-null-refused`)

State machines: [percentile](../../Verus_verification/models/percentile/manifest.json)

### query.functions.random

- Sources: openCypher; [`translator.py` `_scalar_numeric_and_datetime` (rand, randomUUID)](../../../iris_vector_graph/cypher/translator.py#L26919-L26924); [`schema.py` Cypher SQL functions](../../../iris_vector_graph/schema.py#L2179-L2380); [`CypherFn.cls`](../../../iris_src/src/Graph/KG/CypherFn.cls); [W54 predictions and results](../../uplift/consolidated/iteration-47/cypherfn-PAIRS.md)
- Expands: [Built-in functions](#query.functions)
- Verus: premise only: [`cypher_fns.rs`](../../Verus_verification/models/cypher_fns/NOTES.md) `value_on_row`, `theorem_rows_share_one_value` record the observed IRIS premise that a call with no row argument is evaluated once per statement (control `per-row-evaluation` flips the premise); the translator's emitter is a locator, not a modeled decision (iteration 50, review 47-49 item 4)
- agent
- user-facing-behavior

Findings: [randomUUID() and rand() give one value for every row of a query](../../Verus_verification/bugs_issues.md#bug-cyp-114)

### query.functions.sql_helpers

- Sources: [`SqlProcs.cls` CypherFn forwarders](../../../iris_src/src/Graph/KG/SqlProcs.cls#L15-L105); [`CypherFn.cls`](../../../iris_src/src/Graph/KG/CypherFn.cls); the translator's emitted names (`CypherFn_IVGRANGE`, `CypherFn_IVGTYPEERROR`, `CypherFn_IVGJSONSET`, `CypherFn_IVGJSONREMOVE` only)
- Expands: [Built-in functions](#query.functions)
- Verus: [`cypher_fns.rs`](../../Verus_verification/models/cypher_fns/NOTES.md) `ivglistget`, `ivgrange` (the two bodies with a formal transcription)
- agent
- architecture-decision

Recovered in iteration 47 from the translator's emitted SQL names. The other 13 `CypherFn` bodies are reachable from SQL only; their SQL behavior was not probed except `CypherFn_IVGLISTGET` and `CypherFn_IVGRANGE`.

### query.functions.slice

- Sources: openCypher TCK `List2`; [`translator.py` `_expr_slice`](../../../iris_vector_graph/cypher/translator.py#L23679-L23791); [`parser.py` `parse_primary_expression`](../../../iris_vector_graph/cypher/parser.py#L1621-L1641); [W55 predictions and results](../../uplift/consolidated/iteration-48/cypherexpr-PAIRS.md)
- Expands: [Built-in functions](#query.functions)
- Verus: active: [`cypher_exprs.rs`](../../Verus_verification/models/cypher_exprs/NOTES.md) `translated_bound`, `as_built_slice`, `rule_slice`, `parses`; neighbors `theorem_literal_slice_follows_rule`, `theorem_row_nonnegative_slice_follows_rule`, `theorem_other_lower_bounds_parse`; as-built departures `theorem_row_negative_slice_departs` (control `row-slice-wrapped` is the repair), `theorem_identifier_lower_bound_refused` (control `identifier-lookahead`; decided from the tokens since iteration 50) and `theorem_null_list_slice_is_empty` (control `null-list-guard`)
- agent
- user-facing-behavior

Recovered in iteration 48. Frozen predictions L2, L3, L4 held; L1 missed for negative run-time bounds.

Iteration 50: the null list (`theorem_null_list_slice_is_empty`, control `null-list-guard`) and the parameter-list slice (driver premise, not modeled).

Findings: [A negative list-slice bound known only at run time counts as 0](../../Verus_verification/bugs_issues.md#bug-cyp-117); [A slice whose lower bound is a variable name does not parse](../../Verus_verification/bugs_issues.md#bug-cyp-122); [Slicing a null list answers the empty list](../../Verus_verification/bugs_issues.md#bug-cyp-129); [With the driver 5.3.2 an UNWIND of a list parameter fails](../../Verus_verification/bugs_issues.md#bug-cyp-125)

Simplification: [One run-time path for list positions, whatever the index or bound's syntax](../../Verus_verification/design_simplification.md#simp-cyp-101)

### query.functions.strings

- Sources: openCypher TCK `String1`-`String14`, `TypeConversion2`-`4`; the Cypher 9 function reference (negative arguments); [`translator.py` `_scalar_string`](../../../iris_vector_graph/cypher/translator.py#L24475-L24494), [the SQL name of `trim`](../../../iris_vector_graph/cypher/translator.py#L29537), [the CREATE folder's `trim`](../../../iris_vector_graph/cypher/translator.py#L9456); [W55 predictions and results](../../uplift/consolidated/iteration-48/cypherexpr-PAIRS.md)
- Expands: [Built-in functions](#query.functions)
- Verus: active for `substring`'s start: [`cypher_exprs.rs`](../../Verus_verification/models/cypher_exprs/NOTES.md) `as_built_substring`, `rule_substring`; neighbor `theorem_inside_substring_follows_rule`; as-built departure `theorem_negative_start_answers_prefix` (control `substring-checks-start`). The zero-length null (second bullet), the trim whitespace (third bullet), `left`/`right` and the conversions are observed only.
- agent
- user-facing-behavior

Recovered in iteration 48. Frozen predictions S1, S4, S5, S6 held; S2 (negative start) and S3 (length 0) were partial, for literal and run-time arguments alike.

Iteration 50 (review 47-49 m4): the opening claim that the trim functions give the openCypher answer is qualified by the trim bullet.

Findings: [A negative substring start answers leading characters](../../Verus_verification/bugs_issues.md#bug-cyp-123); [A zero-length left, right or substring answers null](../../Verus_verification/bugs_issues.md#bug-cyp-124); [trim() keeps tabs and line breaks in a query's result, while a node CREATE removes them](../../Verus_verification/bugs_issues.md#bug-cyp-130)

### query.functions.coalesce

- Sources: openCypher TCK `Conditional1`; CHANGELOG 4.6.0 R259; [`translator.py` `_is_typed_coalesce`](../../../iris_vector_graph/cypher/translator.py#L7620-L7642), [`_scalar_coalesce`](../../../iris_vector_graph/cypher/translator.py#L24455-L24472); [W55 predictions and results](../../uplift/consolidated/iteration-48/cypherexpr-PAIRS.md)
- Expands: [Built-in functions](#query.functions)
- Verus: active: [`cypher_exprs.rs`](../../Verus_verification/models/cypher_exprs/NOTES.md) `typed_coalesce`, `coalesce_number`; neighbor `theorem_node_coalesce_keeps_type`; as-built departure `theorem_row_coalesce_number_as_text` (control `coalesce-always-typed`)
- agent
- user-facing-behavior

Recovered in iteration 48. Frozen prediction C3 held for stored values and missed for its literal neighbor.

Findings: [coalesce over row values, literals or parameters answers numbers as text](../../Verus_verification/bugs_issues.md#bug-cyp-121); inherited [coalesce over a relationship property returns its stored text](../../Verus_verification/bugs_issues.md#bug-cyp-107)

### query.functions.path_elements

- Expands: [Built-in functions](#query.functions)
- Sources: openCypher TCK `Graph*`, `Path*`; [KNOWN_ISSUES, nodes(p)](../../../docs/KNOWN_ISSUES.md#L421-L433); [`_expr_fn_node_funcs`](../../../iris_vector_graph/cypher/translator.py#L28964-L29023); [W59 predictions PA1-PA7, PC1-PC3 and results](../../uplift/consolidated/iteration-54/clauses-PAIRS.md)
- Verus: active: [`cypher_clauses.rs`](../../Verus_verification/models/cypher_clauses/cypher_clauses.rs) `reads_existing_column`; departure `theorem_path_element_endpoints_fail`; neighbor `theorem_type_and_matched_endpoints_work` (controls `endpoint-reads-json`, `type-reads-alias`)
- agent
- user-facing-behavior

Recovered in iteration 54. PA1-PA4, PA6, PA7 and PC1, PC3 held on API-written and named-graph edges; PA5 and PC2 missed because the prediction overlooked that `create_edge` deduplicates in multigraph mode too, which [structure.multigraph](graph-structure.g5.md#structure.multigraph) already states.

Findings: [startNode() and endNode() of a relationship taken from relationships(p) fail with SQLCODE -29](../../Verus_verification/bugs_issues.md#bug-cyp-141)
