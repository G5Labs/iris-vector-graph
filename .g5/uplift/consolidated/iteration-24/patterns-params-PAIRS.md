# W28: inline map patterns and parameters, node vs relationship — predictions frozen before observation

Frozen 2026-11-16. Before image: seal 23 `54d2bf1f`. Predictions from the owners written this session
(`query.values.equality`, `.in_lists`) and the known issue (relationship shapes `= $v` and inline `{score: 0.95}` share
the spelling rule). No new source read.

| Shape | Node "1" | Node 1 | Node 1.0 (double) | Relationship "1" | Relationship 1.0 |
|---|---|---|---|---|---|
| `= 1` (reference, observed in iteration 16/23) | no | yes | yes | yes | yes |
| inline `{p: 1}` | no (as `=`) | yes | yes | yes | yes |
| `= $v`, v = 1 | no | yes | yes | yes | yes |
| `IN $list`, list = [1] | yes (as literal IN) | yes | unknown | yes | no (as literal IN) |
| inline `{p: true}` | yes (legacy "1"? only if stored text) — "1" is a legacy spelling: yes | yes | unknown | yes | no |

## Outcome ([observation](patterns-params-observed-20261116T173330Z.json))

Every prediction held: inline `{p: 1}` and `= $v` follow `=` on both kinds; `IN $list` follows literal `IN` (bug-cyp-106
also covers parameter lists); `{p: true}` follows the legacy spellings; node double 1.0 is `IN [1]` (its text is "1").
No new discrepancy.

## W29: value functions at the boundary — frozen before observation

Values: node and relationship `p` = "7", 7, 7.5, true. Expressions: `toString(x.p)`, `toInteger(x.p)`, `x.p + 1`,
`coalesce(x.p, 'z')`. openCypher: toString("7") "7", toString(7) "7", toString(7.5) "7.5", toString(true) "true";
toInteger("7") 7, toInteger(7.5) 7, toInteger(true) error/null; "7" + 1 "71", 7 + 1 8, 7.5 + 1 8.5; coalesce returns
the value. Known issue (documented): arithmetic reads a string that spells a number as the number, so node/relationship
"7" + 1 = 8. Owner-derived: relationship "7" reads back as 7 (relationship_text), so toString of it may be "7".
Anything else would be new.

## W29 outcome ([observation](value-functions-observed-20261116T173357Z.json))

Held: `toString`, `toInteger` and `+` follow the documented string-arithmetic known issue on both kinds (`"7" + 1` is 8).
**Miss:** relationship `coalesce(x.p, 'z')` returns the stored text (`'7'`, `'7.5'`, `'1'` for true) while node
`coalesce` keeps types. This follows from the existing owner clause that only marked relationship-property columns are
decoded, but was not predicted: Low bug-cyp-107. Booleans in arithmetic (node `'true1'`, relationship 2) are recorded
in the owner as variants of the documented behavior, without a new entry.
