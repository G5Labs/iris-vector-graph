# W39: node and edge updates and deletes through their readers — predictions frozen before observation

Frozen 2026-11-16, iteration 33. Before image: seal 32 `4707322e`. Product `3eaa79cf`. Fixture `ivg-retest-20261116-iris`.

Why this workflow: step-5 inventory. Of `NodesEdgesMixin`'s public methods, `store_node`, `delete_node`, `delete_edge`,
`set_edge_weight` and the property readers have no active binding; they are ordinary lifecycle and data-representation
paths every application uses. Sources: the statement **bodies** of `structure.node.update`, `structure.node.delete`,
`structure.edge.weight`, `structure.edge.weight.set`, `structure.edge.delete`. The methods were not read. Verus
determines none of these.

| Case | History | Reader | Owner prediction |
|---|---|---|---|
| U1 | `create_node(n, labels=[A], properties={p: 1, q: "x"})`; `store_node(n, {p: 2, q: None}, labels=[B])` | `get_node`, Cypher `RETURN n.p, n.q, labels(n)` | p = 2 (a number), q gone, labels A and B; returns True |
| U2 | `store_node(m, {p: 3})` for a new ID | same | created, with `id` = m and p = 3; True |
| D1 | `delete_node(n)` with an edge n→k | `get_node(n)`; Cypher edge from k's side; `^KG("out")` of n | node, labels, properties and the edge gone; k stays |
| W1 | `set_edge_weight(s, R, o, 2.5)` on a default-graph edge | Cypher `r.weight`; `^KG("out", 0, s, R, o)` | True; both read 2.5 |
| W2 | `set_edge_weight` on a triple with no edge | return; readers | False; nothing written |
| W3 | `set_edge_weight` on a triple that exists only in a named graph | return; that graph's edge | False (default graph only); unchanged |
| E1 | `delete_edge(s, R, o)` on a default-graph edge | Cypher; `^KG("out")` | removed; reports success |
| E2 | `delete_edge` on a triple with no edge | return | reports success |
| E3 | `delete_edge(s, R, o)` without naming a graph, for a triple in a named graph | that graph's edge | stays (one graph unless the caller asks for every graph) |

## Outcome ([observation](update-delete-observed-20261116T222255Z.json); binding in `results/node_edge_update/`)

All nine held: U1 p 2, q gone, labels UA and UB, True; U2 created with `id` and p 3; D1 node, edge and both adjacency
entries gone, k stays; W1 True, `r.weight` 2.5 (float) and `^KG` "2.5"; W2 False, nothing written; W3 False, the named
graph's weight stays 1.0; E1 removed; E2 True; E3 the named graph's edge stays. No finding: the owner statements predict
this family completely. Gained: `node_edge_update` binds four previously unbound public methods.
