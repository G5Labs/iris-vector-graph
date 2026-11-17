# Iteration 50: repairs from independent review 47-49

Before image: `c648d226` (seal 49 `893b0ca7` plus the master's inventory commit). Product `3eaa79cf` unchanged (nothing
outside `.g5/` differs; `check_consolidated.py` confinement PASS). Native evidence only from `ivg-cont-20261117-iris`,
fresh prefixes `i50_031150_`, `i50b_032546_`, `i50m_…` and the bindings' own fresh tags. Guidance:
`uplift-review.md` (steps 2-4), `Verus/uplift-iteration.md` `7c5f718a…` (unchanged). The question cards in
`open_questions.md` are untouched. No quarantined material (iteration-13 Cypher `MERGE`) and no evaluator-private input
was read.

## Result

Review 47-49 (fresh read-only session `e431ba47`, [copied verbatim](REVIEW-47-49.md)) withheld sign-off on seven material
items. All seven are repaired at their owners, models, bindings and register entries, and every claim was reproduced
afresh on the fixture before it was registered ([dispositions](DISPOSITIONS.md)). Item 4 is partly accepted: one
premise-bound member is now locator-only, two premise constants are replaced by models of the member's own logic, and
three stay active with the provider premise named, because the emitter's choice next to them is modeled.

- **bug-plt-113 corrected** (item 1). The cap `min(max_nodes, ppr_top_k)` is documented intent, so the owner now states
  it. The defects are the edges missing among the answered nodes and the seeds admitted past the cap. The wrong repair
  control `guided-cap-max-nodes` is withdrawn. High is kept. The claim is scoped to the ObjectScript reader.
- **Claims resized** (items 2, 3). bug-cyp-111 is narrowed to lists from a property and to parameter indexes; a
  WITH-held literal list follows the rule. bug-cyp-112 is widened to slices, subscripts and `coalesce`. The model's
  Variable misprediction is fixed: `WITH n.l AS l RETURN reverse(l)` answers the string `'[3,2,1]'`.
- **Two new Medium findings** (items 6, 7): a null run-time index answers the first element (bug-cyp-126); a simple
  CASE over a property or row value coerces across types (bug-cyp-127).
- **bug-cyp-120 widened** (item 5) to plain parameters, the ordinary driver pattern. simp-cyp-102 no longer preserves
  the drop.
- **Minors** handled each: four new Low entries and one Medium (m3), m2 triaged into bug-cyp-125, m7 Sources fixed, m8
  modeled and bound, m9 generalized or labeled, m11 kept in the queue.

## Findings

New (found by the review, reproduced by iteration 50's fresh runs; E2E with a passing neighbor):

| ID | Severity | Trigger → observable | Formal claim |
|---|---|---|---|
| [bug-cyp-126](../../../Verus_verification/bugs_issues.md#bug-cyp-126) | Medium | `l[i]` with a null run-time index (or `l[null]` on a row-held list) → the first element | `theorem_null_index_reads_first_element` |
| [bug-cyp-127](../../../Verus_verification/bugs_issues.md#bug-cyp-127) | Medium | `CASE n.s WHEN 1` with `n.s = '1'` → the WHEN is taken | `theorem_simple_case_coerces_across_kinds` |
| [bug-cyp-128](../../../Verus_verification/bugs_issues.md#bug-cyp-128) | Medium | `SET n.l = [n.a, 1]` or `CREATE (:X {l: [n.a, 1]})` → raw `TypeError`, nothing written | none (probe only) |
| [bug-cyp-129](../../../Verus_verification/bugs_issues.md#bug-cyp-129) | Low | `n.missing[0..2]` → `[]` | `theorem_null_list_slice_is_empty` |
| [bug-cyp-130](../../../Verus_verification/bugs_issues.md#bug-cyp-130) | Low | `trim('\t a \n')` in RETURN/SET → unchanged; a node CREATE strips it | none (probe only) |
| [bug-cyp-131](../../../Verus_verification/bugs_issues.md#bug-cyp-131) | Low | `range(1, 3, s)` with a run-time 1.5 → `[1, 2.5]` | none (integer-step model) |
| [bug-cyp-132](../../../Verus_verification/bugs_issues.md#bug-cyp-132) | Low | `SET r.age = toInteger(r.age)` → refused with a self-contradictory message | none (probe only) |

Changed: bug-plt-113 (expected result, repair, scope, heading), bug-cyp-111 (narrowed), bug-cyp-112 (widened),
bug-cyp-113 (WITH-column claim), bug-cyp-120 (parameters), bug-cyp-125 (m2 triage), bug-plt-114 (general theorem),
bug-srch-107 (a re-insert with an unchanged vector changes cell under cosine/dot), bug-srch-109 (the build's
Euclidean clustering). Simplifications: simp-cyp-101 ("preserve null" corrected), simp-cyp-102 (parameters no longer
exempt; `rel-param-kept` linked); Comparison links moved to this iteration's receipts. Withdrawn: the control
`guided-cap-max-nodes` (not a finding). Questions opened or resolved: none.

## Owners changed

`algorithms.op.subgraph.guided` (statement and bullets), `algorithms.op.subgraph` (metadata), `search.ivf.metric`
(cells), `query.functions.list_index`, `.reverse`, `.dynamic_access`, `.range`, `.slice`, `.strings`, `.random`
(metadata), `query.functions` (Sources), `query.values.conditions` (statement corrected), `query.writes.computed_values`,
`query.writes.retype`, and back-links in `query.values.equality` and `.relationship_text`. IDs preserved;
`check_ontology.py` 377 blocks, 0 issues, 17 writing warnings (unchanged).

## Models

| Model | Verified | Controls | Binding |
|---|---|---|---|
| `cypher_fns` | 16 ([receipt](../../../Verus_verification/results/cypher_fns/20261117T033035Z-prove/receipt.json)) | 13 of 13 EXPECTED_FAIL, each exactly its named theorems | AGREES 103; 13/13 mutations and tamper detected ([receipt](../../../Verus_verification/results/cypher_fns/20261117T033050Z-binding/receipt.json)); native declined all 84 queries |
| `cypher_exprs` | 22 ([receipt](../../../Verus_verification/results/cypher_exprs/20261117T033051Z-prove/receipt.json)) | 22 of 22 EXPECTED_FAIL, exact | AGREES 233; 22/22 and tamper ([receipt](../../../Verus_verification/results/cypher_exprs/20261117T033119Z-binding/receipt.json)) |
| `retrieval_compose` | 35 ([receipt](../../../Verus_verification/results/retrieval_compose/20261117T032018Z-prove/receipt.json)) | 15 of 15 EXPECTED_FAIL, exact | AGREES 45; 15/15 and tamper ([receipt](../../../Verus_verification/results/retrieval_compose/20261117T032153Z-binding/receipt.json)) |
| `ivf_entries` | 19 ([receipt](../../../Verus_verification/results/ivf_entries/20261117T032405Z-prove/receipt.json)) | 7 of 7 EXPECTED_FAIL, exact | AGREES 9; 7/7 and tamper ([receipt](../../../Verus_verification/results/ivf_entries/20261117T032444Z-binding/receipt.json)) |

Trust: no `assume`, `admit` or `external_body`; `vstd` only; binding ports are unverified Python. Retained failures (all
receipts kept):
- `property-to-cy-reverse` survived once: the generalized theorem was vacuous under the control. It is now stated per
  argument kind.
- Three `cypher_exprs` controls failed the new switch theorem unnamed; they now name it.
- The worker's `seeds-capped` was FAIL_ELSEWHERE (the claim sat in a lemma), `edges-among-answered` failed five
  theorems with four named, and several prove runs were UNEXPECTED on stale expected counts
  ([retrieval-repairs.md](retrieval-repairs.md)).
- The first reproduction run lost its setup node ([failed-runs/](failed-runs/)).

## Recount ([member-delta.json](member-delta.json); `member_reach.py`, denominator 4,130)

Active bindings **503 → 505**.
- **Gained (3):** `translator.py::_is_row_list_elem` (the WITH-literal path, item 2), `::_container_kind` (reverse's
  list knowledge, item 3), `::_static_value_kind` (simple CASE's static kind, item 7).
- **Lost (1):** `translator.py::_scalar_numeric_and_datetime`, reclassified locator-only (`cites`) under item 4. The
  once-per-statement value is an observed IRIS premise, not a decision this member makes. This loss is correct
  accounting, not a regression.
- **Strengthened (12):** `IVFIndex.cls::AddBatch`, `Build`, `Insert`; `Subgraph.cls::SubgraphJson`;
  `kg_PPR_GUIDED_SUBGRAPH`; `kg_SUBGRAPH`; `ivf_build`; `_create_clause_relationship_entry`; `_expr_case`;
  `_expr_subscript`; `_slice_sql`; `IRISGraphEngine._prop_set_deployed`.
- **Same row, new formal basis:** `Parser.parse_primary_expression` (tokens instead of a constant) and
  `kg_VECTOR_GRAPH_SEARCH` (transcribed truncation instead of `truncate_first()`).
- **New locator-only rows:** `ArnoAccel.cls::SubgraphNativeJson`, `_translate_set_value`, and `_scalar_string`'s trim
  row.

Material predictions changed:
- **Withdrawn:** the claim that a run-time index into a WITH-held literal list fails or answers text; the list predicted
  for `reverse()` of a WITH column from a property; "the cap is the defect".
- **Gained:** a null index answers the first element; simple CASE coerces; a parameter on a relationship CREATE is
  dropped; Insert's cell can differ from the build's; the seeds can exceed the cap.

Correspondence: [delta from 49](correspondence-delta-from-49.json) is STALE_ALL for proof and correspondence, by design.
Four models' formal inputs, their bindings, the crosswalk and the families changed; no product file changed. A fresh
[stamp](correspondence-inputs.json) checks as REUSABLE_INPUTS.

Checks:
- `check_evidence.py`: FRESH.
- `check_findings.py` (`verification_root=.g5/Verus_verification`, with the pre-edit snapshot): no problems.
- `check_ontology.py`: 0 issues.
- `check_consolidated.py` (G5_GUIDE set): PASS.
- `link_verification.py`: not applicable (no TLA models).

## Residual list (first missing step for each)

From this review:
- **Arno reader for bug-plt-113/-114.** First step: a fixture with Arno loaded and the same star graph.
- **bug-cyp-125 and m2 on driver 5.4.x.** First step: run the same three slices under 5.4.0. The null-guard marker
  order (`translator.py:23778-23789`) is a driver-independent fault to confirm then.
- **Probe-only findings** bug-cyp-128, -130, -131 and -132 have no Verus claim. First step: a list-literal SET
  section in `cypher_exprs`, the trim whitespace sets, a fractional `range` step and the relationship SET shapes.
- **Untested neighbors:** a simple CASE with a parameter test or a property WHEN; reverse of a CASE whose list kind is
  unknown; the multigraph relationship CREATE branch with a parameter.
- **Provider premises** (`driver_accepts_ast`, `iris_accepts_scalar_condition`, `filer_writes_same_text`, the k-means
  labels, PPR scores) are observed on IRIS 2026.1 and driver 5.3.2 only.
- **m11** (unchanged): `ivg.retrieve` as a fusion entry point; `c = -rank` dividing by zero; `/hybridSearch` k=0 → 50;
  the fusion IVF leg's fixed `nprobe` of 8; the PPR walk ignoring `edge_types`.

Carried: the iteration-49 residual list and the consolidated queue.

## Cost

About 30 minutes of builder wall clock (03:09 to roughly 03:40 UTC), with a parallel worker for the retrieval/IVF half
(about 15 minutes). Tokens and currency are not available to the builder.

## Independent review

This iteration *is* the repair round for review 47-49 (round 1 of this run). The repairs were not independently
re-reviewed. For the next reviewer:
- reproduce `cypher_fns` `null-index-is-null` and `cypher_exprs` `case-kinds-compared`;
- check that the binding's `prop_set_switch_Absent` (an engine with a non-existent IVG Schema) is a fair stand-in for
  a namespace without `Prop_Set`;
- check that keeping `driver_accepts_ast`, `iris_accepts_scalar_condition` and `filer_writes_same_text` active is
  justified by the modeled emitter choices beside them.
