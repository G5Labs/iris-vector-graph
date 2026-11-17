# Iteration 57 W1: proposed owner-block edits (not applied; the builder integrates)

Additive bullets only. "Today ..." marks an as-built departure; provisional assumptions link existing open questions.
Paths are relative to `.g5/ontology/features/`. Metadata lines use the register's form.

## query.paths.varlength (`cypher.g5.md#query.paths.varlength`)

Add:

- The breadth-first route (`IRISGraphStore.execute_bfs`, which the variable-length fallback and BFS callers read) answers each node other than the source once, at its least depth, with the first type in collation of the edges reaching it from one hop nearer, ordered by depth then id; `max_results` keeps the first rows of that order (0 keeps all). The ObjectScript walk and the SQL fallback answer the same rows on every edge set; the walk is scoped to one graph.
- The Arno walk is chosen only for the default graph, an outbound walk, the library with its `bfs` capability, and no other graph holding edges; otherwise the ObjectScript walk answers, and the SQL walk answers when the ObjectScript walk raises or walks no edge.
- The ends-only walk (`execute_vl_ends`) uses no relationship twice, so it can end at the source over a cycle (or over two parallel relationships, undirected), while the breadth-first route never lists the source.
- Today a direction other than exactly `out`, `in` or `both` is not refused: `OUT` and unknown texts are walked undirected by the SQL fallback, and `outbound` / `inbound` are walked from the edge table ([bug-str-114](../../uplift/consolidated/iteration-57/strategy/findings.md#bug-str-114)). Provisional: refuse it, as the path routines' direction policy ([open question](../../Verus_verification/open_questions.md#HD-1003)) proposes.
- Verus: [traversal_strategy](../../Verus_verification/models/traversal_strategy/NOTES.md) theorem_os_rows_eq_sql_rows, theorem_bfs_never_lists_source, theorem_one_row_per_node, theorem_cap_keeps_nearest_prefix, theorem_arno_only_default_outbound, theorem_fixture_path, theorem_vl_ends_list_source_bfs_does_not, theorem_vl_both_no_backtrack, theorem_unknown_direction_walks_both

## algorithms.op.paths (`algorithms.g5.md#algorithms.op.paths`)

Add:

- `shortest_path_length` and `execute_shortest_path` answer the same length for `out` and `both`, and a parallel edge or another graph's edge changes neither.
- Today `shortest_path_length(a, b, …, 'in')` answers the outgoing length from a to b: it does not reverse `in` as `execute_shortest_path` does, so it can answer no path where an incoming path exists and a length where none does ([bug-str-113](../../uplift/consolidated/iteration-57/strategy/findings.md#bug-str-113)); Cypher's length-only route is taken only for `out` and `both`. Provisional: the existing working assumption ([open question](../../Verus_verification/open_questions.md#HD-1003)) — reverse `in` in the store method.
- Verus: [traversal_strategy](../../Verus_verification/models/traversal_strategy/NOTES.md) theorem_lengths_agree_out_both, theorem_in_length_differs, theorem_parallel_edge_invisible, theorem_other_graph_edges_invisible

## algorithms.op.khop (`algorithms.g5.md#algorithms.op.khop`)

Add:

- A k-hop read has no graph argument: it walks the default graph only, and its nodes other than the seed are the breadth-first route's outbound nodes on that graph.
- Today a seed held only by a named graph answers itself and no edges, because the seed check reads every graph (F-1009, reproduced in iteration 57).
- Verus: [traversal_strategy](../../Verus_verification/models/traversal_strategy/NOTES.md) theorem_khop_is_default_out_bfs, theorem_khop_ignores_named_graphs

## structure.adjacency (`graph-structure.g5.md#structure.adjacency`)

Add:

- Every traversal reader keyed by graph (breadth-first walk, its SQL fallback, ends-only walk, shortest paths, k-hop on the default graph) answers from one graph's entries: another graph's edges change no answer.
- Verus: [traversal_strategy](../../Verus_verification/models/traversal_strategy/NOTES.md) theorem_other_graph_edges_invisible

## search.knn (`search.g5.md#search.knn`)

Add:

- `execute_knn_vec` answers no neighbours, without error, for a (graph, model) pair with no route.
- Verus: [traversal_strategy](../../Verus_verification/models/traversal_strategy/NOTES.md) theorem_knn_no_route_no_rows
