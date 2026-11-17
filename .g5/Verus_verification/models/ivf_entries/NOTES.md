# IVF index entries

Product `3eaa79cf`, unchanged. Iteration 46 (continuation). Predictions frozen from the API reference and owners:
[ivf-PAIRS.md](../../../uplift/consolidated/iteration-46/ivf-PAIRS.md). Owner (new):
[search.ivf](../../../ontology/features/search.g5.md#search.ivf).

## What the model decides

One node's entries in a two-cell index (`in0`, `in1`) and the reported size (`indexed`) under `insert` (into the cell
`ivf_insert` reports) and `delete` (the first cell's copy only); `search_answers` (no width check). Iteration 47
(W53): `entry_score` transcribes `IVFIndex.Search`'s three scoring branches over integer vectors (`dot`, `sqdist`),
`ivf_above` its order, and `cosine_above` the rule for metric "cosine" (dot/|v|, compared exactly without roots).
Owner: [search.ivf.metric](../../../ontology/features/search.g5.md#search.ivf.metric).

## Theorems (9 verified incl. the two recursive spec functions; no imports)

`theorem_insert_then_delete` (agrees), `theorem_same_cell_reinsert_counts_twice` and
`theorem_cross_cell_reinsert_leaves_stale_entry` ([bug-srch-107](../../bugs_issues.md#bug-srch-107)),
`theorem_other_width_answered` ([bug-srch-108](../../bugs_issues.md#bug-srch-108)); `theorem_cosine_ranks_as_dot` (for
every query and pair of vectors, "cosine" scores and orders exactly as "dot") and `theorem_cosine_metric_misranks`
(q = (3,4): (10,0) above (3,4), while the cosine rule puts (3,4) first) ([bug-srch-109](../../bugs_issues.md#bug-srch-109));
neighbor `theorem_equal_lengths_agree` (equal lengths: both orders agree).

## Controls

Six, all EXPECTED_FAIL: `insert-replaces`, `delete-all`, `width-checked`, `delete-noop`, `cosine-normalized` (the
repaired order: `ivf_above` uses `cosine_above` under "cosine"; fails exactly the two departures and leaves
`theorem_equal_lengths_agree` verified) and `cosine-takes-l2-branch` (Search's first branch picks another scorer).

## Binding

[binding.py](binding.py): four cases through the actual IVF calls, the cells taken from `ivf_insert`'s answers, plus
(iteration 47) the cosine case read through `ivf_search` and through SQL `kg_IVF` (order and scores against the port
of `entry_score`): **AGREES** 6 cases; each of the six mutations detected; altering the observed `kg_IVF` order is
detected ([receipt](../../results/ivf_entries/20261117T014907Z-binding/receipt.json)).

## Limits

Build, rebuild and drop (W52 V1, V9, V10) are observed and stated in the owner; the clustering itself (k-means) is a
provider and not modeled; `nprobe` below `nlist` is not exercised. The cosine branch in `Insert`'s cell choice is the same expression as
Search's (inspected), not separately observed. Vectors are integers in the model and floats on IRIS; scaling by a
positive constant preserves both orders. `vector_search`'s IVF fallback and `kg_RRF_FUSE`'s IVF leg read the same
`Search` but were not exercised (the fixture supports `VECTOR_COSINE`).
