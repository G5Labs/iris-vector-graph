# Iteration 58 W2: proposed owner-block edits (not applied; the builder integrates)

Additive bullets only. "Today ..." marks an as-built departure. Paths are relative to `.g5/ontology/features/`.
Finding anchors point at this worker's [findings](findings.md) until the builder copies them into bugs_issues.md.

## query.values (`cypher.g5.md#query.values`)

Add:

- Which columns are decoded is decided per RETURN item by the translator: a node property, a WITH variable bound to a bare node property, and a RETURN `coalesce()` of node properties and scalars read through `CY_TYPED` and the stored-boolean reading; a comparison is a boolean column; a list or map expression a JSON column; anything else reaches the reader as the IRIS driver hands it. Every such typed read answers the value written, of every kind, under IRIS drivers 5.3.2 and 5.4.1 and at all four readers.
- Today a `CASE` column whose branches are node properties is not decoded: a stored boolean answers `'true'`, a stored list or map its JSON text, and with IRIS driver 5.4.1 a stored number its text (`'3'`), on every reader ([finding](findings.md#bug-cyp-156)).
- Today `WITH coalesce(n.a, n.b) AS x ... RETURN x` answers a stored number or boolean as text (`'3'`, `'true'`) under both drivers, while `RETURN coalesce(n.a, n.b)` is typed ([finding](findings.md#bug-cyp-155)).
- Verus: [result_decoders](../../Verus_verification/models/result_decoders/NOTES.md) theorem_typed_roundtrip, theorem_strings_held_everywhere, theorem_with_coalesce_number_is_text, theorem_case_bool_is_text, theorem_case_container_is_text, theorem_case_number_by_driver, theorem_compare_is_boolean_or_null

## query.optional (`cypher.g5.md#query.optional`)

Add:

- A property of a node the `OPTIONAL MATCH` did not bind is null at every reader and under both IRIS drivers, through a `WITH` too, and `collect()` of the unbound node is `[]`.
- Today the unbound node itself, at `execute_cypher`, `/api/cypher` and tx/commit (its three columns), answers `b_id` null but `b_labels` and `b_props` `'[]'`; Bolt answers the node as null ([finding](findings.md#bug-plt-135)).
- Verus: [result_decoders](../../Verus_verification/models/result_decoders/NOTES.md) theorem_null_row_every_decoder, theorem_optional_node_labels

## query.shadow (`cypher.g5.md#query.shadow`)

Add:

- Observed (iteration 58, both IRIS drivers): with `IVG_CYPHER_SHADOW=1`, a read the native executor accepts (`MATCH (a:L)-[:K]->(b) RETURN a.node_id, b.node_id`; `MATCH (n:L) RETURN n.node_id, n.v, n.s`) is answered natively, compared once with the SQL path without a mismatch, and answers the same rows and types at `execute_cypher` and through Bolt. The `ORDER BY` forms of these reads are not native-planned and run on the SQL path.

## query.compiled.equal-answers (`cypher.g5.md#query.compiled.equal-answers`)

Add:

- Observed (iteration 58, both IRIS drivers): the same native-accepted reads answer identical rows and types under the modes `off`, `sync` and `job`. Not isolated: a compiled class's second run (the engine's route chooser sent the repeat to the SQL path).

## query.paging (`cypher.g5.md#query.paging`)

Add:

- Observed (iteration 58): a variable-length read from a node named by id with `LIMIT 2`, `ORDER BY ... LIMIT 2`, `ORDER BY ... DESC LIMIT 2` and `SKIP 1 LIMIT 2` answers the corresponding rows of the full answer (duplicates per path kept), at all four readers; these shapes run in SQL (`CY_VLP_PATHS` with `FETCH FIRST`), not through the engine's BFS routes.
