# Cypher clauses over API-written data, default mode and parameters

Product `3eaa79cf`, unchanged. Iteration 54 (continuation, W59). Predictions frozen from openCypher (TCK), the owners
and the docs before the deciding source was read:
[clauses-PAIRS.md](../../../uplift/consolidated/iteration-54/clauses-PAIRS.md) (commit `6fd28893`). Owners (new):
[query.aggregation.keys](../../../ontology/features/cypher.g5.md#query.aggregation.keys),
[.arithmetic](../../../ontology/features/cypher.g5.md#query.aggregation.arithmetic),
[query.union](../../../ontology/features/cypher.g5.md#query.union),
[query.paging](../../../ontology/features/cypher.g5.md#query.paging),
[query.functions.path_elements](../../../ontology/features/cypher.g5.md#query.functions.path_elements),
[query.writes.delete](../../../ontology/features/cypher.g5.md#query.writes.delete),
[query.optional](../../../ontology/features/cypher.g5.md#query.optional).

## What the model decides, and from what

Every section takes the query's shape or the value's provenance as input and derives the translator's choice from it;
no choice is a parameter.

- **A. Grouping and distinctness keys** (`key_of`, `together`). Inputs: the executor (SQL path or native), the operator
  (grouping key, `count(DISTINCT)`, `RETURN DISTINCT`) and two stored values (kind, stored text). The SQL path compares
  the stored text for grouping and `count(DISTINCT)` (`translate_return_clause` 30777, `_expr_aggregation` 24431) and
  the `CY_TYPED` marked text for `RETURN DISTINCT` (30676); the native executor compares the keys' `$List`
  (`Exec.GroupOf`/`KeyValues`). Storage marks (`mark`): N for an integer, D for a double, none for strings, booleans
  and lists (query.values).
- **B. Arithmetic over aggregates** (`column_type`, `answered`). Input: the RETURN column's AST shape (a bare sum, or
  one operator over two operands, each a literal, a property, `count`, `avg`, or `sum`/`min`/`max` of a property or
  literal). The type follows `_numeric_static_type`/`_arith_operand_type` (a bare property is `'int'`); an `'int'`
  column is read by `_int_expr_value` as `int(round(v))`.
- **C. UNION** (`union_dec`, `read`, `union_merges`). Input: each branch's column decoder. `_tts_union_branches` keeps
  only the boolean mark when every branch has it; the reader then leaves a `CY_TYPED` marked text undecoded. IRIS
  removes duplicate rows by raw value; a boolean literal is the number 1 or 0.
- **D. SKIP/LIMIT** (`as_built_page` vs `rule_page`). Input: how the value is written (an integer literal) or the
  parameter's kind and value. `_resolve_pagination_value`.
- **E. A whole-label count as a UNION branch** (`shortcut`, `prepares`). Input: the branch's shape and whether it is in a
  UNION. The guard of `_lone_label_count` reads the branch copy's emptied `union_queries`; `_ensure_from` appends a
  second FROM to its one-line SELECT.
- **F. startNode/endNode** (`reads_existing_column`). Input: how the relationship variable is bound (a matched edge or
  an element of `relationships(p)`) and the function. `_expr_fn_node_funcs`.
- **G. DELETE** (`as_built_delete` vs `rule_delete`). Input: DETACH or not and the node's outgoing and incoming edge
  counts in its graph. `translate_delete_clause` and `execute_transaction`'s sentinel.
- **H. A WHERE inside OPTIONAL MATCH** (`placed_in_on`, `outer_guarded`, `as_built_opt` vs `rule_opt`). Input: the
  condition's shape (what it reads and how) and whether the earlier node lacks the property. `translate_where_clause`
  pushes the condition into the optional join's ON; `_expr_property_reference` adds the structural guard for an earlier
  variable's guardable read to the query's own WHERE; `_null_rejecting_refs` decides which reads are guardable.
  Provider premise P-OUTER-ON: IRIS 2026.1 refuses (-94) an ON with IVG's arithmetic over an earlier left-joined
  property, or an OR of it with the optional side's correlated read (observed; its exact boundary is not characterized).

## Value domains and exclusions

- A: kinds Int, Str, Bool, List (Float is represented for its mark only). The rule claim excludes Float (whether 1 and
  1.0 are one group is the [open question](../../open_questions.md#query.aggregation.keys.numbers)) and the documented
  collision of a string with a boolean or list of the same text (KNOWN_ISSUES). Values read from an `UNWIND` of a list
  are **not** in the model: their keys depend on `CY_LIST_KINDS` flags (observed: `[1, '1']` one group and one DISTINCT
  row; `[1, true]` one group, two DISTINCT rows) and are observation-only.
- B: totals in half units (multiples of 0.5), the probes' domain; any integer h. Overflow, other fractions and binary64
  rounding are excluded. `min`/`max` of a float property beside an integer literal is typed `'int'` by the same rule
  (`theorem_sum_of_property_sums_is_int_column`'s second clause); its value effect is observed only for `min(n.f) * 2`.
- C: one stored integer column against literal and typed branches; floats, lists and relationship text are observed by
  the probes, not separately modeled (`Raw::Marked` covers the D mark the same way).
- D: integer literals and parameter kinds Missing, Null, Int, Float (whole or not), Str (numeric or not), Bool. A
  non-integer literal (`LIMIT 1.5`) is observed only.
- E, F, G: the shapes named; G counts edges in the node's own graph (the cross-graph neighbor is bound).
- H: seven condition shapes over one hop with no passing match; multi-hop OPTIONAL groups, named paths and
  variable-length OPTIONAL hops are excluded.

## Theorems (26 verified; no imports)

As-built departures: `theorem_sql_group_merges_number_and_its_text(t)` and the general
`theorem_paths_disagree_exactly_on_marked_text(a, b)`, `theorem_sql_group_and_distinct_disagree_on_marked_text(a, b)`
([bug-cyp-135](../../bugs_issues.md#bug-cyp-135), [bug-cyp-136](../../bugs_issues.md#bug-cyp-136));
`theorem_sum_of_property_sums_is_int_column`, `theorem_int_column_loses_any_half(h)` (every odd h),
`theorem_probe_totals` ([bug-cyp-137](../../bugs_issues.md#bug-cyp-137)); `theorem_union_answers_marked_text(t, rest)`,
`theorem_union_dedup_by_raw(n)` ([bug-cyp-138](../../bugs_issues.md#bug-cyp-138));
`theorem_non_integer_parameter_used(i, b, v)` ([bug-cyp-139](../../bugs_issues.md#bug-cyp-139));
`theorem_label_count_branch_fails` ([bug-cyp-140](../../bugs_issues.md#bug-cyp-140));
`theorem_path_element_endpoints_fail` ([bug-cyp-141](../../bugs_issues.md#bug-cyp-141));
`theorem_outer_arith_or_refused(m)` ([bug-cyp-142](../../bugs_issues.md#bug-cyp-142), conditional on P-OUTER-ON);
`theorem_outer_guard_drops_row` ([bug-cyp-143](../../bugs_issues.md#bug-cyp-143)).
Agreeing neighbors: `theorem_sql_return_distinct_keeps_kinds`, `theorem_native_group_follows_rule(a, b)`,
`theorem_float_operand_or_bare_sum_keeps_value(h, a)`, `theorem_whole_total_unchanged(h)`,
`theorem_single_query_decodes`, `theorem_all_bool_union_stays_bool`, `theorem_integer_and_fraction_follow_rule(i, v)`,
`theorem_count_alone_and_other_branches_prepare`, `theorem_type_and_matched_endpoints_work`,
`theorem_delete_follows_rule(detach, out, in)`, `theorem_incoming_only_refused(in)`, `theorem_opt_neighbors_follow_rule(m)`.

## Controls (25, all EXPECTED_FAIL; [receipts](../../results/cypher_clauses/))

Repairs that leave their neighbors verified: `group-by-typed`, `prop-default-unknown`, `union-keeps-decoders`,
`page-int-only`, `count-guard-sees-union`, `shortcut-newline-from`, `endpoint-reads-json`, `opt-guard-in-on`. Decisive guard or effect
removed: `return-distinct-text`, `native-text-key`, `float-literal-int`, `int-read-exact`, `union-drops-bool`,
`typed-read-plain`, `page-no-negative-check`, `page-no-fraction-check`, `ensure-from-always`, `type-reads-alias`,
`delete-outgoing-only`, `delete-no-check`, `range-guarded`, `opt-cond-in-where`. Provider flips: `int-unmarked` (storage
without the N mark), `bool-literal-text` (IRIS giving a boolean literal as text), `iris-accepts-outer-on` (P-OUTER-ON).

## Binding

[binding.py](binding.py): 112 cases on the fixture, data written by `create_node`/`create_edge`, through
`execute_cypher` (SQL path) and `_try_native` on an engine with the native executor on (it accepted all ten grouping
reads), compared with a port of the spec: **AGREES**
([receipt](../../results/cypher_clauses/20261117T060402Z-binding/receipt.json)); each of the 25 mutations is detected
(1 to 8 cases each) and altering the observed `B_b13_sumv_plus_sumf` to the exact 13 half units is detected. DELETE cases
read the result back through `get_node` and the native walk over `^KG` (adjacency). The raw probes behind the
predictions are [clauses_probe.py](../../../uplift/consolidated/iteration-54/clauses_probe.py) and
[clauses_probe2.py](../../../uplift/consolidated/iteration-54/clauses_probe2.py); section H's probes are
[optional_where_probe.py](../../../uplift/consolidated/iteration-54/optional_where_probe.py) and
[optional_mixed_probe.py](../../../uplift/consolidated/iteration-54/optional_mixed_probe.py). Retained: binding
`20261117T054801Z` (102 cases, before section H) and `060330Z` (superseded by a comment change), both AGREES.

## Reconciliation with inherited models

[aggregate_results](../aggregate_results/NOTES.md) states SQL key equality, collation and "representative typing of
equal int/double grouping keys" as provider premises. Section A shows the premise fails on IRIS for keys of different
kinds with the same text: that model's grouping correspondence holds only for single-kind keys. Its proofs are
unchanged; its claim at the reader is narrowed in [query.aggregation.keys](../../../ontology/features/cypher.g5.md#query.aggregation.keys).

## Limits

The port is unverified Python; the binding observes outcome classes (together or apart, half-unit totals, decoded or
marked text, row counts, row count or refusal class, Prepare success, refused or deleted), not every byte. The
transcription covers the branches the probes reach, not every AST kind the functions handle. Premises: IRIS compares
`GROUP BY` and `COUNT(DISTINCT)` on the stored text (observed), `CY_TYPED`'s marks (observed through the reader),
Python's half-to-even `round()` (language), IRIS `UNION` duplicate removal by raw value (observed). All observed on
IRIS 2026.1 with intersystems-irispython 5.3.2 only; the TCK's driver 5.4.x was not available.
