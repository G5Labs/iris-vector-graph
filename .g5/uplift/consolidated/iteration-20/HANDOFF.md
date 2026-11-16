# Iteration 20: null handling and string predicates

Before image: seal 19 `be91d90c`. Product `3eaa79cf` unchanged. Native evidence from the run-isolated fixture only.

## Workflows sampled ([PAIRS](null-semantics-PAIRS.md))

| Workflow | Prediction | Outcome |
|---|---|---|
| W22: missing and null properties in `=`, `<>`, `NOT`, `IN`, `IS NULL`, node vs three relationship null states | openCypher null semantics | held on every cell; recorded as `query.values.nulls` (as-built agreement, no formal claim) |
| W23: `STARTS WITH` / `CONTAINS` / `ENDS WITH` on numbers vs strings | relationship numbers match by text (known-issue variant); node numbers unknown | **node stored numbers also match by their canonical digits**, contradicting the node path's typed equality and ordering and absent from the known issue: Low bug-cyp-105 |
| Migrations (161 members, none bound) | — | set aside: needs a reconstructed 3.2.0 install (about one iteration); affects only installs two major lines back |

## Claims and links

- New statements `query.values.nulls` and `query.values.string_predicates`.
- New Low/Open [bug-cyp-105](../../../Verus_verification/bugs_issues.md#bug-cyp-105), e2e reproduced. Registers: 158
  live bug entries, 55 simplifications, 146 questions.
- `typed_equality` grows to 42 verified (19 new + 23 imports) and 8 controls. Its binding now has 52 worlds and 884
  comparisons, AGREES, with all eight rule mutations detected.
- `sort_key` imports `typed_equality`, so the evidence gate marked its proof, controls and binding stale. All were
  re-run: 51 verified (9 new + 42 imports), 5 EXPECTED_FAIL, binding AGREES. The intermediate count-mismatch receipt
  is kept.
- Reach **272 → 273 of 4,130** ([delta](member-delta.json)): translator `_boolean_expr_comparison_ops` (role limited to
  string predicates).

## Gates

`check_consolidated.py` PASS; `check_ontology.py` 452 blocks, 0 issues; `check_findings.py` no problems;
[13 freshness cases](freshness-controls.json); [correspondence stamp](correspondence-inputs.json).

## Cost

About 17:15–17:22 UTC. Tokens and currency unavailable.
