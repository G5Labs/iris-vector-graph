# W22: null and missing properties in WHERE, node vs relationship — predictions frozen before observation

Frozen 2026-11-16 before any native call on this workflow. Before image: seal 19 `be91d90c`.
Exposure: the W16–W19 equality/ordering/sort sources; `_number_eq_sql` docstring ("`negate` is `<>`: NOT IN, still null
for a null property"). I have not read how `IS NULL`, `NOT`, or `IN` lists are translated, nor how a JSON `null` in
qualifiers is read.

Owners: `query.values.*` (W16–W19); none states null handling. openCypher: a missing property is null; `null = 5`,
`null <> 5`, `null IN [5]` are null (row dropped); `NOT (null = 5)` is null (dropped); `x.p IS NULL` is true.

States: node property missing; node `p = 5`; relationship qualifiers absent (NULL); qualifiers `{}`;
qualifiers `{"p": null}` (Python None); `{"p": 5}`. Queries: `= 5`, `<> 5`, `NOT x.p = 5`, `IN [5, 6]`,
`NOT x.p IN [5]`, `IS NULL`, `IS NOT NULL`, `RETURN x.p`.

| State | = 5 | <> 5 | NOT = 5 | IN [5,6] | NOT IN [5] | IS NULL | IS NOT NULL |
|---|---|---|---|---|---|---|---|
| any missing/null state (openCypher) | no | no | no | no | no | yes | no |
| value 5 | yes | no | no | yes | no | no | yes |

Source-informed risks: `NOT` around a SQL predicate may turn SQL NULL into true for missing properties; the three
relationship null states may differ (absent vs `{}` vs explicit `null`).

## Outcome ([observation](null-semantics-observed-20261116T171534Z.json))

Every cell held on both kinds, including the three relationship null states (qualifiers absent, `{}`, `{"p": null}`)
and `NOT` around a comparison. No discrepancy.

## W23: string predicates on numeric properties — frozen before observation

Values: node and relationship `p` = 12 (number), "12" (string), "abc". Predicates: `STARTS WITH '1'`, `CONTAINS '2'`,
`ENDS WITH 'c'`. openCypher: a string predicate on a number is null (dropped). Owner: `query.values` reads node 12 as
a number. Source-informed expectation: relationship text is compared as text (`JSON_VALUE` "12"), so relationship 12
matches `STARTS WITH '1'` — a variant of the documented known issue "a property cannot tell a number from a string that
spells it". Node 12 (stored number): unknown.

## W23 outcome ([observation](string-predicate-observed-20261116T171621Z.json))

Relationship 12 matches `STARTS WITH '1'` (expected variant of the known issue). **Node 12 (stored number) also
matches**, which the known issue does not mention and which contradicts the node path's typed equality and ordering.
Recorded as Low bug-cyp-105. Source read afterwards: `_boolean_expr_comparison_ops`.

## Set aside

Migrations (161 members, none bound): mostly the 3.2.0 → 4.0.0 upgrade. Testing needs a reconstructed 3.2.0
installation (about one iteration) and affects only installs two major lines back.
