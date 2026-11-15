"""Curated per-statement table for module 16 (API X statements), used by make_audit_1516.py 16."""

T16 = {
    "API-X1.5": dict(outcome="holds-live",
                     code=["iris_vector_graph/api_auth.py:104-124", "iris_vector_graph/cypher_api.py:105-109"],
                     notes="Cypher HTTP server (uvicorn subprocess, IVG_API_KEY set): POST /api/cypher CREATE with no "
                           "key, a wrong key, an empty key, a wrong bearer; /db/neo4j/tx/commit CREATE and /admin/load "
                           "with no key: each 401 {'error':'unauthorized','message':'X-Api-Key header required'}; the "
                           "node was not created and the journal shows no write (the route did not run); 6 cases."),
    "API-X1.6": dict(outcome="holds-live", code=["iris_vector_graph/api_auth.py:111-118", "api/main.py:124"],
                     notes="Sample API (in process) with IVG_API_KEY: the /graphql web socket with no key and with a "
                           "wrong key is closed with 1008 before accept (TestClient WebSocketDisconnect 1008); control: "
                           "with the key it is accepted; 2 cases. The Cypher HTTP server's '/' web socket is exempt by "
                           "design (Bolt authenticates in the protocol, API-X9.3)."),
    "API-X3.2": dict(outcome="holds-live",
                     code=["iris_vector_graph/cypher_api.py:98-99", "iris_vector_graph/api_auth.py:174-175"],
                     notes="Cypher HTTP server with IVG_API_KEY + IVG_READ_ONLY: POST /admin/load, /admin/schema/init, "
                           "/admin/indexes/rebuild, /admin/embed, /admin/snapshot and DELETE /admin/queries/{id}: 403 "
                           "read_only_mode, no journal write; control: POST /admin/explain answers 200 with SQL; 6 "
                           "cases."),
    "API-X3.3": dict(outcome="holds-live", code=["iris_vector_graph/api_auth.py:167-172", "api/main.py:120"],
                     notes="Sample API with IVG_READ_ONLY: POST /fhir-event/ (a valid event) -> 403 read_only_mode, "
                           "nothing written; control: with IVG_ALLOW_FHIR_WRITES=true the request passes the "
                           "middleware (it is then refused by the payload model, 422, by design of the control); 1 "
                           "case."),
    "API-X5.1": dict(outcome="holds-live",
                     code=["api/routers/cypher.py:31-81", "api/routers/cypher.py:119",
                           "api/routers/cypher.py:235-237"],
                     notes="Sample API POST /api/cypher: *1..11 (default cap), unbounded * (parsed as 100 hops), "
                           "*1..11 with IVG_CYPHER_MAX_HOPS='abc' (falls back to 10) and *1..6 with the cap at 5: 413 "
                           "COMPLEXITY_LIMIT_EXCEEDED; control: cap 20 accepts *1..11; 4 cases."),
    "API-X5.2": dict(outcome="holds-live", code=["api/routers/cypher.py:103-114"],
                     notes="Sample API with IVG_READ_ONLY: POST /api/cypher CREATE -> 403 errorType 'access' "
                           "(errorCode INTERNAL_ERROR, as the statement's note says); nothing written; 1 case."),
    "API-X6.1": dict(outcome="holds-live",
                     code=["api/gql/schema.py:290-310", "api/gql/schema.py:326"],
                     notes="Sample API POST /graphql, a 13-level query: GraphQL error naming the depth limit (control: "
                           "4 levels pass); a fresh process with IVG_GRAPHQL_MAX_DEPTH=3 refuses a 4-level query during "
                           "validation (no resolver, no IRIS); control: 'ten' falls back to 10 and accepts 4 levels; 2 "
                           "cases."),
    "API-X6.8": dict(outcome="holds-live",
                     code=["api/gql/schema.py:160-163", "api/gql/schema.py:231-238", "api/gql/schema.py:258",
                           "api/gql/schema.py:269", "api/gql/schema.py:280"],
                     notes="Sample API with IVG_READ_ONLY: createProtein, updateProtein, deleteProtein -> GraphQL error "
                           "(PermissionError, read-only mode); executeCypher CREATE -> {'error': 'mutation queries not "
                           "allowed in read-only mode'}; nothing written or removed; 4 cases."),
    "API-X6.91": dict(outcome="holds-live",
                      code=["examples/domains/biomedical/resolver.py:204-211"],
                      notes="createProtein of an id the default graph holds -> error 'already exists' (its properties "
                            "unchanged); createProtein with a 3-wide vector -> error '768-dimensional', no node made; 2 "
                            "cases."),
    "API-X6.93": dict(outcome="holds-live",
                      code=["examples/domains/biomedical/resolver.py:309-310",
                            "iris_vector_graph/_engine/nodes_edges.py:2202-2225"],
                      notes="deleteProtein of an id only a named graph holds -> 'not found'; of an id the default graph "
                            "and a named graph hold -> ValueError 'held by more than one graph, so nothing was "
                            "deleted'; both rows remain; 2 cases."),
    "API-X7.3": dict(outcome="holds-live",
                     code=["api/routers/fhir_event.py:182-187", "iris_vector_graph/_validate.py:31-49"],
                     notes="Sample API POST /fhir-event/ with graph containing a control character, 257 characters, "
                           "and '0': 422, nothing written; 3 cases."),
    "API-X7.9": dict(outcome="holds-live", code=["api/routers/fhir_event.py:300-305"],
                     notes="An app made with no engine (IRIS address a closed port): POST /fhir-event/ -> 503, nothing "
                           "written; 1 case."),
    "API-X8.5.6": dict(outcome="holds-live", code=["iris_vector_graph/cypher_api.py:288-308"],
                       notes="Cypher HTTP server, IVG_FHIR_ALLOWED_BASES = <listener>/fhir: an unlisted host, the "
                             "listed base plus a path, and the listed base as a string prefix: 400 naming "
                             "IVG_FHIR_ALLOWED_BASES, the listener saw 0 connections; control: the listed base with a "
                             "trailing slash is fetched; 3 cases."),
    "API-X8.6.2": dict(outcome="holds-live", code=["iris_vector_graph/cypher_api.py:230-237",
                                                   "iris_vector_graph/cypher_api.py:381-385"],
                       notes="Read-only server: /db/neo4j/tx/commit with read, CREATE, read -> 403, results [], "
                             "Neo.ClientError.Statement.AccessMode; the write did not happen; 1 case."),
    "API-X8.10.9": dict(outcome="holds-live",
                        code=["iris_vector_graph/cypher_api.py:578-592",
                              "iris_vector_graph/_engine/schema.py:1564-1598",
                              "iris_vector_graph/_engine/schema.py:1634"],
                        notes="Cypher HTTP app (in process): POST /admin/schema/init with embedding_dimension 7 while "
                              "the empty vector columns are declared at another width -> 409 (EmbeddingIdentityConflict), "
                              "no journal write; 1 case."),
    "API-X9.3": dict(outcome="holds-live",
                     code=["iris_vector_graph/bolt_server.py:50-51", "iris_vector_graph/bolt_server.py:474-479",
                           "iris_vector_graph/bolt_server.py:530-565"],
                     notes="Raw Bolt to the server's TCP listener (IVG_API_KEY set): 4.4 RUN CREATE before HELLO; 5.4 "
                           "HELLO without credentials then RUN CREATE; 4.4 refused HELLO, RESET, RUN CREATE: each "
                           "FAILURE Neo.ClientError.Security.Unauthorized, no write; control: 5.4 HELLO + LOGON with "
                           "the key runs a read; 3 cases."),
    "API-X9.4": dict(outcome="holds-live",
                     code=["iris_vector_graph/bolt_server.py:530-545", "iris_vector_graph/bolt_server.py:487-489",
                           "iris_vector_graph/bolt_server.py:662-667"],
                     notes="5.4 good LOGON, wrong LOGON, RESET, RUN CREATE; 5.4 good LOGON, LOGOFF, RUN CREATE; 4.4 "
                           "good HELLO, wrong HELLO, RESET, RUN CREATE: each FAILURE Unauthorized, no write; 3 cases."),
    "API-X9.7": dict(outcome="holds-live", code=["iris_vector_graph/bolt_server.py:567-578"],
                     notes="Read-only server, Bolt 4.4 HELLO with the key, RUN CREATE -> FAILURE "
                           "Neo.ClientError.Statement.AccessMode, no write; the next RUN is IGNORED (session FAILED); 1 "
                           "case."),
    "API-X10.2": dict(outcome="holds-live", code=["iris_vector_graph/gql/resolvers.py:136-147"],
                      notes="Generated GraphQL app (in process) with IVG_READ_ONLY: cypher(query: CREATE ...) -> "
                            "GraphQL error (PermissionError), no write; 1 case."),
    "API-X11.4": dict(outcome="holds-run",
                      code=["iris_src/src/Graph/KG/Service.cls:39-41", "iris_src/src/Graph/KG/Service.cls:76-93"],
                      evidence=["run:val-gated-rag-1"],
                      log_contains={"run:val-gated-rag-1":
                                    "tests/e2e/test_460_kg_webapp_reset_e2e.py::test_an_application_that_is_not_ivgs_is_"
                                    "refused_and_left_as_it_was PASSED"},
                      notes="Not probed live here: triggering it means calling CreateWebApp at a path that holds "
                            "another application, i.e. a %SYS web application of the shared container, which a "
                            "defect would reconfigure. The pinned upstream e2e test makes its own foreign application "
                            "(scratch fixture), calls CreateWebApp on it and asserts the answer names the application "
                            "and its properties are unchanged; it PASSED in val-gated-rag-1 (that run's overall "
                            "result is fail because of other tests)."),
    "API-X13.6": dict(outcome="holds-live", code=["src/iris_fraud_server/app.py:65-70"],
                      notes="Fraud server app (in process; torch and structlog are not installed here and were "
                            "replaced by inert stand-ins for the import only; the request model does not use them): "
                            "payer, device, ip and merchant without a colon -> 422 naming 'namespace:id'; 4 cases."),
    "API-X13.106": dict(outcome="holds-live",
                        code=["src/iris_fraud_server/app.py:51-56", "src/iris_fraud_server/app.py:476-481"],
                        notes="Fraud server app (stand-ins as for API-X13.6): mode EGO -> 501 'EGO mode not implemented "
                              "in MVP'; mode XYZ -> 422 from the request model; 2 cases."),
    "API-X14.1": dict(outcome="holds-live",
                      code=["iris_vector_graph/security.py:101-139", "iris_vector_graph/vector_utils.py:47-50"],
                      notes="VectorOptimizer.get_vector_statistics with 'secrets', 'Graph_KG.nodes; DROP TABLE x', "
                            "'kg_emb_zz' and 'Other.users': ValueError 'not in the allowlist' before any SQL; 4 cases."),
    "API-X14.4": dict(outcome="holds-live",
                      code=["iris_vector_graph/security.py:159-182", "iris_vector_graph/_engine/embeddings.py:996"],
                      notes="engine.store_embedding with an element holding a quote and with a word element: ValueError "
                            "'is not a number'; no vector row; 2 cases."),
    "API-X14.5": dict(outcome="holds-live",
                      code=["iris_vector_graph/security.py:142-151", "iris_vector_graph/engine.py:338",
                            "iris_vector_graph/_engine/embeddings.py:965"],
                      notes="IRISGraphEngine(vector_dtype=\"DOUBLE), 'x') --\" / 'FLOAT32' / 'DOUBLE X') and "
                            "store_embedding(dtype='FLOAT32'): ValueError 'is not a vector element type'; 4 cases."),
}
