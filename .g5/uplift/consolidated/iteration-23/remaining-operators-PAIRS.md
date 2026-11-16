# W27: IN lists and min/max over Python-written mixed values — predictions frozen before observation

Frozen 2026-11-16 before any call on this workflow. Before image: seal 22 `ff05f394`. Predictions are made from the
owners as written in this session (`query.values.equality`, `.sorting`) and the 4.1.0 changelog ("`IN [true]` matches
'true', '1' and 'True'"). No new source read.

| Case | Owner-derived prediction | openCypher |
|---|---|---|
| node "1" `IN [1]` / node 1 `IN [1]` | no / yes (node equality needs a stored number) | no / yes |
| relationship "1" `IN [1]` | yes (relationship spelling rule) | no |
| node 1 `IN [true]` | yes (legacy boolean spellings) | no |
| node {"9", 5}: `min(x.p)`, `max(x.p)` | min 5, max "9" if min/max use the sort key (numeric strings as numbers) | min "9", max 5 |
| relationship {"9", 5}: min, max | min 5, max 9 (both read as numbers) | min "9", max 5 |

## Outcome of the first probe ([observation](remaining-operators-observed-20261116T172936Z.json))

**Miss:** node "1" `IN [1]` matched (predicted no), and node 1 `IN ['1']` matched. Relationship cells followed the
spelling rule. Node 1 `IN [true]` matched (legacy spellings, as predicted). min/max on nodes followed the sort key (min
5, max "9"), as predicted. Source read afterwards: node `IN` compiles to `p3.val IN (?)` with no stored-number test
(`_boolean_expr_in`).

## W27b, frozen before observation

Node strings "01", "1.0", "abc", "" against `IN [1]` and `IN [0]`. If IRIS compares the text with the number
numerically: "01" and "1.0" are in [1]; "abc" and "" are in [0] (text read as 0). openCypher: none.

## W27b outcome ([observation](node-in-observed-20261116T173018Z.json))

The numeric-comparison prediction was **refuted**: node "01", "1.0", "abc" and "" match neither `IN [1]` nor `IN [0]`;
IRIS compares the text with the number's text. In the binding, the port's assumption that relationship `IN` follows
relationship `=` was a further **miss**: a relationship whole float 1.0 is not `IN [1]` (attempt kept). Recorded as
Medium bug-cyp-106 and owner `query.values.in_lists`.
