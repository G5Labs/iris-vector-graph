# Iteration 33: node and edge updates and deletes (a negative result)

Before image: seal 32 `4707322e`. Product `3eaa79cf` unchanged. Native evidence only from `ivg-retest-20261116-iris`.

## W39

Step 5's outside-family workflow: four public lifecycle methods (`store_node`, `delete_node`, `set_edge_weight`,
`delete_edge`) without an active binding. Predictions frozen from the owner statement **bodies**
([update-delete-PAIRS.md](update-delete-PAIRS.md)). All nine held; no finding. Formal:
[models/node_edge_update](../../../Verus_verification/models/node_edge_update/NOTES.md), 5 verified, 6 controls
EXPECTED_FAIL, binding AGREES (23 comparisons); the four owners link it.

## Recount

Active behavioral bindings 371 → **375** of 4,130 ([member-delta.json](member-delta.json)); lost 0.

## Next

The strongest remaining candidate: the Python property-lookup readers over API-written typed values, the non-Cypher
counterpart of the comparison vein of iterations 16-24.
