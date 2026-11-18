# Check status and repair indexes

Use these checks to see what a namespace reports as ready, whether its derived stores are in sync, and how a rebuild can affect readers. To inspect ledger history against live data, see [ledger administration](ledger.g5.md).

## Definitions

- **Integer adjacency copy**: `^NKG`, the copy of the adjacency index the graph algorithms read. It has no graph dimension: an edge held by two graphs is one entry. `engine.sync()` rebuilds it.
- **Pending-sync flag**: one engine's own note that it wrote rows it left for `sync()` to put in the integer copy. Other engines and processes do not see it.
- **Readiness flag**: one of the status report's `ready_for_*` answers, which an operator reads before running the operation it names.
- **Adjacency index**: the native index of each graph's out-edges, in-edges and node labels, used for neighbor lookup, walks and the graph algorithms.
- **Declared index**: an adjacency index that the database maintains from the edge and label tables on every row change.
- **Rebuilt store**: a derived store that is rebuilt from the tables rather than kept current on every write.

## HTTP health checks

<a id="access.health"></a>
[I · access.health]

`/health` needs no key and answers status only, with no counts and no error text. It answers unhealthy when the database does not respond. The sample API's `/health` also answers unhealthy when the namespace's schema record is missing or names another schema; the HTTP server's runs a node count instead.

- Working assumption: Keep current failure visibility after startup outage; retry/rebuild needs a lifecycle policy with bounded attempts and readiness semantics.

<a id="access.health.lifecycle"></a>
[D · access.health.lifecycle]

Health reflects both the probe and the engine retained by the app.

- The sample API captures its engine when created. Failed automatic construction or first connection access still starts an app, but health stays unavailable until recreation; an already-bound engine can recover when its probe succeeds again.
- Injecting an engine whose first connection access fails raises during app creation, rather than starting the engine-absent app.
- The Cypher HTTP server constructs an engine when its cache is empty and retries failed construction on a later request. A later health-query failure retains that engine; a successful probe on it can recover health.
- Reset tries to close the engine and clears the cache even if close raises, allowing later replacement. A normal query's first raised exception resets and retries once; a folded result error does not reset, and a second exception stops with the replacement cached.

## Check readiness and synchronization

<a id="install.status"></a>
[I · install.status]

Status reports current row counts across every graph, while the ordinary count methods report the default graph or the graph named by the caller. Its embedding totals count each distinct legacy or registered table of that kind, treating an older registry row with no kind as a node route.

- An install without a registry still reports its legacy embedding counts.
- A registered table that cannot be counted is named as an error, and completed counts remain available.
- If the graph census fails, the human report marks the graph size as unknown rather than printing an invented zero; the structured status keeps completed counts and probe errors.
- Today only the human report keeps that distinction: `/server`, `/metrics` and the readiness flags read a failed count as zero ([install.status.readers](#install.status.readers), [bug-plt-119](../../Verus_verification/bugs_issues.md#bug-plt-119)).
- Today on IRIS no registered table is counted: the registry read answers each name upper-cased and the name test expects lower case, so the totals are the legacy tables' rows only ([bug-plt-115](../../Verus_verification/bugs_issues.md#bug-plt-115)).

<a id="install.status.readiness"></a>
[I · install.status.readiness]

Each readiness flag is computed from the same probe as the report's counts, over every graph, and should say whether the operation it names would answer.
- `ready_for_bfs` is true when the adjacency index holds an edge and some edge row exists. Where the index is declared, that is exactly "some edge row exists".
- `ready_for_multihop_bfs` adds that the adjacency's predicate entries are consistent (`kg_predicates_consistent`) and that the ObjectScript or Arno path is there; it does not require the integer copy. Variable-length matches answer without it.
- `ready_for_vector_search` is true when the node-vector total is above zero; `vector_index_state` is `absent` with no vectors, `empty` with vectors and no ANN index (the report says "searched by a scan"), and `ready` with an ANN index.
- `ready_for_edge_search` is true when the edge-vector total is above zero.
- `ready_for_full_text` is true while some BM25 index exists, and false again once the last one is dropped.
- The vector totals count every table of their kind, as spec 230 says. ADMIN_GUIDE's older field table describes `ready_for_vector_search` as "the default embedding table holds vectors" and `kg_edge_count` as equal to the edge rows; the code caps that count at 10000.
- Today the vector totals leave out every routed table, node or edge, so a namespace whose vectors are all routed reads `absent` and not ready while a search on that graph answers ([bug-plt-115](../../Verus_verification/bugs_issues.md#bug-plt-115)).
- Today a flag whose count probe failed reads False rather than unknown, for example `ready_for_bfs` for a role that may not read the edge rows while traversals answer ([bug-plt-119](../../Verus_verification/bugs_issues.md#bug-plt-119)).

<a id="install.status.sync"></a>
[I · install.status.sync]

The report's sync state and `pending_sync` show only the calling engine's pending-sync flag. They do not say whether the integer copy is built; `adjacency.nkg_populated` says that.
- The flag is set by a `bulk_load_session` inside the caller's transaction and stays set after the caller's commit or rollback, until that engine runs `sync()`. Another engine or process reports False.
- On a namespace set up while empty, the first edges reach the adjacency index but not the integer copy, until the first `sync()`. Meanwhile the report says "in sync" and `nkg_populated` is False.
- A delete or erase drops the integer copy and clears the flag; the next reader of the copy rebuilds it. Meanwhile the report says "in sync" and `nkg_populated` is False.
- After the first `sync()`, an edge write puts a new triple into the integer copy too, so it stays current without another sync.

<a id="install.status.verify_sync"></a>
[I · install.status.verify_sync]

`verify_sync()` reports drift when the edge rows outnumber the integer copy's edge count, or when this engine's pending-sync flag is set. With `heal=True` it runs `sync()` on drift and reports the result as healed and in sync without checking again.
- The documented use is `if not engine.verify_sync(): engine.sync()`; it is meant to report in sync after a sync on a quiet namespace.
- Today, once two graphs hold the same source, predicate and target, the integer copy counts that edge once. Every check then reports drift, `heal=True` reports healed, and the next check reports drift again; no `sync()` clears it ([bug-plt-116](../../Verus_verification/bugs_issues.md#bug-plt-116)).
- After a delete or erase, it reports drift until the copy is rebuilt, while the status report says "in sync" ([install.status.sync](#install.status.sync)).
- It cannot see rows deleted without the copy following, because it only checks rows outnumbering the copy. [verify_graph](../architecture/adjacency-and-derived-data.g5.md#structure.adjacency) checks one graph both ways.

<a id="install.status.capabilities"></a>
[I · install.status.capabilities]

`engine.capabilities` says what the namespace has deployed. Each engine reads it once, from the class dictionary and two markers that setup writes when it finds edge rows to build from.
- `sync()` sets `kg_built` only in the engine that ran it and never sets `nkg_built` or the markers.
- So on a namespace set up while empty, every engine created later reads `kg_built` and `nkg_built` False whatever is built, until setup runs again while edges exist. Meanwhile personalized PageRank skips its ObjectScript fast path in those engines ([bug-plt-117](../../Verus_verification/bugs_issues.md#bug-plt-117)).
- Running setup again re-detects the capabilities and sets both markers once edges exist, from any engine.
- Working assumption: the store's `capabilities()` is a fixed list of what the adapter implements, every algorithm True, with only the Arno entries live; it is not a report of what this namespace can run. Read availability from `engine.capabilities` and `status()` ([open question](../../Verus_verification/open_questions.md#HD-1703)).

<a id="install.status.readers"></a>
[I · install.status.readers]

The HTTP and command-line reports read the same facts through different readers, so their counts can differ by design.
- `GET /server` carries `status()`'s counts, adjacency facts and probe errors, and `GET /metrics` its counts as numbers; both count every graph. Neither carries `unknown`, and `/metrics` carries no errors either.
- Today a count that failed therefore reads 0 there: `ivg_nodes_total 0` for a scraper's role that may not read the node rows ([bug-plt-119](../../Verus_verification/bugs_issues.md#bug-plt-119)).
- `GET /stats` and `GET /schema` count the default graph's nodes and edges; with nodes in a named graph they answer fewer than `/server`. `/stats`'s embedding count reads the legacy table only.
- `GET /indexes` lists the adjacency indexes as `ONLINE` or `NOT_BUILT`, and each BM25, IVF and PLAID index by name as `ONLINE`, even one that indexed no document. It lists HNSW indexes only on the legacy tables.
- `ivg status`, `ivg schema status` and `ivg indexes list` print the answers of `/server`, `/schema` and `/indexes` unchanged. `ivg status` exits 0 whenever the server answers, even when the answer lists probe errors.
- None of them shows the pending-sync flag; the server's engine wrote nothing of its own, so its flag is always False.

<a id="install.status.ledger"></a>
[I · install.status.ledger]

The report's ledger line says whether the revision ledger is enabled and, when it is, its head sequence and its commit and rejection counts. A read that fails is reported, and the line then says unknown.
- The genesis revision of `enable()` counts as a commit; a refused commit adds a rejection and leaves the head where it was.
- Without the Native API resources the ledger's state cannot be read, and the line says unknown, as documented.
- Today a failed read of the counters, for a role without SELECT on the ledger's counter table, shows "0 commits · 0 rejections" with no error ([bug-plt-120](../../Verus_verification/bugs_issues.md#bug-plt-120)).

<a id="install.status.diagram"></a>
[I · install.status.diagram]

`get_schema_visualization()` draws one node per label and one relationship per predicate, over every graph. A label's properties come from one sampled node, and a predicate's ends from the labels of one sampled edge's endpoints.
- An endpoint without a label is given id 0, which is also the id of the first label in sorted order. Such a relationship is drawn from or to that label ([bug-plt-118](../../Verus_verification/bugs_issues.md#bug-plt-118)).

## Find and repair index drift

<a id="structure.drift"></a>
[I · structure.drift]

A declared adjacency index cannot drift from its rows, and declaring it on an install that has drifted repairs the drift.
- With a declared index, a rebuild after any mix of edge creates, single-relationship deletes, edge, node and prefix deletes and weight changes leaves every entry as it was.

<a id="structure.rebuild"></a>
[I · structure.rebuild]

A rebuild recreates the adjacency index from the rows and then the interned snapshot from the index, and running it again is safe. With a declared index the adjacency never needs it; the interned snapshot still does after bulk loads and erasures.
- The SQL function `rebuild_edge_indices(schema)` runs `BUILD INDEX` on `nodes`, `rdf_labels`, `rdf_props` and `rdf_edges` and answers 4; rows and edge reads are unchanged.
- It refuses a schema that is not an SQL identifier before any statement runs. A caller without `%BUILD_INDEX`, or a schema without these tables, gets an error naming the table, never 0.

- Working assumption: that an early failure leaves the previous adjacency, and a later one leaves a partial index whose degree cache is cleared, never wrong.
- Without the accelerator library, `sync()` still rebuilds the interned snapshot with the ObjectScript builder.
- Today, with a declared index, the rebuild empties the adjacency index and refills it row by row while other sessions read it, so for its duration a k-hop read can answer the start alone, a path length no path, a breadth-first walk blank types, and a native Cypher variable-length count 0; writes made during the rebuild are kept ([finding](../../Verus_verification/bugs_issues.md#bug-str-115)). Working assumption: readers see the old index or the new one, never the emptied one, as the interned snapshot's live rewrite already promises ([open question](../../Verus_verification/open_questions.md#structure.rebuild.failure)).

<a id="structure.verify"></a>
[I · structure.verify]

`verify_graph` reports one graph's adjacency entries with no row behind them, its rows with no adjacency entry, and its current degree-cache entries that disagree with a recount. Its `ok` answers only whether this graph's adjacency agrees with its rows.

## Metadata

### access.health

- design-verified

- uncertain
- Formal: [health/provider/lifecycle contract](../../Verus_verification/models/service_health/service_health.rs), [source roles and evidence limits](../../Verus_verification/models/service_health/NOTES.md).

- Sources: [ADMIN_GUIDE §5](../../../docs/ADMIN_GUIDE.md); [api/main.py database_problem](../../../api/main.py); [CHANGELOG v4.7.0](../../../CHANGELOG.md)
- agent
- operations, security

The schema-record check was added to the sample API's `/health` in 4.6.3 ([CHANGELOG](../../../CHANGELOG.md#L493-L499); [api/main.py](../../../api/main.py#L40-L63)); the HTTP server's `/health` ([cypher_api.py](../../../iris_vector_graph/cypher_api.py#L268-L285)) does not check it. The HTTP server's `/health` holds the engine lock and counts nodes, so it serializes behind other requests.

Open questions: [Should the sample API retry construction after a startup outage?](../../Verus_verification/open_questions.md#q-iter-006)

State machines: [service health](../../Verus_verification/models/service_health/manifest.json)

### access.health.lifecycle

- design-verified
- agent
- operations
- user-facing-behavior
- Expands: [Health](#access.health).
- Formal: [service health](../../Verus_verification/models/service_health/service_health.rs), [qualified source roles](../../Verus_verification/models/service_health/NOTES.md).

Evidence: [84 actual Python/in-process ASGI checks and provider controls](../../Verus_verification/models/service_health/NOTES.md). Readiness is probe-specific, not a promise that every feature works or an external database will recover. api.main roles stay outside the historical member census; constructor/SQL/native-record/network/concurrent providers remain explicit limits.

State machines: [service health](../../Verus_verification/models/service_health/manifest.json)

### install.status

- design-verified
- Sources: [USER_GUIDE, status counts every graph](../../../docs/USER_GUIDE.md#L1203); [ADMIN_GUIDE, status fields and unknown probes](../../../docs/ADMIN_GUIDE.md#L920); [registry-kind and partial count tests](../../../tests/unit/test_230_status_counts.py); [report graph scope](../../../tests/unit/test_460_r050_status_counts_every_graph.py); [failed census and unknown report](../../../tests/unit/test_460_r050_status_unknown.py)
- Verus: [routine_reporting.rs](../../Verus_verification/models/routine_reporting/routine_reporting.rs) `theorem_raw_catalog_to_final_report`, `theorem_route_tables_never_double_count`, `theorem_registry_kind_and_shape_both_required`, `theorem_failed_table_keeps_other_counts` and `theorem_failure_is_unknown_not_empty`; [scope](../../Verus_verification/models/routine_reporting/NOTES.md). Raw rows and registry/error fields derive partial census and graph/node-vector report knowledge. Actual Python executes local SQL and the final reader under a stable registry view and refusal outcome across the two kind scans; transient per-read registry changes, native/index/schema truth, general IRIS comparison/driver semantics, other report fields and cross-read snapshots remain outside this correspondence. Label/property/edge-vector errors do not by themselves make graph size unknown.
- agent
- user-facing-behavior, operations

This owner recovers ordinary reporting intent from the primary docs and tests before the selected reporting implementation is modeled. Graph identity and the meaning of an omitted graph remain with [graph scope](../concepts/graph-scope.g5.md#graph.default). Probe availability, native counters, readiness flags and other status fields are separate conditions; this count/report rule does not certify them or a transactionally consistent snapshot across separate reads. The selected producer-to-report relation has been independently replayed within the linked package's stated source and provider frame.

State machines: [routine reporting](../../Verus_verification/models/routine_reporting/manifest.json), [operator reports](../../Verus_verification/models/operator_reports/manifest.json)

Children: [readiness](#install.status.readiness), [sync state](#install.status.sync), [verify_sync](#install.status.verify_sync), [capabilities](#install.status.capabilities), [HTTP and CLI readers](#install.status.readers), [ledger line](#install.status.ledger), [schema diagram](#install.status.diagram).

Iteration 53 (independent review round 2, M2): a failed count probe reproduced with a narrow monitoring role; the text report keeps "unknown", the other readers read zero ([bug-plt-119](../../Verus_verification/bugs_issues.md#bug-plt-119)); [operator_reports](../../Verus_verification/models/operator_reports/NOTES.md) `theorem_failed_census_unknown_only_in_report`.

Iteration 52: on IRIS the routed-table count fails ([bug-plt-115](../../Verus_verification/bugs_issues.md#bug-plt-115)); the routine_reporting replay ran on local SQL, whose `DISTINCT` keeps the stored case, so its correspondence for routed tables is withdrawn at the IRIS reader. [operator_reports](../../Verus_verification/models/operator_reports/NOTES.md) `theorem_routed_never_counted` models the IRIS reader.

### install.status.readiness

- Sources: [EngineStatus properties](../../../iris_vector_graph/status.py#L159-L214), [status probes](../../../iris_vector_graph/_engine/admin.py#L439-L703), [ADMIN_GUIDE status fields](../../../docs/ADMIN_GUIDE.md#L920-L960), [CHANGELOG R207](../../../CHANGELOG.md#L2252-L2253)
- Expands: [Status reports](#install.status)
- agent
- user-facing-behavior, operations
- design-verified
- Formal: [`theorem_ready_for_bfs_iff_rows`, `theorem_fresh_namespace_edges_skip_nkg`, `theorem_routed_only_not_ready_but_searchable`, `theorem_legacy_vectors_ready`, `theorem_full_text_follows_index`, `theorem_routed_edges_only_not_ready_but_searchable`, `theorem_legacy_edge_vectors_ready`, `theorem_failed_census_unknown_only_in_report`, `theorem_failed_vector_count_reads_zero`, `theorem_failed_side_counts_silent`](../../Verus_verification/models/operator_reports/operator_reports.rs)

Expected results come from ADMIN_GUIDE's field table ("the graph has edges: traversals work", "a BM25 index exists"), its unknown rule (R050, `docs/ADMIN_GUIDE.md#L950-L958`) and spec 230 FR-006 (routed vectors count). The field table's "default embedding table" (L940) predates routing and conflicts with FR-006; FR-006 is kept as the rule. Findings: [bug-plt-115](../../Verus_verification/bugs_issues.md#bug-plt-115), [bug-plt-119](../../Verus_verification/bugs_issues.md#bug-plt-119).

Premises of the formal claims: the adjacency index is declared, `KGEdgeCount` is below its cap, no Arno library is loaded, and the predicate entries are consistent; `kg_predicates_consistent` and the Arno branch of `ready_for_multihop_bfs` are not modeled. A failed probe is modeled for a caller whose privileges let only some probes succeed (iteration 53).

State machines: [operator reports](../../Verus_verification/models/operator_reports/manifest.json)

### install.status.sync

- Sources: [pending_sync and the report line](../../../iris_vector_graph/status.py#L216-L222), [status](../../../iris_vector_graph/_engine/admin.py#L396-L411), [Adjacency.Put](../../../iris_src/src/Graph/KG/Adjacency.cls#L80-L108), [erase clears the flag](../../../iris_vector_graph/_engine/nodes_edges.py#L1518-L1520), [USER_GUIDE caller transaction](../../../docs/USER_GUIDE.md#L276-L282), [ADMIN_GUIDE §9](../../../docs/ADMIN_GUIDE.md#L1036-L1060)
- Expands: [Status reports](#install.status)
- agent
- user-facing-behavior, operations
- design-verified
- Formal: [`theorem_fresh_namespace_edges_skip_nkg`, `theorem_put_after_sync_counted`, `theorem_delete_status_vs_verify`, `theorem_bulk_pending_is_engine_local`](../../Verus_verification/models/operator_reports/operator_reports.rs)

As built; the documented field meaning ("a bulk load left ^NKG stale") holds. The report gives no sign of an unbuilt integer copy outside `nkg_populated` and the internals view; no product finding is registered for that.

State machines: [operator reports](../../Verus_verification/models/operator_reports/manifest.json)

### install.status.verify_sync

- Sources: [verify_sync](../../../iris_vector_graph/_engine/admin.py#L756-L848), [BuildNKG and RewritePass](../../../iris_src/src/Graph/KG/TraversalBuild.cls#L250-L373), [NKGEdgeCount](../../../iris_src/src/Graph/KG/TraversalBuild.cls#L226-L229), [SyncReport](../../../iris_vector_graph/status.py#L73-L104), [verify_graph docstring](../../../iris_vector_graph/_engine/admin.py#L850-L890)
- Expands: [Status reports](#install.status)
- agent
- user-facing-behavior, operations
- design-verified
- Formal: [`theorem_shared_triple_never_in_sync`, `theorem_unique_triples_in_sync_after_sync`, `theorem_heal_claims_in_sync_then_drift`, `theorem_delete_status_vs_verify`](../../Verus_verification/models/operator_reports/operator_reports.rs)

Expected result from the docstring's documented use. Findings: [bug-plt-116](../../Verus_verification/bugs_issues.md#bug-plt-116). The docstring's list of paths that set the flag (`delete_node`, `drop_graph`) is out of date: those now drop the copy instead.

State machines: [operator reports](../../Verus_verification/models/operator_reports/manifest.json)

### install.status.capabilities

- Sources: [capabilities](../../../iris_vector_graph/engine.py#L1742-L1814), [markers read](../../../iris_vector_graph/schema.py#L2782-L2850), [markers written](../../../iris_vector_graph/schema.py#L3309-L3358), [setup replaces the cache](../../../iris_vector_graph/_engine/schema.py#L2578-L2596), [sync sets kg_built](../../../iris_vector_graph/_engine/schema.py#L2887-L2895), [PageRank fast path](../../../iris_vector_graph/_engine/algorithms.py#L341-L343), [store catalogue](../../../iris_vector_graph/stores/iris_sql_store.py#L29-L52), [API reference](../../../docs/API_REFERENCE.md#L51-L57)
- Expands: [Status reports](#install.status)
- agent
- architecture-decision, operations
- uncertain
- design-verified
- Formal: [`theorem_markers_never_set_after_empty_setup`, `theorem_setup_again_sets_markers`, `theorem_setup_with_edges_sets_markers`](../../Verus_verification/models/operator_reports/operator_reports.rs)

Expected result from the API reference ("What the namespace has deployed: the Graph.KG classes, ^KG, ^NKG"). Findings: [bug-plt-117](../../Verus_verification/bugs_issues.md#bug-plt-117). The store catalogue is observed only (all True, Arno entries absent with Arno not loaded); its intent stays with [HD-1703](../../Verus_verification/open_questions.md#HD-1703).

State machines: [operator reports](../../Verus_verification/models/operator_reports/manifest.json)

### install.status.readers

- Sources: [/server, /metrics, /stats, /schema, /indexes](../../../iris_vector_graph/cypher_api.py#L469-L568), [SHOW INDEXES](../../../iris_vector_graph/_engine/admin.py#L195-L264), [count readers](../../../iris_vector_graph/_engine/schema.py#L454-L497), [embedding_count](../../../iris_vector_graph/_engine/embeddings.py#L2124-L2150), [CLI](../../../iris_vector_graph/cli.py#L187-L247), [CLI indexes](../../../iris_vector_graph/cli.py#L443-L456), [ADMIN_API](../../../docs/ADMIN_API.md#L100-L215), [CHANGELOG 4.6.0 graph scope](../../../CHANGELOG.md#L800-L806)
- Expands: [Status reports](#install.status)
- agent
- user-facing-behavior, operations
- design-verified
- Formal: [`theorem_stats_default_vs_server_every_graph`, `theorem_server_and_metrics_project_status`, `theorem_failed_census_unknown_only_in_report`, `theorem_failed_vector_count_reads_zero`, `theorem_all_probes_ok_counts`](../../Verus_verification/models/operator_reports/operator_reports.rs)

`/indexes` and the CLI are observed by the iteration-52 probe; the CLI commands print the HTTP answer unchanged (justified delegation in the crosswalk). Iteration 53 observed `ivg status` exiting 0 with probe errors and an empty BM25 index listed `ONLINE` ([probe](../../uplift/consolidated/iteration-53/reports/failed-probe-20261117T044921Z.json)); neither is modeled. Findings: [bug-plt-119](../../Verus_verification/bugs_issues.md#bug-plt-119).

State machines: [operator reports](../../Verus_verification/models/operator_reports/manifest.json)

### install.status.ledger

- Sources: [_ledger_status](../../../iris_vector_graph/_engine/ledger.py#L39-L67), [GraphLedger.stats](../../../iris_vector_graph/ledger/client.py#L542-L575), [report ledger line](../../../iris_vector_graph/status.py#L216-L355), [ADMIN_GUIDE unknown rule](../../../docs/ADMIN_GUIDE.md#L950-L958)
- Expands: [Status reports](#install.status)
- agent
- user-facing-behavior, operations
- design-verified
- Formal: [`theorem_ledger_stats_failure_reads_zero`, `theorem_ledger_meta_failure_unknown`, `theorem_ledger_counters_follow_commits`, `theorem_enable_two_commits_one_reject`](../../Verus_verification/models/operator_reports/operator_reports.rs)

Added in iteration 53 for independent review round 2 (M3). The rule comes from `_ledger_status`'s docstring ("a read that fails is reported") and R050. Observed in the [probe](../../uplift/consolidated/iteration-53/reports/failed-probe-20261117T044921Z.json) and the operator_reports binding (namespace I53B). Findings: [bug-plt-120](../../Verus_verification/bugs_issues.md#bug-plt-120).

State machines: [operator reports](../../Verus_verification/models/operator_reports/manifest.json)

### install.status.diagram

- Sources: [get_schema_visualization](../../../iris_vector_graph/_engine/schema.py#L2772-L2856), [API reference](../../../docs/API_REFERENCE.md#L239-L245)
- Expands: [Status reports](#install.status)
- agent
- user-facing-behavior
- design-verified
- Formal: [`theorem_unlabeled_endpoint_is_first_label`](../../Verus_verification/models/operator_reports/operator_reports.rs)

The docstring says "0 if none"; that 0 is also the first label's id. Findings: [bug-plt-118](../../Verus_verification/bugs_issues.md#bug-plt-118).

State machines: [operator reports](../../Verus_verification/models/operator_reports/manifest.json)

### structure.drift

- Sources: [CONTEXT.md, Drift](../../../CONTEXT.md#L121-L126), [ADR-0008, existing installs](../../../docs/adr/0008-the-adjacency-index-is-maintained-by-the-engine.md#L40-L41), [spec 252 FR-009](../../../specs/252-adjacency-functional-index/spec.md#L120-L121)
- agent
- data-integrity, operations
- test-coverage
- Verus (iteration 57): [adjacency_maint](../../Verus_verification/models/adjacency_maint/NOTES.md) `theorem_incremental_equals_rebuild`, `theorem_sync_changes_nothing`
- Findings (iteration 57): [bug-str-115](../../Verus_verification/bugs_issues.md#bug-str-115)

Live coverage: [declaring the index repairs a drifted install](../../../tests/e2e/test_252_drifted_install_e2e.py). Observed divergence, suspected: several paths can still produce drift with the index declared ([stage-A notes, F3 to F6 and F10](../../uplift/ivg-verus-initial/intent/graph-structure.md#candidate-findings)).

### structure.rebuild

- uncertain
- Sources: [engine.sync](../../../iris_vector_graph/_engine/schema.py#L2859-L2912), [ADMIN_GUIDE, the adjacency indexes](../../../docs/ADMIN_GUIDE.md#L1032-L1062), [spec 252 FR-010](../../../specs/252-adjacency-functional-index/spec.md#L122), [BuildKG](../../../iris_src/src/Graph/KG/TraversalBuild.cls#L30-L172)
- Children: [What may readers see when a rebuild fails partway?](../../Verus_verification/open_questions.md#structure.rebuild.failure)
- Evidence: [native rebuild observation: default, named-graph and temporal-marked rows kept, an entry with no row removed](../../uplift/consolidated/iteration-21/varlength-PAIRS.md); `rebuild_edge_indices` (iteration 53): [frozen predictions](../../uplift/consolidated/iteration-53/sqlprocs-PAIRS.md) RB1-RB4, [binding](../../Verus_verification/results/sql_procs/20261117T051429Z-binding/receipt.json) `rb_*`, `priv_*_rb`
- Formal: [sql_procs](../../Verus_verification/models/sql_procs/sql_procs.rs) `rebuild`, `theorem_rebuild_answers_four_or_raises` (the SQL function only)
- agent
- operations
- Verus (iteration 57): [adjacency_maint](../../Verus_verification/models/adjacency_maint/NOTES.md) `theorem_incremental_equals_rebuild`; [rebuild_reads](../../Verus_verification/models/rebuild_reads/NOTES.md) `theorem_reader_sees_seed_alone`, `theorem_visible_edges_are_rows`, `theorem_end_is_rows`, repair `theorem_swap_shows_old_or_rows`; findings: [bug-str-115](../../Verus_verification/bugs_issues.md#bug-str-115)

Iteration 53: the `rebuild_edge_indices` bullets come from [Ledger.RebuildEdgeIndices](../../../iris_src/src/Graph/KG/Ledger.cls#L224-L240), ADMIN_GUIDE L577-L580 and CHANGELOG R294; a caller without `%BUILD_INDEX` got "does not have %BUILD_INDEX privileges (rebuilding the indexes of Graph_KG.nodes)".

Findings: [A failed indexed rebuild, or a failed rebuild after a bulk load, leaves a partial adjacency index](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-str-009)

Open questions: [What may readers see when a rebuild fails partway?](../../Verus_verification/open_questions.md#structure.rebuild.failure)

### structure.verify

- Sources: [GraphVerify header](../../../iris_src/src/Graph/KG/GraphVerify.cls#L1-L37), [verify_graph](../../../iris_vector_graph/_engine/admin.py#L850-L890), [USER_GUIDE section 4](../../../docs/USER_GUIDE.md#L444-L452)
- agent
- operations, data-integrity
- test-coverage

Partial live coverage: [a wrong current cache entry is flagged and a stale one ignored](../../../tests/e2e/test_degree_cache_live.py). Observed divergence: on a graph with parallel edges it compares the row count with the number of distinct triples, so it reports rows as missing, and it never checks edge counts; open task T036 of the multigraph spec names this ([stage-A notes, F7](../../uplift/ivg-verus-initial/intent/graph-structure.md#candidate-findings)).

Findings: [verify_graph reports healthy parallel edges as missing adjacency and cannot see lost multiplicity](../../Verus_verification/bugs_issues.md#bug-str-004)

Audit reproduction: [bug-str-004](../../Verus_verification/bugs_issues.md#bug-str-004) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Audit reproduction: [F-0204](../../Verus_verification/bugs_issues.md#F-0204) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [The graph check reports a multigraph's parallel edges as missing adjacency](../../Verus_verification/bugs_issues.md#F-0204).

Audit reproduction: [F-0403](../../Verus_verification/bugs_issues.md#F-0403) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [verify_graph reports drift on a graph with parallel edges whose index matches its rows](../../Verus_verification/bugs_issues.md#F-0403).
