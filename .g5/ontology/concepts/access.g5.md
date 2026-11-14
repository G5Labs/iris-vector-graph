# Access: entry points, authentication and write governance

Who can reach IVG, through which entry points, what they are allowed to do, and which write paths the ledger's strict mode governs.

## Definitions

- **Engine**: the Python `IRISGraphEngine`, which an application uses directly over an IRIS connection. It needs no server.
- **HTTP server**: the server `ivg server start` runs. It serves Cypher, Neo4j-compatible HTTP routes, admin routes and a Bolt listener.
- **Sample API**: the FastAPI app under `api/`, with REST Cypher, GraphQL and the FHIR event route.
- **Bolt**: the Neo4j driver protocol, served over TCP and over WebSocket.
- **MCP tools**: IRIS-hosted tools an MCP client can call, available only on IRIS builds with `%AI`.
- **API key**: the shared secret in `IVG_API_KEY` that the HTTP server and Bolt can require.
- **Read-only mode**: the server-wide setting `IVG_READ_ONLY=true`.
- **Write verdict**: the decision whether a Cypher text writes, made by parsing it.
- **Strict mode**: the ledger setting that refuses graph writes made outside a ledger commit.

## Entry points

<a id="access.surfaces"></a>
[D · access.surfaces]

Applications reach IVG through the engine, or through optional servers built on it: the HTTP server, Bolt, GraphQL, the sample API, the IRIS-hosted MCP tools and an IRIS REST dispatcher. The servers are meant as a convenience layer: each server call should do what an engine method an application could call itself does.

<a id="access.iris_boundary"></a>
[D · access.iris_boundary]

The real privilege boundary is the IRIS login: its database resources and its SQL privileges in the IVG Schema. IVG's server settings add a gate in front of that, not a replacement for it.

- SQL functions that read a global first check that the caller may SELECT the table the global stands for.
- SQL functions that write a global first check INSERT or UPDATE on its table.
- ObjectScript class methods called over the Native API do not check SQL privileges.
- A login whose database access is read-only cannot write, whatever IVG's settings say.

<a id="access.graph_id"></a>
[I · access.graph_id]

No entry point checks whether a caller may use a particular graph: any caller who can reach the data can name any graph. Keeping tenants apart takes separate namespaces (see [graph tenants](../concepts/graph-scope.g5.md#graph.tenants)).

## Authentication

<a id="access.api_key"></a>
[D · access.api_key]

The API key is optional. With `IVG_API_KEY` unset or empty, the HTTP server and Bolt ask for no key at all.

<a id="access.api_key.every_route"></a>
[I · access.api_key.every_route]

With the key set, every route needs it except `/health` and the API documentation.

- The public routes are matched on the exact path.
- A route added later needs the key unless it is added to the public list.
- Every HTTP method needs it. A browser's CORS preflight is answered without it and runs no handler.
- A missing or wrong key gets `401` before any handler runs and before the read-only check.

<a id="access.api_key.headers"></a>
[I · access.api_key.headers]

A client sends the key as `X-Api-Key` or as `Authorization: Bearer`, and the server compares it in constant time.

<a id="access.api_key.bolt"></a>
[I · access.api_key.bolt]

A Bolt client sends the key as the credentials of its `HELLO` or `LOGON` message, and a session that has not presented it can run nothing. A refused key ends the session's authentication even after an earlier good one, and `RESET` does not restore it.

<a id="access.defaults"></a>
[D · access.defaults]

Out of the box the HTTP server listens on every network interface, port 8200, and Bolt on 7687. Both connect to IRIS as `_SYSTEM` with password `SYS` unless configured. The operator guide says to set the key on any server another machine can reach, and to give the server a non-superuser login.

<a id="access.defaults.exposure"></a>
[Q · access.defaults.exposure]

Should the server refuse to start, or at least warn, when it listens beyond the local machine with no API key or with the default superuser login? There is no provisional answer.

- Today only the sample API warns about the default login.
- Without a key and from the network, a caller can load data, run writes and stop IRIS processes through admin routes.

<a id="access.health"></a>
[I · access.health]

`/health` needs no key and answers status only, with no counts and no error text. It answers unhealthy when the database does not respond. The sample API's `/health` also answers unhealthy when the namespace's schema record is missing or names another schema; the HTTP server's runs a node count instead.

## Read-only mode

<a id="access.read_only"></a>
[I · access.read_only]

In read-only mode the server refuses every write, after the key check, and reads run as before.

- Every `POST`, `PUT`, `PATCH` and `DELETE` under `/admin/` is refused, except the route that only explains a query. The HTTP server's load, embed, snapshot, index-rebuild and setup routes all sit under `/admin/`.
- Cypher that writes is refused on the Cypher, Neo4j HTTP, GraphQL and Bolt routes.
- FHIR event writes are refused unless `IVG_ALLOW_FHIR_WRITES=true`.
- A request or transaction batch with any writing statement runs none of its statements.

<a id="access.read_only.verdict"></a>
[D · access.read_only.verdict]

One parser-based rule decides whether a Cypher text writes, for every surface. Text that cannot be parsed counts as a write, and a keyword inside a string or comment is not a write.

<a id="access.read_only.scope"></a>
[Q · access.read_only.scope]

Does read-only mode also govern the IRIS-hosted MCP tools and code running inside IRIS, and should Bolt honor a driver's per-session read mode? There is no provisional answer. The operator guide treats a read-only database login as the real read-only role.

- Today the MCP Cypher tool can write and the MCP SQL tool runs any SQL, whatever the setting.
- Bolt ignores the access mode a driver asks for, so only the server-wide setting refuses writes.

<a id="access.read_only.caches"></a>
[D · access.read_only.caches]

Reads in read-only mode may still write derived state: algorithm caches, the degree cache and compiled query plans. With a read-only database login those reads answer without caching.

## Trusted surfaces

<a id="access.mcp"></a>
[D · access.mcp]

The MCP tools are for a trusted client only. Their SQL tool runs any SQL as the MCP service's login, their load tool reads any server file IRIS can read, and their Cypher tool can write.

<a id="access.webapp"></a>
[D · access.webapp]

The IRIS REST dispatcher stays inert until an operator creates its web application. That application uses password login and gives every user one read-only role for the namespace, which holds only what its search routes read.

## Writes and the ledger

<a id="access.ledger_strict"></a>
[D · access.ledger_strict]

Ledger strict mode governs only the engine calls listed on the [ledger page](../features/ledger.g5.md#ledger.strict), which owns that list. A server route is governed only when it calls one of those engine methods, so a route that runs its own SQL is not.

<a id="access.ledger_strict.surfaces"></a>
[D · access.ledger_strict.surfaces]

Two kinds of write path are outside strict mode on purpose:

- Outside the ledger by decision: embedding, vector-index and BM25 index writes, which change no nodes or relationships.
- Documented raw SQL: the `BulkLoader` class, SQL a caller runs directly, and the MCP SQL tool, which runs any SQL by design.

<a id="access.ledger_strict.bypasses"></a>
[I · access.ledger_strict.bypasses]

Any other path that writes nodes or relationships, except the [undecided paths](#access.ledger_strict.undecided), must be refused in strict mode and change nothing, like the engine's own writes. This covers `bulk_delete_adjacency` and the sample API's REST Cypher route, GraphQL Cypher field and example GraphQL mutations, which no document exempts.

<a id="access.ledger_strict.engine_cache"></a>
[I · access.ledger_strict.engine_cache]

Strict mode applies to an engine whenever the ledger is strict, however long ago the engine was created. An engine must not stay unguarded because the ledger's classes were missing when it first checked.

<a id="access.ledger_strict.undecided"></a>
[Q · access.ledger_strict.undecided]

Must strict mode govern these write paths, which no source places inside or outside it? There is no provisional answer.

- FHIR graph sync, which writes from ObjectScript.
- The MCP Cypher tool.
- Turning a graph's multigraph mode on or off.
- The `Prop_Set` and `Txn_*` SQL procedures, when called directly.
- A ledger commit's [post-commit properties](../features/ledger.g5.md#ledger.commit.post-commit), written by direct SQL after the revision with no strict check.
- The 4.0.0 upgrade, which rewrites tables and globals with no strict check. The temporal backfill writes through `create_edge`, so strict mode refuses it like any other edge write.

Plausible answers: guard each like an engine write, or list it with the documented exemptions.

<a id="access.retries"></a>
[Q · access.retries]

May the server or client retry a call that writes? There is no provisional answer. Only a ledger commit with an idempotency key is protected from a repeat.

- The HTTP server reruns a failed Cypher call once, on a fresh engine.
- The Python client retries a POST on a server error or a timeout, up to three attempts by default.
- So today a write that is not idempotent can be applied twice.

<a id="access.transactions"></a>
[Q · access.transactions]

Must the Neo4j-compatible surfaces keep Neo4j's transaction meaning? There is no provisional answer. Plausible answers: map explicit transactions onto one IVG transaction, or refuse explicit transactions and document per-statement commits.

- Today Bolt's begin, commit and rollback do nothing, so each statement commits on its own and a rollback keeps earlier writes.
- A Neo4j HTTP batch keeps earlier statements when a later one fails.

## Metadata

### access.surfaces

- Sources: [ADMIN_API.md](../../../docs/ADMIN_API.md); [cypher_api.py](../../../iris_vector_graph/cypher_api.py); [api/main.py](../../../api/main.py); [bolt_server.py](../../../iris_vector_graph/bolt_server.py); [MCPTools.cls](../../../iris_src/src/Graph/KG/MCPTools.cls); [Service.cls](../../../iris_src/src/Graph/KG/Service.cls)
- Children: [IRIS boundary](#access.iris_boundary), [graph ID](#access.graph_id)
- agent
- architecture-decision

Observed divergence: the sample API's REST Cypher route, its GraphQL Cypher field and the example GraphQL mutations it mounts run SQL on their own cursor instead of calling the engine (see [strict-mode surfaces](#access.ledger_strict.surfaces)).

Findings: [Bolt sessions never close the IRIS connection their engine opened](../../Verus_verification/bugs_issues.md#bug-plt-002); [The sample API's Cypher endpoints run translated SQL on a raw cursor, bypassing strict mode and the engine's statement protocol](../../Verus_verification/bugs_issues.md#bug-plt-005); [A GraphQL GET request can run a Cypher write](../../Verus_verification/bugs_issues.md#bug-plt-013)

### access.iris_boundary

- Sources: [ADMIN_GUIDE §3 Privileges](../../../docs/ADMIN_GUIDE.md); [SqlPrivilege.cls](../../../iris_src/src/Graph/KG/SqlPrivilege.cls)
- Expands: [Entry points](#access.surfaces)
- agent
- security, architecture-decision
- test-coverage

Introduced in 4.6.0 (R280 readers, R289 writers). Live coverage: `tests/e2e/test_460_r280_sql_global_readers_privilege_e2e.py`, `tests/e2e/test_460_r289_sql_writers_privilege_e2e.py`, and the role rows in `tests/e2e/test_460_r202_reading_role_e2e.py`, `test_460_r050_select_only_role_e2e.py`, `test_460_r311_writer_role_e2e.py`. Observed: `kg_IVF` checks a table named by a global that any database writer can change.

Findings: [The sample environment file sets IRIS_USER, but the server reads IRIS_USERNAME and silently connects as _SYSTEM](../../Verus_verification/bugs_issues.md#bug-plt-009); [The IVF SQL function checks the privilege on a table that the index's own global names](../../Verus_verification/bugs_issues.md#bug-plt-023)

### access.graph_id

- Sources: [USER_GUIDE: graph ID is not a security boundary](../../../docs/USER_GUIDE.md); [graph.tenants](../concepts/graph-scope.g5.md#graph.tenants)
- Expands: [Entry points](#access.surfaces)
- agent
- security

CONTEXT.md calls graphs "isolation units"; that means data separation, not access control.

### access.api_key

- Sources: [ADMIN_GUIDE §5](../../../docs/ADMIN_GUIDE.md); [ADMIN_API.md: Authentication](../../../docs/ADMIN_API.md); [_api_key.py](../../../iris_vector_graph/_api_key.py)
- Children: [every route](#access.api_key.every_route), [headers](#access.api_key.headers), [Bolt](#access.api_key.bolt)
- agent
- security

The opt-in key comes from spec 196, whose directory is no longer in the tree. Only commit `ce337194` remains.

### access.api_key.every_route

- Sources: [ADMIN_API.md: Authentication](../../../docs/ADMIN_API.md); [api_auth.py](../../../iris_vector_graph/api_auth.py); [CHANGELOG v4.6.0](../../../CHANGELOG.md)
- Expands: [API key](#access.api_key)
- agent
- security
- test-coverage

Default-deny since 4.6.0 (R097, R112). Unit tests enumerate every route; live coverage in `tests/e2e/test_460_r222_server_key_and_version_e2e.py`. The tracked-in-repo `.env.sample` still describes the pre-4.6.0 scope of the key.

### access.api_key.headers

- Sources: [_api_key.py](../../../iris_vector_graph/_api_key.py)
- Expands: [API key](#access.api_key)
- agent
- security

Observed: when both headers are present, the request passes if either one matches.

### access.api_key.bolt

- Sources: [ADMIN_API.md: Authentication](../../../docs/ADMIN_API.md); [bolt_server.py](../../../iris_vector_graph/bolt_server.py)
- Expands: [API key](#access.api_key)
- agent
- security

Unit tests only (`tests/unit/test_r097_bolt_auth.py`, `tests/unit/test_r111_bolt_logon.py`).

### access.defaults

- Sources: [ADMIN_API.md: Starting the server](../../../docs/ADMIN_API.md); [ADMIN_GUIDE §5](../../../docs/ADMIN_GUIDE.md); [api/main.py](../../../api/main.py); [cli.py](../../../iris_vector_graph/cli.py)
- Children: [exposure](#access.defaults.exposure)
- agent
- security, operations

Observed divergence: the sample API and `.env.sample` read the login from `IRIS_USER`, the HTTP server and CLI from `IRIS_USERNAME`, so following `.env.sample` for the HTTP server connects as `_SYSTEM`. Bolt per-session IRIS connections are not closed at session end.

Findings: [The sample environment file sets IRIS_USER, but the server reads IRIS_USERNAME and silently connects as _SYSTEM](../../Verus_verification/bugs_issues.md#bug-plt-009)

### access.defaults.exposure

- Sources: [ADMIN_GUIDE §5](../../../docs/ADMIN_GUIDE.md); [cypher_api.py admin routes](../../../iris_vector_graph/cypher_api.py); [Stage A notes F-H5](../../uplift/ivg-verus-initial/intent/platform.md)
- Expands: [Defaults](#access.defaults)
- agent
- uncertain
- security

Findings: [Should the server refuse to start on a reachable address with no key and a superuser login?](../../Verus_verification/open_questions.md#q-plt-003)

### access.health

- Sources: [ADMIN_GUIDE §5](../../../docs/ADMIN_GUIDE.md); [api/main.py database_problem](../../../api/main.py); [CHANGELOG v4.7.0](../../../CHANGELOG.md)
- agent
- operations, security

The schema-record check was added to the sample API's `/health` in 4.6.3 ([CHANGELOG](../../../CHANGELOG.md#L493-L499); [api/main.py](../../../api/main.py#L40-L63)); the HTTP server's `/health` ([cypher_api.py](../../../iris_vector_graph/cypher_api.py#L268-L285)) does not check it. The HTTP server's `/health` holds the engine lock and counts nodes, so it serializes behind other requests.

### access.read_only

- Sources: [ADMIN_API.md: Read-only mode](../../../docs/ADMIN_API.md); [ADMIN_GUIDE §5](../../../docs/ADMIN_GUIDE.md); [api_auth.py](../../../iris_vector_graph/api_auth.py)
- Children: [verdict](#access.read_only.verdict), [scope](#access.read_only.scope), [caches](#access.read_only.caches)
- agent
- security
- test-coverage

Live coverage: `tests/e2e/test_read_only_bypass_e2e.py` (engine read-only). The per-route checks are unit-tested (`tests/unit/test_r113_read_only_one_rule.py`).

### access.read_only.verdict

- Sources: [cypher/read_only.py](../../../iris_vector_graph/cypher/read_only.py); [Release 4.6.0 plan](../../../specs/release-4.6.0/plan.md)
- Expands: [Read-only mode](#access.read_only)
- agent
- security
- test-coverage

The fix followed a privately reported bypass (R113, R115). Live coverage: `tests/e2e/test_read_only_bypass_e2e.py`.

### access.read_only.scope

- Sources: [MCPTools.cls](../../../iris_src/src/Graph/KG/MCPTools.cls); [ADMIN_GUIDE §3](../../../docs/ADMIN_GUIDE.md); [bolt_server.py](../../../iris_vector_graph/bolt_server.py)
- Expands: [Read-only mode](#access.read_only)
- agent
- uncertain
- security

Findings: [Does read-only mode govern the MCP tools, and should Bolt honour a driver's read access mode?](../../Verus_verification/open_questions.md#q-plt-012)

### access.read_only.caches

- Sources: [ADMIN_GUIDE §3 (reading role)](../../../docs/ADMIN_GUIDE.md)
- Expands: [Read-only mode](#access.read_only)
- agent
- operations
- test-coverage

Live coverage for a read-only login: `tests/e2e/test_460_r050_reader_ppr_degree_e2e.py`.

### access.mcp

- Sources: [ADMIN_GUIDE §3 and §4 (The MCP classes)](../../../docs/ADMIN_GUIDE.md); [MCPTools.cls](../../../iris_src/src/Graph/KG/MCPTools.cls); [MCPToolSet.cls](../../../iris_src/src/Graph/KG/MCPToolSet.cls)
- agent
- security

The tool set's only policy is console auditing. The evidence-search tool is documented as taking natural-language text but binds its input as a node ID. Live coverage needs `%AI` (`tests/integration/test_mcp_tools.py`).

Findings: [The MCP evidence search binds its natural-language input as a node ID](../../Verus_verification/bugs_issues.md#bug-plt-020)

### access.webapp

- Sources: [Service.cls CreateWebApp](../../../iris_src/src/Graph/KG/Service.cls); [ADMIN_GUIDE](../../../docs/ADMIN_GUIDE.md)
- agent
- security

Changed in 4.6.0 (R131, R147); earlier releases gave every authenticated user `%All`. Re-running the creator resets an application an earlier release made.

### access.ledger_strict

- Sources: [Ledger API contract: strict-mode guard](../../../specs/213-graph-revision-ledger/contracts/ledger-api.md); [ledger.strict](../features/ledger.g5.md#ledger.strict); [USER_GUIDE: writes outside the ledger](../../../docs/USER_GUIDE.md)
- Children: [surfaces](#access.ledger_strict.surfaces), [bypasses](#access.ledger_strict.bypasses), [engine cache](#access.ledger_strict.engine_cache), [undecided](#access.ledger_strict.undecided)
- agent
- data-integrity

Restated so that the guarded-call list has one owner, `ledger.strict`. The contract's list includes snapshot restore, imports and inference; the bulk loader and raw SQL are documented as unguarded.

### access.ledger_strict.surfaces

- Sources: [ADR-0006](../../../docs/adr/0006-embedding-identity-lives-in-a-registry-not-the-ledger.md); [Ledger API contract: strict-mode guard](../../../specs/213-graph-revision-ledger/contracts/ledger-api.md); [ADMIN_GUIDE §3 (MCP RunSQL)](../../../docs/ADMIN_GUIDE.md); [Review round 1, R1-11](../../uplift/ivg-verus-initial/review/round1-platform.md)
- Expands: [Strict mode](#access.ledger_strict)
- agent
- data-integrity

ADR-0006 says embedding writes sit entirely outside the ledger, and the contract scopes strict mode to structural writes and documents raw SQL as unguarded. Earlier drafts listed these paths as open.

### access.ledger_strict.bypasses

- Sources: [Ledger API contract: strict-mode guard](../../../specs/213-graph-revision-ledger/contracts/ledger-api.md); [USER_GUIDE: writes outside the ledger](../../../docs/USER_GUIDE.md); [_engine/nodes_edges.py bulk_delete_adjacency](../../../iris_vector_graph/_engine/nodes_edges.py); [api/routers/cypher.py](../../../api/routers/cypher.py); [api/gql/schema.py](../../../api/gql/schema.py); [examples/domains/biomedical/resolver.py](../../../examples/domains/biomedical/resolver.py)
- Expands: [Strict mode](#access.ledger_strict)
- agent
- data-integrity

The USER_GUIDE says strict mode refuses `create_node`, `create_edge` "and the other methods". Observed divergence: under strict mode `bulk_delete_adjacency` deleted an edge without a record ([receipt](../../Verus_verification/receipts/native/platform_strict_bulk_delete_adjacency.json)), and the sample API's `POST /api/cypher` committed a `CREATE` without a record while the engine path refused it ([receipt](../../Verus_verification/receipts/native/platform_strict_api_sample.json)). The GraphQL Cypher field is a query field and the router allows queries over GET, so with no key a cross-site GET might run a write (suspected).

Findings: [The sample API's Cypher endpoints run translated SQL on a raw cursor, bypassing strict mode and the engine's statement protocol](../../Verus_verification/bugs_issues.md#bug-plt-005); [bulk_delete_adjacency deletes relationships under strict mode without a record](../../Verus_verification/bugs_issues.md#bug-plt-006)

### access.ledger_strict.engine_cache

- Sources: [ledger/guard.py](../../../iris_vector_graph/ledger/guard.py); [ledger.strict](../features/ledger.g5.md#ledger.strict); [Review round 1, R1-11](../../uplift/ivg-verus-initial/review/round1-platform.md)
- Expands: [Strict mode](#access.ledger_strict)
- agent
- data-integrity

Observed divergence (code reading): the guard caches whether the ledger class is compiled for the engine's lifetime, so an engine that first asked before setup compiled the ledger classes never applies strict mode. The short refresh delay and the fail-open case belong to the [ledger page](../features/ledger.g5.md#ledger.strict).

Findings: [An engine whose first strict-mode check ran before the ledger classes were installed never enforces strict mode](../../Verus_verification/bugs_issues.md#bug-plt-025)

### access.ledger_strict.undecided

- Sources: [FHIRGraph.cls](../../../iris_src/src/Graph/KG/FHIRGraph.cls); [MCPTools.cls](../../../iris_src/src/Graph/KG/MCPTools.cls); [migrations/upgrade.py](../../../iris_vector_graph/migrations/upgrade.py); [temporal_structural_rows.py](../../../iris_vector_graph/migrations/temporal_structural_rows.py); [Review round 1, R1-11](../../uplift/ivg-verus-initial/review/round1-platform.md); [fhir.ledger](../features/fhir.g5.md#fhir.ledger)
- Expands: [Strict mode](#access.ledger_strict)
- agent
- uncertain
- data-integrity

Findings: [Which write paths must strict mode govern beyond the engine's methods, and how is each classified?](../../Verus_verification/open_questions.md#q-plt-008)


Findings: [Post-commit properties bypass strict mode and the block on commits into a target being redacted](../../Verus_verification/bugs_issues.md#bug-led-009)
### access.retries

- Sources: [cypher_api.py _run_cypher](../../../iris_vector_graph/cypher_api.py); [sdk.py _post](../../../iris_vector_graph/sdk.py); [ledger.idempotency](../features/ledger.g5.md#ledger.idempotency)
- agent
- uncertain
- data-integrity, user-facing-behavior

Recorded from the code only; no document states the retry policy, so review round 3 R3-reader M14 turned the former decision into a question. The server retries on any exception, so a write that had committed before the error was raised would run again. No test covers a repeated write.

Findings: [The HTTP server and the SDK retry a failed Cypher write, so a write can apply twice](../../Verus_verification/bugs_issues.md#bug-plt-019), [May the server or the client retry a call that writes?](../../Verus_verification/open_questions.md#q-plt-019)

### access.transactions

- Sources: [bolt_server.py](../../../iris_vector_graph/bolt_server.py); [cypher_api.py tx/commit](../../../iris_vector_graph/cypher_api.py); [Stage A notes F-H1, F-H2](../../uplift/ivg-verus-initial/intent/platform.md)
- agent
- uncertain
- user-facing-behavior, data-integrity

No document states either behavior, and no test covers it.

Findings: [Neo4j-compatible transactions are not transactions: Bolt ROLLBACK keeps the writes and the HTTP transaction endpoint commits statement by statement](../../Verus_verification/bugs_issues.md#bug-plt-008)
