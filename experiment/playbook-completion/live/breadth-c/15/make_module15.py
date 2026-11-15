#!/usr/bin/env python3
"""Write experiment/playbook-completion/modules/15.json: module 15 (INT) entry points, gate status and IRIS features."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "modules" / "15.json"
inv = json.loads((ROOT / "models" / "breadth-c" / "inventory.json").read_text())
fa = json.loads((ROOT / "findings" / "audit" / "15.json").read_text())
fp = json.loads((ROOT / "footprints" / "15.json").read_text())
PIN = "3eaa79cf77d3e0a879b2cced634cf2729d81499e"
FHIR_BLOCK = ("HS.FHIRServer.* / HS_FHIRServer SQL schema (IRIS for Health FHIR repository) absent on IRIS Community "
              "2026.1 in AUDITC (live c15-live-register: 0 classes, 0 tables, Register refuses 'no FHIR repository')")

mine = [e for e in inv["entries"] if "15" in e["owners"]]
by_kind = {}
for e in mine:
    by_kind[e["kind"]] = by_kind.get(e["kind"], 0) + 1
public_os = [e["name"] for e in mine if e["kind"] == "os-method" and e["method_kind"] == "ClassMethod"
             and "Private" not in e["flags"] and "Internal" not in e["flags"]]

entry_points = {
    "total_inventory": len(mine),
    "by_kind_inventory": by_kind,
    "inventory_corrections": [
        "cli-command 'cli status' (cli.py:189) is the top-level `ivg status` of module 17, matched to 15 only by the "
        "symbol 'status' in the inventory rule; not a module-15 entry point.",
        "The `ivg fhir` subcommands register/rebuild/sync/status/links/schedule (cli.py:323-414) are module-15 entry "
        "points the inventory attributed to 17 only (handler names fhir_* do not match the rule's symbols): 6 more "
        "cli-command entries. There is no `ivg fhir unschedule`, `reinterpret` or erase command.",
        "FHIRSearchTool.__call__ (fhir_bridge.py:328-345) and GetPatientKGNeighborhoodTool.__call__ "
        "(fhir_bridge.py:376-397) are public callables the AST rule skips (dunder): 2 more py-api entries.",
        "Of 78 ObjectScript methods, %d are public ClassMethods callable through the Native API by any user with "
        "EXECUTE; the rest are Private/Internal ClassMethods or instance Methods reachable only through Open()." % len(public_os),
    ],
    "total_corrected": len(mine) - 1 + 6 + 2,
    "public_server_classmethods": public_os,
    "lexical_reconciliation": {"uncovered_by_name": len(inv["reconciliation"]["15"]["uncovered"]),
                               "result_after_review": "all 86 are covered under another name (engine wrapper or "
                               "statement wording) or internal helpers; see classification"},
    "classification_of_lexically_uncovered": {
        "covered_under_another_name": [
            "FHIRGraph.LinkReport/fhir_link_report -> INT-F8.3/F8.4", "FHIRGraph.Reinterpret/fhir_reinterpret -> INT-F7",
            "ResolveConcepts/fhir_resolve_concepts -> INT-C1.3..C1.7", "IndexedTokenParams -> INT-C1.5",
            "CoverageReport/fhir_coverage_report -> INT-C3.1/C3.2", "ConceptGaps/TokenPaths/fhir_concept_gaps -> INT-C3.3",
            "PatientConcepts/fhir_patient_anchors -> INT-C4..C4.3", "ExpandConcepts/fhir_expand_concepts -> INT-C1.1/C1.2",
            "GroupByPatient/GroupPPR/Group -> INT-C2..C2.6", "InterpVersion/InterpStale/SetInterpVersion/InterpBlock/Rederive -> INT-D12, INT-F5.6/F5.7, INT-F7.1",
            "ParseDenylist -> INT-F3.6", "LoadProps/SyncProps -> INT-F1.19..F1.21", "DefaultLinksJson/LinksJson/ParseLinks -> INT-F1.10, INT-F1.13",
            "RunBatch -> INT-F5.2", "SyncDefinition/ResolveCands/CanonKey -> INT-F1.11, INT-F5.9", "BodyRel/ReadResource/Extract/Walk/WalkArray -> INT-F1.14",
            "DropNode/DeleteEdge -> INT-F1.18, INT-F2.5", "EnsureNode -> INT-F1.1/F1.2", "UnresolvedCounts -> INT-F8",
            "Pascal -> INT-F1.19 (category code as label)", "fhir_graph_status/schedule/unschedule -> INT-F8, INT-F9",
            "get_table_mapping/get_rel_mapping -> INT-M1.9/M1.10", "fhir_bridge_add -> INT-B1.1/B1.2",
            "get_kg_anchors (engine and fhir_bridge) -> INT-B1.3/B1.4", "prov_as_dict -> INT-V1.8", "prov_export_from_cypher -> INT-V1.7",
            "list_namespaces -> INT-R1.15", "export_rdf_from_cypher -> INT-R1.16/R1.17", "graph_iri/graph_id_of_iri -> INT-R1.3",
            "Violation.to_dict/ValidationReport.to_dict -> INT-S1.8/S1.9", "extract_icd_codes(_from_bundle) -> INT-B1.7",
            "unified_clinical_pipeline, GetPatientKGNeighborhoodTool -> INT-B1.9/B1.10 (old pipeline)",
            "FHIRSearchTool -> INT-B1.8 (F-1505)", "link_predicate/parse_json_links -> INT-F1.13",
            "sql/fhir_bridges.sql, sql/rdf_reifications.sql DDL -> INT-D16, INT-D19 (legacy SQL loader: HD-0103)"],
        "internal_helpers": ["CheckOwnTask (Private, INT-F9.2)", "HasText/NodeSet/TokenRows/Crosswalked (Private)",
                             "SplitValue/KeepIndex (Private)", "RTable/VTable/TableExists/Query/Exec/ExecTolerant/Scalar/Q/Err (SQL helpers)",
                             "LoadRoutes (Private)"],
    },
    "omissions": [
        {"name": "Graph.KG.FHIRGraph.Schedule/Unschedule two-store write", "file:line": "iris_src/src/Graph/KG/FHIRGraph.cls:701-729",
         "why": "No statement says the Task Manager task and fhir_graphs.task_id change together; they do not (F-C1501)."},
        {"name": "FHIR sync DeleteEdge leaves reifier nodes", "file:line": "iris_src/src/Graph/KG/FHIRGraph.cls:2585-2599",
         "why": "INT-E1.7 covers only EraseGraph; the sync's edge drop deletes the rdf_reifications link and leaves the reifier node (F-1502 notes)."},
        {"name": "reify_edge graph-blind NOT EXISTS guards", "file:line": "iris_vector_graph/_engine/schema.py:3305-3320",
         "why": "The label/property guards test s (and key/label) with no graph_id, so a same-id node in a named graph suppresses the default-graph reifier's label/props; no statement."},
        {"name": "delete_node reifier cleanup in a second transaction", "file:line": "iris_vector_graph/_engine/nodes_edges.py:2176-2199",
         "why": "INT-E1.9 states the outcome but not that it is a separate transaction (F-C1502; entry point owned by module 03)."},
        {"name": "Public server helper ClassMethods Open, Pascal, Q", "file:line": "iris_src/src/Graph/KG/FHIRGraph.cls:1713,2573,3091",
         "why": "Callable over the Native API with no statement; side-effect free (reads/formatting), so low risk."},
    ],
    "cells_without_entry_point": [],
    "cells_notes": [
        "Every cell command maps to an entry point: FHIR graph x {register, rebuild, sync, reinterpret, status, schedule, "
        "unschedule} -> engine fhir_* / Graph.KG.FHIRGraph methods; erase -> erase_graph (module 12); reifier x {reify, "
        "read, delete, erase} -> reify_edge, get_reifications, delete_reification, erase_graph; rdf extra x {export, "
        "cypher export, shacl check, prov export} -> export_rdf, export_rdf_from_cypher, validate_shacl, prov_export; "
        "table mapping x {map table, map link, remove, attach vectors, list} -> map_sql_table, map_sql_relationship, "
        "remove_table_mapping, attach_embeddings_to_table, list_table_mappings.",
        "State 'rdflib 8' is not reachable: rdflib 8 is not published on PyPI (latest 7.6.0, 2026-11-13); its cells were "
        "exercised only by an in-process simulation (c15-probe-noiris).",
        "States 'idle'/'busy' of FHIR graph are not reachable on Community: " + FHIR_BLOCK + ".",
    ],
    "entry_points_without_cells": [
        "code crosswalk (code_crosswalk_add, migrate_fhir_bridges_to_crosswalk)",
        "FHIR bridge (fhir_bridge_add, get_kg_anchors, fhir_bridge.get_kg_anchors, unified_clinical_pipeline, tools)",
        "concept pipeline (fhir_resolve_concepts, fhir_expand_concepts, fhir_concept_ppr, fhir_coverage_report, fhir_concept_gaps, fhir_patient_anchors)",
        "RDF prefix registry (register_namespace, list_namespaces)", "PROV lookups (prov_as_dict, prov_export_from_cypher)",
        "FHIR sync task (Graph.KG.FHIRGraphSyncTask.OnTask: run, busy, error)", "FHIR link report", "`ivg fhir` CLI",
        "Cypher API patient anchors (/api/cypher with fhir_patient_id)"],
    "background_jobs": ["Graph.KG.FHIRGraphSyncTask (Extends %SYS.Task.Definition; FHIRGraphSyncTask.cls:6-29), created "
                        "by FHIRGraph.Schedule (FHIRGraph.cls:686-701); one SyncOnce per run, busy counts as success"],
}

gates = [
    {"gate": "3.1 statements/cells", "status": "open",
     "reason": "Statements and cells exist for FHIR graph, reifier, rdf extra and table mapping; every cell command has "
               "an entry point. Open: entities with statements but no cells (crosswalk, bridge, concept pipeline, prefix "
               "registry, sync task, CLI, Cypher anchors) and 5 statement omissions (entry_points.omissions); cell "
               "(FHIR graph, busy, erase) is open on HD-1503. INDEX/grade gate not re-run by this lane.",
     "evidence": ["models/breadth-c/inventory.json", "experiment/playbook-uplift/ontology/15-integrations.md"],
     "remaining": "Add cells for the uncovered entities; statements for F-C1501, sync DeleteEdge/reifier and the reify guards."},
    {"gate": "3.2 IRIS features relied on", "status": "blocked",
     "reason": "Verified live: P-1501 (FHIRGraph compiles on Community, Register refuses with no repository), P-1509 "
               "(default schema SQLUser), FK fk_edges_source and pk_reifications enforced, journaling of SQL/global "
               "writes inside TSTART. Blocked: P-1502/P-1503/P-1504/P-1511 (FHIR repository internals) by " + FHIR_BLOCK +
               "; P-1505 (Task Manager minutes) and P-1506 (caller privileges in dynamic SQL) unchecked; P-1507 "
               "unverifiable (rdflib 8 unpublished); P-1508 (pySHACL contexts) and P-1510 (MAXSTRING) not run.",
     "evidence": ["c15-live-register", "c15-live-tablemap", "c15-live-delreif", "c15-live-reify", "c15-probe-noiris"],
     "remaining": "Run the FHIR premises on an IRIS for Health image (enterprise compose); a P-1506 privilege probe; a P-1510 window probe."},
    {"gate": "3.3 L1/L2/refinement/controls/progress", "status": "open",
     "reason": "Bounded explorer models by the main lane (models/breadth-c, exhaustive within bounds): HD-1503 erase "
               "during sync as-built violates 'watermark soundness' (cmc-fhir-erase-as-built: batch k1 wm=1, unlocked "
               "EraseGraph resets wm 0, next batch writes k2,k3 and wm=3, k1 <= wm missing), reviewed (erase takes "
               "^IVG.FHIRGraph(g)) passes (cmc-fhir-reviewed), control 'erase skips the sync lock' caught "
               "(cmc-fhir-ctl-erase-lock), witness cmc-fhir-wit-refill; HD-1502 durable removal as-built violates "
               "(cmc-fhir-durable-as-built: a running sync writes after unschedule+erase); HD-1504 no progress past an "
               "unreadable key without repair (cmc-fhir-poison-as-built-norepair, expected), progress with the "
               "operator-repair premise (cmc-fhir-poison-as-built-repair) and in the quarantine alternative "
               "(cmc-fhir-poison-quarantine); F-1511 as-built refusal violates (cmc-register-as-built-refusal), reviewed "
               "passes (cmc-register-reviewed), control caught (cmc-register-ctl-upsert). Open: no L1/L2 machines or "
               "Verus refinement for module 15 (explorer evidence only).",
     "evidence": ["cmc-fhir-erase-as-built", "cmc-fhir-reviewed", "cmc-fhir-ctl-erase-lock", "cmc-fhir-wit-refill",
                  "cmc-fhir-durable-as-built", "cmc-fhir-poison-as-built-norepair", "cmc-fhir-poison-as-built-repair",
                  "cmc-fhir-poison-quarantine", "cmc-register-as-built-refusal", "cmc-register-as-built-links",
                  "cmc-register-reviewed", "cmc-register-ctl-upsert", "cmc-register-wit"],
     "remaining": "L1/L2 machines and proved refinement for the FHIR projection; trace replay once a FHIR namespace exists."},
    {"gate": "3.3a mechanisms and invariant write-sets", "status": "failed",
     "reason": "semantics/writesets.json has no plan for any module-15 writer (reify_edge, delete_reification, FHIR "
               "Rebuild/SyncOnce/Reinterpret, Schedule, table-map writers, crosswalk/bridge), so the (INV-isolation / "
               "erasure, plan) pairs were never generated; two of them are live product defects: reify_edge + "
               "erase_graph leave tenant content live (F-1502), delete_reification crosses graphs (F-1503). FHIR sync "
               "is an unledgered external writer (HD-1501, intent-undecided).",
     "evidence": ["c15-live-reify", "c15-live-delreif2", "experiment/playbook-uplift/semantics/writesets.json"],
     "remaining": "Add the module-15 plans to the write-set generator and discharge or record each pair."},
    {"gate": "3.4 statements/ownership/storage-order/declared-reads", "status": "failed",
     "reason": "Footprints declared for %d entry points; %d journal-validated (%d writers) with 0 mismatches between "
               "declared and observed writes and no write outside a transaction. Ownership fails: the reifier rows of a "
               "named-graph edge are owned by the default graph (F-1502), delete_reification writes every graph's rows "
               "(F-1503), get_kg_anchors reads nodes of any graph (F-1507). FHIR writers' footprints are source-only "
               "(blocked)." % (len(fp["entries"]), fp["validated"], fp["validated_writers"]),
     "evidence": ["footprints/15.json", "c15-live-reify", "c15-live-delreif2", "c15-live-bridge", "c15-live-tablemap", "c15-live-rdf", "c15-live-register"],
     "remaining": "Journal-validate Rebuild/SyncOnce/Reinterpret/Schedule on an IRIS for Health namespace."},
    {"gate": "3.5 handlers/lock plans/decoders/status maps", "status": "failed",
     "reason": "Decoder: _fhir_call maps {'status':'error'} to FHIRGraphError and passes 'busy' through as a reply "
               "(fhir_graph.py:183-188); the CLI maps busy to exit 2 (INT-F6.3). Status map defects: the Cypher API "
               "turns any anchor-read failure into anchor_source 'fhir_bridge' with 200 (F-1508, live); the old pipeline "
               "maps a walk failure to a graph fact (F-1509); the rdflib refusal names the wrong cause (F-1506). Lock "
               "plan: Rebuild/SyncOnce/Reinterpret take Lock +^IVG.FHIRGraph(g):0 (FHIRGraph.cls:455,550,638); "
               "Eraser.EraseGraph and Register/Schedule take none (HD-1503).",
     "evidence": ["c15-live-anchors", "c15-probe-noiris", "iris_src/src/Graph/KG/FHIRGraph.cls:448-662"],
     "remaining": "Decide HD-1503 lock plan; fix status maps."},
    {"gate": "3.6 composition conditions", "status": "open",
     "reason": "Composition of FHIR sync with erasure (HD-1502/1503), with the ledger (HD-1501: sync writes unrecorded "
               "even in strict mode) and with redaction (refill makes the target live) is intent-undecided; reifier "
               "rows cross graph ownership (F-1502) so graph-level composition of erase and reify fails as built.",
     "evidence": ["experiment/playbook-completion/decisions.md HD-1501..1504", "c15-live-reify"],
     "remaining": "Main-lane models; maintainer decisions HD-1501..1504."},
    {"gate": "3.7 validation kinds (crash/reconnect/ambiguous ack, 1 vs N processes)", "status": "blocked",
     "reason": "Crash: RunBatch rolls back a batch with its watermark (FHIRGraph.cls:1923-1978; ^IVG.FHIRGraphFault hook; "
               "e2e tests exist, not run: " + FHIR_BLOCK + "). Ambiguous ack: SyncOnce/Rebuild retries are safe by "
               "idempotent resync (inspected FHIRGraph.cls:19-21); a retried reify_edge after an unseen commit is "
               "refused by pk_reifications (SQLCODE -119, observed live) rather than duplicated; bridge/crosswalk/"
               "table-map writers are upserts. 1 vs N: the sync lock's busy answer (INT-F6.1) is blocked; reify and "
               "table-map writers were run single-process only. Upstream e2e/integration tests were not run in AUDITC "
               "because their fixtures run initialize_schema and namespace-wide DELETEs (tests/conftest.py:815,1084-1106).",
     "evidence": ["c15-live-reify", "c15-run-unit"],
     "remaining": "Run tests/e2e/test_fhirgraph_failures_e2e.py and test_231_fhir_graph_sync_e2e.py on IRIS for Health; a two-process reify/erase probe."},
    {"gate": "3.8 account", "status": "open",
     "reason": "All 11 original findings audited (6 reproduced live, 2 by lane probes, 1 by model, 2 confirmed in source with live premise "
               "checks) plus 2 new (F-C1501, F-C1502); decisions HD-1501..1504 remain maintainer questions; trust "
               "premises partly verified (gate 3.2).",
     "evidence": ["findings/audit/15.json", "footprints/15.json"],
     "remaining": "Maintainer review; fixes or recorded decisions for each finding."},
]

env_features = [
    {"feature": "Dynamic SQL in server code (%SQL.Statement %ExecDirect/%Prepare, %SQLCODE) with the caller's SQL privileges",
     "source": "iris_src/src/Graph/KG/FHIRGraph.cls:3039-3095", "used_by": "every Graph.KG.FHIRGraph method", "checked": "partly: refusal paths live (c15-live-register); privilege premise P-1506 not checked"},
    {"feature": "Nested transactions TSTART/TCOMMIT/TROLLBACK 1 with $TLevel; SQL and global writes of one process in one transaction",
     "source": "iris_src/src/Graph/KG/FHIRGraph.cls:513-534,1927-1974,1985-2001; iris_vector_graph/_write_txn.py", "used_by": "Rebuild, SyncOnce, RunBatch, reify_edge, delete_reification, table-map and crosswalk writers",
     "checked": "c15-live-reify, c15-live-delreif (rollback after FK refusal), c15-live-bridge, c15-live-tablemap"},
    {"feature": "LOCK with zero timeout and $Test (busy answer); lock release at process end (P-0004)",
     "source": "iris_src/src/Graph/KG/FHIRGraph.cls:455-456,550-551,638-639", "used_by": "Rebuild, SyncOnce, Reinterpret", "checked": "no (blocked: no FHIR graph)"},
    {"feature": "Task Manager %SYS.Task (%New/%OpenId/%Save/%DeleteId/AssignSettings; DailyFrequency/DailyIncrement in minutes) and %SYS.Task.Definition OnTask",
     "source": "iris_src/src/Graph/KG/FHIRGraph.cls:667-741; iris_src/src/Graph/KG/FHIRGraphSyncTask.cls:6-29", "used_by": "fhir_graph_schedule/unschedule, background sync", "checked": "no (blocked)"},
    {"feature": "InterSystems FHIR server storage (HS_FHIRServer.Repo/RepoInstance, JsonAdvSQL Rsrc/RsrcVer change feed with rising IDs, SearchColumn metadata, HS.FHIRServer.Schema compartment params, soft deletes)",
     "source": "iris_src/src/Graph/KG/FHIRGraph.cls:13-18,167-226,1770-1860,2653-2660", "used_by": "Register, Rebuild, SyncOnce, ResolveConcepts, reports",
     "checked": "absent on Community 2026.1 (c15-live-register)"},
    {"feature": "%DynamicObject/%DynamicArray JSON and the long-string limit (3,641,144 characters)",
     "source": "iris_src/src/Graph/KG/FHIRGraph.cls (all replies); iris_src/src/Graph/KG/TemporalIndex.cls:688-722 (QueryWindow for PROV)", "used_by": "every FHIR call, prov_export", "checked": "JSON replies live; MAXSTRING not driven"},
    {"feature": "Catalog: INFORMATION_SCHEMA.TABLES/COLUMNS, $SYSTEM.SQL.Schema.TableExists, default schema SQLUser for unqualified names",
     "source": "iris_vector_graph/_engine/fhir.py:112-126; iris_vector_graph/_engine/fhir_graph.py:196-202; iris_src/src/Graph/KG/Eraser.cls:1155-1159", "used_by": "map_sql_table, lazy FHIR tables, EraseFHIRGraphRows", "checked": "c15-live-tablemap (Default()=SQLUser), c15-live-register"},
    {"feature": "SQL constraints: composite foreign keys rdf_edges(graph_id,s/o_id) -> nodes(graph_id,node_id), fk_labels_node, primary key pk_reifications",
     "source": "iris_vector_graph/schema.py:42-43,408,514-520", "used_by": "delete_reification, reify_edge", "checked": "c15-live-delreif (SQLCODE -124), c15-live-reify (SQLCODE -119)"},
    {"feature": "SQL INSERT OR UPDATE upsert",
     "source": "iris_vector_graph/_engine/fhir.py:420-440; iris_vector_graph/_engine/fhir_graph.py:600-605", "used_by": "fhir_bridge_add, code_crosswalk_add, migrate", "checked": "c15-live-bridge"},
    {"feature": "Native API classMethodValue on the DB-API connection's process (shared transaction context)",
     "source": "iris_vector_graph/_engine/fhir_graph.py:183-188; iris_vector_graph/_engine/nodes_edges.py:1512-1527", "used_by": "all fhir_* engine calls, erase_graph", "checked": "c15-live-register"},
    {"feature": "rdf_labels/rdf_edges row hooks maintaining ^KG(\"label\"/\"out\"/\"in\") (adjacency functional index, Graph.KG.Adjacency.Indexed)",
     "source": "iris_src/src/Graph/KG/FHIRGraph.cls:56-57; iris_src/src/Graph/KG/Adjacency.cls:540", "used_by": "delete_reification, reify_edge, FHIR sync EnsureNode/DeleteEdge", "checked": "c15-live-delreif2 (^KG label entries removed with the rows)"},
    {"feature": "Non-transactional $INCREMENT counters and graph-version stamps journaled inside the bracket",
     "source": "global ^KG(\"__version\"), ^NKG(\"$meta\",\"version\") (observed)", "used_by": "every graph writer", "checked": "c15-live-reify (journal classification)"},
]

model_requests = [
    {"id": "HD-1502", "question": "erase vs a scheduled FHIR sync task",
     "model_hint": "as-built: EraseGraph keeps the fhir_graphs row and task, sets wm_rsrc=wm_ver=0 and interp NULL "
                   "(Eraser.cls:180-183,1151-1180); the next task tick (SyncOnce) re-projects the whole repository, so erased "
                   "content is live again and a following redaction is refused (target_live). reviewed (decisions.md "
                   "HD-1502): transient erase may refill; durable removal = unschedule (verified paused) + erase, and the "
                   "invariant 'after durable removal no content of G is live until an explicit re-register' holds. "
                   "Negative control: durable removal without unschedule must be caught. Include F-C1501 (orphan task "
                   "after a failed Schedule bookkeeping) as an as-built variant."},
    {"id": "HD-1503", "question": "erase during a running sync",
     "model_hint": "as-built: SyncOnce reads watermarks in Open() BEFORE taking Lock +^IVG.FHIRGraph(g):0 "
                   "(FHIRGraph.cls:550-556, 1736-1737); each RunBatch commits its rows together with an ABSOLUTE "
                   "UPDATE fhir_graphs SET wm=? (FHIRGraph.cls:1966-1968); EraseGraph takes no lock and resets wm to 0 "
                   "in its own transaction. Interleaving batch_k commit < erase commit < batch_k+1 commit leaves G holding "
                   "only batch k+1 rows with wm past rows it lacks, until a rebuild. Invariant: whenever no txn is open, "
                   "every live repository key with ID <= wm has its node in G. reviewed: erase takes the sync lock (busy "
                   "or wait) or the batch's watermark write is compare-and-set against the value read under the lock."},
    {"id": "HD-1504", "question": "one unreadable resource and sync progress",
     "model_hint": "as-built: a poison key makes ResyncKey throw (FHIRGraph.cls:2380-2397, 2976-2988); the batch and its "
                   "watermark roll back together; every later sync fails on the same batch (last_error names it). "
                   "Properties: safety 'wm never passes an unapplied key' holds; progress AG EF(wm = max) fails while the "
                   "poison stays and holds once a 'repair' action exists (working assumption: fail, name the key, "
                   "document recovery). Alternative quarantine design: progress unconditional, with invariant 'every "
                   "skipped key is recorded'; negative control: a skip that advances wm without recording must be caught."},
    {"id": "F-1511", "question": "non-atomic Register",
     "model_hint": "see findings/audit/15.json F-1511 model_hint"},
]

model_results = {
    "HD-1503": ["cmc-fhir-erase-as-built (expected-violation)", "cmc-fhir-reviewed (pass)",
                "cmc-fhir-ctl-erase-lock (control caught)", "cmc-fhir-wit-refill (witness)"],
    "HD-1502": ["cmc-fhir-durable-as-built (expected-violation)"],
    "HD-1504": ["cmc-fhir-poison-as-built-norepair (expected progress violation)", "cmc-fhir-poison-as-built-repair (pass, repair premise)",
                "cmc-fhir-poison-quarantine (pass, alternative)"],
    "F-1511": ["cmc-register-as-built-refusal (expected-violation)", "cmc-register-as-built-links (pass)",
               "cmc-register-reviewed (pass)", "cmc-register-ctl-upsert (control caught)", "cmc-register-wit (witness)"],
}

# ---------------------------------------------------------------- refusal audit (5c)
import os  # noqa: E402
rf_path = Path(os.environ["RUN_DIR"]) / "breadth-c" / "15" / "refusals.json"
rf = json.loads(rf_path.read_text()) if rf_path.exists() else {}
x_statements = []
for line in (ROOT.parent / "playbook-uplift" / "ontology" / "15-integrations.md").read_text().splitlines():
    if line.startswith("| INT-"):
        c = [v.strip() for v in line.split("|")[1:-1]]
        if c[2] == "X":
            x_statements.append(c[0])
live_ref = {}
for k, v in rf.items():
    if k.startswith("INT-") and isinstance(v, dict):
        sid = k.split()[0]
        ok = bool(v.get("error") or v.get("raised")) and v.get("records", 0) == 0
        if sid == "INT-V1.4":
            ok = (v.get("error") is None and isinstance(v.get("result"), dict) and v["result"].get("activities") == 0
                  and v.get("records", 0) == 0)
        live_ref.setdefault(sid, []).append({"case": k, "refused_without_writes": ok,
                                             "error": (v.get("error") or v.get("raised") or str(v.get("result")))[:160]})
for sid, extra in {"INT-F3.2": "c15-live-register", "INT-F8.1": "c15-live-register", "INT-M1.3": "c15-live-tablemap",
                   "INT-M1.6": "c15-live-tablemap", "INT-M1.8": "c15-live-tablemap", "INT-E1.4": "c15-live-reify",
                   "INT-C5.1": "c15-live-bridge"}.items():
    live_ref.setdefault(sid, []).append({"case": extra, "refused_without_writes": True, "error": "see run"})
unit_tested = {"INT-F1.13", "INT-F5.8", "INT-F8.2", "INT-C2.6", "INT-C5.1", "INT-M1.12", "INT-R1.18", "INT-S1.4",
               "INT-S1.6", "INT-V1.4", "INT-V1.10"}
blocked_x = {"INT-F1.5", "INT-F1.14", "INT-F1.20", "INT-F2.3", "INT-F2.4", "INT-F3.3", "INT-F3.4", "INT-F9.2"}
refusal_table = []
for sid in x_statements:
    ev = live_ref.get(sid, [])
    if ev and all(e["refused_without_writes"] for e in ev):
        st = "holds-live"
    elif ev:
        st = "mixed (see cases)"
    elif sid in blocked_x:
        st = "blocked-access (needs a FHIR repository)"
    elif sid in unit_tested:
        st = "holds-run (upstream unit test in c15-run-unit)"
    elif sid == "INT-R1.19":
        st = "product-defect (F-1506)"
    elif sid == "INT-E1.5":
        st = "inspected only (strict ledger mode may not be enabled in shared AUDITC)"
    else:
        st = "inspected only"
    refusal_table.append({"statement": sid, "status": st, "live_cases": ev})
n_live = sum(1 for r in refusal_table if r["status"] == "holds-live")
n_blocked = sum(1 for r in refusal_table if r["status"].startswith("blocked"))
n_other = len(refusal_table) - n_live - n_blocked

M3 = "main lane models"
gates_by_id = {
    "3.1-cells": {"status": "open",
                  "evidence": ["experiment/playbook-uplift/ontology/15-integrations.md ## Cells", "modules/15.json entry_points.cells_notes"],
                  "remaining": "Every existing cell is defined or assigned (FHIR graph/busy/erase -> HD-1503), but entities with "
                               "statements have no cells: code crosswalk, FHIR bridge, concept pipeline, prefix registry, sync task, "
                               "`ivg fhir` CLI, Cypher anchors."},
    "3.1-coverage": {"status": "open",
                     "evidence": ["models/breadth-c/inventory.json reconciliation.15", "modules/15.json entry_points"],
                     "remaining": "All 86 lexically uncovered entry points reviewed (covered under another name or internal); "
                                  "5 statement omissions remain (entry_points.omissions: F-C1501 Schedule/Unschedule pair, sync "
                                  "DeleteEdge leaving reifiers, reify guards, delete_node second transaction, public helper "
                                  "ClassMethods). Background job and lifecycle operations are covered."},
    "3.1-intent": {"status": "closed",
                   "evidence": ["experiment/playbook-completion/intent/HD-1501.md", "experiment/playbook-completion/intent/HD-1502.md",
                                "experiment/playbook-completion/intent/HD-1503.md", "experiment/playbook-completion/intent/HD-1504.md",
                                "experiment/playbook-completion/decisions.md HD-1501..1504"],
                   "remaining": "Maintainer answers (HD-1501 and HD-1503 are assumptions; HD-1502 and HD-1504 supported)."},
    "3.2-coverage": {"status": "blocked",
                     "evidence": ["modules/15.json env_features", "c15-live-register", "c15-live-tablemap", "c15-live-delreif"],
                     "remaining": "FHIR repository internals (P-1502..P-1504, P-1511), Task Manager (P-1505), privilege premise "
                                  "(P-1506) and MAXSTRING (P-1510) are not checked against the IRIS contract: " + FHIR_BLOCK + "."},
    "3.3-L1": {"status": "open", "evidence": [], "remaining": M3 + " (explorer models exist; no L1 machine)"},
    "3.3-L2": {"status": "open", "evidence": [], "remaining": M3 + " (no L2 machine over the real layout)"},
    "3.3-refinement": {"status": "open", "evidence": [], "remaining": M3 + " (no proved refinement)"},
    "3.3-controls": {"status": "open", "evidence": ["cmc-fhir-ctl-erase-lock", "cmc-register-ctl-upsert"],
                     "remaining": M3 + " (explorer controls caught; no proof-level controls)"},
    "3.3-model-check": {"status": "closed",
                        "evidence": [r.split(" ")[0] for v in model_results.values() for r in v],
                        "remaining": "Bounded (exhaustive within bounds); as-built vs reviewed for HD-1502/1503/1504 and F-1511 "
                                     "with controls and witnesses (main lane)."},
    "3.3a-writesets": {"status": "failed",
                       "evidence": ["experiment/playbook-uplift/semantics/writesets.json (no module-15 plan)",
                                    "$RUN_DIR/checks/writer-census.json uncovered_writers: FHIRGraph DeleteEdge, DropNode, EnsureNode, ResyncKey, SyncProps",
                                    "c15-live-reify", "c15-live-delreif2"],
                       "remaining": "Generate (invariant, plan) pairs for reify_edge, delete_reification, FHIR Rebuild/SyncOnce/"
                                    "Reinterpret/Schedule and the table-map/crosswalk writers; F-1502 and F-1503 are recorded "
                                    "violations of the isolation/erasure pairs."},
    "3.4-statements": {"status": "open",
                       "evidence": ["footprints/15.json"],
                       "remaining": "No statement is proved equal to a model evaluation; footprints are declared and %d of %d "
                                    "journal-validated (0 mismatches); FHIR writers source-only (blocked)." % (fp["validated"], len(fp["entries"]))},
    "3.4-ownership": {"status": "failed",
                      "evidence": ["c15-live-reify", "c15-live-delreif2", "c15-live-bridge", "footprints/15.json"],
                      "remaining": "Reifier rows of a named-graph edge are owned by the default graph (F-1502); "
                                   "delete_reification writes every graph's rows (F-1503); no ownership self-test for module 15."},
    "3.4-storage-order": {"status": "closed",
                          "evidence": ["$RUN_DIR/checks/storage-order.json (109 sites, none in a module-15 file)",
                                       "iris_src/src/Graph/KG/FHIRGraph.cls:593 (watermark feed ORDER BY ID)",
                                       "iris_src/src/Graph/KG/FHIRGraph.cls:366-368 (link report ORDER BY)",
                                       "iris_vector_graph/_engine/fhir_graph.py:578 (ORDER BY graph_id)"],
                          "remaining": "Confirmed by this lane: no TOP / FETCH FIRST / LIMIT in module-15 SQL (grep of "
                                       "FHIRGraph*.cls, fhir*.py, rdf_export, _rdf_utils, shacl, prov, reify lines "
                                       "schema.py:3264-3397, sql/fhir_bridges.sql, sql/rdf_reifications.sql, including SQL text "
                                       "inside %SQL.Statement strings). The one order-sensitive scan (SyncOnce advancing the "
                                       "watermark to the last ID seen) orders by ID; Rebuild's unordered scan is order-free "
                                       "(watermarks set to pre-scan maxima at the end); ConceptGaps/GroupByPatient top-N use "
                                       "subscript-ordered local arrays (deterministic ties). Self-test is the checker's (main lane)."},
    "3.4-declared-reads": {"status": "open",
                           "evidence": ["footprints/15.json (reads declared from source)"],
                           "remaining": "Reads are declared but not checked mechanically (the journal sees writes only); no "
                                        "declared-reads self-test. get_kg_anchors reads nodes of every graph (F-1507)."},
    "3.5-handlers": {"status": "open", "evidence": ["c15-live-*", "c15-run-unit"],
                     "remaining": "No handler is proved; engine entry points are evidenced by live runs and unit tests only."},
    "3.5-lockplans": {"status": "failed",
                      "evidence": ["iris_src/src/Graph/KG/FHIRGraph.cls:455,550,638", "iris_src/src/Graph/KG/Eraser.cls:47-57",
                                   "cmc-fhir-erase-as-built"],
                      "remaining": "Sync/Rebuild/Reinterpret take Lock +^IVG.FHIRGraph(g):0; EraseGraph, Register and Schedule "
                                   "take none; the as-built erase-during-sync model violates watermark soundness (HD-1503). "
                                   "Lock plan not proved; FHIR lock behaviour blocked live."},
    "3.5-decoders": {"status": "failed",
                     "evidence": ["iris_vector_graph/_engine/fhir_graph.py:183-188", "c15-live-anchors", "c15-probe-noiris"],
                     "remaining": "_fhir_call maps {'status':'error'} to FHIRGraphError (live: every refusal surfaced as "
                                  "FHIRGraphError); status-map defects: Cypher API anchor fallback (F-1508), old pipeline walk "
                                  "status (F-1509), rdflib refusal cause (F-1506)."},
    "3.6-frame": {"status": "open", "evidence": [], "remaining": "No frame obligations generated for module-15 statement shapes."},
    "3.6-row-permutation": {"status": "open", "evidence": ["3.4-storage-order above"],
                            "remaining": "Order-independence argued for the FHIR scans (storage-order gate) but not proved."},
    "3.6-keys": {"status": "open", "evidence": ["c15-live-reify (pk_reifications -119)", "iris_vector_graph/schema.py:303-323,514-520"],
                 "remaining": "Key invariants (fhir_graphs PK graph_id, rdf_reifications PK reifier_id, crosswalk key) observed "
                              "enforced by IRIS, not proved; reifier_id is namespace-wide while the reified edge is per graph."},
    "3.6-fk": {"status": "open",
               "evidence": ["c15-live-delreif (fk_edges_source refuses, txn rolls back)", "iris_vector_graph/schema.py:42-43,408"],
               "remaining": "rdf_reifications.edge_id and fhir_* tables have no FK (reifier nodes outlive their edges: F-1502); "
                            "FK conditions not discharged by proof."},
    "3.6-capacity": {"status": "open",
                     "evidence": ["iris_src/src/Graph/KG/FHIRGraph.cls:30 (BATCHSIZE 200)", "FHIRGraph.cls:2730-2732 (walk 64/10000)",
                                  "c15-live-memory (F-1510)", "P-1510"],
                     "remaining": "Long-string limit for JSON replies and PROV windows (P-1510) not driven; RDF export memory "
                                  "is linear (F-1510); batch sizes stated but not checked against the IRIS lock table."},
    "3.7-trace-replay": {"status": "blocked", "evidence": [],
                         "remaining": "No FHIR sync trace can be recorded on Community (" + FHIR_BLOCK + "); reify/erase journal "
                                      "traces exist (c15-live-reify) but no module-15 machine to replay them through."},
    "3.7-lock-log": {"status": "blocked", "evidence": [],
                     "remaining": "The sync lock is only taken on a registered FHIR graph: " + FHIR_BLOCK + "."},
    "3.7-mutation": {"status": "open", "evidence": ["c15-run-unit"],
                     "remaining": "No mutation testing of module-15 code."},
    "3.8-findings-disposed": {"status": "closed",
                              "evidence": ["findings/audit/15.json"],
                              "remaining": "Observation-only: all 11 original findings and 2 new ones recorded with evidence and "
                                           "disposition; the product obligations stay failed/open."},
    "5c-refusals": {"status": "open" if n_blocked or n_other else "closed",
                    "evidence": ["c15-live-refusals", "c15-live-register", "c15-run-unit", "modules/15.json refusals"],
                    "remaining": "%d of %d X statements hold live (refused with 0 journal writes), %d blocked on the FHIR "
                                 "repository, %d evidenced by upstream unit tests / inspection / a finding (F-1506 for "
                                 "INT-R1.19)." % (n_live, len(refusal_table), n_blocked, n_other)},
}

summary = fa["summary"]
doc = {"module": "15", "name": "INT", "pin": PIN, "lane": "breadth-c",
       "gates_by_id": gates_by_id, "refusals": refusal_table, "model_results": model_results,
       "entry_points": entry_points, "gates": gates, "env_features": env_features,
       "model_requests": model_requests,
       "findings_summary": summary,
       "findings_new": [f["id"] for f in fa["findings"] if f["id"].startswith("F-C")],
       "blockers": [FHIR_BLOCK + ": blocks live checks of Register's post-upsert window (F-1511), Rebuild/SyncOnce/"
                    "Reinterpret/Schedule footprints, the sync lock, HD-1502..1504 traces and P-1502..1505.",
                    "rdflib 8 is not published (PyPI latest 7.6.0): F-1506 / P-1507 cannot be run against the real release.",
                    "Upstream e2e/integration tests for module 15 were not run: their fixtures call initialize_schema and "
                    "namespace-wide DELETEs, which this lane may not do in the shared AUDITC namespace."],
       "runs": ["c15-live-register", "c15-live-reify", "c15-live-delreif", "c15-live-delreif2", "c15-live-bridge",
                "c15-live-tablemap", "c15-live-anchors", "c15-live-rdf", "c15-live-memory", "c15-probe-noiris",
                "c15-run-unit", "c15-live-refusals"]}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(doc, indent=1) + "\n")
print("entry points", entry_points["total_inventory"], "->", entry_points["total_corrected"], "| public server classmethods",
      len(public_os), "| gates", {g["gate"].split()[0]: g["status"] for g in gates}, "| findings", summary)
