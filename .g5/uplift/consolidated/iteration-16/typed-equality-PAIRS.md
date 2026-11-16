# W16: typed equality in Cypher WHERE, node vs relationship — predictions frozen before native observation

Frozen 2026-11-16 before any native call on this workflow. Before image: seal 15 `1cb3bb2f`.
Exposure: I read the docstrings of translator `_node_number_eq_sql` / `_number_eq_sql` (4.7.0 row 24: a node property
must hold a stored number; relationship text is compared with the number's spellings), `prop_values.number_spellings`,
`TRUE_SPELLINGS = ("true","1","True")`, `FALSE_SPELLINGS = ("false","0","False")` and the line
`col IN bool_spellings_sql(value)`. I have not read which caller uses the boolean spelling test for nodes vs
relationships, nor how `JSON_VALUE` spells a JSON boolean.

Owners consulted first: `query.values` (node reads keep the stored type) and `query.values.relationship_text`
(relationship text decoded by spelling; `1` and `0` are integers, not booleans). No owner states `WHERE` equality.
No Verus model covers `WHERE` comparison.

Worlds, each on fresh nodes or a fresh edge: property `p` written through `create_node(properties=...)` or
`create_edge(qualifiers=...)`, with values int 1, bool True, string "1", float 0.95, string "0.95", int 0, bool False.
Readers: `MATCH ... WHERE x.p = <literal> RETURN count(*)` for literals `true`, `false`, `1`, `0`, `0.95`, and
`RETURN x.p`.

| Stored value | Kind | RETURN x.p | = true | = 1 | = 0.95 | Basis |
|---|---|---|---|---|---|---|
| int 1 | node | 1 | no | yes | — | query.values |
| bool True | node | True | yes | no | — | query.values |
| string "1" | node | "1" | no | no | — | query.values (string stays string) |
| float 0.95 | node | 0.95 | — | — | yes | row 24 docstring |
| string "0.95" | node | "0.95" | — | — | no | row 24 docstring |
| int 1 | relationship | 1 | **yes (source) / no (owner, openCypher)** | yes | — | TRUE_SPELLINGS contains "1" |
| bool True | relationship | True | yes | unknown (depends on JSON_VALUE's spelling of true) | — | — |
| string "1" | relationship | 1 (decoded) | **yes (source)** | yes | — | relationship_text + spellings |
| float 0.95 | relationship | 0.95 | — | — | yes | R121 spellings |
| string "0.95" | relationship | 0.95 (decoded) | — | — | yes | relationship_text; differs from node |

Expected material contrasts: (1) a relationship holding integer 1 (or 0) satisfies `= true` (`= false`) although
`RETURN` reads it as an integer and the same node value does not; (2) the user string "0.95" equals 0.95 on a
relationship but not on a node. The first is a WHERE/RETURN disagreement; the second is a node/relationship asymmetry
consistent with each kind's read rule.

## Outcome (first native run `typed-equality-observed-20261116T164516Z.json`, then the binding panel)

| Prediction | Outcome |
|---|---|
| node int 1: `= true` no | **miss**: matches (stored number compared with the text `'1'`) |
| node string "1": `= true` no | **miss**: matches (legacy spelling) |
| node int 0: `= false` (not predicted) | matches |
| node bool true: `= 1` no | held |
| node string "0.95": `= 0.95` no; node float 0.95 yes | held |
| rel int 1 and string "1": `= true` yes (source) | held; the owner/openCypher prediction "no" was wrong as-built |
| rel bool true: `= 1` unknown | resolved: matches (`JSON_VALUE` reads true as 1) |
| rel string "0.95": `= 0.95` yes | held |

The node misses were the material discovery: the documented known issue names stored strings only, while stored
integers match too. In the binding, relationship float twins and JSON float spellings produced two further misses
(see the model NOTES); both are kept as attempts.
