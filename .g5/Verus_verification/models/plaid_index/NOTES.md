# PLAID: build width check, re-inserts and inserts of another width

Product `3eaa79cf`, unchanged. Iteration 30 (retest). Predictions frozen before observation in
[plaid-PAIRS.md](../../../uplift/consolidated/iteration-30/plaid-PAIRS.md). Owner (new):
[search.plaid](../../../ontology/features/search.g5.md#search.plaid). Finding: F-0608 (PLAID branch).

## What the model decides

An index maps each document to its stored token vectors, with the reported document count, token total and width.
`build` refuses a document list with a token of another width (the Python check, R089). `insert` transcribes
`PLAIDSearch.Insert`: overwrite the document's tokens and add one document and its token count to the totals, with no
width check. A candidate's score is MaxSim over its stored tokens (an uninterpreted provider here; the binding computes
it, with element-wise products stopping at the shorter vector).

## Theorems (5, all new; no imports)

`theorem_build_refuses_other_width` (P1), `theorem_reinsert_inflates_counts` (P3, F-0608), `theorem_reinsert_scored_on_new_tokens`
(P3: the difference from IVF), `theorem_insert_accepts_other_width` (P4, F-0608), `theorem_new_doc_counted_once` (P2,
the passing neighbor). No `assume`, `admit` or `external_body`.

## Controls

Four, all EXPECTED_FAIL full and isolated: `build-skips-width-check`, `count-only-new-docs` and `insert-refuses-other-width`
(the repairs), `keep-old-tokens` (IVF's behavior).

## Binding

[binding.py](binding.py): a mixed-width build (refused, nothing written) and a seeded sequence (seed 20261116) of 24
inserts and searches over six documents, `nprobe` equal to the centroid count: **AGREES, 25 operations**; info counts
and every hit's score match the port; all four mutations detected.

## Limits

Transcription with native agreement. Not checked: candidate selection by centroid (`nprobe` below the centroid count),
client-side k-means, `plaid_drop` beyond cleanup, concurrent writers.
