# Iteration 57 W1: binding-integrity audit of the traversal_strategy crosswalk rows

Question per row labelled models / proves / witnesses in [crosswalk-rows.tsv](crosswalk-rows.tsv): would swapping or
weakening this member's actual decision break a theorem (a control that must fail) or the binding (a port mutation
or an observation that would no longer agree)? Controls: final run `20261117T074637Z`..`20261117T074707Z`, all
EXPECTED_FAIL. Binding: `20261117T074632Z-binding`, 19/19 mutations detected. Rows labelled delegates / cites are not
audited (their decision is not modeled).

| # | block | member | formal item | relation | control that fails | binding detection | verdict |
|---|---|---|---|---|---|---|---|
| 1 | query.paths.varlength | `iris_sql_store.py::IRISGraphStore._select_bfs_strategy` | `select` | models | arno-named-graph, arno-any-direction (theorem_arno_only_default_outbound) | arno_named_graph, arno_any_direction (`select_injected`) | PASS |
| 2 | query.paths.varlength | `iris_sql_store.py::IRISGraphStore._select_bfs_strategy` | `theorem_arno_only_default_outbound` | proves | arno-named-graph, arno-any-direction, arno-ignores-other-graphs | arno_* (`select_injected`) | PASS |
| 3 | query.paths.varlength | `iris_sql_store.py::IRISGraphStore._only_default_graph` | `only_default_graph` | models | arno-ignores-other-graphs | arno_ignores_other_graphs (`select_injected` od0 cells) | PASS |
| 4 | query.paths.varlength | `iris_sql_store.py::IRISGraphStore.execute_bfs` | `adapter_cap` | models | cap-passed-to-adapter (theorem_adapter_walks_uncapped) | cap_passed_to_adapter (`os_cap3`) | PASS |
| 5 | query.paths.varlength | `iris_sql_store.py::IRISGraphStore.execute_bfs` | `theorem_cap_keeps_nearest_prefix` | proves | cap-zero-cuts-all | cap_zero_cuts_all (47 cases) | PASS |
| 6 | query.paths.varlength | `iris_sql_store.py::IRISGraphStore._bfs_rows` | `os_row` | models | bfs-every-depth (theorem_os_rows_eq_sql_rows, theorem_one_row_per_node) | bfs_every_depth (22 cases) | PASS |
| 7 | query.paths.varlength | `iris_sql_store.py::IRISGraphStore._bfs_rows` | `theorem_bfs_never_lists_source` | proves | bfs-lists-source | bfs_lists_source (46 cases) | PASS |
| 8 | query.paths.varlength | `iris_sql_store.py::IRISGraphStore._bfs_rows` | `type_dir_text` | models | types-ignore-case (theorem_unknown_direction_walks_both) | types_ignore_case (`os_dirtext_OUT`) | PASS |
| 11 | query.paths.varlength | `TraversalBFS.cls::BFSFast` | `os_front` | models | sql-revisits fails lemma_front_eq_new, the os_front = sql_new link; a frontier change in BFSFast alone is answer-neutral after the least-depth fold (product comment: re-expansion only recorded edges again) | bfs_every_depth (the fold over BFSFast's rows); no binding mutation of the frontier itself | PASS (theorem only; frontier is answer-neutral after the fold, stated) |
| 12 | query.paths.varlength | `TraversalBFS.cls::BFSFast` | `os_walks_text` | models | bfsfast-case-insensitive (theorem_unknown_direction_walks_both) | bfsfast_case_insensitive (`os_dirtext_OUT` fallback_calls) | PASS |
| 13 | query.paths.varlength | `iris_sql_store.py::IRISGraphStore._run_objectscript_bfs` | `falls_back` | models | no-fallback-on-empty (theorem_fixture_path) | no_fallback_on_empty (6 cases: `os_lone_fallback`, `b7_after_delete`, `os_dirtext_*`) | PASS |
| 14 | query.paths.varlength | `iris_sql_store.py::IRISGraphStore._sql_bfs_fallback` | `sql_new` | models | sql-revisits (lemma_front_eq_new), graph-unscoped | sql_revisits (19 raw walks), graph_unscoped | PASS |
| 15 | query.paths.varlength | `iris_sql_store.py::IRISGraphStore._sql_bfs_fallback` | `sql_dir_text` | models | sql-unknown-dir-as-out (theorem_unknown_direction_walks_both) | sql_unknown_dir_as_out (`os_dirtext_OUT`, `os_dirtext_sideways`) | PASS |
| 16 | query.paths.varlength | `iris_sql_store.py::IRISGraphStore._sql_bfs_fallback` | `theorem_os_rows_eq_sql_rows` | proves | bfs-every-depth, bfs-lists-source | bfs_every_depth, sql_revisits; forced-SQL pairs | PASS |
| 20 | query.paths.varlength | `VarLength.cls::EndsInto` | `trail` | models | trail-repeats-edges (theorem_vl_both_no_backtrack) | trail_repeats_edges (`vl_single_both_1_2`, `vl_mix_out_2_3`) | PASS |
| 21 | query.paths.varlength | `VarLength.cls::EndsInto` | `theorem_vl_both_no_backtrack` | proves | trail-repeats-edges | trail_repeats_edges | PASS |
| 22 | query.paths.varlength | `VarLength.cls::EndsByDistance` | `vl_end` | models | no control targets EndsByDistance's own shortcuts; the spec is the answer | binding observation: dropping the parallel-edge count (tMult) or the source-cycle check changes `vl_parallel_both_1_2` / `vl_cycle_u_*` against the independent trail port (DISAGREES) | PASS (binding only; no formal control on EndsByDistance's shortcuts) |
| 23 | query.paths.varlength | `VarLength.cls::Ends` | `theorem_vl_ends_list_source_bfs_does_not` | witnesses | bfs-lists-source | `vl_cycle_u_1_2` vs `os_cycle_u`; bfs_lists_source | PASS |
| 24 | structure.adjacency | `TraversalBFS.cls::TraverseWithPredicateFast` | `edge_steps` | models | graph-unscoped (theorem_other_graph_edges_invisible) | graph_unscoped (`os_named_out_3`, `sql_named_out_3`, `sp_default_g1_g3`, `khop_named_only_g1`) | PASS |
| 25 | structure.adjacency | `TraversalBFS.cls::TraverseWithPredicateFast` | `theorem_other_graph_edges_invisible` | proves | graph-unscoped | graph_unscoped | PASS |
| 26 | algorithms.op.paths | `iris_sql_store.py::IRISGraphStore.execute_shortest_path` | `esp_len` | models | esp-no-reversal (theorem_in_length_differs) | esp_no_reversal (`sp_in_p3_p1`) | PASS |
| 27 | algorithms.op.paths | `iris_sql_store.py::IRISGraphStore.shortest_path_length` | `spl_len` | models | length-in-reversed (theorem_in_length_differs) | length_in_reversed (`sp_in_*`) | PASS |
| 28 | algorithms.op.paths | `TraversalPaths.cls::ShortestLength` | `spl_dir` | models | length-in-reversed, length-both-as-out | length_in_reversed, length_both_as_out (`sp_both_p3_p1`) | PASS |
| 29 | algorithms.op.paths | `TraversalPaths.cls::ShortestLength` | `theorem_in_length_differs` | witnesses | length-in-reversed, esp-no-reversal | length_in_reversed, esp_no_reversal | PASS |
| 30 | algorithms.op.paths | `TraversalPaths.cls::ShortestPathJson` | `has_len` | models | graph-unscoped (scope); length-both-as-out (theorem_lengths_agree_out_both) | graph_unscoped (`sp_default_g1_g3`), length_both_as_out | PASS |
| 31 | algorithms.op.paths | `TraversalPaths.cls::ShortestPathJson` | `theorem_lengths_agree_out_both` | proves | length-both-as-out | length_both_as_out (`sp_both_p3_p1`) | PASS |
| 34 | algorithms.op.khop | `algorithms.py::_khop_fallback` | `khop_node` | models | khop-walks-both (theorem_khop_is_default_out_bfs) | khop_walks_both (`khop_s_1`, `khop_s_2`) | PASS |
| 35 | algorithms.op.khop | `algorithms.py::_khop_fallback` | `theorem_khop_is_default_out_bfs` | proves | khop-walks-both | khop_walks_both | PASS |
| 38 | search.knn | `iris_sql_store.py::IRISGraphStore.execute_knn_vec` | `knn_rows` | models | knn-unrouted-legacy (theorem_knn_no_route_no_rows) | knn_unrouted_legacy (`knn_unrouted`) | PASS |

29 rows audited; none relabelled. Two pass on one leg only and are stated as such: `BFSFast`'s frontier (`os_front`;
a weakening is caught by `lemma_front_eq_new` under the symmetric control, and is answer-neutral after `_bfs_rows`'
fold) and `EndsByDistance` (`vl_end`; caught by the binding's independent trail port, not by a formal control).
Four controls (`types-ignore-case`, `bfsfast-case-insensitive`, `esp-no-reversal`, `length-both-as-out`) and their
binding mutations were added during this audit, after rows 8, 12, 26 and 31 were first found with no control naming
them; the earlier 14- and 15-control runs are kept.
