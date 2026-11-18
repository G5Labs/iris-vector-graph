# T report — features/temporal (29 blocks)

Saved by the builder from the fork's final message. Fragment: 29 blocks complete, 169 obligations, 52 exclusions,
owner-updates 2; merged check exit 0 PASS. Receipts cited (latest, fresh): temporal_stats prove 20261117T072022Z,
binding 20261117T065845Z; temporal_clock prove 20261116T160855Z, binding 20261115T182957Z; temporal_window_reader prove
20261116T160858Z, binding 20261115T042304Z; retry_replay prove 20261116T160829Z, binding 20261115T183316Z; write_routing
prove 20261116T221442Z, binding 20261117T020529Z; temporal prove 20261116T160854Z; temporal_restore prove
20261116T160857Z, binding 20261115T175727Z; four native temporal_* receipts with unchanged inputs.

## 1. Per block (f/p/a, total, excl) — all complete, no structural zero
temporal.edge 5/1/0 (6, 1); .edge.clock 11/0/0 (11, 0); .edge.graph-scope 0/1/1 (2, 1); temporal.write 7/2/0 (9, 10);
.write.collision 2/0/0 (2, 0); .write.repeatable 1/0/2 (3, 0); .write.retry 5/0/0 (5, 1); temporal.stats 1/0/0 (1, 7);
.stats.after-purge 6/0/0 (6, 1); .stats.window 9/3/1 (13, 2); .stats.velocity 8/0/0 (8, 0); .stats.distinct 5/1/3
(9, 0); temporal.latest 0/0/8 (8, 1); .latest.exact 0/0/5 (5, 2); temporal.delete 1/0/1 (2, 5); temporal.optout 1/2/1
(4, 4); .optout.effect 2/1/2 (5, 0); .optout.toggle 2/3/2 (7, 0); .optout.drop 2/2/3 (7, 1); temporal.window 3/4/4
(11, 1); .window.sources 4/0/0 (4, 0); .window.paging 2/2/1 (5, 1); .paging.release 6/0/3 (9, 0); temporal.labelset
6/1/2 (9, 1); temporal.purge 2/2/1 (5, 4); .purge.bare-nodes 0/0/5 (5, 0); temporal.erase 0/2/0 (2, 6);
temporal.ledger 0/2/2 (4, 3); .ledger.atomic 2/0/0 (2, 0).

## 2. Totals
full 93, partial 29, absent 47, unassessed 0, of 169 (55.0%). Proved 102 (49 full scope; 53 narrowed: 36 full grades,
17 partial). Refuted 6, all full scope: temporal.edge#o03 (no-timestamp write stored at epoch 0, not now);
stats.window#o06 (empty window raises instead of 0); stats.window#o12 (empty-key aggregate read not refused);
stats.distinct#o07 (estimate not within a quarter: one target answers 11); labelset#o02 (equal sets different hashes /
different sets same hash); ledger.atomic#o02 (a failed changeset leaves its statistics counted). Bounded 0, unchecked 0.
Full with no design check: stats.velocity#o08, labelset#o04. Exclusions 52: restatement 35, undecided-alternative 10,
cross-reference 3, definition 2, navigation 1, rationale 1.

## 3. Grades: reused 124, changed 1, new 44
Reused: NOTES and decision-links rows of temporal_clock, temporal_stats, temporal_window_reader, retry_replay,
write_routing; coverage.md "Temporal edges" round-2 rows (collision, repeatable, stats fragment, after-purge, opt-out
effect/drop/toggle, ledger, ledger.atomic, serial delete, graph-scope); the section's coverage-gaps list (latest,
latest.exact, bare nodes, erase).
Changed: temporal.edge#o03 — coverage.md "ts=0 handling … not modelled" → full, refuted (temporal_clock, it. 7; witness
reaches the window reader).
New: partial where a model stops short (update replacing attributes, batch skipped count, millisecond edges in groups and
distinct reads, distinct sketch rebuild, per-graph registration, backfill and drop refusals modelled only as no-ops,
window filters, purge result counts); absent with no model (latest index, bare nodes, opt-out warning, one-call window
readers, server handle ownership).
Narrower than coverage.md (not counted as changed): collision "changes nothing anywhere" full but narrowed (newest-event
index not modelled); temporal.ledger success path partial (no theorem); optout.toggle "existing edges stay" partial
(proved only against the purge).

## 4. Parents
Credited: temporal.stats#o01 (statistics summarize the edges over any serial history): per-step writer rules belong to
temporal.stats.writers (A) and theorem_stats_as_built_fragment composes them over histories; full, proved, narrowed.
Residual: a raw purge cutting a bucket followed by a delete (q-tmp-002) and concurrent writers
(witness_concurrent_inserts_double_count) break the summary while every step rule holds; the theorem excludes updates at
occupied coordinates, throws and rollbacks. All other parents (edge, write, latest, optout, window, window.paging,
purge, ledger) carry only their own obligations; child-restating sentences excluded with owners.

## 5. Restatements
owner-updates: ledger.changeset#x01 → temporal.ledger#o01; ledger.strict#x04 → temporal.ledger#o03 (ledger.strict#x03
left to A). Cross-fork (owners on A's page): temporal.write#x02 'updates the statistics' → temporal.stats.writers;
temporal.write#x04 'asserts the implied structural edge unless the predicate is temporal-only' → temporal.structural;
temporal.write#x06 'but a rollback leaves its statistics counted' → temporal.stats.writers (bullet 5); temporal.delete#x01
'statistics of its bucket are recomputed … event counter goes down by one' → temporal.stats.writers (bullet 4);
temporal.delete#x04 'the structural edge follows the end of the implication' → temporal.structural.end; temporal.purge#x01
'and the marked structural edges that only those timestamps held up' → temporal.structural.end; temporal.purge#x04 'A
triple with timestamps on both sides of the range keeps its structural edge' → temporal.structural.end; temporal.ledger#x01
'Direct temporal writes outside a changeset create no revision' → temporal.structural.ledger.
Reverse direction for A: temporal.stats.writers bullet 2 ("an insert or skip at occupied coordinates changes nothing")
restates temporal.write.collision#o01 and temporal.write#o03; temporal.structural.end bullet 3 ("endpoint nodes stay
unless the purge is asked to retire bare nodes") points to temporal.purge.bare-nodes#o01.
Other owners: graph.names#o04, erasure.kept#o02, #o07, erasure.scope#o04, #o06, erasure.entry-points#o02,
erasure.atomic#o01, erasure.prefix-match#o03.

## 6. Grade-source errors and contradictions
1. temporal.purge bullet 6 overstates: legacy whole-store purge "also removes statistics of buckets before the cutoff's"; TemporalIndex.cls::PurgeBefore (816–860) deletes statistics only inside its loop over remaining raw timestamps; a bucket before the cutoff whose raw edges were already purged keeps its statistics. Graded absent.
2. erasure.atomic#o01 missing a counterexample: temporal.rs witness_rolled_back_delete_undercounts and native R6 (receipts/native/temporal_rollback_counters.json: rolled-back node erasure leaves velocity 0 and raw bucket 0) are a modelled as-built counterexample for the temporal-counter part of erasure atomicity; the iteration-61 row does not cite them.
3. Two stale coverage.md gap rows: "ts=0 handling (bug-tmp-007) … not modelled" (temporal_clock) and "the window reader is still not modelled" (temporal_window_reader).
4. models/temporal_stats/NOTES.md names prove 20261117T065847Z; latest 20261117T072022Z.
5. temporal.window.sources tagged design-verified, but its server half (TemporalWindow.cls::Open/NextKey) is only inspected.
6. temporal.write WA2 ("statistics keep describing the first write") conflicts with temporal.stats.writers bullet 3 (an update counts the edge again today); excluded as undecided alternative.

## 7. Ranked uncovered
1. Newest-event index: temporal.latest#o01–#o08, latest.exact#o01–#o05 (13 absent, no model). Bind TemporalIndex.cls::NoteLatest, ::Relatest, ::RelatestRange, ::RebuildLatest, ::EraseNodes; reader TemporalWindow.cls::Latest, _engine/temporal.py::TemporalMixin.get_latest_edges (native predictions L1–L8 exist from it. 51).
2. Bare-node retirement: bare-nodes#o01–#o05, optout.drop#o02 (6 absent). Bind TemporalIndex.cls::RetireExpired, Eraser.cls::ForgetNodes, Python purge default (temporal.py:623), TemporalPolicy.cls::DropRows.
3. Cross-graph frame: graph-scope#o02 absent; #o01 partial (window reader only). Bind GraphKey.ForIndex in WriteStores, DeleteTemporalEdge, PurgeRawBefore, PurgeBucketRange.
4. Changeset temporal operations: ledger#o01, #o04 partial; #o02, #o03 absent (default update mode as a decision; revision record per temporal op; what a collision records, q-tmp-004, F5). Bind Changeset.create_temporal_edge, LedgerApply.cls::OpCreateTemporalEdge (617–641), Ledger.cls::Commit.
5. Window ordering and filters: window#o02, #o03, #o06, #o07, #o09, #o10 (TemporalWindow.cls::Open/NextKey/Page; TemporalIndex.cls::QueryWindow/QueryWindowInbound; temporal_window.py::window_spec, event).
6. Opt-out operations: optout#o02, #o03; effect#o02–#o04; toggle#o03, #o05–#o07; drop#o04–#o07 (TemporalPolicy.cls::Set, ::IsStructuralKey, ::DropRows, ::BackfillRows; stores/temporal_structural_rows.py).
7. Distinct/group reads with no source or empty predicate: stats.distinct#o02–#o04, stats.window#o11 (GetDistinctCount, GetBucketGroups, GetBucketGroupTargets).
8. Repeatability: write.repeatable#o02, #o03 (BulkInsertCounts, Adjacency.cls::AssertTemporalRow).
9. Live paging and server handles: window.paging#o01, #o03; release#o06–#o08 (TemporalWindow.cls::Open/Page/Close).

## 8. Iteration-60 residual mapping
Temporal residue: items 1, 2, 4, 6, 7 and graph-scope#o02. store/iris_sql_store: temporal store methods already bound;
latest readers not (item 1). Migrations: latest#o08 (a graph written before the index needs one rebuild), legacy purge
(purge#o05). Source-discovered omissions: TemporalIndex.cls::RebuildBucket (migration-only statistics rebuild); the
millisecond class's own readers over seconds-class edges; get_edge_attrs and get_window_sources readers; BulkInsert
wrapper returning only the first count.

## 9. Limitations
Split granularity (latest 8; latest.exact 5, one per writer kind; window bullet 4 one partial across five filters;
labelset bullet 4 split); "Today" sentences graded as current behaviour paired with the intended rule; narrowed scopes
(one writer at a time, declared adjacency index; window reader server half inspected; temporal_clock and retry_replay
are transcriptions checked against a specified adapter); write#o05 derived through the fallback route's single writer
(InsertEdge); temporal.erase mostly restatements (temporal-counter refutation reported in §6.2, not counted here); no
independent review, no fresh runs.
