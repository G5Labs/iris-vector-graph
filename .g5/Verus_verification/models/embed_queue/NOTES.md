# Embedding queue workers

Product `3eaa79cf`, unchanged. Iteration 36 (continuation). Predictions frozen from the owner block and the API
reference before the source was read: [embed-queue-PAIRS.md](../../../uplift/consolidated/iteration-36/embed-queue-PAIRS.md).
Owner: [search.embedding.queue](../../../ontology/features/search.g5.md#search.embedding.queue).

## What the model decides

One queue entry at a time, as an `Entry` of the inputs that decide its fate: default or named graph, whether its node
is in that graph, whether a named graph has a route and a writable element type, whether IRIS knows its config, what
the provider answers (a vector, nothing, or a failure), whether the vector fits the target's width, and whether it
asks for the model the worker produces. The result is an `Outcome`: status, whether a reason is recorded, whether a
vector is stored.

- `rule_ok` is the owner's rule (L1): the entry leaves PENDING; DONE exactly when the vector is stored; ERROR always
  with a reason; an entry for another model is an ERROR.
- `iris_worker` transcribes `EmbedQueue.ProcessBatch` (the method `EmbedQueueTask.OnTask` calls, which
  `start_background_embedding` starts). `py_worker` transcribes `process_embed_queue` run to completion.
- `iris_worker_reviewed` is a proposed repair, not the product: no answer is an ERROR, and the default graph is bound
  as the SQL empty string.

## Theorems (6, all new; no imports)

| Theorem | Claim | Disposition |
|---|---|---|
| `theorem_python_worker_meets_rule` | for a node in its graph, the Python worker's outcome satisfies `rule_ok` | as-built agrees |
| `theorem_iris_named_success_stored` | named graph, route, known config, vector of the right width: DONE and stored | as-built agrees |
| `theorem_iris_unanswered_marked_done` | provider failure, empty answer or unknown config past the guards: DONE, not stored, no reason, and `!rule_ok` | [bug-srch-103](../../bugs_issues.md#bug-srch-103) |
| `theorem_iris_default_graph_never_stores` | a default-graph entry is never stored | [bug-srch-104](../../bugs_issues.md#bug-srch-104) |
| `theorem_reviewed_iris_meets_rule` | the reviewed repair satisfies `rule_ok` on every entry | proposal checked formally only |
| `theorem_interrupted_mark_breaks_rule` | the Python worker's state between SetResult DONE and the store violates `rule_ok` | [open question](../../open_questions.md#search.embedding.queue.processing) |

No `assume`, `admit` or `external_body`.

## Controls

Six, all EXPECTED_FAIL at the named theorem: `iris-unanswered-is-error`, `iris-default-insert-ok`,
`python-done-on-provider-failure`, `python-skips-identity`, `reviewed-keeps-done-on-no-answer`,
`rule-allows-done-without-vector` (the last shows the rule itself separates DONE-without-vector from DONE-with-vector).

## Binding

[binding.py](binding.py) runs 14 fresh entries through the actual workers on the run-isolated continuation fixture and
reads them back with `GetEntry` (status, reason) and `get_embedding` in the entry's graph and model (stored vector):
**AGREES, 42 comparisons**, nothing left pending; the four port mutations that mirror product-facing controls are each
detected. Cases: Python worker P1 vector, P2 failure, P3 wrong width, P4 empty, P5 other model; IRIS worker on the
default graph I1 vector, I2 failure, I3 empty, I4 no config; on a named graph I5 vector, I6 failure, I7 empty, I8 no
config (no route), I9 node in another graph. The task path (`start_background_embedding` → `OnTask` → `ProcessBatch`)
agreed separately for six of these shapes ([observation 2](../../../uplift/consolidated/iteration-36/embed-queue-observed2-20261117T001204Z.json)).

## Premises and limits

- Providers are fixture substitutes: a Python callable for the engine's embedder, and the fixture-only
  `W42.FixtureEmbedding` (`%Embedding.Interface`) behind `%Embedding.Config` `w42-fixture`, width 768
  ([class](../../../uplift/consolidated/iteration-36/fixture/W42.FixtureEmbedding.cls)). A production provider
  (sentence-transformers, OpenAI) can fail, time out or answer nothing; that it surfaces as `SQLCODE` -400 through
  dynamic SQL is observed for this IRIS build with the fixture provider, not for each real provider.
- `iris_insert_ok` is a provider premise observed on IRIS 2026.1: the empty default-graph name binds as NULL and
  `kg_NodeEmbeddings.graph_id` is NOT NULL (`-108`). An install whose `graph_id` accepts NULL is not examined.
- `width_ok` and `dtype_ok` are inputs; only DOUBLE routes and the 768 default width were exercised.
- Not modeled or exercised: two workers at once (HD-0604), free-text entries, `ClearDone`, an interruption between the
  Python worker's two writes (stated as a theorem about the intermediate state, not observed).
