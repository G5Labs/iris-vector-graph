# Iteration 36: the embedding queue (W42)

Before image: `08ab4fff` (retest convergence). Product `3eaa79cf` unchanged. Guidance `uplift-iteration.md`
`d31f5890` (changed from `a7521d0e`), `uplift-scoring.md` `7e250023`; run identity and fixture in
[continuation-run.json](continuation-run.json). Native evidence only from the run-isolated `ivg-cont-20261117-iris`.

## Why this workflow

The updated step 1 and 5 reopen the prior stop product-wide. In the start inventory 112 production files (1,373 members)
had no active binding. `EmbedQueue.cls` and the engine's queue methods (about 27 members) hold persistence, failure and
retry decisions, had an owner block with a recorded source-only divergence, no model, and were not named among the
prior stop's judged or excluded areas.

## Result

Predictions frozen first ([PAIRS](embed-queue-PAIRS.md)). The Python worker agreed with the owner in every case. The
IRIS worker (what `start_background_embedding` runs) did not:

- **bug-srch-103 (Medium, inherited source-only divergence, now e2e reproduced and registered):** provider failure,
  an empty answer or an unknown config ends DONE with no vector and no reason.
- **bug-srch-104 (Medium, new):** it cannot store any default-graph vector (`""` binds as NULL into the NOT NULL
  `graph_id`, `-108`). The Python store writes a non-NULL empty string.
- bug-srch-006 gains evidence (its IRIS-worker consequence cannot store on a fresh install today); decision unchanged.

New model [`embed_queue`](../../../Verus_verification/models/embed_queue/NOTES.md): 6 verified, 6 controls
EXPECTED_FAIL, native binding AGREES (42 comparisons over 14 cases; four mutations detected). The owner block names the
claims; the open question records the new evidence.

## Recount ([member-delta.json](member-delta.json))

Active bindings 375 → **392** of 4,130: 17 newly reached and bound (9 in `EmbedQueue.cls`, 8 in `embeddings.py`), 1 strengthened (`get_embedding`, added reader claim), overlap 0, distinct additions 18, lost
0. Four delegating members are locators only by the project's convention (`BulkEnqueue`, `StartBackgroundTask`,
`EmbedQueueTask.OnTask`, `start_background_embedding`). Not bound: `NormStatus` (trivial), `BulkEnqueueText`,
`ClearDone`, `clear_done`, `get_embeddings` (not exercised).

Correspondence gate: the old stamp reopened everything for the new formal and product inputs
([delta](correspondence-delta-from-35.json)); a fresh stamp is [correspondence-inputs.json](correspondence-inputs.json).

## Next candidate

Return to the product-wide inventory (see the top-level handoff's queue).
