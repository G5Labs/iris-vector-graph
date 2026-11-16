# Cypher WHERE equality and ordering against a boolean or integer literal, node vs relationship

Product `3eaa79cf`, unchanged. Iteration 16 (cloud continuation). Predictions were frozen before native observation in
[typed-equality-PAIRS.md](../../../uplift/consolidated/iteration-16/typed-equality-PAIRS.md), with the exposure noted.
Owner: [query.values.equality](../../../ontology/features/cypher.g5.md#query.values.equality).

## What the model decides

Inputs are the stored representation and the literal; the match is derived.

- **Node** (`rdf_props.val`, the accepted `node_read` model's `Stored`): a boolean literal tests the three spellings of
  `TRUE_SPELLINGS`/`FALSE_SPELLINGS` as SQL `IN`; text compares as text and a stored integer through its canonical
  text (`num_text`, defined digit by digit). An integer literal requires a stored number of that value
  (`_node_number_eq_sql`, 4.7.0 row 24).
- **Relationship** (one JSON member of `qualifiers`): `WHERE` reads `JSON_VALUE` text. A boolean literal tests the same
  spellings; an integer literal accepts the integer's canonical text or its float twin `m.0` (`_number_texts`).
- **RETURN** is the accepted readers, imported unchanged: `node_read::read(cy_typed(..))` and
  `rel_prop_text::as_built`.

Providers, explicit and not assumed beyond their names: IRIS compares a stored integer with `'1'` through its canonical
text; `JSON_VALUE` reads a JSON boolean as `1`/`0` and keeps a whole JSON float's spelling; a stored double's text and
its numeric equality with an integer are uninterpreted functions (`double_text`, `double_equals_int`).

## Theorems

| Theorem | Distinction |
|---|---|
| `theorem_node_true_exact` | a non-double node property equals `true` iff it is text `true`/`1`/`True` or the stored integer 1 |
| `theorem_node_where_return_disagree` | stored integer 1 and text "1" equal `true` while RETURN reads 1 and "1"; integer 0 equals `false` (self-contained) |
| `theorem_node_bool_not_integer`, `theorem_node_integer_needs_stored_number` | node boolean ≠ any integer; no node text equals an integer |
| `theorem_node_bool_agrees_outside_legacy` | outside the legacy spellings and stored 1, boolean equality agrees with openCypher on the read value |
| `theorem_rel_bool_equals_integer` | relationship JSON true equals 1 (false equals 0); the node boolean does not |
| `theorem_rel_integer_equals_true` | relationship integer 1 and string "1" equal `true`; RETURN reads both as integers |
| `theorem_rel_twin_spelling_equals_integer` | relationship text "12.0" equals 12 and reads as a float; node text "12.0" does not equal 12 |
| `theorem_string_integer_kind_asymmetry` | the string "12" equals 12 on a relationship but not on a node |

Counts: 41 verified = 18 new (17 proof functions and the `nat_text` termination check) + 23 unchanged imports
(`node_read` 13, `rel_prop_text` 10). Iteration 16 added 14; iteration 17 added the four ordering theorems. No `assume`, `admit` or `external_body`.

## Ordering (iteration 17)

Owner: [query.values.ordering](../../../ontology/features/cypher.g5.md#query.values.ordering). `_as_number` in
`_translate_boolean_expression` gives node value columns the typed reading (`_stored_number_value`: a number only when
stored as one, else NULL) and every other operand `CAST(... AS DOUBLE)`. The cast is the uninterpreted provider
`cast_double`; the relationship theorem holds under the stated cast value, which the binding observes.

| Theorem | Distinction |
|---|---|
| `theorem_node_text_never_orders` | any node text is dropped by any ordering against a number |
| `theorem_node_integer_orders_by_value` | a stored node integer orders by value |
| `theorem_rel_text_orders_as_cast` | letter-initial relationship text other than true/false, cast to 0, is below every positive integer while RETURN reads the text; the node is dropped |
| `theorem_rel_bool_orders_as_number` | a relationship JSON true orders as 1; a node boolean never orders |

Provider prediction for the cast (numeric prefix, else 0) held on the first ordering run, including `"12abc"` and `""`.

## Controls

Seven controls, each failing its named theorems in full and isolated runs with ordinary errors:
`legacy-one-not-true`, `node-number-by-text` (the pre-4.7.0 node rule), `json-boolean-reads-as-word` (provider),
`stored-integer-not-a-spelling` (the typed alternative), `twin-spelling-dropped`, `rel-ordering-typed` (the node rule on
relationships) and `node-ordering-cast` (the pre-4.7.0 node rule). The first runs of
`legacy-one-not-true` and `stored-integer-not-a-spelling` were FAIL_ELSEWHERE because the disagreement theorem
called `theorem_node_true_exact`, whose contract is trusted in an isolated run; it now derives its cases directly.

## Binding and misses

[Final receipt](../../results/typed_equality/20261116T170150Z-binding/receipt.json): 26 values × {node, relationship}
= 52 worlds, 676 comparisons (seven equality literals, five orderings, and RETURN with its Python type), AGREES; each
of seven port mutations is detected by 2–17 worlds. The iteration-16 equality receipt
`20261116T165332Z-binding` (44 worlds, 352 comparisons) is the earlier accepted version. Two earlier attempts are kept:

- `…165200Z-binding-attempt1-model-miss`: the model and port compared relationship integers with the canonical text
  only. The source's `_number_texts` also accepts the float twin (`1.0`), so the string "1.0" equals 1. The model was
  corrected from source and a control added.
- `…165317Z-binding-attempt2-provider-miss`: the port guessed that `JSON_VALUE` drops a JSON float's leading zero;
  `0.0` reads as `0.0`. Only the declared provider function changed.

Float cells are provider observations fitted after attempts 1–2; integer, boolean and string cells were predicted.
Scope: SQL path (`native_cypher=False`), literals only, writers `create_node`/`create_edge`. No executable product
body is verified.
