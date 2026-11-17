# Clause combinations over API-written data (OPTIONAL MATCH aggregates, UNWIND keys, the -94 boundary)

Product `3eaa79cf`, unchanged. Iteration 58 (continuation, W62 worker W1). Predictions frozen from openCypher, the
owners and the docs before the deciding source was read:
[w62-PAIRS.md](../../../uplift/consolidated/iteration-58/w62-PAIRS.md) rows C1-C9 (commit `2429a0a3`). Owners:
[query.optional](../../../ontology/features/cypher.g5.md#query.optional),
[query.aggregation](../../../ontology/features/cypher.g5.md#query.aggregation),
[query.aggregation.keys](../../../ontology/features/cypher.g5.md#query.aggregation.keys). Observations and verdicts:
[clauses/OBSERVED.md](../../../uplift/consolidated/iteration-58/clauses/OBSERVED.md).

## What the model decides, and from what

No outcome is an input. Each section takes the query shape and the data and derives the product's answer.

- **A. OPTIONAL MATCH aggregates** (`as_built_answer`). Inputs: the shape (`leading`: the OPTIONAL MATCH opens the
  query; `grouped`: a non-aggregate key beside the aggregates), the anchor's edges (type, target value), the pattern
  type and the aggregate kind. `matched` derives the matches from the edges; `opt_rows` derives the LEFT OUTER JOIN's
  rows (one null row when nothing matched); `as_built_sql` folds them as the SQL aggregates do (count(b) over non-null,
  count(*) over rows, sum with `CASE WHEN SUM IS NULL THEN 0` at `translator.py:18600`, collect `COALESCE(..., '[]')`
  at 21666, avg/min null over no value). A leading pure aggregate gets R298's count(*) patch (30574-30582); a leading
  grouped one with no match takes `_null_row_aggregate` (5412-5422) through `optional_null_row_items` (30790-30791).
- **B. UNWIND of a held list: keys** (`bound_text`, `route`, `select_key`, `group_key`). Inputs: the list's elements
  (integer, boolean, string by what it spells, list by its JSON). `bound_text` is the row value IRIS holds (a boolean
  bound as 1 / 0, a list element as its JSON text). GROUP BY is the plain `sql` (30777) and count(DISTINCT) the plain
  argument (24431), so both compare `bound_text`. SELECT DISTINCT compares the selected item, whose route `route`
  derives from the list's kinds: the CY_LIST_KINDS JSON column when the list holds a list (`_unwind_json_text`
  21533, 30660-30664), the boolean flag CASE when booleans mix with other kinds (`_unwind_bool_flag` 21457,
  30665-30671), otherwise the plain value.
- **C. A WHERE inside OPTIONAL MATCH: the SQLCODE -94 boundary** (`refuses_p`, `as_built_opt`). Input: the
  condition's AST (comparisons over the new alias's property, an earlier alias's property, literals and arithmetic;
  AND, OR, NOT nesting). `translate_where_clause` puts the whole condition in the outer join's ON (17128-17175).
  Provider premise P-OUTER-ON (IRIS 2026.1, observed in this iteration's probes and binding): with negation pushed
  to the comparisons, IRIS refuses the ON when it holds a disjunction one of whose sides reads an earlier alias, or a
  comparison with arithmetic over an earlier alias.

## Claims (28 verified)

| Theorem | Claim |
|---|---|
| `theorem_after_match_follows_rule` | for every edge set, type and aggregate, an OPTIONAL MATCH after a MATCH answers the openCypher value (grouped or not) |
| `theorem_null_row_counts` | for every edge set with no match: count(b) 0, count(*) 1, sum 0, avg null, collect [] |
| `theorem_matched_counts` | a matched anchor: count(b) = count(*) = the number of matches |
| `theorem_leading_pure_follows_rule` | a leading OPTIONAL MATCH with aggregates alone follows the rule for every aggregate |
| `theorem_leading_grouped_others_follow_rule` | a leading grouped OPTIONAL MATCH with no match: every aggregate but sum follows the rule |
| `theorem_leading_grouped_sum_is_null` | rejects the probe-confirmed outcome: its sum is null where the rule says 0 (bug-agg-001, registered) |
| `theorem_group_iff_bound_text` | for every list, two elements group together iff their bound row text is equal |
| `theorem_group_merges_kinds` | rejects the probe-confirmed outcomes (bug-cyp-149): 1 and true, 0 and false, a list and the string spelling its JSON group together; so do an integer and its spelling (owner Today) |
| `theorem_group_neighbors_follow_rule` | same-kind integers, booleans, and a boolean beside 'true' group as the rule says |
| `theorem_distinct_json_route_follows_rule` | on the JSON-column route RETURN DISTINCT follows the rule for every pair |
| `theorem_distinct_flag_route_keeps_bool_apart` | on the flag route a boolean is apart from any integer |
| `theorem_group_and_distinct_disagree` | grouping and DISTINCT disagree on [1, true] and [[j], '[j]'] |
| `theorem_plain_route_merges_int_and_spelling` | [i, 'i']: grouping and DISTINCT both merge (owner Today) |
| `theorem_new_alias_only_keeps_row` | every condition over the new alias only (any nesting, any arithmetic) runs and keeps the row |
| `theorem_negation_polarity` | NOT (b.v = a.v OR b.v = n) runs; NOT (b.v = n AND b.v = a.v) and NOT NOT (OR with a.v) are refused |
| `theorem_mixing_earlier_refused` | rejects (bug-cyp-142, registered): b.v = a.v + 1 and b.v = a.v OR b.v = n are refused, the rule keeps the row |
| `theorem_neighbors` | OR and arithmetic over the new alias, NOT of a new-alias comparison run; b.v = a.v reads earlier and runs |

Plus lemmas `lemma_somes_wrap`, `lemma_null_row`, `lemma_no_earlier_not_refused` and the recursive spec functions'
termination obligations.

## Controls (17, each EXPECTED_FAIL in its named functions)

At least one per modeled decision: `sum-null-over-no-value`, `count-var-counts-rows`, `leading-star-unpatched`,
`null-row-sum-zero` (repair direction of bug-agg-001), `null-row-count-var-one`, `grouped-leading-uses-sql`,
`collect-null-over-no-value` (A);
`group-by-kind-column` (repair direction of bug-cyp-149), `bool-bound-as-word`, `distinct-plain-on-flag`,
`json-route-plain` (B); `iris-accepts-or`, `iris-accepts-arith`, `iris-refuses-any-or`, `iris-refuses-any-arith`,
`negation-ignored`, `condition-in-where` (C). See [model.json](model.json).

## Domains and exclusions

- A: integer target values only; the reader's float for avg is compared as sum/count. Native executor excluded (an
  OPTIONAL MATCH always runs on the SQL path, owner query.optional). min/max over non-integers, `count(DISTINCT b)`,
  collect of nodes are observed (probe1) but not modeled.
- B: two-element literal lists of integers, booleans, strings and one-element lists. Floats are excluded (1 and 1.0:
  [open question](../../open_questions.md#query.aggregation.keys.numbers)); maps excluded; lists mixing a boolean with
  an integer and its spelling are excluded (the flag route reads non-booleans through `CY_TYPED`, not observed). A
  run-time list (`WITH [1, true] AS l UNWIND l`) answers the same (probe2) but is not in the binding. `UNWIND $p`
  fails with driver 5.3.2 (bug-cyp-125) and is excluded.
- C: comparisons by `=` only; every anchor has the property read, so the bug-cyp-143 guard (rows lacking it dropped)
  does not arise (the cypher_clauses model owns it; a condition reading the earlier alias that runs is reported as
  `ReadsEarlier`). A comparison reading only the earlier alias (`a.v = 1`) is excluded: `NOT ((b.v = 10) OR (a.v =
  1))` is refused (probe3), which the polarity premise does not decide. The premise is an observed IRIS behavior, not a
  documented IRIS rule.
- Not modeled: C4 (UNION decoders, the cypher_clauses model's section C), C5 (CALL subquery), C6 (FOREACH), C7
  (SET +=), C8 (WITH *), C9 (ORDER BY): observed only (OBSERVED.md).

## Receipts

Final (current file hashes): prove `results/clause_combos/20261117T082328Z-prove` (PASS 28); controls
`20261117T082335Z`..`20261117T082408Z` (17 EXPECTED_FAIL); binding `20261117T082514Z-binding` (AGREES 87/87, 17/17
mutations, 4/4 tamper cases detected, driver 5.3.2). Earlier receipts in the same directory are superseded: the
`20261117T0813*` runs are model versions before the polarity premise (binding `20261117T081543Z` DISAGREES on
`C_not_or_with_earlier`, which led to it); `20261117T08174*`..`082151Z` are the same theorems before the header-comment fix and the two controls
`collect-null-over-no-value` and `condition-in-where` (with the `Dropped` outcome) were added.
