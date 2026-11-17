# W56: composed retrieval — legs → fusion / expansion / rerank → returned ranking (frozen predictions)

Frozen 2026-11-17T02:36Z, **before** reading the deciding source of `_engine/vector.py` (`kg_RRF_FUSE`,
`kg_VECTOR_GRAPH_SEARCH`, `multi_vector_search`, `kg_TXT`), `_engine/algorithms.py` (`kg_PPR_GUIDED_SUBGRAPH`,
`kg_RERANK`, `kg_PPR`, `kg_MENTIONS`), `operators.py`, `iris_src/src/Graph/KG/PyOps.cls` or the SQL `kg_RRF_FUSE` body
in `schema.py`. Sources used: `docs/API_REFERENCE.md` (engine and `IRISGraphOperators` entries), `docs/KNOWN_ISSUES.md`
(the `kg_RRF_FUSE` failed-leg entry and the SQL-procedures-read-default-graph entry), `docs/ADMIN_GUIDE.md`
(`Graph.KG.Service` routes), `docs/migration/v4.0.0.md`, and the owners
[search.fusion](../../../ontology/features/search.g5.md#search.fusion) (and `.same_graph`, `.failed_leg`, `.python`),
[search.knn](../../../ontology/features/search.g5.md#search.knn),
[search.routes.no_fallback](../../../ontology/features/search.g5.md#search.routes.no_fallback),
[search.scope.indexes](../../../ontology/features/search.g5.md#search.scope.indexes),
[search.ivf.metric](../../../ontology/features/search.g5.md#search.ivf.metric),
[algorithms.op](../../../ontology/features/algorithms.g5.md#algorithms.op),
[algorithms.op.ppr](../../../ontology/features/algorithms.g5.md#algorithms.op.ppr),
[algorithms.op.subgraph](../../../ontology/features/algorithms.g5.md#algorithms.op.subgraph) and
[algorithms.op.neighbors](../../../ontology/features/algorithms.g5.md#algorithms.op.neighbors).

Prior knowledge carried in (not product observation): the register's suspected bug-srch-005 (engine absent rank
derived from leg length; SQL 1e9; Cypher and `RRFFusion` 0), HD-0702, HD-0603 (`kg_VECTOR_GRAPH_SEARCH` set-order
truncation), q-srch-006 (two text corpora), bug-srch-010 / KNOWN_ISSUES (failed leg answers `[]`), bug-srch-109 (IVF
"cosine" = dot). Where the owner/doc text and a suspected finding disagree, the prediction follows the **owner/doc
text** and the row says so; a departure is then a miss of the documented contract, not of the suspicion.

Reader: the Python return value of the engine method and of `IRISGraphOperators`; for SQL, the procedure's rows; for
`PyOps`, the class method's return (the REST route was not deployed on the fixture). Fixture: `ivg-cont-20261117-iris`,
fresh prefix `i49_…`, a dedicated graph per case.

Ranking by consequence: fusion across surfaces first (it decides the final ranking for every hybrid RAG caller), then
`kg_VECTOR_GRAPH_SEARCH` (silent truncation), then `kg_PPR_GUIDED_SUBGRAPH`/`kg_RERANK`, then `multi_vector_search`
and `PyOps` routing.

| ID | Case (changing input) | Neighbor | Predicted |
|---|---|---|---|
| F1 | engine `kg_RRF_FUSE`, c=60, vector leg long (≥ 50 hits); item x only in the vector leg at rank 1; item y in both legs at rank 10 | item y at rank 10 in both legs vs item z at rank 10 in one leg only | owner/API: absent adds 0, so y (2/70 = 0.0286) outranks x (1/61 = 0.0164), and y outranks z. (Suspicion bug-srch-005 says absent adds 1/(2c+len); with these numbers y still wins, so the decisive contrast is the next row) |
| F1b | same, legs of 200, x only in vector at rank 1 vs y at rank 50 in both | x at rank 1 in both | owner/API: y (2/110 = 0.0182) outranks x (1/61 = 0.0164); neighbor x-in-both wins outright |
| F2 | engine `kg_RRF_FUSE` called without `c` | `IRISGraphOperators.kg_RRF_FUSE` without `c` | engine: `TypeError` (no default, owner metadata); operators: c = 60 |
| F3 | engine `kg_RRF_FUSE` with `query_text=''` | `query_text` that matches | empty text skips the BM25 leg: every row has bm25_score 0 and rrf = 1/(c+vector rank); neighbor fuses both |
| F4 | vector leg fails (query vector of the wrong width) with a matching text query | vector leg empty but successful (graph with no vectors, right width) with the same text query | KNOWN_ISSUES: failed → `[]` (text leg never runs, ERROR logged); empty → the text leg's ranking alone |
| F5 | `IRISGraphOperators.kg_RRF_FUSE(query_text='alpha')` with the default `query_vector='[]'` | the same with a real query vector | owner metadata: the default `'[]'` fails the vector leg → `[]`; neighbor answers a fused ranking |
| F6 | SQL `Graph_KG.kg_RRF_FUSE` on the default graph, item only in the vector leg vs item in both | engine `kg_RRF_FUSE` on the same data | HD-0702 (as recorded): SQL absent rank 10^9 (contributes ~1e-9); text leg from the `docs` table via `kg_TXT`, so a node with a `docs` row but no BM25 index entry is in SQL's text leg and absent from the engine's |
| F7 | engine `kg_RRF_FUSE` when an IVF index built with metric "cosine" exists (long vector L vs aligned unit vector A) | no IVF index | API: the vector leg reads "the graph's IVF index or `kg_KNN_VEC`". Owner `search.scope.indexes` says an IVF index records no graph. Prediction (low confidence): IVF is read and bug-srch-109 propagates, so L ranks above A in the fused answer; neighbor (kg_KNN_VEC, true cosine) ranks A above L |
| F8 | `PyOps.HybridSearch` (the `/hybridSearch` body) for the default graph | SQL `kg_RRF_FUSE` with the same arguments | HD-0702: same rule as the SQL procedure (absent 10^9, `docs` text), so the same ranking |
| V1 | `kg_VECTOR_GRAPH_SEARCH(k=2)` where the candidate set has 3 nodes: vector hits a (best), b, and expansion target n of a | k = 3 | API/HD-0603: keeps 2 of the set in no particular order, then sorts; the best hit a can be dropped (depends on Python set order, varies with the hash seed across processes); k=3 returns a, b, n with n at 0.0 |
| V2 | expansion edge `confidence` 400 vs 600 with `min_confidence=0.5` | edge with no `confidence` qualifier | 600 included (≥ 500), 400 excluded; an edge with no qualifier excluded (like `kg_NEIGHBORHOOD_EXPANSION`) |
| V3 | `query_text` adds a text-only node t that **also has an embedding** close to the query | t found by the vector leg | API: `vector_similarity` 0.0 for a node found only by text, even with an embedding; neighbor gets its cosine |
| V4 | node that is both a vector hit and an expansion target | expansion-only node | `in_graph_expansion` True only for a node not among the vector hits; the vector hit keeps its cosine |
| V5 | graph with no vectors | query vector of the wrong width | empty graph → `[]`; wrong width → raises (the `kg_KNN_VEC` error propagates) |
| P1 | `kg_PPR_GUIDED_SUBGRAPH(seed_ids, ppr_top_k=1)` on a chain s→a→b | ppr_top_k = 3 | the subgraph is built around the PPR top-1 node only (the seed): nodes within `k_hops`=1 of s; with 3, around s, a, b |
| P2 | a seed that is not a node, alone | duplicate seed `[s, s]` | missing-only → empty subgraph, no error; duplicate counts once (same answer as `[s]`) |
| P3 | `kg_PPR_GUIDED_SUBGRAPH(damping=1.5)` or `max_iterations=0` | damping 0.85 | `ValueError` before reading data (`algorithms.op`); neighbor succeeds |
| P4 | `IRISGraphOperators.kg_PPR_GUIDED_SUBGRAPH(top_k=1)` and `(max_hops=2)` | engine with `ppr_top_k=1`, `k_hops=2` | the same answers (API: `top_k` replaces `ppr_top_k`, `max_hops` replaces `k_hops`) |
| R1 | `kg_RERANK(top_n, qv, qt)` | engine `kg_RRF_FUSE(k=top_n, ..., c=60, qv, qt)` | the same ranking (API: "fused by `kg_RRF_FUSE`"); a node with no embedding enters only via its text rank |
| R2 | `kg_PPR(seeds)` | `kg_PERSONALIZED_PAGERANK(seeds, max_iterations=20)` | same scores, as a list best first |
| M1 | `multi_vector_search` with two sources, one of the wrong width | both valid | API: the failing source is logged and skipped; the answer is the other source's RRF ranking; neighbor fuses both by weighted reciprocal rank (`weight/(rrf_k+rank)`) |
| M2 | `fusion='max'` (not rrf) | `fusion='rrf'` | ranks by raw (weighted) score |
| M3 | a source dict with its own `graph` | the call's `graph=` | the source's `graph` wins for that source |
| Y1 | `PyOps.VectorSearch` (`/vectorSearch`) for a named graph with no route | the same graph with a route | `search.routes.no_fallback`: unrouted → empty, never a width error and never the default graph's vectors; routed → the route's hits |
| N1 | `kg_MENTIONS([s])` | `kg_NEIGHBORS([s], predicate='MENTIONS')` | identical lists (owner `algorithms.op.neighbors`) |
