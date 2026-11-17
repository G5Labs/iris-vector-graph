# Product-wide inventory (master-owned; working copy, mirrored into Git as `.g5/uplift/consolidated/master-inventory.md`)

Frame: `member_reach.py` census at pin 3eaa79cf, 4,130 members. Baseline 4eb9ea30: union 698, active 448.
Score tool: `python3 $G5_RUN_STATE/master/tools/score.py <rev> <outdir>` (runs the revision's own
`member_reach.py`, unions with frozen in-census historical locators from `baseline/historical.json`).

Status legend: OPEN (not yet assigned), ASSIGNED (iteration n), DONE (iteration n, see handoff), BLOCKED, EXCLUDED.

## Uncovered workflows, ranked (consequence x tractability), unbound counts at baseline

| # | Workflow / area | Main members (unbound/total) | Status | Notes |
|---|---|---|---|---|
| 1 | Cypher built-in functions at run time (list/string/JSON/map/regex/percentile/type-error) | `CypherFn.cls` 17/17, `SqlProcs.CypherFnIVG*`+`JSONKEYS`+`Percentile*` ~20, translator function dispatch | DONE 47 (W54) | owner `query.functions`, model `cypher_fns`; bug-cyp-111..116; 12 SQL-only CypherFn bodies + percentiles still unbound |
| 2 | Finish draft W53 (kg_IVF/kg_BM25 SQL readers) + IVF cosine = dot product (draft bug-srch-109) | `SqlProcs.kgIVF/kgBM25`, `IVFIndex` Build/Search | DONE 47 | bug-srch-109 (Medium); kg_IVF bound; kg_BM25 unbound (needs BM25 scoring model) |
| 3 | (DONE 53: model sql_procs; residual 12 SQL-only CypherFn forwarders, LedgerRecords*) SqlProcs edges/paths/txn: `MatchEdges`, `MatchEdgesAllGraphs`, `DijkstraPath`, `TxnBegin/End/Undo`, `PropSet`, `backfilltemporalrows`, `rebuildedgeindices` | SqlProcs ~10 | PARTIAL 47 | Txn_* bound; MatchEdges/DijkstraPath/PropSet/backfill/rebuild open (first missing steps in iteration-47/HANDOFF.md) |
| 4 | Retrieval composition: `kg_VECTOR_GRAPH_SEARCH`, `kg_PPR_GUIDED_SUBGRAPH`, `kg_RERANK`, `multi_vector_search`, `kg_RRF_FUSE`, `PyOps.HybridSearch/FuseRanks/RouteVectorRows/VectorSearch/MetaPath` | operators.py 19/19, PyOps 15/15, vector.py 41 unbound | DONE 49 (W56) | model `retrieval_compose`; 6 owner blocks; bug-plt-113 H, srch-110 M, plt-114 M, srch-111/112 L; bug-srch-005 reproduced. Residual: REST deploy for srch-111/112, PyOps privilege reporting (ReadRows/ReadFailure/Lacks/NoteNoRegistry), MetaPath, bfs_vector_rerank, search_nodes_by_vector, CALL ivg.retrieve, IVF fallback in vector_search |
| 5 | (DONE 52: model operator_reports; residual routed edge vectors, multigraph verify_sync, failed-probe readiness, refused namespace, /indexes + ivg indexes list model rows, LedgerStatus) Operator reports: `status()`/`EngineStatus.*`, `capabilities`, `get_schema_visualization`, `snapshot_info`, HTTP `get_stats/get_metrics/get_indexes/get_schema` | status.py 21/22, cypher_api.py 35/44 | OPEN | counts that guide action |
| 6 | (DONE 51: model temporal_stats; residual latest-index exactness, get_edge_attrs/get_window_sources, legacy PurgeBefore, BulkInsert) Temporal analytics readers (`get_edge_velocity`, `find_burst_nodes`, `get_bucket_groups`, `get_distinct_count`) | TemporalIndex.cls 41/48, _engine/temporal.py 37/45 | OPEN | owned (`temporal.stats`), known divergences, no model |
| 7 | (PARTLY 56 via install_lifecycle) Embedding identity maintenance (`reconcile_recorded_dimensions`, `adopt_embedding_identities`, `list_quarantine`, `place_quarantined`, `measure_route_recall`) | embedding_identity.py 7, _engine/embeddings.py 29 | OPEN | |
| 8 | Imports `load_networkx`, `load_obo` | _engine (admin/load) | OPEN | expected repeat of bug-str-109 class |
| 9 | `ivg` CLI and HTTP admin routes beyond `/api/cypher` | cli.py 28/32, cypher_api.py admin_* | OPEN | |
| 10a | Cypher expression surface with run-time values (string fns, slices, size() of stored values, CASE, list comprehension, aggregation over stored values, functions in CREATE/SET maps, PropSet) | translator.py, SqlProcs.PropSet | DONE 48 (W55) | model `cypher_exprs`; 6 owner blocks; bug-cyp-117..125 (120 High); PropSet bound. Residual: driver 5.4 check for cyp-125, other CREATE shapes, SET += maps, zero-length strings model |
| 10 | (PARTIAL 54: model cypher_clauses; residual OPTIONAL MATCH aggregates, UNWIND grouping, -94 boundary, UNION floats/lists, CALL{} agg, FOREACH, SET +=, WITH *, ORDER BY mixed; ~660/717 translator unbound) Cypher translator clause semantics on Cypher-written data (aggregation/OPTIONAL MATCH/WITH/UNWIND/CASE/list comprehension/path funcs) | translator.py 697/717, parser.py 53, ast.py 54 | OPEN | largest raw gap; prior runs leaned on TCK; needs representative workflow check before any convergence claim |
| 11 | (PARTIAL 57: models traversal_strategy, adjacency_maint, rebuild_reads; residual str-115 for degree/PPR/native, create_edge vs BuildKG race, Traversal.cls 32 facades classify, iris_sql_store 124 unbound (execute_sql DML detection), ^NKG sketch sweep) SQL store layer `stores/iris_sql_store.py` | 140/149 | OPEN | check which public workflows reach it |
| 12 | Engine facade `engine.py` and `_engine/query.py` | 119/124, 116/124 | OPEN | largely delegates; justify shared relation or exclude |
| 12b | `store_protocol.py` (45 members) | 0/45 reached | OPEN-classify | iteration-60 challenge: a `typing.Protocol` of 44 `...` declarations; no behavior to bind; classify as declaration-only (exclude with justification) rather than add locators. `IRISSQLStore.execute_sql` accepts `read_only` and never reads it (no caller passes it) |
| 13 | (DONE 56: model install_lifecycle; residual forced class deploy, routines+grants, concurrent setups, place_quarantined real path) Schema / schema_name / class_deploy (install & DDL) | _engine/schema.py 68/83, schema.py 53/58, schema_name.py 44/47, class_deploy 21 | OPEN | |
| 14 | (PARTIAL 57, see row 11) Traversal builds and BFS (`TraversalBuild` 38/38, `Traversal` 33/34, `Adjacency` 33/34, `VarLength` 15) | iris_src | OPEN | prior: "internals of modeled decisions" - re-challenge |
| 15 | (DONE 55: model bolt_answers; residual shadow/compiled at reader, var-length LIMIT route, _decode_*_columns in Verus, Bolt 5 structs with Java/JS driver, query/v2 node shape, WebSocket Bolt) Bolt server | bolt_server.py 45/53 | OPEN | |
| 16 | SDK / host (`sdk.py` 42/43, `host.py` 38/42) | | OPEN | |
| 17 | Cypher `Exec.cls` / `Gen.cls` native executor internals | 55/59, 23/24 | OPEN | |
| 18 | (DONE 60: models ledger_client, ledger_verify from the test-obligation map; residual: delete-node mode and node-scope two-graph verify merge (q-led-004), enable's lock wait, transport failure after a commit, provider refusal premise, concurrent verify (q-led-006), correlation-index build effect on history, snapshot/upgrade ledger survival, NKG dirty marker candidate, server trusts the client fingerprint) Ledger client/replay/changeset | 35/42, 33/43, 28/29 | DONE 60 (repaired after review 60; validation residue closed in repair 2) | see [iteration-60 handoff](iteration-60/HANDOFF.md), [test obligations](iteration-60/test-obligations.md), [repair dispositions](iteration-60/repair/DISPOSITIONS.md) and [repair-2 handoff](iteration-60/repair2/HANDOFF.md) (counter row held without the head: bug-led-017 Medium); repair residual: D10 delete ops in `ledger_apply`, transport loss after commit (B4/CG-2), BC-3 inputs, `RecordVerify` stall, `from_connect` engines and `disable()`/`set_strict()` inside a caller's transaction (source only) |
| 19 | Migrations 3.2.0 -> 4.0.0 | 161/161 | BLOCKED-ish | needs reconstructed 3.2.0 install (~1 iteration) |
| 20 | Embedded in-IRIS execution (`embedded.py` 44/50), `IVG.CypherEngine` 18/18 | | BLOCKED | package not in container embedded Python (~1 iteration offline install) |
| 21 | Arno/NKG accelerators (ArnoAccel 31, NKGAccel 30, NKGAccelLoader 13, arno_bridge 21, _arno_gate 18, arno_readers 13) | | BLOCKED | library absent |
| 22 | Erasure, redaction, tenant removal (Eraser 23, LedgerRedact 21) | | EXCLUDED | security-related scope limit |
| 23 | FHIR (FHIRGraph.cls 72/77, fhir_graph.py, fhir_bridge) | | EXCLUDED | external provider |
| 24 | Cypher MERGE (`merge_rows.py` 26/26) | | EXCLUDED | quarantined subject |
| 25 | GQL schema (`gql/` 37) | | OPEN-low | sample API |

## Incomplete obligations (carry-forward)
- Review round 1 residual: Arno reader for bug-plt-113/114 (needs Arno); driver 5.4.x for bug-cyp-125/m2; no Verus claim for cyp-128/130/131/132; simple CASE with parameter test; multigraph rel-CREATE with parameter; 3 premise-named active bindings (driver_accepts_ast, iris_accepts_scalar_condition, filer_writes_same_text) kept active — next reviewer to validate; iteration-50 repairs need independent validation.
- Direct executable-body verification = 0 everywhere (bindings are transcriptions with native agreement).
- Probe-only claims open in Verus: bug-str-102, W41 (from retest).
- Unexplained: two-edge temporal batch window read returned one edge (W37).
- No independent reviewer has run since the cloud runs; playbook requires one per phase.

## Unresolved questions (pointers)
- Register: `.g5/Verus_verification/open_questions.md` (question-card refinements in 4eb9ea30 must be preserved).

## Iteration log (master)
| Iter | Session | Batch | Union | Active | Findings | Cost |
|---|---|---|---|---|---|---|
| base | - | - | 698 | 448 | - | - |
| 58 | 2ef0ca19 | W62 clause combinations + result decoders | 914 | 706 | new: cyp-155/156 M; cyp-149..152, plt-135 L; agg-001, cyp-142, cyp-138 strengthened | 37 min, $14.36 (2 sub-workers) |
| 57 | 763aedb5 | W61 store + traversal/adjacency | 907 | 696 | new: str-115 M (reads during sync() wrong), str-117 M (khop2_count_fast), str-113/114 L; F-1009 reproduced | 37 min, $21.31 (2 sub-workers) |
| 56 | 2a81ea7b | repairs review round 3 + install lifecycle | 886 | 662 | new: plt-127 H (Bolt rollback keeps writes; was F-1601), cyp-146 M, srch-116 M, plt-015 L->M; cyp-147/148, tmp-108, srch-113, plt-133/134 L; 4 rows relabelled | 38 min, $35.07 (4 sub-workers) |
| 55 | 6511d787 | W60 query pipeline + Bolt reader | 866 | 640 | new: plt-121/122/123, cyp-144/145 M; plt-124/125/126 L; cyp-125 settled (IRIS driver 5.3.2 vs 5.4.1) -> M + question query.parameters.drivers; F-1602 reproduced | 28 min, $12.82, 175k out tok |
| 54 | 9b48cf72 | W59 Cypher clauses over API data / default mode / params | 847 | 619 | new: cyp-135..138, 142, 143 M; cyp-139..141 L; question query.aggregation.keys.numbers | 37 min, $17.79, 208k out tok |
| 53 | 3b698118 | repairs review round 2 + SqlProcs/BM25/percentiles | 833 | 603 | new: tmp-105 M, plt-119 M, cyp-134 M, tmp-106/plt-120/cyp-133/tmp-107/str-112 L; models sql_procs, bm25_scoring, percentile | 45 min, $33.94 (4 sub-workers) |
| 52 | ff337b8c | W58 operator reports | 799 | 563 | new: plt-115 M (status misses routed vectors), plt-116 M (verify_sync drift loop), plt-117/118 L; routine_reporting claim for routed tables withdrawn | 26 min, $14.81, 159k out tok |
| 51 | ff816019 | W57 temporal statistics readers | 777 | 537 | new: tmp-103 M (HLL floor 11), tmp-104 M (label-set hash collision); tmp-002/003/009, F-0508/0509 strengthened | 28 min, $12.73, 178k out tok |
| 50 | ac0a2d19 | repairs from review round 1 (47-49) | 749 | 505 | new: cyp-126/127 M, cyp-128 M (probe), cyp-129..132 L; plt-113 expected corrected; 1 binding reclassified locator-only | 27 min, $18.03, 177k out tok |
| 49 | 93adbd59 | W56 composed retrieval | 747 | 503 | new: plt-113 H, srch-110 M, plt-114 M, srch-111/112 L; srch-005 reproduced | 22.8 min, $10.69, 149k out tok |
| 48 | fc80ac7b | W55 Cypher run-time expressions; PropSet | 726 | 480 | new: cyp-120 H, cyp-117/118/119 M, cyp-121..124 L, cyp-125 potential; simp-cyp-101/102 | 23 min, $10.68, 148k out tok |
| 47 | 1364fd9f | draft W53 + IVF cosine; W54 Cypher fns; Txn_* | 710 | 463 | new: srch-109 M, cyp-111..114 M, cyp-115/116 L; F-C0841 reproduced | 22.8 min, $12.13, 145k out tok |
