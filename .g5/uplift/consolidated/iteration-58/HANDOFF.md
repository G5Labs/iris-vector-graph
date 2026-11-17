# Iteration 58: W62, remaining clause combinations and result decoders

Before image `2ae9e1d5` (the master's inventory commit after seal 57). Product `3eaa79cf` unchanged: nothing outside
`.g5/` changed (`git diff 2ae9e1d5 -- . ':!.g5'` empty; no untracked file outside `.g5/`).
Commits:
- `2429a0a3` (08:06:41 UTC): the freeze. It committed only [w62-PAIRS.md](w62-PAIRS.md), before any deciding source
  (decoder bodies in `_engine/query.py`, the translator's null-row, UNWIND-flag, FOREACH, `SET +=`, `WITH *`,
  `CALL { }`, UNION and var-length route code) was read. The file's own "~08:15" stamp was a forward estimate; the
  commit time is authoritative.
- `f92a5e35`: checkpoint with the two models, registers and owners integrated.
- The seal.

Guidance read at the start: `$G5_HARNESS/AGENTS.md`; `Verus/{uplift-iteration, uplift-scoring}.md` (re-read in full),
`Verus/{uplift, setup_foundation, verification}.md`, `uplift-intent-recovery.md`, `ontology-format.md` and
`setup_foundation.md` as already applied by iterations 54-57; the binding-integrity rule of
`assignments/iteration-56.txt`; the iteration-54 and -55 residual lists. `open_questions.md` was not changed (no card,
anchor, field or saved answer touched). Quarantine was respected: no iteration-13 Cypher `MERGE` material and no
evaluator-private ledger. Native evidence comes only from `ivg-cont-20261117-iris`, namespace USER, with fresh prefixes
`i58c_` (clauses) and `i58d_` (decoders). No other container was touched, `sync()` was not run, and no STOP file
appeared.

**Drivers per observation.** Clauses (C1-C9, the `clause_combos` binding): intersystems-irispython 5.3.2 (the fixture
venv, the version `uv.lock` pins). Decoders (D1-D9, the `result_decoders` binding): both 5.3.2 and 5.4.1 (the isolated
venv iteration 55 created, `$RUN_DIR/i55/venv541`), on all four readers: Python `execute_cypher`, Bolt with the neo4j
Python driver 6.4.1 against the product's TCP listener, `/api/cypher` and `/db/neo4j/tx/commit`.

**Sub-agents.** Two workers ran in parallel, each owning its own files:
- W1, clause combinations: C1-C9, model `clause_combos`, directory [clauses/](clauses/).
- W2, result decoders and readers: D1-D9, model `result_decoders`, directory [decoders/](decoders/).

The builder alone edited the shared registers (`bugs_issues.md`, `crosswalk/{decision-links,findings}.tsv`,
`families.tsv`, `coverage.md`, `runbook.md`) and the ontology. The harness refused both workers' writes of
`findings.md`; the builder saved them from the workers' reports ([clauses/findings.md](clauses/findings.md),
[decoders/findings.md](decoders/findings.md)). The builder dropped one proposed crosswalk row (W1's IRIS -94 premise,
whose path "IRIS 2026.1 SQL (observed)" is not a product file); the premise stays in the model's NOTES.

## Predictions ([w62-PAIRS.md](w62-PAIRS.md), frozen at `2429a0a3`)

18 workflows, two neighbors each (36 predictions). Details: [clauses/OBSERVED.md](clauses/OBSERVED.md),
[decoders/OBSERVED.md](decoders/OBSERVED.md).

| ID | Verdict | Note |
|---|---|---|
| C1 OPTIONAL aggregates | held | `count(b)` 0, `count(*)` 1; `collect` `[]`, `sum` 0, `avg` null for the unmatched anchor. A leading grouped OPTIONAL MATCH gives `sum` null: inherited bug-agg-001, reproduced and now modeled |
| C2 UNWIND grouping | **missed** (as the row expected) | `[1,'1']`, `[1,true]` and `[[1],'[1]']` each one group with `count(DISTINCT)` 1, while `RETURN DISTINCT` keeps two rows: **bug-cyp-149** |
| C3 -94 boundary | held | OR and arithmetic over the new alias alone run and keep every row; beyond the prediction, the refusal follows negation polarity (bug-cyp-142 extended) |
| C4 UNION values | partial | stored float and list as predicted (bug-cyp-138); a relationship in UNION ALL is JSON text, not a relationship (bug-cyp-138 extended) |
| C5 CALL { } aggregation | held | `c = 0` for the unmatched anchor; the subquery column comes first (documented) |
| C6 FOREACH | partial | `SET n.f = x` fails UndefinedVariable and writes nothing: **bug-cyp-152**; CREATE body and empty list held |
| C7 SET += | held | |
| C8 WITH * | **missed** (both) | `WITH *` then `type(r)` fails -29: **bug-cyp-150**; `WITH *, a.v AS av` does not parse: **bug-cyp-151** |
| C9 ORDER BY mixed after WITH | held | `'a', true, 1.5, 2, null` and the reverse |
| D1 mixed-kind WITH column | **missed** (both) | CASE: stored boolean `'true'`, list/map JSON text, and numbers as text on 5.4.1: **bug-cyp-156**; `WITH coalesce(...)`: numbers and booleans as text on both drivers: **bug-cyp-155** |
| D2 OPTIONAL null-row column | partial | `b.x` null and `collect(b)` `[]` everywhere; the unbound node's `b_labels`/`b_props` are `'[]'` at Python and both HTTP readers (Bolt: null): **bug-plt-135** |
| D3 empty strings and containers | held | |
| D4 map columns | held | |
| D5 numeric expressions | held | |
| D6 boolean expressions | held | |
| D7 empty results | held | |
| D8 shadow and compiled | held, narrower scope | identical answers in modes off/sync/job and with `IVG_CYPHER_SHADOW=1` (one comparison, no mismatch), Python and Bolt, both drivers; a compiled plan's second run was not isolated |
| D9 var-length LIMIT | held | all four LIMIT shapes right; they run in SQL (`CY_VLP_PATHS` + `FETCH FIRST`); `_route_var_length` was reached only by `shortestPath`, where LIMIT has no effect |

Totals: 12 of 18 workflows held fully (D8 within a narrower scope), 3 partial (C4, C6, D2) and 3 missed (C2, C8, D1;
C2 was an intent prediction the inherited residual already expected to miss). Single predictions: 26 of 36 held, 2
partial (both D2 neighbors) and 8 missed (both of C2, C8 and D1; C4's relationship half; C6's SET body).

## Findings

New (matched by trigger and observable consequence against `bugs_issues.md` and `docs/KNOWN_ISSUES.md`):

| ID | Severity | Trigger → observable | Found by / reproduced by |
|---|---|---|---|
| [bug-cyp-155](../../../Verus_verification/bugs_issues.md#bug-cyp-155) | Medium | `WITH coalesce(n.a, n.b) AS x RETURN x` → stored `3`, `2.5`, `true` answer `'3'`, `'2.5'`, `'true'`, all readers, both drivers | D1 neighbor missed / `result_decoders` binding |
| [bug-cyp-156](../../../Verus_verification/bugs_issues.md#bug-cyp-156) | Medium | a CASE column over node properties → boolean `'true'`, list/map JSON text; numbers text on driver 5.4.1 | D1 missed / `result_decoders` binding |
| [bug-cyp-149](../../../Verus_verification/bugs_issues.md#bug-cyp-149) | Low | UNWIND of a held list mixing 1/true or a list and its spelling → one group, `count(DISTINCT)` 1, vs two DISTINCT rows | C2 missed / `clause_combos` binding |
| [bug-cyp-150](../../../Verus_verification/bugs_issues.md#bug-cyp-150) | Low | `WITH *` then `type(r)` → SQLCODE -29 | C8 missed / probe (not modeled) |
| [bug-cyp-151](../../../Verus_verification/bugs_issues.md#bug-cyp-151) | Low | `WITH *, a.v AS av` → parse error | C8 neighbor missed / probe (not modeled) |
| [bug-cyp-152](../../../Verus_verification/bugs_issues.md#bug-cyp-152) | Low | `FOREACH (x IN [1,2] \| SET n.f = x)` → UndefinedVariable, nothing written | C6 partial / probe (not modeled) |
| [bug-plt-135](../../../Verus_verification/bugs_issues.md#bug-plt-135) | Low | unbound OPTIONAL node at Python/HTTP → `b_labels`, `b_props` `'[]'` | D2 partial / `result_decoders` binding |

Unused IDs: bug-cyp-153, -154, -157..-160, bug-plt-136..-138.

Inherited, strengthened (paragraphs appended to the entries; nothing removed):
- [bug-agg-001](../../../Verus_verification/bugs_issues.md#bug-agg-001): reproduced afresh and modeled
  (`theorem_leading_grouped_sum_is_null`).
- [bug-cyp-142](../../../Verus_verification/bugs_issues.md#bug-cyp-142): the -94 refusal characterized by negation
  polarity over 15 shapes (`theorem_negation_polarity`, `theorem_new_alias_only_keeps_row`).
- [bug-cyp-138](../../../Verus_verification/bugs_issues.md#bug-cyp-138): relationship values in UNION ALL (observed only).

Questions: none opened or resolved (C2's 1 vs 1.0 stays under `query.aggregation.keys.numbers`). Simplifications: none.
Discoveries vs repairs: all seven new entries came from this iteration's frozen predictions; none was supplied by a review.

## Models and receipts (final candidate)

| Model | Verified | Controls | Binding |
|---|---|---|---|
| [`clause_combos`](../../../Verus_verification/models/clause_combos/NOTES.md) (new, W1) | 28 | 17/17 EXPECTED_FAIL | AGREES 87; 17/17 port mutations and 4 tampers detected; driver 5.3.2 |
| [`result_decoders`](../../../Verus_verification/models/result_decoders/NOTES.md) (new, W2) | 12 | 17/17 EXPECTED_FAIL | AGREES 480 (2 drivers × 4 readers); 17/17 mutations and the tamper detected |

Each answer is derived from modeled state, not supplied:
- `clause_combos`: the null-row aggregates from the modeled edge set and aggregate kind; group keys from the bound row
  text the translator emits per list element kind; the OPTIONAL WHERE placement from which aliases a condition reads,
  and the -94 refusal from an IRIS premise (P-OUTER-ON, `cites`) fixed on 15 observed shapes.
- `result_decoders`: the column kind (`CY_TYPED`, raw, `CAST AS VARCHAR`) from the query shape (property, WITH
  property, RETURN/WITH coalesce, RETURN/WITH CASE); the SQL value from the stored text and the driver; the decoded
  value from the decoder that kind selects; the null OPTIONAL node's columns from whether it is bound.

General theorems: the null row's `count(b)` is 0 for every edge set; two elements group together iff their bound row
text is equal; a condition over only the new alias keeps every row; every typed property read round-trips every
written kind under both drivers; every decoder passes a null row through; a comparison column is a boolean or null.
Departure (witness) theorems reject each probe-confirmed wrong outcome. Domains and exclusions are in each NOTES.md.

**Re-verification by the builder** (sequential, after both workers finished):
- `clause_combos`: prove PASS 28 (`20261117T082830Z`), controls 17/17 EXPECTED_FAIL, binding AGREES 87
  ([`20261117T083139Z-binding`](../../../Verus_verification/results/clause_combos/20261117T083139Z-binding/receipt.json)).
- `result_decoders`: prove PASS 12 (`20261117T082943Z`), controls 17/17 EXPECTED_FAIL, binding AGREES 480
  ([`20261117T083143Z-binding`](../../../Verus_verification/results/result_decoders/20261117T083143Z-binding/receipt.json)).
- The control suites ran twice each in the re-run (once counted, once inspected for anything other than
  EXPECTED_FAIL; none).

Unsuccessful runs kept: `clause_combos` `081543Z` binding DISAGREES (led to the negation-polarity premise); earlier
`result_decoders` control runs in which `with-prop-untyped` survived and `ret-coalesce-untyped` failed in the wrong
function (fixed by adding `theorem_property_reads_roundtrip`). The workers' superseded receipts stay in the results
folders (deleting them was refused).

## Recount ([member-delta.json](member-delta.json); `member_reach.py`, denominator 4,130)

Active bindings rose from **696 to 706** (+10, 0 lost). Union reach rose from **907 to 914** (+7). Of the 10:
- **7 newly reached:** `_engine/query.py::{_bool_expr_value, _decode_bool_text_columns}`;
  `cypher/translator.py::{_is_node_value_var, _unwind_bool_flag, _unwind_json_text, labels_subquery}`;
  `prop_values.py::read_prop_value`.
- **3 existing locators gaining a binding:** `translator.py::{_json_text_list_agg, _null_row_aggregate, _zero_if_null}`.
- **Strengthened (11):** `query.py::{_decode_typed_value_columns, _finish_sql_result}`;
  `translator.py::{_expr_aggregation, _is_typed_coalesce, _reads_node_value, _scalar_coalesce, translate_return_clause,
  translate_where_clause}`; `prop_values.py::{decode_json_list_map, decode_typed_text, parse_prop_text}`.

`translator.py` and `query.py` remain mostly unbound. Of the nine decoders the assignment named, two are now active
(`_decode_typed_value_columns` strengthened, `_decode_bool_text_columns` new); the other seven
(`_decode_json_value_columns`, `_decode_map_text_columns`, `_decode_numeric_expr_columns`,
`_decode_mixed_expr_columns`, `_decode_empty_json_strings`, `_optional_null_columns`, `_fill_empty_columns`) were
observed end to end on all four readers (D3-D7 held) but are only `cites`: their decisions are not modeled, so they do
not count.

**Material predictions gained:** what a CASE and a WITH coalesce column answer per stored kind and driver; that every
typed property read round-trips on both drivers and four readers; what the unbound OPTIONAL node's three columns are;
the null-row aggregates; when UNWIND-list grouping merges kinds; which OPTIONAL WHERE shapes IRIS refuses.
**Withdrawn:** none.

<a id="binding-integrity-audit"></a>
## Binding-integrity audit

Question for every row added with relation models, proves or witnesses: would swapping or weakening this member's own
decision break a theorem or the binding? Per-row detail with control and mutation names: [clauses/AUDIT.md](clauses/AUDIT.md)
(16 rows) and [decoders/AUDIT.md](decoders/AUDIT.md) (20 rows). 36 rows audited; 1 relabelled; 7 rows (W1 rows 4 and 15, W2 rows 3, 4, 7, 13
and 16) passed only after a control was added for them during the iteration.

| Member (rows) | Relation | Swap or weaken its own decision → | Verdict |
|---|---|---|---|
| `translator.py::_expr_aggregation` (count over non-null; `COUNT(DISTINCT)` key) | models, proves | `count-var-counts-rows`, `sum-null-over-no-value`, `group-by-kind-column`; binding `A_after_*`, `B_*_count_distinct` | active |
| `translator.py::_zero_if_null`, `_json_text_list_agg` | proves | `sum-null-over-no-value`; `collect-null-over-no-value` (added for this row) | active |
| `translator.py::_null_row_aggregate` | models, witnesses | `null-row-count-var-one`, `null-row-sum-zero`; binding `A_leading_grouped_nomatch_*` | active |
| `translator.py::translate_return_clause` (leading star patch; grouped leading SQL; GROUP BY plain sql; DISTINCT flag route; typed emission) | models, proves, witnesses | `leading-star-unpatched`, `grouped-leading-uses-sql`, `group-by-kind-column`, `bool-bound-as-word`, `distinct-plain-on-flag`, `typed-emitted-raw` | active |
| `translator.py::_unwind_bool_flag`, `_unwind_json_text` | models, proves | `distinct-plain-on-flag`, `json-route-plain` | active; `_unwind_bool_flag` **qualified**: the control replaces the route's result, not the flag function's body |
| `translator.py::translate_where_clause` (ON placement) | models, proves | `condition-in-where` (added for this row); premise neighbors `iris-refuses-any-or`, `iris-refuses-any-arith` | active |
| `translator.py::_reads_node_value`, `_is_node_value_var`, `_is_typed_coalesce`, `_scalar_coalesce` | models, proves | `with-prop-untyped`, `ret-coalesce-untyped`, `with-coalesce-typed`, `coalesce-cast-gone`, `case-typed` (several added in the final W2 run) | active |
| `query.py::_finish_sql_result`, `_decode_typed_value_columns` (typed column), `_decode_bool_text_columns` | models, proves | `typed-emitted-raw`, `no-prop-text`, `case-prop-text`; binding `*_Prop_*`, `*_WithProp_*` | active |
| `query.py::_bool_expr_value` | models, proves | `bit-one-false`, `bool-expr-off`, `gt-text-zero` | active; **qualified**: the comparison column kind is a constant in the model (`bool_expr_col`), only the decoder's text→boolean decision is modeled |
| `prop_values.py::read_prop_value`, `decode_typed_text`, `decode_json_list_map`, `parse_prop_text` | models | `no-mark-decode`, `no-json-decode` | active |
| `translator.py::labels_subquery` | models, witnesses | `labels-null`; binding `*_Opt_labels` | active |
| `query.py::_decode_typed_value_columns` → `theorem_null_row_every_decoder` | was proves | no control swaps this decoder's own null pass-through (`missing-not-null` changes the SQL value) | **relabelled `cites`** |
| `_unwound_known_text`, the seven unmodeled decoders, `QueryMixin._cypher_shadow`, `_shadow_compare`, `_to_sql_handle_foreach`, `translate_with_clause`, `Parser.parse_with_clause` | cites | no own decision modeled | not counted |
| `_expr_property_reference`, `_tts_union_branches`, `QueryMixin._route_var_length` | delegates | forward to modeled or unmodeled producers | not counted |

## Owners changed (additive; IDs preserved)

`query.optional` (null-row aggregates with the bug-agg-001 "Today"; new-alias-only WHERE and the -94 negation rule;
null OPTIONAL properties and the bug-plt-135 "Today"), `query.aggregation.keys` (bug-cyp-149 "Today"), `query.union`
(relationship text), `query.writes.computed_values` (`SET +=`), `query.writes` (bug-cyp-152 "Today"),
`query.conformance` (bug-cyp-150/-151 "Today"), `query.values` (the column-kind decision; bug-cyp-155/-156 "Today").
Metadata paragraphs with evidence links were added to those blocks and to `query.aggregation`, `query.shadow`,
`query.compiled.equal-answers` and `query.paging` (observations only; no new statement there). No new block.
`check_ontology.py`: 403 blocks, 0 issues, 18 writing warnings (17 before; the new one is `query.conformance` at 11
bullets).

## Correspondence

The [delta from 57](correspondence-delta-from-57.json) is STALE_ALL for proof and correspondence: the changed formal
inputs are the two new models; the changed product-side inputs are their `binding.py` files, `decision-links.tsv` and
`families.tsv`; no product file changed. The fresh [stamp](correspondence-inputs.json) checks as REUSABLE_INPUTS.

<a id="checks-final-candidate"></a>
## Checks (final candidate)

| Check | Result |
|---|---|
| `check_ontology.py` | 403 blocks, 0 issues, 18 warnings |
| `check_findings.py` (`verification_root=.g5/Verus_verification`, `--previous 2ae9e1d5`) | No problems found (after adding one back-link: `query.aggregation` → bug-cyp-149) |
| `check_evidence.py` | FRESH |
| `check_consolidated.py` (G5_GUIDE set) | PASS (1,168 decision links resolve uniquely; stamp REUSABLE_INPUTS) |
| `git diff --check` | clean |
| Product diff vs pin | none outside `.g5/`; no untracked file outside `.g5/` |

## Limitations

- **Review:** this iteration is not independently reviewed.
- **Not modeled:** C4-C9 (UNION values, CALL { }, FOREACH, `SET +=`, `WITH *`, ORDER BY after WITH) and D3-D9 are
  observed only; bug-cyp-150, -151, -152 are probe-only (no Verus claim). The seven decoders above are cited only.
- **Domains:** floats (1 vs 1.0) are excluded pending `query.aggregation.keys.numbers`; maps in UNWIND; `UNWIND $p` on
  5.3.2 (bug-cyp-125). `NOT ((b.v = 10) OR (a.v = 1))` is refused and lies outside the -94 premise's domain. Only values
  written by `create_node` were tested by W2 (not Cypher-written values or relationship properties); only empty lists
  and maps; CASE and coalesce are reduced to the chosen branch's value.
- **Shadow/compiled:** the `ORDER BY` forms are not native-planned; a compiled plan's second run was not isolated.
- **Var-length LIMIT:** `_route_var_length` was reached only by `shortestPath`; no LIMIT through the BFS route.
- **Fixture residue:** data remains in USER under `i58c_` and `i58d_`.

<a id="residual-list-first-missing-step-for-each"></a>
## Residual list (first missing step for each)

1. The seven unmodeled decoders: add a model section for `int_expr_columns`/`float_expr_columns` and
   `_mixed_scalar_value` (numeric and mixed), then `_decode_map_text_columns` and `_decode_json_value_columns`, with a
   binding case per decoder that a swapped decision would break.
2. bug-cyp-150/-151/-152 in Verus: a model of `WITH *` projection (relationship variables) and of the FOREACH variable
   binding (`foreach_literals` in the SET value).
3. The -94 premise beyond its domain: probe `a.v = lit` alone and under NOT and OR, and read IRIS's -94 conditions.
4. Compiled plans: set `native_route_ms = 0`, run a hop shape twice in mode sync and count `_run_native_plan` calls.
5. Var-length LIMIT through `_route_var_length`: find a non-shortest shape that `_trp_vlp_native` declines.
6. Decoders for Cypher-written values and relationship properties on the four readers (`_decode_rel_prop_text_columns`).
7. Inherited queue otherwise unchanged (see the [continuation residual queue](../HANDOFF.md#continuation-2026-11-17)).

## Cost

Builder session wall clock from about 08:05 to the seal at about 08:37 UTC (about 32 minutes). Two parallel workers: W1 took about 19
minutes and 214k sub-agent tokens; W2 about 15 minutes and 213k sub-agent tokens. Currency is not available in-session.
