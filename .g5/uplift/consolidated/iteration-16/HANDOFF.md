# Iteration 16: typed equality in Cypher WHERE, node vs relationship

Before image: seal 15 `1cb3bb2f`. Product `3eaa79cf` unchanged. Native evidence from the run-isolated fixture
`ivg-cloud-20261116-iris` only (runtime in [iteration 15](../iteration-15/runtime.py)).

## Why this workflow

The Cypher translator is the largest underserved subsystem (4 of 717 members bound before this iteration). `WHERE`
equality changes which rows a read, `SET` or `DELETE` touches, and no owner stated it: `query.values` covers only what
`RETURN` reads back. This is a discovery from this session's survey, not a previously known repair. The product
documents part of the behavior as a known issue; the registers and ontology did not.

## Predictions and outcomes

Frozen before native observation ([PAIRS](typed-equality-PAIRS.md)). Held: node string "0.95" ≠ 0.95; node boolean ≠ 1;
relationship integer 1 and string "1" equal `true` (source prediction); relationship string "0.95" = 0.95. Resolved: a
relationship JSON `true` equals 1. **Misses:** a node's stored integer 1 and string "1" equal `true` (I predicted no
for both), the relationship float-twin spelling (`"1.0"` equals 1), and the provider spelling of whole JSON floats.
All misses are kept with their receipts.

## Owners, formal claims and finding

- New statement [query.values.equality](../../../ontology/features/cypher.g5.md#query.values.equality): the boolean
  legacy spellings, the node stored-number rule, the relationship spelling rule with the float twin, and the
  node/relationship asymmetry. No existing statement changed except metadata links. No question block: openCypher
  and the product's own 4.8.0 plan settle the intended outcome.
- New Medium/Open [bug-cyp-102](../../../Verus_verification/bugs_issues.md#bug-cyp-102), e2e reproduced: a boolean
  equality also matches stored integers 1 and 0, beyond the strings the documented known issue names. Registers: 155
  live bug entries, 55 simplifications, 146 questions.
- New model [typed_equality](../../../Verus_verification/models/typed_equality/NOTES.md): 37 verified = 14 new + 23
  unchanged imports (`node_read`, `rel_prop_text`). It characterizes exactly which non-double node values equal
  `true`, proves WHERE/RETURN disagreement against the accepted read models, and the relationship rules. Five controls,
  all EXPECTED_FAIL in full and isolated runs; two first runs were FAIL_ELSEWHERE through a trusted lemma contract and
  the theorem was made self-contained.
- Native binding: 44 worlds, 352 comparisons, AGREES; five port mutations detected by 2–6 worlds each. Attempts 1
  (model miss) and 2 (provider miss) are kept.
- [Route trace](route-trace.json): translating the probe queries executes exactly the bound translator members.

## Source binding delta

`member_reach.py`: **257 → 264 of 4,130** ([delta](member-delta.json)). New: `_stored_bool_in`,
`_stored_bool_comparison`, `_node_number_eq_sql`, `_number_eq_sql`, `_number_texts`, `_stored_number_test`
(translator) and `prop_values.bool_spellings_sql`. Strengthened: none. Lost: none. Tier: transcription with native
agreement plus a translation route trace; SQL comparison, `JSON_VALUE` spelling and stored-double text are
providers. Direct executable-body verification: 0.

## Gates

`check_consolidated.py` PASS; `check_ontology.py` 448 blocks, 0 issues, 2 inherited warnings; `check_findings.py`
(pre-edit snapshot in `previous-findings/`) no problems; [13 freshness cases](freshness-controls.json) pass;
[correspondence stamp](correspondence-inputs.json).

## Builder diagnostic for this workflow

| Decision | Owner states both cases | Verus distinguishes at the reader |
|---|---|---|
| Node integer 1 vs node boolean true against `= true` / `= 1` | yes (new) | yes, against node_read's RETURN |
| Node string "1" vs integer 1 against `= 1` and `= true` | yes | yes |
| Relationship JSON true vs node boolean against `= 1` | yes | yes |
| Same user string "12" / "12.0" on node vs relationship against `= 12` | yes | yes, against rel_prop_text's RETURN |
| Stored doubles against booleans and integers | yes (stated as observed) | provider only |

Not covered: parameters, `IN` lists, `{p: true}` patterns, `MERGE`, the native executor, Cypher-written values,
ordering comparisons (`<`, `>`), and string equality.

## Cost

About 16:44–17:00 UTC. Native: probe ~3 s, three binding runs ~2 s each. Verus: ~10 proof iterations of a few seconds,
two control rounds ~1 min each. Tokens and currency unavailable.

## Next

Not converged. Candidates: equality through parameters and `{p: true}` patterns on the native executor
(`query.native.equal-answers` requires the same rows), and the ObjectScript subsystem (877 unlinked members).
