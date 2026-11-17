# Iteration 49: composed retrieval — legs → fusion / expansion / subgraph → returned answer (W56)

Before image: `e5f61f45` (seal 48 `9f526f1b` plus the master's inventory commit). Product `3eaa79cf` unchanged
(nothing outside `.g5/` differs from `e5f61f45`; `iris_vector_graph`, `iris_src`, `api`, `tests`, `docs` equal the pin;
`check_consolidated.py` PASS). Native evidence only from `ivg-cont-20261117-iris`, fresh prefixes and graphs per run
(`i49_023944_…`, `i49_024059_…`, `i49_024208_…`, binding `i49b_024741_…`). Guidance: `Verus/uplift-iteration.md` sha256
`7c5f718a88badf0202d91cd1d557ff2dd2f2bab8bc25178dccf852143e913b12` (unchanged). The question cards in
`open_questions.md` are untouched; HD-0603 and HD-0702 gained an evidence paragraph above their cards (additive).

## Result

Predictions for 25 cases across seven workflows were frozen and committed (`f45bad12`) before the deciding source was
read ([PAIRS](retrieval-PAIRS.md)): **18 held, 4 partial, 3 missed**. Source reading and three probes then produced one
High and one Medium defect that no prediction named, confirmed the inherited suspected bug-srch-005 at the real readers,
and showed that the engine's fusion answer depends on which process built the IVF index. New model
`retrieval_compose` (28 verified, 12 of 12 controls EXPECTED_FAIL, binding AGREES 41 cases). Six new owner blocks.
Active bindings **480 → 503**.

What decides the ranking a retrieval caller sees? Four things the docs do not say: the entry point's rule for an item
one leg lacks (engine `len + c` versus 10^9 in SQL/`/hybridSearch`; same legs, the vector-only item is 31st versus
61st); which engine object built an IVF index (the builder reads it, everyone else reads HNSW); Python's set order in
`kg_VECTOR_GRAPH_SEARCH` (the best hit is dropped for most hash seeds at small k); and, for the PPR-guided subgraph, a
cap equal to `ppr_top_k` that the seeds already fill, so the edges are almost all lost.

## Predictions held and missed

| Workflow | Held | Partial | Missed |
|---|---|---|---|
| Fusion across surfaces F1-F8 | F1, F2, F4, F5, F6, F8 | F3 (order held; every row carries +1/(2c)), F7 (held for the building engine; a fresh engine and the operators read HNSW) | F1b (the engine puts the vector-only item above one ranked 50th in both legs) |
| `kg_VECTOR_GRAPH_SEARCH` V1-V5 | V1, V2, V3 (follow-up 2's design; the first probe's text node was also a vector hit), V5 | | V4 (`in_graph_expansion` is true for a vector hit an edge also reaches) |
| PPR-guided subgraph P1-P4 | P2, P3, P4 | | P1 (capped at `ppr_top_k` nodes; edges among them lost) |
| Rerank and PPR R1-R2 | R1, R2 | | |
| `multi_vector_search` M1-M3 | M1, M3 | M2 (weights ignored outside RRF, as "raw score" says) | |
| `PyOps` routing Y1 | | Y1 (768-wide held; another width is refused) | |
| `kg_MENTIONS` N1 | N1 | | |

Not frozen (found after the freeze): bug-plt-114 (traced from P1's miss into `SubgraphJson`), bug-srch-112 (source
reading of `HybridSearch`). Set aside: `CALL ivg.retrieve` (owned, bug-srch-008, not re-probed), `bfs_vector_rerank`
and `search_nodes_by_vector` (not reached; residual), `PyOps.MetaPath` (not reached).

## Findings

New (discovered here; E2E reproduced on the fixture with a passing neighbor unless noted):

| ID | Severity | Trigger → observable | Formal claim |
|---|---|---|---|
| [bug-plt-113](../../../Verus_verification/bugs_issues.md#bug-plt-113) | High | `kg_PPR_GUIDED_SUBGRAPH` when the walk reaches ≥ `ppr_top_k` nodes (always with the default 50 on an ordinary graph) → the top nodes with only the first node's out-edges | `theorem_guided_subgraph_drops_edges_among_top_nodes` |
| [bug-srch-110](../../../Verus_verification/bugs_issues.md#bug-srch-110) | Medium | engine `kg_RRF_FUSE` after `ivf_build(metric="cosine")` → the building engine ranks a long vector 31st, a fresh engine and `IRISGraphOperators` 62nd | `theorem_fused_leg_depends_on_building_engine` |
| [bug-plt-114](../../../Verus_verification/bugs_issues.md#bug-plt-114) | Medium | `kg_SUBGRAPH` → an edge between outermost nodes missing; at the cap an edge to an unlisted node listed; an isolated seed dropped | `theorem_last_hop_edges_missing`, `theorem_capped_subgraph_lists_edge_to_unlisted_node` |
| [bug-srch-111](../../../Verus_verification/bugs_issues.md#bug-srch-111) | Low | `PyOps.VectorSearch`/`HybridSearch` for a graph with no route and a query not 768 wide → width error (engine: empty) | `theorem_unrouted_rest_search_refuses_width` (partially reproduced: class method, not HTTP) |
| [bug-srch-112](../../../Verus_verification/bugs_issues.md#bug-srch-112) | Low | `PyOps.HybridSearch(c=0)` → c = 60 | `theorem_hybrid_c_zero_becomes_60` (partially reproduced) |

Inherited and reconciled: [bug-srch-005](../../../Verus_verification/bugs_issues.md#bug-srch-005) (suspected, partial)
is now **E2E reproduced** at the engine and `/hybridSearch` readers with a passing neighbor; severity stays Medium (a
wrong ranking, consistent with bug-srch-109). The KNOWN_ISSUES failed-leg entry and bug-srch-010 (engine answers [] on a
failed vector leg) are now formally represented for the engine (`theorem_failed_vector_leg_reads_as_no_match`) and
observed; F-0709 (the Python wrapper's dropped failure) is unchanged and still owned by `search.fusion.failed_leg`.
HD-0603's set-order truncation is observed at the reader (7 of 8 hash seeds drop the best hit at k = 2). bug-srch-109
now has a second reader (the building engine's fusion). Withdrawn: none. Simplifications: none new (simp-srch-001
still covers the absent-rank repair; the control `engine-absent-zero` checks it in the model only). Questions opened or
resolved: none.

## Owners changed

New: [search.fusion.surfaces](../../../ontology/features/search.g5.md#search.fusion.surfaces),
[search.fusion.leg_index](../../../ontology/features/search.g5.md#search.fusion.leg_index) (D),
[search.fusion.vector_graph](../../../ontology/features/search.g5.md#search.fusion.vector_graph),
[search.fusion.rest](../../../ontology/features/search.g5.md#search.fusion.rest),
[search.fusion.multi_vector](../../../ontology/features/search.g5.md#search.fusion.multi_vector),
[algorithms.op.subgraph.guided](../../../ontology/features/algorithms.g5.md#algorithms.op.subgraph.guided). Extended
additively: `algorithms.op.subgraph` (two "Today" bullets, sources, model link), `search.fusion` (children, iteration-49
note), `search.fusion.failed_leg` (engine Verus line), `search.ivf.metric` and `search.routes.no_fallback` (findings
back-links). IDs preserved; `check_ontology.py` 377 blocks, 0 issues, 17 writing warnings (unchanged).

## Model

| Model | Verified | Controls | Binding |
|---|---|---|---|
| `retrieval_compose` (new) | 28 ([receipt](../../../Verus_verification/results/retrieval_compose/20261117T024512Z-prove/receipt.json)) | 12 of 12 EXPECTED_FAIL; each fails exactly its named theorems, neighbors verify | AGREES 41 cases; 12 of 12 mutations and the tamper check detected ([receipt](../../../Verus_verification/results/retrieval_compose/20261117T024807Z-binding/receipt.json)) |

Each decision is derived inside the model from inputs: the surface decides the absent place, the leg outcomes decide
the fusion's shape, the building engine decides the IVF scope and the scope decides the leg, the route and query width
decide the REST outcome, the candidate order and k decide what is kept, the frontier order, adjacency and cap decide
the subgraph. Controls: 6 repairs of a decision (`engine-absent-zero`, `vector-failure-isolated`, `hybrid-c-kept`,
`unrouted-no-width-check`, `sort-before-truncate`, `guided-cap-max-nodes`), 3 alternative decisions
(`sql-absent-like-engine`, `hnsw-before-own-ivf`, `expansion-flag-excludes-hits`), 2 effect removals
(`ivf-scope-persisted`, `edge-recorded-after-cap-test`), 1 provider repair (`ivf-cosine-normalized`).
`theorem_failed_source_skipped` has no control (a transcription). Provider inputs not derived: the legs' rows, Python's
set order, PPR scores. Trust: no `assume`, `admit` or `external_body`; `vstd` only; the binding ports are unverified
Python. Retained failures: the first binding run aborted on a symlinked repository path before writing a receipt (the
product calls had completed; fixed by resolving the path); the first probe's `multi_vector_search` cases passed bare
route names (the generic helper resolved them in SQLUser) and were redone in follow-up 2.

## Recount ([member-delta.json](member-delta.json); `member_reach.py`, denominator 4,130)

Active bindings **480 → 503**. Newly reached and bound: 23 — `vector.py::VectorMixin.kg_RRF_FUSE`, `._fusion_leg_index`,
`._index_graph`, `._index_graph_scopes`, `.kg_VECTOR_GRAPH_SEARCH`, `.multi_vector_search`;
`algorithms.py::AlgorithmsMixin.kg_PPR_GUIDED_SUBGRAPH`, `.kg_SUBGRAPH`, `.kg_RERANK`;
`operators.py::IRISGraphOperators.__init__`, `.kg_RRF_FUSE`, `.kg_VECTOR_GRAPH_SEARCH`, `.kg_PPR_GUIDED_SUBGRAPH`;
`stores/iris_sql_store.py::IRISGraphStore.execute_subgraph`; `Subgraph.cls::SubgraphJson`; `PyOps.cls::FuseRanks`,
`HybridSearch`, `VectorSearch`, `vectorToJson`, `getExpectedDimension`, `getVectorTable`, `getDefaultDimension`,
`RouteVectorRows`. Strengthened: 3 — `VectorMixin.ivf_build` (writer of the per-engine scope), `VectorMixin.ivf_search`
(the leg the building engine reads), `GraphSchema.get_procedures_sql_list` (the SQL `kg_RRF_FUSE` body's 10^9). Overlap
0; distinct additions 26; lost 0.

Roles: deciding (`kg_RRF_FUSE`, `_fusion_leg_index`, `_index_graph`, `kg_VECTOR_GRAPH_SEARCH`, `multi_vector_search`,
`kg_PPR_GUIDED_SUBGRAPH`, `SubgraphJson`, `FuseRanks`, `HybridSearch`, `vectorToJson`, `getExpectedDimension`,
`RouteVectorRows`, `IRISGraphOperators.__init__`), state and writer (`_index_graph_scopes`, `ivf_build`), providers with
a stated role (`getVectorTable`, `getDefaultDimension`, `ivf_search`), delegating with a justified shared relation
(`kg_RERANK` fixes c and depths; `IRISGraphOperators.kg_RRF_FUSE` defaults; `.kg_VECTOR_GRAPH_SEARCH` k selection;
`.kg_PPR_GUIDED_SUBGRAPH` renames; `execute_subgraph` and `kg_SUBGRAPH` forward the cap), entry (`VectorSearch`).
Excluded as trivial forwards: `IRISGraphOperators.kg_KNN_VEC`, `.kg_TXT`, `.kg_NEIGHBORHOOD_EXPANSION`, `.kg_SUBGRAPH`,
`.kg_MENTIONS`, `.kg_PPR`, `.kg_RERANK`, `AlgorithmsMixin.kg_MENTIONS` (N1 observed equal to `kg_NEIGHBORS`). Unassessed:
`PyOps.ReadRows`, `ReadFailure`, `Lacks`, `NoteNoRegistry`, `MetaPath`, `getVectorColumn`, `getLegacyVectorTable`,
`AlgorithmsMixin.kg_PPR` (R2 observed, not modeled), `VectorMixin.kg_TXT`, `bm25_search` (providers).

New formal distinctions: absent place by surface; failed versus empty vector leg (engine); IVF scope by engine instance
and the leg it selects; REST width-before-route; `c` 0 → 60; truncation before sort; expansion flag on vector hits;
subgraph edge recording and cap. Correspondence confirmed at the reader for each (binding cases); none withdrawn.
Material predictions gained: F1b, F7 (fresh half), V4, P1, Y1 (4-wide) now have a formal claim that rejects the
outcome the product does not give; F3's value departure is `theorem_engine_skipped_leg_adds_constant`.

Correspondence: [delta from 48](correspondence-delta-from-48.json) (proof and correspondence STALE_ALL by design: the new
model's formal inputs, its binding, the crosswalk and families changed; no product file changed); fresh
[stamp](correspondence-inputs.json) (`check` → REUSABLE_INPUTS). `check_evidence.py` FRESH. `check_findings.py` no
problems (with the pre-edit snapshot); `check_consolidated.py` PASS (G5_GUIDE set). `link_verification.py` not
applicable (no TLA models).

## Residual list (first missing step for each)

W56, open:
- REST layer: `Graph.KG.Service` was not deployed, so bug-srch-111/-112 are partially reproduced. First missing step:
  `CreateWebApp` on the fixture and the same two calls over HTTP.
- `PyOps.ReadRows`/`ReadFailure`/`Lacks`/`NoteNoRegistry` (privilege and missing-registry reporting): first missing step
  is a read-only probe as a second IRIS user lacking SELECT on a route (security-adjacent; defensive scope only).
- `PyOps.MetaPath` (`/metaPath` → `Traversal.BFSJSON`), `bfs_vector_rerank`, `search_nodes_by_vector`: not probed; first
  missing step is predictions from the API reference and admin guide.
- Engine `kg_RRF_FUSE` with duplicate IVF entries (bug-srch-107's stale copy): source reading shows `vec_rank` keeps the
  **last** occurrence (and `dict(vec_results)` its last score) while `FuseRanks` keeps the first. First missing step: a
  cross-cell re-insert into the IVF index the building engine's fusion reads.
- Ties in engine fusion follow Python set order (not claimed); `CALL ivg.retrieve` (0 absent) not re-probed this
  iteration; `vector_search`'s IVF fallback still unexercised (the fixture supports `VECTOR_COSINE`).
- `kg_PPR` (sorted list including zero scores, default graph only) observed, not modeled; `kg_PPR_GUIDED_SUBGRAPH` and
  `kg_SUBGRAPH` read the default graph only (no `graph=`), not separately owned beyond the subgraph bullet.

Carried: the iteration-48 residual list (Cypher write values, bug-cyp-125 on driver 5.4.x, SqlProcs `MatchEdges` /
`DijkstraPath` / `backfill_temporal_rows` / `rebuild_edge_indices`, `kg_BM25`, percentiles, the 12 SQL-only `CypherFn`
bodies).

Set aside: none of the quarantined material was opened (no iteration-13 Cypher `MERGE` material); no evaluator-private
input was read.

## Cost

Builder wall clock about 30 minutes (02:29-02:59 UTC, from the first command to the seal); tokens and currency not
available to the builder. Proof under 1 s, the 12-control suite about 25 s, the binding about 11 s plus eight one-seed
subprocesses.

## Independent review

Not performed in this iteration (no separate reviewer was started). For a reviewer: reproduce `retrieval_compose` prove,
`CONTROL=guided-cap-max-nodes`, and its binding (runbook "Continuation on Linux", iteration 49); attack first whether the
binding's `subgraph` port matches `SubgraphJson`'s loop exits, whether bug-plt-113's High severity is warranted for a
retrieval helper, and whether `theorem_fused_leg_depends_on_building_engine` should name the hnsw probe
(`_probe_native_vec`) as a premise.
