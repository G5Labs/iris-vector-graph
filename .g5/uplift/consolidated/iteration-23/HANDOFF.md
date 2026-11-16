# Iteration 23: IN lists and min/max at the API-writer / Cypher-reader boundary

Before image: seal 22 `ff05f394`. Product `3eaa79cf` unchanged. Native evidence from the run-isolated fixture only.

The product's openCypher TCK passes 3896/3896 ([docs/dev/TCK.md](../../../docs/dev/TCK.md)), but its scenarios write
values through Cypher. Every finding this session comes from values written by the Python API (or ObjectScript writers)
and read by Cypher. This iteration checked the remaining comparison families at that boundary
([PAIRS](remaining-operators-PAIRS.md)):

- `min`/`max` follow the sort key, as predicted from `query.values.sorting` (a consequence of the documented known
  issue).
- **`IN` lists** compare the stored text with each value's text. Miss against the owner-derived prediction: a node
  string `"1"` is `IN [1]` though `= 1` is false; a relationship whole float `1.0` is not `IN [1]` though `= 1` is true.
  Near spellings and words match nothing (the numeric-comparison risk was refuted). New Medium/Open
  [bug-cyp-106](../../../Verus_verification/bugs_issues.md#bug-cyp-106) and owner `query.values.in_lists`.

`typed_equality`: 43 verified (20 new + 23 imports), 9 controls, binding AGREES on 1,040 comparisons (the
relationship-`IN` port miss is kept as an attempt). `sort_key` re-verified at 52 after its import grew. Registers: 159
live bug entries, 55 simplifications, 146 questions. Reach **278 → 279 of 4,130**: translator `_boolean_expr_in`.

Gates: `check_consolidated.py` PASS; `check_ontology.py` 454 blocks, 0 issues; `check_findings.py` no problems;
[13 freshness cases](freshness-controls.json); [correspondence stamp](correspondence-inputs.json).

Not converged: each comparison family checked at this boundary has found an inconsistency with `=`/`RETURN` or
openCypher. Remaining: inline map patterns and parameters on nodes, and value functions.

Cost: about 17:29–17:38 UTC. Tokens and currency unavailable.
