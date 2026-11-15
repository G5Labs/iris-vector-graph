#!/usr/bin/env python3
"""Write experiment/playbook-completion/footprints/15.json: declared footprints (from the pinned source) of module 15's
entry points, each writer compared with the journal observation of its live run where one exists."""
from __future__ import annotations

import json
import os
from pathlib import Path

RUN = Path(os.environ["RUN_DIR"]) / "breadth-c" / "15"
OUT = Path(__file__).resolve().parents[3] / "footprints" / "15.json"
PIN = "3eaa79cf77d3e0a879b2cced634cf2729d81499e"


def j(part, key, sub=None):
    d = json.loads((RUN / f"{part}.json").read_text())
    r = d[key] if sub is None else d[key][sub]
    return r


def obs(run, part, key, sub=None):
    r = j(part, key, sub)
    return {"run": run, "label": r["label"], "error": r["error"],
            "stores_written": r["stores_written"],
            "stores_written_in_txn": r["stores_written_in_txn"],
            "stores_with_nontransactional_increments": r["stores_with_nontransactional_increments"],
            "stores_written_outside_any_txn": r["stores_written_outside_any_txn"],
            "outermost_transactions": r["outermost_transactions"], "records": r["records"]}


def check(entry):
    """Compare declared writes with the journal: an undeclared store or a write outside a transaction is a mismatch.
    ^KG / ^NKG non-transactional increments (graph-version stamps) are expected and not counted."""
    jr = entry.get("journal")
    if not jr:
        return entry
    declared = set(entry["writes"])
    seen = set(jr["stores_written_in_txn"]) | set(jr["stores_written_outside_any_txn"])
    undeclared = sorted(seen - declared)
    missing = sorted(declared - set(jr["stores_written"])) if not jr["error"] else []
    outside = jr["stores_written_outside_any_txn"]
    ok = not undeclared and not outside and (jr["outermost_transactions"] <= 1 or not entry["claims_atomic"]["value"])
    mm = []
    if undeclared:
        mm.append(f"undeclared writes {undeclared}")
    if outside:
        mm.append(f"writes outside any transaction {outside}")
    if entry["claims_atomic"]["value"] and jr["outermost_transactions"] > 1:
        mm.append(f"{jr['outermost_transactions']} outermost transactions where one is claimed")
    if missing:
        jr["declared_not_written_this_run"] = missing
    jr["match"] = ok
    jr["mismatch"] = "; ".join(mm) or None
    return entry


E = []


def add(entry, role, source, reads, writes, transaction, locks, claims, journal=None, notes=None):
    E.append(check({"entry": entry, "role": role, "source": source, "reads": reads, "writes": writes,
                    "transaction": transaction, "locks": locks,
                    "claims_atomic": {"value": claims[0], "source": claims[1]},
                    "journal": journal, "notes": notes}))


GK = "sql:Graph_KG."
# ---------------------------------------------------------------- reification
add("IRISGraphEngine.reify_edge", "writer", "iris_vector_graph/_engine/schema.py:3264-3332",
    [GK + "rdf_edges", GK + "rdf_labels", GK + "rdf_props", GK + "nodes"],
    [GK + "nodes", GK + "rdf_labels", GK + "rdf_props", GK + "rdf_reifications", "global:^KG"],
    "one outermost txn (WriteTxn; create_node nested)", [],
    (True, "iris_vector_graph/_engine/schema.py:3271-3279 docstring: 'leaves nothing behind ... in one transaction'"),
    obs("c15-live-reify", "reify", "reify_edge"),
    "^KG(\"label\",0,...) written by create_node's label index. Every row lands in the default graph whatever the "
    "edge's graph (F-1502). Refusal paths (duplicate reifier id: -119; missing edge) journaled 0 records.")
add("IRISGraphEngine.get_reifications", "reader", "iris_vector_graph/_engine/schema.py:3335-3358",
    [GK + "rdf_reifications", GK + "rdf_props"], [], "none (single SELECT)", [], (False, "reader"),
    obs("c15-live-reify", "reify", "get_reifications"), "Join on reifier id only; no graph predicate.")
add("IRISGraphEngine.delete_reification", "writer", "iris_vector_graph/_engine/schema.py:3361-3397",
    [], [GK + "rdf_reifications", GK + "rdf_props", GK + "rdf_labels", GK + "nodes", "global:^KG"],
    "one outermost txn (WriteTxn)", [],
    (True, "schema.py:3366-3368 docstring: 'rolled back, so nothing is deleted'"),
    obs("c15-live-delreif2", "delreif2", "delete_reification"),
    "^KG(\"label\") index entries go through the rdf_labels row hook; deletes are graph-blind (F-1503). With edges "
    "present the FK fk_edges_source refuses the node delete and the whole txn rolls back (c15-live-delreif).")
# ---------------------------------------------------------------- bridges / crosswalk
add("IRISGraphEngine.fhir_bridge_add", "writer", "iris_vector_graph/_engine/fhir.py:390-442",
    [], [GK + "fhir_bridges", GK + "code_crosswalk"], "one outermost txn (write_txn)", [],
    (True, "INT-B1.1; fhir.py:416 '4.7.0: one transaction of IVG's'"), obs("c15-live-bridge", "bridge", "fhir_bridge_add"))
add("IRISGraphEngine.get_kg_anchors", "reader", "iris_vector_graph/_engine/fhir.py:444-481",
    [GK + "fhir_bridges", GK + "nodes"], [], "none", [], (False, "reader"),
    obs("c15-live-bridge", "bridge", "get_kg_anchors"), "JOIN nodes ON node_id only (fhir.py:470-477): F-1507.")
add("IRISGraphEngine.code_crosswalk_add", "writer", "iris_vector_graph/_engine/fhir_graph.py:607-645",
    [], [GK + "code_crosswalk"], "one outermost txn (write_txn)", [], (True, "fhir_graph.py:640"),
    obs("c15-live-bridge", "bridge", "code_crosswalk_add"))
add("IRISGraphEngine.migrate_fhir_bridges_to_crosswalk", "writer", "iris_vector_graph/_engine/fhir_graph.py:647-680",
    [GK + "fhir_bridges"], [GK + "code_crosswalk"], "one outermost txn (write_txn) around every upsert", [],
    (True, "fhir_graph.py:662"), obs("c15-live-bridge", "bridge", "migrate"),
    "Namespace-wide: rewrites every bridge row (run only when no other lane's rows existed).")
# ---------------------------------------------------------------- table mappings
add("IRISGraphEngine.map_sql_table", "writer", "iris_vector_graph/_engine/fhir.py:88-145",
    ["sql:INFORMATION_SCHEMA.COLUMNS"], [GK + "table_mappings"], "one outermost txn (write_txn)", [],
    (True, "fhir.py:127"), obs("c15-live-tablemap", "tablemap", "map_qualified"),
    "Catalog lookup uses schema 'USER' for an unqualified name (F-1504). Mapping is namespace-wide (no graph key).")
add("IRISGraphEngine.map_sql_relationship", "writer", "iris_vector_graph/_engine/fhir.py:147-197",
    [GK + "table_mappings (cache)"], [GK + "relationship_mappings"], "one outermost txn (write_txn)", [],
    (True, "fhir.py:177"), obs("c15-live-tablemap", "tablemap", "map_rel"))
add("IRISGraphEngine.remove_table_mapping", "writer", "iris_vector_graph/_engine/fhir.py:237-255",
    [GK + "table_mappings"], [GK + "table_mappings", GK + "relationship_mappings"], "one outermost txn (write_txn)", [],
    (True, "fhir.py:248; INT-M1.7"), obs("c15-live-tablemap", "tablemap", "remove"))
add("IRISGraphEngine.list_table_mappings", "reader", "iris_vector_graph/_engine/fhir.py:199-235",
    [GK + "table_mappings", GK + "relationship_mappings"], [], "none", [], (False, "reader"),
    obs("c15-live-tablemap", "tablemap", "list"))
add("IRISGraphEngine.attach_embeddings_to_table", "writer", "iris_vector_graph/_engine/fhir.py:267-367",
    ["<mapped SQL table>", GK + "nodes", "<route vector table>"], ["<routed node vector table kg_emb_<hash>>",
                                                                   GK + "embedding_registry"],
    "per row: store_embedding's own (nested) txn; no outer txn", [],
    (False, "fhir.py:347 '4.7.0: no conn.commit(): store_embedding commits its own part'"), None,
    "Not run live: needs an embedding model (embed_text). Per-row commits by design; a failure mid-table leaves "
    "earlier rows embedded and is reported in errors/error_ids (INT-M1.11).")
# ---------------------------------------------------------------- RDF / SHACL / PROV
add("IRISGraphEngine.register_namespace", "writer", "iris_vector_graph/_engine/rdf_export.py:53-76",
    [GK + "rdf_namespaces"], [GK + "rdf_namespaces"], "one outermost txn (write_txn)", [], (True, "rdf_export.py:63"),
    obs("c15-live-rdf", "rdf", "register_namespace"))
add("IRISGraphEngine.export_rdf", "reader", "iris_vector_graph/_engine/rdf_export.py:96-157",
    [GK + "rdf_labels", GK + "rdf_props", GK + "rdf_edges", GK + "rdf_namespaces"], ["file:<path>"], "none", [],
    (False, "reader; INT-R1 'changes no graph'"), obs("c15-live-rdf", "rdf", "export_rdf"),
    "Builds the whole rdflib ConjunctiveGraph in memory before writing (F-1510, c15-live-memory).")
add("IRISGraphEngine.validate_shacl", "reader", "iris_vector_graph/_engine/shacl.py:203-242",
    [GK + "rdf_labels", GK + "rdf_props", GK + "rdf_edges"], [], "none", [], (False, "reader; INT-S1"),
    obs("c15-live-rdf", "rdf", "validate_shacl"))
add("IRISGraphEngine.prov_export", "reader", "iris_vector_graph/_engine/prov.py:107-139",
    ["global:^KG (TemporalIndex.QueryWindow, default graph)"], ["file:<path>"], "none", [], (False, "reader"),
    obs("c15-live-rdf", "rdf", "prov_export_ok"), "A failed window read raises; no file (F-1501).")
# ---------------------------------------------------------------- FHIR graph (server code); journal blocked on Community
blocked = ("blocked-access: HS.FHIRServer.* / HS_FHIRServer SQL schema (IRIS for Health FHIR repository) absent on "
           "Community 2026.1 in AUDITC (c15-live-register), so no FHIR graph can be registered and these paths "
           "cannot run; footprint from source only")
add("IRISGraphEngine.fhir_graph_register -> Graph.KG.FHIRGraph.Register", "writer",
    "iris_vector_graph/_engine/fhir_graph.py:190-249; iris_src/src/Graph/KG/FHIRGraph.cls:167-279",
    ["sql:HS_FHIRServer.Repo", "sql:HS_FHIRServer.RepoInstance", GK + "fhir_graphs", "sql:HS_FHIRServer_Storage_Json.SearchColumn"],
    [GK + "fhir_graphs (INSERT or UPDATE settings; UPDATE json_links; UPDATE last_error)",
     "DDL: Graph_KG.fhir_graphs, fhir_unresolved, fhir_definitions, fhir_canonical_refs (first register, Python side)",
     "+ Rebuild's footprint when json_links changed"],
    "none: the upsert and the json_links update are separate autocommit statements; Catch returns an error without "
    "undoing the upsert", [], (False, "no atomicity claim; INT-F3.9 states the intended 'failed register leaves settings'"),
    obs("c15-live-register", "register", "engine_register"),
    "Live on Community: the refusal ('no FHIR repository') precedes every write: 0 journal records (SYS-I3 holds on "
    "this path). The F-1511 window (a throw after the upsert) needs a repository: " + blocked)
for name, src, w, txn in [
    ("Graph.KG.FHIRGraph.Rebuild", "FHIRGraph.cls:448-540",
     [GK + "nodes", GK + "rdf_labels", GK + "rdf_props", GK + "rdf_edges", GK + "rdf_reifications", GK + "kg_EdgeEmbeddings",
      GK + "docs", GK + "kg_NodeEmbeddings", GK + "kg_NodeEmbeddings_optimized", "<routed vector tables>",
      GK + "fhir_unresolved", GK + "fhir_definitions", GK + "fhir_canonical_refs", GK + "fhir_graphs", "global:^KG (when not Indexed)"],
     "SyncAllDefinitions: one txn per 200 definitions; RunBatch: one txn per 200 keys (no watermark); DropNode: one txn "
     "per stale key; final fhir_graphs UPDATE (watermarks, counts) autocommit"),
    ("Graph.KG.FHIRGraph.SyncOnce", "FHIRGraph.cls:543-628",
     [GK + "nodes", GK + "rdf_labels", GK + "rdf_props", GK + "rdf_edges", GK + "rdf_reifications", GK + "kg_EdgeEmbeddings",
      GK + "docs", GK + "kg_NodeEmbeddings", GK + "kg_NodeEmbeddings_optimized", "<routed vector tables>",
      GK + "fhir_unresolved", GK + "fhir_definitions", GK + "fhir_canonical_refs", GK + "fhir_graphs (wm_rsrc/wm_ver in batch txn; last_sync autocommit)",
      "global:^KG (when not Indexed)"],
     "Rederive batches (txn each) when interp stale; RunBatch: one txn per 200 keys INCLUDING its watermark UPDATE "
     "(absolute SET, FHIRGraph.cls:1966-1968); final last_sync UPDATE autocommit"),
    ("Graph.KG.FHIRGraph.Reinterpret", "FHIRGraph.cls:631-662",
     [GK + "rdf_edges (compartment)", GK + "rdf_labels", GK + "rdf_props", GK + "fhir_graphs (interp_version)", "global:^KG"],
     "Rederive: one txn per batch; SetInterpVersion autocommit"),
]:
    add(name, "writer", "iris_src/src/Graph/KG/" + src,
        ["sql:<repo Rsrc/RsrcVer/search tables>", GK + "fhir_graphs", GK + "nodes", GK + "rdf_edges", GK + "fhir_unresolved"],
        w, txn, ["Lock +^IVG.FHIRGraph(graph):0 (busy when held); Eraser.EraseGraph takes no such lock (HD-1503)"],
        (True, "per batch only: FHIRGraph.cls:15-18 'Each batch of keys is resynced and its watermark advanced inside one transaction'"),
        None, blocked + ". Watermarks are read in Open() before the lock is taken (FHIRGraph.cls:550-556 vs 1736-1737).")
add("Graph.KG.FHIRGraph.Schedule / Unschedule", "writer", "iris_src/src/Graph/KG/FHIRGraph.cls:667-741",
    [GK + "fhir_graphs", "sql:%SYS.Task (IRISSYS)"],
    ["sql:%SYS.Task (Task Manager definition, %Save / %DeleteId)", GK + "fhir_graphs (task_id, interval_s)"],
    "none: task %Save/%DeleteId and the fhir_graphs UPDATE are separate, no TSTART", [],
    (False, "no claim; SYS-I4 requires both or neither"), None, blocked + " (F-C1501).")
add("Graph.KG.FHIRGraphSyncTask.OnTask", "writer", "iris_src/src/Graph/KG/FHIRGraphSyncTask.cls:14-27",
    ["as SyncOnce"], ["as SyncOnce"], "as SyncOnce", ["as SyncOnce"], (False, "as SyncOnce"), None,
    "Background %SYS.Task job; busy counts as success (INT-F6.2). " + blocked)
add("Graph.KG.FHIRGraph.RecordError", "writer", "iris_src/src/Graph/KG/FHIRGraph.cls:3101-3109",
    [], [GK + "fhir_graphs (last_error)"], "autocommit, after the failed batch rolled back", [],
    (False, "docstring 'outside any transaction'"), None, blocked)
add("Graph.KG.FHIRGraph.Status / LinkReport / ResolveConcepts / ExpandConcepts / CoverageReport / ConceptGaps / "
    "PatientConcepts / TokenPaths / IndexedTokenParams / CompartmentParams / GroupPPR / GroupByPatient", "reader",
    "iris_src/src/Graph/KG/FHIRGraph.cls:282-1712", [GK + "fhir_graphs", GK + "nodes", GK + "rdf_edges",
                                                   GK + "fhir_unresolved", GK + "code_crosswalk",
                                                   "sql:<repo token/search tables>", "global:^KG"],
    [], "none", ["LinkReport takes no lock (INT-F8.3)"], (False, "readers"),
    obs("c15-live-register", "register", "calls", "status"),
    "Live only on the refusal path (unregistered graph: 0 records for every call). " + blocked)
add("IRISGraphEngine.fhir_patient_anchors", "reader", "iris_vector_graph/_engine/fhir_graph.py:563-596",
    [GK + "fhir_graphs", "via PatientConcepts"], [], "none", [], (False, "reader"),
    obs("c15-live-register", "register", "calls", "patient_anchors_no_graph_arg"),
    "No FHIR tables: {'graphs': [], 'anchors': []} with 0 journal records (INT-C4.2).")
add("cypher_api /api/cypher (FHIR anchors: _patient_anchors, _resolve_patient_anchors)", "reader",
    "iris_vector_graph/cypher_api.py:290-347,351-378", ["as fhir_patient_anchors / get_kg_anchors", "http:FHIR_BASE_URL"],
    [], "none (query run separately through _run_cypher)", ["cypher_api._engine_lock"], (False, "reader"), None,
    "Error swallowing on fhir_patient_anchors observed live (c15-live-anchors, F-1508).")

validated = [e for e in E if e["journal"]]
mismatches = [{"entry": e["entry"], "run": e["journal"]["run"], "mismatch": e["journal"]["mismatch"]}
              for e in validated if not e["journal"]["match"]]
doc = {"module": "15", "pin": PIN,
       "generated_by": "experiment/playbook-completion/live/breadth-c/15/make_footprints15.py",
       "journal_oracle": "experiment/playbook-completion/traces/journal.py via live/breadth-c/jcheck.py (AUDITC, "
                         "db /usr/irissys/mgr/auditc/, filtered to the lane's process)",
       "store_naming": "sql:<schema.table> | global:^Root | file:<path>",
       "entries": E, "validated": len(validated),
       "validated_writers": sum(1 for e in validated if e["role"] == "writer"),
       "mismatches": mismatches,
       "notes": ["Classification: stores_with_nontransactional_increments are IRIS $INCREMENT/ID counters and graph "
                 "version stamps (^KG(\"__version\"), ^NKG(\"$meta\",\"version\")) that IRIS journals as "
                 "non-transactional inside the bracket; they are expected and not mismatches.",
                 "Every FHIR-graph writer is source-only: " + blocked + "."]}
OUT.write_text(json.dumps(doc, indent=1) + "\n")
print(len(E), "entries;", len(validated), "journal-validated;", len(mismatches), "mismatches")
for m in mismatches:
    print(m)
