# Iteration 1 — selection before implementation reading

Start: 2026-11-15. Before image: `2a16f2192ac9600e37382cc3046be1429ed9a0c0`, clean `consolidated_uplift`. Product: `3eaa79cf77d3e0a879b2cced634cf2729d81499e`. The two reusable prompts and public `feedback-0.md` / `reviewed-plan.md` govern this continuation. No evaluator directories or unpublished cases are inputs. No delegation, remote writes, product changes or security probes.

## Rotating sample and initial predictions

Judgmental sample from ordinary unit tests in three scarcely modeled areas, plus a known contradiction. These are builder cases, not an independent holdout, and support no repository prevalence estimate. Predictions below use the inherited canonical owners and active claims; source answers are recorded separately after following producers and consumers.

| ID | Actor, two reachable neighbors, final observation | Inherited ontology prediction | Inherited formal distinction |
|---|---|---|---|
| I1-TYPE | Caller reads a node property stored as a number vs the same spelling stored as text; returned Python type differs | `query.values` predicts numeric/text distinction; `query.conformance` and `.native.sql-first` contradict it | Relationship decoder does not model node D/N marks or their producer |
| I1-IMPORT | NDJSON importer sees an unknown kind then a valid node vs malformed JSON then a valid node; return/count and written prefix differ | `install.import` says partial writes, but not unknown-kind admission | No active importer contract |
| I1-ROUTE | Repeated eligible read with a held path just before vs at its recheck threshold; next run may measure the other path | `query.native.route` permits choosing faster but gives no trigger | No active route trial contract |
| I1-READ | Batched `get_nodes` requests an existing bare node vs an absent ID; node object vs omission | Root expressly excludes this reader; graph scope alone cannot answer | Reviewed `gid_l2` covers scope, not bare-node existence/hydration |
| I1-WARM | Operator warms a graph whose SQL source enumeration succeeds vs fails while adjacency has sources; count/source population differs | `structure.degree.cache.warm` does not state standalone fallback | Degree-cache model does not derive source enumeration |

Sample sources (read before implementation): `test_get_nodes.py`, `test_edgeprop_ndjson.py`, `test_460_r218_typed_node_reads.py`, `test_460_r248_typed_node_values.py`, `test_253_native_route.py`, `test_460_native_route_trial.py`; WARM was selected from the published repair and current owner and will be revisited after the first batch.

## Intended work

First reconcile node value rules and model the node tag producer/decoder through a real batched reader. Then derive importer record admission, effects and counters from its input sequence, including failure and a cross-call typed read. Add route trial/recheck distinctions if the product boundary remains bounded. Revisit standalone warming in a different component before sealing. Repair the inventory's definition/type mismatch using the actual AST inventory. Preserve the ledger M03 and cache M21/J04 partial scopes unless their real operation/reader boundaries are modeled; links and reruns cannot promote them.

Unchanged governing blocks: `graph.key`, `graph.all_graphs_read`, `query.native.equal-answers`, `query.native.fallback`, `query.values.relationship_text`, `structure.degree.cache`, `ledger.commit`, `algorithms.cache`. Claims remain proposed recovered intent, as-built model proofs or unit observations, never direct product verification.

## Completion challenge

For every selected distinction, inspect the raw producer, final consuming reader, allowed input domain and failure path. Retain benign mutations that change the named observation. Compare each new lead by trigger and effect against all three inherited registers before assigning novelty. Preserve unanswered policy with a canonical question, bounded default and alternative. Run each changed proof/control suite and whole relevant native Python unit suite; record substituted IRIS boundaries explicitly. Seal only `.g5/` changes in commits with clean tip and an iteration handoff.
