# Bugs and issues — IVG initial Verus uplift

Product baseline `3eaa79cf`. Each entry cites the governing source of the expected behavior, what the baseline does and the evidence. "Suspected" marks an entry whose product reachability is not yet shown natively. Proposed repairs are not implemented (the product is read-only for this uplift). Index and counts: [findings register](findings.md).

<a id="bug-001"></a>
### Two redactions of different targets can run at once, and each one's audit and receipt then describes the other's work

Severity: High · Decision: Open

Run: Uplift 2026-11-13

Also recorded as: F-1303 (playbook arm, S1, reproduced-live; [13.json](../../experiment/playbook-completion/findings/audit/13.json)). (crosswalk)

Found by: [witness_concurrent_targets_break_the_marker](results/ledger_redaction/20261114T044401Z-prove/receipt.json) in [redaction.rs](models/ledger_redaction/redaction.rs) (Variant serial: false): the marker names target A while run B writes tombstones; B's final step removes the marker while A is unfinished and a commit into A is then admitted. [witness_race_then_resume_loses_attribution](results/ledger_redaction/20261114T044401Z-prove/receipt.json) is a classification fact, not a trace of the lifecycle model (review R1-core R1-1; round2-core R2-2): with the knowledge another target's final step removes, `Matches` answers Unknown for A's remaining qualifier records.

Reproduced by: [redaction_concurrent_targets](receipts/native/redaction_concurrent_targets.json) (final, hash-stamped run) — while an ordinary long commit held the head lock, `redact(None, prefix="tA")` and `redact(None, prefix="tB")` both passed their entry checks. B completed: its single redaction revision (seq 6, target digest of `tB|`) names revisions 2 (tenant A's) and 3, and its receipt reports 20 records tombstoned, 2 revisions' metadata cleared and 2 idempotency keys removed, tenant A's included. B's final step removed the marker while A was still running, and a commit into A's target was then accepted (seq 7). A went on to tombstone that commit's records and ended with `RedactionTargetLiveError` (the late commit made `tA|` content live), leaving its own marker in place. The model witness's mid-run commit window was hit natively.

Expected: ADR-0013 "A redaction of a different target is refused until the first one finishes"; spec 256 Decision 1 (Tom, 2026-10-22): the redaction revision names *the* redacted revisions; Decision 3: while a redaction runs, nothing may be written into its target.

Observed: `LedgerRedact.Redact` compares the marker before taking any lock (LedgerRedact.cls:202-205); the marker is written lazily by the first batch that finds a match (:322-324) and never compared by `BatchInLock` or `FinalInLock`; the counters and redacted-revision list under `^IVG.Ledger("redacting")` are shared by every run (:343-344, :423-428); `FinalInLock` kills the marker whoever owns it (:439).

Consequence: an audit trail that names the wrong tenant's revisions and a receipt that reports the other tenant's work as its own; a window, observed natively, in which a commit into the unfinished target is admitted, after which the run tombstones that commit's records while their content is live, ends refused, and leaves its marker blocking readers, verify and every other target until the content is erased again. The two-call tenant recipe (`redact(graph)` + `redact(None, prefix=)`) invites running both at once. By code reading (`FinalInLock` kills the whole `("redacting")` subtree, whoever owns the marker) and that classification fact, B's final step also removes the statement endpoints A's earlier calls learned, so a resumed prefix run of A can leave its remaining qualifier records in clear under a `complete` receipt. That knowledge loss was not observed natively (the native race showed the commit-admission consequence); a single paused and resumed prefix run without the race attributes correctly ([redaction_prefix_resume](receipts/native/redaction_prefix_resume.json)).

Repair proposal (not implemented): [simp-001](design_simplification.md#simp-001). Governing statements: [redaction.batches.competing](../ontology/features/redaction.g5.md#redaction.batches.competing), [redaction.audit](../ontology/features/redaction.g5.md#redaction.audit).

<a id="bug-002"></a>
### A redaction completes while its target's content is still uncommitted-deleted, and the caller's rollback brings the content back with its history tombstoned

Severity: High · Decision: Open

Run: Uplift 2026-11-13

Also recorded as: F-C1201 (playbook arm, S1, reproduced-live; [12.json](../../experiment/playbook-completion/findings/audit/12.json)); F-C1301 (playbook arm, S1, reproduced-live; [13.json](../../experiment/playbook-completion/findings/audit/13.json)). (crosswalk)

Found by: source review (`LiveRows` reads without locks and the Eraser takes no ledger lock; `aad50087` makes `erase_graph` nest in the caller's transaction on a plain connection) and the native probe below (review R1-core R1-12).

Reproduced by: [erasure_caller_transaction](receipts/native/erasure_caller_transaction_redaction.json) — connection 1: `START TRANSACTION`; `erase_graph("gA")` (nested, `$TLEVEL=1`); connection 2: `redact("gA")` completed with 2 tombstones; connection 1: `ROLLBACK`. Afterwards gA has 1 live edge row, its create records are tombstones, and `verify()` reports `diverges`.

Expected: ADR-0013 "Redaction only follows erasure. It is refused while any row of the target is live"; CONTEXT.md "Erasure either completes or leaves the graph untouched".

Observed: `LedgerRedact.LiveRows` (LedgerRedact.cls:149-178) counts rows with `%SQL.Statement` at the process default isolation and sees the uncommitted deletes as gone; nothing serialises erasure with redaction.

Consequence: the history of content that is live again is destroyed; verify never returns to equal for it.

Repair proposal (not implemented): read liveness under the same lock or isolation that erasure commits under (e.g. take the ledger head lock in the eraser, or a target lock shared by erase and redact), or refuse redaction while an erase of the target is uncommitted. Open contract: [q-004](open_questions.md#q-004). Governing statement: [redaction.after-erasure](../ontology/features/redaction.g5.md#redaction.after-erasure).

<a id="bug-str-001"></a>
### Deleting one of several parallel edges through the ledger removes the adjacency of the edges that remain

Severity: High · Decision: Open

Run: Uplift 2026-11-13

Found by: [witness_ledger_delete_rel_drops_survivor_indexed and witness_ledger_delete_rel_drops_survivors_non_indexed](results/graph_structure/20261114T000451Z-prove/receipt.json) in [graph_structure.rs](models/graph_structure/graph_structure.rs) (B-structure O5/F3; control `as-built-delete-rel-without-line-689` attributes the witness to line 689); A-structure F3 and S4 ([intent](../uplift/ivg-verus-initial/intent/graph-structure.md)); A-ops hazard (a)6 ([operations](../uplift/ivg-verus-initial/intent/operations.md)); review R2-data R1-2.

Reproduced by: [graph_structure_parallel_delete_rel](receipts/native/graph_structure_parallel_delete_rel.json) — in the default graph and in a named graph of an indexed namespace, two parallel `s-p-o` edges, ledger `delete_relationship` of one: before, 2 rows, children `[0,1]`, `#` = 2, degree 2; after, one row remains, but the index has no entry for the triple and the degree and a recount read 0 (expected: a bare leaf and degree 1), while Cypher `MATCH` still returns the neighbour through the SQL row.

Expected: every row change moves `out`/`in` in the same transaction and no row is left without adjacency (spec 252 FR-001/FR-016); the multigraph layout keeps one leaf while one edge remains and degree counts live edges (spec 234 FR-003/FR-004; CONTEXT.md:90-95, 103-107).

Observed: `LedgerApply.DeleteRelInternal` deletes the chosen row by `%ID` (`LedgerApply.cls:678`); in an indexed namespace the row's functional-index callback (`RemoveKeyed`) already collapses the triple to the survivor's bare leaf, and then `If $Data(^KG("out",...)) Do Adjacency.Remove(...)` (`LedgerApply.cls:688-689`) kills that leaf and any children. Line 689 predates spec 252 (`fa67b2b3`) and lacks the `Indexed()` guard that `OpCreateRel` has (`LedgerApply.cls:508`). In a non-indexed namespace line 689 alone removes every parallel edge's entry.

Consequence: the surviving relationships are invisible to traversal, native Cypher and degree until `sync()` or a rebuild; reachable whenever the ledger is enabled in non-strict mode on a multigraph graph (parallel edges come from Cypher `CREATE`).

Repair proposal (not implemented): skip line 689 when `Adjacency.Indexed()`, and in a non-indexed multigraph call `RemoveKeyed` with the deleted row's `ekey` (proved: `theorem_repaired_delete_rel_keeps_layout`; single-edge deletes unchanged, `witness_ledger_delete_rel_single_edge_is_right`). Related decision: [q-str-004](open_questions.md#q-str-004). Governing statements: [structure.multigraph.layout](../ontology/features/graph-structure.g5.md#structure.multigraph.layout), [structure.multigraph.count](../ontology/features/graph-structure.g5.md#structure.multigraph.count).

<a id="bug-str-002"></a>
### A cached algorithm answer computed over a write that later rolls back stays current

Severity: High · Decision: Open

Run: Uplift 2026-11-13

Also recorded as: F-0402 (playbook arm, S2, reproduced-live; [04.json](../../experiment/playbook-completion/findings/audit/04.json)). Severity differs: here High, playbook S2; both are kept. (crosswalk)

Found by: [witness_rolled_back_write_poisons_algo_cache](results/graph_structure/20261114T000451Z-prove/receipt.json) in [graph_structure.rs](models/graph_structure/graph_structure.rs) (B-structure O4/F1; repair `theorem_repaired_algo_cache_sound` with `witness_bump_after_rollback_refuses_the_poison`); A-structure F1 and S2; A-platform F-A1 ([intent](../uplift/ivg-verus-initial/intent/platform.md)); A-ops hazard (c)7; review R2-data R1-3.

Reproduced by: [graph_structure_algo_cache_rollback](receipts/native/graph_structure_algo_cache_rollback.json) — connection 1 opens a transaction and adds edge `c→a` (token 655000→655001); connection 2 computes WCC (miss, put) and sees `c` joined to `a`; connection 1 rolls back (no `c→a` row); connection 3's WCC is a cache hit at token 655001 and still joins `c` to `a`.

Expected: a cached result is valid only while the token it was computed under is current, and a reader caching an uncommitted edge that then rolls back is the unsafe case (CONTEXT.md:118-119; ADR-0012:23-26; spec 236 Story 4; the token audit's fix 3, which bumps after `TRollback` in `BuildKG` for this reason).

Observed: writers bump `^KG("__version")` inside their transaction (`Adjacency.cls:92`) and `$Increment` is not rolled back; `_cached_algorithm` reads the token and stores the answer with no writer-lock probe (`iris_sql_store.py:958-981`; `AlgoCache.cls:27-51`); no rollback path bumps the token (`_write_txn.py:234-253`; `Txn.cls:49-58`; Eraser catches at `Eraser.cls:260, 459, 630`).

Consequence: PageRank, PPR, WCC and CDLP answers include an edge that never committed and are served as current until the next adjacency write anywhere in the namespace. Severity is High because the answer served is wrong, not merely stale, it is served as current, and the native run reaches it with ordinary public calls; on a quiet analytic namespace it can persist for a long time (review round2-domains R2-6 asked for this reason).

Repair proposal (not implemented): bump the token after every rollback, as `BuildKG` does (proved for the model, but a rollback IRIS performs for a dead process does not bump), or give the cache the degree cache's discipline: probe `^IVG.AdjW` exclusively with no wait before computing and refuse to store if the probe failed or `^IVG.AdjNoLock` is set. Governing statements: [structure.rebuilt.valid](../ontology/features/graph-structure.g5.md#structure.rebuilt.valid), [structure.rebuilt.rollback](../ontology/features/graph-structure.g5.md#structure.rebuilt.rollback), [algorithms.cache.concurrency](../ontology/features/algorithms.g5.md#algorithms.cache.concurrency).

<a id="bug-tmp-001"></a>
### A temporal write whose structural step fails keeps its raw entry, cannot be finished by a retry, and the bulk fallback reports it written

Severity: High · Decision: Open

Run: Uplift 2026-11-13

Found by: [witness_partial_write_is_not_repaired_by_retry and witness_bulk_fallback_reports_success](results/temporal/20261114T001508Z-prove/receipt.json) in [temporal.rs](models/temporal/temporal.rs) (B-temporal O1/F2; valid outcome `witness_assert_first_repairs_the_retry`); A-temporal F2, S2, S3 ([intent](../uplift/ivg-verus-initial/intent/temporal.md)); reconstruction check gap G32; review R2-data R1-6.

Reproduced by: [temporal_write_modes](receipts/native/temporal_write_modes.json) — `bulk_fallback_insert`: an insert batch with one edge whose endpoint ID IRIS refuses (over 256 characters) returned `written=2, collisions=0` and no error, while the store holds one structural row and the statistics disagree with the raw edges; `bulk_fallback_update`: after the fallback the whole-bucket count/sum/velocity are 2/2.0/4 against the raw store's 2/6.0/2. `partial_write_retry`: a single-edge write refused at its structural step left 1 raw edge and bucket 1 with no statistics, and the insert retry returned without error and wrote nothing more.

Expected: a temporal edge implies its structural edge (ADR-0009); a refused write "writes nothing" (`create_edge_temporal` docstring, `temporal.py:260-261`); first-write-wins with counts that match the raw store (spec 254 FR-003); a failed bulk write reports the count written (R203).

Observed: `TemporalIndex.WriteStores` writes `tout`, `tlast`, `tin` and `$Increment(bucket)` before `AssertTemporalRow`, with no transaction (`TemporalIndex.cls:95-111`; `temporal.py:12-17` admits the residue); a throw leaves no row, aggregate or attributes, and an insert-mode retry then hits `$Data(tout)` and is a silent collision (`TemporalIndex.cls:84-85`; `InsertEdge` answers 1 for every outcome, `:64`). `bulk_write_temporal_edges` catches the batch failure and re-sends every edge one by one (`iris_sql_store.py:2759-2786`), counting each collision as inserted; in update mode it re-increments the statistics of edges already written.

Consequence: a caller is told every edge was written while one has no structural edge, statistics or attributes, and no retry can complete it; windowed statistics disagree with the raw store.

Repair proposal (not implemented): run the structural step before the first Set in `WriteStores`, or wrap `WriteStores` in its own `TSTART`/`TROLLBACK 1`; make the bulk fallback raise, or re-send only the edges not yet written. Open choice: [temporal.write.partial-failure](../ontology/features/temporal.g5.md#temporal.write.partial-failure). Governing statements: [temporal.write](../ontology/features/temporal.g5.md#temporal.write), [temporal.structural](../ontology/features/temporal.g5.md#temporal.structural).

<a id="bug-tmp-002"></a>
### An update at an occupied temporal coordinate counts the edge twice in the statistics

Severity: High · Decision: Open

Run: Uplift 2026-11-13

Also recorded as: F-0501 (playbook arm, S2, reproduced-live; [05.json](../../experiment/playbook-completion/findings/audit/05.json)). Severity differs: here High, playbook S2; both are kept. (crosswalk)

Found by: [witness_update_double_counts](results/temporal/20261114T001508Z-prove/receipt.json) in [temporal.rs](models/temporal/temporal.rs) (B-temporal O1/F1; Q1 option (b) proved consistent by `theorem_stats_repaired_total`); A-temporal F1; A-ops candidate finding and test gap (d) (`test_254_collisions_e2e.py:104-110` asserts no aggregate after an update); review R2-data R1-6.

Reproduced by: [temporal_write_modes](receipts/native/temporal_write_modes.json) case `update_double_count` — after an insert and an update of one coordinate, one raw edge (w=9) but the whole-bucket count=2, sum=11.0, velocity=2 (the raw-exact reading expects 1/9.0/1, the docstring 1/2.0); `bulk_fallback_update` shows the same inflation through the bulk path.

Expected: the statistics after an update "remain based on the original value" (`temporal.py:273-279`; `TemporalIndex.cls:77-79`; CHANGELOG 4669-4670 and 4914-4915 "tagg not adjusted"); under the raw-exact reading they equal the surviving raw edges. The model shows the as-built result breaks both readings.

Observed: with `pMode="update"` `WriteStores` has no early return (`TemporalIndex.cls:82-86`) and runs `$Increment(bucket)` (`:102`) and the count and sum increments (`:117-118`), widening min/max; a later delete rebuilds `tagg` but decrements `bucket` by one only (`:357`). The ledger's `create_temporal_edge` defaults to "update" (`LedgerApply.cls:628`).

Consequence: insert w=2 then update w=9 gives count 2, sum 11, bucket 2 for one raw edge; a window aligned to the bucket and one that cuts it answer differently; after the delete the bucket counts an edge that no longer exists.

Repair proposal (not implemented): on an update, rebuild the bucket's statistics from the raw edges (as delete does) and leave `bucket` alone. Open choice: [temporal.write.update-statistics](../ontology/features/temporal.g5.md#temporal.write.update-statistics). Governing statement: [temporal.stats](../ontology/features/temporal.g5.md#temporal.stats).

<a id="bug-tmp-003"></a>
### A rolled-back temporal write leaves its statistics counted, so a retry counts the edge twice

Severity: High · Decision: Open

Run: Uplift 2026-11-13

Found by: [witness_refused_changeset_leaves_counts, witness_blocked_changeset_leaves_counts, witness_throw_in_changeset_leaves_bucket, witness_caller_rollback_leaves_counts and witness_caller_rollback_of_ledger_commit_leaves_counts](results/temporal/20261114T001508Z-prove/receipt.json) in [temporal.rs](models/temporal/temporal.rs) (B-temporal O6/F3, with `lemma_refused_commit_restores_journaled`); A-temporal F3.

Reproduced by: [temporal_rollback_counters](receipts/native/temporal_rollback_counters.json) — R1 a refused changeset: no raw edge, but the whole-bucket count=1, sum=2.0, velocity=1, and the retry leaves one raw edge with count=2, sum=4.0, velocity=2; R2 a caller's rollback of a ledger commit and R3 of a direct `create_edge_temporal`: no raw edge, count=1; R4 a throw inside a changeset: velocity=1 with no edge.

Expected: if a changeset fails, none of its temporal writes may remain, statistics included (spec 224 "atomically with all structural ops", `changeset.py:321-336`; ledger FR-047, a revision exists iff its mutations are visible); USER_GUIDE "Writes inside your transaction" says a caller's rollback removes both and leaves only the version token and generations (`USER_GUIDE.md:236-275`).

Observed: `WriteStores` counts with `$Increment` (`TemporalIndex.cls:102, 117-118`), which IRIS does not undo on `TROLLBACK` (ADR-0010 "Context"), while the raw stores are journaled Sets and are undone.

Consequence: windowed counts, sums and velocity include edges that do not exist, and every retry of a failed changeset inflates them further, with no error.

Repair proposal (not implemented): replace the statistics `$Increment`s with journaled `Set x=$Get(x)+1` (which needs a lock against concurrent writers, see [q-tmp-001](open_questions.md#q-tmp-001)), or rebuild the bucket's statistics from the raw store after a rollback; at minimum list the statistics in the USER_GUIDE's rollback residue. Model comparison: `witness_counters_undone_keep_exact` (counters undone keep the rule). Governing statements: [temporal.ledger.atomic](../ontology/features/temporal.g5.md#temporal.ledger.atomic), [temporal.stats](../ontology/features/temporal.g5.md#temporal.stats).

<a id="bug-tmp-010"></a>
### A rolled-back temporal delete or node erase leaves the bucket's event counter decremented

Severity: High · Decision: Open

Run: Uplift 2026-11-13

Found by: [witness_rolled_back_delete_undercounts](results/temporal/20261114T001508Z-prove/receipt.json) in [temporal.rs](models/temporal/temporal.rs) (valid outcome `witness_rolled_back_delete_exact_if_counters_undone`); review R2-data R1-9 (the mirror of [bug-tmp-003](#bug-tmp-003)).

Reproduced by: [temporal_rollback_counters](receipts/native/temporal_rollback_counters.json) — R5, a caller's rolled-back delete of the only edge: the raw edge is back with whole-bucket count 1 and sum 2.0, but velocity 0 and the raw bucket 0 (expected 1/2.0/1); R5b, one of two edges: velocity 1 and bucket 1 (expected 2); R6, a rolled-back node erasure: velocity 0 and bucket 0 (expected 1).

Expected: node erasure keeps the remaining statistics exact and runs inside the erasure's transaction; a failed or rolled-back erase leaves the content untouched (ADR-0004; CONTEXT.md "Erasure"); "if a changeset fails, none of its temporal writes may remain, statistics included".

Observed: `RemoveTemporalRow` decrements the bucket with `$Increment(bucket,-1)` (`TemporalIndex.cls:357`), which a `TROLLBACK` does not undo, while its Kill at zero is journaled and restored; since 4.6.4 `delete_edge_temporal` and `delete_node` (→ `TemporalIndex.EraseNodes`) nest in a caller's transaction.

Consequence: after a caller rolls back a delete or a node erase, velocity and bucket counts under-count events that still exist. The bucket node is left holding 0 instead of being killed, and `FindBursts` lists every source present in a bucket, so with a threshold of 0 or less it reports a velocity-0 burst (`TemporalIndex.cls:355-357, 784-803`; review round2-domains R2-4).

Repair proposal (not implemented): the same as [bug-tmp-003](#bug-tmp-003): journaled updates of the counters, or a rebuild of the bucket after a rollback. Governing statements: [temporal.erase](../ontology/features/temporal.g5.md#temporal.erase), [temporal.delete](../ontology/features/temporal.g5.md#temporal.delete).

<a id="bug-srch-001"></a>
### Search indexes keep answering with content that was erased, and a re-created node inherits the erased text

Severity: High · Decision: Open

Run: Uplift 2026-11-13

Found by: [witness_erase_leaves_bm25](results/search/20261114T000543Z-prove/receipt.json) in [search.rs](models/search/search.rs) (B-search O5/F1; repair `theorem_repaired_erase_removes_answers`); A-search F1 and S2 ([intent](../uplift/ivg-verus-initial/intent/search.md)); A-ops hazard (a)3; reconstruction check 2(b)12 and correction 6; review R3-platform R1-7.

Reproduced by: [search_bm25_erase](receipts/native/search_bm25_erase.json) — a BM25 index built for graph `g5probe_bm25_erase` over one node; `erase_graph` removed the node, yet `bm25_search` still answered `g5p:erase:1` (score 0.288); after the node was re-created with other text, the erased text still scored it.

Expected: an erase removes graph content "from every store that holds it" (ADR-0004:10-12, 79-80); `GraphStores.cls:1-16` claims to be the one inventory; `^IVG.AlgoCache` is erased because "no answer outlives erased content" (`GraphStores.cls:113-116`); the Eraser's own reason for erasing `docs` is that text otherwise attaches to whoever re-creates the ID (`Eraser.cls:138-144`).

Observed: `^BM25Idx`, `^IVF`, `^PLAID` and `^VecIdx` are in neither inventory list and no erase or delete path touches them (no reference in `Eraser.cls`; `index_protocol.py:41` is the only `bm25_insert` caller). A BM25 index records its graph (`cfg graph`, `BM25Index.cls:168`), and fusion prefers the index recorded for the graph (`vector.py:204-206`).

Consequence: erased or deleted content stays retrievable through BM25, fusion and the vector indexes until a rebuild, and a node re-created under an erased ID is ranked by the erased text.

Repair proposal (not implemented): let `EraseGraph` drop or empty the BM25 indexes whose `cfg graph` is the erased graph, and list `^IVF`, `^PLAID` and `^VecIdx` in the inventory as unscoped derived stores to rebuild after an erase (proved for BM25 with a frame clause: other graphs' indexes unchanged). The rule is decided for erasure by CONTEXT.md "Erasure", ADR-0004 and ADR-0013 ("cover everything IVG can reach"); upkeep after ordinary node deletes stays the caller's (`bm25_insert`/`bm25_delete`, USER_GUIDE). A replacing restore has the same gap ([bug-plt-024](#bug-plt-024)). Governing statements: [search.erasure.indexes](../ontology/features/search.g5.md#search.erasure.indexes), [erasure.scope](../ontology/features/erasure.g5.md#erasure.scope), [search.erasure](../ontology/features/search.g5.md#search.erasure).

<a id="bug-srch-002"></a>
### A failed BM25 insert or delete rolls back the caller's whole transaction

Severity: High · Decision: Open

Run: Uplift 2026-11-13

Also recorded as: F-C0702 (playbook arm, S1, reproduced-live; [07.json](../../experiment/playbook-completion/findings/audit/07.json)). (crosswalk)

Found by: A-search F3 and S3 ([intent](../uplift/ivg-verus-initial/intent/search.md)); B-search S-c and `witness_caller_txn_rollback` (W-O1d) in [search.rs](models/search/search.rs), whose lost-update branch needs premise P_unlock_in_txn ([prove receipt](results/search/20261114T000543Z-prove/receipt.json)); review R3-platform R1-2.

Reproduced by: [search_bm25_caller_txn_rollback](receipts/native/search_bm25_caller_txn_rollback.json) — on an engine over a plain DB-API connection, the caller opened a transaction, created a node, then called `bm25_insert` with a document whose ID is too long for a subscript; the insert raised `<SUBSCRIPT>` and `$TLEVEL` went from 1 to 0, and after the caller's commit its node is gone. [search_bm25_caller_txn_lock](receipts/native/search_bm25_caller_txn_lock.json) showed IRIS keeps the index lock until the caller's transaction ends, so W-O1d's lost-update trace (which assumes the lock is released at the inner `TCommit`) is not reachable; the finding rests on the rollback alone.

Expected: an IVG write that fails takes back only its own part; the caller's commit or rollback decides the rest (`_write_txn.py` 4.6.4 docstring; the Eraser's `While $TLevel > tTxnLevel { TROLLBACK 1 }`); a failed index write leaves the index as it was (ADR-0007).

Observed: the Insert and Delete catch blocks run `If $TLevel > 0 TRollback` (`BM25Index.cls:487, 508`), which rolls back every level; the under-lock `RequireWritable` refusal (`BM25Index.cls:459`) throws before `TStart` and also lands there.

Consequence: a caller that handles the indexing error and commits silently loses every write it made earlier in its transaction.

Repair proposal (not implemented): roll back to the entry level only (`TROLLBACK 1` while `$TLevel` exceeds the level found on entry), as the Eraser does. Governing statements: [structure.write](../ontology/features/graph-structure.g5.md#structure.write), [search.bm25.write_lock](../ontology/features/search.g5.md#search.bm25.write_lock).

<a id="bug-srch-007"></a>
### Claiming the default embedding table for a model that already has a default-graph route makes that model's stored vectors unreadable

Severity: High · Decision: Open

Run: Uplift 2026-11-13

Found by: [witness_claim_after_route_splits_pair](results/search/20261114T000543Z-prove/receipt.json) in [search.rs](models/search/search.rs) (B-search O3/F9, W-O3c); A-search F9 and S5.

Reproduced by: [search_route_split](receipts/native/search_route_split.json) — a declared model stored a default-graph vector while `kg_NodeEmbeddings` was unclaimed (its own `kg_emb_…` route was created); after `kg_NodeEmbeddings` was claimed for the same model, two registry rows answer `('', model)` and `get_embedding` returns nothing although the vector is still in the `kg_emb_…` table.

Expected: one route per (graph, model) pair; a graph's vectors are never split across two tables (FR-011 as quoted at `embeddings.py:270-273`); every reader of a pair reads where its writer stored.

Observed: the registry has no uniqueness on `(graph_id, model_key, kind)` (`schema.py:143-160`); `set_embedding_identity`/`initialize_schema` claim `kg_NodeEmbeddings` without moving an existing route (`schema.py:1177-1215, 1512`), and `_read_route`'s preference then picks `kg_NodeEmbeddings` (`embeddings.py:455`; `_route_preference` `:107-118`).

Consequence: vectors stored before the claim disappear from reads and search for that model, and undeclared vectors already in the legacy table are read as the model's.

Repair proposal (not implemented): enforce uniqueness of `(graph_id, COALESCE(model_key,''), kind)`, or migrate the existing route when the legacy table is claimed (or refuse the claim while a route for the pair exists), so `_route_preference` stops being load-bearing. Governing statements: [search.routes](../ontology/features/search.g5.md#search.routes), [search.embedding.claim](../ontology/features/search.g5.md#search.embedding.claim).

<a id="bug-plt-001"></a>
### The 4.0.0 documents migration can drop the documents table after its copy failed with a tolerated error

Severity: High · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** No run has produced a copy failure whose message matches the tolerated list; the control flow is read from source (`docs_and_edge_vectors.py:89-97, 647-657` re-read for this entry). Severity is lowered one level from Critical (data loss) for the unconfirmed trigger.

Found by: A-platform F-S7 ([intent](../uplift/ivg-verus-initial/intent/platform.md)).

Reproduced by: none

Expected: the 3.2.0→4.0.0 steps are re-runnable and delete nothing that was not moved first (spec obligation O-MIGRATE; the step order exists because "each step reads what the one before it wrote").

Observed: `_run_tolerantly` treats any error whose text contains `already`, `not unique`, `-201`, `not found`, `does not exist`, `-30>` or `-315` as work a previous pass already did and continues (`docs_and_edge_vectors.py:89-97, 647-657`). `DOCS_FINISH` runs `docs_copy_placed` (`INSERT … SELECT` into the staging table), then `docs_drop_original` (`DROP TABLE docs`) and the rename (`statements.py:102-115, 257-264`). A copy failing with, for example, a unique-constraint (`not unique`) or a "field not found" error is skipped and the source table is dropped.

Consequence: documents that were never copied are deleted irreversibly during an upgrade.

Repair proposal (not implemented): tolerate errors per statement name (only `docs_staging_create` may meet "already exists"; the copy may never be tolerated), or verify the staging row count before the drop. Governing statements: [install.migration.steps](../ontology/concepts/install.g5.md#install.migration.steps), [install.migration](../ontology/concepts/install.g5.md#install.migration).

<a id="bug-cyp-001"></a>
### A caller with Cypher read access can forge a CRC-32 collision so that another shape's queries run its compiled code

Severity: High · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Proved on the model (collisions exist by `lemma_crc_collision_exists`); not probed natively because forcing a collision of real shapes needs a test hook or a crafted shape. Severity is lowered one level from Critical (an integrity breach other users cannot see) for the unconfirmed trigger.

Found by: [witness_collision_swaps_the_class_mid_run and witness_collision_leaves_another_shapes_code_under_an_ok_entry](results/platform/20261114T002651Z-prove/receipt.json) in [platform.rs](models/platform/platform.rs) (B-platform P1, W-O2a, W-O2b); A-cypher F2; review R3-platform R1-3, whose scratch check Adv-2 (`$RUN_DIR/agents/R3-platform/adv/adv2_platform_pshape*.log`) shows that requiring the entry's shape in `Build` closes W-O2b but not W-O2a, and that only unique class names remove the dependency on P-NO-COLLISION.

Reproduced by: none

Expected: a compiled class answers exactly as the interpreter does, and a stale entry is never run (ADR-0014:16-23; spec 257 US1).

Observed: the class name is `IVGC.P<$ZCRC(shape,7)>` (`Gen.cls:69, 183`). `For` detects a colliding shape by its stored shape (`:71`) and rebuilds the same class name for the new shape (`:80-101, 183-207`); `Build` checks the lines' digest but not that the entry's shape is the one the lines were written for (`:177-207`); `RunA` checks the entry once per run (`Exec.cls:158`) and calls `Walk1` per anchor (`:199, 258`). W-O2b needs no run overlap: two first runs of colliding shapes in job mode leave b's entry marked ok over a's code until a deploy or stamp change.

Consequence: wrong Cypher answers for every later run of the victim shape, until a deploy or stamp change. Accidental collisions are rare (about 1.2×10⁻⁴ for 10³ distinct shapes between deploys, 1.2% for 10⁴, mostly as recompile thrash), but adversarially the attack is practical: CRC-32 is affine, four free bytes in a label or property name hit any target, the shape text can be reproduced from the open-source planner, and the attacker can run both shapes until the W-O2b ordering lands. Reads write compiled plans, so this needs only Cypher read access through a server whose IRIS login can write `^IVG.CypherCompiled`, including an `IVG_READ_ONLY` server on the default `_SYSTEM` login. `query.compiled.integrity` and `query.compiled.never-stale` hold only under P-NO-COLLISION, which nothing establishes.

Repair proposal (not implemented): [simp-cyp-001](design_simplification.md#simp-cyp-001). Governing statements: [query.compiled.integrity](../ontology/features/cypher.g5.md#query.compiled.integrity), [query.compiled.never-stale](../ontology/features/cypher.g5.md#query.compiled.never-stale), [query.compiled.equal-answers](../ontology/features/cypher.g5.md#query.compiled.equal-answers).

<a id="F-0304"></a>
### Storing an edge over a marked edge does not take the edge over

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [03.json](../../experiment/playbook-completion/findings/audit/03.json) (live `breadth-a-live-05-temporal`; mc `breadth-a-mc-tmp_mark-as-built`; mc `breadth-a-mc-tmp_mark-reviewed`; control `breadth-a-control-tmp_mark`; live `ws-live-ba-explicit-survives`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-05-temporal`, `ws-live-ba-explicit-survives`

- Expected: ADR-0009 (CONTEXT.md:66-73) and HD-0302 (supported): an explicit structural create clears the temporal mark; a temporal-backed row must not delete an explicitly written edge.
- Observed at the pin: create_edge's edge survives (control), store_edge's edge is deleted
- Source severity S1, confidence high; module 03; governing page here: `structure. / install.bulk_load`.
- Remedy proposed by the playbook arm (not implemented): Run the adopt step after store_edge's swallowed duplicate.
- Reviewed-design control: `playbook-proofs-d1c` `control_f0304_store_no_adopt` fails where expected in this run ([receipt](results/playbook-proofs-d1c/20261115T035820Z-control_f0304_store_no_adopt/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1c/20261115T035754Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0409"></a>
### A failed adjacency rebuild inside a caller's transaction rolls back the caller's work

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [04.json](../../experiment/playbook-completion/findings/audit/04.json) (live `breadth-a-live-04-adjacency`; mc `breadth-a-mc-adj_rebuild_txn-as-built`; mc `breadth-a-mc-adj_rebuild_txn-reviewed`; control `breadth-a-control-adj_rebuild_txn`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-04-adjacency`

- Expected: CHANGELOG 4.6.4 (CHANGELOG.md:410-424): an IVG write never commits or rolls back a transaction its caller opened.
- Observed at the pin: failed sync ended the caller's transaction and discarded its node
- Source severity S1, confidence high; module 04; governing page here: `structure.`.
- Remedy proposed by the playbook arm (not implemented): Roll back to the level found, or refuse sync() inside a caller transaction.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0505"></a>
### The marker test differs between the deleters and the ledger

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [05.json](../../experiment/playbook-completion/findings/audit/05.json) (live `breadth-a-live-05-temporal`; mc `breadth-a-mc-tmp_mark-as-built`; mc `breadth-a-mc-tmp_mark-reviewed`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-05-temporal`

- Expected: ADR-0009 / HD-0302: an explicitly written edge (no JSON-true mark) survives the temporal side; LedgerGenesis treats temporal 1 as an ordinary qualifier (LedgerGenesis.cls:62-75).
- Observed at the pin: explicit edge with temporal:1 deleted by the temporal delete
- Source severity S1, confidence high; module 05; governing page here: `temporal.`.
- Remedy proposed by the playbook arm (not implemented): One shared predicate (JSON boolean true).
- Reviewed-design control: `playbook-proofs-d1c` `control_f0505_marker_predicate` fails where expected in this run ([receipt](results/playbook-proofs-d1c/20261115T035822Z-control_f0505_marker_predicate/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1c/20261115T035754Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0606"></a>
### Erasure leaves IVF, tree and PLAID indexes holding an erased graph's ids and vectors

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [06.json](../../experiment/playbook-completion/findings/audit/06.json) (live `breadth-a-live-06-vectors`; mc `breadth-a-mc-vec_ivf-as-built`; mc `breadth-a-mc-vec_ivf-reviewed`; control `breadth-a-control-vec_ivf`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-06-vectors`

- Expected: HD-0601 (assumption): retained vector-index contents are observable after erasure unless purged; graph-owned indexes must be invalidated or deleted. docs/migration/v4.0.0.md:742-750 names IVF a gap.
- Observed at the pin: IVF still answers 3 erased ids
- Source severity S1, confidence high; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Prune or invalidate graph-owned indexes in the erase; record the graph with the index.
- Reviewed-design control: `playbook-proofs-d1b` `control_f0606_erase_keeps_ivf` fails where expected in this run ([receipt](results/playbook-proofs-d1b/20261115T035745Z-control_f0606_erase_keeps_ivf/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1b/20261115T035711Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0702"></a>
### Erasure leaves BM25 indexes holding an erased graph's terms and node ids

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [07.json](../../experiment/playbook-completion/findings/audit/07.json) (live `b-07-f0702-f0703`; inspected `iris_src/src/Graph/KG/Eraser.cls:138-147`; inspected `iris_src/src/Graph/KG/GraphStores.cls:26-133`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-07-f0702-f0703`

- Expected: CONTEXT.md:198-208 (erasure removes content from every store that holds it); ADR-0004; Graph.KG.GraphStores comment 'no answer outlives erased content' (iris_src/src/Graph/KG/GraphStores.cls:112-115); TXT-I8.
- Observed at the pin: Live (b-07-f0702-f0703): after erase_graph('b07g2') (0 node rows left; journal footprint ^KG, ^NKG, docs, nodes, rdf_labels, rdf_props, no ^BM25Idx), bm25_search on the index built for b07g2 still answers both erased node ids with their scores and the term stays in df; Info unchanged.
- Source severity S1, confidence high; module 07; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): List ^BM25Idx in GraphStores.Inventory scoped by its recorded graph and drop or prune every index built for the erased graph inside the erase (decisions.md HD-0601 style ownership for graph-owned derived stores).
- Reviewed-design control: `playbook-proofs-d1d` `control_f0702_erase_keeps_index` fails where expected in this run ([receipt](results/playbook-proofs-d1d/20261115T035647Z-control_f0702_erase_keeps_index/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0705"></a>
### An index with no recorded graph is read as the default graph's own index

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [07.json](../../experiment/playbook-completion/findings/audit/07.json) (live `b-07-f0705-f0707`; live `b-07-fp-writers`; mc `m07-leg-as-built-fusion-unknown`; mc `m07-leg-as-built-label`; mc `m07-leg-reviewed`; inspected `iris_src/src/Graph/KG/BM25Index.cls:608-612`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-07-f0705-f0707`, `b-07-fp-writers`, `rx-dec-live-07`

- Expected: TXT-B8.3 (an index whose graph is not known is never taken as the default graph's own index); decisions.md HD-0703 (never consult another graph's index); CONTEXT.md:27-43 (graph isolation).
- Observed at the pin: Live (b-07-f0705-f0707): an index created by bm25_insert has no cfg graph subscript; Info answers graph ''; a fresh engine's _index_graph answers ''; default-graph kg_RRF_FUSE answered node b07_n3, which exists only in graph b07g3; Cypher ivg.bm25.search without USE GRAPH labels its row graph_id ''. Model m07-leg-as-built-fusion-unknown / -label; reviewed passes.
- Source severity S1, confidence high; module 07; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Info answers graph null when the subscript is absent; Insert records the graph (or refuses to create an index); _index_graph treats null as unknown.
- Reviewed-design control: `playbook-proofs-d1d` `control_f0705_absent_graph_is_default` fails where expected in this run ([receipt](results/playbook-proofs-d1d/20261115T035644Z-control_f0705_absent_graph_is_default/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0707"></a>
### Under USE GRAPH, BM25 calls do not check that the index was built for that graph

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [07.json](../../experiment/playbook-completion/findings/audit/07.json) (live `b-07-f0705-f0707`; mc `m07-leg-as-built-scope`; mc `m07-leg-reviewed`; mc `m07-leg-control-no-scope-check`; inspected `iris_vector_graph/cypher/translator.py:3133-3134`; inspected `iris_vector_graph/cypher/translator.py:3283-3292`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-07-f0705-f0707`

- Expected: TXT-I7 (with a graph in scope, BM25 calls answer only from an index built for that graph); CONTEXT.md:27-43; HD-0703.
- Observed at the pin: Live (b-07-f0705-f0707): USE GRAPH 'b07g1' CALL ivg.bm25.search('b07g2idx','pineapple',5) answered b07g2's node b07_g2a (the generated SQL has no graph check on the index; labels/props joined for b07g1 come back empty). ivg.retrieve could not be run live (no embedder configured: blocked-access for that arm). Model m07-leg-as-built-scope; reviewed passes; control m07-leg-control-no-scope-check caught.
- Source severity S1, confidence high; module 07; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Compare the index's recorded graph with the graph context and refuse a mismatch or an unknown graph, in ivg.bm25.search and ivg.retrieve.
- Reviewed-design control: `playbook-proofs-d1d` `control_f0707_no_scope_check` fails where expected in this run ([receipt](results/playbook-proofs-d1d/20261115T035645Z-control_f0707_no_scope_check/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0711"></a>
### TextSearchEngine answers across graphs and cannot reach iFind

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [07.json](../../experiment/playbook-completion/findings/audit/07.json) (live `b-07-f0711`; run `b-07-unit`; inspected `iris_vector_graph/text_search.py:31-256`; inspected `iris_vector_graph/__init__.py:93-125`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-07-f0711`

- Expected: TXT-B19.1 (its searches answer from one graph only); CONTEXT.md:27-43; HD-0705 assumption (exported helpers are compatibility surfaces whose scope must be qualified).
- Observed at the pin: Live (b-07-f0711): extract_entity_names and search_with_context returned nodes of graphs b07g1 and b07g2 together; search_documents raised SQLCODE -30 on SQLUSER.DOCS (unqualified table) in both the %FIND path and its LIKE fallback and answered []. tests/unit/test_ifind_and_fusion_sql.py (run b-07-unit) documents %FIND(col, ?) as not IRIS syntax.
- Source severity S1, confidence high; module 07; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Per HD-0705: add a graph argument and predicate to every query, use %ID %FIND search_index(...) on the schema-qualified docs table, or deprecate the export.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0802"></a>
### Text shortcuts answer by substring and ignore USE GRAPH

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0802`; mc `m08-scope-as-built-shortcut`; mc `m08-scope-reviewed`; inspected `iris_vector_graph/_engine/query.py:1807-1856`; live `b-08-live-f0802-rerun`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0802`, `b-08-live-f0802-rerun`

- Expected: A scoped query answers only from its graph (CONTEXT.md:27-43; USER_GUIDE.md:401-404); a query is answered by the translator unless it is exactly a tool's canned text.
- Observed at the pin: Live AUDITB: `USE GRAPH 'b08gA' MATCH (n) RETURN count(*) AS c UNION ALL MATCH ()-[r]->() RETURN count(*) AS c` answered column `result` with nodes 7 / relationships 4 (whole namespace) where b08gA holds 3 / 2; a near-miss `RETURN DISTINCT n.name AS entity_name UNION ALL ...` under USE GRAPH answered canned (entity, id) rows including b08_leak (graph b08gB) and b08_s/b08_t (default graph). Model m08-scope-as-built-shortcut violates SYS-I2; reviewed passes.
- Source severity S1, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Match the exact Neo4j Browser / Bloom texts (or compare the parsed AST), honour USE GRAPH in each shortcut, and test that a near-miss query is answered by the translator.
- Reviewed-design control: `playbook-proofs-d1d` `control_f0802_shortcut_unscoped` fails where expected in this run ([receipt](results/playbook-proofs-d1d/20261115T035657Z-control_f0802_shortcut_unscoped/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0814"></a>
### AQL text values are pasted into the Cypher text, and execute_aql ignores read-only

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0814`; mc `m08-readonly-as-built`; mc `m08-readonly-reviewed`; inspected `iris_vector_graph/cypher/aql/translator.py:50-58`; inspected `iris_vector_graph/cypher/aql/translator.py:154-168`; inspected `iris_vector_graph/_engine/query.py:1730-1745`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0814`, `b-08-live-f0814-rerun`

- Expected: CYP-I9.4: a name written in a query reaches SQL only as a bound value or a checked name; CYP-I8.6 / read-only is available on the query entry points.
- Observed at the pin: Live: honest FILTER v.name == 'nomatch' -> 0 rows; hostile literal 'nomatch" OR true OR v.name = "' -> 2 rows (filter rewritten). A collection name `B08R*1..1]->(v) SET v.pwn = 1 WITH v AS v MATCH (start)-[:B08R` made execute_aql write rdf_props rows on b08_m (graph b08gA) and b08_leak (graph b08gB) (journal: sql:Graph_KG.rdf_props). execute_aql has no read_only parameter. Model m08-readonly-as-built violates CYP-I8.6; reviewed passes.
- Source severity S1, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Send every AQL literal as a query parameter, validate collection names as identifiers, add read_only to execute_aql (judge the translated text with writes_cypher), unit tests with hostile literals.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0815"></a>
### A dotted function name pastes raw text into the SQL

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0815`; mc `m08-scope-as-built-dotted`; mc `m08-readonly-as-built`; run `b-08-run-unit`; inspected `iris_vector_graph/cypher/parser.py:1627-1640`; inspected `iris_vector_graph/cypher/translator.py:29563-29578`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0815`, `b-08-live-f0815-rerun`

- Expected: CYP-I9.4; CYP-I8.6 (read-only changes nothing); USE GRAPH scopes the answer (USER_GUIDE.md:401-404).
- Observed at the pin: Live with read_only=True: under USE GRAPH 'b08gA', `` RETURN `(SELECT LIST(NODE_ID) FROM GRAPH_KG.NODES WHERE %SQLUPPER(GRAPH_ID) = %SQLUPPER('B08GB')) AS LEAK --`.f(1) AS v `` answered 'b08_leak,b08_m' (graph b08gB's ids); a dotted name read %DICTIONARY.COMPILEDCLASS (5734 rows counted); `GRAPH_KG.TXN_BEGIN(0)` raised the connection's $TLEVEL 0 -> 1 (restored with Txn_Undo). Journal: no data write. Generated SQL: `SELECT (...) AS LEAK --.F(1) AS v`. tests/unit/test_cypher_posos_bugs.py:157 asserts the pass-through (b-08-run-unit). Models m08-scope-as-built-dotted and m08-readonly-as-built vi…
- Source severity S1, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Refuse back-quoted or non-identifier namespaces in function calls, allow-list qualified functions (or gate them behind a setting), refuse them in read-only mode; unit tests with hostile names.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0816"></a>
### Schema procedures ignore USE GRAPH

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0816`; mc `m08-scope-as-built-dblabels`; inspected `iris_vector_graph/engine.py:1313-1323`; inspected `iris_vector_graph/engine.py:1702-1714`; live `b-08-live-f0816-rerun`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0816`, `b-08-live-f0816-rerun`

- Expected: USER_GUIDE.md:401-404: USE GRAPH scopes a query to one graph.
- Observed at the pin: Live: under USE GRAPH 'b08gA' (labels B08L, types B08R/B08S), CALL db.labels() listed B08B (only in b08gB) and default-graph labels; db.relationshipTypes() listed B08Q and B08T (not in b08gA).
- Source severity S1, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Give the schema handlers a graph parameter (or refuse them under USE GRAPH), with a unit test.
- Reviewed-design control: `playbook-proofs-d1d` `control_f0816_dblabels_unscoped` fails where expected in this run ([receipt](results/playbook-proofs-d1d/20261115T035658Z-control_f0816_dblabels_unscoped/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0818"></a>
### A variable-length walk in an all-graphs read can cross graphs

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0818`; mc `m08-scope-as-built-vlp`; mc `m08-scope-reviewed`; mc `m08-scope-control-vlp-unscoped`; inspected `iris_vector_graph/cypher/translator.py:15404-15431`; live `b-08-live-f0818-rerun`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0818`, `b-08-live-f0818-rerun`

- Expected: CYP-I5.6 / CONTEXT.md:38-43: a variable-length walk in an all-graphs read stays in the graph of its start node.
- Observed at the pin: Live: with b08gA: b08_x-[:B08R]->b08_m and b08gB: b08_m-[:B08R]->b08_leak, `MATCH (a:B08L {id:'b08_x'}) WITH a MATCH (a)-[:B08R*1..2]->(b) RETURN b.id` answered [b08_leak, b08_m, b08_m] (SQL: CY_VLP_PATHS(Stage1.a, ..., 1, '-', ...): gall = 1); the plain-alias form answered [b08_m]. Model m08-scope-as-built-vlp violates SYS-I2; reviewed passes; control m08-scope-control-vlp-unscoped caught.
- Source severity S1, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Carry the start's graph (Stage1.__g_a is already projected) into CY_VLP_* for every start shape, or refuse the shape; e2e test with a WITH-carried start in two graphs.
- Reviewed-design control: `playbook-proofs-d1d` `control_f0818_vlp_crosses_graphs` fails where expected in this run ([receipt](results/playbook-proofs-d1d/20261115T035700Z-control_f0818_vlp_crosses_graphs/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0820"></a>
### kg_GRAPH_PATH reads every graph

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0820`; mc `m08-scope-as-built-graphpath`; inspected `iris_vector_graph/_engine/algorithms.py:679-697`; inspected `iris_vector_graph/operators.py:46-49`; live `b-08-live-f0820-rerun`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0820`, `b-08-live-f0820-rerun`

- Expected: USER_GUIDE.md:462-464: a Python read with no graph= means the default graph, never every graph (HD-0201 working assumption: omission selects the default graph).
- Observed at the pin: Live: engine.kg_GRAPH_PATH('b08_x','B08R','B08S') returned the path b08_x->b08_m->b08_n, which exists only in graph b08gA (no default-graph edge from b08_x).
- Source severity S1, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Add graph= (default: the default graph) and prefix USE GRAPH, with a unit test.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1002"></a>
### random_walk needs the Arno library for an ObjectScript walk, and walks every graph's edges

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [10.json](../../experiment/playbook-completion/findings/audit/10.json) (live `b-10-live-nkg`; mc `m10-routes-as-built-walk-empty`; mc `m10-nkg-as-built-scope`; mc `m10-nkg-reviewed`; mc `m10-nkg-control-walk-merged`; inspected `iris_vector_graph/_engine/algorithms.py:658-678`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-10-live-nkg`

- Expected: ALG-I1 / CONTEXT.md:261-264 (IVG answers the same without the library, only slower); ALG-I3 and SYS-I2; decisions.md HD-1001 working answer (assumption): a declared graph scope and an observable unavailable result, never an empty graph inferred from missing acceleration.
- Observed at the pin: Live (b-10-live-nkg): engine.random_walk('b10_a') answered [] while b10_a has out-edges and the Arno library is absent (engine._detect_arno() False). With named graph b10g1 holding b10_a -> b10_n beside the default graph's b10_a -> b10_b and ^NKG synced, the walk the engine would call, Graph.KG.NKGAccel.RandomWalkJson (pure ObjectScript), stepped first to ['b10_b', 'b10_n']: the named graph's node b10_n from a default-graph walk. The ^NKG procedure ivg.betweenness refused the same namespace (ALG-B7 holds live). Models: m10-routes-as-built-walk-empty and m10-nkg-as-built-scope reproduce both p…
- Source severity S1, confidence high; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Decide HD-1001; at minimum walk the default graph's ^KG in ObjectScript whatever the library state (or refuse with an explicit unavailable error), call EnsureNKG and refuse when a named graph has edges if ^NKG is kept; a live test with two graphs sharing a node id.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1008"></a>
### Variable-length expansion's every-graph mode walks across graphs

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [10.json](../../experiment/playbook-completion/findings/audit/10.json) (live `b-10-live-scope`; live `b-08-live-f0818`; mc `m10-walk-as-built-one-graph`; mc `m10-walk-reviewed`; mc `m10-walk-control-reset-at-shared`; inspected `iris_src/src/Graph/KG/VarLength.cls:44-51`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-10-live-scope`, `b-08-live-f0818`

- Expected: CONTEXT.md:38-43 (an edge meets only nodes of its own graph); ALG-I2.
- Observed at the pin: Live (b-10-live-scope): default graph b10_s -> b10_k, named graph b10g1 b10_k -> b10_m (shared id b10_k). Graph.KG.VarLength.Ends('b10_s', '', 'out', 2, 2, pAll=1) answered [{'t': 'b10_m', 'l': 2}]; with pAll=0 (default graph) []. The translator side (Cypher with gall = 1) is module 08's F-0818, reproduced live there (b-08-live-f0818). Model m10-walk-as-built-one-graph reproduces it; m10-walk-reviewed passes.
- Source severity S1, confidence high; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Walk each graph separately in the every-graph mode (fix the graph at the first hop); a live test with a parameter source in two graphs.
- Reviewed-design control: `playbook-proofs-d1e` `control_f1008_every_graph_mixed` fails where expected in this run ([receipt](results/playbook-proofs-d1e/20261115T035526Z-control_f1008_every_graph_mixed/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1e/20261115T035416Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1101"></a>
### A replayed commit writes its post-commit properties again

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [11.json](../../experiment/playbook-completion/findings/audit/11.json) (live `b-11-live-findings`; live `b-11-live-footprints-1`; mc `m11-retry-as-built-pcp`; mc `m11-retry-as-built-governed`; mc `m11-retry-reviewed`; live `ib-HD1105-replay-reapplies`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-11-live-findings`, `b-11-live-footprints-1`, `ib-HD1105-replay-reapplies`, `live-native-rerun-1314`

- Expected: A replayed commit applies nothing: specs/213-graph-revision-ledger/contracts/ledger-api.md:26 ('original outcome with replayed=True'), tests/integration/test_ledger_us04_idempotency.py:52-62, LED-B10.5; decisions.md HD-1105 (supported: post-commit properties are a separate direct write and retries must be idempotent) and HD-1305 (supported: a retry must not recreate an erased tenant's properties).
- Observed at the pin: Live AUDITB (b-11-live-findings): commit with key b11-k1 created b11_p1 and post-commit property audit=pcp-v1; a governed set_property wrote governed-v2 (seq 7); the retry with the same key answered replayed=True (seq 6) and post_commit_applied=True and audit read pcp-v1 again; a same-key retry carrying different post-commit properties (fingerprint excludes them, changeset.py:365-385) was replayed and wrote pcp-OTHER; verify() diverges on b11_p1.audit. Journal of the retry: Bump's ledger_stats transaction, then a separate rdf_props DELETE+INSERT transaction (b-11-live-footprints-1 capture com…
- Source severity S1, confidence high; module 11; governing page here: `ledger.`.
- Remedy proposed by the playbook arm (not implemented): Skip post-commit properties when the answer is replayed (or record them in the revision, HD-1105 option a), and include them in the fingerprint so a retry with other properties is a key conflict; a live test retrying after a later set_prop and after an erasure.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1114"></a>
### Erasure changes the statement maps without the head lock

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [11.json](../../experiment/playbook-completion/findings/audit/11.json) (live `live-f1201-reproduced`; live `b-11-live-footprints-2`; inspected `iris_src/src/Graph/KG/Eraser.cls:665-678`; inspected `iris_src/src/Graph/KG/Eraser.cls:809-811`; inspected `iris_src/src/Graph/KG/Eraser.cls:1117-1145`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `live-f1201-reproduced`, `b-11-live-footprints-2`

- Expected: LED-B4.14.4 (only a process that holds the head lock changes the statement id maps); SYS-I1 one owner per fact; ADR-0004.
- Observed at the pin: Source at the pin: Graph.KG.Eraser takes no Lock and kills ^IVG.Ledger('stmt')/('tuple') entries in its own transaction (Eraser.cls:665-678, :809-811, EraseLedgerFor :1117-1145 dirty-reads every statement entry). Live: this lane's journal shows the same writes reached from engine.bulk_delete_adjacency -> Eraser.EraseEdges (^IVG.Ledger stmt/tuple killed in the eraser's transaction, no head lock; b-11-live-footprints-2). The interleaving with a commit was reproduced by the orchestrator (run live-f1201-reproduced: the committer's SET ^IVG.Ledger('stmt',4001)/tuple followed by the eraser's KILL o…
- Source severity S1, confidence high; module 11; governing page here: `ledger.`.
- Remedy proposed by the playbook arm (not implemented): Take ^IVG.Ledger('head') in the eraser's transaction when it touches the statement maps (or document that erasure must not run beside commits); a live commit-into-erased-graph test (owned by the orchestrator's erasure module).
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1302"></a>
### Redaction can tombstone history of content a concurrent commit made live (unlocked start, late marker)

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [13.json](../../experiment/playbook-completion/findings/audit/13.json) (original `live:native-commit_in_unmarked_window`; original `mc:redaction-as-built-live`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM)

- Expected: RED-B1.1 / ADR-0013: a redaction never tombstones live content; the marker refuses commits into the target from the start.
- Observed at the pin: Original live reproduction on the same pin (scenario commit_in_unmarked_window, which compiles the original probe class and is not rerun here) and as-built model trace (3 steps); the opening checks run without the head lock and the marker is set at the first tombstone (LedgerRedact.cls:202-211, 322-324). Fresh model and proof evidence: core lanes (pending).
- Source severity S1, confidence high; module 13; governing page here: `redaction.`.
- Remedy proposed by the playbook arm (not implemented): Check liveness and set the marker in one transaction under the head lock (HD-1301 working answer).
- Reviewed-design control: `playbook-proofs-d9c` `control_f1302_unlocked_start` fails where expected in this run ([receipt](results/playbook-proofs-d9c/20261115T040837Z-control_f1302_unlocked_start/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d9c/20261115T041012Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1305"></a>
### A graph-per-tenant redaction with unprefixed ids reports success while the tenant's node history remains

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [13.json](../../experiment/playbook-completion/findings/audit/13.json) (run `live-native-rerun-1314`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM)

- Expected: Spec 256: tenant erasure removes the tenant's content from history (RED-B1.2, SC-001).
- Observed at the pin: Fresh rerun: redact(gTenantA) completes; tenant A's node ids and property values stay in the ledger (node records are graph-blind); verify diverges.
- Source severity S1, confidence high; module 13; governing page here: `redaction.`.
- Remedy proposed by the playbook arm (not implemented): Return an explicit incomplete/refused outcome when node history cannot be attributed (HD-1304 working answer), or record each node record's graph.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1306"></a>
### A retried commit re-applies post-commit properties and revives erased content

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [13.json](../../experiment/playbook-completion/findings/audit/13.json) (run `live-native-rerun-1314`; run `ib-HD1305-retry-revives`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM)

- Expected: HD-1305 (supported): a retry must not recreate an erased tenant's properties; idempotency contract.
- Observed at the pin: Fresh rerun: the replay of a retried commit re-applies the post-commit property; an erased node's property is live again. Intent lane B additionally observed the property write landing in a target while its redaction marker was set (RED-B5 bypass).
- Source severity S1, confidence high; module 13; governing page here: `redaction.`.
- Remedy proposed by the playbook arm (not implemented): Do not reapply post-commit properties on an idempotent replay (or record their completion atomically with the revision) and route them through the marker check.
- Reviewed-design control: `playbook-proofs-d9c` `control_f1306_replay_direct_sql` fails where expected in this run ([receipt](results/playbook-proofs-d9c/20261115T040845Z-control_f1306_replay_direct_sql/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d9c/20261115T041012Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Related: q-010.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1402"></a>
### A reader can return a partially redacted view

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [14.json](../../experiment/playbook-completion/findings/audit/14.json) (run `live-native-rerun-1314`; run `ib-HD1401-reader-full-race`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM)

- Expected: RPL-I1 / HD-1401: a reader returns a consistent pre- or post-redaction view or the documented in-progress result.
- Observed at the pin: Fresh rerun: the reader's view shows tenant A's graph half redacted. Intent lane B: a whole redaction can finish between two pages of one reconstruct() call with the marker absent before and after, so the post-read marker re-check proposed in the original review cannot detect it (an epoch check would).
- Source severity S1, confidence high; module 14; governing page here: `ledger.readers`.
- Remedy proposed by the playbook arm (not implemented): Validate a reader's whole read against a redaction epoch (counter bumped by every batch and Final) and retry or refuse on change.
- Reviewed-design control: `playbook-proofs-d9c` `control_f1402_reader_no_recheck` fails where expected in this run ([receipt](results/playbook-proofs-d9c/20261115T040858Z-control_f1402_reader_no_recheck/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d9c/20261115T041012Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1502"></a>
### A reifier node always lands in the default graph, and erasing the edge's graph leaves it (with its properties) live

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [15.json](../../experiment/playbook-completion/findings/audit/15.json) (live `c15-live-reify`; inspected `iris_vector_graph/_engine/schema.py:3296-3322`; inspected `iris_src/src/Graph/KG/Eraser.cls:185-189`; inspected `iris_src/src/Graph/KG/FHIRGraph.cls:2585-2599`; inspected `iris_vector_graph/_engine/nodes_edges.py:2176-2199`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c15-live-reify`

- Expected: Erasure removes a graph's content from every store (SYS-D26, ADR-0004); content of one graph never shows up in an answer about another graph (SYS-I2); INT-E1.6/INT-E1.7 (a reifier lives with its edge and goes with its graph).
- Observed at the pin: Live (c15-live-reify): reify_edge on an edge of named graph c15g1 wrote the reifier node, its label 'Reification' and its properties with graph_id '' (default graph) in one transaction; the edge is in c15g1. erase_graph('c15g1') deleted the edge and its rdf_reifications row (journal: one transaction) but the reifier node, label and properties {'source': 'tenant-c15g1-secret', 'confidence': 0.9} stayed in the default graph and were returned by get_node('c15:reif1') and by a default-graph Cypher MATCH. delete_node removes the reifiers of a node's edges (INT-E1.9), so the two deletion paths disa…
- Source severity S1, confidence high; module 15; governing page here: `fhir.`.
- Remedy proposed by the playbook arm (not implemented): Create the reifier in the edge's graph (read graph_id with edge_id) and have every edge-deleting path (Eraser.EraseGraph/EraseNodes, FHIR sync DeleteEdge, direct and Cypher edge deletes) delete the reifier nodes of the edges it removes, in the same transaction; a live test that reifies an edge in G, erases G and finds no reifier in any graph.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1503"></a>
### delete_reification deletes any id's node, labels and properties in every graph without checking it is a reifier

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [15.json](../../experiment/playbook-completion/findings/audit/15.json) (live `c15-live-delreif2`; live `c15-live-delreif`; inspected `iris_vector_graph/_engine/schema.py:3361-3397`; inspected `iris_vector_graph/schema.py:42-43`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c15-live-delreif2`, `c15-live-delreif`

- Expected: SYS-I2 (graph isolation) and INT-E1.10 ('deleting a reifier should touch only that reifier node, and leave no edge without its node'); the docstring (schema.py:3364-3368) admits 'Not graph-scoped'.
- Observed at the pin: Live (c15-live-delreif2): delete_reification('c15:z') on an id that is no reifier (0 rdf_reifications rows) and has no edges deleted its node row, labels, properties and ^KG('label') index entries in BOTH named graph c15g2b and the default graph, in one transaction, and returned True. Sub-claim refuted at the pin (c15-live-delreif): for an id WITH edges the foreign key fk_edges_source (schema.py:42) refuses the node delete (SQLCODE -124) and the whole transaction rolls back, so no edge is left without its node row and ^KG is unchanged; the call raises GraphWriteError naming the FK.
- Source severity S1, confidence high; module 15; governing page here: `fhir.`.
- Remedy proposed by the playbook arm (not implemented): Refuse an id with no rdf_reifications row; scope the deletes to the reifier's graph (the default graph at the pin, or the edge's graph once F-1502 is fixed).
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1603"></a>
### The generated GraphQL server mixes graphs in one answer

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [16.json](../../experiment/playbook-completion/findings/audit/16.json) (live `c16-s3-graphql-sample-api`; inspected `iris_vector_graph/gql/resolvers.py:32-133`; inspected `iris_vector_graph/gql/engine.py:32-57`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c16-s3-graphql-sample-api`

- Expected: SYS-I2 / API-B10.3 / API-B15.8: an answer about one graph holds no content of another; a read with no graph reads the default graph (HD-0201).
- Observed at the pin: Live (c16-s3-graphql-sample-api, create_app over AUDITC): node(id:'c16:x') of the default graph listed outgoing [C16_DEF_EDGE->c16:z, C16_G1_EDGE->c16:y]; the second edge lives only in graph c16g1. nodes(label:'C16Q', limit:3) answered [] although default-graph node c16:qz has the label: the page was cut from all graphs' ids (three c16g1-only nodes) and then read in the default graph. Source: iris_vector_graph/gql/resolvers.py:32-46, :90-133 (no graph_id), gql/engine.py:32-57 (field discovery joins rdf_props to rdf_labels on s only).
- Source severity S1, confidence high; module 16; governing page here: `access.`.
- Remedy proposed by the playbook arm (not implemented): Filter every statement by graph_id (default graph unless a graph argument names one), as api/gql/core/resolvers.py does since spec 230; e2e test with one id in two graphs.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1604"></a>
### The sample API's biomedical fields and its update mutation ignore graphs

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [16.json](../../experiment/playbook-completion/findings/audit/16.json) (live `c16-s3-graphql-sample-api`; live `c16-s8-followup`; inspected `api/gql/loaders.py:19-272`; inspected `examples/domains/biomedical/resolver.py:240-278`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c16-s3-graphql-sample-api`, `c16-s8-followup`

- Expected: API-B6.6/B6.7/B15.8: biomedical fields read one graph; updateProtein changes only the named node in one graph (CONTEXT.md:44-48).
- Observed at the pin: Live (c16-s3-graphql-sample-api): protein(id:'c16:p1') answered labels [Protein, Protein, C16G1Label], name 'p-g1' and interactsWith [c16:p2] — the c16g1 copy's label, property and edge merged into the default-graph protein. updateProtein(name:'p-updated') rewrote the name property in BOTH graphs (props_after shows c16g1 name 'p-updated'). Journal (c16-s8-followup): the mutation wrote ['sql:Graph_KG.rdf_props'] on IRIS process(es) ['10556'], outermost commits {'10556': 1}, outside any transaction: []; cross-graph rewrite reproduced again: True. Source: api/gql/loaders.py:19-45, :183-272 (WHER…
- Source severity S1, confidence high; module 16; governing page here: `access.`.
- Remedy proposed by the playbook arm (not implemented): Add graph_id = ? (default graph) to every loader statement and route the update through the engine with graph=; e2e test with one id in two graphs.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1701"></a>
### The SQL adapter's unscoped node and label reads merge graphs

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [17.json](../../experiment/playbook-completion/findings/audit/17.json) (live `c17-live-engine`; inspected `iris_vector_graph/stores/iris_sql_store.py:1116-1210`; inspected `iris_vector_graph/_engine/query.py:245-275`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c17-live-engine`

- Expected: A node's labels and properties are its own graph's (CONTEXT.md 'All-graphs read', decided 2026-10-20); the engine's get_nodes is graph-scoped since spec 227 (iris_vector_graph/_engine/nodes_edges.py:621-636); SYS-I2.
- Observed at the pin: Live (c17-live-engine, AUDITC): node c17:x labelled C17A in c17g1 and unlabelled in c17g2. IRISGraphStore.get_nodes(['c17:x']) with no graph answered [['c17:x', '["C17A"]']]; get_node_labels answered [['c17:x', '["C17A"]']]. Cypher under USE GRAPH 'c17g2': start-label variable-length {'error': None, 'metadata': 'QueryMetadata(estimated_rows=None, index_usage=[], optimization_applied=[], complexity_score=None, warnings=[])', 'rows': [], 'sql': "SELECT Graph_KG.CY_TYPED(%EXACT(p4.val)) AS t_id\nFROM Graph_KG.nodes n0\nJOIN Graph_KG.rdf_labels l1 ON l1.s = n0.node_id AND l1.label = ? AND COALESC…
- Source severity S1, confidence medium; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): Give get_nodes/get_node_labels/query_nodes a graph argument and pass the query's graph from every Cypher caller; a live test with one id in two graphs.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1801"></a>
### A replacing restore lays the archive's ledger over the live one

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [18.json](../../experiment/playbook-completion/findings/audit/18.json) (live `c18-live-ledger-overlay`; mc `cmc-restore-as-built-history`; mc `cmc-restore-as-built-grows`; mc `cmc-restore-as-built-commit`; mc `cmc-restore-as-built-redaction`; mc `cmc-restore-reviewed`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c18-live-ledger-overlay`

- Expected: spec 213 FR-043 (the ledger survives a snapshot); SNP-I3.6 (after a restore the ledger holds one history whose records and head agree); SYS-I5 (the ledger only grows); ADR-0013 (redacted content leaves history); decisions.md HD-1801 (treat the archive's history as a unit; refuse divergent histories before mutation; keep current redaction obligations).
- Observed at the pin: Live (c18-live-ledger-overlay, AUDITC): ledger enabled, commit seq 2 (c18:L1), save, commit seq 3 (c18:L2, retry key c18-k2), replacing restore of the older archive: meta after restore {'head_id': 'ebae4dc3dfb811f1b3edf277e9aab529', 'head_seq': 2, 'max_ops': 50000, 'ok': True, 'recon_bound': 250000, 'state': 'enabled', 'strict': False}; record (3,1) still present: [1]; LedgerRevision seqs [1, 2, 3]; idem binding c18-k2 = '\x03\x04\x03B\x01de63550c92cde590c0b3685718c468739957a52a0fc9cc4ac0b69b089ee8c653'; the next commit -> {'error': 'LedgerInconsistencyError: revision row save failed: ERROR #…
- Source severity S1, confidence high; module 18; governing page here: `install.snapshot`.
- Remedy proposed by the playbook arm (not implemented): Per HD-1801: refuse a restore whose archive history does not extend the live one, before erase_all; otherwise replace the ledger as a unit (kill ^IVG.Ledger and the ledger storage first) and re-apply live redactions (tombstones, redactedRev, idemRedacted) to the archived records.
- Reviewed-design control: `playbook-proofs-d1b` `control_f1801_no_prefix_check` fails where expected in this run ([receipt](results/playbook-proofs-d1b/20261115T035736Z-control_f1801_no_prefix_check/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1b/20261115T035711Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Related: q-plt-004.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1250"></a>
### An rdf_edges row a %NOINDEX bulk load wrote survives delete_nodes_by_prefix of both its endpoints and EraseAll+PurgeAll until the indices are rebuilt; its endpoint nodes are deleted under it

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-writesets.json](../../experiment/playbook-completion/findings/audit/zz-writesets.json) (live `ws-live-noindex-erase`; live `ws-live-ins-bulkloader_load_edges`; live `ws-live-ins-import_rdf`; inspected `iris_src/src/Graph/KG/Eraser.cls:777-779`; inspected `iris_vector_graph/bulk_loader.py:380-400`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `ws-live-noindex-erase`, `ws-live-ins-bulkloader_load_edges`, `ws-live-ins-import_rdf`

- Expected: docs/adr/0004-erasure-removes-content-not-history.md (erasure removes the content); iris_src/src/Graph/KG/Eraser.cls:699-709 (EraseAll: 'Remove every graph's content from every store'); iris_vector_graph/schema.py:34-44 (fk_edges_source / fk_edges_dest: an edge row needs its endpoint node rows).
- Observed at the pin: Live in AUDITB (ws-live-noindex-erase): BulkLoader.load_edges with its default use_noindex=True registered 2 endpoint nodes (indexed) and wrote the edge row with INSERT %NOINDEX %NOCHECK (bulk_loader.py:456-460): indexed counts saw nodes 2, edges 0; a %IGNOREINDEX full scan saw nodes 2, edges 1. engine.delete_nodes_by_prefix('wse|') answered 2 and deleted both node rows; the edge row stayed (the foreign keys did not refuse deleting nodes the unindexed edge references). Graph.KG.Eraser.EraseAll answered 0 and Ledger.PurgeAll ran: the full scan still found the row (the only content row left); v…
- Source severity S1, confidence high; module 12; governing page here: `erasure.`.
- Remedy proposed by the playbook arm (not implemented): Have the erasure paths read without the indexes a %NOINDEX load leaves stale (or refuse while an index build is pending), and have the bulk loader rebuild its indices before it returns; an erase that leaves a row of an erased tenant should say so.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1306"></a>
### After a 4.5.x upgrade to a non-default IVG Schema, Graph_KG.ledger_revisions keeps the tenant's messages, sources, correlation ids and idempotency keys, which redaction never clears

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [followup.json](../../experiment/playbook-completion/findings/audit/followup.json) (live `fc1306-legacy-ledger-rows`; inspected `iris_vector_graph/_engine/legacy.py:606-646`; inspected `iris_vector_graph/_engine/schema.py:2223-2226`; inspected `iris_vector_graph/_engine/schema.py:2308`; inspected `iris_vector_graph/_engine/class_deploy.py:109-119`; inspected `iris_src/src/Graph/KG/LedgerRedact.cls:351-376`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `fc1306-legacy-ledger-rows`, `o1-fixture-inventory`

- Expected: specs/256-ledger-tenant-redaction/spec.md:142-143 (SC-001: after erase and redaction 'every Graph_KG.ledger_* row finds none of the tenant's ids or values'); spec.md:120-121 (FR-004, Decision 2: a revision's free text is cleared); FR-008 reach statement; docs/adr/0013-redaction-removes-content-from-history.md:47.
- Observed at the pin: Live (run fc1306-legacy-ledger-rows, scratch namespace IVG262FC1306): the pinned fixture's own functions (scripts/fixtures/build_release_namespace.build('v4.5.1', ..., schema_prefix='RAG'), run_ledger_commits) plus v4.5.1's public engine.ledger.commit built a 4.5.1 namespace whose Graph_KG.ledger_revisions held 7 revisions: tenant r114 (seqs 2, 3, 4, 6; seqs 4 and 6 with message, source, correlation_id and idempotency_key) and tenant o114 (seqs 5, 7). The pin's initialize_schema(schema_prefix='RAG') copied them (ledger_history_copied {ledger_revisions: 7, ledger_stats: 1}); verify() equal. Th…
- Source severity S1, confidence high; module 13; governing page here: `redaction.`.
- Remedy proposed by the playbook arm (not implemented): On redaction, also clear (or report) rows of a legacy Graph_KG.ledger_revisions (and ^Graph.KG.LedgerRevisionD) when the IVG Schema is not Graph_KG; or have the upgrade move rather than copy the rows (delete or %NODELDATA plus kill of the legacy storage after the copy is verified); and name any remaining legacy copy in the receipt.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1350"></a>
### Redaction batches tombstone the history of content a ledger-bypassing writer made live after the run's entry check

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-writesets.json](../../experiment/playbook-completion/findings/audit/zz-writesets.json) (live `ws-live-ins-store_node`; live `ws-live-ins-store_edge`; live `ws-live-ins-bulk_create_nodes`; live `ws-live-ins-bulk_ingest_edges`; live `ws-live-ins-bulk_create_edges`; live `ws-live-ins-store_write_nodes`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `ws-live-ins-store_node`, `ws-live-ins-store_edge`, `ws-live-ins-bulk_create_nodes`, `ws-live-ins-bulk_ingest_edges`

- Expected: experiment/playbook-uplift/ontology/13-redaction.md:51 (RED-B1.1: redaction never makes a tombstone of the record of live content); specs/256-ledger-tenant-redaction/spec.md:124 (FR-005: redaction MUST refuse while any non-tombstoned live statement or node of the target remains); docs/adr/0013-redaction-removes-content-from-history.md:17 (refused while any row of the target is live); the product's own checks count any content row of the target as live (LedgerRedact.cls:202-211 entry, 409-416 Final 'became live again').
- Observed at the pin: Live in AUDITB, 12 runs, one per writer (ws-live-ins-store_node, -store_edge, -bulk_create_nodes, -bulk_ingest_edges, -bulk_create_edges, -store_write_nodes, -store_write_edges, -create_edge_temporal, -bulk_create_edges_temporal, -reify_edge, -bulkloader_load_edges, -import_rdf). Each: a target tenant with 7 ledger records (2 nodes with label and property, 1 relationship) is erased (0 live rows); a redaction is started while a second connection holds ^IVG.Ledger("head") (as a concurrent ledger commit does), passes its entry liveness check and waits for the lock; the writer, which reads no mar…
- Source severity S1, confidence high; module 13; governing page here: `redaction.`.
- Remedy proposed by the playbook arm (not implemented): Either make every content writer refuse a write into a target while its marker exists (and serialize writers with the run's start, HD-1301's working answer), or have each batch re-check the target's liveness under the head lock before it tombstones and stop (leaving the marker) when the target is live again.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1351"></a>
### The redaction's liveness check misses rows a bulk load wrote with %NOINDEX: the redaction completes while the tenant's rows exist, and they reappear at the next index rebuild

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-writesets.json](../../experiment/playbook-completion/findings/audit/zz-writesets.json) (live `ws-live-noindex`; inspected `iris_src/src/Graph/KG/LedgerRedact.cls:149-178`; inspected `iris_vector_graph/bulk_loader.py:252-300`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `ws-live-noindex`

- Expected: specs/256-ledger-tenant-redaction/spec.md:124 (FR-005: refuse while any non-tombstoned live statement or node of the target remains); docs/adr/0013-redaction-removes-content-from-history.md:17 (refused while any row of the target is live); RED-B1.1 (experiment/playbook-uplift/ontology/13-redaction.md:51).
- Observed at the pin: Live in AUDITB (ws-live-noindex): tenant wsni committed through the ledger (3 records) and erased; BulkLoader.load_nodes (default use_noindex=True, INSERT %NOINDEX %NOCHECK, bulk_loader.py:8-11) wrote its node, label and property rows; COUNT(*) queries of LiveRows' shape (%EXACT(id) %STARTSWITH ?, LedgerRedact.cls:149-178) answered 0 while a %IGNOREINDEX full scan found nodes 1, labels 1, props 2; redact(None, prefix='wsni') completed (receipt complete, 3 records tombstoned, marker removed); BulkLoader.rebuild_all_indices then made the rows visible: 4 live rows under tombstoned records, verif…
- Source severity S1, confidence high; module 13; governing page here: `redaction.`.
- Remedy proposed by the playbook arm (not implemented): Count liveness without relying on indexes a %NOINDEX load leaves stale (%IGNOREINDEX on LiveRows' counts, or refuse a redaction while an index build is pending for the content tables), or have the bulk loader rebuild the indices before it returns.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1803"></a>
### Graph.KG.Snapshot's unused file helpers read, write and delete server files for any Native API caller

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-versions.json](../../experiment/playbook-completion/findings/audit/zz-versions.json) (live `ver-priv-r2`; live `ver-priv-r1`; live `c18-live-file-helpers`; inspected `iris_src/src/Graph/KG/Snapshot.cls:4-73`; inspected `docs/ADMIN_GUIDE.md:450-473`; inspected `scripts/setup_security.sql:5-7`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `ver-priv-r2`, `ver-priv-r1`, `c18-live-file-helpers`

- Expected: ADMIN_GUIDE.md:450-473 grants the least-privilege reading role %Native_ClassExecution:U; nothing in the product needs server file access through IVG classes (no caller of ReadFileChunk/WriteFileChunk/DeleteDir/ExportGlobals). docs/ADMIN_GUIDE.md:598: 'A read-only role is one whose database resource is R'; :520 'With the database at R it writes nothing'.
- Observed at the pin: Live (c18-live-file-helpers, as _SYSTEM): FileExists('/etc/hostname') = 1, GetFileSize = 33, ReadFileChunk returned 'ivg-playbook-20261113-audit-iris\n'. Source: WriteFileChunk (Snapshot.cls:49-57) writes any path, DeleteDir (:64-68) runs RemoveDirectoryTree on any path, ExportGlobals (:4-22) writes any global to any directory, all as the IRIS server's OS user, with no IVG check. Live as the documented reading role (ver-priv-r1, ver-priv-r2; user IVGAUDIT_RO, database resource at R, %Native_ClassExecution:U): FileExists('/etc/hostname') = 1, GetFileSize = 33, ReadFileChunk returned the host n…
- Source severity S1, confidence high; module 18; governing page here: `install.snapshot`.
- Remedy proposed by the playbook arm (not implemented): Delete the file and global helpers (no product caller), or restrict them to an admin role and an allow-listed folder.
- Recorded in 18.json, zz-versions.json; the later file's record is used.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1804"></a>
### A snapshot carries no routed edge vectors (kg_eemb_ tables): a restore loses them silently

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [18.json](../../experiment/playbook-completion/findings/audit/18.json) (live `c18-live-edge-vectors`; live `c18-live-edge-routes`; inspected `iris_vector_graph/_engine/snapshot.py:299-344, 960-1025`; inspected `iris_vector_graph/security.py:58-80`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c18-live-edge-vectors`, `c18-live-edge-routes`

- Expected: ADMIN_GUIDE.md:984-986 (a snapshot holds kg_EdgeEmbeddings and each routed embedding table the registry names); SNP-I1 (each store is copied or its omission explained); SNP-B1.18.
- Observed at the pin: Live (c18-live-edge-vectors, c18-live-edge-routes part a): store_edge_embedding(graph='c18w') wrote route [['kg_eemb_cb5b098c95e72cdb', 'c18w', 'edge', '4']] with 1 row(s); the archive's members are ['metadata.json', 'sql/Graph_KG_nodes.ndjson', 'sql/Graph_KG_rdf_edges.ndjson', 'sql/Graph_KG_rdf_labels.ndjson', 'sql/Graph_KG_rdf_props.ndjson', 'sql/Graph_KG_rdf_reifications.ndjson', 'sql/Graph_KG_docs.ndjson', 'sql/Graph_KG_embedding_registry.ndjson', 'sql/Graph_KG_code_crosswalk.ndjson', 'sql/Graph_KG_rdf_namespaces.ndjson', 'sql/Graph_KG_table_mappings.ndjson', 'sql/Graph_KG_relationship_ma…
- Source severity S1, confidence high; module 18; governing page here: `install.snapshot`.
- Remedy proposed by the playbook arm (not implemented): Plan and export edge routes (is_routed_edge_embedding_table) with their width and kind, recreate them on restore, and count a registry row whose table could not be restored as failed.
- Reviewed-design control: `playbook-proofs-d1b` `control_fc1804_edge_routes_omitted` fails where expected in this run ([receipt](results/playbook-proofs-d1b/20261115T035744Z-control_fc1804_edge_routes_omitted/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1b/20261115T035711Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1850"></a>
### A replacing restore leaves the live ledger's redaction stores in place: a marked target comes back live, and a second redaction of a restored tenant keeps its revision text and retry key

Severity: High · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-writesets.json](../../experiment/playbook-completion/findings/audit/zz-writesets.json) (live `ws-live-gap-restore`; live `ws-live-gap-marker`; inspected `iris_vector_graph/_engine/snapshot.py:1654-1692`; inspected `iris_src/src/Graph/KG/LedgerRedact.cls:333-378`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `ws-live-gap-restore`, `ws-live-gap-marker`

- Expected: spec 256 Decision 2 as the code states it (iris_src/src/Graph/KG/LedgerRedact.cls:349-352: clear message, source, correlation id and idempotency key of a revision with a redacted record) and specs/256-ledger-tenant-redaction/spec.md:142 (SC-001); ADR-0013 (redaction removes content from history; while a run is in progress the target is not live); decisions.md HD-1801 (treat the archive's history as a unit; keep current redaction obligations).
- Observed at the pin: Live in AUDITB. (1) ws-live-gap-restore: tenant wsgap, revision 2 (message, key wsgap-k1); save_snapshot; erase; redact complete (audit revision 3; redactedRev(2), idemRedacted set, idem killed, text cleared); restore_snapshot(archive, merge=False): records of seq 2 back as originals, row 2 message and key back, idem(wsgap-k1) live, while redactedRev(2) and idemRedacted stay (the import of ^IVG.Ledger sets the archive's nodes and kills none, snapshot.py:1574, 1654-1692). Erase and redact again: the 3 records are tombstoned but ClearRevision is skipped because redactedRev(2) exists (LedgerReda…
- Source severity S1, confidence high; module 18; governing page here: `install.snapshot`.
- Remedy proposed by the playbook arm (not implemented): Make a replacing restore replace the whole ledger state as a unit (kill ^IVG.Ledger, including marker, redactedRev and idemRedacted, before importing) or refuse it when the live ledger has redactions after the archive (HD-1801's working answer); and have ClearRevision clear a revision's text whenever it still holds text, not only when redactedRev is absent.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="bug-led-007"></a>
### Erasing a tenant by prefix leaves its temporal-only events, and the redaction that follows completes while they stay readable

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Also recorded as: F-C1203 (playbook arm, S1, reproduced-live; [followup.json](../../experiment/playbook-completion/findings/audit/followup.json)); F-C1308 (playbook arm, S1, reproduced-live; [followup.json](../../experiment/playbook-completion/findings/audit/followup.json)). Severity differs: here Medium, playbook S1/S1; both are kept. (crosswalk)

Found by: [witness_prefix_erase_leaves_temporal_only_content](results/ledger_redaction/20261114T044401Z-prove/receipt.json) (W5) in [redaction.rs](models/ledger_redaction/redaction.rs), with control [prefix-erase-reaches-temporal](results/ledger_redaction/20261114T044554Z-control-prefix-erase-reaches-temporal/receipt.json) (EXPECTED_FAIL); review round2-core R2-1 (scratch witnesses d1/d2 showed the model's earlier erase over-approximated the product).

Reproduced by: [erasure_prefix_temporal_only](receipts/native/erasure_prefix_temporal_only.json) — tenant `tE|` had two temporal-only events, one whose endpoint `tE|1` had a node row and one whose endpoint `tE|x` had none; `delete_nodes_by_prefix("tE|")` removed 1 node row; the `tE|x` event stayed readable after the erase and after the redaction, which reported `complete` with 4 records tombstoned; `verify()` was `equal`.

Expected: an erase removes graph content from every store that holds it, the temporal index included (ADR-0004; CONTEXT.md "Erasure"); a redaction is refused while any of the target's content is live (CONTEXT.md "Redaction"). Scope (review round 3 R3-reader H2): ADR-0013:37 documents the full tenant redaction for a tenant "whose relationships live in its own graph", and spec 256 ("Not in this spec", `spec.md:161-163`) put off "a tenant-scoped erase of the temporal tiers inside a shared graph" because "with one graph per tenant, `EraseGraph` covers it". The failing case — a tenant's temporal-only events in a shared graph — is therefore outside the documented recipe, but `delete_nodes_by_prefix` still promises erasure from every store (ADR-0004) and the redaction reports `complete` without saying anything is left.

Observed: `Eraser.EraseNodes` collects the IDs to erase from `Graph_KG.nodes` rows (`Eraser.cls:331-349`), and `TemporalIndex.EraseNodes` then erases temporal edges only for those IDs (`TemporalIndex.cls:400-440`). A temporal-only predicate writes no node row (`TemporalIndex.cls:103-114`; ADR-0015), so its events whose endpoints have no node row survive. `LiveRows` does not read the temporal index and verify ignores it, so neither notices.

Consequence: after an erase by prefix and a prefix redaction of a tenant that shares a graph the tenant's events stay readable through the window reader while the redaction reports complete, verify is equal, and the events' history is tombstoned. The documented prefix recipe misses them; removing them needs their endpoint IDs, then an explicit-id erase (`delete_node(id, graph=…)` or the store's `delete_nodes(ids)`, whose `EraseNodeIds` erases events incident on a named ID with or without a node row, `Eraser.cls:352-389`, `TemporalIndex.cls:421`) or `delete_temporal_edge` per event (review round 3 R3-3, code reading; not run natively).

Why Medium: lowered from High in review round 3, because the governing spec deferred this case and the documented recipe assumes one graph per tenant; it stays Medium because the incompleteness is silent (`complete`, `verify()` equal) for a privacy operation.

Repair proposal (not implemented): let `EraseNodes` and `TemporalIndex.EraseNodes` also select temporal endpoints by ID prefix, not only IDs that have node rows; count temporal entries as live content in redaction ([q-009](open_questions.md#q-009)). Without the first change, [simp-003](design_simplification.md#simp-003)'s full live-content check would turn every as-built prefix erase of such a tenant into a refusal until the events are removed by ID. Open part: [redaction.after-erasure.temporal](../ontology/features/redaction.g5.md#redaction.after-erasure.temporal). Governing statements: [erasure.scope](../ontology/features/erasure.g5.md#erasure.scope), [erasure.prefix-match](../ontology/features/erasure.g5.md#erasure.prefix-match).

<a id="bug-003"></a>
### Redacting the whole default graph ignores node rows in named graphs and destroys the history of nodes that are still live

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Also recorded as: F-1304 (playbook arm, S1, reproduced-live; [13.json](../../experiment/playbook-completion/findings/audit/13.json)). Severity differs: here Medium, playbook S1; both are kept. (crosswalk)

Found by: [witness_default_graph_target_is_not_graph_blind](results/ledger_redaction/20261114T044401Z-prove/receipt.json) (W3); `witness_full_check_refuses_the_gaps` shows the stricter check refuses it and still admits the valid run. Review R1-core R1-7 and R1-8: the model's `Erase` removes named-graph node rows for a default-graph target, which the product's does not, so W3 builds the state directly.

Reproduced by: [redaction_default_graph_whole](receipts/native/redaction_default_graph_whole.json) — ledger commit of nodes X, Y and an edge X→Y in graph `gN` (the ledger registers X and Y in `gN`); `erase_graph(None)`; nodes X and Y are still rows in `gN`. `redact(None)` completed and tombstoned 4 records of X and Y; `verify()` diverges afterwards.

Expected: spec 256 plan.md "The node-liveness check for a default-graph target is graph-blind" (node records and verify ignore graphs); ADR-0013 refusal while any row of the target is live.

Observed: `LiveRows` applies graph-blindness only with a prefix (LedgerRedact.cls:155-165); with no prefix it counts `graph_id = ''` rows only, while `Matches` takes every node record (graph "") (:93-94).

Consequence: an operator who erases the whole default graph and redacts it with no prefix (a narrow, operator-initiated trigger; the tenant recipe uses a prefix) loses the history of nodes that are still live in other graphs. Verify, which already diverged after the erase, can be returned to equal by an adoption, but the tombstoned history of those live nodes cannot be restored. The Eraser refuses the analogous empty prefix (Eraser.cls:314-318).

Repair proposal (not implemented): [simp-003](design_simplification.md#simp-003). Governing statement: [redaction.after-erasure.default-graph](../ontology/features/redaction.g5.md#redaction.after-erasure.default-graph).

<a id="bug-004"></a>
### A redaction reports complete while records it could not attribute still hold the target's content

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Found by: [witness_unattributed_qualifier_survives](results/ledger_redaction/20261114T044401Z-prove/receipt.json) (W4) and `lemma_complete_run_removes_every_target_record`, which needs premise P_ends.

Reproduced by: [redaction_unattributed_qualifier](receipts/native/redaction_unattributed_qualifier.json) — an edge written by `engine.create_edge` (allowed outside strict mode), then qualified through the ledger by tuple (statement assigned, `set_qual` record only), then the tenant erased by prefix and redacted: receipt `complete=True`, `records_tombstoned=2`, `unattributed_records=1`, and one `set_qual` record still holds `uSecretQualifier`.

Expected: `ledger.redact` docstring and ADR-0013 "Every record of the target becomes a tombstone"; spec 256 FR-001 "MUST replace every record".

Observed: `LedgerRedact.Matches` answers -1 when a qualifier record's statement endpoints are unknown (no create/delete record, statement entry removed by the erase) (LedgerRedact.cls:101-110); `BatchInLock` skips it and counts it (:317-320); the run still completes. `unattributed_records` is not documented anywhere.

Consequence: tenant strings survive a "complete" redaction; only the undocumented receipt count reveals it.

Repair proposal (not implemented): [simp-002](design_simplification.md#simp-002); at minimum refuse completion (or report incomplete) while the count is above zero. Open choice: [redaction.unattributed](../ontology/features/redaction.g5.md#redaction.unattributed).

<a id="bug-str-003"></a>
### A degree cached before a node is deleted and re-created can be served afterwards as current

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** The model trace is proved, but the race is not natively reproducible without a stall hook (for a small node the recount takes microseconds while the three writer transactions take milliseconds); severity is lowered one level from High.

Found by: [witness_aba_delete_and_recreate_serves_stale_degree](results/graph_structure/20261114T000451Z-prove/receipt.json) in [graph_structure.rs](models/graph_structure/graph_structure.rs) (B-structure O3/F2 route 1; repair `theorem_repaired_cache_sound` and `witness_repair_refuses_the_aba_store`; route 2 `witness_rolled_back_kill_restores_stale_entry` is model-only, its product reachability open); A-structure F2; review R2-data R1-8 and R1-10, now in the model: `witness_gen0_erase_alone_serves_stale_degree` (the generation-0 route, non-indexed namespaces only) and the kill-bump repair `theorem_kill_bump_cache_sound` with `witness_kill_bump_refuses_the_aba_store` and `witness_gen0_kill_bump_refuses`.

Reproduced by: none yet — [graph_structure_degree_aba](receipts/native/graph_structure_degree_aba.json) ran 3 readers for 120 s (3,129 rounds, about 2.1 million degree calls) with no stale entry: INCONCLUSIVE, not evidence of absence; the reader count is bounded by Community's connection licence.

Expected: a cached degree equals a recount at the time it is served, and no count cached before an erase may be served after it, even when later writes bring the generation back to an earlier value (ADR-0012:12-17 and "the cache is derived"; spec 248 spec.md:76-77).

Observed: `RemoveSource` kills `^KG("gen")` and `degc` (`Adjacency.cls:376-377`; also `RemoveGraph`/`RemoveAll` and the non-indexed restore, `snapshot.py:1688-1691`), and writers restart the generation from 0 with `$Increment`. The reader's store test and post-store re-read compare equality only (`Adj.cls:75, 78-80`), so a history A→kill→…→A passes both. The generation is killed by `delete_node` (`Eraser.RemoveNode`), by the purge's default `retire_bare_nodes=True` (`Eraser.ForgetNodes` → `RemoveSource`, `Eraser.cls:1320-1327`), by `erase_graph` (`RemoveGraph`, `Adjacency.cls:437`) and by `%BuildIndices`' `PurgeIndex` (`RemoveAll`, `:461`); after a non-indexed `BuildKG`/`sync()` (no generation bump, `Adjacency.cls:826-830`) a single erase completes it. The spec 248 text and the `Adj.cls:46-48` comment claim the re-read closes the erase window; the model shows the re-read is redundant when generations are monotone and insufficient when they are not.

Consequence: degree (and so Cypher `size()`/degree answers and degree-ordered plans) for a deleted or re-created node reads an old count until the next write to that node.

Repair proposal (not implemented): stamp each cache entry with a never-killed epoch that every kill of `gen`/`degc` increments first, and compare it on a hit (proved for committed kills at any time); or, in `RemoveSource`, `$Increment` the generation instead of killing it (proved: `theorem_kill_bump_cache_sound`; leaves one residue node per erased source, and `RemoveGraph` and `RemoveAll` still need the epoch). Drawing generations from the version token is not a repair ([simp-str-005](design_simplification.md#simp-str-005)). Correct the spec 248 and `Adj.cls` claims. Governing statements: [structure.degree.cache.erase](../ontology/features/graph-structure.g5.md#structure.degree.cache.erase), [structure.degree.cache](../ontology/features/graph-structure.g5.md#structure.degree.cache).

<a id="bug-str-004"></a>
### verify_graph reports healthy parallel edges as missing adjacency and cannot see lost multiplicity

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Found by: A-structure F7 (source arithmetic; open task T036, `tasks.md:198`; unmet SC-005, `spec.md:355-356` of spec 234).

Reproduced by: [graph_structure_parallel_delete_rel](receipts/native/graph_structure_parallel_delete_rel.json) (`f7_verify_before`) — before any delete, a default graph holding two parallel edges reports `ok: 0` with "missing" drift of 1 row in `^KG("out")` and 1 in `^KG("in")` (`sqlEdges` 2, `outEdges` 1).

Expected: `verify_graph` reports rows with no adjacency entry and entries with no row, and its `ok` answers whether the graph's adjacency agrees with its rows; in a multigraph the layout holds one leaf plus children for two or more edges (spec 234 FR-004, SC-005).

Observed: `GraphVerify` computes `missing = rows − matched distinct triples` (`GraphVerify.cls:78, 104, 128`), so every extra parallel edge counts as missing, and a triple that lost its children still matches.

Consequence: an operator sees false drift on every multigraph and may rebuild for nothing, while real multiplicity loss (for example [bug-str-001](#bug-str-001)) goes unreported.

Repair proposal (not implemented): compare each triple's row count with its leaf, children and `#` count. Governing statement: [structure.verify](../ontology/features/graph-structure.g5.md#structure.verify).

<a id="bug-str-005"></a>
### create_edge stores the raw graph name in SQL, so a name with a NUL becomes a second SQL graph sharing one adjacency entry

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Found by: [witness_raw_sql_name_splits_one_index_graph](results/graph_structure/20261114T000451Z-prove/receipt.json) in [graph_structure.rs](models/graph_structure/graph_structure.rs) (B-structure O1/Q5; the model proves the key half only, and is injective only modulo `canonical`); A-structure Q5; review R2-data R1-4.

Reproduced by: [graph_structure_keys](receipts/native/graph_structure_keys.json) case K4 — `create_edge` in graph `'g5k'` and in `'g5k'+NUL` gave two `rdf_edges` rows and one adjacency entry; `delete_edge(graph='g5k')` left the NUL row with no `^KG` entry, and `verify_graph("g5k")` then answers `ok` with no SQL edges, so the orphan row is invisible to it.

Expected: a graph key is derived from the canonical name and NUL is a transport artifact that is stripped (ADR-0003; `GraphKey.cls:23-37`; CONTEXT.md:50-58).

Observed: `create_edge` derives the index key from the canonical name (`nodes_edges.py:1197`) but binds `gid = graph or ""` to SQL (`nodes_edges.py:1213`), so the duplicate guard (`COALESCE(graph_id,'') = ?`, `:1217`) admits a second row; `create_node` binds the raw name with no validation (`nodes_edges.py:1019`).

Consequence: one index graph spans two SQL graphs; deleting through either name leaves a row without adjacency that traversal cannot see and `verify_graph` does not report.

Repair proposal (not implemented): bind `GraphKey.ForName` (the canonical name) to every SQL `graph_id` and validate in `create_node`. Governing statements: [graph.key.derive](../ontology/concepts/graph-scope.g5.md#graph.key.derive), [graph.names](../ontology/concepts/graph-scope.g5.md#graph.names).

<a id="bug-tmp-004"></a>
### A temporal write creates endpoint nodes that the ledger never recorded, so verify diverges after the ledger's own temporal operation

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Found by: [witness_direct_temporal_write_makes_verify_diverge, witness_ledger_temporal_op_makes_verify_diverge and witness_changeset_op_order_decides](results/temporal/20261114T001508Z-prove/receipt.json) in [temporal.rs](models/temporal/temporal.rs) (B-temporal Q4/F4; valid outcomes `witness_known_endpoints_in_named_graph_keep_verify`, `witness_optout_temporal_write_keeps_verify`); A-temporal F4 and Q3.

Reproduced by: [temporal_endpoint_nodes_verify](receipts/native/temporal_endpoint_nodes_verify.json) — V1 a direct write and V2 a ledger `create_temporal_edge` with a new endpoint ID: `verify()` diverges with `unrecorded_writes` on that node; V3 a temporal op followed by `upsert_node` in one changeset: diverges; V4 `[temporal, create_node]` is refused `node_exists` while `[create_node, temporal]` commits; V5 the same under strict mode. Controls C0 (known endpoints) and C1 (temporal-only predicate) stay equal.

Expected: commit `43efd473` ("Decided with Tom"): temporal writes create no revisions and "a temporal mirror is no longer an unrecorded write", the mirror including "its endpoints in the edge's graph"; verify reports divergence only for writes that bypassed the ledger.

Observed: `AssertTemporalRow` inserts missing endpoint nodes with no record (`Adjacency.cls:597`), also inside `OpCreateTemporalEdge`; `read_canonical` reads every `nodes` row graph-blind (`replay.py:598-600`), and `OpCreateNode` is graph-blind, so an upsert of such a node records nothing and a create is refused (`LedgerApply.cls:215-250`). The purge's `retire_bare_nodes` (default since 4.7.0) deletes bare nodes with no ledger check (`Eraser.cls:1333-1352`).

Consequence: a ledger user who writes temporal edges to new IDs gets permanent `diverges` from verify (V3 cannot be fixed by a later upsert), including in strict mode, and the order of operations in a changeset decides between refusal and divergence.

Repair proposal (not implemented): either exclude temporal-asserted endpoint nodes from verify as the marked rows are, or record them (or refuse the temporal op) when an endpoint is missing; make `retire_bare_nodes` skip ledger-recorded nodes. Open choice: [temporal.structural.ledger-nodes](../ontology/features/temporal.g5.md#temporal.structural.ledger-nodes). Governing statements: [temporal.structural.ledger](../ontology/features/temporal.g5.md#temporal.structural.ledger), [ledger.verify](../ontology/features/ledger.g5.md#ledger.verify).

<a id="bug-tmp-005"></a>
### Making a temporal-only predicate structural again before dropping its rows strands marked rows that nothing removes

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Found by: [witness_optin_strands_marked_row](results/temporal/20261114T001508Z-prove/receipt.json) in [temporal.rs](models/temporal/temporal.rs) (B-temporal O3/F8, with `lemma_stranded_row_survives_purge`; recovery `witness_optin_strand_recovery_by_drop`; repair `theorem_rows_optin_guarded`); A-temporal F8 and Q4.

Reproduced by: [temporal_marked_row_lifecycle](receipts/native/temporal_marked_row_lifecycle.json) case F8 — a marked row of a re-opted-in predicate with no timestamp survives delete, purge, drop (refused: the predicate is structural) and backfill. Cases K1–K3 (marker lifecycle, adoption, temporal-only write) behaved as specified.

Expected: a marked row means "this edge exists at some time" and goes with its last timestamp (ADR-0009 and its spec 254 amendment); ADR-0015's migration guidance assumes the drop runs before any toggle back.

Observed: the purge skips registered predicates (`TemporalIndex.cls:966`), so after opting out and purging, the rows stay as decided; after `set_temporal_structural(p, True)` `DropRows` refuses a structural predicate (`TemporalPolicy.cls:132-134`), delete finds no timestamp, and no purge range selects the row.

Consequence: traversal and `MATCH` keep showing edges whose every event was purged, until an operator re-registers the predicate, drops its rows and opts in again.

Repair proposal (not implemented): refuse the opt-in while marked rows of the predicate have no timestamp (proved sufficient), or let `DropRows` accept those rows. Open choice: [temporal.optout.stranded](../ontology/features/temporal.g5.md#temporal.optout.stranded). Governing statement: [temporal.structural.end](../ontology/features/temporal.g5.md#temporal.structural.end).

<a id="bug-tmp-009"></a>
### A temporal aggregate read of min, max or avg over an empty window raises ValueError, although the method promises 0.0

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Found by: review R2-data R1-5 (seen in six probe traces); the same error first stopped two cases of the earlier temporal probe runs.

Reproduced by: [temporal_write_modes](receipts/native/temporal_write_modes.json) and [temporal_rollback_counters](receipts/native/temporal_rollback_counters.json) — `get_temporal_aggregate(..., "min"/"max"/"avg")` over a window with no raw edge (empty, or holding only counts a rolled-back or refused write left) raised `ValueError: could not convert string to float: 'None'`.

Expected: "An empty window or an unknown metric gives `0` or `0.0`, never `None`; a failed server call raises" (`_engine/temporal.py:950-951`).

Observed: the store converts the server's answer with `val = str(...)`, so a missing value becomes the text `None`, which is truthy, and then returns `float(val) if val else 0.0` (`iris_sql_store.py:2977-2987`); the engine also returns `None` when no row comes back (`_engine/temporal.py:959`).

Consequence: dashboards and callers that read min, max or average over a quiet window get an exception instead of 0.0.

Repair proposal (not implemented): test the server value for None before converting, and return `0.0` in the engine's no-row branch, as documented. Governing statement: [temporal.stats](../ontology/features/temporal.g5.md#temporal.stats).

<a id="bug-tmp-011"></a>
### A temporal write that races a purge or delete of the same triple can leave a live timestamp with no structural edge

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Known to the project (spec 254 sign-off) and proved as model traces; not probed. Severity is lowered one level from High.

Found by: [witness_purge_write_race_drops_row, witness_delete_write_race_drops_row, witness_purge_write_race_rowless_route and witness_purge_write_race_strands_new_triple](results/temporal/20261114T040433Z-prove/receipt.json) in [temporal.rs](models/temporal/temporal.rs) (W-RACE-1, W-RACE-3, W-RACE-4, W-RACE-5; valid outcome `witness_purge_then_write_reasserts_row`); the repair shape is proved as `witness_recheck_closes_race_row_at_decide`, `witness_recheck_closes_race_rowless_route`, `witness_recheck_closes_delete_race` and `witness_recheck_closes_kill_window` (premise P-LOCK); review R2-data R1-7 (check C) and round2-domains R2-2 (its scratch witness is integrated as W-RACE-4); spec 254 `tasks.md:80-81`; R2-data expectation E18.

Reproduced by: none

Expected: a temporal edge of a structural predicate implies its structural edge while any of its timestamps exist (ADR-0009's decision; the spec 254 amendment only adds the reverse, that a marked row goes with the last timestamp).

Observed: `RetireExpired` (or `DeleteTemporalEdge`) decides that no timestamp survives and then retracts the row; a concurrent `InsertEdge` for the same triple sees `^KG("out")` present, trusts it and skips `AssertTemporalRow`'s insert; the retract then deletes the row. The decide step also puts every structural candidate with no surviving timestamp into `^||IVG.TPurge` whether or not it has a row (`TemporalIndex.cls:956-1013`), and `RetractTemporalRows` tests the marker only at its DELETE (`Adjacency.cls:674`), so a triple that had no row when the purge decided (reachable through the ADR-0015 opt-out/opt-in window or [bug-tmp-001](#bug-tmp-001)'s throw) loses the marked row a concurrent writer asserts before the retraction; the model's decide step takes only triples with a marked row and so hides this route. `TemporalIndex` takes no lock. The 254 sign-off lists the race as open: "A temporal write racing a purge on the same triple can leave a new timestamp without its row … `DeleteTemporalEdge` has the same window."

Consequence: a newly written event's edge is invisible to traversal and `MATCH` until another write of the triple asserts the row again.

Repair proposal (not implemented): re-check for surviving timestamps under a per-triple lock before the retract, for every candidate, including triples that had no row when the purge decided, or have the writer assert the row without trusting `^KG("out")` while a purge is running. Related question: [q-tmp-001](open_questions.md#q-tmp-001). Governing statements: [temporal.structural](../ontology/features/temporal.g5.md#temporal.structural), [temporal.purge](../ontology/features/temporal.g5.md#temporal.purge).

<a id="bug-srch-003"></a>
### Building or dropping a BM25 index while documents are inserted leaves its counters inconsistent

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Found by: [witness_build_insert_breaks_n, witness_build_insert_double_df and witness_drop_inside_insert](results/search/20261114T000543Z-prove/receipt.json) in [search.rs](models/search/search.rs) (B-search O1/F2; repair `theorem_locked_build_preserves`); A-search F2 and S3; review R3-platform R1-8, after which the model splits Insert and Delete into their steps, so W-O1c is a trace of the model (it fails with Drop disabled), and the repaired Drop and Build wait for an in-flight writer.

Reproduced by: [search_bm25_build_insert_race](receipts/native/search_bm25_build_insert_race.json) — 209 inserts committed inside Build's 0.39 s window; afterwards, with no Build in flight, 94 terms had a document frequency that disagreed with their postings (for example `df(beta0)=416` with 420 postings). The drop-inside-insert trace (W-O1c) was not probed.

Expected: every index write runs under the index's write lock in a transaction, and the counters are consistent at every committed point (ADR-0007; spec 044 FR-016/FR-018).

Observed: `Build` kills and rewrites the index with no lock and no transaction (`BM25Index.cls:97-175`); an Insert after Build's Kill finds no N and starts a new index (`:387`), Build's `IndexDoc` adds the same document's df again, and Build finally publishes its local N, totalLen and vocab_size (`:160-164`). `Drop` kills with no lock (`:587-591`), so an Insert in flight can resurrect a schema-less index.

Consequence: BM25 scores use wrong document frequencies and N until the next Build; a resurrected index refuses writers as "schema 1".

Repair proposal (not implemented): build under a temporary name and swap under the write lock, or take the lock for Build and Drop. This proves counter consistency only; it does not stop a delete issued during a Build from being lost ([bug-srch-016](#bug-srch-016)). Governing statements: [search.bm25.write_lock](../ontology/features/search.g5.md#search.bm25.write_lock), [search.bm25.counts](../ontology/features/search.g5.md#search.bm25.counts).

<a id="bug-srch-004"></a>
### A second or re-run BM25 upgrade rebuilds an index that is already upgraded, and searches answer nothing meanwhile

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Found by: [witness_concurrent_upgrades and witness_crash_after_flip_rerun](results/search/20261114T000543Z-prove/receipt.json) in [search.rs](models/search/search.rs) (B-search O2/F4; repair `theorem_repaired_upgrade_preserves`, valid outcome `witness_repair_rerun_keeps_index`); A-search F4.

Reproduced by: [search_bm25_upgrade_concurrent](receipts/native/search_bm25_upgrade_concurrent.json) — two `Upgrade` calls on a 6,000-document schema-1 index both ran (`upgraded: 1` each); 205 of 210 searches for a term present in every document answered nothing while they ran; the final index was consistent. The crash-after-flip re-run (W-O2b) was not probed.

Expected: a search never observes an incomplete schema-2 index (spec 044 FR-023, SC-012).

Observed: `Upgrade` tests `already` before it sets the flag and takes the lock (`BM25Index.cls:528-533`) and never re-checks under the lock, so a waiting second call, or a re-run after a death between the flip and the flag's clear, kills `df` and `doc` on a schema-2 index (`:542`). After such a death writers are refused with "is being upgraded" rather than told to re-run the upgrade (`:388-389`).

Consequence: transient empty or partial search answers during a duplicate upgrade; a misleading refusal message after an interrupted one.

Repair proposal (not implemented): re-read `schema` under the lock and skip the rebuild of a schema-2 index. Governing statement: [search.bm25.upgrade](../ontology/features/search.g5.md#search.bm25.upgrade).

<a id="bug-srch-005"></a>
### The engine's fusion gives a result missing from one leg a non-zero, length-dependent score

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Derived from source arithmetic; no run compared the rankings. Severity is lowered one level from High.

Found by: A-search F5 and S1 ([intent](../uplift/ivg-verus-initial/intent/search.md)).

Reproduced by: none

Expected: "each hit scores 1/(c+rank)" and "legs not yet searched contribute nothing" (engine docstring and API reference).

Observed: the engine's RRF scores an absent item at a rank derived from the leg's length (`vector.py:1444-1446`), the SQL procedure uses 1e9 (`schema.py:2536-2537`), and `ivg.retrieve` and `fusion.py` use 0 (`translator.py:3342-3352`; `fusion.py:56-58`).

Consequence: with c=60 and legs of 200, an item at vector rank 1 only (1/61 + 1/320 = 0.01952) outranks one at rank 50 in both legs (2/110 = 0.01818), the reverse of standard RRF; the four entry points rank the same inputs differently.

Repair proposal (not implemented): [simp-srch-001](design_simplification.md#simp-srch-001). Open choice: [search.fusion.absent](../ontology/features/search.g5.md#search.fusion.absent). Governing statement: [search.fusion](../ontology/features/search.g5.md#search.fusion).

<a id="bug-srch-006"></a>
### The embedding queue checks identity against the wrong table, and its IRIS worker writes default-graph entries with no identity check

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** The native probe could not run on Community (no `%Embedding.Config` at the table's width); severity is lowered one level from High.

Found by: [witness_queue_default_graph_misroutes and witness_queue_writes_into_claimed_table](results/search/20261114T000543Z-prove/receipt.json) in [search.rs](models/search/search.rs) (B-search O3/F8; control `queue-routes-default-graph`); A-search F8 and S4.

Reproduced by: none yet — [search_queue_default_graph](receipts/native/search_queue_default_graph.json) is INCONCLUSIVE (no `%Embedding.Config` with VectorLength 768).

Expected: 4.0.0 routing (one table per graph and model; "never derive a name to find a route"); `ClaimPendingBatch` carries `config` so the queue is not "the one write path that escapes the embedding identity registry" (`EmbedQueue.cls:108-111`).

Observed: `enqueue_for_embedding` checks every request against `kg_NodeEmbeddings` of the default graph whatever its graph (`embeddings.py:1838-1842`), refusing a named-graph request that `store_embedding` would route — the check the Python worker's docstring calls the 3.2.0 error (`:1993-1998`). `EmbedQueue.ProcessBatch` sends every default-graph entry to `kg_NodeEmbeddings` whatever its `config`, with no check (`EmbedQueue.cls:278-283, 316`).

Consequence: a model B vector can land in model A's table (read back as A's and compared with A's queries), and valid named-graph requests are refused.

Repair proposal (not implemented): resolve default-graph entries through the registry like named ones (or refuse them unless the entry's model owns `kg_NodeEmbeddings`), and check the target route at enqueue. Governing statements: [search.embedding.queue](../ontology/features/search.g5.md#search.embedding.queue), [search.embedding.check_on_write](../ontology/features/search.g5.md#search.embedding.check_on_write).

<a id="bug-srch-008"></a>
### Under USE GRAPH, fusion reads a BM25 index built for another graph as this graph's

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; severity is lowered one level from High.

Found by: A-search F7.

Reproduced by: none

Expected: an index covers one graph and fusion answers one graph (spec 230 FR-009; the 4.6.0 R192 intent at `translator.py:3258-3261`).

Observed: `_index_graph_rows` returns None whenever `USE GRAPH` is set and never compares the index's recorded graph (`translator.py:3125-3141`); `ivg.retrieve` passes `bm25_name` unchecked (`:3283-3292`).

Consequence: node IDs ranked by graph h's text are joined to graph g's nodes, so g's answer is ranked by another graph's content.

Repair proposal (not implemented): compare the named index's recorded graph with the query's graph and refuse a mismatch. Governing statement: [search.fusion.same_graph](../ontology/features/search.g5.md#search.fusion.same_graph).

<a id="bug-srch-009"></a>
### Named-graph edge vectors placed by the 4.0.0 migration cannot be found by edge vector search

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; severity is lowered one level from High.

Found by: A-search F10.

Reproduced by: none

Expected: a graph's vectors are read where they were stored, from a registered route (4.0.0 routing; "never derive a name to find a route").

Observed: `place_edge_vectors` puts each vector in `kg_EdgeEmbeddings` with `graph_id` = the asserting graph (`statements.py:203-212`) and adds no registry row for `(g, model, edge)`; `edge_vector_search(graph=g)` reads only a registered route and answers `[]` (`vector.py:355-358`; `embeddings.py:676-678`). The manual SQL in `docs/migration/v4.0.0.md:592-597` targets the same place.

Consequence: migrated named-graph edge vectors are invisible, and the next `store_edge_embedding(graph=g)` creates a `kg_eemb_…` route, splitting g's edge vectors across two tables.

Repair proposal (not implemented): register a route for each placed `(graph, model, edge)` pair, or place the vectors into routed tables. Governing statement: [search.routes](../ontology/features/search.g5.md#search.routes).

<a id="bug-srch-010"></a>
### A failed vector leg makes the engine's fusion answer an empty list instead of an error

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Found by: A-search F5 (second part); the product's own [KNOWN_ISSUES](../../docs/KNOWN_ISSUES.md) entry "`kg_RRF_FUSE` answers `[]` when an index search fails" (`docs/KNOWN_ISSUES.md:171-178`, planned for 4.7.1).

Reproduced by: none — the behavior is recorded by the product (KNOWN_ISSUES, measured during 4.7.0); not re-run here.

Expected: a leg that fails is reported as a failure that names the leg, not read as an empty ranking.

Observed: `kg_RRF_FUSE` runs the vector leg and then the BM25 leg inside one `try` and only logs a failure (`vector.py:1382` onward), so a failed vector leg answers `[]` and the BM25 leg never runs. `IRISGraphOperators.kg_RRF_FUSE` defaults `query_vector="[]"` (`operators.py:37`), which fails the vector leg on every text-only call against a declared-width table (`vector.py:487-502`).

Consequence: text-only fusion through the operators answers "nothing matched".

Repair proposal (not implemented): raise naming the failed leg (the planned 4.7.1 change), and skip the vector leg when no query vector is given. Governing statement: [search.fusion.failed_leg](../ontology/features/search.g5.md#search.fusion.failed_leg).

<a id="bug-plt-002"></a>
### Bolt sessions never close the IRIS connection their engine opened

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; whether garbage collection closes the connection was not observed. Severity is lowered one level from High (an outage of every IRIS client once a Community instance's connection licence is exhausted).

Found by: A-platform F-H6 ([intent](../uplift/ivg-verus-initial/intent/platform.md)); re-read for this entry: `BoltSession._get_engine` (`bolt_server.py:391-393`) builds an engine through `cypher_api._make_engine` (`cypher_api.py:137, 157-170`), and the session's `finally` closes only the socket (`bolt_server.py:420-425, 954-960`).

Reproduced by: none

Expected: a server releases what each session acquired; the operator guide sizes Community deployments by connection count.

Observed: each Bolt session (WebSocket or TCP) creates its own engine and IRIS connection on first use and never closes it.

Consequence: a long-running Bolt listener can hold one IRIS connection per finished session; on Community the licence then refuses new connections for every client.

Repair proposal (not implemented): close the session's engine connection in the session's `finally`, or share a pooled engine. No ontology statement covers server resource lifetime; nearest: [access.surfaces](../ontology/concepts/access.g5.md#access.surfaces).

<a id="bug-plt-003"></a>
### Two concurrent first setups can both record their IVG Schema, and the loser keeps writing to its own tables

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Proved on the model; not probed natively because it needs a throwaway namespace and a second schema. Severity is lowered one level from High.

Found by: [witness_concurrent_first_setups_overwrite_the_record and witness_deploy_refusal_is_swallowed](results/platform/20261114T002651Z-prove/receipt.json) in [platform.rs](models/platform/platform.rs) (B-platform B1; `witness_reraise_alone_is_not_enough`, `witness_lock_refuses_the_second_setup`); A-platform F-S1; review R3-platform R1-4, now in the model as `witness_cas_alone_still_releases_the_second_engine`: a compare-and-set record write alone still lets the second setup release its engine and write.

Reproduced by: none

Expected: the first `initialize_schema()` records the name and any engine asking for another is refused (ADR-0016:11; spec 262 FR-005/FR-006); two schemas in one namespace would share one adjacency index and one ledger (ADR-0016:17).

Observed: `_record_and_initialize` reads the record (`_engine/schema.py:2222`), runs a setup ADMIN_GUIDE:102-103 measures at 44-62 s, and writes the record unconditionally if it saw none (`:2309-2312`, `schema_name.py:194-198`), with no lock or compare-and-set. The deploy's own re-check raises `IVGSchemaError` but is caught as a best-effort deploy failure (`_engine/schema.py:2591-2594`). Each engine's guard is released once and never re-checked (`engine.py:1874-1885`).

Consequence: the record names whichever setup wrote last, both engines are accepted, and both write the shared `^KG`, `^NKG` and `^IVG.*` from different tables.

Repair proposal (not implemented): hold `LOCK +^IVG.Deploy("schema")` from the read to the record and re-read before writing; re-raising the deploy refusal alone, or a compare-and-set without a raise that keeps the engine refused, is not enough. The outcome is decided by FR-005, FR-006, SC-006 and ADR-0016 ("instead of sharing globals silently"). Governing statements: [install.schema.concurrency](../ontology/concepts/install.g5.md#install.schema.concurrency), [install.schema.record](../ontology/concepts/install.g5.md#install.schema.record).

<a id="bug-plt-004"></a>
### A merge restore keeps at most one row per graph in the core tables and reports every row restored

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Depends on the live export column order; not run. Severity is lowered one level from High.

Found by: A-platform F-B1 (sub-reader b, re-read by A-platform).

Reproduced by: original two-edge/column-order scenario not rerun; iteration 5 real IRIS parent-key/vector consequence via [snapshot binding](models/snapshot_routes/binding.py) and its retained [receipts](results/snapshot_routes/).

Expected: a merge restore adds the archive's rows that are not already present; the v4.1.0 CHANGELOG (3926-3932) names this dedupe defect and fixes it for the FHIR tables.

Observed: the generic merge guard is `WHERE NOT EXISTS (… WHERE {cols[0]} = ?)` and the count is incremented regardless (`_engine/snapshot.py:1287-1298`); export drops `edge_id` (`snapshot.py:872-874`), so for `rdf_edges` (and `rdf_labels`, `rdf_props`, `docs`) the first column is `graph_id`.

Consequence: saving two edges in G, erasing G and merge-restoring gives one edge, and the report says two were restored.

Repair proposal (not implemented): dedupe on each table's key columns, and count only rows actually inserted. Governing statement: [install.snapshot](../ontology/concepts/install.g5.md#install.snapshot).

Iteration 5: the first-column guard root is also F-1802, whose earlier live evidence is retained. A new native shared-ID/other-graph parent witness loses graph A's parent, so its routed vector fails FK and the final reader is empty; the original complete-archive prediction and DISAGREES receipt are preserved. The Verus restore_parent/load/read chain derives this consequence. This strengthens the inherited root, not a new discovery or a repair.

<a id="bug-plt-005"></a>
### The sample API's Cypher endpoints run translated SQL on a raw cursor, bypassing strict mode and the engine's statement protocol

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Found by: `theorem_strict_paths` (path `ApiSampleCypher`) and `witness_undocumented_bypasses_break_the_contract` in [platform.rs](models/platform/platform.rs) ([prove receipt](results/platform/20261114T002651Z-prove/receipt.json); B-platform W2); A-platform F-H3; A-cypher F3 ([intent](../uplift/ivg-verus-initial/intent/cypher.md)); A-ops candidate finding; reconstruction check 2(a)13 and 2(b)16; review R3-platform R1-11 (an undocumented bypass that contradicts the spec 213 contract).

Reproduced by: [platform_strict_api_sample](receipts/native/platform_strict_api_sample.json) — with the ledger enabled and strict, `POST /api/cypher` of `api.main` committed a `CREATE` (row present, HTTP 200) while the same query through the engine raised `LedgerStrictModeError` and wrote nothing.

Expected: under strict mode `execute_cypher` with an updating clause is refused and changes nothing (spec 213 `contracts/ledger-api.md:82-92`); `read_only.py:3-7` lists these routes under the one write rule; each server call should do what an engine method does.

Observed: `api/routers/cypher.py:130-166` and GraphQL `executeCypher` (`api/gql/schema.py:174-200`) execute `translate_to_sql(...).sql` statement by statement on a bare cursor, skipping `_ledger_check("cypher_dml")` (`_engine/query.py:2300`), `write_txn`, the statement protocol (`__capture_ids__`, `__pin_stage__`, `__GRAPH_*` and others, handled only in `iris_sql_store.py:1617-1777`), result decoding and the native path. The same app mounts example GraphQL mutations such as `updateProtein`, a raw `UPDATE rdf_props` with no graph scope or guard.

Consequence: unrecorded structural writes under strict mode; Cypher `DELETE`, pinned `SET` and all-graphs writes in a multi-graph namespace cannot execute correctly on these routes.

Repair proposal (not implemented): route both through `engine.execute_cypher(read_only=…)`, keeping the hop cap and error redaction. Related: [query.routes](../ontology/features/cypher.g5.md#query.routes). Governing statements: [access.ledger_strict.bypasses](../ontology/concepts/access.g5.md#access.ledger_strict.bypasses), [access.surfaces](../ontology/concepts/access.g5.md#access.surfaces).

<a id="bug-plt-006"></a>
### bulk_delete_adjacency deletes relationships under strict mode without a record

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Found by: `witness_undocumented_bypasses_break_the_contract` in [platform.rs](models/platform/platform.rs) ([prove receipt](results/platform/20261114T002651Z-prove/receipt.json); B-platform W1; control `g-bda-guarded`); review R3-platform R1-11 (an undocumented bypass).

Reproduced by: [platform_strict_bulk_delete_adjacency](receipts/native/platform_strict_bulk_delete_adjacency.json) — with the ledger strict, the call deleted the edge (1 → 0 rows) and `verify()` went from `equal` to `diverges`.

Expected: under strict mode `create_node`, `create_edge` "and the other methods" are refused (USER_GUIDE:1107-1120; spec 213 contract); ADR-0004:81 says the method is removed.

Observed: `bulk_delete_adjacency` (`nodes_edges.py:2301-2338`) has no `_ledger_check` and deletes rows in every graph through `Eraser.EraseEdges`, one call per graph.

Consequence: an unrecorded structural delete in a namespace whose owner turned on strict mode to forbid them.

Repair proposal (not implemented): add the strict check (or remove the deprecated method, as ADR-0004 states). Governing statements: [access.ledger_strict.bypasses](../ontology/concepts/access.g5.md#access.ledger_strict.bypasses), [ledger.strict](../ontology/features/ledger.g5.md#ledger.strict), [erasure.entry-points.single-path](../ontology/features/erasure.g5.md#erasure.entry-points.single-path).

<a id="bug-plt-007"></a>
### The migrations' schema-check waiver also releases the refusal of a mismatched schema

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Found by: `witness_waiver_releases_a_mismatch` (W-S2) in [platform.rs](models/platform/platform.rs) ([prove receipt](results/platform/20261114T002651Z-prove/receipt.json); control `s-waive-checks`); A-platform F-S2; review R3-platform R1-5 (the mismatch case is decided by FR-006, which has no exception; only the no-record case stays open).

Reproduced by: [platform_schema_waiver](receipts/native/platform_schema_waiver.json) — in a namespace recorded `Graph_KG`, an engine on `IVGPROBE` was refused (control), but the migrations' waived engine on `IVGPROBE` was not: its dry runs went ahead (one failed only because `IVGPROBE.RDF_EDGES` does not exist). No table or routine was written.

Expected: a mismatch is refused on first database access, before any write (spec 262 FR-006; ADR-0016:11); the waiver's recorded intent is only "may run before any 4.6.0 setup recorded the schema".

Observed: `graph_scoped_embeddings.py:287-288` and `temporal_structural_rows.py:85-89` build `IRISGraphEngine(conn)` from `IVG_SCHEMA_PREFIX` or the default and call `_waive_schema_check()` → `_schema_check_passed()` (`engine.py:1875-1890`), which releases any pending refusal, a mismatch included.

Consequence: where the other schema's tables exist (spec 262 FR-009's explicit two-schema case), `backfill_structural_rows` would write that schema's `rdf_edges` and the namespace's shared `^KG`, and the 4.0.0 embeddings and `^KG` steps, which address the default schema (`upgrade.py:145-152`), can rebuild the shared `^KG` from the other schema's rows.

Repair proposal (not implemented): waive only when no record exists, or build the migration engine on the recorded schema. Related question: [q-plt-011](open_questions.md#q-plt-011). Governing statements: [install.migration.schema](../ontology/concepts/install.g5.md#install.migration.schema), [install.schema.refusal](../ontology/concepts/install.g5.md#install.schema.refusal).

<a id="bug-plt-008"></a>
### Neo4j-compatible transactions are not transactions: Bolt ROLLBACK keeps the writes and the HTTP transaction endpoint commits statement by statement

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; no driver session was run. Severity is lowered one level from High.

Found by: A-platform F-H1 and F-H2; A-ops candidate finding and test gap (d) (no test references Bolt `BEGIN`/`COMMIT`/`ROLLBACK`).

Reproduced by: none

Expected: a client that rolls back a transaction keeps none of its writes; a transaction batch is atomic (Neo4j semantics the surfaces imitate). No IVG document says otherwise.

Observed: Bolt answers `BEGIN`, `COMMIT` and `ROLLBACK` with SUCCESS only and every `RUN` commits (`bolt_server.py:500-510`); `/db/neo4j/tx/commit` runs each statement as its own `_run_cypher` (`cypher_api.py:391-398`).

Consequence: a driver's `tx.rollback()` reports success while the writes stay; a failing statement in an HTTP batch leaves the earlier ones committed.

Repair proposal (not implemented): map an explicit transaction onto one IVG transaction, or refuse explicit transactions with an error and document per-statement commits. Open part: [access.transactions](../ontology/concepts/access.g5.md#access.transactions).

<a id="bug-plt-009"></a>
### The sample environment file sets IRIS_USER, but the server reads IRIS_USERNAME and silently connects as _SYSTEM

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only (re-read: `.env.sample:30`, `cypher_api.py:170`, `cli.py:47`). Severity is lowered one level from High (the server's login, the real privilege boundary, silently becomes a superuser).

Found by: A-platform F-H5 (sub-reader a, F6).

Reproduced by: none

Expected: the operator guide tells operators to give the server a non-superuser login; the IRIS login is the real privilege boundary.

Observed: `.env.sample:30` sets `IRIS_USER=_SYSTEM`, while `cypher_api._make_engine` and the CLI read `IRIS_USERNAME` with default `_SYSTEM` (`cypher_api.py:170`; `cli.py:47`).

Consequence: an operator who follows the sample and changes `IRIS_USER` to a restricted login still runs the server as `_SYSTEM`, a `%All` superuser, with no warning.

Repair proposal (not implemented): read one documented name (accept both with a warning), and fix the sample. Governing statements: [access.defaults](../ontology/concepts/access.g5.md#access.defaults), [access.iris_boundary](../ontology/concepts/access.g5.md#access.iris_boundary).

<a id="bug-plt-010"></a>
### After the native library is replaced, routing can keep using the old library's proof report

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; severity is lowered one level from High (an unproven reader answering in place of the Owner bypasses the evidence gate).

Found by: A-platform F-A2 (sub-reader c, re-read by A-platform).

Reproduced by: none

Expected: when the library is replaced, routing reads the new library's report on its next load and never routes on the old one's revisions (spec 236 edge case).

Observed: `ArnoAccel.IsAvailable` and `CallFn` reload silently when `lib_path` changes (`ArnoAccel.cls:141-169`), so `_reload_arno_if_needed` (`iris_sql_store.py:867`) never clears `_arno_reader_report`; the unit test resets it by hand (`test_236_reader_routing.py:258-268`).

Consequence: a reader whose revision the new library does not prove can answer PageRank instead of the Owner.

Repair proposal (not implemented): clear the cached report whenever the loaded library path or build changes. Governing statement: [algorithms.routing.reload](../ontology/features/algorithms.g5.md#algorithms.routing.reload).

<a id="bug-plt-011"></a>
### An interrupted BulkLoader node load cannot be resumed: re-loading skips the labels and properties of nodes already written

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; severity is lowered one level from High.

Found by: A-platform F-B5 (sub-reader b).

Reproduced by: none

Expected: "re-loading has to stay idempotent" (`bulk_loader.py:97-103`).

Observed: phase 1 commits node rows; a retry with `skip_existing=True` builds labels and properties only for new nodes (`bulk_loader.py:299-314`).

Consequence: nodes written before the interruption stay without their labels and properties for good, with no error.

Repair proposal (not implemented): on a retry, write labels and properties for every node in the input whose row exists but whose labels and properties do not. Governing statement: [install.bulk_load](../ontology/concepts/install.g5.md#install.bulk_load).

<a id="bug-plt-012"></a>
### BulkLoader ignores the namespace's IVG Schema

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; severity is lowered one level from High.

Found by: A-platform F-B6 (sub-reader b).

Reproduced by: none

Expected: every IVG component follows the recorded IVG Schema (ADR-0016 "followed by everything").

Observed: `BulkLoader` defaults to `schema="Graph_KG"` and `rebuild_all_indices` hard-codes `Graph.KG.*` classes (`bulk_loader.py:41, 54-58, 495`).

Consequence: in a namespace recorded `IVGALT`, rows loaded with `%NOINDEX` stay unindexed or the wrong extent is rebuilt, leaving adjacency and indexes behind the rows.

Repair proposal (not implemented): read the recorded schema and use it for tables and classes. Governing statements: [install.bulk_load.loader](../ontology/concepts/install.g5.md#install.bulk_load.loader), [install.schema.classes_follow](../ontology/concepts/install.g5.md#install.schema.classes_follow).

<a id="bug-plt-024"></a>
### A replacing restore leaves the live search indexes in place and merges the archive's into them

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; no probe covers it. Severity is lowered one level from High.

Found by: review R3-platform R1-6.

Reproduced by: none

Expected: a replacing restore empties every graph and loads the archive; an index counts each document once and its counters agree with its postings.

Observed: `erase_all` does not clear `^BM25Idx`, `^IVF`, `^PLAID` or `^VecIdx` (`Eraser.cls:709-830`), and `_import_global_from_ndjson` only sets nodes.

Consequence: after `restore_snapshot(path)`, a live index the archive lacks still answers for the pre-restore graph, and a same-named index mixes live and archived postings, document frequencies and token records.

Repair proposal (not implemented): empty the named search indexes in the replacing restore's erase (as the erase fix in [bug-srch-001](#bug-srch-001) would), then import the archive's. Governing statements: [search.erasure.indexes](../ontology/features/search.g5.md#search.erasure.indexes), [install.snapshot.scope](../ontology/concepts/install.g5.md#install.snapshot.scope).

<a id="bug-cyp-002"></a>
### The native interpreter tells used relationships apart by CRC-32, so a hash collision drops a legitimate match

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; severity is lowered one level from High.

Found by: A-cypher F1.

Reproduced by: none

Expected: the compiled walk, the interpreter and the SQL path give the same answer (ADR-0014; spec 257 US1); the generated walk compares endpoints and key exactly (plan.md l. 24-26) and SQL compares `edge_id`.

Observed: `Neighbours` keeps the edges a match has used as a comma string of `$ZCRC($ListBuild(src, p, dst, ekey), 7)` and skips an edge whose hash is already there (`Exec.cls:1243-1244`).

Consequence: `MATCH (a:P)-[:K]->(b)-[:K]->(c) RETURN count(*)` over two edges whose tuples collide answers 0 in mode `off` and 1 in `sync` and SQL; node IDs are free text, so collisions can be constructed.

Repair proposal (not implemented): key used edges by the full `$ListBuild`, or hold them in a local array subscripted by the tuple. Governing statement: [query.native.equal-answers](../ontology/features/cypher.g5.md#query.native.equal-answers).

<a id="bug-cyp-003"></a>
### Text shortcuts meant for Neo4j Browser answer unrelated queries with canned rows

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; severity is lowered one level from High.

Found by: A-cypher F4.

Reproduced by: none

Expected: IVG answers the fixed Neo4j Browser metadata queries without running them and gives those answers to no other query.

Observed: any non-write text whose upper-cased form contains `MATCH ()`, `COUNT(*)` and `UNION ALL` answers node and relationship counts over every graph; any text containing `RETURN DISTINCT`, `UNION ALL` and `ENTITY` answers 25 node IDs and 25 predicates (`query.py:1829-1856`, from `9c683292`, v1.47.0). The tests are substring tests over the whole text, string literals included, and ignore `USE GRAPH`; `read_only.answered_without_parsing` does not list them.

Consequence: `MATCH (e:Entity) RETURN DISTINCT e.name AS x UNION ALL MATCH (e:Entity) RETURN DISTINCT e.kind AS x` (an ordinary GraphRAG query) answers canned rows.

Repair proposal (not implemented): match the Browser's exact texts, or parse first. Governing statement: [query.browser-metadata](../ontology/features/cypher.g5.md#query.browser-metadata).

<a id="bug-led-001"></a>
### An adopting verify that races a redaction can append the redacted tenant's IDs after the redaction finished

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; the interleaving was not run. Severity is lowered one level from High.

Found by: A-history F5 (third bullet) ([intent](../uplift/ivg-verus-initial/intent/ledger-history.md)); A-ops hazard (c)2; review R1-core CV-3 and R1-6.

Reproduced by: none

Expected: after a complete redaction no record reachable through IVG holds the target's IDs (ADR-0013; spec 256 FR-001); an adoption records the current differences.

Observed: `verify(adopt=True)` checks the marker once, reads the divergence with no lock and commits the adoption without `expected_head` (`replay.py:806-858`). If it reads after the erase and before the redaction starts, and the redaction then runs to completion, the adoption is admitted (the marker is gone) and writes `delete_*` records naming the tenant's IDs after the redaction revision; `enable()` runs this adoption.

Consequence: tenant IDs re-enter the history after a redaction reported complete; a re-run of the redaction removes them, but nothing tells the operator to re-run.

Repair proposal (not implemented): commit the adoption with the head it read (`expected_head`) so a moved head refuses it, or refuse adoption of records that match a completed redaction's target. Governing statements: [ledger.verify](../ontology/features/ledger.g5.md#ledger.verify), [redaction.purpose](../ontology/features/redaction.g5.md#redaction.purpose).

<a id="bug-led-003"></a>
### A replayed commit applies its post-commit properties again over newer values and returns no statement IDs

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; no retry after a later write was run. Severity is lowered one level from High.

Found by: A-history F13 ([intent](../uplift/ivg-verus-initial/intent/ledger-history.md)); reconstruction check 2(a)11; review R1-core CV-6 and R1-6.

Reproduced by: none

Expected: a retry with a bound idempotency key returns the original outcome with `replayed=True` and changes nothing (spec 213 `contracts/ledger-api.md:26`), including the `stmt_ids` the result carries (`:64`).

Observed: a replay returns `stmt_ids` as `{}` (`Ledger.cls:461`); `post_commit_properties` are excluded from the fingerprint and applied again on a replay (`changeset.py:365-386`; `client.py:431-436`).

Consequence: a client that retries after a timeout overwrites property values written since the original commit with its stale ones, an unrecorded write that verify then reports ([q-010](open_questions.md#q-010)); a retrying caller cannot learn the statement IDs of its own revision.

Repair proposal (not implemented): on a replay, skip the post-commit properties (or apply them only if unchanged since the original revision) and return the original `stmt_ids`. Governing statement: [ledger.idempotency](../ontology/features/ledger.g5.md#ledger.idempotency).

<a id="bug-srch-016"></a>
### A BM25 delete issued while a Build runs is lost, and bug-srch-003's proposed repair does not prevent it

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

Found by: review round2-domains R2-1; the search model's as-built lost-delete witness and the witness that the round-1 repair (lock Build and Drop) still loses it, with the extended repair proved by `theorem_repair_delete_takes_effect` ([prove receipt](results/search/20261114T035601Z-prove/receipt.json); controls `repair-delete-checks-n-first`, `as-built-delete-without-early-return`).

Reproduced by: [search_bm25_delete_during_build](receipts/native/search_bm25_delete_during_build.json) — while a rebuild of a 4,000-document index ran (0.71 s), two node deletes with their `bm25_delete` landed inside the window; both deletes answered False and both documents are still returned by a search after the rebuild.

Expected: a committed delete takes effect; every index write runs under the index's lock in a transaction (ADR-0007).

Observed: `Delete` returns 0 before it takes the lock when `cfg N` is absent (`BM25Index.cls:496-499`), and `Build` sets N only after its scan (`:160`); a `bm25_delete` during a Build therefore answers False ("not in the index"), and if the Build's scan already flushed that document, the Build publishes it.

Consequence: a document the caller deleted stays searchable after the Build.

Repair proposal (not implemented): both changes are required together: run Build and Drop under the index lock ([bug-srch-003](#bug-srch-003)'s repair) **and** test N under that lock in Delete (and Insert). Either alone still loses the delete: `witness_round1_repair_loses_delete` (locked Build, as-built Delete) and the round-3 scratch witness `r3_witness_delete_lock_only_still_loses_delete` (locked Delete, unlocked Build; review round 3 R3-7). The combination is proved by `theorem_repair_delete_takes_effect` under variant `locked_build()` ([search.rs](models/search/search.rs)). Alternatively, a build-and-swap that replays the deletes it overlapped. Governing statements: [search.bm25.write_lock](../ontology/features/search.g5.md#search.bm25.write_lock), [search.bm25.incremental](../ontology/features/search.g5.md#search.bm25.incremental).

<a id="F-0106"></a>
### Property keys of a label mix graphs

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [01.json](../../experiment/playbook-completion/findings/audit/01.json) (live `breadth-a-live-01-install`; inspected `iris_vector_graph/_engine/schema.py:500-515`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-01-install`

- Expected: CONTEXT.md:38-43 / SYS-I2: an all-graphs read is the union of each graph's own answer; content of one graph never answers about another.
- Observed at the pin: graph B's key listed under graph A's label
- Source severity S2, confidence high; module 01; governing page here: `install.`.
- Remedy proposed by the playbook arm (not implemented): Join rdf_labels to rdf_props on (graph_id, s); a test with one id in two graphs.
- Reviewed-design control: `playbook-proofs-d1e` `control_f0106_keys_join_on_id` fails where expected in this run ([receipt](results/playbook-proofs-d1e/20261115T035515Z-control_f0106_keys_join_on_id/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1e/20261115T035416Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0201"></a>
### A graph whose mode is off can hold two edges of one triple

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [02.json](../../experiment/playbook-completion/findings/audit/02.json) (live `breadth-a-live-02-mode-off`; mc `breadth-a-mc-gid_mode-as-built`; mc `breadth-a-mc-gid_mode-reviewed`; control `breadth-a-control-gid_mode`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-02-mode-off`

- Expected: Spec 234 FR-002: with the mode off a triple never gets a second edge; GID-I4.10.
- Observed at the pin: two rows of one triple in a mode-off graph
- Source severity S2, confidence high; module 02; governing page here: `graph. / structure.`.
- Remedy proposed by the playbook arm (not implemented): Guard the single-edge writers on the triple whatever its ekey, or refuse mode off while an edge has a non-zero ekey (or renumber the lone edge to 0).
- Reviewed-design control: `playbook-proofs-d1e` `control_f0201_ekey0_guard` fails where expected in this run ([receipt](results/playbook-proofs-d1e/20261115T035517Z-control_f0201_ekey0_guard/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1e/20261115T035416Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0202"></a>
### The name check is not run at every entry that takes a graph name

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [02.json](../../experiment/playbook-completion/findings/audit/02.json) (live `breadth-a-live-02-identity`; inspected `iris_vector_graph/_engine/nodes_edges.py:968-1015`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-02-identity`

- Expected: ADR-0003 (docs/adr/0003-two-graph-key-derivations.md:119-121): the validator rejects the name '0'.
- Observed at the pin: 2 node rows written under the reserved graph name 0
- Source severity S2, confidence high; module 02; governing page here: `graph. / structure.`.
- Remedy proposed by the playbook arm (not implemented): Call validate_graph_name at every entry (create_node, store_node, store_edge, bulk paths, BulkLoader, USE GRAPH) and write the canonical name.
- Reviewed-design control: `playbook-proofs-d1e` `control_f0202_writer_skips_name_check` fails where expected in this run ([receipt](results/playbook-proofs-d1e/20261115T035512Z-control_f0202_writer_skips_name_check/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1e/20261115T035416Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0204"></a>
### The graph check reports a multigraph's parallel edges as missing adjacency

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [02.json](../../experiment/playbook-completion/findings/audit/02.json) (live `breadth-a-live-02-identity`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-02-identity`

- Expected: Spec 234 SC-005: zero drift on a multigraph after random creates and deletes.
- Observed at the pin: false drift on parallel edges
- Source severity S2, confidence high; module 02; governing page here: `graph. / structure.`.
- Remedy proposed by the playbook arm (not implemented): Compare rows per (s,p,o) with the keyed '#' count.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0206"></a>
### Some Python readers join one graph's ids with another graph's data

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [02.json](../../experiment/playbook-completion/findings/audit/02.json) (live `breadth-a-live-02-identity`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-02-identity`

- Expected: USER_GUIDE.md:466-467 (graph= omitted means the default graph); HD-0201 (assumption): no join of ids from one scope to records of another.
- Observed at the pin: answered the default graph's node, which lacks the label
- Source severity S2, confidence high; module 02; governing page here: `graph. / structure.`.
- Remedy proposed by the playbook arm (not implemented): Hydrate each id from its own graph; give _filter_edges_by_properties and set_edge_weight a graph.
- Reviewed-design control: `playbook-proofs-d1e` `control_f0206_hydrate_from_default` fails where expected in this run ([receipt](results/playbook-proofs-d1e/20261115T035514Z-control_f0206_hydrate_from_default/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1e/20261115T035416Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0208"></a>
### An engine keeps a graph's mode forever, so another engine's change is not seen

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [02.json](../../experiment/playbook-completion/findings/audit/02.json) (live `breadth-a-live-02-identity`; mc `breadth-a-mc-gid_mode-as-built`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-02-identity`

- Expected: Spec 234 FR-002; GID-I4.10.
- Observed at the pin: stale cache wrote a parallel edge into a mode-off graph
- Source severity S2, confidence high; module 02; governing page here: `graph. / structure.`.
- Remedy proposed by the playbook arm (not implemented): Read the mode per statement, expire the cache, or refuse a keyed insert server-side in a mode-off graph.
- Reviewed-design control: `playbook-proofs-d1e` `control_f0208_mode_cached_forever` fails where expected in this run ([receipt](results/playbook-proofs-d1e/20261115T035518Z-control_f0208_mode_cached_forever/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1e/20261115T035416Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0303"></a>
### A direct edge delete leaves the ledger's live link for the edge

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [03.json](../../experiment/playbook-completion/findings/audit/03.json) (live `breadth-a-live-ledger-stmt`; mc `breadth-a-mc-wrt_ledger_stmt-as-built`; mc `breadth-a-mc-wrt_ledger_stmt-reviewed`; control `breadth-a-control-wrt_ledger_stmt`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-ledger-stmt`

- Expected: CONTEXT.md:198-205 (no live statement outlives its content); INV-stmt (semantics/writesets.json).
- Observed at the pin: statement 4 and its tuple entry stay live after the row is gone; the re-created edge inherits it
- Source severity S2, confidence high; module 03; governing page here: `structure. / install.bulk_load`.
- Remedy proposed by the playbook arm (not implemented): Route delete_edge (and the Cypher relationship delete) through Eraser.EraseEdges.
- Reviewed-design control: `playbook-proofs-d1c` `control_f0303_direct_delete_keeps_stmt` fails where expected in this run ([receipt](results/playbook-proofs-d1c/20261115T035830Z-control_f0303_direct_delete_keeps_stmt/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1c/20261115T035754Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0305"></a>
### A bulk write larger than one chunk is not one transaction on the server-loader path

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [03.json](../../experiment/playbook-completion/findings/audit/03.json) (live `breadth-a-live-03-bulk-atomicity`; trace `breadth-a-live-03-bulk-atomicity`; live `breadth-a-live-03-bulk-killed-client`; mc `breadth-a-mc-wrt_bulk_atomic-as-built`; mc `breadth-a-mc-wrt_bulk_atomic-reviewed`; control `breadth-a-control-wrt_bulk_atomic`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-03-bulk-atomicity`, `breadth-a-live-03-bulk-killed-client`

- Expected: USER_GUIDE.md:238-241: each bulk write is a transaction of its own.
- Observed at the pin: 1001 of 2000 nodes committed and visible to another process while the call ran; 2 node-writing transactions, pids ['7440'] (cursor pid 7437)
- Source severity S2, confidence high; module 03; governing page here: `structure. / install.bulk_load`.
- Remedy proposed by the playbook arm (not implemented): Run the loader on the cursor's own process inside the WriteTxn (txn.native()), or one loader call per transaction.
- Reviewed-design control: `playbook-proofs-d1c` `control_f0305_chunks_commit_alone` fails where expected in this run ([receipt](results/playbook-proofs-d1c/20261115T035832Z-control_f0305_chunks_commit_alone/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1c/20261115T035754Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0307"></a>
### The server path of bulk_ingest_edges skips a refused edge without an error

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [03.json](../../experiment/playbook-completion/findings/audit/03.json) (live `breadth-a-live-03-writes`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-03-writes`

- Expected: 4.7.0 row 14: every bulk writer raises for a refused row; the SQL path of bulk_ingest_edges raises GraphWriteError.
- Observed at the pin: the too-wide edge was dropped, count 1, no error
- Source severity S2, confidence high; module 03; governing page here: `structure. / install.bulk_load`.
- Remedy proposed by the playbook arm (not implemented): Width-check in Python before sending; make the loader throw on a refused row.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0308"></a>
### The bulk loader stores a NaN or infinite edge property as JSON no reader accepts

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [03.json](../../experiment/playbook-completion/findings/audit/03.json) (live `breadth-a-live-03-writes`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-03-writes`

- Expected: 4.6.0 R307: create_edge and store_edge refuse NaN/Infinity because IRIS JSON functions then fail every relationship read.
- Observed at the pin: loader stored NaN and the Cypher read failed
- Source severity S2, confidence high; module 03; governing page here: `structure. / install.bulk_load`.
- Remedy proposed by the playbook arm (not implemented): Use _qualifiers_json (allow_nan=False) in the loader.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0403"></a>
### verify_graph reports drift on a graph with parallel edges whose index matches its rows

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [04.json](../../experiment/playbook-completion/findings/audit/04.json) (live `breadth-a-live-02-identity`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-02-identity`

- Expected: Spec 234 SC-005 and spec.md:78-80.
- Observed at the pin: false drift on parallel edges
- Source severity S2, confidence high; module 04; governing page here: `structure.`.
- Remedy proposed by the playbook arm (not implemented): Count rows per triple against the '#' count.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0406"></a>
### Clearing the degree cache alone gives zeros while the warm stamp holds

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [04.json](../../experiment/playbook-completion/findings/audit/04.json) (live `breadth-a-live-04-adjacency`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-04-adjacency`

- Expected: ADR-0012:17: the cache is derived; kill it and every answer is still right.
- Observed at the pin: degree centrality answered 0 for a node with 2 out-edges
- Source severity S2, confidence high; module 04; governing page here: `structure.`.
- Remedy proposed by the playbook arm (not implemented): Make AllWarm require an entry, or document killing ^KG('degw') with ^KG('degc').
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

Iteration 1 comparison: warm_sources models WarmAll's source census and stamp admission, not independent cache deletion. The inherited clear-cache/current-stamp witness remains a product gap; the new proof must not be read as repairing it. The canonical warm owner now states globals-only enumeration and this exception.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0502"></a>
### A temporal write with no time lands at epoch 0, not at the current time

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [05.json](../../experiment/playbook-completion/findings/audit/05.json) (live `breadth-a-live-05-temporal`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-05-temporal`

- Expected: InsertEdge's own rule: a missing time is now (TemporalIndex.cls:51).
- Observed at the pin: single write stored at 0; batch ts 0 stored at 1794609910 (>1767225600)
- Source severity S2, confidence high; module 05; governing page here: `temporal.`.
- Remedy proposed by the playbook arm (not implemented): Send '' for a missing timestamp; stop treating an explicit 0 as missing in BulkInsertCounts.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0504"></a>
### Purges and the row drop delete node rows without the strict-mode check or a record

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [05.json](../../experiment/playbook-completion/findings/audit/05.json) (live `breadth-a-live-ledger`; inspected `iris_vector_graph/_engine/temporal.py:623-641`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-ledger`

- Expected: USER_GUIDE.md:1107-1121 (strict refuses structural writes not made through the ledger); erase_bare_nodes calls the guard (iris_vector_graph/stores/iris_sql_store.py:2823-2825).
- Observed at the pin: purge deleted governed node rows under strict mode
- Source severity S2, confidence high; module 05; governing page here: `temporal.`.
- Remedy proposed by the playbook arm (not implemented): Guard node retirement as erase_bare_nodes is guarded, or skip ledger-known nodes.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0507"></a>
### TemporalIndex.Purge wipes every graph's temporal index and leaves the marked rows

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [05.json](../../experiment/playbook-completion/findings/audit/05.json) (live `breadth-a-live-05-purge`; mc `breadth-a-mc-tmp_mark-as-built`; mc `breadth-a-mc-tmp_mark-reviewed`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-05-purge`

- Expected: ADR-0009 amendment: the marked row goes when the triple's last timestamp goes, in every graph; TMP-B9.13.
- Observed at the pin: both graphs' temporal stores wiped; marked rows and adjacency survive every purge
- Source severity S2, confidence high; module 05; governing page here: `temporal.`.
- Remedy proposed by the playbook arm (not implemented): Retract marked rows in Purge (or remove it) and fix the create_edge_temporal docstring that advises calling it.
- Reviewed-design control: `playbook-proofs-d1c` `control_f0507_purge_keeps_rows` fails where expected in this run ([receipt](results/playbook-proofs-d1c/20261115T035824Z-control_f0507_purge_keeps_rows/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1c/20261115T035754Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0510"></a>
### The millisecond index computes 'now' in seconds

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [05.json](../../experiment/playbook-completion/findings/audit/05.json) (live `breadth-a-live-05-temporal`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-05-temporal`

- Expected: TemporalIndexMS: TSUNIT='ms' (TemporalIndexMS.cls:7-9).
- Observed at the pin: stored at 1794609910 (seconds scale) instead of ~1794609910951
- Source severity S2, confidence high; module 05; governing page here: `temporal.`.
- Remedy proposed by the playbook arm (not implemented): Scale now by 1000 when TSUNIT='ms'.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0601"></a>
### A registry read that fails for any reason lets a vector write through unchecked

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [06.json](../../experiment/playbook-completion/findings/audit/06.json) (probe `breadth-a-probe-local-0101-0601`; inspected `iris_vector_graph/_engine/schema.py:1033-1061`; live `rx-live-priv-vec`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-probe-local-0101-0601`, `rx-live-priv-vec`

- Expected: ADR-0006 (refusable before it happens); FR-014 (enforcement is not opt-in).
- Observed at the pin: privilege error on the registry read turned the identity check off
- Source severity S2, confidence high; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Raise from get_embedding_identity (and the inventory/quarantine reads) unless the registry is absent.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0604"></a>
### The IRIS queue worker marks an entry DONE when no vector was made

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [06.json](../../experiment/playbook-completion/findings/audit/06.json) (live `breadth-a-live-06-vectors`; mc `breadth-a-mc-vec_queue-as-built`; mc `breadth-a-mc-vec_queue-reviewed`; control `breadth-a-control-vec_queue`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-06-vectors`

- Expected: SetResult: DONE carries the result vector, ERROR the message; VEC-I7.18.
- Observed at the pin: entry DONE, no vector, no error
- Source severity S2, confidence high; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Set ERROR with the IRIS message on a failed Prepare, a negative SQLCODE or an empty result.
- Reviewed-design control: `playbook-proofs-d1b` `control_f0604_done_without_vector` fails where expected in this run ([receipt](results/playbook-proofs-d1b/20261115T035751Z-control_f0604_done_without_vector/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1b/20261115T035711Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0607"></a>
### The IVF index's 'cosine' metric is an unnormalised dot product

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [06.json](../../experiment/playbook-completion/findings/audit/06.json) (live `breadth-a-live-06-vectors`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-06-vectors`

- Expected: metric='cosine' is cosine similarity (VecIndex.Cosine normalises, VecIndex.cls:83-90).
- Observed at the pin: dot-product order and scores outside [-1, 1]
- Source severity S2, confidence high; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Normalise at build, insert and query time.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0608"></a>
### Vector index stores do not check width or duplicates

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [06.json](../../experiment/playbook-completion/findings/audit/06.json) (live `breadth-a-live-06-vectors`; mc `breadth-a-mc-vec_ivf-as-built`; mc `breadth-a-mc-vec_ivf-reviewed`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-06-vectors`

- Expected: VEC-B11.14: an id lives in at most one cell; indexed counts distinct ids.
- Observed at the pin: a in cells ['0', '1'], indexed 3
- Source severity S2, confidence high; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Delete before insert across cells, count only new ids, refuse another width.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0610"></a>
### The SQL kg_KNN_VEC answers no rows, without error, for a graph whose vectors are under a declared model

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [06.json](../../experiment/playbook-completion/findings/audit/06.json) (live `breadth-a-live-06-vectors`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-06-vectors`

- Expected: docs/KNOWN_ISSUES.md:702-714 (such a call raises); 4.6.0 R265 (no silent empty answer).
- Observed at the pin: empty answer, no error
- Source severity S2, confidence high; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Have VectorRouteGuard refuse when the graph has any node route other than kg_NodeEmbeddings.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0615"></a>
### A store_embeddings batch refused for a missing node can leave a new empty route behind

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [06.json](../../experiment/playbook-completion/findings/audit/06.json) (live `breadth-a-live-06-vectors`; mc `breadth-a-mc-vec_route_batch-as-built`; mc `breadth-a-mc-vec_route_batch-reviewed`; control `breadth-a-control-vec_route_batch`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-06-vectors`

- Expected: SYS-I3: a refused write changes no store (VEC-X3.9).
- Observed at the pin: refused, yet a 6-wide route and registry row now exist
- Source severity S2, confidence high; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Check every node before resolving the route.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0616"></a>
### The embed selector's label filter crosses graphs, and its exclude pattern escapes without ESCAPE

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [06.json](../../experiment/playbook-completion/findings/audit/06.json) (live `breadth-a-live-06-selector`; live `breadth-a-live-06-embed`; inspected `iris_vector_graph/embed_selector.py:71-112`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-06-selector`, `breadth-a-live-06-embed`

- Expected: Spec 227: selection is graph-scoped (embed_nodes docstring); an exclude pattern skips the matching ids (P-0603).
- Observed at the pin: 'same' embedded via another graph's label; x_1 not excluded
- Source severity S2, confidence high; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Add the graph predicate to the label subqueries and ESCAPE '\' to the LIKE.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0618"></a>
### The ledger's node delete does not reach a default-graph node's routed vectors

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [06.json](../../experiment/playbook-completion/findings/audit/06.json) (live `breadth-a-live-ledger`; inspected `iris_src/src/Graph/KG/LedgerApply.cls:353-370`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-ledger`

- Expected: The engine's delete_node (Eraser.EraseNodeIds) reaches every route; a ledger delete of the same node should too.
- Observed at the pin: ledger delete refused by the route's foreign key
- Source severity S2, confidence high; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Have LedgerApply.DeleteNodeRows delete from every node route the registry names for the default graph.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0701"></a>
### BM25 Build and Drop write without the write lock or a transaction

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [07.json](../../experiment/playbook-completion/findings/audit/07.json) (live `b-07-f0701-race`; live `b-07-fp-writers`; mc `m07-bm25-as-built-I2`; mc `m07-bm25-as-built-I5`; mc `m07-bm25-as-built-settle`; mc `m07-bm25-as-built-quiesced-crash`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-07-f0701-race`, `b-07-fp-writers`

- Expected: ADR-0007 (docs/adr/0007-bm25-df-and-doc-record-schema-2.md:5): schema 2 'does every write under an index-level lock in a transaction'; spec 044 FR-016/FR-018 (specs/044-bm25-index/spec.md:162-164): df, N, totalLen consistent 'at every committed point'; FR-019 (:165) two writers never interleave; decisions.md HD-0701 working answer: serialize index modifications and publish a complete generation or unavailable, including crash.
- Observed at the pin: Live (b-07-f0701-race): an Insert from a second process landed during a 3000-node Build; final N=3000/totalLen=12000 against 3001 doc records summing 12003 (TXT-I2 broken, the inserted doc searchable but uncounted); a concurrent reader saw N=1, schema 2 mid-build. Journal: Build 30008 records, none in a transaction; Insert one transaction. Model: m07-bm25-as-built-I2/-I5 (insert during build), m07-bm25-as-built-settle (Drop during Build leaves a header over no postings), m07-bm25-as-built-quiesced-crash (a stopped build then an Insert breaks I2 even with operators keeping writers apart); revi…
- Source severity S2, confidence high; module 07; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Per HD-0701: Build takes the write lock for its run, writes a shadow generation and publishes it in one step (or sets a building flag that writers refuse); Drop takes the lock; a crash leaves the old generation or an explicit unavailable state.
- Reviewed-design control: `playbook-proofs-d1d` `control_f0701_build_in_place` fails where expected in this run ([receipt](results/playbook-proofs-d1d/20261115T035639Z-control_f0701_build_in_place/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0703"></a>
### A BM25 index goes stale silently when node text changes

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [07.json](../../experiment/playbook-completion/findings/audit/07.json) (live `b-07-f0702-f0703`; inspected `docs/USER_GUIDE.md:893-894`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-07-f0702-f0703`

- Expected: CONTEXT.md:109-114 (a rebuilt store is current or says it is stale; SYS-I8); TXT-I6.
- Observed at the pin: Live (b-07-f0702-f0703): after delete_node('b07_s1') the index built for its graph still answers b07_s1 for its old text; bm25_info is byte-identical before and after (no staleness signal). docs/USER_GUIDE.md:893-894 leaves maintenance to the caller (bm25_insert/bm25_delete).
- Source severity S2, confidence high; module 07; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Either a staleness signal (graph-version token recorded at build and compared in Info/Search) or a recorded SYS-I8 exemption for caller-maintained indexes.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0704"></a>
### A refused index-handle build has already destroyed the old BM25 index

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [07.json](../../experiment/playbook-completion/findings/audit/07.json) (live `b-07-f0704`; mc `m07-bm25-as-built-X2-existing`; mc `m07-bm25-reviewed`; inspected `iris_vector_graph/_engine/vector.py:299-310`; inspected `iris_src/src/Graph/KG/BM25Index.cls:99-111`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-07-f0704`

- Expected: SYS-I3 / TXT-X2: a refused command leaves every store as it was (ontology/07 TXT-X2).
- Observed at the pin: Live (b-07-f0704): engine.index('b07h').build(properties=['no_such_property']) raised IndexNotBuiltError after Build had replaced the 2-document index with an empty header (N=0, no doc records); a search then answers []. Model: m07-bm25-as-built-X2(-existing); reviewed (refuse before writing) passes; control m07-bm25-control-late-refusal caught.
- Source severity S2, confidence high; module 07; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Check the property list and the row count before killing, or build under a temporary name and swap.
- Reviewed-design control: `playbook-proofs-d1d` `control_f0704_late_refusal` fails where expected in this run ([receipt](results/playbook-proofs-d1d/20261115T035640Z-control_f0704_late_refusal/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0706"></a>
### The stopword node __stop__ is listed and writable as a BM25 index

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [07.json](../../experiment/playbook-completion/findings/audit/07.json) (live `b-07-f0706`; live `b-07-fp-writers`; probe `b-07-probe-fusion`; inspected `iris_vector_graph/_engine/vector.py:84-104`; inspected `iris_vector_graph/_validate.py:163-179`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-07-f0706`, `b-07-fp-writers`, `b-07-probe-fusion`

- Expected: decisions.md HD-0704 working answer: reserve the stopword name and reject it at public index-management entry points; spec 044 Edge Cases (specs/044-bm25-index/spec.md:274) names sanitize_identifier.
- Observed at the pin: Live (b-07-f0706): bm25_build('__stop__', ...) accepted (BM25BuildInput accepts it, probe b-07-probe-fusion); Info('__stop__') answers an index; bm25_drop('__stop__') deletes the 77-word stopword list (rebuilt by the next tokenize, b-07-fp-writers). The embedded-mode registry walk (vector.py:84-104) was not exercised: it needs iris.gref inside IRIS embedded Python; over the Native API the registry uses BM25Index.List, which skips the name.
- Source severity S2, confidence high; module 07; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Refuse __stop__ in BM25BuildInput and in Build/Insert/Delete/Drop; skip it in the registry walk; or move the stopwords to their own global.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0709"></a>
### Fused searches can hide a failed leg

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [07.json](../../experiment/playbook-completion/findings/audit/07.json) (live `b-07-f0709`; live `b-07-f0705-f0707`; probe `b-07-probe-fusion`; inspected `iris_vector_graph/_engine/vector.py:1421-1436`; inspected `iris_vector_graph/fusion.py:144-152`; inspected `iris_vector_graph/fusion.py:301-310`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-07-f0709`, `b-07-f0705-f0707`, `b-07-probe-fusion`

- Expected: TXT-B13.7 (the fused search raises and names the leg), TXT-B17.3, TXT-B18.2; spec 044 US7 scenario 9 (text leg contributes); fusion.py:165-168 rationale.
- Observed at the pin: Live (b-07-f0709): engine kg_RRF_FUSE for a graph with docs but no BM25 index answered [] with no error while kg_TXT answered two matches; (b-07-f0705-f0707) a vector leg the route refused (0-dim vector) also dropped the text leg, answering []. Probe (b-07-probe-fusion, product code with stub legs): multi_modal_search drops a raising vector leg silently; adaptive_search answers [] when every path fails. Documented in docs/KNOWN_ISSUES.md:172-181 for the engine path (planned 4.7.1).
- Source severity S2, confidence high; module 07; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Raise naming the leg on every fusion path (the 4.7.1 plan), or return a field naming the legs that ran.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

Iteration 2 corroboration: fusion_ranking now models raw list first-rank selection and the Python wrapper's asymmetric provider catches. Its unit binding runs actual multi_modal_search, retaining empty successful legs but omitting failed vector/graph legs while raising text errors. The providers are substituted; no new IRIS observation or new discovery is claimed. bug-srch-010 concerns the engine surface, while this wrapper evidence belongs to F-0709. Owner: search.fusion.failed_leg and search.fusion.python; no shared repair implemented.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0801"></a>
### Ledger strict mode is a cached client check that fails open (Cypher writes)

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0801`; inspected `iris_vector_graph/ledger/guard.py:20-80`; inspected `iris_vector_graph/_engine/query.py:2299-2301`; run `b-08-run-unit`; mc `b-mc-m11-guard-as-built-ttl`; mc `b-mc-m11-guard-as-built-failopen`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0801`, `b-08-live-f0801-rerun`

- Expected: In strict mode a guarded Cypher write raises LedgerStrictModeError and changes nothing (specs/213-graph-revision-ledger/contracts/ledger-api.md:82-92; CYP-X7.2). Decision HD-0801 (assumption): keep modelling the Python guard, cache and fail-open; the intended refusal still applies.
- Observed at the pin: Live, two IRIS processes on AUDITB (b-08-live-f0801): process A's engine wrote once (guard cached state never-enabled); process B enabled the ledger and set strict (Meta: enabled, strict, head_seq 1); 0.28 s later A ran `CREATE (:B08G {id:'b08_g1'})`, which succeeded (row written, journal: nodes/rdf_labels/rdf_props/^KG) and was not recorded (head_seq 1 before and after). B's fresh engine was refused at once and A was refused after the 5 s TTL (LedgerStrictModeError). Source: guard caches Meta for TTL_SECONDS=5.0 and treats any probe exception as never-enabled (iris_vector_graph/ledger/guard.…
- Source severity S2, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Either document the 5 s window and fail-open in ledger-api.md and USER_GUIDE, or check strict mode fail-closed per write (or server-side in Txn_Begin / a trigger) so raw SQL and other clients are covered (HD-0801 options b/c).
- Reviewed-design control: `playbook-proofs-breadth` `control_f0801_ttl_cache` fails where expected in this run ([receipt](results/playbook-proofs-breadth/20261115T035553Z-control_f0801_ttl_cache/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-breadth/20261115T035528Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0803"></a>
### A WHERE after RETURN is parsed and dropped

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0803`; inspected `iris_vector_graph/cypher/parser.py:287-291`; run `b-08-run-unit`; live `b-08-live-f0803-rerun`; run `b-08-run-unit-rerun`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0803`, `b-08-live-f0803-rerun`

- Expected: CYP-X3.8: a where clause after a return is refused, never read and dropped; openCypher refuses the text.
- Observed at the pin: Live: `MATCH (n:B08L) RETURN n.id AS id WHERE false` returned all 5 B08L nodes, no error. tests/unit/test_lexer_parser_coverage.py:209 test_standalone_where_return asserts nothing (passes, b-08-run-unit).
- Source severity S2, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Raise CypherParseError for WHERE after RETURN (or apply it), with a unit test asserting the refusal.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0805"></a>
### A duplicate edge CREATE between literal endpoints fails the whole query instead of adding nothing

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0805`; mc `m08-txn-as-built-dup`; mc `m08-txn-reviewed`; inspected `iris_vector_graph/cypher/translator.py:10212-10248`; live `b-08-live-f0805-rerun`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0805`, `b-08-live-f0805-rerun`

- Expected: KNOWN_ISSUES.md:25-31: CREATE of an edge that exists returns no error and writes nothing for that edge (CYP-B6.7.6, CYP-B6.7.7); the matched-endpoint path is guarded (translator.py:10306-10365).
- Observed at the pin: Live: after `CREATE (a:B08D {id:'b08_d1'})-[:B08T]->(b:B08D {id:'b08_d2'})`, the query `CREATE (c:B08D {id:'b08_d3'}), (a:B08D {id:'b08_d1'})-[:B08T]->(b:B08D {id:'b08_d2'})` raised GraphWriteError SQLCODE -119 (u_spo_graph_ekey) and its other write (node b08_d3) was rolled back. The same duplicate via matched endpoints (`CREATE (a),(b) CREATE (a)-[:T]->(b) CREATE (a)-[:T]->(b)`) is a silent no-op, as documented. Model m08-txn-as-built-dup violates; reviewed (guarded INSERT) passes.
- Source severity S2, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Guard the literal-endpoint INSERT with NOT EXISTS (as the matched path does), or correct KNOWN_ISSUES; live test over an existing edge.
- Reviewed-design control: `playbook-proofs-d1d` `control_f0805_literal_insert_unguarded` fails where expected in this run ([receipt](results/playbook-proofs-d1d/20261115T035652Z-control_f0805_literal_insert_unguarded/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0810"></a>
### SET n.p = null keeps the key

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0810`; inspected `iris_vector_graph/cypher/translator.py:13648-13665`; live `b-08-live-f0810-rerun`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0810`, `b-08-live-f0810-rerun`

- Expected: openCypher: SET n.p = null removes the property; tests/e2e/test_470_set_null_e2e.py docstring says a literal null removes it.
- Observed at the pin: Live: after SET n.z = null on b08_s, keys(n) = [id, z, name] and properties(n).z = '' (the rdf_props row remains); a computed null deletes.
- Source severity S2, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Delete the row for a literal null too; live test of keys(n).
- Reviewed-design control: `playbook-proofs-d1d` `control_f0810_null_keeps_key` fails where expected in this run ([receipt](results/playbook-proofs-d1d/20261115T035655Z-control_f0810_null_keeps_key/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0813"></a>
### Relationship filters conflate numeric-looking strings and numbers

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0813`; inspected `iris_vector_graph/cypher/translator.py:10232-10238`; live `b-08-live-f0813-rerun`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0813`, `b-08-live-f0813-rerun`

- Expected: openCypher comparison semantics for mixed types (KNOWN_ISSUES.md:118-130, 183-240).
- Observed at the pin: Live: edges {w: '10'} and {w: 9}; WHERE r.w > 8 matched both (the string '10' compared as a number); qualifiers store both as JSON strings ('{"w": "10"}', '{"w": "9"}').
- Source severity S2, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Typed storage (planned 4.8.0) and the TCK typed runs on mixed data.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

Iteration 1 scope reconciliation: the original title 'Values carry no stored type' is too broad at 3eaa79cf. Its live witness concerns relationship qualifier filters and remains valid. Nodes written as numbers retain D/N types, numeric-looking node strings stay strings, and 4.7.0 node filters distinguish them (KNOWN_ISSUES.md:183-240; prop_values.py:110-126,211-231). The new node_read contract/binding corroborates that narrower boundary; it does not withdraw the relationship finding or establish all sorting/arithmetic semantics. Owner: query.conformance and query.values.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0819"></a>
### approx_count_distinct in an all-graphs read merges graphs

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0819`; mc `m08-scope-as-built-hll`; inspected `iris_vector_graph/_engine/query.py:4361-4421`; live `b-08-live-f0819-rerun`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0819`, `b-08-live-f0819-rerun`

- Expected: CYP-I4.14: an approximate count in an all-graphs read counts each graph's nodes apart.
- Observed at the pin: Live: `MATCH (a {node_id:'b08_x'})-[:B08R*1..2]->(m) RETURN approx_count_distinct(m)` took the HLL route (sql CountDistinctKHop, warning HLL-256) and answered 2; the exact count(DISTINCT m) answered 1 (b08_leak is reachable only through graph b08gB's edge from the shared id b08_m).
- Source severity S2, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Take the HLL route only when no named graph has edges (as the k-hop shortcut at query.py:4318-4320 does), with a unit test.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0823"></a>
### An aggregate in a CALL subquery that matches nothing answers 0

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0823`; inspected `iris_vector_graph/cypher/translator.py:14543`; live `b-08-live-f0823-rerun`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0823`, `b-08-live-f0823-rerun`

- Expected: openCypher: an empty max/avg is null, an empty collect is [], count is 0.
- Observed at the pin: Live: max(q.v) -> '0', avg(q.v) -> '0' (should be null); collect(q.v) -> the text '[]' (not 0 as the finding said; a string, not a list); count(q) -> 0 (right).
- Source severity S2, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): COALESCE only for count; live test per aggregate.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0901"></a>
### Two plan shapes with one 32-bit checksum share one compiled class

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [09.json](../../experiment/playbook-completion/findings/audit/09.json) (live `b-09-f0901-collision`; mc `m09-planc-as-built-collide-I3`; mc `m09-planc-as-built-collide-binding`; mc `m09-planc-as-built-collide-progress`; mc `m09-planc-reviewed`; mc `m09-planc-control-shared-name`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-09-f0901-collision`

- Expected: ADR-0014 (docs/adr/0014-native-plans-are-compiled-to-classes-at-run-time.md:19): 'A compiled class answers exactly as the interpreter does'; NAT-I3 (a read never runs code written for another plan shape); NAT-T5.16.
- Observed at the pin: Live (b-09-f0901-collision): a birthday search in IRIS over label names of one length found two labels B09QXAYMSHXLZD / B09QWCSOJEBLDF whose plan shapes share $ZCRC(shape,7) = 1912394325 after 90195 candidates (0.23 s); hashes of the separately compiled shapes: {'B09QXAYMSHXLZD': ['1912394325'], 'B09QWCSOJEBLDF': ['1912394325']}. In job mode (one process) a read of the B09QWCSOJEBLDF shape (its build job compiling) then a read of the B09QXAYMSHXLZD shape left one entry, status ['ok']; the next B09QXAYMSHXLZD read answered [[2]] where the SQL path answers [[1]]; a shadow-mode engine raised Nat…
- Source severity S2, confidence high; module 09; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Name the class by a digest wide enough to rule out collisions (the SHA-256 Digest already computes) or a counter, keep the shape check, and have Build verify under its lock that the entry still holds the shape it compiled before marking it ok.
- Reviewed-design control: `playbook-proofs-d1d` `control_f0901_shared_class_name` fails where expected in this run ([receipt](results/playbook-proofs-d1d/20261115T035702Z-control_f0901_shared_class_name/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0902"></a>
### The interpreter tells relationships apart by a 32-bit checksum

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [09.json](../../experiment/playbook-completion/findings/audit/09.json) (live `b-09-f0902-collision`; mc `m09-used-as-built`; mc `m09-used-reviewed`; mc `m09-used-control-type-only`; inspected `iris_src/src/Graph/KG/Cypher/Exec.cls:1236-1250`; inspected `iris_src/src/Graph/KG/Cypher/Gen.cls:410-433`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-09-f0902-collision`

- Expected: NAT-B1.11 (two different relationships in one match are never taken as the same one); ADR-0014:19 (compiled = interpreted); spec 253 FR-002 (same answer as the SQL path).
- Observed at the pin: Live (b-09-f0902-collision): relationships b09_xxaymshxlzd-[:B09T]->b09_hub and b09_xwcsojebldf-[:B09T]->b09_hub share $ZCRC($LB(src,p,dst,""),7) = 1045711388 (found after 90195 candidates). MATCH (a:B09P)-[:B09T]->(h:B09H)<-[:B09T]-(c:B09P) RETURN count(*): SQL path [[2]], interpreter (off mode) [[0]], compiled walk (sync) [[2]]; a control pair without a collision: SQL [[2]], interpreter [[2]]; shadow mode on the interpreted read: NativeMismatch. Model m09-used-as-built; reviewed exact identity passes.
- Source severity S2, confidence high; module 09; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Keep used relationships as exact subscripts (a local array keyed by $LB(src, p, dst, ekey)) instead of checksums in a string.
- Reviewed-design control: `playbook-proofs-d1d` `control_f0902_crc_identity` fails where expected in this run ([receipt](results/playbook-proofs-d1d/20261115T035705Z-control_f0902_crc_identity/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1001"></a>
### A native reader answers default-graph calls in a namespace where a named graph has edges

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `blocked-access`, not a native reproduction; severity is one level below the mapped High.

**Conditional:** the playbook arm could not reach the deciding state (`blocked-access`).

Found by: playbook arm, [zz-versions.json](../../experiment/playbook-completion/findings/audit/zz-versions.json) (probe `b-10-probe-units`; mc `m10-routes-as-built-pagerank-scope`; mc `m10-routes-as-built-pagerank-scope-default-only-lib`; mc `m10-routes-reviewed`; mc `m10-routes-control-no-probe`; inspected `iris_vector_graph/arno_readers.py:257-280`)

Reproduced by: none (blocked-access)

- Expected: spec 236 FR-014a: a native reader 'MUST be used only for the graph scope its proof covers' (specs/236-arno-callout-adoption/spec.md:268-272); ALG-I3 / SYS-I2 (a default-graph answer never mixes in a named graph's edges); the BFS route and the ^NKG tiers probe for named-graph edges (iris_vector_graph/stores/iris_sql_store.py:1842-1858, :3322).
- Observed at the pin: Source at the pin: arno_readers.route takes no named-graph input and answers native for graph '' (iris_vector_graph/arno_readers.py:257-280); _execute_pagerank routes with no named_graph_with_edges probe (iris_sql_store.py:2388-2400). Probe b-10-probe-units ran the pin's route(): 'native' for graph '' with no parameter that could carry named-graph edges. Model m10-routes-as-built-pagerank-scope finds the mixed answer only with a library whose reader is graph-blind; with a graph-0-only reader (m10-routes-as-built-pagerank-scope-default-only-lib) it passes: the outcome hinges on the open premis…
- Source severity S1, confidence medium; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Route to a native reader only when named_graph_with_edges() is None (as BFS and the ^NKG tiers do), or add a named-graph fixture to the reader gate and record graph scope in the proof; then a live test in USER with arno-callout 1.2.1 loaded and a named graph's edges.
- Recorded in 10.json, zz-versions.json; the later file's record is used.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1003"></a>
### Global PageRank lists at most 10,000 nodes from its owner and every node from the native reader

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [10.json](../../experiment/playbook-completion/findings/audit/10.json) (live `b-10-live-cap`; mc `m10-routes-as-built-pagerank-cap`; mc `m10-routes-reviewed`; mc `m10-routes-control-owner-cap`; inspected `iris_src/src/Graph/KG/PageRank.cls:506-520`; inspected `iris_vector_graph/stores/iris_sql_store.py:2388-2400`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-10-live-cap`

- Expected: The method's docstring: every node takes part and the scores sum to 1 over node_count() nodes (iris_vector_graph/_engine/algorithms.py:741-760); decisions.md HD-1004 (assumption): the same result contract on every route, uncapped pending a documented limit, any truncation exposed.
- Observed at the pin: Live (b-10-live-cap): with 10051 default-graph nodes (hub b10_h -> 10,050 nodes, pin's bulk API) kg_PAGERANK() on the owner route answered 10000 rows summing to 0.994926; 51 nodes were silently not listed; PageRank.PageRankGlobalJson itself answered 10000 rows. The native route (every node, iris_sql_store.py:2396-2399) is blocked (arno-callout absent). Model m10-routes-as-built-pagerank-cap reproduces the route disagreement.
- Source severity S2, confidence high; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Decide HD-1004; make both routes cut (or not cut) the same way and say so in the answer (a truncation flag or a documented top_k).
- Reviewed-design control: `playbook-proofs-d1e` `control_f1003_owner_cap` fails where expected in this run ([receipt](results/playbook-proofs-d1e/20261115T035522Z-control_f1003_owner_cap/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1e/20261115T035416Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

Iteration 3 scope reconciliation: algorithms.cache.pagerank separates COUNT:MAX cache admission from the numerical/every-node promise. PageRankGlobalJson:506-520 still caps output at 10000; the new native Python binding only forwards normalized fixture scores and does not rerun this live cap witness. No normalization or unlimited-output proof is claimed; HD-1004 remains authoritative as previously recorded.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1004"></a>
### A cached personalized PageRank answer misses a start node written or removed without an edge

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [10.json](../../experiment/playbook-completion/findings/audit/10.json) (live `b-10-live-cache`; probe `b-10-probe-units`; mc `m10-cache-as-built-ppr`; mc `m10-cache-reviewed-ppr`; mc `m10-cache-control-no-bump-on-create`; mc `m10-cache-as-built-pagerank`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-10-live-cache`, `b-10-probe-units`

- Expected: ALG-B2.19 (a cached answer changes when a start node is added to the graph or removed from it); ALG-B16.11 (after any write a cached answer equals a fresh computation); ALG-I4.
- Observed at the pin: Live (b-10-live-cache): kg_PERSONALIZED_PAGERANK(['b10_x']) answered {} before b10_x existed and the answer was cached (^IVG.AlgoCache(0,'ppr',...)); create_node('b10_x') with no edge wrote only nodes/rdf_props and moved no token; the same call then answered {} from the cache while a fresh run (after AlgoCache.InvalidateAll) answered {'b10_x': 1.0, 'b10_a': 0.0, 'b10_b': 0.0}. Refuted part: deleting the edgeless start node moved ^KG('__version') (7128 -> 7131 for a labelled node; edgeless 7125 -> 7127) because delete_node runs Graph.KG.Eraser.EraseNodeIds, whose InvalidateDerived bumps the to…
- Source severity S2, confidence high; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Put the node-set token in the PPR key (as global PageRank does since R313) or raise a node token on every node write and read it inside AlgoCache.Lookup; a live test that creates an edgeless start node after a cached call.
- Reviewed-design control: `playbook-proofs-d1e` `control_f1004_create_moves_no_token` fails where expected in this run ([receipt](results/playbook-proofs-d1e/20261115T035446Z-control_f1004_create_moves_no_token/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1e/20261115T035416Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

Iteration 3 comparison: the create-an-edgeless-start-node trigger/effect is also bug-plt-017; the two source records are retained, not counted as separate new discoveries. The refuted deletion premise here is not restored. New pagerank_admission is global PageRank only and explicitly does not cover PPR; its node-key success cannot repair or refute this PPR finding.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1006"></a>
### Subgraph vectors are read by node id in every graph

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [10.json](../../experiment/playbook-completion/findings/audit/10.json) (live `b-10-live-scope2`; inspected `iris_vector_graph/_engine/algorithms.py:850-880`; inspected `iris_vector_graph/schema.py:429-437`; inspected `iris_src/src/Graph/KG/Subgraph.cls:6-11`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-10-live-scope2`

- Expected: ALG-I3 (a default-graph call never mixes in a named graph's content); the table is keyed (graph_id, node_id) (iris_vector_graph/schema.py:429-437).
- Observed at the pin: Live (b-10-live-scope2; the first run's fixture violated the (graph_id, node_id) foreign key): kg_NodeEmbeddings held rows [['', 'b10_s', '1,0,0,0'], ['b10g1', 'b10_s', '0,0,0,1']] for b10_s (in both graphs); kg_SUBGRAPH(['b10_s'], include_embeddings=True) returned [0.0, 0.0, 0.0, 1.0] (default-graph vector [1.0, 0.0, 0.0, 0.0], named-graph vector [0.0, 0.0, 0.0, 1.0]).
- Source severity S2, confidence medium; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Add graph_id = '' to the read, correct the comment that the walk is namespace-wide, and test with two graphs.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1007"></a>
### Degree centrality counts parallel edges on out-edges but not on in-edges

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [10.json](../../experiment/playbook-completion/findings/audit/10.json) (live `b-10-live-scope2`; mc `m10-degree-as-built`; mc `m10-degree-reviewed`; mc `m10-degree-control-distinct-out`; inspected `iris_src/src/Graph/KG/Centrality.cls:88-139`; inspected `iris_src/src/Graph/KG/Adjacency.cls:203-206`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-10-live-scope2`

- Expected: CONTEXT.md:103-108 (parallel edges each count towards degree); ALG-B5.4.
- Observed at the pin: Live (b-10-live-scope2; the first run's engine.create_edge kept one edge per triple): named graph b10gm in multigraph mode (engine.set_multigraph, restored after), three parallel b10_p -> b10_q edges by Cypher CREATE and one b10_r -> b10_q (4 edge rows, 1 parallel triple): degree_centrality out {'b10_p': 3, 'b10_r': 1, 'b10_q': 0} (sum 4), in {'b10_q': 2, 'b10_p': 0, 'b10_r': 0} (sum 2). Model m10-degree-as-built violates the handshake invariant; m10-degree-reviewed passes; control caught.
- Source severity S2, confidence high; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Count in-degree from the out mirror's multiplicity; a multigraph test.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1103"></a>
### An adoption is not tied to the head it compared

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [11.json](../../experiment/playbook-completion/findings/audit/11.json) (live `b-11-live-f1103`; live `b-11-live-f1103-reenable-race`; mc `m11-adopt-as-built-commit`; mc `m11-adopt-as-built-two-enables`; mc `m11-adopt-reviewed`; inspected `iris_vector_graph/ledger/replay.py:806-857`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-11-live-f1103`, `b-11-live-f1103-reenable-race`

- Expected: LED-B1.20 (an adoption records only the unrecorded writes it was built from; nothing a later commit did); the history replays to the live store (spec 213 verify); decisions.md HD-1401 (verify needs a coherent cut across its reads).
- Observed at the pin: Live AUDITB with a forced interleaving at a Python call boundary in the harness (replay.read_canonical wrapped; no product file changed): a commit of b11_a-B11T-b11_b (stmt 1, seq 2) landed after verify(adopt=True) had read the records up to its head and before it read the stores; the adoption revision (seq 3) recorded create_rel stmt 1 a second time, so LED-B1.20 is violated (b-11-live-f1103). verify() afterwards still answered equal (replay is idempotent on the statement id), so the 'history no longer replays' impact was not observed for this schedule. Double adoption by two concurrent re-e…
- Source severity S2, confidence high; module 11; governing page here: `ledger.`.
- Remedy proposed by the playbook arm (not implemented): Send the verified head as expected_head on the adoption and re-verify on StaleHeadError (or compute the adoption under the head lock on the server); re-read the state under the head lock in Enable so two re-enables cannot both answer adoption_needed.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1105"></a>
### Deleting a node that only a named graph holds records a delete that removed nothing

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [11.json](../../experiment/playbook-completion/findings/audit/11.json) (live `b-11-live-findings`; live `ib-HD1101-namedonly`; inspected `iris_src/src/Graph/KG/LedgerApply.cls:79-84`; inspected `iris_src/src/Graph/KG/LedgerApply.cls:354-385`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-11-live-findings`, `ib-HD1101-namedonly`

- Expected: LED-B5.3 (a node delete record is written only when a node row was deleted); a commit the ledger accepts replays to the store; decisions.md HD-1101 (assumption: ledger node mutations are scoped to the default-graph row; a named-only id cannot satisfy the existence precondition).
- Observed at the pin: Live AUDITB (b-11-live-findings): b11_named only in graph b11g; ledger delete_node committed (revision with a delete_node record whose prior is {labels:[],props:{}}), the named row stayed, verify() diverges on b11_named; set_property committed and wrote an orphan default-graph rdf_props row; add_label refused 'insert label failed' (fk_labels_node). Matches intent lane run ib-HD1101-namedonly (AUDITIB).
- Source severity S2, confidence high; module 11; governing page here: `ledger.`.
- Remedy proposed by the playbook arm (not implemented): Per HD-1101: node changes test existence of the default-graph row (NodeExists with the default-graph predicate) and refuse node_not_found otherwise, keeping the graph-blind check for edge end nodes; a live test with a named-only id.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1107"></a>
### A commit accepts any revision kind

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [11.json](../../experiment/playbook-completion/findings/audit/11.json) (live `b-11-live-findings`; inspected `iris_vector_graph/ledger/client.py:381-405`; inspected `iris_src/src/Graph/KG/Ledger.cls:424`; inspected `iris_src/src/Graph/KG/Ledger.cls:488-498`; live `rx-live-11`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-11-live-findings`, `rx-live-11`

- Expected: changeset.schema.json:219 (kind enum genesis | adoption | changeset; spec 256 adds redaction) and LED-B4.9.2 (a commit takes only changeset and adoption); LED-B4.9.1 size limit.
- Observed at the pin: Live AUDITB (b-11-live-findings): GraphLedger.commit(kind='genesis'), kind='redaction' and kind='b11-bogus' were accepted and stored with that kind; with max_ops 3 a 4-op changeset was refused too_large while the same size under kind 'b11-bogus' was accepted (size check only for changeset, Ledger.cls:488-498); a kind='adoption' commit of a hand-made create_node item for b11_ghost wrote a record with no store row and verify() diverges.
- Source severity S2, confidence high; module 11; governing page here: `ledger.`.
- Remedy proposed by the playbook arm (not implemented): Refuse kinds other than changeset and adoption in CommitInTxn (keep adoption for the client's verify), and validate adoption items against the stores or restrict adoption to the verify path; a unit test.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1108"></a>
### Two write paths skip the strict-mode guard

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [11.json](../../experiment/playbook-completion/findings/audit/11.json) (live `b-11-live-footprints-2`; live `ib-HD1103-bulk-delete-adjacency`; live `c16-s3-graphql-sample-api`; mc `m11-guard-as-built-unguarded`; mc `m11-guard-reviewed`; inspected `iris_vector_graph/_engine/nodes_edges.py:2301-2339`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-11-live-footprints-2`, `ib-HD1103-bulk-delete-adjacency`, `c16-s3-graphql-sample-api`

- Expected: docs/USER_GUIDE.md:1107-1109 (strict mode refuses create_node, create_edge and the other methods); ledger-api.md:82-93 lists the guarded calls and names only BulkLoader and raw SQL as unguarded; decisions.md HD-1103 (supported: client-side guard on the specified methods; inventory uncovered Python paths).
- Observed at the pin: Live AUDITB (b-11-live-footprints-2): strict on; engine.create_node refused (LedgerStrictModeError) but engine.bulk_delete_adjacency(['b11_a']) deleted the recorded edge b11_a-B11S-b11_b through Graph.KG.Eraser.EraseEdges; the journal shows rdf_edges, ^KG, ^NKG and ^IVG.Ledger stmt/tuple written in the eraser's own transaction with no head lock; verify diverges on that rel. GraphQL create_protein called directly on this connection failed SQLCODE -30 (unqualified SQLUSER.NODES), so that write did not land here; the resolver has no guard (api/gql/resolvers/mutation.py:23-230) and the sample API…
- Source severity S2, confidence high; module 11; governing page here: `ledger.`.
- Remedy proposed by the playbook arm (not implemented): Call the guard in bulk_delete_adjacency and the GraphQL mutations (or document them as unguarded next to BulkLoader and raw SQL); extend tests/integration/test_ledger_us05_compat.py::test_every_guarded_api_is_rejected_and_nothing_changes.
- Reviewed-design control: `playbook-proofs-breadth` `control_f1108_unguarded_bulk_delete` fails where expected in this run ([receipt](results/playbook-proofs-breadth/20261115T035559Z-control_f1108_unguarded_bulk_delete/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-breadth/20261115T035528Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1201"></a>
### A graph erasure removes the statement entry of an edge a concurrent ledger commit creates

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [12.json](../../experiment/playbook-completion/findings/audit/12.json) (run `live-f1201-reproduced`; run `live-erase-vs-commit-fk`; run `live-erase-vs-commit-emptygraph`; original `mc:erasure-as-built`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM)

- Expected: No recorded live edge loses its statement entry (ERS-I3; ADR-0004: 'no live statement outlives its content' and the ledger's statement map tracks every live recorded edge). HD-1201 working answer: erase serializes with same-target commits.
- Observed at the pin: Reproduced on the pin 8/8: EraseGraph takes no ledger head lock (Eraser.cls:47-261) and EraseLedgerFor (Eraser.cls:1117-1144) dirty-reads every statement entry; it killed the committer's ^IVG.Ledger("stmt",4001) and tuple after the commit wrote them; the edge u-R-v, its nodes and adjacency stayed live in G with no statement entry. Journal order is the oracle. With an edge in the graph the same race instead makes the erase fail with an FK error and roll back (8/8); with a short statement scan the eraser wins the race (8/8).
- Source severity S2, confidence high; module 12; governing page here: `erasure.`.
- Remedy proposed by the playbook arm (not implemented): Serialize graph erasure with ledger commits into the same graph (for example take the ledger head lock, or a per-graph lock both take, around the statement cleanup), or make the cleanup remove only statements whose edge rows the same transaction deleted.
- Reviewed-design control: `playbook-proofs-d9c` `control_f1201_erase_unlocked` fails where expected in this run ([receipt](results/playbook-proofs-d9c/20261115T040828Z-control_f1201_erase_unlocked/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d9c/20261115T041012Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1401"></a>
### verify() reports divergence after a logged detach-delete involving named-graph edges

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [14.json](../../experiment/playbook-completion/findings/audit/14.json) (run `live-native-rerun-1314`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM)

- Expected: RPL-B7: verify says equal when every change went through the ledger.
- Observed at the pin: Fresh rerun: verify on the built world already diverges, only on tenantA|n3 (the detach delete kept its named-graph row).
- Source severity S2, confidence high; module 14; governing page here: `ledger.readers`.
- Remedy proposed by the playbook arm (not implemented): Make the ledger's detach-delete and verify agree on node identity across graphs (HD-1401/HD-1101).
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1507"></a>
### The bridge anchor lookup matches a node of that id in any graph

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [15.json](../../experiment/playbook-completion/findings/audit/15.json) (live `c15-live-bridge`; inspected `iris_vector_graph/_engine/fhir.py:444-481`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c15-live-bridge`

- Expected: migrate_fhir_bridges_to_crosswalk documents 'Bridges point at default-graph nodes' (fhir_graph.py:650-652); INT-B1.3; SYS-I2.
- Observed at the pin: Live (c15-live-bridge): with node c15:anchor only in named graph c15g3 and a bridge row C15CODE1 -> c15:anchor, get_kg_anchors(['C15CODE1']) returned ['c15:anchor'] (JOIN nodes ON node_id only, fhir.py:470-477).
- Source severity S2, confidence high; module 15; governing page here: `fhir.`.
- Remedy proposed by the playbook arm (not implemented): Add COALESCE(n.graph_id,'') = '' (the bridges' graph) to the join.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1508"></a>
### The Cypher API answers a failed FHIR-graph anchor read as a bridge lookup

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [15.json](../../experiment/playbook-completion/findings/audit/15.json) (live `c15-live-anchors`; inspected `iris_vector_graph/cypher_api.py:327-347`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c15-live-anchors`

- Expected: Spec 235 FR-021 uses the bridge only when no synced FHIR graph holds the patient; the 4.6.0 rule is that a failed read reaches the caller (CHANGELOG 4.6.0, commit 2d1d6f46); INT-C4.6.
- Observed at the pin: Live (c15-live-anchors), the /api/cypher handler called in-process with the identity-checked AUDITC engine: for fhir_graph='fhir:c15:none' engine.fhir_patient_anchors raises FHIRGraphError ('IndexedTokenParams: FHIR graph ... is not registered'), and for fhir_patient_id='bad id!' it raises ValueError; in both cases the handler answered 200 status OK, anchor_source 'fhir_bridge', 0 anchors, and ran the query with $patient_anchors = [] (cypher_api.py:331-336 'except Exception').
- Source severity S2, confidence high; module 15; governing page here: `fhir.`.
- Remedy proposed by the playbook arm (not implemented): Catch only the 'no FHIR graph tables' case (already answered by fhir_patient_anchors) and let other errors reach the response as 400/500.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1601"></a>
### Bolt BEGIN, COMMIT and ROLLBACK do nothing; every RUN commits at once

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [16.json](../../experiment/playbook-completion/findings/audit/16.json) (live `c16-s1-cypher-http`; inspected `iris_vector_graph/bolt_server.py:500-510`; inspected `iris_vector_graph/bolt_server.py:567-622`; mc `cmc-unit-bolt-as-built-atomic`; mc `cmc-unit-bolt-as-built-once`; mc `cmc-unit-bolt-reviewed`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c16-s1-cypher-http`

- Expected: A Bolt explicit transaction is atomic: ROLLBACK discards the writes made since BEGIN (Bolt protocol, P-1612; API-B9.10 'A rollback should undo the writes made since the driver began its transaction').
- Observed at the pin: Live (c16-s1-cypher-http): neo4j driver 6.4.1 began a transaction, ran CREATE c16:b1, rolled back; the node is still there (count 1). The journal shows the RUN's write committed in its own outermost IRIS transaction before ROLLBACK arrived. A managed transaction (execute_write) whose second statement fails keeps the first statement's node c16:b2. Source: BEGIN/COMMIT answer SUCCESS and ROLLBACK only clears pending rows (iris_vector_graph/bolt_server.py:500-510); RUN calls engine.execute_cypher, which commits (bolt_server.py:567-591).
- Source severity S2, confidence high; module 16; governing page here: `access.`.
- Remedy proposed by the playbook arm (not implemented): Run a Bolt transaction's RUNs inside one engine write transaction and commit/roll it back on COMMIT/ROLLBACK, or refuse BEGIN with a FAILURE that says explicit transactions are unsupported.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1602"></a>
### Bolt PULL {n} drops every row after the first n

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [16.json](../../experiment/playbook-completion/findings/audit/16.json) (live `c16-s1-cypher-http`; inspected `iris_vector_graph/bolt_server.py:624-660`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c16-s1-cypher-http`

- Expected: PULL {n} returns at most n records and has_more=true while rows remain (Bolt protocol, P-1612; API-B9.11).
- Observed at the pin: Live (c16-s1-cypher-http): MATCH over three C16F nodes with driver fetch_size=2 returned 2 rows (c16:f1, c16:f2); the default fetch size returned 3. Source: rows[:n], SUCCESS without has_more, pending result discarded (iris_vector_graph/bolt_server.py:624-660).
- Source severity S2, confidence high; module 16; governing page here: `access.`.
- Remedy proposed by the playbook arm (not implemented): Keep the remainder and answer has_more: true until drained; unit test PULL {n:2} over three rows.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1607"></a>
### Two Cypher entries of the sample API bypass the engine and answer differently

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [16.json](../../experiment/playbook-completion/findings/audit/16.json) (live `c16-s3-graphql-sample-api`; live `c16-s1-cypher-http`; inspected `api/routers/cypher.py:118-166`; inspected `api/gql/schema.py:149-230`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c16-s3-graphql-sample-api`, `c16-s1-cypher-http`

- Expected: API-B5.8: the route answers each query as the engine's execute_cypher does (4.7.0 row 22 rewrite).
- Observed at the pin: Live (c16-s3-graphql-sample-api) with UNWIND $p AS e RETURN e, p=['[2]',[2],true,'1']: engine.execute_cypher and the Cypher HTTP server (c16-s1) answer [['[2]'],[[2]],[true],['1']]; the sample API's POST /api/cypher answers 500 'query execution failed' and its GraphQL executeCypher answers data {error: '<PARAMETER ERROR> Invalid number of parameters'}. Source: api/routers/cypher.py:118-166 and api/gql/schema.py:170-230 call parse_query/translate_to_sql directly, skipping rewrite_ambiguous_param_unwind (iris_vector_graph/_engine/query.py:1900).
- Source severity S2, confidence high; module 16; governing page here: `access.`.
- Remedy proposed by the playbook arm (not implemented): Call engine.execute_cypher from both entries (keeping the hop cap), or apply the same rewrite; parity test across the Cypher entries.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1609"></a>
### The FHIR event route's writes are not all-or-nothing

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [16.json](../../experiment/playbook-completion/findings/audit/16.json) (live `c16-s3-graphql-sample-api`; inspected `api/routers/fhir_event.py:283-365`; mc `cmc-unit-http-as-built-atomic (analogous shape: several committed writes per request; not a model of this route)`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c16-s3-graphql-sample-api`

- Expected: API-B7.4 / SYS-I4: the writes of one call all happen or none do.
- Observed at the pin: Live (c16-s3-graphql-sample-api): POST /fhir-event/ with graph c16g2 and date 1960-01-01 answered 500 ('IRIS write failed: ... TemporalEdgeInput timestamp >= 0') after both create_node calls committed; nodes c16:fe1 and c16:fp1 remain in c16g2. Journal: two outermost commits on the server's IRIS process before the refusal. A successful call journals three separate outermost commits, and the temporal index entries (^KG tout/tin/tlast/bucket/tagg) are written outside any transaction. Source: api/routers/fhir_event.py:318-346.
- Source severity S2, confidence high; module 16; governing page here: `access.`.
- Remedy proposed by the playbook arm (not implemented): Validate first and run the three writes in one engine transaction (write_txn); a unit test that a failed edge write leaves no node.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1610"></a>
### The Neo4j HTTP commit route runs its statements one by one

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [16.json](../../experiment/playbook-completion/findings/audit/16.json) (live `c16-s1-cypher-http`; inspected `iris_vector_graph/cypher_api.py:379-410`; mc `cmc-unit-http-as-built-atomic`; mc `cmc-unit-http-reviewed`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c16-s1-cypher-http`

- Expected: Neo4j's /db/neo4j/tx/commit is a begin-and-commit-in-one-request transaction: all statements or none (P-1612); API-B8.6.1.
- Observed at the pin: Live (c16-s1-cypher-http): three statements (CREATE c16:t1; an unparsable line; CREATE c16:t3) answered 400 with one SyntaxError, and both c16:t1 and c16:t3 are committed — the third ran after the failure. Journal: two separate outermost commits on two different IRIS processes: the failed statement made _run_cypher reset the engine (closing the connection) and retry, so statement 3 ran on a new connection. Source: iris_vector_graph/cypher_api.py:379-410, :239-250.
- Source severity S2, confidence high; module 16; governing page here: `access.`.
- Remedy proposed by the playbook arm (not implemented): Run the statements in one engine transaction and roll back on the first error (Neo4j stops there), or document the route as non-atomic.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1614"></a>
### The demo server's write routes need no key

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [16.json](../../experiment/playbook-completion/findings/audit/16.json) (live `c16-s8-followup`; inspected `src/iris_demo_server/app.py:1-22`; inspected `src/iris_demo_server/routes/fhir.py:503-533`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c16-s8-followup`

- Expected: CHANGELOG.md:994-996 says every app needs the key; API-B13.2.
- Observed at the pin: Live (c16-s8-followup): demo server started with IVG_API_KEY set; without the key GET /api/status/none answered 404 and POST /api/fhir/live/add answered 400 (validation reached, not 401). Source: src/iris_demo_server/app.py:1-22 adds no ApiKeyMiddleware; routes/fhir.py:503-533 write to the FHIR repository and start a sync; __main__ binds 0.0.0.0:8200 (app.py:503-504).
- Source severity S2, confidence high; module 16; governing page here: `access.`.
- Remedy proposed by the playbook arm (not implemented): Add ApiKeyMiddleware and bind 127.0.0.1 by default, or document the demo server as presenter-only.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1615"></a>
### The fraud server's vector lookup always falls back to zeros

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [16.json](../../experiment/playbook-completion/findings/audit/16.json) (live `c16-s5-fraud-sql-stream`; inspected `src/iris_fraud_server/app.py:246-279`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c16-s5-fraud-sql-stream`

- Expected: API-B13.7: the fraud score reads the payer's stored vector.
- Observed at the pin: Live (c16-s5-fraud-sql-stream): the statement as written fails in AUDITC with SQLCODE -30 (table SQLUSER.KG_NODEEMBEDDINGS not found); schema-qualified it fails with SQLCODE -29 (field EMBEDDING not found); the intended form (emb, Graph_KG, default graph) prepares. Source: src/iris_fraud_server/app.py:246-279 also calls fetchone() on an iris.sql.exec result (none exists, app.py:211) and returns np.zeros(768) on any error.
- Source severity S2, confidence high; module 16; governing page here: `access.`.
- Remedy proposed by the playbook arm (not implemented): Read emb from the schema-qualified table for the default graph and iterate the result; a test that a stored vector reaches the score.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1709"></a>
### deploy/README.md promises a refusal the server does not make

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped High.

Found by: playbook arm, [17.json](../../experiment/playbook-completion/findings/audit/17.json) (inspected `iris_vector_graph/cli.py:415-441`; inspected `iris_vector_graph/_api_key.py:15-30`; inspected `deploy/README.md:84-88`)

Reproduced by: none (confirmed-source)

- Expected: deploy/README.md:86: the server refuses auth: none with host 0.0.0.0 unless --force-no-auth.
- Observed at the pin: Confirmed in source: `ivg server start` defaults --host 0.0.0.0 and has no --force-no-auth (cli.py:419-426); auth is off when IVG_API_KEY is unset (iris_vector_graph/_api_key.py:21-23); no code reads IVG_AUTH_MODE (deploy/docker/compose.yml:34). HD-1705 working decision: local-only default or explicit opt-in.
- Source severity S1, confidence high; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): Per HD-1705: default to 127.0.0.1 or require an explicit opt-in for unauthenticated external binding; align the docs.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1712"></a>
### LazyKG.in_degree collapses parallel edges that degree() counts

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [17.json](../../experiment/playbook-completion/findings/audit/17.json) (live `c17-live-engine`; inspected `iris_vector_graph/stores/lazy_kg.py:215-269`; inspected `iris_src/src/Graph/KG/Adjacency.cls:197-209`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c17-live-engine`

- Expected: LazyKG docstring: degree counts parallel edges (stores/lazy_kg.py:215-235); in-direction should count the same edges.
- Observed at the pin: Live (c17-live-engine, multigraph c17mg): rows into c17:b = 3 (two parallel a-R->b and c-R->b); out_degree(a) = 2; in_degree(b) = 2; in_degree_for_predicate(b, R) = 2.
- Source severity S2, confidence high; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): Count the keyed children for a multigraph triple; a multigraph unit test.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1802"></a>
### A merge restore guards plain tables on their first column only, and counts skipped rows as restored

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [18.json](../../experiment/playbook-completion/findings/audit/18.json) (live `c18-live-merge-guard`; live `c18-live-save-footprint`; inspected `iris_vector_graph/_engine/snapshot.py:1287-1298`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c18-live-merge-guard`, `c18-live-save-footprint`

- Expected: SNP-B4.1 (a merge adds each missing row, judged by the row's own key); SNP-B4.2 (a row counts as restored only when added); USER_GUIDE.md:1151-1153 (merge=True adds to what is there).
- Observed at the pin: Live (c18-live-merge-guard): graph c18m with 3 nodes, 2 edges, labels and props archived ({'nodes': 3, 'rdf_edges': 2, 'rdf_labels': 3, 'rdf_props': 6}); after erase and re-creating one edge, one label, one property ({'nodes': 2, 'rdf_edges': 1, 'rdf_labels': 1, 'rdf_props': 3}), merge restore left {'nodes': 3, 'rdf_edges': 1, 'rdf_labels': 1, 'rdf_props': 3} - rows missing {'nodes': 0, 'rdf_edges': 1, 'rdf_labels': 2, 'rdf_props': 3}; the result reported restored_tables {'Graph_KG.code_crosswalk': 0, 'Graph_KG.docs': 0, 'Graph_KG.embedding_registry': 0, 'Graph_KG.fhir_bridges': 0, 'Graph_KG.…
- Source severity S2, confidence high; module 18; governing page here: `install.snapshot`.
- Remedy proposed by the playbook arm (not implemented): Guard each table on its primary or unique key (as CONFIGURATION_TABLES does) and count only inserted rows.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

Iteration 5 strengthening: the generic first-column merge guard is the same root as bug-plt-004; both IDs/history are retained, not counted as two new findings. Real IRIS merge with preexisting graph B's shared node skips graph A's parent and refuses A's routed vector by FK, while B's existing vector is counted restored but unchanged. snapshot_routes now derives restore_parent -> load -> read and distinguishes an existing incompatible row's successful skip from an empty incompatible table's refusal. Original complete-archive prediction/DISAGREES receipt retained; no repair implemented.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1803"></a>
### Edge vectors lose their graph and metadata in a snapshot

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [18.json](../../experiment/playbook-completion/findings/audit/18.json) (live `c18-live-edge-routes`; inspected `iris_vector_graph/_engine/snapshot.py:942-956, 1510-1552`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c18-live-edge-routes`

- Expected: SNP-B1.18 (edge vectors keep their graph and notes); Graph_KG.kg_EdgeEmbeddings is UNIQUE (graph_id, s, p, o_id) with metadata (iris_vector_graph/schema.py:455-464).
- Observed at the pin: Live (c18-live-edge-routes, part b): a kg_EdgeEmbeddings row of graph c18L with metadata, planted by SQL (the shape the table's key and metadata column exist for; the pin's own writer sends named-graph edge vectors to routes, part a), [['c18L', 'c18:l1', '{"m": 1}']]; archived as [{'emb': '1,2,3,4', 'o_id': 'c18:l2', 'p': 'R', 's': 'c18:l1'}] (no graph_id, no metadata); after deleting it and a merge restore: [['', 'c18:l1', 'None']].
- Source severity S2, confidence high; module 18; governing page here: `install.snapshot`.
- Remedy proposed by the playbook arm (not implemented): Export and restore graph_id and metadata; match on the full key.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1805"></a>
### A merge restore overwrites temporal aggregates instead of combining them

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [18.json](../../experiment/playbook-completion/findings/audit/18.json) (live `c18-live-aggregates`; inspected `iris_vector_graph/_engine/snapshot.py:1679`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c18-live-aggregates`

- Expected: SNP-B4.6 (after a merge restore the timed summaries still match the timed events); TemporalIndex.cls:96-125.
- Observed at the pin: Live (c18-live-aggregates): bucket 1700001000 with 2 archived events and a third live one; aggregate count before merge 3 / window 3; after merge restore aggregate 2 / window 3.
- Source severity S2, confidence high; module 18; governing page here: `install.snapshot`.
- Remedy proposed by the playbook arm (not implemented): Rebuild touched buckets and tlast after a merge (RebuildBucketAggregate, RebuildLatest) or refuse overlapping merges.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1806"></a>
### Graph.KG.Snapshot.ImportGlobals loads any global file without the allow-list

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [18.json](../../experiment/playbook-completion/findings/audit/18.json) (live `c18-live-file-helpers`; inspected `iris_src/src/Graph/KG/Snapshot.cls:4-73`; live `ws-live-snap-importglobals`; live `rx-live-18`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c18-live-file-helpers`, `ws-live-snap-importglobals`, `rx-live-18`

- Expected: SNP-X5.1 (every way to load globals keeps to the restore allow-list); snapshot.py:412-422 (an archive is a file anyone can write).
- Observed at the pin: Live (c18-live-file-helpers): Graph.KG.Snapshot is deployed in AUDITC with ['Decode', 'DeleteDir', 'Encode', 'ExportGlobals', 'FileExists', 'GetFileSize', 'ImportGlobals', 'IsVector', 'NodeRef', 'NodeValueJSON', 'ReadFileChunk', 'SetNodeJSON', 'WriteFileChunk']; ImportGlobals('/nonexistent-ivgaudit-c18/') answered {"imported":0} - callable over the Native API; its body runs $System.OBJ.Load on every *.gof (Snapshot.cls:24-35) with no list. No product code calls it.
- Source severity S2, confidence high; module 18; governing page here: `install.snapshot`.
- Remedy proposed by the playbook arm (not implemented): Delete the unused methods, or apply the restore allow-list.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0101"></a>
### An inline relationship property in a Cypher pattern fails on an edge with no properties

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [01.json](../../experiment/playbook-completion/findings/audit/01.json) (live `breadth-a-live-02-mode-off`; inspected `iris_vector_graph/schema.py:2185`; inspected `iris_vector_graph/cypher/translator.py:11197-11216`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-02-mode-off`

- Expected: openCypher: MATCH (x)-[r:R {k: 0}]->(y) and MATCH (x)-[r:R]->(y) WHERE r.k = 0 are equivalent; a missing property makes the filter false, not an error. create_edge's docstring: omitted properties leave the property null.
- Observed at the pin: inline form raises SQLCODE -149 on NULL qualifiers
- Source severity S2, confidence high; module 01; governing page here: `install.`.
- Remedy proposed by the playbook arm (not implemented): Guard Graph_KG.JSON_VALUE against an empty/NULL document (as CY_REL_PROP does), or emit the guarded function in _merge_prop_preds; a Cypher test over an edge written by create_edge without properties.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0150"></a>
### Every initialize_schema moves a node with a '__graph' property into that graph (add_graph_id_to_nodes), and the engine still writes such a property: an unrecorded cross-graph move, also into a graph…

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-writesets.json](../../experiment/playbook-completion/findings/audit/zz-writesets.json) (live `ws-live-migrations`; inspected `iris_vector_graph/schema.py:1514-1637`; inspected `iris_vector_graph/schema.py:704-722`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `ws-live-migrations`

- Expected: CHANGELOG.md:5229-5240 (spec 214: graph_id is a real column, the __graph pseudo-property is legacy) and iris_vector_graph/_engine/nodes_edges.py:1058 ('spec 214 FR-019: __graph pseudo-property no longer written'); iris_vector_graph/ledger/changeset.py:31 (the ledger reserves '__graph'); while a redaction runs the target stays not live (ADR-0013:17, RED-B5).
- Observed at the pin: Live in AUDITB (ws-live-migrations): graph wsagG (a ledger relationship, erased) with a bounded redaction's marker; engine.create_node('wsag|z', properties={'__graph': 'wsagG'}) stored a '__graph' property row in the default graph; GraphSchema.add_graph_id_to_nodes, which ensure_indexes runs on every initialize_schema (schema.py:719, _engine/schema.py:2514), answered rows_migrated 1: node wsag|z now has graph_id wsagG and the property is gone; wsagG has 1 live node row while its marker exists, and a re-run is refused target_live. The ledger recorded nothing (create_node is not a ledger write…
- Source severity S2, confidence high; module 01; governing page here: `install.`.
- Remedy proposed by the playbook arm (not implemented): Refuse '__graph' as a property key on every write path (as the ledger does), and run the __graph migration only once, when the graph_id column is added (not on every initialize_schema).
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0151"></a>
### retract_inference deletes any relationship whose qualifiers contain a key named 'inferred', a ledger relationship included, leaving its statement live

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-writesets.json](../../experiment/playbook-completion/findings/audit/zz-writesets.json) (live `ws-live-stmt-collision`; inspected `iris_vector_graph/_engine/schema.py:3186-3259`; inspected `iris_vector_graph/_engine/schema.py:61`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `ws-live-stmt-collision`

- Expected: iris_vector_graph/_engine/schema.py:3187 (retract_inference deletes 'the edges materialize_inference wrote'); INV-stmt / ERS-I2 (no live statement without its row).
- Observed at the pin: Live in AUDITB (ws-live-stmt-collision): a ledger relationship wsq|x -RI-> wsq|y created with qualifiers {'inferred': 'user'} (stored {"inferred":"user"}, statement 3 live); engine.retract_inference() returned 1 and deleted that row (DELETE ... WHERE qualifiers LIKE '%"inferred":%', schema.py:61, 3224); statement 3 stays live with no row; verify() = diverges (unrecorded_writes).
- Source severity S2, confidence high; module 01; governing page here: `install.`.
- Remedy proposed by the playbook arm (not implemented): Identify inferred rows by a marker no user qualifier can carry (reserve the key in the ledger and the writers), or skip rows that have a live statement.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0330"></a>
### A failed server-loader bulk_create_nodes answers 'nothing written' while its first 1,000 nodes stay committed

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-trace-replay.json](../../experiment/playbook-completion/findings/audit/zz-trace-replay.json) (trace `tr-replay-03`; source `iris_vector_graph/_engine/nodes_edges.py:1715-1757`; source `iris_vector_graph/_batch_check.py:68-80`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM)

- Expected: docs/USER_GUIDE.md:238-241: with no caller transaction 'each write (... the bulk loaders ...) is a transaction of its own'; iris_vector_graph/_batch_check.py:68-80 (raise_if_missing: 'a writer raises it before its rollback, so nothing of the batch is written'); a GraphWriteError's text says what stayed written (4.7.0 row 14; the same rule F-0806 applies to Cypher).
- Observed at the pin: Trace 03/bulk (tr-replay-03): bulk_create_nodes of 2,000 nodes on a from_connect engine (two 1,000-node chunks to Graph.KG.EdgeScan.BulkIngestNodesSQL on the engine's own Native API process, iris_vector_graph/_engine/nodes_edges.py:1715-1757), the last node carrying a 70,000-character property value (wider than rdf_props.val VARCHAR(64000), schema.py:415; _check_create_nodes checks id, label and key widths only, nodes_edges.py:243-262). The journal shows the loader process commit chunk 1 (1,000 node rows) in its own transaction, chunk 2 rolled back (TROLLBACK 1 after SQLCODE -104 'property bl…
- Source severity S2, confidence high; module 03; governing page here: `structure. / install.bulk_load`.
- Remedy proposed by the playbook arm (not implemented): Run the loader chunks on the caller's process inside the WriteTxn (txn.native() in every case, the F-0305 fix), so a failed batch leaves nothing; until then, a failure after a committed chunk must say how many nodes stayed committed instead of 'nothing written'.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0341"></a>
### get_json_field_values pastes the field name into its SQL text, so a field name can change the statement

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (live `st-live-susp-json-field`; inspected `iris_vector_graph/_engine/nodes_edges.py:916-930`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `st-live-susp-json-field`

- Expected: SQL text carries only constants and identifiers the code controls, values are bound (the product's own pattern elsewhere: _validate, sanitize_identifier; F-0815 for the same class of defect in Cypher); get_json_field_values(key, field) answers the field's values inside the key's blobs (iris_vector_graph/_engine/nodes_edges.py:916-930).
- Observed at the pin: Live AUDITD (st-live-susp-json-field), scratch rows jf:1 'meta' = {"color": "red"} and jf:2 'private' = {"color": "blue"}: get_json_field_values('meta', 'color') answers ['red']; a field containing one quote makes the statement fail ('Incorrect number of parameters'); a crafted field ending in ... WHERE "key" <> ? AND (1 = 1 OR val LIKE ?) -- turns the statement into a read of every other key and answers ['blue'] from the 'private' row. The field is formatted into a string literal of the select list (nodes_edges.py:921-922) and into the LIKE pattern (:926). The query also has no graph predica…
- Source severity S2, confidence high; module 03; governing page here: `structure. / install.bulk_load`.
- Remedy proposed by the playbook arm (not implemented): Bind the field: build the marker with a parameter (SELECT $PIECE($PIECE(val, ?, 2), '"', 1) ... with the bound text '"' + field + '": "'), escape % and _ in the LIKE pattern with an ESCAPE clause, or validate field against a strict identifier pattern; add a graph predicate.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0348"></a>
### Racing create_edge calls on a new edge whose endpoint is new can all lose: some answer False ('already exists') and no edge is written

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (live `st-live-keys-race-edge`; live `st-live-keys`; inspected `iris_vector_graph/_engine/nodes_edges.py:1205-1256`; inspected `iris_vector_graph/_engine/nodes_edges.py:1106-1150`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `st-live-keys-race-edge`, `st-live-keys`

- Expected: create_edge answers False only if the edge already existed, a duplicate is never an error (iris_vector_graph/_engine/nodes_edges.py:1176-1186 docstring); when two writers race to create one edge, one adds it and the other answers False (WRT-B4.9, 03-writes.md:118; nodes_edges.py:1243-1245 'a concurrent writer won the race'); endpoint rows a concurrent writer got to first are not an error (nodes_edges.py:1123-1124).
- Observed at the pin: Live AUDITD (st-live-keys-race-edge): four connections released together call create_edge('rx:1','R','rx:2') with rx:2 not yet a node. In 4 of 8 trials no call succeeds: two answer False and two raise GraphWriteError SQLCODE -121 (fk_edges_dest), and afterwards neither the edge nor rx:2 exists. With both endpoints present beforehand, 8 of 8 trials give one True, three False and one edge. Reading of the code: a racer that meets another racer's uncommitted endpoint row skips its own insert (nodes_edges.py:1123-1124), its edge insert then fails the FK or meets another racer's uncommitted edge ro…
- Source severity S2, confidence high; module 03; governing page here: `structure. / install.bulk_load`.
- Remedy proposed by the playbook arm (not implemented): Treat -119/-121 met against another writer's uncommitted row as 'retry' rather than 'duplicate': wait on the row (a SQL lock on the key, e.g. LOCK of the (graph, s, p, o) tuple before the probe) and re-probe after it commits or rolls back; answer False only when a committed edge is found.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0349"></a>
### The bulk loader writes duplicate node, label, property and edge keys: an id twice in one batch, a load with skip_existing=False, or two loaders at once

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (live `st-live-keys`; inspected `iris_vector_graph/bulk_loader.py:290-334`; inspected `iris_vector_graph/bulk_loader.py:420-440`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `st-live-keys`

- Expected: Graph_KG.nodes is keyed by (node_id, graph_id), rdf_labels by (graph_id, s, label), rdf_props by (graph_id, s, key) and rdf_edges by (s, p, o_id, graph_id, ekey) (iris_vector_graph/schema.py:35-44, 396-419). BulkLoader writes %NOINDEX %NOCHECK, which skips those checks (P-0304), and relies on its own scans to keep them: 'Without the hint every existence check here believes the previous bulk load never happened, and %NOCHECK means the second copy lands without complaint' (iris_vector_graph/bulk_loader.py:182-199); load_edges dedupes its input in memory (bulk_loader.py:420-427).
- Observed at the pin: Live AUDITD (st-live-keys): load_nodes([('kb:1', ...), ('kb:1', ...)]) answers nodes 2, labels 2, props 4 and leaves two node rows, two label rows and two rows per property key for (default graph, kb:1); get_node('kb:1') answers labels ['A', 'A']. load_nodes and load_edges run a second time with skip_existing=False duplicate the node, label, prop and edge keys. Two loaders of the same 50 ids started together each write all 50 nodes. In every case rebuild_all_indices answers True for all four classes and the duplicates stay; the load answers report no error.
- Source severity S2, confidence high; module 03; governing page here: `structure. / install.bulk_load`.
- Remedy proposed by the playbook arm (not implemented): Deduplicate node ids (and labels/properties per node) in the batch as load_edges does; refuse skip_existing=False under %NOCHECK or drop %NOCHECK for the key-carrying inserts; serialise loaders of one graph (a lock on the graph) and check the declared keys before %BuildIndices, failing the load on a duplicate.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0350"></a>
### BulkLoader.load_edges' INSERT %NOINDEX %NOCHECK lets a graph whose mode is off hold two rows of one triple at the same edge key, and the index rebuild accepts them

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-writesets.json](../../experiment/playbook-completion/findings/audit/zz-writesets.json) (live `ws-live-ba-noindex-parallel`; inspected `iris_vector_graph/bulk_loader.py:456-460`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `ws-live-ba-noindex-parallel`

- Expected: specs/234-multigraph-parallel-edges/spec.md:32-35, 225-226 and GID-I4.10 (experiment/playbook-uplift/ontology: a graph whose mode is off never holds parallel edges, whatever engine or path writes to it); iris_vector_graph/schema.py:34-44 (u_spo_graph_ekey UNIQUE (s, p, o_id, graph_id, ekey)); iris_vector_graph/bulk_loader.py:396 (skip_existing 'avoids UNIQUE violations').
- Observed at the pin: Live in AUDITB (ws-live-ba-noindex-parallel), default graph, mode off: BulkLoader.load_edges([('wsgp|a','R','wsgp|b',None)]) with its default use_noindex=True wrote one row at ekey 0 that the indexes do not hold; engine.create_edge of the same triple returned True and wrote a second row, also at ekey 0 (its guard and the unique key read the index); BulkLoader.rebuild_all_indices answered True for every index with both rows of key (wsgp|a, R, wsgp|b, '', 0) in place. Two load_edges calls with skip_existing=False wrote two rows of another triple, both ekey 0, and the rebuild again answered True.
- Source severity S2, confidence high; module 03; governing page here: `structure. / install.bulk_load`.
- Remedy proposed by the playbook arm (not implemented): Do not combine %NOCHECK with %NOINDEX for rdf_edges (or check the triple against every row with a %NOINDEX-aware read and within the batch whatever skip_existing says), and rebuild the indices before load_edges returns; validate the unique key when rebuilding it.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0450"></a>
### A ledger relationship whose qualifiers hold temporal=1 is deleted as a temporal edge's derived row, and its statement stays live

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-writesets.json](../../experiment/playbook-completion/findings/audit/zz-writesets.json) (live `ws-live-stmt-collision`; live `ws-live-stmt-purge`; inspected `iris_src/src/Graph/KG/Adjacency.cls:736-748`; inspected `iris_src/src/Graph/KG/LedgerApply.cls:420-434`; inspected `iris_src/src/Graph/KG/TemporalPolicy.cls:124-228`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `ws-live-stmt-collision`, `ws-live-stmt-purge`

- Expected: docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md:38-42 ('A row an explicit write asserted is unmarked and outlives the purge of its timestamps'); iris_src/src/Graph/KG/Adjacency.cls:619-621 (the row is deleted only while it carries the temporal marker, 'so an edge created explicitly outlives its temporal edges'); INV-stmt / ERS-I2 (no live statement without its row, experiment/playbook-uplift/ontology/12-erasure.md:42).
- Observed at the pin: Live in AUDITB (ws-live-stmt-collision, ws-live-stmt-purge). The ledger accepts any qualifier key but id and __graph (LedgerApply.cls:68-71) and stores values as strings (QualsJson, LedgerApply.cls:420-434), so create_relationship(..., qualifiers={'temporal': 1}) is stored {"temporal":"1"}; Adjacency.IsTemporalMarked (736-748) tests %Get("temporal") = 1, which "1" satisfies, while the ledger's own adoption test is = "true" (LedgerApply.cls:469). (a) A temporal edge on the same triple and engine.delete_edge_temporal: TemporalIndex.DeleteTemporalEdge -> RetractTemporalRow deleted the ledger's r…
- Source severity S2, confidence high; module 04; governing page here: `structure.`.
- Remedy proposed by the playbook arm (not implemented): Mark derived rows with something a governed relationship cannot carry (a reserved qualifier key the ledger and every writer refuse, or a separate column), and make every marker test use the same predicate; or have the temporal retraction refuse a row that has a live statement.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0501"></a>
### A refused temporal write raises but leaves the edge in the temporal index

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [05.json](../../experiment/playbook-completion/findings/audit/05.json) (live `breadth-a-live-05-partial`; inspected `iris_src/src/Graph/KG/TemporalIndex.cls:80-111`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-05-partial`

- Expected: create_edge_temporal docstring: 'A write IRIS refuses raises GraphWriteError and writes nothing'.
- Observed at the pin: raised, yet the temporal index holds the edge
- Source severity S2, confidence high; module 05; governing page here: `temporal.`.
- Remedy proposed by the playbook arm (not implemented): Open a transaction in InsertEdge/WriteStores (or assert the row first) so a refusal takes back tout/tin/bucket/tagg.
- Reviewed-design control: `playbook-proofs-d1c` `control_fc0501_refused_write_partial` fails where expected in this run ([receipt](results/playbook-proofs-d1c/20261115T035825Z-control_fc0501_refused_write_partial/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1c/20261115T035754Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0602"></a>
### SQL kg_KNN_VEC answers a node once per label, so a multi-label node takes several of the k places

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [06.json](../../experiment/playbook-completion/findings/audit/06.json) (live `breadth-a-live-06-embed`; inspected `iris_vector_graph/schema.py:2468-2479`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-06-embed`

- Expected: kg_KNN_VEC is a k-nearest-nodes search over the default route (schema.py:2437-2483); kg_RRF_FUSE's vector leg calls it with no label filter (schema.py:2558).
- Observed at the pin: answer ['bakn1233234', 'bakn1233234'] (a twice, b pushed out)
- Source severity S2, confidence high; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Use EXISTS for the label filter (no join when no filter is given), or SELECT DISTINCT node_id.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0701"></a>
### An index built under the stopword name makes index-structure words stopwords in every BM25 index

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [07.json](../../experiment/playbook-completion/findings/audit/07.json) (live `b-07-f0706`; inspected `iris_src/src/Graph/KG/BM25Index.cls:41-50`; inspected `iris_src/src/Graph/KG/BM25Index.cls:79-86`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-07-f0706`

- Expected: TXT-D1 (a stopword is one of 77 common English words); HD-0704 (reserve the stopword name).
- Observed at the pin: Live (b-07-f0706): after bm25_build('__stop__', ['name'], graph='b07g1') the words 'doc', 'tf', 'len' (and 'cfg', 'df') are stopwords for every index in the namespace: a rebuild of index b07w drops them (searches for each answer [] where they answered b07_w1 before) because Tokenize's stopword test $Data(^BM25Idx("__stop__", tok)) (BM25Index.cls:83) is true for the index's own subscripts. The effect lasts until the __stop__ index is dropped (which also deletes the stopword list until the next tokenize).
- Source severity S2, confidence high; module 07; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Refuse the name (HD-0704) or move the stopword list to its own global.
- Reviewed-design control: `playbook-proofs-d1d` `control_fc0701_stop_name_accepted` fails where expected in this run ([receipt](results/playbook-proofs-d1d/20261115T035642Z-control_fc0701_stop_name_accepted/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0715"></a>
### bm25_search rewrites document ids: its leading-dot patch runs over the whole answer, so an id holding ':.5', ',.7' or '[.9' comes back as ':0.5', ',0.7', '[0.9'

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-refusals.json](../../experiment/playbook-completion/findings/audit/zz-refusals.json) (live `rx-dec-live-07`; check `rx-dec-map`; inspected `iris_vector_graph/_engine/vector.py:1817-1819`; inspected `iris_src/src/Graph/KG/BM25Index.cls:361-365`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `rx-dec-live-07`

- Expected: TXT-B2 (search returns each best document with its node id and score); TXT-B2.13 (each id and score in the answer is valid JSON, ids included); CHANGELOG.md:463-467 (4.6.3: 'Search answers keep a node id with a quote or a backslash', each answer escaped as RFC 8259 asks); docs/USER_GUIDE.md:859-866 (bm25_search and CALL ivg.bm25.search answer the same nodes); tests/e2e/test_463_search_id_escaping_e2e.py:57-71 asserts the Python and Cypher answers agree id for id.
- Observed at the pin: Live (rx-dec-live-07, case 'ids containing ...'): graph rxdg, nodes rxd:a, rxd:.5x, rxd,.7y, rxd[.9z, rxd:b with the word zebra, index rxdidx. Graph.KG.BM25Index.Search's raw answer is valid JSON with the ids exactly as stored and every score already written with a leading 0 (no '"score":.' in the wire); bm25_search answered ('rxd:0.5x', ...), ('rxd,0.7y', ...), ('rxd[0.9z', ...) for 3 of the 5 rows, and bm25_search(report=True) the same; CALL ivg.bm25.search (JSON_TABLE over the same wire) answered the ids unchanged. Cause: _parse applies re.sub(r'(?<=[:\[,])(\.\d)', r'0\1', raw) to the whol…
- Source severity S2, confidence high; module 07; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Drop the text patch (the server already writes a leading 0), or apply it to number tokens only by parsing with json.loads(parse_float=...) after a token-aware scan; add an id with ':.5' to the 4.6.3 id-escaping test.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0748"></a>
### One token longer than the subscript limit in any document makes bm25_build fail after it has emptied the index, and searches then answer nothing

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (live `st-live-cap-bm25`; inspected `iris_src/src/Graph/KG/BM25Index.cls:56-87`; inspected `iris_src/src/Graph/KG/BM25Index.cls:97-110`; inspected `iris_src/src/Graph/KG/BM25Index.cls:176-204`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `st-live-cap-bm25`

- Expected: A refused command leaves every store as it was (SYS-I3, TXT-X2 in experiment/playbook-uplift/ontology/07-text-search.md; cited by F-0704); Build indexes every node of the graph over the named properties (iris_src/src/Graph/KG/BM25Index.cls:97-175).
- Observed at the pin: Live AUDITD (st-live-cap-bm25): with one document holding a 600- or 2,000-character token (or a 300-character token in a document whose id has 256 characters), bm25_build raises 'RuntimeError: <THROW>' and leaves the index without documents; rebuilding a good 5-document index after one such node is added destroys it the same way, and bm25_search for any ordinary term then answers [] without error. Build kills ^BM25Idx(name) first (BM25Index.cls:99) and Tokenize tests each token with $Data(^BM25Idx("__stop__", tok)) (:83), which raises <SUBSCRIPT> for a long token; bm25_insert and bm25_search…
- Source severity S2, confidence high; module 07; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Skip or truncate tokens longer than a fixed length in Tokenize (before any subscript use), and build into a temporary name that replaces the old index only on success (as F-0704's remedy); report the document that failed.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0803"></a>
### MERGE ... ON CREATE SET r = a gives every merged relationship the first row's properties

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-storage-order`; inspected `iris_vector_graph/cypher/translator.py:12362-12395`; inspected `$RUN_DIR/checks/storage-order.json`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-storage-order`

- Expected: openCypher: MERGE runs once per incoming row; `SET r = a` copies that row's node a onto that row's relationship (CYP-B6.8 per-row MERGE semantics); gate §3.4 storage-order.
- Observed at the pin: Live (b-08-live-storage-order): `MATCH (a:B08PP), (t:B08TT {id:'b08_tt'}) MERGE (a)-[r:B08MR3]->(t) ON CREATE SET r = a` with a = b08_p1 {city:'ca', pop:1} and b08_p2 {city:'cb', pop:2} created two relationships whose qualifiers were both {id:'b08_p1', city:'ca', pop:'1'}. The translator copies `(SELECT TOP 1 a.node_id FROM <preceding rows>)` (translator.py:12362-12395) with no ORDER BY and applies one UPDATE to every merged relationship, so the stored values come from whichever row storage order puts first.
- Source severity S2, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Correlate the copied node with each relationship's own row (per-row UPDATE through the row-bound MERGE plan, or a correlated subquery on the relationship's source/target), or refuse `SET r = a` when the preceding clauses bind more than one row; live test with two rows.
- Reviewed-design control: `playbook-proofs-d1d` `control_fc0803_top1_copy` fails where expected in this run ([receipt](results/playbook-proofs-d1d/20261115T035653Z-control_fc0803_top1_copy/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0848"></a>
### A Cypher CREATE or MERGE with literal or parameter endpoint ids drops a parameter-bound relationship property without an error

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (live `st-live-cypher-relprop`; live `st-live-cap-values`; inspected `iris_vector_graph/cypher/translator.py:10213-10246`; inspected `iris_vector_graph/cypher/translator.py:473-504`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `st-live-cypher-relprop`, `st-live-cap-values`

- Expected: docs/KNOWN_ISSUES.md:89-95: 'A literal (a list or a map too), a parameter and a WITH's column are stored'; iris_vector_graph/cypher/translator.py:507-512 (_refuse_unstorable_rel_props: a parameter is stored, anything it cannot store is refused before writing).
- Observed at the pin: Live AUDITD (st-live-cypher-relprop, found by st-live-cap-values): CREATE (a:L {id: 'a2'})-[:R {q: $v}]->(b:L {id: 'b2'}), the same with $s/$o endpoint ids, with a number parameter, and MERGE (a:L {id: 'a4'})-[:R {q: $v}]->(b:L {id: 'b4'}) each answer no error and create the edge with no q (rdf_edges.qualifiers empty; r.q null). The same parameter between MATCHed endpoints and a literal q are stored. The literal-endpoint path (translator.py:10213-10222) resolves an ast.Literal or a FOREACH binding only, so a parameter resolves to None and is dropped as a null property (:10228).
- Source severity S2, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Resolve parameters (context.input_params) in the literal-endpoint path as _rel_literal_props does, or route such patterns through _rel_literal_props; refuse any property the writer cannot store instead of dropping it.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0901"></a>
### A build marks whatever entry its hash holds as ok, so one shape's entry can run another shape's class for good

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [09.json](../../experiment/playbook-completion/findings/audit/09.json) (live `b-09-f0901-collision`; mc `m09-planc-as-built-collide-binding`; mc `m09-planc-reviewed`; inspected `iris_src/src/Graph/KG/Cypher/Gen.cls:175-182`; inspected `iris_src/src/Graph/KG/Cypher/Gen.cls:207`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-09-f0901-collision`

- Expected: NAT-T5.16 (a ready entry runs only the class written for its own shape) and NAT-I3; ADR-0014:19.
- Observed at the pin: Live (b-09-f0901-collision): a birthday search in IRIS over label names of one length found two labels B09QXAYMSHXLZD / B09QWCSOJEBLDF whose plan shapes share $ZCRC(shape,7) = 1912394325 after 90195 candidates (0.23 s); hashes of the separately compiled shapes: {'B09QXAYMSHXLZD': ['1912394325'], 'B09QWCSOJEBLDF': ['1912394325']}. In job mode (one process) a read of the B09QWCSOJEBLDF shape (its build job compiling) then a read of the B09QXAYMSHXLZD shape left one entry, status ['ok']; the next B09QXAYMSHXLZD read answered [[2]] where the SQL path answers [[1]]; a shadow-mode engine raised Nat…
- Source severity S2, confidence high; module 09; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Under its lock, Build writes the entry only if it still holds the shape (or digest) it compiled; otherwise it deletes the class and leaves the entry.
- Reviewed-design control: `playbook-proofs-d1d` `control_fc0901_mark_any_entry` fails where expected in this run ([receipt](results/playbook-proofs-d1d/20261115T035703Z-control_fc0901_mark_any_entry/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1150"></a>
### A plain SQL INSERT into Graph_KG.ledger_revisions is accepted, and a row planted at head+1 made the next ledger commit fail

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-writesets.json](../../experiment/playbook-completion/findings/audit/zz-writesets.json) (live `ws-live-sql-insert-wedge`; live `ws-live-sql-guard`; inspected `iris_src/src/Graph/KG/LedgerRevision.cls:44`; inspected `iris_src/src/Graph/KG/LedgerRevision.cls:87-108`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `ws-live-sql-insert-wedge`, `ws-live-sql-guard`

- Expected: iris_src/src/Graph/KG/LedgerRevision.cls:1-5 ('one immutable row per committed revision ... Written only by Graph.KG.Ledger.Commit inside the commit transaction'; UPDATE and DELETE are rejected, FR-023).
- Observed at the pin: Live in AUDITB (ws-live-sql-insert-wedge): with head seq 3, an SQL INSERT of a row with seq 4 and every required column was accepted (the table has UPDATE and DELETE triggers, no INSERT trigger); the next engine.ledger.commit (the only one attempted after the INSERT) failed LedgerInconsistencyError 'revision row save failed: ERROR #5805: ID key not unique ... ^Graph.KG.LedgerRevisionD(4) exists'; verify() still answered equal. An INSERT of an existing seq is refused (SeqIdx) and UPDATE is refused (trigger) (ws-live-sql-guard), so the INSERT cannot rewrite history; it blocks the ledger.
- Source severity S2, confidence high; module 11; governing page here: `ledger.`.
- Remedy proposed by the playbook arm (not implemented): Add an INSERT trigger (or %OnBeforeSave check) that refuses a row outside Ledger.Commit's transaction, as for UPDATE and DELETE; and have verify() report a revision row with no records.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1303"></a>
### A bounded redaction (max_batches) restarts its scan at the first record and may never finish

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [13.json](../../experiment/playbook-completion/findings/audit/13.json) (run `live-fc1303-bounded-resume`; run `core-m2-as-built-paced-resume`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM)

- Expected: LedgerRedact.cls:178-180: 'pMaxBatches > 0 stops after that many batches and leaves the run in progress; running the same target again resumes it.' RED-B8 (a stopped run resumes); spec 256 SC-003 (batching).
- Observed at the pin: Live on the pin: 60 calls with batch 1 and max_batches 1 each re-scanned the first 20 records (batch x SCANFACTOR cap, :306-310) from the start (:213), tombstoned nothing and returned complete=false; 9 target records remained. The same world completes with max_batches 0. Model: core M2 paced-resume progress mutant and AG EF failure.
- Source severity S2, confidence high; module 13; governing page here: `redaction.`.
- Remedy proposed by the playbook arm (not implemented): Persist the scan cursor with the marker (or start each call after the last tombstoned position) so a resumed call continues where the previous one stopped.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1304"></a>
### IVG's own snapshot archives keep an erased and redacted tenant, the receipt does not name them, and a restore brings the tenant back

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [followup.json](../../experiment/playbook-completion/findings/audit/followup.json) (live `fu-r01a-snapshot-copies`; inspected `iris_vector_graph/cypher_api.py:668-678`; inspected `iris_vector_graph/_engine/snapshot.py:387-422`; inspected `iris_vector_graph/_engine/snapshot.py:1035`; inspected `iris_src/src/Graph/KG/LedgerRedact.cls:504-508`; live `c18-live-ledger-overlay`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `fu-r01a-snapshot-copies`, `c18-live-ledger-overlay`

- Expected: specs/256-ledger-tenant-redaction/spec.md:42-44 (US1: afterwards 'no record, revision field or index reachable through IVG holds the tenant's entity ids, attribute values or messages'; the receipt says 'what stayed out of reach'); spec.md:127-128 (FR-008: the receipt states what stays out of reach); docs/adr/0013-redaction-removes-content-from-history.md:47-48 ('Together they cover everything IVG can reach'; out of reach: export_reconstruction files, journals, backups); iris_src/src/Graph/KG/LedgerRedact.cls:504-508 (the receipt's out_of_reach: exactly those three).
- Observed at the pin: Live in AUDITA (fu-r01a-snapshot-copies): tenant fu1|x committed through the ledger with a secret property, message, source, correlation id and idempotency key; engine.save_snapshot (the call POST /admin/snapshot makes with $IVG_SNAPSHOT_DIR or the temp folder, iris_vector_graph/cypher_api.py:668-678) taken before the erase, after the erase and after the redaction; delete_nodes_by_prefix + ledger.redact(None, prefix='fu1') complete, verify() equal, and the SC-001 scan of ^IVG.Ledger and Graph_KG.ledger_* finds none of the six tenant tokens. The pre-erase archive holds the tenant in sql/Graph_…
- Source severity S2, confidence high; module 13; governing page here: `redaction.`.
- Remedy proposed by the playbook arm (not implemented): Name IVG's own archives (save_snapshot files, including those POST /admin/snapshot writes to $IVG_SNAPSHOT_DIR or the temp folder) in the receipt's out_of_reach and in ADR-0013's reach statement; optionally refuse or warn on restoring an archive older than a completed redaction (HD-1801's re-apply of live redactions) and give the HTTP snapshot a retention rule.
- Reviewed-design control: `playbook-proofs-d1b` `control_fc1304_receipt_omits_archives` fails where expected in this run ([receipt](results/playbook-proofs-d1b/20261115T035739Z-control_fc1304_receipt_omits_archives/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1b/20261115T035711Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1307"></a>
### A writer that keeps the target live holds a redaction open indefinitely, and while it is open every tenant's record readers, verify() and other redactions are refused

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [followup.json](../../experiment/playbook-completion/findings/audit/followup.json) (live `fu-r03-marker-held-open`; inspected `iris_src/src/Graph/KG/LedgerRedact.cls:202-211`; inspected `iris_src/src/Graph/KG/LedgerRedact.cls:393-441`; inspected `iris_vector_graph/ledger/client.py:682-693`; inspected `iris_vector_graph/cypher_api.py:628-643`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `fu-r03-marker-held-open`

- Expected: docs/adr/0013-redaction-removes-content-from-history.md:18 (Batches: while the marker exists 'a commit with a record in the target is refused'; 'Re-running the same redaction resumes it'); specs/256-ledger-tenant-redaction/spec.md:156 (Decision 3), :125 (FR-006), :148 (SC-004: other tenants' verify() result unchanged); iris_vector_graph/ledger/client.py:633-660 (redact docstring: calling again resumes the run).
- Observed at the pin: Live in AUDITA (fu-r03-marker-held-open, two connections): tenant fa3 erased, a bounded run (batch 1, max_batches 1) left the marker. engine.create_node('fa3|zombie') on a non-strict ledger was accepted (no non-ledger writer reads the marker), while a ledger commit into fa3 was refused. Running the redaction again was refused at the entry liveness check ('still holds 4 live row(s)', LedgerRedact.cls:207-211). A run that passed the entry check while a second connection held the head lock tombstoned every remaining fa3 record, and after a bypass write during the wait Final refused ('became live…
- Source severity S2, confidence high; module 13; governing page here: `redaction.`.
- Remedy proposed by the playbook arm (not implemented): Either make the marker binding on every writer of the content tables (the non-ledger write paths, Cypher updating clauses, POST /admin/load and the temporal mirror refuse a write into the marked target), or scope the readers' refusal to the marked target and add an operator abandon/rollback for a run that cannot finish; state 'no writer makes a marked target live' as a progress premise (P-C02).
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1547"></a>
### get_reifications reads the reifier's properties from every graph

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (live `st-live-reads-b`; control `st-control-reads-selftest`; inspected `iris_vector_graph/_engine/schema.py:3335-3360`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `st-live-reads-b`

- Expected: get_reifications returns the reifiers of rdf_edges row edge_id with their properties (iris_vector_graph/_engine/schema.py:3335-3339); a reifier node is an ordinary node of one graph (15-integrations.md INT-D19, INT-E1; reify_edge writes it in the default graph, INT-E1.6 / F-1502), and since spec 227 a node id is unique per graph, not per namespace (iris_vector_graph/schema.py:383-391); content of one graph never shows up in an answer about another graph (00-system.md SYS-I2).
- Observed at the pin: Live AUDITD (st-live-reads-b, non-interference oracle with self-test st-control-reads-selftest): default-graph edge a-R-b reified as rf1 with props {p: '1'}; adding a node rf1 in named graph stg2 with props {p: '2', q: 'x'} (and a reification of another edge) changed get_reifications(edge a-R-b) from [{reifier_id: rf1, properties: {id: rf1, p: '1'}}] to [{reifier_id: rf1, properties: {id: rf1, p: '2', q: 'x'}}]: another graph's property rows of the same id are joined in and overwrite the reifier's own. The query joins rdf_props on the id alone: LEFT JOIN rdf_props p ON p.s = r.reifier_id (sch…
- Source severity S2, confidence high; module 15; governing page here: `fhir.`.
- Remedy proposed by the playbook arm (not implemented): Join the reifier's properties in the reifier node's graph (the graph reify_edge wrote it in, or the edge's graph once F-1502 is fixed): add the graph_id condition to the rdf_props join, e.g. through the nodes row of the reifier.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1601"></a>
### A finished Bolt session never gives back its IRIS connection

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [16.json](../../experiment/playbook-completion/findings/audit/16.json) (live `c16-s2-bolt-sessions`; inspected `iris_vector_graph/bolt_server.py:391-423`; inspected `iris_vector_graph/bolt_server.py:922-960`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c16-s2-bolt-sessions`

- Expected: API-T8.3 says each Bolt session opens its own IRIS connection; P-1609: each connection counts against the instance's connection/licence limit (8 on this Community container), so a session must release it.
- Observed at the pin: Live (c16-s2-bolt-sessions): three sequential Bolt sessions (driver closed each, GOODBYE sent) left three new AUDITC IRIS processes alive 20 s later; they disappeared only when the server process stopped. Source: the session builds its engine lazily (iris_vector_graph/bolt_server.py:391-394) and its run() finally-blocks close only the socket (bolt_server.py:404, :423 WebSocket; :940, :957 TCP), never self._engine.conn.
- Source severity S2, confidence high; module 16; governing page here: `access.`.
- Remedy proposed by the playbook arm (not implemented): Close the session's engine connection when the session ends (finally block), or share a bounded pool.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1603"></a>
### Bolt listens on every interface unless the server is started by `ivg server start`

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [16.json](../../experiment/playbook-completion/findings/audit/16.json) (probe `c16-s6-status-maps`; inspected `iris_vector_graph/cypher_api.py:47-63`; inspected `iris_vector_graph/cli.py:419-441`; inspected `docs/ADMIN_API.md:13-28`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c16-s6-status-maps`

- Expected: docs/ADMIN_API.md:26-28: the Bolt listener 'listens on the address --host names, or on BOLT_TCP_HOST'; API-T9.1; HD-1705 working answer: local-only or explicit opt-in for unauthenticated external binding.
- Observed at the pin: Live (c16-s6-status-maps): `uvicorn iris_vector_graph.cypher_api:app --host 127.0.0.1` served HTTP on 127.0.0.1:18617 and the Bolt listener on 0.0.0.0:18618. Source: cypher_api.py:51 defaults BOLT_TCP_HOST to 0.0.0.0; only the CLI sets it from --host (cli.py:429); the documented `python -m iris_vector_graph.cypher_api` binds HTTP 0.0.0.0:8000 and Bolt 0.0.0.0:7687 (cypher_api.py:779; ADMIN_API.md:22). With IVG_API_KEY unset the listener needs no credentials.
- Source severity S2, confidence high; module 16; governing page here: `access.`.
- Remedy proposed by the playbook arm (not implemented): Default BOLT_TCP_HOST to the HTTP host (or 127.0.0.1) in the app itself, not only in the CLI; refuse an unauthenticated non-loopback bind unless explicitly forced.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1604"></a>
### The Cypher HTTP server runs a query again after any failure, writes included

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [16.json](../../experiment/playbook-completion/findings/audit/16.json) (live `c16-s4-server-retry`; live `c16-s1-cypher-http`; inspected `iris_vector_graph/cypher_api.py:239-260`; mc `cmc-retry-as-built-once`; mc `cmc-retry-as-built-honest`; mc `cmc-retry-reviewed`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c16-s4-server-retry`, `c16-s1-cypher-http`

- Expected: decisions.md HD-1603 (working answer): retry only a read, a write known not to have run, or a write with a verified idempotency key; an ambiguous commit outcome stays unknown.
- Observed at the pin: Live (c16-s4-server-retry, fault injection of a lost acknowledgement after the engine's commit, through the real FastAPI app on AUDITC): SET n.counter = n.counter + 1 — one request moved the counter from 1 to 3 and answered 200; CREATE without a key — after the control run made 1 C16R2 node, ONE faulted request brought the total to 3 (control total 1); CREATE with an id answered 200 {'columns': ['id'], 'rowCount': 1, 'rows': [['c16:r3']], 'status': 'OK'}. c16-s1 also shows a plain parse error triggering the reset-and-retry (two IRIS processes for one /db/neo4j/tx/commit). Source: _run_cypher…
- Source severity S2, confidence high; module 16; governing page here: `access.`.
- Remedy proposed by the playbook arm (not implemented): Retry only reads or errors raised before the statement ran (connection refused at connect); otherwise return an unknown-outcome error; or carry an idempotency key end to end. Combine with the SDK retry (HD-1702, module 17) as one protocol.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1703"></a>
### One HTTP client call can create a write twice (client resend after a late reply; server re-run after an exception)

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [17.json](../../experiment/playbook-completion/findings/audit/17.json) (live `c17-live-server`; mc `cmc-retry-as-built-once`; mc `cmc-retry-as-built-honest`; mc `cmc-retry-reviewed`; control `cmc-retry-ctl-client`; control `cmc-retry-ctl-server`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c17-live-server`

- Expected: decisions.md HD-1702 / HD-1603 (working): after an ambiguous outcome retry only a read, a write known not to have run, or one with a verified idempotency key; treat client and server retries as one protocol.
- Observed at the pin: Live (c17-live-server): IVGClient(timeout=2 s, max_retries=3) through a proxy that held the first reply 4 s sent one CREATE (n:C17Dup {marker}); the proxy saw 2 requests, the client answered {'rows': [['c17dup-1794613789']]}, and AUDITC holds 2 nodes with that marker. Source: sdk.py:209-228 resends a POST after TimeoutException/ConnectError/5xx whatever the query; IVGServerError.is_retryable is any 5xx (sdk.py:41-42); cypher_api.py:250-268 re-runs execute_cypher on a fresh connection after any exception. Model: cmc-retry-as-built-once (expected-violation), cmc-retry-as-built-honest (expected-…
- Source severity S2, confidence high; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): Retry only reads or writes known not to have run (connect error before send); report an unknown outcome for an ambiguous write; or carry an end-to-end idempotency key (the ledger's retry key) through /api/cypher.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1743"></a>
### IRISGraphStore.query_nodes(limit=n) kills the calling Python process (SIGSEGV) on IRIS Community 2026.1 with the locked driver

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (live `st-live-so-confirm`; live `st-live-so-17b`; inspected `iris_vector_graph/stores/iris_sql_store.py:1176-1181`; run `env2-fc1720-query-nodes`; run `env2-fc1720-query-nodes-d540`; run `env2-fetchfirst-probe`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `st-live-so-confirm`, `st-live-so-17b`

- Expected: A public store method either answers or raises (store_protocol.py:10-11); the product knows FETCH FIRST is hazardous for this driver/engine family and avoids it elsewhere (iris_vector_graph/engine.py:725-739 _fetch_first_unsafe and its subprocess probe :772-830; docs/iris-sql-quirks.md:47-62; the in-line comment iris_sql_store.py:1177-1178 records a segfault on FETCH FIRST ? ROWS ONLY on ARM64).
- Observed at the pin: Live (st-live-so-confirm P17, AUDITD, IRIS 2026.1 Community build 234U, intersystems_irispython 5.3.2, x86_64): a child process that calls engine._store.query_nodes(limit=2) prints its start mark and exits with return code -11 (SIGSEGV) before any answer, in both insertion orders; the first attempt inside the permutation harness ended the harness with 'dumped core'. The statement is SELECT node_id FROM Graph_KG.nodes FETCH FIRST 2 ROWS ONLY (iris_vector_graph/stores/iris_sql_store.py:1179-1180), sent without consulting _fetch_first_unsafe. Attribution control (st-live-so-17b): the same statem…
- Source severity S2, confidence high; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): Use TOP n (as the translator does for joins and the engine does when _fetch_first_unsafe is set) or consult _fetch_first_unsafe in the adapter; a test that runs query_nodes(limit=n) on the supported driver.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1750"></a>
### A refused Eraser probe is cached as 'absent': the store's deletes then run as plain SQL and leave the ledger statements of the deleted edges live

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-orchestrator-steer7.json](../../experiment/playbook-completion/findings/audit/zz-orchestrator-steer7.json) (live `ws-live-sql-fallback-priv`; inspected `iris_vector_graph/stores/iris_sql_store.py:1307-1318`; inspected `iris_vector_graph/stores/iris_sql_store.py:1363-1418`; inspected `iris_vector_graph/stores/iris_sql_store.py:1474-1518`; inspected `iris_vector_graph/_dictionary.py:1-64`; inspected `iris_vector_graph/schema.py:119-143`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `ws-live-sql-fallback-priv`

- Expected: iris_vector_graph/stores/iris_sql_store.py:1333-1338 (delete_nodes' docstring reserves the SQL path for 'an install with no ObjectScript classes, hence no ^KG to maintain'; here the classes, the ledger and ^KG all exist); INV-stmt / ERS-I2 (no live statement without its row, experiment/playbook-uplift/ontology/12-erasure.md:42). Context, not the anchor: docs/ADMIN_GUIDE.md:511-514's ClassesUnreadable rule covers only a routines database the role cannot read (raised when the <PROTECT> names that database, iris_vector_graph/schema.py:119-143); for a refusal that names no database, a missing %Na…
- Observed at the pin: Live in AUDITB (ws-live-sql-fallback-priv), as the operator-authorised disposable principal, ledger enabled (not strict), 4 nodes and 2 recorded edges, verify() equal. With ADMIN_GUIDE's writing row (%DB_%DEFAULT:RW, %Native_ClassExecution:U, %Native_GlobalAccess:U, INSERT/UPDATE/DELETE ON SCHEMA Graph_KG) engine.delete_node('sfp|a') and IRISGraphStore.delete_edges([('sfp|c','R','sfp|d')]) went through Graph.KG.Eraser (probe cache True) and the rows, the ^KG out entries and both ledger statements went. With the same role without %Native_ClassExecution the probe's native IDKEYExists raised '<P…
- Source severity S2, confidence high; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): Treat only a definite 'not compiled' answer as absent: re-raise (or raise ClassesUnreadable) on a refusal or any other probe error, do not cache a failed probe, and log the fallback at WARNING; or remove the SQL fallback for namespaces where the ledger or ^KG exists.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1801"></a>
### save_snapshot archives writes that never commit

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [18.json](../../experiment/playbook-completion/findings/audit/18.json) (live `c18-live-dirty-export`; mc `cmc-snap-as-built-committed`; mc `cmc-snap-as-built-dangling`; mc `cmc-snap-reviewed`; control `cmc-snap-ctl-gate`; inspected `iris_vector_graph/_engine/snapshot.py:864-1034`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c18-live-dirty-export`

- Expected: decisions.md HD-1802 (working): claim a consistent snapshot only with quiescent writers or a verified snapshot/epoch protocol, and declare the quiet-writer premise for the current exporter; SNP-Q1.17.
- Observed at the pin: Live (c18-live-dirty-export): another connection opened a transaction (TLEVEL 1) and created c18:ghost; save_snapshot ran; the writer rolled back; the DB holds 0 ghost rows, the archive holds {'kg_lines': [{'k': ['label', '0', 'C18Ghost', 'c18:ghost'], 'v': ''}], 'nodes': [{'created_at': '2026-11-13T23:05:06', 'graph_id': '', 'node_id': 'c18:ghost'}], 'rdf_props': [{'graph_id': '', 'key': 'p', 's': 'c18:ghost', 'val': 'uncommitted'}, {'graph_id': '', 'key': 'id', 's': 'c18:ghost', 'val': 'c18:ghost'}]}. Model: cmc-snap-as-built-committed (expected-violation, 36 states, exhaustive within bound…
- Source severity S2, confidence high; module 18; governing page here: `install.snapshot`.
- Remedy proposed by the playbook arm (not implemented): Document the quiet-writer premise (HD-1802) and refuse or warn when transactions are open; or export under a namespace-wide export gate that writers respect.
- Reviewed-design control: `playbook-proofs-d1b` `control_fc1801_dirty_export` fails where expected in this run ([receipt](results/playbook-proofs-d1b/20261115T035741Z-control_fc1801_dirty_export/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1b/20261115T035711Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1802"></a>
### restore_snapshot drops a global line it cannot write without raising or counting it

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [18.json](../../experiment/playbook-completion/findings/audit/18.json) (live `c18-live-swallowed-lines`; inspected `iris_vector_graph/_engine/snapshot.py:1654-1692`; inspected `tests/unit/test_460_r271_snapshot_raises.py:156-163`; live `rx-live-18`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c18-live-swallowed-lines`, `rx-live-18`

- Expected: SNP-X2.14 (a native index that cannot be written stops the restore; the error says what is done); restore docstring snapshot.py:1088-1094 ('A global it cannot write ... raises RuntimeError').
- Observed at the pin: Live (c18-live-swallowed-lines): an archive with ^IVG.GraphMode lines ['{"k": ["c18x"], "v": "1"}', '{"k": [""], "v": "1"}', '{"k": ["c18y", ""], "v": "1"}']; the bad subscripts set directly over the Native API -> {'[""]': 'RuntimeError: <SUBSCRIPT>', '["c18y", ""]': 'RuntimeError: <SUBSCRIPT>'}; merge restore answered {'failed_rows': {}, 'restored_globals': ['IVG.GraphMode'], 'restored_layers': ['globals'], 'restored_tables': {}, 'snapshot_ts': 1794612073559} (error None); the good line was written: {'c18x': 1}. Source: _import_global_from_ndjson catches every per-line exception with logger.…
- Source severity S2, confidence high; module 18; governing page here: `install.snapshot`.
- Remedy proposed by the playbook arm (not implemented): Count failed lines in failed_rows (per global) or raise as documented; a test with a line IRIS refuses.
- Reviewed-design control: `playbook-proofs-d1b` `control_fc1802_swallowed_line` fails where expected in this run ([receipt](results/playbook-proofs-d1b/20261115T035742Z-control_fc1802_swallowed_line/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1b/20261115T035711Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-CS01"></a>
### A revision whose changeset recorded nothing keeps the tenant's message, source, correlation id and idempotency key (and the key's binding) through a complete redaction

Severity: Medium · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-simulator.json](../../experiment/playbook-completion/findings/audit/zz-simulator.json) (live `sim-fcs01-minimal`; live `sim-fcs01-ddmin-s1033`; trace `sim-main-20261114`; trace `sim-race-20261114`; control `sim-oracle-selftest`; inspected `iris_src/src/Graph/KG/LedgerApply.cls:229-233`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `sim-fcs01-minimal`, `sim-fcs01-ddmin-s1033`

- Expected: specs/256-ledger-tenant-redaction/spec.md:42-44 (US1: after erase and redaction 'no record, revision field or index reachable through IVG holds the tenant's entity ids, attribute values or messages'); spec.md:121-123 (FR-004: 'For a revision whose every record is redacted, message, source, correlation_id and idempotency_key MUST be cleared'; a revision with no records has every record redacted); spec.md:142-143 (SC-001: a scan of every ^IVG.Ledger subscript and value and every Graph_KG.ledger_* row finds none of the tenant's ids or values, 'Zero matches is the bar'); specs/256-ledger-tenant-r…
- Observed at the pin: Found by the randomized simulator (I6 SC-001 scan at each completed redaction) in 9 of 304 schedules, first seed 1033 (graph-per-tenant gamma) and in the prefix shape (seed 1087); shrunk through the product to 7 operations (sim-fcs01-ddmin-s1033) and hand-reduced to 6, reproduced 3/3 on AUDITA (sim-fcs01-minimal): commit(create_node acme|n1 with label Person, key acme-k-min-1) -> seq 2; commit(upsert_node acme|n1 + add_label acme|n1 Person, key acme-k-min-2, message 'acme commit min-2', source {tenant: acme}, correlation id acme-corr-0) -> seq 3 with op_count 0 (an existing node and an existi…
- Source severity S2, confidence high; module 13; governing page here: `redaction.`.
- Remedy proposed by the playbook arm (not implemented): Give every committed revision something the target predicate can match, or do not create a revision that records nothing. Options: (a) a changeset whose operations all turn out to be no-ops returns the current head without writing a revision row or binding its key (spec 213 would have to say whether an all-no-op commit is a revision); (b) record each no-op operation as a content-free 'noop' record carrying the entity id and graph, so FR-001's predicate matches it and the first-tombstone rule clears the revision and unbinds the key; (c) at Final, clear the metadata of revisions with op_count 0…
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="bug-str-006"></a>
### Concurrent writers of one multigraph triple can lose its multiplicity or leave a ghost edge entry

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; concurrent keyed writers are not represented in the model and were not run. Severity is lowered one level from Medium.

Found by: A-structure F4 and S6 ([intent](../uplift/ivg-verus-initial/intent/graph-structure.md)).

Reproduced by: none

Expected: a triple's adjacency is a leaf, plus one child per edge and `#` while two or more edges share it, and holds no entry without a row (spec 234 FR-004/FR-006; spec 252 FR-003).

Observed: `PutKeyed` tests `'$Data(leaf)` and calls `Put` with no mutual exclusion (`Adjacency.cls:220-223`); writers hold shared locks only. Two first puts of one triple (two `%BuildIndices` jobs, `TraversalBuild.cls:131-133`, or two transactions) both take the `Put` branch; a writer that builds children from another's uncommitted leaf keeps them after that one rolls back; two `RemoveKeyed` of a two-edge triple can both pass their guards and leave a leaf with no rows. The comment at `Adjacency.cls:227-230` covers only an existing leaf.

Consequence: wrong degree and traversal multiplicity, or an edge entry with no row, until a rebuild.

Repair proposal (not implemented): serialize keyed transitions per triple with an exclusive lock on `^IVG.AdjT(g,s,p,o)` held to commit (mode-off writers never take it), or derive children and `#` from committed rows at rebuild. Governing statement: [structure.multigraph.layout](../ontology/features/graph-structure.g5.md#structure.multigraph.layout).

<a id="bug-str-007"></a>
### Restoring a multigraph archive into an indexed namespace loses its parallel edges' multiplicity

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; severity is lowered one level from Medium.

Found by: A-structure F5; A-platform F-B2.

Reproduced by: none

Expected: the multigraph mode is part of the snapshot so a restored multigraph keeps its parallel edges (spec 234 FR-001; `snapshot.py:157-160` comment). Spec 234 lists restore (US4) as not done but specifies no refusal.

Observed: the replacing restore runs `erase_all`, which clears the modes, then inserts rows (`snapshot.py:1234-1300`); `RowPut` sees mode off and writes single-edge leaves; `^IVG.GraphMode` arrives later with the globals (`:1554-1590`) and the keyed `out`/`in` lines are skipped as index-derived (`:1659-1665`); no rebuild follows.

Consequence: after a restore, parallel triples have degree 1 and one-hop Cypher answers once, until `sync()`.

Repair proposal (not implemented): restore `^IVG.GraphMode` before the rows, or rebuild the adjacency of multigraph graphs after the restore. Governing statement: [structure.multigraph.restore](../ontology/features/graph-structure.g5.md#structure.multigraph.restore).

<a id="bug-str-008"></a>
### A single-edge graph can get two rows for one triple from a stale multigraph flag or an unlocked mode switch

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; severity is lowered one level from Medium.

Found by: A-structure F6 and Q6.

Reproduced by: none

Expected: with multigraph mode off there is one row per triple (spec 234 FR-003); switching off is refused while a triple has two rows.

Observed: `u_spo_graph_ekey` admits `ekey<>0` rows in a mode-off graph (`schema.py:44`). `GraphMode.Set(off)` counts and then kills with no lock (`GraphMode.cls:35-40`); another engine's cached "on" (`admin.py:922-926`; `translator.py:441-457`) keeps emitting the `MAX(ekey)+1` insert (`translator.py:10368-10386`); a restore can do the same ([bug-str-007](#bug-str-007)).

Consequence: deleting either of the two rows kills the shared leaf (`RowRemove` → `Remove`), leaving the other row without adjacency.

Repair proposal (not implemented): re-read the mode per statement, or have the functional index refuse an `ekey<>0` row in a mode-off graph, and lock the mode switch against writers. Governing statements: [structure.multigraph.off](../ontology/features/graph-structure.g5.md#structure.multigraph.off), [structure.multigraph.switch](../ontology/features/graph-structure.g5.md#structure.multigraph.switch).

<a id="bug-str-009"></a>
### A failed indexed rebuild, or a failed rebuild after a bulk load, leaves a partial adjacency index

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; severity is lowered one level from Medium.

Found by: A-structure F8; reconstruction check 2(a)6, 2(a)11 and gap G39 ([reconstruction check](../uplift/ivg-verus-initial/reconstruction-check.md)).

Reproduced by: none

Expected: a failed rebuild "leaves the previous adjacency intact" (spec 248 spec.md:74-75; `BuildKG` comment `TraversalBuild.cls:46-58`); a bulk load de-duplicates and rebuilds whether it succeeds or fails (spec 252 FR-008).

Observed: the indexed path runs `%BuildIndices` after `TCommit`, and `PurgeIndex` is `RemoveAll` (`TraversalBuild.cls:124-136`; `AdjIndex.cls:29-32`), so the promise holds only for the non-indexed path (the catch does bump the token, `:164-170`); `BuildKG` commits every 50k rows; the `rebuild_edge_indices` procedure empties the whole index outside a transaction; a failed `_rebuild_after_load` is only logged.

Consequence: readers see a partial or empty adjacency after a failed rebuild, and a failed post-load rebuild goes unnoticed.

Repair proposal (not implemented): build into a staging tree and swap, or report the failure and keep `^IVG.AdjNoLock`-style degradation visible; raise from `_rebuild_after_load`. Open part: [structure.rebuild.failure](../ontology/features/graph-structure.g5.md#structure.rebuild.failure). Governing statements: [structure.rebuild](../ontology/features/graph-structure.g5.md#structure.rebuild), [structure.adjacency.bulk](../ontology/features/graph-structure.g5.md#structure.adjacency.bulk).

<a id="bug-str-010"></a>
### Node interning runs inside the functional-index callback, which ADR-0008 rules out

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; the impact depends on `^NKG` readers that were not traced. Severity is lowered one level from Medium.

Found by: A-structure F9.

Reproduced by: none

Expected: interning "cannot" live in the index, because a rollback leaves nameless IDs and the locks deadlock under overlapping writers (ADR-0008:66-67).

Observed: `RowPut` → `Put` interns when `^NKG` is built (`Adjacency.cls:95-107`); inside a transaction `InternNode`'s lock is held to commit, and after a 5 s wait it returns another transaction's possibly uncommitted index or `""` (`GraphIndex.cls:49-54`); `$Increment(^NKG(-3,s))` and `edgeCount` survive a rollback.

Consequence: 5 s stalls under overlapping writers and interned IDs or counters that disagree with committed rows until the next build sweep (`TraversalBuild.cls:478-479`).

Repair proposal (not implemented): move interning out of the callback (intern on read or at rebuild), as ADR-0008 decided, or amend the ADR with the accepted residue. Governing statement: [structure.adjacency.declared](../ontology/features/graph-structure.g5.md#structure.adjacency.declared).

<a id="bug-str-011"></a>
### The keyed adjacency writers turn errors into statuses that IRIS ignores, so a row can commit without its entry

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Relies on the documented IRIS behavior that a functional-index callback's status is not read; not run. Severity is lowered one level from Medium.

Found by: A-structure F10.

Reproduced by: none

Expected: every row change moves the adjacency in the same transaction, or the statement fails (spec 252 FR-001/FR-003).

Observed: `PutKeyed` and `RemoveKeyed` convert exceptions to statuses (`Adjacency.cls:264-267, 316-319`), while IRIS does not read a callback's status (4.7.0 row 17; `Adjacency.cls:51-53`); `Put` and `Remove` let exceptions through.

Consequence: in a multigraph graph a failing keyed write leaves a row without adjacency (drift), unlike a single-edge graph.

Repair proposal (not implemented): throw from the keyed writers as `Put`/`Remove` do. Governing statement: [structure.adjacency.declared](../ontology/features/graph-structure.g5.md#structure.adjacency.declared).

<a id="bug-str-012"></a>
### A ledger qualifier update reweights a multigraph triple's leaf to an edge that is not the lowest

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; severity is lowered one level from Medium.

Found by: A-structure F11.

Reproduced by: none

Expected: the leaf carries the weight of the lowest live `ekey` (spec 234 FR-004).

Observed: `LedgerApply.PersistQuals` calls `Reweight`, which sets the leaf unconditionally (`LedgerApply.cls:561-563`; `Adjacency.cls:334-339`); in an indexed namespace the call also duplicates the index's `RowUpdate`.

Consequence: weighted algorithms and traversals read the updated edge's weight for the whole triple.

Repair proposal (not implemented): reweight only when the updated row is the lowest `ekey`, or leave it to `RowUpdate` when indexed. Governing statements: [structure.multigraph.layout](../ontology/features/graph-structure.g5.md#structure.multigraph.layout), [structure.edge.weight](../ontology/features/graph-structure.g5.md#structure.edge.weight).

<a id="bug-str-013"></a>
### Deleting a relationship with delete_edge or Cypher DELETE leaves its reifications, edge embeddings and ledger statement behind

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only (`delete_edge` re-read by the reconstruction check; Cypher from the inventory). Severity is lowered one level from Medium.

Found by: A-ops hazard (a)2 and candidate simplification ([operations](../uplift/ivg-verus-initial/intent/operations.md)); A-structure Q1; reconstruction check 2(a)15, 2(b)5 and correction 3.

Reproduced by: none

Expected: every path that deletes graph content goes through the Eraser's transaction, and a path that removes content from one store but not the others is a defect (ADR-0004:71-82); no live ledger statement outlives its content.

Observed: `delete_edge` removes the row and adjacency only (`nodes_edges.py:1382-1456`), and Cypher `DELETE r` the row only (`translator.py:10699-10712`), while `Eraser.EraseEdgeRow` also removes `rdf_reifications`, `kg_EdgeEmbeddings` and `^IVG.Ledger("tuple"/"stmt")` (`Eraser.cls:641-677`). `DETACH DELETE` leaves the optimized and routed node vector tables and the temporal stores.

Consequence: orphan reifier nodes, edge vectors that still answer edge vector search, and live ledger statements for deleted relationships.

Repair proposal (not implemented): [simp-str-001](design_simplification.md#simp-str-001). Open parts: [structure.edge.delete.reifications](../ontology/features/graph-structure.g5.md#structure.edge.delete.reifications), [query.writes.delete-scope](../ontology/features/cypher.g5.md#query.writes.delete-scope). Governing statements: [erasure.entry-points.single-path](../ontology/features/erasure.g5.md#erasure.entry-points.single-path), [erasure.live-statements](../ontology/features/erasure.g5.md#erasure.live-statements).

<a id="bug-str-014"></a>
### delete_reification deletes the reifier's rows in every graph

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; severity is lowered one level from Medium.

Found by: reconstruction check 2(a)3 (verified `schema.py:3361-3392`).

Reproduced by: none

Expected: a call that names a graph acts in that graph only, and the same ID in two graphs is two nodes.

Observed: `delete_reification` deletes the reifier node, labels and properties with no graph predicate and outside the Eraser (`_engine/schema.py:3361-3392`).

Consequence: removing a reification in one graph deletes another graph's node that shares the reifier's ID.

Repair proposal (not implemented): scope the delete to the reification's graph and route it through the Eraser. Governing statements: [structure.reification](../ontology/features/graph-structure.g5.md#structure.reification), [graph.membership](../ontology/concepts/graph-scope.g5.md#graph.membership).

<a id="bug-str-015"></a>
### Without the adjacency index, edge writers write adjacency on a second connection that commits separately from the row

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; severity is lowered one level from Medium.

Found by: A-ops hazard (a)1 and (e)1-2 ([operations](../uplift/ivg-verus-initial/intent/operations.md)).

Reproduced by: none

Expected: each engine write is one transaction or nests in the caller's; only its own part is taken back on failure.

Observed: without `idx_edges_adj` (`engine.py:704-723`) the engine edge writers call `EdgeScan.*Adjacency` through `engine._iris_obj()`, a separate connection when the engine holds credentials (`engine.py:1916-1943`): `create_edge` (`nodes_edges.py:1226`), `set_edge_weight` (`:1366`), `delete_edge` (`:1445`), the `bulk_ingest_edges` fallback, `materialize_inference` and `retract_inference`.

Consequence: a rolled-back or failed edge write leaves its `^KG` entry (a traversal finds an edge with no row), and readers see the entry before the row commits.

Repair proposal (not implemented): write the non-indexed adjacency on the caller's connection, or after the row commits. Related question: [q-plt-006](open_questions.md#q-plt-006). Governing statement: [structure.adjacency.undeclared](../ontology/features/graph-structure.g5.md#structure.adjacency.undeclared).

<a id="bug-tmp-006"></a>
### Two Python temporal paths write structural rows for a temporal-only predicate

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Legacy paths read from source; not run. Severity is lowered one level from Medium.

Found by: A-temporal F9.

Reproduced by: none

Expected: a temporal-only predicate's write writes no `rdf_edges` row and no node (ADR-0015:14-16).

Observed: with the undocumented `IRISGraphEngine(..., temporal_structural_rows=True)` (spec 246, "not adopted"), `_own_structural_row` writes a marked row through `create_edge` for any predicate (`temporal.py:182-198, 306-308`); without the adjacency index, a named-graph `create_edge_temporal` or bulk write writes an unmarked mirror row and nodes for any predicate (`temporal.py:309-331, 455-475`), which is never retracted, and `RetractTemporalShadows` keeps the shadow because a row exists (`Adjacency.cls:694-731`).

Consequence: temporal-only edges appear in traversal and `MATCH` on these paths.

Repair proposal (not implemented): consult the registry on both paths, or remove the spec-246 path ([simp-tmp-001](design_simplification.md#simp-tmp-001)). Governing statement: [temporal.optout.effect](../ontology/features/temporal.g5.md#temporal.optout.effect).

<a id="bug-tmp-007"></a>
### create_edge_temporal with no timestamp stores the event at time 0

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only (verified by the reconstruction check, `temporal.py:292-294`). Severity is lowered one level from Medium.

Found by: A-temporal F11; reconstruction check 2(b)13 and correction 24.

Reproduced by: none

Expected: a write with no timestamp is stamped with the current time.

Observed: the single-edge path sends `0` (`temporal.py:294`), the store sends `"0"` (`iris_sql_store.py:2680`), and `InsertEdge` substitutes "now" only for `""` (`TemporalIndex.cls:51`); the bulk path substitutes "now" for 0 (`:170`). The unit test `test_timestamp_none_sends_empty_string` asserts only that `"A"` is in the call (`tests/unit/test_temporal_edges.py:58-62`).

Consequence: such events land in 1970 and are missed by recent-window reads, velocity and latest-event queries.

Repair proposal (not implemented): send `""` (or the current time) for None, and make the test assert the timestamp. Governing statement: [temporal.edge](../ontology/features/temporal.g5.md#temporal.edge).

<a id="bug-tmp-008"></a>
### The ObjectScript temporal purge-all and erase-all leave marked structural rows

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** From the operations inventory's sub-sweep, not re-read; severity is lowered one level from Medium.

Found by: reconstruction check 2(a)14; A-ops hazard (a)5.

Reproduced by: none

Expected: a marked structural row goes when the last timestamp of its triple goes, by delete or purge (ADR-0009 amendment, spec 254 Decision 1).

Observed: `TemporalIndex.Purge` and `TemporalIndex.EraseAll` clear the temporal stores without retracting marked rows (inventory); `TemporalPolicy.DropRows` deletes rows without ledger tuple cleanup.

Consequence: edges that exist only because of purged events stay visible to traversal and `MATCH`.

Repair proposal (not implemented): retract marked rows in both methods, rows first, as `RetireExpired` does. Governing statements: [temporal.purge](../ontology/features/temporal.g5.md#temporal.purge), [temporal.erase](../ontology/features/temporal.g5.md#temporal.erase).

<a id="bug-tmp-013"></a>
### A temporal write inside a purge's range that lands after the purge removed the row leaves a marked row with no timestamp

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Proved as a model trace; not probed. Not listed in spec 254's sign-off. Severity is lowered one level from Medium (the same consequence as [bug-tmp-005](#bug-tmp-005)).

Found by: [witness_purge_write_race_strands_row](results/temporal/20261114T040433Z-prove/receipt.json) in [temporal.rs](models/temporal/temporal.rs) (W-RACE-2, B-temporal round 1); the related route through a triple the purge never decided on is W-RACE-5 `witness_purge_write_race_strands_new_triple`, and the repair (the kill loop re-retracts every triple it left without a timestamp) is `witness_recheck_closes_kill_window` (premise P-LOCK).

Reproduced by: none

Expected: a marked row goes with the last timestamp of its triple (ADR-0009 amendment; spec 254 Decision 1).

Observed: the purge retracts the triple's marked row (`RetractTemporalRows`, `TemporalIndex.cls:1016`); a write at a timestamp inside the purge's range then asserts a fresh marked row; the purge's raw kill loop (`PurgeRawBefore`, `:876-915`) then removes that timestamp. `TemporalIndex` takes no lock.

Consequence: a marked structural edge with no timestamp, which no later purge or delete selects, stays visible to traversal and `MATCH` until an explicit `delete_edge`.

Repair proposal (not implemented): serialise a purge with writers of the same triple, or re-run the row step after the raw kill for triples written meanwhile; see [bug-tmp-011](#bug-tmp-011). Governing statements: [temporal.structural.end](../ontology/features/temporal.g5.md#temporal.structural.end), [temporal.purge](../ontology/features/temporal.g5.md#temporal.purge).

<a id="bug-srch-011"></a>
### Fusion chooses indexes from a snapshot taken when the engine started

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; severity is lowered one level from Medium.

Found by: A-search F6.

Reproduced by: none

Expected: fusion answers from indexes that cover the query's graph as they are now.

Observed: `_index_registry` is built at construction or schema check (`engine.py:367, 1885`); `bm25_drop` and `ivf_drop` remove nothing from it or from `_index_graph_scopes` (`vector.py:1868-1870, 2058-2060`).

Consequence: fusion keeps choosing a dropped index (whose search answers `[]` silently), never sees an index another process built, and can use an index another process rebuilt for another graph as this graph's.

Repair proposal (not implemented): read the index registry per call, or invalidate it on drop and on a recorded-graph mismatch. Governing statement: [search.scope.indexes](../ontology/features/search.g5.md#search.scope.indexes).

<a id="bug-srch-012"></a>
### Embedding identity enforcement allows the write when the registry read fails

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Proved on the model; the trigger (a failing registry SELECT after a successful one within the 30 s route cache) cannot be induced through public calls.

Found by: [witness_identity_fail_open](results/search/20261114T000543Z-prove/receipt.json) in [search.rs](models/search/search.rs) (B-search W-O3d; control `repair-fail-closed-off`); A-search F11 and S4.

Reproduced by: none

Expected: a registry read failure other than "no registry" raises (4.6.0 R161, `embeddings.py:438-444`).

Observed: `get_embedding_identity` returns None for any exception (`schema.py:1054-1056`) and `enforce_embedding_identity` then permits the write (`:1383-1385`). Width is still checked from the cached route.

Consequence: a writer whose mechanism, dtype or model disagrees with the recorded identity is admitted instead of refused with an explanation.

Repair proposal (not implemented): [simp-srch-002](design_simplification.md#simp-srch-002). Governing statement: [search.embedding.check_on_write](../ontology/features/search.g5.md#search.embedding.check_on_write).

<a id="bug-srch-013"></a>
### TextSearchEngine.search_documents is public, ignores graphs and very likely always fails

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only.

Found by: A-search F13.

Reproduced by: none

Expected: every search answers one graph and reports failure as failure.

Observed: it reads unqualified `docs` and uses `%FIND(text,?)` (`text_search.py:48-66`; compare `schema.py:2499-2502`); its LIKE fallback is graph-unscoped and errors return `[]`.

Consequence: callers get empty answers, or other graphs' documents.

Repair proposal (not implemented): remove it, or delegate to the scoped text search. Governing statement: [search.scope](../ontology/features/search.g5.md#search.scope).

<a id="bug-srch-014"></a>
### The embedding queue marks entries done without a stored vector

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** From the operations inventory (`EmbedQueue.cls:112-136, 300-330`; `embeddings.py:1964-1980`); not run. Severity is lowered one level from Medium.

Found by: A-ops candidate finding and hazard (c)5; reconstruction check 2(a)9 and correction 19.

Reproduced by: none

Expected: an entry is done once its vector is stored; a failed entry stays visible as failed.

Observed: the IRIS worker marks an entry DONE when `Prepare` fails or no row comes back; the Python worker sets DONE before its vector commits; `ClaimPendingBatch` does not claim, so two workers can process the same entry.

Consequence: nodes silently left without embeddings, and duplicate work under two workers.

Repair proposal (not implemented): claim entries, mark DONE after the vector commits and FAILED on error. Open part: [search.embedding.queue.processing](../ontology/features/search.g5.md#search.embedding.queue.processing).

<a id="bug-srch-015"></a>
### Route creation commits the routed table before its registry row, and an orphaned table makes every erase in the namespace fail

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Needs a failure between the commits; not run. Severity is lowered one level from Medium.

Found by: reconstruction check 2(a)10, 2(b)2 and correction 2.

Reproduced by: none

Expected: the routed table, its index state and its registry row are created together; a routed table never exists without its registry row.

Observed: `_create_routed_table`, `_attempt_route_index` and `_record_route_index_state` each commit (`_engine/schema.py` around 902, 922, 948) before the registry row (`embeddings.py:470-537`); the code comment says an orphan "makes every erase in the namespace fail with SQLCODE -124 and erase nothing".

Consequence: a failure between those commits blocks every erase in the namespace until an administrator removes the table.

Repair proposal (not implemented): write the registry row first (or in the same commit), and let the Eraser tolerate an unregistered `kg_emb_` table. Governing statements: [search.routes.create_on_write](../ontology/features/search.g5.md#search.routes.create_on_write), [search.routes.orphan](../ontology/features/search.g5.md#search.routes.orphan).

<a id="bug-plt-013"></a>
### A GraphQL GET request can run a Cypher write

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; severity is lowered one level from Medium.

Found by: A-platform F-H4 (sub-reader a, re-read by A-platform).

Reproduced by: none

Expected: writes are not reachable through safe HTTP methods; read-only mode and the key gate writes.

Observed: `executeCypher` is a Query field (`api/gql/schema.py:98-165`), and the `GraphQLRouter` is built without overriding `allow_queries_via_get` (`api/main.py:93`).

Consequence: with no key configured, a cross-site GET from a browser can run a `CREATE` against a reachable server.

Repair proposal (not implemented): make `executeCypher` a mutation, or disable queries via GET. Governing statement: [access.surfaces](../ontology/concepts/access.g5.md#access.surfaces).

<a id="bug-plt-014"></a>
### remove_legacy_objects reports later procedures of a class as removed when the class's delete failed

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Confirmed by reading `legacy.py:680-684`; the failing delete was not run.

Found by: A-platform F-S4.

Reproduced by: none

Expected: the removal report is exact (spec FR-011).

Observed: when `cls in classes_done`, the item is set `removed=True` without consulting the first delete's result (`legacy.py:680-684`).

Consequence: an operator is told objects were removed that are still installed.

Repair proposal (not implemented): remember each class's result and copy it. Governing statement: [install.legacy](../ontology/concepts/install.g5.md#install.legacy).

<a id="bug-plt-015"></a>
### An engine whose schema name differs only in case from the record loads classes under its own spelling

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; no test covers it. Severity is lowered one level from Medium.

Found by: A-platform F-S6.

Reproduced by: none

Expected: `ivgalt` and `IVGALT` are "recorded and compared as one" (spec 262:204-205).

Observed: comparison is case-insensitive (`schema_name.py:138-140`), but the source rewrite, the deploy and `foreign_schema_classes` use the engine's spelling (`_engine/schema.py:2219`; `class_deploy.py:204-209, 318`); only the marker probe hedges with `.upper()` (`schema_name.py:231-234`).

Consequence: `ivgalt.SqlProcs` can be loaded beside `IVGALT.SqlProcs`.

Repair proposal (not implemented): canonicalize to the recorded spelling before the rewrite. Governing statement: [install.schema.name](../ontology/concepts/install.g5.md#install.schema.name).

<a id="bug-plt-016"></a>
### A restore swallows a global line that fails to import

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; severity is lowered one level from Medium.

Found by: A-platform F-B4; A-ops candidate finding.

Reproduced by: none

Expected: failures are counted and reported (R271's intent for `failed_rows`).

Observed: a failed global line is logged at debug only (`_engine/snapshot.py:1683-1684`); it is neither counted nor listed.

Consequence: a restore reports success with globals (adjacency, ledger, temporal) missing.

Repair proposal (not implemented): count and list failed global lines with the failed rows. Governing statement: [install.snapshot.failure](../ontology/concepts/install.g5.md#install.snapshot.failure).

<a id="bug-plt-017"></a>
### A cached personalized PageRank answer does not notice a node created after it

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; severity is lowered one level from Medium.

Found by: A-platform F-A4 (sub-reader c); A-structure Q8 (whether WCC and CDLP need the same for node-only writes, not inspected).

Reproduced by: none

Expected: a cached answer is valid only while nothing it depends on has changed; R313 added a node-set key for PageRank for this reason.

Observed: PPR's cache key has no node-set token, and creating a node does not move the graph-version token.

Consequence: `[]` cached for a seed that did not exist yet is served after `create_node(seed)` until the next adjacency write.

Same creation trigger/effect as the retained playbook record F-1004, which carries an inherited live observation and refutes its node-deletion premise. This is one creation defect, not two discoveries. The new global PageRank contract does not cover PPR.

Repair proposal (not implemented): key PPR on the node-set token as PageRank is. Governing statements: [algorithms.cache.token](../ontology/features/algorithms.g5.md#algorithms.cache.token), [algorithms.cache](../ontology/features/algorithms.g5.md#algorithms.cache).

<a id="bug-plt-018"></a>
### Capabilities and status report native algorithms that are not proven or routed

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Confirmed by reading; not run.

Found by: A-platform F-A5 (sub-reader c).

Reproduced by: none

Expected: status tells an operator which algorithms run natively and on what evidence.

Observed: `ppr_arno`, `wcc_arno` and `rust_algorithms` come from a hard-coded list (`NKGAccelLoader.cls:99-127`; `iris_sql_store.py:2991-3000`), though only PageRank is proven and routed; the status "algorithms:" line prints capability keys (`status.py:325-331`); no field shows the proof's validity or the per-algorithm route.

Consequence: operators are told algorithms are accelerated that always run on the Owner.

Repair proposal (not implemented): report the per-algorithm route and proof state. Governing statement: [algorithms.proof](../ontology/features/algorithms.g5.md#algorithms.proof).

<a id="bug-plt-019"></a>
### The HTTP server and the SDK retry a failed Cypher write, so a write can apply twice

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** From the operations inventory (`cypher_api.py:239-251`; `sdk.py:210-225`); not run. Severity is lowered one level from Medium.

Found by: reconstruction check 2(a)13 and correction 18.

Reproduced by: none

Expected: a retry does not repeat a write that committed; only ledger commits with an idempotency key de-duplicate.

Observed: `_run_cypher` retries any exception once on a fresh engine; the SDK's `_post` retries 5xx responses and timeouts.

Consequence: a write whose response failed after commit can be applied twice (for example two parallel edges in a multigraph).

Repair proposal (not implemented): retry only reads, or only errors raised before the write began. Governing statement: [access.retries](../ontology/concepts/access.g5.md#access.retries).

<a id="bug-plt-020"></a>
### The MCP evidence search binds its natural-language input as a node ID

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; MCP needs %AI, which Community lacks.

Found by: A-platform F-H7 (sub-reader a).

Reproduced by: none

Expected: the tool does what its description says: search with a natural-language input.

Observed: `EvidenceSearch` documents a natural-language input but binds it as a node ID (`MCPTools.cls:190-216`).

Consequence: the tool answers nothing for ordinary questions.

Repair proposal (not implemented): run a text or vector search on the input, or describe the parameter as a node ID. Governing statement: [access.mcp](../ontology/concepts/access.g5.md#access.mcp).

<a id="bug-plt-021"></a>
### The Txn_End and Txn_Undo SQL procedures end every transaction level, the caller's included

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** From the operations inventory; not run.

Found by: reconstruction check 2(a)16.

Reproduced by: none

Expected: IVG takes back only its own level of a caller's transaction (4.6.4).

Observed: any SQL client can call `Txn_Begin`/`Txn_End`/`Txn_Undo`, and `End(1)`/`Undo(1)` end every level.

Consequence: a SQL caller that nests IVG's transaction procedures in its own transaction loses or commits its outer work.

Repair proposal (not implemented): end or undo only to the level the matching `Txn_Begin` found. Governing statement: [structure.write](../ontology/features/graph-structure.g5.md#structure.write).

<a id="bug-plt-025"></a>
### An engine whose first strict-mode check ran before the ledger classes were installed never enforces strict mode

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Proved as a model trace (control `g-class-present-recomputed`); not probed. Severity is lowered one level from Medium.

Found by: [witness_class_absent_cached_for_the_engines_lifetime](results/platform/20261114T002651Z-prove/receipt.json) in [platform.rs](models/platform/platform.rs); review R3-platform R1-11.

Reproduced by: none

Expected: strict mode applies to an engine whenever the ledger is strict, however long ago the engine was created (spec 213 strict-mode contract).

Observed: `LedgerGuard` caches `_class_present` for the engine's lifetime (`ledger/guard.py:45-49`); when the first probe finds no ledger class (for example an engine created before setup compiled the classes), the guard treats the ledger as never enabled from then on.

Consequence: a long-lived engine (a server process started before setup) writes unrecorded under strict mode until it is restarted.

Repair proposal (not implemented): re-probe the class when it was absent, at least whenever `Meta()` would be re-read, or enforce strict on the server ([simp-plt-001](design_simplification.md#simp-plt-001)). Governing statement: [access.ledger_strict.engine_cache](../ontology/concepts/access.g5.md#access.ledger_strict.engine_cache).

<a id="bug-cyp-004"></a>
### A write inside CALL { } is refused with a raw SQL syntax error instead of a clear refusal

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Found by: reconstruction check 2(a)15 and correction 22 (the subquery translation handles only `MATCH`/`WHERE`/`UNWIND`, `translator.py:14635-14663`); review R3-platform R1-10.

Reproduced by: [cypher_subquery_write](receipts/native/cypher_subquery_write.json) — `CALL { CREATE (n:SubqProbe {id: 'subq|1'}) } RETURN 1 AS one` returned a result whose `error` field holds SQLCODE -12 ("A term expected…"), raised nothing and wrote nothing; a plain `CREATE` wrote its node. This meets "carried out or refused" (verdict OBSERVED_AS_EXPECTED for that intent); the defect is the form of the refusal.

Expected: a write clause inside a `CALL { }` body is carried out, or the whole query is refused; it is never skipped silently.

Observed: the subquery translator does not classify `CALL { CREATE … }` as a write and emits SQL that IRIS cannot parse; the error surfaces only as an internal SQL message in the result object, with no raise, no `GraphWriteError` and no strict-mode refusal. A silent drop when `RETURN` reads only matched variables remains unobserved.

Consequence: callers cannot tell an unsupported construct from a server fault; the limitation is not listed among the documented deviations.

Repair proposal (not implemented): refuse a write inside `CALL { }` at translation with a named error, and list it in the conformance deviations. Governing statements: [query.writes.subquery](../ontology/features/cypher.g5.md#query.writes.subquery), [query.conformance](../ontology/features/cypher.g5.md#query.conformance).

<a id="bug-cyp-005"></a>
### An all-graphs read skips graph correlation when only the nodes table looks single-graph

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Data-dependent; source reading only. Severity is lowered one level from Medium.

Found by: A-cypher F6.

Reproduced by: none

Expected: an all-graphs read pairs each node only with its own graph's rows.

Observed: `_all_graphs_correlated` asks `_more_than_one_graph`, which reads only `nodes` (`engine.py:612-639`; `translator.py:782-794`); `rdf_props` has no foreign key to `nodes` (`schema.py:411-418`), and 4.7.0 states that property rows left by SQL-removed nodes exist (CHANGELOG l. 54-58).

Consequence: with nodes in one graph and leftover property rows of the same ID in another, the SQL path reads the other graph's value; the native path does not, so shadow mode raises or the answers differ.

Repair proposal (not implemented): probe `rdf_props` too, or correlate whenever any graph-owned table holds two graphs. Governing statement: [query.graph-scope.read](../ontology/features/cypher.g5.md#query.graph-scope.read).

<a id="bug-cyp-006"></a>
### USE GRAPH accepts graph names the graph keys refuse

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; severity is lowered one level from Medium.

Found by: A-cypher F8.

Reproduced by: none

Expected: the reserved name `"0"` and control characters are refused before anything is written (ADR-0003).

Observed: `parser.py:174-192` accepts any string; refusal happens only where `ForIndex` runs, so a label-less `USE GRAPH '0' CREATE ({id:'a'})` writes a `nodes` row in graph `'0'` that `^KG` cannot represent, and native reads throw and fall back to SQL.

Consequence: rows in an unrepresentable graph, which every later functional-index callback for that graph rejects.

Repair proposal (not implemented): call `validate_graph_name` on the graph context at parse or translate. Governing statement: [query.graph-scope.names](../ontology/features/cypher.g5.md#query.graph-scope.names).

<a id="bug-cyp-007"></a>
### A run that started before a property-layout change can recompile a shape's class for the old layout under newer runs

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Proved on the model; needs a layout recompile inside one run's window, not probed.

Found by: [witness_straggler_recompiles_for_an_old_layout](results/platform/20261114T002651Z-prove/receipt.json) in [platform.rs](models/platform/platform.rs) (B-platform P2, W-O2c).

Reproduced by: none

Expected: a stale entry is never run (ADR-0014:16-23).

Observed: the check is made once per run (`Exec.cls:158`); a run whose `Props.Begin` preceded an `rdf_props` recompile reaches `For` after a newer run compiled the shape, rewrites the entry and recompiles the same class for the old layout (`Gen.cls:63-101`).

Consequence: the newer run's next walk reads old global names; only in-flight runs are affected and the entry heals on the next check.

Repair proposal (not implemented): [simp-cyp-001](design_simplification.md#simp-cyp-001). Governing statement: [query.compiled.never-stale](../ontology/features/cypher.g5.md#query.compiled.never-stale).

<a id="bug-cyp-008"></a>
### The compiled-plan read-back after a synchronous build skips the class-name check

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Proved on the model; needs a role with RW on the database (the R311 threat) and a race.

Found by: [witness_readback_trusts_the_entrys_class](results/platform/20261114T002651Z-prove/receipt.json) in [platform.rs](models/platform/platform.rs) (B-platform P3, W-O2d; control `p-no-class-name-check`).

Reproduced by: none

Expected: a planted or foreign entry never selects the class a run executes (4.6.0 R311; ADR-0014).

Observed: `Gen.For` lines 102-103 return the entry's class if its status is ok, without line 73's `IVGC.P<h>` name check.

Consequence: an entry planted in the window after a sync build points the run at another shape's class.

Repair proposal (not implemented): apply line 73's checks at line 103. Governing statement: [query.compiled.integrity](../ontology/features/cypher.g5.md#query.compiled.integrity).

<a id="bug-led-002"></a>
### A ledger commit into a graph during its erase can lose the new relationship's statement entry

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; not run. Severity is lowered one level from Medium.

Found by: A-history F4 scenario 2 ([intent](../uplift/ivg-verus-initial/intent/ledger-history.md)).

Reproduced by: none

Expected: every live relationship committed through the ledger has its statement entry (the statement index addresses it).

Observed: the Eraser takes no ledger head lock; a ledger commit can insert a relationship (and its endpoints) after the erase's `DELETE rdf_edges` and before `EraseLedgerFor`, which then kills every statement entry of the graph (`Eraser.cls:1107-1143`).

Consequence: the new relationship stays live with no statement, so later ledger operations by statement and redaction attribution cannot reach it.

Repair proposal (not implemented): see [q-004](open_questions.md#q-004) (serialise erase with commits, for example by taking the head lock in the Eraser while the ledger is enabled). Open part: [erasure.concurrency](../ontology/features/erasure.g5.md#erasure.concurrency).

<a id="bug-led-004"></a>
### Re-enabling the ledger during an unfinished redaction skips the adoption without telling the caller

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; severity is lowered one level from Medium.

Found by: A-history F14; review R1-core CV-6 and R1-6.

Reproduced by: none

Expected: enabling adopts the current state, so that writes made while the ledger was disabled are recorded and verify is equal.

Observed: `enable()` runs `verify(adopt=True)` (`client.py:288-296`), which answers `redaction_in_progress` while the marker exists and adopts nothing (`replay.py:812-823`); `enable()` neither raises nor reports it.

Consequence: the ledger is enabled with unrecorded writes; a later verify diverges with no hint that the adoption was skipped.

Repair proposal (not implemented): refuse `enable` while a redaction is unfinished, or report the skipped adoption. Related question: [q-led-003](open_questions.md#q-led-003). Governing statement: [ledger.lifecycle](../ontology/features/ledger.g5.md#ledger.lifecycle).

<a id="bug-led-005"></a>
### A reifier's delete record written inside a tenant's revision is reached by neither redaction target

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; nothing tests it. Severity is lowered one level from Medium.

Found by: review R1-core CV-4 and R1-11.

Reproduced by: none

Expected: every record of the target becomes a tombstone (ADR-0013; spec 256 FR-001).

Observed: `DeleteRelInternal` writes a `delete_node` record (graph `""`, the reifier's own ID, prior = its label and property snapshot) for each reifier of a deleted edge; `Matches` reaches it only through a prefix the reifier ID carries, so neither `redact(tenantGraph)` nor `redact(None, prefix=tenant)` tombstones it unless the reifier ID has the tenant prefix.

Consequence: the reifier's labels and properties from the tenant's own revision stay in clear after a complete redaction.

Repair proposal (not implemented): attribute a cascade record to the relationship that caused it (for example by recording the edge's endpoints in it, as [simp-002](design_simplification.md#simp-002) proposes for qualifier records), or name reifier IDs with the tenant prefix. Governing statement: [redaction.target.nodes](../ontology/features/redaction.g5.md#redaction.target.nodes).

<a id="bug-led-006"></a>
### A redaction that finds nothing to tombstone sets no marker, so a target record committed meanwhile survives a complete run

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Shown by a reviewer's scratch model witness; not probed. One `create_temporal_edge` of a temporal-only predicate into the target suffices, because it writes no row that the final step's liveness check reads (review round2-core); otherwise the trace needs a create and a delete of target content inside the run's window.

Found by: review R1-core CV-2 and R1-9 (scratch witness `rv_witness_unstarted_run_completes_with_target_record`, `$RUN_DIR/agents/R1-core/adv_valid/verus.log`); `theorem_completion` holds only for started runs ([receipt](results/ledger_redaction/20261114T044401Z-prove/receipt.json)).

Reproduced by: none

Expected: while a redaction runs, nothing may be written into its target, and a complete run leaves no target record (spec 256 Decision 3; ADR-0013).

Observed: `BatchInLock` writes the marker only at the first match (`LedgerRedact.cls:322-324`), and `FinalInLock` returns without a revision when there is no marker and no statement; `BlocksCommit` refuses only while a marker exists.

Consequence: a target commit that lands after the scan has passed its position is admitted and survives a run that reports `complete`.

Repair proposal (not implemented): claim the marker at the start of the first batch ([simp-001](design_simplification.md#simp-001)). Governing statement: [redaction.batches.commits](../ontology/features/redaction.g5.md#redaction.batches.commits).

<a id="bug-led-008"></a>
### Under strict mode the only API delete is a ledger changeset, which leaves documents, temporal, FHIR and search-index content that redaction and verify cannot see

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; not probed. Severity is lowered one level from Medium.

Found by: review round2-core R2-3 (expectation E10).

Reproduced by: none

Expected: an erase removes content from every store that holds it, and a path that removes content from one store but not the others is a defect (ADR-0004:71-82); a redaction is refused while the target's content is live.

Observed: under strict mode `erase_graph`, `erase_all` and `delete_nodes_by_prefix` raise `LedgerStrictModeError` ([platform_strict_paths](receipts/native/platform_strict_paths.json)), so the only API deletion is a ledger `delete_node`/`delete_relationship`. `LedgerApply.DeleteNodeRows` (`LedgerApply.cls:353-372`) deletes `kg_NodeEmbeddings(_optimized)`, `rdf_labels`, `rdf_props` and `nodes` only; it leaves `Graph_KG.docs` (no foreign key, `schema.py:471-479`), the temporal index, the FHIR side tables, routed node vectors and the named search indexes (a routed table's foreign key may instead refuse the whole changeset). `LiveRows` and verify read none of these stores.

Consequence: "delete through the ledger, then redact" completes with `verify()` equal while the tenant's text, vectors and events remain.

Repair proposal (not implemented): route the ledger's node delete through the Eraser's node erase ([simp-str-001](design_simplification.md#simp-str-001)'s single path), or let erasure run under strict mode as a recorded operation; see [q-003](open_questions.md#q-003). Open part: [redaction.strict-mode](../ontology/features/redaction.g5.md#redaction.strict-mode). Governing statements: [erasure.entry-points.single-path](../ontology/features/erasure.g5.md#erasure.entry-points.single-path), [redaction.after-erasure](../ontology/features/redaction.g5.md#redaction.after-erasure).

<a id="bug-led-009"></a>
### Post-commit properties bypass strict mode and the block on commits into a target being redacted

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Source reading only; the strict-mode and mid-redaction cases were not run.

Found by: review round2-core R2-4 (expectation E11).

Reproduced by: none — [ledger_post_commit_verify](receipts/native/ledger_post_commit_verify.json) shows only that post-commit properties are written outside the revision (verify diverges).

Expected: strict mode refuses writes made outside the ledger; while a redaction runs, a commit with a record in its target is refused (spec 256 Decision 3).

Observed: `ledger.commit` writes `post_commit_properties` by direct SQL after the revision (`client.py:430-487`); the strict guard is not consulted for them and `BlocksCommit` checks only the changeset's records.

Consequence: a commit whose post-commit properties name `tenant|…` makes a default-graph prefix target live in the middle of a run (the final step then refuses and the marker stays; for a prefix target an erase by prefix cannot clear such a property row, because the prefix erase selects IDs from node rows ([bug-led-010](#bug-led-010)), so only an explicit-id erase or raw SQL clears it, and until then the namespace-wide marker blocks readers, verify and every other target), and after a completed redaction it re-creates erased IDs as property rows.

Repair proposal (not implemented): check post-commit properties against strict mode and the redaction marker before writing them, or record them in the revision. Related: [q-010](open_questions.md#q-010), [bug-led-003](#bug-led-003). Governing statements: [ledger.unrecorded](../ontology/features/ledger.g5.md#ledger.unrecorded), [redaction.batches.commits](../ontology/features/redaction.g5.md#redaction.batches.commits).

<a id="bug-led-010"></a>
### A property row with no node row survives the prefix erase, and every later prefix redaction of its tenant is refused

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Found by: review round 3 R3-4 (scratch model L-d); integrated as witness W6 [witness_orphan_prop_row_blocks_prefix_redaction](results/ledger_redaction/20261114T044401Z-prove/receipt.json) in [redaction.rs](models/ledger_redaction/redaction.rs) (a `PropRow` goes with a prefix erase only when its node row exists in the same graph), with control [prefix-erase-takes-orphan-props](results/ledger_redaction/20261114T044600Z-control-prefix-erase-takes-orphan-props/receipt.json) (EXPECTED_FAIL).

Reproduced by: [redaction_orphan_prop_blocks](receipts/native/redaction_orphan_prop_blocks.json) — a commit with `post_commit_properties = {"tP|x": {...}}` (the node `tP|x` is never created) leaves 1 property row and 0 node rows; after `delete_nodes_by_prefix("tP|")` the row is still there and `redact(None, prefix="tP")` is refused `RedactionTargetLiveError`; a second prefix erase changes nothing and the redaction is refused again; `delete_node("tP|x", graph="")` removes the row and the redaction then completes.

Expected: an erase removes the tenant's content from every store that holds it (ADR-0004; CONTEXT.md "Erasure"), and the documented tenant recipe — erase by prefix, then redact by prefix (ADR-0013; USER_GUIDE) — completes.

Observed: `Graph_KG.rdf_props` has no foreign key to `Graph_KG.nodes` (`schema.py:411-418`), and `ledger.commit` inserts post-commit property rows for any ID (`client.py:466-473`); `Eraser.EraseNodes` collects the IDs to erase from `Graph_KG.nodes` rows only (`Eraser.cls:331-349`), while `LedgerRedact.LiveRows` counts `rdf_props` rows by prefix.

Consequence: a loud refusal, not silent retention: the tenant cannot be redacted through the documented recipe until an administrator finds the orphan IDs and erases them by ID. If the orphan row is written while a redaction runs ([bug-led-009](#bug-led-009)), the run's final step refuses and its marker blocks the namespace's readers, verify and other targets until then. Severity Low because the refusal is visible and an explicit-id erase repairs it.

Repair proposal (not implemented): let the prefix erase also select property (and label) rows by ID prefix, or refuse `post_commit_properties` for IDs with no node row; the first keeps the recipe working for data written before the change. Related: [bug-led-007](#bug-led-007) (the same node-row selection misses temporal-only events), [simp-003](design_simplification.md#simp-003). Governing statements: [erasure.prefix-match](../ontology/features/erasure.g5.md#erasure.prefix-match), [redaction.after-erasure](../ontology/features/redaction.g5.md#redaction.after-erasure).

<a id="bug-str-016"></a>
### Without the adjacency index, a temporal write to an existing triple changes its stored weight without moving the version token

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Code reading only; non-indexed installs only; not run natively.

Found by: review round2-domains R2-5 (code reading); reclassified from an observation to a suspected bug by review round 3 R3-8.

Reproduced by: none

Expected: every change to the adjacency index, its edges or its labels increases the graph-version token (CONTEXT.md "Graph-Version Token"; [structure.rebuilt.token](../ontology/features/graph-structure.g5.md#structure.rebuilt.token)).

Observed: `Adjacency.PutShadow` on a triple that already has an adjacency entry rewrites the `out`/`in` weight and moves `^KG("__version")` only when the entry is new (`Adjacency.cls:128-136`), unlike `Reweight` (`:340`).

Consequence: a token-validated cache can serve the old weight. The algorithm cache `^IVG.AlgoCache` admits only PageRank, PPR, WCC and CDLP, which count multiplicity and ignore weights, so it is unaffected. `^ArnoKG` snapshots are validated only by the token (`GraphStores.cls:131`); whether any `^ArnoKG` reader uses weights is not traced, because the Arno library is not in this repository.

Repair proposal (not implemented): bump the token in `PutShadow` when the stored weight changes, as `Reweight` does.

<a id="bug-plt-026"></a>
### Setup records an explicitly named schema while IVG's tables sit in one other schema

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Code reading only (review round 3 R3-reader H3); not run natively. The only upstream test of FR-009 uses a default engine (`tests/e2e/test_262_record.py`).

Found by: review round 3 R3-reader H3.

Reproduced by: none

Expected: spec 262 FR-009: when IVG's tables are in exactly one schema and it is not the engine's, the engine "MUST be refused with an error naming that schema … and MUST record nothing"; the explicit-name exception is stated only for tables in *more than one* schema. FR-005/FR-006 exist so that two schemas never silently share the namespace-wide globals.

Observed: `initialize_schema` sets `how = "explicit"` and records the engine's schema whenever the name was given by argument or `IVG_SCHEMA_PREFIX`, including when every IVG table is in one other schema (`_engine/schema.py:2229-2242`); the engine's own comment says the explicit branch is for "several schemas" (`engine.py:295-297`).

Consequence: the namespace records schema T while the adjacency index and the other namespace-wide globals still hold schema S's data, the sharing FR-005/FR-006 were written to prevent.

Interpretation needing confirmation: FR-009's rationale ("an engine never writes to a schema it was not given") is met by an explicit name, so the as-built branch may be intended; the wording of FR-009 is not. See [install.schema.existing](../ontology/concepts/install.g5.md#install.schema.existing).

Repair proposal (not implemented): apply the explicit branch only when IVG's tables are in more than one schema, or amend FR-009 to allow an explicit name in the one-other-schema case and say what happens to the other schema's globals.

<a id="bug-led-011"></a>
### Erasing a long list of node IDs or relationships without a caller's transaction commits once per 500 entries

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Code reading only (review round 3 R3-reader M4); no failure was injected natively (the erasure failure-injection suites could not run on Community Edition).

Found by: review round 3 R3-reader M4.

Reproduced by: none

Expected: an erase runs as one transaction and either completes or leaves the content untouched (ADR-0004:21-23; [erasure.atomic](../ontology/features/erasure.g5.md#erasure.atomic)).

Observed: the store's `delete_nodes` and `delete_edges` split the IDs into chunks of 500 (`_DELETE_CHUNK`, `stores/iris_sql_store.py:1302-1305`) and call the Eraser once per chunk (`:1347-1358`); without a caller's transaction `_eraser_txn` commits immediately and "each Eraser call owns its transaction" (`:1451-1472`). `bulk_delete_nodes` batches by design and reports a failed batch as wholly "rolled back" even when its earlier chunks committed (`_engine/nodes_edges.py:2283-2298`). `erase_bare_nodes` commits per 10,000 IDs (`Eraser.cls:1297-1304`).

Consequence: a failure part-way through a large ID-list erase leaves the earlier chunks erased and the rest live; running the same erase again finishes it. Inside a caller's transaction the chunks nest and roll back together.

Repair proposal (not implemented): run the chunks inside one IVG transaction level when there is no caller transaction, or document the per-chunk commit and report the committed count on failure.

Iteration 2 scope: [bulk_delete](models/bulk_delete/NOTES.md) corroborates the caller's counts and partial-effect risk at Python unit level. Actual `_delete_in_scope` deletes the primary nodes before later reifier cleanup; an injected cleanup-provider failure makes `bulk_delete_nodes` report the whole request as failed while those nodes are gone. This is a related producer path, not a new per-chunk IRIS reproduction or a new finding. The Verus model represents the partial effect and continued later batches. Owner: [structure.node.delete.bulk](../ontology/features/graph-structure.g5.md#structure.node.delete.bulk); the store's real per-chunk transaction behavior remains inherited/inspected.

<a id="bug-srch-017"></a>
### A BM25 index built before 4.0.0 reports the default graph, so the default graph's fusion reads another graph's documents as its own

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Code reading only (review round 3 R3-reader M25); not run natively (no pre-4.0.0 index on this arm).

Found by: review round 3 R3-reader M25.

Reproduced by: none

Expected: a BM25 index records which graph it covers, and fusion reads the graph's own index ([search.scope.indexes](../ontology/features/search.g5.md#search.scope.indexes); spec 230 graph scope).

Observed: an index left over from a pre-230 build has no graph subscript and covered every graph; `BM25Index.Info` reports graph `""` for it, the same value the default graph reports (`BM25Index.cls:603-611`, whose comment says to rebuild such an index). `_pick_fusion_index` prefers an index recorded for `graph_id` (`_engine/vector.py:164-206`), so the default graph's fusion picks it without a warning.

Consequence: default-graph fusion can return node IDs from other graphs until the index is rebuilt.

Repair proposal (not implemented): mark pre-230 indexes as unscoped during upgrade (or refuse them in fusion with a message to rebuild).

<a id="bug-plt-027"></a>
### BulkLoader's node and edge loads write without indexes and return before rebuilding them

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Code reading only (review round 3 R3-reader M6); the bulk-loader suites passed (`test_bulk_loader_live` 18, `test_bulk_loader_endpoints` 5), which exercise the documented call sequence.

Found by: review round 3 R3-reader M6.

Reproduced by: none

Expected: spec 252 FR-008: "Bulk paths that write `%NOINDEX` MUST dedupe and MUST end in `%BuildIndices` before returning, success or failure"; ADR-0008: "No `%NOINDEX` writer returns before its `%BuildIndices`."

Observed: `BulkLoader.load_nodes` and `load_edges` write with `%NOINDEX %NOCHECK` by default and leave the rebuild to the caller ("Call rebuild_all_indices() after loading", `bulk_loader.py:380-395`); `bulk_load_session` rebuilds, and inside a caller's transaction leaves it to `sync()` (`:540-603`).

Consequence: a caller that uses the class directly and skips `rebuild_all_indices()` leaves the adjacency index and SQL indexes stale; traversal and indexed lookups miss the loaded rows.

Interpretation needing confirmation: the class may be meant as a low-level tool outside FR-008, with `bulk_load_session` as the governed path; no source says so.

Repair proposal (not implemented): rebuild at the end of `load_nodes`/`load_edges` (or make `use_noindex` imply it), or document the class as outside FR-008. Related: [bug-plt-011](#bug-plt-011), [bug-plt-012](#bug-plt-012). Governing statement: [structure.adjacency.bulk](../ontology/features/graph-structure.g5.md#structure.adjacency.bulk).

<a id="bug-str-017"></a>
### Nothing reports an existing graph whose name is now refused, as ADR-0003 promises, and verification itself refuses the name "0"

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

**Suspected.** Code reading only (review round 3 R3-reader M10); no pre-existing graph named "0" could be created on this arm, because new writes of the name are refused ([graph_structure_keys](receipts/native/graph_structure_keys.json) K1, K2).

Found by: review round 3 R3-reader M10; A-structure Q3.

Reproduced by: none

Expected: ADR-0003 (Accepted): "the validator rejects new ones and `verify_graph` reports existing violations" (`docs/adr/0003-*.md:68-69`).

Observed: `GraphVerify.VerifyGraph` calls `GraphKey.ForIndex(pGraph)` first (`GraphVerify.cls:40-42`), which throws for `"0"`; no other call lists graphs with refused names; every adjacency rebuild throws on such a row (`TraversalBuild.cls:46-53`).

Consequence: an install that already holds such a graph has no way to find it through IVG, and its rebuilds fail.

Repair proposal (not implemented): a verification pass that lists rows whose graph name the validator refuses, without deriving their key. Related: [q-str-001](open_questions.md#q-str-001). Governing statement: [graph.names.report](../ontology/concepts/graph-scope.g5.md#graph.names.report).

<a id="bug-test-001"></a>
### The eigenvector routing unit test fails at the baseline because its mock store lacks the loners argument

Severity: Low · Decision: Open

Run: Uplift 2026-11-13

Found by: the upstream unit suite at the baseline (Python 3.11.18, driver 5.3.2 per `uv.lock`, run through `native/run_upstream.py`): 1 of 18 failures.

Reproduced by: `tests/unit/test_centrality_unit.py::TestEngineRoutingThroughStore::test_eigenvector_routes_to_store` fails alone without IRIS (log `$RUN_DIR/tests/centrality-isolated.log`): `1 failed`.

Expected: `PRE_RELEASE_CHECKLIST.md:282` records the unit suite at `724dbd0b` as "24,564 passed, 0 failed".

Observed: since `99b00ce9` (2026-11-07, an ancestor of `724dbd0b`) the engine calls `execute_eigenvector(..., loners=list(self._loners()))` (`_engine/algorithms.py:1518-1523`), but the test's mock store defines `execute_eigenvector(self, max_iter, tol, top_k, progress_callback=None)` (`tests/unit/test_centrality_unit.py:66-68`).

Consequence: the suite cannot be green at the released commit; the checklist's claim is inaccurate. No product behavior is affected.

Repair proposal (not implemented): add `loners=None` to the mock and assert it is passed.

<a id="bug-adp-001"></a>
### A batch fallback in the embedded cursor reruns the rows that already ran

Severity: Low · Decision: Open

Run: Consolidated uplift 2026-11-14

**Suspected:** the control flow is observed on the real cursor with a scripted `iris.sql`; whether IRIS raises an unsupported-path error at a row after a successful prepare is not shown. Severity is lowered one level from Medium.

Found by: [witness_ddtab_mid_batch_reruns_rows](results/embedded_no_data/20261115T042913Z-prove/receipt.json) in [embedded_no_data.rs](models/embedded_no_data/embedded_no_data.rs), with control `repair-fallback-resumes` (EXPECTED_FAIL); reading `embedded.py:387-413` while lifting public case M17.

Reproduced by: none natively; unit level on the pin's real `EmbeddedCursor.executemany` ([binding receipt](results/embedded_no_data/20261115T042852Z-binding/receipt.json), `observed_rerun`: rows `[0, 0, 1]` completed, row count 2).

Expected: a batch runs each row once (`executemany` reports "the rows run"; `OPS-B4.6.90`).

Observed: the first pass runs rows in order; an unsupported-path error at row k sends the whole batch to the fallback, which starts again at row 0 (`embedded.py:399-410`), so rows 0..k-1 run twice and the row count reports only the second pass.

Consequence: an INSERT batch can write rows twice or fail on a key it wrote itself; an UPDATE batch reapplies changes.

Repair proposal (not implemented): resume the fallback at the row that failed (the model's `fallback_start(failed_at)`), or run the whole batch through one path chosen at prepare time. Governing statement: [adapters.embedded.no_data](../ontology/concepts/adapters.g5.md#adapters.embedded.no_data).

<a id="bug-str-101"></a>
### Flat node property aliases lose one stored value when id and p_id coexist

Severity: Low · Decision: Open

Run: Uplift improvement iteration 1, 2026-11-15

**Suspected** end to end: the real Python writer accepts both keys and the real reader loses one; IRIS persistence and row ordering were substituted. The read docstring promises the node's properties, without reserving the alias keys.

Found by: tracing the sampled bare-node reader into its property assignments, `nodes_edges.py:670-676`; [node_read](models/node_read/NOTES.md) `witness_alias_collision`.

Reproduced by: none on live IRIS; [node_read binding](models/node_read/binding.py) calls the actual `create_node` with `id=stored-id` and `p_id=user-value`, captures both bound properties and feeds both permitted row orders into actual `get_nodes`.

Expected: structural ID/labels stay intact, and every accepted property can be recovered without an unspecified row order choosing which value survives (`get_node` docstring, `nodes_edges.py:563-568`).

Observed: the node's structural `id` remains `n`; property `id` maps to `p_id`, colliding with the caller's own `p_id`. Forward order yields `user-value`; reverse order yields `stored-id`. The same issue applies to `labels`/`p_labels`.

Comparison with inherited findings: F-0206/RC-01 lose values by mixing graphs; F-0813/RC-17 concern value types. Neither has this single-graph key-remapping trigger or loss. No matching alias finding was found in the three registers; this is a builder-discovered candidate, not a held-out result.

Recommendation (not implemented): preserve properties in a separate map, or reserve and validate a documented alias namespace. Owner/default/alternative: [structure.node.read.aliases](../ontology/features/graph-structure.g5.md#structure.node.read.aliases), [q-iter-001](open_questions.md#q-iter-001). No human has chosen the API migration.

<a id="bug-cyp-101"></a>
### Relationship property text with a trailing line break or non-ASCII digits is read back as a number

Severity: Low · Decision: Open

Run: Consolidated uplift 2026-11-14

**Suspected** end to end: the decoder's behavior is observed on the real function; that IRIS returns such text unchanged through `JSON_VALUE` is not observed. Severity is one level below its consequence (a stored string silently changes type and value).

Found by: [witness_as_built_trailing_newline_promoted, witness_as_built_unicode_digit_promoted](results/rel_prop_text/20261115T043200Z-prove/receipt.json) in [rel_prop_text.rs](models/rel_prop_text/rel_prop_text.rs); reading `prop_values.py:90-91` while lifting public case M18.

Reproduced by: none natively; unit level on the pin's real `parse_rel_prop_text` ([binding receipt](results/rel_prop_text/20261115T043204Z-binding/receipt.json): 38 departures from the canonical rule, every one with a line break or U+0662).

Expected: canonical integer or decimal text becomes a number; numeric-looking text that is not canonical stays text (the decoder's docstring, `prop_values.py:154-158`; public case M18).

Observed: `parse_rel_prop_text("12\n")` is `12` and `parse_rel_prop_text("1\u0662")` is `12`: Python's `\d` matches any Unicode decimal digit and `$` matches before a final line break (`prop_values.py:90-91`, `:164-167`).

Consequence: a relationship property stored as such a string comes back from `RETURN r.p` as an integer or float, with the line break dropped.

Repair proposal (not implemented): compile both patterns with `re.ASCII` and end them with `\Z`; the controls `as-built-ascii-digits` and `as-built-without-final-newline-match` show each change removes one half. Governing statement: [query.values.relationship_text](../ontology/features/cypher.g5.md#query.values.relationship_text).

<a id="bug-led-101"></a>
### A property changed before node deletion loses its range-start prior in a lifecycle diff

Severity: Low · Decision: Open

Run: Consolidated uplift 2026-11-14; producer correction and stronger witness 2026-11-15

**Suspected end to end and policy-dependent.** Real named Python readers agree with a source-faithful snapshot fixture; no live IRIS writer ran. The promised net endpoint interpretation still needs its lifecycle application policy made precise by the maintainer.

Found by: original [l2-inverse-order probe](results/unit-probes/20261115T043637Z-l2-inverse-order/receipt.json); corrected and strengthened by [history_diff](models/history_diff/NOTES.md), `theorem_change_then_delete_loses_range_prior` and the actual named-reader binding.

Reproduced by: none on IRIS in this iteration. Python `GraphLedger.diff` and `GraphLedger.reconstruct` execute with SQL, revision IDs and ObjectScript records substituted; [binding receipt](results/history_diff/20261115T065234Z-binding/receipt.json).

Expected: under the net endpoint interpretation of the ledger API, a diff from a later revision back to one where n.k was 1 must retain that original value, or expose that it cannot describe it. Governing owners: [ledger.readers.diff](../ontology/features/ledger.g5.md#ledger.readers.diff), [lifecycle policy](../ontology/features/ledger.g5.md#ledger.readers.diff.order).

Observed: start at revision 1 with k=1; set k=2 at 2; delete n at 3; recreate n at 4 and set k=3 at 5. DeleteNodeRows stores NodeSnapshotJson containing k=2. compute_diff closes that life and drops its earlier attribute prior 1. The reverse range has an existence creation snapshot with k=2 and prop:k from 3 to absent; neither gives the original 1. The new Verus witness derives that snapshot from the raw writes; continuous lives instead preserve the first prior and last value for arbitrary operation sequences.

Consequence: the range cannot be treated as a complete endpoint delta across this lifecycle. Rev==fwd.inverse() still passes and does not establish that stronger behavior.

Repair options (not implemented): retain the first observed prior in the closed life's snapshot; or specify that lifecycle entries describe the deletion moment and do not reconstruct range endpoints. The maintainer owns that choice. q-con-002 also retains the independent ordered-script question.

#### Historical witness correction

The original headline claimed any delete/recreate lost the old property. Its fixture supplied delete_node prior="" and its script applier ignored JSON snapshots. The actual producer stores labels and properties in NodeSnapshotJson (LedgerApply.cls:339-371). For the simple no-intervening-change neighbor, reverse existence.after contains k=1; the former missing-property inference is withdrawn. The original probe/receipt remain unchanged. The stronger change-before-delete witness is corroboration of the same range-prior boundary, not a newly counted bug; stable tie ordering remains as built and its desired application policy remains open.


<a id="F-0101"></a>
### Legacy removal reports objects removed that may still be there

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `reproduced-test`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [01.json](../../experiment/playbook-completion/findings/audit/01.json) (probe `breadth-a-probe-local-0101-0601`; mc `breadth-a-mc-ins_legacy-as-built`; control `breadth-a-control-ins_legacy`; inspected `iris_vector_graph/_engine/legacy.py:666-698`)

Reproduced by: none (reproduced-test)

- Expected: `removed` is whether the object was dropped (specs/262-ivg-owned-sql-schema/data-model.md:50-60).
- Observed at the pin: view and second SqlProc item reported removed although every drop/delete failed
- Source severity S3, confidence high; module 01; governing page here: `install.`.
- Remedy proposed by the playbook arm (not implemented): Set `removed` from _drop's result for views and from the class delete's result for every item of that class; a unit case where DROP VIEW raises.
- Reviewed-design control: `playbook-proofs-d1e` `control_f0101_removed_unchecked` fails where expected in this run ([receipt](results/playbook-proofs-d1e/20261115T035511Z-control_f0101_removed_unchecked/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1e/20261115T035416Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0102"></a>
### Some setup failures are only logged, not put in the reply's warnings

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Medium.

Found by: playbook arm, [01.json](../../experiment/playbook-completion/findings/audit/01.json) (inspected `iris_vector_graph/_engine/schema.py:2506-2511`; inspected `iris_vector_graph/_engine/schema.py:1664-1671`; inspected `iris_vector_graph/_engine/schema.py:2680-2681`; mc `breadth-a-mc-ins_setup-as-built`)

Reproduced by: none (confirmed-source)

- Expected: ADMIN_GUIDE (docs/ADMIN_GUIDE.md:428): `warnings` lists what you must act on, each also logged at WARNING.
- Observed at the pin: A base DDL failure other than already-exists/privilege is a log line (iris_vector_graph/_engine/schema.py:2506-2511); a failed ALTER ... emb VECTOR goes to report['failed'] and a log line (1666-1671); a failed ^KG bootstrap is a log line (2680-2681). Re-read at the pin.
- Source severity S2, confidence high; module 01; governing page here: `install.`.
- Remedy proposed by the playbook arm (not implemented): Append each of these to status['warnings']; a unit test that makes one CREATE TABLE fail with a non-tolerated error.
- Reviewed-design control: `playbook-proofs-d1e` `control_f0102_failure_only_logged` fails where expected in this run ([receipt](results/playbook-proofs-d1e/20261115T035507Z-control_f0102_failure_only_logged/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1e/20261115T035416Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0103"></a>
### The first-use check accepts a namespace with no schema record

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [01.json](../../experiment/playbook-completion/findings/audit/01.json) (live `breadth-a-live-01-install`; mc `breadth-a-mc-ins_setup-as-built`; inspected `iris_vector_graph/schema_name.py:220-235`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-01-install`

- Expected: Spec 262 FR-006a (specs/262-ivg-owned-sql-schema/spec.md:245): refuse when the namespace has no schema record or lacks the 4.6.0 objects; HD-0101 (supported) separates an unreadable record (warn) from a readable mismatch (refuse).
- Observed at the pin: accepted with no record (marker class present)
- Source severity S3, confidence high; module 01; governing page here: `install.`.
- Remedy proposed by the playbook arm (not implemented): Refuse when no record exists whatever the marker says (setup exempt), or amend FR-006a and the ADMIN_GUIDE to say the marker alone is accepted.
- Reviewed-design control: `playbook-proofs-d1e` `control_f0103_marker_admits` fails where expected in this run ([receipt](results/playbook-proofs-d1e/20261115T035505Z-control_f0103_marker_admits/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1e/20261115T035416Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0104"></a>
### Spec 240 says its design was not adopted, but it ships

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [01.json](../../experiment/playbook-completion/findings/audit/01.json) (inspected `specs/240-alt-migration-as-data/spec.md:6`; inspected `iris_vector_graph/migrations/docs_and_edge_vectors.py:53`)

Reproduced by: none (confirmed-source)

- Expected: A spec's status line describes the shipped code.
- Observed at the pin: specs/240-alt-migration-as-data/spec.md:6 'Status: Exploratory (alternative implementation; not adopted)'; iris_vector_graph/migrations/docs_and_edge_vectors.py:53 imports iris_vector_graph.migrations.statements.
- Source severity S3, confidence high; module 01; governing page here: `install.`.
- Remedy proposed by the playbook arm (not implemented): Update the spec status or remove the module.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0105"></a>
### The SQL files under sql/ describe an old schema and put objects outside the IVG Schema

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [01.json](../../experiment/playbook-completion/findings/audit/01.json) (inspected `sql/schema.sql:4-7`; inspected `scripts/deploy_production.py:63-66`)

Reproduced by: none (confirmed-source)

- Expected: Spec 262 FR-001/FR-002 (spec.md:231-233): IVG creates nothing outside the IVG Schema; HD-0103 (assumption): packaged SQL loaded by the legacy deployer is reachable.
- Observed at the pin: sql/schema.sql:4-7 creates Graph_KG.nodes keyed by node_id alone; scripts/deploy_production.py:65 still runs sql/schema.sql and sql/operators_fixed.sql.
- Source severity S3, confidence high; module 01; governing page here: `install.`.
- Remedy proposed by the playbook arm (not implemented): Per HD-0103: bring the legacy deployer to parity or retire it; mark the historical files.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0107"></a>
### Every setup runs an unqualified DROP INDEX

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [01.json](../../experiment/playbook-completion/findings/audit/01.json) (inspected `iris_vector_graph/schema.py:655-658`; live `breadth-a-live-01-install`)

Reproduced by: none (confirmed-source)

- Expected: Spec 262 FR-007 (spec.md:246-248): IVG's SQL names only IVG Schema objects, fully qualified.
- Observed at the pin: observation
- Source severity S3, confidence medium; module 01; governing page here: `install.`.
- Remedy proposed by the playbook arm (not implemented): Qualify it (DROP INDEX idx_props_key_val ON <schema>.rdf_props) or drop the step.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0108"></a>
### The upstream test deploy does not follow setup's skip rules

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [01.json](../../experiment/playbook-completion/findings/audit/01.json) (inspected `tests/conftest.py:215-262`; live `$RUN_DIR/setup/deploy-AUDITA.json`)

Reproduced by: none (confirmed-source)

- Expected: docs/ADMIN_GUIDE.md:353: IRIS Community is supported; initialize_schema skips classes whose %AI dependencies are absent.
- Observed at the pin: tests/conftest.py:215-262 compiles every class under iris_src/src and raises on any failure; setup skipped Graph.KG.MCPService/MCPToolSet/MCPTools in AUDITA ($RUN_DIR/setup/deploy-AUDITA.json).
- Source severity S4, confidence high; module 01; governing page here: `install.`.
- Remedy proposed by the playbook arm (not implemented): Have the fixture call initialize_schema() or apply select_classes; a CI job on Community.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0109"></a>
### The 4.0.0 upgrade does not follow the namespace's schema

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [01.json](../../experiment/playbook-completion/findings/audit/01.json) (inspected `iris_vector_graph/migrations/upgrade.py:55-59`; inspected `iris_vector_graph/migrations/upgrade.py:138-141`)

Reproduced by: none (confirmed-source)

- Expected: ADR-0016 (docs/adr/0016-one-ivg-schema-per-namespace.md:10-12): the schema name chosen at install is followed by everything.
- Observed at the pin: iris_vector_graph/migrations/upgrade.py:58 DEFAULT_SCHEMA = 'Graph_KG' and :140 schema default; ^IVG.Deploy('schema') is never read.
- Source severity S3, confidence high; module 01; governing page here: `install.`.
- Remedy proposed by the playbook arm (not implemented): Read the record (refuse a mismatch) or document Graph_KG-only.
- Reviewed-design control: `playbook-proofs-d1e` `control_f0109_upgrade_default_schema` fails where expected in this run ([receipt](results/playbook-proofs-d1e/20261115T035509Z-control_f0109_upgrade_default_schema/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1e/20261115T035416Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0110"></a>
### ADR-0016 lags the shipped design

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [01.json](../../experiment/playbook-completion/findings/audit/01.json) (inspected `docs/adr/0016-one-ivg-schema-per-namespace.md:5`; inspected `docs/adr/0016-one-ivg-schema-per-namespace.md:26`; inspected `iris_vector_graph/_engine/admin.py:378`)

Reproduced by: none (confirmed-source)

- Expected: A decision record states the shipped mechanism and API names.
- Observed at the pin: docs/adr/0016-one-ivg-schema-per-namespace.md:5 'implementation pending: spec 262'; :26 names remove_legacy_sql_objects while the method is remove_legacy_objects (iris_vector_graph/_engine/admin.py:378).
- Source severity S3, confidence high; module 01; governing page here: `install.`.
- Remedy proposed by the playbook arm (not implemented): Amend the ADR's status and consequences.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0203"></a>
### The Python name check refuses fewer control characters than the server check

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [02.json](../../experiment/playbook-completion/findings/audit/02.json) (live `breadth-a-live-02-identity`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-02-identity`

- Expected: CHANGELOG.md:4618-4620: the Python mirror exists to refuse what the server refuses, before the round trip.
- Observed at the pin: Python accepts, server refuses
- Source severity S4, confidence high; module 02; governing page here: `graph. / structure.`.
- Remedy proposed by the playbook arm (not implemented): Refuse unicodedata category Cc (0-31, 127-159) in _validate.validate_graph_name.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0205"></a>
### Direct edge writes, the ledger and Bolt do not track parallel edges, and the user docs do not say so

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Medium.

Found by: playbook arm, [02.json](../../experiment/playbook-completion/findings/audit/02.json) (inspected `iris_vector_graph/bolt_server.py:770`; inspected `iris_src/src/Graph/KG/LedgerApply.cls:144-157`)

Reproduced by: none (confirmed-source)

- Expected: Spec 234 FR-007/FR-012/FR-013 (edge_id identity, ambiguous_tuple refusal); its status line says US4 not done.
- Observed at the pin: Bolt gives a relationship id hash(f'{s}-{type}-{o}') (iris_vector_graph/bolt_server.py:770); LedgerApply.FindEdge takes the first row of the triple (iris_src/src/Graph/KG/LedgerApply.cls:144-157). Re-read at the pin.
- Source severity S2, confidence medium; module 02; governing page here: `graph. / structure.`.
- Remedy proposed by the playbook arm (not implemented): Implement FR-007/012/013 or document each limit.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0207"></a>
### Turning the mode off races a write that adds a parallel edge

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `reproduced-model`, not a native reproduction; severity is one level below the mapped Medium.

Found by: playbook arm, [02.json](../../experiment/playbook-completion/findings/audit/02.json) (mc `breadth-a-mc-gid_mode-as-built`; mc `breadth-a-mc-gid_mode-reviewed`; control `breadth-a-control-gid_mode`; inspected `iris_src/src/Graph/KG/GraphMode.cls:26-61`)

Reproduced by: none (reproduced-model)

- Expected: Spec 234 FR-002 (the refusal exists to keep a mode-off graph single-edge).
- Observed at the pin: GraphMode.Set counts parallel triples with one SQL query then kills the setting, no lock, no transaction (iris_src/src/Graph/KG/GraphMode.cls:26-45).
- Source severity S2, confidence high; module 02; governing page here: `graph. / structure.`.
- Remedy proposed by the playbook arm (not implemented): Hold a lock the multigraph writers also take across the count and the kill.
- Reviewed-design control: `playbook-proofs-d1e` `control_f0207_set_off_unlocked` fails where expected in this run ([receipt](results/playbook-proofs-d1e/20261115T035520Z-control_f0207_set_off_unlocked/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1e/20261115T035416Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0209"></a>
### An all-graphs walk can miss graphs

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [02.json](../../experiment/playbook-completion/findings/audit/02.json) (inspected `iris_vector_graph/_engine/query.py:2408-2420`)

Reproduced by: none (confirmed-source)

- Expected: An all-graphs read is the union over every graph (CONTEXT.md:38-43).
- Observed at the pin: _edge_graphs stops after 10,000 graphs and answers [] on any error (iris_vector_graph/_engine/query.py:2408-2420).
- Source severity S4, confidence high; module 02; governing page here: `graph. / structure.`.
- Remedy proposed by the playbook arm (not implemented): List without a cap and raise on failure.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0301"></a>
### The bulk loader writes while ledger strict mode is on

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [03.json](../../experiment/playbook-completion/findings/audit/03.json) (live `breadth-a-live-ledger`; inspected `iris_vector_graph/bulk_loader.py:252-272`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-ledger`

- Expected: HD-0301 (supported): spec 213's API contract excludes the bulk loader and raw SQL from strict mode; the USER_GUIDE (docs/USER_GUIDE.md:1107-1121) says strict refuses create_node, create_edge 'and the other methods'.
- Observed at the pin: loader wrote under strict mode (contract exception; docs say otherwise)
- Source severity S3, confidence high; module 03; governing page here: `structure. / install.bulk_load`.
- Remedy proposed by the playbook arm (not implemented): State the exclusion in the USER_GUIDE next to strict mode (the contract is supported as is).
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0302"></a>
### Strict mode reaches another engine only after its five-second cache expires

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [03.json](../../experiment/playbook-completion/findings/audit/03.json) (live `breadth-a-live-ledger`; tested `tests/unit/test_ledger_guard.py::test_cache_honours_ttl_and_refresh`; inspected `iris_vector_graph/ledger/guard.py:20-59`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-ledger`

- Expected: USER_GUIDE.md:1107-1121 states refusal without a window; HD-1103 (supported): strict mode is a client-side guard whose cache behaviour must be inventoried.
- Observed at the pin: another engine wrote within its cache window
- Source severity S3, confidence high; module 03; governing page here: `structure. / install.bulk_load`.
- Remedy proposed by the playbook arm (not implemented): Document the window and the fail-open rule next to set_strict, or check on the server.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0306"></a>
### create_node answers False for a write IRIS refuses as invalid

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [03.json](../../experiment/playbook-completion/findings/audit/03.json) (live `breadth-a-live-03-writes`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-03-writes`

- Expected: create_node docstring: False means the node already exists; 4.6.0 R203: a refusal is not 'already there'.
- Observed at the pin: answered False (exists) with nothing written
- Source severity S4, confidence high; module 03; governing page here: `structure. / install.bulk_load`.
- Remedy proposed by the playbook arm (not implemented): Drop the 'validation failed' match or width-check the graph name.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0309"></a>
### The bulk loader rebuilds the indexes of Graph_KG whatever schema it loaded

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Medium.

Found by: playbook arm, [03.json](../../experiment/playbook-completion/findings/audit/03.json) (inspected `iris_vector_graph/bulk_loader.py:493-496`)

Reproduced by: none (confirmed-source)

- Expected: ADR-0016 / CONTEXT.md:20-24: a namespace's IVG schema may be other than Graph_KG.
- Observed at the pin: rebuild_all_indices calls %BuildIndices on the fixed classes Graph.KG.rdfedges/rdflabels/rdfprops/nodes (iris_vector_graph/bulk_loader.py:495).
- Source severity S2, confidence high; module 03; governing page here: `structure. / install.bulk_load`.
- Remedy proposed by the playbook arm (not implemented): Derive the class names from the schema.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0401"></a>
### A killed source generation can let an in-flight reader store a wrong out-degree

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `intent-undecided`, not a native reproduction; severity is one level below the mapped Medium.

**Policy-dependent:** the playbook arm classed the expected behavior as undecided intent.

Found by: playbook arm, [04.json](../../experiment/playbook-completion/findings/audit/04.json) (mc `breadth-a-mc-adj_degree-as-built`; mc `breadth-a-mc-adj_degree-reviewed`; control `breadth-a-control-adj_degree`; inspected `iris_src/src/Graph/KG/Adj.cls:51-90`)

Reproduced by: none (intent-undecided)

- Expected: ADJ-I5.9 / ADJ-I5.9.1; HD-0401 (assumption): invalidation never makes an old degree-cache value valid again.
- Observed at the pin: Adj.Degree's four steps (iris_src/src/Graph/KG/Adj.cls:51-90) against RemoveSource/RemoveGraph/RemoveAll killing ^KG('gen') (Adjacency.cls:376-377, 437-438, 461-462) and a rolled-back erase.
- Source severity S2, confidence high; module 04; governing page here: `structure.`.
- Remedy proposed by the playbook arm (not implemented): Per HD-0401: step the generation (or a graph epoch) and never kill it; the model also needs the step before the write (see F-C0401).
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0404"></a>
### Snapshot restore writes the adjacency index outside the one writer where the row hook is not declared

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [04.json](../../experiment/playbook-completion/findings/audit/04.json) (inspected `iris_vector_graph/_engine/snapshot.py:1656-1692`)

Reproduced by: none (confirmed-source)

- Expected: ADR-0011 (one writer); ADR-0008:46 and spec 252 FR-016 (ImportGlobals restores rows only).
- Observed at the pin: _import_global_from_ndjson sets ^KG out/in over the Native API when the namespace is not indexed (iris_vector_graph/_engine/snapshot.py:1656-1692).
- Source severity S3, confidence high; module 04; governing page here: `structure.`.
- Remedy proposed by the playbook arm (not implemented): Route the restore through Graph.KG.Adjacency or rebuild from rows; extend the single-writer guard to Python.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0405"></a>
### Some weight refreshes do not move the graph-version token

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [04.json](../../experiment/playbook-completion/findings/audit/04.json) (live `breadth-a-live-04-adjacency`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-04-adjacency`

- Expected: CONTEXT.md:116-119: every write path able to change an algorithm's answer moves the token.
- Observed at the pin: weight changed 1.0 -> 5.0 with token and generation unchanged
- Source severity S4, confidence high; module 04; governing page here: `structure.`.
- Remedy proposed by the playbook arm (not implemented): Step the token whenever a stored weight changes.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0407"></a>
### Reweight takes no writer lock and moves no generation, against ADR-0012 and spec 252 FR-004

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [04.json](../../experiment/playbook-completion/findings/audit/04.json) (live `breadth-a-live-04-adjacency`; tested `tests/e2e/test_degree_cache_live.py::test_reweight_does_not_move_the_generation`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-04-adjacency`

- Expected: ADR-0012:31 and spec 252 FR-004 as written.
- Observed at the pin: weight changed, generation unchanged (docs over-state the rule)
- Source severity S3, confidence high; module 04; governing page here: `structure.`.
- Remedy proposed by the playbook arm (not implemented): Amend ADR-0012 and FR-004 to 'every write that changes the set of out entries'.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0408"></a>
### Comments and docs still describe adjacency behaviour that changed

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [04.json](../../experiment/playbook-completion/findings/audit/04.json) (inspected `iris_src/src/Graph/KG/EdgeScan.cls:149`; inspected `iris_vector_graph/_engine/admin.py:854-861`)

Reproduced by: none (confirmed-source)

- Expected: Comments and ADRs describe the shipped behaviour.
- Observed at the pin: EdgeScan.cls:149 'graph="" = default graph'; admin.py:854-861 drop_graph text; ADR-0010 line 5 'implementation pending'.
- Source severity S4, confidence high; module 04; governing page here: `structure.`.
- Remedy proposed by the playbook arm (not implemented): Correct the four texts.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0503"></a>
### A temporal write can create node rows that the ledger never records

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `intent-undecided`, not a native reproduction; severity is one level below the mapped Medium.

**Policy-dependent:** the playbook arm classed the expected behavior as undecided intent.

Found by: playbook arm, [05.json](../../experiment/playbook-completion/findings/audit/05.json) (live `breadth-a-live-ledger`; inspected `iris_src/src/Graph/KG/Adjacency.cls:575-603`)

Reproduced by: none (intent-undecided)

- Expected: INV-replay / RPL-B3: with every write made through the ledger, replay equals the store; HD-0501 (assumption): implicitly created endpoints are real effects to record or give derived provenance.
- Observed at the pin: verify diverges on node rows the changeset's temporal op created
- Source severity S2, confidence high; module 05; governing page here: `temporal.`.
- Remedy proposed by the playbook arm (not implemented): Per HD-0501: record the endpoint rows a governed temporal op creates, or mark them derived and exclude them from verify.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0506"></a>
### Without the adjacency index, the Python mirror writes an unmarked row for any predicate

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Medium.

Found by: playbook arm, [05.json](../../experiment/playbook-completion/findings/audit/05.json) (inspected `iris_vector_graph/_engine/temporal.py:309-331`)

Reproduced by: none (confirmed-source)

- Expected: ADR-0015 (an opted-out predicate writes nothing else); ADR-0009 (the asserted row is marked).
- Observed at the pin: create_edge_temporal / bulk_create_edges_temporal insert an unmarked rdf_edges row when not _adjacency_indexed (iris_vector_graph/_engine/temporal.py:309-331, 453-475).
- Source severity S2, confidence high; module 05; governing page here: `temporal.`.
- Remedy proposed by the playbook arm (not implemented): Write the marker and honour the opt-out registry, or drop the mirror.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0508"></a>
### find_burst_nodes accepts a predicate and ignores it

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [05.json](../../experiment/playbook-completion/findings/audit/05.json) (live `breadth-a-live-05-temporal`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-05-temporal`

- Expected: Args docstring: 'predicate: Filter to edges with this predicate' (temporal.py find_burst_nodes).
- Observed at the pin: hub reported as a burst of predicate B with only A edges
- Source severity S3, confidence high; module 05; governing page here: `temporal.`.
- Remedy proposed by the playbook arm (not implemented): Remove the argument or count per predicate; make the docstring agree (its first paragraph now says it filters nothing).
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0509"></a>
### InternLabelSet's canonical form is not valid JSON for some inputs

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [05.json](../../experiment/playbook-completion/findings/audit/05.json) (live `breadth-a-live-05-temporal`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-05-temporal`

- Expected: Spec 204 FR-012: the canonical form is JSON.
- Observed at the pin: resolved text is not JSON
- Source severity S3, confidence high; module 05; governing page here: `temporal.`.
- Remedy proposed by the playbook arm (not implemented): Build the form with JSON escaping; catch the parse error.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0511"></a>
### A changeset's insert-mode temporal op is recorded even when it collides

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [05.json](../../experiment/playbook-completion/findings/audit/05.json) (live `breadth-a-live-ledger`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-ledger`

- Expected: Changeset.create_temporal_edge docstring: insert fails if the key exists (iris_vector_graph/ledger/changeset.py:334-335).
- Observed at the pin: collision committed and recorded; weight unchanged
- Source severity S3, confidence high; module 05; governing page here: `temporal.`.
- Remedy proposed by the playbook arm (not implemented): Return the collision from WriteStores to LedgerApply; refuse or skip the record (HD-0502).
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0512"></a>
### The batch field that suppresses the reverse index is not the one spec 204 names

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [05.json](../../experiment/playbook-completion/findings/audit/05.json) (live `breadth-a-live-05-temporal`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-05-temporal`

- Expected: Spec 204 FR-009 (specs/204-temporal-index-gaps/spec.md:185): suppress_reverse.
- Observed at the pin: suppress_reverse ignored; reverse index written
- Source severity S3, confidence high; module 05; governing page here: `temporal.`.
- Remedy proposed by the playbook arm (not implemented): Accept both names or amend the spec.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0513"></a>
### Temporal writes validate their input on one path only

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [05.json](../../experiment/playbook-completion/findings/audit/05.json) (live `breadth-a-live-05-purge`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-05-purge`

- Expected: TemporalEdgeInput (iris_vector_graph/_validate.py:207-227): timestamp >= 0, weight >= 0.
- Observed at the pin: refused with a timestamp; stored without one and on the batch path
- Source severity S3, confidence high; module 05; governing page here: `temporal.`.
- Remedy proposed by the playbook arm (not implemented): Validate every edge on every path.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0514"></a>
### The Python structural-row migration cannot read a large graph

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Medium.

Found by: playbook arm, [05.json](../../experiment/playbook-completion/findings/audit/05.json) (inspected `iris_vector_graph/migrations/temporal_structural_rows.py:55-63`; inspected `iris_vector_graph/_engine/temporal.py:500-505`)

Reproduced by: none (confirmed-source)

- Expected: The migration backfills every temporal triple of a graph.
- Observed at the pin: _temporal_triples reads with get_edges_in_window(start=0, end=_ALL_TIME_END) (iris_vector_graph/migrations/temporal_structural_rows.py:55-63), whose docstring states a ~35 k-edge cap that raises TemporalWindowError (iris_vector_graph/_engine/temporal.py:500-505).
- Source severity S2, confidence high; module 05; governing page here: `temporal.`.
- Remedy proposed by the playbook arm (not implemented): Read with iter_edges_in_window, or call backfill_temporal_structural_rows.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0602"></a>
### Vectors from one model can be stored under another model's identity

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Medium.

Found by: playbook arm, [06.json](../../experiment/playbook-completion/findings/audit/06.json) (inspected `iris_vector_graph/_engine/embeddings.py:157-197`; inspected `iris_vector_graph/_engine/embeddings.py:2033-2049`; inspected `iris_vector_graph/_engine/schema.py:1013-1018`)

Reproduced by: none (confirmed-source)

- Expected: ADR-0006: a vector's identity is the model that made it.
- Observed at the pin: embed_text falls back to a Python embedder when the IRIS EMBEDDING() call fails (iris_vector_graph/_engine/embeddings.py:157-197); _encode_batch never calls IRIS EMBEDDING() (2033-2049); the offered identity comes from embedding_config first (iris_vector_graph/_engine/schema.py:1013-1018).
- Source severity S2, confidence high; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Offer the identity of the model that produced the vector, or refuse cross-model fallback.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0603"></a>
### The IRIS queue worker writes vectors with no identity check, and ignores the model for the default graph

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Medium.

Found by: playbook arm, [06.json](../../experiment/playbook-completion/findings/audit/06.json) (inspected `iris_src/src/Graph/KG/EmbedQueue.cls:258-338`)

Reproduced by: none (confirmed-source)

- Expected: ADR-0006 / spec 226: every seam that writes vectors consults the registry.
- Observed at the pin: ProcessBatch targets Graph_KG.kg_NodeEmbeddings for every default-graph entry whatever its config (iris_src/src/Graph/KG/EmbedQueue.cls:280-286) and reads no registry row.
- Source severity S2, confidence high; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Route default-graph entries through the registry and compare the entry's model and width before writing.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0605"></a>
### enqueue_for_embedding checks the default table's row, not the target graph's route

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [06.json](../../experiment/playbook-completion/findings/audit/06.json) (inspected `iris_vector_graph/_engine/embeddings.py:1803-1850`)

Reproduced by: none (confirmed-source)

- Expected: Spec 227: kg_NodeEmbeddings' registry row is the default pair's row and nobody else's (embeddings.py:1992-1998).
- Observed at the pin: enqueue_for_embedding always enforces against ('kg_NodeEmbeddings', graph '') (iris_vector_graph/_engine/embeddings.py:1839-1842 at the pin's numbering: the enforce call before _ensure_queue_route).
- Source severity S3, confidence high; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Resolve the target route (graph, config) and enforce against its row.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0609"></a>
### The fused search may read an IVF index built for another graph

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Medium.

Found by: playbook arm, [06.json](../../experiment/playbook-completion/findings/audit/06.json) (inspected `iris_vector_graph/_engine/vector.py:194-225`)

Reproduced by: none (confirmed-source)

- Expected: FR-013 (a scoped lookup never widens); search_nodes_by_vector refuses the same case (vector.py:783-790).
- Observed at the pin: _fusion_leg_index falls back to an index whose graph is unknown, with a WARNING (iris_vector_graph/_engine/vector.py:208-225).
- Source severity S2, confidence high; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Refuse the IVF leg for an index of unknown or other graph; persist the graph with the index.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0611"></a>
### Edge vectors the upgrade places in a named graph are not found by edge search, and the edge and text quarantines have no API

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Medium.

Found by: playbook arm, [06.json](../../experiment/playbook-completion/findings/audit/06.json) (inspected `iris_vector_graph/migrations/statements.py:203-240`; inspected `iris_vector_graph/_engine/schema.py:1305-1315`)

Reproduced by: none (confirmed-source)

- Expected: CONTEXT.md:159-161 (an operator places each quarantined vector); edge search resolves (graph, model, edge) routes.
- Observed at the pin: The edge step inserts into kg_EdgeEmbeddings with the edge's graph_id (iris_vector_graph/migrations/statements.py:203-240) and adopts kg_EdgeEmbeddings for graph '' only (iris_vector_graph/_engine/schema.py:1312-1315).
- Source severity S2, confidence high; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Route named-graph edge rows into kg_eemb_ tables or register kg_EdgeEmbeddings per graph; add list/place calls.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0612"></a>
### The edge and table searches skip rules the node search keeps

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [06.json](../../experiment/playbook-completion/findings/audit/06.json) (inspected `iris_vector_graph/_engine/vector.py:366-391`; live `rx-live-06`)

Reproduced by: none (confirmed-source)

- Expected: ADR-0005 forbids the lengthed TO_VECTOR form for a query vector; 4.6.0 R142 uses the route's dtype.
- Observed at the pin: edge_vector_search builds TO_VECTOR(?, engine dtype, comma-counted dim) and answers [] for errors containing '-30', 'not found' or 'empty' (iris_vector_graph/_engine/vector.py:366-391).
- Source severity S3, confidence high; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Use the unlengthed form and the route's dtype; extend the routed-name refusal to kg_eemb_.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0613"></a>
### VectorOptimizer.migrate_to_optimized writes vectors without the identity check and reports success with failures

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [06.json](../../experiment/playbook-completion/findings/audit/06.json) (inspected `iris_vector_graph/vector_utils.py:151-280`)

Reproduced by: none (confirmed-source)

- Expected: ADR-0006: every seam that writes vectors consults the registry.
- Observed at the pin: migrate_to_optimized inserts row by row with no enforce_embedding_identity and no transaction and returns success: True with a failed count (iris_vector_graph/vector_utils.py:151-280).
- Source severity S3, confidence high; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Enforce the identity, run as one transaction or report failure when failed > 0.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0614"></a>
### embed_nodes and embed_edges count an identity refusal as an error and return normally

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [06.json](../../experiment/playbook-completion/findings/audit/06.json) (live `breadth-a-live-06-embed`; inspected `iris_vector_graph/_engine/embeddings.py:1462-1480`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `breadth-a-live-06-embed`

- Expected: ADR-0006: spec 226 requires it to raise.
- Observed at the pin: identity conflict counted as errors; returned normally
- Source severity S3, confidence high; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Re-raise EmbeddingIdentityConflict.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0617"></a>
### The glossary and user guide say a second model's write is refused; the code routes it to its own table

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [06.json](../../experiment/playbook-completion/findings/audit/06.json) (inspected `CONTEXT.md:154-157`; inspected `iris_vector_graph/_engine/embeddings.py:755-792`; tested `tests/integration/test_embedding_identity_refusal_e2e.py::test_same_width_different_model_gets_its_own_route`)

Reproduced by: none (confirmed-source)

- Expected: CONTEXT.md:154-157 and docs/USER_GUIDE.md:958-960.
- Observed at the pin: A write naming another model gets its own route (iris_vector_graph/_engine/embeddings.py:755-792); the upstream test test_same_width_different_model_gets_its_own_route asserts it.
- Source severity S3, confidence high; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Update CONTEXT.md and the USER_GUIDE.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0708"></a>
### Spec 044 states behaviour the code no longer has

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `reproduced-test`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [07.json](../../experiment/playbook-completion/findings/audit/07.json) (run `b-07-unit`; inspected `specs/044-bm25-index/spec.md:78-158`; inspected `iris_src/src/Graph/KG/BM25Index.cls:6-22`; inspected `iris_vector_graph/_engine/vector.py:917-1054`)

Reproduced by: none (reproduced-test)

- Expected: specs/044-bm25-index/spec.md (Status Draft): FR-002 (:148) stored avgdl/idf; FR-010 (:156) Info shape; US2 sc.4 (:78) empty query returns []; US4 sc.2 (:109) warning on a dropped index; Edge Cases (:274) sanitize_identifier; FR-012 (:158) kg_TXT falls back to BM25 'default'.
- Observed at the pin: Run (b-07-unit): tests/unit/test_bm25_index.py::TestBM25IndexUnit::test_bm25_search_empty_query_raises_validation_error passes (bm25_search raises on an empty query). Source: schema 2 stores no idf/avgdl (BM25Index.cls:6-22); kg_TXT has no BM25 fallback (vector.py:917-1054); names are not sanitized (F-0706 live).
- Source severity S3, confidence high; module 07; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Amend spec 044 to the 4.2/4.6.5 behaviour or implement what it keeps (HD-0703 keeps FR-012 for the matching graph); rename TestBM25IndexE2E::test_kgtxt_returns_bm25_scores_not_like_scores.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0710"></a>
### Weighted fusion's default weights go to legs by position, not by kind

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `reproduced-test`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [07.json](../../experiment/playbook-completion/findings/audit/07.json) (probe `b-07-probe-fusion`; inspected `iris_vector_graph/fusion.py:214-219`)

Reproduced by: none (reproduced-test)

- Expected: iris_vector_graph/fusion.py:216 comment: vector=0.5, text=0.3, graph=0.2.
- Observed at the pin: Probe (b-07-probe-fusion): a text-only weighted call with graph expansion scores text 0.625 and graph 0.375 (weights 0.5/0.3 normalized) where the comment's 0.3/0.2 give 0.6/0.4.
- Source severity S4, confidence high; module 07; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Map default weights from search_modes.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0804"></a>
### Lexer errors are Python SyntaxError, not CypherParseError

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0804`; inspected `iris_vector_graph/cypher/lexer.py:229-232`; inspected `iris_vector_graph/cypher/lexer.py:267-270`; live `b-08-live-f0804-rerun`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0804`, `b-08-live-f0804-rerun`

- Expected: USER_GUIDE.md:313: a query that does not parse raises CypherParseError (CYP-X12.1).
- Observed at the pin: Live: an unknown character (§), an unterminated string and a stray ';' each raised SyntaxError, none an instance of CypherParseError (parser.py:18 derives from Exception).
- Source severity S3, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Raise CypherParseError (or a subclass) from the lexer, or document both types; keep a distinct type for parses-but-invalid.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0806"></a>
### A stepped write's error message says earlier steps are kept

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0806`; mc `m08-txn-as-built-msg`; inspected `iris_vector_graph/_engine/query.py:1692-1705`; live `b-08-live-f0806-rerun`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0806`, `b-08-live-f0806-rerun`

- Expected: Since 4.6.4 a write query is one write_txn rolled back on any failure (query.py:1946-1962; USER_GUIDE.md:266-271): nothing is written.
- Observed at the pin: Live: `CREATE (:B08Y {id:'b08_short'}) WITH * MATCH (b:B08K {k: 1/0}) CREATE (:B08Z)` (count-only CREATE pipeline) raised GraphWriteError 'execute_cypher failed (SQLCODE -149), the rows of the steps before it are written' while node b08_short was rolled back (0 rows). Per-row MERGE/CREATE failing in a write step say 'nothing written' (correct). Model m08-txn-as-built-msg violates; reviewed passes.
- Source severity S3, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Drop the 'written' text (say nothing was written) and unit-test the message.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0807"></a>
### Some refused writes raise ValueError or SyntaxError, not GraphWriteError

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0807`; inspected `iris_vector_graph/_engine/query.py:1980-1985`; inspected `iris_vector_graph/cypher/translator.py:11513-11519`; live `b-08-live-f0807-rerun`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0807`, `b-08-live-f0807-rerun`

- Expected: USER_GUIDE.md:317-318 and the execute_cypher docstring (query.py:1756-1758): a write IRIS or IVG refuses raises GraphWriteError.
- Observed at the pin: Live: count-only CREATE over 103,823 rows -> ValueError; MERGE on null -> ValueError; MERGE ON CREATE SET n = {...} -> SyntaxError; SET a.v = r.w + 1 -> SyntaxError. Nothing written in any.
- Source severity S3, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Wrap translator/engine refusals of writes in GraphWriteError keeping the cause, or list the other types in USER_GUIDE Errors.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0808"></a>
### FOREACH over a parameter list does not run per item

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0808`; inspected `iris_vector_graph/cypher/translator.py:3949-3967`; inspected `iris_vector_graph/cypher/translator.py:7262-7307`; live `b-08-live-f0808-rerun`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0808`, `b-08-live-f0808-rerun`

- Expected: openCypher runs the FOREACH body once per element.
- Observed at the pin: Live: `FOREACH (x IN $list | CREATE (:B08F {v: x}))` with list [1,2,3] raised SyntaxError 'Undefined variable: x' and wrote nothing; the literal-list form created 3 nodes.
- Source severity S3, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Bind a parameter source before translation (as UNWIND does), or refuse it with a documented error; live test.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0809"></a>
### MERGE ON CREATE SET / ON MATCH SET value shapes fail (documented, 4.7.1)

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0809`; inspected `iris_vector_graph/cypher/translator.py:12062-12451`; live `b-08-live-f0809-rerun`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0809`, `b-08-live-f0809-rerun`

- Expected: KNOWN_ISSUES.md:131-142 (openCypher semantics).
- Observed at the pin: Live: ON MATCH SET n.s = size(n.id) -> GraphWriteError SQLCODE -23; pattern MERGE ON CREATE SET a.c = a.count + 1 -> GraphWriteError <ARGUMENT ERROR>; ON MATCH SET n.v = 1/0 on a node the MERGE creates -> GraphWriteError -149, node not created. All three as documented.
- Source severity S3, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): The planned 4.7.1 fix with a live test per shape.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0811"></a>
### RETURN r.p of an edge number past 64 bits answers an integer

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0811`; inspected `iris_vector_graph/prop_values.py:141-168`; run `b-08-run-unit`; live `b-08-live-f0811-rerun`; run `b-08-run-unit-rerun`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0811`, `b-08-live-f0811-rerun`

- Expected: openCypher answers the float 1e+20 (KNOWN_ISSUES.md:163-170).
- Observed at the pin: Live: after SET r.p = 1e20, RETURN r.p answered int 100000000000000000000.
- Source severity S3, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Cap the relationship reader at 64 bits as the node reader is; unit test parse_rel_prop_text.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0812"></a>
### A whole-number result of SET arithmetic reads back as an integer

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0812`; inspected `iris_vector_graph/cypher/translator.py:13784-13887`; live `b-08-live-f0812-rerun`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0812`, `b-08-live-f0812-rerun`

- Expected: openCypher: 2 * 1.5 is the float 3.0 (KNOWN_ISSUES.md:154-161).
- Observed at the pin: Live: SET n.w = n.w * 1.5 over w: 2; RETURN n.w answered int 3.
- Source severity S3, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Keep the float type through the SET writer; live test.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0817"></a>
### An unknown db, dbms or apoc procedure answers no rows

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0817`; inspected `iris_vector_graph/engine.py:1716-1720`; live `b-08-live-f0817-rerun`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0817`, `b-08-live-f0817-rerun`

- Expected: CYP-X10.2: an unknown procedure name is refused, with the list of known names.
- Observed at the pin: Live: CALL db.b08nothing(), apoc.b08nothing(), dbms.b08nothing() each answered column 'value' with no rows and no error; ivg.b08nothing raised ValueError listing known names; gds.b08nothing.stream answered an 'error' column result.
- Source severity S3, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Raise for every unknown name (ProcedureNotFound) with a unit test.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0821"></a>
### The published TCK figures cannot be tied to this repository

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (probe `b-08-probe-tck-provenance`; inspected `docs/dev/TCK.md:172-238`; probe `b-08-probe-tck-provenance-rerun`)

Reproduced by: none (confirmed-source)

- Expected: Evidence claims are reproducible at a named commit (playbook §3.7).
- Observed at the pin: git: 9ca0edca, 99514e62, 2406c7dc, 500ecd40, da666988 (cited by docs/dev/TCK.md:172-201) are not objects in this repository; 0e69c125, f7a8c581 and 99ca2807 are ancestors of the pin. No TCK run here (not in scope; IRIS-backed).
- Source severity S3, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): A full typed TCK run at the pin on Community and enterprise, multigraph on and off, keeping RUN_INFO and results.tsv.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0822"></a>
### CREATE or MERGE after UNWIND $p AS e WITH e fails

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0822`; inspected `iris_vector_graph/cypher/translator.py:7044-7087`; live `b-08-live-f0822-rerun`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0822`, `b-08-live-f0822-rerun`

- Expected: openCypher: one node per element (KNOWN_ISSUES.md:585-596).
- Observed at the pin: Live: `UNWIND $p AS e WITH e CREATE (:B08U {id: e.id})` raised GraphWriteError '<PARAMETER ERROR> Invalid number of parameters' (neither the -119 KNOWN_ISSUES/CHANGELOG name nor the -23 the unit test names); UNWIND without WITH created 2 nodes.
- Source severity S3, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): A fix with a live test, and one error in docs and tests.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0824"></a>
### Two slashes inside an AQL string start a comment

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-f0824`; inspected `iris_vector_graph/cypher/aql/lexer.py:46-63`; live `b-08-live-f0824-rerun`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-f0824`, `b-08-live-f0824-rerun`

- Expected: A string literal holding // is a string.
- Observed at the pin: translate_aql (the pin's code, run in the live session) on FILTER v.url == 'http://x' raised AQLParseError 'Expected RETURN'; 'x' translated fine. It also cut a back-quoted collection name containing // (F-0814 probing).
- Source severity S3, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Strip comments in the tokenizer outside strings; unit test.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0825"></a>
### An expression the translator does not handle becomes SQL NULL

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (inspected `iris_vector_graph/cypher/translator.py:29676-29756`)

Reproduced by: none (confirmed-source)

- Expected: A query the product cannot translate is refused (CYP-X12.x), never answered with a silent null.
- Observed at the pin: translate_expression falls through to `return "NULL"` (translator.py:29756). Probing six pattern-expression shapes in memory (RETURN (a)-->(), size(pattern), WITH pattern, pattern comprehension, named path, exists(pattern)) found no input that reaches it: the parser refuses pattern expressions in value position and the others translate. Reachability not established.
- Source severity S4, confidence low; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Raise a translation error at the fall-through and run the TCK and unit suites to find any shape that relied on it.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0903"></a>
### The namespace compile mode is not checked: any value but job or off acts as sync

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [09.json](../../experiment/playbook-completion/findings/audit/09.json) (live `b-09-f0903-mode`; mc `m09-mode-as-built`; mc `m09-mode-reviewed`; mc `m09-mode-control-unknown-job`; inspected `iris_src/src/Graph/KG/Cypher/Gen.cls:41-44`; inspected `iris_src/src/Graph/KG/Cypher/Gen.cls:61-105`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-09-f0903-mode`

- Expected: NAT-X12 (a namespace mode other than job, sync or off is refused, never taken as sync); docs/ADMIN_GUIDE.md:774-779 tells operators to Set ^IVG.CypherGen("mode") = "off" under change control.
- Observed at the pin: Live (b-09-f0903-mode): namespace value -> (Effective, entry status right after the read returned, IVGC classes, read ms): {"off": {"effective": "off", "entry_status": [], "classes": [], "ms": 2.8}, "OFF": {"effective": "OFF", "entry_status": ["ok"], "classes": ["IVGC.P3348648270"], "ms": 46.6}, "none": {"effective": "none", "entry_status": ["ok"], "classes": ["IVGC.P3348648270"], "ms": 43.9}, "job": {"effective": "job", "entry_status": ["ok"], "classes": ["IVGC.P3348648270"], "ms": 7.2}}. Model m09-mode-as-built (violation of NAT-X12); reviewed (unknown taken as off) passes; control caught.
- Source severity S3, confidence high; module 09; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Effective() (or For) treats an unknown namespace value as off and logs it once; a test that sets "OFF" and asserts no entry is written.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0905"></a>
### A deploy's drop does not wait for builds already running

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [09.json](../../experiment/playbook-completion/findings/audit/09.json) (live `b-09-f0905-dropall-race`; mc `m09-planc-as-built-drop-shape`; mc `m09-planc-as-built-drop-I5`; mc `m09-planc-as-built-drop-progress`; mc `m09-planc-reviewed`; mc `m09-planc-control-drop-nolock`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-09-f0905-dropall-race`

- Expected: ADR-0014 and NAT-I5 (after a deploy, no compiled plan made before it is left); NAT-T5.22.
- Observed at the pin: Live (b-09-f0905-dropall-race): a job-mode read started a build; DropAll 0.0 s later; after the job finished the namespace held entries {"1226463392": {"list_length": 4, "elements_defined": "10010", "class": "IVGC.P1226463392", "status": "ok", "shape_len": 0, "zcrc_of_shape": "0", "hash_matches_shape": false, "src_lines": ""}} (elements defined '10010') and classes ['IVGC.P1226463392']; Gen.Entries(): RuntimeError: <THROW>; two rereads answered [[['b09_db']], [['b09_db']]] and left {"1226463392": {"list_length": 4, "elements_defined": "10010", "class": "IVGC.P1226463392", "status": "ok", "sha…
- Source severity S3, confidence high; module 09; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): DropAll takes each entry's lock (or a namespace lock Build also takes); Build re-checks that its entry still exists before writing; For and Entries read with $ListGet.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0906"></a>
### The native gate checks the edge index but not the label index

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `reproduced-model`, not a native reproduction; severity is one level below the mapped Medium.

Found by: playbook arm, [09.json](../../experiment/playbook-completion/findings/audit/09.json) (mc `m09-gate-as-built`; mc `m09-gate-reviewed`; mc `m09-gate-control-always-open`; live `b-09-f0906-index-facts`; inspected `iris_vector_graph/cypher/native_plan.py:528-529`; inspected `iris_vector_graph/engine.py:703-724`)

Reproduced by: none (reproduced-model)

- Expected: NAT-I1 (labels are read from the adjacency index only where each label write keeps it up to date); CONTEXT.md:88-96 (the index is declared on the edge and label tables).
- Observed at the pin: Model m09-gate-as-built: with the edge index declared and the label index not (the state ensure_adjacency_index leaves when it fails between its two declarations, iris_vector_graph/schema.py:863-899), a label write keeps only the row and the open gate answers from ^KG; reviewed gate (both indexes) passes; control caught. Live (b-09-f0906-index-facts, read only): AUDITB has [['Graph.KG.rdfedges', 'idxedgesadj', 'index', 'idx_edges_adj'], ['Graph.KG.rdfedges', 'idxedgesgraphid', 'index', 'idx_edges_graph_id'], ['Graph.KG.rdfedges', 'idxedgesgraphoid', 'index', 'idx_edges_graph_oid'], ['Graph.KG…
- Source severity S2, confidence medium; module 09; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): The gate (or Graph.KG.Adjacency.Indexed()) also requires idx_labels_adj as a functional index; a unit test with the label index absent.
- Reviewed-design control: `playbook-proofs-d1d` `control_f0906_gate_edge_index_only` fails where expected in this run ([receipt](results/playbook-proofs-d1d/20261115T035710Z-control_f0906_gate_edge_index_only/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0907"></a>
### Shadow mode holds any ordered projection to a fixed row order, ties included

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [09.json](../../experiment/playbook-completion/findings/audit/09.json) (live `b-09-f0907-shadow-ties`; inspected `iris_vector_graph/cypher/native_plan.py:179-194`; inspected `iris_vector_graph/_engine/query.py:2232-2238`; inspected `iris_vector_graph/cypher/native_shadow.py:55-63`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-09-f0907-shadow-ties`

- Expected: spec 253 FR-013 and docs/dev/TCK.md: rows in the same order only where the query orders them completely; NAT-T8.4.
- Observed at the pin: Live (b-09-f0907-shadow-ties): {"limit": {"native": [["b09_t1", "same"], ["b09_t2", "same"]], "sql": [["b09_t4", "same"], ["b09_t3", "same"]], "shadow": "NativeMismatch"}, "nolimit": {"native": [["b09_t1", "same"], ["b09_t2", "same"], ["b09_t3", "same"], ["b09_t4", "same"]], "sql": [["b09_t4", "same"], ["b09_t3", "same"], ["b09_t2", "same"], ["b09_t1", "same"]], "shadow": "NativeMismatch"}, "control_unique_order": {"native": [["b09_t1", "same"], ["b09_t2", "same"]], "sql": [["b09_t1", "same"], ["b09_t2", "same"]], "shadow": "no mismatch"}}.
- Source severity S4, confidence high; module 09; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Compute 'ordered' for projections from whether the ORDER BY keys determine the returned row (or compare tied runs as bags); a unit test with a tied ORDER BY.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0908"></a>
### The privilege check spec 253 puts in the executor is in the engine only

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-versions.json](../../experiment/playbook-completion/findings/audit/zz-versions.json) (live `ver-priv-r3`; live `ver-priv-r2`; live `ver-priv-create`; inspected `iris_src/src/Graph/KG/Cypher/Exec.cls:32-72`; inspected `iris_src/src/Graph/KG/Cypher/Exec.cls:832-904`; inspected `iris_vector_graph/engine.py:559-586`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `ver-priv-r3`, `ver-priv-r2`, `ver-priv-create`

- Expected: specs/253-native-cypher-executor/spec.md:124-127 (FR-011: the executor MUST check SELECT on the graph tables, cached per process and user); decisions.md HD-0901 working answer: authorization at use.
- Observed at the pin: Live (ver-priv-r3; ver-priv-r2): a disposable user IVGAUDIT_RO holding ADMIN_GUIDE section 3's reading row in AUDITB (%DB_%DEFAULT:R, %Native_ClassExecution:U, %Native_GlobalAccess:U; SELECT and EXECUTE ON SCHEMA Graph_KG) had SELECT revoked (grantor-aware, CheckPrivilege 0 for user and role). Graph.KG.Cypher.Exec.Run called directly over the Native API by that user, now with no SELECT on any Graph_KG table, answered the plans for MATCH (a:P)-[:KNOWS]->(b) (3 rows) and MATCH (a:P {node_id:'a'})-[:KNOWS]->(b) ([b]); only a plan whose anchor the executor resolves through dynamic SQL (an unlabel…
- Source severity S3, confidence high; module 09; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Amend FR-011 to the shipped design (engine-side check, database resource as the boundary), or add the check to Run.
- Reviewed-design control: `playbook-proofs-d1d` `control_f0908_run_unchecked` fails where expected in this run ([receipt](results/playbook-proofs-d1d/20261115T035706Z-control_f0908_run_unchecked/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1d/20261115T035613Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Recorded in 09.json, zz-versions.json; the later file's record is used.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-0909"></a>
### Spec 253's 'same process' reason for seeing one's own writes is not what the code does

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [09.json](../../experiment/playbook-completion/findings/audit/09.json) (live `b-09-f0909-txn-visibility`; inspected `iris_vector_graph/engine.py:1894-1942`; inspected `iris_vector_graph/_engine/query.py:2202-2209`; assumed `P-0002`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-09-f0909-txn-visibility`

- Expected: specs/253-native-cypher-executor/spec.md:91-92 (a native read inside an open transaction sees its own writes because it runs in the same process); NAT-B4.1, NAT-T4.7.
- Observed at the pin: Live (b-09-f0909-txn-visibility): an engine from from_connect ran SQL in pid 15129 and native reads in pid 15130 (dedicated: True); with START TRANSACTION and an uncommitted node+edge in the SQL process (tlevel 1), its native read answered [[1]] (native: 1); another engine's process (pid 14786) also answered [[1]] natively; after ROLLBACK [[0]]. The read sees the caller's writes by reading uncommitted data from another process (P-0002), as it sees any writer's.
- Source severity S3, confidence high; module 09; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Correct the spec's reason; add an e2e test that writes in an open transaction and reads natively on an engine built with from_connect.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1005"></a>
### The interned snapshot can lack edges with nothing saying it is out of date

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [10.json](../../experiment/playbook-completion/findings/audit/10.json) (live `b-10-live-nkg-f1005`; mc `m10-nkg-as-built-fresh`; mc `m10-nkg-reviewed`; mc `m10-nkg-control-ensure-ignores-stale`; inspected `iris_src/src/Graph/KG/TemporalIndex.cls:104-112`; inspected `iris_src/src/Graph/KG/Adjacency.cls:111-140`)

Reproduced by: none (confirmed-source)

- Expected: ALG-B12.7 (a snapshot reader sees the same edges as the adjacency index or learns the snapshot is out of date); SYS-I8 and CONTEXT.md:109-114 (a rebuilt store matches its sources or says it is stale).
- Observed at the pin: Not reproduced live in the default configuration (b-10-live-nkg-f1005): with ^NKG built from b10_a -> b10_b, create_edge_temporal(b10_b, B10T, b10_c) wrote ['global:^KG', 'global:^NKG', 'sql:Graph_KG.rdf_edges'] (journal): the temporal edge asserted a structural rdf_edges row whose adjacency index wrote ^KG and interned b10_c into ^NKG (interned: True, edgeCount 1 -> 2); betweenness [{'id': 'b10_b', 'score': 1.0}] and closeness answered the same before and after engine.sync() (differs: False). The source shows why: TemporalIndex.InsertEdge calls Adjacency.PutShadow (no interning, no stale mar…
- Source severity S3, confidence medium; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Mark ^NKG stale in PutShadow when ^NKG is built (EnsureNKG then rebuilds), or compare builtFrom with the token in EnsureNKG; correct the ADJACENCY CONTRACT docstring (temporal.py:280-286), which still says temporal edges are never interned although the indexed path interns them.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1009"></a>
### khop answers a start node that exists only in a named graph

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [10.json](../../experiment/playbook-completion/findings/audit/10.json) (live `b-10-live-scope`; mc `m10-walk-as-built-khop`; mc `m10-walk-reviewed`; inspected `iris_vector_graph/_engine/algorithms.py:600-626`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-10-live-scope`

- Expected: The khop docstring: a missing seed answers two empty lists (_engine/algorithms.py:577-594); ALG-I3.
- Observed at the pin: Live (b-10-live-scope): khop('b10_z') for b10_z held only by named graph b10g1 answered {'nodes': ['b10_z'], 'edges': []}; khop of an id in no graph answered {'nodes': [], 'edges': []}. Model m10-walk-as-built-khop reproduces it.
- Source severity S3, confidence high; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Add graph_id = '' to _khop_seed_exists.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1010"></a>
### Leiden's server route ignores max_levels and tol

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [10.json](../../experiment/playbook-completion/findings/audit/10.json) (inspected `iris_vector_graph/stores/iris_sql_store.py:3765-3790`; inspected `iris_src/src/Graph/KG/Communities.cls:615`; inspected `iris_src/src/Graph/KG/Communities.cls:433-443`; inspected `iris_vector_graph/_engine/algorithms.py:1527-1545`)

Reproduced by: none (confirmed-source)

- Expected: leiden_communities documents max_levels and tol as arguments (_engine/algorithms.py:1527-1545).
- Observed at the pin: Confirmed at the source: _leiden_serverside calls Graph.KG.Communities.LeidenJsonAuto(10, gamma, 0.0001, top_k, 256, seed) whatever the caller passed (iris_vector_graph/stores/iris_sql_store.py:3765-3790); LeidenJsonPy takes neither (iris_src/src/Graph/KG/Communities.cls:615) and LeidenJson documents tol as unused (Communities.cls:433-443). Not driven live: which server path runs (leidenalg in IRIS Python or the greedy ObjectScript fallback) depends on the instance's Python packages, so an equal answer for two max_levels values would not by itself show the argument was dropped.
- Source severity S3, confidence high; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Pass the caller's values, or document that this route ignores them.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1011"></a>
### Documents describe snapshot behaviour the code no longer has

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [10.json](../../experiment/playbook-completion/findings/audit/10.json) (inspected `docs/ADMIN_GUIDE.md:1271-1272`; inspected `iris_vector_graph/stores/iris_sql_store.py:3322-3336`; inspected `iris_vector_graph/_engine/algorithms.py:1676-1684`; inspected `iris_vector_graph/stores/iris_sql_store.py:3977-4006`; live `b-10-live-nkg`)

Reproduced by: none (confirmed-source)

- Expected: docs/ADMIN_GUIDE.md and the method docstrings describe what the code does.
- Observed at the pin: Confirmed at the source: ADMIN_GUIDE.md:1271-1272 says algorithms answer [] for every node when ^NKG is not built, but the methods fall back to a Python walk with a warning (iris_sql_store.py:3322-3336; seen live in b-10-live-nkg: betweenness on an unbuilt ^NKG answered from the Python walk) or raise; the triangle_count / strongly_connected_components / k_core docstrings say they read ^NKG while only the default graph has edges (_engine/algorithms.py:1676-1684) but the store methods use the Arno upload of ^KG graph 0 or LazyKG (iris_sql_store.py:3977-4006).
- Source severity S3, confidence high; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Update the troubleshooting entry and the three docstrings.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1012"></a>
### The proof record names one library build for entries proven on different builds

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `reproduced-test`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [10.json](../../experiment/playbook-completion/findings/audit/10.json) (probe `b-10-probe-units`; run `b-10-run-unit`; inspected `iris_vector_graph/_arno_gate.py:138-177`)

Reproduced by: none (reproduced-test)

- Expected: CONTEXT.md:276-280: the proof record holds the build each reader was proven on.
- Observed at the pin: Probe (b-10-probe-units) of the pin's _arno_gate.build_proof: with a previous record proving pagerank on build 1.2.0 and a run that proved only wcc on build 1.3.0, the new record keeps pagerank (True) and names only {'version': '1.3.0', 'sha256': {'lib': 'bbb'}} as its library, with no per-entry build (False). The upstream unit test that asserts the keeping (tests/unit/test_236_reader_gate.py) passed here (b-10-run-unit).
- Source severity S3, confidence high; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Keep the library identity per entry.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1013"></a>
### Graph.KG.PageRankEmbedded is deployed and reads every graph

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [10.json](../../experiment/playbook-completion/findings/audit/10.json) (live `b-10-live-scope`; inspected `iris_src/src/Graph/KG/PageRankEmbedded.cls:5-30`; inspected `docs/ADMIN_GUIDE.md:346`; inspected `scripts/deploy_objectscript.py:129`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-10-live-scope`

- Expected: ALG-I2/ALG-I3 and the IVG schema boundary (spec 262: the IVG tables live in the IVG schema, Graph_KG here).
- Observed at the pin: Live (b-10-live-scope): the deployed class method Graph.KG.PageRankEmbedded.ComputePageRank('b10_%', ...) answered {"raised": "RuntimeError: <THROW> *%Exception.PythonException <PYTHON EXCEPTION> 246 <class 'irisbuiltins.SQLError'>: Table 'SQLUSER.NODES' not found"}: its unqualified table names resolve to SQLUser, outside the namespace's IVG schema, so the deployed class cannot run against the IVG tables at all here; where a SQLUser.nodes/rdf_edges exists it reads that table instead. The every-graph part is confirmed at the source only: ComputePageRankCore selects nodes and rdf_edges by node_…
- Source severity S3, confidence high; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Remove the class or scope it to one graph and the IVG schema (qualified table names).
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1102"></a>
### The stats row can lose counts

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [11.json](../../experiment/playbook-completion/findings/audit/11.json) (live `b-11-live-f1102-contention`; live `b-11-live-f1102-locktimeout`; live `b-11-live-f1102-txn`; mc `m11-stats-as-built-rmw`; mc `m11-stats-as-built-caller-txn`; mc `m11-stats-reviewed`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-11-live-f1102-contention`, `b-11-live-f1102-locktimeout`, `b-11-live-f1102-txn`

- Expected: docs/ledger-prometheus-hook.md:16 ('ledger_stats counts every process's commits, so it is the one to use for totals'); LED-B13.4 (each outcome adds exactly one); FR-051 (LedgerStats.cls:1-3).
- Observed at the pin: Live AUDITB: (1) four processes x 1,000 Ledger.Count calls, each answering status 1, raised the counter by 3,865 (135 lost updates of the %OpenId/%Save read-modify-write; b-11-live-f1102-contention; 2 x 300 calls lost none in b-11-live-f1102-txn). (2) A commit nested in process A's caller transaction holds the stats row's lock until that transaction ends: process B's Count waited 10.0 s and failed with a %SaveData lock error that every caller ignores, so its count is lost (b-11-live-f1102-locktimeout); a refused commit or a guard refusal in another process therefore stalls 10 s too. (3) The f…
- Source severity S3, confidence high; module 11; governing page here: `ledger.`.
- Remedy proposed by the playbook arm (not implemented): Increment each counter atomically ($Increment on a mapped global, or UPDATE ... SET c = c + 1 outside the commit's transaction for refusals), count commits in a way a rollback takes back exactly, and never let a counter update wait on another process's transaction; or document the counters as approximate lower bounds.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1104"></a>
### Two first enables at once: the second fails instead of returning the genesis

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [11.json](../../experiment/playbook-completion/findings/audit/11.json) (live `b-11-live-f1104`; mc `m11-enable-as-built`; mc `m11-enable-as-built-consistency`; mc `m11-enable-reviewed`; inspected `iris_src/src/Graph/KG/Ledger.cls:252-329`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-11-live-f1104`

- Expected: specs/213-graph-revision-ledger/contracts/ledger-api.md:22 (enable returns the genesis on the first call or the current head, idempotent); LED-B1.12; decisions.md HD-1104 (assumption: settings fixed at genesis; does not change idempotency).
- Observed at the pin: Live AUDITB, two processes released together on a never-enabled ledger with 1,500 nodes: in 8 of 8 trials one Enable answered inconsistent and the other seq 1 (b-11-live-f1104). Two mechanisms: 6 trials 'revision row missing for seq 0': the second read the first's uncommitted state=enabled and head=0 on the unlocked fast path (Ledger.cls:254-260); 2 trials 'ID key not unique': the second had read never-enabled before the first set it, waited on the head lock and re-ran the genesis (:288-304, P-1106 confirmed). The ledger was left enabled at head 1 with one revision (rollback intact). Model: m…
- Source severity S3, confidence high; module 11; governing page here: `ledger.`.
- Remedy proposed by the playbook arm (not implemented): Take the head lock before reading the state (or re-read it under the lock) in every branch, including the enabled fast path; a live test with two concurrent enable() calls.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1106"></a>
### A replayed commit returns no statement ids

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [11.json](../../experiment/playbook-completion/findings/audit/11.json) (live `b-11-live-findings`; mc `m11-retry-as-built-stmt-ids`; inspected `iris_src/src/Graph/KG/Ledger.cls:455-462`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-11-live-findings`

- Expected: ledger-api.md:26 ('original outcome with replayed=True'); changeset.schema.json:273-285 (CommitResponse.stmt_ids); LED-B4.7.8.
- Observed at the pin: Live AUDITB (b-11-live-findings): first commit of a keyed create_relationship answered stmt_ids {0: '2'}; the retry answered replayed=True with stmt_ids {}. Model m11-retry-as-built-stmt-ids violates LED-B4.7.8; m11-retry-reviewed passes.
- Source severity S3, confidence high; module 11; governing page here: `ledger.`.
- Remedy proposed by the playbook arm (not implemented): Rebuild stmt_ids from the revision's create_rel/upsert_rel records (or store them with the key), or amend the contract; a test comparing both answers.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1109"></a>
### The user guide says a retry replays without a retry key

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [11.json](../../experiment/playbook-completion/findings/audit/11.json) (live `b-11-live-findings`; inspected `docs/USER_GUIDE.md:1102`; inspected `iris_src/src/Graph/KG/Ledger.cls:453-463`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-11-live-findings`

- Expected: docs/USER_GUIDE.md:1102 ('Committing the same actor and operations again returns the first revision with replayed=True'); client.py:85-91 CommitResult docstring.
- Observed at the pin: Live AUDITB (b-11-live-findings): the same set_property changeset committed twice without a key made two revisions (second not replayed); create_node twice without a key: the second refused node_exists. The server looks for a replay only with an idempotency_key (Ledger.cls:455-457).
- Source severity S3, confidence high; module 11; governing page here: `ledger.`.
- Remedy proposed by the playbook arm (not implemented): Say 'with the same idempotency_key' in USER_GUIDE.md:1102 and the CommitResult docstring.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1110"></a>
### The wire contract lags the code

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `reproduced-test`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [11.json](../../experiment/playbook-completion/findings/audit/11.json) (probe `b-11-probe-schema`; inspected `specs/213-graph-revision-ledger/contracts/changeset.schema.json`; inspected `iris_vector_graph/ledger/changeset.py:309-360`)

Reproduced by: none (reproduced-test)

- Expected: LED-B8.12 (the wire contract lists every change kind and error code the server uses); specs/213-graph-revision-ledger/contracts/changeset.schema.json; ledger-api.md:26.
- Observed at the pin: Probe (b-11-probe-schema, no IRIS; the pin's builder validated against the published schema with jsonschema Draft 2020-12 as tests/unit/test_ledger_changeset.py does): a create_temporal_edge op is invalid; post_commit_properties is rejected (additionalProperties false); CommitError.error lacks idempotency_redacted, redaction_in_progress, invalid_target and target_live, which Ledger*.cls answer; MutationRecord enums lack create_temporal_edge / temporal_edge; ledger-api.md:26 still lists LedgerTransactionOpenError for commit.
- Source severity S3, confidence high; module 11; governing page here: `ledger.`.
- Remedy proposed by the playbook arm (not implemented): Update changeset.schema.json and ledger-api.md; extend the upstream schema unit test with a temporal op and post-commit properties.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1111"></a>
### The metrics hook is not called for refusals made in Python

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [11.json](../../experiment/playbook-completion/findings/audit/11.json) (live `b-11-live-findings`; inspected `iris_vector_graph/ledger/client.py:381-416`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-11-live-findings`

- Expected: docs/ledger-prometheus-hook.md:35-36 ('engine.ledger.commit() calls it once per call, whatever the outcome'); LED-B9.8.
- Observed at the pin: Live AUDITB (b-11-live-findings): a registered hook saw 0 events for an EmptyChangesetError and for a ChangesetOperationError (bad op_ref), both raised by changeset.validate() before _emit (client.py:392), and 1 event (stale_head) for a server refusal.
- Source severity S4, confidence high; module 11; governing page here: `ledger.`.
- Remedy proposed by the playbook arm (not implemented): Emit before raising in commit(), or narrow the doc to calls that reach the server.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1112"></a>
### Two e2e fixtures read a meta key that does not exist and disable the ledger after them

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [11.json](../../experiment/playbook-completion/findings/audit/11.json) (live `b-11-live-findings`; inspected `tests/e2e/test_460_r281_ledger_post_commit_graph_e2e.py:52`; inspected `tests/e2e/test_460_r290_ledger_node_ops_graph_e2e.py:66`; inspected `iris_src/src/Graph/KG/Ledger.cls:143-156`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-11-live-findings`

- Expected: LED-B3.12 (a caller learns if the ledger is on from meta's state; meta has no other on flag).
- Observed at the pin: Live AUDITB (b-11-live-findings): meta() keys are ok, state, strict, max_ops, recon_bound, head_seq, head_id; with the ledger enabled bool(meta().get('enabled')) is False, so the fixtures at tests/e2e/test_460_r281_ledger_post_commit_graph_e2e.py:52 and tests/e2e/test_460_r290_ledger_node_ops_graph_e2e.py:66 always enable() and always disable() at teardown.
- Source severity S4, confidence high; module 11; governing page here: `ledger.`.
- Remedy proposed by the playbook arm (not implemented): Test meta()['state'] == 'enabled' in both fixtures.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1113"></a>
### The history source filter matches stored JSON text, not a source string

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [11.json](../../experiment/playbook-completion/findings/audit/11.json) (live `b-11-live-f1113`; inspected `iris_vector_graph/ledger/replay.py:339-341`; inspected `iris_src/src/Graph/KG/Ledger.cls:521-522`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-11-live-f1113`

- Expected: client.py:613 ('Filter to revisions tagged with this source string'); LED-B3.9; CHANGELOG spec 216 entry.
- Observed at the pin: Live AUDITB (b-11-live-f1113): source={'system':'cmms','run':'b11'} is stored as IRIS JSON text {"run":"b11","system":"cmms"}; history(source='cmms') answers 0 revisions, the exact stored text 1, Python's insertion-order JSON text 0.
- Source severity S3, confidence high; module 11; governing page here: `ledger.`.
- Remedy proposed by the playbook arm (not implemented): Document the exact-text rule or filter on a JSON field of source; a live test.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1301"></a>
### Spec 256 FR-004 ('every record') contradicts Decision 2 ('any record') on clearing revision free text

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [13.json](../../experiment/playbook-completion/findings/audit/13.json) (source `specs/256-ledger-tenant-redaction/spec.md (FR-004 vs Decisions)`)

Reproduced by: none (confirmed-source)

- Expected: Decision 2 / ADR-0013 (accepted): clear free text when any record of the revision is redacted (HD-1302 supported).
- Observed at the pin: Implementation and live behaviour follow 'any' (fresh: upstream spanning-revision test in the original run; intent lane B record HD-1302). The spec's FR-004 wording is stale.
- Source severity S3, confidence high; module 13; governing page here: `redaction.`.
- Remedy proposed by the playbook arm (not implemented): Edit FR-004 to say 'any record', matching Decision 2 and ADR-0013.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1501"></a>
### PROV export raises on a failed window read; its docstring and SEMANTIC_LAYER say it logs and writes an empty file

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [15.json](../../experiment/playbook-completion/findings/audit/15.json) (live `c15-live-rdf`; run `c15-run-unit`; inspected `iris_vector_graph/_engine/prov.py:107-139`; inspected `iris_vector_graph/_engine/prov.py:181-207`; inspected `docs/SEMANTIC_LAYER.md:264-269`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c15-live-rdf`

- Expected: The 4.6.0 rule is that a failed read raises (CHANGELOG 4.6.0, commit 2d1d6f46; INT-V1.5). The docstring (iris_vector_graph/_engine/prov.py:114-115 'A failed window read is logged and exports nothing') and docs/SEMANTIC_LAYER.md:267-269 ('logged as a warning and exported as an empty file, not raised') still describe the pre-4.6.0 behaviour.
- Observed at the pin: Live: prov_export on an engine whose IRIS connection fails raised RuntimeError '<COMMUNICATION LINK ERROR> Connection closed' and wrote no file (c15-live-rdf, prov_failed_window). The upstream unit test test_get_temporal_edges_window_no_iris_raises (asserting the raise) passed in the module set (c15-run-unit). _get_temporal_edges_window has no try (prov.py:181-207).
- Source severity S3, confidence high; module 15; governing page here: `fhir.`.
- Remedy proposed by the playbook arm (not implemented): Correct the prov_export docstring, docs/SEMANTIC_LAYER.md 'Limits of the PROV-O export' and the copy in docs/API_REFERENCE.md to say a failed or too-large window read raises.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1504"></a>
### map_sql_table looks up an unqualified table in schema 'USER' instead of the default schema SQLUser

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [15.json](../../experiment/playbook-completion/findings/audit/15.json) (live `c15-live-tablemap`; inspected `iris_vector_graph/_engine/fhir.py:112-126`)

Reproduced by: none (confirmed-source)

- Expected: INT-M1.4: a table name with no schema is found in the default SQL schema; IRIS puts an unqualified table in SQLUser (P-1509).
- Observed at the pin: Live (c15-live-tablemap): %SYSTEM.SQL.Schema.Default() = 'SQLUser'; INFORMATION_SCHEMA has 0 tables in schema 'USER'; the catalog query map_sql_table runs for an unqualified name uses TABLE_SCHEMA='USER' (fhir.py:113-120) and so refuses every unqualified name ('Table ... not found'), while the qualified IVGAudit.C15Patients mapping succeeds. A real SQLUser table mapped unqualified was not driven: AUDITC has no SQLUser table and the audit may create scratch tables only under IVGAudit.*.
- Source severity S4, confidence high; module 15; governing page here: `fhir.`.
- Remedy proposed by the playbook arm (not implemented): Use the namespace default schema (SQLUser, or $SYSTEM.SQL.Schema.Default()) for an unqualified name; add a test with an unqualified table.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1505"></a>
### FHIRSearchTool says it handles pagination; the condition search reads one Bundle page

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `reproduced-test`, not a native reproduction; severity is one level below the mapped Medium.

Found by: playbook arm, [15.json](../../experiment/playbook-completion/findings/audit/15.json) (probe `c15-probe-noiris`; inspected `iris_vector_graph/fhir_bridge.py:85-127`)

Reproduced by: none (reproduced-test)

- Expected: FHIRSearchTool docstring 'Wraps FHIR REST API details (pagination, auth, resource parsing)' (iris_vector_graph/fhir_bridge.py:305-310); INT-B1.8.
- Observed at the pin: Probe (c15-probe-noiris): against a local FHIR stub whose first Bundle page (2 Conditions) carries link[relation=next] to a second page (1 Condition), fhir_search_conditions and FHIRSearchTool returned the 2 page-1 codes; the stub logged no page-2 request.
- Source severity S2, confidence high; module 15; governing page here: `fhir.`.
- Remedy proposed by the playbook arm (not implemented): Follow next links with a page cap, or correct the docstring.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1506"></a>
### With rdflib lacking ConjunctiveGraph (rdflib 8 per KNOWN_ISSUES), export and SHACL report 'rdflib is required'

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `reproduced-test`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [15.json](../../experiment/playbook-completion/findings/audit/15.json) (probe `c15-probe-noiris`; inspected `iris_vector_graph/_engine/_rdf_utils.py:125-133`; assumed `P-1507`; run `rx-live-15`)

Reproduced by: none (reproduced-test)

- Expected: SYS-I9 (every refusal says why); INT-R1.19.
- Observed at the pin: Probe (c15-probe-noiris): with rdflib 7.6.0 importable but its ConjunctiveGraph attribute removed in the process, _build_rdflib_graph raised ImportError 'rdflib is required for RDF operations. Install with: pip install iris-vector-graph[rdf]' (cause: cannot import name 'ConjunctiveGraph'). The real rdflib 8 could not be installed: PyPI lists no rdflib 8 release (latest 7.6.0, checked 2026-11-13), so premise P-1507 ('rdflib 8 removes ConjunctiveGraph', docs/KNOWN_ISSUES.md 'The RDF extra needs rdflib 7') is unverified.
- Source severity S4, confidence medium; module 15; governing page here: `fhir.`.
- Remedy proposed by the playbook arm (not implemented): Import ConjunctiveGraph in its own try and name the rdflib<8 requirement (or move to Dataset).
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1509"></a>
### The old clinical pipeline reports a failed rank walk as 'no graph connectivity'

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `reproduced-test`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [15.json](../../experiment/playbook-completion/findings/audit/15.json) (probe `c15-probe-noiris`; run `c15-run-unit`; inspected `iris_vector_graph/fhir_bridge.py:281-295`)

Reproduced by: none (reproduced-test)

- Expected: 4.6.0 rule: failures reach the caller (CHANGELOG); INT-B1.9. Docstring status list omits fhir_error (fhir_bridge.py:220-227).
- Observed at the pin: Probe (c15-probe-noiris): with an autospec of IRISGraphEngine whose kg_PERSONALIZED_PAGERANK raises, unified_clinical_pipeline returned status 'anchors_resolved_but_no_graph_connectivity', the same status as a genuinely empty walk; an unreachable FHIR base returned 'fhir_error', a status the docstring does not list. Upstream tests pin the status for an empty walk (test_pipeline_ppr_empty, passed in c15-run-unit) and record that this except once hid a TypeError (tests/unit/test_231_fhir_bridge_fixes.py:1-8).
- Source severity S3, confidence high; module 15; governing page here: `fhir.`.
- Remedy proposed by the playbook arm (not implemented): Re-raise or return a distinct 'ppr_error' status; document fhir_error.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1510"></a>
### RDF export claims bounded memory but builds the whole graph in memory

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [15.json](../../experiment/playbook-completion/findings/audit/15.json) (live `c15-live-memory`; inspected `iris_vector_graph/_engine/_rdf_utils.py:102-135`; inspected `iris_vector_graph/_engine/rdf_export.py:10-14`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c15-live-memory`

- Expected: rdf_export.py:10-14 'Streaming cursor pattern - memory-bounded for any graph size'; INT-R1.13.
- Observed at the pin: Live (c15-live-memory): export_rdf of a 300-node graph (1,200 triples) peaked at 1.80 MB of Python allocations (tracemalloc) and of a 3,000-node graph (12,000 triples) at 18.6 MB: ratio 10.33 for 10x the triples, about 1.5 KB per triple, i.e. linear in graph size (one in-memory ConjunctiveGraph, _rdf_utils.py:135,210-284, serialized at the end, rdf_export.py:143).
- Source severity S3, confidence high; module 15; governing page here: `fhir.`.
- Remedy proposed by the playbook arm (not implemented): Stream N-Triples/N-Quads row by row, or correct the docstring and SEMANTIC_LAYER.md.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1511"></a>
### A register that fails after its upsert keeps the new settings

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `reproduced-model`, not a native reproduction; severity is one level below the mapped Medium.

Found by: playbook arm, [15.json](../../experiment/playbook-completion/findings/audit/15.json) (inspected `iris_src/src/Graph/KG/FHIRGraph.cls:167-279`; live `c15-live-register`; mc `cmc-register-as-built-refusal`; mc `cmc-register-as-built-links`; mc `cmc-register-reviewed`; control `cmc-register-ctl-upsert`)

Reproduced by: none (reproduced-model)

- Expected: SYS-I3 (a refused command leaves every store as it was); INT-F3.9.
- Observed at the pin: \Source: Register upserts Graph_KG.fhir_graphs (FHIRGraph.cls:235-245) with autocommit Exec and no TSTART, then runs Open, LoadColumns (LoadLinks, LoadCompartment, LoadProps, HS.FHIRServer.Schema.LoadSchema) and the json_links UPDATE (:247-258); the Catch (:276-278) returns an error without undoing the upsert. Live on Community (c15-live-register): every refusal reachable without a repository happens before the upsert and wrote 0 journal records, so the defect window cannot be entered here.
- Source severity S2, confidence high; module 15; governing page here: `fhir.`.
- Remedy proposed by the playbook arm (not implemented): Validate and load metadata before writing, then do the upsert and the json_links update in one transaction (or roll back the upsert on failure).
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1605"></a>
### The sample API's nodes field names Graph_KG instead of the engine's schema

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Medium.

Found by: playbook arm, [16.json](../../experiment/playbook-completion/findings/audit/16.json) (inspected `api/gql/core/resolvers.py:172-274`; inspected `api/gql/loaders.py:29-263`; inspected `iris_vector_graph/_engine/class_deploy.py:112-117`)

Reproduced by: none (confirmed-source)

- Expected: Spec 262 / API-B6.5: surfaces read the engine's IVG Schema (engine._ivg_schema); the generated server does (iris_vector_graph/gql/engine.py:14-15).
- Observed at the pin: Source at the pin: api/gql/core/resolvers.py:172-175, :206-274 and api/gql/loaders.py hard-code Graph_KG. Not reproducible live here: AUDITC is installed under Graph_KG and lanes may not create a namespace with another IVG Schema (CONVENTIONS.md scope control). The server classes are not affected: class deploy rewrites the Graph_KG token to the chosen schema (iris_vector_graph/_engine/class_deploy.py:112-117), so MCPTools/PyOps literals are rewritten at deploy.
- Source severity S2, confidence high; module 16; governing page here: `access.`.
- Remedy proposed by the playbook arm (not implemented): Build the SQL from engine._ivg_schema; run the GraphQL tests on a custom-schema namespace.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1606"></a>
### The sample API's Cypher route accepts a timeout and a cache flag and uses neither

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [16.json](../../experiment/playbook-completion/findings/audit/16.json) (live `c16-s3-graphql-sample-api`; inspected `api/models/cypher.py:41-58`; inspected `api/routers/cypher.py:94-260`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c16-s3-graphql-sample-api`

- Expected: api/models/cypher.py:41-58 documents timeout as 'Query execution timeout' (1-300 s); API-B5.7.
- Observed at the pin: Live (c16-s3-graphql-sample-api): POST /api/cypher with timeout=1 ran a 3-way cross join of 120 nodes for 1.83 s and answered 200 with the full count (1,728,000). Source: api/routers/cypher.py:94-260 never reads request.timeout or enable_cache.
- Source severity S3, confidence medium; module 16; governing page here: `access.`.
- Remedy proposed by the playbook arm (not implemented): Enforce the timeout (statement timeout or cancel) or remove the fields from the model and docs.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1611"></a>
### The generated GraphQL server's health route always says healthy

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [16.json](../../experiment/playbook-completion/findings/audit/16.json) (live `c16-s3-graphql-sample-api`; inspected `iris_vector_graph/gql/__init__.py:58-67`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c16-s3-graphql-sample-api`

- Expected: API-B10.6: health says so when IRIS does not answer (the sample API answers 503 since 4.6.3, CHANGELOG.md:493-497).
- Observed at the pin: Live (c16-s3-graphql-sample-api): create_app over an engine whose connection was closed answered GET /health 200 {status: healthy, database: disconnected}. Source: iris_vector_graph/gql/__init__.py:58-67.
- Source severity S3, confidence high; module 16; governing page here: `access.`.
- Remedy proposed by the playbook arm (not implemented): Answer 503 when the probe fails, as api/main.py does.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1613"></a>
### The MCP vector lookup treats the client's text as a node id

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `blocked-access`, not a native reproduction; severity is one level below the mapped Medium.

**Conditional:** the playbook arm could not reach the deciding state (`blocked-access`).

Found by: playbook arm, [16.json](../../experiment/playbook-completion/findings/audit/16.json) (inspected `iris_src/src/Graph/KG/MCPTools.cls:189-221`; inspected `$RUN_DIR/setup/deploy-AUDITC.json (objectscript_skipped)`)

Reproduced by: none (blocked-access)

- Expected: MCPTools.cls:189-192 documents query as a natural-language description; API-B12.9.
- Observed at the pin: Source at the pin: EvidenceSearch binds query as node_id in the subquery that fetches that node's vector (iris_src/src/Graph/KG/MCPTools.cls:193-221). Not run: Graph.KG.MCPService/MCPToolSet/MCPTools cannot be deployed on IRIS Community (setup skipped them: needs %AI.MCP.Service, %AI.ToolSet, %AI.Tool, %AI.Policy.ConsoleAudit; $RUN_DIR/setup/deploy-AUDITC.json).
- Source severity S2, confidence high; module 16; governing page here: `access.`.
- Remedy proposed by the playbook arm (not implemented): Embed the text before the search (engine.embed_text or IRIS EMBEDDING()), or document the argument as a node id; e2e test on an AI build.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1702"></a>
### A caller transaction cannot be opened through an in-IRIS cursor

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `reproduced-test`, not a native reproduction; severity is one level below the mapped Medium.

Found by: playbook arm, [17.json](../../experiment/playbook-completion/findings/audit/17.json) (run `c17-run-unit-ops`; check `c17-offline`; inspected `iris_vector_graph/embedded.py:312-321`; inspected `iris_vector_graph/_write_txn.py:206-207`)

Reproduced by: none (reproduced-test)

- Expected: docs/USER_GUIDE.md 'Writes inside your transaction': after SQL START TRANSACTION the caller's ROLLBACK removes IVG's write; no exception for EmbeddedConnection.
- Observed at the pin: EmbeddedCursor.execute returns before sending START TRANSACTION, BEGIN, BEGIN TRANSACTION, COMMIT, ROLLBACK (iris_vector_graph/embedded.py:312-321). Checked through the cursor itself with a recording stand-in for iris.sql (c17-offline: none of the four statements reached it) and the upstream unit test test_transaction_statements_are_noop (c17-run-unit-ops, passed). The irispython E2E (USER_GUIDE example inside IRIS) needs the package installed in the container's embedded Python: blocked-access (installing it would modify the container).
- Source severity S2, confidence high; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): Map the statements to TSTART/TCOMMIT/TROLLBACK (or pass them through) in EmbeddedCursor, or document the limit; an irispython E2E of the USER_GUIDE example.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1703"></a>
### IVG_STRICT_NAMESPACE warns; two documents say it raises

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [17.json](../../experiment/playbook-completion/findings/audit/17.json) (live `c17-live-engine`; run `c17-run-unit-ops`; inspected `iris_vector_graph/stores/iris_sql_store.py:815-838`; live `rx-live-17`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c17-live-engine`, `rx-live-17`

- Expected: docs/ADMIN_GUIDE.md:1254 ('1 raises'); iris_vector_graph/exceptions.py:19-20 ('Upgrade to a hard error').
- Observed at the pin: Live (c17-live-engine): IRISGraphStore(conn to AUDITC, namespace='USER') with IVG_STRICT_NAMESPACE=1: outcome returned; warnings ["NamespaceMismatchWarning: Namespace mismatch: connected to 'AUDITC', expected 'USER'. IVG works in the connection's namespace, 'AUDITC': drop namespace= or connect to 'USER'."]. Source iris_vector_graph/stores/iris_sql_store.py:830-838 (warnings.warn, no raise).
- Source severity S3, confidence high; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): Raise when strict, or correct ADMIN_GUIDE and the docstring.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1704"></a>
### The error root does not catch every IVG error

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `reproduced-test`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [17.json](../../experiment/playbook-completion/findings/audit/17.json) (check `c17-offline`; run `c17-run-unit-ops`)

Reproduced by: none (reproduced-test)

- Expected: iris_vector_graph/errors.py:1-17: every engine-side error descends from IVGError, one catchable root.
- Observed at the pin: c17-offline: the nine classes the finding names are not IVGError subclasses (MRO recorded); a mechanical scan of every exception class the package defines finds 26 outside IVGError, e.g. BatchShortfall, _NotALiteral, SnapshotReadError, AQLParseError, AQLTranslationError, _Decline, NativeMismatch, CypherParseError, EntityNotFoundError, TemporalQueryRequiresEngine, _NoFold, EmbeddedUnavailableError.
- Source severity S3, confidence high; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): Re-base the public errors on IVGError (keep current bases as mixins) or narrow the docstring; extend test_all_descend_from_single_root to every exported error.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1705"></a>
### vector_similarity_search ranks L2 results farthest first

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [17.json](../../experiment/playbook-completion/findings/audit/17.json) (live `c17-live-vec`; inspected `iris_vector_graph/dbapi_utils.py:238-275`)

Reproduced by: none (confirmed-source)

- Expected: A similarity search returns the nearest rows (docstring, dbapi_utils.py:249-252); VECTOR_L2 is a distance (P-1710).
- Observed at the pin: \Source: metric='L2' maps to VECTOR_L2 and the statement orders score DESC (dbapi_utils.py:256-272). Live (c17-live-vec, IRIS IRIS for UNIX (Ubuntu Server LTS for x86-64 Containers) 2026.1 (Build 234U) Fri Mar 27 2026 14:07:14 EDT, scratch table IVGAudit.C17V rows 1:[0,0], 2:[1,0], 3:[5,0]): vector_similarity_search(metric='L2') -> ProgrammingError: <SQL ERROR>; Details: [SQLCODE: <-359>:<SQL Function (function stored procedure) not found>] [Location: <Prepare>] [%msg: < User defined SQL function 'SQLUSER.VECTOR_L2' does not exist>]; raw VECTOR_L2 -> ProgrammingError: <SQL ERROR>; Details: [SQ…
- Source severity S3, confidence medium; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): ORDER BY score ASC for L2 (or negate it); a test with three known vectors.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1706"></a>
### create_hnsw_index does not try ACORN first

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [17.json](../../experiment/playbook-completion/findings/audit/17.json) (live `c17-live-vec`; inspected `iris_vector_graph/dbapi_utils.py:170-204`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c17-live-vec`

- Expected: Docstring: 'Tries ACORN=1 first (faster build, IRIS 2025.1+), falls back to standard HNSW' (dbapi_utils.py:181-183).
- Observed at the pin: Live (c17-live-vec): the statements create_hnsw_index sent, captured through a recording cursor on AUDITC: ["CREATE INDEX C17VHNSW ON IVGAudit.C17V (emb) AS HNSW(M=16, efConstruction=200, Distance='L2')"]; it returned False.
- Source severity S4, confidence high; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): Implement the two-step attempt or correct the docstring.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1707"></a>
### SHOW CONSTRAINTS and the index lists name keys the schema does not have

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [17.json](../../experiment/playbook-completion/findings/audit/17.json) (live `c17-live-engine`; inspected `iris_vector_graph/_engine/admin.py:255-280`; inspected `iris_vector_graph/stores/iris_sql_store.py:3060-3082`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c17-live-engine`

- Expected: SHOW CONSTRAINTS reports the namespace's real keys; since spec 227/234 nodes are keyed (node_id, graph_id) and edges u_spo_graph_ekey (iris_vector_graph/schema.py:399-400, :44).
- Observed at the pin: Live (c17-live-engine): SHOW CONSTRAINTS answered {'columns': ['name', 'type', 'entityType', 'labelsOrTypes', 'properties', 'ownedIndex'], 'error': None, 'rows': [['node_id_unique', 'UNIQUENESS', 'NODE', "['*']", "['node_id']", 'pk_nodes'], ['edge_spo_unique', 'UNIQUENESS', 'RELATIONSHIP', "['*']", "['s', 'p', 'o_id']", 'pk_rdf_edges'], ['fhir_bridge_unique', 'UNIQUENESS', 'NODE', "['*']", "['fhir_code', 'kg_node_id']", 'pk_bridge']]}; the store's list_indexes [['pk_nodes', 'UNIQUE', 'ONLINE'], ['pk_rdf_edges', 'UNIQUE', 'ONLINE']]; INFORMATION_SCHEMA.TABLE_CONSTRAINTS for nodes/rdf_edges [['…
- Source severity S3, confidence high; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): Read constraints from the dictionary, or list the real names and columns.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1708"></a>
### The bolt-on installer does not do what deploy/README.md says

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Medium.

Found by: playbook arm, [17.json](../../experiment/playbook-completion/findings/audit/17.json) (inspected `deploy/bolt-on/install.sh:15-100`; inspected `deploy/README.md:20-26, 84-101`; inspected `iris_vector_graph/cli.py:415-441`)

Reproduced by: none (confirmed-source)

- Expected: deploy/README.md:24 (creates namespace, installs schema, prints key and start command) and :85 (ivg_service user with access only to Graph_KG.* tables).
- Observed at the pin: Confirmed in source: deploy/bolt-on/install.sh generates a password (:21-22) and writes ivg-config.yml (:72-91) but creates no user or grant; the printed start command (:97) passes --iris-password with no user, and `ivg server start` has no user option (iris_vector_graph/cli.py:419-434: IRIS_USERNAME defaults to _SYSTEM in cypher_api.py:170); the namespace step uses %SYS.Namespace over SQL/Native (:36-49), which ADMIN_GUIDE section 1 says cannot create a namespace; nothing reads ivg-config.yml. Not run: the installer targets a remote instance and would create a namespace (forbidden on the aud…
- Source severity S2, confidence high; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): Create the user and ADMIN_GUIDE section 3 grants in the installer and pass the user name, or rewrite deploy/README.md path 2.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1710"></a>
### The docker deploy recipe cannot build or log in as written

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [17.json](../../experiment/playbook-completion/findings/audit/17.json) (inspected `deploy/docker/compose.yml:1-40`; inspected `deploy/docker/cpf/merge.conf`)

Reproduced by: none (confirmed-source)

- Expected: deploy/README.md path 1 ('5 minutes').
- Observed at the pin: Confirmed in source: deploy/docker/compose.yml:19-22 builds from context ../.. with dockerfile Dockerfile, and the pin has no root Dockerfile (git ls-tree 3eaa79cf); IRIS_USERNAME ivg_service (:31) is created by nothing in the recipe or deploy/docker/cpf/merge.conf; the image is iris-community:latest (:3) while docker-compose.yml pins 2026.1. Not built: a docker build on the audit host is outside the lane's scope.
- Source severity S3, confidence high; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): Add the Dockerfile and a user-creation step (or use _SYSTEM for the demo and say so), and pin the image.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1711"></a>
### The deploy guide's SDK example reads a field IVGResult does not have

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `reproduced-test`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [17.json](../../experiment/playbook-completion/findings/audit/17.json) (check `c17-offline`; inspected `iris_vector_graph/result.py:9-16`)

Reproduced by: none (reproduced-test)

- Expected: deploy/README.md:73-79 iterates result.records.
- Observed at the pin: c17-offline: IVGResult fields ['bolt_column_types', 'columns', 'error', 'metadata', 'params', 'rows', 'sql']; result.records -> AttributeError: 'IVGResult' object has no attribute 'records'.
- Source severity S4, confidence high; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): Use result.rows/columns in the example, or add a records view.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1713"></a>
### STATUS_PARTS omits two parts that status() marks unknown

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `reproduced-test`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [17.json](../../experiment/playbook-completion/findings/audit/17.json) (check `c17-offline`; live `c17-live-engine`)

Reproduced by: none (reproduced-test)

- Expected: status.py:10-11 'What EngineStatus.unknown may name'.
- Observed at the pin: c17-offline: STATUS_PARTS ['graph', 'acceleration', 'sync', 'vector_index', 'fulltext_index', 'ivf_index', 'plaid_index', 'ledger']; admin.py appends ['adjacency', 'routines'] (admin.py:551, :752-753). Live status() on AUDITC: unknown = []; status() wrote 0 journal records (a reader).
- Source severity S4, confidence high; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): Add both names to STATUS_PARTS; test set(status.unknown) <= set(STATUS_PARTS).
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1714"></a>
### Two IVGClient calls and the async client do not map 401/403

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [17.json](../../experiment/playbook-completion/findings/audit/17.json) (live `c17-live-server`; inspected `iris_vector_graph/sdk.py:166-182, 254-281`; live `rx-live-17`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c17-live-server`, `rx-live-17`

- Expected: IVGClient._refused: '401 and 403 as IVGClientError, for every request (R225)' (sdk.py:195-201); IVGClientError docstring (sdk.py:22-25).
- Observed at the pin: Live (c17-live-server: Cypher HTTP server on 127.0.0.1:18750 with IVG_API_KEY set, client with a wrong key): {"AsyncIVGClient.execute_cypher": {"class": "HTTPStatusError", "is_IVGClientError": false}, "execute_cypher": {"class": "IVGClientError", "is_IVGClientError": true, "module": "iris_vector_graph.sdk", "msg": "Authentication failed \u2014 check api_key"}, "explain": {"class": "HTTPStatusError", "is_IVGClientError": false, "module": "httpx", "msg": "Client error '401 Unauthorized' for url 'http://127.0.0.1:18750/admin/explain'\nFor more information check: https://developer.mozilla.org/en-…
- Source severity S3, confidence high; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): Route those calls through _refused; unit tests with a 401 transport.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1804"></a>
### Native index values come back as text

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [18.json](../../experiment/playbook-completion/findings/audit/18.json) (live `c18-live-value-types`; live `c18-live-save-footprint`; inspected `iris_vector_graph/_engine/snapshot.py:1644-1646, 1679`; live `rx-dec-live-18`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c18-live-value-types`, `c18-live-save-footprint`, `rx-dec-live-18`

- Expected: spec 255 (a value comes back with the type it was written with); SNP-B2.21.
- Observed at the pin: Live (c18-live-value-types and c18-live-save-footprint): the archive line for the attribute is [{'k': ['edgeprop', 'c18g', '1700000000', 'c18:a', 'T', 'c18:b', 'amount'], 'v': '20'}]; get_edge_attrs before {'amount': 20} (int), after merge restore {'amount': '20'} (str).
- Source severity S3, confidence high; module 18; governing page here: `install.snapshot`.
- Remedy proposed by the playbook arm (not implemented): Archive the value's type (as the vector form does) or move values on the server.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-1807"></a>
### The HTTP snapshot endpoint can write two snapshots to one path

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [18.json](../../experiment/playbook-completion/findings/audit/18.json) (live `c18-live-http-endpoint`; inspected `iris_vector_graph/cypher_api.py:668-678`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c18-live-http-endpoint`

- Expected: Each save produces its own archive (POST /admin/snapshot answers the path it wrote).
- Observed at the pin: Live (c18-live-http-endpoint): two POSTs in one second answered [200, 200] with paths ['/home/ziniu_wu_g5labs_ai/runs/iris-vector-graph-playbook-uplift-20261113/completion-audit/breadth-c/18/archives/ivg_snapshot_1794611107.snapshot', '/home/ziniu_wu_g5labs_ai/runs/iris-vector-graph-playbook-uplift-20261113/completion-audit/breadth-c/18/archives/ivg_snapshot_1794611107.snapshot']; the file holds created_ts 1794611107088 of the second (save timestamps [1794611107076, 1794611107088]).
- Source severity S3, confidence high; module 18; governing page here: `install.snapshot`.
- Remedy proposed by the playbook arm (not implemented): Use a unique name (uuid or ms + counter) and refuse to overwrite.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0090"></a>
### Four unit tests never run: each is shadowed by a later method of the same name in its test class (lint warning F811)

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [zz-product-gates.json](../../experiment/playbook-completion/findings/audit/zz-product-gates.json) (run `pg-lint-ruff`; run `pg-lint-summary`; log `$RUN_DIR/product-gates/lint-r1/shadowed-collect.txt`; inspected `tests/unit/test_coverage_boost.py:234-256`; inspected `tests/unit/test_coverage_boost.py:307-335`; inspected `tests/unit/test_engine_deep.py:367-375`)

Reproduced by: none (confirmed-source)

- Expected: The product's lint gate is 'ruff check . - zero errors' (PRE_RELEASE_CHECKLIST.md:139-146; CONTRIBUTING.md:36-39 'Lint before you commit'), and its default rules include F811 (redefinition of an unused name). A test the suite contains is meant to run: CONTRIBUTING.md:175 ('Write the test before the code, and assert the answer'); pytest collects one function per name in a class, so a redefined test method replaces the earlier one.
- Observed at the pin: ruff 0.15.14 (pg-lint-ruff) reports F811 at tests/unit/test_coverage_boost.py:307 and :319 (TestBulkLoader.test_load_networkx_empty_graph and test_load_networkx_with_nodes_and_edges redefine :234 and :245) and at tests/unit/test_engine_deep.py:399 (TestEmbedNodesMethod.test_embed_nodes_progress_callback redefines :367) and :1139 (TestEngineEmbedTextMethod.test_embed_text_embedder_returns_list redefines :1132). pytest --collect-only on the three classes collects each of these names once, and the class attribute is the later definition in all four cases (co_firstlineno 307, 319, 399, 1139; $RUN…
- Source severity S4, confidence high; module 00; governing page here: `root, access.`.
- Remedy proposed by the playbook arm (not implemented): Give each pair distinct names (or merge them) so both bodies run, after deciding which assertions are wanted; select F811 as an error in a [tool.ruff] table so the lint gate fails on a shadowed test.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0301"></a>
### create_edge's adoption of a marked row runs after its transaction commits

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [03.json](../../experiment/playbook-completion/findings/audit/03.json) (inspected `iris_vector_graph/_engine/nodes_edges.py:1236-1252`)

Reproduced by: none (confirmed-source)

- Expected: create_edge docstring/ADR-0009: an explicit create over a marked row adopts it in the same write.
- Observed at the pin: When the guarded insert finds the triple, txn.commit() runs first and _adopt_temporal_row's UPDATE runs afterwards as its own statement (iris_vector_graph/_engine/nodes_edges.py:1236-1252); a temporal delete in between removes the marked row and the call answers False (duplicate) with no edge.
- Source severity S4, confidence medium; module 03; governing page here: `structure. / install.bulk_load`.
- Remedy proposed by the playbook arm (not implemented): Adopt inside the same transaction as the guarded insert.
- Reviewed-design control: `playbook-proofs-d1c` `control_fc0301_adopt_after_commit` fails where expected in this run ([receipt](results/playbook-proofs-d1c/20261115T035829Z-control_fc0301_adopt_after_commit/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1c/20261115T035754Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0302"></a>
### Property lookups with a limit return a storage-order subset

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [03.json](../../experiment/playbook-completion/findings/audit/03.json) (inspected `iris_vector_graph/_engine/nodes_edges.py:801-832`; inspected `iris_vector_graph/_engine/nodes_edges.py:892-915`; inspected `experiment/playbook-completion/models/breadth-a/storage-order/03.json`)

Reproduced by: none (confirmed-source)

- Expected: A capped lookup answers a defined subset (no stated order at the pin; ADR/USER_GUIDE silent).
- Observed at the pin: get_node_ids_by_property and get_property_pairs_like build SELECT TOP n ... with no ORDER BY (iris_vector_graph/_engine/nodes_edges.py:820, 904): with a limit the caller gets the first n rows in scan order.
- Source severity S4, confidence medium; module 03; governing page here: `structure. / install.bulk_load`.
- Remedy proposed by the playbook arm (not implemented): ORDER BY the subject (and value) under a limit, or document the arbitrary subset.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0340"></a>
### networkx-loader's --clear-existing deletes every graph's edges, labels and properties by raw SQL and leaves their nodes, temporal edges and vectors, with strict mode on

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (live `st-live-susp-loader-clear`; inspected `scripts/ingest/networkx_loader.py:264-283`; inspected `pyproject.toml:178`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `st-live-susp-loader-clear`

- Expected: A clear of graph data goes through the eraser, which removes a graph's rows and every derived store together (Graph.KG.Eraser, Graph.KG.GraphStores.Inventory; 12-erasure.md Scope); every content write is refused while ledger strict mode is on (11-ledger.md strict mode; WRT-T1.82 notes this loader's clear as built); one graph's operation does not touch another graph (SYS-I2).
- Observed at the pin: Live AUDITD (st-live-susp-loader-clear): NetworkXIRISLoader.import_graph(G, clear_existing=True) runs DELETE FROM Graph_KG.rdf_edges / rdf_labels / rdf_props with no graph filter (scripts/ingest/networkx_loader.py:279-283) and answers success with strict mode on. Afterwards graph sgB has no edges, labels or properties but keeps both node rows (get_node answers labels []), its temporal edge (window read 1) and the default graph's vector row remains; the default graph's earlier edges (including one the ledger committed), labels and properties are gone too, and no revision records the deletion.
- Source severity S3, confidence high; module 03; governing page here: `structure. / install.bulk_load`.
- Remedy proposed by the playbook arm (not implemented): Clear through the product's eraser (erase_graph per graph, or EraseAll for a whole-namespace reset) and refuse while strict mode is on; or remove the option.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0347"></a>
### A caller transaction with more than about 1,000 row writes to a table escalates to a table lock; every other process's write to that table, in any graph, then waits 10 s and fails with SQLCODE -110

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `intent-undecided`, not a native reproduction; severity is one level below the mapped Low.

**Policy-dependent:** the playbook arm classed the expected behavior as undecided intent.

Found by: playbook arm, [zz-orchestrator-steer7.json](../../experiment/playbook-completion/findings/audit/zz-orchestrator-steer7.json) (live `st-live-cap-batch`; inspected `iris_vector_graph/_engine/nodes_edges.py:1103`)

Reproduced by: none (intent-undecided)

- Expected: No IVG document states whether one graph's (or tenant's) transaction may block writes to other graphs: a search of docs/, specs/ and README.md at the pin for lock escalation, LockThreshold or escalat* finds no statement on it; the multi-graph documents promise isolation of answers (SYS-I2), not of availability. The product neither documents nor configures the IRIS lock-escalation threshold (the engine default; iris-contract treats lock escalation as an engine feature). Intent undecided.
- Observed at the pin: Live on AUDITD (structural lane, st-live-cap-batch, part '03 lock escalation'): with setAutoCommit(False), a caller transaction holding 200 create_node inserts leaves row locks only, and a second process's create_node succeeds in 0.03 s; holding 1,500 inserts, the lock table shows table locks ^t52S.XCFT.1 (nodes) and ^t52S.DMCe.1 (rdf_props) in mode X, and a second process's create_node of another node in another call waits 10.09 s and raises GraphWriteError SQLCODE -110 'nothing written' (its node is absent and the answer is consistent). Answers stay consistent; only availability across grap…
- Source severity S3, confidence high; module 03; governing page here: `structure. / install.bulk_load`.
- Remedy proposed by the playbook arm (not implemented): Decide whether large caller transactions may block other graphs' writers; if not, document a batch limit below the escalation threshold or configure the threshold for IVG's tables, and say so in the operations guide.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0351"></a>
### Explicit edge writers store the temporal marker {"temporal": true} given as a caller qualifier: the row is a marked row with no timestamp, and verify() does not see the relationship

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-writesets.json](../../experiment/playbook-completion/findings/audit/zz-writesets.json) (live `ws-live-ba-marker-qualifier`; inspected `iris_vector_graph/ledger/replay.py:613-620`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `ws-live-ba-marker-qualifier`

- Expected: docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md:38-42 (the marker distinguishes a temporal edge's derived row; a row an explicit write asserted is unmarked) and ADR-0009/TMP-B9.13 marked-needs-time (a marked row exists only while its triple has a timestamp); experiment/playbook-uplift/ontology/14-replay.md:51 (RPL-B7.1: verify names a change made outside the ledger an unrecorded write).
- Observed at the pin: Live in AUDITB (ws-live-ba-marker-qualifier), no temporal edge in the namespace: engine.store_edge, engine.create_edge and BulkLoader.load_edges (use_noindex False), each given qualifiers {'temporal': True}, wrote rows stored {"temporal": true}; their triples have no timestamp. verify() then reported diverges on the six endpoint nodes only: the three relationships are not among its differences, because read_canonical skips rows whose temporal qualifier is JSON true (iris_vector_graph/ledger/replay.py:617-620).
- Source severity S3, confidence high; module 03; governing page here: `structure. / install.bulk_load`.
- Remedy proposed by the playbook arm (not implemented): Reserve the marker key: refuse (or strip) a caller qualifier named 'temporal' in every explicit writer, as the ledger reserves 'id' and '__graph', so the marker can only come from the temporal side.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

Iteration 4 strengthening, not a new discovery: independent review of edge_acceptance found the caller marker input missing from its first transcription. The extended run/theorem_caller_marker_retained and 56 actual Python/SQLite cases now include temporal=True on insertion and repeated adoption: True/True, one row, final caller value and marker retained. The prior live verify omission remains inherited, not rerun. temporal.structural.adopt preserves ADR-0009's intended unmarked explicit edge and names this observed exception. No reserve/strip repair is implemented; the SQL/provider boundary remains conditional.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0401"></a>
### A writer stopped between its adjacency write and its generation step lets a reader cache a count that includes the undone edge

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `reproduced-model`, not a native reproduction; severity is one level below the mapped Medium.

Found by: playbook arm, [04.json](../../experiment/playbook-completion/findings/audit/04.json) (mc `breadth-a-mc-adj_degree-hd0401-writer-window`; inspected `iris_src/src/Graph/KG/Adjacency.cls:80-93`; inspected `iris_src/src/Graph/KG/Adj.cls:51-90`)

Reproduced by: none (reproduced-model)

- Expected: ADJ-I5.9 / ADR-0012: a cached degree carrying the current generation equals the committed count.
- Observed at the pin: Adjacency.Put writes ^KG('out')/('in') and only then $Increments ^KG('gen') (iris_src/src/Graph/KG/Adjacency.cls:87-89); Adj.Degree's probe can precede the writer's lock and its count can follow the out write (iris_src/src/Graph/KG/Adj.cls:68-80). A writer process stopped between the two (rolled back by IRIS, P-0001) leaves the generation unchanged, so the reader's store of the dirty count stays current.
- Source severity S2, confidence medium; module 04; governing page here: `structure.`.
- Remedy proposed by the playbook arm (not implemented): Step the generation before the out write (the reviewed adj_degree design), as well as never killing it (HD-0401).
- Reviewed-design control: `playbook-proofs-breadth` `control_fc0401_write_before_gen` fails where expected in this run ([receipt](results/playbook-proofs-breadth/20261115T035604Z-control_fc0401_write_before_gen/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-breadth/20261115T035528Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0402"></a>
### Two adjacency rebuilds can run at once

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `intent-undecided`, not a native reproduction; severity is one level below the mapped Medium.

**Policy-dependent:** the playbook arm classed the expected behavior as undecided intent.

Found by: playbook arm, [04.json](../../experiment/playbook-completion/findings/audit/04.json) (mc `breadth-a-mc-adj_rebuild_txn-as-built`; mc `breadth-a-mc-adj_rebuild_txn-reviewed`; inspected `iris_src/src/Graph/KG/Adjacency.cls:809-822`)

Reproduced by: none (intent-undecided)

- Expected: HD-0402 (assumption): at most one publishing rebuild per adjacency structure; the ADMIN_GUIDE names a single rebuild.
- Observed at the pin: Adjacency.BeginRebuild takes ^IVG.AdjW in shared mode (iris_src/src/Graph/KG/Adjacency.cls:814-822), which a second rebuild's shared request does not conflict with (P-0403).
- Source severity S2, confidence medium; module 04; governing page here: `structure.`.
- Remedy proposed by the playbook arm (not implemented): Take the rebuild lock exclusively (or a separate exclusive rebuild lock) and return busy to a second caller.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0415"></a>
### A refused erase or adjacency rebuild (writer lock not granted) still leaves writes behind: the graph's no-lock mark, source generations and ^KG("__version")

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-refusals.json](../../experiment/playbook-completion/findings/audit/zz-refusals.json) (live `rx-live-04`; inspected `iris_src/src/Graph/KG/Adjacency.cls:51-73`; inspected `iris_src/src/Graph/KG/Adjacency.cls:428-458`; inspected `iris_src/src/Graph/KG/Eraser.cls:225-235`; inspected `iris_src/src/Graph/KG/TraversalBuild.cls:30-40`; inspected `iris_src/src/Graph/KG/TraversalBuild.cls:155-163`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `rx-live-04`

- Expected: ADJ-X4.7 (ontology/04-adjacency.md, stated refusal): 'Removing a graph, removing all graphs and starting an adjacency rebuild are refused when the lock is not granted in 5 seconds. Nothing is written.' (implementing code iris_src/src/Graph/KG/Adjacency.cls:428-434, 452-458, 814-821; callers Eraser.cls:234-235, 788-789, TraversalBuild.cls:37-38). The erase contract: 'Erasure either completes or leaves the graph untouched' (iris_vector_graph/_engine/nodes_edges.py:1500-1507).
- Observed at the pin: rx-live-04 (AUDITE, journal oracle, a second process holding ^IVG.AdjW exclusively, shown in ^$LOCK): erase_graph('rx04g') raised 'Adjacency.RemoveGraph: the writer lock for graph rx04g was not granted in 5 seconds' after 15.07 s, erase_all() raised the RemoveAll message after 20.07 s, sync() raised the BeginRebuild message after 5.00 s. Rows and ^KG out entries were restored (5 nodes, 3 edges, 10 out entries before and after), but the journal shows net changes that the rollback did not take back: ^IVG.AdjNoLock("rx04g") (and ^IVG.AdjNoLock(0) for erase_all), ^KG("gen","rx04g","rx04:a"|"rx04:…
- Source severity S4, confidence high; module 04; governing page here: `structure.`.
- Remedy proposed by the playbook arm (not implemented): Either take the graph's (or the parent's) writer lock in the Eraser and in BuildKG before any row is deleted or any counter is bumped, so the 5-second refusal comes first and writes nothing; or state the refusal as it is built: the content is untouched, but the no-lock mark, the source generations and the version stamp move, and the refusal comes after 5 seconds per row. Clearing the no-lock mark is a separate decision (it disables the graph's degree cache until a rebuild).
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0440"></a>
### ^KG("prop") has no owning module, and four modules write it

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (check `st-check-own-census`; inspected `iris_src/src/Graph/KG/TraversalBuild.cls:60-67`; inspected `experiment/playbook-uplift/ontology/04-adjacency.md:49`)

Reproduced by: none (confirmed-source)

- Expected: Playbook §3.4 (experiment/playbook-uplift/verification-playbook.txt:32, 311): each store has a single write owner. ADJ-0 lists the stores the adjacency module owns (experiment/playbook-uplift/ontology/04-adjacency.md:49) and ^KG("prop") is not among them. No other Root or Scope line names it. GraphStores.Inventory lists it as graph content (iris_src/src/Graph/KG/GraphStores.cls:82).
- Observed at the pin: st-check-own-census: writers of ^KG("prop") are Graph.KG.TraversalBuild.BuildKG (iris_src/src/Graph/KG/TraversalBuild.cls:65, Kill ^KG("prop")), the 4.0.0 node-store step rekey_kg_node_stores (iris_vector_graph/migrations/kg_node_stores.py:176), Graph.KG.Eraser (EraseGraph :239, EraseIdSet :579, EraseAll :794, ForgetNodes :1327) and the restore paths (snapshot STORE_PLAN; Snapshot.ImportGlobals/SetNodeJSON, conditional). Readers include Graph.KG.Subgraph.
- Source severity S4, confidence high; module 04; governing page here: `structure.`.
- Remedy proposed by the playbook arm (not implemented): Name an owner for ^KG("prop") (the adjacency module's ADJ-0 list, or a module of its own) and route the other writers through it, or retire the store if nothing current needs it.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0502"></a>
### With temporal_structural_rows=True, create_edge_temporal raises 'Cursor closed' and writes no marked row under the driver the pin's uv.lock installs

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `reproduced-test`, not a native reproduction; severity is one level below the mapped Medium.

Found by: playbook arm, [zz-validation.json](../../experiment/playbook-completion/findings/audit/zz-validation.json) (run `val-e2e-1-c20`; run `val-rerun-3`; run `val-driver532-1`; run `val-driver540-1`; run `val-driver540-2`; inspected `iris_vector_graph/_engine/temporal.py:171-236`)

Reproduced by: none (reproduced-test)

- Expected: specs/246-alt-temporal-structural-row and tests/e2e/test_temporal_structural_row_live.py:53-90: with IRISGraphEngine(temporal_structural_rows=True), create_edge_temporal gives a temporal-only edge a marked structural row; TMP-B2.13 (that engine flag makes the Python side write and remove the marked row).
- Observed at the pin: ProgrammingError 'Cursor closed; DataRow is inaccessible' at iris_vector_graph/_engine/temporal.py:188-189 (_own_structural_row -> _select_structural_row fetchone) in e2e-1-c20 and in rerun-3 (fresh session, file first): deterministic; again in driver532-1 (2 cases). The same file passes under intersystems-irispython 5.4.0 (driver540-1, driver540-2).
- Source severity S2, confidence medium; module 05; governing page here: `temporal.`.
- Remedy proposed by the playbook arm (not implemented): As F-C1706 (driver floor); independently, read the structural-row probe before reusing its cursor.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0601"></a>
### A node re-enqueued while a worker holds its old text is marked DONE with the old vector

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `reproduced-model`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [06.json](../../experiment/playbook-completion/findings/audit/06.json) (mc `breadth-a-mc-vec_queue-as-built`; inspected `iris_src/src/Graph/KG/EmbedQueue.cls:35-60`)

Reproduced by: none (reproduced-model)

- Expected: enqueue_for_embedding docstring: re-enqueue overwrites, one entry per node (the latest request is the one to honour).
- Observed at the pin: ClaimPendingBatch is a plain scan with no claim state (iris_src/src/Graph/KG/EmbedQueue.cls:105-133); Enqueue overwrites a PENDING entry of the same graph (EmbedQueue.cls:44-58); the worker then sets DONE for the entry id with the vector of the text it read before.
- Source severity S3, confidence medium; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Version each entry (a sequence stamped at enqueue) and set DONE only if the version is unchanged; or claim atomically.
- Reviewed-design control: `playbook-proofs-d1b` `control_fc0601_no_version_check` fails where expected in this run ([receipt](results/playbook-proofs-d1b/20261115T035752Z-control_fc0601_no_version_check/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1b/20261115T035711Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0603"></a>
### kg_KNN_VEC's route guard picks an arbitrary registry row where Python applies a fixed preference

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [06.json](../../experiment/playbook-completion/findings/audit/06.json) (inspected `iris_src/src/Graph/KG/GraphStores.cls:300-312`; inspected `experiment/playbook-completion/models/breadth-a/storage-order/06.json`)

Reproduced by: none (confirmed-source)

- Expected: Route resolution is one rule across surfaces (embeddings.py:107-118 orders the candidates).
- Observed at the pin: VectorRouteGuard selects TOP 1 table_name over registry rows keyed (table_name, graph_id), so two node rows for one graph with no model key answer in scan order (iris_src/src/Graph/KG/GraphStores.cls:300-312).
- Source severity S4, confidence low; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Apply the Python preference in the guard (ORDER BY it) or refuse when more than one row qualifies.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0604"></a>
### The 4.0.0 vector migration takes an undeclared legacy table's width from an arbitrary row

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [06.json](../../experiment/playbook-completion/findings/audit/06.json) (inspected `iris_vector_graph/migrations/graph_scoped_embeddings.py:1265-1280`; inspected `experiment/playbook-completion/models/breadth-a/storage-order/06.json`)

Reproduced by: none (confirmed-source)

- Expected: Migration sizes a route from the data it moves; rows of several widths are a quarantine case.
- Observed at the pin: _Migrator._measured_width reads one stored vector with no ORDER BY when neither the table nor the registry declares a width (iris_vector_graph/migrations/graph_scoped_embeddings.py:1265-1280).
- Source severity S4, confidence low; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Measure every distinct width and refuse/quarantine a mixed table.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0605"></a>
### The embed queue serves PENDING entries in node-id order, so an entry can wait indefinitely

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [06.json](../../experiment/playbook-completion/findings/audit/06.json) (inspected `iris_src/src/Graph/KG/EmbedQueue.cls:112-133`; inspected `experiment/playbook-completion/models/breadth-a/storage-order/06.json`)

Reproduced by: none (confirmed-source)

- Expected: A queue that is worked repeatedly eventually serves every entry (progress; HD-0604 single consumer).
- Observed at the pin: ClaimPendingBatch and ProcessBatch take the first batchSize PENDING entries in reqId (= node id) collation order (iris_src/src/Graph/KG/EmbedQueue.cls:112-133, 258-268); under steady enqueueing of low-collating ids a high id is never reached.
- Source severity S4, confidence low; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Serve in arrival order (a sequence subscript) or round-robin from the last reqId.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0606"></a>
### The graph-scoped vector search exceeds spec 227 SC-010's 1.1x latency budget in every run

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `reproduced-test`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [zz-validation.json](../../experiment/playbook-completion/findings/audit/zz-validation.json) (run `val-perf-default-1`; run `val-perf-default-2`; run `val-perf-default-3`; run `val-perf-default-4`; run `val-perf-default-540-1`; run `val-perf-default-540-2`)

Reproduced by: none (reproduced-test)

- Expected: Spec 227 SC-010 as stated in tests/perf/test_227_single_graph_latency.py:1-5, 41-44 (a single-graph installation does not pay for routing: the graph-scoped kg_KNN_VEC stays within 1.10x of the 3.2.0 unscoped scan on the same 300 rows, interleaved medians).
- Observed at the pin: Scoped/unscoped median ratio 1.169, 1.145, 1.205, 1.124 under driver 5.3.2 (perf-default-1..4) and 1.149, 1.147 under 5.4.0 (perf-default-540-1/2): over the budget in 6 of 6 runs; about 0.25-0.3 ms per call.
- Source severity S4, confidence medium; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Profile the scoped statement against the unscoped one on a quiet machine; either close the gap or restate the budget.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0615"></a>
### VectorOptimizer.migrate_to_optimized cannot run on IRIS 2026.1: its CREATE INDEX IF NOT EXISTS ... AS HNSW is rejected, so it copies nothing and answers success False

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-refusals.json](../../experiment/playbook-completion/findings/audit/zz-refusals.json) (live `rx-live-06`; inspected `iris_vector_graph/vector_utils.py:194-199`; inspected `README.md:12-21`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `rx-live-06`

- Expected: README.md:12 and :21 ('Any IRIS 2025.1 or later works'); the method's own contract (iris_vector_graph/vector_utils.py:150-162: migrate the source table's vectors into kg_NodeEmbeddings_optimized and return migration results), and ADR-0006 as stated by VEC-X3.16 (the tool that fills the second legacy table checks the identity too).
- Observed at the pin: Live in AUDITE (IRIS 2026.1 Community Build 234U, run rx-live-06, case 'VectorOptimizer.migrate_to_optimized copies rx06-src vectors into a table claimed for rx06-dst -> refused by the identity check'): with one vector in kg_NodeEmbeddings, migrate_to_optimized() returned {'success': False, 'reason': 'Migration error: <SQL ERROR>; Details: [SQLCODE: <-1>:<Invalid SQL statement>] ... < ON expected, NOT found ^ CREATE INDEX IF NOT>'} and copied nothing (kg_NodeEmbeddings_optimized 0 rows; journal: no net change). The statement at vector_utils.py:194-199 runs before the copy loop (vector_utils.p…
- Source severity S4, confidence high; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Use a CREATE INDEX form every supported engine accepts (or probe for the index and skip the statement when it exists, as other setup code does), and run the identity check of F-0613 before the copy; add a live test of migrate_to_optimized on the oldest supported engine.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0640"></a>
### Dropping a neighborhood_vector index handle kills ^NKG("q") in the interned snapshot

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (check `st-check-own-census`; inspected `iris_vector_graph/_engine/vector.py:322-331`; inspected `iris_vector_graph/index_protocol.py:50`)

Reproduced by: none (confirmed-source)

- Expected: ^NKG is owned by the adjacency module (04-adjacency.md:49, ADJ-0 'Stores owned ... ^NKG') with the algorithms module (10-algorithms.md:5-9); VEC owns its own index globals (06-vectors.md:8-9). Playbook §3.4: single write owner.
- Observed at the pin: iris_vector_graph/_engine/vector.py:329-330 VectorMixin._neighborhood_index_drop runs Native API kill('^NKG', 'q') for any index name; index_protocol.py:50 routes the drop of a 'neighborhood_vector' index handle to it. The build and search of that index type are not implemented (vector.py:322-328 raise NotImplementedError). No other product site writes ^NKG("q") except Graph.KG.GraphIndex.DropNKG (Kill ^NKG) and the restore paths (st-check-own-census).
- Source severity S4, confidence high; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Give the neighborhood index a global of its own (or make the drop a no-op while the index type is unimplemented); never kill a sub-store of ^NKG from the vector module.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0642"></a>
### Vector top-k searches cut equal scores in storage order

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (live `st-live-perm-b`; inspected `iris_vector_graph/_engine/vector.py:569-600`; inspected `iris_vector_graph/schema.py:2436-2482`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `st-live-perm-b`

- Expected: Playbook principle 5 (never depend on storage or insertion order, only on keys and explicit orderings; verification-playbook.txt:33-34); HD-0603's working assumption, a ranking contract with defined tie behaviour (decisions.md:83-85, intent/HD-0603.md:37-41); kg_KNN_VEC returns 'up to k (node_id, cosine) pairs, highest first' (docs/API_REFERENCE.md:955-971) with no tie rule. F-C0703 is the same defect for text search.
- Observed at the pin: Live (st-live-perm-b, AUDITD): five nodes, three with the identical vector [1,0,0,0], stored in three insertion orders; kg_KNN_VEC('[1,0,0,0]', k=2) answered [pv:1, pv:2] (forward), [pv:3, pv:2] (reverse), [pv:2, pv:3] (shuffle): which tied node is cut depends on insertion order; with k=4 the same set comes back with the tied ranks reordered. Source: every vector top-k orders by score only (ORDER BY score DESC with no tie key: iris_vector_graph/_engine/vector.py:569-600 kg_KNN_VEC, :377-383 edge_vector_search, :819-829 the optimized path, :1264-1268 vector_search; the generated kg_KNN_VEC pro…
- Source severity S3, confidence high; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Order every vector top-k by a total key (score DESC, then node_id, or (s, p, o_id) for edges) in the SQL, the generated procedure and the adapter helpers, and state the tie rule in the API reference; a test that stores tied vectors in two orders and compares answers.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0670"></a>
### Two embed-queue workers can work the same entry at once: the single-consumer premise is neither enforced nor documented

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-semantics.json](../../experiment/playbook-completion/findings/audit/zz-semantics.json) (inspected `iris_src/src/Graph/KG/EmbedQueue.cls:112-134`; inspected `iris_src/src/Graph/KG/EmbedQueue.cls:258-268`; inspected `iris_vector_graph/_engine/embeddings.py:1912-1915`; live `intent-a-hd0604-queue-claim`; mc `sem-mc-queue-as-built`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `intent-a-hd0604-queue-claim`

- Expected: The embed queue is single-consumer by design (iris_src/src/Graph/KG/EmbedQueue.cls:22-25 'Single-processor', maintainer commit 5bb149ed; intent/HD-0604.md, status supported). Mechanism M-07 (semantics/mechanisms.json) law M07-L2: one worker per entry at a time, held by a claim or a lock, or refused.
- Observed at the pin: Neither worker claims an entry: ClaimPendingBatch is a read-only scan of PENDING entries (EmbedQueue.cls:112-134) and ProcessBatch tests status PENDING and works the entry (EmbedQueue.cls:258-268); the Python worker process_embed_queue calls ClaimPendingBatch with no lock (iris_vector_graph/_engine/embeddings.py:1912-1915). Both the IRIS task (Graph.KG.EmbedQueueTask) and process_embed_queue are public, and no user document states the single-worker rule (docs/API_REFERENCE.md:1387-1416). Two IRIS processes calling ClaimPendingBatch were handed the same 3 entries (probe intent-a-hd0604-queue-c…
- Source severity S3, confidence high; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Enforce one consumer per namespace (a lock held from claim to mark, or an atomic claim state per entry that a second worker skips), or document that only one of the two workers may run and refuse to start the second.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0690"></a>
### VectorOptimizer, a public class, hard-codes the Graph_KG schema, so in a namespace whose IVG Schema has another name it reads and writes the wrong tables

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [zz-product-gates.json](../../experiment/playbook-completion/findings/audit/zz-product-gates.json) (inspected `iris_vector_graph/vector_utils.py:22-26`; inspected `iris_vector_graph/vector_utils.py:46-60`; inspected `iris_vector_graph/__init__.py:94`; run `pg-style-review-r2`)

Reproduced by: none (confirmed-source)

- Expected: docs/adr/0016-one-ivg-schema-per-namespace.md:10-12: every SQL object IVG creates lives in one schema, the IVG Schema, default Graph_KG, and a user may choose another name (IRISGraphEngine(schema_prefix=...) or IVG_SCHEMA_PREFIX); iris_vector_graph/__init__.py:94 and :123 export VectorOptimizer as public API.
- Observed at the pin: Source at the pin: iris_vector_graph/vector_utils.py:22-26 sets _SCHEMA = "Graph_KG" (its comment: 'The embedding tables live in Graph_KG'); _qualify (:46-50) qualifies every table with it; the reads and writes at :295, :322 and :352 use it; VectorOptimizer.__init__ (:58-60) takes only a connection and never reads the namespace's recorded IVG Schema. The same comment (:22-25) says every method swallows a 'table not found' into a dict, so under another schema a call reports unavailability or does nothing rather than raising. Found by the style review round 2 (style-r2/STYLE-G2.md D-06-14, C-35…
- Source severity S4, confidence high; module 06; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Resolve the namespace's recorded IVG Schema (as the engine does through schema_name) or take the engine or the schema name as a constructor argument, and stop turning 'table not found' into an empty answer.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0703"></a>
### Text-search top-k answers and fused ranks depend on scan order

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [07.json](../../experiment/playbook-completion/findings/audit/07.json) (inspected `iris_vector_graph/_engine/vector.py:1041-1046`; inspected `iris_vector_graph/_engine/vector.py:979-1003`; inspected `iris_vector_graph/schema.py:2484-2578`; inspected `iris_vector_graph/text_search.py:111-233`; inspected `iris_vector_graph/_engine/vector.py:1438-1452`; live `b-07-f0709`)

Reproduced by: none (confirmed-source)

- Expected: Playbook principle 5 / gate 3.4-storage-order (never depend on storage or insertion order); decisions.md HD-0603/HD-0702 (a ranking contract with defined tie behaviour).
- Observed at the pin: Source (storage-order check $RUN_DIR/checks/storage-order.json, dispositions in modules/07.json storage_order): engine kg_TXT's LIKE fallback takes `SELECT TOP k d.id, 1.0 AS score ... WHERE <LIKE terms> AND <graph>` with no ORDER BY (iris_vector_graph/_engine/vector.py:1041-1046), so which k matching documents answer, and their ranks, are the scan's; this is the path that ran on AUDITB (every kg_TXT score 1.0 in b-07-f0709, iFind index unusable). The iFind path (vector.py:979-985, :998-1003), the generated kg_TXT procedure (iris_vector_graph/schema.py:2484-2520) and kg_RRF_FUSE's ROW_NUMBER(…
- Source severity S3, confidence high; module 07; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Order every top-k text query by a total key (score DESC, then the node id), give ROW_NUMBER() the same tie key, and break ties in the engine fusion by node id; a test that inserts tied documents in two orders and compares answers.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0716"></a>
### The engine's index registry mis-decodes BM25Index.List: an index name holding a comma or a leading/trailing space is split or trimmed, so the real index is missing and phantom names appear

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-refusals.json](../../experiment/playbook-completion/findings/audit/zz-refusals.json) (live `rx-dec-live-07`; check `rx-dec-map`; inspected `iris_src/src/Graph/KG/BM25Index.cls:626-633`; inspected `iris_vector_graph/_engine/vector.py:106-118`; inspected `iris_vector_graph/_validate.py:163-179`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `rx-dec-live-07`

- Expected: TXT-B9 (List names every BM25 index); TXT-B1.10 and the list_indexes/index docstrings (iris_vector_graph/_engine/vector.py:227-242, 260-266: the registry holds the indexes found when the engine starts; index(name) raises IndexNotFoundError for a name not in it). bm25_build and bm25_insert accept such names (BM25BuildInput only requires a non-empty name, iris_vector_graph/_validate.py:163-179; bm25_insert validates nothing).
- Observed at the pin: Live (rx-dec-live-07, case 'index names holding the separator or a leading space'): bm25_insert('rxd,comma', ...) and bm25_insert(' rxdspace', ...) both created indexes; Graph.KG.BM25Index.List answered ' rxdspace,rxd,comma,rxdidx,rxdins'; _build_index_registry (Native API path: split(',') then strip(), iris_vector_graph/_engine/vector.py:106-118) gave bm25 names ['comma', 'rxd', 'rxdidx', 'rxdins', 'rxdspace']: the indexes 'rxd,comma' and ' rxdspace' are missing and 'rxd', 'comma', 'rxdspace' are phantoms (bm25_info on them answers no index). A fresh engine's registry, which list_indexes, in…
- Source severity S4, confidence high; module 07; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Answer List as a JSON array (or $List) and decode it as such; or refuse ',' and surrounding spaces in index names in BM25BuildInput and bm25_insert.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0717"></a>
### BM25Index.Build and Info write the graph name into their JSON escaping only backslash and quote: a graph name with a control character makes bm25_build raise JSONDecodeError after the index was rebui…

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-refusals.json](../../experiment/playbook-completion/findings/audit/zz-refusals.json) (live `rx-dec-live-07`; check `rx-dec-map`; inspected `iris_src/src/Graph/KG/BM25Index.cls:172-174`; inspected `iris_src/src/Graph/KG/BM25Index.cls:608-614`; inspected `iris_vector_graph/_engine/vector.py:1777-1785`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `rx-dec-live-07`

- Expected: TXT-B1.10 / TXT-D9 (the index records its graph and the engine reads it back through Info); RFC 8259 escaping as CHANGELOG.md:463-467 states for the search answers (the jsonEsc helper, iris_src/src/Graph/KG/TraversalBFS.cls:15-33); graph names with control characters are refused elsewhere (validate_graph_name, iris_vector_graph/_validate.py:19-49; ADR-0003), but bm25_build does not call it.
- Observed at the pin: Live (rx-dec-live-07, case 'graph name with a tab'): bm25_build('rxdctl', ['name'], graph='rxd\tg') ran Build (^BM25Idx('rxdctl','cfg','graph') = 'rxd\tg' stored) and then raised JSONDecodeError 'Invalid control character'; Graph.KG.BM25Index.Info('rxdctl') answers '{"N":0,...,"graph":"rxd<TAB>g","schema":2}', which json.loads refuses; bm25_info raises JSONDecodeError and _index_graph swallows it and answers None (unknown). Build kills any index of that name before it writes (BM25Index.cls:99).
- Source severity S4, confidence high; module 07; governing page here: `search.`.
- Remedy proposed by the playbook arm (not implemented): Validate the graph with validate_graph_name in bm25_build before calling Build; escape with jsonEsc (or build the answer with %DynamicObject) in Build and Info.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0801"></a>
### A rolled-back Cypher edge write leaves the interned snapshot's counters raised

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-fc0801-rollback-nkg`; live `b-08-live-footprints`; inspected `iris_src/src/Graph/KG/Adjacency.cls:95-107`; inspected `iris_vector_graph/_engine/admin.py:808-816`; live `b-08-live-fc0801-rollback-nkg-rerun`; live `b-08-live-footprints-rerun`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-fc0801-rollback-nkg`, `b-08-live-footprints`, `b-08-live-fc0801-rollback-nkg-rerun`, `b-08-live-footprints-rerun`

- Expected: SYS-I8 (CONTEXT.md:109-120): a store built from others matches them or says it is out of date; CYP-I6.4: a failed write query takes back all of its steps.
- Observed at the pin: Live: with ^NKG built (engine.sync()), a query that creates edge b08_r1-[:B08NEW]->b08_r2 and then fails (duplicate literal edge) rolled back the row and the ^NKG(-1/-2) entries, but ^NKG(-3, idx(b08_r1)) went 1 -> 2 and ^NKG("$meta","edgeCount") 2 -> 3, with no stale mark (Adjacency.Put $Increments them, Adjacency.cls:95-107; $INCREMENT is not undone by TROLLBACK). The journal shows these records outside the transaction (b-08-live-footprints).
- Source severity S4, confidence medium; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Either keep the counters inside the transaction (SET from the merged degree, as BuildNKG's sweep does) or mark ^NKG stale when a writer's transaction rolls back; or document ^NKG(-3) and edgeCount as upper bounds (admin.py already treats edgeCount as an over-count).
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0802"></a>
### Schema procedures report one sampled element's property keys, chosen by storage order

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [08.json](../../experiment/playbook-completion/findings/audit/08.json) (live `b-08-live-storage-order`; inspected `iris_vector_graph/engine.py:1333-1400`; inspected `$RUN_DIR/checks/storage-order.json`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-08-live-storage-order`

- Expected: db.schema.nodeTypeProperties / relTypeProperties list the property keys a label's nodes / a type's relationships hold (Neo4j procedure contract the handlers emulate: iris_vector_graph/engine.py:1333-1400); gate §3.4 storage-order: no answer depends on storage or insertion order.
- Observed at the pin: Live (b-08-live-storage-order): two B08SA nodes inserted with keys {k2} then {k1}: nodeTypeProperties reported [id, k2] (k1 missing); two B08SR edges with qualifiers {qa} then {qb}: relTypeProperties reported [qa, weight] (qb missing). The handlers sample `SELECT TOP 1 rl.s ... WHERE rl.label = ?` (engine.py:1340) and `SELECT TOP 1 qualifiers ... WHERE p = ?` (engine.py:1382) with no ORDER BY, so the keys listed depend on which row storage order puts first.
- Source severity S3, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): List the distinct keys over every element of the label/type (SELECT DISTINCT key ... JOIN rdf_labels ... ORDER BY key, as apoc.meta.data does at engine.py:1624-1627), or document the procedures as a sample.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0840"></a>
### A Cypher DELETE deletes vector rows and reification rows itself, and only from the legacy vector table

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (check `st-check-own-census`; inspected `iris_vector_graph/cypher/translator.py:10740-10800`)

Reproduced by: none (confirmed-source)

- Expected: The vector tables are VEC's (06-vectors.md:5-8: the routed kg_emb_<hash> tables and the three legacy tables), reifications are INT's (15-integrations.md:5-10: reify_edge, get_reifications, delete_reification). The Cypher module's Scope names writes of the graph tables (08-cypher-sql.md:5, CYP-D1 :40: nodes, rdf_labels, rdf_props, rdf_edges). Playbook §3.4: single write owner.
- Observed at the pin: iris_vector_graph/cypher/translator.py translate_delete_clause adds DELETE statements on Graph_KG.kg_NodeEmbeddings (:10750 for reifier nodes, :10783 for deleted nodes) and on Graph_KG.rdf_reifications (:10757, :10796, :10800) to the write transaction (st-check-own-census sites). No statement names a routed kg_emb_/kg_eemb_ table.
- Source severity S3, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Delete a node's vectors and reification links through the owners' paths (the eraser's route-aware node erase, delete_reification), so every route is reached and one module keeps each store's rules.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0841"></a>
### Cypher range() with a step of 0 known only at run time answers [] instead of raising NumberOutOfRange

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (live `st-live-susp-range-step`; inspected `iris_src/src/Graph/KG/CypherFn.cls:255-257`; inspected `iris_vector_graph/cypher/translator.py:29055-29122`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `st-live-susp-range-step`

- Expected: openCypher: range() with a step of 0 raises ArgumentError NumberOutOfRange at run time (vendor/opencypher/tck/features/expressions/list/List11.feature:115-130); the translator itself refuses a literal step of 0 with that error (iris_vector_graph/cypher/translator.py:29055-29099).
- Observed at the pin: Live AUDITD (st-live-susp-range-step): RETURN range(1, 3, 0) raises ValueError 'range() step cannot be zero (NumberOutOfRange)'; UNWIND [0] AS s RETURN range(1, 3, s) and WITH 0 AS s RETURN range(1, 3, s) answer [] with no error (a run-time step of 1 answers [1, 2, 3]). The run-time path goes to CypherFn IVGRANGE, which returns "[]" for a step of 0 (iris_src/src/Graph/KG/CypherFn.cls:255-257).
- Source severity S4, confidence high; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Raise from IVGRANGE for a step of 0 (an SQL error the engine maps to NumberOutOfRange), as the literal path does.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0849"></a>
### A relationship property bound by a WITH before a literal-endpoint CREATE is stored as text that is not JSON

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (live `st-live-cypher-relprop`; inspected `iris_vector_graph/cypher/translator.py:10410-10432`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `st-live-cypher-relprop`

- Expected: rdf_edges.qualifiers holds a JSON object (iris_vector_graph/schema.py:40, %Library.DynamicObject; translator.py:466-469); docs/KNOWN_ISSUES.md:94-95 says a WITH's column is stored.
- Observed at the pin: Live AUDITD (st-live-cypher-relprop): WITH $v AS v CREATE (a:L {id: 'a5'})-[:R {q: v}]->(b:L {id: 'b5'}) with v = 'val' answers no error and stores the qualifiers text {"q": val} (unquoted), which json.loads rejects; MATCH ...-[r]->... RETURN r.q answers null.
- Source severity S3, confidence medium; module 08; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Quote stage-bound string values when the qualifiers JSON is assembled (json-encode the column, not splice it raw), or bind the whole object as one parameter.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0940"></a>
### IVG.CypherEngine.Scalar answers the caller's default when the read fails, so a failed COUNT reads as 0

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (inspected `iris_src/src/IVG/CypherEngine.cls:140-150`; live `st-live-susp-scalar`; inspected `iris_vector_graph/_engine/query.py:1745-1760`)

Reproduced by: none (confirmed-source)

- Expected: IVG.CypherEngine's contract is {columns, rows, error}: 'a bad query is an error value, not a throw' (iris_src/src/IVG/CypherEngine.cls:12, :110; QueryJson :97-127 passes the error); execute_cypher answers a failed read with IVGResult.error and no rows (iris_vector_graph/_engine/query.py:1755-1757).
- Observed at the pin: Inspected at the pin: Scalar (CypherEngine.cls:140-150) iterates r.rows and returns the default when there is none, without reading r.error. Live AUDITD (st-live-susp-scalar): execute_cypher('MATCH (n) RETURN count(n) / 0 AS c') answers error SQLCODE -149 and rows [] without raising, which is exactly the input on which Scalar returns its default ('0' for a count). Scalar itself could not be called here: the container's embedded Python lacks pydantic, so IVG.CypherEngine.Local() raises ModuleNotFoundError.
- Source severity S3, confidence high; module 09; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Raise (or return a distinguishable value) when r.error is set, as QueryJson reports it; document the behaviour.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C0948"></a>
### Compiled native plan classes have no bound: one class per plan shape accumulates until a deploy

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (inspected `iris_src/src/Graph/KG/Cypher/Gen.cls:163-230`; inspected `iris_vector_graph/schema.py:2939`)

Reproduced by: none (confirmed-source)

- Expected: Playbook §3.6 capacity: a stated bound or measured limit for every resource that grows with use (gate 3.6-capacity, open text 'a bound or a measured limit for compiled classes'); NAT-T5.2: one compiled plan serves every read of its shape.
- Observed at the pin: Inspected at the pin: Gen.Build compiles one class IVGC.P<hash> per plan-shape hash (iris_src/src/Graph/KG/Cypher/Gen.cls:163-221) and records it in ^IVG.CypherCompiled; the only removal is DropAll (Gen.cls:225-230), called by setup's deploy (iris_vector_graph/schema.py:2939). No count, size or age bound and no eviction exist, so the namespace gains one compiled class (and its routines) per distinct shape (labels, keys, hop structure) for as long as the namespace lives, within the 32-bit hash space that F-0901 shows can collide.
- Source severity S4, confidence medium; module 09; governing page here: `query.`.
- Remedy proposed by the playbook arm (not implemented): Bound the compiled-plan set (a count or LRU with DropAll of cold entries, or compile only shapes seen N times) and document the bound; or state that applications must not generate unbounded shapes.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1001"></a>
### triangle_count, a read, creates twelve SQL functions (DDL, class compile, commit) and rewrites the deploy record, with no Arno library

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [10.json](../../experiment/playbook-completion/findings/audit/10.json) (live `b-10-live-fp`; live `b-10-live-fp-detail`; inspected `iris_vector_graph/stores/iris_sql_store.py:3977-3988`; inspected `iris_vector_graph/stores/arno_bridge.py:658-694`; inspected `iris_vector_graph/stores/arno_bridge.py:106-136`; inspected `iris_vector_graph/stores/arno_bridge.py:360-378`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-10-live-fp`, `b-10-live-fp-detail`

- Expected: ALG-I6: a read algorithm changes no content; it may write only its own work areas and caches (experiment/playbook-uplift/ontology/10-algorithms.md ALG-I6). The routine record ^IVG.Deploy("routines") is setup's record of what it created (iris_vector_graph/routine_record.py:1-21).
- Observed at the pin: Live, journal oracle (b-10-live-fp): the first engine.triangle_count() in AUDITB (Arno library absent) wrote ['global:^IVG.Deploy', 'global:^oddDEP', 'global:^oddTSQL'] with no error, then answered from the LazyKG walk. The dictionary shows 16 classes Graph.KG.funcivgarnozf* created at that moment (b-10-live-fp-detail: TimeCreated $H 67888,3446-3447), i.e. the read path ran CREATE OR REPLACE FUNCTION for the $ZF wrappers and committed. A later triangle_count on a new connection rewrote ^IVG.Deploy("routines") again (1 journal record) although nothing was created. Source: execute_triangle_coun…
- Source severity S3, confidence high; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Create the $ZF wrappers in setup (initialize_schema) only, and have the read path probe availability without DDL (or check IsAvailable first); save the routine record only when something was created.
- Reviewed-design control: `playbook-proofs-d1e` `control_fc1001_read_creates_routines` fails where expected in this run ([receipt](results/playbook-proofs-d1e/20261115T035523Z-control_fc1001_read_creates_routines/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-d1e/20261115T035416Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1002"></a>
### Leiden on Zachary's karate club gives ARI 0.072 on the non-Arno path, against the product's 0.75 threshold

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `reproduced-test`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [zz-validation.json](../../experiment/playbook-completion/findings/audit/zz-validation.json) (run `val-e2e-1-c17`; run `val-rerun-2`; run `val-driver540-1`; run `val-driver540-2`; run `val-driver532-1`; inspected `tests/e2e/test_communities_e2e.py:78-110`)

Reproduced by: none (reproduced-test)

- Expected: Spec 163 FR-007 as stated and relaxed in tests/e2e/test_communities_e2e.py:78-110 (Leiden on the karate club, gamma 0.05, seed 42, ARI > 0.75 against the ground truth); tests/perf/test_leiden_four_way.py:12-15 (the Arno path and the non-Arno leidenalg path both give ARI 1.0 against the leidenalg reference).
- Observed at the pin: ARI = 0.072 in e2e-1-c17, rerun-2, driver540-1, driver540-2 and driver532-1: identical on both drivers (deterministic). The Community container has no Arno library, so the non-Arno fallback path ran (ALG-B6.2).
- Source severity S3, confidence medium; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Check the fallback path's partition against the leidenalg reference the perf test names, or state the fallback's quality separately.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1018"></a>
### The store's membership decoder refuses the Owner's components and label-propagation answers when a default-graph node is named 'components', 'communities' or 'largest' (read as an accelerated summary…

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-refusals.json](../../experiment/playbook-completion/findings/audit/zz-refusals.json) (live `rx-dec-live-10`; check `rx-dec-map`; inspected `iris_vector_graph/stores/iris_sql_store.py:636`; inspected `iris_vector_graph/stores/iris_sql_store.py:662-676`; inspected `iris_vector_graph/_engine/algorithms.py:816-828`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `rx-dec-live-10`

- Expected: ALG-B3 (connected components group the default graph's nodes; Graph.KG.Algorithms.WCCJson answers a node->component map, iris_src/src/Graph/KG/Algorithms.cls:6-90); the decoder's own contract (iris_vector_graph/stores/iris_sql_store.py:662-676 docstring: Graph.KG.Algorithms answers with a map, which is a readable shape; only the accelerated summary is refused); the spec-230 reference in the product's code comments (e.g. iris_vector_graph/_engine/admin.py:306; there is no specs/230* at the pin) (an unreadable shape raises, a readable one is read). A node id is any string; nothing reserves thes…
- Observed at the pin: Live (rx-dec-live-10, cases 'a default-graph node named largest'): default graph rxda->rxdb->rxdc->rxda, rxdc->largest, chain rxdx1..rxdx4, rxdd alone. Graph.KG.Algorithms.WCCJson answered the valid map {'largest':'largest','rxda':'largest',...,'rxdx4':'rxdx1'}; IRISGraphStore._execute_wcc answered rows [] with error "a summary, not a node→component_id map: it carries ['largest']" (AcceleratedSummaryShape from _membership_rows, iris_sql_store.py:670-675, _SUMMARY_KEYS iris_sql_store.py:636); CDLPJson likewise ('node→community_id'). kg_WCC and kg_CDLP still answered the wire map: on a store er…
- Source severity S4, confidence high; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Tell the shapes apart by producer (the Owner path never answers a summary) or by structure (a summary's 'components' is a number and 'largest' a list; a component label is a node id string), not by the presence of a key that can be a node id.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1040"></a>
### Graph.KG.ArnoAccel.BumpVersion moves the adjacency module's graph-version token

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (check `st-check-own-census`; inspected `iris_src/src/Graph/KG/ArnoAccel.cls:291-302`)

Reproduced by: none (confirmed-source)

- Expected: The graph-version token ^KG("__version") is in the adjacency module's owned stores (04-adjacency.md:49 ADJ-0; :64 ADJ-D15 'Each write that can change an answer moves it up'); ADR-0011 puts every rule that must hold on each adjacency write in Graph.KG.Adjacency (docs/adr/0011-the-adjacency-index-has-one-writer-module.md:12-30). Playbook §3.4: single write owner.
- Observed at the pin: iris_src/src/Graph/KG/ArnoAccel.cls:295-302 BumpVersion runs $Increment(^KG("__version")) and $Increment(^NKG("$meta","version")) outside Graph.KG.Adjacency (st-check-own-census: the only undeclared writer of ^KG("__version") besides the restore's _raise_kg_version, snapshot.py:57, covered by F-0404).
- Source severity S4, confidence high; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Bump the token through the adjacency module (one method that also keeps the degree generation rules), and name the Arno bridge as its caller.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1041"></a>
### The ^NKG centrality class methods called directly answer every graph merged; only the SQL functions refuse

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (live `st-live-susp-nkg-merged`; inspected `iris_src/src/Graph/KG/NKGAccel.cls:208-223`; inspected `iris_src/src/Graph/KG/NKGAccelCentrality.cls:4-10`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `st-live-susp-nkg-merged`

- Expected: An answer about a graph holds only that graph's data (SYS-I2); the product's own refusal says an algorithm over ^NKG with a named graph's edges present 'would be every graph's merged' (iris_src/src/Graph/KG/NKGAccel.cls:208-223, RefuseMergedGraphs; called by the kg_* SQL functions, iris_vector_graph/schema.py:2644-2665).
- Observed at the pin: Live AUDITD (st-live-susp-nkg-merged): with nd:1->nd:2 in the default graph and ng:1->ng:2->ng:3->ng:4 in graph sgN and ^NKG built by engine.sync(), Graph.KG.NKGAccelCentrality.ClosenessGlobal over the Native API answers all six nodes of both graphs as one graph (ng:1 1.833, ng:2 1.5, nd:1 1, ...) and BetweennessGlobal answers ng:2 and ng:3 of graph sgN; SQL Graph_KG.kg_Closeness refuses the same state; engine.closeness_centrality() answers nd:1 and nd:2 only. Inspected: EigenvectorGlobal, BetweennessGlobalParallel, BetweennessNeighborhood and ClosenessGlobalMSBFS (NKGAccelCentrality.cls:95,…
- Source severity S3, confidence high; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Call RefuseMergedGraphs inside the class methods (or key ^NKG by graph), so every entry point refuses or answers per graph.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1046"></a>
### The ^NKG traversal class methods called directly (k-hop neighbours, shortest path, distinct k-hop count) answer every graph merged

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (live `st-live-reads3-10`; control `st-control-reads3-selftest`; inspected `iris_src/src/Graph/KG/NKGAccelTraversal.cls:20-186`; inspected `iris_src/src/Graph/KG/NKGAccelTraversal.cls:366-553`; inspected `iris_src/src/Graph/KG/NKGAccel.cls:164-191`; inspected `iris_src/src/Graph/KG/NKGAccel.cls:213-223`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `st-live-reads3-10`

- Expected: An algorithm that takes no graph answers for the default graph alone and never mixes in a named graph's edges (ALG-I3, experiment/playbook-uplift/ontology/10-algorithms.md:45, citing docs/USER_GUIDE.md:767-775 and CONTEXT.md:97-101; SYS-I2). The product's own guard states why a reader of ^NKG cannot answer one graph: ^NKG holds every graph's edges with no graph key, and the ^NKG SQL functions refuse once a named graph has an edge so that plain SQL cannot get a mixed answer (iris_src/src/Graph/KG/NKGAccel.cls:213-223; ALG-B7, ALG-B7.2, 10-algorithms.md:129-131).
- Observed at the pin: Live, AUDITD (st-live-reads3-10, oracle self-tested by st-control-reads3-selftest): default graph a-R->b, b-R->c, a-S->c, c-R->a; the same ids with edges a-R->c, c-R->a, a-R->d, d-R->b, b-S->a written in graphs stg1 and stg2, then engine.sync() (^NKG merges them). Over the Native API, with no graph argument: Graph.KG.NKGAccelTraversal.KHopNeighbors('a', 2, 1000) and its NKGAccel wrapper, KHopJson and KHopNeighborsSorted list node d (which exists only in the named graphs) at dist 1, totalNodes 3 -> 4; ShortestPathNKG('a', 'd', 10) answers {"hops":1} instead of {"hops":-1}; CountDistinctKHop('a…
- Source severity S3, confidence high; module 10; governing page here: `algorithms.`.
- Remedy proposed by the playbook arm (not implemented): Give these readers the refusal the ^NKG SQL functions have (NKGAccel.RefuseMergedGraphs before reading ^NKG), or a graph argument that restricts the walk to one graph's edges; until then document that they answer every graph merged. Add a test with the same ids and edges in a named graph.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1101"></a>
### The stats row can count a commit its caller rolled back

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [11.json](../../experiment/playbook-completion/findings/audit/11.json) (live `b-11-live-f1102-txn`; mc `m11-stats-as-built-caller-txn`; inspected `iris_src/src/Graph/KG/LedgerStats.cls:51-88`; inspected `iris_src/src/Graph/KG/Ledger.cls:559-565`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `b-11-live-f1102-txn`

- Expected: LED-B13.2 (kept revisions are counted in the commit's own transaction), LED-B13.4; docs/ledger-prometheus-hook.md:16 (ledger_stats is the one to use for totals); stats head_seq mirrors the ledger head.
- Observed at the pin: Live AUDITB (b-11-live-f1102-txn): process A committed inside its own caller transaction (stats row saved: commits_ok 1->2, head_seq 1->2, row lock held to A's end); process B's Ledger.Count opened the row (dirty copy: commits_ok 2, head_seq 2), waited 2.5 s on the row lock; A rolled back (row restored to commits_ok 1, head_seq 1); B's %Save then wrote its whole dirty copy: final commits_ok 2 and head_seq 2 while the ledger head is 1 and only one commit is kept. Model m11-stats-as-built-caller-txn finds exactly this trace (read during the caller transaction, rollback, whole-row save).
- Source severity S3, confidence high; module 11; governing page here: `ledger.`.
- Remedy proposed by the playbook arm (not implemented): Same as F-1102: per-counter atomic increments (a refusal count must not write the commit count or head_seq), and derive head_seq from ^IVG.Ledger('head') at read time.
- Reviewed-design control: `playbook-proofs-breadth` `control_fc1101_stats_whole_row` fails where expected in this run ([receipt](results/playbook-proofs-breadth/20261115T035601Z-control_fc1101_stats_whole_row/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-breadth/20261115T035528Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1102"></a>
### With SynchCommit=0 (the tested setting, IRIS default) an acknowledged ledger commit can be lost on an instance crash

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `intent-undecided`, not a native reproduction; severity is one level below the mapped Medium.

**Policy-dependent:** the playbook arm classed the expected behavior as undecided intent.

Found by: playbook arm, [11-orchestrator.json](../../experiment/playbook-completion/findings/audit/11-orchestrator.json) (run `live-crash-world-r2`; live `live-crash-repeat-sc0`; live `live-crash-repeat-sc1`)

Reproduced by: none (intent-undecided)

- Expected: A revision the ledger reports as committed exists afterwards (spec 213: a revision exists iff its mutations are visible; clients treat the returned revision as durable). No IVG document states a durability premise or the IRIS setting it needs.
- Observed at the pin: Live: with iris.cpf SynchCommit=0 (the IRIS default: TCOMMIT returns before the journal is synced), a 36,000-operation commit acknowledged as seq 3 was entirely absent after a SIGKILL of the container and journal recovery; the ledger stayed consistent (head, revision rows, statement/tuple map, verify equal) and a retry with the same idempotency key committed once. The in-flight trial recovered all-or-nothing.
- Source severity S2, confidence high; module 11; governing page here: `ledger.`.
- Remedy proposed by the playbook arm (not implemented): Document the durability premise (SynchCommit=1 or a journal flush before acknowledging, or say that acknowledged revisions can be lost on a crash and that an idempotent retry recovers them), and consider checking the setting at enable().
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1106"></a>
### Relationships the wire schema admits are refused once s+p+o exceed an undocumented key-length limit

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [correspondence.json](../../experiment/playbook-completion/findings/audit/correspondence.json) (live `corr-capacity`; inspected `iris_vector_graph/schema.py:33-45`; inspected `specs/213-graph-revision-ledger/contracts/changeset.schema.json:7-10`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `corr-capacity`

- Expected: specs/213-graph-revision-ledger/contracts/changeset.schema.json:7-8 (NodeId maxLength 256, Name128 maxLength 128 for the tuple's s, o and p); Graph_KG.rdf_edges declares s, o_id VARCHAR(256) and p VARCHAR(128) (iris_vector_graph/schema.py:37-39).
- Observed at the pin: Live AUDITC (corr-capacity): a commit of create_relationship with s = o of 194 characters and p of 97 commits; with s = o of 195 and p of 97 (and with 256/128) it is refused with failed_op 'insert relationship failed: ... <SUBSCRIPT>%SQLInsert+21^Graph.KG.rdfedges.1 ^t52S.BWr6.3(...)': the table's own unique index u_spo_graph_ekey (schema.py:44) cannot hold the key. The refusal is clean (nothing written). The ledger's tuple index ^IVG.Ledger("tuple", s, p, o, graphKey) would overflow one character later (s = o = 195, p = 97 still fits a read; read-only probe), so widening the table index woul…
- Source severity S3, confidence high; module 11; governing page here: `ledger.`.
- Remedy proposed by the playbook arm (not implemented): Document one combined key-length limit for (s, p, o, graph) that every store holding the tuple as subscripts can carry (rdf_edges' unique index, ^KG("out"/"in"), ^IVG.Ledger("tuple")), validate it before the transaction (client and ApplyAll) with its own error, and align the wire schema; or key the indexes by a hash of long values.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1107"></a>
### The commit does not enforce the wire schema's length limits, and reports violations as a ledger inconsistency

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [correspondence.json](../../experiment/playbook-completion/findings/audit/correspondence.json) (live `corr-capacity`; inspected `iris_src/src/Graph/KG/Ledger.cls:451-528`; inspected `iris_vector_graph/ledger/errors.py:87-88`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `corr-capacity`

- Expected: changeset.schema.json: message maxLength 4000 (:189), idempotency_key maxLength 256 (:193), qualifier values maxLength 4000 (:46); errors.py:87-88 LedgerInconsistencyError 'The ledger's own structures disagree with each other'; CommitError codes (changeset.schema.json:288-311).
- Observed at the pin: Live AUDITC (corr-capacity), every refusal clean (no state change): idempotency_key of 257 characters -> inconsistent 'revision row save failed: ERROR #7201 Datatype value ...' (LedgerRevision MAXLEN, Ledger.cls:554-555); of 600 -> inconsistent '<SUBSCRIPT> CommitInTxn+35^Graph.KG.Ledger.1 ^IVG.Ledger("idem",...)' (Ledger.cls:457); message of 4,001 -> inconsistent #7201; a qualifier value of 4,000,000 -> inconsistent '<MAXSTRING> %GetNext+30^%Iterator.Object.1'. Each surfaces in Python as LedgerInconsistencyError. Conversely a qualifier value of 1,000,000 characters (schema maximum 4000) is a…
- Source severity S3, confidence high; module 11; governing page here: `ledger.`.
- Remedy proposed by the playbook arm (not implemented): Validate the changeset and its metadata against the published limits before TSTART (and in Changeset.validate), refusing with a validation code (failed_op with op_index, or a new code) instead of 'inconsistent'; keep 'inconsistent' for disagreements of the ledger's own structures.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1108"></a>
### A detach delete assigns statement ids to unrecorded incident edges in storage order

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `intent-undecided`, not a native reproduction; severity is one level below the mapped Low.

**Policy-dependent:** the playbook arm classed the expected behavior as undecided intent.

Found by: playbook arm, [correspondence.json](../../experiment/playbook-completion/findings/audit/correspondence.json) (live `corr-row-permutation`; inspected `iris_src/src/Graph/KG/LedgerApply.cls:384-410`)

Reproduced by: none (intent-undecided)

- Expected: specs/213 FR-011 (detach cascades in statement-id order); playbook §3.4 storage-order / §3.6 row-permutation: results must not depend on row insertion order.
- Observed at the pin: Live AUDITC (corr-row-permutation): a recorded node pm|1 with three unrecorded (ledger-bypassing) edges to pm|a, pm|b, pm|c inserted in the orders abc, cba, bca; delete_node(pm|1, detach) records the same three delete_rel records each time, but statement ids 1, 2, 3 go to the edges in insertion order (LedgerApply.cls:385-398: incident edges from a SELECT without ORDER BY; AllocStmt in cursor order). Recorded content without the ids is identical.
- Source severity S4, confidence high; module 11; governing page here: `ledger.`.
- Remedy proposed by the playbook arm (not implemented): Order the incident-edge SELECT by (s, p, o_id, graph_id) before allocating ids, if statement identity is meant to be a function of the logical state.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1109"></a>
### Every node_not_found refusal is decoded as a create_relationship failure with relationship-only advice

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [correspondence.json](../../experiment/playbook-completion/findings/audit/correspondence.json) (trace `corr-trace-ext`; inspected `iris_vector_graph/ledger/errors.py:91-128`; inspected `iris_vector_graph/ledger/errors.py:175-199`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM)

- Expected: errors.py:91-92 (NodeNotFoundError: 'A relationship operation references a node that does not exist'); the server emits node_not_found also for add_label, remove_label, set_prop, remove_prop and delete_node (LedgerApply.cls:290, 299, 315, 325, 380) besides create_rel (:459-460); FR-008 asks for the failing op's index and reason.
- Observed at the pin: Live AUDITC (corr-trace-ext, op commit-failed-op): a changeset whose add_label names a missing node is refused with failed_op/node_not_found; the client raises NodeNotFoundError 'create_relationship failed: node 'nope|1' does not exist. Add upsert_node('nope|1') to the changeset, or set auto_stub_missing_nodes=True' (errors.py:120-125, from_commit_error :187-193). op_index and reason are kept; the message names the wrong operation and advice (auto_stub_missing_nodes only stubs relationship endpoints, changeset.py:205-209) that cannot fix a node operation.
- Source severity S4, confidence high; module 11; governing page here: `ledger.`.
- Remedy proposed by the playbook arm (not implemented): Build the message from the op index and the server's reason (or narrow NodeNotFoundError to create_rel/upsert_rel refusals).
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1110"></a>
### After a BUILD INDEX, a duplicate-key insert raises <LIST ERROR>, which the duplicate check does not recognise

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [zz-contract.json](../../experiment/playbook-completion/findings/audit/zz-contract.json) (run `env-ext-r6`)

Reproduced by: none (confirmed-source)

- Expected: `_write_txn.is_duplicate` (iris_vector_graph/_write_txn.py:46-49) treats a unique-key refusal as 'already there'.
- Observed at the pin: IRIS contract clause X-NOINDEX (round r6, scratch tables only): after BUILD INDEX a duplicate insert through DB-API raises DataError <LIST ERROR> instead of SQLCODE -119; is_duplicate matches only 'unique' or '-119'. Not reproduced on the product's own tables.
- Source severity S3, confidence medium; module 11; governing page here: `ledger.`.
- Remedy proposed by the playbook arm (not implemented): Recognise the <LIST ERROR> form in is_duplicate (or check the key explicitly) after index rebuilds.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1202"></a>
### EraseGraph's adjacency kill can drop the adjacency of an edge committed after its row delete

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `reproduced-model`, not a native reproduction; severity is one level below the mapped Medium.

Found by: playbook arm, [12.json](../../experiment/playbook-completion/findings/audit/12.json) (run `core-m2-as-built-F1201-adjacency`)

Reproduced by: none (reproduced-model)

- Expected: Adjacency (^KG out/in) matches live edge rows (ADR-0012, ERS-B1.1).
- Observed at the pin: Model only (core M2, 6 steps), same root cause as F-1201 (no serialization with commits). In the 8 native F-1201 trials the adjacency survived (kg_out_G_defined), so this interleaving was not hit live.
- Source severity S2, confidence medium; module 12; governing page here: `erasure.`.
- Remedy proposed by the playbook arm (not implemented): As F-1201.
- Reviewed-design control: `playbook-proofs-pa3` `control_fc1202_erase_unguarded` fails where expected in this run ([receipt](results/playbook-proofs-pa3/20261115T040804Z-control_fc1202_erase_unguarded/receipt.json)); the reviewed design verifies ([baseline](results/playbook-proofs-pa3/20261115T041009Z-baseline/receipt.json)). That is a model fact about the reviewed design, not a product property.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1204"></a>
### EraseNodes fails on a prefix longer than the subscript limit instead of erasing nothing

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [correspondence.json](../../experiment/playbook-completion/findings/audit/correspondence.json) (live `corr-capacity`; inspected `iris_src/src/Graph/KG/Eraser.cls:322-351`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `corr-capacity`

- Expected: Eraser.cls:307-321 (EraseNodes removes every node whose id starts with the prefix; 0 means nothing matched); the redaction of the same target answers complete with nothing matched.
- Observed at the pin: Live AUDITC (corr-capacity): EraseNodes("", <10,000 characters>) throws 'erase failed on cursor ivgErasePrefix with SQLCODE -400 (<SUBSCRIPT> ... ^t52S.XCFT.4(...))' (Eraser.cls:333-339); nothing changes. LedgerRedact.Redact with a 10,000-character prefix answers ok.
- Source severity S4, confidence high; module 12; governing page here: `erasure.`.
- Remedy proposed by the playbook arm (not implemented): Return 0 for a prefix longer than any node_id can be (256), or validate the prefix length up front.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1302"></a>
### Final trusts a scan that ended before it took the lock

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `reproduced-model`, not a native reproduction; severity is one level below the mapped Medium.

Found by: playbook arm, [13.json](../../experiment/playbook-completion/findings/audit/13.json) (run `core-m2-as-built-F1302-commit-after-check`)

Reproduced by: none (reproduced-model)

- Expected: A complete receipt means no record of the target remains unredacted.
- Observed at the pin: Model only (core M2, 20 steps; low likelihood): a record committed and then erased between the last batch and Final stays unredacted while the call reports complete.
- Source severity S2, confidence medium; module 13; governing page here: `redaction.`.
- Remedy proposed by the playbook arm (not implemented): Have Final check that the scan reached the head it holds the lock on, or rescan the tail under the lock.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1305"></a>
### Graph_KG.embedding_quarantine keeps a tenant's node ids and vectors through every erase and redaction, and the receipt does not say so

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [followup.json](../../experiment/playbook-completion/findings/audit/followup.json) (run `fu-r01b-quarantine-erase-plan`; inspected `iris_src/src/Graph/KG/Eraser.cls:300-302`; inspected `iris_src/src/Graph/KG/Eraser.cls:752-758`; inspected `iris_vector_graph/_engine/schema.py:205-227`; inspected `iris_vector_graph/migrations/graph_scoped_embeddings.py:955-968`; inspected `iris_src/src/Graph/KG/LedgerRedact.cls:504-508`)

Reproduced by: none (confirmed-source)

- Expected: specs/256-ledger-tenant-redaction/spec.md:42-44 and 127-128 (FR-008 reach statement); docs/adr/0013-redaction-removes-content-from-history.md:47-48 ('Together they cover everything IVG can reach'). By design the quarantine is evidence, not content: iris_src/src/Graph/KG/Eraser.cls:300-302 and 756-758 (FR-039, FR-040); iris_vector_graph/_engine/schema.py:205-227 (node_id, vector, metadata, no graph).
- Observed at the pin: \Source: neither EraseGraph, EraseNodes/EraseIdSet nor EraseAll names Graph_KG.embedding_quarantine except in comments (Eraser.cls:300, 756); LedgerRedact.cls never names it; the receipt (LedgerRedact.cls:504-508) does not mention it; engine.list_quarantine() (schema.py:1913) returns its rows with node_id. The pin's own upstream tests that pin this behaviour pass here (fu-r01b-quarantine-erase-plan: tests/unit/test_227_erase_plan.py, 3 quarantine tests). Not built live: the only writer of a quarantine row is the 4.0.0 migration from a 3.2.0 install (iris_vector_graph/migrations/graph_scoped_em…
- Source severity S3, confidence high; module 13; governing page here: `redaction.`.
- Remedy proposed by the playbook arm (not implemented): Keep the by-design behaviour but state it: the receipt's out_of_reach (and ADR-0013) should name embedding_quarantine rows, or the redaction should report the count of quarantined rows whose node_id matches the target's prefix.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1309"></a>
### The redaction's audit revision stores an unsalted SHA-256 of the tenant's name: a guessed tenant is confirmable from history

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [followup.json](../../experiment/playbook-completion/findings/audit/followup.json) (check `fu-r10-target-digest`; live `fu-r01a-snapshot-copies`; inspected `iris_src/src/Graph/KG/LedgerRedact.cls:56-59`; inspected `iris_src/src/Graph/KG/LedgerRedact.cls:418-441`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `fu-r01a-snapshot-copies`

- Expected: specs/256-ledger-tenant-redaction/spec.md:152-154 (Decision 1: the audit holds 'no entity id, attribute, value or free text from the target'); docs/adr/0013-redaction-removes-content-from-history.md:16 ('holds counts and sha256(graph NUL match) instead of the target's name. Nothing in it comes from the target'); spec.md:66-67 (US2: 'nobody can recover the content from the digest') against ADR-0013:43, 49 (record digests unsalted, 'can be confirmed by guessing').
- Observed at the pin: Live digest (fu-r01a-snapshot-copies) and computation (fu-r10-target-digest): the redaction revision's source.target_sha256, readable through history() (which does not check the marker) and Graph_KG.ledger_revisions.source, is 5693ca28...c58d = SHA-256('' NUL 'fu1|') = Graph.KG.LedgerRedact.TargetDigest('', 'fu1|') (LedgerRedact.cls:56-59, :200, :433, :487). A 200,006-name dictionary confirmed exactly 'fu1' in 0.13 s (about 1.5 million guesses a second on one Python core). The marker and the receipt carry the same digest.
- Source severity S3, confidence high; module 13; governing page here: `redaction.`.
- Remedy proposed by the playbook arm (not implemented): Decide the intent (maintainer question): if the audit must not identify the tenant, store a keyed digest (HMAC with a namespace secret) or nothing; if confirmability is accepted, say so in ADR-0013 (as it already does for record digests) and drop 'Nothing in it comes from the target'. Reconcile spec 256 US2 with ADR-0013 Consequences.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1501"></a>
### Schedule/Unschedule change the Task Manager task and the fhir_graphs task_id in separate, untransacted steps

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [15.json](../../experiment/playbook-completion/findings/audit/15.json) (inspected `iris_src/src/Graph/KG/FHIRGraph.cls:667-741`)

Reproduced by: none (confirmed-source)

- Expected: SYS-I4 (a command that writes to more than one store writes all or none); INT-F9 (one sync task per graph); HD-1502 reviewed design needs an unschedule that verifiably stops refills.
- Observed at the pin: \Source: Schedule saves the %SYS.Task (FHIRGraph.cls:701, %Save) and only then records its id with a separate autocommit UPDATE Graph_KG.fhir_graphs SET task_id (:703); Unschedule deletes the task (:726) and then clears task_id (:729). No TSTART covers either pair. If the UPDATE fails after Schedule's %Save, a running sync task exists that fhir_graphs does not name: Unschedule then reports success without removing it, and the next Schedule creates a second task. Not run live: HS.FHIRServer.* classes and the HS_FHIRServer SQL schema (an IRIS for Health FHIR repository) are absent on IRIS Commun…
- Source severity S3, confidence medium; module 15; governing page here: `fhir.`.
- Remedy proposed by the playbook arm (not implemented): Wrap the task change and the task_id update in one transaction (IRIS transactions span the IRISSYS and namespace databases), or make Unschedule find tasks by (TaskClass, NameSpace, GraphId) rather than by the stored id.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1502"></a>
### delete_node removes the reifier nodes of the node's edges in a second transaction

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [15.json](../../experiment/playbook-completion/findings/audit/15.json) (live `c15-live-reify`; inspected `iris_vector_graph/_engine/nodes_edges.py:2176-2199`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c15-live-reify`

- Expected: SYS-I4 (all or none across stores); INT-E1.9 (deleting a node also deletes the reifier nodes of its edges).
- Observed at the pin: Live (c15-live-reify, delete_node_parity): delete_node('c15:a2', graph='c15g1b') journaled two outermost transactions: the node, its edge and the rdf_reifications row in the first, the reifier node c15:reif2 (default graph) in the second. _delete_in_scope (nodes_edges.py:2176-2199) deletes reifiers after the node delete commits and, on failure, raises GraphWriteError 'the node is deleted; the reifier nodes of its edges (n) are not'.
- Source severity S3, confidence high; module 15; governing page here: `fhir.`.
- Remedy proposed by the playbook arm (not implemented): Delete the reifier nodes inside the same transaction as the node and its edges.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1540"></a>
### The FHIR graph build writes the adjacency label index and the vector and document rows itself

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (check `st-check-own-census`; inspected `iris_src/src/Graph/KG/FHIRGraph.cls:2470-2620`)

Reproduced by: none (confirmed-source)

- Expected: ^KG("label") is the adjacency module's (03-writes.md:43 WRT-D7 'owned by the adjacency module'; 04-adjacency.md:49), written by Graph.KG.Adjacency.PutLabel/RemoveLabel, which move the graph-version token; the label functional index calls them on each rdf_labels row (iris_vector_graph/schema.py:780, iris_src/src/Graph/KG/LabelIndex.cls:10-27). Vector and document rows are VEC's (06-vectors.md:5-8; 07-text-search.md:9-10). INT-F1.17 (15-integrations.md:94) says that with the functional index declared the row writes keep ^KG and the class skips its own Put/Remove.
- Observed at the pin: iris_src/src/Graph/KG/FHIRGraph.cls sets ^KG("label",...) directly in SyncProps (:2566, unconditionally) and EnsureNode (:2616, unconditionally) and kills it in SyncProps (:2560) and DropNode (:2475-2477, :2491) when not indexed; DropNode deletes Graph_KG.docs, kg_NodeEmbeddings, kg_NodeEmbeddings_optimized and every routed node table (:2481-2489) and DeleteEdge deletes kg_EdgeEmbeddings and every routed edge table (:2588-2594) by its own SQL (st-check-own-census).
- Source severity S3, confidence medium; module 15; governing page here: `fhir.`.
- Remedy proposed by the playbook arm (not implemented): Write labels only through the rows (indexed) or Graph.KG.Adjacency.PutLabel/RemoveLabel (not indexed), and delete a node's vectors and documents through the eraser's node path, so each store keeps one writer and the version token moves.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1548"></a>
### Deleting a relationship with delete_edge or Cypher DELETE leaves its reification rows pointing at an edge that no longer exists

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (live `st-live-fk`; inspected `iris_vector_graph/schema.py:514-519`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `st-live-fk`

- Expected: A reification belongs to its edge: rdf_reifications(reifier_id, edge_id) names the reified edge (iris_vector_graph/schema.py:514-519); delete_node removes the reifiers of a node's edges (INT-E1.9, F-C1502) and erase_graph deletes the rdf_reifications rows of the graph's edges (F-1502 observed), so a deleted edge has no reification.
- Observed at the pin: Live AUDITD (st-live-fk): two edges reified (fr:r1, fr:r2); delete_edge('fr:1','R','fr:2') and MATCH (a {id:'fr:2'})-[r:R]->(b {id:'fr:3'}) DELETE r both answer success, and afterwards both rdf_reifications rows remain with edge_ids 6101 and 6102 that no rdf_edges row has; get_reifications(6101) still answers fr:r1 with its properties. rdf_reifications.edge_id has no foreign key (schema.py:514-519).
- Source severity S3, confidence high; module 15; governing page here: `fhir.`.
- Remedy proposed by the playbook arm (not implemented): Delete (or refuse to delete before removing) the edge's rdf_reifications rows and reifier nodes in delete_edge and in the Cypher relationship DELETE, in the same transaction, as delete_node intends; or declare a foreign key with ON DELETE CASCADE.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1549"></a>
### A one-edge PROV lookup fails once the default graph's temporal history no longer fits one IRIS string

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (live `st-live-cap-batch-r2`; live `st-live-cap-batch`; inspected `iris_vector_graph/_engine/prov.py:181-221`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `st-live-cap-batch-r2`, `st-live-cap-batch`

- Expected: prov_as_dict maps one temporal edge (iris_vector_graph/_engine/prov.py:86-105) and prov_export_from_cypher the edges of the nodes a query returns (prov.py:141-175); INT-V1.6 (15-integrations.md:283) bounds only a window export ('Export a big history window by window'); module 05 has a paged reader for any window (iter_edges_in_window, spec 255).
- Observed at the pin: Live AUDITD (st-live-cap-batch-r2): with 40,000 default-graph temporal edges whose JSON passes 3,641,144 characters, prov_as_dict of one edge and prov_export_from_cypher of one node both raise RuntimeError '<MAXSTRING>QueryWindow+27^Graph.KG.TemporalIndex.1', as does prov_export of the whole window; a one-second window exports. Both helpers read the whole default-graph window with QueryWindow(0, 9999999999) and filter in Python (prov.py:181-221). With short ids (st-live-cap-batch, window under the limit) all succeed.
- Source severity S3, confidence high; module 15; governing page here: `fhir.`.
- Remedy proposed by the playbook arm (not implemented): Read through the paged cursor (iter_edges_in_window with source or sources filters) or QueryWindow narrowed to the edge's timestamp and source, so a lookup's cost depends on its own edges, not on the whole history.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1602"></a>
### Server and connection failures are reported as client syntax errors

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [16.json](../../experiment/playbook-completion/findings/audit/16.json) (probe `c16-s6-status-maps`; inspected `iris_vector_graph/cypher_api.py:367-460`; inspected `iris_vector_graph/bolt_server.py:614-622`)

Reproduced by: none (confirmed-source)

- Expected: SYS-I9 (every refusal says why); Neo4j status codes distinguish ClientError (caller's fault, not retried) from TransientError/DatabaseError (P-1612); HTTP 4xx means the request was wrong.
- Observed at the pin: Live (c16-s6-status-maps, stub engine, no IRIS): a lost IRIS connection answers HTTP 400 on /api/cypher and /db/{db}/query/v2, 400 + 'Neo.ClientError.Statement.SyntaxError' on /db/neo4j/tx/commit, and a Bolt FAILURE 'Neo.ClientError.Statement.SyntaxError' (classification ClientError, not retryable) both when the session's engine cannot connect and when a query's connection fails. Source: cypher_api.py:367-376, :396-400, :451-460; bolt_server.py:617-622 map every exception to those codes. Also: the sample API answers an unknown function as 400 UNDEFINED_VARIABLE (c16-s3, api/routers/cypher.py:…
- Source severity S3, confidence high; module 16; governing page here: `access.`.
- Remedy proposed by the playbook arm (not implemented): Map connection/database failures to 5xx / Neo.TransientError.* (or DatabaseError) and keep SyntaxError for parse failures.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1640"></a>
### The stdio MCP server's LoadGraph always reports 0 nodes and 0 edges loaded

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (live `st-live-susp-mcp-load`; inspected `scripts/mcp/ivg_mcp_server.py:102-128`; inspected `iris_vector_graph/_engine/snapshot.py:547-552`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `st-live-susp-mcp-load`

- Expected: LoadGraph 'Returns node and edge counts' (scripts/mcp/ivg_mcp_server.py:52-58).
- Observed at the pin: Live AUDITD (st-live-susp-mcp-load): call_tool('LoadGraph') on a GraphML file of 3 nodes and 2 edges (the mcp transport replaced by a stand-in, the module's connection set to AUDITD) answers nodesLoaded 0, edgesLoaded 0, buildKGCompleted true, while 3 node rows and 2 edge rows were written. The handler reads stats['nodes_created'] / ['edges_created'] (ivg_mcp_server.py:124-125); engine.load_networkx returns nodes, edges, skipped_nodes, skipped_edges (snapshot.py:547-552, observed live).
- Source severity S4, confidence high; module 16; governing page here: `access.`.
- Remedy proposed by the playbook arm (not implemented): Read stats['nodes'] and stats['edges'] (and the OBO loader's keys).
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1641"></a>
### The generated GraphQL server's Node.properties always answers an empty list

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (live `st-live-susp-gql-props`; inspected `iris_vector_graph/gql/schema.py:30-37`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `st-live-susp-gql-props`

- Expected: The Node interface's properties field lists the node's key/value pairs (iris_vector_graph/gql/schema.py:13-16, 30-37); the generic node type returns them (gql/resolvers.py:205-207).
- Observed at the pin: Live AUDITD (st-live-susp-gql-props): node gq:1 with label Gqx and properties name=alpha, colour=red; create_app over the engine, queried in-process: node(id: "gq:1") answers properties [] while the typed fields name 'alpha' and colour 'red' come back; nodes(label: "Gqx") answers properties [] too. Node.properties returns [] (schema.py:35-37) and every generated type inherits it.
- Source severity S3, confidence high; module 16; governing page here: `access.`.
- Remedy proposed by the playbook arm (not implemented): Resolve properties from the node's stored properties (as GenericNode does), or drop the field from the interface.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1642"></a>
### The generated GraphQL server pages nodes(label) over an unordered id list

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (live `st-live-so-confirm`; live `st-live-perm-c`; inspected `iris_vector_graph/gql/resolvers.py:32-46`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `st-live-so-confirm`, `st-live-perm-c`

- Expected: A paged field (nodes(label, limit, offset), iris_vector_graph/gql/schema.py:150-156 -> gql/resolvers.py:32) is meant to page a defined sequence, so that consecutive pages partition the answer whatever the storage order (playbook principle 5, verification-playbook.txt:33-34). The sample API's own nodes field orders before it pages (api/gql/core/resolvers.py:159-177).
- Observed at the pin: Live (st-live-so-confirm P16, AUDITD): five nodes of label Q written forward and in reverse; resolve_nodes(label='Q', limit=2, offset=0|2|4) answered pages [so16:0, so16:1] [so16:2, so16:3] [so16:4] forward and [so16:4, so16:3] [so16:2, so16:1] [so16:0] reverse; the permutation run (st-live-perm-c, module 16) shows three different first pages for three orders, while the sample API's ORDER BY created_at pages held. Source: SELECT s FROM rdf_labels WHERE label = ? with no ORDER BY, then all_ids[offset : offset + limit] (iris_vector_graph/gql/resolvers.py:32-46).
- Source severity S4, confidence high; module 16; governing page here: `access.`.
- Remedy proposed by the playbook arm (not implemented): ORDER BY s (and the graph) in the statement and page in SQL (TOP/offset over the ordered rows), scoped to one graph (F-1603).
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1701"></a>
### Two declared console scripts cannot run from an install

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [17.json](../../experiment/playbook-completion/findings/audit/17.json) (check `c17-offline`; inspected `pyproject.toml:176-196`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM)

- Expected: pyproject.toml:176-179 declares console scripts run-tests and networkx-loader beside ivg.
- Observed at the pin: c17-offline: run-tests -> {'exit': 1, 'stderr_tail': [' from scripts.test import main', "ModuleNotFoundError: No module named 'scripts.test'"]}; scripts/test.py tracked at the pin: False; the wheel packages only ['iris_vector_graph'] (pyproject.toml wheel config), so scripts.ingest.networkx_loader is absent from a wheel install (it resolved here only because the venv's editable install puts a source checkout on sys.path).
- Source severity S4, confidence high; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): Drop the two entries or ship the modules they name.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1702"></a>
### `ivg server start --workers N` (N > 1) exits without serving

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [17.json](../../experiment/playbook-completion/findings/audit/17.json) (live `c17-live-server-workers`; inspected `iris_vector_graph/cli.py:427-441`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c17-live-server-workers`

- Expected: docs/ADMIN_API.md:20 documents --workers; OPS-B1.12 (uvicorn.run(cypher_api.app, host, port, workers)).
- Observed at the pin: Live (c17-live-server-workers): `ivg server start --host 127.0.0.1 --port 18799 --workers 2` printed uvicorn's 'You must pass the application as an import string to enable reload or workers' and exited 1; cli.py:437-438 passes the app object.
- Source severity S3, confidence high; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): Pass the import string 'iris_vector_graph.cypher_api:app' to uvicorn.run, or drop the option; the product's own N-process path then exists for the 1-vs-N validation.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1704"></a>
### The L2 metric of the vector helpers fails on IRIS Community 2026.1

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [17.json](../../experiment/playbook-completion/findings/audit/17.json) (live `c17-live-vec`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `c17-live-vec`

- Expected: dbapi_utils.vector_similarity_search and create_hnsw_index document metric 'L2' beside COSINE and DOT (dbapi_utils.py:238-275, :170-204); IRIS Community 2026.1 is the exercised target (P-1701).
- Observed at the pin: Live (c17-live-vec, IRIS for UNIX (Ubuntu Server LTS for x86-64 Containers) 2026.1 (Build 234U) Fri Mar 27 2026 14:07:14 EDT): vector_similarity_search(metric='L2') -> ProgrammingError: <SQL ERROR>; Details: [SQLCODE: <-359>:<SQL Function (function stored procedure) not found>] [Location: <Prepare>] [%msg: < User defined SQL function 'SQLUSER.VECTOR_L2' does not exist>]; raw VECTOR_L2 -> ProgrammingError: <SQL ERROR>; Details: [SQLCODE: <-359>:<SQL Function (function stored procedure) not found>] [Location: <Prepare>] [%msg: < User defined SQL function 'SQLUSER.VECTOR_L2' does not exist>]; CO…
- Source severity S4, confidence high; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): Refuse metric='L2' on servers without VECTOR_L2 (or compute it), and say which metrics each edition supports.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1705"></a>
### The product's transaction premise 'measured on IRIS 2026.3 (driver 5.4.0)' is false on 2026.1 and 2026.2 with either driver: the driver is not its cause

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-versions.json](../../experiment/playbook-completion/findings/audit/zz-versions.json) (live `ver-e261-d532`; live `ver-e261-d540`; live `ver-e262-d532`; live `ver-e262-d540`; live `ver-e262-d532-full`; live `ver-sql-entry-probe-e261`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `ver-e261-d532`, `ver-e261-d540`, `ver-e262-d532`, `ver-e262-d540`

- Expected: iris_vector_graph/_write_txn.py:15-17 and iris_src/src/Graph/KG/Txn.cls:7-8 state, as a measured fact, that SQL COMMIT and ROLLBACK end every level and START TRANSACTION inside a transaction does nothing; docs/ADMIN_GUIDE.md:19-28 recommends 2026.1 or later and runs 2026.1 Community on every push.
- Observed at the pin: Live, same 113 cases (cases.py --seed 20261114) on four engine x driver cells: SQL COMMIT and ROLLBACK at $TLEVEL 2 end ONE level (2 -> 1) and START TRANSACTION inside a level does nothing, on IRIS 2026.1 (Build 234U) and 2026.2 (Build 221U) Community, with intersystems-irispython 5.3.2 and 5.4.0 (ver-e261-d532, ver-e261-d540, ver-e262-d532, ver-e262-d540: the premise mutants sql-commit-ends-all / sql-rollback-ends-all killed by 2 and 4 cases in every cell), through both client entry points iris.dbapi.connect and iris.connect (ver-sql-entry-probe-e261, ver-sql-entry-probe-e262). The full cont…
- Source severity S3, confidence high; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): State the premise per version (one level on 2026.1/2026.2; every level on 2026.3 if re-measured there), or drop it: the shape it justifies (Txn_Begin/End/Undo = TSTART/TCOMMIT/TROLLBACK 1) is right on every version measured. Re-measure on 2026.3 and record the build.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1706"></a>
### The pin's uv.lock installs intersystems-irispython 5.3.2, on which IVG answers scores as Decimal or text, raises on duplicate rows and refuses list parameters

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `reproduced-test`, not a native reproduction; severity is one level below the mapped Medium.

Found by: playbook arm, [zz-validation.json](../../experiment/playbook-completion/findings/audit/zz-validation.json) (run `val-driver532-1`; run `val-driver540-1`; run `val-driver540-2`; run `val-driver540-oracle-1`; run `val-oracle-1-c00`; run `val-gated-532-1`)

Reproduced by: none (reproduced-test)

- Expected: pyproject.toml:42 asks only intersystems-iris>=1.0.0 and uv.lock:1358-1371 resolves it to intersystems-iris 5.3.3 / intersystems-irispython 5.3.2, so a uv sync of the pin installs this driver. Against it: OPS-B5.4 and iris_vector_graph/stores/iris_sql_store.py:1215-1220 (write_nodes / write_edges: 'A duplicate row is skipped'); the product's own tests and oracle: tests/e2e/test_460_proc_yield_alias_e2e.py:108 (a YIELDed score is int/float), the r306 algorithm oracle (scores equal the float reference), tests/e2e/test_460_r284_retrieve_rrf_score_e2e.py (retrieve() rrf_score is a float); the ope…
- Observed at the pin: Driver A/B, alternating in time over the same files (validation/SUITES.md 'Driver A/B'). Under 5.3.2 (the uv.lock version): (a) Cypher CALL ivg.* YIELD scores come back as decimal.Decimal and retrieve()'s rrf_score as str ('.032522474881015332737'): 252 type-only failures in the r306 oracle (oracle-1), 289 in the gated subset, 2/2 rrf cases; (b) a duplicate INSERT inside write_txn surfaces as '<LIST ERROR> Incorrect list format, unsupported type for IRISList' instead of SQLCODE -119, so write_nodes / write_edges / create_edge raise GraphWriteError and write nothing (is_duplicate, iris_vector_…
- Source severity S2, confidence high; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): Set a driver floor in pyproject.toml (the version CI tests, at least 5.4.0) and refresh uv.lock; type numeric result columns of Cypher procedure YIELDs and retrieve() explicitly; recognise the driver's duplicate-row error in is_duplicate.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1715"></a>
### On a namespace that refuses the engine, close does not run: IRISGraphEngine has no close() and its store's close() is refused

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-refusals.json](../../experiment/playbook-completion/findings/audit/zz-refusals.json) (live `rx-live-17`; inspected `iris_vector_graph/schema_name.py:376-377`; inspected `iris_vector_graph/engine.py:384-390`; inspected `iris_vector_graph/engine.py:414-416`; inspected `iris_vector_graph/stores/iris_sql_store.py:4278-4279`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `rx-live-17`

- Expected: OPS-X2.1.1 (ontology/17-operations.md): 'On a namespace that refuses the engine, most calls are refused. Setup, status, legacy removal and close still run.' Source of the exemption: EXEMPT_METHODS = {'initialize_schema', 'status', 'remove_legacy_objects', 'close'} (iris_vector_graph/schema_name.py:376-377, 'What a namespace that refuses an engine still lets it do').
- Observed at the pin: Live (rx-live-17, AUDITE recording Graph_KG): IRISGraphEngine(conn, schema_prefix='RX17ALT') is refused at first access; create_node, get_node, node_count, execute_cypher and the store's get_nodes raise IVGSchemaError, status() and remove_legacy_objects(dry_run=True) run, but hasattr(engine, 'close') is False (the exemption names a method the engine does not define), and engine._store.close() raises IVGSchemaError: the store's methods are guarded with no exemptions (engine.py:388-390 guard_methods(self._store)), so its close (a no-op, iris_sql_store.py:4278-4279) is refused. The refusal itsel…
- Source severity S4, confidence high; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): Either give the engine a close() (releasing what it holds) and exempt the store's close from the guard, or drop 'close' from EXEMPT_METHODS and from the stated behaviour.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1716"></a>
### kill_query cannot end any process on IRIS 2026.1: %SYSTEM.SYS.KillProcess is not an SQL function (SQLCODE -359), so every call answers False

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-refusals.json](../../experiment/playbook-completion/findings/audit/zz-refusals.json) (live `rx-live-17`; inspected `iris_vector_graph/_engine/admin.py:957-969`; inspected `docs/API_REFERENCE.md:2686-2692`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `rx-live-17`

- Expected: docs/API_REFERENCE.md:2686-2692 'kill_query(query_id) ... End the IRIS process with ID query_id (an id from list_active_queries)'; iris_vector_graph/_engine/admin.py:957-962 'Calls %SYSTEM.SYS.KillProcess through SQL. True when the statement ran ...; False when it failed'.
- Observed at the pin: Live (rx-live-17, AUDITE, IRIS 2026.1 Community Build 234U, driver 5.3.2): engine.kill_query on the lane's own scratch process (pid 140416, an ordinary killable client process) answered False and logged 'kill_query 140416 failed: [SQLCODE: <-359>:<SQL Function (function stored procedure) not found>] ... User defined SQL function %SYSTEM.SYS.KILLPROCESS does not exist'; the process answered %SYSTEM.SYS.ProcessID afterwards (still alive). The same -359 for pid 999999999. The statement 'SELECT %SYSTEM.SYS.KillProcess(?)' (admin.py:964-965) cannot run, so the documented operation never ends a pro…
- Source severity S3, confidence high; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): Call the class method through the Native API (classMethodValue('%SYSTEM.SYS', 'KillProcess', pid)) or through a projected stored procedure, check its return status, and answer False (or raise) when the process was not ended; add a live test that ends a scratch process.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1740"></a>
### The SQL adapter's node delete removes document and reification rows by its own SQL

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (check `st-check-own-census`; inspected `iris_vector_graph/stores/iris_sql_store.py:1363-1418`)

Reproduced by: none (confirmed-source)

- Expected: OPS-B5.6 (17-operations.md:189): delete nodes removes ids 'with their labels, properties, edges and vectors' (no documents or reification links named). Documents are VEC's (07-text-search.md:9-10), reifications INT's (15-integrations.md:5-10). Playbook §3.4: single write owner.
- Observed at the pin: iris_vector_graph/stores/iris_sql_store.py _delete_nodes_sql deletes Graph_KG.rdf_reifications rows (:1387) and Graph_KG.docs rows (:1403) itself, besides the content and legacy vector tables OPS-B5.6 names (st-check-own-census).
- Source severity S4, confidence high; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): Delete through the owners (the eraser's node erase, which already reaches documents and routes) and state in OPS-B5.6 what the delete removes.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1741"></a>
### The enterprise web gateway recipe lets any address manage the gateway and connects to IRIS as _SYSTEM with the stock password

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (inspected `docker/enterprise/webgateway-init.sh:12-31`; inspected `docker/enterprise/docker-compose-2026.yml:1-45`; inspected `docker/enterprise/merge.cpf:1-5`)

Reproduced by: none (confirmed-source)

- Expected: A deploy recipe does not expose an administration surface to every address with known credentials (deploy/README.md and docs/ADMIN_GUIDE.md treat credentials and network exposure as operator settings; F-1710 for the other docker recipe).
- Observed at the pin: Inspected at the pin (not deployed): docker/enterprise/webgateway-init.sh:12-31 writes CSP.ini with System_Manager=*.*.*.* (the gateway's management pages from any client address) and [LOCAL] Username=_SYSTEM, Password=]]]U1lT (the gateway's obfuscated form of 'SYS'); docker/enterprise/docker-compose-2026.yml:28-29 publishes the gateway on host port 64780 and :5-6 IRIS's superserver on 4972, both on every host interface; merge.cpf:4 keeps _SYSTEM's password from ever expiring or being forced to change. Only .iris-dev.toml refers to the recipe.
- Source severity S3, confidence high; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): Restrict System_Manager to the loopback/container network, bind published ports to 127.0.0.1, take the IRIS credentials from a secret and require a password change, and label the recipe as a local developer setup.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1742"></a>
### IRISGraphStore.query_nodes(limit=n) cuts an unordered node scan

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

**Suspected** here: the playbook arm's disposition is `confirmed-source`, not a native reproduction; severity is one level below the mapped Low.

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (inspected `iris_vector_graph/stores/iris_sql_store.py:1162-1200`; check `st-check-so-gate`; live `st-live-so-17b`)

Reproduced by: none (confirmed-source)

- Expected: A capped read answers a defined subset (playbook principle 5; store_protocol.py:10-11 states no order); the same lane's F-C0302 is the engine counterpart.
- Observed at the pin: Source at the pin: without a label, query_nodes runs SELECT node_id FROM <schema>.nodes FETCH FIRST n ROWS ONLY with no ORDER BY (iris_vector_graph/stores/iris_sql_store.py:1176-1181), so the n nodes answered (and then filtered by property) are the first n in scan order. The product call itself cannot be observed answering here: it kills the client process first (F-C1743, st-live-so-confirm P17). The same unordered prefix in the TOP spelling, sent by a harness cursor over the same data, answered [so17:0, so17:1] forward and [so17:4, so17:3] reverse (st-live-so-17b).
- Source severity S4, confidence high; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): ORDER BY node_id (and graph) before the cut, with TOP n rather than FETCH FIRST (see F-C1743), and scope the read to one graph (F-1701).
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1795"></a>
### When its dedicated Native API connection is refused (licence units exhausted), the engine silently uses the caller's connection and retries the refused connect on every native call

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-orchestrator-steer7.json](../../experiment/playbook-completion/findings/audit/zz-orchestrator-steer7.json) (live `live-licence-world`; inspected `iris_vector_graph/engine.py:1894-1942`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `live-licence-world`

- Expected: iris_vector_graph/engine.py:1895-1898: the dedicated connection exists because mixing iris.createIRIS() and cursor DDL on the same connection 'permanently corrupts the IRIS Python driver's parameter binding state'; :1913-1918: the caller's connection is used only 'when [the credentials] are not known'. The product's convention against swallowed failures (C-17, product-gates/STYLE.md) asks that a failed step be reported.
- Observed at the pin: Live (live-licence-world, AUDITE, IRIS Community 2026.1, 8 licence units): an engine from IRISGraphEngine.from_connect, then 7 idle connections taking every free unit (the 8th refused 'Unable to allocate a license'); the engine's first native call (ledger enable/commit) could not open its dedicated connection; engine._native_conn stayed None and the calls ran on the caller's own connection (engine.py:1940-1941, except Exception: return _create(self.conn)), with no warning or error logged. Each later native call tried the refused connect again: two 150- and 3-operation commits took 2,062.6 ms…
- Source severity S4, confidence high; module 17; governing page here: `install. / access. / adapters.`.
- Remedy proposed by the playbook arm (not implemented): Log the refused dedicated connect and either raise or record the degraded mode once (do not retry the connect on every native call); if sharing the caller's connection is unsafe, as the comment says, refuse instead of falling back.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

<a id="F-C1848"></a>
### save_snapshot and restore_snapshot hold the whole archive in client memory: about 11 MB per 1,000 edges, 190 times the archive's size

Severity: Low · Decision: Open

Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)

Found by: playbook arm, [zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json) (live `st-live-cap-snapshot-mem`; inspected `iris_vector_graph/_engine/snapshot.py:864-900`; inspected `iris_vector_graph/_engine/snapshot.py:1107-1112`)

Reproduced by: playbook arm, live on its IRIS (x86_64 VM): `st-live-cap-snapshot-mem`

- Expected: Playbook §3.6 capacity: a stated bound or measured limit for every resource that grows with the data. save_snapshot documents 'the whole database's graph content' (iris_vector_graph/_engine/snapshot.py:803-815) and states no memory bound; no IVG document gives one.
- Observed at the pin: Live AUDITD (st-live-cap-snapshot-mem): peak client allocation of save_snapshot 21.3 / 89.2 / 356.1 MB and of restore_snapshot 21.8 / 84.6 / 338.4 MB for 2,000 / 8,000 / 32,000 edges (archives of 0.12 / 0.48 / 1.9 MB); save takes 7 / 28 / 108 s. save_snapshot fetches every row of every table with fetchall() and builds every NDJSON member as a list in memory before writing (snapshot.py:864-900); restore reads every member into memory (snapshot.py:1107-1112). By extrapolation a namespace of a million edges needs about 11 GB on the client; nothing refuses or streams.
- Source severity S3, confidence high; module 18; governing page here: `install.snapshot`.
- Remedy proposed by the playbook arm (not implemented): Stream each table into its ZIP member with a server-side cursor in pages (zipfile open(..., 'w') per member) and restore member by member in batches; until then document the memory needed per edge and a size above which snapshots are refused.
- Not yet compared with the guidance arm's entries beyond the confirmed merges.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

## Observations and documentation drift

<a id="bug-tmp-012"></a>
### Without the adjacency index, deleting a temporal edge removes the adjacency of an explicit edge on the same triple

Severity: Low

Run: Uplift 2026-11-13

Found by: review R2-data R1-13 and expectation E8.

In a namespace without the adjacency index, `TemporalIndex.DeleteTemporalEdge` calls `Adjacency.Remove` with no row check, unlike the purge's `RetractTemporalShadows`, which keeps a triple that has any row; the Python docstring documents this as a "KNOWN AMBIGUITY" (`temporal.py:364-369`). `temporal.structural.end` ("An unmarked structural edge stays") holds only with the index declared. Legacy installs only; recorded as an observation. Governing statement: [temporal.structural.end](../ontology/features/temporal.g5.md#temporal.structural.end).

<a id="bug-plt-022"></a>
### The schema check is skipped silently for logins without global access and for non-IRIS connections

Severity: Low

Run: Uplift 2026-11-13

Found by: `witness_unreadable_record_skips_the_check` (W-S4) in [platform.rs](models/platform/platform.rs) ([prove receipt](results/platform/20261114T002651Z-prove/receipt.json)); A-platform F-S8.

The first-access check logs and skips when the record cannot be read (`engine.py:1862-1866`; `schema_name.py:270-283`), so a pooled or proxied DB-API connection gets no check. This is documented (ADMIN_GUIDE:515-518): an accepted design gap, recorded so the premise P-NATIVE-READABLE is visible. Governing statement: [install.schema.refusal](../ontology/concepts/install.g5.md#install.schema.refusal).

<a id="bug-plt-023"></a>
### The IVF SQL function checks the privilege on a table that the index's own global names

Severity: Low

Run: Uplift 2026-11-13

Found by: A-platform F-H8 (sub-reader a).

`kg_IVF` checks SELECT on the table named by `^IVF(name,"cfg","table")` (`SqlProcs.cls:141`), which a role able to write the database can redirect to a table it may read. Observation only; the consequence was not traced. Governing statement: [access.iris_boundary](../ontology/concepts/access.g5.md#access.iris_boundary).

<a id="bug-doc-001"></a>
### The OpsReview brief's one-call redaction recipe never reaches the tenant's node records

Severity: Low

Run: Uplift 2026-11-13

Found by: A-history F3 (confirmed by source) ([intent](../uplift/ivg-verus-initial/intent/ledger-history.md)); review R1-core CV-6 and R1-6.

Reproduced by: none — follows from the behavior shown by [redaction_binding](receipts/native/redaction_binding.json), where node records carry the default graph.

`IVG-OPSREVIEW-BRIEF.md:125` recommends `engine.ledger.redact(graph, prefix="tenant|")`. Node records always carry graph `""` (`LedgerApply.cls:232-369`; spec 256 plan.md:9) and `Matches` requires the record's graph to equal the target (`LedgerRedact.cls:93`), so this call leaves every node record of the tenant. The correct recipe is the pair in ADR-0013:37 (the tenant's graph, then the default graph with the prefix). Governing statement: [redaction.tenant](../ontology/features/redaction.g5.md#redaction.tenant).

<a id="bug-doc-002"></a>
### The user guide says a repeated commit replays, which holds only with an idempotency key

Severity: Low

Run: Uplift 2026-11-13

Found by: A-history F7 (confirmed by source); review R1-core E1.2 and R1-6.

`USER_GUIDE.md:1102` ("Retries") says committing the same actor and operations again replays. Replay requires `idempotency_key` (`Ledger.cls:457`); without one the retry applies again or fails on an existing node. Governing statement: [ledger.idempotency.key-required](../ontology/features/ledger.g5.md#ledger.idempotency.key-required).

<a id="bug-doc-003"></a>
### Spec 256's text contradicts its own decisions and the shipped tombstone format

Severity: Low

Run: Uplift 2026-11-13

Found by: A-history F6 (confirmed by source).

- FR-004 says metadata is cleared when "every" record is redacted, Decision 2 says "any" (`spec.md:121` vs `:155`); SC-004 promises byte-identical revision rows, which Decision 2 contradicts for spanning revisions (`:148`).
- "The revision count does not change" (`:106`) contradicts Decision 1's redaction revision; acceptance scenario 2 is garbled (`:57-58`).
- The Key Entities tombstone `$LB("redacted", digest, flags)` (`:134`) differs from the code's five fields (`LedgerRedact.cls:337`).
- FR-003 requires history and export to mark ordinals, which they cannot; spec 213's contracts lack the spec 256 codes and kinds, and spec 213 `spec.md` and `research.md` are cited but absent at the pin.

Governing statement: [redaction.tombstone](../ontology/features/redaction.g5.md#redaction.tombstone).

<a id="bug-doc-004"></a>
### Several shipped specifications still say Draft or not adopted

Severity: Low

Run: Uplift 2026-11-13

Found by: A-history F6; A-platform F-S10; A-search Q3.

Spec 256 says "Status: Draft" although it shipped in 4.3.0; specs 240 and 241 say "Exploratory … not adopted" and "Draft … not adopted" although `9b7bb810` and `996aed7a` are merged and shipped (241's shortcut is at `graph_scoped_embeddings.py:735-760`); specs 235, 236 and 044 still say Draft.

<a id="bug-doc-005"></a>
### ADR-0016 still describes the IVG Schema design before it was built

Severity: Low

Run: Uplift 2026-11-13

Found by: A-platform F-S9.

ADR-0016 says "Status: Accepted (… implementation pending)", the regex `[A-Z][A-Z0-9_]*`, "the ObjectScript classes read it there" and `remove_legacy_sql_objects`. The shipped design (research R1, FR-004, the code) rewrites class source at deploy, allows mixed case, and names `remove_legacy_objects`. Governing statement: [install.schema](../ontology/concepts/install.g5.md#install.schema).

<a id="bug-doc-006"></a>
### ADR-0003 says control characters are stripped from named-graph keys, but the code refuses them

Severity: Low

Run: Uplift 2026-11-13

Found by: B-structure O1 doc drift ([NOTES](models/graph_structure/NOTES.md)); confirmed by [graph_structure_keys](receipts/native/graph_structure_keys.json) cases K2 and K3 (refused).

ADR-0003:14 gives the named-graph index key as `$ZStrip(graphId,"*C")`; `GraphKey.Validate` refuses any control character and strips only NUL (`GraphKey.cls:38-48, 82-85`). Governing statement: [graph.key.two_forms](../ontology/concepts/graph-scope.g5.md#graph.key.two_forms).

<a id="bug-doc-007"></a>
### ADR-0004 says bulk_delete_adjacency was removed, but it is still shipped and documented

Severity: Low

Run: Uplift 2026-11-13

Found by: B-platform doc drift ([NOTES](models/platform/NOTES.md)).

ADR-0004:81 says `bulk_delete_adjacency` "is removed rather than deprecated"; it is present (`nodes_edges.py:2301-2338`) and in API_REFERENCE:418. It now erases through the Eraser, so it no longer leaves drift, but it bypasses strict mode ([bug-plt-006](#bug-plt-006)). Governing statement: [erasure.entry-points.single-path](../ontology/features/erasure.g5.md#erasure.entry-points.single-path).

<a id="bug-doc-008"></a>
### ADR-0012 does not mention the lockless-writer fallback that 4.7.0 added

Severity: Low

Run: Uplift 2026-11-13

Found by: A-structure Q7; A-ops hazard (c)8.

`Adjacency.WriterLock` proceeds without the lock after 5 s and sets `^IVG.AdjNoLock` (`Adjacency.cls:61-75`), which disables cache stores until a rebuild; this lives only in a CHANGELOG row and code comments, while ADR-0012 still says every writer holds the shared lock. Governing statement: [structure.degree.cache.uncommitted](../ontology/features/graph-structure.g5.md#structure.degree.cache.uncommitted).

<a id="bug-doc-009"></a>
### Temporal documentation contradicts the code in several places

Severity: Low

Run: Uplift 2026-11-13

Found by: A-temporal S4, F5 and F12; B-temporal O1 (contradictory docs); reconstruction check 2(b)3.

- The `create_edge_temporal` docstring says a refused write "writes nothing" (`temporal.py:260-261`); `_temporal_left` says the stores written before the error stay (`temporal.py:12-17`).
- `Changeset.create_temporal_edge` says "insert (fail if key exists)" (`changeset.py:334-335`); since spec 254 an insert collision succeeds and is recorded.
- `delete_edge_temporal`'s "KNOWN AMBIGUITY" (`temporal.py:364-369`) is false for indexed installs.
- Spec 213 `contracts/ledger-api.md:92` says a strict-mode temporal write skips its plain row; with the index declared the marked row is written server-side.
- ADR-0009:40 on Cypher adoption is stale, and ADR-0002 forbids other classes to read the temporal globals while `TemporalWindow` reads `tout`/`tin`/`edgeprop`/`tlast` (the guard test checks writers only, `test_temporal_single_owner.py:1-40`).
- USER_GUIDE "Writes inside your transaction" lists two counters a rollback leaves; the statistics are also left ([bug-tmp-003](#bug-tmp-003)).

Governing statement: [temporal.owner](../ontology/features/temporal.g5.md#temporal.owner).

<a id="bug-doc-010"></a>
### Search documents are not reconciled with graph-scoped routing or with the BM25 corpus

Severity: Low

Run: Uplift 2026-11-13

Found by: B-search O3 and Q2 ([NOTES](models/search/NOTES.md)); A-search F1 (documentation part) and Q2; review R3-platform R1-9 (provenance).

ADR-0006 and CONTEXT.md "Embedding Registry" say a write at another model is "refused rather than mixed in" (the glossary phrase was added on 2026-11-04 in `267aaff1`, R039, restating ADR-0006 after the 4.0.0 routing release, not reconciled with it); since 4.0.0 a different declared model is routed to its own table, and refusal remains for width, dtype and mechanism on the same pair and for re-claiming a recorded table. `docs/migration/v4.0.0.md:750` says the BM25 corpus is `Graph_KG.docs`; `BM25Index.Build` reads `rdf_props`. Governing statement: [search.embedding.other_model](../ontology/features/search.g5.md#search.embedding.other_model).

<a id="bug-doc-011"></a>
### ADR-0005 forbids the three-argument TO_VECTOR for query vectors, which four call sites use

Severity: Low

Run: Uplift 2026-11-13

Found by: A-search F12.

ADR-0005 says the 3-argument `TO_VECTOR` "MUST NOT be used for a query vector"; `edge_vector_search` (`vector.py:368`), `vector_search` (`:1240`), `dbapi_utils.py:268` and `iris_sql_store.py:2634` use it with the query's own length, so no reshape is expected (the ADR's measured hazard is a width declared on the query). Either narrow the ADR or drop the length. Governing statement: [search.knn](../ontology/features/search.g5.md#search.knn).

<a id="bug-doc-012"></a>
### The glossary says structural edges are subject to the ledger, but Cypher writes are never recorded

Severity: Low

Run: Uplift 2026-11-13

Found by: A-cypher F10.

CONTEXT.md:60-63 says a Structural Edge is "Subject to the revision ledger", and USER_GUIDE:1107-1110 speaks only of `create_node`, `create_edge` and "the other methods"; Cypher DML is unrecorded and refused only in strict mode (`ledger/guard.py:20, 75-80`). One sentence in each document would close the gap. Governing statement: [query.writes.ledger](../ontology/features/cypher.g5.md#query.writes.ledger).

<a id="bug-cyp-009"></a>
### A build job queued before a layout change can leave a shape interpreted until the next change

Severity: Unranked

Run: Uplift 2026-11-13

Found by: B-platform Part 3 "Not represented" (source reading, not modelled) ([NOTES](models/platform/NOTES.md)).

A build job queued before an `rdf_props` recompile can mark a fresh pending entry "refused" (its digest is for old-layout lines); the fresh job then quits on the non-pending status and the shape stays interpreted until the next stamp change or deploy. Answers stay correct; only the speed-up is lost. Governing statement: [query.compiled.fallback](../ontology/features/cypher.g5.md#query.compiled.fallback).

<a id="bug-test-002"></a>
### The other unit, integration and cited end-to-end failures at the baseline come from this uplift's harness and environment, or are not root-caused

Severity: Unranked

Run: Uplift 2026-11-13

Found by: the upstream suites at the baseline (Python 3.11.18, driver 5.3.2 per `uv.lock`, IRIS Community, through `native/run_upstream.py`); logs under `$RUN_DIR/tests/` (cited files: `$RUN_DIR/tests/cited/`).

- Unit: 24,792 passed, 18 failed, 63 errors. Four failures are findings ([bug-test-001](#bug-test-001), [q-cyp-004](open_questions.md#q-cyp-004)). The other 14 failures (`test_460_r173_refusal_order.py` 4, `test_conftest_class_deploy.py` 4, `test_schema_init.py` 5, `test_setup_logging.py` 1) exercise the session class deploy that `run_upstream.py` replaces with `engine.initialize_schema()`. The 63 errors (`test_cypher_e2e_new_features.py` 33, `test_property_primitives.py` 15, `test_engine_status.py` 6, `test_boolean_text_storage_e2e.py` 4, `test_rrf_fuse_e2e.py` 3, `test_ivf_index.py` 2) build width-4 test engines against a session deployed at width 768, or need embedded Python.
- Ledger and erasure integration, per file: all passed, `test_ledger_us03_concurrency` 4/4 when run alone (its first-run hang in the long combined run was environmental), except the erasure failure-injection suites (`test_eraser_failures`, `test_edgescan_ledger_erase`), which need a scratch namespace and then fail on Community's connection licence ("Unable to allocate a license"): no verdict.
- End-to-end and integration files the ontology cites: 81 run, 1,330 passed, 16 failed, 329 skipped, 1 timeout. Environment: `test_mcp_tools` (no `%AI` classes), `test_460_r202_reading_role_e2e` (no embedded Python), `test_embedding_registry_e2e` (Community IRIS refuses a functional index on an unfixed-width vector, ERROR #5414), `test_262_upgrade_451` (600 s cap). Leftover probe state: `test_230_migration` passes 4/4 after a reset. Not root-caused: `test_460_legacy_manifest_320_loader_e2e`, `test_460_legacy_manifest_400_e2e` and `test_463_legacy_same_named_functions_e2e`, plausibly driver 5.3.2 against the release gate's 5.4.x, or missing legacy-install fixtures.

Apart from the four unit findings, these are coverage limits of this arm, not evidence of product defects; the three legacy-manifest failures stay unexplained.

<a id="bug-test-003"></a>
### Native probe runs on this arm have setup limits that bound what their verdicts show

Severity: Unranked

Run: Uplift 2026-11-13

Found by: review R3-platform R1-12, R1-10 and R2-data R1-12; the probe receipts under `receipts/native/`.

- Community's connection licence ("Unable to allocate a license") bounds concurrency: `graph_structure_degree_aba` ran 3 readers (an earlier 16-reader run lost most of them to the licence), and the erasure failure-injection suites cannot run. It is a premise of every probe run here.
- `search_queue_default_graph` is INCONCLUSIVE (Community ships no `%Embedding.Config` at the table's width 768), so [bug-srch-006](#bug-srch-006) stays unobserved; `search_route_split`'s first run claimed a width-4 identity on the 768-wide table and was INCONCLUSIVE until its setup was fixed.
- The first native receipts carried no probe-source hash or product baseline, and `cypher_subquery_write`'s first receipt came from an older probe revision and misread its own result. The final receipts are hash-stamped (`_probe_inputs`, `_product_baseline`); earlier copies are kept in `receipts/native/earlier/`.
- Judge gaps the review listed: `parallel_delete_rel` did not require the two-edge layout before the delete (the final receipt records it: 2 rows, children `[0,1]`, `#` = 2); `keys` K3 did not condition on the observed control class; `algo_cache_rollback` has no arm with the algorithm cache disabled. The temporal probes now check their preconditions and failure sites (R1 records that op 0 ran before op 1 was refused; the partial write names `AssertTemporalRow`).

These limit the evidence, not the product.

## Withdrawn, refuted and not reproduced (playbook arm)

Playbook-arm finding records whose own disposition withdraws them. They stay here with the recorded reason.

<a id="F-0904"></a>
### In sync mode a failed build runs in the reader's own process

Severity: Unranked

- Playbook arm disposition: `not-reproduced` ([09.json](../../experiment/playbook-completion/findings/audit/09.json)); source severity S3.
- Reason recorded: The mechanism (sync compiles in the reader's process, costing it the compile time) is source-confirmed; the harsher effect (the process can no longer prepare SQL) is an IRIS 2026.3 premise that Community 2026.1 did not show. Whether sync is a supported production mode is not settled: ADMIN_GUIDE offers it (docs/ADMIN_GUIDE.md:746-752), spec 257 US3 promises compilation never costs a caller.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


<a id="F-1608"></a>
### The sample API lets two threads use its one IRIS connection at once

Severity: Unranked

- Playbook arm disposition: `not-reproduced` ([16.json](../../experiment/playbook-completion/findings/audit/16.json)); source severity S3.
- Reason recorded: The overlap was exercised but the failure (SQLCODE -400 seen upstream on 2026.3 AI with driver 5.4.1) did not occur on this build/driver. The code still relies on an unproved premise; obligation stays open.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


<a id="F-1612"></a>
### The REST dispatcher may read only the first chunk of a large request body

Severity: Unranked

- Playbook arm disposition: `refuted` ([16.json](../../experiment/playbook-completion/findings/audit/16.json)); source severity S4.
- Reason recorded: blocked-access for the end-to-end check: dependency = a %CSP.REST web application dispatching to Graph.KG.Service (Graph.KG.Service.CreateWebApp), which modifies Security.Applications. Other IRIS versions may still default to 32,000 (documented %Stream.Object.Read signature).

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


<a id="F-C0403"></a>
### Candidate: with the adjacency index declared, a failed rebuild could leave part of the adjacency missing

Severity: Unranked

- Playbook arm disposition: `not-reproduced` ([04.json](../../experiment/playbook-completion/findings/audit/04.json)); source severity S4.
- Reason recorded: Candidate from the journal (J12: ^KG out/in refilled outside any transaction by the caller's and two worker processes) against the method's comment: the indexed path purges and refills after TCommit with %BuildIndices in parallel jobs. Not reproduced: a sync() failed on a row with graph_id '0' left all 400 sources of a 400-edge graph in ^KG out and verify_graph ok. Readers during the refill can still see a partial adjacency (the method's own catch comment says so); that window was not measured. Not counted as a defect.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


<a id="F-C1240"></a>
### EraseAll kills ^ArnoKG, a store the erase plan (GraphStores.Inventory) does not list

Severity: Unranked

- Playbook arm disposition: `refuted` ([zz-structural.json](../../experiment/playbook-completion/findings/audit/zz-structural.json)); source severity S4.
- Reason recorded: The kill itself is the right effect for an erase-all (ADR-0004). Not checked here: whether a graph erasure (which does not touch ^ArnoKG) leaves an Arno-path answer built from the erased graph's cached adjacency; that is an erasure-completeness question for the owning lanes. Refuted (orchestrator, from the ontology-2 lane's correction, checked at the pin): GraphStores.Inventory does list ^ArnoKG at GraphStores.cls:131, one line past the range the record cited (28-130); that entry itself says erasing content without bumping ^KG("__version") leaves Arno serving the erased graph, which is an era…

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


<a id="F-C1720"></a>
### IRISGraphStore.query_nodes(limit=n) without a label filter kills the calling Python process (SIGSEGV) on the pin's locked driver 5.3.2: it sends FETCH FIRST n ROWS ONLY, which the product's own FETCH…

Severity: Unranked

- Playbook arm disposition: `duplicate` ([zz-contract-2.json](../../experiment/playbook-completion/findings/audit/zz-contract-2.json)); source severity S2.
- Reason recorded: Reachability: query_nodes is a public method of the SQL store adapter; the engine reaches it only for stores without the native_sql capability (_engine/query.py:2286-2340), so the IRIS engine's own Cypher path does not (both execute_cypher probes answered). The process dies, not just the call: an API server or MCP process using the adapter this way stops serving every request. Distinct from F-C1706 (same driver, different symptom: a crash rather than wrong types or errors). Found by the contract-2 lane's TOP / LIMIT / FETCH FIRST coverage (X2-TOP); FETCH FIRST stays outside the contract (P2-F…
- Duplicate of F-C1743.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._

## Candidates not filed (playbook arm)

Candidate findings named by the playbook arm's stopped lock-plan lane (`lockplans/PARTIAL.md`, `STATUS.md`); not findings, kept so no ID is lost. Their drafts are not cited.

<a id="F-C0811"></a>
### Unfiled candidate F-C0811

Severity: Unranked

- Named in STATUS.md and PROOF-DEBT.md (lock-plan lane); not filed as a finding by the playbook arm, not reproduced or examined here.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


<a id="F-C1711"></a>
### Unfiled candidate F-C1711

Severity: Unranked

- Named in STATUS.md and PROOF-DEBT.md (lock-plan lane); not filed as a finding by the playbook arm, not reproduced or examined here.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


<a id="F-C0111"></a>
### Unfiled candidate F-C0111

Severity: Unranked

- Named in a lock-plan draft (`lockplans/11.json`, PENDING-LIVE); not filed as a finding by the playbook arm, not reproduced or examined here.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


<a id="F-C0511"></a>
### Unfiled candidate F-C0511

Severity: Unranked

- Named in a lock-plan draft (`lockplans/51.json`, PENDING-LIVE); not filed as a finding by the playbook arm, not reproduced or examined here.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


<a id="F-C0512"></a>
### Unfiled candidate F-C0512

Severity: Unranked

- Named in a lock-plan draft (`lockplans/51.json`, PENDING-LIVE); not filed as a finding by the playbook arm, not reproduced or examined here.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


<a id="F-C0513"></a>
### Unfiled candidate F-C0513

Severity: Unranked

- Named in a lock-plan draft (`lockplans/51.json`, PENDING-LIVE); not filed as a finding by the playbook arm, not reproduced or examined here.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._


<a id="F-C1011"></a>
### Unfiled candidate F-C1011

Severity: Unranked

- Named in a lock-plan draft (`lockplans/01.json`, PENDING-LIVE); not filed as a finding by the playbook arm, not reproduced or examined here.

_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._
