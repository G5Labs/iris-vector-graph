# W46: SQL table mappings through the Cypher reader

Selected from the product-wide inventory after iteration 39: `map_sql_table`, `map_sql_relationship`,
`remove_table_mapping`, `get_table_mapping`, `list_table_mappings`, `reload_table_mappings` have no binding, were never
run natively ("FHIR suites skipped"; q-plt-018), and need no external provider: they map an ordinary SQL table. Owners:
`fhir.sql_mapping`, `.relationships`, `.adjacency` (statements); q-plt-018 (graph scope, open). Verus before: nothing.

## Predictions, frozen before reading the source (owner statements, API reference)

A fixture table `W46.Drug(id, name, year INTEGER)` with three rows and `W46.Target(id, drug_id)` with a foreign key.

| ID | Case | Reader | Predicted |
|---|---|---|---|
| T1 | `map_sql_table("W46.Drug", "id", "MDrug<run>", ["name", "year"])` | `MATCH (n:MDrug) RETURN n.id, n.name, n.year` | the three rows; nothing copied into IVG's tables (node count unchanged) |
| T2 | neighbor: an IVG node created with label `MDrug<run>` before mapping | the same MATCH | not returned while the label is mapped (owner: the mapped label is read from its table only) |
| T3 | `remove_table_mapping` | the same MATCH; the SQL table | the IVG node returns; the table is untouched |
| T4 | map `MTarget` and `map_sql_relationship("MTarget", "OF", "MDrug", target_fk="drug_id")` | `MATCH (t:MTarget)-[:OF]->(d:MDrug) RETURN t.id, d.id` | one row per target, joined on the foreign key |
| T5 | neighbor of T4: removing the `MDrug` mapping | `list_table_mappings()`; the T4 MATCH | the relationship mapping is gone too |
| T6 | `khop` / variable-length `*1..2` from a mapped node | answers | nothing from mapped rows (owner: not in the adjacency index) |
| T7 | `USE GRAPH 'g'` with the mapping in place | MATCH | the same rows (q-plt-018's evidence: no graph column) |
| T8 | `WHERE n.year = 2011` (an INTEGER column) | rows | the matching row |
| T9 | a second engine created before the mapping, without `reload_table_mappings()` | its MATCH | not predicted with confidence: the API names a per-engine cache, so the second engine may still read IVG's own nodes |

## Outcome (observed after the freeze)

Observations: [1](sqlmap-observed-20261117T004907Z.json), [2](sqlmap-observed2-20261117T004940Z.json) (the reversed key reading and IVG relationships from mapped nodes, added after the first
observation), then the [binding](../../../Verus_verification/results/sql_mapping/20261117T005114Z-binding/receipt.json) (AGREES with `sql_mapping.rs`).

| ID | Held? | What happened |
|---|---|---|
| T1 | yes | the three rows; IVG's node count unchanged |
| T2 | yes | the IVG node with the mapped label is hidden |
| T3 | yes | after removal the IVG node returns; the table keeps its 3 rows |
| T4 | **no** | with the key on the source table, as documented, `SQLCODE -29` ("N1.DRUG_ID"); the key is read on the target table (observation 2) — new bug-cyp-108 |
| T5 | yes | the relationship mapping went with the label |
| T6 | yes | `khop` and `*1..2` find nothing from mapped rows |
| T7 | yes | `USE GRAPH` reads the same rows |
| T8 | yes | `WHERE n.yr = 2011` (literal and parameter) finds the row |
| T9 | (unconfident) | engine B kept reading IVG's own node after A mapped the label, until reload — question `fhir.sql_mapping.cache` |

Added after reading the source or the first observation (not frozen): T0, an unqualified table is refused
(bug-cyp-110); any IVG relationship from a mapped node is an SQL error (bug-cyp-109). The owner's relationship
statement was corrected (the key's side). Material prediction gained: `fhir.sql_mapping` now predicts the key side,
the IVG-relationship limit, the per-engine cache and the unqualified-name refusal.
