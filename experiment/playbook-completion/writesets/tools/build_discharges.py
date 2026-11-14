#!/usr/bin/env python3
"""Build writesets/DISCHARGES.json: one discharge for every census obligation of gate 3.3a-writesets
(matrix-input/writer-census-obligations.json, from the registered census run followup-writer-census) and one entry per
module-level 3.3a-writesets cell that matrix/obligations.json has open.

    python experiment/playbook-completion/writesets/tools/build_discharges.py [--check]

The per-writer table below is the analysis (writesets/WRITESETS.md explains the method). A writer is taken as its
entry point: what one call of it writes, its callees included, because that is what a caller can make it do and what
the live probes (writesets/live/ws_probes.py) exercise. Each obligation gets exactly one of
  lemma   the writer's writes cannot break the invariant (grade proved / mc / live / inspected; inspected is weakest)
  guard   a check in the code stops the writer (path:lines; confirmed live where a run is cited)
  finding a finding whose evidence covers this writer (the cited runs are that evidence) - the cell closes, the
          product obligation stays failed
  open    with the exact reason
--check exits 1 when the written file differs from what the table produces (used by check_discharges.py).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PC = Path(__file__).resolve().parents[2]          # experiment/playbook-completion
OUT = PC / "writesets" / "DISCHARGES.json"
CENSUS = PC / "matrix-input" / "writer-census-obligations.json"

# --------------------------------------------------------------------------------------------- shared citations

LR_LIVEROWS = "iris_src/src/Graph/KG/LedgerRedact.cls:149-178"
LR_ENTRY = "iris_src/src/Graph/KG/LedgerRedact.cls:202-211"
LR_BATCH = "iris_src/src/Graph/KG/LedgerRedact.cls:302-330"
LR_FINAL = "iris_src/src/Graph/KG/LedgerRedact.cls:409-416"
LR_BLOCKS = "iris_src/src/Graph/KG/LedgerRedact.cls:258-269"
LR_MATCHES = "iris_src/src/Graph/KG/LedgerRedact.cls:89-112"
LR_CLEAR = "iris_src/src/Graph/KG/LedgerRedact.cls:333-378"
FK_EDGES = "iris_vector_graph/schema.py:34-44"
FK_LABELS = "iris_vector_graph/schema.py:403-409"
PROPS_NOFK = "iris_vector_graph/schema.py:411-418"
REPLAY_CANON = "iris_vector_graph/ledger/replay.py:588-642"
REPLAY_COMPARE = "iris_vector_graph/ledger/replay.py:645-698"
WRITETXN = "iris_vector_graph/_write_txn.py:1-30"
ALLOC_STMT = "iris_src/src/Graph/KG/LedgerApply.cls:160-169"
ISMARKED = "iris_src/src/Graph/KG/Adjacency.cls:736-748"
QUALSJSON = "iris_src/src/Graph/KG/LedgerApply.cls:420-434"
ORIG_MARKER = "experiment/playbook-uplift/semantics/WRITESETS.md:47-49"
ORIG_NLT = "experiment/playbook-uplift/semantics/WRITESETS.md:61-63"
ORIG_REPLAY = "experiment/playbook-uplift/semantics/WRITESETS.md:88-90"
ORIG_STMT = "experiment/playbook-uplift/semantics/WRITESETS.md:74-76"

R_FK = "run:ws-live-fk-guard"
R_FC1301 = "run:ws-live-fc1301-delete-reification"
R_COLL = "run:ws-live-stmt-collision"
R_PURGE = "run:ws-live-stmt-purge"
R_MIG = "run:ws-live-migrations"
R_FHIR = "run:ws-live-fhir-blocked"
M_FC1301 = ["run:core-m2-as-built-bypass-rollback", "run:core-m2-as-built-commit-rollback"]


def ins_run(name):
    return f"run:ws-live-ins-{name}"


def D(kind, grade, evidence, findings=(), reason=""):
    return {"discharge": kind, "grade": grade, "evidence": list(evidence), "findings": list(findings),
            "reason": reason}


# ------------------------------------------------------------------------------- discharge shapes (per invariant)

def marker_inserter(sites, run=None, note=""):
    ev = ([run] if run else []) + sites + [LR_BLOCKS, LR_FINAL, ORIG_MARKER]
    if run:
        return D("finding", "live", ev, ["F-C1307"],
                 "The writer inserts node (or property) rows with caller-chosen ids, so it can make a marked target "
                 "live; nothing on its path reads ^IVG.Ledger(\"redacting\") (only ledger commits do, through "
                 "BlocksCommit). Live: with the marker set, the writer wrote the target's rows, Final then refused "
                 "'became live again', the marker stayed, verify() answered redaction_in_progress and a re-run was "
                 "refused target_live: the run is held open as F-C1307 records (its live evidence was "
                 "engine.create_node; this run is the same defect for this writer). Contradicts the original "
                 "discharge 'not guarded: RED-B5.2' for the bypass plans." + note)
    return D("finding", "inspected", ev, ["F-C1307"],
             "The writer inserts node (or property) rows with caller-chosen ids into a graph and no line of it reads "
             "^IVG.Ledger(\"redacting\") (only ledger commits do, through BlocksCommit); it can therefore make a "
             "marked target live while its redaction runs, and Final then refuses and keeps the marker: F-C1307's "
             "defect. Not run live for this writer (graded inspected)." + note)


def nlt_inserter(sites, run=None, note=""):
    ev = ([run] if run else []) + sites + [LR_ENTRY, LR_BATCH, LR_FINAL, ORIG_NLT]
    if run:
        return D("finding", "live", ev, ["F-C1350"],
                 "Live: the redaction passed its entry liveness check (target erased) and waited for the head lock; "
                 "the writer wrote the target's rows and committed; every tombstone of the run was written after "
                 "that commit (journal addresses), while the target was live: a record became a tombstone while its "
                 "content was live (RED-B1.1). Batches do not re-check liveness (BatchInLock) and the writer does "
                 "not read the marker. Recorded as F-C1350." + note)
    return D("finding", "inspected", ev, ["F-C1350"],
             "The writer inserts rows of a target with caller-chosen ids and does not read the marker; BatchInLock "
             "tombstones without re-checking liveness, so a write by it after a run's entry check is followed by "
             "tombstones of the now-live target: F-C1350's defect (live for 12 other writers). Not run live for "
             "this writer (graded inspected)." + note)


def replay_lemma(sites, run=None, note=""):
    ev = ([run] if run else []) + sites + [REPLAY_CANON, REPLAY_COMPARE, ORIG_REPLAY]
    reason = ("INV-replay holds under 'no unrecorded writes' (RPL-B3). The writer writes content rows and no ledger "
              "record, so every effect it has is an unrecorded write: compare() either sees it and classifies it "
              "unrecorded_writes (RPL-B7.1), or the write is outside the replay abstraction (a temporal-marked row, a "
              "node's graph, a reserved property, ekey) and replay still equals the store in that abstraction. The "
              "writer cannot make replay disagree with the store unseen." + note)
    if run:
        return D("lemma", "live", ev, [], reason + " Live: the writer's process wrote content and no ^IVG.Ledger "
                 "node (journal); verify() went equal -> diverges, classification unrecorded_writes.")
    return D("lemma", "inspected", ev, [], reason + " Inspected only for this writer.")


def stmt_lemma_rows(sites, what, note=""):
    return D("lemma", "inspected", sites + [ALLOC_STMT, FK_EDGES, ORIG_STMT],
             [], f"INV-stmt (live statements are exactly the live recorded edges) reads ^IVG.Ledger(\"stmt\"/\"tuple\") "
             f"and rdf_edges. {what} The writer writes no ^IVG.Ledger node (statements are allocated only by "
             "LedgerApply.AllocStmt), so the set of live statements is unchanged and no recorded edge loses its row." + note)


def fk_lemma(sites, what, extra_runs=(), note=""):
    return D("lemma", "inspected", list(extra_runs) + [R_FK] + sites + [FK_EDGES, FK_LABELS, LR_LIVEROWS],
             [], f"{what} A target is live iff LiveRows counts a node, label, property or edge row of it. Every edge "
             "row that matches a target has an endpoint node row in the same graph with the matching id "
             "(fk_edges_source / fk_edges_dest on (graph_id, s|o_id)), and every label row has its node row "
             "(fk_labels_node), and that node row is itself counted for the target. So edge (or label) rows alone "
             "never turn a target from not live to live, nor (deleted, committed or not) from live to not live: the "
             "writer can neither make a marked or erased target live nor let a run's liveness check pass on a live "
             "target. Live: the foreign keys refuse an edge and a label without their node (ws-live-fk-guard). "
             "It writes no ^IVG.Ledger node." + note)


def nonkey_lemma(sites, what, extra_runs=(), note=""):
    return D("lemma", "inspected", list(extra_runs) + sites + [LR_LIVEROWS, LR_MATCHES],
             [], f"{what} LiveRows counts rows by (COALESCE(graph_id, ''), id prefix) and record membership "
             "(Matches) reads only ledger globals, so an update that keeps every row's id and COALESCE'd graph "
             "changes neither whether a target is live nor which records are a target's; the writer adds no record." + note)


def fc1301(sites, run=None, note=""):
    ev = ([run] if run else []) + M_FC1301 + sites + [LR_LIVEROWS, LR_ENTRY, WRITETXN]
    base = ("The writer deletes node rows (or the only rows) of a target inside a transaction that can roll back "
            "(its own TSTART/TROLLBACK or WriteTxn, nested in a caller's transaction). LiveRows reads uncommitted "
            "data, so while the delete is uncommitted another connection's redaction sees the target not live, "
            "tombstones it (and sets the marker); the rollback then makes the target live again: F-C1301.")
    if run:
        return D("finding", "live", ev, ["F-C1301"], base + " Live for this writer: the redaction completed while "
                 "the delete was uncommitted and the caller's ROLLBACK restored the content under tombstoned "
                 "records; with a bounded run the rollback made the target live while the marker names it." + note)
    return D("finding", "inspected", ev, ["F-C1301"], base + " Graded inspected for this writer (F-C1301 is live "
             "for delete_reification, ws-live-fc1301-delete-reification; model for any writer)." + note)


def open_(reason, evidence):
    return D("open", "open", evidence, [], reason)


# ------------------------------------------------------------------------------------------------ the writers
# Each entry: invariant -> discharge. Site citations are the census sites (path:lines) widened to the function.

W = {}

NE = "iris_vector_graph/_engine/nodes_edges.py"
SC = "iris_vector_graph/_engine/schema.py"
SN = "iris_vector_graph/_engine/snapshot.py"
TM = "iris_vector_graph/_engine/temporal.py"
ST = "iris_vector_graph/stores/iris_sql_store.py"
GS = "iris_vector_graph/schema.py"
KG = "iris_src/src/Graph/KG/"


def inserter(writer, sites, run, stmt_what, note_marker="", note_nlt="", note_replay=""):
    W[writer] = {
        "INV-marker": marker_inserter(sites, run, note_marker),
        "INV-no-live-tombstone": nlt_inserter(sites, run, note_nlt),
        "INV-replay": replay_lemma(sites, run, note_replay),
        "INV-stmt": stmt_lemma_rows(sites, stmt_what),
    }


inserter(f"{NE}::store_node", [f"{NE}:2393-2530"], ins_run("store_node"),
         "The writer writes node, label and property rows only (no rdf_edges row).")
inserter(f"{NE}::store_edge", [f"{NE}:2532-2588", f"{NE}:1106-1150"], ins_run("store_edge"),
         "The writer inserts an rdf_edges row (and its endpoint node rows) that no statement names; a duplicate of a "
         "recorded tuple is refused by u_spo_graph_ekey and swallowed, so no recorded edge's row changes.")
inserter(f"{NE}::bulk_create_edges", [f"{NE}:87-91", f"{NE}:1873-2017"], ins_run("bulk_create_edges"),
         "The writer inserts rdf_edges rows no statement names (an existing tuple is not duplicated) and its census "
         "site only sets qualifiers to NULL on a temporal-marked row (no row added or removed).",
         note_replay=" Its adopt UPDATE (qualifiers NULL on a marked row) also hits a ledger relationship whose "
         "qualifiers hold temporal=1 (F-C0450's predicate); that change is an unrecorded write verify classifies.")
inserter(f"{NE}::bulk_ingest_edges", [f"{NE}:2019-2132"], ins_run("bulk_ingest_edges"),
         "The writer inserts default-graph rdf_edges rows (and endpoint nodes) no statement names, skipping tuples "
         "already present.",
         note_marker=" The live run took the server path (EdgeScan.BulkIngestEdgesSQL); the census site, the row-by-row "
                     "fallback (2086-2105), registers endpoints the same way and is inspected.",
         note_nlt=" The live run took the server path; the fallback branch is inspected.")
inserter(f"{KG}EdgeScan.cls::BulkIngestEdgesSQL", [f"{KG}EdgeScan.cls:267-313", f"{KG}EdgeScan.cls:247-258"],
         ins_run("bulk_ingest_edges"),
         "The writer inserts default-graph rdf_edges rows (after RegisterDefaultNode) no statement names, skipping "
         "a tuple already present.")
inserter(f"{KG}EdgeScan.cls::BulkIngestNodesSQL", [f"{KG}EdgeScan.cls:340-430", f"{KG}EdgeScan.cls:247-258"],
         ins_run("bulk_create_nodes"),
         "The writer writes node, label and property rows only (its DELETE removes property rows of ids with no node "
         "row).")
inserter(f"{KG}EdgeScan.cls::RegisterDefaultNode", [f"{KG}EdgeScan.cls:247-258"], ins_run("bulk_create_nodes"),
         "The writer inserts a default-graph node row only.",
         note_marker=" Exercised through engine.bulk_create_nodes (BulkIngestNodesSQL calls it for every id); "
                     "BulkIngestEdgesSQL calls it for both endpoints (ws-live-ins-bulk_ingest_edges).")
inserter(f"{KG}FHIRGraph.cls::EnsureNode", [f"{KG}FHIRGraph.cls:2602-2618"], None,
         "The writer writes node, label and property rows of a FHIR key only.",
         note_marker=" Live is blocked: AUDITB has no FHIR repository (HS_FHIRServer, ws-live-fhir-blocked).",
         note_nlt=" Live is blocked (ws-live-fhir-blocked).")
W[f"{KG}FHIRGraph.cls::EnsureNode"]["INV-marker"]["evidence"].append(R_FHIR)
W[f"{KG}FHIRGraph.cls::EnsureNode"]["INV-no-live-tombstone"]["evidence"].append(R_FHIR)
inserter(f"{KG}FHIRGraph.cls::SyncProps", [f"{KG}FHIRGraph.cls:2498-2570", PROPS_NOFK], None,
         "The writer writes label and property rows of a FHIR key only.",
         note_marker=" Its property INSERTs need no node row (rdf_props has no foreign key), so they alone can make "
                     "the FHIR graph live. Live is blocked (ws-live-fhir-blocked).",
         note_nlt=" Live is blocked (ws-live-fhir-blocked).")
W[f"{KG}FHIRGraph.cls::SyncProps"]["INV-marker"]["evidence"].append(R_FHIR)
W[f"{KG}FHIRGraph.cls::SyncProps"]["INV-no-live-tombstone"]["evidence"].append(R_FHIR)
inserter(f"{SC}::reify_edge", [f"{SC}:3264-3332"], ins_run("reify_edge"),
         "The writer writes the reifier's node, label, property and rdf_reifications rows (no rdf_edges row).")
inserter(f"{SN}::import_rdf", [f"{SN}:557-795"], ins_run("import_rdf"),
         "The writer inserts node, property and rdf_edges rows no statement names, skipping tuples already present.")
inserter(f"{TM}::_mirror_node", [f"{TM}:98-118", f"{TM}:304-332"], None,
         "The writer inserts a node row only.",
         note_marker=" Its branch runs without the adjacency index (temporal.py:308); with the index the same entry "
                     "point (create_edge_temporal) wrote the same node rows through InsertEdge live "
                     "(ws-live-ins-create_edge_temporal).",
         note_nlt=" Live analogue: ws-live-ins-create_edge_temporal (same rows, adjacency-index branch).")
W[f"{TM}::_mirror_node"]["INV-marker"]["evidence"].append(ins_run("create_edge_temporal"))
W[f"{TM}::_mirror_node"]["INV-no-live-tombstone"]["evidence"].append(ins_run("create_edge_temporal"))
inserter(f"{TM}::create_edge_temporal", [f"{TM}:246-332", f"{KG}TemporalIndex.cls:104-114"],
         ins_run("create_edge_temporal"),
         "The writer inserts a temporal-marked rdf_edges row (and endpoint nodes) no statement names; an existing "
         "row of the tuple is not touched (AssertTemporalRow's NOT EXISTS).",
         note_marker=" The live run used the adjacency-index branch (InsertEdge asserts the rows); the census site "
                     "(temporal.py:316, no index) inserts the same rows.")
inserter(f"{TM}::bulk_create_edges_temporal", [f"{TM}:390-476"], ins_run("bulk_create_edges_temporal"),
         "The writer inserts temporal-marked rdf_edges rows (and endpoint nodes) no statement names.")
inserter("iris_vector_graph/bulk_loader.py::_register_endpoints", ["iris_vector_graph/bulk_loader.py:201-228"],
         ins_run("bulkloader_load_edges"), "The writer inserts node rows only.")
inserter(f"{ST}::write_nodes", [f"{ST}:1214-1251"], ins_run("store_write_nodes"),
         "The writer writes node, label and property rows only.")
inserter(f"{ST}::write_edges", [f"{ST}:1253-1301"], ins_run("store_write_edges"),
         "The writer inserts default-graph rdf_edges rows (and endpoint nodes) no statement names.")

# ResyncKey: as an entry point it calls EnsureNode and SyncProps (node/property inserts) and DeleteEdge.
RK = [f"{KG}FHIRGraph.cls:2039-2344", f"{KG}FHIRGraph.cls:2216-2240"]
W[f"{KG}FHIRGraph.cls::ResyncKey"] = {
    "INV-marker": marker_inserter(RK, None, " Its own census sites are an UPDATE of qualifiers and an edge INSERT; the "
                                  "inserts that make a key live come from EnsureNode and SyncProps, which it calls "
                                  "(FHIRGraph.cls:2275, 2284). Live is blocked (ws-live-fhir-blocked)."),
    "INV-no-live-tombstone": nlt_inserter(RK, None, " Through EnsureNode/SyncProps, which it calls. Live is blocked "
                                          "(ws-live-fhir-blocked)."),
    "INV-replay": replay_lemma(RK, None),
    "INV-stmt": open_("blocked-access (HS_FHIRServer classes absent: ws-live-fhir-blocked). Inspected: ResyncKey "
                      "deletes every rdf_edges row of the FHIR graph with s = key that the repository does not want "
                      "(FHIRGraph.cls:2216-2240, DeleteEdge 2585-2599) and touches no ^IVG.Ledger node, so a ledger "
                      "relationship committed into a FHIR graph would lose its row while its statement stays live "
                      "(the F-0303 shape). Not reproducible here, so no finding is recorded.",
                      [R_FHIR] + RK + [f"{KG}FHIRGraph.cls:2585-2599"]),
}
for inv in ("INV-marker", "INV-no-live-tombstone"):
    W[f"{KG}FHIRGraph.cls::ResyncKey"][inv]["evidence"].append(R_FHIR)

# Edge-only or non-identity writers -----------------------------------------------------------------------------

def no_row_writer(writer, sites, what_marker, stmt_what, kind="fk", extra_runs=(), replay_run=None, stmt=None,
                  note_replay=""):
    f = fk_lemma if kind == "fk" else nonkey_lemma
    W[writer] = {
        "INV-marker": f(sites, what_marker, extra_runs),
        "INV-no-live-tombstone": f(sites, what_marker, extra_runs),
        "INV-replay": replay_lemma(sites, replay_run, note_replay),
        "INV-stmt": stmt if stmt is not None else stmt_lemma_rows(sites, stmt_what),
    }


no_row_writer(f"{SC}::materialize_inference", [f"{SC}:2966-3183"],
              "The writer inserts only rdf_edges rows (inferred qualifier), FK-checked (no %NOCHECK).",
              "It inserts rdf_edges rows no statement names, skipping tuples already present (_exists).")
no_row_writer(f"{GS}::_restore_rescued_rdf_edges", [f"{GS}:3112-3285"],
              "The writer re-inserts rescued rdf_edges rows whose endpoints resolve (WHERE endpoint_resolves, no "
              "%NOCHECK); it runs only to finish the v3.2.0 rdf_edges rescue (schema.py:3070-3110).",
              "It re-inserts rows that existed before the rescue and writes no statement.")
no_row_writer(f"{NE}::set_edge_weight", [f"{NE}:1306-1380"],
              "The writer only UPDATEs the qualifiers of existing default-graph rows of a triple (False when none).",
              "It changes qualifiers only; a statement names a tuple, not qualifiers.", kind="nonkey")
no_row_writer(f"{GS}::ensure_ekey", [f"{GS}:1107-1157", f"{GS}:1090-1104"],
              "The writer only sets rdf_edges.ekey 0 where it is NULL (an upgraded table).",
              "Statements name (s, p, o, graph), not ekey.", kind="nonkey", extra_runs=[R_MIG])
no_row_writer(f"{GS}::ensure_props_value_key", [f"{GS}:904-975"],
              "The writer only runs UPDATE rdf_props SET val = val (recomputes the val_key column).",
              "It writes rdf_props only.", kind="nonkey", extra_runs=[R_MIG])
no_row_writer(f"{GS}::tighten_graph_id_column", [f"{GS}:1230-1338"],
              "The writer only sets graph_id '' where it is NULL, which COALESCE(graph_id, '') already reads as ''.",
              "Statements carry the graph name from the ledger op, and the tuple index's GKey is the same for NULL "
              "and ''.", kind="nonkey", extra_runs=[R_MIG])

COLL = [ISMARKED, QUALSJSON, "iris_src/src/Graph/KG/LedgerApply.cls:68-71", "docs/adr/0009-a-temporal-edge-implies-a-structural-edge.md:38-42"]
no_row_writer(f"{KG}Adjacency.cls::RetractTemporalRow", [f"{KG}Adjacency.cls:623-645"],
              "The writer deletes only rdf_edges rows (temporal-marked ones of one triple).", "",
              replay_run=R_COLL,
              stmt=D("finding", "live", [R_COLL, f"{KG}Adjacency.cls:623-645", f"{KG}TemporalIndex.cls:325-343"] + COLL,
                     ["F-C0450"], "Live: a ledger relationship whose qualifiers hold temporal=1 (stored {\"temporal\":\"1\"}, "
                     "IsTemporalMarked accepts it) and a temporal edge on the same triple; deleting the temporal edge "
                     "(engine.delete_edge_temporal -> DeleteTemporalEdge -> RetractTemporalRow) deleted the ledger's "
                     "row and left its statement live: INV-stmt fails (F-C0450)."))
W[f"{KG}Adjacency.cls::RetractTemporalRow"]["INV-replay"]["reason"] += " (ws-live-stmt-collision: diverges, unrecorded_writes after the deletion.)"
no_row_writer(f"{KG}Adjacency.cls::RetractTemporalRows", [f"{KG}Adjacency.cls:650-688"],
              "The writer deletes only rdf_edges rows (temporal-marked ones of a set of triples).", "",
              replay_run=R_PURGE,
              stmt=D("finding", "live", [R_PURGE, f"{KG}Adjacency.cls:650-688", f"{KG}TemporalIndex.cls:944-1046"] + COLL,
                     ["F-C0450"], "Live: the purge (engine.purge_before -> RetireExpired -> RetractTemporalRows) on a "
                     "ledger relationship with qualifiers {\"temporal\":\"1\"}: the %STARTSWITH marker test misses, the "
                     "fallback RetractTemporalRow (Adjacency.cls:677-679) deletes the ledger's row and its statement "
                     "stays live (F-C0450)."))
no_row_writer(f"{SC}::retract_inference", [f"{SC}:3186-3259", f"{SC}:61"],
              "The writer deletes only rdf_edges rows (qualifiers LIKE '%\"inferred\":%').", "",
              replay_run=R_COLL,
              stmt=D("finding", "live", [R_COLL, f"{SC}:3186-3259", f"{SC}:61", QUALSJSON], ["F-C0151"],
                     "Live: engine.retract_inference() deleted a ledger relationship whose qualifiers hold a user key "
                     "'inferred' (stored {\"inferred\":\"user\"}) and its statement stays live: INV-stmt fails (F-C0151)."))
no_row_writer(f"{KG}FHIRGraph.cls::DeleteEdge", [f"{KG}FHIRGraph.cls:2585-2599"],
              "The writer deletes only one rdf_edges row by edge_id.", "",
              stmt=open_("blocked-access (HS_FHIRServer classes absent: ws-live-fhir-blocked). Inspected: DeleteEdge "
                         "deletes an rdf_edges row by edge_id with no statement cleanup, and ResyncKey calls it for every "
                         "row of the key the repository does not want (FHIRGraph.cls:2216-2240), a ledger relationship "
                         "in a FHIR graph included; it would fail INV-stmt as F-0303 does for delete_edge. Not "
                         "reproducible here, so no finding is recorded.",
                         [R_FHIR, f"{KG}FHIRGraph.cls:2585-2599", f"{KG}FHIRGraph.cls:2216-2240"]))

# Node-row deleters ---------------------------------------------------------------------------------------------

def deleter(writer, sites, run, stmt, note="", replay_run=None):
    W[writer] = {
        "INV-marker": fc1301(sites, run, note),
        "INV-no-live-tombstone": fc1301(sites, run, note),
        "INV-replay": replay_lemma(sites, replay_run or run),
        "INV-stmt": stmt,
    }


deleter(f"{SC}::delete_reification", [f"{SC}:3361-3397"], R_FC1301,
        stmt_lemma_rows([f"{SC}:3361-3397"], "The writer deletes rdf_reifications, property, label and node rows of "
                        "an id; a node row with an edge cannot go (fk_edges_source/dest refuse the DELETE and the call "
                        "rolls back), so no edge row is removed."))
deleter(f"{KG}Eraser.cls::DeleteBareSet", [f"{KG}Eraser.cls:1260-1315", f"{KG}Eraser.cls:1208-1248"], None,
        stmt_lemma_rows([f"{KG}Eraser.cls:1260-1315"], "The writer deletes node rows that no edge names (BareClauses, "
                        "and the foreign keys refuse a node with a dependant), so no edge row is removed."),
        note=" Its batches are TSTART ... TCOMMIT with TROLLBACK on error (Eraser.cls:1272-1313) and nest in a "
             "caller's transaction; it deletes ledger-recorded bare nodes (ws-live-stmt-collision: DropRows retired "
             "the 2 recorded endpoints through it).", replay_run=R_COLL)
deleter(f"{KG}FHIRGraph.cls::DropNode", [f"{KG}FHIRGraph.cls:2402-2494", f"{KG}FHIRGraph.cls:1923-1978"], None,
        open_("blocked-access (HS_FHIRServer classes absent: ws-live-fhir-blocked). Inspected: DropNode first deletes "
              "every rdf_edges row of the FHIR graph that names the key as source or target through DeleteEdge "
              "(FHIRGraph.cls:2406-2440), with no statement cleanup, so a ledger relationship committed into a FHIR "
              "graph would lose its row while its statement stays live (the F-0303 shape). Not reproducible here, "
              "so no finding is recorded.", [R_FHIR, f"{KG}FHIRGraph.cls:2402-2494", f"{KG}FHIRGraph.cls:2585-2599"]),
        note=" It runs inside RunBatch's TSTART ... TCOMMIT, which a failure (or the ^IVG.FHIRGraphFault hook) rolls "
             "back (FHIRGraph.cls:1920-1978). Live is blocked (ws-live-fhir-blocked).")
for inv in ("INV-marker", "INV-no-live-tombstone"):
    W[f"{KG}FHIRGraph.cls::DropNode"][inv]["evidence"].append(R_FHIR)
deleter(f"{KG}TemporalPolicy.cls::DropRows", [f"{KG}TemporalPolicy.cls:124-228"], None,
        D("finding", "live", [R_COLL, f"{KG}TemporalPolicy.cls:124-228"] + COLL, ["F-C0450"],
          "Live: drop_temporal_structural_rows('RD') (TemporalPolicy.DropRows) deleted a ledger relationship whose "
          "qualifiers hold temporal=1 (pass 2 parses them with IsTemporalMarked) and retired its 2 recorded endpoint "
          "nodes; the statement stays live without its row (F-C0450)."),
        note=" Its edge deletes alone cannot take a target from live to not live, but it also retires the endpoints "
             "it leaves bare (RetireBareNodes -> DeleteBareSet), in batches of TSTART ... TCOMMIT with TROLLBACK on "
             "error (TemporalPolicy.cls:173-219).", replay_run=R_COLL)
deleter(f"{NE}::_drop_orphaned_props", [f"{NE}:1617-1646", f"{NE}:1761-1866", PROPS_NOFK], None,
        stmt_lemma_rows([f"{NE}:1617-1646"], "The writer deletes rdf_props rows only."),
        note=" It deletes only property rows whose node row is absent, which LiveRows still counts; it runs in "
             "bulk_create_nodes' SQL path inside its WriteTxn (nodes_edges.py:1761-1866, call at 1843), so a target whose only live "
             "rows are such properties is seen not live while the delete is uncommitted.")

# SQL fallbacks of the store's deleters: unreached at the pin's deploy ------------------------------------------

def fallback_open(what):
    return (f"open: unreached at the pin's deploy. {what} runs only when IRISGraphStore._has_eraser_method answers "
            "False (iris_sql_store.py:1307-1318), i.e. when Graph.KG.Eraser.EraseNodeIds / EraseEdges is not "
            "compiled; initialize_schema compiles the Eraser with the ledger (ws-deploy-auditb: 66 classes "
            "unchanged), and the deployed path goes through the Eraser. The probe caches any exception as 'absent', "
            "and on that path the SQL deletes recorded rows with no statement cleanup inside a WriteTxn that can roll "
            "back (the F-0303 / F-C1301 shapes). That configuration was not reproduced, so no finding is recorded.")


SQLF = [f"{ST}:1307-1318", f"{ST}:1320-1361", f"{ST}:1474-1518"]
W[f"{ST}::_delete_nodes_sql"] = {
    "INV-marker": open_(fallback_open("_delete_nodes_sql (iris_sql_store.py:1363-1418)"),
                        ["run:ws-deploy-auditb", f"{ST}:1363-1418"] + SQLF),
    "INV-no-live-tombstone": open_(fallback_open("_delete_nodes_sql (iris_sql_store.py:1363-1418)"),
                                   ["run:ws-deploy-auditb", f"{ST}:1363-1418"] + SQLF),
    "INV-replay": replay_lemma([f"{ST}:1363-1418"], None),
    "INV-stmt": open_(fallback_open("_delete_nodes_sql (iris_sql_store.py:1363-1418)"),
                      ["run:ws-deploy-auditb", f"{ST}:1363-1418"] + SQLF),
}
W[f"{ST}::delete_edges"] = {
    "INV-marker": fk_lemma([f"{ST}:1474-1518"], "The writer deletes only rdf_edges rows (through EraseEdges or its "
                           "SQL fallback)."),
    "INV-no-live-tombstone": fk_lemma([f"{ST}:1474-1518"], "The writer deletes only rdf_edges rows (through "
                                      "EraseEdges or its SQL fallback)."),
    "INV-replay": replay_lemma([f"{ST}:1474-1518"], None),
    "INV-stmt": open_(fallback_open("The SQL DELETE of delete_edges (iris_sql_store.py:1504-1518)"),
                      ["run:ws-deploy-auditb", f"{ST}:1474-1518"] + SQLF),
}
# add_graph_id_to_nodes -----------------------------------------------------------------------------------------
AG = [f"{GS}:1514-1637", f"{GS}:704-722", f"{SC}:2513-2514"]
W[f"{GS}::add_graph_id_to_nodes"] = {
    "INV-marker": D("finding", "live", [R_MIG] + AG + [LR_LIVEROWS, LR_BLOCKS], ["F-C0150"],
                    "Live: engine.create_node stored a '__graph' property, and add_graph_id_to_nodes (which every "
                    "initialize_schema runs, schema.py:719) moved that node into the named graph while that graph's "
                    "redaction marker existed: the marked target became live and a re-run was refused target_live "
                    "(F-C0150)."),
    "INV-no-live-tombstone": D("finding", "inspected", [R_MIG] + AG + [LR_ENTRY, LR_BATCH], ["F-C0150"],
                               "The move shown live (ws-live-migrations) makes a graph target live without a ledger "
                               "write; after a run's entry check, BatchInLock tombstones without re-checking (the "
                               "F-C1350 mechanism, live for 12 inserters). The composition is inspected (F-C0150)."),
    "INV-replay": replay_lemma(AG, None, " The move changes a node row's graph, which the graph-blind node map of "
                               "read_canonical (replay.py:597-600) does not see; replay equals the store in that "
                               "abstraction (the blindness itself is F-1304/F-1305's)."),
    "INV-stmt": stmt_lemma_rows(AG, "The writer moves node rows between graphs and deletes '__graph' property rows; "
                                "a node row with edges cannot move (fk_edges_source/dest reference (graph_id, node_id)), "
                                "so no edge row changes."),
}

# Snapshot helpers ----------------------------------------------------------------------------------------------
IG = [f"{KG}Snapshot.cls:24-35", f"{KG}Snapshot.cls:4-22"]
R_IG = "run:ws-live-snap-importglobals"
how = {
    "INV-shape": ("live", "Live: an imported .gof of another history replaced the records of revision 2 while its "
                  "revision row stayed: the records are neither the revision's originals nor their tombstones."),
    "INV-isolation": ("inspected", "The same overwrite can lay a tombstone on any record (the file carries the values), "
                      "so a record outside every redacted target can become a tombstone."),
    "INV-text": ("inspected", "A .gof of ^Graph.KG.LedgerRevisionD (or of ^IVG.Ledger(\"redactedRev\")) is loaded the "
                 "same way, past the immutability triggers, so a revision with a tombstone can get its free text back."),
    "INV-retry": ("inspected", "A .gof can set ^IVG.Ledger(\"idem\", key) to a revision with tombstones or kill "
                  "idemRedacted."),
    "INV-marker": ("inspected", "A .gof can set or kill ^IVG.Ledger(\"redacting\") and the records it governs."),
    "INV-no-live-tombstone": ("inspected", "A .gof can write tombstones of live content (records) or content rows "
                              "(table globals) under tombstoned records."),
    "INV-replay": ("live", "Live: after the import verify() went equal -> diverges (the records no longer replay to "
                   "the store)."),
    "INV-stmt": ("inspected", "A .gof can set or kill ^IVG.Ledger(\"stmt\"/\"tuple\") or rdf_edges' storage global."),
}
W[f"{KG}Snapshot.cls::ImportGlobals"] = {
    inv: D("finding", g, [R_IG, "run:c18-live-file-helpers"] + IG, ["F-1806"],
           "ImportGlobals runs $System.OBJ.Load on every *.gof in a directory with no allow-list (F-1806), and is "
           "callable over the Native API. Live (ws-live-snap-importglobals): it loaded a ^IVG.Ledger export and its "
           "process set ^IVG.Ledger rec, head, meta, idBySeq, revById and stmtNext. " + t)
    for inv, (g, t) in how.items()
}
SNJ = [f"{KG}Snapshot.cls:87-106", f"{SN}:1654-1692"]
W[f"{KG}Snapshot.cls::SetNodeJSON"] = {
    inv: D("guard", "live", ["run:ws-live-snap-setnodejson"] + SNJ, [],
           "NodeRef (Snapshot.cls:95-106) throws unless the global is ^IVF, ^PLAID or ^VecIdx, so SetNodeJSON writes "
           "none of ^IVG.Ledger and the storage globals of nodes, rdf_labels, rdf_props, rdf_edges and "
           "ledger_revisions, the stores this invariant reads (the census read its `Set @tRef` as 'any global'). "
           "Live: 40 calls on those globals refused 'not a vector-index global', no global set by the calling "
           "process (journal). Its one product caller, restore_snapshot (snapshot.py:1674-1677), passes vector "
           "globals only; restore's own ledger writes are snapshot.restore_replace's (F-1801, WS-GAP-*).")
    for inv in how
}

# Ledger-text writers -------------------------------------------------------------------------------------------
W["iris_vector_graph/_engine/legacy.py::copy_ledger_history"] = {
    "INV-text": D("finding", "live", ["run:fc1306-legacy-ledger-rows", "iris_vector_graph/_engine/legacy.py:606-646",
                                      f"{SC}:2308", LR_CLEAR], ["F-C1306"],
                  "F-C1306's live run went through this writer (initialize_schema(schema_prefix='RAG') -> "
                  "ledger_history_copied, the 7+1 rows): it copies Graph_KG.ledger_revisions into the IVG Schema and "
                  "leaves the originals; ClearRevision clears only the copy, so after a complete redaction the "
                  "Graph_KG rows of the tombstoned revisions keep message, source, correlation id and key."),
}
W["<any SQL client>::INSERT INTO Graph_KG.ledger_revisions"] = {
    "INV-text": D("guard", "live", ["run:ws-live-sql-guard", "iris_src/src/Graph/KG/LedgerRevision.cls:1-5",
                                    "iris_src/src/Graph/KG/LedgerRevision.cls:44",
                                    "iris_src/src/Graph/KG/LedgerRevision.cls:87-108"], [],
                  "seq is the table's unique IdKey (SeqIdx) and UPDATE/DELETE are refused by RejectUpdate/RejectDelete, "
                  "so an SQL INSERT can neither replace nor rewrite the row of a revision that has records; a new row's "
                  "seq has no record (records are written with their row in one commit), so no tombstone sits under "
                  "its text. Live: INSERT of the redacted seq refused SQLCODE -119 (SeqIdx), UPDATE refused -132, the "
                  "text stays cleared. Side effect recorded separately: an INSERT of head+1 wedges every later commit "
                  "(F-C1150, ws-live-sql-insert-wedge), an availability defect, not an INV-text break."),
}

# Conditional writers -------------------------------------------------------------------------------------------
IV = ["iris_vector_graph/dbapi_utils.py:1-20", "iris_vector_graph/dbapi_utils.py:101-167"]
GSE = "iris_vector_graph/migrations/graph_scoped_embeddings.py"


def cond_vacuous(inv):
    r = ("Resolved: no product code calls insert_vector (its only call is the docstring example on "
         "RAG.SourceDocuments, dbapi_utils.py:16); the run-time table is the caller's, so no product path names a "
         "content or ledger table and the condition of this obligation never holds at the pin. A caller who passes a "
         "content table is an arbitrary SQL client writing that table (the census's '<any SQL client>' surface).")
    if inv == "INV-text":
        r += (" Named Graph_KG.ledger_revisions, its INSERT and UPDATE meet the SeqIdx key and the RejectUpdate "
              "trigger (ws-live-sql-guard).")
    return D("lemma", "inspected", IV + (["run:ws-live-sql-guard"] if inv == "INV-text" else []), [], r)


W["iris_vector_graph/dbapi_utils.py::insert_vector"] = {inv: cond_vacuous(inv) for inv in
                                                        ("INV-marker", "INV-no-live-tombstone", "INV-replay",
                                                         "INV-stmt", "INV-text")}


def mig_child(writer, sites, what):
    out = {}
    for inv in ("INV-marker", "INV-no-live-tombstone", "INV-replay", "INV-stmt"):
        out[inv] = D("lemma", "inspected", sites + [f"{GSE}:660-690", f"{GSE}:95", FK_LABELS, PROPS_NOFK], [],
                     f"Resolved: {what} The run-time table is rdf_labels or rdf_props (the 4.0.0 statement list, "
                     "graph_scoped_embeddings.py:672-689). On the pin's schema graph_id is NOT NULL and (graph_id, s, "
                     "label|key) is the primary key (schema.py:403-418), so the statement matches no row; it changes "
                     "rows only on a 3.2.0-shaped install, which predates the ledger (no record, marker or statement "
                     "exists for the invariant to read). It writes no ledger node and no rdf_edges row.")
    out["INV-text"] = D("lemma", "inspected", sites + [f"{GSE}:660-690"], [],
                        "Resolved: the run-time table is rdf_labels or rdf_props, never Graph_KG.ledger_revisions; the "
                        "writer writes no meta, record or redactedRev.")
    return out


W[f"{GSE}::_backfill_graph_id"] = mig_child(f"{GSE}::_backfill_graph_id", [f"{GSE}:731-750"],
                                            "_backfill_graph_id runs UPDATE <table> SET graph_id = ... WHERE graph_id IS NULL.")
W[f"{GSE}::_dedupe"] = mig_child(f"{GSE}::_dedupe", [f"{GSE}:781-821"],
                                 "_dedupe deletes exact duplicates of (graph_id, s, label|key), keeping the lowest %ID.")
W[f"{GSE}::_redistribute"] = {
    inv: D("lemma", "inspected", [f"{GSE}:1048-1093", f"{GSE}:73", f"{GSE}:300-315"], [],
           "Resolved: the run-time table is a SOURCE_TABLES member (kg_NodeEmbeddings, kg_NodeEmbeddings_optimized, "
           "graph_scoped_embeddings.py:73, 303-314); embedding tables are none of the stores this invariant reads "
           "(content = nodes, rdf_labels, rdf_props, rdf_edges; ledger globals and ledger_revisions).")
    for inv in ("INV-marker", "INV-no-live-tombstone", "INV-replay", "INV-stmt", "INV-text")
}

# Write-set gaps of snapshot.restore_replace ---------------------------------------------------------------------
GAP = [f"{SN}:1574", f"{SN}:1654-1692", LR_CLEAR, "iris_src/src/Graph/KG/LedgerRedact.cls:345"]
W[f"{SN}::_import_global_from_ndjson"] = {
    "INV-marker": D("finding", "live", ["run:ws-live-gap-marker", "run:c18-live-ledger-overlay"] + GAP, ["F-C1850", "F-1801"],
                    "Live: a bounded redaction left the marker; a replacing restore of an archive that holds the target "
                    "brought its 9 rows back and left the live ledger's marker (the import sets the archive's nodes "
                    "and kills none), so the marker names a live target; a re-run is refused target_live (F-C1850; "
                    "the overlay itself is F-1801)."),
    "INV-retry": D("finding", "live", ["run:ws-live-gap-restore", "run:c18-live-ledger-overlay"] + GAP, ["F-C1850", "F-1801"],
                   "Live: after a replacing restore of a pre-erase archive the live ledger's idemRedacted and "
                   "redactedRev(2) survive while idem(key) comes back; a second redaction of the tenant tombstones the "
                   "revision but ClearRevision skips it (redactedRev exists, LedgerRedact.cls:345), so the key stays "
                   "live on a revision with tombstones, and a retry with it is answered replayed=True with that "
                   "revision (F-C1850)."),
    "INV-text": D("finding", "live", ["run:ws-live-gap-restore", "run:c18-live-ledger-overlay"] + GAP, ["F-C1850", "F-1801"],
                  "Live: same run: after the second redaction revision 2 has only tombstones and its row keeps message "
                  "'wsgap secret message' and its idempotency key, because the surviving redactedRev(2) makes "
                  "ClearRevision skip it (F-C1850)."),
}

# ------------------------------------------------------------------------------------------- module-level cells

def module_entries(census_ids_by_module, open_ids_by_module):
    def ids(m):
        return census_ids_by_module.get(m, [])

    def opened(m):
        return open_ids_by_module.get(m, [])
    BA = "experiment/playbook-completion/models/breadth-a/writesets.json"
    ba_open = {"01": 112, "03": 97, "04": 125, "05": 171, "06": 48}
    out = {}
    for m in ("01", "03", "04", "05", "06"):
        out[f"module:{m}"] = {
            "discharge": "open", "grade": "open", "evidence": [BA, "experiment/playbook-completion/writesets/DISCHARGES.json"],
            "findings": [],
            "reason": (f"The census part is done: {len(ids(m))} census cells of module {m} each have one discharge in "
                       f"DISCHARGES.json ({len(opened(m))} of them open: {', '.join(opened(m)) or 'none'}). Still open: "
                       f"{ba_open[m]} (module invariant, writer) pairs of {BA} with status 'open' (module invariants "
                       "ADJ/GID/TMP/VEC/..., not the 8 manifest invariants); this lane did not discharge them."),
        }
    out["module:08"] = {"discharge": "open", "grade": "open", "evidence": ["experiment/playbook-completion/modules/08.json"],
                        "findings": [], "reason": "Not in the census: module 08's graph-coherence invariants (CYP-I5.5/I5.6, "
                        "SYS-I2) against other modules' writers (02/03/15) are still undischarged (modules/08.json "
                        "invariant_writesets); this lane did not address them."}
    out["module:10"] = {"discharge": "open", "grade": "open", "evidence": ["experiment/playbook-completion/modules/10.json"],
                        "findings": [], "reason": "Not in the census: module 10's cell is open because its closed claim "
                        "cites no registered run or committed artifact; this lane did not address it."}
    out["module:11"] = {"discharge": "finding", "grade": "live",
                        "evidence": ["experiment/playbook-completion/writesets/DISCHARGES.json", "run:ws-live-sql-guard",
                                     "run:ws-live-snap-importglobals", "run:ws-live-snap-setnodejson",
                                     "run:fc1306-legacy-ledger-rows", "run:ws-live-gap-restore"],
                        "findings": ["F-1806", "F-C1306", "F-C1850", "F-C1150"],
                        "reason": "Every census obligation on module 11's invariants (INV-shape, INV-isolation, INV-text, "
                        "INV-retry) has one discharge: WS-OBL-001 guard, the SetNodeJSON 8 guard, the ImportGlobals 8 "
                        "and WS-OBL-066 and WS-GAP-002/003 findings; module 11's own pairs were already dispositioned "
                        "(modules/11.json). Verification cell closes; product obligation fails (F-1806, F-C1306, F-C1850, "
                        "and the SQL INSERT wedge F-C1150)."}
    out["module:12"] = {"discharge": "open", "grade": "open",
                        "evidence": ["experiment/playbook-completion/writesets/DISCHARGES.json", R_COLL, R_PURGE, R_FHIR],
                        "findings": ["F-C0450", "F-C0151", "F-C1301"],
                        "reason": "INV-stmt (ERS-I2/I3) is module 12's: every census INV-stmt obligation has a discharge "
                        f"except {', '.join(sorted(open_ids_by_module.get('_stmt', [])))} (FHIR DropNode/DeleteEdge/ResyncKey: "
                        "blocked-access, HS_FHIRServer absent; iris_sql_store SQL fallbacks: unreached at the pin's "
                        "deploy). Module 12's own 4 cells (DeleteBareSet) are discharged (F-C1301 inspected, lemmas)."}
    out["module:13"] = {"discharge": "open", "grade": "open",
                        "evidence": ["experiment/playbook-completion/writesets/DISCHARGES.json"] +
                        [ins_run(n) for n in ("store_node", "store_edge")] + [R_FC1301, R_MIG, "run:ws-live-gap-marker"],
                        "findings": ["F-C1350", "F-C1307", "F-C1301", "F-C0150", "F-C1850"],
                        "reason": "INV-marker and INV-no-live-tombstone are module 13's: every census obligation on them "
                        "has a discharge except "
                        f"{', '.join(sorted(open_ids_by_module.get('_mnlt', [])))} (_delete_nodes_sql's SQL fallback, "
                        "unreached at the pin's deploy). The product fails both: 12 bypass inserters live (F-C1350, "
                        "F-C1307), a bypass deleter live (F-C1301), add_graph_id_to_nodes (F-C0150), restore (F-C1850)."}
    out["module:14"] = {"discharge": "finding", "grade": "inspected",
                        "evidence": ["experiment/playbook-completion/writesets/DISCHARGES.json"] +
                        [ins_run(n) for n in ("store_node", "import_rdf")] + [R_COLL, "run:ws-live-snap-importglobals"],
                        "findings": ["F-1806"],
                        "reason": "INV-replay is module 14's: of the 42 census INV-replay obligations (4 conditional), 40 "
                        "are discharged by the RPL-B3 premise lemma (no unrecorded writes) with verify()'s "
                        "classification observed live for 20 writers (diverges, unrecorded_writes), SetNodeJSON's by "
                        "guard, and Snapshot.ImportGlobals' by finding F-1806 (imported ledger records no longer replay "
                        "to the store). Verification cell closes at the weakest grade (inspected); the product's other "
                        "replay findings (F-1305, F-C1308, F-1401) are outside these writer obligations."}
    rest = {
        "15": ("FHIR writers: live blocked (ws-live-fhir-blocked), discharged at inspected grade or open; reify_edge "
               "live, delete_reification live. Still open in module 15's cell and outside the census: the (invariant, "
               "plan) pairs of FHIR Rebuild/SyncOnce/Reinterpret/Schedule and the table-map/crosswalk writers it names."),
        "17": ("iris_sql_store write_nodes/write_edges live; the SQL fallbacks of _delete_nodes_sql and delete_edges "
               "are open (unreached at the pin's deploy); insert_vector's conditional cells are resolved (no product "
               "caller)."),
        "18": ("Snapshot.ImportGlobals: finding F-1806 (live), Snapshot.SetNodeJSON: guard (live), import_rdf live, "
               "restore's three write-set gaps live (F-C1850). Still open in module 18's cell and outside the census: "
               "snapshot.restore_merge is not a plan though it writes the ledger globals and ^KG(\"tagg\") (F-1805)."),
    }
    for m in ("15", "17", "18"):
        op = opened(m)
        out[f"module:{m}"] = {
            "discharge": "open", "grade": "open",
            "evidence": ["experiment/playbook-completion/writesets/DISCHARGES.json"],
            "findings": [],
            "reason": (f"{len(ids(m))} census cells of module {m}, each with one discharge in DISCHARGES.json; "
                       f"{len(op)} of them open ({', '.join(op) or 'none'}). " + rest[m]),
        }
    return out


# ------------------------------------------------------------------------------------------------------ build

def build() -> dict:
    census = json.loads(CENSUS.read_text())
    cells = census["extra_cells"]
    out = {}
    by_mod, open_by_mod = {}, {}
    missing = []
    for c in cells:
        oid, w, inv = c["obligation_id"], c["writer"], c["invariant"]
        d = W.get(w, {}).get(inv)
        if d is None:
            missing.append((oid, w, inv))
            continue
        e = {"writer": w, "invariant": inv, "kind": c["kind"], "module": c["module"]}
        e.update(json.loads(json.dumps(d)))
        out[oid] = e
        by_mod.setdefault(c["module"], []).append(oid)
        if d["discharge"] == "open":
            open_by_mod.setdefault(c["module"], []).append(oid)
            if inv == "INV-stmt":
                open_by_mod.setdefault("_stmt", []).append(oid)
            if inv in ("INV-marker", "INV-no-live-tombstone"):
                open_by_mod.setdefault("_mnlt", []).append(oid)
    if missing:
        raise SystemExit(f"no discharge for {len(missing)} census obligations: {missing[:5]}")
    obl = json.loads((PC / "matrix" / "obligations.json").read_text())
    open_modules = {c["module"] for c in obl["cells"] if c.get("gate") == "3.3a-writesets"
                    and "obligation_id" not in c
                    and (c.get("status") == "open" or c.get("source") == "matrix-input/writesets.json")}
    mods = module_entries(by_mod, open_by_mod)
    for m in sorted(open_modules):
        out[f"module:{m}"] = mods.get(f"module:{m}") or {
            "discharge": "open", "grade": "open", "evidence": ["experiment/playbook-completion/matrix/obligations.json"],
            "findings": [], "reason": f"module {m}'s 3.3a-writesets cell is open for reasons outside the census; this "
            "lane did not address them."}
    return {"_doc": ("Keys: census obligation ids (WS-OBL-*, WS-COND-*, WS-GAP-*) and module:NN; this _doc key is the "
                     "only other key. One discharge per census obligation of gate 3.3a-writesets (matrix-input/writer-census-"
                     "obligations.json, run followup-writer-census, source_sha256 " + census["source_sha256"] + ") and "
                     "one entry per module-level 3.3a-writesets cell open in matrix/obligations.json (keys module:NN). "
                     "Generated by writesets/tools/build_discharges.py; checked by writesets/tools/check_discharges.py. "
                     "A finding discharge closes the verification cell while the product obligation stays failed."),
            **out}


def main() -> int:
    data = build()
    text = json.dumps(data, indent=1, sort_keys=True) + "\n"
    if "--check" in sys.argv:
        return 0 if OUT.exists() and OUT.read_text() == text else 1
    OUT.write_text(text)
    n = {}
    for k, v in data.items():
        if k.startswith(("WS-OBL", "WS-COND", "WS-GAP")):
            n[v["discharge"]] = n.get(v["discharge"], 0) + 1
    print(f"wrote {OUT}: {sum(n.values())} census obligations {n}, "
          f"{sum(1 for k in data if k.startswith('module:'))} module entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
