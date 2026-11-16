# Iteration 17: equality on the native path, and ordering comparisons

Before image: seal 16 `1f949ffe`. Product `3eaa79cf` unchanged. Native evidence from the run-isolated fixture only.

## Workflows sampled

1. **W17, the W16 equality cells on the native executor** (a different executor for the same reader;
   [PAIRS](native-equality-PAIRS.md)). Owner prediction: equal answers. Outcome: the native planner declines every
   non-string equality value by design (`native_plan._value`), so none of 352 cells routes natively and equal answers
   hold by declining. Recorded in `query.values.equality`; no formal or reach credit.
2. **W18, ordering comparisons, node vs relationship** (the next neighbor of W16; [PAIRS](ordering-PAIRS.md)).
   Material discovery: any non-numeric relationship text orders as 0 against a number (and `"12abc"` as 12), while
   `RETURN` reads the text and the node property is dropped. The product removed this cast-to-0 reading on every other
   comparison path (R307, R308, 4.7.0 row 24).
3. Set aside with reasons (in [native-equality-PAIRS.md](native-equality-PAIRS.md)): the store's
   `query_nodes(property_filters=...)` (no product caller), graph-name C1 control characters (not ordinary data), and
   Cypher `MERGE` (adjacent to the quarantined iteration-13 investigation; not pursued).

## Owners, claims, finding

- New statement [query.values.ordering](../../../ontology/features/cypher.g5.md#query.values.ordering);
  `query.values.equality` gains the native-routing fact.
- New Medium/Open [bug-cyp-103](../../../Verus_verification/bugs_issues.md#bug-cyp-103), e2e reproduced with node and
  numeric neighbors. Registers: 156 live bug entries, 55 simplifications, 146 questions.
- [typed_equality](../../../Verus_verification/models/typed_equality/NOTES.md) grows to 41 verified (18 new + 23
  imports) with four ordering theorems and two controls (7 total, all EXPECTED_FAIL full and isolated). The IRIS
  text-to-double cast is an uninterpreted provider; the relationship theorem is conditional on its value, which the
  binding observes.
- Binding: 52 worlds, 676 comparisons, AGREES on the first ordering run; seven port mutations detected (2–17 worlds).

## Source binding delta

**264 → 266 of 4,130** ([delta](member-delta.json)): `_translate_boolean_expression` (role limited to the
ordering-with-number branch) and `_stored_number_value`. Lost: none. Direct executable-body verification: 0.

## Gates

`check_consolidated.py` PASS; `check_ontology.py` 449 blocks, 0 issues, 2 inherited warnings; `check_findings.py` no
problems; [13 freshness cases](freshness-controls.json); [correspondence stamp](correspondence-inputs.json).

## Cost

About 16:55–17:10 UTC. Native probes and binding under 10 s each; Verus a few seconds per run, controls ~1.5 min.
Tokens and currency unavailable.

## Next

Not converged: each of the last three iterations found a material, previously unrecorded behavior. Remaining
directions: Cypher string comparison and `ORDER BY` across mixed types (same translator family); the ObjectScript
subsystem (877 unlinked members); store-protocol readers with real consumers.
