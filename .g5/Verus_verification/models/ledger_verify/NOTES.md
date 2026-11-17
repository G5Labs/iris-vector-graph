# Verify: scope, entries and adoption

Product: `3eaa79cf77d3e0a879b2cced634cf2729d81499e`. Owners: `ledger.verify`, `ledger.verify.scope`, `ledger.unrecorded`.
Added in iteration 60 (the test obligations of `test_ledger_us09_verify.py`, `test_ledger_us05_compat.py`,
`test_ledger_us11_temporal_coexist.py`, `test_ledger_verify_pre_enable_writes.py`; map I3, I4, I35, I40, I62-I66 had no
formal claim). **Repaired in the iteration-60 repair after review 60** (FE-1, FE-2): as-built transcription,
**15 verified / 12 controls** (receipts `results/ledger_verify/20261117T211222Z-prove`, `20261117T2112*-control-*`).

## What the repair changed

- **Two temporal-marker rules, not one (FE-1).** The iteration-60 model held one boolean marker per edge row and per
  statement, so it could not represent a relationship whose qualifier `temporal` is the TEXT `"true"`. The product has
  two rules: `read_canonical` leaves out a row only when `temporal` is the JSON boolean `true` (what a temporal write
  stores); `_drop_temporal_marked` leaves out a replay statement whose `temporal` is the text `"true"` (meant for the
  pre-4.6.0 genesis records). The ledger stores every qualifier as text (`LedgerApply.QualsJson`;
  `changeset._str_value` turns a Python `True` into `"true"`). The model now has `QVal::{Bool, Text}`, `table_marked`
  and `replay_marked` separately, and derives the as-built divergence: `theorem_text_marker_never_equal` (every verify
  diverges, whatever the history, and every `verify(adopt=True)` writes another adoption revision) and
  `theorem_adoption_never_closes_a_text_marker`. Registered as
  [bug-led-013](../../bugs_issues.md#bug-led-013).
- **Narrowed:** `theorem_adoption_closes_the_difference` now requires `no_text_marker(b)` (no relationship in the
  tables whose temporal qualifier reads as text "true") and is stated over `replay_after_adoption = redrop(adopt(..))`,
  i.e. with the drop rule running again on the next verify. **Withdrawn:** its iteration-60 unconditional form ("adopting
  the entries always makes the next verify equal"); control `text-marker-premise-dropped` shows the premise is needed.
- **Narrowed/split:** `theorem_temporal_marked_rows_left_out` no longer says "left out on both sides" for one marker. It
  states the two rules with their neighbours: a JSON-true row is left out of the tables, the same row with text "true"
  is kept; a statement with text "true" is left out of the replay, one with "yes" is kept. **Withdrawn:** the
  iteration-60 claim that a marked relationship is left out on both sides (it holds only for JSON-true rows, which never
  have a statement, and for text-true statements, whose rows the tables keep).
- **Node existence from label and property rows (FE-2).** `canon_node` now includes a label row or a non-reserved
  property row (`read_canonical`'s `setdefault`; a reserved property is skipped first). `lemma_canonical_wf` proves
  every canonical view is well formed, so the `wf(b)` premise of the equality and adoption theorems is discharged for
  the tables side; `theorem_orphan_property_reports_node` gives the node-existence and property entries the product
  reports for a post-commit property on an ID with no node row.

## Claims and controls

| Claim | Theorem | Control (must fail) |
|---|---|---|
| Verify is equal exactly when the replayed and canonical views agree | `theorem_equal_iff_views_agree` | (follows from `emitted`) |
| Every canonical view is well formed (node from node, label or property rows) | `lemma_canonical_wf` | `node-from-node-rows-only` |
| A property row with no node row reports the node and the property | `theorem_orphan_property_reports_node` | `node-from-node-rows-only`, `new-entity-attributes-dropped` |
| Adopting the entries closes the difference **when no tables relationship has temporal text "true"** | `theorem_adoption_closes_the_difference` (via `lemma_adopt_agrees`) | `text-marker-premise-dropped`, `adopt-without-cascade`, `new-entity-attributes-dropped` (in `lemma_adopt_agrees`) |
| The two marker rules and their neighbours | `theorem_temporal_marked_rows_left_out` | `temporal-row-governed`, `replay-keeps-marked`, `one-marker-rule` |
| A committed qualifier `temporal` = "true" (or True) is in the tables, not in the replay; "yes" is on both sides | `theorem_marker_rules_differ` | `one-marker-rule`, `replay-keeps-marked` |
| The replay never carries temporal text "true" | `lemma_replay_view_dropped` | `replay-keeps-marked` |
| A tables relationship with temporal text "true" makes every verify diverge, whatever the history; every adopt writes again | `theorem_text_marker_never_equal` | `one-marker-rule` |
| After adopting it, the next replay drops it again and verify still diverges | `theorem_adoption_never_closes_a_text_marker` | `no-redrop` |
| An unrecorded node gives existence + label + property entries; an unrecorded deletion gives the deletion alone | `theorem_entries_for_created_and_deleted_nodes` | `new-entity-attributes-dropped` |
| No adoption revision when equal; never without `adopt=True` | `theorem_adoption_only_when_needed` | `adopt-when-equal` |
| Nodes matched by ID across graphs | `theorem_node_identity_ignores_graph` | `graph-scoped-node-identity` |
| Reserved properties left out | `theorem_reserved_properties_left_out` | `reserved-kept` |
| Statement IDs not compared | `theorem_statement_ids_not_compared` | `statement-ids-compared` |

## Bindings and evidence

`replay.py::{read_canonical, _drop_temporal_marked, compare, _adoption_items, verify, VerificationReport.equal}`,
`client.py::GraphLedger.verify`, `changeset.py::_str_value` and `LedgerApply.cls::QualsJson` (rows in
`crosswalk/decision-links.tsv`, family `C-ledger_verify`). `binding.py` (local runtime wrapper) builds the tables view
from its own SQL reads and the replay view from `GraphLedger.reconstruct(head)`, then compares the transcription with
the product's `verify()`. Repair run ([receipt](../../results/ledger_verify/20261117T212044Z-binding/receipt.json),
namespaces `I60RV` and `I60RT` of the local fixture): **AGREES, 5 cases**; V0-V2 as in iteration 60 plus a committed
`temporal="yes"` relationship and a post-commit property on an ID with no node row; T1 commits relationships with
`temporal="true"`, `temporal=True` and `"yes"` and writes unrecorded edges with text `"true"` and JSON `true` (entries
for the text-"true" tuples only); T2 adopts and the next verify still diverges with the same entries. 10 of 11
control-equivalent mutations disagree with an observation (`replay-keeps-marked` is now natively exercised;
`statement-ids-compared` still needs forged history; `text-marker-premise-dropped` is a proof premise whose runtime
consequence is the `no-redrop` mutation). The iteration-60 receipt `20261117T200650Z-binding` (namespace `I60LB`) is
kept; it never committed a text-"true" qualifier. Independent E2E reproduction:
[repair probe](../../../uplift/consolidated/iteration-60/repair/probes/observed-20261117T210756Z-fe1-fe2-fe5-c4.json)
sections `fe1`, `fe2`.

## Premises and limits

- Quiescent inputs: no writer between the record read and the table read (verify takes no lock; q-led-006).
- The tables abstraction holds one value per (node, key): a node ID with property rows in two graphs is merged by the
  product in row order (graph-blind read; q-led-004 / HD-1401) and is outside the claim.
- One comparable relationship per tuple on the replay side (`as_comparable` keys by tuple); a JSON `null` qualifier
  value (skipped by `read_canonical`) is not modelled; non-boolean JSON values are abstracted as text.
- The replay fold and Adopt's recording of the items are premises supplied by `reconstruction` / `ledger_content`;
  `redrop` states that the drop rule runs again on the next verify (observed in T2).
- Redaction-in-progress (`redaction_in_progress` result) is outside (excluded area). Direct executable-body proofs: 0.
