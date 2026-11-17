# Iteration 40: SQL table mappings (W46)

Before image: seal 39 `4d80f119`. Product `3eaa79cf` unchanged. Native evidence only from `ivg-cont-20261117-iris`
(fixture-only SQL tables in schemas `W46x…`, `W46y…`, `W46b…` and `SQLUser`).

## Why this workflow

From the unbound public methods: the SQL table mappings had precise owner statements on the FHIR page but had never run
natively (q-plt-018: "FHIR suites skipped") and had no binding; they need no external provider.

## Result

Predictions frozen first ([PAIRS](sqlmap-PAIRS.md)): 7 of 8 confident predictions held; T4 missed. New, all Low:
bug-cyp-108 (`target_fk` read on the target table, documented on the source table), bug-cyp-109 (an IVG relationship
from a mapped node is an SQL error), bug-cyp-110 (an unqualified table is refused). New question
`fhir.sql_mapping.cache` (running engines keep a stale mapping cache). Owner `fhir.sql_mapping.relationships` corrected,
and `fhir.sql_mapping` extended. New model [`sql_mapping`](../../../Verus_verification/models/sql_mapping/NOTES.md):
5 verified, 5 controls EXPECTED_FAIL, native binding AGREES (11 cases, two engines).

## Recount ([member-delta.json](member-delta.json))

Active bindings 412 → **423**: 11 newly reached and bound (8 `fhir.py`, `_invalidate_mapping_cache`,
`_trp_mapped_relation`, `list_table_mappings`), 0 strengthened, lost 0. Correspondence: [delta from
39](correspondence-delta-from-39.json), fresh [stamp](correspondence-inputs.json).
