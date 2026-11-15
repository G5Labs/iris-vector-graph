#!/usr/bin/env python3
"""Write module 16's audit outputs from the curated records below and the live run results under $RUN_DIR.

    python experiment/playbook-completion/live/breadth-c/16/build_outputs.py

Outputs: experiment/playbook-completion/{findings/audit,footprints,modules}/16.json. Journal fields are copied from
the run JSONs ($RUN_DIR/breadth-c/16/s*.json); every live claim names the registered run id that observed it.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMP = HERE.parents[2]
RUN = Path(os.environ["RUN_DIR"]) / "breadth-c" / "16"
PIN = "3eaa79cf77d3e0a879b2cced634cf2729d81499e"


def load(name):
    p = RUN / name
    return json.loads(p.read_text()) if p.exists() else {"checks": {}}


S1, S2, S3 = load("s1_cypher_http.run2.json"), load("s2_bolt_sessions.json"), load("s3_graphql_sample_api.json")
S4, S5, S6 = load("s4_server_retry.json"), load("s5_misc.json"), load("s6_status_maps.json")
S7, S8 = load("s7_more_writers.json"), load("s8_followup.json")


def jsum(j):
    if not j:
        return None
    keep = ("label", "pids", "records", "outermost_commits_by_pid", "stores_written", "stores_written_in_txn",
            "stores_with_nontransactional_increments", "stores_written_outside_any_txn", "error",
            "other_pids_in_window")
    return {k: j.get(k) for k in keep}


def chk(S, k):
    return S.get("checks", {}).get(k, {})


def ev(kind, ref):
    return {"kind": kind, "ref": ref}


MC = ev("mc", "pending:main (models/breadth-c)")
MC_BOLT = [ev("mc", "cmc-unit-bolt-as-built-atomic"), ev("mc", "cmc-unit-bolt-as-built-once"),
           ev("mc", "cmc-unit-bolt-reviewed"), ev("control", "cmc-unit-ctl-rollback"), ev("mc", "cmc-unit-wit-bolt")]
MC_HTTP = [ev("mc", "cmc-unit-http-as-built-atomic"), ev("mc", "cmc-unit-http-reviewed")]
MC_RETRY = [ev("mc", "cmc-retry-as-built-once"), ev("mc", "cmc-retry-as-built-honest"), ev("mc", "cmc-retry-reviewed"),
            ev("control", "cmc-retry-ctl-client"), ev("control", "cmc-retry-ctl-server"),
            ev("mc", "cmc-retry-wit-read"), ev("mc", "cmc-retry-wit-write")]

# ------------------------------------------------------------------------------------------------- findings
s4inc, s4anon, s4keyed = chk(S4, "inc"), chk(S4, "anon"), chk(S4, "keyed")
s8u, s8d, s8s = chk(S8, "F1604.updateProtein_journal"), chk(S8, "F1614.demo_without_key"), chk(
    S8, "P1607.terminal_read_no_length")
retry_repro = bool(s4inc.get("reproduced")) or bool(s4anon.get("reproduced"))

F = []
F.append(dict(
    id="F-1601", module="16", title="Bolt BEGIN, COMMIT and ROLLBACK do nothing; every RUN commits at once",
    intended="A Bolt explicit transaction is atomic: ROLLBACK discards the writes made since BEGIN (Bolt protocol, "
             "P-1612; API-B9.10 'A rollback should undo the writes made since the driver began its transaction').",
    observed="Live (c16-s1-cypher-http): neo4j driver 6.4.1 began a transaction, ran CREATE c16:b1, rolled back; the "
             "node is still there (count 1). The journal shows the RUN's write committed in its own outermost IRIS "
             "transaction before ROLLBACK arrived. A managed transaction (execute_write) whose second statement fails "
             "keeps the first statement's node c16:b2. Source: BEGIN/COMMIT answer SUCCESS and ROLLBACK only clears "
             "pending rows (iris_vector_graph/bolt_server.py:500-510); RUN calls engine.execute_cypher, which commits "
             "(bolt_server.py:567-591).",
    disposition="reproduced-live",
    evidence=[ev("live", "c16-s1-cypher-http"), ev("inspected", "iris_vector_graph/bolt_server.py:500-510"),
              ev("inspected", "iris_vector_graph/bolt_server.py:567-622"), *MC_BOLT],
    gates=["3.5-handlers", "3.5-decoders", "3.7 ambiguous acknowledgement", "3.3-model-check"],
    severity="S2", confidence="high",
    remedy="Run a Bolt transaction's RUNs inside one engine write transaction and commit/roll it back on "
           "COMMIT/ROLLBACK, or refuse BEGIN with a FAILURE that says explicit transactions are unsupported.",
    model_hint="as-built: each RUN commits immediately; BEGIN/COMMIT/ROLLBACK are acknowledgements only "
               "(bolt_server.py:500-510, 580). A driver retry of a managed unit of work after a failure re-applies "
               "the committed statements. Reviewed (decisions.md HD-1603 policy applied to Bolt units): RUNs of a "
               "BEGIN..COMMIT unit become visible together at COMMIT; ROLLBACK leaves no effect; a retried unit applies "
               "once. Invariant: committed effects == effects of COMMITted units.",
    notes="Driver retries make it worse: execute_write retries a unit after transient errors, re-running statements "
          "that already committed."))
F.append(dict(
    id="F-1602", module="16", title="Bolt PULL {n} drops every row after the first n",
    intended="PULL {n} returns at most n records and has_more=true while rows remain (Bolt protocol, P-1612; API-B9.11).",
    observed="Live (c16-s1-cypher-http): MATCH over three C16F nodes with driver fetch_size=2 returned 2 rows "
             "(c16:f1, c16:f2); the default fetch size returned 3. Source: rows[:n], SUCCESS without has_more, "
             "pending result discarded (iris_vector_graph/bolt_server.py:624-660).",
    disposition="reproduced-live",
    evidence=[ev("live", "c16-s1-cypher-http"), ev("inspected", "iris_vector_graph/bolt_server.py:624-660")],
    gates=["3.5-decoders", "3.5-handlers"], severity="S2", confidence="high",
    remedy="Keep the remainder and answer has_more: true until drained; unit test PULL {n:2} over three rows.",
    notes="Silent truncation: the driver reports success with fewer rows."))
F.append(dict(
    id="F-1603", module="16", title="The generated GraphQL server mixes graphs in one answer",
    intended="SYS-I2 / API-B10.3 / API-B15.8: an answer about one graph holds no content of another; a read with no "
             "graph reads the default graph (HD-0201).",
    observed="Live (c16-s3-graphql-sample-api, create_app over AUDITC): node(id:'c16:x') of the default graph listed "
             "outgoing [C16_DEF_EDGE->c16:z, C16_G1_EDGE->c16:y]; the second edge lives only in graph c16g1. "
             "nodes(label:'C16Q', limit:3) answered [] although default-graph node c16:qz has the label: the page was "
             "cut from all graphs' ids (three c16g1-only nodes) and then read in the default graph. Source: "
             "iris_vector_graph/gql/resolvers.py:32-46, :90-133 (no graph_id), gql/engine.py:32-57 (field discovery "
             "joins rdf_props to rdf_labels on s only).",
    disposition="reproduced-live",
    evidence=[ev("live", "c16-s3-graphql-sample-api"), ev("inspected", "iris_vector_graph/gql/resolvers.py:32-133"),
              ev("inspected", "iris_vector_graph/gql/engine.py:32-57")],
    gates=["3.4-declared-reads", "3.1-coverage", "SYS-I2"], severity="S1", confidence="high",
    remedy="Filter every statement by graph_id (default graph unless a graph argument names one), as "
           "api/gql/core/resolvers.py does since spec 230; e2e test with one id in two graphs.",
    notes="Isolation leak of edge facts across graphs; a named graph is a tenant unit (spec 256)."))
F.append(dict(
    id="F-1604", module="16", title="The sample API's biomedical fields and its update mutation ignore graphs",
    intended="API-B6.6/B6.7/B15.8: biomedical fields read one graph; updateProtein changes only the named node in "
             "one graph (CONTEXT.md:44-48).",
    observed="Live (c16-s3-graphql-sample-api): protein(id:'c16:p1') answered labels [Protein, Protein, C16G1Label], "
             "name 'p-g1' and interactsWith [c16:p2] — the c16g1 copy's label, property and edge merged into the "
             "default-graph protein. updateProtein(name:'p-updated') rewrote the name property in BOTH graphs "
             "(props_after shows c16g1 name 'p-updated'). " +
             (f"Journal (c16-s8-followup): the mutation wrote {s8u.get('journal', {}).get('stores_written')} on IRIS "
              f"process(es) {s8u.get('journal', {}).get('pids')}, outermost commits "
              f"{s8u.get('journal', {}).get('outermost_commits_by_pid')}, outside any transaction: "
              f"{s8u.get('journal', {}).get('stores_written_outside_any_txn')}; cross-graph rewrite reproduced again: "
              f"{s8u.get('reproduced')}." if s8u else "Journal capture pending (c16-s8-followup).") +
             " Source: api/gql/loaders.py:19-45, :183-272 (WHERE s IN ...), examples/domains/biomedical/resolver.py:"
             "240-278 (UPDATE Graph_KG.rdf_props ... WHERE s = ? AND key = ?).",
    disposition="reproduced-live",
    evidence=[ev("live", "c16-s3-graphql-sample-api"), ev("live", "c16-s8-followup"),
              ev("inspected", "api/gql/loaders.py:19-272"),
              ev("inspected", "examples/domains/biomedical/resolver.py:240-278")],
    gates=["3.4-declared-reads", "3.4-ownership", "3.3a-writesets", "SYS-I2"], severity="S1", confidence="high",
    remedy="Add graph_id = ? (default graph) to every loader statement and route the update through the engine with "
           "graph=; e2e test with one id in two graphs.",
    notes="The update bypasses the engine (no write transaction wrapper, no ledger guard) and writes another "
          "tenant's graph."))
F.append(dict(
    id="F-1605", module="16", title="The sample API's nodes field names Graph_KG instead of the engine's schema",
    intended="Spec 262 / API-B6.5: surfaces read the engine's IVG Schema (engine._ivg_schema); the generated server "
             "does (iris_vector_graph/gql/engine.py:14-15).",
    observed="Source at the pin: api/gql/core/resolvers.py:172-175, :206-274 and api/gql/loaders.py hard-code "
             "Graph_KG. Not reproducible live here: AUDITC is installed under Graph_KG and lanes may not create a "
             "namespace with another IVG Schema (CONVENTIONS.md scope control). The server classes are not affected: "
             "class deploy rewrites the Graph_KG token to the chosen schema (iris_vector_graph/_engine/"
             "class_deploy.py:112-117), so MCPTools/PyOps literals are rewritten at deploy.",
    disposition="confirmed-source",
    evidence=[ev("inspected", "api/gql/core/resolvers.py:172-274"), ev("inspected", "api/gql/loaders.py:29-263"),
              ev("inspected", "iris_vector_graph/_engine/class_deploy.py:112-117")],
    gates=["3.4-declared-reads", "3.2-coverage"], severity="S2", confidence="high",
    remedy="Build the SQL from engine._ivg_schema; run the GraphQL tests on a custom-schema namespace.",
    notes="Live check blocked-access: needs a namespace installed under a non-default IVG Schema."))
F.append(dict(
    id="F-1606", module="16", title="The sample API's Cypher route accepts a timeout and a cache flag and uses neither",
    intended="api/models/cypher.py:41-58 documents timeout as 'Query execution timeout' (1-300 s); API-B5.7.",
    observed="Live (c16-s3-graphql-sample-api): POST /api/cypher with timeout=1 ran a 3-way cross join of 120 nodes "
             "for 1.83 s and answered 200 with the full count (1,728,000). Source: api/routers/cypher.py:94-260 never "
             "reads request.timeout or enable_cache.",
    disposition="reproduced-live",
    evidence=[ev("live", "c16-s3-graphql-sample-api"), ev("inspected", "api/models/cypher.py:41-58"),
              ev("inspected", "api/routers/cypher.py:94-260")],
    gates=["3.5-handlers", "3.6-capacity"], severity="S3", confidence="medium",
    remedy="Enforce the timeout (statement timeout or cancel) or remove the fields from the model and docs.",
    notes="Margin is modest (1.83 s against 1 s) but the source shows the field is never read."))
F.append(dict(
    id="F-1607", module="16", title="Two Cypher entries of the sample API bypass the engine and answer differently",
    intended="API-B5.8: the route answers each query as the engine's execute_cypher does (4.7.0 row 22 rewrite).",
    observed="Live (c16-s3-graphql-sample-api) with UNWIND $p AS e RETURN e, p=['[2]',[2],true,'1']: "
             "engine.execute_cypher and the Cypher HTTP server (c16-s1) answer [['[2]'],[[2]],[true],['1']]; the "
             "sample API's POST /api/cypher answers 500 'query execution failed' and its GraphQL executeCypher answers "
             "data {error: '<PARAMETER ERROR> Invalid number of parameters'}. Source: api/routers/cypher.py:118-166 "
             "and api/gql/schema.py:170-230 call parse_query/translate_to_sql directly, skipping "
             "rewrite_ambiguous_param_unwind (iris_vector_graph/_engine/query.py:1900).",
    disposition="reproduced-live",
    evidence=[ev("live", "c16-s3-graphql-sample-api"), ev("live", "c16-s1-cypher-http"),
              ev("inspected", "api/routers/cypher.py:118-166"), ev("inspected", "api/gql/schema.py:149-230")],
    gates=["3.5-handlers", "3.6 composition (one semantics per query)"], severity="S2", confidence="high",
    remedy="Call engine.execute_cypher from both entries (keeping the hop cap), or apply the same rewrite; parity "
           "test across the Cypher entries.",
    notes="The divergence differs from the original prediction (pre-4.7.0 coerced rows): at this pin both bypassing "
          "entries fail on the input instead. Either way they do not answer as the engine does."))
F.append(dict(
    id="F-1608", module="16", title="The sample API lets two threads use its one IRIS connection at once",
    intended="API-B4.5: two calls never use the one IRIS connection at once (DB-API threadsafety 1, P-1605; "
             "CHANGELOG 4.6.5 fixed the same pattern in cypher_api with _engine_lock).",
    observed="Source: no lock around the shared connection (api/main.py:100-113 health is a sync def run on the "
             "thread pool; api/routers/cypher.py:94 is async with blocking DB calls on the event loop). Live "
             "(c16-s3-graphql-sample-api): 12 s with two threads on /health and one on /api/cypher: 6,943 health "
             "probes and 3,184 queries, 0 non-200 answers and 0 wrong counts on IRIS Community 2026.1 with "
             "intersystems-irispython 5.3.2.",
    disposition="not-reproduced",
    evidence=[ev("live", "c16-s3-graphql-sample-api"), ev("inspected", "api/main.py:100-113"),
              ev("inspected", "api/routers/cypher.py:94")],
    gates=["3.7 1 vs N processes/threads"], severity="S3", confidence="medium",
    remedy="Serialize use of the connection (as cypher_api._engine) or use one connection per request.",
    notes="The overlap was exercised but the failure (SQLCODE -400 seen upstream on 2026.3 AI with driver 5.4.1) did "
          "not occur on this build/driver. The code still relies on an unproved premise; obligation stays open."))
F.append(dict(
    id="F-1609", module="16", title="The FHIR event route's writes are not all-or-nothing",
    intended="API-B7.4 / SYS-I4: the writes of one call all happen or none do.",
    observed="Live (c16-s3-graphql-sample-api): POST /fhir-event/ with graph c16g2 and date 1960-01-01 answered 500 "
             "('IRIS write failed: ... TemporalEdgeInput timestamp >= 0') after both create_node calls committed; "
             "nodes c16:fe1 and c16:fp1 remain in c16g2. Journal: two outermost commits on the server's IRIS process "
             "before the refusal. A successful call journals three separate outermost commits, and the temporal "
             "index entries (^KG tout/tin/tlast/bucket/tagg) are written outside any transaction. Source: "
             "api/routers/fhir_event.py:318-346.",
    disposition="reproduced-live",
    evidence=[ev("live", "c16-s3-graphql-sample-api"), ev("inspected", "api/routers/fhir_event.py:283-365"),
              ev("mc", "cmc-unit-http-as-built-atomic (analogous shape: several committed writes per request; not a "
                       "model of this route)")],
    gates=["3.5-handlers", "3.3a-writesets", "SYS-I4"], severity="S2", confidence="high",
    remedy="Validate first and run the three writes in one engine transaction (write_txn); a unit test that a failed "
           "edge write leaves no node.",
    notes="Deprecated route (removed in 5.0). The outside-transaction temporal ^KG writes belong to "
          "create_edge_temporal (module 05) and are reported there as an observation, not as a module-16 finding."))
F.append(dict(
    id="F-1610", module="16", title="The Neo4j HTTP commit route runs its statements one by one",
    intended="Neo4j's /db/neo4j/tx/commit is a begin-and-commit-in-one-request transaction: all statements or none "
             "(P-1612); API-B8.6.1.",
    observed="Live (c16-s1-cypher-http): three statements (CREATE c16:t1; an unparsable line; CREATE c16:t3) answered "
             "400 with one SyntaxError, and both c16:t1 and c16:t3 are committed — the third ran after the failure. "
             "Journal: two separate outermost commits on two different IRIS processes: the failed statement made "
             "_run_cypher reset the engine (closing the connection) and retry, so statement 3 ran on a new "
             "connection. Source: iris_vector_graph/cypher_api.py:379-410, :239-250.",
    disposition="reproduced-live",
    evidence=[ev("live", "c16-s1-cypher-http"), ev("inspected", "iris_vector_graph/cypher_api.py:379-410"), *MC_HTTP],
    gates=["3.5-handlers", "3.6 composition", "3.3-model-check"], severity="S2", confidence="high",
    remedy="Run the statements in one engine transaction and roll back on the first error (Neo4j stops there), or "
           "document the route as non-atomic.",
    model_hint="as-built: per-statement commit, later statements still run after an error "
               "(cypher_api.py:391-405). Reviewed: unit atomicity — the request's effects are all statements' or "
               "none; processing stops at the first error. Invariant: after a 4xx/5xx answer no statement effect "
               "of the request is committed."))
F.append(dict(
    id="F-1611", module="16", title="The generated GraphQL server's health route always says healthy",
    intended="API-B10.6: health says so when IRIS does not answer (the sample API answers 503 since 4.6.3, "
             "CHANGELOG.md:493-497).",
    observed="Live (c16-s3-graphql-sample-api): create_app over an engine whose connection was closed answered "
             "GET /health 200 {status: healthy, database: disconnected}. Source: iris_vector_graph/gql/__init__.py:58-67.",
    disposition="reproduced-live",
    evidence=[ev("live", "c16-s3-graphql-sample-api"), ev("inspected", "iris_vector_graph/gql/__init__.py:58-67")],
    gates=["3.5-decoders (status map)"], severity="S3", confidence="high",
    remedy="Answer 503 when the probe fails, as api/main.py does.", notes=""))
p1607_native = all(not chk(S5, f"P1607.{c}").get("holds", True) for c in
                   ("%Stream.TmpCharacter", "%CSP.CharacterStream", "%CSP.BinaryStream")) and bool(S5.get("checks"))
F.append(dict(
    id="F-1612", module="16", title="The REST dispatcher may read only the first chunk of a large request body",
    intended="API-B11.12: the routes read a request body of any size.",
    observed="The finding rests on premise P-1607 (Read() with no length returns at most 32,000 characters). On IRIS "
             "Community 2026.1 the premise does not hold for the CSP request stream classes: a 50,000-character "
             "stream read with Read() and no length returned all 50,000 characters for %CSP.BinaryStream, "
             "%CSP.CharacterStream and %Stream.TmpCharacter (Native API invoke, c16-s5-fraud-sql-stream" +
             (f"; ObjectScript in a terminal, c16-s8-followup: {s8s.get('result')}" if s8s else "") + "). "
             "End-to-end through a web application is blocked: no web application in the instance dispatches to "
             "Graph.KG.Service (Security.Applications read, $RUN_DIR/breadth-c/16/webapps.txt) and creating one "
             "changes instance security, which lanes may not do.",
    disposition="refuted",
    evidence=[ev("live", "c16-s5-fraud-sql-stream"), ev("live", "c16-s8-followup"),
              ev("inspected", "iris_src/src/Graph/KG/Service.cls:321-327")],
    gates=["3.2-coverage (P-1607)", "3.5-decoders"], severity="S4", confidence="medium",
    remedy="None needed for the 32,000 premise on this build; keep a large-body test (bodies past the long-string "
           "limit still fail at %FromJSON of one string).",
    notes="blocked-access for the end-to-end check: dependency = a %CSP.REST web application dispatching to "
          "Graph.KG.Service (Graph.KG.Service.CreateWebApp), which modifies Security.Applications. Other IRIS "
          "versions may still default to 32,000 (documented %Stream.Object.Read signature)."))
F.append(dict(
    id="F-1613", module="16", title="The MCP vector lookup treats the client's text as a node id",
    intended="MCPTools.cls:189-192 documents query as a natural-language description; API-B12.9.",
    observed="Source at the pin: EvidenceSearch binds query as node_id in the subquery that fetches that node's "
             "vector (iris_src/src/Graph/KG/MCPTools.cls:193-221). Not run: Graph.KG.MCPService/MCPToolSet/MCPTools "
             "cannot be deployed on IRIS Community (setup skipped them: needs %AI.MCP.Service, %AI.ToolSet, %AI.Tool, "
             "%AI.Policy.ConsoleAudit; $RUN_DIR/setup/deploy-AUDITC.json).",
    disposition="blocked-access",
    evidence=[ev("inspected", "iris_src/src/Graph/KG/MCPTools.cls:189-221"),
              ev("inspected", "$RUN_DIR/setup/deploy-AUDITC.json (objectscript_skipped)")],
    gates=["3.5-handlers"], severity="S2", confidence="high",
    remedy="Embed the text before the search (engine.embed_text or IRIS EMBEDDING()), or document the argument as a "
           "node id; e2e test on an AI build.",
    notes="Blocked dependency: IRIS %AI package (%AI.MCP.Service, %AI.ToolSet, %AI.Tool, %AI.Policy.ConsoleAudit), "
          "absent on Community 2026.1. Source-confirmed."))
F.append(dict(
    id="F-1614", module="16", title="The demo server's write routes need no key",
    intended="CHANGELOG.md:994-996 says every app needs the key; API-B13.2.",
    observed=(f"Live (c16-s8-followup): demo server started with IVG_API_KEY set; without the key GET "
              f"/api/status/none answered {s8d.get('status_route')} and POST /api/fhir/live/add answered "
              f"{s8d.get('live_add')} (validation reached, not 401). " if s8d else "Live check pending. ") +
             "Source: src/iris_demo_server/app.py:1-22 adds no ApiKeyMiddleware; routes/fhir.py:503-533 write to the "
             "FHIR repository and start a sync; __main__ binds 0.0.0.0:8200 (app.py:503-504).",
    disposition="reproduced-live" if s8d.get("reproduced") else "confirmed-source",
    evidence=[ev("live", "c16-s8-followup"), ev("inspected", "src/iris_demo_server/app.py:1-22"),
              ev("inspected", "src/iris_demo_server/routes/fhir.py:503-533")],
    gates=["3.5-handlers", "API-T1"], severity="S2", confidence="high",
    remedy="Add ApiKeyMiddleware and bind 127.0.0.1 by default, or document the demo server as presenter-only.",
    notes="The write itself was not attempted (no FHIR repository on Community); the key gate is absent for every "
          "route."))
F.append(dict(
    id="F-1615", module="16", title="The fraud server's vector lookup always falls back to zeros",
    intended="API-B13.7: the fraud score reads the payer's stored vector.",
    observed="Live (c16-s5-fraud-sql-stream): the statement as written fails in AUDITC with SQLCODE -30 (table "
             "SQLUSER.KG_NODEEMBEDDINGS not found); schema-qualified it fails with SQLCODE -29 (field EMBEDDING not "
             "found); the intended form (emb, Graph_KG, default graph) prepares. Source: src/iris_fraud_server/app.py:"
             "246-279 also calls fetchone() on an iris.sql.exec result (none exists, app.py:211) and returns "
             "np.zeros(768) on any error.",
    disposition="reproduced-live",
    evidence=[ev("live", "c16-s5-fraud-sql-stream"), ev("inspected", "src/iris_fraud_server/app.py:246-279")],
    gates=["3.4-statements", "3.5-decoders"], severity="S2", confidence="high",
    remedy="Read emb from the schema-qualified table for the default graph and iterate the result; a test that a "
           "stored vector reaches the score.", notes="Silent false result: errors become a zero vector."))
# ---- new findings
F.append(dict(
    id="F-C1601", module="16", title="A finished Bolt session never gives back its IRIS connection",
    intended="API-T8.3 says each Bolt session opens its own IRIS connection; P-1609: each connection counts against "
             "the instance's connection/licence limit (8 on this Community container), so a session must release it.",
    observed="Live (c16-s2-bolt-sessions): three sequential Bolt sessions (driver closed each, GOODBYE sent) left "
             "three new AUDITC IRIS processes alive 20 s later; they disappeared only when the server process "
             "stopped. Source: the session builds its engine lazily (iris_vector_graph/bolt_server.py:391-394) and "
             "its run() finally-blocks close only the socket (bolt_server.py:404, :423 WebSocket; :940, :957 TCP), "
             "never self._engine.conn.",
    disposition="reproduced-live",
    evidence=[ev("live", "c16-s2-bolt-sessions"), ev("inspected", "iris_vector_graph/bolt_server.py:391-423"),
              ev("inspected", "iris_vector_graph/bolt_server.py:922-960")],
    gates=["3.6-capacity", "3.7 reconnect / 1 vs N sessions", "3.5-handlers"], severity="S2", confidence="high",
    remedy="Close the session's engine connection when the session ends (finally block), or share a bounded pool.",
    notes="On Community a handful of Bolt sessions exhaust IRIS connections for every client of the instance; the "
          "refused connection then reaches the driver as Neo.ClientError.Statement.SyntaxError (F-C1602)."))
F.append(dict(
    id="F-C1602", module="16", title="Server and connection failures are reported as client syntax errors",
    intended="SYS-I9 (every refusal says why); Neo4j status codes distinguish ClientError (caller's fault, not "
             "retried) from TransientError/DatabaseError (P-1612); HTTP 4xx means the request was wrong.",
    observed="Live (c16-s6-status-maps, stub engine, no IRIS): a lost IRIS connection answers HTTP 400 on "
             "/api/cypher and /db/{db}/query/v2, 400 + 'Neo.ClientError.Statement.SyntaxError' on /db/neo4j/tx/commit, "
             "and a Bolt FAILURE 'Neo.ClientError.Statement.SyntaxError' (classification ClientError, not retryable) "
             "both when the session's engine cannot connect and when a query's connection fails. Source: "
             "cypher_api.py:367-376, :396-400, :451-460; bolt_server.py:617-622 map every exception to those codes. "
             "Also: the sample API answers an unknown function as 400 UNDEFINED_VARIABLE (c16-s3, "
             "api/routers/cypher.py:231-247); the generated server's semantic_search swallows every error as [] "
             "(iris_vector_graph/gql/resolvers.py:85-88).",
    disposition="confirmed-source",
    evidence=[ev("probe", "c16-s6-status-maps"), ev("inspected", "iris_vector_graph/cypher_api.py:367-460"),
              ev("inspected", "iris_vector_graph/bolt_server.py:614-622")],
    gates=["3.5-decoders", "SYS-I9"], severity="S3", confidence="high",
    remedy="Map connection/database failures to 5xx / Neo.TransientError.* (or DatabaseError) and keep "
           "SyntaxError for parse failures.", notes="Disposition is confirmed-source: the probe ran the real server code "
                                                    "(FastAPI app, Bolt TCP listener, neo4j driver) but the IRIS failure was "
                                                    "simulated by a stub engine, not observed on IRIS. Interacts with retry policy: a correct transient code would let "
                                                    "drivers retry, which is only safe once F-1601 is fixed."))
F.append(dict(
    id="F-C1603", module="16", title="Bolt listens on every interface unless the server is started by `ivg server start`",
    intended="docs/ADMIN_API.md:26-28: the Bolt listener 'listens on the address --host names, or on BOLT_TCP_HOST'; "
             "API-T9.1; HD-1705 working answer: local-only or explicit opt-in for unauthenticated external binding.",
    observed="Live (c16-s6-status-maps): `uvicorn iris_vector_graph.cypher_api:app --host 127.0.0.1` served HTTP on "
             "127.0.0.1:18617 and the Bolt listener on 0.0.0.0:18618. Source: cypher_api.py:51 defaults "
             "BOLT_TCP_HOST to 0.0.0.0; only the CLI sets it from --host (cli.py:429); the documented "
             "`python -m iris_vector_graph.cypher_api` binds HTTP 0.0.0.0:8000 and Bolt 0.0.0.0:7687 "
             "(cypher_api.py:779; ADMIN_API.md:22). With IVG_API_KEY unset the listener needs no credentials.",
    disposition="reproduced-live",
    evidence=[ev("probe", "c16-s6-status-maps"), ev("inspected", "iris_vector_graph/cypher_api.py:47-63"),
              ev("inspected", "iris_vector_graph/cli.py:419-441"), ev("inspected", "docs/ADMIN_API.md:13-28")],
    gates=["3.5-handlers", "HD-1705"], severity="S2", confidence="high",
    remedy="Default BOLT_TCP_HOST to the HTTP host (or 127.0.0.1) in the app itself, not only in the CLI; refuse an "
           "unauthenticated non-loopback bind unless explicitly forced.",
    notes="Deployment-default question is HD-1705 (intent-undecided); the mismatch with ADMIN_API's statement is "
          "a defect regardless."))
F.append(dict(
    id="F-C1604", module="16", title="The Cypher HTTP server runs a query again after any failure, writes included",
    intended="decisions.md HD-1603 (working answer): retry only a read, a write known not to have run, or a write "
             "with a verified idempotency key; an ambiguous commit outcome stays unknown.",
    observed=("Live (c16-s4-server-retry, fault injection of a lost acknowledgement after the engine's commit, "
              "through the real FastAPI app on AUDITC): " +
              f"SET n.counter = n.counter + 1 — one request moved the counter from {s4inc.get('counter_after_control')} "
              f"to {s4inc.get('counter_after_faulted')} and answered {s4inc.get('faulted', {}).get('status')}; "
              f"CREATE without a key — after the control run made 1 C16R2 node, ONE faulted request brought the total to "
              f"{s4anon.get('nodes_after_faulted')} (control total {s4anon.get('nodes_after_control')}); CREATE with an id answered "
              f"{s4keyed.get('faulted', {}).get('status')} {str(s4keyed.get('faulted', {}).get('body'))[:160]}. "
              if S4.get("checks") else "Live fault-injection pending. ") +
             "c16-s1 also shows a plain parse error triggering the reset-and-retry (two IRIS processes for one "
             "/db/neo4j/tx/commit). Source: _run_cypher retries once after any exception, resetting the engine "
             "(iris_vector_graph/cypher_api.py:239-250); every Cypher route uses it.",
    disposition="reproduced-live" if retry_repro else "confirmed-source",
    evidence=[ev("live", "c16-s4-server-retry"), ev("live", "c16-s1-cypher-http"),
              ev("inspected", "iris_vector_graph/cypher_api.py:239-260"), *MC_RETRY],
    gates=["3.7 ambiguous acknowledgement / crash / reconnect", "3.5-handlers", "3.3-model-check", "SYS-I6"],
    severity="S2", confidence="high" if retry_repro else "medium",
    remedy="Retry only reads or errors raised before the statement ran (connection refused at connect); otherwise "
           "return an unknown-outcome error; or carry an idempotency key end to end. Combine with the SDK retry "
           "(HD-1702, module 17) as one protocol.",
    model_hint="as-built: on any exception after execute_cypher (including after the engine's commit) the server "
               "resets the connection and re-executes the same query (cypher_api.py:241-250). Reviewed (HD-1603): "
               "re-execute only if the first attempt is known not to have committed or the query is a read; an "
               "ambiguous outcome is reported as unknown. Invariant: one client request applies its write at most "
               "once. Combined with the SDK's own POST retry (sdk.py, HD-1702) the as-built protocol can apply one "
               "logical write up to 4 times.",
    notes="The fault is a wrapper around engine.execute_cypher in the test process only (no product change); it "
          "models a connection lost after the server-side commit. Model: cmc-retry-as-built-once's shortest trace is "
          "the server re-running a committed write whose reply was lost; cmc-retry-as-built-honest: the client is told "
          "'failed' for an applied write. The client half (SDK POST retry) is module 17's F-C1703."))

findings = {"module": "16", "pin": PIN, "findings": F}

# ------------------------------------------------------------------------------------------------- footprints
s1 = S1.get("checks", {})
s3 = S3.get("checks", {})
s7 = S7.get("checks", {})


def jrun(run, j, declared_writes, claims_atomic):
    if not j:
        return None
    w = set(j.get("stores_written") or [])
    undeclared = sorted(w - set(declared_writes))
    out = {"run": run, **jsum(j), "undeclared_writes": undeclared}
    out["match"] = (not undeclared) and (not claims_atomic or len(j.get("outermost_commits_by_pid") or {}) <= 1 and
                                         sum((j.get("outermost_commits_by_pid") or {}).values()) <= 1)
    return out


NODE_W = ["sql:Graph_KG.nodes", "sql:Graph_KG.rdf_labels", "sql:Graph_KG.rdf_props", "global:^KG"]
EDGE_W = NODE_W + ["sql:Graph_KG.rdf_edges"]
E = []


def entry(**kv):
    E.append(kv)


entry(entry="POST /api/cypher (write)", role="writer",
      source="iris_vector_graph/cypher_api.py:351-376 -> _run_cypher :239-260 -> engine.execute_cypher "
             "(iris_vector_graph/_engine/query.py:1946-1967)",
      reads=["sql:Graph_KG.*  (per translated query)"], writes=EDGE_W + ["global:^NKG (version stamp)"],
      transaction="one engine write transaction per execute_cypher; on ANY exception the engine is reset (connection "
                  "closed) and the query re-run once on a new connection (HD-1603, F-C1604)",
      locks=["_engine_lock (threading.RLock, in-process only, cypher_api.py:149)"],
      claims_atomic="per Cypher statement (engine write wrapper)",
      journal=jrun("c16-s1-cypher-http", chk(S1, "A.api_cypher_write").get("journal"), EDGE_W, True))
entry(entry="POST /api/cypher (write) with a lost acknowledgement (fault injected after the engine's commit)",
      role="writer", source="iris_vector_graph/cypher_api.py:239-260 (retry after any exception)",
      reads=["as /api/cypher"], writes=["sql:Graph_KG.rdf_props"],
      transaction="first attempt commits; the server resets the engine and commits the same write again on a new "
                  "IRIS process", locks=["_engine_lock"], claims_atomic="one request applies its write once (HD-1603)",
      journal=jrun("c16-s4-server-retry", chk(S4, "inc").get("journal"), ["sql:Graph_KG.rdf_props", "global:^KG"],
                   True))
entry(entry="POST /db/neo4j/tx/commit (N statements)", role="writer",
      source="iris_vector_graph/cypher_api.py:379-410",
      reads=["as /api/cypher"], writes=EDGE_W,
      transaction="one engine transaction PER statement; later statements run after a failure",
      locks=["_engine_lock per statement"], claims_atomic="Neo4j endpoint contract: one transaction per request (P-1612)",
      journal=jrun("c16-s1-cypher-http", chk(S1, "A.F1610_tx_commit_partial").get("journal"), EDGE_W, True))
entry(entry="POST /db/{db}/query/v2", role="reader|writer", source="iris_vector_graph/cypher_api.py:436-460",
      reads=["as /api/cypher"], writes=EDGE_W, transaction="as /api/cypher (via _run_cypher)",
      locks=["_engine_lock"], claims_atomic="per statement", journal=None)
entry(entry="Bolt RUN (TCP / WebSocket), inside BEGIN..ROLLBACK", role="writer",
      source="iris_vector_graph/bolt_server.py:567-622; BEGIN/COMMIT/ROLLBACK :500-510",
      reads=["as execute_cypher"], writes=EDGE_W,
      transaction="each RUN commits its own engine transaction; BEGIN/COMMIT/ROLLBACK touch no transaction",
      locks=["none (one IRIS connection per session, never closed: F-C1601)"],
      claims_atomic="Bolt explicit transaction contract (P-1612)",
      journal=jrun("c16-s1-cypher-http", chk(S1, "A.F1601_bolt_rollback").get("journal"), EDGE_W, False))
entry(entry="POST /admin/load", role="writer",
      source="iris_vector_graph/cypher_api.py:623-643 -> import_graph_ndjson (iris_vector_graph/_engine/snapshot.py:1727)",
      reads=["request body (temp file)"], writes=EDGE_W, transaction="per line / per batch (import_graph_ndjson)",
      locks=["_engine_lock (thread pool)"], claims_atomic="no claim (ADMIN_API.md:260-281)",
      journal=jrun("c16-s7-more-writers", chk(S7, "admin_load").get("journal"), EDGE_W, False))
entry(entry="POST /admin/indexes/rebuild", role="writer", source="iris_vector_graph/cypher_api.py:597-610",
      reads=["sql:Graph_KG.rdf_edges", "sql:Graph_KG.nodes"], writes=["global:^KG", "global:^NKG"],
      transaction="rebuild_kg / rebuild_nkg (module 04)", locks=["_engine_lock"], claims_atomic="no claim",
      journal=None, note="namespace-wide rebuild: not run in a shared namespace")
entry(entry="POST /admin/embed", role="writer", source="iris_vector_graph/cypher_api.py:613-620 -> embed_nodes",
      reads=["sql:Graph_KG.nodes", "sql:Graph_KG.rdf_props"], writes=["sql:Graph_KG.kg_NodeEmbeddings | routed kg_emb_*"],
      transaction="module 06 embed_nodes", locks=["_engine_lock"], claims_atomic="no claim", journal=None,
      note="needs an embedder; not run")
entry(entry="POST /admin/schema/init", role="writer", source="iris_vector_graph/cypher_api.py:578-594 -> initialize_schema",
      reads=["^IVG.Deploy"], writes=["DDL, class compile, ^IVG.Deploy (module 01)"], transaction="module 01",
      locks=["_engine_lock"], claims_atomic="no claim", journal=None, note="forbidden by lane rules (compiles classes)")
entry(entry="DELETE /admin/queries/{id}", role="writer (process control)",
      source="iris_vector_graph/cypher_api.py:702-715", reads=[], writes=["IRIS process table (KillProcess)"],
      transaction="none", locks=["_engine_lock"], claims_atomic="n/a", journal=None)
entry(entry="GET /health, /schema, /indexes, /server, /metrics, /stats, /admin/export, /admin/queries; "
            "POST /admin/explain", role="reader", source="iris_vector_graph/cypher_api.py:268-284, :469-570, :646-740",
      reads=["sql:Graph_KG.nodes", "sql:Graph_KG.rdf_labels", "sql:Graph_KG.rdf_props", "sql:Graph_KG.rdf_edges",
             "%SYS.ProcessQuery (queries)", "%SYSTEM.Version"], writes=["(export: a temp file, removed)"],
      transaction="none", locks=["_engine_lock"], claims_atomic="n/a", journal=None)
entry(entry="sample API POST /api/cypher (write)", role="writer",
      source="api/routers/cypher.py:94-260 (translate_to_sql; START TRANSACTION..COMMIT on the shared connection)",
      reads=["sql:Graph_KG.*"], writes=EDGE_W,
      transaction="SQL START TRANSACTION / COMMIT / ROLLBACK when is_transactional (api/routers/cypher.py:139-158)",
      locks=["none (shared connection without a lock, F-1608)"], claims_atomic="statements of one query",
      journal=jrun("c16-s7-more-writers", chk(S7, "sample_api_cypher_create").get("journal"), EDGE_W, True))
entry(entry="sample API GraphQL executeCypher", role="writer", source="api/gql/schema.py:149-230",
      reads=["sql:Graph_KG.*"], writes=EDGE_W, transaction="as the sample API Cypher route",
      locks=["none"], claims_atomic="statements of one query", journal=None)
upd = s8u.get("journal")
entry(entry="sample API GraphQL updateProtein", role="writer",
      source="examples/domains/biomedical/resolver.py:240-290",
      reads=["sql:Graph_KG.nodes (node_exists, default graph)"], writes=["sql:Graph_KG.rdf_props (EVERY graph's row for s,key)"],
      transaction="UPDATE/INSERT per field then connection.commit()", locks=["none"],
      claims_atomic="no claim; API-B6.7 requires one node in one graph",
      journal=jrun("c16-s8-followup", upd, ["sql:Graph_KG.rdf_props"], False) if upd else None)
entry(entry="sample API GraphQL createProtein / deleteProtein", role="writer",
      source="examples/domains/biomedical/resolver.py:188-240, :299-320 (engine.create_node / delete_node, default graph)",
      reads=["engine"], writes=NODE_W + ["routed vector table (createProtein embedding)"],
      transaction="engine write wrappers", locks=["none"], claims_atomic="engine", journal=None)
entry(entry="sample API POST /fhir-event/", role="writer", source="api/routers/fhir_event.py:283-365",
      reads=["sql:Graph_KG.kg_NodeEmbeddings (already_embedded)"], writes=EDGE_W,
      transaction="three engine calls, each its own transaction; temporal ^KG entries outside any transaction",
      locks=["none"], claims_atomic="API-B7.4 should be all-or-nothing",
      journal=jrun("c16-s3-graphql-sample-api", chk(S3, "API.fhir_event_success_footprint").get("journal"), EDGE_W, True))
entry(entry="sample API GraphQL node/nodes/stats/protein/gene/pathway; generated GraphQL node/nodes/stats/"
            "semantic_search/outgoing/incoming", role="reader",
      source="api/gql/core/resolvers.py:60-355; api/gql/loaders.py; iris_vector_graph/gql/resolvers.py:10-133",
      reads=["sql:Graph_KG.nodes", "sql:Graph_KG.rdf_labels", "sql:Graph_KG.rdf_props", "sql:Graph_KG.rdf_edges",
             "kg_KNN_VEC routes"], writes=[], transaction="none", locks=["none"], claims_atomic="n/a", journal=None,
      note="declared-read violations: rdf_edges/rdf_labels/rdf_props read without graph_id (F-1603, F-1604)")
entry(entry="generated GraphQL cypher field", role="writer", source="iris_vector_graph/gql/resolvers.py:136-165",
      reads=["as execute_cypher"], writes=EDGE_W, transaction="engine.execute_cypher", locks=["none"],
      claims_atomic="per statement", journal=None)
entry(entry="Graph.KG.Service VectorSearch / HybridSearch / MetaPath", role="reader",
      source="iris_src/src/Graph/KG/Service.cls:263-320 -> Graph.KG.PyOps",
      reads=["kg_KNN_VEC / kg_RRF_FUSE / kg_TXT routes", "sql:Graph_KG.embedding_registry", "global:^KG (MetaPath)"],
      writes=[], transaction="none", locks=["none"], claims_atomic="n/a", journal=None,
      note="blocked-access live: no web application dispatches to Graph.KG.Service")
entry(entry="Graph.KG.Service.CreateWebApp", role="writer (security config)", source="iris_src/src/Graph/KG/Service.cls:30-75",
      reads=["Security.Applications (%SYS)"], writes=["Security.Applications, Security.Roles, SQL GRANTs"],
      transaction="none", locks=["none"], claims_atomic="refuses another app before changing anything "
                                                        "(Service.cls:39-41)", journal=None,
      note="not run: modifies instance security")
entry(entry="MCPTools CypherQuery / RunSQL / LoadGraph / GraphStats / PPRWalk / EvidenceSearch", role="writer|reader",
      source="iris_src/src/Graph/KG/MCPTools.cls:9-221", reads=["sql:Graph_KG.*"],
      writes=["any (RunSQL runs arbitrary SQL; LoadGraph loads files)"], transaction="per tool call",
      locks=["none"], claims_atomic="n/a", journal=None, note="blocked-access: %AI classes absent on Community")
entry(entry="demo server /api/fhir/live/add, /api/fhir/live/sync", role="writer",
      source="src/iris_demo_server/routes/fhir.py:503-533", reads=["FHIR repository (HTTP)"],
      writes=["FHIR repository (PUT Condition)", "FHIR graph sync (module 15)"], transaction="FHIR server / sync",
      locks=["sync lock (module 15)"], claims_atomic="n/a", journal=None,
      note="needs IRIS for Health FHIR server: not run")

for e in E:  # a Bolt unit that was rolled back must leave no committed write
    if e["entry"].startswith("Bolt RUN") and e.get("journal"):
        if sum((e["journal"].get("outermost_commits_by_pid") or {}).values()) >= 1:
            e["journal"]["match"] = False
            e["journal"]["mismatch"] = "the RUN's write committed in its own outermost transaction; the unit was then " \
                                       "rolled back by the client and the write stayed (F-1601)"
j_valid = [e for e in E if e.get("journal")]
footprints = {
    "module": "16", "pin": PIN,
    "method": "Declared footprints from source; journal validation with experiment/playbook-completion/traces/"
              "journal.py via live/breadth-c/16/jsrv.py journal_by_marker (the server's IRIS pid found from the scratch "
              "id in the journaled global nodes; all records of that pid in the window classified as in-transaction, "
              "non-transactional increment (ID counters, ^KG(\"__version\")) or outside any transaction).",
    "entries": E, "validated": len(j_valid),
    "mismatches": [
        {"entry": e["entry"], "run": e["journal"]["run"],
         "what": e["journal"].get("mismatch") or ("undeclared writes " + str(e["journal"]["undeclared_writes"]) if e["journal"]["undeclared_writes"]
                  else "") + ("; " if e["journal"]["undeclared_writes"] else "") +
                 ("more than one outermost transaction for a unit claimed atomic: " +
                  json.dumps(e["journal"]["outermost_commits_by_pid"]) if not e["journal"]["match"] else "")}
        for e in j_valid if not e["journal"]["match"]] + [
        {"entry": "sample API POST /fhir-event/ (success path)", "run": "c16-s3-graphql-sample-api",
         "what": "temporal index entries ^KG(\"tout\"|\"tin\"|\"tlast\"|\"bucket\"|\"tagg\", graph, ...) journaled "
                 "outside any transaction (create_edge_temporal, module 05 owner): observation passed to module 05"}],
}

# ------------------------------------------------------------------------------------------------- module record
inv = json.loads((COMP / "models/breadth-c/inventory.json").read_text())
rec16 = inv["reconciliation"]["16"]
omissions = [
    {"name": "sample API GraphQL createProtein / deleteProtein (writers)", "file:line": "api/gql/schema.py:253-286; "
     "examples/domains/biomedical/resolver.py:188-320", "why": "no statement covers these mutations (only updateProtein, API-B6.7)"},
    {"name": "Bolt DISCARD (and LOGOFF semantics)", "file:line": "iris_vector_graph/bolt_server.py:487-516",
     "why": "no statement or cell; DISCARD drops pending rows without has_more handling"},
    {"name": "Bolt session connection lifecycle", "file:line": "iris_vector_graph/bolt_server.py:391-423, 922-960",
     "why": "no statement says a session releases its IRIS connection (F-C1601)"},
    {"name": "Cypher HTTP server retry-on-any-error (_run_cypher)", "file:line": "iris_vector_graph/cypher_api.py:239-260",
     "why": "only an open question API-Q8.5.2 (HD-1603); no B/X statement of the as-built behavior"},
    {"name": "cypher_api.wsgi_app (a2wsgi, running inside IRIS)", "file:line": "iris_vector_graph/cypher_api.py:781-785",
     "why": "deployment entry point not stated (lifespan/Bolt behaviour under WSGI unstated)"},
    {"name": "python -m iris_vector_graph.cypher_api / uvicorn entry (Bolt bind default)", "file:line":
     "iris_vector_graph/cypher_api.py:47-63, 777-779", "why": "API-T9.1 states the CLI path only (F-C1603)"},
    {"name": "demo seed entry points and IVGDemo.FHIRLoad", "file:line": "src/iris_demo_server/services/bio_demo_data.py:227; "
     "src/iris_demo_server/services/fhir_demo_data.py:452; src/iris_demo_server/objectscript/IVGDemo/FHIRLoad.cls:13",
     "why": "writers that seed demo namespaces (and load a class); no statement"},
    {"name": "MCP stdio server scripts/mcp/ivg_mcp_server.py + config/mcp-graph.toml", "file:line":
     "scripts/mcp/ivg_mcp_server.py:1-30; config/mcp-graph.toml:1-20", "why": "an MCP interface (Cypher + graph loading) "
     "outside every module's Scope; recorded system-wide by module 00"},
    {"name": "Neo4j Browser bundle (iris_vector_graph/browser_static) served at /browser", "file:line":
     "iris_vector_graph/cypher_api.py:73-90", "why": "API-T8.11 covers its key gate only; the vendored bundle is "
     "excluded from the wheel (pyproject.toml wheel exclude) and owned by no Scope"},
]
uncovered_classes = {
    "covered_under_another_name": "admin routes and handlers (API-B8.10, T8.10.x); route handler functions cited "
        "by line range in Source columns; Service.cls VectorSearch/HybridSearch/MetaPath (API-B11 by route path) and "
        "CheckWebApp/WebAppRole/EnsureWebAppRole/GrantWebAppSql (API-B11.1, T11.5, X11.4); biomedical relationship "
        "fields and gene/pathway (API-B6.6); generated resolvers (API-B10.x) incl. semantic_search ('a vector search'); "
        "Bolt HELLO/LOGON/RUN/PULL/BEGIN/COMMIT/ROLLBACK/RESET/GOODBYE (API-B9.x); demo and fraud routes (API-B13.x)",
    "internal_helpers": "PackStream pack/unpack/encode/decode/negotiate (bolt_server.py), security.py and routing.py "
        "helpers (API-B14 group by file), DataLoader batch_load_fn, pydantic validators of demo models, demo client "
        "services, api/dependencies.py, api/gql/core/domain_resolver.py registry",
    "genuine_omissions": len(omissions),
}
cells_map = {
    "Cypher HTTP call": {"health": "GET /health", "cypher read": "POST /api/cypher, /db/neo4j/tx/commit, /db/{db}/query/v2",
                         "cypher write": "same", "admin write": "POST|DELETE /admin/*", "explain": "POST /admin/explain"},
    "Bolt session with a key set": {"hello with key": "TAG_HELLO/TAG_LOGON", "hello with wrong key": "TAG_HELLO/TAG_LOGON",
                                    "run": "TAG_RUN", "reset": "TAG_RESET", "rollback": "TAG_ROLLBACK"},
    "graph a caller names": {"GraphQL node read": "sample API node/nodes; generated node/nodes",
                             "FHIR event write": "POST /fhir-event/", "REST vector search": "Graph.KG.Service.VectorSearch",
                             "Cypher read with USE GRAPH": "POST /api/cypher"},
    "REST web app path": {"create web app": "Graph.KG.Service.CreateWebApp", "vector search": "VectorSearch",
                          "walk": "MetaPath"},
    "MCP tool set": {"Cypher tool": "MCPTools.CypherQuery", "SQL tool": "MCPTools.RunSQL", "load tool": "MCPTools.LoadGraph",
                     "vector lookup": "MCPTools.EvidenceSearch"},
}
entry_points_without_cells = ["Bolt BEGIN/COMMIT/PULL/DISCARD/LOGOFF/GOODBYE", "generated GraphQL server (no entity)",
                              "sample API Cypher route and GraphQL executeCypher/mutations", "demo and fraud servers",
                              "admin kill/queries/export routes (folded into 'admin write')"]

disp = {}
for f in F:
    disp[f["disposition"]] = disp.get(f["disposition"], 0) + 1

R = lambda *x: list(x)  # noqa: E731
gates = [
    {"gate": "3.1 statements/cells", "status": "open",
     "reason": "Every cell maps to an entry point (cells_without_entry_point empty), but 9 entry points have no "
               "statement (omissions) and many entry points have no cell (Bolt BEGIN/COMMIT/PULL, generated GraphQL, "
               "demo/fraud). Open questions HD-1601..1605 carry working answers in decisions.md.",
     "evidence": R("experiment/playbook-completion/models/breadth-c/inventory.json#reconciliation.16",
                   "experiment/playbook-uplift/ontology/16-interfaces.md:232-305"),
     "remaining": "Add statements for the omissions; add cells for Bolt explicit transactions/PULL and the generated "
                  "server; index regeneration and grade checks were not rerun here."},
    {"gate": "3.2 IRIS features relied on", "status": "open",
     "reason": "env_features below lists 16 features; P-1607 was falsified live on 2026.1 (refutes F-1612); P-1609 "
               "observed (8-connection cap; Bolt sessions hold connections); P-1601 confirmed by setup skip; "
               "P-1611/P-1606 unchecked (no web app, no TLS proxy).",
     "evidence": R("c16-s5-fraud-sql-stream", "c16-s8-followup", "c16-s2-bolt-sessions", "$RUN_DIR/setup/deploy-AUDITC.json"),
     "remaining": "%CSP.REST dispatch and web-app role checks need a web application (blocked); %AI features need an AI build."},
    {"gate": "3.3 L1/L2/refinement/controls/progress", "status": "open",
     "reason": "Bounded explorer models by the main lane (models/breadth-c): unit atomicity of Bolt BEGIN..ROLLBACK and "
               "HTTP tx/commit (as-built expected violations, reviewed pass, rollback control caught, witness), and "
               "the client+server retry protocol over an ambiguous acknowledgement (as-built 'at most once' and "
               "'honest outcome' violations, reviewed pass, client/server controls caught, read/write witnesses). "
               "No Verus L1/L2/refinement for module 16.",
     "evidence": R("cmc-unit-bolt-as-built-atomic", "cmc-unit-bolt-reviewed", "cmc-unit-http-as-built-atomic",
                   "cmc-unit-http-reviewed", "cmc-retry-as-built-once", "cmc-retry-reviewed", "cmc-unit-ctl-rollback",
                   "cmc-retry-ctl-server"),
     "remaining": "L1/L2/refinement proofs; models of the read-scoping defects"},
    {"gate": "3.3a mechanisms and invariant write-sets", "status": "failed",
     "reason": "Writers of this module that write what SYS-I2/SYS-I4 read violate them live: updateProtein writes every "
               "graph's property (F-1604), /fhir-event and /db/neo4j/tx/commit commit partial units (F-1609, F-1610), "
               "Bolt ROLLBACK keeps writes (F-1601). Writer inventory derived from source (footprints/16.json).",
     "evidence": R("c16-s1-cypher-http", "c16-s3-graphql-sample-api", "footprints/16.json"),
     "remaining": "Record (invariant, plan) pairs for the 16 writers in the write-set generator."},
    {"gate": "3.4 statements/ownership/storage-order/declared-reads", "status": "failed",
     "reason": "declared-reads: generated GraphQL and sample API loaders read rdf_edges/rdf_labels/rdf_props without "
               "graph_id (F-1603, F-1604, reproduced live); ownership: the sample API's updateProtein writes "
               "rdf_props with raw SQL outside the engine (owner module 03); storage-order: one documented sampling "
               "site (gql/engine.py:40), see gates_by_id.",
     "evidence": R("c16-s3-graphql-sample-api", "footprints/16.json"), "remaining": "Statement proofs are not applicable "
     "to Python/HTTP handlers without an IRIS SQL model; ownership/declared-read self-tests not built."},
    {"gate": "3.5 handlers/lock plans/decoders/status maps", "status": "failed",
     "reason": "Status maps verified live: 400 syntax, 401 missing/wrong key, 403 read-only, 503 health, Bolt "
               "Unauthorized/AccessMode codes (c16-s1); but connection failures map to 400 / ClientError.SyntaxError "
               "(F-C1602), the generated /health is always 200 (F-1611), PULL decoding truncates (F-1602), "
               "Bolt transaction messages are no-ops (F-1601). Lock plan: _engine_lock serializes the HTTP server's "
               "one connection (cypher_api.py:146-149); the sample API has none (F-1608 not reproduced).",
     "evidence": R("c16-s1-cypher-http", "c16-s6-status-maps", "c16-s3-graphql-sample-api"),
     "remaining": "Handler proofs not applicable without a model of the routes; status-map table kept in "
                  "modules/16.json status_maps."},
    {"gate": "3.6 composition conditions", "status": "failed",
     "reason": "Composition of client retry (SDK, HD-1702) with server retry (F-C1604) and driver retry over Bolt "
               "(F-1601) is not idempotent; capacity: Bolt sessions leak connections (F-C1601).",
     "evidence": R("c16-s4-server-retry", "c16-s2-bolt-sessions", "cmc-retry-as-built-once", "cmc-unit-bolt-as-built-once"), "remaining": "capacity bound for Bolt sessions; fix-side designs (reviewed models pass)."},
    {"gate": "3.7 validation kinds (crash/reconnect/ambiguous ack, 1 vs N processes)", "status": "open",
     "reason": "Done: ambiguous ack via fault injection (c16-s4), reconnect after error (c16-s1 journal shows the "
               "reset to a new IRIS process), N concurrent threads on one connection (c16-s3), N sequential Bolt "
               "sessions (c16-s2), 2,402 upstream unit tests (c16-unit-suite). Not done: crash of the server process "
               "mid-transaction, N server processes (workers>1), integration/e2e suites for module 16.",
     "evidence": R("c16-s4-server-retry", "c16-s1-cypher-http", "c16-s3-graphql-sample-api", "c16-s2-bolt-sessions",
                   "c16-unit-suite"),
     "remaining": "server crash test; workers>1; tests/e2e API suites under the lock."},
    {"gate": "3.8 account", "status": "open",
     "reason": "All 15 original findings dispositioned (findings/audit/16.json) plus 4 new; product obligations stay "
               "failed where defects were reproduced.", "evidence": R("findings/audit/16.json"),
     "remaining": "independent review sign-off; maintainer decisions HD-1601..1605."},
]

gates_by_id = {
    "3.1-cells": {"status": "open", "evidence": ["ontology/16-interfaces.md:232-305", "modules/16.json#cells_map"],
                  "remaining": "cells exist for 5 entities and map to entry points; add cells for Bolt explicit "
                               "transactions/PULL, generated GraphQL and demo/fraud servers"},
    "3.1-coverage": {"status": "open", "evidence": ["models/breadth-c/inventory.json#reconciliation.16",
                                                    "modules/16.json#entry_points.omissions"],
                     "remaining": "9 omissions (incl. 4 writers / deployment entries) need statements"},
    "3.1-intent": {"status": "open", "evidence": ["experiment/playbook-completion/decisions.md HD-1601..1605"],
                   "remaining": "working answers recorded; maintainer decision pending (HD-1603 retry, HD-1705 bind)"},
    "3.2-coverage": {"status": "open", "evidence": ["modules/16.json#env_features", "c16-s5-fraud-sql-stream",
                                                    "c16-s8-followup", "c16-s2-bolt-sessions"],
                     "remaining": "CSP dispatch and %AI features cannot be exercised here (blocked-access)"},
    "3.3-L1": {"status": "open", "evidence": [], "remaining": "explorer models only (models/breadth-c); no Verus L1/L2/refinement for module 16"},
    "3.3-L2": {"status": "open", "evidence": [], "remaining": "explorer models only (models/breadth-c); no Verus L1/L2/refinement for module 16"},
    "3.3-refinement": {"status": "open", "evidence": [], "remaining": "explorer models only (models/breadth-c); no Verus L1/L2/refinement for module 16"},
    "3.3-controls": {"status": "open", "evidence": [], "remaining": "explorer models only (models/breadth-c); no Verus L1/L2/refinement for module 16"},
    "3.3-model-check": {"status": "closed",
                        "evidence": ["cmc-unit-bolt-as-built-atomic", "cmc-unit-bolt-as-built-once",
                                     "cmc-unit-bolt-reviewed", "cmc-unit-ctl-rollback", "cmc-unit-wit-bolt",
                                     "cmc-unit-http-as-built-atomic", "cmc-unit-http-reviewed",
                                     "cmc-retry-as-built-once", "cmc-retry-as-built-honest", "cmc-retry-reviewed",
                                     "cmc-retry-ctl-client", "cmc-retry-ctl-server", "cmc-retry-wit-read",
                                     "cmc-retry-wit-write"],
                        "remaining": "bounded explorer models (exhaustive within bounds) of Bolt/HTTP unit atomicity "
                                     "and the client+server retry protocol: as-built violate (F-1601, F-1610, "
                                     "F-C1604), reviewed designs pass, controls caught, witnesses reachable; the "
                                     "generated GraphQL/sample API read scoping (F-1603/F-1604) is not modelled"},
    "3.3a-writesets": {"status": "failed", "evidence": ["footprints/16.json", "c16-s3-graphql-sample-api",
                                                       "c16-s1-cypher-http"],
                       "remaining": "writer inventory derived from source (footprints/16.json, 14 writer entries); "
                                    "SYS-I2/SYS-I4 pairs violated by F-1604, F-1609, F-1610, F-1601"},
    "3.4-statements": {"status": "not-applicable", "evidence": ["iris_vector_graph/cypher_api.py", "api/"],
                       "remaining": "module 16 owns no storage statements of its own except the sample API's raw SQL "
                                    "(api/gql/loaders.py, examples/domains/biomedical/resolver.py:262-275) and the "
                                    "fraud server's lookup; those are recorded as findings (F-1604, F-1615) instead of "
                                    "proved; the Cypher entries delegate to modules 08/09"},
    "3.4-ownership": {"status": "failed", "evidence": ["examples/domains/biomedical/resolver.py:262-275",
                                                      "c16-s3-graphql-sample-api"],
                      "remaining": "updateProtein writes Graph_KG.rdf_props directly (owner: module 03 write path); "
                                   "no ownership self-test built"},
    "3.4-storage-order": {"status": "open", "evidence": ["$RUN_DIR/checks/storage-order.json"],
                          "sites": [
                              {"site": "iris_vector_graph/gql/engine.py:40",
                               "sql": "SELECT DISTINCT p.key ... AND p.s IN (SELECT TOP {sample_limit} s FROM rdf_labels WHERE label = ?)",
                               "disposition": "intent-undecided",
                               "reason": "documented sampling (gql/engine.py:38-39 'Using TOP clause for sampling as per "
                                         "SC-002/SC-003 and FR-002'): not a unique key and not existence-only; for a "
                                         "label with more than sample_limit (1000) nodes the generated type's fields "
                                         "depend on which rows storage order returns, so the schema can differ between "
                                         "starts. No source settles whether a storage-order-dependent schema is "
                                         "acceptable. The same subquery joins rdf_props on s alone (graph mixing, F-1603)."},
                              {"site": "iris_src/src/Graph/KG/MCPTools.cls:33", "disposition": "false-positive",
                               "reason": "a /// doc-comment example of RunSQL input (MCPTools.cls:31-33), not executed SQL"}],
                          "remaining": "decide whether sampled schema discovery may depend on storage order; no self-test"},
    "3.4-declared-reads": {"status": "failed", "evidence": ["c16-s3-graphql-sample-api",
                                                           "iris_vector_graph/gql/resolvers.py:32-133",
                                                           "api/gql/loaders.py:19-272"],
                           "remaining": "graph_id predicates missing (F-1603, F-1604); no self-test"},
    "3.5-handlers": {"status": "failed", "evidence": ["c16-s1-cypher-http", "c16-s3-graphql-sample-api",
                                                     "c16-s4-server-retry"],
                     "remaining": "handlers violate their stated steps (F-1601, F-1606, F-1607, F-1609, F-1610, F-C1604)"},
    "3.5-lockplans": {"status": "open", "evidence": ["iris_vector_graph/cypher_api.py:146-149, 232-236",
                                                    "c16-s3-graphql-sample-api"],
                      "remaining": "only an in-process RLock (HTTP server) and no lock (sample API, Bolt sessions); "
                                   "no IRIS LOCK in module 16 handlers; concurrency premise P-1605 not proved"},
    "3.5-decoders": {"status": "failed", "evidence": ["c16-s6-status-maps", "c16-s1-cypher-http",
                                                     "c16-s3-graphql-sample-api"],
                     "remaining": "F-1602 (PULL), F-1611 (health), F-C1602 (error classification)"},
    "3.6-frame": {"status": "not-applicable", "evidence": [],
                  "remaining": "module 16 has no statement-shape classes of its own (delegates to engine modules)"},
    "3.6-row-permutation": {"status": "open", "evidence": ["iris_vector_graph/gql/resolvers.py:32-46"],
                            "remaining": "nodes(label) paging slices an unordered id list (offset/limit without ORDER "
                                         "BY): page content depends on row order"},
    "3.6-keys": {"status": "not-applicable", "evidence": [], "remaining": "no keys owned by module 16"},
    "3.6-fk": {"status": "not-applicable", "evidence": [], "remaining": "no foreign keys owned by module 16"},
    "3.6-capacity": {"status": "failed", "evidence": ["c16-s2-bolt-sessions"],
                     "remaining": "Bolt sessions hold IRIS connections until the server exits (F-C1601); "
                                  "limitRows/hop caps exist (cypher_api.py:254-256, api/routers/cypher.py:31-80)"},
    "3.7-trace-replay": {"status": "open", "evidence": ["footprints/16.json (journal traces)"],
                         "remaining": "journal traces captured; replay through the main lane's machines pending"},
    "3.7-lock-log": {"status": "not-applicable", "evidence": [],
                     "remaining": "module 16 handlers take no IRIS locks (cypher_api.py, bolt_server.py, api/)"},
    "3.7-mutation": {"status": "open", "evidence": ["c16-unit-suite"],
                     "remaining": "no mutation testing of the HTTP/Bolt layers"},
    "3.8-findings-disposed": {"status": "closed", "evidence": ["findings/audit/16.json"],
                              "remaining": "all 15 original + 4 new findings recorded with evidence and disposition; "
                                           "product obligations stay failed where reproduced"},
    "5c-refusals": {"status": "open", "evidence": ["c16-s1-cypher-http"],
                    "remaining": "audited live: X1.5 (missing key 401), X3.2 (read-only admin 403, explain 200), "
                                 "X8.6.2 (read-only Cypher 403), X9.3/X9.4 (Bolt Unauthorized, AccessMode); other X "
                                 "statements (X7.3, X11.4, X13.6) inspected only"},
}

status_maps = {
    "cypher_api (Cypher HTTP server)": [
        {"when": "missing/wrong key", "answer": "401 {error: unauthorized}", "source": "iris_vector_graph/api_auth.py:105-123", "live": "c16-s1 B.*"},
        {"when": "read-only write (Cypher)", "answer": "403 (read_only_refusal)", "source": "cypher_api.py:353-354, 381-385, 438-439", "live": "c16-s1 C.*"},
        {"when": "read-only write (admin path)", "answer": "403 read_only_mode", "source": "api_auth.py:150-175", "live": "c16-s1 C.admin_load_readonly"},
        {"when": "any exception in /api/cypher, query/v2 (parse, translation, execution, connection)", "answer": "400 {status:error, error:str(e)}", "source": "cypher_api.py:367-376, 451-460", "live": "c16-s1 A.api_cypher_syntax_error; c16-s6 (connection -> 400)"},
        {"when": "any statement error in tx/commit", "answer": "400 + Neo.ClientError.Statement.SyntaxError per error, partial results", "source": "cypher_api.py:391-405", "live": "c16-s1, c16-s6"},
        {"when": "/health probe fails", "answer": "503 {status: unavailable}", "source": "cypher_api.py:268-284", "live": "c16-s6"},
        {"when": "/schema,/indexes,/server,/metrics,/stats or admin error", "answer": "500 detail=str(e)", "source": "cypher_api.py:481-610", "live": "c16-s6 (/schema)"},
        {"when": "schema init EmbeddingIdentityConflict", "answer": "409", "source": "cypher_api.py:589-591", "live": None},
        {"when": "kill failure / explain failure", "answer": "400", "source": "cypher_api.py:711, 740", "live": None}],
    "bolt_server": [
        {"when": "unauthenticated non-auth message / wrong key", "answer": "FAILURE Neo.ClientError.Security.Unauthorized; state FAILED", "source": "bolt_server.py:477-479, 524-560", "live": "c16-s1 B.bolt_wrong_key"},
        {"when": "read-only write RUN", "answer": "FAILURE Neo.ClientError.Statement.AccessMode", "source": "bolt_server.py:570-578", "live": "c16-s1 C.bolt_write_readonly"},
        {"when": "any RUN exception (parse, engine, connection, licence)", "answer": "FAILURE Neo.ClientError.Statement.SyntaxError", "source": "bolt_server.py:614-622", "live": "c16-s1 A.bolt_syntax_error_failure_code; c16-s6 map.bolt.*"},
        {"when": "message in FAILED state", "answer": "IGNORED (RESET -> SUCCESS)", "source": "bolt_server.py:466-473", "live": None},
        {"when": "BEGIN / COMMIT / ROLLBACK", "answer": "SUCCESS, no transaction effect", "source": "bolt_server.py:500-510", "live": "c16-s1 A.F1601_*"},
        {"when": "PULL {n}", "answer": "rows[:n] then SUCCESS without has_more; rest dropped", "source": "bolt_server.py:624-660", "live": "c16-s1 A.F1602_pull_n"}],
    "generated GraphQL (iris_vector_graph.gql)": [
        {"when": "exception text 'Access Denied'", "answer": "403", "source": "gql/__init__.py:36-45", "live": None},
        {"when": "'License Limit' / 'Too many connections'", "answer": "503", "source": "gql/__init__.py:36-45", "live": None},
        {"when": "other unhandled", "answer": "500", "source": "gql/__init__.py:36-45", "live": None},
        {"when": "resolver error", "answer": "200 with GraphQL errors[] (semantic_search: [] and a log line)", "source": "gql/resolvers.py:85-88", "live": None},
        {"when": "/health", "answer": "always 200 healthy", "source": "gql/__init__.py:58-67", "live": "c16-s3 GQL.F1611_*"}],
    "sample API (api.main)": [
        {"when": "read-only write", "answer": "403", "source": "api/routers/cypher.py:104-116", "live": None},
        {"when": "CypherParseError", "answer": "400 syntax", "source": "api/routers/cypher.py:216-229", "live": "c16-s3 API.status_syntax"},
        {"when": "ValueError/SyntaxError (translation; unknown function too)", "answer": "400 UNDEFINED_VARIABLE (413 complexity)", "source": "api/routers/cypher.py:231-247", "live": "c16-s3 API.status_undefined_variable, API.status_execution"},
        {"when": "SQL execution error", "answer": "500 'query execution failed'", "source": "api/routers/cypher.py:201-213", "live": "c16-s3 API.F1607_unwind_parity"},
        {"when": "/health database problem", "answer": "503 with fixed reason", "source": "api/main.py:100-113", "live": None},
        {"when": "/fhir-event write failure", "answer": "500 'IRIS write failed: ...' after partial writes", "source": "api/routers/fhir_event.py:318-346", "live": "c16-s3 API.F1609_*"},
        {"when": "GraphQL executeCypher error", "answer": "200 data {error: str}", "source": "api/gql/schema.py:224-226", "live": "c16-s3 API.F1607_unwind_parity"}],
    "REST dispatcher (Graph.KG.Service)": [
        {"when": "any error, incl. unparsable body", "answer": "500 {error: text}", "source": "iris_src/src/Graph/KG/Service.cls:337-345", "live": "blocked-access (no web application)"}],
}

env_features = [
    {"feature": "DB-API connection over the SuperServer (one IRIS process per connection)", "source": "iris_vector_graph/cypher_api.py:156-172; api/main.py:21-37", "used_by": "every server", "checked": "live (all runs)"},
    {"feature": "instance connection/licence cap (Community: 8 connections in total)", "source": "iris_vector_graph/bolt_server.py:391-394 (one connection per Bolt session); P-1609", "used_by": "Bolt sessions, GraphQL pool comment gql/pooling.py:7-11", "checked": "live (c16-s2; infrastructure licence refusals during the first run)"},
    {"feature": "engine write transactions (TSTART/TCOMMIT via the engine) per Cypher call", "source": "iris_vector_graph/_engine/query.py:1946-1967 (module 08), used by cypher_api.py:239-260, bolt_server.py:580", "used_by": "Cypher HTTP, Bolt, generated GraphQL cypher", "checked": "journal (c16-s1)"},
    {"feature": "SQL START TRANSACTION / COMMIT / ROLLBACK on a DB-API cursor", "source": "api/routers/cypher.py:139-158; api/gql/schema.py:182-201", "used_by": "sample API Cypher route and executeCypher", "checked": "journal (c16-s7: one outermost commit for a CREATE a->b)"},
    {"feature": "closing a connection rolls back its open transaction (P-0001/SYS-P1)", "source": "iris_vector_graph/cypher_api.py:209-217 (_reset_engine in the retry path)", "used_by": "server retry", "checked": "inspected"},
    {"feature": "$INCREMENT / ID counters are non-transactional (journaled outside the transaction bracket)", "source": "observed in every journal capture", "used_by": "row ids of nodes/rdf_* tables", "checked": "journal"},
    {"feature": "%SYSTEM.SYS.KillProcess callable from SQL", "source": "iris_vector_graph/cypher_api.py:707", "used_by": "DELETE /admin/queries/{id}", "checked": "inspected"},
    {"feature": "%SYS.ProcessQuery readable from SQL", "source": "iris_vector_graph/_engine/admin.py active_queries_sql via cypher_api.py:686-694", "used_by": "GET /admin/queries", "checked": "live (used by c16-s2)"},
    {"feature": "%SYSTEM.Version.GetVersion via the Native API", "source": "iris_vector_graph/cypher_api.py:752-763", "used_by": "GET /server", "checked": "inspected"},
    {"feature": "%CSP.REST dispatch (UrlMap) and %request.Content stream Read()", "source": "iris_src/src/Graph/KG/Service.cls:4-10, 321-327", "used_by": "REST dispatcher", "checked": "Read() default length live (c16-s5, c16-s8); dispatch blocked (no web application)"},
    {"feature": "Security.Applications / roles (MatchRoles, AutheEnabled=32) and SQL GRANT in %SYS", "source": "iris_src/src/Graph/KG/Service.cls:30-75, 104-260", "used_by": "Graph.KG.Service.CreateWebApp", "checked": "read-only listing (webapps.txt); P-1611 unchecked"},
    {"feature": "%AI.MCP.Service, %AI.ToolSet, %AI.Tool, %AI.Policy.ConsoleAudit", "source": "iris_src/src/Graph/KG/MCPService.cls:3; MCPToolSet.cls:5; MCPTools.cls:3", "used_by": "MCP tool set", "checked": "absent on Community 2026.1 (setup skip, deploy-AUDITC.json)"},
    {"feature": "embedded Python in IRIS ([Language = python], iris.sql.prepare/exec)", "source": "iris_src/src/Graph/KG/MCPTools.cls:9, 74, 193; src/iris_fraud_server/app.py:205-270", "used_by": "MCP tools, fraud server", "checked": "not run (MCP blocked; fraud server needs embedded mode)"},
    {"feature": "VECTOR columns and VECTOR_DOT_PRODUCT", "source": "iris_src/src/Graph/KG/MCPTools.cls:210-212; src/iris_fraud_server/app.py:256-262", "used_by": "MCP vector lookup, fraud score", "checked": "live prepare of the intended statement (c16-s5)"},
    {"feature": "IVG Schema record ^IVG.Deploy(\"schema\") read through the Native API", "source": "api/main.py:40-66 (read_record)", "used_by": "sample API /health", "checked": "live (sample API health 200, c16-s3)"},
    {"feature": "IRIS WSGI hosting of a2wsgi apps (cypher_api.wsgi_app) and embedded `iris` module", "source": "iris_vector_graph/cypher_api.py:22-28, 781-785", "used_by": "running the Cypher HTTP server inside IRIS", "checked": "not run"},
]

module = {
    "module": "16", "name": "API", "pin": PIN,
    "entry_points": {
        "total": rec16["entry_points"], "by_kind": rec16["by_kind"], "lexically_covered": rec16["lexically_covered"],
        "lexically_uncovered": len(rec16["uncovered"]), "uncovered_classification": uncovered_classes,
        "omissions": omissions, "cells_without_entry_point": [], "cells_map": cells_map,
        "entry_points_without_cells": entry_points_without_cells,
        "servers": {
            "Cypher HTTP server (cypher_api)": "GET /, /browser, /health, /db/neo4j, /db/neo4j/tx, /schema, /indexes, "
                "/server, /metrics, /stats, /admin/export, /admin/queries; POST /api/cypher, /db/neo4j/tx/commit, "
                "/db/{db}/query/v2, /admin/schema/init, /admin/indexes/rebuild, /admin/embed, /admin/load, "
                "/admin/snapshot (module 18), /admin/explain; DELETE /admin/queries/{id}; WebSocket / (Bolt); "
                "static mount /browser",
            "Bolt (TCP + WebSocket)": "HELLO, LOGON, LOGOFF, RUN, PULL, BEGIN, COMMIT, ROLLBACK, DISCARD, RESET, GOODBYE",
            "generated GraphQL (gql.create_app)": "GET /, /health; /graphql: stats, node, nodes, semanticSearch, cypher; "
                "Node.properties/outgoing/incoming; Relationship.node; one type per label",
            "sample API (api.main)": "GET /, /health; POST /api/cypher, /fhir-event/; /graphql: node, nodes, stats, "
                "protein, gene, pathway, executeCypher; mutations createProtein, updateProtein, deleteProtein",
            "REST dispatcher (Graph.KG.Service)": "POST /vectorSearch, /hybridSearch, /metaPath; CreateWebApp",
            "MCP (Graph.KG.MCPTools, AI builds)": "CypherQuery, RunSQL, LoadGraph, GraphStats, PPRWalk, EvidenceSearch",
            "demo server": "GET /, /fraud, /bio, /fhir, /arch/*, /api/status/{key}, /api/fraud/scenario/{n}, "
                "/api/bio/scenario/{n}, /api/bio/network/{id}, /api/fhir/stats, /api/fhir/scenario/{n}, "
                "/api/fhir/neighborhood/{key}; POST /api/fraud/score, /api/bio/search, /api/bio/pathway, "
                "/api/fhir/search, /api/fhir/live/add, /api/fhir/live/sync",
            "fraud server": "GET /, /fraud/health; POST /fraud/score",
        },
        "notes": "Inventory from models/breadth-c/tools/inventory.py (354 entry points owned by module 16; 241 "
                 "lexically uncovered, reviewed: most are covered under a route path or group statement or are "
                 "internal helpers; 9 genuine omissions listed). The sample API is repository-only (not in the wheel "
                 "or sdist) and imports iris_devtester, a dev extra (api/main.py:12; pyproject.toml:119).",
    },
    "gates": gates, "gates_by_id": gates_by_id, "status_maps": status_maps, "env_features": env_features,
    "findings_summary": {"original": 15, "new": len(F) - 15, "by_disposition": disp,
                         "reproduced_live": [f["id"] for f in F if f["disposition"] == "reproduced-live"]},
    "blockers": [
        "REST dispatcher end-to-end: no web application dispatches to Graph.KG.Service; creating one changes "
        "Security.Applications (forbidden for lanes)",
        "MCP classes: %AI.MCP.Service, %AI.ToolSet, %AI.Tool, %AI.Policy.ConsoleAudit absent on IRIS Community 2026.1",
        "F-1605 live: needs a namespace installed under a non-default IVG Schema (lanes may not create namespaces)",
        "demo FHIR write routes: need an IRIS for Health FHIR repository",
        "shared 8-connection cap: live runs serialized behind tools/locks.sh iris",
    ],
    "runs": ["c16-unit-suite", "c16-s1-cypher-http", "c16-s2-bolt-sessions", "c16-s3-graphql-sample-api",
             "c16-s4-server-retry", "c16-s5-fraud-sql-stream", "c16-s6-status-maps", "c16-s7-more-writers",
             "c16-s8-followup"],
}

for path, obj in ((COMP / "findings/audit/16.json", findings), (COMP / "footprints/16.json", footprints),
                  (COMP / "modules/16.json", module)):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=False, default=str) + "\n")
    print("wrote", path.relative_to(COMP))
print(json.dumps(module["findings_summary"], indent=1))
print("validated", footprints["validated"], "mismatches", len(footprints["mismatches"]))
