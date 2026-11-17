# W2 coverage.md snippet (iteration 56)

coverage.md has no rows for cypher_clauses or percentile (their scope lives in the model NOTES and the iteration
handoffs); only the aggregate_results row (coverage.md:697) changes.

## REPLACE coverage.md line 697 (exact old line below, then the new line)

OLD:
| [aggregate_results](models/aggregate_results/NOTES.md) | Raw selected rows/RETURN AST→unique groups/null/distinct/half-unit SUM and AVG contributors/typed scalar bridge/collection/full output→given order/page/public-name projection.62new queries=46proof+16rec,13unchanged imports;12producer controls,669comparisons,109upstream. | Actual SQL/JSON/IEEE/equality/metadata/codec/collation/sort remain framed. Native count Group/GroupOf/EmitGroups are inspected typed transcriptions with nonnull/pW1/key/order premises, not native-body verification. OPTIONAL synthetic fallback remains observed/partial. |

NEW:
| [aggregate_results](models/aggregate_results/NOTES.md) | Raw selected rows/RETURN AST→unique groups/null/distinct/half-unit SUM and AVG contributors/typed scalar bridge/collection/full output→given order/page/public-name projection.62new queries=46proof+16rec,13unchanged imports;12producer controls,669comparisons,109upstream. | Actual SQL/JSON/IEEE/equality/metadata/codec/collation/sort remain framed. Native count Group/GroupOf/EmitGroups are inspected typed transcriptions with nonnull/pW1/key/order premises, not native-body verification. OPTIONAL synthetic fallback remains observed/partial. Narrowed (iterations 54 and 56, review 53-55 F3; [NOTES](models/aggregate_results/NOTES.md#narrowed-scope-iterations-54-and-56)): group-key equality is a premise IRIS meets only for keys of one kind (bug-cyp-135/136), and `theorem_numeric_distinct_normalizes_int_and_whole_double` (count(DISTINCT) of 1 and 1.0 is one) is conditional on the open question query.aggregation.keys.numbers, not a guarantee under the provisional "two values" assumption. |

## Optional additions (if the parent keeps per-iteration rows; same three columns as the Iteration-13 table)

| [cypher_clauses](models/cypher_clauses/NOTES.md) | Iteration 56 adds section I: length/nodes/relationships of a named OPTIONAL path derived from the pattern and what the row bound; `theorem_unmatched_fixed_path_length_is_hops` (bug-cyp-146), general departure-exactly theorem, neighbor for bound and variable-length paths and a null anchor. 29 verified, 28/28 controls, binding AGREES 124. | A path projected through WITH and length() of a string are outside; inspected transcription of `_expr_fn_path_funcs`/`_vlp_path_sql`. |
| [percentile](models/percentile/NOTES.md) | Iteration 56 adds the answer type (`theorem_disc_over_ints_answers_float`, bug-cyp-147) and the p argument (`theorem_non_number_p_not_refused`, general `theorem_p_departs_exactly_on_non_numbers`, bug-cyp-148). 30 verified, 7/7 controls, binding AGREES 168. | The translator's FLOAT typing and `_float_expr_value` are one decision in the model; a literal null p rests on premise P-OS-EMPTY-ZERO; null-p intent (error or null) unsettled, both readings reject today's answers. |
