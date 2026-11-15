#!/usr/bin/env python3
"""Module 18 (snapshots) live checks in namespace AUDITC, journal-validated.

    bash experiment/playbook-completion/tools/locks.sh iris timeout 1500 python live/breadth-c/18/snp_live.py [checks...]

Non-destructive checks (save footprint, dirty export, server file helpers, HTTP endpoint names) touch only lane-C
scratch data (ids and graphs starting c18). The destructive group (replacing and merge restores, ledger enable,
PurgeAll, erase_all) runs only when AUDITC holds no content but this lane's c18 scratch data; otherwise it refuses
and says what it found. Each check writes $RUN_DIR/breadth-c/18/<check>.json; the summary goes to
live/breadth-c/18/results.json. Nothing is compiled, no product file is changed.
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
import traceback
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from jcheck import Lane, run_dir, dump, NS  # noqa: E402

OUT = run_dir("18")
SNAPDIR = OUT / "archives"
SNAPDIR.mkdir(exist_ok=True)
RESULTS = HERE / "results.json"


def _zip_lines(path, member):
    with zipfile.ZipFile(path) as z:
        if member not in z.namelist():
            return []
        return [json.loads(x) for x in z.read(member).decode().splitlines() if x.strip()]


def _zip_names(path):
    with zipfile.ZipFile(path) as z:
        return z.namelist()


def _first_cols(path):
    out = {}
    for t in ("nodes", "rdf_edges", "rdf_labels", "rdf_props", "docs"):
        rows = _zip_lines(path, f"sql/Graph_KG_{t}.ndjson")
        out[t] = list(rows[0].keys()) if rows else None
    return out


def seed(L, g="c18g"):
    e = L.eng
    e.create_node("c18:a", labels=["C18"], properties={"name": "a"}, graph=g)
    e.create_node("c18:b", labels=["C18"], properties={"name": "b"}, graph=g)
    e.create_edge("c18:a", "R", "c18:b", graph=g)


def foreign_content(L):
    """Rows or ledger state in AUDITC that are not lane-C (c18) scratch data."""
    q = {
        "nodes": "SELECT COUNT(*) FROM Graph_KG.nodes WHERE NOT (node_id %STARTSWITH 'c18')",
        "rdf_edges": "SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE NOT (s %STARTSWITH 'c18')",
        "rdf_props": "SELECT COUNT(*) FROM Graph_KG.rdf_props WHERE NOT (s %STARTSWITH 'c18')",
        "rdf_labels": "SELECT COUNT(*) FROM Graph_KG.rdf_labels WHERE NOT (s %STARTSWITH 'c18')",
        "kg_EdgeEmbeddings": "SELECT COUNT(*) FROM Graph_KG.kg_EdgeEmbeddings WHERE NOT (s %STARTSWITH 'c18')",
        "embedding_registry": "SELECT COUNT(*) FROM Graph_KG.embedding_registry WHERE NOT (graph_id %STARTSWITH 'c18') AND graph_id <> ''",
    }
    found = {k: L.c.sql(v)[0][0] for k, v in q.items()}
    found["ledger_state"] = L.eng.ledger.meta()["state"]
    bad = {k: v for k, v in found.items() if (k != "ledger_state" and v) or (k == "ledger_state" and v != "never-enabled")}
    return found, bad


# ------------------------------------------------------------------------------------------------ non-destructive
def check_save_footprint(L):
    """SNP-I2: saving reads the namespace and writes nothing to it (journal); archive layout facts."""
    seed(L)
    L.eng.create_edge_temporal("c18:a", "T", "c18:b", timestamp=1_700_000_000, attrs={"amount": 20}, graph="c18g")
    path = str(SNAPDIR / "save_footprint.snapshot")
    r = L.journaled("save_snapshot", lambda: L.eng.save_snapshot(path))
    kg = _zip_lines(path, "globals/KG.ndjson")
    attr_lines = [x for x in kg if x["k"][:1] == ["edgeprop"] and "c18:a" in x["k"]] or \
                 [x for x in kg if "amount" in json.dumps(x["k"])]
    res = {
        "observes": "SNP-I2 (save writes nothing), P-1801 (first SELECT * column), SNP-T1.11 (values archived as text)",
        "journal": {k: v for k, v in r.items() if k != "raw"},
        "writes_by_save_pid": r["records"],
        "first_columns": _first_cols(path),
        "archived_attr_lines": attr_lines[:5],
        "pass": r["error"] is None and r["records"] == 0,
    }
    return res


def check_dirty_export(L):
    """HD-1802: a save while another connection's transaction is open archives its uncommitted write."""
    from jcheck import second_engine
    c2, e2 = second_engine()
    try:
        cur2 = c2.conn.cursor()
        cur2.execute("START TRANSACTION")
        e2.create_node("c18:ghost", labels=["C18Ghost"], properties={"p": "uncommitted"})
        lvl = c2.sql("SELECT $TLEVEL")[0][0]
        path = str(SNAPDIR / "dirty_export.snapshot")
        L.eng.save_snapshot(path)
        cur2.execute("ROLLBACK")
        after = L.c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = 'c18:ghost'")[0][0]
        nodes = [x for x in _zip_lines(path, "sql/Graph_KG_nodes.ndjson") if x.get("node_id") == "c18:ghost"]
        props = [x for x in _zip_lines(path, "sql/Graph_KG_rdf_props.ndjson") if x.get("s") == "c18:ghost"]
        kg = [x for x in _zip_lines(path, "globals/KG.ndjson") if "c18:ghost" in x["k"]]
        return {
            "observes": "HD-1802 / SNP-Q1.17: export of a write that never commits",
            "writer_tlevel_during_save": lvl,
            "ghost_rows_in_db_after_rollback": after,
            "ghost_in_archive": {"nodes": nodes, "rdf_props": props, "kg_lines": kg[:5]},
            "archive_holds_never_committed_write": bool(nodes or props or kg) and after == 0,
        }
    finally:
        try:
            c2.sql("ROLLBACK")
        except Exception:
            pass
        c2.close()


def check_file_helpers(L):
    """F-1806 and the other Graph.KG.Snapshot file helpers: callable over the Native API by a namespace user."""
    o = L.c
    out = {"observes": "F-1806; Snapshot.cls:4-73 deployed helpers", "caller": "_SYSTEM over the Native API"}
    for m, args in [("FileExists", ("/etc/hostname",)), ("GetFileSize", ("/etc/hostname",)),
                    ("ReadFileChunk", ("/etc/hostname", 0, 200)),
                    ("ImportGlobals", ("/nonexistent-ivgaudit-c18/",))]:
        try:
            out[m] = str(o.call("Graph.KG.Snapshot", m, *args))
        except Exception as e:
            out[m] = f"ERROR {type(e).__name__}: {e}"[:300]
    out["deployed_methods"] = [r[0] for r in o.sql(
        "SELECT Name FROM %Dictionary.CompiledMethod WHERE parent = 'Graph.KG.Snapshot' ORDER BY Name")]
    out["callers_in_product"] = "none (grep at the pin: ExportGlobals/ImportGlobals/ReadFileChunk/WriteFileChunk/DeleteDir are called by no product code)"
    return out


def check_http_endpoint(L):
    """F-1807: POST /admin/snapshot twice within one second -> one path, the second save overwrites the first."""
    os.environ.update({"IRIS_HOST": "127.0.0.1", "IRIS_PORT": os.environ["IVG_PORT"], "IRIS_NAMESPACE": NS,
                       "IRIS_USERNAME": "_SYSTEM", "IRIS_PASSWORD": "SYS", "BOLT_ENABLED": "0",
                       "IVG_SNAPSHOT_DIR": str(SNAPDIR)})
    os.environ.pop("IVG_API_KEY", None)
    from fastapi.testclient import TestClient
    import iris_vector_graph.cypher_api as api
    client = TestClient(api.app)  # no lifespan: no Bolt listener
    try:
        # align to the start of a second so both requests fall in it
        time.sleep(1 - (time.time() % 1) + 0.01)
        r1 = client.post("/admin/snapshot")
        r2 = client.post("/admin/snapshot")
        j1, j2 = r1.json(), r2.json()
        p1, p2 = j1.get("path"), j2.get("path")
        ts1 = j1.get("result", {}).get("snapshot_ts")
        ts2 = j2.get("result", {}).get("snapshot_ts")
        info = None
        if p2 and Path(p2).exists():
            with zipfile.ZipFile(p2) as z:
                info = json.loads(z.read("metadata.json"))["created_ts"]
        return {"observes": "F-1807", "status": [r1.status_code, r2.status_code], "paths": [p1, p2],
                "same_path": p1 == p2, "snapshot_ts": [ts1, ts2], "file_created_ts": info,
                "first_archive_overwritten": p1 == p2 and info == ts2 and ts1 != ts2}
    finally:
        with api._engine_lock:
            api._reset_engine()


# ------------------------------------------------------------------------------------------------ destructive
def _restore(L, label, path, merge):
    return L.journaled(label, lambda: L.eng.restore_snapshot(path, merge=merge))


def _strip(r):
    return {k: v for k, v in r.items() if k != "raw"}


def check_restore_footprint(L):
    """SNP-B3/T2.10/T3.1: what a replacing restore writes, and in which transactions (journal)."""
    seed(L)
    L.eng.create_edge_temporal("c18:a", "T", "c18:b", timestamp=1_700_000_000, attrs={"amount": 20}, graph="c18g")
    path = str(SNAPDIR / "restore_footprint.snapshot")
    L.eng.save_snapshot(path)
    r = _restore(L, "restore_replace", path, False)
    after = L.c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE graph_id = 'c18g'")[0][0]
    rm = _restore(L, "restore_merge_same_archive", path, True)
    return {"observes": "SNP-B3, SNP-T2.10, SNP-T3.1, SYS-I4 (restore is not one transaction)",
            "replace": _strip(r), "edges_after": after, "merge_same_archive": _strip(rm)}


def check_merge_guard(L):
    """F-1802: merge restore guards plain tables on the first column and counts skipped rows as restored."""
    e = L.eng
    g = "c18m"
    for n in ("c18:m1", "c18:m2", "c18:m3"):
        e.create_node(n, labels=["C18M"], properties={"k": n}, graph=g)
    e.create_edge("c18:m1", "R", "c18:m2", graph=g)
    e.create_edge("c18:m2", "R", "c18:m3", graph=g)
    path = str(SNAPDIR / "merge_guard.snapshot")
    e.save_snapshot(path)

    def counts():
        return {t: L.c.sql(f"SELECT COUNT(*) FROM Graph_KG.{t} WHERE graph_id = ?", g)[0][0]
                for t in ("nodes", "rdf_edges", "rdf_labels", "rdf_props")}
    full = counts()
    e.erase_graph(g)
    e.create_node("c18:m1", labels=["C18M"], properties={"k": "c18:m1"}, graph=g)
    e.create_node("c18:m2", graph=g)
    e.create_edge("c18:m1", "R", "c18:m2", graph=g)
    before = counts()
    r = _restore(L, "merge_restore", path, True)
    after = counts()
    return {"observes": "F-1802 / SNP-B4.1 / SNP-B4.2", "archive_counts": full, "live_before_merge": before,
            "after_merge": after, "result": r["result"], "error": r["error"],
            "rows_missing_after_merge": {t: full[t] - after[t] for t in full},
            "first_columns": _first_cols(path), "journal": _strip(r)}


def check_edge_vectors(L):
    """F-1803: an edge vector of a named graph comes back in the default graph without metadata."""
    e = L.eng
    g = "c18v"
    e.create_node("c18:v1", graph=g)
    e.create_node("c18:v2", graph=g)
    e.create_edge("c18:v1", "R", "c18:v2", graph=g)
    e.store_edge_embedding("c18:v1", "R", "c18:v2", [0.1, 0.2, 0.3, 0.4], metadata={"src": "c18"}, graph=g)
    where = {}
    for t in [r[0] for r in L.c.sql("SELECT table_name FROM Graph_KG.embedding_registry")] + ["kg_EdgeEmbeddings"]:
        try:
            rows = L.c.sql(f"SELECT graph_id, s, metadata FROM Graph_KG.{t} WHERE s = 'c18:v1'")
            if rows:
                where[t] = [list(map(str, x)) for x in rows]
        except Exception:
            pass
    path = str(SNAPDIR / "edge_vectors.snapshot")
    e.save_snapshot(path)
    arch = [x for x in _zip_lines(path, "sql/Graph_KG_kg_EdgeEmbeddings.ndjson") if x.get("s") == "c18:v1"]
    arch_routed = {n: [x for x in _zip_lines(path, n) if x.get("s") == "c18:v1"]
                   for n in _zip_names(path) if "kg_eemb" in n}
    e.erase_graph(g)
    r = _restore(L, "merge_restore_edge_vectors", path, True)
    back = L.c.sql("SELECT graph_id, s, metadata FROM Graph_KG.kg_EdgeEmbeddings WHERE s = 'c18:v1'")
    return {"observes": "F-1803 / SNP-B1.18", "stored_in": where, "archived_legacy_rows": arch,
            "archived_routed_rows": arch_routed, "after_merge_restore_kg_EdgeEmbeddings": [list(map(str, x)) for x in back],
            "result": r["result"], "error": r["error"]}


def check_value_types(L):
    """F-1804: a numeric temporal attribute reads back as text after a snapshot round trip."""
    e = L.eng
    g = "c18t"
    e.create_edge_temporal("c18:t1", "T", "c18:t2", timestamp=1_700_000_100, attrs={"amount": 20}, graph=g)
    before = e.get_edges_in_window("c18:t1", "T", 1_700_000_000, 1_700_000_200, graph=g)
    attrs_before = e.get_edge_attrs(1_700_000_100, "c18:t1", "T", "c18:t2", graph=g)
    path = str(SNAPDIR / "value_types.snapshot")
    e.save_snapshot(path)
    e.erase_graph(g)
    r = _restore(L, "merge_restore_values", path, True)
    after = e.get_edges_in_window("c18:t1", "T", 1_700_000_000, 1_700_000_200, graph=g)
    attrs = e.get_edge_attrs(1_700_000_100, "c18:t1", "T", "c18:t2", graph=g)
    return {"observes": "F-1804 / SNP-B2.21", "window_before": before, "window_after": after,
            "edge_attrs_before": attrs_before, "edge_attrs_after": attrs,
            "amount_type_before": type(attrs_before.get("amount")).__name__ if isinstance(attrs_before, dict) else None,
            "amount_type_after": type(attrs.get("amount")).__name__ if isinstance(attrs, dict) else None, "result": r["result"], "error": r["error"]}


def check_aggregates(L):
    """F-1805: a merge restore overwrites a live bucket aggregate with the archive's."""
    e = L.eng
    g = "c18a"
    t0 = 1_700_001_000 - (1_700_001_000 % 300)
    e.create_edge_temporal("c18:s", "P", "c18:o1", timestamp=t0 + 10, weight=1.0, graph=g)
    e.create_edge_temporal("c18:s", "P", "c18:o2", timestamp=t0 + 20, weight=1.0, graph=g)
    path = str(SNAPDIR / "aggregates.snapshot")
    e.save_snapshot(path)
    e.create_edge_temporal("c18:s", "P", "c18:o3", timestamp=t0 + 30, weight=1.0, graph=g)
    agg_before = e.get_temporal_aggregate("c18:s", "P", "count", t0, t0 + 300, graph=g)
    win_before = len(e.get_edges_in_window("c18:s", "P", t0, t0 + 299, graph=g))
    r = _restore(L, "merge_restore_aggregates", path, True)
    agg_after = e.get_temporal_aggregate("c18:s", "P", "count", t0, t0 + 300, graph=g)
    win_after = len(e.get_edges_in_window("c18:s", "P", t0, t0 + 299, graph=g))
    return {"observes": "F-1805 / SNP-B4.6", "bucket": t0, "aggregate_count_before": agg_before,
            "window_count_before": win_before, "aggregate_count_after": agg_after, "window_count_after": win_after,
            "aggregate_disagrees_with_window": agg_after != win_after, "result": r["result"], "error": r["error"]}


def check_swallowed_global_lines(L):
    """New: a global line the restore cannot set is dropped silently: not raised, not in failed_rows (SNP-X2.14)."""
    src = SNAPDIR / "swallow.snapshot"
    meta = {"version": "1.1", "layout": "graph-scoped", "created_ts": int(time.time() * 1000), "tables": {},
            "globals": {"IVG.GraphMode": {"format": "ndjson"}}}
    lines = [json.dumps({"k": ["c18x"], "v": "1"}), json.dumps({"k": [""], "v": "1"}),
             json.dumps({"k": ["c18y", ""], "v": "1"})]
    with zipfile.ZipFile(src, "w") as z:
        z.writestr("metadata.json", json.dumps(meta))
        z.writestr("globals/IVG.GraphMode.ndjson", "\n".join(lines))
    direct = {}
    for subs in ([""], ["c18y", ""]):
        try:
            L.c.o.set("1", "^IVG.GraphMode", *subs)
            direct[json.dumps(subs)] = "set ok"
        except Exception as e:
            direct[json.dumps(subs)] = f"{type(e).__name__}: {e}"[:200]
    r = _restore(L, "merge_restore_bad_lines", str(src), True)
    present = {"c18x": L.c.o.isDefined("^IVG.GraphMode", "c18x")}
    L.c.o.kill("^IVG.GraphMode", "c18x")
    return {"observes": "SNP-X2.14 vs snapshot.py:1679-1683 (per-line except: logger.debug)", "archive_lines": lines,
            "direct_native_set_of_bad_subscripts": direct, "restore_result": r["result"], "restore_error": r["error"],
            "good_line_written": present,
            "bad_lines_reported": bool((r["result"] or {}).get("failed_rows")) or r["error"] is not None}


def check_refusals(L):
    """SNP-X2.1 (strict ledger) and SNP-X2.2 (caller transaction): refused, nothing written (journal)."""
    path = str(SNAPDIR / "refusal.snapshot")
    seed(L)
    L.eng.save_snapshot(path)
    out = {"observes": "SNP-X2.1, SNP-X2.2, SYS-I3"}
    L.eng.ledger.enable()
    L.eng.ledger.set_strict(True)
    out["strict"] = _strip(_restore(L, "restore_in_strict", path, False))
    L.eng.ledger.set_strict(False)
    cur = L.c.conn.cursor()
    cur.execute("START TRANSACTION")
    L.eng.create_node("c18:intxn")
    out["caller_txn"] = _strip(_restore(L, "restore_in_caller_txn", path, False))
    cur.execute("ROLLBACK")
    L.c.call("Graph.KG.Ledger", "PurgeAll")
    return out


def check_ledger_overlay(L):
    """F-1801 / HD-1801: an older archive restored over a ledger that moved on; then a redaction undone."""
    from iris_vector_graph.ledger import Changeset
    e, o = L.eng, L.c.o
    L.c.call("Graph.KG.Ledger", "PurgeAll")
    e.ledger.enable()
    cs1 = Changeset(actor="c18", actor_type="agent", message="one").create_node("c18:L1", labels=["C18L"])
    r1 = e.ledger.commit(cs1)
    path = str(SNAPDIR / "ledger_old.snapshot")
    e.save_snapshot(path)
    cs2 = Changeset(actor="c18", actor_type="agent", message="two", idempotency_key="c18-k2").create_node("c18:L2")
    r2 = e.ledger.commit(cs2)
    head_before = e.ledger.meta()
    rr = _restore(L, "restore_older_archive_over_moved_ledger", path, False)
    st = {
        "meta_after_restore": e.ledger.meta(),
        "rec_seq_after_head_present": [o.isDefined("^IVG.Ledger", "rec", r2.revision.seq, 1)],
        "revision_rows": [x[0] for x in L.c.sql("SELECT seq FROM Graph_KG.ledger_revisions ORDER BY seq")],
        "idem_c18_k2": str(o.get("^IVG.Ledger", "idem", "c18-k2")),
    }
    cs3 = Changeset(actor="c18", actor_type="agent", message="three").create_node("c18:L3")
    try:
        r3 = e.ledger.commit(cs3)
        st["commit_after_restore"] = {"ok": True, "seq": r3.revision.seq}
    except Exception as ex:
        st["commit_after_restore"] = {"ok": False, "error": f"{type(ex).__name__}: {ex}"[:400]}
    try:
        rr2 = e.ledger.commit(Changeset(actor="c18", actor_type="agent", message="two",
                                        idempotency_key="c18-k2").create_node("c18:L2"))
        st["retry_of_k2"] = {"replayed": rr2.replayed, "seq": rr2.revision.seq,
                             "head_seq": e.ledger.meta()["head_seq"]}
    except Exception as ex:
        st["retry_of_k2"] = {"error": f"{type(ex).__name__}: {ex}"[:400]}
    try:
        st["verify"] = str(e.ledger.verify().result)
    except Exception as ex:
        st["verify"] = f"{type(ex).__name__}: {ex}"[:300]

    # part 2: an archive made before a redaction
    L.c.call("Graph.KG.Ledger", "PurgeAll")
    e.erase_all()
    e.ledger.enable()
    cs = Changeset(actor="c18", actor_type="agent", message="tenant data").create_node(
        "c18t|x", labels=["C18T"], properties={"secret": "c18-sensitive"})
    rt = e.ledger.commit(cs)
    path2 = str(SNAPDIR / "ledger_before_redaction.snapshot")
    e.save_snapshot(path2)
    e.delete_nodes_by_prefix("c18t|")
    receipt = e.ledger.redact(None, prefix="c18t")
    recs_redacted = [rec.to_wire() for rec in e.ledger.get_revision(rt.revision.revision_id).records]
    rr3 = _restore(L, "restore_pre_redaction_archive", path2, False)
    recs_after = [rec.to_wire() for rec in e.ledger.get_revision(rt.revision.revision_id).records]
    marks = []
    k = ""
    while True:
        k = o.nextSubscript(False, "^IVG.Ledger", "redactedRev", k)
        if not k:
            break
        marks.append(k)
    part2 = {"receipt": str(receipt)[:400], "records_after_redaction": recs_redacted,
             "records_after_restore": recs_after, "redactedRev_marks_after_restore": marks,
             "content_back_in_history": "c18-sensitive" in json.dumps(recs_after),
             "restore_error": rr3["error"]}
    L.c.call("Graph.KG.Ledger", "PurgeAll")
    return {"observes": "F-1801, HD-1801, SNP-I3.6, SNP-B3.7, SYS-I5", "head_before_restore": head_before,
            "restore": _strip(rr), "after": st, "part2_redaction": part2}


def check_edge_routes(L):
    """Follow-up to edge_vectors: (a) an edge route kg_eemb_* of a named graph through save + replacing restore;
    (b) F-1803 as stated: a legacy kg_EdgeEmbeddings row of a named graph (planted by SQL, the shape the table's
    UNIQUE (graph_id, s, p, o_id) and metadata column exist for) through save + merge restore."""
    e = L.eng
    g = "c18w"
    e.create_node("c18:w1", graph=g)
    e.create_node("c18:w2", graph=g)
    e.create_edge("c18:w1", "R", "c18:w2", graph=g)
    e.store_edge_embedding("c18:w1", "R", "c18:w2", [0.5, 0.5, 0.5, 0.5], metadata={"src": "c18w"}, graph=g)
    reg = [list(map(str, r)) for r in L.c.sql("SELECT table_name, graph_id, kind, dimension FROM Graph_KG.embedding_registry WHERE graph_id = ?", g)]
    route = reg[0][0] if reg else None
    rows_before = L.c.sql(f"SELECT COUNT(*) FROM Graph_KG.{route}")[0][0] if route else None
    path = str(SNAPDIR / "edge_routes.snapshot")
    saved = e.save_snapshot(path)
    names = _zip_names(path)
    r = _restore(L, "replace_restore_edge_route", path, False)
    def table_exists(t):
        return L.c.sql("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'Graph_KG' AND TABLE_NAME = ?", t)[0][0]
    reg_after = [list(map(str, x)) for x in L.c.sql("SELECT table_name, graph_id, kind, index_state FROM Graph_KG.embedding_registry WHERE graph_id = ?", g)]
    exists_after = table_exists(route) if route else None
    rows_after = None
    if exists_after:
        rows_after = L.c.sql(f"SELECT COUNT(*) FROM Graph_KG.{route}")[0][0]
    try:
        srch = e.edge_vector_search([0.5, 0.5, 0.5, 0.5], top_k=3, graph=g) if hasattr(e, "edge_vector_search") else None
        srch = repr(srch)[:300]
    except Exception as ex:
        srch = f"{type(ex).__name__}: {ex}"[:300]
    part_a = {"registry_before": reg, "route_rows_before": rows_before, "archive_members": names,
              "archive_routed_tables": saved.get("tables", {}).get(f"Graph_KG.{route}"),
              "restore_result": r["result"], "registry_after": reg_after, "route_table_exists_after": exists_after,
              "route_rows_after": rows_after, "edge_vector_search_after": srch}
    # (b) the legacy table row of a named graph
    L.c.sql("INSERT INTO Graph_KG.kg_EdgeEmbeddings (graph_id, s, p, o_id, emb, metadata) "
            "VALUES ('c18L', 'c18:l1', 'R', 'c18:l2', TO_VECTOR('[1,2,3,4]', DOUBLE), '{\"m\": 1}')")
    before = [list(map(str, x)) for x in L.c.sql("SELECT graph_id, s, metadata FROM Graph_KG.kg_EdgeEmbeddings WHERE s = 'c18:l1'")]
    path2 = str(SNAPDIR / "legacy_edge_vectors.snapshot")
    e.save_snapshot(path2)
    arch = [x for x in _zip_lines(path2, "sql/Graph_KG_kg_EdgeEmbeddings.ndjson") if x.get("s") == "c18:l1"]
    L.c.sql("DELETE FROM Graph_KG.kg_EdgeEmbeddings WHERE s = 'c18:l1'")
    r2 = _restore(L, "merge_restore_legacy_edge_vector", path2, True)
    after = [list(map(str, x)) for x in L.c.sql("SELECT graph_id, s, metadata FROM Graph_KG.kg_EdgeEmbeddings WHERE s = 'c18:l1'")]
    part_b = {"planted_row": before, "archived_row": arch, "after_merge_restore": after, "restore_result": r2["result"]}
    return {"observes": "edge routes in snapshots (new) and F-1803 (legacy table)", "edge_route": part_a,
            "legacy_table": part_b,
            "edge_route_lost": bool(route) and (not exists_after or not rows_after),
            "legacy_row_lost_graph": bool(after) and all(x[0] == "" for x in after)}


NONDESTRUCTIVE = {"save_footprint": check_save_footprint, "dirty_export": check_dirty_export,
                  "file_helpers": check_file_helpers, "http_endpoint": check_http_endpoint}
DESTRUCTIVE = {"restore_footprint": check_restore_footprint, "merge_guard": check_merge_guard,
               "edge_vectors": check_edge_vectors, "value_types": check_value_types, "aggregates": check_aggregates,
               "swallowed_global_lines": check_swallowed_global_lines, "refusals": check_refusals,
               "ledger_overlay": check_ledger_overlay, "edge_routes": check_edge_routes}


def cleanup(L):
    for g in ("c18g", "c18m", "c18v", "c18t", "c18a"):
        try:
            L.eng.erase_graph(g)
        except Exception:
            pass
    try:
        L.eng.delete_nodes_by_prefix("c18")
    except Exception:
        pass


def main():
    want = sys.argv[1:] or list(NONDESTRUCTIVE) + list(DESTRUCTIVE)
    summary = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}
    with Lane("c18", embedding_dimension=4) as L:
        found, bad = foreign_content(L)
        destructive_ok = not bad
        for name in want:
            fn = NONDESTRUCTIVE.get(name) or DESTRUCTIVE.get(name)
            if name in DESTRUCTIVE and not destructive_ok:
                res = {"skipped": "AUDITC holds content that is not lane C scratch data", "found": found}
            else:
                t0 = time.time()
                try:
                    res = fn(L)
                except Exception as ex:
                    res = {"exception": f"{type(ex).__name__}: {ex}", "traceback": traceback.format_exc()[-3000:]}
                res["seconds"] = round(time.time() - t0, 2)
                res["utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                if name in DESTRUCTIVE:
                    # back to an empty namespace with no ledger: this lane's own data only was there
                    try:
                        L.c.call("Graph.KG.Ledger", "PurgeAll")
                        L.eng.erase_all()
                    except Exception as ex:
                        res["cleanup_error"] = str(ex)
                else:
                    cleanup(L)
            dump(OUT / f"{name}.json", res)
            summary[name] = {k: v for k, v in res.items() if k not in ("journal", "replace", "merge_same_archive",
                                                                          "traceback")}
            print(name, json.dumps(res, default=str)[:1500])
        summary["_foreign_content_at_start"] = found
    RESULTS.write_text(json.dumps(summary, indent=1, sort_keys=True, default=str) + "\n")


if __name__ == "__main__":
    main()
