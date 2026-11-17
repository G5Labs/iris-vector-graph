# Iteration 58 (W62): frozen predictions, clause combinations and result decoders

Frozen at 2026-11-17 ~08:15 UTC, before any deciding source was read: the bodies of `iris_vector_graph/_engine/query.py`'s
`_decode_*_columns`, `_optional_null_columns`, `_fill_empty_columns`, `_shadow_compare`, `_cypher_shadow`, and the
translator's `_null_row_aggregate`, `optional_null_row_items`, `_unwound_known_text`, `_bool_flag`, `CY_LIST_KINDS`,
FOREACH/`SET +=`/`WITH *`/`CALL { }`/UNION handling and `_route_var_length`. Only function names (from a `grep` for
`def _decode_`) and line numbers named by the iteration-54/55 residual lists were seen.

Sources for each prediction: openCypher 9 / the Cypher manual semantics (marked **oC**), the owner blocks in
[cypher.g5.md](../../../ontology/features/cypher.g5.md) (marked with the block ID), and inherited findings. Where an owner
block already records a "Today" deviation, the prediction is the as-built behavior the owner records and is marked
**owner-Today**; such a prediction checks the owner, not the intent.

Data: API-written nodes and edges (`create_node`/`create_edge` or the store writers) with a fresh prefix `i58c_`/`i58d_`;
readers are Python `execute_cypher` (IRIS driver 5.3.2 unless stated), Bolt (neo4j driver 6.4.1 against the product's
TCP listener), `/api/cypher` and `/db/neo4j/tx/commit`.

## C: clause combinations (iteration-54 residual)

| ID | Prediction A | Neighbor B | Source |
|---|---|---|---|
| C1 OPTIONAL aggregates | `MATCH (a:L) OPTIONAL MATCH (a)-[:NONE]->(b) RETURN a.id, count(b), count(*)` → per `a`: `count(b)=0`, `count(*)=1` | same with one `a` that has a `K` edge to two `b`s, pattern `[:K]`: matched `a` gives `count(b)=2, count(*)=2`; unmatched gives `0, 1`; `collect(b.id)` is `[]` for the unmatched, `sum(b.v)` 0, `avg(b.v)` null | oC; query.optional |
| C2 UNWIND grouping | `UNWIND [1,'1'] AS x RETURN x, count(*)` → two groups (int 1 and string '1') | `UNWIND [1,true] AS x RETURN x, count(*)` → two groups; `RETURN DISTINCT x` over the same lists → two rows each | oC (values of different types are never equivalent). Inherited residual note says as-built one group for both: this prediction is the intent, expected to miss |
| C3 -94 boundary | `OPTIONAL MATCH (a)-[:K]->(b) WHERE b.v = a.v + 1` fails with SQLCODE -94 (owner-Today, bug-cyp-142) | `WHERE b.v = 2 OR b.v = 3` (OR over the new alias only) and `WHERE b.v - 1 = 2` (arithmetic over the new alias only) run and keep every `a` row (null row when no match) | query.optional |
| C4 UNION values | `MATCH (n) WHERE n.id=$f RETURN n.f AS x UNION RETURN 2.5 AS x` with stored double 2.5 → two rows, the stored one as storage text `"\x01D2.5"` (owner-Today, bug-cyp-138) | a stored list property in a branch reaches the reader as JSON text; `MATCH ()-[r:K]->() RETURN r AS x UNION ALL ...` returns a relationship value (oC) | query.union; oC |
| C5 CALL { } aggregation | `MATCH (a:L) CALL { WITH a MATCH (a)-[:K]->(b) RETURN count(b) AS c } RETURN a.id, c` → one row per `a`, `c=0` for an `a` with no `K` edge | the same with `RETURN b.id AS c` inside (no aggregate) → the unmatched `a` has no row | oC (unit/aggregating subquery) |
| C6 FOREACH | `MATCH (n {id}) FOREACH (x IN [1,2] \| SET n.f = x)` → `n.f = 2` (int) after | `FOREACH (x IN [1,2] \| CREATE (:M {v:x}))` creates two nodes; `FOREACH` over `[]` changes nothing | oC |
| C7 SET += | `SET n += {a: 1, b: null}` on an API node with `a='old', c='keep'` → `a=1` (int), `b` absent, `c='keep'` | `SET n = {a: 1}` → only `a` remains (`c` removed); `SET n += {t: toUpper('x')}` → `t='X'` | oC; query.writes.computed_values |
| C8 WITH * | `MATCH (a)-[r:K]->(b) WITH * RETURN a.id, type(r), b.id` → the same rows as without `WITH *` | `WITH *, a.v AS av RETURN av` → `a`'s value with its type | oC |
| C9 ORDER BY mixed after WITH | `MATCH (n:L) WITH n.v AS v ORDER BY v RETURN v` over API values string 'a', bool true, int 2, float 1.5, null → `'a', true, 1.5, 2, null` | `ORDER BY v DESC` → `null, 2, 1.5, true, 'a'` | query.values.sorting; oC orderability |

## D: result decoders and readers (iteration-55 residual)

| ID | Prediction A | Neighbor B | Source |
|---|---|---|---|
| D1 mixed-kind WITH column | `MATCH (n:L) WITH CASE WHEN n.k='i' THEN n.v ELSE n.s END AS x RETURN x` over int, float, string, bool values → each row keeps its type on all four readers (Python int/float/str/bool; Bolt the same; JSON number/string/boolean) | `WITH coalesce(n.v, n.s) AS x` over the same nodes → same typing | query.values; oC |
| D2 OPTIONAL null-row column | `MATCH (a:L) OPTIONAL MATCH (a)-[:NONE]->(b) RETURN a.id, b, b.x` → `b` and `b.x` null (Python `None`, Bolt `None`, JSON `null`) on all four readers | same column after `WITH a, b` → null; `collect(b)` → `[]` | query.optional |
| D3 empty strings and containers | a stored empty string `''` reads back `''` (not null) on all readers | a stored empty list `[]` reads back `[]`, an empty map `{}` reads `{}` | oC; query.values |
| D4 map columns | `RETURN {a: n.v, b: 'x'} AS m` with stored int `v` → a map whose `a` is an int on all readers | a map literal with a nested list and a boolean keeps their types | oC |
| D5 numeric expression columns | `RETURN n.v + 1, n.v * 1.5, n.v / 2` with stored int 3 → `4` (int), `4.5` (float), `1` (int division) | stored float 3.0: `4.0`, `4.5`, `1.5` (floats) | oC |
| D6 boolean expression columns | `RETURN n.v > 1 AS b` → `true`/`false` booleans on all readers | against a missing property → null | oC |
| D7 empty results | a `RETURN a.id, b.x` with no rows answers zero rows but the column names on all readers | `RETURN count(*)` with no matches → one row `0` | oC |
| D8 shadow and compiled | a read the native executor accepts answers the same rows and types with `IVG_CYPHER_SHADOW=1` as without, at the Python reader and through Bolt | the same read with compiled plans on answers the same | query.shadow; query.compiled.equal-answers |
| D9 variable-length LIMIT | `MATCH (a {id})-[:K*1..3]->(b) RETURN b.id LIMIT 2` → two rows | `... RETURN b.id ORDER BY b.id LIMIT 2` → the two smallest ids | oC; query.paging |
