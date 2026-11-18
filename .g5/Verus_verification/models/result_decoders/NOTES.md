# One stored value through the result decoders (result_decoders)

Product `3eaa79cf`, unchanged. Iteration 58 (W62). Predictions frozen before the deciding source was read:
[w62-PAIRS.md](../../../uplift/consolidated/iteration-58/w62-PAIRS.md) (commit `2429a0a3`), rows D1-D9. Owners:
[query.values](../../../ontology/features/cypher.g5.md#query.values),
[query.optional](../../../ontology/features/cypher.g5.md#query.optional),
[query.shadow](../../../ontology/architecture/query-execution.g5.md#query.shadow),
[access.bolt.graph_values](../../../ontology/features/client-interfaces.g5.md#access.bolt.graph_values).
An as-built Verus transcription with native agreement; **not** executable-body verification. Bundled vstd only; no
`assume`, `admit` or `external_body`. Outcomes: [OBSERVED.md](../../../uplift/consolidated/iteration-58/decoders/OBSERVED.md).

## What each part derives, from which input

| Part | Deciding input | Derived decision | Reader |
|---|---|---|---|
| writer | the written value's kind | `store`: an int/float as an IRIS number, a boolean as `'true'`/`'false'`, `''`, `[]`/`{}` as JSON text, none as no row | `rdf_props.val` |
| K1 column kind | the RETURN item's shape | `reads_node_value` (`_reads_node_value` 7644-7678): property, WITH of a property, RETURN coalesce -> typed; CASE, WITH coalesce -> not | `typed_value_columns`, `prop_text_expr_columns` |
| K2 SQL form | the shape (via K1) | `sql_form`: `CY_TYPED`, the WITH stage's `CAST(... AS VARCHAR)` for coalesce, else raw | the column's SQL |
| driver | stored cell, SQL form, IRIS driver | `sql_value`: a raw IRIS number is a number under 5.3.2, text under 5.4.1; `CY_TYPED` marks it; a CAST is text; no row is null | the Python value in the row |
| decoders | the column kind and the value | `dec_typed` (read_prop_value), `dec_prop_text` (parse_prop_text), in `_finish_sql_result` order | the engine's row |
| K3 comparison | stored cell, constant | `gt_sql` 1/0/NULL and `dec_bool_expr` (`_bool_expr_value`) | boolean or null |
| K4 OPTIONAL node | whether the node is bound | `labels_col`: `COALESCE(JSON_ARRAYAGG(label), '[]')`; Bolt rebuilds a null node from a null id | `b_labels` / Bolt `b` |

## Claims (each verified; 12 obligations)

- `theorem_typed_roundtrip`: for every written value of every kind and both drivers, a typed shape answers the value
  written (D3, D8; RETURN coalesce valid neighbor).
- `theorem_property_reads_roundtrip`: the same, per shape, for the property read, the WITH of a property and the RETURN
  coalesce (the K1 decision of each shape is not assumed).
- `theorem_null_row_every_decoder`: a missing value is null for every shape, SQL form, driver and decoder (D2 `b.x`).
- `theorem_with_coalesce_number_is_text` (bug-cyp-155): a WITH coalesce column answers a stored number as its text,
  both drivers.
- `theorem_case_bool_is_text`, `theorem_case_container_is_text`, `theorem_case_number_by_driver` (bug-cyp-156): a CASE
  column answers booleans, lists and maps as text under both drivers and numbers as text under 5.4.1 only.
- `theorem_strings_held_everywhere`: plain and empty strings keep their value in every shape (valid neighbor).
- `theorem_compare_is_boolean_or_null`: a comparison column is the boolean for a stored number, null for no value (D6).
- `theorem_optional_node_labels` (bug-plt-135): an unbound node's labels column is `'[]'` at Python, API and TX; null at Bolt.
- `theorem_probe_rows`: the probe's observed values.

## Value domains and exclusions

- Numbers: all mathematical integers; floats as integer tenths (the decimal spelling `str(t/10)` in the binding port);
  NaN, infinities, integers past 64 bits and Decimal results are outside.
- Strings: abstract plain strings that spell no boolean, number, list or map (`Plain(nat)`), and `''`. A stored string
  spelling `true` or a list is the registered KNOWN_ISSUES behavior and outside.
- Lists and maps: only `[]` and `{}`; nested containers outside (D4 observed only).
- CASE and coalesce are abstracted to "the chosen branch's stored value": the branch selection itself is SQL's and not
  modeled; both branches are node properties.
- Node values written by `create_node` only; Cypher-written values, relationship properties
  (`_decode_rel_prop_text_columns`), and the numeric, map-text and mixed decoders (no modeled kind reaches them) are
  outside. Readers: Bolt, API and TX are modeled as carrying the Python value unchanged for these kinds (observed).
- The native executor's own rows are outside (D8 observed equal only).
- Providers: P-DRV-NUM (IRIS driver 5.3.2 hands a raw IRIS number as a number, 5.4.1 as text; observed in the binding
  for both drivers), P-IRIS-CAST (CAST to VARCHAR yields the number's text, observed `'3'`, `'2.5'`).

## Controls (17, each EXPECTED_FAIL in its named functions)

`case-typed`, `with-coalesce-typed` (K1); `coalesce-cast-gone` (K2); `driver-541-native` (driver provider);
`no-mark-decode`, `bool-text-ignored` (decoders); `no-prop-text`, `case-prop-text` (prop-text column decision);
`bool-expr-off`, `gt-text-zero` (K3); `missing-not-null` (null row); `labels-null` (K4); added after the crosswalk
audit: `ret-coalesce-untyped` (`_is_typed_coalesce`), `with-prop-untyped` (`_is_node_value_var`), `typed-emitted-raw`
(`translate_return_clause` emission), `no-json-decode` (`decode_json_list_map`), `bit-one-false` (`_bool_expr_value`). See [model.json](model.json).

## Binding

[binding.py](binding.py): nine `create_node` values x six value shapes, a comparison column and the unbound OPTIONAL
node, at execute_cypher, Bolt, `/api/cypher`, tx/commit, under IRIS drivers 5.3.2 and 5.4.1 (subprocess), compared
with an independent Python port of this file. Receipt `results/result_decoders/20261117T082201Z-binding`: AGREES 480/480;
each of the 17 port mutations (one per control) changes at least one prediction away from the observation; a tampered
observation (`5.3.2_PY_WithCoalesce_int` set to the int 3) is detected.

## Latest receipts (checked in iteration 64)

The latest receipt of each kind, as `tools/census.py` resolves it: prove [20261117T082943Z-prove](../../results/result_decoders/20261117T082943Z-prove/receipt.json), binding [20261117T083143Z-binding](../../results/result_decoders/20261117T083143Z-binding/receipt.json), and the latest receipt for each of the 17 named controls in [results/result_decoders/](../../results/result_decoders/). A receipt this file calls "final" or "latest" above is the one current when that paragraph was written; later reruns supersede it.
