# Verify: scope, entries and adoption

Product: `3eaa79cf77d3e0a879b2cced634cf2729d81499e`. Owners: `ledger.verify`, `ledger.verify.scope`, `ledger.unrecorded`.
Added in iteration 60: the test obligations of `test_ledger_us09_verify.py`, `test_ledger_us05_compat.py`,
`test_ledger_us11_temporal_coexist.py` and `test_ledger_verify_pre_enable_writes.py` (map I3, I4, I35, I40, I62-I66) had
no formal claim; the owner blocks had no model link. As-built transcription, **8 verified / 8 controls** (receipts
`results/ledger_verify/20261117T200656Z-prove`, `20261117T2006*/2007*-control-*`).

## Claims and controls

| Claim | Theorem | Control (must fail) |
|---|---|---|
| Verify is equal exactly when the replayed and canonical views agree | `theorem_equal_iff_views_agree` | (follows from `emitted`) |
| Adopting the reported entries makes the replayed view equal the tables, so the next verify is equal | `theorem_adoption_closes_the_difference` | `adopt-without-cascade`, `new-entity-attributes-dropped` |
| An unrecorded node gives existence + label + property entries; an unrecorded deletion gives the deletion alone | `theorem_entries_for_created_and_deleted_nodes` | `new-entity-attributes-dropped` |
| No adoption revision when equal; never without `adopt=True` | `theorem_adoption_only_when_needed` | `adopt-when-equal` |
| Nodes matched by ID across graphs | `theorem_node_identity_ignores_graph` | `graph-scoped-node-identity` |
| Reserved properties left out | `theorem_reserved_properties_left_out` | `reserved-kept` |
| Temporal-marked rows left out on both sides; the same row unmarked is governed | `theorem_temporal_marked_rows_left_out` | `temporal-row-governed`, `replay-keeps-marked` |
| Statement IDs not compared | `theorem_statement_ids_not_compared` | `statement-ids-compared` |

## Bindings and evidence

`replay.py::{read_canonical, _drop_temporal_marked, compare, _adoption_items, verify, VerificationReport,
VerificationReport.equal}` and `client.py::GraphLedger.verify` (rows in `crosswalk/decision-links.tsv`, family
`C-ledger_verify`). `binding.py` (local runtime wrapper) builds the tables view from its own SQL reads and the replay view
from `GraphLedger.reconstruct(head)`, then compares the transcription with the product's `verify()` on namespace `I60LB`
of the local fixture: equal ledger with `adopt=True` writes nothing; seven kinds of unrecorded writes (node with label
and property, Cypher property change, node deletion with a property, unrecorded edge with qualifier, deletion of a
recorded edge with qualifier, direct temporal write, node only in a named graph) give exactly the transcription's nine
entries; adoption writes one record per entry with the old head as parent and the next verify is equal. **AGREES (3
cases)**; 6 of 8 control-equivalent mutations disagree with an observation; `replay-keeps-marked` and
`statement-ids-compared` need forged history and are inspected only. Receipt `results/ledger_verify/20261117T200650Z-binding`.
The iteration-60 prediction rows V1, V2, C1, C2, R1.B and N9 (`PREDICTIONS-graded.md`) are further native observations.

## Premises and limits

- Quiescent inputs: no writer between the record read and the table read (verify takes no lock; q-led-006).
- The tables abstraction holds one value per (node, key): a node ID with property rows in two graphs is merged by the
  product in row order (graph-blind read; q-led-004 / HD-1401) and is outside the claim.
- Qualifier text conversion and default-graph spellings are transcription details of the harness, not modelled.
- The replay fold and Adopt's recording of the items are premises supplied by `reconstruction` / `ledger_content`.
- Redaction-in-progress (`redaction_in_progress` result) is outside (excluded area). Direct executable-body proofs: 0.
