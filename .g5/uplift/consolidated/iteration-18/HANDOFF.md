# Iteration 18: ORDER BY's sort key, and an executor disagreement

Before image: seal 17 `3181d497`. Product `3eaa79cf` unchanged. Native evidence from the run-isolated fixture only.

## Workflows sampled

1. **W19, ORDER BY over mixed values, node vs relationship** ([PAIRS](order-by-PAIRS.md)). Node strings that spell
   numbers sort among numbers although `RETURN` reads strings and `WHERE` ordering drops them: a prediction miss
   against openCypher, but a documented known issue, so no register entry. The sort key lives in the ObjectScript
   subsystem (`Graph.KG.Cypher.SortKey`), the largest unbound area.
2. **W19b, empty string under the two executors.** Discovered through the binding: `SortKey.Key("")` returns the null
   rank when called as ObjectScript, but the SQL path passes `$Char(0)`, a string. Frozen prediction, then one query
   answered by both executors: SQL `'', 'a', 'b', 1, 2, null`; native `'a', 'b', 1, 2, '', null`; the public
   `execute_cypher` used native. This breaks `query.native.equal-answers`.

## Owners, claims, finding

- New statement [query.values.sorting](../../../ontology/features/cypher.g5.md#query.values.sorting), citing the
  known issue for numeric strings and stating the executor difference.
- New Medium/Open [bug-cyp-104](../../../Verus_verification/bugs_issues.md#bug-cyp-104), e2e reproduced; linked from
  `query.native.equal-answers`. Registers: 157 live bug entries, 55 simplifications, 146 questions.
- New model [sort_key](../../../Verus_verification/models/sort_key/NOTES.md): 50 verified = 9 new + 41 imports. It
  transcribes the key's rank for scalar text and proves the node `WHERE`/`ORDER BY` disagreement against the imported
  `typed_equality` rule, and the executor disagreement under the observed transport premise. Five controls, all
  EXPECTED_FAIL in full and isolated runs.
- Binding: 30 SQL-function cells plus 29 direct class-method calls, AGREES. An earlier SQL-only receipt and the
  transport-miss attempt are kept.

## Source binding delta

**266 → 269 of 4,130** ([delta](member-delta.json)): `Graph.KG.Cypher.SortKey.cls::Key` (class method executed
directly), `Graph.KG.Cypher.Exec.cls::SortKey`, translator `_sort_key`. Lost: none. Direct executable-body
verification: 0.

## Gates

`check_consolidated.py` PASS; `check_ontology.py` 450 blocks, 0 issues, 2 inherited warnings; `check_findings.py` no
problems; [13 freshness cases](freshness-controls.json); [correspondence stamp](correspondence-inputs.json).

## Cost

About 17:03–17:15 UTC. Native probes and bindings a few seconds each; Verus seconds per run, controls ~1 min.
Tokens and currency unavailable.

## Next

Not converged: this iteration found an equal-answers violation between executors. Before any convergence claim, the
strongest remaining candidates are other native-executor shapes against the SQL path, and a different underserved
workflow outside the Cypher value family (for example ObjectScript lifecycle classes or store-protocol readers with
real consumers).
