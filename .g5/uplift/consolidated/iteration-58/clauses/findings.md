# Iteration 58 W1 (clause combinations): findings

Four new entries (bug-cyp-149 to -152); bug-cyp-153 and -154 are unused. Saved by the builder from W1's report (the
harness refused the worker's write). Checked first: `bugs_issues.md` (bug-cyp-135 covers stored values, not lists the
query holds; F-0808 is a FOREACH over a parameter list with a CREATE body; nothing on `WITH *`) and `docs/KNOWN_ISSUES.md`
(the CALL column order is documented; owner `query.aggregation.keys` already states `UNWIND [1,'1']`).

<a id="bug-cyp-149"></a>
### Over a list the query holds, a grouping key and count(DISTINCT) merge 1 with true and a list with the string spelling it, while RETURN DISTINCT keeps them apart

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 58)

Found by: iteration 58 W62 frozen prediction C2 (missed, [PAIRS](../w62-PAIRS.md)); [clause_combos](../../../../Verus_verification/models/clause_combos/NOTES.md) `theorem_group_iff_bound_text`, `theorem_group_merges_kinds`, `theorem_group_and_distinct_disagree`, neighbors `theorem_group_neighbors_follow_rule`, `theorem_distinct_json_route_follows_rule`; controls `group-by-kind-column`, `bool-bound-as-word`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin, driver 5.3.2 ([probe](probe1.out); [run-time list](probe2.out); [binding](../../../../Verus_verification/results/clause_combos/20261117T082514Z-binding/receipt.json) `B_int_true_*`, `B_zero_false_*`, `B_list_spelled_*`). `UNWIND [1, true] AS x RETURN x, count(*)` answers `[[1, 2]]` and `count(DISTINCT x)` 1, while `RETURN DISTINCT x` answers `[[1], [True]]`; `[0, false]` the same; `UNWIND [[1], '[1]']` gives one group and count(DISTINCT) 1 but two DISTINCT rows; `WITH [1, true] AS l UNWIND l AS x RETURN x, count(*)` answers `[[1, 2]]`. Passing neighbors: `['true', true]` (two groups), `[1,2]`, `[2,2]`, `[true,false]`, `[1,'x']`, `[[1],1]`.

Expected: [query.aggregation.keys](../../../../ontology/features/cypher.g5.md#query.aggregation.keys) and [query.aggregation](../../../../ontology/features/cypher.g5.md#query.aggregation) ("a nested list or map is different from text spelling it"); openCypher: values of different types are never equivalent.

Observed: `translate_return_clause` selects the row through the boolean-flag CASE (`translator.py:30665-30671`, `_unwind_bool_flag` 21457) or CY_LIST_KINDS' JSON column (30660-30664, `_unwind_json_text` 21533), keeping the kind, but adds the plain `sql` (`u0.x`) to GROUP BY (30777); `_expr_aggregation` writes `COUNT(DISTINCT u0.x)` (24431). IRIS binds true as 1 and a list row as its JSON text; the kind column (`x__b` / `x__t` / `x__k`) is never a key.

Consequence: grouped counts over lists mixing booleans with 0/1, or lists with their spellings, merge groups with no error; count(DISTINCT) undercounts and disagrees with RETURN DISTINCT. Low: such lists are uncommon; the stored-value root is the Medium bug-cyp-135.

Repair proposal (not implemented): add the UNWIND row's kind column to GROUP BY and to the COUNT(DISTINCT) argument whenever the translator emits one. Preserve: single-kind lists, `'true'` vs true apart, the null group. Control `group-by-kind-column` checks the direction in the model only.

<a id="bug-cyp-150"></a>
### WITH * drops a relationship variable: a later type(r) fails with SQLCODE -29 "Field 'STAGE1.R' not found"

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 58)

Found by: iteration 58 W62 frozen prediction C8 (missed, [PAIRS](../w62-PAIRS.md)). Not modeled.

Reproduced by: **E2E reproduced** on the same fixture and pin, driver 5.3.2 ([probe](probe1.out), [neighbors](probe2.out)). `MATCH (a:L)-[r:K]->(b) WITH * RETURN a.name, type(r), b.name` fails at Prepare with -29. Passing neighbors: the same without `WITH *`, `WITH a, r, b ... type(r)`, and `WITH * RETURN a.name, b.name`.

Expected: openCypher: `WITH *` projects every variable in scope unchanged.

Observed: the star branch of `translate_with_clause` (`translator.py:30857-30872`) projects a relationship as `{var}_s`, `{var}_p`, `{var}_o_id` only, so nothing named `r` reaches the next stage.

Consequence: the query fails with an error naming an internal stage; no wrong answer. Workaround: list the variables.

Repair proposal (not implemented): project each variable as the explicit `WITH a, r, b` does, or rewrite `*` to that list. Preserve: node variables, `WITH * WHERE`, the `CALL ... YIELD` use (2215).

<a id="bug-cyp-151"></a>
### WITH *, a.v AS av does not parse: "Expected EOF, got ,"

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 58)

Found by: iteration 58 W62 C8 neighbor (missed, [PAIRS](../w62-PAIRS.md)). Not modeled.

Reproduced by: **E2E reproduced** on the same fixture and pin, driver 5.3.2 ([probe](probe1.out)): `MATCH (a:L) WITH *, a.v AS av RETURN av` raises `CypherParseError ... col 29: Expected EOF, got ,`; `WITH a, a.v AS av` passes.

Expected: the openCypher grammar allows `WITH *, items`.

Observed: `Parser.parse_with_clause` (`parser.py:333-345`) returns a star WithClause with no items right after `*`.

Consequence: a valid query is refused; no wrong answer.

Repair proposal (not implemented): accept `, item [AS alias]` after `*` and have the star branch add them. Preserve: `WITH *` alone and `WITH * WHERE`.

<a id="bug-cyp-152"></a>
### FOREACH over a literal list with a SET body that reads the loop variable fails "UndefinedVariable: x" and writes nothing

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 58)

Found by: iteration 58 W62 frozen prediction C6 (partial, [PAIRS](../w62-PAIRS.md)). Not modeled.

Reproduced by: **E2E reproduced** on the same fixture and pin, driver 5.3.2 ([probe](probe1.out), [neighbor](probe2.out)): `FOREACH (x IN [1,2] | SET n.f = x)` raises `SyntaxError: UndefinedVariable` and `get_node` still reads `f: 0`. Passing neighbors: `SET n.f = 5` in the body, a `CREATE (:M {v: x})` body (creates 1 and 2), and the empty list.

Expected: openCypher runs the body per element (n.f = 2); owner [query.writes](../../../../ontology/features/cypher.g5.md#query.writes).

Observed: `_to_sql_handle_foreach` (`translator.py:3949-3966`) binds the variable only as `"__foreach_literal__"` plus `foreach_literals`, which the CREATE property path reads; the SET value's translation does not resolve it. This is a different trigger from F-0808 (parameter list, CREATE body).

Consequence: the common "set from each element" FOREACH is refused and nothing is written.

Repair proposal (not implemented): resolve `foreach_literals` in the SET value translation, applying the SETs in list order. Preserve: the CREATE body, the empty list, literal SET values.

## Proposed addenda to inherited entries (integrated by the builder)

- **bug-agg-001** (reproduced): `OPTIONAL MATCH (b:NoLabel) RETURN b.v AS k, sum(b.v), count(b)` answers `[None, None, 0]`. Now modeled by `theorem_leading_grouped_sum_is_null`; controls `null-row-sum-zero` and `grouped-leading-uses-sql`.
- **bug-cyp-142** (extended): the refusal follows negation polarity. The probe3 and binding `C_*` cases (15 shapes) are covered by `theorem_negation_polarity` and `theorem_new_alias_only_keeps_row`. Still open: `NOT ((b.v = 10) OR (a.v = 1))` is refused.
- **bug-cyp-138** (extended): a relationship in a UNION ALL branch comes back as `'{"type":"K","props":{}}'` text, but as a map when returned alone.
