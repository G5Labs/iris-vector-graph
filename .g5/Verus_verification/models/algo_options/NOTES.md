# Algorithm options through the engine method and Cypher CALL ivg.*

Product `3eaa79cf`, unchanged. Iteration 28 (retest). Predictions frozen before observation in
[algo-options-PAIRS.md](../../../uplift/consolidated/iteration-28/algo-options-PAIRS.md). Owner:
[algorithms.op](../../../ontology/features/algorithms.g5.md#algorithms.op).

## What the model decides

For the eight centrality and community procedures, `listed` is the option set each procedure takes (the allowed-key
sets, which equal the field map `_PROCEDURE_OPTION_FIELDS` — checked natively in this iteration — and the methods'
keyword arguments). `model_ok` is the input model's decision: integer ranges (`topK` 0..1,000,000, `maxHops` 0..1000,
`sampleSize` 0..1,000,000, `maxIter` 1..1000, `maxLevels` 1..100, `memBudgetMB` 16..8192, `randomSeed` 0..2^32-1),
exact literals for `direction` and `formula`. The engine method refuses an unknown keyword (`TypeError`) and otherwise
asks the model; Cypher refuses an unlisted key (`ValueError` naming the allowed ones), checks `direction` first, then
asks the same model. Pydantic's coercion of a value to an integer is an uninterpreted provider shared by both paths.

## Theorems (5, all new; no imports)

`theorem_same_decision` (the documented promise: same values, same range), `theorem_unlisted_refused`,
`theorem_ranges`, `theorem_uncoercible_refused`, `theorem_enumerations_exact`. No `assume`, `admit` or `external_body`.
`theorem_unlisted_refused` holds twice over (the key check and the model, which has no such field), so no single
mutation isolates it; it has no control of its own.

## Controls

Six, all EXPECTED_FAIL full and isolated: `cypher-skips-model` (the pre-4.6.5 Cypher reading), `keyword-differs`,
`topk-from-one`, `maxiter-unbounded`, `uncoercible-accepted`, `formula-any-case`.

## Binding

[binding.py](binding.py) runs the frozen W33 matrix (36 cases from `iteration-28/algo_options_probe.py`) plus 5 more
(including float `gamma`/`tol` and a non-numeric string) through both entry points on the fixture: **AGREES, 41 cases,
82 comparisons**, accepted calls return the same row counts on both, all six mutations detected.

## Limits

Transcription with native agreement. Float options are checked natively only. Not covered: the `gds.*` shims (whose
`gds.betweenness.stream` also validates through `BetweennessInput`), `ivg.ppr`/PageRank argument checks, the
algorithms' answers themselves, and positional-argument refusal.
