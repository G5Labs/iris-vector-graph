# Node and edge updates and deletes

Product `3eaa79cf`, unchanged. Iteration 33 (retest). Predictions frozen from the owner statement bodies before
observation in [update-delete-PAIRS.md](../../../uplift/consolidated/iteration-33/update-delete-PAIRS.md). Owners:
[structure.node.update](../../../ontology/features/graph-structure.g5.md#structure.node.update), `.node.delete`,
`.edge.weight.set`, `.edge.delete`.

## What the model decides

A store of nodes (properties and labels per graph and ID) and edges (graph, source, predicate, target → weight).
`store_node` applies each given property (a value replaces, None removes), adds the given labels and sets `id` only
when absent, answering True. `delete_node` removes the node and every edge incident to it in its graph.
`set_edge_weight` changes a default-graph edge's weight, else answers False and writes nothing. `delete_edge` removes
the triple from one graph and answers True. The SQL and adjacency-index effects are provider steps, observed natively.

## Theorems (5, all new; no imports)

`theorem_store_node_updates`, `theorem_store_new_gets_id`, `theorem_delete_node_removes_incident`,
`theorem_set_weight_default_graph_only`, `theorem_delete_edge_one_graph`. No `assume`, `admit` or `external_body`.

## Controls

Six, all EXPECTED_FAIL full and isolated: `none-keeps-property`, `labels-replaced`, `delete-node-keeps-edges`,
`weight-any-graph`, `delete-edge-every-graph`, `new-node-no-id`.

## Binding

[binding.py](binding.py) replays the nine W39 cases with fresh IDs: **AGREES, 23 comparisons**, all six mutations detected.

## Limits

Not exercised: `delete_node`'s documents, vectors and reifier cleanup; `delete_edge(all_graphs=True)`; concurrent writers.
