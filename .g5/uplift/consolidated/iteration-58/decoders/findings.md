# Iteration 58 W2 (result decoders): findings

Three new entries (bug-cyp-155, -156, bug-plt-135); bug-cyp-157 to -160 and bug-plt-136 to -138 are unused. Saved by
the builder from W2's report (the harness refused the worker's write). Checked first: `bugs_issues.md` (bug-cyp-138 is
UNION storage text; bug-plt-121 to -126 are Bolt/HTTP shapes; none covers CASE, a WITH coalesce column or the null
OPTIONAL node's label/property columns) and `docs/KNOWN_ISSUES.md`.

<a id="bug-cyp-155"></a>
### A WITH column of coalesce() answers a stored number as its text: WITH coalesce(n.v, n.s) AS x RETURN x gives '3' for 3 and '2.5' for 2.5

Severity: Medium · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 58)

Found by: iteration 58 W62 frozen prediction D1 neighbor B (missed, [PAIRS](../w62-PAIRS.md)); [result_decoders](../../../../Verus_verification/models/result_decoders/NOTES.md) `theorem_with_coalesce_number_is_text`; valid neighbor `theorem_property_reads_roundtrip`; controls `with-coalesce-typed` (the repair), `coalesce-cast-gone`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin, IRIS drivers 5.3.2 and 5.4.1, all four readers (Python `execute_cypher`, Bolt with neo4j 6.4.1, `/api/cypher`, `/db/neo4j/tx/commit`) ([5.3.2](decoders-observed-5.3.2-20261117T080853Z.json), [5.4.1](decoders-observed-5.4.1-20261117T080939Z.json) `D1_coalesce`; [binding](../../../../Verus_verification/results/result_decoders/20261117T082201Z-binding/receipt.json) `*_WithCoalesce_*`). Stored `3`, `2.5`, `true` come back as `'3'`, `'2.5'`, `'true'`; `RETURN coalesce(...)` without the WITH returns them typed.

Expected: openCypher: coalesce returns its first non-null argument unchanged. [query.values](../../../../ontology/features/cypher.g5.md#query.values): "A node property read preserves its stored numeric type".

Observed: in the WITH stage, `_scalar_coalesce` (`translator.py:24455-24470`) casts the first argument to VARCHAR. The final RETURN emits `x AS x` (`translator.py:30690-30691`), because `_reads_node_value` (`7644-7678`) recognises a WITH variable only when it is bound to a bare property (`_is_node_value_var` 7592), and `_is_typed_coalesce` (7620-7641) applies only to RETURN items. No decoder touches `x`.

Consequence: an ordinary `WITH coalesce(...)` silently returns numbers and booleans as strings on every reader and driver.

Repair proposal (not implemented): treat a WITH variable bound to a typed coalesce as a node value (add it to `prop_text_vars`) and drop the stage CAST, so the RETURN reads it through `CY_TYPED` and `parse_prop_text`. Preserve: RETURN coalesce typing, and the CASTs in WHERE. Distinguishing case: `*_WithCoalesce_int` returns `3` after the repair.

<a id="bug-cyp-156"></a>
### A CASE column answers a stored boolean as 'true', a stored list or map as its JSON text, and, with IRIS driver 5.4.1, a stored number as its text

Severity: Medium · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 58)

Found by: iteration 58 W62 frozen prediction D1 A (missed, [PAIRS](../w62-PAIRS.md)); [result_decoders](../../../../Verus_verification/models/result_decoders/NOTES.md) `theorem_case_bool_is_text`, `theorem_case_container_is_text`, `theorem_case_number_by_driver`; neighbor `theorem_strings_held_everywhere`; controls `case-typed`, `case-prop-text`, `driver-541-native`.

Reproduced by: **E2E reproduced**, both drivers, all four readers plus the native-default engine (`D1_case`, `D1_case_noid`, `D1_ret_case`; [binding](../../../../Verus_verification/results/result_decoders/20261117T082201Z-binding/receipt.json) `*_RetCase_*`, `*_WithCase_*`). Under 5.3.2: `3`, `2.5`, `'txt'`, `'true'`. Under 5.4.1: `'3'`, `'2.5'`, `'txt'`, `'true'`. A stored `[1, 2]` comes back as `'[1, 2]'`.

Expected: openCypher: CASE returns the chosen branch's value with its type. [query.values](../../../../ontology/features/cypher.g5.md#query.values): `CY_TYPED` decides the type rather than the driver's column type.

Observed: `_reads_node_value` (`translator.py:7644-7678`) has no case for CASE expressions, so the raw `p.val` is emitted (`30690-30691`) and is in no decoder list (`query.py:332-349`). Driver 5.4.1 hands raw IRIS numbers to Python as text (`prop_values.py:204-212`).

Consequence: silently wrong types on every reader; numbers are wrong on the current IRIS driver.

Repair proposal (not implemented): type a CASE whose branches are all node values or scalar literals/parameters through `CY_TYPED(CASE ... END)` plus `prop_text_expr_columns`, including through a WITH. Preserve: string literal branches.

<a id="bug-plt-135"></a>
### An OPTIONAL MATCH node with no match answers labels '[]' and properties '[]' at execute_cypher, /api/cypher and tx/commit

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 58)

Found by: iteration 58 W62 frozen prediction D2 (partial, [PAIRS](../w62-PAIRS.md)); [result_decoders](../../../../Verus_verification/models/result_decoders/NOTES.md) `theorem_optional_node_labels`; control `labels-null`.

Reproduced by: **E2E reproduced**, both drivers (`D2_opt`, `D2_with`; [binding](../../../../Verus_verification/results/result_decoders/20261117T082201Z-binding/receipt.json) `*_Opt_labels`). The row is `[i, null, '[]', '[]', null]`; Bolt returns `b` as null.

Expected: [query.optional](../../../../ontology/features/cypher.g5.md#query.optional): the pattern's new variables are null.

Observed: `labels_subquery` (`translator.py:1282-1289`) uses `COALESCE(JSON_ARRAYAGG(label), CAST('[]' ...))`, and the properties column also comes back `'[]'`.

Consequence: a caller that tests `b_labels` or `b_props` instead of `b_id` sees a node with no labels where there is no match.

Repair proposal (not implemented): return NULL for those columns when the node id is NULL. Preserve: a bound node with no labels still returns `'[]'`.
