# 14 Replay, verification and record readers

Module: RPL
Root: RPL-0
Scope: client-side replay and verification (iris_vector_graph/ledger/replay.py), the record readers and verify of
GraphLedger (iris_vector_graph/ledger/client.py:695-744), the paged record reader and canonical record form
(iris_src/src/Graph/KG/Ledger.cls:571-646) and the reconstruction export (iris_vector_graph/ledger/export.py). Last stage of the
worked example. The replay theorems are in proofs/src/model.rs and l1.rs; the reader race is model-checked in
model/src/readers.rs.

## Glossary

| Term | Defined by | Restated by |
|---|---|---|
| verify call | RPL-D2 | |
| checked content | RPL-D3 | |
| record reader | RPL-D4 | RPL-D4a, RPL-D4b, RPL-D4c |
| unrecorded write | RPL-D5 | RPL-D5a |
| adoption | RPL-D6 | |

## Statements

| Id | Parent | Kind | Statement | Evidence | Source | Notes |
|---|---|---|---|---|---|---|
| RPL-0 | SYS-0 | R | The ledger's records can be played back to rebuild the graph and checked against the store. | inspected:iris_vector_graph/ledger/replay.py:1-6 | specs/256-ledger-tenant-redaction/spec.md; docs/adr/0013-redaction-removes-content-from-history.md | "Verifiable means replay equals the store" (spec 256); there is no hash chain over records. |
| RPL-D1 | RPL-0 | D | A replay up to a revision uses only the records up to that point. | inspected:iris_vector_graph/ledger/replay.py:155-210; inspected:iris_vector_graph/ledger/replay.py:544-570 | specs/213-graph-revision-ledger | GraphState.apply and reconstruct. Modelled as a fold over records (proofs/src/model.rs replay). |
| RPL-D2 | RPL-0 | D | The verify call checks the replay against the tables. | inspected:iris_vector_graph/ledger/replay.py:806-855 | specs/256-ledger-tenant-redaction/spec.md | ledger.verify(); results equal, diverges, redaction_in_progress. |
| RPL-D3 | RPL-0 | D | Checked content is what the verify call looks at: nodes, labels, props, edges and their keys. | inspected:iris_vector_graph/ledger/replay.py:588-643 | specs/213-graph-revision-ledger | read_canonical. |
| RPL-D4 | RPL-0 | D | A record reader returns ledger records, or a view built from them. | inspected:iris_vector_graph/ledger/client.py:695-739 | docs/adr/0013-redaction-removes-content-from-history.md | get_revision, diff, reconstruct, export_reconstruction. |
| RPL-D5 | RPL-0 | D | An unrecorded write is a change to governed content made outside the ledger. | inspected:iris_vector_graph/ledger/replay.py:645-700 | specs/213-graph-revision-ledger | Same meaning as LED-D10; compare's classification unrecorded_writes. |
| RPL-D6 | RPL-0 | D | An adoption is a revision that saves a change made outside the ledger. | inspected:iris_vector_graph/ledger/replay.py:849-856 | specs/213-graph-revision-ledger | Same meaning as LED-D11. |
| RPL-B1 | RPL-0 | B | Replay skips tombstones and the notes a redaction saves about itself. | inspected:iris_vector_graph/ledger/replay.py:24-26; inspected:iris_vector_graph/ledger/replay.py:170-172; tested:tests/unit/test_256_ledger_redaction.py::test_apply_ignores_a_tombstone; tested:tests/unit/test_256_ledger_redaction.py::test_apply_ignores_a_redaction_revision_record_even_when_its_seq_names_a_statement; proved:theorem_audit_changes_nothing | specs/256-ledger-tenant-redaction/spec.md | FR-003. The unit tests ran in the uplift's unit run (24,579 passed). |
| RPL-B1.1 | RPL-B1 | B | After a redaction, replay gives what it gave before, less the tenant. | proved:lemma_replay_tomb; live:native-mixed_tenant_flow; tested:tests/integration/test_256_ledger_redaction_e2e.py::test_replay_to_every_seq_holds_no_tenant_a_content | specs/256-ledger-tenant-redaction/spec.md | Proved for every history and every target whose records are separable (P-1301). |
| RPL-B2 | RPL-0 | B | The verify call looks at checked content and nothing else. | inspected:iris_vector_graph/ledger/replay.py:588-643 | specs/213-graph-revision-ledger | Vectors, text documents, the temporal index and the adjacency index are outside it. |
| RPL-B2.1 | RPL-B2 | B | It leaves out time-stamped records and the rows they imply. | inspected:iris_vector_graph/ledger/replay.py:618-622; inspected:iris_vector_graph/ledger/replay.py:792-804 | docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md | A temporal record does not change the replay (GraphState.apply has no temporal branch). So "replay equals the store" says nothing about the temporal index. |
| RPL-B2.2 | RPL-B2 | B | It matches nodes by id alone, whatever graph holds them. | inspected:iris_vector_graph/ledger/replay.py:596-606 | specs/256-ledger-tenant-redaction/plan.md | The ledger's node records name no graph either. See RPL-B7. |
| RPL-B3 | RPL-0 | B | Once a tenant is erased and redacted, the verify call says equal again. | proved:theorem_erase_then_redact; tested:tests/integration/test_256_ledger_redaction_e2e.py::test_verify_diverges_after_the_erase_alone_and_is_equal_after_the_redaction; live:native-mixed_tenant_flow; live:native-killed_mid_batch; live:native-killed_at_random; live:native-paused_and_resumed; mc:redaction-reviewed; assumed:P-1310; finding:F-1305 | specs/256-ledger-tenant-redaction/spec.md | FR-007. Proved for any history from a state where the verify call said equal, for targets whose records are separable (P-1301) and where the erasure, the liveness check and the record match cover the same entities (P-1310). At the pin those three scopes differ for unprefixed tenants in their own graph, where it fails live (F-1305). Live in the four cited scenarios. Model: "replay equals the store once settled" holds in every reachable state of the reviewed design. |
| RPL-B3.1 | RPL-B3 | B | Saves outside the tenant between the two steps keep this true. | proved:theorem_commit_between; live:native-paused_and_resumed | specs/256-ledger-tenant-redaction/spec.md | Live: tenant B committed while A's redaction was paused. |
| RPL-P1 | RPL-B3 | P | The theorem needs every record of one node or edge to fall in a redaction or none. | assumed:P-1301 | proofs/src/model.rs | Separability, as RED-P1. |
| RPL-B3.2 | RPL-B3 | B | The world of the upstream test did not match before the erasure. | live:native-mixed_tenant_flow; finding:F-1401 | tests/integration/test_256_ledger_redaction_e2e.py | Test reflection: "equal after redaction" there is also the erasure removing a node row its detach delete left (tenantA\|n3 in gTenantA). The test never checks verify before erasing. |
| RPL-B4 | RPL-0 | B | After erasure alone, the verify call says the two do not match. | proved:theorem_erasure_alone_diverges; tested:tests/integration/test_256_ledger_redaction_e2e.py::test_verify_diverges_after_the_erase_alone_and_is_equal_after_the_redaction; live:native-mixed_tenant_flow | specs/256-ledger-tenant-redaction/plan.md | |
| RPL-X1 | RPL-0 | X | While a redaction is not done, the verify call says so and saves nothing. | inspected:iris_vector_graph/ledger/replay.py:812-823; tested:tests/unit/test_256_ledger_redaction.py::test_verify_reports_in_progress_without_reading_records_or_adopting; live:native-paused_and_resumed | docs/adr/0013-redaction-removes-content-from-history.md | Decision 3: adopting the difference would write the erased content back. |
| RPL-D4a | RPL-X1 | D | A record reader returns ledger records, or a view built from them. | inspected:iris_vector_graph/ledger/client.py:695-739 | docs/adr/0013-redaction-removes-content-from-history.md | Same meaning as RPL-D4. Local restatement for the literal term-scope rule (HD-0001). |
| RPL-X2 | RPL-X1 | X | While a redaction is not done, each record reader stops with an error. | inspected:iris_vector_graph/ledger/client.py:687-739; tested:tests/unit/test_256_ledger_redaction.py::test_record_readers_refuse_while_a_redaction_runs; live:native-paused_and_resumed | docs/adr/0013-redaction-removes-content-from-history.md | RedactionInProgressError. history() is not a record reader and does not refuse. |
| RPL-D4b | RPL-X2 | D | A record reader returns ledger records, or a view built from them. | inspected:iris_vector_graph/ledger/client.py:695-739 | docs/adr/0013-redaction-removes-content-from-history.md | Same meaning as RPL-D4. Local restatement for the literal term-scope rule (HD-0001). |
| RPL-I1 | RPL-X2 | I | A record reader never returns a view of a redaction that is half done. | finding:F-1402; mc:readers-as-built; mc:readers-reviewed; live:native-reader_races_redaction | docs/adr/0013-redaction-removes-content-from-history.md | At the pin the reader checks the marker once, before it reads, with no lock; a redaction that starts in between is read half done (4-step counterexample; reproduced live with reconstruct). A second check after the read passes the model. |
| RPL-D4c | RPL-I1 | D | A record reader returns ledger records, or a view built from them. | inspected:iris_vector_graph/ledger/client.py:695-739 | docs/adr/0013-redaction-removes-content-from-history.md | Same meaning as RPL-D4. Local restatement for the literal term-scope rule (HD-0001). |
| RPL-Q1 | RPL-I1 | Q | Should each record reader look for a redaction again once it has read? | open:HD-1401 | model/src/readers.rs | |
| RPL-T1 | RPL-D2 | T | The verify call reads records and tables at separate times, with no lock. | inspected:iris_vector_graph/ledger/replay.py:806-835; assumed:P-0002 | specs/213-graph-revision-ledger | A commit in between shows up as a difference. |
| RPL-P2 | RPL-T1 | P | The verify call is run while nobody writes to the graph. | assumed:P-1401 | specs/213-graph-revision-ledger | |
| RPL-B5 | RPL-0 | B | Record readers show a tombstone in its place as a redacted record. | inspected:iris_src/src/Graph/KG/Ledger.cls:607-646; tested:tests/integration/test_256_ledger_redaction_e2e.py::test_diff_marks_tombstones_rather_than_hiding_them; tested:tests/unit/test_256_ledger_redaction.py::test_a_tombstone_contributes_no_entry_and_is_listed_as_redacted | specs/256-ledger-tenant-redaction/spec.md | FR-003: op "redacted", digest and redacted_op columns; Diff.redacted lists (seq, ordinal). |
| RPL-B6 | RPL-0 | B | An export made before a redaction still holds the content it removed. | inspected:iris_src/src/Graph/KG/LedgerRedact.cls:505-509; assumed:P-1309 | docs/adr/0013-redaction-removes-content-from-history.md | Named in every receipt. |
| RPL-B7 | RPL-D2 | B | The verify call says equal when every change went through the ledger. | finding:F-1401; live:native-mixed_tenant_flow | specs/213-graph-revision-ledger | Fails after a ledger detach delete of a node that has edges in a named graph: the delete keeps the named graph's node row (4.6.0 R290) and verification, comparing nodes by id alone, sees that row. |
| RPL-D5a | RPL-B7 | D | An unrecorded write is a change to governed content made outside the ledger. | inspected:iris_vector_graph/ledger/replay.py:645-700 | specs/213-graph-revision-ledger | Same meaning as RPL-D5. Local restatement for the literal term-scope rule (HD-0001). |
| RPL-B7.1 | RPL-B7 | B | The verify call names a change made outside the ledger an unrecorded write. | inspected:iris_vector_graph/ledger/replay.py:645-700 | specs/213-graph-revision-ledger | classification unrecorded_writes. |
| RPL-B8 | RPL-0 | B | A verify call with adoption saves the gaps it found as an adoption. | inspected:iris_vector_graph/ledger/replay.py:849-856 | specs/213-graph-revision-ledger | While a redaction marker exists the adoption is refused like any commit into the target (Ledger.cls:514-518). |

## Cells

Entity ledger view: states agreeing, erased not redacted, redacting, redacted, with unrecorded writes; commands verify, verify with adoption, read records, reconstruct, export

| Entity | State | Command | Outcome | Statements | Decision |
|---|---|---|---|---|---|
| ledger view | agreeing | verify | ok | RPL-B7 | |
| ledger view | agreeing | verify with adoption | no-op | RPL-B8 | |
| ledger view | agreeing | read records | ok | RPL-B5 | |
| ledger view | agreeing | reconstruct | ok | RPL-D1 | |
| ledger view | agreeing | export | ok | RPL-B6 | |
| ledger view | erased not redacted | verify | ok | RPL-B4 | |
| ledger view | erased not redacted | verify with adoption | ok | RPL-B8 | |
| ledger view | erased not redacted | read records | ok | ERS-B4 | |
| ledger view | erased not redacted | reconstruct | ok | ERS-B3 | |
| ledger view | erased not redacted | export | ok | RPL-B6 | |
| ledger view | redacting | verify | refused | RPL-X1 | |
| ledger view | redacting | verify with adoption | refused | RPL-X1 | |
| ledger view | redacting | read records | refused | RPL-X2, RPL-I1 | |
| ledger view | redacting | reconstruct | refused | RPL-X2, RPL-I1 | |
| ledger view | redacting | export | refused | RPL-X2 | |
| ledger view | redacted | verify | ok | RPL-B3 | |
| ledger view | redacted | verify with adoption | no-op | RPL-B3, RPL-B8 | |
| ledger view | redacted | read records | ok | RPL-B5 | |
| ledger view | redacted | reconstruct | ok | RPL-B1.1 | |
| ledger view | redacted | export | ok | RPL-B1.1 | |
| ledger view | with unrecorded writes | verify | ok | RPL-B7.1 | |
| ledger view | with unrecorded writes | verify with adoption | ok | RPL-B8 | |
| ledger view | with unrecorded writes | read records | ok | RPL-B5 | |
| ledger view | with unrecorded writes | reconstruct | ok | RPL-D1 | |
| ledger view | with unrecorded writes | export | ok | RPL-B6 | |
