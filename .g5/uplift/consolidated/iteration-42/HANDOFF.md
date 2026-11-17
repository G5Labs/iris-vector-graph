# Iteration 42: one-hop retrieval operators (W48)

Before image: seal 41 `d73ffaf1`. Product `3eaa79cf` unchanged. Native evidence only from `ivg-cont-20261117-iris`.

## Why this workflow

A different family from the import work of iterations 38-41: `operators.py` (0 of 19 bound) and the engine's
`kg_NEIGHBORS`, `kg_MENTIONS` and `kg_NEIGHBORHOOD_EXPANSION` had no owner and no binding.

## Result

Predictions frozen first ([PAIRS](neighbors-PAIRS.md)): 10 of 11 held; no finding. The miss (N7, an assumed
default-graph scope) became the question `algorithms.op.neighbors.scope`. New owner `algorithms.op.neighbors`; new
model [`retrieval_scope`](../../../Verus_verification/models/retrieval_scope/NOTES.md): 3 verified, 4 controls
EXPECTED_FAIL, native binding AGREES.

## Recount ([member-delta.json](member-delta.json))

Active bindings 426 → **428**: 2 newly reached and bound (`kg_NEIGHBORS`, `kg_NEIGHBORHOOD_EXPANSION`); `kg_MENTIONS`
and the three `operators.py` wrappers are locators (delegates). Lost 0. Correspondence: [delta from
41](correspondence-delta-from-41.json), fresh [stamp](correspondence-inputs.json).
