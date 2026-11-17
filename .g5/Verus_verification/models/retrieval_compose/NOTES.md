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
| `kg_VECTOR_GRAPH_SEARCH` truncation | `index_of`, `answered` (transcribed `[:k]` before the sort; iteration 50 removed the premise constant `truncate_first()`), `rule_answered` | `theorem_k_covering_set_keeps_best`; `theorem_best_hit_can_be_dropped` | `sort-before-truncate` (now changes the transcribed order of operations) |
| Its flags and scores | `in_graph_expansion`, `vector_similarity` | `theorem_expansion_flag_and_text_only_zero` | `expansion-flag-excludes-hits` |
| `SubgraphJson` seeds, BFS, edge before cap test, and what the answer lists | `admit`, `expand_node`, `expand_frontier`, `lists_edge`; rule `rule_lists_edge`, `rule_within_cap` | general: `theorem_capped_subgraph_lists_edge_to_unlisted_node`, `theorem_filled_cap_expands_only_first_node`, `theorem_admitted_seeds_ignore_cap`; witness: `theorem_last_hop_edges_missing` | `edge-recorded-after-cap-test`, `edges-among-answered`, `seeds-capped`, `expand-whole-frontier-at-cap` |
| Guided cap (documented) and its answer | `guided_cap` | general: `theorem_guided_cap_is_ppr_top_k` (min for every input); witnesses: neighbor `theorem_guided_uncapped_lists_all_edges`, `theorem_guided_subgraph_drops_edges_among_top_nodes`, `theorem_guided_seeds_exceed_cap` | `guided-cap-top-k-only`, `edges-among-answered`, `seeds-capped`, `expand-whole-frontier-at-cap` |
| Failing `multi_vector_search` source | `mvs_rows` | `theorem_failed_source_skipped` | none (a transcription of the skip; M1 observed) |

Iteration 49: 28 verified ([receipt](../../results/retrieval_compose/20261117T024512Z-prove/receipt.json)); 12 of 12
controls EXPECTED_FAIL. **Iteration 50: 35 verified** ([receipt](../../results/retrieval_compose/20261117T032018Z-prove/receipt.json));
**15 of 15 controls EXPECTED_FAIL** (`results/retrieval_compose/20261117T0320*-control-*`, `20261117T0321*-control-*`),
each failing exactly its named theorems (the whole-file error count equals the named count) while the neighbors verify.

## Iteration 50: repairs from review 47-49

- **bug-plt-113 corrected (item 1).** The cap `min(max_nodes, ppr_top_k)` is documented intent (docstring
  `algorithms.py:956-957`; the design note's `top_k` "hard node cap" and "`len(result.nodes) <= top_k` always"). The
  iteration-49 control `guided-cap-max-nodes` encoded the wrong repair (pass `max_nodes`); it is withdrawn from
  `model.json` (its receipts stay as history, e.g. `results/retrieval_compose/20261117T0245*-control-guided-cap-max-nodes`).
  The model now states the documented answer (`rule_lists_edge`: every edge between two answered nodes;
  `rule_within_cap`) and derives two departures: `admit` takes every seed with an edge whatever the cap
  (`theorem_admitted_seeds_ignore_cap`, witness `theorem_guided_seeds_exceed_cap`: seeds s, a3, a4 and `ppr_top_k = 1`
  give 3 nodes and no edge), and once the seeds fill the cap only the first frontier node is expanded
  (`theorem_filled_cap_expands_only_first_node`, witness `theorem_guided_subgraph_drops_edges_among_top_nodes`).
  Repairs as controls: `edges-among-answered` (the answer lists every edge among its nodes; also repairs bug-plt-114),
  `seeds-capped`; effects: `expand-whole-frontier-at-cap`, `guided-cap-top-k-only`. Scope: the ObjectScript Owner
  `SubgraphJson`; with Arno loaded and no `edge_types`, `execute_subgraph` asks `ArnoAccel.SubgraphNativeJson` first
  (`iris_sql_store.py:2526-2541`), which is not modeled (no Arno on the fixture).
- **m9.** `theorem_capped_subgraph_lists_edge_to_unlisted_node`, `theorem_guided_cap_is_ppr_top_k` and
  `theorem_hybrid_c_zero_becomes_60` now hold for every input; the star theorems are labeled witnesses and the general
  claims carry the rule. One failing run is kept: the first `seeds-capped` run (`20261117T031931Z`) was FAIL_ELSEWHERE
  because the claim sat in a helper lemma; the theorem now carries its own induction.
- **Item 4.** `truncate_first()` (a premise constant) is gone: `answered` transcribes `list(set(...))[:k]` and
  `rule_answered` is the ranked alternative; `sort-before-truncate` now changes the transcription.
  `PyOps.getDefaultDimension` stays a directly transcribed constant (its whole body is `Quit 768`).

## Binding

[binding.py](binding.py) runs the product on fresh data and feeds the legs, adjacency, Python set orders and PPR
scores the product itself reports into Python ports of the spec functions: iteration 49 **AGREES 41 cases**
([receipt](../../results/retrieval_compose/20261117T024807Z-binding/receipt.json)); iteration 50 **AGREES 45 cases**,
all 15 mutations detected, tamper detected ([receipt](../../results/retrieval_compose/20261117T032153Z-binding/receipt.json)),
adding `guided_more`: seeds s+a3+a4 and a3+a4+a5 with `ppr_top_k = 1` (3 nodes over a cap of 1, no edges) and [s] with
`ppr_top_k = 50` under `max_nodes` 3 (7 nodes, only a1→a2) and 5000 (all 7 edges); `contrasts.rule_departures` lists
the edges among answered nodes that are missing and whether the answer exceeds the cap. Contrasts at the readers: x is
31st in engine `kg_RRF_FUSE` and 61st in `PyOps.HybridSearch` on the same legs; L is 31st in the building engine
and 62nd in a fresh engine and `IRISGraphOperators`; the best vector hit is missing for 7 of 8 hash seeds at k = 2;
`kg_PPR_GUIDED_SUBGRAPH(ppr_top_k=7)` answers 7 nodes with the single edge a1 → a2; with three seeds and `ppr_top_k=1`, 3 nodes and no edge.

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
- Trust: no `assume`, `admit` (the verifier keyword; the spec function `admit` is the seed loop) or `external_body`; `vstd` only; the binding ports are unverified Python.
  implementation-verified 0.
