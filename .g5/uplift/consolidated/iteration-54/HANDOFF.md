# Iteration 54: Cypher clauses over API-written data, default (single-edge) mode and parameters (W59)

Before image `577205f1` (seal 53 `d4aa778b` plus the master's inventory commit). Product `3eaa79cf` unchanged: nothing
outside `.g5/` changed (`git diff 577205f1 -- . ':!.g5'` empty; `check_consolidated.py` confinement PASS).
Commits:
- `6fd28893`: the freeze, committing only [clauses-PAIRS.md](clauses-PAIRS.md) before any deciding source was read;
- `bf86b3d0`: the probes and their observations, before the deciding source was read;
- `cc7abade`: the model (sections A-G) and its first binding;
- the seal.

Guidance read at the start: `$G5_HARNESS/AGENTS.md`; `Verus/{uplift, uplift-iteration, uplift-scoring,
setup_foundation, verification}.md`; `uplift-intent-recovery.md`, `ontology-format.md`, `TLC/setup_foundation.md`,
`setup_foundation.md`. `open_questions.md` changed only by one appended entry (`query.aggregation.keys.numbers`);
no existing card, anchor or saved answer was touched. Quarantine respected: no iteration-13 Cypher `MERGE` material
and no evaluator-private ledger was opened. Native evidence comes only from `ivg-cont-20261117-iris`, namespace USER,
fresh prefixes `i54_`, `i54b_`, `i54k_` and named graphs `i54g…`, `i54m…`, `i54kg…`; no other container was touched.
No sub-agents were used.

## Why this batch, and what the TCK cannot see

The translator is the largest unbound production surface, and the product claims openCypher TCK 3896/3896. The TCK
writes every fixture through Cypher literals in multigraph mode with driver 5.4.x, and its UNION, DISTINCT and grouping
scenarios use literal or single-kind data. This batch wrote data through `create_node`/`create_edge`/`bulk_create_edges`,
a named graph and a multigraph graph, ran in the default single-edge mode with driver 5.3.2, and passed `SKIP`/`LIMIT`
and filters as parameters. Six workflows (OPTIONAL MATCH; aggregation and grouping; WITH/DISTINCT/ORDER BY/SKIP/LIMIT;
UNION, EXISTS and comprehensions; paths; DELETE/DETACH DELETE/REMOVE) were sampled, breadth first.

## Predictions: 42 frozen rows; 35 held, 3 partial, 4 missed (plus one post-read probe, below)

| Workflow (rows) | Held | Partial | Missed |
|---|---|---|---|
| OPTIONAL MATCH (OM1-OM7) | 7 | | |
| Aggregation (AG1-AG7) | AG3, AG4, AG6 | AG5 (`'x'` sums as 0), AG7 (the probed `sum + sum` form departed: bug-cyp-137) | AG1, AG2 (grouping and `count(DISTINCT)` by text: bug-cyp-135) |
| WITH/DISTINCT/ORDER BY/SKIP/LIMIT (WS1-WS7) | 7 | | |
| UNION (UN1-UN3) | UN1, UN3 | UN2 (row count held, value is marked text: bug-cyp-138) | |
| EXISTS (EX1-EX2), comprehensions (PC1-PC3) | EX1, EX2, PC1, PC3 | | PC2 |
| Paths (PA1-PA7) | PA1-PA4, PA6, PA7 | | PA5 |
| DELETE / DETACH / REMOVE (DL1-DL6) | 6 | | |

PC2 and PA5 missed for one reason the owner already stated: `create_edge` deduplicates in multigraph mode too
([structure.multigraph](../../../ontology/features/graph-structure.g5.md#structure.multigraph)). That is a prediction
error, not a finding. Rows and observations: [clauses-PAIRS.md](clauses-PAIRS.md#result-iteration-54-observation-follow-up-after-the-first-observation-and-before-the-deciding-source-was-read-binding-after-it).

After the source read, a probe of the OPTIONAL WHERE placement (prediction written before it ran) held for every
condition on the optional side and departed for two shapes that read an earlier variable (bug-cyp-142, -143).

Native executor: it declined every OPTIONAL MATCH, UNION, EXISTS, comprehension, path function, parameter `LIMIT` and
write; where it answered, it agreed with the SQL path except on grouping (bug-cyp-136).

## Findings (all new; matched by trigger and observable consequence against the register and KNOWN_ISSUES)

| ID | Severity | Trigger → observable | Found by / reproduced by |
|---|---|---|---|
| [bug-cyp-135](../../../Verus_verification/bugs_issues.md#bug-cyp-135) | Medium | grouping key, `count(DISTINCT)`, `WITH DISTINCT` over a stored number and its spelling → one group; `RETURN DISTINCT` keeps two | frozen AG1, AG2 missed / probes, binding `A_*` |
| [bug-cyp-136](../../../Verus_verification/bugs_issues.md#bug-cyp-136) | Medium | one grouped read over mixed stored kinds → SQL 4 groups, native 6 | follow-up native read / binding `A_*_native_group` |
| [bug-cyp-137](../../../Verus_verification/bugs_issues.md#bug-cyp-137) | Medium | `sum(n.v) + sum(n.f)` → `int(round())`: 6.5 answers 6, 2.5 answers 2 | first observation, after the freeze / binding `B_*` |
| [bug-cyp-138](../../../Verus_verification/bugs_issues.md#bug-cyp-138) | Medium | UNION with a stored property → `'\x01N1'`, `'\x01D2.5'`, JSON text; dedup by raw value | UN2 partial / binding `C_*` |
| [bug-cyp-142](../../../Verus_verification/bugs_issues.md#bug-cyp-142) | Medium | OPTIONAL MATCH `WHERE b.v = a.v + 1` or `a.v = 1 OR b.v = 5` → SQLCODE -94, no rows (provider premise P-OUTER-ON) | after the source read / probe, binding `H_*` |
| [bug-cyp-143](../../../Verus_verification/bugs_issues.md#bug-cyp-143) | Medium | OPTIONAL MATCH `WHERE b.v = a.v` → the row of a node without `v` is dropped, not kept with null | after the source read / probe, binding `H_*` |
| [bug-cyp-139](../../../Verus_verification/bugs_issues.md#bug-cyp-139) | Low | SKIP/LIMIT `$p` = `'2'`, true, 2.0 → used as counts; `'x'` raw ValueError; null "not provided" | follow-up / binding `D_*` |
| [bug-cyp-140](../../../Verus_verification/bugs_issues.md#bug-cyp-140) | Low | a whole-label count as a UNION branch → SQLCODE -1 | follow-up / binding `E_*` |
| [bug-cyp-141](../../../Verus_verification/bugs_issues.md#bug-cyp-141) | Low | `startNode`/`endNode` of a `relationships(p)` element → SQLCODE -29 | first observation (`PA4_rels`) / binding `F_*` |

All nine are E2E reproduced on the fixture at the unchanged pin, each with a passing neighbor. Inherited entries
reconciled: none is a duplicate. KNOWN_ISSUES' "A property cannot tell a number from a string" covers filters, sorting
and arithmetic over text, not grouping or DISTINCT; its boolean/list text collision is kept as the documented exception
in the owner and the model. bug-agg-001 (leading grouped OPTIONAL sum) stays its own entry; OM5 confirms the
non-leading OPTIONAL sum is 0. Inherited [aggregate_results](../../../Verus_verification/models/aggregate_results/NOTES.md)
named SQL key equality as a provider premise; this iteration shows it fails for keys of different kinds with equal
text, so that model's grouping correspondence is narrowed to single-kind keys (proofs unchanged).

Question opened: [query.aggregation.keys.numbers](../../../Verus_verification/open_questions.md#query.aggregation.keys.numbers)
(do 1 and 1.0 fall in one group?). Simplifications: none proposed, tested or retired.

## Owners (cypher.g5.md)

New blocks: `query.aggregation.keys` (uncertain, linked to the question), `query.aggregation.arithmetic`,
`query.optional`, `query.paging`, `query.union`, `query.functions.path_elements`,
`query.writes.delete`. Extended metadata: `query.aggregation` (children, findings), `query.values`,
`query.values.equality`, `query.native.equal-answers` (findings back-links), `query.writes` (child). One owner per
commitment; IDs and anchors preserved. Expected results come from the TCK, openCypher, USER_GUIDE, ADMIN_GUIDE,
KNOWN_ISSUES and the existing owners; none comes from a preferred repair. `check_ontology.py`: 398 blocks (391 before),
0 issues, 17 writing warnings (unchanged).

## Model

| Model | Verified | Controls | Binding |
|---|---|---|---|
| [`cypher_clauses`](../../../Verus_verification/models/cypher_clauses/NOTES.md) (new) | 26 ([prove](../../../Verus_verification/results/cypher_clauses/20261117T060139Z-prove/receipt.json)) | 25/25 EXPECTED_FAIL | AGREES 112 ([receipt](../../../Verus_verification/results/cypher_clauses/20261117T060402Z-binding/receipt.json)); 25/25 mutations and tamper detected |

Each section derives the translator's choice from the query shape or the value's provenance (operator and executor;
the column's AST; each branch's decoder; the parameter's kind; the branch shape; how the relationship variable is bound;
the node's edge counts; the OPTIONAL WHERE's shape and whether the earlier node lacks the property). General theorems: `theorem_paths_disagree_exactly_on_marked_text(a, b)` and
`theorem_sql_group_and_distinct_disagree_on_marked_text(a, b)` for every pair of stored values;
`theorem_int_column_loses_any_half(h)` for every odd h; `theorem_union_answers_marked_text(t, rest)` for every value
and branch list; `theorem_delete_follows_rule` for every edge count. Value domains and exclusions are stated in the
NOTES (Float excluded from the grouping rule; UNWIND-list keys observation-only; half-unit totals). Controls include a
repair for every departure that leaves its neighbor verified, the removal of each decisive guard or effect, and two
provider flips. Trust: no `assume`, `admit` or `external_body`; vstd only.

## Recount ([member-delta.json](member-delta.json); `member_reach.py`, denominator 4,130)

Active bindings **603 → 619**; union reach (active plus baseline historical locators) **833 → 847**.
- Newly bound: 16 members. Newly reached: 14 (`translate_return_clause`, `_arith_operand_type`, `_tts_union_branches`,
  `_lone_label_count`, `_translate_to_sql`, `_resolve_pagination_value`, `_validate_pagination_int`,
  `_expr_fn_node_funcs`, `translate_delete_clause`, `translate_where_clause`, `_expr_property_reference`,
  `_null_rejecting_refs` in the translator; `_int_expr_value`; `IRISGraphStore.execute_transaction`). Existing locators gaining a binding: 2 (`_numeric_static_type`,
  `Exec.KeyValues`, both cited by `aggregate_results`).
- Strengthened: `_expr_aggregation`, `Exec.GroupOf` (a new claim beside the inherited one).
- Narrowed: the inherited `aggregate_results` grouping correspondence at the reader (above).
- Lost: 0.

Roles: `_translate_to_sql` is an entry point (it offers every translated query to the label-count shortcut);
`execute_transaction` is bound for one narrow effect (the DELETE sentinel), not as a whole.

**Material predictions gained:** grouping and `count(DISTINCT)` compare text on the SQL path while `RETURN DISTINCT` and
the native executor compare type; arithmetic over property aggregates is rounded half to even; a UNION answers stored
values as storage text and dedups raw values; SKIP/LIMIT parameters of other kinds are counts; a label-count UNION
branch fails; endpoints of a path element fail; an OPTIONAL WHERE reading an earlier variable fails (arithmetic, OR) or drops
nodes without the property; DELETE is refused for incoming-only edges and DETACH clears the native
adjacency (held, now formal). **Withdrawn:** the reading of `aggregate_results` as a grouping claim for mixed-kind keys.

## Correspondence

The [delta from 53](correspondence-delta-from-53.json) is STALE_ALL for proof and correspondence; the changed inputs
are the new model (`cypher_clauses.rs`, `model.json`), its binding, `decision-links.tsv` and `families.tsv` only; no product file changed. The fresh
[stamp](correspondence-inputs.json) checks as REUSABLE_INPUTS.

## Checks (final candidate)

| Check | Result |
|---|---|
| `check_ontology.py` | 398 blocks, 0 issues, 17 warnings (unchanged) |
| `check_findings.py` (`verification_root=.g5/Verus_verification`, `--previous` the pre-edit copy) | No problems found |
| `check_evidence.py` | FRESH |
| `check_consolidated.py` (G5_GUIDE set) | PASS (926 decision links resolve; statements 398 rows; correspondence stamp REUSABLE_INPUTS) |
| Product diff vs pin | none outside `.g5/`; no untracked file outside `.g5/` |

## Limitations

- **Review:** not independently reviewed; round 3 of the review budget remains.
- **Driver:** every observation is on driver 5.3.2; the TCK's 5.4.x was not available, so a driver-dependent decode
  (for example of `'\x01N1'` in a UNION) is unchecked there. The source shows the decoders are dropped by the
  translator, so the departure is not expected to depend on the driver.
- **Observed only:** OPTIONAL MATCH's null rows and aggregates (OM1-OM7, held), EXISTS, pattern comprehension, `UNWIND`-list keys, AG5's `'x'` as 0, the
  native decline of a parameter `LIMIT`. The model's transcription covers the branches the probes reach.
- **Repairs:** none was run on the product; controls check the model's direction only.
- **Fixture state:** the probe and binding nodes remain in USER under their fresh prefixes.

## Residual list (first missing step for each)

- **OPTIONAL MATCH in Verus, rest:** the null-row UNION of `translate_return_clause` (`optional_null_row_items`,
  30779-30796) for OM5/OM6, and multi-hop OPTIONAL groups (`_mpt_push_where_into_opt_group`); first step: bind OM5's
  `count(b)`/`count(*)` through `_null_row_aggregate`. The P-OUTER-ON boundary (which ON shapes IRIS refuses) is
  characterized only by the shapes probed; first step: vary the arithmetic and OR forms over one alias.
- **UNWIND-list keys:** model `CY_LIST_KINDS`' flags for grouping and DISTINCT (`[1, '1']` one group, `[1, true]` one
  group but two DISTINCT rows); first step: `_unwound_known_text` and `_bool_flag` at 30650-30690.
- **1 vs 1.0:** the owner decision in `query.aggregation.keys.numbers`.
- **UNION of floats, lists and relationship values:** bind `C_*` cases for the D mark and JSON columns; first step: add
  `Dec::Json` reads to the port.
- **Other clause surfaces not sampled:** `CALL { }` with aggregation over API data, `FOREACH`, `SET +=` over API maps,
  `WITH *`, `ORDER BY` over mixed-kind API values after `WITH`; also driver 5.4.x for bug-cyp-125.
- **Carried:** the iteration-53 residual list and the consolidated queue.

## Cost

About 50 minutes of builder wall clock (05:20 to about 06:10 UTC); no sub-agents. Tokens and currency are not
available to the builder.
