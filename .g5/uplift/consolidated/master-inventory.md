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
| 3 | SqlProcs edges/paths/txn: `MatchEdges`, `MatchEdgesAllGraphs`, `DijkstraPath`, `TxnBegin/End/Undo`, `PropSet`, `backfilltemporalrows`, `rebuildedgeindices` | SqlProcs ~10 | PARTIAL 47 | Txn_* bound; MatchEdges/DijkstraPath/PropSet/backfill/rebuild open (first missing steps in iteration-47/HANDOFF.md) |
| 4 | Retrieval composition: `kg_VECTOR_GRAPH_SEARCH`, `kg_PPR_GUIDED_SUBGRAPH`, `kg_RERANK`, `multi_vector_search`, `kg_RRF_FUSE`, `PyOps.HybridSearch/FuseRanks/RouteVectorRows/VectorSearch/MetaPath` | operators.py 19/19, PyOps 15/15, vector.py 41 unbound | OPEN | |
| 5 | Operator reports: `status()`/`EngineStatus.*`, `capabilities`, `get_schema_visualization`, `snapshot_info`, HTTP `get_stats/get_metrics/get_indexes/get_schema` | status.py 21/22, cypher_api.py 35/44 | OPEN | counts that guide action |
| 6 | Temporal analytics readers (`get_edge_velocity`, `find_burst_nodes`, `get_bucket_groups`, `get_distinct_count`) | TemporalIndex.cls 41/48, _engine/temporal.py 37/45 | OPEN | owned (`temporal.stats`), known divergences, no model |
| 7 | Embedding identity maintenance (`reconcile_recorded_dimensions`, `adopt_embedding_identities`, `list_quarantine`, `place_quarantined`, `measure_route_recall`) | embedding_identity.py 7, _engine/embeddings.py 29 | OPEN | |
| 8 | Imports `load_networkx`, `load_obo` | _engine (admin/load) | OPEN | expected repeat of bug-str-109 class |
| 9 | `ivg` CLI and HTTP admin routes beyond `/api/cypher` | cli.py 28/32, cypher_api.py admin_* | OPEN | |
| 10a | Cypher expression surface with run-time values (string fns, slices, size() of stored values, CASE, list comprehension, aggregation over stored values, functions in CREATE/SET maps, PropSet) | translator.py, SqlProcs.PropSet | ASSIGNED 48 | vein produced 4 Medium in 47 |
| 10 | Cypher translator clause semantics on Cypher-written data (aggregation/OPTIONAL MATCH/WITH/UNWIND/CASE/list comprehension/path funcs) | translator.py 697/717, parser.py 53, ast.py 54 | OPEN | largest raw gap; prior runs leaned on TCK; needs representative workflow check before any convergence claim |
| 11 | SQL store layer `stores/iris_sql_store.py` | 140/149 | OPEN | check which public workflows reach it |
| 12 | Engine facade `engine.py` and `_engine/query.py` | 119/124, 116/124 | OPEN | largely delegates; justify shared relation or exclude |
| 13 | Schema / schema_name / class_deploy (install & DDL) | _engine/schema.py 68/83, schema.py 53/58, schema_name.py 44/47, class_deploy 21 | OPEN | |
| 14 | Traversal builds and BFS (`TraversalBuild` 38/38, `Traversal` 33/34, `Adjacency` 33/34, `VarLength` 15) | iris_src | OPEN | prior: "internals of modeled decisions" - re-challenge |
| 15 | Bolt server | bolt_server.py 45/53 | OPEN | |
| 16 | SDK / host (`sdk.py` 42/43, `host.py` 38/42) | | OPEN | |
| 17 | Cypher `Exec.cls` / `Gen.cls` native executor internals | 55/59, 23/24 | OPEN | |
| 18 | Ledger client/replay/changeset | 35/42, 33/43, 28/29 | OPEN | ledger family modeled; check readers |
| 19 | Migrations 3.2.0 -> 4.0.0 | 161/161 | BLOCKED-ish | needs reconstructed 3.2.0 install (~1 iteration) |
| 20 | Embedded in-IRIS execution (`embedded.py` 44/50), `IVG.CypherEngine` 18/18 | | BLOCKED | package not in container embedded Python (~1 iteration offline install) |
| 21 | Arno/NKG accelerators (ArnoAccel 31, NKGAccel 30, NKGAccelLoader 13, arno_bridge 21, _arno_gate 18, arno_readers 13) | | BLOCKED | library absent |
| 22 | Erasure, redaction, tenant removal (Eraser 23, LedgerRedact 21) | | EXCLUDED | security-related scope limit |
| 23 | FHIR (FHIRGraph.cls 72/77, fhir_graph.py, fhir_bridge) | | EXCLUDED | external provider |
| 24 | Cypher MERGE (`merge_rows.py` 26/26) | | EXCLUDED | quarantined subject |
| 25 | GQL schema (`gql/` 37) | | OPEN-low | sample API |

## Incomplete obligations (carry-forward)
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
| 47 | 1364fd9f | draft W53 + IVF cosine; W54 Cypher fns; Txn_* | 710 | 463 | new: srch-109 M, cyp-111..114 M, cyp-115/116 L; F-C0841 reproduced | 22.8 min, $12.13, 145k out tok |
