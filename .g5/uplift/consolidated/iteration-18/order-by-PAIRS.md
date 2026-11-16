# W19: ORDER BY over mixed property values, node vs relationship — predictions frozen before observation

Frozen 2026-11-16 before any native call on this workflow. Before image: seal 17 `3181d497`.
Exposure: the translator comment at the property-to-property comparison ("a range compares them by Cypher
orderability, as ORDER BY sorts them (CY_SORT_KEY): numbers as numbers, strings as strings, null across kinds") and a
grep hit `CASE WHEN ISNUMERIC(sort_expr) = 1 THEN CAST(sort_expr AS DOUBLE) END` near translator line 6233, context
unread. I have not read `CY_SORT_KEY` or how relationship properties are sorted.

Owners consulted: `query.values`, `.relationship_text`, `.equality`, `.ordering`. None states ORDER BY.
openCypher ascending orderability: strings < booleans < numbers, nulls last; within a kind by value.

World: one label with eleven nodes (or eleven edges from one anchor), property `p` written by `create_node` /
`create_edge`: 10, 9, 2.5, "10", "9", "abc", "B", true, false, "" and a missing property. Reader:
`MATCH ... RETURN x.p ORDER BY x.p` (and `DESC`), read in RETURN's own types.

| Prediction | Node | Relationship |
|---|---|---|
| owner/openCypher, ascending | "", "10", "9", "B", "abc", false, true, 2.5, 9, 10, null | same on the values RETURN reads; but RETURN reads "10"/"9" as integers on relationships, so they would join the numbers: "", "B", "abc", false, true, 2.5, 9, "9"→9, 10, "10"→10, null |
| source hint (ISNUMERIC cast) | numeric strings may sort as numbers | likely the same cast |

Material question: whether node and relationship sort the same stored strings ("10", "9") into different kinds, and
whether either path sorts in an order that disagrees with the values RETURN shows.

## Outcome of the first probe ([observation](order-by-observed-20261116T170357Z.json))

Node strings "9" and "10" sort among the numbers (`9, '9', 10, '10'`) while RETURN reads strings and node WHERE drops
them against numbers: **miss** against the openCypher prediction for nodes, matching the source hint. Relationship
"9"/"10" sort as numbers, consistent with RETURN. Nulls last ascending, first descending. Source read afterwards:
`Graph.KG.Cypher.SortKey.Key`. The node behavior is a documented known issue ("A property cannot tell a number from a
string that spells it", docs/KNOWN_ISSUES.md:183); no register entry is added for it.

## W19b: empty string under the two executors — prediction frozen before observation

The sort-key binding showed `SortKey.Key("")` over the Native API returns the null rank `z`, while SQL
`CY_SORT_KEY('')` (bound as `$Char(0)`) returns the string rank `l`. Query
`MATCH (a {id: 'x'})-[:R]->(b) RETURN b.p ORDER BY b.p` is planned natively. Targets' `p`: `""`, `"b"`, `2`, missing.

| Executor | Prediction |
|---|---|
| SQL path | `""`, `"b"`, `2`, null (empty string first among strings) |
| native (owner: equal answers) | the same |
| native (source-informed risk) | `"b"`, `2`, then `""` with the nulls, if the stored empty string reaches `SortKey.Key` as ObjectScript `""` |

## W19b outcome ([observation](empty-string-order-observed-20261116T170714Z.json))

The source-informed risk held and the owner prediction (equal answers) failed: SQL `'', 'a', 'b', 1, 2, null`;
native `'a', 'b', 1, 2, '', null`; `execute_cypher` answered natively. Recorded as bug-cyp-104.
