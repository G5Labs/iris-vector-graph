# The embedding inventory and its CLI reader

Product `3eaa79cf`, unchanged. Iteration 29 (retest). Predictions frozen before observation in
[inventory-PAIRS.md](../../../uplift/consolidated/iteration-29/inventory-PAIRS.md). Owner (new):
[search.routes.inventory](../../../ontology/operations/search-indexes.g5.md#search.routes.inventory).

## What the model decides

`report(routes, graphs)` transcribes `SchemaMixin.embedding_inventory`: one row per registry route (its graph, table,
count and index state), then a no-route row for each graph with nodes that has no route. `routed_tables` is the CLI's
count of rows naming a table (`cli._inventory_payload`). The registry rows, per-graph counts and the class dictionary's
HNSW indexes are inputs (provider reads); their mutual consistency across separate reads is not modeled.

## Theorems (3, all new; no imports)

`theorem_unrouted_graph_reported` (US4-3), `theorem_routed_graph_has_no_empty_row`, `theorem_rows_name_table_iff_route`
(so the CLI's count equals the number of routes). No `assume`, `admit` or `external_body`.

## Controls

Three, all EXPECTED_FAIL full and isolated: `omit-unrouted-graphs`, `every-graph-gets-empty-row`, `empty-row-names-a-table`.

## Binding

[binding.py](binding.py): the actual report and the actual `ivg embeddings inventory --json-output` in two states (a new
named graph without, then with, its first embedding), against the model's report built from the engine's route rows and
an independent `SELECT DISTINCT` of the graphs with nodes: **AGREES**, CLI rows equal the engine's, routed-table count
as predicted, all three mutations detected. The W34 probe separately observed the per-graph count (0 → 1) and the new
route's `present` HNSW index.

## Limits

Route counts and index states are taken from the report, not re-derived; the text table's layout is not checked beyond
its last line; `recall_measured` and the refused-index path are not exercised.
