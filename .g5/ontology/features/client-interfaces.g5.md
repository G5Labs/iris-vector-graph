# Client interfaces

Start here when choosing how to connect to IVG or interpreting a response from Bolt or HTTP. The [access policies](../concepts/access.g5.md) describe the shared permission checks.

## Definitions

- **Engine**: the Python `IRISGraphEngine`, which an application uses directly over an IRIS connection. It needs no server.
- **HTTP server**: the server `ivg server start` runs. It serves Cypher, Neo4j-compatible HTTP routes, admin routes and a Bolt listener.
- **Sample API**: the FastAPI app under `api/`, with REST Cypher, GraphQL and the FHIR event route.
- **Bolt**: the Neo4j driver protocol, served over TCP and over WebSocket.
- **MCP tools**: IRIS-hosted tools an MCP client can call, available only on IRIS builds with `%AI`.

## Client entry points

<a id="access.surfaces"></a>
[D · access.surfaces]

Applications reach IVG through the engine, or through optional servers built on it: the HTTP server, Bolt, GraphQL, the sample API, the IRIS-hosted MCP tools and an IRIS REST dispatcher. The servers are meant as a convenience layer: each server call should do what an engine method an application could call itself does.

- Today the HTTP Cypher routes return at most 1,000 rows of an answer. `/api/cypher` documents this as `limitRows`, and its row count gives the rows kept; `/db/neo4j/tx/commit` and `/db/{db}/query/v2` cut without saying so.

- Working assumption: Treat /metaPath as default-graph-only and include that in its contract. A body naming `graph` should be refused or honoured, not ignored; until decided, model the silent ignore as the baseline.

<a id="access.mcp"></a>
[D · access.mcp]

The MCP tools are for a trusted client only. Their SQL tool runs any SQL as the MCP service's login, their load tool reads any server file IRIS can read, and their Cypher tool can write.

## Bolt and HTTP transactions

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
- Under read-only mode a request with any writing statement runs none of its statements ([read-only mode](../concepts/access.g5.md#access.read_only)).
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

## Metadata

### access.surfaces

- uncertain
- Sources: [ADMIN_API.md](../../../docs/ADMIN_API.md); [cypher_api.py](../../../iris_vector_graph/cypher_api.py); [api/main.py](../../../api/main.py); [bolt_server.py](../../../iris_vector_graph/bolt_server.py); [MCPTools.cls](../../../iris_src/src/Graph/KG/MCPTools.cls); [Service.cls](../../../iris_src/src/Graph/KG/Service.cls)
- Children: [Bolt stream](#access.bolt), [Neo4j HTTP transactions](#access.http_transactions), [IRIS boundary](../concepts/access.g5.md#access.iris_boundary), [graph ID](../concepts/access.g5.md#access.graph_id)
- Verus: [http_rows](../../Verus_verification/models/http_rows/NOTES.md) `theorem_answer_is_prefix`, `theorem_neo4j_answer_cannot_tell_truncation`, `theorem_api_row_count_is_kept` (HTTP Cypher row cap, as built)
- Evidence: [frozen predictions and native observations](../../uplift/consolidated/iteration-32/http-PAIRS.md)
- agent
- architecture-decision

Observed divergence: the sample API's REST Cypher route, its GraphQL Cypher field and the example GraphQL mutations it mounts run SQL on their own cursor instead of calling the engine (see [strict-mode surfaces](../concepts/access.g5.md#access.ledger_strict.surfaces)).

Findings: [Bolt sessions never close the IRIS connection their engine opened](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-plt-002); [The sample API's Cypher endpoints run translated SQL on a raw cursor, bypassing strict mode and the engine's statement protocol](../../Verus_verification/bugs_issues.md#bug-plt-005); [A GraphQL GET request can run a Cypher write](../../Verus_verification/bugs_issues.md#bug-plt-013); [The Neo4j-compatible HTTP routes return at most 1,000 rows of an answer without saying so](../../Verus_verification/bugs_issues.md#bug-plt-108)

Open questions: [Should the REST dispatcher's `/metaPath` take a graph?](../../Verus_verification/open_questions.md#HD-1604)

Assumption review evidence: Changed from decisions.md: **no**. Same reading. Added: spec 230 is absent from the repository and the mirror, and a supplied graph key is ignored silently.

State machines: [http rows](../../Verus_verification/models/http_rows/manifest.json)


Findings: [The Neo4j HTTP transaction route answers a whole node as three text columns](../../Verus_verification/bugs_issues.md#bug-plt-126) (iteration 55)

### access.mcp

- Sources: [ADMIN_GUIDE §3 and §4 (The MCP classes)](../../../docs/ADMIN_GUIDE.md); [MCPTools.cls](../../../iris_src/src/Graph/KG/MCPTools.cls); [MCPToolSet.cls](../../../iris_src/src/Graph/KG/MCPToolSet.cls)
- agent
- security

The tool set's only policy is console auditing. The evidence-search tool is documented as taking natural-language text but binds its input as a node ID. Live coverage needs `%AI` (`tests/integration/test_mcp_tools.py`).

Findings: [The MCP evidence search binds its natural-language input as a node ID](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-plt-020)

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

Findings: [A Neo4j HTTP `tx/commit` request keeps the writes of its successful statements when another statement fails, and runs the statements after the failure](../../Verus_verification/bugs_issues.md#bug-plt-136)

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
