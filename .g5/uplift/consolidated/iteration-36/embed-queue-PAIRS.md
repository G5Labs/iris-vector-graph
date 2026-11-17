# W42: the embedding queue, from enqueue to the vector reader

Selected from the product-wide inventory at the start of iteration 36 (guidance d31f5890): `iris_src/src/Graph/KG/EmbedQueue.cls`
(14 members) and the engine's queue methods in `_engine/embeddings.py` have no active binding, the prior stop never named
the queue as judged, and it holds persistence, failure and retry decisions. Owner: `search.embedding.queue`
(statement, two working assumptions, bug-srch-006, HD-0604). Verus before this iteration: no model; nothing determines
any case below.

## Predictions, frozen before reading the queue's source (from the owner block and `docs/API_REFERENCE.md` only)

Changing input or history, the reader, expected difference:

| ID | Case | Reader | Predicted |
|---|---|---|---|
| Q1 | `enqueue_for_embedding(node_ids=[a, b], embedding_config=C, graph=G)` on a graph with no route for C | return value; `embed_queue_pending()` | returns 2; pending rises by 2; G gains a route for C (changelog 4.x: enqueue creates the route) |
| Q2 | neighbor of Q1: the target table already records a different model identity | same | refused before anything is queued (owner: "checked before it is queued"); pending unchanged |
| Q3 | `process_embed_queue` on a batch whose entries all name the model the worker produces | queue entry status; `get_embedding(node, graph=G, model_key=C)` | every entry done; every vector readable in G's route |
| Q4 | neighbor of Q3: one entry names another model | that entry's status; the other entries; the vector reader | that entry is an error with a reason, the rest are done and stored |
| Q5 | neighbor of Q3: one entry's text cannot be embedded or its vector cannot be stored | entry status; vector reader | error with the reason, never done; no vector |
| Q6 | a second worker while the first holds a batch | entry status | not predicted as an outcome: single-worker is an unenforced premise (HD-0604) |

The owner also records an observed divergence for the IRIS worker (`ProcessBatch`): a failed prepare or no-row answer is
marked done. That is the inherited suspicion this workflow can reproduce or withdraw.

## Outcome (observed after the freeze)

Observations: [1](embed-queue-observed-20261117T001118Z.json) (Python worker; IRIS worker by `ProcessBatch`),
[2](embed-queue-observed2-20261117T001204Z.json) (IRIS worker through `start_background_embedding`, default versus named
graph), then the [binding](../../../Verus_verification/results/embed_queue/20261117T001547Z-binding/receipt.json) (14
fresh cases, AGREES with `embed_queue.rs`). The IRIS worker needs a provider; Community has none, so a fixture-only
`%Embedding.Interface` class ([fixture/](fixture/W42.FixtureEmbedding.cls)) stands in. Its three answers (a vector,
nothing, a failure) were checked against `SELECT EMBEDDING()` first: vector; NULL; `SQLCODE -400`; an unknown config is `-280`.

| ID | Held? | What happened |
|---|---|---|
| Q1 | yes | returned 4, pending 4 (default graph). For a named graph the route was created at the config's width (observation 2). |
| Q2 | not exercised | the default table was undeclared, so a named model was accepted (Q4 setup). The cross-table identity case is bug-srch-006's subject, tagged outside active reproduction; set aside. |
| Q3 | Python yes; IRIS split | Python worker: DONE and a 768-wide vector. IRIS worker: named graph DONE and stored; **default graph ERROR `-108`, nothing stored** (new bug-srch-104). |
| Q4 | yes | Python worker: the entry asking for `w42-fixture` became ERROR with the identity reason; the rest of the batch finished. |
| Q5 | Python yes; IRIS **no** | Python worker: failure, empty and wrong-width answers end ERROR with the reason. IRIS worker: failure, empty answer and unknown config end **DONE with no vector and no reason** (bug-srch-103, the owner's recorded divergence, now reproduced). |
| Q6 | not run | single-worker premise unchanged (HD-0604). |

Misses: Q3 and Q5 for the IRIS worker. Material prediction gained: from `search.embedding.queue` plus the new
observation a reader can now predict, per worker and graph kind, whether queued work ends DONE with a vector, DONE
without one, or ERROR. Formal claim that rejects the wrong outcome: `rule_ok` with
`theorem_iris_unanswered_marked_done` (as-built violates it) and the control `rule-allows-done-without-vector`.
