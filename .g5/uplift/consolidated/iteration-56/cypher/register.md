# W2 register snippets for bugs_issues.md (iteration 56)

Paste each entry verbatim into `.g5/Verus_verification/bugs_issues.md`. Placement: bug-cyp-146 in the **Medium** run,
after `bug-cyp-145`; bug-cyp-147 and bug-cyp-148 in the **Low** run, after `bug-cyp-139`. bug-cyp-149 (spare) unused.
No inherited entry needs an edit: bug-cyp-134's text already says the answer is read as a float, without a separate
finding; its "Observed" may gain the sentence at the end of this file (optional).

---

<a id="bug-cyp-146"></a>
### length(p) of a path an OPTIONAL MATCH did not bind answers the pattern's length instead of null

Severity: Medium · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 56)

Found by: independent review round 3 (review 53-55 F2, reviewer session `c68a5c59`, probe `rv55b … len_*`); [cypher_clauses](models/cypher_clauses/NOTES.md) section I `theorem_unmatched_fixed_path_length_is_hops`, general `theorem_path_fn_departs_exactly_on_unmatched_fixed_length`, neighbor `theorem_bound_or_varlen_path_follows_rule`; controls `fixed-length-from-row`, `varlen-length-from-pattern`, `anchor-null-ignored`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin, on an engine with the native executor off and one with it on ([probe](../uplift/consolidated/iteration-56/cypher/cypher-observed-20261117T065840Z.json) `fix1_un`, `fix2_un`; [binding](results/cypher_clauses/20261117T065639Z-binding/receipt.json) `I_fix1_unmatched_len`, `I_fix2_unmatched_len`, `I_fix1_unmatched_len_native_on`). Over `a1 → a2 → a3` written by `create_edge`, `MATCH (a {name: 'a3'}) OPTIONAL MATCH p = (a)-[:K]->(b) RETURN length(p), p IS NULL, nodes(p), relationships(p)` answers `1, true, null, null`; the two-hop pattern from `a2` answers `length(p)` = 2 with `p IS NULL` true. Passing neighbors: a bound path answers its own length (1, 2); a variable-length `OPTIONAL MATCH p = (a)-[:K*1..2]->(b)` with no match answers null and with matches 1 and 2; a null anchor (`OPTIONAL MATCH (a {name: 'none'}) OPTIONAL MATCH p = ...`) answers null; `length(null)` answers null. OPTIONAL MATCH never runs native, so both engines answer the same.

Expected: [query.optional](../ontology/features/cypher.g5.md#query.optional) ("later expressions read them as null") and openCypher: a path the OPTIONAL MATCH did not bind is null, and `length(null)` is null.

Observed: the translator's path-function branch answers `length()` of a fixed pattern with the constant `len(pattern.relationships)` (`translator.py:28797-28802`), never reading the row; `nodes()` and `relationships()` read the row's aliases and so are null, and a variable-length path reads its row value (`_vlp_path_sql`). Only a null anchor (`optional_null_row_unconditional`, 28788-28790) answers NULL.

Consequence: a report that counts or filters on `length(p)` after an OPTIONAL MATCH treats rows with no path as paths of full length (for example `WHERE length(p) > 0` keeps every unmatched row, and `sum(length(p))` counts them), silently. Repair proposal (not implemented): for a path bound by an OPTIONAL MATCH, emit `CASE WHEN <the path's first edge alias> IS NULL THEN NULL ELSE h END`, as `nodes(p)` already yields null. Preserve: the constant for a path bound by a plain MATCH (always bound), the variable-length branch, the null-anchor branch. Distinguishing case: the binding's `I_fix1_unmatched_len` against `I_fix1_matched_len`; the control `fixed-length-from-row` checks the direction in the model only.

---

<a id="bug-cyp-147"></a>
### percentileDisc over integers answers a float

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 56)

Found by: owned as built in iteration 53 ("Today both answer a float"); registered after independent review round 3 (review 53-55 minor "percentile result type"); [percentile](models/percentile/NOTES.md) `theorem_disc_over_ints_answers_float`, neighbor `theorem_float_and_cont_kinds_follow_rule`; control `disc-keeps-input-kind`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([probe](../uplift/consolidated/iteration-56/cypher/cypher-observed-20261117T065840Z.json) `pct_int`, `pct_flt`, `min_int`; [binding](results/percentile/20261117T065550Z-binding/receipt.json) `kind:unwind:int`, `kind:match:int`). `UNWIND [10, 20, 30, 40] AS x RETURN percentileDisc(x, 0.5)` answers `20.0` (a Python float), also over stored integers. Passing neighbors: `percentileCont` answers `25.0` (a float, as it should); over floats `percentileDisc` answers `1.5`; `min(x)` and `max(x)` over the same integers answer `10` and `20` as integers, on both engines.

Expected: [query.functions.percentile](../ontology/features/cypher.g5.md#query.functions.percentile): `percentileDisc` answers one of the values, so it keeps their type; Neo4j answers `20` over integers (openCypher TCK `Aggregation6` compares percentileDisc results over integers as integers).

Observed: `_scalar_statistical` emits `Percentile_PDISC(JSON_ARRAYAGG(CAST(x AS DOUBLE)), p)` and the translator types the column FLOAT, so `_float_expr_value` (`_engine/query.py:1243-1260`) turns every answer into a float.

Consequence: a client comparing the answer with a stored integer, or using it as a list index or a `LIMIT`, gets a float. Repair proposal (not implemented): type the percentileDisc column from its argument's static type (int for an integer property), leaving percentileCont FLOAT. Preserve: percentileCont's float, the `NumberOutOfRange` refusal, null for no values; the iteration-55 text-spelling read under driver 5.4.1.

---

<a id="bug-cyp-148"></a>
### A percentile p that is not a number: null raises a raw Python TypeError, text and booleans are converted, a literal null answers p = 0

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 56)

Found by: independent review round 3 (review 53-55 minor "null percentile parameter", probe `pct_param_null`, `pct_param_str`); the other kinds by the iteration-56 probe; [percentile](models/percentile/NOTES.md) `theorem_non_number_p_not_refused`, general `theorem_p_departs_exactly_on_non_numbers`; controls `null-param-refused`, `literal-null-refused`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([probe](../uplift/consolidated/iteration-56/cypher/cypher-observed-20261117T065840Z.json) `pct_p_*`, `pct_lit_null`; [binding](results/percentile/20261117T065550Z-binding/receipt.json) `p:*`). Over `UNWIND [10, 20, 30] AS x RETURN percentileDisc(x, $p)`: `$p` = null raises `TypeError: float() argument must be a string or a real number, not 'NoneType'` out of `execute_cypher` (percentileCont the same); `$p` = `'x'` raises `ValueError: could not convert string to float`; `$p` = `'0.5'` answers 20.0; `$p` = true answers 30.0 (p = 1); a literal `percentileDisc(x, null)` answers 10.0 (p = 0). Passing neighbors: `$p` = 0.5 and a literal 0.5 answer 20.0; a missing `$p` is "Undefined variable: p".

Expected: [query.functions.percentile](../ontology/features/cypher.g5.md#query.functions.percentile): `p` is a number from 0 to 1; anything else fails as a Cypher argument error (openCypher does not say whether a null p fails or answers null; both readings reject a raw Python exception and the p = 0 answer).

Observed: `_scalar_statistical` passes a `$p` parameter through Python `float(context.input_params[name])` (`translator.py:28595-28603`) during translation, outside the error handling that turns translation errors into Cypher errors; a literal null is pasted as SQL `NULL`, which `IVG.Percentile.PDISC` reads as `""` and so as 0 in its range check and index (provider premise P-OS-EMPTY-ZERO, observed).

Consequence: a client passing a null or text percentile gets an untyped Python exception instead of a Cypher error, or a silent answer for a different percentile. Repair proposal (not implemented): accept only an int or float (not bool) parameter and raise `InvalidArgumentType` otherwise; refuse a literal null the same way (or answer null, by the decision on intent). Preserve: numeric parameters and literals, `NumberOutOfRange` for numbers outside 0 to 1, the missing-parameter error.

---

Optional sentence for bug-cyp-134 "Observed" (inherited, not required): "The answer's type, a float also over integers, is registered separately as [bug-cyp-147](#bug-cyp-147)."
