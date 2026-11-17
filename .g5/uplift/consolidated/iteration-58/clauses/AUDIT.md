# Iteration 58 W1: binding-integrity audit of the clause_combos crosswalk rows

Question per row labelled models / proves / witnesses in [crosswalk-rows.tsv](crosswalk-rows.tsv): would swapping or
weakening this member's actual decision break a theorem (a control that must fail) or the binding (a port mutation
or an observation that would no longer agree)? Controls and binding: the final run (prove `20261117T082328Z`,
controls `20261117T082335Z`..`20261117T082408Z`, binding `20261117T082514Z-binding`; [OBSERVED.md](OBSERVED.md)) (17 controls, each EXPECTED_FAIL; binding with 17 port mutations, one per control).
Rows labelled delegates / cites are not audited (their decision is not modeled here).

| # | block | member | formal item | relation | control that fails | binding detection | verdict |
|---|---|---|---|---|---|---|---|
| 1 | query.optional | `translator.py::_expr_aggregation` (count(b) over non-null) | `as_built_sql` | models | count-var-counts-rows (theorem_after_match_follows_rule, theorem_null_row_counts) | count-var-counts-rows (`A_after_a2_*_CountVar`, `A_leading_*`) | PASS |
| 2 | query.optional | `translator.py::_expr_aggregation` | `theorem_null_row_counts` | proves | count-var-counts-rows, sum-null-over-no-value, collect-null-over-no-value | same three | PASS |
| 3 | query.aggregation | `translator.py::_zero_if_null` | `theorem_after_match_follows_rule` | proves | sum-null-over-no-value | sum-null-over-no-value (`A_after_a2_*_Sum`, `A_leading_pure_nomatch_Sum`) | PASS |
| 4 | query.aggregation | `translator.py::_json_text_list_agg` | `theorem_after_match_follows_rule` | proves | collect-null-over-no-value (added in the final run for this row) | collect-null-over-no-value (`A_after_a2_*_Collect`) | PASS |
| 5 | query.optional | `translator.py::translate_return_clause` 30574-30582 | `theorem_leading_pure_follows_rule` | proves | leading-star-unpatched | leading-star-unpatched (`A_leading_pure_nomatch_CountStar`) | PASS |
| 6 | query.optional | `translator.py::_null_row_aggregate` | `null_row_aggregate` | models | null-row-count-var-one, null-row-sum-zero | same (`A_leading_grouped_nomatch_*`) | PASS |
| 7 | query.optional | `translator.py::_null_row_aggregate` | `theorem_leading_grouped_sum_is_null` | witnesses | null-row-sum-zero | null-row-sum-zero (`A_leading_grouped_nomatch_Sum`) | PASS |
| 8 | query.optional | `translator.py::translate_return_clause` 30780-30791 | `as_built_answer` | models | grouped-leading-uses-sql | grouped-leading-uses-sql | PASS |
| 9 | query.aggregation.keys | `translator.py::translate_return_clause` 30777 | `theorem_group_iff_bound_text` | proves | group-by-kind-column | group-by-kind-column (`B_*_groups`) | PASS |
| 10 | query.aggregation.keys | `translator.py::_expr_aggregation` 24431 | `group_key` | models | group-by-kind-column (the model's count(DISTINCT) shares the grouping key) | group-by-kind-column (`B_*_count_distinct`, observed separately) | PASS (shared key: a mutation of count(DISTINCT) alone is not separately modeled) |
| 11 | query.aggregation.keys | `translator.py::translate_return_clause` 30777 | `theorem_group_merges_kinds` | witnesses | group-by-kind-column, bool-bound-as-word | same (`B_int_true_*`, `B_zero_false_*`, `B_list_spelled_*`) | PASS |
| 12 | query.aggregation.keys | `translator.py::translate_return_clause` 30655-30671 | `theorem_distinct_flag_route_keeps_bool_apart` | proves | distinct-plain-on-flag | distinct-plain-on-flag (`B_int_true_distinct_rows`, `B_zero_false_distinct_rows`) | PASS |
| 13 | query.aggregation.keys | `translator.py::_unwind_bool_flag` | `route` | models | distinct-plain-on-flag (no flag = the plain item, exactly the control's replacement) | distinct-plain-on-flag | PASS (the route function itself is not mutated; dropping the flag is equivalent to the control) |
| 14 | query.aggregation.keys | `translator.py::_unwind_json_text` | `theorem_distinct_json_route_follows_rule` | proves | json-route-plain | json-route-plain (`B_list_spelled_distinct_rows`) | PASS |
| 15 | query.optional | `translator.py::translate_where_clause` | `placed_in_on` | models | condition-in-where (added in the final run for this row) | condition-in-where (every `C_*` that runs) | PASS |
| 16 | query.optional | `translator.py::translate_where_clause` 17128-17175 | `theorem_new_alias_only_keeps_row` | proves | condition-in-where; premise neighbors iris-refuses-any-or, iris-refuses-any-arith | condition-in-where, iris-refuses-any-* (`C_or_new_only`, `C_arith_new_only`, `C_mul_new_only`) | PASS |

The provider premise P-OUTER-ON (`refuses_p`) is labelled `cites`: it is IRIS's behavior, not a product member. Its
own controls (iris-accepts-or, iris-accepts-arith, iris-refuses-any-or, iris-refuses-any-arith, negation-ignored) and
port mutations are all detected; the binding's 15 condition shapes, 6 of them refused, fix it on the observed domain.

Relabelled before the final run: rows 4 and 15 had no control that broke on their own decision (collect's `[]` and the
ON placement); controls `collect-null-over-no-value` and `condition-in-where` were added so they stay `proves` /
`models` rather than being relabelled `cites`. No row fails in the final run.
