# IVF index entries

Product `3eaa79cf`, unchanged. Iteration 46 (continuation). Predictions frozen from the API reference and owners:
[ivf-PAIRS.md](../../../uplift/consolidated/iteration-46/ivf-PAIRS.md). Owner (new):
[search.ivf](../../../ontology/features/search.g5.md#search.ivf).

## What the model decides

One node's entries in a two-cell index (`in0`, `in1`) and the reported size (`indexed`) under `insert` (into the cell
`ivf_insert` reports) and `delete` (the first cell's copy only); `search_answers` (no width check).

## Theorems (4 verified; no imports)

`theorem_insert_then_delete` (agrees), `theorem_same_cell_reinsert_counts_twice` and
`theorem_cross_cell_reinsert_leaves_stale_entry` ([bug-srch-107](../../bugs_issues.md#bug-srch-107)),
`theorem_other_width_answered` ([bug-srch-108](../../bugs_issues.md#bug-srch-108)).

## Controls

Four, all EXPECTED_FAIL: `insert-replaces`, `delete-all`, `width-checked`, `delete-noop`.

## Binding

[binding.py](binding.py): four cases through the actual IVF calls, the cells taken from `ivf_insert`'s answers:
**AGREES**; each mutation detected.

## Limits

Build, rebuild and drop (W52 V1, V9, V10) are observed and stated in the owner; the clustering itself (k-means) is a
provider and not modeled; `nprobe` below `nlist` is not exercised.
