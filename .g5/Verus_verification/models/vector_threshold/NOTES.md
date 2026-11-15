# Inclusive vector score thresholds before row limits

As-built scaled-integer predicate transcription at 3eaa79cf, **6 verified / 3 controls**.
Owner: search.knn.threshold. Results/raw logs: `../../results/vector_threshold/`.

`build` derives the optional predicate and duplicated query-vector/threshold bind
counts. `admits/eligible/search` filters score >= threshold before taking k, while
omission keeps all scores eligible. Scores are supplied by a ranked cosine
provider as exact scaled integers, not derived cosine or IEEE floating point.
`theorem_boundary_included` proves equality admitted/below excluded; omission and
limit neighbors are explicit. Three controls remove threshold, exclude equality,
or omit the second vector bind; named theorems fail.

**32 result comparisons** run actual generic/edge Python SQL builders and final
readers against a local SQLite table of three real vectors. SQLite evaluates the
WHERE/order/limit with a Python cosine function. The adapter changes TOP to LIMIT
and removes TO_VECTOR dtype/width syntax; bind values, predicate and result paths
are real. Omitted/0/0.5/1 thresholds x k1..4 x node/edge vary. The strict-comparison
product mutant drops an equality row and is detected, as is a changed result.
This is adapted-provider agreement, NOT IRIS preparation or native IRIS result
evidence. Route lookup is fixed to one table; no security or cross-graph probe.

Trust: bundled pinned vstd only, no unchecked declarations or actors. Valid finite
numeric conversion, faithful SQL bind/dialect semantics, cosine computation and
ranked provider inputs remain premises. Float NaN/infinity, ties, index routes,
width checks and all other KNN surfaces are outside this slice.
Implementation-verified 0; expected fixture calculations are unverified Python.
