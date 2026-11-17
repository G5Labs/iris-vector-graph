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

## Theorems (iteration 47: 9 verified; iteration 50: 19 verified; no imports)

`theorem_insert_then_delete` (agrees), `theorem_same_cell_reinsert_counts_twice` and
`theorem_cross_cell_reinsert_leaves_stale_entry` ([bug-srch-107](../../bugs_issues.md#bug-srch-107)),
`theorem_other_width_answered` ([bug-srch-108](../../bugs_issues.md#bug-srch-108)); `theorem_cosine_ranks_as_dot` (for
every query and pair of vectors, "cosine" scores and orders exactly as "dot") and `theorem_cosine_metric_misranks`
(q = (3,4): (10,0) above (3,4), while the cosine rule puts (3,4) first) ([bug-srch-109](../../bugs_issues.md#bug-srch-109));
neighbor `theorem_equal_lengths_agree` (iteration 50, m9: for every query and every pair of vectors of the same
nonzero length, the dot order agrees with the cosine rule; the iteration-47 example is kept as
`theorem_equal_lengths_witness`).

Iteration 50 (review 47-49 m8): which cell a vector goes to. `build_cell` (the build's k-means label: Euclidean-nearest
centroid, whatever the metric) against `insert_cell` (Insert's own copy of the metric branch: dot product for "cosine"
and "dot"). `theorem_l2_insert_matches_build` (every vector and centroid pair: under "l2" both agree) and
`theorem_cosine_reinsert_changes_cell` (c0 = (1,0), c1 = (5,5), v = (2,0): the build and the cosine rule put v in c0,
Insert puts it in c1, so re-inserting the unchanged vector leaves a second entry, bug-srch-107's cross-cell case).

## Controls

Iteration 50: seven, all EXPECTED_FAIL, each failing exactly its named theorems
(`results/ivf_entries/20261117T0324*-control-*`): `insert-replaces`, `delete-all`, `width-checked`, `delete-noop`,
`cosine-normalized` (the repaired order: `ivf_above` uses `cosine_above` under "cosine"; fails exactly the two
departures), `cosine-takes-l2-branch` (Search's first branch picks another scorer; it now names
`theorem_cosine_metric_misranks` too, which it always failed: iteration 47's receipt shows 4 errors for 1 named
theorem, the extra one from the old equal-length example, whose proof now also states the distances) and
`insert-by-distance` (Insert picks the cell by distance, as the build does; fails `theorem_cosine_reinsert_changes_cell`,
the l2 neighbor verifies).

## Binding

[binding.py](binding.py): four cases through the actual IVF calls, the cells taken from `ivf_insert`'s answers, plus
(iteration 47) the cosine case read through `ivf_search` and through SQL `kg_IVF` (order and scores against the port
of `entry_score`): **AGREES** 6 cases; each of the six mutations detected; altering the observed `kg_IVF` order is
detected ([receipt](../../results/ivf_entries/20261117T014907Z-binding/receipt.json)). Iteration 50: **AGREES 9 cases**,
all seven mutations and the tamper detected ([receipt](../../results/ivf_entries/20261117T032444Z-binding/receipt.json)):
`cell_cosine`, `cell_dot` and `cell_l2` build a two-cell index over a short and a long cluster, read the build's cell
for a1 = (1.2, 0, 0, 0) from `^IVF(name,"list",cell,node)`, re-insert a1 with the same vector and read Insert's cell:
cosine and dot move it to the long cluster's cell (now in both cells, `indexed` + 1), l2 keeps it. The port takes the
centroids as the clusters' means under the observed labels (provider input).

## Limits

Build, rebuild and drop (W52 V1, V9, V10) are observed and stated in the owner; the clustering itself (k-means) is a
provider and not modeled (its labels are taken as the Euclidean-nearest final centroid, observed for separated
clusters); `nprobe` below `nlist` is not exercised. Insert's cell choice is modeled and observed (iteration 50); Search's
choice of cells to probe uses the same metric branch (inspected, not separately observed). Vectors are integers in the model and floats on IRIS; scaling by a
positive constant preserves both orders. `vector_search`'s IVF fallback and `kg_RRF_FUSE`'s IVF leg read the same
`Search` but were not exercised (the fixture supports `VECTOR_COSINE`).
