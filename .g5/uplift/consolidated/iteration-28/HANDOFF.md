# Iteration 28: algorithm options through both entry points (a negative result)

Before image: seal 27 `f1d4e561`. Product `3eaa79cf` unchanged. Native evidence only from `ivg-retest-20261116-iris`.

## W33

Selected by the step-5 inventory: `_validate.py` 39/41 unbound, ordinary validation, reached from two entry points
(engine methods and Cypher `CALL ivg.*`), outside every family of iterations 14-27. Predictions frozen from the owner
statement bodies and USER_GUIDE first; a source-based expectation added, marked, before observation
([algo-options-PAIRS.md](algo-options-PAIRS.md)).

- **All 36 frozen cases held**: both entry points take the same decision and, when they accept, return the same rows.
  The one source-based expectation (an unlisted Cypher key raising `KeyError`) missed: an earlier key check raises the
  documented `ValueError`. The allowed-key sets equal the field map (checked).
- No finding. Ontology gain: [algorithms.op](../../../ontology/features/algorithms.g5.md#algorithms.op) now states the
  option ranges and that both entry points apply them (no owner stated them before).
- Formal: [models/algo_options](../../../Verus_verification/models/algo_options/NOTES.md), 5 verified, 6 controls
  EXPECTED_FAIL; binding AGREES 82 comparisons over 41 cases, all six mutations detected.

## Recount

Active behavioral bindings 328 → **349** of 4,130 ([member-delta.json](member-delta.json)): 21 newly reached and bound
(8 input models, `validate_procedure_options`, 4 translator option checks, 8 algorithm methods as their option
decision sites); lost 0. The algorithm methods are bound for their option decision only, not their answers.

## Bearing on convergence

This is the first batch of the retest that changed no outcome prediction (the docs already promised it, and the code
implements one shared model). It is evidence of diminishing returns for *option validation*, not for the product:
iterations 25-27 each found defects in families nobody had examined.
