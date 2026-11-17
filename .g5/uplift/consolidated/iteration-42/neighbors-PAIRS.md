# W48: one-hop retrieval operators (kg_NEIGHBORS, kg_MENTIONS, kg_NEIGHBORHOOD_EXPANSION)

Selected from the unowned, unbound public methods after iteration 41 (a different family from the import work of
iterations 38-41): `operators.py` (19 members, 0 bound) and the engine's `kg_NEIGHBORS`, `kg_MENTIONS` and
`kg_NEIGHBORHOOD_EXPANSION` are retrieval steps of GraphRAG pipelines, and no owner statement names them. Sources for the
predictions: the API reference only. Verus before: nothing.

## Predictions, frozen before reading the source

| ID | Case | Reader | Predicted |
|---|---|---|---|
| N1 | a→b, a→c (type R) | `kg_NEIGHBORS([a])` | {b, c} |
| N2 | neighbor: `direction="in"` from b | | {a} |
| N3 | neighbor: `direction="both"` from b, with b→d | | {a, d} |
| N4 | `predicate="R"` with a→e of type Q | | {b, c}; e absent |
| N5 | two sources a, a2 both →b; `distinct=True` vs `False` | list | b once with True; twice with False |
| N6 | 1,200 sources all → one target t (more than `chunk_size` 500), `distinct=True` | list | t once (the distinct promise holds across chunks) |
| N7 | the same edges only in a named graph | `kg_NEIGHBORS` (no graph argument) | nothing: the default graph only, as the other unscoped operators read it |
| N8 | `kg_MENTIONS([a])` with a -MENTIONS-> m | | {m} |
| N9 | `kg_NEIGHBORHOOD_EXPANSION([a], confidence_threshold=500)` with edges of confidence 900, 500, 100 and one without | dicts | the 900 and 500 edges, highest first; the other two absent |

## Outcome (observed after the freeze)

[Observation](neighbors-observed-20261117T005928Z.json), then the [binding](../../../Verus_verification/results/retrieval_scope/20261117T010033Z-binding/receipt.json) (AGREES
with `retrieval_scope.rs`). 10 of 11 cases held (N1, N1b, N2-N6, N8, N9; N5 has two). N7 missed: `kg_NEIGHBORS` reads
every graph (named-graph-only edges are returned, and a seed ID in two graphs gives both graphs' neighbors), as Cypher
without `USE GRAPH` does, while `kg_NEIGHBORHOOD_EXPANSION`, `kg_PPR` and the walks read the default graph. That
is recorded as the question `algorithms.op.neighbors.scope`, not a finding: no source states the intended scope.
No finding. Material prediction gained: the new owner `algorithms.op.neighbors` predicts every case.
