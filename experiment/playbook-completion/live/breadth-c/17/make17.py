#!/usr/bin/env python3
"""Compose module 17's footprints, findings audit and gate status from live results, offline checks and models.

    python experiment/playbook-completion/live/breadth-c/17/make17.py

Inputs: $RUN_DIR/breadth-c/17/<check>.json (ops_live.py), offline.json (ops_offline.py), models RESULTS.json.
Outputs: footprints/17.json, findings/audit/17.json, modules/17.json. Live values are inserted, not typed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMP = HERE.parents[2]
RUN = Path(os.environ["RUN_DIR"]) / "breadth-c" / "17"
PIN = "3eaa79cf77d3e0a879b2cced634cf2729d81499e"


def res(name):
    p = RUN / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else {}


def g(r, *path, default=None):
    for k in path:
        if not isinstance(r, dict) or k not in r:
            return default
        r = r[k]
    return r


L1701, L1705, L1707, L1712, L1713, L1703, FP, SRV = (res(n) for n in ("F-1701", "F-1705", "F-1707", "F-1712", "F-1713",
                                                                      "F-1703", "footprints", "server"))
OFF = res("offline")
MODELS = {c["id"]: c for c in json.loads((COMP / "models/breadth-c/RESULTS.json").read_text())["checks"]}


def rec(id_, title, intended, observed, disposition, evidence, gates, severity, confidence, remedy, notes=""):
    return {"id": id_, "module": "17", "title": title, "intended": intended, "observed": observed,
            "disposition": disposition, "evidence": evidence, "gates": gates, "severity": severity,
            "confidence": confidence, "remedy": remedy, "notes": notes}


def findings():
    out = []
    leak = g(L1701, "leak_observed")
    merged = g(L1701, "store_get_nodes_no_graph")
    out.append(rec(
        "F-1701", "The SQL adapter's unscoped node and label reads merge graphs",
        "A node's labels and properties are its own graph's (CONTEXT.md 'All-graphs read', decided 2026-10-20); the engine's "
        "get_nodes is graph-scoped since spec 227 (iris_vector_graph/_engine/nodes_edges.py:621-636); SYS-I2.",
        f"Live (c17-live-engine, AUDITC): node c17:x labelled C17A in c17g1 and unlabelled in c17g2. "
        f"IRISGraphStore.get_nodes(['c17:x']) with no graph answered {merged}; get_node_labels answered "
        f"{g(L1701, 'store_get_node_labels')}. Cypher under USE GRAPH 'c17g2': start-label variable-length "
        f"{g(L1701, 'start_label')}, target-label {g(L1701, 'target_label')}, fixed-length {g(L1701, 'fixed_start_label')}, "
        f"plain label match {g(L1701, 'labels_in_g2')}. Source: iris_vector_graph/stores/iris_sql_store.py:1116-1210 (no graph "
        "predicate when graph is None; query_nodes has no graph parameter); callers _engine/query.py:245, :266, :3319.",
        "reproduced-live" if (leak or merged) else "not-reproduced",
        [{"kind": "live", "ref": "c17-live-engine"}, {"kind": "inspected", "ref": "iris_vector_graph/stores/iris_sql_store.py:1116-1210"},
         {"kind": "inspected", "ref": "iris_vector_graph/_engine/query.py:245-275"}],
        ["3.4-declared-reads", "SYS-I2"], "S1", "high" if leak else "medium",
        "Give get_nodes/get_node_labels/query_nodes a graph argument and pass the query's graph from every Cypher caller; a "
        "live test with one id in two graphs.",
        "" if leak else "Reproduced at the adapter's public reads (IRISGraphStore is exported; an unscoped get_nodes for an id "
        "the default graph does not hold answers another graph's labels). The Cypher impact the original claims was NOT "
        "observed for the four shapes run under USE GRAPH: each answered [] with graph-scoped SQL (the generated SQL joins "
        "rdf_labels with graph_id = 'c17g2', recorded in the live result), so the query.py:245/266/3319 store calls were not "
        "reached by these shapes at the pin."))
    out.append(rec(
        "F-1702", "A caller transaction cannot be opened through an in-IRIS cursor",
        "docs/USER_GUIDE.md 'Writes inside your transaction': after SQL START TRANSACTION the caller's ROLLBACK removes IVG's "
        "write; no exception for EmbeddedConnection.",
        "EmbeddedCursor.execute returns before sending START TRANSACTION, BEGIN, BEGIN TRANSACTION, COMMIT, ROLLBACK "
        "(iris_vector_graph/embedded.py:312-321). Checked through the cursor itself with a recording stand-in for iris.sql "
        "(c17-offline: none of the four statements reached it) and the upstream unit test test_transaction_statements_are_noop "
        "(c17-run-unit-ops, passed). The irispython E2E (USER_GUIDE example inside IRIS) needs the package installed in the "
        "container's embedded Python: blocked-access (installing it would modify the container).",
        "reproduced-test",
        [{"kind": "run", "ref": "c17-run-unit-ops"}, {"kind": "check", "ref": "c17-offline"},
         {"kind": "inspected", "ref": "iris_vector_graph/embedded.py:312-321"},
         {"kind": "inspected", "ref": "iris_vector_graph/_write_txn.py:206-207"}],
        ["3.5-handlers", "3.7-e2e"], "S2", "high",
        "Map the statements to TSTART/TCOMMIT/TROLLBACK (or pass them through) in EmbeddedCursor, or document the limit; an "
        "irispython E2E of the USER_GUIDE example.",
        "End-to-end effect inside IRIS: blocked-access (iris_vector_graph not installed in the container's irispython; "
        "installing it would change the container)."))
    warn = g(L1703, "warnings") or []
    out.append(rec(
        "F-1703", "IVG_STRICT_NAMESPACE warns; two documents say it raises",
        "docs/ADMIN_GUIDE.md:1254 ('1 raises'); iris_vector_graph/exceptions.py:19-20 ('Upgrade to a hard error').",
        f"Live (c17-live-engine): IRISGraphStore(conn to AUDITC, namespace='USER') with IVG_STRICT_NAMESPACE=1: outcome "
        f"{g(L1703, 'outcome')}; warnings {warn[:2]}. Source iris_vector_graph/stores/iris_sql_store.py:830-838 "
        "(warnings.warn, no raise).",
        "reproduced-live" if g(L1703, "outcome") == "returned" else "confirmed-source",
        [{"kind": "live", "ref": "c17-live-engine"}, {"kind": "run", "ref": "c17-run-unit-ops"},
         {"kind": "inspected", "ref": "iris_vector_graph/stores/iris_sql_store.py:815-838"}],
        ["3.5-decoders", "5c-refusals"], "S3", "high",
        "Raise when strict, or correct ADMIN_GUIDE and the docstring."))
    nu = g(OFF, "F-1704", "not_under_IVGError") or []
    out.append(rec(
        "F-1704", "The error root does not catch every IVG error",
        "iris_vector_graph/errors.py:1-17: every engine-side error descends from IVGError, one catchable root.",
        f"c17-offline: the nine classes the finding names are not IVGError subclasses (MRO recorded); a mechanical scan of "
        f"every exception class the package defines finds {len(nu)} outside IVGError, e.g. "
        f"{', '.join(x.rsplit('.', 1)[1] for x in nu[:12])}.",
        "reproduced-test",
        [{"kind": "check", "ref": "c17-offline"}, {"kind": "run", "ref": "c17-run-unit-ops"}],
        ["3.5-decoders"], "S3", "high",
        "Re-base the public errors on IVGError (keep current bases as mixins) or narrow the docstring; extend "
        "test_all_descend_from_single_root to every exported error."))
    l2 = g(L1705, "l2_top1_for_origin")
    unsupported = g(L1705, "l2_unsupported")
    out.append(rec(
        "F-1705", "vector_similarity_search ranks L2 results farthest first",
        "A similarity search returns the nearest rows (docstring, dbapi_utils.py:249-252); VECTOR_L2 is a distance (P-1710).",
        f"Source: metric='L2' maps to VECTOR_L2 and the statement orders score DESC (dbapi_utils.py:256-272). Live "
        f"(c17-live-vec, IRIS {g(L1705, 'iris_version')}, scratch table IVGAudit.C17V rows 1:[0,0], 2:[1,0], 3:[5,0]): "
        f"vector_similarity_search(metric='L2') -> {l2}; raw VECTOR_L2 -> {g(L1705, 'raw_l2')}; the same call with COSINE "
        f"-> {g(L1705, 'cosine_top1_for_x')}.",
        "reproduced-live" if g(L1705, "l2_farthest_first") else "confirmed-source",
        [{"kind": "live", "ref": "c17-live-vec"}, {"kind": "inspected", "ref": "iris_vector_graph/dbapi_utils.py:238-275"}],
        ["3.5-handlers", "3.2-coverage"], "S2" if not unsupported else "S3", "high" if not unsupported else "medium",
        "ORDER BY score ASC for L2 (or negate it); a test with three known vectors.",
        ("On IRIS Community 2026.1 VECTOR_L2 does not exist (SQLCODE -359 'User defined SQL function SQLUSER.VECTOR_L2 does "
         "not exist'), so P-1710 does not hold on the edition this audit runs and the descending order cannot be observed "
         "here; the call raises instead (F-C1704). The ordering defect applies wherever VECTOR_L2 exists.") if unsupported else ""))
    if unsupported:
        out.append(rec(
            "F-C1704", "The L2 metric of the vector helpers fails on IRIS Community 2026.1",
            "dbapi_utils.vector_similarity_search and create_hnsw_index document metric 'L2' beside COSINE and DOT "
            "(dbapi_utils.py:238-275, :170-204); IRIS Community 2026.1 is the exercised target (P-1701).",
            f"Live (c17-live-vec, {g(L1705, 'iris_version')}): vector_similarity_search(metric='L2') -> {l2}; raw "
            f"VECTOR_L2 -> {g(L1705, 'raw_l2')}; COSINE works -> {g(L1705, 'cosine_top1_for_x')}.",
            "reproduced-live",
            [{"kind": "live", "ref": "c17-live-vec"}],
            ["3.2-coverage", "3.5-handlers"], "S4", "high",
            "Refuse metric='L2' on servers without VECTOR_L2 (or compute it), and say which metrics each edition supports.",
            "An IRIS environment-contract fact for the orchestrator: VECTOR_L2 is absent on Community 2026.1."))
    sqls = g(L1705, "create_hnsw_index_sql") or []
    out.append(rec(
        "F-1706", "create_hnsw_index does not try ACORN first",
        "Docstring: 'Tries ACORN=1 first (faster build, IRIS 2025.1+), falls back to standard HNSW' (dbapi_utils.py:181-183).",
        f"Live (c17-live-vec): the statements create_hnsw_index sent, captured through a recording cursor on AUDITC: "
        f"{sqls}; it returned {g(L1705, 'create_hnsw_index_returned')}.",
        "reproduced-live" if sqls and not any("ACORN" in s.upper() for s in sqls) else "confirmed-source",
        [{"kind": "live", "ref": "c17-live-vec"}, {"kind": "inspected", "ref": "iris_vector_graph/dbapi_utils.py:170-204"}],
        ["3.5-handlers"], "S4", "high", "Implement the two-step attempt or correct the docstring."))
    rep = g(L1707, "reported_names_absent_from_dictionary")
    out.append(rec(
        "F-1707", "SHOW CONSTRAINTS and the index lists name keys the schema does not have",
        "SHOW CONSTRAINTS reports the namespace's real keys; since spec 227/234 nodes are keyed (node_id, graph_id) and edges "
        "u_spo_graph_ekey (iris_vector_graph/schema.py:399-400, :44).",
        f"Live (c17-live-engine): SHOW CONSTRAINTS answered {g(L1707, 'SHOW CONSTRAINTS')}; the store's list_indexes "
        f"{(g(L1707, 'store_list_indexes') or [])[:4]}; INFORMATION_SCHEMA.TABLE_CONSTRAINTS for nodes/rdf_edges "
        f"{g(L1707, 'dictionary_constraints')}; reported names absent from the dictionary: {rep}.",
        "reproduced-live" if rep else "confirmed-source",
        [{"kind": "live", "ref": "c17-live-engine"}, {"kind": "inspected", "ref": "iris_vector_graph/_engine/admin.py:255-280"},
         {"kind": "inspected", "ref": "iris_vector_graph/stores/iris_sql_store.py:3060-3082"}],
        ["3.6-keys", "3.5-decoders"], "S3", "high", "Read constraints from the dictionary, or list the real names and columns."))
    for fid, title, intended, observed, ev, sev, remedy in [
        ("F-1708", "The bolt-on installer does not do what deploy/README.md says",
         "deploy/README.md:24 (creates namespace, installs schema, prints key and start command) and :85 (ivg_service user "
         "with access only to Graph_KG.* tables).",
         "Confirmed in source: deploy/bolt-on/install.sh generates a password (:21-22) and writes ivg-config.yml (:72-91) but "
         "creates no user or grant; the printed start command (:97) passes --iris-password with no user, and `ivg server "
         "start` has no user option (iris_vector_graph/cli.py:419-434: IRIS_USERNAME defaults to _SYSTEM in cypher_api.py:170); "
         "the namespace step uses %SYS.Namespace over SQL/Native (:36-49), which ADMIN_GUIDE section 1 says cannot create a "
         "namespace; nothing reads ivg-config.yml. Not run: the installer targets a remote instance and would create a "
         "namespace (forbidden on the audit container).",
         [{"kind": "inspected", "ref": "deploy/bolt-on/install.sh:15-100"}, {"kind": "inspected", "ref": "deploy/README.md:20-26, 84-101"},
          {"kind": "inspected", "ref": "iris_vector_graph/cli.py:415-441"}], "S2",
         "Create the user and ADMIN_GUIDE section 3 grants in the installer and pass the user name, or rewrite deploy/README.md path 2."),
        ("F-1709", "deploy/README.md promises a refusal the server does not make",
         "deploy/README.md:86: the server refuses auth: none with host 0.0.0.0 unless --force-no-auth.",
         "Confirmed in source: `ivg server start` defaults --host 0.0.0.0 and has no --force-no-auth (cli.py:419-426); auth is "
         "off when IVG_API_KEY is unset (iris_vector_graph/_api_key.py:21-23); no code reads IVG_AUTH_MODE "
         "(deploy/docker/compose.yml:34). HD-1705 working decision: local-only default or explicit opt-in.",
         [{"kind": "inspected", "ref": "iris_vector_graph/cli.py:415-441"}, {"kind": "inspected", "ref": "iris_vector_graph/_api_key.py:15-30"},
          {"kind": "inspected", "ref": "deploy/README.md:84-88"}], "S1",
         "Per HD-1705: default to 127.0.0.1 or require an explicit opt-in for unauthenticated external binding; align the docs."),
        ("F-1710", "The docker deploy recipe cannot build or log in as written",
         "deploy/README.md path 1 ('5 minutes').",
         "Confirmed in source: deploy/docker/compose.yml:19-22 builds from context ../.. with dockerfile Dockerfile, and the pin "
         "has no root Dockerfile (git ls-tree 3eaa79cf); IRIS_USERNAME ivg_service (:31) is created by nothing in the recipe or "
         "deploy/docker/cpf/merge.conf; the image is iris-community:latest (:3) while docker-compose.yml pins 2026.1. Not "
         "built: a docker build on the audit host is outside the lane's scope.",
         [{"kind": "inspected", "ref": "deploy/docker/compose.yml:1-40"}, {"kind": "inspected", "ref": "deploy/docker/cpf/merge.conf"}],
         "S3", "Add the Dockerfile and a user-creation step (or use _SYSTEM for the demo and say so), and pin the image."),
    ]:
        out.append(rec(fid, title, intended, observed, "confirmed-source", ev, ["3.1-coverage"], sev, "high", remedy))
    out.append(rec(
        "F-1711", "The deploy guide's SDK example reads a field IVGResult does not have",
        "deploy/README.md:73-79 iterates result.records.",
        f"c17-offline: IVGResult fields {g(OFF, 'F-1711', 'fields')}; result.records -> {g(OFF, 'F-1711', 'result.records')}.",
        "reproduced-test", [{"kind": "check", "ref": "c17-offline"}, {"kind": "inspected", "ref": "iris_vector_graph/result.py:9-16"}],
        ["3.5-decoders"], "S4", "high", "Use result.rows/columns in the example, or add a records view."))
    out.append(rec(
        "F-1712", "LazyKG.in_degree collapses parallel edges that degree() counts",
        "LazyKG docstring: degree counts parallel edges (stores/lazy_kg.py:215-235); in-direction should count the same edges.",
        f"Live (c17-live-engine, multigraph c17mg): rows into c17:b = {g(L1712, 'rows_into_b')} (two parallel a-R->b and "
        f"c-R->b); out_degree(a) = {g(L1712, 'out_degree_a')}; in_degree(b) = {g(L1712, 'in_degree_b')}; "
        f"in_degree_for_predicate(b, R) = {g(L1712, 'in_degree_for_predicate_b')}.",
        "reproduced-live" if g(L1712, "in_degree_undercounts") else ("not-reproduced" if L1712 else "confirmed-source"),
        [{"kind": "live", "ref": "c17-live-engine"}, {"kind": "inspected", "ref": "iris_vector_graph/stores/lazy_kg.py:215-269"},
         {"kind": "inspected", "ref": "iris_src/src/Graph/KG/Adjacency.cls:197-209"}],
        ["3.5-handlers"], "S2", "high", "Count the keyed children for a multigraph triple; a multigraph unit test."))
    out.append(rec(
        "F-1713", "STATUS_PARTS omits two parts that status() marks unknown",
        "status.py:10-11 'What EngineStatus.unknown may name'.",
        f"c17-offline: STATUS_PARTS {g(OFF, 'F-1713', 'STATUS_PARTS')}; admin.py appends {g(OFF, 'F-1713', 'names_outside_STATUS_PARTS')} "
        f"(admin.py:551, :752-753). Live status() on AUDITC: unknown = {g(L1713, 'unknown')}; status() wrote "
        f"{g(L1713, 'status_journal', 'records')} journal records (a reader).",
        "reproduced-test", [{"kind": "check", "ref": "c17-offline"}, {"kind": "live", "ref": "c17-live-engine"}],
        ["3.5-decoders"], "S4", "high", "Add both names to STATUS_PARTS; test set(status.unknown) <= set(STATUS_PARTS)."))
    wk = g(SRV, "wrong_key") or {}
    bad = [k for k, v in wk.items() if isinstance(v, dict) and not v.get("is_IVGClientError")]
    out.append(rec(
        "F-1714", "Two IVGClient calls and the async client do not map 401/403",
        "IVGClient._refused: '401 and 403 as IVGClientError, for every request (R225)' (sdk.py:195-201); IVGClientError "
        "docstring (sdk.py:22-25).",
        f"Live (c17-live-server: Cypher HTTP server on 127.0.0.1:18750 with IVG_API_KEY set, client with a wrong key): "
        f"{json.dumps(wk)[:700]}.",
        "reproduced-live" if bad else ("not-reproduced" if wk else "confirmed-source"),
        [{"kind": "live", "ref": "c17-live-server"}, {"kind": "inspected", "ref": "iris_vector_graph/sdk.py:166-182, 254-281"}],
        ["3.5-decoders"], "S3", "high", "Route those calls through _refused; unit tests with a 401 transport."))
    dup = g(SRV, "nodes_created_for_one_call")
    out.append(rec(
        "F-C1703", "One HTTP client call can create a write twice (client resend after a late reply; server re-run after an exception)",
        "decisions.md HD-1702 / HD-1603 (working): after an ambiguous outcome retry only a read, a write known not to have run, "
        "or one with a verified idempotency key; treat client and server retries as one protocol.",
        f"Live (c17-live-server): IVGClient(timeout=2 s, max_retries=3) through a proxy that held the first reply 4 s sent "
        f"one CREATE (n:C17Dup {{marker}}); the proxy saw {g(SRV, 'proxy_requests')} requests, the client answered "
        f"{g(SRV, 'client_answer')}, and AUDITC holds {dup} nodes with that marker. Source: sdk.py:209-228 resends a POST "
        "after TimeoutException/ConnectError/5xx whatever the query; IVGServerError.is_retryable is any 5xx (sdk.py:41-42); "
        "cypher_api.py:250-268 re-runs execute_cypher on a fresh connection after any exception. Model: "
        f"cmc-retry-as-built-once ({MODELS['cmc-retry-as-built-once']['result']}), cmc-retry-as-built-honest "
        f"({MODELS['cmc-retry-as-built-honest']['result']}: a definite failure reported for an applied write), "
        f"cmc-retry-reviewed ({MODELS['cmc-retry-reviewed']['result']}), controls cmc-retry-ctl-client/-server.",
        "reproduced-live" if (dup or 0) > 1 else "reproduced-model",
        [{"kind": "live", "ref": "c17-live-server"}, {"kind": "mc", "ref": "cmc-retry-as-built-once"},
         {"kind": "mc", "ref": "cmc-retry-as-built-honest"}, {"kind": "mc", "ref": "cmc-retry-reviewed"},
         {"kind": "control", "ref": "cmc-retry-ctl-client"}, {"kind": "control", "ref": "cmc-retry-ctl-server"},
         {"kind": "inspected", "ref": "iris_vector_graph/sdk.py:41-42, 209-228"},
         {"kind": "inspected", "ref": "iris_vector_graph/cypher_api.py:250-268"}],
        ["3.7-integration-worlds", "3.3-model-check", "SYS-I6"], "S2", "high",
        "Retry only reads or writes known not to have run (connect error before send); report an unknown outcome for an "
        "ambiguous write; or carry an end-to-end idempotency key (the ledger's retry key) through /api/cypher.",
        "Intent status: HD-1702/HD-1603 are working assumptions (decisions.md), not maintainer decisions; the duplicate is "
        "observed behaviour either way. Shared with module 16 (server half)."))
    cs = g(OFF, "F-C1701") or {}
    out.append(rec(
        "F-C1701", "Two declared console scripts cannot run from an install",
        "pyproject.toml:176-179 declares console scripts run-tests and networkx-loader beside ivg.",
        f"c17-offline: run-tests -> {g(cs, 'runs_outside_repo_without_PYTHONPATH', 'run-tests')}; scripts/test.py tracked at "
        f"the pin: {cs.get('scripts/test.py tracked at pin')}; the wheel packages only {cs.get('wheel_packages')} "
        "(pyproject.toml wheel config), so scripts.ingest.networkx_loader is absent from a wheel install (it resolved here only "
        "because the venv's editable install puts a source checkout on sys.path).",
        "reproduced-live",
        [{"kind": "check", "ref": "c17-offline"}, {"kind": "inspected", "ref": "pyproject.toml:176-196"}],
        ["3.1-coverage"], "S4", "high", "Drop the two entries or ship the modules they name."))
    out.append(rec(
        "F-C1702", "`ivg server start --workers N` (N > 1) exits without serving",
        "docs/ADMIN_API.md:20 documents --workers; OPS-B1.12 (uvicorn.run(cypher_api.app, host, port, workers)).",
        "Live (c17-live-server-workers): `ivg server start --host 127.0.0.1 --port 18799 --workers 2` printed uvicorn's "
        "'You must pass the application as an import string to enable reload or workers' and exited 1; cli.py:437-438 passes "
        "the app object.",
        "reproduced-live",
        [{"kind": "live", "ref": "c17-live-server-workers"}, {"kind": "inspected", "ref": "iris_vector_graph/cli.py:427-441"}],
        ["3.7-e2e"], "S3", "high",
        "Pass the import string 'iris_vector_graph.cypher_api:app' to uvicorn.run, or drop the option; the product's own N-process "
        "path then exists for the 1-vs-N validation.",
        "Consequence for gate 3.7 (1 vs N application processes): the documented multi-process server path does not start."))
    return out


def footprints():
    def jr(k):
        return g(FP, k) or {}
    E = []

    def add(entry, role, source, reads, writes, txn, claims, run_key, declared):
        j = jr(run_key) if run_key else None
        jj = None
        if j:
            written = set(j.get("stores_written", []))
            und = sorted(w for w in written if not any(w.startswith(d) for d in declared))
            jj = {"run": "c17-live-engine", "stores_written": sorted(written),
                  "stores_written_in_txn": j.get("stores_written_in_txn"),
                  "stores_written_outside_any_txn": j.get("stores_written_outside_any_txn"),
                  "outermost_transactions": j.get("outermost_transactions"), "error": j.get("error"),
                  "undeclared_writes": und, "match": not und and not (claims.get("claims") and j.get("stores_written_outside_any_txn")),
                  "mismatch": (f"undeclared {und}" if und else "") + (
                      f" writes outside a transaction although the source claims one: {j.get('stores_written_outside_any_txn')}"
                      if claims.get("claims") and j.get("stores_written_outside_any_txn") else "")}
        E.append({"entry": entry, "role": role, "source": source, "reads": reads, "writes": writes, "transaction": txn,
                  "locks": [], "claims_atomic": claims, "journal": jj})
    add("IRISGraphStore.write_nodes", "writer", "iris_vector_graph/stores/iris_sql_store.py:1214-1251",
        ["sql:Graph_KG.nodes (duplicate probe)"], ["sql:Graph_KG.nodes", "sql:Graph_KG.rdf_labels", "sql:Graph_KG.rdf_props", "global:^KG"],
        "one write_txn (Graph.KG.Txn level)", {"claims": True, "source": "iris_sql_store.py:1215 'in one transaction'"},
        "store.write_nodes", ["sql:Graph_KG.nodes", "sql:Graph_KG.rdf_labels", "sql:Graph_KG.rdf_props", "global:^KG"])
    add("IRISGraphStore.write_edges", "writer", "iris_vector_graph/stores/iris_sql_store.py:1253-1302",
        ["sql:Graph_KG.nodes"], ["sql:Graph_KG.nodes", "sql:Graph_KG.rdf_edges", "global:^KG", "global:^IVG.Ledger"],
        "one write_txn", {"claims": True, "source": "iris_sql_store.py:1254 'in one transaction'"},
        "store.write_edges", ["sql:Graph_KG.nodes", "sql:Graph_KG.rdf_edges", "global:^KG", "global:^NKG", "global:^IVG"])
    add("IRISGraphStore.delete_edges", "writer", "iris_vector_graph/stores/iris_sql_store.py:1474-1520 (Graph.KG.Eraser.EraseEdges)",
        ["sql:Graph_KG.rdf_edges"], ["sql:Graph_KG.rdf_edges", "sql:Graph_KG.rdf_reifications", "sql:Graph_KG.kg_EdgeEmbeddings", "global:^KG", "global:^NKG"],
        "Eraser.EraseEdges: one transaction", {"claims": True, "source": "Eraser.cls EraseEdges TSTART..TCOMMIT"},
        "store.delete_edges", ["sql:Graph_KG.", "global:^KG", "global:^NKG", "global:^IVG"])
    add("IRISGraphStore.delete_nodes", "writer", "iris_vector_graph/stores/iris_sql_store.py:1320-1418 (Graph.KG.Eraser.EraseNodes)",
        ["sql:Graph_KG.nodes"], ["sql:Graph_KG.nodes", "sql:Graph_KG.rdf_labels", "sql:Graph_KG.rdf_props", "sql:Graph_KG.rdf_edges",
                                 "sql:Graph_KG.docs", "sql:Graph_KG.kg_NodeEmbeddings", "global:^KG", "global:^NKG"],
        "Eraser.EraseNodes: one transaction", {"claims": True, "source": "nodes_edges.py:1531 'in one transaction'"},
        "store.delete_nodes", ["sql:Graph_KG.", "global:^KG", "global:^NKG", "global:^IVG"])
    add("IRISGraphStore.write_temporal_edge", "writer", "iris_vector_graph/stores/iris_sql_store.py:2655-2690 (Graph.KG.TemporalIndex)",
        [], ['global:^KG("tout"/"tin"/"bucket"/"tagg"/"tlast"/"edgeprop")', "sql:Graph_KG.nodes", "sql:Graph_KG.rdf_edges (marked structural row)"],
        "server-side (TemporalIndex)", {"claims": False, "source": ""}, "store.write_temporal_edge",
        ["global:^KG", "sql:Graph_KG.", "global:^NKG", "global:^IVG"])
    add("IRISGraphStore.execute_sql(sql, params, read_only=True)", "reader by name; writer in fact", "iris_vector_graph/stores/iris_sql_store.py:1522-1557",
        ["any"], ["any table the SQL names (read_only is ignored: HD-1701)"], "the statement's own (autocommit)",
        {"claims": False, "source": "store_protocol read_only flag; HD-1701"}, "store.execute_sql(read_only=True) INSERT",
        ["sql:", "global:"])
    add("dbapi_utils.insert_vector", "writer", "iris_vector_graph/dbapi_utils.py:101-168", [], ["the caller's table"],
        "the caller's cursor (autocommit per statement)", {"claims": False, "source": ""}, "",
        [])
    add("IRISGraphEngine.status()", "reader", "iris_vector_graph/_engine/admin.py:380-760", ["many (probes)"], [], "none",
        {"claims": False, "source": ""}, "", [])
    add("IRISGraphEngine.verify_sync() (repair=False)", "reader", "iris_vector_graph/_engine/admin.py:756-848", ["sql:Graph_KG.rdf_edges", "global:^KG"], [],
        "none", {"claims": False, "source": ""}, "verify_sync()", [])
    add("Graph.KG.Meta.Set / Delete", "writer", "iris_src/src/Graph/KG/Meta.cls:14-28", [], ["global:^Graph.KG.Meta"],
        "none (one SET/KILL)", {"claims": False, "source": ""}, "Graph.KG.Meta.Set", ["global:^Graph.KG.Meta"])
    # journal for insert_vector and status come from other result keys
    for e in E:
        if e["entry"] == "dbapi_utils.insert_vector":
            j = g(L1705, "insert_vector_journal") or {}
            if isinstance(j, str):
                e["journal"] = None
                e["journal_note"] = j
            elif j:
                e["journal"] = {"run": "c17-live-engine", "stores_written": j.get("stores_written"),
                                "stores_written_outside_any_txn": j.get("stores_written_outside_any_txn"),
                                "match": all(s.startswith("sql:IVGAudit") for s in j.get("stores_written", [])), "mismatch": ""}
        if e["entry"] == "IRISGraphEngine.status()":
            j = g(L1713, "status_journal") or {}
            if j:
                e["journal"] = {"run": "c17-live-engine", "stores_written": j.get("stores_written"), "records": j.get("records"),
                                "match": not j.get("stores_written"), "mismatch": "" if not j.get("stores_written") else "status() wrote"}
    val = [e for e in E if e["journal"]]
    mism = [{"entry": e["entry"], "mismatch": e["journal"]["mismatch"]} for e in val if not e["journal"]["match"]]
    return {"module": "17", "pin": PIN, "entries": E, "validated": len(val), "mismatches": mism,
            "notes": "Journal classification per live/breadth-c/jcheck.py; execute_sql(read_only=True) writing is HD-1701 "
                     "(intent-lane probe evidence/runs/ib-HD1701-readonly-flag.json)."}


if __name__ == "__main__":
    f = findings()
    (COMP / "findings/audit/17.json").write_text(json.dumps({"module": "17", "pin": PIN, "findings": f}, indent=1) + "\n")
    fp = footprints()
    (COMP / "footprints/17.json").write_text(json.dumps(fp, indent=1) + "\n")
    from collections import Counter
    print("findings", Counter(x["disposition"] for x in f), "footprints validated", fp["validated"], "mismatches", fp["mismatches"])
