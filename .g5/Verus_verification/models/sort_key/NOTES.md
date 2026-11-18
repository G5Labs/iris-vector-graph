# ORDER BY's sort-key rank for ordinary scalar values, and the two executors' argument

Product `3eaa79cf`, unchanged. Iteration 18 (cloud continuation). Predictions frozen before native observation in
[order-by-PAIRS.md](../../../uplift/consolidated/iteration-18/order-by-PAIRS.md). Owner:
[query.values.sorting](../../../ontology/features/cypher.g5.md#query.values.sorting).

## What the model decides

`rank(v, t)` transcribes the first character of `Graph.KG.Cypher.SortKey.Key` (and the SQL `CY_SORT_KEY`, which the
product's `test_257` holds to the same code) in its branch order, for ordinary scalar text: null `z`; empty (`$Char(0)`)
`l`; typed string `l`; boolean `m`; untyped `true`/`false` `m`; `NaN` `o`; a number, or untyped text `$IsValidNum`
accepts, `n`; other text `l`. Lists, maps, graph JSON, durations, dates and times are excluded by `scalar_text`.
`$IsValidNum` is an uninterpreted provider. The executors' argument is a stated transport premise: the SQL path gives
`Some("")` (`$Char(0)`), the native path gives ObjectScript `""`, i.e. null (`native_arg`).

## Theorems (52 verified = 9 new + 43 unchanged imports from typed_equality, node_read and rel_prop_text)

`theorem_rank_order`, `theorem_untyped_numeric_text_sorts_as_number`, `theorem_typed_string_sorts_as_string`,
`theorem_word_sorts_as_string`, `theorem_empty_string_sorts_as_string`, `theorem_null_sorts_last`,
`theorem_bool_before_number`, `theorem_node_where_and_order_by_disagree` (imports typed_equality's node ordering: a
numeric-looking node string is dropped by WHERE and sorted among numbers by ORDER BY) and
`theorem_executors_disagree_on_empty_string`. No `assume`, `admit` or `external_body`.

## Controls

Five, all EXPECTED_FAIL in full and isolated runs: `untyped-number-as-string` (openCypher's rule), `boolean-after-number`,
`empty-string-as-null`, `null-first`, `native-empty-as-string` (the repair).

## Binding

[Receipt](../../results/sort_key/20261116T170756Z-binding/receipt.json): 30 SQL `CY_SORT_KEY` cells and 29 direct
`SortKey.Key` calls over the Native API, AGREES; four rule mutations detected. The `$IsValidNum` regex guess held on
the first run. `…170611Z-binding` is the SQL-only first version; `…170637Z-binding-attempt2-transport-miss` is the
first run with class calls, where `Key("")` returned the null rank. That observation is the transport premise, and the
executor comparison ([observation](../../../uplift/consolidated/iteration-18/empty-string-order-observed-20261116T170714Z.json))
confirmed it at the public reader. No executable product body is verified.

Iteration 20 extended the imported `typed_equality` by one theorem, so this crate grew from 50 to 51 with no change
here; the evidence gate marked the old receipts stale, the proof and all five controls were re-run, and the
intermediate receipt with the old expected count (UNEXPECTED 51 != 50) is kept. Iteration 23 grew the import again (51 → 52); proof, controls and binding were re-run.

## Latest receipts (checked in iteration 64)

The latest receipt of each kind, as `tools/census.py` resolves it: prove [20261116T173218Z-prove](../../results/sort_key/20261116T173218Z-prove/receipt.json), binding [20261116T173229Z-binding](../../results/sort_key/20261116T173229Z-binding/receipt.json), and the latest receipt for each of the 5 named controls in [results/sort_key/](../../results/sort_key/). A receipt this file calls "final" or "latest" above is the one current when that paragraph was written; later reruns supersede it.
