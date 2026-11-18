# review-1 census rows notes
1 query.native.equal-answers#o03 full/refuted/narrowed -> agree (rank->row order composition informal; SortKey.Key & Exec.OrderKey checked)
2 access.surfaces#o04 full/proved/full -> agree (cypher_api.py 239-265, 379-460 match)
3 access.bolt.graph_values#o05 full/refuted/narrowed -> agree (bolt_server.py 713-801 prev_node/next)
4 erasure.atomic#o01 full/refuted/narrowed -> partial: theorem_failed_call_leaves_stores is definitional (call() Some(late)=>rows unchanged); premise excepts only version $Increment but TemporalIndex.RemoveTemporalRow:357 $Increment(bucket,-1) under EraseNodes (Eraser.cls:605) is not rolled back; refuting witness cited is temporal delete in caller rollback (o04 case), not an erase failure. list witness (o05) would refute.
5 erasure.entry-points.single-path#o04 full/proved/narrowed -> partial(borderline): witness_delete_edge_leaves_statement has no Adj entry; adjacency removal only by delete_edge spec fn (a/b). product nodes_edges.py:1382-1456 matches (all_graphs path unmodelled, not required)
6 ledger.commit.caller-transaction#o12 full/proved/narrowed -> agree (txn_rollback cnt derived from stats_holder/stats_base, ledger_client.rs:346-383; level0 vs level>0 contrast in ensures)
7 redaction.target#o03 full/proved/full -> agree (match_string = LedgerRedact.cls:48-53; lemma equality => same has_prefix selection, redaction.rs:51)
8 ledger.lifecycle#o05 full/proved/narrowed -> agree (client_commit Disabled branch; calls_server excludes empty changeset, caller-txn path not cited -> narrowed ok; enabled contrast not in cited theorem, minor)
9 structure.adjacency.scan#o09 full/proved/full -> full/narrowed: plan(edgescan_env,named_graph) sql_procs.rs:133-137 doc premise 'no inline relationship properties', id-named non-anon source (translator.py:16472-16492 conditions) not in premises; USE GRAPH '' mapping supplied as named=false
10 temporal.structural.mark#o03 full/proved/narrowed -> agree (rows_ok_parts temporal.rs:2101 preserved by theorem_rows_as_built gives 'goes'; lemma_temporal_ops_keep_explicit_rows gives 'unmarked stays'; optout exception and phased excluded -> narrowed)
11 algorithms.cache.pagerank#o05 full/proved/narrowed -> agree (key()/call() census derived from n None; algorithms.py:178-196,780-796 + iris_sql_store.py:2362-2387 match)
12 search.fusion.python#o03 full/proved/full -> agree(borderline): theorem per single list rank; score=sum part(rank) definitional, sort not modelled (NOTES 'observed consumer sorts'); fusion.py:38-64 uses only ids/positions
13 query.values#o01 full/proved/narrowed -> agree (write/cy_typed/read node_read.rs:15-42; finish_scalar reaches decoded cell; N-fraction is #o02 separately)
14 query.functions.percentile#o02 full/proved/narrowed -> agree (pcont == IVG/Percentile.cls:21-36; theorem general over xs,p)
15 install.inference#o09 full/proved/narrowed -> agree (materialize keeps present rows inference_rows.rs:41-47; theorem one shape -> narrowed)
16 install.export.rdf.report#o02 full/proved/narrowed -> agree (cited theorem covers only objects-excluded; +2 blank case proved by uncited theorem_envelope_has_two_derived_blank_subjects rdf_reporting.rs:176 and theorem_raw_rows_to_final_report:212 -> locator incomplete, substance full)
17 search.embedding#o02 full/refuted/narrowed -> agree (witness_identity_fail_open search.rs:2813 reaches writer outcome; schema.py:1054-1056 returns None on read error = fail-open as built)
18 temporal.write.retry#o03 full/proved/narrowed -> agree (run/fold over clock model, fault position is environment input; empty store + one item -> narrowed)
19 install.schema.not_ready#o06 full/proved/full -> agree (first_access install_lifecycle.rs:61-71 = schema_name.py:220-235; requires = statement condition)
20 install.status.capabilities#o01 full/refuted/narrowed -> agree (theorem over all acts: markers never set, detect reads markers operator_reports.rs:352-355; 'built' side implicit; os:true constant so class-dictionary part unmodelled, refutation rests on kg/nkg)
A1 structure.multigraph.layout#o06 absent -> agree (gmode_l2 'a fresh key, any here' no clash; no concurrency model; owner-contradicted)
A2 structure.rebuilt#o01 absent -> agree(borderline) (freshness_stamp covers deg2p stamps only; adjacency_maint marks_stale models NKG stale flag not token)
A3 algorithms.owner#o01 absent -> partial? traversal_strategy theorem_fixture_path (Arno absent -> ObjectScript Owner answers BFS) represents a case
A4 algorithms.graph_scope#o02 absent -> agree (no RefuseMergedGraphs model; algo_options = option validation only; traversal_strategy other_graphs_have_edges only routes Arno)
A5 algorithms.op.walks#o07 absent -> agree (no random_walk in any model/crate)
A6 query.graph-scope.names#o02 absent -> agree (cys_l1/l2 scope only; no name validation model)
A7 fhir.interpretation#o07 absent -> borderline partial: ppr_walk.rs:30-37 hops skips ex.contains(pred) with exclusion as input (Request.excluded None = engine default no exclusion); FHIR default list not modelled
A8 install.schema.classes_follow#o01 absent -> partial: platform.rs:80-81,245 SetupDeploy inserts setup schema into classes_for ('rewritten sources'); case-variant spelling (bug-plt-015) not represented (platform.rs:31-32)
A9 install.snapshot#o04 absent -> partial (plausibly full refuted/narrowed): proofs-d1b cx_fc1801.rs::counterexample_fc1801 (dirty export under concurrent writer, control_fc1801_dirty_export receipt 20261115T035741Z) + snap_l2 R18-1 export gate; proofs-mech i13_epoch/m13_epoch epoch protocol. Also question: WA may be undecided-alternative (HD-1802)
A10 install.snapshot.failure#o02 absent -> agree (snapshot.py:1205-1215 _commit per table; d1b excludes crash mid-restore; no model)
Stats: FULL grade agree 18/20 (strict) / 19/20 (lenient #5); grade+scope 17/20. ABSENT agree 6/10 (7/10 if A7 held).
Wilson 18/20: 0.699-0.972; 19/20: 0.764-0.991
