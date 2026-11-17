# One-hop retrieval scope

Product `3eaa79cf`, unchanged. Iteration 42 (continuation). Predictions frozen from the API reference:
[neighbors-PAIRS.md](../../../uplift/consolidated/iteration-42/neighbors-PAIRS.md). Owner (new):
[algorithms.op.neighbors](../../../ontology/features/algorithms.g5.md#algorithms.op.neighbors).

## What the model decides

Decision tables: which graphs `kg_NEIGHBORS` and `kg_NEIGHBORHOOD_EXPANSION` read (`neighbors_reads`,
`expansion_reads`), which edges the expansion keeps (`expansion_keeps`), and whether `kg_NEIGHBORS` appends a target
(`appended`, one `seen` set across chunks).

## Theorems (3 verified; no imports)

`theorem_scopes_differ` (question [algorithms.op.neighbors.scope](../../open_questions.md#algorithms.op.neighbors.scope)),
`theorem_confidence_filter`, `theorem_distinct_across_chunks`. No `assume`, `admit` or `external_body`.

## Controls

Four, all EXPECTED_FAIL: `neighbors-default-only`, `missing-confidence-kept`, `strict-threshold`, `dedupe-per-chunk`.

## Binding

[binding.py](binding.py): six outcome classes through the actual operators (chunk size 1 to force chunking):
**AGREES**; each of four mutations is detected.

## Limits

`kg_PPR`, `kg_RERANK` (delegates to `kg_RRF_FUSE`), `kg_PPR_GUIDED_SUBGRAPH` and the `in`/`both` directions beyond
W48's cases are not modeled; a Cypher error inside `kg_NEIGHBORS` would be skipped silently (inspected, not observed).
