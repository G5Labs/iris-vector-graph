# W49: embed_nodes and its readers (get_unembedded_nodes, embedding_count, get_embedding)

Selected from the unowned, unbound public methods after iteration 42: `embed_nodes`, `get_unembedded_nodes` and
`embedding_count` have no owner statement, no binding and no finding; `embed_nodes` is the documented bulk vector writer
(DATA_FORMATS.md §7). The identity rules of `search.embedding.*` govern the write; nothing states which nodes it embeds.
Sources for the predictions: API reference, USER_GUIDE §7 and §4.7.0 transactions, DATA_FORMATS §7. Verus before: none
for this writer (`search` covers the identity check).

A fixture model object with `encode(texts)` answering 768-wide vectors, as a sentence-transformers model would.

## Predictions, frozen before reading the source

| ID | Case | Reader | Predicted |
|---|---|---|---|
| E1 | three nodes labelled `Gene<run>` and one `Other<run>`; `embed_nodes(model, label=Gene<run>)` | `get_embedding`, `embedding_count()` | the three Gene nodes have vectors; the Other node none; the count rises by 3 |
| E2 | neighbor: a fourth Gene node added, then `missing_only=True` | the answer; vectors | only the new node is embedded |
| E3 | neighbor of E2 without `missing_only` and without `force` | the answer | not predicted with confidence: either every Gene node is embedded again or those with vectors are skipped |
| E4 | `node_ids=[one id]` | vectors | only that node is embedded |
| E5 | `exclude_pattern` | | not predicted with confidence (the reference does not say glob, regex or SQL LIKE) |
| E6 | the same label in a named graph G, `embed_nodes(..., graph=G, model_key=k)` | `get_embedding(id, graph=G, model_key=k)`; the default graph's vectors | G's nodes get vectors in G's route for k; the default graph's are unchanged |
| E7 | `get_unembedded_nodes(graph=G, model_key=k)` before and after E6 | ids | before: G's nodes; after: none of them |

## Outcome (observed after the freeze)

The first probe run used a fixture model whose `encode` returned lists; the per-text path calls `.tolist()`, so every
node errored — a fixture artifact, kept in the run directory's stderr only and not counted. The corrected run:
[observation](embed-nodes-observed-20261117T010321Z.json); then the [binding](../../../Verus_verification/results/embed_selection/20261117T010437Z-binding/receipt.json) (AGREES).

| ID | Held? | What happened |
|---|---|---|
| E1 | partly | the Gene nodes got vectors and the Other node none; but the exclusion `<prefix>_skip*` excluded nothing (new bug-srch-105) |
| E2 | yes | only the new node |
| E3 | (resolved) | without `force` the nodes that have a vector are skipped (`skipped` counts them); `force` re-embeds all |
| E4 | yes | only the listed node |
| E5 | (resolved) | a glob: `*skip*` excludes; any `_` or `%` makes it match nothing |
| E6 | yes | G's labelled nodes got vectors in G's route for k |
| E7 | yes | before: G's nodes; after: only the unlabelled one |

Added after reading the source (not frozen): E8, a G node whose label exists only on its default-graph twin is embedded
(new bug-srch-106). Also: the text embedded is the node ID unless `text_fn` is given (now in the owner). Material
prediction gained: the new owner `search.embedding.bulk` predicts selection, skipping and the two defects.
