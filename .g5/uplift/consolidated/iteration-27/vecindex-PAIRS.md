# W32: the VecIndex lifecycle through vec_search — predictions frozen before observation

Frozen 2026-11-16, iteration 27. Before image: seal 26 `39bed451`. Product `3eaa79cf`. Fixture `ivg-retest-20261116-iris`.

Why this workflow: step 1 and step 5 both point here. `iris_src/src/Graph/KG/VecIndex.cls` has 32 of 32 members
without an active binding; the ontology defines VecIndex only as a named index and in erasure scope, so **no owner
states what a search returns** (an ontology coverage gap). Public outcome: nearest-neighbour results. Outside every
family investigated in iterations 14-26.

Sources for predictions: API_REFERENCE `vec_*` (lines 1150-1226) only. `VecIndex.cls` and `_engine/vector.py` were
not read. Verus determines none of these.

Setup per case: `vec_create_index(name, dim=3, metric)`; small vectors so that a tree's leaf (default 50) holds all.

| Case | Changing input or history | Reader | Docs prediction |
|---|---|---|---|
| V1 | insert 4 vectors, no build | `vec_search(q, k=2)` | brute force: the 2 nearest, nearest first; cosine `score` = cosine, `distance` = 1 - cosine |
| V2 | V1 then `vec_build` | same | same answer as V1 (small index: one leaf holds all) |
| V3 | V2 then `vec_insert` a vector equal to `q` | same | the new vector is **not** returned until the next `vec_build` (the index has trees) |
| V4 | V3 then `vec_build` | same | the new vector is first with score 1.0 |
| V5 | k = 10 with 5 vectors | `vec_search` | 5 hits |
| V6 | same vectors, metric `dot` vs `cosine`, one long vector pointing away from `q`'s direction slightly | order | cosine orders by angle; dot by the dot product, largest first (the long vector can win under dot) |
| V7 | metric `l2` | `score`, `distance` | `score` is the distance, nearest (smallest) first |
| V8 | `vec_expand(seed)` | hits | the seed itself is included, first (identical vector) |
| V9 | `vec_insert` same `doc_id` again with a new vector, then `vec_build` | `vec_search`, `vec_info.count` | one entry, the new vector; count unchanged |
| V10 | `vec_create_index` again on an existing name | `vec_info.count`, `vec_search` | unknown from the docs ("reset the settings"); leaning: vectors kept |
| V11 | `vec_insert` a vector of the wrong width | the call; `vec_info.count` | unknown from the docs; leaning: refused, nothing stored |
| V12 | `vec_drop` then `vec_search` | the call | unknown; leaning: `[]` |

### Added after reading the source, before any observation (exposed: source-informed)

`Create` sets `numTrees` (default 4) at once, and `Insert` adds every vector to each existing tree (`InsertIntoTree`; a
tree with no nodes gets a root leaf), so search never takes the brute-force path while `numTrees > 0`. `Insert` adds
one to `meta.count` unconditionally and overwrites `cfg.dim` with the inserted vector's width; `Create` on an existing
name resets `count` to 0 and keeps the vectors and trees. The Python wrappers check nothing about width.

| Case | Source-based expectation (differs from the docs where marked) |
|---|---|
| V1, V2 | as the docs (all vectors sit in the root leaf, or in one leaf after the build) |
| V3 | **differs**: the vector inserted after the build is returned at once (it was added to the trees) |
| V9 | **differs**: `vec_info.count` goes up by one on a re-insert of the same id (search returns the id once, with the new vector) |
| V10 | **differs**: `vec_info.count` becomes 0 while search still returns the old vectors |
| V11 | **differs**: the wrong-width vector is accepted and `vec_info.dim` becomes its width; later searches with the original width: unknown (error or wrong distances) |
| V12 | `[]` (no trees after the drop: brute force over nothing) |

## Outcome ([observation](vecindex-observed-20261116T215013Z.json); binding receipts in `results/vec_index/`)

| Case | Docs prediction | Source-based | Observed |
|---|---|---|---|
| V1, V2 | held | held | a, b nearest first, scores 0.998752 / 0.998158 |
| V3 | **miss** | held | the post-build insert is first at once (score 1.0) → Low bug-srch-102 |
| V4, V5, V8 | held | held | |
| V6, V7 | held | held | cosine: near > long > far; dot: long (5) > near > far, distance -5; l2: score = distance |
| V9 | **miss** | held | count 5 → 6, the ID once with its new vector → F-0608 (VecIndex branch) |
| V10 | leaning missed | held | count 0, all 5 vectors still returned → Low bug-srch-101 (new) |
| V11 | leaning missed | held (width), refined | accepted; dim 3 → 2; ranked by shared parts (binding: `$vectorop` stops at the shorter vector, not zero-padding) |
| V12 | held | held | `[]`; `vec_info` then reports zeros |

No owner predicted any of these before this iteration: there was no VecIndex owner statement. `search.vecindex` now
states all twelve outcomes; `vec_index` distinguishes V3, V9, V10, V11, V12 and the score mapping.
