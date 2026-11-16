# Iteration 29: the embedding inventory through the engine and the CLI (a negative result)

Before image: seal 28 `c2fc07dc`. Product `3eaa79cf` unchanged. Native evidence only from `ivg-retest-20261116-iris`.

## W34

Step 5: an entry point no iteration examined (`cli.py` 32/32 unbound) and a report with no owner and no binding
(`embedding_inventory`). Predictions frozen from the API reference, ADMIN_GUIDE, ADMIN_API and the CLI docstrings
([inventory-PAIRS.md](inventory-PAIRS.md)). All seven held, including the CLI's routed-table count (3 → 4) and the new
route's HNSW index. No finding.

- New owner [search.routes.inventory](../../../ontology/features/search.g5.md#search.routes.inventory) (346 blocks).
- Formal: [models/embedding_inventory](../../../Verus_verification/models/embedding_inventory/NOTES.md), 3 verified, 3
  controls EXPECTED_FAIL; binding AGREES in two states including the CLI JSON, all mutations detected.

## Recount

Active behavioral bindings 349 → **357** of 4,130 ([member-delta.json](member-delta.json)): 8 newly reached and bound
(`embedding_inventory`, `_graphs_with_nodes`, `_registry_inventory_rows`, `EmbeddingInventoryRow`, and four CLI
members); lost 0.

## Bearing on convergence

Second consecutive batch outside the defect families with no changed outcome prediction (W33 option validation, W34
reporting/CLI). The strongest remaining candidate is the unrun PLAID branch of F-0608.
