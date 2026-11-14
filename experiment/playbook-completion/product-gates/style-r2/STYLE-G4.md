Module 15: 6 deviations of 5 conventions (primary sources: 6 of 5; secondary BRIEF.md: 0)
Module 16: 8 deviations of 5 conventions (primary sources: 7 of 4; secondary BRIEF.md: 1)
Module 17: 8 deviations of 3 conventions (primary sources: 8 of 3; secondary BRIEF.md: 0)
Module 18: 8 deviations of 5 conventions (primary sources: 8 of 5; secondary BRIEF.md: 0)

<!-- markdownlint-disable MD013 MD041 -->

# 3.5-style round 2, group G4: modules 15-18 against IVG's own documented conventions

Lane: product-gates. Observation only. Paths are relative to the audit root; every `path:line` was checked with `sed -n`/`grep -n` at the checkout, whose product tree equals pin `3eaa79cf` (`git diff --stat 3eaa79cf HEAD -- . ':(exclude)experiment'` is empty at HEAD `14678055`). Inspected-grade only: nothing was run.

- **Judged as round 1** (`product-gates/STYLE.md`): C-1 not counted (tool lane); C-3 and C-20 not judged; C-6..C-9 are judged on writes, and direct reads of `^KG` go to borderline as round 1's B-1; ObjectScript swallows go to borderline as round 1's B-2; a broad `except` on a write path that reports the failure to the caller (result field, HTTP error) is borderline as round 1's B-3; a swallow that only logs, passes, returns False/None or continues on a write path is a C-17 deviation; Python-issued `SELECT TOP ... ORDER BY` is borderline as B-4; a `Graph_KG` literal in a deployed class is not a C-35 deviation (B-5). Secondary-authority rules (C-21..C-26, `docs/dev/notes/research/alt-impl/BRIEF.md:38-42`) are counted separately.
- **C-18 reading**: a message that names a writing call conforms when it says the call writes or names the write ("creates", "records", "deploys", "erase"), as round 1 read it; `sync()`, `Register()` and `initialize_schema()` named bare do not.
- **New group conventions** (both conform in G4): **C-40G4-1** `iris-vector-rag` MUST NOT be a dependency (`.specify/memory/constitution.md:265-267`): absent from `pyproject.toml` and `uv.lock`. **C-40G4-2** IVG reads `IVG_SCHEMA_PREFIX`, never `IRIS_SCHEMA_PREFIX` (`docs/adr/0016-one-ivg-schema-per-namespace.md:20`): no in-scope file reads the latter.
- **Coverage**: "full" = read line by line; "sweep" = every convention search of the brief run over the whole file and every hit read in context, plus every write path the searches led to. Files over ~3,000 lines are sweeps by rule; so are `cypher_api.py` and `_engine/snapshot.py` as the task assigned. Many smaller files are also sweeps (see each module's Limitations).

## Module 15: integrations (FHIR, RDF, SHACL, PROV)

| File | Lines | Coverage | Conventions applicable |
| --- | --- | --- | --- |
| iris_src/src/Graph/KG/FHIRGraph.cls | 3111 | sweep (>3,000 lines); header and every write method read: Register, Rebuild, SyncOnce, Reinterpret, Schedule, Unschedule, CheckOwnTask, RunBatch, SyncAll/SyncDefinition, DropNode, SyncProps, DeleteEdge, EnsureNode, SQL helpers | C-4..C-9, C-14, C-17(B-2), C-18, C-19, C-21..C-26, C-35 |
| iris_src/src/Graph/KG/FHIRGraphSyncTask.cls | 29 | full | C-14, C-21, C-22 |
| iris_vector_graph/_engine/fhir.py | 482 | full | C-2, C-16, C-17, C-18, C-35 |
| iris_vector_graph/_engine/schema.py (materialize_inference, retract_inference, reify_edge, get_reifications, delete_reification: 2966-3397) | 432 | full (part named by scope) | C-2, C-4, C-17, C-18, C-35 |
| iris_vector_graph/_engine/rdf_export.py | 246 | full | C-2, C-16, C-17, C-35 |
| iris_vector_graph/_engine/fhir_graph.py; fhir_bridge.py; fhir_links.py; _rdf_utils.py; shacl.py; prov.py | 680; 408; 71; 287; 242; 268 | sweep | C-2, C-9, C-16, C-17, C-18, C-35 |
| sql/fhir_bridges.sql; sql/rdf_reifications.sql | 14; 9 | full | C-35 |
| scripts/ingest/load_umls_bridges.py (repo script, not in the package) | 138 | sweep; load_to_iris read in full | C-17, C-35 |

The FHIR anchor route of `cypher_api.py` and `ivg fhir` of `cli.py` are reviewed under modules 16 and 17.

Deviations (counted)

| ID | Conv. | Location | What deviates |
| --- | --- | --- | --- |
| D-15-01 | C-14 | FHIRGraph.cls:3-6 | The header says "Nothing else is copied: properties and codes stay in the repository and are read live". SyncProps copies each resource's category codes (`system\|code`) and `meta_profile` into `rdf_props` and makes category labels (2496-2570, comment 2496-2497); EnsureNode writes an `id` property (2612-2615); ResyncKey adds derived `in_patient_compartment` edges (2212, 2277) |
| D-15-02 | C-7 | FHIRGraph.cls:2475-2478, 2491, 2560, 2566, 2616 | Sets and kills `^KG("label", GKey, ...)` itself instead of `Graph.KG.Adjacency.PutLabel`/`RemoveLabel` (Adjacency.cls:768-787), ADR-0008:18-21. 2491, 2566 and 2616 run even where the label functional index is declared |
| D-15-03 | C-18 | FHIRGraph.cls:1724, 1728 | "FHIR graph ... is not registered; call Register() first": Register writes the `fhir_graphs` row (238-244, 259) and may rebuild the graph (264-265); the message does not say so |
| D-15-04 | C-17 | scripts/ingest/load_umls_bridges.py:77-78 | `except Exception: conn.commit()` around `CREATE TABLE`: a failed DDL is swallowed with no message |
| D-15-05 | C-17 | scripts/ingest/load_umls_bridges.py:92-93, 99 | Every refused INSERT is counted as a duplicate and reported as "duplicates skipped" |
| D-15-06 | C-35 | scripts/ingest/load_umls_bridges.py:66, 86 | Creates and fills `Graph_KG.fhir_bridges` by literal on a plain connection (126), whatever the namespace's IVG Schema |

Borderline (not counted)

- **B15-1 (B-1)**: FHIRGraph reads `^KG("out"/"in")` directly: 874, 954, 1090, 1259, 1520-1525, 1626, 2235-2250, 2446-2461 (writes go through Adjacency, below).
- **B15-2 (B-2)**: RecordError swallows its own `UPDATE ... last_error` failure (FHIRGraph.cls:3102-3109, empty `Catch`); Register's `Catch` (274-276) rolls nothing back after the upsert (existing F-1511).
- **B15-3 (C-14)**: header 8-9 says the FHIR-side schema names "come from Graph_KG.fhir_graphs"; `HS_FHIRServer.Repo`, `RepoInstance` and `SearchColumn` are fixed names (33, 179, 195, 215). Parameter comment 32 says SearchColumn is shared, so the header's "every table" is loose rather than wrong.
- **B15-4 (C-23, secondary)**: `$Get(..Interp(...))` and `$Get(..Cols(...))` (1439-1442, 2279, 2422, 2548, 2598). The rule's words cover any object property; these are `[ MultiDimensional ]` properties (82, 149), on which `$Get` is defined.
- **B15-5 (C-17, B-3 style)**: fhir.py:341-345 catches broadly per row on a write path, but puts the row in `error_ids` in the result (contract at 290-293).
- **B15-6 (C-35)**: sql/fhir_bridges.sql and sql/rdf_reifications.sql create objects in `Graph_KG`; no code or script loads them (setup creates both tables from `schema.py`).

Candidate findings

1. D-15-02: existing **F-C1540** (the FHIR graph build writes the label index itself; where the index is not declared, label changes do not move `^KG("__version")`).
2. D-15-04/05/06: **new candidate**. Module 15. *The UMLS bridge loader reports every refused INSERT as a duplicate and ignores a failed CREATE TABLE, in the fixed Graph_KG schema.* Evidence: scripts/ingest/load_umls_bridges.py:62-99. Why it is a defect: against a namespace whose table cannot be created or written (a missing privilege, another IVG Schema), the run ends "0 inserted, N duplicates skipped" and exits normally; the operator reads a complete load. Proposed S4 (repo script, not shipped: ontology INT-T1.80); confidence medium (source reading).

Conforming evidence: C-4 FHIRGraph.cls:1719-1720 (`ForName`/`ForIndex`), 1489, 1600; schema.py:3028, 3236 (`graph_index_key`). C-6 FHIRGraph.cls:2236, 2263, 2278, 2467, 2597 (Adjacency.Put/Remove). C-9 prov.py:186-187 (TemporalIndex). C-14 FHIRGraphSyncTask.cls:1-5 (each claim holds: Schedule creates, Unschedule deletes, busy is not an error at 18-22). C-17 schema.py:3068, 3086, 3235, 3258, 3327-3330, 3395 (`GraphWriteError` after rollback); rdf_export.py:62-76 and fhir.py:129-137 (`write_txn`). C-18 FHIRGraph.cls:183 ("which creates it"); fhir_graph.py:204-207. C-21 FHIRGraphSyncTask.cls:16, 26; FHIRGraph.cls:746, 767. C-22 FHIRGraph.cls:3073. C-25 FHIRGraph.cls:987, 2423. C-26 FHIRGraph.cls:569. C-35 fhir_graph.py:208, 600-604, 643, 666; fhir.py:37, 129-137; _rdf_utils.py:109-119; shacl.py:233.

Reviewer notes (not counted)

- rdf_export.py:137-141 and 201-205: `except Exception: pass` around binding a namespace prefix. The path writes an export file, not stored data.
- fhir.py:33-47, 64-83: a failed mapping-cache load leaves `{}`. `get_table_mapping` reloads only on `None` (26), so a transient failure hides every mapped table until `reload_table_mappings`. This is a read path, and 55-56 documents the empty cache.
- "collision" in its everyday sense (fhir.py:286; constants.py:5, 48; routing.py:20, 45) next to the glossary's Collision (CONTEXT.md:173-177).
- FHIRGraph.cls:3074 treats any prepare error whose text contains "-30" as table-not-found. That match is a substring, so it is wider than SQLCODE -30. FHIRGraph.cls:676 `(tInterval # 60 > 0)` evaluates correctly left to right.

Limitations: FHIRGraph's read-only report methods (CoverageReport, ConceptGaps, Group*, parsing helpers) were swept, not read. The six RDF/FHIR Python files marked sweep were not read line by line.

## Module 16: interfaces (sample API, GraphQL, Cypher HTTP, Bolt, MCP, demo servers)

Sample status: the docs call `api/` "the sample API" (CHANGELOG.md:493). They call `src/iris_demo_server` demos (its README.md:1-6) and the fraud server a demo app (ontology API-D9). `api/gql/resolvers/` and `api/gql/types.py` are not served; only unit tests import them (ontology 16-interfaces.md:135, API-T6.11). Deviations in samples are counted and marked.

| File | Lines | Coverage | Conventions applicable |
| --- | --- | --- | --- |
| api/main.py; api/dependencies.py | 155; 50 | full | C-2, C-17, C-18, C-35 |
| api/gql/resolvers/mutation.py (not served) | 243 | full | C-17, C-27, C-35 |
| api/routers/cypher.py; api/routers/fhir_event.py; api/models/cypher.py | 260; 365; 249 | sweep (fhir_event 140-170, 280-365 read) | C-2, C-17, C-18, C-35 |
| api/gql/{__init__,context,schema,loaders,types}.py, api/gql/core/{domain_resolver,loaders,resolvers,types}.py, api/gql/resolvers/query.py | 37-432 each | sweep | C-15, C-17, C-19, C-35 |
| examples/domains/biomedical/types.py; loaders.py | 355; 147 | sweep | C-17, C-35 |
| iris_vector_graph/gql/{__init__,constants,engine,pooling,resolvers,schema}.py | 11-208 each | sweep | C-17, C-35 |
| iris_vector_graph/cypher_api.py | 785 | sweep (as assigned) | C-17, C-18, C-35 |
| iris_vector_graph/bolt_server.py; api_auth.py; _api_key.py; security.py; routing.py | 1000; 200; 62; 182; 107 | sweep | C-15, C-17, C-35 |
| iris_src/src/Graph/KG/Service.cls; MCPService.cls; MCPToolSet.cls; MCPTools.cls | 347; 8; 19; 225 | full | C-14, C-21..C-26, C-27, C-35 |
| src/iris_demo_server/** (app, models/4, routes/3, services/5, objectscript/IVGDemo/FHIRLoad.cls) | 4,980 | sweep; FHIRLoad.cls full | C-17, C-22, C-35 |
| src/iris_fraud_server/{__init__,__main__,app}.py | 616 | sweep | C-17, C-35 (own `gs_*` tables, not IVG's) |
| scripts/mcp/ivg_mcp_server.py; config/mcp-graph.toml | 138; 18 | sweep (75-138 read); full | C-17, C-35 |

Deviations (counted)

| ID | Conv. | Location | What deviates |
| --- | --- | --- | --- |
| D-16-01 | C-15 | api/gql/core/resolvers.py:169-171 (sample) | Calls the IVG Schema qualifier of `rdf_props` "the schema prefix" (CONTEXT.md:25 says to avoid the term) |
| D-16-02 | C-35 | api/gql/core/resolvers.py:173, 209-211, 234-235, 250-251, 268; api/gql/loaders.py:30, 38, 85, 93, 139, 147, 193, 232, 262 (sample) | Names `Graph_KG` on the engine's plain connection instead of the engine's IVG Schema |
| D-16-03 | C-35 | api/gql/resolvers/query.py:79-92; api/gql/resolvers/mutation.py:47-76, 125-147, 206-228 (sample, not served) | Unqualified `nodes`, `rdf_labels`, `rdf_props`, `rdf_edges`, `kg_NodeEmbeddings`: they resolve in the connection's default schema (SQLUser, as resolvers.py:169-171 itself notes), not the IVG Schema |
| D-16-04 | C-35 | src/iris_demo_server/services/iris_biomedical_client.py:61, 83, 122, 135; fhir_graph_client.py:58, 101, 193, 213, 220; bio_demo_data.py:198, 200 (demo) | Reads `Graph_KG.*` by literal; the namespace's recorded IVG Schema is never consulted |
| D-16-05 | C-35 | scripts/mcp/ivg_mcp_server.py:89-90 | `set_schema_prefix("Graph_KG")` before `translate_to_sql`: the `sql` the tool answers names `Graph_KG` while the engine at 93 uses its own schema |
| D-16-06 | C-18 | api/main.py:60 (sample) | "setup has not finished; run initialize_schema()": names a writing call and does not say it writes (compare schema_name.py:28-35) |
| D-16-07 | C-17 | api/routers/fhir_event.py:164-165 (sample, deprecated route) | The background embedding write logs a WARNING on failure and nothing else; the reply has already said `queued_for_embedding: true` (359-365) |
| D-16-08 | C-24 (secondary) | iris_src/src/Graph/KG/MCPTools.cls:126, 137 | `SELECT TOP 10 ... ORDER BY cnt DESC` in ObjectScript |

Borderline (not counted)

- **B16-1 (C-15)**: security.py:125 "Remove schema prefix" names the qualifier of whatever table name `validate_table_name` is passed, not only the IVG Schema's.
- **B16-2 (C-35)**: MCPTools.cls:22 and 82 build `IRISGraphEngine(EmbeddedConnection(iris.sql))` with no `schema_prefix`, while the class's own literals (18, 114-137) are rewritten by the deploy. An engine is refused in a namespace that records another schema (schema_name.py:220-235). ADR-0016's words govern where objects live, not how a deployed class picks the engine's schema.
- **B16-3 (B-4)**: MCPTools.cls:209-214 `SELECT TOP ? ... ORDER BY score DESC` inside a `Language = python` method.
- **B16-4 (C-14)**: Service.cls has no class header (line 1), so it makes no claim to check (ARCHITECTURE.md:203 presumes one). MCPTools.cls:1 lists five tools; the class has six, and RunSQL (31-69) runs any SQL. The list omits a tool; it states nothing false.
- **B16-5 (C-17, B-3 style)**: write paths that catch broadly but return the failure to the client: cypher_api.py:396-400 (existing F-1610, F-C1602: labelled SyntaxError); api/gql/schema.py:222-223 (F-1607); bolt_server.py:616-622 (F-C1602); ivg_mcp_server.py:115-120 (`buildKGCompleted: false`, error text dropped).
- **B16-6 (C-19)**: api/gql/core/resolvers.py:189-195 compares string-stored `rdf_props.val` with `CAST(... AS DOUBLE)`. api/gql/core/types.py:169 documents the operators as "numeric comparisons" but not what a non-numeric value does.

Candidate findings

1. D-16-02: existing **F-1605**.
2. D-16-04: **new candidate**. Module 16. *The demo server's biomedical and FHIR panels read Graph_KG, not the namespace's IVG Schema.* Evidence: iris_biomedical_client.py:61-135, fhir_graph_client.py:58-220, bio_demo_data.py:198-200. Why it is a defect: in a namespace set up under another IVG Schema the panels read tables IVG does not use, or none, and show an empty or offline graph. This is the sample-API pattern of F-1605. Proposed S4; confidence low (a demo whose README quick start uses the default container, README.md:9-16).
3. D-16-07: related to existing F-1609 (the route is not all-or-nothing). No new candidate: the reply says only "queued".

Conforming evidence: C-17 api/routers/fhir_event.py:325-326, 345-346 (raise 500 "IRIS write failed"); cypher_api.py:668-678. C-18 Service.cls:67 ("until initialize_schema() creates it"); Service.cls:87 ("CreateWebApp changed nothing"). C-21 Service.cls:35/72, 78/92, 106/157, 173/262. C-22 Service.cls:41, 66, 191-192; FHIRLoad.cls. C-25 Service.cls:128, 191, 195, 219. C-26 Service.cls:41, 115, 201. C-27 PyOps.cls:335 via Service. C-35 iris_vector_graph/gql/engine.py:14-15; gql/resolvers.py:13, 38; api/gql/schema.py:174-178 and api/routers/cypher.py:129 (translate with `engine=`); api/main.py:52-65 (checks the record); Service.cls:160-161, 176 and MCPTools.cls:18 (deploy token, B-5). C-2: no `type: ignore` in module 16.

Reviewer notes (not counted)

- api/gql/loaders.py:44-45, 99-100, 153-154, 209-210, 239-240, 269-270: `except Exception: pass` on reads, so a failed read answers "not found". examples/domains/biomedical/types.py:121 records that the examples dropped this pattern.
- src/iris_demo_server/app.py:203 repeats FHIRGraph's stale header claim ("no copy of codes or properties", D-15-01).
- MCPTools.EvidenceSearch treats the query as a node id (existing F-1613). The stdio server's LoadGraph counts are always 0 (existing F-C1640, ivg_mcp_server.py:124-125).
- api/gql/resolvers/mutation.py:75-78 inserts vectors directly, past the embedding registry's identity check. It is not served.

Limitations: the demo servers' HTML, JS and CSS, the GraphQL schema shapes and the HTTP routes' status codes have no documented convention. cypher_api.py, bolt_server.py and the api/gql modules were swept, not read line by line.

## Module 17: operations (CLI, status, hosts, SQL adapter routing, SDK, errors, helpers, Meta/PyOps/SQL/JsonKeys)

| File | Lines | Coverage | Conventions applicable |
| --- | --- | --- | --- |
| iris_vector_graph/stores/iris_sql_store.py | 4279 | sweep (>3,000 lines); routing, guards, writes and knn read; algorithm bodies left to module 10 | C-2, C-4, C-17, C-27, C-31, C-35 |
| iris_vector_graph/errors.py | 244 | full | C-16, C-18 |
| iris_vector_graph/dbapi_utils.py | 279 | sweep (1-30, 100-279 read) | C-17, C-27 |
| iris_vector_graph/engine.py (construction 277-400, from_connect 487, from_wrapper 517, capabilities 1742-1812) | 1944 | sweep of the named parts | C-15, C-17, C-18, C-35 |
| iris_vector_graph/_engine/admin.py (module 04's verify_sync, verify_graph, status().adjacency excluded) | 1041 | sweep | C-15, C-17, C-18, C-35 |
| iris_vector_graph/{cli,status,capabilities,host,embedded,_iris_compat,store_protocol,sdk,index_config,index_protocol,exceptions,result,utils,constants,models,__init__}.py; stores/{lazy_kg,__init__}.py; _engine/__init__.py | 0-549 each | sweep | C-2, C-4, C-15, C-17, C-18, C-31, C-35 |
| iris_src/src/Graph/KG/Meta.cls; SQL.cls; JsonKeys.cls | 90; 22; 20 | full | C-8, C-9, C-14, C-21..C-26, C-35 |
| iris_src/src/Graph/KG/PyOps.cls | 430 | sweep (1-30, 192-430 read) | C-14, C-24, C-27, C-28, C-35 |
| scripts/setup_security.sql; scripts/install-embedded-deps.sh | 20; 42 | full | C-35 |
| docker-compose.yml; docker/**; deploy/**; pyproject.toml; uv.lock | 487 + manifests | sweep | C-40G4-1 (no style rule for recipes) |

Deviations (counted)

| ID | Conv. | Location | What deviates |
| --- | --- | --- | --- |
| D-17-01 | C-27 | stores/iris_sql_store.py:2633-2634 | `TO_VECTOR(?, {dtype}, {len(query_vector)})` converts a query vector with the 3-argument form ADR-0005:16-19 forbids. The comment (2628-2632) cites ADR-0005; the width is the query's own, so nothing is reshaped |
| D-17-02 | C-27 | dbapi_utils.py:253, 268 | `vector_similarity_search` converts the query with `TO_VECTOR(?, {dtype}, {dim})`, `dim = len(query_vector)` |
| D-17-03 | C-17 | dbapi_utils.py:141-167 | `insert_vector` answers a refused INSERT or UPDATE with `return False` (ERROR log) |
| D-17-04 | C-17 | dbapi_utils.py:197-204 | `create_hnsw_index` answers a refused CREATE INDEX with `return False`, DEBUG log only |
| D-17-05 | C-17 | dbapi_utils.py:228-235 | `create_ivfflat_index`: the same |
| D-17-06 | C-17 | stores/iris_sql_store.py:1287-1295 | `except Exception: pass` around the INSERT into the legacy `rdf_edges_adjout` inside `write_edges`' transaction. The comment means "table absent", but every error is swallowed |
| D-17-07 | C-18 | errors.py:86 | `IndexNotSyncedError` remedy "Call engine.sync() before querying." does not say `sync()` writes |
| D-17-08 | C-18 | status.py:273-274, 300, 304 | The status report names `initialize_schema()` ("logs why") and `engine.sync()` twice without saying they write |

Borderline (not counted)

- **B17-1 (C-17, B-3 style)**: the failure is returned in `IVGResult.error`: iris_sql_store.py:1538-1554 (`execute_sql`, USER_GUIDE §3), 2687-2689 (`write_temporal_edge`), 2759-2782 (bulk fallback, `first_error`).
- **B17-2 (C-17)**: engine.py:394-397 swallows a failure to give a foreign `store=` object the strict-mode guard (marked "foreign store objects"); this is construction, not a data path.
- **B17-3 (C-17)**: embedded.py:542-546 swallows a failed ROLLBACK; commit (535-538) deliberately raises.
- **B17-4 (C-18)**: errors.py:72-73 "Call engine.embed_nodes(...)". The verb implies storing vectors without saying it writes.
- **B17-5 (C-14)**: Meta.cls:1-2 describes a key/value store; HnswIndexes (38-61), GetNKG and GetKG (70-88) go unmentioned. PyOps.cls has no class header (line 1).
- **B17-6 (C-9, B-1)**: Meta.cls:79-88 GetKG reads any `^KG` subscripts a Native API caller names, the temporal stores included (ADR-0002:9-11); no in-repo caller passes one. Other direct reads: lazy_kg.py:58-79, 155-267 (documented, ARCHITECTURE.md:186); iris_sql_store.py:1853-1856.
- **B17-7 (B-4)**: PyOps.cls:337-344 `SELECT TOP k ... ORDER BY score DESC` inside a `Language = python` method.
- **B17-8 (C-17)**: admin.py:957-969 `kill_query` returns False with a WARNING (documented at 958-961). It ends a process; it does not change stored data.

Candidate findings: none new. D-17-01/02 change no answer, because the declared width equals the query's own. D-17-03..05 answer False under a declared `-> bool` contract. D-17-06 touches a legacy side table. Related existing findings in the swept files: F-1705, F-1706, F-C1704 (dbapi_utils), F-1702 (embedded.py:312-321), F-1712 (lazy_kg).

Conforming evidence: C-2 iris_sql_store.py:566-567 (the one `type: ignore`, justified in place). C-4 lazy_kg.py:128; iris_sql_store.py:2032-2034 (passes the name; ForIndex derives). C-15 status.py:149 and admin.py:379-388 (SQLUser named for the legacy objects); engine.py:287, 342 (`schema_prefix` names the setting). C-17 iris_sql_store.py:1299-1300; cli.py:146-148 (and every other command: message, exit 1). C-18 admin.py:435-436 ("records the schema"); engine.py:1810 ("deploys them"); PyOps.cls:228 ("creates it"); errors.py:47 ("Create it"). C-27 dbapi_utils.py:134, 154 (stored values, not queries); PyOps.cls:335. C-28 PyOps.cls:24-54, 111. C-31 lazy_kg.py:27-30, 215-235 (Adj.Degree). C-35 iris_sql_store.py:770-787; admin.py:720; engine.py:435-460; constants.py:34 (static-helper text, rewritten by SchemaCursor, schema_name.py:404-409); setup_security.sql:2-3. C-21/C-22/C-25 Meta.cls:18-22, 35; SQL.cls:9. C-40G4-1 and C-40G4-2: conform.

Reviewer notes (not counted)

- admin.py:527, 562, 572 and 826 name `engine.sync()` or `initialize_schema()` without saying they write. They sit in module 04's status().adjacency and verify_sync, so they are not counted here; module 04's reviewer should check them.
- scripts/install-embedded-deps.sh:9, 23 cite AGENTS.md, which is absent at the pin (round 1 L-1).
- The deploy recipes have no documented style rule; their defects are existing F-1708, F-1709, F-1710, F-C1741.

Limitations: the SQL adapter's algorithm bodies (PPR, centralities, communities, BFS adapters) belong to module 10 and were not judged. Most module 17 Python files were swept, not read line by line.

## Module 18: snapshot

| File | Lines | Coverage | Conventions applicable |
| --- | --- | --- | --- |
| iris_src/src/Graph/KG/Snapshot.cls | 166 | full | C-8, C-9, C-14, C-21..C-26 |
| iris_vector_graph/_engine/snapshot.py (save_snapshot 797-1049, snapshot_info 1050-1074, restore_snapshot 1076-1610, helpers 1-438 and 1612-1692) | 1904 | sweep (as assigned); restore and the two global helpers read in full | C-2, C-4, C-7..C-9, C-10, C-17, C-27..C-35 |
| iris_vector_graph/cypher_api.py POST /admin/snapshot | 668-678 | full | C-17 |

Deviations (counted)

| ID | Conv. | Location | What deviates |
| --- | --- | --- | --- |
| D-18-01 | C-7 | snapshot.py:1654-1692 (1679), 48-57, 1588 | In a namespace without the adjacency index (1659-1662) the restore writes `^KG("out"/"in"/"label")` with `iris_obj.set` and sets the version stamp `^KG("__version")` itself. ADR-0008:18-21 names snapshot restore among the writers that must go through the one module (also ADR-0011:12) |
| D-18-02 | C-8 | snapshot.py:1654-1692; plan 134-135, 148-149 | The restore sets `^KG("prop")`, `("labelset")`, `("deg2p")`, `("deg2p_exact")` and kills `("degw"/"degc"/"gen", graph)` (1689-1691) directly, outside the stores' owners |
| D-18-03 | C-9 | snapshot.py:136-144 (plan), 1612-1652 (save walk), 1654-1692 (restore) | The six temporal stores are read and written by ad-hoc global scans outside TemporalIndex, a cross-graph admin operation ADR-0002:34-36 says must be a TemporalIndex classmethod |
| D-18-04 | C-17 | snapshot.py:1683-1684 | A global line the restore cannot write is logged at DEBUG and dropped; it is neither counted nor raised |
| D-18-05 | C-17 | snapshot.py:1200-1203 | `_register_endpoints`: a refused node INSERT is logged at DEBUG only |
| D-18-06 | C-17 | snapshot.py:1229-1231 | A failed FHIR-table DDL statement is a WARNING and the restore carries on |
| D-18-07 | C-17 | snapshot.py:1505-1508 | A failed route-cache invalidation after routed tables were recreated is DEBUG only |
| D-18-08 | C-29 | snapshot.py:394, 1679 | `^BM25Idx` (its `cfg N`, `df`, `doc`, `tf`) is written with plain Native API sets, outside BM25Index and its write lock `^BM25Idx(name,"lock")` (BM25Index.cls:406, 535; ADR-0007:5, 10) |

Borderline (not counted)

- **B18-1 (C-14)**: Snapshot.cls has no class header (line 1).
- **B18-2 (B-2)**: Snapshot.cls:16-19 (an export that fails is left out silently), 31-32 (an import that fails is not counted), 56 (`%Save` status dropped). Existing F-1806 and F-C1803 cover the class's exposure.
- **B18-3 (C-32)**: the restore writes `out`/`in` without the shared lock `^IVG.AdjW` and without bumping `gen`, then kills `degw`, `degc` and `gen` for each graph it wrote (1685-1691). ADR-0012:17 says a killed cache stays correct, and :31-32 allows a justified exception; the comment at 1685-1687 gives the justification.
- **B18-4 (C-34)**: the restore writes `^IVG.TemporalStructural` directly (163, 408). ADR-0015:12-13 says only TemporalPolicy sets it; its table at :29 lists snapshot/restore as carrying the registry.
- **B18-5 (C-17, B-3 style)**: per-row failures are counted in `failed_rows` with the contract at 1087-1088: 1299-1304, 1359-1368, 1452-1455, 1488-1490, 1541-1550.
- **B18-6 (C-17)**: `_insert_row` (1154-1173) is `except Exception: return False` verbatim, but nothing calls it.
- **B18-7 (B-1)**: save reads every exported `^KG` subtree directly (1612-1652).

Candidate findings

1. D-18-04: existing **F-C1802**.
2. D-18-03: existing **F-1805** (a merge restore overwrites the temporal aggregates).
3. D-18-08: **new candidate**. Module 18. *A merge restore overwrites a BM25 index's corpus counters with the archive's.* Evidence: snapshot.py:394, 1654-1692 (1679); BM25Index.cls:8, 15 (`cfg N`, `df` layout), 406, 535 (writer lock); ADR-0007:5. Why it is a defect: `merge=True` keeps the live index's documents but replaces `N` and each `df(term)` with the archive's values. Neither then counts the documents the index holds, so BM25 scores drift with no error. This is the BM25 analogue of F-1805. Proposed S3; confidence medium (source reading).

Conforming evidence: C-4 the restore uses the archive's stored keys and derives none (1680-1681). C-10 there is no `Kill ^NKG`; the restore raises the `^NKG` version past both values (37-45). C-17 `_commit` raises naming what is and is not restored (1205-1216); a global that cannot be imported raises (1575-1582); POST /admin/snapshot raises 500 (cypher_api.py:677-678). C-18 the restore_snapshot docstring opens "...; writes." (1082). C-27 the restore stores vectors and converts no query (1345, 1355, 1476, 1484). C-28 identity is restored as the `embedding_registry` table (118). C-31 `deg`/`degp` are skipped (349, 1658). C-33 `^IVG.CypherCompiled` is never archived (387-410). C-35 `@runs_in_ivg_schema` (797, 1076); `self._t(short)` (1408); `restorable_globals(schema)` (1555). C-9 Snapshot.cls:95-105 confines its `$Name` indirection to the vector-index globals (contrast D-10 of round 1). C-22/C-25/C-26 Snapshot.cls:17, 32, 82, 111, 127, 138.

Reviewer notes (not counted)

- STORE_PLAN still exports and restores `^KG("prop")` (148), which ARCHITECTURE.md:107 calls retired.
- On save, a route with no width (329-335) or one that is unreadable (978-992) is a WARNING and the archive goes without it (export path; existing F-C1804 for edge routes).

Limitations: import_rdf, load_networkx, load_obo and NDJSON import/export in snapshot.py are outside the module 18 scope and were not judged. `_engine/snapshot.py` was swept as assigned, not read line by line outside restore and the global helpers.

## Group limitations

- **L-G4-1**: G4 covers about 40,000 lines in roughly 100 files. Only the files marked "full" were read line by line; every other file was covered by the brief's convention searches, with each hit and each write path read in context. A non-searchable deviation, such as a false claim in a Python docstring, may be missed in sweep-only files. C-14 is complete: every in-scope Graph.KG class header was read.
- **L-G4-2**: no documented rule exists for Python docstrings, naming or comments beyond the tools (round 1 L-3), or for ObjectScript layout (round 1 L-2). The same holds for HTTP route and error-body design, GraphQL schema naming, the demo pages' HTML/JS/CSS, shell, Dockerfile and compose style, CLI exit codes and help text, log levels, and production code reading test fault-injection globals (FHIRGraph.cls:1920-1922, 1970).
- **L-G4-3**: C-3 and C-20 were not judged; C-1 was left to the tool lane.
