# Bulk embedding selection

Product `3eaa79cf`, unchanged. Iteration 43 (continuation). Predictions frozen from the API reference and guides:
[embed-nodes-PAIRS.md](../../../uplift/consolidated/iteration-43/embed-nodes-PAIRS.md). Owner (new):
[search.embedding.bulk](../../../ontology/architecture/search-storage-and-indexes.g5.md#search.embedding.bulk).

## What the model decides

For one node of the requested graph: `label_ok_built` (its ID has the label in any graph) versus `label_ok_rule` (in its
own graph); `excluded` (the glob matches and contains no `_` or `%`); `selected`; and `embedded` (selected, and no
vector yet unless `force`).

## Theorems (4 verified; no imports)

`theorem_existing_vectors` (agrees), `theorem_plain_pattern_excludes` (agrees),
`theorem_special_pattern_excludes_nothing` ([bug-srch-105](../../bugs_issues.md#bug-srch-105)),
`theorem_label_from_other_graph` ([bug-srch-106](../../bugs_issues.md#bug-srch-106)).

## Controls

Four, all EXPECTED_FAIL: `escape-honoured`, `label-scoped`, `force-ignored`, `exclusion-ignored`.

## Binding

[binding.py](binding.py): 7 outcome classes through the actual `embed_nodes`: **AGREES**; each mutation detected. The
first binding run is kept with a `harness_error` note (the check expected no vector for a node the previous call had
rightly excluded).

## Limits and premises

- IRIS `LIKE` without `ESCAPE` treats a backslash literally (observed).
- The fixture model is not a SentenceTransformer, so the batch `encode` path is not exercised; `text_fn` not exercised.
- The first W49 probe run used a list-returning fixture model, which the per-text path cannot use (`.tolist()`); it is
  kept as a fixture artifact, not product evidence.
