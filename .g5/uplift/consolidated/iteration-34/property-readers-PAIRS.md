# W40: Python property readers over API-written typed values — predictions frozen before observation

Frozen 2026-11-16, iteration 34. Before image: seal 33 `f5d4805a`. Product `3eaa79cf`. Fixture `ivg-retest-20261116-iris`.

Why this workflow: the strongest remaining candidate at the step-5 check. Ten public readers in `nodes_edges.py`
(`get_nodes_by_property`, `get_node_ids_by_property`, `get_property_values`, `get_property_pairs`,
`get_node_properties`, `get_nodes_by_label`, `nodes_exist`, `property_value_exists`, `get_node_ids_like`,
`list_graphs`) have no owner statement and no binding. They read values written through the Python API, the boundary
where iterations 16-24 found seven comparison faults on the Cypher side. Sources: API_REFERENCE lines 588-720 only
(`val: Optional[str]`, "Every value stored", "`get_node` without `id` and `labels`", "in any graph", "named graphs that
have edges"). The readers' code was not read. Verus determines none of these.

Nodes in the default graph with property `p` = 7, 7.5, "7", true; one node with `p` = 7 in a named graph.

| Case | Reader | Docs-based prediction |
|---|---|---|
| R1 | `get_nodes_by_property("p", "7")` | unknown which of 7 and "7" match (docs type `val` as a string); both readers below the same |
| R2 | `get_node_ids_by_property("p", "7")` | the same IDs as R1 |
| R3 | `get_property_values("p")` | the stored values, typed as `get_node` types them (7, 7.5, "7", True) |
| R4 | `get_property_pairs("p")` | the same values as R3, paired with subjects |
| R5 | `get_node_properties(n)` | `get_node(n)` without `id` and `labels` (so `p_id` stays), typed the same |
| R6 | `get_nodes_by_label(L)` | each node as `get_node` returns it |
| R7 | `get_nodes_by_property("p")` graph scope | unknown (the docs name no graph) |
| R8 | `nodes_exist([...])` | IDs with a node row in any graph, the named-graph one included |
| R9 | `list_graphs()` | the named graphs that have edges; a graph with only nodes is not listed |

## Outcome ([observation](property-readers-observed-20261116T222559Z.json))

| Case | Outcome |
|---|---|
| R1 | resolved: "7" (and 7) finds both the number 7 and the string "7"; "true" finds a stored true ("True" and "1" do not); "7.5" finds 7.5 |
| R2 | **miss**: 3 IDs, the named graph's included, where R1 gives 2 — already recorded as open question HD-0201 (the docs-based prediction missed; the ontology's question knew) |
| R3, R4 | **miss** for booleans: `"true"` where `get_node` gives True; numbers typed; the named graph's value included (HD-0201) → Low **bug-str-102** (new) |
| R5 | held (`p_id` stays) |
| R6 | held, default graph only |
| R7 | resolved: default graph only |
| R8 | held, every graph |
| R9 | held: a named graph with nodes only is not listed |

Material prediction gained: a new owner statement `structure.node.read.properties` now predicts all nine; the question
card HD-0201 gains the observation. No formal contract (probe-only claim, open in Verus).
