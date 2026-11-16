# Iteration 24: inline patterns, parameters and value functions

Before image: seal 23 `54d2bf1f`. Product `3eaa79cf` unchanged. Native evidence from the run-isolated fixture only.
Predictions frozen before each observation ([PAIRS](patterns-params-PAIRS.md)).

| Workflow | Outcome |
|---|---|
| W28: inline `{p: 1}`, `= $v`, `IN $list`, `{p: true}`, node vs relationship | every cell predicted correctly from the owners written this session; bug-cyp-106 also covers `IN $list` |
| W29: `toString`, `toInteger`, `+`, `coalesce` | documented string-arithmetic behavior held; **miss**: relationship `coalesce` returns stored text (`'1'` for true), predictable from the `relationship_text` owner's "only marked columns are decoded" clause but not predicted. New Low/Open [bug-cyp-107](../../../Verus_verification/bugs_issues.md#bug-cyp-107). Boolean arithmetic recorded in the owner as a variant of the documented behavior |

No new model or source link; reach stays **279 of 4,130**. Registers: 160 live bug entries, 55 simplifications, 146
questions. Gates: `check_consolidated.py` PASS; `check_ontology.py` 454 blocks, 0 issues; `check_findings.py` no
problems; [correspondence stamp](correspondence-inputs.json).

Cost: about 17:33–17:42 UTC. Tokens and currency unavailable.
