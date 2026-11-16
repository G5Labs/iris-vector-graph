# Iteration 27: the VecIndex lifecycle, and a correction to how owner predictions were read

Before image: seal 26 `39bed451`. Product `3eaa79cf` unchanged. Native evidence only from `ivg-retest-20261116-iris`.

## Correction to iterations 25 and 26

Their "owner prediction" columns were read from the blocks' metadata entries, not the statement bodies. The bodies of
`install.bulk_load.rebuild`, `structure.write` and `temporal.write` already predicted A1, T5, T8 and T10. The PAIRS
files now carry the correction; iteration 25's claimed "owner gap" for A1 is withdrawn. Still not predicted by any owner
before those iterations: the interrupted re-load (B1, only a metadata "Suspected" note), the autocommit-off split
(bug-tmp-102) and the autocommit-off temporal setting. Those are now in the statements, and the behavioral prose the two
iterations had put into metadata was moved into statements or removed as duplicate (metadata stays lightweight).

## W32: VecIndex

Selected in step 1 and step 5: `VecIndex.cls` 32/32 unbound, no owner statement for search results, outside every
family investigated since iteration 14. Docs-based predictions frozen first; source-based expectations added, marked,
before observation ([vecindex-PAIRS.md](vecindex-PAIRS.md)). Docs missed V3, V9, V10 (leaning), V11 (leaning); the
source-based expectations held, refined by the binding (`$vectorop` stops at the shorter vector).

- New owner [search.vecindex](../../../ontology/features/search.g5.md#search.vecindex) (345 blocks).
- **F-0608** restored live (Medium): its VecIndex branch, never run by the playbook audit, is now E2E reproduced (count
  inflation on re-insert; another width accepted and recorded). Repair of a known finding.
- **bug-srch-101** (Low, new discovery): re-create reports count 0 while the vectors stay searchable.
- **bug-srch-102** (Low, new): the API reference says inserts need a rebuild to be searchable; they are found at once.
- Formal: [models/vec_index](../../../Verus_verification/models/vec_index/NOTES.md), 8 verified, 6 controls EXPECTED_FAIL;
  binding AGREES 215 comparisons over 160 operations and five metrics (first run DISAGREES on l2 after the 2-wide
  insert; premise corrected; kept).

## Recount

Active behavioral bindings 305 → **328** of 4,130 ([member-delta.json](member-delta.json)): 23 newly reached and bound
(16 `VecIndex.cls` members, 7 `VectorMixin.vec_*` entries); no existing member gained a claim; lost 0.

## Next

Step 5: return to the product-wide inventory, pick the strongest remaining candidate and one tractable workflow outside
the families examined in iterations 25-27 (bulk load, caller transactions, VecIndex).
