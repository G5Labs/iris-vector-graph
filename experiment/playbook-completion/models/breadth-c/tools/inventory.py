#!/usr/bin/env python3
"""Mechanical entry-point inventory of the product at the pin, with module ownership from the Scope lines.

    python experiment/playbook-completion/models/breadth-c/tools/inventory.py [--out models/breadth-c/inventory.json]

Reads only files tracked at the pin (git ls-tree 3eaa79cf), never the working tree's untracked files. Extracts:
  py-api        public functions and public methods of public classes (AST), incl. the engine's mixin methods
  os-method     ObjectScript ClassMethod / Method in iris_src/src and other .cls files, with SqlProc / SqlName flags
  http-route    FastAPI/Starlette decorators (@app.get, @router.post, @app.websocket), include_router prefixes,
                and %CSP.REST UrlMap routes
  graphql-field strawberry @field / @mutation methods
  bolt-message  TAG_* message handlers in bolt_server.py
  cli-command   click commands and groups in cli.py
  task          %SYS.Task.Definition subclasses (background jobs) and %SYS.Task creators
  sql-routine   CREATE PROCEDURE / FUNCTION in .sql files
  deploy        compose services, Dockerfiles, shell installers, pyproject console scripts, __main__ blocks

Ownership comes from RULES, a transcription of each module's Scope line (experiment/playbook-uplift/ontology/NN-*.md,
"Scope:"). A rule names a path (glob) and optionally the symbols it covers. An entry point whose file matches no rule,
or whose symbol is excluded from every rule on its file, is UNOWNED. Coverage of an owned entry point by its module's
statements is lexical: the entry point's name (method name, route path, command name) appears as a token in the module's
ontology file. Lexical coverage is a screening signal; every "uncovered" item is listed for review, not counted as a
defect by itself.
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

PIN = "3eaa79cf77d3e0a879b2cced634cf2729d81499e"
REPO = Path(__file__).resolve().parents[5]
ONT = REPO / "experiment" / "playbook-uplift" / "ontology"

# ---------------------------------------------------------------------------------------------------------------
# Ownership rules transcribed from the Scope lines. (module, glob, include-symbols or None for whole file,
# exclude-symbols). Symbols are bare method/function names (or "Class.Method" for ObjectScript, "/route" for routes).
# ---------------------------------------------------------------------------------------------------------------
SCHEMA_PY_06 = {"kg_KNN_VEC", "_kg_knn_vec_sql", "knn_vec"}
ENGINE_SCHEMA_01 = {"initialize_schema", "is_ready"}
ENGINE_SCHEMA_04 = {"sync", "rebuild_kg", "rebuild_nkg", "backfill_degp"}
ENGINE_SCHEMA_06 = {"get_embedding_identity", "set_embedding_identity", "adopt_embedding_identities",
                    "enforce_embedding_identity", "reconcile_recorded_dimensions", "embedding_inventory",
                    "list_quarantine", "place_quarantined", "routed_table_ddl"}
ENGINE_SCHEMA_15 = {"reify_edge", "get_reifications", "delete_reification"}
VECTOR_07 = {"bm25_build", "bm25_search", "bm25_insert", "bm25_delete", "bm25_upgrade", "bm25_drop", "bm25_info",
             "kg_TXT", "kg_RRF_FUSE"}
NODES_EDGES_12 = {"erase_graph", "delete_nodes_by_prefix"}
NODES_EDGES_04 = {"bulk_delete_adjacency"}
SNAPSHOT_18 = {"save_snapshot", "snapshot_info", "restore_snapshot"}
SNAPSHOT_NOT_18 = {"import_rdf", "load_networkx", "load_obo", "import_graph_ndjson", "export_graph_ndjson"}
LEDGER_CLIENT_11 = {"enable", "disable", "set_strict", "meta", "head", "commit", "history", "stats"}
LEDGER_CLIENT_13 = {"redact", "redaction_in_progress"}
LEDGER_CLIENT_14 = {"verify", "records", "iter_records", "record", "canonical_records", "revision_records",
                    "reconstruct", "diff", "export"}
ADMIN_02 = {"set_multigraph", "is_multigraph"}
ADMIN_04 = {"verify_sync", "verify_graph"}

RULES = [
    # 01 install and schema
    ("01", "iris_vector_graph/schema_name.py", None, set()),
    ("01", "iris_vector_graph/_engine/schema.py", ENGINE_SCHEMA_01, set()),
    ("01", "iris_vector_graph/schema.py", None, SCHEMA_PY_06 | {"kg_TXT", "kg_RRF_FUSE"}),
    ("01", "iris_vector_graph/_engine/class_deploy.py", None, set()),
    ("01", "iris_vector_graph/routine_record.py", None, set()),
    ("01", "iris_vector_graph/legacy_manifest.py", None, set()),
    ("01", "iris_vector_graph/legacy_bodies.py", None, set()),
    ("01", "iris_vector_graph/legacy_text.py", None, set()),
    ("01", "iris_vector_graph/_engine/legacy.py", None, set()),
    ("01", "iris_vector_graph/migrations/__init__.py", None, set()),
    ("01", "iris_vector_graph/migrations/_commit.py", None, set()),
    ("01", "iris_vector_graph/migrations/statements.py", None, set()),
    ("01", "iris_vector_graph/migrations/upgrade.py", None, set()),
    ("01", "sql/*", None, set()),
    ("01", "sql/*/*", None, set()),
    ("01", "iris_src/src/Graph/KG/SqlPrivilege.cls", None, set()),
    ("01", "iris_src/src/Graph/KG/SqlProcs.cls", None, set()),
    # 02 graph identity
    ("02", "iris_src/src/Graph/KG/GraphKey.cls", None, set()),
    ("02", "iris_src/src/Graph/KG/GraphMode.cls", None, set()),
    ("02", "iris_vector_graph/_validate.py", None, set()),
    ("02", "iris_vector_graph/engine.py", {"_GraphSubEngine", "namespace"}, set()),
    ("02", "iris_vector_graph/_engine/admin.py", ADMIN_02, set()),
    # 03 direct writes
    ("03", "iris_vector_graph/_engine/nodes_edges.py", None, NODES_EDGES_12 | {"drop_graph"}),
    ("03", "iris_src/src/Graph/KG/PropWrite.cls", None, set()),
    ("03", "iris_src/src/Graph/KG/Txn.cls", None, set()),
    ("03", "iris_src/src/Graph/KG/LabelIndex.cls", None, set()),
    ("03", "iris_vector_graph/_write_txn.py", None, set()),
    ("03", "iris_vector_graph/bulk_loader.py", None, set()),
    ("03", "iris_vector_graph/prop_values.py", None, set()),
    ("03", "iris_vector_graph/_dictionary.py", None, set()),
    ("03", "iris_vector_graph/_collation.py", None, set()),
    ("03", "iris_vector_graph/_batch_check.py", None, set()),
    ("03", "iris_vector_graph/engine.py", {"_GraphSubEngine"}, set()),
    # 04 adjacency
    *[("04", f"iris_src/src/Graph/KG/{c}.cls", None, set()) for c in
      ["Adjacency", "AdjIndex", "Adj", "EdgeScan", "Edgeless", "GraphIndex", "TraversalBuild", "GraphVerify",
       "AlgoCache"]],
    ("04", "iris_vector_graph/_edgeless.py", None, set()),
    ("04", "iris_vector_graph/freshness.py", None, set()),
    ("04", "iris_vector_graph/algo_cache.py", None, set()),
    ("04", "iris_vector_graph/_engine/schema.py", ENGINE_SCHEMA_04, set()),
    ("04", "iris_vector_graph/_engine/admin.py", ADMIN_04, set()),
    ("04", "iris_vector_graph/_engine/nodes_edges.py", NODES_EDGES_04, set()),
    ("04", "iris_vector_graph/stores/iris_sql_store.py", {"_cached_algorithm"}, set()),
    ("04", "iris_vector_graph/engine.py", {"sync", "rebuild_kg", "rebuild_nkg"}, set()),
    # 05 temporal
    *[("05", f"iris_src/src/Graph/KG/{c}.cls", None, set()) for c in
      ["TemporalIndex", "TemporalIndexMS", "TemporalPolicy", "TemporalWindow"]],
    ("05", "iris_vector_graph/_engine/temporal.py", None, set()),
    ("05", "iris_vector_graph/_engine/temporal_window.py", None, set()),
    ("05", "iris_vector_graph/_engine/temporal_only_warning.py", None, set()),
    ("05", "iris_vector_graph/_tz.py", None, set()),
    ("05", "iris_vector_graph/migrations/temporal_structural_rows.py", None, set()),
    ("05", "iris_vector_graph/engine.py", {"_TemporalSubEngine"}, set()),
    # 06 vectors
    ("06", "iris_vector_graph/embedding_identity.py", None, set()),
    ("06", "iris_vector_graph/embed_selector.py", None, set()),
    ("06", "iris_vector_graph/_engine/vector.py", None, VECTOR_07),
    ("06", "iris_vector_graph/_engine/embeddings.py", None, set()),
    ("06", "iris_vector_graph/vector_utils.py", None, set()),
    ("06", "iris_vector_graph/_widths.py", None, set()),
    ("06", "iris_vector_graph/migrations/graph_scoped_embeddings.py", None, set()),
    ("06", "iris_vector_graph/migrations/docs_and_edge_vectors.py", None, set()),
    ("06", "iris_vector_graph/migrations/kg_node_stores.py", None, set()),
    *[("06", f"iris_src/src/Graph/KG/{c}.cls", None, set()) for c in
      ["IVFIndex", "VecIndex", "PLAIDSearch", "EmbedQueue", "EmbedQueueTask"]],
    ("06", "iris_vector_graph/_engine/schema.py", ENGINE_SCHEMA_06, set()),
    ("06", "iris_vector_graph/schema.py", SCHEMA_PY_06, set()),
    ("06", "iris_vector_graph/engine.py", {"execute_knn_vec"}, set()),
    # 07 text search
    ("07", "iris_src/src/Graph/KG/BM25Index.cls", None, set()),
    ("07", "iris_vector_graph/text_search.py", None, set()),
    ("07", "iris_vector_graph/fusion.py", None, set()),
    ("07", "iris_vector_graph/_engine/vector.py", VECTOR_07, set()),
    ("07", "iris_vector_graph/schema.py", {"kg_TXT", "kg_RRF_FUSE"}, set()),
    ("07", "iris_vector_graph/_engine/algorithms.py", {"kg_RERANK"}, set()),
    ("07", "iris_src/src/Graph/KG/Service.cls", {"HybridSearch", "/hybridSearch"}, set()),
    ("07", "iris_src/src/Graph/KG/PyOps.cls", {"HybridSearch"}, set()),
    # 08 Cypher SQL
    ("08", "iris_vector_graph/cypher/*", None, {"native_plan.py", "native_route.py", "native_shadow.py"}),
    ("08", "iris_vector_graph/cypher/*/*", None, set()),
    ("08", "iris_vector_graph/cypher/*/*/*", None, set()),
    ("08", "iris_vector_graph/_engine/query.py", None, {"_try_native", "_run_native_plan", "_shadow_compare",
                                                         "_routed_sql"}),
    ("08", "iris_vector_graph/stores/iris_sql_store.py", {"execute_transaction"}, set()),
    ("08", "iris_src/src/Graph/KG/CypherFn.cls", None, set()),
    ("08", "iris_src/src/IVG/Percentile.cls", None, set()),
    ("08", "iris_vector_graph/operators.py", None, set()),
    ("08", "sql/operators.sql", None, set()),
    ("08", "iris_vector_graph/engine.py", {"_CypherSubEngine", "execute_cypher", "execute_bfs"}, set()),
    # 09 native executor
    *[("09", f"iris_src/src/Graph/KG/Cypher/{c}.cls", None, set()) for c in ["Exec", "Gen", "Props", "SortKey"]],
    ("09", "iris_src/src/IVG/CypherEngine.cls", None, set()),
    ("09", "iris_vector_graph/cypher/native_plan.py", None, set()),
    ("09", "iris_vector_graph/cypher/native_route.py", None, set()),
    ("09", "iris_vector_graph/cypher/native_shadow.py", None, set()),
    ("09", "iris_vector_graph/_engine/query.py", {"execute_cypher", "_try_native", "_run_native_plan",
                                                   "_shadow_compare", "_routed_sql"}, set()),
    # 10 algorithms
    ("10", "iris_vector_graph/_engine/algorithms.py", None, {"kg_RERANK"}),
    *[("10", f"iris_src/src/Graph/KG/{c}.cls", None, set()) for c in
      ["Algorithms", "PageRank", "PageRankEmbedded", "Centrality", "Communities", "Subgraph", "Traversal",
       "TraversalBFS", "TraversalKHop", "TraversalPaths", "VarLength", "NKGAccel", "NKGAccelAdjacency",
       "NKGAccelCentrality", "NKGAccelLoader", "NKGAccelTraversal", "ArnoAccel", "AlgoCache"]],
    ("10", "iris_vector_graph/stores/arno_bridge.py", None, set()),
    ("10", "iris_vector_graph/arno_readers.py", None, set()),
    ("10", "iris_vector_graph/_arno_gate.py", None, set()),
    ("10", "iris_vector_graph/algo_cache.py", None, set()),
    ("10", "iris_vector_graph/engine.py", {"_AlgorithmsSubEngine"}, set()),
    # 11 ledger
    ("11", "iris_src/src/Graph/KG/Ledger.cls", None, {"Records", "CanonicalRecord"}),
    *[("11", f"iris_src/src/Graph/KG/{c}.cls", None, set()) for c in
      ["LedgerApply", "LedgerGenesis", "LedgerStats", "LedgerRevision"]],
    ("11", "iris_vector_graph/ledger/changeset.py", None, set()),
    ("11", "iris_vector_graph/ledger/client.py", LEDGER_CLIENT_11 | {"GraphLedger"}, set()),
    ("11", "iris_vector_graph/ledger/guard.py", None, set()),
    ("11", "iris_vector_graph/ledger/errors.py", None, set()),
    ("11", "iris_vector_graph/ledger/__init__.py", None, set()),
    ("11", "iris_vector_graph/_engine/ledger.py", None, set()),
    # 12 erasure
    ("12", "iris_src/src/Graph/KG/Eraser.cls", None, set()),
    ("12", "iris_src/src/Graph/KG/GraphStores.cls", None, set()),
    ("12", "iris_vector_graph/_engine/nodes_edges.py", NODES_EDGES_12, set()),
    # 13 redaction
    ("13", "iris_src/src/Graph/KG/LedgerRedact.cls", None, set()),
    ("13", "iris_vector_graph/ledger/client.py", LEDGER_CLIENT_13, set()),
    # 14 replay
    ("14", "iris_vector_graph/ledger/replay.py", None, set()),
    ("14", "iris_vector_graph/ledger/export.py", None, set()),
    ("14", "iris_vector_graph/ledger/client.py", LEDGER_CLIENT_14, set()),
    ("14", "iris_src/src/Graph/KG/Ledger.cls", {"Records", "CanonicalRecord"}, set()),
    # 15 integrations
    ("15", "iris_src/src/Graph/KG/FHIRGraph.cls", None, set()),
    ("15", "iris_src/src/Graph/KG/FHIRGraphSyncTask.cls", None, set()),
    ("15", "iris_vector_graph/_engine/fhir_graph.py", None, set()),
    ("15", "iris_vector_graph/_engine/fhir.py", None, set()),
    ("15", "iris_vector_graph/fhir_bridge.py", None, set()),
    ("15", "iris_vector_graph/fhir_links.py", None, set()),
    ("15", "iris_vector_graph/_engine/rdf_export.py", None, set()),
    ("15", "iris_vector_graph/_engine/_rdf_utils.py", None, set()),
    ("15", "iris_vector_graph/_engine/shacl.py", None, set()),
    ("15", "iris_vector_graph/_engine/prov.py", None, set()),
    ("15", "sql/fhir_bridges.sql", None, set()),
    ("15", "sql/rdf_reifications.sql", None, set()),
    ("15", "iris_vector_graph/_engine/schema.py", ENGINE_SCHEMA_15, set()),
    ("15", "iris_vector_graph/cli.py", {"fhir", "register", "rebuild", "sync", "status", "links", "schedule"}, set()),
    # 16 interfaces
    ("16", "api/*", None, set()),
    ("16", "api/*/*", None, set()),
    ("16", "api/*/*/*", None, set()),
    ("16", "iris_vector_graph/gql/*", None, set()),
    ("16", "iris_vector_graph/cypher_api.py", None, set()),
    ("16", "iris_vector_graph/bolt_server.py", None, set()),
    ("16", "iris_vector_graph/api_auth.py", None, set()),
    ("16", "iris_vector_graph/_api_key.py", None, set()),
    ("16", "iris_vector_graph/security.py", None, set()),
    ("16", "iris_vector_graph/routing.py", None, set()),
    ("16", "iris_src/src/Graph/KG/Service.cls", None, set()),
    ("16", "iris_src/src/Graph/KG/MCPService.cls", None, set()),
    ("16", "iris_src/src/Graph/KG/MCPToolSet.cls", None, set()),
    ("16", "iris_src/src/Graph/KG/MCPTools.cls", None, set()),
    ("16", "src/iris_demo_server/*", None, set()),
    ("16", "src/iris_demo_server/*/*", None, set()),
    ("16", "src/iris_demo_server/*/*/*", None, set()),
    ("16", "src/iris_fraud_server/*", None, set()),
    ("16", "examples/domains/biomedical/resolver.py", None, set()),  # cited by API-B6.7 as the sample API's resolver
    # 17 operations
    *[("17", f"iris_vector_graph/{f}", None, set()) for f in
      ["cli.py", "status.py", "capabilities.py", "_engine/admin.py", "host.py", "embedded.py", "_iris_compat.py",
       "stores/iris_sql_store.py", "stores/lazy_kg.py", "store_protocol.py", "sdk.py", "index_config.py",
       "index_protocol.py", "errors.py", "exceptions.py", "result.py", "dbapi_utils.py", "utils.py",
       "constants.py", "models.py"]],
    *[("17", f"iris_src/src/Graph/KG/{c}.cls", None, set()) for c in ["Meta", "PyOps", "SQL", "JsonKeys"]],
    ("17", "docker-compose.yml", None, set()),
    ("17", "docker/*", None, set()),
    ("17", "docker/*/*", None, set()),
    ("17", "deploy/*", None, set()),
    ("17", "deploy/*/*", None, set()),
    ("17", "deploy/*/*/*", None, set()),
    ("17", "pyproject.toml", None, set()),
    ("17", "uv.lock", None, set()),
    # 18 snapshot
    ("18", "iris_src/src/Graph/KG/Snapshot.cls", None, set()),
    ("18", "iris_vector_graph/_engine/snapshot.py", None, SNAPSHOT_NOT_18),
    ("18", "iris_vector_graph/cypher_api.py", {"/admin/snapshot", "admin_snapshot"}, set()),
]

# Files whose content is not executable product code (data, docs, vendored assets) are listed separately.
NON_CODE = re.compile(r"\.(md|txt|json|svg|png|ico|jpg|gif|mp4|woff2?|ttf|eot|css|html|http|cypher|lock|typed)$")
PRODUCT_ROOTS = ("iris_vector_graph/", "iris_src/", "api/", "sql/", "src/", "deploy/", "docker/", "examples/",
                 "scripts/", "config/")
PRODUCT_FILES = ("docker-compose.yml", "pyproject.toml", "uv.lock")


def tracked_files():
    out = subprocess.run(["git", "ls-tree", "-r", "--name-only", PIN], cwd=REPO, capture_output=True, text=True,
                         check=True).stdout.split("\n")
    return [f for f in out if f and (f.startswith(PRODUCT_ROOTS) or f in PRODUCT_FILES)]


def pin_text(path: str) -> str:
    return subprocess.run(["git", "show", f"{PIN}:{path}"], cwd=REPO, capture_output=True, text=True,
                          errors="replace", check=True).stdout


def owners(path: str, symbol: str | None, container: str | None = None):
    """Modules owning (path, symbol). `container` is the enclosing class (for symbol rules naming a class)."""
    found = []
    for mod, glob, inc, exc in RULES:
        if not fnmatch.fnmatchcase(path, glob):
            continue
        base = path.rsplit("/", 1)[-1]
        if base in exc:
            continue
        if symbol is None:
            if inc is None:
                found.append(mod)
            continue
        names = {symbol, container} - {None}
        if inc is not None and not (names & inc):
            continue
        if names & exc:
            continue
        found.append(mod)
    return sorted(set(found))


def file_owners(path: str):
    """Modules owning a file wholly or partly."""
    mods = set()
    for mod, glob, inc, exc in RULES:
        if fnmatch.fnmatchcase(path, glob) and path.rsplit("/", 1)[-1] not in exc:
            mods.add(mod)
    return sorted(mods)


# ------------------------------------------------------------------ extractors
def py_entries(path, text):
    out = []
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        return [dict(kind="parse-error", name=str(e), file=path, line=0)]
    is_main = False
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            out.append(dict(kind="py-api", name=node.name, container=None, file=path, line=node.lineno,
                            end=node.end_lineno))
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_") or (
                isinstance(node, ast.ClassDef) and node.name.endswith("SubEngine")):
            for m in node.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and not m.name.startswith("_"):
                    out.append(dict(kind="py-api", name=m.name, container=node.name, file=path, line=m.lineno,
                                    end=m.end_lineno))
        elif isinstance(node, ast.If) and "__main__" in ast.unparse(node.test):
            is_main = True
            out.append(dict(kind="deploy", name="__main__", container=None, file=path, line=node.lineno,
                            end=node.end_lineno))
    # decorators: routes, graphql fields, click commands (anywhere, including nested defs)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for d in node.decorator_list:
            src = ast.unparse(d)
            m = re.match(r"(\w+(?:\.\w+)*)\.(get|post|put|delete|patch|websocket|api_route|route)\((['\"])(.*?)\3", src)
            if m and m.group(1).split(".")[-1] in ("app", "router", "api", "_app"):
                out.append(dict(kind="http-route", name=f"{m.group(2).upper()} {m.group(4)}", handler=node.name,
                                container=None, file=path, line=node.lineno, end=node.end_lineno))
                continue
            if re.match(r"strawberry\.(field|mutation)", src):
                out.append(dict(kind="graphql-field", name=node.name, container=None, file=path, line=node.lineno,
                                end=node.end_lineno))
                continue
            m = re.match(r"(\w+)\.(command|group)\((?:['\"]([\w-]+)['\"])?", src)
            if m and path.endswith("cli.py"):
                out.append(dict(kind="cli-command", name=(m.group(1) + " " + (m.group(3) or node.name)),
                                handler=node.name, container=None, file=path, line=node.lineno, end=node.end_lineno))
            if re.match(r"click\.group", src) and path.endswith("cli.py"):
                out.append(dict(kind="cli-command", name="ivg (group)", handler=node.name, container=None,
                                file=path, line=node.lineno, end=node.end_lineno))
    # include_router prefixes
    for i, line in enumerate(text.split("\n"), 1):
        m = re.search(r"include_router\((\w+)(?:,\s*prefix=['\"]([^'\"]+)['\"])?", line)
        if m:
            out.append(dict(kind="http-route", name=f"MOUNT {m.group(2) or '/'} -> {m.group(1)}", container=None,
                            file=path, line=i, end=i))
    if path.endswith("bolt_server.py"):
        for i, line in enumerate(text.split("\n"), 1):
            m = re.search(r"(?:el)?if tag == (TAG_[A-Z]+)", line)
            if m:
                out.append(dict(kind="bolt-message", name=m.group(1), container=None, file=path, line=i, end=i))
    return out


CLS_HDR = re.compile(r"^Class\s+([\w.%]+)(?:\s+Extends\s+(.+?))?(?:\s*\[(.*)\])?\s*$")
METH = re.compile(r"^(ClassMethod|Method|Query)\s+(%?\w+)\s*\((.*?)$")


def cls_entries(path, text):
    out = []
    lines = text.split("\n")
    cname, extends = None, ""
    for i, line in enumerate(lines, 1):
        m = CLS_HDR.match(line)
        if m:
            cname, extends = m.group(1), (m.group(2) or "")
            if "%SYS.Task.Definition" in extends:
                out.append(dict(kind="task", name=f"{cname} (Extends %SYS.Task.Definition)", container=cname,
                                file=path, line=i, end=i))
            continue
        m = METH.match(line)
        if m and cname:
            kind, name = m.group(1), m.group(2)
            # keyword block is on this line after the closing paren (single-line signatures in this repo)
            kw = line[line.rfind(")"):] if ")" in line else ""
            j = i
            while "{" not in lines[j - 1] and j < len(lines) and j - i < 6:
                j += 1
                kw += lines[j - 1]
            flags = []
            for f in ("SqlProc", "Private", "Internal", "Final", "Language = python", "ReturnResultsets"):
                if f in kw:
                    flags.append(f)
            sqln = re.search(r"SqlName\s*=\s*(\w+)", kw)
            out.append(dict(kind="os-method", name=f"{cname}.{name}", method=name, container=cname,
                            method_kind=kind, flags=flags, sql_name=(sqln.group(1) if sqln else None),
                            file=path, line=i, end=i))
    for i, line in enumerate(lines, 1):
        m = re.search(r'<Route Url="([^"]+)" Method="(\w+)" Call="(\w+)"', line)
        if m:
            out.append(dict(kind="http-route", name=f"{m.group(2)} {m.group(1)}", handler=m.group(3),
                            container=cname, file=path, line=i, end=i))
        if "##class(%SYS.Task).%New()" in line:
            out.append(dict(kind="task", name=f"{cname} creates a %SYS.Task", container=cname, file=path, line=i,
                            end=i))
    return out


def sql_entries(path, text):
    out = []
    for i, line in enumerate(text.split("\n"), 1):
        m = re.search(r"CREATE\s+(?:OR\s+REPLACE\s+)?(PROCEDURE|FUNCTION|TABLE|VIEW|INDEX)\s+([\w.\"]+)", line, re.I)
        if m:
            out.append(dict(kind="sql-routine" if m.group(1).upper() in ("PROCEDURE", "FUNCTION") else "sql-ddl",
                            name=f"{m.group(1).upper()} {m.group(2)}", container=None, file=path, line=i, end=i))
    return out


def deploy_entries(path, text):
    out = []
    if path.endswith((".yml", ".yaml")) and "services:" in text:
        insvc = False
        for i, line in enumerate(text.split("\n"), 1):
            if line.startswith("services:"):
                insvc = True
                continue
            if insvc and re.match(r"^\S", line):
                insvc = False
            m = re.match(r"^  ([\w-]+):\s*$", line)
            if insvc and m:
                out.append(dict(kind="deploy", name=f"compose service {m.group(1)}", container=None, file=path,
                                line=i, end=i))
    elif path.endswith("Dockerfile") or path.endswith(".sh") or path.endswith(".cpf") or path.endswith(".conf"):
        out.append(dict(kind="deploy", name=path.rsplit("/", 1)[-1], container=None, file=path, line=1, end=1))
    elif path == "pyproject.toml":
        sect = False
        for i, line in enumerate(text.split("\n"), 1):
            if line.strip() == "[project.scripts]":
                sect = True
                continue
            if sect and line.startswith("["):
                sect = False
            m = re.match(r'^([\w-]+)\s*=\s*"([\w.:]+)"', line)
            if sect and m:
                out.append(dict(kind="deploy", name=f"console script {m.group(1)} -> {m.group(2)}", container=None,
                                file=path, line=i, end=i))
    return out


def ontology_text(mod: str) -> str:
    f = next(ONT.glob(f"{mod}-*.md"))
    return f.read_text()


def token_in(text: str, name: str) -> bool:
    return re.search(r"(?<![\w/])" + re.escape(name) + r"(?![\w])", text) is not None


def coverage_key(e):
    """Names to look for in the ontology for this entry point."""
    k = e["kind"]
    if k == "os-method":
        keys = [e["name"], e["method"]]
        if e.get("sql_name"):
            keys.append(e["sql_name"])
        return keys
    if k == "http-route":
        path = e["name"].split(" ", 1)[1].split(" ->")[0]
        return [path] + ([e["handler"]] if e.get("handler") else [])
    if k == "cli-command":
        return [e["name"].split(" ", 1)[-1], e.get("handler", "")]
    if k == "bolt-message":
        return [e["name"], e["name"].replace("TAG_", "")]
    if k == "task":
        return [e["container"]]
    if k == "deploy":
        return [e["file"].rsplit("/", 1)[-1], e["name"].split(" ")[-1], e["file"]]
    return [e["name"]] + ([f"{e['container']}.{e['name']}"] if e.get("container") else [])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "experiment/playbook-completion/models/breadth-c/inventory.json"))
    a = ap.parse_args()
    files = tracked_files()
    entries = []
    file_rows = []
    for f in files:
        if "browser_static/" in f:
            continue
        code = not NON_CODE.search(f)
        fo = file_owners(f)
        file_rows.append(dict(file=f, code=code, owners=fo))
        if not code:
            continue
        try:
            text = pin_text(f)
        except subprocess.CalledProcessError:
            continue
        if f.endswith(".py"):
            es = py_entries(f, text)
        elif f.endswith(".cls") or f.endswith(".cls.txt"):
            es = cls_entries(f, text)
        elif f.endswith(".sql"):
            es = sql_entries(f, text)
        else:
            es = deploy_entries(f, text)
        for e in es:
            sym = e.get("method") or e.get("handler") or e["name"]
            if e["kind"] == "http-route":
                sym_alt = e["name"].split(" ", 1)[1]
                o = sorted(set(owners(f, sym, e.get("container"))) | set(owners(f, sym_alt, e.get("container"))))
            else:
                o = owners(f, sym, e.get("container"))
            if not o and e["kind"] == "http-route" and e.get("handler"):
                o = owners(f, e["handler"])
            e["owners"] = o
            entries.append(e)
    # browser_static is one vendored asset bundle
    file_rows.append(dict(file="iris_vector_graph/browser_static/** (vendored Neo4j Browser bundle)", code=False,
                          owners=file_owners("iris_vector_graph/browser_static/index.html")))

    # reconciliation for modules 15-18 (lexical screening)
    recon = {}
    for mod in ["15", "16", "17", "18"]:
        txt = ontology_text(mod)
        mine = [e for e in entries if mod in e["owners"]]
        covered, uncovered = [], []
        for e in mine:
            keys = [k for k in coverage_key(e) if k]
            (covered if any(token_in(txt, k) for k in keys) else uncovered).append(e)
        recon[mod] = dict(entry_points=len(mine), lexically_covered=len(covered),
                          uncovered=[dict(kind=e["kind"], name=e["name"], file=e["file"], line=e["line"])
                                     for e in uncovered],
                          by_kind={k: sum(1 for e in mine if e["kind"] == k) for k in sorted({e["kind"] for e in mine})})
    unowned_entries = [e for e in entries if not e["owners"]]
    unowned_files = [r for r in file_rows if r["code"] and not r["owners"]]
    by_root = defaultdict(int)
    for r in unowned_files:
        by_root[r["file"].split("/")[0]] += 1
    summary = dict(
        pin=PIN, files=len(file_rows), code_files=sum(1 for r in file_rows if r["code"]),
        entry_points=len(entries),
        by_kind={k: sum(1 for e in entries if e["kind"] == k) for k in sorted({e["kind"] for e in entries})},
        by_module={m: sum(1 for e in entries if m in e["owners"]) for m in
                   sorted({m for e in entries for m in e["owners"]})},
        unowned_entry_points=len(unowned_entries), unowned_code_files=len(unowned_files),
        unowned_code_files_by_root=dict(by_root),
    )
    out = dict(summary=summary, reconciliation=recon,
               unowned_files=[r["file"] for r in unowned_files],
               unowned_entry_points=[dict(kind=e["kind"], name=e["name"], container=e.get("container"),
                                          file=e["file"], line=e["line"]) for e in unowned_entries],
               files=file_rows, entries=entries)
    Path(a.out).write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=1))
    for mod, r in recon.items():
        print(mod, r["entry_points"], "covered", r["lexically_covered"], "uncovered", len(r["uncovered"]), r["by_kind"])


if __name__ == "__main__":
    main()
