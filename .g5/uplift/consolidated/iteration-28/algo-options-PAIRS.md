# W33: algorithm options through the Python method and the Cypher procedure — predictions frozen before observation

Frozen 2026-11-16, iteration 28. Before image: seal 27 `f1d4e561`. Product `3eaa79cf`. Fixture `ivg-retest-20261116-iris`.

Why this workflow: step-5 inventory. `_validate.py` has 39 of 41 members without an active binding; its input models
and `validate_procedure_options` are the ordinary validation in front of the centrality and community algorithms, reached
from two entry points (the engine methods and Cypher `CALL ivg.*`). Outside the bulk-load, caller-transaction and VecIndex
families of iterations 25-27, and outside the comparison-operator family of 16-24.

Sources: owner statement bodies `algorithms.op`, `.closeness`, `.eigenvector`, `.betweenness`, `.leiden`; USER_GUIDE
"Cypher procedures" (lines 783-802): "The centrality and community procedures take each option as the engine method of
the same name does (... the same values, the same range), and a value the method refuses raises `ValueError` naming the
procedure and the option"; "an option not listed raises `ValueError` naming the ones allowed". `_validate.py`, the
algorithm methods and the procedure dispatch were **not** read. Verus determines none of these.

Graph: a small default-graph triangle plus a tail, written through the engine.

| Case | Value | Python method | Cypher `CALL ivg.*` | Prediction |
|---|---|---|---|---|
| O1 | closeness `formula: 'bogus'` | refuses | refuses, naming procedure and option | both refuse (owner + docs) |
| O2 | eigenvector `maxIter` 0, 1001; neighbor 1000 | 0 and 1001 refused, 1000 answers | same | both agree (owner: 1 to 1000) |
| O3 | `direction: 'sideways'` (degree, betweenness, closeness) | refuses before reading | same | both refuse (owner) |
| O4 | an option not listed, `{foo: 1}` | (keyword) `TypeError` | `ValueError` naming the allowed options | refuse on both (docs) |
| O5 | `topK` 0 and -1 | unknown | unknown | **both the same** (docs) |
| O6 | betweenness `sampleSize` -1 | unknown | unknown | both the same |
| O7 | betweenness `maxHops` 0 and -1 | unknown | unknown | both the same |
| O8 | leiden `gamma` 0 and -1 | unknown | unknown | both the same |
| O9 | `topK: "2"` (a string) | unknown | unknown | both the same |
| O10 | neighbor: valid options (`topK: 2`) | 2 rows | 2 rows, same IDs and scores | agree |

### Added after reading the source, before any observation (exposed: source-informed)

Both entry points build the same pydantic model (`_validate.py` :243-288; the engine methods in `_engine/algorithms.py`;
Cypher through `_PROCEDURE_OPTION_FIELDS` and `validate_procedure_options`, translator.py :140-180). So O5-O9 should
agree, decided by the model's ranges (`top_k` 0 to 1,000,000; `max_hops` 0 to 1000; `sample_size` ≥ 0; `gamma` in
(0, 100]; `max_iter` 1 to 1000) and pydantic's lax coercion (a string "2" and 2.0 accepted as 2; 2.5 refused).
Expected difference: **O4** — `validate_procedure_options` indexes `names[option]` before pydantic runs and catches only
`ValidationError`, so an unlisted Cypher option may raise `KeyError`, not the documented `ValueError` naming the allowed
options. Cypher's `direction` is checked by `_procedure_direction` first (same three values, case-sensitive), so O3 agrees.

## Outcome ([observation](algo-options-observed-20261116T215903Z.json); binding in `results/algo_options/`)

Every case agreed with the frozen docs/owner prediction: 36 of 36 cells take the same decision on both entry points,
and accepted calls return the same row count. O4: Cypher raises `ValueError` naming the allowed keys
(`_validate_centrality_proc_map`/`_validate_community_proc_map` run first); the **source-based** expectation of a
`KeyError` missed, the docs-based prediction held. O5: `topK` 0 keeps every row (184), -1 refused on both. O9: `"2"`,
`2.0` and `true` (as 1) accepted on both; `2.5` refused. No discrepancy, no finding. Material prediction gained: the
option ranges are now stated in `algorithms.op` (no owner stated them), and `algo_options` binds the shared decision.
