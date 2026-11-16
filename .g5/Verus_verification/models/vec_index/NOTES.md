# VecIndex: inserts, builds, counts, width and ranking

Product `3eaa79cf`, unchanged. Iteration 27 (retest). Predictions frozen before native observation in
[vecindex-PAIRS.md](../../../uplift/consolidated/iteration-27/vecindex-PAIRS.md) (docs-based first, then marked
source-based additions). Owner: [search.vecindex](../../../ontology/features/search.g5.md#search.vecindex), written in
this iteration (no owner stated VecIndex results before).

## What the model decides

An index holds its stored vectors, `meta.count`, the recorded width, the number of trees, the current planes and the
leaf membership. `reach(planes, v)` is the leaf a vector reaches; it is uninterpreted (random planes) and the same for
`InsertIntoTree` and the primary descent of `SearchTree`. `create` sets settings and a zero count and keeps vectors and
trees; `insert` stores the vector, sets the width to its length, adds one to the count and adds the ID to the leaf it
reaches in each tree; `build` re-places every stored vector under new planes; `drop` empties everything. A search ranks
the candidates (the leaf the query reaches; every stored vector when there are no trees) by distance, ascending, and
`score` maps the distance to the reported score per metric. Source lines are in the header of [vec_index.rs](vec_index.rs).

## Theorems (8, all new; no imports)

`theorem_insert_found_by_identical_query` (V3), `theorem_build_places_every_vector`, `theorem_reinsert_inflates_count`
(F-0608), `theorem_distinct_inserts_count_vectors` (the passing neighbor), `theorem_recreate_zero_count_keeps_vectors`
(bug-srch-101; stated for an index without trees, observed with trees on a one-leaf index), `theorem_insert_overwrites_dim`
(F-0608 width), `theorem_drop_empties_search` (V12), `theorem_score_mapping` (V5-V7). No `assume`, `admit` or
`external_body`; bundled vstd only. The ranking itself (sort by distance, then ID) and the metric arithmetic are not
proved; the binding checks them natively.

## Controls

Six, all EXPECTED_FAIL full and isolated: `insert-not-into-trees` (the API reference's description),
`count-only-new-ids` and `refuse-other-width` (the repair proposals), `create-keeps-count`, `build-keeps-old-planes`,
`dot-score-is-distance`.

## Binding

[binding.py](binding.py): for each of the five metrics a seeded sequence (seed 20261116) of 30 operations on a fresh
index of at most 12 vectors (one-leaf trees, exact ranking): inserts of new and stored IDs, builds, searches, expands, a
re-create and one 2-wide insert, then a drop. After every operation `vec_info` count and width and every hit's ID,
score and distance are compared with a port: **AGREES, 160 operations, 215 comparisons**; five of six mutations
detected (`build_keeps_old_planes` cannot change a one-leaf tree). The **first run DISAGREED** in two l2 searches: the
port padded the 2-wide vector with zeros, while `$vectorop` stops at the shorter vector. The provider premise in the
model header and the port were corrected; that receipt is kept.

## Limits

Transcription with native agreement; no product body is verified. Not checked: multi-leaf trees and `nprobe`
(approximate search), plane selection in `BuildTree`, `vec_bulk_insert`, `vec_search_multi`, the unsupported
`Mahalanobis` helper, concurrent writers, erasure (owned by the erasure pages' open question).
