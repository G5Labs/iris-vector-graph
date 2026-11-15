#!/usr/bin/env python3
"""§3.4 ownership check: a single write owner per table/global, over the source-derived census (census_all.py).

    python ownership.py --out DIR            # census + check + controls -> DIR/ownership.json, prints the tables
    python ownership.py --self-test          # seeded violations must be classified exactly (exit 1 otherwise)

Steps
1. Census: census_all.census() over the pin's product files (every durable store; see that file).
2. Site -> module: models/breadth-c/inventory.json (the product-wide entry inventory transcribed from the ontology Scope
   lines): a .cls site by its Class.Method entry, a Python site by the innermost entry whose line range holds it; a
   private helper of a file several modules share by the owners of the same-file entries that call it (transitively);
   then the breadth-A function lists (models/breadth-a/tools/modules.py MODULE_FILES); then the file's owners. A file no
   Scope names is module 00 (unowned, models/breadth-c reconciliation).
3. Declared owner per store (DECLARED below, each with its citation): one owning module, the co-writers that the owner's
   ontology or a product store plan names (Graph.KG.GraphStores.Inventory for erasure; snapshot.py STORE_PLAN for
   restore), delegate methods the owner's Scope names as its writers, and the classes an ADR makes the only writers.
4. Check: per store, every module with a direct write site. A module other than the owner is a second writer:
   'declared' (a named co-writer: the single-owner rule fails by design) or 'undeclared'. A site outside an ADR's
   class list is an 'adr' violation whatever its module. A whole-root write (Kill ^KG) writes every sub-store; a
   run-time sub-store (^KG(?)) or an 'any' write (a global loader, an indirection on a caller's name) is a
   conditional write of every store it may reach.
5. Controls: (a) completeness against the registered census (followup-writer-census): every site there is a site here
   with a compatible store; (b) the product's own guard (tests/unit/test_adjacency_single_writer.py): the .cls writers of
   ^KG("out")/("in") found here are exactly the guard's (Adjacency.cls only); (c) journal control: every
   (entry point, store written) pair the journal oracle recorded in footprints/NN.json is explained by a census site
   (same store) in the entry's module or in a module its source reaches by call; unexplained pairs are census gaps.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
PC = HERE.parents[1]                          # experiment/playbook-completion
REPO = PC.parents[1]
sys.path.insert(0, str(HERE))
import census_all as C  # noqa: E402

INVENTORY = PC / "models/breadth-c/inventory.json"
REG_CENSUS_REL = "followup/writer-census.json"
ONT = "experiment/playbook-uplift/ontology/"

# ------------------------------------------------------------------------------------------------ declarations

GS = "iris_src/src/Graph/KG/GraphStores.cls:28-130 (Inventory: the stores erasure covers) + " + ONT + "12-erasure.md:24 (ERS-0)"
SP = "iris_vector_graph/_engine/snapshot.py:102-200 (STORE_PLAN, the stores a restore writes) + " + ONT + "18-snapshot.md:5 (SNP Scope)"
TEMPORAL_DELEGATES = ["Graph.KG.Adjacency.AssertTemporalRow", "Graph.KG.Adjacency.RetractTemporalRow",
                      "Graph.KG.Adjacency.RetractTemporalRows", "Graph.KG.LedgerApply.OpCreateTemporalEdge"]
#: EdgeScan's SQL bulk ingest is the server path of WRT's bulk loads (03-writes.md:5 'bulk loads';
#: nodes_edges.py:1741 and :2062 call it; RegisterDefaultNode is its endpoint step, EdgeScan.cls:285-291)
BULK_DELEGATES = ["Graph.KG.EdgeScan.BulkIngestNodesSQL", "Graph.KG.EdgeScan.BulkIngestEdgesSQL",
                  "Graph.KG.EdgeScan.RegisterDefaultNode"]
CONTENT_COWRITERS = {
    "11": ("owner", ONT + "03-writes.md:34 (WRT-0 owns the writes 'that do not go through the ledger'); " + ONT + "11-ledger.md:5-11 (the commit path and the records it writes)"),
    "12": ("plan", GS),
    "18": ("plan", SP),
    "08": ("writer", ONT + "08-cypher-sql.md:5,40 (Scope: writes CREATE, MERGE, SET, REMOVE, DELETE; CYP-D1 the graph tables)"),
    "01": ("writer", ONT + "01-install-schema.md:4-6 (the 3.2.0 edge rescue and the graph_id upgrade steps); sql/fraud_sample_data.sql is demo data (intent/HD-0103.md:18,41)"),
    "15": ("writer", ONT + "15-integrations.md:5-10,92 (FHIRGraph.cls builds and resyncs FHIR graphs, INT-F1.15; reify_edge / delete_reification)"),
    "17": ("writer", ONT + "17-operations.md:185,187,189 (OPS-B5.4 write nodes, OPS-B5.5 write edges, OPS-B5.6 delete nodes)"),
}
LEGACY_01 = ("writer", ONT + "01-install-schema.md:7-8 (the legacy objects: _engine/legacy.py, whose copy_ledger_history copies a 4.5.x ledger into the IVG Schema)")
PURGE_11 = ("writer", "iris_src/src/Graph/KG/Ledger.cls:242-248 PurgeAll; LedgerRevision.cls:5 ('Test/admin reset goes through Graph.KG.Ledger.PurgeAll')")
OPS_DELETE = ("writer", ONT + "17-operations.md:189 (OPS-B5.6: delete nodes removes ids with their labels, properties, edges and vectors)")
MIGRATION_06 = ("writer", ONT + "06-vectors.md:12-15 (Scope: the 4.0.0 steps graph_scoped_embeddings.py, docs_and_edge_vectors.py, kg_node_stores.py)")

DECLARED = {
    # content: no Root names one owner; WRT-0 names the facts, the ledger and erasure name their own write paths
    "sql:Graph_KG.nodes": {"owner": "03", "cite": ONT + "03-writes.md:34 (WRT-0: owns writes of nodes, edges, labels and properties that do not go through the ledger)",
                           "cowriters": dict(CONTENT_COWRITERS, **{"05": ("writer", ONT + "05-temporal.md:39 (TMP-0: the rows those events imply; endpoint rows)"), "06": MIGRATION_06}),
                           "delegates": TEMPORAL_DELEGATES + BULK_DELEGATES},
    "sql:Graph_KG.rdf_edges": {"owner": "03", "cite": ONT + "03-writes.md:34 (WRT-0)",
                               "cowriters": dict(CONTENT_COWRITERS, **{"05": ("writer", ONT + "05-temporal.md:39 (TMP-0: the rows in the edge table those events imply)")}),
                               "delegates": TEMPORAL_DELEGATES + BULK_DELEGATES},
    "sql:Graph_KG.rdf_labels": {"owner": "03", "cite": ONT + "03-writes.md:34 (WRT-0)", "cowriters": dict(CONTENT_COWRITERS, **{"06": MIGRATION_06}),
                                "delegates": BULK_DELEGATES},
    "sql:Graph_KG.rdf_props": {"owner": "03", "cite": ONT + "03-writes.md:34 (WRT-0)", "cowriters": dict(CONTENT_COWRITERS, **{"06": MIGRATION_06}),
                               "delegates": BULK_DELEGATES},
    # adjacency (ADJ-0 'Stores owned' list; ADR-0011 for out/in)
    'global:^KG("out")': {"owner": "04", "cite": ONT + "04-adjacency.md:49 (ADJ-0 stores owned); docs/adr/0011-the-adjacency-index-has-one-writer-module.md:12",
                          "classes": ["Graph.KG.Adjacency"], "adr": "ADR-0011", "cowriters": {"12": GS, "18": SP}},
    'global:^KG("in")': {"owner": "04", "cite": ONT + "04-adjacency.md:49; docs/adr/0011-the-adjacency-index-has-one-writer-module.md:12",
                         "classes": ["Graph.KG.Adjacency"], "adr": "ADR-0011", "cowriters": {"12": GS, "18": SP}},
    'global:^KG("label")': {"owner": "04", "cite": ONT + "04-adjacency.md:49 (written by the same class, spec 252); " + ONT + "03-writes.md:43 (WRT-D7: owned by the adjacency module)",
                            "cowriters": {"12": GS, "18": SP, "06": MIGRATION_06}},
    'global:^KG("gen")': {"owner": "04", "cite": ONT + "04-adjacency.md:49", "cowriters": {"12": GS}},
    'global:^KG("degc")': {"owner": "04", "cite": ONT + "04-adjacency.md:49", "cowriters": {"12": GS}},
    'global:^KG("degw")': {"owner": "04", "cite": ONT + "04-adjacency.md:49", "cowriters": {"12": GS}},
    'global:^KG("deg")': {"owner": "04", "cite": ONT + "04-adjacency.md:49 (the counts made from the copy; ADR-0010 retired them)"},
    'global:^KG("degp")': {"owner": "04", "cite": ONT + "04-adjacency.md:49 (the counts; ADR-0010 retired them)"},
    'global:^KG("__version")': {"owner": "04", "cite": ONT + "04-adjacency.md:49,64 (ADJ-0, ADJ-D15 the graph-version token)"},
    'global:^KG("deg2p")': {"owner": "04", "cite": ONT + "04-adjacency.md:49", "cowriters": {"12": GS, "18": SP, "06": MIGRATION_06}},
    'global:^KG("deg2p_exact")': {"owner": "04", "cite": ONT + "04-adjacency.md:49", "cowriters": {"12": GS, "18": SP, "06": MIGRATION_06}},
    'global:^KG("deg2p_exact_merged")': {"owner": "04", "cite": ONT + "04-adjacency.md:6-8 (TraversalBuild two-hop counts); GraphStores.cls:126 (computed by NKGAccelTraversal)",
                                         "cowriters": {"12": GS, "10": "iris_src/src/Graph/KG/GraphStores.cls:126 (Arno's two-hop counts, Graph.KG.NKGAccelTraversal:Build2HopExact)"}},
    'global:^KG("prop")': {"owner": None, "cite": "no Root or Scope names an owner of ^KG(\"prop\") (ADJ-0 does not list it)",
                           "cowriters": {"12": GS, "18": SP, "06": MIGRATION_06}},
    "global:^IVG.AdjNoLock": {"owner": "04", "cite": ONT + "04-adjacency.md:49"},
    "global:^IVG.BuiltFrom": {"owner": "04", "cite": ONT + "04-adjacency.md:49"},
    "global:^IVG.AlgoCache": {"owner": "04", "cite": ONT + "04-adjacency.md:49",
                              "cowriters": {"10": ONT + "10-algorithms.md:5-9 (the shared result cache as the store uses it)", "12": GS}},
    "global:^NKG": {"owner": "04", "cite": ONT + "04-adjacency.md:49 (ADJ-0 lists ^NKG)",
                    "cowriters": {"10": ONT + "10-algorithms.md:5-9 (Scope: the interned snapshot ^NKG)", "12": GS, "18": SP}},
    # temporal (TMP-0 'Owns ...'; ADR-0002 for the five subtrees)
    'global:^KG("tout")': {"owner": "05", "cite": ONT + "05-temporal.md:39; docs/adr/0002-temporal-globals-are-not-directly-accessible.md:7-10",
                           "classes": ["Graph.KG.TemporalIndex", "Graph.KG.TemporalIndexMS"], "adr": "ADR-0002", "cowriters": {"12": GS, "18": SP}},
    'global:^KG("tin")': {"owner": "05", "cite": ONT + "05-temporal.md:39; ADR-0002", "classes": ["Graph.KG.TemporalIndex", "Graph.KG.TemporalIndexMS"], "adr": "ADR-0002", "cowriters": {"12": GS, "18": SP}},
    'global:^KG("bucket")': {"owner": "05", "cite": ONT + "05-temporal.md:39; ADR-0002", "classes": ["Graph.KG.TemporalIndex", "Graph.KG.TemporalIndexMS"], "adr": "ADR-0002", "cowriters": {"12": GS, "18": SP}},
    'global:^KG("tagg")': {"owner": "05", "cite": ONT + "05-temporal.md:39; ADR-0002", "classes": ["Graph.KG.TemporalIndex", "Graph.KG.TemporalIndexMS"], "adr": "ADR-0002", "cowriters": {"12": GS, "18": SP}},
    'global:^KG("edgeprop")': {"owner": "05", "cite": ONT + "05-temporal.md:39; ADR-0002", "classes": ["Graph.KG.TemporalIndex", "Graph.KG.TemporalIndexMS"], "adr": "ADR-0002", "cowriters": {"12": GS, "18": SP}},
    'global:^KG("tlast")': {"owner": "05", "cite": ONT + "05-temporal.md:39; GraphStores.cls:92-93 (kept by TemporalIndex alone)", "cowriters": {"12": GS, "18": SP}},
    'global:^KG("labelset")': {"owner": "05", "cite": ONT + "05-temporal.md:39 (labelset interning)", "cowriters": {"12": GS, "18": SP}},
    "global:^IVG.TemporalStructural": {"owner": "05", "cite": ONT + "05-temporal.md:39,52 (TMP-0, TMP-D13)", "cowriters": {"12": GS, "18": SP}},
    # graph identity
    "global:^IVG.GraphMode": {"owner": "02", "cite": ONT + "02-graph-identity.md:5,33 (Scope GraphMode.cls; GID-0)", "cowriters": {"12": GS, "18": SP}},
    # vectors (VEC Scope 'Owns ...')
    "sql:Graph_KG.embedding_registry": {"owner": "06", "cite": ONT + "06-vectors.md:5-6", "cowriters": {"12": GS + "; " + ONT + "06-vectors.md:128 (VEC-B2.22)", "18": SP,
                                        "01": ("owner", ONT + "06-vectors.md:14-15 (the registry's persistence half lives in _engine/schema.py, owned jointly with setup)")}},
    "sql:kg_emb_*": {"owner": "06", "cite": ONT + "06-vectors.md:6", "cowriters": {"12": ONT + "06-vectors.md:128 (VEC-B2.22: erasing a graph empties and drops its routes)", "18": SP}},
    "sql:kg_eemb_*": {"owner": "06", "cite": ONT + "06-vectors.md:6", "cowriters": {"12": ONT + "06-vectors.md:128 (VEC-B2.22)", "18": SP}},
    "sql:Graph_KG.kg_NodeEmbeddings": {"owner": "06", "cite": ONT + "06-vectors.md:7", "cowriters": {"12": GS, "18": SP,
                                       "01": ("writer", "sql/fraud_sample_data.sql (demo data loaded by scripts.setup.load_fraud_data; intent/HD-0103.md:18,41)"),
                                       "17": OPS_DELETE}},
    "sql:Graph_KG.kg_NodeEmbeddings_optimized": {"owner": "06", "cite": ONT + "06-vectors.md:7", "cowriters": {"12": GS, "17": OPS_DELETE}},
    "sql:Graph_KG.kg_EdgeEmbeddings": {"owner": "06", "cite": ONT + "06-vectors.md:7", "cowriters": {"12": GS, "18": SP, "17": OPS_DELETE}},
    "sql:Graph_KG.kg_EdgeEmbeddings{suffix}": {"owner": "06", "cite": ONT + "06-vectors.md:7 (the legacy edge table's width reset)"},
    "sql:Graph_KG.embedding_quarantine": {"owner": "06", "cite": ONT + "06-vectors.md:8"},
    "sql:Graph_KG.edge_vector_quarantine": {"owner": "06", "cite": ONT + "06-vectors.md:13-15 (4.0.0 steps: docs_and_edge_vectors)"},
    "sql:Graph_KG.docs_quarantine": {"owner": "06", "cite": ONT + "06-vectors.md:13-15 (docs_and_edge_vectors)"},
    "sql:Graph_KG.docs": {"owner": "06", "cite": ONT + "07-text-search.md:9-10 (the docs table is created by module VEC)", "cowriters": {"12": GS, "18": SP}},
    "sql:Graph_KG.docs{suffix}": {"owner": "06", "cite": ONT + "07-text-search.md:9-10"},
    "global:^IVF": {"owner": "06", "cite": ONT + "06-vectors.md:8-9", "cowriters": {"18": SP}},
    "global:^VecIdx": {"owner": "06", "cite": ONT + "06-vectors.md:9", "cowriters": {"18": SP}},
    "global:^PLAID": {"owner": "06", "cite": ONT + "06-vectors.md:9", "cowriters": {"18": SP}},
    "global:^EmbedQueue": {"owner": "06", "cite": ONT + "06-vectors.md:9-10"},
    "global:^IVG.EmbedQueueTask": {"owner": "06", "cite": ONT + "06-vectors.md:9-10 (EmbedQueueTask.cls)"},
    # text
    "global:^BM25Idx": {"owner": "07", "cite": ONT + "07-text-search.md:5-6 (Owns ... the ^BM25Idx global)", "cowriters": {"18": SP}},
    'global:^BM25Idx("__stop__")': {"owner": "07", "cite": ONT + "07-text-search.md:5-6 (its stopword list)"},
    # native executor
    "global:^IVG.CypherCompiled": {"owner": "09", "cite": ONT + "09-native-executor.md:5-7 (Gen.cls: compiled plans, plan entries)"},
    "global:^IRIS.Temp.IVG.Cypher": {"owner": "09", "cite": ONT + "09-native-executor.md:5-6 (Exec.cls: paging, workers)"},
    # algorithms
    "global:^ArnoKG": {"owner": "10", "cite": ONT + "10-algorithms.md:5-8 (ArnoAccel, NKGAccel* readers)"},
    "global:^ArnoAccel": {"owner": "10", "cite": ONT + "10-algorithms.md:7-8 (the Arno library bridge)"},
    "global:^bcBitAdj": {"owner": "10", "cite": ONT + "10-algorithms.md:5-8 (NKGAccelCentrality)"},
    "global:^bcParScore": {"owner": "10", "cite": ONT + "10-algorithms.md:5-8 (NKGAccelCentrality)"},
    "global:^bcParSrc": {"owner": "10", "cite": ONT + "10-algorithms.md:5-8 (NKGAccelCentrality)"},
    "global:^IRIS.Temp.IVG.VL": {"owner": "10", "cite": ONT + "10-algorithms.md:5-6 (VarLength)"},
    # ledger (LED Scope; RED Scope and its three named exemptions)
    'global:^IVG.Ledger("rec")': {"owner": "11", "cite": ONT + "11-ledger.md:5-11", "cowriters": {"13": ONT + "13-redaction.md:35 (RED-0: takes content out of the ledger's records)", "18": SP}},
    'global:^IVG.Ledger("stmt")': {"owner": "11", "cite": ONT + "11-ledger.md:5-11 (statement identity)",
                                   "cowriters": {"12": ONT + "12-erasure.md:32,40 (ERS-B1.2, ERS-B2.1); " + GS, "13": ONT + "13-redaction.md:93 (RED-B9)", "18": SP}},
    'global:^IVG.Ledger("tuple")': {"owner": "11", "cite": ONT + "11-ledger.md:5-11 (statement identity)",
                                    "cowriters": {"12": ONT + "12-erasure.md:32,40; " + GS, "13": ONT + "13-redaction.md:93 (RED-B9)", "18": SP}},
    'global:^IVG.Ledger("idem")': {"owner": "11", "cite": ONT + "11-ledger.md:5-11", "cowriters": {"13": ONT + "11-ledger.md:123 (LED-B4.7.11: the redaction module owns it)", "18": SP}},
    'global:^IVG.Ledger("idemRedacted")': {"owner": "13", "cowriters_extra": {"11": PURGE_11}, "cite": ONT + "11-ledger.md:123; " + ONT + "13-redaction.md:5", "cowriters": {"18": SP}},
    'global:^IVG.Ledger("redactedRev")': {"owner": "13", "cowriters_extra": {"11": PURGE_11}, "cite": ONT + "13-redaction.md:5", "cowriters": {"18": SP}},
    'global:^IVG.Ledger("redacting")': {"owner": "13", "cowriters_extra": {"11": PURGE_11}, "cite": ONT + "13-redaction.md:5; " + ONT + "11-ledger.md:135 (LED-B4.10.5)", "cowriters": {"18": SP}},
    'global:^IVG.Ledger("head")': {"owner": "11", "cite": ONT + "11-ledger.md:5-11", "cowriters": {"18": SP}},
    'global:^IVG.Ledger("stmtNext")': {"owner": "11", "cite": ONT + "11-ledger.md:5-11", "cowriters": {"18": SP}},
    'global:^IVG.Ledger("idBySeq")': {"owner": "11", "cite": ONT + "11-ledger.md:5-11", "cowriters": {"18": SP}},
    'global:^IVG.Ledger("revById")': {"owner": "11", "cite": ONT + "11-ledger.md:5-11", "cowriters": {"18": SP}},
    'global:^IVG.Ledger("meta")': {"owner": "11", "cite": ONT + "11-ledger.md:5-11 (enable, disable, strict mode)", "cowriters": {"18": SP}},
    "sql:Graph_KG.ledger_revisions": {"owner": "11", "cite": ONT + "11-ledger.md:5-11 (the immutable revision table)",
                                      "cowriters": {"13": ONT + "11-ledger.md:202 (LED-B7.4: redaction may clear four free-text fields)", "18": SP, "01": LEGACY_01}},
    "sql:Graph_KG.ledger_stats": {"owner": "11", "cite": ONT + "11-ledger.md:5-11 (stats)", "cowriters": {"18": SP, "01": LEGACY_01}},
    # integrations (INT Scope and Root)
    "sql:Graph_KG.fhir_graphs": {"owner": "15", "cite": ONT + "15-integrations.md:5,50", "cowriters": {"12": ONT + "15-integrations.md:156 (INT-F10: erasing sets both sync watermarks to zero)", "18": SP}},
    "sql:Graph_KG.fhir_definitions": {"owner": "15", "cite": ONT + "15-integrations.md:5,50", "cowriters": {"12": GS, "18": SP}},
    "sql:Graph_KG.fhir_unresolved": {"owner": "15", "cite": ONT + "15-integrations.md:5,50", "cowriters": {"12": GS, "18": SP}},
    "sql:Graph_KG.fhir_canonical_refs": {"owner": "15", "cite": ONT + "15-integrations.md:5,50", "cowriters": {"12": GS, "18": SP}},
    "sql:Graph_KG.code_crosswalk": {"owner": "15", "cite": ONT + "15-integrations.md:50 (code maps)", "cowriters": {"18": SP}},
    "sql:Graph_KG.fhir_bridges": {"owner": "15", "cite": ONT + "15-integrations.md:5 (sql/fhir_bridges.sql)", "cowriters": {"18": SP}},
    "sql:Graph_KG.rdf_reifications": {"owner": "15", "cite": ONT + "15-integrations.md:5-10 (reify_edge, get_reifications, delete_reification; edge notes)",
                                      "cowriters": {"12": GS, "18": SP, "11": ("writer", ONT + "11-ledger.md:180 (LED-B5.24: deleting an edge deletes the nodes that reify it; rdf_reifications rows deleted)")}},
    "sql:Graph_KG.rdf_namespaces": {"owner": "15", "cite": ONT + "15-integrations.md:50 (RDF files; register_namespace)", "cowriters": {"18": SP}},
    "sql:Graph_KG.table_mappings": {"owner": "15", "cite": ONT + "15-integrations.md:50 (table maps)", "cowriters": {"18": SP}},
    "sql:Graph_KG.relationship_mappings": {"owner": "15", "cite": ONT + "15-integrations.md:50 (table maps)", "cowriters": {"18": SP}},
    # operations, setup, snapshot
    "global:^Graph.KG.Meta": {"owner": "17", "cite": ONT + "17-operations.md:5 (Graph.KG.Meta)"},
    "global:^IVG.Deploy": {"owner": "01", "cite": ONT + "01-install-schema.md:4-8 (schema record, routine record, class deploy)"},
    "sql:Graph_KG.rdf_edges__ivg400rescue": {"owner": "01", "cite": ONT + "01-install-schema.md:5-6 (the 3.2.0 edge rescue)"},
    "sql:Graph_KG.rdf_edges__ivg400unplaced": {"owner": "01", "cite": ONT + "01-install-schema.md:5-6 (the 3.2.0 edge rescue)"},
    "sql:Graph_KG.nodes_new": {"owner": "01", "cite": ONT + "01-install-schema.md:5-6 (the graph_id upgrade steps)"},
    "file": {"owner": "18", "cite": ONT + "18-snapshot.md:5 (the archive file; the server-side helpers)"},
}
#: Files outside the inventory's module files that the product serves (attributed with the citation).
EXTRA_FILE_OWNERS = {"examples/domains/biomedical/resolver.py": (["16"], "served by the sample API: api/gql/schema.py:78-85 imports BiomedicalDomainResolver (updateProtein, F-1604)")}
#: Sites the served product cannot reach (attributed as usual, classified 'unserved').
UNSERVED = {"api/gql/resolvers/mutation.py": ONT + "16-interfaces.md:115 (API-T6.11: the resolvers in api/gql/resolvers are not part of the served schema; imported only by unit tests)"}
#: Module-level SQL templates: the modules whose code executes them.
TEMPLATE_USERS = {
    ("iris_vector_graph/migrations/statements.py", None): (["06"], "statements.py:270-290 bind(); executed by migrations/docs_and_edge_vectors.py:62,243-252,650-662 (06's 4.0.0 step)"),
}
#: GraphSchema.get_bulk_insert_sql's templates by line (schema.py:1808-1838), attributed to the code that executes each kind.
BULK_TEMPLATE_LINES = {1814: (["03", "06"], "kind nodes_with_graph: nodes_edges.py:1025,1131,1777 (03) and migrations/graph_scoped_embeddings.py:726 (06)"),
                       1836: ([], "kind kg_NodeEmbeddings: no product code asks for it (grep of _bulk_sql / get_bulk_insert_sql callers)")}
BULK_TEMPLATE_DEFAULT = (["03"], "kinds nodes, rdf_labels(_with_graph), rdf_props(_with_graph), rdf_edges(_with_graph): nodes_edges.py:1025-1955 _bulk_sql (03's bulk writes)")
#: The SQL file sql/fraud_sample_data.sql is demo data of no module's Scope; sql/ is module 01's by its Scope ("the SQL
#: files under sql/"). Stores that are IRIS's own (Task Manager rows) have no IVG owner.
NO_IVG_OWNER = {"system:%SYS.Task": "IRIS Task Manager rows (%SYS.Task): IRIS's table; EmbedQueue and FHIRGraph each own their own task row"}


def gs_inventory():
    """Stores named by Graph.KG.GraphStores.Inventory (the erase/snapshot plan), as census store names."""
    text = (REPO / "iris_src/src/Graph/KG/GraphStores.cls").read_text()
    out = set()
    for m in re.finditer(r'\.\.Entry\("((?:[^"]|"")+)"', text):
        n = m.group(1).replace('""', '"')
        if n.startswith("^"):
            mm = re.match(r'(\^[\w.]+)(?:\("([^"]+)"\))?', n)
            out.add(C.global_store(mm.group(1), ("lit:" + mm.group(2)) if mm.group(2) else None, False))
        else:
            out.add(C.sql_store(n))
    return out


# ------------------------------------------------------------------------------------------------ module attribution

class Modules:
    def __init__(self, inv=None, breadth_a=True):
        inv = inv or json.loads(INVENTORY.read_text())
        self.file_owners = {f["file"]: f["owners"] for f in inv["files"]}
        self.cls_entry = {}
        self.py_entries = defaultdict(list)
        for e in inv["entries"]:
            if e["file"].endswith(".cls") and e["kind"] == "os-method":
                self.cls_entry[e["name"]] = e["owners"]
            elif e["file"].endswith(".py"):
                self.py_entries[e["file"]].append(e)
        self.callers_cache = {}
        self.texts = {}
        self.mfiles = {}
        if breadth_a:
            sys.path.insert(0, str(PC / "models/breadth-a/tools"))
            try:
                import modules as ba  # noqa: E402
                for mod, spec in ba.MODULE_FILES.items():
                    for f, sp in spec.get("py", {}).items():
                        self.mfiles.setdefault(f, []).append((mod, sp))
            except Exception:  # noqa: BLE001
                pass

    def text(self, rel):
        if rel not in self.texts:
            p = REPO / rel
            self.texts[rel] = p.read_text(errors="replace") if p.exists() else ""
        return self.texts[rel]

    def _py_calls(self, rel):
        """function name -> set of called names, and function name -> [(start, end)] for one file."""
        if rel in self.callers_cache:
            return self.callers_cache[rel]
        calls, ranges = defaultdict(set), defaultdict(list)
        try:
            tree = ast.parse(self.text(rel))
        except SyntaxError:
            self.callers_cache[rel] = (calls, ranges)
            return calls, ranges
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                ranges[n.name].append((n.lineno, getattr(n, "end_lineno", n.lineno)))
                for c in ast.walk(n):
                    if isinstance(c, ast.Call):
                        calls[n.name].add(c.func.attr if isinstance(c.func, ast.Attribute) else getattr(c.func, "id", ""))
                    elif isinstance(c, ast.Name):
                        calls[n.name].add(c.id)        # a constant or function named (passed, not called)
        self.callers_cache[rel] = (calls, ranges)
        return calls, ranges

    def of(self, site):
        f, line = site["file"], site["line"]
        if f in EXTRA_FILE_OWNERS:
            return EXTRA_FILE_OWNERS[f][0], "served file: " + EXTRA_FILE_OWNERS[f][1]
        for (tf, tm), (mods, cite) in TEMPLATE_USERS.items():
            if tf == f and (tm is None or tm == site.get("method")):
                return mods, "template executed by: " + cite
        if f == "iris_vector_graph/schema.py" and site.get("method") == "GraphSchema.get_bulk_insert_sql":
            mods, cite = BULK_TEMPLATE_LINES.get(line, BULK_TEMPLATE_DEFAULT)
            return (mods or ["unserved"]), "template executed by: " + cite
        if f.endswith(".cls"):
            o = self.cls_entry.get(site["method"])
            if o:
                return sorted(o), "inventory entry " + site["method"]
            return sorted(self.file_owners.get(f, [])) or ["00"], "file owners"
        if f.endswith(".sql"):
            return sorted(self.file_owners.get(f, [])) or ["00"], "file owners (sql)"
        best = None
        for e in self.py_entries.get(f, []):
            if e["line"] <= line <= e.get("end", e["line"]) and (best is None or e["line"] >= best["line"]):
                best = e
        if best and best["owners"]:
            return sorted(best["owners"]), f"inventory entry {best['name']} ({f}:{best['line']}-{best.get('end')})"
        if best and not best["owners"]:
            return ["00"], f"inventory entry {best['name']} with no owning Scope (module 00, models/breadth-c reconciliation)"
        fo = self.file_owners.get(f, [])
        if len(fo) == 1:
            return fo, "file owner"
        if not fo:
            return ["00"], "file no Scope names (module 00)"
        # a private helper of a shared file: owners of the same-file entries that reach it
        calls, ranges = self._py_calls(f)
        fname = None
        for name, rs in ranges.items():
            for a, b in rs:
                if a <= line <= b and (fname is None or a >= ranges[fname][0][0]):
                    fname = name
        if fname is None:
            # a module-level constant (a DDL template): the functions that name it
            tree = ast.parse(self.text(f))
            const = None
            for st in tree.body:
                if isinstance(st, ast.Assign) and st.lineno <= line <= getattr(st, "end_lineno", st.lineno):
                    const = next((t.id for t in st.targets if isinstance(t, ast.Name)), None)
            fname = const
        owners, seen, todo = set(), {fname}, [fname]
        while todo:
            cur = todo.pop()
            for caller, callees in calls.items():
                if cur in callees and caller not in seen:
                    seen.add(caller)
                    todo.append(caller)
                    for e in self.py_entries.get(f, []):
                        if e["name"] == caller and e["owners"]:
                            owners |= set(e["owners"])
        if owners:
            return sorted(owners), f"same-file callers of {fname}"
        for mod, sp in self.mfiles.get(f, []):
            if isinstance(sp, dict):
                inc = sp.get("include") or []
                exc = sp.get("exclude") or {}
                q = site.get("method", "")
                short = q.split(".")[-1]
                if (inc and (short in inc or q in inc)) or (exc and short not in exc and not inc):
                    return [mod], "breadth-A function list"
        return sorted(fo), "file owners (shared file, helper not attributed)"


# ------------------------------------------------------------------------------------------------ check

def expand_store(st, known):
    """A site's store -> [(store, conditional?)]."""
    if st == "any":
        return [(k, True) for k in known if not k.startswith("schema:")]
    m = re.match(r'(global:\^[\w.]+)\(\?\)$', st)
    if m:
        return [(k, True) for k in known if k.startswith(m.group(1) + "(")]
    if st in ("global:^KG", "global:^NKG", "global:^IVG.Ledger"):
        subs = [(k, False) for k in known if k.startswith(st + "(")]
        return subs + ([(st, False)] if st in known else [])
    return [(st, False)]


def declared_by(cite, owner):
    """Who declares a co-writer: the owner's own ontology file ('owner'), a product store plan ('plan'), else the
    writer's ontology ('writer')."""
    if owner and re.search(r"ontology/" + owner + r"-", cite):
        return "owner"
    if "GraphStores" in cite or "STORE_PLAN" in cite:
        return "plan"
    return "writer"


def declared_for(store):
    if store in DECLARED:
        return DECLARED[store]
    if store.startswith("global:^NKG("):
        return DECLARED["global:^NKG"]
    return None


def site_class(site):
    if site["file"].endswith(".cls"):
        return site["method"].rsplit(".", 1)[0]
    return site["file"]


def check(sites, modules: Modules, gs=None):
    gs = gs if gs is not None else gs_inventory()
    row_sites = [s for s in sites if s.get("kind") != "ddl"]
    known = sorted({s["store"] for s in row_sites if s["store"] not in ("any", "unresolved-table") and "(?)" not in s["store"]}
                   | set(DECLARED))
    for s in sites:
        s["modules"], s["attribution"] = modules.of(s)
    stores = {}
    for s in row_sites:
        for st, cond in expand_store(s["store"], known):
            if st in ("global:^KG", "global:^NKG", "global:^IVG.Ledger"):
                continue
            stores.setdefault(st, []).append((s, cond))
    report = {}
    for st, lst in sorted(stores.items()):
        dec = declared_for(st)
        owner = dec["owner"] if dec else None
        cow = dict(dec.get("cowriters", {})) if dec else {}
        delegates = set(dec.get("delegates", [])) if dec else set()
        cow.update(dec.get("cowriters_extra", {}) if dec else {})
        by_mod = defaultdict(list)
        for s, cond in lst:
            for m in s["modules"]:
                by_mod[m].append((s, cond))
        definite_mods = {m for m, ss in by_mod.items() if any(not c for _s, c in ss)}
        writers = {}
        for m, ss in sorted(by_mod.items()):
            dele = [s for s, c in ss if s["method"] in delegates]
            uns = [s for s, c in ss if (s["file"] in UNSERVED or m == "unserved") and s["method"] not in delegates]
            rest = [(s, c) for s, c in ss if s["method"] not in delegates and s["file"] not in UNSERVED and m != "unserved"]
            definite = [s for s, c in rest if not c]
            conditional = [s for s, c in rest if c]
            by, basis = "", ""
            if st in NO_IVG_OWNER:
                cls_ = "not-ivg"
            elif m == owner:
                cls_ = "owner"
            elif not rest and dele:
                cls_ = "delegate"
            elif not rest and uns:
                cls_ = "unserved"
            elif m in cow:
                v = cow[m]
                by, basis = (v if isinstance(v, tuple) else (declared_by(v, owner), v))
                cls_ = "declared"
            elif owner is None and definite_mods <= {m}:
                cls_ = "sole-writer"
            else:
                cls_ = "undeclared" if definite else "undeclared-conditional"
            writers[m] = {"class": cls_, "declared_by": by, "basis": basis,
                          "sites": sorted({f"{s['file']}:{s['line']} {s['method']}" for s in definite}),
                          "conditional_sites": sorted({f"{s['file']}:{s['line']} {s['method']}" for s in conditional}),
                          "delegate_sites": sorted({f"{s['file']}:{s['line']} {s['method']}" for s in dele}),
                          "unserved_sites": sorted({f"{s['file']}:{s['line']} {s['method']}" for s in uns})}
        adr = []
        if dec and dec.get("classes"):
            for s, cond in lst:
                if site_class(s) not in dec["classes"] and s["method"] not in delegates:
                    adr.append({"site": f"{s['file']}:{s['line']} {s['method']}", "conditional": cond, "modules": s["modules"],
                                "adr": dec.get("adr")})
        active = {m for m, w in writers.items() if w["class"] not in ("delegate", "unserved", "not-ivg")}
        single = len(active) <= 1 and not adr
        report[st] = {"owner": owner, "owner_cite": dec["cite"] if dec else NO_IVG_OWNER.get(st, "no declaration"),
                      "writers": writers, "single_owner": single, "adr_violations": adr,
                      "erase_plan_lists_it": st in gs}
    # DDL: schema writes per module (reported, not part of the row/node ownership decision)
    ddl = defaultdict(lambda: defaultdict(set))
    for s in sites:
        if s.get("kind") == "ddl":
            for m in s["modules"]:
                ddl[s["store"]][m].add(f"{s['file']}:{s['line']}")
    return report, {k: {m: sorted(v) for m, v in d.items()} for k, d in sorted(ddl.items())}


def per_module(report):
    mods = defaultdict(lambda: {"writes_others": [], "others_write_own": [], "own_single": [], "adr": []})
    for st, r in report.items():
        for m, w in r["writers"].items():
            if w["class"] not in ("owner", "sole-writer", "not-ivg"):
                mods[m]["writes_others"].append({"store": st, "owner": r["owner"], "class": w["class"], "declared_by": w["declared_by"],
                                                 "sites": w["sites"][:8], "conditional_sites": w["conditional_sites"][:4],
                                                 "n_sites": len(w["sites"]), "basis": w["basis"]})
        if r["owner"]:
            others = {m: w for m, w in r["writers"].items() if m != r["owner"] and w["class"] not in ("delegate", "unserved", "not-ivg")}
            if others:
                mods[r["owner"]]["others_write_own"].append({"store": st, "writers": {m: w["class"] for m, w in others.items()}})
            elif r["owner"] in r["writers"]:
                mods[r["owner"]]["own_single"].append(st)
        for a in r["adr_violations"]:
            for m in a["modules"]:
                mods[m]["adr"].append({"store": st, **a})
    return mods


# ------------------------------------------------------------------------------------------------ controls

REG_STORE_COMPAT = {"content": ("sql:Graph_KG.nodes", "sql:Graph_KG.rdf_edges", "sql:Graph_KG.rdf_labels", "sql:Graph_KG.rdf_props"),
                    "meta": ("sql:Graph_KG.ledger_revisions",), "rec": ('global:^IVG.Ledger("rec")',),
                    "stmt": ('global:^IVG.Ledger("stmt")', 'global:^IVG.Ledger("tuple")', 'global:^IVG.Ledger("stmtNext")'),
                    "idem": ('global:^IVG.Ledger("idem")',), "idemRedacted": ('global:^IVG.Ledger("idemRedacted")',),
                    "redactedRev": ('global:^IVG.Ledger("redactedRev")',), "marker": ('global:^IVG.Ledger("redacting")',),
                    "state": ('global:^IVG.Ledger("meta")',), "ledger-all": ("global:^IVG.Ledger",)}


def completeness(sites, reg_path):
    reg = json.loads(Path(reg_path).read_text())["detail"]
    have = defaultdict(set)
    for s in sites:
        have[(s["file"], s["line"])].add(s["store"])
    missing, incompatible = [], []
    for r in reg:
        if r["file"].startswith("<"):
            continue                         # the SQL INSERT surface of ledger_revisions: no product site
        k = (r["file"], r["line"])
        if k not in have:
            missing.append(f"{r['file']}:{r['line']} {r['owner']} {r['store']}")
            continue
        want = REG_STORE_COMPAT.get(r["store"])
        mine = have[k]
        if r["store"] in ("unresolved", "any"):
            continue
        if want and not any(any(x == w or x.startswith(w + "(") or x.startswith(w.split("(")[0] + "(?") or x == "any"
                                for w in want) for x in mine):
            incompatible.append({"site": f"{r['file']}:{r['line']} {r['owner']}", "registered": r["store"], "here": sorted(mine)})
    return {"registered_sites": len([r for r in reg if not r["file"].startswith("<")]), "missing": missing,
            "incompatible": incompatible}


def product_guard(sites):
    """The product's own scan (tests/unit/test_adjacency_single_writer.py) applied to the pin, against ours."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("guard", REPO / "tests/unit/test_adjacency_single_writer.py")
    g = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(g)
        theirs = sorted(str(Path(k).name) for k in g._writers().keys())
    except Exception as ex:  # noqa: BLE001
        return {"error": f"{type(ex).__name__}: {ex}"}
    ours = sorted({Path(s["file"]).name for s in sites if s["file"].endswith(".cls")
                   and s["store"] in ('global:^KG("out")', 'global:^KG("in")')})
    return {"guard_writers": theirs, "census_cls_writers": ours, "agree": theirs == ours}


GENERIC = {"__enter__", "__exit__", "__init__", "call", "close", "commit", "cursor", "execute", "executemany", "fetchall",
           "fetchone", "get", "items", "rollback", "run", "set", "tuple", "list", "dict", "str", "int", "len", "join", "append",
           "format", "isinstance", "getattr", "hasattr", "sorted", "range", "print", "super", "replace", "split", "strip",
           "lower", "upper", "keys", "values", "update", "pop", "add", "kill", "increment", "debug", "info", "warning",
           "error", "exception", "loads", "dumps", "encode", "decode", "startswith", "endswith", "max", "min", "sum", "any",
           "all", "enumerate", "zip", "map", "filter", "next", "iter", "open", "read", "write", "bool", "float", "type"}
HOOKS = {"sql:Graph_KG.rdf_edges": ["Graph.KG.AdjIndex.InsertIndex", "Graph.KG.AdjIndex.UpdateIndex", "Graph.KG.AdjIndex.DeleteIndex"],
         "sql:Graph_KG.rdf_labels": ["Graph.KG.LabelIndex.InsertIndex", "Graph.KG.LabelIndex.UpdateIndex", "Graph.KG.LabelIndex.DeleteIndex"]}
HOOK_CITE = "iris_vector_graph/schema.py:774,780 (idx_edges_adj AS Graph.KG.AdjIndex, idx_labels_adj AS Graph.KG.LabelIndex): a SQL write of the row runs the hook"
#: Entry points that execute SQL text their caller supplies: any table can be written, no product site names it.
CALLER_SQL = {"IRISGraphStore.execute_sql": "iris_vector_graph/stores/iris_sql_store.py:1522-1557 (cursor.execute of the caller's sql)"}


class Reach:
    """Call reach from a footprint entry's source ranges: Python by callee name (same file first, then any product
    file, depth 4), Python -> ObjectScript by class/method string pairs, ObjectScript by ##class(X).M( and ..M(, and
    the SQL row hooks of rdf_edges / rdf_labels."""

    def __init__(self, modules, sites):
        self.m = modules
        self.cls_idx = cls_call_index()
        self.py_idx = defaultdict(list)          # name -> [(file, start, end)]
        for rel, text in ((str(p.relative_to(REPO)), None) for p in C.product_files() if p.suffix == ".py"):
            calls, ranges = modules._py_calls(rel)
            for name, rs in ranges.items():
                for a, b in rs:
                    self.py_idx[name].append((rel, a, b))
        self.sites_by_file = defaultdict(list)
        self.sites_by_method = defaultdict(list)
        for s in sites:
            if s["file"].endswith(".cls"):
                self.sites_by_method[s["method"]].append(s)
            else:
                self.sites_by_file[s["file"]].append(s)

    def from_source(self, src):
        ranges = re.findall(r"([\w/.\-]+\.(?:py|cls)):(\d+)(?:-(\d+))?", src or "")
        py_todo, os_todo = [], []
        for f, a, b in ranges:
            if not b and f.endswith(".py"):
                # a single line names a function: the whole function that starts or holds it
                _c, rs = self.m._py_calls(f)
                hold = [(x, y) for v in rs.values() for x, y in v if x <= int(a) <= y]
                a, b = (min(hold, key=lambda r: r[1] - r[0]) if hold else (int(a), int(a)))
            a, b = int(a), int(b or a)
            if f.endswith(".py"):
                py_todo.append((f, a, b, 0))
            else:
                cls = f.split("iris_src/src/")[-1][:-4].replace("/", ".")
                for name, st, en, _ in self.cls_idx.get(cls, []):
                    if st <= b and en >= a:
                        os_todo.append(cls + "." + name)
        seen_py, seen_os, sites = set(), set(), []
        while py_todo:
            f, a, b, d = py_todo.pop()
            if (f, a) in seen_py:
                continue
            seen_py.add((f, a))
            sites += [s for s in self.sites_by_file.get(f, []) if a <= s["line"] <= b]
            body = "\n".join(self.m.text(f).splitlines()[a - 1:b])
            for cm in re.finditer(r'"(Graph\.KG\.[\w.]+|IVG\.\w+)"\s*,\s*"(\w+)"', body):
                os_todo.append(cm.group(1) + "." + cm.group(2))
            for cm in re.finditer(r"(?:LEDGER_CLASS|_CLASS)\s*,\s*\"(\w+)\"", body):
                os_todo.append("Graph.KG.Ledger." + cm.group(1))
            if f.startswith("iris_vector_graph/ledger/"):
                for cm in re.finditer(r"\b_call\(\s*\"(\w+)\"", body):
                    os_todo.append("Graph.KG.Ledger." + cm.group(1))     # client.py:239-252 _call(method) on LEDGER_CLASS
            if d >= 6:
                continue
            for name in set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", body)) - GENERIC:
                cands = self.py_idx.get(name, [])
                local = [c for c in cands if c[0] == f]
                for c in (local or cands[:12]):
                    py_todo.append((c[0], c[1], c[2], d + 1))
        hops = 0
        while True:
            while os_todo and hops < 20000:
                hops += 1
                q = os_todo.pop()
                if q in seen_os:
                    continue
                seen_os.add(q)
                sites += self.sites_by_method.get(q, [])
                cls, _, meth = q.rpartition(".")
                for name, st, en, cb in self.cls_idx.get(cls, []):
                    if name == meth:
                        for cm in re.finditer(r"##class\(([\w.]+)\)\.(\w+)\(", cb):
                            os_todo.append(cm.group(1) + "." + cm.group(2))
                        for cm in re.finditer(r"\.\.(\w+)\(", cb):
                            os_todo.append(cls + "." + cm.group(1))
            # the row hooks of the SQL rows written so far (a SQL write of the row runs the hook)
            for st_, hooks in HOOKS.items():
                if any(x["store"] == st_ for x in sites):
                    os_todo += [h for h in hooks if h not in seen_os]
            if not os_todo:
                break
        mods = set()
        for s in sites:
            mods |= set(s["modules"])
        return sites, mods


def cls_call_index():
    idx = {}
    for p in (REPO / "iris_src/src").rglob("*.cls"):
        rel = str(p.relative_to(REPO))
        cls = rel.split("iris_src/src/")[-1][:-4].replace("/", ".")
        ms, _ = C.os_methods(p.read_text(errors="replace"))
        idx[cls] = [(n, a, b, body) for n, a, b, body in ms]
    return idx


def journal_pairs():
    """(module, entry, source, store) for every store the journal oracle recorded per footprint entry."""
    out = []
    for f in sorted((PC / "footprints").glob("*.json")):
        d = json.loads(f.read_text())
        mod = d.get("module")
        eps = {}
        for e in d.get("entry_points", []) or d.get("entries", []):
            eid = e.get("id") or e.get("entry")
            eps[eid] = e
        if d.get("journal_validation"):
            for j in d["journal_validation"]:
                e = eps.get(j.get("footprint"), {})
                for st in j.get("stores_written") or []:
                    out.append((mod, j.get("footprint"), e.get("source"), st, j.get("run")))
        for eid, e in eps.items():
            j = e.get("journal_validation") or e.get("journal")
            js = j if isinstance(j, list) else [j] if j else []
            for jj in js:
                if not isinstance(jj, dict):
                    continue
                for st in (jj.get("observed_stores") or jj.get("stores_written") or []):
                    out.append((mod, eid, e.get("source"), st, jj.get("run_id") or jj.get("run")))
    return out


def norm_journal_store(st):
    st = st.split(" ")[0]
    return st


#: (entry, store) pairs the call reach does not connect, explained by reading (each with the path that writes the store).
READ_EXPLAINED = {
    ("extra:Graph_KG.Txn_Begin/Txn_End/Txn_Undo", "global:^KG"): "the journal window is a Cypher write wrapped by Txn_Begin/End (b-08-live-footprints): its SQL rows of rdf_edges/rdf_labels run the row hooks (schema.py:774,780 -> AdjIndex/LabelIndex -> Adjacency.RowPut/PutLabel, Adjacency.cls:477-505,768)",
    ("extra:Graph_KG.Txn_Begin/Txn_End/Txn_Undo", "global:^NKG"): "as above: Adjacency.Put/RowPut also mark ^NKG (Adjacency.cls:80-120)",
    ("guard:engine writers (_ledger_check call sites)", "global:^KG"): "the guarded engine writers' SQL rows run the row hooks (schema.py:774,780 -> Adjacency)",
    ("guard:engine writers (_ledger_check call sites)", "global:^NKG"): "as above (Adjacency.Put marks ^NKG)",
}


HASHED = re.compile(r"^global:\^[A-Za-z0-9]{4}\.[A-Za-z0-9]{4}\.\d+$")


def journal_control(sites, modules: Modules):
    reach = Reach(modules, sites)
    known = {s["store"] for s in sites} | set(DECLARED)
    exp_cache = {}

    def stores_of(s):
        if s["store"] not in exp_cache:
            exp_cache[s["store"]] = {st for st, _c in expand_store(s["store"], known)} | {s["store"]}
        return exp_cache[s["store"]]
    by_store_mods = defaultdict(set)
    for s in sites:
        for st in stores_of(s):
            by_store_mods[st] |= set(s["modules"])
    rows = []
    cache = {}
    for mod, eid, src, st, run in journal_pairs():
        st = norm_journal_store(st)
        root = st.split("(")[0]
        if src not in cache:
            cache[src] = reach.from_source(src)
        rsites, rmods = cache[src]
        rmods = rmods | {mod}

        def match(store_set):
            return st in store_set or any(x.startswith(st + "(") for x in store_set) or \
                (("(" in st) and (root in store_set or root + "(?)" in store_set))
        if C.is_system_global(root.replace("global:", "")) or root.startswith("global:^odd"):
            verdict, basis = "system-global", "IRIS class/SQL dictionary global, not a product store"
        elif (eid, st) in READ_EXPLAINED:
            verdict, basis = "explained-by-reading", READ_EXPLAINED[(eid, st)]
        elif any(k in (eid or "") for k in CALLER_SQL):
            verdict, basis = "explained-caller-sql", next(v for k, v in CALLER_SQL.items() if k in (eid or ""))
        elif HASHED.match(st):
            ddl_routes = [s for s in rsites if s.get("kind") == "ddl" and ("kg_emb_" in s["store"] or "kg_eemb_" in s["store"])]
            route_dml = [s for s in rsites if s["store"] in ("sql:kg_emb_*", "sql:kg_eemb_*")]
            if not ddl_routes and route_dml:
                ddl_routes = [s for s in sites if s.get("kind") == "ddl" and ("kg_emb_" in s["store"] or "kg_eemb_" in s["store"])]
            if ddl_routes and route_dml:
                verdict, basis = "explained-table-created-in-action", f"hashed storage of a routed table the action creates ({ddl_routes[0]['file']}:{ddl_routes[0]['line']}) and writes ({route_dml[0]['file']}:{route_dml[0]['line']})"
            else:
                verdict, basis = "census-gap", "hashed DDL storage the census does not attribute"
        else:
            hit = [s for s in rsites if match(stores_of(s))]
            if hit:
                h = hit[0]
                hook = h["method"].startswith("Graph.KG.Adjacency.") and any(x.startswith("Graph.KG.AdjIndex") or x.startswith("Graph.KG.LabelIndex") for x in [])
                verdict, basis = "explained-by-reached-site", f"{h['file']}:{h['line']} {h['method']}"
            else:
                writers = set()
                for k, v in by_store_mods.items():
                    if match({k}):
                        writers |= v
                if not writers:
                    verdict, basis = "census-gap", "no census site writes this store"
                elif writers & rmods:
                    verdict, basis = "explained-by-module", "a census writer in a reached module: " + ",".join(sorted(writers & rmods))
                else:
                    verdict, basis = "store-only", "census writers " + ",".join(sorted(writers)) + " not reached from the entry's source"
        rows.append({"module": mod, "entry": eid, "source": src, "store": st, "run": run, "verdict": verdict,
                     "basis": basis})
    return rows


# ------------------------------------------------------------------------------------------------ self-test

SEED_CLS_X = '''Class Graph.KG.ZZSeedSecondWriter
{
ClassMethod Stray(pG, pS, pP, pO)
{
    Set tN = 1, ^KG("out", pG, pS, pP, pO) = 1
}
ClassMethod Delegating(pG, pS, pP, pO)
{
    Do ##class(Graph.KG.Adjacency).Put(pG, pS, pP, pO)
}
ClassMethod Indirect(pName)
{
    Set tRef = $Name(^BM25Idx(pName))
    Kill @tRef
}
}
'''
SEED_PY_X = '''
def seeded_dynamic_writer(self, cursor, rid):
    cursor.execute(f"DELETE FROM {self._t('rdf_reifications')} WHERE reifier_id = ?", [rid])


def seeded_dynamic_global(iris_obj, g):
    gname = "^KG"
    iris_obj.kill(gname, "bucket", g)
'''
SEED_CLS_OWNER = '''Class Graph.KG.ZZSeedOwnWriter
{
ClassMethod OwnWrite(pG, pS, pP, pO)
{
    Set ^KG("out", pG, pS, pP, pO) = 1
}
}
'''


def self_test() -> int:
    inv = json.loads(INVENTORY.read_text())
    seeds = [("iris_src/src/Graph/KG/ZZSeedSecondWriter.cls", SEED_CLS_X),
             ("iris_vector_graph/zz_seed_owner.py", SEED_PY_X),
             ("iris_src/src/Graph/KG/ZZSeedOwnWriter.cls", SEED_CLS_OWNER)]
    inv["files"] += [{"file": seeds[0][0], "owners": ["16"]}, {"file": seeds[1][0], "owners": ["16"]},
                     {"file": seeds[2][0], "owners": ["04"]}]
    inv["entries"] += [{"file": seeds[0][0], "kind": "os-method", "name": f"Graph.KG.ZZSeedSecondWriter.{n}", "line": 1,
                        "end": 1, "owners": ["16"]} for n in ("Stray", "Delegating", "Indirect")]
    inv["entries"] += [{"file": seeds[2][0], "kind": "os-method", "name": "Graph.KG.ZZSeedOwnWriter.OwnWrite", "line": 1,
                        "end": 1, "owners": ["04"]}]
    mods = Modules(inv)
    sites = C.census(seeds)
    report, _ = check(sites, mods, gs=set())
    def cls_of(store, m):
        return report.get(store, {}).get("writers", {}).get(m, {}).get("class")
    found = {(s["method"], s["store"]) for s in sites}
    expect = {
        "Set target after a multi-target Set (16 writes 04's ^KG(out)) flagged undeclared":
            cls_of('global:^KG("out")', "16") == "undeclared" and ("Graph.KG.ZZSeedSecondWriter.Stray", 'global:^KG("out")') in found,
        "ADR-0011 violation reported for the seeded class":
            any(a["site"].endswith("ZZSeedSecondWriter.Stray") for a in report.get('global:^KG("out")', {}).get("adr_violations", [])),
        "delegating call into Adjacency.Put is not a write site":
            not any(s["method"].endswith(".Delegating") for s in sites),
        "indirection Kill @$Name(^BM25Idx(...)) resolved and flagged (16 writes 07's store)":
            cls_of("global:^BM25Idx", "16") == "undeclared",
        "Python f-string table name resolved to rdf_reifications and flagged (16 writes 15's store)":
            cls_of("sql:Graph_KG.rdf_reifications", "16") == "undeclared",
        "Native API kill with a variable global name resolved to ^KG(bucket) and flagged (16 writes 05's store)":
            cls_of('global:^KG("bucket")', "16") == "undeclared",
        "the owner's own write is classified owner, not a second writer":
            cls_of('global:^KG("out")', "04") == "owner",
        "the owner's own write breaks no ADR (seeded class name is not Adjacency: reported)":
            any(a["site"].endswith("ZZSeedOwnWriter.OwnWrite") for a in report.get('global:^KG("out")', {}).get("adr_violations", [])),
    }
    ok = all(expect.values())
    for k, v in expect.items():
        print(("PASS " if v else "FAIL ") + k)
    print("self-test", "PASS" if ok else "FAIL", f"({sum(expect.values())}/{len(expect)})")
    return 0 if ok else 1


# ------------------------------------------------------------------------------------------------ main

def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    import os
    out = Path(sys.argv[sys.argv.index("--out") + 1])
    out.mkdir(parents=True, exist_ok=True)
    files = [(str(p.relative_to(REPO)), p.read_text(errors="replace")) for p in C.product_files()]
    sites = C.census(files)
    mods = Modules()
    report, ddl = check(sites, mods)
    pm = per_module(report)
    comp = completeness(sites, Path(os.environ["RUN_DIR"]) / REG_CENSUS_REL)
    guard = product_guard(sites)
    jc = journal_control(sites, mods)
    jsum = defaultdict(lambda: defaultdict(int))
    for r in jc:
        jsum[r["module"]][r["verdict"]] += 1
    multi = {st: r for st, r in report.items() if not r["single_owner"]}
    res = {"files": len(files), "sites": len(sites), "stores": len(report), "multi_writer_stores": len(multi),
           "undeclared_pairs": sum(1 for r in report.values() for w in r["writers"].values() if w["class"] == "undeclared"),
           "declared_pairs": sum(1 for r in report.values() for w in r["writers"].values() if w["class"] == "declared"),
           "conditional_pairs": sum(1 for r in report.values() for w in r["writers"].values() if w["class"] == "undeclared-conditional"),
           "adr_violations": sum(len(r["adr_violations"]) for r in report.values()),
           "completeness": comp, "product_guard": guard,
           "journal_control": {"pairs": len(jc), "by_module": {k: dict(v) for k, v in sorted(jsum.items())},
                               "census_gaps": [r for r in jc if r["verdict"] == "census-gap"],
                               "store_only": [r for r in jc if r["verdict"] == "store-only"]},
           "declared": DECLARED, "no_ivg_owner": NO_IVG_OWNER, "skipped_unknown_tokens": C.SKIPPED_UNKNOWN,
           "report": report, "per_module": pm, "ddl": ddl,
           "site_attribution": [{k: s[k] for k in ("file", "line", "method", "store", "verb", "mechanism", "modules", "attribution")} for s in sites]}
    (out / "ownership.json").write_text(json.dumps(res, indent=1, default=list))
    (out / "journal-control.json").write_text(json.dumps(jc, indent=1))
    print(f"{res['files']} files, {res['sites']} write sites, {res['stores']} stores; {res['multi_writer_stores']} stores with more than one writer module")
    print(f"second-writer pairs: undeclared {res['undeclared_pairs']}, declared co-writers {res['declared_pairs']}, conditional {res['conditional_pairs']}; ADR class violations {res['adr_violations']}")
    print(f"completeness vs registered census: {comp['registered_sites']} sites, missing {len(comp['missing'])}, incompatible {len(comp['incompatible'])}")
    print(f"product guard (test_adjacency_single_writer): {guard}")
    print(f"journal control: {len(jc)} pairs; " + "; ".join(f"{k}: {dict(v)}" for k, v in sorted(jsum.items())))
    for st, r in sorted(multi.items()):
        ws = ", ".join(f"{m}:{w['class']}" for m, w in sorted(r["writers"].items()))
        print(f"  {st:42} owner {r['owner']}  writers {ws}" + (f"  ADR {len(r['adr_violations'])}" if r["adr_violations"] else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
