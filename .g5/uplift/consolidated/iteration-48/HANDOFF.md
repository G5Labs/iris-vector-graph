# Iteration 48: Cypher expressions over values known only at run time (W55)

Before image: `3001a6b0` (seal 47 `7f04a790` plus the master's inventory commit). Product `3eaa79cf` unchanged
(`check_consolidated.py` PASS; nothing outside `.g5/` differs from `3001a6b0`). Native evidence only from
`ivg-cont-20261117-iris`, fresh prefixes per run (`i48_…`, `i48b_…`, `i48c_…`, `ce…`, `i48q_…`). Guidance:
`Verus/uplift-iteration.md` sha256 `7c5f718a88badf0202d91cd1d557ff2dd2f2bab8bc25178dccf852143e913b12` (unchanged).
The question cards in `open_questions.md` are untouched (no question opened).

## Result

Predictions for 22 cases across five families were frozen and committed (`d8fe862a`) before the deciding source was
read ([PAIRS](cypherexpr-PAIRS.md)): **16 held, 4 partial, 2 missed**. The source reading then traced each departure
to one translator decision taken on the argument's syntax, and a follow-up found a silent write loss that no prediction
covered. New model `cypher_exprs` (17 verified, 17 controls EXPECTED_FAIL, binding AGREES 209 cases). Six new owner
blocks. Active bindings **463 → 480**.

Did the literal/run-time split decide other consequential expressions? Partly. It decided two of the six departures:
a negative slice bound (`l[-3..]` from a row counts as 0) and a boolean condition (a row or parameter boolean fails
`CASE WHEN`/`WHERE`). The others depend on the function or the clause, with literals affected too: a node `CREATE`
refuses any function the Python constant folder does not know (literal or not; this is bug-cyp-114's refusal), a
relationship `CREATE` between new nodes silently drops every computed value, `coalesce` loses the type unless a node
property is among its arguments, and `substring` accepts a negative start.

## Predictions held and missed

| Workflow | Held | Partial | Missed |
|---|---|---|---|
| W55 writes W1-W5 | W1, W3, W4, W5 | | W2 (`size()` in a `CREATE` map refused) |
| W55 strings S1-S6 | S1, S4, S5, S6 | S2 (negative start answers a prefix), S3 (length 0 is null) | |
| W55 slices and lists L1-L4 | L2, L3, L4 | | L1 (negative run-time bound) |
| W55 CASE/coalesce C1-C4 | C1, C2 | C3 (literal neighbor `'1'`), C4 (`UNWIND` boolean fails) | |
| W55 aggregation A1-A3 | A1, A2, A3 | | |

Not frozen (found after the freeze): bug-cyp-120 (seen in follow-up 2's `F7_rel_fn` before the source reading, isolated in follow-up
3), bug-cyp-122 (the probe's own query failed to parse), bug-cyp-125 (the binding harness). Set aside as
already owned: aggregation over stored values beyond A1-A3 (`query.aggregation`), the relationship `coalesce` text
(bug-cyp-107), `size()` of a stored string spelling a list (documented).

## Findings

New (discovered here; E2E reproduced on the fixture with a passing neighbor unless noted):

| ID | Severity | Trigger → observable | Formal claim |
|---|---|---|---|
| [bug-cyp-120](../../../Verus_verification/bugs_issues.md#bug-cyp-120) | High | relationship `CREATE` between new nodes with a computed value (`1 + 1`, `toUpper('ab')`) → success, property dropped | `theorem_inline_rel_expression_dropped` |
| [bug-cyp-117](../../../Verus_verification/bugs_issues.md#bug-cyp-117) | Medium | negative slice bound from a row or parameter → counts as 0 | `theorem_row_negative_slice_departs` |
| [bug-cyp-118](../../../Verus_verification/bugs_issues.md#bug-cyp-118) | Medium | bare boolean from `UNWIND`/`WITH`/parameter in `CASE WHEN`/`WHERE` → query fails (SQLCODE -14) | `theorem_row_boolean_condition_fails` (IRIS premise) |
| [bug-cyp-119](../../../Verus_verification/bugs_issues.md#bug-cyp-119) | Medium | node `CREATE` value `size()`, `abs()`, `toInteger('5')`, `substring`, `replace`, `randomUUID()`, `rand()` → refused, nothing written | `theorem_unfolded_create_value_refused` |
| [bug-cyp-121](../../../Verus_verification/bugs_issues.md#bug-cyp-121) | Low | `coalesce` over row values, literals, parameters → number as text | `theorem_row_coalesce_number_as_text` |
| [bug-cyp-122](../../../Verus_verification/bugs_issues.md#bug-cyp-122) | Low | `l[a..3]` with an identifier lower bound → parse error | `theorem_identifier_lower_bound_refused` |
| [bug-cyp-123](../../../Verus_verification/bugs_issues.md#bug-cyp-123) | Low | negative `substring` start → leading characters; negative length → opaque -400 | `theorem_negative_start_answers_prefix` |
| [bug-cyp-124](../../../Verus_verification/bugs_issues.md#bug-cyp-124) | Low | `left`/`right`/`substring` with length 0 → null | none (probe only, open in Verus) |
| [bug-cyp-125](../../../Verus_verification/bugs_issues.md#bug-cyp-125) | Low | `UNWIND $list` with driver 5.3.2 → "Invalid number of parameters" | none (potential problem; driver-conditional, partially reproduced) |

Inherited and reconciled: [bug-cyp-114](../../../Verus_verification/bugs_issues.md#bug-cyp-114)'s `CREATE` refusal is
now traced (its cause is bug-cyp-119; the entry says so); iteration 47's "Incorrect number of parameters" failures of
`n.l[$i]` and `m[$k]` may share bug-cyp-125's driver premise (noted in bug-cyp-125, not re-tested on 5.4.x);
the KNOWN_ISSUES map-row `CASE WHEN` entry is a neighbor of bug-cyp-118, not the same shape. Withdrawn: none.
Simplifications (new, model-only comparisons): [simp-cyp-101](../../../Verus_verification/design_simplification.md#simp-cyp-101)
one run-time path for list positions (covers bug-cyp-111 and -117),
[simp-cyp-102](../../../Verus_verification/design_simplification.md#simp-cyp-102) one SQL path for computed write values
(covers bug-cyp-114/-119/-120). Questions opened or resolved: none (openCypher settles every expected outcome; whether
driver 5.3.x is supported is recorded in bug-cyp-125, not as a card).

## Owners changed

New: [query.functions.slice](../../../ontology/features/cypher.g5.md#query.functions.slice), `.strings`, `.coalesce`;
[query.values.conditions](../../../ontology/features/cypher.g5.md#query.values.conditions);
[query.writes.computed_values](../../../ontology/features/cypher.g5.md#query.writes.computed_values),
[query.writes.retype](../../../ontology/features/cypher.g5.md#query.writes.retype) (D). Extended additively:
`query.functions.random` (links the shared refusal cause), `query.writes` and `query.values` children lists,
`query.conformance` and `query.functions.list_index` metadata. IDs preserved; `check_ontology.py` 371 blocks, 0 issues,
17 writing warnings (unchanged).

## Model

| Model | Verified | Controls | Binding |
|---|---|---|---|
| `cypher_exprs` (new) | 17 ([receipt](../../../Verus_verification/results/cypher_exprs/20261117T021938Z-prove/receipt.json)) | 17 of 17 EXPECTED_FAIL; each fails only its named theorem except the effect control `substring-zero-based` (two) | AGREES 209 cases; 17 of 17 mutations and the tamper check detected ([receipt](../../../Verus_verification/results/cypher_exprs/20261117T022154Z-binding/receipt.json)) |

The translator's choice is derived inside the model from the argument's syntax (`Syntax`, `Fn`, `RelValue`, `CoArg`,
`Lower`), never supplied as a parameter. Controls: seven repairs that leave their neighbor verified, seven removals of
a decisive guard or effect, two provider-premise flips, one effect control. Three premises are observed, not proved:
IRIS refuses a scalar condition (SQLCODE -14), the driver refuses an AST argument, and IRIS's filer writes no
same-text value (observed here through the product's own path for a namespace without `Prop_Set`). Retained failure:
binding `20261117T022138Z` DISAGREED on its own harness (its `UNWIND $pairs` read returned no rows; the literal-list
form was then used; that observation became bug-cyp-125). Trust inventory: no `assume`, `admit` or `external_body`;
`vstd` only; the binding port is unverified Python.

## Recount ([member-delta.json](member-delta.json); `member_reach.py`, denominator 4,130)

Active bindings **463 → 480**. Newly reached and bound: 17 — `translator.py::_expr_slice`, `_slice_sql`,
`translate_boolean_expression`, `_expr_case`, `_create_resolve_prop_value`, `_fold_constant`, `_fold_or_raise`,
`_create_node_literal`, `_create_node_per_row`, `_create_clause_relationship_entry`, `_is_typed_coalesce`,
`_scalar_coalesce`, `_prop_set`; `parser.py::Parser.parse_primary_expression`;
`engine.py::IRISGraphEngine._prop_set_deployed`; `SqlProcs.cls::PropSet`; `PropWrite.cls::SetVal`. Strengthened (a new
claim on an already bound member): 4 — `_translate_boolean_expression`, `_stored_bool_in`, `_scalar_string`,
`QueryMixin._execute_parsed_sql`. Overlap 0; distinct additions 21; lost 0. Roles: deciding translator functions
(`_expr_slice`, `_translate_boolean_expression`, `_create_resolve_prop_value`, `_fold_constant`,
`_create_clause_relationship_entry`, `_is_typed_coalesce`, `_scalar_string`, `parse_primary_expression`,
`_prop_set_deployed`), emitting functions (`_slice_sql`, `_expr_case`, `_scalar_coalesce`, `_prop_set`), writers
(`_create_node_literal`, `_create_node_per_row`), delegating entries with a justified shared relation
(`translate_boolean_expression`, `_fold_or_raise`), ObjectScript entry and body (`PropSet`, `PropWrite.SetVal`), reader
(`_execute_parsed_sql`). New formal distinctions: literal vs run-time slice bound; predicate vs scalar condition by
syntax; folded vs unfolded `CREATE` value; literal vs computed relationship value; typed vs text `coalesce`; identifier
vs other lower bound; negative vs inside `substring` start; `Prop_Set` deployed vs not. Correspondence confirmed at the
reader for each (binding cases above); none withdrawn. Material predictions gained: L1, W2, C3, C4 (and S2) now have a
formal claim that rejects the openCypher outcome the product does not give; W4 (held) gained its bound source roles.

Correspondence: [delta from 47](correspondence-delta-from-47.json) (proof and correspondence STALE_ALL by design: the
new model's formal inputs, its binding, the crosswalk and families changed; no product file changed); fresh
[stamp](correspondence-inputs.json) (`check` → REUSABLE_INPUTS). `check_evidence.py` FRESH (cypher_exprs 17 verified, 17
controls). `check_findings.py` no problems; `check_consolidated.py` PASS. `link_verification.py` reports
`.g5/TLA_verification/models not found` (no TLA models in this foundation; not applicable).

## Residual list (first missing step for each)

W55, open:
- `_create_node_from_alias` (also resolves `CREATE` values) and `_create_values_edge_keyed` (multigraph relationship
  values): first missing step is a probe of a `CREATE` that names an earlier node and of a relationship `CREATE` with
  multigraph off; both are expected to share bug-cyp-119/-120's decision.
- Zero-length strings (bug-cyp-124), `left`/`right` with negative lengths and the type conversions: observed only; first
  missing step is a model of IRIS's empty-string-as-null for `LEFT`/`RIGHT`/`SUBSTRING`.
- bug-cyp-125: first missing step is the same `UNWIND $xs AS a RETURN a` on driver 5.4.0/5.4.1 (no wheel on this
  machine), which decides whether it is a product defect or a fixture premise; it may also reclassify iteration 47's
  "Incorrect number of parameters" observations.
- Other expression shapes with a syntax-based choice not yet probed: map access conditions (`CASE WHEN m.k`),
  `CASE` results that are lists, nested function calls in `CREATE` (`toUpper(toString(i))`), `SET n += {…}` with
  unfolded functions (one shape held), string slicing of a string variable (`_expr_slice`'s string branch ignores
  run-time bounds; openCypher does not define string slices).
- `PropWrite.Layout` and `SetVal`'s lock and layout refusals: not modeled.
- Carried from iteration 47 Part B and Part C: the 12 SQL-only `CypherFn` bodies, percentiles, `keys(n)` listing `id`,
  bug-cyp-115/-116 probe-only, the native executor (declined every function and expression shape probed in 47 and 48),
  `vector_search`'s IVF fallback, `kg_BM25`, `MatchEdges`/`MatchEdgesAllGraphs`, `DijkstraPath`,
  `backfill_temporal_rows`, `rebuild_edge_indices`. `Prop_Set` is now bound (removed from this list).

Set aside: none of the quarantined material was opened (no iteration-13 Cypher `MERGE` material; no `MERGE` was
probed); no evaluator-private input was read.

## Cost

Builder wall clock about 25 minutes (02:05-02:31 UTC, from the first command to the seal); tokens and currency not
available to the builder. Proof under 2 s, the 17-control suite about 17 s, the binding about 2 s.

## Independent review

Not performed in this iteration (no separate reviewer was started). For a reviewer: reproduce `cypher_exprs` prove,
`CONTROL=rel-value-kept`, and its binding (runbook "Continuation on Linux", iteration 48); attack first whether the
binding's port of `create_rel_value` and `coalesce_number` matches the spec functions, whether `bug-cyp-120`'s High
severity is warranted, and whether `theorem_row_boolean_condition_fails` should be read beyond the observed IRIS 2026.1
premise.
