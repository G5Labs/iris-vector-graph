# Iteration 57, W61: writes and deletes → adjacency → traversal answers, by strategy — frozen predictions

Frozen before any deciding source was read in `iris_vector_graph/stores/iris_sql_store.py`,
`iris_src/src/Graph/KG/{Traversal,TraversalBuild,Adjacency,TraversalBFS,TraversalKHop}.cls`. Sources used: owners
`structure.*`, `algorithms.op.{khop,walks,neighbors,paths}`, `query.paths.varlength`, `structure.rebuilt.stamp`;
`docs/API_REFERENCE.md` (`delete_nodes_by_prefix`, `delete_edge`, `khop2_count_fast/exact`, `engine.cypher`);
`docs/ADMIN_GUIDE.md` §temporal opt-out; test docstrings and oracles: `tests/e2e/test_460_bfs_route_independent_e2e.py`
(`_bfs_reference`: the documented `execute_bfs` rows), `test_252_vlp_ends_kg_e2e.py`, `test_460_r284_khop2_freshness_e2e.py`,
`test_460_shortest_path_incoming_e2e.py`, `test_460_knn_vec_routes_e2e.py`, `test_460_vlp_relationship_uniqueness_e2e.py`,
`tests/unit/test_227_bfs_graph_scope.py`, `test_230_bfs_direction_and_limit.py`, `test_bfs_strategy.py`.

Fixture: `ivg-cont-20261117-iris`, USER, prefix `i57_`, named graphs `i57g…`. Arno/NKG accelerator library absent:
every prediction is for the non-Arno path; the Arno branch stays conditional and is recorded, not exercised.

Each row: changing input or history → reader → expected difference. "A" and "B" are the two neighbors.

## 1. BFS / k-hop / variable-length ends by strategy

| ID | Workflow | A (input/history → expected at reader) | B (neighbor → expected) | Source of expectation |
|---|---|---|---|---|
| B1 | `store.execute_bfs(src, preds, hops, dir, max)` strategy, default vs named graph | default graph, Arno absent → ObjectScript strategy; rows `(id, hops, pred)`, one per node other than the source, at its least BFS depth, with the first type in collation among edges reaching it from depth−1, ordered by depth then id | the same node IDs and edges written into a named graph `g`, BFS asked with `graph=g` → the same rows, and none from the default graph's edges of the same IDs | `_bfs_reference`; test_227 (named graph never Arno; SQL fallback scoped by graph) |
| B2 | ObjectScript vs SQL fallback on the same data | ObjectScript strategy answers the reference rows | SQL fallback strategy (forced) answers the same rows (same set, same order, same pred) for out/in/both, with a predicate filter and hops 1-3 | test_460_bfs_route_independent "the same on each route"; test_227 fallback scoped |
| B3 | cycles, self-loops and parallel edges | a cycle back to the source and a self-loop on the source → the source is never a row | a multigraph triple with two parallel edges → its target appears once (one row per node, not per edge) | `_bfs_reference` (source excluded; one row per node) |
| B4 | the cap | `max_results = 0` → every row | `max_results = k` → the first k rows of the uncapped answer (nearest first) | test "a capped BFS keeps the nearest rows" |
| B5 | direction | `dir='in'` from d → nodes with a path into d | `dir='both'` → the union walk, each node once at its least depth | `_bfs_reference` |
| B6 | variable-length ends (`execute_vl_ends` / `CY_VLP_ENDS`) vs BFS | a cycle returning to the source at depth ≥ minh → ends include the source (trail walk, edge-distinct) | `execute_bfs` on the same data never lists the source | test_252 (trail walk, each end once with least depth ≥ minh) |
| B7 | k-hop (`khop`) after writes vs after deletes | an edge written by `create_edge` is walked at once (declared index) | after `delete_edge` of that triple the next `khop`/`execute_bfs` no longer reaches its target (unless another path) | `structure.adjacency.declared` |

## 2. Delete paths

| ID | Workflow | A | B | Source |
|---|---|---|---|---|
| D1 | `delete_nodes_by_prefix(prefix, graph)` | prefix in graph g → every g node with that prefix and its incident edges gone; BFS/degree in g no longer see them | the same IDs in another graph h → untouched (rows, adjacency, BFS answers in h unchanged) | API_REFERENCE "every node in one graph"; `structure.node.delete` |
| D2 | `delete_edge(s,p,o, graph=g)` when the same triple is held in graph h | g's adjacency entry gone; BFS in g no longer reaches o through p | h's adjacency entry and BFS answer in h unchanged | `structure.edge.delete` (one graph); `structure.adjacency` (graph-keyed) |
| D3 | store `delete_edges` vs engine `delete_edge` vs Cypher `DELETE r` | each removes the edge row and (declared index) its out/in entries; degree drops by the edge count | in a multigraph with two parallel edges, Cypher `DELETE r` of one relationship leaves the other: the target is still reached and degree drops by one | `structure.multigraph.count`/`.layout`, `structure.adjacency.declared` |
| D4 | `delete_node` / store `delete_nodes` labels | the node's labels gone from the label index | another node with the same label keeps it; label reads unchanged for it | `structure.node.delete` |

## 3. Rebuild vs incremental

| ID | Workflow | A | B | Source |
|---|---|---|---|---|
| R1 | interleaved writes/deletes/reweights, then `sync()` | with a declared index the `^KG` out/in entries, degrees and labels before `sync()` equal those after (no drift) | `set_edge_weight` then `sync()` → the out entry carries the new weight before and after the rebuild (weight read from qualifiers) | `structure.drift`, `structure.adjacency.declared`, `structure.edge.weight` |
| R2 | two-hop counts `khop2_count_fast` vs `khop2_count_exact` | right after `sync()`: fast = the precomputed upper bound (sum of the middle nodes' out-degrees), exact = distinct nodes first reached at hop 2 | after a later edge write, both answer the walked count (stale stats not read) until the next `sync()` | test_460_r284; `structure.rebuilt.stamp` |
| R3 | `^NKG` rebuild after deletes | after deletes, a NKG rewrite converges by names to a fresh build | — (Arno absent: `^NKG` readers conditional; record whether the sync path even writes `^NKG`) | test_nkg_live_rewrite |

## 4. Shortest path

| ID | Workflow | A | B | Source |
|---|---|---|---|---|
| S1 | `shortest_path_length` vs `execute_shortest_path`, direction out | both find the same hop length on the same data | on a multigraph, parallel edges do not change the length | `algorithms.op.paths` |
| S2 | direction `in` | `execute_shortest_path(…, 'in')` finds the path along incoming edges (caller reversal) | `shortest_path_length(…, 'in')` does not reverse: answers a length that differs from execute_shortest_path's (owner working assumption names this gap) | `algorithms.op.paths` working assumption; test_460_shortest_path_incoming |
| S3 | named graph | a path in graph g only → found when g is named | not found with the default graph named | `algorithms.op.paths` "inside one graph" |

## 5. Fallbacks

| ID | Workflow | A | B | Source |
|---|---|---|---|---|
| N1 | `execute_knn_vec` | a graph with routed vectors → the route's nearest neighbours | a graph/model pair with no route → no neighbours | test_460_knn_vec_routes |
| N2 | `_khop_fallback` when the native call is unavailable | the SQL fallback answers the same node set as the native k-hop on the same graph | — named graph scoping preserved | `algorithms.op.khop` |

Number of predictions: 13 workflows with both neighbors (26), plus R3/N2 with one neighbor each (2 more single).
