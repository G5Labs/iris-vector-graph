# W2 binding-integrity audit (iteration 56)

Question per row: would swapping or weakening this member's actual decision break a theorem or the binding?

| Member | Formal item | Relation | Swap / weaken the member's decision | Breaks? | Verdict |
|---|---|---|---|---|---|
| `translator.py::_expr_fn_path_funcs` 28797-28802 | `theorem_unmatched_fixed_path_length_is_hops` | proves | read a fixed path's length from the row (null when unbound) | yes: control `fixed-length-from-row` fails 2 theorems; binding mutation `fixed_length_from_row` 3 cases | active (decision) |
| `translator.py::_expr_fn_path_funcs` 28788-28815 | `theorem_bound_or_varlen_path_follows_rule` | proves | drop the null-anchor branch | yes: control `anchor-null-ignored`; binding `anchor_null_ignored` 1 case | active (same member, second role) |
| `translator.py::_vlp_path_sql` 28701-28725 | `theorem_bound_or_varlen_path_follows_rule` | proves | answer a var-length length from the pattern instead of the row's `l` | yes: control `varlen-length-from-pattern`; binding `varlen_length_from_pattern` 1 case | active (decision; new member) |
| `translator.py::_scalar_statistical` 28595-28603 | `theorem_non_number_p_not_refused` | proves | refuse a non-number p (type check before float()) | yes: control `null-param-refused`; binding `null-param-refused` 1 case | active (decision) |
| `translator.py::_scalar_statistical` 28616-28617 | `theorem_disc_over_ints_answers_float` | proves | keep the input type (no CAST AS DOUBLE / FLOAT column) | yes: control `disc-keeps-input-kind`; binding `disc-keeps-input-kind` 2 cases | active (decision, shared with the reader below) |
| `_engine/query.py::_float_expr_value` 1243-1260 | `theorem_disc_over_ints_answers_float` | proves | pass an int through unchanged | yes at the binding (`kind:*` would read int); in the model the translator's typing and this reader are one constant decision (`cast_kind`), so the control does not separate them | active (reader; shared decision named) — new member |
| `translator.py::_scalar_statistical` 28570-28618 (row 899) | `pdisc` | models → **delegates** | swapping the emitter's forwarding leaves pdisc's theorems untouched (the index rule is PDISC's) | no | relabeled delegates (counted through the two rows above) |
| `Percentile.cls::PDISC`, `PCONT`, `SortArray`, `SqlProcs::PercentilePDISC/PCONT` | unchanged | unchanged | not named by the review; unchanged | — | unchanged |
| `Exec.cls::GroupOf` (aggregate_results row) | `theorem_key_enumeration_complete_unique` | models | key equality is a premise; the theorem is narrowed, the member is also bound by `cypher_clauses::theorem_paths_disagree_exactly_on_marked_text` (proves) | n/a (narrowing, not a new row) | unchanged; claim narrowed in NOTES and owner metadata |

Net effect expected on member_reach: + `_expr_fn_path_funcs`, + `_vlp_path_sql`, + `_float_expr_value` (if not already bound elsewhere); `_scalar_statistical` stays bound (now by two decision rows instead of the emitter row).
