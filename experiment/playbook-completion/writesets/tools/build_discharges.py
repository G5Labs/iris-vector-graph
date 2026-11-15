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
PAIRS = PC / "writesets" / "RUN-PAIRS.json"
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
R_RDEL = "run:ws-live-replay-delete_reification"
R_RIMP = "run:ws-live-replay-import_rdf"
R_NIE = "run:ws-live-noindex-erase"
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


JOURNAL_LIVE = (" Live: the writer's process wrote content and no ^IVG.Ledger node (journal of the cited run); "
                "verify() went equal -> diverges, classification unrecorded_writes.")
NOJ_LIVE = (" Live (the cited run has no journal section): verify() went equal -> diverges, classification "
            "unrecorded_writes, and its differences name this writer's deletion.")


def replay_lemma(sites, run=None, note="", live=JOURNAL_LIVE):
    runs = [run] if isinstance(run, str) else list(run or [])
    ev = runs + sites + [REPLAY_CANON, REPLAY_COMPARE, ORIG_REPLAY, "iris_vector_graph/ledger/guard.py:69-80"]
    reason = ("Holds as detection, not as preservation (review R4-07). The writer writes content rows and no ledger "
              "record, so it breaks RPL-B3's premise ('no unrecorded writes') and replay no longer equals the store; "
              "what holds is that the divergence is reported: compare() sees the write and classifies it "
              "unrecorded_writes (RPL-B7.1), or the write lies outside the replay abstraction (a temporal-marked row, "
              "a node's graph, a reserved property, ekey) where replay still equals the store. The writer cannot make "
              "replay disagree with the store unseen. The product permits such writes on a non-strict ledger (the "
              "strict-mode guard refuses them only when strict, ledger/guard.py:69-80) and classifies them in verify() "
              "(replay.py:645-649), so this is a lemma (detection), not a finding." + note)
    if runs:
        d = D("lemma", "live", ev, [], reason + live)
    else:
        d = D("lemma", "inspected", ev, [], reason + " Inspected only for this writer.")
    d["holds_as"] = "detection"
    return d


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
    d = D("lemma", "inspected", sites + [LR_LIVEROWS, LR_MATCHES],
          [], f"{what} LiveRows counts rows by (COALESCE(graph_id, ''), id prefix) and record membership "
          "(Matches) reads only ledger globals, so an update that keeps every row's id and COALESCE'd graph "
          "changes neither whether a target is live nor which records are a target's; the writer adds no record." + note)
    if extra_runs:
        d["context_runs"] = [r[4:] for r in extra_runs]
        d["reason"] += (" Context only, not evidence (review R4-07): ws-live-migrations ran this writer while a "
                        "marker existed and it was a no-op there (rows_repaired 0 / already at 234 / backfilled 0), "
                        "so the target stayed not live and the records unchanged; it exercised nothing this lemma "
                        "rests on.")
    return d


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


def inserter(writer, sites, run, stmt_what, note_marker="", note_nlt="", note_replay="", replay_runs=None):
    W[writer] = {
        "INV-marker": marker_inserter(sites, run, note_marker),
        "INV-no-live-tombstone": nlt_inserter(sites, run, note_nlt),
        "INV-replay": replay_lemma(sites, run if replay_runs is None else replay_runs, note_replay),
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
         "The writer inserts node, property and rdf_edges rows no statement names, skipping tuples already present.",
         replay_runs=[R_RIMP],
         note_replay=" The INV-replay sub-check of ws-live-ins-import_rdf did not start from an equal baseline (a "
                     "%NOINDEX edge left by the previous case, F-C1250; erratum) and is not cited; ws-live-replay-import_rdf "
                     "re-ran it from an equal baseline.")
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
         ins_run("bulkloader_load_edges"), "The writer inserts node rows only.",
         replay_runs=[ins_run("bulkloader_load_edges"), R_NIE],
         note_replay=" In ws-live-ins-bulkloader_load_edges the baseline was equal and the write was classified; the "
                     "record's 'equal again after erasing' is wrong (erratum: the loader's %NOINDEX edge survived the "
                     "erase, F-C1250). ws-live-noindex-erase shows the same classification (nodes the writer registered "
                     "and the edge) from a clean namespace.")
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
                  note_replay="", replay_live=JOURNAL_LIVE):
    f = fk_lemma if kind == "fk" else nonkey_lemma
    W[writer] = {
        "INV-marker": f(sites, what_marker, extra_runs),
        "INV-no-live-tombstone": f(sites, what_marker, extra_runs),
        "INV-replay": replay_lemma(sites, replay_run, note_replay, live=replay_live),
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
              replay_run=R_COLL, replay_live=NOJ_LIVE,
              stmt=D("finding", "live", [R_COLL, f"{KG}Adjacency.cls:623-645", f"{KG}TemporalIndex.cls:325-343"] + COLL,
                     ["F-C0450"], "Live: a ledger relationship whose qualifiers hold temporal=1 (stored {\"temporal\":\"1\"}, "
                     "IsTemporalMarked accepts it) and a temporal edge on the same triple; deleting the temporal edge "
                     "(engine.delete_edge_temporal -> DeleteTemporalEdge -> RetractTemporalRow) deleted the ledger's "
                     "row and left its statement live: INV-stmt fails (F-C0450)."))
no_row_writer(f"{KG}Adjacency.cls::RetractTemporalRows", [f"{KG}Adjacency.cls:650-688"],
              "The writer deletes only rdf_edges rows (temporal-marked ones of a set of triples).", "",
              replay_run=R_PURGE, replay_live=NOJ_LIVE + " The run reached the deletion through RetractTemporalRows' "
              "fallback (RetractTemporalRow, Adjacency.cls:677-679), not its own %STARTSWITH DELETE.",
              stmt=D("finding", "live", [R_PURGE, f"{KG}Adjacency.cls:650-688", f"{KG}TemporalIndex.cls:944-1046"] + COLL,
                     ["F-C0450"], "Live: the purge (engine.purge_before -> RetireExpired -> RetractTemporalRows) on a "
                     "ledger relationship with qualifiers {\"temporal\":\"1\"}: the %STARTSWITH marker test misses, the "
                     "fallback RetractTemporalRow (Adjacency.cls:677-679) deletes the ledger's row and its statement "
                     "stays live (F-C0450)."))
no_row_writer(f"{SC}::retract_inference", [f"{SC}:3186-3259", f"{SC}:61"],
              "The writer deletes only rdf_edges rows (qualifiers LIKE '%\"inferred\":%').", "",
              replay_run=R_COLL, replay_live=NOJ_LIVE,
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

def deleter(writer, sites, run, stmt, note="", replay_run=None, replay_live=JOURNAL_LIVE):
    W[writer] = {
        "INV-marker": fc1301(sites, run, note),
        "INV-no-live-tombstone": fc1301(sites, run, note),
        "INV-replay": replay_lemma(sites, replay_run, live=replay_live),
        "INV-stmt": stmt,
    }


deleter(f"{SC}::delete_reification", [f"{SC}:3361-3397"], R_FC1301, replay_run=R_RDEL, stmt=stmt_lemma_rows([f"{SC}:3361-3397"], "The writer deletes rdf_reifications, property, label and node rows of "
                        "an id; a node row with an edge cannot go (fk_edges_source/dest refuse the DELETE and the call "
                        "rolls back), so no edge row is removed."))
deleter(f"{KG}Eraser.cls::DeleteBareSet", [f"{KG}Eraser.cls:1260-1315", f"{KG}Eraser.cls:1208-1248"], None,
        stmt_lemma_rows([f"{KG}Eraser.cls:1260-1315"], "The writer deletes node rows that no edge names (BareClauses, "
                        "and the foreign keys refuse a node with a dependant), so no edge row is removed."),
        note=" Its batches are TSTART ... TCOMMIT with TROLLBACK on error (Eraser.cls:1272-1313) and nest in a "
             "caller's transaction; it deletes ledger-recorded bare nodes (ws-live-stmt-collision: DropRows retired "
             "the 2 recorded endpoints through it).", replay_run=R_COLL,
        replay_live=NOJ_LIVE + " (its deletions there were the 2 recorded endpoints DropRows retired through it).")
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
             "error (TemporalPolicy.cls:173-219).", replay_run=R_COLL, replay_live=NOJ_LIVE)
deleter(f"{NE}::_drop_orphaned_props", [f"{NE}:1617-1646", f"{NE}:1761-1866", PROPS_NOFK], None,
        stmt_lemma_rows([f"{NE}:1617-1646"], "The writer deletes rdf_props rows only."),
        note=" It deletes only property rows whose node row is absent, which LiveRows still counts; it runs in "
             "bulk_create_nodes' SQL path inside its WriteTxn (nodes_edges.py:1761-1866, call at 1843), so a target whose only live "
             "rows are such properties is seen not live while the delete is uncommitted.")

# SQL fallbacks of the store's deleters: reachable when the Eraser probe fails (F-C1750) ----------------------
# Originally open as "unreached at the pin's deploy" (fallback_open below, kept for the record). The orchestrator's
# live probe ws-live-sql-fallback-priv reached them through the pin's public API: a writing role without
# %Native_ClassExecution is refused the dictionary SELECT (-99) and the native IDKEYExists (<PROTECT>), and
# _has_eraser_method caches the exception as "absent" (iris_sql_store.py:1307-1318).

def fallback_open(what):
    return (f"open: unreached at the pin's deploy. {what} runs only when IRISGraphStore._has_eraser_method answers "
            "False (iris_sql_store.py:1307-1318), i.e. when Graph.KG.Eraser.EraseNodeIds / EraseEdges is not "
            "compiled; initialize_schema compiles the Eraser with the ledger (ws-deploy-auditb: 66 classes "
            "unchanged), and the deployed path goes through the Eraser. The probe caches any exception as 'absent', "
            "and on that path the SQL deletes recorded rows with no statement cleanup inside a WriteTxn that can roll "
            "back (the F-0303 / F-C1301 shapes). That configuration was not reproduced, so no finding is recorded.")


R_SFP = "run:ws-live-sql-fallback-priv"
SQLF = [f"{ST}:1307-1318", f"{ST}:1320-1361", f"{ST}:1474-1518", "iris_vector_graph/_dictionary.py:46-64"]
SFP_REACH = (" Reachable at the pin (ws-live-sql-fallback-priv): with a writing role that lacks "
             "%Native_ClassExecution, the probe's dictionary SELECT is refused (-99), its native IDKEYExists raises "
             "<PROTECT>, and _has_eraser_method caches the exception as 'absent' (iris_sql_store.py:1307-1318), so "
             "engine.delete_node / delete_nodes take this SQL path (F-C1750).")


def sfp_stmt(what, sites):
    return D("finding", "live", [R_SFP] + sites + SQLF, ["F-C1750"],
             f"Live: {what} ran as plain SQL after the refused Eraser probe was cached as absent; it deleted the "
             "recorded edge row and left its ledger statement (^IVG.Ledger tuple and stmt, closed seq empty) live "
             "without the row, with no warning (F-C1750). With ADMIN_GUIDE's writing row the same call went through "
             "Graph.KG.Eraser and the statement went with the row (control in the same run).")


W[f"{ST}::_delete_nodes_sql"] = {
    "INV-marker": fc1301([f"{ST}:1363-1418", R_SFP] + SQLF, None, SFP_REACH),
    "INV-no-live-tombstone": fc1301([f"{ST}:1363-1418", R_SFP] + SQLF, None, SFP_REACH),
    "INV-replay": replay_lemma([f"{ST}:1363-1418"], None),
    "INV-stmt": sfp_stmt("engine.delete_node('sfp|a') (store.delete_nodes -> _delete_nodes_sql, "
                         "iris_sql_store.py:1363-1418)", [f"{ST}:1363-1418"]),
}
W[f"{ST}::delete_edges"] = {
    "INV-marker": fk_lemma([f"{ST}:1474-1518"], "The writer deletes only rdf_edges rows (through EraseEdges or its "
                           "SQL fallback)."),
    "INV-no-live-tombstone": fk_lemma([f"{ST}:1474-1518"], "The writer deletes only rdf_edges rows (through "
                                      "EraseEdges or its SQL fallback)."),
    "INV-replay": replay_lemma([f"{ST}:1474-1518"], None),
    "INV-stmt": sfp_stmt("IRISGraphStore.delete_edges([('sfp|c', 'R', 'sfp|d')]) (exported by iris_vector_graph; "
                         "its SQL DELETE, iris_sql_store.py:1504-1518)", [f"{ST}:1474-1518"]),
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
                  "Graph_KG rows of the tombstoned revisions keep message, source, correlation id and key. Depends "
                  "on the operator's ruling O-1 (review R2-07): fc1306-legacy-ledger-rows compiled a non-pin release "
                  "(v4.5.1) into a scratch namespace; if O-1 rules that out of scope, this discharge falls back to "
                  "inspected (legacy.py:606-646, LedgerRedact.cls:353-378)."),
}
W["iris_vector_graph/_engine/legacy.py::copy_ledger_history"]["INV-text"]["depends_on"] = ["O-1"]
W["iris_vector_graph/_engine/legacy.py::copy_ledger_history"]["INV-text"]["depends_on_status"] = {
    "O-1": "satisfied: operator clarification recorded in experiment/playbook-completion/incidents/O-1-FIXTURES.md "
           "(the fixture setup behind fc1306-legacy-ledger-rows is authorized verification setup)"}
W["iris_vector_graph/_engine/legacy.py::copy_ledger_history"]["INV-text"]["evidence"].append(
    "experiment/playbook-completion/incidents/O-1-FIXTURES.md")
W["iris_vector_graph/_engine/legacy.py::copy_ledger_history"]["INV-text"]["reason"] += (
    " O-1 is now answered (incidents/O-1-FIXTURES.md): the setup is authorized and the live grade stands.")
W["<any SQL client>::INSERT INTO Graph_KG.ledger_revisions"] = {
    "INV-text": D("guard", "live", ["run:ws-live-sql-guard", "iris_src/src/Graph/KG/LedgerRevision.cls:1-5",
                                    "iris_src/src/Graph/KG/LedgerRevision.cls:44",
                                    "iris_src/src/Graph/KG/LedgerRevision.cls:87-108"], [],
                  "seq is the table's unique IdKey (SeqIdx) and UPDATE/DELETE are refused by RejectUpdate/RejectDelete, "
                  "so an SQL INSERT can neither replace nor rewrite the row of a revision that has records; a new row's "
                  "seq has no record (records are written with their row in one commit), so no tombstone sits under "
                  "its text. Live: INSERT of the redacted seq refused SQLCODE -119 (SeqIdx), UPDATE refused -132, the "
                  "text stays cleared. Side effect recorded separately: an INSERT of head+1 made the next ledger commit fail "
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
    BAD = PC / "writesets" / "BREADTH-A-DISCHARGES.json"
    bad = json.loads(BAD.read_text()) if BAD.exists() else {}
    BADREL = "experiment/playbook-completion/writesets/BREADTH-A-DISCHARGES.json"

    def ba_summary(m, prefix=None):
        es = [v for k, v in bad.items() if k != "_doc" and (k.startswith(prefix) if prefix else
                                                               (v.get("module") == m and "|" in k and not k.startswith("m")))]
        kinds = {}
        for v in es:
            kinds[v["discharge"]] = kinds.get(v["discharge"], 0) + 1
        opn = sorted(k for k, v in bad.items() if k != "_doc" and v in es and v["discharge"] == "open")
        fs = sorted({f for v in es for f in v.get("findings", [])})
        grades = {v["grade"] for v in es if v["discharge"] != "open"}
        return len(es), kinds, opn, fs, grades

    for m in ("01", "03", "04", "05", "06"):
        n, kinds, opn, fs, grades = ba_summary(m)
        census_open = opened(m)
        st = "open" if (opn or census_open) else "finding" if fs else "lemma"
        out[f"module:{m}"] = {
            "discharge": st, "grade": "open" if st == "open" else ("inspected" if "inspected" in grades else sorted(grades)[0]),
            "evidence": [BADREL, BA, "experiment/playbook-completion/writesets/DISCHARGES.json"],
            "findings": fs,
            "reason": (f"{len(ids(m))} census cells of module {m}, each with one discharge in DISCHARGES.json "
                       f"({len(census_open)} open). The {ba_open[m]} open breadth-a (module invariant, writer) pairs of {BA} "
                       f"each have one discharge in BREADTH-A-DISCHARGES.json ({n} entries: "
                       + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())) + "); "
                       + (f"open: {'; '.join(opn)}." if opn else "none is open.")
                       + " The product fails where a finding discharges a pair."),
        }
    n8, k8, o8, f8, g8 = ba_summary("08", "m08|")
    out["module:08"] = {"discharge": "open" if o8 else "guard", "grade": "inspected", "findings": f8,
                        "evidence": [BADREL, "experiment/playbook-completion/modules/08.json", "run:ws-live-fk-guard"],
                        "reason": f"Module 08's open plan item (CYP-I5.5/CYP-I5.6/SYS-I2 against other modules' writers: "
                                  f"engine.direct_write, bulk_loader, fhir sync, raw SQL) has {n8} discharges in "
                                  f"BREADTH-A-DISCHARGES.json (m08|...: " + ", ".join(f"{k} {v}" for k, v in sorted(k8.items()))
                                  + "): the composite foreign keys (live for raw SQL) and the bulk loader's endpoint "
                                  "registration. Module 08's other pairs were already dispositioned (modules/08.json)."}
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
                        "reason": "INV-replay is module 14's: of the 42 census INV-replay obligations (4 conditional), 40 are "
                        "lemmas that hold as detection, not preservation (review R4-07): 36 writers make unrecorded "
                        "content writes, breaking RPL-B3's no-unrecorded-writes premise, and verify() classifies them "
                        "(RPL-B7.1; live for 20 writers) or they lie outside the replay abstraction; 4 conditional "
                        "writers write no content store at the pin (holds_as vacuous). SetNodeJSON's cell is a guard and "
                        "Snapshot.ImportGlobals' a finding (F-1806: imported ledger records no longer replay to the "
                        "store). Verification cell closes at the weakest grade (inspected); the product's other replay "
                        "findings (F-1305, F-C1308, F-1401) are outside these writer obligations."}
    rest = {
        "15": ("FHIR writers: live blocked (ws-live-fhir-blocked), discharged at inspected grade or open; reify_edge "
               "live, delete_reification live. Still open in module 15's cell and outside the census: the (invariant, "
               "plan) pairs of FHIR Rebuild/SyncOnce/Reinterpret/Schedule and the table-map/crosswalk writers it names."),
        "17": ("iris_sql_store write_nodes/write_edges live; the SQL fallbacks of _delete_nodes_sql and delete_edges "
               "are open (unreached at the pin's deploy); insert_vector's conditional cells are resolved (no product "
               "caller)."),
        "18": ("Snapshot.ImportGlobals: finding F-1806 (live), Snapshot.SetNodeJSON: guard (live), import_rdf live, "
               "restore's three write-set gaps live (F-C1850). snapshot.restore_merge (not a plan) now has 9 discharges "
               "in BREADTH-A-DISCHARGES.json (m18|...): INV-text/INV-retry/INV-marker live (F-C1850 with merge=True, "
               "ws-live-ba-restore-merge), the other five INV-* by F-1801's overlay (inspected), TMP-B1.7 by F-1805."),
    }
    for m in ("15", "17", "18"):
        op = opened(m)
        closed18 = (m == "18" and not op)
        out[f"module:{m}"] = {
            "discharge": "finding" if closed18 else "open", "grade": "inspected" if closed18 else "open",
            "evidence": ["experiment/playbook-completion/writesets/DISCHARGES.json"]
                        + (["experiment/playbook-completion/writesets/BREADTH-A-DISCHARGES.json"] if m == "18" else []),
            "findings": ["F-1806", "F-C1850", "F-1801", "F-1805"] if closed18 else [],
            "reason": (f"{len(ids(m))} census cells of module {m}, each with one discharge in DISCHARGES.json; "
                       f"{len(op)} of them open ({', '.join(op) or 'none'}). " + rest[m]),
        }
    return out


# ------------------------------------------------------------------------------------- runs -> exercised pairs
# Machine-readable map (written to writesets/RUN-PAIRS.json, checked by check_discharges.py C9-C12): for each lane run
# a census discharge cites, the (invariant, writer) pairs it exercised and the outcome on each ("fail": the product
# broke the invariant for that writer in the run; "pass": the run observed the invariant hold or the guard refuse),
# plus what else the run failed on when that is not a census pair, and runs that are context for a pair (cited, but
# they exercised nothing the discharge rests on).

def _w(name):
    return {
        "store_node": f"{NE}::store_node", "store_edge": f"{NE}::store_edge",
        "bulk_create_edges": f"{NE}::bulk_create_edges", "bulk_ingest_edges": f"{NE}::bulk_ingest_edges",
        "BulkIngestEdgesSQL": f"{KG}EdgeScan.cls::BulkIngestEdgesSQL", "BulkIngestNodesSQL": f"{KG}EdgeScan.cls::BulkIngestNodesSQL",
        "RegisterDefaultNode": f"{KG}EdgeScan.cls::RegisterDefaultNode", "write_nodes": f"{ST}::write_nodes",
        "write_edges": f"{ST}::write_edges", "create_edge_temporal": f"{TM}::create_edge_temporal",
        "bulk_create_edges_temporal": f"{TM}::bulk_create_edges_temporal", "reify_edge": f"{SC}::reify_edge",
        "_register_endpoints": "iris_vector_graph/bulk_loader.py::_register_endpoints", "import_rdf": f"{SN}::import_rdf",
        "delete_reification": f"{SC}::delete_reification", "RetractTemporalRow": f"{KG}Adjacency.cls::RetractTemporalRow",
        "RetractTemporalRows": f"{KG}Adjacency.cls::RetractTemporalRows", "DropRows": f"{KG}TemporalPolicy.cls::DropRows",
        "retract_inference": f"{SC}::retract_inference", "DeleteBareSet": f"{KG}Eraser.cls::DeleteBareSet",
        "ImportGlobals": f"{KG}Snapshot.cls::ImportGlobals", "SetNodeJSON": f"{KG}Snapshot.cls::SetNodeJSON",
        "sql": "<any SQL client>::INSERT INTO Graph_KG.ledger_revisions",
        "gap": f"{SN}::_import_global_from_ndjson", "add_graph_id_to_nodes": f"{GS}::add_graph_id_to_nodes",
        "copy_ledger_history": "iris_vector_graph/_engine/legacy.py::copy_ledger_history",
        "_delete_nodes_sql": f"{ST}::_delete_nodes_sql", "delete_edges": f"{ST}::delete_edges",
        "tighten_graph_id_column": f"{GS}::tighten_graph_id_column", "ensure_ekey": f"{GS}::ensure_ekey",
        "ensure_props_value_key": f"{GS}::ensure_props_value_key",
    }[name]


def _ex(inv, name, outcome, note=""):
    return {"invariant": inv, "writer": _w(name), "outcome": outcome, **({"note": note} if note else {})}


INS_WRITERS = {
    "store_node": ["store_node"], "store_edge": ["store_edge"],
    "bulk_create_nodes": ["BulkIngestNodesSQL", "RegisterDefaultNode"],
    "bulk_ingest_edges": ["BulkIngestEdgesSQL", "RegisterDefaultNode", "bulk_ingest_edges"],
    "bulk_create_edges": ["bulk_create_edges"], "store_write_nodes": ["write_nodes"],
    "store_write_edges": ["write_edges"], "create_edge_temporal": ["create_edge_temporal"],
    "bulk_create_edges_temporal": ["bulk_create_edges_temporal"], "reify_edge": ["reify_edge"],
    "bulkloader_load_edges": ["_register_endpoints"], "import_rdf": ["import_rdf"],
}
RUN_PAIRS = {}
for _run, _ws in INS_WRITERS.items():
    ex = []
    for _n in _ws:
        note = ("entry point engine.bulk_ingest_edges, server path (BulkIngestEdgesSQL); the census site, the row-by-row "
                "fallback, did not execute") if _n == "bulk_ingest_edges" else ""
        if _run != "import_rdf":
            ex.append(_ex("INV-replay", _n, "pass", note or ("verify() classified the write (equal -> diverges, "
                          "unrecorded_writes); the record's 'equal again after erasing' is wrong (erratum)"
                          if _run == "bulkloader_load_edges" else "")))
        ex.append(_ex("INV-marker", _n, "fail", note))
        ex.append(_ex("INV-no-live-tombstone", _n, "fail", note))
    RUN_PAIRS[f"ws-live-ins-{_run}"] = {
        "exercised": ex, "journal": True,
        "not_exercised": (["INV-replay of import_rdf: the baseline was not equal (a %NOINDEX edge row left by the "
                           "previous case, F-C1250); re-run as ws-live-replay-import_rdf"] if _run == "import_rdf" else [])}
RUN_PAIRS.update({
    "ws-live-fc1301-delete-reification": {"journal": True, "exercised": [
        _ex("INV-marker", "delete_reification", "fail"), _ex("INV-no-live-tombstone", "delete_reification", "fail")],
        "not_exercised": ["INV-replay of delete_reification: both phases' deletes were rolled back; the diverges "
                          "it shows is a completed redaction over restored content (review R4-02)"]},
    "ws-live-replay-delete_reification": {"journal": True, "exercised": [
        _ex("INV-replay", "delete_reification", "pass", "committed delete, no caller transaction")]},
    "ws-live-replay-import_rdf": {"journal": True, "exercised": [
        _ex("INV-replay", "import_rdf", "pass", "equal baseline, full-scan residue check 0")]},
    "ws-live-stmt-collision": {"journal": False, "exercised": [
        _ex("INV-stmt", "RetractTemporalRow", "fail"), _ex("INV-stmt", "DropRows", "fail"),
        _ex("INV-stmt", "retract_inference", "fail"),
        _ex("INV-replay", "RetractTemporalRow", "pass", "one verify() after all three writers; its differences name rel 1"),
        _ex("INV-replay", "DropRows", "pass", "differences name rel 2"),
        _ex("INV-replay", "retract_inference", "pass", "differences name rel 3"),
        _ex("INV-replay", "DeleteBareSet", "pass", "differences name nodes wsq|c, wsq|d (retired through DropRows)")]},
    "ws-live-stmt-purge": {"journal": False, "exercised": [
        _ex("INV-stmt", "RetractTemporalRows", "fail", "through its fallback RetractTemporalRow"),
        _ex("INV-replay", "RetractTemporalRows", "pass", "through its fallback RetractTemporalRow")]},
    "ws-live-snap-importglobals": {"journal": True, "exercised": [
        _ex("INV-shape", "ImportGlobals", "fail"), _ex("INV-replay", "ImportGlobals", "fail")]},
    "ws-live-snap-setnodejson": {"journal": True, "exercised": [
        _ex(i, "SetNodeJSON", "pass") for i in ("INV-shape", "INV-isolation", "INV-text", "INV-retry", "INV-marker",
                                                "INV-no-live-tombstone", "INV-replay", "INV-stmt")]},
    "ws-live-sql-guard": {"journal": False, "exercised": [_ex("INV-text", "sql", "pass")]},
    "ws-live-sql-insert-wedge": {"journal": False, "exercised": [_ex("INV-text", "sql", "pass")],
                                 "failed_other": ["F-C1150: the planted head+1 row made the next ledger commit fail "
                                                  "(availability, not an INV-text break)"]},
    "ws-live-gap-restore": {"journal": False, "exercised": [_ex("INV-text", "gap", "fail"), _ex("INV-retry", "gap", "fail")]},
    "ws-live-gap-marker": {"journal": False, "exercised": [_ex("INV-marker", "gap", "fail")]},
    "ws-live-migrations": {"journal": False, "exercised": [_ex("INV-marker", "add_graph_id_to_nodes", "fail")],
                           "context_for": [[i, _w(n)] for n in ("tighten_graph_id_column", "ensure_ekey",
                                                                 "ensure_props_value_key")
                                           for i in ("INV-marker", "INV-no-live-tombstone")]},
    "ws-live-noindex-erase": {"journal": False, "exercised": [
        _ex("INV-replay", "_register_endpoints", "pass", "verify() after BulkLoader.load_edges named the 2 registered "
            "nodes and the edge (unrecorded_writes)")],
        "failed_other": ["F-C1250: the loader's %NOINDEX edge row survived delete_nodes_by_prefix of both endpoints "
                         "and EraseAll+PurgeAll (an erasure defect, not a census pair)"]},
    "fc1306-legacy-ledger-rows": {"journal": False, "exercised": [_ex("INV-text", "copy_ledger_history", "fail")],
                                  "lane": "fc1306"},
    "ws-live-sql-fallback-priv": {"journal": False, "lane": "orchestrator", "exercised": [
        _ex("INV-stmt", "_delete_nodes_sql", "fail", "role without %Native_ClassExecution: the Eraser probe cached "
            "absent; the statement of the deleted edge stays live (F-C1750)"),
        _ex("INV-stmt", "delete_edges", "fail", "same role, IRISGraphStore.delete_edges' SQL DELETE (F-C1750)")],
        "context_for": [[i, _w("_delete_nodes_sql")] for i in ("INV-marker", "INV-no-live-tombstone")]},
})


def _reg(rid):
    p = PC / "evidence" / "runs" / f"{rid}.json"
    return json.loads(p.read_text()) if p.exists() else {}


def attribute_failed_runs(entries):
    """lemma/guard entries: every cited failed run must have failed on another pair; record which (R4-02)."""
    for oid, e in entries.items():
        if e["discharge"] not in ("lemma", "guard"):
            continue
        other, why = [], {}
        for ev in e["evidence"]:
            if not ev.startswith("run:"):
                continue
            rid = ev[4:]
            if _reg(rid).get("result") != "fail":
                continue
            m = RUN_PAIRS.get(rid)
            if m is None:
                raise SystemExit(f"{oid}: cites failed run {rid} with no RUN_PAIRS entry")
            mine = [x for x in m["exercised"] if x["invariant"] == e["invariant"] and x["writer"] == e["writer"]]
            if any(x["outcome"] == "fail" for x in mine):
                raise SystemExit(f"{oid}: cites {rid}, which failed on this very pair: the cell must fail")
            fails = [f"({x['invariant']}, {x['writer'].split('::')[-1]})" for x in m["exercised"] if x["outcome"] == "fail"]
            fails += m.get("failed_other", [])
            other.append(rid)
            why[rid] = "failed on other pairs only: " + "; ".join(fails)
        if other:
            e["failed_runs_other_pairs"] = other
            e["failed_runs_other_pairs_reason"] = why
        if e["discharge"] == "lemma" and e["invariant"] == "INV-replay" and "holds_as" not in e:
            e["holds_as"] = "vacuous"
            e["reason"] += (" holds_as vacuous: at the pin this writer writes no content store the replay reads (no "
                            "product caller, a statement that matches no row on the pin's schema, or embedding tables "
                            "only), so there is nothing to detect.")


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
    attribute_failed_runs(out)
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
    pairs = json.dumps({"_doc": "Runs cited by census discharges -> the (invariant, writer) pairs each exercised, with "
                                "the outcome; failed_other: what else the run failed on; context_for: pairs the run is "
                                "cited for as context only. Generated by writesets/tools/build_discharges.py.",
                        "runs": RUN_PAIRS}, indent=1, sort_keys=True) + "\n"
    if "--check" in sys.argv:
        ok = OUT.exists() and OUT.read_text() == text and PAIRS.exists() and PAIRS.read_text() == pairs
        return 0 if ok else 1
    OUT.write_text(text)
    PAIRS.write_text(pairs)
    n = {}
    for k, v in data.items():
        if k.startswith(("WS-OBL", "WS-COND", "WS-GAP")):
            n[v["discharge"]] = n.get(v["discharge"], 0) + 1
    print(f"wrote {OUT}: {sum(n.values())} census obligations {n}, "
          f"{sum(1 for k in data if k.startswith('module:'))} module entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
