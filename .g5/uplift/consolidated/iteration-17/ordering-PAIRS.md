# W18: ordering comparisons on node vs relationship properties — predictions frozen before observation

Frozen 2026-11-16 before any native call on this workflow. Before image: seal 16 `1f949ffe`.
Exposure: the docstring of translator `_stored_number_value` ("a node property row's val as a DOUBLE when it holds a
number, else NULL: a string never orders against a number (openCypher: null), where CAST(val AS DOUBLE) read the
string '.95' as 0.95 (4.7.0 row 24)"). I have not read how relationship properties are ordered or how ORDER BY sorts.

Owners consulted: `query.values`, `query.values.relationship_text`, `query.values.equality` (W16). None states
ordering. openCypher: comparing a number with a string gives null, so `WHERE x.p > 0.5` drops the row.

Worlds as W16 (create_node / create_edge writers), values: float 0.95, int 1, string "0.95", string ".95", string "1",
string "x", bool true. Queries: `WHERE x.p > 0.5`, `WHERE x.p < 2`, `RETURN count(*)`.

| Value | Node `> 0.5` / `< 2` | Relationship `> 0.5` / `< 2` | Basis |
|---|---|---|---|
| float 0.95 | yes / yes | yes / yes | numbers |
| int 1 | yes / yes | yes / yes | numbers |
| string "0.95" | no / no | **unknown**: yes/yes if relationship text is cast like `RETURN` decodes it ("0.95" reads as a float) | node: docstring; rel: owner analogy with relationship_text |
| string ".95" | no / no | unknown: RETURN reads it as text, so openCypher says no | |
| string "1" | no / no | unknown (RETURN reads integer 1) | |
| string "x" | no / no | no / no | |
| bool true | no / no | unknown (JSON_VALUE reads true as 1, W16) | |

Expected material contrast: if relationship ordering casts text like `RETURN`, then the user string "0.95" orders as a
number on a relationship but not on a node (the W16 asymmetry extended to ordering), and a relationship boolean may
order as 1.

## Outcome ([probe](ordering-observed-20261116T165915Z.json), then the 52-world binding)

| Prediction | Outcome |
|---|---|
| node strings and booleans never order | held |
| numbers order by value on both kinds | held |
| rel "0.95" orders as 0.95 (unknown) | resolved: yes |
| rel ".95": openCypher no (RETURN reads text) | **as-built yes**: orders as 0.95 |
| rel bool true (unknown) | resolved: orders as 1 |
| rel "x": `> 0.5` / `< 2` no / no | **miss on `< 2`**: kept, because the cast reads "x" as 0 |

The material discovery is the last row: any non-numeric relationship text orders as 0 (and `"12abc"` as 12), while
the product removed that cast-to-0 reading on every other comparison path. Source read after the probe:
`_translate_boolean_expression` / `_as_number`.
