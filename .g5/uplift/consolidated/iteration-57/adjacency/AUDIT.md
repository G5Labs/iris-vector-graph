<!-- markdownlint-disable MD013 -->

# Iteration 57 (W2, adjacency) — binding-integrity audit

Question per crosswalk row with relation models / proves / witnesses: would swapping or weakening this member's actual decision break a theorem or the binding? Controls are the model's find/replace mutations (all 14 EXPECTED_FAIL, `results/adjacency_maint/20261117T074811Z`…`074902Z`); binding mutations and cases are from `results/adjacency_maint/20261117T075252Z-binding/receipt.json` (`sensitivity_cases`).

| # | Member (path::symbol, lines) | Formal item | Relation | Control that fails | Binding mutation / case | Verdict |
|---|---|---|---|---|---|---|
| 1 | `iris_src/src/Graph/KG/Adjacency.cls::PutKeyed` 210-269 | `put_keyed` | models | put-keyed-drops-others, transition-weight-not-old-leaf, create-ignores-mode | put_keyed_drops_others (5 cases), transition_new_weight (2) | yes |
| 2 | `iris_src/src/Graph/KG/Adjacency.cls::PutKeyed` 210-269 | `lemma_create` | proves | put-keyed-drops-others, transition-weight-not-old-leaf, create-ignores-mode, canon-leaf-not-lowest (all fail lemma_create) | as above | yes |
| 3 | `iris_src/src/Graph/KG/Adjacency.cls::SetLeafFromLowest` 874-881 | `lowest_w` | models | canon-leaf-not-lowest | leaf_highest (3 cases: multi_two leaf 7 at ekey 0) | yes |
| 4 | `iris_src/src/Graph/KG/Adjacency.cls::OtherEdgeKeys` 886-902 | `lemma_second` | proves | put-keyed-drops-others, transition-weight-not-old-leaf (fail lemma_second) | put_keyed_drops_others; a product OtherEdgeKeys that missed the other row would leave one child: multi_two mismatches | yes |
| 5 | `iris_src/src/Graph/KG/Adjacency.cls::RemoveKeyed` 275-321 | `remove_keyed` | models | remove-keyed-takes-triple | remove_keyed_takes_triple (3 cases: multi_after_delete_r, count_ms_after_delete_r, bfs_gm_ms) | yes |
| 6 | `iris_src/src/Graph/KG/Adjacency.cls::RemoveKeyed` 275-321 | `theorem_delete_one_parallel_keeps_other` | proves | remove-keyed-takes-triple | as above | yes |
| 7 | `iris_src/src/Graph/KG/Adj.cls::Count` 110-136 | `contrib` | models | remove-keyed-takes-triple breaks the contrib clauses of theorem_delete_one_parallel_keeps_other | a Count that counted a # triple once would observe count_ms_two = 2 against the port's 3 (binding DISAGREES) | yes |
| 8 | `iris_vector_graph/cypher/translator.py::translate_delete_clause` 10705-10718 | `rows_step` | models | none (definitional: DelRow{k} is one row) | cypher_delete_r_rows = 1: a DELETE by (s, p, o) would remove both rows (2) against the model's one DelRow; added in 20261117T075252Z because the port records DelRows from the ekeys that went and would otherwise follow the product | yes |
| 9 | `iris_src/src/Graph/KG/Adjacency.cls::RowPut` 477-488 | `row_put` | models | create-ignores-mode | create_ignores_mode (5 cases) | yes |
| 10 | `iris_src/src/Graph/KG/Adjacency.cls::RowRemove` 491-501 | `row_remove` | models | remove-keyed-takes-triple, plain-remove-keeps | remove_keyed_takes_triple, plain_remove_keeps (2 cases) | yes |
| 11 | `iris_src/src/Graph/KG/Adjacency.cls::Remove` 147-167 | `theorem_plain_delete_takes_triple` | proves | plain-remove-keeps | plain_remove_keeps (entries of b->c, x->a) | yes |
| 12 | `iris_src/src/Graph/KG/Adjacency.cls::Remove` 161-164 | `nkg_edge_after_remove` | models | held-elsewhere-ignored | held_elsewhere_ignored (nkg_n1n2_after_ga); dropping the removal altogether observes nkg_xa_after true against false | yes |
| 13 | `iris_src/src/Graph/KG/Adjacency.cls::HeldElsewhere` 184-195 | `theorem_nkg_held_elsewhere` | proves | held-elsewhere-ignored | held_elsewhere_ignored | yes |
| 14 | `iris_src/src/Graph/KG/Adjacency.cls::MarkGraphGone` 174-181 | `theorem_mark_graph_gone` | proves | mark-gone-default-graph | none (the stale flag is namespace-wide; not read) | yes (theorem only) |
| 15 | `iris_src/src/Graph/KG/Adjacency.cls::RowUpdate` 505-534 | `row_update` | models | update-ignored | reweight_ignored (reweight_before_sync); the keyed-child branch is proof-only (no multigraph default-graph reweight observed) | yes |
| 16 | `iris_src/src/Graph/KG/Adjacency.cls::RowUpdate` 505-534 | `lemma_update` | proves | update-ignored, canon-leaf-not-lowest | reweight_ignored | yes |
| 17 | `iris_src/src/Graph/KG/Adjacency.cls::Reweight` 328-342 | `row_update` | models | update-ignored | reweight_ignored (reweight_before_sync); the keyed-child branch is proof-only (no multigraph default-graph reweight observed) | yes |
| 18 | `iris_vector_graph/_engine/nodes_edges.py::set_edge_weight` 1306-1380 | `rows_step` | models | none (definitional Update op) | an UPDATE that left the row (adjacency only) would revert to weight 2 at the next sync: entries_after_sync mismatches; reweight_before_sync observed 5 | yes |
| 19 | `iris_vector_graph/_engine/nodes_edges.py::delete_edge` 1382-1446 | `theorem_other_graph_untouched` | proves | erase-ignores-graph (the EraseNodes branch); the DelRow branch is definitional | a delete_edge that deleted every graph's rows would observe GB's n_1->n_2 gone and bfs_gb_n1 shorter against the port (binding DISAGREES); erase_ignores_graph (5 cases) | yes |
| 20 | `iris_src/src/Graph/KG/Eraser.cls::EraseEdges` 395-465 | `erases` | models | erase-ignores-graph | erase_ignores_graph (5 cases); an EraseEdges that left the adjacency would observe d->x present against the port | yes |
| 21 | `iris_src/src/Graph/KG/Eraser.cls::EraseIdSet` 467-640 | `erases` | models | erase-ignores-graph | erase_ignores_graph (5 cases); an EraseEdges that left the adjacency would observe d->x present against the port | yes |
| 22 | `iris_src/src/Graph/KG/Eraser.cls::EraseIdSet` 467-640 | `theorem_erase_nodes_takes_incident` | proves | erase-ignores-graph | erase_ignores_graph | yes |
| 23 | `iris_src/src/Graph/KG/Eraser.cls::EraseIdSet` 549-553 | `theorem_label_delete_scoped` | proves | label-erase-by-label | label_erase_by_label (2 cases) | yes |
| 24 | `iris_src/src/Graph/KG/Adjacency.cls::RemoveLabel` 779-787 | `label_kept` | models | label-erase-by-label | label_erase_by_label | yes |
| 25 | `iris_src/src/Graph/KG/TraversalBuild.cls::BuildKG` 30-165 | `rebuild` | models | create-ignores-mode (fails lemma_rebuild_prefix), canon-leaf-not-lowest (fails lemma_rebuild) | entries_after_sync is compared with the port's rebuild of the recorded rows: a BuildKG that wrote bare leaves for the multigraph triple (3 rows) mismatches | yes |
| 26 | `iris_src/src/Graph/KG/TraversalBuild.cls::BuildKG` 30-165 | `lemma_rebuild` | proves | canon-leaf-not-lowest | as above | yes |
| 27 | `iris_src/src/Graph/KG/TraversalBuild.cls::BuildKG` 126-137 | `theorem_incremental_equals_rebuild` | proves | every lemma_* control (create-ignores-mode, canon-leaf-not-lowest, put-keyed-drops-others, update-ignored, plain-remove-keeps, remove-keyed-takes-triple) fails a lemma this theorem consumes | entries_before_sync vs entries_after_sync vs port | yes |
| 28 | `iris_src/src/Graph/KG/TraversalBuild.cls::BuildKG` 126-137 | `theorem_sync_changes_nothing` | proves | as above | as above | yes |
| 29 | `iris_src/src/Graph/KG/TraversalKHop.cls::KHop2CountFast` 214-225 | `fast_answer` | models | fresh-ignores-stamp | fresh_ignores_stamp (two_hop_after_write) | yes |
| 30 | `iris_src/src/Graph/KG/TraversalKHop.cls::KHop2CountFast` 214-225 | `theorem_two_hop` | proves | fresh-ignores-stamp | fresh_ignores_stamp | yes |
| 31 | `iris_src/src/Graph/KG/TraversalKHop.cls::KHop2CountExact` 227-235 | `exact_answer` | models | none directly (theorem_two_hop's exact clause passes the walk as the stored count) | exact_is_sum (two_hop_after_sync exact 1); a product reading the sum observes 3 | yes (binding) |
| 32 | `iris_src/src/Graph/KG/TraversalKHop.cls::Fresh` 240-243 | `theorem_write_makes_stale` | proves | stamp-not-equality | fresh_ignores_stamp | yes |
| 33 | `iris_src/src/Graph/KG/TraversalKHop.cls::KHop2Count` 67-133 | `walk_count` | models | walk-counts-source-and-first-hop | exact_is_sum; a walk counting the source observes two_hop_after_write 2 against 1 | yes |
| 34 | `iris_src/src/Graph/KG/TraversalBuild.cls::Build2HopStats` 939-994 | `witness_fast_overcounts` | witnesses | walk-counts-source-and-first-hop | a Build2HopStats storing the exact count observes two_hop_after_sync fast 1 against the port's 3 | yes |
| 35 | `iris_src/src/Graph/KG/TraversalBuild.cls::Build2HopExactStats` 1005-1067 | `walk_count` | models | walk-counts-source-and-first-hop | exact_is_sum; a walk counting the source observes two_hop_after_write 2 against 1 | yes |

Result: every models/proves/witnesses row passes; none relabelled. One row needed a new binding case before it passed: the Cypher `DELETE r` producer (`translate_delete_clause`), because the binding derives `DelRow` ops from the ekeys that disappeared and so would have followed a product that deleted by triple; `cypher_delete_r_rows` now pins it to one row.

Weak spots (still pass, stated): `MarkGraphGone` is theorem-only (control `mark-gone-default-graph`; the namespace-wide stale flag is not read by the binding). `row_update`'s keyed-child branch and `exact_answer` are covered by the binding only. `theorem_other_graph_untouched`'s DelRow branch is definitional in the model; the product's graph scope of `delete_edge` is pinned by the binding (`bfs_gb_n1`, GB entries).

Rows relabelled delegates/cites from the start (their own decision is not modeled): `EraseEdgeRow`, `IRISGraphStore.delete_edges/delete_nodes/delete_nodes_by_prefix`, `RemoveNode`, `sync`, `khop2_count_fast` (delegates); `write_edges`, `write_nodes`, `FillTriple`, `BuildKGKeyed` (cites; the last two are the undeclared path, not on the fixture).
