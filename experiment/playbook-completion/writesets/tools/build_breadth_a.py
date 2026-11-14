#!/usr/bin/env python3
"""Build writesets/BREADTH-A-DISCHARGES.json: one discharge for every breadth-a module-invariant pair with status
'open' in experiment/playbook-completion/models/breadth-a/writesets.json (modules 01, 03, 04, 05, 06), plus the
open module-08 pairs (modules/08.json invariant_writesets) and snapshot.restore_merge (module 18, not a plan).

    python experiment/playbook-completion/writesets/tools/build_breadth_a.py [--check]

Keys. breadth-a pairs carry no id; the pair's identity is (module, invariant, writer), which is unique in the file,
so the key is "<module>|<invariant>|<writer>". The supplementary pairs use "m08|..." and "m18|...".

Method (mechanical grouping). A pair's writer is a footprint entry point (footprints/NN.json). The footprint lists,
for each store it writes, the functions that write it ("at": path:line (function)). For each invariant, every such
function is put in one class with one argument (CLASSES below); a pair's discharge is the combination of the classes
of the functions through which it writes the invariant's read set (a finding class wins over a lemma or guard, and
the findings are joined). Writers with no function list, or whose decisive evidence is a live run, have an explicit
entry (OVERRIDES). Model checks of breadth-a (models/breadth-a/RESULTS.json; runs breadth-a-mc-*) are cited where the
family's model has the writer as one of its actions; the check is named in the reason. Grades: mc (an explorer check,
exhaustive within its bounds, of the as-built design exhibits the violation for the modelled action; a reviewed design
that passes is a statement about the model only), live (a registered ws-live run exercised this pair:
BREADTH-A-RUN-PAIRS.json), inspected (read at the pin; weakest).
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

PC = Path(__file__).resolve().parents[2]
REPO = PC.parents[1]
PIN = "3eaa79cf77d3e0a879b2cced634cf2729d81499e"
BA = PC / "models" / "breadth-a" / "writesets.json"
OUT = PC / "writesets" / "BREADTH-A-DISCHARGES.json"
PAIRS_OUT = PC / "writesets" / "BREADTH-A-RUN-PAIRS.json"
KG = "iris_src/src/Graph/KG/"

# ------------------------------------------------------------------------------------- citations from the pin tree

_SRC = {}


def _pin(path):
    if path not in _SRC:
        r = subprocess.run(["git", "show", f"{PIN}:{path}"], cwd=REPO, capture_output=True, text=True)
        _SRC[path] = r.stdout if r.returncode == 0 else None
    return _SRC[path]


def cite(path, name):
    """path:start-end of ClassMethod/Method `name` (.cls) or def `name` (.py) at the pin."""
    src = _pin(path)
    if src is None:
        raise SystemExit(f"{path} not at the pin")
    if path.endswith(".cls"):
        L = src.split("\n")
        for i, l in enumerate(L):
            if re.match(rf"^(ClassMethod|Method)\s+{re.escape(name)}\b", l):
                j = i + 1
                while j < len(L) and L[j] != "}":
                    j += 1
                return f"{path}:{i + 1}-{j + 1}"
    else:
        for n in ast.walk(ast.parse(src)):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
                return f"{path}:{n.lineno}-{n.end_lineno}"
    raise SystemExit(f"{name} not found in {path}")


A = lambda m: cite(KG + "Adjacency.cls", m)          # noqa: E731
TI = lambda m: cite(KG + "TemporalIndex.cls", m)     # noqa: E731
NE = "iris_vector_graph/_engine/nodes_edges.py"
GS = "iris_vector_graph/schema.py"
BL = "iris_vector_graph/bulk_loader.py"
FK = f"{GS}:34-44"
FK_LABELS = f"{GS}:403-409"


def D(kind, grade, evidence, findings=(), reason="", **extra):
    d = {"discharge": kind, "grade": grade, "evidence": list(evidence), "findings": list(findings), "reason": reason}
    d.update(extra)
    return d


# ------------------------------------------------------------------------------------------------------ classes
# CLASSES[invariant][class] = (discharge, grade, findings, evidence, reason); FUNC[invariant][function] = class.

R_DEG_W = "run:breadth-a-mc-adj_degree-hd0401-writer-window"
R_DEG_AB = "run:breadth-a-mc-adj_degree-as-built"
R_TOK_AB = "run:breadth-a-mc-adj_token-as-built"
R_GID_AB = "run:breadth-a-mc-gid_mode-as-built"
R_MARK_AB = "run:breadth-a-mc-tmp_mark-as-built"
R_BUCK_AB = "run:breadth-a-mc-tmp_bucket-as-built"
R_Q_AB = "run:breadth-a-mc-vec_queue-as-built"
R_IVF_AB = "run:breadth-a-mc-vec_ivf-as-built"
R_FK = "run:ws-live-fk-guard"

SQLTEXT = ("lemma", "inspected", [], [cite(GS, "get_base_schema_sql"), cite(GS, "get_indexes_sql"),
                                      cite(GS, "get_bulk_insert_sql"), cite(GS, "get_graph_scope_migration_sql")],
           "The function returns SQL text and writes nothing itself; the footprint counts the tables its statements "
           "name. The statements are judged with the writers that execute them (schema setup's DDL, the bulk "
           "loader's INSERT).")
DDL = ("lemma", "inspected", [], [cite(GS, "ensure_indexes"), cite(GS, "ensure_ekey"), cite(GS, "add_graph_id_column"),
                                  cite(GS, "update_spo_unique_constraint"), FK],
       "Schema statements only (CREATE/ALTER TABLE, CREATE INDEX, constraints, ekey 0 for NULL under the pre-234 key): "
       "no row is added and no row's (s, p, o_id, graph_id) changes; the unique key (s, p, o_id, graph_id, ekey), or "
       "before 234 (s, p, o_id, graph_id), is kept or created, so no statement of this writer can add a second row "
       "of a triple, retract a row, mark or unmark one, or touch a timestamp.")
NOOP_REBUILD = ("lemma", "inspected", [], [cite(KG + "TraversalBuild.cls", "BuildKG")],
                "The rdf_edges (and rdf_labels) writes of this writer are index builds (%BuildIndices of idxedgesadj / "
                "idxlabelsadj, TraversalBuild.cls BuildKG; the journal candidate J12 of sync shows them as index "
                "nodes): no row is added, removed or changed.")


def _cls(*a):
    return a


CLASSES = {
    "ADJ-I5.9": {
        "W": ("finding", "mc", ["F-C0401"], [R_DEG_W, A("Put"), A("Remove"), A("PutKeyed"), A("RowUpdate"),
                                             cite(KG + "Adj.cls", "Degree")],
              "The writer changes ^KG(\"out\") through Graph.KG.Adjacency's one-writer methods, which set the out entry "
              "and then $Increment ^KG(\"gen\") inside the caller's transaction (e.g. Adjacency.cls:87-89, 152-155): "
              "it is family adj_degree's writer W. A stop between the out write and the generation step lets a "
              "reader cache a count that includes the undone write (F-C0401; check adj_degree-hd0401-writer-window, "
              "exhaustive within bounds, shows it; the full reviewed design adj_degree-reviewed passes, model only)."),
        "E": ("finding", "mc", ["F-0401"], [R_DEG_AB, A("RemoveSource"), A("RemoveAll"), A("RemoveGraph")],
              "The writer kills ^KG(\"gen\") (and degc) with the out entries (RemoveSource/RemoveAll/RemoveGraph): "
              "family adj_degree's eraser E. A generation killed back to 0 lets an in-flight reader that read it "
              "before store a wrong count as current (F-0401, intent-undecided; check adj_degree-as-built-F0401-erase "
              "in run breadth-a-mc-adj_degree-as-built)."),
        "R": ("finding", "mc", ["F-C0401", "F-0401"], [R_DEG_W, R_DEG_AB, cite(KG + "Adj.cls", "Degree"),
                                                       cite(KG + "Adj.cls", "WarmFill")],
              "The writer stores ^KG(\"degc\") through Adj.Degree or Adj.WarmFill (probe, count, store if the "
              "generation did not move): family adj_degree's reader R. Its stored entry is the one that becomes "
              "wrongly current in both as-built counterexamples (writer stopped before its generation step, F-C0401; "
              "generation killed, F-0401)."),
        "F": ("lemma", "inspected", [], [A("FillEdge"), A("FillTriple"), A("BeginRebuild"), A("RemoveAll"),
                                         cite(KG + "TraversalBuild.cls", "BuildKG")],
              "FillEdge/FillTriple write out entries without a generation step, but only inside a rebuild "
              "(callers TraversalBuild.cls:119, 194): BuildKG holds Adjacency.BeginRebuild's shared lock on "
              "^IVG.AdjW, which every reader's exclusive probe on ^IVG.AdjW(g) conflicts with (Adj.cls Degree), "
              "after RemoveAll killed degc; no count is stored against a partly filled source. (The rebuild's "
              "RemoveAll is class E.)"),
        "V": ("lemma", "inspected", [], [A("Reweight"), A("SetLeafFromLowest"), cite(KG + "Adj.cls", "Degree")],
              "The writer changes an out entry's value (a weight: Reweight; a multigraph triple's leaf weight: "
              "SetLeafFromLowest, inside PutKeyed/RemoveKeyed/RowUpdate) and no entry's presence or \"#\" count; "
              "Adj.Count counts entries, so no stored out-degree changes."),
    },
    "ADJ-I11.2": {
        "W": ("finding", "mc", ["F-0402"], [R_TOK_AB, A("Put"), A("Remove"), A("PutKeyed"), A("Reweight"), A("RemoveAll")],
              "The writer changes ^KG(\"out\") (presence or weight) and then $Increments ^KG(\"__version\") inside "
              "the caller's transaction (Adjacency.cls:87-92 and the same order in Remove, PutKeyed, RemoveKeyed, "
              "PutShadow, RowUpdate, Reweight, RemoveSource, RemoveAll): family adj_token's writer W. A build that "
              "reads the new token and the uncommitted edge stores an answer that stays current after the write "
              "rolls back (F-0402, live; check adj_token-as-built-F0402)."),
        "B": ("finding", "mc", ["F-0402"], [R_TOK_AB, cite(KG + "TraversalBuild.cls", "Build2HopStats"),
                                            cite(KG + "TraversalBuild.cls", "Build2HopExactStats")],
              "The writer is a token-stamped build (the two-hop counts ^KG(\"deg2p\") and ^IVG.BuiltFrom, "
              "TraversalBuild.cls Build2HopStats / Build2HopExactStats): family adj_token's builder B, whose model "
              "names the two-hop counts among its representatives. It reads the token, then the adjacency without "
              "a lock, then stores under the token: F-0402 (check adj_token-as-built-F0402)."),
        "K": ("lemma", "inspected", [], [cite(KG + "TraversalBuild.cls", "BuildKG")],
              "BuildKG's own token step comes after all its writes (TraversalBuild.cls:145, and :162 on failure), "
              "outside any transaction: an answer computed before the step carries the old token (stale, never "
              "wrongly current) and nothing it wrote is rolled back afterwards."),
        "L": ("lemma", "inspected", [], [A("PutLabel"), A("RemoveLabel")],
              "Label writes (Adjacency.PutLabel/RemoveLabel/RemoveAllLabels via the label index) move the token but "
              "write no ^KG(\"out\") entry; ADJ-I11.2 is about the edges a cached answer holds, so no answer can hold "
              "an uncommitted edge through this writer (label-filtered answers are outside this invariant)."),
        "I": ("lemma", "inspected", [], [cite(KG + "Eraser.cls", "InvalidateDerived"), cite(KG + "ArnoAccel.cls", "BumpVersion")],
              "The writer kills stamped stores (^IVG.AlgoCache, ^KG(\"deg2p\")) or moves the token without writing "
              "an edge: both can only make an entry stale, never wrongly current."),
    },
}
GUARD_ANYKEY = ("guard", "inspected", [], [A("AssertTemporalRow"), cite(KG + "EdgeScan.cls", "BulkIngestEdgesSQL"),
                                           cite(NE, "bulk_ingest_edges"), FK],
                "The insert is guarded by an existence test on (s, p, o_id, graph) over every edge key (AssertTemporalRow's "
                "NOT EXISTS, Adjacency.cls:603; BulkIngestEdgesSQL's SELECT, EdgeScan.cls:299-301 region; bulk_ingest_edges' "
                "NOT EXISTS), and the unique key refuses a concurrent second ekey-0 row: the writer never adds a second "
                "row of a triple. Residual: the test reads through the indexes and misses a row a %NOINDEX bulk load "
                "left unindexed (F-C0350, the bulk loader's pair).")
DEL_ROWS = ("lemma", "inspected", [], [A("RetractTemporalRow"), cite(KG + "TemporalPolicy.cls", "DropRows"),
                                       cite(KG + "Eraser.cls", "EraseAll"), cite(NE, "delete_edge")],
            "The writer only deletes rdf_edges rows; a graph's number of rows per triple can only drop, so no "
            "parallel edge appears.")
UPD_Q = ("lemma", "inspected", [], [cite(NE, "set_edge_weight"), cite(NE, "_adopt_temporal_row")],
         "The writer only updates qualifiers of existing rows; no row is added and no (s, p, o_id, graph_id, ekey) changes.")
CLASSES["GID-I4.10"] = {
    "SQLTEXT": SQLTEXT, "DDL": DDL, "REB": NOOP_REBUILD, "DEL": DEL_ROWS, "UPD": UPD_Q, "GUARD": GUARD_ANYKEY,
    "CE": ("finding", "inspected", ["F-0201"], [R_GID_AB, cite(NE, "create_edge")],
           "The writer inserts through create_edge, whose guard tests only edge key 0 (nodes_edges.py:1205-1219): "
           "a lone row at ekey 1 does not stop a second row (F-0201, live; check gid_mode-as-built-F0201)."),
    "BL": ("finding", "live", ["F-C0350"], ["run:ws-live-ba-noindex-parallel", cite(BL, "load_edges"),
                                            f"{BL}:456-460"],
           "BulkLoader.load_edges inserts with %NOINDEX %NOCHECK: the row is not in the unique index, so a later "
           "create_edge of the triple added a second row at the same ekey 0 in a mode-off graph, and two loads with "
           "skip_existing=False wrote two rows; rebuild_all_indices then succeeded with the duplicates "
           "(ws-live-ba-noindex-parallel, F-C0350)."),
}
INS_UNREC = ("lemma", "inspected", [], [cite(NE, "store_edge"), cite(NE, "create_edge"), A("AssertTemporalRow"),
                                        cite("iris_src/src/Graph/KG/LedgerApply.cls", "AllocStmt")],
             "The writer inserts rdf_edges rows that no statement names and writes no ^IVG.Ledger node (statements "
             "are allocated only by LedgerApply.AllocStmt): the set of live statements and the rows of recorded edges "
             "are unchanged (as the census INV-stmt lemmas, writesets/DISCHARGES.json).")
CLASSES["INV-stmt"] = {
    "SQLTEXT": SQLTEXT, "DDL": DDL, "REB": NOOP_REBUILD, "UPD": UPD_Q, "INS": INS_UNREC,
    "RETRACT": ("finding", "inspected", ["F-C0450"], ["run:ws-live-stmt-collision", "run:ws-live-stmt-purge",
                                                      A("RetractTemporalRow"), A("RetractTemporalRows"),
                                                      cite(KG + "TemporalPolicy.cls", "DropRows"), A("IsTemporalMarked")],
                "The writer deletes rows that Adjacency.IsTemporalMarked accepts, which a ledger relationship with "
                "qualifiers temporal=1 satisfies; its statement stays live without its row (F-C0450)."),
    "ERASEALL": ("finding", "inspected", ["F-1201"], [cite(KG + "Eraser.cls", "EraseAll")],
                 "Eraser.EraseAll deletes every rdf_edges row and then kills every ^IVG.Ledger(\"stmt\")/(\"tuple\") in "
                 "its own transaction, taking no ledger head lock: a ledger commit landing between the row delete and "
                 "the statement kill keeps its row and loses its statement (F-1201's shape, live for EraseGraph; "
                 "intent-undecided, HD-1201). Not run for EraseAll."),
    "ERASEROW": ("lemma", "inspected", [], [cite(KG + "Eraser.cls", "EraseEdgeRow"), cite(KG + "Eraser.cls", "EraseEdges")],
                 "Eraser.EraseEdgeRow kills the edge's statement and tuple entry with its row in one step (the route "
                 "F-0303's remedy names): no live statement outlives its row and no recorded edge loses its statement."),
    "SQLDEL": ("open", "open", [], ["run:ws-deploy-auditb", cite("iris_vector_graph/stores/iris_sql_store.py", "_delete_nodes_sql")],
               "open: unreached at the pin's deploy, as the census cell WS-OBL-150 (writesets/DISCHARGES.json): the SQL "
               "fallback runs only when the Eraser method probe answers False."),
}
CLASSES["ADR-0009/HD-0302 explicit-survives"] = {
    "SQLTEXT": SQLTEXT, "DDL": DDL, "REB": NOOP_REBUILD,
    "RETRACT": ("finding", "inspected", ["F-0505"], [R_MARK_AB, A("RetractTemporalRow"), A("RetractTemporalRows"),
                                                     cite(KG + "TemporalPolicy.cls", "DropRows"), A("IsTemporalMarked")],
                "The writer retracts rows its marker predicate accepts (IsTemporalMarked: %Get(\"temporal\") = 1, true "
                "for JSON true, the number 1 and the string \"1\"), so an explicitly written edge with temporal=1 is "
                "removed by the temporal side (F-0505, live; check tmp_mark-as-built-F0505)."),
    "NONADOPT": ("finding", "inspected", ["F-0304"], ["run:ws-live-ba-explicit-survives",
                                                      cite(KG + "EdgeScan.cls", "BulkIngestEdgesSQL"), cite(BL, "load_edges")],
                 "The writer's explicit write of a triple that already has a temporal edge's marked row skips the insert "
                 "and leaves the marker, so the triple's last temporal delete removes the explicitly written edge (the "
                 "F-0304 mechanism; ADR-0009:38-42 names create_edge and bulk_create_edges as the adopting writes)."),
    "ADOPT": ("lemma", "inspected", [], [cite(NE, "_adopt_temporal_row"), cite(NE, "create_edge")],
              "The write adopts a marked row (qualifiers replaced, the marker goes), which is what keeps an explicit "
              "edge from the temporal side (ADR-0009:38-42); it removes nothing."),
    "TINS": ("lemma", "inspected", [], [A("AssertTemporalRow"), TI("InsertEdge")],
             "The temporal write asserts a marked row only when the triple has no row (NOT EXISTS, Adjacency.cls:603) "
             "and writes timestamps; it never removes or rewrites an explicit row."),
    "TOUT": ("lemma", "inspected", [], [TI("EraseAll"), TI("EraseGraph"), TI("MigrateRaw"), TI("RemoveTemporalRow")],
             "The writer removes or re-keys temporal stores and retracts no rdf_edges row: it cannot remove an "
             "explicitly written edge."),
    "NOTTEMP": ("lemma", "inspected", [], [cite(KG + "Eraser.cls", "EraseAll"), cite(NE, "delete_edge"),
                                           cite(NE, "set_edge_weight")],
                "Not a temporal delete or purge: an erasure, an explicit delete or a weight update, which ADR-0009's "
                "explicit-survives property does not govern (the tmp_mark model treats DirectDelete as out of scope)."),
    "SQLDEL": ("lemma", "inspected", [], [cite("iris_vector_graph/stores/iris_sql_store.py", "_delete_nodes_sql")],
               "Not a temporal delete or purge (an explicit node delete's SQL fallback)."),
}
CLASSES["ADR-0009/TMP-B9.13 marked-needs-time"] = {
    "SQLTEXT": SQLTEXT, "DDL": DDL, "REB": NOOP_REBUILD,
    "TINS": ("lemma", "inspected", [], [TI("InsertEdge"), A("AssertTemporalRow"), TI("RemoveTemporalRow")],
             "The marked row is asserted in the same call that sets the triple's timestamp (WriteStores sets tout, "
             "then AssertTemporalRow, TemporalIndex.cls:97-111), or for a timestamp that exists (the backfills)."),
    "RETRACT": ("lemma", "inspected", [], [A("RetractTemporalRow"), A("RetractTemporalRows"),
                                           cite(KG + "TemporalPolicy.cls", "DropRows")],
                "The writer only deletes marked rows; it creates none."),
    "TOUTCTX": ("lemma", "inspected", [], [TI("EraseGraph"), TI("EraseNodes"), TI("RemoveTemporalRow"), TI("MigrateRaw"),
                                           f"{KG}Eraser.cls:237", f"{KG}Eraser.cls:605"],
                "The writer removes or re-keys timestamps only where its caller handles the rows: Eraser.EraseGraph / "
                "EraseNodes delete the rows in the same transaction (Eraser.cls:237, 605), DeleteTemporalEdge and "
                "RetireExpired retract the row with the triple's last timestamp, MigrateRaw / MigrateToGraphScoped "
                "move timestamps under the graph key without dropping any."),
    "TERASEALL": ("finding", "inspected", ["F-0507"], [R_MARK_AB, TI("EraseAll"), TI("Purge")],
                  "TemporalIndex.EraseAll (which Purge calls) kills every graph's temporal stores and retracts no row: "
                  "marked rows stay without timestamps (F-0507, live; check tmp_mark-as-built-F0507)."),
    "MARKQUAL": ("finding", "inspected", ["F-C0351"], ["run:ws-live-ba-marker-qualifier", cite(NE, "store_edge"),
                                                       cite(NE, "create_edge"), cite(BL, "load_edges")],
                 "The writer stores caller qualifiers as given, so {\"temporal\": true} makes a marked row whose triple "
                 "has no timestamp (F-C0351)."),
    "NOQUAL": ("lemma", "inspected", [], [cite(KG + "EdgeScan.cls", "BulkIngestEdgesSQL"), cite(NE, "bulk_ingest_edges"),
                                          cite(NE, "bulk_create_edges")],
               "The writer inserts rows without qualifiers (or the inferred marker) and never the temporal marker."),
    "DELUPD": ("lemma", "inspected", [], [cite(KG + "Eraser.cls", "EraseAll"), cite(NE, "delete_edge"),
                                          cite(NE, "set_edge_weight")],
               "The writer deletes rows or merges a weight into existing qualifiers: it creates no marked row and "
               "removes no timestamp."),
}
CLASSES["TMP-B1.7"] = {
    "WS": ("finding", "mc", ["F-0501"], [R_BUCK_AB, TI("WriteStores"), TI("InsertEdge")],
           "The writer reaches TemporalIndex.WriteStores, which on an update-mode write at an occupied coordinate "
           "increments the bucket counter and the aggregate's count and sum again (TemporalIndex.cls:100, 117-118): "
           "family tmp_bucket's Insert (F-0501, live; check tmp_bucket-as-built-F0501)."),
    "RM": ("lemma", "inspected", [], [TI("RemoveTemporalRow")],
           "RemoveTemporalRow kills the edge, decrements the bucket counter and rebuilds the bucket aggregate from "
           "tout (TemporalIndex.cls:348-360): after it the counter and aggregate describe the bucket's edges "
           "(tmp_bucket's Delete; the as-built counterexample needs an update)."),
    "REB": ("lemma", "inspected", [], [TI("RebuildBucket")],
            "The writer recomputes a bucket's counter and aggregate from tout (RebuildBucket, RebuildBucketAggregate) or "
            "updates the HyperLogLog registers, which are not part of the count/sum this invariant states."),
    "ERASE": ("lemma", "inspected", [], [TI("EraseAll"), TI("EraseGraph"), TI("EraseNodes")],
              "The writer removes tout, the bucket counters and the aggregates together (EraseAll/EraseGraph), or edge "
              "by edge through RemoveTemporalRow (EraseNodes)."),
    "MIG": ("lemma", "inspected", [], [TI("MigrateDerived"), TI("MigrateRaw")],
            "A layout migration: entries are re-keyed under the graph key; a key that would collide is rebuilt from "
            "tout (MigrateDerived -> RebuildBucket)."),
    "PURGE": ("open", "open", [], [TI("PurgeBefore"), TI("PurgeRawBefore"), TI("PurgeBucketRange"),
                                   "iris_vector_graph/_engine/temporal.py:645-650", "iris_vector_graph/_engine/temporal.py:658-661"],
              "open: intent. The purge leaves aggregates and raw edges disagreeing by design: PurgeRawBefore keeps the "
              "aggregates, PurgeBucketRange keeps the raw edges (temporal.py:645-650: 'pair this with purge_raw_before "
              "... or the aggregates go on describing edges that are gone'), PurgeBefore keeps the boundary bucket's "
              "aggregate. The model's invariant (exact agreement) is stronger than TMP-B1.7's statement (an update-mode "
              "write); which contract governs purges is not settled."),
}
CLASSES["VEC-I7.18"] = {
    "SQLTEXT": SQLTEXT, "DDL": DDL,
    "PB": ("finding", "mc", ["F-0604"], [R_Q_AB, cite(KG + "EmbedQueue.cls", "ProcessBatch")],
           "The writer is the IRIS queue worker (EmbedQueueTask.OnTask -> EmbedQueue.ProcessBatch), which sets DONE "
           "when no exception was thrown, also when no vector was made (EmbedQueue.cls:326-327; F-0604, live; check "
           "vec_queue-as-built-F0604)."),
    "ENQ": ("lemma", "inspected", [], [cite(KG + "EmbedQueue.cls", "Enqueue"), cite(KG + "EmbedQueue.cls", "BulkEnqueue")],
            "The writer sets entries PENDING (Enqueue overwrites a PENDING entry, EmbedQueue.cls:35-60); it never sets "
            "DONE. (A re-enqueue while a worker holds the old text is the separate re-enqueue property, F-C0601.)"),
    "CLR": ("lemma", "inspected", [], [cite(KG + "EmbedQueue.cls", "ClearDone")],
            "ClearDone kills DONE entries; it marks none."),
    "EMB": ("lemma", "inspected", [], [cite(KG + "Eraser.cls", "EraseAll")],
            "The writer writes or deletes vector rows and sets no queue entry DONE; deleting a vector later cannot make "
            "'its vector was made' false for an entry already DONE."),
}
CLASSES["VEC-B11.4/HD-0601"] = {
    "SQLTEXT": SQLTEXT, "DDL": DDL,
    "NDEL": ("finding", "inspected", ["F-0606"], ["run:ws-live-ba-vec-node-delete", cite(KG + "Eraser.cls", "DeleteBareSet"),
                                                  cite(KG + "Eraser.cls", "EraseAll"), f"{KG}Eraser.cls:1-35"],
             "The writer deletes node (and vector) rows and names no ^IVF, ^VecIdx or ^PLAID (Eraser.cls:1-35; F-0606): "
             "a graph-owned index keeps answering the deleted ids."),
    "NINS": ("lemma", "inspected", [], [cite(NE, "store_node"), cite(KG + "EdgeScan.cls", "RegisterDefaultNode"),
                                        A("AssertTemporalRow")],
             "The writer adds (or, add_graph_id_to_nodes, re-graphs) node rows: it removes no vector and lists nothing in "
             "a vector index."),
    "IDXW": ("lemma", "inspected", [], [cite(KG + "IVFIndex.cls", "Build"), cite(KG + "VecIndex.cls", "Insert"),
                                        cite(KG + "PLAIDSearch.cls", "Insert")],
             "An index writer lists the ids and vectors its caller passes, or reads from the graph's vector rows at build "
             "time; it erases nothing. The index comes to list ids with no live vector only when node or vector rows go "
             "and the index keeps them (the node deleters' pairs, F-0606)."),
    "IDXD": ("lemma", "inspected", [], [cite(KG + "IVFIndex.cls", "Delete"), cite(KG + "VecIndex.cls", "Drop"),
                                        cite(KG + "PLAIDSearch.cls", "Drop")],
             "The writer removes index entries (Delete/Drop): it can only shrink what the index lists."),
}
CLASSES["VEC-B11.14"] = {
    "ADD": ("finding", "mc", ["F-0608"], [R_IVF_AB, cite(KG + "IVFIndex.cls", "AddBatch")],
            "AddBatch sets ^IVF(name, \"list\", cell, id) without removing the id from another cell (IVFIndex.cls:254): "
            "family vec_ivf's Insert (F-0608, live; check vec_ivf-as-built-F0608-one-cell)."),
    "FIN": ("finding", "inspected", ["F-0608"], [cite(KG + "IVFIndex.cls", "FinalizeIndex")],
            "FinalizeIndex sets indexed to the number of listings (IVFIndex.cls:274), which counts an id listed in two "
            "cells twice: it writes the count F-0608 describes rather than the number of distinct ids."),
    "DEL": ("lemma", "inspected", [], [cite(KG + "IVFIndex.cls", "Delete"), cite(KG + "IVFIndex.cls", "Drop")],
            "The writer removes listings (Delete, Drop): it adds no second listing of an id and lowers the count with the "
            "listing it removes."),
}
CLASSES["VEC-X3.9/SYS-I3"] = {
    "ERASE": ("lemma", "inspected", [], [cite(KG + "Eraser.cls", "EraseAll")],
              "EraseAll deletes registry rows and routes; it refuses no batch and creates no route."),
}

FUNC = {
    "ADJ-I5.9": {"Adjacency.Put": "W", "Adjacency.Remove": "W", "Adjacency.PutKeyed": "W", "Adjacency.RemoveKeyed": "W",
                 "Adjacency.PutShadow": "W", "Adjacency.RowUpdate": "W", "Adjacency.RemoveSource": "E",
                 "Adjacency.RemoveAll": "E", "Adj.Degree": "R", "Adj.WarmFill": "R", "Adjacency.FillEdge": "F",
                 "Adjacency.FillTriple": "F", "Adjacency.Reweight": "V", "Adjacency.SetLeafFromLowest": "V"},
    "ADJ-I11.2": {"Adjacency.Put": "W", "Adjacency.Remove": "W", "Adjacency.PutKeyed": "W", "Adjacency.RemoveKeyed": "W",
                  "Adjacency.PutShadow": "W", "Adjacency.RowUpdate": "W", "Adjacency.Reweight": "W",
                  "Adjacency.RemoveSource": "W", "Adjacency.RemoveAll": "W", "TraversalBuild.Build2HopStats": "B",
                  "TraversalBuild.Build2HopExactStats": "B", "TraversalBuild.BuildKG": "K", "Adjacency.PutLabel": "L",
                  "Adjacency.RemoveLabel": "L", "Adjacency.RemoveAllLabels": "L", "Eraser.InvalidateDerived": "I",
                  "Eraser.EraseAll": "I", "Eraser.EraseEdges": "I", "ArnoAccel.BumpVersion": "I"},
}
_EDGE_FUNCS = {
    "GraphSchema.get_base_schema_sql": "SQLTEXT", "GraphSchema.get_indexes_sql": "SQLTEXT",
    "GraphSchema.get_bulk_insert_sql": "SQLTEXT", "GraphSchema.get_graph_scope_migration_sql": "SQLTEXT",
    "GraphSchema.ensure_indexes": "DDL", "GraphSchema.add_graph_id_column": "DDL", "GraphSchema.add_graph_id_index": "DDL",
    "GraphSchema.add_graph_oid_index": "DDL", "GraphSchema.ensure_ekey": "DDL", "GraphSchema.update_spo_unique_constraint": "DDL",
    "GraphSchema.ensure_adjacency_index": "DDL", "journal:breadth-a-journal-footprints:J12": "REB",
}
FUNC["GID-I4.10"] = {**_EDGE_FUNCS, "Adjacency.RetractTemporalRow": "DEL", "Adjacency.RetractTemporalRows": "DEL",
                     "TemporalPolicy.DropRows": "DEL", "Eraser.EraseAll": "DEL", "Eraser.EraseEdgeRow": "DEL",
                     "IRISGraphStore._delete_nodes_sql": "DEL", "NodesEdgesMixin.delete_edge": "DEL",
                     "NodesEdgesMixin.set_edge_weight": "UPD", "NodesEdgesMixin._adopt_temporal_row": "UPD",
                     "Adjacency.AssertTemporalRow": "GUARD", "EdgeScan.BulkIngestEdgesSQL": "GUARD",
                     "NodesEdgesMixin.bulk_ingest_edges": "GUARD", "NodesEdgesMixin.create_edge": "CE",
                     "BulkLoader.load_edges": "BL"}
FUNC["INV-stmt"] = {**_EDGE_FUNCS, "Adjacency.RetractTemporalRow": "RETRACT", "Adjacency.RetractTemporalRows": "RETRACT",
                    "TemporalPolicy.DropRows": "RETRACT", "Eraser.EraseAll": "ERASEALL", "Eraser.EraseEdgeRow": "ERASEROW",
                    "IRISGraphStore._delete_nodes_sql": "SQLDEL", "NodesEdgesMixin.set_edge_weight": "UPD",
                    "NodesEdgesMixin._adopt_temporal_row": "UPD", "Adjacency.AssertTemporalRow": "INS",
                    "EdgeScan.BulkIngestEdgesSQL": "INS", "NodesEdgesMixin.bulk_ingest_edges": "INS",
                    "NodesEdgesMixin.create_edge": "INS", "NodesEdgesMixin.bulk_create_edges": "INS",
                    "NodesEdgesMixin.store_edge": "INS", "TemporalMixin.create_edge_temporal": "INS",
                    "TemporalMixin.bulk_create_edges_temporal": "INS", "BulkLoader.load_edges": "INS"}
FUNC["ADR-0009/HD-0302 explicit-survives"] = {
    **_EDGE_FUNCS, "Adjacency.RetractTemporalRow": "RETRACT", "Adjacency.RetractTemporalRows": "RETRACT",
    "TemporalPolicy.DropRows": "RETRACT", "EdgeScan.BulkIngestEdgesSQL": "NONADOPT",
    "NodesEdgesMixin.bulk_ingest_edges": "NONADOPT", "BulkLoader.load_edges": "NONADOPT",
    "NodesEdgesMixin._adopt_temporal_row": "ADOPT", "NodesEdgesMixin.create_edge": "ADOPT",
    "Adjacency.AssertTemporalRow": "TINS", "TemporalIndex.WriteStores": "TINS", "TemporalIndex.EraseAll": "TOUT",
    "TemporalIndex.EraseGraph": "TOUT", "TemporalIndex.MigrateRaw": "TOUT", "TemporalIndex.RemoveTemporalRow": "TOUT",
    "Eraser.EraseAll": "NOTTEMP", "Eraser.EraseEdgeRow": "NOTTEMP", "NodesEdgesMixin.delete_edge": "NOTTEMP",
    "NodesEdgesMixin.set_edge_weight": "NOTTEMP", "IRISGraphStore._delete_nodes_sql": "SQLDEL"}
FUNC["ADR-0009/TMP-B9.13 marked-needs-time"] = {
    **_EDGE_FUNCS, "Adjacency.AssertTemporalRow": "TINS", "TemporalIndex.WriteStores": "TINS",
    "Adjacency.RetractTemporalRow": "RETRACT", "Adjacency.RetractTemporalRows": "RETRACT", "TemporalPolicy.DropRows": "RETRACT",
    "TemporalIndex.EraseGraph": "TOUTCTX", "TemporalIndex.RemoveTemporalRow": "TOUTCTX", "TemporalIndex.MigrateRaw": "TOUTCTX",
    "TemporalIndex.EraseAll": "TERASEALL", "NodesEdgesMixin.store_edge": "MARKQUAL", "NodesEdgesMixin.create_edge": "MARKQUAL",
    "NodesEdgesMixin._adopt_temporal_row": "MARKQUAL", "BulkLoader.load_edges": "MARKQUAL",
    "EdgeScan.BulkIngestEdgesSQL": "NOQUAL", "NodesEdgesMixin.bulk_ingest_edges": "NOQUAL",
    "NodesEdgesMixin.bulk_create_edges": "NOQUAL", "TemporalMixin.bulk_create_edges_temporal": "NOQUAL",
    "TemporalMixin.create_edge_temporal": "NOQUAL", "Eraser.EraseAll": "DELUPD", "Eraser.EraseEdgeRow": "DELUPD",
    "IRISGraphStore._delete_nodes_sql": "DELUPD", "NodesEdgesMixin.delete_edge": "DELUPD",
    "NodesEdgesMixin.set_edge_weight": "DELUPD"}
FUNC["TMP-B1.7"] = {"TemporalIndex.WriteStores": "WS", "TemporalIndex.RemoveTemporalRow": "RM",
                    "TemporalIndex.RebuildBucket": "REB", "TemporalIndex.RebuildBucketAggregate": "REB",
                    "TemporalIndex.UpdateHLL": "REB", "TemporalIndex.EraseAll": "ERASE", "TemporalIndex.EraseGraph": "ERASE",
                    "TemporalIndex.MigrateDerived": "MIG", "TemporalIndex.MigrateRaw": "MIG",
                    "TemporalIndex.PurgeBefore": "PURGE", "TemporalIndex.PurgeRawBefore": "PURGE",
                    "TemporalIndex.PurgeBucketRange": "PURGE"}
FUNC["VEC-I7.18"] = {"EmbedQueue.ProcessBatch": "PB", "EmbedQueue.Enqueue": "ENQ", "EmbedQueue.BulkEnqueueText": "ENQ",
                     "EmbedQueue.ClearDone": "CLR", "Eraser.EraseAll": "EMB", "GraphSchema.get_base_schema_sql": "SQLTEXT",
                     "GraphSchema.get_bulk_insert_sql": "SQLTEXT", "GraphSchema.get_graph_scope_migration_sql": "SQLTEXT"}
FUNC["VEC-B11.4/HD-0601"] = {
    "Eraser.DeleteBareSet": "NDEL", "Eraser.EraseAll": "NDEL", "IRISGraphStore._delete_nodes_sql": "NDEL",
    "Adjacency.AssertTemporalRow": "NINS", "BulkLoader._register_endpoints": "NINS", "BulkLoader.load_nodes": "NINS",
    "EdgeScan.RegisterDefaultNode": "NINS", "GraphSchema.add_graph_id_to_nodes": "NINS", "NodesEdgesMixin.store_node": "NINS",
    "_mirror_node": "NINS", "GraphSchema.get_base_schema_sql": "SQLTEXT", "GraphSchema.get_bulk_insert_sql": "SQLTEXT",
    "GraphSchema.get_graph_scope_migration_sql": "SQLTEXT",
    **{f"IVFIndex.{m}": "IDXW" for m in ("AddBatch", "Build", "FinalizeIndex")},
    **{f"IVFIndex.{m}": "IDXD" for m in ("Delete", "Drop")},
    **{f"PLAIDSearch.{m}": "IDXW" for m in ("Build", "BuildInvertedIndex", "Insert", "StoreCentroids", "StoreDocTokens",
                                           "StoreDocTokensBatch")},
    "PLAIDSearch.Drop": "IDXD",
    **{f"VecIndex.{m}": "IDXW" for m in ("Build", "BuildTree", "Create", "GetDim", "Insert", "InsertIntoTree",
                                        "SetInverseCov", "InsertJSON", "InsertBatchJSON")},
    "VecIndex.Drop": "IDXD"}
FUNC["VEC-B11.14"] = {"IVFIndex.AddBatch": "ADD", "IVFIndex.FinalizeIndex": "FIN", "IVFIndex.Delete": "DEL",
                      "IVFIndex.Drop": "DEL"}
FUNC["VEC-X3.9/SYS-I3"] = {"Eraser.EraseAll": "ERASE"}

# ------------------------------------------------------------------------------------- writer-level overrides
# (invariant, writer) -> (class name in CLASSES[invariant], extra evidence, note, grade override)

LIVE = {}   # (invariant, writer) -> list of runs that exercised it (BREADTH-A-RUN-PAIRS.json)


def live(inv, writer, run, outcome, note=""):
    LIVE.setdefault(run, []).append({"invariant": inv, "writer": writer, "outcome": outcome, **({"note": note} if note else {})})


OVR = {}


def ovr(inv, writers, cls, grade=None, runs=(), note=""):
    for w in writers:
        OVR[(inv, w)] = (cls, grade, list(runs), note)


REBUILDERS = ["py:iris_vector_graph.schema.GraphSchema.bootstrap_kg_global", "py:IRISGraphEngine.bulk_load_session",
              "cls:Graph.KG.TraversalBuild.BuildKG", "py:IRISGraphEngine.rebuild_kg", "py:IRISGraphEngine.verify_sync",
              "rest:POST /admin/indexes/rebuild"]
for inv in ("GID-I4.10", "INV-stmt", "ADR-0009/HD-0302 explicit-survives", "ADR-0009/TMP-B9.13 marked-needs-time"):
    ovr(inv, REBUILDERS, "REB")
ovr("GID-I4.10", ["py:IRISGraphEngine.bulk_load_session"], "OPEN_SESSION")
CLASSES["GID-I4.10"]["OPEN_SESSION"] = ("open", "open", [], [cite(NE, "bulk_load_session")],
                                         "open: not decided. bulk_load_session disables index maintenance for the whole "
                                         "session and rebuilds at the end (nodes_edges.py:382-386); whether the unique key "
                                         "and the writers' existence guards still see rows written inside the session "
                                         "(the F-C0350 failure mode) was not probed.")
MIGR = ["py:iris_vector_graph.migrations.upgrade.upgrade_to_4_0_0",
        "py:iris_vector_graph.migrations.kg_node_stores.rekey_kg_node_stores"]
CLASSES["ADJ-I5.9"]["MIGR"] = ("finding", "inspected", ["F-0401"], [cite("iris_vector_graph/migrations/kg_node_stores.py",
                                                                        "rekey_kg_node_stores"), A("RemoveAll")],
                               "The migration kills the flat ^KG prop/label/deg2p/deg2p_exact stores and calls "
                               "TraversalBuild.BuildKG (kg_node_stores.py:65-67, 173-176), whose RemoveAll kills ^KG(\"gen\") "
                               "and degc: class E through the rebuild (F-0401).")
CLASSES["ADJ-I11.2"]["MIGR"] = ("finding", "inspected", ["F-0402"], [cite("iris_vector_graph/migrations/kg_node_stores.py",
                                                                         "rekey_kg_node_stores")],
                                "The migration kills the stamped deg2p stores and rebuilds through BuildKG, whose two-hop "
                                "build is family adj_token's builder B (F-0402).")
for inv in ("ADR-0009/HD-0302 explicit-survives", "ADR-0009/TMP-B9.13 marked-needs-time", "TMP-B1.7"):
    CLASSES[inv]["MIGR"] = ("lemma", "inspected", [], [cite("iris_vector_graph/migrations/kg_node_stores.py",
                                                           "rekey_kg_node_stores")],
                            "The migration kills only the flat ^KG prop/label/deg2p/deg2p_exact stores and rebuilds the "
                            "adjacency from the rows (kg_node_stores.py:1-40, 173-176): it writes no rdf_edges row, no "
                            "qualifier and no temporal store.")
for inv in ("ADJ-I5.9", "ADJ-I11.2", "ADR-0009/HD-0302 explicit-survives", "ADR-0009/TMP-B9.13 marked-needs-time", "TMP-B1.7"):
    ovr(inv, MIGR, "MIGR")


# footprint artifacts and context corrections (each checked against the code)
ART = ("lemma", "inspected", [], [cite(GS, "get_bulk_insert_sql"), cite(GS, "get_procedures_sql_list"),
                                  cite(NE, "create_node"), cite(NE, "bulk_create_nodes")],
       "Footprint artifact: the writer writes no ^KG(\"out\"), (\"gen\"), (\"degc\") or stamped store itself. Its listed "
       "Adjacency/Adj functions come from the rdf_edges row hook (AdjIndex -> Adjacency.RowPut) or a stored procedure's "
       "body that the extractor attached because a SQL-text builder it reaches names rdf_edges, or the procedures call "
       "Adj.Degree only when a reader later runs them (that reader's own pair). create_node and bulk_create_nodes write "
       "node, label and property rows only (their label writes are the ADJ-I11.2 label class).")
for inv in ("ADJ-I5.9", "ADJ-I11.2"):
    CLASSES[inv]["ART"] = ART
ovr("ADJ-I5.9", ["py:IRISGraphEngine.create_node", "py:IRISGraphEngine.bulk_create_nodes",
                 "py:iris_vector_graph.schema.GraphSchema.get_bulk_insert_sql",
                 "py:iris_vector_graph.schema.GraphSchema.get_procedures_sql_list",
                 "py:iris_vector_graph._engine.legacy.grant_read_path",
                 "py:iris_vector_graph._engine.legacy.read_path_routines"], "ART")
ovr("ADJ-I11.2", ["py:iris_vector_graph.schema.GraphSchema.get_bulk_insert_sql",
                  "py:iris_vector_graph.schema.GraphSchema.get_procedures_sql_list",
                  "py:iris_vector_graph._engine.legacy.read_path_routines"], "ART")
ovr("ADJ-I11.2", ["py:IRISGraphEngine.create_node", "py:IRISGraphEngine.bulk_create_nodes"], "L")
REBUILD_W = ["py:iris_vector_graph.schema.GraphSchema.bootstrap_kg_global", "py:IRISGraphEngine.bulk_load_session",
             "cls:Graph.KG.TraversalBuild.BuildKG", "py:IRISGraphEngine.rebuild_kg", "py:IRISGraphEngine.verify_sync",
             "rest:POST /admin/indexes/rebuild", "py:IRISGraphEngine.sync"]
ovr("ADJ-I5.9", REBUILD_W, ["E", "F", "R"], note=" The rebuild's Adjacency.Put calls (the idxedgesadj index build, "
    "TraversalBuild.cls:133) run under BeginRebuild's shared ^IVG.AdjW lock, which refuses every reader's probe, so "
    "the writer-window class W does not apply to them.")
ovr("ADJ-I11.2", REBUILD_W, ["B", "K", "L"], note=" The rebuild's own Puts and RemoveAll run outside any transaction "
    "(a rebuild inside a caller's transaction is F-0409's case), so no rebuild write is rolled back after its token step; "
    "the stamped two-hop build it runs is class B.")
ovr("ADJ-I11.2", ["py:IRISGraphEngine.initialize_schema"], "K", note=" initialize_schema's RemoveAll and fill run inside "
    "BuildKG's rebuild, outside any transaction (setup refuses a caller transaction).")
CLASSES["VEC-B11.4/HD-0601"]["BARE"] = ("lemma", "inspected", [], [cite(KG + "Eraser.cls", "DeleteBareSet"),
                                                                   cite(KG + "Eraser.cls", "EraseBareNodes")],
                                        "The writer deletes only BARE nodes (Eraser.DeleteBareSet through RetireBareNodes): "
                                        "BareClauses require no embedding row in the two legacy tables and every routed one "
                                        "(Eraser.cls:1181-1206), so no live vector is removed and no index entry loses its "
                                        "vector through this writer.")
ovr("VEC-B11.4/HD-0601", ["cls:Graph.KG.TemporalPolicy.DropRows", "cls:Graph.KG.TemporalIndex.PurgeBefore",
                          "cls:Graph.KG.TemporalIndex.PurgeRawBefore", "cls:Graph.KG.TemporalIndex.RetireExpired",
                          "py:IRISGraphEngine.purge_before", "py:IRISGraphEngine.drop_temporal_structural_rows"], "BARE")
ovr("ADR-0009/TMP-B9.13 marked-needs-time", ["py:iris_vector_graph.migrations.temporal_structural_rows.backfill_structural_rows"],
    "TINS", note=" backfill_structural_rows calls create_edge with TEMPORAL_QUALIFIERS for each triple that has temporal "
    "edges (temporal_structural_rows.py:107-110): every marked row it writes has a timestamp.")

ovr("ADR-0009/TMP-B9.13 marked-needs-time", ["py:IRISGraphEngine.erase_all"], "DELUPD",
    note=" erase_all's Eraser.EraseAll deletes every rdf_edges row in the same transaction in which it calls "
    "TemporalIndex.EraseAll (Eraser.cls:776-791), so no marked row is left without its timestamps (a %NOINDEX loader "
    "row it misses, F-C1250, is unmarked).")

# live-decided pairs
for w in ("py:iris_vector_graph.bulk_loader.BulkLoader.load_edges",):
    live("GID-I4.10", w, "ws-live-ba-noindex-parallel", "fail")
ovr("GID-I4.10", ["py:iris_vector_graph.bulk_loader.BulkLoader.load_networkx"], "BL", grade="inspected",
    note=" load_networkx runs load_edges with use_noindex (default True) before its index rebuild (bulk_loader.py:575-587); not run itself.")
for w, run in (("py:IRISGraphEngine.bulk_ingest_edges", "ws-live-ba-explicit-survives"),
               ("cls:Graph.KG.EdgeScan.BulkIngestEdgesSQL", "ws-live-ba-explicit-survives"),
               ("py:iris_vector_graph.bulk_loader.BulkLoader.load_edges", "ws-live-ba-explicit-survives")):
    live("ADR-0009/HD-0302 explicit-survives", w, run, "fail")
for w in ("py:IRISGraphEngine.store_edge", "py:IRISGraphEngine.create_edge", "py:iris_vector_graph.bulk_loader.BulkLoader.load_edges"):
    live("ADR-0009/TMP-B9.13 marked-needs-time", w, "ws-live-ba-marker-qualifier", "fail")
for w in ("py:IRISGraphEngine.delete_node", "py:IRISGraphEngine.bulk_delete_nodes"):
    live("VEC-B11.4/HD-0601", w, "ws-live-ba-vec-node-delete", "fail")
    ovr("VEC-B11.4/HD-0601", [w], "NDEL")
# the census collision runs exercised these breadth-a writers (the same functions through their entry points)
for w in ("cls:Graph.KG.Adjacency.RetractTemporalRow", "cls:Graph.KG.TemporalIndex.DeleteTemporalEdge",
          "cls:Graph.KG.TemporalPolicy.DropRows", "py:IRISGraphEngine.drop_temporal_structural_rows"):
    live("INV-stmt", w, "ws-live-stmt-collision", "fail")
    live("ADR-0009/HD-0302 explicit-survives", w, "ws-live-stmt-collision", "fail")
for w in ("cls:Graph.KG.Adjacency.RetractTemporalRows", "cls:Graph.KG.TemporalIndex.PurgeBefore",
          "cls:Graph.KG.TemporalIndex.RetireExpired", "py:IRISGraphEngine.purge_before"):
    live("INV-stmt", w, "ws-live-stmt-purge", "fail", "through RetractTemporalRows' fallback RetractTemporalRow")
ovr("INV-stmt", ["cls:Graph.KG.TemporalIndex.DeleteTemporalEdge", "cls:Graph.KG.TemporalIndex.PurgeBefore",
                 "cls:Graph.KG.TemporalIndex.RetireExpired", "py:IRISGraphEngine.purge_before",
                 "cls:Graph.KG.TemporalIndex.PurgeRawBefore", "cls:Graph.KG.TemporalPolicy.BackfillRows"], None)
ovr("ADR-0009/HD-0302 explicit-survives", ["cls:Graph.KG.TemporalIndex.DeleteTemporalEdge",
                                           "py:IRISGraphEngine.drop_temporal_structural_rows"], "RETRACT")
ovr("INV-stmt", ["py:IRISGraphEngine.erase_all"], "ERASEALL")
ovr("INV-stmt", ["py:IRISGraphEngine.bulk_delete_adjacency"], "ERASEROW")

# ------------------------------------------------------------------------------------------- supplementary pairs

EXTRA = {
    "m08|CYP-I5.5/CYP-I5.6/SYS-I2|engine.direct_write": D(
        "guard", "inspected", [R_FK, FK, FK_LABELS, cite(NE, "create_edge"), cite(NE, "store_node")], [],
        "An edge row must have both endpoint node rows in its own graph and a label row its node row in the same graph "
        "(composite foreign keys fk_edges_source / fk_edges_dest / fk_labels_node on (graph_id, id)); the engine's "
        "direct writers register endpoints in the edge's graph first (create_edge, store_edge _ensure_edge_endpoints). "
        "The foreign keys were exercised live by plain SQL (ws-live-fk-guard), not through these writers, so this cell "
        "is graded inspected. Property rows carry "
        "their graph_id and have no foreign key: a property row of graph g is g's data by its own key.",
        module="08", invariant="CYP-I5.5/CYP-I5.6/SYS-I2", writer="engine.direct_write"),
    "m08|CYP-I5.5/CYP-I5.6/SYS-I2|bulk_loader": D(
        "lemma", "inspected", [cite(BL, "_register_endpoints"), cite(BL, "load_edges"), f"{BL}:456-460"], [],
        "BulkLoader inserts edges with %NOCHECK, so the foreign keys do not check them; the loader registers every "
        "endpoint in its own graph first (_register_endpoints, called before the edge insert, bulk_loader.py:449) and "
        "writes every edge into the same graph (one loader, one graph), so an edge meets only nodes of its graph. "
        "Inspected only; the %NOINDEX side effects are F-C0350, F-C1250, F-C1351.",
        module="08", invariant="CYP-I5.5/CYP-I5.6/SYS-I2", writer="bulk_loader"),
    "m08|CYP-I5.5/CYP-I5.6/SYS-I2|fhir sync": D(
        "guard", "inspected", [cite(KG + "FHIRGraph.cls", "ResyncKey"), cite(KG + "FHIRGraph.cls", "EnsureNode"), FK,
                               "run:ws-live-fhir-blocked"], [],
        "ResyncKey writes every node and edge into the FHIR graph's own GraphId, EnsureNode-ing the target before the "
        "edge INSERT (FHIRGraph.cls:2275-2277), and the foreign keys check the INSERT. Live is blocked (no FHIR "
        "repository, ws-live-fhir-blocked).",
        module="08", invariant="CYP-I5.5/CYP-I5.6/SYS-I2", writer="fhir sync"),
    "m08|CYP-I5.5/CYP-I5.6/SYS-I2|raw SQL": D(
        "guard", "live", [R_FK, FK, FK_LABELS], [],
        "A plain SQL INSERT of an edge or label row is checked by the composite foreign keys (live: refused without "
        "the node, ws-live-fk-guard). A client that writes with %NOCHECK bypasses them, as any SQL client can bypass "
        "a constraint it is allowed to skip; that is outside IVG's writers.",
        module="08", invariant="CYP-I5.5/CYP-I5.6/SYS-I2", writer="raw SQL"),
}
RM = "run:ws-live-ba-restore-merge"
SNAPR = ["iris_vector_graph/_engine/snapshot.py:416-422", "iris_vector_graph/_engine/snapshot.py:1554-1580",
         cite("iris_vector_graph/_engine/snapshot.py", "_import_global_from_ndjson")]
for inv, kind in (("INV-text", "live"), ("INV-retry", "live"), ("INV-marker", "live"), ("INV-shape", "inspected"),
                  ("INV-isolation", "inspected"), ("INV-no-live-tombstone", "inspected"), ("INV-replay", "inspected"),
                  ("INV-stmt", "inspected")):
    if kind == "live":
        EXTRA[f"m18|{inv}|snapshot.restore_merge"] = D(
            "finding", "live", [RM] + SNAPR, ["F-C1850", "F-1801"],
            "A merging restore imports the archive's ^IVG.Ledger through the same path as a replacing one (the allowed "
            "globals include the ledger's storage, snapshot.py:416-422, 1554-1580) and kills none of the live ledger's "
            "nodes. Live (ws-live-ba-restore-merge): a second redaction of a restored tenant kept the revision's text "
            "and live retry key, and a live marker survived while the merge made its target live (F-C1850's effects, "
            "with merge=True).", module="18", invariant=inv, writer="snapshot.restore_merge")
        live(inv, "snapshot.restore_merge", "ws-live-ba-restore-merge", "fail")
    else:
        EXTRA[f"m18|{inv}|snapshot.restore_merge"] = D(
            "finding", "inspected", [RM] + SNAPR, ["F-1801"],
            "A merging restore lays the archive's ^IVG.Ledger nodes over the live ones exactly as a replacing restore "
            "does (same import path, no kill): F-1801's overlay, which breaks this invariant as the replacing restore's "
            "cell records (semantics/WRITESETS.md, snapshot.restore_replace). ws-live-ba-restore-merge shows the overlay "
            "in merge mode (records of a redacted revision back as originals); this invariant's break was not run.",
            module="18", invariant=inv, writer="snapshot.restore_merge")
EXTRA["m18|TMP-B1.7|snapshot.restore_merge"] = D(
    "finding", "inspected", ["run:c18-live-aggregates"] + SNAPR, ["F-1805"],
    "A merging restore sets the archive's ^KG(\"tagg\") nodes over the live ones instead of combining them (F-1805, "
    "live in its own record): the aggregate then describes the archive's edges, not the merged bucket's.",
    module="18", invariant="TMP-B1.7", writer="snapshot.restore_merge")


live("CYP-I5.5/CYP-I5.6/SYS-I2", "raw SQL", "ws-live-fk-guard", "pass",
     "plain SQL INSERTs of an edge and a label without their node were refused by the foreign keys")

# ------------------------------------------------------------------------------------------------------- build

def pair_funcs():
    fp = {}
    for m in ("01", "02", "03", "04", "05", "06"):
        for e in json.loads((PC / "footprints" / f"{m}.json").read_text())["entry_points"]:
            fp[(m, e["id"])] = e
    return fp


def build():
    ba = json.loads(BA.read_text())
    inv_reads = {k: set(v["reads"]) for k, v in ba["invariants"].items()}
    fp = pair_funcs()
    out, unclassified = {}, []
    for p in ba["pairs"]:
        if p["status"] != "open":
            continue
        inv, w, m = p["invariant"], p["writer"], p["module"]
        key = f"{m}|{inv}|{w}"
        e = fp.get((m, w)) or {}
        funcs = set()
        for wr in e.get("writes", []):
            if wr["store"] in inv_reads[inv] or wr["store"] in p["writes"]:
                for at in wr["at"]:
                    mm = re.search(r"\((.*?)\)$", at)
                    funcs.add(mm.group(1) if mm else at)
        o = OVR.get((inv, w))
        classes = []
        if o and o[0]:
            classes = list(o[0]) if isinstance(o[0], (list, tuple)) else [o[0]]
        else:
            for f in sorted(funcs):
                c = FUNC.get(inv, {}).get(f)
                if c:
                    classes.append(c)
        classes = sorted(set(classes))
        if not classes:
            unclassified.append((key, sorted(funcs)))
            continue
        defs = [CLASSES[inv][c] for c in classes]
        order = {"finding": 0, "open": 1, "guard": 2, "lemma": 3}
        main = min(defs, key=lambda d: order[d[0]])
        kind = main[0]
        sel = [d for d in defs if d[0] == kind]
        findings = sorted({f for d in sel for f in d[2]})
        evidence = []
        for d in sel:
            for x in d[3]:
                if x not in evidence:
                    evidence.append(x)
        grades = {d[1] for d in sel}
        grade = "open" if kind == "open" else ("inspected" if "inspected" in grades else sorted(grades)[0])
        runs_here = [r for r, xs in LIVE.items() if any(x["invariant"] == inv and x["writer"] == w for x in xs)]
        note = o[3] if o else ""
        if o and o[1]:
            grade = o[1]
        if runs_here and kind in ("finding", "lemma", "guard"):
            grade = "live"
            evidence = [f"run:{r}" for r in runs_here] + [x for x in evidence if x[4:] not in runs_here]
        elif grade == "live":
            grade = "inspected"
        reason = " ".join(d[4] for d in sel) + note
        reason = f"[{inv} via {', '.join(classes)}; writing functions: {', '.join(sorted(funcs)) or 'none listed'}] " + reason
        if grade == "live":
            reason += " Live for this writer: " + ", ".join(runs_here) + "."
        out[key] = {"module": m, "invariant": inv, "writer": w, "classes": classes, "discharge": kind, "grade": grade,
                    "evidence": evidence, "findings": findings, "reason": reason}
    if unclassified:
        raise SystemExit("unclassified pairs:\n" + "\n".join(f"  {k}: {f}" for k, f in unclassified))
    out.update(EXTRA)
    return {"_doc": ("One discharge per breadth-a module-invariant pair with status 'open' in "
                     "models/breadth-a/writesets.json (key module|invariant|writer), plus the open module-08 pairs "
                     "(m08|...) and snapshot.restore_merge (m18|...). Generated by writesets/tools/build_breadth_a.py; "
                     "checked by writesets/tools/check_discharges.py (B1-B11)."), **out}


def main() -> int:
    data = build()
    text = json.dumps(data, indent=1, sort_keys=True) + "\n"
    pairs = json.dumps({"_doc": "Runs cited by breadth-a discharges -> the (invariant, writer) pairs each exercised "
                                "(breadth-a writer names), with the outcome. Generated by build_breadth_a.py.",
                        "runs": LIVE}, indent=1, sort_keys=True) + "\n"
    if "--check" in sys.argv:
        return 0 if OUT.exists() and OUT.read_text() == text and PAIRS_OUT.exists() and PAIRS_OUT.read_text() == pairs else 1
    OUT.write_text(text)
    PAIRS_OUT.write_text(pairs)
    n = {}
    for k, v in data.items():
        if k == "_doc":
            continue
        n.setdefault(v["module"], {}).setdefault(v["discharge"], 0)
        n[v["module"]][v["discharge"]] += 1
    print(f"wrote {OUT}: {sum(1 for k in data if k != '_doc')} entries; by module: {json.dumps(n, sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
