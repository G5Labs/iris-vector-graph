# Bugs and issues — IVG initial Verus uplift

Product baseline `3eaa79cf`. Each entry cites the governing source of the expected behavior, what the baseline does and the evidence. "Suspected" marks an entry whose product reachability is not yet shown natively. Proposed repairs are not implemented (the product is read-only for this uplift). Index and counts: [findings register](findings.md).

<a id="bug-001"></a>
### Two redactions of different targets can run at once, and each one's audit and receipt then describes the other's work

Severity: High · Decision: Open

Run: Uplift 2026-11-13

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

<a id="bug-led-007"></a>
### Erasing a tenant by prefix leaves its temporal-only events, and the redaction that follows completes while they stay readable

Severity: Medium · Decision: Open

Run: Uplift 2026-11-13

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

Reproduced by: none

Expected: a merge restore adds the archive's rows that are not already present; the v4.1.0 CHANGELOG (3926-3932) names this dedupe defect and fixes it for the FHIR tables.

Observed: the generic merge guard is `WHERE NOT EXISTS (… WHERE {cols[0]} = ?)` and the count is incremented regardless (`_engine/snapshot.py:1287-1298`); export drops `edge_id` (`snapshot.py:872-874`), so for `rdf_edges` (and `rdf_labels`, `rdf_props`, `docs`) the first column is `graph_id`.

Consequence: saving two edges in G, erasing G and merge-restoring gives one edge, and the report says two were restored.

Repair proposal (not implemented): dedupe on each table's key columns, and count only rows actually inserted. Governing statement: [install.snapshot](../ontology/concepts/install.g5.md#install.snapshot).

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
