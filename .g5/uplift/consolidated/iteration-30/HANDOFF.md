# Iteration 30: F-0608's PLAID branch

Before image: seal 29 `6a4ca6e4`. Product `3eaa79cf` unchanged. Native evidence only from `ivg-retest-20261116-iris`.

## W35

The strongest remaining candidate at the step-5 check: F-0608's PLAID branch, never run. Predictions frozen from the
API reference, the R089 build check and F-0608's claim, then source-based expectations added, marked, before
observation ([plaid-PAIRS.md](plaid-PAIRS.md)).

- Held: the build refuses another width (P1); a new document is counted and ranks first (P2); unknown names answer
  `[]`/`{}` (P5); an insert of another width is accepted (P4) — and, scored on shared components, outranks correct
  matches.
- **Partly missed**: F-0608's IVF-derived expectation that a re-inserted document's old vectors still answer. PLAID
  overwrites the tokens; only the counts are inflated (indexed 5 → 6, totalTokens 8 → 9). The source-based expectation
  held.
- F-0608 updated with the PLAID reproduction and its difference from IVF (repair of a known finding). New owner
  [search.plaid](../../../ontology/features/search.g5.md#search.plaid) (347 blocks).
- Formal: [models/plaid_index](../../../Verus_verification/models/plaid_index/NOTES.md), 5 verified, 4 controls
  EXPECTED_FAIL; binding AGREES over 25 operations, all mutations detected.

## Recount

See [member-delta.json](member-delta.json): 7 PLAID members newly bound (`Insert`, `Info`, `Search`, and four
`VectorMixin.plaid_*` entries); lost 0.
