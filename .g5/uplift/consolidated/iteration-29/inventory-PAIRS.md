# W34: the embedding inventory through the engine and the CLI — predictions frozen before observation

Frozen 2026-11-16, iteration 29. Before image: seal 28 `c2fc07dc`. Product `3eaa79cf`. Fixture `ivg-retest-20261116-iris`.

Why this workflow: step 5, an entry point no iteration examined. `cli.py` is 32/32 unbound and `embedding_inventory` has
no owner statement and no binding; the CLI's `embeddings inventory` is a second final reader of the same report.
Sources for predictions: API_REFERENCE `embedding_inventory` ("one row per embedding route, plus one per graph that has
none"), ADMIN_GUIDE lines 1128-1145 (row count "counted inside its graph", `index_state` present/refused/absent; setup
builds no index on `kg_NodeEmbeddings`; a `kg_emb_<hash>` route gets one when created, if IRIS accepts), ADMIN_API line
404 (the CLI connects to IRIS directly), and the CLI docstrings (reads only; never creates a route; `routed_tables`
counts rows that name a table). The engine's `embedding_inventory` was not read. Verus determines none of these.

| Case | History | Reader | Prediction |
|---|---|---|---|
| I1 | the fixture as it is | `embedding_inventory()` | a `kg_NodeEmbeddings` row, dimension 768, `index_state` `absent` |
| I2 | a node in a new named graph `g1`, no embedding | engine rows; CLI | one row for `g1` with no table; the CLI prints `-` and does not count it in "N routed tables" |
| I3 | one embedding stored for a default-graph node | `row_count` of `kg_NodeEmbeddings` | one more than before |
| I4 | the first embedding for a node in `g1` | engine rows; CLI | `g1` now has a `kg_emb_<hash>` row with `row_count` 1 and `index_state` `present` (or `refused` with an error); routed tables + 1; no separate no-route row for `g1` |
| I5 | the inventory read twice | routes | reading creates nothing: the same rows |
| I6 | `kg_NodeEmbeddings` holds vectors of default-graph nodes only | `row_count` | counts that graph's vectors only |
| I7 | CLI `--json-output` vs engine | payload | the same rows; `routed_tables` = rows with a table |

## Outcome ([observation](inventory-observed-20261116T220346Z.json); binding in `results/embedding_inventory/`)

All seven held. I1: the default graph has three routes (`kg_NodeEmbeddings`, `kg_EdgeEmbeddings`,
`kg_NodeEmbeddings_optimized`), each 768 wide, count 0, index `absent` (the prediction named only the first; not a
miss). I2: the new graph's row has no table; the CLI prints 8 rows and "3 routed tables". I3: 0 → 1. I4: `g1` gets
`kg_emb_<hash>`, count 1, index `present` (`idx_..._ann`), and loses its no-route row; the CLI says "4 routed tables".
I5: two reads identical. No discrepancy, no finding. Material prediction gained: the report had no owner; it now has
`search.routes.inventory`, and `embedding_inventory` binds its rows and the CLI count.
