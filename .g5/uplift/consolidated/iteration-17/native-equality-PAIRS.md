# W17: the W16 equality cells on the native Cypher executor — predictions frozen before observation

Frozen 2026-11-16 before any native-executor call on this workflow. Before image: seal 16 `1f949ffe`.
Exposure: I have not read the native executor's comparison code. I know from the owners that the native executor is on
by default where the adjacency index is declared, answers only reads, and must give the SQL path's rows
([query.native.equal-answers](../../../ontology/features/cypher.g5.md#query.native.equal-answers)); "a defect found on the
SQL path ... is fixed on the SQL path first, and the native executor copies the fixed behavior."

Changing input: the executor (engine `native_cypher=True` with the index declared vs `native_cypher=False`), holding
the W16 worlds and queries fixed. Reader: the same `WHERE x.p = <literal> RETURN count(*)` and `RETURN x.p`.

| Cell | Owner prediction (equal answers) | Source-informed prediction |
|---|---|---|
| every W16 cell, node and relationship | native = SQL, including node integer 1 = true | none (native comparison code not read) |
| routing | each query is answered natively (read, MATCH, no UNION/procedure) | unknown whether count(*) and relationship filters route natively |

Material question: whether the native executor reproduces the legacy boolean match and the node stored-number rule, or
applies typed equality (openCypher), which would break equal answers.

## Outcome

[Observation](native-equality-observed-20261116T165710Z.json): the native gate is open (`native_gate` returns None), yet
none of the 352 W16 cells routes natively: `native_plan.plan_query` returns None. The source states why
(`native_plan._value`, lines 62–74): "strings only: the SQL path's typed equality rules for numbers, booleans and
lists are not reproduced yet". Equal answers therefore hold for boolean and integer literals because the native path
declines them, not because it reproduces the rules. Probing nine further shapes (label scans, relationship filters,
`{p: true}` patterns, parameters) also found no native plan without an anchored string-valued shape.

Disposition: the owner prediction (equal answers) holds; the routing question is resolved by source and observation.
No formal claim or reach credit: this is a routing fact, recorded in `query.values.equality`.

## Candidates set aside in this iteration, with reasons

- Store `query_nodes(property_filters=...)` compares `json.loads(stored text)` with the filter value (a string "1"
  would match the integer 1). No product caller passes `property_filters`; only tests and the store protocol do.
- `validate_graph_name` vs `Graph.KG.GraphKey:Validate`: the control-character tests may differ for C1 controls
  (U+0080–U+009F). Graph names with C1 controls are not ordinary data in this scope.
- Cypher `MERGE` find-or-create: unbound and consequential, but iteration 12 named it as the next workflow and
  iteration 13 turned away from it at the user's direction about an interrupted investigation whose subject was not
  recorded. Not pursued here, to keep that boundary.
