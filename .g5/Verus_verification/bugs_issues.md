# Bugs and issues — iteration 13 findings audit

Git `eceb147d37720658e34b07f279cc267870fd393c`; product `3eaa79cf`. This is a fresh audit, with no product repair or uplift iteration. There are 46 ordinary entries with executable evidence: 42 e2e reproduced and 4 partial reproduced. Another 107 security-related entries are explicitly **outside active reproduction scope** and received defensive source/existing-evidence review only. Entries are ordered by severity; each declares its evidence scope.

All 434 starting IDs are reconciled. The 281 removed entries retain stable IDs and historical evidence in the [review record](audits/register-20261115/bugs-review.md). Lack of reproduction is not proof of correctness. [Counts, commands and limitations](audits/register-20261115/README.md).

## Findings by severity and evidence scope

<a id="bug-str-001"></a>
### Deleting one of several parallel edges through the ledger removes the adjacency of the edges that remain

Severity: High · Decision: Open

Run: Uplift 2026-11-13

Found by: [witness_ledger_delete_rel_drops_survivor_indexed and witness_ledger_delete_rel_drops_survivors_non_indexed](results/graph_structure/20261114T000451Z-prove/receipt.json) in [graph_structure.rs](models/graph_structure/graph_structure.rs) (B-structure O5/F3; control `as-built-delete-rel-without-line-689` attributes the witness to line 689); A-structure F3 and S4 ([intent](../uplift/ivg-verus-initial/intent/graph-structure.md)); A-ops hazard (a)6 ([operations](../uplift/ivg-verus-initial/intent/operations.md)); review R2-data R1-2.

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `parallel_ledger_delete`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: [graph_structure_parallel_delete_rel](receipts/native/graph_structure_parallel_delete_rel.json) — in the default graph and in a named graph of an indexed namespace, two parallel `s-p-o` edges, ledger `delete_relationship` of one: before, 2 rows, children `[0,1]`, `#` = 2, degree 2; after, one row remains, but the index has no entry for the triple and the degree and a recount read 0 (expected: a bare leaf and degree 1), while Cypher `MATCH` still returns the neighbour through the SQL row.

Expected: every row change moves `out`/`in` in the same transaction and no row is left without adjacency (spec 252 FR-001/FR-016); the multigraph layout keeps one leaf while one edge remains and degree counts live edges (spec 234 FR-003/FR-004; CONTEXT.md:90-95, 103-107).

Observed: `LedgerApply.DeleteRelInternal` deletes the chosen row by `%ID` (`LedgerApply.cls:678`); in an indexed namespace the row's functional-index callback (`RemoveKeyed`) already collapses the triple to the survivor's bare leaf, and then `If $Data(^KG("out",...)) Do Adjacency.Remove(...)` (`LedgerApply.cls:688-689`) kills that leaf and any children. Line 689 predates spec 252 (`fa67b2b3`) and lacks the `Indexed()` guard that `OpCreateRel` has (`LedgerApply.cls:508`). In a non-indexed namespace line 689 alone removes every parallel edge's entry.

Consequence: the surviving relationships are invisible to traversal, native Cypher and degree until `sync()` or a rebuild; reachable whenever the ledger is enabled in non-strict mode on a multigraph graph (parallel edges come from Cypher `CREATE`).

Repair proposal (not implemented): skip line 689 when `Adjacency.Indexed()`, and in a non-indexed multigraph call `RemoveKeyed` with the deleted row's `ekey` (proved: `theorem_repaired_delete_rel_keeps_layout`; single-edge deletes unchanged, `witness_ledger_delete_rel_single_edge_is_right`). Related decision: [q-str-004](open_questions.md#q-str-004). Governing statements: [structure.multigraph.layout](../ontology/features/graph-structure.g5.md#structure.multigraph.layout), [structure.multigraph.count](../ontology/features/graph-structure.g5.md#structure.multigraph.count).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [structure.multigraph.layout](../ontology/features/graph-structure.g5.md#structure.multigraph.layout), [structure.multigraph.count](../ontology/features/graph-structure.g5.md#structure.multigraph.count).

<a id="bug-tmp-001"></a>
### A temporal write whose structural step fails keeps its raw entry, cannot be finished by a retry, and the bulk fallback reports it written

Severity: High · Decision: Open

Run: Uplift 2026-11-13

Found by: [witness_partial_write_is_not_repaired_by_retry and witness_bulk_fallback_reports_success](results/temporal/20261114T001508Z-prove/receipt.json) in [temporal.rs](models/temporal/temporal.rs) (B-temporal O1/F2; valid outcome `witness_assert_first_repairs_the_retry`); A-temporal F2, S2, S3 ([intent](../uplift/ivg-verus-initial/intent/temporal.md)); reconstruction check gap G32; review R2-data R1-6.

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `temporal_partial_retry, temporal_bulk_insert, temporal_bulk_update`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: [temporal_write_modes](receipts/native/temporal_write_modes.json) — `bulk_fallback_insert`: an insert batch with one edge whose endpoint ID IRIS refuses (over 256 characters) returned `written=2, collisions=0` and no error, while the store holds one structural row and the statistics disagree with the raw edges; `bulk_fallback_update`: after the fallback the whole-bucket count/sum/velocity are 2/2.0/4 against the raw store's 2/6.0/2. `partial_write_retry`: a single-edge write refused at its structural step left 1 raw edge and bucket 1 with no statistics, and the insert retry returned without error and wrote nothing more.

Expected: a temporal edge implies its structural edge (ADR-0009); a refused write "writes nothing" (`create_edge_temporal` docstring, `temporal.py:260-261`); first-write-wins with counts that match the raw store (spec 254 FR-003); a failed bulk write reports the count written (R203).

Observed: `TemporalIndex.WriteStores` writes `tout`, `tlast`, `tin` and `$Increment(bucket)` before `AssertTemporalRow`, with no transaction (`TemporalIndex.cls:95-111`; `temporal.py:12-17` admits the residue); a throw leaves no row, aggregate or attributes, and an insert-mode retry then hits `$Data(tout)` and is a silent collision (`TemporalIndex.cls:84-85`; `InsertEdge` answers 1 for every outcome, `:64`). `bulk_write_temporal_edges` catches the batch failure and re-sends every edge one by one (`iris_sql_store.py:2759-2786`), counting each collision as inserted; in update mode it re-increments the statistics of edges already written.

Consequence: a caller is told every edge was written while one has no structural edge, statistics or attributes, and no retry can complete it; windowed statistics disagree with the raw store.

Repair proposal (not implemented): run the structural step before the first Set in `WriteStores`, or wrap `WriteStores` in its own `TSTART`/`TROLLBACK 1`; make the bulk fallback raise, or re-send only the edges not yet written. Open choice: [temporal.write.partial-failure](open_questions.md#temporal.write.partial-failure). Governing statements: [temporal.write](../ontology/features/temporal.g5.md#temporal.write), [temporal.structural](../ontology/features/temporal.g5.md#temporal.structural).


Iteration 8 strengthens completed-prefix then whole-batch replay with the known F-0502 time carrier: after actual native full success followed by an injected reply error, raw0 can leave both current-time and epoch0 events while count1 is reported. retry_replay derives completed prefix state, entire fallback and final points; positive and prewrite neighbors remain. [Scope and controls](models/retry_replay/NOTES.md). Partial effects within one write, real transport faults, failing fallback items and other modes remain open; no repair or new bug count.


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [temporal.write](../ontology/features/temporal.g5.md#temporal.write), [temporal.write.partial-failure](open_questions.md#temporal.write.partial-failure), [temporal.structural](../ontology/features/temporal.g5.md#temporal.structural).

<a id="bug-tmp-002"></a>
### An update at an occupied temporal coordinate counts the edge twice in the statistics

Severity: High · Decision: Open

Run: Uplift 2026-11-13

Also recorded as: F-0501 (playbook arm, S2, reproduced-live; [05.json](../../experiment/playbook-completion/findings/audit/05.json)). Severity differs: here High, playbook S2; both are kept. (crosswalk)

Found by: [witness_update_double_counts](results/temporal/20261114T001508Z-prove/receipt.json) in [temporal.rs](models/temporal/temporal.rs) (B-temporal O1/F1; Q1 option (b) proved consistent by `theorem_stats_repaired_total`); A-temporal F1; A-ops candidate finding and test gap (d) (`test_254_collisions_e2e.py:104-110` asserts no aggregate after an update); review R2-data R1-6.

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `temporal_update_counts`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: [temporal_write_modes](receipts/native/temporal_write_modes.json) case `update_double_count` — after an insert and an update of one coordinate, one raw edge (w=9) but the whole-bucket count=2, sum=11.0, velocity=2 (the raw-exact reading expects 1/9.0/1, the docstring 1/2.0); `bulk_fallback_update` shows the same inflation through the bulk path.

Expected: the statistics after an update "remain based on the original value" (`temporal.py:273-279`; `TemporalIndex.cls:77-79`; CHANGELOG 4669-4670 and 4914-4915 "tagg not adjusted"); under the raw-exact reading they equal the surviving raw edges. The model shows the as-built result breaks both readings.

Observed: with `pMode="update"` `WriteStores` has no early return (`TemporalIndex.cls:82-86`) and runs `$Increment(bucket)` (`:102`) and the count and sum increments (`:117-118`), widening min/max; a later delete rebuilds `tagg` but decrements `bucket` by one only (`:357`). The ledger's `create_temporal_edge` defaults to "update" (`LedgerApply.cls:628`).

Consequence: insert w=2 then update w=9 gives count 2, sum 11, bucket 2 for one raw edge; a window aligned to the bucket and one that cuts it answer differently; after the delete the bucket counts an edge that no longer exists.

Repair proposal (not implemented): on an update, rebuild the bucket's statistics from the raw edges (as delete does) and leave `bucket` alone. Open choice: [temporal.write.update-statistics](open_questions.md#temporal.write.update-statistics). Governing statement: [temporal.stats](../ontology/features/temporal.g5.md#temporal.stats).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [temporal.write.update-statistics](open_questions.md#temporal.write.update-statistics), [temporal.stats](../ontology/features/temporal.g5.md#temporal.stats).

<a id="bug-tmp-003"></a>
### A rolled-back temporal write leaves its statistics counted, so a retry counts the edge twice

Severity: High · Decision: Open

Run: Uplift 2026-11-13

Found by: [witness_refused_changeset_leaves_counts, witness_blocked_changeset_leaves_counts, witness_throw_in_changeset_leaves_bucket, witness_caller_rollback_leaves_counts and witness_caller_rollback_of_ledger_commit_leaves_counts](results/temporal/20261114T001508Z-prove/receipt.json) in [temporal.rs](models/temporal/temporal.rs) (B-temporal O6/F3, with `lemma_refused_commit_restores_journaled`); A-temporal F3.

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `temporal_rollback_r1, temporal_rollback_r2, temporal_rollback_r3, temporal_rollback_r4`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: [temporal_rollback_counters](receipts/native/temporal_rollback_counters.json) — R1 a refused changeset: no raw edge, but the whole-bucket count=1, sum=2.0, velocity=1, and the retry leaves one raw edge with count=2, sum=4.0, velocity=2; R2 a caller's rollback of a ledger commit and R3 of a direct `create_edge_temporal`: no raw edge, count=1; R4 a throw inside a changeset: velocity=1 with no edge.

Expected: if a changeset fails, none of its temporal writes may remain, statistics included (spec 224 "atomically with all structural ops", `changeset.py:321-336`; ledger FR-047, a revision exists iff its mutations are visible); USER_GUIDE "Writes inside your transaction" says a caller's rollback removes both and leaves only the version token and generations (`USER_GUIDE.md:236-275`).

Observed: `WriteStores` counts with `$Increment` (`TemporalIndex.cls:102, 117-118`), which IRIS does not undo on `TROLLBACK` (ADR-0010 "Context"), while the raw stores are journaled Sets and are undone.

Consequence: windowed counts, sums and velocity include edges that do not exist, and every retry of a failed changeset inflates them further, with no error.

Repair proposal (not implemented): replace the statistics `$Increment`s with journaled `Set x=$Get(x)+1` (which needs a lock against concurrent writers, see [q-tmp-001](open_questions.md#q-tmp-001)), or rebuild the bucket's statistics from the raw store after a rollback; at minimum list the statistics in the USER_GUIDE's rollback residue. Model comparison: `witness_counters_undone_keep_exact` (counters undone keep the rule). Governing statements: [temporal.ledger.atomic](../ontology/features/temporal.g5.md#temporal.ledger.atomic), [temporal.stats](../ontology/features/temporal.g5.md#temporal.stats).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [temporal.stats](../ontology/features/temporal.g5.md#temporal.stats), [temporal.ledger.atomic](../ontology/features/temporal.g5.md#temporal.ledger.atomic).

<a id="bug-tmp-010"></a>
### A rolled-back temporal delete or node erase leaves the bucket's event counter decremented

Severity: High · Decision: Open

Run: Uplift 2026-11-13

Found by: [witness_rolled_back_delete_undercounts](results/temporal/20261114T001508Z-prove/receipt.json) in [temporal.rs](models/temporal/temporal.rs) (valid outcome `witness_rolled_back_delete_exact_if_counters_undone`); review R2-data R1-9 (the mirror of [bug-tmp-003](#bug-tmp-003)).

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `temporal_rollback_r5, temporal_rollback_r5b, temporal_rollback_r6`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: [temporal_rollback_counters](receipts/native/temporal_rollback_counters.json) — R5, a caller's rolled-back delete of the only edge: the raw edge is back with whole-bucket count 1 and sum 2.0, but velocity 0 and the raw bucket 0 (expected 1/2.0/1); R5b, one of two edges: velocity 1 and bucket 1 (expected 2); R6, a rolled-back node erasure: velocity 0 and bucket 0 (expected 1).

Expected: node erasure keeps the remaining statistics exact and runs inside the erasure's transaction; a failed or rolled-back erase leaves the content untouched (ADR-0004; CONTEXT.md "Erasure"); "if a changeset fails, none of its temporal writes may remain, statistics included".

Observed: `RemoveTemporalRow` decrements the bucket with `$Increment(bucket,-1)` (`TemporalIndex.cls:357`), which a `TROLLBACK` does not undo, while its Kill at zero is journaled and restored; since 4.6.4 `delete_edge_temporal` and `delete_node` (→ `TemporalIndex.EraseNodes`) nest in a caller's transaction.

Consequence: after a caller rolls back a delete or a node erase, velocity and bucket counts under-count events that still exist. The bucket node is left holding 0 instead of being killed, and `FindBursts` lists every source present in a bucket, so with a threshold of 0 or less it reports a velocity-0 burst (`TemporalIndex.cls:355-357, 784-803`; review round2-domains R2-4).

Repair proposal (not implemented): the same as [bug-tmp-003](#bug-tmp-003): journaled updates of the counters, or a rebuild of the bucket after a rollback. Governing statements: [temporal.erase](../ontology/features/temporal.g5.md#temporal.erase), [temporal.delete](../ontology/features/temporal.g5.md#temporal.delete).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [temporal.delete](../ontology/features/temporal.g5.md#temporal.delete), [temporal.erase](../ontology/features/temporal.g5.md#temporal.erase).

<a id="F-0304"></a>
### Storing an edge over a marked edge does not take the edge over

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [03.json](../../experiment/playbook-completion/findings/audit/03.json) (live `breadth-a-live-05-temporal`; mc `breadth-a-mc-tmp_mark-as-built`; mc `breadth-a-mc-tmp_mark-reviewed`; control `breadth-a-control-tmp_mark`; live `ws-live-ba-explicit-survives`)

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `store_edge_marker_adoption`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-05-temporal`, `ws-live-ba-explicit-survives`

- Expected: ADR-0009 (CONTEXT.md:66-73) and HD-0302 (supported): an explicit structural create clears the temporal mark; a temporal-backed row must not delete an explicitly written edge.
- Observed at the pin: create_edge's edge survives (control), store_edge's edge is deleted
- Source severity S1, confidence high; module 03; governing page here: `structure. / install.bulk_load`.
- Remedy proposed by the playbook arm (not implemented): Run the adopt step after store_edge's swallowed duplicate.
- Reviewed-design control: `playbook-proofs-d1c` `control_f0304_store_no_adopt` fails where expected in this run ([receipt](results/playbook-proofs-d1c/20261115T035820Z-control_f0304_store_no_adopt/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1c/20261115T035754Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [temporal.structural.adopt](../ontology/features/temporal.g5.md#temporal.structural.adopt).

<a id="bug-001"></a>
### Two redactions of different targets can run at once, and each one's audit and receipt then describes the other's work

Severity: High · Decision: Open

Run: Uplift 2026-11-13

Also recorded as: F-1303 (playbook arm, S1, reproduced-live; [13.json](../../experiment/playbook-completion/findings/audit/13.json)). (crosswalk)

Found by: [witness_concurrent_targets_break_the_marker](results/ledger_redaction/20261114T044401Z-prove/receipt.json) in [redaction.rs](models/ledger_redaction/redaction.rs) (Variant serial: false): the marker names target A while run B writes tombstones; B's final step removes the marker while A is unfinished and a commit into A is then admitted. [witness_race_then_resume_loses_attribution](results/ledger_redaction/20261114T044401Z-prove/receipt.json) is a classification fact, not a trace of the lifecycle model (review R1-core R1-1; round2-core R2-2): with the knowledge another target's final step removes, `Matches` answers Unknown for A's remaining qualifier records.

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: [redaction_concurrent_targets](receipts/native/redaction_concurrent_targets.json) (final, hash-stamped run) — while an ordinary long commit held the head lock, `redact(None, prefix="tA")` and `redact(None, prefix="tB")` both passed their entry checks. B completed: its single redaction revision (seq 6, target digest of `tB|`) names revisions 2 (tenant A's) and 3, and its receipt reports 20 records tombstoned, 2 revisions' metadata cleared and 2 idempotency keys removed, tenant A's included. B's final step removed the marker while A was still running, and a commit into A's target was then accepted (seq 7). A went on to tombstone that commit's records and ended with `RedactionTargetLiveError` (the late commit made `tA|` content live), leaving its own marker in place. The model witness's mid-run commit window was hit natively.

Expected: ADR-0013 "A redaction of a different target is refused until the first one finishes"; spec 256 Decision 1 (Tom, 2026-10-22): the redaction revision names *the* redacted revisions; Decision 3: while a redaction runs, nothing may be written into its target.

Observed: `LedgerRedact.Redact` compares the marker before taking any lock (LedgerRedact.cls:202-205); the marker is written lazily by the first batch that finds a match (:322-324) and never compared by `BatchInLock` or `FinalInLock`; the counters and redacted-revision list under `^IVG.Ledger("redacting")` are shared by every run (:343-344, :423-428); `FinalInLock` kills the marker whoever owns it (:439).

Consequence: an audit trail that names the wrong tenant's revisions and a receipt that reports the other tenant's work as its own; a window, observed natively, in which a commit into the unfinished target is admitted, after which the run tombstones that commit's records while their content is live, ends refused, and leaves its marker blocking readers, verify and every other target until the content is erased again. The two-call tenant recipe (`redact(graph)` + `redact(None, prefix=)`) invites running both at once. By code reading (`FinalInLock` kills the whole `("redacting")` subtree, whoever owns the marker) and that classification fact, B's final step also removes the statement endpoints A's earlier calls learned, so a resumed prefix run of A can leave its remaining qualifier records in clear under a `complete` receipt. That knowledge loss was not observed natively (the native race showed the commit-admission consequence); a single paused and resumed prefix run without the race attributes correctly ([redaction_prefix_resume](receipts/native/redaction_prefix_resume.json)).

Repair proposal (not implemented): [simp-001](design_simplification.md#simp-001). Governing statements: [redaction.batches.competing](../ontology/features/redaction.g5.md#redaction.batches.competing), [redaction.audit](../ontology/features/redaction.g5.md#redaction.audit).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-002"></a>
### A redaction completes while its target's content is still uncommitted-deleted, and the caller's rollback brings the content back with its history tombstoned

Severity: High · Decision: Open

Run: Uplift 2026-11-13

Also recorded as: F-C1201 (playbook arm, S1, reproduced-live; [12.json](../../experiment/playbook-completion/findings/audit/12.json)); F-C1301 (playbook arm, S1, reproduced-live; [13.json](../../experiment/playbook-completion/findings/audit/13.json)). (crosswalk)

Found by: source review (`LiveRows` reads without locks and the Eraser takes no ledger lock; `aad50087` makes `erase_graph` nest in the caller's transaction on a plain connection) and the native probe below (review R1-core R1-12).

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: [erasure_caller_transaction](receipts/native/erasure_caller_transaction_redaction.json) — connection 1: `START TRANSACTION`; `erase_graph("gA")` (nested, `$TLEVEL=1`); connection 2: `redact("gA")` completed with 2 tombstones; connection 1: `ROLLBACK`. Afterwards gA has 1 live edge row, its create records are tombstones, and `verify()` reports `diverges`.

Expected: ADR-0013 "Redaction only follows erasure. It is refused while any row of the target is live"; CONTEXT.md "Erasure either completes or leaves the graph untouched".

Observed: `LedgerRedact.LiveRows` (LedgerRedact.cls:149-178) counts rows with `%SQL.Statement` at the process default isolation and sees the uncommitted deletes as gone; nothing serialises erasure with redaction.

Consequence: the history of content that is live again is destroyed; verify never returns to equal for it.

Repair proposal (not implemented): read liveness under the same lock or isolation that erasure commits under (e.g. take the ledger head lock in the eraser, or a target lock shared by erase and redact), or refuse redaction while an erase of the target is uncommitted. Open contract: [q-004](open_questions.md#q-004). Governing statement: [redaction.after-erasure](../ontology/features/redaction.g5.md#redaction.after-erasure).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-srch-001"></a>
### Search indexes keep answering with content that was erased, and a re-created node inherits the erased text

Severity: High · Decision: Open

Run: Uplift 2026-11-13

Found by: [witness_erase_leaves_bm25](results/search/20261114T000543Z-prove/receipt.json) in [search.rs](models/search/search.rs) (B-search O5/F1; repair `theorem_repaired_erase_removes_answers`); A-search F1 and S2 ([intent](../uplift/ivg-verus-initial/intent/search.md)); A-ops hazard (a)3; reconstruction check 2(b)12 and correction 6; review R3-platform R1-7.

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: [search_bm25_erase](receipts/native/search_bm25_erase.json) — a BM25 index built for graph `g5probe_bm25_erase` over one node; `erase_graph` removed the node, yet `bm25_search` still answered `g5p:erase:1` (score 0.288); after the node was re-created with other text, the erased text still scored it.

Expected: an erase removes graph content "from every store that holds it" (ADR-0004:10-12, 79-80); `GraphStores.cls:1-16` claims to be the one inventory; `^IVG.AlgoCache` is erased because "no answer outlives erased content" (`GraphStores.cls:113-116`); the Eraser's own reason for erasing `docs` is that text otherwise attaches to whoever re-creates the ID (`Eraser.cls:138-144`).

Observed: `^BM25Idx`, `^IVF`, `^PLAID` and `^VecIdx` are in neither inventory list and no erase or delete path touches them (no reference in `Eraser.cls`; `index_protocol.py:41` is the only `bm25_insert` caller). A BM25 index records its graph (`cfg graph`, `BM25Index.cls:168`), and fusion prefers the index recorded for the graph (`vector.py:204-206`).

Consequence: erased or deleted content stays retrievable through BM25, fusion and the vector indexes until a rebuild, and a node re-created under an erased ID is ranked by the erased text.

Repair proposal (not implemented): let `EraseGraph` drop or empty the BM25 indexes whose `cfg graph` is the erased graph, and list `^IVF`, `^PLAID` and `^VecIdx` in the inventory as unscoped derived stores to rebuild after an erase (proved for BM25 with a frame clause: other graphs' indexes unchanged). The rule is decided for erasure by CONTEXT.md "Erasure", ADR-0004 and ADR-0013 ("cover everything IVG can reach"); upkeep after ordinary node deletes stays the caller's (`bm25_insert`/`bm25_delete`, USER_GUIDE). A replacing restore has the same gap ([bug-plt-024](#bug-plt-024)). Governing statements: [search.erasure.indexes](../ontology/features/search.g5.md#search.erasure.indexes), [erasure.scope](../ontology/features/erasure.g5.md#erasure.scope), [search.erasure](../ontology/features/search.g5.md#search.erasure).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-cyp-001"></a>
### A caller with Cypher read access can forge a CRC-32 collision so that another shape's queries run its compiled code

Severity: High · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Proved on the model (collisions exist by `lemma_crc_collision_exists`); not probed natively because forcing a collision of real shapes needs a test hook or a crafted shape. Severity is lowered one level from Critical (an integrity breach other users cannot see) for the unconfirmed trigger.

Found by: [witness_collision_swaps_the_class_mid_run and witness_collision_leaves_another_shapes_code_under_an_ok_entry](results/platform/20261114T002651Z-prove/receipt.json) in [platform.rs](models/platform/platform.rs) (B-platform P1, W-O2a, W-O2b); A-cypher F2; review R3-platform R1-3, whose scratch check Adv-2 (`$RUN_DIR/agents/R3-platform/adv/adv2_platform_pshape*.log`) shows that requiring the entry's shape in `Build` closes W-O2b but not W-O2a, and that only unique class names remove the dependency on P-NO-COLLISION.

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none

Expected: a compiled class answers exactly as the interpreter does, and a stale entry is never run (ADR-0014:16-23; spec 257 US1).

Observed: the class name is `IVGC.P<$ZCRC(shape,7)>` (`Gen.cls:69, 183`). `For` detects a colliding shape by its stored shape (`:71`) and rebuilds the same class name for the new shape (`:80-101, 183-207`); `Build` checks the lines' digest but not that the entry's shape is the one the lines were written for (`:177-207`); `RunA` checks the entry once per run (`Exec.cls:158`) and calls `Walk1` per anchor (`:199, 258`). W-O2b needs no run overlap: two first runs of colliding shapes in job mode leave b's entry marked ok over a's code until a deploy or stamp change.

Consequence: wrong Cypher answers for every later run of the victim shape, until a deploy or stamp change. Accidental collisions are rare (about 1.2×10⁻⁴ for 10³ distinct shapes between deploys, 1.2% for 10⁴, mostly as recompile thrash), but adversarially the attack is practical: CRC-32 is affine, four free bytes in a label or property name hit any target, the shape text can be reproduced from the open-source planner, and the attacker can run both shapes until the W-O2b ordering lands. Reads write compiled plans, so this needs only Cypher read access through a server whose IRIS login can write `^IVG.CypherCompiled`, including an `IVG_READ_ONLY` server on the default `_SYSTEM` login. `query.compiled.integrity` and `query.compiled.never-stale` hold only under P-NO-COLLISION, which nothing establishes.

Repair proposal (not implemented): [simp-cyp-001](design_simplification.md#simp-cyp-001). Governing statements: [query.compiled.integrity](../ontology/features/cypher.g5.md#query.compiled.integrity), [query.compiled.never-stale](../ontology/features/cypher.g5.md#query.compiled.never-stale), [query.compiled.equal-answers](../ontology/features/cypher.g5.md#query.compiled.equal-answers).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-0606"></a>
### Erasure leaves IVF, tree and PLAID indexes holding an erased graph's ids and vectors

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [06.json](../../experiment/playbook-completion/findings/audit/06.json) (live `breadth-a-live-06-vectors`; mc `breadth-a-mc-vec_ivf-as-built`; mc `breadth-a-mc-vec_ivf-reviewed`; control `breadth-a-control-vec_ivf`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-06-vectors`

- Expected: HD-0601 (assumption): retained vector-index contents are observable after erasure unless purged; graph-owned indexes must be invalidated or deleted. docs/migration/v4.0.0.md:742-750 names IVF a gap.
- Observed at the pin: IVF still answers 3 erased ids
- Source severity S1, confidence high; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Prune or invalidate graph-owned indexes in the erase; record the graph with the index.
- Reviewed-design control: `playbook-proofs-d1b` `control_f0606_erase_keeps_ivf` fails where expected in this run ([receipt](results/playbook-proofs-d1b/20261115T035745Z-control_f0606_erase_keeps_ivf/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1b/20261115T035711Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-0702"></a>
### Erasure leaves BM25 indexes holding an erased graph's terms and node ids

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [07.json](../../experiment/playbook-completion/findings/audit/07.json) (live `b-07-f0702-f0703`; inspected `iris_src/src/Graph/KG/Eraser.cls:138-147`; inspected `iris_src/src/Graph/KG/GraphStores.cls:26-133`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-07-f0702-f0703`

- Expected: CONTEXT.md:198-208 (erasure removes content from every store that holds it); ADR-0004; Graph.KG.GraphStores comment 'no answer outlives erased content' (iris_src/src/Graph/KG/GraphStores.cls:112-115); TXT-I8.
- Observed at the pin: Live (b-07-f0702-f0703): after erase_graph('b07g2') (0 node rows left; journal footprint ^KG, ^NKG, docs, nodes, rdf_labels, rdf_props, no ^BM25Idx), bm25_search on the index built for b07g2 still answers both erased node ids with their scores and the term stays in df; Info unchanged.
- Source severity S1, confidence high; module 07; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): List ^BM25Idx in GraphStores.Inventory scoped by its recorded graph and drop or prune every index built for the erased graph inside the erase (decisions.md HD-0601 style ownership for graph-owned derived stores).
- Reviewed-design control: `playbook-proofs-d1d` `control_f0702_erase_keeps_index` fails where expected in this run ([receipt](results/playbook-proofs-d1d/20261115T035647Z-control_f0702_erase_keeps_index/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-0705"></a>
### An index with no recorded graph is read as the default graph's own index

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [07.json](../../experiment/playbook-completion/findings/audit/07.json) (live `b-07-f0705-f0707`; live `b-07-fp-writers`; mc `m07-leg-as-built-fusion-unknown`; mc `m07-leg-as-built-label`; mc `m07-leg-reviewed`; inspected `iris_src/src/Graph/KG/BM25Index.cls:608-612`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-07-f0705-f0707`, `b-07-fp-writers`, `rx-dec-live-07`

- Expected: TXT-B8.3 (an index whose graph is not known is never taken as the default graph's own index); decisions.md HD-0703 (never consult another graph's index); CONTEXT.md:27-43 (graph isolation).
- Observed at the pin: Live (b-07-f0705-f0707): an index created by bm25_insert has no cfg graph subscript; Info answers graph ''; a fresh engine's _index_graph answers ''; default-graph kg_RRF_FUSE answered node b07_n3, which exists only in graph b07g3; Cypher ivg.bm25.search without USE GRAPH labels its row graph_id ''. Model m07-leg-as-built-fusion-unknown / -label; reviewed passes.
- Source severity S1, confidence high; module 07; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Info answers graph null when the subscript is absent; Insert records the graph (or refuses to create an index); _index_graph treats null as unknown.
- Reviewed-design control: `playbook-proofs-d1d` `control_f0705_absent_graph_is_default` fails where expected in this run ([receipt](results/playbook-proofs-d1d/20261115T035644Z-control_f0705_absent_graph_is_default/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-0707"></a>
### Under USE GRAPH, BM25 calls do not check that the index was built for that graph

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [07.json](../../experiment/playbook-completion/findings/audit/07.json) (live `b-07-f0705-f0707`; mc `m07-leg-as-built-scope`; mc `m07-leg-reviewed`; mc `m07-leg-control-no-scope-check`; inspected `iris_vector_graph/cypher/translator.py:3133-3134`; inspected `iris_vector_graph/cypher/translator.py:3283-3292`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-07-f0705-f0707`

- Expected: TXT-I7 (with a graph in scope, BM25 calls answer only from an index built for that graph); CONTEXT.md:27-43; HD-0703.
- Observed at the pin: Live (b-07-f0705-f0707): USE GRAPH 'b07g1' CALL ivg.bm25.search('b07g2idx','pineapple',5) answered b07g2's node b07_g2a (the generated SQL has no graph check on the index; labels/props joined for b07g1 come back empty). ivg.retrieve could not be run live (no embedder configured: blocked-access for that arm). Model m07-leg-as-built-scope; reviewed passes; control m07-leg-control-no-scope-check caught.
- Source severity S1, confidence high; module 07; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Compare the index's recorded graph with the graph context and refuse a mismatch or an unknown graph, in ivg.bm25.search and ivg.retrieve.
- Reviewed-design control: `playbook-proofs-d1d` `control_f0707_no_scope_check` fails where expected in this run ([receipt](results/playbook-proofs-d1d/20261115T035645Z-control_f0707_no_scope_check/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-0711"></a>
### TextSearchEngine answers across graphs and cannot reach iFind

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [07.json](../../experiment/playbook-completion/findings/audit/07.json) (live `b-07-f0711`; run `b-07-unit`; inspected `iris_vector_graph/text_search.py:31-256`; inspected `iris_vector_graph/__init__.py:93-125`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-07-f0711`

- Expected: TXT-B19.1 (its searches answer from one graph only); CONTEXT.md:27-43; HD-0705 assumption (exported helpers are compatibility surfaces whose scope must be qualified).
- Observed at the pin: Live (b-07-f0711): extract_entity_names and search_with_context returned nodes of graphs b07g1 and b07g2 together; search_documents raised SQLCODE -30 on SQLUSER.DOCS (unqualified table) in both the %FIND path and its LIKE fallback and answered []. tests/unit/test_ifind_and_fusion_sql.py (run b-07-unit) documents %FIND(col, ?) as not IRIS syntax.
- Source severity S1, confidence high; module 07; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Per HD-0705: add a graph argument and predicate to every query, use %ID %FIND search_index(...) on the schema-qualified docs table, or deprecate the export.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-0802"></a>
### Text shortcuts answer by substring and ignore USE GRAPH

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0802`; mc `m08-scope-as-built-shortcut`; mc `m08-scope-reviewed`; inspected `iris_vector_graph/_engine/query.py:1807-1856`; live `b-08-live-f0802-rerun`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0802`, `b-08-live-f0802-rerun`

- Expected: A scoped query answers only from its graph (CONTEXT.md:27-43; USER_GUIDE.md:401-404); a query is answered by the translator unless it is exactly a tool's canned text.
- Observed at the pin: Live AUDITB: `USE GRAPH 'b08gA' MATCH (n) RETURN count(*) AS c UNION ALL MATCH ()-[r]->() RETURN count(*) AS c` answered column `result` with nodes 7 / relationships 4 (whole namespace) where b08gA holds 3 / 2; a near-miss `RETURN DISTINCT n.name AS entity_name UNION ALL ...` under USE GRAPH answered canned (entity, id) rows including b08_leak (graph b08gB) and b08_s/b08_t (default graph). Model m08-scope-as-built-shortcut violates SYS-I2; reviewed passes.
- Source severity S1, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Match the exact Neo4j Browser / Bloom texts (or compare the parsed AST), honour USE GRAPH in each shortcut, and test that a near-miss query is answered by the translator.
- Reviewed-design control: `playbook-proofs-d1d` `control_f0802_shortcut_unscoped` fails where expected in this run ([receipt](results/playbook-proofs-d1d/20261115T035657Z-control_f0802_shortcut_unscoped/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-0814"></a>
### AQL text values are pasted into the Cypher text, and execute_aql ignores read-only

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0814`; mc `m08-readonly-as-built`; mc `m08-readonly-reviewed`; inspected `iris_vector_graph/cypher/aql/translator.py:50-58`; inspected `iris_vector_graph/cypher/aql/translator.py:154-168`; inspected `iris_vector_graph/_engine/query.py:1730-1745`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0814`, `b-08-live-f0814-rerun`

- Expected: CYP-I9.4: a name written in a query reaches SQL only as a bound value or a checked name; CYP-I8.6 / read-only is available on the query entry points.
- Observed at the pin: Live: honest FILTER v.name == 'nomatch' -> 0 rows; hostile literal 'nomatch" OR true OR v.name = "' -> 2 rows (filter rewritten). A collection name `B08R*1..1]->(v) SET v.pwn = 1 WITH v AS v MATCH (start)-[:B08R` made execute_aql write rdf_props rows on b08_m (graph b08gA) and b08_leak (graph b08gB) (journal: sql:Graph_KG.rdf_props). execute_aql has no read_only parameter. Model m08-readonly-as-built violates CYP-I8.6; reviewed passes.
- Source severity S1, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Send every AQL literal as a query parameter, validate collection names as identifiers, add read_only to execute_aql (judge the translated text with writes_cypher), unit tests with hostile literals.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-0815"></a>
### A dotted function name pastes raw text into the SQL

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0815`; mc `m08-scope-as-built-dotted`; mc `m08-readonly-as-built`; run `b-08-run-unit`; inspected `iris_vector_graph/cypher/parser.py:1627-1640`; inspected `iris_vector_graph/cypher/translator.py:29563-29578`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0815`, `b-08-live-f0815-rerun`

- Expected: CYP-I9.4; CYP-I8.6 (read-only changes nothing); USE GRAPH scopes the answer (USER_GUIDE.md:401-404).
- Observed at the pin: Live with read_only=True: under USE GRAPH 'b08gA', `` RETURN `(SELECT LIST(NODE_ID) FROM GRAPH_KG.NODES WHERE %SQLUPPER(GRAPH_ID) = %SQLUPPER('B08GB')) AS LEAK --`.f(1) AS v `` answered 'b08_leak,b08_m' (graph b08gB's ids); a dotted name read %DICTIONARY.COMPILEDCLASS (5734 rows counted); `GRAPH_KG.TXN_BEGIN(0)` raised the connection's $TLEVEL 0 -> 1 (restored with Txn_Undo). Journal: no data write. Generated SQL: `SELECT (...) AS LEAK --.F(1) AS v`. tests/unit/test_cypher_posos_bugs.py:157 asserts the pass-through (b-08-run-unit). Models m08-scope-as-built-dotted and m08-readonly-as-built vi…
- Source severity S1, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Refuse back-quoted or non-identifier namespaces in function calls, allow-list qualified functions (or gate them behind a setting), refuse them in read-only mode; unit tests with hostile names.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-0816"></a>
### Schema procedures ignore USE GRAPH

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0816`; mc `m08-scope-as-built-dblabels`; inspected `iris_vector_graph/engine.py:1313-1323`; inspected `iris_vector_graph/engine.py:1702-1714`; live `b-08-live-f0816-rerun`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0816`, `b-08-live-f0816-rerun`

- Expected: USER_GUIDE.md:401-404: USE GRAPH scopes a query to one graph.
- Observed at the pin: Live: under USE GRAPH 'b08gA' (labels B08L, types B08R/B08S), CALL db.labels() listed B08B (only in b08gB) and default-graph labels; db.relationshipTypes() listed B08Q and B08T (not in b08gA).
- Source severity S1, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Give the schema handlers a graph parameter (or refuse them under USE GRAPH), with a unit test.
- Reviewed-design control: `playbook-proofs-d1d` `control_f0816_dblabels_unscoped` fails where expected in this run ([receipt](results/playbook-proofs-d1d/20261115T035658Z-control_f0816_dblabels_unscoped/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-0818"></a>
### A variable-length walk in an all-graphs read can cross graphs

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0818`; mc `m08-scope-as-built-vlp`; mc `m08-scope-reviewed`; mc `m08-scope-control-vlp-unscoped`; inspected `iris_vector_graph/cypher/translator.py:15404-15431`; live `b-08-live-f0818-rerun`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0818`, `b-08-live-f0818-rerun`

- Expected: CYP-I5.6 / CONTEXT.md:38-43: a variable-length walk in an all-graphs read stays in the graph of its start node.
- Observed at the pin: Live: with b08gA: b08_x-[:B08R]->b08_m and b08gB: b08_m-[:B08R]->b08_leak, `MATCH (a:B08L {id:'b08_x'}) WITH a MATCH (a)-[:B08R*1..2]->(b) RETURN b.id` answered [b08_leak, b08_m, b08_m] (SQL: CY_VLP_PATHS(Stage1.a, ..., 1, '-', ...): gall = 1); the plain-alias form answered [b08_m]. Model m08-scope-as-built-vlp violates SYS-I2; reviewed passes; control m08-scope-control-vlp-unscoped caught.
- Source severity S1, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Carry the start's graph (Stage1.__g_a is already projected) into CY_VLP_* for every start shape, or refuse the shape; e2e test with a WITH-carried start in two graphs.
- Reviewed-design control: `playbook-proofs-d1d` `control_f0818_vlp_crosses_graphs` fails where expected in this run ([receipt](results/playbook-proofs-d1d/20261115T035700Z-control_f0818_vlp_crosses_graphs/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-0820"></a>
### kg_GRAPH_PATH reads every graph

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0820`; mc `m08-scope-as-built-graphpath`; inspected `iris_vector_graph/_engine/algorithms.py:679-697`; inspected `iris_vector_graph/operators.py:46-49`; live `b-08-live-f0820-rerun`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0820`, `b-08-live-f0820-rerun`

- Expected: USER_GUIDE.md:462-464: a Python read with no graph= means the default graph, never every graph (HD-0201 working assumption: omission selects the default graph).
- Observed at the pin: Live: engine.kg_GRAPH_PATH('b08_x','B08R','B08S') returned the path b08_x->b08_m->b08_n, which exists only in graph b08gA (no default-graph edge from b08_x).
- Source severity S1, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Add graph= (default: the default graph) and prefix USE GRAPH, with a unit test.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-1002"></a>
### random_walk needs the Arno library for an ObjectScript walk, and walks every graph's edges

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [10.json](../../experiment/playbook-completion/findings/audit/10.json) (live `b-10-live-nkg`; mc `m10-routes-as-built-walk-empty`; mc `m10-nkg-as-built-scope`; mc `m10-nkg-reviewed`; mc `m10-nkg-control-walk-merged`; inspected `iris_vector_graph/_engine/algorithms.py:658-678`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-10-live-nkg`

- Expected: ALG-I1 / CONTEXT.md:261-264 (IVG answers the same without the library, only slower); ALG-I3 and SYS-I2; decisions.md HD-1001 working answer (assumption): a declared graph scope and an observable unavailable result, never an empty graph inferred from missing acceleration.
- Observed at the pin: Live (b-10-live-nkg): engine.random_walk('b10_a') answered [] while b10_a has out-edges and the Arno library is absent (engine._detect_arno() False). With named graph b10g1 holding b10_a -> b10_n beside the default graph's b10_a -> b10_b and ^NKG synced, the walk the engine would call, Graph.KG.NKGAccel.RandomWalkJson (pure ObjectScript), stepped first to ['b10_b', 'b10_n']: the named graph's node b10_n from a default-graph walk. The ^NKG procedure ivg.betweenness refused the same namespace (ALG-B7 holds live). Models: m10-routes-as-built-walk-empty and m10-nkg-as-built-scope reproduce both p…
- Source severity S1, confidence high; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Decide HD-1001; at minimum walk the default graph's ^KG in ObjectScript whatever the library state (or refuse with an explicit unavailable error), call EnsureNKG and refuse when a named graph has edges if ^NKG is kept; a live test with two graphs sharing a node id.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-1008"></a>
### Variable-length expansion's every-graph mode walks across graphs

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [10.json](../../experiment/playbook-completion/findings/audit/10.json) (live `b-10-live-scope`; live `b-08-live-f0818`; mc `m10-walk-as-built-one-graph`; mc `m10-walk-reviewed`; mc `m10-walk-control-reset-at-shared`; inspected `iris_src/src/Graph/KG/VarLength.cls:44-51`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-10-live-scope`, `b-08-live-f0818`

- Expected: CONTEXT.md:38-43 (an edge meets only nodes of its own graph); ALG-I2.
- Observed at the pin: Live (b-10-live-scope): default graph b10_s -> b10_k, named graph b10g1 b10_k -> b10_m (shared id b10_k). Graph.KG.VarLength.Ends('b10_s', '', 'out', 2, 2, pAll=1) answered [{'t': 'b10_m', 'l': 2}]; with pAll=0 (default graph) []. The translator side (Cypher with gall = 1) is module 08's F-0818, reproduced live there (b-08-live-f0818). Model m10-walk-as-built-one-graph reproduces it; m10-walk-reviewed passes.
- Source severity S1, confidence high; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Walk each graph separately in the every-graph mode (fix the graph at the first hop); a live test with a parameter source in two graphs.
- Reviewed-design control: `playbook-proofs-d1e` `control_f1008_every_graph_mixed` fails where expected in this run ([receipt](results/playbook-proofs-d1e/20261115T035526Z-control_f1008_every_graph_mixed/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1e/20261115T035416Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-1101"></a>
### A replayed commit writes its post-commit properties again

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [11.json](../../experiment/playbook-completion/findings/audit/11.json) (live `b-11-live-findings`; live `b-11-live-footprints-1`; mc `m11-retry-as-built-pcp`; mc `m11-retry-as-built-governed`; mc `m11-retry-reviewed`; live `ib-HD1105-replay-reapplies`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-11-live-findings`, `b-11-live-footprints-1`, `ib-HD1105-replay-reapplies`, `live-native-rerun-1314`

- Expected: A replayed commit applies nothing: specs/213-graph-revision-ledger/contracts/ledger-api.md:26 ('original outcome with replayed=True'), tests/integration/test_ledger_us04_idempotency.py:52-62, LED-B10.5; decisions.md HD-1105 (supported: post-commit properties are a separate direct write and retries must be idempotent) and HD-1305 (supported: a retry must not recreate an erased tenant's properties).
- Observed at the pin: Live AUDITB (b-11-live-findings): commit with key b11-k1 created b11_p1 and post-commit property audit=pcp-v1; a governed set_property wrote governed-v2 (seq 7); the retry with the same key answered replayed=True (seq 6) and post_commit_applied=True and audit read pcp-v1 again; a same-key retry carrying different post-commit properties (fingerprint excludes them, changeset.py:365-385) was replayed and wrote pcp-OTHER; verify() diverges on b11_p1.audit. Journal of the retry: Bump's ledger_stats transaction, then a separate rdf_props DELETE+INSERT transaction (b-11-live-footprints-1 capture com…
- Source severity S1, confidence high; module 11; governing page here: `ledger.`.
- Remedy proposed by the playbook arm (not implemented): Skip post-commit properties when the answer is replayed (or record them in the revision, HD-1105 option a), and include them in the fingerprint so a retry with other properties is a key conflict; a live test retrying after a later set_prop and after an erasure.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-1114"></a>
### Erasure changes the statement maps without the head lock

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [11.json](../../experiment/playbook-completion/findings/audit/11.json) (live `live-f1201-reproduced`; live `b-11-live-footprints-2`; inspected `iris_src/src/Graph/KG/Eraser.cls:665-678`; inspected `iris_src/src/Graph/KG/Eraser.cls:809-811`; inspected `iris_src/src/Graph/KG/Eraser.cls:1117-1145`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `live-f1201-reproduced`, `b-11-live-footprints-2`

- Expected: LED-B4.14.4 (only a process that holds the head lock changes the statement id maps); SYS-I1 one owner per fact; ADR-0004.
- Observed at the pin: Source at the pin: Graph.KG.Eraser takes no Lock and kills ^IVG.Ledger('stmt')/('tuple') entries in its own transaction (Eraser.cls:665-678, :809-811, EraseLedgerFor :1117-1145 dirty-reads every statement entry). Live: this lane's journal shows the same writes reached from engine.bulk_delete_adjacency -> Eraser.EraseEdges (^IVG.Ledger stmt/tuple killed in the eraser's transaction, no head lock; b-11-live-footprints-2). The interleaving with a commit was reproduced by the orchestrator (run live-f1201-reproduced: the committer's SET ^IVG.Ledger('stmt',4001)/tuple followed by the eraser's KILL o…
- Source severity S1, confidence high; module 11; governing page here: `ledger.`.
- Remedy proposed by the playbook arm (not implemented): Take ^IVG.Ledger('head') in the eraser's transaction when it touches the statement maps (or document that erasure must not run beside commits); a live commit-into-erased-graph test (owned by the orchestrator's erasure module).
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-1302"></a>
### Redaction can tombstone history of content a concurrent commit made live (unlocked start, late marker)

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [13.json](../../experiment/playbook-completion/findings/audit/13.json) (original `live:native-commit_in_unmarked_window`; original `mc:redaction-as-built-live`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM)

- Expected: RED-B1.1 / ADR-0013: a redaction never tombstones live content; the marker refuses commits into the target from the start.
- Observed at the pin: Original live reproduction on the same pin (scenario commit_in_unmarked_window, which compiles the original probe class and is not rerun here) and as-built model trace (3 steps); the opening checks run without the head lock and the marker is set at the first tombstone (LedgerRedact.cls:202-211, 322-324). Fresh model and proof evidence: core lanes (pending).
- Source severity S1, confidence high; module 13; governing page here: `redaction.`.
- Remedy proposed by the playbook arm (not implemented): Check liveness and set the marker in one transaction under the head lock (HD-1301 working answer).
- Reviewed-design control: `playbook-proofs-d9c` `control_f1302_unlocked_start` fails where expected in this run ([receipt](results/playbook-proofs-d9c/20261115T040837Z-control_f1302_unlocked_start/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d9c/20261115T041012Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-1305"></a>
### A graph-per-tenant redaction with unprefixed ids reports success while the tenant's node history remains

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [13.json](../../experiment/playbook-completion/findings/audit/13.json) (run `live-native-rerun-1314`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM)

- Expected: Spec 256: tenant erasure removes the tenant's content from history (RED-B1.2, SC-001).
- Observed at the pin: Fresh rerun: redact(gTenantA) completes; tenant A's node ids and property values stay in the ledger (node records are graph-blind); verify diverges.
- Source severity S1, confidence high; module 13; governing page here: `redaction.`.
- Remedy proposed by the playbook arm (not implemented): Return an explicit incomplete/refused outcome when node history cannot be attributed (HD-1304 working answer), or record each node record's graph.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-1306"></a>
### A retried commit re-applies post-commit properties and revives erased content

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [13.json](../../experiment/playbook-completion/findings/audit/13.json) (run `live-native-rerun-1314`; run `ib-HD1305-retry-revives`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM)

- Expected: HD-1305 (supported): a retry must not recreate an erased tenant's properties; idempotency contract.
- Observed at the pin: Fresh rerun: the replay of a retried commit re-applies the post-commit property; an erased node's property is live again. Intent lane B additionally observed the property write landing in a target while its redaction marker was set (RED-B5 bypass).
- Source severity S1, confidence high; module 13; governing page here: `redaction.`.
- Remedy proposed by the playbook arm (not implemented): Do not reapply post-commit properties on an idempotent replay (or record their completion atomically with the revision) and route them through the marker check.
- Reviewed-design control: `playbook-proofs-d9c` `control_f1306_replay_direct_sql` fails where expected in this run ([receipt](results/playbook-proofs-d9c/20261115T040845Z-control_f1306_replay_direct_sql/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d9c/20261115T041012Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Related: q-010.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-1402"></a>
### A reader can return a partially redacted view

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [14.json](../../experiment/playbook-completion/findings/audit/14.json) (run `live-native-rerun-1314`; run `ib-HD1401-reader-full-race`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM)

- Expected: RPL-I1 / HD-1401: a reader returns a consistent pre- or post-redaction view or the documented in-progress result.
- Observed at the pin: Fresh rerun: the reader's view shows tenant A's graph half redacted. Intent lane B: a whole redaction can finish between two pages of one reconstruct() call with the marker absent before and after, so the post-read marker re-check proposed in the original review cannot detect it (an epoch check would).
- Source severity S1, confidence high; module 14; governing page here: `ledger.readers`.
- Remedy proposed by the playbook arm (not implemented): Validate a reader's whole read against a redaction epoch (counter bumped by every batch and Final) and retry or refuse on change.
- Reviewed-design control: `playbook-proofs-d9c` `control_f1402_reader_no_recheck` fails where expected in this run ([receipt](results/playbook-proofs-d9c/20261115T040858Z-control_f1402_reader_no_recheck/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d9c/20261115T041012Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-1502"></a>
### A reifier node always lands in the default graph, and erasing the edge's graph leaves it (with its properties) live

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [15.json](../../experiment/playbook-completion/findings/audit/15.json) (live `c15-live-reify`; inspected `iris_vector_graph/_engine/schema.py:3296-3322`; inspected `iris_src/src/Graph/KG/Eraser.cls:185-189`; inspected `iris_src/src/Graph/KG/FHIRGraph.cls:2585-2599`; inspected `iris_vector_graph/_engine/nodes_edges.py:2176-2199`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c15-live-reify`

- Expected: Erasure removes a graph's content from every store (SYS-D26, ADR-0004); content of one graph never shows up in an answer about another graph (SYS-I2); INT-E1.6/INT-E1.7 (a reifier lives with its edge and goes with its graph).
- Observed at the pin: Live (c15-live-reify): reify_edge on an edge of named graph c15g1 wrote the reifier node, its label 'Reification' and its properties with graph_id '' (default graph) in one transaction; the edge is in c15g1. erase_graph('c15g1') deleted the edge and its rdf_reifications row (journal: one transaction) but the reifier node, label and properties {'source': 'tenant-c15g1-secret', 'confidence': 0.9} stayed in the default graph and were returned by get_node('c15:reif1') and by a default-graph Cypher MATCH. delete_node removes the reifiers of a node's edges (INT-E1.9), so the two deletion paths disa…
- Source severity S1, confidence high; module 15; governing page here: `fhir.`.
- Remedy proposed by the playbook arm (not implemented): Create the reifier in the edge's graph (read graph_id with edge_id) and have every edge-deleting path (Eraser.EraseGraph/EraseNodes, FHIR sync DeleteEdge, direct and Cypher edge deletes) delete the reifier nodes of the edges it removes, in the same transaction; a live test that reifies an edge in G, erases G and finds no reifier in any graph.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-1503"></a>
### delete_reification deletes any id's node, labels and properties in every graph without checking it is a reifier

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [15.json](../../experiment/playbook-completion/findings/audit/15.json) (live `c15-live-delreif2`; live `c15-live-delreif`; inspected `iris_vector_graph/_engine/schema.py:3361-3397`; inspected `iris_vector_graph/schema.py:42-43`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c15-live-delreif2`, `c15-live-delreif`

- Expected: SYS-I2 (graph isolation) and INT-E1.10 ('deleting a reifier should touch only that reifier node, and leave no edge without its node'); the docstring (schema.py:3364-3368) admits 'Not graph-scoped'.
- Observed at the pin: Live (c15-live-delreif2): delete_reification('c15:z') on an id that is no reifier (0 rdf_reifications rows) and has no edges deleted its node row, labels, properties and ^KG('label') index entries in BOTH named graph c15g2b and the default graph, in one transaction, and returned True. Sub-claim refuted at the pin (c15-live-delreif): for an id WITH edges the foreign key fk_edges_source (schema.py:42) refuses the node delete (SQLCODE -124) and the whole transaction rolls back, so no edge is left without its node row and ^KG is unchanged; the call raises GraphWriteError naming the FK.
- Source severity S1, confidence high; module 15; governing page here: `fhir.`.
- Remedy proposed by the playbook arm (not implemented): Refuse an id with no rdf_reifications row; scope the deletes to the reifier's graph (the default graph at the pin, or the edge's graph once F-1502 is fixed).
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-1603"></a>
### The generated GraphQL server mixes graphs in one answer

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [16.json](../../experiment/playbook-completion/findings/audit/16.json) (live `c16-s3-graphql-sample-api`; inspected `iris_vector_graph/gql/resolvers.py:32-133`; inspected `iris_vector_graph/gql/engine.py:32-57`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c16-s3-graphql-sample-api`

- Expected: SYS-I2 / API-B10.3 / API-B15.8: an answer about one graph holds no content of another; a read with no graph reads the default graph (HD-0201).
- Observed at the pin: Live (c16-s3-graphql-sample-api, create_app over AUDITC): node(id:'c16:x') of the default graph listed outgoing [C16_DEF_EDGE->c16:z, C16_G1_EDGE->c16:y]; the second edge lives only in graph c16g1. nodes(label:'C16Q', limit:3) answered [] although default-graph node c16:qz has the label: the page was cut from all graphs' ids (three c16g1-only nodes) and then read in the default graph. Source: iris_vector_graph/gql/resolvers.py:32-46, :90-133 (no graph_id), gql/engine.py:32-57 (field discovery joins rdf_props to rdf_labels on s only).
- Source severity S1, confidence high; module 16; governing page here: `access.`.
- Remedy proposed by the playbook arm (not implemented): Filter every statement by graph_id (default graph unless a graph argument names one), as api/gql/core/resolvers.py does since spec 230; e2e test with one id in two graphs.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-1604"></a>
### The sample API's biomedical fields and its update mutation ignore graphs

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [16.json](../../experiment/playbook-completion/findings/audit/16.json) (live `c16-s3-graphql-sample-api`; live `c16-s8-followup`; inspected `api/gql/loaders.py:19-272`; inspected `examples/domains/biomedical/resolver.py:240-278`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c16-s3-graphql-sample-api`, `c16-s8-followup`

- Expected: API-B6.6/B6.7/B15.8: biomedical fields read one graph; updateProtein changes only the named node in one graph (CONTEXT.md:44-48).
- Observed at the pin: Live (c16-s3-graphql-sample-api): protein(id:'c16:p1') answered labels [Protein, Protein, C16G1Label], name 'p-g1' and interactsWith [c16:p2] — the c16g1 copy's label, property and edge merged into the default-graph protein. updateProtein(name:'p-updated') rewrote the name property in BOTH graphs (props_after shows c16g1 name 'p-updated'). Journal (c16-s8-followup): the mutation wrote ['sql:Graph_KG.rdf_props'] on IRIS process(es) ['10556'], outermost commits {'10556': 1}, outside any transaction: []; cross-graph rewrite reproduced again: True. Source: api/gql/loaders.py:19-45, :183-272 (WHER…
- Source severity S1, confidence high; module 16; governing page here: `access.`.
- Remedy proposed by the playbook arm (not implemented): Add graph_id = ? (default graph) to every loader statement and route the update through the engine with graph=; e2e test with one id in two graphs.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-1701"></a>
### The SQL adapter's unscoped node and label reads merge graphs

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [17.json](../../experiment/playbook-completion/findings/audit/17.json) (live `c17-live-engine`; inspected `iris_vector_graph/stores/iris_sql_store.py:1116-1210`; inspected `iris_vector_graph/_engine/query.py:245-275`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c17-live-engine`

- Expected: A node's labels and properties are its own graph's (CONTEXT.md 'All-graphs read', decided 2026-10-20); the engine's get_nodes is graph-scoped since spec 227 (iris_vector_graph/_engine/nodes_edges.py:621-636); SYS-I2.
- Observed at the pin: Live (c17-live-engine, AUDITC): node c17:x labelled C17A in c17g1 and unlabelled in c17g2. IRISGraphStore.get_nodes(['c17:x']) with no graph answered [['c17:x', '["C17A"]']]; get_node_labels answered [['c17:x', '["C17A"]']]. Cypher under USE GRAPH 'c17g2': start-label variable-length {'error': None, 'metadata': 'QueryMetadata(estimated_rows=None, index_usage=[], optimization_applied=[], complexity_score=None, warnings=[])', 'rows': [], 'sql': "SELECT Graph_KG.CY_TYPED(%EXACT(p4.val)) AS t_id\nFROM Graph_KG.nodes n0\nJOIN Graph_KG.rdf_labels l1 ON l1.s = n0.node_id AND l1.label = ? AND COALESC…
- Source severity S1, confidence medium; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): Give get_nodes/get_node_labels/query_nodes a graph argument and pass the query's graph from every Cypher caller; a live test with one id in two graphs.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-1801"></a>
### A replacing restore lays the archive's ledger over the live one

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [18.json](../../experiment/playbook-completion/findings/audit/18.json) (live `c18-live-ledger-overlay`; mc `cmc-restore-as-built-history`; mc `cmc-restore-as-built-grows`; mc `cmc-restore-as-built-commit`; mc `cmc-restore-as-built-redaction`; mc `cmc-restore-reviewed`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c18-live-ledger-overlay`

- Expected: spec 213 FR-043 (the ledger survives a snapshot); SNP-I3.6 (after a restore the ledger holds one history whose records and head agree); SYS-I5 (the ledger only grows); ADR-0013 (redacted content leaves history); decisions.md HD-1801 (treat the archive's history as a unit; refuse divergent histories before mutation; keep current redaction obligations).
- Observed at the pin: Live (c18-live-ledger-overlay, AUDITC): ledger enabled, commit seq 2 (c18:L1), save, commit seq 3 (c18:L2, retry key c18-k2), replacing restore of the older archive: meta after restore {'head_id': 'ebae4dc3dfb811f1b3edf277e9aab529', 'head_seq': 2, 'max_ops': 50000, 'ok': True, 'recon_bound': 250000, 'state': 'enabled', 'strict': False}; record (3,1) still present: [1]; LedgerRevision seqs [1, 2, 3]; idem binding c18-k2 = '\x03\x04\x03B\x01de63550c92cde590c0b3685718c468739957a52a0fc9cc4ac0b69b089ee8c653'; the next commit -> {'error': 'LedgerInconsistencyError: revision row save failed: ERROR #…
- Source severity S1, confidence high; module 18; governing page here: `install.snapshot`.
- Remedy proposed by the playbook arm (not implemented): Per HD-1801: refuse a restore whose archive history does not extend the live one, before erase_all; otherwise replace the ledger as a unit (kill ^IVG.Ledger and the ledger storage first) and re-apply live redactions (tombstones, redactedRev, idemRedacted) to the archived records.
- Reviewed-design control: `playbook-proofs-d1b` `control_f1801_no_prefix_check` fails where expected in this run ([receipt](results/playbook-proofs-d1b/20261115T035736Z-control_f1801_no_prefix_check/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1b/20261115T035711Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Related: q-plt-004.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-C1250"></a>
### An rdf_edges row a %NOINDEX bulk load wrote survives delete_nodes_by_prefix of both its endpoints and EraseAll+PurgeAll until the indices are rebuilt; its endpoint nodes are deleted under it

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-writesets.json](../../experiment/playbook-completion/findings/audit/zz-writesets.json) (live `ws-live-noindex-erase`; live `ws-live-ins-bulkloader_load_edges`; live `ws-live-ins-import_rdf`; inspected `iris_src/src/Graph/KG/Eraser.cls:777-779`; inspected `iris_vector_graph/bulk_loader.py:380-400`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `ws-live-noindex-erase`, `ws-live-ins-bulkloader_load_edges`, `ws-live-ins-import_rdf`

- Expected: docs/adr/0004-erasure-removes-content-not-history.md (erasure removes the content); iris_src/src/Graph/KG/Eraser.cls:699-709 (EraseAll: 'Remove every graph's content from every store'); iris_vector_graph/schema.py:34-44 (fk_edges_source / fk_edges_dest: an edge row needs its endpoint node rows).
- Observed at the pin: Live in AUDITB (ws-live-noindex-erase): BulkLoader.load_edges with its default use_noindex=True registered 2 endpoint nodes (indexed) and wrote the edge row with INSERT %NOINDEX %NOCHECK (bulk_loader.py:456-460): indexed counts saw nodes 2, edges 0; a %IGNOREINDEX full scan saw nodes 2, edges 1. engine.delete_nodes_by_prefix('wse|') answered 2 and deleted both node rows; the edge row stayed (the foreign keys did not refuse deleting nodes the unindexed edge references). Graph.KG.Eraser.EraseAll answered 0 and Ledger.PurgeAll ran: the full scan still found the row (the only content row left); v…
- Source severity S1, confidence high; module 12; governing page here: `erasure.`.
- Remedy proposed by the playbook arm (not implemented): Have the erasure paths read without the indexes a %NOINDEX load leaves stale (or refuse while an index build is pending), and have the bulk loader rebuild its indices before it returns; an erase that leaves a row of an erased tenant should say so.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-C1306"></a>
### After a 4.5.x upgrade to a non-default IVG Schema, Graph_KG.ledger_revisions keeps the tenant's messages, sources, correlation ids and idempotency keys, which redaction never clears

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [followup.json](../../experiment/playbook-completion/findings/audit/followup.json) (live `fc1306-legacy-ledger-rows`; inspected `iris_vector_graph/_engine/legacy.py:606-646`; inspected `iris_vector_graph/_engine/schema.py:2223-2226`; inspected `iris_vector_graph/_engine/schema.py:2308`; inspected `iris_vector_graph/_engine/class_deploy.py:109-119`; inspected `iris_src/src/Graph/KG/LedgerRedact.cls:351-376`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `fc1306-legacy-ledger-rows`, `o1-fixture-inventory`

- Expected: specs/256-ledger-tenant-redaction/spec.md:142-143 (SC-001: after erase and redaction 'every Graph_KG.ledger_* row finds none of the tenant's ids or values'); spec.md:120-121 (FR-004, Decision 2: a revision's free text is cleared); FR-008 reach statement; docs/adr/0013-redaction-removes-content-from-history.md:47.
- Observed at the pin: Live (run fc1306-legacy-ledger-rows, scratch namespace IVG262FC1306): the pinned fixture's own functions (scripts/fixtures/build_release_namespace.build('v4.5.1', ..., schema_prefix='RAG'), run_ledger_commits) plus v4.5.1's public engine.ledger.commit built a 4.5.1 namespace whose Graph_KG.ledger_revisions held 7 revisions: tenant r114 (seqs 2, 3, 4, 6; seqs 4 and 6 with message, source, correlation_id and idempotency_key) and tenant o114 (seqs 5, 7). The pin's initialize_schema(schema_prefix='RAG') copied them (ledger_history_copied {ledger_revisions: 7, ledger_stats: 1}); verify() equal. Th…
- Source severity S1, confidence high; module 13; governing page here: `redaction.`.
- Remedy proposed by the playbook arm (not implemented): On redaction, also clear (or report) rows of a legacy Graph_KG.ledger_revisions (and ^Graph.KG.LedgerRevisionD) when the IVG Schema is not Graph_KG; or have the upgrade move rather than copy the rows (delete or %NODELDATA plus kill of the legacy storage after the copy is verified); and name any remaining legacy copy in the receipt.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-C1350"></a>
### Redaction batches tombstone the history of content a ledger-bypassing writer made live after the run's entry check

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-writesets.json](../../experiment/playbook-completion/findings/audit/zz-writesets.json) (live `ws-live-ins-store_node`; live `ws-live-ins-store_edge`; live `ws-live-ins-bulk_create_nodes`; live `ws-live-ins-bulk_ingest_edges`; live `ws-live-ins-bulk_create_edges`; live `ws-live-ins-store_write_nodes`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `ws-live-ins-store_node`, `ws-live-ins-store_edge`, `ws-live-ins-bulk_create_nodes`, `ws-live-ins-bulk_ingest_edges`

- Expected: experiment/playbook-uplift/ontology/13-redaction.md:51 (RED-B1.1: redaction never makes a tombstone of the record of live content); specs/256-ledger-tenant-redaction/spec.md:124 (FR-005: redaction MUST refuse while any non-tombstoned live statement or node of the target remains); docs/adr/0013-redaction-removes-content-from-history.md:17 (refused while any row of the target is live); the product's own checks count any content row of the target as live (LedgerRedact.cls:202-211 entry, 409-416 Final 'became live again').
- Observed at the pin: Live in AUDITB, 12 runs, one per writer (ws-live-ins-store_node, -store_edge, -bulk_create_nodes, -bulk_ingest_edges, -bulk_create_edges, -store_write_nodes, -store_write_edges, -create_edge_temporal, -bulk_create_edges_temporal, -reify_edge, -bulkloader_load_edges, -import_rdf). Each: a target tenant with 7 ledger records (2 nodes with label and property, 1 relationship) is erased (0 live rows); a redaction is started while a second connection holds ^IVG.Ledger("head") (as a concurrent ledger commit does), passes its entry liveness check and waits for the lock; the writer, which reads no mar…
- Source severity S1, confidence high; module 13; governing page here: `redaction.`.
- Remedy proposed by the playbook arm (not implemented): Either make every content writer refuse a write into a target while its marker exists (and serialize writers with the run's start, HD-1301's working answer), or have each batch re-check the target's liveness under the head lock before it tombstones and stop (leaving the marker) when the target is live again.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-C1351"></a>
### The redaction's liveness check misses rows a bulk load wrote with %NOINDEX: the redaction completes while the tenant's rows exist, and they reappear at the next index rebuild

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-writesets.json](../../experiment/playbook-completion/findings/audit/zz-writesets.json) (live `ws-live-noindex`; inspected `iris_src/src/Graph/KG/LedgerRedact.cls:149-178`; inspected `iris_vector_graph/bulk_loader.py:252-300`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `ws-live-noindex`

- Expected: specs/256-ledger-tenant-redaction/spec.md:124 (FR-005: refuse while any non-tombstoned live statement or node of the target remains); docs/adr/0013-redaction-removes-content-from-history.md:17 (refused while any row of the target is live); RED-B1.1 (experiment/playbook-uplift/ontology/13-redaction.md:51).
- Observed at the pin: Live in AUDITB (ws-live-noindex): tenant wsni committed through the ledger (3 records) and erased; BulkLoader.load_nodes (default use_noindex=True, INSERT %NOINDEX %NOCHECK, bulk_loader.py:8-11) wrote its node, label and property rows; COUNT(*) queries of LiveRows' shape (%EXACT(id) %STARTSWITH ?, LedgerRedact.cls:149-178) answered 0 while a %IGNOREINDEX full scan found nodes 1, labels 1, props 2; redact(None, prefix='wsni') completed (receipt complete, 3 records tombstoned, marker removed); BulkLoader.rebuild_all_indices then made the rows visible: 4 live rows under tombstoned records, verif…
- Source severity S1, confidence high; module 13; governing page here: `redaction.`.
- Remedy proposed by the playbook arm (not implemented): Count liveness without relying on indexes a %NOINDEX load leaves stale (%IGNOREINDEX on LiveRows' counts, or refuse a redaction while an index build is pending for the content tables), or have the bulk loader rebuild the indices before it returns.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-C1803"></a>
### Graph.KG.Snapshot's unused file helpers read, write and delete server files for any Native API caller

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-versions.json](../../experiment/playbook-completion/findings/audit/zz-versions.json) (live `ver-priv-r2`; live `ver-priv-r1`; live `c18-live-file-helpers`; inspected `iris_src/src/Graph/KG/Snapshot.cls:4-73`; inspected `docs/ADMIN_GUIDE.md:450-473`; inspected `scripts/setup_security.sql:5-7`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `ver-priv-r2`, `ver-priv-r1`, `c18-live-file-helpers`

- Expected: ADMIN_GUIDE.md:450-473 grants the least-privilege reading role %Native_ClassExecution:U; nothing in the product needs server file access through IVG classes (no caller of ReadFileChunk/WriteFileChunk/DeleteDir/ExportGlobals). docs/ADMIN_GUIDE.md:598: 'A read-only role is one whose database resource is R'; :520 'With the database at R it writes nothing'.
- Observed at the pin: Live (c18-live-file-helpers, as _SYSTEM): FileExists('/etc/hostname') = 1, GetFileSize = 33, ReadFileChunk returned 'ivg-playbook-20261113-audit-iris\n'. Source: WriteFileChunk (Snapshot.cls:49-57) writes any path, DeleteDir (:64-68) runs RemoveDirectoryTree on any path, ExportGlobals (:4-22) writes any global to any directory, all as the IRIS server's OS user, with no IVG check. Live as the documented reading role (ver-priv-r1, ver-priv-r2; user IVGAUDIT_RO, database resource at R, %Native_ClassExecution:U): FileExists('/etc/hostname') = 1, GetFileSize = 33, ReadFileChunk returned the host n…
- Source severity S1, confidence high; module 18; governing page here: `install.snapshot`.
- Remedy proposed by the playbook arm (not implemented): Delete the file and global helpers (no product caller), or restrict them to an admin role and an allow-listed folder.
- Recorded in 18.json, zz-versions.json; the later file's record is used.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-C1850"></a>
### A replacing restore leaves the live ledger's redaction stores in place: a marked target comes back live, and a second redaction of a restored tenant keeps its revision text and retry key

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-writesets.json](../../experiment/playbook-completion/findings/audit/zz-writesets.json) (live `ws-live-gap-restore`; live `ws-live-gap-marker`; inspected `iris_vector_graph/_engine/snapshot.py:1654-1692`; inspected `iris_src/src/Graph/KG/LedgerRedact.cls:333-378`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `ws-live-gap-restore`, `ws-live-gap-marker`

- Expected: spec 256 Decision 2 as the code states it (iris_src/src/Graph/KG/LedgerRedact.cls:349-352: clear message, source, correlation id and idempotency key of a revision with a redacted record) and specs/256-ledger-tenant-redaction/spec.md:142 (SC-001); ADR-0013 (redaction removes content from history; while a run is in progress the target is not live); decisions.md HD-1801 (treat the archive's history as a unit; keep current redaction obligations).
- Observed at the pin: Live in AUDITB. (1) ws-live-gap-restore: tenant wsgap, revision 2 (message, key wsgap-k1); save_snapshot; erase; redact complete (audit revision 3; redactedRev(2), idemRedacted set, idem killed, text cleared); restore_snapshot(archive, merge=False): records of seq 2 back as originals, row 2 message and key back, idem(wsgap-k1) live, while redactedRev(2) and idemRedacted stay (the import of ^IVG.Ledger sets the archive's nodes and kills none, snapshot.py:1574, 1654-1692). Erase and redact again: the 3 records are tombstoned but ClearRevision is skipped because redactedRev(2) exists (LedgerReda…
- Source severity S1, confidence high; module 18; governing page here: `install.snapshot`.
- Remedy proposed by the playbook arm (not implemented): Make a replacing restore replace the whole ledger state as a unit (kill ^IVG.Ledger, including marker, redactedRev and idemRedacted, before importing) or refuse it when the live ledger has redactions after the archive (HD-1801's working answer); and have ClearRevision clear a revision's text whenever it still holds text, not only when redactedRev is absent.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-tmp-102"></a>
### With the driver's autocommit off, rolling back a create_edge_temporal keeps the temporal edge but removes its structural edge and nodes

Severity: High · Decision: Open

Run: Uplift 2026-11-16 (retest, iteration 26)

Found by: the first `write_routing` native binding run, which disagreed with the model in three autocommit-off histories ([receipt](results/write_routing/20261116T214148Z-binding/receipt.json)); then a targeted probe with the source-based expectation frozen first ([predictions](../uplift/consolidated/iteration-26/caller-txn-PAIRS.md)); [write_routing](models/write_routing/NOTES.md) `theorem_autocommit_off_temporal_edge_splits`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 retest fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-26/autocommit-observed-20261116T214248Z.json); [binding](results/write_routing/20261116T214623Z-binding/receipt.json)). Caller: `conn.setAutoCommit(False)`, nothing written (`$TLEVEL` 0), `create_edge_temporal(a, R, b, timestamp=…)` (`$TLEVEL` 1 afterwards), `conn.rollback()`. Then, on another connection: `get_edges_in_window(a, R, …)` returns the edge and `^KG("tout")` holds it, while `MATCH ()-[r:R]->()` counts 0, `^KG("out")` has no entry and `get_node` finds neither endpoint. Same result on an engine made with `from_connect`. Passing neighbors: the same call after SQL `START TRANSACTION` leaves nothing after the rollback (T13), and with `commit()` every reader sees the edge (T11n).

Expected: USER_GUIDE "Writes inside your transaction": with autocommit off a transaction is open, and "your rollback removes the rows the write made and its adjacency entries". ADR-0009: a temporal edge owns its marked structural row. The owner is [structure.write](../ontology/features/graph-structure.g5.md#structure.write).

Cause: `create_edge_temporal` calls `Graph.KG.TemporalIndex.InsertEdge` directly (`IRISGraphStore.write_temporal_edge`), not through `WriteTxn`, so nothing opens the caller's level first. `InsertEdge` sets `^KG("tout")`/`("tin")` at `$TLEVEL` 0, where a global set is durable at once, and only then inserts the marked row and endpoint nodes with embedded SQL, which opens the caller's transaction implicitly and is rolled back with it.

Consequence: a rolled-back temporal edge stays in window reads, aggregates and latest-event reads, while Cypher, traversal and the node readers never saw it; the two readers disagree permanently. High: wrong results after a rollback the caller relied on, with a confirmed trigger on a documented caller mode. `delete_edge_temporal` repairs one edge if the caller knows it.

The same rule holds for the batch writer and the delete (iteration 31, [observation](../uplift/consolidated/iteration-31/temporal-variants-observed-20261116T221350Z.json), [binding](results/write_routing/20261116T221455Z-binding/receipt.json)): a rolled-back `bulk_create_edges_temporal` keeps its temporal entries and loses its structural rows and nodes; a rolled-back `delete_edge_temporal` leaves the temporal edge deleted while its structural row and `^KG("out")` entry come back. Under `START TRANSACTION` both are fully undone.

Repair proposal (checked in the model only): open the caller's level first, as `WriteTxn.begin` does with autocommit off (`Txn_Begin(1)`), around the direct temporal calls, or write the SQL part first (controls `temporal-sql-first`, `delete-sql-first` make the split theorem fail). Preserve: the calls join the caller's transaction after `START TRANSACTION` on both engines (T4, T5, W37). Distinguishing case: T11 against T13.

<a id="bug-cyp-120"></a>
### A relationship CREATE between new nodes drops every computed or parameter property value without an error

Severity: High · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 48)

Found by: a follow-up to W55's write pairs before the source reading (`F7_rel_fn` in [follow-up 2](../uplift/consolidated/iteration-48/cypherexpr-observed2-20261117T021350Z.json)), isolated in [follow-up 3](../uplift/consolidated/iteration-48/cypherexpr-observed3-20261117T021604Z.json); the plain-parameter case by [review 47-49](../uplift/consolidated/iteration-50/REVIEW-47-49.md) item 5; [cypher_exprs](models/cypher_exprs/NOTES.md) `theorem_inline_rel_expression_dropped` and `theorem_inline_rel_param_dropped` with neighbor `theorem_inline_rel_literal_written`; controls `rel-value-kept`, `rel-param-kept`, `rel-literal-dropped`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-48/cypherexpr-observed3-20261117T021604Z.json) `toUpper_lit`, `size_lit`, `arith`, `toString_lit`, `uuid`, `param_fn`; [follow-up](../uplift/consolidated/iteration-48/cypherexpr-observed2-20261117T021350Z.json) `F7_rel_*`; iteration 50: [fresh repro](../uplift/consolidated/iteration-50/review-repro-20261117T031150Z.json) `rel_new_param*`, [binding](results/cypher_exprs/20261117T033119Z-binding/receipt.json) `create_rel_*`, `create_rel_matched_*`, `create_node_Param`). `CREATE (:N {id: 'a'})-[:T {v: 1 + 1}]->(:N {id: 'b'})` succeeds and writes both nodes and the relationship, but the relationship has no `v`; the same holds for `toUpper('ab')`, `size('ab')`, `toString(1)`, `randomUUID()`, `toUpper($s)` and a plain parameter: `CREATE (a {id: ...})-[r {k: $k, lit: 1}]->(b {id: ...})` with `$k = 4` stores `keys(r) = ['lit']` and `r.k` null. Passing neighbors: a literal `{v: 'ab'}` and an `UNWIND` literal variable are stored; a node `CREATE` stores `$k`; between matched nodes `$k` and literals are stored, and a computed value is refused with a message naming the property (documented in KNOWN_ISSUES).

Expected: openCypher: a `CREATE` stores each property value its map computes or binds; where IVG cannot, it refuses (as it does between matched nodes).

Observed: `_create_clause_relationship_entry`, for endpoints known literally, keeps a property value only when it is a Literal or a FOREACH/UNWIND literal variable; any other expression, an `ast.Parameter` included, maps to None, and the next line drops None values as "null props are not stored" (`translator.py:10213-10226`). The multigraph branch receives the same filtered map.

Consequence: the write reports success and the property is lost; nothing tells the caller. Drivers send values as parameters, so the ordinary pattern `CREATE (a {id: $a})-[:R {since: $since}]->(b {id: $b})` loses `since`. High (silent data loss on an ordinary `CREATE` pattern).

Repair proposal (not implemented): resolve a relationship value as a node value is resolved: bind a parameter as its value, fold or translate a computed value, or refuse naming the property; never drop a non-null value. Preserve: literal and `UNWIND`-literal values, the matched-node refusal until computed values are supported there, and null values not stored. Writers and readers affected: the literal-endpoint fast path and its multigraph branch; every reader of `rdf_edges.qualifiers`. Distinguishing case: `CREATE (:N {id: 'a'})-[:T {k: $k}]->(:N {id: 'b'})` stores `k`. The controls `rel-param-kept` and `rel-value-kept` check the repaired rule in the model only. Governing statement: [query.writes.computed_values](../ontology/features/cypher.g5.md#query.writes.computed_values).

<a id="bug-plt-113"></a>
### kg_PPR_GUIDED_SUBGRAPH lists almost none of the edges among its answered nodes and can answer more nodes than its cap

Severity: High · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 49)

Found by: W56 prediction P1 ([predictions](../uplift/consolidated/iteration-49/retrieval-PAIRS.md), missed), traced through `kg_PPR_GUIDED_SUBGRAPH` and `Graph.KG.Subgraph.SubgraphJson`; corrected after [review 47-49](../uplift/consolidated/iteration-50/REVIEW-47-49.md) item 1, which found that the iteration-49 entry treated the documented cap as the defect and proposed the wrong repair, and found the seeds-over-the-cap case. [retrieval_compose](models/retrieval_compose/NOTES.md) `theorem_filled_cap_expands_only_first_node` and `theorem_admitted_seeds_ignore_cap` (every input), witnesses `theorem_guided_subgraph_drops_edges_among_top_nodes` and `theorem_guided_seeds_exceed_cap`, neighbor `theorem_guided_uncapped_lists_all_edges`; controls `edges-among-answered`, `seeds-capped`, `expand-whole-frontier-at-cap`, `guided-cap-top-k-only` ([prove](results/retrieval_compose/20261117T032018Z-prove/receipt.json), 15 of 15 controls EXPECTED_FAIL). The iteration-49 control `guided-cap-max-nodes` encoded the wrong repair and is withdrawn (its receipts are kept).

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin, ObjectScript `SubgraphJson` path (no Arno reader on the fixture): iteration-50 [fixture reproduction](../uplift/consolidated/iteration-50/review-repro-20261117T031150Z.json) and [binding](results/retrieval_compose/20261117T032153Z-binding/receipt.json) `guided[*]`, `guided_more[*]` (AGREES 45 cases); earlier [observation](../uplift/consolidated/iteration-49/retrieval-observed3-20261117T024208Z.json) `PG_star_top3`, `PG_star_top7`, `PG_star_top50`. Default graph, star s → a1..a6 plus a1 → a2. `kg_PPR_GUIDED_SUBGRAPH([s], ppr_top_k=7)` answers all seven nodes with the single edge a1 → a2; `ppr_top_k=3` answers s, a1, a2 with only a1 → a2. Seeds s, a3, a4 with `ppr_top_k=1` answer three nodes (the cap is 1) and no edge, although s → a3 and s → a4 join them; [s] with `ppr_top_k=50` and `max_nodes=3` answers seven nodes and only a1 → a2. Passing neighbor: [s] with `ppr_top_k=50` and the default `max_nodes` answers all seven edges.

Expected: the docstring (`algorithms.py:956-957`): the subgraph of the seeds and the top nodes within `k_hops`, "capped at `min(max_nodes, ppr_top_k)` nodes"; the [design note](../../docs/dev/notes/enhancements/001-ppr-guided-subgraph.md) (`top_k` a "hard node cap"; acceptance "`len(result.nodes) <= top_k` always"); [algorithms.op.subgraph](../ontology/features/algorithms.g5.md#algorithms.op.subgraph): the edges among the answered nodes. The cap itself is intended.

Observed: `kg_PPR_GUIDED_SUBGRAPH` calls `kg_SUBGRAPH(seeds + top_ids, k_hops, max_nodes=min(max_nodes, ppr_top_k))` (`algorithms.py:971-973`). `SubgraphJson` admits every seed that has an edge with no cap test (`Subgraph.cls:36-48`), so the seeds alone can exceed the cap; once the count has reached the cap it expands only the first frontier node in ID order, recording that node's out-edges, and stops (`Subgraph.cls:51-99`). With Arno loaded and no `edge_types`, `IRISGraphStore.execute_subgraph` asks `ArnoAccel.SubgraphNativeJson` first (`iris_sql_store.py:2526-2541`); that path was not checked.

Consequence: whenever the walk reaches at least `ppr_top_k` nodes (with the default 50, any ordinary graph), the answer is the top nodes with only the out-edges of the alphabetically first one, which may also point outside the answer; with more seeds than the cap the answer is larger than the documented cap. A retrieval caller gets a node list with its relationships missing and no sign of it. High is kept: the method's main output is wrong under its defaults, silently; the cap being intended does not change the edge loss. The over-cap node count alone would be Medium.

Repair proposal (not implemented): keep the cap; admit seeds and top nodes only up to the cap (best PPR score first), then list every edge whose two ends are answered (the same repair as bug-plt-114's). Preserve: the cap `min(max_nodes, ppr_top_k)`, the PPR ranking and `ppr_top_k`, argument checks before any read, `k_hops`, and the uncapped answer (all seven edges when the cap exceeds the reachable nodes). Writers and readers: `SubgraphJson` (seed loop, frontier loop, edge list), `kg_SUBGRAPH` and `kg_PPR_GUIDED_SUBGRAPH` (reshape), `IRISGraphOperators.kg_PPR_GUIDED_SUBGRAPH`; the Arno reader must give the same answer. Distinguishing cases: [s] with `ppr_top_k=3` lists s → a1 and s → a2; seeds s, a3, a4 with `ppr_top_k=1` answer one node. Checked in the model only (controls `edges-among-answered` and `seeds-capped` make the departures fail while the uncapped neighbor verifies); not run on the product. Governing statement: [algorithms.op.subgraph.guided](../ontology/features/algorithms.g5.md#algorithms.op.subgraph.guided).

<a id="bug-str-004"></a>
### verify_graph reports healthy parallel edges as missing adjacency and cannot see lost multiplicity

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Found by: A-structure F7 (source arithmetic; open task T036, `tasks.md:198`; unmet SC-005, `spec.md:355-356` of spec 234).

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `parallel_ledger_delete`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: [graph_structure_parallel_delete_rel](receipts/native/graph_structure_parallel_delete_rel.json) (`f7_verify_before`) — before any delete, a default graph holding two parallel edges reports `ok: 0` with "missing" drift of 1 row in `^KG("out")` and 1 in `^KG("in")` (`sqlEdges` 2, `outEdges` 1).

Expected: `verify_graph` reports rows with no adjacency entry and entries with no row, and its `ok` answers whether the graph's adjacency agrees with its rows; in a multigraph the layout holds one leaf plus children for two or more edges (spec 234 FR-004, SC-005).

Observed: `GraphVerify` computes `missing = rows − matched distinct triples` (`GraphVerify.cls:78, 104, 128`), so every extra parallel edge counts as missing, and a triple that lost its children still matches.

Consequence: an operator sees false drift on every multigraph and may rebuild for nothing, while real multiplicity loss (for example [bug-str-001](#bug-str-001)) goes unreported.

Repair proposal (not implemented): compare each triple's row count with its leaf, children and `#` count. Governing statement: [structure.verify](../ontology/features/graph-structure.g5.md#structure.verify).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [structure.verify](../ontology/features/graph-structure.g5.md#structure.verify).

<a id="bug-tmp-009"></a>
### A temporal aggregate read of min, max or avg over an empty window raises ValueError, although the method promises 0.0

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Found by: review R2-data R1-5 (seen in six probe traces); the same error first stopped two cases of the earlier temporal probe runs.

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `empty_temporal_min`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: [temporal_write_modes](receipts/native/temporal_write_modes.json) and [temporal_rollback_counters](receipts/native/temporal_rollback_counters.json) — `get_temporal_aggregate(..., "min"/"max"/"avg")` over a window with no raw edge (empty, or holding only counts a rolled-back or refused write left) raised `ValueError: could not convert string to float: 'None'`.

Expected: "An empty window or an unknown metric gives `0` or `0.0`, never `None`; a failed server call raises" (`_engine/temporal.py:950-951`).

Observed: the store converts the server's answer with `val = str(...)`, so a missing value becomes the text `None`, which is truthy, and then returns `float(val) if val else 0.0` (`iris_sql_store.py:2977-2987`); the engine also returns `None` when no row comes back (`_engine/temporal.py:959`).

Consequence: dashboards and callers that read min, max or average over a quiet window get an exception instead of 0.0.

Repair proposal (not implemented): test the server value for None before converting, and return `0.0` in the engine's no-row branch, as documented. Governing statement: [temporal.stats](../ontology/features/temporal.g5.md#temporal.stats).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [temporal.stats](../ontology/features/temporal.g5.md#temporal.stats).

<a id="bug-srch-005"></a>
### The engine's fusion gives a result missing from one leg a non-zero, length-dependent score

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Iteration 49: the trigger is now confirmed at the real readers (below). Severity stays Medium: a wrong ranking among retrieved candidates, consistent with bug-srch-109.

Found by: A-search F5 and S1 ([intent](../uplift/ivg-verus-initial/intent/search.md)); W56 predictions F1/F1b ([predictions](../uplift/consolidated/iteration-49/retrieval-PAIRS.md), F1b missed); [retrieval_compose](models/retrieval_compose/NOTES.md) `theorem_engine_absent_rank_reorders`, `theorem_engine_skipped_leg_adds_constant`, neighbor `theorem_both_legs_rank10_wins_everywhere`; controls `engine-absent-zero`, `sql-absent-like-engine`.

Reproduced by: **E2E reproduced** (iteration 49) on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-49/retrieval-observed-20261117T023944Z.json) `F1_engine`, `F8_pyops_hybrid_G`, `F3_empty_text`, `F6_sql_fuse`; [binding](results/retrieval_compose/20261117T024807Z-binding/receipt.json) `engine_fuse`, `pyops_hybrid`, `sql_fuse`, `engine_empty_text`). One graph: x is vector rank 1 and in no text list; n00..n59 are in both legs in the same order (vector leg 62 long, text legs 60 long). The engine's `kg_RRF_FUSE(..., c=60)` answers x 31st with 1/61 + 1/180; the `/hybridSearch` body (`PyOps.HybridSearch` → `FuseRanks`) on the same graph answers x 61st with 1/61, and the SQL procedure on the default graph follows the 10^9 rule as well. An empty text query adds 1/120 to every engine row. Passing neighbor: an item at rank 10 in both legs beats x on every surface. Earlier record: partial reproduced — [executable component cases](audits/register-20261115/components.py) and [results](audits/register-20261115/components.json). Remaining gate: a real pair of vector/BM25 providers and final reader ranking contrast remain; absent-rank policy is still Q search.fusion.absent

Historical reproduction record: none

Expected: "each hit scores 1/(c+rank)" and "legs not yet searched contribute nothing" (engine docstring and API reference).

Observed: the engine's RRF scores an absent item at a rank derived from the leg's length (`vector.py:1444-1446`), the SQL procedure uses 1e9 (`schema.py:2536-2537`), and `ivg.retrieve` and `fusion.py` use 0 (`translator.py:3342-3352`; `fusion.py:56-58`).

Consequence: with c=60 and legs of 200, an item at vector rank 1 only (1/61 + 1/320 = 0.01952) outranks one at rank 50 in both legs (2/110 = 0.01818), the reverse of standard RRF; the four entry points rank the same inputs differently.

Repair proposal (not implemented): [simp-srch-001](design_simplification.md#simp-srch-001). Open choice: [search.fusion.absent](open_questions.md#HD-0702). Governing statement: [search.fusion](../ontology/features/search.g5.md#search.fusion).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). a real pair of vector/BM25 providers and final reader ranking contrast remain; absent-rank policy is still Q search.fusion.absent

Canonical owner and evidence: [search.fusion](../ontology/features/search.g5.md#search.fusion), [search.fusion.absent](open_questions.md#HD-0702).

<a id="bug-plt-004"></a>
### A merge restore keeps at most one row per graph in the core tables and reports every row restored

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13


Found by: A-platform F-B1 (sub-reader b, re-read by A-platform).

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `snapshot_merge_parent`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: original two-edge/column-order scenario not rerun; iteration 5 real IRIS parent-key/vector consequence via [snapshot binding](models/snapshot_routes/binding.py) and its retained [receipts](results/snapshot_routes).

Expected: a merge restore adds the archive's rows that are not already present; the v4.1.0 CHANGELOG (3926-3932) names this dedupe defect and fixes it for the FHIR tables.

Observed: the generic merge guard is `WHERE NOT EXISTS (… WHERE {cols[0]} = ?)` and the count is incremented regardless (`_engine/snapshot.py:1287-1298`); export drops `edge_id` (`snapshot.py:872-874`), so for `rdf_edges` (and `rdf_labels`, `rdf_props`, `docs`) the first column is `graph_id`.

Consequence: saving two edges in G, erasing G and merge-restoring gives one edge, and the report says two were restored.

Repair proposal (not implemented): dedupe on each table's key columns, and count only rows actually inserted. Governing statement: [install.snapshot](../ontology/concepts/install.g5.md#install.snapshot).

Iteration 5: the first-column guard root is also F-1802, whose earlier live evidence is retained. A new native shared-ID/other-graph parent witness loses graph A's parent, so its routed vector fails FK and the final reader is empty; the original complete-archive prediction and DISAGREES receipt are preserved. The Verus restore_parent/load/read chain derives this consequence. This strengthens the inherited root, not a new discovery or a repair.


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [install.snapshot](../ontology/concepts/install.g5.md#install.snapshot), [install.snapshot.routes](../ontology/concepts/install.g5.md#install.snapshot.routes).

Fresh audit qualification: two archived parents in the same graph reproduce the first-column merge skip on this schema. The initial one-parent-per-graph/shared-ID attempt succeeded and is preserved as a refuted subcase; it does not refute all merge-loss cases.

<a id="F-0204"></a>
### The graph check reports a multigraph's parallel edges as missing adjacency

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [02.json](../../experiment/playbook-completion/findings/audit/02.json) (live `breadth-a-live-02-identity`)

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `parallel_ledger_delete`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-02-identity`

- Expected: Spec 234 SC-005: zero drift on a multigraph after random creates and deletes.
- Observed at the pin: false drift on parallel edges
- Source severity S2, confidence high; module 02; governing page here: `graph. / structure.`.
- Remedy proposed by the playbook arm (not implemented): Compare rows per (s,p,o) with the keyed '#' count.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [structure.verify](../ontology/features/graph-structure.g5.md#structure.verify).

<a id="F-0208"></a>
### An engine keeps a graph's mode forever, so another engine's change is not seen

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [02.json](../../experiment/playbook-completion/findings/audit/02.json) (live `breadth-a-live-02-identity`; mc `breadth-a-mc-gid_mode-as-built`)

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `stale_multigraph`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-02-identity`

- Expected: Spec 234 FR-002; GID-I4.10.
- Observed at the pin: stale cache wrote a parallel edge into a mode-off graph
- Source severity S2, confidence high; module 02; governing page here: `graph. / structure.`.
- Remedy proposed by the playbook arm (not implemented): Read the mode per statement, expire the cache, or refuse a keyed insert server-side in a mode-off graph.
- Reviewed-design control: `playbook-proofs-d1e` `control_f0208_mode_cached_forever` fails where expected in this run ([receipt](results/playbook-proofs-d1e/20261115T035518Z-control_f0208_mode_cached_forever/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1e/20261115T035416Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [structure.multigraph.switch](../ontology/features/graph-structure.g5.md#structure.multigraph.switch).

<a id="F-0403"></a>
### verify_graph reports drift on a graph with parallel edges whose index matches its rows

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [04.json](../../experiment/playbook-completion/findings/audit/04.json) (live `breadth-a-live-02-identity`)

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `parallel_ledger_delete`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-02-identity`

- Expected: Spec 234 SC-005 and spec.md:78-80.
- Observed at the pin: false drift on parallel edges
- Source severity S2, confidence high; module 04; governing page here: `structure.`.
- Remedy proposed by the playbook arm (not implemented): Count rows per triple against the '#' count.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [structure.verify](../ontology/features/graph-structure.g5.md#structure.verify).

<a id="F-0502"></a>
### A temporal write with no time lands at epoch 0, not at the current time

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [05.json](../../experiment/playbook-completion/findings/audit/05.json) (live `breadth-a-live-05-temporal`)

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `missing_temporal_time`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-05-temporal`

- Expected: InsertEdge's own rule: a missing time is now (TemporalIndex.cls:51).
- Observed at the pin: single write stored at 0; batch ts 0 stored at 1794609910 (>1767225600)
- Source severity S2, confidence high; module 05; governing page here: `temporal.`.
- Remedy proposed by the playbook arm (not implemented): Send '' for a missing timestamp; stop treating an explicit 0 as missing in BulkInsertCounts.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

Iteration 7 strengthens the known missing-time issue, also bug-tmp-007, without a new bug count: actual Python single omission/None sends text0 and native stores epoch0; normal bulk0 resolves current seconds, prewrite-unavailable bulk fallback stores epoch0. Positive100 agrees; duplicate normal0/collision1 versus fallback1/collision0 leaves the same event. temporal_clock derives raw aliases/carrier/selected server writer to the final window with 25 new units plus31 inherited rechecked. Actual native9 and Python adapter evidence remain distinct. Intended missing-time clock requirement remains; no repair or general prefix-failure/clock/coercion proof.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [temporal.edge.clock](../ontology/features/temporal.g5.md#temporal.edge.clock).

<a id="F-0607"></a>
### The IVF index's 'cosine' metric is an unnormalised dot product

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [06.json](../../experiment/playbook-completion/findings/audit/06.json) (live `breadth-a-live-06-vectors`)

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `ivf_cosine`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-06-vectors`

- Expected: metric='cosine' is cosine similarity (VecIndex.Cosine normalises, VecIndex.cls:83-90).
- Observed at the pin: dot-product order and scores outside [-1, 1]
- Source severity S2, confidence high; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Normalise at build, insert and query time.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [search.scope.indexes.ivf](../ontology/features/search.g5.md#search.scope.indexes.ivf).

<a id="F-0610"></a>
### The SQL kg_KNN_VEC answers no rows, without error, for a graph whose vectors are under a declared model

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [06.json](../../experiment/playbook-completion/findings/audit/06.json) (live `breadth-a-live-06-vectors`)

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `declared_model_knn`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-06-vectors`

- Expected: docs/KNOWN_ISSUES.md:702-714 (such a call raises); 4.6.0 R265 (no silent empty answer).
- Observed at the pin: empty answer, no error
- Source severity S2, confidence high; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Have VectorRouteGuard refuse when the graph has any node route other than kg_NodeEmbeddings.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [search.knn](../ontology/features/search.g5.md#search.knn).

<a id="F-0803"></a>
### A WHERE after RETURN is parsed and dropped

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0803`; inspected `iris_vector_graph/cypher/parser.py:287-291`; run `b-08-run-unit`; live `b-08-live-f0803-rerun`; run `b-08-run-unit-rerun`)

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `where_after_return`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0803`, `b-08-live-f0803-rerun`

- Expected: CYP-X3.8: a where clause after a return is refused, never read and dropped; openCypher refuses the text.
- Observed at the pin: Live: `MATCH (n:B08L) RETURN n.id AS id WHERE false` returned all 5 B08L nodes, no error. tests/unit/test_lexer_parser_coverage.py:209 test_standalone_where_return asserts nothing (passes, b-08-run-unit).
- Source severity S2, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Raise CypherParseError for WHERE after RETURN (or apply it), with a unit test asserting the refusal.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [query.conformance](../ontology/features/cypher.g5.md#query.conformance).

<a id="F-0810"></a>
### SET n.p = null keeps the key

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0810`; inspected `iris_vector_graph/cypher/translator.py:13648-13665`; live `b-08-live-f0810-rerun`)

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `set_literal_null`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0810`, `b-08-live-f0810-rerun`

- Expected: openCypher: SET n.p = null removes the property; tests/e2e/test_470_set_null_e2e.py docstring says a literal null removes it.
- Observed at the pin: Live: after SET n.z = null on b08_s, keys(n) = [id, z, name] and properties(n).z = '' (the rdf_props row remains); a computed null deletes.
- Source severity S2, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Delete the row for a literal null too; live test of keys(n).
- Reviewed-design control: `playbook-proofs-d1d` `control_f0810_null_keeps_key` fails where expected in this run ([receipt](results/playbook-proofs-d1d/20261115T035655Z-control_f0810_null_keeps_key/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [query.values](../ontology/features/cypher.g5.md#query.values).

<a id="F-0823"></a>
### An aggregate in a CALL subquery that matches nothing answers 0

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0823`; inspected `iris_vector_graph/cypher/translator.py:14543`; live `b-08-live-f0823-rerun`)

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `empty_call_max`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0823`, `b-08-live-f0823-rerun`

- Expected: openCypher: an empty max/avg is null, an empty collect is [], count is 0.
- Observed at the pin: Live: max(q.v) -> '0', avg(q.v) -> '0' (should be null); collect(q.v) -> the text '[]' (not 0 as the finding said; a string, not a list); count(q) -> 0 (right).
- Source severity S2, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): COALESCE only for count; live test per aggregate.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [query.aggregation](../ontology/features/cypher.g5.md#query.aggregation).

<a id="F-1004"></a>
### A cached personalized PageRank answer misses a start node written or removed without an edge

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [10.json](../../experiment/playbook-completion/findings/audit/10.json) (live `b-10-live-cache`; probe `b-10-probe-units`; mc `m10-cache-as-built-ppr`; mc `m10-cache-reviewed-ppr`; mc `m10-cache-control-no-bump-on-create`; mc `m10-cache-as-built-pagerank`)

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `ppr_edgeless_seed`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-10-live-cache`, `b-10-probe-units`

- Expected: ALG-B2.19 (a cached answer changes when a start node is added to the graph or removed from it); ALG-B16.11 (after any write a cached answer equals a fresh computation); ALG-I4.
- Observed at the pin: Live (b-10-live-cache): kg_PERSONALIZED_PAGERANK(['b10_x']) answered {} before b10_x existed and the answer was cached (^IVG.AlgoCache(0,'ppr',...)); create_node('b10_x') with no edge wrote only nodes/rdf_props and moved no token; the same call then answered {} from the cache while a fresh run (after AlgoCache.InvalidateAll) answered {'b10_x': 1.0, 'b10_a': 0.0, 'b10_b': 0.0}. Refuted part: deleting the edgeless start node moved ^KG('__version') (7128 -> 7131 for a labelled node; edgeless 7125 -> 7127) because delete_node runs Graph.KG.Eraser.EraseNodeIds, whose InvalidateDerived bumps the to…
- Source severity S2, confidence high; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Put the node-set token in the PPR key (as global PageRank does since R313) or raise a node token on every node write and read it inside AlgoCache.Lookup; a live test that creates an edgeless start node after a cached call.
- Reviewed-design control: `playbook-proofs-d1e` `control_f1004_create_moves_no_token` fails where expected in this run ([receipt](results/playbook-proofs-d1e/20261115T035446Z-control_f1004_create_moves_no_token/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1e/20261115T035416Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

Iteration 3 comparison: the create-an-edgeless-start-node trigger/effect is also bug-plt-017; the two source records are retained, not counted as separate new discoveries. The refuted deletion premise here is not restored. New pagerank_admission is global PageRank only and explicitly does not cover PPR; its node-key success cannot repair or refute this PPR finding.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [algorithms.cache.token](../ontology/features/algorithms.g5.md#algorithms.cache.token).

<a id="F-1802"></a>
### A merge restore guards plain tables on their first column only, and counts skipped rows as restored

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [18.json](../../experiment/playbook-completion/findings/audit/18.json) (live `c18-live-merge-guard`; live `c18-live-save-footprint`; inspected `iris_vector_graph/_engine/snapshot.py:1287-1298`)

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `snapshot_merge_parent`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c18-live-merge-guard`, `c18-live-save-footprint`

- Expected: SNP-B4.1 (a merge adds each missing row, judged by the row's own key); SNP-B4.2 (a row counts as restored only when added); USER_GUIDE.md:1151-1153 (merge=True adds to what is there).
- Observed at the pin: Live (c18-live-merge-guard): graph c18m with 3 nodes, 2 edges, labels and props archived ({'nodes': 3, 'rdf_edges': 2, 'rdf_labels': 3, 'rdf_props': 6}); after erase and re-creating one edge, one label, one property ({'nodes': 2, 'rdf_edges': 1, 'rdf_labels': 1, 'rdf_props': 3}), merge restore left {'nodes': 3, 'rdf_edges': 1, 'rdf_labels': 1, 'rdf_props': 3} - rows missing {'nodes': 0, 'rdf_edges': 1, 'rdf_labels': 2, 'rdf_props': 3}; the result reported restored_tables {'Graph_KG.code_crosswalk': 0, 'Graph_KG.docs': 0, 'Graph_KG.embedding_registry': 0, 'Graph_KG.fhir_bridges': 0, 'Graph_KG.…
- Source severity S2, confidence high; module 18; governing page here: `install.snapshot`.
- Remedy proposed by the playbook arm (not implemented): Guard each table on its primary or unique key (as CONFIGURATION_TABLES does) and count only inserted rows.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

Iteration 5 strengthening: the generic first-column merge guard is the same root as bug-plt-004; both IDs/history are retained, not counted as two new findings. Real IRIS merge with preexisting graph B's shared node skips graph A's parent and refuses A's routed vector by FK, while B's existing vector is counted restored but unchanged. snapshot_routes now derives restore_parent -> load -> read and distinguishes an existing incompatible row's successful skip from an empty incompatible table's refusal. Original complete-archive prediction/DISAGREES receipt retained; no repair implemented.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [install.snapshot.routes](../ontology/concepts/install.g5.md#install.snapshot.routes).

Fresh audit qualification: the 41-case panel exercises the two-parents-in-one-graph skip and preserves an existing live graph. The historical routed-vector parent case is not rerun under an asserted identical physical column order.

<a id="F-C0101"></a>
### An inline relationship property in a Cypher pattern fails on an edge with no properties

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [01.json](../../experiment/playbook-completion/findings/audit/01.json) (live `breadth-a-live-02-mode-off`; inspected `iris_vector_graph/schema.py:2185`; inspected `iris_vector_graph/cypher/translator.py:11197-11216`)

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `null_relationship_pattern`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-02-mode-off`

- Expected: openCypher: MATCH (x)-[r:R {k: 0}]->(y) and MATCH (x)-[r:R]->(y) WHERE r.k = 0 are equivalent; a missing property makes the filter false, not an error. create_edge's docstring: omitted properties leave the property null.
- Observed at the pin: inline form raises SQLCODE -149 on NULL qualifiers
- Source severity S2, confidence high; module 01; governing page here: `install.`.
- Remedy proposed by the playbook arm (not implemented): Guard Graph_KG.JSON_VALUE against an empty/NULL document (as CY_REL_PROP does), or emit the guarded function in _merge_prop_preds; a Cypher test over an edge written by create_edge without properties.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [query.conformance](../ontology/features/cypher.g5.md#query.conformance).

<a id="F-C0501"></a>
### A refused temporal write raises but leaves the edge in the temporal index

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [05.json](../../experiment/playbook-completion/findings/audit/05.json) (live `breadth-a-live-05-partial`; inspected `iris_src/src/Graph/KG/TemporalIndex.cls:80-111`)

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `temporal_partial_retry`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-05-partial`

- Expected: create_edge_temporal docstring: 'A write IRIS refuses raises GraphWriteError and writes nothing'.
- Observed at the pin: raised, yet the temporal index holds the edge
- Source severity S2, confidence high; module 05; governing page here: `temporal.`.
- Remedy proposed by the playbook arm (not implemented): Open a transaction in InsertEdge/WriteStores (or assert the row first) so a refusal takes back tout/tin/bucket/tagg.
- Reviewed-design control: `playbook-proofs-d1c` `control_fc0501_refused_write_partial` fails where expected in this run ([receipt](results/playbook-proofs-d1c/20261115T035825Z-control_fc0501_refused_write_partial/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1c/20261115T035754Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [temporal.write.partial-failure](open_questions.md#temporal.write.partial-failure).

<a id="F-C0602"></a>
### SQL kg_KNN_VEC answers a node once per label, so a multi-label node takes several of the k places

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [06.json](../../experiment/playbook-completion/findings/audit/06.json) (live `breadth-a-live-06-embed`; inspected `iris_vector_graph/schema.py:2468-2479`)

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `knn_label_multiplicity`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-06-embed`

- Expected: kg_KNN_VEC is a k-nearest-nodes search over the default route (schema.py:2437-2483); kg_RRF_FUSE's vector leg calls it with no label filter (schema.py:2558).
- Observed at the pin: answer ['bakn1233234', 'bakn1233234'] (a twice, b pushed out)
- Source severity S2, confidence high; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Use EXISTS for the label filter (no join when no filter is given), or SELECT DISTINCT node_id.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [search.knn](../ontology/features/search.g5.md#search.knn).

<a id="F-C0715"></a>
### bm25_search rewrites document ids: its leading-dot patch runs over the whole answer, so an id holding ':.5', ',.7' or '[.9' comes back as ':0.5', ',0.7', '[0.9'

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-refusals.json](../../experiment/playbook-completion/findings/audit/zz-refusals.json) (live `rx-dec-live-07`; check `rx-dec-map`; inspected `iris_vector_graph/_engine/vector.py:1817-1819`; inspected `iris_src/src/Graph/KG/BM25Index.cls:361-365`)

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `bm25_result_id`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `rx-dec-live-07`

- Expected: TXT-B2 (search returns each best document with its node id and score); TXT-B2.13 (each id and score in the answer is valid JSON, ids included); CHANGELOG.md:463-467 (4.6.3: 'Search answers keep a node id with a quote or a backslash', each answer escaped as RFC 8259 asks); docs/USER_GUIDE.md:859-866 (bm25_search and CALL ivg.bm25.search answer the same nodes); tests/e2e/test_463_search_id_escaping_e2e.py:57-71 asserts the Python and Cypher answers agree id for id.
- Observed at the pin: Live (rx-dec-live-07, case 'ids containing ...'): graph rxdg, nodes rxd:a, rxd:.5x, rxd,.7y, rxd[.9z, rxd:b with the word zebra, index rxdidx. Graph.KG.BM25Index.Search's raw answer is valid JSON with the ids exactly as stored and every score already written with a leading 0 (no '"score":.' in the wire); bm25_search answered ('rxd:0.5x', ...), ('rxd,0.7y', ...), ('rxd[0.9z', ...) for 3 of the 5 rows, and bm25_search(report=True) the same; CALL ivg.bm25.search (JSON_TABLE over the same wire) answered the ids unchanged. Cause: _parse applies re.sub(r'(?<=[:\[,])(\.\d)', r'0\1', raw) to the whol…
- Source severity S2, confidence high; module 07; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Drop the text patch (the server already writes a leading 0), or apply it to number tokens only by parsing with json.loads(parse_float=...) after a token-aware scan; add an id with ':.5' to the 4.6.3 id-escaping test.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [search.bm25](../ontology/features/search.g5.md#search.bm25).

<a id="F-C0848"></a>
### A Cypher CREATE or MERGE with literal or parameter endpoint ids drops a parameter-bound relationship property without an error

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (live `st-live-cypher-relprop`; live `st-live-cap-values`; inspected `iris_vector_graph/cypher/translator.py:10213-10246`; inspected `iris_vector_graph/cypher/translator.py:473-504`)

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `relationship_parameter`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `st-live-cypher-relprop`, `st-live-cap-values`

- Expected: docs/KNOWN_ISSUES.md:89-95: 'A literal (a list or a map too), a parameter and a WITH's column are stored'; iris_vector_graph/cypher/translator.py:507-512 (_refuse_unstorable_rel_props: a parameter is stored, anything it cannot store is refused before writing).
- Observed at the pin: Live AUDITD (st-live-cypher-relprop, found by st-live-cap-values): CREATE (a:L {id: 'a2'})-[:R {q: $v}]->(b:L {id: 'b2'}), the same with $s/$o endpoint ids, with a number parameter, and MERGE (a:L {id: 'a4'})-[:R {q: $v}]->(b:L {id: 'b4'}) each answer no error and create the edge with no q (rdf_edges.qualifiers empty; r.q null). The same parameter between MATCHed endpoints and a literal q are stored. The literal-endpoint path (translator.py:10213-10222) resolves an ast.Literal or a FOREACH binding only, so a parameter resolves to None and is dropped as a null property (:10228).
- Source severity S2, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Resolve parameters (context.input_params) in the literal-endpoint path as _rel_literal_props does, or route such patterns through _rel_literal_props; refuse any property the writer cannot store instead of dropping it.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [query.writes](../ontology/features/cypher.g5.md#query.writes).

<a id="bug-led-007"></a>
### Erasing a tenant by prefix leaves its temporal-only events, and the redaction that follows completes while they stay readable

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Also recorded as: F-C1203 (playbook arm, S1, reproduced-live; [followup.json](../../experiment/playbook-completion/findings/audit/followup.json)); F-C1308 (playbook arm, S1, reproduced-live; [followup.json](../../experiment/playbook-completion/findings/audit/followup.json)). Severity differs: here Medium, playbook S1/S1; both are kept. (crosswalk)

Found by: [witness_prefix_erase_leaves_temporal_only_content](results/ledger_redaction/20261114T044401Z-prove/receipt.json) (W5) in [redaction.rs](models/ledger_redaction/redaction.rs), with control [prefix-erase-reaches-temporal](results/ledger_redaction/20261114T044554Z-control-prefix-erase-reaches-temporal/receipt.json) (EXPECTED_FAIL); review round2-core R2-1 (scratch witnesses d1/d2 showed the model's earlier erase over-approximated the product).

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: [erasure_prefix_temporal_only](receipts/native/erasure_prefix_temporal_only.json) — tenant `tE|` had two temporal-only events, one whose endpoint `tE|1` had a node row and one whose endpoint `tE|x` had none; `delete_nodes_by_prefix("tE|")` removed 1 node row; the `tE|x` event stayed readable after the erase and after the redaction, which reported `complete` with 4 records tombstoned; `verify()` was `equal`.

Expected: an erase removes graph content from every store that holds it, the temporal index included (ADR-0004; CONTEXT.md "Erasure"); a redaction is refused while any of the target's content is live (CONTEXT.md "Redaction"). Scope (review round 3 R3-reader H2): ADR-0013:37 documents the full tenant redaction for a tenant "whose relationships live in its own graph", and spec 256 ("Not in this spec", `spec.md:161-163`) put off "a tenant-scoped erase of the temporal tiers inside a shared graph" because "with one graph per tenant, `EraseGraph` covers it". The failing case — a tenant's temporal-only events in a shared graph — is therefore outside the documented recipe, but `delete_nodes_by_prefix` still promises erasure from every store (ADR-0004) and the redaction reports `complete` without saying anything is left.

Observed: `Eraser.EraseNodes` collects the IDs to erase from `Graph_KG.nodes` rows (`Eraser.cls:331-349`), and `TemporalIndex.EraseNodes` then erases temporal edges only for those IDs (`TemporalIndex.cls:400-440`). A temporal-only predicate writes no node row (`TemporalIndex.cls:103-114`; ADR-0015), so its events whose endpoints have no node row survive. `LiveRows` does not read the temporal index and verify ignores it, so neither notices.

Consequence: after an erase by prefix and a prefix redaction of a tenant that shares a graph the tenant's events stay readable through the window reader while the redaction reports complete, verify is equal, and the events' history is tombstoned. The documented prefix recipe misses them; removing them needs their endpoint IDs, then an explicit-id erase (`delete_node(id, graph=…)` or the store's `delete_nodes(ids)`, whose `EraseNodeIds` erases events incident on a named ID with or without a node row, `Eraser.cls:352-389`, `TemporalIndex.cls:421`) or `delete_temporal_edge` per event (review round 3 R3-3, code reading; not run natively).

Why Medium: lowered from High in review round 3, because the governing spec deferred this case and the documented recipe assumes one graph per tenant; it stays Medium because the incompleteness is silent (`complete`, `verify()` equal) for a privacy operation.

Repair proposal (not implemented): let `EraseNodes` and `TemporalIndex.EraseNodes` also select temporal endpoints by ID prefix, not only IDs that have node rows; count temporal entries as live content in redaction ([q-009](open_questions.md#q-009)). Without the first change, [simp-003](design_simplification.md#simp-003)'s full live-content check would turn every as-built prefix erase of such a tenant into a refusal until the events are removed by ID. Open part: [redaction.after-erasure.temporal](open_questions.md#q-009). Governing statements: [erasure.scope](../ontology/features/erasure.g5.md#erasure.scope), [erasure.prefix-match](../ontology/features/erasure.g5.md#erasure.prefix-match).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-003"></a>
### Redacting the whole default graph ignores node rows in named graphs and destroys the history of nodes that are still live

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Also recorded as: F-1304 (playbook arm, S1, reproduced-live; [13.json](../../experiment/playbook-completion/findings/audit/13.json)). Severity differs: here Medium, playbook S1; both are kept. (crosswalk)

Found by: [witness_default_graph_target_is_not_graph_blind](results/ledger_redaction/20261114T044401Z-prove/receipt.json) (W3); `witness_full_check_refuses_the_gaps` shows the stricter check refuses it and still admits the valid run. Review R1-core R1-7 and R1-8: the model's `Erase` removes named-graph node rows for a default-graph target, which the product's does not, so W3 builds the state directly.

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: [redaction_default_graph_whole](receipts/native/redaction_default_graph_whole.json) — ledger commit of nodes X, Y and an edge X→Y in graph `gN` (the ledger registers X and Y in `gN`); `erase_graph(None)`; nodes X and Y are still rows in `gN`. `redact(None)` completed and tombstoned 4 records of X and Y; `verify()` diverges afterwards.

Expected: spec 256 plan.md "The node-liveness check for a default-graph target is graph-blind" (node records and verify ignore graphs); ADR-0013 refusal while any row of the target is live.

Observed: `LiveRows` applies graph-blindness only with a prefix (LedgerRedact.cls:155-165); with no prefix it counts `graph_id = ''` rows only, while `Matches` takes every node record (graph "") (:93-94).

Consequence: an operator who erases the whole default graph and redacts it with no prefix (a narrow, operator-initiated trigger; the tenant recipe uses a prefix) loses the history of nodes that are still live in other graphs. Verify, which already diverged after the erase, can be returned to equal by an adoption, but the tombstoned history of those live nodes cannot be restored. The Eraser refuses the analogous empty prefix (Eraser.cls:314-318).

Repair proposal (not implemented): [simp-003](design_simplification.md#simp-003). Governing statement: [redaction.after-erasure.default-graph](../ontology/features/redaction.g5.md#redaction.after-erasure.default-graph).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-004"></a>
### A redaction reports complete while records it could not attribute still hold the target's content

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Found by: [witness_unattributed_qualifier_survives](results/ledger_redaction/20261114T044401Z-prove/receipt.json) (W4) and `lemma_complete_run_removes_every_target_record`, which needs premise P_ends.

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: [redaction_unattributed_qualifier](receipts/native/redaction_unattributed_qualifier.json) — an edge written by `engine.create_edge` (allowed outside strict mode), then qualified through the ledger by tuple (statement assigned, `set_qual` record only), then the tenant erased by prefix and redacted: receipt `complete=True`, `records_tombstoned=2`, `unattributed_records=1`, and one `set_qual` record still holds `uSecretQualifier`.

Expected: `ledger.redact` docstring and ADR-0013 "Every record of the target becomes a tombstone"; spec 256 FR-001 "MUST replace every record".

Observed: `LedgerRedact.Matches` answers -1 when a qualifier record's statement endpoints are unknown (no create/delete record, statement entry removed by the erase) (LedgerRedact.cls:101-110); `BatchInLock` skips it and counts it (:317-320); the run still completes. `unattributed_records` is not documented anywhere.

Consequence: tenant strings survive a "complete" redaction; only the undocumented receipt count reveals it.

Repair proposal (not implemented): [simp-002](design_simplification.md#simp-002); at minimum refuse completion (or report incomplete) while the count is above zero. Open choice: [redaction.unattributed](open_questions.md#redaction.unattributed).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-str-005"></a>
### create_edge stores the raw graph name in SQL, so a name with a NUL becomes a second SQL graph sharing one adjacency entry

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Found by: [witness_raw_sql_name_splits_one_index_graph](results/graph_structure/20261114T000451Z-prove/receipt.json) in [graph_structure.rs](models/graph_structure/graph_structure.rs) (B-structure O1/Q5; the model proves the key half only, and is injective only modulo `canonical`); A-structure Q5; review R2-data R1-4.

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: [graph_structure_keys](receipts/native/graph_structure_keys.json) case K4 — `create_edge` in graph `'g5k'` and in `'g5k'+NUL` gave two `rdf_edges` rows and one adjacency entry; `delete_edge(graph='g5k')` left the NUL row with no `^KG` entry, and `verify_graph("g5k")` then answers `ok` with no SQL edges, so the orphan row is invisible to it.

Expected: a graph key is derived from the canonical name and NUL is a transport artifact that is stripped (ADR-0003; `GraphKey.cls:23-37`; CONTEXT.md:50-58).

Observed: `create_edge` derives the index key from the canonical name (`nodes_edges.py:1197`) but binds `gid = graph or ""` to SQL (`nodes_edges.py:1213`), so the duplicate guard (`COALESCE(graph_id,'') = ?`, `:1217`) admits a second row; `create_node` binds the raw name with no validation (`nodes_edges.py:1019`).

Consequence: one index graph spans two SQL graphs; deleting through either name leaves a row without adjacency that traversal cannot see and `verify_graph` does not report.

Repair proposal (not implemented): bind `GraphKey.ForName` (the canonical name) to every SQL `graph_id` and validate in `create_node`. Governing statements: [graph.key.derive](../ontology/concepts/graph-scope.g5.md#graph.key.derive), [graph.names](../ontology/concepts/graph-scope.g5.md#graph.names).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-srch-006"></a>
### The embedding queue checks identity against the wrong table, and its IRIS worker writes default-graph entries with no identity check

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** The native probe could not run on Community (no `%Embedding.Config` at the table's width); severity is lowered one level from High.

Found by: [witness_queue_default_graph_misroutes and witness_queue_writes_into_claimed_table](results/search/20261114T000543Z-prove/receipt.json) in [search.rs](models/search/search.rs) (B-search O3/F8; control `queue-routes-default-graph`); A-search F8 and S4.

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none yet — [search_queue_default_graph](receipts/native/search_queue_default_graph.json) is INCONCLUSIVE (no `%Embedding.Config` with VectorLength 768).

Expected: 4.0.0 routing (one table per graph and model; "never derive a name to find a route"); `ClaimPendingBatch` carries `config` so the queue is not "the one write path that escapes the embedding identity registry" (`EmbedQueue.cls:108-111`).

Observed: `enqueue_for_embedding` checks every request against `kg_NodeEmbeddings` of the default graph whatever its graph (`embeddings.py:1838-1842`), refusing a named-graph request that `store_embedding` would route — the check the Python worker's docstring calls the 3.2.0 error (`:1993-1998`). `EmbedQueue.ProcessBatch` sends every default-graph entry to `kg_NodeEmbeddings` whatever its `config`, with no check (`EmbedQueue.cls:278-283, 316`).

Consequence: a model B vector can land in model A's table (read back as A's and compared with A's queries), and valid named-graph requests are refused.

Repair proposal (not implemented): resolve default-graph entries through the registry like named ones (or refuse them unless the entry's model owns `kg_NodeEmbeddings`), and check the target route at enqueue. Governing statements: [search.embedding.queue](../ontology/features/search.g5.md#search.embedding.queue), [search.embedding.check_on_write](../ontology/features/search.g5.md#search.embedding.check_on_write).

Evidence added (iteration 36, ordinary queue workflow W42; this entry's identity question was not probed): on a fresh 4.7.0 install the IRIS worker's write of any default-graph entry is refused (`graph_id` binds as NULL; [bug-srch-104](#bug-srch-104)), so this entry's IRIS-worker consequence cannot store a vector there today; it would return with that repair. An enqueue naming a model for the default graph was accepted against an undeclared `kg_NodeEmbeddings` ([observation](../uplift/consolidated/iteration-36/embed-queue-observed-20261117T001118Z.json), Q4). Decision and severity unchanged.


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-srch-008"></a>
### Under USE GRAPH, fusion reads a BM25 index built for another graph as this graph's

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; severity is lowered one level from High.

Found by: A-search F7.

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none

Expected: an index covers one graph and fusion answers one graph (spec 230 FR-009; the 4.6.0 R192 intent at `translator.py:3258-3261`).

Observed: `_index_graph_rows` returns None whenever `USE GRAPH` is set and never compares the index's recorded graph (`translator.py:3125-3141`); `ivg.retrieve` passes `bm25_name` unchecked (`:3283-3292`).

Consequence: node IDs ranked by graph h's text are joined to graph g's nodes, so g's answer is ranked by another graph's content.

Repair proposal (not implemented): compare the named index's recorded graph with the query's graph and refuse a mismatch. Governing statement: [search.fusion.same_graph](../ontology/features/search.g5.md#search.fusion.same_graph).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-plt-005"></a>
### The sample API's Cypher endpoints run translated SQL on a raw cursor, bypassing strict mode and the engine's statement protocol

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Found by: `theorem_strict_paths` (path `ApiSampleCypher`) and `witness_undocumented_bypasses_break_the_contract` in [platform.rs](models/platform/platform.rs) ([prove receipt](results/platform/20261114T002651Z-prove/receipt.json); B-platform W2); A-platform F-H3; A-cypher F3 ([intent](../uplift/ivg-verus-initial/intent/cypher.md)); A-ops candidate finding; reconstruction check 2(a)13 and 2(b)16; review R3-platform R1-11 (an undocumented bypass that contradicts the spec 213 contract).

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: [platform_strict_api_sample](receipts/native/platform_strict_api_sample.json) — with the ledger enabled and strict, `POST /api/cypher` of `api.main` committed a `CREATE` (row present, HTTP 200) while the same query through the engine raised `LedgerStrictModeError` and wrote nothing.

Expected: under strict mode `execute_cypher` with an updating clause is refused and changes nothing (spec 213 `contracts/ledger-api.md:82-92`); `read_only.py:3-7` lists these routes under the one write rule; each server call should do what an engine method does.

Observed: `api/routers/cypher.py:130-166` and GraphQL `executeCypher` (`api/gql/schema.py:174-200`) execute `translate_to_sql(...).sql` statement by statement on a bare cursor, skipping `_ledger_check("cypher_dml")` (`_engine/query.py:2300`), `write_txn`, the statement protocol (`__capture_ids__`, `__pin_stage__`, `__GRAPH_*` and others, handled only in `iris_sql_store.py:1617-1777`), result decoding and the native path. The same app mounts example GraphQL mutations such as `updateProtein`, a raw `UPDATE rdf_props` with no graph scope or guard.

Consequence: unrecorded structural writes under strict mode; Cypher `DELETE`, pinned `SET` and all-graphs writes in a multi-graph namespace cannot execute correctly on these routes.

Repair proposal (not implemented): route both through `engine.execute_cypher(read_only=…)`, keeping the hop cap and error redaction. Related: [query.routes](open_questions.md#query.routes). Governing statements: [access.ledger_strict.bypasses](../ontology/concepts/access.g5.md#access.ledger_strict.bypasses), [access.surfaces](../ontology/concepts/access.g5.md#access.surfaces).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-plt-006"></a>
### bulk_delete_adjacency deletes relationships under strict mode without a record

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Found by: `witness_undocumented_bypasses_break_the_contract` in [platform.rs](models/platform/platform.rs) ([prove receipt](results/platform/20261114T002651Z-prove/receipt.json); B-platform W1; control `g-bda-guarded`); review R3-platform R1-11 (an undocumented bypass).

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: [platform_strict_bulk_delete_adjacency](receipts/native/platform_strict_bulk_delete_adjacency.json) — with the ledger strict, the call deleted the edge (1 → 0 rows) and `verify()` went from `equal` to `diverges`.

Expected: under strict mode `create_node`, `create_edge` "and the other methods" are refused (USER_GUIDE:1107-1120; spec 213 contract); ADR-0004:81 says the method is removed.

Observed: `bulk_delete_adjacency` (`nodes_edges.py:2301-2338`) has no `_ledger_check` and deletes rows in every graph through `Eraser.EraseEdges`, one call per graph.

Consequence: an unrecorded structural delete in a namespace whose owner turned on strict mode to forbid them.

Repair proposal (not implemented): add the strict check (or remove the deprecated method, as ADR-0004 states). Governing statements: [access.ledger_strict.bypasses](../ontology/concepts/access.g5.md#access.ledger_strict.bypasses), [ledger.strict](../ontology/features/ledger.g5.md#ledger.strict), [erasure.entry-points.single-path](../ontology/features/erasure.g5.md#erasure.entry-points.single-path).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-plt-007"></a>
### The migrations' schema-check waiver also releases the refusal of a mismatched schema

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Found by: `witness_waiver_releases_a_mismatch` (W-S2) in [platform.rs](models/platform/platform.rs) ([prove receipt](results/platform/20261114T002651Z-prove/receipt.json); control `s-waive-checks`); A-platform F-S2; review R3-platform R1-5 (the mismatch case is decided by FR-006, which has no exception; only the no-record case stays open).

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: [platform_schema_waiver](receipts/native/platform_schema_waiver.json) — in a namespace recorded `Graph_KG`, an engine on `IVGPROBE` was refused (control), but the migrations' waived engine on `IVGPROBE` was not: its dry runs went ahead (one failed only because `IVGPROBE.RDF_EDGES` does not exist). No table or routine was written.

Expected: a mismatch is refused on first database access, before any write (spec 262 FR-006; ADR-0016:11); the waiver's recorded intent is only "may run before any 4.6.0 setup recorded the schema".

Observed: `graph_scoped_embeddings.py:287-288` and `temporal_structural_rows.py:85-89` build `IRISGraphEngine(conn)` from `IVG_SCHEMA_PREFIX` or the default and call `_waive_schema_check()` → `_schema_check_passed()` (`engine.py:1875-1890`), which releases any pending refusal, a mismatch included.

Consequence: where the other schema's tables exist (spec 262 FR-009's explicit two-schema case), `backfill_structural_rows` would write that schema's `rdf_edges` and the namespace's shared `^KG`, and the 4.0.0 embeddings and `^KG` steps, which address the default schema (`upgrade.py:145-152`), can rebuild the shared `^KG` from the other schema's rows.

Repair proposal (not implemented): waive only when no record exists, or build the migration engine on the recorded schema. Related question: [q-plt-011](open_questions.md#q-plt-011). Governing statements: [install.migration.schema](../ontology/concepts/install.g5.md#install.migration.schema), [install.schema.refusal](../ontology/concepts/install.g5.md#install.schema.refusal).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-plt-009"></a>
### The sample environment file sets IRIS_USER, but the server reads IRIS_USERNAME and silently connects as _SYSTEM

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only (re-read: `.env.sample:30`, `cypher_api.py:170`, `cli.py:47`). Severity is lowered one level from High (the server's login, the real privilege boundary, silently becomes a superuser).

Found by: A-platform F-H5 (sub-reader a, F6).

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none

Expected: the operator guide tells operators to give the server a non-superuser login; the IRIS login is the real privilege boundary.

Observed: `.env.sample:30` sets `IRIS_USER=_SYSTEM`, while `cypher_api._make_engine` and the CLI read `IRIS_USERNAME` with default `_SYSTEM` (`cypher_api.py:170`; `cli.py:47`).

Consequence: an operator who follows the sample and changes `IRIS_USER` to a restricted login still runs the server as `_SYSTEM`, a `%All` superuser, with no warning.

Repair proposal (not implemented): read one documented name (accept both with a warning), and fix the sample. Governing statements: [access.defaults](../ontology/concepts/access.g5.md#access.defaults), [access.iris_boundary](../ontology/concepts/access.g5.md#access.iris_boundary).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-cyp-002"></a>
### The native interpreter tells used relationships apart by CRC-32, so a hash collision drops a legitimate match

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; severity is lowered one level from High.

Found by: A-cypher F1.

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none

Expected: the compiled walk, the interpreter and the SQL path give the same answer (ADR-0014; spec 257 US1); the generated walk compares endpoints and key exactly (plan.md l. 24-26) and SQL compares `edge_id`.

Observed: `Neighbours` keeps the edges a match has used as a comma string of `$ZCRC($ListBuild(src, p, dst, ekey), 7)` and skips an edge whose hash is already there (`Exec.cls:1243-1244`).

Consequence: `MATCH (a:P)-[:K]->(b)-[:K]->(c) RETURN count(*)` over two edges whose tuples collide answers 0 in mode `off` and 1 in `sync` and SQL; node IDs are free text, so collisions can be constructed.

Repair proposal (not implemented): key used edges by the full `$ListBuild`, or hold them in a local array subscripted by the tuple. Governing statement: [query.native.equal-answers](../ontology/features/cypher.g5.md#query.native.equal-answers).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-led-001"></a>
### An adopting verify that races a redaction can append the redacted tenant's IDs after the redaction finished

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; the interleaving was not run. Severity is lowered one level from High.

Found by: A-history F5 (third bullet) ([intent](../uplift/ivg-verus-initial/intent/ledger-history.md)); A-ops hazard (c)2; review R1-core CV-3 and R1-6.

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none

Expected: after a complete redaction no record reachable through IVG holds the target's IDs (ADR-0013; spec 256 FR-001); an adoption records the current differences.

Observed: `verify(adopt=True)` checks the marker once, reads the divergence with no lock and commits the adoption without `expected_head` (`replay.py:806-858`). If it reads after the erase and before the redaction starts, and the redaction then runs to completion, the adoption is admitted (the marker is gone) and writes `delete_*` records naming the tenant's IDs after the redaction revision; `enable()` runs this adoption.

Consequence: tenant IDs re-enter the history after a redaction reported complete; a re-run of the redaction removes them, but nothing tells the operator to re-run.

Repair proposal (not implemented): commit the adoption with the head it read (`expected_head`) so a moved head refuses it, or refuse adoption of records that match a completed redaction's target. Governing statements: [ledger.verify](../ontology/features/ledger.g5.md#ledger.verify), [redaction.purpose](../ontology/features/redaction.g5.md#redaction.purpose).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-0106"></a>
### Property keys of a label mix graphs

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [01.json](../../experiment/playbook-completion/findings/audit/01.json) (live `breadth-a-live-01-install`; inspected `iris_vector_graph/_engine/schema.py:500-515`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-01-install`

- Expected: CONTEXT.md:38-43 / SYS-I2: an all-graphs read is the union of each graph's own answer; content of one graph never answers about another.
- Observed at the pin: graph B's key listed under graph A's label
- Source severity S2, confidence high; module 01; governing page here: `install.`.
- Remedy proposed by the playbook arm (not implemented): Join rdf_labels to rdf_props on (graph_id, s); a test with one id in two graphs.
- Reviewed-design control: `playbook-proofs-d1e` `control_f0106_keys_join_on_id` fails where expected in this run ([receipt](results/playbook-proofs-d1e/20261115T035515Z-control_f0106_keys_join_on_id/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1e/20261115T035416Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-0206"></a>
### Some Python readers join one graph's ids with another graph's data

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [02.json](../../experiment/playbook-completion/findings/audit/02.json) (live `breadth-a-live-02-identity`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-02-identity`

- Expected: USER_GUIDE.md:466-467 (graph= omitted means the default graph); HD-0201 (assumption): no join of ids from one scope to records of another.
- Observed at the pin: answered the default graph's node, which lacks the label
- Source severity S2, confidence high; module 02; governing page here: `graph. / structure.`.
- Remedy proposed by the playbook arm (not implemented): Hydrate each id from its own graph; give _filter_edges_by_properties and set_edge_weight a graph.
- Reviewed-design control: `playbook-proofs-d1e` `control_f0206_hydrate_from_default` fails where expected in this run ([receipt](results/playbook-proofs-d1e/20261115T035514Z-control_f0206_hydrate_from_default/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1e/20261115T035416Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-0507"></a>
### TemporalIndex.Purge wipes every graph's temporal index and leaves the marked rows

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [05.json](../../experiment/playbook-completion/findings/audit/05.json) (live `breadth-a-live-05-purge`; mc `breadth-a-mc-tmp_mark-as-built`; mc `breadth-a-mc-tmp_mark-reviewed`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-05-purge`

- Expected: ADR-0009 amendment: the marked row goes when the triple's last timestamp goes, in every graph; TMP-B9.13.
- Observed at the pin: both graphs' temporal stores wiped; marked rows and adjacency survive every purge
- Source severity S2, confidence high; module 05; governing page here: `temporal.`.
- Remedy proposed by the playbook arm (not implemented): Retract marked rows in Purge (or remove it) and fix the create_edge_temporal docstring that advises calling it.
- Reviewed-design control: `playbook-proofs-d1c` `control_f0507_purge_keeps_rows` fails where expected in this run ([receipt](results/playbook-proofs-d1c/20261115T035824Z-control_f0507_purge_keeps_rows/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1c/20261115T035754Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-0801"></a>
### Ledger strict mode is a cached client check that fails open (Cypher writes)

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0801`; inspected `iris_vector_graph/ledger/guard.py:20-80`; inspected `iris_vector_graph/_engine/query.py:2299-2301`; run `b-08-run-unit`; mc `b-mc-m11-guard-as-built-ttl`; mc `b-mc-m11-guard-as-built-failopen`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0801`, `b-08-live-f0801-rerun`

- Expected: In strict mode a guarded Cypher write raises LedgerStrictModeError and changes nothing (specs/213-graph-revision-ledger/contracts/ledger-api.md:82-92; CYP-X7.2). Decision HD-0801 (assumption): keep modelling the Python guard, cache and fail-open; the intended refusal still applies.
- Observed at the pin: Live, two IRIS processes on AUDITB (b-08-live-f0801): process A's engine wrote once (guard cached state never-enabled); process B enabled the ledger and set strict (Meta: enabled, strict, head_seq 1); 0.28 s later A ran `CREATE (:B08G {id:'b08_g1'})`, which succeeded (row written, journal: nodes/rdf_labels/rdf_props/^KG) and was not recorded (head_seq 1 before and after). B's fresh engine was refused at once and A was refused after the 5 s TTL (LedgerStrictModeError). Source: guard caches Meta for TTL_SECONDS=5.0 and treats any probe exception as never-enabled (iris_vector_graph/ledger/guard.…
- Source severity S2, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Either document the 5 s window and fail-open in ledger-api.md and USER_GUIDE, or check strict mode fail-closed per write (or server-side in Txn_Begin / a trigger) so raw SQL and other clients are covered (HD-0801 options b/c).
- Reviewed-design control: `playbook-proofs-breadth` `control_f0801_ttl_cache` fails where expected in this run ([receipt](results/playbook-proofs-breadth/20261115T035553Z-control_f0801_ttl_cache/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-breadth/20261115T035528Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-0819"></a>
### approx_count_distinct in an all-graphs read merges graphs

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0819`; mc `m08-scope-as-built-hll`; inspected `iris_vector_graph/_engine/query.py:4361-4421`; live `b-08-live-f0819-rerun`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0819`, `b-08-live-f0819-rerun`

- Expected: CYP-I4.14: an approximate count in an all-graphs read counts each graph's nodes apart.
- Observed at the pin: Live: `MATCH (a {node_id:'b08_x'})-[:B08R*1..2]->(m) RETURN approx_count_distinct(m)` took the HLL route (sql CountDistinctKHop, warning HLL-256) and answered 2; the exact count(DISTINCT m) answered 1 (b08_leak is reachable only through graph b08gB's edge from the shared id b08_m).
- Source severity S2, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Take the HLL route only when no named graph has edges (as the k-hop shortcut at query.py:4318-4320 does), with a unit test.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-0901"></a>
### Two plan shapes with one 32-bit checksum share one compiled class

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [09.json](../../experiment/playbook-completion/findings/audit/09.json) (live `b-09-f0901-collision`; mc `m09-planc-as-built-collide-I3`; mc `m09-planc-as-built-collide-binding`; mc `m09-planc-as-built-collide-progress`; mc `m09-planc-reviewed`; mc `m09-planc-control-shared-name`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-09-f0901-collision`

- Expected: ADR-0014 (docs/adr/0014-native-plans-are-compiled-to-classes-at-run-time.md:19): 'A compiled class answers exactly as the interpreter does'; NAT-I3 (a read never runs code written for another plan shape); NAT-T5.16.
- Observed at the pin: Live (b-09-f0901-collision): a birthday search in IRIS over label names of one length found two labels B09QXAYMSHXLZD / B09QWCSOJEBLDF whose plan shapes share $ZCRC(shape,7) = 1912394325 after 90195 candidates (0.23 s); hashes of the separately compiled shapes: {'B09QXAYMSHXLZD': ['1912394325'], 'B09QWCSOJEBLDF': ['1912394325']}. In job mode (one process) a read of the B09QWCSOJEBLDF shape (its build job compiling) then a read of the B09QXAYMSHXLZD shape left one entry, status ['ok']; the next B09QXAYMSHXLZD read answered [[2]] where the SQL path answers [[1]]; a shadow-mode engine raised Nat…
- Source severity S2, confidence high; module 09; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Name the class by a digest wide enough to rule out collisions (the SHA-256 Digest already computes) or a counter, keep the shape check, and have Build verify under its lock that the entry still holds the shape it compiled before marking it ok.
- Reviewed-design control: `playbook-proofs-d1d` `control_f0901_shared_class_name` fails where expected in this run ([receipt](results/playbook-proofs-d1d/20261115T035702Z-control_f0901_shared_class_name/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-0902"></a>
### The interpreter tells relationships apart by a 32-bit checksum

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [09.json](../../experiment/playbook-completion/findings/audit/09.json) (live `b-09-f0902-collision`; mc `m09-used-as-built`; mc `m09-used-reviewed`; mc `m09-used-control-type-only`; inspected `iris_src/src/Graph/KG/Cypher/Exec.cls:1236-1250`; inspected `iris_src/src/Graph/KG/Cypher/Gen.cls:410-433`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-09-f0902-collision`

- Expected: NAT-B1.11 (two different relationships in one match are never taken as the same one); ADR-0014:19 (compiled = interpreted); spec 253 FR-002 (same answer as the SQL path).
- Observed at the pin: Live (b-09-f0902-collision): relationships b09_xxaymshxlzd-[:B09T]->b09_hub and b09_xwcsojebldf-[:B09T]->b09_hub share $ZCRC($LB(src,p,dst,""),7) = 1045711388 (found after 90195 candidates). MATCH (a:B09P)-[:B09T]->(h:B09H)<-[:B09T]-(c:B09P) RETURN count(*): SQL path [[2]], interpreter (off mode) [[0]], compiled walk (sync) [[2]]; a control pair without a collision: SQL [[2]], interpreter [[2]]; shadow mode on the interpreted read: NativeMismatch. Model m09-used-as-built; reviewed exact identity passes.
- Source severity S2, confidence high; module 09; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Keep used relationships as exact subscripts (a local array keyed by $LB(src, p, dst, ekey)) instead of checksums in a string.
- Reviewed-design control: `playbook-proofs-d1d` `control_f0902_crc_identity` fails where expected in this run ([receipt](results/playbook-proofs-d1d/20261115T035705Z-control_f0902_crc_identity/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-1001"></a>
### A native reader answers default-graph calls in a namespace where a named graph has edges

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `blocked-access`, not a native reproduction; severity is one level below the mapped High.

**Conditional:** the playbook arm could not reach the deciding state (`blocked-access`).

Found by: playbook arm, [zz-versions.json](../../experiment/playbook-completion/findings/audit/zz-versions.json) (probe `b-10-probe-units`; mc `m10-routes-as-built-pagerank-scope`; mc `m10-routes-as-built-pagerank-scope-default-only-lib`; mc `m10-routes-reviewed`; mc `m10-routes-control-no-probe`; inspected `iris_vector_graph/arno_readers.py:257-280`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none (blocked-access)

- Expected: spec 236 FR-014a: a native reader 'MUST be used only for the graph scope its proof covers' (specs/236-arno-callout-adoption/spec.md:268-272); ALG-I3 / SYS-I2 (a default-graph answer never mixes in a named graph's edges); the BFS route and the ^NKG tiers probe for named-graph edges (iris_vector_graph/stores/iris_sql_store.py:1842-1858, :3322).
- Observed at the pin: Source at the pin: arno_readers.route takes no named-graph input and answers native for graph '' (iris_vector_graph/arno_readers.py:257-280); _execute_pagerank routes with no named_graph_with_edges probe (iris_sql_store.py:2388-2400). Probe b-10-probe-units ran the pin's route(): 'native' for graph '' with no parameter that could carry named-graph edges. Model m10-routes-as-built-pagerank-scope finds the mixed answer only with a library whose reader is graph-blind; with a graph-0-only reader (m10-routes-as-built-pagerank-scope-default-only-lib) it passes: the outcome hinges on the open premis…
- Source severity S1, confidence medium; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Route to a native reader only when named_graph_with_edges() is None (as BFS and the ^NKG tiers do), or add a named-graph fixture to the reader gate and record graph scope in the proof; then a live test in USER with arno-callout 1.2.1 loaded and a named graph's edges.
- Recorded in 10.json, zz-versions.json; the later file's record is used.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-1006"></a>
### Subgraph vectors are read by node id in every graph

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [10.json](../../experiment/playbook-completion/findings/audit/10.json) (live `b-10-live-scope2`; inspected `iris_vector_graph/_engine/algorithms.py:850-880`; inspected `iris_vector_graph/schema.py:429-437`; inspected `iris_src/src/Graph/KG/Subgraph.cls:6-11`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-10-live-scope2`

- Expected: ALG-I3 (a default-graph call never mixes in a named graph's content); the table is keyed (graph_id, node_id) (iris_vector_graph/schema.py:429-437).
- Observed at the pin: Live (b-10-live-scope2; the first run's fixture violated the (graph_id, node_id) foreign key): kg_NodeEmbeddings held rows [['', 'b10_s', '1,0,0,0'], ['b10g1', 'b10_s', '0,0,0,1']] for b10_s (in both graphs); kg_SUBGRAPH(['b10_s'], include_embeddings=True) returned [0.0, 0.0, 0.0, 1.0] (default-graph vector [1.0, 0.0, 0.0, 0.0], named-graph vector [0.0, 0.0, 0.0, 1.0]).
- Source severity S2, confidence medium; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Add graph_id = '' to the read, correct the comment that the walk is namespace-wide, and test with two graphs.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-1108"></a>
### Two write paths skip the strict-mode guard

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [11.json](../../experiment/playbook-completion/findings/audit/11.json) (live `b-11-live-footprints-2`; live `ib-HD1103-bulk-delete-adjacency`; live `c16-s3-graphql-sample-api`; mc `m11-guard-as-built-unguarded`; mc `m11-guard-reviewed`; inspected `iris_vector_graph/_engine/nodes_edges.py:2301-2339`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-11-live-footprints-2`, `ib-HD1103-bulk-delete-adjacency`, `c16-s3-graphql-sample-api`

- Expected: docs/USER_GUIDE.md:1107-1109 (strict mode refuses create_node, create_edge and the other methods); ledger-api.md:82-93 lists the guarded calls and names only BulkLoader and raw SQL as unguarded; decisions.md HD-1103 (supported: client-side guard on the specified methods; inventory uncovered Python paths).
- Observed at the pin: Live AUDITB (b-11-live-footprints-2): strict on; engine.create_node refused (LedgerStrictModeError) but engine.bulk_delete_adjacency(['b11_a']) deleted the recorded edge b11_a-B11S-b11_b through Graph.KG.Eraser.EraseEdges; the journal shows rdf_edges, ^KG, ^NKG and ^IVG.Ledger stmt/tuple written in the eraser's own transaction with no head lock; verify diverges on that rel. GraphQL create_protein called directly on this connection failed SQLCODE -30 (unqualified SQLUSER.NODES), so that write did not land here; the resolver has no guard (api/gql/resolvers/mutation.py:23-230) and the sample API…
- Source severity S2, confidence high; module 11; governing page here: `ledger.`.
- Remedy proposed by the playbook arm (not implemented): Call the guard in bulk_delete_adjacency and the GraphQL mutations (or document them as unguarded next to BulkLoader and raw SQL); extend tests/integration/test_ledger_us05_compat.py::test_every_guarded_api_is_rejected_and_nothing_changes.
- Reviewed-design control: `playbook-proofs-breadth` `control_f1108_unguarded_bulk_delete` fails where expected in this run ([receipt](results/playbook-proofs-breadth/20261115T035559Z-control_f1108_unguarded_bulk_delete/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-breadth/20261115T035528Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-1201"></a>
### A graph erasure removes the statement entry of an edge a concurrent ledger commit creates

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [12.json](../../experiment/playbook-completion/findings/audit/12.json) (run `live-f1201-reproduced`; run `live-erase-vs-commit-fk`; run `live-erase-vs-commit-emptygraph`; original `mc:erasure-as-built`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM)

- Expected: No recorded live edge loses its statement entry (ERS-I3; ADR-0004: 'no live statement outlives its content' and the ledger's statement map tracks every live recorded edge). HD-1201 working answer: erase serializes with same-target commits.
- Observed at the pin: Reproduced on the pin 8/8: EraseGraph takes no ledger head lock (Eraser.cls:47-261) and EraseLedgerFor (Eraser.cls:1117-1144) dirty-reads every statement entry; it killed the committer's ^IVG.Ledger("stmt",4001) and tuple after the commit wrote them; the edge u-R-v, its nodes and adjacency stayed live in G with no statement entry. Journal order is the oracle. With an edge in the graph the same race instead makes the erase fail with an FK error and roll back (8/8); with a short statement scan the eraser wins the race (8/8).
- Source severity S2, confidence high; module 12; governing page here: `erasure.`.
- Remedy proposed by the playbook arm (not implemented): Serialize graph erasure with ledger commits into the same graph (for example take the ledger head lock, or a per-graph lock both take, around the statement cleanup), or make the cleanup remove only statements whose edge rows the same transaction deleted.
- Reviewed-design control: `playbook-proofs-d9c` `control_f1201_erase_unlocked` fails where expected in this run ([receipt](results/playbook-proofs-d9c/20261115T040828Z-control_f1201_erase_unlocked/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d9c/20261115T041012Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-1401"></a>
### verify() reports divergence after a logged detach-delete involving named-graph edges

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [14.json](../../experiment/playbook-completion/findings/audit/14.json) (run `live-native-rerun-1314`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM)

- Expected: RPL-B7: verify says equal when every change went through the ledger.
- Observed at the pin: Fresh rerun: verify on the built world already diverges, only on tenantA|n3 (the detach delete kept its named-graph row).
- Source severity S2, confidence high; module 14; governing page here: `ledger.readers`.
- Remedy proposed by the playbook arm (not implemented): Make the ledger's detach-delete and verify agree on node identity across graphs (HD-1401/HD-1101).
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-1507"></a>
### The bridge anchor lookup matches a node of that id in any graph

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [15.json](../../experiment/playbook-completion/findings/audit/15.json) (live `c15-live-bridge`; inspected `iris_vector_graph/_engine/fhir.py:444-481`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c15-live-bridge`

- Expected: migrate_fhir_bridges_to_crosswalk documents 'Bridges point at default-graph nodes' (fhir_graph.py:650-652); INT-B1.3; SYS-I2.
- Observed at the pin: Live (c15-live-bridge): with node c15:anchor only in named graph c15g3 and a bridge row C15CODE1 -> c15:anchor, get_kg_anchors(['C15CODE1']) returned ['c15:anchor'] (JOIN nodes ON node_id only, fhir.py:470-477).
- Source severity S2, confidence high; module 15; governing page here: `fhir.`.
- Remedy proposed by the playbook arm (not implemented): Add COALESCE(n.graph_id,'') = '' (the bridges' graph) to the join.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-1614"></a>
### The demo server's write routes need no key

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [16.json](../../experiment/playbook-completion/findings/audit/16.json) (live `c16-s8-followup`; inspected `src/iris_demo_server/app.py:1-22`; inspected `src/iris_demo_server/routes/fhir.py:503-533`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c16-s8-followup`

- Expected: CHANGELOG.md:994-996 says every app needs the key; API-B13.2.
- Observed at the pin: Live (c16-s8-followup): demo server started with IVG_API_KEY set; without the key GET /api/status/none answered 404 and POST /api/fhir/live/add answered 400 (validation reached, not 401). Source: src/iris_demo_server/app.py:1-22 adds no ApiKeyMiddleware; routes/fhir.py:503-533 write to the FHIR repository and start a sync; __main__ binds 0.0.0.0:8200 (app.py:503-504).
- Source severity S2, confidence high; module 16; governing page here: `access.`.
- Remedy proposed by the playbook arm (not implemented): Add ApiKeyMiddleware and bind 127.0.0.1 by default, or document the demo server as presenter-only.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-1709"></a>
### deploy/README.md promises a refusal the server does not make

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped High.

Found by: playbook arm, [17.json](../../experiment/playbook-completion/findings/audit/17.json) (inspected `iris_vector_graph/cli.py:415-441`; inspected `iris_vector_graph/_api_key.py:15-30`; inspected `deploy/README.md:84-88`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none (confirmed-source)

- Expected: deploy/README.md:86: the server refuses auth: none with host 0.0.0.0 unless --force-no-auth.
- Observed at the pin: Confirmed in source: `ivg server start` defaults --host 0.0.0.0 and has no --force-no-auth (cli.py:419-426); auth is off when IVG_API_KEY is unset (iris_vector_graph/_api_key.py:21-23); no code reads IVG_AUTH_MODE (deploy/docker/compose.yml:34). HD-1705 working decision: local-only default or explicit opt-in.
- Source severity S1, confidence high; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): Per HD-1705: default to 127.0.0.1 or require an explicit opt-in for unauthenticated external binding; align the docs.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-1806"></a>
### Graph.KG.Snapshot.ImportGlobals loads any global file without the allow-list

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [18.json](../../experiment/playbook-completion/findings/audit/18.json) (live `c18-live-file-helpers`; inspected `iris_src/src/Graph/KG/Snapshot.cls:4-73`; live `ws-live-snap-importglobals`; live `rx-live-18`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c18-live-file-helpers`, `ws-live-snap-importglobals`, `rx-live-18`

- Expected: SNP-X5.1 (every way to load globals keeps to the restore allow-list); snapshot.py:412-422 (an archive is a file anyone can write).
- Observed at the pin: Live (c18-live-file-helpers): Graph.KG.Snapshot is deployed in AUDITC with ['Decode', 'DeleteDir', 'Encode', 'ExportGlobals', 'FileExists', 'GetFileSize', 'ImportGlobals', 'IsVector', 'NodeRef', 'NodeValueJSON', 'ReadFileChunk', 'SetNodeJSON', 'WriteFileChunk']; ImportGlobals('/nonexistent-ivgaudit-c18/') answered {"imported":0} - callable over the Native API; its body runs $System.OBJ.Load on every *.gof (Snapshot.cls:24-35) with no list. No product code calls it.
- Source severity S2, confidence high; module 18; governing page here: `install.snapshot`.
- Remedy proposed by the playbook arm (not implemented): Delete the unused methods, or apply the restore allow-list.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-C0150"></a>
### Every initialize_schema moves a node with a '__graph' property into that graph (add_graph_id_to_nodes), and the engine still writes such a property: an unrecorded cross-graph move, also into a graph…

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-writesets.json](../../experiment/playbook-completion/findings/audit/zz-writesets.json) (live `ws-live-migrations`; inspected `iris_vector_graph/schema.py:1514-1637`; inspected `iris_vector_graph/schema.py:704-722`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `ws-live-migrations`

- Expected: CHANGELOG.md:5229-5240 (spec 214: graph_id is a real column, the __graph pseudo-property is legacy) and iris_vector_graph/_engine/nodes_edges.py:1058 ('spec 214 FR-019: __graph pseudo-property no longer written'); iris_vector_graph/ledger/changeset.py:31 (the ledger reserves '__graph'); while a redaction runs the target stays not live (ADR-0013:17, RED-B5).
- Observed at the pin: Live in AUDITB (ws-live-migrations): graph wsagG (a ledger relationship, erased) with a bounded redaction's marker; engine.create_node('wsag|z', properties={'__graph': 'wsagG'}) stored a '__graph' property row in the default graph; GraphSchema.add_graph_id_to_nodes, which ensure_indexes runs on every initialize_schema (schema.py:719, _engine/schema.py:2514), answered rows_migrated 1: node wsag|z now has graph_id wsagG and the property is gone; wsagG has 1 live node row while its marker exists, and a re-run is refused target_live. The ledger recorded nothing (create_node is not a ledger write…
- Source severity S2, confidence high; module 01; governing page here: `install.`.
- Remedy proposed by the playbook arm (not implemented): Refuse '__graph' as a property key on every write path (as the ledger does), and run the __graph migration only once, when the graph_id column is added (not on every initialize_schema).
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-C0151"></a>
### retract_inference deletes any relationship whose qualifiers contain a key named 'inferred', a ledger relationship included, leaving its statement live

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-writesets.json](../../experiment/playbook-completion/findings/audit/zz-writesets.json) (live `ws-live-stmt-collision`; inspected `iris_vector_graph/_engine/schema.py:3186-3259`; inspected `iris_vector_graph/_engine/schema.py:61`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `ws-live-stmt-collision`

- Expected: iris_vector_graph/_engine/schema.py:3187 (retract_inference deletes 'the edges materialize_inference wrote'); INV-stmt / ERS-I2 (no live statement without its row).
- Observed at the pin: Live in AUDITB (ws-live-stmt-collision): a ledger relationship wsq|x -RI-> wsq|y created with qualifiers {'inferred': 'user'} (stored {"inferred":"user"}, statement 3 live); engine.retract_inference() returned 1 and deleted that row (DELETE ... WHERE qualifiers LIKE '%"inferred":%', schema.py:61, 3224); statement 3 stays live with no row; verify() = diverges (unrecorded_writes).
- Source severity S2, confidence high; module 01; governing page here: `install.`.
- Remedy proposed by the playbook arm (not implemented): Identify inferred rows by a marker no user qualifier can carry (reserve the key in the ledger and the writers), or skip rows that have a live statement.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-C0341"></a>
### get_json_field_values pastes the field name into its SQL text, so a field name can change the statement

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (live `st-live-susp-json-field`; inspected `iris_vector_graph/_engine/nodes_edges.py:916-930`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `st-live-susp-json-field`

- Expected: SQL text carries only constants and identifiers the code controls, values are bound (the product's own pattern elsewhere: _validate, sanitize_identifier; F-0815 for the same class of defect in Cypher); get_json_field_values(key, field) answers the field's values inside the key's blobs (iris_vector_graph/_engine/nodes_edges.py:916-930).
- Observed at the pin: Live AUDITD (st-live-susp-json-field), scratch rows jf:1 'meta' = {"color": "red"} and jf:2 'private' = {"color": "blue"}: get_json_field_values('meta', 'color') answers ['red']; a field containing one quote makes the statement fail ('Incorrect number of parameters'); a crafted field ending in ... WHERE "key" <> ? AND (1 = 1 OR val LIKE ?) -- turns the statement into a read of every other key and answers ['blue'] from the 'private' row. The field is formatted into a string literal of the select list (nodes_edges.py:921-922) and into the LIKE pattern (:926). The query also has no graph predica…
- Source severity S2, confidence high; module 03; governing page here: `structure. / install.bulk_load`.
- Remedy proposed by the playbook arm (not implemented): Bind the field: build the marker with a parameter (SELECT $PIECE($PIECE(val, ?, 2), '"', 1) ... with the bound text '"' + field + '": "'), escape % and _ in the LIKE pattern with an ESCAPE clause, or validate field against a strict identifier pattern; add a graph predicate.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-C0901"></a>
### A build marks whatever entry its hash holds as ok, so one shape's entry can run another shape's class for good

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [09.json](../../experiment/playbook-completion/findings/audit/09.json) (live `b-09-f0901-collision`; mc `m09-planc-as-built-collide-binding`; mc `m09-planc-reviewed`; inspected `iris_src/src/Graph/KG/Cypher/Gen.cls:175-182`; inspected `iris_src/src/Graph/KG/Cypher/Gen.cls:207`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-09-f0901-collision`

- Expected: NAT-T5.16 (a ready entry runs only the class written for its own shape) and NAT-I3; ADR-0014:19.
- Observed at the pin: Live (b-09-f0901-collision): a birthday search in IRIS over label names of one length found two labels B09QXAYMSHXLZD / B09QWCSOJEBLDF whose plan shapes share $ZCRC(shape,7) = 1912394325 after 90195 candidates (0.23 s); hashes of the separately compiled shapes: {'B09QXAYMSHXLZD': ['1912394325'], 'B09QWCSOJEBLDF': ['1912394325']}. In job mode (one process) a read of the B09QWCSOJEBLDF shape (its build job compiling) then a read of the B09QXAYMSHXLZD shape left one entry, status ['ok']; the next B09QXAYMSHXLZD read answered [[2]] where the SQL path answers [[1]]; a shadow-mode engine raised Nat…
- Source severity S2, confidence high; module 09; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Under its lock, Build writes the entry only if it still holds the shape (or digest) it compiled; otherwise it deletes the class and leaves the entry.
- Reviewed-design control: `playbook-proofs-d1d` `control_fc0901_mark_any_entry` fails where expected in this run ([receipt](results/playbook-proofs-d1d/20261115T035703Z-control_fc0901_mark_any_entry/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-C1150"></a>
### A plain SQL INSERT into Graph_KG.ledger_revisions is accepted, and a row planted at head+1 made the next ledger commit fail

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-writesets.json](../../experiment/playbook-completion/findings/audit/zz-writesets.json) (live `ws-live-sql-insert-wedge`; live `ws-live-sql-guard`; inspected `iris_src/src/Graph/KG/LedgerRevision.cls:44`; inspected `iris_src/src/Graph/KG/LedgerRevision.cls:87-108`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `ws-live-sql-insert-wedge`, `ws-live-sql-guard`

- Expected: iris_src/src/Graph/KG/LedgerRevision.cls:1-5 ('one immutable row per committed revision ... Written only by Graph.KG.Ledger.Commit inside the commit transaction'; UPDATE and DELETE are rejected, FR-023).
- Observed at the pin: Live in AUDITB (ws-live-sql-insert-wedge): with head seq 3, an SQL INSERT of a row with seq 4 and every required column was accepted (the table has UPDATE and DELETE triggers, no INSERT trigger); the next engine.ledger.commit (the only one attempted after the INSERT) failed LedgerInconsistencyError 'revision row save failed: ERROR #5805: ID key not unique ... ^Graph.KG.LedgerRevisionD(4) exists'; verify() still answered equal. An INSERT of an existing seq is refused (SeqIdx) and UPDATE is refused (trigger) (ws-live-sql-guard), so the INSERT cannot rewrite history; it blocks the ledger.
- Source severity S2, confidence high; module 11; governing page here: `ledger.`.
- Remedy proposed by the playbook arm (not implemented): Add an INSERT trigger (or %OnBeforeSave check) that refuses a row outside Ledger.Commit's transaction, as for UPDATE and DELETE; and have verify() report a revision row with no records.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-C1303"></a>
### A bounded redaction (max_batches) restarts its scan at the first record and may never finish

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [13.json](../../experiment/playbook-completion/findings/audit/13.json) (run `live-fc1303-bounded-resume`; run `core-m2-as-built-paced-resume`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM)

- Expected: LedgerRedact.cls:178-180: 'pMaxBatches > 0 stops after that many batches and leaves the run in progress; running the same target again resumes it.' RED-B8 (a stopped run resumes); spec 256 SC-003 (batching).
- Observed at the pin: Live on the pin: 60 calls with batch 1 and max_batches 1 each re-scanned the first 20 records (batch x SCANFACTOR cap, :306-310) from the start (:213), tombstoned nothing and returned complete=false; 9 target records remained. The same world completes with max_batches 0. Model: core M2 paced-resume progress mutant and AG EF failure.
- Source severity S2, confidence high; module 13; governing page here: `redaction.`.
- Remedy proposed by the playbook arm (not implemented): Persist the scan cursor with the marker (or start each call after the last tombstoned position) so a resumed call continues where the previous one stopped.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-C1304"></a>
### IVG's own snapshot archives keep an erased and redacted tenant, the receipt does not name them, and a restore brings the tenant back

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [followup.json](../../experiment/playbook-completion/findings/audit/followup.json) (live `fu-r01a-snapshot-copies`; inspected `iris_vector_graph/cypher_api.py:668-678`; inspected `iris_vector_graph/_engine/snapshot.py:387-422`; inspected `iris_vector_graph/_engine/snapshot.py:1035`; inspected `iris_src/src/Graph/KG/LedgerRedact.cls:504-508`; live `c18-live-ledger-overlay`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `fu-r01a-snapshot-copies`, `c18-live-ledger-overlay`

- Expected: specs/256-ledger-tenant-redaction/spec.md:42-44 (US1: afterwards 'no record, revision field or index reachable through IVG holds the tenant's entity ids, attribute values or messages'; the receipt says 'what stayed out of reach'); spec.md:127-128 (FR-008: the receipt states what stays out of reach); docs/adr/0013-redaction-removes-content-from-history.md:47-48 ('Together they cover everything IVG can reach'; out of reach: export_reconstruction files, journals, backups); iris_src/src/Graph/KG/LedgerRedact.cls:504-508 (the receipt's out_of_reach: exactly those three).
- Observed at the pin: Live in AUDITA (fu-r01a-snapshot-copies): tenant fu1|x committed through the ledger with a secret property, message, source, correlation id and idempotency key; engine.save_snapshot (the call POST /admin/snapshot makes with $IVG_SNAPSHOT_DIR or the temp folder, iris_vector_graph/cypher_api.py:668-678) taken before the erase, after the erase and after the redaction; delete_nodes_by_prefix + ledger.redact(None, prefix='fu1') complete, verify() equal, and the SC-001 scan of ^IVG.Ledger and Graph_KG.ledger_* finds none of the six tenant tokens. The pre-erase archive holds the tenant in sql/Graph_…
- Source severity S2, confidence high; module 13; governing page here: `redaction.`.
- Remedy proposed by the playbook arm (not implemented): Name IVG's own archives (save_snapshot files, including those POST /admin/snapshot writes to $IVG_SNAPSHOT_DIR or the temp folder) in the receipt's out_of_reach and in ADR-0013's reach statement; optionally refuse or warn on restoring an archive older than a completed redaction (HD-1801's re-apply of live redactions) and give the HTTP snapshot a retention rule.
- Reviewed-design control: `playbook-proofs-d1b` `control_fc1304_receipt_omits_archives` fails where expected in this run ([receipt](results/playbook-proofs-d1b/20261115T035739Z-control_fc1304_receipt_omits_archives/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1b/20261115T035711Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-C1307"></a>
### A writer that keeps the target live holds a redaction open indefinitely, and while it is open every tenant's record readers, verify() and other redactions are refused

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [followup.json](../../experiment/playbook-completion/findings/audit/followup.json) (live `fu-r03-marker-held-open`; inspected `iris_src/src/Graph/KG/LedgerRedact.cls:202-211`; inspected `iris_src/src/Graph/KG/LedgerRedact.cls:393-441`; inspected `iris_vector_graph/ledger/client.py:682-693`; inspected `iris_vector_graph/cypher_api.py:628-643`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `fu-r03-marker-held-open`

- Expected: docs/adr/0013-redaction-removes-content-from-history.md:18 (Batches: while the marker exists 'a commit with a record in the target is refused'; 'Re-running the same redaction resumes it'); specs/256-ledger-tenant-redaction/spec.md:156 (Decision 3), :125 (FR-006), :148 (SC-004: other tenants' verify() result unchanged); iris_vector_graph/ledger/client.py:633-660 (redact docstring: calling again resumes the run).
- Observed at the pin: Live in AUDITA (fu-r03-marker-held-open, two connections): tenant fa3 erased, a bounded run (batch 1, max_batches 1) left the marker. engine.create_node('fa3|zombie') on a non-strict ledger was accepted (no non-ledger writer reads the marker), while a ledger commit into fa3 was refused. Running the redaction again was refused at the entry liveness check ('still holds 4 live row(s)', LedgerRedact.cls:207-211). A run that passed the entry check while a second connection held the head lock tombstoned every remaining fa3 record, and after a bypass write during the wait Final refused ('became live…
- Source severity S2, confidence high; module 13; governing page here: `redaction.`.
- Remedy proposed by the playbook arm (not implemented): Either make the marker binding on every writer of the content tables (the non-ledger write paths, Cypher updating clauses, POST /admin/load and the temporal mirror refuse a write into the marked target), or scope the readers' refusal to the marked target and add an operator abandon/rollback for a run that cannot finish; state 'no writer makes a marked target live' as a progress premise (P-C02).
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-C1547"></a>
### get_reifications reads the reifier's properties from every graph

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (live `st-live-reads-b`; control `st-control-reads-selftest`; inspected `iris_vector_graph/_engine/schema.py:3335-3360`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `st-live-reads-b`

- Expected: get_reifications returns the reifiers of rdf_edges row edge_id with their properties (iris_vector_graph/_engine/schema.py:3335-3339); a reifier node is an ordinary node of one graph (15-integrations.md INT-D19, INT-E1; reify_edge writes it in the default graph, INT-E1.6 / F-1502), and since spec 227 a node id is unique per graph, not per namespace (iris_vector_graph/schema.py:383-391); content of one graph never shows up in an answer about another graph (00-system.md SYS-I2).
- Observed at the pin: Live AUDITD (st-live-reads-b, non-interference oracle with self-test st-control-reads-selftest): default-graph edge a-R-b reified as rf1 with props {p: '1'}; adding a node rf1 in named graph stg2 with props {p: '2', q: 'x'} (and a reification of another edge) changed get_reifications(edge a-R-b) from [{reifier_id: rf1, properties: {id: rf1, p: '1'}}] to [{reifier_id: rf1, properties: {id: rf1, p: '2', q: 'x'}}]: another graph's property rows of the same id are joined in and overwrite the reifier's own. The query joins rdf_props on the id alone: LEFT JOIN rdf_props p ON p.s = r.reifier_id (sch…
- Source severity S2, confidence high; module 15; governing page here: `fhir.`.
- Remedy proposed by the playbook arm (not implemented): Join the reifier's properties in the reifier node's graph (the graph reify_edge wrote it in, or the edge's graph once F-1502 is fixed): add the graph_id condition to the rdf_props join, e.g. through the nodes row of the reifier.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-C1603"></a>
### Bolt listens on every interface unless the server is started by `ivg server start`

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [16.json](../../experiment/playbook-completion/findings/audit/16.json) (probe `c16-s6-status-maps`; inspected `iris_vector_graph/cypher_api.py:47-63`; inspected `iris_vector_graph/cli.py:419-441`; inspected `docs/ADMIN_API.md:13-28`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c16-s6-status-maps`

- Expected: docs/ADMIN_API.md:26-28: the Bolt listener 'listens on the address --host names, or on BOLT_TCP_HOST'; API-T9.1; HD-1705 working answer: local-only or explicit opt-in for unauthenticated external binding.
- Observed at the pin: Live (c16-s6-status-maps): `uvicorn iris_vector_graph.cypher_api:app --host 127.0.0.1` served HTTP on 127.0.0.1:18617 and the Bolt listener on 0.0.0.0:18618. Source: cypher_api.py:51 defaults BOLT_TCP_HOST to 0.0.0.0; only the CLI sets it from --host (cli.py:429); the documented `python -m iris_vector_graph.cypher_api` binds HTTP 0.0.0.0:8000 and Bolt 0.0.0.0:7687 (cypher_api.py:779; ADMIN_API.md:22). With IVG_API_KEY unset the listener needs no credentials.
- Source severity S2, confidence high; module 16; governing page here: `access.`.
- Remedy proposed by the playbook arm (not implemented): Default BOLT_TCP_HOST to the HTTP host (or 127.0.0.1) in the app itself, not only in the CLI; refuse an unauthenticated non-loopback bind unless explicitly forced.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-C1743"></a>
### IRISGraphStore.query_nodes(limit=n) kills the calling Python process (SIGSEGV) on IRIS Community 2026.1 with the locked driver

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (live `st-live-so-confirm`; live `st-live-so-17b`; inspected `iris_vector_graph/stores/iris_sql_store.py:1176-1181`; run `env2-fc1720-query-nodes`; run `env2-fc1720-query-nodes-d540`; run `env2-fetchfirst-probe`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `st-live-so-confirm`, `st-live-so-17b`

- Expected: A public store method either answers or raises (store_protocol.py:10-11); the product knows FETCH FIRST is hazardous for this driver/engine family and avoids it elsewhere (iris_vector_graph/engine.py:725-739 _fetch_first_unsafe and its subprocess probe :772-830; docs/iris-sql-quirks.md:47-62; the in-line comment iris_sql_store.py:1177-1178 records a segfault on FETCH FIRST ? ROWS ONLY on ARM64).
- Observed at the pin: Live (st-live-so-confirm P17, AUDITD, IRIS 2026.1 Community build 234U, intersystems_irispython 5.3.2, x86_64): a child process that calls engine._store.query_nodes(limit=2) prints its start mark and exits with return code -11 (SIGSEGV) before any answer, in both insertion orders; the first attempt inside the permutation harness ended the harness with 'dumped core'. The statement is SELECT node_id FROM Graph_KG.nodes FETCH FIRST 2 ROWS ONLY (iris_vector_graph/stores/iris_sql_store.py:1179-1180), sent without consulting _fetch_first_unsafe. Attribution control (st-live-so-17b): the same statem…
- Source severity S2, confidence high; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): Use TOP n (as the translator does for joins and the engine does when _fetch_first_unsafe is set) or consult _fetch_first_unsafe in the adapter; a test that runs query_nodes(limit=n) on the supported driver.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-CS01"></a>
### A revision whose changeset recorded nothing keeps the tenant's message, source, correlation id and idempotency key (and the key's binding) through a complete redaction

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-simulator.json](../../experiment/playbook-completion/findings/audit/zz-simulator.json) (live `sim-fcs01-minimal`; live `sim-fcs01-ddmin-s1033`; trace `sim-main-20261114`; trace `sim-race-20261114`; control `sim-oracle-selftest`; inspected `iris_src/src/Graph/KG/LedgerApply.cls:229-233`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `sim-fcs01-minimal`, `sim-fcs01-ddmin-s1033`

- Expected: specs/256-ledger-tenant-redaction/spec.md:42-44 (US1: after erase and redaction 'no record, revision field or index reachable through IVG holds the tenant's entity ids, attribute values or messages'); spec.md:121-123 (FR-004: 'For a revision whose every record is redacted, message, source, correlation_id and idempotency_key MUST be cleared'; a revision with no records has every record redacted); spec.md:142-143 (SC-001: a scan of every ^IVG.Ledger subscript and value and every Graph_KG.ledger_* row finds none of the tenant's ids or values, 'Zero matches is the bar'); specs/256-ledger-tenant-r…
- Observed at the pin: Found by the randomized simulator (I6 SC-001 scan at each completed redaction) in 9 of 304 schedules, first seed 1033 (graph-per-tenant gamma) and in the prefix shape (seed 1087); shrunk through the product to 7 operations (sim-fcs01-ddmin-s1033) and hand-reduced to 6, reproduced 3/3 on AUDITA (sim-fcs01-minimal): commit(create_node acme|n1 with label Person, key acme-k-min-1) -> seq 2; commit(upsert_node acme|n1 + add_label acme|n1 Person, key acme-k-min-2, message 'acme commit min-2', source {tenant: acme}, correlation id acme-corr-0) -> seq 3 with op_count 0 (an existing node and an existi…
- Source severity S2, confidence high; module 13; governing page here: `redaction.`.
- Remedy proposed by the playbook arm (not implemented): Give every committed revision something the target predicate can match, or do not create a revision that records nothing. Options: (a) a changeset whose operations all turn out to be no-ops returns the current head without writing a revision row or binding its key (spec 213 would have to say whether an all-no-op commit is a revision); (b) record each no-op operation as a content-free 'noop' record carrying the entity id and graph, so FR-001's predicate matches it and the first-tombstone rule clears the revision and unbinds the key; (c) at Final, clear the metadata of revisions with op_count 0…
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-1003"></a>
### Global PageRank lists at most 10,000 nodes from its owner and every node from the native reader

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [10.json](../../experiment/playbook-completion/findings/audit/10.json) (live `b-10-live-cap`; mc `m10-routes-as-built-pagerank-cap`; mc `m10-routes-reviewed`; mc `m10-routes-control-owner-cap`; inspected `iris_src/src/Graph/KG/PageRank.cls:506-520`; inspected `iris_vector_graph/stores/iris_sql_store.py:2388-2400`)

Reproduced by: **e2e reproduced** — [actual public PageRank regression](audits/register-20261115/regressions.py), `pagerank_owner_cap`; [41-case final results and passing neighbors](audits/register-20261115/regressions.json). Actual IRIS Owner; no Arno route-equivalence claim.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-10-live-cap`

- Expected: The method's docstring: every node takes part and the scores sum to 1 over node_count() nodes (iris_vector_graph/_engine/algorithms.py:741-760); decisions.md HD-1004 (assumption): the same result contract on every route, uncapped pending a documented limit, any truncation exposed.
- Observed at the pin: Live (b-10-live-cap): with 10051 default-graph nodes (hub b10_h -> 10,050 nodes, pin's bulk API) kg_PAGERANK() on the owner route answered 10000 rows summing to 0.994926; 51 nodes were silently not listed; PageRank.PageRankGlobalJson itself answered 10000 rows. The native route (every node, iris_sql_store.py:2396-2399) is blocked (arno-callout absent). Model m10-routes-as-built-pagerank-cap reproduces the route disagreement.
- Source severity S2, confidence high; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Decide HD-1004; make both routes cut (or not cut) the same way and say so in the answer (a truncation flag or a documented top_k).
- Reviewed-design control: `playbook-proofs-d1e` `control_f1003_owner_cap` fails where expected in this run ([receipt](results/playbook-proofs-d1e/20261115T035522Z-control_f1003_owner_cap/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1e/20261115T035416Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

Iteration 3 scope reconciliation: algorithms.cache.pagerank separates COUNT:MAX cache admission from the numerical/every-node promise. PageRankGlobalJson:506-520 still caps output at 10000; the new native Python binding only forwards normalized fixture scores and does not rerun this live cap witness. No normalization or unlimited-output proof is claimed; HD-1004 remains authoritative as previously recorded.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

Audit: Actual public engine and ObjectScript Owner list 10000 of 10002 ordinary nodes with score sum below one; a one-node public caller passes. No Arno reader is available, so cross-route equivalence remains untested. Canonical owners: [algorithms.op.pagerank](../ontology/features/algorithms.g5.md#algorithms.op.pagerank), [algorithms.cache.pagerank](../ontology/features/algorithms.g5.md#algorithms.cache.pagerank).

<a id="bug-cyp-102"></a>
### A boolean equality also matches stored integers 1 and 0, beyond the legacy strings the known issue names

Severity: Medium · Decision: Open

Run: Uplift 2026-11-16 (cloud continuation, iteration 16)

Found by: source-first contrast of Cypher `WHERE` equality against the `RETURN` readers, with predictions frozen before observation ([predictions](../uplift/consolidated/iteration-16/typed-equality-PAIRS.md)); [typed_equality](models/typed_equality/NOTES.md) `theorem_node_true_exact` and `theorem_node_where_return_disagree`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 fixture with the unchanged pin ([probe](../uplift/consolidated/iteration-16/typed-equality-observed-20261116T164516Z.json); [44-world binding](results/typed_equality/20261116T165332Z-binding/receipt.json)). A node written by `create_node(properties={"p": 1})` stores the number 1; `MATCH (x) WHERE x.p = true RETURN count(*)` counts it and `RETURN x.p` returns the integer 1. A stored integer 0 matches `= false`. The string "1" also matches `= true` while `= 1` does not. Passing neighbors: a node boolean `true` matches `= true` and not `= 1`; integers 2, 12 and -1 match no boolean.

Expected: openCypher equality is false between a boolean and an integer, and [query.values](../ontology/features/cypher.g5.md#query.values) reads these values back as integers and strings. The product documents the legacy boolean match as a known issue ([KNOWN_ISSUES](../../docs/KNOWN_ISSUES.md#L597-L612)), planned to go with typed storage in 4.8.0, but scopes it to stored strings `'1'` and `'True'`; since 4.6.4 the API stores integers as numbers, and those match as well. The full as-built rule is [query.values.equality](../ontology/features/cypher.g5.md#query.values.equality).

Cause: `_stored_bool_in` emits `val IN ('true', '1', 'True')`, and IRIS compares a stored number with the text `'1'` as equal.

Consequence: a filter on a boolean flag also returns, updates or deletes rows whose property is the integer 1 or 0, which the known issue's workaround ("compare with the string you mean") does not avoid. Medium: visible wrong results with a confirmed trigger; destructive when the filter feeds `DELETE` or `SET`.

Repair proposal (not implemented, not checked): until typed storage, restrict the numeric arm of the boolean test to stored text (exclude rows that `_stored_number_test` marks as numbers), and extend the known issue's symptom to stored integers. Preserve: legacy text rows `'1'`/`'True'` keep matching, booleans written since 4.1.0 match, integer equality is unchanged. Distinguishing case: node `p = 1` (number) against `p = true`.

<a id="bug-cyp-103"></a>
### A relationship property that is not a number orders as one against a number literal

Severity: Medium · Decision: Open

Run: Uplift 2026-11-16 (cloud continuation, iteration 17)

Found by: the ordering neighbor of the iteration 16 equality workflow, with predictions frozen before observation ([predictions](../uplift/consolidated/iteration-17/ordering-PAIRS.md)); [typed_equality](models/typed_equality/NOTES.md) `theorem_rel_text_orders_as_cast` and `theorem_node_text_never_orders`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 fixture with the unchanged pin ([probe](../uplift/consolidated/iteration-17/ordering-observed-20261116T165915Z.json); [52-world binding](results/typed_equality/20261116T170150Z-binding/receipt.json)). `create_edge(a, "R", b, qualifiers={"p": "x"})`, then `MATCH (s)-[x:R]->(t) WHERE x.p < 2 RETURN count(*)` counts the edge, and `RETURN x.p` returns `"x"`. The empty string and `"x"` satisfy `< 1`; `"12abc"` satisfies `>= 1`; a JSON `true` satisfies `>= 1`. Passing neighbors: the same values as node properties are never kept, and relationship numbers order by value.

Expected: openCypher gives null for a string compared with a number, so the row is dropped. The product treats the cast-to-0 reading as a defect elsewhere: R308 replaced it for property-to-property comparisons ("CAST(val AS DOUBLE) made every non-numeric string 0"), R307 for booleans, and 4.7.0 row 24 for node properties against numbers. The as-built rule is [query.values.ordering](../ontology/features/cypher.g5.md#query.values.ordering).

Cause: in `_translate_boolean_expression`, `_as_number` applies the typed reading (`_stored_number_value`) only to node value columns; a relationship operand gets `CAST(JSON_VALUE(qualifiers, '$.p') AS DOUBLE)`, and IRIS casts non-numeric text to 0 and leading-number text to that number.

Consequence: range filters on relationship properties (`r.weight < 1`, `r.since >= 2020`) keep relationships whose value is missing-as-empty, a word, or text starting with digits, and the result disagrees with `RETURN`. Medium: wrong filter results with a confirmed trigger; destructive when the filter feeds `DELETE` or `SET`.

Repair proposal (not implemented, not checked): give relationship operands a typed reading like `_stored_number_value` (numeric only when the qualifier member is a JSON number or canonical numeric text, as `RETURN` decodes it), else NULL. Preserve: relationship numbers and Cypher-written numeric text still order; node and property-to-property paths unchanged. Distinguishing case: relationship `p = "x"` against `p < 2`.

<a id="bug-cyp-104"></a>
### ORDER BY sorts an empty-string property with the nulls on the native executor and first on the SQL path

Severity: Medium · Decision: Open

Run: Uplift 2026-11-16 (cloud continuation, iteration 18)

Found by: the sort-key binding, where `Graph.KG.Cypher.SortKey.Key("")` over the Native API returned the null rank while `CY_SORT_KEY('')` over SQL returned the string rank; then an executor comparison with the prediction frozen first ([predictions](../uplift/consolidated/iteration-18/order-by-PAIRS.md)); [sort_key](models/sort_key/NOTES.md) `theorem_executors_disagree_on_empty_string`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-18/empty-string-order-observed-20261116T170714Z.json)). An anchor with six targets whose `p` is `""`, `"b"`, `2`, missing, `"a"` and `1`; `MATCH (x {id: <anchor>})-[:R]->(b) RETURN b.p ORDER BY b.p` returns `'', 'a', 'b', 1, 2, null` on the SQL path and `'a', 'b', 1, 2, '', null` on the native executor, which `execute_cypher` used. `DESC` differs the same way. Passing neighbor: without the empty string, both paths agree on the same values (the W19 node and relationship sorts).

Expected: [query.native.equal-answers](../ontology/features/cypher.g5.md#query.native.equal-answers) requires the native answer to equal the SQL path's, in the same order where the query orders completely; these values are distinct. The as-built sort is [query.values.sorting](../ontology/features/cypher.g5.md#query.values.sorting).

Cause: the SQL path binds the stored empty string to `CY_SORT_KEY` as `$Char(0)`, which `Key` ranks as a string; the native executor's `Exec.SortKey` passes it as ObjectScript `""`, which `Key` treats as null.

Consequence: the order, and with `LIMIT` or `SKIP` the rows, depend on which executor answers, and the router can switch executors by timing. Shadow mode would raise a mismatch. Medium: visible wrong order with a confirmed trigger on ordinary data.

Repair proposal (not implemented, not checked): have `Exec.SortKey` pass a stored empty string as `$Char(0)` (or have `Key` distinguish an empty stored value from a missing one on that path), preserving null-last for missing properties and the SQL path unchanged. Distinguishing case: the six-target query above.

<a id="bug-cyp-106"></a>
### IN lists compare a property's text with each value's spelling, so they disagree with = on nodes and relationships

Severity: Medium · Decision: Open

Run: Uplift 2026-11-16 (cloud continuation, iteration 23)

Found by: the `IN`-list neighbor of the typed comparison workflows, with predictions frozen first ([predictions](../uplift/consolidated/iteration-23/remaining-operators-PAIRS.md)); [typed_equality](models/typed_equality/NOTES.md) `theorem_node_in_disagrees_with_equality`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 fixture with the unchanged pin ([probes](../uplift/consolidated/iteration-23/remaining-operators-observed-20261116T172936Z.json), [near spellings](../uplift/consolidated/iteration-23/node-in-observed-20261116T173018Z.json); [52-world binding](results/typed_equality/20261116T173137Z-binding/receipt.json)). A node written with `p = "1"`: `WHERE x.p IN [1]` keeps it while `WHERE x.p = 1` drops it, and `RETURN x.p` reads `"1"`. A node number 1 is `IN ['1']`. An edge written with `qualifiers={"p": 1.0}`: `WHERE x.p = 1` keeps it while `WHERE x.p IN [1]` drops it. Passing neighbors: node `"01"`, `"1.0"`, `"abc"` and `""` match neither list; numbers in lists of numbers match on both kinds.

Expected: openCypher defines `IN` by `=`. Since 4.7.0 node `=` requires a stored number of that value ([query.values.equality](../ontology/features/cypher.g5.md#query.values.equality)), and relationship `=` accepts an integer's float twin; `IN` follows neither. The documented known issue lists `=`, inline maps and `WITH` columns for these shapes, not `IN`. The as-built rule is [query.values.in_lists](../ontology/features/cypher.g5.md#query.values.in_lists).

Cause: `_boolean_expr_in` emits `val IN (?)` (nodes) or the `JSON_VALUE` text `IN (?)` (relationships), comparing text with the bound value's text, without `_node_number_eq_sql` or `_number_texts`.

Consequence: rewriting `x.p = 1 OR x.p = 2` as `x.p IN [1, 2]` changes the result, in opposite directions on nodes and relationships. Medium: wrong filter results with a confirmed trigger; destructive under `DELETE` or `SET`.

Repair proposal (not implemented, not checked): translate a literal integer list through the same equality builders (`_node_number_eq_sql` for nodes, `_number_eq_sql` with `_number_texts` for relationships), preserving string lists and the boolean legacy spellings. Distinguishing cases: node `p = "1"` and relationship `p = 1.0` against `IN [1]`.

<a id="bug-plt-011"></a>
### An interrupted BulkLoader node load cannot be resumed: re-loading skips the labels and properties of nodes already written

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Found by: A-platform F-B5 (sub-reader b), source reading; confirmed in the retest's iteration 25 with predictions frozen first ([predictions](../uplift/consolidated/iteration-25/bulk-loader-PAIRS.md)); [bulk_load](models/bulk_load/NOTES.md) `theorem_interrupted_load_is_never_completed`, `witness_interrupted_rerun_strands`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 retest fixture with the unchanged pin ([probe](../uplift/consolidated/iteration-25/bulk-loader-observed-20261116T212413Z.json), case B1; [binding](results/bulk_load/20261116T213301Z-binding/receipt.json), 24 interrupted histories). `BulkLoader.load_nodes` of two new nodes with a label and a property, interrupted at the label insert (injected: the first `rdf_labels` `executemany` raises, the state a lost connection leaves after phase 1 commits per batch), raises `BulkLoadError`. The same call again returns `{"nodes": 0, "labels": 0, "props": 0}`, and `get_node` then shows both nodes with no labels and no properties; `MATCH (n:L)` finds neither, also after `rebuild_all_indices`. Passing neighbor (B2): when the first call completes, the same call again also returns zeros and both nodes keep their labels and properties.

Expected: "re-loading the same data has to stay idempotent" (`bulk_loader.py:93-95`); the owner [install.bulk_load.loader](../ontology/concepts/install.g5.md#install.bulk_load.loader) promises that a completed load reads back as its input.

Cause: the skip scan selects input ids that already have a node row (`_known_nodes_sql`), and phases 2 and 3 write labels and properties only for the ids that scan did not see (`nodes_to_process = new_nodes`, `bulk_loader.py:314`). Phase 1 has already committed.

Consequence: after any failure in phase 2 or 3, the loaded nodes stay without their labels and properties, and the re-run's counts read as "already loaded". An administrator can delete the stranded nodes and load again. Medium: visible wrong data with a confirmed trigger path; the interruption itself was injected.

Repair proposal (checked in the model only): let the re-run also process nodes of its input that have neither labels nor properties (control `rerun-completes-stranded` makes the stranding theorems fail), preserving the documented rule that an existing node keeps the property values it has. Distinguishing case: B1 against B2 above.

<a id="bug-plt-027"></a>
### BulkLoader's node and edge loads write without indexes and return before rebuilding them

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Found by: review round 3 R3-reader M6 (code reading); observed at the readers in the retest's iteration 25 with predictions frozen first ([predictions](../uplift/consolidated/iteration-25/bulk-loader-PAIRS.md), cases A1-A7); [bulk_load](models/bulk_load/NOTES.md) `theorem_noindex_invisible_until_rebuild`, `theorem_indexed_load_reads_now`. Iteration 25 first filed this as bug-plt-106; that ID is kept as an alias of this entry.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 retest fixture with the unchanged pin ([probe](../uplift/consolidated/iteration-25/bulk-loader-observed-20261116T212413Z.json); [binding](results/bulk_load/20261116T213301Z-binding/receipt.json)). `load_nodes` and `load_edges` with their default `use_noindex=True` return counts of 2 nodes, 2 labels, 4 properties and 1 edge; then `get_node` returns `None`, `MATCH (a {id: …})-[r]->(b)` returns no row and `MATCH (n:L) RETURN count(n)` returns 0. Passing neighbors: the same load with `use_noindex=False` reads back at once (A2); after `rebuild_all_indices()` the default load reads back (A3), and so does the earlier unrebuilt load (A1 re-read); `load_networkx`, which rebuilds, reads back (A7).

Expected: spec 252 FR-008: "Bulk paths that write `%NOINDEX` MUST dedupe and MUST end in `%BuildIndices` before returning, success or failure"; ADR-0008: "No `%NOINDEX` writer returns before its `%BuildIndices`." The owner [structure.adjacency.bulk](../ontology/features/graph-structure.g5.md#structure.adjacency.bulk) applies FR-008 to the bulk loader.

Observed: `BulkLoader.load_nodes` and `load_edges` write with `%NOINDEX %NOCHECK` by default and leave the rebuild to the caller; `load_edges`' docstring says to call `rebuild_all_indices()`, `load_nodes`' does not. Only `load_networkx` rebuilds before returning.

Consequence: a caller who uses `load_nodes`/`load_edges` directly sees an apparently empty graph until it rebuilds; traversal, indexed lookups and other writers' index-based dedupe and delete paths miss the loaded rows (related inherited entries F-C1250, F-C1351). Medium: visible misbehavior with a confirmed trigger, which an administrator can repair with one call. The Low of the original entry reflected a code-reading-only suspicion.

Interpretation needing confirmation (unchanged): the class may be meant as a low-level tool outside FR-008, with `bulk_load_session` as the governed path; the owner currently applies FR-008 to it.

Repair proposal (not implemented, not checked): end each `%NOINDEX` public load in `rebuild_all_indices()` (as `load_networkx` does), or make `use_noindex` default to `False` for the per-phase methods; preserve `load_networkx`'s single rebuild. Distinguishing case: A1 against A2. Related: [bug-plt-011](#bug-plt-011).

<a id="F-0608"></a>
### Vector index stores do not check width or duplicates

Severity: Medium · Decision: Open

Run: Playbook completion audit (imported 2026-11-14)

Found by: the playbook arm's audit (module 06), live on the IVF index; the PLAID branch in iteration 30 ([predictions](../uplift/consolidated/iteration-30/plaid-PAIRS.md), [plaid_index](models/plaid_index/NOTES.md) `theorem_reinsert_inflates_counts`, `theorem_insert_accepts_other_width`) (`p0608_ivf_insert_duplicates`: re-inserting `a` put it in two cells and raised `indexed` from 2 to 3); the VecIndex branch, which that audit did not run, in the retest's iteration 27 with predictions frozen first ([predictions](../uplift/consolidated/iteration-27/vecindex-PAIRS.md)); [vec_index](models/vec_index/NOTES.md) `theorem_reinsert_inflates_count`, `theorem_insert_overwrites_dim`.

Reproduced by: **E2E reproduced** for VecIndex on the run-isolated IRIS 2026.1 retest fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-27/vecindex-observed-20261116T215013Z.json), cases V9 and V11; [binding](results/vec_index/20261116T215331Z-binding/receipt.json), five metrics). Re-inserting a stored ID raises `vec_info.count` from 5 to 6 while the index still holds 5 vectors (the search returns the ID once, with its new vector). Inserting `[1, 0]` into a 3-wide index is accepted, `vec_info.dim` becomes 2, and the vector is ranked by the parts both vectors share (an l2 distance ignores the query's third component). Passing neighbor: distinct inserts into a new index count exactly the stored vectors. The IVF branch rests on the playbook's live result above, not rerun here. PLAID branch (iteration 30, [observation](../uplift/consolidated/iteration-30/plaid-observed-20261116T220723Z.json), [binding](results/plaid_index/20261116T220842Z-binding/receipt.json)): re-inserting a stored document raises `plaid_info.indexed` (5 → 6) and `totalTokens` (8 → 9) although the index holds 5 documents and 7 tokens; unlike IVF, the document is then scored on its new tokens only, so the old direction no longer ranks it. A 2-wide document is accepted into a 3-wide index and, scored on the shared components, takes the first rank (1.0) ahead of a correctly sized match (0.5). `plaid_build` already refuses another width (R089), so only `plaid_insert` lacks the check.

Expected: the playbook statement VEC-B11.14 ("an id lives in at most one cell; indexed counts distinct ids"); `plaid_build` already refuses a token of another width (R089), and `vec_create_index` takes a `dim`.

Consequence: `vec_info` over-reports the index size after updates, and one wrong-width vector silently changes the recorded width and is ranked on partial data. Medium: wrong reported size and wrong rankings with a confirmed trigger; an administrator can rebuild the index.

Repair proposal (checked in the model only): count only IDs not yet stored, and refuse a vector whose width differs from the index's (controls `count-only-new-ids` and `refuse-other-width` make the as-built theorems fail); preserve replacement of a stored ID's vector. Distinguishing cases: V9 and V11.

<a id="bug-plt-012"></a>
### BulkLoader ignores the namespace's IVG Schema

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Found by: A-platform F-B6 (sub-reader b), source reading; confirmed in the retest's iteration 31 with predictions frozen first ([predictions](../uplift/consolidated/iteration-31/schema-PAIRS.md)); [bulk_load](models/bulk_load/NOTES.md) `theorem_loader_without_schema_writes_nothing`, `theorem_rebuild_in_other_schema_leaves_rows_unreadable`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 retest fixture with the unchanged pin, in a new namespace `W37` set up by `initialize_schema()` with `schema_prefix="Kg2"` ([observation](../uplift/consolidated/iteration-31/schema-observed-20261116T221059Z.json); [binding](results/bulk_load/20261116T221240Z-binding/receipt.json)). `BulkLoader(conn).load_nodes(...)` fails with "Table 'GRAPH_KG.NODES' not found" and writes nothing. With `schema="Kg2"` an indexed load is readable at once, but a default unindexed load followed by `rebuild_all_indices()` answers `false` for all four `Graph.KG.*` classes and the node stays unreadable through the Kg2 engine's `get_node`. Passing neighbor: the same unindexed load and rebuild in `USER` (`Graph_KG`) answers `true` four times and reads back.

Expected: [install.bulk_load.loader](../ontology/concepts/install.g5.md#install.bulk_load.loader): "It writes and rebuilds in the namespace's recorded IVG Schema, like every other IVG writer"; ADR-0016.

Cause: `BulkLoader` defaults to `schema="Graph_KG"` and `rebuild_all_indices` names the `Graph.KG.*` classes whatever schema it was given (`bulk_loader.py:41, 56-60, 495`).

Consequence: in a namespace with another IVG Schema, the loader fails unless told the schema, and then its default unindexed loads never become readable through its own rebuild. The original entry rated this High before lowering it for an unconfirmed trigger; both failures are loud (an SQL error, or a rebuild that answers `false` with warnings), so Medium: visible misbehavior an administrator can repair.

Repair proposal (checked in the model only): take the schema from the namespace's record, and rebuild the classes of that schema's package (controls `default-schema-follows-namespace` and `rebuild-follows-schema`). Preserve `Graph_KG` behavior. Distinguishing cases: S1 and S3 against S4.

<a id="bug-plt-108"></a>
### The Neo4j-compatible HTTP routes return at most 1,000 rows of an answer without saying so

Severity: Medium · Decision: Open

Run: Uplift 2026-11-16 (retest, iteration 32)

Found by: source reading after the W38 predictions were frozen (`_run_cypher` keeps at most `limit` rows), then observation ([predictions](../uplift/consolidated/iteration-32/http-PAIRS.md), H5); [http_rows](models/http_rows/NOTES.md) `theorem_neo4j_answer_cannot_tell_truncation`.

Reproduced by: **E2E reproduced** in-process (FastAPI `TestClient`, no listener) against the run-isolated IRIS 2026.1 retest fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-32/http-observed-20261116T221726Z.json); [binding](results/http_rows/20261116T221848Z-binding/receipt.json)). `UNWIND range(1, 1200) AS i RETURN i`: `execute_cypher` returns 1,200 rows; `POST /db/neo4j/tx/commit` returns 1,000 rows in `results[0].data` with no error, and `POST /db/neo4j/query/v2` returns 1,000 in `data.values`, neither with any sign of the cut. Passing neighbors: 999 and 1,000 rows come back whole; `/api/cypher` documents its `limitRows` (default 1000) and honours `limitRows: 2000` (1,200 rows). Every value and type otherwise agreed across the engine and the three routes (H1-H4, H6).

Expected: [access.surfaces](../ontology/concepts/access.g5.md#access.surfaces): each server call should do what the engine method it stands for does; Neo4j's transaction and query APIs return the whole answer (paging is the client's choice), and nothing in IVG's docs mentions a cap on those routes.

Cause: `neo4j_tx_commit` and `neo4j_query_v2` call `_run_cypher(statement, parameters)` with its default `limit=1000` (`cypher_api.py:239-265, 379-460`); only `/api/cypher` exposes the limit and returns `rowCount`, which counts the rows kept.

Consequence: a Neo4j HTTP client gets a silently incomplete answer for any query with more than 1,000 rows; with the query API it cannot even tell from the response. Medium: wrong (incomplete) results with a confirmed trigger on a secondary protocol; Bolt and `/api/cypher` are the documented paths.

Repair proposal (not implemented): return every row on the Neo4j routes (or honour a client limit and say when the answer was cut, as `/api/cypher` could with a total). Preserve `/api/cypher`'s documented `limitRows`. Distinguishing case: 1,000 against 1,001 rows on `/tx/commit`.

<a id="bug-srch-103"></a>
### The IRIS queue worker marks an entry done when the provider fails or answers nothing

Severity: Medium · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 36)

Found by: the owner's recorded divergence for `ProcessBatch` (source reading at stage A; no register entry before this one), tested by the frozen W42 prediction Q5, which missed for the IRIS worker ([predictions](../uplift/consolidated/iteration-36/embed-queue-PAIRS.md)); [embed_queue](models/embed_queue/NOTES.md) `theorem_iris_unanswered_marked_done`, control `iris-unanswered-is-error`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin, through `start_background_embedding` (the Task Manager task) and through `ProcessBatch` directly ([observation 1](../uplift/consolidated/iteration-36/embed-queue-observed-20261117T001118Z.json), [observation 2](../uplift/consolidated/iteration-36/embed-queue-observed2-20261117T001204Z.json), [binding](results/embed_queue/20261117T001547Z-binding/receipt.json) cases I2-I4, I6, I7). The provider is a fixture-only `%Embedding.Interface` class. When it fails (`SQLCODE -400`) or answers nothing, or the entry names no known config (`-280`), the entry becomes `DONE` with no error, no result and no vector, and leaves the pending count. Passing neighbors: in a named graph a provider answer is stored and the entry is `DONE` (I5); the Python worker turns the same failures into `ERROR` with the reason (P2, P4).

Expected: [search.embedding.queue](../ontology/features/search.g5.md#search.embedding.queue): "An entry whose text cannot be embedded, or whose vector cannot be stored, is marked as an error with the reason, never as done." The class's own comment (`EmbedQueue.cls:321`) says a failed write "is the entry's error, not DONE".

Observed: `ProcessBatch` writes `DONE` after the `Try` whenever `%Execute` reports an `SQLCODE` other than 0 or returns an empty value (`EmbedQueue.cls:308-327`); dynamic SQL reports the provider's failure through `SQLCODE` rather than throwing, so the `Catch` never sees it.

Consequence: a provider outage or a misnamed config turns queued work into finished work with nothing stored and no reason; the task stops because nothing is pending, and only a search for unembedded nodes shows the loss. Medium: silent loss of requested work; the data that exists is not changed.

Repair proposal (not implemented; checked in Verus only): mark the entry `ERROR` with the `SQLCODE` message when the statement fails or answers nothing. `embed_queue.rs::theorem_reviewed_iris_meets_rule` shows the repaired worker meets the owner's rule on every modeled entry (with bug-srch-104's repair); behavior to keep: named-graph success, the refusals before the provider call. Governing statement: [search.embedding.queue](../ontology/features/search.g5.md#search.embedding.queue).

<a id="bug-srch-104"></a>
### The IRIS queue worker cannot store a default-graph vector

Severity: Medium · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 36)

Found by: the frozen W42 prediction Q3 for the IRIS worker missed ([predictions](../uplift/consolidated/iteration-36/embed-queue-PAIRS.md)); [embed_queue](models/embed_queue/NOTES.md) `theorem_iris_default_graph_never_stores`, control `iris-default-insert-ok`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin, through `start_background_embedding` and through `ProcessBatch` ([observation 1](../uplift/consolidated/iteration-36/embed-queue-observed-20261117T001118Z.json), [observation 2](../uplift/consolidated/iteration-36/embed-queue-observed2-20261117T001204Z.json), [binding](results/embed_queue/20261117T001547Z-binding/receipt.json) case I1). A default-graph node queued with a config whose provider answers a 768-wide vector ends `ERROR` with "-108 'graph_id' in table 'Graph_KG.kg_NodeEmbeddings' is a required field", and `get_embedding` finds nothing. Passing neighbors: the same provider and width in a named graph is stored (I5); the Python worker stores the default-graph vector (P1).

Expected: [search.embedding.queue](../ontology/features/search.g5.md#search.embedding.queue) and the API reference ("Run an IRIS task that works the embedding queue now") promise that queued work is done; the default graph is a graph like any other ([graph scope](../ontology/concepts/graph-scope.g5.md)).

Observed: `enqueue_for_embedding` sends the default graph as `""` (`constants.DEFAULT_GRAPH`), and `ProcessBatch` binds that `""` as the `graph_id` of its INSERT (`EmbedQueue.cls:316-320`). An empty ObjectScript host variable binds as SQL NULL, which the class itself works around in `NodeInGraph` (`COALESCE`, lines 201-206) but not here.

Consequence: on a fresh 4.7.0 install the IRIS worker stores no default-graph vector at all; with bug-srch-103 the only default-graph entries it marks `DONE` are those that got no vector. It also means the IRIS-worker half of [bug-srch-006](#bug-srch-006) (a default-graph entry written to `kg_NodeEmbeddings` whatever its model) cannot store anything on such an install; on an install whose `graph_id` accepts NULL it is unexamined. The product's queue tests run without a provider and check only refusals (`tests/integration/test_embed_queue_process.py:1-5`). Medium: the IRIS worker fails all default-graph work, visibly.

Repair proposal (not implemented; checked in Verus only): bind the default graph as the SQL empty string, which is what the Python store writes (observed: `graph_id` length 0, not NULL; the column is NOT NULL). Same receipt as bug-srch-103. Governing statement: [search.embedding.queue](../ontology/features/search.g5.md#search.embedding.queue).

<a id="bug-str-105"></a>
### retract_inference deletes an edge the user created after the same triple was inferred

Severity: Medium · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 38)

Found by: the frozen W44 prediction I4 missed ([predictions](../uplift/consolidated/iteration-38/inference-PAIRS.md)); [inference_rows](models/inference_rows/NOTES.md) `theorem_asserted_after_is_retracted`, control `create-marks-asserted`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin, multigraph off ([observation](../uplift/consolidated/iteration-38/inference-observed-20261117T003415Z.json) I4 and I9; [binding](results/inference_rows/20261117T003857Z-binding/receipt.json)). With `A subClassOf B` and `x type A`, `materialize_inference()` writes `x type B` marked inferred; `create_edge(x, type, B)` then answers False and leaves the row marked inferred; `retract_inference()` deletes it and its `^KG` entry. Passing neighbor (I3): when `x type B` is created before materializing, the same visible graph keeps it through retract.

Expected: the API reference says retract deletes "the edges `materialize_inference` wrote" and the docstring that "an asserted edge for the same triple keeps its adjacency entry"; a caller who created the edge has asserted it. Whether a create of an inferred triple should make it asserted is the owner question [install.inference.assert_after](open_questions.md#install.inference.assert_after).

Observed: `create_edge` skips a triple that already has a row (multigraph off) and does not touch its qualifiers; `retract_inference` deletes every row whose qualifiers contain `"inferred":` (`schema.py:3215-3227`).

Consequence: two histories with the same edges before retract end differently, and a fact the user stated is silently removed. Medium: loss of user data on an ordinary sequence (materialize, add facts, retract to re-run).

Repair proposal (not implemented; checked in Verus only): have `create_edge` clear the inferred marker on an existing inferred row (control `create-marks-asserted` is the repaired rule), or refuse with a message. Governing statement: [install.inference](../ontology/concepts/install.g5.md#install.inference).

<a id="bug-str-107"></a>
### SHACL validation treats one node ID in two graphs as one node, so an invalid node passes

Severity: Medium · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 39)

Found by: the frozen W45 prediction S4, taken from the semantic-layer doc's IRI rule, compared with [graph scope](../ontology/concepts/graph-scope.g5.md) ([predictions](../uplift/consolidated/iteration-39/shacl-PAIRS.md)); [shacl_data](models/shacl_data/NOTES.md) `theorem_other_graph_masks_missing_property`, control `data-graph-keeps-graphs-apart`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin, pySHACL 0.40.2 and rdflib 7.6.0 ([observation](../uplift/consolidated/iteration-39/shacl-observed-20261117T004330Z.json) S4, S4b; [binding](results/shacl_data/20261117T004553Z-binding/receipt.json) case `min_twin_masked`). Node `twin` in the default graph has `approved`; the node `twin` in a named graph, with the same label, does not. `validate_shacl` with a shape requiring `approved` answers `conforms = True` and no violation. Passing neighbor: a node without `approved` in only one graph is reported (`min_bad`).

Expected: [graph scope](../ontology/concepts/graph-scope.g5.md): "The same node ID in two graphs is two nodes, each with its own labels, properties and edges", and a reader of every graph answers the union of each graph's own answer, a node keeping its own graph's properties. SEMANTIC_LAYER.md recommends validation as an ingestion gate.

Observed: the data graph mints a node's IRI from its ID alone (`_rdf_utils._mint_iri`), and the graphs' contexts are validated together, so the shape sees one IRI with the union of both graphs' triples.

Consequence: data written to a named graph that breaks a shape is accepted when another graph has a valid node with the same ID; the reverse case reports a violation against the wrong graph's node. Medium: a wrong validation answer, silently.

Repair proposal (not implemented): validate each graph's context on its own (or mint graph-qualified IRIs for validation), and name the graph in each violation. Governing statements: [install.shacl](../ontology/concepts/install.g5.md#install.shacl), [graph scope](../ontology/concepts/graph-scope.g5.md).

<a id="bug-str-109"></a>
### import_rdf drops a literal's datatype, so an imported xsd:integer reads back as text and matches no number

Severity: Medium · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 41)

Found by: the frozen W47 prediction R5 missed ([predictions](../uplift/consolidated/iteration-41/rdfimport-PAIRS.md)); [rdf_import](models/rdf_import/NOTES.md) `theorem_datatype_dropped`, control `keep-datatype`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin and rdflib 7.6.0 ([observation](../uplift/consolidated/iteration-41/rdfimport-observed-20261117T005436Z.json) R5; [stored rows and Cypher](../uplift/consolidated/iteration-41/rdfimport-observed2-20261117T005514Z.json); [binding](results/rdf_import/20261117T005643Z-binding/receipt.json) `int_literal_reads_as`, `int_literal_equals_in_cypher`). `"2011"^^xsd:integer` is stored as the text `2011`, like the plain literal `"2011"`; `get_node` returns `"2011"` and `MATCH (n) WHERE n.yr = 2011` finds nothing. Passing neighbors: an integer 2011 written by `create_node` reads back as 2011 and matches; `"true"^^xsd:boolean` reads back as True.

Expected: SEMANTIC_LAYER.md: "a literal becomes a property of the subject"; the export writes integer properties as `xsd:integer` and IVG's readers keep a written integer's type ([query.values](../ontology/features/cypher.g5.md#query.values)), so a declared integer is expected to stay one.

Consequence: numeric filters, sorting and comparisons over imported data silently miss or misorder rows. Medium: wrong query answers, no error.

Repair proposal (not implemented): store numeric and boolean literals in the typed form the API's writers use. Governing statement: [install.import.rdf](../ontology/concepts/install.g5.md#install.import.rdf).

<a id="bug-str-110"></a>
### Re-importing RDF never updates a property: a changed literal keeps the old value and is only logged

Severity: Medium · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 41)

Found by: source reading after the W47 freeze (R9, not frozen) ([predictions](../uplift/consolidated/iteration-41/rdfimport-PAIRS.md)); [rdf_import](models/rdf_import/NOTES.md) `theorem_reimport_keeps_old_value`, control `upsert-property`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-41/rdfimport-observed-20261117T005436Z.json) R7, R9; [binding](results/rdf_import/20261117T005643Z-binding/receipt.json) `reimport_value`, `reimport_properties_counted`). After importing `<u> <label> "first"`, importing `<u> <label> "second"` answers `properties: 0`, logs an `SQLCODE -119` warning, and `get_node` and Cypher still read `"first"`. Passing neighbor: an edge in a re-imported file is not duplicated.

Expected: the API reference: "write its triples as nodes, edges and properties"; the docstring counts "rows already present included", which holds for edges but not for properties.

Observed: each property is a plain `INSERT` into `rdf_props`; the primary key `(graph_id, s, key)` refuses it and the failure is logged and skipped (`_engine/snapshot.py`, `import_rdf._flush`).

Consequence: refreshing a graph from an updated RDF file leaves stale values while the call succeeds; the answer's counts differ between edges and properties. Medium: silent stale data.

Repair proposal (not implemented): upsert properties (or report the rows not written in the answer). Governing statement: [install.import.rdf](../ontology/concepts/install.g5.md#install.import.rdf).

<a id="bug-str-111"></a>
### import_rdf(infer=True) on N-Quads or TriG infers in the graph argument, not in the graphs the quads were written to

Severity: Medium · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 41)

Found by: source reading after the W47 freeze (R10, not frozen) ([predictions](../uplift/consolidated/iteration-41/rdfimport-PAIRS.md)); [rdf_import](models/rdf_import/NOTES.md) `theorem_infer_ignores_contexts`, control `infer-on-contexts`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-41/rdfimport-observed-20261117T005436Z.json) R1_R2_R10; [binding](results/rdf_import/20261117T005643Z-binding/receipt.json) `inferred_rows_in_context_graph`). An N-Quads file with `A subClassOf B` and `i type A`, all in context `urn:ivg:graph:trials…`, imported with `infer=True` and no `graph`, writes no inferred edge in `trials…`, and answers `"inferred": 7`: seven edges materialized in the default graph from data the file did not contain.

Expected: the docstring: "`infer` ... runs `materialize_inference`" after an import whose "quad's own graph name wins"; [install.inference](../ontology/concepts/install.g5.md#install.inference) scopes inference to one graph.

Consequence: the imported graph gets no inference, another graph gets derived edges the caller did not ask for, and the answer's count describes the other graph. Medium.

Repair proposal (not implemented): run inference on each graph the import wrote to. Governing statement: [install.import.rdf](../ontology/concepts/install.g5.md#install.import.rdf).

<a id="bug-plt-110"></a>
### prov_as_dict and prov_export_from_cypher fail for every edge once the default graph's temporal history is large

Severity: Medium · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 44)

Found by: source reading after the W50 freeze (P9, not frozen) ([predictions](../uplift/consolidated/iteration-44/prov-PAIRS.md)); [prov_window](models/prov_window/NOTES.md) `theorem_as_dict_fails_on_large_history`, controls `read-streams`, `as-dict-bounded`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-44/prov-observed-20261117T010711Z.json) P8_P9; [binding](results/prov_window/20261117T010842Z-binding/receipt.json) `as_dict_with_large_history`). After 40,000 temporal edges were written to the default graph, `prov_as_dict("<s>|<p>|<A>|<t>")` for an edge that exists raises `RuntimeError: <MAXSTRING>QueryWindow+27^Graph.KG.TemporalIndex.1`; `prov_export` of a small window around the same edge still answers. Before the large load the same call answered (P4).

Expected: SEMANTIC_LAYER.md says these two calls "read every temporal edge of the default graph to find theirs" (a cost), not that they stop working; the other temporal window readers were moved off the one-string read for this reason (CHANGELOG: `iter_edges_in_window`).

Observed: both read `QueryWindow` over all time with one Native API call and filter in Python (`_engine/prov.py:181-219`); `QueryWindow` raises once the answer exceeds one IRIS string (about 35,000 edges).

Consequence: on any namespace with a real temporal history these two PROV calls are unusable, whatever edge or nodes are asked for. Medium: a feature fails outright (visibly), with no window argument to work around it.

Repair proposal (not implemented): look the edge up by its own source, predicate and timestamp (or read the window in chunks). Governing statement: [install.export.prov](../ontology/concepts/install.g5.md#install.export.prov).

<a id="bug-plt-111"></a>
### export_rdf_from_cypher writes an empty file and reports 0 triples when its query fails

Severity: Medium · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 45)

Found by: source reading after the W51 freeze (C10, not frozen) ([predictions](../uplift/consolidated/iteration-45/cyphexport-PAIRS.md)); [cypher_export](models/cypher_export/NOTES.md) `theorem_failed_query_looks_empty`, control `error-raised`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-45/cyphexport-observed-20261117T011128Z.json) C10; [binding](results/cypher_export/20261117T011234Z-binding/receipt.json) `failed_query`). A query IRIS refuses at run time (a mapped label through an IVG relationship, [bug-cyp-109](#bug-cyp-109)) sets `result.error` when run with `execute_cypher`; `export_rdf_from_cypher` with the same query answers `{"triples": 0}`, writes an empty file and raises nothing.

Expected: the user guide: "Check `result.error` (or pass `raise_on_error=True`) wherever an empty answer would be taken for 'nothing found'"; an export of nothing is that case.

Consequence: a failed export is indistinguishable from a query that matched nothing; downstream tools load an empty file. Medium: silent wrong result.

Repair proposal (not implemented): raise when the query's result carries an error (or run it with `raise_on_error=True`). Governing statement: [install.export.rdf.cypher](../ontology/concepts/install.g5.md#install.export.rdf.cypher).

<a id="bug-srch-107"></a>
### Re-inserting a node into an IVF index keeps its old vector when the new one lands in another cell, and counts it twice

Severity: Medium · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 46)

Found by: the frozen W52 prediction V4 missed ([predictions](../uplift/consolidated/iteration-46/ivf-PAIRS.md)), then a second observation; [ivf_entries](models/ivf_entries/NOTES.md) `theorem_cross_cell_reinsert_leaves_stale_entry`, `theorem_same_cell_reinsert_counts_twice`, controls `insert-replaces`, `delete-all`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-46/ivf-observed-20261117T011444Z.json) V4; [second observation](../uplift/consolidated/iteration-46/ivf-observed2-20261117T011512Z.json); [binding](results/ivf_entries/20261117T011629Z-binding/receipt.json)). `ivf_insert(name, "x", v1)` then `ivf_insert(name, "x", v2)` with `v2` nearest another centroid leaves both entries: a search with `v1` still returns `x` first, and after one `ivf_delete(name, "x")` (answering True) `x` is still returned. In the same cell the second insert replaces the vector but `ivf_info.indexed` rises by 2. Iteration 50 ([review 47-49](../uplift/consolidated/iteration-50/REVIEW-47-49.md) m8): the cross-cell case needs no change of vector. Under metric "cosine" or "dot", re-inserting a node with the vector the build stored can choose another cell, because the build clusters by Euclidean k-means and `Insert` picks the cell with the largest dot product ([binding](results/ivf_entries/20261117T032444Z-binding/receipt.json) `cell_cosine`, `cell_dot`: built in cell 0, inserted in cell 1, now in both, `indexed` + 1; neighbor `cell_l2` keeps cell 0). [ivf_entries](models/ivf_entries/NOTES.md) `theorem_cosine_reinsert_changes_cell`, neighbor `theorem_l2_insert_matches_build`, control `insert-by-distance`.

Expected: the API reference: `ivf_insert` "add[s] one vector ... in the cell of its nearest centroid"; `ivf_delete` "remove[s] node_id's vector ... Returns True if it was there"; `ivf_info.indexed` is the index's size. [search.scope.indexes.upkeep](../ontology/features/search.g5.md#search.scope.indexes.upkeep): the caller keeps the index in step through these calls.

Observed: `IVFIndex.Insert` writes `^IVF(name,"list",cell,node)` without clearing the node's entry in other cells and always adds one to `indexed`; `Delete` removes the first cell's entry and stops (`IVFIndex.cls:180-230`).

Consequence: updating a node's vector leaves its old vector answering searches, deleting it does not remove it, and the reported size drifts. Medium: silent stale results.

Repair proposal (not implemented): remove the node from every cell before inserting, count only new nodes, and delete every copy. Governing statement: [search.ivf](../ontology/features/search.g5.md#search.ivf).

<a id="bug-srch-109"></a>
### An IVF index built with metric "cosine" ranks by the raw dot product, so a long vector outranks a perfectly aligned one

Severity: Medium · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 47)

Found by: source reading of `IVFIndex.Search` while checking W53's SQL reader ([predictions](../uplift/consolidated/iteration-47/sqlprocs-PAIRS.md); not a frozen prediction); [ivf_entries](models/ivf_entries/NOTES.md) `theorem_cosine_ranks_as_dot` (every query and vector pair) and `theorem_cosine_metric_misranks` (witness), controls `cosine-normalized` (the repaired order; the equal-length neighbor `theorem_equal_lengths_agree`, general since iteration 50, still verifies) and `cosine-takes-l2-branch` (which also fails `theorem_cosine_metric_misranks`, named since iteration 50).

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-47/ivf-cosine-observed-20261117T014744Z.json); [binding](results/ivf_entries/20261117T014907Z-binding/receipt.json) `cosine_ivf_search`, `cosine_kg_IVF`). One graph holds `long_off` = (10,0,0,0), `unit_on` = (0.6,0.8,0,0) and `other` = (0,0,1,0); `ivf_build(..., metric="cosine")`, then the query (0.6,0.8,0,0). `ivf_search` and `SELECT kg_IVF(...)` both answer `long_off` 6.0, `unit_on` 1.0, `other` 0.0. Passing neighbor on the same vectors: the route search `search_nodes_by_vector` answers `unit_on` 1.0, `long_off` 0.6, `other` 0.0. Not exercised: `vector_search`'s IVF fallback and `kg_RRF_FUSE`'s IVF leg (the fixture supports `VECTOR_COSINE`, so the fallback is not taken).

Expected: the metric's name and default (`ivf_build(metric="cosine")`, reported back by `ivf_info`); `_IVF_METRICS` accepts "cosine" and "dot" as different choices; the route search ranks by cosine, and `VecIndex` was changed in 4.7.0 so that a cosine index scores the cosine.

Observed: every branch that scores under "cosine" computes `$vectorop("sum", $vectorop("v*", q, v))`, the same as "dot": centroid choice and entry scoring in `Search` (`IVFIndex.cls:75-78`, `112-115`) and the cell choice in `Insert` (`:200-201`). `ivf_build` clusters the raw vectors with Euclidean k-means whatever the metric and stores them in those cells (`vector.py:1985-2017`, `AddBatch`); nothing divides by a length. So under "cosine" the build's cells follow distance while `Search` and `Insert` follow the dot product ([review 47-49](../uplift/consolidated/iteration-50/REVIEW-47-49.md) m8; see [bug-srch-107](#bug-srch-107)).

Consequence: with stored vectors that are not unit length (`store_embedding` accepts any), a cosine IVF index returns a different top k from the route search on the same data, through both the Python and the SQL reader. Unit-length embeddings, which most providers return, are unaffected. Medium: wrong ranking under a confirmed but data-dependent trigger.

Repair proposal (not implemented): normalize vectors and centroids at build and insert time for metric "cosine" (or divide by the stored length at search time). Preserve: "dot" and "l2"/"euclidean" scores unchanged; equal-length vectors keep their order. Writers: `ivf_build`, `AddBatch`, `Insert`; readers: `Search` (via `ivf_search`, `kg_IVF`, `ivg.ivf.search`, `vector_search`'s fallback, `kg_RRF_FUSE`). The control `cosine-normalized` checks the repaired order in the model only; the repair was not run on the product. Governing statement: [search.ivf.metric](../ontology/features/search.g5.md#search.ivf.metric).

<a id="bug-srch-110"></a>
### The engine's fusion reads a cosine IVF index only in the process that built it, so the same call ranks differently elsewhere

Severity: Medium · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 49)

Found by: W56 prediction F7 ([predictions](../uplift/consolidated/iteration-49/retrieval-PAIRS.md); held for the building engine, missed for a fresh engine and the operators) and the source of `_fusion_leg_index` / `_index_graph`; [retrieval_compose](models/retrieval_compose/NOTES.md) `theorem_fused_leg_depends_on_building_engine` with neighbor `theorem_other_graph_ivf_not_read`; controls `ivf-scope-persisted`, `hnsw-before-own-ivf`, `ivf-cosine-normalized`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-49/retrieval-observed-20261117T023944Z.json) `leg_index_choice_*`, `F7_engine_building`, `F7_engine_fresh`, `F7_ops_fresh`; [binding](results/retrieval_compose/20261117T024807Z-binding/receipt.json) `choice_building`, `choice_fresh`, `engine_fuse_building`, `engine_fuse_fresh`, `ops_fuse_fresh`). One graph with 62 vectors including L = (10,10,0,0); `ivf_build(..., metric="cosine")` in engine e1. The same `kg_RRF_FUSE(100, 200, 200, 60, [1,0,0,0], "zeta", graph=g)` answers L 31st in e1 (it reads the IVF index, which scores L's dot product 10 first) and 62nd in a fresh engine and in `IRISGraphOperators` (they cannot tell the index's graph and read the server-side cosine search). Passing neighbor: before the IVF build, e1 answers exactly as the fresh engine does.

Expected: one answer per call and data; [search.ivf.metric](../ontology/features/search.g5.md#search.ivf.metric) (a cosine index scores the cosine).

Observed: `ivf_build` records the index's graph only in the building engine's `_index_graph_scopes` (`vector.py:2023-2025`); `_index_graph` answers None for an IVF index in any other engine (`:164-176`), and `_fusion_leg_index` prefers an index recorded for the graph over `hnsw` (`:187-225`). The IVF leg (`ivf_search`) also ignores `graph`.

Consequence: a service that builds its IVF index in one process and searches in another (or restarts) silently changes the vector leg and the fused ranking; with non-unit vectors, the building process ranks by bug-srch-109's dot product. Medium: wrong ranking, data- and process-dependent.

Repair proposal (not implemented): record an IVF index's graph with the index (as BM25 does) and choose the leg by that, and repair bug-srch-109; preserve the BM25 leg's choice and the hnsw leg's graph scope. Governing statement: [search.fusion.leg_index](../ontology/features/search.g5.md#search.fusion.leg_index).

<a id="bug-plt-114"></a>
### kg_SUBGRAPH misses edges among the outermost nodes and lists an edge to a node it left out when capped

Severity: Medium · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 49)

Found by: the source of `Graph.KG.Subgraph.SubgraphJson` while tracing bug-plt-113; [retrieval_compose](models/retrieval_compose/NOTES.md) `theorem_last_hop_edges_missing`, `theorem_capped_subgraph_lists_edge_to_unlisted_node`; control `edge-recorded-after-cap-test`. Iteration 50: `theorem_capped_subgraph_lists_edge_to_unlisted_node` now holds for every node, adjacency and state at the cap ([review 47-49](../uplift/consolidated/iteration-50/REVIEW-47-49.md) m9); the repair is checked in the model by the control `edges-among-answered`, which also repairs bug-plt-113's edge loss.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-49/retrieval-observed3-20261117T024208Z.json) `S_star_1hop`, `S_star_cap3`, `S_isolated_seed`; [follow-up](../uplift/consolidated/iteration-49/retrieval-observed2-20261117T024059Z.json) `S_cap*`; [binding](results/retrieval_compose/20261117T024807Z-binding/receipt.json) `subgraph[*]`). Star s → a1..a6 plus a1 → a2: `kg_SUBGRAPH([s], k_hops=1)` answers a1 and a2 but not the edge a1 → a2; with `max_nodes=3` it answers s, a1, a2 and the edge s → a3; a seed with no edges is not answered. Passing neighbor: `k_hops=2` lists a1 → a2.

Expected: [algorithms.op.subgraph](../ontology/features/algorithms.g5.md#algorithms.op.subgraph): the nodes within `k_hops`, at most `max_nodes`, and the edges among them.

Observed: `SubgraphJson` records only edges leaving a frontier node, records the edge before the cap test and quits, and admits a seed only when it has an edge either way (`Subgraph.cls:38-99`).

Consequence: callers that read the edge list (context building, `kg_PPR_GUIDED_SUBGRAPH`) miss relationships among returned nodes and can meet an edge whose end is not in the node list. Medium: visible wrong structure, no stored data changed.

Repair proposal (not implemented): after the walk, list every edge whose two ends are answered (and drop a crossing edge at the cap); answer an isolated seed as a node. Preserve the hop limit, the cap and the edge-type filter. Governing statement: [algorithms.op.subgraph](../ontology/features/algorithms.g5.md#algorithms.op.subgraph).

<a id="bug-cyp-111"></a>
### A list index known only at run time fails the query when it is negative, for a list read from a property or indexed by a parameter, and answers the element as text

Severity: Medium · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 47)

Found by: the frozen W54 prediction L2 missed ([predictions](../uplift/consolidated/iteration-47/cypherfn-PAIRS.md)); narrowed by [review 47-49](../uplift/consolidated/iteration-50/REVIEW-47-49.md) item 2 (a WITH-held literal list answers correctly); [cypher_fns](models/cypher_fns/NOTES.md) `theorem_row_negative_index_fails` and `theorem_param_negative_index_fails` with neighbors `theorem_with_literal_row_index_follows_rule`, `theorem_literal_index_follows_rule`, `theorem_row_nonnegative_index_follows_rule` and `theorem_ivglistget_is_rule`; controls `row-index-through-ivglistget`, `with-literal-elem-unwrapped`, `with-literal-elem-untyped`, `literal-negative-unwrapped`, `ivglistget-no-wrap`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([iteration-47 observation](../uplift/consolidated/iteration-47/cypherfn-observed2-20261117T015618Z.json) `I_row_*`, `I_param_neg`, `I_with_list_neg`; iteration 50: [fresh repro](../uplift/consolidated/iteration-50/review-repro-20261117T031150Z.json) `idx_*`, [binding](results/cypher_fns/20261117T033050Z-binding/receipt.json) `index_<source>_<kind>_<i>`, 63 cases over three list sources). Over a stored `n.l = [1, 2, 3]`, `UNWIND [-1] AS i RETURN n.l[i]` (and -3, -4) fails with `-149 ... JSON_ARRAYGET ... <RANGE>`; `WITH n.l AS l UNWIND [-1] AS i RETURN l[i]` fails `<RANGE>` in `JSON_VALUE`; `n.l[$i]` fails "Incorrect number of parameters" for every value; `WITH [1, 2, 3] AS l RETURN l[$i]` with `$i = -1` fails `<RANGE>`. A non-negative run-time index into a list from a property answers text: `UNWIND [0] AS i RETURN n.l[i]` answers `'1'` where `n.l[0]` answers 1. Passing neighbors: a WITH-held literal list read by a row index follows the rule with the element's type (`WITH [1, 2, 3] AS l UNWIND [-1] AS i RETURN l[i]` answers the integer 3, review item 2); every literal index; `CypherFn_IVGLISTGET('[1,2,3]', '-1')` answers 3.

Expected: openCypher (TCK `List1`): a negative index counts from the end, an index past either end is null, and the element keeps its type. The translator already wraps a literal negative index (4.6.0 R267) and a row index into a WITH-held literal list (R308, `CY_LIST_ELEM`).

Observed: `_expr_subscript` decides by the list's source and the index's syntax (`translator.py:23509-23656`). A property read takes `JSON_ARRAYGET(l, CAST(i AS INTEGER))`; another WITH column takes `JSON_VALUE(l, '$.' || i)`; a parameter index is inlined into `JSON_ARRAYGET` for a WITH column and left as a marker IRIS refuses on a property read. `Graph_KG.JSON_ARRAYGET` and `JSON_VALUE` are `%Get(i)` (`schema.py:2179-2184`), which raises `<RANGE>` below 0 and answers text. Only a row index into a WITH-held literal list reaches `CY_LIST_ELEM` (`_is_row_list_elem`, `translator.py:7681-7732`).

Consequence: a query that indexes a stored list with a computed or unwound negative index, or any list with a negative parameter, returns nothing and an error; with a non-negative index into a stored list the value comes back as a string. Medium.

Repair proposal (not implemented): emit `CY_LIST_ELEM` (typed, wraps negatives) for every run-time index, whatever the list's source, and compute a parameter index in Python as R311 does for literals. Preserve: literal indexes, the WITH-literal path, null past either end, and a null index giving null (today it does not: [bug-cyp-126](#bug-cyp-126)). Writers and readers affected: the `RETURN`/`WITH` columns that read an element, and `CY_LIST_ELEM`'s callers. Distinguishing case: `MATCH (n) UNWIND [-1] AS i RETURN n.l[i]` answers 3 while `WITH [1, 2, 3] AS l UNWIND [-1] AS i RETURN l[i]` still answers 3. The control `row-index-through-ivglistget` checks the repaired rule in the model only. Governing statement: [query.functions.list_index](../ontology/features/cypher.g5.md#query.functions.list_index).

<a id="bug-cyp-112"></a>
### reverse() of a list held in a property, a slice, a subscript or a coalesce reverses its JSON text, and of a WITH column from a property answers the JSON text

Severity: Medium · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 47)

Found by: the frozen W54 prediction L1 missed ([predictions](../uplift/consolidated/iteration-47/cypherfn-PAIRS.md)); widened by [review 47-49](../uplift/consolidated/iteration-50/REVIEW-47-49.md) item 3 (slice, subscript, coalesce, and the Variable case the model mispredicted); [cypher_fns](models/cypher_fns/NOTES.md) `theorem_stored_list_reversed_as_text`, `theorem_unknown_list_variable_answered_as_text`, neighbor `theorem_reverse_neighbors`; controls `property-to-cy-reverse`, `reverse-column-typed`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([iteration-47 observation](../uplift/consolidated/iteration-47/cypherfn-observed-20261117T015433Z.json) `L1_list`, `L1_empty`; iteration 50: [fresh repro](../uplift/consolidated/iteration-50/review-repro-20261117T031150Z.json) `rev_*`, [binding](results/cypher_fns/20261117T033050Z-binding/receipt.json) `reverse_*`, eleven argument forms). For a Cypher-written `n.l = [1, 2, 3]`: `reverse(n.l)` and `reverse(coalesce(n.l, []))` answer the string `']3 ,2 ,1['`; `WITH [1, 2, 3] AS l RETURN reverse(l[0..3])` answers `']3,2,1['`; `WITH [[1, 2, 3], [4]] AS l RETURN reverse(l[0])` answers `']3,2,1['`; `WITH n.l AS l RETURN reverse(l)` answers the string `'[3,2,1]'` (reversed, but as text). Passing neighbors: `reverse([1, 2, 3])`, `WITH [1, 2, 3] AS l RETURN reverse(l)`, `reverse(n.l + [])`, `reverse(tail(n.l))` and `reverse(CASE WHEN 1 = 1 THEN [1, 2, 3] END)` answer lists; `reverse(n.str)` of `'gotcha'` answers `'ahctog'`.

Expected: openCypher: `reverse()` of a list is the list in reverse order; of a string, the reversed string.

Observed: two decisions. `_scalar_string` sends only list literals, comprehensions, list-valued calls (by `_container_kind`), variables and `CASE` to `CY_REVERSE`; a property read, a slice, a subscript or another call goes to SQL `REVERSE()`, which reverses the text (`translator.py:24495-24513`). And `CY_REVERSE`'s JSON answer is decoded into a list only for a column the translator knows to be a list, so a variable from a property comes back as JSON text.

Consequence: wrong values for a common list operation on stored data. Medium.

Repair proposal (not implemented): send every non-literal argument to `CY_REVERSE`, which already reverses a JSON array or a string by its run-time value, and mark the column for decoding by the value's run-time kind. A stored string that spells a list would then reverse as the list (the documented known issue). Preserve: string arguments and the list forms that work today. Distinguishing case: `WITH n.l AS l RETURN reverse(l)` answers `[3, 2, 1]` and `reverse(n.str)` still `'ahctog'`. Controls `property-to-cy-reverse` and `reverse-column-typed` check the two halves in the model only. Governing statement: [query.functions.reverse](../ontology/features/cypher.g5.md#query.functions.reverse).

<a id="bug-cyp-113"></a>
### n[k] with a key from UNWIND reads the property named "k", so keys(n) then n[k] answers null for every key

Severity: Medium · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 47)

Found by: the frozen W54 prediction L7 missed, then source reading ([predictions](../uplift/consolidated/iteration-47/cypherfn-PAIRS.md)); [cypher_fns](models/cypher_fns/NOTES.md) `theorem_row_key_reads_variable_name`, neighbor `theorem_param_key_follows_rule`, control `row-key-by-value`; the WITH-column failure (already in this entry's evidence) gained `theorem_with_column_key_fails` and control `with-key-by-value` in iteration 50 ([review 47-49](../uplift/consolidated/iteration-50/REVIEW-47-49.md) m5; [binding](results/cypher_fns/20261117T033050Z-binding/receipt.json) `node_with_key`, [fresh repro](../uplift/consolidated/iteration-50/review-repro-20261117T031150Z.json) `key_from_with_column`).

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-47/cypherfn-observed2-20261117T015618Z.json) `N_row_key`, `N_with_key`; [idiom](../uplift/consolidated/iteration-47/cypherfn-observed3-20261117T020020Z.json) `keys_idiom`; [binding](results/cypher_fns/20261117T015955Z-binding/receipt.json) `node_row_key`). A node with `k: 'gotcha'`, `num: 5`: `UNWIND ['num', 'str', 'zz'] AS k RETURN k, n[k]` answers `'gotcha'` on every row; `MATCH (n) UNWIND keys(n) AS k RETURN k, n[k]` answers null for every key; `WITH n, 'str' AS k RETURN n[k]` raises "Non-integer index type for list subscript". Passing neighbor: `n[$k]` with `$k = 'num'` answers 5.

Expected: openCypher: `n[k]` is the property whose name is `k`'s value.

Observed: for a `Variable` index on a node, `_expr_subscript` binds `context.input_params.get(idx.name, idx.name)`, so a variable that is not a parameter becomes its own name as the key of the `rdf_props` join (`translator.py:23533-23541`). A node carried through `WITH` is a stage column, so `n[k]` takes the scalar branch, where a key known to be a string raises "Non-integer index type for list subscript" (`translator.py:23583-23610`).

Consequence: dynamic property reads silently answer another property or null. Medium: wrong values with no error.

Repair proposal (not implemented): translate the index expression for a variable that is not a parameter, as for other expressions. Governing statement: [query.functions.dynamic_access](../ontology/features/cypher.g5.md#query.functions.dynamic_access).

<a id="bug-cyp-114"></a>
### randomUUID() and rand() give one value for every row of a query, and a CREATE that uses one is refused

Severity: Medium · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 47)

Found by: the frozen W54 prediction L12 missed ([predictions](../uplift/consolidated/iteration-47/cypherfn-PAIRS.md)); [cypher_fns](models/cypher_fns/NOTES.md) `theorem_rows_share_one_value` (conditional on the observed IRIS premise), control `per-row-evaluation`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-47/cypherfn-observed2-20261117T015618Z.json) `R_return`, `R_collect`, `R_create_*`; [CREATE neighbors](../uplift/consolidated/iteration-47/cypherfn-observed3-20261117T020020Z.json); [binding](results/cypher_fns/20261117T015955Z-binding/receipt.json) `uuid_distinct_over_5`, `rand_distinct_over_5`). `UNWIND [1, 2, 3] AS i RETURN randomUUID(), rand()` answers the same UUID and the same float on all three rows; `UNWIND range(1, 50) AS i WITH randomUUID() AS u RETURN count(DISTINCT u)` answers 1. `CREATE (:X {u: randomUUID()})`, with or without `UNWIND`, fails "nothing written: <LIST ERROR> Cannot write argument in list"; the same `UNWIND ... CREATE` with `u: 'x'` writes three nodes. Other functions inside a `CREATE` map were not checked.

Expected: openCypher: each call of `randomUUID()` returns a new UUID and `rand()` a new number.

Observed: the translator emits `Graph_KG.NEWID()` and `Graph_KG.RAND()`, calls without a row argument (`translator.py:26919-26924`; `schema.py:2321, 2324`); IRIS 2026.1 evaluates each once per statement. The write refusal was traced in iteration 48: [bug-cyp-119](#bug-cyp-119) (any function the Python constant folder does not work out).

Consequence: generated identifiers repeat across rows of a read, and cannot be generated in a `CREATE` at all. Medium.

Repair proposal (not implemented): pass a row-dependent argument (or declare the functions non-deterministic) so IRIS evaluates them per row, and accept a function value in a `CREATE` map. Governing statement: [query.functions.random](../ontology/features/cypher.g5.md#query.functions.random).

<a id="bug-cyp-117"></a>
### A negative list-slice bound known only at run time counts as 0

Severity: Medium · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 48)

Found by: the frozen W55 prediction L1 missed ([predictions](../uplift/consolidated/iteration-48/cypherexpr-PAIRS.md)); [cypher_exprs](models/cypher_exprs/NOTES.md) `theorem_row_negative_slice_departs` with neighbors `theorem_literal_slice_follows_rule` and `theorem_row_nonnegative_slice_follows_rule`; controls `row-slice-wrapped`, `literal-slice-unwrapped`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-48/cypherexpr-observed-20261117T021241Z.json) `L1_rows`, `L1_param`; [follow-up](../uplift/consolidated/iteration-48/cypherexpr-observed2-20261117T021350Z.json) `F3_*`; [binding](results/cypher_exprs/20261117T022154Z-binding/receipt.json) `slice_row_*`, `slice_param_*`, `slice_literal_*`). Over a stored `n.l = [1, 2, 3, 4, 5]`, `UNWIND [[-3, -1]] AS ab RETURN n.l[ab[0]..ab[1]]` answers `[]` (rule `[3, 4]`), `[-3, 5]` answers the whole list (rule `[3, 4, 5]`), `[0, -1]` answers `[]` (rule `[1, 2, 3, 4]`); parameters `n.l[$a..$b]` behave the same, and so does a list the query holds (`WITH [1, 2, 3, 4, 5] AS l`). Passing neighbors: the same bounds written in the query (`n.l[-3..-1]` is `[3, 4]`), and every non-negative run-time bound.

Expected: openCypher (TCK `List2` [6], [8]): a negative bound counts from the end; bounds are clamped to the list.

Observed: `_expr_slice` wraps a literal negative bound as `GREATEST(0, JSON_ARRAYLENGTH(l) + n)` and passes any other bound as it is into `rn > (start) AND rn <= (end)` (`translator.py:23741-23772`), so a negative run-time start keeps every row and a negative run-time end keeps none.

Consequence: a slice computed from data (`l[-k..]`, `l[..-1]` with a parameter) silently answers the wrong elements. Medium.

Repair proposal (not implemented): give a run-time bound the same wrap in SQL (`CASE WHEN b < 0 THEN GREATEST(0, len + b) ELSE b END`); preserve literal bounds and null bounds. The control `row-slice-wrapped` checks the repaired rule in the model only (the non-negative neighbor stays verified); see [one run-time path for list positions](design_simplification.md#simp-cyp-101). Governing statement: [query.functions.slice](../ontology/features/cypher.g5.md#query.functions.slice).

<a id="bug-cyp-118"></a>
### A boolean known only at run time cannot be a CASE WHEN or WHERE condition

Severity: Medium · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 48)

Found by: the frozen W55 prediction C4 missed for its `UNWIND` half ([predictions](../uplift/consolidated/iteration-48/cypherexpr-PAIRS.md)); [cypher_exprs](models/cypher_exprs/NOTES.md) `theorem_row_boolean_condition_fails` (conditional on the observed IRIS premise) with neighbor `theorem_predicate_condition_follows_rule`; controls `row-condition-compared`, `property-condition-raw`, `iris-accepts-scalar-condition`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-48/cypherexpr-observed-20261117T021241Z.json) `C4_unwind`; [follow-up](../uplift/consolidated/iteration-48/cypherexpr-observed2-20261117T021350Z.json) `F6_*`; [binding](results/cypher_exprs/20261117T022154Z-binding/receipt.json) `cond_*`, `where_RowVar_*`). `UNWIND [true, false] AS f RETURN CASE WHEN f THEN 'y' ELSE 'n' END`, `WITH true AS f RETURN CASE WHEN f ...`, `RETURN CASE WHEN $f ...` and `UNWIND [true, false] AS f WITH f WHERE f RETURN f` each fail at Prepare with SQLCODE -14 "A comparison operator is required here". Passing neighbors: a stored boolean property (`CASE WHEN n.flag`), a literal, `f = true`, `NOT f`, `f AND true` and the simple `CASE f WHEN true`.

Expected: openCypher: any boolean expression is a condition; `CASE WHEN b` takes the branch when `b` is true.

Observed: `_translate_boolean_expression` turns a literal, a property read, a map access and a comparison into predicates, but returns the SQL of a bare variable or parameter as it is (`translator.py:18688-18716`); IRIS 2026.1 refuses a scalar in a predicate position. The known issue "A boolean property of a map row reads as false in a CASE WHEN" is a neighbor (`input.fixed`), not this shape.

Consequence: a query that branches or filters on a computed or passed-in flag fails outright. Medium.

Repair proposal (not implemented): compare a bare row or parameter boolean as `= 1` (or route it through `_stored_bool_in`'s JSON-kind test). The control `row-condition-compared` checks the repaired rule in the model only. Governing statement: [query.values.conditions](../ontology/features/cypher.g5.md#query.values.conditions).

<a id="bug-cyp-119"></a>
### A node CREATE whose map value calls a function IVG does not work out in Python is refused

Severity: Medium · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 48)

Found by: the frozen W55 prediction W2 missed (W3 held as the owner predicted) ([predictions](../uplift/consolidated/iteration-48/cypherexpr-PAIRS.md)); the source reading traced bug-cyp-114's `CREATE` refusal; [cypher_exprs](models/cypher_exprs/NOTES.md) `theorem_unfolded_create_value_refused` with neighbor `theorem_folded_create_value_written`; controls `create-value-translated`, `toupper-not-folded`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-48/cypherexpr-observed-20261117T021241Z.json) `W2_*`, `W3_*`; [follow-up](../uplift/consolidated/iteration-48/cypherexpr-observed2-20261117T021350Z.json) `F7_*`; [binding](results/cypher_exprs/20261117T022154Z-binding/receipt.json) `create_node_*`, `set_node_*`). `CREATE (:X {id: 'a', v: size('ab')})` fails "execute_cypher failed, nothing written: <LIST ERROR> Cannot write argument in list: unknown list type detected", and so do `abs(-1)`, `toInteger('5')`, `substring('abc', 1)`, `replace('a', 'a', 'b')`, `randomUUID()` and `rand()`, with or without `UNWIND`; no node is written. Passing neighbors: `toUpper('ab')`, `toLower`, `trim`, `coalesce(null, 'x')`, `toString(1)`, `toInteger(2.5)`, `1 + 1` and `toUpper($s)` are stored, and `SET x.v = <each of the 15 shapes>` stores the value.

Expected: openCypher: a `CREATE` stores each property value its map computes.

Observed: `_create_resolve_prop_value` asks `_fold_constant` to work out a function value in Python; the folder handles coalesce, the case and trim functions, `toString`, `toFloat`/`toInteger` of a number and arithmetic, and returns `_NOT_CONSTANT` for anything else, and the function then returns the AST itself (`translator.py:9594-9599`, `9670`), which the node INSERT binds as an argument and the driver refuses.

Consequence: a node cannot be created with a generated identifier, a size, an absolute value or a parsed number in one statement; the whole write is refused (nothing partial). Medium. bug-cyp-114 named the `randomUUID()` and `rand()` cases; this is their cause.

Repair proposal (not implemented): translate an unfolded value to SQL as `SET` does (control `create-value-translated` checks the repaired rule in the model only); see [one SQL path for computed write values](design_simplification.md#simp-cyp-102). Governing statement: [query.writes.computed_values](../ontology/features/cypher.g5.md#query.writes.computed_values).

<a id="bug-cyp-126"></a>
### A null list index known only at run time answers the list's first element instead of null

Severity: Medium · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 50)

Found by: [review 47-49](../uplift/consolidated/iteration-50/REVIEW-47-49.md) item 6 (reviewer probe `p2`); [cypher_fns](models/cypher_fns/NOTES.md) `theorem_null_index_reads_first_element`; controls `null-index-is-null`, `row-index-through-ivglistget`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([fresh repro](../uplift/consolidated/iteration-50/review-repro-20261117T031150Z.json) `idx_null_*`; [binding](results/cypher_fns/20261117T033050Z-binding/receipt.json) `index_*_null`). `WITH [1, 2, 3] AS l UNWIND [null] AS i RETURN l[i]` answers `'1'`; so do `MATCH (n) RETURN n.l[null]`, `n.l[n.nope]`, `UNWIND [null] AS i RETURN n.l[i]`, `WITH n.l AS l UNWIND [null] AS i RETURN l[i]` and `WITH [1, 2, 3] AS l RETURN l[null]`. A null parameter index fails "Incorrect number of parameters". Passing neighbor: the literal list `[1, 2, 3][null]` answers null (folded by the translator).

Expected: openCypher (TCK `List1`): a null index gives null.

Observed: the run-time paths of `_expr_subscript` hand the null to `JSON_ARRAYGET(l, CAST(NULL AS INTEGER))` or `JSON_VALUE(l, '$.' || CAST(NULL AS VARCHAR))` (`translator.py:23620-23656`). IRIS passes SQL NULL to an ObjectScript function as `""`; `%Get("")` reads position 0, and `'$.' || NULL` is the path `'$.'` whose key `""` also reads position 0 (`schema.py:2179-2184`). `CY_LIST_ELEM` would also read position 0 for `""`.

Consequence: a missing index silently selects the first element, so `l[m.idx]` over rows lacking `idx` returns a real-looking value. Medium: wrong value with no error.

Repair proposal (not implemented): test the index for null before the lookup (`CASE WHEN i IS NULL THEN NULL ELSE ... END`) on every run-time path, or have the element functions treat `""` as null. Preserve: the literal-list fold and every non-null index. Distinguishing case: `UNWIND [null, 0] AS i RETURN n.l[i]` answers null then 1. The control `null-index-is-null` checks the property path in the model only. Governing statement: [query.functions.list_index](../ontology/features/cypher.g5.md#query.functions.list_index).

<a id="bug-cyp-127"></a>
### A simple CASE over a property or a row value takes a WHEN of another type when the text matches

Severity: Medium · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 50)

Found by: [review 47-49](../uplift/consolidated/iteration-50/REVIEW-47-49.md) item 7 (reviewer probe `p5`); [cypher_exprs](models/cypher_exprs/NOTES.md) `theorem_simple_case_coerces_across_kinds` with neighbor `theorem_simple_case_same_kind_or_literal_follows_rule`; controls `case-kinds-compared`, `case-literal-kinds-unchecked`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([fresh repro](../uplift/consolidated/iteration-50/review-repro-20261117T031150Z.json) `case_simple_*`, `eq_prop_str_vs_int`; [binding](results/cypher_exprs/20261117T033119Z-binding/receipt.json) `simple_case_*`, nine kind pairs). With `n.s1 = '1'` and `n.i1 = 1`: `CASE n.s1 WHEN 1 THEN 'num' WHEN '1' THEN 'str' END` answers `'num'`; `UNWIND ['1'] AS s RETURN CASE s WHEN 1 ...` answers `'num'`; `CASE n.i1 WHEN '1' THEN 'str' ...` answers `'str'`. Passing neighbors: `n.s1 = 1` is false and `CASE WHEN n.s1 = 1 THEN 'num' ELSE 'other' END` answers `'other'`; `CASE '1' WHEN 1 ...` (literal test) takes the ELSE; same-type WHENs match.

Expected: openCypher and [query.values.equality](../ontology/features/cypher.g5.md#query.values.equality): a simple CASE takes the first WHEN equal to the test, and `'1'` does not equal 1.

Observed: `_expr_case` drops a WHEN of another kind only when both kinds are known statically, which `_static_value_kind` knows only for literals; every other WHEN goes to SQL `CASE x WHEN y`, which IRIS evaluates with its own coercion, so a number equals text that spells it (`translator.py:22189-22238`).

Consequence: a branch chosen on stored or unwound data can be wrong while the equivalent generic `CASE` is right. Medium: wrong value with no error.

Repair proposal (not implemented): translate a simple CASE whose test or WHEN kind is unknown to the generic form through the typed comparison `=` already uses (`CY_JCMP`), keeping the static drop for literals. Preserve: literal simple CASEs, same-type matches, null tests taking the ELSE. Distinguishing case: `CASE n.s1 WHEN 1 THEN 'num' ELSE 'other' END` answers `'other'` while `CASE n.i1 WHEN 1 ...` still answers `'num'`. The control `case-kinds-compared` checks the repaired rule in the model only. Governing statement: [query.values.conditions](../ontology/features/cypher.g5.md#query.values.conditions).

<a id="bug-cyp-128"></a>
### A SET or CREATE of a list literal that holds a property read fails with a raw Python TypeError and writes nothing

Severity: Medium · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 50)

Found by: [review 47-49](../uplift/consolidated/iteration-50/REVIEW-47-49.md) m3 (reviewer probe `p4`). No formal contract (probe and source reading only).

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([fresh repro](../uplift/consolidated/iteration-50/review-repro-20261117T031150Z.json) `set_list_from_props`; [follow-up](../uplift/consolidated/iteration-50/review-repro2-20261117T032546Z.json) `set_list_*`, `create_list_property_elem`, `after_refusal_read`). `MATCH (n) SET n.l1 = [n.a, 1]` and `MATCH (n) CREATE (:X {l: [n.a, 1]})` raise `TypeError: Object of type PropertyReference is not JSON serializable` before any SQL runs; `n.l1` stays null. Passing neighbors: `[x, 1]` from `UNWIND`, `[$x, 1]` and `[1 + 1, 1]` are stored.

Expected: openCypher: a list literal's elements are evaluated per row and the list is stored; where IVG cannot, a Cypher error naming the property, as the matched-relationship refusal does.

Observed: `_translate_set_value` hands a list literal to `_constant_value` and, when that answers `_NOT_CONSTANT`, `json.dumps` the raw elements, AST nodes included (`translator.py:12638-12642`).

Consequence: an ordinary write is refused with an internal error that names no Cypher concept. Medium (refusal of a valid write; nothing partial).

Repair proposal (not implemented): build the list in SQL from translated elements (as `SET` translates scalars), or refuse with a `CypherError` naming the property. Preserve: constant lists and row-literal lists. Governing statement: [query.writes.computed_values](../ontology/features/cypher.g5.md#query.writes.computed_values).

<a id="bug-cyp-115"></a>
### A map value read by a key answers numbers and booleans as text

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 47)

Found by: the frozen W54 prediction L7 missed ([predictions](../uplift/consolidated/iteration-47/cypherfn-PAIRS.md)). No formal contract: probe only, open in Verus.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-47/cypherfn-observed2-20261117T015618Z.json) `M_rows_types`, `M_literal_key`). `WITH {a: 1, b: 2.5, c: true, d: [1]} AS m UNWIND ['a', 'b', 'c', 'd'] AS k RETURN k, m[k]` answers `'1'`, `'2.5'`, `'1'`, `'[1]'`; `m['a']` answers `'1'` and `m.c` answers 1 for `true`. A missing key answers null, as expected. `WITH $m AS m RETURN m[$k]` fails "Incorrect number of parameters".

Expected: openCypher: the map's value with its type.

Observed: a string or variable key becomes `JSON_VALUE(m, '$.' || key)`, which answers text (`translator.py:23565-23575, 23638-23639`). Related documented issue: a property of a map in a parameter list reads a boolean as 1 (KNOWN_ISSUES).

Consequence: comparisons and arithmetic on such values see strings. Low. Governing statement: [query.functions.dynamic_access](../ontology/features/cypher.g5.md#query.functions.dynamic_access).

<a id="bug-cyp-116"></a>
### head() of a number fails with an error that does not name TypeError

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 47)

Found by: the frozen W54 prediction L11 partly missed ([predictions](../uplift/consolidated/iteration-47/cypherfn-PAIRS.md)). No formal contract: probe only.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-47/cypherfn-observed2-20261117T015618Z.json) `T_head_number_msg`, `T_head_number_literal`). `head(n.num)` of a stored 5, `n.num[0]` and `head(n.str)` fail with `CY_LIST_ELEM failed ... %msg=` (empty); `RETURN head(5)` with `JSON_ARRAYGET failed ... %msg=`.

Expected: the 4.6.0 CHANGELOG: a type error on a row fails with IRIS's error text "which contains the openCypher name" (`TypeError`), so a caller can test for it with `in`.

Observed: the list element functions raise without a message (`schema.py:2300`, `2179`).

Consequence: callers cannot tell a type error from another failure. Low. Governing statement: [query.functions](../ontology/features/cypher.g5.md#query.functions).

<a id="bug-cyp-121"></a>
### coalesce over row values, literals or parameters answers numbers and booleans as text

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 48)

Found by: the frozen W55 prediction C3's literal neighbor missed ([predictions](../uplift/consolidated/iteration-48/cypherexpr-PAIRS.md)); [cypher_exprs](models/cypher_exprs/NOTES.md) `theorem_row_coalesce_number_as_text` with neighbor `theorem_node_coalesce_keeps_type`; controls `coalesce-always-typed`, `coalesce-needs-two-props`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-48/cypherexpr-observed-20261117T021241Z.json) `C3_*`; [follow-up](../uplift/consolidated/iteration-48/cypherexpr-observed2-20261117T021350Z.json) `F5_*`; [binding](results/cypher_exprs/20261117T022154Z-binding/receipt.json) `coalesce_*`). `RETURN coalesce(null, 1)` answers `'1'`, `coalesce(null, 2.5, 'z')` `'2.5'`, `coalesce(null, true, 'z')` `'1'`; `UNWIND [7] AS x RETURN coalesce(x, 'z')` `'7'`; `coalesce($p, 1)` with `$p = 7` `'7'`; `coalesce(n.i, x)` with `x` from `UNWIND` `'7'`. Passing neighbors: `coalesce(n.missing, n.v, 'z')` and `coalesce(n.i, $p)` keep the stored integer.

Expected: openCypher (TCK `Conditional1`): `coalesce` returns its first non-null argument unchanged.

Observed: `_is_typed_coalesce` reads the winner with its type only when a node property is among node properties, scalar literals and scalar parameters (`translator.py:7620-7642`); otherwise `_scalar_coalesce` CASTs the first argument and later non-string literals to VARCHAR (`translator.py:24455-24472`). Related inherited entry: [bug-cyp-107](#bug-cyp-107) (a relationship property in `coalesce`).

Consequence: a defaulted number or flag arrives as a string, and later comparisons or arithmetic on it follow string rules. Low.

Governing statement: [query.functions.coalesce](../ontology/features/cypher.g5.md#query.functions.coalesce).

<a id="bug-cyp-122"></a>
### A list slice whose lower bound is a variable name does not parse

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 48)

Found by: the W55 probe's own query `n.l[a..3]` failed to parse ([observation](../uplift/consolidated/iteration-48/cypherexpr-observed-20261117T021241Z.json) `L1_rows_scalar`); [cypher_exprs](models/cypher_exprs/NOTES.md) `theorem_identifier_lower_bound_refused` with neighbor `theorem_other_lower_bounds_parse`; control `identifier-lookahead`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([follow-up](../uplift/consolidated/iteration-48/cypherexpr-observed2-20261117T021350Z.json) `F4_*`; [binding](results/cypher_exprs/20261117T022154Z-binding/receipt.json) `parse_*`). `WITH [1, 2, 3] AS l, 1 AS a RETURN l[a..3]` fails "CypherParseError: Expected IDENTIFIER, got FLOAT_LITERAL"; `l[a..b]`, `l[a..]` and `l[a .. 3]` fail "Expected IDENTIFIER, got .". Passing neighbors: `l[1..b]`, `l[$a..3]`, `l[x[0]..3]`.

Expected: openCypher: any expression may be a slice bound.

Observed: `Parser.parse_primary_expression` reads a `.` after an identifier as a property access and then expects a name (`parser.py:1621-1641`); the postfix loop that serves other bounds looks ahead for `..` and the `.N` float, this branch does not.

Consequence: the query is refused (fails loudly); a workaround exists (`l[(a)..3]` was not tested; `l[x[0]..3]` works). Low.

Governing statement: [query.functions.slice](../ontology/features/cypher.g5.md#query.functions.slice).

<a id="bug-cyp-123"></a>
### A negative substring start answers leading characters instead of an error

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 48)

Found by: the frozen W55 prediction S2 partly missed ([predictions](../uplift/consolidated/iteration-48/cypherexpr-PAIRS.md)); [cypher_exprs](models/cypher_exprs/NOTES.md) `theorem_negative_start_answers_prefix` with neighbor `theorem_inside_substring_follows_rule`; controls `substring-checks-start`, `substring-zero-based`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-48/cypherexpr-observed-20261117T021241Z.json) `S2_neg_*`; [follow-up](../uplift/consolidated/iteration-48/cypherexpr-observed2-20261117T021350Z.json) `F1_*`, `F2_neg`; [binding](results/cypher_exprs/20261117T022154Z-binding/receipt.json) `substring_*`). `substring('hello', -1, 2)` and `substring(n.s, a, 2)` with `a = -1` from `UNWIND` answer `'h'`, `a = -3` answers `''`; `substring('hello', 1, -1)` fails SQLCODE -400 `<ILLEGAL VALUE>`, a fatal IRIS error naming no Cypher error; `left(n.s, -1)` answers null. Literal and run-time arguments behave alike here. Passing neighbors: every start and length inside the string.

Expected: the Cypher 9 function reference: a negative start or length raises an error (openCypher's TCK does not pin it).

Observed: `_scalar_string` emits `SUBSTRING(s, (start) + 1, len)` with no check (`translator.py:24488-24494`); IRIS takes positions below 1 as the string's start.

Consequence: a computed negative offset silently answers a different substring. Low.

Governing statement: [query.functions.strings](../ontology/features/cypher.g5.md#query.functions.strings).

<a id="bug-cyp-124"></a>
### A zero-length left, right or substring answers null instead of the empty string

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 48)

Found by: the frozen W55 prediction S3 partly missed ([predictions](../uplift/consolidated/iteration-48/cypherexpr-PAIRS.md)). No formal contract: probe only (open in Verus).

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-48/cypherexpr-observed-20261117T021241Z.json) `S3_*`; [follow-up](../uplift/consolidated/iteration-48/cypherexpr-observed2-20261117T021350Z.json) `F2_*`). `left('hello', 0)`, `right('hello', 0)`, `left(n.s, 0)`, `substring('hello', 2, 0)` and `substring(n.s, 1, 0)` answer null, for literal and run-time arguments; `substring('hello', 0, 0)` answers `''`. Passing neighbors: every length of 1 or more.

Expected: openCypher: an empty result is the empty string, not null.

Observed: the SQL functions answer IRIS's empty string, which SQL reads as null; not traced further.

Consequence: `IS NULL` tests and `coalesce` treat an empty prefix as missing. Low.

Governing statement: [query.functions.strings](../ontology/features/cypher.g5.md#query.functions.strings).

<a id="bug-cyp-125"></a>
### With the driver 5.3.2 an UNWIND of a list parameter fails "Invalid number of parameters"

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 48)

Found by: the first `cypher_exprs` binding run (its `UNWIND $pairs` read answered no rows, [receipt](results/cypher_exprs/20261117T022138Z-binding/receipt.json)); a follow-up after the binding. No formal contract: potential problem, conditional on the driver.

Reproduced by: **Partially reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin and its driver `intersystems-irispython` 5.3.2 (the fixture's venv); not run on 5.4.x. `UNWIND $xs AS a RETURN a` with `$xs = [1, 2]` answers `<PARAMETER ERROR> Invalid number of parameters`, and after a `MATCH` `<ARGUMENT ERROR> Incorrect number of parameters`; the translated SQL reads `JSON_TABLE(?, '$[*]' ...)`. Passing neighbor: `WITH $xs AS l UNWIND l AS a RETURN a` answers `[1], [2]`. Iteration 47's "Incorrect number of parameters" observations for `n.l[$i]` and `m[$k]` ([bug-cyp-111](#bug-cyp-111)) may share this premise.

Expected: the README: the TCK passes on Community 2026.1 with drivers 5.4.0 and 5.4.1; `pyproject.toml` accepts `intersystems-iris>=1.0.0`. The iris-sql-quirks guide (item 6) says a `?` inside `JSON_TABLE`'s source is not a parameter.

Observed: a potential problem only: whether 5.4.x binds the marker is not established here, and whether 5.3.x is a supported driver is not stated.

Consequence: if 5.3.x is supported, the main bulk-load pattern (`UNWIND $rows ...`) fails with it. Low until established.

Iteration 50 triage of [review 47-49](../uplift/consolidated/iteration-50/REVIEW-47-49.md) m2 ([fresh repro](../uplift/consolidated/iteration-50/review-repro-20261117T031150Z.json) `param_list_slice*`, `param_list_index`): `RETURN $l[$s..$e]` and `RETURN $l[$s..]` fail "Incorrect number of parameters", and `RETURN $l[$s]` "Invalid number of parameters", while `RETURN $l[1..3]` (worked out in Python, 4.6.0 R311) and `WITH $l AS l RETURN l[$s..$e]` answer `[2, 3]`. The translated slice reads `JSON_TABLE(?, ...)`, the same marker-in-`JSON_TABLE` shape as above, so this is the same premise, not a new finding. Source reading adds one fault that would remain on any driver: `_expr_slice` adds the null-guard markers to the parameter list after the slice's own markers but writes them first in the SQL (`translator.py:23778-23789`), so with a parameter list the first guard would receive the list's text. Not modeled (`cypher_exprs` has no parameter-list base).

Governing statement: [query.conformance](../ontology/features/cypher.g5.md#query.conformance).

<a id="bug-cyp-129"></a>
### Slicing a null list answers the empty list instead of null

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 50)

Found by: [review 47-49](../uplift/consolidated/iteration-50/REVIEW-47-49.md) m1 (reviewer probe `p4`); [cypher_exprs](models/cypher_exprs/NOTES.md) `theorem_null_list_slice_is_empty`; control `null-list-guard`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([fresh repro](../uplift/consolidated/iteration-50/review-repro-20261117T031150Z.json) `null_list_slice`, `null_list_index`; [binding](results/cypher_exprs/20261117T033119Z-binding/receipt.json) `null_list_slice_*`). `MATCH (n) RETURN n.missing[0..2]` answers `[]` for literal, row and parameter bounds. Passing neighbor: `n.missing[0]` answers null.

Expected: openCypher: an operation on null gives null.

Observed: `_expr_slice` returns NULL only for an explicit null bound; the list goes into `JSON_TABLE`, which yields no rows for NULL, and the aggregate answers `[]` (`translator.py:23679-23791`).

Consequence: a missing list reads as empty, so `size(n.missing[0..2])` is 0 instead of null. Low.

Repair proposal (not implemented): add the list to the null guard. Governing statement: [query.functions.slice](../ontology/features/cypher.g5.md#query.functions.slice).

<a id="bug-cyp-130"></a>
### trim() keeps tabs and line breaks in a query's result, while a node CREATE removes them

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 50)

Found by: [review 47-49](../uplift/consolidated/iteration-50/REVIEW-47-49.md) m4 (reviewer probe `p4`). No formal contract (probe and source reading only).

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([fresh repro](../uplift/consolidated/iteration-50/review-repro-20261117T031150Z.json) `trim_*`; [follow-up](../uplift/consolidated/iteration-50/review-repro2-20261117T032546Z.json) `return_trim_*`, `create_trim*`, `set_trim`). `RETURN trim('\t a \n')` answers the string unchanged (size 5), as does `trim(n.s)` and `SET n.t = trim(...)`; `rtrim('a \n')` keeps the line break while `ltrim('\t a')` answers `'a'`; `CREATE (:X {t: trim('\t a \n')})` stores `'a'`. Passing neighbor: `trim('  a  ')` answers `'a'`.

Expected: Neo4j's Cypher manual: `trim()` removes leading and trailing whitespace; the same expression gives the same value in `RETURN`, `SET` and `CREATE`.

Observed: `RETURN` and `SET` translate `trim` to SQL `TRIM` (`translator.py:29537`), which removes spaces only; the node `CREATE` folder works it out with Python's `str.strip` (`translator.py:9456`), which removes all whitespace.

Consequence: text with tabs or line breaks is compared or stored differently depending on the clause. Low.

Repair proposal (not implemented): trim the same whitespace set on both paths (SQL `$ZSTRIP`-style function or a Python fold limited to spaces), after deciding which set is intended. Governing statement: [query.functions.strings](../ontology/features/cypher.g5.md#query.functions.strings).

<a id="bug-cyp-131"></a>
### range() with a step known only at run time accepts a fractional step

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 50)

Found by: [review 47-49](../uplift/consolidated/iteration-50/REVIEW-47-49.md) m6 (reviewer probe `p1`). No formal contract: `cypher_fns`'s range model covers integer steps only.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([fresh repro](../uplift/consolidated/iteration-50/review-repro-20261117T031150Z.json) `range_fractional_step_*`; [follow-up](../uplift/consolidated/iteration-50/review-repro2-20261117T032546Z.json) `range_*`). `UNWIND [1.5] AS s RETURN range(1, 3, s)` and `range(1, 3, $s)` with 1.5 answer `[1, 2.5]`. Passing neighbors: the literal `range(1, 3, 1.5)` is refused ("must be an integer"); a run-time step of 2 answers `[1, 3, 5]`.

Expected: openCypher: `range()` takes integers; the translator already refuses a literal fractional step.

Observed: `CypherFn.IVGRANGE` loops with whatever step it receives (`CypherFn.cls:255`), and the translator checks only literal arguments (`translator.py:29114-29122`).

Consequence: a fractional run-time step yields non-integer elements instead of an error. Low.

Repair proposal (not implemented): raise in `IVGRANGE` for a non-integer argument, as for a step of 0 ([F-C0841](#F-C0841)). Governing statement: [query.functions.range](../ontology/features/cypher.g5.md#query.functions.range).

<a id="bug-cyp-132"></a>
### A relationship SET from a function of its own property is refused with a message that says such a read is allowed

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 50)

Found by: [review 47-49](../uplift/consolidated/iteration-50/REVIEW-47-49.md) m10 (reviewer probe `p3`). No formal contract (probe only).

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([fresh repro](../uplift/consolidated/iteration-50/review-repro-20261117T031150Z.json) `rel_retype*`; [follow-up](../uplift/consolidated/iteration-50/review-repro2-20261117T032546Z.json) `rel_set_*`, `rel_read`). `MATCH ()-[r]->() SET r.age = toInteger(r.age)` and `SET r.n = toString(r.n)` are refused with "a relationship's value can read only its own `age`; a SET of a relationship from another property or another variable is not supported", although the value reads only its own property. Passing neighbor: `SET r.n = r.n + 1` is stored; a relationship's stored `'30'` already reads back as 30 ([relationship text](../ontology/features/cypher.g5.md#query.values.relationship_text)).

Expected: either the SET is stored, or the refusal names the actual limit (a function of the property is not supported).

Observed: the relationship `SET` path accepts arithmetic over the relationship's own property only; any function call is refused with the shared message.

Consequence: a misleading error; the stored value is unchanged. Low.

Repair proposal (not implemented): name the unsupported shape in the message, or translate the function as the node `SET` does. Governing statement: [query.writes.retype](../ontology/features/cypher.g5.md#query.writes.retype).

<a id="bug-agg-001"></a>
### A leading grouped OPTIONAL MATCH with no matches returns NULL for SUM instead of zero

Severity: Low · Decision: Open

Run: Ordinary consolidated iteration13, 2026-11-15

Found by: the fresh aggregate source survey, actual local SQL caller contrasts, [prospective native neighbors](../uplift/consolidated/iteration-13/root-optional-aggregate-PAIRS.md), [four actual native caller observations](../uplift/consolidated/iteration-13/root-optional-aggregate-native.json), and [independent29-check fact audit](../uplift/consolidated/iteration-13/review-optional-aggregate-audit.json) with [authority/dedup triage](../uplift/consolidated/iteration-13/review-optional-aggregate-triage.md). This is a source-informed ordinary discovery, not private evaluation or an assessment of interrupted work.

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `optional_grouped_sum`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: actual pinned SQL-path execute_cypher on the task-owned IRIS, using only a fresh graph, one new anchor and a never-created unique label. No namespace census, unrelated data, supplied result rows, injected provider error or product patch.

Expected: [query.aggregation](../ontology/features/cypher.g5.md#query.aggregation). The newer [R308 regression](../../tests/unit/test_460_r308_guards.py#L53) explicitly says openCypher SUM over no values is0 and requires zero for an all-null group. A synthetic optional row contributes to COUNT(*) but supplies no value to SUM.

Observed: leading `OPTIONAL MATCH (n:Missing) RETURN n.kind, count(*), count(n), sum(n.x), avg(n.x), collect(n.x)` in the fresh graph returns `[null,1,0,null,null,[]]`. The sum should be0. Ordinary empty global MATCH returns `[0,0,0,null,[]]`, leading global OPTIONAL returns `[1,0,0,null,[]]`, and an anchored missing OPTIONAL returns `[1,0,0,null,[]]`. All four source forecasts agree with the actual calls; only the grouped fallback differs from the prospectively recorded zero-sum reference. The fixture and anchor readback are retained in the raw receipt.

Cause and authority: `_null_row_aggregate` supplies SQL NULL for SUM, and a leading grouped OPTIONAL materializes that value in its synthetic UNION fallback rather than passing through the ordinary SUM zero-if-null expression. The older [R298 helper unit](../../tests/unit/test_460_r298_fixes46_leftovers.py#L28) explicitly tests that NULL as built. Root preserves this source tension and follows the newer, explicit all-null-group SUM requirement; the helper test does not justify different public SUM results by query shape. F-0823 concerns a different empty CALL result with max/avg/collect, not this grouped OPTIONAL SUM root.

Consequence: an ordinary report can receive a missing metric instead of a numeric zero when it adds a grouping key to an unmatched OPTIONAL query. Low reflects this narrow read-result consequence; no data loss or wider aggregation failure is claimed.

Repair proposal (not implemented): return a numeric zero for SUM in the synthetic no-value fallback and preserve its final type, while retaining COUNT(*)1, COUNT(value)0, AVG null and COLLECT[]. Keep ordinary/global/grouped/anchored neighbors separate. The ordinary aggregate model's SQL-fold domain remains qualified; this OPTIONAL caller boundary is observed and still partial in Verus, not a new active source binding or executable-body proof. No product repair or owner decision is recorded.


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [query.aggregation](../ontology/features/cypher.g5.md#query.aggregation).

<a id="bug-str-008"></a>
### A single-edge graph can get two rows for one triple from a stale multigraph flag or an unlocked mode switch

Severity: Low · Decision: Open

Run: Uplift 2026-11-13


Found by: A-structure F6 and Q6.

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `stale_multigraph`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: none

Expected: with multigraph mode off there is one row per triple (spec 234 FR-003); switching off is refused while a triple has two rows.

Observed: `u_spo_graph_ekey` admits `ekey<>0` rows in a mode-off graph (`schema.py:44`). `GraphMode.Set(off)` counts and then kills with no lock (`GraphMode.cls:35-40`); another engine's cached "on" (`admin.py:922-926`; `translator.py:441-457`) keeps emitting the `MAX(ekey)+1` insert (`translator.py:10368-10386`); a restore can do the same ([bug-str-007](#bug-str-007)).

Consequence: deleting either of the two rows kills the shared leaf (`RowRemove` → `Remove`), leaving the other row without adjacency.

Repair proposal (not implemented): re-read the mode per statement, or have the functional index refuse an `ekey<>0` row in a mode-off graph, and lock the mode switch against writers. Governing statements: [structure.multigraph.off](../ontology/features/graph-structure.g5.md#structure.multigraph.off), [structure.multigraph.switch](../ontology/features/graph-structure.g5.md#structure.multigraph.switch).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [structure.multigraph.off](../ontology/features/graph-structure.g5.md#structure.multigraph.off), [structure.multigraph.switch](../ontology/features/graph-structure.g5.md#structure.multigraph.switch).

<a id="bug-tmp-007"></a>
### create_edge_temporal with no timestamp stores the event at time 0

Severity: Low · Decision: Open

Run: Uplift 2026-11-13


Found by: A-temporal F11; reconstruction check 2(b)13 and correction 24.

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `missing_temporal_time`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: none

Expected: a write with no timestamp is stamped with the current time.

Observed: the single-edge path sends `0` (`temporal.py:294`), the store sends `"0"` (`iris_sql_store.py:2680`), and `InsertEdge` substitutes "now" only for `""` (`TemporalIndex.cls:51`); the bulk path substitutes "now" for 0 (`:170`). The unit test `test_timestamp_none_sends_empty_string` asserts only that `"A"` is in the call (`tests/unit/test_temporal_edges.py:58-62`).

Consequence: such events land in 1970 and are missed by recent-window reads, velocity and latest-event queries.

Repair proposal (not implemented): send `""` (or the current time) for None, and make the test assert the timestamp. Governing statement: [temporal.edge](../ontology/features/temporal.g5.md#temporal.edge).


Iteration 7: corroborated with F-0502 as one known missing-time root. Actual native single omission/None/zero stores epoch0; normal bulk0 uses current seconds, prewrite fallback0 stores epoch0. Positive timestamps agree. [Clock model and provider limits](models/temporal_clock/NOTES.md), [native neighbors](../uplift/consolidated/iteration-7/timestamp-native.json). Intended current-time stamping remains violated; no repair or new bug count.


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [temporal.edge](../ontology/features/temporal.g5.md#temporal.edge).

<a id="bug-plt-017"></a>
### A cached personalized PageRank answer does not notice a node created after it

Severity: Low · Decision: Open

Run: Uplift 2026-11-13


Found by: A-platform F-A4 (sub-reader c); A-structure Q8 (whether WCC and CDLP need the same for node-only writes, not inspected).

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `ppr_edgeless_seed`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: none

Expected: a cached answer is valid only while nothing it depends on has changed; R313 added a node-set key for PageRank for this reason.

Observed: PPR's cache key has no node-set token, and creating a node does not move the graph-version token.

Consequence: `[]` cached for a seed that did not exist yet is served after `create_node(seed)` until the next adjacency write.

Same creation trigger/effect as the retained playbook record F-1004, which carries an inherited live observation and refutes its node-deletion premise. This is one creation defect, not two discoveries. The new global PageRank contract does not cover PPR.

Repair proposal (not implemented): key PPR on the node-set token as PageRank is. Governing statements: [algorithms.cache.token](../ontology/features/algorithms.g5.md#algorithms.cache.token), [algorithms.cache](../ontology/features/algorithms.g5.md#algorithms.cache).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [algorithms.cache](../ontology/features/algorithms.g5.md#algorithms.cache), [algorithms.cache.token](../ontology/features/algorithms.g5.md#algorithms.cache.token).

<a id="bug-adp-001"></a>
### A batch fallback in the embedded cursor reruns the rows that already ran

Severity: Low · Decision: Open

Run: Consolidated uplift 2026-11-14

**Suspected:** the control flow is observed on the real cursor with a scripted `iris.sql`; whether IRIS raises an unsupported-path error at a row after a successful prepare is not shown. Severity is lowered one level from Medium.

Found by: [witness_ddtab_mid_batch_reruns_rows](results/embedded_no_data/20261115T042913Z-prove/receipt.json) in [embedded_no_data.rs](models/embedded_no_data/embedded_no_data.rs), with control `repair-fallback-resumes` (EXPECTED_FAIL); reading `embedded.py:387-413` while lifting public case M17.

Reproduced by: **partial reproduced** — [executable component cases](audits/register-20261115/components.py) and [results](audits/register-20261115/components.json). Remaining gate: IRIS must raise the unsupported-path error after a successful batch prefix; scripted iris.sql does not establish this native trigger

Historical reproduction record: none natively; unit level on the pin's real `EmbeddedCursor.executemany` ([binding receipt](results/embedded_no_data/20261115T042852Z-binding/receipt.json), `observed_rerun`: rows `[0, 0, 1]` completed, row count 2).

Expected: a batch runs each row once (`executemany` reports "the rows run"; `OPS-B4.6.90`).

Observed: the first pass runs rows in order; an unsupported-path error at row k sends the whole batch to the fallback, which starts again at row 0 (`embedded.py:399-410`), so rows 0..k-1 run twice and the row count reports only the second pass.

Consequence: an INSERT batch can write rows twice or fail on a key it wrote itself; an UPDATE batch reapplies changes.

Repair proposal (not implemented): resume the fallback at the row that failed (the model's `fallback_start(failed_at)`), or run the whole batch through one path chosen at prepare time. Governing statement: [adapters.embedded.no_data](../ontology/concepts/adapters.g5.md#adapters.embedded.no_data).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). IRIS must raise the unsupported-path error after a successful batch prefix; scripted iris.sql does not establish this native trigger

Canonical owner and evidence: [adapters.embedded.no_data](../ontology/concepts/adapters.g5.md#adapters.embedded.no_data).

<a id="bug-str-101"></a>
### Flat node property aliases lose one stored value when id and p_id coexist

Severity: Low · Decision: Open

Run: Uplift improvement iteration 1, 2026-11-15


Found by: tracing the sampled bare-node reader into its property assignments, `nodes_edges.py:670-676`; [node_read](models/node_read/NOTES.md) `witness_alias_collision`.

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `node_alias_collision`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: none on live IRIS; [node_read binding](models/node_read/binding.py) calls the actual `create_node` with `id=stored-id` and `p_id=user-value`, captures both bound properties and feeds both permitted row orders into actual `get_nodes`.

Expected: structural ID/labels stay intact, and every accepted property can be recovered without an unspecified row order choosing which value survives (`get_node` docstring, `nodes_edges.py:563-568`).

Observed: the node's structural `id` remains `n`; property `id` maps to `p_id`, colliding with the caller's own `p_id`. Forward order yields `user-value`; reverse order yields `stored-id`. The same issue applies to `labels`/`p_labels`.

Comparison with inherited findings: F-0206/RC-01 lose values by mixing graphs; F-0813/RC-17 concern value types. Neither has this single-graph key-remapping trigger or loss. No matching alias finding was found in the three registers; this is a builder-discovered candidate, not a held-out result.

Recommendation (not implemented): preserve properties in a separate map, or reserve and validate a documented alias namespace. Owner/default/alternative: [structure.node.read.aliases](open_questions.md#q-iter-001), [q-iter-001](open_questions.md#q-iter-001). No human has chosen the API migration.


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [structure.node.read](../ontology/features/graph-structure.g5.md#structure.node.read), [structure.node.read.aliases](open_questions.md#q-iter-001).

<a id="bug-cyp-101"></a>
### Relationship property text with a trailing line break or non-ASCII digits is read back as a number

Severity: Low · Decision: Open

Run: Consolidated uplift 2026-11-14


Found by: [witness_as_built_trailing_newline_promoted, witness_as_built_unicode_digit_promoted](results/rel_prop_text/20261115T043200Z-prove/receipt.json) in [rel_prop_text.rs](models/rel_prop_text/rel_prop_text.rs); reading `prop_values.py:90-91` while lifting public case M18.

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `relationship_text`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: none natively; unit level on the pin's real `parse_rel_prop_text` ([binding receipt](results/rel_prop_text/20261115T043204Z-binding/receipt.json): 38 departures from the canonical rule, every one with a line break or U+0662).

Expected: canonical integer or decimal text becomes a number; numeric-looking text that is not canonical stays text (the decoder's docstring, `prop_values.py:154-158`; public case M18).

Observed: `parse_rel_prop_text("12\n")` is `12` and `parse_rel_prop_text("1\u0662")` is `12`: Python's `\d` matches any Unicode decimal digit and `$` matches before a final line break (`prop_values.py:90-91`, `:164-167`).

Consequence: a relationship property stored as such a string comes back from `RETURN r.p` as an integer or float, with the line break dropped.

Repair proposal (not implemented): compile both patterns with `re.ASCII` and end them with `\Z`; the controls `as-built-ascii-digits` and `as-built-without-final-newline-match` show each change removes one half. Governing statement: [query.values.relationship_text](../ontology/features/cypher.g5.md#query.values.relationship_text).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [query.values.relationship_text](../ontology/features/cypher.g5.md#query.values.relationship_text).

<a id="F-0508"></a>
### find_burst_nodes accepts a predicate and ignores it

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [05.json](../../experiment/playbook-completion/findings/audit/05.json) (live `breadth-a-live-05-temporal`)

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `burst_predicate`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-05-temporal`

- Expected: Args docstring: 'predicate: Filter to edges with this predicate' (temporal.py find_burst_nodes).
- Observed at the pin: hub reported as a burst of predicate B with only A edges
- Source severity S3, confidence high; module 05; governing page here: `temporal.`.
- Remedy proposed by the playbook arm (not implemented): Remove the argument or count per predicate; make the docstring agree (its first paragraph now says it filters nothing).
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [temporal.stats](../ontology/features/temporal.g5.md#temporal.stats).

<a id="F-0509"></a>
### InternLabelSet's canonical form is not valid JSON for some inputs

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [05.json](../../experiment/playbook-completion/findings/audit/05.json) (live `breadth-a-live-05-temporal`)

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `label_set_json`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-05-temporal`

- Expected: Spec 204 FR-012: the canonical form is JSON.
- Observed at the pin: resolved text is not JSON
- Source severity S3, confidence high; module 05; governing page here: `temporal.`.
- Remedy proposed by the playbook arm (not implemented): Build the form with JSON escaping; catch the parse error.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [temporal.edge](../ontology/features/temporal.g5.md#temporal.edge).

<a id="F-0808"></a>
### FOREACH over a parameter list does not run per item

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0808`; inspected `iris_vector_graph/cypher/translator.py:3949-3967`; inspected `iris_vector_graph/cypher/translator.py:7262-7307`; live `b-08-live-f0808-rerun`)

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `foreach_parameter`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0808`, `b-08-live-f0808-rerun`

- Expected: openCypher runs the FOREACH body once per element.
- Observed at the pin: Live: `FOREACH (x IN $list | CREATE (:B08F {v: x}))` with list [1,2,3] raised SyntaxError 'Undefined variable: x' and wrote nothing; the literal-list form created 3 nodes.
- Source severity S3, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Bind a parameter source before translation (as UNWIND does), or refuse it with a documented error; live test.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [query.conformance](../ontology/features/cypher.g5.md#query.conformance).

<a id="F-0817"></a>
### An unknown db, dbms or apoc procedure answers no rows

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0817`; inspected `iris_vector_graph/engine.py:1716-1720`; live `b-08-live-f0817-rerun`)

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `unknown_procedure`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0817`, `b-08-live-f0817-rerun`

- Expected: CYP-X10.2: an unknown procedure name is refused, with the list of known names.
- Observed at the pin: Live: CALL db.b08nothing(), apoc.b08nothing(), dbms.b08nothing() each answered column 'value' with no rows and no error; ivg.b08nothing raised ValueError listing known names; gds.b08nothing.stream answered an 'error' column result.
- Source severity S3, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Raise for every unknown name (ProcedureNotFound) with a unit test.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [query.system-procedures.unknown](open_questions.md#q-cyp-005).

Intent qualification: empty success is reproduced. Whether an unknown procedure must be refused remains the canonical open policy question; this is not an owner-ratified semantic rule.

<a id="F-0822"></a>
### CREATE or MERGE after UNWIND $p AS e WITH e fails

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0822`; inspected `iris_vector_graph/cypher/translator.py:7044-7087`; live `b-08-live-f0822-rerun`)

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `unwind_with`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0822`, `b-08-live-f0822-rerun`

- Expected: openCypher: one node per element (KNOWN_ISSUES.md:585-596).
- Observed at the pin: Live: `UNWIND $p AS e WITH e CREATE (:B08U {id: e.id})` raised GraphWriteError '<PARAMETER ERROR> Invalid number of parameters' (neither the -119 KNOWN_ISSUES/CHANGELOG name nor the -23 the unit test names); UNWIND without WITH created 2 nodes.
- Source severity S3, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): A fix with a live test, and one error in docs and tests.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [query.writes](../ontology/features/cypher.g5.md#query.writes).

<a id="F-0824"></a>
### Two slashes inside an AQL string start a comment

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0824`; inspected `iris_vector_graph/cypher/aql/lexer.py:46-63`; live `b-08-live-f0824-rerun`)

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `aql_string_comment`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0824`, `b-08-live-f0824-rerun`

- Expected: A string literal holding // is a string.
- Observed at the pin: translate_aql (the pin's code, run in the live session) on FILTER v.url == 'http://x' raised AQLParseError 'Expected RETURN'; 'x' translated fine. It also cut a back-quoted collection name containing // (F-0814 probing).
- Source severity S3, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Strip comments in the tokenizer outside strings; unit test.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [query.aql](../ontology/features/cypher.g5.md#query.aql).

<a id="F-1804"></a>
### Native index values come back as text

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [18.json](../../experiment/playbook-completion/findings/audit/18.json) (live `c18-live-value-types`; live `c18-live-save-footprint`; inspected `iris_vector_graph/_engine/snapshot.py:1644-1646, 1679`; live `rx-dec-live-18`)

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `snapshot_temporal_types`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `c18-live-value-types`, `c18-live-save-footprint`, `rx-dec-live-18`

- Expected: spec 255 (a value comes back with the type it was written with); SNP-B2.21.
- Observed at the pin: Live (c18-live-value-types and c18-live-save-footprint): the archive line for the attribute is [{'k': ['edgeprop', 'c18g', '1700000000', 'c18:a', 'T', 'c18:b', 'amount'], 'v': '20'}]; get_edge_attrs before {'amount': 20} (int), after merge restore {'amount': '20'} (str).
- Source severity S3, confidence high; module 18; governing page here: `install.snapshot`.
- Remedy proposed by the playbook arm (not implemented): Archive the value's type (as the vector form does) or move values on the server.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

Iteration 6 strengthening, not a new discovery: actual fresh temporal writer -> snapshot -> one-call/paged window preserves weights but changes integer attrs n=1 to string n='1'. The initial DISAGREES receipt170720 and intended type-preservation oracle remain. temporal_restore now models Number -> NumericText scalar export separately from weight coercion and attribute type, with a distinguishing Verus theorem. A method-copy proposal merely removing str(value) failed on actual Decimal JSON serialization and is retired as insufficient; no repair implemented. Owner install.snapshot.temporal.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [install.snapshot.temporal](../ontology/concepts/install.g5.md#install.snapshot.temporal).

<a id="F-C0841"></a>
### Cypher range() with a step of 0 known only at run time answers [] instead of raising NumberOutOfRange

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (live `st-live-susp-range-step`; inspected `iris_src/src/Graph/KG/CypherFn.cls:255-257`; inspected `iris_vector_graph/cypher/translator.py:29055-29122`)

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `runtime_range_zero`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases. Reproduced again in iteration 47 on the run-isolated continuation fixture ([observation](../uplift/consolidated/iteration-47/cypherfn-observed-20261117T015433Z.json) `L4_range_zero_rows`; [binding](results/cypher_fns/20261117T015955Z-binding/receipt.json) `range_row_1_3_0`, `sql_ivgrange_1_3_0`), now with a formal claim: [cypher_fns](models/cypher_fns/NOTES.md) `theorem_runtime_zero_step_empty`, neighbor `theorem_nonzero_step_follows_rule`, controls `range-zero-raises`, `range-ignores-direction`.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `st-live-susp-range-step`

- Expected: openCypher: range() with a step of 0 raises ArgumentError NumberOutOfRange at run time (vendor/opencypher/tck/features/expressions/list/List11.feature:115-130); the translator itself refuses a literal step of 0 with that error (iris_vector_graph/cypher/translator.py:29055-29099).
- Observed at the pin: Live AUDITD (st-live-susp-range-step): RETURN range(1, 3, 0) raises ValueError 'range() step cannot be zero (NumberOutOfRange)'; UNWIND [0] AS s RETURN range(1, 3, s) and WITH 0 AS s RETURN range(1, 3, s) answer [] with no error (a run-time step of 1 answers [1, 2, 3]). The run-time path goes to CypherFn IVGRANGE, which returns "[]" for a step of 0 (iris_src/src/Graph/KG/CypherFn.cls:255-257).
- Source severity S4, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Raise from IVGRANGE for a step of 0 (an SQL error the engine maps to NumberOutOfRange), as the literal path does.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [query.conformance](../ontology/features/cypher.g5.md#query.conformance).

<a id="F-C0849"></a>
### A relationship property bound by a WITH before a literal-endpoint CREATE is stored as text that is not JSON

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (live `st-live-cypher-relprop`; inspected `iris_vector_graph/cypher/translator.py:10410-10432`)

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `relationship_with`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `st-live-cypher-relprop`

- Expected: rdf_edges.qualifiers holds a JSON object (iris_vector_graph/schema.py:40, %Library.DynamicObject; translator.py:466-469); docs/KNOWN_ISSUES.md:94-95 says a WITH's column is stored.
- Observed at the pin: Live AUDITD (st-live-cypher-relprop): WITH $v AS v CREATE (a:L {id: 'a5'})-[:R {q: v}]->(b:L {id: 'b5'}) with v = 'val' answers no error and stores the qualifiers text {"q": val} (unquoted), which json.loads rejects; MATCH ...-[r]->... RETURN r.q answers null.
- Source severity S3, confidence medium; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Quote stage-bound string values when the qualifiers JSON is assembled (json-encode the column, not splice it raw), or bind the whole object as one parameter.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [query.writes](../ontology/features/cypher.g5.md#query.writes).

Fresh audit qualification: the real stored qualifiers are invalid JSON; on this audit build RETURN r.q raises a CY_REL_PROP SQL error. The earlier null result is historical and is not claimed universal.

<a id="F-C1018"></a>
### The store's membership decoder refuses the Owner's components and label-propagation answers when a default-graph node is named 'components', 'communities' or 'largest' (read as an accelerated summary…

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-refusals.json](../../experiment/playbook-completion/findings/audit/zz-refusals.json) (live `rx-dec-live-10`; check `rx-dec-map`; inspected `iris_vector_graph/stores/iris_sql_store.py:636`; inspected `iris_vector_graph/stores/iris_sql_store.py:662-676`; inspected `iris_vector_graph/_engine/algorithms.py:816-828`)

Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `membership_reserved_id`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `rx-dec-live-10`

- Expected: ALG-B3 (connected components group the default graph's nodes; Graph.KG.Algorithms.WCCJson answers a node->component map, iris_src/src/Graph/KG/Algorithms.cls:6-90); the decoder's own contract (iris_vector_graph/stores/iris_sql_store.py:662-676 docstring: Graph.KG.Algorithms answers with a map, which is a readable shape; only the accelerated summary is refused); the spec-230 reference in the product's code comments (e.g. iris_vector_graph/_engine/admin.py:306; there is no specs/230* at the pin) (an unreadable shape raises, a readable one is read). A node id is any string; nothing reserves thes…
- Observed at the pin: Live (rx-dec-live-10, cases 'a default-graph node named largest'): default graph rxda->rxdb->rxdc->rxda, rxdc->largest, chain rxdx1..rxdx4, rxdd alone. Graph.KG.Algorithms.WCCJson answered the valid map {'largest':'largest','rxda':'largest',...,'rxdx4':'rxdx1'}; IRISGraphStore._execute_wcc answered rows [] with error "a summary, not a node→component_id map: it carries ['largest']" (AcceleratedSummaryShape from _membership_rows, iris_sql_store.py:670-675, _SUMMARY_KEYS iris_sql_store.py:636); CDLPJson likewise ('node→community_id'). kg_WCC and kg_CDLP still answered the wire map: on a store er…
- Source severity S4, confidence high; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Tell the shapes apart by producer (the Owner path never answers a summary) or by structure (a summary's 'components' is a number and 'largest' a list; a component label is a node id string), not by the presence of a key that can be a node id.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.

Canonical owner and evidence: [algorithms.op.wcc](../ontology/features/algorithms.g5.md#algorithms.op.wcc), [algorithms.routing.fallback](../ontology/features/algorithms.g5.md#algorithms.routing.fallback).

Fresh audit qualification: public SQL GraphStore execute_wcc returns an error for the accepted node ID components. The public engine kg_WCC succeeds by falling back to the Owner. The fresh regression does not claim that the engine WCC call fails.

<a id="bug-plt-101"></a>
### WebSocket Bolt counts re-encoded bytes instead of received chunks and can lose later messages

Severity: Low · Decision: Open

Run: Consolidated iteration9, 2026-11-15 · Suspected end to end (actual Python local transports)

Found by: the [iteration8 remaining-work framing challenge](../uplift/consolidated/iteration-8/next-survey-remaining.md), followed by [36 actual full-session traces and two localized method-copy controls](../uplift/consolidated/iteration-9/bolt-session-probe.json). Source: `BoltSession._recv_message`, `bolt_server.py:439-459`. Formal source-transcription witnesses: [bolt_stream.rs](models/bolt_stream/bolt_stream.rs) `theorem_small_chunk_reencoding_leaves_terminator`, `theorem_small_chunk_empty_closes_before_queued_run`, and the coalesced passing witness; [limits](models/bolt_stream/NOTES.md).

Reproduced by: **partial reproduced** — [executable component cases](audits/register-20261115/components.py) and [results](audits/register-20261115/components.json). Remaining gate: actual WebSocket listener/socket and real database query provider; local transport and one-row engine adapter are substituted

Historical reproduction record: None natively; `bolt-session-probe.py` executes the real ordinary handshake, WebSocket session run/receive/dispatch, RUN/PULL and record encoder using local async transport objects and a one-row engine adapter, with zero socket connections. Listener and real driver reachability are not claimed.

Expected: [access.bolt.framing](../ontology/concepts/access.g5.md#access.bolt.framing), from the product's Bolt4.4 compatibility commitment and the [primary chunking specification](https://neo4j.com/docs/bolt/current/bolt/message/): a message may be split into arbitrary positive chunks through 65,535 bytes, without changing subsequent messages.

Observed: the stateless decoder accepts the valid fragmented HELLO, then `_recv_message` advances the raw buffer by the length of a default-chunk re-encoding. This omits extra received chunk headers and leaves old bytes. With later RUN/PULL delivered separately, the retained HELLO trace executes RETURN1 once but never emits a record, remains STREAMING, and fails to consume PULL/GOODBYE before the local transport is exhausted. The earlier small RESET witness instead returns empty before the later RUN. These are distinct concrete consequences of the same wrong offset; it does not always suppress RUN. Canonical default framing succeeds. Coalescing the whole exchange also succeeds because all complete bodies enter the queue before the wrong cut, but leaves residue; this passing neighbor is retained. The initial harness incorrectly expected coalesced failure and is preserved under `bolt-attempts/overbroad-packet-oracle.*` as a withdrawn expectation.

Consequence: a valid ordinary client exchange can lose its query or response depending on chunk/transport boundaries. This is separate from the known PULL suffix loss (F-1602), transaction atomicity (F-1601), and empty-NOOP run-loop root (bug-plt-102).

Repair proposal (not implemented): retain actual consumed-byte offsets from the raw decoder. A copy of the actual receive method using counted raw headers/payload boundaries fixes the fragmented/separate-frame case while the unchanged run loop still fails on NOOP. Changing only the run loop leaves the fragmented HELLO failure; both changes pass the ordinary matrix. No product file was edited.


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). actual WebSocket listener/socket and real database query provider; local transport and one-row engine adapter are substituted

Canonical owner and evidence: [access.bolt.framing](../ontology/concepts/access.g5.md#access.bolt.framing).

<a id="bug-plt-102"></a>
### WebSocket Bolt closes an ordinary session when it receives a valid keep-alive chunk

Severity: Low · Decision: Open

Run: Consolidated iteration9, 2026-11-15 · Suspected end to end (actual Python local transports)

Found by: [36 full-session local-transport traces](../uplift/consolidated/iteration-9/bolt-session-probe.json), source inspection of `BoltSession.run` (`bolt_server.py:410-412`) versus `TcpBoltSession.run` (`:946-948`), and primary protocol adjudication. [bolt_stream.rs](models/bolt_stream/bolt_stream.rs) separately proves `theorem_noop_closes_wire_without_engine` and `theorem_noop_coalesced_closes_with_queued_run` in the admitted state/wire fragment; [limits](models/bolt_stream/NOTES.md).

Reproduced by: **partial reproduced** — [executable component cases](audits/register-20261115/components.py) and [results](audits/register-20261115/components.json). Remaining gate: actual WebSocket listener/socket and real database query provider; local transport and one-row engine adapter are substituted

Historical reproduction record: None natively; actual session/codec methods run through local transport objects, with no listener, actual socket, authentication scenario or database provider. Scalar query output is a declared one-row adapter premise.

Expected: [access.bolt.framing](../ontology/concepts/access.g5.md#access.bolt.framing). The [primary Bolt message specification](https://neo4j.com/docs/bolt/current/bolt/message/) introduces empty NOOP chunks in4.1 with both clients and servers supporting them;4.3 permits them in all connection states. The actual trace negotiates the product's supported4.4.

Observed: a canonical HELLO then empty chunk followed by ordinary RUN/PULL closes before the query, because `_recv_message` returns b'' and the WebSocket run loop treats every false value as connection end. Both separate and coalesced transport frames fail. The same actual TCP session run/receive using StreamReader and a local writer continues and emits the expected scalar record; no TCP socket was opened.

Consequence: a legal keep-alive prematurely ends an otherwise usable WebSocket Bolt connection. This root remains after correcting actual chunk consumption (bug-plt-101).

Repair proposal (not implemented): distinguish end-of-connection from empty keep-alive bytes, or consume NOOP in the receive layer. A copy of the WebSocket run method using a None-only end check fixes canonical-NOOP cases, while retaining the fragmented/separate HELLO failure from the other root. Both local changes together pass all packetization neighbors. No product file was edited.


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). actual WebSocket listener/socket and real database query provider; local transport and one-row engine adapter are substituted

<a id="bug-str-014"></a>
### delete_reification deletes the reifier's rows in every graph

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; severity is lowered one level from Medium.

Found by: reconstruction check 2(a)3 (verified `schema.py:3361-3392`).

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none

Expected: a call that names a graph acts in that graph only, and the same ID in two graphs is two nodes.

Observed: `delete_reification` deletes the reifier node, labels and properties with no graph predicate and outside the Eraser (`_engine/schema.py:3361-3392`).

Consequence: removing a reification in one graph deletes another graph's node that shares the reifier's ID.

Repair proposal (not implemented): scope the delete to the reification's graph and route it through the Eraser. Governing statements: [structure.reification](../ontology/features/graph-structure.g5.md#structure.reification), [graph.membership](../ontology/concepts/graph-scope.g5.md#graph.membership).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-srch-012"></a>
### Embedding identity enforcement allows the write when the registry read fails

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Proved on the model; the trigger (a failing registry SELECT after a successful one within the 30 s route cache) cannot be induced through public calls.

Found by: [witness_identity_fail_open](results/search/20261114T000543Z-prove/receipt.json) in [search.rs](models/search/search.rs) (B-search W-O3d; control `repair-fail-closed-off`); A-search F11 and S4.

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none

Expected: a registry read failure other than "no registry" raises (4.6.0 R161, `embeddings.py:438-444`).

Observed: `get_embedding_identity` returns None for any exception (`schema.py:1054-1056`) and `enforce_embedding_identity` then permits the write (`:1383-1385`). Width is still checked from the cached route.

Consequence: a writer whose mechanism, dtype or model disagrees with the recorded identity is admitted instead of refused with an explanation.

Repair proposal (not implemented): [simp-srch-002](design_simplification.md#simp-srch-002). Governing statement: [search.embedding.check_on_write](../ontology/features/search.g5.md#search.embedding.check_on_write).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-srch-013"></a>
### TextSearchEngine.search_documents is public, ignores graphs and very likely always fails

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only.

Found by: A-search F13.

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none

Expected: every search answers one graph and reports failure as failure.

Observed: it reads unqualified `docs` and uses `%FIND(text,?)` (`text_search.py:48-66`; compare `schema.py:2499-2502`); its LIKE fallback is graph-unscoped and errors return `[]`.

Consequence: callers get empty answers, or other graphs' documents.

Repair proposal (not implemented): remove it, or delegate to the scoped text search. Governing statement: [search.scope](../ontology/features/search.g5.md#search.scope).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-plt-013"></a>
### A GraphQL GET request can run a Cypher write

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; severity is lowered one level from Medium.

Found by: A-platform F-H4 (sub-reader a, re-read by A-platform).

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none

Expected: writes are not reachable through safe HTTP methods; read-only mode and the key gate writes.

Observed: `executeCypher` is a Query field (`api/gql/schema.py:98-165`), and the `GraphQLRouter` is built without overriding `allow_queries_via_get` (`api/main.py:93`).

Consequence: with no key configured, a cross-site GET from a browser can run a `CREATE` against a reachable server.

Repair proposal (not implemented): make `executeCypher` a mutation, or disable queries via GET. Governing statement: [access.surfaces](../ontology/concepts/access.g5.md#access.surfaces).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-plt-025"></a>
### An engine whose first strict-mode check ran before the ledger classes were installed never enforces strict mode

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Proved as a model trace (control `g-class-present-recomputed`); not probed. Severity is lowered one level from Medium.

Found by: [witness_class_absent_cached_for_the_engines_lifetime](results/platform/20261114T002651Z-prove/receipt.json) in [platform.rs](models/platform/platform.rs); review R3-platform R1-11.

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none

Expected: strict mode applies to an engine whenever the ledger is strict, however long ago the engine was created (spec 213 strict-mode contract).

Observed: `LedgerGuard` caches `_class_present` for the engine's lifetime (`ledger/guard.py:45-49`); when the first probe finds no ledger class (for example an engine created before setup compiled the classes), the guard treats the ledger as never enabled from then on.

Consequence: a long-lived engine (a server process started before setup) writes unrecorded under strict mode until it is restarted.

Repair proposal (not implemented): re-probe the class when it was absent, at least whenever `Meta()` would be re-read, or enforce strict on the server ([simp-plt-001](design_simplification.md#simp-plt-001)). Governing statement: [access.ledger_strict.engine_cache](../ontology/concepts/access.g5.md#access.ledger_strict.engine_cache).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-cyp-005"></a>
### An all-graphs read skips graph correlation when only the nodes table looks single-graph

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Data-dependent; source reading only. Severity is lowered one level from Medium.

Found by: A-cypher F6.

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none

Expected: an all-graphs read pairs each node only with its own graph's rows.

Observed: `_all_graphs_correlated` asks `_more_than_one_graph`, which reads only `nodes` (`engine.py:612-639`; `translator.py:782-794`); `rdf_props` has no foreign key to `nodes` (`schema.py:411-418`), and 4.7.0 states that property rows left by SQL-removed nodes exist (CHANGELOG l. 54-58).

Consequence: with nodes in one graph and leftover property rows of the same ID in another, the SQL path reads the other graph's value; the native path does not, so shadow mode raises or the answers differ.

Repair proposal (not implemented): probe `rdf_props` too, or correlate whenever any graph-owned table holds two graphs. Governing statement: [query.graph-scope.read](../ontology/features/cypher.g5.md#query.graph-scope.read).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-cyp-006"></a>
### USE GRAPH accepts graph names the graph keys refuse

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; severity is lowered one level from Medium.

Found by: A-cypher F8.

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none

Expected: the reserved name `"0"` and control characters are refused before anything is written (ADR-0003).

Observed: `parser.py:174-192` accepts any string; refusal happens only where `ForIndex` runs, so a label-less `USE GRAPH '0' CREATE ({id:'a'})` writes a `nodes` row in graph `'0'` that `^KG` cannot represent, and native reads throw and fall back to SQL.

Consequence: rows in an unrepresentable graph, which every later functional-index callback for that graph rejects.

Repair proposal (not implemented): call `validate_graph_name` on the graph context at parse or translate. Governing statement: [query.graph-scope.names](../ontology/features/cypher.g5.md#query.graph-scope.names).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-cyp-007"></a>
### A run that started before a property-layout change can recompile a shape's class for the old layout under newer runs

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Proved on the model; needs a layout recompile inside one run's window, not probed.

Found by: [witness_straggler_recompiles_for_an_old_layout](results/platform/20261114T002651Z-prove/receipt.json) in [platform.rs](models/platform/platform.rs) (B-platform P2, W-O2c).

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none

Expected: a stale entry is never run (ADR-0014:16-23).

Observed: the check is made once per run (`Exec.cls:158`); a run whose `Props.Begin` preceded an `rdf_props` recompile reaches `For` after a newer run compiled the shape, rewrites the entry and recompiles the same class for the old layout (`Gen.cls:63-101`).

Consequence: the newer run's next walk reads old global names; only in-flight runs are affected and the entry heals on the next check.

Repair proposal (not implemented): [simp-cyp-001](design_simplification.md#simp-cyp-001). Governing statement: [query.compiled.never-stale](../ontology/features/cypher.g5.md#query.compiled.never-stale).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-cyp-008"></a>
### The compiled-plan read-back after a synchronous build skips the class-name check

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Proved on the model; needs a role with RW on the database (the R311 threat) and a race.

Found by: [witness_readback_trusts_the_entrys_class](results/platform/20261114T002651Z-prove/receipt.json) in [platform.rs](models/platform/platform.rs) (B-platform P3, W-O2d; control `p-no-class-name-check`).

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none

Expected: a planted or foreign entry never selects the class a run executes (4.6.0 R311; ADR-0014).

Observed: `Gen.For` lines 102-103 return the entry's class if its status is ok, without line 73's `IVGC.P<h>` name check.

Consequence: an entry planted in the window after a sync build points the run at another shape's class.

Repair proposal (not implemented): apply line 73's checks at line 103. Governing statement: [query.compiled.integrity](../ontology/features/cypher.g5.md#query.compiled.integrity).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-led-004"></a>
### Re-enabling the ledger during an unfinished redaction skips the adoption without telling the caller

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; severity is lowered one level from Medium.

Found by: A-history F14; review R1-core CV-6 and R1-6.

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none

Expected: enabling adopts the current state, so that writes made while the ledger was disabled are recorded and verify is equal.

Observed: `enable()` runs `verify(adopt=True)` (`client.py:288-296`), which answers `redaction_in_progress` while the marker exists and adopts nothing (`replay.py:812-823`); `enable()` neither raises nor reports it.

Consequence: the ledger is enabled with unrecorded writes; a later verify diverges with no hint that the adoption was skipped.

Repair proposal (not implemented): refuse `enable` while a redaction is unfinished, or report the skipped adoption. Related question: [q-led-003](open_questions.md#q-led-003). Governing statement: [ledger.lifecycle](../ontology/features/ledger.g5.md#ledger.lifecycle).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-led-005"></a>
### A reifier's delete record written inside a tenant's revision is reached by neither redaction target

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; nothing tests it. Severity is lowered one level from Medium.

Found by: review R1-core CV-4 and R1-11.

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none

Expected: every record of the target becomes a tombstone (ADR-0013; spec 256 FR-001).

Observed: `DeleteRelInternal` writes a `delete_node` record (graph `""`, the reifier's own ID, prior = its label and property snapshot) for each reifier of a deleted edge; `Matches` reaches it only through a prefix the reifier ID carries, so neither `redact(tenantGraph)` nor `redact(None, prefix=tenant)` tombstones it unless the reifier ID has the tenant prefix.

Consequence: the reifier's labels and properties from the tenant's own revision stay in clear after a complete redaction.

Repair proposal (not implemented): attribute a cascade record to the relationship that caused it (for example by recording the edge's endpoints in it, as [simp-002](design_simplification.md#simp-002) proposes for qualifier records), or name reifier IDs with the tenant prefix. Governing statement: [redaction.target.nodes](../ontology/features/redaction.g5.md#redaction.target.nodes).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-led-006"></a>
### A redaction that finds nothing to tombstone sets no marker, so a target record committed meanwhile survives a complete run

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Shown by a reviewer's scratch model witness; not probed. One `create_temporal_edge` of a temporal-only predicate into the target suffices, because it writes no row that the final step's liveness check reads (review round2-core); otherwise the trace needs a create and a delete of target content inside the run's window.

Found by: review R1-core CV-2 and R1-9 (scratch witness `rv_witness_unstarted_run_completes_with_target_record`, `$RUN_DIR/agents/R1-core/adv_valid/verus.log`); `theorem_completion` holds only for started runs ([receipt](results/ledger_redaction/20261114T044401Z-prove/receipt.json)).

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none

Expected: while a redaction runs, nothing may be written into its target, and a complete run leaves no target record (spec 256 Decision 3; ADR-0013).

Observed: `BatchInLock` writes the marker only at the first match (`LedgerRedact.cls:322-324`), and `FinalInLock` returns without a revision when there is no marker and no statement; `BlocksCommit` refuses only while a marker exists.

Consequence: a target commit that lands after the scan has passed its position is admitted and survives a run that reports `complete`.

Repair proposal (not implemented): claim the marker at the start of the first batch ([simp-001](design_simplification.md#simp-001)). Governing statement: [redaction.batches.commits](../ontology/features/redaction.g5.md#redaction.batches.commits).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-led-008"></a>
### Under strict mode the only API delete is a ledger changeset, which leaves documents, temporal, FHIR and search-index content that redaction and verify cannot see

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; not probed. Severity is lowered one level from Medium.

Found by: review round2-core R2-3 (expectation E10).

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none

Expected: an erase removes content from every store that holds it, and a path that removes content from one store but not the others is a defect (ADR-0004:71-82); a redaction is refused while the target's content is live.

Observed: under strict mode `erase_graph`, `erase_all` and `delete_nodes_by_prefix` raise `LedgerStrictModeError` ([platform_strict_paths](receipts/native/platform_strict_paths.json)), so the only API deletion is a ledger `delete_node`/`delete_relationship`. `LedgerApply.DeleteNodeRows` (`LedgerApply.cls:353-372`) deletes `kg_NodeEmbeddings(_optimized)`, `rdf_labels`, `rdf_props` and `nodes` only; it leaves `Graph_KG.docs` (no foreign key, `schema.py:471-479`), the temporal index, the FHIR side tables, routed node vectors and the named search indexes (a routed table's foreign key may instead refuse the whole changeset). `LiveRows` and verify read none of these stores.

Consequence: "delete through the ledger, then redact" completes with `verify()` equal while the tenant's text, vectors and events remain.

Repair proposal (not implemented): route the ledger's node delete through the Eraser's node erase ([simp-str-001](design_simplification.md#simp-str-001)'s single path), or let erasure run under strict mode as a recorded operation; see [q-003](open_questions.md#q-003). Open part: [redaction.strict-mode](open_questions.md#q-003). Governing statements: [erasure.entry-points.single-path](../ontology/features/erasure.g5.md#erasure.entry-points.single-path), [redaction.after-erasure](../ontology/features/redaction.g5.md#redaction.after-erasure).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-led-009"></a>
### Post-commit properties bypass strict mode and the block on commits into a target being redacted

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; the strict-mode and mid-redaction cases were not run.

Found by: review round2-core R2-4 (expectation E11).

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none — [ledger_post_commit_verify](receipts/native/ledger_post_commit_verify.json) shows only that post-commit properties are written outside the revision (verify diverges).

Expected: strict mode refuses writes made outside the ledger; while a redaction runs, a commit with a record in its target is refused (spec 256 Decision 3).

Observed: `ledger.commit` writes `post_commit_properties` by direct SQL after the revision (`client.py:430-487`); the strict guard is not consulted for them and `BlocksCommit` checks only the changeset's records.

Consequence: a commit whose post-commit properties name `tenant|…` makes a default-graph prefix target live in the middle of a run (the final step then refuses and the marker stays; for a prefix target an erase by prefix cannot clear such a property row, because the prefix erase selects IDs from node rows ([bug-led-010](#bug-led-010)), so only an explicit-id erase or raw SQL clears it, and until then the namespace-wide marker blocks readers, verify and every other target), and after a completed redaction it re-creates erased IDs as property rows.

Repair proposal (not implemented): check post-commit properties against strict mode and the redaction marker before writing them, or record them in the revision. Related: [q-010](open_questions.md#q-010), [bug-led-003](#bug-led-003). Governing statements: [ledger.unrecorded](../ontology/features/ledger.g5.md#ledger.unrecorded), [redaction.batches.commits](../ontology/features/redaction.g5.md#redaction.batches.commits).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-led-010"></a>
### A property row with no node row survives the prefix erase, and every later prefix redaction of its tenant is refused

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Found by: review round 3 R3-4 (scratch model L-d); integrated as witness W6 [witness_orphan_prop_row_blocks_prefix_redaction](results/ledger_redaction/20261114T044401Z-prove/receipt.json) in [redaction.rs](models/ledger_redaction/redaction.rs) (a `PropRow` goes with a prefix erase only when its node row exists in the same graph), with control [prefix-erase-takes-orphan-props](results/ledger_redaction/20261114T044600Z-control-prefix-erase-takes-orphan-props/receipt.json) (EXPECTED_FAIL).

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: [redaction_orphan_prop_blocks](receipts/native/redaction_orphan_prop_blocks.json) — a commit with `post_commit_properties = {"tP|x": {...}}` (the node `tP|x` is never created) leaves 1 property row and 0 node rows; after `delete_nodes_by_prefix("tP|")` the row is still there and `redact(None, prefix="tP")` is refused `RedactionTargetLiveError`; a second prefix erase changes nothing and the redaction is refused again; `delete_node("tP|x", graph="")` removes the row and the redaction then completes.

Expected: an erase removes the tenant's content from every store that holds it (ADR-0004; CONTEXT.md "Erasure"), and the documented tenant recipe — erase by prefix, then redact by prefix (ADR-0013; USER_GUIDE) — completes.

Observed: `Graph_KG.rdf_props` has no foreign key to `Graph_KG.nodes` (`schema.py:411-418`), and `ledger.commit` inserts post-commit property rows for any ID (`client.py:466-473`); `Eraser.EraseNodes` collects the IDs to erase from `Graph_KG.nodes` rows only (`Eraser.cls:331-349`), while `LedgerRedact.LiveRows` counts `rdf_props` rows by prefix.

Consequence: a loud refusal, not silent retention: the tenant cannot be redacted through the documented recipe until an administrator finds the orphan IDs and erases them by ID. If the orphan row is written while a redaction runs ([bug-led-009](#bug-led-009)), the run's final step refuses and its marker blocks the namespace's readers, verify and other targets until then. Severity Low because the refusal is visible and an explicit-id erase repairs it.

Repair proposal (not implemented): let the prefix erase also select property (and label) rows by ID prefix, or refuse `post_commit_properties` for IDs with no node row; the first keeps the recipe working for data written before the change. Related: [bug-led-007](#bug-led-007) (the same node-row selection misses temporal-only events), [simp-003](design_simplification.md#simp-003). Governing statements: [erasure.prefix-match](../ontology/features/erasure.g5.md#erasure.prefix-match), [redaction.after-erasure](../ontology/features/redaction.g5.md#redaction.after-erasure).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-srch-017"></a>
### A BM25 index built before 4.0.0 reports the default graph, so the default graph's fusion reads another graph's documents as its own

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Code reading only (review round 3 R3-reader M25); not run natively (no pre-4.0.0 index on this arm).

Found by: review round 3 R3-reader M25.

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none

Expected: a BM25 index records which graph it covers, and fusion reads the graph's own index ([search.scope.indexes](../ontology/features/search.g5.md#search.scope.indexes); spec 230 graph scope).

Observed: an index left over from a pre-230 build has no graph subscript and covered every graph; `BM25Index.Info` reports graph `""` for it, the same value the default graph reports (`BM25Index.cls:603-611`, whose comment says to rebuild such an index). `_pick_fusion_index` prefers an index recorded for `graph_id` (`_engine/vector.py:164-206`), so the default graph's fusion picks it without a warning.

Consequence: default-graph fusion can return node IDs from other graphs until the index is rebuilt.

Repair proposal (not implemented): mark pre-230 indexes as unscoped during upgrade (or refuse them in fusion with a message to rebuild).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-0209"></a>
### An all-graphs walk can miss graphs

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [02.json](../../experiment/playbook-completion/findings/audit/02.json) (inspected `iris_vector_graph/_engine/query.py:2408-2420`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none (confirmed-source)

- Expected: An all-graphs read is the union over every graph (CONTEXT.md:38-43).
- Observed at the pin: _edge_graphs stops after 10,000 graphs and answers [] on any error (iris_vector_graph/_engine/query.py:2408-2420).
- Source severity S4, confidence high; module 02; governing page here: `graph. / structure.`.
- Remedy proposed by the playbook arm (not implemented): List without a cap and raise on failure.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-0609"></a>
### The fused search may read an IVF index built for another graph

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Medium.

Found by: playbook arm, [06.json](../../experiment/playbook-completion/findings/audit/06.json) (inspected `iris_vector_graph/_engine/vector.py:194-225`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none (confirmed-source)

- Expected: FR-013 (a scoped lookup never widens); search_nodes_by_vector refuses the same case (vector.py:783-790).
- Observed at the pin: _fusion_leg_index falls back to an index whose graph is unknown, with a WARNING (iris_vector_graph/_engine/vector.py:208-225).
- Source severity S2, confidence high; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Refuse the IVF leg for an index of unknown or other graph; persist the graph with the index.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-0908"></a>
### The privilege check spec 253 puts in the executor is in the engine only

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-versions.json](../../experiment/playbook-completion/findings/audit/zz-versions.json) (live `ver-priv-r3`; live `ver-priv-r2`; live `ver-priv-create`; inspected `iris_src/src/Graph/KG/Cypher/Exec.cls:32-72`; inspected `iris_src/src/Graph/KG/Cypher/Exec.cls:832-904`; inspected `iris_vector_graph/engine.py:559-586`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `ver-priv-r3`, `ver-priv-r2`, `ver-priv-create`

- Expected: specs/253-native-cypher-executor/spec.md:124-127 (FR-011: the executor MUST check SELECT on the graph tables, cached per process and user); decisions.md HD-0901 working answer: authorization at use.
- Observed at the pin: Live (ver-priv-r3; ver-priv-r2): a disposable user IVGAUDIT_RO holding ADMIN_GUIDE section 3's reading row in AUDITB (%DB_%DEFAULT:R, %Native_ClassExecution:U, %Native_GlobalAccess:U; SELECT and EXECUTE ON SCHEMA Graph_KG) had SELECT revoked (grantor-aware, CheckPrivilege 0 for user and role). Graph.KG.Cypher.Exec.Run called directly over the Native API by that user, now with no SELECT on any Graph_KG table, answered the plans for MATCH (a:P)-[:KNOWS]->(b) (3 rows) and MATCH (a:P {node_id:'a'})-[:KNOWS]->(b) ([b]); only a plan whose anchor the executor resolves through dynamic SQL (an unlabel…
- Source severity S3, confidence high; module 09; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Amend FR-011 to the shipped design (engine-side check, database resource as the boundary), or add the check to Run.
- Reviewed-design control: `playbook-proofs-d1d` `control_f0908_run_unchecked` fails where expected in this run ([receipt](results/playbook-proofs-d1d/20261115T035706Z-control_f0908_run_unchecked/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Recorded in 09.json, zz-versions.json; the later file's record is used.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-1009"></a>
### khop answers a start node that exists only in a named graph

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [10.json](../../experiment/playbook-completion/findings/audit/10.json) (live `b-10-live-scope`; mc `m10-walk-as-built-khop`; mc `m10-walk-reviewed`; inspected `iris_vector_graph/_engine/algorithms.py:600-626`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-10-live-scope`

- Expected: The khop docstring: a missing seed answers two empty lists (_engine/algorithms.py:577-594); ALG-I3.
- Observed at the pin: Live (b-10-live-scope): khop('b10_z') for b10_z held only by named graph b10g1 answered {'nodes': ['b10_z'], 'edges': []}; khop of an id in no graph answered {'nodes': [], 'edges': []}. Model m10-walk-as-built-khop reproduces it.
- Source severity S3, confidence high; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Add graph_id = '' to _khop_seed_exists.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-1013"></a>
### Graph.KG.PageRankEmbedded is deployed and reads every graph

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [10.json](../../experiment/playbook-completion/findings/audit/10.json) (live `b-10-live-scope`; inspected `iris_src/src/Graph/KG/PageRankEmbedded.cls:5-30`; inspected `docs/ADMIN_GUIDE.md:346`; inspected `scripts/deploy_objectscript.py:129`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `b-10-live-scope`

- Expected: ALG-I2/ALG-I3 and the IVG schema boundary (spec 262: the IVG tables live in the IVG schema, Graph_KG here).
- Observed at the pin: Live (b-10-live-scope): the deployed class method Graph.KG.PageRankEmbedded.ComputePageRank('b10_%', ...) answered {"raised": "RuntimeError: <THROW> *%Exception.PythonException <PYTHON EXCEPTION> 246 <class 'irisbuiltins.SQLError'>: Table 'SQLUSER.NODES' not found"}: its unqualified table names resolve to SQLUser, outside the namespace's IVG schema, so the deployed class cannot run against the IVG tables at all here; where a SQLUser.nodes/rdf_edges exists it reads that table instead. The every-graph part is confirmed at the source only: ComputePageRankCore selects nodes and rdf_edges by node_…
- Source severity S3, confidence high; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Remove the class or scope it to one graph and the IVG schema (qualified table names).
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-C0340"></a>
### networkx-loader's --clear-existing deletes every graph's edges, labels and properties by raw SQL and leaves their nodes, temporal edges and vectors, with strict mode on

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (live `st-live-susp-loader-clear`; inspected `scripts/ingest/networkx_loader.py:264-283`; inspected `pyproject.toml:178`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `st-live-susp-loader-clear`

- Expected: A clear of graph data goes through the eraser, which removes a graph's rows and every derived store together (Graph.KG.Eraser, Graph.KG.GraphStores.Inventory; 12-erasure.md Scope); every content write is refused while ledger strict mode is on (11-ledger.md strict mode; WRT-T1.82 notes this loader's clear as built); one graph's operation does not touch another graph (SYS-I2).
- Observed at the pin: Live AUDITD (st-live-susp-loader-clear): NetworkXIRISLoader.import_graph(G, clear_existing=True) runs DELETE FROM Graph_KG.rdf_edges / rdf_labels / rdf_props with no graph filter (scripts/ingest/networkx_loader.py:279-283) and answers success with strict mode on. Afterwards graph sgB has no edges, labels or properties but keeps both node rows (get_node answers labels []), its temporal edge (window read 1) and the default graph's vector row remains; the default graph's earlier edges (including one the ledger committed), labels and properties are gone too, and no revision records the deletion.
- Source severity S3, confidence high; module 03; governing page here: `structure. / install.bulk_load`.
- Remedy proposed by the playbook arm (not implemented): Clear through the product's eraser (erase_graph per graph, or EraseAll for a whole-namespace reset) and refuse while strict mode is on; or remove the option.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-C1041"></a>
### The ^NKG centrality class methods called directly answer every graph merged; only the SQL functions refuse

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (live `st-live-susp-nkg-merged`; inspected `iris_src/src/Graph/KG/NKGAccel.cls:208-223`; inspected `iris_src/src/Graph/KG/NKGAccelCentrality.cls:4-10`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `st-live-susp-nkg-merged`

- Expected: An answer about a graph holds only that graph's data (SYS-I2); the product's own refusal says an algorithm over ^NKG with a named graph's edges present 'would be every graph's merged' (iris_src/src/Graph/KG/NKGAccel.cls:208-223, RefuseMergedGraphs; called by the kg_* SQL functions, iris_vector_graph/schema.py:2644-2665).
- Observed at the pin: Live AUDITD (st-live-susp-nkg-merged): with nd:1->nd:2 in the default graph and ng:1->ng:2->ng:3->ng:4 in graph sgN and ^NKG built by engine.sync(), Graph.KG.NKGAccelCentrality.ClosenessGlobal over the Native API answers all six nodes of both graphs as one graph (ng:1 1.833, ng:2 1.5, nd:1 1, ...) and BetweennessGlobal answers ng:2 and ng:3 of graph sgN; SQL Graph_KG.kg_Closeness refuses the same state; engine.closeness_centrality() answers nd:1 and nd:2 only. Inspected: EigenvectorGlobal, BetweennessGlobalParallel, BetweennessNeighborhood and ClosenessGlobalMSBFS (NKGAccelCentrality.cls:95,…
- Source severity S3, confidence high; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Call RefuseMergedGraphs inside the class methods (or key ^NKG by graph), so every entry point refuses or answers per graph.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-C1046"></a>
### The ^NKG traversal class methods called directly (k-hop neighbours, shortest path, distinct k-hop count) answer every graph merged

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (live `st-live-reads3-10`; control `st-control-reads3-selftest`; inspected `iris_src/src/Graph/KG/NKGAccelTraversal.cls:20-186`; inspected `iris_src/src/Graph/KG/NKGAccelTraversal.cls:366-553`; inspected `iris_src/src/Graph/KG/NKGAccel.cls:164-191`; inspected `iris_src/src/Graph/KG/NKGAccel.cls:213-223`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `st-live-reads3-10`

- Expected: An algorithm that takes no graph answers for the default graph alone and never mixes in a named graph's edges (ALG-I3, experiment/playbook-uplift/ontology/10-algorithms.md:45, citing docs/USER_GUIDE.md:767-775 and CONTEXT.md:97-101; SYS-I2). The product's own guard states why a reader of ^NKG cannot answer one graph: ^NKG holds every graph's edges with no graph key, and the ^NKG SQL functions refuse once a named graph has an edge so that plain SQL cannot get a mixed answer (iris_src/src/Graph/KG/NKGAccel.cls:213-223; ALG-B7, ALG-B7.2, 10-algorithms.md:129-131).
- Observed at the pin: Live, AUDITD (st-live-reads3-10, oracle self-tested by st-control-reads3-selftest): default graph a-R->b, b-R->c, a-S->c, c-R->a; the same ids with edges a-R->c, c-R->a, a-R->d, d-R->b, b-S->a written in graphs stg1 and stg2, then engine.sync() (^NKG merges them). Over the Native API, with no graph argument: Graph.KG.NKGAccelTraversal.KHopNeighbors('a', 2, 1000) and its NKGAccel wrapper, KHopJson and KHopNeighborsSorted list node d (which exists only in the named graphs) at dist 1, totalNodes 3 -> 4; ShortestPathNKG('a', 'd', 10) answers {"hops":1} instead of {"hops":-1}; CountDistinctKHop('a…
- Source severity S3, confidence high; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Give these readers the refusal the ^NKG SQL functions have (NKGAccel.RefuseMergedGraphs before reading ^NKG), or a graph argument that restricts the walk to one graph's edges; until then document that they answer every graph merged. Add a test with the same ids and edges in a named graph.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-C1202"></a>
### EraseGraph's adjacency kill can drop the adjacency of an edge committed after its row delete

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `reproduced-model`, not a native reproduction; severity is one level below the mapped Medium.

Found by: playbook arm, [12.json](../../experiment/playbook-completion/findings/audit/12.json) (run `core-m2-as-built-F1201-adjacency`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none (reproduced-model)

- Expected: Adjacency (^KG out/in) matches live edge rows (ADR-0012, ERS-B1.1).
- Observed at the pin: Model only (core M2, 6 steps), same root cause as F-1201 (no serialization with commits). In the 8 native F-1201 trials the adjacency survived (kg_out_G_defined), so this interleaving was not hit live.
- Source severity S2, confidence medium; module 12; governing page here: `erasure.`.
- Remedy proposed by the playbook arm (not implemented): As F-1201.
- Reviewed-design control: `playbook-proofs-pa3` `control_fc1202_erase_unguarded` fails where expected in this run ([receipt](results/playbook-proofs-pa3/20261115T040804Z-control_fc1202_erase_unguarded/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-pa3/20261115T041009Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-C1302"></a>
### Final trusts a scan that ended before it took the lock

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `reproduced-model`, not a native reproduction; severity is one level below the mapped Medium.

Found by: playbook arm, [13.json](../../experiment/playbook-completion/findings/audit/13.json) (run `core-m2-as-built-F1302-commit-after-check`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none (reproduced-model)

- Expected: A complete receipt means no record of the target remains unredacted.
- Observed at the pin: Model only (core M2, 20 steps; low likelihood): a record committed and then erased between the last batch and Final stays unredacted while the call reports complete.
- Source severity S2, confidence medium; module 13; governing page here: `redaction.`.
- Remedy proposed by the playbook arm (not implemented): Have Final check that the scan reached the head it holds the lock on, or rescan the tail under the lock.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-C1305"></a>
### Graph_KG.embedding_quarantine keeps a tenant's node ids and vectors through every erase and redaction, and the receipt does not say so

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [followup.json](../../experiment/playbook-completion/findings/audit/followup.json) (run `fu-r01b-quarantine-erase-plan`; inspected `iris_src/src/Graph/KG/Eraser.cls:300-302`; inspected `iris_src/src/Graph/KG/Eraser.cls:752-758`; inspected `iris_vector_graph/_engine/schema.py:205-227`; inspected `iris_vector_graph/migrations/graph_scoped_embeddings.py:955-968`; inspected `iris_src/src/Graph/KG/LedgerRedact.cls:504-508`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none (confirmed-source)

- Expected: specs/256-ledger-tenant-redaction/spec.md:42-44 and 127-128 (FR-008 reach statement); docs/adr/0013-redaction-removes-content-from-history.md:47-48 ('Together they cover everything IVG can reach'). By design the quarantine is evidence, not content: iris_src/src/Graph/KG/Eraser.cls:300-302 and 756-758 (FR-039, FR-040); iris_vector_graph/_engine/schema.py:205-227 (node_id, vector, metadata, no graph).
- Observed at the pin: \Source: neither EraseGraph, EraseNodes/EraseIdSet nor EraseAll names Graph_KG.embedding_quarantine except in comments (Eraser.cls:300, 756); LedgerRedact.cls never names it; the receipt (LedgerRedact.cls:504-508) does not mention it; engine.list_quarantine() (schema.py:1913) returns its rows with node_id. The pin's own upstream tests that pin this behaviour pass here (fu-r01b-quarantine-erase-plan: tests/unit/test_227_erase_plan.py, 3 quarantine tests). Not built live: the only writer of a quarantine row is the 4.0.0 migration from a 3.2.0 install (iris_vector_graph/migrations/graph_scoped_em…
- Source severity S3, confidence high; module 13; governing page here: `redaction.`.
- Remedy proposed by the playbook arm (not implemented): Keep the by-design behaviour but state it: the receipt's out_of_reach (and ADR-0013) should name embedding_quarantine rows, or the redaction should report the count of quarantined rows whose node_id matches the target's prefix.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-C1309"></a>
### The redaction's audit revision stores an unsalted SHA-256 of the tenant's name: a guessed tenant is confirmable from history

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [followup.json](../../experiment/playbook-completion/findings/audit/followup.json) (check `fu-r10-target-digest`; live `fu-r01a-snapshot-copies`; inspected `iris_src/src/Graph/KG/LedgerRedact.cls:56-59`; inspected `iris_src/src/Graph/KG/LedgerRedact.cls:418-441`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: playbook arm, live on its IRIS (x86_64 VM): `fu-r01a-snapshot-copies`

- Expected: specs/256-ledger-tenant-redaction/spec.md:152-154 (Decision 1: the audit holds 'no entity id, attribute, value or free text from the target'); docs/adr/0013-redaction-removes-content-from-history.md:16 ('holds counts and sha256(graph NUL match) instead of the target's name. Nothing in it comes from the target'); spec.md:66-67 (US2: 'nobody can recover the content from the digest') against ADR-0013:43, 49 (record digests unsalted, 'can be confirmed by guessing').
- Observed at the pin: Live digest (fu-r01a-snapshot-copies) and computation (fu-r10-target-digest): the redaction revision's source.target_sha256, readable through history() (which does not check the marker) and Graph_KG.ledger_revisions.source, is 5693ca28...c58d = SHA-256('' NUL 'fu1|') = Graph.KG.LedgerRedact.TargetDigest('', 'fu1|') (LedgerRedact.cls:56-59, :200, :433, :487). A 200,006-name dictionary confirmed exactly 'fu1' in 0.13 s (about 1.5 million guesses a second on one Python core). The marker and the receipt carry the same digest.
- Source severity S3, confidence high; module 13; governing page here: `redaction.`.
- Remedy proposed by the playbook arm (not implemented): Decide the intent (maintainer question): if the audit must not identify the tenant, store a keyed digest (HMAC with a namespace secret) or nothing; if confirmability is accepted, say so in ADR-0013 (as it already does for record digests) and drop 'Nothing in it comes from the target'. Reconcile spec 256 US2 with ADR-0013 Consequences.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="F-C1741"></a>
### The enterprise web gateway recipe lets any address manage the gateway and connects to IRIS as _SYSTEM with the stock password

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (inspected `docker/enterprise/webgateway-init.sh:12-31`; inspected `docker/enterprise/docker-compose-2026.yml:1-45`; inspected `docker/enterprise/merge.cpf:1-5`)

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none (confirmed-source)

- Expected: A deploy recipe does not expose an administration surface to every address with known credentials (deploy/README.md and docs/ADMIN_GUIDE.md treat credentials and network exposure as operator settings; F-1710 for the other docker recipe).
- Observed at the pin: Inspected at the pin (not deployed): docker/enterprise/webgateway-init.sh:12-31 writes CSP.ini with System_Manager=*.*.*.* (the gateway's management pages from any client address) and [LOCAL] Username=_SYSTEM, Password=]]]U1lT (the gateway's obfuscated form of 'SYS'); docker/enterprise/docker-compose-2026.yml:28-29 publishes the gateway on host port 64780 and :5-6 IRIS's superserver on 4972, both on every host interface; merge.cpf:4 keeps _SYSTEM's password from ever expiring or being forced to change. Only .iris-dev.toml refers to the recipe.
- Source severity S3, confidence high; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): Restrict System_Manager to the loopback/container network, bind published ports to 127.0.0.1, take the IRIS credentials from a secret and require a password change, and label the recipe as a local developer setup.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-tmp-101"></a>
### A temporal edge's internal mark is returned as relationship data by Cypher and written as an RDF qualifier

Severity: Low · Decision: Open

Run: Uplift 2026-11-16 (cloud continuation, iteration 15)

Found by: source-first contrast across the three edge readers, with predictions frozen before observation ([predictions](../uplift/consolidated/iteration-15/temporal-marker-PAIRS.md)); [temporal_marker](models/temporal_marker/NOTES.md) `theorem_cypher_reports_marker_key`, `theorem_rdf_marked_row_is_reified` and `theorem_rdf_report_counts`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 fixture with the unchanged pin ([observations](../uplift/consolidated/iteration-15/temporal-marker-observed-20261116T161532Z.json); [160-world binding panel](results/temporal_marker/20261116T164055Z-binding/receipt.json)). One default-graph triple `(a, KNOWS, b)` written by `create_edge_temporal(weight=1.5)` stores `{"temporal":true,"weight":1.5}`. Cypher `MATCH (a)-[r:KNOWS]->(b) RETURN properties(r), r.temporal` returns `{temporal: True, weight: 1.5}` and `True`. `export_rdf` writes the triple plus a reification envelope and qualifiers `temporal` (boolean true) and `weight`; the report is 11 triples / 4 nodes / 4 edges. Passing neighbors: the same triple from `create_edge` returns `{}` and reports 5 / 2 / 1; after adoption by `create_edge` or `bulk_create_edges` every reader matches the unmarked edge. `export_graph_ndjson` writes no line for the marked edge, as documented.

Expected: [temporal.structural.mark](../ontology/features/temporal.g5.md#temporal.structural.mark) says the mark lets counts, exports and cleanup tell an implied edge from an explicit one. ADR-0009 makes the triple visible to Cypher `MATCH` and to exports, and spec 252 planned the mark as a separate "temporal-origin column" (implemented as a qualifier, task T033). No source says the mark itself is relationship data. The intended reader representation is the child question [temporal.structural.mark.visibility](open_questions.md#temporal.structural.mark.visibility).

Cause: `AssertTemporalRow` stores the mark inside `qualifiers`. Cypher's relationship map is `CY_RETYPE_MAP(qualifiers)` with no key filter (translator `_edge_props_sql`), and RDF export's qualifier loop hides only `inferred`. The NDJSON exporter instead drops marked rows with `TEMPORAL_MARKED_ROW`.

Consequence: for the same visible triple, the edge's properties and the RDF content and report depend on which writer created it. A user query over `properties(r)` or a consumer of RDF qualifiers sees an internal flag, and RDF report `edges`/`nodes` grow by 3 and 2 per marked edge. Low because the expected representation is not settled and no stored data is lost.

Repair proposal (not implemented, not checked): keep the edge and its weight visible but omit the `temporal` key from Cypher relationship maps and RDF qualifiers (and from the RDF envelope when it is the only remaining key), preserving NDJSON's documented omission and every marker-based delete, purge and adoption rule. Writers and readers affected: `AssertTemporalRow`, `CY_RETYPE_MAP`/`_edge_props_sql`, `_build_rdflib_graph`; distinguishing case: the marked-versus-plain pair above.

<a id="bug-cyp-105"></a>
### A string predicate matches a node property stored as a number by its digits

Severity: Low · Decision: Open

Run: Uplift 2026-11-16 (cloud continuation, iteration 20)

Found by: the string-predicate neighbor of the typed comparison workflows, with the prediction frozen first ([predictions](../uplift/consolidated/iteration-20/null-semantics-PAIRS.md)); [typed_equality](models/typed_equality/NOTES.md) `theorem_node_number_matches_string_prefix`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 fixture with the unchanged pin ([probe](../uplift/consolidated/iteration-20/string-predicate-observed-20261116T171621Z.json); [52-world binding](results/typed_equality/20261116T171733Z-binding/receipt.json)). `create_node(a, properties={"p": 12})` stores the number 12; `MATCH (x) WHERE x.id = a AND x.p STARTS WITH '1' RETURN count(*)` counts it and `CONTAINS '2'` too, while `RETURN x.p` returns the integer 12. The stored double 0.95 does not start with `'0.'` (it is tested as `.95`). Passing neighbors: the string "abc" behaves as text on both kinds; `= 12` and `< 20` on the same node honor the stored type.

Expected: openCypher makes `STARTS WITH`, `ENDS WITH` and `CONTAINS` null when an operand is not a string. Since 4.7.0 the node path reads equality and ordering by the stored type ([query.values.equality](../ontology/features/cypher.g5.md#query.values.equality), [query.values.ordering](../ontology/features/cypher.g5.md#query.values.ordering)); string predicates do not. The documented known issue about numbers and strings does not mention string predicates. The as-built rule is [query.values.string_predicates](../ontology/features/cypher.g5.md#query.values.string_predicates).

Cause: `_boolean_expr_comparison_ops` emits `%EXACT(value) LIKE %EXACT(prefix || '%')` over the stored value with no stored-number test.

Consequence: a prefix or substring filter over a property that holds numbers on some nodes and strings on others also returns the numbers, and a decimal's match depends on IRIS's canonical spelling. Low: narrow trigger and no data loss.

Repair proposal (not implemented, not checked): apply the stored-number test (`_stored_number_test`) so a node number is null for string predicates, leaving strings unchanged. Distinguishing case: node `p = 12` against `STARTS WITH '1'`.

<a id="bug-cyp-107"></a>
### coalesce over a relationship property returns its stored text, and a boolean as '1'

Severity: Low · Decision: Open

Run: Uplift 2026-11-16 (cloud continuation, iteration 24)

Found by: the value-function probe at the API-writer / Cypher-reader boundary, with predictions frozen first ([predictions](../uplift/consolidated/iteration-24/patterns-params-PAIRS.md)). No formal model.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-24/value-functions-observed-20261116T173357Z.json)). `create_edge(a, "R", b, qualifiers={"p": 7})`, then `RETURN coalesce(x.p, 'z')` returns the string `'7'`; with `7.5` it returns `'7.5'`; with `true` it returns `'1'`. `RETURN x.p` returns 7, 7.5 and `True`. Passing neighbors: on nodes `coalesce` returns 7, 7.5 and `True` with their types.

Expected: openCypher's `coalesce` returns its first non-null argument unchanged. [query.values.relationship_text](../ontology/features/cypher.g5.md#query.values.relationship_text) decodes only result columns the translator marks as relationship property reads; a `coalesce` column is not marked, so the raw `JSON_VALUE` text reaches the result, and `JSON_VALUE` spells a JSON boolean as `1`.

Consequence: the common idiom `RETURN coalesce(r.weight, 0)` returns text for every stored weight, and a boolean flag returns `'1'`, which no reader can tell from the string `"1"`. Low: wrong result type, no data change.

Repair proposal (not implemented, not checked): decode a relationship property argument of `coalesce` (and similar pass-through functions) as `RETURN r.p` does, or mark such columns for `_decode_rel_prop_text_columns`. Distinguishing case: relationship `p = true` read by `RETURN coalesce(x.p, 'z')`.

<a id="bug-plt-107"></a>
### The user guide says a from_connect engine's temporal edge writes run outside the caller's transaction; create_edge_temporal joins it

Severity: Low · Decision: Open

Run: Uplift 2026-11-16 (retest, iteration 26)

Found by: the frozen W31 prediction T5, taken from the USER_GUIDE, missed ([predictions](../uplift/consolidated/iteration-26/caller-txn-PAIRS.md)); [write_routing](models/write_routing/NOTES.md) `theorem_routing`, control `temporal-on-own-connection`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 retest fixture ([observation](../uplift/consolidated/iteration-26/caller-txn-observed-20261116T213901Z.json), T5 and T10). On an engine made with `from_connect`, `START TRANSACTION` on its connection, `create_edge_temporal`, `ROLLBACK`: the window read returns nothing (the write joined). Neighbor: on the same engine and history, `purge_before` is not undone by the rollback (T10), which is what the guide describes.

Expected: the guide should say which calls run on the engine's own connection. It says: "A write that IVG sends over a Native API connection of its own (an engine made with `from_connect`: the temporal edge stores, `^KG` on a namespace without the adjacency index) runs in another IRIS process, outside your transaction."

Consequence: a reader of the guide expects a rolled-back temporal edge to stay on a `from_connect` engine and has no warning that `purge_before`, `rebuild_temporal_latest`, `set_temporal_structural` and the structural drop/backfill do. Low: misleading documentation.

Repair proposal (not implemented): name the calls that use `engine._iris_obj()` (purge, rebuild, policy, structural drop/backfill) instead of "the temporal edge stores". Governing statement: [structure.write](../ontology/features/graph-structure.g5.md#structure.write).

<a id="bug-srch-101"></a>
### Creating a VecIndex again under the same name reports a count of 0 while its vectors stay searchable

Severity: Low · Decision: Open

Run: Uplift 2026-11-16 (retest, iteration 27)

Found by: source reading after the W32 predictions were frozen, then observation ([predictions](../uplift/consolidated/iteration-27/vecindex-PAIRS.md), V10); [vec_index](models/vec_index/NOTES.md) `theorem_recreate_zero_count_keeps_vectors`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 retest fixture ([observation](../uplift/consolidated/iteration-27/vecindex-observed-20261116T215013Z.json); [binding](results/vec_index/20261116T215331Z-binding/receipt.json)). After 5 inserts, `vec_create_index` on the same name returns normally; `vec_info.count` is 0 and `vec_search` still returns all 5 vectors. Passing neighbor: a first create reports 0 and searches return nothing.

Expected: the API reference describes the call as "Create (or reset the settings of)" an index; it does not say what happens to the stored vectors, and no source promises a count that disagrees with the contents.

Consequence: a caller who re-creates an index to start over keeps old vectors in its results, and the reported count hides them. Low: misleading report; the contents are as stored.

Repair proposal (not implemented): either clear the vectors and trees on create, or keep `meta.count` equal to the stored vectors. Governing statement: [search.vecindex](../ontology/features/search.g5.md#search.vecindex).

<a id="bug-srch-102"></a>
### The API reference says a vector inserted into a VecIndex is searchable only after the next vec_build

Severity: Low · Decision: Open

Run: Uplift 2026-11-16 (retest, iteration 27)

Found by: the frozen W32 prediction V3, taken from the API reference, missed ([predictions](../uplift/consolidated/iteration-27/vecindex-PAIRS.md)); [vec_index](models/vec_index/NOTES.md) `theorem_insert_found_by_identical_query`, control `insert-not-into-trees`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 retest fixture ([observation](../uplift/consolidated/iteration-27/vecindex-observed-20261116T215013Z.json), V3). After `vec_build`, `vec_insert` of a vector equal to the query makes it the first hit at once (score 1.0).

Expected: the reference says "It is searchable through the trees only after the next `vec_build`" and "an index with no trees is searched by brute force"; `Insert` adds every vector to each existing tree, and `vec_create_index` sets four trees at once, so brute force runs only on an index created with no trees or after a drop.

Consequence: callers may run needless builds; the description of which search runs is wrong. Low: documentation drift.

Repair proposal (not implemented): say that inserts are placed in the existing trees and that `vec_build` re-places every vector with new planes.

<a id="bug-str-102"></a>
### get_property_values and get_property_pairs return a stored boolean as the string "true"

Severity: Low · Decision: Open

Run: Uplift 2026-11-16 (retest, iteration 34)

Found by: the frozen W40 prediction R3 ("typed as `get_node` types them") missed ([predictions](../uplift/consolidated/iteration-34/property-readers-PAIRS.md)).

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 retest fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-34/property-readers-observed-20261116T222559Z.json), R3, R4, R5). For a node created with `properties={"p": True}`, `get_node` and `get_node_properties` return `True`, while `get_property_values("p")` and `get_property_pairs("p")` return `"true"`. Passing neighbors: in the same calls an integer 7 and a float 7.5 come back as `int` and `float`, and a string "7" as `str`.

Expected: [structure.node.read](../ontology/features/graph-structure.g5.md#structure.node.read) reads typed properties; the API reference says `get_property_values` returns "every value stored", with no sign that booleans alone come back as text.

Consequence: a caller that gathers values with these readers sees `"true"` and cannot tell it from a stored string "true"; `get_node` disagrees. Low: wrong result type, no data change. Not checked: the cause in code, and the other value readers (`get_property_pairs_like`).

Repair proposal (not implemented): decode the stored boolean spelling in these two readers as `get_node` does. Governing statement: [structure.node.read.properties](../ontology/features/graph-structure.g5.md#structure.node.read.properties).

<a id="bug-str-103"></a>
### kg_GRAPH_WALK keeps one row per hop and node, dropping other edges that reach that node at the same hop

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 37)

Found by: source reading after the W43 predictions were frozen ([predictions](../uplift/consolidated/iteration-37/traversal-PAIRS.md), W1's one row per walked edge), then observation; [walk_reader](models/walk_reader/NOTES.md) `theorem_same_hop_target_collapses`, control `stage-keeps-every-edge`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-37/traversal-observed-20261117T002418Z.json) W5, W6; [binding](results/walk_reader/20261117T002834Z-binding/receipt.json) cases `diamond`, `two_types`). On a diamond s→a→x, s→b→x the walk returns s→a, s→b and b→x only; with s -R-> a and s -Q-> a it returns only the R row. `khop` on the same graphs lists every edge. Passing neighbors: a chain, a cross edge (s→b and a→b, where b is listed at hops 1 and 2) and a back edge to the start keep every edge (`chain`, `cross`, `back_edge`).

Expected: [algorithms.op.walks](../ontology/features/algorithms.g5.md#algorithms.op.walks) says a graph walk "returns at most `max_results` rows of (source, type, target, hop)" and the docstring that the hop is "the hop at which the target was reached". Neither says one edge per target and hop survives, and the cross-edge rows show the walk is not a one-row-per-node tree either. Which reading is intended is the question [algorithms.op.walks.rows](open_questions.md#algorithms.op.walks.rows).

Observed: `BFSFastJsonSorted` stages each walked edge as `^ArnoKG("bfs_r", tag, step, o) = (s, p, w)` (`TraversalBFS.cls:449-460`, the write at 458), so a later edge with the same hop and target overwrites an earlier one; `max_results` is applied to edges before that collapse.

Consequence: a caller asking which edges or types connect a start to its neighborhood misses parallel edges and alternative parents, and which one is kept depends on walk order; the answer can be shorter than `max_results` while edges remain. Low: a reader's result, no data change.

Repair proposal (not implemented): key the stage by (step, target, source, type), or document one row per (hop, node) and say which parent is kept. Governing statement: [algorithms.op.walks](../ontology/features/algorithms.g5.md#algorithms.op.walks).

<a id="bug-str-104"></a>
### A graph walk whose answer is longer than an IRIS string raises and leaves its staged rows in ^ArnoKG

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 37)

Found by: the frozen W43 prediction L1 missed ([predictions](../uplift/consolidated/iteration-37/traversal-PAIRS.md)); [walk_reader](models/walk_reader/NOTES.md) `theorem_walk_overflow_raises_and_leaves_stage`, control `walk-has-stream`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-37/traversal-observed-20261117T002418Z.json) L1; [binding](results/walk_reader/20261117T002834Z-binding/receipt.json) case `large`). On a star of 40,000 edges whose targets have 40-character padding, `kg_GRAPH_WALK(hub, max_depth=1, max_results=40010)` raises `<MAXSTRING>ReadBFSResults+16^Graph.KG.TraversalBFS.1`, and a new `^ArnoKG("bfs_r", <tag>)` subtree of the staged rows remains. Passing neighbor: `khop(hub, hops=1)` on the same star returns all 40,000 edges.

Expected: the 4.6/4.7 changelog says "A BFS answer past IRIS's string limit no longer fails" through `BFSFastStream` / `ReadBFSResultsStream` (scoped there to `khop()`), and `host._decode_sorted` falls back to `ReadBFSResultsStream` for exactly this tree. [algorithms.op.walks](../ontology/features/algorithms.g5.md#algorithms.op.walks) promises rows up to `max_results`.

Observed: `kg_GRAPH_WALK` calls `BFSFastJsonSorted` with `_call_classmethod` and then `_call_classmethod_large(..., "ReadBFSResults", tag)` (`algorithms.py:716-729`); `host.call_large` falls back only for methods in `STREAM_FALLBACKS` (`BFSFastJson`, `BFSFastJsonDirect`), so the overflow is raised. `ReadBFSResults` kills the stage only after building its string (`TraversalBFS.cls:493-515`, the kill at 513).

Consequence: a large walk fails visibly, and each failed call leaves its rows in a persistent global that nothing clears. Low: needs `max_results` above roughly 35,000 rows (the default is 100).

Repair proposal (not implemented): read the stage through the `SORTED:` decoder (which has the stream fallback) or add `ReadBFSResults` → `ReadBFSResultsStream` to the fallbacks. Governing statement: [algorithms.op.walks](../ontology/features/algorithms.g5.md#algorithms.op.walks).

<a id="bug-str-106"></a>
### materialize_inference derives less than the RDFS entailments the API reference promises

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 38)

Found by: the frozen W44 prediction I7 missed ([predictions](../uplift/consolidated/iteration-38/inference-PAIRS.md)); source reading added I10; [inference_rows](models/inference_rows/NOTES.md) `theorem_no_subproperty_propagation`, `theorem_domain_type_not_lifted`, controls `derive-rdfs7`, `derive-lifts-domain`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-38/inference-observed-20261117T003415Z.json) I7_I8_I10; [binding](results/inference_rows/20261117T003857Z-binding/receipt.json)). With `p subPropertyOf q`, `x p y`, `p domain D`, `p range R` and `D subClassOf E`, materializing writes `x type D` and `y type R` only: no `x q y` and no `x type E`. Rerunning adds nothing, because inference reads only asserted edges. Passing neighbors: subclass chains, types from asserted types, domain and range (I1, I8).

Expected: the API reference: "Derive RDFS (`rules="owl"`: also OWL) entailments in one graph". RDFS entailment includes the subproperty rule (rdfs7) and applies the subclass rule to every derived type (rdfs9). The docstring lists exactly the rules implemented, so the source and the reference disagree.

Consequence: a reader of the reference expects a superproperty query or a superclass of a domain to find these nodes, and it does not. Low: missing derived rows; asserted data unchanged.

Repair proposal (not implemented): either derive to a fixpoint with rdfs7 and lift derived types, or state the rule list in the reference. Governing statement: [install.inference](../ontology/concepts/install.g5.md#install.inference).

<a id="bug-str-108"></a>
### Validating only new node IDs, as the semantic-layer guide suggests, refuses valid data whose shape checks an edge's target

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 39)

Found by: the frozen W45 prediction S6 ([predictions](../uplift/consolidated/iteration-39/shacl-PAIRS.md)); [shacl_data](models/shacl_data/NOTES.md) `theorem_focus_only_breaks_class`, control `focus-loads-targets`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-39/shacl-observed-20261117T004330Z.json) S5, S6; [binding](results/shacl_data/20261117T004553Z-binding/receipt.json) cases `class_full`, `class_focus_only`). A drug with an `INHIBITS` edge to a node labelled as the shape's `sh:class` conforms when both IDs are listed, and fails ("Value does not have class") when only the drug is listed.

Expected: SEMANTIC_LAYER.md's ingestion pattern validates `node_ids=new_ids` and raises on any violation; it also says "Validating only some nodes reads only their triples", so the outcome is documented, but the recommended pattern rejects a valid new node that points at an existing one.

Consequence: an ingestion step built as the guide shows refuses valid data for any shape that looks at a neighbor. Low: a false refusal, visible.

Repair proposal (not implemented): load the listed nodes' edge targets' type triples too, or document the limitation beside the pattern. Governing statement: [install.shacl](../ontology/concepts/install.g5.md#install.shacl).

<a id="bug-cyp-108"></a>
### map_sql_relationship reads target_fk on the target table, while its documentation puts the key on the source table

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 40)

Found by: the frozen W46 prediction T4 missed ([predictions](../uplift/consolidated/iteration-40/sqlmap-PAIRS.md)); [sql_mapping](models/sql_mapping/NOTES.md) `theorem_fk_side_differs`, control `join-on-source-fk`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-40/sqlmap-observed-20261117T004907Z.json) T4; [second observation](../uplift/consolidated/iteration-40/sqlmap-observed2-20261117T004940Z.json); [binding](results/sql_mapping/20261117T005114Z-binding/receipt.json) `join_key_on_source`, `join_key_on_target`). With `Target.drug_id` holding a drug's id, `map_sql_relationship("MTarget", "OF", "MDrug", target_fk="drug_id")` (the key on the source table, as documented) makes `MATCH (t:MTarget)-[:OF]->(d:MDrug)` fail with `SQLCODE -29` ("Field 'N1.DRUG_ID' not found"); mapping the reverse direction, `MDrug -[:HAS]-> MTarget` with the same `target_fk`, answers the right pairs.

Expected: the method's documentation: "The edge is either a foreign key on the source table (`target_fk`) or a join table"; [fhir.sql_mapping.relationships](../ontology/features/fhir.g5.md#fhir.sql_mapping.relationships) said the same.

Consequence: a caller following the documentation gets an error, or, where the target table happens to have a column of that name, a silent join on the wrong column (not exercised). Low.

Repair proposal (not implemented): read `target_fk` on the source table, or rename the parameter and document that it names a target-table column holding the source id. Governing statement: [fhir.sql_mapping](../ontology/features/fhir.g5.md#fhir.sql_mapping).

<a id="bug-cyp-109"></a>
### A Cypher pattern from a mapped label through an IVG relationship fails with an SQL error

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 40)

Found by: source-informed addition to W46 after the freeze ([second observation](../uplift/consolidated/iteration-40/sqlmap-observed2-20261117T004940Z.json)); [sql_mapping](models/sql_mapping/NOTES.md) `theorem_mapped_with_ivg_relationship_errors`, control `unmapped-rel-translated`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-40/sqlmap-observed-20261117T004907Z.json) T5_rel_after_remove; [second observation](../uplift/consolidated/iteration-40/sqlmap-observed2-20261117T004940Z.json); [binding](results/sql_mapping/20261117T005114Z-binding/receipt.json) `mapped_unmapped_rel`). With node `d1` of a mapped label and an IVG edge `d1 -[TREATS]-> x`, `MATCH (d:MappedLabel)-[:TREATS]->(x)` and `MATCH (d)-[r]->(x)` from a mapped node return `result.error` with `SQLCODE -29` ("Field 'N0.NODE_ID' not found"). Passing neighbors: the same relationship from an IVG node, and a mapped relationship between mapped labels, answer rows.

Expected: [fhir.sql_mapping.adjacency](../ontology/features/fhir.g5.md#fhir.sql_mapping.adjacency): "Pattern and property queries in Cypher see them"; nothing says a mapped node cannot take part in a pattern with IVG's own relationships.

Consequence: a query mixing mapped rows and IVG edges cannot be answered; the error is visible (`result.error`, or `RuntimeError` with `raise_on_error`). Low.

Repair proposal (not implemented): translate a non-mapped relationship from a mapped node against the mapped id column, or refuse it with a message that names the limitation. Governing statement: [fhir.sql_mapping](../ontology/features/fhir.g5.md#fhir.sql_mapping).

<a id="bug-cyp-110"></a>
### map_sql_table refuses an existing table named without a schema

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 40)

Found by: source reading during W46 (not frozen) ([observation](../uplift/consolidated/iteration-40/sqlmap-observed-20261117T004907Z.json) T0); [sql_mapping](models/sql_mapping/NOTES.md) `theorem_unqualified_name_refused`, control `unqualified-checks-sqluser`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([binding](results/sql_mapping/20261117T005114Z-binding/receipt.json) `unqualified_accepted`, `qualified_sqluser_accepted`). A table created as `CREATE TABLE BPlain…` (IRIS puts it in `SQLUser`) is refused by `map_sql_table("BPlain…", ...)` with "Table … or column 'id' not found"; `map_sql_table("SQLUser.BPlain…", ...)` accepts it.

Expected: the API reference: "Map an existing SQL table". IRIS resolves an unqualified table name in `SQLUser`.

Observed: the existence check looks in `INFORMATION_SCHEMA.COLUMNS` under `TABLE_SCHEMA = 'USER'` when the name has no schema (`_engine/fhir.py:111-118`).

Consequence: a false refusal with a misleading message; qualifying the name works. Low.

Repair proposal (not implemented): check the unqualified name under `SQLUser` (or resolve the default schema). Governing statement: [fhir.sql_mapping](../ontology/features/fhir.g5.md#fhir.sql_mapping).

<a id="bug-srch-105"></a>
### embed_nodes ignores an exclude_pattern that contains an underscore or a percent sign

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 43)

Found by: observation in W49 (E1), then source reading ([predictions](../uplift/consolidated/iteration-43/embed-nodes-PAIRS.md); E5 was not predicted with confidence); [embed_selection](models/embed_selection/NOTES.md) `theorem_special_pattern_excludes_nothing`, control `escape-honoured`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-43/embed-nodes-observed-20261117T010321Z.json) E1, E5; [binding](results/embed_selection/20261117T010437Z-binding/receipt.json) `underscore_pattern_b_x`, `plain_pattern_dx`). `embed_nodes(label=..., exclude_pattern="<prefix>_skip*")` embeds the node `<prefix>_skip_me`; `exclude_pattern="*dx*"` (no underscore) excludes `…dx`.

Expected: the parameter's name and the selector's glob translation promise exclusion by a glob; node IDs commonly contain `_`.

Observed: `_glob_to_sql_like` escapes `_` and `%` with a backslash, and the clause is `node_id NOT LIKE '…'` with no `ESCAPE`; IRIS then reads the backslash as a literal character, so the pattern matches no ID (`embed_selector.py:71-72, 110-112`).

Consequence: nodes the caller meant to exclude are embedded, costing model time and storing vectors nobody asked for. Low.

Repair proposal (not implemented): add `ESCAPE '\'` to the clause. Governing statement: [search.embedding.bulk](../ontology/features/search.g5.md#search.embedding.bulk).

<a id="bug-srch-106"></a>
### embed_nodes in a named graph selects a node by a label that only its twin in another graph has

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 43)

Found by: source reading after the W49 freeze (E8, not frozen) ([predictions](../uplift/consolidated/iteration-43/embed-nodes-PAIRS.md)); [embed_selection](models/embed_selection/NOTES.md) `theorem_label_from_other_graph`, control `label-scoped`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-43/embed-nodes-observed-20261117T010321Z.json) E6_E8_graph; [binding](results/embed_selection/20261117T010437Z-binding/receipt.json) `twin_in_G_selected`). Node `g3` has the label in the default graph; the node `g3` in graph G has no label. `embed_nodes(label=..., graph=G, model_key=k)` stores a vector for G's `g3`. Passing neighbor: a G node without the label in any graph is not selected.

Expected: [graph scope](../ontology/concepts/graph-scope.g5.md): "The same node ID in two graphs is two nodes, each with its own labels"; the method's docstring: "Both the node selection and the writes are scoped".

Observed: the label condition is `node_id IN (SELECT s FROM rdf_labels WHERE label = …)` with no graph condition (`embed_selector.py:98-101`), while the node and `missing_only` conditions are scoped.

Consequence: vectors for nodes outside the requested label in that graph. Low: extra vectors; no other data changes.

Repair proposal (not implemented): scope the label subquery to the graph. Governing statement: [search.embedding.bulk](../ontology/features/search.g5.md#search.embedding.bulk).

<a id="bug-plt-109"></a>
### The semantic-layer guide says an over-large PROV window exports an empty file; the export raises instead

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 44)

Found by: the frozen W50 prediction P8, taken from the guide, missed ([predictions](../uplift/consolidated/iteration-44/prov-PAIRS.md)); [prov_window](models/prov_window/NOTES.md) `theorem_large_window_raises`, control `doc-matches-code`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-44/prov-observed-20261117T010711Z.json) P8; [binding](results/prov_window/20261117T010842Z-binding/receipt.json) `export_all_time`). A window of 40,000 edges makes `prov_export` raise `RuntimeError: <MAXSTRING>…`; no file is written. Passing neighbor: windows that fit export normally (P1-P3).

Expected: SEMANTIC_LAYER.md: "A window larger than that string can hold is logged as a warning and exported as an empty file, not raised"; the method's docstring: "A failed window read is logged and exports nothing."

Consequence: a caller following the guide does not expect the exception. Low: the behavior is safer than documented; the documents are wrong.

Repair proposal (not implemented): correct the guide and docstring, or read the window in chunks. Governing statement: [install.export.prov](../ontology/concepts/install.g5.md#install.export.prov).

<a id="bug-plt-112"></a>
### export_rdf_from_cypher drops a row whose value is 0, false or empty unless the columns are named s, p and o

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 45)

Found by: source reading after the W51 freeze (C11, not frozen) ([predictions](../uplift/consolidated/iteration-45/cyphexport-PAIRS.md)); [cypher_export](models/cypher_export/NOTES.md) `theorem_falsy_value_depends_on_names`, control `positional-checks-null`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-45/cyphexport-observed-20261117T011128Z.json) C11; [binding](results/cypher_export/20261117T011234Z-binding/receipt.json) `named_zero`, `positional_zero`). With a property `v = 0` on two nodes, `RETURN n.node_id AS s, 'v' AS p, n.v AS o` exports 2 triples, and the same query with columns `x, y, z` exports 0.

Expected: SEMANTIC_LAYER.md: "Return three columns named `s`, `p` and `o` (or any three columns, read in that order)".

Consequence: renaming columns silently changes which rows are exported. Low.

Repair proposal (not implemented): test positional values against null, as the named path does. Governing statement: [install.export.rdf.cypher](../ontology/concepts/install.g5.md#install.export.rdf.cypher).

<a id="bug-srch-108"></a>
### ivf_search answers a query of another width with scores instead of refusing it

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 46)

Found by: the frozen W52 prediction V8 missed ([predictions](../uplift/consolidated/iteration-46/ivf-PAIRS.md)); [ivf_entries](models/ivf_entries/NOTES.md) `theorem_other_width_answered`, control `width-checked`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-46/ivf-observed-20261117T011444Z.json) V8; [binding](results/ivf_entries/20261117T011629Z-binding/receipt.json) `other_width_answered`). On a 4-wide index a 3-wide query returns three hits, two of them scored 1.0.

Expected: [search.embedding.width](../ontology/features/search.g5.md#search.embedding.width): "A query vector is never padded or cut to fit a table. A query of the wrong width raises an error instead of returning scores." The IVF index is built from such a table.

Consequence: a caller mixing models gets a ranking computed over part of the vector, with no error. Low: needs a wrong-width query.

Repair proposal (not implemented): refuse a query whose width differs from `cfg dim`. Governing statement: [search.ivf](../ontology/features/search.g5.md#search.ivf).

<a id="bug-srch-111"></a>
### `/vectorSearch` and `/hybridSearch` refuse a query of another width for a graph with no vectors

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 49)

Found by: W56 prediction Y1 (held for a 768-wide query, missed for a 4-wide one) and the source of `PyOps.vectorToJson` / `getExpectedDimension`; [retrieval_compose](models/retrieval_compose/NOTES.md) `theorem_unrouted_rest_search_refuses_width`; control `unrouted-no-width-check`.

Reproduced by: **Partially reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-49/retrieval-observed-20261117T023944Z.json) `Y1_*`; [binding](results/retrieval_compose/20261117T024807Z-binding/receipt.json) `pyops_unrouted_4`, `pyops_unrouted_768`, `engine_unrouted_4`). `Graph.KG.PyOps.VectorSearch` (the `/vectorSearch` body) for a named graph with no route and a 4-wide query raises "Query embedding dimension 4 does not match expected 768"; with a 768-wide query it answers []; the engine's `kg_KNN_VEC` answers [] for the 4-wide query. The REST application itself was not deployed, so the HTTP response is the missing step.

Expected: [search.routes.no_fallback](../ontology/features/search.g5.md#search.routes.no_fallback): an unrouted pair answers nothing, never a width error.

Observed: `vectorToJson` checks the width against `getExpectedDimension`, which answers `getDefaultDimension()` = 768 for a pair with no route (`PyOps.cls:136-141`), before the route is looked up.

Consequence: a REST search of a graph that has no vectors yet fails with a misleading width error instead of an empty answer. Low.

Repair proposal (not implemented): look the route up first and answer [] for an unrouted named graph. Governing statement: [search.fusion.rest](../ontology/features/search.g5.md#search.fusion.rest).

<a id="bug-srch-112"></a>
### `/hybridSearch` replaces a fusion constant of 0 with 60

Severity: Low · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 49)

Found by: the source of `PyOps.HybridSearch` (`c = int(c) if c else 60`, `PyOps.cls:374`) after W56 F8; [retrieval_compose](models/retrieval_compose/NOTES.md) `theorem_hybrid_c_zero_becomes_60`; control `hybrid-c-kept`.

Reproduced by: **Partially reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin ([observation](../uplift/consolidated/iteration-49/retrieval-observed-20261117T023944Z.json) `F8_pyops_hybrid_G_c0`; [binding](results/retrieval_compose/20261117T024807Z-binding/receipt.json) `pyops_hybrid_c0`): `HybridSearch(q, "zeta", 100, 0, g)` answers exactly the scores of `c = 60`. The REST route's own argument handling was not exercised.

Expected: the caller's constant (the SQL procedure and the engine accept 0 and score 1/rank).

Consequence: a caller asking for c = 0 silently gets c = 60. Low (an unusual value).

Repair proposal (not implemented): default only a missing `c`. Governing statement: [search.fusion.surfaces](../ontology/features/search.g5.md#search.fusion.surfaces).

<a id="bug-plt-022"></a>
### The schema check is skipped silently for logins without global access and for non-IRIS connections

Severity: Low

Run: Uplift 2026-11-13

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Found by: `witness_unreadable_record_skips_the_check` (W-S4) in [platform.rs](models/platform/platform.rs) ([prove receipt](results/platform/20261114T002651Z-prove/receipt.json)); A-platform F-S8.

The first-access check logs and skips when the record cannot be read (`engine.py:1862-1866`; `schema_name.py:270-283`), so a pooled or proxied DB-API connection gets no check. This is documented (ADMIN_GUIDE:515-518): an accepted design gap, recorded so the premise P-NATIVE-READABLE is visible. Governing statement: [install.schema.refusal](../ontology/concepts/install.g5.md#install.schema.refusal).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-plt-023"></a>
### The IVF SQL function checks the privilege on a table that the index's own global names

Severity: Low

Run: Uplift 2026-11-13

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Found by: A-platform F-H8 (sub-reader a).

`kg_IVF` checks SELECT on the table named by `^IVF(name,"cfg","table")` (`SqlProcs.cls:141`), which a role able to write the database can redirect to a table it may read. Observation only; the consequence was not traced. Governing statement: [access.iris_boundary](../ontology/concepts/access.g5.md#access.iris_boundary).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.

<a id="bug-doc-001"></a>
### The OpsReview brief's one-call redaction recipe never reaches the tenant's node records

Severity: Low

Run: Uplift 2026-11-13

Found by: A-history F3 (confirmed by source) ([intent](../uplift/ivg-verus-initial/intent/ledger-history.md)); review R1-core CV-6 and R1-6.

Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.

Historical reproduction record: none — follows from the behavior shown by [redaction_binding](receipts/native/redaction_binding.json), where node records carry the default graph.

`IVG-OPSREVIEW-BRIEF.md:125` recommends `engine.ledger.redact(graph, prefix="tenant|")`. Node records always carry graph `""` (`LedgerApply.cls:232-369`; spec 256 plan.md:9) and `Matches` requires the record's graph to equal the target (`LedgerRedact.cls:93`), so this call leaves every node record of the tenant. The correct recipe is the pair in ADR-0013:37 (the tenant's graph, then the default graph with the prefix). Governing statement: [redaction.tenant](../ontology/features/redaction.g5.md#redaction.tenant).


Audit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.


## Archived ID navigation

These anchors preserve older links. The corresponding claims and review dispositions are outside this active register.

<span id="bug-plt-106"></span> [bug-plt-106: filed in iteration 25, merged into bug-plt-027](#bug-plt-027)

<span id="bug-str-002"></span> [bug-str-002: review record](audits/register-20261115/bugs-review.md#bug-str-002)

<span id="bug-srch-002"></span> [bug-srch-002: review record](audits/register-20261115/bugs-review.md#bug-srch-002)

<span id="bug-srch-007"></span> [bug-srch-007: review record](audits/register-20261115/bugs-review.md#bug-srch-007)

<span id="bug-plt-001"></span> [bug-plt-001: review record](audits/register-20261115/bugs-review.md#bug-plt-001)

<span id="F-0409"></span> [F-0409: review record](audits/register-20261115/bugs-review.md#F-0409)

<span id="F-0505"></span> [F-0505: review record](audits/register-20261115/bugs-review.md#F-0505)

<span id="F-C1804"></span> [F-C1804: review record](audits/register-20261115/bugs-review.md#F-C1804)

<span id="bug-str-003"></span> [bug-str-003: review record](audits/register-20261115/bugs-review.md#bug-str-003)

<span id="bug-tmp-004"></span> [bug-tmp-004: review record](audits/register-20261115/bugs-review.md#bug-tmp-004)

<span id="bug-tmp-005"></span> [bug-tmp-005: review record](audits/register-20261115/bugs-review.md#bug-tmp-005)

<span id="bug-tmp-011"></span> [bug-tmp-011: review record](audits/register-20261115/bugs-review.md#bug-tmp-011)

<span id="bug-srch-003"></span> [bug-srch-003: review record](audits/register-20261115/bugs-review.md#bug-srch-003)

<span id="bug-srch-004"></span> [bug-srch-004: review record](audits/register-20261115/bugs-review.md#bug-srch-004)

<span id="bug-srch-009"></span> [bug-srch-009: review record](audits/register-20261115/bugs-review.md#bug-srch-009)

<span id="bug-srch-010"></span> [bug-srch-010: review record](audits/register-20261115/bugs-review.md#bug-srch-010)

<span id="bug-plt-002"></span> [bug-plt-002: review record](audits/register-20261115/bugs-review.md#bug-plt-002)

<span id="bug-plt-003"></span> [bug-plt-003: review record](audits/register-20261115/bugs-review.md#bug-plt-003)

<span id="bug-plt-008"></span> [bug-plt-008: review record](audits/register-20261115/bugs-review.md#bug-plt-008)

<span id="bug-plt-010"></span> [bug-plt-010: review record](audits/register-20261115/bugs-review.md#bug-plt-010)

<span id="bug-plt-024"></span> [bug-plt-024: review record](audits/register-20261115/bugs-review.md#bug-plt-024)

<span id="bug-cyp-003"></span> [bug-cyp-003: review record](audits/register-20261115/bugs-review.md#bug-cyp-003)

<span id="bug-led-003"></span> [bug-led-003: review record](audits/register-20261115/bugs-review.md#bug-led-003)

<span id="bug-srch-016"></span> [bug-srch-016: review record](audits/register-20261115/bugs-review.md#bug-srch-016)

<span id="F-0201"></span> [F-0201: review record](audits/register-20261115/bugs-review.md#F-0201)

<span id="F-0202"></span> [F-0202: review record](audits/register-20261115/bugs-review.md#F-0202)

<span id="F-0303"></span> [F-0303: review record](audits/register-20261115/bugs-review.md#F-0303)

<span id="F-0305"></span> [F-0305: review record](audits/register-20261115/bugs-review.md#F-0305)

<span id="F-0307"></span> [F-0307: review record](audits/register-20261115/bugs-review.md#F-0307)

<span id="F-0308"></span> [F-0308: review record](audits/register-20261115/bugs-review.md#F-0308)

<span id="F-0406"></span> [F-0406: review record](audits/register-20261115/bugs-review.md#F-0406)

<span id="F-0504"></span> [F-0504: review record](audits/register-20261115/bugs-review.md#F-0504)

<span id="F-0510"></span> [F-0510: review record](audits/register-20261115/bugs-review.md#F-0510)

<span id="F-0601"></span> [F-0601: review record](audits/register-20261115/bugs-review.md#F-0601)

<span id="F-0604"></span> [F-0604: review record](audits/register-20261115/bugs-review.md#F-0604)

<span id="F-0615"></span> [F-0615: review record](audits/register-20261115/bugs-review.md#F-0615)

<span id="F-0616"></span> [F-0616: review record](audits/register-20261115/bugs-review.md#F-0616)

<span id="F-0618"></span> [F-0618: review record](audits/register-20261115/bugs-review.md#F-0618)

<span id="F-0701"></span> [F-0701: review record](audits/register-20261115/bugs-review.md#F-0701)

<span id="F-0703"></span> [F-0703: review record](audits/register-20261115/bugs-review.md#F-0703)

<span id="F-0704"></span> [F-0704: review record](audits/register-20261115/bugs-review.md#F-0704)

<span id="F-0706"></span> [F-0706: review record](audits/register-20261115/bugs-review.md#F-0706)

<span id="F-0709"></span> [F-0709: review record](audits/register-20261115/bugs-review.md#F-0709)

<span id="F-0805"></span> [F-0805: review record](audits/register-20261115/bugs-review.md#F-0805)

<span id="F-0813"></span> [F-0813: review record](audits/register-20261115/bugs-review.md#F-0813)

<span id="F-1007"></span> [F-1007: review record](audits/register-20261115/bugs-review.md#F-1007)

<span id="F-1103"></span> [F-1103: review record](audits/register-20261115/bugs-review.md#F-1103)

<span id="F-1105"></span> [F-1105: review record](audits/register-20261115/bugs-review.md#F-1105)

<span id="F-1107"></span> [F-1107: review record](audits/register-20261115/bugs-review.md#F-1107)

<span id="F-1508"></span> [F-1508: review record](audits/register-20261115/bugs-review.md#F-1508)

<span id="F-1601"></span> [F-1601: review record](audits/register-20261115/bugs-review.md#F-1601)

<span id="F-1602"></span> [F-1602: review record](audits/register-20261115/bugs-review.md#F-1602)

<span id="F-1607"></span> [F-1607: review record](audits/register-20261115/bugs-review.md#F-1607)

<span id="F-1609"></span> [F-1609: review record](audits/register-20261115/bugs-review.md#F-1609)

<span id="F-1610"></span> [F-1610: review record](audits/register-20261115/bugs-review.md#F-1610)

<span id="F-1615"></span> [F-1615: review record](audits/register-20261115/bugs-review.md#F-1615)

<span id="F-1712"></span> [F-1712: review record](audits/register-20261115/bugs-review.md#F-1712)

<span id="F-1803"></span> [F-1803: review record](audits/register-20261115/bugs-review.md#F-1803)

<span id="F-1805"></span> [F-1805: review record](audits/register-20261115/bugs-review.md#F-1805)

<span id="F-C0330"></span> [F-C0330: review record](audits/register-20261115/bugs-review.md#F-C0330)

<span id="F-C0348"></span> [F-C0348: review record](audits/register-20261115/bugs-review.md#F-C0348)

<span id="F-C0349"></span> [F-C0349: review record](audits/register-20261115/bugs-review.md#F-C0349)

<span id="F-C0350"></span> [F-C0350: review record](audits/register-20261115/bugs-review.md#F-C0350)

<span id="F-C0450"></span> [F-C0450: review record](audits/register-20261115/bugs-review.md#F-C0450)

<span id="F-C0701"></span> [F-C0701: review record](audits/register-20261115/bugs-review.md#F-C0701)

<span id="F-C0748"></span> [F-C0748: review record](audits/register-20261115/bugs-review.md#F-C0748)

<span id="F-C0803"></span> [F-C0803: review record](audits/register-20261115/bugs-review.md#F-C0803)

<span id="F-C1601"></span> [F-C1601: review record](audits/register-20261115/bugs-review.md#F-C1601)

<span id="F-C1604"></span> [F-C1604: review record](audits/register-20261115/bugs-review.md#F-C1604)

<span id="F-C1703"></span> [F-C1703: review record](audits/register-20261115/bugs-review.md#F-C1703)

<span id="F-C1750"></span> [F-C1750: review record](audits/register-20261115/bugs-review.md#F-C1750)

<span id="F-C1801"></span> [F-C1801: review record](audits/register-20261115/bugs-review.md#F-C1801)

<span id="F-C1802"></span> [F-C1802: review record](audits/register-20261115/bugs-review.md#F-C1802)

<span id="bug-plt-104"></span> [bug-plt-104: review record](audits/register-20261115/bugs-review.md#bug-plt-104)

<span id="bug-str-006"></span> [bug-str-006: review record](audits/register-20261115/bugs-review.md#bug-str-006)

<span id="bug-str-007"></span> [bug-str-007: review record](audits/register-20261115/bugs-review.md#bug-str-007)

<span id="bug-str-009"></span> [bug-str-009: review record](audits/register-20261115/bugs-review.md#bug-str-009)

<span id="bug-str-010"></span> [bug-str-010: review record](audits/register-20261115/bugs-review.md#bug-str-010)

<span id="bug-str-011"></span> [bug-str-011: review record](audits/register-20261115/bugs-review.md#bug-str-011)

<span id="bug-str-012"></span> [bug-str-012: review record](audits/register-20261115/bugs-review.md#bug-str-012)

<span id="bug-str-013"></span> [bug-str-013: review record](audits/register-20261115/bugs-review.md#bug-str-013)

<span id="bug-str-015"></span> [bug-str-015: review record](audits/register-20261115/bugs-review.md#bug-str-015)

<span id="bug-tmp-006"></span> [bug-tmp-006: review record](audits/register-20261115/bugs-review.md#bug-tmp-006)

<span id="bug-tmp-008"></span> [bug-tmp-008: review record](audits/register-20261115/bugs-review.md#bug-tmp-008)

<span id="bug-tmp-013"></span> [bug-tmp-013: review record](audits/register-20261115/bugs-review.md#bug-tmp-013)

<span id="bug-srch-011"></span> [bug-srch-011: review record](audits/register-20261115/bugs-review.md#bug-srch-011)

<span id="bug-srch-014"></span> [bug-srch-014: review record](audits/register-20261115/bugs-review.md#bug-srch-014)

<span id="bug-srch-015"></span> [bug-srch-015: review record](audits/register-20261115/bugs-review.md#bug-srch-015)

<span id="bug-plt-014"></span> [bug-plt-014: review record](audits/register-20261115/bugs-review.md#bug-plt-014)

<span id="bug-plt-015"></span> [bug-plt-015: review record](audits/register-20261115/bugs-review.md#bug-plt-015)

<span id="bug-plt-016"></span> [bug-plt-016: review record](audits/register-20261115/bugs-review.md#bug-plt-016)

<span id="bug-plt-018"></span> [bug-plt-018: review record](audits/register-20261115/bugs-review.md#bug-plt-018)

<span id="bug-plt-019"></span> [bug-plt-019: review record](audits/register-20261115/bugs-review.md#bug-plt-019)

<span id="bug-plt-020"></span> [bug-plt-020: review record](audits/register-20261115/bugs-review.md#bug-plt-020)

<span id="bug-plt-021"></span> [bug-plt-021: review record](audits/register-20261115/bugs-review.md#bug-plt-021)

<span id="bug-cyp-004"></span> [bug-cyp-004: review record](audits/register-20261115/bugs-review.md#bug-cyp-004)

<span id="bug-led-002"></span> [bug-led-002: review record](audits/register-20261115/bugs-review.md#bug-led-002)

<span id="bug-str-016"></span> [bug-str-016: review record](audits/register-20261115/bugs-review.md#bug-str-016)

<span id="bug-plt-026"></span> [bug-plt-026: review record](audits/register-20261115/bugs-review.md#bug-plt-026)

<span id="bug-led-011"></span> [bug-led-011: review record](audits/register-20261115/bugs-review.md#bug-led-011)

<span id="bug-str-017"></span> [bug-str-017: review record](audits/register-20261115/bugs-review.md#bug-str-017)

<span id="bug-test-001"></span> [bug-test-001: review record](audits/register-20261115/bugs-review.md#bug-test-001)

<span id="bug-led-101"></span> [bug-led-101: review record](audits/register-20261115/bugs-review.md#bug-led-101)

<span id="F-0101"></span> [F-0101: review record](audits/register-20261115/bugs-review.md#F-0101)

<span id="F-0102"></span> [F-0102: review record](audits/register-20261115/bugs-review.md#F-0102)

<span id="F-0103"></span> [F-0103: review record](audits/register-20261115/bugs-review.md#F-0103)

<span id="F-0104"></span> [F-0104: review record](audits/register-20261115/bugs-review.md#F-0104)

<span id="F-0105"></span> [F-0105: review record](audits/register-20261115/bugs-review.md#F-0105)

<span id="F-0107"></span> [F-0107: review record](audits/register-20261115/bugs-review.md#F-0107)

<span id="F-0108"></span> [F-0108: review record](audits/register-20261115/bugs-review.md#F-0108)

<span id="F-0109"></span> [F-0109: review record](audits/register-20261115/bugs-review.md#F-0109)

<span id="F-0110"></span> [F-0110: review record](audits/register-20261115/bugs-review.md#F-0110)

<span id="F-0203"></span> [F-0203: review record](audits/register-20261115/bugs-review.md#F-0203)

<span id="F-0205"></span> [F-0205: review record](audits/register-20261115/bugs-review.md#F-0205)

<span id="F-0207"></span> [F-0207: review record](audits/register-20261115/bugs-review.md#F-0207)

<span id="F-0301"></span> [F-0301: review record](audits/register-20261115/bugs-review.md#F-0301)

<span id="F-0302"></span> [F-0302: review record](audits/register-20261115/bugs-review.md#F-0302)

<span id="F-0306"></span> [F-0306: review record](audits/register-20261115/bugs-review.md#F-0306)

<span id="F-0309"></span> [F-0309: review record](audits/register-20261115/bugs-review.md#F-0309)

<span id="F-0401"></span> [F-0401: review record](audits/register-20261115/bugs-review.md#F-0401)

<span id="F-0404"></span> [F-0404: review record](audits/register-20261115/bugs-review.md#F-0404)

<span id="F-0405"></span> [F-0405: review record](audits/register-20261115/bugs-review.md#F-0405)

<span id="F-0407"></span> [F-0407: review record](audits/register-20261115/bugs-review.md#F-0407)

<span id="F-0408"></span> [F-0408: review record](audits/register-20261115/bugs-review.md#F-0408)

<span id="F-0503"></span> [F-0503: review record](audits/register-20261115/bugs-review.md#F-0503)

<span id="F-0506"></span> [F-0506: review record](audits/register-20261115/bugs-review.md#F-0506)

<span id="F-0511"></span> [F-0511: review record](audits/register-20261115/bugs-review.md#F-0511)

<span id="F-0512"></span> [F-0512: review record](audits/register-20261115/bugs-review.md#F-0512)

<span id="F-0513"></span> [F-0513: review record](audits/register-20261115/bugs-review.md#F-0513)

<span id="F-0514"></span> [F-0514: review record](audits/register-20261115/bugs-review.md#F-0514)

<span id="F-0602"></span> [F-0602: review record](audits/register-20261115/bugs-review.md#F-0602)

<span id="F-0603"></span> [F-0603: review record](audits/register-20261115/bugs-review.md#F-0603)

<span id="F-0605"></span> [F-0605: review record](audits/register-20261115/bugs-review.md#F-0605)

<span id="F-0611"></span> [F-0611: review record](audits/register-20261115/bugs-review.md#F-0611)

<span id="F-0612"></span> [F-0612: review record](audits/register-20261115/bugs-review.md#F-0612)

<span id="F-0613"></span> [F-0613: review record](audits/register-20261115/bugs-review.md#F-0613)

<span id="F-0614"></span> [F-0614: review record](audits/register-20261115/bugs-review.md#F-0614)

<span id="F-0617"></span> [F-0617: review record](audits/register-20261115/bugs-review.md#F-0617)

<span id="F-0708"></span> [F-0708: review record](audits/register-20261115/bugs-review.md#F-0708)

<span id="F-0710"></span> [F-0710: review record](audits/register-20261115/bugs-review.md#F-0710)

<span id="F-0804"></span> [F-0804: review record](audits/register-20261115/bugs-review.md#F-0804)

<span id="F-0806"></span> [F-0806: review record](audits/register-20261115/bugs-review.md#F-0806)

<span id="F-0807"></span> [F-0807: review record](audits/register-20261115/bugs-review.md#F-0807)

<span id="F-0809"></span> [F-0809: review record](audits/register-20261115/bugs-review.md#F-0809)

<span id="F-0811"></span> [F-0811: review record](audits/register-20261115/bugs-review.md#F-0811)

<span id="F-0812"></span> [F-0812: review record](audits/register-20261115/bugs-review.md#F-0812)

<span id="F-0821"></span> [F-0821: review record](audits/register-20261115/bugs-review.md#F-0821)

<span id="F-0825"></span> [F-0825: review record](audits/register-20261115/bugs-review.md#F-0825)

<span id="F-0903"></span> [F-0903: review record](audits/register-20261115/bugs-review.md#F-0903)

<span id="F-0905"></span> [F-0905: review record](audits/register-20261115/bugs-review.md#F-0905)

<span id="F-0906"></span> [F-0906: review record](audits/register-20261115/bugs-review.md#F-0906)

<span id="F-0907"></span> [F-0907: review record](audits/register-20261115/bugs-review.md#F-0907)

<span id="F-0909"></span> [F-0909: review record](audits/register-20261115/bugs-review.md#F-0909)

<span id="F-1005"></span> [F-1005: review record](audits/register-20261115/bugs-review.md#F-1005)

<span id="F-1010"></span> [F-1010: review record](audits/register-20261115/bugs-review.md#F-1010)

<span id="F-1011"></span> [F-1011: review record](audits/register-20261115/bugs-review.md#F-1011)

<span id="F-1012"></span> [F-1012: review record](audits/register-20261115/bugs-review.md#F-1012)

<span id="F-1102"></span> [F-1102: review record](audits/register-20261115/bugs-review.md#F-1102)

<span id="F-1104"></span> [F-1104: review record](audits/register-20261115/bugs-review.md#F-1104)

<span id="F-1106"></span> [F-1106: review record](audits/register-20261115/bugs-review.md#F-1106)

<span id="F-1109"></span> [F-1109: review record](audits/register-20261115/bugs-review.md#F-1109)

<span id="F-1110"></span> [F-1110: review record](audits/register-20261115/bugs-review.md#F-1110)

<span id="F-1111"></span> [F-1111: review record](audits/register-20261115/bugs-review.md#F-1111)

<span id="F-1112"></span> [F-1112: review record](audits/register-20261115/bugs-review.md#F-1112)

<span id="F-1113"></span> [F-1113: review record](audits/register-20261115/bugs-review.md#F-1113)

<span id="F-1301"></span> [F-1301: review record](audits/register-20261115/bugs-review.md#F-1301)

<span id="F-1501"></span> [F-1501: review record](audits/register-20261115/bugs-review.md#F-1501)

<span id="F-1504"></span> [F-1504: review record](audits/register-20261115/bugs-review.md#F-1504)

<span id="F-1505"></span> [F-1505: review record](audits/register-20261115/bugs-review.md#F-1505)

<span id="F-1506"></span> [F-1506: review record](audits/register-20261115/bugs-review.md#F-1506)

<span id="F-1509"></span> [F-1509: review record](audits/register-20261115/bugs-review.md#F-1509)

<span id="F-1510"></span> [F-1510: review record](audits/register-20261115/bugs-review.md#F-1510)

<span id="F-1511"></span> [F-1511: review record](audits/register-20261115/bugs-review.md#F-1511)

<span id="F-1605"></span> [F-1605: review record](audits/register-20261115/bugs-review.md#F-1605)

<span id="F-1606"></span> [F-1606: review record](audits/register-20261115/bugs-review.md#F-1606)

<span id="F-1611"></span> [F-1611: review record](audits/register-20261115/bugs-review.md#F-1611)

<span id="F-1613"></span> [F-1613: review record](audits/register-20261115/bugs-review.md#F-1613)

<span id="F-1702"></span> [F-1702: review record](audits/register-20261115/bugs-review.md#F-1702)

<span id="F-1703"></span> [F-1703: review record](audits/register-20261115/bugs-review.md#F-1703)

<span id="F-1704"></span> [F-1704: review record](audits/register-20261115/bugs-review.md#F-1704)

<span id="F-1705"></span> [F-1705: review record](audits/register-20261115/bugs-review.md#F-1705)

<span id="F-1706"></span> [F-1706: review record](audits/register-20261115/bugs-review.md#F-1706)

<span id="F-1707"></span> [F-1707: review record](audits/register-20261115/bugs-review.md#F-1707)

<span id="F-1708"></span> [F-1708: review record](audits/register-20261115/bugs-review.md#F-1708)

<span id="F-1710"></span> [F-1710: review record](audits/register-20261115/bugs-review.md#F-1710)

<span id="F-1711"></span> [F-1711: review record](audits/register-20261115/bugs-review.md#F-1711)

<span id="F-1713"></span> [F-1713: review record](audits/register-20261115/bugs-review.md#F-1713)

<span id="F-1714"></span> [F-1714: review record](audits/register-20261115/bugs-review.md#F-1714)

<span id="F-1807"></span> [F-1807: review record](audits/register-20261115/bugs-review.md#F-1807)

<span id="F-C0090"></span> [F-C0090: review record](audits/register-20261115/bugs-review.md#F-C0090)

<span id="F-C0301"></span> [F-C0301: review record](audits/register-20261115/bugs-review.md#F-C0301)

<span id="F-C0302"></span> [F-C0302: review record](audits/register-20261115/bugs-review.md#F-C0302)

<span id="F-C0347"></span> [F-C0347: review record](audits/register-20261115/bugs-review.md#F-C0347)

<span id="F-C0351"></span> [F-C0351: review record](audits/register-20261115/bugs-review.md#F-C0351)

<span id="F-C0401"></span> [F-C0401: review record](audits/register-20261115/bugs-review.md#F-C0401)

<span id="F-C0402"></span> [F-C0402: review record](audits/register-20261115/bugs-review.md#F-C0402)

<span id="F-C0415"></span> [F-C0415: review record](audits/register-20261115/bugs-review.md#F-C0415)

<span id="F-C0440"></span> [F-C0440: review record](audits/register-20261115/bugs-review.md#F-C0440)

<span id="F-C0502"></span> [F-C0502: review record](audits/register-20261115/bugs-review.md#F-C0502)

<span id="F-C0601"></span> [F-C0601: review record](audits/register-20261115/bugs-review.md#F-C0601)

<span id="F-C0603"></span> [F-C0603: review record](audits/register-20261115/bugs-review.md#F-C0603)

<span id="F-C0604"></span> [F-C0604: review record](audits/register-20261115/bugs-review.md#F-C0604)

<span id="F-C0605"></span> [F-C0605: review record](audits/register-20261115/bugs-review.md#F-C0605)

<span id="F-C0606"></span> [F-C0606: review record](audits/register-20261115/bugs-review.md#F-C0606)

<span id="F-C0615"></span> [F-C0615: review record](audits/register-20261115/bugs-review.md#F-C0615)

<span id="F-C0640"></span> [F-C0640: review record](audits/register-20261115/bugs-review.md#F-C0640)

<span id="F-C0642"></span> [F-C0642: review record](audits/register-20261115/bugs-review.md#F-C0642)

<span id="F-C0670"></span> [F-C0670: review record](audits/register-20261115/bugs-review.md#F-C0670)

<span id="F-C0690"></span> [F-C0690: review record](audits/register-20261115/bugs-review.md#F-C0690)

<span id="F-C0703"></span> [F-C0703: review record](audits/register-20261115/bugs-review.md#F-C0703)

<span id="F-C0716"></span> [F-C0716: review record](audits/register-20261115/bugs-review.md#F-C0716)

<span id="F-C0717"></span> [F-C0717: review record](audits/register-20261115/bugs-review.md#F-C0717)

<span id="F-C0801"></span> [F-C0801: review record](audits/register-20261115/bugs-review.md#F-C0801)

<span id="F-C0802"></span> [F-C0802: review record](audits/register-20261115/bugs-review.md#F-C0802)

<span id="F-C0840"></span> [F-C0840: review record](audits/register-20261115/bugs-review.md#F-C0840)

<span id="F-C0940"></span> [F-C0940: review record](audits/register-20261115/bugs-review.md#F-C0940)

<span id="F-C0948"></span> [F-C0948: review record](audits/register-20261115/bugs-review.md#F-C0948)

<span id="F-C1001"></span> [F-C1001: review record](audits/register-20261115/bugs-review.md#F-C1001)

<span id="F-C1002"></span> [F-C1002: review record](audits/register-20261115/bugs-review.md#F-C1002)

<span id="F-C1040"></span> [F-C1040: review record](audits/register-20261115/bugs-review.md#F-C1040)

<span id="F-C1101"></span> [F-C1101: review record](audits/register-20261115/bugs-review.md#F-C1101)

<span id="F-C1102"></span> [F-C1102: review record](audits/register-20261115/bugs-review.md#F-C1102)

<span id="F-C1106"></span> [F-C1106: review record](audits/register-20261115/bugs-review.md#F-C1106)

<span id="F-C1107"></span> [F-C1107: review record](audits/register-20261115/bugs-review.md#F-C1107)

<span id="F-C1108"></span> [F-C1108: review record](audits/register-20261115/bugs-review.md#F-C1108)

<span id="F-C1109"></span> [F-C1109: review record](audits/register-20261115/bugs-review.md#F-C1109)

<span id="F-C1110"></span> [F-C1110: review record](audits/register-20261115/bugs-review.md#F-C1110)

<span id="F-C1204"></span> [F-C1204: review record](audits/register-20261115/bugs-review.md#F-C1204)

<span id="F-C1501"></span> [F-C1501: review record](audits/register-20261115/bugs-review.md#F-C1501)

<span id="F-C1502"></span> [F-C1502: review record](audits/register-20261115/bugs-review.md#F-C1502)

<span id="F-C1540"></span> [F-C1540: review record](audits/register-20261115/bugs-review.md#F-C1540)

<span id="F-C1548"></span> [F-C1548: review record](audits/register-20261115/bugs-review.md#F-C1548)

<span id="F-C1549"></span> [F-C1549: review record](audits/register-20261115/bugs-review.md#F-C1549)

<span id="F-C1602"></span> [F-C1602: review record](audits/register-20261115/bugs-review.md#F-C1602)

<span id="F-C1640"></span> [F-C1640: review record](audits/register-20261115/bugs-review.md#F-C1640)

<span id="F-C1641"></span> [F-C1641: review record](audits/register-20261115/bugs-review.md#F-C1641)

<span id="F-C1642"></span> [F-C1642: review record](audits/register-20261115/bugs-review.md#F-C1642)

<span id="F-C1701"></span> [F-C1701: review record](audits/register-20261115/bugs-review.md#F-C1701)

<span id="F-C1702"></span> [F-C1702: review record](audits/register-20261115/bugs-review.md#F-C1702)

<span id="F-C1704"></span> [F-C1704: review record](audits/register-20261115/bugs-review.md#F-C1704)

<span id="F-C1705"></span> [F-C1705: review record](audits/register-20261115/bugs-review.md#F-C1705)

<span id="F-C1706"></span> [F-C1706: review record](audits/register-20261115/bugs-review.md#F-C1706)

<span id="F-C1715"></span> [F-C1715: review record](audits/register-20261115/bugs-review.md#F-C1715)

<span id="F-C1716"></span> [F-C1716: review record](audits/register-20261115/bugs-review.md#F-C1716)

<span id="F-C1740"></span> [F-C1740: review record](audits/register-20261115/bugs-review.md#F-C1740)

<span id="F-C1742"></span> [F-C1742: review record](audits/register-20261115/bugs-review.md#F-C1742)

<span id="F-C1795"></span> [F-C1795: review record](audits/register-20261115/bugs-review.md#F-C1795)

<span id="F-C1848"></span> [F-C1848: review record](audits/register-20261115/bugs-review.md#F-C1848)

<span id="bug-plt-103"></span> [bug-plt-103: review record](audits/register-20261115/bugs-review.md#bug-plt-103)

<span id="bug-plt-105"></span> [bug-plt-105: review record](audits/register-20261115/bugs-review.md#bug-plt-105)

<span id="bug-tmp-012"></span> [bug-tmp-012: review record](audits/register-20261115/bugs-review.md#bug-tmp-012)

<span id="bug-doc-002"></span> [bug-doc-002: review record](audits/register-20261115/bugs-review.md#bug-doc-002)

<span id="bug-doc-003"></span> [bug-doc-003: review record](audits/register-20261115/bugs-review.md#bug-doc-003)

<span id="bug-doc-004"></span> [bug-doc-004: review record](audits/register-20261115/bugs-review.md#bug-doc-004)

<span id="bug-doc-005"></span> [bug-doc-005: review record](audits/register-20261115/bugs-review.md#bug-doc-005)

<span id="bug-doc-006"></span> [bug-doc-006: review record](audits/register-20261115/bugs-review.md#bug-doc-006)

<span id="bug-doc-007"></span> [bug-doc-007: review record](audits/register-20261115/bugs-review.md#bug-doc-007)

<span id="bug-doc-008"></span> [bug-doc-008: review record](audits/register-20261115/bugs-review.md#bug-doc-008)

<span id="bug-doc-009"></span> [bug-doc-009: review record](audits/register-20261115/bugs-review.md#bug-doc-009)

<span id="bug-doc-010"></span> [bug-doc-010: review record](audits/register-20261115/bugs-review.md#bug-doc-010)

<span id="bug-doc-011"></span> [bug-doc-011: review record](audits/register-20261115/bugs-review.md#bug-doc-011)

<span id="bug-doc-012"></span> [bug-doc-012: review record](audits/register-20261115/bugs-review.md#bug-doc-012)

<span id="bug-cyp-009"></span> [bug-cyp-009: review record](audits/register-20261115/bugs-review.md#bug-cyp-009)

<span id="bug-test-002"></span> [bug-test-002: review record](audits/register-20261115/bugs-review.md#bug-test-002)

<span id="bug-test-003"></span> [bug-test-003: review record](audits/register-20261115/bugs-review.md#bug-test-003)

<span id="F-0904"></span> [F-0904: review record](audits/register-20261115/bugs-review.md#F-0904)

<span id="F-1608"></span> [F-1608: review record](audits/register-20261115/bugs-review.md#F-1608)

<span id="F-1612"></span> [F-1612: review record](audits/register-20261115/bugs-review.md#F-1612)

<span id="F-C0403"></span> [F-C0403: review record](audits/register-20261115/bugs-review.md#F-C0403)

<span id="F-C1240"></span> [F-C1240: review record](audits/register-20261115/bugs-review.md#F-C1240)

<span id="F-C1720"></span> [F-C1720: review record](audits/register-20261115/bugs-review.md#F-C1720)

<span id="F-C0811"></span> [F-C0811: review record](audits/register-20261115/bugs-review.md#F-C0811)

<span id="F-C1711"></span> [F-C1711: review record](audits/register-20261115/bugs-review.md#F-C1711)

<span id="F-C0111"></span> [F-C0111: review record](audits/register-20261115/bugs-review.md#F-C0111)

<span id="F-C0511"></span> [F-C0511: review record](audits/register-20261115/bugs-review.md#F-C0511)

<span id="F-C0512"></span> [F-C0512: review record](audits/register-20261115/bugs-review.md#F-C0512)

<span id="F-C0513"></span> [F-C0513: review record](audits/register-20261115/bugs-review.md#F-C0513)

<span id="F-C1011"></span> [F-C1011: review record](audits/register-20261115/bugs-review.md#F-C1011)
