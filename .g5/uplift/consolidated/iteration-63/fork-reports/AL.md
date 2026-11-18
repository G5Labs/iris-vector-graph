# AL report — features/algorithms (22 blocks)

Saved by the builder from the fork's final message. Fragment: 22 blocks complete, 137 obligations, 18 exclusions, no
owner-updates; merged check PASS.

## 1. Per block (f/p/a, total, excl)
algorithms.graph_scope 1/0/1 (2, 5); algorithms.op (parent) 2/7/3 (12, 3); op.pagerank 2/0/7 (9, 0); op.ppr 7/1/0
(8, 1); op.ppr.completion 2/0/0 (2, 0); op.wcc 3/0/0 (3, 0); op.cdlp 3/1/0 (4, 0); op.subgraph 4/3/3 (10, 0);
op.subgraph.guided 4/2/4 (10, 1); op.degree 0/0/4 (4, 0); op.betweenness 0/0/7 (7, 0); op.closeness 0/0/2 (2, 1);
op.eigenvector 0/0/3 (3, 1); op.leiden 0/0/6 (6, 0); op.triangles 0/0/3 (3, 0); op.scc 0/0/2 (2, 1); op.kcore 0/0/2
(2, 0); op.khop 5/1/1 (7, 0); op.walks 3/1/4 (8, 2); op.neighbors 4/1/2 (7, 0); op.paths 3/2/2 (7, 1);
op.paths.weighted 12/3/4 (19, 2). All complete; no structural zero.

## 2. Totals
full 55, partial 22, absent 60, unassessed 0, of 137 (40.1%). Proved 64, all narrowed (0 full scope); refuted 6 (5
full grades, 1 partial); bounded 0; unchecked 0; none 67. Exclusions 18: restatement 8, undecided-alternative 6,
rationale 2, definition 1, evidence-annotation 1. No full-scope proof because every applicable model is either an
exact-arithmetic / finite stable-graph transcription relying on provider premises (IRIS collation, Adj.Degree equal to
raw multiplicity, native bodies, pydantic coercion) or a reviewed-design playbook crate.

## 3. Grades: 74 reused, 1 changed, 62 new
Reused: NOTES of ppr_walk, communities, retrieval_compose, retrieval_scope, traversal_strategy, rebuild_reads,
walk_reader, weighted_paths, weighted_cost, weighted_fraction, sql_procs, algo_options; blocks' Verus metadata. Each
theorem/control found in source; receipts latest and fresh per the tool.
Changed: paths.weighted#o01 — coverage.md line 484 "Open (no optimality proof of the ObjectScript Dijkstra)" → full,
proved, narrowed (weighted_paths, iteration 9: optimality, completeness, termination).
New: 60 absent; plus proofs-d1e-based grades: pagerank#o01 refuted by cx_f1003 (F-1003 Owner cap), pagerank#o06 as-built
cap witness, paths#o04 via cx_hd1003 (iteration-61 convention for reviewed-design controls; nothing reproduced live).
Judgement: a "Today" departure confirmed by an as-built witness is full, proved, narrowed; the intended rule it
contradicts is full, refuted. algorithms.op#o04 (scores equal to 12 decimals are a tie) partial, refuted (only PPR
modelled; its fast reader breaks the tie, bug-plt-103, q-iter-008).

## 4. Parents
Open: algorithms.op#o01 (every answer lists every node, including nodes with no edge): WCC, CDLP and PPR completion are
modelled; degree, closeness, eigenvector, triangles, SCC, k-core, Leiden are not, so a node with no edge can be missing
from their answers while every modelled child holds; global PageRank's own block is refuted by the 10,000-row cap.
No entailment claimed; the parent's other obligations are its own (option ranges/literals, identical decisions between
methods and procedures, ranking/ties, damping and direction refusals). subgraph→guided, ppr→completion,
paths→weighted are each block's own text.

## 5. Restatements
No owner updates; within page: graph_scope clauses → pagerank#o02, subgraph#o06, ppr#o06, degree#o04; parent's
exceptions bullet → betweenness#o02, walks#o01; closeness formula refusal and eigenvector max_iter range →
algorithms.op#o08. Cross-page overlap counted (not excluded): algorithms.graph_scope#o02 specialises
graph.unscoped_snapshot#o02 (adds the procedure list and error message). No cross-fork restatements.

## 6. Grade-source errors and contradictions
1. coverage.md stale: line 484 (paths.weighted "Open") and line 502 ("No active formal link: … weighted shortest path's optimality") stale since iteration 9; line 451 ("all of algorithms.* … not modelled") superseded by ppr_walk, communities, retrieval_*, traversal_strategy, walk_reader, weighted_*.
2. algorithms.op bullet 4 "sampleSize 0 or more": source caps at 1,000,000 (_validate.py:249, Field(ge=0, le=1_000_000)), as algo_options' in_range does.
3. algorithms.op bullet 3 (unknown direction → ValueError) contradicts its child algorithms.op.paths (path routines answer no path) and execute_bfs's SQL walk reads unknown text as both (bug-str-114).
4. algorithms.op.paths bullet 2 holds only for ShortestPathJson; TraversalPaths.cls:121 (`Set tBoth = (direction = "both")`) makes ShortestLength walk every non-"both" text outbound.
5. algorithms.graph_scope "naming the Python method to use": the Cypher refusal names engine.<method>() (translator.py:256-275); NKGAccel.RefuseMergedGraphs (NKGAccel.cls:213-223) only says "Call the engine's method".
6. algorithms.op.leiden "random_seed makes a run repeatable": its own metadata says the ObjectScript Louvain (second in order) ignores random_seed.
7. algorithms.op.walks: random_walk (_engine/algorithms.py:658-678) returns [] without Arno (metadata "Observed divergence"; HD-1001).
8. Product docstring: degree_centrality (~_engine/algorithms.py:1069) still says n counts only nodes with an edge.
9. retrieval_compose's withdrawn control guided-cap-max-nodes (receipt 20261117T024538Z) is STALE (not cited).

## 7. Ranked uncovered
1. Centrality and community answers (29 absent, no model): degree#o01–o04, betweenness#o01–o07, closeness#o01–o02, eigenvector#o01–o03, leiden#o01–o06, triangles#o01–o03, scc#o01–o02, kcore#o01–o02. Values; betweenness's fixed SHA-1 sample of 200 sources; direction/max_hops pair rules; Leiden's fallback order. Roles: _engine/algorithms.py::degree_centrality, betweenness_centrality(_neighborhood), closeness_centrality, eigenvector_centrality, leiden_communities, triangle_count, strongly_connected_components, k_core; NKGAccelCentrality.cls; stores' execute_degree_centrality.
2. Global PageRank: pagerank#o02–o05, #o07, #o08 absent; #o01 refuted only in reviewed crate. Default-graph scope, sum to 1, dangling spread, parallel-edge weighting, seeded delegation to PPR. Roles kg_PAGERANK, _kg_pagerank_global, PageRank.cls::PageRankGlobalJson (cap :503-520), iris_sql_store.py::execute_pagerank.
3. ^NKG procedure refusal (graph_scope#o02): translator.py::_refuse_merged_graphs, NKGAccel.RefuseMergedGraphs, lazy_kg.named_graph_with_edges.
4. Completion for nodes with no edge (algorithms.op#o01 residual, #o02 "n is the node count"): _engine/algorithms.py::_loners, _edgeless.complete_degree/complete_labels.
5. paths.weighted #o10, #o06, #o12, #o16 (engine.py::_proc_ivg_shortestpath_weighted :1201-1313, SqlProcs.DijkstraPath).
6. subgraph#o03, #o04, #o06; guided#o05, #o06, #o11 (kg_SUBGRAPH, kg_PPR_GUIDED_SUBGRAPH, kg_PPR; execute_subgraph whose Arno SubgraphNativeJson answers first, unmodelled).
7. walks#o02, #o06, #o07, #o08 (Traversal.BFSFastJsonSorted, kg_GRAPH_PATH, random_walk).
8. algorithms.op#o05, #o09, #o10, #o11.
9. khop#o04, paths#o02, paths#o07, neighbors#o07.

## 8. Iteration-60 residual mapping
store/iris_sql_store: execute_pagerank, execute_subgraph, execute_degree_centrality, shortest_path_length behind
pagerank#o01–o05, subgraph#o01–o10, degree#o01–o04, paths#o05–o06. Translator residue: graph_scope#o02
(_refuse_merged_graphs, _procedure_graphs), paths#o07 (algorithms.op#o07, #o12 covered by algo_options). Operator and
retrieval residues: subgraph.guided#o09–o11 (IRISGraphOperators argument aliases, kg_PPR), neighbors#o03 (kg_MENTIONS),
walks#o06 (kg_GRAPH_PATH). None: GQL/GraphQL, SDK/CLI/HTTP admin, install, load_networkx/load_obo, migrations, temporal.
Source-discovered omissions: kg_GRAPH_WALK next-hop lookahead (_engine/algorithms.py:707-709); kg_GRAPH_WALK_TVF alias
(:733); kg_GRAPH_PATH sets path_id 1 on every row (:682-684); ppr() wrapper re-sorts by raw score after the kg cut;
whole-float PPR iteration count passes validation then TypeError at range; option validation in gds.* shims;
bfs_vector_rerank (:1293) has no block.

## 9. Limitations
Targeted source reading only (graph-scope refusal, option models, PageRank/random_walk/graph-path bodies, ShortestLength
direction); the 29 centrality/community obligations are absent because no model exists, not from reading each
implementation; F-1003/HD-1003 from reviewed-design controls; split granularity (19 weighted-path, 7 betweenness, 6
Leiden); no independent review.
