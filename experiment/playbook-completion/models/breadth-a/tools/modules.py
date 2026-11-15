"""Module file assignment for breadth lane A (modules 01-06), transcribed from each module's Scope line.

Each entry cites the Scope paragraph of experiment/playbook-uplift/ontology/NN-*.md (lines 3-15 of each file). A file
is either assigned whole ("*") or by function-level include/exclude lists; every exclusion and every inclusion that is
not in the Scope text literally carries a reason. Nothing here is inferred from the findings.
"""
from __future__ import annotations

ONTOLOGY = {
    "01": "experiment/playbook-uplift/ontology/01-install-schema.md",
    "02": "experiment/playbook-uplift/ontology/02-graph-identity.md",
    "03": "experiment/playbook-uplift/ontology/03-writes.md",
    "04": "experiment/playbook-uplift/ontology/04-adjacency.md",
    "05": "experiment/playbook-uplift/ontology/05-temporal.md",
    "06": "experiment/playbook-uplift/ontology/06-vectors.md",
}
NAMES = {"01": "install-schema", "02": "graph-identity", "03": "writes", "04": "adjacency", "05": "temporal",
         "06": "vectors"}

SCHEMA_ENGINE_06 = ["routed_table_ddl", "get_embedding_identity", "set_embedding_identity", "adopt_embedding_identities",
                    "enforce_embedding_identity", "reconcile_recorded_dimensions", "embedding_inventory",
                    "list_quarantine", "place_quarantined", "EmbeddingInventoryRow", "QuarantinedVector"]
SCHEMA_ENGINE_04 = ["sync", "rebuild_kg", "rebuild_nkg", "backfill_degp", "backfill_deg2p_exact"]
# _engine/schema.py members no lane-A Scope names (and no other module's Scope names for inference): kept out of 01's
# entry points and reported as unassigned, so that the omission list of 01 is not padded with another module's API.
SCHEMA_ENGINE_UNASSIGNED = {
    "materialize_inference": "not setup; no ontology Scope line names inference materialization (reported unassigned)",
    "retract_inference": "not setup; no ontology Scope line names inference retraction (reported unassigned)",
    "reify_edge": "reification is cited by 15-integrations, not by setup",
    "get_reifications": "reification is cited by 15-integrations, not by setup",
    "delete_reification": "reification is cited by 15-integrations, not by setup",
}

# file -> spec. spec: "*" (all), or {"include": [...]} / {"exclude": {...: reason}}; "reason" for the whole file.
MODULE_FILES = {
    "01": {
        "scope": "01-install-schema.md:5-15",
        "py": {
            "iris_vector_graph/schema_name.py": "*",
            "iris_vector_graph/_engine/schema.py": {
                "exclude": dict(**{n: "Scope 06: the registry's persistence half lives in _engine/schema.py (06-vectors.md:15-16)" for n in SCHEMA_ENGINE_06},
                                **{n: "Scope 04: the engine's sync, rebuild and backfill entry points (04-adjacency.md:10-12)" for n in SCHEMA_ENGINE_04},
                                **SCHEMA_ENGINE_UNASSIGNED)},
            "iris_vector_graph/schema.py": {
                "exclude": {"hnsw_indexes": "vector index DDL: Scope 01 'the vector width rules of setup are stated in module VEC'",
                            "get_embedding_dimension": "vector width rule: stated in module VEC (01 Scope)"}},
            "iris_vector_graph/_engine/class_deploy.py": "*",
            "iris_vector_graph/routine_record.py": "*",
            "iris_vector_graph/legacy_manifest.py": "*",
            "iris_vector_graph/legacy_bodies.py": "*",
            "iris_vector_graph/legacy_text.py": "*",
            "iris_vector_graph/_engine/legacy.py": "*",
            "iris_vector_graph/migrations/__init__.py": "*",
            "iris_vector_graph/migrations/_commit.py": "*",
            "iris_vector_graph/migrations/statements.py": "*",
            "iris_vector_graph/migrations/upgrade.py": "*",
            "iris_vector_graph/_engine/admin.py": {"include": ["remove_legacy_objects"],
                                                    "reason": "facade of legacy removal (01 Scope: the legacy objects)"},
            "iris_vector_graph/engine.py": {"include": ["_check_namespace_schema", "_schema_check_passed",
                                                         "_waive_schema_check"],
                                            "reason": "the first-use schema check (cells 'first use'; INS-X3.*), private but the only implementation of that command"},
            "scripts/deploy_production.py": {"include": ["*"], "reason": "the legacy loader of sql/schema.sql and sql/operators_fixed.sql (HD-0103: inventory both install paths)"},
            "scripts/deploy_graph_tvfs.py": {"include": ["*"], "reason": "loader of sql/graph_walk_tvf.sql (HD-0103)"},
        },
        "cls": ["iris_src/src/Graph/KG/SqlPrivilege.cls", "iris_src/src/Graph/KG/SqlProcs.cls"],
        "sql_files": True,
        "routines_from_ddl": {"default": True},
    },
    "02": {
        "scope": "02-graph-identity.md:5",
        "py": {
            "iris_vector_graph/_validate.py": "*",
            "iris_vector_graph/_engine/admin.py": {"include": ["set_multigraph", "is_multigraph"]},
            "iris_vector_graph/engine.py": {"include": ["_more_than_one_graph", "_GraphSubEngine.set_multigraph",
                                                         "_GraphSubEngine.is_multigraph", "namespace"],
                                            "reason": "graph-scoping parts of engine.py (02 Scope); _more_than_one_graph decides the all-graphs route"},
        },
        "cls": ["iris_src/src/Graph/KG/GraphKey.cls", "iris_src/src/Graph/KG/GraphMode.cls"],
    },
    "03": {
        "scope": "03-writes.md:5",
        "py": {
            "iris_vector_graph/_engine/nodes_edges.py": {
                "exclude": {"erase_graph": "03 Scope: owned by the erasure module",
                            "delete_nodes_by_prefix": "03 Scope: owned by the erasure module",
                            "drop_graph": "03 Scope: owned by the erasure module",
                            "bulk_delete_adjacency": "04 Scope names it (04-adjacency.md:12)",
                            "backfill_2hop_exact": "04 Scope: derived two-hop counts (TraversalBuild) are module ADJ"}},
            "iris_vector_graph/_write_txn.py": "*",
            "iris_vector_graph/bulk_loader.py": "*",
            "iris_vector_graph/prop_values.py": "*",
            "iris_vector_graph/_dictionary.py": "*",
            "iris_vector_graph/_collation.py": "*",
            "iris_vector_graph/_batch_check.py": "*",
            "iris_vector_graph/engine.py": {"include": ["_GraphSubEngine.create_node", "_GraphSubEngine.create_edge",
                                                         "_GraphSubEngine.delete_node", "_GraphSubEngine.delete_edge",
                                                         "_GraphSubEngine.bulk_create_nodes",
                                                         "_GraphSubEngine.bulk_create_edges",
                                                         "_GraphSubEngine.get_node_count", "_GraphSubEngine.get_edge_count",
                                                         "_GraphSubEngine.get_labels",
                                                         "_GraphSubEngine.get_relationship_types",
                                                         "from_connect", "from_wrapper", "_iris_obj"],
                                            "reason": "the write facade of engine.py (03 Scope); from_connect/_iris_obj decide which server process a write runs in (WRT-D17)"},
        },
        "cls": ["iris_src/src/Graph/KG/PropWrite.cls", "iris_src/src/Graph/KG/Txn.cls",
                "iris_src/src/Graph/KG/LabelIndex.cls"],
    },
    "04": {
        "scope": "04-adjacency.md:5-14",
        "py": {
            "iris_vector_graph/_edgeless.py": "*",
            "iris_vector_graph/freshness.py": "*",
            "iris_vector_graph/algo_cache.py": "*",
            "iris_vector_graph/_engine/schema.py": {"include": SCHEMA_ENGINE_04},
            "iris_vector_graph/_engine/admin.py": {"include": ["verify_sync", "verify_graph", "status"]},
            "iris_vector_graph/_engine/nodes_edges.py": {"include": ["bulk_delete_adjacency", "backfill_2hop_exact",
                                                                      "_rebuild_after_load"],
                                                          "reason": "bulk_delete_adjacency and the bulk-load warm-up (_rebuild_after_load) are named by the 04 Scope; backfill_2hop_exact builds deg2p"},
            "iris_vector_graph/stores/iris_sql_store.py": {"include": ["IRISSQLStore._cached_algorithm", "_cached_algorithm"],
                                                           "reason": "named by the 04 Scope (the result cache's client)"},
            "iris_vector_graph/engine.py": {"include": ["_CypherSubEngine.sync", "_CypherSubEngine.rebuild_nkg",
                                                         "_CypherSubEngine.rebuild_kg", "_adjacency_indexed"]},
        },
        "cls": ["iris_src/src/Graph/KG/" + c + ".cls" for c in
                ("Adjacency", "AdjIndex", "Adj", "EdgeScan", "Edgeless", "GraphIndex", "TraversalBuild", "GraphVerify",
                 "AlgoCache")],
    },
    "05": {
        "scope": "05-temporal.md:5",
        "py": {
            "iris_vector_graph/_engine/temporal.py": "*",
            "iris_vector_graph/_engine/temporal_window.py": "*",
            "iris_vector_graph/_engine/temporal_only_warning.py": "*",
            "iris_vector_graph/_tz.py": "*",
            "iris_vector_graph/migrations/temporal_structural_rows.py": "*",
            "iris_vector_graph/engine.py": {"include": ["_TemporalSubEngine.*"],
                                            "reason": "the engine's temporal facade (engine.temporal) fronts this module's methods"},
        },
        "cls": ["iris_src/src/Graph/KG/" + c + ".cls" for c in
                ("TemporalIndex", "TemporalIndexMS", "TemporalPolicy", "TemporalWindow")],
        "cited_cls": ["Graph.KG.Adjacency.AssertTemporalRow", "Graph.KG.Adjacency.RetractTemporalRow",
                      "Graph.KG.Adjacency.RetractTemporalRows", "Graph.KG.LedgerApply.OpCreateTemporalEdge"],
    },
    "06": {
        "scope": "06-vectors.md:5-16",
        "py": {
            "iris_vector_graph/embedding_identity.py": "*",
            "iris_vector_graph/embed_selector.py": "*",
            "iris_vector_graph/_engine/vector.py": {
                "exclude": {"kg_TXT": "06 Scope: kg_TXT is module TXT",
                            "bm25_build": "06 Scope: bm25_* are module TXT", "bm25_search": "module TXT",
                            "bm25_insert": "module TXT", "bm25_delete": "module TXT", "bm25_upgrade": "module TXT",
                            "bm25_drop": "module TXT", "bm25_info": "module TXT"}},
            "iris_vector_graph/_engine/embeddings.py": "*",
            "iris_vector_graph/vector_utils.py": "*",
            "iris_vector_graph/_widths.py": "*",
            "iris_vector_graph/migrations/graph_scoped_embeddings.py": "*",
            "iris_vector_graph/migrations/docs_and_edge_vectors.py": "*",
            "iris_vector_graph/migrations/kg_node_stores.py": "*",
            "iris_vector_graph/_engine/schema.py": {"include": SCHEMA_ENGINE_06},
            "iris_vector_graph/schema.py": {"include": ["hnsw_indexes", "get_embedding_dimension"],
                                            "reason": "setup's vector width and HNSW rules (01 Scope assigns them to VEC)"},
            "iris_vector_graph/engine.py": {"include": ["_CypherSubEngine.execute_knn_vec"]},
        },
        "cls": ["iris_src/src/Graph/KG/" + c + ".cls" for c in
                ("IVFIndex", "VecIndex", "PLAIDSearch", "EmbedQueue", "EmbedQueueTask")],
        "routines": ["kg_KNN_VEC", "kg_VEC_ROUTE_GUARD", "kg_RRF_FUSE"],
    },
}

# SQL routines created by setup's DDL strings (schema.py get_procedures_sql_list): semantics owner by name prefix.
ROUTINE_OWNER = [("kg_KNN_VEC", "06"), ("kg_VEC_ROUTE_GUARD", "06"), ("kg_RRF_FUSE", "06"), ("kg_TXT", "07"),
                 ("kg_PPR", "10"), ("kg_Degree", "10"), ("kg_Betweenness", "10"), ("kg_Closeness", "10"),
                 ("kg_Eigenvector", "10"), ("kg_Leiden", "10"), ("kg_Triangle", "10"), ("kg_SCC", "10"),
                 ("kg_KCore", "10"), ("", "08")]


def routine_owner(name: str) -> str:
    for prefix, mod in ROUTINE_OWNER:
        if name.startswith(prefix):
            return mod
    return "08"
