#!/usr/bin/env python3
"""Gate 3.4-storage-order for modules 01-06: the reviewed disposition of every site of the coordinator's scan
($RUN_DIR/checks/storage-order.json) in these modules' files, plus sites the scan missed (found by grep for
TOP/LIMIT/FETCH FIRST and truncating $Order loops in the modules' scope files; see storage_order_sites.py and
$RUN_DIR/breadth-a/storage-order/grep-missed.log).

Each disposition below was read at the pin (path:line cited). Dispositions:
  unique-key       the WHERE pins a unique/primary key, so at most one row qualifies
  existence-only   the caller only tests for a row, or any qualifying row gives the same answer (cited why)
  false-positive   an ORDER BY is in the same statement (concatenated literal) or the prefix is not a result prefix
  order-dependent  which row(s) the caller gets depends on scan order
  collation-ordered (missed_by_scan only) an ObjectScript $Order traversal: deterministic subscript order
Tie note: a TOP k ... ORDER BY score DESC with no secondary key resolves ties at the k-th place in scan order; such
sites are false-positives of the scan (they do order) and carry tie_break "scan order" so the gate sees it.

    python experiment/playbook-completion/models/breadth-a/tools/storage_order_dispositions.py
"""
from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "storage-order"
RUN = Path(os.environ["RUN_DIR"])
TIE = "scan order (ORDER BY score only; equal scores at the k-th place are cut in storage order)"


def S(file, line, function, disposition, key_or_reason, cites, finding_candidate=False, title="", severity="",
      **extra):
    d = {"file": file, "line": line, "function": function, "disposition": disposition,
         "key_or_reason": key_or_reason, "cites": cites, "finding_candidate": finding_candidate,
         "title": title, "severity": severity}
    d.update(extra)
    return d


SITES = {
    "01": [
        S("iris_vector_graph/_engine/admin.py", 706, "AdminMixin._missing_routines", "false-positive",
          "docstring text naming the probe, not SQL", ["iris_vector_graph/_engine/admin.py:706-713"],
          owner_note="status().missing_routines is reported by module 17's status; the routines are setup's (INS-B5.7)"),
        S("iris_vector_graph/_engine/admin.py", 733, "AdminMixin._missing_routines", "false-positive",
          "SELECT TOP 0 <schema>.<name>(NULL): a Prepare probe that returns no rows; only its SQLCODE is read",
          ["iris_vector_graph/_engine/admin.py:731-743"]),
        S("iris_vector_graph/_engine/schema.py", 2360, "SchemaMixin._plan_setup", "existence-only",
          "kg_built = ... cursor.fetchone() is not None", ["iris_vector_graph/_engine/schema.py:2360-2361"],
          aside="reads Graph_KG.rdf_edges literally while the same function plans for `schema` (2350); a namespace "
                "whose IVG Schema is not Graph_KG is probed in the wrong schema (spec 262 FR-007; not storage order)"),
        S("iris_vector_graph/_engine/schema.py", 2791, "SchemaMixin.get_schema_visualization", "order-dependent",
          "TOP 1 rl.s WHERE label = ?: the sampled node of a label is the first in scan order",
          ["iris_vector_graph/_engine/schema.py:2788-2793", "iris_vector_graph/_engine/schema.py:2773-2776"],
          documented=True,
          note="Documented as a sample ('Sampled, not exact: ... one node carrying it'). The sample is graph-blind "
               "(rdf_labels/rdf_props joined by id only): finding F-0106."),
        S("iris_vector_graph/_engine/schema.py", 2800, "SchemaMixin.get_schema_visualization", "false-positive",
          'DISTINCT TOP 20 "key" ... ORDER BY "key" in the concatenated literal',
          ["iris_vector_graph/_engine/schema.py:2799-2802"]),
        S("iris_vector_graph/_engine/schema.py", 2825, "SchemaMixin.get_schema_visualization", "order-dependent",
          "TOP 1 s, o_id WHERE p = ?: the sampled edge of a predicate is the first in scan order",
          ["iris_vector_graph/_engine/schema.py:2819-2826", "iris_vector_graph/_engine/schema.py:2774-2775"],
          documented=True, note="Documented sample ('those of one edge's endpoints')."),
        S("iris_vector_graph/_engine/schema.py", 2833, "SchemaMixin.get_schema_visualization", "order-dependent",
          "TOP 1 label WHERE s = ?: for an endpoint with several labels the start label is whichever row comes "
          "first; graph-blind (no graph_id)", ["iris_vector_graph/_engine/schema.py:2832-2837"], documented=True,
          note="Inside the documented 'sampled, not exact' contract (2773-2776), which does not say which label of a "
               "multi-label endpoint is used; the graph-blind join is F-0106."),
        S("iris_vector_graph/_engine/schema.py", 2839, "SchemaMixin.get_schema_visualization", "order-dependent",
          "as 2833, for the end label", ["iris_vector_graph/_engine/schema.py:2838-2843"], documented=True,
          note="as 2833"),
        S("iris_vector_graph/schema.py", 887, "GraphSchema.ensure_adjacency_index", "existence-only",
          "chooses the log level only: logger.info if cursor.fetchone() else logger.debug",
          ["iris_vector_graph/schema.py:887-888"]),
        S("iris_vector_graph/schema.py", 933, "GraphSchema.ensure_props_value_key", "existence-only",
          "batch drain: UPDATE ... WHERE %ID IN (SELECT TOP n %ID ... WHERE val_key IS NULL AND val IS NOT NULL) "
          "repeats until a batch is short or no row qualifies, so which rows one batch takes cannot change the end "
          "state (every qualifying row is recomputed; a stalled pass stops on the rows left, whatever their order)",
          ["iris_vector_graph/schema.py:928-955"],
          note="the scan reports line 933; the TOP is on 934"),
        S("iris_vector_graph/schema.py", 1908, "GraphSchema.validate_schema", "existence-only",
          "status[table] = True when the SELECT runs; the row is not read", ["iris_vector_graph/schema.py:1904-1911"]),
    ],
    "02": [
        S("iris_vector_graph/engine.py", 624, "IRISGraphEngine._more_than_one_graph", "existence-only",
          "any first row works: its graph_id is then compared with index probes for a graph above and below it "
          "(634), so the answer (two or more graphs?) does not depend on which row came first",
          ["iris_vector_graph/engine.py:621-641"],
          note="a NULL first graph_id takes the MIN/MAX path (628-631); {g, NULL} answers False on both paths, so "
               "the answer is order-independent there too"),
        S("iris_vector_graph/engine.py", 634, "IRISGraphEngine._more_than_one_graph", "existence-only",
          "existence of a graph_id above / below the first one", ["iris_vector_graph/engine.py:633-636"]),
    ],
    "03": [
        S("iris_vector_graph/_engine/nodes_edges.py", 884, "NodesEdgesMixin.property_value_exists", "existence-only",
          "return cursor.fetchone() is not None", ["iris_vector_graph/_engine/nodes_edges.py:879-889"]),
    ],
    "04": [],
    "05": [],
    "06": [
        S("iris_vector_graph/_engine/embeddings.py", 884, "EmbeddingsMixin._probe_native_vec", "existence-only",
          "WHERE 1=0 compile probe: only whether VECTOR_COSINE prepares", ["iris_vector_graph/_engine/embeddings.py:880-896"]),
        S("iris_vector_graph/_engine/vector.py", 60, "VectorMixin._detect_stored_vector_dtype", "existence-only",
          "one stored vector to probe the column's element type, which is declared per table, so any row answers "
          "the same", ["iris_vector_graph/_engine/vector.py:56-84"]),
        S("iris_vector_graph/_engine/vector.py", 72, "VectorMixin._detect_stored_vector_dtype", "existence-only",
          "LIMIT 1 cast probe: only whether the statement runs", ["iris_vector_graph/_engine/vector.py:69-79"]),
        S("iris_vector_graph/_engine/vector.py", 377, "VectorMixin.edge_vector_search", "false-positive",
          "ORDER BY score DESC in the concatenated literal", ["iris_vector_graph/_engine/vector.py:377-383"],
          tie_break=TIE),
        S("iris_vector_graph/_engine/vector.py", 435, "VectorMixin._raise_width_mismatch", "existence-only",
          "one stored vector's width for an error message; a route's emb column declares one width",
          ["iris_vector_graph/_engine/vector.py:425-446"]),
        S("iris_vector_graph/_engine/vector.py", 569, "VectorMixin.kg_KNN_VEC", "false-positive",
          "ORDER BY score DESC in the concatenated literal", ["iris_vector_graph/_engine/vector.py:569-574"],
          tie_break=TIE),
        S("iris_vector_graph/_engine/vector.py", 578, "VectorMixin.kg_KNN_VEC", "false-positive",
          "ORDER BY score DESC in the concatenated literal", ["iris_vector_graph/_engine/vector.py:578-583"],
          tie_break=TIE),
        S("iris_vector_graph/_engine/vector.py", 587, "VectorMixin.kg_KNN_VEC", "false-positive",
          "ORDER BY score DESC in the concatenated literal", ["iris_vector_graph/_engine/vector.py:587-591"],
          tie_break=TIE),
        S("iris_vector_graph/_engine/vector.py", 595, "VectorMixin.kg_KNN_VEC", "false-positive",
          "ORDER BY score DESC in the concatenated literal", ["iris_vector_graph/_engine/vector.py:595-599"],
          tie_break=TIE),
        S("iris_vector_graph/_engine/vector.py", 661, "VectorMixin.measure_route_recall", "false-positive",
          "ORDER BY node_id in the same literal; node_id is unique per (graph_id) in a route",
          ["iris_vector_graph/_engine/vector.py:660-663"]),
        S("iris_vector_graph/_engine/vector.py", 819, "VectorMixin._kg_KNN_VEC_python_optimized", "false-positive",
          "ORDER BY score DESC in the concatenated literal", ["iris_vector_graph/_engine/vector.py:818-825"],
          tie_break=TIE),
        S("iris_vector_graph/_engine/vector.py", 829, "VectorMixin._kg_KNN_VEC_python_optimized", "false-positive",
          "ORDER BY score DESC in the concatenated literal", ["iris_vector_graph/_engine/vector.py:828-833"],
          tie_break=TIE),
        S("iris_vector_graph/_engine/vector.py", 1146, "VectorMixin.validate_vector_table", "existence-only",
          "one sampled value's length; documented as 'the length of one sampled vector', and a VECTOR column "
          "declares one width", ["iris_vector_graph/_engine/vector.py:1122-1158"], documented=True),
        S("iris_vector_graph/_engine/vector.py", 1265, "VectorMixin.vector_search", "false-positive",
          "ORDER BY score DESC in the concatenated literal", ["iris_vector_graph/_engine/vector.py:1264-1269"],
          tie_break=TIE),
        S("iris_vector_graph/vector_utils.py", 123, "VectorOptimizer.check_hnsw_availability", "false-positive",
          "ORDER BY similarity DESC in the same literal; only timing and count are used",
          ["iris_vector_graph/vector_utils.py:123-130"]),
        S("iris_vector_graph/vector_utils.py", 320, "VectorOptimizer.benchmark_vector_search", "false-positive",
          "ORDER BY similarity DESC in the same literal; only timing and count are used",
          ["iris_vector_graph/vector_utils.py:320-327"]),
        S("iris_vector_graph/vector_utils.py", 352, "VectorOptimizer.benchmark_vector_search", "existence-only",
          "any 100 rows serve the timing benchmark; the result holds only timings and min(len, k)",
          ["iris_vector_graph/vector_utils.py:345-375"]),
        S("iris_vector_graph/vector_utils.py", 455, "VectorOptimizer.get_vector_statistics", "existence-only",
          "one row's vector for 'vector_dimension'; the column declares one width",
          ["iris_vector_graph/vector_utils.py:453-462"],
          aside="len(sample_vector) is the length of the value as returned; if the driver returns the CSV text this "
                "is a character count, not a width (not storage order; unverified)"),
        S("iris_vector_graph/migrations/graph_scoped_embeddings.py", 1273, "_Migrator._measured_width",
          "order-dependent",
          "the 4.0.0 node step sizes the route tables from one stored vector when the legacy table declares no "
          "width and the registry records none; with rows of several widths, the plan's width is whichever row "
          "the scan returns first", ["iris_vector_graph/migrations/graph_scoped_embeddings.py:840-846",
                                     "iris_vector_graph/migrations/graph_scoped_embeddings.py:1268-1283"],
          finding_candidate=True, severity="S4",
          title="The 4.0.0 vector migration takes an undeclared legacy table's width from an arbitrary row",
          note="Reachable only for a legacy table with no declared and no recorded width and mixed widths; "
               "a VECTOR column declared with a type and no length holds rows of different widths (docs/migration/v4.0.0.md:329-332 relies on this for the quarantine's emb). "
               "Which rows then fit the new route is decided by scan order. Not reproduced."),
        S("iris_vector_graph/schema.py", 2436, "GraphSchema.get_procedures_sql_list (kg_KNN_VEC DDL)",
          "false-positive", "the procedure body ends ORDER BY score DESC (the scan matched the CREATE line)",
          ["iris_vector_graph/schema.py:2469-2482"], tie_break=TIE,
          aside="not storage order: with labelFilter NULL the LEFT JOIN of rdf_labels keeps one row per label, so "
                "a node with n labels can fill n of the k places (schema.py:2471-2476); kg_RRF_FUSE's vector leg "
                "passes NULL (schema.py:2558). Unverified; outside this gate."),
        S("iris_src/src/Graph/KG/GraphStores.cls", 308, "VectorRouteGuard", "order-dependent",
          "SELECT TOP 1 table_name ... WHERE graph_id = :pGraph AND COALESCE(model_key,'') = '' AND kind node: the "
          "registry key is (table_name, graph_id) (_engine/schema.py:143-158) and the (graph_id, model_key) index is "
          "not unique (_engine/schema.py:585-588), so two node rows can answer one graph; the guard returns 0 "
          "(read kg_NodeEmbeddings) or raises depending on which row the scan returns first",
          ["iris_src/src/Graph/KG/GraphStores.cls:304-318", "iris_vector_graph/_engine/embeddings.py:107-118",
           "iris_vector_graph/_engine/embeddings.py:693-728"],
          finding_candidate=True, severity="S4",
          title="kg_KNN_VEC's route guard picks an arbitrary registry row where Python applies a fixed preference",
          note="Python resolves two rows for one pair with _route_preference (FR-015: kg_NodeEmbeddings before "
               "kg_NodeEmbeddings_optimized). The guard has no such rule. Reachable when a named graph holds both "
               "legacy rows (a 3.2.0 adoption mapped to one named graph); not reproduced. Owner: GraphStores.cls is "
               "module 12's file; VEC-B5.21/VEC-I5.22 state the guard in module 06."),
    ],
}

MISSED = {
    "02": [
        S("iris_vector_graph/_engine/query.py", 2412, "QueryMixin._edge_graphs", "collation-ordered",
          "for _ in range(10_000): nextSubscript over ^KG(\"out\"): the first 10,000 graph keys in collation order; "
          "the rest are silently left out, and any error answers []", ["iris_vector_graph/_engine/query.py:2408-2420"],
          finding_candidate=True, finding="F-0209", severity="S4",
          title="An all-graphs walk lists at most 10,000 graphs (existing finding F-0209)",
          documented=False, note="Deterministic (collation), not storage order; the truncation is undocumented. "
                                 "A capacity issue (gate 3.6-capacity) already recorded as F-0209."),
    ],
    "03": [
        S("iris_vector_graph/_engine/nodes_edges.py", 820, "NodesEdgesMixin.get_node_ids_by_property",
          "order-dependent",
          "TOP n s FROM rdf_props WHERE key = ? [AND val = ?] with no ORDER BY: with a limit the caller gets the "
          "first n subjects in scan order", ["iris_vector_graph/_engine/nodes_edges.py:801-832"],
          finding_candidate=True, severity="S4",
          title="Property lookups with a limit return a storage-order subset",
          note="The scan missed it: the TOP is built in a separate f-string. The docstring promises only a 'Cap on "
               "returned rows' (815); the same query is graph-blind (F-0206 family)."),
        S("iris_vector_graph/_engine/nodes_edges.py", 904, "NodesEdgesMixin.get_property_pairs_like",
          "order-dependent", "TOP n s, val ... WHERE key = ? AND val LIKE ? with no ORDER BY: a capped keyword probe "
          "answers the first n matches in scan order", ["iris_vector_graph/_engine/nodes_edges.py:892-915"],
          finding_candidate=True, severity="S4", title="as nodes_edges.py:820 (same candidate)",
          note="The docstring calls it a 'bounded LIKE probe' (898) and promises no order."),
    ],
    "04": [
        S("iris_src/src/Graph/KG/Edgeless.cls", 65, "Edgeless.Scan", "collation-ordered",
          "pages loners in node_id order (ORDER BY node_id, 52-54) and returns the resume key at the cap",
          ["iris_src/src/Graph/KG/Edgeless.cls:22-27", "iris_src/src/Graph/KG/Edgeless.cls:43-68"],
          documented=True, note="Deterministic paging; checked, not a scan miss of the storage-order rule."),
    ],
    "05": [
        S("iris_src/src/Graph/KG/TemporalWindow.cls", 185, "TemporalWindow (paged window reader)", "collation-ordered",
          "a page stops at pCount rows or PAGECHARS and the handle resumes at the saved key, so pages are complete and "
          "in ^KG subscript order", ["iris_src/src/Graph/KG/TemporalWindow.cls:160-191"], documented=True),
        S("iris_src/src/Graph/KG/TemporalWindow.cls", 341, "TemporalWindow.Latest", "collation-ordered",
          "every-source and prefix reads page the latest-event index in source order with a 'next' key; ties at the "
          "newest timestamp go to the last (p, o) in index order", ["iris_src/src/Graph/KG/TemporalWindow.cls:293-347"],
          documented=True),
    ],
    "06": [
        S("iris_src/src/Graph/KG/EmbedQueue.cls", 131, "EmbedQueue.ClaimPendingBatch", "collation-ordered",
          "the first batchSize PENDING entries in reqId order; reqId is the node id (Enqueue, 37-38), so entries are "
          "served in id collation order, not arrival order", ["iris_src/src/Graph/KG/EmbedQueue.cls:105-134",
                                                              "iris_src/src/Graph/KG/EmbedQueue.cls:35-59"],
          documented=True, finding_candidate=True, severity="S4",
          title="The embed queue serves PENDING entries in node-id order, so a late-collating entry can wait "
                "indefinitely under steady enqueue",
          note="Documented as a 'plain ordered scan (single-processor; no claim state)' (106-107); the arrival-order "
               "consequence (no FIFO, possible starvation) is not stated. Progress property, not reproduced."),
        S("iris_src/src/Graph/KG/EmbedQueue.cls", 267, "EmbedQueue.ProcessBatch", "collation-ordered",
          "the same order for the ObjectScript worker (Quit:processed>=batchSize)",
          ["iris_src/src/Graph/KG/EmbedQueue.cls:258-268"], documented=True, finding_candidate=True, severity="S4",
          title="as EmbedQueue.cls:131 (same candidate)"),
        S("iris_src/src/Graph/KG/IVFIndex.cls", 141, "IVFIndex.Search", "collation-ordered",
          "results ranked by ^||ivfRanked(-score, nodeId): ties broken by node id, deterministic",
          ["iris_src/src/Graph/KG/IVFIndex.cls:128-155"], documented=False,
          note="Deterministic; the metric itself is F-0607."),
    ],
}

OUT_OF_SCOPE = {
    "01": [
        ("iris_vector_graph/_engine/admin.py", 104, "active_queries_sql", "17 operations (list_active_queries)"),
        ("iris_vector_graph/engine.py", 576, "IRISGraphEngine._native_privileges", "09 native executor"),
        ("iris_vector_graph/engine.py", 784, "IRISGraphEngine._detect_fetch_first_unsafe", "08 cypher-sql (driver probe)"),
        ("iris_vector_graph/engine.py", 1340, "IRISGraphEngine._proc_db_schema_nodetypeproperties", "08 cypher-sql procedures"),
        ("iris_vector_graph/engine.py", 1346, "IRISGraphEngine._proc_db_schema_nodetypeproperties", "08 cypher-sql procedures"),
        ("iris_vector_graph/engine.py", 1382, "IRISGraphEngine._proc_db_schema_reltypeproperties", "08 cypher-sql procedures"),
        ("iris_vector_graph/engine.py", 1491, "IRISGraphEngine._proc_db_propertykeys", "08 cypher-sql procedures"),
        ("iris_vector_graph/engine.py", 1624, "IRISGraphEngine._proc_apoc_meta_data", "08 cypher-sql procedures"),
        ("iris_vector_graph/schema.py", 2484, "kg_TXT DDL", "07 text-search"),
        ("iris_vector_graph/schema.py", 2513, "kg_TXT DDL body (missed by scan)", "07 text-search"),
        ("iris_vector_graph/schema.py", 2545, "kg_RRF_FUSE DDL body (missed by scan)", "07 text-search (fusion)"),
    ],
    "04": [
        ("iris_vector_graph/stores/iris_sql_store.py", 2633, "IRISGraphStore.execute_knn_vec", "17 operations (SQL adapter); has ORDER BY score DESC"),
        ("iris_vector_graph/stores/iris_sql_store.py", 1179, "fetch_clause (missed by scan)", "17 operations (SQL adapter)"),
    ],
    "06": [
        ("iris_vector_graph/_engine/vector.py", 979, "VectorMixin.kg_TXT", "07 text-search"),
        ("iris_vector_graph/_engine/vector.py", 998, "VectorMixin.kg_TXT", "07 text-search"),
        ("iris_vector_graph/_engine/vector.py", 1042, "VectorMixin.kg_TXT", "07 text-search"),
    ],
}

# Scan sites in files no module 01-06 lists, recorded once (in 01) so every scan site is accounted for here.
NOT_IN_01_06 = [
    ("iris_vector_graph/_engine/query.py", [151, 588, 1818, 1835, 1837], "08 cypher-sql"),
    ("iris_vector_graph/cypher/translator.py", [2926, 3330, 3343, 4433, 4440, 4460, 4482, 5809, 8176, 11141, 11175,
                                                 12386], "08 cypher-sql"),
    ("iris_vector_graph/text_search.py", [48, 77, 111, 165, 212], "07 text-search"),
    ("iris_vector_graph/gql/engine.py", [40], "16 interfaces"),
    ("iris_vector_graph/ledger/replay.py", [342], "14 replay"),
    ("iris_vector_graph/dbapi_utils.py", [267], "17 operations"),
    ("iris_src/src/Graph/KG/Cypher/Exec.cls", [1101], "09 native executor"),
    ("iris_src/src/Graph/KG/MCPTools.cls", [33], "16 interfaces"),
]

STATUS = {
    "01": ("open", "4 order-dependent sites, all inside get_schema_visualization's documented sample (2773-2776); no "
                   "self-test pins the sample, and its graph-blind joins are F-0106; every other site is "
                   "existence-only or a false positive"),
    "02": ("closed", "both scan sites are existence probes whose answer is order-independent; the one truncating "
                     "traversal (_edge_graphs) is collation-ordered and already finding F-0209 (gate 3.6-capacity)"),
    "03": ("open", "the scan's only site is existence-only, but it missed two capped property lookups "
                   "(nodes_edges.py:820, 904) that return a storage-order subset"),
    "04": ("closed", "no scan site in module 04's functions; grep of its files found only Edgeless.Scan, which pages "
                     "in node_id order"),
    "05": ("closed", "no scan site; the temporal readers' truncations are collation-ordered pages that resume"),
    "06": ("open", "two order-dependent candidates (graph_scoped_embeddings.py:1273 migration width; "
                   "GraphStores.cls:308 route guard), score ties cut in scan order at every top-k search, and the "
                   "embed queue's id-order service"),
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    scan = json.loads((RUN / "checks" / "storage-order.json").read_text())
    excerpt = {}
    for s in scan:
        k = (s["file"], s["line"])
        if len(s["sql"]) > len(excerpt.get(k, "")):
            excerpt[k] = s["sql"]
    accounted = set()
    for m in ["01", "02", "03", "04", "05", "06"]:
        sites = []
        for s in SITES[m]:
            s = dict(s)
            s["sql_excerpt"] = excerpt.get((s["file"], s["line"]), "")[:300]
            if not s["sql_excerpt"]:
                raise SystemExit(f"{s['file']}:{s['line']} is not a scan site")
            accounted.add((s["file"], s["line"]))
            sites.append(s)
        oos = []
        for f, line, fn, owner in OUT_OF_SCOPE.get(m, []):
            oos.append({"file": f, "line": line, "function": fn, "owner": owner,
                        "in_scan": (f, line) in excerpt})
            accounted.add((f, line))
        doc = {
            "module": m, "gate": "3.4-storage-order", "input": "$RUN_DIR/checks/storage-order.json",
            "pin": "3eaa79cf77d3e0a879b2cced634cf2729d81499e",
            "generated_by": "experiment/playbook-completion/models/breadth-a/tools/storage_order_dispositions.py",
            "method": "each scan site in the module's files assigned by enclosing function (storage_order_sites.py, "
                      "inventory entry-point ranges and Scope lines) and read at the pin; scan completeness sampled "
                      "by grep of the module's scope files for TOP/LIMIT/FETCH FIRST and truncating $Order loops "
                      "($RUN_DIR/breadth-a/storage-order/grep-missed.log). Source reading only; nothing was run.",
            "sites": sites, "missed_by_scan": MISSED.get(m, []), "out_of_scope": oos,
            "summary": dict(Counter(s["disposition"] for s in sites)),
            "summary_missed": dict(Counter(s["disposition"] for s in MISSED.get(m, []))),
            "finding_candidates": sorted({s["title"] for s in sites + MISSED.get(m, []) if s["finding_candidate"]}),
            "status_suggestion": {"status": STATUS[m][0], "reason": STATUS[m][1]},
        }
        if m == "01":
            doc["not_in_modules_01_06"] = [{"file": f, "lines": ls, "owner": o} for f, ls, o in NOT_IN_01_06]
            for f, ls, _ in NOT_IN_01_06:
                accounted |= {(f, x) for x in ls}
        (OUT / f"{m}.json").write_text(json.dumps(doc, indent=1) + "\n")
        print(m, doc["summary"], doc["summary_missed"], doc["status_suggestion"]["status"])
    missing = sorted(set(excerpt) - accounted)
    print("scan sites not accounted for:", missing)
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
