# A report — architecture/adjacency-and-derived-data (26 blocks)

Saved by the builder from the fork's final message. Fragment: 26 blocks complete, 131 obligations, 30 exclusions,
owner-updates `ledger.strict#x03 → temporal.structural.ledger#o04`; merged check exit 0 PASS.

## 1. Per block (f/p/a/u, excl) — none structural zero
structure.multigraph.layout 5/1/2/0 (0); structure.adjacency (parent) 1/2/2/0 (2); .declared 2/1/0/0 (0); .undeclared
0/2/1/0 (0); .one_writer 0/0/1/0 (2); .bulk 0/3/3/0 (1); .scan 11/0/0/0 (1); .declare 5/1/0/0 (1); structure.degree.cache
(parent) 2/1/0/0 (2); .uncommitted 2/2/0/0 (0); .erase 2/0/0/0 (0); .warm 6/2/1/0 (1); structure.rebuilt (parent)
1/0/3/0 (3); .token 0/2/2/0 (1); .stamp 7/0/0/0 (0); .valid 2/0/0/0 (0); .stale_read 0/1/2/0 (0); temporal.owner
0/0/1/0 (2); temporal.stats.writers 6/0/0/0 (2); temporal.structural (parent) 1/1/2/0 (6); .mark 4/0/0/0 (1);
.mark.readers 7/0/1/0 (1); .adopt 7/0/1/0 (1); .end 3/0/1/0 (0); .upgrade 7/0/2/0 (2); .ledger 3/2/1/0 (1).

## 2. Totals
full 84, partial 21, absent 26, unassessed 0, of 131 (64.1%). Proved 80 (18 full scope, 62 narrowed); refuted 6
(narrowed); bounded 0; unchecked 0; none 45. Full with no check (step definition, 8): scan#o03, #o06, uncommitted#o03,
erase#o01, valid#o01, #o02, adopt#o05, upgrade#o07. Exclusions 30: restatement 13, undecided-alternative 10,
rationale 6, cross-reference 1.

## 3. Grades: reused 66, new 60, changed 5
Reused: coverage.md graph-structure and temporal rows, decision links, NOTES of adjacency_maint, sql_procs,
index_declaration, freshness_stamp, warm_sources, temporal_stats, temporal_marker, edge_acceptance.
Changed: undeclared#o03 "Proved (the documented divergence)" → partial (witness covers only a raw SQL delete, not
Cypher, store_edge or write_edges); degree.cache.erase#o02 "Suspected violation" → full, refuted (ABA and gen-0
witnesses reach the served degree, rule 3; native probe INCONCLUSIVE); temporal.structural#o01 "Proved; Observed
(conditional)" → full, refuted (witness_partial_write_breaks_fwd, witness_purge_write_race_drops_row);
temporal.structural.end#o01 "Proved; Observed, suspected violation under interleaving" → full, refuted
(witness_purge_write_race_strands_row); temporal.structural.adopt#o01 "Proved; Observed (create_edge)" → full, refuted
(edge_acceptance::theorem_temporal_adoption: store_edge keeps the mark, F-0304; a caller-supplied marker too, F-C0351;
create_edge, bulk and ledger cases graded separately #o02, #o03, #o05).
New refutations: scan#o10 (bug-cyp-133: the IVG_EDGESCAN hop must answer what the default plan answers); upgrade#o08
(bug-tmp-107: setup's temporal_rows_backfilled counts every triple walked, not rows written).

## 4. Parents (none credited; open cases)
adjacency#o01 — the undeclared rebuild (FillEdge) leaves entries that disagree with the rows (unmodelled);
adjacency#o02–#o05 — own text (rebuild serialization, reader graph scoping, interned snapshot's merged edge while another
graph holds the triple); degree.cache#o01 — bulk-reader whole-graph stamp path serves counts without reading
generations; degree.cache#o03 — clearing entries while the stamp stays current returns zeros (F-0406, warm#o09);
rebuilt#o01 — ^NKG decides freshness by its own stale flag and a per-process flag, not a token; rebuilt#o02 — no child
covers the ^ArnoKG accelerator; rebuilt#o03 — the per-process flag lets another process treat a failed rebuild as fresh;
temporal.structural#o01 — a throwing structural step (bug-tmp-001) or a purge race leaves a timestamp with no row.

## 5. Restatements
owner-update: ledger.strict#x03 → temporal.structural.ledger#o04. Within page: declare#x01 → temporal.structural.upgrade#o01;
upgrade#x02 → structure.adjacency.declare#o05; adopt#x01 → temporal.structural.mark.readers#o07; rebuilt#x01 →
structure.rebuilt.stamp#o06; rebuilt#x02 → structure.rebuilt.valid#o01; degree.cache#x01 → structure.degree.cache.erase#o02.
To enumerated pages: adjacency#x01 → graph.key#o01; scan#x01 → access.iris_boundary#o01; upgrade#x01 →
access.iris_boundary#o04. Cross-fork: structure.adjacency.bulk#x01 → install.bulk_load (G) (bulk loader leaves no
duplicates and rebuilds indexes before returning, on success or failure); structure.rebuilt.token#x01 →
algorithms.cache.token (AE) (an answer that depends on other content must key on it or not be cached);
temporal.structural#x01 → temporal.optout (T) (temporal-only predicates are the exception); temporal.structural.ledger#x01
→ temporal.ledger (T) (temporal writes inside a changeset do create revisions).

## 6. Grade-source errors and contradictions
1. structure.adjacency.bulk bullet 4 (inside a caller transaction bulk_load_session "leaves ^NKG to sync()"): operator_reports' kept DISAGREE binding 20261117T042222Z and NOTES show each row goes through Adjacency.RowPut, which interns into ^NKG when the skeleton exists; docstring nodes_edges.py:383-393 matches the ontology, not the observation.
2. structure.multigraph.layout bullet 5 promises the losing writer retries once; its own metadata says no retry exists (the losing statement fails with a uniqueness error).
3. degree.cache.uncommitted bullet 3 "until the next rebuild": ^IVG.AdjNoLock is also killed by RemoveGraph, i.e. erase_graph (Adjacency.cls:440), as well as by the rebuild (:465).
4. temporal.owner and adjacency.one_writer contradicted by their own metadata (window reader and snapshot restore access the stores directly); graded absent with inspection contradicted.
5. structure.rebuilt lead contradicted for the interned snapshot (own flags, not a token stamp); freshness.py imported nowhere in the product.
6. NOTES links to old block locations: freshness_stamp, index_declaration, rebuild_reads → features/graph-structure.g5.md#…; traversal_strategy → features/graph-structure.g5.md#structure.adjacency; temporal_marker, temporal_stats → features/temporal.g5.md#temporal.structural.mark, #temporal.stats.writers.
7. coverage.md: undeclared row overstates; temporal.structural, .end, .adopt and degree.cache.erase rows use Proved/Suspected where rule 3 gives refuted; adjacency_maint NOTES names 20261117T074807Z as latest prove (latest 20261118T013554Z).
8. temporal.structural.end bullet 3 "unless the purge is asked to retire bare nodes": graph_structure NOTES records retire_bare_nodes=True as the purge default (temporal.py:623) — not checked beyond the NOTES.

## 7. Ranked uncovered
1. Bulk index rebuild and duplicates: bulk#o02–#o04 absent; #o01, #o05, #o06 partial (rebuild-before-return on success and failure — a failed rebuild is only logged, bug-str-009; %NOINDEX unique-key skip; ^NKG inside a caller transaction; pending_sync after rollback). Bind nodes_edges.py::bulk_create_edges, bulk_create_nodes, rebuild warn path :67-79, bulk_load_session; readers status().pending_sync, ^NKG, verify_graph.
2. Interned-snapshot freshness: rebuilt#o01, #o03, stale_read#o02, #o03 absent; stale_read#o01 partial. Bind TraversalBuild.cls::EnsureNKG (:393-425), BuildNKG, Adjacency.cls::MarkGraphGone, variable-length routing query.py :2454-2457, IndexNotSyncedError.
3. Token coverage per writer: token#o02, #o03 absent; #o01, #o04 partial (bug-str-016). Bind every $Increment(^KG("__version")) site (Adjacency.cls:92, label writes :767-787), snapshot restore (:48-58), algo_cache.py.
4. Undeclared namespaces: undeclared#o01 absent; #o02, #o03 partial; temporal.structural#o03, #o04, temporal.structural.ledger#o06 absent. Bind create_edge undeclared branch (:1221-1249), FillEdge and EdgeScan writers, temporal Python mirror (temporal.py:304-331).
5. Multigraph key allocation and clash retry: layout#o05, #o06 absent; #o04 partial (translator keyed inserts :10368-10386, create_edge).
6. Cypher CREATE/MERGE adopting marked rows: adopt#o04 absent (translator relationship SQL).
7. Degree whole-graph stamp path: warm#o09 (F-0406) absent; degree.cache#o03, warm#o01, #o08 partial (Adj.cls::AllWarm, bulk readers, Adjacency.cls::EndRebuild :857-869).
8. Rebuild serialization: adjacency#o02, #o03 absent (HD-0402; BuildKG, BeginRebuild, ^IVG.AdjW).
9. Single-owner rules: temporal.owner#o01, one_writer#o01 absent, contradicted (temporal_window.py, snapshot restore :1680-1691).
10. Smaller: end#o04 (Eraser.ForgetNodes); upgrade#o03, #o04 (predicate registry, seen-limit re-check, BackfillWalk); mark.readers#o02 (temporal export); adjacency#o04 (TraversalPaths graph scoping); declare#o06 (drift repair).

## 8. Iteration-60 residual mapping
store/iris_sql_store: undeclared#o03 (write_edges leaves the index stale); rebuilt.valid (_cached_algorithm). Translator
residue: layout#o05, #o06; adopt#o04; scan#o10, #o11; stale_read#o03. Install residue: declare#o06; upgrade#o03, #o04,
#o08. Temporal residue: temporal.structural#o03, #o04; .end#o04; .ledger#o01, #o05, #o06; temporal.owner#o01;
mark.readers#o02. Operator residue: bulk#o05, #o06; stale_read. None: GQL/GraphQL, SDK/CLI/HTTP admin,
load_networkx/load_obo, migrations.
Source-discovered omissions: AdjNoLock also cleared by RemoveGraph (Adjacency.cls:440); writer lock logs a console WARNING
once per process and graph (Adjacency.cls:68-71); iris_vector_graph/freshness.py has no caller (the rule stated for it
governs dead code).

## 9. Limitations
Split granularity (scan 11, warm 9, stats.writers 6); requirement-refuted plus Today-proved pairs cite the same witness
(scan#o10/#o11, upgrade#o08/#o09); process rules excluded as rationale (one_writer source-scan sentence, temporal.owner
"new operation" sentence); declare#o01–#o05 and stamp#o01–#o06 proved full scope may be generous (unit-level bindings);
temporal.structural.ledger#o04 rests on platform's exemption witness; contradictions mostly second-hand (spot-checked
WriterLock, bulk_load_session docstring, snapshot restore writer); no independent review.
