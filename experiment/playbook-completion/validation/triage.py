#!/usr/bin/env python3
"""Triage rules for the validation lane: every failure and error of a run is matched to exactly one rule.

    python triage.py <prefix> [...]     prints the rule each failure/error matched, and any that matched none

Categories (the lane brief): product-defect (the as-built pin violates a spec/doc/contract; `test-stale` marks the
case where the pin's own test contradicts the pin's documented behaviour, so the suite is red at the pin whatever the
environment), environment (exact missing dependency), harness (this lane's harness), intermittent (passed on a rerun
of the same set). A rule cites the evidence that justifies its category.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aggregate import aggregate  # noqa: E402

RULES = [
    # (id, category, node regex, message regex, reason / reference)
    ("width-refusal", "product-defect (test-stale)", r".", r"EmbeddingIdentityConflict.*this engine's embedding_dimension is",
     "The test builds IRISGraphEngine(embedding_dimension=4 or another width) and calls initialize_schema() without "
     "rewidth on a namespace set up at the session width 768; 4.7.0 refuses that by design (CHANGELOG.md:22-24, the "
     "exception text). Code follows its contract; the test predates 4.7.0."),
    ("sqluser-views", "product-defect (test-stale)", r".", r"Table 'SQLUSER\.",
     "The test uses unqualified SQLUser tables (nodes, rdf_edges, ...); 4.6.0 removed the four SQLUser views "
     "(CHANGELOG.md:786-789 'The four SQLUser views are gone: read the tables'); tests/TESTING.md still documents them."),
    ("gql-sqluser-setup", "product-defect (test-stale)", r"tests\.integration\.gql\.", r".",
     "Same root cause as sqluser-views: the GraphQL tests seed and check rows with unqualified SQLUser SQL inside bare "
     "try/except (tests/integration/gql/test_graphql_queries.py:34-60), so the rows are never written and the resolver "
     "answers None/'not found'. Separately (inspected, not run): api/gql/resolvers/query.py:79-92 (node(id)) also "
     "queries unqualified tables, which on a 4.6+ install raises SQLCODE -30."),
    ("path-as-dict", "product-defect (test-stale)", r"test_shortest_path", r"JSON object must be str, bytes or bytearray, not dict",
     "The test json.loads() a path; since 4.6.0 a path in a result row is a Python dict (CHANGELOG.md:771-772, 884)."),
    ("mock-signature", "product-defect (test-stale)", r"test_centrality_unit", r"unexpected keyword argument 'loners'",
     "Pure unit test (no IRIS): its mock store's execute_eigenvector lacks the `loners` keyword the engine passes "
     "(iris_vector_graph/_engine/algorithms.py:1518). Red in CI's own unit job as well."),
    ("regression-budgets", "product-defect (test-stale)", r"tests\.regression\.", r".",
     "Static budgets in tests/regression (cyclomatic complexity, 2,000-line modules, 800-line classes, "
     "engine_api_baseline.json) are exceeded or stale at the pin (translator.py 31,908 lines; API grew graph= params). "
     "Not run by CI (.github/workflows/ci.yml runs tests/unit only)."),
    ("decimal-score", "product-defect (driver 5.3.2 from the pin's uv.lock)", r".",
     r"unsupported operand type\(s\) for -: 'float' and 'decimal.Decimal'|'decimal.Decimal' and 'float'|Decimal\('",
     "CALL ivg.closeness / ivg.degreeCentrality YIELD score returns decimal.Decimal under the driver the pin's uv.lock "
     "installs (intersystems-irispython 5.3.2), where the test (and networkx comparison) expects a float; tests/e2e/test_460_proc_yield_alias_e2e.py:108 "
     "asserts a YIELDed ppr score is int/float and gets Decimal('0.3759...'); the r306 algorithm oracle (run in USER "
     "with the documented IVG_ORACLE_USER=1) fails the same way: degreeCentrality/closeness/community scores come back "
     "as Decimal('0.571428571') against the reference's float 0.571428571 (unequal in Python); ivg.ppr's values are "
     "within the oracle's 1e-4 tolerance (~6e-7 off), so only the type fails. All 252 oracle failures are Cypher "
     "CALL ivg.* YIELD columns (ivg.ppr, ivg.degreeCentrality, ivg.closeness, community procedures), on both the arno "
     "and no_arno variants; the Python-API cases (kg_PERSONALIZED_PAGERANK, degree_centrality, ...) all pass. "
     "docs/dev/driver-drift.md shows 5.4.0 also decodes a decimal as "
     "Decimal, so the type is not obviously a 5.3.2 artefact. "
     "docs/dev/driver-drift.md says IVG decodes property values typed so answers do not depend on the driver; score "
     "columns are not covered. Driver dependence not excluded: 5.4.x is not available offline here. Severity S4, "
     "confidence medium."
     " DRIVER A/B (operator ruling 03:16Z): the same files under intersystems-irispython 5.4.0 ($RUN_DIR/availability/driver-5.4.0-venv) pass: driver540-1 (237 passed; only leiden-karate-ari fails) and driver540-oracle-1 (960/960, against 34 failures on 5.3.2 in oracle-1-c00). pyproject.toml:42 asks only intersystems-iris>=1.0.0, and uv.lock:1358-1371 resolves it to intersystems-iris 5.3.3 / irispython 5.3.2, so a `uv sync` of the pin installs the driver on which this fails; CI tests a fresh resolution instead (.github/workflows/ci.yml)."),
    ("gref-logging", "environment", r"test_setup_logging", r"gref|Class or mo",
     "iris-embedded-python-wrapper logs \"Class or module 'gref' not found in iris_embedded_python\" when no embedded "
     "IRIS runtime is configured (client-only Python on this VM); the test asserts no unexpected log lines. Same "
     "failure as the original audit's unit run."),
    ("audit-ns-guard", "environment", r".", r"AuditNamespacePolicy",
     "The test makes its own scratch namespace (scripts/dev/make_scratch_namespace.py / tcp_setup); this lane may not "
     "create namespaces (CONVENTIONS.md) and the harness refuses it. Missing dependency: an owned scratch namespace."),
    ("doc460", "environment", r"test_docs_run", r"IVG460DOC: FAIL ns: namespace IVG460DOC does not exist",
     "tests/docs/test_docs_run.py needs the scratch namespace IVG460DOC made by make_scratch_namespace.py "
     "(its docstring); not present, and this lane may not create it."),
    ("alt-namespace", "environment", r"IVGALT|IVG262ALT", r"Access Denied",
     "Needs namespace IVG262ALT (IVG set up with schema IVGALT); absent (a connection to a missing namespace answers "
     "Access Denied), and this lane may not create it."),
    ("alt-namespace-grant", "environment", r"test_grant_copy", r"Access Denied",
     "tests/integration/test_grant_copy.py:20 connects to IVG_NS_IVG262ALT (default IVG262ALT); absent, and this "
     "lane may not create it."),
    ("mcp-ai-classes", "environment", r".", r"CLASS DOES NOT EXIST>.*\*Graph\.KG\.MCP",
     "Graph.KG.MCPTools / MCPToolSet / MCPService extend %AI.Tool / %AI.ToolSet / %AI.MCP.Service, which IRIS "
     "Community 2026.1 does not have (env-probe/license.log); the pin's initialize_schema skips them and says so."),
    ("var-length-raises", "product-defect (test-stale)", r"test_query_deep", r"var-length walk \(BFSFastJsonSorted\)",
     "The test mocks BFSFastJsonSorted to raise and expects a result; since 4.6.0 the engine raises "
     "(iris_vector_graph/_engine/query.py:4200 '4.6.0: raises; it answered no rows, logged at WARNING')."),
    ("nodepk-leftover", "product-defect (test-isolation)", r"test_nodepk_migration", r"UNIQUE or PRIMARY KEY constraint failed",
     "The fixture (tests/integration/test_nodepk_migration.py:55-61) inserts fixed ids SAMPLE:node1.. into the "
     "unqualified `nodes`, i.e. the legacy SQLUser.nodes this file creates (:198, :477); a row left by an earlier use "
     "fails the unique check. Test-side isolation defect; the file also leaves SQLUser tables in the namespace."),
    ("duplicate-listerror", "product-defect (driver 5.3.2 from the pin's uv.lock)", r".",
     r"LIST ERROR> Incorrect list format, unsupported type for IRISList",
     "IRISGraphStore.write_nodes / write_edges document 'A duplicate row is skipped' "
     "(iris_vector_graph/stores/iris_sql_store.py:1215-1220; _skip_duplicate :756-762 skips only what is_duplicate() "
     "recognises). On this stack (IRIS Community 2026.1, intersystems-irispython 5.3.2 from the pin's uv.lock) the "
     "duplicate INSERT inside write_txn surfaces as DataError '<LIST ERROR> Incorrect list format, unsupported type "
     "for IRISList; type detected : 0' instead of SQLCODE -119, so a re-ingest of an existing node raises "
     "GraphWriteError and writes nothing. Reproduced in both runs but not on the same cases (integration-1: 3 cases; "
     "rerun-1: 4, one of which passed in integration-1), so the class is reproducible and the case intermittent: a "
     "lead for a product-defect (is_duplicate, iris_vector_graph/_write_txn.py:46-49, recognises only 'unique'/-119 "
     "text); driver dependence not excluded (5.4.x unavailable offline). Same class in e2e: "
     "tests/e2e/test_create_edge_atomic_e2e.py:91-102 expects the server's <SUBSCRIPT> error for a too-long endpoint "
     "pair and gets GraphWriteError carrying the driver's <LIST ERROR> instead (nothing written either way)."
     " DRIVER A/B (operator ruling 03:16Z): the same files under intersystems-irispython 5.4.0 ($RUN_DIR/availability/driver-5.4.0-venv) pass: driver540-1 (237 passed; only leiden-karate-ari fails) and driver540-oracle-1 (960/960, against 34 failures on 5.3.2 in oracle-1-c00). pyproject.toml:42 asks only intersystems-iris>=1.0.0, and uv.lock:1358-1371 resolves it to intersystems-iris 5.3.3 / irispython 5.3.2, so a `uv sync` of the pin installs the driver on which this fails; CI tests a fresh resolution instead (.github/workflows/ci.yml)."),
    ("clone-perms", "harness", r"test_460_embed_queue_worker_routes_e2e", r"ivgtest_USER/IVGTest\.FakeEmbedding\.cls",
     "Harness: the clean clone was checked out under umask 077, so tests/e2e/fixtures/IVGTest.FakeEmbedding.cls was "
     "0600; `docker cp` keeps the mode and owner and irisowner could not read it, so %SYSTEM.OBJ.Load failed. The clone "
     "was made go+rX (no content or git-visible change) at 01:31 UTC and the file rerun as perm-rerun-1."),
    ("arno-absent", "environment", r"test_411_bfs_zf_limit_e2e", r"assert False is True",
     "test_the_store_probe_keeps_arno_on asserts _detect_arno() is True; the Arno callout library (libarno_callout.so "
     "via $ZF, loaded by Graph.KG.ArnoAccel) is not deployed on this Community container (other files skip with 'the "
     "Arno library is not loaded on this container'); this file has no such skip."),
    ("licence-236", "environment", r".", r"Unable to allocate a license",
     "Infrastructure, never a product result: IRIS Community allows 8 licence units for the whole container. The "
     "spec 236 scratch fixture (tests/conftest.py:1376-1492, Scratch236) opens a new connection for every native()/"
     "dbapi() call and closes them only at session end, so even one file's session exceeds 8 units. Rerun per file "
     "under the lock (scratch-236-2a/2b) failed the same way while a probe under the lock showed no other client "
     "(env-probe/licprobe-1.log: LUConsumed 1). Missing dependency: a licence with more units (Enterprise)."),
    ("varlen-lookup-lead", "unconfirmed lead (non-decisive run)", r"test_025_varlen_path_functions",
     r"DID NOT RAISE <class 'RuntimeError'>",
     "Seen only in the licence-degraded spec 236 scratch runs (scratch-236-1, scratch-236-2a-f00): "
     "tests/integration/test_025_varlen_path_functions.py:178-185 patches get_node_labels to raise and expects "
     "execute_cypher to raise; it returned. Could be a swallowed lookup error (product) or a route that does not call "
     "get_node_labels in this namespace; not decidable from a run whose fixture exhausted the licence."),
    ("embedded-python-deps", "environment", r"test_execution_contexts_new", r"No module named 'pydantic'",
     "The test copies the checkout's package into the container and imports it in IRIS embedded Python "
     "(/usr/irissys/bin/irispython); the container's embedded Python has no pydantic (IVG's dependencies are not "
     "installed there). Missing dependency: the package's requirements in the container's irispython."),
    ("duplicate-edge-timing", "intermittent", r"test_duplicate_edge_cost_e2e",
     r"AssertionError: \[",
     "The functional half passed (one edge). The timing half wants the median duplicate create_edge under 8 ms "
     "(tests/e2e/test_duplicate_edge_cost_e2e.py:25-26, 'a guarded insert is a probe', unique-key path ~30 ms on the "
     "author's machine); here medians are ~10 ms on a 2-CPU Community container on a shared VM. Below the 30 ms "
     "unique-key cost, so consistent with the probe path on slower hardware; not decidable here (no reference run on "
     "the author's hardware). Both cases passed in rerun-2: intermittent timing."),
    ("leiden-karate-ari", "product-defect", r"test_communities_e2e.*test_leiden_karate_club_ari", r"Karate club ARI",
     "Spec 163 FR-007 (as relaxed in the test, tests/e2e/test_communities_e2e.py:78-110): Leiden on Zachary's karate "
     "club, gamma=0.05, seed 42, must reach ARI > 0.75; here ARI = 0.072, identical in e2e-1-c17 and rerun-2 "
     "(deterministic). This container has no Arno library, so the non-Arno path ran; tests/perf/"
     "test_leiden_four_way.py:12-15 states both paths agree (ARI 1.0 vs leidenalg). Severity S3 (wrong partition "
     "quality on the documented fallback), confidence medium: the threshold's derivation assumes one path."),
    ("bulk-ingest-timing", "environment", r"test_stress_ingest.*throughput", r"BulkIngestEdges throughput",
     "Wall-clock bound (>10K edges/s at 500 rows/txn) measured on the author's ivg-iris-enterprise "
     "(tests/e2e/test_stress_ingest.py:148-177: 13,123 e/s there); the same test skips the bound on a shared host "
     "(IVG_GATE_PARALLEL=1, citing 5,375 e/s). Here 6,765 e/s (e2e-1-c20) and 5,807 e/s (rerun-3) on a 2-CPU Community "
     "container on a shared VM. The ingest itself succeeded."),
    ("temporal-structural-cursor", "product-defect (driver 5.3.2 from the pin's uv.lock)", r"test_temporal_structural_row_live",
     r"Cursor closed; Details: DataRow is inaccessible",
     "Spec 246: with IRISGraphEngine(temporal_structural_rows=True), create_edge_temporal must give a temporal-only "
     "edge a marked structural row (tests/e2e/test_temporal_structural_row_live.py:53-90). It raises "
     "ProgrammingError 'Cursor closed; DataRow is inaccessible' at iris_vector_graph/_engine/temporal.py:189 "
     "(_own_structural_row -> _select_structural_row fetchone) in both e2e-1-c20 and rerun-3 (fresh session, file "
     "first): deterministic. Driver dependence (5.3.2) not excluded. Severity S2 (the opt-in write path fails), "
     "confidence medium."
     " DRIVER A/B (operator ruling 03:16Z): the same files under intersystems-irispython 5.4.0 ($RUN_DIR/availability/driver-5.4.0-venv) pass: driver540-1 (237 passed; only leiden-karate-ari fails) and driver540-oracle-1 (960/960, against 34 failures on 5.3.2 in oracle-1-c00). pyproject.toml:42 asks only intersystems-iris>=1.0.0, and uv.lock:1358-1371 resolves it to intersystems-iris 5.3.3 / irispython 5.3.2, so a `uv sync` of the pin installs the driver on which this fails; CI tests a fresh resolution instead (.github/workflows/ci.yml)."),
    ("schema-contract-stale", "product-defect (test-stale)", r"test_schema_contract", r"has UNEXPECTED columns",
     "tests/test_schema_contract.py's EXPECTED_COLUMNS predate columns the pin's DDL adds (docs.graph_id, "
     "embedding_registry.kind, kg_EdgeEmbeddings.emb_rowid/graph_id/metadata, rdf_edges.ekey, rdf_props.val_key); the "
     "message itself says to update EXPECTED_COLUMNS when the DDL changed intentionally. Not run by CI."),
    ("nodepk-sqluser-bulk", "product-defect (test-stale)", r"test_nodepk_(graph_analytics|advanced_benchmarks|performance)",
     r"FOREIGN KEY constraint failed|Should insert all 10K nodes, got 0",
     "The fixtures use scripts/migrations/migrate_to_nodepk.py:254-310 bulk_insert_nodes, which INSERTs into the "
     "unqualified `nodes` (SQLUser), removed in 4.6.0 (CHANGELOG.md:786-789): the rows land in a stray legacy "
     "SQLUser.nodes left by tests/integration/test_nodepk_migration.py:198 (or nowhere), so Graph_KG.rdf_labels' "
     "fk_labels_node refuses the labels (-121) and the 10K-node gate counts 0 Graph_KG rows."),
    ("sc010-latency", "product-defect", r"test_227_single_graph_latency", r"the scoped search costs",
     "Spec 227 SC-010 (tests/perf/test_227_single_graph_latency.py, interleaved medians: the test's own A/B design): "
     "the graph-scoped kg_KNN_VEC must stay within 1.1x of the 3.2.0 unscoped scan on the same 300 rows. Measured "
     "1.169x (2.05 vs 1.75 ms), 1.145x (1.85 vs 1.61 ms), 1.205x (3.00 vs 2.48 ms) in perf-default-1/2/3: over budget "
     "in every run here. Severity S4 (about 0.3 ms per call), confidence medium: Community 2-CPU container, not the "
     "author's laptop; the ratio, not the absolute time, is the criterion."),
    ("leiden-10k-timing", "environment (timing, unconfirmed)", r"test_communities_perf.*leiden", r"Leiden on 10000 nodes",
     "Spec 163 NFR-004 gate in tests/e2e/test_communities_perf.py: Leiden on ER(10,000, 0.001) under 60 s; 62.04 s "
     "here on the non-Arno path (no libarno on Community) on a 2-CPU container. The file's docstring calls the gate a "
     "wide upper bound for the fallback path; missed by 3% on non-reference hardware: a lead, not decidable here."),
    ("embedded-callin-denied", "environment", r"test_460_r185_container_script_refusal_e2e|test_460_r197_test_container_refusal_e2e",
     r"IrisStart failed: IRIS_ACCESSDENIED",
     "The test runs the setup script inside the container with its embedded Python (/usr/irissys/bin/irispython "
     "via docker exec); IrisStart answers IRIS_ACCESSDENIED (-15): the container's callin access for that OS user is "
     "not granted (Community image default; changing %Service_CallIn would reconfigure the shared container). The "
     "refusal under test is never reached."),
    ("list-param-count", "product-defect (driver 5.3.2 from the pin's uv.lock)", r".",
     r"PARAMETER ERROR>; Details: Invalid number of parameters|ARGUMENT ERROR> Bad argument given; Details: Incorrect number of parameters",
     "Cypher with list values bound as parameters or list concatenation (UNWIND $list, two list parameters, "
     "size($l1 + $l2), TCK Unwind1 [3] `UNWIND (first + second)`) fails in the driver's parameter binding: "
     "'<PARAMETER ERROR> Invalid number of parameters' / '<ARGUMENT ERROR> Incorrect number of parameters'. Under "
     "intersystems-irispython 5.4.0 the TCK unwind area passes 14/14 (driver540-tck-unwind-1) against 13/14 on 5.3.2 "
     "(tck-1, tck-unwind-rerun-1), and the 7 gated e2e files holding these and the Decimal cases pass 138/138 under 5.4.0 (gated-540-1) against 19 failures under 5.3.2 right after (gated-532-1)."),
    ("rrf-score-string", "product-defect (driver 5.3.2 from the pin's uv.lock)", r"test_460_r284_retrieve_rrf_score_e2e",
     r"\('ret1', '\.0",
     "tests/e2e/test_460_r284_retrieve_rrf_score_e2e.py asserts the retrieve() rrf_score is a float with the hand-worked "
     "value; it comes back as the text '.032522474881015332737' (a VARCHAR-typed column decoded as str). Same family "
     "as decimal-score (numeric result columns not typed as float). Driver A/B: passes under 5.4.0 (gated-rag-540-1, "
     "2/2) and fails under 5.3.2 right after (gated-rag-532-1, 0/2)."),
    ("readonly-worktree", "harness", r"test_demo_pages", r"collection failure|Read-only file system",
     "unit-1 only: the audit worktree is read-only for this lane and FastHTML writes .sesskey into the cwd at import; "
     "fixed by running every suite from the clean writable clone (unit-3)."),
    ("arno-lib-unrecorded", "environment", r"test_236_bfs_size_gate", r"the scratch namespace has no library recorded",
     "The native case needs ^ArnoAccel(\"lib_path\") copied from USER into the scratch namespace "
     "(tests/conftest.py:1486-1489); no Arno library is deployed on this container, so none is recorded. Seen only in a "
     "licence-degraded, non-decisive run."),
    ("embedded-python-deps-236", "environment", r"test_cypher_engine_objectscript", r"No module named 'pydantic'",
     "As embedded-python-deps: the container's embedded Python has no pydantic. Seen only in a licence-degraded run."),
    ("kgtxt-prefix", "intermittent", r"test_kg_txt_e2e", r"kg_TXT did not return cancer doc",
     "Test-side: cancer_docs = [d for d in doc_ids if 'd1' in d or 'd4' in d] (tests/integration/"
     "test_kg_txt_e2e.py:70) matches the random hex prefix too (kgtxt_608d49_d2 contains 'd4'), so a non-cancer doc "
     "is expected whenever uuid4().hex[:6] contains 'd1' or 'd4' (about 4% of runs: 5 positions x 2 patterns / 256)."),
]


def match(node, msg):
    for rid, cat, nre, mre, why in RULES:
        if re.search(nre, node) and re.search(mre, msg, re.S):
            return rid, cat
    return None, None


def triage(prefix):
    a = aggregate(prefix)
    out = {}
    unmatched = []
    for kind in ("failures", "errors"):
        for node, msg, full in a[kind]:
            rid, cat = match(node, full)
            if rid is None:
                unmatched.append((kind, node, msg))
            else:
                out.setdefault(rid, {"category": cat, "count": 0, "nodes": []})
                out[rid]["count"] += 1
                out[rid]["nodes"].append(node)
    return a, out, unmatched


if __name__ == "__main__":
    for p in sys.argv[1:]:
        a, out, un = triage(p)
        print(f"== {p} {a['counts']}")
        for rid, v in out.items():
            print(f"  {rid:20} {v['category']:30} {v['count']}")
        for kind, node, msg in un:
            print(f"  UNMATCHED {kind} {node} :: {msg[:200]}")
