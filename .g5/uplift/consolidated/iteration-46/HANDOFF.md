# Iteration 46: the IVF index after its build (W52)

Before image: seal 45 `1410734b`. Product `3eaa79cf` unchanged. Native evidence only from `ivg-cont-20261117-iris`.

## Result

Predictions frozen first ([PAIRS](ivf-PAIRS.md)): 8 of 10 held. New: bug-srch-107 (Medium, a re-insert keeps the old
vector in another cell, a delete removes one copy, and every insert counts), bug-srch-108 (Low, a query of another width
is answered). New owner `search.ivf`; new model [`ivf_entries`](../../../Verus_verification/models/ivf_entries/NOTES.md):
4 verified, 4 controls EXPECTED_FAIL, native binding AGREES.

## Recount ([member-delta.json](member-delta.json))

Active bindings 441 → **448**: 7 newly reached and bound; `ivf_drop` is a locator. Lost 0. Correspondence: [delta from
45](correspondence-delta-from-45.json), fresh [stamp](correspondence-inputs.json).
