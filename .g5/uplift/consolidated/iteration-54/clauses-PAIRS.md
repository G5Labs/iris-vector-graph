# W59: Cypher clauses over API-written data, default (non-multigraph) mode and parameters (frozen predictions)

Frozen 2026-11-17, **before** reading how the translator handles `OPTIONAL MATCH`, aggregation and grouping, `WITH`,
`DISTINCT`, `ORDER BY`, `SKIP`/`LIMIT`, `UNION`, `EXISTS`, pattern comprehension, path functions, `DELETE`, `DETACH
DELETE` or `REMOVE`, and before reading the native planner's acceptance of those shapes. Sources used: openCypher (the
public TCK features `ReturnSkipLimit1`-`3`, `WithSkipLimit*`, `Union1`-`3`, `Return6`, `Aggregation*`, `Null1`-`2`,
`Graph3`-`9`, read from a vendored copy since the pin's submodule is empty; CIP2016-06-14 for grouping equivalence),
the owners [query.aggregation](../../../ontology/features/cypher.g5.md#query.aggregation),
[query.conformance](../../../ontology/features/cypher.g5.md#query.conformance),
[query.values](../../../ontology/features/cypher.g5.md#query.values) and its children,
[query.writes](../../../ontology/features/cypher.g5.md#query.writes),
[structure.edge.single](../../../ontology/features/graph-structure.g5.md#structure.edge.single),
[structure.multigraph.count](../../../ontology/features/graph-structure.g5.md#structure.multigraph.count),
[structure.node.delete](../../../ontology/features/graph-structure.g5.md#structure.node.delete), and the docs
`docs/KNOWN_ISSUES.md` (multigraph `CREATE`, `nodes(p)` of a variable-length path, `OPTIONAL MATCH` variable-length
shapes, booleans stored as text), `docs/USER_GUIDE.md` §§ "Where a query runs", DELETE refusal (line 334), parallel
edges (line 470), `docs/ADMIN_GUIDE.md` (`OPTIONAL MATCH` is SQL-only) and `docs/dev/TCK.md` (the TCK runs with
multigraph on, Cypher-written data, driver 5.4.x).

Why these conditions: the TCK writes every fixture through Cypher literals, in multigraph mode, with driver 5.4.x.
The fixture here writes through the Python API (`create_node`, `create_edge`, `bulk_create_edges`, a named graph and a
multigraph graph) in the default single-edge mode, with driver 5.3.2, and passes `SKIP`/`LIMIT` and filter values as
parameters. Each pair holds the clause fixed and varies one of: API- vs Cypher-written data, literal vs parameter,
match vs no match, default vs named graph, single-edge vs multigraph.

Expected outcome = openCypher unless an owner block or a known issue states a deviation; where one does, the row says
so. Readers: the `execute_cypher` result row on the SQL path (engine with `native_cypher=False`), and the native
executor's own answer (`_try_native`) wherever it accepts the shape; for writes, a later `MATCH`, `get_node()` and the
edge count. Native prediction: it declines every `OPTIONAL MATCH`, `UNION`, `EXISTS`, comprehension, path function
and write (ADMIN_GUIDE, USER_GUIDE "Where a query runs"), and where it answers it gives the SQL answer
([query.native.equal-answers](../../../ontology/features/cypher.g5.md#query.native.equal-answers)).

Fixture (fresh tag per run, labels and types suffixed with it). API-written default graph: `a1 {name: 'a1', v: 1, s:
'1', f: 2.5, b: true, l: [1, 2]}`, `a2 {name: 'a2', v: 2, s: 'x', f: 1.0, l: [3]}`, `a3 {name: 'a3'}`, `d1 {name:
'dup'}`, `d2 {name: 'dup'}`; edges `a1-K->a2 {w: 1}`, `a1-K->a3 (weight 2.5)`, `a2-K->a3`. A Cypher-written twin with
the same values (label `C`, type `KC`). Named graph `g`: `gx-K->gy`. Multigraph graph `m`: two `create_edge(mx, K, my)`.

| ID | Case | Neighbor | Predicted |
|---|---|---|---|
| OM1 | `MATCH (a:A {name: 'a2'}) OPTIONAL MATCH (a)-[r:K]->(b) RETURN a.name, b.name, r IS NULL`… with `a3` (no outgoing edge) | the same from `a1` (two edges) | `a3`: one row `['a3', null, true]`; `a1`: two rows (`a2`, `a3`, false); Cypher-written twin the same |
| OM2 | `OPTIONAL MATCH (a)-[:NOSUCH]->(b)` from `a1` (type never written) | `OPTIONAL MATCH (a)-[:K]->(b:NoSuchLabel)` | one row with `b` null in both; never an error, never zero rows |
| OM3 | `MATCH (a:A) OPTIONAL MATCH (a)-[:K]->(b) WHERE b.v = 2 RETURN a.name, b.name` (WHERE inside) | the same with `WITH a, b WHERE b.v = 2` after it | inside: one row per `a` (5 rows), `b` set only for `a1` → `a2`; after: only `['a1', 'a2']` |
| OM4 | after `OPTIONAL MATCH` with no match: `RETURN b.v + 1, coalesce(b.v, 0), b IS NULL, b.name STARTS WITH 'x'` | the matched row's same projections | `null, 0, true, null`; matched (`a1` → `a2`): `3, 2, false, false` |
| OM5 | `MATCH (a:A) OPTIONAL MATCH (a)-[:K]->(b) RETURN a.name, count(b), count(*), collect(b.name)` | `sum(b.v)`, `avg(b.v)` per `a` | `a1`: 2, 2, both names; `a3`, `d1`, `d2`: 0, 1, `[]`; sum 0 and avg null where none matched ([query.aggregation](../../../ontology/features/cypher.g5.md#query.aggregation); bug-agg-001 owns only a *leading* grouped OPTIONAL) |
| OM6 | `OPTIONAL MATCH (n:NoSuchLabel) RETURN n` (leading, no match) | `OPTIONAL MATCH (n:NoSuchLabel) RETURN count(n)` | one row `[null]`; `[0]` |
| OM7 | `MATCH (a {id: a1}) OPTIONAL MATCH (a)-[:K]->(b) OPTIONAL MATCH (b)-[:K]->(c) RETURN b.name, c.name` | the same under `USE GRAPH g` from `gx` (named-graph API edges) | `a2 → a3` and `a3 → null`; named graph `gy` with `c` null |
| AG1 | `MATCH (n:G) RETURN n.k, count(*)` over API-written `k` = 1, 1, `'1'`, 1.5 | the Cypher-written twin | three groups: 1 (count 2, integer), `'1'` (1, string), 1.5 (1); same for the twin |
| AG2 | `count(DISTINCT n.k)` over API-written 1, `'1'`, true, `'true'` | over `UNWIND [1, '1', true, 'true']` | openCypher 4. Docs: a string that spells a boolean is stored as the boolean's text, so the stored pair reads as one value: **3** for API data; 4 for the `UNWIND` |
| AG3 | `collect(n.l)` over API-written lists `[1, 2]`, `[3]` | `collect(n.m)` over API-written maps `{k: 1}` | `[[1, 2], [3]]` as lists of integers; `[{k: 1}]` as a map, not text ([query.aggregation](../../../ontology/features/cypher.g5.md#query.aggregation)) |
| AG4 | `sum(n.v)`, `avg(n.v)` over API-written 1, 2 (integers) | over 1, 2 and 2.5 (a float) | 3 (integer), 1.5; 5.5 (float), 1.8333… (float) ([query.aggregation](../../../ontology/features/cypher.g5.md#query.aggregation)) |
| AG5 | `sum(n.s)` over API-written strings `'1'`, `'2'` | `sum(x)` over `UNWIND ['1', '2']` | openCypher: an error (sum of strings). Docs ([query.conformance](../../../ontology/features/cypher.g5.md#query.conformance): arithmetic coerces numeric-looking text): 3 for both; not predicted with confidence which |
| AG6 | `MATCH (n:NoSuch) RETURN count(n), sum(n.v), avg(n.v), collect(n.v)` | the same with a grouping key `n.k` | one row `[0, 0, null, []]`; no rows |
| AG7 | `sum(r.w)` over API-written relationship numbers `w` 1 and 2.5 | over Cypher-written relationship `w` 1 and 2.5 | 3.5 both ([relationship text](../../../ontology/features/cypher.g5.md#query.values.relationship_text) decodes the text) |
| WS1 | `MATCH (n:A) RETURN n.name ORDER BY n.name SKIP $s LIMIT $l` with `s` 1, `l` 2 | `SKIP 1 LIMIT 2` | the same two rows (`a2`, `a3`) |
| WS2 | `LIMIT $l` with `l` = -1 | `LIMIT -1` written in the query | both refused (TCK ReturnSkipLimit2 [10], [12]: NegativeIntegerArgument); nothing returned |
| WS3 | `SKIP $s` with `s` = -1, and `LIMIT $l` with `l` = 1.5 | `SKIP -1`, `LIMIT 1.5` | refused (NegativeIntegerArgument, InvalidArgumentType), parameter and literal alike |
| WS4 | `LIMIT $l` with `l` = 0 | `LIMIT 0` | no rows, both |
| WS5 | `MATCH (n:A) WHERE n.name = 'dup' RETURN DISTINCT n` (two nodes, one name) | `RETURN DISTINCT n.name` | two rows; one row |
| WS6 | `MATCH (n:A) WITH n.name AS nm, n.v AS v WHERE v IS NOT NULL RETURN nm ORDER BY v DESC` (order by a `WITH` column not returned) | `RETURN n.name AS nm ORDER BY nm DESC` (a projected alias) | `a2`, `a1`; names in descending order |
| WS7 | `MATCH (n:A) WITH n ORDER BY n.v DESC LIMIT 1 RETURN n.name` | `WITH n ORDER BY n.v DESC LIMIT $l` with `l` 1 | a node with no `v` (`a3`, `d1` or `d2`) for both: null sorts first with `DESC` ([sorting](../../../ontology/features/cypher.g5.md#query.values.sorting)); with `WHERE n.v IS NOT NULL` first, `a2` for both |
| UN1 | `RETURN 1 AS x UNION RETURN 1 AS x` | `UNION ALL` | one row; two rows |
| UN2 | `MATCH (n:A {name: 'a1'}) RETURN n.v AS x UNION MATCH (m:A {name: 'a2'}) RETURN m.v - 1 AS x` (API integers 1 and 1) | the same with `n.s` (`'1'`, a string) in the first branch | one row `1`; two rows (`'1'` and 1 differ) |
| UN3 | `RETURN 1 AS x UNION RETURN 2 AS y` | `RETURN 1 AS x UNION RETURN 1 AS x UNION ALL RETURN 1 AS x` | refused (DifferentColumnsInUnion); refused (InvalidClauseComposition) |
| EX1 | `MATCH (n:A) WHERE EXISTS { (n)-[:K]->() } RETURN n.name` over API edges | `WHERE (n)-[:K]->()` (pattern predicate) and `NOT EXISTS {…}` | `a1`, `a2`; the same; `a3`, `d1`, `d2` |
| EX2 | `USE GRAPH g MATCH (n) WHERE EXISTS { (n)-[:K]->() } RETURN n.id` (named-graph API edge) | without `USE GRAPH` over the same | `gx`; `gx` plus default-graph `a1`, `a2` if the label is not given |
| PC1 | `MATCH (n:A {name: 'a1'}) RETURN [(n)-[:K]->(m) \| m.name]` over API edges | from `a3` (no edge) | `['a2', 'a3']` in any order; `[]` |
| PC2 | `size([(x)-[:K]->(y) \| y])` from multigraph `mx` (two parallel API edges) | from a default-graph pair after `create_edge` twice | 2 ([structure.multigraph.count](../../../ontology/features/graph-structure.g5.md#structure.multigraph.count)); 1 ([structure.edge.single](../../../ontology/features/graph-structure.g5.md#structure.edge.single)) |
| PC3 | `[x IN n.l WHERE x > 1 \| x * 10]` over API-written `[1, 2]` | the Cypher-written twin | `[20]` (integer) both |
| PA1 | `MATCH p = (a {name: 'a1'})-[r:K]->(b {name: 'a2'}) RETURN length(p), type(r), startNode(r).name, endNode(r).name, size(nodes(p)), size(relationships(p))` over the API edge | the Cypher-written twin | `1, 'K…', 'a1', 'a2', 2, 1` both |
| PA2 | `MATCH (b {name: 'a2'})<-[r:K]-(a) RETURN startNode(r).name, endNode(r).name` | undirected `(b)-[r:K]-(x)` from `a2` | `a1`, `a2` (start is the source whatever the pattern's direction); `a1→a2` and `a2→a3` rows give starts `a1`, `a2` |
| PA3 | `USE GRAPH g MATCH p = (x)-[r]->(y) RETURN type(r), startNode(r).id, length(p)` | without `USE GRAPH` | `K…, gx, 1`; the same row among the default graph's |
| PA4 | `MATCH p = (a {name: 'a1'})-[:K*1..2]->(c) RETURN length(p), [x IN nodes(p) \| x.name]` | `relationships(p)` types | lengths 1, 1, 2 (`a2`, `a3`, `a2→a3`); names by element; KNOWN_ISSUES: `nodes(p)` itself answers ids, the comprehension answers names |
| PA5 | `MATCH (x {id: mx})-[r:K]->(y) RETURN count(r)` over two multigraph API edges | after `create_edge` twice in the default single-edge graph (second call reports False) | 2; 1 |
| PA6 | `bulk_create_edges` with one triple twice in one batch (default graph), then `count(r)` | a second `bulk_create_edges` of a present triple | 1; 1 (docstring: "an edge already present is not duplicated") |
| PA7 | Cypher `MATCH (a), (b) CREATE (a)-[:K]->(b)` over an existing API-written `a1→a2` in the default graph | the same in multigraph graph `m` | adds nothing, no error (KNOWN_ISSUES first entry); adds a second edge |
| DL1 | `MATCH (n {id: a1}) DELETE n` (API node with API edges) | the same on `d1` (no edges) | refused (`GraphWriteError`, ConstraintVerificationFailed), nothing deleted (USER_GUIDE line 334); `d1` deleted |
| DL2 | `MATCH (n {id: a3}) DELETE n` (only incoming API edges) | `DETACH DELETE` of `a3` | refused; deleted with its edges: `a1`'s and `a2`'s `-[:K]->()` reads drop it, `get_node` None, degree of `a1` falls |
| DL3 | `MATCH ({id: a1})-[r:K]->({id: a2}) DELETE r` | the same, then `create_edge(a1, K, a2)` | edge gone, endpoints remain; `create_edge` reports True (a new edge) |
| DL4 | `MATCH (n {id: a1}) REMOVE n.f` (API-written float) | `REMOVE n:A` | `keys(n)` and `get_node` lack `f`; the label is gone from `labels(n)` and `get_node` |
| DL5 | `USE GRAPH g MATCH ()-[r:K]->() DELETE r` | without `USE GRAPH` (`MATCH ({id: gx})-[r]->() DELETE r` with the same id `gx` also in the default graph) | only `g`'s edge goes; each graph's matched edge goes, others stay |
| DL6 | `MATCH ({id: mx})-[r:K]->() WITH r LIMIT 1 DELETE r` (multigraph, two parallel edges) | `DETACH DELETE` of `mx` | one edge remains (`count(r)` 1); none remain |

Not predicted with confidence: the error class names IVG gives for refused `SKIP`/`LIMIT` values and `UNION` columns
(the TCK passes on them, so some refusal is expected), whether `AG5` coerces or refuses, and whether 1 and 1.0 group
together (left out of AG1 for that reason).

## Result (iteration 54; [observation](clauses-observed-20261117T053516Z.json), [follow-up](clauses-observed2-20261117T053826Z.json) after the first observation and before the deciding source was read, [binding](../../../Verus_verification/results/cypher_clauses/20261117T060402Z-binding/receipt.json) after it)

Readers: the SQL path (`native_cypher=False`) for every row; the native executor (`_try_native` on an engine with it on,
used from the follow-up) accepted only plain `MATCH ... RETURN` shapes, `DISTINCT`/`count` over one hop, literal
`ORDER BY ... LIMIT` and the grouped reads of AG1, and declined every `OPTIONAL MATCH`, `UNION`, `EXISTS`,
comprehension, path function, parameter `LIMIT` and write. Where it answered, it agreed with the SQL path except on
grouping (bug-cyp-136).

**42 rows: 35 held, 3 partial, 4 missed.**

| ID | Held? | Observed |
|---|---|---|
| OM1-OM7 | held (7) | one null row for `a3`, two rows for `a1`; missing type or label gives the null row; WHERE inside keeps 5 rows, after keeps 1; `null, 0, true, null` vs `3, 2, false, false`; `count(b)` 0 with `count(*)` 1, `sum` 0, `avg` null; leading OPTIONAL gives `[null]` and `[0]`; the chained and named-graph forms as predicted; the Cypher twin the same |
| AG1 | **missed** | `[1, 3], [1.5, 1]`: the integer 1 and the string "1" are one group (API and Cypher twin alike); `RETURN DISTINCT` keeps them apart → **bug-cyp-135** |
| AG2 | **missed** | `count(DISTINCT)` 2 for the stored values and 2 for `UNWIND [1, '1', true, 'true']` (predicted 3 and 4): the key is the text → **bug-cyp-135** |
| AG3 | held | `[[1, 2], [3]]` lists of integers; `[{k: 1}]` a map |
| AG4 | held | 3 (integer), 1.5; 5.5, 1.8333… |
| AG5 | partial | coerced, as the docs alternative said: `UNWIND ['1', '2']` sums to 3, but a stored `'x'` counts as 0 (`sum` over `'1'`, `'x'` is 1), which no source states |
| AG6 | held | `[0, 0, null, []]`; no rows |
| AG7 | partial | API relationships: `sum(coalesce(r.w, r.weight))` 3.5 as predicted; the probe's `sum(r.w) + sum(r.weight)` answered 4 on API and Cypher twins → **bug-cyp-137** (the single-sum twin was not observed in the predicted form) |
| WS1-WS7 | held (7) | parameter and literal pages equal; `-1` and `1.5` refused with NegativeIntegerArgument and InvalidArgumentType, parameter and literal alike; `LIMIT 0` no rows; two DISTINCT nodes, one DISTINCT name; ORDER BY a WITH column and an alias; a null-`v` node first with `DESC` |
| UN1 | held | one row; two rows |
| UN2 | partial | row counts as predicted, but the value is `'\x01N1'`, not 1 → **bug-cyp-138** |
| UN3 | held | both refused with a SyntaxError (messages are not the TCK's error names) |
| EX1, EX2 | held | `a1`, `a2` for `EXISTS {}` and the pattern predicate; the complement for `NOT`; `gx` under `USE GRAPH` |
| PC1, PC3 | held | `['a2', 'a3']`, `[]`; `[20]` both |
| PC2 | **missed** | 1, not 2: the second `create_edge` in the multigraph graph returned False. The owner [structure.multigraph](../../../ontology/features/graph-structure.g5.md#structure.multigraph) already says direct create deduplicates at this pin; the prediction overlooked it |
| PA1-PA4 | held | `1, 'K…', 'a1', 'a2', 2, 1` both writers; start is the source for incoming and undirected patterns; named graph; lengths 1, 1, 2 and names through the comprehension |
| PA5 | **missed** | multigraph 1 (same cause as PC2); single-edge 1 as predicted |
| PA6, PA7 | held | batch duplicate stored once (the call answers 2, the batch size, as documented); Cypher `CREATE` adds nothing in the single-edge graph and a second edge in multigraph mode |
| DL1-DL6 | held (6) | refused with ConstraintVerificationFailed for outgoing and incoming-only edges; DETACH removes the node and its edges, and the native walk over `^KG` no longer reaches it; `DELETE r` keeps the endpoints and `create_edge` then answers True; `REMOVE` of a property and of a label reach `keys`, `labels` and `get_node`; `USE GRAPH` deletes only that graph's edge; one of two parallel edges remains |

Found after the freeze, not predicted:
- arithmetic over two property aggregates is read as a rounded integer (**bug-cyp-137**), from `AG4_mixed_props`;
- a SKIP/LIMIT parameter of string, boolean or whole-float kind is used as a count, `'x'` raises a raw `ValueError`, and
  null is "not provided" (**bug-cyp-139**);
- a whole-label count as a UNION branch fails with SQLCODE -1 (**bug-cyp-140**);
- `startNode`/`endNode` of a `relationships(p)` element fail with SQLCODE -29 (**bug-cyp-141**, from `PA4_rels`);
- a UNION of `1`, `2.5`, `true`, `[1]` loses `true` (merged with 1) and answers `'[1]'` (part of bug-cyp-138);
- the native executor answers the AG1 grouping with typed groups (**bug-cyp-136**);
- a parameter `LIMIT` sends an otherwise native read to the SQL path (observation, no finding);
- after the source read, the default-graph `DELETE` of an ID a named graph also holds with an edge was predicted to
  delete (graph scope) and did.
- after the source read of the OPTIONAL MATCH WHERE placement, a probe with its prediction written first (one row per
  node, null where no match passes; [optional_where_probe.py](optional_where_probe.py),
  [optional_mixed_probe.py](optional_mixed_probe.py)): eleven of twelve single-side shapes held; conditions that read
  an earlier variable departed: arithmetic or `OR` fail with SQLCODE -94 (**bug-cyp-142**), and an equality or
  inequality on an earlier node's property drops the nodes that lack it (**bug-cyp-143**). The first runs of both probes
  read only the rows and showed the refusals as empty answers; they are kept under `failed-runs/`
  ([where](failed-runs/optional-where-observed-20261117T055812Z.json), [mixed](failed-runs/optional-mixed-observed-20261117T055837Z.json));
  the reruns ([where](optional-where-observed-20261117T060017Z.json), [mixed](optional-mixed-observed-20261117T060018Z.json)) record the error.
