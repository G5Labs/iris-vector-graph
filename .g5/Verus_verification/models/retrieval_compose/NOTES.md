# Composed retrieval (W56)

Product `3eaa79cf`, unchanged. Iteration 49 (continuation). Predictions frozen from the API reference, KNOWN_ISSUES,
the admin guide and the owners before the deciding source was read:
[retrieval-PAIRS.md](../../../uplift/consolidated/iteration-49/retrieval-PAIRS.md). Owners:
[search.fusion.surfaces](../../../ontology/features/search.g5.md#search.fusion.surfaces),
[.leg_index](../../../ontology/features/search.g5.md#search.fusion.leg_index),
[.vector_graph](../../../ontology/features/search.g5.md#search.fusion.vector_graph),
[.rest](../../../ontology/features/search.g5.md#search.fusion.rest),
[.multi_vector](../../../ontology/features/search.g5.md#search.fusion.multi_vector),
[search.fusion.failed_leg](../../../ontology/features/search.g5.md#search.fusion.failed_leg) (engine half),
[algorithms.op.subgraph](../../../ontology/features/algorithms.g5.md#algorithms.op.subgraph) and
[algorithms.op.subgraph.guided](../../../ontology/features/algorithms.g5.md#algorithms.op.subgraph.guided).

## What the model decides (each decision derived from the inputs, never supplied)

| Distinction | Spec function(s) | Theorems (neighbor first) | Control that must fail |
|---|---|---|---|
| Absent item: engine `len + c`, SQL procedure and `FuseRanks` 10^9, `RRFFusion` 0 | `absent_place`, `part`, `rrf` | `theorem_both_legs_rank10_wins_everywhere`; `theorem_engine_absent_rank_reorders` (fixture legs: x 31st vs 61st), `theorem_engine_absent_depends_on_length`, `theorem_engine_skipped_leg_adds_constant` | `engine-absent-zero` (3 theorems), `sql-absent-like-engine` |
| Failed vs empty vector leg (one `try`) | `engine_fuse` | `theorem_failed_vector_leg_reads_as_no_match` (empty leg → text ranking; failed → []) | `vector-failure-isolated` |
| Which vector index the engine reads | `ivf_scope_seen`, `leg_index`, `above` | `theorem_other_graph_ivf_not_read`; `theorem_fused_leg_depends_on_building_engine` | `ivf-scope-persisted`, `hnsw-before-own-ivf`, `ivf-cosine-normalized` |
| `/hybridSearch` constant | `hybrid_c` | `theorem_hybrid_c_zero_becomes_60` | `hybrid-c-kept` |
| `/vectorSearch` width before route | `pyops_expected`, `pyops_vector_search`, `engine_knn` | `theorem_unrouted_rest_search_refuses_width` (768-wide and routed neighbors inside) | `unrouted-no-width-check` |
| `kg_VECTOR_GRAPH_SEARCH` truncation | `index_of`, `answered` | `theorem_k_covering_set_keeps_best`; `theorem_best_hit_can_be_dropped` | `sort-before-truncate` |
| Its flags and scores | `in_graph_expansion`, `vector_similarity` | `theorem_expansion_flag_and_text_only_zero` | `expansion-flag-excludes-hits` |
| `SubgraphJson` BFS, edge before cap test | `expand_node`, `expand_frontier` | `theorem_last_hop_edges_missing`, `theorem_capped_subgraph_lists_edge_to_unlisted_node` | `edge-recorded-after-cap-test` |
| Guided cap | `guided_cap` | `theorem_guided_cap_is_ppr_top_k`, `theorem_guided_subgraph_drops_edges_among_top_nodes` | `guided-cap-max-nodes` (2 theorems) |
| Failing `multi_vector_search` source | `mvs_rows` | `theorem_failed_source_skipped` | none (a transcription of the skip; M1 observed) |

28 verified ([receipt](../../results/retrieval_compose/20261117T024512Z-prove/receipt.json)); 12 of 12 controls
EXPECTED_FAIL, each failing exactly its named theorems (the whole-file error count equals the named count) while
the neighbors verify.

## Binding

[binding.py](binding.py) runs the product on fresh data and feeds the legs, adjacency, Python set orders and PPR
scores the product itself reports into Python ports of the spec functions: **AGREES 41 cases**; all 12 mutations
(mirroring the controls) detected; altering x's observed engine score is detected
([receipt](../../results/retrieval_compose/20261117T024807Z-binding/receipt.json)). Contrasts at the readers: x is
31st in engine `kg_RRF_FUSE` and 61st in `PyOps.HybridSearch` on the same legs; L is 31st in the building engine
and 62nd in a fresh engine and `IRISGraphOperators`; the best vector hit is missing for 7 of 8 hash seeds at k = 2;
`kg_PPR_GUIDED_SUBGRAPH(ppr_top_k=7)` answers 7 nodes with the single edge a1 → a2.

Readers: engine and `IRISGraphOperators` return values, the SQL procedure's rows, `Graph.KG.PyOps` class methods
called through the native API (the REST web application was not deployed). Delegating members bound with a stated
role: `kg_RERANK` (fixes c = 60 and 2 × `top_n`), `IRISGraphOperators.kg_RRF_FUSE` (defaults, `'[]'`),
`.kg_VECTOR_GRAPH_SEARCH` (k selection), `.kg_PPR_GUIDED_SUBGRAPH` (argument names), `.__init__` (its own engine),
`IRISGraphStore.execute_subgraph` and `kg_SUBGRAPH` (forward the cap). Excluded as trivial forwards for this scope:
`IRISGraphOperators.kg_KNN_VEC`, `.kg_TXT`, `.kg_NEIGHBORHOOD_EXPANSION`, `.kg_SUBGRAPH`, `.kg_MENTIONS`, `.kg_PPR`,
`.kg_RERANK`, and `kg_MENTIONS` (observed equal to `kg_NEIGHBORS` along the predicate). Provider inputs, not derived:
`kg_KNN_VEC`, `bm25_search`, `kg_TXT`, `ivf_search` scores, Python's set order, PPR scores.

## Limits and premises

- Exact real arithmetic for the fused scores; Python floats and IRIS decimals are compared to 2e-9 in the binding.
  Ties are not claimed (none occur in the chosen legs except foreign default-graph rows, compared by score).
- The model's set order is any sequence; that Python's set order varies by hash seed is observed, not proved.
- `ReadRows`, `ReadFailure`, `Lacks`, `NoteNoRegistry` (privilege and failure reporting), `MetaPath`, `kg_PPR`'s
  sort and `kg_TXT`'s term counting are not modeled. `kg_BM25`-style scoring is a provider.
- Premise: the `hnsw` registry entry exists only when `_probe_native_vec` finds `VECTOR_COSINE` (true on the fixture, recorded as `hnsw_present` in the binding). Without it, a fresh engine reads an unknown-scope IVF index (`theorem_other_graph_ivf_not_read`'s third clause).
- The SQL procedure was exercised on the default graph only (a named graph with a route is refused by design).
- Trust: no `assume`, `admit` or `external_body`; `vstd` only; the binding ports are unverified Python.
  implementation-verified 0.
