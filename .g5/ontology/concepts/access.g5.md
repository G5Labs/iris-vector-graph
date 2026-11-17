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

- Today the HTTP Cypher routes return at most 1,000 rows of an answer. `/api/cypher` documents this as `limitRows`, and its row count gives the rows kept; `/db/neo4j/tx/commit` and `/db/{db}/query/v2` cut without saying so.

- Working assumption: Treat /metaPath as default-graph-only and include that in its contract. A body naming `graph` should be refused or honoured, not ignored; until decided, model the silent ignore as the baseline.


<a id="access.bolt"></a>
[I · access.bolt]

Bolt carries an ordered stream of messages and results over TCP or WebSocket. Changing how a valid message is split into chunks or transport reads must preserve its meaning and every following message.

- Working assumption: Keep ambiguous write outcomes distinct from known pre-write failure; automatic resend of non-idempotent writes is not presumed safe.
- Working assumption: Retry a read, or a write known not to have executed (a connection error raised before the statement was sent). Never re-run a write whose outcome is unknown; return an error that says the outcome is unknown. A write carrying a verified idempotency key may be retried.
- Working assumption: after an ambiguous outcome resend only a known read or an explicitly idempotent operation; report an unknown outcome otherwise; treat client and server retries as one protocol. Note that this narrows a documented feature (compatibility decision).
- A statement run outside an explicit transaction commits on its own when it finishes. What an explicit transaction promises is owned by [Bolt transactions](#access.bolt.transactions).


<a id="access.bolt.framing"></a>
[I · access.bolt.framing]

A message can use any positive chunk sizes through 65,535 bytes and ends with a zero-size chunk.
- Complete bodies are dispatched in order; an incomplete suffix stays buffered until it is complete.
- A zero-size chunk between messages is a keep-alive in the supported Bolt 4.4 protocol and leaves the session usable.


<a id="access.bolt.results"></a>
[I · access.bolt.results]

A successful RUN supplies a result stream, preserving admitted values and field order.
- PULL with a positive n returns at most n records, keeps the unread suffix, and reports that more records remain until the stream is exhausted; n=-1 returns every remaining record.
- RESET discards the pending result and permits a later RUN. ROLLBACK also discards the pending result; what it does to the transaction's writes is owned by [Bolt transactions](#access.bolt.transactions).
- A failed RUN emits FAILURE, clears pending rows, and ordinary requests are ignored until recovery.
- Today a PULL with a positive n returns the first n records and drops the rest, without saying that more remained ([finding](../../Verus_verification/audits/register-20261115/bugs-review.md#F-1602)).


<a id="access.bolt.transactions"></a>
[I · access.bolt.transactions]

An explicit Bolt transaction keeps its writes only if it commits. A ROLLBACK, a failed statement, a RESET or a closed connection before COMMIT must leave none of the transaction's writes behind; a server that cannot do this must refuse BEGIN with a FAILURE, so the client knows each statement commits on its own.
- A statement outside an explicit transaction commits when it finishes, and a committed transaction keeps all of its writes.
- Which of the two forms IVG keeps, real transactions or a refused BEGIN, is not decided ([question](../../Verus_verification/open_questions.md#access.transactions)).
- Today BEGIN, COMMIT and ROLLBACK all answer SUCCESS and none of them opens, commits or undoes anything: ROLLBACK only clears the pending rows and COMMIT only returns the session to READY, and each statement commits as it runs. A rolled-back transaction, one with a failed statement, one ended by RESET or a closed connection, and an aborted `execute_write` all keep their writes while the driver reports no error ([finding](../../Verus_verification/bugs_issues.md#bug-plt-127)).

<a id="access.http_transactions"></a>
[I · access.http_transactions]

A Neo4j HTTP transaction request (`/db/neo4j/tx/commit`) is one transaction: it keeps its statements' writes only if every statement succeeds. When one fails, none of the request's writes may stay; a server that cannot do this must refuse a request it could commit only in part.
- A request whose statements all succeed commits all of their writes.
- Under read-only mode a request with any writing statement runs none of its statements ([read-only mode](#access.read_only)).
- The rule is the one [Bolt transactions](#access.bolt.transactions) owns: a request is BEGIN, its statements and COMMIT. Which form IVG keeps is the same open choice ([question](../../Verus_verification/open_questions.md#access.transactions)).
- Today each statement commits as it runs and the request goes on after a failure: CREATE, a failing statement and CREATE answer 400 and keep both nodes ([finding](../../Verus_verification/bugs_issues.md#bug-plt-136)).

<a id="access.bolt.versions"></a>
[I · access.bolt.versions]

The Bolt listener agrees on Bolt 4.4 or a version from 5.0 to 5.4, reading the client's four proposals in order. When none of them can be met, it answers four zero bytes and closes the connection.
- A 5.x proposal with a range is met at its highest minor version up to 5.4: 5.8 with a range of 4 gets 5.4, while 5.8 alone, or 5.6 to 5.8, is refused.
- A proposal it does not know, such as the Bolt 5.7 manifest offer, is skipped, and a later proposal can still be met.
- A Bolt 4 client sends the API key in HELLO; a Bolt 5.1 or later client sends it in LOGON.


<a id="access.bolt.errors"></a>
[I · access.bolt.errors]

A RUN that fails answers FAILURE with a Neo4j status code and the failure's text, and the session accepts RESET and a new RUN. A write refused by read-only mode gets `Neo.ClientError.Statement.AccessMode`, and a wrong API key gets `Neo.ClientError.Security.Unauthorized`.
- Today every other failure carries `Neo.ClientError.Statement.SyntaxError`, including an IRIS SQL error, a parameter the IRIS driver refuses and an undefined parameter, so a client cannot tell a bad query from a failed database ([finding](../../Verus_verification/bugs_issues.md#bug-plt-124)).
- Today an integer result outside 64 bits ends the session instead of failing the query ([finding](../../Verus_verification/bugs_issues.md#bug-plt-125)).


<a id="access.bolt.graph_values"></a>
[I · access.bolt.graph_values]

A value in a Bolt record arrives with the value and type the engine answers, and a whole node or relationship arrives as a Bolt node or relationship. A node carries its own identity, labels and stored properties; a relationship carries its type, its properties and its stored start and end node.
- Integers, floats, strings, booleans, null, lists, maps and paths arrive alike on Bolt, `execute_cypher` and the HTTP routes. Integers use the smallest PackStream width; a path arrives as the engine's map of node ids and relationship types.
- Today a node's id is 31 bits of Python's hash of its node ID, so two nodes can reach the client as one, and ids change when the server restarts ([finding](../../Verus_verification/bugs_issues.md#bug-plt-122)).
- Today a relationship's start and end are the node columns before and after it in the RETURN: `RETURN b, r, a` reports b as the start of a stored `a→b`, and `RETURN r` alone has no endpoints ([finding](../../Verus_verification/bugs_issues.md#bug-plt-123)).
- Today a whole node carries each property longer than 200 characters as its first 200 characters and `...`, and a long list or map as that text ([finding](../../Verus_verification/bugs_issues.md#bug-plt-121)).

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


<a id="access.defaults"></a>
[D · access.defaults]

Out of the box the HTTP server listens on every network interface, port 8200, and Bolt on 7687. Both connect to IRIS as `_SYSTEM` with password `SYS` unless configured. The operator guide says to set the key on any server another machine can reach, and to give the server a non-superuser login.

- Working assumption: Treat the documented open bind and credentials as current behavior only; safer defaults need a maintainer policy decision.
- Working assumption: The product contract at the pin is ADMIN_GUIDE section 5's open default; F-1709 is a documentation defect against deploy/README.md:86 (registered as fail against that stated text). For the reviewed deployment, keep local-only binding or an explicit opt-in for unauthenticated external binding as a stated premise, not as the product's intent.


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

## Trusted surfaces


<a id="access.mcp"></a>
[D · access.mcp]

The MCP tools are for a trusted client only. Their SQL tool runs any SQL as the MCP service's login, their load tool reads any server file IRIS can read, and their Cypher tool can write.


<a id="access.webapp"></a>
[D · access.webapp]

The IRIS REST dispatcher stays inert until an operator creates its web application. That application uses password login and gives every user one read-only role for the namespace, which holds only what its search routes read.

- Working assumption: Treat both apps as supported entry points subject to the shared HTTP safety constraints: key gate and read-only (already applied), a depth bound, and an honest health check. Record the generated app's missing depth limit and always-healthy /health as gaps against that parity, not as violations of a stated contract.


## Writes and the ledger


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

## Metadata

### access.surfaces

- uncertain
- Sources: [ADMIN_API.md](../../../docs/ADMIN_API.md); [cypher_api.py](../../../iris_vector_graph/cypher_api.py); [api/main.py](../../../api/main.py); [bolt_server.py](../../../iris_vector_graph/bolt_server.py); [MCPTools.cls](../../../iris_src/src/Graph/KG/MCPTools.cls); [Service.cls](../../../iris_src/src/Graph/KG/Service.cls)
- Children: [Bolt stream](#access.bolt), [Neo4j HTTP transactions](#access.http_transactions), [IRIS boundary](#access.iris_boundary), [graph ID](#access.graph_id)
- Verus: [http_rows](../../Verus_verification/models/http_rows/NOTES.md) `theorem_answer_is_prefix`, `theorem_neo4j_answer_cannot_tell_truncation`, `theorem_api_row_count_is_kept` (HTTP Cypher row cap, as built)
- Evidence: [frozen predictions and native observations](../../uplift/consolidated/iteration-32/http-PAIRS.md)
- agent
- architecture-decision

Observed divergence: the sample API's REST Cypher route, its GraphQL Cypher field and the example GraphQL mutations it mounts run SQL on their own cursor instead of calling the engine (see [strict-mode surfaces](#access.ledger_strict.surfaces)).

Findings: [Bolt sessions never close the IRIS connection their engine opened](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-plt-002); [The sample API's Cypher endpoints run translated SQL on a raw cursor, bypassing strict mode and the engine's statement protocol](../../Verus_verification/bugs_issues.md#bug-plt-005); [A GraphQL GET request can run a Cypher write](../../Verus_verification/bugs_issues.md#bug-plt-013); [The Neo4j-compatible HTTP routes return at most 1,000 rows of an answer without saying so](../../Verus_verification/bugs_issues.md#bug-plt-108)

Open questions: [Should the REST dispatcher's `/metaPath` take a graph?](../../Verus_verification/open_questions.md#HD-1604)

Assumption review evidence: Changed from decisions.md: **no**. Same reading. Added: spec 230 is absent from the repository and the mirror, and a supplied graph key is ignored silently.

State machines: [http rows](../../Verus_verification/models/http_rows/manifest.json)


Findings: [The Neo4j HTTP transaction route answers a whole node as three text columns](../../Verus_verification/bugs_issues.md#bug-plt-126) (iteration 55)

### access.bolt

- design-verified

- uncertain
- Sources: [Bolt protocol commitment](../../../iris_vector_graph/bolt_server.py#L1-L8), [ADMIN_API](../../../docs/ADMIN_API.md); [primary Bolt message specification](https://neo4j.com/docs/bolt/current/bolt/message/)
- Verus: [bolt_stream model and limits](../../Verus_verification/models/bolt_stream/NOTES.md), as-built byte/state transcription; raw framing through admitted RUN/PULL final records, no generic codec/provider/network or database transaction proof.
- Children: [framing](#access.bolt.framing), [result stream](#access.bolt.results), [transactions](#access.bolt.transactions), [versions](#access.bolt.versions), [errors](#access.bolt.errors), [graph values](#access.bolt.graph_values)
- Expands: [Entry points](#access.surfaces)
- agent
- user-facing-behavior, data-integrity

Recovered in iteration9 from the shipped Bolt4.4 compatibility commitment and primary protocol, independently of the current decoder. This does not change the [Must the Neo4j-compatible surfaces keep Neo4j's transaction meaning?](../../Verus_verification/open_questions.md#access.transactions): pending rows and database transaction atomicity are different decisions.

Open questions: [Should the Cypher HTTP server run a failed query a second time?](../../Verus_verification/open_questions.md#HD-1603), [Should the HTTP client resend a write query after a server error?](../../Verus_verification/open_questions.md#HD-1702), [Must the Neo4j-compatible surfaces keep Neo4j's transaction meaning?](../../Verus_verification/open_questions.md#access.transactions), [May the server or the client retry a call that writes?](../../Verus_verification/open_questions.md#q-plt-019)

State machines: [bolt stream](../../Verus_verification/models/bolt_stream/manifest.json)

Assumption review evidence: Changed from decisions.md: **no**. Same direction as decisions.md. New history evidence (9c683292 to 7d62dbf5) and a live duplicate write strengthen it. Changed from decisions.md: no. Probe confirms; added that the retry itself is a documented maintainer feature (so the working answer is a narrowing, not a bug fix) and that statement failures are 400 and not retried.

### access.bolt.framing

- design-verified
- Sources: [primary message specification: Chunking and versions4.1/4.3](https://neo4j.com/docs/bolt/current/bolt/message/), [`BoltSession.run/_recv_message`](../../../iris_vector_graph/bolt_server.py#L396-L459), [`TcpBoltSession.run/_recv_message`](../../../iris_vector_graph/bolt_server.py#L936-L987)
- Verus: [bolt_stream.rs](../../Verus_verification/models/bolt_stream/bolt_stream.rs): `lemma_scan_encoded_prefix`, `theorem_small_chunk_reencoding_leaves_terminator`, `theorem_small_chunk_empty_closes_before_queued_run`, `theorem_coalesced_small_chunks_still_deliver_queued_run`, `theorem_noop_closes_wire_without_engine`; [fragment](../../Verus_verification/models/bolt_stream/NOTES.md). Raw scanner and actual re-encoding cut/queue are derived, with separate and coalesced passing/failing neighbors; transport scheduling and generic handshake/authentication remain outside the contract.
- Expands: [Bolt stream](#access.bolt)
- agent
- user-facing-behavior, data-integrity

Observed at the pin: WebSocket consumption is computed by default re-encoding each decoded body instead of counting received chunk headers. A fragmented HELLO followed by separately delivered RUN/PULL can therefore lose the result stream: the retained full HELLO trace executes RUN once but never emits its record. The smaller RESET witness loses the later RUN itself. Coalescing all messages can queue a successful exchange while leaving residue, so failure is packetization dependent. Separately, the WebSocket run loop closes on empty bytes from a valid NOOP; the TCP loop continues. [36 full-session local-transport cases and localized method-copy repairs](../../uplift/consolidated/iteration-9/bolt-session-probe.json) execute the actual session/codec over a one-row engine adapter, with no listener, socket, authentication scenario or database. Native network reachability remains unassessed.

Findings: [WebSocket consumes the wrong byte count after small chunks](../../Verus_verification/bugs_issues.md#bug-plt-101); [WebSocket closes on a Bolt keep-alive chunk](../../Verus_verification/bugs_issues.md#bug-plt-102).

Audit reproduction: [bug-plt-101](../../Verus_verification/bugs_issues.md#bug-plt-101) is partial reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/components.json). This is product observation, not executable-body verification.

Audit reproduction: [bug-plt-102](../../Verus_verification/bugs_issues.md#bug-plt-102) is partial reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/components.json). This is product observation, not executable-body verification.

State machines: [bolt stream](../../Verus_verification/models/bolt_stream/manifest.json)

### access.bolt.results

- design-verified
- Sources: [primary message specification: PULL](https://neo4j.com/docs/bolt/current/bolt/message/), [`_handle_run/_handle_pull/_handle_reset` and dispatch](../../../iris_vector_graph/bolt_server.py#L500-L669)
- Verus: [bolt_stream.rs](../../Verus_verification/models/bolt_stream/bolt_stream.rs): `theorem_raw_wire_run_then_pull_final_records`, `theorem_partial_pull_drops_suffix_and_reports_no_more`, `theorem_raw_error_string_decides_failure`, `theorem_commit_preserves_but_rollback_discards` (pending rows only, not writes), `theorem_reset_allows_next_result`; [scope](../../Verus_verification/models/bolt_stream/NOTES.md). Admitted scalar/list/map cells and fixed canonical request fragments, not general PackStream/graph objects or SQL/provider execution.
- Expands: [Bolt stream](#access.bolt)
- agent
- user-facing-behavior, data-integrity

Observed: positive n slices rows then clears the entire pending result and omits has_more (known F-1602); n=0 emits all rows but is only an as-built out-of-domain neighbor, not a compatible PULL request. RUN replaces pending rows. DISCARD, RESET and ROLLBACK clear pending rows; COMMIT leaves them despite returning READY. These as-built transitions do not establish that every sequence is allowed by the protocol. Scalar/list/map admitted codec values and final records are a narrower scope than all graph objects or arbitrary query providers.

Iteration 55: the PULL suffix loss reproduced with the neo4j driver 6.4.1 (`fetch_size=2` receives 2 of 5 records, no error); Bolt is not capped at 1,000 rows as the HTTP routes are.

Findings: [An integer result past 64 bits ends the Bolt session](../../Verus_verification/bugs_issues.md#bug-plt-125); [PULL drops its unread suffix](../../Verus_verification/audits/register-20261115/bugs-review.md#F-1602). Explicit transactions moved to [Bolt transactions](#access.bolt.transactions) in iteration 56.

State machines: [bolt stream](../../Verus_verification/models/bolt_stream/manifest.json)

### access.bolt.transactions

- design-verified
- uncertain
- Sources: [BEGIN/COMMIT/ROLLBACK dispatch](../../../iris_vector_graph/bolt_server.py#L500-L510), [`_handle_run`](../../../iris_vector_graph/bolt_server.py#L567-L622), [`_handle_reset`](../../../iris_vector_graph/bolt_server.py#L662-L667); [primary Bolt message specification: BEGIN, COMMIT, ROLLBACK, RESET](https://neo4j.com/docs/bolt/current/bolt/message/); [USER_GUIDE: a caller's rollback removes IVG's writes (engine)](../../../docs/USER_GUIDE.md); [README: a neo4j-driver compatible server](../../../README.md)
- Verus: [bolt_tx.rs](../../Verus_verification/models/bolt_tx/bolt_tx.rs) `step`, the rule `neo`, general `theorem_rollback_keeps_writes`, `theorem_rollback_departs_iff_writes`, `theorem_failed_tx_keeps_earlier_writes`, `theorem_reset_or_close_keeps_writes`, neighbors `theorem_commit_agrees`, `theorem_autocommit_agrees`, the checked alternative `theorem_refusal_matches_rule` (controls `atomic-tx`, `begin-refused`, `rollback-answers-failure`, `run-not-committed`, `failed-run-writes`, `failure-not-sticky`, `rule-rollback-keeps`); [scope](../../Verus_verification/models/bolt_tx/NOTES.md)
- Evidence: [review 53-55 F1 probe](../../uplift/consolidated/iteration-56/review-probes/rv55b-observed-20261117T064330Z.json); [bolt_tx binding](../../Verus_verification/results/bolt_tx/20261117T065936Z-binding/receipt.json) (raw Bolt 4.4 client and neo4j driver 6.4.1)
- Expands: [Bolt stream](#access.bolt)
- agent
- user-facing-behavior, data-integrity

Recovered in iteration 56 from the Bolt message specification, the README's neo4j-driver compatibility claim and the engine's own transaction contract (USER_GUIDE: a caller's rollback removes IVG's writes). No product document says Bolt transactions are unsupported. Both answers the open question lists keep the rule above: either real transactions, or a refused BEGIN; neither allows answering SUCCESS to a ROLLBACK whose writes stay. The open choice is which of the two. Iteration 59 (review 56-58 m1): the "Today" bullet now says what COMMIT and ROLLBACK actually do (`bolt_server.py:502-510`: ROLLBACK clears the pending rows, COMMIT returns the session to READY; neither touches a write); the HTTP batch's sibling rule is [Neo4j HTTP transactions](#access.http_transactions).

Open questions: [Must the Neo4j-compatible surfaces keep Neo4j's transaction meaning?](../../Verus_verification/open_questions.md#access.transactions)

Findings: [A Bolt rollback keeps the transaction's writes](../../Verus_verification/bugs_issues.md#bug-plt-127) (formerly F-1601)

State machines: [bolt transactions](../../Verus_verification/models/bolt_tx/manifest.json)

### access.http_transactions

- design-verified
- uncertain
- Sources: [`neo4j_tx_commit`](../../../iris_vector_graph/cypher_api.py#L379-L404), [`_run_cypher`](../../../iris_vector_graph/cypher_api.py#L239-L265), [`_cypher_writes_under_read_only`](../../../iris_vector_graph/cypher_api.py#L230-L236); [ADMIN_API: Neo4j HTTP routes and read-only mode](../../../docs/ADMIN_API.md); [README: Neo4j-compatible surfaces](../../../README.md)
- Verus: [bolt_tx.rs](../../Verus_verification/models/bolt_tx/bolt_tx.rs) HTTP section: the rule derived from Bolt's `theorem_http_rule_is_bolt_rule`, `theorem_http_batch_keeps_writes_around_failure`, `theorem_http_batch_departs_iff`, neighbors `theorem_http_all_succeed_agrees`, `theorem_http_read_only_runs_none`, witness `theorem_http_witness_failing_middle` (controls `http-batch-atomic`, `http-stop-at-failure`, `http-failure-writes`, `http-status-ok-on-error`, `http-read-only-runs-reads`, `read-only-first-only`, `rule-http-keeps-earlier`); [scope](../../Verus_verification/models/bolt_tx/NOTES.md)
- Evidence: [review 56-58 G1](../../uplift/consolidated/iteration-59/REVIEW-56-58.md); [bolt_tx binding section H](../../Verus_verification/results/bolt_tx/20261117T090118Z-binding/receipt.json) (FastAPI TestClient, real engine, nine requests)
- Expands: [Entry points](#access.surfaces)
- agent
- user-facing-behavior, data-integrity

Recovered in iteration 59 (review 56-58 G1) from the route's name, ADMIN_API (the read-only rule already treats one request as a unit) and the product's own Bolt rule. Neo4j's HTTP API documentation could not be fetched in this session or in the review, so it is not quoted. Observed beside the departure: every failed statement is reported as `Neo.ClientError.Statement.SyntaxError` whatever failed, and the successful statements' results are returned beside the errors.

Open questions: [Must the Neo4j-compatible surfaces keep Neo4j's transaction meaning?](../../Verus_verification/open_questions.md#access.transactions)

Findings: [A Neo4j HTTP tx/commit request keeps its successful statements' writes when another fails](../../Verus_verification/bugs_issues.md#bug-plt-136) (iteration 59)

State machines: [bolt transactions](../../Verus_verification/models/bolt_tx/manifest.json)

### access.bolt.versions

- design-verified
- Sources: [`negotiate_version`](../../../iris_vector_graph/bolt_server.py#L331-L347), [`_handle_hello`/`_handle_logon`](../../../iris_vector_graph/bolt_server.py#L547-L565), [ADMIN_API Authentication](../../../docs/ADMIN_API.md); [Bolt handshake specification](https://neo4j.com/docs/bolt/current/bolt/handshake/)
- Verus: [bolt_answers.rs](../../Verus_verification/models/bolt_answers/bolt_answers.rs) `negotiate`, general `theorem_answer_is_zero_or_supported`, `theorem_v5_rule`, `theorem_probe_offers` (controls `range-unchecked`, `no-bolt5`); [scope](../../Verus_verification/models/bolt_answers/NOTES.md)
- Evidence: [W60 predictions BP1, BP2 and results](../../uplift/consolidated/iteration-55/pipeline-PAIRS.md)
- Expands: [Bolt stream](#access.bolt)
- agent
- user-facing-behavior

Recovered in iteration 55 from the handshake specification and ADMIN_API. BP1 held; BP2's main prediction (4.4 only) missed: 5.0 to 5.4 are agreed. The neo4j driver 6.4.1 agreed 5.4. HELLO answers `server: Neo4j/5.0.0`; Node and Relationship structures keep the Bolt 4 field layout on Bolt 5, which the Python driver accepts (other drivers unchecked).

State machines: [bolt answers](../../Verus_verification/models/bolt_answers/manifest.json)

### access.bolt.errors

- design-verified
- Sources: [`_handle_run`](../../../iris_vector_graph/bolt_server.py#L567-L622), [`_refuse_unauthorized`/`_authenticate`](../../../iris_vector_graph/bolt_server.py#L523-L545), [`PackStream._pack_int`](../../../iris_vector_graph/bolt_server.py#L95-L105); [Neo4j status codes](https://neo4j.com/docs/status-codes/current/); [ADMIN_API read-only mode](../../../docs/ADMIN_API.md)
- Verus: [bolt_answers.rs](../../Verus_verification/models/bolt_answers/bolt_answers.rs) `bolt_code`, `theorem_runtime_failure_reported_as_syntax`, `theorem_gate_codes_follow_rule`, `pull_value`, `theorem_overflow_breaks_connection`, `theorem_int64_values_arrive` (controls `code-by-cause`, `gates-folded`, `nofit-is-failure`)
- Evidence: [W60 predictions ER1, ER2, BP4, T5 and results](../../uplift/consolidated/iteration-55/pipeline-PAIRS.md)
- Expands: [Bolt stream](#access.bolt)
- agent
- user-facing-behavior

Recovered in iteration 55. The engine itself answers a failed read with `IVGResult.error` and no rows unless `raise_on_error=True` (its docstring and USER_GUIDE); Bolt and the HTTP routes turn that into a failure.

Findings: [Bolt reports every failed query as a syntax error](../../Verus_verification/bugs_issues.md#bug-plt-124); [An integer result past 64 bits ends the Bolt session](../../Verus_verification/bugs_issues.md#bug-plt-125)

State machines: [bolt answers](../../Verus_verification/models/bolt_answers/manifest.json)

### access.bolt.graph_values

- design-verified
- Sources: [`_node_int_id`, `pack_node`](../../../iris_vector_graph/bolt_server.py#L351-L362), [`_recompose_graph_row`, `_pack_rel_from_value`, `_parse_props_field`](../../../iris_vector_graph/bolt_server.py#L713-L905), [`PackStream`](../../../iris_vector_graph/bolt_server.py#L67-L150); [USER_GUIDE: lists, maps and paths through execute_cypher, REST and Bolt](../../../docs/USER_GUIDE.md); [PackStream specification](https://neo4j.com/docs/bolt/current/packstream/)
- Verus: [bolt_answers.rs](../../Verus_verification/models/bolt_answers/bolt_answers.rs) `int_marker`, `theorem_marker_is_smallest`; `bolt_id`, `client_view2`, `theorem_hash_collision_loses_first_node`, `theorem_distinct_ids_keep_both`; `reported`, `theorem_endpoints_follow_columns`, `theorem_one_hop_right_iff_source_first`, `theorem_rel_alone_or_last`; `bolt_node_prop`, `theorem_long_property_truncated`, `theorem_short_property_kept`
- Evidence: [W60 predictions RT1-RT11, BP6-BP8, T1-T3 and results](../../uplift/consolidated/iteration-55/pipeline-PAIRS.md)
- Expands: [Bolt stream](#access.bolt)
- agent
- user-facing-behavior, data-integrity

Recovered in iteration 55. The value-type rows RT1-RT7 held on all four readers (Python, Bolt, `/api/cypher`, `/db/neo4j/tx/commit`). The id collision relies on the neo4j driver's per-result node cache (provider premise P-DRIVER-ID, observed with 6.4.1).

Findings: [Bolt cuts long node properties](../../Verus_verification/bugs_issues.md#bug-plt-121); [Bolt node ids can collide](../../Verus_verification/bugs_issues.md#bug-plt-122); [Bolt relationship endpoints follow column order](../../Verus_verification/bugs_issues.md#bug-plt-123); [The Neo4j HTTP transaction route answers a node as three text columns](../../Verus_verification/bugs_issues.md#bug-plt-126)

State machines: [bolt answers](../../Verus_verification/models/bolt_answers/manifest.json)

### access.iris_boundary

- Sources: [ADMIN_GUIDE §3 Privileges](../../../docs/ADMIN_GUIDE.md); [ADMIN_GUIDE, table or schema counts, columns do not](../../../docs/ADMIN_GUIDE.md#L566-L576); [SqlPrivilege.cls](../../../iris_src/src/Graph/KG/SqlPrivilege.cls)
- Formal: [`require`, `holds_priv`, `check_priv`, `theorem_all_passes`, `theorem_single_check_iff_holds`, `theorem_column_only_select_refused`, `theorem_table_schema_role_select_pass`, `theorem_write_names_first_missing`](../../Verus_verification/models/sql_procs/sql_procs.rs)
- Expands: [Entry points](#access.surfaces)
- agent
- security, architecture-decision
- test-coverage

Introduced in 4.6.0 (R280 readers, R289 writers). Live coverage: `tests/e2e/test_460_r280_sql_global_readers_privilege_e2e.py`, `tests/e2e/test_460_r289_sql_writers_privilege_e2e.py`, and the role rows in `tests/e2e/test_460_r202_reading_role_e2e.py`, `test_460_r050_select_only_role_e2e.py`, `test_460_r311_writer_role_e2e.py`. Observed: `kg_IVF` checks a table named by a global that any database writer can change.

Iteration 56 (review 53-55 F4): the verdict is derived from the caller's recorded grants, not supplied. The sql_procs binding calls MatchEdges, MatchEdgesAllGraphs, DijkstraPath, backfill_temporal_rows and rebuild_edge_indices as eight users (no grant, schema SELECT, schema write, table SELECT, column-only SELECT, a role holding table SELECT, schema SELECT with INSERT on nodes only, %All) and compares the verdict and the table it names; CheckPrivilege's treatment of table, schema and column grants is the provider premise P-CHECKPRIV, observed there.

Findings: [The sample environment file sets IRIS_USER, but the server reads IRIS_USERNAME and silently connects as _SYSTEM](../../Verus_verification/bugs_issues.md#bug-plt-009); [The IVF SQL function checks the privilege on a table that the index's own global names](../../Verus_verification/bugs_issues.md#bug-plt-023)

### access.graph_id

- Sources: [USER_GUIDE: graph ID is not a security boundary](../../../docs/USER_GUIDE.md); [graph.tenants](graph-scope.g5.md#graph.tenants)
- Expands: [Entry points](#access.surfaces)
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

### access.defaults

- uncertain
- Sources: [ADMIN_API.md: Starting the server](../../../docs/ADMIN_API.md); [ADMIN_GUIDE §5](../../../docs/ADMIN_GUIDE.md); [api/main.py](../../../api/main.py); [cli.py](../../../iris_vector_graph/cli.py)
- Children: [Should the server refuse to start on a reachable address with no key and a superuser login?](../../Verus_verification/open_questions.md#q-plt-003)
- agent
- security, operations

Observed divergence: the sample API and `.env.sample` read the login from `IRIS_USER`, the HTTP server and CLI from `IRIS_USERNAME`, so following `.env.sample` for the HTTP server connects as `_SYSTEM`. Bolt per-session IRIS connections are not closed at session end.

Findings: [The sample environment file sets IRIS_USER, but the server reads IRIS_USERNAME and silently connects as _SYSTEM](../../Verus_verification/bugs_issues.md#bug-plt-009)

Open questions: [Should server start refuse to listen on every address without an API key?](../../Verus_verification/open_questions.md#HD-1705), [Should the server refuse to start on a reachable address with no key and a superuser login?](../../Verus_verification/open_questions.md#q-plt-003)

Assumption review evidence: Changed from decisions.md: yes. decisions.md kept both contradictory contracts open; commit 6df261d9/R032 makes ADMIN_GUIDE the single operator document and git history shows --force-no-auth was never implemented on any branch, so the open default is the current contract and the hardening is a deployment premise.

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

### access.mcp

- Sources: [ADMIN_GUIDE §3 and §4 (The MCP classes)](../../../docs/ADMIN_GUIDE.md); [MCPTools.cls](../../../iris_src/src/Graph/KG/MCPTools.cls); [MCPToolSet.cls](../../../iris_src/src/Graph/KG/MCPToolSet.cls)
- agent
- security

The tool set's only policy is console auditing. The evidence-search tool is documented as taking natural-language text but binds its input as a node ID. Live coverage needs `%AI` (`tests/integration/test_mcp_tools.py`).

Findings: [The MCP evidence search binds its natural-language input as a node ID](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-plt-020)

### access.webapp

- uncertain
- Sources: [Service.cls CreateWebApp](../../../iris_src/src/Graph/KG/Service.cls); [ADMIN_GUIDE](../../../docs/ADMIN_GUIDE.md)
- agent
- security

Changed in 4.6.0 (R131, R147); earlier releases gave every authenticated user `%All`. Re-running the creator resets an application an earlier release made.

Open questions: [Should the generated GraphQL server match the sample API's safety limits?](../../Verus_verification/open_questions.md#HD-1605)

Assumption review evidence: Changed from decisions.md: **yes**. Partial change. decisions.md left the choice open between 'distinct entry points' and parity. R097, R107 and R079 show the maintainer already hardening create_app as a deployable app, so parity (b) is now the working direction. decisions.md also used 'sample' for the app the maintainer calls the development app.

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
