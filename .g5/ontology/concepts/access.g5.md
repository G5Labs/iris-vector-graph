# Access policies

Start here for the rules that govern access across IVG interfaces, including IRIS privileges, authentication and strict writes. For specific client behavior, see [client interfaces](../features/client-interfaces.g5.md).

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

## IRIS privileges and graph identity

<a id="access.iris_boundary"></a>
[D · access.iris_boundary]

The real privilege boundary is the IRIS login: its database resources and its SQL privileges in the IVG Schema. IVG's server settings add a gate in front of that, not a replacement for it.

- SQL functions that read a global first check that the caller may SELECT the table the global stands for, and otherwise fail naming that table.
- The caller holds a privilege when `%All` is among its roles, or when the login or any of its roles holds it on the table or on the table's whole schema. A privilege on only some of a table's columns does not count.
- A function that checks several tables or privileges names the first one missing, in the order it checks them.
- SQL functions that write a global first check INSERT or UPDATE on its table.
- ObjectScript class methods called over the Native API do not check SQL privileges.
- A login whose database access is read-only cannot write, whatever IVG's settings say.

<a id="access.graph_id"></a>
[I · access.graph_id]

No entry point checks whether a caller may use a particular graph: any caller who can reach the data can name any graph. Keeping tenants apart takes separate namespaces (see [graph tenants](graph-scope.g5.md#graph.tenants)).

## Authentication

<a id="access.api_key"></a>
[D · access.api_key]

The API key is optional. With `IVG_API_KEY` unset or empty, the HTTP server and Bolt ask for no key at all.

- Working assumption: Model the single key and the IRIS user's privileges as the authorization surface. Treat an admin-only key or a kill route that is off by default as a proposed strengthening. Record IVG_READ_ONLY as the existing, coarse lever.

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

## Read-only mode

<a id="access.read_only"></a>
[I · access.read_only]

In read-only mode the server refuses every write, after the key check, and reads run as before.

- Every `POST`, `PUT`, `PATCH` and `DELETE` under `/admin/` is refused, except the route that only explains a query. The HTTP server's load, embed, snapshot, index-rebuild and setup routes all sit under `/admin/`.
- Cypher that writes is refused on the Cypher, Neo4j HTTP, GraphQL and Bolt routes.
- FHIR event writes are refused unless `IVG_ALLOW_FHIR_WRITES=true`.
- A request or transaction batch with any writing statement runs none of its statements.

- Working assumption: Keep engine read-only guarantees and explicitly list interfaces that ignore access hints; protocol hints and server enforcement need separate decisions.
- Working assumption: read_only=True is a requested guarantee; enforce it at a trusted boundary (refuse non-SELECT before it runs) or refuse/remove the unsupported flag in a versioned change. The engine's own use (reads only) makes enforcement compatible with internal callers.

<a id="access.read_only.verdict"></a>
[D · access.read_only.verdict]

One parser-based rule decides whether a Cypher text writes, for every surface. Text that cannot be parsed counts as a write, and a keyword inside a string or comment is not a write.

<a id="access.read_only.caches"></a>
[D · access.read_only.caches]

Reads in read-only mode may still write derived state: algorithm caches, the degree cache and compiled query plans. With a read-only database login those reads answer without caching.

## Which writes does strict mode govern?

<a id="access.ledger_strict"></a>
[D · access.ledger_strict]

Ledger strict mode governs only the engine calls listed on the [ledger page](../features/ledger.g5.md#ledger.strict), which owns that list. A server route is governed only when it calls one of those engine methods, so a route that runs its own SQL is not.

- Working assumption: Preserve explicit BulkLoader/raw-SQL/vector exemptions and list undecided FHIR/server paths individually; do not infer exemption from a missing guard.

<a id="access.ledger_strict.surfaces"></a>
[D · access.ledger_strict.surfaces]

Two kinds of write path are outside strict mode on purpose:

- Outside the ledger by decision: embedding, vector-index and BM25 index writes, which change no nodes or relationships.
- Documented raw SQL: the `BulkLoader` class, SQL a caller runs directly, and the MCP SQL tool, which runs any SQL by design.

<a id="access.ledger_strict.bypasses"></a>
[I · access.ledger_strict.bypasses]

Any other path that writes nodes or relationships, except the [undecided paths](../../Verus_verification/open_questions.md#q-plt-008), must be refused in strict mode and change nothing, like the engine's own writes. This covers `bulk_delete_adjacency` and the sample API's REST Cypher route, GraphQL Cypher field and example GraphQL mutations, which no document exempts.

- Working assumption: Preserve explicit BulkLoader/raw-SQL/vector exemptions and list undecided FHIR/server paths individually; do not infer exemption from a missing guard.

<a id="access.ledger_strict.engine_cache"></a>
[I · access.ledger_strict.engine_cache]

Strict mode applies to an engine whenever the ledger is strict, however long ago the engine was created. An engine must not stay unguarded because the ledger's classes were missing when it first checked.

## Earlier links

These links take you to the current sections and statements.

<a id="access-entry-points-authentication-and-write-governance"></a>

[Access policies](#access-policies)

<a id="entry-points"></a>

[Client entry points](../features/client-interfaces.g5.md#client-entry-points) · [Bolt and HTTP transactions](../features/client-interfaces.g5.md#bolt-and-http-transactions) · [IRIS privileges and graph identity](#iris-privileges-and-graph-identity)

<a id="trusted-surfaces"></a>

[Client entry points](../features/client-interfaces.g5.md#client-entry-points) · [Server deployment and defaults](../operations/setup-and-upgrade.g5.md#server-deployment-and-defaults)

<a id="writes-and-the-ledger"></a>

[Which writes does strict mode govern?](#which-writes-does-strict-mode-govern)

<a id="access.surfaces"></a>

[access.surfaces](../features/client-interfaces.g5.md#access.surfaces)

<a id="access.bolt"></a>

[access.bolt](../features/client-interfaces.g5.md#access.bolt)

<a id="access.bolt.framing"></a>

[access.bolt.framing](../features/client-interfaces.g5.md#access.bolt.framing)

<a id="access.bolt.results"></a>

[access.bolt.results](../features/client-interfaces.g5.md#access.bolt.results)

<a id="access.bolt.transactions"></a>

[access.bolt.transactions](../features/client-interfaces.g5.md#access.bolt.transactions)

<a id="access.http_transactions"></a>

[access.http_transactions](../features/client-interfaces.g5.md#access.http_transactions)

<a id="access.bolt.versions"></a>

[access.bolt.versions](../features/client-interfaces.g5.md#access.bolt.versions)

<a id="access.bolt.errors"></a>

[access.bolt.errors](../features/client-interfaces.g5.md#access.bolt.errors)

<a id="access.bolt.graph_values"></a>

[access.bolt.graph_values](../features/client-interfaces.g5.md#access.bolt.graph_values)

<a id="access.defaults"></a>

[access.defaults](../operations/setup-and-upgrade.g5.md#access.defaults)

<a id="access.health"></a>

[access.health](../operations/status-and-repair.g5.md#access.health)

<a id="access.health.lifecycle"></a>

[access.health.lifecycle](../operations/status-and-repair.g5.md#access.health.lifecycle)

<a id="access.mcp"></a>

[access.mcp](../features/client-interfaces.g5.md#access.mcp)

<a id="access.webapp"></a>

[access.webapp](../operations/setup-and-upgrade.g5.md#access.webapp)

## Metadata

### access.iris_boundary

- Sources: [ADMIN_GUIDE §3 Privileges](../../../docs/ADMIN_GUIDE.md); [ADMIN_GUIDE, table or schema counts, columns do not](../../../docs/ADMIN_GUIDE.md#L566-L576); [SqlPrivilege.cls](../../../iris_src/src/Graph/KG/SqlPrivilege.cls)
- Formal: [`require`, `holds_priv`, `check_priv`, `theorem_all_passes`, `theorem_single_check_iff_holds`, `theorem_column_only_select_refused`, `theorem_table_schema_role_select_pass`, `theorem_write_names_first_missing`](../../Verus_verification/models/sql_procs/sql_procs.rs)
- Expands: [Entry points](../features/client-interfaces.g5.md#access.surfaces)
- agent
- security, architecture-decision
- test-coverage

Introduced in 4.6.0 (R280 readers, R289 writers). Live coverage: `tests/e2e/test_460_r280_sql_global_readers_privilege_e2e.py`, `tests/e2e/test_460_r289_sql_writers_privilege_e2e.py`, and the role rows in `tests/e2e/test_460_r202_reading_role_e2e.py`, `test_460_r050_select_only_role_e2e.py`, `test_460_r311_writer_role_e2e.py`. Observed: `kg_IVF` checks a table named by a global that any database writer can change.

Iteration 56 (review 53-55 F4): the verdict is derived from the caller's recorded grants, not supplied. The sql_procs binding calls MatchEdges, MatchEdgesAllGraphs, DijkstraPath, backfill_temporal_rows and rebuild_edge_indices as eight users (no grant, schema SELECT, schema write, table SELECT, column-only SELECT, a role holding table SELECT, schema SELECT with INSERT on nodes only, %All) and compares the verdict and the table it names; CheckPrivilege's treatment of table, schema and column grants is the provider premise P-CHECKPRIV, observed there.

Findings: [The sample environment file sets IRIS_USER, but the server reads IRIS_USERNAME and silently connects as _SYSTEM](../../Verus_verification/bugs_issues.md#bug-plt-009); [The IVF SQL function checks the privilege on a table that the index's own global names](../../Verus_verification/bugs_issues.md#bug-plt-023)

### access.graph_id

- Sources: [USER_GUIDE: graph ID is not a security boundary](../../../docs/USER_GUIDE.md); [graph.tenants](graph-scope.g5.md#graph.tenants)
- Expands: [Entry points](../features/client-interfaces.g5.md#access.surfaces)
- agent
- security

CONTEXT.md calls graphs "isolation units"; that means data separation, not access control.

Audit (HD-1601): Existing authority: The namespace is the authorization boundary; graph IDs scope data operations and do not confer access rights. See [current behavior, alternatives and settling sources](../../Verus_verification/audits/register-20261115/question-review.md#HD-1601).

Findings: [Should a server limit which graphs a caller may name?](../../Verus_verification/open_questions.md#HD-1601).

### access.api_key

- uncertain
- Sources: [ADMIN_GUIDE §5](../../../docs/ADMIN_GUIDE.md); [ADMIN_API.md: Authentication](../../../docs/ADMIN_API.md); [_api_key.py](../../../iris_vector_graph/_api_key.py)
- Children: [every route](#access.api_key.every_route), [headers](#access.api_key.headers), [Bolt](#access.api_key.bolt)
- agent
- security

The opt-in key comes from spec 196, whose directory is no longer in the tree. Only commit `ce337194` remains.

Open questions: [Should admin work need a different key from reading?](../../Verus_verification/open_questions.md#HD-1602)

Assumption review evidence: Changed from decisions.md: **yes**. Status moves from assumption to supported. ADMIN_API and ADMIN_GUIDE (4.6.0) explicitly document one key on every route and the read-only lever. decisions.md did not cite IVG_READ_ONLY.

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

### access.read_only

- uncertain
- Sources: [ADMIN_API.md: Read-only mode](../../../docs/ADMIN_API.md); [ADMIN_GUIDE §5](../../../docs/ADMIN_GUIDE.md); [api_auth.py](../../../iris_vector_graph/api_auth.py)
- Children: [verdict](#access.read_only.verdict), [Does read-only mode govern the MCP tools, and should Bolt honour a driver's read access mode?](../../Verus_verification/open_questions.md#q-plt-012), [caches](#access.read_only.caches)
- agent
- security
- test-coverage

Live coverage: `tests/e2e/test_read_only_bypass_e2e.py` (engine read-only). The per-route checks are unit-tested (`tests/unit/test_r113_read_only_one_rule.py`).

Open questions: [Should the SQL adapter's pass-through refuse a write when called read-only?](../../Verus_verification/open_questions.md#HD-1701), [Does read-only mode govern the MCP tools, and should Bolt honour a driver's read access mode?](../../Verus_verification/open_questions.md#q-plt-012)

Assumption review evidence: Changed from decisions.md: no. Live probe confirms the flag is ignored; added the protocol's raise-not-approximate rule as supporting evidence and the misreported-error observation.

### access.read_only.verdict

- Sources: [cypher/read_only.py](../../../iris_vector_graph/cypher/read_only.py); [Release 4.6.0 plan](../../../specs/release-4.6.0/plan.md)
- Expands: [Read-only mode](#access.read_only)
- agent
- security
- test-coverage

The fix followed a privately reported bypass (R113, R115). Live coverage: `tests/e2e/test_read_only_bypass_e2e.py`.

### access.read_only.caches

- Sources: [ADMIN_GUIDE §3 (reading role)](../../../docs/ADMIN_GUIDE.md)
- Expands: [Read-only mode](#access.read_only)
- agent
- operations
- test-coverage

Live coverage for a read-only login: `tests/e2e/test_460_r050_reader_ppr_degree_e2e.py`.

### access.ledger_strict

- uncertain
- Sources: [Ledger API contract: strict-mode guard](../../../specs/213-graph-revision-ledger/contracts/ledger-api.md); [ledger.strict](../features/ledger.g5.md#ledger.strict); [USER_GUIDE: writes outside the ledger](../../../docs/USER_GUIDE.md)
- Children: [surfaces](#access.ledger_strict.surfaces), [bypasses](#access.ledger_strict.bypasses), [engine cache](#access.ledger_strict.engine_cache), [Which write paths must strict mode govern beyond the engine's methods, and how is each classified?](../../Verus_verification/open_questions.md#q-plt-008)
- agent
- data-integrity

Restated so that the guarded-call list has one owner, `ledger.strict`. The contract's list includes snapshot restore, imports and inference; the bulk loader and raw SQL are documented as unguarded.

Open questions: [Which write paths must strict mode govern beyond the engine's methods, and how is each classified?](../../Verus_verification/open_questions.md#q-plt-008)

### access.ledger_strict.surfaces

- Sources: [ADR-0006](../../../docs/adr/0006-embedding-identity-lives-in-a-registry-not-the-ledger.md); [Ledger API contract: strict-mode guard](../../../specs/213-graph-revision-ledger/contracts/ledger-api.md); [ADMIN_GUIDE §3 (MCP RunSQL)](../../../docs/ADMIN_GUIDE.md); [Review round 1, R1-11](../../uplift/ivg-verus-initial/review/round1-platform.md)
- Expands: [Strict mode](#access.ledger_strict)
- agent
- data-integrity

ADR-0006 says embedding writes sit entirely outside the ledger, and the contract scopes strict mode to structural writes and documents raw SQL as unguarded. Earlier drafts listed these paths as open.

### access.ledger_strict.bypasses

- uncertain
- Sources: [Ledger API contract: strict-mode guard](../../../specs/213-graph-revision-ledger/contracts/ledger-api.md); [USER_GUIDE: writes outside the ledger](../../../docs/USER_GUIDE.md); [_engine/nodes_edges.py bulk_delete_adjacency](../../../iris_vector_graph/_engine/nodes_edges.py); [api/routers/cypher.py](../../../api/routers/cypher.py); [api/gql/schema.py](../../../api/gql/schema.py); [examples/domains/biomedical/resolver.py](../../../examples/domains/biomedical/resolver.py)
- Expands: [Strict mode](#access.ledger_strict)
- agent
- data-integrity

The USER_GUIDE says strict mode refuses `create_node`, `create_edge` "and the other methods". Observed divergence: under strict mode `bulk_delete_adjacency` deleted an edge without a record ([receipt](../../Verus_verification/receipts/native/platform_strict_bulk_delete_adjacency.json)), and the sample API's `POST /api/cypher` committed a `CREATE` without a record while the engine path refused it ([receipt](../../Verus_verification/receipts/native/platform_strict_api_sample.json)). The GraphQL Cypher field is a query field and the router allows queries over GET, so with no key a cross-site GET might run a write (suspected).

Findings: [The sample API's Cypher endpoints run translated SQL on a raw cursor, bypassing strict mode and the engine's statement protocol](../../Verus_verification/bugs_issues.md#bug-plt-005); [bulk_delete_adjacency deletes relationships under strict mode without a record](../../Verus_verification/bugs_issues.md#bug-plt-006)

Open questions: [Which write paths must strict mode govern beyond the engine's methods, and how is each classified?](../../Verus_verification/open_questions.md#q-plt-008)

### access.ledger_strict.engine_cache

- Sources: [ledger/guard.py](../../../iris_vector_graph/ledger/guard.py); [ledger.strict](../features/ledger.g5.md#ledger.strict); [Review round 1, R1-11](../../uplift/ivg-verus-initial/review/round1-platform.md)
- Expands: [Strict mode](#access.ledger_strict)
- agent
- data-integrity

Observed divergence (code reading): the guard caches whether the ledger class is compiled for the engine's lifetime, so an engine that first asked before setup compiled the ledger classes never applies strict mode. The short refresh delay and the fail-open case belong to the [ledger page](../features/ledger.g5.md#ledger.strict).

Findings: [An engine whose first strict-mode check ran before the ledger classes were installed never enforces strict mode](../../Verus_verification/bugs_issues.md#bug-plt-025)
