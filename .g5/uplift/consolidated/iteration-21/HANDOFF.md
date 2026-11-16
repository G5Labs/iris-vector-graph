# Iteration 21: variable-length multiplicity and adjacency rebuild

Before image: seal 20 `1dcbf766`. Product `3eaa79cf` unchanged. Native evidence from the run-isolated fixture only.

Two different underserved ObjectScript-backed workflows, tested against frozen predictions ([PAIRS](varlength-PAIRS.md)):

| Workflow | Prediction | Outcome |
|---|---|---|
| W24: variable-length paths over a diamond, SQL path and default engine | one row per path (openCypher) | held on both engines; recorded as `query.paths.varlength` (as-built agreement, no formal claim) |
| W25: `rebuild_kg()` with default, named-graph and temporal-marked rows and a planted entry with no row | rows kept, planted entry removed | held; evidence linked from `structure.rebuild` |

No new finding, model or source link; reach stays **273 of 4,130**. Gates: `check_consolidated.py` PASS,
`check_ontology.py` 453 blocks / 0 issues, `check_findings.py` no problems, [correspondence stamp](correspondence-inputs.json).

Not converged: BM25 text search has detailed owners (`search.bm25.*`) but no model and no source binding, and its
ranking and count rules are consequential and testable on the fixture. Iteration 22 takes it.

Cost: about 17:21–17:26 UTC. Tokens and currency unavailable.
