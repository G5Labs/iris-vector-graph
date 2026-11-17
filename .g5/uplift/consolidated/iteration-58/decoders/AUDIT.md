# Iteration 58 W2: binding-integrity audit of the result_decoders crosswalk rows

Question per row labelled models / proves / witnesses in [crosswalk-rows.tsv](crosswalk-rows.tsv): would swapping or
weakening this member's own decision break a theorem (a control that must fail) or the binding (a port mutation whose
predictions no longer agree with the observations)? Final runs: prove `20261117T082127Z-prove` PASS 12; 17 controls `20261117T082129Z`..`20261117T082152Z`, all
EXPECTED_FAIL; binding `20261117T082201Z-binding` AGREES 480, 17/17 port mutations (one per control) detected, tamper detected. Rows labelled delegates / cites are not
audited (their decision is not modeled).

First pass (12 controls, `20261117T081423Z`..`081439Z`, binding `20261117T081535Z`) failed four rows: `_is_typed_coalesce`,
`_is_node_value_var`, `translate_return_clause` (emission), `decode_json_list_map` and `_bool_expr_value`'s own body had no
control or mutation that swaps their decision. Five controls and mutations were added (`ret-coalesce-untyped`,
`with-prop-untyped`, `typed-emitted-raw`, `no-json-decode`, `bit-one-false`), and one row was relabelled (below).

| # | block | member | formal item | relation | control that fails | binding detection | verdict |
|---|---|---|---|---|---|---|---|
| 1 | query.values | `translator.py::_reads_node_value` | `reads_node_value` | models | case-typed, with-coalesce-typed, ret-coalesce-untyped, with-prop-untyped | same-named mutations (`*_RetCase_*`, `*_WithCoalesce_*`, `*_RetCoalesce_btrue`, `5.4.1_*_WithProp_int`) | PASS |
| 2 | query.values | `translator.py::_reads_node_value` | `theorem_case_number_by_driver` | proves | case-typed, driver-541-native | case-typed, driver-541-native (`5.4.1_*_RetCase_int`) | PASS |
| 3 | query.values | `translator.py::_is_typed_coalesce` | `reads_node_value` | models | ret-coalesce-untyped (theorem_property_reads_roundtrip, theorem_probe_rows) | ret-coalesce-untyped (`*_RetCoalesce_btrue`, 5.4.1 numbers) | PASS (after control added) |
| 4 | query.values | `translator.py::_is_node_value_var` | `reads_node_value` | models | with-prop-untyped (theorem_property_reads_roundtrip) | with-prop-untyped (`*_WithProp_btrue`, `*_WithProp_list0`) | PASS (after control added) |
| 5 | query.values | `translator.py::_scalar_coalesce` | `sql_form` | models | coalesce-cast-gone | coalesce-cast-gone (`5.3.2_*_WithCoalesce_int`) | PASS |
| 6 | query.values | `translator.py::_scalar_coalesce` | `theorem_with_coalesce_number_is_text` | proves | coalesce-cast-gone, with-coalesce-typed | coalesce-cast-gone, with-coalesce-typed | PASS |
| 7 | query.values | `translator.py::translate_return_clause` | `sql_form` | models | typed-emitted-raw (theorem_typed_roundtrip) | typed-emitted-raw (`5.4.1_*_Prop_int`, `_float`) | PASS (after control added) |
| 8 | query.values | `query.py::_finish_sql_result` | `decode` | models | no-prop-text, case-prop-text (which decoder applies); the order typed -> bool-text is answer-neutral on the modeled kinds (disjoint inputs: marked/JSON text vs 'true'/'false'), stated | no-prop-text, case-prop-text | PASS (order: stated neutral) |
| 9 | query.values | `query.py::_decode_typed_value_columns` | `dec_typed` | models | no-mark-decode, no-json-decode | no-mark-decode, no-json-decode | PASS |
| 10 | query.values | `query.py::_decode_typed_value_columns` | `theorem_typed_roundtrip` | proves | no-mark-decode, no-json-decode, typed-emitted-raw | same | PASS |
| 11 | query.values | `prop_values.py::read_prop_value` | `dec_typed` | models | no-mark-decode, no-json-decode | same | PASS |
| 12 | query.values | `prop_values.py::decode_typed_text` | `dec_typed` | models | no-mark-decode | no-mark-decode (`*_Prop_int`, `_float`) | PASS |
| 13 | query.values | `prop_values.py::decode_json_list_map` | `dec_typed` | models | no-json-decode | no-json-decode (`*_Prop_list0`) | PASS (after control added) |
| 14 | query.values | `query.py::_decode_bool_text_columns` | `decode` | models | no-prop-text, case-prop-text | same | PASS |
| 15 | query.values | `prop_values.py::parse_prop_text` | `dec_prop_text` | models | bool-text-ignored | bool-text-ignored (`*_Prop_btrue`) | PASS |
| 16 | query.values | `query.py::_bool_expr_value` | `dec_bool_expr` | models | bit-one-false; bool-expr-off removes its application | bit-one-false (`*_Gt_int`), bool-expr-off | PASS (after control added) |
| 17 | query.values | `query.py::_bool_expr_value` | `theorem_compare_is_boolean_or_null` | proves | bit-one-false, bool-expr-off, gt-text-zero | same | PASS |
| 18 | query.optional | `translator.py::labels_subquery` | `labels_col` | models | labels-null | labels-null (`*_PY_Opt_labels`, API, TX) | PASS |
| 19 | query.optional | `translator.py::labels_subquery` | `theorem_optional_node_labels` | witnesses | labels-null | labels-null | PASS |
| 20 | query.optional | `query.py::_decode_typed_value_columns` | `theorem_null_row_every_decoder` | was proves | missing-not-null changes the SQL value, not this decoder's decision; no control swaps the decoder's own null pass-through | none for the decoder itself | **relabelled cites** |
