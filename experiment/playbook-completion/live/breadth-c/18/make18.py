#!/usr/bin/env python3
"""Compose module 18's footprints, findings audit and gate status from the live results and model results.

    python experiment/playbook-completion/live/breadth-c/18/make18.py

Reads $RUN_DIR/breadth-c/18/<check>.json (snp_live.py) and models/breadth-c/RESULTS.json; writes
footprints/18.json, findings/audit/18.json, modules/18.json. Statements of fact below cite path:lines at the pin and
registered run ids; a value read from a live result is inserted, not typed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMP = HERE.parents[2]
RUN = Path(os.environ["RUN_DIR"]) / "breadth-c" / "18"
PIN = "3eaa79cf77d3e0a879b2cced634cf2729d81499e"


def res(name):
    p = RUN / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def j(r, *path, default=None):
    for k in path:
        if not isinstance(r, dict) or k not in r:
            return default
        r = r[k]
    return r


MODELS = {c["id"]: c for c in json.loads((COMP / "models/breadth-c/RESULTS.json").read_text())["checks"]}
SAVE, DIRTY, FILES, HTTP = res("save_footprint"), res("dirty_export"), res("file_helpers"), res("http_endpoint")
RFP, MERGE, EVEC, VAL, AGG = res("restore_footprint"), res("merge_guard"), res("edge_vectors"), res("value_types"), res("aggregates")
SWAL, REF, LED = res("swallowed_global_lines"), res("refusals"), res("ledger_overlay")
EROUTE = res("edge_routes")


def fp_entry(entry, role, source, reads, writes, txn, locks, claims, journal=None):
    return {"entry": entry, "role": role, "source": source, "reads": reads, "writes": writes, "transaction": txn,
            "locks": locks, "claims_atomic": claims, "journal": journal}


def jsum(run_id, jr, declared_writes, note=""):
    if not jr:
        return None
    written = set(jr.get("stores_written", []))
    undeclared = sorted(written - set(declared_writes))
    return {"run": run_id, "stores_written": sorted(written), "stores_written_in_txn": jr.get("stores_written_in_txn"),
            "stores_written_outside_any_txn": jr.get("stores_written_outside_any_txn"),
            "outermost_transactions": jr.get("outermost_transactions"), "records": jr.get("records"),
            "undeclared_writes": undeclared, "match": not undeclared, "mismatch": note}


KG_SUBS = ["out", "in", "deg2p", "deg2p_exact", "tout", "tin", "bucket", "tagg", "edgeprop", "tlast", "label", "prop",
           "labelset"]
SAVE_READS = (["sql:Graph_KG." + t for t in ("nodes", "rdf_edges", "rdf_labels", "rdf_props", "rdf_reifications",
                                              "docs", "embedding_registry", "fhir_unresolved", "fhir_definitions",
                                              "fhir_canonical_refs", "fhir_graphs", "code_crosswalk", "rdf_namespaces",
                                              "table_mappings", "relationship_mappings", "fhir_bridges",
                                              "kg_NodeEmbeddings", "kg_EdgeEmbeddings", "kg_emb_<route>")]
              + [f'global:^KG("{s}")' for s in KG_SUBS]
              + ["global:^BM25Idx", "global:^IVF", "global:^PLAID", "global:^VecIdx", "global:^NKG", "global:^IVG.Ledger",
                 "global:^Graph.KG.LedgerRevisionD", "global:^Graph.KG.LedgerRevisionI", "global:^Graph.KG.LedgerStatsD",
                 "global:^IVG.GraphMode", "global:^IVG.TemporalStructural"])
RESTORE_WRITES = (["sql:Graph_KG." + t for t in ("nodes", "rdf_edges", "rdf_labels", "rdf_props", "rdf_reifications", "docs",
                                                 "embedding_registry", "fhir_unresolved", "fhir_definitions",
                                                 "fhir_canonical_refs", "fhir_graphs", "code_crosswalk", "rdf_namespaces",
                                                 "table_mappings", "relationship_mappings", "fhir_bridges",
                                                 "kg_NodeEmbeddings", "kg_NodeEmbeddings_optimized", "kg_EdgeEmbeddings",
                                                 "kg_emb_<route> (DDL + rows)", "embedding_route_state")]
                  + ["global:^KG", "global:^NKG", "global:^BM25Idx", "global:^IVF", "global:^PLAID", "global:^VecIdx",
                     "global:^IVG.Ledger", "global:^Graph.KG.LedgerRevisionD", "global:^Graph.KG.LedgerRevisionI",
                     "global:^Graph.KG.LedgerStatsD", "global:^IVG.GraphMode", "global:^IVG.TemporalStructural",
                     "global:^ArnoKG", "global:^IVG.AlgoCache", "global:^ArnoAccel",
                     "sql:Graph_KG.ledger_revisions", "sql:Graph_KG.ledger_stats"])


def footprints():
    rj = j(RFP, "replace") or {}
    mj = j(RFP, "merge_same_archive") or {}
    entries = [
        fp_entry("IRISGraphEngine.save_snapshot", "reader", "iris_vector_graph/_engine/snapshot.py:797-1048",
                 SAVE_READS, ["file: the ZIP archive at path (outside IRIS)"], "none: one SELECT * per table and a "
                 "nextSubscript/get walk per global, in sequence, no transaction, no lock (uncommitted reads)", [],
                 {"claims": False, "source": "snapshot.py:803 'reads only'; no consistency claim (USER_GUIDE.md:1151-1153)"},
                 {"run": "c18-live-save-footprint", "stores_written": j(SAVE, "journal", "stores_written"),
                  "records": j(SAVE, "writes_by_save_pid"), "match": j(SAVE, "writes_by_save_pid") == 0,
                  "mismatch": "" if j(SAVE, "writes_by_save_pid") == 0 else "save wrote to the namespace"}),
        fp_entry("IRISGraphEngine.snapshot_info", "reader", "iris_vector_graph/_engine/snapshot.py:1050-1074",
                 ["file: metadata.json of the archive"], [], "none (no connection)", [],
                 {"claims": False, "source": "snapshot.py:1052"}, None),
        fp_entry("IRISGraphEngine.restore_snapshot(merge=False)", "writer",
                 "iris_vector_graph/_engine/snapshot.py:1076-1610; iris_src/src/Graph/KG/Eraser.cls:709-850",
                 ["file: archive", "sql:Graph_KG.embedding_registry", "global:^NKG(\"$meta\",\"version\")",
                  "global:^KG(\"__version\")", "$TLEVEL (refuse_in_caller_transaction)", "ledger meta (strict guard)"],
                 RESTORE_WRITES,
                 "Eraser.EraseAll in one TSTART..TCOMMIT (routed tables dropped after its commit); then each table's "
                 "INSERTs with conn.commit() after the table (autocommit connection: one commit per statement); "
                 "globals set node by node over the Native API, no transaction; version counters last",
                 ["none (no LOCK; the ledger head lock is not taken)"],
                 {"claims": False, "source": "SNP-T3.1, snapshot.py:1086-1094 docstring: partial on failure"},
                 jsum("c18-live-restore-footprint", rj, RESTORE_WRITES + ["sql:Graph_KG.embedding_quarantine"])),
        fp_entry("IRISGraphEngine.restore_snapshot(merge=True)", "writer", "iris_vector_graph/_engine/snapshot.py:1270-1298, 1341-1350, 1510-1552, 1654-1692",
                 ["file: archive", "each target table (NOT EXISTS guard)"], [w for w in RESTORE_WRITES if "Ledger" not in w] + ["global:^IVG.Ledger (if archived)"],
                 "no erase; per statement (autocommit); globals set over the live nodes", ["none"],
                 {"claims": False, "source": "snapshot.py:1081-1085"},
                 jsum("c18-live-restore-footprint", mj, RESTORE_WRITES)),
        fp_entry("IRISGraphEngine.restore_snapshot(merge=False) over an enabled ledger", "writer",
                 "iris_vector_graph/_engine/snapshot.py:1554-1588; Eraser.cls:806-812",
                 ["file: archive"], RESTORE_WRITES, "as above; the ledger globals and the ledger classes' storage are set node by node "
                 "outside any transaction and nothing of the live ledger is killed but stmt/tuple", ["none: the ledger head lock is not taken"],
                 {"claims": False, "source": "SNP-B3.4"},
                 jsum("c18-live-ledger-overlay", j(LED, "restore") or {}, RESTORE_WRITES,
                      "ledger storage written outside any transaction and without the head lock (Ledger.cls owns it)")),
        fp_entry("IRISGraphEngine.restore_snapshot refused (strict ledger / caller transaction)", "refusal",
                 "iris_vector_graph/_engine/snapshot.py:1095-1102; iris_vector_graph/ledger/guard.py:70-80",
                 ["ledger meta", "$TLEVEL"], ["sql:Graph_KG.ledger_stats (rej_strict_block counter, strict refusal only)"],
                 "the counter bump is its own transaction", [], {"claims": False, "source": "SNP-X2.1, SNP-X2.2"},
                 {"run": "c18-live-refusals", "stores_written": j(REF, "strict", "stores_written"),
                  "caller_txn_records": j(REF, "caller_txn", "records"),
                  "match": set(j(REF, "strict", "stores_written") or []) <= {"sql:Graph_KG.ledger_stats"} and not j(REF, "caller_txn", "records"),
                  "mismatch": "", "note": "the strict refusal's only write is the rejection counter (by design); the caller-transaction refusal writes nothing"}),
        fp_entry("POST /admin/snapshot", "reader", "iris_vector_graph/cypher_api.py:668-678",
                 SAVE_READS, ["file: $IVG_SNAPSHOT_DIR/ivg_snapshot_<epoch second>.snapshot (overwritten when it exists)"],
                 "as save_snapshot, under the server's _engine_lock (Python RLock, one process)", ["_engine_lock (in-process)"],
                 {"claims": False, "source": "cypher_api.py:668-678"},
                 {"run": "c18-live-http-endpoint", "match": True, "mismatch": "", "note": "file effect observed: same path twice"}),
        fp_entry("Graph.KG.Snapshot.NodeValueJSON", "reader", "iris_src/src/Graph/KG/Snapshot.cls:75-82",
                 ["global:^IVF", "global:^PLAID", "global:^VecIdx"], [], "none", [], {"claims": False, "source": ""}, None),
        fp_entry("Graph.KG.Snapshot.SetNodeJSON", "writer", "iris_src/src/Graph/KG/Snapshot.cls:84-89, 93-106",
                 [], ["global:^IVF", "global:^PLAID", "global:^VecIdx"], "none (one SET per call)", [],
                 {"claims": False, "source": "NodeRef refuses other globals (:95-99)"}, None),
        fp_entry("Graph.KG.Snapshot.ImportGlobals", "writer", "iris_src/src/Graph/KG/Snapshot.cls:24-35",
                 ["server directory *.gof"], ["any global or item the files hold ($System.OBJ.Load)"], "none", [],
                 {"claims": False, "source": ""}, {"run": "c18-live-file-helpers", "note": "called on a missing directory only: {imported:0}", "match": True, "mismatch": ""}),
        fp_entry("Graph.KG.Snapshot.ExportGlobals", "writer (server files)", "iris_src/src/Graph/KG/Snapshot.cls:4-22",
                 ["any global named in the JSON list"], ["server directory (CreateDirectoryChain) and <name>.gof files"], "none", [],
                 {"claims": False, "source": ""}, None),
        fp_entry("Graph.KG.Snapshot.ReadFileChunk / GetFileSize / FileExists", "reader (server files)",
                 "iris_src/src/Graph/KG/Snapshot.cls:37-47, 59-62, 70-73", ["any server file the IRIS process can read"], [],
                 "none", [], {"claims": False, "source": ""},
                 {"run": "c18-live-file-helpers", "note": "read /etc/hostname over the Native API", "match": True, "mismatch": ""}),
        fp_entry("Graph.KG.Snapshot.WriteFileChunk / DeleteDir", "writer (server files)",
                 "iris_src/src/Graph/KG/Snapshot.cls:49-57, 64-68", [], ["any server file / directory tree the IRIS process can write or remove"],
                 "none", [], {"claims": False, "source": ""}, None),
    ]
    validated = [e for e in entries if e["journal"] and e["journal"].get("run", "").startswith("c18-live") and "stores_written" in e["journal"]]
    mism = [{"entry": e["entry"], "undeclared": e["journal"].get("undeclared_writes"), "outside_txn": e["journal"].get("stores_written_outside_any_txn")}
            for e in validated if not e["journal"].get("match")]
    return {"module": "18", "pin": PIN, "entries": entries, "validated": len(validated), "mismatches": mism,
            "notes": "Store names: sql:<schema.table> from the namespace's compiled storage (traces/journal.py storage_map), "
                     "global:^Root otherwise. Journal classification per live/breadth-c/jcheck.py."}



def rec(id_, title, intended, observed, disposition, evidence, gates, severity, confidence, remedy, notes=""):
    return {"id": id_, "module": "18", "title": title, "intended": intended, "observed": observed,
            "disposition": disposition, "evidence": evidence, "gates": gates, "severity": severity,
            "confidence": confidence, "remedy": remedy, "notes": notes}


def m(id_):
    c = MODELS[id_]
    return f"{id_} ({c['result']}, {c['states']} states, {'exhaustive within bounds' if c['exhaustive'] else 'truncated'})"


def findings():
    out = []
    a = j(LED, "after") or {}
    p2 = j(LED, "part2_redaction") or {}
    wedged = isinstance(a.get("commit_after_restore"), dict) and not a["commit_after_restore"].get("ok", True)
    leftover = a.get("rec_seq_after_head_present")
    out.append(rec(
        "F-1801", "A replacing restore lays the archive's ledger over the live one",
        "spec 213 FR-043 (the ledger survives a snapshot); SNP-I3.6 (after a restore the ledger holds one history whose "
        "records and head agree); SYS-I5 (the ledger only grows); ADR-0013 (redacted content leaves history); decisions.md "
        "HD-1801 (treat the archive's history as a unit; refuse divergent histories before mutation; keep current redaction "
        "obligations).",
        f"Live (c18-live-ledger-overlay, AUDITC): ledger enabled, commit seq 2 (c18:L1), save, commit seq 3 (c18:L2, retry key "
        f"c18-k2), replacing restore of the older archive: meta after restore {a.get('meta_after_restore')}; record (3,1) "
        f"still present: {leftover}; LedgerRevision seqs {a.get('revision_rows')}; idem binding c18-k2 = "
        f"{a.get('idem_c18_k2')!r}; the next commit -> {a.get('commit_after_restore')}; a retry of c18-k2 -> "
        f"{a.get('retry_of_k2')}; verify -> {a.get('verify')}. Redaction half: a tenant node c18t|x with property secret "
        f"committed, archived, erased (delete_nodes_by_prefix) and redacted; records after redaction "
        f"{p2.get('records_after_redaction')}; after a replacing restore of the pre-redaction archive the same revision's "
        f"records are {p2.get('records_after_restore')} (content back: {p2.get('content_back_in_history')}) while "
        f"redactedRev marks {p2.get('redactedRev_marks_after_restore')} remain. Models: {m('cmc-restore-as-built-history')}, "
        f"{m('cmc-restore-as-built-grows')}, {m('cmc-restore-as-built-commit')} (the ledger can never commit again: the "
        f"leftover LedgerRevision row holds the IdKey of head+1, Ledger.cls:530-556, LedgerRevision.cls:44), "
        f"{m('cmc-restore-as-built-redaction')}; reviewed {m('cmc-restore-reviewed')}; control {m('cmc-restore-ctl-marks')}.",
        "reproduced-live" if (wedged or p2.get("content_back_in_history")) else "reproduced-model",
        [{"kind": "live", "ref": "c18-live-ledger-overlay"}, {"kind": "mc", "ref": "cmc-restore-as-built-history"},
         {"kind": "mc", "ref": "cmc-restore-as-built-grows"}, {"kind": "mc", "ref": "cmc-restore-as-built-commit"},
         {"kind": "mc", "ref": "cmc-restore-as-built-redaction"}, {"kind": "mc", "ref": "cmc-restore-reviewed"},
         {"kind": "control", "ref": "cmc-restore-ctl-marks"},
         {"kind": "inspected", "ref": "iris_src/src/Graph/KG/Eraser.cls:806-812"},
         {"kind": "inspected", "ref": "iris_vector_graph/_engine/snapshot.py:1554-1588, 1654-1692"}],
        ["3.3a-writesets", "3.4-ownership", "3.3-model-check", "SYS-I5", "SNP-I3.6"], "S1", "high",
        "Per HD-1801: refuse a restore whose archive history does not extend the live one, before erase_all; otherwise "
        "replace the ledger as a unit (kill ^IVG.Ledger and the ledger storage first) and re-apply live redactions "
        "(tombstones, redactedRev, idemRedacted) to the archived records.",
        "The wedge (no commit possible after restoring an older archive) is stronger than the original's 'reuses sequence "
        "numbers': the IdKey on LedgerRevision.Seq refuses the next revision row, and nothing removes the leftover row."
        if wedged else ""))
    fm = j(MERGE, "rows_missing_after_merge") or {}
    lost = {k: v for k, v in fm.items() if v}
    out.append(rec(
        "F-1802", "A merge restore guards plain tables on their first column only, and counts skipped rows as restored",
        "SNP-B4.1 (a merge adds each missing row, judged by the row's own key); SNP-B4.2 (a row counts as restored only when "
        "added); USER_GUIDE.md:1151-1153 (merge=True adds to what is there).",
        f"Live (c18-live-merge-guard): graph c18m with 3 nodes, 2 edges, labels and props archived "
        f"({j(MERGE, 'archive_counts')}); after erase and re-creating one edge, one label, one property "
        f"({j(MERGE, 'live_before_merge')}), merge restore left {j(MERGE, 'after_merge')} - rows missing {fm}; the result "
        f"reported restored_tables {j(MERGE, 'result', 'restored_tables')} and failed_rows {j(MERGE, 'result', 'failed_rows')}. "
        f"First SELECT * columns {j(MERGE, 'first_columns')} (P-1801 confirmed live).",
        "reproduced-live" if lost else ("not-reproduced" if MERGE else "confirmed-source"),
        [{"kind": "live", "ref": "c18-live-merge-guard"}, {"kind": "live", "ref": "c18-live-save-footprint"},
         {"kind": "inspected", "ref": "iris_vector_graph/_engine/snapshot.py:1287-1298"}],
        ["3.4-declared-reads", "3.6-keys"], "S2", "high",
        "Guard each table on its primary or unique key (as CONFIGURATION_TABLES does) and count only inserted rows."))
    ev = EVEC or {}
    lg = j(EROUTE, "legacy_table") or {}
    er = j(EROUTE, "edge_route") or {}
    lost_graph = j(EROUTE, "legacy_row_lost_graph")
    out.append(rec(
        "F-1803", "Edge vectors lose their graph and metadata in a snapshot",
        "SNP-B1.18 (edge vectors keep their graph and notes); Graph_KG.kg_EdgeEmbeddings is UNIQUE (graph_id, s, p, o_id) with "
        "metadata (iris_vector_graph/schema.py:455-464).",
        f"Live (c18-live-edge-routes, part b): a kg_EdgeEmbeddings row of graph c18L with metadata, planted by SQL (the shape the "
        f"table's key and metadata column exist for; the pin's own writer sends named-graph edge vectors to routes, part a), "
        f"{lg.get('planted_row')}; archived as {lg.get('archived_row')} (no graph_id, no metadata); after deleting it and a merge "
        f"restore: {lg.get('after_merge_restore')}.",
        "reproduced-live" if lost_graph else ("not-reproduced" if lg else "confirmed-source"),
        [{"kind": "live", "ref": "c18-live-edge-routes"}, {"kind": "inspected", "ref": "iris_vector_graph/_engine/snapshot.py:942-956, 1510-1552"}],
        ["3.4-declared-reads", "3.6-keys", "SYS-I2"], "S2", "high",
        "Export and restore graph_id and metadata; match on the full key.",
        "At the pin store_edge_embedding(graph=<named>) writes a routed kg_eemb_ table, not kg_EdgeEmbeddings "
        "(c18-live-edge-vectors), so the legacy-table path concerns rows written before routing or by SQL; the routed path has "
        "its own, larger defect F-C1804."))
    v = VAL or {}
    out.append(rec(
        "F-1804", "Native index values come back as text",
        "spec 255 (a value comes back with the type it was written with); SNP-B2.21.",
        f"Live (c18-live-value-types and c18-live-save-footprint): the archive line for the attribute is "
        f"{j(SAVE, 'archived_attr_lines')}; get_edge_attrs before {v.get('edge_attrs_before')} ({v.get('amount_type_before')}), "
        f"after merge restore {v.get('edge_attrs_after')} ({v.get('amount_type_after')}).",
        "reproduced-live" if v.get("amount_type_before") and v.get("amount_type_before") != v.get("amount_type_after") else (
            "not-reproduced" if v.get("amount_type_after") else "confirmed-source"),
        [{"kind": "live", "ref": "c18-live-value-types"}, {"kind": "live", "ref": "c18-live-save-footprint"},
         {"kind": "inspected", "ref": "iris_vector_graph/_engine/snapshot.py:1644-1646, 1679"}],
        ["3.5-decoders"], "S3", "high", "Archive the value's type (as the vector form does) or move values on the server."))
    ag = AGG or {}
    out.append(rec(
        "F-1805", "A merge restore overwrites temporal aggregates instead of combining them",
        "SNP-B4.6 (after a merge restore the timed summaries still match the timed events); TemporalIndex.cls:96-125.",
        f"Live (c18-live-aggregates): bucket {ag.get('bucket')} with 2 archived events and a third live one; aggregate count "
        f"before merge {ag.get('aggregate_count_before')} / window {ag.get('window_count_before')}; after merge restore "
        f"aggregate {ag.get('aggregate_count_after')} / window {ag.get('window_count_after')}.",
        "reproduced-live" if ag.get("aggregate_disagrees_with_window") else ("not-reproduced" if AGG else "confirmed-source"),
        [{"kind": "live", "ref": "c18-live-aggregates"}, {"kind": "inspected", "ref": "iris_vector_graph/_engine/snapshot.py:1679"}],
        ["3.6-frame", "SYS-I8"], "S2", "high",
        "Rebuild touched buckets and tlast after a merge (RebuildBucketAggregate, RebuildLatest) or refuse overlapping merges."))
    out.append(rec(
        "F-1806", "Graph.KG.Snapshot.ImportGlobals loads any global file without the allow-list",
        "SNP-X5.1 (every way to load globals keeps to the restore allow-list); snapshot.py:412-422 (an archive is a file anyone "
        "can write).",
        f"Live (c18-live-file-helpers): Graph.KG.Snapshot is deployed in AUDITC with {[x for x in (j(FILES, 'deployed_methods') or []) if not x.startswith('%')]}; "
        f"ImportGlobals('/nonexistent-ivgaudit-c18/') answered {j(FILES, 'ImportGlobals')} - callable over the Native API; "
        "its body runs $System.OBJ.Load on every *.gof (Snapshot.cls:24-35) with no list. No product code calls it.",
        "reproduced-live",
        [{"kind": "live", "ref": "c18-live-file-helpers"}, {"kind": "inspected", "ref": "iris_src/src/Graph/KG/Snapshot.cls:4-73"}],
        ["5c-refusals", "3.4-ownership"], "S2", "high", "Delete the unused methods, or apply the restore allow-list."))
    out.append(rec(
        "F-1807", "The HTTP snapshot endpoint can write two snapshots to one path",
        "Each save produces its own archive (POST /admin/snapshot answers the path it wrote).",
        f"Live (c18-live-http-endpoint): two POSTs in one second answered {j(HTTP, 'status')} with paths {j(HTTP, 'paths')}; "
        f"the file holds created_ts {j(HTTP, 'file_created_ts')} of the second (save timestamps {j(HTTP, 'snapshot_ts')}).",
        "reproduced-live" if j(HTTP, "first_archive_overwritten") else "confirmed-source",
        [{"kind": "live", "ref": "c18-live-http-endpoint"}, {"kind": "inspected", "ref": "iris_vector_graph/cypher_api.py:668-678"}],
        ["3.5-handlers"], "S3", "high", "Use a unique name (uuid or ms + counter) and refuse to overwrite."))
    # new findings
    out.append(rec(
        "F-C1801", "save_snapshot archives writes that never commit",
        "decisions.md HD-1802 (working): claim a consistent snapshot only with quiescent writers or a verified snapshot/epoch "
        "protocol, and declare the quiet-writer premise for the current exporter; SNP-Q1.17.",
        f"Live (c18-live-dirty-export): another connection opened a transaction (TLEVEL {j(DIRTY, 'writer_tlevel_during_save')}) "
        f"and created c18:ghost; save_snapshot ran; the writer rolled back; the DB holds {j(DIRTY, 'ghost_rows_in_db_after_rollback')} "
        f"ghost rows, the archive holds {j(DIRTY, 'ghost_in_archive')}. Model: {m('cmc-snap-as-built-committed')}, "
        f"{m('cmc-snap-as-built-dangling')} (an edge archived without its endpoint), reviewed export gate "
        f"{m('cmc-snap-reviewed')}, control {m('cmc-snap-ctl-gate')}, witness {m('cmc-snap-wit')}. Neither USER_GUIDE.md:1151-1168 "
        "nor ADMIN_GUIDE.md:975-1010 declares a quiet-writer premise; the docstring says only 'reads only' (snapshot.py:803).",
        "reproduced-live" if j(DIRTY, "archive_holds_never_committed_write") else "reproduced-model",
        [{"kind": "live", "ref": "c18-live-dirty-export"}, {"kind": "mc", "ref": "cmc-snap-as-built-committed"},
         {"kind": "mc", "ref": "cmc-snap-as-built-dangling"}, {"kind": "mc", "ref": "cmc-snap-reviewed"},
         {"kind": "control", "ref": "cmc-snap-ctl-gate"}, {"kind": "inspected", "ref": "iris_vector_graph/_engine/snapshot.py:864-1034"}],
        ["3.5-lockplans", "3.3-model-check", "SYS-P2"], "S2", "high",
        "Document the quiet-writer premise (HD-1802) and refuse or warn when transactions are open; or export under a "
        "namespace-wide export gate that writers respect.",
        "Intent: HD-1802 is a working assumption; the observation (an archive can hold content that never existed, which a "
        "restore then makes real) is beyond 'not point in time' and holds under any reading."))
    sw = SWAL or {}
    out.append(rec(
        "F-C1802", "restore_snapshot drops a global line it cannot write without raising or counting it",
        "SNP-X2.14 (a native index that cannot be written stops the restore; the error says what is done); restore docstring "
        "snapshot.py:1088-1094 ('A global it cannot write ... raises RuntimeError').",
        f"Live (c18-live-swallowed-lines): an archive with ^IVG.GraphMode lines {sw.get('archive_lines')}; the bad subscripts "
        f"set directly over the Native API -> {sw.get('direct_native_set_of_bad_subscripts')}; merge restore answered "
        f"{sw.get('restore_result')} (error {sw.get('restore_error')}); the good line was written: {sw.get('good_line_written')}. "
        "Source: _import_global_from_ndjson catches every per-line exception with logger.debug (snapshot.py:1665-1683); the unit "
        "test test_restore_raises_on_a_global_it_cannot_write patches the whole method to raise "
        "(tests/unit/test_460_r271_snapshot_raises.py:156-163), so the per-line path is untested.",
        "reproduced-live" if sw and not sw.get("bad_lines_reported") else ("not-reproduced" if sw else "confirmed-source"),
        [{"kind": "live", "ref": "c18-live-swallowed-lines"}, {"kind": "inspected", "ref": "iris_vector_graph/_engine/snapshot.py:1654-1692"},
         {"kind": "inspected", "ref": "tests/unit/test_460_r271_snapshot_raises.py:156-163"}],
        ["5c-refusals", "3.5-decoders"], "S2", "high",
        "Count failed lines in failed_rows (per global) or raise as documented; a test with a line IRIS refuses."))
    out.append(rec(
        "F-C1803", "Graph.KG.Snapshot's unused file helpers read, write and delete server files for any Native API caller",
        "ADMIN_GUIDE.md:450-473 grants the least-privilege reading role %Native_ClassExecution:U; nothing in the product "
        "needs server file access through IVG classes (no caller of ReadFileChunk/WriteFileChunk/DeleteDir/ExportGlobals).",
        f"Live (c18-live-file-helpers, as _SYSTEM): FileExists('/etc/hostname') = {j(FILES, 'FileExists')}, GetFileSize = "
        f"{j(FILES, 'GetFileSize')}, ReadFileChunk returned {j(FILES, 'ReadFileChunk')!r}. Source: WriteFileChunk "
        "(Snapshot.cls:49-57) writes any path, DeleteDir (:64-68) runs RemoveDirectoryTree on any path, ExportGlobals (:4-22) "
        "writes any global to any directory, all as the IRIS server's OS user, with no IVG check. Whether a user holding only "
        "the documented reading role can call them was not run: it needs a new IRIS user and role on the audit container "
        "(blocked-access: Security.Users/Roles changes are container configuration).",
        "reproduced-live",
        [{"kind": "live", "ref": "c18-live-file-helpers"}, {"kind": "inspected", "ref": "iris_src/src/Graph/KG/Snapshot.cls:4-73"},
         {"kind": "inspected", "ref": "docs/ADMIN_GUIDE.md:450-473"}, {"kind": "inspected", "ref": "scripts/setup_security.sql:5-7"}],
        ["3.4-ownership", "5c-refusals"], "S1", "medium",
        "Delete the file and global helpers (no product caller), or restrict them to an admin role and an allow-listed folder.",
        "Extends F-1806 from loading globals to arbitrary server file read/write/delete. Confidence medium: the reading-role "
        "reachability rests on ADMIN_GUIDE's grants and IRIS's resource model (file I/O is not resource-protected), not on a "
        "live call as that role."))
    out.append(rec(
        "F-C1804", "A snapshot carries no routed edge vectors (kg_eemb_ tables): a restore loses them silently",
        "ADMIN_GUIDE.md:984-986 (a snapshot holds kg_EdgeEmbeddings and each routed embedding table the registry names); "
        "SNP-I1 (each store is copied or its omission explained); SNP-B1.18.",
        f"Live (c18-live-edge-vectors, c18-live-edge-routes part a): store_edge_embedding(graph='c18w') wrote route "
        f"{er.get('registry_before')} with {er.get('route_rows_before')} row(s); the archive's members are "
        f"{er.get('archive_members')} (no kg_eemb_ file, no routed-table entry; the registry row is archived); after a replacing "
        f"restore (failed_rows {j(er, 'restore_result', 'failed_rows')}) the registry holds {er.get('registry_after')}, the route "
        f"table exists: {er.get('route_table_exists_after')}, rows: {er.get('route_rows_after')}; edge_vector_search on the graph: "
        f"{er.get('edge_vector_search_after')}. Source: routed_export_plan keeps only names is_routed_embedding_table accepts, "
        "node routes kg_emb_<16 hex> (snapshot.py:299-344; security.py:58-68 'False for an edge route'), and no other code exports "
        "or recreates kg_eemb_ tables.",
        "reproduced-live" if j(EROUTE, "edge_route_lost") or (EVEC and not EVEC.get("after_merge_restore_kg_EdgeEmbeddings")
                                                             and EVEC.get("stored_in")) else "confirmed-source",
        [{"kind": "live", "ref": "c18-live-edge-vectors"}, {"kind": "live", "ref": "c18-live-edge-routes"},
         {"kind": "inspected", "ref": "iris_vector_graph/_engine/snapshot.py:299-344, 960-1025"},
         {"kind": "inspected", "ref": "iris_vector_graph/security.py:58-80"}],
        ["3.1-coverage", "3.3a-writesets", "SNP-I1"], "S1", "high",
        "Plan and export edge routes (is_routed_edge_embedding_table) with their width and kind, recreate them on restore, and "
        "count a registry row whose table could not be restored as failed.",
        "Data loss: after a replacing restore the graph's edge vectors are gone and the report is complete-looking."))
    return out


def gates():
    G = {}

    def put(k, status, ev, rem=""):
        G[k] = {"status": status, "evidence": ev, "remaining": rem}
    put("3.1-cells", "closed", ["experiment/playbook-uplift/ontology/18-snapshot.md ## Cells (21 cells; the two open cells assigned to HD-1801)"])
    put("3.1-coverage", "closed", ["experiment/playbook-completion/models/breadth-c/inventory.json reconciliation.18 (22 entry points; the 8 lexically uncovered are SetNodeJSON (SNP-T1.9), the private helpers IsVector/Encode/Decode/NodeRef, and the plan helpers routed_export_plan/ledger_storage_globals/snapshot_globals/kg_export_subscripts (SNP-B1.7, SNP-I1.1))"],
        "no cell covers the Snapshot.cls file helpers (stated by SNP-T5/SNP-X5.1 only); import/export NDJSON, import_rdf, load_networkx, load_obo are excluded by the Scope line and owned by no module (modules/00.json)")
    put("3.1-intent", "closed", ["experiment/playbook-completion/decisions.md HD-1801, HD-1802"])
    put("3.2-coverage", "open", ["env_features"], "the IRIS contract must place each feature (uncommitted reads, Native API value round trip, SELECT * order, IdKey uniqueness, autocommit) inside its subset")
    put("3.3-L1", "open", ["models/breadth-c/src/restore.rs", "models/breadth-c/src/snapcut.rs"], "explorer machines are executable abstract models (bounded), not a Verus L1")
    put("3.3-L2", "open", [], "no L2 over the archive/ledger storage layout")
    put("3.3-refinement", "open", [], "not proved")
    put("3.3-controls", "open", ["cmc-restore-ctl-marks", "cmc-snap-ctl-gate"], "controls are rejected by the explorer, not by a proof")
    put("3.3-model-check", "closed", [m(x) for x in ("cmc-snap-as-built-committed", "cmc-snap-as-built-dangling", "cmc-snap-reviewed",
        "cmc-snap-ctl-gate", "cmc-snap-wit", "cmc-restore-as-built-history", "cmc-restore-as-built-redaction",
        "cmc-restore-as-built-grows", "cmc-restore-as-built-commit", "cmc-restore-reviewed", "cmc-restore-ctl-marks", "cmc-restore-wit")],
        "merge restore (F-1802/F-1805) is live-reproduced, not modelled")
    put("3.3a-writesets", "failed", ["experiment/playbook-uplift/semantics/WRITESETS.md (snapshot.restore_replace open for all 8 invariants)", "F-1801", "F-1805"],
        "snapshot.restore_merge is not a plan in semantics/writesets.json although it writes the ledger globals and ^KG(\"tagg\") (F-1805)")
    put("3.4-statements", "open", [], "not proved")
    put("3.4-ownership", "failed", ["F-1801", "F-C1803", "F-1806"], "restore sets ^IVG.Ledger and the ledger storage directly (Graph.KG.Ledger is their writer); the file/global helpers write outside every owner")
    put("3.4-storage-order", "closed", ["$RUN_DIR/checks/storage-order.json: no site in iris_vector_graph/_engine/snapshot.py or Graph/KG/Snapshot.cls"],
        "column-order reliance (SELECT * first column as the merge key, P-1801) is recorded under F-1802, not row order")
    put("3.4-declared-reads", "failed", ["F-1802", "F-1803"])
    put("3.5-handlers", "open", [], "not proved")
    put("3.5-lockplans", "failed", ["F-C1801", "c18-live-dirty-export", "footprints/18.json (restore takes no lock)"], "a lock plan (export gate / restore exclusion) per HD-1802")
    put("3.5-decoders", "failed", ["F-1804", "F-C1802"])
    put("3.6-frame", "failed", ["F-1805"])
    put("3.6-row-permutation", "closed", ["iris_vector_graph/_engine/snapshot.py:211-239 (RESTORE_TABLE_ORDER puts nodes first; endpoints registered per edge, :1175-1203)"], "inspected only")
    put("3.6-keys", "failed", ["F-1802", "F-1803"])
    put("3.6-fk", "closed", ["iris_vector_graph/_engine/snapshot.py:1175-1203 (edge endpoints registered in the edge's graph)", "c18-live-restore-footprint"], "inspected plus one live replace restore")
    put("3.6-capacity", "open", ["iris_vector_graph/_engine/snapshot.py:1103-1110 (every archive member read into memory)", "snapshot.py:862-1041 (whole archive built in memory)"], "no bound or streaming; not measured")
    put("3.7-trace-replay", "open", ["c18-live-restore-footprint (journal of a replace and a merge restore)"], "the journal trace is not replayed through M5")
    put("3.7-lock-log", "open", ["c18-live-restore-footprint"], "no lock plan to check against (none taken)")
    put("3.7-mutation", "open", [], "not done")
    put("3.8-findings-disposed", "closed", ["findings/audit/18.json"])
    put("5c-refusals", "failed", ["SNP-X2.1/X2.2: c18-live-refusals", "SNP-X2.14: F-C1802", "SNP-X5.1: F-1806"])
    return G


if __name__ == "__main__":
    out = footprints()
    (COMP / "footprints/18.json").write_text(json.dumps(out, indent=1) + "\n")
    print("footprints/18.json", out["validated"], "validated", len(out["mismatches"]), "mismatches")
    f = findings()
    (COMP / "findings/audit/18.json").write_text(json.dumps({"module": "18", "pin": PIN, "findings": f}, indent=1) + "\n")
    from collections import Counter
    print("findings", Counter(x["disposition"] for x in f))
    gb = gates()
    mod = json.loads((COMP / "modules/18.json").read_text()) if (COMP / "modules/18.json").exists() else {}
    mod.update({"module": "18", "name": "SNP", "pin": PIN, "gates_by_id": gb,
                "findings_summary": dict(Counter(x["disposition"] for x in f))})
    (COMP / "modules/18.json").write_text(json.dumps(mod, indent=1) + "\n")
