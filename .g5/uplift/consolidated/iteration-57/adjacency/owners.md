# Iteration 57 W2: proposed owner edits (saved by the builder from W2's report; applied by the builder)

Paths: `ontology/features/graph-structure.g5.md` unless noted; additive; no open question needed.

- `structure.multigraph.layout` + "The one-to-two transition keeps the earlier edge as a keyed entry with its own weight, whatever order the rows are written or rebuilt in." + Verus `lemma_create`, `lemma_second`
- `structure.multigraph.count` + "Deleting one of two parallel edges (Cypher `DELETE r`) leaves the other: the target is still reached, the triple carries the survivor's weight, and the degree drops by one." + Verus `theorem_delete_one_parallel_keeps_other`
- `structure.adjacency` + "Removing a triple from one graph leaves the interned snapshot's merged edge while another graph still holds the triple." + Verus `theorem_nkg_held_elsewhere`, `theorem_mark_graph_gone`
- `structure.drift` + "With a declared index, a rebuild after any mix of edge creates, single-relationship deletes, edge, node and prefix deletes and weight changes leaves every entry as it was." + Verus `theorem_incremental_equals_rebuild`, `theorem_sync_changes_nothing`
- `structure.edge.delete` + "Deleting an edge from one graph leaves the same triple in every other graph, with its adjacency entry and traversal answers." + Verus `theorem_other_graph_untouched`
- `structure.node.delete` + "A delete by ID or prefix in one graph leaves the same IDs, their edges and labels in other graphs; another node with the same label keeps it." + Verus `theorem_erase_nodes_takes_incident`, `theorem_label_delete_scoped`
- `structure.rebuild` + "Without the accelerator library, `sync()` still rebuilds the interned snapshot with the ObjectScript builder."
- `structure.rebuilt.stamp` + "Today `khop2_count_fast` with a type answers, while the two-hop statistics are current, the sum of the middle nodes' out-degrees, which counts the source reached back and a target once per middle node; after any write it answers the walked count (bug-str-117)." + Verus `theorem_two_hop`, `witness_fast_overcounts`, `theorem_write_makes_stale`
