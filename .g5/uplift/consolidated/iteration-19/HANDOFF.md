# Iteration 19: the strongest remaining candidate and a different underserved workflow

Before image: seal 18 `42620fb4`. Product `3eaa79cf` unchanged. Native evidence from the run-isolated fixture only;
setup ran in a fresh namespace `W21` created inside it.

## Why these workflows

Before any convergence claim the iteration guide asks to test the strongest remaining candidate and a different
underserved workflow. After iteration 18's executor disagreement, the strongest candidate was other native-executor
shapes against the SQL path. The different workflow is schema setup lifecycle (`_engine/schema.py`, 7 of 83 members
bound), outside the Cypher value family.

## Outcomes

| Workflow | Prediction | Outcome |
|---|---|---|
| W20: 16 ordinary anchored read shapes, native vs SQL ([PAIRS](native-shapes-PAIRS.md)) | equal answers | held: 4 shapes plan natively and all agree over string, integer, float, boolean, list and missing values; 12 take the SQL path |
| W20b: empty string in `count`, `DISTINCT`, plain projection | equal (risk: native treats `""` as null) | held: equal answers; `count(b.p)` is SQL-only. bug-cyp-104 stays specific to the sort key (bounded refutation of the wider risk) |
| W21: setup dry run / real run / repeat on a fresh namespace ([PAIRS](setup-lifecycle-PAIRS.md)) | per `install.setup`, `.dry_run` | held at every step: dry runs write nothing; real run records `new`; repeats are `existing` and change nothing |
| W21: record removed (interrupted setup), mismatching engine | `inferred` then restored; refusal with nothing written | held |

No new finding: both tests found the foundation's owners and the product in agreement.

## Owners, claims, links

- `install.setup`, `.dry_run` and `.resume` gain Verus metadata. No statement text changed.
- New model [setup_record](../../../Verus_verification/models/setup_record/NOTES.md): 7 verified, 4 controls, all
  EXPECTED_FAIL; binding against both recorded native runs AGREES (28 comparisons; three of four mutations detected,
  the explicit-name case is formal only).
- Reach **269 → 272 of 4,130** ([delta](member-delta.json)): `SchemaMixin.initialize_schema`,
  `SchemaMixin._record_and_initialize`, `schema_name.write_record`. Lost: none.

## Gates

`check_consolidated.py` PASS; `check_ontology.py` 450 blocks, 0 issues; `check_findings.py` no problems;
[12 freshness cases](freshness-controls.json); [correspondence stamp](correspondence-inputs.json).

## Convergence assessment (not claimed)

[Unlinked distribution](unlinked-distribution.json) by area: Cypher translator/parser 969 unbound of 996; ObjectScript
906 of 972; other package modules 900 of 955; engine mixins 613 of 711; stores 177 of 184; migrations 161 of 161;
ledger 132 of 151. Direct executable-body verification remains 0.

This iteration's two tests found no new discrepancy. But iterations 15–18 each found a material, previously
unrecorded behavior, all in reader semantics: the temporal mark, boolean equality on stored integers, cast-to-0
ordering on relationships, and the executor sort disagreement. Neighboring Cypher value semantics remain unexamined
(string functions, `null` in `<>`/`IN`, arithmetic and list operators beyond the documented known issue, `CASE`,
`coalesce`), and so does the entire migrations area. Further modeling there would plausibly change material
predictions, as each recent iteration did. Convergence is therefore not supported. The largest unknown, the Cypher
translator's remaining value semantics, costs about one iteration (15–30 minutes of builder time plus fixture probes)
per operator family to settle.

## Cost

About 17:10–17:25 UTC. Native probes seconds each; setup runs about 20 s on the fresh namespace; Verus seconds per run.
Tokens and currency unavailable.
